from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests
import responses

from patient_api.client import PatientClient, parse_patients
from patient_api.config import Settings
from patient_api.exceptions import AuthenticationError, ConfigurationError, DatasetError
from patient_api.repository import (
    FileRepository,
    InMemoryRepository,
    RemoteRepository,
    build_repository,
)

BASE = "https://upstream.test/api"
TOKEN_URL = f"{BASE}/public/token"
DATA_URL = f"{BASE}/dataset/abc"


@pytest.fixture
def settings() -> Settings:
    return Settings(base_url=BASE, student_id="E1", password="pw", retries=0, timeout=1)


def _dataset(*ids: int) -> dict:
    return {"data": {"patients": [{"id": i, "name": f"P{i}"} for i in ids]}}


def _mock_happy_path(*ids: int) -> None:
    responses.post(TOKEN_URL, json={"token": "tok123", "dataUrl": "/dataset/abc"}, status=201)
    responses.get(DATA_URL, json=_dataset(*ids))


class TestParsePatients:
    def test_skips_malformed_records_instead_of_failing(self) -> None:
        parsed = parse_patients([{"id": 1}, {"name": "no id"}, "not a dict", {"id": 2}])
        assert [p.id for p in parsed] == [1, 2]


class TestPatientClient:
    def test_requires_credentials(self) -> None:
        with pytest.raises(ConfigurationError):
            PatientClient(Settings(base_url=BASE))

    @responses.activate
    def test_happy_path_returns_patients(self, settings: Settings) -> None:
        _mock_happy_path(1, 2, 3)
        assert [p.id for p in PatientClient(settings).fetch_patients()] == [1, 2, 3]

    @responses.activate
    def test_sends_credentials_and_bearer_token(self, settings: Settings) -> None:
        _mock_happy_path(1)
        PatientClient(settings).fetch_patients()
        token_call, data_call = responses.calls
        assert json.loads(token_call.request.body) == {
            "studentId": "E1",
            "set": "setA",
            "password": "pw",
        }
        assert data_call.request.headers["Authorization"] == "Bearer tok123"

    @responses.activate
    def test_rejected_credentials(self, settings: Settings) -> None:
        responses.post(TOKEN_URL, json={"message": "bad password"}, status=401)
        with pytest.raises(AuthenticationError, match="HTTP 401"):
            PatientClient(settings).fetch_patients()

    @responses.activate
    @pytest.mark.parametrize("body", [{}, {"token": "t"}, {"dataUrl": "/x"}])
    def test_incomplete_token_response(self, settings: Settings, body: dict) -> None:
        responses.post(TOKEN_URL, json=body, status=200)
        with pytest.raises(AuthenticationError, match="missing"):
            PatientClient(settings).fetch_patients()

    @responses.activate
    def test_non_json_token_response(self, settings: Settings) -> None:
        responses.post(TOKEN_URL, body="<html>oops</html>", status=200)
        with pytest.raises(AuthenticationError, match="non-JSON"):
            PatientClient(settings).fetch_patients()

    @responses.activate
    def test_network_failure_on_token(self, settings: Settings) -> None:
        responses.post(TOKEN_URL, body=requests.ConnectionError("down"))
        with pytest.raises(AuthenticationError, match="could not reach"):
            PatientClient(settings).fetch_patients()

    @responses.activate
    def test_network_failure_on_dataset(self, settings: Settings) -> None:
        responses.post(TOKEN_URL, json={"token": "t", "dataUrl": "/dataset/abc"})
        responses.get(DATA_URL, body=requests.Timeout("slow"))
        with pytest.raises(DatasetError, match="could not reach"):
            PatientClient(settings).fetch_patients()

    @responses.activate
    def test_dataset_http_error(self, settings: Settings) -> None:
        responses.post(TOKEN_URL, json={"token": "t", "dataUrl": "/dataset/abc"})
        responses.get(DATA_URL, status=500, body="boom")
        with pytest.raises(DatasetError, match="HTTP 500"):
            PatientClient(settings).fetch_patients()

    @responses.activate
    @pytest.mark.parametrize("body", [{}, {"data": {}}, {"data": {"patients": "nope"}}, []])
    def test_unexpected_dataset_shape(self, settings: Settings, body: object) -> None:
        responses.post(TOKEN_URL, json={"token": "t", "dataUrl": "/dataset/abc"})
        responses.get(DATA_URL, json=body)
        with pytest.raises(DatasetError):
            PatientClient(settings).fetch_patients()


class TestFileRepository:
    def test_reads_upstream_envelope(self, sample_file: Path) -> None:
        patients = FileRepository(sample_file).all()
        assert len(patients) == 40
        assert patients[0].id == 201

    def test_reads_bare_list(self, tmp_path: Path) -> None:
        f = tmp_path / "p.json"
        f.write_text(json.dumps([{"id": 1}, {"id": 2}]))
        assert [p.id for p in FileRepository(f).all()] == [1, 2]

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(DatasetError, match="cannot read"):
            FileRepository(tmp_path / "nope.json").all()

    def test_invalid_json(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("{not json")
        with pytest.raises(DatasetError):
            FileRepository(f).all()

    def test_wrong_shape(self, tmp_path: Path) -> None:
        f = tmp_path / "shape.json"
        f.write_text(json.dumps({"hello": "world"}))
        with pytest.raises(DatasetError, match="list of patients"):
            FileRepository(f).all()


class _FakeClient:
    """Stands in for PatientClient; counts fetches and can be told to fail."""

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def fetch_patients(self):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.fail:
            raise DatasetError("upstream down")
        return parse_patients([{"id": self.calls}])


class TestRemoteRepository:
    def _repo(self, ttl: float = 60):  # type: ignore[no-untyped-def]
        now = [0.0]
        client = _FakeClient()
        repo = RemoteRepository(client, ttl=ttl, clock=lambda: now[0])  # type: ignore[arg-type]
        return repo, client, now

    def test_caches_within_ttl(self) -> None:
        repo, client, now = self._repo()
        repo.all()
        now[0] = 59
        repo.all()
        assert client.calls == 1

    def test_refreshes_after_ttl(self) -> None:
        repo, client, now = self._repo()
        repo.all()
        now[0] = 61
        assert repo.all()[0].id == 2
        assert client.calls == 2

    def test_serves_stale_data_when_refresh_fails(self) -> None:
        repo, client, now = self._repo()
        repo.all()
        client.fail = True
        now[0] = 100
        assert [p.id for p in repo.all()] == [1]

    def test_first_fetch_failure_propagates(self) -> None:
        repo, client, _ = self._repo()
        client.fail = True
        with pytest.raises(DatasetError):
            repo.all()

    def test_returned_list_is_a_copy(self) -> None:
        repo, _, _ = self._repo()
        repo.all().clear()
        assert len(repo.all()) == 1


class TestBuildRepository:
    def test_data_file_wins(self, sample_file: Path) -> None:
        assert isinstance(build_repository(Settings(data_file=sample_file)), FileRepository)

    def test_remote_when_credentials_present(self) -> None:
        repo = build_repository(Settings(student_id="a", password="b"))
        assert isinstance(repo, RemoteRepository)

    def test_remote_without_credentials_is_a_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            build_repository(Settings())


def test_in_memory_repository_isolates_callers() -> None:
    repo = InMemoryRepository(parse_patients([{"id": 1}]))
    repo.all().clear()
    assert len(repo.all()) == 1
