#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -d .venv ] && source .venv/bin/activate
echo "SIFT is running — open http://localhost:8000 in your browser."
exec uvicorn sift.api:app --host 127.0.0.1 --port 8000
