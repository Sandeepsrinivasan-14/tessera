"""HTTP client for the upstream (token-protected) patient dataset service."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import requests
from pydantic import ValidationError as PydanticValidationError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Settings
from .exceptions import AuthenticationError, DatasetError
from .models import Patient

logger = logging.getLogger(__name__)


def parse_patients(raw_records: Iterable[Any]) -> list[Patient]:
    """Validate raw dicts into :class:`Patient` objects.

    One malformed record should not take the whole dataset down, so invalid rows are
    logged and skipped rather than raising.
    """
    patients: list[Patient] = []
    for index, record in enumerate(raw_records):
        try:
            patients.append(Patient.model_validate(record))
        except PydanticValidationError as exc:
            logger.warning("skipping malformed patient record #%d: %s", index, exc.errors()[:1])
    return patients


def _build_session(retries: int) -> requests.Session:
    """A session that retries transient gateway errors with exponential backoff."""
    retry = Retry(
        total=retries,
        backoff_factor=1.0,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),  # the token POST is idempotent
        respect_retry_after_header=True,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class PatientClient:
    """Authenticates against the upstream service and downloads the patient dataset."""

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        settings.require_credentials()
        self._settings = settings
        self._session = session or _build_session(settings.retries)

    @property
    def token_url(self) -> str:
        return f"{self._settings.base_url}/public/token"

    def authenticate(self) -> tuple[str, str]:
        """Exchange credentials for ``(bearer_token, absolute_data_url)``."""
        payload = {
            "studentId": self._settings.student_id,
            "set": self._settings.dataset_set,
            "password": self._settings.password,
        }
        try:
            response = self._session.post(
                self.token_url, json=payload, timeout=self._settings.timeout
            )
        except requests.RequestException as exc:
            raise AuthenticationError(f"could not reach token endpoint: {exc}") from exc

        if response.status_code not in (200, 201):
            raise AuthenticationError(
                f"token request failed with HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise AuthenticationError("token endpoint returned non-JSON content") from exc

        token = body.get("token")
        data_path = body.get("dataUrl")
        if not token or not data_path:
            raise AuthenticationError("token response is missing 'token' or 'dataUrl'")
        return token, f"{self._settings.base_url}{data_path}"

    def fetch_patients(self) -> list[Patient]:
        """Authenticate, download the dataset and return validated patients."""
        token, data_url = self.authenticate()
        logger.info("fetching dataset from %s", data_url)
        try:
            response = self._session.get(
                data_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self._settings.timeout,
            )
        except requests.RequestException as exc:
            raise DatasetError(f"could not reach dataset endpoint: {exc}") from exc

        if response.status_code != 200:
            raise DatasetError(
                f"dataset request failed with HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            records = response.json()["data"]["patients"]
        except (ValueError, KeyError, TypeError) as exc:
            raise DatasetError("dataset response is missing data.patients") from exc
        if not isinstance(records, list):
            raise DatasetError("data.patients is not a list")
        return parse_patients(records)
