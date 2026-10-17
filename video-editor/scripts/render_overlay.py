#!/usr/bin/env python3
"""Render one branded overlay template to a transparent WebM (or MOV/MP4).

usage: render_overlay.py TEMPLATE OUT --vars '{"title": "..."}' [--dur 4] [--size 1920x1080] [--format webm]

TEMPLATE is a name in templates/ (e.g. lower-third) or a path to an .html file.
Images referenced in vars ("image": "/abs/path.png") are copied next to the composition.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
BROWSER = next(iter(sorted(Path("/opt/pw-browsers").glob("chromium_headless_shell-*/chrome-linux/headless_shell"))), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("out")
    ap.add_argument("--vars", default="{}")
    ap.add_argument("--dur", type=float, default=4.0)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--format", default="webm", choices=["webm", "mov", "mp4"])
    ap.add_argument("--fps", default="30")
    ap.add_argument("--quality", default="looks")
    a = ap.parse_args()

    tpl = Path(a.template)
    if not tpl.exists():
        tpl = TEMPLATES / f"{a.template}.html"
    w, h = a.size.split("x")
    vars_ = json.loads(a.vars)

    with tempfile.TemporaryDirectory(prefix="tcc-overlay-") as tmp:
        proj = Path(tmp)
        shutil.copytree(TEMPLATES / "assets", proj / "assets")
        # Copy any local media into the project so Chrome can load it by relative path.
        for k, v in list(vars_.items()):
            if isinstance(v, str) and os.path.isfile(v):
                dst = proj / "assets" / f"media-{k}{Path(v).suffix.lower()}"
                shutil.copy(v, dst)
                vars_[k] = f"assets/{dst.name}"
        html = tpl.read_text()
        html = (html.replace("{{W}}", w).replace("{{H}}", h)
                    .replace("{{DUR}}", f"{a.dur:g}")
                    .replace("{{VARS}}", json.dumps(vars_)))
        (proj / "index.html").write_text(html)
        (proj / "hyperframes.json").write_text("{}")
        out = Path(a.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, HYPERFRAMES_SKIP_SKILLS="1", HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
        if BROWSER and "HYPERFRAMES_BROWSER_PATH" not in env:
            env["HYPERFRAMES_BROWSER_PATH"] = str(BROWSER)
        cmd = ["npx", "--prefix", str(ROOT), "hyperframes", "render", str(proj), "-o", str(out),
               "--format", a.format, "--fps", a.fps, "--quality", a.quality, "--quiet"]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            sys.stderr.write(r.stdout[-4000:] + r.stderr[-4000:])
            sys.exit(1)
    print(out)


if __name__ == "__main__":
    main()
