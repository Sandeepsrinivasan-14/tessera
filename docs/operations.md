# Operations

## Running

| Goal | Command |
| --- | --- |
| Local, offline | `PATIENT_API_DATA_FILE=data/sample_patients.json patientctl serve` |
| Local, hot reload | `make serve` |
| Remote upstream | export `PATIENT_API_STUDENT_ID` / `PATIENT_API_PASSWORD`, then `patientctl serve` |
| Container | `docker compose up --build` |
| Production-style | `uvicorn "patient_api.api:create_app" --factory --host 0.0.0.0 --port 8000 --workers 2` |

With multiple workers each process keeps its own cache, which is fine for read-only data.

## Health and observability

- `GET /health` is a pure liveness probe and never touches the upstream, so it stays green during
  an upstream outage. The Docker image uses it for `HEALTHCHECK`.
- Every response carries `X-Request-ID` (echoed if the client sends one) and `X-Process-Time-ms`.
- The server logs one line per request at INFO: method, path, status, latency, request id.
  Use `-v` for debug logging.

## Tuning for slow upstreams

Free-tier hosts such as Render sleep when idle, and the first request after a sleep can take tens
of seconds.

- Raise `PATIENT_API_TIMEOUT` (default 45 s) if cold starts exceed it.
- Raise `PATIENT_API_CACHE_TTL` to reduce how often the upstream is hit.
- Retries (`PATIENT_API_RETRIES`) use exponential backoff and honour `Retry-After`.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| 503 `missing environment variable(s)` | No credentials and no data file | Set credentials or `PATIENT_API_DATA_FILE` |
| 502 `token request failed with HTTP 401` | Wrong credentials / set | Check `PATIENT_API_STUDENT_ID`, `_PASSWORD`, `_SET` |
| 502 `could not reach ...` | Upstream asleep or down | Retry; increase timeout and retries |
| 400 on `/patients/filter` | `department` missing or blank | Pass `?department=Cardiology` |
| Empty patient list | Upstream returned no valid records | Check logs for "skipping malformed patient record" |
