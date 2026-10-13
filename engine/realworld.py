"""Real-world physics for every story: one set of rules for weight, the sun, the wind and falling things.

CLASSROOM videos ("physics": "real") get every rule at full strength. STORY videos get only what a good video
needs: sun shadows, the shared wind, falling things and weight in the walk, a light lean when starting / stopping
- no lean into curves and the usual walk timing (scaled by the story's "exaggeration"). Education videos ("physics": "real",
or the ⚛ Physics lesson button) are always PURE physics: exaggeration is 1.0 and cannot be raised, no extra
squash, no stretched jumps, no cartoon wind-ups - what students see is correct.

    weight    body_mass(cdef), heaviness(cdef): heavy people step slower and sink a little, light ones
              bounce; starting / stopping takes time (momentum), the body leans with the acceleration,
              jump height and landing from the body's weight
    sun       sun(time): height and side of the sun -> shadow length / direction, light colour, how
              warm and low the light is; bounce light from the ground onto people
    wind      Wind: one scene wind (strength, direction, gusts) for trees, grass, clothes, hair, flags,
              smoke, dust and rain - all moved the same way at the same moment
    falling   material(o): mass, bounciness, breaks or not, air drag (a leaf floats, a sack thuds)
              and the sound by weight and surface
"""
import math

from .util import clamp, stable_hash

M = 175.0            # story units per metre (an adult is 300 units ~ 1.7 m)
G = 9.8              # m/s²
G_U = G * M          # gravity in story units / s²


def is_real(spec):
    """Pure-physics (education) mode from story / scene settings."""
    return str((spec or {}).get("physics", "story")).lower() in ("real", "school", "true", "on", "yes", "lab")


def exaggeration_of(spec):
    """The story's exaggeration (0.3 .. 2), always 1.0 in pure-physics mode."""
    if is_real(spec):
        return 1.0
    try:
        return max(0.3, min(2.0, float((spec or {}).get("exaggeration", 1.0))))
    except (TypeError, ValueError):
        return 1.0


# ============================================================================ weight and momentum
ADULT_KG = 65.0


def body_mass(cdef):
    """kg: an adult of normal build is 65 kg; size goes with the cube of height, build widens the body."""
    if getattr(cdef, "kind", "human") != "human":
        sp = getattr(cdef, "animal", None) or {}
        return float(sp.get("mass") or 0) or 40.0 * max(0.2, float(getattr(cdef, "scale", 1.0))) ** 3
    s = max(0.3, float(getattr(cdef, "scale", 1.0) or 1.0))
    b = float(getattr(cdef, "build", 1.0) or 1.0)
    m = ADULT_KG * s ** 3 * b ** 1.6
    if getattr(cdef, "age", "adult") == "old":
        m *= 0.95
    return m


def heaviness(cdef):
    """1 = an ordinary adult, 0.5 = a light child, 1.8 = a heavy person (only humans; animals 1)."""
    if getattr(cdef, "kind", "human") != "human":
        return 1.0
    return clamp(body_mass(cdef) / ADULT_KG, 0.35, 2.0)


def gait(cdef, ex=1.0):
    """How the weight changes walking / running (multipliers on the normal gait):
    speed (heavy = slower), bob (light = bouncier, heavy = flatter), sink (heavy = knees a little more bent)."""
    h = heaviness(cdef)
    d = h - 1.0
    return {
        "speed": clamp(1.0 - 0.18 * d, 0.82, 1.08),
        "bob": clamp(1.0 - 0.9 * d * ex, 0.4, 1.9),
        "clear": clamp(1.0 - 0.35 * d * ex, 0.7, 1.3),
        "sink": clamp(6.0 * d, -3.0, 6.0),             # hip lower by this much (units): bent knees under weight
        "swing": clamp(1.0 - 0.15 * d, 0.85, 1.1),
    }


def start_stop(cdef, aname, speed, ex=1.0, real=False):
    """(seconds to speed up, seconds to slow down) for a walk / run at this speed (units/s): momentum.
    A heavy body needs longer to get going and to stop; a runner takes a few steps to stop."""
    if aname not in ("walk", "run", "approach", "retreat"):
        return None
    h = heaviness(cdef)
    v = speed / M                                        # m/s
    a_go = 2.2 / h ** 0.5 if aname != "run" else 3.4 / h ** 0.5      # m/s² a person can push off with
    a_stop = 3.0 / h ** 0.5 if aname != "run" else 4.0 / h ** 0.5
    ta, tb = v / a_go, v / a_stop
    if not real:                                         # story video: the usual timing, only a touch of weight
        k = clamp(h ** 0.3, 0.85, 1.2) / ex
        ta, tb = ((0.25, 0.35) if aname == "run" else (0.35, 0.5))
        ta, tb = ta * k, tb * k
    if aname == "run":
        return clamp(ta, 0.25, 1.2), clamp(tb, 0.35, 1.0)
    return clamp(ta, 0.2, 0.7), clamp(tb, 0.3, 0.8)


def lean_from_accel(a_units, ex=1.0, real=False):
    """Body lean in degrees for an acceleration along the facing direction (units/s²): the body tips so the
    push of the feet goes through the centre of mass (tan(lean) = a / g), a bit less than the full angle
    because the legs and arms also take it."""
    a = a_units / M
    deg = math.degrees(math.atan2(a, G)) * 0.5
    if not real:                                         # story video: a lighter lean (just enough to read)
        deg *= 0.5 * ex
    return clamp(deg, -16.0, 14.0)


def bank_from_turn(v_units, curvature, ex=1.0, real=False):
    """Lean into a curve (degrees, + = toward the inside): tan(bank) = v² / (r g)."""
    if curvature <= 1e-9:
        return 0.0
    v = v_units / M
    r = 1.0 / curvature / M
    deg = math.degrees(math.atan2(v * v, r * G))
    if not real:
        deg *= ex
    return clamp(deg, 0.0, min(20.0, 5.0 * v))           # people do not tip far at walking pace


def jump(cdef, ex=1.0, real=False, height=None, g=G):
    """(height in units, seconds) of a standing jump: a heavy body jumps lower, a light one higher; the time
    in the air is the real one, t = 2·√(2h/g) (the take-off crouch and the landing take the rest)."""
    if height is None:                                  # legs as strong as the body is big; extra fat weighs it down
        size = max(0.3, float(getattr(cdef, "scale", 1.0) or 1.0))
        fat = max(0.5, float(getattr(cdef, "build", 1.0) or 1.0)) ** 1.6
        height = 120.0 * size * fat ** -0.6 * (1.0 if real else ex ** 0.5)
        height *= G / max(0.3, g)                     # the same push: 6x higher on the Moon (engine/galaxy.py)
    height = clamp(float(height), 5.0, 1500.0)
    air = 2.0 * math.sqrt(2.0 * height / (max(0.3, g) * M))
    dur = air / 0.62                                     # the air part of a_jump is 62 % of the action
    return height, clamp(dur, 0.6, 6.0)


def landing_bend(cdef, ex=1.0):
    """Extra knee bend on landing (0..1): heavier bodies sink deeper."""
    return clamp(0.35 + 0.45 * (heaviness(cdef) - 1.0), 0.1, 0.9) * min(1.3, ex)


# ============================================================================ the sun
# time word -> (height of the sun in degrees, side: -1 = left (morning, east) .. +1 = right (evening, west),
#               light colour, warmth 0..1)
SUN_TIMES = {
    "dawn": (4.0, -1.0, (1.0, 0.62, 0.42), 1.0),
    "sunrise": (6.0, -1.0, (1.0, 0.66, 0.42), 1.0),
    "morning": (24.0, -0.85, (1.0, 0.86, 0.66), 0.6),
    "day": (52.0, -0.35, (1.0, 0.97, 0.9), 0.15),
    "noon": (78.0, 0.1, (1.0, 1.0, 0.96), 0.0),
    "afternoon": (38.0, 0.6, (1.0, 0.93, 0.8), 0.3),
    "golden_hour": (12.0, 0.85, (1.0, 0.74, 0.45), 0.9),
    "evening": (14.0, 0.85, (1.0, 0.76, 0.5), 0.8),
    "sunset": (5.0, 0.95, (1.0, 0.58, 0.36), 1.0),
    "dusk": (2.0, 0.95, (0.85, 0.55, 0.55), 0.7),
    "night": (40.0, 0.3, (0.7, 0.8, 1.0), 0.0),       # the moon: a cool light, soft short shadows
    "midnight": (55.0, 0.3, (0.65, 0.75, 1.0), 0.0),
}


def sun(time_word=None):
    """Where the sun is and what its light is like:
    elev (deg), side (-1..1), dir (unit vector toward the sun: x right, y up, z into the picture),
    color, warmth, shadow (length of a shadow per unit of height, capped), night."""
    t = str(time_word or "day").lower().strip().replace(" ", "_")
    elev, side, col, warm = SUN_TIMES.get(t, SUN_TIMES["day"])
    e = math.radians(elev)
    # the sun is a little behind the camera (z < 0) so shadows fall into the picture and faces stay lit
    hx, hz = side, -0.55
    n = math.hypot(hx, hz) or 1.0
    c = math.cos(e)
    d = (hx / n * c, math.sin(e), hz / n * c)
    return {"elev": elev, "side": 1.0 if side >= 0 else -1.0, "dir": d, "color": col, "warmth": warm,
            "shadow": clamp(1.0 / math.tan(max(e, math.radians(3.0))), 0.15, 4.0),
            "night": t in ("night", "midnight")}


OVERCAST = ("rain", "storm", "cyclone", "snow", "fog", "mist", "overcast", "cloudy", "drizzle")


def shadow_2d(time_word=None, weather=None):
    """(stretch, shift, alpha) for a flat ground shadow: stretch = how long it is along the ground (x 1 = round),
    shift = which way it points (+ = to the right, away from a sun on the left), alpha (fainter at night).
    Under clouds the light comes from the whole sky: a soft round shadow right under the feet."""
    if str(weather or "").lower() in OVERCAST:
        return 1.0, 0.0, 0.7
    s = sun(time_word)
    L = s["shadow"]
    stretch = clamp(0.8 + 0.55 * L, 0.9, 3.0)
    shift = -s["dir"][0] / max(0.05, math.hypot(s["dir"][0], s["dir"][2])) * clamp(L, 0.0, 3.0)
    return stretch, shift, (0.6 if s["night"] else 1.0)


# the 2D renderer reads this for every shadow it draws (set per scene, like code3d.CONTACT); 3D: how dark
SHADOW = [(1.0, 0.0, 1.0)]
SHADOW_3D = [1.0]


def set_time(time_word, weather=None):
    SHADOW[0] = shadow_2d(time_word, weather)


# ============================================================================ the wind
WEATHER_WIND = {"cyclone": 6.0, "storm": 2.2, "windy": 2.8, "wind": 2.8, "rain": 1.4, "snow": 1.1,
                "dust_storm": 4.0, "sandstorm": 4.0}
WIND_WORDS = {"calm": 0.0, "still": 0.0, "none": 0.0, "breeze": 1.0, "light": 1.0, "gentle": 0.8,
              "windy": 2.8, "strong": 3.2, "gale": 4.5, "storm": 4.0, "cyclone": 6.0}


class Wind:
    """One wind for the whole scene. strength: 0 calm, 1 breeze, 2.8 windy, 6 cyclone (the old scale);
    direction: +1 blows to the right, -1 to the left; gusts 0..1 (stronger puffs that travel across the
    scene, so trees on the left bend a moment before the ones on the right)."""

    def __init__(self, strength=1.0, direction=1.0, gusts=None, seed=0):
        self.strength = max(0.0, float(strength))
        self.direction = 1.0 if float(direction) >= 0 else -1.0
        self.gusts = clamp(float(gusts if gusts is not None else (0.25 + 0.12 * self.strength)), 0.0, 1.0)
        self.seed = (seed % 97) * 0.37

    @classmethod
    def from_spec(cls, spec, weather=None, seed=0):
        """From a scene / background: "wind": 2 | "breeze" | {"strength": 2, "direction": "left", "gusts": 0.5};
        else from the weather (windy, storm, cyclone ...)."""
        spec = spec or {}
        w = spec.get("wind")
        base = WEATHER_WIND.get(str(weather or spec.get("weather") or "").lower(), 1.0)
        strength, direction, gusts = base, 1.0, None
        if isinstance(w, dict):
            v = w.get("strength", w.get("speed", base))
            strength = WIND_WORDS.get(str(v).lower(), None) if isinstance(v, str) else v
            strength = base if strength is None else strength
            direction = _dir(w.get("direction", w.get("to", 1)))
            gusts = w.get("gusts")
        elif isinstance(w, str):
            parts = w.lower().replace(",", " ").split()
            for p in parts:
                if p in WIND_WORDS:
                    strength = WIND_WORDS[p]
                elif p in ("left", "right", "west", "east"):
                    direction = _dir(p)
        elif isinstance(w, (int, float)) and not isinstance(w, bool):
            strength = float(w)
        if isinstance(gusts, str):
            gusts = {"none": 0.0, "low": 0.15, "some": 0.35, "strong": 0.7, "high": 0.7}.get(gusts.lower(), None)
        try:
            return cls(float(strength), direction, gusts, seed)
        except (TypeError, ValueError):
            return cls(base, 1.0, None, seed)

    def gust(self, t, x=0.0):
        """0..1 extra push of a gust at time t and place x: gusts travel with the wind (about 6 m/s)."""
        if self.gusts <= 0:
            return 0.0
        u = t - self.direction * x / (6.0 * M) + self.seed
        g = 0.5 * math.sin(u * 0.53) + 0.3 * math.sin(u * 1.27 + 1.3) + 0.2 * math.sin(u * 2.9 + 0.4)
        return max(0.0, g) ** 1.5 * self.gusts

    def at(self, t, x=0.0):
        """Signed wind push now at x (strength units, + = to the right): steady part + gusts."""
        return self.direction * self.strength * (1.0 + 1.6 * self.gust(t, x))

    def speed(self, t, x=0.0):
        """Air speed in story units / s (signed): a breeze is ~0.5 m/s of push on cloth, a cyclone fierce."""
        return self.at(t, x) * 90.0

    def sway(self, t, x=0.0, freq=1.0, phase=0.0):
        """A plant's sideways bend in units of its normal breeze swing (1 = the old gentle sway): it flutters,
        and in a real wind it leans downwind - more in a gust, which reaches the left trees before the right
        ones when the wind blows to the right. + = bends to the right."""
        s = self.strength
        g = self.gust(t, x)
        lean = max(0.0, s - 1.0) * 1.3 * math.sqrt(s) * (1.0 + 1.2 * g) + 0.6 * min(s, 1.0) * g
        flutter = math.sin(t * freq * (0.9 + 0.3 * max(0.0, s - 1.0)) + phase + x * 0.01) * math.sqrt(max(s, 0.0))
        return self.direction * lean + flutter

    def drift(self):
        """How fast clouds / smoke / dust / rain drift sideways (x the old breeze speed), signed."""
        return self.direction * max(0.0, self.strength) ** 1.5


def _dir(v):
    if isinstance(v, str):
        return -1.0 if v.lower() in ("left", "west", "-1", "to_left") else 1.0
    try:
        return -1.0 if float(v) < 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


# the renderers read the scene's wind here (set per scene, like SHADOW)
WIND = [Wind()]


def set_wind(w):
    WIND[0] = w if isinstance(w, Wind) else Wind()


def wind():
    return WIND[0]


def sway(t, x=0.0, freq=1.0, phase=0.0):
    """The scene wind's sway at t / x (see Wind.sway) - one call for every tree, bush and grass tuft."""
    return WIND[0].sway(t, x, freq, phase)


def set_scene(bg, sc=None):
    """Before a frame is drawn: the scene's sun (2D shadows) and wind become the current ones. The wind is
    worked out once per place + weather (weather can change during the scene)."""
    spec = dict(getattr(bg, "spec", None) or {})
    if sc is not None and isinstance(getattr(sc, "spec", None), dict):
        for k in ("wind", "time"):
            if sc.spec.get(k) is not None and spec.get(k) is None:
                spec[k] = sc.spec[k]
    weather = getattr(bg, "weather", None)
    wx = getattr(bg, "wx", None) or {}
    changing = bool(wx.get("changing"))
    key = (id(bg), weather, round(wx.get("wind", 0.0), 2) if changing else None)
    cache = getattr(bg, "_rw_wind", None)
    if cache is None or cache[0] != key:
        w = Wind.from_spec(spec, weather, seed=stable_hash(str(spec.get("preset", ""))) % 997)
        if changing and not _explicit_strength(spec.get("wind")):
            w.strength = max(0.0, float(wx["wind"]))      # the wind picks up as the storm comes
        bg._rw_wind = cache = (key, w)
        try:
            bg.wind = max(0.0, w.strength)                # the old scalar: how strong (the 2D places read it)
        except AttributeError:
            pass
    set_wind(cache[1])
    set_time(time_word(bg), weather)
    if changing:                                         # clouds over the sun: shadows fade and go round
        c = clamp(wx.get("cloud", 0.0), 0.0, 1.0)
        st, sh, a = SHADOW[0]
        k = clamp((c - 0.3) / 0.6, 0.0, 1.0)
        SHADOW[0] = (st + (1.0 - st) * k, sh * (1.0 - k), a * (1.0 - 0.45 * k))
    SHADOW_3D[0] = 1.0 - 0.6 * clamp((wx.get("cloud", 0.0) - 0.3) / 0.6, 0.0, 1.0) if changing else 1.0


def _explicit_strength(w):
    if isinstance(w, dict):
        return any(k in w for k in ("strength", "speed"))
    return w is not None


def time_word(bg):
    """The exact time of day of a place ("golden_hour", "dawn" ... not only the sky it maps to)."""
    raw = str((getattr(bg, "spec", None) or {}).get("time") or "").lower().strip().replace(" ", "_")
    if raw in SUN_TIMES:
        return raw
    return str(getattr(bg, "time", "day") or "day").lower()


# ============================================================================ falling things
# material -> density-ish mass per size, bounciness (coefficient of restitution), breaks?, air drag
# (0 = none .. 1 = floats down like a leaf), the sound when it lands on hard / soft ground
MATERIALS = {
    "rubber": dict(kg=0.4, e=0.75, breaks=False, drag=0.05, hard="boing", soft="thud"),
    "clay": dict(kg=2.0, e=0.0, breaks=True, drag=0.0, hard="crash", soft="crash"),
    "glass": dict(kg=0.6, e=0.0, breaks=True, drag=0.0, hard="crash", soft="crash"),
    "stone": dict(kg=3.0, e=0.15, breaks=False, drag=0.0, hard="knock", soft="thud"),
    "metal": dict(kg=2.5, e=0.3, breaks=False, drag=0.0, hard="clang", soft="thud"),
    "wood": dict(kg=2.0, e=0.25, breaks=False, drag=0.02, hard="knock", soft="thud"),
    "sack": dict(kg=25.0, e=0.0, breaks=False, drag=0.02, hard="sack", soft="sack"),
    "fruit": dict(kg=0.2, e=0.1, breaks=False, drag=0.02, hard="thud", soft="thud"),
    "paper": dict(kg=0.05, e=0.0, breaks=False, drag=0.85, hard="rustle", soft="rustle"),
    "leaf": dict(kg=0.01, e=0.0, breaks=False, drag=1.0, hard="rustle", soft="rustle"),
    "feather": dict(kg=0.005, e=0.0, breaks=False, drag=1.0, hard=None, soft=None),
    "cloth": dict(kg=0.3, e=0.0, breaks=False, drag=0.55, hard="thud", soft="thud"),
}
TYPE_MATERIAL = {
    "ball": "rubber", "football": "rubber", "balloon": "rubber", "pot": "clay", "matka": "pot", "vase": "clay",
    "jar": "glass", "bottle": "glass", "glass": "glass", "plate": "clay", "cup": "clay", "egg": "clay",
    "stone": "stone", "rock": "stone", "boulder": "stone", "pebble": "stone", "brick": "stone",
    "bucket": "metal", "pan": "metal", "can": "metal", "coin": "metal", "key": "metal", "sword": "metal",
    "log": "wood", "stick": "wood", "crate": "wood", "box": "wood", "chest": "wood", "barrel": "wood",
    "book": "wood", "sack": "sack", "bag": "sack", "rice_bag": "sack", "apple": "fruit", "mango": "fruit",
    "coconut": "fruit", "banana": "fruit", "paper": "paper", "letter": "paper", "kite": "paper",
    "leaf": "leaf", "leaves": "leaf", "petal": "leaf", "flower": "leaf", "feather": "feather",
    "cloth": "cloth", "dupatta": "cloth", "shirt": "cloth", "hat": "cloth",
}
SOFT_GROUND = ("sand", "grass", "snow", "mud", "dirt", "hay")


def material(o):
    """The material name of an object (PropTrack): "material" in its spec, else from its type / id / traits."""
    spec = getattr(o, "spec", {}) or {}
    m = str(spec.get("material") or "").lower()
    if m in MATERIALS:
        return m
    words = f"{getattr(o, 'type', '')} {getattr(o, 'id', '')}".lower().replace("-", "_").split()
    for w in words:
        for part in [w] + w.split("_"):
            got = TYPE_MATERIAL.get(part)
            if got in MATERIALS:
                return got
            if got in TYPE_MATERIAL:
                return TYPE_MATERIAL[got]
    try:
        from . import objects
        T = objects.traits(o)
    except Exception:                                    # noqa: BLE001
        T = set()
    if "break" in T:
        return "clay"
    if "heavy" in T:
        return "stone"
    if "round" in T:
        return "rubber"
    return "wood"


def mass_of(o):
    """kg: material x size (a 60-unit pot ~ 2 kg, a 250-unit boulder ~ hundreds)."""
    spec = getattr(o, "spec", {}) or {}
    if spec.get("mass") is not None:
        try:
            return float(spec["mass"])
        except (TypeError, ValueError):
            pass
    mat = MATERIALS[material(o)]
    try:
        from . import objects
        w, h = objects.size(o)
    except Exception:                                    # noqa: BLE001
        w, h = 50.0, 50.0
    vol = (max(w, 5.0) / 60.0) * (max(h, 5.0) / 60.0) * (min(w, h) / 60.0 if min(w, h) > 0 else 1.0)
    return max(0.003, mat["kg"] * vol)


def fall_time(height_units, drag=0.0, g=G):
    """Seconds to fall this far: free fall t = √(2h/g) for heavy things; a leaf / feather reaches its terminal
    speed (about 1 m/s) at once and drifts down slowly (with no air: drag 0, it falls like a stone)."""
    h = max(0.0, height_units)
    t_free = math.sqrt(2.0 * h / (max(0.05, g) * M))
    if drag <= 0.0:
        return t_free
    v_term = (1.0 - drag) * 25.0 + drag * 0.9            # m/s
    t_term = h / M / v_term
    return max(t_free, t_term)


def landing_sound(o, surface, speed_units=None):
    """(sound name, volume) for an object landing on a surface: by its material and weight."""
    mat = MATERIALS[material(o)]
    soft = str(surface or "") in SOFT_GROUND
    name = mat["soft"] if soft else mat["hard"]
    if surface == "water":
        name = "splash" if mass_of(o) > 2.0 else "plop"
    if name is None:
        return None, 0.0
    m = mass_of(o)
    vol = clamp(0.35 + 0.18 * math.log10(max(m, 0.01) * 10.0), 0.15, 1.0)
    if soft:
        vol *= 0.75
    if speed_units is not None:
        vol *= clamp(speed_units / (5.0 * M), 0.4, 1.2)
    return name, max(0.08, vol)
