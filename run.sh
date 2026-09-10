#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -f .venv/bin/activate ] && source .venv/bin/activate
if ! grep -q '^GROQ_API_KEY=.\+' .env 2>/dev/null; then
  echo ""
  echo "  No API key yet. Open the file called  .env  and paste your key"
  echo "  after  GROQ_API_KEY=   then run this again."
  echo "  Get a free key at https://console.groq.com/keys"
  echo ""
  exit 1
fi
echo ""
echo "  CV Screening is running."
echo "  Open  http://localhost:8000  in your browser."
echo "  Press Ctrl+C here to stop it."
echo ""
exec python3 -m uvicorn screening.api:app --host 127.0.0.1 --port 8000
