"""The cinematographer: every shot gets what a real film camera crew would choose.

The auto-director (director.py) decides WHAT to show and when to cut. This decides HOW it is filmed:
  1. reads the scene first: a TENSION curve (emotions, shouts, fights, runs, crashes, storms, dark moods)
  2. shot size follows it - calm = wider, rising = tighter, the peak = the closest / a slow push
  3. a real LENS per shot (24-28 mm wide for places and action, 40-50 mm for talk, 85-135 mm for emotion)
     with its depth of field: long lens = soft background, the one who matters is sharp
  4. camera HEIGHT with meaning (eye level; low for power / anger / big animals; high for fear / small / sad;
     at a child's eye height for a child)
  5. a 3/4 ANGLE instead of flat side-on (faces and conversations turn into the depth)
  6. MOVES with weight: tripod-still at the peak, slow dolly while calm, handheld as tension rises
  7. FOREGROUND framing now and then: a soft out-of-focus pillar edge / leaves / grass / pole near the lens
Story camera events keep their shot type and timing; only settings they did not give are filled in.

JSON control (all optional):
  "settings": {"cinema": {"style": "feature | classic | dramatic | documentary | action | dreamy | off",
                          (feature = animated-feature film: steady eased moves, 24-85 mm lenses, motivated
                           moves only, fewer cuts, low angles for powerful characters; default in 3D)
                          "look": "feature | flat"   (feature: warm key / cool fill, rim light, bloom, grade),
                          "decide": "gaps | all"   (all = the camera films the whole scene itself; the story's
                                                    own camera events are ignored, shakes stay),
                          "pace": "slow | normal | fast", "lens": "wide | normal | long",
                          "depth": 0.7 (0 = all sharp .. 1 = very soft backgrounds),
                          "foreground": true | false | "often", "handheld": 0..1,
                          "angles": "flat | normal | dynamic", "reactions": true}}
  a scene can have its own "cinema": {...} (overrides the story's for that scene)
  any camera event:  "lens": 50 | "85mm" | "wide" | "normal" | "long",  "dof": "shallow | deep | 0..1",
                     "angle": 30 (degrees round the subject), "height": "low | eye | high" (or a number),
                     "move": "locked | dolly_in | dolly_out | truck_left | truck_right | crane_up | handheld | steadicam",
                     "foreground": "leaves | pillar | grass | pole | branch | none"
"""
import math

STYLES = {
    #              handheld base, handheld per tension, lens mul, closeups, low angles, depth
    "classic":     dict(hh0=0.18, hht=0.32, lens=1.0, tight=0.0, low=0.0, depth=0.7),
    "dramatic":    dict(hh0=0.12, hht=0.35, lens=1.12, tight=0.18, low=0.25, depth=0.9),
    "documentary": dict(hh0=0.5, hht=0.3, lens=0.9, tight=-0.1, low=0.0, depth=0.5),
    "action":      dict(hh0=0.4, hht=0.5, lens=0.82, tight=0.05, low=0.3, depth=0.55),
    "dreamy":      dict(hh0=0.08, hht=0.1, lens=1.25, tight=0.0, low=0.0, depth=1.0),
    # animated feature (Moana / Pixar layout): a steadicam / dolly crew, real film lenses, subtle focus
    "feature":     dict(hh0=0.0, hht=0.0, lens=1.0, tight=0.05, low=0.2, depth=0.55, feature=True),
}
# feature lenses in real millimetres (full-frame). Our lens factor 1.0 = FOCAL 1100 on a 1920 frame = about 20.7 mm
MM_PER_LENS = 20.7
FEATURE_MM = {"EW": 24.0, "W": 28.0, "FS": 35.0, "MS": 45.0, "MCU": 58.0, "CU": 75.0, "ECU": 85.0}
POWER_WORDS = ("king", "raja", "maharaja", "samrat", "emperor", "queen", "rani", "ravan", "ravana", "villain",
               "demon", "rakshas", "asura", "dashrath", "dasharath", "janak", "sugriv", "bali", "vali", "kumbhkaran",
               "kumbhakarna", "meghnad", "indrajit", "tataka", "god", "vishwamitra", "guru")
POWER_HATS = ("crown", "king_crown", "mukut", "turban_royal", "royal", "tiara")


def is_feature(opts):
    return bool(STYLES.get((opts or {}).get("style"), {}).get("feature"))


def is_power(cdef):
    """A character the camera looks UP to: "power": true in the JSON, or a king / queen / villain / big animal."""
    if cdef is None:
        return False
    spec = getattr(cdef, "spec", None) or {}
    if "power" in spec:
        return bool(spec.get("power"))
    if getattr(cdef, "kind", "human") != "human":
        return str(getattr(cdef, "species", "")) in ("tiger", "lion", "elephant", "bear", "dinosaur", "gorilla", "rhino")
    words = " ".join(str(spec.get(k, "")) for k in ("name", "role", "profession", "title", "outfit")).lower() + \
        " " + str(getattr(cdef, "id", "")).lower()
    if any(w in words for w in POWER_WORDS):
        return True
    return str(spec.get("hat", "")).lower() in POWER_HATS
PACE = {"slow": 1.35, "normal": 1.0, "fast": 0.72}
LENS_WORD = {"wide": 0.72, "ultra_wide": 0.55, "normal": 1.0, "standard": 1.0, "long": 1.9, "tele": 2.4,
             "telephoto": 2.4, "portrait": 1.9}
HEIGHT_WORD = {"low": -70.0, "ground": -140.0, "worm": -140.0, "eye": 0.0, "eye_level": 0.0, "shoulder": 25.0,
               "high": 110.0, "top": 220.0, "bird": 300.0}

# shot type -> size class
SIZE = {}
for _k in ("extreme_wide", "establishing", "drone", "dark_wide", "overhead", "crane_down"):
    SIZE[_k] = "EW"
for _k in ("wide", "static_wide", "crane_up", "pull_back", "slow_pull", "slow_pan", "pan_left", "pan_right"):
    SIZE[_k] = "W"
for _k in ("full_shot", "medium_wide", "auto", "track", "lead", "follow", "arc", "handheld_follow", "whip"):
    SIZE[_k] = "FS"
for _k in ("medium", "over_shoulder", "reverse", "low_angle", "high_angle", "dutch", "tilt_up", "tilt_down"):
    SIZE[_k] = "MS"
for _k in ("medium_closeup", "push_in", "slow_push", "long_lens"):
    SIZE[_k] = "MCU"
for _k in ("closeup", "close", "focus", "crash_zoom", "dolly_zoom"):
    SIZE[_k] = "CU"
for _k in ("extreme_closeup", "insert"):
    SIZE[_k] = "ECU"
LENS_OF = {"EW": 0.7, "W": 0.8, "FS": 0.95, "MS": 1.12, "MCU": 1.45, "CU": 1.8, "ECU": 2.3}
NO_TOUCH = ("pov", "inside", "spin", "look_around", "dolly_zoom", "crash_zoom", "long_lens", "whip", "zoom", "pan")

EMO_T = {"angry": 0.8, "scared": 0.8, "crying": 0.7, "surprised": 0.65, "sad": 0.45, "thinking": 0.25,
         "happy": 0.18, "laughing": 0.3, "neutral": 0.1}
ACT_T = {"fight": 0.85, "pounce": 0.85, "attack": 0.85, "kick": 0.75, "push": 0.6, "struggle": 0.7, "throw": 0.55,
         "fall": 0.7, "roar": 0.75, "run": 0.45, "gallop": 0.5, "jump": 0.4, "hide": 0.55, "peek": 0.5, "scared": 0.7,
         "cry": 0.6, "chase": 0.8, "climb": 0.45, "break": 0.6}
IMPACTS = ("crash", "thunder", "splash", "thud", "roar", "stomp", "explosion", "boom", "scream")


def options(settings, scene_spec=None, mode3d=None):
    """The story's "cinema" settings with the scene's on top."""
    o = {"style": None, "pace": "normal", "lens": "normal", "depth": None, "foreground": "sometimes",
         "handheld": None, "angles": "normal", "reactions": True}
    for src in ((settings or {}).get("cinema"), (scene_spec or {}).get("cinema")):
        if isinstance(src, dict):
            o.update({k: v for k, v in src.items() if v is not None})
        elif isinstance(src, str):
            o["style"] = src
    if o["style"] is None or str(o["style"]).lower() in ("auto", "default", ""):
        o["style"] = "feature" if (mode3d if mode3d is not None else _is3d(settings, scene_spec)) else "classic"
    elif str(o["style"]).lower() in ("off", "none", "simple", "false"):
        o["style"] = "off"                                  # the old camera (no cinematographer)
    elif o["style"] not in STYLES:
        o["style"] = "classic"
    o["look"] = str(o.get("look") or ("feature" if o["style"] == "feature" else "flat")).lower()
    return o


def _is3d(settings, scene_spec):
    for src in (scene_spec or {}, settings or {}):
        m = src.get("camera_mode", src.get("world"))
        if m is not None:
            return str(m).lower() in ("3d", "2.5d", "true3d", "depth")
    return False


# ============================================================================ 1. reading the scene
def tension_curve(tl, step=0.25):
    """-> (times step, values 0..1): how tense the scene is at each moment."""
    dur = max(0.5, float(getattr(tl, "duration", 10.0) or 10.0))
    n = int(dur / step) + 2
    raw = [0.0] * n

    def put(a, b, v, tail=1.5):
        i0, i1 = max(0, int(a / step)), min(n - 1, int(b / step))
        for i in range(i0, i1 + 1):
            raw[i] = max(raw[i], v)
        for k in range(1, int(tail / step) + 1):          # it stays in the air a little
            i = i1 + k
            if i < n:
                raw[i] = max(raw[i], v * (1.0 - k * step / tail))

    for sp in getattr(tl, "speeches", []):
        emo = str(sp.emotion or "").lower()
        v = EMO_T.get(emo, 0.12)
        txt = str(sp.text)
        if "!" in txt:
            v += 0.15
        if sp.who == "narrator":
            v *= 0.6
        put(sp.start, sp.end, min(1.0, v), 2.0)
    for tr in getattr(tl, "tracks", {}).values():
        if getattr(tr, "crowd", False):
            continue
        for s in tr.segments:
            v = ACT_T.get(s.action)
            if v:
                put(s.start, s.start + max(0.4, s.dur), v, 1.8)
            if s.emotion:
                put(s.start, s.start + max(0.4, s.dur), EMO_T.get(str(s.emotion).lower(), 0.1) * 0.8, 1.0)
    for t, name, vol, *_rest in getattr(tl, "sfx", []):
        if any(k in str(name) for k in IMPACTS) and vol >= 0.4:
            put(t, t + 0.3, 0.8, 2.0)
    for t, c in getattr(tl, "camera", []):
        if c.get("type") in ("shake", "earthquake", "explosion", "punch", "impact", "rumble"):
            put(t, t + float(c.get("duration", 0.6)), 0.7, 1.5)
    for t, mood, _f in getattr(tl, "mood_fx", []):
        if str(mood) in ("dark_jungle", "spooky", "night"):
            put(t, dur, 0.25, 0)
    for t, w, _f in getattr(tl, "weather_fx", []):
        if str(w) == "storm":
            put(t, dur, 0.35, 0)
    out, cur = [], 0.0
    a_up, a_dn = 0.6, 0.12                                  # rises quickly, settles slowly
    for v in raw:
        cur = cur + (v - cur) * (a_up if v > cur else a_dn)
        out.append(min(1.0, cur))
    return step, out


def tension_at(curve, t):
    step, vals = curve
    if not vals:
        return 0.0
    i = int(max(0.0, t) / step)
    return vals[min(i, len(vals) - 1)]


def peaks(curve, thr=0.6):
    step, vals = curve
    out = []
    for i in range(1, len(vals) - 1):
        if vals[i] >= thr and vals[i] >= vals[i - 1] and vals[i] > vals[i + 1]:
            if not out or i * step - out[-1] > 4.0:
                out.append(i * step)
    return out


# ============================================================================ helpers for JSON words
def lens_value(v, feature=False):
    """50 / "85mm" / "wide" / 1.4 -> our lens factor (1 = about 40 mm; in the feature style real mm: 1 = 20.7 mm)"""
    if feature and v is not None:
        s_ = str(v).lower().strip().replace(" ", "")
        if s_.endswith("mm") or (isinstance(v, (int, float)) and float(v) > 6):
            try:
                return max(0.9, min(6.0, float(s_.replace("mm", "")) / MM_PER_LENS))
            except ValueError:
                pass
        if s_ in ("wide", "ultra_wide"):
            return 24.0 / MM_PER_LENS if s_ == "wide" else 20.0 / MM_PER_LENS
        if s_ in ("normal", "standard"):
            return 45.0 / MM_PER_LENS
        if s_ in ("long", "portrait"):
            return 85.0 / MM_PER_LENS
        if s_ in ("tele", "telephoto"):
            return 135.0 / MM_PER_LENS
    if v is None:
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return max(0.4, min(4.0, f / 40.0 if f > 6 else f))
    s = str(v).lower().strip().replace(" ", "_")
    if s in LENS_WORD:
        return LENS_WORD[s]
    s = s.replace("mm", "")
    try:
        f = float(s)
        return max(0.4, min(4.0, f / 40.0 if f > 6 else f))
    except ValueError:
        return None


def height_value(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return HEIGHT_WORD.get(str(v).lower().strip().replace(" ", "_"))


def dof_value(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return max(0.0, min(1.5, float(v)))
    return {"shallow": 1.1, "soft": 0.9, "normal": 0.5, "deep": 0.0, "sharp": 0.0, "none": 0.0}.get(
        str(v).lower().strip(), None)


def foreground_kind(bg):
    """what could stand near the lens in this place"""
    pre = str(getattr(bg, "preset", "") or "").lower()
    if (getattr(bg, "spec", None) or {}).get("planet_place"):
        return None                                      # another planet: no Earth leaves / grass / poles in front of the lens
    if getattr(bg, "indoor", False) or any(k in pre for k in ("palace", "temple", "castle", "school", "hospital",
                                                                "police", "station", "court", "fort", "mahal")):
        return "pillar"
    if any(k in pre for k in ("jungle", "forest", "garden", "park", "bamboo", "village", "farm", "orchard", "river",
                              "lake", "hill", "banyan", "ghat")):
        return "leaves"
    if any(k in pre for k in ("field", "mustard", "meadow", "desert", "beach", "savanna")):
        return "grass"
    if any(k in pre for k in ("city", "street", "market", "bus", "town", "road")):
        return "pole"
    if any(k in pre for k in ("space", "moon", "mars", "planet", "solar", "galaxy", "cave", "sea", "ocean",
                              "underwater", "snow", "ice", "sky", "cloud")):
        return None                                      # nothing grows there: no leaves in front of the lens
    return None if getattr(bg, "time", "") == "space" else "leaves"


# ============================================================================ 2-7. every shot
def clear_angle(tl, tgt, t, a, typ="medium"):
    """3D: the orbit angle (degrees, + = camera to the right) closest to `a` from which nobody else stands
    between the camera and `tgt` - a face half hidden behind someone's back looks like a mistake."""
    from .world3d import Z_of_z, X_of, p3, FOCAL
    W2 = tl.world_w / 2.0
    zoom = {"closeup": 3.6, "medium_closeup": 2.8, "medium": 2.4, "low_angle": 2.3, "high_angle": 1.1,
            "slow_push": 1.4, "push_in": 1.45, "full_shot": 1.1, "medium_wide": 1.15}.get(typ, 1.2)
    ds = FOCAL / zoom

    def world(cid):
        tr = tl.tracks[cid]
        x, z = tr.x_at(t), tr.z_at(t)
        return X_of(x, p3(z), W2), Z_of_z(z), tr.cdef.scale
    try:
        Xs, Zs, _ = world(tgt)
        others = [world(k) for k, tr in tl.tracks.items()
                  if k != tgt and not tr.crowd and tl._visible(k, t)]
    except Exception:
        return a

    def blocked(deg):
        r = math.radians(deg)
        cx, cz = Xs + ds * math.sin(r), Zs - ds * math.cos(r)
        vx, vz = Xs - cx, Zs - cz
        L = math.hypot(vx, vz) or 1.0
        for bx, bz, sc in others:
            u = ((bx - cx) * vx + (bz - cz) * vz) / (L * L)
            if not (0.05 < u < 0.93):
                continue                                    # behind the camera or behind the subject
            if abs((bx - cx) * vz - (bz - cz) * vx) / L < 70.0 * sc:
                return True
        return False
    for cand in (a, -a, a * 0.5, -a * 0.5, 0.0, a * 1.6, -a * 1.6):
        if not blocked(cand):
            return cand
    return a


def shape(tl, shots, mode3d, opts, bg=None):
    """shots: [(t, cmd)] from the director (auto + story) -> the same list with the camera crew's choices.
    Auto shots may also change size with the tension; story shots only get what they did not set."""
    st = STYLES.get(opts.get("style"), STYLES["classic"])
    feat = bool(st.get("feature"))
    curve = tension_curve(tl)
    tl._tension = curve
    depth = opts.get("depth")
    depth = st["depth"] if depth is None else max(0.0, min(1.5, float(depth)))
    lens_bias = LENS_WORD.get(str(opts.get("lens", "normal")).lower(), 1.0) ** 0.35 * st["lens"]
    ang_k = {"flat": 0.0, "normal": 1.0, "dynamic": 1.6}.get(str(opts.get("angles", "normal")).lower(), 1.0)
    hh_user = opts.get("handheld")
    fg_opt = opts.get("foreground", "sometimes")
    fg_every = {True: 3, "sometimes": 3, "often": 2, "always": 1, False: 0, "none": 0, "off": 0}.get(fg_opt, 3)
    fg_kind = foreground_kind(bg) if bg is not None else "leaves"
    if fg_kind is None:
        fg_every = 0
    pk = peaks(curve)
    out = []
    n_fg = fg_every - 1 if fg_every else 0                  # the scene's first wide shot is framed too
    for idx, (t, c) in enumerate(sorted(shots, key=lambda s: s[0])):
        c = dict(c)
        typ = c.get("type", "auto")
        auto = bool(c.get("_auto"))
        tens = tension_at(curve, t + 0.3)
        tgt = c.get("target") or c.get("who")
        tr = tl.tracks.get(tgt) if tgt else None
        # ---- the JSON words on any shot -> numbers
        if "lens" in c:
            lv = lens_value(c["lens"], feat)
            if lv is None:
                c.pop("lens")
            else:
                c["lens"] = lv
        if "height" in c and not isinstance(c["height"], (int, float)):
            hv = height_value(c["height"])
            if hv is None:
                c.pop("height")
            else:
                c["height"] = hv
        if "dof" in c:
            dv = dof_value(c.pop("dof"))
            if dv is not None:
                c["aperture"] = dv
        mv = str(c.get("move", "")).lower()
        if mv:
            if mv in ("locked", "tripod", "still", "static"):
                c["locked"] = True
                c["drift"] = None
            elif mv in ("dolly_in", "push", "push_in"):
                c["drift"] = "in"
            elif mv in ("dolly_out", "pull", "pull_out"):
                c["drift"] = "out"
            elif mv in ("truck_left", "truck_right"):
                c["drift"] = mv.split("_")[1]
            elif mv in ("crane_up", "rise", "up", "crane"):
                c["drift"] = "up"
            elif mv in ("orbit", "arc") and tgt:
                c.setdefault("drift", "right")
            elif mv in ("truck", "track"):
                c.setdefault("drift", "right")
            elif mv in ("hold",):
                c["drift"] = None
            elif mv in ("handheld", "shoulder"):
                c.setdefault("handheld", 0.9)
            elif mv in ("steadicam", "gimbal"):
                c.setdefault("handheld", 0.25)
        if typ in NO_TOUCH or typ in ("shake", "punch", "impact", "rack_focus"):
            out.append((t, c))
            continue
        size = SIZE.get(typ, "MS")
        emo = ""
        for sp in tl.speeches:
            if sp.start - 0.4 <= t <= sp.end and sp.who == tgt:
                emo = str(sp.emotion or "").lower()
                break
        # ---- 2. shot size follows the tension (auto shots only)
        if auto:
            near_peak = any(abs(t - p) < 1.2 for p in pk)
            tight = st["tight"] + (tens - 0.4) * 0.8
            if typ == "medium" and tr is not None and tight > 0.28:
                typ = c["type"] = "medium_closeup"
            elif typ == "medium" and tight < -0.2 and tr is not None:
                typ = c["type"] = "medium_wide"
            elif typ == "closeup" and tight < -0.25 and emo not in EMO_T:
                typ = c["type"] = "medium_closeup"
            if near_peak and typ in ("medium", "medium_closeup", "closeup") and tr is not None and \
                    emo in ("surprised", "scared", "thinking", "sad", "crying"):
                typ = c["type"] = "slow_push"                   # the realisation: creep in
                c.setdefault("duration", 4.0)
            size = SIZE.get(typ, size)
        # ---- 3. lens + depth of field
        if "lens" not in c and feat:
            mm = FEATURE_MM.get(size, 45.0) * lens_bias
            if size in ("MS", "MCU", "CU") and typ not in ("track", "lead", "follow"):
                mm *= 1.0 + 0.15 * tens                        # emotion: a longer lens, the world falls away
            if typ in ("track", "lead", "follow", "handheld_follow"):
                mm = min(mm, 35.0)                              # action: wide, full of space and speed
            if typ == "low_angle":
                mm = min(mm, 40.0)                              # power: wide enough to feel the height
            c["lens"] = round(max(22.0, min(100.0, mm)) / MM_PER_LENS, 3)
        if "lens" not in c:
            lens = LENS_OF.get(size, 1.0) * lens_bias
            if size in ("MS", "MCU", "CU") and typ not in ("track", "lead", "follow"):
                lens *= 1.0 + 0.22 * tens                      # tension: the world closes in behind the face
            if typ in ("track", "lead", "follow", "handheld_follow"):
                lens = min(lens, 0.85)                          # action: wide and close, full of energy
            c["lens"] = round(max(0.55, min(3.2, lens)), 3)
        if "aperture" not in c and mode3d and feat:           # subtle: the subject sharp, the far world soft
            c["aperture"] = round(depth * max(0.0, min(0.55, (c["lens"] - 1.6) * 0.22)), 3)
        elif "aperture" not in c and mode3d:
            c["aperture"] = round(depth * max(0.0, min(1.2, (c["lens"] - 0.95) * 0.9)), 3)
        # ---- 4. height with meaning
        if "height" not in c and typ in ("medium", "medium_closeup", "closeup", "slow_push", "push_in",
                                         "full_shot", "medium_wide", "track", "lead", "follow", "auto"):
            h = 0.0
            if tr is not None:
                species = str(getattr(tr.cdef, "species", "") or "")
                if feat and is_power(tr.cdef) and emo not in ("scared", "crying", "sad"):
                    h = -70.0 - 40.0 * st["low"]                # we look up to kings, villains, giants
                elif emo == "angry" or (tr.cdef.kind != "human" and species in ("tiger", "lion", "elephant", "bear",
                                                                                "dinosaur", "bull", "wolf")):
                    h = -55.0 - 40.0 * st["low"]
                elif emo in ("scared", "crying", "sad"):
                    h = 45.0
                elif getattr(tr.cdef, "age", "") in ("child", "toddler", "baby") and size in ("MS", "MCU", "CU", "FS"):
                    h = -60.0                                   # at the child's own eye height
            if not feat:
                h += 10.0 * math.sin(idx * 1.7)                 # never exactly the same height twice
            if abs(h) > 3:
                c["height"] = round(h, 1)
        # ---- 5. a 3/4 angle into the depth (3D)
        if mode3d and "angle" not in c and ang_k > 0 and typ in ("medium", "medium_closeup", "closeup",
                                                                  "medium_wide", "full_shot", "auto", "wide",
                                                                  "slow_push", "push_in", "low_angle", "high_angle"):
            face = 0
            if tr is not None:
                try:                                            # the way they face NOW (in a talk: the other one)
                    face = 1 if tr.state(t + 0.3, tl).facing >= 0 else -1
                except Exception:
                    try:
                        face = 1 if tr.facing_at(t + 0.2) >= 0 else -1
                    except Exception:
                        face = 0
            if size in ("MS", "MCU", "CU") and face:
                a = 26.0 * face                                 # the camera steps round to the front of the face
            else:
                a = 14.0 * (1 if idx % 2 else -1)
            a *= ang_k
            if tr is not None:                                  # far back (deep in the stage) or an animal: a smaller
                try:                                            # step round, or the sideways move swings it out of shot
                    zt = float(tr.z_at(t + 0.3))
                except Exception:                               # noqa: BLE001
                    zt = 0.0
                if zt > 450:
                    a *= max(0.25, 1.0 - (zt - 450.0) / 700.0)
                if getattr(tr.cdef, "kind", "human") != "human":
                    a *= 0.5
            if tgt in tl.tracks:
                a = clear_angle(tl, tgt, t + 0.3, a, typ)     # nobody standing between the lens and the face
            c["angle"] = round(a, 1)
        # ---- 6. moves with weight
        if feat and "handheld" not in c:
            c["handheld"] = 0.0 if hh_user is None else round(float(hh_user) * 0.5, 3)   # dolly / crane, not a shoulder
        if "handheld" not in c and not c.get("locked"):
            hh = st["hh0"] + st["hht"] * tens
            if hh_user is not None:
                hh = float(hh_user) * (0.6 + 0.8 * tens)
            if size in ("EW", "W"):
                hh *= 0.5
            c["handheld"] = round(hh, 3)
        if auto and tens > 0.78 and size in ("CU", "ECU", "MCU") and typ != "slow_push":
            c["drift"] = None                                   # the peak: the camera holds its breath
            c["locked"] = True
        elif feat and auto and c.get("drift") is None and not c.get("locked") and size in ("EW", "W"):
            c["drift"] = "in"                                   # a wide keeps a very slow push (parallax)
        elif not feat and auto and tens < 0.3 and size in ("W", "FS", "MS") and c.get("drift") is None \
                and not c.get("locked"):
            c["drift"] = "in"                                   # calm: a slow dolly keeps it alive
        # ---- 7. foreground framing now and then
        if "foreground" not in c and fg_every and size in (("EW", "W", "FS") if feat else ("EW", "W", "FS", "MS")) \
                and typ not in (
                "overhead", "drone", "over_shoulder", "reverse"):
            n_fg += 1
            if n_fg % fg_every == 0:
                side = "left"
                if tr is not None:
                    try:
                        side = "left" if tr.facing_at(t + 0.2) >= 0 else "right"   # behind their back, look room free
                    except Exception:
                        pass
                c["foreground"] = {"kind": fg_kind, "side": side, "seed": idx}
        elif isinstance(c.get("foreground"), str):
            k = c["foreground"].lower()
            c["foreground"] = None if k in ("none", "off", "no") or (fg_kind is None and k in ("auto", "yes", "true")) else \
                {"kind": fg_kind if k in ("auto", "yes", "true") else k, "side": c.get("foreground_side", "left"),
                 "seed": idx}
        out.append((t, c))
    return out


def min_shot(tl, t, opts):
    """How long a shot should last at least now (seconds): calm = long takes, tension = quick cuts."""
    curve = getattr(tl, "_tension", None)
    if curve is None:
        curve = tension_curve(tl)
        tl._tension = curve
    tens = tension_at(curve, t)
    if is_feature(opts):                                    # a feature holds its shots: fewer, longer takes
        return max(2.6, (3.8 - 1.2 * tens) * PACE.get(str(opts.get("pace", "normal")).lower(), 1.0))
    base = 3.0 - 1.7 * tens
    return max(1.1, base * PACE.get(str(opts.get("pace", "normal")).lower(), 1.0))
