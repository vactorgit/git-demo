#!/usr/bin/env python3
"""Final checks on a render, plus a timestamped review sheet for feedback.

usage: qc.py EDIT.json RENDER.mp4

Checks: black frames, dead air (> 1.2 s of silence), loudness (target -14 LUFS), audio/video
length mismatch, Short length (> 60 s). Writes <render>.review.md next to the render.
"""
import json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assemble import Timeline, apply_zooms, q  # noqa: E402


def ff(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"],
                          capture_output=True, text=True).stderr


def stream_durations(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    return {s["codec_type"]: float(s.get("duration", 0)) for s in json.loads(r.stdout)["streams"]}


def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    edit_path, render = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    E = json.loads(edit_path.read_text())
    problems, notes = [], []

    log = ff(["-i", str(render), "-vf", "blackdetect=d=0.25:pix_th=0.06", "-af", "silencedetect=n=-45dB:d=1.2,ebur128"])
    for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", log):
        problems.append(f"black frames {mmss(float(m[1]))}–{mmss(float(m[2]))}")
    starts = re.findall(r"silence_start: ([\d.]+)", log)
    ends = re.findall(r"silence_end: ([\d.]+)", log)
    for s, e in zip(starts, ends + [None] * (len(starts) - len(ends))):
        problems.append(f"dead air from {mmss(float(s))}" + (f" to {mmss(float(e))}" if e else " to end"))
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    if lufs:
        i = float(lufs[-1])
        (problems if abs(i + 14) > 1.5 else notes).append(f"integrated loudness {i:.1f} LUFS (target -14)")
    d = stream_durations(render)
    if abs(d.get("video", 0) - d.get("audio", 0)) > 0.1:
        problems.append(f"audio/video length mismatch: video {d.get('video')}s audio {d.get('audio')}s")
    length = d.get("video", 0)
    notes.append(f"length {mmss(length)}")
    if E.get("format") == "short" and length <= 60.5:
        problems.append(f"Short is {length:.1f}s — must be over 60 s for TikTok Creator Rewards")

    # Review sheet: what is said at each moment of the finished video, with every overlay/SFX placed.
    all_words = json.loads((edit_path.parent / E["transcript"]).read_text())["words"] if E.get("transcript") else []
    segs = apply_zooms([dict(s, **{"in": q(s["in"]), "out": q(s["out"])}) for s in E["segments"]], E.get("zooms", []), all_words)
    tl = Timeline(segs, all_words)
    rows = []
    if E.get("transcript"):
        words = json.loads((edit_path.parent / E["transcript"]).read_text())["words"]
        line, t0 = [], None
        for w in words:
            if not any(a <= w["start"] < b for _, a, b, _ in tl.segs):
                continue
            t = tl.to_out(w["start"])
            if t0 is None:
                t0 = t
            line.append(w["w"])
            if w["w"].endswith((".", "?", "!")) or len(line) > 18:
                rows.append((t0, "🗣", " ".join(line)))
                line, t0 = [], None
        if line:
            rows.append((t0, "🗣", " ".join(line)))
    for o in E.get("overlays", []):
        t = tl.resolve(o)
        if t is not None:
            rows.append((t, "🎨", f"{o['template']} ({o.get('dur', 4)}s): {json.dumps(o.get("vars", {}), ensure_ascii=False)[:120]}"))
    for s in E.get("sfx", []):
        t = tl.resolve(s)
        if t is not None:
            rows.append((t, "🔊", f"sfx {s['name']} {s.get('gain_db', -10)} dB"))
    rows.sort(key=lambda r: (r[0], r[1] != "🗣"))
    md = [f"# Review sheet — {render.name}", "",
          "Give notes as `0:12 — make the power card bigger`. Times below are finished-video times.", "",
          "## Checks", *[f"- ❌ {p}" for p in problems], *[f"- ✅ {n}" for n in notes], "",
          "## Timeline", *[f"- `{mmss(t)}` {k} {txt}" for t, k, txt in rows]]
    out = render.with_suffix(".review.md")
    out.write_text("\n".join(md) + "\n")
    print("\n".join(md[:8 + len(problems) + len(notes)]))
    print(out)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
