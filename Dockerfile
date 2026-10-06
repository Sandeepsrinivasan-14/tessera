# syntax=docker/dockerfile:1

# ---- build stage: install the package into an isolated prefix --------------
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

# ---- runtime stage: slim, non-root ------------------------------------------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATIENT_API_DATA_FILE=/app/data/sample_patients.json

RUN useradd --create-home --uid 10001 app
COPY --from=builder /install /usr/local
WORKDIR /app
# Synthetic demo data so the container works with zero configuration.
# For remote mode, unset PATIENT_API_DATA_FILE and supply the credentials.
COPY --chown=app:app data ./data
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["tessera", "serve", "--host", "0.0.0.0", "--port", "8000"]
