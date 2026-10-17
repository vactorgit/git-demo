# This Comic Cooks — Claude Code video editor

Raw footage in, finished video out. Claude Code coordinates; these free tools do the jobs:

| Job | Tool |
|---|---|
| Transcriber | NVIDIA Parakeet TDT 0.6B v3 (`scripts/transcribe.py`, via sherpa-onnx, runs on CPU) |
| Editor | Claude, following `.claude/skills/youtube-edit/SKILL.md` → writes `edit.json` |
| Animator | HyperFrames (HeyGen) — branded HTML templates in `templates/` rendered to transparent video |
| Sound | `sfx/` starter pack (synthesized), user-supplied music, auto-ducking |
| Finisher | FFmpeg (`scripts/assemble.py` cut + composite + mix, `scripts/qc.py` checks) |

The style lives in the skill. Notes the user gives get saved into its **Learned rules** section.

## Setup

```bash
cd video-editor && ./setup.sh
```

## Edit a video

Ask Claude: *"Use the youtube-edit skill to edit `<file or Drive link>` as an Obsession Report episode"*
(or a Short, or a Put Some Respect On Their Name episode). By hand:

```bash
P=projects/moon-knight
python3 scripts/transcribe.py $P/raw/take1.mp4 $P/work/transcript.json
python3 scripts/draft_cut.py  $P/work/transcript.json $P/work/phrases.md   # then write $P/edit.json
python3 scripts/assemble.py   $P/edit.json --draft
python3 scripts/qc.py         $P/edit.json $P/renders/draft.mp4             # writes draft.review.md
```

Preview one graphic on its own:

```bash
python3 scripts/render_overlay.py power-card /tmp/pc.webm --dur 5 \
  --vars '{"name":"Moon Knight","alias":"Marc Spector","powers":["Strength peaks at the full moon"]}'
```

## Layout

```
brand/        logos, brand.json, fonts (woff2 for HTML, ttf for captions)
templates/    HyperFrames overlays: lower-third, power-card, title-slam, show-open, panel-showcase
sfx/          sound effects (regenerate with scripts/make_sfx.py)
scripts/      transcribe, draft_cut, render_overlay, assemble, qc
projects/     per-video working folders (git-ignored: raw footage stays out of the repo)
```
