from __future__ import annotations

import pytest

from tessera import analytics
from tessera.exceptions import EmptyDatasetError, PatientNotFoundError
from tessera.models import Patient

from .conftest import make_patient


class TestFindPatient:
    def test_returns_match(self, patients: list[Patient]) -> None:
        assert analytics.find_patient(patients, 3).name == "Chitra Nair"

    def test_missing_raises(self, patients: list[Patient]) -> None:
        with pytest.raises(PatientNotFoundError) as info:
            analytics.find_patient(patients, 999)
        assert info.value.patient_id == 999


class TestFilterByDepartment:
    def test_case_insensitive(self, patients: list[Patient]) -> None:
        result = analytics.filter_by_department(patients, "CARDIOLOGY")
        assert [p.id for p in result] == [1, 3]

    def test_ignores_surrounding_whitespace_on_both_sides(self, patients: list[Patient]) -> None:
        assert [p.id for p in analytics.filter_by_department(patients, "  Neurology ")] == [2]

    def test_returns_only_the_public_fields(self, patients: list[Patient]) -> None:
        result = analytics.filter_by_department(patients, "pediatrics")
        assert result[0].model_dump() == {
            "id": 4,
            "name": "Dev Shah",
            "department": "Pediatrics",
            "doctor": "Dr. House",
        }

    def test_no_match_is_empty_list(self, patients: list[Patient]) -> None:
        assert analytics.filter_by_department(patients, "oncology") == []


class TestHighestBill:
    def test_picks_largest_total(self, patients: list[Patient]) -> None:
        result = analytics.highest_bill(patients)
        assert (result.id, result.totalBill) == (3, 1000)

    def test_tie_prefers_first_in_dataset(self) -> None:
        tied = [make_patient(1), make_patient(2), make_patient(3, lab=1)]
        assert analytics.highest_bill(tied).id == 1

    def test_missing_bill_components_count_as_zero(self) -> None:
        sparse = Patient.model_validate({"id": 1, "bill": {"consultation": 50}})
        assert analytics.highest_bill([sparse]).totalBill == 50

    def test_does_not_mutate_input(self, patients: list[Patient]) -> None:
        before = [p.id for p in patients]
        analytics.highest_bill(patients)
        assert [p.id for p in patients] == before

    def test_empty_raises(self) -> None:
        with pytest.raises(EmptyDatasetError):
            analytics.highest_bill([])


class TestLongestStay:
    def test_picks_most_days(self, patients: list[Patient]) -> None:
        result = analytics.longest_stay(patients)
        assert (result.id, result.daysAdmitted) == (2, 10)

    def test_tie_prefers_later_record(self) -> None:
        tied = [make_patient(1, days=7), make_patient(2, days=7)]
        assert analytics.longest_stay(tied).id == 2

    def test_single_patient(self) -> None:
        assert analytics.longest_stay([make_patient(9, days=0)]).id == 9

    def test_empty_raises(self) -> None:
        with pytest.raises(EmptyDatasetError):
            analytics.longest_stay([])


class TestAdmissionSummary:
    def test_counts_and_average(self, patients: list[Patient]) -> None:
        result = analytics.admission_summary(patients)
        assert (result.admittedCount, result.dischargedCount, result.averageAge) == (2, 2, 50.0)

    def test_average_rounded_to_two_places(self) -> None:
        group = [make_patient(1, age=10), make_patient(2, age=10), make_patient(3, age=11)]
        assert analytics.admission_summary(group).averageAge == 10.33

    def test_unknown_status_is_counted_in_neither_bucket(self) -> None:
        result = analytics.admission_summary([make_patient(1, status="Transferred")])
        assert (result.admittedCount, result.dischargedCount) == (0, 0)

    def test_empty_raises(self) -> None:
        with pytest.raises(EmptyDatasetError):
            analytics.admission_summary([])


class TestDepartmentStats:
    def test_rollup_values(self, patients: list[Patient]) -> None:
        stats = {s.department: s for s in analytics.department_stats(patients)}
        cardio = stats["Cardiology"]
        assert cardio.patientCount == 2
        assert cardio.admittedCount == 1
        assert cardio.averageAge == 30.0
        assert cardio.averageStayDays == 4.0
        assert cardio.totalRevenue == 1300
        assert cardio.averageBill == 650.0

    def test_sorted_by_volume_then_name(self, patients: list[Patient]) -> None:
        order = [s.department for s in analytics.department_stats(patients)]
        assert order == ["Cardiology", "Pediatrics", "neurology"]

    def test_blank_department_grouped_as_unassigned(self) -> None:
        stats = analytics.department_stats([make_patient(1, department="  ")])
        assert stats[0].department == "Unassigned"

    def test_empty_input_gives_empty_list(self) -> None:
        assert analytics.department_stats([]) == []
