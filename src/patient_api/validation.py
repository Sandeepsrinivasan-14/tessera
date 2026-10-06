"""Input validation helpers shared by the HTTP layer and the CLI."""

from __future__ import annotations

from .exceptions import ValidationError


def parse_patient_id(raw: str) -> int:
    """Convert user input to a patient id, or raise :class:`ValidationError`.

    Deliberately stricter than ``int()``: it rejects signs, underscores
    (``"2_01"``), and non-ASCII digits, all of which ``int()`` would happily accept.
    """
    candidate = (raw or "").strip()
    if not (candidate.isascii() and candidate.isdigit()):
        raise ValidationError("Invalid ID format. ID must be a number.")
    return int(candidate)


def require_department(raw: str | None) -> str:
    """Return a usable department name or raise :class:`ValidationError`."""
    if raw is None or not raw.strip():
        raise ValidationError("department query parameter is required")
    return raw
