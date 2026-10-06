# Security Policy

## Handling credentials

- Upstream credentials are read **only** from environment variables (`PATIENT_API_*`), optionally
  supplied through a local `.env` file. They must never be committed. `.env` is git-ignored;
  `.env.example` contains placeholders only.
- If you ever commit a secret by accident, treat it as compromised: **rotate it first**, then
  remove it from the repository history. Deleting the file in a later commit is not enough, as the
  value remains in Git history.
- Secret scanning runs automatically: **Gitleaks** in CI (`.github/workflows/secret-scan.yml`) and as a
  pre-commit hook. Install the hook with `pre-commit install`.
- `patientctl doctor` reports whether secrets are set without printing them, so it is safe to share its output.

## Dashboard

The dashboard is served with a strict Content-Security-Policy and renders API text with
`textContent` only. Tests fail if inline scripts or styles, third-party requests, or
`innerHTML`/`eval` are introduced.

## Data

This repository contains only synthetic data. Do not add real patient information (PHI), even for
testing. If you adapt this project for real clinical data, you are responsible for the legal and
regulatory requirements that apply (for example HIPAA or India's DPDP Act), including access
control, audit logging and encryption in transit and at rest. The bundled API has no
authentication of its own.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security tab → *Report a vulnerability*) rather
than a public issue. Include steps to reproduce and the affected version.
