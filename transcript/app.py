import os
import re

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, url_for

import core
import summary

load_dotenv()

app = Flask(__name__)

LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def _language_arg() -> str | None:
    lang = (request.args.get("lang") or "").strip()
    return lang if lang and LANG_RE.match(lang) else None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/transcript")
def transcript_page():
    video_id = core.extract_video_id(request.args.get("v", ""))
    if not video_id:
        return redirect(url_for("index", error="link"))
    return render_template("transcript.html", video_id=video_id, ai=summary.available())


# Swap "youtube.com" for your site's address in any video link and it lands here,
# the same trick youtubetotranscript.com supports.
@app.route("/watch")
def watch_redirect():
    return redirect(url_for("transcript_page", v=request.args.get("v", "")))


@app.route("/shorts/<video_id>")
@app.route("/live/<video_id>")
@app.route("/embed/<video_id>")
def path_redirect(video_id):
    return redirect(url_for("transcript_page", v=video_id))


@app.route("/api/transcript")
def api_transcript():
    video_id = core.extract_video_id(request.args.get("v", ""))
    if not video_id:
        return jsonify({"error": "That doesn't look like a YouTube link. Paste a video URL or ID."}), 400
    try:
        result = core.get_transcript(video_id, _language_arg())
    except core.TranscriptError as e:
        return jsonify({"error": e.message}), e.status
    data = result.to_dict()
    data["info"] = core.get_video_info(video_id)
    return jsonify(data)


@app.route("/download/<video_id>.<fmt>")
def download(video_id, fmt):
    if not core.VIDEO_ID_RE.match(video_id) or fmt not in ("txt", "srt", "vtt"):
        abort(404)
    try:
        result = core.get_transcript(video_id, _language_arg())
    except core.TranscriptError as e:
        return Response(e.message, status=e.status, mimetype="text/plain")

    if fmt == "srt":
        body, mime = core.to_srt(result.segments), "application/x-subrip"
    elif fmt == "vtt":
        body, mime = core.to_vtt(result.segments), "text/vtt"
    else:
        body = core.to_plain(result.segments, timestamps=request.args.get("timestamps") == "1")
        mime = "text/plain"

    return Response(
        body,
        mimetype=mime,
        headers={"Content-Disposition": f'attachment; filename="transcript-{video_id}.{fmt}"'},
    )


@app.route("/api/summary", methods=["POST"])
def api_summary():
    data = request.get_json(silent=True) or {}
    video_id = core.extract_video_id(data.get("v", ""))
    if not video_id:
        return jsonify({"error": "Missing video."}), 400
    lang = data.get("lang") or None
    if lang and not LANG_RE.match(lang):
        lang = None
    try:
        result = core.get_transcript(video_id, lang)
        info = core.get_video_info(video_id)
        text = summary.summarize(core.to_plain(result.segments, timestamps=True), info.get("title"))
    except (core.TranscriptError, summary.SummaryError) as e:
        return jsonify({"error": e.message}), e.status
    return jsonify({"summary": text})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=False, host="127.0.0.1", port=port)
