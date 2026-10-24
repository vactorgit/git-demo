"""A stand-in for youtube_transcript_api so tests and the benchmark run offline."""

from types import SimpleNamespace as NS

from youtube_transcript_api._errors import TranscriptsDisabled, VideoUnavailable

GOOD_ID = "dQw4w9WgXcQ"
NO_CAPTIONS_ID = "nocaptions0"
PRIVATE_ID = "privatevid0"
OFFLINE_ID = "offlinevid0"

LINES = [
    "Welcome back to the channel.",
    "Today we're talking about the X-Men.",
    "First, a little history.",
    "The team first appeared in 1963.",
    "Let's look at the original five members.",
    "Thanks for watching, see you next time.",
]


class FakeTrack:
    def __init__(self, code, name, generated, translatable=True, translated_to=None):
        self.language_code = code
        self.language = name
        self.is_generated = generated
        self.translation_languages = (
            [NS(language="French", language_code="fr"), NS(language="German", language_code="de")]
            if translatable
            else []
        )
        self._translated_to = translated_to

    @property
    def is_translatable(self):
        return bool(self.translation_languages)

    def translate(self, code):
        names = {"fr": "French", "de": "German"}
        return FakeTrack(code, names[code], True, False, translated_to=code)

    def fetch(self):
        prefix = f"[{self.language_code}] " if self.language_code != "en" else ""
        return NS(
            language=self.language,
            language_code=self.language_code,
            is_generated=self.is_generated,
            snippets=[NS(start=i * 4.5, duration=4.0, text=prefix + t) for i, t in enumerate(LINES)],
        )


class FakeApi:
    calls = 0

    def __init__(self, proxy_config=None):
        pass

    def list(self, video_id):
        FakeApi.calls += 1
        if video_id == NO_CAPTIONS_ID:
            raise TranscriptsDisabled(video_id)
        if video_id == PRIVATE_ID:
            raise VideoUnavailable(video_id)
        if video_id == OFFLINE_ID:
            import requests

            raise requests.ConnectionError("no network")
        return [FakeTrack("es", "Spanish (auto-generated)", True), FakeTrack("en", "English", False)]


def install():
    import core

    core.YouTubeTranscriptApi = FakeApi
    core.get_video_info = lambda vid: {"title": "Test video", "author": "Test channel", "thumbnail": ""}
    core.clear_cache()
