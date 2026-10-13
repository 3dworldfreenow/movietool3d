"""🔊 The sound library: which sounds a story uses, which ones have a real recording, and saving uploads under the
right name.

Every sound the engine makes has a name ("rotor", "siren", "rain" ...). A recording saved as assets/sfx/<name>.<ext>
is used instead of the synthesised sound (engine/sfx.py). Any sound may have several takes (siren, siren_2,
siren_3 ...: a different one each time it plays); an upload either replaces a sound's takes or adds another one. New
names can be added too (the library grows): a story plays them with {"sound": "<name>"}. needs(story) lists what a story will play and why, so the studio can show what is
still synthesised and take an upload for it.
"""
import math
import os
import re
import shutil

from . import sfx

EXTS = (".mp3", ".wav", ".ogg", ".flac", ".m4a")
BEDS = ("rain", "wind", "thunder")                  # several recordings each (name, name_2, name_3 ...)
MAX_MB = 30

WHAT = {   # name -> what it should sound like (for the upload list)
    "rain": "steady rain (a long loop, 30 s or more)", "wind": "wind / a storm gale (a long loop)",
    "thunder": "one clap of thunder", "engine": "a car engine running (loop)", "car_door": "a car door shutting",
    "siren": "a police siren", "rotor": "a helicopter overhead (loop)", "jet": "a jet's engines, spooling up",
    "door": "a door opening", "knock": "knocking on a door", "phone": "a phone ringing",
    "footstep": "one footstep", "run_step": "a running footstep", "crash": "a crash of wood / metal",
    "clang": "a metal bang", "thud": "a heavy thud", "creak": "creaking wood or metal", "whoosh": "a fast whoosh",
    "scrape": "metal scraping", "static": "TV static / signal lost", "scream": "one person screaming",
    "panic": "a street of people screaming and shouting", "murmur": "a hall of people talking low (loop)",
    "whispers": "people whispering", "heartbeat": "a heartbeat", "splash": "a splash", "boom": "an explosion",
    "hail": "hail on roofs", "bird": "birds", "dog": "a dog barking",
}


def _base(b):
    """a file's sound name: siren_2 -> siren (a take), car_door -> car_door"""
    m = re.fullmatch(r"(.+?)_(\d+)", b)
    return m.group(1) if m else b


def custom():
    """the names people added themselves (recordings in assets/sfx that are not a built-in sound)"""
    if not os.path.isdir(sfx.REAL_DIR):
        return []
    known = set(sfx.SFX) | set(BEDS)
    out = set()
    for f in os.listdir(sfx.REAL_DIR):
        b, ext = os.path.splitext(f)
        if ext.lower() in EXTS and b not in known and _base(b) not in known:
            out.add(_base(b))
    return sorted(out)


_INFO = {}


def check(path):
    """🔎 test a recording the way the engine will hear it: {"dur": s, "peak_db", "rms_db", "lead": s of silence at
    the start, "warn": [...]} (a file the engine cannot read raises ValueError)"""
    import numpy as np
    try:
        a = np.asarray(sfx.decode_audio(path), np.float32)
    except Exception:
        raise ValueError("That file could not be read as audio.")
    n = len(a)
    dur = n / float(sfx.SR)
    peak = float(np.abs(a).max()) if n else 0.0
    rms = float(np.sqrt(np.mean(a.astype(np.float64) ** 2))) if n else 0.0
    db = lambda v: round(20 * math.log10(max(v, 1e-6)), 1)
    loud = np.where(np.abs(a) > 0.01)[0]                               # (-40 dB: where the sound starts)
    lead = float(loud[0]) / sfx.SR if loud.size else dur
    warn = []
    if dur < 0.1:
        warn.append("too short (under 0.1 s)")
    if peak < 0.006:
        warn.append("silent - nothing to hear")
    elif peak < 0.05:
        warn.append("very quiet (it will be turned up)")
    if n and float(np.mean(np.abs(a) > 0.99)) > 0.001:
        warn.append("distorted (clipped peaks)")
    if 0.3 < lead < dur:
        warn.append(f"{lead:.1f} s of silence at the start (trim it so it plays on time)")
    return {"dur": round(dur, 2), "peak_db": db(peak), "rms_db": db(rms), "lead": round(lead, 2), "warn": warn}


def info(fname):
    """check() of a saved recording (remembered until the file changes) + its size"""
    p = os.path.join(sfx.REAL_DIR, os.path.basename(fname))
    st = os.stat(p)
    key = (fname, st.st_mtime, st.st_size)
    if key not in _INFO:
        try:
            got = check(p)
        except ValueError as ex:
            got = {"dur": 0, "peak_db": -120, "rms_db": -120, "lead": 0, "warn": [str(ex)]}
        got["kb"] = round(st.st_size / 1024)
        _INFO[key] = got
    return dict(_INFO[key], file=fname)


def names():
    """every sound name: the synthesised ones, the weather beds and the ones added to the library"""
    return sorted(set(sfx.SFX) | set(BEDS) | set(custom()))


def files(name):
    """the recordings (takes) saved for a name: <name>.<ext>, <name>_2.<ext> ..."""
    if not os.path.isdir(sfx.REAL_DIR):
        return []
    out = []
    for f in sorted(os.listdir(sfx.REAL_DIR)):
        b, ext = os.path.splitext(f)
        if ext.lower() in EXTS and (b == name or re.fullmatch(re.escape(name) + r"_\d+", b)):
            out.append(f)
    return out


def needs(story):
    """{name: why} - the sounds this story will play: its "sound" events and what its scenes imply (cars,
    helicopters, the weather, debris, crowds ...)"""
    need = {}

    def add(n, why):
        need.setdefault(n, why)
    for i, sc in enumerate(story.get("scenes") or [], 1):
        tag = sc.get("id") or f"scene {i}"
        for e in sc.get("events") or []:
            if not isinstance(e, dict):
                continue
            if e.get("sound"):
                add(str(e["sound"]).lower(), f"{tag}: a \"sound\" event")
            w = str(e.get("weather") or "").lower()
            if w:
                if any(k in w for k in ("rain", "storm", "drizzle", "monsoon", "shower", "cyclone", "hurricane")):
                    add("rain", f"{tag}: the rain")
                if any(k in w for k in ("storm", "cyclone", "hurricane", "wind")):
                    add("wind", f"{tag}: the wind")
                if any(k in w for k in ("storm", "cyclone", "hurricane", "thunder")):
                    add("thunder", f"{tag}: thunder")
            if e.get("effect") == "lightning":
                add("thunder", f"{tag}: lightning")
            if e.get("do") in ("walk", "run"):
                add("footstep", f"{tag}: walking")
        for c in sc.get("stick_cars") or []:
            k = str(c.get("kind", "car"))
            if k in ("helicopter", "heli", "chopper", "apache", "gunship", "army_helicopter"):
                add("rotor", f"{tag}: the helicopter")
            elif k in ("jet", "plane", "aircraft"):
                add("jet", f"{tag}: the jet")
            elif c.get("fly"):
                add("creak", f"{tag}: a car rocking in the wind")
                add("thud", f"{tag}: a car rocking in the wind")
            elif c.get("from") and c.get("to"):
                add("engine", f"{tag}: a car driving")
                add("car_door", f"{tag}: car doors")
                if k == "police":
                    add("siren", f"{tag}: the police car")
        if sc.get("stick_debris"):
            for n in ("clang", "thud", "crash", "whoosh", "creak"):
                add(n, f"{tag}: debris in the wind")
        if sc.get("stick_panic"):
            add("panic", f"{tag}: people screaming")
        if sc.get("stick_murmur"):
            add("murmur", f"{tag}: the hall talking")
        if sc.get("stick_whispers"):
            add("whispers", f"{tag}: whispers")
        live = sc.get("stick_live")
        if isinstance(live, dict) and live.get("fall_at") is not None:
            add("crash", f"{tag}: the camera falls")
            add("static", f"{tag}: signal lost")
        if sc.get("stick_hail"):
            add("hail", f"{tag}: hail")
    return need


def status(story=None):
    """the upload list: [{name, what, why, files}] - the story's sounds first, then every other name"""
    need = needs(story) if story else {}
    rows = []
    for n in list(need) + [x for x in names() if x not in need]:
        mine = n not in sfx.SFX and n not in BEDS
        rows.append({"name": n, "what": WHAT.get(n, ("your own sound: " if mine else "") + n.replace("_", " ")),
                     "why": need.get(n, ""), "files": files(n), "info": [info(f) for f in files(n)],
                     "needed": n in need, "custom": mine})
    return rows


def save(name, src_path, filename, mode="auto", new=False):
    """keep an uploaded recording as the sound <name> -> its file name.
    mode "replace": it becomes the only take (the old ones are deleted); "add": another take next to the old ones
    (name_2, name_3 ...); "auto": rain / wind / thunder add, the rest replace. new=True adds a name of your own to the
    library. Raises ValueError for a bad name / file."""
    name = re.sub(r"[^a-z0-9_]+", "_", str(name).lower()).strip("_")
    if not name:
        raise ValueError("Give the sound a name.")
    if name not in names():
        if not new:
            raise ValueError(f"Unknown sound name \"{name}\" - pick one from the list, or add it as a new sound.")
        if not (2 <= len(name) <= 30) or re.fullmatch(r".+_\d+", name) or name[0].isdigit():
            raise ValueError("A new sound name: 2-30 letters (a-z, 0-9, _), not ending in _<number>.")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in EXTS:
        raise ValueError("Send an audio file: mp3, wav, ogg, flac or m4a.")
    if os.path.getsize(src_path) > MAX_MB * 1024 * 1024:
        raise ValueError(f"The file is too big ({MAX_MB} MB at most).")
    got = check(src_path)                            # (raises when the engine cannot read it)
    if got["dur"] < 0.1:
        raise ValueError("The recording is too short.")
    if "silent - nothing to hear" in got["warn"]:
        raise ValueError("The recording is silent - nothing to hear.")
    if mode not in ("auto", "replace", "add"):
        mode = "auto"
    if mode == "auto":
        mode = "add" if name in BEDS else "replace"
    try:
        os.makedirs(sfx.REAL_DIR, exist_ok=True)
    except OSError as ex:
        raise ValueError(f"The server cannot make the sounds folder ({ex.strerror or ex}).")
    if not os.access(sfx.REAL_DIR, os.W_OK):
        raise ValueError("The server is not allowed to write in assets/sfx - give the studio's user write access "
                         "to that folder.")
    old = files(name)
    if mode == "add" and old:                        # another take
        k = 2
        while any(os.path.splitext(f)[0] == f"{name}_{k}" for f in old):
            k += 1
        base = f"{name}_{k}"
    else:
        for f in old:                                # (replace: the new one is the only take)
            os.remove(os.path.join(sfx.REAL_DIR, f))
        base = name
    out = base + ext
    try:                                             # (a copy, not a rename: the upload may sit on another disk -
        shutil.copyfile(src_path, os.path.join(sfx.REAL_DIR, out))     # /tmp - where a rename fails)
    except OSError as ex:
        raise ValueError(f"The server could not save the file ({ex.strerror or ex}).")
    sfx._REAL.clear()
    return out


def remove(fname):
    """delete one uploaded recording (only an audio file in assets/sfx)"""
    fname = os.path.basename(str(fname))
    if os.path.splitext(fname)[1].lower() not in EXTS:
        raise ValueError("Not a sound file.")
    p = os.path.join(sfx.REAL_DIR, fname)
    if not os.path.isfile(p):
        raise ValueError("No such file.")
    os.remove(p)
    sfx._REAL.clear()


MIME = {".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".flac": "audio/flac", ".m4a": "audio/mp4", ".wav": "audio/wav"}


def play_file(fname, engine=False):
    """(bytes, mimetype) of one saved recording - as uploaded, or (engine=True) as the engine hears it: decoded to
    mono 44.1 kHz WAV (proof the renderer can read it)"""
    fname = os.path.basename(str(fname))
    p = os.path.join(sfx.REAL_DIR, fname)
    if os.path.splitext(fname)[1].lower() not in EXTS or not os.path.isfile(p):
        raise ValueError("No such sound file.")
    if not engine:
        with open(p, "rb") as f:
            return f.read(), MIME.get(os.path.splitext(p)[1].lower(), "application/octet-stream")
    import io
    import wave
    import numpy as np
    x = np.asarray(sfx.decode_audio(p), np.float32)
    pcm = (np.clip(x[: sfx.SR * 30], -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sfx.SR)
        w.writeframes(pcm)
    return buf.getvalue(), "audio/wav"


def preview(name):
    """(bytes, mimetype) to listen to a sound: its recording, else the synthesised one as a wav"""
    fs = files(name)
    if fs:                                           # (the first take)
        p = os.path.join(sfx.REAL_DIR, fs[0])
        ext = os.path.splitext(p)[1].lower()
        with open(p, "rb") as f:
            return f.read(), {".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".flac": "audio/flac",
                              ".m4a": "audio/mp4"}.get(ext, "audio/wav")
    import io
    import wave
    import numpy as np
    if name in BEDS:
        x = sfx.thunder(np.random.default_rng(1)) if name == "thunder" else \
            sfx._filt(np.random.default_rng(1).standard_normal(sfx.SR * 4).astype(np.float32), "bandpass",
                      [900, 7000] if name == "rain" else [120, 700]) * 0.3
    else:
        x = sfx.SfxBank(sfx.REAL_DIR, warn=lambda *a: None).get(name)
    if x is None:
        raise ValueError("No such sound.")
    x = np.asarray(x, np.float32)
    if x.ndim > 1:
        x = x.mean(axis=0)
    pcm = (np.clip(x[: sfx.SR * 8], -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sfx.SR)
        w.writeframes(pcm)
    return buf.getvalue(), "audio/wav"
