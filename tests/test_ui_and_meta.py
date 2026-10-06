from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from patient_api.api import STATIC_DIR, create_app
from patient_api.config import Settings
from patient_api.repository import InMemoryRepository

ASSETS = ["app.js", "styles.css", "theme.js", "favicon.svg"]


class TestDashboard:
    def test_root_serves_the_dashboard_with_a_strict_csp(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        csp = response.headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "Patient Records" in response.text

    @pytest.mark.parametrize("name", ASSETS)
    def test_assets_are_served(self, client: TestClient, name: str) -> None:
        response = client.get(f"/static/{name}")
        assert response.status_code == 200
        assert response.content

    def test_every_asset_referenced_by_the_page_exists(self, client: TestClient) -> None:
        html = client.get("/").text
        for path in re.findall(r'(?:src|href)="(/static/[^"]+)"', html):
            assert client.get(path).status_code == 200, path

    def test_static_route_does_not_allow_path_traversal(self, client: TestClient) -> None:
        assert client.get("/static/../api.py").status_code == 404
        assert client.get("/static/%2e%2e/api.py").status_code == 404

    def test_dashboard_is_not_in_the_openapi_schema(self, client: TestClient) -> None:
        assert "/" not in client.get("/openapi.json").json()["paths"]

    def test_responses_forbid_content_sniffing(self, client: TestClient) -> None:
        assert client.get("/health").headers["x-content-type-options"] == "nosniff"


class TestCspCompatibility:
    """The page runs under ``script-src 'self'; style-src 'self'``, so these must hold."""

    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    def test_no_inline_scripts(self) -> None:
        for tag in re.findall(r"<script\b[^>]*>", self.html):
            assert "src=" in tag, tag

    def test_no_inline_styles(self) -> None:
        assert "<style" not in self.html
        assert not re.search(r"\sstyle\s*=", self.html)

    def test_no_inline_event_handlers(self) -> None:
        assert not re.search(r'\son[a-z]+\s*=\s*"', self.html)

    def test_no_third_party_requests(self) -> None:
        for name in ["index.html", *ASSETS]:
            text = (STATIC_DIR / name).read_text(encoding="utf-8")
            assert not re.search(r"https?://(?!www\.w3\.org)", text), name


class TestScriptSafety:
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "pattern",
        [r"\.innerHTML", r"\.outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\("],
    )
    def test_never_injects_markup_from_api_data(self, pattern: str) -> None:
        assert not re.search(pattern, self.js)

    def test_does_not_use_set_attribute_for_style(self) -> None:
        assert not re.search(r"setAttribute\(\s*['\"]style", self.js)


class TestMeta:
    def test_reports_version_and_memory_source(self, client: TestClient) -> None:
        body = client.get("/meta").json()
        assert body["source"] == "memory"
        assert re.fullmatch(r"\d+\.\d+\.\d+", body["version"])

    def test_file_source(self, sample_file: Path) -> None:
        app = TestClient(create_app(settings=Settings(data_file=sample_file)))
        assert app.get("/meta").json()["source"] == "file"

    def test_remote_source_does_not_need_credentials_or_network(self) -> None:
        app = TestClient(create_app(settings=Settings()))
        response = app.get("/meta")
        assert response.status_code == 200
        assert response.json()["source"] == "remote"

    def test_never_exposes_credentials(self) -> None:
        secret = "hunter2-do-not-leak"
        app = TestClient(
            create_app(settings=Settings(student_id="someone", password=secret)),
            raise_server_exceptions=False,
        )
        for path in ("/meta", "/health", "/openapi.json", "/"):
            assert secret not in app.get(path).text


class TestSorting:
    def test_default_is_by_id(self, client: TestClient) -> None:
        ids = [p["id"] for p in client.get("/patients").json()["items"]]
        assert ids == [1, 2, 3, 4]

    def test_sort_by_bill_descending(self, client: TestClient) -> None:
        body = client.get("/patients", params={"sort": "totalBill", "order": "desc"}).json()
        assert [p["id"] for p in body["items"]] == [3, 2, 1, 4]

    def test_sort_by_name_is_case_insensitive(self, client: TestClient) -> None:
        body = client.get("/patients", params={"sort": "name", "order": "desc"}).json()
        assert body["items"][0]["name"] == "Dev Shah"

    def test_sort_applies_before_pagination(self, client: TestClient) -> None:
        body = client.get(
            "/patients", params={"sort": "age", "order": "desc", "limit": 2, "offset": 1}
        ).json()
        assert [p["age"] for p in body["items"]] == [60, 40]

    def test_ties_keep_dataset_order(self) -> None:
        from patient_api import analytics

        from .conftest import make_patient

        tied = [make_patient(5, age=1), make_patient(3, age=1), make_patient(9, age=1)]
        assert [p.id for p in analytics.sort_patients(tied, "age")] == [5, 3, 9]
        assert [p.id for p in analytics.sort_patients(tied, "age", descending=True)] == [5, 3, 9]

    def test_unknown_sort_field_is_rejected(self, client: TestClient) -> None:
        assert client.get("/patients", params={"sort": "password"}).status_code == 422
        assert client.get("/patients", params={"order": "sideways"}).status_code == 422


def test_in_memory_repository_reports_its_source() -> None:
    assert InMemoryRepository([]).source == "memory"
