from __future__ import annotations

from fastapi.testclient import TestClient

from patient_api.api import create_app
from patient_api.config import Settings
from patient_api.exceptions import AuthenticationError, DatasetError
from patient_api.repository import InMemoryRepository


class _FailingRepo:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def all(self):  # type: ignore[no-untyped-def]
        raise self._error


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_request_headers_are_added(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"
    assert float(response.headers["X-Process-Time-ms"]) >= 0


def test_request_id_generated_when_absent(client: TestClient) -> None:
    assert len(client.get("/health").headers["X-Request-ID"]) == 12


class TestGetPatient:
    def test_found(self, client: TestClient) -> None:
        body = client.get("/patients/3").json()
        assert body["name"] == "Chitra Nair"
        assert body["daysAdmitted"] == 5  # camelCase contract preserved
        assert body["bill"] == {"consultation": 300, "medicine": 400, "lab": 300}

    def test_not_found(self, client: TestClient) -> None:
        response = client.get("/patients/999")
        assert response.status_code == 404
        assert response.json() == {"message": "patient 999 not found"}

    def test_invalid_id_does_not_crash(self, client: TestClient) -> None:
        response = client.get("/patients/abc")
        assert response.status_code == 400
        assert response.json() == {"message": "Invalid ID format. ID must be a number."}


class TestFilter:
    def test_case_insensitive_and_trimmed_fields(self, client: TestClient) -> None:
        response = client.get("/patients/filter", params={"department": "cArDiOlOgY"})
        assert response.status_code == 200
        assert response.json() == [
            {"id": 1, "name": "Asha Rao", "department": "Cardiology", "doctor": "Dr. House"},
            {"id": 3, "name": "Chitra Nair", "department": "Cardiology", "doctor": "Dr. House"},
        ]

    def test_missing_parameter_is_400(self, client: TestClient) -> None:
        response = client.get("/patients/filter")
        assert response.status_code == 400
        assert response.json() == {"message": "department query parameter is required"}

    def test_blank_parameter_is_400(self, client: TestClient) -> None:
        assert client.get("/patients/filter", params={"department": " "}).status_code == 400

    def test_no_matches_is_empty_list(self, client: TestClient) -> None:
        assert client.get("/patients/filter", params={"department": "oncology"}).json() == []


class TestAnalyticsEndpoints:
    def test_highest_bill(self, client: TestClient) -> None:
        assert client.get("/patients/highest-bill").json() == {
            "id": 3,
            "name": "Chitra Nair",
            "department": "Cardiology",
            "totalBill": 1000,
        }

    def test_longest_stay(self, client: TestClient) -> None:
        assert client.get("/patients/longest-stay").json() == {
            "id": 2,
            "name": "Bala Iyer",
            "department": "neurology",
            "daysAdmitted": 10,
        }

    def test_admission_summary(self, client: TestClient) -> None:
        assert client.get("/patients/admission/summary").json() == {
            "admittedCount": 2,
            "dischargedCount": 2,
            "averageAge": 50.0,
        }

    def test_department_stats(self, client: TestClient) -> None:
        body = client.get("/analytics/departments").json()
        assert body[0]["department"] == "Cardiology"
        assert body[0]["patientCount"] == 2

    def test_empty_dataset_gives_404_not_a_crash(self) -> None:
        empty = TestClient(create_app(repository=InMemoryRepository([])))
        for path in (
            "/patients/highest-bill",
            "/patients/longest-stay",
            "/patients/admission/summary",
        ):
            response = empty.get(path)
            assert response.status_code == 404, path
            assert response.json() == {"message": "no patients available"}


class TestListPatients:
    def test_returns_envelope(self, client: TestClient) -> None:
        body = client.get("/patients").json()
        assert (body["total"], body["limit"], body["offset"]) == (4, 50, 0)
        assert [p["id"] for p in body["items"]] == [1, 2, 3, 4]

    def test_pagination(self, client: TestClient) -> None:
        body = client.get("/patients", params={"limit": 2, "offset": 1}).json()
        assert body["total"] == 4
        assert [p["id"] for p in body["items"]] == [2, 3]

    def test_filters_combine(self, client: TestClient) -> None:
        body = client.get(
            "/patients", params={"department": "cardiology", "status": "discharged"}
        ).json()
        assert [p["id"] for p in body["items"]] == [3]

    def test_name_search(self, client: TestClient) -> None:
        body = client.get("/patients", params={"q": "iyer"}).json()
        assert [p["id"] for p in body["items"]] == [2]

    def test_limit_is_bounded(self, client: TestClient) -> None:
        assert client.get("/patients", params={"limit": 0}).status_code == 422
        assert client.get("/patients", params={"limit": 1000}).status_code == 422
        assert client.get("/patients", params={"offset": -1}).status_code == 422


class TestUpstreamFailures:
    def test_dataset_error_is_502(self) -> None:
        app = TestClient(create_app(repository=_FailingRepo(DatasetError("upstream down"))))
        response = app.get("/patients/1")
        assert response.status_code == 502
        assert response.json() == {"message": "upstream down"}

    def test_auth_error_is_502(self) -> None:
        app = TestClient(create_app(repository=_FailingRepo(AuthenticationError("denied"))))
        assert app.get("/patients").status_code == 502

    def test_missing_credentials_is_503_and_app_still_starts(self) -> None:
        # No repository injected and no credentials configured: the app must still boot and
        # report a clean 503 on data routes, while /health keeps working.
        app = TestClient(create_app(settings=Settings()))
        assert app.get("/health").status_code == 200
        response = app.get("/patients")
        assert response.status_code == 503
        assert "PATIENT_API_STUDENT_ID" in response.json()["message"]


def test_legacy_singular_aliases_still_work(client: TestClient) -> None:
    assert client.get("/patient/longest-stay").json() == client.get("/patients/longest-stay").json()
    assert (
        client.get("/patient/admission/summary").json()
        == client.get("/patients/admission/summary").json()
    )
    hidden = client.get("/openapi.json").json()["paths"]
    assert "/patient/longest-stay" not in hidden


def test_openapi_documents_every_route(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/health",
        "/patients",
        "/patients/filter",
        "/patients/highest-bill",
        "/patients/longest-stay",
        "/patients/admission/summary",
        "/patients/{patient_id}",
        "/analytics/departments",
    } <= set(paths)
