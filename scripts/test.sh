#!/usr/bin/env bash
set -euo pipefail

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Create venv first." >&2
  echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

".venv/bin/python" - <<'PY'
import sys
if sys.prefix == sys.base_prefix:
    raise SystemExit("Not in project venv context.")
PY

exec ".venv/bin/python" -m pytest "$@"
