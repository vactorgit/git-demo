@echo off
rem Windows: double-click to start Transcript Grabber. Close this window to stop it.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then double-click this file again.
  pause
  exit /b 1
)
if not exist .venv (
  echo First run: setting things up, about a minute...
  python -m venv .venv || exit /b 1
)
.venv\Scripts\pip install -q --disable-pip-version-check -r requirements.txt || (pause & exit /b 1)
start "" http://127.0.0.1:5001
echo Transcript Grabber is running at http://127.0.0.1:5001
echo Leave this window open while you use it.
.venv\Scripts\python app.py
