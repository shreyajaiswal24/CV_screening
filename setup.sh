#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Setting up SIFT…"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
mkdir -p data credentials
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "  Created .env — now open it and paste your Groq API key after GROQ_API_KEY="
  echo "  Get a free key at https://console.groq.com/keys"
fi
python -c "from sift import db; db.init()" 2>/dev/null || true
echo ""
echo "  Setup complete. Next:  ./run.sh"
