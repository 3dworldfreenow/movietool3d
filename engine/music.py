"""Procedural background music by mood. 100% synthesised => no copyright issues on YouTube.

Moods: happy, calm, sad, tense, adventure, funny, mystery, romantic (+ aliases).
You can also point "music" at your own file (mp3/wav) instead of a mood.

Plucked strings are real Karplus-Strong strings (Python Playground ch. 4): a short burst of noise goes round a
delay line one period long and is averaged as it goes, so it rings and fades exactly like a plucked string.

Indian music: "music": "raga_calm" (or any mood with "music_style": "indian" in the settings) plays a raga on
sitar (with the jawari buzz and meend slides), santoor (hammered, shimmering) and a tanpura drone, with a soft
tabla theka - the raga matches the mood:
    calm / romantic  Yaman (evening)       happy  Bhupali / Desh       sad  Bhairavi       morning  Bhairav
    mystery / tense  Malkauns (night)      funny / festival  Kafi (Holi)                adventure  Durga
"""
import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100

MOODS = {
    #            bpm, root midi, progression [(semitones, quality)], style
    "happy":     (108, 60, [(0, "maj"), (7, "maj"), (9, "min"), (5, "maj")], "pop"),
    "calm":      (76, 65, [(0, "maj"), (9, "min"), (5, "maj"), (7, "maj")], "soft"),
    "sad":       (66, 57, [(0, "min"), (8, "maj"), (3, "maj"), (10, "maj")], "piano"),
    "tense":     (94, 50, [(0, "min"), (0, "min"), (8, "maj"), (7, "maj")], "pulse"),
    "adventure": (122, 62, [(0, "maj"), (10, "maj"), (5, "maj"), (0, "maj")], "drive"),
    "funny":     (132, 60, [(0, "maj"), (9, "min"), (2, "min"), (7, "maj")], "bounce"),
    "mystery":   (62, 52, [(0, "min"), (5, "min"), (0, "min"), (7, "maj")], "bells"),
    "romantic":  (72, 67, [(0, "maj"), (4, "min"), (5, "maj"), (7, "maj")], "soft"),
}
ALIASES = {"cheerful": "happy", "joyful": "happy", "upbeat": "happy", "peaceful": "calm", "relaxed": "calm",
           "gentle": "calm", "emotional": "sad", "melancholy": "sad", "scary": "tense", "horror": "tense",
           "suspense": "tense", "action": "adventure", "epic": "adventure", "heroic": "adventure",
           "comedy": "funny", "playful": "funny", "night": "mystery", "magical": "mystery", "love": "romantic"}


def resolve_mood(m):
    m = str(m or "").lower().strip()
    if m.startswith("raga") or m in RAGA_MOODS:
        return m
    m = ALIASES.get(m, m)
    return m if m in MOODS else None


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def _lp(x, f):
    return sosfilt(butter(2, min(f, SR / 2 - 100), "lowpass", fs=SR, output="sos"), x).astype(np.float32)


def _adsr(n, a, d, s, r):
    e = np.full(n, s, np.float32)
    A, D, R = int(a * SR), int(d * SR), int(r * SR)
    A = min(A, n)
    e[:A] = np.linspace(0, 1, A) if A else e[:A]
    D = min(D, n - A)
    if D > 0:
        e[A:A + D] = np.linspace(1, s, D)
    R = min(R, n)
    if R > 0:
        e[-R:] *= np.linspace(1, 0, R)
    return e


_KS = {}


def ks(f, dur, decay=0.996, bright=1.0, seed=0, burst=None):
    """Karplus-Strong plucked string: a noise burst circulating in a delay line of one period, averaged each pass
    (the averaging is the string losing its high harmonics first). decay < 1 = how fast it dies. Vectorised one
    period at a time; tuned exactly by resampling the integer-length loop."""
    key = (round(f, 2), round(dur, 3), round(decay, 5), round(bright, 2), seed, burst)
    got = _KS.get(key)
    if got is not None:
        return got
    n = int(dur * SR)
    N = max(2, int(SR / f))
    rng = np.random.default_rng(seed + int(f * 10))
    ph = np.arange(N) / N                                # where the finger plucks (1/5 along): a triangle
    tri = np.where(ph < 0.2, ph / 0.2, (1.0 - ph) / 0.8)
    buf = 0.65 * (tri - tri.mean()) * 2.0 + 0.35 * rng.uniform(-1.0, 1.0, N)
    if bright < 1.0:                                     # a softer pluck: smooth the burst (fewer high partials)
        k = max(1, int((1.0 - bright) * 6))
        buf = np.convolve(buf, np.ones(k) / k, mode="same")
    if burst is not None:                                # a hammer (santoor): short burst, then silence
        L = max(2, int(N * burst))
        buf[L:] *= 0.15
    buf -= buf.mean()
    total = int(n * f * (N + 0.5) / SR) + N + 2         # samples needed at the loop's own pitch
    out = np.empty(total, np.float64)
    out[:N] = buf
    prev_last = buf[-1]
    i = N
    while i < total:
        blk = out[i - N:i]
        nxt = decay * 0.5 * (blk + np.concatenate(([prev_last], blk[:-1])))
        m = min(N, total - i)
        out[i:i + m] = nxt[:m]
        prev_last = blk[-1]
        i += N
    ratio = f / (SR / (N + 0.5))                          # exact pitch (the averaging adds half a sample)
    t = np.arange(n) * ratio
    y = np.interp(t, np.arange(total), out).astype(np.float32)
    a = min(int(0.002 * SR), n)
    if a:
        y[:a] *= np.linspace(0, 1, a)
    peak = np.abs(y).max()
    if peak > 0:
        y /= peak
    if len(_KS) > 600:
        _KS.clear()
    _KS[key] = y
    return y


def pluck(f, dur, bright=1.0, decay=0.45):
    """A plucked note (guitar / harp-like) - Karplus-Strong. decay (seconds) sets how long it rings."""
    per = SR / max(f, 20.0)                               # loop passes per second = f; amplitude * d^(f*T) = 1/e
    d = float(np.exp(-1.0 / max(1e-3, decay * 2.2 * f)))
    x = ks(f, dur, decay=min(0.99995, max(0.9, d)), bright=min(1.0, 0.55 + 0.3 * bright))
    del per
    return x * 0.8


def pad(freqs, dur, cutoff=1400):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n, np.float32)
    for f in freqs:
        for det in (0.997, 1.003):
            for h in range(1, 6):
                x += (np.sin(2 * np.pi * f * det * h * t) / h).astype(np.float32)
    x = _lp(x / (len(freqs) * 6), cutoff)
    return x * _adsr(n, min(0.6, dur / 3), 0.3, 0.8, min(0.8, dur / 3))


def bass(f, dur, stacc=False):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) + 0.1 * np.sin(2 * np.pi * 3 * f * t)
    env = _adsr(n, 0.008, 0.08, 0.7, 0.05) if not stacc else np.exp(-t / 0.12)
    return (x * env).astype(np.float32)


def kick(rng):
    d = 0.22
    t = np.arange(int(d * SR)) / SR
    f = 50 + 90 * np.exp(-t * 30)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)).astype(np.float32)


def hat(rng, d=0.04):
    n = int(d * SR)
    x = rng.standard_normal(n).astype(np.float32)
    x = sosfilt(butter(2, 7000, "highpass", fs=SR, output="sos"), x).astype(np.float32)
    return x * np.exp(-np.arange(n) / SR / 0.012).astype(np.float32)


def generate(mood, duration, seed=0, style=None):
    """Return stereo (2, n) float32 music for `duration` seconds."""
    raw = str(mood or "").lower().strip()
    if style == "indian" or raw.startswith("raga") or raw in RAGA_MOODS:
        return generate_indian(raw.replace("raga_", "").replace("raga", "") or "calm", duration, seed)
    mood = resolve_mood(mood) or "happy"
    bpm, root, prog, style = MOODS[mood]
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bar = beat * 4
    n = int((duration + 3) * SR)
    L = np.zeros(n, np.float32)
    R = np.zeros(n, np.float32)

    def put(sig, t, g=1.0, pan=0.0):
        a = int(t * SR)
        if a >= n:
            return
        m = min(len(sig), n - a)
        L[a:a + m] += sig[:m] * g * (1 - pan) * 0.5 * 1.4
        R[a:a + m] += sig[:m] * g * (1 + pan) * 0.5 * 1.4

    n_bars = int(np.ceil((duration + 1) / bar))
    for b in range(n_bars):
        t0 = b * bar
        off, q = prog[b % len(prog)]
        third = 4 if q == "maj" else 3
        chord = [root + off, root + off + third, root + off + 7]
        freqs = [mtof(m) for m in chord]
        bf = mtof(root + off - 24)

        if style in ("pop", "soft", "piano", "bells", "pulse", "drive"):
            cut = {"pop": 1600, "soft": 1100, "piano": 900, "bells": 800, "pulse": 700, "drive": 1500}[style]
            gain = {"pop": 0.22, "soft": 0.35, "piano": 0.25, "bells": 0.3, "pulse": 0.3, "drive": 0.2}[style]
            put(pad([f * 0.5 for f in freqs], bar + 0.4, cut), t0, gain)

        arp = chord + [chord[0] + 12, chord[1] + 12]
        if style == "pop":
            for k in range(8):
                m = arp[[0, 2, 1, 3, 2, 4, 3, 2][k]] + 12
                put(pluck(mtof(m), beat * 1.2), t0 + k * beat / 2, 0.16, [-0.3, 0.3][k % 2])
            for k in range(4):
                put(bass(bf, beat * 0.9), t0 + k * beat, 0.35)
            for k in (0, 2):
                put(kick(rng), t0 + k * beat, 0.45)
            for k in range(4):
                put(hat(rng), t0 + k * beat + beat / 2, 0.12, 0.4)
        elif style == "soft":
            for k in range(4):
                m = arp[[0, 1, 2, 3][k]] + 12
                put(pluck(mtof(m), beat * 2.5, 0.6, 0.9), t0 + k * beat, 0.13, [-0.4, 0.4][k % 2])
            put(bass(bf, bar * 0.95), t0, 0.28)
        elif style == "piano":
            for k in range(4):
                m = arp[[0, 2, 1, 3][k]] + 12
                put(pluck(mtof(m), beat * 3, 0.8, 1.2), t0 + k * beat, 0.16, [-0.2, 0.2][k % 2])
            if b % 2 == 0:
                mel = root + off + 24 + rng.choice([0, 3 if q == "min" else 4, 7])
                put(pluck(mtof(mel), bar * 1.5, 0.5, 1.6), t0 + beat * 0.5, 0.1, 0.2)
            put(bass(bf, bar * 0.95), t0, 0.25)
        elif style == "pulse":
            for k in range(8):
                put(bass(bf * 2, beat * 0.45, True), t0 + k * beat / 2, 0.35)
            for k in range(16):
                put(hat(rng, 0.02), t0 + k * beat / 4, 0.05 + 0.04 * (k % 4 == 0), 0.3)
            if b % 2 == 1:
                put(pluck(mtof(root + off + 19), bar, 0.3, 2.0), t0 + beat * 2, 0.08, -0.4)
        elif style == "drive":
            for k in range(8):
                put(bass(bf, beat * 0.45, True), t0 + k * beat / 2, 0.4)
            for k in range(16):
                m = arp[[0, 1, 2, 3, 4, 3, 2, 1][k % 8]] + 12
                put(pluck(mtof(m), beat * 0.6, 1.2, 0.25), t0 + k * beat / 4, 0.09, [-0.35, 0.35][k % 2])
            for k in range(4):
                put(kick(rng), t0 + k * beat, 0.5)
                put(hat(rng), t0 + k * beat + beat / 2, 0.14, 0.3)
        elif style == "bounce":
            for k in range(4):
                put(bass(bf if k % 2 == 0 else bf * 1.5, beat * 0.4, True), t0 + k * beat, 0.45)
                for m in chord:
                    put(pluck(mtof(m + 12), beat * 0.3, 1.5, 0.08), t0 + k * beat + beat / 2, 0.08)
            for k in range(8):
                if rng.random() < 0.7:
                    m = arp[rng.integers(0, len(arp))] + 24
                    put(pluck(mtof(m), beat * 0.4, 1.5, 0.1), t0 + k * beat / 2, 0.1, 0.35)
        elif style == "bells":
            for k in range(4):
                if rng.random() < 0.6:
                    m = arp[rng.integers(0, len(arp))] + 24
                    put(pluck(mtof(m), beat * 4, 0.3, 2.5), t0 + k * beat, 0.09, rng.uniform(-0.6, 0.6))
            put(bass(bf, bar * 0.95), t0, 0.22)

    out = np.stack([L, R])[:, : int(duration * SR)]
    peak = np.abs(out).max()
    if peak > 0:
        out *= 0.8 / peak
    f = min(int(1.5 * SR), out.shape[1] // 3)
    if f > 0:
        out[:, :f] *= np.linspace(0, 1, f)
        out[:, -f:] *= np.linspace(1, 0, f)
    return out.astype(np.float32)


# ============================================================================ Indian: ragas on sitar, santoor, tanpura
#  raga: scale (semitones from Sa), vadi (the main note), tempo, tala beats, Sa (midi)
RAGAS = {
    "yaman":    ([0, 2, 4, 6, 7, 9, 11], 4, 70, 61),
    "bhupali":  ([0, 2, 4, 7, 9], 4, 96, 62),
    "desh":     ([0, 2, 4, 5, 7, 9, 10, 11], 7, 84, 62),
    "bhairavi": ([0, 1, 3, 5, 7, 8, 10], 5, 62, 61),
    "bhairav":  ([0, 1, 4, 5, 7, 8, 11], 8, 66, 61),
    "malkauns": ([0, 3, 5, 8, 10], 5, 64, 59),
    "kafi":     ([0, 2, 3, 5, 7, 9, 10], 7, 112, 62),
    "durga":    ([0, 2, 5, 7, 9], 7, 118, 62),
}
RAGA_MOODS = {"calm": "yaman", "romantic": "yaman", "love": "yaman", "evening": "yaman", "peaceful": "yaman",
              "happy": "bhupali", "cheerful": "bhupali", "rain": "desh", "monsoon": "desh", "sad": "bhairavi",
              "emotional": "bhairavi", "morning": "bhairav", "devotional": "bhairav", "temple": "bhairav",
              "mystery": "malkauns", "night": "malkauns", "tense": "malkauns", "funny": "kafi", "festival": "kafi",
              "holi": "kafi", "diwali": "kafi", "adventure": "durga", "epic": "durga", "sitar": "yaman",
              "indian": "bhupali"}
RAGA_MOODS.update({k: k for k in RAGAS})


def sitar(f, dur, seed=0, meend=0.0):
    """Sitar: a bright Karplus-Strong string + the jawari buzz (the flat bridge: a soft clip that makes the
    upper partials sing) + a glide up from meend semitones below (meend)."""
    x = ks(f, dur, decay=0.9993, bright=1.0, seed=seed)
    if meend:
        n = len(x)
        t = np.arange(n) / SR
        slide = np.minimum(1.0, t / 0.18)
        ratio = 2 ** ((-meend * (1.0 - slide)) / 12.0)
        pos = np.cumsum(ratio)
        pos = pos / pos[-1] * (n - 1) * min(1.0, ratio.mean())
        x = np.interp(pos, np.arange(n), x).astype(np.float32)
    buzz = np.tanh(3.2 * x) * 0.55 + 0.45 * x                # jawari
    hp = sosfilt(butter(1, 900, "highpass", fs=SR, output="sos"), buzz).astype(np.float32)
    return (0.6 * buzz + 0.4 * hp).astype(np.float32)


def santoor(f, dur, seed=0):
    """Santoor: hammered strings - a short hard burst, two strings a hair apart (the shimmer)."""
    a = ks(f, dur, decay=0.9985, bright=1.0, seed=seed, burst=0.25)
    b = ks(f * 1.004, dur, decay=0.9985, bright=1.0, seed=seed + 1, burst=0.25)
    return (0.5 * a + 0.5 * b).astype(np.float32)


def tanpura(sa, dur, seed=0, fifth=True):
    """Tanpura drone: Pa - Sa - Sa - Sa (low), each string long and buzzing, played round and round."""
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    notes = [sa * (1.5 if fifth else 4 / 3.0) / 2, sa, sa, sa / 2]
    t = 0.0
    k = 0
    while t < dur:
        f = notes[k % 4]
        x = ks(f, 4.0, decay=0.99985, bright=0.6, seed=seed + k % 4)
        x = (np.tanh(2.5 * x) * 0.7 + 0.3 * x).astype(np.float32)
        a = int(t * SR)
        m = min(len(x), n - a)
        if m > 0:
            out[a:a + m] += x[:m] * 0.5
        t += 0.95
        k += 1
    return out


def _tabla(kind, rng):
    """na / tin (dayan, ringing high) and ge (bayan, low with a pitch bend)."""
    if kind in ("na", "tin"):
        x = ks(rng.uniform(430, 470) if kind == "na" else 380, 0.35, decay=0.997, bright=1.0, seed=7)
        return x * np.exp(-np.arange(len(x)) / SR / 0.12).astype(np.float32)
    d = 0.45
    t = np.arange(int(d * SR)) / SR
    f = 80 + 50 * np.exp(-t * 6)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)).astype(np.float32)


THEKA = ["ge", "na", "na", "ge", "na", "na", "tin", "na"]         # a light 8-beat keherwa feel


def generate_indian(mood, duration, seed=0):
    """A raga for the mood: tanpura drone all through, a sitar melody that walks the raga (up the scale -
    aroha, down - avaroha, resting on Sa, Pa and the vadi), santoor answering, soft tabla."""
    rname = RAGA_MOODS.get(mood) or ("bhupali" if mood not in RAGAS else mood)
    scale, vadi, bpm, sa_m = RAGAS[rname]
    rng = np.random.default_rng(seed + 11)
    n = int((duration + 3) * SR)
    L = np.zeros(n, np.float32)
    R = np.zeros(n, np.float32)

    def put(sig, t, g=1.0, pan=0.0):
        a = int(t * SR)
        if a >= n or a < 0:
            return
        m = min(len(sig), n - a)
        L[a:a + m] += sig[:m] * g * (1 - pan) * 0.5
        R[a:a + m] += sig[:m] * g * (1 + pan) * 0.5

    sa = mtof(sa_m)
    dr = tanpura(sa / 2, duration + 2.0, seed)
    put(dr, 0.0, 0.35, -0.15)
    beat = 60.0 / bpm
    degrees = [d - 12 for d in scale] + scale + [d + 12 for d in scale[:3]]
    pos = len(scale)                                           # start on Sa (middle)
    t = beat * 4                                               # the drone sets the mood first
    phrase = 0
    while t < duration - 1.0:
        n_notes = int(rng.integers(4, 9))
        up = phrase % 2 == 0
        for j in range(n_notes):
            step = int(rng.choice([1, 1, 1, 2, -1])) * (1 if up else -1)
            pos = int(np.clip(pos + step, 2, len(degrees) - 2))
            if j == n_notes - 1:                                # end the phrase on a resting note
                rest = [k for k, d in enumerate(degrees) if d % 12 in (0, 7, scale[min(vadi, len(scale) - 1)] % 12)]
                pos = min(rest, key=lambda k: abs(k - pos))
            m = sa_m + degrees[pos]
            ln = beat * float(rng.choice([0.5, 0.5, 1.0, 1.0, 1.5])) * (2.0 if j == n_notes - 1 else 1.0)
            mee = float(rng.choice([0, 0, 0, 1, 2])) if j > 0 else 0.0
            put(sitar(mtof(m), ln + 1.2, seed + j, mee), t, 0.32, 0.15)
            t += ln
        t += beat * float(rng.choice([1, 2]))
        if rng.random() < 0.6:                                   # the santoor answers the phrase
            for j in range(4):
                m = sa_m + degrees[int(np.clip(pos + (j if phrase % 2 else -j), 0, len(degrees) - 1))] + 12
                for rep in range(2):                             # santoor tremolo: quick double strokes
                    put(santoor(mtof(m), beat * 1.5, seed + j), t + j * beat * 0.5 + rep * beat * 0.12, 0.13,
                        -0.35)
            t += beat * 2.5
        phrase += 1
    if bpm >= 80:                                               # tabla for the livelier ragas
        k = 0
        tt = beat * 8
        while tt < duration - 0.5:
            put(_tabla(THEKA[k % 8], rng), tt, 0.28 if THEKA[k % 8] == "ge" else 0.2, 0.05)
            tt += beat / 2
            k += 1
    out = np.stack([L, R])[:, : int(duration * SR)]
    peak = np.abs(out).max()
    if peak > 0:
        out *= 0.8 / peak
    f = min(int(1.5 * SR), out.shape[1] // 3)
    if f > 0:
        out[:, :f] *= np.linspace(0, 1, f)
        out[:, -f:] *= np.linspace(1, 0, f)
    return out.astype(np.float32)
