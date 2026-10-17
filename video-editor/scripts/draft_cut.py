#!/usr/bin/env python3
"""Propose a first-pass cut from a Parakeet transcript: drop dead air, filler-only bits and earlier retakes.

usage: draft_cut.py TRANSCRIPT.json OUT_PHRASES.md [--gap 0.35] [--max-pause 0.45] [--pad 0.08]

Works sentence by sentence (a sentence ends at . ? ! or at a pause longer than --gap), because
restarts often run straight into the line before them. Writes a numbered list (KEEP / CUT + reason)
for Claude to review, and prints a JSON segments array ready for edit.json. Claude makes the final
call from the list; this script only does the mechanical first pass.
"""
import argparse, json, re

FILLERS = {"um", "uh", "erm", "uhh", "umm", "hmm", "ah", "okay", "ok", "hold", "on", "wait", "sorry"}


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def sentences(words, gap):
    out, cur = [], []
    for w in words:
        if cur and w["start"] - cur[-1]["end"] > gap:
            out.append(cur)
            cur = []
        cur.append(w)
        if w["w"].endswith((".", "?", "!")):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("out")
    ap.add_argument("--gap", type=float, default=0.35, help="silence (s) that always splits sentences")
    ap.add_argument("--max-pause", type=float, default=0.45, help="longer pauses between kept lines get trimmed")
    ap.add_argument("--pad", type=float, default=0.08, help="breathing room kept around speech (s)")
    a = ap.parse_args()
    t = json.load(open(a.transcript))
    units = sentences(t["words"], a.gap)
    content = [[x for x in (norm(w["w"]) for w in u) if x and x not in FILLERS] for u in units]
    verdict = []
    for i, c in enumerate(content):
        if not c:
            verdict.append(("CUT", "filler only"))
            continue
        # Retake: one of the next few lines restarts with the same opening words -> keep the later take.
        head = c[:4]
        retake = len(head) >= 3 and any(content[j][:len(head)] == head for j in range(i + 1, min(i + 4, len(units))))
        # Trailing-off false start: short line ending in a filler ("... the, uh. Hold on.")
        tail = norm(units[i][-1]["w"])
        trail = tail in FILLERS and len(units[i]) > 2
        verdict.append(("CUT", "retake (a later take starts the same way)") if retake
                       else ("CUT", "trails off into filler") if trail else ("KEEP", ""))

    lines = [f"# Line list for {t.get('source', '')}", "",
             "Review these. Retake detection is a heuristic — check every CUT and every long KEEP.", ""]
    segs, prev_kept_end = [], None
    for i, (u, (v, why)) in enumerate(zip(units, verdict)):
        text = " ".join(w["w"] for w in u)
        lines.append(f"{i:03d} [{u[0]['start']:7.2f} → {u[-1]['end']:7.2f}] {v}{' — ' + why if why else ''}: {text}")
        if v != "KEEP":
            prev_kept_end = None
            continue
        gap_before = u[0]["start"] - (units[i - 1][-1]["end"] if i else 0.0)
        gap_after = (units[i + 1][0]["start"] if i + 1 < len(units) else t["duration"]) - u[-1]["end"]
        s = max(0.0, u[0]["start"] - min(a.pad, gap_before / 2))
        e = min(t["duration"], u[-1]["end"] + min(a.pad, gap_after / 2))
        if segs and prev_kept_end is not None and u[0]["start"] - prev_kept_end <= a.max_pause:
            segs[-1]["out"] = round(e, 3)  # natural pause between kept lines: stay continuous
        else:
            segs.append({"in": round(s, 3), "out": round(e, 3)})
        prev_kept_end = u[-1]["end"]
    open(a.out, "w").write("\n".join(lines) + "\n")
    kept = sum(s["out"] - s["in"] for s in segs)
    print(json.dumps({"segments": segs, "kept_seconds": round(kept, 2), "raw_seconds": t["duration"]}, indent=1))


if __name__ == "__main__":
    main()
