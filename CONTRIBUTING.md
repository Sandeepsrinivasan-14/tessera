# Contributing

Thanks for taking a look at Tessera! This is a small project, so the process is light.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
make install          # editable install with dev tools
make check            # ruff + mypy --strict + pytest, the same as CI
```

## Ground rules

- **Business logic goes in `analytics.py`** as a pure function (no I/O, no mutation of inputs).
  The API and CLI should only wire things together.
- **Every behaviour change needs a test.** Tie-breaking, edge cases and error paths are all
  pinned by tests today; keep it that way.
- **Keep the JSON contract stable.** Response fields are camelCase (`totalBill`, `daysAdmitted`).
- **Never commit credentials or real patient data.** Use `.env` (git-ignored) and the synthetic
  dataset in `data/`.
- Code style is enforced by `ruff`; types by `mypy --strict`. Run `make format` to auto-fix.

## Working on the dashboard

The UI is plain files in `src/tessera/static/`; there is nothing to build. Run `make serve` and
open <http://127.0.0.1:8000/>. Keep to the rules the tests enforce: no inline scripts or styles, no
third-party requests, and never `innerHTML` (use `textContent`). Check light and dark themes, keyboard
use, and a narrow (phone-width) window before opening a PR.

## Adding an endpoint

1. Add a pure function and response model (`analytics.py`, `models.py`) with unit tests.
2. Expose it in `api.py` (declare fixed paths *before* `/patients/{patient_id}`) and, if useful,
   as a `tessera` subcommand in `cli.py`.
3. Add API tests in `tests/test_api.py` covering success and error cases.
4. Update the endpoint table in `README.md` and add a line to `CHANGELOG.md`.

## Pull requests

Branch from `main`, keep PRs focused, and fill in the PR template checklist.
