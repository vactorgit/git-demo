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
  "captions": true,
  "backdrop": {"show": "The Obsession Report", "episode": "..."}   # voiceover-only episodes
}
A source with no video stream (a voiceover .wav/.mp3) switches to voiceover mode: the vo-backdrop
template loops under everything, captions sit centre screen, and zooms are ignored.
Overlay/SFX/music times are either "at" (finished-video time) or "src_at" (time in source 0,
mapped through the cut; use this when picking moments off the transcript).
"""
import argparse, concurrent.futures as cf, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
SIZES = {"long": (1920, 1080), "short": (1080, 1920)}
SHORT_MIN = 61.0
# Templates that cover the whole frame: captions step aside while they are up.
FULLSCREEN = {"title-slam", "show-open", "panel-showcase", "quote-card", "list-card", "score-card"}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"command failed: {' '.join(map(str, cmd))[:400]}\n{r.stderr[-3000:]}")
    return r


def probe(path):
    """(width, height, duration); width/height are None for audio-only sources (voiceover episodes)."""
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-show_entries", "format=duration", "-of", "json", str(path)])
    d = json.loads(r.stdout)
    v = d.get("streams") or [{}]
    return v[0].get("width"), v[0].get("height"), float(d["format"]["duration"])


def q(t):
    """Snap to the frame grid so audio and video segment lengths match exactly."""
    return round(t * FPS) / FPS


def norm_word(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


class Timeline:
    def __init__(self, segments, words=None):
        self.words = [w for w in (words or []) if any(a <= w["start"] < b for a, b in
                                                      ((s["in"], s["out"]) for s in segments if s.get("src", 0) == 0))]
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

    def find_cue(self, phrase, occurrence=1):
        """Source time where the kept transcript says `phrase` (nth occurrence)."""
        target = [norm_word(x) for x in phrase.split() if norm_word(x)]
        keys = [norm_word(w["w"]) for w in self.words]
        seen = 0
        for i in range(len(keys) - len(target) + 1):
            if keys[i:i + len(target)] == target:
                seen += 1
                if seen == occurrence:
                    return self.words[i]["start"], self.words[i + len(target) - 1]["end"]
        sys.exit(f"cue not found in transcript: {phrase!r} (occurrence {occurrence})")

    def resolve(self, item):
        if "at" in item:
            return item["at"]
        if "cue" in item:
            start, _ = self.find_cue(item["cue"], item.get("occurrence", 1))
            return self.to_out(start) + item.get("offset", 0.0)
        return self.to_out(item["src_at"], item.get("src", 0)) + item.get("offset", 0.0)


def apply_zooms(segs, zooms, words):
    """Split segments so each zoom {"cue", "dur", "zoom"} covers whole words; splits are seamless (no audio fade)."""
    tl = Timeline(segs, words)
    for z in zooms:
        start, _ = tl.find_cue(z["cue"], z.get("occurrence", 1))
        want_end = start + z.get("dur", 3.0)
        later = [w["start"] for w in tl.words if w["start"] >= want_end]
        end = later[0] - 0.02 if later else want_end
        out = []
        for s in segs:
            a, b = s["in"], s["out"]
            if b <= start or a >= end or s.get("src", 0) != 0:
                out.append(s)
                continue
            if a < start:
                out.append(dict(s, out=q(start - 0.02), join_out=True))
            out.append(dict(s, **{"in": q(max(a, start - 0.02)), "out": q(min(b, end)), "zoom": z.get("zoom", 1.15),
                                  "join_in": a < start, "join_out": b > end}))
            if b > end:
                out.append(dict(s, **{"in": q(end), "join_in": True}))
        segs = out
    return segs


def cut_segment(i, seg, src, size, fmt, reframe_x, sw, sh, tmp):
    w, h = size
    dur = seg["out"] - seg["in"]
    fade_in = 0 if seg.get("join_in") else min(0.012, dur / 4)
    fade_out = 0 if seg.get("join_out") else min(0.012, dur / 4)
    af = ",".join(["aresample=48000"] + ([f"afade=t=in:d={fade_in}"] if fade_in else [])
                  + ([f"afade=t=out:st={dur - fade_out:.3f}:d={fade_out}"] if fade_out else []))
    out = tmp / f"seg{i:04d}.mkv"
    if sw is None:  # voiceover: audio only, sample-exact to the frame grid
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{seg['in']:.3f}", "-i", str(src), "-t", f"{dur:.3f}", "-vn",
             "-af", af + f",apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}", "-c:a", "pcm_s16le", "-ac", "2", str(out)])
        return out
    z = float(seg.get("zoom", 1.0))
    vf = []
    if fmt == "short" and sw > sh:  # reframe 16:9 -> 9:16
        cw = sh * 9 / 16
        vf.append(f"crop={cw:.0f}:{sh}:{(sw - cw) * reframe_x:.0f}:0")
    if z > 1.0:  # punch-in, anchored a little above centre (faces sit in the upper third)
        vf.append(f"crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})*0.4")
    vf += [f"scale={w}:{h}:force_original_aspect_ratio=increase", f"crop={w}:{h}", "setsar=1", f"fps={FPS}"]
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{seg['in']:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
         "-vf", ",".join(vf), "-af", af,
         "-frames:v", str(round(dur * FPS)), "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-c:a", "pcm_s16le", "-ac", "2", str(out)])
    return out


def render_overlay(o, size, cache, i):
    """Render one graphic, reusing a cached render when template, assets, vars, duration and size are unchanged."""
    tpl = o["template"]
    vars_ = dict(o.get("vars", {}))
    if "_times" in o:
        vars_["times"] = o["_times"]
    h = hashlib.sha256()
    for k, v in vars_.items():  # media paths in vars are relative to edit.json
        if isinstance(v, str) and (o["_base"] / v).is_file():
            vars_[k] = str((o["_base"] / v).resolve())
            h.update(Path(vars_[k]).read_bytes())
    h.update((ROOT / "templates" / f"{tpl}.html").read_bytes())
    h.update((ROOT / "templates/assets/brand.css").read_bytes())
    h.update(json.dumps([tpl, vars_, o.get("dur", 4), size], sort_keys=True).encode())
    out = cache / f"{tpl}-{h.hexdigest()[:16]}.webm"
    if not out.exists():
        part = out.with_suffix(".part.webm")
        run([sys.executable, str(ROOT / "scripts/render_overlay.py"), tpl, str(part), "--dur", str(o.get("dur", 4)),
             "--size", f"{size[0]}x{size[1]}", "--vars", json.dumps(vars_)])
        part.rename(out)
    return out


def ass_time(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_captions(words, tl, size, path, style="short", hide=(), shift=()):
    """Burned-in captions in brand lettering, active word in fire orange.
    short: 1-3 words, lower third of a 9:16 frame. long (voiceover episodes): up to 4 words, centre screen.
    hide: (start, end) windows in finished-video time with no captions (full-screen graphics).
    shift: (start, end, x_fraction) windows where a side card is up: captions move to x and shrink."""
    w, h = size
    size_px, max_words, max_chars, align, margin_v = ((110, 3, 16, 2, int(h * 0.30)) if style == "short"
                                                      else (124, 4, 24, 5, 0))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Luckiest Guy,{size_px},&H00FFFFFF,&H00FFFFFF,&H00111111,&H00111111,0,0,0,0,100,100,2,0,1,8,5,{align},120,120,{margin_v},1

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
        if src_kept and not any(a <= s < b for a, b in hide):
            mapped.append((s, e, wd["w"].upper()))
    lines, i = [], 0
    while i < len(mapped):
        chunk = [mapped[i]]
        while (len(chunk) < max_words and i + len(chunk) < len(mapped)
               and mapped[i + len(chunk)][0] - chunk[-1][1] < 0.25
               and not chunk[-1][2].endswith((".", "?", "!", ","))
               and sum(len(c[2]) + 1 for c in chunk) + len(mapped[i + len(chunk)][2]) <= max_chars):
            chunk.append(mapped[i + len(chunk)])
        end_chunk = chunk[-1][1] + 0.15
        nxt = mapped[i + len(chunk)][0] if i + len(chunk) < len(mapped) else end_chunk
        nxt = min([nxt] + [a for a, b in hide if a > chunk[-1][0]])
        side = next((x for a, b, x in shift if a <= chunk[0][0] < b), None)
        sc = 72 if side is not None else 100
        place = f"\\an5\\pos({int(w * side)},{int(h * 0.5)})" if side is not None else ""
        for k, (s, e, _) in enumerate(chunk):
            e2 = chunk[k + 1][0] if k + 1 < len(chunk) else min(end_chunk, nxt)
            text = " ".join(("{\\c&H4C91FF&}" + c[2] + "{\\c&HFFFFFF&}") if j == k else c[2] for j, c in enumerate(chunk))
            pop = (f"{{{place}\\fscx{int(sc * 1.12)}\\fscy{int(sc * 1.12)}\\t(0,90,\\fscx{sc}\\fscy{sc})}}" if k == 0
                   else f"{{{place}\\fscx{sc}\\fscy{sc}}}")
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
    words = json.loads((base / E["transcript"]).read_text())["words"] if E.get("transcript") else []
    segs = apply_zooms(segs, E.get("zooms", []), words)
    tl = Timeline(segs, words)
    out = Path(a.out) if a.out else base / "renders" / ("draft.mp4" if a.draft else "final.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "short" and tl.duration < SHORT_MIN:
        sys.exit(f"REFUSING: short is {tl.duration:.1f}s; TikTok Creator Rewards needs > 60 s. Add back material.")

    probes = {i: probe(s) for i, s in enumerate(sources)}
    vo_only = all(p[0] is None for p in probes.values())
    if vo_only and E.get("zooms"):
        print("voiceover-only: zooms ignored (no camera footage)", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix="tcc-edit-") as tmpd:
        tmp = Path(tmpd)
        print(f"cutting {len(segs)} segments → {tl.duration:.1f}s", file=sys.stderr)
        overlays = E.get("overlays", [])
        for o in overlays:
            o["_base"] = base
            # Builds: items given as {"text", "cue"} appear when their line is spoken.
            items = o.get("vars", {}).get("items")
            if items and any(isinstance(x, dict) for x in items):
                t0 = tl.resolve(o)
                o["_times"] = [round(tl.resolve(x) - t0, 2) if isinstance(x, dict) and "cue" in x and t0 is not None
                               else None for x in items]
                o["vars"] = dict(o["vars"], items=[x["text"] if isinstance(x, dict) else x for x in items])
        with cf.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
            seg_jobs = [ex.submit(cut_segment, i, s, sources[s.get("src", 0)], size, fmt, E.get("reframe_x", 0.5),
                                  *probes[s.get("src", 0)][:2], tmp) for i, s in enumerate(segs)]
            seg_files = [j.result() for j in seg_jobs]
        print(f"rendering {len(overlays)} overlays", file=sys.stderr)
        with cf.ThreadPoolExecutor(max_workers=2) as ex:  # each Hyperframes render already uses several Chrome workers
            cache = base / "work" / "overlay-cache"
            cache.mkdir(parents=True, exist_ok=True)
            ov_files = list(ex.map(lambda p: render_overlay(p[1], size, cache, p[0]), enumerate(overlays)))

        listing = tmp / "concat.txt"
        listing.write_text("".join(f"file '{f}'\n" for f in seg_files))
        cut = tmp / "cut.mkv"
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(cut)])

        if vo_only:
            loop = tmp / "backdrop.mp4"
            run([sys.executable, str(ROOT / "scripts/render_overlay.py"), "vo-backdrop", str(loop), "--dur", "10",
                 "--size", f"{size[0]}x{size[1]}", "--format", "mp4", "--vars", json.dumps(E.get("backdrop", {}))])
            inputs, vchain, achain = ["-stream_loop", "-1", "-i", str(loop), "-i", str(cut)], [], []
            n, last, voice = 2, "[0:v]", "[1:a]"
        else:
            inputs, vchain, achain = ["-i", str(cut)], [], []
            n, last, voice = 1, "[0:v]", "[0:a]"
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
            hide = [(t, t + o.get("dur", 4)) for o in overlays if o["template"] in FULLSCREEN
                    for t in [tl.resolve(o)] if t is not None]
            shift = [(t, t + o.get("dur", 4), 0.62 if o["vars"].get("side") == "left" else 0.38) for o in overlays
                     if o["template"] == "power-card" and fmt != "short" for t in [tl.resolve(o)] if t is not None]
            write_captions(words, tl, size, ass, style="short" if fmt == "short" else "long", hide=hide, shift=shift)
            vchain.append(f"{last}ass={ass}:fontsdir={ROOT / 'brand/fonts-ttf'}[vcap]")
            last = "[vcap]"
        vchain.append(f"{last}format=yuv420p[vout]")

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
