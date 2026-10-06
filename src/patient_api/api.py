"""FastAPI application exposing the patient analytics endpoints."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

from . import __version__, analytics
from .config import Settings
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    DatasetError,
    EmptyDatasetError,
    PatientAPIError,
    PatientNotFoundError,
    ValidationError,
)
from .models import (
    AdmissionSummary,
    DepartmentStats,
    ErrorResponse,
    HighestBill,
    LongestStay,
    Page,
    Patient,
    PatientSummary,
)
from .repository import PatientRepository, build_repository
from .validation import parse_patient_id, require_department

logger = logging.getLogger("patient_api.http")

#: Exception type -> HTTP status. First ``isinstance`` match wins.
_STATUS_FOR: tuple[tuple[type[PatientAPIError], int], ...] = (
    (ValidationError, 400),
    (PatientNotFoundError, 404),
    (EmptyDatasetError, 404),
    (ConfigurationError, 503),
    (AuthenticationError, 502),
    (DatasetError, 502),
)

_ERRORS = {
    400: {"model": ErrorResponse, "description": "Invalid input"},
    404: {"model": ErrorResponse, "description": "Not found / no data"},
    502: {"model": ErrorResponse, "description": "Upstream dataset unavailable"},
}


def create_app(
    repository: PatientRepository | None = None, settings: Settings | None = None
) -> FastAPI:
    """Application factory.

    Pass a ``repository`` to inject data directly (tests do this); otherwise one is built
    from ``settings`` / the environment.
    """
    app = FastAPI(
        title="Patient Records API",
        version=__version__,
        description=(
            "Token-authenticated hospital patient data, exposed with search, "
            "admission analytics and billing insights."
        ),
    )
    resolved = settings or Settings.from_env()
    app.state.repository = repository
    app.state.settings = resolved

    def get_repository(request: Request) -> PatientRepository:
        # Built lazily so importing the app never needs credentials or the network.
        if request.app.state.repository is None:
            request.app.state.repository = build_repository(request.app.state.settings)
        repo: PatientRepository = request.app.state.repository
        return repo

    Repo = Depends(get_repository)  # noqa: N806

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.2f}"
        logger.info(
            "%s %s -> %d (%.1f ms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

    @app.exception_handler(PatientAPIError)
    async def handle_domain_error(_: Request, exc: PatientAPIError) -> JSONResponse:
        status = next((code for kind, code in _STATUS_FOR if isinstance(exc, kind)), 500)
        if status >= 500:
            logger.error("upstream/config failure: %s", exc)
        return JSONResponse(status_code=status, content={"message": str(exc)})

    # ------------------------------------------------------------------ meta

    @app.get("/health", tags=["meta"], summary="Liveness probe")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    # -------------------------------------------------------------- patients
    # NOTE: fixed-path routes must be declared before "/patients/{patient_id}".

    @app.get("/patients", response_model=Page, tags=["patients"], summary="List patients")
    def list_patients(
        repo: PatientRepository = Repo,
        department: str | None = Query(None, description="Case-insensitive department filter"),
        status: str | None = Query(None, description="Admitted or Discharged"),
        q: str | None = Query(None, description="Case-insensitive name substring"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Page:
        patients = repo.all()
        if department:
            wanted = department.strip().lower()
            patients = [p for p in patients if p.department.strip().lower() == wanted]
        if status:
            wanted = status.strip().lower()
            patients = [p for p in patients if p.status.strip().lower() == wanted]
        if q:
            needle = q.strip().lower()
            patients = [p for p in patients if needle in p.name.lower()]
        return Page(
            total=len(patients),
            limit=limit,
            offset=offset,
            items=patients[offset : offset + limit],
        )

    @app.get(
        "/patients/filter",
        response_model=list[PatientSummary],
        responses={400: _ERRORS[400]},
        tags=["patients"],
        summary="Patients in one department",
    )
    def filter_patients(
        department: str | None = Query(None), repo: PatientRepository = Repo
    ) -> list[PatientSummary]:
        return analytics.filter_by_department(repo.all(), require_department(department))

    @app.get(
        "/patients/highest-bill",
        response_model=HighestBill,
        responses={404: _ERRORS[404]},
        tags=["analytics"],
        summary="Patient with the highest total bill",
    )
    def highest_bill(repo: PatientRepository = Repo) -> HighestBill:
        return analytics.highest_bill(repo.all())

    @app.get(
        "/patients/longest-stay",
        response_model=LongestStay,
        responses={404: _ERRORS[404]},
        tags=["analytics"],
        summary="Patient admitted the longest",
    )
    def longest_stay(repo: PatientRepository = Repo) -> LongestStay:
        return analytics.longest_stay(repo.all())

    @app.get(
        "/patients/admission/summary",
        response_model=AdmissionSummary,
        responses={404: _ERRORS[404]},
        tags=["analytics"],
        summary="Admitted / discharged counts and mean age",
    )
    def admission_summary(repo: PatientRepository = Repo) -> AdmissionSummary:
        return analytics.admission_summary(repo.all())

    @app.get(
        "/analytics/departments",
        response_model=list[DepartmentStats],
        tags=["analytics"],
        summary="Per-department volume, stay length and revenue",
    )
    def departments(repo: PatientRepository = Repo) -> list[DepartmentStats]:
        return analytics.department_stats(repo.all())

    @app.get(
        "/patients/{patient_id}",
        response_model=Patient,
        responses={400: _ERRORS[400], 404: _ERRORS[404]},
        tags=["patients"],
        summary="Get one patient by id",
    )
    def get_patient(patient_id: str, repo: PatientRepository = Repo) -> Patient:
        return analytics.find_patient(repo.all(), parse_patient_id(patient_id))

    # Backward-compatible aliases: the original coursework brief named these two routes in
    # the singular. Kept working but hidden from the OpenAPI docs.
    app.add_api_route(
        "/patient/longest-stay",
        longest_stay,
        methods=["GET"],
        response_model=LongestStay,
        include_in_schema=False,
    )
    app.add_api_route(
        "/patient/admission/summary",
        admission_summary,
        methods=["GET"],
        response_model=AdmissionSummary,
        include_in_schema=False,
    )

    return app
