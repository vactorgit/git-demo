#!/usr/bin/env python3
"""Propose a first-pass cut from a Parakeet transcript: drop dead air, filler-only phrases and earlier retakes.

usage: draft_cut.py TRANSCRIPT.json OUT_PHRASES.md [--gap 0.35] [--pad 0.08]

Writes a numbered phrase list (KEEP / CUT + reason) for Claude to review, and prints a JSON
segments array ready to paste into edit.json. Claude makes the final call from the phrase list;
this script only does the mechanical first pass.
"""
import argparse, json, re

FILLERS = {"um", "uh", "erm", "uhh", "umm", "hmm", "ah", "like", "so", "okay", "ok"}


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def phrases(words, gap):
    out, cur = [], []
    for w in words:
        if cur and w["start"] - cur[-1]["end"] > gap:
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("out")
    ap.add_argument("--gap", type=float, default=0.35, help="silence (s) that splits phrases")
    ap.add_argument("--pad", type=float, default=0.08, help="breathing room kept around speech (s)")
    a = ap.parse_args()
    t = json.load(open(a.transcript))
    ph = phrases(t["words"], a.gap)
    keys = [[norm(w["w"]) for w in p] for p in ph]
    verdict = []
    for i, k in enumerate(keys):
        content = [x for x in k if x and x not in FILLERS]
        if not content:
            verdict.append(("CUT", "filler only"))
            continue
        # Retake: a later phrase (within ~4 phrases) restarts with the same opening words -> keep the later take.
        head = content[:3]
        retake = len(head) >= 2 and any(
            [x for x in keys[j] if x not in FILLERS][:len(head)] == head
            for j in range(i + 1, min(i + 5, len(keys))))
        verdict.append(("CUT", "retake (a later take starts the same way)") if retake else ("KEEP", ""))

    lines = [f"# Phrase list for {t.get('source', '')}", "",
             "Review these. Retake detection is a heuristic — check every CUT and every long KEEP.", ""]
    segs = []
    for i, (p, (v, why)) in enumerate(zip(ph, verdict)):
        text = " ".join(w["w"] for w in p)
        lines.append(f"{i:03d} [{p[0]['start']:7.2f} → {p[-1]['end']:7.2f}] {v}{' — ' + why if why else ''}: {text}")
        if v == "KEEP":
            s, e = max(0.0, p[0]["start"] - a.pad), min(t["duration"], p[-1]["end"] + a.pad)
            if segs and s - segs[-1]["out"] < 0.15:
                segs[-1]["out"] = round(e, 3)  # natural pause inside a take: keep it continuous
            else:
                segs.append({"in": round(s, 3), "out": round(e, 3)})
    open(a.out, "w").write("\n".join(lines) + "\n")
    kept = sum(s["out"] - s["in"] for s in segs)
    print(json.dumps({"segments": segs, "kept_seconds": round(kept, 2), "raw_seconds": t["duration"]}, indent=1))


if __name__ == "__main__":
    main()
