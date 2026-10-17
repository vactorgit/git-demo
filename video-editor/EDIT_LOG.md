# Edit log

One entry per video. The scoreboard: fixes needed per round should trend down video after video.
Newest first. Each entry: fixes caught by QC, by self-review, and by the user, plus the rules they produced.

## 2026-10-17 — Vision Quest Ep 2 "Theseus" (test edit, stand-in voice)
- **Source:** 8:34 synthetic voiceover of the user's review script → 8:19 cut (1 planted flub + 3 s dead air removed).
- **Round 1 (camera-placeholder draft):** 30 graphics. Self-review: 2 fixes (Code of Arms card + lower-third stacked; last two lower-thirds overlapping).
- **Round 2 (voiceover mode):** self-review: 2 fixes (captions collided with power cards; left-side Ultron card covered the show bug).
- **Round 3:** new automatic checks found 1 stacked graphic + 9 caption-only stretches of 18–41 s. Added 18 graphics (48 total); lists now build on their spoken cues.
- **Round 4 (self-review of round 3):** 4 list cards sat empty 1.8–4 s before their first item → now start 0.7 s before it.
  Also seen: Parakeet dropped "'d" ("the one I change" for "I'd change") — check contractions in captions on real takes.
- **User notes:** none yet.
- **Rules added:**
  - side cards go right in voiceover episodes
  - captions step aside for full-screen graphics and move aside for side cards
  - a new graphic at least every 15 s in voiceover episodes (now checked by `qc.py`)
  - list items are cued to their lines
  - the Line → visual table
  - the "Never" list
- **Promoted to `qc.py`:** stacked-graphics check, caption-only-gap check, empty-list check (> 1.5 s), plan-only mode.
