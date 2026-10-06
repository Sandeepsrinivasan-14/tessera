"""Command-line interface: ``patientctl``.

Examples::

    patientctl --data-file data/sample_patients.json summary
    patientctl departments --format table
    patientctl get 201
    patientctl serve --port 8000
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__, analytics
from .config import DEFAULT_DOTENV, Settings
from .exceptions import ConfigurationError, PatientAPIError
from .repository import PatientRepository, build_repository
from .validation import parse_patient_id, require_department


def _add_common_options(parser: argparse.ArgumentParser, *, is_root: bool) -> None:
    """Options accepted both before and after the subcommand.

    Subparsers use ``SUPPRESS`` defaults so an option given only at the root level is not
    overwritten by the subparser's own default.
    """
    unset = None if is_root else argparse.SUPPRESS
    parser.add_argument(
        "--data-file",
        type=Path,
        default=unset,
        help="read patients from this JSON file instead of the remote service",
    )
    parser.add_argument(
        "--format",
        choices=("json", "table"),
        default="json" if is_root else argparse.SUPPRESS,
        help="output format (table applies to list-style results)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False if is_root else argparse.SUPPRESS,
        help="enable debug logging",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patientctl",
        description="Query hospital patient data from the command line.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    _add_common_options(parser, is_root=True)

    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        _add_common_options(sp, is_root=False)
        return sp

    command("summary", "admitted/discharged counts and mean age")
    command("highest-bill", "patient with the highest total bill")
    command("longest-stay", "patient admitted the longest")
    command("departments", "per-department statistics")
    command("doctor", "check configuration (never prints secrets)")
    command("get", "fetch one patient by id").add_argument("patient_id", help="numeric patient id")
    command("filter", "list patients in a department").add_argument(
        "department", help="department name (case-insensitive)"
    )
    serve = command("serve", "run the HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    return parser


def _render_table(rows: Sequence[dict[str, Any]]) -> str:
    """Render dicts as an aligned plain-text table."""
    if not rows:
        return "(no results)"
    headers = list(rows[0])
    cells = [[str(row.get(h, "")) for h in headers] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) for i, h in enumerate(headers)]
    line = "  ".join("-" * w for w in widths)
    out = ["  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)), line]
    out += ["  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)) for r in cells]
    return "\n".join(out)


def _emit(result: Any, fmt: str) -> None:
    """Print a pydantic model / list of models as JSON or a table."""
    if isinstance(result, list):
        rows = [item.model_dump(by_alias=True) for item in result]
        print(_render_table(rows) if fmt == "table" else json.dumps(rows, indent=2))
    else:
        print(json.dumps(result.model_dump(by_alias=True), indent=2))


def _run_query(args: argparse.Namespace, repo: PatientRepository) -> None:
    patients = repo.all()
    command = args.command
    if command == "summary":
        _emit(analytics.admission_summary(patients), args.format)
    elif command == "highest-bill":
        _emit(analytics.highest_bill(patients), args.format)
    elif command == "longest-stay":
        _emit(analytics.longest_stay(patients), args.format)
    elif command == "departments":
        _emit(analytics.department_stats(patients), args.format)
    elif command == "get":
        _emit(analytics.find_patient(patients, parse_patient_id(args.patient_id)), args.format)
    elif command == "filter":
        _emit(
            analytics.filter_by_department(patients, require_department(args.department)),
            args.format,
        )


def _doctor(settings: Settings) -> int:
    """Report how the app is configured. Secrets are reported as set/missing, never shown."""

    def status(present: bool) -> str:
        return "set" if present else "missing"

    rows = [("mode", settings.mode)]
    if settings.data_file is not None:
        exists = settings.data_file.is_file()
        rows.append(("data file", f"{settings.data_file} ({'found' if exists else 'NOT FOUND'})"))
        ok = exists
    else:
        rows += [
            ("base url", settings.base_url),
            ("dataset set", settings.dataset_set),
            ("student id", status(bool(settings.student_id))),
            ("password", status(bool(settings.password))),
        ]
        ok = settings.has_credentials
    rows.append((".env file", "found" if DEFAULT_DOTENV.is_file() else "not found"))

    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        print(f"{label.ljust(width)}  {value}")
    if ok:
        print("\nConfiguration looks good.")
        return 0
    if settings.data_file is not None:
        print("\nThe data file does not exist. Check PATIENT_API_DATA_FILE.", file=sys.stderr)
    else:
        print(
            "\nAdd PATIENT_API_STUDENT_ID and PATIENT_API_PASSWORD to .env "
            "(copy .env.example), or set PATIENT_API_DATA_FILE to run offline.",
            file=sys.stderr,
        )
    return 2


def _serve(args: argparse.Namespace, settings: Settings) -> None:
    import uvicorn  # imported lazily: only the server needs it

    if args.reload:
        uvicorn.run(
            "patient_api.api:create_app", factory=True, host=args.host, port=args.port, reload=True
        )
        return
    from .api import create_app

    uvicorn.run(create_app(settings=settings), host=args.host, port=args.port)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Queries stay quiet by default; the long-running server logs each request at INFO.
    default_level = logging.INFO if args.command == "serve" else logging.WARNING
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else default_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = Settings.from_env()
        if args.data_file is not None:
            settings = Settings(**{**settings.__dict__, "data_file": args.data_file})
        if args.command == "doctor":
            return _doctor(settings)
        if args.command == "serve":
            _serve(args, settings)
            return 0
        _run_query(args, build_repository(settings))
        return 0
    except ConfigurationError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    except PatientAPIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
