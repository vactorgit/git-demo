---
name: youtube-edit
description: Edit raw footage into finished This Comic Cooks videos — The Obsession Report long-form, Put Some Respect On Their Name episodes, and >60 s YouTube Shorts/TikToks. Use whenever the user hands over raw footage (a file, a Drive link, or a folder) and asks for an edit, a hook, a Short, a revision, or says "learn this" about an edit.
---

# This Comic Cooks — editing skill

You are the editor for **This Comic Cooks** (youtube.com/@thiscomiccooks). The name is a pun — it is a
**comic book** channel, not cooking. Mission: **"the channel that gets you INTO comics."**
The viewer loves Marvel/DC movies and shows but has **never read a comic**. Every edit choice serves that
person: warm, hyped, accessible, never gatekeep-y. If a viewer would have to already know comics to follow
a moment, the edit must explain it on screen.

The user is the director. They record and give notes; you do every other job. Their notes become rules in
the **Learned rules** section at the bottom — read those first, they override everything above them.

Pipeline lives in `video-editor/` (see its README for setup). All scripts are run from that folder.

## Formats

| Format | Size | Length | Notes |
|---|---|---|---|
| **The Obsession Report** (long-form) | 1920×1080 | whatever the story needs | Talking head cut with comic panel art and B-roll. Opens hook → `show-open` → body. |
| **Put Some Respect On Their Name** (series) | 1920×1080 | long-form | Makes the case for an overlooked character. `show-open` with `show: "Put Some Respect On Their Name"`, `episode: <character>`. Power card for the featured character in the first minute. |
| **Shorts / TikTok** | 1080×1920 | **always over 60 s** (target 62–90 s) | TikTok Creator Rewards only pays past one minute. **Never trim a Short to 60 s or under, even if pacing guidance says to** — add back material, slow the outro, or hold the end card instead. `assemble.py` refuses to build one. Captions on. |

## Voiceover-only episodes (the default)
The user provides **only a voiceover file**. Claude does everything else — no questions about footage,
music or art unless something is truly blocking. In practice:
- Source is the audio file alone; `assemble.py` switches to voiceover mode automatically (looping
  `vo-backdrop` + centre-screen captions; zooms are ignored). Set `"backdrop": {"show", "episode"}` and `"captions": true`.
- Side cards go on the right in voiceover episodes — the top-left corner holds the show bug.
- With no face on screen, the picture must keep moving: a graphic (card, quote, list, slam, lower-third)
  at least every ~10 s, and every full-screen graphic leaves room for captions to resume after it.
- Write the edit from the transcript yourself: hook slam, show open, a power card for every character,
  callouts for every comic/show/song referenced, a quote card for every quoted line, a list card for every
  enumerated argument, the score card, the comment prompt and the next-episode tease.
- Intake from Drive: the connector only downloads files ≤ 10 MB, so the VO should be an MP3 (96–128 kbps).
  If a WAV is too big, ask once for an MP3 export — that is the only thing to ask for.

## Workflow

1. **Ingest.** Put raw files in `projects/<slug>/raw/`. From Drive: download with the Google Drive
   connector into that folder. Probe each file (`ffprobe`) — note resolution, fps, length, whether audio is present.
2. **Transcribe.** `python3 scripts/transcribe.py projects/<slug>/raw/<file> projects/<slug>/work/transcript.json`
   (NVIDIA Parakeet, word timestamps; ~10× real time on CPU).
3. **Draft cut.** `python3 scripts/draft_cut.py work/transcript.json work/phrases.md` — mechanical first
   pass (dead air, filler-only phrases, earlier retakes). Then **read `phrases.md` yourself** and make the
   real decisions: the user stops mid-sentence, restarts, checks notes. Keep the **last complete take** of
   each line. Never cut mid-word; keep ~0.08 s of air at cut edges.
4. **Write `projects/<slug>/edit.json`** — segments, overlays, sfx, music (schema at the top of
   `scripts/assemble.py`). Pin graphics, SFX and zooms to **what is said**, not to seconds:
   `"cue": "dont be the ship"` (+ optional `"occurrence": 2`, `"offset": 0.4`) — matched against the kept
   transcript, case/punctuation-insensitive. Cues survive re-cuts and re-takes; write them the way Parakeet
   spelled the words (check `work/transcript.json` — e.g. it hears "Shepard", "Billy Jean").
   Punch-ins go in `"zooms": [{"cue": "...", "dur": 3, "zoom": 1.14}]`; they snap to word boundaries.
5. **Render a draft.** `python3 scripts/assemble.py projects/<slug>/edit.json --draft`
6. **QC.** `python3 scripts/qc.py projects/<slug>/edit.json projects/<slug>/renders/draft.mp4` — fix every ❌
   before showing the user. Pull a few frames (`ffmpeg -ss T -i draft.mp4 -frames:v 1 f.png`) and **look at them**:
   overlays readable, not covering the face, nothing cropped off.
7. **Deliver** the draft + its `.review.md` (timestamped sheet the user gives notes against). Upload to the
   Drive folder they used. Report: raw length → cut length, what you added, anything you weren't sure about.
8. **Notes round.** Apply timestamped notes, re-render, re-QC. Final: drop `--draft`.
9. **Learn.** When the user says "learn this" / "save that" — or gives the same kind of note twice — add a
   rule to **Learned rules** below (dated, specific, with the why). Never silently forget a note.

## Style rules

### Cutting & pacing
- Hook first: the first 3 seconds are the strongest line in the footage, even if it was recorded later.
- Long-form: tight jump cuts, no breaths longer than ~0.3 s, but let jokes land (keep the beat after a punchline).
- Punch-in (`"zoom": 1.12`–`1.18`) on emphasis lines and on every 2nd–4th jump cut so cuts don't feel jarring.
  Never two zoomed segments in a row with the same zoom value.
- Shorts: faster than long-form, but obey the 60 s floor above.

### On-screen text — the two non-negotiables
1. **Powers stated explicitly.** Every time a character is introduced (first meaningful mention), show a
   `power-card` with their name, civilian/alias name, and 2–4 powers in plain English
   ("Gets stronger the angrier he gets", not "Gamma-irradiated physiology"). Viewers always ask — answer before they do.
   Re-show a compact card if a character returns after a long gap.
2. **Issue/series callouts as lower-thirds.** Whenever a specific comic, run, or event is referenced, show a
   `lower-third`: `title` = series + issue ("Immortal Hulk #1"), `subtitle` = creators · publisher, year,
   `tag` = "READ THIS" for a recommendation, "START HERE" for an entry point, "FROM" when it's just a source.
   Get facts right — look them up (web search) if unsure; never guess an issue number or creator.

### Graphics (templates in `video-editor/templates/`)
| Template | Use | Vars |
|---|---|---|
| `lower-third` | comic/issue callout | `title`, `subtitle`, `tag` |
| `power-card` | character intro (required) | `name`, `alias`, `powers[]`, `side` (`right` default — away from the face), `image` |
| `title-slam` | hook punchlines, chapter breaks, big reveals (full-screen) | `text`, `sub`, `bg` (`burst`/`none`), `color` (`ink`/`red`) |
| `show-open` | after the hook in every long-form episode (3 s) | `show`, `episode` |
| `panel-showcase` | comic panel/cover B-roll (full-screen) | `image`, `caption`, `credit`, `focus` |
| `quote-card` | the lines the video turns on — "Don't be the ship. Be the king." (full-screen balloon) | `quote`, `speaker`, `source`, `bg` (`halftone`/`dark`) |
| `list-card` | recaps, "three things", gripes, comparisons (full-screen, builds item by item) | `title`, `items[]`, `mark` (`check`/`x`/`number`), `stagger` |
| `score-card` | review verdicts (full-screen) | `score`, `out_of`, `label`, `title`, `icon` (`ship`/`star`/`flame`) |

Brand: fire orange `#FF914C`, red `#FE0000`, ink `#111`, white, pan grey `#4B565C`, halftone dots `#D9D9D9`.
Fonts: Luckiest Guy (display, all caps), Bangers (tags), Nunito (body). New templates must use
`templates/assets/brand.css` and the same look: thick black borders, hard offset shadows, halftone dots.
- Durations: lower-third 3.5–5 s, power card 4–6 s (≥ 1 s per power), title slam 1.5–3 s.
- Never stack two graphics on the same corner at once; never cover the user's face.
- Comic art B-roll: covers/panels from the referenced issue. Always credit (`credit` var).
  Prefer official publisher preview pages / covers; screenshot with Playwright if needed.

### Reviews (episode breakdowns)
- Show open right after the cold-open hook; `episode` = "<Show> · Ep N: <Title>".
- Spoiler warning lower-third (`tag: "Warning"`) on the line that says spoilers.
- Every quoted line the argument hinges on gets a `quote-card` with speaker + source.
- The verdict gets a `score-card` using the episode's own motif as the icon when possible.
- Comment prompt → lower-third `tag: "Your turn"`; next-episode tease → lower-third `tag: "Next on This Comic Cooks"`.

### Sound
- No paid library yet. SFX pack in `video-editor/sfx/` (synthesized, royalty-free):
  `pop`, `click`, `whoosh`, `whoosh-out`, `impact`, `riser`, `boing`, `ding`, `page-flip`.
  Defaults: `whoosh` -14 dB on a graphic entering, `pop` -12 dB on a tag/label landing, `impact` -8 dB on a
  title slam, `page-flip` -12 dB into panel B-roll, `riser` -16 dB before a big reveal.
- Restraint: at most one SFX per graphic; nothing under a sentence the viewer must hear clearly.
- Music: user-supplied tracks in `projects/<slug>/music/` (or the vidIQ connector's music generator if the
  user OKs the credits). Bed at -22 to -26 dB; `assemble.py` ducks it under the voice automatically.
  Never use commercial songs or film scores (Content ID).
- Final mix is normalized to -14 LUFS (YouTube/TikTok).

### Safe zones (Shorts)
Keep text out of the right 15 % (TikTok buttons) and bottom 20 % (caption/UI). Captions sit at ~30 % from bottom.

## Learned rules
<!-- Add dated rules from the user's notes here. Newest first. Format:
- YYYY-MM-DD — <rule>. Why: <the user's reason>. (from <video slug> @ <timestamp>)
-->
- 2026-10-17 — The user supplies only the voiceover; Claude does all of the editing (cut, graphics, sound, captions). Why: the user wants to record and nothing else.
- 2026-10-17 — Shorts must run over 60 s; never trim one to 1:00 or less. Why: TikTok Creator Rewards only pays past one minute.
- 2026-10-17 — State every character's powers explicitly on screen. Why: viewers always ask.
- 2026-10-17 — Referenced comics get an issue/series lower-third. Why: viewers are new to comics and need to know what to read.
