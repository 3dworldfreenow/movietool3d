"""Procedural sound effects + ambient beds, synthesised with numpy.

Any effect can be replaced by a real recording: put  assets/sfx/<name>.wav (or .mp3)
next to main.py and it is used instead of the synthesised version.
Real recordings for the weather (only free / CC0 ones - see assets/sfx/README.md):
  rain*.ogg|mp3|wav|flac    a rain bed, looped, louder and softer with the rain
  wind*.*                   a wind bed, the same way
  thunder*.*                claps of thunder: a different one each time (thunder_1, thunder_2 ...)
Missing files: the synthesised sound is used, as before.
"""
import os

import numpy as np
from scipy.signal import butter, sosfilt

from .audio import decode_audio

SR = 44100


_REAL = {}
REAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sfx")


def real(prefix):
    """the recordings in assets/sfx named <prefix>.* or <prefix>_*.* (mono, decoded once)"""
    if prefix not in _REAL:
        out = []
        if os.path.isdir(REAL_DIR):
            for f in sorted(os.listdir(REAL_DIR)):
                b, ext = os.path.splitext(f)
                if ext.lower() in (".ogg", ".mp3", ".wav", ".flac", ".m4a") and (b == prefix or b.startswith(prefix + "_")):
                    try:
                        a = decode_audio(os.path.join(REAL_DIR, f))
                        if len(a) > SR // 10:
                            out.append(a / (np.abs(a).max() + 1e-6))
                    except Exception:
                        pass
        _REAL[prefix] = out
    return _REAL[prefix]


def _looped(x, n, rng, fade=1.0):
    """a recording laid end to end until n samples, from a random start; each copy fades in and out over `fade`
    seconds and overlaps the next by that much, so the joins are seamless (no click, no gap)"""
    f = int(min(fade * SR, len(x) // 3))
    out = np.zeros(n + len(x), np.float32)
    up, down = np.linspace(0, 1, f, dtype=np.float32), np.linspace(1, 0, f, dtype=np.float32)
    pos, first = 0, True
    while pos < n:
        seg = (x[int(rng.uniform(0, max(1, len(x) - 2 * f))):] if first else x).astype(np.float32).copy()
        if f > 0 and len(seg) > 2 * f:
            if not first:
                seg[:f] *= up
            seg[-f:] *= down
        out[pos:pos + len(seg)] += seg
        pos += max(1, len(seg) - f)
        first = False
    return out[:n]


def _bed(prefix, n, rng, rms=0.1):
    """a real recording as a stereo bed at a steady loudness (two different starts: wide), or None"""
    xs = real(prefix)
    if not xs:
        return None
    x = xs[int(rng.integers(len(xs)))]
    b = np.stack([_looped(x, n, rng), _looped(x, n, rng)])
    return (b * (rms / (np.sqrt(np.mean(b ** 2)) + 1e-6))).astype(np.float32)


def thunder_any(rng):
    """a clap of thunder: one of the real recordings when there are some, else the synthesised one"""
    xs = real("thunder")
    return xs[int(rng.integers(len(xs)))] * 0.9 if xs else thunder(rng)


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _noise(dur, rng):
    return rng.standard_normal(int(dur * SR)).astype(np.float32)


def _filt(x, kind, f, order=2):
    if isinstance(f, (list, tuple)):
        f = [min(max(v, 20), SR / 2 - 100) for v in f]
    else:
        f = min(max(f, 20), SR / 2 - 100)
    sos = butter(order, f, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def _env(n, attack=0.005, decay=0.1):
    t = np.arange(n) / SR
    e = np.exp(-t / max(decay, 1e-4))
    a = int(attack * SR)
    if a > 0:
        e[:a] *= np.linspace(0, 1, a)
    return e.astype(np.float32)


def _norm(x, peak=0.8):
    m = np.abs(x).max()
    return (x * (peak / m)).astype(np.float32) if m > 0 else x.astype(np.float32)


def _sweep(f0, f1, dur, shape="exp"):
    t = _t(dur)
    if shape == "exp":
        f = f0 * (f1 / f0) ** (t / dur)
    else:
        f = f0 + (f1 - f0) * t / dur
    return np.sin(2 * np.pi * np.cumsum(f) / SR).astype(np.float32)


# ------------------------------------------------------------------ one-shots
def footstep(rng, soft=1.0):
    d = 0.12
    n = _filt(_noise(d, rng), "lowpass", rng.uniform(700, 1100)) * _env(int(d * SR), 0.002, 0.025)
    th = np.sin(2 * np.pi * rng.uniform(70, 95) * _t(d)) * _env(int(d * SR), 0.002, 0.03)
    return _norm(n * 0.8 + th * 0.6, 0.55 * soft)


def run_step(rng):
    d = 0.09
    n = _filt(_noise(d, rng), "bandpass", [300, 2200]) * _env(int(d * SR), 0.001, 0.018)
    return _norm(n, 0.55)


def jump(rng):
    d = 0.35
    w = _filt(_noise(d, rng), "bandpass", [600, 2500]) * np.hanning(int(d * SR))
    s = _sweep(260, 720, d) * _env(int(d * SR), 0.01, 0.2) * 0.3
    return _norm(w * 0.6 + s, 0.5)


def land(rng):
    d = 0.3
    th = _sweep(110, 45, d) * _env(int(d * SR), 0.001, 0.07)
    n = _filt(_noise(d, rng), "lowpass", 500) * _env(int(d * SR), 0.001, 0.04)
    return _norm(th + n * 0.5, 0.75)


def thud(rng):
    d = 0.5
    th = _sweep(90, 35, d) * _env(int(d * SR), 0.001, 0.12)
    n = _filt(_noise(d, rng), "lowpass", 350) * _env(int(d * SR), 0.001, 0.08)
    return _norm(th + n * 0.6, 0.9)


def door(rng):
    d = 0.9
    t = _t(d)
    f = 170 + 40 * np.sin(2 * np.pi * 3.1 * t) + 30 * rng.standard_normal(len(t)).cumsum() / np.sqrt(len(t))
    saw = 2 * ((np.cumsum(f) / SR) % 1.0) - 1
    creak = _filt(saw.astype(np.float32), "bandpass", [500, 1800]) * np.hanning(len(t)) ** 0.5
    creak *= 0.6 + 0.4 * (np.sin(2 * np.pi * 11 * t) > 0)
    out = np.zeros(int(1.25 * SR), np.float32)
    out[:len(creak)] += creak * 0.5
    c = thud(rng)[: int(0.4 * SR)]
    out[int(0.85 * SR): int(0.85 * SR) + len(c)] += c * 0.8
    return _norm(out, 0.7)


def knock(rng):
    out = np.zeros(int(0.8 * SR), np.float32)
    for k in range(3):
        d = 0.08
        h = _filt(_noise(d, rng), "bandpass", [250, 900]) * _env(int(d * SR), 0.001, 0.015)
        h += np.sin(2 * np.pi * 180 * _t(d)) * _env(int(d * SR), 0.001, 0.02) * 0.5
        a = int(k * 0.19 * SR)
        out[a:a + len(h)] += h
    return _norm(out, 0.8)


def clap(rng):
    d = 0.18
    n = _filt(_noise(d, rng), "bandpass", [900, 3500]) * _env(int(d * SR), 0.001, 0.02)
    return _norm(n, 0.55)


def whoosh(rng):
    d = 0.5
    x = _noise(d, rng)
    lo = _filt(x, "bandpass", [300, 1200]) * np.linspace(1, 0, len(x))
    hi = _filt(x, "bandpass", [1200, 4500]) * np.linspace(0, 1, len(x))
    return _norm((lo + hi) * np.hanning(len(x)), 0.5)


def pop(rng):
    d = 0.09
    return _norm(_sweep(900, 220, d) * _env(int(d * SR), 0.001, 0.03), 0.6)


def ding(rng, base=880):
    d = 1.6
    t = _t(d)
    x = sum(a * np.sin(2 * np.pi * base * m * t) * np.exp(-t * (2.5 + m)) for m, a in ((1, 1), (2.76, .4), (5.4, .2)))
    return _norm(x.astype(np.float32), 0.55)


def bell(rng):
    return ding(rng, 523)


def tada(rng):
    notes = [523.25, 659.25, 783.99, 1046.5]
    out = np.zeros(int(1.6 * SR), np.float32)
    for i, f in enumerate(notes):
        d = 1.6 - i * 0.1
        t = _t(d)
        saw = sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, 6))
        tone = _filt(saw.astype(np.float32), "lowpass", 3000) * _env(len(t), 0.01, 0.6)
        a = int(i * 0.1 * SR)
        out[a:a + len(tone)] += tone[: len(out) - a]
    return _norm(out, 0.6)


def boing(rng):
    d = 0.7
    t = _t(d)
    f = 180 + 90 * np.exp(-t * 4) * np.sin(2 * np.pi * 14 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, 0.3)
    return _norm(x.astype(np.float32), 0.6)


def splash(rng):
    d = 0.8
    x = _noise(d, rng)
    t = _t(d)
    y = _filt(x, "lowpass", 5000) * np.exp(-t * 5)
    y += _filt(x, "highpass", 3000) * np.exp(-t * 9) * 0.5
    return _norm(y, 0.7)


def crash(rng):
    d = 1.4
    t = _t(d)
    x = _filt(_noise(d, rng), "highpass", 500) * np.exp(-t * 3.5)
    x += sum(np.sin(2 * np.pi * f * t) * np.exp(-t * 4) * 0.15 for f in (412, 587, 889, 1301))
    return _norm(x.astype(np.float32), 0.8)


def thunder(rng):
    d = 3.5
    t = _t(d)
    x = _filt(_noise(d, rng), "lowpass", 180, 3) * (np.exp(-t * 1.2) * (0.6 + 0.4 * np.sin(2 * np.pi * 1.7 * t) ** 2))
    x[: int(0.15 * SR)] += _filt(_noise(0.15, rng), "lowpass", 2000) * np.linspace(1, 0, int(0.15 * SR))
    return _norm(x, 0.9)


def car_horn(rng):
    d = 0.6
    t = _t(d)
    x = np.sign(np.sin(2 * np.pi * 400 * t)) + np.sign(np.sin(2 * np.pi * 500 * t))
    x = _filt(x.astype(np.float32), "lowpass", 2500) * _env(len(t), 0.01, 2.0)
    x[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))
    return _norm(x, 0.5)


def phone(rng):
    out = np.zeros(int(2.2 * SR), np.float32)
    for k in range(2):
        d = 0.8
        t = _t(d)
        x = (np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 480 * t)) * (np.sin(2 * np.pi * 20 * t) > 0)
        a = int(k * 1.2 * SR)
        out[a:a + len(t)] += x.astype(np.float32)
    return _norm(out, 0.45)


def heartbeat(rng):
    out = np.zeros(int(1.0 * SR), np.float32)
    for a, g in ((0.0, 1.0), (0.22, 0.7)):
        d = 0.2
        x = _sweep(70, 40, d) * _env(int(d * SR), 0.005, 0.05) * g
        out[int(a * SR): int(a * SR) + len(x)] += x
    return _norm(out, 0.8)


def magic(rng):
    d = 1.3
    out = np.zeros(int(d * SR), np.float32)
    for k in range(28):
        f = rng.uniform(1500, 4500)
        dd = 0.25
        x = np.sin(2 * np.pi * f * _t(dd)) * _env(int(dd * SR), 0.002, 0.06)
        a = int(rng.uniform(0, d - dd) * SR)
        out[a:a + len(x)] += x * (1 - a / len(out))
    return _norm(out, 0.45)


def snore(rng):
    d = 2.6
    t = _t(d)
    inhale = (t < 1.2) * np.sin(np.pi * np.clip(t / 1.2, 0, 1))
    buzz = np.sign(np.sin(2 * np.pi * 95 * t)) * inhale
    x = _filt(buzz.astype(np.float32) + _noise(d, rng) * 0.3 * inhale, "lowpass", 700)
    exhale = (t > 1.4) * np.sin(np.pi * np.clip((t - 1.4) / 1.1, 0, 1))
    x += _filt(_noise(d, rng), "bandpass", [300, 1500]) * exhale * 0.25
    return _norm(x, 0.35)


def bird(rng):
    out = np.zeros(int(0.9 * SR), np.float32)
    n = rng.integers(2, 5)
    base = rng.uniform(2500, 4200)
    for k in range(n):
        d = rng.uniform(0.05, 0.11)
        x = _sweep(base * rng.uniform(0.9, 1.1), base * rng.uniform(1.2, 1.6), d, "lin") * np.hanning(int(d * SR))
        a = int(k * rng.uniform(0.12, 0.18) * SR)
        if a + len(x) < len(out):
            out[a:a + len(x)] += x
    return _norm(out, 0.35)


def dog_bark(rng):
    out = np.zeros(int(0.7 * SR), np.float32)
    for k in range(2):
        d = 0.16
        t = _t(d)
        f = 480 * np.exp(-t * 6) + 180
        saw = 2 * ((np.cumsum(f) / SR) % 1.0) - 1
        x = _filt(saw.astype(np.float32), "bandpass", [400, 1800]) * _env(len(t), 0.005, 0.06)
        out[int(k * 0.3 * SR): int(k * 0.3 * SR) + len(t)] += x
    return _norm(out, 0.7)


def slip(rng):
    return _norm(_sweep(900, 300, 0.35, "lin") * _env(int(0.35 * SR), 0.005, 0.2), 0.5)


# ------------------------------------------------------------------ animals & machines
def _saw(freqs):
    ph = np.cumsum(freqs) / SR
    return (2 * (ph % 1.0) - 1).astype(np.float32)


def _curve(points, dur):
    """Piecewise-linear frequency curve: [(t_frac, hz), ...]."""
    t = np.linspace(0, 1, int(dur * SR))
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def roar(rng, dur=1.5, base=95):
    f = _curve([(0, base * 0.8), (0.3, base * 1.25), (1, base * 0.7)], dur)
    x = _saw(f) + 0.6 * _filt(_noise(dur, rng), "lowpass", 900)
    x = _filt(x, "bandpass", [120, 1400])
    t = _t(dur)
    am = 0.75 + 0.25 * np.sin(2 * np.pi * 23 * t) * rng.uniform(0.8, 1.2)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.6
    return _norm(x * am * env, 0.9)


def growl(rng):
    return roar(rng, 1.0, 70) * 0.8


def meow(rng):
    dur = 0.75
    f = _curve([(0, 520), (0.35, 820), (1, 430)], dur)
    x = sum(np.sin(2 * np.pi * np.cumsum(f * h) / SR) / h for h in range(1, 6))
    x = _filt(x.astype(np.float32), "bandpass", [500, 3000])
    t = _t(dur)
    return _norm(x * np.sin(np.pi * t / dur) ** 0.7, 0.6)


def moo(rng):
    dur = 1.5
    f = _curve([(0, 105), (0.25, 145), (0.8, 135), (1, 95)], dur)
    x = _filt(_saw(f), "lowpass", 750)
    x = _filt(x, "bandpass", [150, 1100])
    t = _t(dur)
    return _norm(x * np.sin(np.pi * t / dur) ** 0.5, 0.85)


def neigh(rng):
    dur = 1.3
    base = _curve([(0, 700), (0.2, 1300), (0.7, 900), (1, 450)], dur)
    t = _t(dur)
    f = base * (1 + 0.06 * np.sin(2 * np.pi * 14 * t))
    x = sum(np.sin(2 * np.pi * np.cumsum(f * h) / SR) / (h * h) for h in range(1, 5))
    am = 0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 9 * t))
    return _norm((x * am * np.sin(np.pi * t / dur) ** 0.5).astype(np.float32), 0.6)


def bleat(rng):
    dur = 0.7
    t = _t(dur)
    f = 360 * (1 + 0.05 * np.sin(2 * np.pi * 11 * t))
    x = _filt(_saw(f), "bandpass", [600, 2200])
    return _norm(x * np.sin(np.pi * t / dur), 0.6)


def oink(rng):
    out = np.zeros(int(0.7 * SR), np.float32)
    for k in range(2):
        d = 0.18
        f = _curve([(0, 150), (1, 110)], d)
        x = _filt(_saw(f) + _noise(d, rng) * 0.4, "bandpass", [200, 1400]) * np.hanning(int(d * SR))
        a = int(k * 0.26 * SR)
        out[a:a + len(x)] += x
    return _norm(out, 0.7)


def trumpet(rng):
    dur = 1.4
    t = _t(dur)
    f = _curve([(0, 300), (0.25, 540), (0.8, 500), (1, 420)], dur) * (1 + 0.03 * np.sin(2 * np.pi * 7 * t))
    x = _filt(_saw(f), "bandpass", [400, 3500]) + 0.2 * _filt(_noise(dur, rng), "bandpass", [800, 3000])
    return _norm(x * np.sin(np.pi * t / dur) ** 0.4, 0.8)


def howl(rng):
    dur = 2.0
    t = _t(dur)
    f = _curve([(0, 380), (0.3, 720), (0.8, 650), (1, 420)], dur) * (1 + 0.01 * np.sin(2 * np.pi * 5 * t))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    return _norm((x * np.sin(np.pi * t / dur) ** 0.6).astype(np.float32), 0.6)


def caw(rng):
    out = np.zeros(int(0.9 * SR), np.float32)
    for k in range(2):
        d = 0.25
        x = _filt(_saw(_curve([(0, 520), (1, 430)], d)) + _noise(d, rng) * 0.5, "bandpass", [700, 2600])
        x *= np.hanning(len(x))
        a = int(k * 0.38 * SR)
        out[a:a + len(x)] += x
    return _norm(out, 0.6)


def squawk(rng):
    d = 0.4
    x = _filt(_saw(_curve([(0, 1100), (0.5, 1500), (1, 900)], d)) + _noise(d, rng) * 0.6, "bandpass", [900, 4000])
    return _norm(x * np.hanning(len(x)), 0.55)


def cluck(rng):
    out = np.zeros(int(0.8 * SR), np.float32)
    for k in range(3):
        d = 0.09
        x = _filt(_saw(_curve([(0, 480), (1, 380)], d)), "bandpass", [500, 1800]) * np.hanning(int(d * SR))
        a = int(k * 0.17 * SR)
        out[a:a + len(x)] += x
    return _norm(out, 0.55)


def quack(rng):
    out = np.zeros(int(0.7 * SR), np.float32)
    for k in range(2):
        d = 0.2
        x = _filt(_saw(_curve([(0, 480), (1, 380)], d)), "bandpass", [700, 1600]) * np.hanning(int(d * SR))
        a = int(k * 0.3 * SR)
        out[a:a + len(x)] += x
    return _norm(out, 0.6)


def screech(rng):
    d = 0.9
    x = _filt(_saw(_curve([(0, 2200), (0.3, 2600), (1, 1500)], d)) + _noise(d, rng) * 0.4, "bandpass", [1500, 5000])
    return _norm(x * np.hanning(len(x)), 0.45)


def flap(rng):
    out = np.zeros(int(0.8 * SR), np.float32)
    for k in range(5):
        d = 0.07
        x = _filt(_noise(d, rng), "lowpass", 900) * _env(int(d * SR), 0.005, 0.02)
        a = int(k * 0.13 * SR)
        out[a:a + len(x)] += x
    return _norm(out, 0.45)


def paw(rng):
    return footstep(rng, 0.45)


def hoof(rng):
    d = 0.12
    x = _filt(_noise(d, rng), "bandpass", [500, 1600]) * _env(int(d * SR), 0.001, 0.02)
    x += np.sin(2 * np.pi * rng.uniform(600, 800) * _t(d)) * _env(int(d * SR), 0.001, 0.025) * 0.6
    return _norm(x, 0.5)


def stomp(rng):
    return thud(rng) * 0.9


def engine(rng):
    dur = 2.0
    t = _t(dur)
    f = 48 + 3 * np.sin(2 * np.pi * 0.5 * t)
    x = _saw(f) + 0.5 * _saw(f * 2.01)
    x = _filt(x, "lowpass", 380) * (0.8 + 0.2 * np.sin(2 * np.pi * 22 * t))
    return _norm(x, 0.5)


def hail(rng):
    """hail on a tin roof and the ground: hundreds of hard little clicks (ice hitting at ~10 m/s), loud and fast"""
    dur = 4.0
    out = np.zeros(int(dur * SR), np.float32)
    for _ in range(900):
        k = int(rng.uniform(0, dur - 0.05) * SR)
        n = int(0.012 * SR)
        click = _filt(_noise(0.012, rng), "highpass", rng.uniform(1800, 4500)) * np.exp(-np.arange(n) / (0.002 * SR))
        out[k:k + n] += click[:len(out[k:k + n])] * rng.uniform(0.2, 1.0)
    return _norm(out + _filt(_noise(dur, rng), "bandpass", [600, 3000]) * 0.15, 0.7)


def zap(rng):
    """an electric spark: a crackling burst (a short arc: broadband noise chopped into fast pulses)"""
    dur = 0.7
    t = _t(dur)
    gate = (rng.random(len(t)) < 0.08).astype(np.float32)
    gate = np.convolve(gate, np.ones(60) / 6, mode="same")
    x = _filt(_noise(dur, rng), "highpass", 1200) * gate * np.exp(-t * 4)
    x += np.sin(2 * np.pi * 120 * t) * 0.25 * np.exp(-t * 6)                     # the mains hum of the arc
    return _norm(x, 0.8)


def boom(rng):
    """an explosion: a sharp crack, then the low rolling boom of the pressure wave and debris falling"""
    dur = 2.5
    t = _t(dur)
    low = _filt(_noise(dur, rng), "lowpass", 180) * np.exp(-t * 1.6) * 2.2
    crack = _filt(_noise(dur, rng), "highpass", 900) * np.exp(-t * 18)
    out = low + crack
    deb = crash(rng)[: int(1.2 * SR)] * 0.4
    k = int(0.5 * SR)
    out[k:k + len(deb)] += deb[: len(out) - k]
    return _norm(out, 0.95)


def car_door(rng):
    """a car door shut: the latch click, the thump of the panel (a steel box resonating low) and a short ring"""
    out = np.zeros(int(0.6 * SR), np.float32)
    c = _filt(_noise(0.02, rng), "highpass", 2500) * _env(int(0.02 * SR), 0.001, 0.01)
    out[:len(c)] += c * 0.5
    t = _t(0.35)
    body = np.sin(2 * np.pi * (78 + 30 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
    ring = np.sin(2 * np.pi * 410 * t) * np.exp(-t * 26) * 0.18
    k = int(0.012 * SR)
    out[k:k + len(t)] += (body + ring + _filt(_noise(0.35, rng), "lowpass", 600) * np.exp(-t * 30) * 0.5)
    return _norm(out, 0.85)


def siren(rng):
    """a police siren: the two-tone wail (a horn swept between ~650 and ~1300 Hz, about once a second)"""
    dur = 4.0
    t = _t(dur)
    f = 950 + 330 * np.sin(2 * np.pi * 0.55 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
    x = _filt(x.astype(np.float32), "bandpass", [400, 3500])
    return _norm(x, 0.45)


def rocket(rng):
    dur = 4.0
    t = _t(dur)
    x = _filt(_noise(dur, rng), "lowpass", 600, 3) * np.clip(t / 0.8, 0, 1)
    x += 0.5 * _filt(_noise(dur, rng), "bandpass", [800, 3000]) * np.clip(t / 1.2, 0, 1)
    return _norm(x, 0.85)


def firework(rng):
    """A rocket: a rising whistle, the boom of the burst, then crackles."""
    up = 1.0
    d = up + 2.2
    x = np.zeros(int(d * SR), np.float32)
    w = _sweep(rng.uniform(900, 1200), rng.uniform(2200, 2800), up) * np.linspace(0.15, 0.35, int(up * SR))
    w += 0.15 * _filt(_noise(up, rng), "highpass", 3000) * np.linspace(0.2, 1.0, int(up * SR))
    x[: len(w)] += w
    b0 = int(up * SR)
    bd = 1.4
    tb = _t(bd)
    boom = _filt(_noise(bd, rng), "lowpass", 220, 3) * np.exp(-tb * 3.0) * 2.2
    boom += _filt(_noise(bd, rng), "bandpass", [400, 2500]) * np.exp(-tb * 9.0) * 0.6
    x[b0:b0 + len(boom)] += boom[: len(x) - b0]
    for _ in range(26):                                  # the crackle
        p = b0 + int(rng.uniform(0.25, 1.9) * SR)
        n = int(0.012 * SR)
        if p + n < len(x):
            x[p:p + n] += _filt(_noise(0.012, rng), "highpass", 2500) * _env(n, 0.0005, 0.004) * rng.uniform(0.2, 0.5)
    return _norm(x, 0.85)


def fizz(rng):
    """A sparkler / fountain cracker hissing."""
    d = 2.5
    t = _t(d)
    x = _filt(_noise(d, rng), "bandpass", [2500, 9000]) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * t) ** 2)
    x *= np.clip(t / 0.15, 0, 1) * np.clip((d - t) / 0.4, 0, 1)
    return _norm(x, 0.45)


def crackle(rng):
    d = 0.8
    x = np.zeros(int(d * SR), np.float32)
    for _ in range(18):
        p = int(rng.uniform(0, d - 0.02) * SR)
        n = int(0.01 * SR)
        x[p:p + n] += _filt(_noise(0.01, rng), "highpass", 2000) * _env(n, 0.0005, 0.003)
    return _norm(x, 0.6)


def fan_hum(rng):
    dur = 2.0
    t = _t(dur)
    x = 0.4 * np.sin(2 * np.pi * 120 * t) + _filt(_noise(dur, rng), "bandpass", [200, 900]) * 0.6
    return _norm(x.astype(np.float32) * (0.9 + 0.1 * np.sin(2 * np.pi * 4.4 * t)), 0.25)



def scrape(rng):
    """Something heavy dragged / pushed over the ground (loopable)."""
    d = 1.0
    t = _t(d)
    x = _filt(_noise(d, rng), "bandpass", [180, 1400])
    grain = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 7.3 * t + 2 * np.sin(2 * np.pi * 1.7 * t)))
    return _norm((x * grain).astype(np.float32), 0.5)


def rumble(rng):
    """A big rock rolling (loopable)."""
    d = 1.0
    t = _t(d)
    x = _filt(_noise(d, rng), "lowpass", 220) * (0.7 + 0.3 * np.sin(2 * np.pi * 3.0 * t))
    x += _filt(_noise(d, rng), "bandpass", [300, 900]) * 0.25 * (np.sin(2 * np.pi * 6.0 * t) > 0.6)
    return _norm(x.astype(np.float32), 0.6)


def creak(rng):
    """A lid / old wooden thing opening."""
    d = 0.8
    t = _t(d)
    f = 240 + 70 * np.sin(2 * np.pi * 2.3 * t) + 25 * rng.standard_normal(len(t)).cumsum() / np.sqrt(len(t))
    saw = 2 * ((np.cumsum(f) / SR) % 1.0) - 1
    c = _filt(saw.astype(np.float32), "bandpass", [600, 2200]) * np.hanning(len(t)) ** 0.5
    c *= 0.6 + 0.4 * (np.sin(2 * np.pi * 13 * t) > 0)
    return _norm(c.astype(np.float32), 0.55)


def plop(rng):
    """A small stone dropping into water."""
    d = 0.5
    t = _t(d)
    f = 900 * np.exp(-t * 18) + 250
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
    n = _filt(_noise(d, rng), "highpass", 2500) * np.exp(-t * 20) * 0.4
    return _norm((tone + n).astype(np.float32), 0.7)


def clang(rng):
    """Metal hitting the ground: a bright ring that dies away (a bucket, a pan, a sword)."""
    d = 1.2
    t = _t(d)
    x = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * k) * a for f, k, a in
            ((523, 4.5, 0.5), (1187, 6.0, 0.35), (1931, 8.0, 0.25), (2873, 11.0, 0.15)))
    x += _filt(_noise(d, rng), "highpass", 3000) * np.exp(-t * 40) * 0.5
    return _norm(x.astype(np.float32), 0.75)


def sack(rng):
    """A heavy soft sack (grain, sand) landing: a deep dull thump and a little grainy shuffle, no bounce."""
    d = 0.6
    t = _t(d)
    th = _sweep(70, 30, d) * np.exp(-t * 14)
    n = _filt(_noise(d, rng), "lowpass", 600) * np.exp(-t * 9) * 0.5
    grain = _filt(_noise(d, rng), "bandpass", [1500, 4000]) * np.exp(-t * 12) * 0.12
    return _norm((th + n + grain).astype(np.float32), 0.9)


def rustle(rng):
    """A leaf / paper touching down: a soft dry rustle."""
    d = 0.35
    t = _t(d)
    x = _filt(_noise(d, rng), "bandpass", [2000, 7000]) * np.sin(np.pi * t / d) ** 2
    return _norm(x.astype(np.float32), 0.35)


def gulp(rng):
    """Two swallows."""
    out = np.zeros(int(0.7 * SR), np.float32)
    for k, st in enumerate((0.05, 0.38)):
        d = 0.16
        t = _t(d)
        f = 180 + 260 * np.sin(np.pi * t / d)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.hanning(len(t)) * (1 - 0.3 * k)
        i = int(st * SR)
        out[i:i + len(x)] += x.astype(np.float32)
    return _norm(_filt(out, "lowpass", 900), 0.5)


def crunch(rng):
    """A bite: short crackly bursts."""
    out = np.zeros(int(0.45 * SR), np.float32)
    for k in range(4):
        d = 0.05
        n = _filt(_noise(d, rng), "bandpass", [1500, 6000]) * _env(int(d * SR), 0.001, 0.02)
        i = int((0.02 + k * 0.07 + rng.uniform(0, 0.02)) * SR)
        out[i:i + len(n)] += n[: len(out) - i]
    return _norm(out, 0.45)


def hoot(rng):
    """Owl: hoo-hoo."""
    out = np.zeros(int(1.0 * SR), np.float32)
    for st, d in ((0.0, 0.28), (0.4, 0.45)):
        t = _t(d)
        x = np.sin(2 * np.pi * (380 - 40 * t / d) * t) * np.hanning(len(t))
        i = int(st * SR)
        out[i:i + len(x)] += x.astype(np.float32)
    return _norm(out, 0.5)


def coo(rng):
    """Pigeon: a soft rolling coo."""
    d = 0.9
    t = _t(d)
    f = 300 + 60 * np.sin(2 * np.pi * 1.6 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t)) * np.hanning(len(t))
    return _norm(_filt(x.astype(np.float32), "lowpass", 900), 0.45)


def punch(rng):
    d = 0.35
    th = _sweep(160, 50, d) * _env(int(d * SR), 0.001, 0.06)
    n = _filt(_noise(d, rng), "bandpass", [200, 2500]) * _env(int(d * SR), 0.001, 0.03)
    return _norm(th + n * 0.8, 0.85)


def kiss(rng):
    """💋 a kiss: a soft wet smack (a short breathy burst with a little pitched pop)."""
    d = 0.18
    n = _filt(_noise(d, rng), "bandpass", [900, 4000]) * _env(int(d * SR), 0.002, 0.04)
    pp = _sweep(1400, 600, d) * _env(int(d * SR), 0.001, 0.03)
    return _norm((n * 0.7 + pp * 0.5).astype(np.float32), 0.45)


def slap(rng):
    """👋 a slap: a sharp bright crack of skin on skin with a little low thump."""
    d = 0.25
    n = _filt(_noise(d, rng), "bandpass", [1200, 7000]) * _env(int(d * SR), 0.0005, 0.025)
    th = _sweep(220, 90, d) * _env(int(d * SR), 0.001, 0.04)
    return _norm((n + th * 0.35).astype(np.float32), 0.9)


def rotor(rng, dur=4.0):
    """a helicopter overhead: the blade "whop" (each blade's tip vortex slapping the air, ~4 blades x 4.8 turns a
    second = ~19 a second, heard as a throb) over the turbine's whine and the downwash roar"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = _filt(rng.standard_normal(n).astype(np.float32), "lowpass", 380)
    beat = 0.5 + 0.5 * np.cos(2 * np.pi * 19.2 * t)
    whop = noise * beat ** 6 * 2.2
    whine = 0.05 * np.sin(2 * np.pi * (2300 + 15 * np.sin(2 * np.pi * 0.3 * t)) * t)
    wash = _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [150, 1200]) * 0.25
    return _norm(whop + whine + wash, 0.7)


def scream(rng, base=None):
    """a person's scream / shout of fear: a buzzy voice (a saw wave) rising then falling, through two mouth
    formants (~900 and ~1800 Hz: an "aah"), with a shake in it"""
    f0 = base or rng.uniform(260, 620)
    dur = rng.uniform(0.5, 1.1)
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = t / dur
    f = f0 * (1 + 0.35 * np.sin(np.pi * u ** 0.7)) * (1 + 0.025 * np.sin(2 * np.pi * 7 * t))
    ph = np.cumsum(f) / SR
    saw = (2 * (ph % 1.0) - 1).astype(np.float32)
    v = _filt(saw, "bandpass", [700, 1100]) + 0.6 * _filt(saw, "bandpass", [1500, 2300])
    v = v + 0.15 * _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [2000, 5000])
    return _norm(v * _env(n, 0.04, dur * 0.5), 0.6)


def panic(rng, dur=5.0):
    """a street in panic, heard from across the road: people shouting and screaming here and there"""
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    k = rng.uniform(0, 0.4)
    while k < dur - 0.3:
        s = scream(rng) * rng.uniform(0.25, 0.7)
        a = int(k * SR)
        m = min(len(s), n - a)
        out[a:a + m] += s[:m]
        k += rng.uniform(0.25, 0.9)
    return _norm(out, 0.6)


def static(rng, dur=1.6):
    """a TV feed lost: hard white noise"""
    n = int(dur * SR)
    x = rng.standard_normal(n).astype(np.float32)
    return _norm(x * _env(n, 0.005, dur * 0.4), 0.5)


def jet(rng, dur=5.0):
    """a jet's engines: the turbine whine (a high tone that rises as it spools up) over the roar of the exhaust"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    whine = 0.12 * np.sin(2 * np.pi * np.cumsum(2600 + 1400 * u) / SR)
    roar = _filt(rng.standard_normal(n).astype(np.float32), "lowpass", 500) * (0.4 + 0.6 * u)
    hiss = _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [2000, 6000]) * 0.15
    return _norm(whine + roar + hiss, 0.7)


def murmur(rng, dur=5.0):
    """a hall full of people talking low: many voices' syllables (bursts of voiced noise through vowel formants),
    none of them words"""
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    k = 0.0
    while k < dur - 0.2:
        d = rng.uniform(0.08, 0.22)
        m = int(d * SR)
        f1 = rng.uniform(350, 800)
        syl = _filt(rng.standard_normal(m).astype(np.float32), "bandpass", [f1, f1 * 2.4]) * _env(m, 0.02, d * 0.5)
        a = int(k * SR)
        out[a:a + m] += syl[: max(0, min(m, n - a))] * rng.uniform(0.2, 0.6)
        k += rng.uniform(0.01, 0.06)
    return _norm(_filt(out, "lowpass", 2500), 0.5)


def whispers(rng, dur=4.0):
    """people whispering: breathy "s" and "sh" sounds and soft half-words, here and there"""
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    k = rng.uniform(0, 0.3)
    while k < dur - 0.3:
        d = rng.uniform(0.15, 0.45)
        m = int(d * SR)
        lo = rng.choice([2500, 3500, 1800])
        s_ = _filt(rng.standard_normal(m).astype(np.float32), "bandpass", [lo, lo * 2.2]) * _env(m, 0.03, d * 0.6)
        a = int(k * SR)
        out[a:a + m] += s_[: max(0, min(m, n - a))] * rng.uniform(0.3, 0.8)
        k += rng.uniform(0.1, 0.5)
    return _norm(out, 0.45)


SFX = {
    "kiss": kiss, "smooch": kiss, "muah": kiss, "slap": slap, "thappad": slap,
    "gulp": gulp, "drink": gulp, "swallow": gulp, "crunch": crunch, "bite": crunch, "eat": crunch,
    "punch": punch, "hit": punch, "smack": punch, "hoot": hoot, "owl": hoot, "coo": coo, "pigeon": coo,
    "footstep": footstep, "footsteps": footstep, "step": footstep, "run_step": run_step, "running": run_step,
    "jump": jump, "land": land, "thud": thud, "fall": thud, "door": door, "door_open": door,
    "door_close": thud, "knock": knock, "clap": clap, "applause": clap, "whoosh": whoosh, "swoosh": whoosh,
    "pop": pop, "ding": ding, "bell": bell, "tada": tada, "success": tada, "boing": boing, "splash": splash,
    "crash": crash, "thunder": thunder_any, "car_horn": car_horn, "horn": car_horn, "phone": phone,
    "ring": phone, "heartbeat": heartbeat, "magic": magic, "sparkle": magic, "snore": snore,
    "bird": bird, "birds": bird, "dog": dog_bark, "bark": dog_bark, "slip": slip,
    "chirp": bird, "tweet": bird, "sing": bird, "roar": roar, "growl": growl, "meow": meow, "cat": meow,
    "moo": moo, "cow": moo, "neigh": neigh, "horse": neigh, "bleat": bleat, "goat": bleat, "oink": oink,
    "trumpet": trumpet, "elephant": trumpet, "howl": howl, "wolf": howl, "caw": caw, "crow": caw,
    "squawk": squawk, "parrot": squawk, "cluck": cluck, "hen": cluck, "quack": quack, "duck": quack,
    "screech": screech, "eagle": screech, "flap": flap, "wings": flap, "paw": paw, "hoof": hoof,
    "stomp": stomp, "car_door": car_door, "siren": siren, "hail": hail, "zap": zap, "boom": boom, "explosion": boom, "engine": engine, "car": engine, "rocket": rocket, "launch": rocket, "fan": fan_hum,
    "lion": roar, "tiger": roar,
    "firework": firework, "fireworks": firework, "patakha": firework, "fizz": fizz, "sparkler": fizz,
    "hiss": fizz, "crackle": crackle,
    "clang": clang, "metal": clang, "sack": sack, "bag_thud": sack, "rustle": rustle, "leaves": rustle,
    "murmur": murmur, "crowd": murmur, "hubbub": murmur, "whispers": whispers, "whisper": whispers,
    "jet": jet, "plane": jet, "rotor": rotor, "helicopter": rotor, "chopper": rotor, "scream": scream, "shout": scream,
    "panic": panic, "crowd_panic": panic, "static": static, "no_signal": static,
    "scrape": scrape, "drag": scrape, "rumble": rumble, "roll": rumble, "creak": creak, "plop": plop,
}


class SfxBank:
    def __init__(self, asset_dir="assets/sfx", warn=print, seed=1):
        self.asset_dir = asset_dir
        self.warn = warn
        self.rng = np.random.default_rng(seed)
        self._files = {}
        self._warned = set()

    def get(self, name):
        key = str(name).lower().strip().replace(" ", "_")
        takes = []                                   # <key>.<ext> and its other takes <key>_2.<ext> ...: one at random
        if os.path.isdir(self.asset_dir):
            for f in sorted(os.listdir(self.asset_dir)):
                b, ext = os.path.splitext(f)
                if ext.lower() in (".wav", ".mp3", ".ogg", ".flac", ".m4a") and \
                        (b == key or (b.startswith(key + "_") and b[len(key) + 1:].isdigit())):
                    takes.append(os.path.join(self.asset_dir, f))
        if takes:
            p = takes[int(self.rng.integers(len(takes)))]
            if p not in self._files:
                self._files[p] = decode_audio(p)
            return self._files[p]
        if os.path.exists(str(name)) and os.path.isfile(str(name)):
            return decode_audio(str(name))
        fn = SFX.get(key)
        if fn is None:
            import difflib
            close = difflib.get_close_matches(key, list(SFX), n=1, cutoff=0.6)
            if close:
                fn = SFX[close[0]]
            elif key not in self._warned:
                self._warned.add(key)
                self.warn(f"unknown sound effect '{name}' (add assets/sfx/{key}.wav to use your own)")
                return None
        return fn(self.rng) if fn else None


# ------------------------------------------------------------------ ambient beds
def ambient(kind, dur, seed=0):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    out = np.zeros((2, n), np.float32)
    t = np.arange(n) / SR
    kind = str(kind).lower()

    def add_events(fn, rate, gain):
        k = rng.uniform(0.3, 1.5)
        while k < dur - 0.5:
            s = fn(rng) * gain
            pan = rng.uniform(-0.8, 0.8)
            a = int(k * SR)
            m = min(len(s), n - a)
            out[0, a:a + m] += s[:m] * (1 - pan) / 2
            out[1, a:a + m] += s[:m] * (1 + pan) / 2
            k += rng.exponential(1.0 / rate) + 0.3

    if kind in ("birds", "park", "morning", "village"):
        add_events(bird, 0.55, 0.55)
        w = _filt(rng.standard_normal(n).astype(np.float32), "lowpass", 300) * 0.05
        out += w
    elif kind == "forest":
        add_events(bird, 0.8, 0.6)
        w = _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [150, 900])
        out += w * (0.05 + 0.04 * np.sin(2 * np.pi * t / 7.0))
    elif kind in ("wind", "mountains", "snow"):
        for ch in range(2):
            w = _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [120, 700])
            out[ch] += w * (0.12 + 0.1 * np.sin(2 * np.pi * t / (6.0 + ch) + ch)) * 1.4
    elif kind in ("night", "crickets"):
        for k in range(3):
            f = rng.uniform(4200, 5200)
            gate = (np.sin(2 * np.pi * 28 * t + k) > 0.3) * (np.sin(2 * np.pi * rng.uniform(0.6, 1.1) * t + k * 2) > 0)
            sig = np.sin(2 * np.pi * f * t) * gate * 0.05
            out[k % 2] += sig.astype(np.float32)
    elif kind in ("city", "street", "traffic"):
        r = _filt(rng.standard_normal(n).astype(np.float32), "lowpass", 220) * 0.35
        out += r
        add_events(whoosh, 0.2, 0.35)
        add_events(car_horn, 0.03, 0.12)
    elif kind in ("rain", "storm"):
        rb = _bed("rain", n, rng, 0.13)                  # a real rain recording when there is one
        for ch in range(2):
            out[ch] += rb[ch] if rb is not None else \
                _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [900, 7000]) * 0.13
        if kind == "storm":
            add_events(thunder_any, 0.08, 0.8)
    elif kind in ("sea", "waves", "beach"):
        swell = 0.5 + 0.5 * np.sin(2 * np.pi * t / 7.5)
        for ch in range(2):
            out[ch] += _filt(rng.standard_normal(n).astype(np.float32), "lowpass", 900) * 0.25 * swell ** 2
        add_events(bird, 0.1, 0.3)
    elif kind == "jungle":
        add_events(bird, 1.0, 0.6)
        add_events(squawk, 0.08, 0.35)
        buzz = np.sin(2 * np.pi * 3800 * t) * (np.sin(2 * np.pi * 45 * t) > 0.2) * 0.03
        out += buzz.astype(np.float32)
        out += _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [150, 700]) * 0.05
    elif kind in ("cyclone", "hurricane", "tornado"):
        for ch in range(2):
            w = _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [80, 900])
            out[ch] += w * (0.45 + 0.25 * np.sin(2 * np.pi * t / (3.0 + ch)))
            out[ch] += _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [900, 7000]) * 0.12
        add_events(thunder_any, 0.1, 0.8)
    elif kind == "space":
        drone = 0.08 * np.sin(2 * np.pi * 55 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 9)) + \
                0.05 * np.sin(2 * np.pi * 82.4 * t + np.sin(2 * np.pi * 0.2 * t))
        out += drone.astype(np.float32)
    elif kind in ("river", "water", "stream"):
        for ch in range(2):
            b = _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [400, 2500])
            mod = np.abs(_filt(rng.standard_normal(n).astype(np.float32), "lowpass", 6))
            out[ch] += b * 0.12 * (0.4 + mod / (mod.max() + 1e-6))
        add_events(bird, 0.3, 0.45)
    elif kind in ("market", "crowd", "bazaar"):
        for ch in range(2):
            b = _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [250, 1400])
            mod = np.abs(_filt(rng.standard_normal(n).astype(np.float32), "lowpass", 3))
            out[ch] += b * 0.2 * (0.5 + mod / (mod.max() + 1e-6))
        add_events(bell, 0.05, 0.15)
    elif kind == "farm":
        add_events(bird, 0.4, 0.5)
        add_events(moo, 0.04, 0.3)
        add_events(cluck, 0.06, 0.3)
    elif kind == "fan":
        hum = fan_hum(rng)
        reps = int(np.ceil(n / len(hum)))
        out += np.tile(hum, reps)[:n] * 0.6
    elif kind in ("room", "indoor", "classroom"):
        out += _filt(rng.standard_normal(n).astype(np.float32), "lowpass", 180) * 0.02
    # fade edges
    f = min(int(0.8 * SR), n // 2)
    if f > 0:
        out[:, :f] *= np.linspace(0, 1, f)
        out[:, -f:] *= np.linspace(1, 0, f)
    return out


def weather_bed(sc, bg, t0, dur, seed=0):
    """Sound of weather that changes during a scene (engine/weatherline.py), stereo: wind that rises and falls,
    the rain from the first few drops to a downpour and back, thunder in a storm, drips after the rain."""
    from . import weatherline
    rng = np.random.default_rng(seed + 17)
    n = int(dur * SR)
    if n <= 0:
        return None
    out = np.zeros((2, n), np.float32)
    step = 0.1
    ts = np.arange(0.0, dur + step, step)
    lv = [weatherline.state(sc, bg, t0 + t) for t in ts]
    tt = np.arange(n) / SR

    def env(key, f=lambda v: v):
        return np.interp(tt, ts, np.array([f(x[key]) for x in lv], np.float32)).astype(np.float32)
    rain = env("rain")
    wind = env("wind", lambda v: max(0.0, v - 0.6) / 3.0)
    drips = env("drips")
    if rain.max() > 0.01:
        heavy = rain ** 1.4
        rb = _bed("rain", n, rng, 0.14)                  # a real rain recording when there is one
        for ch in range(2):
            hiss = rb[ch] if rb is not None else \
                _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [900, 7000]) * 0.14
            out[ch] += hiss * heavy
        k = 0.0                                          # single drops (patter): many at first, lost in the hiss later
        while k < dur:
            r = float(np.interp(k, ts, [x["rain"] for x in lv]))
            if r > 0.03:
                d = _filt(_noise(0.03, rng), "bandpass", [2000, 6000]) * _env(int(0.03 * SR), 0.001, 0.008)
                a = int(k * SR)
                m = min(len(d), n - a)
                pan = rng.uniform(-0.9, 0.9)
                g = 0.25 * min(1.0, r * 2.0)
                out[0, a:a + m] += d[:m] * g * (1 - pan) / 2
                out[1, a:a + m] += d[:m] * g * (1 + pan) / 2
            k += 1.0 / (6.0 + 60.0 * r) if r > 0.03 else 0.25
    if wind.max() > 0.01:
        wb = _bed("wind", n, rng, 0.25)                  # a real wind recording when there is one
        for ch in range(2):
            w = wb[ch] if wb is not None else _filt(rng.standard_normal(n).astype(np.float32), "bandpass", [120, 700])
            out[ch] += w * wind * (0.25 + 0.1 * np.sin(2 * np.pi * tt / (5.0 + ch))) * (4.0 if wb is not None else 1.0)
    if drips.max() > 0.02:                               # after the rain: drips from roofs and leaves
        k = 0.2
        while k < dur:
            dv = float(np.interp(k, ts, [x["drips"] for x in lv]))
            if dv > 0.02 and rng.random() < dv:
                s = plop(rng) * 0.18 * dv
                a = int(k * SR)
                m = min(len(s), n - a)
                pan = rng.uniform(-0.8, 0.8)
                out[0, a:a + m] += s[:m] * (1 - pan) / 2
                out[1, a:a + m] += s[:m] * (1 + pan) / 2
            k += rng.uniform(0.15, 0.6)
    return out


def default_ambient(bg, place_only=False):
    """The background sound of a place; place_only = without the weather (the weather has its own track)."""
    if place_only:
        w = bg.weather
        bg.weather = "clear"
        try:
            return default_ambient(bg)
        finally:
            bg.weather = w
    if bg.weather in ("rain", "storm"):
        return bg.weather
    if bg.weather in ("windy", "wind"):
        return "wind"
    if bg.night and not bg.indoor:
        return "night"
    if bg.weather == "cyclone":
        return "cyclone"
    base = {"park": "birds", "village": "birds", "street": "city", "forest": "forest", "mountains": "wind",
            "beach": "waves", "snow": "wind", "desert": "wind", "room": "room", "classroom": "room",
            "plain": "birds", "river": "river", "jungle": "jungle", "space": "space", "kitchen": "room",
            "bedroom": "room", "road": "city", "market": "market", "farm": "farm"}.get(bg.preset, "none")
    if any(e["type"] == "fan" and e.get("on", True) for e in bg.elements):
        return [base, "fan"]
    return base
