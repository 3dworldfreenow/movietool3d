"""Scene timeline: turns the JSON event list into per-character motion tracks, speech clips,
sound effects, props & vehicles, emotion icons, particle effects, crowds and camera commands.

Event timing rules (so an AI-written script "just works"):
  * "at": <seconds>        -> absolute time inside the scene
  * "with": "prev"         -> starts together with the previous event
  * "after": <seconds>     -> starts <seconds> after the previous event ends
  * otherwise              -> starts when the previous event ends (+ small gap)
"""
import math
import re
import random

from . import animals
from . import realworld
from .poses import ACTIONS, ActionSpec, resolve_action, blend, a_jump, FACES, WALK_STRIDE, RUN_STRIDE, mood_gait, mood_stride
from .depth import Z_NAMES, mood_name
from .util import clamp, smoothstep, stable_hash, ease

SPEECH_GAP = 0.25
EMOTION_ALIASES = {"joy": "happy", "smile": "happy", "excited": "happy", "cheerful": "happy", "love": "happy",
                   "mad": "angry", "furious": "angry", "upset": "sad", "unhappy": "sad",
                   "shock": "surprised", "shocked": "surprised", "fear": "scared", "afraid": "scared",
                   "worried": "scared", "nervous": "scared", "laugh": "laughing", "cry": "crying",
                   "sleepy": "sleeping", "curious": "thinking", "confused": "thinking", "calm": "neutral",
                   # words AIs often write -> the nearest face / voice
                   "serious": "thinking", "focused": "thinking", "praying": "thinking", "prayerful": "thinking",
                   "wise": "thinking", "doubtful": "thinking", "puzzled": "thinking", "suspicious": "thinking",
                   "determined": "neutral", "firm": "neutral", "respectful": "neutral", "stern": "angry",
                   "proud": "happy", "confident": "happy", "brave": "neutral", "hopeful": "happy",
                   "amazed": "surprised", "astonished": "surprised", "stunned": "surprised", "wonder": "surprised",
                   "awe": "surprised", "awed": "surprised", "joyful": "happy", "glad": "happy", "delighted": "happy",
                   "gentle": "happy", "kind": "happy", "loving": "happy", "caring": "happy", "grateful": "happy",
                   "admiring": "happy", "playful": "happy", "relieved": "happy", "blessed": "happy",
                   "anxious": "scared", "tense": "scared", "terrified": "scared", "panic": "scared",
                   "horrified": "scared", "helpless": "sad", "heartbroken": "crying", "lonely": "sad",
                   "tired": "sad", "disappointed": "sad", "guilty": "sad", "ashamed": "sad", "sorrowful": "sad",
                   "annoyed": "angry", "irritated": "angry", "frustrated": "angry", "rage": "angry",
                   "jealous": "angry", "laughing": "laughing", "amused": "laughing", "funny": "laughing"}

VEHICLES = {
    #        speed, seat offsets (along facing, from centre), floor height for riders, engine sound
    "car":    dict(speed=430, seats=[95, -95], floor=10, sound="engine"),
    "jeep":   dict(speed=450, seats=[95, -95], floor=10, sound="engine"),
    "bus":    dict(speed=320, seats=[380, 190, 20, -150, -320], floor=58, sound="engine"),
    "auto":   dict(speed=330, seats=[120, -60], floor=34, sound="engine"),
    "bike":   dict(speed=260, seats=[-12], floor=0, sound=None),
    "boat":   dict(speed=170, seats=[110, -90], floor=26, sound="splash"),
    "rocket": dict(speed=500, seats=[0], floor=245, sound="rocket"),
    "rowboat": dict(speed=120, seats=[70, -70], floor=18, sound="splash"),
    "fishing_boat": dict(speed=150, seats=[170, 30], floor=30, sound="engine"),
    "sailboat": dict(speed=200, seats=[90, -70], floor=26, sound=None),
    "ship": dict(speed=180, seats=[420, 220, 20, -180, -380], floor=205, sound="engine"),
    "paper_boat": dict(speed=60, seats=[0], floor=0, sound=None),
}
# pushing: how many people it takes, and half the length (story units) to stand at the back bumper
VEHICLE_WEIGHT = {"bike": 1, "car": 2, "jeep": 2, "auto": 1, "bus": 5, "rowboat": 2, "boat": 3, "rocket": 9,
                  "fishing_boat": 4, "sailboat": 3, "ship": 30, "paper_boat": 1}
VEHICLE_HALF = {"bike": 95, "car": 245, "jeep": 245, "auto": 175, "bus": 570, "boat": 230, "rowboat": 170,
                "rocket": 80}
VEHICLE_ALIASES = {"rickshaw": "auto", "autorickshaw": "auto", "auto_rickshaw": "auto", "taxi": "car",
                   "van": "car", "safari": "jeep", "land_rover": "jeep", "bicycle": "bike", "cycle": "bike", "scooter": "bike",
                   "motorbike": "bike", "spaceship": "rocket", "school_bus": "bus", "ferry": "ship",
                   "steamer": "ship", "cruise": "ship", "row_boat": "rowboat", "canoe": "rowboat", "kayak": "rowboat",
                   "fishing": "fishing_boat", "trawler": "fishing_boat", "sail": "sailboat", "yacht": "sailboat",
                   "paperboat": "paper_boat", "nav": "boat", "naav": "boat"}
WATER_VEHICLES = ("boat", "rowboat", "fishing_boat", "sailboat", "ship", "paper_boat")


def vinfo(v):
    """Speed, seats, floor and sound of vehicle v - built in, or read from a PICTURE used as a vehicle
    (a bullock cart, a tractor ...: "vehicles": [{"id": "cart1", "type": "<picture>", "seats": 2}])."""
    if v.vtype != "picture":
        return VEHICLES[v.vtype]
    got = getattr(v, "_vinfo", None)
    if got:
        return got
    from . import images
    m = images.info(v.type) or {}
    h = float(v.spec.get("height") or m.get("height") or 240)
    w = h * (m.get("w") or 1) / float(m.get("h") or 1)
    ride = m.get("ride") if isinstance(m.get("ride"), dict) else None
    if ride:                                             # a 3D / code vehicle that says how it is ridden (RIDE)
        k = h / float(m.get("height") or h)
        pts = []
        for p in ride.get("seats") or [[0.0, ride.get("seat_height", 60.0), 0.0]]:
            p = p if isinstance(p, (list, tuple)) else [p, ride.get("seat_height", 60.0), 0.0]
            pts.append((float(p[0]) * k, float(p[1]) * k, float(p[2]) * k))
        pose = ride.get("pose", "sit")
        got = dict(speed=float(v.spec.get("speed", ride.get("speed", 220))), seats=[p[0] for p in pts],
                   seat_y=[p[1] for p in pts], seat_z=[p[2] for p in pts], floor=0.0, seat=pts[0][1],
                   pose=pose, sound=v.spec.get("sound", ride.get("sound")), w=w, h=h)
        v._vinfo = got
        return got
    seats = v.spec.get("seats", m.get("seats", 2))
    if isinstance(seats, (int, float)):
        n = max(1, int(seats))
        seats = [0.0] if n == 1 else [0.28 - 0.56 * k / (n - 1) for k in range(n)]
    got = dict(speed=float(v.spec.get("speed", m.get("speed", 200))), seats=[float(f) * w for f in seats],
               floor=float(v.spec.get("seat_height", m.get("seat_height", 0.42))) * h,
               sound=v.spec.get("sound", m.get("sound")), w=w, h=h)
    v._vinfo = got
    return got


def seat_x(v, seat, t):
    """World x of a seat of vehicle v at time t (side view)."""
    vx, vy, vf = v.pos(t)
    seats = vinfo(v)["seats"]
    return vx + vf * seats[min(seat, len(seats) - 1)] * v.scale


def boat_bob(v, t):
    """Vertical bob of a floating vehicle (same formula used for drawing and for its passengers)."""
    amp = v.spec.get("_sea", 0) if v.vtype in WATER_VEHICLES else 0
    if not amp and v.vtype != "boat":
        return 0.0
    return (2.0 + amp * 0.45) * math.sin(t * 2.2 + (stable_hash(v.id) % 7))

def story_dz(z, dZ):
    """story depth z moved by dZ real 3D units (away from the camera): the depth scale is not even."""
    if abs(dZ) < 1e-6:
        return z
    try:
        from .world3d import Z_of_z
    except Exception:
        return z
    lo, hi = 0.0, 3000.0
    want = Z_of_z(z) + dZ
    for _ in range(40):
        mid = (lo + hi) / 2
        if Z_of_z(mid) < want:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


RIDE_KIND = {"pedal": "bike", "sit": "car", "stand": "ship", "row": "rowboat"}   # RIDE pose -> rider pose
HIP_ON_SEAT = {"bike": 126.0, "car": 82.5, "ship": 0.0, "rowboat": 82.5}          # adult hip height in that pose
RIDE_WORDS = ("ride", "drive", "board", "get_in", "enter_vehicle", "cycle", "sit_in", "fly_rocket")
OUT_WORDS = ("get_out", "exit_vehicle", "get_off", "leave_vehicle")
# things characters do WITH objects (engine/objects.py)
OBJ_WORDS = {
    "push": "push", "shove": "push", "roll": "roll", "pull": "pull", "drag": "pull",
    "throw": "throw", "toss": "throw", "hurl": "throw", "fling": "throw", "throw_stone": "throw",
    "carry": "carry", "lift": "carry",
    "sit_on": "sit_on", "stand_on": "stand_on", "climb_on": "stand_on", "step_on": "stand_on",
    "climb": "climb", "climb_up": "climb", "climb_tree": "climb",
    "get_down": "get_down", "climb_down": "get_down", "jump_down": "get_down", "come_down": "get_down",
    "hide": "hide", "hide_behind": "hide", "take_cover": "hide", "duck": "hide", "peek": "peek",
    "come_out": "come_out", "unhide": "come_out",
    "open": "open", "close": "close", "shut": "close", "break": "break", "smash": "break",
    "turn_on": "turn_on", "switch_on": "turn_on", "light": "turn_on", "light_up": "turn_on", "ignite": "turn_on",
    "turn_off": "turn_off", "switch_off": "turn_off", "blow_out": "turn_off", "put_out": "turn_off",
    "use": "use", "change": "use",
    # putting a thing down where it belongs: on a table / shelf / the bed, in a bag, on the floor over there
    "put": "put", "place": "put", "keep": "put", "set": "put", "put_on": "put", "put_in": "put", "store": "put",
    "put_back": "put", "keep_back": "put", "rakh": "put", "rakho": "put", "rakhna": "put", "rakh_do": "put",
    # through the door of a building (3D things drawn with pen.door): in, and out again
    "enter": "enter", "go_inside": "enter", "go_in": "enter", "go_into": "enter", "walk_in": "enter",
    "enter_building": "enter", "go_home": "enter",
    "come_out_of": "emerge", "exit_from": "emerge", "walk_out_of": "emerge", "step_out": "emerge",
    "come_in": "emerge", "come_in_through": "emerge", "come_outside": "emerge",
}
SEAT_KEEP = ("talk", "wave", "point", "think", "laugh", "cry", "sad", "clap", "angry", "surprised", "scared", "shrug",
             "nod", "look_around", "turn", "idle", "pick", "give", "drop", "bow", "eat", "sing", "struggle")
LEG_KEYS = ("ln_t", "ln_s", "lf_t", "lf_s", "lift", "rot")
OBJ_MAYBE = {"sit": "sit_on", "stand": "stand_on", "kick": "kick", "hit": "break", "pick": "carry",
             "pick_up": "carry", "grab": "carry", "take": "carry"}
OBJ_NEED = {"push": "movable", "pull": "movable", "roll": "movable", "throw": "movable", "carry": "movable",
            "kick": "movable", "sit_on": "sit", "stand_on": "stand", "climb": "climb", "hide": "hide",
            "open": "open", "close": "open", "break": "break", "turn_on": "switch", "turn_off": "switch"}
WATER_WORDS = ("water", "river", "lake", "sea", "pond", "into_water", "into_the_river")
ICONS = ("!", "?", "heart", "idea", "sweat", "anger", "stars", "music", "zzz", "exclaim", "question",
         "blush", "tears", "shock", "gloom")
AUTO_ICON = {"surprised": "!", "scared": "sweat", "angry": "anger", "think": "?", "fall": "stars", "hug": "heart",
             "shout": "!", "fight": "anger", "pull_hand_back": "!"}
# small actions done on the spot during a conversation: without their own "facing" they keep facing the
# person being talked with (a bow to the king, a nod to the guru), not wherever the last walk pointed
CONVO_KEEP = ("talk", "wave", "point", "think", "laugh", "cry", "sad", "clap", "angry", "surprised", "scared",
              "shrug", "nod", "bow", "namaste", "happy", "celebrate", "stand", "idle", "look_around", "sing",
              "pray", "bless", "salute", "worried", "gloom", "smile", "shy", "proud", "listen")
# actions that turn toward the character / object they are aimed at ("target": "maya")
FACE_TARGET = ("look_at", "look_up", "look_down", "fight", "touch", "reach", "shout", "stop", "shove", "talk", "point",
               "give", "wave", "retreat", "stumble", "angry", "laugh", "cry", "hug", "nod", "bow", "pull_hand_back")


def norm_emotion(e):
    if not e:
        return None
    e = str(e).lower().strip()
    e = EMOTION_ALIASES.get(e, e)
    return e if e in FACES else None


def vehicle_type(t):
    t = str(t or "").lower().strip()
    t = VEHICLE_ALIASES.get(t, t)
    return t if t in VEHICLES else None


def walk_u(s, t):
    """0..1 along a walk with natural speed: speeds up at the start, slows down to arrive (steering 'arrival').
    Walks that are the middle of one path (corners) keep their speed."""
    d = max(s.dur, 0.01)
    x = clamp(t - s.start, 0.0, d)
    if s.action not in ("walk", "run", "hop", "gallop", "trot", "approach", "retreat", "swim", "fly"):
        return x / d
    ch = s.params.get("_chain")
    first = ch is None or ch[0] == 0
    last = ch is None or ch[0] == ch[1] - 1
    mom = s.params.get("_mom")                  # momentum (engine/realworld.py): heavy bodies / runners take longer
    ta = min(mom[0] if mom else (0.35 if s.action == "walk" else 0.25), d * 0.3) if first else 0.0
    tb = min(mom[1] if mom else (0.5 if s.action == "walk" else 0.35), d * 0.35) if last else 0.0
    v = 1.0 / max(1e-6, d - ta / 2.0 - tb / 2.0)
    if ta > 0 and x < ta:
        return 0.5 * v * x * x / ta
    if tb > 0 and x > d - tb:
        r = d - x
        return 1.0 - 0.5 * v * r * r / tb
    return v * (ta / 2.0 + (x - ta))


def _cr_point(cr, u):
    """Catmull-Rom point between cr[1] and cr[2] (cr = 4 (x, z) points) at u 0..1."""
    p0, p1, p2, p3 = cr
    u2, u3 = u * u, u * u * u
    return tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * u + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * u2 +
                        (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * u3) for j in range(2))


_CR_ARC = {}


def _cr_arc(cr):
    """Arc-length table of a Catmull-Rom piece: [(param u, distance walked)] (depth counts ZK)."""
    key = tuple(cr)
    got = _CR_ARC.get(key)
    if got is None:
        if len(_CR_ARC) > 20000:
            _CR_ARC.clear()
        tab, prev, d = [(0.0, 0.0)], _cr_point(cr, 0.0), 0.0
        for k in range(1, 33):
            u = k / 32.0
            p = _cr_point(cr, u)
            d += math.hypot(p[0] - prev[0], (p[1] - prev[1]) * ZK)
            tab.append((u, d))
            prev = p
        got = _CR_ARC[key] = tab
    return got


def _cr_arc_point(cr, f):
    """Point at fraction f (0..1) of the piece's real LENGTH - even speed along the curve (a spline's own
    parameter bunches up in the bends, which made walkers speed up and slow down and their feet slide)."""
    tab = _cr_arc(cr)
    L = tab[-1][1]
    if L < 1e-6:
        return _cr_point(cr, f)
    d = clamp(f, 0.0, 1.0) * L
    lo, hi = 0, len(tab) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if tab[mid][1] < d:
            lo = mid
        else:
            hi = mid
    (u0, d0), (u1, d1) = tab[lo], tab[hi]
    u = u0 + (u1 - u0) * ((d - d0) / max(1e-9, d1 - d0))
    return _cr_point(cr, u)


ANTICIPATE_FACE = 0.22      # s: an expression starts this long before its line (the thought comes first)

class Segment:
    __slots__ = ("action", "spec", "start", "dur", "x0", "x1", "facing", "params", "emotion", "prop",
                 "z0", "z1", "view")

    def __init__(self, action, spec, start, dur, x0, x1, facing, params, emotion=None, prop=None,
                 z0=None, z1=None, view=None):
        self.action, self.spec = action, spec
        self.start, self.dur = start, max(dur, 0.01)
        self.x0, self.x1, self.facing = x0, x1, facing
        self.params, self.emotion, self.prop = params, emotion, prop
        self.z0, self.z1 = z0, z1          # depth (None = keep current depth)
        self.view = view                   # None (side) | "camera" | "away" | "side" (reset)

    @property
    def end(self):
        return self.start + self.dur


class Speech:
    def __init__(self, who, text, start, dur, clip, emotion=None, voice_key=None):
        self.who, self.text, self.start, self.dur = who, text, start, dur
        self.clip, self.emotion, self.voice_key = clip, emotion, voice_key
        self.lip = None
        self.to = None                         # who the line is said to (the one the speaker faces)
        self.talk = None                       # lipsync.Talk: mouth shapes, brows, nods, blinks (per frame)

    @property
    def end(self):
        return self.start + self.dur


def _act_prepare(scene):
    """Pick the gesture of every line once (in order, so nobody repeats the same gesture twice running)."""
    if getattr(scene, "_acted", False):
        return
    from . import acting as _act
    last = {}
    for n, sp in enumerate(scene.speeches):
        sp.gest = _act.classify(sp.text, sp.emotion, stable_hash(f"{sp.who}{n}"), last.get(sp.who))
        last[sp.who] = sp.gest
        sp.beats = _act.beats(sp, scene.fps)
        sp.react = _act.reaction_to(sp)
    scene._acted = True


class CharState:
    __slots__ = ("x", "y", "facing", "pose", "face", "mouth", "extras", "alpha", "blink", "seat", "holding",
                 "riding", "z", "view", "squash", "mount")


ZK = 0.8          # one unit of depth "costs" this much walking distance
ENTER_DUR = 0.8   # stepping into a car / bus (after the door opens)
EXIT_DUR = 0.8    # stepping out
CLOSED_VEHICLES = ("car", "jeep", "bus", "auto")
STEP_UP = 64.0    # the highest step a person takes in one go (one or two stair risers, a kerb, a low stage)
LEVEL_DT = 0.05   # seconds between the height samples that follow someone from surface to surface


def pick_level(heights, ref):
    """The surface someone at height ref stands on next: the highest one they can step up to (at most STEP_UP
    higher); walking off an edge they come down to the next one below."""
    ok = [h for h in heights if h <= ref + STEP_UP]
    if ok:
        return max(ok)
    return min(heights) if heights else 0.0


def step_ok(y0, y1, dist, flat=True):
    """Can someone walk from height y0 to y1 over a horizontal distance dist? flat = the ground they step onto is
    level (a stair tread, a floor): a step up to STEP_UP is fine (stairs yes, a wall no). On sloping ground (a
    hillside, a ramp) only slopes up to about 37 degrees - steeper sides need the path."""
    dy = abs(y1 - y0)
    if flat:
        return dy <= STEP_UP + 0.35 * dist
    return dy <= 3.0 + 0.6 * dist


def parse_z(v, default=0.0):
    """Depth value: number 0..1000 or a name (front, middle, back, far_back, horizon)."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(clamp(v, 0, 3000))
    key = str(v).lower().strip()
    if key in Z_NAMES:
        return float(Z_NAMES[key])
    try:
        return float(clamp(float(key), 0, 3000))
    except ValueError:
        return default


VIEW_WORDS = {"camera": "camera", "front": "camera", "viewer": "camera", "audience": "camera", "us": "camera",
              "away": "away", "back": "away", "backward": "away", "behind": "away",
              "three_quarter": "side", "side": "side", "profile": "side"}


class CharTrack:
    def __init__(self, cdef, x, facing, hidden=False, emotion=None, scene=None, crowd=False, z=0.0, view=None):
        self.cdef = cdef
        self.scene = scene
        self.crowd = crowd
        self.x0, self.facing0, self.hidden = float(x), facing, hidden
        self.z0 = float(z)
        self.view0 = view
        self.view_marks = []                 # (time, view) from "facing": "camera"/"away"/"side" on lines
        self.segments = []
        self.moods = [(0.0, norm_emotion(emotion) or "neutral")]
        self.speech = []
        self.icons = []                      # (start, kind)
        self.blink_period = 3.3 + (stable_hash(cdef.id) % 17) / 10.0
        self.actions = animals.actions_for(cdef) or ACTIONS
        self.actx = animals.animal_ctx(cdef) if cdef.kind != "human" else {}
        self.phase = (stable_hash(cdef.id) % 1000) / 137.0
        self.perches = []                    # [start, top, up_dur, end, object id]  sitting / standing on things

    def perch_y(self, t):
        """Height of the thing this character is sitting / standing on at time t (None = on the ground)."""
        for st, top, up, end, _pid in reversed(self.perches):
            if st > t + 1e-9:
                continue
            if end is not None and t >= end:
                d = t - end
                return top * (1 - ease(d / 0.45, "in")) if d < 0.45 else None
            return top * ease(clamp((t - st) / max(up, 0.01), 0, 1), "inout")
        return None

    def resolve(self, name):
        if self.cdef.kind != "human":
            return animals.resolve_animal_action(self.cdef, name)
        return resolve_action(name)

    def last_facing(self):
        return self.segments[-1].facing if self.segments else self.facing0

    def seg_index(self, t):
        idx = -1
        for i, s in enumerate(self.segments):
            if s.start <= t + 1e-9:
                idx = i
            else:
                break
        return idx

    def riding_at(self, t):
        i = self.seg_index(t)
        if i >= 0 and self.segments[i].action == "ride":
            return self.segments[i]
        return None

    def mounted_at(self, t):
        """The animal track this character sits on at time t (or None)."""
        i = self.seg_index(t)
        if i >= 0 and self.segments[i].action == "mount" and self.scene is not None:
            return self.scene.tracks.get(self.segments[i].params.get("_mount"))
        return None

    def saddle_at(self, t):
        """(x, y) of the saddle point on this (four-legged) animal at time t, following its pose.
        A person carrying a baby: the seat is on the forearm in front of the chest, or on the hip."""
        from .animals import q_solve
        i = self.seg_index(t)
        pose, _, _ = self._raw(i, t)
        if self.cdef.kind == "human":
            from .character import solve
            J = solve(pose, self.cdef.scale)
            f = self.facing_at(t)
            s_ = self.cdef.scale
            how = None
            for o in (self.scene.tracks.values() if self.scene is not None else ()):
                j = o.seg_index(t)
                if j >= 0 and o.segments[j].action == "mount" and o.segments[j].params.get("_mount") == self.cdef.id:
                    how = o.segments[j].params.get("_carry")
                    break
            if how == "hip":
                return self.x_at(t) + f * (J["hip"][0] + 7 * s_), J["hip"][1] + 10 * s_
            if how == "bridal":                       # 💞 a grown-up in the arms: across the front, at the forearms
                return self.x_at(t) + f * (J["sh"][0] + 30 * s_), (J["sh"][1] + J["hip"][1]) / 2 - 8 * s_
            if how == "overhead":                     # held up over the head on straight arms
                return self.x_at(t) + f * (J["head"][0] + 4 * s_), J["head"][1] + 56 * s_
            if how == "shoulders":                    # sitting on the shoulders, legs down the front
                return self.x_at(t) + f * (J["neck"][0] - 6 * s_), J["neck"][1] + 6 * s_
            return self.x_at(t) + f * (J["sh"][0] + 16 * s_), (J["sh"][1] + J["hip"][1]) / 2 + 6 * s_
        sp = self.cdef.animal
        J = q_solve(pose, sp, self.cdef.scale)
        f = self.facing_at(t)
        mx = (J["sh"][0] + J["hip"][0]) / 2 + (J["sh"][0] - J["hip"][0]) * 0.12
        my = (J["sh"][1] + J["hip"][1]) / 2 + sp["girth"] * self.cdef.scale * 0.42
        return self.x_at(t) + f * mx, my

    def facing_at(self, t):
        i = self.seg_index(t)
        return self.segments[i].facing if i >= 0 else self.facing0

    def gait_at(self, t):
        i = self.seg_index(t)
        if i < 0:
            return 0.0
        s = self.segments[i]
        if s.spec.moving and t < s.end:
            return 1.0 if s.action in ("run", "gallop") else 0.45
        return 0.0

    def x_at(self, t):
        i = self.seg_index(t)
        if i < 0:
            return self.x0
        s = self.segments[i]
        if s.action == "mount" and self.scene is not None:
            m = self.scene.tracks.get(s.params.get("_mount"))
            if m is not None:
                return m.saddle_at(t)[0]
        if s.action == "ride" and self.scene is not None:
            vid, seat = s.params.get("_vehicle"), s.params.get("_seat", 0)
            v = self.scene.props.get(vid)
            if v is not None:
                sx = seat_x(v, seat, t)
                en = s.params.get("_enter")
                if en and t < en[1] + ENTER_DUR:
                    return en[0] + (sx - en[0]) * ease(clamp((t - en[1]) / ENTER_DUR, 0, 1), "inout")
                return sx
        px = s.params.get("_perch_x")
        if px is not None:                                    # stepping from beside the object onto it
            return px[0] + (px[1] - px[0]) * ease(clamp((t - s.start) / max(px[2], 0.01), 0, 1), "inout")
        ex = s.params.get("_exit")
        if ex and self.scene is not None and t < ex[2] + EXIT_DUR + 0.25:
            v = self.scene.props.get(ex[0])
            if v is not None:
                u = ease(clamp((t - ex[2] - 0.25) / EXIT_DUR, 0, 1), "inout")
                x_from = ex[3] if len(ex) > 3 and ex[3] is not None else seat_x(v, ex[1], t)
                return x_from + (s.x1 - x_from) * u
        cr = s.params.get("_cr") if s.spec.moving else None
        if cr is not None and t < s.end:                      # a curved walk (smooth corner of a planned path)
            return _cr_arc_point(cr, walk_u(s, t))[0]
        if s.spec.moving and s.x1 != s.x0:
            u = walk_u(s, t)
            return s.x0 + (s.x1 - s.x0) * u
        return s.x1

    def z_at(self, t):
        m = self.mounted_at(t)
        if m is not None:
            if m.cdef.kind == "human":                  # 👶 carried: in front of the carrier's body (hip: more to the side)
                j = self.seg_index(t)
                how = self.segments[j].params.get("_carry") if j >= 0 else None
                return m.z_at(t) - {"hip": 22.0, "bridal": 14.0, "overhead": 0.0, "shoulders": 0.0}.get(how, 8.0) * m.cdef.scale
            return m.z_at(t)
        rd = self.riding_at(t) if self.scene is not None else None
        if rd is not None and not rd.params.get("_enter"):
            v = self.scene.props.get(rd.params.get("_vehicle"))
            vi = vinfo(v) if v is not None and v.vtype == "picture" else {}
            if vi.get("seat_z") is not None:                   # on a seat point: the vehicle's depth + its side
                sz = vi["seat_z"][min(rd.params.get("_seat", 0), len(vi["seat_z"]) - 1)] * v.scale
                return story_dz(v.z_at(t), sz)
        z = self.z0
        for s in self.segments:
            if s.start > t + 1e-9:
                break
            if s.z1 is None:
                continue
            z0 = z if s.z0 is None else s.z0
            cr = s.params.get("_cr") if s.spec.moving else None
            if cr is not None and t < s.end and s.start <= t:
                return _cr_arc_point(cr, walk_u(s, t))[1]
            if s.spec.moving and s.z1 != z0 and t < s.end:
                u = walk_u(s, t)
                return z0 + (s.z1 - z0) * u
            z = s.z1
        return z

    def view_at(self, t):
        """Which way the character shows itself: None (side profile), "camera" or "away"."""
        return self._view_info(t)[0]

    def _view_info(self, t):
        """(view, asked) - asked = the story said so ("facing": "camera" on a line / an action); a front view
        left over from walking toward the camera or from the start is not asked, and turns to talk."""
        if self.cdef.kind == "bird" or (self.cdef.kind == "human" and self.cdef.style == "classic"):
            return None, True
        m = self.mounted_at(t)
        if m is not None:
            return m.view_at(t), True              # riders turn with their animal
        v = self.view0
        hard = False
        timeline = [(s.start, 0, s) for s in self.segments] + [(mt, 1, mv) for mt, mv in self.view_marks]
        timeline.sort(key=lambda it: (it[0], it[1]))
        for start, kind, s in timeline:
            if start > t + 1e-9:
                break
            if kind == 1:
                v = None if s == "side" else s
                hard = True
                continue
            moving_now = s.spec.moving and t < s.end
            if s.view:
                v = None if s.view == "side" else s.view
                hard = True
            elif s.spec.moving:
                hard = False
                dx = abs(s.x1 - s.x0)
                dz = abs((s.z1 if s.z1 is not None else 0) - (s.z0 if s.z0 is not None else 0)) * ZK
                if s.z1 is not None and dz > dx * 1.2:
                    toward = s.z1 < (s.z0 if s.z0 is not None else self.z0)
                    if moving_now:
                        v = "camera" if toward else "away"
                    else:
                        v = "camera" if toward else None     # standing with back turned only when asked
                elif dx > 1:
                    v = None
            elif s.action == "ride":
                v = None
        return v, hard

    def _level_y(self, t):
        """Height on the ground following the surface this person is on: step by step from the start of the
        scene (every LEVEL_DT), so on stairs they go up one step at a time, under a balcony they stay on the
        floor, and on the balcony they stay up there."""
        sc = self.scene
        if not (sc._walk_list() if (sc.bg is not None or getattr(sc, "props", None)) else []):
            return sc.ground_y(self.x_at(t), self.z_at(t))
        ver = (len(self.segments), len(self.perches), id(sc))
        c = self.__dict__.get("_lvl")
        if c is None or c[0] != ver:
            c = self._lvl = [ver, {}]
        cache = c[1]
        k = max(0, int(t / LEVEL_DT))
        k0 = k
        while k0 >= 0 and k0 not in cache:
            k0 -= 1
        if k0 < 0:                                             # the start: on whatever they are placed on
            lv = getattr(self, "start_level", None)
            y = sc.ground_y(self.x_at(0.0), self.z_at(0.0), ref=150.0 if lv is None else float(lv))
            cache[0] = y
            k0 = 0
        y = cache[k0]
        for kk in range(k0 + 1, k + 1):
            tk = kk * LEVEL_DT
            y = sc.ground_y(self.x_at(tk), self.z_at(tk), ref=y)
            cache[kk] = y
        return sc.ground_y(self.x_at(t), self.z_at(t), ref=y)

    def y_at(self, t):
        m = self.mounted_at(t)
        if m is not None:
            return m.saddle_at(t)[1]               # saddle height (the rider's hip goes here, see state())
        if self.perches:
            py = self.perch_y(t)
            if py is not None:
                return py
        if self.scene is not None:
            i = self.seg_index(t)
            ex = self.segments[i].params.get("_exit") if i >= 0 else None
            if ex and t < ex[2] + EXIT_DUR + 0.25:             # stepping down out of a vehicle
                v = self.scene.props.get(ex[0])
                if v is not None:
                    u = ease(clamp((t - ex[2] - 0.25) / EXIT_DUR, 0, 1), "inout")
                    return (v.pos(t)[1] + vinfo(v)["floor"] * v.scale) * (1 - u)
        s = self.riding_at(t)
        if self.scene is None:
            return 0.0
        if s is None:                                          # on the ground: up and down the hills, stairs ...
            return self._level_y(t)
        v = self.scene.props.get(s.params.get("_vehicle"))
        if v is None:
            return 0.0
        vi = vinfo(v)
        if vi.get("seat") is not None:                         # RIDE seat points: the hips go on the seat
            kind = s.params.get("_vehicle_kind", "car")
            sy = vi.get("seat_y") or [vi["seat"]]
            seat = sy[min(s.params.get("_seat", 0), len(sy) - 1)]
            y = v.pos(t)[1] + max(0.0, seat * v.scale - HIP_ON_SEAT.get(kind, 82.5) * self.cdef.scale) + \
                boat_bob(v, t)
        else:
            y = v.pos(t)[1] + vi["floor"] * v.scale + boat_bob(v, t)
        en = s.params.get("_enter")
        if en and t < en[1] + ENTER_DUR:                       # stepping up into it
            y *= ease(clamp((t - en[1]) / ENTER_DUR, 0, 1), "inout")
        return y

    def _listening(self, t, scene, face):
        """While another character talks: nod a beat after some of their stressed words, blink, look up at a
        question, smile back at a happy line. -> ctl or None"""
        best = None
        for o in getattr(scene, "speeches", ()):
            if o.who == self.cdef.id or o.who == "narrator" or o.talk is None:
                continue
            if o.start <= t < o.end + 0.6:
                best = o
                break
        if best is None:
            return None
        fps = scene.fps
        k = (t - best.start) * fps
        nod = brow = 0.0
        blink = False
        salt = stable_hash(self.cdef.id)
        w = 0.45 * fps
        for j, p in enumerate(best.talk.peaks):
            loc = k - (p + 0.18 * fps)
            if 0 <= loc < w:
                h = (salt + j * 37) % 100
                if h < 45:
                    nod += 3.0 * math.sin(math.pi * (loc + 0.5) / w)
                if 45 <= h < 70 and loc < 0.13 * fps:
                    blink = True
        if best.talk.question:
            loc = k - (best.talk.n - 0.4 * fps)
            if 0 <= loc < 0.8 * fps:
                brow = 0.4 * math.sin(math.pi * loc / (0.8 * fps))
        smile = best.emotion in ("happy", "laughing") and face == "neutral" and (salt % 3) != 0
        if nod == 0.0 and not blink and brow == 0.0 and not smile:
            return None
        return {"nod": nod, "blink": blink, "brow": brow, "smile": smile, "gx": 0.0, "gy": 0.0}

    EYE_H = {"human": 268.0, "quadruped": 120.0, "bird": 60.0}

    def _eye_h(self):
        return self.EYE_H.get(self.cdef.kind, 120.0) * self.cdef.scale

    def gaze(self, t, scene, x, y, z, facing, view):
        """Where the eyes look: (gx, gy) - side view: gx + = ahead; front view: gx + = screen right; gy + = up.
        They look at the one talking / talked to, at what an action is aimed at, at a vehicle driving by;
        otherwise they wander a little - with quick small jumps (saccades) like real eyes."""
        if scene is None or self.crowd:
            return 0.0, 0.0
        me = self.cdef.id
        tx = ty = None
        i = self.seg_index(t)
        seg = self.segments[i] if i >= 0 else None
        if seg is not None and t <= seg.end + 0.4:
            for k in ("target", "look_at", "object", "at_who", "toward", "to", "with"):
                v = seg.params.get(k)
                if isinstance(v, str) and v != me:
                    if v in scene.tracks and scene.tracks[v] is not self:
                        o = scene.tracks[v]
                        tx, ty, tz = o.x_at(t), o.y_at(t) + o._eye_h(), o.z_at(t)
                        break
                    if v in scene.props:
                        pr = scene.props[v]
                        px, py, _ = pr.pos(t)
                        tx, ty, tz = px, py + 70.0, pr.z_at(t)
                        break
        if tx is None:
            who = scene.focus_who(me, t)
            if who is not None and who in scene.tracks:
                o = scene.tracks[who]
                tx, ty, tz = o.x_at(t), o.y_at(t) + o._eye_h(), o.z_at(t)
        if tx is None:                                   # nothing to talk about: a vehicle going by catches the eye
            best = None
            for pr in scene.props.values():
                if pr.vtype and pr.moving(t):
                    px, py, _ = pr.pos(t)
                    d = abs(px - x)
                    if d < 1600 and (best is None or d < best[0]):
                        best = (d, px, py + 120.0, pr.z_at(t))
            if best is not None:
                _d, tx, ty, tz = best
        if tx is None:                                   # ... or someone running past (eyes follow movement)
            best = None
            for oid, o in scene.tracks.items():
                if o is self or oid == me or getattr(o, "crowd", False):
                    continue
                try:
                    ox_, vx_ = o.x_at(t), (o.x_at(t) - o.x_at(t - 0.25)) / 0.25
                except Exception:                        # noqa: BLE001
                    continue
                d = abs(ox_ - x)
                if abs(vx_) > 220.0 and d < 1400 and (best is None or d < best[0]):
                    best = (d, ox_, o.y_at(t) + o._eye_h(), o.z_at(t))
            if best is not None:
                _d, tx, ty, tz = best
        salt = stable_hash(me) % 997
        k = int((t + salt * 0.013) / 1.35)               # a new little eye jump every ~1.3 s
        h = stable_hash(f"{me}:{k}")
        ox, oy = ((h % 7) - 3) * 0.05, (((h // 7) % 5) - 2) * 0.05
        my_eye = y + self._eye_h()
        if tx is None:                                   # idle: the eyes drift, mostly ahead
            return 0.45 + 0.35 * math.sin(t * 0.37 + salt) + ox, 0.18 * math.sin(t * 0.29 + salt * 0.5) + oy
        dx = tx - x
        dist = max(120.0, math.hypot(dx, (tz - z) * ZK * 2.0))
        gy = clamp((ty - my_eye) / dist * 1.7, -1.0, 1.0)
        if view == "camera":
            gx = clamp(dx / 260.0, -1.0, 1.0)
        elif view == "away":
            gx = 0.0
        else:
            gx = 0.9 if dx * facing >= -20 else -0.55
        return clamp(gx + ox * 0.6, -1.0, 1.0), clamp(gy + oy * 0.6, -1.0, 1.0)

    def convo_face(self, t):
        """The track this character turns to right now in a conversation (None: no conversation, or they are
        busy - walking, riding, an action with its own "facing", a front view the story asked for)."""
        sc = self.scene
        if sc is None or not getattr(sc, "auto_face", True) or self.crowd:
            return None
        i = self.seg_index(t)
        seg = self.segments[i] if i >= 0 else None
        if seg is not None:
            idle = (t - seg.start > seg.dur and not seg.spec.persistent) or seg.action in ("idle", "stand", "appear")
            if not idle and (seg.spec.moving or seg.action not in CONVO_KEEP or seg.params.get("facing") is not None
                             or seg.params.get("face") is not None):
                return None
            if seg.action == "ride" or self.mounted_at(t) is not None:
                return None
        v, asked = self._view_info(t)
        if asked and v in ("camera", "away"):
            return None
        who = sc.focus_who(self.cdef.id, t)
        return sc.tracks.get(who) if who is not None else None

    def speaking(self, t):
        for sp in self.speech:
            if sp.start <= t < sp.end:
                return sp
        return None

    def mood(self, t):
        m = self.moods[0][1]
        for tt, e in self.moods:
            if tt <= t:
                m = e
        return m

    # -- evaluation
    def _ctx(self, s, t):
        ctx = {"params": s.params if s else {}, "speed": 0.0, "dist": 0.0}
        ctx.update(self.actx)
        if self.cdef.kind == "human":                   # babies crawl, toddlers toddle (engine/poses.py)
            ctx["age"] = self.cdef.age
            from .character import body_of
            ctx["legk"] = (body_of(self.cdef) or {}).get("leg", 1.0)
        if self.cdef.kind == "human" and not self.crowd:   # the body's weight (engine/realworld.py)
            body = getattr(self, "_body", None)
            if body is None:
                sc_ = self.scene
                ex_ = getattr(sc_, "exaggeration", 1.0) if sc_ is not None else 1.0
                body = self._body = dict(realworld.gait(self.cdef, ex_),
                                         land=realworld.landing_bend(self.cdef, ex_),
                                         real=bool(getattr(sc_, "real", False)))
            ctx["body"] = body
        if s is not None and s.params.get("_mood"):
            ctx["mood"] = s.params["_mood"]
        if s is not None and s.action == "ride" and self.scene is not None:
            v = self.scene.props.get(s.params.get("_vehicle"))
            if v is not None:                                  # is the vehicle moving now? (pedal / row / sway)
                a, b = v.pos(t - 0.06)[0], v.pos(t + 0.06)[0]
                ctx["vmoving"] = clamp(abs(b - a) / 0.12 / 60.0, 0.0, 1.0)
        if s is not None and s.spec.moving:
            dz = 0.0
            if s.z1 is not None and s.z0 is not None:
                dz = (s.z1 - s.z0) * ZK
            cr = s.params.get("_cr")
            total = _cr_arc(cr)[-1][1] if cr is not None else math.hypot(s.x1 - s.x0, dz)
            ctx["speed"] = total / s.dur
            # the distance really walked so far (with the speeding up / slowing down): the legs step exactly
            # as far as the body moves, so the foot on the ground never slides
            ctx["dist"] = total * clamp(walk_u(s, min(t, s.end)), 0, 1)
        return ctx

    def _raw(self, i, t):
        idle_fn = self.actions["idle"].fn
        if i < 0:
            p, ex = idle_fn(t + self.phase, 1, self._ctx(None, t))
            return p, ex, True
        s = self.segments[i]
        local = t - s.start
        if local > s.dur and not s.spec.persistent:
            p, ex = idle_fn(t + self.phase, 1, self._ctx(None, t))
            return p, ex, True
        lt = min(local, s.dur) if s.spec.oneshot or s.spec.moving else local
        p, ex = s.spec.fn(lt, s.dur, self._ctx(s, t))
        return p, ex, s.action in ("idle", "stand", "appear")

    def seated_at(self, t):
        """The "sit" this character is still sitting on at t: talking, thinking, waving, crying ... keep them
        seated (only the upper body acts); walking, jumping, dancing, hugging ... make them stand up."""
        sit = None
        for sg in self.segments:
            if sg.start > t + 1e-9:
                break
            if sg.action == "sit":
                sit = sg
            elif sit is not None and sg.action not in SEAT_KEEP:
                sit = None
        return sit

    # -- anticipation: a small opposite move before the real one (animation principle)
    ANTIC = {"walk": 0.2, "run": 0.3, "jump": 0.0, "retreat": 0.18}

    def _antic(self, pose, nxt, k):
        """pose wound up for the coming action nxt, by k (0..1)."""
        if k <= 0.0 or nxt is None:
            return pose
        a = nxt.action
        if a in ("walk", "run", "retreat") and nxt.spec.moving:
            big = 1.6 if a == "run" else 1.0
            return add_pose(pose, torso=-6.0 * big * k, head=3.0 * k, ln_s=-12.0 * big * k, lf_s=-12.0 * big * k,
                            ln_t=6.0 * big * k, lf_t=6.0 * big * k, an_u=10.0 * big * k, af_u=-10.0 * big * k)
        return pose

    def _anticipate(self, pose, t, i, seg, idle):
        """Wind up before walking / running off, push off at the start, lean forward to stand up from a seat,
        dip a little when sitting down."""
        segs = self.segments
        nxt = segs[i + 1] if i + 1 < len(segs) else None
        if nxt is not None and nxt.action in self.ANTIC and self.ANTIC[nxt.action] > 0 and \
                (idle or seg is None or (not seg.spec.moving and t > seg.end)) and self.riding_at(t) is None:
            lead = self.ANTIC[nxt.action]
            d = nxt.start - t
            if 0.0 < d < lead:
                pose = self._antic(pose, nxt, smoothstep(1.0 - d / lead))
        if seg is not None:
            local = t - seg.start
            prev = segs[i - 1] if i >= 1 else None
            if prev is not None and prev.action == "sit" and seg.action not in SEAT_KEEP and local < 0.6:
                pose = add_pose(pose, torso=24.0 * math.sin(math.pi * local / 0.6))     # lean forward to stand up
            if seg.action == "sit" and local < seg.spec.blend_in:
                pose = add_pose(pose, torso=14.0 * math.sin(math.pi * local / max(0.1, seg.spec.blend_in)))
        return pose

    def _face_simple(self, t, i_now):
        """The face at an earlier moment (emotion / speech / action) - for smooth changes of expression."""
        if t < 0:
            return self.mood(0.0)
        i = self.seg_index(t)
        face = self.mood(t)
        seg = self.segments[i] if i >= 0 else None
        if seg is not None and seg.emotion and (seg.spec.persistent or t <= seg.end):
            face = seg.emotion
        elif seg is not None and t <= seg.end + 1e-6:
            try:
                _p, ex = seg.spec.fn(min(t - seg.start, seg.dur) if seg.spec.oneshot or seg.spec.moving else
                                     t - seg.start, seg.dur, self._ctx(seg, t))
                if ex.get("face"):
                    face = ex["face"]
            except Exception:
                pass
        sp = self.speaking(t)
        if sp is not None and sp.emotion:
            face = sp.emotion
        elif sp is None:                                 # anticipation: the face changes a moment BEFORE the line
            nx = self.speaking(t + ANTICIPATE_FACE)
            if nx is not None and nx.emotion:
                face = nx.emotion
        return face

    # -- cloth / hair follow-through
    def _has_cloth(self):
        c = self.cdef
        ex = getattr(c, "extras", ()) or ()
        return c.hair in ("long", "braid", "ponytail") or any(k in ex for k in ("cape", "dupatta", "pallu"))

    def drag_at(self, t):
        """(swing, lift) in degrees for hair, dupatta, saree pallu and capes: they trail behind when the body
        moves, swing past and settle when it stops (a damped spring), and float up while falling."""
        cache = getattr(self, "_drag_cache", None)
        key = round(t, 4)
        if cache is not None and key in cache:
            return cache[key]
        if cache is None or len(cache) > 400:
            cache = self._drag_cache = {}
        dt, T = 1.0 / 30.0, 1.4
        w, zeta = 2 * math.pi * 1.15, 0.28
        k_ = ZK * 2.5
        th = om = lf = olf = 0.0
        n = int(T / dt)
        prev = None
        wind = realworld.wind()                          # the scene's one wind blows it too
        for j in range(n + 1):
            tt = t - T + j * dt
            p = (self.x_at(tt), self.z_at(tt) * k_, self.y_at(tt))
            if prev is None:
                prev = p
                continue
            vx, vz, vy = (p[0] - prev[0]) / dt, (p[1] - prev[1]) / dt, (p[2] - prev[2]) / dt
            prev = p
            f = self.facing_at(tt) or 1
            v = math.hypot(vx, vz)
            if vx * f < -20.0 and abs(vx) > abs(vz):
                v = -v                                   # walking backwards: it blows forward
            wv = wind.speed(tt, p[0]) * f                # + = the wind comes from behind (blows it forward)
            flap = math.sin(tt * 7.3 + p[0] * 0.01) * 0.025 * abs(wv)
            target = clamp(0.11 * (v - wv) + flap, -45.0, 75.0)
            om += (-w * w * (th - target) - 2 * zeta * w * om) * dt
            th += om * dt
            ltarget = clamp(-0.08 * vy, -20.0, 60.0)
            olf += (-w * w * (lf - ltarget) - 2 * zeta * w * olf) * dt
            lf += olf * dt
        got = (clamp(th, -50.0, 85.0), clamp(lf, -25.0, 70.0))
        cache[key] = got
        return got

    def momentum(self, t, dt=0.15):
        """(acceleration along the facing direction, sideways acceleration, speed) in units/s(²) on the ground:
        what the body feels when it speeds up, slows down or goes round a curve (averaged over 0.3 s, so the
        lean comes and goes smoothly). Depth counts as much as it costs to walk (ZK)."""
        k_ = ZK
        P_ = [(self.x_at(t + j * dt), self.z_at(t + j * dt) * k_) for j in (-1, 0, 1)]
        v0 = ((P_[1][0] - P_[0][0]) / dt, (P_[1][1] - P_[0][1]) / dt)
        v1 = ((P_[2][0] - P_[1][0]) / dt, (P_[2][1] - P_[1][1]) / dt)
        if max(math.hypot(*v0), math.hypot(*v1)) > 1500.0:   # placed somewhere else at once: no real motion
            return 0.0, 0.0, 0.0
        vx, vz = (v0[0] + v1[0]) / 2, (v0[1] + v1[1]) / 2
        ax, az = (v1[0] - v0[0]) / dt, (v1[1] - v0[1]) / dt
        v = math.hypot(vx, vz)
        f = self.facing_at(t) or 1
        if v > 5.0:
            ux, uz = vx / v, vz / v
            back = -1.0 if vx * f < -0.2 * v and abs(vx) > abs(vz) else 1.0   # walking backwards
            along = (ax * ux + az * uz) * back
            lat = ux * az - uz * ax                     # + = turning toward +z (into the picture) on the right
        else:
            along, lat = ax * f, 0.0
        return along, lat, v

    def state(self, t, scene):
        st = CharState()
        i = self.seg_index(t)
        pose, extras, idle = self._raw(i, t)
        seg = self.segments[i] if i >= 0 else None
        sat = self.seated_at(t) if self.cdef.kind == "human" else None
        if sat is not None and seg is not None and seg is not sat:
            sp_, _ = sat.spec.fn(t - sat.start, sat.dur, self._ctx(sat, t))
            pose = dict(pose)
            for k in LEG_KEYS:                          # legs and hips stay on the seat
                pose[k] = sp_[k]
            pose["torso"] = min(pose.get("torso", 0.0), 8.0)
            extras = dict(extras, seat=True)
        antic = self.cdef.kind == "human" and not self.crowd and scene is not None and \
            getattr(scene, "anticipation", True)
        if seg is not None:
            local = t - seg.start
            bi = seg.spec.blend_in
            if local < bi and bi > 0:
                prev, _, _ = self._raw(i - 1, seg.start)
                if antic:
                    prev = self._antic(prev, seg, 1.0)
                pose = blend(prev, pose, smoothstep(local / bi)) if getattr(scene, "real", False) else \
                    blend_overshoot(prev, pose, local / bi)     # (pure physics: no cartoon overshoot)
            elif local > seg.dur and not seg.spec.persistent and local < seg.dur + 0.35:
                endp, _, _ = self._raw(i, seg.end - 1e-4)
                pose = blend(endp, pose, smoothstep((local - seg.dur) / 0.35))
                extras = {}
        if antic:
            pose = self._anticipate(pose, t, i, seg, idle)
        sp = self.speaking(t)
        acting = str(getattr(scene, "acting", "auto") or "auto").lower() if scene is not None else "off"
        acts = acting not in ("off", "none", "no", "false") and self.cdef.kind == "human" and not self.crowd
        if sp is not None and idle:
            w = smoothstep(min(t - sp.start, sp.end - t) / 0.3)
            if acts:                                    # a gesture of its own for every line (engine/acting.py)
                from . import acting as _act
                _act_prepare(scene)
                talk = _act.talk_pose(sp.gest, t - sp.start, sp.dur, sp.beats, 0.6 if acting == "calm" else 1.0)
            else:
                talk, _ = self.actions["talk"].fn(t - sp.start, sp.dur, self._ctx(None, t))
            pose = blend(pose, talk, w)
        elif acts and idle and self.riding_at(t) is None and self.mounted_at(t) is None:
            from . import acting as _act                # listening / waiting: never a frozen statue
            _act_prepare(scene)
            react = None
            for o in scene.speeches:
                if o.who != self.cdef.id and o.who in scene.tracks and o.end <= t < o.end + 1.7 and o.react:
                    react = (o.react, t - o.end)
            seated_ = self.seated_at(t) is not None
            lp = _act.listen_pose(pose, self.cdef.id, t, react, scale=self.cdef.scale)
            if seated_:
                lp = {k: (pose.get(k, 0.0) if k in LEG_KEYS or k in ("an_u", "an_l", "af_u", "af_l") else v)
                      for k, v in lp.items()}
            pose = lp
        holding = scene.prop_holder_of(self.cdef.id, t)
        if holding and idle and self.cdef.kind == "human":
            pose = dict(pose, an_u=48, an_l=28)
        st.x = self.x_at(t)
        st.y = self.y_at(t)
        if st.y > 1.0 and seg is not None and seg.spec.moving and scene is not None and self.cdef.kind == "human":
            f = seg.facing                                     # climbing: lean into the slope
            z_ = self.z_at(t)
            g = (scene.ground_y(st.x + 12 * f, z_) - scene.ground_y(st.x - 12 * f, z_)) / 24.0
            if abs(g) > 0.02:
                pose = dict(pose, torso=pose.get("torso", 0.0) + clamp(g * 45.0, -10.0, 22.0))
        ride = self.riding_at(t)
        st.riding = ride.params.get("_vehicle") if ride else None
        if ride is None and seg is not None and seg.params.get("_exit"):
            ex = seg.params["_exit"]
            if t < ex[2] + 0.25 + EXIT_DUR * 0.55 and (len(ex) < 4 or ex[3] is None):
                st.riding = ex[0]                    # side view: slides out through the door, inside the body
        mount = self.mounted_at(t)
        st.mount = mount.cdef.id if mount is not None else None
        facing = seg.facing if seg else self.facing0
        convo = False
        if mount is not None:
            facing = mount.facing_at(t)
            if seg is not None:
                seg.params["_gait"] = mount.gait_at(t)
                pose, extras = seg.spec.fn(t - seg.start, seg.dur, self._ctx(seg, t))
        if ride is not None:
            v = scene.props.get(st.riding)
            if v is not None:
                facing = v.pos(t)[2]
        elif (idle or (seg is not None and not seg.spec.moving and seg.action in CONVO_KEEP and
                       seg.params.get("facing") is None and seg.params.get("face") is None)) \
                and scene.auto_face and not self.crowd and not any(
                o is not self and o.mounted_at(t) is self for o in scene.tracks.values()):
            target = scene.focus_target(self.cdef.id, t)
            if target is not None and abs(target - st.x) > 20:
                facing = 1 if target > st.x else -1
                convo = True
        if extras.get("flip"):
            facing = -facing
        if self.cdef.kind == "human" and scene is not None and not self.crowd:   # 👶 carrying a baby: the arms hold it
            for o in scene.tracks.values():
                if o is not self and o.cdef.kind == "human" and o.mounted_at(t) is self:
                    from .poses import HOLD_ARMS, HOLD_HIP, HOLD_BY
                    j = o.seg_index(t)
                    how = o.segments[j].params.get("_carry") if j >= 0 else None
                    pose = dict(pose, **(HOLD_BY.get(how) or (HOLD_HIP if how == "hip" else HOLD_ARMS)))
                    if how == "overhead":
                        pose["torso"] = min(pose.get("torso", 0.0), -4.0)      # (a heavy weight up there: leaning back)
                    break
        ex_k = getattr(scene, "exaggeration", 1.0) if scene is not None else 1.0
        real = bool(getattr(scene, "real", False)) if scene is not None else False
        if abs(ex_k - 1.0) > 0.01 and self.cdef.kind == "human":
            pose = exaggerate(pose, ex_k, moving=seg is not None and seg.spec.moving and t <= seg.end)
        bank = 0.0
        if self.cdef.kind == "human" and not self.crowd and ride is None and mount is None and \
                not (seg is not None and seg.action in ("jump", "fall", "sit", "lie", "sleep", "climb")):
            acc, lat, v = self.momentum(t)               # momentum: lean with speeding up / slowing down,
            lean = realworld.lean_from_accel(acc, ex_k, real)          # into a curve
            if abs(lean) > 0.2:
                pose = dict(pose, torso=pose.get("torso", 0.0) + lean, head=pose.get("head", 0.0) - 0.4 * lean)
            if real and v > 30.0 and abs(lat) > 1.0:         # leaning into curves: classroom videos only
                bank = math.copysign(realworld.bank_from_turn(v, abs(lat) / (v * v), ex_k, real), lat)
        if scene is not None and getattr(scene, "cloth", True) and self.cdef.kind == "human" and not self.crowd \
                and self._has_cloth():
            extras = dict(extras, drag=self.drag_at(t))
        st.facing = facing
        st.pose = pose
        face = self.mood(t)
        if extras.get("face"):
            face = extras["face"]
        if seg is not None and seg.emotion and (seg.spec.persistent or t <= seg.end):
            face = seg.emotion
        if sp is not None and sp.emotion:
            face = sp.emotion
        elif sp is None and self.cdef.kind == "human" and not self.crowd:
            nx = self.speaking(t + ANTICIPATE_FACE)       # anticipation: the face changes a moment before the line
            if nx is not None and nx.emotion:
                face = nx.emotion
        st.face = face
        face_from = None
        if self.cdef.kind == "human" and not self.crowd:     # the face changes smoothly (3D faces blend)
            for back in (0.08, 0.16, 0.24, 0.32):
                fp = self._face_simple(t - back, i)
                if fp != face:
                    face_from = (fp, back / 0.32)
                    break
        st.mouth = 0.0
        ctl = None
        if sp is not None and sp.lip is not None and len(sp.lip):
            k = int((t - sp.start) * scene.fps)
            if 0 <= k < len(sp.lip):
                st.mouth = float(sp.lip[k])
            if sp.talk is not None:                        # the real mouth shapes + brows, nods, blinks
                ctl = sp.talk.at(k)
        if sp is None and extras.get("mouth") is not None:
            st.mouth = float(extras["mouth"])               # an action moves the mouth itself (eating: bite, chew)
        cap = extras.get("talk") if sp is None else None
        if isinstance(cap, dict):                           # a captured face (engine/videomocap.py): jaw, smile, brows,
            ctl = dict(cap)                                 # blinks, gaze - straight from the actor's video
        if ctl is None and not self.crowd:
            ctl = self._listening(t, scene, face)          # someone else talks: small nods, blinks
        if abs(bank) > 0.3:
            extras = dict(extras, bank=bank)
        st.extras = extras
        st.alpha = extras.get("alpha", 0.0 if (self.hidden and (seg is None)) else 1.0)
        st.blink = ((t + (stable_hash(self.cdef.id) % 100) / 37.0) % self.blink_period) < 0.13
        if ctl is not None:
            if sp is not None and ctl.get("shape") is not None:
                st.blink = bool(ctl.get("blink"))           # a speaker blinks in the pauses
            else:
                st.blink = st.blink or bool(ctl.get("blink"))
            if ctl.get("smile") and st.face == "neutral":
                st.face = "happy"
            ctl["lid"] = 1.0 if st.blink else (0.35 if st.face == "thinking" else 0.0)
            if isinstance(cap, dict) and "lid" in cap:
                ctl["lid"] = max(ctl["lid"], float(cap["lid"]))
            val = st.mouth if (sp is not None or extras.get("mouth") is not None) else 0.0
            if "jaw" in ctl and "closed" in ctl:
                val = max(0.0, min(1.0, ctl["jaw"] * (1.0 - 0.85 * ctl["closed"])))
            from .lipsync import Mouth
            if face_from is not None:
                ctl = dict(ctl, face_from=face_from[0], face_k=face_from[1])
            st.mouth = Mouth(val, ctl)
            nod = float(ctl.get("nod", 0.0))
            tilt = float(ctl.get("tilt", 0.0))
            if abs(nod) > 0.05 or abs(tilt) > 0.05:        # the head dips on the beat / lifts on a question
                pose = dict(pose)
                pose["head"] = pose.get("head", 0.0) - nod * (0.8 if self.cdef.kind != "human" else 1.0) + 0.6 * tilt
                st.pose = pose
        st.seat = bool(extras.get("seat")) and (seg is None or (sat is not None and seg is not sat)
                                                or t - seg.start > seg.spec.blend_in * 0.5)
        st.holding = holding
        st.z = self.z_at(t)
        if mount is not None:                      # sit the hip on the saddle
            from .character import solve
            st.y = st.y - solve(pose, self.cdef.scale)["hip"][1]
        elif seg is not None and seg.action in ("sit_on", "perch", "climb") and self.cdef.kind == "human" \
                and self.perches and st.y > 0:
            from .character import solve               # sitting ON something: the hip goes on its top
            st.y = max(0.0, st.y - solve(pose, self.cdef.scale)["hip"][1])
        if ride is not None or self.crowd:
            st.view = None
        else:
            st.view, asked = self._view_info(t)
            if convo and st.view == "camera" and not asked:
                st.view = None                              # in a conversation: turn to the other person
        if st.view == "away" and sp is not None and not (seg is not None and seg.view == "away"):
            st.view = None                                  # speakers turn around to talk
        st.squash = squash_factor(seg, t) if seg is not None and not real else (1.0, 1.0)   # pure physics: none
        if abs(ex_k - 1.0) > 0.01:
            st.squash = (1.0 + (st.squash[0] - 1.0) * ex_k, 1.0 + (st.squash[1] - 1.0) * ex_k)
        if ride is None and not self.crowd and self.cdef.kind != "bird":
            fl = self.flip_at(t)                           # card-flip turn (Paper Mario style)
            if fl is not None:
                u, of, nf, ov, nv = fl
                if of != nf and ov is None and nv is None:        # left <-> right: squeeze flat, open the other way
                    if u < 0.5:
                        st.facing = of
                    k = abs(math.cos(math.pi * u))
                    st.squash = (st.squash[0] * max(0.06, k), st.squash[1])
                elif ov != nv:                                    # side <-> front / back: a quick squeeze
                    if u < 0.5:
                        st.view = ov if not (ov == "away" and sp is not None) else None
                        if of is not None and ov is None:
                            st.facing = of
                    k = 1.0 - 0.55 * math.sin(math.pi * u)
                    st.squash = (st.squash[0] * k, st.squash[1])
        if not self.crowd and self.cdef.kind == "human" and st.alpha > 0.01 and scene is not None and \
                getattr(scene, "gaze", True):
            try:                                            # the eyes look at someone / something
                gx_, gy_ = self.gaze(t, scene, st.x, st.y, st.z, st.facing, st.view)
            except Exception:
                gx_ = None
            if gx_ is not None:
                from .lipsync import Mouth
                old_ = getattr(st.mouth, "ctl", None)
                c_ = dict(old_) if old_ else {"nod": 0.0, "blink": st.blink, "brow": 0.0, "smile": False,
                                              "lid": 1.0 if st.blink else (0.35 if st.face == "thinking" else 0.0)}
                c_["gx"], c_["gy"] = gx_, gy_
                st.mouth = Mouth(float(st.mouth), c_)
        return st

    FLIP_T = 0.22

    def flip_events(self):
        """[(time, old facing, new facing, old view, new view)] - every turn the character makes."""
        got = getattr(self, "_flips", None)
        if got is not None and got[0] == len(self.segments):
            return got[1]
        times = set()
        for sg in self.segments:
            times.add(round(sg.start, 4))
            if sg.spec.moving:
                times.add(round(sg.end, 4))
        for mt, _mv in self.view_marks:
            times.add(round(mt, 4))
        ev = []
        for tb in sorted(times):
            if tb <= 0.05:
                continue
            try:
                of, nf = self.facing_at(tb - 1e-3), self.facing_at(tb + 1e-3)
                ov, nv = self.view_at(tb - 1e-3), self.view_at(tb + 1e-3)
            except Exception:
                continue
            if self.riding_at(tb + 1e-3) is not None or self.riding_at(tb - 1e-3) is not None:
                continue
            if (of != nf and ov is None and nv is None) or ov != nv:
                ev.append((tb, of, nf, ov, nv))
        self._flips = (len(self.segments), ev)
        return ev

    def flip_at(self, t):
        for tb, of, nf, ov, nv in reversed(self.flip_events()):
            if tb <= t < tb + self.FLIP_T:
                return (t - tb) / self.FLIP_T, of, nf, ov, nv
            if tb <= t:
                break
        return None


OVERSHOOT_KEYS = ("an_u", "an_l", "af_u", "af_l", "head", "neck", "tail")


def _back_out(u, k=1.9):
    u = clamp(u, 0.0, 1.0) - 1.0
    return 1.0 + (k + 1) * u ** 3 + k * u ** 2


def blend_overshoot(a, b, u):
    """Body blends smoothly; arms, head and tail swing slightly past the target and settle (overshoot)."""
    w = smoothstep(u)
    wo = _back_out(u)
    keys = a.keys() | b.keys()
    return {k: a.get(k, 0.0) + (b.get(k, 0.0) - a.get(k, 0.0)) * (wo if k in OVERSHOOT_KEYS else w) for k in keys}


def add_pose(p, **kw):
    q = dict(p)
    for k, v in kw.items():
        q[k] = q.get(k, 0.0) + v
    return q


_STAND_EX = {"torso": 0.0, "head": 0.0, "an_u": 8.0, "an_l": 8.0, "af_u": -6.0, "af_l": 8.0}


def exaggerate(pose, k, moving=False):
    """The whole story calmer (k < 1) or more cartoony (k > 1): every pose is pushed away from a plain stand."""
    q = dict(pose)
    keys = ("an_u", "an_l", "af_u", "af_l") if moving else ("torso", "head", "an_u", "an_l", "af_u", "af_l")
    for key in keys:
        base = _STAND_EX[key]
        v = base + (q.get(key, base) - base) * k
        lim = 175.0 if key.startswith("a") else 85.0
        q[key] = max(-lim, min(lim, v))
    if not moving and "lift" in q and q["lift"] > 0:
        q["lift"] = q["lift"] * (0.5 + 0.5 * k)
    return q


def squash_factor(seg, t):
    """(scale_x, scale_y) for squash & stretch on jumps, hops and falls."""
    act = seg.action
    if act not in ("jump", "pounce", "hop", "fall"):
        return 1.0, 1.0
    u = (t - seg.start) / max(seg.dur, 0.01)
    if act == "fall":
        k = math.exp(-((u - 0.32) / 0.07) ** 2)
        return 1.0 + 0.16 * k, 1.0 - 0.2 * k
    if act == "hop":
        ph = (u * max(1.0, seg.dur * 1.6)) % 1.0
        k1 = math.exp(-((ph - 0.05) / 0.06) ** 2)
        k2 = math.sin(math.pi * ph) * 0.6
        return 1.0 + 0.1 * k1 - 0.05 * k2, 1.0 - 0.12 * k1 + 0.08 * k2
    crouch = math.exp(-((u - 0.18) / 0.05) ** 2)          # anticipation squash
    rise = math.exp(-((u - 0.32) / 0.07) ** 2)            # take-off stretch
    land = math.exp(-((u - 0.82) / 0.05) ** 2)            # landing squash
    sx = 1.0 + 0.1 * crouch - 0.07 * rise + 0.14 * land
    sy = 1.0 - 0.12 * crouch + 0.12 * rise - 0.17 * land
    return sx, sy


class Route:
    """A vehicle's way along several points (x, z): a smooth curve through them, driven with one gentle start and
    one gentle stop (no stopping at every corner). Facing and front / back view follow where the nose points."""

    def __init__(self, pts, dur, reverse=False):
        pts = [(float(a), float(b)) for a, b in pts]
        if len(pts) > 2:                                # round every corner (a car turns in a curve, never
            dense = [pts[0]]                            # overshoots it): a bend from before to after the corner
            for i in range(1, len(pts) - 1):
                a, c, b = pts[i - 1], pts[i], pts[i + 1]
                li = math.hypot(c[0] - a[0], c[1] - a[1])
                lo = math.hypot(b[0] - c[0], b[1] - c[1])
                r = min(0.45 * li, 0.45 * lo, 260.0)
                if r < 5:
                    dense.append(c)
                    continue
                p_in = (c[0] + (a[0] - c[0]) * r / li, c[1] + (a[1] - c[1]) * r / li)
                p_out = (c[0] + (b[0] - c[0]) * r / lo, c[1] + (b[1] - c[1]) * r / lo)
                for k in range(0, 9):
                    u = k / 8.0
                    dense.append(((1 - u) ** 2 * p_in[0] + 2 * u * (1 - u) * c[0] + u * u * p_out[0],
                                  (1 - u) ** 2 * p_in[1] + 2 * u * (1 - u) * c[1] + u * u * p_out[1]))
            dense.append(pts[-1])
            pts = dense
        self.pts, self.dur, self.reverse = pts, dur, reverse
        self.cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(b[0] - a[0], (b[1] - a[1]) * ZK * 2.5))
        self.length = self.cum[-1]
        # slower through the bends: each piece "costs" more time the more the way turns there (a driver brakes
        # into a corner and speeds up out of it), so the drive keeps its length and total time
        self.cost = [0.0]
        n = len(pts)
        for i in range(1, n):
            L = self.cum[i] - self.cum[i - 1]
            turn = 0.0
            for j in (i - 1, i):
                if 0 < j < n - 1:
                    a, b, c = pts[j - 1], pts[j], pts[j + 1]
                    a1 = math.atan2((b[1] - a[1]) * ZK * 2.5, b[0] - a[0])
                    a2 = math.atan2((c[1] - b[1]) * ZK * 2.5, c[0] - b[0])
                    turn += abs((a2 - a1 + math.pi) % (2 * math.pi) - math.pi) * 0.5
            per = turn / max(L, 15.0) * 100.0                 # radians per 100 units of road
            self.cost.append(self.cost[-1] + L * (1.0 + 1.6 * min(per, 2.0)))

    def _d(self, u):
        """Distance along the drive at 0..1 of its time (gentle start / stop, slower in the bends)."""
        c = ease(u, "inout") * self.cost[-1]
        i = 1
        while i < len(self.cost) - 1 and self.cost[i] < c:
            i += 1
        span = max(1e-9, self.cost[i] - self.cost[i - 1])
        return self.cum[i - 1] + (self.cum[i] - self.cum[i - 1]) * clamp((c - self.cost[i - 1]) / span, 0.0, 1.0)

    def _seg(self, u):
        d = self._d(u)
        i = 1
        while i < len(self.cum) - 1 and self.cum[i] < d:
            i += 1
        a, b = self.pts[i - 1], self.pts[i]
        L = max(1e-6, self.cum[i] - self.cum[i - 1])
        f = clamp((d - self.cum[i - 1]) / L, 0.0, 1.0)
        return a, b, f

    def at(self, u, facing=1):
        """(x, z, facing) at 0..1 of the drive."""
        a, b, f = self._seg(u)
        x, z = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        dx = b[0] - a[0]
        if abs(dx) > 1.0:
            facing = 1 if dx > 0 else -1
            if self.reverse:
                facing = -facing
        return x, z, facing

    def point_at(self, d):
        """(x, z) at distance d along the drive."""
        d = clamp(d, 0.0, self.length)
        i = 1
        while i < len(self.cum) - 1 and self.cum[i] < d:
            i += 1
        a, b = self.pts[i - 1], self.pts[i]
        L = max(1e-6, self.cum[i] - self.cum[i - 1])
        f = clamp((d - self.cum[i - 1]) / L, 0.0, 1.0)
        return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f

    def tangent(self, u, span=70.0):
        """The way the nose points at 0..1 of the drive (dx, dz in story units), smoothed over about a car's
        length so it turns gradually through the corners."""
        d = self._d(u)
        h = min(span, self.length / 2.0)
        a, b = self.point_at(d - h), self.point_at(d + h)
        dx, dz = b[0] - a[0], b[1] - a[1]
        if abs(dx) + abs(dz) < 1e-6:
            return None
        return (-dx, -dz) if self.reverse else (dx, dz)

    def view(self, u):
        a, b, _f = self._seg(u)
        dx, dz = b[0] - a[0], (b[1] - a[1]) * ZK * 2.5
        if abs(dz) > abs(dx) * 1.2:                     # mostly toward / away from the camera
            back = dz > 0
            if self.reverse:
                back = not back
            return "back" if back else "front"
        return None


class PropTrack:
    def __init__(self, spec):
        self.id = spec.get("id") or spec.get("type", "prop")
        self.type = str(spec.get("type", self.id)).lower()
        self.vtype = vehicle_type(self.type)
        if self.vtype is None and (spec.get("_picture_vehicle") or spec.get("vehicle") is True):
            self.vtype = "picture"                          # one of your pictures used as a vehicle
        self.spec = spec
        self.scale = float(spec.get("scale", 1.0))
        f = spec.get("facing", "right")
        self.facing0 = -1 if str(f).lower() in ("left", "-1") else 1
        self.states = [(0.0, ("rest", float(spec.get("x", 0)), float(spec.get("y", 0))))]
        self.z0 = parse_z(spec.get("z", spec.get("depth")))
        self.zmoves = []        # (start, dur, z0, z1, view)  driving into / out of the scene (3D mode)
        self.routes = {}        # move start -> Route: a vehicle driving round things / turning (x and z together)
        if spec.get("held_by"):
            self.states = [(0.0, ("held", spec["held_by"]))]
        elif spec.get("in"):                                # in a bag / the trunk since an earlier scene
            self.states = [(0.0, ("in", spec["in"]))]
        self.riders = 0
        self.doors = []         # (time, seat, "in" | "out")  door opens while someone gets in / out
        self.events = []        # (time, kind, value)  objects: open / close / break / float / sink / rustle / shake

    def add(self, t, state):
        self.states.append((t, state))
        self.states.sort(key=lambda s: s[0])

    def at(self, t):
        cur = self.states[0][1]
        start = 0.0
        for tt, s in self.states:
            if tt <= t:
                cur, start = s, tt
        return cur, start

    def pos(self, t):
        """(x, y, facing) for vehicles / moving props."""
        facing = self.facing0
        x, y = 0.0, 0.0
        for tt, s in self.states:
            if tt > t:
                break
            if s[0] == "rest":
                x, y = s[1], s[2]
            elif s[0] == "move":
                _, x0, y0, x1, y1, dur, arc = s[:7]
                u = clamp((t - tt) / max(dur, 0.01), 0, 1)
                rt = self.routes.get(tt)
                if rt is not None:                          # driving a route: round things, a U-turn
                    x, _z, facing = rt.at(u, facing)
                    y = y0 + (y1 - y0) * ease(u, "inout")
                    continue
                if x1 != x0:
                    facing = 1 if x1 > x0 else -1
                    if len(s) > 7 and s[7] == "reverse":      # backing up: the nose keeps pointing the old way
                        facing = -facing
                kind_ = s[7] if len(s) > 7 else None
                if kind_ == "fall":                         # from rest under gravity: y goes with t²
                    x, y = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u * u
                    continue
                if kind_ == "flutter":                      # a leaf / paper: slow, steady, swinging side to side
                    sw = arc or 40.0
                    x = x0 + (x1 - x0) * u + sw * math.sin(u * dur * 3.1) * (1 - u * 0.5)
                    y = y0 + (y1 - y0) * u + 0.15 * sw * abs(math.cos(u * dur * 3.1))
                    continue
                k = ease(u, "inout") if self.vtype or kind_ in ("push", "roll") else u
                x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k + arc * 4 * u * (1 - u)
        sh = self._shake(t)
        tl = getattr(self, "_tl", None)
        if tl is not None and not self.spec.get("y"):         # standing / driving on a hill
            y += tl.ground_y(x, self.z_at(t), exclude=self.id)
        return x + sh, y, facing

    # -- interactive objects (engine/objects.py)
    def _last(self, t, kinds):
        got = None
        for tt, kind, val in self.events:
            if tt <= t and kind in kinds:
                got = (tt, kind, val)
        return got

    def open_at(self, t):
        amt = 1.0 if self.spec.get("open") else 0.0
        for tt, kind, _ in sorted(self.events, key=lambda e: e[0]):
            if tt > t or kind not in ("open", "close"):
                continue
            u = smoothstep(clamp((t - tt) / 0.5, 0, 1))
            amt = amt + ((1.0 if kind == "open" else 0.0) - amt) * u
        return amt

    def state_at(self, t):
        """The picture state of an object from an object sheet (None = its normal picture)."""
        got = self._last(t, ("state",))
        st = got[2] if got else self.spec.get("state")
        return None if st in (None, "", "normal", "off", "closed") else st

    def broken_at(self, t):
        got = self._last(t, ("break",))
        return (t - got[0]) if got else (1e9 if self.spec.get("broken") else None)

    def water_at(self, t):
        got = self._last(t, ("float", "sink", "dry"))
        if not got or got[1] == "dry":
            return None
        return got[1], got[0]

    def roll_at(self, t):
        """Signed distance rolled so far (round objects turn by this / radius)."""
        d = 0.0
        for tt, s in self.states:
            if tt > t:
                break
            if s[0] == "move" and len(s) > 7 and s[7] in ("roll", "push"):
                u = clamp((t - tt) / max(s[5], 0.01), 0, 1)
                d += (s[3] - s[1]) * ease(u, "inout")
        return d

    def spin_at(self, t):
        """Tumbling while flying through the air (thrown / kicked)."""
        a = 0.0
        for tt, s in self.states:
            if tt > t:
                break
            if s[0] == "move" and len(s) > 7 and s[7] == "throw":
                u = clamp((t - tt) / max(s[5], 0.01), 0, 1)
                a += -math.copysign(1, s[3] - s[1] or 1) * u * s[5] * 9.0
        return a

    def rustle_at(self, t):
        got = self._last(t, ("rustle",))
        return max(0.0, 1 - (t - got[0]) / 0.8) if got else 0.0

    def _shake(self, t):
        for tt, kind, val in self.events:
            if kind == "shake" and tt <= t <= tt + val:
                return 3.0 * math.sin(t * 40) * math.sin(math.pi * (t - tt) / val)
        return 0.0

    def travel(self, t):
        """Total distance travelled (for wheel rotation)."""
        d = 0.0
        for tt, s in self.states:
            if tt > t:
                break
            if s[0] == "move":
                _, x0, y0, x1, y1, dur = s[:6]
                u = clamp((t - tt) / max(dur, 0.01), 0, 1)
                k = ease(u, "inout") if self.vtype else u
                rt = self.routes.get(tt)
                if rt is not None:                          # wheels turn for the whole way driven (depth too)
                    d += rt._d(u)
                    continue
                zm = next((m for m in self.zmoves if abs(m[0] - tt) < 1e-6), None)
                d += math.hypot(x1 - x0, ((zm[3] - zm[2]) * ZK * 2.5) if zm else 0.0) * k
        return d

    def moves_between(self, a, b):
        return any(s[0] == "move" and tt < b and tt + s[5] > a for tt, s in self.states)

    def moving(self, t):
        cur, st = self.at(t)
        return cur[0] == "move" and t - st < cur[5]

    def doors_at(self, t):
        """How far each door is open (0..1): {seat: amount}. Open before someone steps in / out, close after."""
        out = {}
        for t0, seat, kind in self.doors:
            if kind == "in":
                a, b, c, d = t0 - 0.3, t0, t0 + ENTER_DUR, t0 + ENTER_DUR + 0.3
            else:
                a, b, c, d = t0, t0 + 0.25, t0 + 0.25 + EXIT_DUR, t0 + 0.55 + EXIT_DUR
            if a <= t <= d:
                amt = smoothstep((t - a) / (b - a)) if t < b else (1.0 if t <= c else 1 - smoothstep((t - c) / (d - c)))
                out[seat] = max(out.get(seat, 0.0), amt)
        return out

    def _route_now(self, t):
        for st, rt in self.routes.items():
            if st <= t <= st + rt.dur:
                return st, rt
        return None

    def z_at(self, t):
        cur = self._route_now(t) if self.routes else None
        if cur is not None:
            return cur[1].at(clamp((t - cur[0]) / max(cur[1].dur, 0.01), 0, 1))[1]
        z = self.z0
        for st, dur, z0, z1, _v in self.zmoves:
            if st > t:
                break
            u = clamp((t - st) / max(dur, 0.01), 0, 1)
            z = z0 + (z1 - z0) * ease(u, "inout")
        return z

    def view_at(self, t):
        """None = side view; "front" = driving toward the camera; "back" = driving away."""
        cur = self._route_now(t) if self.routes else None
        if cur is not None:                             # on a route: the view follows the way the car points
            return cur[1].view(clamp((t - cur[0]) / max(cur[1].dur, 0.01), 0, 1))
        v = None
        for st, dur, z0, z1, view in self.zmoves:
            if st > t:
                break
            v = view
        return v

    def heading_at(self, t):
        """The way the nose points (dx, dz in story units, not normalised): through every turn of a drive, and
        where it last drove when parked. Backing up keeps the nose the old way."""
        last = None
        for tt, s in self.states:
            if tt > t:
                break
            if s[0] != "move":
                continue
            u = clamp((t - tt) / max(s[5], 0.01), 0.0, 1.0)
            rt = self.routes.get(tt)
            d = None
            if rt is not None:
                d = rt.tangent(u)
            else:
                zm = next((m for m in self.zmoves if abs(m[0] - tt) < 1e-6), None)
                dx, dz = s[3] - s[1], ((zm[3] - zm[2]) if zm else 0.0)
                if abs(dx) + abs(dz) > 1.0:
                    d = (-dx, -dz) if (len(s) > 7 and s[7] == "reverse") else (dx, dz)
            if d is not None:
                last = d
        if last is None:
            h = self.spec.get("heading")
            if isinstance(h, (int, float)):            # degrees: 0 = right, 90 = away, -90 = toward the camera
                return math.cos(math.radians(h)), math.sin(math.radians(h)) / (ZK * 2.5)
            return float(self.facing0), 0.0
        return last

    def _heading_before(self, t0):
        """Where the nose pointed just before t0 (the last drive before it, or the start)."""
        last = None
        for tt, s in self.states:
            if tt >= t0 - 1e-6:
                break
            if s[0] != "move":
                continue
            rt = self.routes.get(tt)
            if rt is not None:
                d = rt.tangent(1.0)
            else:
                zm = next((m for m in self.zmoves if abs(m[0] - tt) < 1e-6), None)
                dx, dz = s[3] - s[1], ((zm[3] - zm[2]) if zm else 0.0)
                d = ((-dx, -dz) if (len(s) > 7 and s[7] == "reverse") else (dx, dz)) if abs(dx) + abs(dz) > 1 else None
            if d is not None:
                last = d
        if last is None:
            h = self.spec.get("heading")
            if isinstance(h, (int, float)):
                return math.cos(math.radians(h)), math.sin(math.radians(h)) / (ZK * 2.5)
            return float(self.facing0), 0.0
        return last

    def speed_at(self, t, dt=0.1):
        x0, _, _ = self.pos(t)
        x1, _, _ = self.pos(t + dt)
        return math.hypot(x1 - x0, (self.z_at(t + dt) - self.z_at(t)) * 3.0) / dt


class SceneTimeline:
    def __init__(self, scene_spec, characters, fps, index, warn, speak_fn, world_width, crowd_fn=None, bg=None):
        self.spec = scene_spec
        self.bg = bg                # the Background (water checks for objects)
        self.index = index
        self.fps = fps
        self.warn = warn
        self.world_w = world_width
        self.auto_face = scene_spec.get("auto_face", True)
        self.acting = scene_spec.get("acting", "auto")      # body language from the words (engine/acting.py)
        self.follow_roads = scene_spec.get("follow_roads", True)   # vehicles drive along roads / paths
        self.drive_side = scene_spec.get("drive_side", "left")     # keep left (India); "right" elsewhere
        # 0.5 calm .. 1 normal .. 1.5 cartoony; education ("physics": "real") = pure physics, always 1.0
        self.real = realworld.is_real(scene_spec)
        try:                                                # gravity here (a planet: engine/galaxy.py)
            self.g = max(0.05, float(scene_spec.get("gravity", realworld.G)))
        except (TypeError, ValueError):
            self.g = realworld.G
        self.exaggeration = realworld.exaggeration_of(scene_spec)
        self.cloth = scene_spec.get("cloth", True) is not False            # hair / dupatta / cape swing
        self.anticipation = scene_spec.get("anticipation", True) is not False and not self.real
        self.walk_mood = scene_spec.get("walk_mood", True) is not False
        self.distance_maps = scene_spec.get("distance_maps", True) is not False
        self.tracks = {}
        self.crowd = []
        self.props = {}
        self._rel_locks = []                 # (time, camera x): placed from the camera's view -> that camera
        self.speeches = []
        self.sfx = []           # (time, name, volume, who)
        self.loops = []         # (start, end, name, volume, who)  looping sounds (engines)
        self.camera = []        # (time, dict)
        self.footsteps = []     # (time, who, kind)
        self.effects = []       # dict(start, kind, x, y, who, dur)
        self.mood_fx = []       # (start, mood_name, fade)   lighting moods (depth.MOODS)
        self.leaves = []        # (start, end)   foreground leaves passing the camera
        self.blur = []          # (start, on)    focus blur on/off (camera "focus_blur")
        self.pictures = []      # dict(start, name, dur, caption, style)  real-image "picture moments"
        self.texts = []         # dict(start, dur, text, style)  words on screen: a road sign, "2 hours later..."
        self.space_trips = []   # dict(start, dur, route)  a rocket trip's full-screen shot (engine/spacetrip.py)
        self.physics_huds = []  # dict(start, dur, spec, ...)  stopwatch, numbers and graph of an experiment
        self.weather_fx = []    # (start, weather, fade)   rain starts / stops during the scene
        self.mode3d = False     # true 2.5D world (camera_mode "3d"), set by the project
        self.room3d = False     # an indoor place as a 3D room (set by the project)
        self.photo3d = None     # name of the background picture shown as 2.5D depth layers
        bgs = scene_spec.get("background") if isinstance(scene_spec.get("background"), dict) else {}
        self.depth = bool(scene_spec.get("depth") or bgs.get("depth"))
        lighting = scene_spec.get("lighting") or bgs.get("lighting")
        if lighting:
            self.mood_fx.append((0.0, mood_name(lighting), 0.01))
        if scene_spec.get("foreground_leaves") or bgs.get("foreground_leaves"):
            self.leaves.append((0.0, 1e9))
        self.duration = 0.0
        self._speak = speak_fn
        self._crowd_moves = []
        self._build(characters)
        if crowd_fn and scene_spec.get("crowd"):
            self._build_crowd(crowd_fn)
        for e_, t_ in self._crowd_moves:                  # crowd moves wait until the crowd exists
            self._group_move(e_, t_, now=True)

    # ------------------------------------------------------------------ public helpers
    def prop_holder_of(self, cid, t):
        for p in self.props.values():
            s, _ = p.at(t)
            if s[0] == "held" and s[1] == cid:
                return p.id
        return None

    def focus_target(self, cid, t):
        who = self.focus_who(cid, t)
        return self.tracks[who].x_at(t) if who is not None else None

    def focus_who(self, cid, t):
        """Who this character should face now in a conversation, or None: the speaker faces the one the
        line is said to (else the nearest person), listeners face the speaker; for a moment after a line the
        two keep facing each other (a bow, a nod, a pause) instead of snapping back."""
        cur = None
        for sp in self.speeches:
            if sp.who in self.tracks and sp.start <= t < sp.end:
                cur = sp
                break
        if cur is None:                                  # between lines: the last line (just said) still holds
            for sp in self.speeches:
                if sp.who in self.tracks and sp.end <= t < sp.end + 2.5 and (cur is None or sp.end > cur.end):
                    cur = sp
            if cur is not None and cid not in (cur.who, cur.to):
                cur = None                               # only the two who talked
        if cur is None:
            return None
        if cur.who != cid:
            return cur.who if self._visible(cur.who, t) else None
        if cur.to in self.tracks and self._visible(cur.to, t):
            return cur.to
        me = self.tracks[cid].x_at(t)
        others = [(abs(tr.x_at(t) - me), k) for k, tr in self.tracks.items()
                  if k != cid and not tr.crowd and self._visible(k, t)]
        return min(others)[1] if others else None

    def _addressees(self):
        """Who each line is said to: the story's "facing"/"to" on the line, else the person who spoke just before
        (a reply), else the next speaker (a question), else nobody (the nearest person)."""
        spk = sorted([sp for sp in self.speeches if sp.who in self.tracks], key=lambda q: q.start)
        for i, sp in enumerate(spk):
            if sp.to is not None:
                continue
            for j in range(i - 1, -1, -1):
                o = spk[j]
                if sp.start - o.end > 8.0:
                    break
                if o.who != sp.who:
                    sp.to = o.who
                    break
            if sp.to is None:
                for o in spk[i + 1:]:
                    if o.start - sp.end > 8.0:
                        break
                    if o.who != sp.who:
                        sp.to = o.who
                        break

    def _visible(self, cid, t):
        tr = self.tracks[cid]
        i = tr.seg_index(t)
        if i < 0:
            return not tr.hidden
        return tr.segments[i].action != "disappear"

    # ------------------------------------------------------------------ building
    def _resolve_x(self, value, who, t, cur_x):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, (list, tuple)) and value:
            return float(value[0])
        if isinstance(value, str):
            v = value.lower()
            if v in ("offscreen_left", "left_edge", "off_left", "left"):
                return -260.0 if v != "left" else self.world_w * 0.15
            if v in ("offscreen_right", "right_edge", "off_right", "right"):
                return self.world_w + 260.0 if v != "right" else self.world_w * 0.85
            if v in ("center", "middle"):
                return self.world_w / 2
            if value in self.tracks and value != who:
                ox = self.tracks[value].x_at(t)
                side = -1 if cur_x < ox else 1
                c = self.tracks[value].cdef
                gap = 120 * c.scale if c.kind == "human" else (c.animal.get("body", 60) * 0.7 + 90) * c.scale
                return ox + side * gap
            if value in self.props:
                p = self.props[value]
                if p.vtype:
                    return p.pos(t)[0]
                s, _ = p.at(t)
                if s[0] == "rest":
                    return s[1] - (35 if cur_x < s[1] else -35)
        self.warn(f"scene {self.index + 1}: can't understand position '{value}'")
        return cur_x

    def _stage_rules(self, cid, x, z, c):
        """Real-world rules for where a character starts (fixed quietly, with a note):
        nobody stands inside a rock / chest / parked car or inside another person, and somebody far away
        (z > 1000) stands on the path in the middle, where the camera can see them."""
        from . import objects
        W = self.world_w
        if z > 1000 and abs(x - W / 2) > 110 and not c.get("in") and not c.get("hidden"):
            nx = W / 2 + max(-100.0, min(100.0, x - W / 2))
            self.warn(f"fixed: scene {self.index + 1}: {cid} is far away (z {z:.0f}) - moved onto the path (x {nx:.0f})")
            x = nx
        if c.get("in") or c.get("riding"):
            return x, z
        walk_ids = {w_[0] for w_ in self._walk_list()}
        for pid, o in self.props.items():
            if pid in walk_ids:
                continue                                # a stage / floor / steps: standing ON it is fine
            if o.vtype:
                ox, oz, w = o.pos(0)[0], o.z_at(0), 520.0 * o.scale * (1.6 if o.vtype == "bus" else 1.0)
            elif objects.is_object(o) and o.at(0)[0][0] == "rest":
                ox, oz, w = o.at(0)[0][1], o.z_at(0), objects.size(o)[0]
            else:
                continue
            from . import images as _im
            _img = objects._image_name(o) if not o.vtype else None
            if _img and (_im.info(_img) or {}).get("foot"):
                continue                                # a 3D thing: its real footprint is checked below
            if abs(x - ox) < w / 2 + 25 and abs(z - oz) < 90:
                nz = max(0.0, oz - 130.0) if oz >= 130 else oz + 130.0
                self.warn(f"fixed: scene {self.index + 1}: {cid} was standing inside '{pid}' - moved in front of it")
                z = nz
        if not any(c.get(k) for k in ("on", "inside", "behind", "hidden", "hide", "at_object", "sit_on")):
            x, z = self._free_start(cid, x, z)
        for oid, tr in self.tracks.items():
            if abs(tr.x0 - x) < 70 and abs(tr.z0 - z) < 70:
                nx = x + (130.0 if x >= tr.x0 else -130.0)
                self.warn(f"fixed: scene {self.index + 1}: {cid} and {oid} stood in the same spot - moved apart")
                x = nx
        return x, z

    def _free_start(self, cid, x, z):
        """Nobody starts INSIDE a hut wall, a pillar, a tree trunk or a bush (3D footprints): step to the nearest
        open ground - in front first (toward the camera), then to the sides, then behind."""
        try:
            obs = self._obstacles(None, 0.0, people=False)
        except Exception:
            return x, z

        def inside(px, pz):
            return any(abs(px - ox) < hw + 20 and oz - hd - 15 < pz < oz + hd + 15 and oy < STEP_UP
                       for ox, oz, hw, hd, oy in obs)
        if not inside(x, z):
            return x, z
        got = self._nearest_free(x, z, inside)
        if got is None:
            return x, z
        self.warn(f"fixed: scene {self.index + 1}: {cid} was placed inside something solid - moved to "
                  f"x {got[0]:.0f}, z {got[1]:.0f}")
        return got

    def _nearest_free(self, x, z, inside):
        """The nearest open ground to (x, z): in front (toward the camera) or to the side first - a spot behind
        a hut would count as being IN the hut - behind only when nothing nearer is free."""
        best = None
        for r in (50, 90, 140, 200, 270, 350, 450, 560, 700):
            for k in range(16):
                a = k * math.pi / 8.0
                dx, dz = math.cos(a), -math.sin(a)          # dz < 0 = toward the camera
                nx, nz = x + dx * r * 1.3, z + dz * r
                if nz < 0 or not (-200 <= nx <= self.world_w + 200) or inside(nx, nz) or self._is_water(nx, nz):
                    continue
                cost = r + (140.0 if dz > 0.2 else 0.0)
                if best is None or cost < best[0]:
                    best = (cost, round(nx), round(nz))
            if best is not None and best[0] <= r + 1:
                break                                        # nothing further can be nearer
        return None if best is None else (best[1], best[2])

    def _hill_named(self, name):
        hills = getattr(self.bg, "hills", None) if self.bg is not None else None
        if not hills:
            return None
        k = str(name).lower().strip().replace(" ", "_")
        if k in ("hill", "hilltop", "hill_top", "top_of_hill", "top_of_the_hill", "the_hill", "up_the_hill"):
            return hills[0]
        m = re.match(r"^hill_?(\d+)$", k)
        if m and 1 <= int(m.group(1)) <= len(hills):
            return hills[int(m.group(1)) - 1]
        return None

    def ground_y(self, x, z, exclude=None, ref=None):
        """Height of the ground at story (x, z): 0 on flat land, up the hills of a place JSON, and on the
        walkable tops of 3D code things (steps, platforms, jetties, bridges, balconies, roofs, terrain).
        ref = the height someone is at now: where surfaces are stacked (a balcony over a floor) they stay on
        the one they can step onto (at most STEP_UP higher) instead of popping up to the highest one."""
        cands = self._ground_cands(x, z, exclude)
        if ref is None:
            return max(c[0] for c in cands)
        return pick_level([c[0] for c in cands], ref)

    def _ground_cands(self, x, z, exclude=None):
        """[(height, level?)] of every surface at story (x, z): the tops of walkable things, the hills, and the
        plain ground - but NOT the plain ground under something that stands on it (a hill, stairs, a stage: you
        can't walk inside them); under a raised thing (a balcony, a gallery) the ground is there."""
        hy = self._hill_y(x, z)
        tops = self._walk_tops(x, z, exclude, with_flat=True)
        covered = any(g for _y, _f, g in tops)
        base = [] if (covered and hy < 1.0) else [(hy, hy < 1.0)]
        return base + [(y, f) for y, f, _g in tops] or [(0.0, True)]

    def _hill_y(self, x, z):
        """Height of the hills of a place JSON at story (x, z) (0 off the hills)."""
        hy = 0.0
        hills = getattr(self.bg, "hills", None) if self.bg is not None else None
        for h in hills or ():
            u, v = abs(x - h["xc"]) / h["a"], abs(z - h["zc"]) / h["b"]
            if u >= 1.0 or v >= 1.0:
                continue
            fu = 1.0 if u < h["top"] else math.cos(math.pi / 2 * (u - h["top"]) / (1.0 - h["top"])) ** 2
            fv = 1.0 if v < 0.35 else math.cos(math.pi / 2 * (v - 0.35) / 0.65) ** 2
            hy = max(hy, h["H"] * fu * fv * (1.0 if getattr(self, "mode3d", False) else h["p"]))
        return hy

    def ground_level(self, x, z, ref):
        """(height, level?) of the ground someone at height ref steps onto at (x, z): level = a flat tread / floor
        (steps are fine), not level = a slope (a hill side: only gentle ones can be walked)."""
        tops = self._ground_cands(x, z)                      # place-JSON hills count as a slope
        ok = [t for t in tops if t[0] <= ref + STEP_UP]
        return max(ok, key=lambda t: t[0]) if ok else min(tops, key=lambda t: t[0])

    def _walk_list(self):
        """[(prop id, [(poly world XZ, plane)...], bbox)] of the walkable 3D things (at their resting spot)."""
        got = getattr(self, "_walk_cache", None)
        if got is not None:
            return got
        from . import objects, images
        from .world3d import X_of, p3, Z_of_z
        out = []
        A = self.world_w / 2.0
        for pid, o in getattr(self, "props", {}).items():
            if getattr(o, "vtype", None):
                continue
            img = objects._image_name(o)
            meta = images.info(img) if img else None
            if not meta or not meta.get("walk"):
                continue
            try:
                x0, z0 = float(o.pos(0.0)[0]), float(o.z_at(0.0))
            except Exception:
                continue
            h_draw = objects.size(o)[1]
            sc = h_draw / max(1.0, float(meta.get("height") or h_draw))
            X0, Z0 = X_of(x0, p3(z0), A), Z_of_z(z0)
            turn = math.radians(float(o.spec.get("turn") or 0.0))
            ct, st = math.cos(turn), math.sin(turn)
            fx = -1.0 if o.spec.get("flip") else 1.0
            y_off = float(o.spec.get("y") or 0.0)            # a raised thing (a balcony) keeps its height
            polys = []
            for poly in meta["walk"]:
                P = []
                for (px, py, pz) in poly:
                    px *= fx
                    rx, rz = px * ct + pz * st, -px * st + pz * ct
                    P.append((X0 + rx * sc, py * sc + y_off, Z0 + rz * sc))
                if len(P) < 3:
                    continue
                a, b, c = P[0], P[1], P[2]
                u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
                v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
                n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                if abs(n[1]) < 1e-6:
                    continue
                polys.append((P, a, n))
            if polys:
                xs = [q[0] for P, _a, _n in polys for q in P]
                zs = [q[2] for P, _a, _n in polys for q in P]
                out.append((pid, polys, (min(xs), max(xs), min(zs), max(zs))))
        self._walk_cache = out
        return out

    def _walk_y(self, x, z, exclude=None):
        return max([0.0] + self._walk_tops(x, z, exclude))

    def _walk_tops(self, x, z, exclude=None, with_flat=False):
        """Heights of every walkable top over story (x, z) (a floor, the steps, a balcony above ...).
        with_flat: (height, level?) pairs - level = a flat top (a tread, a floor), not a slope."""
        wl = self._walk_list() if self.bg is not None or getattr(self, "props", None) else []
        if not wl:
            return []
        from .world3d import X_of, p3, Z_of_z
        Z = Z_of_z(z)
        X = X_of(x, p3(z), self.world_w / 2.0)
        best = []
        for pid, polys, (bx0, bx1, bz0, bz1) in wl:
            if pid == exclude or not (bx0 - 1 <= X <= bx1 + 1 and bz0 - 1 <= Z <= bz1 + 1):
                continue
            mine = []
            for P, a, n in polys:
                inside = False                            # point in polygon (X, Z plane)
                j = len(P) - 1
                for i in range(len(P)):
                    xi, zi, xj, zj = P[i][0], P[i][2], P[j][0], P[j][2]
                    if (zi > Z) != (zj > Z) and X < (xj - xi) * (Z - zi) / ((zj - zi) or 1e-9) + xi:
                        inside = not inside
                    j = i
                if inside:
                    y = a[1] - (n[0] * (X - a[0]) + n[2] * (Z - a[2])) / n[1]
                    ln = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) or 1.0
                    mine.append((y, abs(n[1]) / ln > 0.97))
            # tops buried inside the same solid (the lower boxes of a staircase) are not floors: keep a top only
            # if nothing of this thing lies less than a storey above it (a real upper floor is further up)
            keep = [p for p in mine if not any(p[0] < q[0] <= p[0] + 150.0 for q in mine)]
            if with_flat:                                   # stands on the ground (not raised like a balcony)
                g = float((self.props[pid].spec.get("y") if pid in self.props else 0.0) or 0.0) <= STEP_UP
                best += [(y, f, g) for y, f in keep]
            else:
                best += [p[0] for p in keep]
        return best

    def _story_of(self, X, Z):
        """World (X, Z) of the 3D stage -> story (x, z)."""
        from .codedraw import z_from_depth
        from .scene3d import FOCAL
        from .world3d import p3
        z = z_from_depth(Z - FOCAL)
        p = p3(z)
        return X * p + self.world_w / 2.0 * (1.0 - p), z

    def door_spots(self, pid, t=0.0):
        """The doors of a 3D thing: [(x, z, out_x, out_z, toward_camera)] in story units - the doorway and a
        spot a few steps outside it."""
        from . import objects, images
        from .world3d import X_of, p3, Z_of_z
        o = self.props.get(pid)
        if o is None or o.vtype:
            return []
        img = objects._image_name(o)
        meta = images.info(img) if img else None
        if not meta or not meta.get("doors"):
            return []
        x0, z0 = float(o.pos(t)[0]), float(o.z_at(t))
        h_draw = objects.size(o)[1]
        sc = h_draw / max(1.0, float(meta.get("height") or h_draw))
        X0, Z0 = X_of(x0, p3(z0), self.world_w / 2.0), Z_of_z(z0)
        turn = math.radians(float(o.spec.get("turn") or 0.0))
        ct, st = math.cos(turn), math.sin(turn)
        fx = -1.0 if o.spec.get("flip") else 1.0
        out = []
        for d in meta["doors"]:
            px, pz, nx, nz = d[0] * fx, d[2], d[3] * fx, d[4]
            rx, rz = px * ct + pz * st, -px * st + pz * ct
            rnx, rnz = nx * ct + nz * st, -nx * st + nz * ct
            DX, DZ = X0 + rx * sc, Z0 + rz * sc
            dx_, dz_ = self._story_of(DX + rnx * 12, DZ + rnz * 12)
            ox, oz = self._story_of(DX + rnx * 110, DZ + rnz * 110)
            out.append((dx_, max(0.0, dz_), ox, max(0.0, oz), rnz < -0.5))
        return out

    def foot_story(self, pid, t=0.0):
        """(x min, x max, z min, z max) in story units of the solid ground footprint of a 3D thing, or None."""
        from . import objects, images
        from .world3d import X_of, p3, Z_of_z
        o = self.props.get(pid)
        if o is None or getattr(o, "vtype", None):
            return None
        img = objects._image_name(o)
        meta = images.info(img) if img else None
        if not meta or not meta.get("foot"):
            return None
        fx0, fx1, fz0, fz1 = meta["foot"]
        x0, z0 = float(o.pos(t)[0]), float(o.z_at(t))
        h_draw = objects.size(o)[1]
        sc = h_draw / max(1.0, float(meta.get("height") or h_draw))
        X0, Z0 = X_of(x0, p3(z0), self.world_w / 2.0), Z_of_z(z0)
        turn = math.radians(float(o.spec.get("turn") or 0.0))
        ct, st = math.cos(turn), math.sin(turn)
        fx = -1.0 if o.spec.get("flip") else 1.0
        pts = []
        for px, pz in ((fx0, fz0), (fx1, fz0), (fx0, fz1), (fx1, fz1)):
            px *= fx
            rx, rz = px * ct + pz * st, -px * st + pz * ct
            pts.append(self._story_of(X0 + rx * sc, Z0 + rz * sc))
        xs, zs = [q[0] for q in pts], [q[1] for q in pts]
        return min(xs), max(xs), max(0.0, min(zs)), max(zs)

    def building_behind(self, x, z):
        """The building with a door that someone standing at (x, z) is behind or inside (a palace, a house) -
        people there come OUT through its door instead of walking through its wall. None if none."""
        best = None
        for pid in self.props:
            ds = self.door_spots(pid)
            if not ds:
                continue
            fs = self.foot_story(pid)
            if fs is None:
                continue
            front = min(fs[2], min(d[1] for d in ds))
            if fs[0] - 30 <= x <= fs[1] + 30 and z > front + 40:
                if best is None or front > best[0]:
                    best = (front, pid)
        return best[1] if best else None

    def walk_top_spot(self, pid):
        """Story (x, z, y) of the middle of the HIGHEST walkable top of a thing (a balcony, a roof, a stage) -
        where "to": "<thing>" takes someone who walks there. None if the thing has no walkable top."""
        from .world3d import Z_of_z
        from .codedraw import z_from_depth
        from .scene3d import FOCAL
        for p_id, polys, _bb in self._walk_list():
            if p_id != pid:
                continue
            P = max(polys, key=lambda q: max(v[1] for v in q[0]))[0]
            X = sum(v[0] for v in P) / len(P)
            Zw = sum(v[2] for v in P) / len(P)
            y = sum(v[1] for v in P) / len(P)
            z = z_from_depth(Zw - FOCAL)
            from .world3d import p3
            p = p3(z)
            x = X * p + self.world_w / 2.0 * (1.0 - p)
            return x, z, y
        return None

    def _objects_with_cutouts(self):
        """The scene's objects + things taken out of its background picture (engine/takeout.py): they go back
        exactly where they were in the picture, now as real objects (unless the story places them itself)."""
        objs = [dict(o) if isinstance(o, dict) else {"id": o, "type": o} for o in (self.spec.get("objects") or [])]
        if self.bg is not None and getattr(self.bg, "place_objects", None):    # real objects of a place JSON
            mine = {o.get("id") for o in objs}
            objs += [dict(o) for o in self.bg.place_objects if o["id"] not in mine]
            for n in getattr(self.bg, "place_notes", []):
                self.warn(f"scene {self.index + 1}: place: {n}")
            for m in getattr(self.bg, "place_missing", []):
                self.warn(f"scene {self.index + 1}: place: '{m['what']}' is not a known thing or picture"
                          + (f" (did you mean {', '.join(m['suggest'])}?)" if m.get("suggest") else
                             " - make it in Studio > Places (Gemini draws it) or Images"))
        objs = [o for o in objs if not o.get("gone")]        # taken away in an earlier scene (engine/belongings.py)
        bg = self.spec.get("background")
        img = bg.get("image") if isinstance(bg, dict) else None
        if not img and self.bg is not None and getattr(self.bg, "backdrop", None):
            img = self.bg.backdrop.get("name")                # a saved (interactive) place built on a photo
        if not img:
            return objs
        from . import images
        meta = images.info(img) or {}
        for name in meta.get("cut_objects") or []:
            om = images.info(name)
            if not om or not om.get("at"):
                continue
            at = om["at"]
            mine = [o for o in objs if o.get("type") == name or o.get("id") == name]
            if not mine:
                objs.append({"id": name, "type": name, "x": self.world_w / 2 + at["dx"], "z": at["z"], "_cutout": True})
            for o in mine:
                o.setdefault("x", self.world_w / 2 + at["dx"])
                o.setdefault("z", at["z"])
        return objs

    def _weather_reactions(self):
        """People react to rain by themselves (engine/weatherline.py): at the first drops they look up and hold
        out a hand; in heavy rain they cover their heads - or, with "react": "run", run for cover under the
        nearest shelter (a tree, a hut, a stall). Someone holding an umbrella just stays under it. Only people
        who are free then (not walking, talking or doing something the story asked)."""
        react = getattr(self, "weather_react", True)
        if react in (False, "off", "none", "no") or not self.weather_fx or getattr(self.bg, "no_air", False):
            return
        from . import weatherline
        base = getattr(self.bg, "weather", "clear") if self.bg is not None else "clear"
        starts = weatherline.rain_starts(self.weather_fx, base)
        content_end = 1.0                                 # where the scene's own story ends (lines, actions,
        for tr_ in self.tracks.values():                  # effects, weather changes)
            for sp_ in tr_.speech:
                content_end = max(content_end, sp_.end)
            for sg_ in tr_.segments:
                if not sg_.spec.persistent:
                    content_end = max(content_end, sg_.end)
        for e_ in getattr(self, "effects", None) or ():
            content_end = max(content_end, float(e_.get("start", 0)) + float(e_.get("dur", 0)))
        for st_, _n, fd_ in self.weather_fx:
            content_end = max(content_end, st_ + fd_)
        if not starts:
            return
        w0 = weatherline.base_levels(base)

        def rain_at(t):
            return weatherline._levels_at(self.weather_fx, w0, t)["rain"]

        def busy_from(tr, a):
            """When this person is next busy (talking or doing something) from time a on (a = busy now)."""
            nxt = 1e9
            for sp in tr.speech:
                if sp.end > a:
                    nxt = min(nxt, max(a, sp.start))
            for sg in tr.segments:
                if sg.action in ("idle", "stand", "appear"):
                    continue
                if (sg.end if not sg.spec.persistent else 1e9) > a:
                    nxt = min(nxt, max(a, sg.start))
            return nxt

        def free(tr, a, b):
            return busy_from(tr, a) >= b
        shelters = []
        for pid, p in self.props.items():
            nm = f"{pid} {p.type}".lower()
            if any(k in nm for k in ("tree", "hut", "house", "stall", "shed", "banyan", "neem", "peepal",
                                       "temple", "shop", "bus_stop", "umbrella", "verandah", "porch")):
                shelters.append(p)
        for t0, heavy in starts:
            t_end = t0
            while t_end < t0 + 120 and rain_at(t_end) > 0.25:
                t_end += 0.25
            t_end = min(t_end, content_end)               # (never longer than the scene's own story: rain that
            #                                               never stops must not stretch the scene)
            for k_, tr in enumerate(self.tracks.values()):
                if tr.cdef.kind != "human" or tr.crowd or tr.riding_at(t0) is not None:
                    continue
                if self.prop_holder_of(tr.cdef.id, t0) and "umbrella" in str(self.prop_holder_of(tr.cdef.id, t0)):
                    continue                              # under an umbrella already
                a = t0 + 0.2 + 0.35 * (k_ % 3)            # not all at the same moment
                if free(tr, a, a + 2.2):
                    x = tr.x_at(a)
                    self._seg(tr, "feel_rain", a, 2.2, x, x, tr.facing_at(a), {}, z=tr.z_at(a))
                    a += 2.2
                if not heavy:
                    continue
                later = any(sg.start > a and sg.action not in ("idle", "stand") for sg in tr.segments)
                if react == "run" and shelters and not later:   # run for cover (when the story has them stay)
                    x, z = tr.x_at(a), tr.z_at(a)
                    best = min(shelters, key=lambda p: abs(p.pos(a)[0] - x) + abs(p.z_at(a) - z))
                    bx = best.pos(a)[0]
                    side = 1 if x >= bx else -1
                    if free(tr, a, a + 3.0):
                        self._add_action(tr, "run", {"to": {"x": bx + side * 70, "z": best.z_at(a) - 40}}, a, "scared")
                    continue
                while a < t_end - 1.5:                     # covered heads whenever they are free in the rain
                    nb = busy_from(tr, a)
                    if nb <= a + 0.05:
                        a += 0.25
                        continue
                    b_ = min(t_end, nb - 0.3)
                    if b_ - a >= 1.5:
                        x = tr.x_at(a)
                        self._seg(tr, "cover_head", a, b_ - a, x, x, tr.facing_at(a), {}, z=tr.z_at(a))
                    a = b_ + 0.3

    def _build(self, characters):
        spec = self.spec
        W = self.world_w
        placed = spec.get("characters", [])
        if isinstance(placed, dict):
            placed = [dict(v, id=k) for k, v in placed.items()]
        n = max(len(placed), 1)
        stage_z = {}
        people = [c for c in placed if isinstance(c, dict) and not c.get("in") and not c.get("riding")]
        if spec.get("auto_stage", True) and len(people) >= 2 and not any(
                ("z" in c or "depth" in c) for c in placed if isinstance(c, dict)):
            # staging in depth: nobody stands in one flat line - alternate near / far like a film blocking
            pattern = (0, 150, 50, 240, 100, 300, 20, 190, 270, 80)
            order = sorted(people, key=lambda c: float(c["x"]) if isinstance(c.get("x"), (int, float)) else 0.0)
            for k, c in enumerate(order):
                stage_z[c.get("id")] = float(pattern[k % len(pattern)])
        from . import images as _imgs
        vlist = []
        for p in (spec.get("vehicles", []) or []):
            p = {"id": p, "type": p} if isinstance(p, str) else dict(p)
            if not vehicle_type(p.get("type", p.get("id"))) and (_imgs.info(str(p.get("type", ""))) or {}):
                p["_picture_vehicle"] = True               # a picture as a vehicle
            elif not vehicle_type(p.get("type", p.get("id"))):
                # a vehicle type we don't have ("new_car_3d"): the nearest one by its words, never a still prop
                was = str(p.get("type", p.get("id")))
                words = [w_ for w_ in re.split(r"[_\-\s\d]+", was.lower() + " " + str(p.get("id", "")).lower())
                         if w_ and w_ != "3d"]
                vt = None
                for w_ in words:                           # one of the 3D vehicles drawn in code (car_3d ...)
                    w_ = VEHICLE_ALIASES.get(w_, w_)
                    if (_imgs.info(w_ + "_3d") or {}):
                        vt = w_ + "_3d"
                        p["_picture_vehicle"] = True
                        break
                vt = vt or next((vehicle_type(w_) for w_ in words if vehicle_type(w_)), None) or "car"
                p["type"] = vt
                self.warn(f"fixed: scene {self.index + 1}: there is no vehicle '{was}' - used a {vt} "
                          "(make one in 🧊 3D Code > ➕ New vehicle, or check the name)")
            vlist.append(p)
        for p in (spec.get("props", []) or []) + self._objects_with_cutouts() + vlist:
            if isinstance(p, str):
                p = {"id": p, "type": p}
            if p.get("relative_to"):                   # placed from the camera's view / next to someone
                p = self._place_rel(p, 0.0)
            pt = PropTrack(p)
            pt._tl = self
            if pt.id in self.props:
                self.warn(f"scene {self.index + 1}: two props / objects are called '{pt.id}' - give each its own id")
            self.props[pt.id] = pt
        self._park_clear()
        from . import objects as _objects
        for p in spec.get("objects", []) or []:
            if isinstance(p, dict) and p.get("_kept"):         # carried in from an earlier scene: a prop, not an object
                continue
            pid = p if isinstance(p, str) else (p.get("id") or p.get("type"))
            pt = self.props.get(pid)
            if pt is not None and not pt.vtype and not _objects.is_object(pt):
                self.warn(f"scene {self.index + 1}: object '{pid}' (type '{pt.type}') is not a known object and has no "
                          f"abilities - use one of: {', '.join(list(_objects.BUILTIN)[:10])} or a picture with abilities")
        for k, c in enumerate(placed):
            if isinstance(c, str):
                c = {"id": c}
            cid = c.get("id")
            if cid not in characters:
                self.warn(f"scene {self.index + 1}: unknown character '{cid}' (add it to 'characters')")
                continue
            if c.get("relative_to"):
                c = self._place_rel(c, 0.0)
            x = c.get("x", W * (k + 1) / (n + 1))
            if isinstance(x, str):
                x = {"offscreen_left": -260, "offscreen_right": W + 260, "center": W / 2,
                     "left": W * 0.2, "right": W * 0.8}.get(x, W / 2)
            facing = c.get("facing", "right" if float(x) < W / 2 else "left")
            facing = -1 if str(facing).lower() in ("left", "-1") else 1
            z = parse_z(c.get("z", c.get("depth")), stage_z.get(cid, 0.0))
            on = c.get("on")
            spot = self.walk_top_spot(on) if isinstance(on, str) and on in self.props else None
            if spot is not None:                        # starts up on a balcony / roof / stage
                if "x" not in c:
                    x = spot[0]
                if "z" not in c and "depth" not in c:
                    z = spot[1]
            else:
                if on:
                    self.warn(f"scene {self.index + 1}: {cid} is 'on' '{on}' but it has no walkable top - use "
                              "\"stand_on\" / \"climb\" for rocks and trees")
                x, z = self._stage_rules(cid, float(x), float(z), c)
            view = VIEW_WORDS.get(str(c.get("facing", "")).lower())
            if view == "side":
                view = None
            if z > 0:
                self.depth = True
            inside = c.get("inside")
            if inside is None and not on and not c.get("hidden") and z > 300 and \
                    str(c.get("from_door", "auto")).lower() not in ("no", "off", "false"):
                inside = self.building_behind(float(x), float(z))     # behind the palace: comes out of its door
            if isinstance(inside, str):                 # starts inside a building: hidden at its door
                ds = self.door_spots(inside) if inside in self.props else []
                if ds:
                    x, z = ds[0][0], ds[0][1]
                else:
                    self.warn(f"scene {self.index + 1}: {cid} is 'inside' '{inside}' but it has no door")
            tr = CharTrack(characters[cid], x, facing, c.get("hidden", False) or bool(inside), c.get("emotion"),
                           scene=self, z=z, view=view)
            tr.inside_of = inside if isinstance(inside, str) else None
            if spot is not None:
                tr.start_level = spot[2]
            elif isinstance(c.get("level"), (int, float)):
                tr.start_level = float(c["level"])
            else:
                tr.start_level = None
            self.tracks[cid] = tr
            if c.get("in") or c.get("riding"):
                vid = c.get("in") or c.get("riding")
                if vid in self.props and self.props[vid].vtype:
                    self._board(tr, vid, 0.0, instant=True)

        events = list(spec.get("events", spec.get("actions", [])) or [])
        narr = spec.get("narration")
        if narr:
            first = {"narrate": narr}
            first.update({"narrate" + k[len("narration"):]: v for k, v in self.spec.items()
                          if k.startswith("narration_")})
            events.insert(0, first)

        events = expand_see(events)
        cursor, prev_start, prev_end = 0.0, 0.0, 0.0
        for n_ev, e in enumerate(events):
            if not isinstance(e, dict):
                self.warn(f"scene {self.index + 1}: event {n_ev + 1} is not an object, skipped")
                continue
            if "at" in e:
                start = float(e["at"])
            elif str(e.get("with", "")).lower() in ("prev", "previous", "last") or e.get("parallel"):
                start = prev_start
            elif "after" in e:
                start = prev_end + float(e["after"])
            else:
                start = cursor + (0.12 if n_ev else 0.0)
            start = max(0.0, start)
            end = self._event(e, start, n_ev)
            prev_start, prev_end = start, end
            cursor = max(cursor, end)

        self._finish_perches()
        self._weather_reactions()
        self._addressees()
        last = cursor
        for st_, _w, fade_ in self.weather_fx:              # the weather change plays out to its end
            last = max(last, st_ + fade_)
        for tr in self.tracks.values():
            for s in tr.segments:
                if not s.spec.persistent:
                    last = max(last, s.end)
        for p in self.props.values():
            for tt, s in p.states:
                if s[0] == "move":
                    last = max(last, tt + s[5])
            for tt, kind, _ in p.events:
                last = max(last, tt + (1.5 if kind in ("sink", "break") else 0.5))
        tail = float(spec.get("tail", 1.2))
        self.duration = max(float(spec.get("duration", 0) or 0), last + tail, 1.0)
        self._auto_dust()
        self._lock_rel_cameras()
        if self.spec.get("show_mentioned", True) not in (False, "off", "no", 0):
            try:                                          # "they reached a waterfall" -> there is a waterfall
                from . import mentioned
                got = mentioned.place(self)
                if got:
                    self.warn(f"fixed: scene {self.index + 1}: the story talks about "
                              + ", ".join(p[0].replace("_said_", "") for p in got)
                              + " - added at the back so it is on screen (\"show_mentioned\": false to stop)")
            except Exception as ex:
                self.warn(f"scene {self.index + 1}: talked-about things skipped ({ex})")
        if self.spec.get("lived_in"):
            try:
                from . import livedin
                got = livedin.place(self, self.spec.get("lived_in"))
                if got:
                    self.warn(f"fixed: scene {self.index + 1}: lived-in props added: "
                              + ", ".join(p[1].replace("lived_in_3d_", "") for p in got[:8]))
            except Exception as ex:
                self.warn(f"scene {self.index + 1}: lived-in props skipped ({ex})")

    # ------------------------------------------------------------------ real physics experiments (engine/physics.py)
    def _physics(self, e, start, n_ev, who):
        """{"experiment": "pendulum", ...} -> a 3D experiment in the scene (+ its stopwatch / numbers / graph);
        {"freeze": "<id>", "duration": 3} -> it stops while someone explains;
        {"who": "ravi", "do": "throw", "angle": 45, "speed": 9} / {"who": "ravi", "do": "drop", "from": 2}."""
        from . import physics
        if "freeze" in e and "experiment" not in e:
            pid = str(e.get("freeze"))
            pr = self.props.get(pid)
            if pr is None or pr.type != "experiment":
                cands = [p for p in self.props.values() if p.type == "experiment"]
                pr = cands[-1] if cands else None
            dur = float(e.get("duration", 2.5))
            if pr is None:
                self.warn(f"scene {self.index + 1}: nothing to freeze ('{pid}' is not an experiment)")
                return start
            pr.spec.setdefault("_freezes", []).append((start, dur))
            return start + dur
        spec = {k: v for k, v in e.items() if k not in ("at", "with", "after", "who", "do", "block", "id")}
        if who and "experiment" not in e:                  # a person throws / drops: it starts at their hand
            kind = "projectile" if str(e.get("do")).lower() == "throw" else "fall"
            spec["experiment"] = kind
            tr = self.tracks.get(who)
            if tr is not None:
                try:
                    x0, z0 = tr.x_at(start), tr.z_at(start)
                except Exception:                          # noqa: BLE001
                    x0, z0 = self.world_w / 2, 300.0
                f = 1
                try:
                    f = tr.facing_at(start) or 1
                except Exception:                          # noqa: BLE001
                    pass
                if kind == "projectile":
                    spec.setdefault("from", 1.5)
                    sp = float(e.get("speed", 10.0))
                    ang = math.radians(float(e.get("angle", 45.0)))
                    g = physics.PLANETS.get(str(e.get("planet", "earth")).lower(), 9.81) or 9.81
                    vs = sp * math.sin(ang)
                    T = (vs + math.sqrt(vs * vs + 2 * g * float(spec["from"]))) / g
                    R = sp * math.cos(ang) * T
                    spec.setdefault("x", x0 + f * (R * physics.M / 2 + 40))
                    if f < 0:
                        spec["flip"] = True
                else:
                    spec.setdefault("height", float(e.get("from", 1.6)))
                    spec.setdefault("objects", e.get("what", "ball"))
                    spec.setdefault("x", x0 + f * 60)
                spec.setdefault("z", z0 + 40)
            if tr is not None:                             # the throw / drop pose (no object needed)
                try:
                    pose = "throw" if kind == "projectile" else "drop"
                    xx = tr.x_at(start)
                    self._seg(tr, pose, start, 0.9, xx, xx, f, {}, z=tr.z_at(start))
                except Exception:                          # noqa: BLE001
                    pass
        if "g" not in spec and "planet" not in spec and abs(self.g - realworld.G) > 0.01:
            spec["g"] = self.g                              # an experiment on another planet uses its gravity
        kind = physics.kind_of(spec.get("experiment"))
        if kind is None:
            self.warn(f"scene {self.index + 1}: unknown experiment '{spec.get('experiment')}' - try: "
                      + ", ".join(physics.NAMES))
            return start
        spec["experiment"] = kind
        real = str(self.spec.get("physics", "story")).lower() in ("real", "school", "true", "on", "yes", "lab")
        try:
            ex = physics.get(spec)
            natural = ex.length() / float(spec.get("slowmo", 1.0) or 1.0)
        except Exception as ex_:                           # noqa: BLE001
            self.warn(f"scene {self.index + 1}: experiment '{kind}' skipped ({ex_})")
            return start
        dur = float(e.get("duration", natural))
        pid = str(e.get("id") or f"exp_{len([p for p in self.props.values() if p.type == 'experiment']) + 1}")
        spec.update({"id": pid, "type": "experiment", "_start": start})
        spec.setdefault("x", self.world_w / 2)
        spec.setdefault("z", 380.0)
        if who:
            spec["_hide_before"] = True                    # the ball is in the hand until it is thrown
            spec.setdefault("_end", start + natural + 2.5)  # ... and is gone (picked up) a little after it lands
        for p in self.props.values():                      # a new experiment on the same table replaces the old one
            if p.type == "experiment" and abs(float(p.spec.get("x", 0)) - float(spec["x"])) < 200 and \
                    abs(float(p.spec.get("z", 0)) - float(spec["z"])) < 200 and "_end" not in p.spec:
                p.spec["_end"] = start
        if e.get("until") is not None:
            spec["_end"] = float(e["until"])
        pt = PropTrack(spec)
        pt._tl = self
        self.props[pid] = pt
        sm = float(spec.get("slowmo", 1.0) or 1.0)
        if e.get("sounds", True) not in (False, 0, "no", "off"):      # a knock when it bounces, a splash ...
            try:
                for tl_, nm_ in ex.sounds()[:12]:
                    if 0 <= tl_ <= natural * sm + 0.01:
                        self.sfx.append((start + tl_ / sm, nm_, 0.55, pid))
            except Exception:                              # noqa: BLE001
                pass
        labels = e.get("labels", real)
        for h in self.physics_huds:                        # one panel at a time: the new one takes over
            if h["start"] + h["dur"] > start:
                h["dur"] = max(0.0, start - h["start"])
        if labels not in (False, 0, "no", "off"):
            self.physics_huds.append(dict(start=start, dur=dur + float(e.get("hold", 1.5)), spec=spec,
                                          graph=e.get("graph", True) not in (False, 0, "no", "off"),
                                          numbers=e.get("numbers", True) not in (False, 0, "no", "off"),
                                          watch=e.get("stopwatch", True) not in (False, 0, "no", "off")))
        if e.get("camera", True) not in (False, 0, "no", "off"):     # the camera looks at it (it is the star)
            w_, h_ = physics.size(spec)
            zoom = round(max(0.5, min(1.5, 640.0 / max(w_ * 0.62, h_, 200.0))), 2)
            self._event({"camera": str(e.get("camera")) if isinstance(e.get("camera"), str) else "medium",
                         "target": pid, "zoom": zoom, "cut": True}, start, n_ev)
        return start + (dur if e.get("block", True) not in (False, 0, "no") else 0.0)

    # ------------------------------------------------------------------ groups that move together (boids)
    def _group_move(self, e, start, now=False):
        """A herd follows its herder, a flock of goats / ducks moves as one, a crowd runs from a tiger: each member
        follows the three boid rules (apart, same way, together) - engine/boids.py. Adds walk / run segments."""
        from . import boids
        crowd = "crowd" in e and not isinstance(e.get("who"), (list, tuple))
        if crowd and not now:
            self._crowd_moves.append((e, start))
            return start + (float(e.get("duration", 4.0)) if e.get("block") else 0.0)
        if crowd:
            members = list(self.crowd)
        else:
            members = [self.tracks[c] for c in e.get("who") if c in self.tracks]
        if not members:
            self.warn(f"scene {self.index + 1}: nobody to move as a group ({e.get('who')})")
            return start
        how = str(e.get("do", e.get("crowd", "herd"))).lower()
        lead = e.get("follow") or e.get("leader") or e.get("with_who")
        frm = e.get("from") or e.get("away_from")
        T = float(e.get("duration", 0) or 0)
        leader_path = None
        if lead in self.tracks:
            ltr = self.tracks[lead]
            if not T:
                ends = [s_.end for s_ in ltr.segments if s_.spec.moving and s_.end > start]
                T = (max(ends) - start + 1.5) if ends else 6.0
            leader_path = lambda t_: (ltr.x_at(start + t_), ltr.z_at(start + t_))        # noqa: E731
        elif isinstance(e.get("to"), (int, float, dict, str)) and how not in ("flee", "scatter"):
            to = e["to"]
            if isinstance(to, dict):
                gx, gz = float(to.get("x", self.world_w / 2)), float(parse_z(to.get("z", 0)))
            else:
                gx, gz = self._resolve_x(to, None, start, self.world_w / 2), members[0].z_at(start)
            leader_path = lambda t_: (gx, gz)                                              # noqa: E731
        flee = None
        if frm in self.tracks:
            ptr = self.tracks[frm]
            flee = lambda t_: (ptr.x_at(start + t_), ptr.z_at(start + t_))                  # noqa: E731
            if leader_path is None:                        # run to the far side, away from it
                px0 = ptr.x_at(start)
                gx = self.world_w + 600 if px0 < self.world_w / 2 else -600
                leader_path = lambda t_: (gx, 300.0)                                        # noqa: E731
        elif frm in self.props:
            pr = self.props[frm]
            flee = lambda t_: (pr.pos(start + t_)[0], pr.z_at(start + t_))                 # noqa: E731
        T = T or (4.0 if flee else 6.0)
        fast = flee is not None or e.get("run") or how in ("flee", "scatter")
        speed = (90.0, 520.0 if fast else 240.0)
        starts = [(m.x_at(start), m.z_at(start)) for m in members]
        seed = stable_hash(f"{self.index}{start:.2f}{how}") % 100000
        try:                                              # solid things the group walks round
            solids = [(ox, oz, hw, hd) for ox, oz, hw, hd, oy in self._obstacles(members[0], start, None, people=False)
                      if abs(oy) < 150]
        except Exception:
            solids = []
        big = max((m.cdef.scale * (200.0 if m.cdef.kind == "quadruped" else 90.0)) for m in members)
        paths = boids.herd_paths(starts, leader_path, T, seed, step=0.5, flee=flee, speed=speed, zk=ZK * 2.5,
                                 solids=solids, size=max(110.0, big * 0.85))
        for m, path in zip(members, paths):
            if crowd:                                      # the crowd stops what it was doing
                keep = []
                for sg in m.segments:
                    if sg.start >= start:
                        continue
                    if sg.end > start:
                        sg.dur = max(0.01, start - sg.start)
                    keep.append(sg)
                m.segments = keep
            steps = [(t0, xa, za, t1, xb, zb) for (t0, xa, za), (t1, xb, zb) in zip(path, path[1:])
                     if math.hypot(xb - xa, (zb - za) * ZK * 2.5) >= 12.0]
            runs, cur = [], []                              # unbroken stretches: one smooth chained walk each
            for st_ in steps:
                if cur and abs(cur[-1][3] - st_[0]) > 1e-6:
                    runs.append(cur)
                    cur = []
                cur.append(st_)
            if cur:
                runs.append(cur)
            for run in runs:
                for k_, (t0, xa, za, t1, xb, zb) in enumerate(run):
                    d = math.hypot(xb - xa, (zb - za) * ZK * 2.5)
                    v = d / max(1e-3, t1 - t0)
                    name = "run" if v > 260 else "walk"
                    aname, _ = m.resolve(name)
                    if aname not in m.actions:
                        aname = "walk" if "walk" in m.actions else next(iter(m.actions))
                    spec = m.actions[aname]
                    if not spec.moving:
                        spec = ActionSpec(spec.fn, spec.dur, moving=True, blend_in=spec.blend_in)
                    f = 1 if xb >= xa else -1
                    if abs(xb - xa) < 6:
                        f = m.segments[-1].facing if m.segments else m.facing0
                    pa = (run[k_ - 1][1], run[k_ - 1][2]) if k_ > 0 else (xa, za)
                    pb = (run[k_ + 1][4], run[k_ + 1][5]) if k_ + 1 < len(run) else (xb, zb)
                    prm = {"_group": how, "_chain": (k_, len(run)), "_cr": (pa, (xa, za), (xb, zb), pb)}
                    m.segments.append(Segment(aname, spec, start + t0, t1 - t0, xa, xb, f, prm, z0=za, z1=zb))
            m.segments.sort(key=lambda s_: s_.start)
        return start + (T if e.get("block", True) else 0.0)

    # ------------------------------------------------------------------ placing things from the camera's view
    def _place_rel(self, spec, t, who=None):
        """{"relative_to": "camera", "x": 300, "y": 0, "z": 1200}: 300 to the camera's right, on the ground (y = up
        from the ground), 1200 away from the camera  ->  the same spec with story x / z (and y).
        {"relative_to": "ravi", "behind": 200} / "front" / "left" / "right" / "x" / "z": next to a character or a
        thing at that moment. The camera is the scene's normal camera at the stage front looking in, centred on
        "camera_x" (a number or a character id; default the middle of the scene); that shot's camera is locked
        (a static wide) so the angle stays as written."""
        from .world3d import FOCAL as F_
        out = dict(spec)
        rt = str(spec.get("relative_to")).lower()
        try:
            if rt in ("camera", "cam", "screen", "lens"):
                cx = self.world_w / 2.0
                camx = spec.get("camera_x", cx)
                if isinstance(camx, str):
                    camx = self.tracks[camx].x_at(t) if camx in self.tracks else (
                        self.props[camx].pos(t)[0] if camx in self.props else cx)
                D = float(spec.get("z", spec.get("distance", spec.get("away", 1200))))
                if D < F_:
                    self.warn(f"scene {self.index + 1}: 'relative_to camera' z = {D:.0f} is closer than the front of "
                              f"the stage ({F_:.0f}) - put at {F_:.0f}")
                    D = F_
                if D <= F_ / 0.42:
                    z = 1000.0 * (1.0 - F_ / D) / 0.58
                else:
                    z = 1000.0 + (D - F_ / 0.42) / 4.0
                z = clamp(z, 0.0, 3000.0)
                p = F_ / D
                xr = float(spec.get("x", 0.0)) + float(spec.get("right", 0.0)) - float(spec.get("left", 0.0))
                out["x"] = round((float(camx) + xr) * p + cx * (1.0 - p), 1)
                out["z"] = round(z, 1)
                if float(spec.get("y", 0.0) or 0.0) > 0:
                    out["y"] = float(spec["y"])
                if spec.get("lock", True) is not False:
                    self._rel_locks.append((t, float(camx)))
            else:
                key = spec.get("relative_to")
                if key in self.tracks:
                    tr = self.tracks[key]
                    bx, bz, f = tr.x_at(t), tr.z_at(t), (tr.facing_at(t) or 1)
                elif key in self.props:
                    pr = self.props[key]
                    bx, _by, f = pr.pos(t)
                    bz, f = pr.z_at(t), (f or 1)
                else:
                    self.warn(f"scene {self.index + 1}: 'relative_to': '{key}' is not a character, thing or 'camera'")
                    return out
                dx = float(spec.get("x", 0.0)) + float(spec.get("right", 0.0)) - float(spec.get("left", 0.0)) + \
                    (float(spec.get("front", 0.0)) - float(spec.get("behind", 0.0))) * (1 if f >= 0 else -1)
                out["x"] = round(bx + dx, 1)
                out["z"] = round(bz + float(spec.get("z", 0.0)), 1)
            out.pop("relative_to", None)
        except (TypeError, ValueError) as ex:
            self.warn(f"scene {self.index + 1}: could not use 'relative_to' ({ex})")
        return out

    def _lock_rel_cameras(self):
        """Every moment something was placed from the camera's view gets that camera (unless the story set one)."""
        for t, camx in getattr(self, "_rel_locks", []):
            if any(abs(tt - t) < 0.3 for tt, c in self.camera if c.get("type") not in ("shake", "punch")):
                continue
            self.camera.append((t, {"type": "static_wide", "x": camx, "zoom": 1.0, "cut": True, "_rel": True,
                                    "lens": 1.0, "foreground": "none", "handheld": 0.0}))
        self.camera.sort(key=lambda c: c[0])

    def _auto_dust(self):
        """Wheels on a dirt / sand road kick up dust behind them (stays where it was kicked up, then settles)."""
        if self.spec.get("dust") is False:
            return
        for pid, p in self.props.items():
            if p.vtype not in ("car", "jeep", "bus", "auto", "bike") and \
                    not any(w in str(getattr(p, "type", "")).lower() for w in ("tractor", "truck", "cart", "jeep")):
                continue
            for tt, s_ in p.states:
                if s_[0] != "move" or s_[5] < 0.4:
                    continue
                x0 = s_[1]
                try:
                    surf = self.surface_at(x0, p.z_at(tt + 0.05))
                except Exception:
                    surf = "grass"
                if surf not in ("dirt", "sand", "mud") and not (surf == "grass" and p.vtype == "jeep"):
                    continue
                self.effects.append(dict(start=tt, kind="dust_trail", dur=float(s_[5]), follow=pid, who=None,
                                         z=p.z_at(tt), intensity=1.4 if p.vtype in ("jeep", "bus") else
                                         (0.5 if p.vtype == "bike" else 1.0)))

    def _event(self, e, start, n_ev):
        if isinstance(e.get("to"), dict) and e["to"].get("relative_to"):
            q = self._place_rel(e["to"], start, e.get("who"))
            e = dict(e, to={"x": q["x"], "z": q["z"]})
        elif e.get("relative_to") and ("effect" in e or "x" in e or "z" in e):
            e = self._place_rel(e, start, e.get("who"))
        if (str(e.get("do", "")).lower() in ("herd", "flock", "follow_group", "flee", "scatter") and
                isinstance(e.get("who"), (list, tuple))) or str(e.get("crowd", "")).lower() in ("flee", "scatter", "follow"):
            return self._group_move(e, start)
        who = e.get("who") or e.get("character")
        keys = [k for k in e if k not in ("at", "with", "after")]
        if "wait" in e and len(keys) == 1:
            return start + float(e["wait"])
        if "narrate" in e or "narration" in e:
            text = e.get("narrate") or e.get("narration")
            dur, clip = self._speak("narrator", text, e, "narrate")
            if hasattr(clip, "texts"):
                text = clip.texts[clip.primary]
            self.speeches.append(Speech("narrator", text, start, dur, clip, None, "narrator"))
            return start + dur
        if "sfx" in e or "sound" in e:
            name = e.get("sfx") or e.get("sound")
            opts = {"for": e.get("for", e.get("length")), "loop": bool(e.get("loop")), "from": e.get("from_sec"),
                    "carry": bool(e.get("carry")), "fade": e.get("fade")}
            self.sfx.append((start, name, float(e.get("volume", 1.0)), who, opts))
            return start + float(e.get("duration", 0.0))
        if "experiment" in e or "freeze" in e or (who and str(e.get("do", "")).lower() in ("throw", "drop") and
                                                   any(k in e for k in ("angle", "speed", "from", "height"))):
            got = self._physics(e, start, n_ev, who)
            if got is not None:
                return got
        if isinstance(e.get("space_trip"), dict) and not who:     # 🚀 the trip between planets (journey.py)
            dur = float(e.get("duration", 8.0))
            self.space_trips.append(dict(start=start, dur=dur, route=e["space_trip"]))
            return start + (dur if e.get("block", True) else 0.0)
        if "text" in e and not who and isinstance(e.get("text"), str):
            # words on the screen (not spoken): {"text": "जंगल 5 km", "style": "sign" | "time" | "title" | "label",
            # "duration": 3} - a road sign board, "2 घंटे बाद...", a big title, a small label
            dur = float(e.get("duration", 3.0))
            self.texts.append(dict(start=start, dur=dur, text=e["text"], style=str(e.get("style", "title")).lower(),
                                   arrow=e.get("arrow", "→" if str(e.get("style", "")).lower() == "sign" else "")))
            return start + (dur if e.get("block") else 0.0)
        pic = e.get("picture") or e.get("photo") or e.get("show_image")
        if pic and not who:
            from . import images
            if not images.exists(pic):
                self.warn(f"scene {self.index + 1}: picture '{pic}' not found (add it in Studio > Images or assets/images)")
                return start
            dur = float(e.get("duration", 4.0))
            self.pictures.append(dict(start=start, name=pic, dur=dur, caption=str(e.get("caption", "")),
                                      style=str(e.get("style", "full")).lower(), move=str(e.get("move", "in")).lower(),
                                      speed=float(e.get("speed", 1.0)), loop=e.get("loop", "loop"),
                                      zoom=float(e.get("zoom", 1.12)), focus=e.get("focus")))
            return start + dur
        if ("weather" in e or "rain" in e) and not who:
            from . import weatherline
            w = e.get("weather", "rain" if e.get("rain", True) not in (False, 0, "off", "stop") else "clear")
            seq = isinstance(w, (list, tuple)) or weatherline.is_sequence(w)
            over = float(e.get("over", e.get("fade", e.get("duration", 20.0 if seq else 2.0))))
            if not isinstance(w, (list, tuple)):
                w = str(w).lower()
            got = weatherline.steps(w, start, over)
            for st_, name_, fade_ in got:
                self.weather_fx.append((st_, name_, fade_))
                if name_ == "storm" and e.get("lightning", True):
                    for k_ in range(max(1, int(fade_ / 5.0))):           # lightning now and then in the storm
                        self._effect({"effect": "lightning", "x": self.world_w * (0.3 + 0.4 * (k_ % 2))},
                                     st_ + 1.0 + k_ * 5.0)
            self.weather_fx.sort(key=lambda q: q[0])
            if e.get("react") is not None:
                self.weather_react = e.get("react")
            return start + (over if e.get("block") else 0.0)
        if "mood" in e and not who:
            self.mood_fx.append((start, mood_name(e["mood"]), float(e.get("duration", e.get("fade", 1.5)))))
            return start + (float(e.get("duration", 0)) if e.get("block") else 0.0)
        if "camera" in e:
            cmd = dict(e)
            cmd["type"] = str(e["camera"]).lower().replace("-", "_").replace(" ", "_")
            self.camera.append((start, cmd))
            from .camera import FX as _FX, ALIASES as _CA
            if _CA.get(cmd["type"], cmd["type"]) not in _FX:
                blur = e.get("focus_blur", e.get("blur", e.get("dof")))
                self.blur.append((start, bool(blur)))
            return start + (float(e.get("duration", 0.0)) if e.get("block") else 0.0)
        if "effect" in e and str(e["effect"]).lower() in ("foreground_leaves", "leaves_front", "bushes", "foliage"):
            d = e.get("duration")
            self.leaves.append((start, start + float(d) if d else 1e9))
            return start
        if "effect" in e:
            self._effect(e, start)
            return start + (float(e.get("duration", 0)) if e.get("block") else 0.0)
        vid = e.get("vehicle")
        if vid and not who and ("to" in e or "move" in e or "by" in e or "y" in e):
            return self._vehicle_move(vid, e, start)
        if "prop" in e and "do" not in e and e.get("fall") not in (None, False):
            return self._prop_fall(e, start)                # a thing falls from a height (roof, tree, table)
        if "prop" in e and "do" not in e and ("to" in e or "move" in e):
            return self._prop_move(e, start)

        if who not in self.tracks:
            if who:
                self.warn(f"scene {self.index + 1}: event {n_ev + 1} uses '{who}' who is not placed in this scene")
            return start
        tr = self.tracks[who]
        end = start
        emotion = norm_emotion(e.get("emotion"))
        icon = e.get("icon")
        if icon:
            tr.icons.append((start, str(icon).lower()))
        if (emotion or icon) and "say" not in e and "do" not in e and "action" not in e:
            if emotion:
                tr.moods.append((start, emotion))
            return start
        if e.get("effect_at_me"):
            self._effect({"effect": e["effect_at_me"], "who": who}, start)

        fv0 = e.get("facing") or e.get("face")
        if fv0 is not None and not (e.get("do") or e.get("action")):
            view = VIEW_WORDS.get(str(fv0).lower())
            if view:
                tr.view_marks.append((start, view))
            elif str(fv0).lower() in ("left", "right") or fv0 in self.tracks:
                tr.view_marks.append((start, "side"))
        say = e.get("say") or e.get("dialogue") or e.get("line")
        if say:
            dur, clip = self._speak(who, say, e, "say")
            if hasattr(clip, "texts"):
                say = clip.texts[clip.primary]
            sp = Speech(who, say, start, dur, clip, emotion, who)
            for k_ in ("facing", "face", "to", "target", "look_at", "at_who"):
                if isinstance(e.get(k_), str) and e[k_] in self.tracks and e[k_] != who:
                    sp.to = e[k_]
                    break
            tr.speech.append(sp)
            self.speeches.append(sp)
            end = start + dur + SPEECH_GAP
            if not (e.get("do") or e.get("action")):
                self._auto_block(tr, sp, e, start)
        action = e.get("do") or e.get("action")
        if action:
            raw = str(action).lower().strip().replace(" ", "_").replace("-", "_")
            got = self._baby_carry(tr, raw, e, start)
            if got is not None:
                return max(end, got)
            from . import duets                          # 💞 two people together: hug, kiss, lift, throw, fight ...
            got = duets.handle(self, tr, raw, e, start, emotion if not say else None)
            if got is not None:
                return max(end, got)
            got = self._people_action(tr, raw, e, start, emotion if not say else None, bool(say))
            if got is not None:
                return max(end, got)
            if raw in OBJ_WORDS or (raw in OBJ_MAYBE and self._object_ref(e)):
                got = self._object_action(tr, raw, e, start)
                if got is not None:
                    return max(end, got)
            if raw in RIDE_WORDS or (vid and raw not in OUT_WORDS):
                return max(end, self._ride_action(tr, raw, e, start))
            if raw in OUT_WORDS:
                return max(end, self._get_out(tr, e, start))
            aname, msg = tr.resolve(action)
            if msg:
                self.warn(f"scene {self.index + 1}: {msg}")
            end = max(end, self._add_action(tr, aname, e, start, emotion if not say else None,
                                            speech_dur=(end - start) if say else 0))
        return end

    # ------------------------------------------------------------------ blocking: moving while talking
    def _auto_block(self, tr, sp, e, start):
        """A scene of pure talk: now and then the speaker moves while saying the line (like film blocking) -
        walks over to someone standing far away, or takes a step toward the one they talk to. Only when nobody
        has moved for a while, never longer than the line, and never for people sitting / riding / hiding.
        "acting": "off" or "calm" (scene or story settings) leaves everyone where the story put them."""
        mode = str(getattr(self, "acting", "auto") or "auto").lower()
        if mode in ("off", "none", "no", "false", "calm") or tr.cdef.kind != "human" or tr.crowd:
            return
        me = tr.cdef.id
        if tr.riding_at(start) is not None or tr.mounted_at(start) is not None or tr.seated_at(start) is not None \
                or not self._visible(me, start):
            return
        i = tr.seg_index(start)
        if i >= 0:
            sg = tr.segments[i]
            if sg.spec.persistent and sg.action not in ("idle", "stand", "appear") or start < sg.end:
                return
        st = self.__dict__.setdefault("_blk", {"n": 0})
        st["n"] += 1
        for o in self.tracks.values():                   # somebody moved a moment ago: no need
            for sg in o.segments:
                if sg.spec.moving and sg.start <= start and sg.end > start - 5.0:
                    return
        other = sp.to if sp.to in self.tracks else self.focus_who(me, start + 0.05)
        if other is None or other not in self.tracks or other == me:
            return
        o = self.tracks[other]
        x0, z0, ox, oz = tr.x_at(start), tr.z_at(start), o.x_at(start), o.z_at(start)
        d = math.hypot(ox - x0, (oz - z0) * ZK)
        side = 1 if x0 >= ox else -1
        gap = 250.0 * max(0.75, (tr.cdef.scale + o.cdef.scale) / 2.0)
        if d > 520.0 and str(sp.text).strip().endswith("!"):
            return                                       # calling out across the place: stays put
        if d > 520.0:                                    # too far to talk: walk over while saying it
            tx, tz = ox + side * gap, oz + (z0 - oz) * 0.35
        elif st["n"] % 3 == 0 and sp.dur >= 1.8 and d > gap + 50.0:
            k = min(130.0, d - gap)                       # a step or two toward them, on a stressed line
            tx, tz = x0 + (ox - x0) / d * k, z0 + (oz - z0) / d * k * 0.6
        elif st["n"] % 3 == 0 and sp.dur >= 1.8:          # close already: a step to a new mark (a little to
            dz_ = 80.0 if (stable_hash(me) + st["n"]) % 2 else -80.0     # the side, nearer / farther)
            tx, tz = x0 + side * 55.0, clamp(z0 + dz_, 0.0, 900.0)
        else:
            return
        speed = (tr.actions["walk"].speed or 230.0) * 0.8
        if math.hypot(tx - x0, (tz - z0) * ZK) / speed > sp.dur + 0.3:
            return
        try:
            self._add_action(tr, "walk", {"to": {"x": round(tx), "z": round(tz)}, "speed": speed}, start, None)
        except Exception:
            pass

    # ------------------------------------------------------------------ actions with / toward people
    def _who_target(self, e, me=None):
        """The character (or object) an action is aimed at: "target", "to", "at_who", "look_at", "with"."""
        for k in ("target", "to", "at_who", "look_at", "with", "toward", "towards"):
            v = e.get(k)
            if isinstance(v, str) and v != me and (v in self.tracks or v in self.props):
                return v
        return None

    def _any_objects(self):
        from . import objects
        return any(objects.is_object(p) for p in self.props.values())

    def _people_action(self, tr, raw, e, start, emotion, has_say):
        """approach / shove someone / stop / carry-without-object. Returns the end time, or None to go on."""
        me = tr.cdef.id
        tgt = self._who_target(e, me)
        if tr.cdef.kind != "human":
            if raw in ("approach", "come_near", "come_closer", "go_near", "walk_up_to"):
                e2 = dict(e, to=tgt) if tgt else dict(e, by=220 * tr.last_facing())
                return self._add_action(tr, "walk", e2, start, emotion)
            return None
        if raw in ("approach", "come_near", "come_closer", "go_near", "walk_up_to", "go_up_to"):
            e2 = {k: v for k, v in e.items() if k not in ("say", "narrate", "target")}
            if "to" not in e2 or e2.get("to") != tgt:
                if tgt:
                    e2["to"] = tgt
                elif "to" not in e2 and "by" not in e2:
                    e2["by"] = 220 * tr.last_facing()
            return self._add_action(tr, "run" if e.get("fast") or e.get("run") else "walk", e2, start, emotion)
        vpush = self._vehicle_ref(e) if raw in ("push", "shove", "pull", "push_car", "push_vehicle") else None
        if vpush:                                         # pushing a car / bike / cart (with helpers)
            return self._push_vehicle(tr, vpush, e, start)
        if raw in ("push", "shove", "push_away") and not self._object_ref(e) and (
                (tgt in self.tracks) or not self._any_objects()):
            t = start
            if tgt in self.tracks:
                other = self.tracks[tgt]
                if abs(other.x_at(t) - tr.x_at(t)) > 170 or abs(other.z_at(t) - tr.z_at(t)) > 60:
                    t = self._add_action(tr, "walk", {"to": tgt}, t, None)
            e2 = {k: v for k, v in e.items() if k not in ("to", "by", "target")}
            if tgt in self.tracks:
                e2["facing"] = tgt
            end = self._add_action(tr, "shove", e2, t, emotion)
            hit = t + 0.45
            self.sfx.append((hit, "whoosh", 0.6, me))
            if tgt in self.tracks and self.tracks[tgt].cdef.kind == "human":
                other = self.tracks[tgt]
                d = 1 if other.x_at(hit) >= tr.x_at(hit) else -1
                self._add_action(other, "stumble", {"by": d * 95 * other.cdef.scale, "facing": me, "duration": 0.7},
                                 hit, None)
                self.sfx.append((hit + 0.05, "thud", 0.5, tgt))
            return end
        rd_ = tr.riding_at(start)
        if raw in ("stop", "halt", "brake", "park", "stop_vehicle", "stop_the_car", "stop_jeep") and rd_ is not None:
            # the driver stops the vehicle (they stay in it - "get_out" to step out)
            vid_ = rd_.params.get("_vehicle")
            v_ = self.props.get(vid_)
            if v_ is not None and v_.moving(start):
                self._brake(v_, start)
            return start + 0.6
        if raw in ("stop", "halt") and not (tgt or has_say or e.get("gesture")):
            return self._add_action(tr, "stand", e, start, emotion)
        if raw in ("carry", "lift", "hold") and not self._object_ref(e) and not self._any_objects():
            return self._add_action(tr, "carry", e, start, emotion)
        return None

    # ------------------------------------------------------------------ pushing vehicles
    def _vehicle_ref(self, e):
        for k in ("vehicle", "object", "target", "to", "thing", "car"):
            v = e.get(k)
            if isinstance(v, str) and v in self.props and self.props[v].vtype:
                return v
        return None

    def _push_vehicle(self, tr, vid, e, start):
        """People push a car / bike / cart / bus from behind: enough people (helpers) and it rolls slowly,
        too few and they strain while it only rocks. "driver": "<id>" steers from inside; "start": true = the
        engine starts at the end (push-start) - the car drives off and the pushers fall flat."""
        v = self.props[vid]
        vt = v.vtype
        need = int(v.spec.get("pushers", VEHICLE_WEIGHT.get(vt, 2)))
        half = (vinfo(v)["w"] / 2.0 if vt == "picture" else VEHICLE_HALF.get(vt, 220)) * float(
            getattr(v, "scale", 1.0) or 1.0)
        x_v, _, _ = v.pos(start)
        z_v = v.z_at(start)
        face = v.facing0 if v.facing0 in (1, -1) else 1
        # which way: "to" / "by", else forward
        if "by" in e:
            dest = x_v + float(e["by"])
        elif isinstance(e.get("to"), (int, float)) or (isinstance(e.get("to"), str) and e.get("to") != vid):
            dest = self._resolve_x(e["to"], tr.cdef.id, start, x_v)
        else:
            n_ = 1 + len(e.get("helpers") or e.get("help") or [])
            dest = x_v + face * float(e.get("distance", 450 if n_ >= need else 140))   # alone: only a little way
        d = 1 if dest >= x_v else -1
        t = start
        driver = e.get("driver")
        if driver in self.tracks and self.tracks[driver].riding_at(t) is None:
            t = self._ride_action(self.tracks[driver], "ride", {"vehicle": vid}, t)
        pushers = [tr] + [self.tracks[h] for h in (e.get("helpers") or e.get("help") or [])
                          if h in self.tracks and h != tr.cdef.id and h != driver]
        stand = x_v - d * (half + 30 * tr.cdef.scale)
        spots = []
        for k, p_tr in enumerate(pushers):               # at the back bumper: side by side in depth (3D / depth
            if self.depth or getattr(self, "mode3d", False):   # scenes), else a tight row behind each other
                zz, xx = max(0.0, z_v - 40 + 70 * k), stand - d * 8 * (k % 2)
            else:
                zz, xx = z_v, stand - d * 34 * k
            spots.append((p_tr, xx, zz))
            t = max(t, self._go(p_tr, xx, zz, start))
        force = len(pushers) + (1 if e.get("strong") else 0)
        dur_try = float(e.get("duration", 0) or 0)
        if force < need - 1 or (need >= 3 and force < need):      # too heavy: straining, the car only rocks
            dur0 = dur_try or 2.4
            for p_tr, xx, zz in spots:
                self._seg(p_tr, "push", t, dur0, xx, xx, d, {"_strain": 1.0, "_hand": -10}, z=zz)
                p_tr.icons.append((t + 0.5, "sweat"))
            v.add(t, ("move", x_v, 0.0, x_v + d * 6, 0.0, dur0 * 0.5, 0.0))
            v.add(t + dur0 * 0.5, ("move", x_v + d * 6, 0.0, x_v, 0.0, dur0 * 0.5, 0.0))
            v.add(t + dur0, ("rest", x_v, 0.0))
            self.warn(f"scene {self.index + 1}: the {vt} is too heavy for {force} - it needs about {need} people "
                      f"(add \"helpers\": [...])")
            return t + dur0
        speed = float(e.get("speed", 0) or 0) or min(170.0, 45.0 + 40.0 * (force - need + 1))
        dx = dest - x_v
        dur = dur_try or max(1.2, abs(dx) / speed)
        for p_tr, xx, zz in spots:
            self._seg(p_tr, "push", t, dur, xx, xx + dx, d, {"_hand": -10, "_strain": 1.0 if force < need else (
                0.4 if force == need else 0.0)},
                      z=zz, spec=ActionSpec(ACTIONS["push"].fn, dur, moving=True, blend_in=0.3))
        v.add(t, ("move", x_v, 0.0, dest, 0.0, dur, 0.0))
        v.add(t + dur, ("rest", dest, 0.0))
        self.loops.append((t, t + dur, "rumble", 0.35, vid))
        end = t + dur
        if e.get("start") or e.get("push_start") or e.get("then_start"):
            self.sfx.append((end, "engine", 0.9, vid))
            self.effects.append(dict(start=end, kind="smoke", x=dest - d * half, y=40, dur=1.6, follow=vid))
            if any(r.params.get("_vehicle") == vid for p2 in self.tracks.values() for r in p2.segments
                   if r.action == "ride"):
                off = dest + d * float(e.get("drive_off", 900))
                v.add(end + 0.4, ("move", dest, 0.0, off, 0.0, 1.8, 0.0))
                v.add(end + 2.2, ("rest", off, 0.0))
                self.loops.append((end + 0.4, end + 2.2, "engine", 0.55, vid))
            for p_tr, xx, zz in spots:                      # the car shoots off: the pushers fall flat
                self._seg(p_tr, "fall", end + 0.45, 1.6, xx + dx, xx + dx + d * 60, d, {}, z=zz)
                self.sfx.append((end + 0.7, "thud", 0.5, p_tr.cdef.id))
            end += 2.2
        return end

    # ------------------------------------------------------------------ actions
    def _add_action(self, tr, aname, e, start, emotion, speech_dur=0.0):
        if aname in ("walk", "run") and getattr(tr, "inside_of", None) and "to" in e and not e.get("through") \
                and not e.get("_via") and not self._visible(tr.cdef.id, start):
            got = self._obj_door(tr, "emerge", dict(e, object=tr.inside_of, run=aname == "run"), start)
            if got is not None:                         # still inside a building: come out of its door first
                return got
        spec = tr.actions[aname]
        cur_x = tr.x_at(start)
        facing = tr.last_facing()
        if tr.riding_at(start) is not None:          # doing something else = get out first
            self._get_out(tr, {}, start)
            cur_x = tr.x_at(start)
        x0 = cur_x
        if "from" in e:
            x0 = self._resolve_x(e["from"], tr.cdef.id, start, cur_x)
        x1 = x0
        z_now = tr.z_at(start)
        z1 = None
        moving = spec.moving or (aname in ("jump", "pounce") and ("to" in e or "by" in e))
        if spec.moving or moving:
            to = e.get("to")
            if isinstance(to, dict):
                if "x" in to:
                    x1 = self._resolve_x(to["x"], tr.cdef.id, start, x0)
                if "z" in to or "depth" in to:
                    z1 = parse_z(to.get("z", to.get("depth")), z_now)
            elif isinstance(to, str) and self._hill_named(to) is not None:     # "hilltop" / "hill_2"
                h_ = self._hill_named(to)
                x1, z1 = h_["xc"] + (0.0 if abs(x0 - h_["xc"]) < 60 else -30.0 * (1 if x0 < h_["xc"] else -1)), \
                    h_["zc"] - 70.0                        # the front of the top: in front of a temple up there
            elif isinstance(to, str) and to not in self.tracks and to.lower() in Z_NAMES:
                z1 = float(Z_NAMES[to.lower()])
            elif isinstance(to, str) and to in self.props and not self.props[to].vtype \
                    and self.walk_top_spot(to) is not None:   # "to": "balcony" / "roof" / "stage": go up onto it
                x1, z1, gy_ = self.walk_top_spot(to)
                mx_, mz_ = self._make_room(tr, x1, z1, start)  # someone already stands there: step beside them
                if (mx_, mz_) != (x1, z1):
                    x1, z1 = mx_, mz_
                    gy_ = self.ground_level(x1, z1, gy_)[0]     # the ground right there (a hillside is lower)
                e = dict(e, _goal_y=gy_)
            elif to is not None:
                x1 = self._resolve_x(to, tr.cdef.id, start, x0)
                if isinstance(to, str) and to in self.tracks:
                    z1 = self.tracks[to].z_at(start)
            elif "by" in e:
                x1 = x0 + float(e["by"])
            elif aname == "retreat":                    # step back: away from someone, or just backwards
                away = e.get("away_from") or e.get("from_who") or self._who_target(e, tr.cdef.id)
                ox = self.tracks[away].x_at(start) if away in self.tracks else None
                back = (1 if x0 >= ox else -1) if ox is not None else -facing
                x1 = x0 + back * float(e.get("distance", 180))
            elif aname == "walk" and str(e.get("do", "")).lower() in ("exit", "leave"):
                x1 = -260.0 if facing < 0 else self.world_w + 260.0
            if "z" in e or "depth" in e:
                z1 = parse_z(e.get("z", e.get("depth")), z_now)
        elif "z" in e or "depth" in e:
            z1 = parse_z(e.get("z", e.get("depth")), z_now)          # instant placement at a depth
        if z1 is not None and abs(z1 - z_now) < 1:
            z1 = None
        if spec.moving and aname not in ("fly", "swim") and not e.get("swim") and tr.cdef.species not in (
                "duck", "fish") and (x1 != x0 or z1 is not None):
            x1, z1 = self._stop_at_water(tr, x0, z_now, x1, z1)
        if spec.moving and aname in ("walk", "run", "hop", "approach") and not e.get("_via"):
            mate = e.get("beside") or e.get("behind") or e.get("with_who")
            if mate in self.tracks and mate != tr.cdef.id:      # walk together: beside or a step behind
                mt = self.tracks[mate]
                me_end = None
                for sg in mt.segments:
                    if sg.spec.moving and sg.start <= start + 0.05 and sg.end > start - 0.05:
                        me_end = sg
                chain_end = None
                if me_end is not None:
                    ends = [sg for sg in mt.segments if sg.spec.moving and sg.start >= me_end.start - 1e-6
                            and sg.params.get("_chain") and sg.start <= me_end.start + 30]
                    chain_end = max(ends, key=lambda q: q.end) if ends else me_end
                if chain_end is not None:
                    mx, mz = mt.x_at(chain_end.end + 1e-3), mt.z_at(chain_end.end + 1e-3)
                    side = 1 if x0 >= mt.x_at(start) else -1
                    if e.get("behind") == mate:
                        dirx = 1 if mx >= mt.x_at(start) else -1
                        x1, z1 = mx - dirx * 110.0, mz + 25.0
                    else:
                        x1, z1 = mx + side * 95.0, mz + 15.0
            if "to" in e and isinstance(e.get("to"), dict) and not e.get("_via"):
                x1, z1 = self._make_room(tr, x1, z1 if z1 is not None else z_now, start)     # people don't stack up
            via = e.get("via")
            way = None
            if isinstance(via, list) and via and not e.get("through"):
                way = []
                for vp in via:
                    if isinstance(vp, dict):
                        way.append((self._resolve_x(vp.get("x", x0), tr.cdef.id, start, x0),
                                    parse_z(vp.get("z", z_now), z_now)))
                way.append((x1, z1 if z1 is not None else z_now))
            elif not e.get("through"):
                self._path_climbs = False
                way = self._plan_path(tr, x0, z_now, x1, z1 if z1 is not None else z_now, start, e)
            if way and len(way) == 1 and abs(way[0][0] - x0) < 20 and abs(way[0][1] - z_now) < 20:
                return start                            # blocked right away: stays where they are
            climbs = bool(way) and getattr(self, "_path_climbs", False)   # up / down stairs: follow the path exactly
            if way:                                      # round things (A*) or through your "via" points: one smooth walk
                base = {k: v for k, v in e.items() if k not in ("to", "by", "duration", "say", "narrate", "via")}
                sp_ = float(e.get("speed", 0) or 0) or None
                t_ = start
                pts = [(x0, z_now)] + [(float(a), float(b)) for a, b in way]
                for n_, (wx, wz) in enumerate(way):
                    p0 = pts[max(0, n_ - 1)] if n_ > 0 else pts[0]
                    p3 = pts[n_ + 2] if n_ + 2 < len(pts) else pts[n_ + 1]
                    en = dict(base, to={"x": wx, "z": wz}, _via=True, _chain=(n_, len(way)))
                    if not climbs:
                        cr_ = (p0, pts[n_], pts[n_ + 1], p3)
                        bl_ = getattr(self, "_path_blocked", None)
                        # the smooth curve must not cut a corner INTO the river or a wall: straight there instead
                        n_s = max(12, int(math.hypot(cr_[2][0] - cr_[1][0], cr_[2][1] - cr_[1][1]) / 12))
                        if not any((self._is_water(*_cr_point(cr_, k_ / n_s)) and not self._is_water(x0, z_now)) or
                                   (bl_ is not None and bl_(*_cr_point(cr_, k_ / n_s)))
                                   for k_ in range(1, n_s)):
                            en["_cr"] = cr_
                    if sp_:
                        en["speed"] = sp_
                    last = n_ == len(way) - 1
                    t_ = self._add_action(tr, aname, en, t_, emotion, speech_dur if last else 0.0)
                return t_
        if z1 is not None:
            self.depth = True
        default_speed = animals.speed_of(tr.cdef, aname) if tr.cdef.kind != "human" else (spec.speed or 300)
        walk_mood = None
        if tr.cdef.kind == "human" and aname in ("walk", "run") and not tr.crowd and getattr(self, "walk_mood", True):
            walk_mood = emotion or tr.mood(start)          # walking by mood: sad drags, angry stomps ...
            if walk_mood in (None, "neutral"):
                for sp_ in tr.speech:                       # or how they just spoke
                    if sp_.emotion and sp_.end <= start + 0.05 and start - sp_.end < 4.0:
                        walk_mood = sp_.emotion
            g_ = mood_gait(walk_mood)
            if g_ is None:
                walk_mood = None
            elif "speed" not in e and "duration" not in e:
                default_speed *= g_["speed"] if aname == "walk" else (0.5 + 0.5 * g_["speed"])
        human = tr.cdef.kind == "human" and not tr.crowd
        if human and aname in ("walk", "run") and "speed" not in e and "duration" not in e:
            default_speed *= realworld.gait(tr.cdef)["speed"]      # heavy people walk a little slower
            default_speed *= {"baby": 0.32, "toddler": 0.5}.get(tr.cdef.age, 1.0)   # a crawl / a toddle is slow
        speed = float(e.get("speed", default_speed))
        jump_k = None
        if human and aname == "jump" and "duration" not in e:      # height and time in the air from the weight
            jump_k = realworld.jump(tr.cdef, self.exaggeration, self.real,
                                    e.get("height") if e.get("height") is not None else None, g=self.g)
        if jump_k is not None:
            dur = jump_k[1]
        elif "duration" in e:
            dur = float(e["duration"])
        elif spec.moving:
            dist = math.hypot(x1 - x0, ((z1 - z_now) * ZK) if z1 is not None else 0.0)
            dur = dist / max(speed, 1) if dist > 1 else 2.0
            mom_ = realworld.start_stop(tr.cdef, aname, speed, self.exaggeration, self.real) if human else None
            if mom_ is not None and dist > 1 and self.real:  # classroom: the extra time a slow start / stop takes
                ch_ = e.get("_chain")
                ta0, tb0 = (0.35, 0.5) if aname == "walk" else (0.25, 0.35)
                extra = (max(0.0, mom_[0] - ta0) if ch_ is None or ch_[0] == 0 else 0.0) + \
                        (max(0.0, mom_[1] - tb0) if ch_ is None or ch_[0] == ch_[1] - 1 else 0.0)
                dur += 0.5 * extra
        else:
            dur = max(spec.dur, speech_dur)
        if x1 != x0:
            facing = 1 if x1 > x0 else -1
            if aname in ("retreat", "stumble"):
                facing = -facing                            # backing away: still facing what they back away from
        fv = e.get("facing") or e.get("face")
        if fv is None and aname in FACE_TARGET:
            fv = self._who_target(e, tr.cdef.id) or e.get("away_from")
            if fv in self.props and fv not in self.tracks:     # an object: turn toward where it is
                fv = "right" if self.props[fv].pos(start)[0] > x0 else "left"
        view = VIEW_WORDS.get(str(fv).lower()) if fv is not None else None
        if view is not None:
            fv = None
        if fv is not None:
            if str(fv).lower() in ("left", "-1"):
                facing = -1
            elif str(fv).lower() in ("right", "1"):
                facing = 1
            elif fv in self.tracks:
                facing = 1 if self.tracks[fv].x_at(start) > x0 else -1
        if aname == "turn":
            facing = -tr.last_facing()
        params = dict(e)
        if walk_mood:
            params["_mood"] = walk_mood
        if jump_k is not None:
            params["height"] = jump_k[0]
        if human and spec.moving:
            mom = realworld.start_stop(tr.cdef, aname, speed, self.exaggeration, self.real)
            if mom is not None:
                params["_mom"] = mom
        cr = params.get("_cr")
        if cr is not None:
            ok_cr = (abs(cr[1][0] - x0) < 2 and abs(cr[2][0] - x1) < 2 and z1 is not None and
                     abs(cr[2][1] - z1) < 2 and abs(cr[1][1] - z_now) < 2)
            straight = abs(cr[0][0] - cr[1][0]) < 1 and abs(cr[0][1] - cr[1][1]) < 1 and \
                abs(cr[3][0] - cr[2][0]) < 1 and abs(cr[3][1] - cr[2][1]) < 1
            if not ok_cr or straight:
                params.pop("_cr", None)
        if aname == "wake":
            i_ = tr.seg_index(start - 1e-6)
            if i_ >= 0 and tr.segments[i_].action in ("sleep", "lie", "fall"):
                params["_from_lying"] = True
        if moving and not spec.moving:
            spec = ActionSpec(spec.fn, spec.dur, moving=True, blend_in=spec.blend_in, oneshot=True)
        seg = Segment(aname, spec, start, dur, x0, x1, facing, params, emotion,
                      z0=z_now if z1 is not None else None, z1=z1, view=view)
        tr.segments.append(seg)
        tr.segments.sort(key=lambda s: s.start)
        who = tr.cdef.id

        # automatic footsteps
        if spec.moving and (abs(x1 - x0) > 1 or z1 is not None) and aname in ("walk", "run", "hop"):
            kind = self._step_kind(tr, aname)
            if kind:
                if tr.cdef.kind == "quadruped":
                    sp = tr.cdef.animal
                    stride = (sp["thigh"] + sp["shin"]) * (2.2 if aname == "walk" else 3.6) * tr.cdef.scale
                    per = 4 if aname == "walk" else 2
                else:
                    stride = mood_stride(params.get("_mood"), aname)
                    per = 2
                dist = max(1.0, math.hypot(x1 - x0, ((z1 - z_now) * ZK) if z1 is not None else 0.0))
                k = 0
                while True:
                    d = (0.25 + k / per) * stride
                    if d > dist:
                        break
                    self.footsteps.append((start + dur * d / dist, who, kind))
                    k += 1
            if aname == "run":
                self._impact(start + 0.05, who, size=0.8)
        # automatic action sounds / icons / effects
        auto = {"jump": [(0.2, "jump"), (0.8, "land")], "pounce": [(0.2, "whoosh"), (0.8, "land")],
                "fall": [(0.3, "thud")], "kick": [(0.5, "whoosh")], "surprised": [(0.0, "pop")],
                "drink": [(0.35, "gulp")], "eat": [(0.4, "crunch")]}.get(aname, [])
        if aname == "fight" and tr.cdef.kind == "human":
            auto = [((k * 0.55 + 0.2) / dur, "whoosh") for k in range(int(dur / 0.55))]
        if aname == "clap" and tr.cdef.kind == "human":
            auto = [((k + 0.5) / 3.0 / dur, "clap") for k in range(int(dur * 3.0))]
        if aname == "roar" and tr.cdef.kind != "human":
            snd = tr.cdef.animal.get("sound")
            if snd:
                auto = [(0.12, snd)]
        if aname == "sing" and tr.cdef.kind == "bird":
            auto = [(0.05, tr.cdef.animal.get("sound", "chirp")), (0.5, tr.cdef.animal.get("sound", "chirp"))]
        if aname == "fly":
            auto = [(0.0, "flap")]
        for frac, name in auto:
            self.sfx.append((start + dur * frac, name, 0.8, who))
        if aname in ("jump", "pounce", "fall"):
            self._impact(start + dur * (0.8 if aname != "fall" else 0.35), who, size=1.2 if aname == "fall" else 1.0)
        if aname == "celebrate":
            self.effects.append(dict(start=start, kind="confetti", who=who, dur=min(dur, 2.5)))
        if aname in AUTO_ICON and not e.get("icon") and e.get("auto_icon", True):
            tr.icons.append((start + 0.05, AUTO_ICON[aname]))
        if emotion == "happy" and aname == "hug":
            tr.icons.append((start, "heart"))

        prop = e.get("prop") or e.get("object")
        if prop and aname in ("pick", "drop", "give"):
            if prop not in self.props:
                self.props[prop] = PropTrack({"id": prop, "type": e.get("prop_type", prop), "x": x0 + facing * 40})
            frac = 0.5 if aname != "give" else 0.55
            t_ev = start + dur * frac
            if aname == "pick":
                self.props[prop].add(t_ev, ("held", who))
            elif aname == "drop":                          # it falls from the hand (gravity / a leaf floats)
                xd = x0 + facing * 45 * tr.cdef.scale
                self._fall(self.props[prop], xd, float(e.get("height", 120.0 * tr.cdef.scale)), t_ev,
                           z=tr.z_at(t_ev))
            else:
                target = e.get("to") or e.get("target")
                if target in self.tracks:
                    self.props[prop].add(t_ev, ("held", target))
        return start + dur

    def _step_kind(self, tr, aname):
        if tr.cdef.kind == "bird":
            return None
        if tr.cdef.kind == "quadruped":
            return tr.cdef.animal.get("step")
        return "walk" if aname == "walk" else "run"

    # ------------------------------------------------------------------ vehicles
    def _vehicle(self, vid, near_x=0.0, vtype=None):
        if vid not in self.props:
            vt = vehicle_type(vtype or vid) or next(       # "ferry_boat" -> a boat, "school_bus" -> a bus
                (vehicle_type(w_) for w_ in reversed(re.split(r"[_\-\s\d]+", str(vid).lower())) if vehicle_type(w_)), "car")
            self.props[vid] = PropTrack({"id": vid, "type": vt, "x": near_x + 180})
            self.warn(f"scene {self.index + 1}: vehicle '{vid}' was not listed in 'vehicles' - added a {vt}")
        v = self.props[vid]
        if not v.vtype:
            self.warn(f"scene {self.index + 1}: '{vid}' is not a vehicle")
            return None
        return v

    def _board(self, tr, vid, start, instant=False):
        v = self.props[vid]
        seat = v.riders
        v.riders += 1
        kind = v.vtype
        if kind == "picture":                               # how a code vehicle is ridden
            kind = RIDE_KIND.get(vinfo(v).get("pose"), "picture")
        params = {"_vehicle": vid, "_seat": seat, "_vehicle_kind": kind}
        x = tr.x_at(start)
        if not instant and v.vtype in CLOSED_VEHICLES:
            params["_enter"] = (x, start)
            v.doors.append((start, seat, "in"))
        seg = Segment("ride", tr.actions.get("ride") or ACTIONS["ride"], start, 0.5, x, x, v.facing0, params)
        if params.get("_enter"):
            seg.spec = ActionSpec(seg.spec.fn, seg.spec.dur, persistent=True, blend_in=ENTER_DUR * 0.8)
            self.sfx.append((start + ENTER_DUR + 0.2, "door", 0.35, tr.cdef.id))
        if tr.cdef.kind != "human":
            seg.spec = tr.actions.get("sit") or tr.actions["idle"]
            seg.action = "ride"
        tr.segments.append(seg)
        tr.segments.sort(key=lambda s: s.start)
        return start + (ENTER_DUR + 0.1 if params.get("_enter") else 0.5)

    def _ride_action(self, tr, raw, e, start):
        target = e.get("on") or e.get("animal") or e.get("vehicle") or e.get("in")
        if target in self.tracks and self.tracks[target].cdef.kind == "quadruped":
            return self._mount(tr, target, e, start)
        vid = e.get("vehicle") or e.get("in") or e.get("on")
        if not vid:
            vs = [p for p in self.props.values() if p.vtype]
            if not vs:
                self.warn(f"scene {self.index + 1}: '{tr.cdef.id}' wants to {raw} but there is no vehicle")
                return start
            me = tr.x_at(start)
            vid = min(vs, key=lambda p: abs(p.pos(start)[0] - me)).id
        v = self._vehicle(vid, tr.x_at(start), e.get("vehicle_type"))
        if v is None:
            return start
        t = start
        if tr.riding_at(t) is None or tr.riding_at(t).params.get("_vehicle") != vid:
            vx = v.pos(t)[0]
            me = tr.x_at(t)
            if v.vtype in CLOSED_VEHICLES:              # walk up to the door of the next free seat
                door = seat_x(v, v.riders, t) + v.facing0 * 25 * v.scale
                dz = max(0.0, v.z_at(t) - 40)
                if abs(door - me) > 20 or abs(tr.z_at(t) - dz) > 20:
                    t = self._add_action(tr, "walk", {"to": {"x": door, "z": dz}}, t, None)
            elif abs(vx - me) > 80:                     # walk to the vehicle first
                aname = "walk"
                t = self._add_action(tr, aname, {"to": vx - 60 * (1 if vx > me else -1)}, t, None)
            self.sfx.append((t, "door" if v.vtype in ("car", "auto", "jeep") else ("ding" if v.vtype in ("bike", "bus") else "pop"),
                             0.5, tr.cdef.id))
            t = self._board(tr, vid, t)
        if raw == "drive" or "to" in e or "by" in e:
            t = self._vehicle_move(vid, e, t)
        return t

    def _vehicle_move(self, vid, e, start):
        v = self._vehicle(vid, 0.0, e.get("vehicle_type"))
        if v is None:
            return start
        x0, y0, _ = v.pos(start)
        to = e.get("to", e.get("move"))
        z0 = v.z_at(start)
        z1 = None
        if isinstance(to, dict):
            x1 = self._resolve_x(to["x"], None, start, x0) if "x" in to else x0
            y1 = float(to.get("y", y0))
            if "z" in to or "depth" in to:
                z1 = parse_z(to.get("z", to.get("depth")), z0)
        elif isinstance(to, str) and to.lower() in Z_NAMES and to not in self.tracks:
            x1, y1, z1 = x0, y0, float(Z_NAMES[to.lower()])
        elif isinstance(to, (list, tuple)):
            x1 = float(to[0])
            y1 = float(to[1]) if len(to) > 1 else y0
        elif to is not None:
            x1 = self._resolve_x(to, None, start, x0)
            y1 = float(e.get("y", y0))
        elif "by" in e:
            x1, y1 = x0 + float(e["by"]), float(e.get("y", y0))
        else:
            x1, y1 = x0, float(e.get("y", y0))
        if "z" in e and z1 is None:
            z1 = parse_z(e["z"], z0)
        reverse = bool(e.get("reverse") or e.get("backward") or e.get("backwards"))
        pts = None
        if self._drives_on_land(v, e, y0, y1):          # real-world driving: a car is not a ghost or a boat
            self._backup = None
            x1, z1, pts = self._drive_route(v, x0, z0, x1, z1, start, reverse)
            bk = self._backup
            self._backup = None
            if bk is not None:                          # a 3-point turn: back up steering, then drive on
                mid, spot = bk
                t_b = self._back_up(v, vid, (x0, z0), mid, spot, start)
                self._no_backup = True
                try:
                    return self._vehicle_move(vid, e, t_b + 0.25)
                finally:
                    self._no_backup = False
        dz = (z1 - z0) * ZK * 2.5 if z1 is not None else 0.0
        dist = math.hypot(math.hypot(x1 - x0, y1 - y0), dz)
        route = Route(pts, 1.0, reverse) if pts else None
        if route is not None:
            dist = max(dist, route.length)
        speed = float(e.get("speed", vinfo(v)["speed"])) * (0.5 if reverse else 1.0)   # backing up: slowly
        dur = float(e.get("duration", max(1.0, dist / speed)))
        if self._drives_on_land(v, e, y0, y1) and not e.get("at_once"):
            self._stop_short = None
            wait = self._give_way(v, vid, x0, z0, x1, z1 if z1 is not None else z0, route, start, dur)
            if wait > 0:                                 # someone is in the way: wait (brake), then go
                start += wait
            us = self._stop_short
            self._stop_short = None
            if us is not None and us < 0.97:             # it stays in the way: stop behind it
                if route is not None:
                    d_stop = route._d(us)
                    keep = [p_ for p_, c_ in zip(route.pts, route.cum) if c_ < d_stop]
                    end_p = route.point_at(d_stop)
                    route = Route(keep + [end_p], 1.0, reverse) if len(keep) >= 1 else None
                    x1, z1 = end_p
                else:
                    e_ = ease(us, "inout")
                    x1 = x0 + (x1 - x0) * e_
                    if z1 is not None:
                        z1 = z0 + (z1 - z0) * e_
                if route is not None and len(route.pts) < 2:
                    route = None
                dz = (z1 - z0) * ZK * 2.5 if z1 is not None else 0.0
                dist = max(math.hypot(x1 - x0, dz), route.length if route is not None else 0.0)
                dur = float(e.get("duration", max(1.0, dist / speed)))
                self.warn(f"fixed: scene {self.index + 1}: {vid} stops at x {x1:.0f} - something stays in its way")
        v.add(start, ("move", x0, y0, x1, y1, dur, 0.0) + (("reverse",) if reverse and route is None else ()))
        if route is not None:
            route.dur = dur
            v.routes[start] = route
        if z1 is not None and abs(z1 - z0) > 1:
            view = ("front" if z1 < z0 else "back") if abs(dz) > abs(x1 - x0) * 1.2 else None
            if view and reverse:
                view = {"front": "back", "back": "front"}[view]
            v.zmoves.append((start, dur, z0, z1, view))
            v.zmoves.sort(key=lambda m: m[0])
            self.mode_depth_used = True
        elif route is not None:
            v.zmoves.append((start, dur, z0, z0, None))
            v.zmoves.sort(key=lambda m: m[0])
        v.add(start + dur, ("rest", x1, y1))
        snd = vinfo(v)["sound"]
        if snd:
            self.loops.append((start, start + dur, snd, 0.55, vid))
        if v.vtype == "rocket":
            self.effects.append(dict(start=start, kind="smoke", x=x0, y=y0, dur=dur + 1.0, follow=vid))
            self.camera.append((start, {"type": "shake", "intensity": 0.8, "duration": min(dur, 2.5)}))
        if v.vtype == "bike":
            self.sfx.append((start, "ding", 0.4, None))
        return start + dur

    def _give_way(self, v, vid, x0, z0, x1, z1, route, start, dur):
        """Seconds to wait before driving off so it never runs into a vehicle that is already driving there, or
        into someone walking across (a driver gives way). 0 = go now."""
        half = VEHICLE_HALF.get(v.vtype, 200) * v.scale
        k_ = ZK * 2.5

        def me(u):
            if route is not None:
                x, z, _f = route.at(u)
                hx, hz = route.tangent(u) or (x1 - x0, z1 - z0)
            else:
                e_ = ease(u, "inout")
                x, z = x0 + (x1 - x0) * e_, z0 + (z1 - z0) * e_
                hx, hz = x1 - x0, z1 - z0
            a = math.atan2(hz * k_, hx)
            return x, z, abs(math.cos(a)) * half * 0.85 + abs(math.sin(a)) * 110.0

        others = [(oid, o) for oid, o in self.props.items() if o.vtype and oid != vid and o.vtype not in WATER_VEHICLES
                  and float(o.spec.get("y") or 0) < 40]
        people = [tr for tr in self.tracks.values() if not tr.crowd and any(
            sg.spec.moving and sg.end > start and sg.start < start + dur + 8 for sg in tr.segments)]
        if not others and not people:
            return 0.0

        def clash(delay, upto=1.0):
            n = max(4, int(dur / 0.15))
            steps = [(i / n, start + delay + i / n * dur, False) for i in range(n + 1) if i / n <= upto]
            t_end = start + delay + upto * dur
            steps += [(upto, t_end + k * 0.25, True) for k in range(1, 33)]   # then parked: not in a car's way
            for u, t, parked in steps:
                x, z, ext = me(u)
                for oid, o in others:
                    ox, _oy, _of = o.pos(t)
                    oz = o.z_at(t)
                    hx, hz = o.heading_at(t)
                    a = math.atan2(hz * k_, hx)
                    oh = VEHICLE_HALF.get(o.vtype, 200) * o.scale if o.vtype in VEHICLE_HALF else 150.0
                    oext = abs(math.cos(a)) * oh * 0.85 + abs(math.sin(a)) * 110.0
                    if abs(ox - x) < ext + oext and abs(oz - z) < 80:
                        return True
                for tr in ([] if parked else people):
                    if tr.riding_at(t) is not None or not self._visible(tr.cdef.id, t):
                        continue
                    if abs(tr.x_at(t) - x) < ext + 40 and abs(tr.z_at(t) - z) < 55:
                        return True
            return False
        if not clash(0.0):
            return 0.0
        for k in range(1, 25):                            # up to 12 s: wait until the way is clear
            if not clash(k * 0.5):
                self.warn(f"fixed: scene {self.index + 1}: {vid} waits {k * 0.5:.1f}s - something is in its way "
                          f"(it gives way instead of crashing)")
                return k * 0.5
        # it never clears (something parks in the way): drive up to it and stop
        lo, hi = 0.0, 1.0
        for _ in range(12):
            mid = (lo + hi) / 2.0
            if clash(0.0, mid):
                hi = mid
            else:
                lo = mid
        self._stop_short = max(0.0, lo - 0.04)
        return 0.0

    def _brake(self, v, t):
        """Stop a driving vehicle at time t: it slows to a halt in about a car length, where it is then."""
        for i, (tt, s_) in enumerate(v.states):
            if s_[0] == "move" and tt <= t < tt + s_[5]:
                u_stop = clamp((t - tt) / s_[5] + 0.08, 0.0, 1.0)
                rt = v.routes.get(tt)
                if rt is not None:
                    d_ = rt._d(u_stop)
                    keep = [p_ for p_, c_ in zip(rt.pts, rt.cum) if c_ < d_]
                    end = rt.point_at(d_)
                    new_dur = max(0.4, (t - tt) + 0.9)
                    nr = Route(keep + [end], new_dur, rt.reverse)
                    v.routes[tt] = nr
                    x1, z1 = end
                else:
                    e_ = ease(u_stop, "inout")
                    x1 = s_[1] + (s_[3] - s_[1]) * e_
                    z1 = None
                    new_dur = max(0.4, (t - tt) + 0.9)
                ns = list(s_)
                ns[3], ns[5] = x1, new_dur
                v.states[i] = (tt, tuple(ns))
                for j, (tt2, s2) in enumerate(v.states):     # parked where it stopped
                    if tt2 > tt and s2[0] == "rest":
                        v.states[j] = (tt + new_dur, ("rest", x1, s2[2]))
                        break
                v.states.sort(key=lambda q: q[0])
                for j, m in enumerate(v.zmoves):
                    if abs(m[0] - tt) < 1e-6:
                        z_end = z1 if z1 is not None else m[2] + (m[3] - m[2]) * ease(u_stop, "inout")
                        v.zmoves[j] = (m[0], new_dur, m[2], z_end, m[4])
                self.loops = [(a, (min(b, tt + new_dur) if w == v.id else b), n_, vol, w) for a, b, n_, vol, w in self.loops]
                self.warn(f"fixed: scene {self.index + 1}: {v.id} brakes and stops at {t:.1f}s")
                return

    def _park_clear(self):
        """A car / bus / jeep the story parks INSIDE a hut, a field or a haystack: moved to the nearest free spot
        beside it (like people put inside things)."""
        from .vehicles import BOATS
        for vid, v in self.props.items():
            if not v.vtype or v.vtype in BOATS or v.vtype in WATER_VEHICLES or v.vtype == "rocket":
                continue
            st, _ = v.at(0.0)
            if st[0] != "rest" or float(v.spec.get("y") or 0) > 40:
                continue
            x, z = float(st[1]), float(v.z0)
            if z > 1000:
                continue
            half = VEHICLE_HALF.get(v.vtype, 200) * v.scale
            self._plan_exclude = vid
            try:
                solid = [o for o in self._obstacles(None, 0.0, people=False)]
            except Exception:
                solid = []
            finally:
                self._plan_exclude = None

            def hit(px, pz):
                return [n_ for n_, (ox, oz, hw, hd, oy) in enumerate(solid)
                        if abs(px - ox) < hw + half * 0.82 and abs(pz - oz) < hd + 20]
            bad = hit(x, z)
            if not bad:
                continue
            best = None
            for dz in (0, -60, 60, -120, 120, -200, 200, -300, 300):
                for dx in range(0, 901, 50):
                    for sx in ((0,) if dx == 0 else (-1, 1)):
                        px, pz = x + sx * dx, z + dz
                        if pz < 0 or pz > 1000 or self._is_water(px, pz) or hit(px, pz):
                            continue
                        cost = dx + abs(dz) * 1.6
                        if best is None or cost < best[0]:
                            best = (cost, px, pz)
                if best is not None and best[0] < 150:
                    break
            if best is None:
                continue
            _c, px, pz = best
            v.states[0] = (0.0, ("rest", px, st[2]))
            v.z0 = pz
            v.spec = dict(v.spec, x=px, z=pz)
            self.warn(f"fixed: scene {self.index + 1}: {vid} was parked inside something solid - moved to x {px:.0f}, "
                      f"z {pz:.0f}")

    def _back_up(self, v, vid, p0, mid, spot, start):
        """Back up along a curve (nose still the old way, swinging round) - the first move of a 3-point turn."""
        y0 = v.pos(start)[1]
        route = Route([p0, mid, spot], 1.0, True)
        speed = vinfo(v)["speed"] * 0.45
        dur = max(1.0, route.length / speed)
        route.dur = dur
        v.add(start, ("move", p0[0], y0, spot[0], y0, dur, 0.0))
        v.routes[start] = route
        v.zmoves.append((start, dur, p0[1], spot[1], None))
        v.zmoves.sort(key=lambda m: m[0])
        v.add(start + dur, ("rest", spot[0], y0))
        snd = vinfo(v)["sound"]
        if snd:
            self.loops.append((start, start + dur, snd, 0.45, vid))
        self.warn(f"fixed: scene {self.index + 1}: {vid} has no room to turn round - it backs up and turns "
                  f"(a 3-point turn)")
        return start + dur

    def _drives_on_land(self, v, e, y0, y1):
        from .vehicles import BOATS
        return not (v.vtype in BOATS or v.vtype in WATER_VEHICLES or v.vtype == "rocket" or e.get("fly") or
                    e.get("through") or abs(y1 - y0) > 40)

    def _drive_route(self, v, x0, z0, x1, z1, t, reverse=False):
        """Real-world driving (cars, jeeps, buses, autos, bikes, carts):
        - never into a river / lake / sea - stops at the water's edge
        - round trees, houses, walls, parked cars and people standing in the road (with room for its size)
        - turning back the other way = a real U-turn swinging out into the road, not a flip on the spot
          ("reverse": true backs up instead, nose still pointing the old way)
        Returns (x1, z1, route points or None for the plain straight drive)."""
        zt = z1 if z1 is not None else z0
        half = VEHICLE_HALF.get(v.vtype, 200) * v.scale
        if self._zones() or (self.bg is not None and getattr(self.bg, "water", None)):
            if not self._is_water(x0, z0):
                last = (x0, zt)
                for k in range(1, 61):
                    xs, zs = x0 + (x1 - x0) * k / 60.0, z0 + (zt - z0) * k / 60.0
                    if self._is_water(xs + (half if x1 >= x0 else -half), zs):   # the front bumper
                        d = 1 if x1 >= x0 else -1
                        x1, zt = last[0] - d * 30.0, last[1]
                        self.warn(f"fixed: scene {self.index + 1}: {v.id} stops at the water's edge (a {v.vtype} "
                                  f"cannot drive into water - use a boat)")
                        break
                    last = (xs, zs)
        best = None
        k_ = ZK * 2.5                                    # depth counts this much more on the ground
        hx, hz = v.heading_at(t)
        hl = math.hypot(hx, hz * k_)
        ux, uz = (hx / hl, hz * k_ / hl) if hl > 1e-9 else (float(v.pos(t)[2]), 0.0)   # nose (ground units)
        gx, gz = x1 - x0, (zt - z0) * k_
        gl = math.hypot(gx, gz)
        cosang = (ux * gx + uz * gz) / gl if gl > 1e-9 else 1.0
        self._plan_exclude = v.id                        # solid things in its way (not the car itself)
        try:
            solid = self._obstacles(None, t, people=True)
        except Exception:
            solid = []
        finally:
            self._plan_exclude = None

        # things the car already stands next to (parked beside a field / a wall): only their own footprint counts,
        # so it can drive away from them
        near = {n_ for n_, (ox, oz, hw, hd, oy) in enumerate(solid)
                if abs(x0 - ox) < hw + half * 0.62 and oz - hd - 40 < z0 < oz + hd + 40}

        def free(px, pz, along_x=True):
            mx = half * 0.62 if along_x else half * 0.45         # the car's length along its way, width across
            return pz >= 0 and not self._is_water(px, pz) and not any(
                abs(px - ox) < hw + (0.0 if n_ in near else mx) and
                oz - hd - (0.0 if n_ in near else 40) < pz < oz + hd + (0.0 if n_ in near else 40)
                for n_, (ox, oz, hw, hd, oy) in enumerate(solid))

        def free_line(pts_):
            for a, b in zip(pts_, pts_[1:]):
                L_ = math.hypot(b[0] - a[0], (b[1] - a[1]) * k_)
                ax_ = abs(b[0] - a[0]) >= abs(b[1] - a[1]) * k_
                n_ = max(2, int(L_ / 25.0))
                for j in range(1, n_ + 1):
                    if not free(a[0] + (b[0] - a[0]) * j / n_, a[1] + (b[1] - a[1]) * j / n_, ax_):
                        return False
            return True
        if not reverse and getattr(self, "follow_roads", True) and not getattr(self, "_no_road", False):
            rr = self._road_route(v, x0, z0, x1, zt, free_line)
            if rr is not None:                           # on the road / path, in its lane
                pts, rname = rr
                j_ = 1
                while j_ < len(pts) - 1 and math.hypot(pts[j_][0] - x0, (pts[j_][1] - z0) * k_) < 60:
                    j_ += 1
                fx_, fz_ = pts[j_][0] - x0, (pts[j_][1] - z0) * k_
                fl_ = math.hypot(fx_, fz_)
                if fl_ < 1e-6 or (ux * fx_ + uz * fz_) / fl_ >= -0.2:   # (the road starts behind it: turn first)
                    self.warn(f"road: scene {self.index + 1}: {v.id} drives along the {rname}")
                    pts = self._ease_out(pts, ux, uz, half, free_line)
                    return pts[-1][0], pts[-1][1], pts
        way0 = None
        cos1 = cosang
        if not reverse and gl > 2 * half:                # where the planned way first heads (round things)
            way0 = self._plan_vehicle(v, x0, z0, x1, zt, t)
            if way0:
                f0 = next((w for w in way0 if math.hypot(w[0] - x0, (w[1] - z0) * k_) > 60), way0[-1])
                w0x, w0z = f0[0] - x0, (f0[1] - z0) * k_
                w0l = math.hypot(w0x, w0z)
                if w0l > 1e-6:
                    cos1 = min(cosang, (ux * w0x + uz * w0z) / w0l)
        if not reverse and cos1 < -0.34 and gl > 2 * half:
            # U-turn: forward, swing round in a half circle into the next lane, come back the other way.
            # Try both sides; keep the shorter one that is clear (no water, nothing solid).
            R, D0 = half * 0.9, max(400.0, half * 2.0)
            for sgn, D in ((1, D0), (-1, D0), (1, D0 * 0.6), (-1, D0 * 0.6), (1, D0 * 0.42), (-1, D0 * 0.42)):
                if best is not None and D < D0:
                    break                                         # (a tighter turn only when there is no room)
                nx, nz = -uz * sgn, ux * sgn                     # sideways (ground units)
                arc = []
                for a_, b_ in ((0.7, 0.1), (1.0, 0.5), (0.7, 0.9), (0.1, 1.0)):
                    gx_, gz_ = ux * R * a_ + nx * D * b_, uz * R * a_ + nz * D * b_
                    arc.append((x0 + gx_, z0 + gz_ / k_))
                if not free_line([(x0, z0)] + arc):
                    continue
                arc = [(round(a), round(b)) for a, b in arc]
                way_ = self._plan_vehicle(v, arc[-1][0], arc[-1][1], x1, zt, t) or [(x1, zt)]
                cand = [(x0, z0)] + arc + list(way_)
                if not free_line(cand[len(arc):]):
                    continue
                L = sum(math.hypot(b[0] - a[0], (b[1] - a[1]) * k_) for a, b in zip(cand, cand[1:]))
                if best is None or L < best[0]:
                    best = (L, cand)
            if best is None and not getattr(self, "_no_backup", False):
                # no room to swing round: back up first, steering, like a driver in a tight spot (a 3-point turn)
                for sgn in (1, -1):
                    nx, nz = -uz * sgn, ux * sgn
                    for kb in (1.0, 0.7):
                        bxm, bzm = -ux * R * 1.3 * kb + nx * D0 * 0.4 * kb, -uz * R * 1.3 * kb + nz * D0 * 0.4 * kb
                        mid = (x0 - ux * R * 0.55 * kb, z0 - uz * R * 0.55 * kb / k_)
                        bk = (round(x0 + bxm), round(z0 + bzm / k_))
                        if free_line([(x0, z0), mid, bk]):
                            self._backup = (mid, bk)
                            return x1, z1, None
            if best is None:
                self.warn(f"scene {self.index + 1}: {v.id} has no room to turn round - it turns on the spot "
                          f"(give it more room, or \"reverse\": true to back up)")
        if best is not None:
            pts = best[1]
            return pts[-1][0], pts[-1][1], pts
        lead = []
        if not reverse and v.vtype in VEHICLE_HALF and cosang < 0.9 and gl > half * 1.5:
            # more than ~25 degrees off: pull out along where the nose points first - a car turns in a curve,
            # it never spins on the spot
            L = min(half * 0.9, gl * 0.35)
            p = (x0 + ux * L, z0 + uz * L / k_)
            if p[1] >= 0 and not self._is_water(*p):
                lead = [(round(p[0]), round(p[1]))]
        start_x, start_z = (lead[0] if lead else (x0, z0))
        way = self._plan_vehicle(v, start_x, start_z, x1, zt, t)
        if lead and not way:                             # no way on from the pull-out spot: plan from where it is
            lead = []
            way = self._plan_vehicle(v, x0, z0, x1, zt, t)
        if lead and way and not free_line([(x0, z0)] + lead + list(way)[:1]):
            lead = []                                    # the pull-out runs into something: plan from where it is
            way = self._plan_vehicle(v, x0, z0, x1, zt, t)
        if lead and way:                                 # the way on from there must not double back (a hairpin)
            fx_ = next((w for w in way if math.hypot(w[0] - start_x, (w[1] - start_z) * k_) > 60), way[-1])
            wx_, wz_ = fx_[0] - start_x, (fx_[1] - start_z) * k_
            wl_ = math.hypot(wx_, wz_)
            if wl_ > 1e-6 and (ux * wx_ + uz * wz_) / wl_ < -0.2:
                lead = []
                way = self._plan_vehicle(v, x0, z0, x1, zt, t)
        straight = not way                               # (None from the planner = the straight way is free)
        if not way:
            way = [(x1, zt)]
        pts = [(x0, z0)] + lead + list(way)
        if not reverse:                                  # leave in a curve that starts along the nose: no skid
            pts = self._ease_out(pts, ux, uz, half, free_line)
        if len(pts) == 2 and not lead:
            if straight:
                return x1, z1, None                      # the plain straight drive
            return pts[1][0], pts[1][1], None            # blocked: only as far as it can go
        return pts[-1][0], pts[-1][1], pts

    @staticmethod
    def _ease_out(pts, ux, uz, half, free_line):
        """Replace the start of a drive with a curve that leaves along the nose (ux, uz in ground units) and
        joins the way a turning-circle further on - a car turns, it never spins on the spot."""
        k_ = ZK * 2.5
        if len(pts) < 2:
            return pts
        a_ = pts[0]
        # the first direction of the way
        j = 1
        while j < len(pts) - 1 and math.hypot(pts[j][0] - a_[0], (pts[j][1] - a_[1]) * k_) < 60:
            j += 1
        lx, lz = pts[j][0] - a_[0], (pts[j][1] - a_[1]) * k_
        ll = math.hypot(lx, lz)
        if ll < 1e-6:
            return pts
        cosang = (ux * lx + uz * lz) / ll
        if cosang >= 0.98 or cosang < -0.2:
            return pts
        ang = math.acos(clamp(cosang, -1.0, 1.0))
        reach = max(90.0, half * 1.5 * ang / (math.pi / 2))    # a sharper turn needs more road
        cum, i, e_ = 0.0, 1, None                          # the point that far along the way
        while i < len(pts):
            seg = math.hypot(pts[i][0] - pts[i - 1][0], (pts[i][1] - pts[i - 1][1]) * k_)
            if cum + seg >= reach:
                f = (reach - cum) / max(seg, 1e-6)
                e_ = (pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f)
                break
            cum += seg
            i += 1
        if e_ is None:
            i, e_ = len(pts) - 1, (a_[0] + (pts[-1][0] - a_[0]) * 0.7, a_[1] + (pts[-1][1] - a_[1]) * 0.7)
        Lc = reach * 0.55
        c_ = (a_[0] + ux * Lc, a_[1] + uz * Lc / k_)
        curve = [((1 - q) ** 2 * a_[0] + 2 * q * (1 - q) * c_[0] + q * q * e_[0],
                  (1 - q) ** 2 * a_[1] + 2 * q * (1 - q) * c_[1] + q * q * e_[1]) for q in (kk / 12.0 for kk in range(1, 13))]
        new = [a_] + curve + pts[i:]
        if free_line([a_] + curve) or not free_line(pts[:i + 1]):
            return new
        return pts

    ROAD_WORDS = ("road", "path", "street", "sadak", "lane", "highway", "track", "rasta", "marg")

    def _roads(self):
        """Every road / path in the scene as a centre line [(x, z) ...] (story units) with its half width:
        a road or path thing of a 3D place (its walk surface), the winding path of a jungle / forest / village
        (into the distance), and a road band across the place. Cached."""
        got = getattr(self, "_road_cache", None)
        if got is not None:
            return got
        from .world3d import Z_of_z, p3
        out = []
        k_ = ZK * 2.5
        try:                                              # 1. road / path things with a walk surface
            for pid, polys, _bb in self._walk_list():
                o = self.props.get(pid)
                name = f"{pid} {getattr(o, 'type', '')}".lower()
                if not any(w in name for w in self.ROAD_WORDS) or len(polys) < 2:
                    continue
                cs = []
                for P, _a, _n in polys:
                    cx = sum(q[0] for q in P) / len(P)
                    cz = sum(q[2] for q in P) / len(P)
                    w_ = max(q[0] for q in P) - min(q[0] for q in P)
                    d_ = max(q[2] for q in P) - min(q[2] for q in P)
                    cs.append((cx, cz, w_, d_))
                along_z = (max(c[1] for c in cs) - min(c[1] for c in cs)) >= (max(c[0] for c in cs) - min(c[0] for c in cs))
                cs.sort(key=lambda c: c[1] if along_z else c[0])
                pts, halves = [], []
                for cx, cz, w_, d_ in cs:
                    x, z = self._story_of(cx, cz)
                    pts.append((x, z))
                    halves.append((w_ if along_z else d_) / 2.0 * (p3(z) if along_z else 1.0))
                halves.sort()
                out.append({"name": pid, "pts": pts, "half": halves[len(halves) // 2]})
        except Exception:
            pass
        bg = self.bg
        spec = getattr(bg, "spec", {}) or {}
        want = spec.get("path")
        has_path = bool(want) if want is not None else False
        if has_path and not getattr(bg, "worldmap", None) and not getattr(bg, "water", None) and not out:
            cx = self.world_w / 2.0                       # 2. the winding path into the distance (world3d.path_x)
            pts = []
            for k in range(0, 61):
                z = k * 50.0
                Z = Z_of_z(z)
                X = cx + 70 * math.sin(Z / 1500.0 + 0.4) - 25 * math.sin(Z / 4100.0)
                p = p3(z)
                pts.append((X * p + cx * (1.0 - p), z))
            out.append({"name": "path", "pts": pts, "half": 160.0})
        for e in getattr(bg, "elements", []) or []:       # 3. a road band across the place
            if isinstance(e, dict) and e.get("type") == "road_band":
                z0_, z1_ = float(e.get("z0", 0)), float(e.get("z1", 0))
                zc = (z0_ + z1_) / 2.0
                out.append({"name": f"{e.get('style', 'tar')} road", "pts": [(-600.0 + i * 200.0, zc) for i in
                                                                            range(int((self.world_w + 1200) / 200) + 1)],
                            "half": abs(z1_ - z0_) / 2.0 * k_})
        self._road_cache = out
        return out

    @staticmethod
    def _poly_proj(pts, x, z, k_):
        """(distance along, distance off, segment index) of point (x, z) on a polyline - ground units."""
        best, along = None, 0.0
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            ax, az, bx, bz = a[0], a[1] * k_, b[0], b[1] * k_
            L = math.hypot(bx - ax, bz - az)
            if L < 1e-6:
                continue
            u = clamp(((x - ax) * (bx - ax) + (z * k_ - az) * (bz - az)) / (L * L), 0.0, 1.0)
            px, pz = ax + (bx - ax) * u, az + (bz - az) * u
            d = math.hypot(x - px, z * k_ - pz)
            if best is None or d < best[1]:
                best = (along + u * L, d, i)
            along += L
        return best

    def _road_route(self, v, x0, z0, x1, z1, free_line):
        """Drive along a road / path when both ends are near it and it goes the right way: join it, keep to
        the left lane ("settings": {"drive_side": "right"} for the other side), leave it near the goal.
        -> (points, road name) or None."""
        k_ = ZK * 2.5
        gl = math.hypot(x1 - x0, (z1 - z0) * k_)
        if gl < 300:
            return None
        side = -1.0 if str(getattr(self, "drive_side", "left")).lower() == "right" else 1.0
        best = None
        for rd in self._roads():
            P = rd["pts"]
            if len(P) < 2:
                continue
            a = self._poly_proj(P, x0, z0, k_)
            b = self._poly_proj(P, x1, z1, k_)
            if a is None or b is None:
                continue
            join = max(700.0, rd["half"] * 3.0)
            along = abs(b[0] - a[0])
            if a[1] > join or b[1] > join or along < max(300.0, 0.45 * gl):
                continue
            if best is None or along > best[0]:
                best = (along, rd, a, b)
        if best is None:
            return None
        along, rd, a, b = best
        P = rd["pts"]
        # the road as a list of (distance along, x, z_ground)
        cum, line = [0.0], [(P[0][0], P[0][1] * k_)]
        for p_, q_ in zip(P, P[1:]):
            cum.append(cum[-1] + math.hypot(q_[0] - p_[0], (q_[1] - p_[1]) * k_))
            line.append((q_[0], q_[1] * k_))

        def at(s):
            s = clamp(s, 0.0, cum[-1])
            i = 1
            while i < len(cum) - 1 and cum[i] < s:
                i += 1
            L = max(1e-6, cum[i] - cum[i - 1])
            f = (s - cum[i - 1]) / L
            (ax, az), (bx, bz) = line[i - 1], line[i]
            return ax + (bx - ax) * f, az + (bz - az) * f, (bx - ax) / L, (bz - az) / L
        sgn = 1.0 if b[0] >= a[0] else -1.0
        half = rd["half"]
        lane = half * 0.45 * side if half > 260 else 0.0           # narrow path: the middle of it
        s0 = a[0] + sgn * (60.0 if a[1] < half else min(250.0, along * 0.15))
        s1 = b[0] - sgn * (60.0 if b[1] < half else min(250.0, along * 0.15))
        if (s1 - s0) * sgn < 150:
            return None
        n = max(2, int(abs(s1 - s0) / 120.0))
        pts = [(x0, z0)]
        for j in range(n + 1):
            x, zg, tx, tz = at(s0 + (s1 - s0) * j / n)
            tx, tz = tx * sgn, tz * sgn
            lx, lz = -tz, -tx                                  # left of the way it goes (camera side when going right)
            pts.append((x + lx * lane, max(0.0, (zg + lz * lane) / k_)))
        pts.append((x1, z1))
        clean = [pts[0]]
        for q in pts[1:]:
            if math.hypot(q[0] - clean[-1][0], (q[1] - clean[-1][1]) * k_) > 30:
                clean.append(q)
        if not free_line(clean):
            return None
        return clean, rd["name"]

    def _plan_vehicle(self, v, x0, z0, x1, z1, t):
        """The walking planner, sized for a vehicle: every solid thing gets the car's half length / width more room."""
        class _VT:                                        # a stand-in "walker" for the planner
            class cdef:
                id, species, kind, scale = v.id, None, "vehicle", v.scale

            def y_at(self, _t):
                return 0.0

            def riding_at(self, _t):
                return None

            mounted_at = riding_at
        self._plan_exclude = v.id
        self._plan_pad = (VEHICLE_HALF.get(v.vtype, 200) * v.scale * 0.85, 45.0)
        try:
            self._path_climbs = False
            return self._plan_path(_VT(), x0, z0, x1, z1, t, {})
        finally:
            self._plan_exclude = None
            self._plan_pad = None

    CARRIED_WORDS = ("carried", "be_carried", "held", "in_arms", "on_hip", "carried_on_hip", "in_lap")
    PICK_WORDS = ("pick_up", "pickup", "pick", "lift", "carry", "hold", "hold_baby", "carry_baby", "take")

    def _baby_carry(self, tr, raw, e, start):
        """👶 babies / toddlers carried: {"who": "munna", "do": "carried", "by": "maa", "on": "hip"} or
        {"who": "maa", "do": "pick_up", "target": "munna"} - the carrier holds them in the arms (or on the hip) and
        can walk with them ("to"); "do": "put_down" (the carrier) / anything else (the baby) ends it."""
        small = ("baby", "toddler")
        if raw in self.CARRIED_WORDS and tr.cdef.kind == "human":
            by = e.get("by") or (e.get("on") if e.get("on") in self.tracks else None) or e.get("with")
            if by in self.tracks and self.tracks[by].cdef.kind == "human" and by != tr.cdef.id:
                how = "hip" if (raw in ("on_hip", "carried_on_hip") or e.get("on") == "hip" or e.get("how") == "hip") else "arms"
                return self._carry(tr, by, e, start, how)
            return None
        if raw in self.PICK_WORDS and tr.cdef.kind == "human":
            tgt = e.get("target") or e.get("who2") or e.get("object") or e.get("child") or e.get("baby")
            if tgt in self.tracks and self.tracks[tgt].cdef.kind == "human" and tgt != tr.cdef.id and \
                    (self.tracks[tgt].cdef.age in small or raw in ("hold_baby", "carry_baby")):
                how = "hip" if (e.get("on") == "hip" or e.get("how") == "hip") else "arms"
                return self._carry(self.tracks[tgt], tr.cdef.id, e, start, how)
        if raw in ("put_down", "set_down", "put_baby_down") and tr.cdef.kind == "human":
            for o in self.tracks.values():
                m = o.mounted_at(start)
                if m is tr:
                    x_ = tr.x_at(start) + tr.facing_at(start) * 45 * tr.cdef.scale
                    seg = Segment("sit_up" if o.cdef.age == "baby" else "idle", o.actions.get("sit_up") or ACTIONS["sit_up"]
                                  if o.cdef.age == "baby" else o.actions["idle"], start, 0.8, x_, x_, tr.facing_at(start), {})
                    o.segments.append(seg)
                    o.segments.sort(key=lambda s_: s_.start)
                    return start + 0.8
        return None

    def _carry(self, baby, carrier_id, e, start, how="arms"):
        """the carrier walks to the baby (if far), picks it up; then the baby rides along (a 'mount' on a person)"""
        m = self.tracks[carrier_id]
        t = start
        bx, bz, mx = baby.x_at(t), baby.z_at(t), m.x_at(t)
        if abs(bx - mx) > 80 or abs(bz - m.z_at(t)) > 60:
            side = 1 if mx > bx else -1
            t = self._add_action(m, "walk", {"to": {"x": bx + side * 45, "z": bz}}, t, None)
        spec = baby.actions.get("carried") or ACTIONS["carried"]
        seg = Segment("mount", spec, t, 0.6, m.x_at(t), m.x_at(t), m.facing_at(t), {"_mount": carrier_id, "_carry": how})
        baby.segments.append(seg)
        baby.segments.sort(key=lambda s_: s_.start)
        t += 0.6
        if "to" in e or "by_x" in e:
            me = {k: v for k, v in e.items() if k in ("to", "speed", "duration")}
            t = self._add_action(m, "walk", me, t, None)
        return t

    def _mount(self, tr, mid, e, start):
        """Climb onto an animal (walks to it first), and optionally ride it somewhere ("to" / "do" of the animal)."""
        m = self.tracks[mid]
        t = start
        if tr.mounted_at(t) is None or tr.mounted_at(t).cdef.id != mid:
            mx, mz = m.x_at(t), m.z_at(t)
            me = tr.x_at(t)
            if abs(mx - me) > 90 or abs(mz - tr.z_at(t)) > 60:
                side = 1 if me > mx else -1
                t = self._add_action(tr, "walk", {"to": {"x": mx + side * 70, "z": mz}}, t, None)
            seg = Segment("mount", ACTIONS["mount"], t, 0.6, m.x_at(t), m.x_at(t), m.facing_at(t),
                          {"_mount": mid})
            tr.segments.append(seg)
            tr.segments.sort(key=lambda s: s.start)
            self.sfx.append((t, "whoosh", 0.35, tr.cdef.id))
            t += 0.6
        if "to" in e or "by" in e:                    # ride somewhere: the animal walks / runs, the rider comes along
            gait = str(e.get("gait", e.get("speed_mode", "walk"))).lower()
            gait = "run" if gait in ("run", "gallop", "fast", "trot") else "walk"
            me = {k: v for k, v in e.items() if k in ("to", "by", "speed", "duration")}
            t = self._add_action(m, gait, me, t, None)
        return t

    def _free_spot(self, tr, x, z, t, away=1):
        """Real-world rule: two people can't stand in the same spot. Step aside (outwards, then nearer the
        camera) until nobody else is there at time t."""
        for k in range(10):
            clash = False
            for ot in self.tracks.values():
                if ot is tr or ot.riding_at(t) is not None or ot.mounted_at(t) is not None:
                    continue
                try:
                    ox, oz = ot.x_at(t), ot.z_at(t)
                except Exception:
                    continue
                if abs(ox - x) < 80 and abs(oz - z) < 60:
                    clash = True
                    break
            if not clash:
                return x, z
            if k % 2 == 0:
                x += away * 115.0
            else:
                z = max(0.0, z - 70.0)
        return x, z

    def _get_out(self, tr, e, start):
        if tr.riding_at(start) is None and tr.mounted_at(start) is None and self._perched(tr, start):
            return self._get_down(tr, start)
        m = tr.mounted_at(start)
        if m is not None:                             # climb down beside the animal
            f = m.facing_at(start)
            x = m.x_at(start) - f * 60
            zd = max(0.0, m.z_at(start) - 70.0)          # steps down on the camera side, never hidden behind it
            x, zd = self._free_spot(tr, x, zd, start + 0.6, away=-f)
            seg = Segment("stand", tr.actions["stand"], start, 0.6, x, x, f, {}, z0=zd, z1=zd)
            tr.segments.append(seg)
            tr.segments.sort(key=lambda s: s.start)
            self.sfx.append((start, "jump", 0.3, tr.cdef.id))
            return start + 0.6
        ride = tr.riding_at(start)
        if ride is None:
            return start
        vid = ride.params["_vehicle"]
        seat = ride.params.get("_seat", 0)
        v = self.props.get(vid)
        vx, vy, vf = v.pos(start) if v else (tr.x_at(start), 0, 1)
        if v is None or v.vtype not in CLOSED_VEHICLES:
            x = tr.x_at(start) - vf * 20
            seg = Segment("stand", tr.actions["stand"], start, 0.6, x, x, vf, {})
            tr.segments.append(seg)
            tr.segments.sort(key=lambda s: s.start)
            if v:
                v.riders = max(0, v.riders - 1)
            return start + 0.6
        vz = v.z_at(start)
        wide = 1.4 if v.vtype == "bus" else 1.0
        if v.view_at(start):                              # seen from the front / back: out from behind its side
            side = -1 if seat % 2 == 0 else 1
            x = vx + side * 240 * v.scale * wide
            z = vz
            ex = (vid, seat, start, vx + side * 105 * v.scale * wide)
        else:                                             # side view: step out of the door toward the camera
            x = seat_x(v, seat, start) + vf * 25 * v.scale
            z = max(0.0, vz - 45)
            ex = (vid, seat, start, None)
        x, z = self._free_spot(tr, x, z, start + 0.3 + EXIT_DUR, away=(1 if x >= vx else -1))
        seg = Segment("stand", tr.actions["stand"], start, 0.25 + EXIT_DUR, x, x, vf, {"_exit": ex}, z0=z, z1=z)
        seg.spec = ActionSpec(seg.spec.fn, seg.spec.dur, persistent=True, blend_in=0.25 + EXIT_DUR * 0.8)
        tr.segments.append(seg)
        tr.segments.sort(key=lambda s: s.start)
        v.riders = max(0, v.riders - 1)
        v.doors.append((start, seat, "out"))
        self.sfx.append((start, "door", 0.45, tr.cdef.id))
        self.sfx.append((start + 0.55 + EXIT_DUR, "door", 0.35, tr.cdef.id))
        return start + 0.35 + EXIT_DUR


    # ------------------------------------------------------------------ interactive objects
    def _object_ref(self, e):
        from . import objects
        for k in ("object", "prop", "on", "behind", "target", "thing"):
            v = e.get(k)
            if isinstance(v, str) and v in self.props and objects.is_object(self.props[v]):
                return v
        return None

    def _zones(self):
        return getattr(self.bg, "water_zones", None) or [] if self.bg is not None else []

    def _is_water(self, x, z=None):
        zones = self._zones()
        if zones:                                   # water marked on your own background picture
            return any(x0 <= x <= x1 and (z is None or z0 - 120 <= z <= z1 + 120) for x0, x1, z0, z1 in zones)
        return bool(self.bg is not None and getattr(self.bg, "water", None) and self.bg.is_water(x))

    def _obstacles(self, tr, t, target=None, people=True):
        """Solid things on the stage at time t: [(x, z, half_width, half_depth)] - objects, parked vehicles,
        other people and animals (not the one we walk to, not riders)."""
        from . import objects
        obs = []
        for pid, o in self.props.items():
            if pid == target or pid == getattr(self, "_plan_exclude", None):
                continue
            if o.vtype:
                if o.vtype in ("paper_boat",):
                    continue
                tw = t
                if o.moving(t):
                    if getattr(self, "_plan_pad", None) is None:
                        continue                        # (people: it drives past)
                    ends = [tt for tt, s_ in o.states if s_[0] == "rest" and tt > t]
                    if not ends or ends[0] > t + 12.0:
                        continue
                    tw = ends[0] + 0.01                 # a vehicle planning its way: where that one will park
                ox = o.pos(tw)[0]
                w = 520.0 * o.scale * (1.6 if o.vtype == "bus" else 1.0)
                if o.vtype in VEHICLE_HALF:
                    w = 2.0 * VEHICLE_HALF[o.vtype] * o.scale * 1.05
                obs.append((ox, o.z_at(tw), w / 2, 110.0, 0.0))
            elif objects.is_object(o):
                st, _ = o.at(t)
                if st[0] != "rest":
                    continue
                if o.open_at(t) and any(k in f"{pid} {o.type}".lower() for k in ("gate", "door", "phatak", "darwaza")):
                    continue                            # an OPEN gate / door: people walk through it
                w = objects.size(o)[0]
                if w < 70 and not (getattr(self, "_plan_pad", None) and objects.size(o)[1] > 50):
                    continue                            # a stone, an apple: step over it (a car can't: a pump, a post)
                w = max(w, 40.0)
                if float(o.spec.get("y") or 0.0) > STEP_UP * 2:
                    continue                            # up in the air (a balcony railing): not in anyone's way below
                from . import images
                img = objects._image_name(o)
                meta = (images.info(img) or {}) if img else {}
                if meta.get("walk"):                    # steps, a jetty, a stage: people walk ON it
                    continue
                if float(meta.get("height") or objects.size(o)[1]) < STEP_UP * 0.6:
                    continue                            # a floor, a rug, a road, a line on the ground: step onto it
                hd = 90.0
                fp = meta.get("foot")
                if meta.get("is3d") and not fp:
                    continue                            # nothing of it near the ground (a ceiling, hanging lamps)
                oy_ = float(o.spec.get("y") or 0.0)
                if not fp:
                    obs.append((st[1], o.z_at(t), w / 2, hd, oy_))
                    continue
                # a 3D thing: its REAL ground footprint (world units -> story) - piece by piece when it has
                # several (a row of bushes, two pillars): people walk BETWEEN them, not through the whole row
                from .codedraw import z_from_depth
                from .world3d import Z_of_z, p3 as _p3
                from .scene3d import FOCAL
                h_draw = objects.size(o)[1]
                sc = h_draw / max(1.0, float(meta.get("height") or h_draw))
                zc = o.z_at(t)
                Zc = Z_of_z(zc) - FOCAL
                k_ = _p3(zc)
                for f_ in (meta.get("feet") or [fp]):
                    za = z_from_depth(Zc + f_[2] * sc)
                    zb = z_from_depth(Zc + f_[3] * sc)
                    hd_ = max(40.0, (zb - za) / 2.0)          # a tree blocks at its trunk, not its whole crown;
                    w_ = max(50.0, (f_[1] - f_[0]) * sc * k_)          # a hut at its walls, not its roof overhang
                    obs.append((st[1] + (f_[0] + f_[1]) / 2.0 * sc * k_, (za + zb) / 2.0, w_ / 2, hd_, oy_))
        for oid, ot in (self.tracks.items() if people else ()):
            if ot is tr or oid == target or ot.riding_at(t) is not None or ot.mounted_at(t) is not None:
                continue
            if not self._visible(oid, t):
                continue                                # inside a house / vanished: not in the way
            try:
                ox, oz = ot.x_at(t), ot.z_at(t)
                oy = ot.y_at(t)
            except Exception:
                continue
            if any(o2 is tr for o2 in [ot.mounted_at(t)] if o2 is not None):
                continue
            hw = 55.0 * ot.cdef.scale if ot.cdef.kind == "human" else 120.0 * ot.cdef.scale
            obs.append((ox, oz, hw, 55.0, oy))
        return obs

    def _plan_path(self, tr, x0, z0, x1, z1, t, e):
        """Real-world walking: find a way round solid things (A* on a grid over the stage floor, x and depth z),
        then keep only the corners. Returns waypoints ending at the destination, or None if the straight way is
        free."""
        import heapq
        if abs(x1 - x0) < 40 and abs(z1 - z0) < 40:
            return None
        tgt = e.get("to") if isinstance(e.get("to"), str) else None
        obs = self._obstacles(tr, t, tgt, people=not e.get("_no_people"))
        pad = getattr(self, "_plan_pad", None)
        if pad:                                          # a vehicle: room for its own size
            obs = [(ox, oz, hw + pad[0], hd + pad[1], oy) for ox, oz, hw, hd, oy in obs]
        water = bool(self._zones() or (self.bg is not None and getattr(self.bg, "water", None))) and not (
            e.get("swim") or tr.cdef.species in ("duck", "fish"))
        if water and (self._is_water(x1, z1) or self._is_water(x0, z0)):
            water = False                                # stepping into / out of a boat: the water is the point

        tight = set()                                   # obstacles next to the start / goal: only their solid core

        def blocked(x, z, y=0.0):
            for n_, (ox, oz, hw, hd, oy) in enumerate(obs):   # passing BEHIND someone needs more room than in front:
                if n_ in tight:
                    if abs(x - ox) < hw and oz - hd < z < oz + hd and abs(y - oy) < 150:
                        return True
                elif abs(x - ox) < hw + 18 and oz - hd < z < oz + 2.4 * hd and abs(y - oy) < 150:
                    return True                         # (only things at the same level: not the ones below a balcony)
            return bool(water and y < STEP_UP and self._is_water(x, z))

        levels = bool(self._walk_list() if (self.bg is not None or getattr(self, "props", None)) else []) or \
            bool(getattr(self.bg, "hills", None) if self.bg is not None else None)
        goal_y = e.get("_goal_y")

        from .world3d import Z_of_z, p3, X_of
        W2 = self.world_w / 2.0

        def gdist(ax, az, bx, bz):
            """Ground distance between two stage points for slope checks: far away one step of story depth is
            much more real ground than near the camera (never less than the old story measure)."""
            pa, pb = p3(az), p3(bz)
            dw = math.hypot(X_of(bx, pb, W2) - X_of(ax, pa, W2), Z_of_z(bz) - Z_of_z(az))
            return max(dw, math.hypot(bx - ax, (bz - az) * 1.5))

        def walk_line(a, b, ya):
            """Walk the straight line a -> b starting at height ya: (ok, height at the end). Not ok if something
            solid is in the way or a step is too high (a wall, a balcony edge - use the stairs)."""
            n = max(2, int(math.hypot(b[0] - a[0], (b[1] - a[1]) * 1.5) / 20))
            y = ya
            px_, pz_ = a
            for k in range(1, n + 1):
                x_, z_ = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
                seg = gdist(px_, pz_, x_, z_)
                px_, pz_ = x_, z_
                if levels:
                    y2, flat = self.ground_level(x_, z_, y)
                    if not step_ok(y, y2, seg, flat or relax[0]):
                        return False, y
                    y = y2
                if k < n and blocked(x_, z_, y):
                    return False, y
            return True, y

        relax = [False]                                 # True: a steep hillside may be scrambled up (no gentle way)
        self._path_blocked = None if levels else (lambda x_, z_: blocked(x_, z_))

        def clear(a, b, ya=0.0):
            return walk_line(a, b, ya)[0]

        def at_goal(y):
            return goal_y is None or abs(y - goal_y) <= STEP_UP

        y0 = tr.y_at(t) if levels else 0.0
        def core(px, pz, ob):
            return abs(px - ob[0]) < ob[2] and ob[1] - ob[3] < pz < ob[1] + ob[3]

        moved = False
        if goal_y is None and not e.get("_via") and (pad or (e.get("who") and isinstance(e.get("to"), dict))):
            # the story asks for a spot INSIDE a rock / a hut / a trunk (or too close for a car's body): stand
            # (or park) at the nearest open spot next to it instead of walking into it
            static = self._obstacles(tr, t, tgt, people=False)
            if pad:
                static = [(ox, oz, hw + pad[0], hd + pad[1], oy) for ox, oz, hw, hd, oy in static]
            stuck = [ob for ob in static if core(x1, z1, ob) and not core(x0, z0, ob)]
            if stuck:
                got = self._nearest_free(x1, z1, lambda px, pz: any(core(px, pz, ob) for ob in static))
                if got is not None:
                    who_ = tr.cdef.id
                    self.warn(f"fixed: scene {self.index + 1}: {who_}'s spot (x {x1:.0f}, z {z1:.0f}) is inside something "
                              f"solid - {'parks' if pad else 'stops'} next to it at x {got[0]:.0f}, z {got[1]:.0f}")
                    x1, z1 = float(got[0]), float(got[1])
                    moved = True

        def margin(px, pz, ob):
            return abs(px - ob[0]) < ob[2] + 18 and ob[1] - ob[3] < pz < ob[1] + 2.4 * ob[3]
        # walking up TO something (a bush, a person, a hut's door): that one thing is the goal, not a wall - but
        # everything ELSE on the way is still solid (before: the whole walk went straight through it all).
        # A start / goal just BESIDE or BEHIND something keeps it solid, with only its core blocking.
        if goal_y is None:
            obs[:] = [ob for ob in obs if not core(x1, z1, ob)]
        obs[:] = [ob for ob in obs if not core(x0, z0, ob)]      # starting inside something: leaving is allowed
        tight.update(n_ for n_, ob in enumerate(obs) if margin(x1, z1, ob) or margin(x0, z0, ob))
        ok, y_end = walk_line((x0, z0), (x1, z1), y0)
        if ok and at_goal(y_end):
            return [(round(x1), round(z1))] if moved else None
        SX, SZ = 40.0, 30.0
        xl, xh = min(x0, x1) - 500, max(x0, x1) + 500
        if e.get("_wide"):                               # 2nd try: the whole stage (round the END of a long fence)
            xl, xh = min(xl, -300.0), max(xh, self.world_w + 300.0)
        zl, zh = 0.0, min(3000.0, max(z0, z1) + 360.0)
        if levels and (goal_y is not None or abs(y0) > STEP_UP):    # the stairs may be anywhere on the stage
            xl, xh = min(xl, -100.0), max(xh, self.world_w + 100.0)
            zh = max(zh, min(3000.0, 1100.0))
        nx, nz = int((xh - xl) / SX) + 1, int((zh - zl) / SZ) + 1
        cell = lambda x, z: (int(round((x - xl) / SX)), int(round((z - zl) / SZ)))   # noqa: E731
        pos = lambda i, j: (xl + i * SX, zl + j * SZ)                                  # noqa: E731
        lvl = lambda y: int(round(y / 30.0)) if levels else 0                           # noqa: E731
        s0, g0 = cell(x0, z0), cell(x1, z1)
        n0 = (s0[0], s0[1], lvl(y0))
        # distance map (book ch. 17): once per plan, how far every floor cell is from the nearest solid thing.
        # Blocked cells are looked up instead of tested against every obstacle, and the way keeps a natural gap
        # from walls, trunks and parked cars instead of brushing past them.
        dmap = blk = None
        GAP = 55.0
        if not levels and nx * nz <= 40000 and getattr(self, "distance_maps", True):
            try:
                import numpy as _np
                from scipy.ndimage import distance_transform_edt as _edt
                GX = (xl + _np.arange(nx) * SX)[:, None]           # the same test as blocked(), all cells at once
                GZ = (zl + _np.arange(nz) * SZ)[None, :]
                blk = _np.zeros((nx, nz), dtype=bool)
                for n_, (ox, oz, hw, hd, oy) in enumerate(obs):
                    if abs(oy) >= 150:
                        continue
                    if n_ in tight:
                        blk |= (_np.abs(GX - ox) < hw) & (GZ > oz - hd) & (GZ < oz + hd)
                    else:
                        blk |= (_np.abs(GX - ox) < hw + 18) & (GZ > oz - hd) & (GZ < oz + 2.4 * hd)
                if water:
                    for i_ in range(nx):
                        for j_ in range(nz):
                            if not blk[i_, j_] and self._is_water(xl + i_ * SX, zl + j_ * SZ):
                                blk[i_, j_] = True
                if 0 <= g0[0] < nx and 0 <= g0[1] < nz:
                    blk[g0[0], g0[1]] = False
                dmap = _edt(~blk, sampling=(SX, SZ * 1.5)) if blk.any() else None
            except Exception:
                dmap = blk = None
        found = None
        for attempt in range(2):                        # 1st: only walkable slopes; 2nd (going up, no gentle way):
            if attempt == 1 and not (levels and goal_y is not None):     # scramble up the steep side instead of
                break                                                     # walking into the hill
            relax[0] = attempt == 1
            openq = [(0.0, n0)]
            came, cost, hgt = {n0: None}, {n0: 0.0}, {n0: y0}
            while openq and len(came) < (60000 if levels else (30000 if e.get("_wide") else 6000)):
                _, cur = heapq.heappop(openq)
                if (cur[0], cur[1]) == g0 and at_goal(hgt[cur]):
                    found = cur
                    break
                ci, cj, _l = cur
                yc = hgt[cur]
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    ni, nj = ci + di, cj + dj
                    if not (0 <= ni < nx and 0 <= nj < nz):
                        continue
                    px, pz = pos(ni, nj)
                    step = math.hypot(di * SX, dj * SZ * 1.5)
                    if levels:
                        step = gdist(px - di * SX, pz - dj * SZ, px, pz)
                    yn, flat = self.ground_level(px, pz, yc) if levels else (0.0, True)
                    if levels and not step_ok(yc, yn, step, flat or relax[0]):
                        continue                        # too high a step / too steep: a wall, an edge, a cliff
                    if (ni, nj) != g0 and (blk[ni, nj] if blk is not None else blocked(px, pz, yn)):
                        continue
                    nk = (ni, nj, lvl(yn))
                    nc = cost[cur] + step + (abs(yn - yc) * 0.5 if levels else 0.0)
                    if dmap is not None:                    # keep a natural gap from solid things
                        dd = dmap[ni, nj]
                        if dd < GAP and (ni, nj) != g0:
                            nc += (GAP - dd) * 0.9
                    if nc < cost.get(nk, 1e18):
                        cost[nk] = nc
                        came[nk] = cur
                        hgt[nk] = yn
                        gx, gz = pos(*g0)
                        hh = abs(goal_y - yn) if goal_y is not None else 0.0
                        heapq.heappush(openq, (nc + math.hypot(gx - px, (gz - pz) * 1.5) + hh, nk))
            if found is not None:
                break
        if found is None:
            if levels and goal_y is not None:
                return None                             # stairs / levels: the old straight climb
            if not e.get("_wide"):                       # the way round may be further out: look over the whole stage
                wide = self._plan_path(tr, x0, z0, x1, z1, t, dict(e, _wide=True, _quiet=True))
                if wide and abs(wide[-1][0] - x1) + abs(wide[-1][1] - z1) < 10:
                    return wide                          # it gets there (round the end of the fence)
            if not e.get("_no_people") and len(obs) != len(self._obstacles(tr, t, tgt, people=False)):
                # people move: someone in the way now (walking off at the same moment) is not a wall -
                # plan round the solid things only, never stop dead because of a friend
                return self._plan_path(tr, x0, z0, x1, z1, t, dict(e, _no_people=True))
            # real-world rule: no way round (walled in, a river across) -> stop in front of it, never walk THROUGH
            n = max(2, int(math.hypot(x1 - x0, (z1 - z0) * 1.5) / 15))
            last = (x0, z0)
            for k in range(1, n + 1):
                xs, zs = x0 + (x1 - x0) * k / n, z0 + (z1 - z0) * k / n
                if blocked(xs, zs):
                    break
                last = (xs, zs)
            else:
                return None
            if e.get("_quiet"):
                return None                             # (a trial run: the caller decides)
            self.warn(f"fixed: scene {self.index + 1}: {tr.cdef.id} cannot get through to x={x1:.0f} (something solid "
                      f"is in the way and there is no way round) - stops in front of it. Move the target, or add \"via\" "
                      f"points / \"through\": true")
            if math.hypot(last[0] - x0, last[1] - z0) < 20:
                return [(round(x0), round(z0))]
            return [(round(last[0]), max(0.0, round(last[1])))]
        self._path_climbs = levels and any(abs(hgt[k] - y0) > STEP_UP for k in came)    # stairs on the way
        cells = []
        c = found
        while c is not None:
            cells.append((pos(c[0], c[1]), hgt[c]))
            c = came[c]
        cells.reverse()
        cells[0] = ((x0, z0), y0)
        cells[-1] = ((x1, z1), cells[-1][1])
        self._path_cells = cells
        way, a, ya = [], cells[0][0], cells[0][1]        # keep only the corners (line of sight, same heights)

        def roomy(p, q):
            """the straight cut keeps the gap the path kept (distance map)"""
            if dmap is None:
                return True
            n_ = max(2, int(math.hypot(q[0] - p[0], (q[1] - p[1]) * 1.5) / 25))
            for k_ in range(1, n_):
                x_, z_ = p[0] + (q[0] - p[0]) * k_ / n_, p[1] + (q[1] - p[1]) * k_ / n_
                if math.hypot(x_ - x0, (z_ - z0) * 1.5) < 70 or math.hypot(x_ - x1, (z_ - z1) * 1.5) < 70:
                    continue
                ci_, cj_ = cell(x_, z_)
                if 0 <= ci_ < nx and 0 <= cj_ < nz and dmap[ci_, cj_] < GAP * 0.55:
                    return False
            return True
        i = 0
        while i < len(cells) - 1:
            j = len(cells) - 1
            while j > i + 1:
                ok_, ye = walk_line(a, cells[j][0], ya)
                if ok_ and (not levels or abs(ye - cells[j][1]) <= STEP_UP) and roomy(a, cells[j][0]):
                    break
                j -= 1
            a, ya = cells[j]
            way.append((round(a[0]), max(0.0, round(a[1]))))
            i = j
        if levels:
            return way if len(way) > 1 else None
        return way if len(way) > 1 else None          # EVERY corner (keeping only the last 5 cut through things)

    def _detour(self, tr, x0, z0, x1, z1, t):
        """Real-world rule: nobody walks THROUGH a rock, a log, a chest or a parked car/bus. If one stands on the
        straight way (at about the same depth), return a point to walk round it (in front; behind if at the front)."""
        from . import objects
        if abs(x1 - x0) < 60:
            return None
        lo, hi = sorted((x0, x1))
        best = None
        for pid, o in self.props.items():
            if o.vtype:
                if o.moving(t) or o.vtype in ("paper_boat",):
                    continue
                ox, _, _ = o.pos(t)
                w = 520.0 * o.scale * (1.6 if o.vtype == "bus" else 1.0)
                if any(tr_.riding_at(t) is not None and tr_.riding_at(t).params.get("_vehicle") == pid
                       for tr_ in self.tracks.values()) and o.vtype not in ("bus",):
                    pass
            else:
                if not objects.is_object(o):
                    continue
                st, _ = o.at(t)
                if st[0] != "rest":
                    continue
                ox = st[1]
                w = objects.size(o)[0]
                if w < 70:                              # small things (a stone, an apple): step over them
                    continue
            oz = o.z_at(t)
            if not (lo + 30 < ox < hi - 30):
                continue
            if abs(x1 - ox) < w / 2 + 50 or abs(x0 - ox) < w / 2 + 50:
                continue                                # walking TO it or starting next to it
            u = (ox - x0) / (x1 - x0)
            zc = z0 + (z1 - z0) * u
            if abs(zc - oz) > 110:
                continue
            if best is None or abs(ox - x0) < abs(best[0] - x0):
                best = (ox, oz, w)
        if best is None:
            return None
        ox, oz, w = best
        d = 1 if x1 > x0 else -1
        zv = oz - 170.0 if oz >= 170.0 else oz + 170.0
        return ox, max(0.0, zv)

    def _stop_at_water(self, tr, x0, z0, x1, z1):
        """Real-world rule: people and land animals do not walk into a river / lake / sea - they stop at the
        water's edge (use a boat, or "swim": true, to go in)."""
        if not (self._zones() or (self.bg is not None and getattr(self.bg, "water", None))):
            return x1, z1
        zt = z1 if z1 is not None else z0
        if self._is_water(x0, z0):
            return x1, z1                               # already in the water (a boat scene): leave it
        from .vehicles import BOATS
        for v in self.props.values():                   # walking to a boat to get in: fine
            if v.vtype in BOATS and abs(v.pos(0)[0] - x1) < 320:
                return x1, z1
        last = (x0, z0)
        for k in range(1, 41):
            u = k / 40.0
            xs, zs = x0 + (x1 - x0) * u, z0 + (zt - z0) * u
            if self._is_water(xs, zs):
                d = 1 if x1 >= x0 else -1
                xe = last[0] - d * 40.0
                self.warn(f"fixed: scene {self.index + 1}: {tr.cdef.id} stops at the water's edge (people don't walk into "
                          "water - use a boat, or add \"swim\": true)")
                return xe, (last[1] if z1 is not None else None)
            last = (xs, zs)
        return x1, z1

    def _water_z(self, x):
        for x0, x1, z0, z1 in self._zones():
            if x0 - 400 <= x <= x1 + 400:
                return (z0 + z1) / 2.0
        return None

    def _shore_edge(self, x, direction):
        """The water's edge a thing pushed from x toward `direction` reaches first (None = use the old shore)."""
        zones = self._zones()
        if not zones:
            return None
        cands = [(x0 if direction > 0 else x1) for x0, x1, z0, z1 in zones]
        return min(cands, key=lambda e: abs(e - x))

    def _water_x(self, x_from, direction):
        bg = self.bg
        zones = self._zones()
        if zones:
            x0, x1, z0, z1 = min(zones, key=lambda zn: min(abs(zn[0] - x_from), abs(zn[1] - x_from)))
            return x0 + min(260.0, (x1 - x0) / 2) if abs(x0 - x_from) <= abs(x1 - x_from) else x1 - min(260.0, (x1 - x0) / 2)
        if bg is not None and getattr(bg, "water", None):
            if bg.shore_x is None:
                return x_from + direction * 320
            return bg.shore_x + (260 if bg.land_side == "left" else -260)
        self.warn(f"scene {self.index + 1}: there is no water here - add \"water\": \"river\" and a \"shore\" "
                  "to the background")
        return x_from + direction * 320

    def _obj_where(self, o, t):
        s, _ = o.at(t)
        if s[0] == "held" and s[1] in self.tracks:
            h = self.tracks[s[1]]
            return h.x_at(t), h.z_at(t)
        if s[0] == "in" and s[1] in self.props and s[1] != o.id:   # in a bag / the trunk: where that is
            return self._obj_where(self.props[s[1]], t)
        return o.pos(t)[0], o.z_at(t)

    def _find_object(self, tr, e, kind, t):
        from . import objects
        ref = self._object_ref(e)
        if ref:
            return ref
        name = None
        for k in ("object", "prop", "on", "behind", "thing"):
            if isinstance(e.get(k), str):
                name = e[k]
                break
        if name:
            from . import images
            if name in self.props and not self.props[name].vtype:
                return name
            if objects.base_type(name) in objects.BUILTIN or images.exists(name):
                me = tr.x_at(t)
                f = tr.last_facing()
                self.props[name] = PropTrack({"id": name, "type": name, "x": me + f * 160, "z": tr.z_at(t)})
                self.warn(f"scene {self.index + 1}: object '{name}' was not in the scene's \"objects\" - "
                          f"put it next to {tr.cdef.id}")
                return name
            self.warn(f"scene {self.index + 1}: unknown object '{name}'")
        need = OBJ_NEED.get(kind)
        me, mz = tr.x_at(t), tr.z_at(t)
        best, bd = None, 1e18
        for pid, o in self.props.items():
            if o.vtype or not objects.is_object(o):
                continue
            if need and need not in objects.traits(o):
                continue
            s, _ = o.at(t)
            if s[0] == "held" and s[1] != tr.cdef.id:
                continue
            ox, oz = self._obj_where(o, t)
            d = abs(ox - me) + abs(oz - mz)
            if d < bd:
                best, bd = pid, d
        return best

    def _make_room(self, tr, x1, z1, t):
        """Steering 'separation': don't end a walk inside someone who is standing there - step beside them."""
        for oid, ot in self.tracks.items():
            if ot is tr or ot.crowd:
                continue
            try:
                ox, oz = ot.x_at(t), ot.z_at(t)
            except Exception:
                continue
            if abs(ox - x1) < 75 and abs(oz - z1) < 70:
                side = 1 if x1 >= ox else -1
                if abs(ox - x1) < 5:
                    side = 1 if tr.x_at(t) > ox else -1
                return ox + side * 95.0, z1
        return x1, z1

    def _go(self, tr, x, z, t, run=False):
        if abs(tr.x_at(t) - x) > 12 or abs(tr.z_at(t) - z) > 12:
            t = self._add_action(tr, "run" if run else "walk", {"to": {"x": x, "z": z}}, t, None)
        return t

    def _seg(self, tr, aname, start, dur, x0, x1, facing, params=None, z=None, spec=None):
        spec = spec or tr.actions.get(aname) or ACTIONS.get(aname) or tr.actions["idle"]
        seg = Segment(aname, spec, start, dur, x0, x1, facing, params or {}, z0=z, z1=z)
        tr.segments.append(seg)
        tr.segments.sort(key=lambda q: q.start)
        return seg

    def _struggle(self, tr, o, t, dur=1.6, why="too heavy"):
        x = tr.x_at(t)
        self._seg(tr, "push", t, dur, x, x, tr.last_facing(), {"_strain": 1.0})
        o.events.append((t, "shake", dur))
        tr.icons.append((t + 0.3, "sweat"))
        self.warn(f"scene {self.index + 1}: {tr.cdef.id} can't move '{o.id}' ({why}) - add \"helpers\": [...] or "
                  "\"strong\": true")
        return t + dur

    def _finish_perches(self):
        ENDS = ("hop_down", "ride", "mount")
        for tr in self.tracks.values():
            for p in tr.perches:
                if p[3] is not None:
                    continue
                for sgm in tr.segments:
                    if sgm.start <= p[0] + p[2] + 1e-6 or sgm.params.get("_perch_keep"):
                        continue
                    if sgm.spec.moving or sgm.action in ENDS or sgm.params.get("_perch_x") is not None:
                        p[3] = sgm.start
                        break

    def _perched(self, tr, t):
        for p in reversed(tr.perches):
            if p[0] <= t and (p[3] is None or p[3] > t):
                return p
        return None

    def _into_water(self, o, x, t):
        from . import objects
        w, h = objects.size(o)
        tr_ = objects.traits(o)
        kind = "float" if "floats" in tr_ else "sink"
        self.effects.append(dict(start=t, kind="splash", x=x, y=0.0, dur=1.0, who=None, z=o.z_at(t),
                                 intensity=clamp(max(w, h) / 110.0, 0.35, 1.6)))
        self.sfx.append((t, "splash" if max(w, h) > 60 else "plop", 0.85, o.id))
        o.events.append((t, kind, None))
        return t + (0.6 if kind == "float" else 1.4)

    def _land(self, o, x, t, direction, hit=None, react=True, speed=None):
        """A thrown / kicked / dropped object comes down at x: splash, break, hit someone or bounce - by what it
        is made of, how heavy it is and how fast it lands (speed in units/s; None = thrown hard enough)."""
        from . import objects
        T = objects.traits(o)
        w, h = objects.size(o)
        if self._is_water(x, o.z_at(t)):
            return self._into_water(o, x, t)
        mat_name = realworld.material(o)
        mat = realworld.MATERIALS[mat_name]
        surf = self.surface_at(x, o.z_at(t))
        soft = surf in realworld.SOFT_GROUND
        # breaks: clay / glass hitting the ground fast enough (a pot set down on sand stays whole)
        brk_v = (2.0 if not soft else 4.5) * realworld.M
        if ("break" in T or mat["breaks"]) and (speed is None or speed > brk_v):
            o.events.append((t, "break", None))
            self.sfx.append((t, "crash", clamp(0.5 + 0.15 * realworld.mass_of(o), 0.5, 1.0), o.id))
            self.effects.append(dict(start=t, kind="dust", x=x, y=0.0, dur=0.8, who=None, z=o.z_at(t)))
            return t + 0.4
        if mat["drag"] < 0.5:                             # light things (a leaf) land without a puff
            self._impact(t, None, x, o.z_at(t), size=clamp(max(w, h) / 90.0, 0.3, 1.5))
        snd, vol = realworld.landing_sound(o, surf, speed)
        if snd:
            self.sfx.append((t, snd, vol, o.id))
        if hit and react and hit in self.tracks:
            self._add_action(self.tracks[hit], "surprised", {}, t, None)
            self.tracks[hit].icons.append((t, "stars"))
        # bounces that lose energy each time (restitution: rubber keeps most, a sack none; soft ground takes
        # more), then a round thing rolls to a stop (friction). Each hop is a real ballistic arc.
        g = self.g * realworld.M                          # (the planet's gravity)
        rnd = "round" in T
        e_rest = mat["e"] * (0.55 if soft else 1.0)
        if "heavy" in T:
            e_rest = min(e_rest, 0.1)
        if speed is not None:
            H = (e_rest * speed) ** 2 / (2.0 * g)          # the height of the first bounce: (e·v)² / 2g
        else:
            H = (min(70.0, 20 + w * 0.3) if mat_name == "rubber" else min(18.0, 6 + w * 0.2)) * e_rest / 0.5
        vx = 260.0 if mat_name == "rubber" else 120.0
        if speed is not None and abs(direction) < 0.5:     # straight down: hardly any sideways speed
            vx = 15.0
        direction = direction if abs(direction) >= 0.5 else 1
        cx, tt = x, t
        for k_ in range(5 if rnd or mat_name == "rubber" else 2):
            if H < 3.0:
                break
            dur = 2.0 * math.sqrt(2.0 * H / g)
            nx = cx + direction * vx * dur
            if self._is_water(nx, o.z_at(t)):
                break
            o.add(tt, ("move", cx, 0.0, nx, 0.0, dur, H, "throw"))
            tt += dur
            cx = nx
            if snd:
                self.sfx.append((tt, snd, max(0.08, vol * e_rest ** (k_ + 1)), o.id))
            H *= max(e_rest, 0.0001) ** 2                 # (height goes with the square of the speed)
            vx *= 0.7
        if rnd and vx > 20:                               # roll on and stop (friction: more on sand / grass)
            roll_d = vx * (0.8 if mat_name == "rubber" else 0.35) * (0.5 if soft else 1.0)
            if not self._is_water(cx + direction * roll_d, o.z_at(t)):
                o.add(tt, ("move", cx, 0.0, cx + direction * roll_d, 0.0, 1.0, 0.0, "roll"))
                tt += 1.0
                cx += direction * roll_d
        o.add(tt, ("rest", cx, 0.0))
        return tt

    def _fall(self, o, x, height, t, z=None):
        """Let a thing fall from `height` (units) at x: a stone / pot / sack drops by gravity (faster and
        faster), a leaf / paper / feather floats down slowly and drifts with the wind; then it lands."""
        mat = dict(realworld.MATERIALS[realworld.material(o)])
        if getattr(self.bg, "no_air", False):            # no air (the Moon): a feather falls like a stone
            mat["drag"] = 0.0
        height = max(0.0, float(height))
        if z is not None:
            o.zmoves.append((t, 0.01, z, z, None))
            o.zmoves.sort(key=lambda m: m[0])
        if height < 2.0:
            o.add(t, ("rest", x, 0.0))
            return t
        dur = realworld.fall_time(height, mat["drag"], self.g)
        if self._is_water(x, o.z_at(t)) and mat["drag"] < 0.3:
            o.add(t, ("move", x, height, x, 0.0, dur, 0.0, "fall"))
            o.add(t + dur, ("rest", x, 0.0))
            return self._into_water(o, x, t + dur)
        if mat["drag"] >= 0.3:
            x1 = x + realworld.wind().speed(t) * dur * 0.7      # carried by the wind as it floats down
            o.add(t, ("move", x, height, x1, 0.0, dur, 30.0 + 30.0 * mat["drag"], "flutter"))
            speed = (1.0 - mat["drag"]) * 3.0 * realworld.M
        else:
            x1 = x
            o.add(t, ("move", x, height, x, 0.0, dur, 0.0, "fall"))
            speed = math.sqrt(2.0 * self.g * realworld.M * height)     # v = sqrt(2gh)
        o.add(t + dur, ("rest", x1, 0.0))
        if dur > 0.8 and mat["drag"] < 0.3:                   # a long fall (3 m+): the air rushing past
            self.sfx.append((t, "whoosh", 0.25, o.id))
        return self._land(o, x1, t + dur, 0, speed=speed)

    def _object_action(self, tr, raw, e, start):
        from . import objects
        kind = OBJ_WORDS.get(raw) or OBJ_MAYBE.get(raw, raw)
        if tr.cdef.kind != "human" and kind not in ("hide", "come_out", "peek", "sit_on", "stand_on", "get_down",
                                                    "enter", "emerge"):
            return None
        if kind in ("enter", "emerge") and (e.get("vehicle") or e.get("car")):
            return None                                      # "enter" a car = get in (the vehicle code does it)
        t = start
        if tr.riding_at(t) is not None or tr.mounted_at(t) is not None:
            t = self._get_out(tr, {}, t)
        if kind in ("enter", "emerge"):
            return self._obj_door(tr, kind, e, t)
        if kind == "get_down":
            return self._get_down(tr, t)
        if kind in ("come_out", "peek"):
            return self._come_out(tr, kind, e, t)
        if kind == "put" and not (e.get("object") or e.get("prop")):
            held = self.prop_holder_of(tr.cdef.id, t)           # "put it on the table": what is in the hand
            if held is not None:
                e = dict(e, object=held)
        pid = self._find_object(tr, e, kind, t)
        if pid is None:
            if kind == "hide":
                return None                                  # nothing to hide behind: old "disappear"
            self.warn(f"scene {self.index + 1}: {tr.cdef.id} wants to {raw} but there is no object that can "
                      f"'{OBJ_NEED.get(kind, kind)}' (add one to the scene's \"objects\")")
            return None
        o = self.props[pid]
        T = objects.traits(o)
        need = OBJ_NEED.get(kind)
        if need and need not in T and not (kind in ("throw", "carry", "kick") and "light" in T):
            self.warn(f"scene {self.index + 1}: '{pid}' can't be used to {raw} (it has: "
                      f"{', '.join(sorted(T)) or 'no abilities'}) - trying anyway")
        fn = {"push": self._obj_push, "pull": self._obj_push, "roll": self._obj_push, "throw": self._obj_throw,
              "kick": self._obj_kick, "carry": self._obj_carry, "sit_on": self._obj_perch,
              "stand_on": self._obj_perch, "climb": self._obj_perch, "hide": self._obj_hide,
              "open": self._obj_open, "close": self._obj_open, "break": self._obj_break,
              "turn_on": self._obj_state, "turn_off": self._obj_state, "use": self._obj_state,
              "put": self._obj_put}.get(kind)
        if fn is None:
            return None
        return fn(tr, o, kind, e, t)

    def _target_x(self, e, tr, t, x_from, default_dir, keys=("to", "target", "into")):
        """Where something should go: number, name, character, {"x", "z"} or water. Returns (x, z or None, who)."""
        for k in keys:
            if k not in e:
                continue
            v = e[k]
            if isinstance(v, dict):
                x = self._resolve_x(v["x"], None, t, x_from) if "x" in v else x_from
                z = parse_z(v.get("z", v.get("depth")), 0.0) if ("z" in v or "depth" in v) else None
                return x, z, None
            if isinstance(v, str) and v.lower() in WATER_WORDS:
                wx = self._water_x(x_from, default_dir)
                return wx, self._water_z(wx), None
            if isinstance(v, str) and v in self.tracks:
                return self.tracks[v].x_at(t), self.tracks[v].z_at(t), v
            if isinstance(v, str) and v in self.props:
                ox, oz = self._obj_where(self.props[v], t)
                return ox, oz, None
            return self._resolve_x(v, None, t, x_from), None, None
        if "by" in e:
            return x_from + float(e["by"]), None, None
        return None, None, None

    def _obj_push(self, tr, o, kind, e, t):
        from . import objects
        T = objects.traits(o)
        w, h = objects.size(o)
        sc = tr.cdef.scale
        x_o, z_o = self._obj_where(o, t)
        me = tr.x_at(t)
        d0 = (1 if x_o >= me else -1) if abs(x_o - me) > 5 else tr.last_facing()
        if kind == "pull":
            d0 = -d0
        dest, _, _ = self._target_x(e, tr, t, x_o, d0)
        if dest is None:
            dest = x_o + d0 * float(e.get("distance", 320))
        direction = 1 if dest >= x_o else -1
        t_start = t
        if kind == "pull":
            stand, face = x_o + direction * (w / 2 + 34 * sc), -direction
        else:
            stand, face = x_o - direction * (w / 2 + 26 * sc), direction
        t = self._go(tr, stand, z_o, t)
        helpers = [hid for hid in (e.get("helpers") or e.get("help") or []) if hid in self.tracks and hid != tr.cdef.id]
        ht = []
        for k, hid in enumerate(helpers):
            h_tr = self.tracks[hid]
            hz = max(0.0, z_o + 100 * (k + 1))
            t_h = self._go(h_tr, stand + direction * 14 * (k + 1), hz, t_start)
            ht.append((h_tr, hz))
            t = max(t, t_h)
        heavy = "heavy" in T
        force = 1 + len(helpers) + (1 if e.get("strong") else 0)
        hand = clamp((min(h * 0.6, 220) - 190) * 0.35, -45, 15)
        if "movable" not in T:
            return self._struggle(tr, o, t, why="it does not move")
        if heavy and force < 2:                     # too heavy for one person: pushes hard, it only wobbles
            dur0 = float(e.get("duration", 0) or 0) or 2.2
            self._seg(tr, "pull" if kind == "pull" else "push", t, dur0, stand, stand, face,
                      {"_strain": 1.0, "_hand": hand}, z=z_o)
            o.events.append((t + 0.2, "shake", dur0 - 0.3))
            tr.icons.append((t + 0.5, "sweat"))
            self.sfx.append((t + 0.3, "scrape", 0.25, o.id))
            return t + dur0
        speed = float(e.get("speed", 0) or 0) or (80 + 25 * (force - 2) if heavy else 150)
        if "round" in T:
            speed *= 1.3
        slide = None
        bg = self.bg
        edge = self._shore_edge(x_o, direction)
        if self._is_water(dest, z_o) or self._is_water(dest + direction * w * 0.3, z_o):
            if edge is not None or (bg is not None and bg.shore_x is not None):   # to the edge, it slides in
                edge = edge if edge is not None else bg.shore_x
                if (dest - (edge - direction * w * 0.3)) * direction > 0:
                    dest = edge - direction * w * 0.3
                slide = edge + direction * (w / 2 + 40)
            else:
                slide = dest + direction * w * 0.5
        dx = dest - x_o
        dur = float(e.get("duration", 0) or 0) or max(0.8, abs(dx) / speed)
        aname = "pull" if kind == "pull" else "push"
        self._seg(tr, aname, t, dur, stand, stand + dx, face, {"_hand": hand, "_obj": o.id}, z=z_o,
                  spec=ActionSpec(ACTIONS[aname].fn, dur, moving=True, blend_in=0.3))
        for k, (h_tr, hz) in enumerate(ht):
            hx = stand + direction * 14 * (k + 1)
            self._seg(h_tr, aname, t, dur, hx, hx + dx, face, {"_hand": hand}, z=hz,
                      spec=ActionSpec(ACTIONS[aname].fn, dur, moving=True, blend_in=0.3))
        mode = "roll" if "round" in T else "push"
        o.add(t, ("move", x_o, 0.0, dest, 0.0, dur, 0.0, mode))
        o.add(t + dur, ("rest", dest, 0.0))
        snd = "rumble" if ("round" in T and heavy) else "scrape"
        self.loops.append((t, t + dur, snd, 0.5 if heavy else 0.3, o.id))
        end = t + dur
        if slide is not None:
            o.add(end, ("move", dest, 0.0, slide, 0.0, 0.55, 0.0, mode))
            o.add(end + 0.55, ("rest", slide, 0.0))
            self._into_water(o, slide, end + 0.4)
            end += 0.9
        return end

    def _pick_up(self, tr, o, t):
        from . import objects
        s, _ = o.at(t)
        if s[0] == "in" and s[1] in self.props:              # out of the bag / trunk first
            o.add(t, ("rest",) + tuple(self.props[s[1]].pos(t)[:2]))
        x_o, z_o = self._obj_where(o, t)
        y_o = float(o.pos(t)[1] or 0.0)
        me = tr.x_at(t)
        side = 1 if me >= x_o else -1
        sc = tr.cdef.scale
        if y_o > 25.0:                                       # on a table / shelf / the bed: stand in front of it
            t = self._go(tr, x_o + side * 26 * sc, max(0.0, z_o - 62.0), t)
        else:
            t = self._go(tr, x_o + side * 38 * sc, z_o, t)
        h = self._reach_h(tr, y_o + 0.5 * objects.size(o)[1])   # where the hand goes (in grown-up units)
        return self._add_action(tr, "pick", {"prop": o.id, "facing": "left" if side > 0 else "right", "h": h},
                                t, None)

    @staticmethod
    def _reach_h(tr, h):
        """a height in the world -> the same height on a grown-up of the poses (300 tall): a sculpted person stands
        ~405 units tall (engine/sculpt_people.py), the older bodies 300 (both times their own scale)"""
        tall = 405.0 if (tr.cdef.spec or {}).get("look3d") == "sculpt" else 300.0
        return h * 300.0 / (tall * max(tr.cdef.scale, 0.3))

    def _surface(self, th, t, level=None):
        """A thing to put something on -> (x, z, top height, half width, half depth). The sculpted furniture knows
        its real top (a table 130, the kitchen platform 150, a charpai 78, the bed 92); a shelf has boards
        (level 1, 2, 3); anything else: its own top."""
        from . import objects, images, sculpt_things
        x, y, _ = th.pos(t)
        z = th.z_at(t)
        img = objects._image_name(th)
        meta = (images.info(img) or {}) if img else {}
        name = re.sub(r"_\d+$", "", str(meta.get("thing") or th.type))
        w, h = objects.size(th)
        fp = meta.get("foot")
        hw = (abs(fp[1] - fp[0]) / 2.0) if fp else w / 2.0
        hd = (abs(fp[3] - fp[2]) / 2.0) if fp else 30.0
        top = sculpt_things.TOPS.get(name)
        K = sculpt_things.CLAY_SCALE                     # (the sculpted furniture is drawn at the people's measure)
        if top is None:
            top = float(y or 0.0) + h
        else:
            top *= K
        if name == "shelf":
            top = (122.0 + 45.0 * (max(1, min(3, int(level or 1))) - 1)) * K
        if name in ("bed", "sofa"):
            hw *= 0.8                                        # (not on the headboard / the arm)
        return x, z, float(top), hw, hd

    def _obj_put(self, tr, o, kind, e, t):
        """Put a thing somewhere and leave it there: "on" a table / shelf ("level": 2) / the bed / the platform,
        "in" a bag / the trunk / a bucket (then it is inside: not seen until someone takes it out), or "to" a
        spot on the floor. Picked up first if it is not in the hand yet; it stays where it was put (and is still
        there in the next scene at the same place: engine/project.py)."""
        from . import objects
        s, _ = o.at(t)
        if s[0] == "held" and s[1] != tr.cdef.id:
            self.warn(f"scene {self.index + 1}: '{o.id}' is in {s[1]}'s hand - {tr.cdef.id} can't put it down")
            return None
        if not (s[0] == "held" and s[1] == tr.cdef.id):
            t = self._pick_up(tr, o, t)
        sc = tr.cdef.scale
        me = tr.x_at(t)
        on = e.get("on") or e.get("onto") or e.get("upon")
        into = e.get("in") or e.get("into") or e.get("inside")
        ref = into if into in self.props else (on if on in self.props else None)
        if into and into not in self.props:
            self.warn(f"scene {self.index + 1}: put '{o.id}' in '{into}' - there is no '{into}' here")
        if on and on not in self.props and not into:
            self.warn(f"scene {self.index + 1}: put '{o.id}' on '{on}' - there is no '{on}' here (put on the floor)")
        oh = objects.size(o)[1]
        if ref is not None:
            th = self.props[ref]
            sx, sz, top, hw, hd = self._surface(th, t, e.get("level") or e.get("shelf"))
            if ref == into:                                  # in it: the hand goes to its opening
                ix, iz, ytop = sx, sz, top
            else:                                            # on it: on the near part, toward whoever puts it
                room = max(0.0, hw - 18.0)
                ix = sx + clamp(me - sx, -room, room)
                for p_ in self.props.values():               # (not right on top of another thing there)
                    if p_ is not o and p_.at(t)[0][0] == "rest" and abs(float(p_.pos(t)[1] or 0) - top) < 6 and \
                            abs(p_.pos(t)[0] - ix) < 22 and abs(p_.z_at(t) - sz) < 60:
                        ix += 30.0 if ix <= sx else -30.0
                iz = sz - min(hd * 0.35, 25.0)
                ytop = top
            side = 1 if me >= ix else -1
            t = self._go(tr, ix + side * 26 * sc, max(0.0, iz - max(hd * 0.7, 40.0) - 30.0), t)
        else:
            tx, tz, _w = self._target_x(e, tr, t, me, tr.last_facing(), keys=("to", "at", "near"))
            if tx is not None:
                side = 1 if me >= tx else -1
                t = self._go(tr, tx + side * 40 * sc, tz if tz is not None else tr.z_at(t), t)
                ix, iz = tx, (tz if tz is not None else tr.z_at(t))
            else:
                side = -tr.last_facing()
                ix, iz = me - side * 45 * sc, tr.z_at(t)
            ytop = 0.0
        h_hand = self._reach_h(tr, ytop + 0.5 * oh)
        dur = 1.4
        end = self._add_action(tr, "put", {"facing": "left" if side > 0 else "right", "h": h_hand}, t, None)
        t_ev = t + dur * 0.52
        mz = tr.z_at(t_ev)
        if ref is not None and ref == into:
            o.add(t_ev, ("in", into))                        # inside now: not drawn until taken out
            self.sfx.append((t_ev, "rustle", 0.35, tr.cdef.id))
        else:
            o.add(t_ev, ("rest", ix, ytop))
            if abs(iz - mz) > 1.0:
                o.zmoves.append((t_ev, 0.05, mz, iz, None))
                o.zmoves.sort(key=lambda m: m[0])
            self.sfx.append((t_ev, "thud", 0.18, tr.cdef.id))
        return max(end, t + dur)

    def _obj_carry(self, tr, o, kind, e, t):
        from . import objects
        T = objects.traits(o)
        s, _ = o.at(t)
        if s[0] == "held" and s[1] == tr.cdef.id:
            pass
        elif "heavy" in T and not e.get("strong"):
            x_o, z_o = self._obj_where(o, t)
            t = self._go(tr, x_o - tr.last_facing() * (objects.size(o)[0] / 2 + 26), z_o, t)
            return self._struggle(tr, o, t, why="too heavy to carry")
        else:
            t = self._pick_up(tr, o, t)
        if "to" in e:
            x1, z1, _ = self._target_x(e, tr, t, tr.x_at(t), tr.last_facing(), keys=("to",))
            t = self._go(tr, x1, z1 if z1 is not None else tr.z_at(t), t)
        return t

    def _obj_throw(self, tr, o, kind, e, t):
        from . import objects
        T = objects.traits(o)
        s, _ = o.at(t)
        if not (s[0] == "held" and s[1] == tr.cdef.id):
            if s[0] == "held":
                self.warn(f"scene {self.index + 1}: '{o.id}' is in {s[1]}'s hand")
                return None
            if "heavy" in T and not e.get("strong"):
                x_o, z_o = self._obj_where(o, t)
                t = self._go(tr, x_o - tr.last_facing() * (objects.size(o)[0] / 2 + 26), z_o, t)
                return self._struggle(tr, o, t, why="too heavy to throw")
            t = self._pick_up(tr, o, t)
        me, mz = tr.x_at(t), tr.z_at(t)
        tx, tz, hit = self._target_x(e, tr, t + 0.8, me, tr.last_facing())
        if tx is None:
            tx = me + tr.last_facing() * float(e.get("distance", 420))
        facing = 1 if tx >= me else -1
        self._seg(tr, "throw", t, 0.9, me, me, facing, {})
        rel = t + 0.9 * 0.45
        sc = tr.cdef.scale
        hx, hy = me + facing * 45 * sc, tr.y_at(rel) + 215 * sc
        dist = math.hypot(tx - hx, ((tz - mz) * ZK * 2.0) if tz is not None else 0.0)
        fd = float(e.get("flight", 0) or 0) or clamp(dist / 650.0, 0.45, 1.5)
        arc = float(e.get("arc", 60 + dist * 0.28))
        o.add(rel, ("move", hx, hy, tx, 0.0, fd, arc, "throw"))
        o.zmoves.append((rel, fd, mz, tz if tz is not None else mz, None))
        o.zmoves.sort(key=lambda m: m[0])
        self.sfx.append((rel, "whoosh", 0.6, tr.cdef.id))
        land = rel + fd
        o.add(land, ("rest", tx, 0.0))
        end = self._land(o, tx, land, facing, hit, e.get("react", True))
        return max(t + 0.9, end)

    def _obj_kick(self, tr, o, kind, e, t):
        from . import objects
        T = objects.traits(o)
        w, h = objects.size(o)
        x_o, z_o = self._obj_where(o, t)
        me = tr.x_at(t)
        d0 = (1 if x_o >= me else -1) if abs(x_o - me) > 5 else tr.last_facing()
        t = self._go(tr, x_o - d0 * (w / 2 + 40 * tr.cdef.scale), z_o, t)
        t_hit = t + 0.8 * 0.5
        self._add_action(tr, "kick", {"facing": "right" if d0 > 0 else "left"}, t, None)
        tx, tz, hit = self._target_x(e, tr, t_hit, x_o, d0)
        if tx is None:
            tx = x_o + d0 * float(e.get("distance", 380 if "light" in T else 220))
        self.sfx.append((t_hit, "thud", 0.5, tr.cdef.id))
        if "heavy" in T and not e.get("strong"):                   # ouch!
            tr.icons.append((t_hit, "stars"))
            o.events.append((t_hit, "shake", 0.3))
            self._add_action(tr, "jump", {"height": 40}, t + 0.8, "crying")
            return t + 0.8 + 1.1
        if "light" in T:
            fd = clamp(abs(tx - x_o) / 700.0, 0.4, 1.2)
            o.add(t_hit, ("move", x_o, 0.0, tx, 0.0, fd, 60 + abs(tx - x_o) * 0.3, "throw"))
            if tz is not None:
                o.zmoves.append((t_hit, fd, z_o, tz, None))
                o.zmoves.sort(key=lambda m: m[0])
            o.add(t_hit + fd, ("rest", tx, 0.0))
            return max(t + 0.8, self._land(o, tx, t_hit + fd, d0, hit, e.get("react", True)))
        fd = max(0.6, abs(tx - x_o) / 260.0)
        o.add(t_hit, ("move", x_o, 0.0, tx, 0.0, fd, 0.0, "roll" if "round" in T else "push"))
        o.add(t_hit + fd, ("rest", tx, 0.0))
        self.loops.append((t_hit, t_hit + fd, "rumble" if "round" in T else "scrape", 0.35, o.id))
        end = t_hit + fd
        if self._is_water(tx, z_o):
            end = self._into_water(o, tx, end)
        return max(t + 0.8, end)

    def _obj_perch(self, tr, o, kind, e, t):
        from . import objects
        w, h = objects.size(o)
        sc = tr.cdef.scale
        x_o, z_o = self._obj_where(o, t)
        me = tr.x_at(t)
        side = 1 if me >= x_o else -1
        zc = max(0.0, z_o - 2)
        if kind == "climb":
            height = float(e.get("height", 0) or 0) or (objects.top_of(o) * (0.55 if h > 260 else 0.95))
            t = self._go(tr, x_o + side * min(20.0, w * 0.1), zc, t)
            up = max(1.2, height / 110.0)
            x = tr.x_at(t)
            self._seg(tr, "climb", t, up, x, x, -side, {"_perch_keep": True}, z=zc)
            tr.perches.append([t, height, up, None, o.id])
            self._seg(tr, "perch", t + up, 0.8, x, x, -side if e.get("facing") is None else side,
                      {"_perch_keep": True}, z=zc)
            self.sfx.append((t, "whoosh", 0.25, tr.cdef.id))
            return t + up + 0.4
        top = objects.top_of(o, sit=(kind == "sit_on"))
        near = x_o + side * (w / 2 + 28 * sc)
        t = self._go(tr, near, zc, t)
        on_x = x_o + side * min(w * 0.18, 30.0)
        if kind == "sit_on":
            up = 0.55 if top < 170 else top / 170.0
            self._seg(tr, "sit_on", t, 0.8, near, on_x, side, {"_perch_x": (near, on_x, up)}, z=zc)
        else:
            up = 0.7 if top < 150 else top / 140.0
            self._seg(tr, "step_up" if top < 150 else "climb", t, up, near, on_x, -side,
                      {"_perch_x": (near, on_x, up), "_perch_keep": True}, z=zc)
            self._seg(tr, "stand", t + up, 0.4, on_x, on_x, side, {"_perch_keep": True}, z=zc)
        tr.perches.append([t, top, up, None, o.id])
        self.sfx.append((t + up * 0.8, "land", 0.35, tr.cdef.id))
        return t + up + 0.25

    def _get_down(self, tr, t):
        p = self._perched(tr, t)
        if p is None:
            return self._get_out(tr, {}, t) if (tr.riding_at(t) or tr.mounted_at(t)) else t
        x = tr.x_at(t)
        f = tr.last_facing()
        o = self.props.get(p[4])
        from . import objects
        w = objects.size(o)[0] if o else 80
        x1 = x + f * (w / 2 + 40)
        self._seg(tr, "hop_down", t, 0.6, x, x1, f, {},
                  spec=ActionSpec(ACTIONS["hop_down"].fn, 0.6, moving=True, oneshot=True, blend_in=0.1))
        p[3] = t
        self.sfx.append((t + 0.45, "land", 0.4, tr.cdef.id))
        return t + 0.6

    def _obj_hide(self, tr, o, kind, e, t):
        from . import objects
        w, h = objects.size(o)
        x_o, z_o = self._obj_where(o, t)
        off = (stable_hash(tr.cdef.id) % 7 - 3) / 3.0 * w * 0.18
        zb = z_o + max(55.0, min(140.0, w * 0.3))
        t = self._go(tr, x_o + off, zb, t, run=e.get("run", True))
        f = tr.last_facing()
        who = e.get("from")
        if who in self.tracks:
            f = 1 if self.tracks[who].x_at(t) > x_o else -1
        if tr.cdef.kind == "human":
            self._seg(tr, "hide", t, 0.7, x_o + off, x_o + off, f, {}, z=zb)
        else:
            self._seg(tr, "sit" if "sit" in tr.actions else "idle", t, 0.7, x_o + off, x_o + off, f, {}, z=zb)
        o.events.append((t, "rustle", None))
        self.sfx.append((t, "whoosh", 0.25, tr.cdef.id))
        return t + 0.7

    def _come_out(self, tr, kind, e, t):
        x = tr.x_at(t)
        f = tr.last_facing()
        if kind == "peek":
            if tr.cdef.kind != "human":
                return t
            self._seg(tr, "peek", t, 1.0, x, x, f, {}, z=tr.z_at(t))
            return t + 1.0
        z = tr.z_at(t)
        to = e.get("to")
        if to is not None:
            return self._add_action(tr, "walk", {"to": to}, t, None)
        return self._go(tr, x + f * 160, max(0.0, z - 130), t)

    def _door_of(self, tr, e, t, prefer=None):
        """(building id, (door x, z, out x, out z, toward camera)) - the door someone means, or the nearest."""
        name = None
        for k in ("object", "into", "building", "out_of", "thing", "door", "house"):
            if isinstance(e.get(k), str):
                name = e[k]
                break
        me, mz = tr.x_at(t), tr.z_at(t)
        cands = [name] if name else ([prefer] if prefer else [pid for pid in self.props])
        if name and name not in self.props:
            self.warn(f"scene {self.index + 1}: unknown building / object '{name}' for {tr.cdef.id}")
            return None, None
        best = None
        for pid in cands:
            for d in self.door_spots(pid, t):
                dist = abs(d[2] - me) + abs(d[3] - mz)
                if best is None or dist < best[0]:
                    best = (dist, pid, d)
        if best is None:
            what = f"'{name}'" if name else "anything here"
            self.warn(f"scene {self.index + 1}: {tr.cdef.id} can't go in or out - {what} has no door "
                      "(draw one with pen.door(...) in its 3D code)")
            return None, None
        return best[1], best[2]

    def _obj_door(self, tr, kind, e, t):
        """enter: walk to the door, it opens, walk in and vanish inside.  emerge (come_out_of / come_in): appear in
        the doorway and step out (into the room of an inside place, or out of a building), then go on to "to"."""
        pid, d = self._door_of(tr, e, t, prefer=getattr(tr, "inside_of", None) if kind == "emerge" else None)
        if d is None:
            return None
        o = self.props[pid]
        from . import objects
        dx, dz, ox, oz, toward_cam = d
        f = tr.last_facing()
        if kind == "enter":
            t = self._go(tr, ox, oz, t, run=bool(e.get("run")))
            if "open" in objects.traits(o) or objects.state_image(o, "open"):
                o.events.append((t + 0.1, "open", None))
            self.sfx.append((t + 0.1, "door", 0.6, pid))
            t = self._add_action(tr, "run" if e.get("run") else "walk",
                                 {"to": {"x": dx, "z": dz}, "through": True, "speed": 170}, t, None)
            self._seg(tr, "disappear", t, 0.45, dx, dx, tr.last_facing(), {"_door": pid}, z=dz)
            tr.inside_of = pid
            return t + 0.45
        # emerge
        self.sfx.append((t, "door", 0.6, pid))
        if "open" in objects.traits(o) or objects.state_image(o, "open"):
            o.events.append((t, "open", None))
        self._seg(tr, "appear", t, 0.45, dx, dx, f, {"_door": pid}, z=dz)
        t += 0.45
        t = self._add_action(tr, "run" if e.get("run") else "walk",
                             {"to": {"x": ox, "z": oz}, "through": True, "speed": 190}, t, None)
        tr.inside_of = None
        if "to" in e:
            t = self._add_action(tr, "run" if e.get("run") else "walk", {"to": e["to"]}, t, None)
        return t

    def _obj_open(self, tr, o, kind, e, t):
        from . import objects
        w, h = objects.size(o)
        x_o, z_o = self._obj_where(o, t)
        me = tr.x_at(t)
        side = 1 if me >= x_o else -1
        t = self._go(tr, x_o + side * (w / 2 + 30 * tr.cdef.scale), max(0.0, z_o - 2), t)
        self._seg(tr, "open", t, 1.2, tr.x_at(t), tr.x_at(t), -side, {}, z=max(0.0, z_o - 2))
        o.events.append((t + 0.55, kind, None))
        self.sfx.append((t + 0.45, "creak", 0.6, o.id))
        if kind == "open" and (o.spec.get("treasure") or (objects.base_type(o.type) == "chest"
                                                           and o.spec.get("treasure", True))):
            self.sfx.append((t + 0.9, "magic", 0.5, o.id))
            self.effects.append(dict(start=t + 0.8, kind="sparkle", x=x_o, y=h * 0.5, dur=1.8, who=None,
                                     z=z_o, intensity=0.8))
            tr.icons.append((t + 1.0, "!"))
        return t + 1.2

    def _obj_state(self, tr, o, kind, e, t):
        """turn_on / turn_off / use: walk to the object, reach for it, its picture changes to the new state."""
        from . import objects
        w, h = objects.size(o)
        x_o, z_o = self._obj_where(o, t)
        me = tr.x_at(t)
        side = 1 if me >= x_o else -1
        st = e.get("state")
        if not st:
            if kind == "turn_on":
                st = "on"
            elif kind == "turn_off":
                st = "off"
            else:                                         # "use": the object's first extra state
                extra = [k for k in objects.states_of(o) if k not in ("open", "broken")]
                st = extra[0] if extra else "on"
        if st not in ("off", "normal") and not objects.state_image(o, st):
            self.warn(f"scene {self.index + 1}: '{o.id}' has no '{st}' picture (make it on an object sheet)")
        t = self._go(tr, x_o + side * (w / 2 + 30 * tr.cdef.scale), max(0.0, z_o - 2), t)
        self._seg(tr, "open", t, 1.0, tr.x_at(t), tr.x_at(t), -side, {}, z=max(0.0, z_o - 2))
        o.events.append((t + 0.5, "state", st))
        self.sfx.append((t + 0.45, "magic" if st == "on" else "pop", 0.45, o.id))
        if st not in ("off", "normal"):
            self.effects.append(dict(start=t + 0.5, kind="sparkle", x=x_o, y=h * 0.6, dur=0.9, who=None, z=z_o,
                                     intensity=0.5))
        return t + 1.0

    def _obj_break(self, tr, o, kind, e, t):
        from . import objects
        w, h = objects.size(o)
        T = objects.traits(o)
        x_o, z_o = self._obj_where(o, t)
        me = tr.x_at(t)
        side = 1 if me >= x_o else -1
        t = self._go(tr, x_o + side * (w / 2 + 34 * tr.cdef.scale), max(0.0, z_o - 2), t)
        self._seg(tr, "smash", t, 1.0, tr.x_at(t), tr.x_at(t), -side, {}, z=max(0.0, z_o - 2))
        hit = t + 0.55
        if "break" in T:
            o.events.append((hit, "break", None))
            self.sfx.append((hit, "crash", 0.8, o.id))
            self.effects.append(dict(start=hit, kind="dust", x=x_o, y=0.0, dur=0.8, who=None, z=z_o))
        else:
            self.sfx.append((hit, "thud", 0.6, o.id))
            o.events.append((hit, "shake", 0.3))
            tr.icons.append((hit, "stars"))
        return t + 1.0

    # ------------------------------------------------------------------ props / effects
    def _prop_fall(self, e, start):
        """{"prop": "pot", "fall": true, "from": 300} or {"prop": "leaf", "fall": 400, "x": 900}: it falls from that
        height (units; default: where it is now, else 300) and lands by its weight and material."""
        pid = e["prop"]
        if pid not in self.props:
            self.props[pid] = PropTrack({"id": pid, "type": e.get("type", pid), "x": float(e.get("x", self.world_w / 2)),
                                         "material": e.get("material")})
        pt = self.props[pid]
        x, y = pt.pos(start)[:2]
        if "x" in e:
            x = self._resolve_x(e["x"], None, start, x)
        f = e.get("fall")
        h = e.get("from", e.get("height", f if isinstance(f, (int, float)) and not isinstance(f, bool) else None))
        h = float(h) if h is not None else (y if y > 2 else 300.0)
        z = parse_z(e["z"], pt.z_at(start)) if "z" in e else None
        end = self._fall(pt, x, h, start, z=z)
        return end if e.get("block", True) else start

    def _prop_move(self, e, start):
        pid = e["prop"]
        if pid not in self.props:
            self.props[pid] = PropTrack({"id": pid, "type": e.get("type", pid)})
        pt = self.props[pid]
        if pt.vtype:
            return self._vehicle_move(pid, e, start)
        s, _ = pt.at(start)
        if s[0] == "rest":
            x0, y0 = s[1], s[2]
        elif s[0] == "held" and s[1] in self.tracks:
            x0, y0 = self.tracks[s[1]].x_at(start), 150.0
        else:
            x0, y0 = pt.pos(start)[:2]
        to = e.get("to", e.get("move"))
        x1 = self._resolve_x(to, None, start, x0) if not isinstance(to, (list, tuple)) else float(to[0])
        y1 = float(to[1]) if isinstance(to, (list, tuple)) and len(to) > 1 else float(e.get("y", 0))
        dur = float(e.get("duration", 1.0))
        pt.add(start, ("move", x0, y0, x1, y1, dur, float(e.get("arc", 0))))
        pt.add(start + dur, ("rest", x1, y1))
        return start + dur

    # ------------------------------------------------------------------ what the ground is made of
    SURFACE_WORDS = (("water", ("sea", "lake", "river", "pond", "ocean")),
                     ("snow", ("snow", "ice", "himalaya")),
                     ("sand", ("beach", "desert", "sand", "dune")),
                     ("road", ("street", "road", "city", "market", "station", "highway", "town", "parking")),
                     ("stone", ("palace", "temple", "castle", "cave", "fort", "mahal", "mountain", "rock", "ghat")),
                     ("wood", ("room", "classroom", "office", "kitchen", "bedroom", "restaurant", "hospital", "house",
                               "home", "hall", "library", "shop")),
                     ("grass", ("jungle", "forest", "park", "garden", "zoo", "hill", "meadow", "lawn", "cricket",
                                "school_ground", "valley")),
                     ("dirt", ("village", "farm", "field", "gaon", "rural", "mela", "fair", "dhaba", "camp")))
    IMPACT = {"dirt": ("dust", "thud"), "sand": ("sand_puff", "thud"), "grass": ("grass_burst", "thud"),
              "water": ("splash", "splash"), "snow": ("snow_puff", "thud"), "mud": ("mud_splat", "plop"),
              "road": ("stone_chips", "thud"), "stone": ("stone_chips", "knock"), "wood": (None, "thud"),
              "tiles": (None, "thud")}

    def surface_at(self, x, z=0.0):
        """What the ground is at (x, z): dirt, grass, sand, water, snow, road, stone, wood, mud."""
        try:
            if self._is_water(x, z):
                return "water"
        except Exception:
            pass
        try:
            for rd in self._roads():
                pts, half = rd["pts"], rd["half"]
                for (ax, az), (bx, bz) in zip(pts, pts[1:]):
                    dx, dz = bx - ax, (bz - az) * ZK * 2.5
                    L2 = dx * dx + dz * dz
                    u = 0.0 if L2 < 1e-9 else clamp(((x - ax) * dx + (z - az) * ZK * 2.5 * dz) / L2, 0, 1)
                    if math.hypot(x - (ax + dx * u), (z - az) * ZK * 2.5 - dz * u) < half:
                        name = str(rd.get("name", "")).lower()
                        return "road" if any(w in name for w in ("road", "street", "highway")) else "dirt"
        except Exception:
            pass
        bg = self.bg
        kind = None
        weather = str(getattr(bg, "weather", "") or "").lower()
        g = getattr(bg, "ground", None)
        if g:
            from .background import GROUNDS
            kind = {v: k for k, v in GROUNDS.items()}.get(g)
            kind = {"dark_grass": "grass", "tiles": "tiles"}.get(kind, kind)
        if kind is None:
            spec = getattr(bg, "spec", {}) or {}
            name = f"{spec.get('preset', '')} {getattr(bg, 'preset', '')} {spec.get('place', '')}".lower()
            for k_, words in self.SURFACE_WORDS:
                if k_ == "water":
                    continue
                if any(w in name for w in words):
                    kind = k_
                    break
        kind = kind or "grass"
        if kind == "dirt" and "rain" in weather:
            kind = "mud"
        return kind

    def _impact(self, t, who=None, x=None, z=0.0, size=1.0, sound=False):
        """Something lands (a jump, a fall, a dropped thing): the right puff for the ground and its sound."""
        if who is not None and who in self.tracks:
            tr = self.tracks[who]
            x, z = tr.x_at(t), tr.z_at(t)
        if x is None:
            return
        surf = self.surface_at(x, z)
        fx, snd = self.IMPACT.get(surf, ("dust", "thud"))
        if fx:
            d = dict(start=t, kind=fx, dur=0.8, intensity=clamp(size, 0.3, 2.0))
            if who is not None:
                d["who"] = who
            else:
                d.update(x=x, y=0.0, who=None, z=z)
            self.effects.append(d)
        if sound and snd:
            self.sfx.append((t, snd, 0.5 * clamp(size, 0.3, 1.5), who))
        return surf

    def _effect(self, e, start):
        kind = str(e.get("effect")).lower()
        who = e.get("who") or e.get("at_who") or e.get("target")
        from . import particles
        dflt = {"fireworks": 4.0, "anaar": 4.0, "phuljhadi": 4.0, "chakri": 3.0, "holi": 3.0, "fountain": 6.0,
                "dust_trail": 4.0, "petals": 2.5}.get(kind, 2.0)
        d = dict(start=start, kind=kind, dur=float(e.get("duration", dflt)), who=who if who in self.tracks else None,
                 x=e.get("x"), y=float(e.get("y", 0)), intensity=float(e.get("intensity", 1.0)))
        fol = e.get("follow") or (who if who in self.props else None)
        if fol in self.props:
            d["follow"] = fol
            d["z"] = self.props[fol].z_at(start)
        if d["who"] is None and d["x"] is None and "follow" not in d:
            d["x"] = self.world_w / 2
        if "z" in e:
            d["z"] = parse_z(e["z"]) if isinstance(e["z"], str) else float(e["z"])
        psnd = particles.SOUND.get({"firework": "fireworks"}.get(kind, kind))
        if psnd:
            n_ = max(1, int(round(3 * d["intensity"]))) if kind in ("fireworks", "firework", "patakhe") else 1
            for j in range(n_):
                self.sfx.append((start + j * max(0.35, d["dur"] / n_) * 0.8, psnd, 0.6, who))
        if isinstance(d["x"], str):
            d["x"] = self._resolve_x(d["x"], None, start, self.world_w / 2)
        self.effects.append(d)
        snd = {"explosion": "boom", "sparks": "zap", "rocks": "rumble", "splash": "splash", "fire": None, "magic": "magic", "sparkle": "magic",
               "confetti": "pop", "smoke": None, "hearts": "ding", "lightning": "thunder"}.get(kind)
        if snd:
            self.sfx.append((start, snd, 0.6, who))

    # ------------------------------------------------------------------ crowds
    def _build_crowd(self, crowd_fn):
        spec = self.spec["crowd"]
        if isinstance(spec, (int, float)):
            spec = {"count": int(spec)}
        n = int(spec.get("count", 8))
        lo, hi = spec.get("range", spec.get("x", [150, self.world_w - 150]))
        mode = str(spec.get("action", spec.get("mode", "mixed"))).lower()
        rng = random.Random(self.index * 977 + n)
        for i in range(n):
            cdef = crowd_fn(i, rng, spec)
            x = lo + (hi - lo) * (i + rng.uniform(0.1, 0.9)) / n
            facing = rng.choice([-1, 1])
            zr = spec.get("depth", spec.get("z", [200, 750] if self.depth else None))
            z = rng.uniform(float(zr[0]), float(zr[1])) if isinstance(zr, (list, tuple)) else parse_z(zr)
            tr = CharTrack(cdef, x, facing, scene=self, crowd=True, z=z)
            m = mode if mode != "mixed" else rng.choice(["idle", "idle", "talk", "walk", "cheer"])
            t = rng.uniform(0, 1.5)
            if m == "walk":
                cx = x
                while t < self.duration:
                    tx = rng.uniform(lo, hi)
                    d = abs(tx - cx) / 150.0
                    tr.segments.append(Segment("walk", tr.actions["walk"], t, max(d, 0.5), cx, tx,
                                               1 if tx > cx else -1, {}))
                    t += d + rng.uniform(1.0, 3.0)
                    cx = tx
            elif m in ("cheer", "clap", "celebrate", "dance", "talk", "wave", "laugh", "sit"):
                name = {"cheer": "celebrate"}.get(m, m)
                aname, _ = tr.resolve(name)
                tr.segments.append(Segment(aname, tr.actions[aname], t, self.duration, x, x, facing, {}))
            self.crowd.append(tr)


def expand_see(events):
    """{"who": "ramu", "see": "tiger"} -> the film pattern: Ramu's face, what he sees through his eyes (a real
    point-of-view shot on the 3D page), then his face again with the reaction ("do", "emotion", "say", "icon")."""
    out = []
    for e in events:
        if not (isinstance(e, dict) and e.get("see") and (e.get("who") or e.get("character"))):
            out.append(e)
            continue
        who, tgt = e.get("who") or e.get("character"), e["see"]
        first = {"who": who, "facing": tgt}
        for k in ("at", "with", "after"):
            if k in e:
                first[k] = e[k]
        react = {"who": who, "do": e.get("do", "surprised"), "emotion": e.get("emotion", "surprised")}
        for k in ("say", "icon", "sfx"):
            if k in e:
                react[k] = e[k]
        out += [first,
                {"camera": "closeup", "target": who, "cut": True, "with": "prev"},
                {"wait": float(e.get("before", 0.9))},
                {"camera": "pov", "target": who, "look_at": tgt, "cut": True,
                 **({"degrees": e["degrees"]} if "degrees" in e else {})},
                {"wait": float(e.get("duration", 2.4))},
                {"camera": "closeup", "target": who, "cut": True},
                react]
    return out
