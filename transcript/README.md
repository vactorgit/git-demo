# Transcript Grabber

Your own version of youtubetotranscript.com. Paste a YouTube link, get the full transcript.

## Desktop app (easiest)

Download it from the **Transcript Grabber (desktop app)** release on this repo's Releases page:
`TranscriptGrabber-Windows.zip` or `TranscriptGrabber-Mac.zip`. Unzip it and open **Transcript Grabber**. Nothing else to install.

- Windows: if a blue "Windows protected your PC" box appears, click **More info**, then **Run anyway**.
- Mac (Apple silicon, 2020 or newer): right-click the app, choose **Open**, then **Open**. If macOS still blocks it, go to **System Settings > Privacy & Security** and click **Open Anyway**.

Those warnings appear because the app isn't signed with a paid Apple/Microsoft developer certificate.
For AI summaries in the desktop app, put a `.env` file with `ANTHROPIC_API_KEY=...` in the same folder as the app.

GitHub builds both versions automatically (`.github/workflows/desktop.yml`) whenever anything in `transcript/` changes.

## Start it from the code (on your computer, free)

1. Install Python once from https://www.python.org/downloads/. On Windows, tick **"Add python.exe to PATH"** in the installer.
2. Download this `transcript` folder.
3. Double-click **`start.command`** (Mac) or **`start.bat`** (Windows).
   - Mac: the first time, right-click the file, choose **Open**, then **Open** again (Mac asks once for files downloaded from the internet).
   - The first run takes about a minute to set up.
4. Your browser opens the site. Leave the black window open while you use it, and close it to stop.

## What it does

| Feature | |
|---|---|
| Paste any YouTube link (videos, Shorts, live replays, youtu.be, embeds) | ✓ |
| Pasting a link starts right away | ✓ |
| Video player next to the transcript | ✓ |
| The line being spoken lights up and the transcript follows the video | ✓ |
| Click any line to jump the video there | ✓ |
| Timestamps on or off | ✓ |
| Paragraph view for easier reading | ✓ |
| Search the transcript, with matches highlighted | ✓ |
| Switch between the video's caption languages | ✓ |
| Machine-translate into other languages | ✓ |
| Copy to clipboard | ✓ |
| Download as text, text with timestamps, SRT or VTT subtitles | ✓ |
| Video title and channel | ✓ |
| AI summary with timestamped key points (optional, needs an Anthropic API key) | ✓ |
| Recently opened videos on the home page | ✓ |
| Shareable links: `/transcript?v=VIDEO_ID` | ✓ |
| Link shortcut: swap `youtube.com` for your site's address in any video link | ✓ |
| Works on phones, light and dark mode | ✓ |

It only works on videos that have captions (creator-written or auto-generated), the same as youtubetotranscript.com.

### Optional: AI summaries

Copy `.env.example` to `.env` and put your Anthropic API key after `ANTHROPIC_API_KEY=`. Restart the app. The **AI summary** box appears on each transcript page. Each summary is a paid Claude API call.

## Put it online (optional)

The folder is ready for hosts like Render or Railway (`Procfile` included; set the root directory to `transcript`).
YouTube blocks most hosting servers from fetching captions, so a hosted copy also needs a residential proxy.
Add `WEBSHARE_PROXY_USERNAME` / `WEBSHARE_PROXY_PASSWORD` (a Webshare "Residential" plan) or `PROXY_URL` as environment variables on the host.

## Command-line version

`python get_transcript.py` asks for a link, prints the transcript and saves it as a text file. Add `--timestamps` for timed lines.

## For developers

```
pip install -r requirements.txt pytest
python -m pytest -q tests          # unit and route tests (offline, fake YouTube)
node tests/benchmark.js            # feature benchmark in a real browser (needs Playwright)
python app.py                      # http://127.0.0.1:5001
```

`tests/benchmark.js` checks every feature in the table above against a fake YouTube and prints PASS/FAIL per feature.
