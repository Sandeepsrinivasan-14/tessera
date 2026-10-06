"""Pure analytics over lists of :class:`~tessera.models.Patient`.

Every function here is side-effect free: it never mutates its input and never touches the
network, which keeps the business rules trivially unit-testable.

A note on ``reduce``: the original coursework brief required ``functools.reduce`` for the
admission summary and the longest-stay lookup, so those two use it deliberately.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from functools import reduce
from typing import Any, Literal

from .exceptions import EmptyDatasetError, PatientNotFoundError
from .models import (
    AdmissionSummary,
    DepartmentStats,
    HighestBill,
    LongestStay,
    Patient,
    PatientSummary,
)

SortField = Literal["id", "name", "department", "age", "daysAdmitted", "totalBill"]

_SORT_KEYS: dict[str, Callable[[Patient], Any]] = {
    "id": lambda p: p.id,
    "name": lambda p: p.name.lower(),
    "department": lambda p: p.department.lower(),
    "age": lambda p: p.age,
    "daysAdmitted": lambda p: p.days_admitted,
    "totalBill": lambda p: p.bill.total,
}


def sort_patients(
    patients: Sequence[Patient], field: SortField = "id", descending: bool = False
) -> list[Patient]:
    """Return a new list sorted by ``field``. The sort is stable, so ties keep dataset order."""
    return sorted(patients, key=_SORT_KEYS[field], reverse=descending)


def find_patient(patients: Sequence[Patient], patient_id: int) -> Patient:
    """Return the patient with ``patient_id`` or raise :class:`PatientNotFoundError`."""
    for patient in patients:
        if patient.id == patient_id:
            return patient
    raise PatientNotFoundError(patient_id)


def filter_by_department(patients: Sequence[Patient], department: str) -> list[PatientSummary]:
    """Patients in ``department``, compared case-insensitively and ignoring padding."""
    target = department.strip().lower()
    return [
        PatientSummary(id=p.id, name=p.name, department=p.department, doctor=p.doctor)
        for p in patients
        if p.department.strip().lower() == target
    ]


def highest_bill(patients: Sequence[Patient]) -> HighestBill:
    """The patient with the largest total bill (consultation + medicine + lab).

    On a tie the patient appearing first in the dataset wins, because Python's sort is
    stable even with ``reverse=True``.
    """
    if not patients:
        raise EmptyDatasetError("no patients available")
    ranked = sorted(patients, key=lambda p: p.bill.total, reverse=True)
    top = ranked[0]
    return HighestBill(
        id=top.id, name=top.name, department=top.department, totalBill=top.bill.total
    )


def longest_stay(patients: Sequence[Patient]) -> LongestStay:
    """The patient admitted for the most days. On a tie the *later* record wins."""
    if not patients:
        raise EmptyDatasetError("no patients available")
    top = reduce(lambda a, b: a if a.days_admitted > b.days_admitted else b, patients)
    return LongestStay(
        id=top.id, name=top.name, department=top.department, daysAdmitted=top.days_admitted
    )


def admission_summary(patients: Sequence[Patient]) -> AdmissionSummary:
    """Admitted / discharged counts and the mean age (rounded to 2 dp)."""
    if not patients:
        raise EmptyDatasetError("no patients available")
    admitted = reduce(lambda n, p: n + (p.status == "Admitted"), patients, 0)
    discharged = reduce(lambda n, p: n + (p.status == "Discharged"), patients, 0)
    total_age = reduce(lambda total, p: total + p.age, patients, 0)
    return AdmissionSummary(
        admittedCount=admitted,
        dischargedCount=discharged,
        averageAge=round(total_age / len(patients), 2),
    )


def department_stats(patients: Sequence[Patient]) -> list[DepartmentStats]:
    """Roll patients up by department, busiest department first."""
    groups: dict[str, list[Patient]] = defaultdict(list)
    for patient in patients:
        groups[patient.department.strip() or "Unassigned"].append(patient)

    stats = []
    for name, group in groups.items():
        count = len(group)
        revenue = sum(p.bill.total for p in group)
        stats.append(
            DepartmentStats(
                department=name,
                patientCount=count,
                admittedCount=sum(p.status == "Admitted" for p in group),
                averageAge=round(sum(p.age for p in group) / count, 2),
                averageStayDays=round(sum(p.days_admitted for p in group) / count, 2),
                totalRevenue=round(revenue, 2),
                averageBill=round(revenue / count, 2),
            )
        )
    stats.sort(key=lambda s: (-s.patientCount, s.department))
    return stats
