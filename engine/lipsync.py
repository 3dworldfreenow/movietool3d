"""Natural talking faces: mouth SHAPES (not just open / shut) + brows, nods, blinks and glances - offline.

How (see README "Talking faces"):
  1. the SOUNDS of the line: eSpeak NG turns the text into phonemes (Hindi, English, Tamil ... offline);
     no eSpeak -> simple letter rules (Latin and Devanagari letters)
  2. each sound -> one of 9 cartoon mouth shapes (the animators' A..H + rest, like Rhubarb Lip Sync):
        X rest   A closed M B P   B teeth (EE S T K ...)   C open (EH)   D wide open (AA)
        E round open (O)   F small round (OO W)   G lip under teeth (F V)   H tongue up (L TH)
  3. the voice audio says WHEN: the sounds are laid out along the loud parts of the recording (more sounds
     where it is loud, none in the pauses), so the mouth closes on M / B / P and rounds on O / OO in time
  4. from the same audio + text: brows lift on stressed words and questions, small head nods on emphasis,
     blinks in the pauses, small eye glances
Everything is plain numpy - no model, no download.
"""
import math
import re
import shutil
import subprocess
import zlib

import numpy as np

# shape -> (jaw open, lip width, lip round, lips closed, teeth show, tongue show)
SHAPES = {
    "X": (0.00, 0.50, 0.00, 1.0, 0.0, 0.0),
    "A": (0.00, 0.45, 0.10, 1.0, 0.0, 0.0),
    "B": (0.18, 0.88, 0.00, 0.0, 1.0, 0.0),
    "C": (0.50, 0.75, 0.05, 0.0, 0.6, 0.0),
    "D": (1.00, 0.70, 0.10, 0.0, 0.3, 0.0),
    "E": (0.55, 0.38, 0.70, 0.0, 0.1, 0.0),
    "F": (0.25, 0.18, 1.00, 0.0, 0.0, 0.0),
    "G": (0.12, 0.72, 0.00, 0.3, 1.0, 0.0),
    "H": (0.45, 0.62, 0.05, 0.0, 0.5, 1.0),
}
KEYS = ("jaw", "wide", "round", "closed", "teeth", "tongue")
VOWEL_SHAPES = set("CDEF")

ESPEAK_VOICE = {"hi": "hi", "en": "en-us", "ta": "ta", "te": "te", "mr": "mr", "bn": "bn", "gu": "gu", "kn": "kn",
                "ml": "ml", "pa": "pa", "ur": "ur", "es": "es", "fr": "fr", "de": "de", "ne": "ne"}
_MULTI = ("aI", "aU", "eI", "oU", "OI", "tS", "dZ", "i:", "u:", "a:", "e:", "o:", "O:", "3:", "A:", "E:", "@L", "@-")
_ESPEAK = {"bin": None, "checked": False}


# ============================================================================ text -> shapes
def _espeak():
    if not _ESPEAK["checked"]:
        _ESPEAK["checked"] = True
        _ESPEAK["bin"] = shutil.which("espeak-ng") or shutil.which("espeak")
    return _ESPEAK["bin"]


def _is_latin(text):
    letters = [c for c in text if c.isalpha()]
    return not letters or sum(1 for c in letters if ord(c) < 0x250) / len(letters) > 0.6


def _phone_shape(ph):
    p = ph.strip("'`,:;#*_~=|0123456789")
    if not p:
        return None
    two = {"aI": "DB", "aU": "DF", "eI": "CB", "oU": "EF", "OI": "EB", "tS": "B", "dZ": "B", "@L": "CH"}
    if p in two:
        return two[p]
    c = p[0]
    if c in "pbm":
        return "A"
    if c in "fv":
        return "G"
    if c in "TDl":
        return "H"
    if c in "wuU":
        return "F"
    if c in "oO3":
        return "E" if c != "o" else "F"
    if c in "aA":
        return "D"
    if c in "EV@&":
        return "C"
    if c in "eiIjy":
        return "B"
    if c == "h":
        return "C"
    return "B"                                              # the other consonants: teeth, a little open


def _parse_espeak(out):
    words = []
    for w in out.split():
        seq, i = [], 0
        while i < len(w):
            m = next((t for t in _MULTI if w.startswith(t, i)), None)
            tok = m or w[i]
            i += len(tok)
            s = _phone_shape(tok)
            if s:
                seq.extend(list(s))
        if seq:
            words.append(seq)
    return words


_DEV = {}
for ch in "पफबभम":
    _DEV[ch] = "A"
for ch in "व":
    _DEV[ch] = "F"
for ch in "लड़ढ़":
    _DEV[ch] = "H"
for ch in "अआा":
    _DEV[ch] = "D"
for ch in "एेैऐ":
    _DEV[ch] = "C"
for ch in "इईिीय":
    _DEV[ch] = "B"
for ch in "उऊुू":
    _DEV[ch] = "F"
for ch in "ओोऔौ":
    _DEV[ch] = "E"


def _letters(text):
    """no eSpeak: letters -> shapes (rough, but closes on m/b/p and rounds on o/u)"""
    words = []
    for w in re.findall(r"[\w\u0900-\u0963\u0966-\u097F]+", text.lower()):   # keeps Hindi vowel signs in the word
        seq = []
        i = 0
        while i < len(w):
            c = w[i]
            if w.startswith("th", i):
                seq.append("H")
                i += 2
                continue
            if c in _DEV:
                seq.append(_DEV[c])
            elif "ऀ" <= c <= "ॿ":
                if c not in "्ंँः़":
                    seq.append("B")
                    if i + 1 >= len(w) or not ("ा" <= w[i + 1] <= "्"):
                        seq.append("C")                    # the hidden 'a' after a Hindi consonant
            elif c in "mbp":
                seq.append("A")
            elif c in "fv":
                seq.append("G")
            elif c == "l":
                seq.append("H")
            elif c in "ow":
                seq.append("E" if c == "o" else "F")
            elif c == "u":
                seq.append("F")
            elif c == "a":
                seq.append("D")
            elif c == "e":
                seq.append("C")
            elif c in "iy":
                seq.append("B")
            elif c.isalpha():
                seq.append("B")
            i += 1
        if seq:
            words.append(seq)
    return words


_PH_CACHE = {}


def text_shapes(text, lang="en-IN"):
    """[[shapes of word 1], [word 2] ...]"""
    text = re.sub(r"<[^>]+>|\[[^\]]*\]", " ", str(text or "")).strip()
    if not text:
        return []
    key = (text, lang)
    if key in _PH_CACHE:
        return _PH_CACHE[key]
    words = None
    exe = _espeak()
    if exe:
        base = str(lang or "en").split("-")[0].lower()
        voice = "en-us" if _is_latin(text) else ESPEAK_VOICE.get(base, "en-us")
        try:
            r = subprocess.run([exe, "-q", "-x", "-v", voice, text], capture_output=True, timeout=10)
            words = _parse_espeak(r.stdout.decode("utf-8", errors="replace"))
        except (OSError, subprocess.SubprocessError):
            words = None
    if not words:
        words = _letters(text)
    if len(_PH_CACHE) > 2000:
        _PH_CACHE.clear()
    _PH_CACHE[key] = words
    return words


# ============================================================================ audio -> timing
def _env(audio, fps, sr):
    hop = sr / fps
    n = max(1, int(np.ceil(len(audio) / hop)))
    a = np.asarray(audio, np.float32)
    idx = (np.arange(n) * hop).astype(np.int64)
    win = int(hop * 1.2)
    pad = np.concatenate([a, np.zeros(win + 1, np.float32)])
    frames = np.lib.stride_tricks.sliding_window_view(pad, win)[idx]
    rms = np.sqrt((frames * frames).mean(axis=1))
    hi = np.abs(np.diff(frames, axis=1)).mean(axis=1)      # hiss (s, sh, f): lots of fast change
    ref = np.percentile(rms, 92) if rms.max() > 0 else 1.0
    e = np.clip(rms / max(ref, 1e-6), 0, 1.3)
    hiss = hi / (rms * 2.0 + 1e-6)
    return e.astype(np.float32), hiss.astype(np.float32)


class Mouth(float):
    """The mouth opening (a number, like before) that also carries the face controls: .ctl = {jaw, wide, round,
    closed, teeth, tongue, brow, gx, gy, lid, smile ...}. Old drawing code just sees the number."""

    def __new__(cls, value, ctl=None):
        m = float.__new__(cls, value)
        m.ctl = ctl or {}
        return m


def ctl_of(mouth):
    return getattr(mouth, "ctl", None) or None


class Talk:
    """Per-frame face controls of one spoken line."""
    __slots__ = ("n", "jaw", "wide", "round", "closed", "teeth", "tongue", "brow", "nod", "tilt", "blink",
                 "gx", "gy", "peaks", "mouth", "shape", "question")

    def at(self, k):
        if k < 0 or k >= self.n:
            return None
        return {"jaw": float(self.jaw[k]), "wide": float(self.wide[k]), "round": float(self.round[k]),
                "closed": float(self.closed[k]), "teeth": float(self.teeth[k]), "tongue": float(self.tongue[k]),
                "brow": float(self.brow[k]), "nod": float(self.nod[k]), "tilt": float(self.tilt[k]),
                "blink": bool(self.blink[k]), "gx": float(self.gx[k]), "gy": float(self.gy[k]),
                "shape": self.shape[k]}


def _pulse(n, at, width, amp=1.0):
    """a smooth bump (0 -> amp -> 0) over `width` frames starting at frame `at`"""
    out = np.zeros(n, np.float32)
    w = max(1, int(width))
    for k in range(w):
        i = at + k
        if 0 <= i < n:
            out[i] = amp * math.sin(math.pi * (k + 0.5) / w)
    return out


def analyze(audio, text, fps, lang="en-IN", sr=24000, emotion=None, seed=None):
    """-> Talk (arrays, one value per video frame)."""
    e, hiss = _env(audio, fps, sr)
    n = len(e)
    t = Talk()
    t.n = n
    sm = np.convolve(e, np.ones(3) / 3.0, mode="same")
    voiced = sm > 0.12
    # ---- 1. the sounds laid out along the loud parts
    words = text_shapes(text, lang)
    seq, wts = [], []
    for wi, w in enumerate(words):
        for s in w:
            seq.append(s)
            wts.append(2.0 if s in VOWEL_SHAPES else (1.4 if s == "A" else 1.0))
    shape = np.array(["X"] * n, dtype=object)
    if seq and voiced.any():
        mass = np.where(voiced, np.maximum(sm, 0.05), 0.0)
        mass = mass / mass.sum()
        pos = np.cumsum(mass) - mass / 2.0                  # where each frame sits (0..1 of the speech)
        W = np.cumsum(wts)
        centers = (W - np.array(wts) / 2.0) / W[-1]          # where each sound sits (0..1 of the speech)
        k = np.searchsorted(centers, pos)
        k = np.clip(k, 0, len(seq) - 1)
        k2 = np.clip(k - 1, 0, len(seq) - 1)
        pick = np.where(np.abs(centers[k2] - pos) < np.abs(centers[k] - pos), k2, k)
        for i in range(n):
            if voiced[i]:
                shape[i] = seq[pick[i]]
        for j, s in enumerate(seq):                          # M / B / P always shut the lips for a moment
            if s == "A":
                i = int(np.searchsorted(pos, centers[j]))
                if 0 <= i < n and voiced[min(i, n - 1)]:
                    shape[min(i, n - 1)] = "A"
    else:                                                    # no text: loudness only
        shape = np.where(voiced, np.where(sm > 0.7, "D", np.where(sm > 0.35, "C", "B")), "X").astype(object)
    # hissy frames (s / sh / f) that were given an open shape -> teeth
    for i in range(n):
        if voiced[i] and hiss[i] > 1.6 and shape[i] in ("C", "D"):
            shape[i] = "B"
    # ---- 2. shapes -> smooth controls (lips move a little ahead into the next shape)
    P = np.array([SHAPES[s] for s in shape], np.float32)
    loud = np.clip(0.55 + 0.45 * sm, 0.3, 1.1)
    P[:, 0] *= loud
    out = np.zeros_like(P)
    prev = P[0]
    for i in range(n):
        tgt = P[i]
        if shape[i] in ("A", "X") and tgt[3] >= 1.0:
            cur = prev * 0.35 + tgt * 0.65                   # lips shut quickly
        else:
            cur = prev * 0.45 + tgt * 0.55
        out[i] = cur
        prev = cur
    t.jaw, t.wide, t.round, t.closed, t.teeth, t.tongue = (out[:, j].copy() for j in range(6))
    t.shape = list(shape)
    t.mouth = np.clip(t.jaw * (1.0 - 0.8 * t.closed), 0, 1).astype(np.float32)   # old single value
    # ---- 3. stressed moments, pauses, question
    rng = np.random.RandomState((zlib.crc32(str(text).encode()) if seed is None else seed) & 0x7fffffff)
    peaks = []
    gap = int(0.35 * fps)
    for i in range(2, n - 2):
        if sm[i] > 0.78 and sm[i] >= sm[i - 1] and sm[i] >= sm[i + 1] and sm[i] >= sm[max(0, i - 4):i + 5].max():
            if not peaks or i - peaks[-1] >= gap:
                peaks.append(i)
    t.peaks = peaks
    q = bool(re.search(r"[?？]\s*[\"')\]]*\s*$", str(text).strip())) or bool(re.search(r"^\s*(kya|क्या)\b", str(text).lower()))
    t.question = q
    excl = "!" in str(text)
    brow = np.zeros(n, np.float32)
    nod = np.zeros(n, np.float32)
    for j, p in enumerate(peaks):
        strong = 1.0 if (excl or j == 0) else 0.7
        if rng.rand() < 0.75:
            brow += _pulse(n, p - int(0.08 * fps), 0.45 * fps, 0.55 * strong)
        if rng.rand() < 0.6:
            nod += _pulse(n, p - int(0.05 * fps), 0.32 * fps, 4.0 * strong)     # degrees, head dips on the beat
    tilt = np.zeros(n, np.float32)
    last = int(np.nonzero(voiced)[0][-1]) if voiced.any() else n - 1
    if q:                                                    # a question: brows up, head tilts, at the end
        a = max(0, int(last - 0.7 * fps))
        ramp = np.clip((np.arange(n) - a) / max(1.0, 0.35 * fps), 0, 1)
        brow = np.maximum(brow, 0.8 * ramp)
        tilt = (6.0 * ramp).astype(np.float32)
    else:                                                    # a statement: a small nod down to finish
        nod += _pulse(n, max(0, last - int(0.25 * fps)), 0.5 * fps, 3.0)
    t.brow = np.clip(brow, 0, 1).astype(np.float32)
    t.nod = nod.astype(np.float32)
    t.tilt = tilt
    # ---- 4. blinks in the pauses (+ now and then), small eye glances
    blink = np.zeros(n, bool)
    bl = max(2, int(0.13 * fps))
    run = 0
    for i in range(n):
        if not voiced[i]:
            run += 1
            if run == int(0.12 * fps) and i > int(0.3 * fps) and rng.rand() < 0.7:
                blink[i:i + bl] = True
        else:
            run = 0
    last_b = -999
    for i in range(n):
        if blink[i]:
            last_b = i
        elif i - last_b > int(3.2 * fps) and rng.rand() < 0.03:
            blink[i:i + bl] = True
            last_b = i
    t.blink = blink
    gx = np.zeros(n, np.float32)
    gy = np.zeros(n, np.float32)
    i = 0
    cur = (0.0, 0.0)
    while i < n:
        hold = int(fps * rng.uniform(0.8, 2.0))
        cur = (float(rng.uniform(-0.12, 0.12)), float(rng.uniform(-0.06, 0.08)))
        if i == 0 and (emotion == "thinking" or rng.rand() < 0.25):
            cur = (float(rng.choice([-0.35, 0.35])), 0.22)   # looks away while starting a thought
            hold = int(fps * 0.5)
        gx[i:i + hold], gy[i:i + hold] = cur
        i += hold
    t.gx, t.gy = gx, gy
    return t


def listen(n, fps, speaker_talk, offset_frames, seed=0):
    """A listener's small reactions to someone talking: nods on some of the speaker's beats, blinks after."""
    rng = np.random.RandomState(seed & 0x7fffffff)
    nod = np.zeros(n, np.float32)
    blink = np.zeros(n, bool)
    brow = np.zeros(n, np.float32)
    if speaker_talk is None:
        return nod, blink, brow
    for j, p in enumerate(speaker_talk.peaks):
        k = p + offset_frames + int(0.18 * fps)              # a beat after the speaker's stress
        if rng.rand() < 0.45:
            nod += _pulse(n, k, 0.45 * fps, 3.0)
        if rng.rand() < 0.25:
            blink[max(0, k):max(0, k) + max(2, int(0.13 * fps))] = True
    if speaker_talk.question:                                # a question makes the listener look up a bit
        last = offset_frames + speaker_talk.n
        brow += _pulse(n, last - int(0.4 * fps), 0.8 * fps, 0.4)
    return nod, blink[:n], brow
