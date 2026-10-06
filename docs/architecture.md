# Architecture

## Layers

| Layer | Module(s) | Responsibility | Knows about |
| --- | --- | --- | --- |
| Interface | `api.py`, `cli.py`, `static/` | Parse requests/arguments, map errors to status codes / exit codes, render the dashboard | everything below |
| Core | `analytics.py`, `validation.py`, `models.py` | Business rules, input rules, data shapes | only itself |
| Data access | `repository.py`, `client.py` | Where patients come from; auth, retries, caching | `config.py` |
| Cross-cutting | `config.py`, `exceptions.py` | Settings, error taxonomy | nothing |

The dependency direction is strictly downward. The core never imports the data layer, so the
analytics can be tested with plain Python lists.

## Request flow (`GET /patients/highest-bill`)

1. Middleware stamps `X-Request-ID` and starts a timer.
2. The route resolves a `PatientRepository` (built lazily on first use, so importing the app never
   needs credentials or network).
3. `RemoteRepository.all()` returns cached patients if younger than the TTL; otherwise
   `PatientClient` authenticates, downloads, and validates the dataset.
4. `analytics.highest_bill()` computes the result with no side effects.
5. Pydantic serialises the response using the camelCase aliases.
6. Middleware logs method, path, status and latency.

## Dashboard

The dashboard (`src/patient_api/static/`) is a thin client of the public API; it has no private
endpoints. It fetches `/meta`, `/patients/admission/summary`, `/patients/highest-bill`,
`/patients/longest-stay`, `/analytics/departments` and `/patients`, so anything it can show, an
API consumer can also get.

- **No build step.** Plain `index.html`, `styles.css`, `app.js` and `theme.js`, shipped as package data.
- **Strict CSP.** The page is served with `script-src 'self'; style-src 'self'; frame-ancestors 'none'`.
  That is why there are no inline scripts, styles or event handlers, and why dynamic styling goes
  through the CSSOM (`style.setProperty`) rather than `style` attributes.
- **No markup injection.** API text is only ever inserted with `textContent` / text nodes.
- **Tests enforce both rules** (`tests/test_ui_and_meta.py`): no inline script/style, no
  third-party URLs, and no `innerHTML`, `eval` or `document.write` anywhere in `app.js`.
- **One data language.** Filled cell = admitted, hollow = discharged, rose ring = highest bill,
  rose dot = longest stay. The same marks appear in the census, legend, notable records and drawer.

## Error model

Every deliberate error derives from `PatientAPIError`; the HTTP layer maps type → status in a
single table (`_STATUS_FOR` in `api.py`).

| Exception | HTTP | CLI exit | Meaning |
| --- | --- | --- | --- |
| `ValidationError` | 400 | 1 | Malformed id / missing department |
| `PatientNotFoundError` | 404 | 1 | No such patient |
| `EmptyDatasetError` | 404 | 1 | Aggregate over zero patients |
| `ConfigurationError` | 503 | 2 | Missing credentials or bad setting |
| `AuthenticationError` | 502 | 1 | Upstream rejected credentials |
| `DatasetError` | 502 | 1 | Upstream unreachable or malformed |

All bodies share one shape: `{"message": "..."}`.

## Resilience choices

- **Timeouts everywhere.** No request can hang forever (the original scripts had none).
- **Retry with backoff** on 429/502/503/504; free-tier hosts often return 502/503 while waking up.
- **Stale-on-error cache.** After one successful fetch, an upstream outage degrades to slightly old
  data rather than failing requests.
- **Tolerant parsing.** `null` fields fall back to defaults; a record that cannot be parsed at all
  is skipped and logged.
- **Lazy construction.** The app boots without credentials and reports a clean 503 on data routes.

## Extension points

- **New data source** (e.g. SQL): implement `all() -> list[Patient]` and return it from
  `build_repository`. Nothing else changes.
- **New metric**: add a pure function and a response model, then expose it in `api.py`/`cli.py`.
- **Auth for the HTTP layer**: add a FastAPI dependency to the router; the core is unaffected.

## Known limitations

- Analytics run in memory over the full dataset, which is fine for the thousands of records this
  targets, not for millions.
- The API itself is unauthenticated (see `SECURITY.md`).
- The data model has no admission/discharge dates, so time-series analytics are not yet possible.
