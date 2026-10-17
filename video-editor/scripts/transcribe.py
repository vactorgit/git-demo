#!/usr/bin/env python3
"""Transcribe a video/audio file with NVIDIA Parakeet (TDT 0.6B v3, via sherpa-onnx) into word timestamps.

usage: transcribe.py INPUT OUT.json

Output: {"duration": s, "words": [{"w": "Hello", "start": 0.12, "end": 0.40}, ...], "text": "..."}
Long inputs are decoded in ~25 s windows cut at silences so timestamps stay accurate.
"""
import json, os, subprocess, sys
from pathlib import Path
import numpy as np

MODEL = Path(os.environ.get("PARAKEET_DIR") or next((p for p in [Path.home() / ".cache/parakeet/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8", Path("/opt/models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8")] if p.exists()), ""))
SR = 16000


def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def windows(audio, target=25.0, search=5.0):
    """Split at the quietest 50 ms frame near each target boundary."""
    hop = int(0.05 * SR)
    energy = np.sqrt(np.convolve(audio ** 2, np.ones(hop) / hop, mode="same")[::hop] + 1e-12)
    start, n = 0, len(audio)
    while start < n:
        if n - start <= (target + search) * SR:
            yield start, n
            return
        lo, hi = int((start + (target - search) * SR) / hop), int((start + (target + search) * SR) / hop)
        cut = (lo + int(np.argmin(energy[lo:hi]))) * hop
        yield start, cut
        start = cut


def tokens_to_words(tokens, stamps, durations, offset):
    words = []
    for i, (tok, ts) in enumerate(zip(tokens, stamps)):
        # TDT durations can swallow the pause after a word; cap them so silences stay visible.
        end = ts + min(durations[i] if durations and i < len(durations) and durations[i] > 0 else 0.08, 0.32)
        if tok.startswith(" ") or not words:
            words.append({"w": tok.strip(), "start": ts + offset, "end": end + offset})
        else:
            words[-1]["w"] += tok
            if tok.strip() not in {".", ",", "?", "!", "...", ";", ":"}:  # punctuation lands late; ignore its time
                words[-1]["end"] = end + offset
    return [w for w in words if w["w"]]


def main():
    import sherpa_onnx
    src, out = sys.argv[1], sys.argv[2]
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(MODEL / "encoder.int8.onnx"), decoder=str(MODEL / "decoder.int8.onnx"),
        joiner=str(MODEL / "joiner.int8.onnx"), tokens=str(MODEL / "tokens.txt"),
        model_type="nemo_transducer", num_threads=os.cpu_count() or 4)
    audio = load_audio(src)
    words = []
    for a, b in windows(audio):
        s = rec.create_stream()
        s.accept_waveform(SR, audio[a:b])
        rec.decode_stream(s)
        r = s.result
        durs = list(getattr(r, "durations", []) or [])
        words += tokens_to_words(list(r.tokens), list(r.timestamps), durs, a / SR)
        print(f"  {b / SR:7.1f}s / {len(audio) / SR:.1f}s", file=sys.stderr)
    # A word never runs past the next word's start.
    for w, nxt in zip(words, words[1:]):
        w["end"] = round(min(w["end"], nxt["start"]), 3)
        w["start"] = round(w["start"], 3)
    if words:
        words[-1]["start"] = round(words[-1]["start"], 3)
        words[-1]["end"] = round(words[-1]["end"], 3)
    data = {"source": str(src), "duration": round(len(audio) / SR, 3), "words": words,
            "text": " ".join(w["w"] for w in words)}
    Path(out).write_text(json.dumps(data, indent=1))
    print(out)


if __name__ == "__main__":
    main()
