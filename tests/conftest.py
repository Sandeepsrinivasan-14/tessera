from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from patient_api.api import create_app
from patient_api.models import Patient
from patient_api.repository import InMemoryRepository

SAMPLE_FILE = Path(__file__).resolve().parents[1] / "data" / "sample_patients.json"


def make_patient(
    pid: int,
    *,
    name: str = "Test Patient",
    department: str = "Cardiology",
    doctor: str = "Dr. House",
    status: str = "Admitted",
    age: int = 40,
    days: int = 3,
    consultation: float = 100,
    medicine: float = 100,
    lab: float = 100,
) -> Patient:
    return Patient.model_validate(
        {
            "id": pid,
            "name": name,
            "department": department,
            "doctor": doctor,
            "status": status,
            "age": age,
            "daysAdmitted": days,
            "bill": {"consultation": consultation, "medicine": medicine, "lab": lab},
        }
    )


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test from an empty directory so a developer's real ``.env`` is never read."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def patients() -> list[Patient]:
    """A small, hand-checkable dataset.

    * Highest bill: id 3 (1000 total) -- unique.
    * Longest stay: id 2 (10 days) -- unique.
    * Admitted: 1, 2 (2 total); Discharged: 3, 4 (2 total); ages sum to 40+60+20+80 = 200.
    """
    return [
        make_patient(1, name="Asha Rao", department="Cardiology", age=40, days=3),
        make_patient(
            2,
            name="Bala Iyer",
            department="neurology",
            age=60,
            days=10,
            consultation=200,
            medicine=200,
            lab=200,
        ),
        make_patient(
            3,
            name="Chitra Nair",
            department="Cardiology",
            status="Discharged",
            age=20,
            days=5,
            consultation=300,
            medicine=400,
            lab=300,
        ),
        make_patient(
            4,
            name="Dev Shah",
            department="Pediatrics",
            status="Discharged",
            age=80,
            days=1,
            consultation=50,
            medicine=50,
            lab=50,
        ),
    ]


@pytest.fixture
def client(patients: list[Patient]) -> TestClient:
    return TestClient(create_app(repository=InMemoryRepository(patients)))


@pytest.fixture
def sample_file() -> Path:
    return SAMPLE_FILE
