"""Real 3D vehicles in 3D scenes: a car is a solid shape that turns with the road, not a flat side picture.

In camera_mode 3d every car / jeep / bus / auto / bike is drawn from a 3D model (assets/code/sedan_3d.py ...),
turned to the way its nose points at that moment (PropTrack.heading_at), so it swings round corners, drives
toward / away from the camera nose first, and never slides sideways. Your own 3D vehicles (car_3d, cart_3d,
boat_3d ...) turn the same way. The story's "color" repaints the body.

Per vehicle: "flat": true keeps the old flat drawing.   Story: "settings": {"vehicles_3d": false} for all.
"""
import math

MODEL_FOR = {"car": "sedan_3d", "jeep": "jeep_3d", "bus": "bus_3d", "auto": "auto_rickshaw_3d", "bike": "bicycle_3d"}
PAINT = {"sedan_3d": "#e63946", "jeep_3d": "#5b7f3a", "bus_3d": "#f4b400", "auto_rickshaw_3d": "#2a9d4f",
         "bicycle_3d": "#1d4e89"}
OPEN = ("bicycle_3d",)                  # riders sit ON it (drawn after it), not inside a body
_RECOL = {}
_TURNED = {}


def _rgb(h):
    h = str(h).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None


def model_of(pr, settings=None):
    """(name, meta) of the 3D model to draw this vehicle with, or None (-> the flat drawing)."""
    from . import images
    if pr.spec.get("flat") or (settings is not None and settings.get("vehicles_3d") is False):
        return None
    if pr.vtype == "picture":
        name = str(pr.type)
    else:
        name = MODEL_FOR.get(pr.vtype)
    if not name:
        return None
    meta = images.info(name) or {}
    if not (meta.get("is3d") and meta.get("live") and meta.get("code")):
        return None
    return name, meta


def _recolor(faces, src, dst):
    key = (id(faces), dst)
    got = _RECOL.get(key)
    if got is not None and got[0] is faces:
        return got[1]
    from .code3d import Face
    out = []
    idx = {}
    for f in faces:
        c = f.c
        if isinstance(c, tuple) and len(c) >= 3:
            ks = [c[i] / src[i] for i in range(3) if src[i] > 0.05]
            if ks and max(ks) - min(ks) < 0.03 and 0.4 < ks[0] < 1.05 and \
                    all(abs(c[i] - src[i] * ks[0]) < 0.02 for i in range(3)):    # the paint (or a shade of it)
                k = ks[0]
                c = tuple(min(1.0, v * k) for v in dst) + tuple(c[3:])
        g = Face(f.pts, f.n, c, f.cull, f.line, f.w, None, f.sub, f.edge, f.kind, f.mat, f.walk)
        idx[id(f)] = g
        out.append(g)
    for f, g in zip(faces, out):
        if f.parent is not None:
            g.parent = idx.get(id(f.parent))
    if len(_RECOL) > 300:
        _RECOL.clear()
    _RECOL[key] = (faces, out)
    return out


def faces_for(name, meta, t, color=None):
    """The model's faces at drive time t, repainted in the story's colour."""
    from . import codedraw
    faces = codedraw.live_faces(meta, t)
    if not faces:
        return None
    src = PAINT.get(name)
    if color and src:
        a, b = _rgb(src), _rgb(color)
        if a and b and a != b:
            faces = _recolor(faces, a, b)
    return faces


def turned(faces, deg):
    from . import code3d
    key = (id(faces), round(deg % 360.0, 1))
    got = _TURNED.get(key)
    if got is None or got[0] is not faces:
        if len(_TURNED) > 800:
            _TURNED.clear()
        got = _TURNED[key] = (faces, code3d.turned(faces, deg))
    return got[1]


_TILT = {}


def tilted(faces, pitch, roll):
    """The body leaning on its springs: pitch (degrees, + = nose up) about the side axis, roll (+ = leans to
    its right) about the nose axis, round the middle of the floor."""
    if abs(pitch) < 0.05 and abs(roll) < 0.05:
        return faces
    key = (id(faces), round(pitch * 4) / 4, round(roll * 4) / 4)
    got = _TILT.get(key)
    if got is not None and got[0] is faces:
        return got[1]
    from .code3d import Face
    a, b = math.radians(key[1]), math.radians(key[2])
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)

    def rp(p):
        x, y, z = p[0], p[1], p[2]
        x, y = x * ca - y * sa, x * sa + y * ca          # pitch: nose (+x) up for a > 0
        y, z = y * cb - z * sb, y * sb + z * cb          # roll round the nose axis
        return (x, y, z)
    out = [Face([rp(q) for q in f.pts], rp(f.n) if f.kind == "poly" else f.n, f.c, f.cull, f.line, f.w, None,
                f.sub, f.edge, f.kind, f.mat, f.walk, f.tex, f.uv) for f in faces]
    idx = {id(f): g for f, g in zip(faces, out)}
    for f, g in zip(faces, out):
        if f.parent is not None:
            g.parent = idx.get(id(f.parent))
    if len(_TILT) > 600:
        _TILT.clear()
    _TILT[key] = (faces, out)
    return out


def body_tilt(pr, t):
    """(pitch, roll) in degrees from the springs: the nose dips when it brakes and lifts when it pulls away,
    the body leans out in a bend, then it bobs and settles (a damped spring, ~1.3 Hz)."""
    from .timeline import ZK
    k_ = ZK * 2.5
    if not any(s_[0] == "move" and tt - 0.2 <= t <= tt + s_[5] + 2.0 for tt, s_ in pr.states):
        return 0.0, 0.0
    dt, T = 1.0 / 30.0, 1.6
    w, zeta = 2 * math.pi * 1.3, 0.35
    K = 1.1 / 300.0                                      # 300 units/s^2 -> about 1 degree

    def P(tt):
        return pr.pos(tt)[0], pr.z_at(tt) * k_
    th = om = ph = oph = 0.0
    n = int(T / dt)
    for i in range(n + 1):
        tt = t - T + i * dt
        a0, b0, c0 = P(tt - dt), P(tt), P(tt + dt)
        ax, az = (c0[0] - 2 * b0[0] + a0[0]) / (dt * dt), (c0[1] - 2 * b0[1] + a0[1]) / (dt * dt)
        hx, hz = pr.heading_at(tt)
        hl = math.hypot(hx, hz * k_) or 1.0
        ux, uz = hx / hl, hz * k_ / hl
        a_long = ax * ux + az * uz                     # speeding up (+) / braking (-)
        a_lat = ax * (-uz) + az * ux                   # toward its left (+)
        a_long = max(-900.0, min(900.0, a_long))
        a_lat = max(-900.0, min(900.0, a_lat))
        om += (-w * w * th - 2 * zeta * w * om + w * w * K * a_long) * dt
        th += om * dt
        oph += (-w * w * ph - 2 * zeta * w * oph + w * w * K * 0.8 * a_lat) * dt
        ph += oph * dt
    return max(-2.5, min(2.5, th)), max(-2.5, min(2.5, ph))


def draw(ctx, name, meta, x, y, height, deg, t, color=None, alpha=1.0, tilt=(0.0, 0.0)):
    """Draw the vehicle solid with the real 3D camera. False when not in a 3D scene (-> flat drawing)."""
    from . import code3d
    if code3d.CURRENT is None:
        return False
    faces = faces_for(name, meta, t, color)
    if not faces:
        return False
    faces = tilted(faces, tilt[0], tilt[1])
    faces = turned(faces, deg)
    got = code3d.draw_in_scene(ctx, faces, x, y, height, float(meta.get("height") or height), False, alpha,
                               recolor=False)
    return bool(got)


def world_deg(at, zmap, x, z, hx, hz):
    """Turn (degrees, for code3d.turned) that points the model's nose (+x) along story heading (hx, hz),
    measured on screen-world ground through the scene's own mapping at(x, z) -> (X, Z)."""
    L = math.hypot(hx, hz * 2.0)
    if L < 1e-9:
        return 0.0
    e = 40.0 / L
    X0, Z0 = at(x, zmap(z))
    X1, Z1 = at(x + hx * e, zmap(z + hz * e))
    dX, dZ = X1 - X0, Z1 - Z0
    if abs(dX) + abs(dZ) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(-dZ, dX))          # turned(): nose (1, 0, 0) -> (cos a, -sin a)


def seat_offsets(meta, deg, scale):
    """[(dx, dy, dz)] world offsets of the RIDE seats once the model is turned by deg."""
    ride = meta.get("ride") if isinstance(meta.get("ride"), dict) else {}
    seats = ride.get("seats") or []
    a = math.radians(deg)
    c, s_ = math.cos(a), math.sin(a)
    out = []
    for p in seats:
        if not isinstance(p, (list, tuple)) or len(p) < 3:
            continue
        px, py, pz = float(p[0]), float(p[1]), float(p[2])
        out.append(((px * c + pz * s_) * scale, py * scale, (-px * s_ + pz * c) * scale))
    return out
