.DEFAULT_GOAL := help
PY ?= python

.PHONY: help install test lint format typecheck check serve data docker clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package with dev dependencies (editable)
	$(PY) -m pip install -e ".[dev]"

test:  ## Run the test suite with coverage
	$(PY) -m pytest --cov --cov-report=term-missing

lint:  ## Lint with ruff
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format:  ## Auto-format and fix lint issues
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

typecheck:  ## Strict type-check with mypy
	$(PY) -m mypy

check: lint typecheck test  ## Everything CI runs

serve:  ## Run the API locally against the sample data
	PATIENT_API_DATA_FILE=data/sample_patients.json tessera serve --reload

data:  ## Regenerate the synthetic sample dataset
	$(PY) scripts/generate_sample_data.py > data/sample_patients.json

docker:  ## Build the container image
	docker build -t tessera .

clean:  ## Remove build and cache artefacts
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
