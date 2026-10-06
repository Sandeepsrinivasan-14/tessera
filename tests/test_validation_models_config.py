from __future__ import annotations

from pathlib import Path

import pytest

from tessera.config import DEFAULT_BASE_URL, Settings
from tessera.exceptions import ConfigurationError, ValidationError
from tessera.models import Bill, Patient
from tessera.validation import parse_patient_id, require_department


class TestParsePatientId:
    @pytest.mark.parametrize(("raw", "expected"), [("201", 201), (" 7 ", 7), ("0", 0)])
    def test_accepts_plain_digits(self, raw: str, expected: int) -> None:
        assert parse_patient_id(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["abc", "", "  ", "-5", "+5", "2_01", "1.5", "٣٣", "12a", "0x10"]
    )
    def test_rejects_everything_else(self, raw: str) -> None:
        with pytest.raises(ValidationError, match="Invalid ID format"):
            parse_patient_id(raw)


class TestRequireDepartment:
    def test_returns_value(self) -> None:
        assert require_department("Cardiology") == "Cardiology"

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_missing_or_blank_raises(self, raw: str | None) -> None:
        with pytest.raises(ValidationError, match="department query parameter is required"):
            require_department(raw)


class TestModels:
    def test_bill_total(self) -> None:
        assert Bill(consultation=1, medicine=2, lab=3).total == 6

    def test_none_values_become_defaults(self) -> None:
        p = Patient.model_validate(
            {"id": 1, "name": None, "age": None, "daysAdmitted": None, "bill": None}
        )
        assert (p.name, p.age, p.days_admitted, p.bill.total) == ("", 0, 0, 0)

    def test_accepts_alias_and_field_name(self) -> None:
        assert Patient.model_validate({"id": 1, "daysAdmitted": 4}).days_admitted == 4
        assert Patient.model_validate({"id": 1, "days_admitted": 4}).days_admitted == 4

    def test_serialises_back_to_camel_case(self) -> None:
        dumped = Patient.model_validate({"id": 1, "daysAdmitted": 4}).model_dump(by_alias=True)
        assert dumped["daysAdmitted"] == 4

    def test_unknown_fields_are_ignored(self) -> None:
        assert Patient.model_validate({"id": 1, "mystery": "x"}).id == 1


class TestSettings:
    def test_defaults(self) -> None:
        s = Settings.from_env({})
        assert s.base_url == DEFAULT_BASE_URL
        assert (s.student_id, s.password, s.data_file) == (None, None, None)
        assert s.dataset_set == "setA"

    def test_reads_prefixed_variables_and_trims(self) -> None:
        s = Settings.from_env(
            {
                "PATIENT_API_STUDENT_ID": " e1 ",
                "PATIENT_API_PASSWORD": "pw",
                "PATIENT_API_BASE_URL": "https://example.test/api/",
                "PATIENT_API_TIMEOUT": "5",
                "PATIENT_API_RETRIES": "1",
                "PATIENT_API_CACHE_TTL": "0",
                "PATIENT_API_DATA_FILE": "x.json",
            }
        )
        assert s.student_id == "e1"
        assert s.base_url == "https://example.test/api"  # trailing slash stripped
        assert (s.timeout, s.retries, s.cache_ttl) == (5.0, 1, 0.0)
        assert s.data_file == Path("x.json")

    def test_blank_values_are_treated_as_unset(self) -> None:
        assert Settings.from_env({"PATIENT_API_PASSWORD": "   "}).password is None

    def test_bad_number_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            Settings.from_env({"PATIENT_API_TIMEOUT": "soon"})

    def test_require_credentials_lists_what_is_missing(self) -> None:
        with pytest.raises(ConfigurationError) as info:
            Settings().require_credentials()
        assert "PATIENT_API_STUDENT_ID" in str(info.value)
        assert "PATIENT_API_PASSWORD" in str(info.value)

    def test_require_credentials_passes_when_present(self) -> None:
        Settings(student_id="a", password="b").require_credentials()
