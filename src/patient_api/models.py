"""Typed data models for patients and API responses."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Bill(BaseModel):
    """Itemised hospital bill. Missing components count as zero."""

    model_config = ConfigDict(extra="ignore")

    consultation: float = 0
    medicine: float = 0
    lab: float = 0

    @field_validator("consultation", "medicine", "lab", mode="before")
    @classmethod
    def _none_is_zero(cls, value: object) -> object:
        return 0 if value is None else value

    @property
    def total(self) -> float:
        return self.consultation + self.medicine + self.lab


class Patient(BaseModel):
    """A single patient record as returned by the upstream dataset."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    name: str = ""
    department: str = ""
    doctor: str = ""
    status: str = ""
    age: int = 0
    days_admitted: int = Field(default=0, alias="daysAdmitted")
    bill: Bill = Field(default_factory=Bill)

    @field_validator("name", "department", "doctor", "status", mode="before")
    @classmethod
    def _none_is_empty(cls, value: object) -> object:
        return "" if value is None else value

    @field_validator("age", "days_admitted", mode="before")
    @classmethod
    def _none_is_zero(cls, value: object) -> object:
        return 0 if value is None else value

    @field_validator("bill", mode="before")
    @classmethod
    def _none_is_empty_bill(cls, value: object) -> object:
        return {} if value is None else value


class PatientSummary(BaseModel):
    """Compact patient view used by the filter endpoint."""

    id: int
    name: str
    department: str
    doctor: str


class HighestBill(BaseModel):
    id: int
    name: str
    department: str
    totalBill: float  # noqa: N815 - public JSON contract uses camelCase


class LongestStay(BaseModel):
    id: int
    name: str
    department: str
    daysAdmitted: int  # noqa: N815 - public JSON contract uses camelCase


class AdmissionSummary(BaseModel):
    admittedCount: int  # noqa: N815
    dischargedCount: int  # noqa: N815
    averageAge: float  # noqa: N815


class DepartmentStats(BaseModel):
    """Per-department rollup."""

    department: str
    patientCount: int  # noqa: N815
    admittedCount: int  # noqa: N815
    averageAge: float  # noqa: N815
    averageStayDays: float  # noqa: N815
    totalRevenue: float  # noqa: N815
    averageBill: float  # noqa: N815


class Page(BaseModel):
    """Paginated list envelope."""

    total: int
    limit: int
    offset: int
    items: list[Patient]


class ErrorResponse(BaseModel):
    message: str
