#!/usr/bin/env bash
# Setup for SIFT. Safe to run more than once.
set -uo pipefail
cd "$(dirname "$0")"

say()  { printf '  %s\n' "$1"; }
fail() { printf '\n  SETUP STOPPED\n  %s\n\n' "$1"; exit 1; }

echo ""
echo "Setting up CV Screening…"
echo ""

# --- 1. Python ---------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || fail \
"Python 3 is not installed.
   Ubuntu/WSL:  sudo apt update && sudo apt install python3 python3-pip
   Mac:         brew install python3
   Windows:     https://python.org/downloads"

PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
say "Python $PYV found"

# --- 2. Virtual environment (optional) ---------------------------------------
# Found by cold-cloning this repo: python3-venv is NOT installed by default on
# Ubuntu, and the original script died with ".venv/bin/activate: No such file
# or directory" - meaningless to a non-developer. It now explains the problem
# and carries on without a venv rather than stopping.
PY=python3
if python3 -m venv .venv >/dev/null 2>&1 && [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PY=python
  say "Created an isolated environment (.venv)"
else
  rm -rf .venv
  say "Could not create an isolated environment - installing into your user"
  say "  Python instead. That works fine. To use one, first run:"
  say "     sudo apt install python3-venv       (Ubuntu / WSL)"
fi

# --- 3. Dependencies ---------------------------------------------------------
say "Installing packages (this takes a minute)…"
if [ "$PY" = "python" ]; then
  $PY -m pip install -q --upgrade pip >/dev/null 2>&1
  $PY -m pip install -q -r requirements.txt || fail "Could not install packages. Check your internet connection."
else
  $PY -m pip install -q --user --upgrade pip >/dev/null 2>&1
  $PY -m pip install -q --user -r requirements.txt || fail \
"Could not install packages.
   Check your internet connection, or try:
     python3 -m pip install --user --break-system-packages -r requirements.txt"
fi
say "Packages installed"

# --- 4. Folders and settings -------------------------------------------------
mkdir -p data credentials
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  NEEDS_KEY=1
else
  NEEDS_KEY=0
fi

$PY -c "from sift import db; db.init()" >/dev/null 2>&1 && say "Database ready" \
  || say "Database will be created on first run"

# --- 5. What to do next ------------------------------------------------------
echo ""
if [ "$NEEDS_KEY" = "1" ] || ! grep -q '^GROQ_API_KEY=.\+' .env 2>/dev/null; then
  echo "  ALMOST DONE - one thing left:"
  echo ""
  echo "  1. Get a free key at  https://console.groq.com/keys"
  echo "  2. Open the file called  .env  in this folder"
  echo "  3. Paste your key after  GROQ_API_KEY="
  echo "  4. Then run:  ./run.sh"
else
  echo "  Setup complete. Start it with:  ./run.sh"
  echo "  Then open  http://localhost:8000"
fi
echo ""
