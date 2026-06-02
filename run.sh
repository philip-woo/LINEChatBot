#!/usr/bin/env bash
# Start the FastAPI ingestion service. Loads .env, ensures SSL_CERT_FILE for
# macOS, and runs uvicorn on PORT (default 8000).
set -euo pipefail
cd "$(dirname "$0")"

# Ensure SSL_CERT_FILE is set (macOS Python cert fix) if .env didn't set it.
if [ -z "${SSL_CERT_FILE:-}" ]; then
  export SSL_CERT_FILE="$(./.venv/bin/python -c 'import certifi; print(certifi.where())')"
fi

PORT="${PORT:-8000}"
exec ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" "$@"
