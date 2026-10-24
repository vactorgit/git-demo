import core
import fake_youtube
import pytest
import summary
from fake_youtube import GOOD_ID, NO_CAPTIONS_ID, OFFLINE_ID, PRIVATE_ID


@pytest.mark.parametrize(
    "link",
    [
        f"https://www.youtube.com/watch?v={GOOD_ID}",
        f"https://www.youtube.com/watch?feature=share&v={GOOD_ID}&t=42s",
        f"https://m.youtube.com/watch?v={GOOD_ID}",
        f"https://youtu.be/{GOOD_ID}?si=abc",
        f"https://youtube.com/shorts/{GOOD_ID}",
        f"https://www.youtube.com/live/{GOOD_ID}",
        f"https://www.youtube.com/embed/{GOOD_ID}",
        f"https://www.youtube-nocookie.com/embed/{GOOD_ID}",
        f"  {GOOD_ID}  ",
    ],
)
def test_extract_video_id(link):
    assert core.extract_video_id(link) == GOOD_ID


@pytest.mark.parametrize("link", ["", "hello", "https://vimeo.com/123", "https://youtube.com/watch?v=short"])
def test_extract_video_id_rejects(link):
    assert core.extract_video_id(link) is None


def test_transcript_prefers_english_creator_captions(client):
    res = client.get(f"/api/transcript?v={GOOD_ID}")
    assert res.status_code == 200
    body = res.get_json()
    assert body["language_code"] == "en"
    assert body["is_generated"] is False
    assert len(body["segments"]) == len(fake_youtube.LINES)
    assert body["segments"][1] == {"start": 4.5, "duration": 4.0, "text": fake_youtube.LINES[1]}
    assert {l["code"] for l in body["languages"]} == {"en", "es"}
    assert {l["code"] for l in body["translations"]} == {"fr", "de"}
    assert body["info"]["title"] == "Test video"


def test_transcript_other_track_and_translation(client):
    assert client.get(f"/api/transcript?v={GOOD_ID}&lang=es").get_json()["language_code"] == "es"
    body = client.get(f"/api/transcript?v={GOOD_ID}&lang=fr").get_json()
    assert body["language_code"] == "fr"
    assert body["translated"] is True
    assert body["segments"][0]["text"].startswith("[fr]")


def test_transcript_errors(client):
    assert client.get("/api/transcript?v=hello").status_code == 400
    res = client.get(f"/api/transcript?v={NO_CAPTIONS_ID}")
    assert res.status_code == 404 and "no captions" in res.get_json()["error"]
    res = client.get(f"/api/transcript?v={PRIVATE_ID}")
    assert res.status_code == 404 and "unavailable" in res.get_json()["error"]
    res = client.get(f"/api/transcript?v={OFFLINE_ID}")
    assert res.status_code == 502 and "internet connection" in res.get_json()["error"]


def test_transcript_is_cached(client):
    fake_youtube.FakeApi.calls = 0
    client.get(f"/api/transcript?v={GOOD_ID}")
    client.get(f"/api/transcript?v={GOOD_ID}")
    assert fake_youtube.FakeApi.calls == 1


def test_pages_and_link_shortcuts(client):
    assert client.get("/").status_code == 200
    page = client.get(f"/transcript?v={GOOD_ID}")
    assert page.status_code == 200 and GOOD_ID.encode() in page.data
    assert client.get("/transcript?v=nope").headers["Location"].endswith("/?error=link")
    for path in (f"/watch?v={GOOD_ID}", f"/shorts/{GOOD_ID}", f"/live/{GOOD_ID}"):
        assert client.get(path).headers["Location"].endswith(f"/transcript?v={GOOD_ID}")


def test_downloads(client):
    txt = client.get(f"/download/{GOOD_ID}.txt")
    assert txt.status_code == 200
    assert txt.headers["Content-Disposition"] == f'attachment; filename="transcript-{GOOD_ID}.txt"'
    assert txt.get_data(as_text=True) == " ".join(fake_youtube.LINES)

    timed = client.get(f"/download/{GOOD_ID}.txt?timestamps=1").get_data(as_text=True)
    assert timed.splitlines()[1] == f"[0:04] {fake_youtube.LINES[1]}"

    srt = client.get(f"/download/{GOOD_ID}.srt").get_data(as_text=True)
    assert srt.startswith(f"1\n00:00:00,000 --> 00:00:04,000\n{fake_youtube.LINES[0]}\n")

    vtt = client.get(f"/download/{GOOD_ID}.vtt").get_data(as_text=True)
    assert vtt.startswith("WEBVTT\n\n00:00:00.000 --> 00:00:04.000\n")

    assert client.get(f"/download/{GOOD_ID}.exe").status_code == 404
    assert client.get(f"/download/{NO_CAPTIONS_ID}.txt").status_code == 404


def test_cue_end_never_overlaps_next_line():
    segs = [{"start": 0, "duration": 10, "text": "a"}, {"start": 3, "duration": 2, "text": "b"}]
    assert core.to_srt(segs).splitlines()[1] == "00:00:00,000 --> 00:00:03,000"


def test_clock_format():
    assert core.fmt_clock(5) == "0:05"
    assert core.fmt_clock(65.9) == "1:05"
    assert core.fmt_clock(3725) == "1:02:05"


def test_summary_off_without_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    res = client.post("/api/summary", json={"v": GOOD_ID})
    assert res.status_code == 501


def test_summary_uses_transcript(client, monkeypatch):
    seen = {}

    def fake_summarize(text, title):
        seen["text"], seen["title"] = text, title
        return "A short summary."

    monkeypatch.setattr(summary, "summarize", fake_summarize)
    res = client.post("/api/summary", json={"v": GOOD_ID})
    assert res.get_json() == {"summary": "A short summary."}
    assert seen["title"] == "Test video"
    assert seen["text"].startswith(f"[0:00] {fake_youtube.LINES[0]}")


def test_proxy_config_from_env(monkeypatch):
    for k in ("WEBSHARE_PROXY_USERNAME", "WEBSHARE_PROXY_PASSWORD", "PROXY_URL"):
        monkeypatch.delenv(k, raising=False)
    assert core.proxy_config() is None
    monkeypatch.setenv("PROXY_URL", "http://user:pass@proxy.example:8080")
    assert core.proxy_config() is not None
