#!/usr/bin/env python3
"""Synthesize the starter sound-effects pack into sfx/ (royalty-free: we made them).

Replace or add to these with real library sounds later; the skill only cares about the file names.
"""
import numpy as np
import soundfile as sf
from pathlib import Path

SR = 48000
OUT = Path(__file__).resolve().parent.parent / "sfx"
rng = np.random.default_rng(7)


def t(dur):
    return np.arange(int(SR * dur)) / SR


def env(n, attack=0.005, release=None):
    e = np.ones(n)
    a = max(1, int(SR * attack))
    e[:a] = np.linspace(0, 1, a)
    r = n - a if release is None else int(SR * release)
    e[-r:] *= np.linspace(1, 0, r) ** 2
    return e


def lowpass(x, cutoff):
    # one-pole low-pass; cutoff may be an array (sweeps)
    cutoff = np.broadcast_to(cutoff, x.shape)
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    prev = 0.0
    for i in range(len(x)):
        prev = (1 - a[i]) * x[i] + a[i] * prev
        y[i] = prev
    return y


def norm(x, peak=0.8):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def pop():
    tt = t(0.09)
    f = np.geomspace(900, 250, len(tt))
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(tt), 0.002), 0.7)


def click():
    tt = t(0.03)
    x = rng.standard_normal(len(tt)) * np.exp(-tt * 300) + np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 200)
    return norm(x, 0.5)


def whoosh(dur=0.45, up=True):
    tt = t(dur)
    n = rng.standard_normal(len(tt))
    sweep = np.geomspace(300, 5000, len(tt)) if up else np.geomspace(5000, 300, len(tt))
    shape = np.sin(np.pi * tt / dur) ** 2
    return norm(lowpass(n, sweep) * shape, 0.6)


def impact():
    tt = t(0.9)
    boom = np.sin(2 * np.pi * np.cumsum(np.geomspace(120, 38, len(tt))) / SR) * np.exp(-tt * 5)
    crack = lowpass(rng.standard_normal(len(tt)), 3000) * np.exp(-tt * 30)
    return norm(boom + 0.6 * crack, 0.9)


def riser(dur=1.5):
    tt = t(dur)
    n = lowpass(rng.standard_normal(len(tt)), np.geomspace(200, 8000, len(tt)))
    tone = np.sin(2 * np.pi * np.cumsum(np.geomspace(200, 900, len(tt))) / SR) * 0.3
    return norm((n + tone) * (tt / dur) ** 2, 0.6)


def boing():
    tt = t(0.6)
    f = 220 + 140 * np.sin(2 * np.pi * 9 * tt) * np.exp(-tt * 4)
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 5), 0.6)


def ding():
    tt = t(1.0)
    x = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt * d) * g for f, d, g in [(1320, 4, 1), (2640, 7, .4), (3960, 10, .2)])
    return norm(x * env(len(tt), 0.002, 0.2), 0.5)


def page_flip():
    tt = t(0.35)
    n = rng.standard_normal(len(tt))
    flutter = 0.5 + 0.5 * np.sin(2 * np.pi * 28 * tt)
    return norm(lowpass(n, 2500) * flutter * np.sin(np.pi * tt / 0.35), 0.5)


def main():
    OUT.mkdir(exist_ok=True)
    pack = {
        "pop": pop(), "click": click(), "whoosh": whoosh(), "whoosh-out": whoosh(0.35, up=False),
        "impact": impact(), "riser": riser(), "boing": boing(), "ding": ding(), "page-flip": page_flip(),
    }
    for name, x in pack.items():
        sf.write(OUT / f"{name}.wav", np.stack([x, x], 1).astype(np.float32), SR)
        print(name, f"{len(x)/SR:.2f}s")


if __name__ == "__main__":
    main()
