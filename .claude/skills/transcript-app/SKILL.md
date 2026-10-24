---
name: transcript-app
description: Work on the Transcript Grabber app in transcript/ (the user's own youtubetotranscript.com). Use when changing, testing, running or deploying it.
---

# Transcript Grabber (`transcript/`)

A Flask app benchmarked against youtubetotranscript.com: paste a YouTube link, get the transcript.

## Layout
- `core.py`: link parsing, fetching via `youtube-transcript-api` (with in-memory cache, optional proxy from env), TXT/SRT/VTT formatting.
- `summary.py`: optional AI summary through the Anthropic SDK (`claude-opus-5-5`, streaming, `fallbacks="default"`). Off unless `ANTHROPIC_API_KEY` is set.
- `app.py`: routes. `/transcript?v=ID` page, `/api/transcript`, `/download/ID.(txt|srt|vtt)`, `/api/summary`, and `/watch`, `/shorts/ID`, `/live/ID`, `/embed/ID` redirects.
- `templates/`, `static/style.css`, `static/transcript.js`: UI. Player sync uses the YouTube IFrame API.
- `start.command` / `start.bat`: double-click launchers for the user (creates `.venv`, installs, opens the browser).
- `get_transcript.py`: standalone command-line version.
- `desktop.py`: desktop app (pywebview window around the Flask server). `TG_HEADLESS=1 TG_PORT=n` runs only the server, which the build uses as a smoke test.
- `.github/workflows/desktop.yml`: builds Windows (.exe) and Mac (.app) with PyInstaller on GitHub Actions, then republishes the `transcript-grabber-desktop` release. Bundled files resolve through `sys._MEIPASS` in `app.py`.

## Verify every change
1. `python -m pytest -q transcript/tests`
2. `node transcript/tests/benchmark.js`. It must print `N/N features passing`. When adding a feature, add a `check(...)` for it and a row to the README feature table.

Both use `tests/fake_youtube.py`, because cloud sessions can't reach YouTube. Say so when reporting results: real-video behavior is untested from the cloud.

## Gotchas
- `[hidden]` must stay `display: none !important` in `style.css`; component `display` rules otherwise override it (this once left the Download menu stuck open over the transcript).
- The user is not a developer. Keep instructions to double-click steps, and explain any cost (proxy, API key) before relying on it.
- No claude.ai artifact can fetch YouTube itself. That's why this is a Flask app.
