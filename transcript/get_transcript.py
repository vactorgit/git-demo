"""Paste a YouTube link, get the full transcript.

Setup (once):   pip install youtube-transcript-api
Run:            python get_transcript.py
Or:             python get_transcript.py https://youtu.be/VIDEO_ID --timestamps

The transcript prints on screen and is saved as transcript-VIDEO_ID.txt
next to this script.
"""

import re
import sys
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApiException,
)

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
URL_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def extract_video_id(text: str) -> str | None:
    text = text.strip()
    if VIDEO_ID_RE.match(text):
        return text
    match = URL_RE.search(text)
    return match.group(1) if match else None


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fetch(video_id: str):
    # Prefer English captions, falling back to whatever the video has.
    transcripts = list(YouTubeTranscriptApi().list(video_id))
    if not transcripts:
        raise NoTranscriptFound(video_id, ["en"], transcripts)
    english = [t for t in transcripts if t.language_code.startswith("en")]
    pool = english or transcripts
    chosen = next((t for t in pool if not t.is_generated), pool[0])
    return chosen.fetch()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    timestamps = "--timestamps" in sys.argv

    link = args[0] if args else input("Paste a YouTube link: ")
    video_id = extract_video_id(link)
    if not video_id:
        print("That doesn't look like a YouTube link.")
        return 1

    try:
        fetched = fetch(video_id)
    except (TranscriptsDisabled, NoTranscriptFound):
        print("This video has no captions, so there's no transcript to get.")
        return 1
    except (VideoUnavailable, InvalidVideoId):
        print("That video is unavailable or private.")
        return 1
    except AgeRestricted:
        print("That video is age-restricted, so YouTube won't share its captions.")
        return 1
    except (RequestBlocked, IpBlocked):
        print("YouTube is blocking requests from this network. Try again later or from another connection.")
        return 1
    except YouTubeTranscriptApiException as e:
        print(f"Couldn't get the transcript: {type(e).__name__}")
        return 1

    lines = [" ".join(s.text.split()) for s in fetched.snippets]
    if timestamps:
        text = "\n".join(f"[{fmt_time(s.start)}] {line}" for s, line in zip(fetched.snippets, lines))
    else:
        text = " ".join(line for line in lines if line)

    out = Path(__file__).with_name(f"transcript-{video_id}.txt")
    out.write_text(text + "\n", encoding="utf-8")

    print(text)
    print(f"\n--- {len(text.split()):,} words, {fetched.language}. Saved to {out} ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
