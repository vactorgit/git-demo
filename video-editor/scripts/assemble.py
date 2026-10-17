#!/usr/bin/env python3
"""Build a finished video from an edit decision list (edit.json).

usage: assemble.py EDIT.json [--out final.mp4] [--draft]

edit.json (all times in seconds):
{
  "format": "long" | "short",            # short = 1080x1920, min 61 s (TikTok Creator Rewards)
  "sources": ["raw/a-cam.mp4"],          # paths relative to edit.json
  "transcript": "work/transcript.json",  # optional; needed for captions
  "reframe_x": 0.5,                      # short from 16:9 source: horizontal crop centre (0-1)
  "segments": [{"src": 0, "in": 1.2, "out": 5.8, "zoom": 1.0}],   # zoom 1.12 = punch-in
  "overlays": [{"template": "lower-third", "src_at": 14.2, "dur": 4, "vars": {...}}],
  "sfx":      [{"name": "pop", "src_at": 14.2, "gain_db": -10}],
  "music":    [{"file": "music/bed.mp3", "at": 0, "to": 30, "gain_db": -22, "fade": 1.5}],
  "captions": true
}
Overlay/SFX/music times are either "at" (finished-video time) or "src_at" (time in source 0,
mapped through the cut; use this when picking moments off the transcript).
"""
import argparse, concurrent.futures as cf, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
SIZES = {"long": (1920, 1080), "short": (1080, 1920)}
SHORT_MIN = 61.0


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"command failed: {' '.join(map(str, cmd))[:400]}\n{r.stderr[-3000:]}")
    return r


def probe(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-show_entries", "format=duration", "-of", "json", str(path)])
    d = json.loads(r.stdout)
    return d["streams"][0]["width"], d["streams"][0]["height"], float(d["format"]["duration"])


def q(t):
    """Snap to the frame grid so audio and video segment lengths match exactly."""
    return round(t * FPS) / FPS


class Timeline:
    def __init__(self, segments):
        self.segs, pos = [], 0.0
        for s in segments:
            self.segs.append((s.get("src", 0), s["in"], s["out"], pos))
            pos += s["out"] - s["in"]
        self.duration = pos

    def to_out(self, src_t, src=0):
        for sid, a, b, pos in self.segs:
            if sid == src and a <= src_t < b:
                return pos + src_t - a
        # Moment was cut: snap to the next kept moment.
        later = [(pos, a) for sid, a, b, pos in self.segs if sid == src and a >= src_t]
        return min(later)[0] if later else None

    def resolve(self, item):
        if "at" in item:
            return item["at"]
        return self.to_out(item["src_at"], item.get("src", 0))


def cut_segment(i, seg, src, size, fmt, reframe_x, sw, sh, tmp):
    w, h = size
    z = float(seg.get("zoom", 1.0))
    vf = []
    if fmt == "short" and sw > sh:  # reframe 16:9 -> 9:16
        cw = sh * 9 / 16
        vf.append(f"crop={cw:.0f}:{sh}:{(sw - cw) * reframe_x:.0f}:0")
    if z > 1.0:  # punch-in, anchored a little above centre (faces sit in the upper third)
        vf.append(f"crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})*0.4")
    vf += [f"scale={w}:{h}:force_original_aspect_ratio=increase", f"crop={w}:{h}", "setsar=1", f"fps={FPS}"]
    dur = seg["out"] - seg["in"]
    fade = min(0.012, dur / 4)
    out = tmp / f"seg{i:04d}.mkv"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{seg['in']:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
         "-vf", ",".join(vf), "-af", f"aresample=48000,afade=t=in:d={fade},afade=t=out:st={dur - fade:.3f}:d={fade}",
         "-frames:v", str(round(dur * FPS)), "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-c:a", "pcm_s16le", "-ac", "2", str(out)])
    return out


def render_overlay(o, size, tmp, i):
    out = tmp / f"ov{i:03d}.webm"
    tpl = o["template"]
    vars_ = dict(o.get("vars", {}))
    for k, v in vars_.items():  # media paths in vars are relative to edit.json
        if isinstance(v, str) and (o["_base"] / v).is_file():
            vars_[k] = str((o["_base"] / v).resolve())
    run([sys.executable, str(ROOT / "scripts/render_overlay.py"), tpl, str(out), "--dur", str(o.get("dur", 4)),
         "--size", f"{size[0]}x{size[1]}", "--vars", json.dumps(vars_)])
    return out


def ass_time(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_captions(words, tl, size, path):
    """Shorts captions: 1-3 word chunks, brand lettering, active word in fire orange."""
    w, h = size
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Luckiest Guy,110,&H00FFFFFF,&H00FFFFFF,&H00111111,&H00111111,0,0,0,0,100,100,2,0,1,7,4,2,80,80,{int(h * 0.30)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    mapped = []
    for wd in words:
        s = tl.to_out(wd["start"])
        if s is None:
            continue
        # drop words that were cut (their mapped start snapped forward past their own end)
        e = s + (wd["end"] - wd["start"])
        src_kept = any(a <= wd["start"] < b for _, a, b, _ in tl.segs)
        if src_kept:
            mapped.append((s, e, wd["w"].upper()))
    lines, i = [], 0
    while i < len(mapped):
        chunk = [mapped[i]]
        while (len(chunk) < 3 and i + len(chunk) < len(mapped)
               and mapped[i + len(chunk)][0] - chunk[-1][1] < 0.25
               and not chunk[-1][2].endswith((".", "?", "!", ","))
               and sum(len(c[2]) for c in chunk) < 16):
            chunk.append(mapped[i + len(chunk)])
        end_chunk = chunk[-1][1] + 0.15
        nxt = mapped[i + len(chunk)][0] if i + len(chunk) < len(mapped) else end_chunk
        for k, (s, e, _) in enumerate(chunk):
            e2 = chunk[k + 1][0] if k + 1 < len(chunk) else min(end_chunk, nxt)
            text = " ".join(("{\\c&H4C91FF&}" + c[2] + "{\\c&HFFFFFF&}") if j == k else c[2] for j, c in enumerate(chunk))
            pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if k == 0 else ""
            lines.append(f"Dialogue: 0,{ass_time(s)},{ass_time(max(e2, s + 0.05))},Cap,,0,0,0,,{pop}{text}")
        i += len(chunk)
    Path(path).write_text(head + "\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit")
    ap.add_argument("--out")
    ap.add_argument("--draft", action="store_true", help="fast low-quality encode for review")
    a = ap.parse_args()
    edit_path = Path(a.edit).resolve()
    base = edit_path.parent
    E = json.loads(edit_path.read_text())
    fmt = E.get("format", "long")
    size = SIZES[fmt]
    sources = [base / s for s in E["sources"]]
    segs = [dict(s, **{"in": q(s["in"]), "out": q(s["out"])}) for s in E["segments"]]
    tl = Timeline(segs)
    out = Path(a.out) if a.out else base / "renders" / ("draft.mp4" if a.draft else "final.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "short" and tl.duration < SHORT_MIN:
        sys.exit(f"REFUSING: short is {tl.duration:.1f}s; TikTok Creator Rewards needs > 60 s. Add back material.")

    probes = {i: probe(s) for i, s in enumerate(sources)}
    with tempfile.TemporaryDirectory(prefix="tcc-edit-") as tmpd:
        tmp = Path(tmpd)
        print(f"cutting {len(segs)} segments → {tl.duration:.1f}s", file=sys.stderr)
        overlays = E.get("overlays", [])
        for o in overlays:
            o["_base"] = base
        with cf.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
            seg_jobs = [ex.submit(cut_segment, i, s, sources[s.get("src", 0)], size, fmt, E.get("reframe_x", 0.5),
                                  *probes[s.get("src", 0)][:2], tmp) for i, s in enumerate(segs)]
            seg_files = [j.result() for j in seg_jobs]
        print(f"rendering {len(overlays)} overlays", file=sys.stderr)
        with cf.ThreadPoolExecutor(max_workers=2) as ex:  # each Hyperframes render already uses several Chrome workers
            ov_files = list(ex.map(lambda p: render_overlay(p[1], size, tmp, p[0]), enumerate(overlays)))

        listing = tmp / "concat.txt"
        listing.write_text("".join(f"file '{f}'\n" for f in seg_files))
        cut = tmp / "cut.mkv"
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(cut)])

        inputs, vchain, achain = ["-i", str(cut)], [], []
        n = 1
        last = "[0:v]"
        for i, (o, f) in enumerate(zip(overlays, ov_files)):
            t0 = tl.resolve(o)
            if t0 is None:
                print(f"  skipping overlay {i}: its moment was cut", file=sys.stderr)
                continue
            inputs += ["-c:v", "libvpx-vp9", "-i", str(f)]
            vchain.append(f"[{n}:v]setpts=PTS-STARTPTS+{t0:.3f}/TB[o{i}];{last}[o{i}]overlay=eof_action=pass:format=auto[v{i}]")
            last = f"[v{i}]"
            n += 1
        if E.get("captions") and E.get("transcript"):
            ass = tmp / "captions.ass"
            write_captions(json.loads((base / E["transcript"]).read_text())["words"], tl, size, ass)
            vchain.append(f"{last}ass={ass}:fontsdir={ROOT / 'brand/fonts-ttf'}[vcap]")
            last = "[vcap]"
        vchain.append(f"{last}format=yuv420p[vout]")

        voice = "[0:a]"
        mix = [voice]
        for i, s in enumerate(E.get("sfx", [])):
            t0 = tl.resolve(s)
            if t0 is None:
                continue
            inputs += ["-i", str(ROOT / "sfx" / f"{s['name']}.wav")]
            ms = int(t0 * 1000)
            achain.append(f"[{n}:a]aresample=48000,volume={s.get('gain_db', -10)}dB,adelay={ms}|{ms}[s{i}]")
            mix.append(f"[s{i}]")
            n += 1
        beds = []
        for i, m in enumerate(E.get("music", [])):
            t0 = tl.resolve(m) or 0.0
            t1 = m.get("to", tl.duration)
            length = max(0.1, t1 - t0)
            fade = m.get("fade", 1.5)
            inputs += ["-stream_loop", "-1", "-i", str(base / m["file"])]
            ms = int(t0 * 1000)
            achain.append(f"[{n}:a]aresample=48000,atrim=0:{length:.3f},afade=t=in:d={min(fade, length / 3):.2f},"
                          f"afade=t=out:st={length - fade:.3f}:d={fade},volume={m.get('gain_db', -22)}dB,"
                          f"adelay={ms}|{ms}[m{i}]")
            beds.append(f"[m{i}]")
            n += 1
        if beds:
            # Duck music under the voice.
            achain.append(f"{voice}asplit=2[vk][vmix]")
            mix[0] = "[vmix]"
            achain.append(f"{''.join(beds)}amix=inputs={len(beds)}:normalize=0[bed]")
            achain.append("[bed][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck]")
            mix.append("[duck]")
        achain.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,"
                      "loudnorm=I=-14:TP=-1.0:LRA=11,aresample=48000[aout]")

        graph = ";".join(vchain + achain)
        enc = (["-c:v", "libx264", "-preset", "veryfast", "-crf", "26"] if a.draft
               else ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high"])
        run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
             *enc, "-r", str(FPS), "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
             "-t", f"{tl.duration:.3f}", str(out)])
    print(out)


if __name__ == "__main__":
    main()
