# Changelog

All notable changes are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-06

First packaged release. Restructures the original coursework scripts into an installable
service.

### Added
- Installable `patient_api` package (`src/` layout, typed, `py.typed`).
- FastAPI service with eight documented endpoints, request-ID/timing headers and a uniform
  `{"message": ...}` error shape.
- Pure analytics layer: highest bill, longest stay, admission summary, department rollups.
- Resilient upstream client with timeouts and retry/backoff, plus a TTL cache that serves stale
  data when a refresh fails.
- `patientctl` CLI (JSON and table output, meaningful exit codes).
- Offline mode and a reproducible synthetic dataset.
- 122 tests, `ruff`, `mypy --strict`, GitHub Actions (Python 3.10–3.13 + Docker smoke test).
- Multi-stage non-root Dockerfile, `docker-compose.yml`, `Makefile`.
- README, architecture and operations docs, contributing guide, security policy.

### Changed
- Credentials now come from environment variables instead of being hardcoded in source.
- Patient-ID validation is stricter than `int()` (rejects `"2_01"`, signs, non-ASCII digits).
- `.gitignore` re-saved as UTF-8 (it was UTF-16 and ignored by Git).

### Removed
- The six standalone scripts and the empty `rough` file; their logic lives in the package and each
  original route is preserved (the two singular routes remain as hidden aliases).

### Security
- Removed hardcoded upstream credentials from the working tree. See `SECURITY.md`.
