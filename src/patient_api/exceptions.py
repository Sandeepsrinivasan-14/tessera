"""Exception hierarchy for the patient_api package.

Every error the library raises on purpose derives from :class:`PatientAPIError`,
so callers can catch one type at the boundary (the HTTP layer and the CLI both do).
"""

from __future__ import annotations


class PatientAPIError(Exception):
    """Base class for all errors raised deliberately by this package."""


class ConfigurationError(PatientAPIError):
    """Required configuration (for example credentials) is missing or invalid."""


class AuthenticationError(PatientAPIError):
    """The upstream server rejected the credentials or returned no token."""


class DatasetError(PatientAPIError):
    """The dataset could not be fetched or did not have the expected shape."""


class ValidationError(PatientAPIError):
    """A caller-supplied value (such as a patient id) is malformed."""


class PatientNotFoundError(PatientAPIError):
    """No patient exists with the requested id."""

    def __init__(self, patient_id: int) -> None:
        super().__init__(f"patient {patient_id} not found")
        self.patient_id = patient_id


class EmptyDatasetError(PatientAPIError):
    """An aggregate was requested but there are no patients to aggregate."""
