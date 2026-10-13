"""Real 3D characters and animals for the 3D page (the camera can go all the way round them).

Every person / animal is built from 3D solids (Pen3) each frame, driven by the SAME pose data as the 2D
drawings: the 2D rig gives the joints in the side plane (forward / up), the near and far limbs are put left
and right of the body, and the whole figure is turned to the way the character really faces in the world.
So every action (walk, run, sit, dance, fight, sleep, animal gaits, roar ...) works in 3D without new code.

    ON[0]     True while a full-3D scene is drawn (set by the renderer)
    HEAD      {id(track): heading (radians)} for this frame; heading 0 = facing away from the camera (+Z),
              +pi/2 = facing right (+X), pi = facing the camera
"""
import math
from .util import stable_hash
import os

from .character import solve, BONES
from .util import darker, lighter

ON = [False]
HEAD = {}
CHEAT = 0.35                   # side-facing people turn a little toward the camera (stage acting)


# ============================================================================ which way everyone faces
def _ang_mix(a, b, k):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * k


def heading_raw(tr, t, at, others):
    X1, Z1 = at(tr.x_at(t), tr.z_at(t))
    rd = tr.riding_at(t) if hasattr(tr, "riding_at") else None
    if rd is not None or (hasattr(tr, "mounted_at") and tr.mounted_at(t) is not None):
        f = 1.0 if tr.facing_at(t) >= 0 else -1.0          # riding: face the way the vehicle / animal goes
        return f * (math.pi / 2 + CHEAT)
    if tr.gait_at(t) > 0:                                   # walking: the way they walk
        X2, Z2 = at(tr.x_at(t + 0.12), tr.z_at(t + 0.12))
        if math.hypot(X2 - X1, Z2 - Z1) > 2.0:
            return math.atan2(X2 - X1, Z2 - Z1)
    cf = tr.convo_face(t) if hasattr(tr, "convo_face") else None
    if cf is not None:                                     # in a conversation: turn to the one they talk with
        Xo, Zo = at(cf.x_at(t), cf.z_at(t))
        dx, dz = Xo - X1, Zo - Z1
        if math.hypot(dx, dz) > 10.0:
            f = 1.0 if dx >= 0 else -1.0
            return _ang_mix(math.atan2(dx, dz), f * (math.pi / 2 + CHEAT), 0.25)
    v = tr.view_at(t)
    if v == "camera":
        return math.pi
    if v == "away":
        return 0.0
    f = 1.0 if tr.facing_at(t) >= 0 else -1.0
    best = None                                            # talking to someone: face them for real
    for o in others:
        if o is tr:
            continue
        Xo, Zo = at(o.x_at(t), o.z_at(t))
        dx, dz = Xo - X1, Zo - Z1
        dd = math.hypot(dx, dz)
        if dx * f > 15.0 and dd < 1600.0 and (best is None or dd < best[0]):
            best = (dd, math.atan2(dx, dz))
    side = f * (math.pi / 2 + CHEAT)
    if best is not None:
        return _ang_mix(best[1], side, 0.25)
    return side


def heading(tr, t, at, others):
    """Turns take time: a weighted average of the last 0.3 s (no snapping round)."""
    sx = sz = 0.0
    for i, w in enumerate((6, 5, 4, 3, 2, 1)):
        a = heading_raw(tr, max(0.0, t - i * 0.055), at, others)
        sx += w * math.sin(a)
        sz += w * math.cos(a)
    return math.atan2(sx, sz)


# ============================================================================ helpers
def _col(c, k=None):
    if k is None:
        return tuple(c[:3])
    return tuple(max(0.0, min(1.0, v * k)) for v in c[:3])


def _p3(p, zlat=0.0):
    """2D rig point (forward, up) -> 3D local (x forward, y up, z to the side)."""
    return (float(p[0]), float(p[1]), float(zlat))


def _hexc(v, fallback=(0.5, 0.5, 0.5)):
    if isinstance(v, (tuple, list)):
        return tuple(v[:3])
    if isinstance(v, str) and v.startswith("#") and len(v) >= 7:
        return tuple(int(v[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return fallback


IRIS = ("#3b2314", "#4a2c17", "#2a1a10", "#5a3a1c", "#3d2a1a", "#6b4a2a")


def face_look(c):
    """This person's own face (the same every frame): eye size and gap, nose, mouth, brows, iris colour.
    Picked from the character's id, so two people never share one face; "face": {"eyes": 1.2, "nose": 0.8,
    "mouth": 1.1, "brows": 1.3, "gap": 0.36, "iris": "#4a2c17"} in the story changes any of it."""
    import zlib
    h = zlib.crc32(str(getattr(c, "id", "x")).encode("utf-8"))

    def r(k, lo, hi):
        return lo + (hi - lo) * (((h >> (k * 4)) & 0xFF) / 255.0)
    age = getattr(c, "age", "")
    child = age in ("child", "toddler", "baby")
    small = age in ("toddler", "baby")                  # big eyes, a button nose, chubby cheeks, hardly a jaw
    fem = getattr(c, "gender", "") == "female"
    old = age == "old"
    shapes = ("oval", "round", "long", "square", "heart", "oval")
    look = {"eyes": r(0, 0.92, 1.1) * (1.14 if child else 1.0) * (1.04 if fem else 1.0),
            "gap": r(1, 0.31, 0.36), "nose": r(2, 0.85, 1.2) * (0.8 if child else 1.0) * (0.9 if fem else 1.0),
            "mouth": r(3, 0.88, 1.12), "brows": r(4, 0.85, 1.25) * (0.75 if fem else 1.0) * (0.8 if child else 1.0),
            "iris": IRIS[h % len(IRIS)], "lashes": fem, "wrinkles": old,
            # the sculpted head (engine/char3d.py HumanRig.skull): how strong each shape is (1 = normal)
            "jaw": r(5, 0.75, 1.2) * (0.45 if child else 1.0) * (0.8 if fem else 1.0),
            "cheek": r(6, 0.7, 1.25) * (1.35 if child else 1.0) * (0.75 if old else 1.0),
            "chin": r(7, 0.7, 1.25) * (0.5 if child else 1.0) * (0.85 if fem else 1.0),
            "brow_ridge": r(1, 0.6, 1.3) * (0.3 if child else 1.0) * (0.55 if fem else 1.0),
            "skull": r(2, 0.8, 1.2), "sag": 1.0 if old else 0.0,
            # step 2: the face shape and its parts
            "shape": "round" if small else shapes[(h >> 9) % len(shapes)],
            "nose_w": r(3, 0.82, 1.25) * (0.8 if small else 1.0), "nose_len": r(4, 0.85, 1.2) * (0.65 if small else 0.85 if child else 1.0),
            "lips": r(5, 0.7, 1.3) * (1.15 if fem else 0.9) * (0.75 if small else 1.0),
            "chubby": 1.0 if small else (0.5 if child else 0.0), "age_lines": 1.0 if old else 0.0, "small": small}
    if small:
        look.update(eyes=look["eyes"] * 1.15, nose=look["nose"] * 0.75, mouth=look["mouth"] * 0.8, brows=look["brows"] * 0.55,
                    jaw=0.2, chin=0.25, brow_ridge=0.1, cheek=1.6, skull=1.25)
    want = (getattr(c, "spec", None) or {}).get("face")
    if isinstance(want, dict):
        for k in ("eyes", "gap", "nose", "mouth", "brows", "jaw", "cheek", "chin", "brow_ridge", "skull", "nose_w", "nose_len",
                  "lips", "chubby", "jowls", "chin_len", "forehead", "ears"):
            try:
                if k in want:
                    look[k] = float(want[k])
            except (TypeError, ValueError):
                pass
        if want.get("shape") in ("oval", "round", "long", "square", "heart"):
            look["shape"] = want["shape"]
        if "age_lines" in want:
            look["age_lines"] = float(bool(want["age_lines"]))
        if isinstance(want.get("talk"), dict):                 # the person's speaking style (char3d _talk_style)
            look["talk"] = {k: float(v) for k, v in want["talk"].items() if isinstance(v, (int, float))}
        if isinstance(want.get("iris"), str):
            look["iris"] = want["iris"]
        if "lashes" in want:
            look["lashes"] = bool(want["lashes"])
    return look


def shell(pen, centre, fwd, up, R, covered, col, rings=12, sides=20):
    """Part of a ball (hair, caps): only the cells where covered(up_amount, forward_amount) is True.
    A single outer skin a little bigger than the head, so it always sorts in front of the head."""
    lat = (0.0, 0.0, 1.0)
    cx, cy, cz = centre

    def P(th, ph):
        u, sn = math.cos(th), math.sin(th)
        f, l = sn * math.cos(ph), sn * math.sin(ph)
        return (cx + R * (up[0] * u + fwd[0] * f), cy + R * (up[1] * u + fwd[1] * f), cz + R * l), u, f
    rings, sides = max(4, int(rings * pen.detail)), max(6, int(sides * pen.detail))
    for i in range(rings):
        t0, t1 = math.pi * i / rings, math.pi * (i + 1) / rings
        for j in range(sides):
            p0, p1 = 2 * math.pi * j / sides, 2 * math.pi * (j + 1) / sides
            _, um, fm = P((t0 + t1) / 2, (p0 + p1) / 2)
            if not covered(um, fm):
                continue
            pts = [P(t0, p0)[0], P(t0, p1)[0], P(t1, p1)[0], P(t1, p0)[0]]
            if i == 0:
                pts = [pts[0], pts[2], pts[3]]
            elif i == rings - 1:
                pts = pts[:3]
            vn = [tuple(v / R for v in (p[0] - cx, p[1] - cy, p[2] - cz)) for p in pts]   # smooth: a ball's normals
            f_ = pen._face_auto(pts, col, centre)
            if f_ is not None and len(vn) == len(f_.pts):
                f_.vn = [pen._dir(v) for v in vn]


# ============================================================================ the posed skeletons handed to the code
SCENE_DARK = 0.0          # 0 day .. 1 deep night - set each frame by the renderer (the pupils follow it)
FACE_EX = 1.0             # the story's exaggeration (0.6 calm .. 1.4 cartoon; 1 in pure physics) - faces follow it


class _Rig:
    """Common to every skeleton (people, animals, birds)."""

    def _face_ctl(self, mouth, blink):
        """Talking face points (from the voice + text): rig.mouth_shape, rig.brow, rig.gaze, rig.lid, rig.nod."""
        ctl = getattr(mouth, "ctl", None) or {}
        self.talk = ctl
        if "jaw" in ctl:
            self.mouth_shape = {k: float(ctl.get(k, 0.0)) for k in ("jaw", "wide", "round", "closed", "teeth", "tongue")}
        else:                                   # not talking (or old data): a simple open / shut from rig.mouth
            m = max(0.0, min(1.0, float(mouth or 0.0)))
            self.mouth_shape = {"jaw": m, "wide": 0.5, "round": 0.0, "closed": 0.0 if m > 0.06 else 1.0,
                                "teeth": 0.0, "tongue": 0.0}
        self.brow = float(ctl.get("brow", 0.0))
        self.gaze = (float(ctl.get("gx", 0.0)), float(ctl.get("gy", 0.0)))
        self.lid = float(ctl.get("lid", 1.0 if blink else 0.0))
        self.nod = float(ctl.get("nod", 0.0))
        # 👁 the pupil: wide in the dark (up to ~2x, like real eyes 2-8 mm), wider still in fear / surprise / love,
        # a little smaller in bright light; it eases (the pupil takes about a second to change)
        dark = max(0.0, min(1.0, float(SCENE_DARK)))
        emo = {"surprised": 0.25, "scared": 0.35, "afraid": 0.35, "in_love": 0.3, "shocked": 0.3, "angry": -0.1}.get(str(getattr(self, "face", "")), 0.0)
        self.pupil = max(0.7, min(1.8, 0.85 + 0.8 * dark + emo))
        self.face_ex = max(0.5, min(1.6, float(FACE_EX)))
        self.face_from = ctl.get("face_from")          # the face it is changing from ...
        self.face_k = float(ctl.get("face_k", 1.0))     # ... and how far the change has got (0..1)

    def show(self, part):
        """False when this part is hidden: rig.body(pen, hide=["hair"]) draws the normal body without its hair."""
        return str(part) not in self._hide

    @staticmethod
    def mix(a, b, f):
        """The point a fraction f of the way from a to b."""
        return tuple(a[i] + (b[i] - a[i]) * f for i in range(len(a)))

    @staticmethod
    def color(v):
        return _hexc(v)

    def body(self, pen, hide=()):
        """Draw the normal body (person_3d / quadruped_3d / bird_3d) - then add your own parts on top.
        hide = the parts to leave out, e.g. ["hair", "shoes"] (you draw your own)."""
        old = self._hide
        self._hide = set(old) | {str(h) for h in (hide or ())}
        try:
            _run_base(pen, self, self._t, self._state)
        finally:
            self._hide = old


class HumanRig(_Rig):
    def __init__(self, c, pose, face="neutral", mouth=0.0, blink=False, t=0.0, state=None):
        self._c, self._t, self._state, self._hide, self._depth = c, t, state, set(), 0
        self.kind = "human"
        self.s = s = c.scale
        from .character import KID_AGES, body_of, head_k
        self.child = c.age in KID_AGES
        self.small = c.age in ("baby", "toddler")              # babies / toddlers: their own proportions and face
        hr = BONES["head_r"] * head_k(c, toon=False)                 # (3D keeps its own shapes: no 2.5D toon)
        J = self._J = solve(pose, s, hr, body_of(c, toon=False))
        # 🫁 breathing: the chest and shoulders rise and fall a little (about every 4 s; faster and deeper after
        # running) - everything above the waist goes with them
        ph = (stable_hash(c.id) % 100) / 16.0
        brk = 1.0 + 0.8 * min(1.0, abs(float(pose.get("_speed", 0.0) or 0.0)) / 200.0)
        bb = 0.55 * s * brk * math.sin(2 * math.pi * float(t) / (3.9 / brk) + ph)
        if abs(bb) > 1e-3:
            J = self._J = dict(J)
            for k_ in ("sh", "neck", "head", "en", "hn", "ef", "hf"):
                if k_ in J:
                    p_ = J[k_]
                    J[k_] = (p_[0], p_[1] + bb) + tuple(p_[2:])
        self.K = s * c.build ** 0.4
        self.skin = _col(c.skin)
        self.top = _col(c.top) if c.top else self.skin
        self.bottom = _col(c.bottom) if c.bottom else self.skin
        self.shoes = _col(c.shoes)
        self.hair_color = _col(c.hair_color)
        self.accent = _col(c.accent)
        self.gender, self.age, self.hair, self.outfit = c.gender, c.age, c.hair, c.outfit
        self.bottom_kind, self.sleeves = c.bottom_kind, c.sleeves
        self.mustache, self.beard, self.glasses = bool(c.mustache), bool(c.beard), bool(c.glasses)
        self.hat = c.hat
        self.extras = set(getattr(c, "extras", ()) or ())     # cape, dupatta, pallu ...
        self.face, self.mouth, self.blink, self.t = face, max(0.0, min(1.0, float(mouth or 0.0))), bool(blink), t
        self._face_ctl(mouth, blink)
        self.pose = dict(pose)
        self.sw = (15.0 if c.gender == "female" else 17.0) * s * c.build ** 0.6     # half shoulder width
        self.hw = 9.0 * s * c.build ** 0.5                                         # half hip width
        self.hip, self.waist, self.chest, self.neck = (_p3(J["hip"]), _p3(J["waist"]), _p3(J["sh"]), _p3(J["neck"]))
        self.neck_top = (J["neck"][0], J["neck"][1] + 8 * s, 0.0)
        self.head = _p3(J["head"])
        self.head_r = hr * s
        a = math.radians(pose.get("rot", 0.0) - pose["torso"] - pose["head"])   # the nod of the head
        self.fwd = (math.cos(a), -math.sin(a), 0.0)
        self.up = (math.sin(a), math.cos(a), 0.0)
        self.hand_near = self.arm("near")[2]
        self.hand_far = self.arm("far")[2]
        self.look = face_look(c)
        self._talk_style()

    def _talk_style(self):
        """This person's own way of talking (like Imitator, ICCV 2023: the same words, a personal style): a big
        jaw or tight lips, wide or round, lively brows, a nodding head - "face": {"talk": {"jaw": 1.3, "wide": 0.8,
        "brow": 1.4, "nod": 1.2}}. Lips that close for M / B / P still close fully (the style never opens them)."""
        st = self.look.get("talk") or {}
        if not st:
            return
        ms = dict(self.mouth_shape)
        ms["jaw"] = max(0.0, min(1.0, ms["jaw"] * float(st.get("jaw", 1.0))))
        ms["wide"] = max(0.0, min(1.0, ms["wide"] * float(st.get("wide", 1.0))))
        ms["round"] = max(0.0, min(1.0, ms["round"] * float(st.get("round", 1.0))))
        self.mouth_shape = ms
        self.brow = self.brow * float(st.get("brow", 1.0))
        self.nod = self.nod * float(st.get("nod", 1.0))

    # ---------------------------------------------------------------- painting a face on the head
    def on_face(self, u, l, lift=0.0):
        """The point of the head's surface at u up / l to the side (head sizes, -1..1), lifted off it by lift."""
        k = 1.0 + lift
        f = math.sqrt(max(0.0, 1.0 - u * u - l * l))
        F, U, L = self.sculpt(f, u, l, sockets=False)     # on this person's own head shape (pear, long jaw ...)
        return self.on_head(F * k, U * k, L * k)

    def face_anchor(self, pen, u, l, lift=0.22):
        """An invisible point just in front of the face: everything put on it with layer() is drawn right after
        it, in order (like paint on paper), and hidden together when that side of the face turns away."""
        p = self.on_face(u, l, lift)
        hc = self.head
        n = tuple(p[i] - hc[i] for i in range(3))
        L = math.sqrt(sum(v * v for v in n)) or 1.0
        n = tuple(v / L for v in n)
        a = (0.0, 1.0, 0.0) if abs(n[1]) < 0.9 else (1.0, 0.0, 0.0)
        e1 = (n[1] * a[2] - n[2] * a[1], n[2] * a[0] - n[0] * a[2], n[0] * a[1] - n[1] * a[0])
        e2 = (n[1] * e1[2] - n[2] * e1[1], n[2] * e1[0] - n[0] * e1[2], n[0] * e1[1] - n[1] * e1[0])
        d = 0.004
        pts = [p, tuple(p[i] + e1[i] * d for i in range(3)), tuple(p[i] + e2[i] * d for i in range(3))]
        if sum(((pts[1][i] - p[i]) * (pts[2][(i + 1) % 3] - p[(i + 1) % 3]) -
                (pts[1][(i + 1) % 3] - p[(i + 1) % 3]) * (pts[2][i] - p[i])) * n[(i + 2) % 3] for i in range(3)) < 0:
            pts = [pts[0], pts[2], pts[1]]
        return pen._add(pts, n, self.skin, cull=True)

    def swing(self, p0, p1, k=1.0):
        """p1 hanging from p0, swung back (and up) by the hair / cloth follow-through (rig.drag) times k."""
        d, lf = self.drag
        a = -math.radians((0.8 * max(-35.0, min(80.0, d)) + 0.5 * lf) * k)
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        ca, sa = math.cos(a), math.sin(a)
        return (p0[0] + dx * ca - dy * sa, p0[1] + dx * sa + dy * ca, p1[2])

    @staticmethod
    def layer(pen, anchor, n0, sub):
        """Put the faces drawn since len(pen.faces) == n0 on the anchor, as paint layer `sub`."""
        for f in pen.faces[n0:]:
            f.parent, f.sub = anchor, int(sub)

    def face_patch(self, pen, ul, c, lift=0.02):
        """A flat painted shape on the face through (u, l) points."""
        pts = [self.on_face(u, l, lift) for u, l in ul]
        if len(pts) < 3:
            return None
        cu = sum(u for u, _ in ul) / len(ul)
        cl = sum(l for _, l in ul) / len(ul)
        q = self.on_face(cu, cl, 0.0)
        hc = self.head
        n = tuple(q[i] - hc[i] for i in range(3))
        L = math.sqrt(sum(v * v for v in n)) or 1.0
        return pen._add(pts, tuple(v / L for v in n), c, cull=False)

    def face_line(self, pen, ul, w, c, lift=0.03):
        """A painted line on the face through (u, l) points, w thick (head sizes)."""
        pts = [self.on_face(u, l, lift) for u, l in ul]
        if len(pts) >= 2:
            pen.tube(pts, w * self.head_r, c=c, sides=4, smooth=False, ends=False)

    def leg(self, side="near"):
        J, z = self._J, (-1.0 if side == "near" else 1.0) * self.hw
        k = ("kn", "fn", "toe_n") if side == "near" else ("kf", "ff", "toe_f")
        return _p3(J["hip"], z), _p3(J[k[0]], z), _p3(J[k[1]], z), _p3(J[k[2]], z)

    def arm(self, side="near"):
        J, sd, s = self._J, (-1.0 if side == "near" else 1.0), self.s
        k = ("en", "hn") if side == "near" else ("ef", "hf")
        return (_p3(J["sh"], sd * self.sw), _p3(J[k[0]], sd * (self.sw + 1.5 * s)), _p3(J[k[1]], sd * (self.sw + s)))

    def on_head(self, f, u, lat):
        """A point on / near the head: f forward, u up, lat to the side (in head sizes; 1 = on the surface)."""
        r, (hx, hy, _), fw, up = self.head_r, self.head, self.fwd, self.up
        return (hx + (fw[0] * f + up[0] * u) * r, hy + (fw[1] * f + up[1] * u) * r, lat * r)

    def model(self, pen, name, height=None, colors=None, bones=None, max_faces=None, two_sided=False, head=None):
        """An imported RIGGED model (GLB / glTF / Mixamo FBX with bones) moved by this skeleton: every action works.
        height = how tall (default: as tall as this character).  bones = {"hips": "Hips", ...} to fix the
        matching.  colors = {"#hex": "new colour"} like pen.model.  max_faces = how many triangles for the body
        (the head keeps all of its own unless head="simple"; far away it is simplified by itself)."""
        from .rigmodel import draw_on_rig
        return draw_on_rig(pen, self, name, height, colors, bones, max_faces, two_sided, head)

    def cap(self, pen, covered, colour, size=1.07):
        """Part of a ball round the head (hair, a cap, a helmet): covered(up, forward) -> True where it covers.
        up / forward go from -1 to 1 (up = 1 at the top, forward = 1 at the face)."""
        shell(pen, self.head, self.fwd, self.up, self.head_r * float(size), covered, colour)

    def sculpt(self, f, u, l, sockets=True):
        """A point of the round head (f forward, u up, l to the side - a unit direction) moved to the person's
        own head shape: a taller skull and its back, the jaw narrowing to the chin, cheekbones, a brow ridge,
        soft eye sockets (and cheeks that sag a little when old). Returns (f, u, l) in head sizes."""
        lk = self.look
        g = lambda x, m, w: math.exp(-((x - m) / w) ** 2)
        shape = lk.get("shape", "oval")
        if shape == "long":                             # the face shape: stretch / squash before the details
            u = u * (1.07 if u < 0 else 1.03)
            l = l * 0.95
        elif shape == "round":
            l = l * (1.05 if u < 0.3 else 1.0)
            u = u * 0.97
        F, U, Ls = f, u, l
        sk = lk.get("skull", 1.0)
        if u > 0:
            U = u * (1.0 + 0.06 * sk)
            Ls = l * (1.0 - 0.05 * u)
        if f < 0:
            F = f * (1.0 + 0.07 * sk * max(0.0, u + 0.35))
        front = max(0.0, f)
        jaw_k = lk.get("jaw", 1.0) * {"round": 0.7, "square": 0.5, "heart": 1.35, "long": 1.0}.get(shape, 1.0)
        if u < 0:                                       # the jaw narrows to the chin, the chin comes forward
            k = -u
            if shape == "square":                       # square: wide jaw corners, then a flatter chin
                Ls *= 1.0 - jaw_k * 0.28 * k ** 2.6
            else:
                Ls *= 1.0 - jaw_k * 0.28 * k ** 1.3
            F *= 1.0 - 0.1 * k * (1.0 - front)
            U -= lk.get("chin", 1.0) * 0.05 * k * k * front
            F += lk.get("chin", 1.0) * 0.08 * k * k * front ** 3
        cb = g(u, -0.06, 0.17) * g(abs(l), 0.6, 0.2) * front * (1.3 if shape == "heart" else 1.0)
        F += 0.05 * lk.get("cheek", 1.0) * cb
        ch_ = lk.get("chubby", 0.0)
        if ch_:                                          # chubby cheeks (children, toddlers, babies): low and round
            cc = g(u, -0.3, 0.17) * g(abs(l), 0.5, 0.2) * front
            F += 0.07 * ch_ * cc
            Ls += math.copysign(0.05 * ch_ * cc, l)
        Ls += math.copysign(0.03 * lk.get("cheek", 1.0) * cb, l)
        F += 0.04 * lk.get("brow_ridge", 1.0) * g(u, 0.3, 0.08) * max(0.0, front - 0.5) * 2.0
        gap = lk.get("gap", 0.33)
        if sockets:                                     # (the eyes sit in them: features are placed without them)
            for sd in (-1.0, 1.0):
                F -= 0.035 * g(u, 0.1, 0.1) * g(l, sd * gap, 0.13) * front
        if lk.get("sag"):
            Ls += math.copysign(0.025 * g(u, -0.35, 0.15) * front, l)
        # 🎭 cartoon / caricature shapes (0 = none, 1 = strong): the face really changes, the features ride on it
        fr_ = 0.35 + 0.65 * min(1.0, max(0.0, f + 0.35))   # strongest at the face, little at the back (under the hair)
        jw = lk.get("jowls", 0.0)
        if jw and u < 0:                                # a pear face: wide, heavy jowls and a low round bottom
            k = -u
            Ls *= 1.0 + jw * 0.42 * k ** 0.8 * (1.0 - 0.5 * k ** 3) * fr_
            F *= 1.0 + jw * 0.16 * k * front
            U -= jw * 0.16 * k * k
        cl = lk.get("chin_len", 0.0)
        if cl and u < 0:                                # a long jaw: the lower face stretches down to a longer chin
            k = -u
            U -= cl * 0.3 * k ** 1.6
            Ls *= 1.0 - cl * 0.1 * k * k
        fh = lk.get("forehead", 0.0)
        if fh and u > 0:                                # a tall dome of a forehead
            U += fh * 0.16 * u * u
        return F, U, Ls

    def skull(self, pen, colour=None):
        """The sculpted head with smooth shading: more corners when it is big on screen (close-ups)."""
        px = self.head_r * (getattr(pen, "px_unit", None) or 6.0)
        rings = int(max(8, min(26, 7 + px / 8.0)) * max(0.5, min(1.0, pen.detail)))
        sides = rings * 2
        grid = []
        for i in range(rings + 1):
            th = math.pi * i / rings
            u, sn = math.cos(th), math.sin(th)
            row = []
            for j in range(sides):
                ph = 2 * math.pi * j / sides
                F, U, Ls = self.sculpt(sn * math.cos(ph), u, sn * math.sin(ph))
                row.append(self.on_head(F, U, Ls))
            grid.append(row)
        pen.smooth_grid(grid, colour or self.skin, self.head)


class QuadRig(_Rig):
    def __init__(self, c, pose, face="neutral", mouth=0.0, blink=False, t=0.0, state=None):
        from .animals import q_solve
        self._c, self._t, self._state, self._hide, self._depth = c, t, state, set(), 0
        self.kind = "quadruped"
        sp = self.sp = dict(c.animal)
        self.species = c.species
        self.s = s = c.scale
        J = self._J = q_solve(pose, sp, s)
        self.fur, self.belly = _col(sp["fur"]), _col(sp["belly"])
        self.dark = darker(self.fur, 0.55)
        self.g = sp["girth"] * s * 0.6                       # a bit chunkier than the side drawing (cartoon)
        self.lat = self.g * 0.62
        self.legw = sp.get("leg_w", sp["girth"] * 0.34) * s / 2
        self.leg_color = _hexc(sp.get("leg_color"), self.fur) if sp.get("leg_color") else self.fur
        self.hoof = (0.12, 0.1, 0.1) if sp.get("hooves") or sp.get("step") == "hoof" else darker(self.leg_color, 0.8)
        self.muzzle = _hexc(sp.get("muzzle"), self.belly) if sp.get("muzzle") else self.belly
        self.mane = _hexc(sp.get("mane"), (0.3, 0.18, 0.08)) if sp.get("mane") else None
        self.tail_tip = _hexc(sp.get("tail_tip"), self.dark) if sp.get("tail_tip") else self.dark
        self.neck_w = sp["neck_w"] * s / 2
        self.head_r = sp["head"] * s
        sl, swd = sp.get("snout", (20, 18))
        self.snout = (sl * s, swd * s)
        self.face, self.mouth, self.blink, self.t = face, float(mouth or 0.0), bool(blink), t
        self._face_ctl(mouth, blink)
        self.pose = dict(pose)
        self.tail, self.wag = pose.get("tail", 0.0), pose.get("wag", 0.0)
        self.jaw, self.trunk = pose.get("jaw", 0.0), pose.get("trunk", 0.0)
        self._hip, self._sh = J["hip"], J["sh"]
        self.length = abs(J["sh"][0] - J["hip"][0])
        self.neck_base, self.neck_end, self.head = _p3(J["nb"]), _p3(J["ne"]), _p3(J["head"])
        na = math.atan2(J["ne"][1] - J["nb"][1], J["ne"][0] - J["nb"][0])
        self.fwd = (math.cos(na - 1.25), math.sin(na - 1.25), 0.0)        # the face looks forward-down
        self.hand_near = self.head

    def along(self, f):
        return (self._hip[0] + (self._sh[0] - self._hip[0]) * f, self._hip[1] + (self._sh[1] - self._hip[1]) * f, 0.0)

    def legs(self):
        """the legs as the planet's physics made them: 0 (a slider), 2 (+ two small arms, "arm"), 4, 6 or 8
        (the middle pairs are "middle")"""
        J, out, nl = self._J, [], int(self.sp.get("legs", 4))
        if nl == 0:
            return out
        rows = [(-1, "kfn", "pfn", "sj", "arm" if nl == 2 else "front"), (1, "kff", "pff", "sj", "arm" if nl == 2 else "front")]
        for i in sorted({k[2] for k in J if k.startswith("rm")}):
            rows += [(-1, f"km{i}n", f"pm{i}n", "rm" + i, "middle"), (1, f"km{i}f", f"pm{i}f", "rm" + i, "middle")]
        rows += [(-1, "kbn", "pbn", "hj", "back"), (1, "kbf", "pbf", "hj", "back")]
        for side, kk, pp, root, end in rows:
            z = side * self.lat * (1.35 if nl >= 6 and end != "arm" else 1.0)     # many legs splay out to the sides
            out.append((_p3(J[root], z), _p3(J[kk], z), _p3(J[pp], z), end, side))
        return out

    def face_point(self, f, u, lat):
        r, (hx, hy, _), fw = self.head_r, self.head, self.fwd
        return (hx + fw[0] * f * r, hy + fw[1] * f * r + u * r, lat * r)


class BirdRig(_Rig):
    def __init__(self, c, pose, face="neutral", mouth=0.0, blink=False, t=0.0, state=None, flying=False):
        self._c, self._t, self._state, self._hide, self._depth = c, t, state, set(), 0
        self.kind = "bird"
        sp = self.sp = dict(c.animal)
        self.species = c.species
        self.s = s = c.scale
        self.fur, self.belly = _col(sp["fur"]), _col(sp["belly"])
        self.wing = _col(sp["wing"]) if isinstance(sp.get("wing"), tuple) else darker(self.fur, 0.8)
        self.head_color = _col(sp["headc"]) if isinstance(sp.get("headc"), tuple) else self.fur
        bc, bl = sp.get("beak", ((0.9, 0.6, 0.1), 10))
        self.beak_color = _hexc(bc, (0.9, 0.6, 0.1))
        self.beak_len = bl * s
        self.b = sp["body"] * s
        self.head_r = sp["head"] * s
        self.flying = bool(flying)
        lk, nk = float(sp.get("leg_k", 1.0)), float(sp.get("neck_k", 1.0))     # long legs / a long neck (flamingo)
        self.y0 = self.b * (0.35 if flying else 0.9 + 0.5 * (lk - 1.0)) + pose.get("lift", 0.0) * s
        self.face, self.mouth, self.blink, self.t = face, float(mouth or 0.0), bool(blink), t
        self._face_ctl(mouth, blink)
        self.pose = dict(pose)
        self.head = (self.b * (0.75 + 0.12 * (nk - 1.0)), self.y0 + self.b * (0.45 + 0.55 * (nk - 1.0)), 0.0)
        self.hand_near = self.head


# ============================================================================ which code draws a character
BASE = {"human": "person_3d", "quadruped": "quadruped_3d", "bird": "bird_3d"}
KINDS3 = ("character3d", "animal3d")
_BUILTIN = {}
_WARNED = set()
_DEF_DIR = os.path.join(os.path.dirname(__file__), "char3d_defaults")


def _builtin(base):
    """The shipped copy of a default body (used when the file in assets/code is missing or broken)."""
    if base not in _BUILTIN:
        from .codedraw import compile_code
        with open(os.path.join(_DEF_DIR, base + ".py"), encoding="utf-8") as fh:
            _BUILTIN[base] = compile_code(fh.read(), base)
    return _BUILTIN[base]


def _file_fn(name):
    from . import codedraw
    got = codedraw._load(name)
    if not got or got[2].get("KIND") not in KINDS3:
        return None
    return got[1]


def code_for(c):
    """[(name, fn), ...] to try for this character: its own look, the species, the base body, the built-in."""
    kind = c.kind if c.kind in BASE else "quadruped"
    names = []
    look = (c.spec or {}).get("look3d")
    if look == "sculpt" and kind == "human":                # 🗿 a sculpted clay figure (engine/sculpt_rig.py)
        from . import sculpt_rig
        return [("sculpt", sculpt_rig.code_fn), ("builtin:" + BASE[kind], None)]
    if look == "sculpt" and kind == "bird":                 # 🐦 a sculpted clay bird (engine/sculpt_birds.py)
        from . import sculpt_birds
        return [("sculpt", sculpt_birds.code_fn), ("builtin:" + BASE[kind], None)]
    if look == "sculpt" and kind == "quadruped":            # 🐯 a sculpted clay animal (engine/sculpt_animals.py)
        from . import sculpt_animals
        return [("sculpt", sculpt_animals.code_fn), ("builtin:" + BASE[kind], None)]
    if look:
        names.append(str(look))
    names.append(f"{c.id}_3d")
    if kind != "human":
        names.append(f"{c.species}_3d")
        try:
            from . import codedraw
            for n, m in codedraw.list_code().items():
                if m.get("kind") == "animal3d" and m.get("for") == c.species and n not in names:
                    names.append(n)
        except Exception:
            pass
    names.append(BASE[kind])
    out = []
    for n in names:
        try:
            fn = _file_fn(n)
        except Exception as ex:                         # a broken file: say so once, use the next one
            if n not in _WARNED:
                _WARNED.add(n)
                print(f"3D character code '{n}' has a problem ({ex}) - using the normal body")
            fn = None
        if fn is not None:
            out.append((n, fn))
    out.append(("builtin:" + BASE[kind], None))
    return out


def _run_base(pen, rig, t, state):
    """rig.body(): the normal body (the base file, or the built-in copy when the base file is the one running)."""
    base = BASE.get(rig.kind, "quadruped_3d")
    fn = None
    if rig._depth == 0 and getattr(rig, "_running", "") != base:
        try:
            fn = _file_fn(base)
        except Exception:
            fn = None
    rig._depth += 1
    try:
        (fn or _builtin(base))(pen, rig, t, state)
    finally:
        rig._depth -= 1


def _mark_skin(faces, n0, rig):
    """people's skin faces get the skin look (code3d.skin_light): material slot 4 = skin"""
    try:
        from . import code3d as _c
        sr = _c.color(rig.skin)[:3]
    except Exception:                                   # noqa: BLE001
        return
    for f in faces[n0:]:
        if f.kind == "poly" and f.mat is None and abs(f.c[0] - sr[0]) < 0.004 and abs(f.c[1] - sr[1]) < 0.004 \
                and abs(f.c[2] - sr[2]) < 0.004:
            f.mat = (0.0, 1.0, 0.0, 1)


def make_rig(c, pose, face="neutral", mouth=0.0, blink=False, t=0.0, state=None, flying=False):
    if c.kind == "human":
        return HumanRig(c, pose, face, mouth, blink, t, state)
    if c.kind == "bird":
        return BirdRig(c, pose, face, mouth, blink, t, state, flying)
    return QuadRig(c, pose, face, mouth, blink, t, state)


def build(pen, c, pose, face="neutral", mouth=0.0, blink=False, t=0.0, detail=1.0, flying=False, state=None,
          fn=None, drag=None):
    """Run the character's code into pen (local frame: x forward). -> rig (or None if nothing worked)."""
    pen.detail = detail
    tries = [("given", fn)] if fn is not None else code_for(c)
    base = BASE.get(c.kind if c.kind in BASE else "quadruped")
    for name, f in tries:
        rig = make_rig(c, pose, face, mouth, blink, t, state if state else (c.spec or {}).get("look3d_state"), flying)
        rig._running = name
        rig.drag = tuple(drag) if drag else (0.0, 0.0)     # (swing back, lift) degrees: hair / cloth follow-through
        n0 = len(pen.faces)
        try:
            (f or _builtin(base))(pen, rig, t, rig._state)
            if c.kind == "human":
                _mark_skin(pen.faces, n0, rig)
            return rig
        except Exception as ex:
            del pen.faces[n0:]
            if fn is not None:
                raise
            if name not in _WARNED:
                _WARNED.add(name)
                print(f"3D character code '{name}' failed ({ex}) - using the next one")
    return None


# ============================================================================ drawing into the 3D scene
def draw(ctx, c, pose, x, y, heading_, face, mouth, t, alpha=1.0, blink=False, flying=False, detail=1.0,
         drag=None, squash=None, bank=0.0):
    """Build the figure and draw it with the real scene camera. Returns the info dict the 2D drawing returns
    (head, head_r, hand in the caller's local coordinates) or None when not in a 3D scene."""
    from . import code3d
    if code3d.CURRENT is None:
        return None
    pen = code3d.Pen3()
    try:
        M_ = ctx.get_matrix()
        pen.px_unit = abs(M_.xx) or None             # screen pixels per unit here: close-ups get finer heads
    except Exception:                                # noqa: BLE001
        pass
    pen.push()
    pen.turn(math.degrees(heading_) - 90.0)
    if bank:
        pen.tilt(bank)                                    # leaning into a curve (engine/realworld.py)
    if squash and (abs(squash[0] - 1) > 0.005 or abs(squash[1] - 1) > 0.005):
        pen.scale(squash[0], squash[1], squash[0])        # squash & stretch round the feet
    rig = build(pen, c, pose, face, mouth, blink, t, detail, flying, drag=drag)
    pen.pop()
    if rig is None:
        return None
    got = code3d.draw_in_scene(ctx, pen.faces, x, y, None, None, alpha=alpha, recolor=False)
    if got is None:
        return None
    sx_, cx_ = math.sin(heading_), math.cos(heading_)       # local x -> world X; local z -> world X = -cos

    def loc(p):
        return (x + p[0] * sx_ - p[2] * cx_, y + p[1])
    hd = rig.head
    info = {"head": loc(hd), "head_r": rig.head_r, "hand": loc(rig.hand_near)}
    return info


# ============================================================================ Studio preview: many camera angles
POSES = ("idle", "walk", "run", "talk", "wave", "sit", "dance", "jump")
VIEWS = (("front", 0.0, 10.0), ("3/4", 38.0, 12.0), ("side", 90.0, 8.0), ("back", 180.0, 10.0),
         ("from above", 30.0, 52.0), ("low", -35.0, 2.0))


def sample_char(s):
    """A character to try the code on (the file's PREVIEW = {...} settings)."""
    from .character import CharacterDef
    spec = dict(s.get("PREVIEW") or {})
    who = str(s.get("FOR") or "human").lower()
    if who not in ("human", "quadruped", "bird") and "species" not in spec:
        spec["species"] = who                       # FOR = "tiger" -> try it on a tiger
    if who == "quadruped" and "species" not in spec:
        spec["species"] = "dog"
    if who == "bird" and "species" not in spec:
        spec["species"] = "parrot"
    from . import animals, registry
    registry.load()
    S = s.get("SPECIES") if isinstance(s.get("SPECIES"), dict) else None
    new = who not in ("human", "quadruped", "bird") and (who not in animals.BUILTIN) and \
        (S is not None or animals.canon(who) == "human")
    if new:                                          # a new animal (not saved yet, or just changed): make it now
        try:
            registry.install_code_species(who, S or {}, s.get("DESCRIPTION"))
            spec["species"] = who
        except Exception:
            spec["species"] = (S or {}).get("base") or ("parrot" if (S or {}).get("kind") == "bird" else "tiger")
    elif who not in ("human",) and animals.canon(spec.get("species", "")) == "human":
        spec["species"] = "tiger"
    spec.setdefault("name", "Preview")
    return CharacterDef("preview", spec)


def pose_at(c, pose_name, t):
    from .poses import ACTIONS
    from .animals import actions_for, animal_ctx
    table = actions_for(c) if c.kind != "human" else ACTIONS
    ctx = {"params": {}, "speed": 0.0, "dist": 0.0}
    if c.kind != "human":
        ctx.update(animal_ctx(c))
    name = pose_name if pose_name in table else "idle"
    if name == "sit" and c.kind != "human" and "sit" not in table:
        name = "idle"
    spec = table[name]
    dur = spec.dur or 1.0
    p, ex = spec.fn(t % max(dur, 1e-3) if name not in ("walk", "run") else t, dur, ctx)
    return p, ex


def faces_for(fn, s, pose_name="idle", t=0.0, look=None):
    from . import code3d
    c = sample_char(s)
    p, ex = pose_at(c, pose_name, t)
    pen = code3d.Pen3()
    pen.push()
    pen.turn(math.degrees(math.pi) - 90.0)          # facing the preview camera
    talk = pose_name == "talk"
    mouth = 0.0
    if talk:                                   # the preview says "A D B E F C H G" - every mouth shape in turn
        from .lipsync import SHAPES, KEYS, Mouth
        sh = "ADBEFCHG"[int(t * 4) % 8]
        ctl = dict(zip(KEYS, SHAPES[sh]))
        ctl.update(brow=0.4 if sh in "DE" else 0.0, gx=0.0, gy=0.0, lid=0.0, nod=0.0, shape=sh)
        mouth = Mouth(ctl["jaw"] * (1 - 0.85 * ctl["closed"]), ctl)
    build(pen, c, p, (ex or {}).get("face", "happy" if pose_name in ("dance", "wave") else "neutral"),
          mouth, False, t, 1.0, pose_name == "jump" and c.kind == "bird",
          state=look, fn=fn)
    pen.pop()
    return pen.faces, c


def preview_png(fn, s, state=None, t=None, frame=None, width=900, height=560):
    """One picture: the character seen from 6 camera angles (front, 3/4, side, back, above, low);
    frame given (▶ Turn around): the camera goes round while it moves."""
    import io
    import cairo
    from . import code3d
    pose_name, look = "idle", None
    if state:
        st = str(state)
        if st.startswith("look: "):
            look = st[6:]
        elif st in POSES:
            pose_name = st
    def fit(fs):
        ex = code3d.extent(fs) or (0, 300, 0, 300, 0, 300)
        big = max(ex[1] - ex[0], ex[3] - ex[2], ex[5] - ex[4], 1.0)
        return max(1.05, 300.0 / big * 0.9)
    if frame is not None:
        tt = float(frame) / 12.0
        faces, c = faces_for(fn, s, pose_name, tt, look)
        surf = code3d.preview_view(faces, width, height, angle=-30.0 + 10.0 * int(frame), elev=12.0, person=False,
                                   zoom=fit(faces))
        buf = io.BytesIO()
        surf.write_to_png(buf)
        return buf.getvalue()
    faces, c = faces_for(fn, s, pose_name, float(t or 0.35), look)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(0.95, 0.94, 0.9)
    ctx.paint()
    cols, rows = 3, 2
    tw, th = width // cols, height // rows
    for i, (label, ang, elev) in enumerate(VIEWS):
        tile = code3d.preview_view(faces, tw, th, angle=ang, elev=elev, person=False, zoom=fit(faces))
        x0, y0 = (i % cols) * tw, (i // cols) * th
        ctx.set_source_surface(tile, x0, y0)
        ctx.paint()
        ctx.set_source_rgba(0, 0, 0, 0.55)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(max(11, th // 16))
        ctx.move_to(x0 + 8, y0 + th - 10)
        ctx.show_text(label)
    ctx.set_source_rgba(0, 0, 0, 0.6)
    ctx.set_font_size(max(11, height // 32))
    ctx.move_to(10, 22)
    n = len(faces)
    ctx.show_text(f"{pose_name}{' · ' + look if look else ''} · {n} shapes" +
                  ("  ⚠ many shapes - slower renders" if n > 2200 else ""))
    buf = io.BytesIO()
    surf.write_to_png(buf)
    return buf.getvalue()


def check(fn, s):
    """Try the code in a few poses (for saving). -> number of shapes, raises on problems."""
    most = 0
    for pn in ("idle", "walk", "sit"):
        faces, _c = faces_for(fn, s, pn, 0.3)
        if not faces:
            raise ValueError(f"nothing was drawn in the '{pn}' pose")
        most = max(most, len(faces))
    return most
