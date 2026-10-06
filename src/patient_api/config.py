"""Runtime configuration, read from environment variables.

Credentials are **never** stored in source. Copy ``.env.example`` to ``.env`` (which is
git-ignored) or export the variables in your shell.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .exceptions import ConfigurationError

DEFAULT_BASE_URL = "https://t4e-testserver.onrender.com/api"
DEFAULT_SAMPLE_FILE = Path(__file__).resolve().parents[2] / "data" / "sample_patients.json"


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    base_url: str = DEFAULT_BASE_URL
    student_id: str | None = None
    dataset_set: str = "setA"
    password: str | None = None
    #: Seconds to wait on the upstream server. Render free-tier instances can take a
    #: while to wake from sleep, so the default is deliberately generous.
    timeout: float = 45.0
    retries: int = 3
    #: How long a fetched dataset is reused before it is refreshed.
    cache_ttl: float = 60.0
    #: When set, patients are read from this JSON file and no network call is made.
    data_file: Path | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        """Build settings from ``PATIENT_API_*`` environment variables."""
        source = os.environ if env is None else env

        def get(name: str) -> str | None:
            value = source.get(f"PATIENT_API_{name}")
            return value.strip() if value and value.strip() else None

        data_file = get("DATA_FILE")
        try:
            return cls(
                base_url=(get("BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
                student_id=get("STUDENT_ID"),
                dataset_set=get("SET") or "setA",
                password=get("PASSWORD"),
                timeout=float(get("TIMEOUT") or 45.0),
                retries=int(get("RETRIES") or 3),
                cache_ttl=float(get("CACHE_TTL") or 60.0),
                data_file=Path(data_file) if data_file else None,
            )
        except ValueError as exc:
            raise ConfigurationError(f"invalid numeric PATIENT_API_* value: {exc}") from exc

    def require_credentials(self) -> None:
        """Raise :class:`ConfigurationError` unless remote credentials are present."""
        missing = [
            name
            for name, value in (
                ("PATIENT_API_STUDENT_ID", self.student_id),
                ("PATIENT_API_PASSWORD", self.password),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "missing environment variable(s): "
                + ", ".join(missing)
                + ". Set them, or set PATIENT_API_DATA_FILE to run offline."
            )
