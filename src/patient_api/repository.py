"""Where patients come from: a JSON file, or the remote service with a small TTL cache."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .client import PatientClient, parse_patients
from .config import Settings
from .exceptions import DatasetError
from .models import Patient


class PatientRepository(Protocol):
    """Anything that can list all patients."""

    #: Short label for where the data comes from: ``"file"``, ``"remote"`` or ``"memory"``.
    source: str

    def all(self) -> list[Patient]: ...


class InMemoryRepository:
    """Holds a fixed list of patients. Handy for tests and demos."""

    source = "memory"

    def __init__(self, patients: list[Patient]) -> None:
        self._patients = list(patients)

    def all(self) -> list[Patient]:
        return list(self._patients)


class FileRepository:
    """Reads patients from a JSON file.

    Accepts either a bare list of patients or the upstream envelope
    ``{"data": {"patients": [...]}}``.
    """

    source = "file"

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def all(self) -> list[Patient]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DatasetError(f"cannot read data file {self._path}: {exc}") from exc
        records = raw if isinstance(raw, list) else raw.get("data", {}).get("patients")
        if not isinstance(records, list):
            raise DatasetError(f"{self._path} does not contain a list of patients")
        return parse_patients(records)


class RemoteRepository:
    """Fetches from the upstream service and caches the result for ``cache_ttl`` seconds.

    Thread-safe, and serves stale data if a refresh fails (a cold-starting free-tier
    server should not turn a working API into a 502).
    """

    source = "remote"

    def __init__(
        self,
        client: PatientClient,
        ttl: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._cached: list[Patient] | None = None
        self._fetched_at = 0.0

    def all(self) -> list[Patient]:
        with self._lock:
            fresh = self._cached is not None and (self._clock() - self._fetched_at) < self._ttl
            if fresh:
                return list(self._cached or [])
            try:
                self._cached = self._client.fetch_patients()
                self._fetched_at = self._clock()
            except Exception:
                if self._cached is None:
                    raise
            return list(self._cached or [])


def build_repository(settings: Settings) -> PatientRepository:
    """Pick the repository implied by ``settings`` (file if configured, else remote)."""
    if settings.data_file is not None:
        return FileRepository(settings.data_file)
    return RemoteRepository(PatientClient(settings), ttl=settings.cache_ttl)
