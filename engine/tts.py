"""Text-to-speech with automatic fallback.

Engines (tried in this order with tts_engine="auto"):
  edge     Microsoft neural voices via the free `edge-tts` package (needs internet) - best quality
  piper    Piper neural voices, offline on the CPU (`pip install piper-tts` + the voice files:
           python tools/get_piper_voices.py) - natural, not robotic; the local voice
  pyttsx3  offline system voices (Windows SAPI / macOS NSSpeech / Linux espeak)
  espeak   espeak-ng / espeak command line (offline, robotic but always works)
  silent   no audio, estimated duration (lip-sync still animates)

Every clip is cached in <cache>/tts, so re-rendering a story is fast.
"""
import asyncio
import hashlib
import os
import shutil
import subprocess
import sys

import numpy as np

from .audio import decode_audio, write_wav, read_wav

SR = 44100


class _Skip(Exception):
    pass

EDGE_VOICES = {
    "en-US": {"male": "en-US-GuyNeural", "female": "en-US-JennyNeural", "child": "en-US-AnaNeural",
              "narrator": "en-US-AriaNeural", "old": "en-US-DavisNeural"},
    "en-GB": {"male": "en-GB-RyanNeural", "female": "en-GB-SoniaNeural", "child": "en-GB-MaisieNeural",
              "narrator": "en-GB-SoniaNeural", "old": "en-GB-ThomasNeural"},
    "en-IN": {"male": "en-IN-PrabhatNeural", "female": "en-IN-NeerjaNeural", "child": "en-IN-NeerjaNeural",
              "narrator": "en-IN-NeerjaNeural", "old": "en-IN-PrabhatNeural"},
    "hi-IN": {"male": "hi-IN-MadhurNeural", "female": "hi-IN-SwaraNeural", "child": "hi-IN-SwaraNeural",
              "narrator": "hi-IN-SwaraNeural", "old": "hi-IN-MadhurNeural"},
}


def _pair(code, male, female):
    return {"male": f"{code}-{male}Neural", "female": f"{code}-{female}Neural", "child": f"{code}-{female}Neural",
            "narrator": f"{code}-{female}Neural", "old": f"{code}-{male}Neural"}


EDGE_VOICES.update({
    "ta-IN": _pair("ta-IN", "Valluvar", "Pallavi"), "te-IN": _pair("te-IN", "Mohan", "Shruti"),
    "mr-IN": _pair("mr-IN", "Manohar", "Aarohi"), "bn-IN": _pair("bn-IN", "Bashkar", "Tanishaa"),
    "gu-IN": _pair("gu-IN", "Niranjan", "Dhwani"), "kn-IN": _pair("kn-IN", "Gagan", "Sapna"),
    "ml-IN": _pair("ml-IN", "Midhun", "Sobhana"), "es-ES": _pair("es-ES", "Alvaro", "Elvira"),
    "fr-FR": _pair("fr-FR", "Henri", "Denise"),
})
# 🗣 Piper (local): voice files in assets/voices/piper/<name>.onnx (+ .onnx.json); one voice per role, and each
# character's own "pitch" / "rate" make two men sound different. A character may name one: "voice": {"piper": ...}
PIPER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "voices", "piper")
PIPER_VOICES = {
    "en": {"male": "en_US-ryan-medium", "female": "en_US-lessac-medium", "child": "en_US-amy-medium",
           "narrator": "en_US-lessac-medium", "old": "en_GB-alan-medium"},
    "hi": {"male": "hi_IN-rohan-medium", "female": "hi_IN-priyamvada-medium", "child": "hi_IN-priyamvada-medium",
           "narrator": "hi_IN-priyamvada-medium", "old": "hi_IN-pratham-medium"},
}
# many voices in one file: every character gets a speaker of its own (by its place in the cast), a man's voice for a
# man (each speaker's pitch is measured once and remembered in <model>.genders.json)
PIPER_MULTI = ("en_US-libritts_r-medium", "en_US-libritts-high")                 # 900+ English speakers
PIPER_INDIAN = ("en_US-l2arctic-medium", {"male": ("ASI", "RRBI"), "female": ("SVBI", "TNI")})   # Indian English
ESPEAK_LANG = {"en-US": "en-us", "en-GB": "en-gb", "en-IN": "en-us", "hi-IN": "hi", "ta-IN": "ta", "te-IN": "te",
               "mr-IN": "mr", "bn-IN": "bn", "gu-IN": "gu", "kn-IN": "kn", "ml-IN": "ml", "es-ES": "es", "fr-FR": "fr"}
LANG_NAMES = {"en-US": "English (US)", "en-GB": "English (UK)", "en-IN": "English (India)", "hi-IN": "Hindi",
              "ta-IN": "Tamil", "te-IN": "Telugu", "mr-IN": "Marathi", "bn-IN": "Bengali", "gu-IN": "Gujarati",
              "kn-IN": "Kannada", "ml-IN": "Malayalam", "es-ES": "Spanish", "fr-FR": "French"}
ISO3 = {"en": "eng", "hi": "hin", "ta": "tam", "te": "tel", "mr": "mar", "bn": "ben", "gu": "guj", "kn": "kan",
        "ml": "mal", "es": "spa", "fr": "fra"}


def norm_lang(code):
    """'hi', 'hindi', 'HI-in' -> 'hi-IN' (a key of EDGE_VOICES) or the input unchanged."""
    c = str(code or "").strip()
    low = c.lower()
    for k, v in LANG_NAMES.items():
        if low in (k.lower(), v.lower(), v.lower().split(" ")[0]):
            return k
    short = low.split("-")[0]
    for k in EDGE_VOICES:
        if k.lower().startswith(short + "-"):
            return "en-IN" if short == "en" and low == "en" else k
    return c


BIG_ANIMALS = ("tiger", "lion", "bear", "elephant", "cow", "horse", "wolf", "eagle")


def voice_role(cdef):
    if cdef is None:
        return "narrator"
    if getattr(cdef, "kind", "human") != "human":
        if cdef.species in BIG_ANIMALS and cdef.age not in ("child", "baby", "toddler"):
            return "male" if cdef.gender != "female" else "female"
        return "child"
    if cdef.age in ("child", "kid", "baby", "toddler"):
        return "child"
    if cdef.age == "old":
        return "old"
    return "female" if cdef.gender in ("female", "f", "girl", "woman") else "male"


def build_voice(cdef, language, index, overrides=None):
    """Resolve a full voice description for a character (or narrator if cdef is None)."""
    lang = language if language in EDGE_VOICES else "en-US"
    role = voice_role(cdef)
    if overrides is None:
        overrides = (cdef.voice if cdef else {}) or {}
    v = {k: val for k, val in dict(overrides).items() if val is not None}
    if v.get("name") and not v.get("edge"):
        v["edge"] = v["name"]
    v.setdefault("edge", EDGE_VOICES[lang][role])
    variants = {"male": ["m3", "m1", "m7", "m2"], "female": ["f3", "f1", "f4", "f2"],
                "child": ["f5", "f4"], "old": ["m6", "m4"], "narrator": ["f2"]}[role]
    v.setdefault("espeak", f"{ESPEAK_LANG.get(lang, 'en-us')}+{variants[index % len(variants)]}")
    # automatic pitch variety so two characters of the same kind sound different
    base_pitch = {"child": 12, "old": -4}.get(role, 0)
    if cdef is not None and getattr(cdef, "kind", "human") != "human":
        base_pitch += -9 if cdef.species in BIG_ANIMALS else 6
    v["pitch_auto"] = "pitch" not in v                  # (a voice of its own needs no pitch trick: see TTS._piper_pick)
    v["seat"] = index
    v.setdefault("pitch", base_pitch + [0, -6, 6, -3, 3][index % 5] * (0 if role == "narrator" else 1))
    v.setdefault("rate", -5 if role in ("narrator", "old") else 0)
    v["role"] = role
    return v


class TTS:
    def __init__(self, engine="auto", cache_dir="cache", language="en-US", warn=print, log=print):
        self.pref = (engine or "auto").lower()
        self.cache = os.path.join(cache_dir, "tts")
        os.makedirs(self.cache, exist_ok=True)
        self.language = language
        self.warn, self.log = warn, log
        self._dead = set()
        self.used = set()
        self.espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
        self._piper_models = {}

    def order(self):
        if self.pref == "auto":
            return ["edge", "piper", "pyttsx3", "espeak", "silent"]
        if self.pref in ("local", "offline"):
            return ["piper", "pyttsx3", "espeak", "silent"]
        return [self.pref, "piper", "espeak", "silent"] if self.pref != "silent" else ["silent"]

    def _path(self, eng, text, voice):
        who = self._piper_pick(voice) if eng == "piper" else voice.get(eng)
        key = hashlib.sha1(repr((eng, text, who, voice.get("pitch"), voice.get("rate"),
                                 self.language)).encode()).hexdigest()[:20]
        return os.path.join(self.cache, f"{eng}_{key}.wav")

    def cached(self, text, voice):
        text = " ".join(str(text).split())
        for eng in self.order():
            if eng in self._dead or eng == "silent":
                continue
            if os.path.exists(self._path(eng, text, voice)):
                return True
            if eng == "edge" and self.pref == "auto":
                return False       # would still try edge first
        return self.pref == "silent"

    def synth(self, text, voice):
        """Returns (samples float32 mono @44.1k, engine_used)."""
        text = " ".join(str(text).split())
        for eng in self.order():
            if eng in self._dead:
                continue
            path = self._path(eng, text, voice)
            if os.path.exists(path):
                self.used.add(eng)
                return read_wav(path), eng
            try:
                audio = getattr(self, "_" + eng)(text, voice, path)
            except _Skip:
                self._dead.add(eng)
                continue
            except Exception as ex:  # engine unavailable -> never try it again this run
                self._dead.add(eng)
                self.warn(f"voice engine '{eng}' unavailable ({type(ex).__name__}: {str(ex)[:120]}); falling back")
                continue
            if eng != "silent":
                audio = _clean(audio)
                write_wav(path, audio)
            self.used.add(eng)
            return audio, eng
        return np.zeros(int(SR * 1.0), np.float32), "silent"

    # ---------------------------------------------------------------- engines
    def _edge(self, text, voice, path):
        import edge_tts  # noqa
        tmp = path + ".mp3"
        pitch = int(round(float(voice.get("pitch", 0)) * 2.5))
        rate = int(voice.get("rate", 0))
        comm = edge_tts.Communicate(text, voice["edge"], rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")

        async def run():
            await asyncio.wait_for(comm.save(tmp), timeout=40)
        asyncio.run(run())
        if not os.path.exists(tmp) or os.path.getsize(tmp) < 200:
            raise RuntimeError("empty audio from edge-tts")
        audio = decode_audio(tmp)
        os.remove(tmp)
        return audio

    def _have(self, name):
        return os.path.exists(os.path.join(PIPER_DIR, name + ".onnx"))

    def _load(self, name):
        from piper import PiperVoice  # noqa
        if name not in self._piper_models:
            self._piper_models[name] = PiperVoice.load(os.path.join(PIPER_DIR, name + ".onnx"))
        return self._piper_models[name]

    def _gender_pool(self, model, gender, need):
        """the first `need` speakers of a many-speaker voice file that sound like a man / a woman: each speaker's
        pitch is measured once (a man's voice sits below ~165 Hz) and kept in <model>.genders.json"""
        import json
        import random
        import wave
        from piper import SynthesisConfig  # noqa
        cache = os.path.join(PIPER_DIR, model + ".genders.json")
        try:
            f0s = {int(k): v for k, v in json.load(open(cache)).items()}
        except Exception:
            f0s = {}
        pv = self._load(model)
        n = int(getattr(pv.config, "num_speakers", 1) or 1)
        order = list(range(n))
        random.Random(7).shuffle(order)
        pool, dirty = [], False
        for sid in order:
            if sid not in f0s:
                tmp = os.path.join(self.cache, f"_f0_{model}_{sid}.wav")
                with wave.open(tmp, "wb") as w:
                    pv.synthesize_wav("Hello there, this is how my voice sounds today.", w,
                                      syn_config=SynthesisConfig(speaker_id=sid))
                f0s[sid] = _median_f0(decode_audio(tmp))
                os.remove(tmp)
                dirty = True
            if (f0s[sid] < 165) == (gender == "male") and f0s[sid] > 0:
                pool.append(sid)
                if len(pool) >= need:
                    break
        if dirty:
            try:
                json.dump({str(k): v for k, v in f0s.items()}, open(cache, "w"))
            except OSError:
                pass
        return pool

    def _piper_pick(self, voice):
        """(voice file, speaker or None, pitch shift) for this character:
        its own choice ("piper", "speaker") > Hindi voices for a Hindi story > Indian English speakers (L2-ARCTIC)
        for an Indian character > one of the 900 English speakers > one voice per role"""
        role = voice.get("role", "male")
        seat = int(voice.get("seat", 0))
        gender = "male" if role in ("male", "old") else "female"
        pitch = float(voice.get("pitch", 0))
        auto = voice.get("pitch_auto", True)
        if voice.get("piper"):
            return str(voice["piper"]), voice.get("speaker"), pitch
        lang = str(self.language).lower()
        if lang.startswith("hi"):
            name = PIPER_VOICES["hi"].get(role) or PIPER_VOICES["hi"]["male"]
            if self._have(name):
                return name, None, pitch                               # (3 voices: pitch and speed tell them apart)
        edge = str(voice.get("edge") or "")
        indian = lang.endswith("-in") or edge[:5].lower() in ("en-in", "hi-in", "ta-in", "te-in", "mr-in", "bn-in")
        own = {"child": 7.0, "old": -2.0}.get(role, 0.0)               # a speaker of its own: no pitch trick needed
        if indian and self._have(PIPER_INDIAN[0]):
            names = PIPER_INDIAN[1][gender]
            ids = self._load(PIPER_INDIAN[0]).config.speaker_id_map or {}
            sid = ids.get(names[seat % len(names)])
            if sid is not None:
                return PIPER_INDIAN[0], sid, pitch                     # (2 a gender: pitch keeps them apart)
        for multi in PIPER_MULTI:
            if self._have(multi):
                pool = self._gender_pool(multi, gender, seat + 1)
                if pool:
                    return multi, pool[min(seat, len(pool) - 1)], own if auto else pitch
                break
        name = PIPER_VOICES["en"].get(role) or PIPER_VOICES["en"]["male"]
        if not self._have(name):
            have = sorted(f[:-5] for f in os.listdir(PIPER_DIR) if f.endswith(".onnx")) if os.path.isdir(PIPER_DIR) else []
            if not have:
                raise RuntimeError("no Piper voices (run: python tools/get_piper_voices.py)")
            name = have[0]
        return name, None, pitch

    def _piper(self, text, voice, path):
        try:
            from piper import SynthesisConfig  # noqa
        except ImportError:
            raise RuntimeError("piper-tts not installed (pip install piper-tts)")
        name, sid, pitch = self._piper_pick(voice)
        if not self._have(name):
            raise RuntimeError(f"no Piper voice {name} (run: python tools/get_piper_voices.py)")
        pv = self._load(name)
        import wave
        tmp = path + ".tmp.wav"
        rate = int(voice.get("rate", 0))
        cfg = SynthesisConfig(length_scale=1.0 / max(0.5, 1.0 + rate / 100.0), speaker_id=sid)
        with wave.open(tmp, "wb") as w:
            pv.synthesize_wav(text, w, syn_config=cfg)
        audio = decode_audio(tmp)
        os.remove(tmp)
        if abs(pitch) > 0.5:                                           # a little higher / lower
            audio = _pitch_shift(audio, 2 ** (pitch / 36.0))
        return audio

    def _pyttsx3(self, text, voice, path):
        if sys.platform.startswith("linux"):
            raise _Skip()
        import pyttsx3  # noqa
        eng = pyttsx3.init()
        want_f = voice.get("role") in ("female", "child", "narrator")
        for v in eng.getProperty("voices"):
            name = (v.name or "").lower()
            if want_f and any(k in name for k in ("zira", "female", "samantha", "hazel", "susan", "heera")):
                eng.setProperty("voice", v.id)
                break
            if not want_f and any(k in name for k in ("david", "male", "alex", "daniel", "george", "ravi")):
                eng.setProperty("voice", v.id)
                break
        eng.setProperty("rate", int(175 * (1 + int(voice.get("rate", 0)) / 100.0)))
        tmp = path + ".tmp.wav"
        eng.save_to_file(text, tmp)
        eng.runAndWait()
        audio = decode_audio(tmp)
        os.remove(tmp)
        if voice.get("role") == "child":
            audio = _pitch_shift(audio, 1.18)
        return audio

    def _espeak(self, text, voice, path):
        if not self.espeak_bin:
            raise RuntimeError("espeak-ng not installed")
        tmp = path + ".tmp.wav"
        pitch = int(max(0, min(99, 50 + float(voice.get("pitch", 0)) * 2.2)))
        speed = int(165 * (1 + int(voice.get("rate", 0)) / 100.0))
        subprocess.run([self.espeak_bin, "-v", voice["espeak"], "-s", str(speed), "-p", str(pitch),
                        "-g", "2", "-w", tmp, text], check=True, capture_output=True, timeout=60)
        audio = decode_audio(tmp)
        os.remove(tmp)
        return audio

    def _silent(self, text, voice, path):
        n = int(SR * (0.35 + 0.062 * len(text)))
        # fake syllable envelope so lip-sync still moves; volume is ~inaudible
        t = np.arange(n) / SR
        env = (np.sin(2 * np.pi * 4.5 * t) > 0).astype(np.float32)
        return (env * 1e-3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)


def _clean(a):
    a = np.asarray(a, np.float32)
    if a.size == 0:
        return np.zeros(SR // 2, np.float32)
    thr = max(np.abs(a).max() * 0.02, 1e-4)
    idx = np.where(np.abs(a) > thr)[0]
    if idx.size:
        pad = int(0.04 * SR)
        a = a[max(0, idx[0] - pad): idx[-1] + pad]
    peak = np.abs(a).max()
    if peak > 1e-6:
        a = a * (0.89 / peak)
    return a.astype(np.float32)


def _median_f0(a, sr=SR):
    """the speaking pitch of a recording (Hz, median over its voiced frames; 0 if none): autocorrelation per 40 ms"""
    a = np.asarray(a, np.float32)
    n = int(0.04 * sr)
    lo, hi = int(sr / 400), int(sr / 60)
    f0 = []
    for i in range(0, len(a) - n, n):
        fr = a[i:i + n] - a[i:i + n].mean()
        if np.sqrt((fr ** 2).mean()) < 0.02:
            continue
        ac = np.correlate(fr, fr, "full")[n - 1:]
        if ac[0] <= 0:
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] / ac[0] > 0.35:
            f0.append(sr / k)
    return float(np.median(f0)) if f0 else 0.0


def _pitch_shift(a, factor):
    """Crude pitch/tempo shift by resampling (used for child voices on pyttsx3)."""
    n = int(len(a) / factor)
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
