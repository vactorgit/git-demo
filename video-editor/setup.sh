#!/usr/bin/env bash
# One-time setup for the This Comic Cooks editing pipeline. Safe to re-run.
# Works on Linux (cloud sessions) and macOS (brew). Needs: python3, node 18+, ffmpeg.
set -euo pipefail
cd "$(dirname "$0")"

command -v ffmpeg >/dev/null || { [[ "$(uname)" == Darwin ]] && brew install ffmpeg || { echo "install ffmpeg"; exit 1; }; }
python3 -m pip install -q sherpa-onnx soundfile numpy fonttools brotli
npm install --silent

# NVIDIA Parakeet TDT 0.6B v3 (int8 ONNX build, ~490 MB) from the sherpa-onnx GitHub releases.
MODEL_DIR="${PARAKEET_DIR:-$HOME/.cache/parakeet/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8}"
if [[ ! -f "$MODEL_DIR/encoder.int8.onnx" ]]; then
  mkdir -p "$(dirname "$MODEL_DIR")"
  curl -fSL https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2 \
    | tar xj -C "$(dirname "$MODEL_DIR")"
fi
echo "export PARAKEET_DIR=\"$MODEL_DIR\"  # add to your shell profile"

# Hyperframes needs a Chrome: reuse a pre-installed headless shell if there is one, else let it download its own.
if [[ -z "${HYPERFRAMES_BROWSER_PATH:-}" ]]; then
  CAND=$(ls /opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell 2>/dev/null | head -1 || true)
  [[ -n "$CAND" ]] && echo "export HYPERFRAMES_BROWSER_PATH=\"$CAND\"" || npx hyperframes browser ensure
fi

[[ -f sfx/pop.wav ]] || python3 scripts/make_sfx.py
echo "setup ok"
