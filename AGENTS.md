# Agent Instructions

## Python Environment

- Always run tests with the project-local virtual environment at `.venv`.
- Do not run tests with system `python` or system `pytest`.
- Preferred commands:
  - `source .venv/bin/activate && pytest`
  - `./scripts/test.sh`
  - `make test`

## Test Execution Policy

- All local verification and debugging test runs must go through `.venv`.
- CI and local runs should use the same entrypoint (`./scripts/test.sh`) to avoid environment drift.
