import re

from flask import Flask, jsonify, render_template, request
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

app = Flask(__name__)

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
URL_PATTERNS = [
    re.compile(r"(?:youtube\.com|youtube-nocookie\.com)/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/)([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
]


def extract_video_id(text: str) -> str | None:
    text = text.strip()
    if VIDEO_ID_RE.match(text):
        return text
    for pattern in URL_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def pick_transcript(transcript_list, language: str | None):
    available = list(transcript_list)
    if language:
        for t in available:
            if t.language_code == language:
                return t, available
    # Prefer English, then manually written captions, then whatever exists.
    for t in available:
        if t.language_code.startswith("en") and not t.is_generated:
            return t, available
    for t in available:
        if t.language_code.startswith("en"):
            return t, available
    for t in available:
        if not t.is_generated:
            return t, available
    return available[0], available


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/transcript", methods=["POST"])
def transcript():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request."}), 400

    video_id = extract_video_id(data.get("url", ""))
    if not video_id:
        return jsonify({"error": "That doesn't look like a YouTube link. Paste a video URL or ID."}), 400

    language = data.get("language") or None

    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
        chosen, available = pick_transcript(transcript_list, language)
        fetched = chosen.fetch()
    except (TranscriptsDisabled, NoTranscriptFound, IndexError):
        return jsonify({"error": "This video has no captions, so there's no transcript to get."}), 404
    except (VideoUnavailable, InvalidVideoId):
        return jsonify({"error": "That video is unavailable or private."}), 404
    except AgeRestricted:
        return jsonify({"error": "That video is age-restricted, so YouTube won't share its captions."}), 403
    except (RequestBlocked, IpBlocked):
        return jsonify({"error": "YouTube is blocking requests from this server. Try again later or run it from another network."}), 503
    except YouTubeTranscriptApiException as e:
        return jsonify({"error": f"Couldn't get the transcript: {type(e).__name__}"}), 502

    return jsonify({
        "video_id": video_id,
        "language": fetched.language,
        "language_code": fetched.language_code,
        "is_generated": fetched.is_generated,
        "languages": [
            {"code": t.language_code, "name": t.language, "generated": t.is_generated}
            for t in available
        ],
        "segments": [
            {"start": round(s.start, 2), "text": s.text} for s in fetched.snippets
        ],
    })


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5001)
