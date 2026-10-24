#!/bin/bash
# Mac: double-click to start Transcript Grabber. Close this window to stop it.
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python isn't installed. Get it from https://www.python.org/downloads/ then double-click this file again."
  read -r -p "Press Enter to close."
  exit 1
fi
if [ ! -d .venv ]; then
  echo "First run: setting things up (about a minute)..."
  python3 -m venv .venv || exit 1
fi
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt || exit 1
(sleep 2 && open "http://127.0.0.1:5001") &
echo "Transcript Grabber is running at http://127.0.0.1:5001"
echo "Leave this window open while you use it."
.venv/bin/python app.py
