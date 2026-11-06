#!/usr/bin/env bash
# Launch Erwin's Hypothesis on your computer.
# First run sets everything up (about a minute); later runs start in seconds.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is needed. Install it from https://www.python.org/downloads/ and run this again."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "First run: setting up (this happens only once)..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
if [ ! -f .venv/.installed ] || [ backend/requirements.txt -nt .venv/.installed ]; then
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r backend/requirements.txt
  touch .venv/.installed
fi

PORT="${EH_PORT:-8765}"
URL="http://127.0.0.1:${PORT}"
echo ""
echo "  Erwin's Hypothesis is running at ${URL}"
echo "  Close this window (or press Ctrl+C) to quit."
echo ""
( sleep 1.5; open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || true ) &
cd backend
exec python -m app.main
