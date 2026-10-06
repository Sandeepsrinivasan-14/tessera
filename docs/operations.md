# Operations

## Running

| Goal | Command |
| --- | --- |
| Local, offline | `PATIENT_API_DATA_FILE=data/sample_patients.json patientctl serve` |
| Local, hot reload | `make serve` |
| Remote upstream | `cp .env.example .env`, fill it in, run `patientctl doctor`, then `patientctl serve` |
| Dashboard | open `http://127.0.0.1:8000/` once the server is running |
| Container | `docker compose up --build` |
| Production-style | `uvicorn "patient_api.api:create_app" --factory --host 0.0.0.0 --port 8000 --workers 2` |

With multiple workers each process keeps its own cache, which is fine for read-only data.

## Checking your configuration

`patientctl doctor` shows the mode (offline or remote), the base URL, whether the credentials are
*set* or *missing*, and whether a `.env` file was found. It never prints a secret value, so its
output is safe to paste into an issue. It exits with `2` when something required is missing.

Configuration is read from real environment variables first, then from a `.env` file in the
directory you run the command from.

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
| 503 `missing environment variable(s)` | No credentials and no data file | Fill in `.env` (run `patientctl doctor`) or set `PATIENT_API_DATA_FILE` |
| Dashboard shows "Patient records are unavailable." | The API returned an error; the banner above it says why | Follow the message, then choose **Try again** |
| 502 `token request failed with HTTP 401` | Wrong credentials / set | Check `PATIENT_API_STUDENT_ID`, `_PASSWORD`, `_SET` |
| 502 `could not reach ...` | Upstream asleep or down | Retry; increase timeout and retries |
| 400 on `/patients/filter` | `department` missing or blank | Pass `?department=Cardiology` |
| Empty patient list | Upstream returned no valid records | Check logs for "skipping malformed patient record" |
