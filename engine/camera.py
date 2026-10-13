"""Camera engine: framing, moves and cinematic shots.

Commands come from scene events (or from the auto-director, engine/director.py), e.g.
  {"camera": "wide"}  {"camera": "auto"}  {"camera": "follow", "target": "ravi", "zoom": 1.3}
  {"camera": "closeup", "target": "maya"}   {"camera": "medium", "target": "maya"}
  {"camera": "push_in", "target": "ravi"}   {"camera": "pull_back"}   {"camera": "pan", "x": 2200}
  {"camera": "over_shoulder", "target": "ravi", "look_at": "maya"}   (ravi's shoulder, maya's face)
  {"camera": "shake"}  {"camera": "punch"}  {"camera": "zoom_pulse"}
Cinematic moves (True 2.5D mode moves a real camera; the normal look gets the nearest equivalent):
  track       camera travels sideways WITH the subject (the foreground slides past)
  lead        camera backs away in front of someone walking toward it
  crane_up    rises and looks down (endings)      crane_down / establishing   comes down into the scene
  low_angle   camera near the ground looking up (heroes, tigers)   high_angle  looking down (small, lost)
  tilt_up     starts at the ground and tilts up (reveals)          tilt_down
  arc         swings around the subject (it stays centred, the world turns behind it)
  whip        very fast pan to a new subject (motion blur)
  dutch       tilted horizon (tension)             rack_focus  focus moves to "target", framing stays
  pov         through the eyes of "target"         reverse     over-the-shoulder from the other side
  inside      riding inside a vehicle ("target": "bus1")
Film-style shots (ideas from film grammar, Unity Cinemachine, Blender Camera Shakify and "trauma" shake):
  extreme_wide  the whole world, people tiny (openings, loneliness)      dark_wide   same, darker + vignette (night, fear)
  slow_pan      slow travel sideways across the scene ("direction": "left|right", "distance": 700, or "to": x/id)
  pan_left / pan_right                                                     slow_push / slow_pull   6-7 s creeping dolly
  long_lens     telephoto: camera far back, zoomed in - flat background, soft focus (3D mode)
  handheld_follow   follows the subject like a person walking with the camera
  dolly_zoom    "vertigo": the subject stays the same size while the world stretches behind (3D mode)
  face          3D: a tight face close-up (head only - the faces' acting)  crash_zoom    very fast zoom into a face (comedy / shock)          extreme_closeup   eyes / mouth fill the frame
  insert        close-up of an object ("target": "<object id>")     full_shot / medium_wide / medium_closeup
  drone         high aerial shot that glides over the place          overhead    straight down from above
  pedestal_up / pedestal_down   camera rises / sinks without tilting   static_wide  locked-off wide, no drift
Options on any move: "zoom", "duration", "cut": true, "focus_blur": true, "drift": "in|out|left|right|up",
"roll": 5 (degrees), "height": -150 (camera up/down), "focus": "<id>", "dark": 0.4 (darker picture + vignette),
"letterbox": true (black cinema bars), "lens": 2.5 (1 = normal, bigger = telephoto, smaller = wide-angle; 3D mode),
"handheld": 1.0 or "walk|run|breathe|vehicle|drone" (camera held by a person), "frame": "left|right" (put the
subject on a third of the frame, looking into the space).
Shakes: shake, punch, impact, zoom_pulse, earthquake, explosion, rumble, vehicle, heartbeat ("intensity", "duration").
"""
import math

from .background import Camera
from .util import clamp, lerp, ease
from .depth import p_of_z, lift_of_p

ZOOM3D = {"face": 6.2, "closeup": 3.6, "close": 3.6, "focus": 2.6, "medium": 2.4, "low_angle": 2.3, "high_angle": 1.4,
          "dutch": 1.7}
DEFAULT_ZOOM = {"face": 2.6, "closeup": 1.85, "close": 1.85, "focus": 1.45, "follow": None, "medium": 1.35}
FX = ("shake", "punch", "impact", "pulse", "zoom_pulse", "earthquake", "explosion", "rumble", "vehicle", "heartbeat")
FX_DUR = {"shake": 0.6, "earthquake": 3.5, "explosion": 1.2, "rumble": 2.5, "vehicle": 4.0, "heartbeat": 1.6}
ALIASES = {"dolly_in": "push_in", "push": "push_in", "dolly_out": "pull_back", "reveal": "pull_back",
           "ots": "over_shoulder", "overshoulder": "over_shoulder", "truck": "track", "tracking": "track",
           "dolly_side": "track", "side_track": "track", "leading": "lead", "walk_and_talk": "lead",
           "crane": "crane_up", "jib_up": "crane_up", "jib_down": "crane_down", "establish": "establishing",
           "establishing_shot": "establishing", "orbit": "arc", "whip_pan": "whip", "swish": "whip",
           "dutch_angle": "dutch", "tilted": "dutch", "rack": "rack_focus", "focus_pull": "rack_focus",
           "point_of_view": "pov", "reverse_angle": "reverse", "reverse_shot": "reverse", "interior": "inside",
           "in_vehicle": "inside", "low": "low_angle", "worm": "low_angle", "high": "high_angle",
           "birds_eye": "high_angle", "two_shot": "medium", "mid": "medium", "close_up": "closeup",
           "long": "wide", "long_shot": "wide", "master": "wide",
           "ews": "extreme_wide", "extreme_long_shot": "extreme_wide", "extreme_wide_shot": "extreme_wide",
           "very_wide": "extreme_wide", "vista": "extreme_wide", "landscape": "extreme_wide",
           "face_closeup": "face", "face_shot": "face", "tight_closeup": "face", "ecu": "extreme_closeup", "extreme_close_up": "extreme_closeup", "big_closeup": "extreme_closeup",
           "dark_wide_shot": "dark_wide", "night_wide": "dark_wide", "moody_wide": "dark_wide",
           "slow_pan_left": "pan_left", "slow_pan_right": "pan_right", "pan_across": "slow_pan", "panorama": "slow_pan",
           "slow_dolly_in": "slow_push", "slow_push_in": "slow_push", "creep_in": "slow_push", "slow_zoom": "slow_push",
           "slow_zoom_in": "slow_push", "slow_dolly_out": "slow_pull", "slow_pull_back": "slow_pull",
           "slow_zoom_out": "slow_pull", "zoom_in": "push_in", "zoom_out": "pull_back",
           "telephoto": "long_lens", "long_lens_shot": "long_lens", "compressed": "long_lens",
           "handheld": "handheld_follow", "shaky_follow": "handheld_follow", "follow_handheld": "handheld_follow",
           "documentary": "handheld_follow", "vertigo": "dolly_zoom", "zolly": "dolly_zoom", "contra_zoom": "dolly_zoom",
           "snap_zoom": "crash_zoom", "smash_zoom": "crash_zoom", "quick_zoom": "crash_zoom",
           "aerial": "drone", "flyover": "drone", "fly_over": "drone", "drone_shot": "drone", "helicopter": "drone",
           "top_down": "overhead", "top_shot": "overhead", "god_view": "overhead", "gods_eye": "overhead",
           "boom_up": "pedestal_up", "rise": "pedestal_up", "boom_down": "pedestal_down", "sink": "pedestal_down",
           "full": "full_shot", "full_body": "full_shot", "cowboy": "medium_wide", "cowboy_shot": "medium_wide",
           "american_shot": "medium_wide", "medium_close": "medium_closeup", "mcu": "medium_closeup",
           "locked": "static_wide", "locked_off": "static_wide", "tripod": "static_wide",
           "object_closeup": "insert", "insert_shot": "insert", "detail": "insert",
           "quake": "earthquake", "blast": "explosion", "boom": "explosion", "rumbling": "rumble",
           "bumpy": "vehicle", "car_ride": "vehicle", "heart_beat": "heartbeat",
           "orbit_360": "spin", "360": "spin", "turntable": "spin", "circle_around": "spin", "full_orbit": "spin",
           "pov_pan": "look_around", "look_round": "look_around", "scan": "look_around", "eyes": "pov",
           "first_person": "pov", "through_eyes": "pov", "eye_view": "pov"}
MOVES = ("auto", "wide", "follow", "face", "closeup", "close", "focus", "medium", "pan", "zoom", "static", "push_in",
         "pull_back", "over_shoulder", "track", "lead", "crane_up", "crane_down", "establishing", "low_angle",
         "high_angle", "tilt_up", "tilt_down", "arc", "whip", "dutch", "pov", "reverse", "inside",
         "extreme_wide", "dark_wide", "slow_pan", "pan_left", "pan_right", "slow_push", "slow_pull", "long_lens",
         "handheld_follow", "dolly_zoom", "crash_zoom", "extreme_closeup", "insert", "full_shot", "medium_wide",
         "medium_closeup", "drone", "overhead", "pedestal_up", "pedestal_down", "static_wide", "spin",
         "look_around")
EX0 = {"dh": 0.0, "aim": 0.0, "tilt": 0.0, "arc": 0.0, "roll": 0.0, "lens": 1.0, "dim": 0.0, "bars": 0.0,
       "orb": 0.0, "yaw": 0.0}
PANS = ("slow_pan", "pan_left", "pan_right", "drone")
FILM = ("extreme_wide", "dark_wide", "static_wide", "slow_pan", "pan_left", "pan_right", "drone", "slow_push",
        "slow_pull", "pedestal_up", "pedestal_down", "overhead", "long_lens", "handheld_follow", "dolly_zoom",
        "crash_zoom", "extreme_closeup", "insert", "full_shot", "medium_wide", "medium_closeup")
FILM_DUR = {"slow_pan": 6.0, "pan_left": 6.0, "pan_right": 6.0, "drone": 8.0, "slow_push": 7.0, "slow_pull": 7.0,
            "dolly_zoom": 3.5, "crash_zoom": 0.28, "pedestal_up": 4.0, "pedestal_down": 4.0, "extreme_wide": 2.0,
            "dark_wide": 2.0, "overhead": 3.0, "long_lens": 1.2, "extreme_closeup": 0.9, "insert": 0.9}
# trauma shakes: (px, roll degrees, noise speed, "decay" | "hold")
TRAUMA = {"earthquake": (26.0, 2.2, 9.0, "hold"), "explosion": (34.0, 3.0, 24.0, "decay"),
          "rumble": (7.0, 0.4, 14.0, "hold")}
TAU_ = 2 * math.pi
# default zoom of the framing shots (on top of DEFAULT_ZOOM)
SHOT_ZOOM = {"extreme_closeup": 3.5, "insert": 2.5, "full_shot": 1.12, "medium_wide": 1.22, "medium_closeup": 1.62,
             "long_lens": 1.4, "dolly_zoom": 1.4, "crash_zoom": 2.3, "handheld_follow": None}
# handheld styles (after Blender "Camera Shakify" presets): (sway px, bob px, bob Hz, roll deg, speed)
HANDHELD = {"breathe": (5.0, 3.5, 0.0, 0.35, 1.0), "walk": (7.0, 5.0, 1.9, 0.6, 1.2),
            "run": (10.0, 9.0, 2.9, 1.1, 1.8), "vehicle": (3.0, 3.0, 7.5, 0.25, 2.6),
            "drone": (14.0, 8.0, 0.0, 0.5, 0.35), "investigation": (6.0, 4.0, 0.0, 0.5, 0.7)}


SUBJECT_SHOTS = ("closeup", "close", "focus", "medium", "over_shoulder", "push_in", "slow_push", "low_angle",
                 "high_angle", "dutch", "extreme_closeup", "medium_closeup", "insert", "crash_zoom", "long_lens",
                 "full_shot", "medium_wide", "arc", "spin", "whip")


def cy_for_zoom(z):
    if z <= 1.0:
        return 345.0 / max(z, 0.3)
    return max(165.0, 345.0 - (z - 1.0) * 170.0)


def _noise(t, seed=0.0):
    """Smooth handheld wobble in -1..1."""
    return (math.sin(t * 1.31 + seed) * 0.5 + math.sin(t * 2.73 + 1.7 + seed * 2) * 0.3 +
            math.sin(t * 0.57 + 4.1 + seed * 3) * 0.2)


def _smooth_damp(cur, target, vel, smooth_time, dt):
    """Critically damped spring toward target (Unity SmoothDamp): -> (new value, new velocity)."""
    st = max(1e-4, smooth_time)
    om = 2.0 / st
    x = om * dt
    e = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
    ch = cur - target
    tmp = (vel + om * ch) * dt
    vel = (vel - om * tmp) * e
    return target + (ch + tmp) * e, vel


class CameraDirector:
    def __init__(self, tl, fps, world_w, handheld=None):
        self.tl, self.fps, self.world_w = tl, fps, world_w
        self._yhint = None
        from .cinema import is_feature
        self.feature = bool(getattr(tl, "mode3d", False)) and is_feature(getattr(tl, "cinema", None))
        self._dsub = 0.0
        self._start_z = 1.0
        self._ex = dict(EX0)
        self._rev = self._pov = self._inside = None
        self._look = None
        self.mode3d = bool(getattr(tl, "mode3d", False))
        hh = handheld if handheld is not None else getattr(tl, "handheld", 0.0)
        self.handheld = float(hh or 0.0)
        cmds = sorted(tl.camera, key=lambda c: c[0])
        self.moves, self.shakes, self.racks = [], [], []
        for t, c in cmds:
            c["type"] = ALIASES.get(c["type"], c["type"])
            if c["type"] in FX:
                self.shakes.append((t, c))
            elif c["type"] == "rack_focus":
                self.racks.append((t, c))
            else:
                if c["type"] not in MOVES:
                    tl.warn(f"scene {tl.index + 1}: unknown camera '{c['type']}', using 'auto'")
                    c["type"] = "auto"
                self.moves.append((t, c))

    # ------------------------------------------------------------------ where things are
    def _zmap(self, z):
        return clamp(2.0 * self._rev - z, 0.0, 3000.0) if self._rev is not None else z

    def _where(self, cid, t):
        """(x, z) of a character, vehicle or object."""
        tr = self.tl.tracks.get(cid)
        if tr is not None:
            return tr.x_at(t), tr.z_at(t)
        pr = self.tl.props.get(cid) if cid else None
        if pr is not None:
            s, _ = pr.at(t)
            if s[0] == "held" and s[1] in self.tl.tracks:
                h = self.tl.tracks[s[1]]
                return h.x_at(t), h.z_at(t)
            return pr.pos(t)[0], pr.z_at(t)
        return None

    def _char_x(self, cid, t):
        """Camera x that puts the character in the middle of the screen (accounts for its depth layer)."""
        w = self._where(cid, t)
        if w is None:
            return None
        x, z = w
        if getattr(self.tl, "room3d", False):
            return x                                  # rooms: x is the real position across the room
        p = self._pz(self._zmap(z))
        if p >= 0.999:
            return x
        anchor = self.world_w / 2.0 if self.mode3d else 960.0
        return (x - (1.0 - p) * anchor) / p

    def _pz(self, z):
        if self.mode3d:
            from .world3d import p3
            return p3(z)
        return p_of_z(z)

    def _subject(self, cid, t):
        """3D mode: the dolly is measured from this character's depth."""
        w = self._where(cid, t) if cid else None
        if w is not None:
            self._dsub = self._zmap(w[1])

    def _char_p(self, cid, t):
        w = self._where(cid, t)
        return p_of_z(w[1]) if w else 1.0

    def _y_for(self, cid, t, zoom):
        """Camera y that frames a (possibly deep) character like a front one at the same apparent zoom."""
        w = self._where(cid, t)
        if not w or self.mode3d:
            return None
        p = p_of_z(w[1])
        if p >= 0.999:
            return None
        zeff = 1.0 + (zoom - 1.0) * p
        target = lift_of_p(p) + cy_for_zoom(zeff) * min(1.0, 0.55 + 0.45 * p)
        return (target - (1.0 - p) * 345.0) / p

    def _auto(self, t, cur):
        tl = self.tl
        xs = []
        for cid, tr in tl.tracks.items():
            if tl._visible(cid, t):
                x = self._char_x(cid, t)
                if -150 < x < self.world_w + 150:
                    xs.append(x)
        for pid, pr in tl.props.items():                     # a car / bus driving through is part of the shot
            if pr.vtype and pr.moving(t):
                x = self._char_x(pid, t)
                if x is not None and -150 < x < self.world_w + 150:
                    xs.append(x)
        if not xs:
            return self.world_w / 2, 1.0
        mean = sum(xs) / len(xs)
        spread = max(xs) - min(xs)
        z = clamp(1900.0 / (spread + 560.0), 1.05, 1.6)
        speaker = None
        for sp in tl.speeches:
            if sp.start <= t < sp.end and sp.who in tl.tracks:
                speaker = self._char_x(sp.who, t)
                break
        if speaker is not None:
            mean = 0.65 * mean + 0.35 * speaker
            z += 0.08
        return mean, z

    def _depth_zoom(self, cid, t, zz):
        """Zoom needed so a character at depth looks as big as the requested zoom on a front character."""
        if self.mode3d:
            return zz                     # a real dolly: the camera moves to the subject instead
        p = self._char_p(cid, t)
        return clamp(1.0 + (zz - 1.0) / max(p, 0.3) + (1.0 - p) * 0.9, 0.5, 4.0) if p < 0.999 else zz

    def _kid(self, cid, zz):
        tr = self.tl.tracks.get(cid)
        return zz / max(tr.cdef.scale, 0.5) ** 0.8 if tr is not None else zz

    def _moving(self, cid, t):
        tr = self.tl.tracks.get(cid)
        if tr is None:
            pr = self.tl.props.get(cid)
            return (1 if pr.pos(t + 0.1)[0] >= pr.pos(t)[0] else -1) if pr is not None and pr.moving(t) else 0
        i = tr.seg_index(t)
        if i >= 0 and tr.segments[i].spec.moving and t < tr.segments[i].end:
            return tr.segments[i].facing
        m = tr.mounted_at(t)
        if m is not None:
            return self._moving(m.cdef.id, t)
        return 0

    def _lead(self, cid, t, secs=0.4, most=260.0):
        """Screen room ahead of a moving subject (world units): its speed x a short time, smoothed."""
        a, b = self._char_x(cid, t - 0.25), self._char_x(cid, t + 0.25)
        if a is None or b is None:
            return 0.0
        return clamp((b - a) / 0.5 * secs, -most, most)

    # ------------------------------------------------------------------ seeing round things (3D)
    def _occluders(self):
        """Tall solid things (tree trunks, huts, pillars, walls) as world rectangles [X0, X1, Z0, Z1]."""
        if getattr(self, "_occ", None) is not None:
            return self._occ
        self._occ = []
        if not self.mode3d:
            return self._occ
        try:
            from . import objects, images
            from .world3d import Z_of_z, p3, X_of
            W2 = self.world_w / 2.0
            for pid, o in self.tl.props.items():
                if o.vtype or not objects.is_object(o):
                    continue
                st, _ = o.at(0.0)
                if st[0] != "rest" or float(o.spec.get("y") or 0.0) > 60:
                    continue
                img = objects._image_name(o)
                meta = (images.info(img) or {}) if img else {}
                fp = meta.get("foot")
                h = float(meta.get("height") or 0.0)
                if not fp or h < 200 or meta.get("walk"):      # low things (a bush, a stone) never hide a face
                    continue
                h_draw = objects.size(o)[1]
                sc = h_draw / max(1.0, h)
                zc = o.z_at(0.0)
                Xc, Zc = X_of(st[1], p3(zc), W2), Z_of_z(zc)
                for f_ in (meta.get("feet") or [fp]):
                    self._occ.append((pid, Xc + f_[0] * sc, Xc + f_[1] * sc, Zc + f_[2] * sc, Zc + f_[3] * sc))
        except Exception:                                   # noqa: BLE001 - only an improvement, never a failure
            self._occ = []
        return self._occ

    def _clear_angle(self, cid, t, zoom, prev=0.0):
        """3D: the smallest orbit angle (radians) round the subject that sees it with nothing solid in between -
        a speaker behind a tree trunk or a pillar: the camera steps round it. 0.0 = already clear."""
        occ = self._occluders()
        if not occ or not cid:
            return 0.0
        if cid in self.tl.tracks and not self.tl._visible(cid, t):
            return 0.0                                      # hidden inside a house: nothing to see round
        w = self._where(cid, t)
        if w is None:
            return 0.0
        from .world3d import Z_of_z, p3, X_of
        from .scene3d import FOCAL
        sx, sz = w
        Xs, Zs = X_of(sx, p3(sz), self.world_w / 2.0), Z_of_z(sz)
        ds = max(150.0, FOCAL / max(zoom, 0.3))

        def clear(a):
            cx, cz = Xs + ds * math.sin(a), Zs - ds * math.cos(a)
            for _pid, x0, x1, z0, z1 in occ:
                if z0 > Zs - 20 or z1 < cz:                 # behind the subject / behind the camera
                    continue
                for k in range(1, 20):                      # walk the line of sight
                    u = k / 20.0
                    px, pz = cx + (Xs - cx) * u, cz + (Zs - cz) * u
                    if pz > Zs - 25:
                        break
                    if x0 - 15 < px < x1 + 15 and z0 - 15 < pz < z1 + 15:
                        return False
            return True
        if clear(0.0):
            return 0.0                                      # straight on whenever it can
        if abs(prev) > 1e-3 and clear(prev):
            return prev                                     # keep the same side (no flip-flopping)
        for deg in (8, 14, 20, 27, 34):
            for sgn in ((1, -1) if prev >= 0 else (-1, 1)):
                a = math.radians(deg * sgn)
                if clear(a):
                    return a
        return 0.0

    # ------------------------------------------------------------------ one command -> desired framing
    def _desired(self, cmd, t, cur):
        self._yhint = None
        self._dsub = 0.0
        self._ex = dict(EX0)
        self._rev = self._pov = self._inside = None
        self._look = None
        typ = cmd["type"]
        tgt = cmd.get("target") or cmd.get("who")
        other = cmd.get("look_at") or cmd.get("at")
        z = cmd.get("zoom")
        if typ == "reverse" or (typ == "over_shoulder" and cmd.get("reverse")):
            if self.mode3d and tgt and other and self._where(tgt, t) and self._where(other, t):
                self._rev = (self._where(tgt, t)[1] + self._where(other, t)[1]) / 2.0
            typ = "over_shoulder"
        if self.mode3d and typ in ("push_in", "follow", "closeup", "close", "focus", "medium", "over_shoulder",
                                   "track", "lead", "low_angle", "high_angle", "arc", "dutch", "whip", "tilt_up",
                                   "tilt_down", "crane_up", "long_lens", "handheld_follow", "dolly_zoom",
                                   "crash_zoom", "extreme_closeup", "insert", "full_shot", "medium_wide",
                                   "medium_closeup", "slow_push", "pedestal_up", "pedestal_down", "overhead",
                                   "spin"):
            self._subject(tgt, t)
        elif self.mode3d and typ == "zoom" and isinstance(cmd.get("target", cmd.get("x")), str):
            self._subject(cmd.get("target", cmd.get("x")), t)
        x, zz = self._frame(typ, cmd, t, cur, tgt, other, z)
        ex = self._ex
        self._lift = self._ground_lift(tgt, t)                # someone up a hill: the camera rises with them
        if "dark" in cmd:
            ex["dim"] = clamp(float(cmd["dark"]), 0.0, 0.9)
        if cmd.get("letterbox") or cmd.get("bars") or cmd.get("cinematic") or cmd.get("cinemascope"):
            ex["bars"] = 1.0
        if "lens" in cmd and typ != "dolly_zoom":
            ex["lens"] = clamp(float(cmd["lens"]), 0.4, 4.0)
        fr = str(cmd.get("frame", cmd.get("compose", ""))).lower()
        if fr in ("left", "left_third", "right", "right_third"):          # rule of thirds: subject on a third
            x += (1.0 if fr.startswith("left") else -1.0) * 320.0 / max(zz, 0.3)
        if "height" in cmd:
            ex["dh"] += float(cmd["height"])
        if "roll" in cmd:
            ex["roll"] = float(cmd["roll"])
        if "tilt" in cmd and typ not in ("tilt_up", "tilt_down"):
            ex["tilt"] += float(cmd["tilt"])
        if "turn" in cmd:                                  # 3D page: the camera turns its head (degrees)
            try:
                ex["yaw"] += float(cmd["turn"])
            except (TypeError, ValueError):
                pass
        if "degrees" in cmd and typ == "arc":              # 3D page: a real orbit of this many degrees
            ex["orb"] = float(cmd["degrees"]) * (1 if cmd.get("direction", "right") != "left" else -1)
        if "angle" in cmd and typ != "arc" and self.mode3d:  # a 3/4 view: the camera stands round the subject
            try:
                a = clamp(float(cmd["angle"]), -80.0, 80.0)
                ex["orb"] += a                               # 3D page: a real orbit
                ex["arc"] += a * 9.0                         # other 3D scenes: step sideways (lens shift)
            except (TypeError, ValueError):
                pass
        return x, zz

    def _frame(self, typ, cmd, t, cur, tgt, other, z):
        ex = self._ex
        if typ in FILM:
            return self._frame_film(typ, cmd, t, cur, tgt, z)
        if typ == "push_in":
            x = self._char_x(tgt, t) if tgt else None
            if x is None:
                x = float(cmd.get("x", cur.x))
            zz = float(z) if z else max(1.45, self._start_z * 1.45)
            if tgt:
                zz = self._depth_zoom(tgt, t, zz)
                self._yhint = self._y_for(tgt, t, zz)
            return x, zz
        if typ in ("pull_back", "crane_up"):
            x = cmd.get("x")
            if x is None:
                x = self._char_x(tgt, t) if (tgt and typ == "crane_up") else None
            if x is None:
                x, _ = self._auto(t, cur)
            zz = float(z) if z else clamp(1920.0 / (self.world_w + 250.0), 0.85, 1.0)
            if typ == "crane_up":
                ex.update(dh=float(cmd.get("rise", 650)), aim=1.0)
                zz = float(z) if z else 0.9
            return float(x), zz
        if typ in ("establishing", "crane_down"):
            x = self._char_x(tgt, t) if tgt else None
            if x is None:
                x = float(cmd.get("x", self._auto(t, cur)[0]))
            zz = float(z) if z else clamp(1920.0 / (self.world_w + 250.0) * 1.1, 0.95, 1.15)
            return x, zz
        if typ in ("over_shoulder",):
            xa, xb = self._char_x(tgt, t), self._char_x(other, t)
            if xa is None or xb is None:
                return (xa if xa is not None else (xb if xb is not None else cur.x)), float(z or 1.5)
            zz = float(z) if z else 1.55
            if self.mode3d and not z:
                got = self._ots3d(tgt, other, t)
                if got is not None:
                    return got
            return xb + (xa - xb) * 0.38, zz
        if typ == "auto":
            return self._auto(t, cur)
        if typ == "wide":
            zw = float(z) if z else clamp(1920.0 / (self.world_w + 250.0), 0.9, 1.0)
            x = cmd.get("x", self.world_w / 2)
            if isinstance(x, str):
                x = self._char_x(x, t) or self.world_w / 2
            return float(x), zw
        if typ in ("pov", "look_around"):
            self._look = other
            typ = "pov"
            self._pov = tgt if tgt in self.tl.tracks else None
            if self.mode3d and self._pov:
                return self._char_x(tgt, t) or cur.x, 1.0
            tgt, typ = (other or tgt), "closeup"                  # normal look: close-up on what they see
        if typ == "inside":
            if self.mode3d and tgt in self.tl.props and self.tl.props[tgt].vtype:
                self._inside = tgt
                return self._char_x(tgt, t) or cur.x, 1.0
            typ = "follow"
        if typ in ("follow", "face", "closeup", "close", "focus", "medium", "track", "lead", "low_angle", "high_angle",
                   "arc", "dutch", "whip", "tilt_up", "tilt_down", "spin"):
            x = self._char_x(tgt, t) if tgt else None
            if x is None:
                x = cur.x if typ not in ("tilt_up", "tilt_down", "arc") else self._auto(t, cur)[0]
            if tgt and typ in ("follow", "track", "handheld_follow"):
                # look-ahead: room in front of whoever moves, as much as their real speed (a car gets more than
                # a walker; none when standing) - not a jump the moment they start or stop
                x += self._lead(tgt, t) * (1.0 if typ != "track" else 0.6)
            base = {"track": 1.3, "lead": 1.25, "low_angle": 1.35, "high_angle": 1.1, "arc": 1.35, "spin": 1.2,
                    "dutch": 1.45, "whip": 1.35, "tilt_up": 1.05, "tilt_down": 1.1}.get(typ)
            zz = float(z) if z else (DEFAULT_ZOOM.get(typ) or base or cur.z)
            if self.mode3d and not z:                     # 3D figures are full bodies: real shot sizes
                zz = ZOOM3D.get(typ, zz)
            if not z and typ not in ("follow", "track", "lead", "tilt_up", "tilt_down") and tgt:
                zz = self._kid(tgt, zz)                           # kids get a tighter shot
            if tgt and typ in ("face", "closeup", "close", "focus", "medium", "low_angle", "high_angle", "dutch", "arc",
                               "whip", "spin"):
                zz = self._depth_zoom(tgt, t, zz)
                self._yhint = self._y_for(tgt, t, zz)
            if self.mode3d and tgt in self.tl.tracks and typ in ("face", "closeup", "close", "focus", "medium") and \
                    "y" not in cmd:                         # 3D: the lens at eye height, a little headroom
                cd_ = self.tl.tracks[tgt].cdef
                eye = {"human": 1.0, "quadruped": 0.5, "bird": 0.4}.get(getattr(cd_, "kind", "human"), 0.6)
                self._yhint = max(70.0, (284.0 if typ == "face" else 270.0 if typ in ("closeup", "close") else 235.0) * cd_.scale * eye)
                if self.feature:                        # feature headroom: eyes on the upper third, never a cut head
                    ex["tilt"] = ex.get("tilt", 0.0) + (0.06 if typ in ("face", "closeup", "close") else 0.03)
                else:
                    ex["tilt"] = ex.get("tilt", 0.0) - (0.07 if typ in ("face", "closeup", "close") else 0.04)
            if typ == "face" and self.mode3d and tgt in self.tl.tracks and "angle" not in cmd:
                try:                                    # a face shot from the 3/4 front (the side they face), not a profile
                    tr_ = self.tl.tracks[tgt]
                    fc = tr_.facing_at(t) or 1
                    ft = self.tl.focus_target(tgt, t) if getattr(self.tl, "auto_face", False) else None
                    if ft is not None and abs(ft - tr_.x_at(t)) > 20:      # in a talk they turn to the other person
                        fc = 1 if ft > tr_.x_at(t) else -1
                except Exception:                       # noqa: BLE001
                    fc = 1
                ex["orb"] = ex.get("orb", 0.0) + 52.0 * (1 if fc > 0 else -1)
                ex["arc"] = ex.get("arc", 0.0) + 52.0 * 9.0 * (1 if fc > 0 else -1)
            if typ == "track":
                ex.update(dh=-50.0)
            elif typ == "lead":
                ex.update(dh=-25.0)
            elif typ == "low_angle":
                k_low = 1.0                                    # how tall the subject is next to a person
                if tgt in self.tl.tracks:
                    cd_ = self.tl.tracks[tgt].cdef
                    kind_ = getattr(cd_, "kind", "human")
                    k_low = {"human": 1.0, "bird": 0.3}.get(kind_, 0.45) * max(0.3, float(getattr(cd_, "scale", 1.0) or 1.0))
                    if kind_ != "human" and getattr(cd_, "species", "") in ("elephant", "giraffe", "camel", "horse"):
                        k_low *= 1.8
                # the camera sits lower for a short subject and looks up less: a tiger is framed from near the
                # ground, not shot over (a fixed drop of a person's height aimed over animals into the trees)
                ex.update(dh=-210.0 * min(1.0, k_low), aim=1.0, tilt=0.06 * min(1.0, k_low))
            elif typ == "high_angle":
                ex.update(dh=560.0, aim=1.0)
            elif typ == "arc":
                ex.update(arc=float(cmd.get("amount", 300)) * (1 if cmd.get("direction", "right") != "left" else -1))
            elif typ == "dutch":
                ex.update(roll=float(cmd.get("roll", 7)))
            elif typ == "spin":                            # 3D page: all the way round the subject
                ex.update(orb=float(cmd.get("degrees", 360)) * (1 if cmd.get("direction", "right") != "left" else -1))
            return x + float(cmd.get("offset", 0)), zz
        if typ == "pan":
            x = cmd.get("x", cmd.get("to", cur.x))
            if isinstance(x, str):
                x = self._char_x(x, t) or (self.world_w / 2 if x == "center" else cur.x)
            return float(x), float(z) if z else cur.z
        if typ == "zoom":
            x = cmd.get("x", cmd.get("target"))
            if isinstance(x, str):
                x = self._char_x(x, t)
            return (float(x) if x is not None else cur.x), float(z or 1.3)
        if typ == "static":
            return float(cmd.get("x", cur.x)), float(z or cur.z)
        return cur.x, cur.z

    def _frame_film(self, typ, cmd, t, cur, tgt, z):
        """The film-style shots (extreme wide, slow pans, telephoto, vertigo, drone, ...)."""
        ex = self._ex
        wide_z = clamp(1920.0 / (self.world_w + 250.0), 0.9, 1.0)
        if typ in ("extreme_wide", "dark_wide", "static_wide"):
            base = {"extreme_wide": clamp(wide_z * 0.74, 0.6, 0.76), "dark_wide": wide_z * 0.94}.get(typ, wide_z)
            zw = float(z) if z else base
            x = cmd.get("x", tgt if tgt else self.world_w / 2)
            if isinstance(x, str):
                x = self._char_x(x, t) or self.world_w / 2
            if typ == "extreme_wide":
                ex["dh"] = float(cmd.get("rise", 260))
            if typ == "dark_wide":
                ex["dim"] = float(cmd.get("dark", 0.5))
            return float(x), zw
        if typ in PANS:
            if "_px" not in cmd:                          # fixed when the shot starts
                zz0 = float(z) if z else (0.85 if typ == "drone" else cur.z)
                dest = cmd.get("to", cmd.get("x"))
                if dest is None and typ != "drone":
                    dest = cmd.get("target")
                if isinstance(dest, str):
                    dest = self._char_x(dest, t) if dest not in ("center", "middle") else self.world_w / 2
                if dest is None:
                    d = str(cmd.get("direction", "left" if typ == "pan_left" else "right")).lower()
                    sign = -1.0 if d in ("left", "-1") else 1.0
                    dist = float(cmd.get("distance", 900 if typ == "drone" else 700))
                    dest = cur.x + sign * dist
                    if abs(self._clamp(dest, zz0) - cur.x) < 220 and typ not in ("pan_left", "pan_right"):
                        dest = cur.x - sign * dist                # no room that way: pan the other way
                cmd["_px"], cmd["_pz"] = float(dest), zz0
            if typ == "drone":
                ex.update(dh=float(cmd.get("rise", 950)), aim=0.55)
            return cmd["_px"], cmd["_pz"]
        if typ in ("slow_push", "slow_pull"):
            x = self._char_x(tgt, t) if tgt else None
            if x is None:
                x = float(cmd.get("x", cur.x))
            push = typ == "slow_push"
            zz = float(z) if z else self._start_z * (1.32 if push else 0.78)
            if tgt and push:
                zz = self._depth_zoom(tgt, t, zz)
                self._yhint = self._y_for(tgt, t, zz)
            return x, zz
        if typ in ("pedestal_up", "pedestal_down", "overhead"):
            x = self._char_x(tgt, t) if tgt else None
            if x is None:
                x = self._auto(t, cur)[0]
            if "_pz" not in cmd:
                cmd["_pz"] = float(z) if z else (1.0 if typ == "overhead" else cur.z)
            if typ == "overhead":
                ex.update(dh=float(cmd.get("rise", 1150)), aim=1.0)
            else:
                ex["dh"] = float(cmd.get("rise", 320)) if typ == "pedestal_up" else -140.0
            return x, cmd["_pz"]
        # framing on a subject: extreme close-up, insert, full shot, telephoto, vertigo, crash zoom, handheld
        x = self._char_x(tgt, t) if tgt else None
        if x is None:
            x = cur.x
        if typ == "handheld_follow":
            mv = self._moving(tgt, t) if tgt else 0
            return x + mv * 110 + float(cmd.get("offset", 0)), float(z) if z else 1.3
        zz = float(z) if z else SHOT_ZOOM[typ]
        if tgt and not z:
            zz = self._kid(tgt, zz)
        if tgt:
            zz = self._depth_zoom(tgt, t, zz)
            self._yhint = self._y_for(tgt, t, zz)
        if typ in ("extreme_closeup", "crash_zoom") and tgt in self.tl.tracks:
            ex["dh"] = 95.0 * self.tl.tracks[tgt].cdef.scale         # camera at eye level: the face fills it
        if typ == "long_lens":
            ex["lens"] = float(cmd.get("lens", 2.6))
        elif typ == "dolly_zoom":
            ex["lens"] = float(cmd.get("lens_to", 0.62 if str(cmd.get("direction", "in")) != "out" else 2.3))
        return x + float(cmd.get("offset", 0)), zz

    def _ground_lift(self, tgt, t):
        """How high the subject stands (hills). No target: the people on screen, on average."""
        tl = self.tl
        if not getattr(getattr(tl, "bg", None), "hills", None) and not (hasattr(tl, "_walk_list") and tl._walk_list()):
            return 0.0                                  # flat ground, nothing to climb: no lift
        ids = [tgt] if tgt in tl.tracks else [c for c in tl.tracks if tl._visible(c, t)]
        ys = []
        for cid in ids:
            try:
                ys.append(tl.tracks[cid].y_at(t))
            except Exception:
                pass
        return (sum(ys) / len(ys)) if ys else 0.0

    def _ots3d(self, shoulder, face, t):
        """True 2.5D over-the-shoulder: solve camera x + distance so the near shoulder sits big at the frame
        edge (~22% from the side) and the face at ~60%. Returns (x, zoom) with the dolly on the shoulder."""
        from .world3d import Z_of_z, FOCAL
        wa, wb = self._where(shoulder, t), self._where(face, t)
        if not wa or not wb:
            return None
        za, zb = self._zmap(wa[1]), self._zmap(wb[1])
        Za, Zb = Z_of_z(za), Z_of_z(zb)
        if Zb - Za < 120:
            return None
        Xa, Xb = self._char_x(shoulder, t), self._char_x(face, t)
        side = 1.0 if Xb >= Xa else -1.0                  # shoulder on the left when the face is to the right
        ua, ub = -0.30 * 1920 * side, 0.10 * 1920 * side
        cz = (ua * Za - ub * Zb - FOCAL * (Xa - Xb)) / (ua - ub)
        cz = clamp(cz, Za - 900.0, Za - 260.0)
        cx = Xa - ua * (Za - cz) / FOCAL
        self._dsub = za
        return cx, FOCAL / (Za - cz)

    @staticmethod
    def _from_state(cmd, st_x, st_z, ex):
        """Shots that start somewhere else (a crane down starts high, a tilt up starts at the ground)."""
        typ = cmd["type"]
        f = dict(cmd.get("_from") or {})
        if typ in ("establishing", "crane_down"):
            f.setdefault("dh", float(cmd.get("rise", 900)))
            f.setdefault("aim", 1.0)
            f.setdefault("zmul", 0.85)
        elif typ == "tilt_up":
            f.setdefault("tilt", -0.55)
        elif typ == "tilt_down":
            f.setdefault("tilt", 0.35)
        elif typ == "arc":
            f.setdefault("arc", -float(cmd.get("amount", 300)) * (1 if cmd.get("direction", "right") != "left" else -1))
        elif typ == "spin":                                # round the subject from where the camera is now
            f.setdefault("orb", 0.0)
        elif typ == "dolly_zoom":
            f.setdefault("lens", float(cmd.get("lens_from", 2.3 if str(cmd.get("direction", "in")) != "out" else 0.62)))
        elif typ == "pedestal_up":
            f.setdefault("dh", -140.0)
        elif typ == "pedestal_down":
            f.setdefault("dh", float(cmd.get("rise", 320)))
        for k in EX0:
            if k in f:
                ex[k] = float(f[k])
        if "zmul" in f:
            st_z *= float(f["zmul"])
        return st_x, st_z, bool(f)

    def _handheld_for(self, cmd, typ, t):
        """(amount, style) of the handheld feel for this shot."""
        amt, style = self.handheld, "breathe"
        if typ in ("wide", "establishing", "crane_down", "crane_up", "extreme_wide", "dark_wide", "overhead"):
            amt *= 0.6
        if typ == "handheld_follow":
            tgt = cmd.get("target") or cmd.get("who")
            mv = self._moving(tgt, t) if tgt else 0
            amt, style = max(amt, 1.2), ("walk" if mv else "investigation")
            tr = self.tl.tracks.get(tgt)
            if mv and tr is not None:
                i = tr.seg_index(t)
                if i >= 0 and tr.segments[i].action == "run":
                    style = "run"
        elif typ == "drone":
            amt, style = max(amt, 0.8), "drone"
        hh = cmd.get("handheld", cmd.get("shake_style"))
        if isinstance(hh, str) and hh.lower() in HANDHELD:
            style, amt = hh.lower(), max(amt, 1.0)
        elif isinstance(hh, bool):
            amt = 1.0 if hh else 0.0
        elif isinstance(hh, (int, float)):
            amt = float(hh)
        if typ == "static_wide" or cmd.get("locked") or cmd.get("tripod"):
            amt = 0.0
        return amt, style

    def _clamp(self, x, z):
        if getattr(self, "mode3d", False):
            # a real 3D place goes on past the stage edges (a room's own walls, the world all round): the camera
            # may centre on anyone in it - by the bed in the far corner of the room too
            return clamp(x, 0.0, self.world_w)
        half = 960.0 / z
        lo, hi = half - 200, self.world_w - half + 200
        if lo > hi:
            return self.world_w / 2
        return clamp(x, lo, hi)

    # ------------------------------------------------------------------ the whole path
    def path(self, n_frames):
        states = []
        cur = None
        cur_ex = dict(EX0)
        active_i = -2
        start_state, start_ex, start_t = None, dict(EX0), 0.0
        flags = (None, None, None)
        default = {"type": "auto"}
        slow_types = ("push_in", "pull_back", "crane_up", "crane_down", "establishing", "arc", "tilt_up",
                      "tilt_down")
        for f in range(n_frames):
            t = f / self.fps
            i = -1
            for k, (tt, _) in enumerate(self.moves):
                if tt <= t + 1e-9:
                    i = k
            cmd = self.moves[i][1] if i >= 0 else default
            ctime = self.moves[i][0] if i >= 0 else 0.0
            if cur is None:
                x, z = self._desired(cmd, t, Camera())
                cur = Camera(self._clamp(x, z), cy_for_zoom(z), z, d=self._dsub)
                cur_ex = dict(self._ex)
                active_i, start_state, start_t = i, Camera(cur.x, cur.y, cur.z, d=cur.d), t
                start_ex = dict(cur_ex)
                sx_, sz_, jumped = self._from_state(cmd, cur.x, cur.z, start_ex)
                start_state.z = sz_
                flags = (self._rev, self._pov, self._inside)
            elif i != active_i:
                active_i, start_t = i, ctime
                start_state = Camera(cur.x, cur.y, cur.z, d=cur.d)
                start_ex = dict(cur_ex)
                self._desired(cmd, t, cur)
                new_flags = (self._rev, self._pov, self._inside)
                if new_flags != flags or cmd.get("cut"):             # a cut: start from the new shot
                    dx0, dz0 = self._desired(cmd, t, cur)
                    start_state = Camera(self._clamp(dx0, dz0), cy_for_zoom(dz0), dz0, d=self._dsub)
                    start_ex = dict(self._ex)
                    flags = new_flags
                sx_, sz_, jumped = self._from_state(cmd, start_state.x, start_state.z, start_ex)
                start_state.z = sz_
            self._start_z = start_state.z
            dx, dz = self._desired(cmd, t, cur)
            typ = cmd["type"]
            slow = typ in slow_types
            dflt = 3.0 if slow else (0.35 if typ == "whip" else (0.9 if typ != "auto" else 1.2))
            if typ in ("establishing", "crane_down", "crane_up"):
                dflt = 4.0
            if typ == "arc":
                dflt = 6.0
            if typ == "spin":
                dflt = 9.0
            if typ == "look_around":
                dflt = 5.0
            dflt = FILM_DUR.get(typ, dflt)
            dur = float(cmd.get("duration", dflt))
            jump = bool(cmd.get("_from")) or typ in ("establishing", "crane_down", "tilt_up", "tilt_down", "arc", "spin", "look_around",
                                                     "dolly_zoom", "pedestal_up", "pedestal_down")
            if cmd.get("cut") and not jump:
                dur = 0.0
            el = t - start_t
            ex_t = self._ex
            if dur > 1e-6 and el < dur:
                k = ease(el / dur, cmd.get("ease", "in" if typ == "crash_zoom" else "inout"))
                lock = (cmd.get("cut") and jump) or typ == "dolly_zoom"     # vertigo: framing fixed, lens moves
                nx = dx if lock else lerp(start_state.x, dx, k)   # cut INTO a moving shot
                nz = dz if typ == "dolly_zoom" else lerp(start_state.z, dz, k)
                nd = lerp(start_state.d, self._dsub, k) if not lock else self._dsub
                ex = {kk: lerp(start_ex[kk], ex_t[kk], k) for kk in EX0}
                if self._yhint is not None:
                    self._yhint = lerp(start_state.y, self._yhint, k)
            else:
                tau = {"auto": 0.7, "follow": 0.12, "track": 0.1, "lead": 0.15, "handheld_follow": 0.16}.get(typ, 0.0)
                if tau > 0 and typ != "auto":
                    # a camera operator, not a rubber band: a critically damped spring (smooth start and stop
                    # when a car speeds up or brakes, no jolt, no overshoot)
                    nx, self._vx = _smooth_damp(cur.x, dx, getattr(self, "_vx", 0.0), tau * 2.2, 1.0 / self.fps)
                    nz, self._vz = _smooth_damp(cur.z, dz, getattr(self, "_vz", 0.0), tau * 3.0, 1.0 / self.fps)
                    a = 1 - math.exp(-1.0 / (self.fps * tau))
                    nd = lerp(cur.d, self._dsub, a)
                elif tau > 0:
                    a = 1 - math.exp(-1.0 / (self.fps * tau))
                    nx, nz = lerp(cur.x, dx, a), lerp(cur.z, dz, a)
                    nd = lerp(cur.d, self._dsub, a)
                else:
                    nx, nz, nd = dx, dz, self._dsub
                ex = dict(ex_t)
                self._vx = getattr(self, "_vx", 0.0) if tau > 0 else 0.0
                # a shot that has arrived keeps breathing: slow drift so the camera is never frozen
                drift = cmd.get("drift")
                if drift:
                    u = min(el - dur, 8.0)
                    u = u * u / (u + 1.2)                      # the move eases in (no jolt after the arrival)
                    if drift == "in":
                        nz *= 1.0 + 0.012 * u
                    elif drift == "out":
                        nz *= 1.0 - 0.01 * u
                    elif drift in ("left", "right"):
                        ex["arc"] += (22.0 if drift == "right" else -22.0) * u
                    elif drift == "up":
                        ex["dh"] += 14.0 * u
            sub_ = (cmd.get("look_at") or cmd.get("at")) if typ == "over_shoulder" else (cmd.get("target") or cmd.get("who"))
            want_a = 0.0
            if self.mode3d and not (self._pov or self._inside or self._rev is not None) and \
                    cmd.get("see_through") is not True and (typ in SUBJECT_SHOTS or typ in ("follow", "track", "lead")):
                if not sub_:                                 # no target given: whoever is talking
                    sub_ = next((sp.who for sp in self.tl.speeches if sp.start <= t < sp.end and sp.who in self.tl.tracks), None)
                want_a = self._clear_angle(sub_, t, nz, getattr(self, "_occ_a", 0.0)) if sub_ else 0.0
            elif self.mode3d and typ == "auto" and cmd.get("see_through") is not True:
                sp_ = next((sp.who for sp in self.tl.speeches if sp.start <= t < sp.end and sp.who in self.tl.tracks), None)
                want_a = self._clear_angle(sp_, t, nz, getattr(self, "_occ_a", 0.0)) if sp_ else 0.0
            k_o = 1.0 - math.exp(-1.0 / (self.fps * 0.45))           # glide round it (never a jump) -
            if (i, ) != getattr(self, "_occ_shot", None):             # but a CUT starts the new shot already clear
                if cmd.get("cut") or getattr(self, "_occ_shot", None) is None:
                    self._occ_a = want_a
                self._occ_shot = (i, )
            self._occ_a = getattr(self, "_occ_a", 0.0) + (want_a - getattr(self, "_occ_a", 0.0)) * k_o
            lift = getattr(self, "_lift", 0.0)
            a_l = 1.0 - math.exp(-1.0 / (self.fps * 0.35))          # time-based: same at any frame rate
            self._lift_s = lift if not hasattr(self, "_lift_s") else self._lift_s + (lift - self._lift_s) * a_l
            ex = dict(ex)
            ex["dh"] += self._lift_s * (1.0 if self.mode3d else 0.0)
            nz = clamp(nz, 0.5, 7.0 if self.mode3d else 4.0)
            if not (self._pov or self._inside):
                nx = self._clamp(nx, nz)
            ny = float(cmd.get("y", self._yhint if self._yhint is not None else cy_for_zoom(nz)))
            if not self.mode3d:                                        # normal look: the nearest equivalent
                ny += ex["dh"] * 0.12 - ex["tilt"] * 160.0 + self._lift_s
                nx += ex["arc"] * 0.3
            cam = Camera(nx, ny, nz, d=nd)
            cam.dh, cam.arc, cam.roll = ex["dh"], ex["arc"], ex["roll"]
            if abs(self._occ_a) > 1e-3:                               # step round the tree / pillar in the way
                from .scene3d import FOCAL as _F
                cam.arc += max(150.0, _F / max(nz, 0.3)) * math.tan(self._occ_a)
            cam.lens, cam.dim, cam.bars = ex["lens"], ex["dim"], ex["bars"]
            cam.hor, cam.aim = 0.5 + ex["tilt"], ex["aim"]
            cam.rev, cam.pov, cam.inside = self._rev, self._pov, self._inside
            cam.keep = self.feature                                    # long lens keeps the angles (3D)
            cam.orb, cam.yaw, cam.look = ex["orb"], ex["yaw"], self._look
            if typ == "look_around":                                  # eyes sweep from left to right
                amp = float(cmd.get("degrees", 70))
                u = clamp(el / max(dur, 0.5), 0.0, 1.0)
                cam.yaw += -amp * math.cos(math.pi * ease(u, "inout")) * (1 if cmd.get("direction", "right") != "left" else -1)
            foc = cmd.get("focus")
            for rt, rc in self.racks:
                if start_t - 1e-6 <= rt <= t:
                    foc = rc.get("target") or rc.get("who") or foc
                    cam.ap = float(rc.get("strength", 0.9))
            cam.foc = foc
            if typ in SUBJECT_SHOTS:                                   # who the shot is about (sharp focus)
                cam.sub = (cmd.get("look_at") or cmd.get("at")) if typ == "over_shoulder" else \
                    (cmd.get("target") or cmd.get("who"))
            else:
                cam.sub = None
            if "aperture" in cmd and not getattr(cam, "ap", 0.0):    # the lens' depth of field (cinema.py)
                try:
                    cam.ap = float(cmd["aperture"])
                except (TypeError, ValueError):
                    pass
            fg = cmd.get("foreground")
            if isinstance(fg, dict):                                   # soft foreground near the lens
                cam.fg = dict(fg, dx=(nx - start_state.x) * nz, t=el)
            if typ == "long_lens":                                     # telephoto: shallow focus
                cam.ap = max(cam.ap, float(cmd.get("blur", 0.6)))
            amt, style = self._handheld_for(cmd, typ, t)
            if amt > 0:                                                # a person holds the camera
                sway, bob, hz, rl, spd = HANDHELD[style]
                cam.sx += sway * amt * _noise(t * spd, 0.3)
                cam.sy += (0.7 * sway * _noise(t * spd * 1.1, 2.1)
                           + (bob * (abs(math.sin(math.pi * hz * t)) - 0.5) * 2.0 if hz else 0.0)) * amt
                cam.roll += rl * amt * _noise(t * spd * 0.8, 5.2)
            for st, sc in self.shakes:
                sd = float(sc.get("duration", FX_DUR.get(sc["type"], 0.35)))
                if not (st <= t < st + sd):
                    continue
                k = (t - st) / sd
                inten = float(sc.get("intensity", 1.0))
                if sc["type"] in TRAUMA:                                # "trauma" shake: strength = trauma^2
                    amp, rl, spd, shape = TRAUMA[sc["type"]]
                    if shape == "decay":
                        tr_ = 1.0 - k
                    else:                                              # hold: ease in, hold, ease out
                        tr_ = min(1.0, k / 0.12) * min(1.0, (1.0 - k) / 0.3)
                    sh = inten * tr_ * tr_
                    cam.sx += amp * sh * _noise(t * spd, 11.0 + st)
                    cam.sy += amp * sh * _noise(t * spd * 1.13, 23.0 + st)
                    cam.roll += rl * sh * _noise(t * spd * 0.7, 37.0 + st)
                    if sc["type"] == "explosion":
                        cam.z *= 1.0 + 0.07 * inten * (1.0 - k) ** 3
                    continue
                if sc["type"] == "vehicle":                            # engine buzz + road bumps
                    fade = min(1.0, k / 0.1) * min(1.0, (1.0 - k) / 0.1)
                    bump = max(0.0, math.sin(TAU_ * 0.9 * (t - st))) ** 12
                    cam.sy += inten * fade * (1.6 * math.sin(t * 95.0) + 9.0 * bump)
                    cam.roll += 0.25 * inten * fade * _noise(t * 3.0, 4.0)
                    continue
                if sc["type"] == "heartbeat":                          # lub-dub zoom pulses
                    beat = ((t - st) % 0.8) / 0.8
                    pulse = math.exp(-((beat - 0.05) / 0.04) ** 2) + 0.6 * math.exp(-((beat - 0.25) / 0.04) ** 2)
                    cam.z *= 1.0 + 0.045 * inten * pulse
                    continue
                if sc["type"] == "shake":
                    amp = 14.0 * inten * (1 - k)
                    cam.sx += amp * math.sin(t * 71.0)
                    cam.sy += amp * math.cos(t * 53.0)
                    cam.roll += 1.2 * inten * (1 - k) * math.sin(t * 37.0)
                else:   # punch / impact / zoom pulse: quick zoom-in that springs back
                    cam.z *= 1.0 + 0.14 * inten * math.sin(math.pi * k) * (1 - k * 0.5)
                    if sc["type"] in ("punch", "impact"):
                        cam.sx += 8 * inten * (1 - k) * math.sin(t * 90.0)
            if states and typ == "whip" and el < dur + 0.05:            # motion blur while whipping
                cam.blur = (nx - states[-1].x) * nz
            cur = Camera(nx, ny, nz, d=nd)
            cur_ex = ex
            states.append(cam)
        return states
