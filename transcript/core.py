"""Fetch, cache and format YouTube transcripts."""

import os
import re
import threading
import time
from dataclasses import dataclass, field

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    NotTranslatable,
    RequestBlocked,
    TranscriptsDisabled,
    TranslationLanguageNotAvailable,
    VideoUnavailable,
    YouTubeTranscriptApiException,
)
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
URL_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)

CACHE_TTL = 6 * 3600
CACHE_MAX = 300


class TranscriptError(Exception):
    """A failure with a message fit to show the user, plus an HTTP status."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class Transcript:
    video_id: str
    language: str
    language_code: str
    is_generated: bool
    translated: bool
    segments: list  # [{"start": float, "duration": float, "text": str}]
    languages: list = field(default_factory=list)  # caption tracks the video has
    translations: list = field(default_factory=list)  # languages it can be machine-translated into

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "language": self.language,
            "language_code": self.language_code,
            "is_generated": self.is_generated,
            "translated": self.translated,
            "languages": self.languages,
            "translations": self.translations,
            "segments": self.segments,
        }


def extract_video_id(text: str) -> str | None:
    text = (text or "").strip()
    if VIDEO_ID_RE.match(text):
        return text
    match = URL_RE.search(text)
    return match.group(1) if match else None


def proxy_config():
    """Optional proxy for servers whose IP YouTube blocks (most cloud hosts)."""
    user, password = os.getenv("WEBSHARE_PROXY_USERNAME"), os.getenv("WEBSHARE_PROXY_PASSWORD")
    if user and password:
        return WebshareProxyConfig(proxy_username=user, proxy_password=password)
    url = os.getenv("PROXY_URL")
    if url:
        return GenericProxyConfig(http_url=url, https_url=url)
    return None


_cache: dict = {}
_cache_lock = threading.Lock()


def _cache_get(key):
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
        _cache.pop(key, None)
        return None


def _cache_put(key, value):
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            del _cache[oldest]
        _cache[key] = (time.time(), value)


def clear_cache():
    with _cache_lock:
        _cache.clear()


def _pick(tracks, language: str | None):
    if language:
        for t in tracks:
            if t.language_code == language:
                return t
    # Prefer English, then creator-written captions, then whatever exists.
    english = [t for t in tracks if t.language_code.startswith("en")]
    pool = english or tracks
    return next((t for t in pool if not t.is_generated), pool[0])


def get_transcript(video_id: str, language: str | None = None) -> Transcript:
    key = (video_id, language or "")
    cached = _cache_get(key)
    if cached:
        return cached

    try:
        # A new client per call: the library's client isn't thread-safe.
        tracks = list(YouTubeTranscriptApi(proxy_config=proxy_config()).list(video_id))
        if not tracks:
            raise TranscriptError("This video has no captions, so there's no transcript to get.", 404)

        chosen = _pick(tracks, language)
        translated = False
        if language and chosen.language_code != language:
            chosen = chosen.translate(language)
            translated = True
        fetched = chosen.fetch()
    except (TranscriptsDisabled, NoTranscriptFound):
        raise TranscriptError("This video has no captions, so there's no transcript to get.", 404)
    except (NotTranslatable, TranslationLanguageNotAvailable):
        raise TranscriptError("YouTube can't translate this video's captions into that language.", 400)
    except (VideoUnavailable, InvalidVideoId):
        raise TranscriptError("That video is unavailable or private.", 404)
    except AgeRestricted:
        raise TranscriptError("That video is age-restricted, so YouTube won't share its captions.", 403)
    except (RequestBlocked, IpBlocked):
        raise TranscriptError(
            "YouTube is blocking requests from this server. Try again later, or set up a proxy (see README).", 503
        )
    except YouTubeTranscriptApiException as e:
        raise TranscriptError(f"Couldn't get the transcript ({type(e).__name__}).", 502)

    base = tracks[0]
    result = Transcript(
        video_id=video_id,
        language=fetched.language,
        language_code=fetched.language_code,
        is_generated=fetched.is_generated,
        translated=translated,
        segments=[
            {"start": round(s.start, 2), "duration": round(s.duration, 2), "text": clean_text(s.text)}
            for s in fetched.snippets
            if clean_text(s.text)
        ],
        languages=[
            {"code": t.language_code, "name": t.language, "generated": t.is_generated} for t in tracks
        ],
        translations=[
            {"code": l.language_code, "name": l.language}
            for l in (next((t for t in tracks if t.is_translatable), base).translation_languages or [])
        ],
    )
    _cache_put(key, result)
    return result


def get_video_info(video_id: str) -> dict:
    """Title and channel from YouTube's public oEmbed endpoint. Best effort."""
    cached = _cache_get(("info", video_id))
    if cached:
        return cached
    info = {"title": None, "author": None, "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"}
    try:
        res = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=5,
        )
        if res.ok:
            data = res.json()
            info["title"] = data.get("title")
            info["author"] = data.get("author_name")
    except (requests.RequestException, ValueError):
        pass
    _cache_put(("info", video_id), info)
    return info


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("​", "").split())


def fmt_clock(seconds: float) -> str:
    s = int(seconds)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _fmt_cue(seconds: float, sep: str) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _cue_end(segments, i) -> float:
    seg = segments[i]
    end = seg["start"] + (seg.get("duration") or 0)
    if i + 1 < len(segments):
        end = min(end, segments[i + 1]["start"]) if end > seg["start"] else segments[i + 1]["start"]
    return max(end, seg["start"] + 0.5)


def to_plain(segments, timestamps: bool = False) -> str:
    if timestamps:
        return "\n".join(f"[{fmt_clock(s['start'])}] {s['text']}" for s in segments)
    return " ".join(s["text"] for s in segments)


def to_srt(segments) -> str:
    blocks = []
    for i, seg in enumerate(segments):
        blocks.append(
            f"{i + 1}\n{_fmt_cue(seg['start'], ',')} --> {_fmt_cue(_cue_end(segments, i), ',')}\n{seg['text']}\n"
        )
    return "\n".join(blocks)


def to_vtt(segments) -> str:
    cues = [
        f"{_fmt_cue(seg['start'], '.')} --> {_fmt_cue(_cue_end(segments, i), '.')}\n{seg['text']}\n"
        for i, seg in enumerate(segments)
    ]
    return "WEBVTT\n\n" + "\n".join(cues)
