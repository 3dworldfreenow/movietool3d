"""Real physics for school videos: experiments that move by the true formulas, in real units (1 m = 175 story
units, a person is 1.7 m), drawn in 3D, with arrows, a ruler, a stopwatch, the numbers and a graph that draws
itself.

Story:
    {"experiment": "pendulum", "id": "p1", "x": 1200, "z": 400, "length": 1.5, "angle": 20, "duration": 10}
    {"experiment": "projectile", "speed": 12, "angle": 45}      {"experiment": "fall", "height": 4, "objects":
    "stone,feather", "air": false, "planet": "moon"}            {"who": "ravi", "do": "throw", "angle": 45,
    "speed": 9}   {"who": "ravi", "do": "drop", "what": "ball", "from": 2}   {"freeze": "p1", "duration": 3}
    common keys: "labels" (numbers + graph, default: on when settings "physics": "real"), "slowmo": 0.5
    (half speed), "graph": false, "arrows": false, "ruler": false, "planet": "earth" | "moon" | "mars" | "jupiter"
Settings: "physics": "real" (school mode: labels on, real timing) | "story" (default: no labels).

Every frame computes the state from the time (no stepping), so parallel rendering gives the same picture.
"""
import math

M = 175.0                                  # story units per metre
PLANETS = {"earth": 9.81, "moon": 1.62, "mars": 3.71, "jupiter": 24.79, "space": 0.0}
TAU = 2 * math.pi

RED, BLUE, GREEN, YELLOW = "#e63946", "#3a86ff", "#2a9d48", "#ffbe0b"
ARROW_V, ARROW_F, ARROW_A = "#2a9d48", "#e63946", "#8338ec"     # speed (green), force (red), acceleration


def _num(spec, key, default, lo=None, hi=None, *alts):
    v = spec.get(key)
    for a in alts:
        if v is None:
            v = spec.get(a)
    try:
        v = float(v) if v is not None else float(default)
    except (TypeError, ValueError):
        v = float(default)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def _list(v, default):
    if v is None:
        return list(default)
    if isinstance(v, (list, tuple)):
        return list(v)
    return [s.strip() for s in str(v).split(",") if s.strip()]


def _g(spec):
    if spec.get("g") is not None:
        return _num(spec, "g", 9.81, 0.0, 100.0)
    return PLANETS.get(str(spec.get("planet", "earth")).lower(), 9.81)


# ============================================================================ drawing helpers (Pen3)
def arrow(pen, p, q, c=ARROW_V, r=4.0):
    """an arrow from p to q (3D points): a tube and a flat head facing the camera"""
    dx, dy, dz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    if L < 6:
        return
    ux, uy, uz = dx / L, dy / L, dz / L
    hl = min(L * 0.45, r * 6.0)
    base = (q[0] - ux * hl, q[1] - uy * hl, q[2] - uz * hl)
    pen.tube([p, base], r, c=c, sides=6, smooth=False)
    # a side direction in the picture plane (perpendicular, mostly in x-y)
    sx, sy = -uy, ux
    sl = math.hypot(sx, sy) or 1.0
    sx, sy = sx / sl * hl * 0.55, sy / sl * hl * 0.55
    pen.poly([(base[0] + sx, base[1] + sy, base[2] - 1), (q[0], q[1], q[2] - 1), (base[0] - sx, base[1] - sy, base[2] - 1)],
             c=c)


def ruler(pen, x, z, h_m, step=0.5):
    """a measuring pole h_m metres tall with yellow / black bands every step metres"""
    n = max(1, int(math.ceil(h_m / step)))
    for i in range(n):
        y0 = i * step * M
        hh = min(step * M, h_m * M - y0)
        if hh <= 0:
            break
        pen.box(x, y0, z, w=10, h=hh, d=10, c=YELLOW if i % 2 == 0 else "#222222")
        if (i * step) % 1.0 < 1e-6:                 # a longer tick at every whole metre
            pen.box(x + 12, y0, z, w=24, h=4, d=6, c="#222222")


def dashed(pen, p, q, c="#ffffff", w=2.5, n=12):
    for i in range(n):
        if i % 2:
            continue
        a, b = i / n, (i + 1) / n
        pen.line([tuple(p[k] + (q[k] - p[k]) * a for k in range(3)), tuple(p[k] + (q[k] - p[k]) * b for k in range(3))],
                 c=c, w=w)


def ring(pen, x, y, z, r, c="#ffffff", w=3.0, plane="xz", n=40):
    pts = []
    for i in range(n + 1):
        a = TAU * i / n
        if plane == "xz":
            pts.append((x + r * math.cos(a), y, z + r * math.sin(a)))
        else:
            pts.append((x + r * math.cos(a), y + r * math.sin(a), z))
    pen.line(pts, c=c, w=w)


def plank(pen, cx, cy, z, length, thick, depth, ang, c="wood"):
    """a box rotated about the z axis (see-saw plank, ramp top): ang in radians"""
    ca, sa = math.cos(ang), math.sin(ang)
    hl, ht, hd = length / 2, thick / 2, depth / 2
    corners = []
    for sxx in (-1, 1):
        for syy in (-1, 1):
            corners.append((cx + sxx * hl * ca - syy * ht * sa, cy + sxx * hl * sa + syy * ht * ca))
    (a, b, c2, d) = corners[0], corners[1], corners[3], corners[2]   # -,-  -,+  +,+  +,-
    for zz in (z - hd, z + hd):
        pen.poly([(a[0], a[1], zz), (b[0], b[1], zz), (c2[0], c2[1], zz), (d[0], d[1], zz)], c=c)
    for p, q in ((a, b), (b, c2), (c2, d), (d, a)):
        pen.poly([(p[0], p[1], z - hd), (q[0], q[1], z - hd), (q[0], q[1], z + hd), (p[0], p[1], z + hd)], c=c)


def frame(pen, w, h, z0=-60, z1=60, c="#5c4a3a", r=7):
    """two posts and a top bar (pendulum, spring, swing)"""
    for x in (-w / 2, w / 2):
        pen.tube([(x, 0, z0), (x, h, 0)], r, c=c, sides=6, smooth=False)
        pen.tube([(x, 0, z1), (x, h, 0)], r, c=c, sides=6, smooth=False)
    pen.tube([(-w / 2 - 10, h, 0), (w / 2 + 10, h, 0)], r * 1.1, c=c, sides=6, smooth=False)


# ---------------------------------------------------------------------------- solving motion (Runge-Kutta)
class Table:
    """The motion worked out ONCE with 4th-order Runge-Kutta (Computational Physics with Python, ch. 4), then
    read at any time by interpolation - every frame is the same, so parallel rendering still works.
    f(t, y) -> dy/dt (lists); y0 = start values; stop(t, y) -> True ends it (the ball reached the ground)."""

    def __init__(self, f, y0, T, dt=0.004, stop=None):
        ts, ys = [0.0], [list(y0)]
        t, y = 0.0, list(y0)
        n = len(y0)
        while t < T:
            k1 = f(t, y)
            k2 = f(t + dt / 2, [y[i] + dt / 2 * k1[i] for i in range(n)])
            k3 = f(t + dt / 2, [y[i] + dt / 2 * k2[i] for i in range(n)])
            k4 = f(t + dt, [y[i] + dt * k3[i] for i in range(n)])
            y = [y[i] + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(n)]
            t += dt
            ts.append(t)
            ys.append(y)
            if stop is not None and stop(t, y):
                break
        self.ts, self.ys, self.dt = ts, ys, dt
        self.end = ts[-1]

    def at(self, t):
        if t <= 0:
            return list(self.ys[0])
        if t >= self.end:
            return list(self.ys[-1])
        k = int(t / self.dt)
        k = min(k, len(self.ts) - 2)
        u = (t - self.ts[k]) / self.dt
        a, b = self.ys[k], self.ys[k + 1]
        return [a[i] + (b[i] - a[i]) * u for i in range(len(a))]


def ghosts(pen, fn, t, n=4, step=0.05):
    """a fading trail behind a moving thing: fn(pen, t, alpha) draws it at an earlier time (motion feels alive)"""
    for k in range(n, 0, -1):
        tt = t - k * step
        if tt <= 0:
            continue
        fn(pen, tt, 0.16 + 0.12 * (n - k) / n)


def puff(pen, x, y, z, age, c="#d8cfc0", n=10, size=6.0, spread=60.0):
    """a small cloud of dust / spray where something lands or hits (age = seconds since)"""
    if age < 0 or age > 0.7:
        return
    import random as _r
    rr = _r.Random(int(x * 7 + z * 13) & 0xffff)
    for i in range(n):
        a = rr.uniform(0, TAU)
        sp = rr.uniform(0.4, 1.0) * spread
        px = x + math.cos(a) * sp * age * 2.2
        pz = z + math.sin(a) * sp * age * 1.2
        py = y + rr.uniform(0.2, 1.0) * 70 * age - 120 * age * age
        pen.dot(px, max(y, py), pz, r=size * (1 + 2 * age), c=c)


def ghost_c(c, alpha):
    """a see-through version of a colour for ghosts"""
    from .codedraw import color
    r, g, b, _a = color(c)
    return (r, g, b, alpha)


# ============================================================================ experiments
class Exp:
    name = "experiment"
    title = ""

    def __init__(self, spec):
        self.spec = spec
        self.g = _g(spec)
        self.setup()

    def setup(self):
        pass

    def length(self):
        return 8.0

    def size(self):
        return 400.0, 400.0

    def draw(self, pen, t):
        pass

    def values(self, t):
        """[(label, value text)] for the panel"""
        return []

    def graph(self):
        """(x label, y label, fn(t) -> y or [ys], y max, [colours]) or None"""
        return None

    def energy(self, t):
        """(kinetic, potential) at time t as parts of the total (for the energy bars) or None"""
        return None

    def sounds(self):
        """[(time, sound name)] - a knock when it bounces, a splash ... (added to the scene's sounds)"""
        return []


# ---------------------------------------------------------------------------- free fall
class Fall(Exp):
    name, title = "fall", "Free fall"
    TERMINAL = {"stone": 60.0, "ball": 25.0, "feather": 0.6, "paper": 1.6, "leaf": 1.0, "coin": 40.0, "apple": 30.0}
    COL = {"stone": "#7d7a74", "ball": RED, "feather": "#f5f5f0", "paper": "#ffffff", "leaf": "#4f9f3a",
           "coin": "#e0b030", "apple": "#d62828"}

    def setup(self):
        self.h = _num(self.spec, "height", 3.0, 0.2, 60.0, "from", "h")
        self.objs = _list(self.spec.get("objects", self.spec.get("what")), ["stone"])[:4]
        self.air = self.spec.get("air", any(o in ("feather", "paper", "leaf") for o in self.objs)) not in (False, 0, "no", "off")
        if self.g <= 0:
            self.g = 9.81

    def _drop(self, o, t):
        """(distance fallen m, speed m/s)"""
        vt = self.TERMINAL.get(o, 30.0) if self.air else 1e9
        if vt > 1e6:
            return 0.5 * self.g * t * t, self.g * t
        k = self.g / vt
        d = vt * (t - (1 - math.exp(-k * t)) / k)
        return d, vt * (1 - math.exp(-k * t))

    def land_time(self, o):
        lo, hi = 0.0, 1.0
        while self._drop(o, hi)[0] < self.h and hi < 400:
            hi *= 2
        for _ in range(50):
            mid = (lo + hi) / 2
            if self._drop(o, mid)[0] < self.h:
                lo = mid
            else:
                hi = mid
        return hi

    def length(self):
        return min(30.0, max(self.land_time(o) for o in self.objs) + 1.5)

    def size(self):
        return 260.0 + 140 * len(self.objs), self.h * M + 60

    def pos(self, o, t):
        T = self.land_time(o)
        tt = min(t, T)
        d, v = self._drop(o, tt)
        return max(0.0, self.h - d), (0.0 if t >= T else v)

    def draw(self, pen, t):
        H = self.h * M
        pen.box(-80, 0, 0, w=110, h=H, d=110, c="#b5a48b")                 # the tower
        pen.box(-80 + 70 * len(self.objs), H, 0, w=140 * len(self.objs) + 90, h=14, d=110, c="#8b5a2b")
        if self.spec.get("ruler", True):
            ruler(pen, -160, 40, self.h)
        for i, o in enumerate(self.objs):
            x = 40 + 140 * i
            y, v = self.pos(o, t)
            r = 14 if o in ("feather", "leaf", "paper") else 18
            yy = y * M + r
            c = self.COL.get(o, RED)
            if o == "feather":
                pen.ellipsoid(x, yy, 0, rx=26, ry=6, rz=10, c=c, rings=4, sides=8)
                pen.line([(x - 26, yy, 0), (x + 30, yy + 3, 0)], c="#c8c0b0", w=2)
            elif o == "paper":
                pen.box(x, yy - 2, 0, w=50, h=3, d=36, c=c)
            elif o == "coin":
                pen.cylinder(x, yy - 3, 0, r=14, h=5, c=c, sides=12)
            else:
                if v > 0.3:
                    def one(p_, tt, al, o=o, x=x, r=r, c=c):
                        y2, _v = self.pos(o, tt)
                        p_.sphere(x, y2 * M + r, 0, r=r * 0.9, c=ghost_c(c, al), rings=4, sides=8)
                    ghosts(pen, one, t, n=4, step=0.04)
                pen.sphere(x, yy, 0, r=r, c=c, rings=6, sides=10)
            puff(pen, x, 4, 0, t - self.land_time(o), c="#c9c3b6" if self.g < 5 else "#d8cfc0")
            if self.spec.get("arrows", True) and v > 0.05:
                arrow(pen, (x + 34, yy, -10), (x + 34, yy - min(220, 18 * v), -10), ARROW_V)
                arrow(pen, (x - 34, yy, -10), (x - 34, yy - 60, -10), ARROW_F, r=3)     # weight (gravity)

    def values(self, t):
        o = self.objs[0]
        y, v = self.pos(o, t)
        out = [("g", f"{self.g:.2f} m/s²"), ("height", f"{y:.2f} m"), ("speed", f"{v:.2f} m/s")]
        if len(self.objs) > 1:
            y2, v2 = self.pos(self.objs[1], t)
            out.append((self.objs[1], f"{y2:.2f} m, {v2:.2f} m/s"))
        out.append(("lands at", f"{self.land_time(o):.2f} s"))
        return out

    def graph(self):
        return ("time (s)", "height (m)", lambda t: [self.pos(o, t)[0] for o in self.objs], self.h,
                [self.COL.get(o, RED) for o in self.objs])

    def energy(self, t):
        y, v = self.pos(self.objs[0], t)
        tot = max(1e-9, self.g * self.h)
        return 0.5 * v * v / tot, self.g * y / tot

    def sounds(self):
        return [(self.land_time(o), "knock") for o in self.objs if o not in ("feather", "paper", "leaf")]


# ---------------------------------------------------------------------------- projectile (and the catapult)
class Projectile(Exp):
    name, title = "projectile", "Throwing a ball"

    def setup(self):
        self.v = _num(self.spec, "speed", 10.0, 0.5, 80.0, "v")
        self.a = math.radians(_num(self.spec, "angle", 45.0, -80.0, 89.0))
        self.h0 = _num(self.spec, "from", 1.0, 0.0, 50.0, "height")
        if self.g <= 0:
            self.g = 9.81
        vs = self.v * math.sin(self.a)
        self.T = (vs + math.sqrt(vs * vs + 2 * self.g * self.h0)) / self.g
        self.R = self.v * math.cos(self.a) * self.T
        self.t_top = max(0.0, vs / self.g)
        self.H = self.h0 + vs * self.t_top - 0.5 * self.g * self.t_top ** 2
        self.launch = 0.35 if self.name == "catapult" else 0.0
        self.air = self.spec.get("air", False) not in (False, 0, "no", "off")
        self.drag = _num(self.spec, "drag", 0.024, 0.0, 2.0)          # k/m of a football in air (1/m)
        self.vac = (self.T, self.R, self.H, self.t_top)
        if self.air:                                      # with air: worked out step by step (Runge-Kutta)
            k = self.drag
            g = self.g

            def f(t, y):
                v = math.hypot(y[2], y[3])
                return [y[2], y[3], -k * v * y[2], -g - k * v * y[3]]
            self.tb = Table(f, [0.0, self.h0, self.v * math.cos(self.a), self.v * math.sin(self.a)], 60.0,
                            dt=0.003, stop=lambda t, y: y[1] < 0 and t > 0.01)
            self.T = self.tb.end
            self.R = self.tb.ys[-1][0]
            top = max(range(len(self.tb.ys)), key=lambda i: self.tb.ys[i][1])
            self.H, self.t_top = self.tb.ys[top][1], self.tb.ts[top]

    def length(self):
        return min(30.0, self.launch + self.T + 1.5)

    def size(self):
        return self.R * M + 300, self.H * M + 80

    def at(self, t):
        tt = min(max(0.0, t - self.launch), self.T)
        if self.air:
            x, y, vx, vy = self.tb.at(tt)
            return x, max(0.0, y), vx, vy, tt
        x = self.v * math.cos(self.a) * tt
        y = self.h0 + self.v * math.sin(self.a) * tt - 0.5 * self.g * tt * tt
        vx, vy = self.v * math.cos(self.a), self.v * math.sin(self.a) - self.g * tt
        return x, max(0.0, y), vx, vy, tt

    def draw(self, pen, t):
        x0 = -self.R * M / 2
        pen.box(x0 - 30, 0, 0, w=60, h=self.h0 * M, d=60, c="#b5a48b") if self.h0 > 0.05 else None
        if self.name == "catapult":
            k = min(1.0, max(0.0, t / self.launch)) if self.launch else 1.0
            ang = -1.1 + 1.6 * k                                   # the arm swings up and lets go
            pen.box(x0 - 30, 0, 0, w=110, h=20, d=80, c="#8b5a2b")
            pen.tube([(x0 - 30, 20, 0), (x0 - 30 + 70 * math.cos(ang), 20 + 70 * math.sin(ang) + 60, 0)], 6,
                     c="#6b4528", sides=6, smooth=False)
        x, y, vx, vy, tt = self.at(t)
        # the path so far (dots)
        n = int(tt / 0.06)
        for i in range(n + 1):
            ti = i * 0.06
            q = self.at(self.launch + ti)
            pen.dot(x0 + q[0] * M, max(4, q[1] * M), 0, r=4, c="#ffffff")
        if self.air and self.spec.get("compare", True):   # the path it would take with no air (faint)
            Tv = self.vac[0]
            for i in range(int(Tv / 0.09) + 1):
                ti = i * 0.09
                pxv = x0 + self.v * math.cos(self.a) * ti * M
                pyv = (self.h0 + self.v * math.sin(self.a) * ti - 0.5 * self.g * ti * ti) * M
                pen.dot(pxv, max(4, pyv), 0, r=3, c=(1, 1, 1, 0.35))
        bx, by = x0 + x * M, y * M + 16
        if tt < self.T:
            def one(p_, t2, al):
                q = self.at(t2)
                p_.sphere(x0 + q[0] * M, q[1] * M + 16, 0, r=14, c=ghost_c(RED, al), rings=4, sides=8)
            ghosts(pen, one, t, n=4, step=0.035)
        pen.sphere(bx, by, 0, r=16, c=RED, rings=6, sides=10)
        puff(pen, x0 + self.R * M, 2, 0, t - self.launch - self.T)
        if tt >= self.t_top - 0.02 and self.t_top > 0:          # the highest point, marked
            hx = x0 + self.v * math.cos(self.a) * self.t_top * M
            dashed(pen, (hx, 0, 6), (hx, self.H * M, 6), c="#ffd166")
            pen.dot(hx, self.H * M, 0, r=9, c="#ffd166")
        if tt >= self.T - 1e-3:                                 # where it landed
            ring(pen, x0 + self.R * M, 2, 0, 40, c="#ffd166", w=4)
            dashed(pen, (x0, 3, 50), (x0 + self.R * M, 3, 50), c="#ffffff", n=24)
        elif self.spec.get("arrows", True) and t >= self.launch:
            arrow(pen, (bx, by, -10), (bx + vx * 14, by + vy * 14, -10), ARROW_V)
            arrow(pen, (bx, by - 20, -12), (bx, by - 80, -12), ARROW_F, r=3)
        if self.spec.get("ruler", True):
            ruler(pen, x0 - 90, 60, max(1.0, math.ceil(self.H)))

    def values(self, t):
        x, y, vx, vy, tt = self.at(t)
        out = [("speed", f"{math.hypot(vx, vy) if tt < self.T else 0:.2f} m/s"), ("angle", f"{math.degrees(self.a):.0f}°"),
               ("x", f"{x:.2f} m"), ("height", f"{y:.2f} m"), ("highest", f"{self.H:.2f} m"),
               ("lands at", f"{self.R:.2f} m after {self.T:.2f} s")]
        if self.air:
            out.append(("with no air", f"{self.vac[1]:.2f} m - air takes {100 * (1 - self.R / max(1e-6, self.vac[1])):.0f}%"))
        return out

    def energy(self, t):
        x, y, vx, vy, tt = self.at(t)
        ke, pe = 0.5 * (vx * vx + vy * vy), self.g * y
        tot = max(1e-9, 0.5 * self.v ** 2 + self.g * self.h0)
        return ke / tot, pe / tot

    def sounds(self):
        return [(self.launch, "whoosh"), (self.launch + self.T, "knock")]

    def graph(self):
        return ("time (s)", "height (m)", lambda t: self.at(t)[1], max(self.H, 0.5), [RED])


class Catapult(Projectile):
    name, title = "catapult", "A catapult"


# ---------------------------------------------------------------------------- bouncing balls
class Bounce(Exp):
    name, title = "bounce", "Bouncing balls"
    E = {"rubber": 0.82, "tennis": 0.72, "cricket": 0.55, "football": 0.7, "steel": 0.6, "clay": 0.12}
    COL = {"rubber": RED, "tennis": "#c8e03a", "cricket": "#a31621", "football": "#ffffff", "steel": "#b0b8c0",
           "clay": "#b06a3a"}

    def setup(self):
        self.h = _num(self.spec, "height", 2.0, 0.2, 30.0, "from")
        self.balls = _list(self.spec.get("balls", self.spec.get("objects")), ["rubber", "cricket", "clay"])[:4]
        if self.spec.get("e") is not None:
            self.es = [_num(self.spec, "e", 0.7, 0.0, 0.98)] * len(self.balls)
        else:
            self.es = [self.E.get(b, 0.7) for b in self.balls]
        if self.g <= 0:
            self.g = 9.81

    def height(self, e, t):
        g = self.g
        t0 = math.sqrt(2 * self.h / g)
        if t < t0:
            return self.h - 0.5 * g * t * t, -g * t, 0
        v = math.sqrt(2 * g * self.h) * e
        tt, n = t - t0, 1
        while v > 0.08 and n < 60:
            fl = 2 * v / g
            if tt < fl:
                return v * tt - 0.5 * g * tt * tt, v - g * tt, n
            tt -= fl
            v *= e
            n += 1
        return 0.0, 0.0, n

    def length(self):
        return 9.0

    def size(self):
        return 160.0 * len(self.balls) + 160, self.h * M + 60

    def draw(self, pen, t):
        n = len(self.balls)
        pen.box(0, 0, 0, w=160 * n + 60, h=6, d=160, c="#6b6f76")
        pen.box(-80 * n - 40, self.h * M, 0, w=60, h=10, d=60, c="#8b5a2b")
        if self.spec.get("ruler", True):
            ruler(pen, -80 * n - 70, 70, self.h)
        for i, b in enumerate(self.balls):
            x = -80 * (n - 1) + 160 * i
            y, v, k = self.height(self.es[i], t)
            r = 18
            sq = 1.0
            if y < 0.03 and abs(v) > 0.3:                          # squashed for a moment on the floor
                sq = 0.75
            if abs(v) > 0.4:
                def one(p_, tt, al, e=self.es[i], x=x, b=b):
                    y2, _v, _k = self.height(e, tt)
                    p_.sphere(x, y2 * M + r + 6, 0, r=r * 0.9, c=ghost_c(self.COL.get(b, RED), al), rings=4, sides=8)
                ghosts(pen, one, t, n=3, step=0.04)
            pen.sphere(x, y * M + r * sq + 6, 0, r=r, c=self.COL.get(b, RED), rings=6, sides=10, squash=sq)
            for tb in self.hits(self.es[i])[:3]:
                puff(pen, x, 8, 0, t - tb, n=6, size=4, spread=40)

    def values(self, t):
        out = [("drop", f"{self.h:.1f} m")]
        for i, b in enumerate(self.balls):
            y, v, k = self.height(self.es[i], t)
            out.append((f"{b} (e={self.es[i]:.2f})", f"{y:.2f} m, bounce {k}"))
        return out

    def graph(self):
        return ("time (s)", "height (m)", lambda t: [self.height(e, t)[0] for e in self.es], self.h,
                [self.COL.get(b, RED) for b in self.balls])

    def hits(self, e):
        """the moments it hits the floor"""
        g = self.g
        out = [math.sqrt(2 * self.h / g)]
        v = math.sqrt(2 * g * self.h) * e
        while v > 0.3 and len(out) < 30:
            out.append(out[-1] + 2 * v / g)
            v *= e
        return out

    def energy(self, t):
        y, v, _k = self.height(self.es[0], t)
        tot = max(1e-9, self.g * self.h)
        return 0.5 * v * v / tot, self.g * y / tot

    def sounds(self):
        out = []
        for e in self.es[:2]:
            out += [(tb, "knock") for tb in self.hits(e)[:6]]
        return out


# ---------------------------------------------------------------------------- pendulum and swing
class Pendulum(Exp):
    name, title = "pendulum", "Pendulum"

    def setup(self):
        ls = self.spec.get("lengths") or self.spec.get("length") or 1.0
        self.Ls = [max(0.1, min(5.0, float(v))) for v in _list(ls, [1.0])][:4]
        self.th0 = math.radians(_num(self.spec, "angle", 20.0, 1.0, 179.0))
        self.damp = _num(self.spec, "damping", 0.03, 0.0, 5.0)
        self.F = _num(self.spec, "drive", 0.0, 0.0, 50.0)            # a push in rhythm (x g/L)
        self.W = _num(self.spec, "drive_speed", 0.667, 0.05, 5.0)     # its rhythm (x the natural speed)
        if self.g <= 0:
            self.g = 9.81
        self.tables = {}

    def period(self, L):
        """small swings: T = 2π√(L/g); bigger swings take a bit longer"""
        return TAU * math.sqrt(L / self.g) * (1 + self.th0 ** 2 / 16.0 + 11 * self.th0 ** 4 / 3072.0)

    def table(self, L):
        """the REAL pendulum: θ'' = -(g/L)·sin θ - q·θ' + F·sin(Ωt)  (not the small-angle shortcut)"""
        tb = self.tables.get(L)
        if tb is None:
            w0 = math.sqrt(self.g / L)
            q, F, W = 2 * self.damp, self.F * w0 * w0, self.W * w0
            tb = Table(lambda t, y: [y[1], -w0 * w0 * math.sin(y[0]) - q * y[1] + F * math.sin(W * t)],
                       [self.th0, 0.0], min(60.0, self.length() + 2), dt=min(0.004, 0.02 / w0))
            self.tables[L] = tb
        return tb

    def theta(self, L, t):
        th, om = self.table(L).at(t)
        if self.F > 0:                                   # driven: it may go over the top - keep the angle readable
            th = (th + math.pi) % TAU - math.pi
        return th, om

    def energy(self, t):
        L = self.Ls[0]
        th, om = self.theta(L, t)
        ke = 0.5 * (L * om) ** 2
        pe = self.g * L * (1 - math.cos(th))
        tot = max(1e-9, self.g * L * (1 - math.cos(self.th0)), ke + pe)
        return ke / tot, pe / tot

    def sounds(self):
        return [] if self.name == "swing" else [(0.0, "whoosh")]

    def length(self):
        return min(30.0, (6 if self.F > 0 else 3) * TAU * math.sqrt(max(self.Ls) / self.g) + 1)

    def size(self):
        Lm = max(self.Ls) * M
        return max(300.0, 2 * Lm * min(1.0, math.sin(min(self.th0, 1.57))) + 200 * len(self.Ls)), \
            Lm * (2.0 if self.F > 0 or self.th0 > 1.57 else 1.0) + 120

    def draw(self, pen, t):
        Lm = max(self.Ls) * M
        top = Lm + 70
        n = len(self.Ls)
        w = max(260.0, 2 * Lm * math.sin(self.th0) + 120) + 60 * (n - 1)
        frame(pen, w, top)
        cols = [RED, BLUE, GREEN, YELLOW]
        for i, L in enumerate(self.Ls):
            z = (i - (n - 1) / 2) * 50
            th, om = self.theta(L, t)
            px, py = 0.0, top
            bx, by = px + L * M * math.sin(th), py - L * M * math.cos(th)
            if self.name == "swing":
                pen.line([(px - 30, py, z), (bx - 30, by, z)], c="#7a5a3a", w=3)
                pen.line([(px + 30, py, z), (bx + 30, by, z)], c="#7a5a3a", w=3)
                plank(pen, bx, by - 4, z, 90, 8, 40, th, c="wood")
                pen.sphere(bx, by + 40, z, r=16, c="#e0ac69", rings=5, sides=8)            # a child sitting
                pen.box(bx, by + 4, z, w=34, h=34, d=24, c=cols[i % 4])
            else:
                if self.spec.get("trail", True):
                    def one(p_, tt, al, L=L, z=z, c=cols[i % 4]):
                        th2, _ = self.theta(L, tt)
                        p_.sphere(px + L * M * math.sin(th2), py - L * M * math.cos(th2), z, r=18,
                                  c=ghost_c(c, al), rings=4, sides=8)
                    ghosts(pen, one, t, n=4, step=0.045)
                pen.line([(px, py, z), (bx, by, z)], c="#dddddd", w=2.5)
                pen.sphere(bx, by, z, r=20, c=cols[i % 4], rings=6, sides=10)
                if self.spec.get("arrows", True) and abs(om) > 0.05:
                    v = om * L * 60
                    arrow(pen, (bx, by, z - 25), (bx + v * math.cos(th), by + v * math.sin(th), z - 25), ARROW_V, r=3)
        if self.spec.get("ruler", True):
            dashed(pen, (0, top, 20), (0, top - max(self.Ls) * M - 30, 20), c="#ffffff")

    def values(self, t):
        out = [("g", f"{self.g:.2f} m/s²")]
        for L in self.Ls:
            th, _ = self.theta(L, t)
            out.append((f"L = {L:g} m", f"T = {self.period(L):.2f} s, angle {math.degrees(th):+.0f}°"))
        out.append(("T", "= 2π√(L/g)" + (" (+ a push in rhythm)" if self.F > 0 else "")))
        return out

    def graph(self):
        if self.spec.get("phase") or self.F > 0:          # phase space: angle against speed (chaos shows here)
            L = self.Ls[0]
            wmax = max(abs(y[1]) for y in self.table(L).ys) or 1.0
            return {"kind": "xy", "xl": "angle", "yl": "speed", "fx": lambda t: math.degrees(self.theta(L, t)[0]),
                    "fy": lambda t: self.theta(L, t)[1], "xmax": 180.0 if self.F > 0 else math.degrees(self.th0) * 1.1,
                    "ymax": wmax * 1.1, "col": RED}
        return ("time (s)", "angle (°)", lambda t: [math.degrees(self.theta(L, t)[0]) for L in self.Ls],
                math.degrees(min(self.th0, math.pi)), [RED, BLUE, GREEN, YELLOW][:len(self.Ls)])


class Swing(Pendulum):
    name, title = "swing", "A swing (jhoola)"

    def setup(self):
        super().setup()
        if not self.spec.get("length") and not self.spec.get("lengths"):
            self.Ls = [2.0]


# ---------------------------------------------------------------------------- spring and mass
class Spring(Exp):
    name, title = "spring", "Spring and mass"

    def setup(self):
        self.k = _num(self.spec, "k", 20.0, 0.5, 5000.0, "stiffness")
        self.m = _num(self.spec, "mass", 0.5, 0.01, 200.0, "m")
        self.A = _num(self.spec, "pull", 0.15, 0.0, 1.0, "amplitude")
        self.z = _num(self.spec, "damping", 0.04, 0.0, 1.5)
        self.w0 = math.sqrt(self.k / self.m)
        self.L0 = 0.5
        self.stretch = (self.m * (self.g or 9.81)) / self.k

    def disp(self, t):
        wd = self.w0 * math.sqrt(max(1e-6, 1 - self.z ** 2))
        e = math.exp(-self.z * self.w0 * t)
        return -self.A * e * math.cos(wd * t), self.A * e * wd * math.sin(wd * t)

    def length(self):
        return min(30.0, 4 * TAU / self.w0 + 1)

    def size(self):
        return 300.0, (self.L0 + self.stretch + self.A) * M + 200

    def draw(self, pen, t):
        top = (self.L0 + min(self.stretch, 1.2) + self.A + 0.4) * M + 60
        frame(pen, 240, top)
        x, v = self.disp(t)
        Lnow = (self.L0 + min(self.stretch, 1.2)) * M - x * M
        pts = []
        turns = 12
        for i in range(turns * 10 + 1):
            u = i / (turns * 10)
            a = TAU * turns * u
            pts.append((14 * math.cos(a), top - Lnow * u, 14 * math.sin(a)))
        pen.line(pts, c="#c0c6cc", w=3)
        mh = 30 + 10 * min(4.0, self.m)
        pen.box(0, top - Lnow - mh, 0, w=mh, h=mh, d=mh, c=BLUE)
        if self.spec.get("ruler", True):
            dashed(pen, (-80, top - (self.L0 + min(self.stretch, 1.2)) * M, 0),
                   (80, top - (self.L0 + min(self.stretch, 1.2)) * M, 0), c="#ffd166", n=10)
        if self.spec.get("arrows", True):
            f = -self.k * x
            y0 = top - Lnow - mh / 2
            arrow(pen, (mh / 2 + 30, y0, -10), (mh / 2 + 30, y0 + max(-150, min(150, f * 8)), -10), ARROW_F, r=3)

    def energy(self, t):
        x, v = self.disp(t)
        ke, pe = 0.5 * self.m * v * v, 0.5 * self.k * x * x
        tot = max(1e-9, 0.5 * self.k * self.A ** 2)
        return ke / tot, pe / tot

    def values(self, t):
        x, v = self.disp(t)
        return [("k", f"{self.k:g} N/m"), ("mass", f"{self.m:g} kg"), ("stretch", f"{x * 100:+.1f} cm"),
                ("speed", f"{abs(v):.2f} m/s"), ("T = 2π√(m/k)", f"{TAU / self.w0:.2f} s")]

    def graph(self):
        return ("time (s)", "stretch (cm)", lambda t: self.disp(t)[0] * 100, self.A * 100, [BLUE])


# ---------------------------------------------------------------------------- down a slope (friction)
class Slope(Exp):
    name, title = "slope", "Down a slope"
    MU = {"ice": 0.03, "glass": 0.1, "wood": 0.3, "cardboard": 0.35, "sand": 0.55, "rubber": 0.85, "carpet": 0.6}
    COL = {"ice": "#cfeaf7", "glass": "#a8d8e8", "wood": "#b07d4f", "cardboard": "#c8a070", "sand": "#e3c27a",
           "rubber": "#3a3a3a", "carpet": "#8a2b3a", "ball": "#888888"}

    def setup(self):
        self.ang = math.radians(_num(self.spec, "angle", 25.0, 2.0, 70.0))
        self.L = _num(self.spec, "length", 3.0, 0.5, 20.0)
        self.lanes = _list(self.spec.get("surfaces", self.spec.get("objects")), ["ice", "wood", "sand"])[:4]
        if self.g <= 0:
            self.g = 9.81

    def acc(self, s):
        if s == "ball":
            return 5.0 / 7.0 * self.g * math.sin(self.ang)
        mu = self.MU.get(s, 0.3)
        a = self.g * (math.sin(self.ang) - mu * math.cos(self.ang))
        return max(0.0, a)

    def dist(self, s, t):
        a = self.acc(s)
        if a <= 0:
            return 0.0, 0.0
        T = math.sqrt(2 * self.L / a)
        tt = min(t, T)
        return 0.5 * a * tt * tt, (a * tt if t < T else 0.0)

    def length(self):
        ts = [math.sqrt(2 * self.L / self.acc(s)) for s in self.lanes if self.acc(s) > 0] or [3.0]
        return min(30.0, max(ts) + 1.5)

    def size(self):
        return self.L * M * math.cos(self.ang) + 200, self.L * M * math.sin(self.ang) + 100

    def draw(self, pen, t):
        Lx, Ly = self.L * M * math.cos(self.ang), self.L * M * math.sin(self.ang)
        x0 = -Lx / 2
        n = len(self.lanes)
        for i, s in enumerate(self.lanes):
            z = (i - (n - 1) / 2) * 90
            c = self.COL.get(s, "#b07d4f")
            hz = 40
            # the ramp: a wedge (top face in the lane's surface)
            pen.poly([(x0, Ly, z - hz), (x0 + Lx, 0, z - hz), (x0 + Lx, 0, z + hz), (x0, Ly, z + hz)], c=c)
            pen.poly([(x0, 0, z - hz), (x0 + Lx, 0, z - hz), (x0, Ly, z - hz)], c="#8b6b4a")
            pen.poly([(x0, 0, z + hz), (x0 + Lx, 0, z + hz), (x0, Ly, z + hz)], c="#8b6b4a")
            pen.poly([(x0, 0, z - hz), (x0, 0, z + hz), (x0, Ly, z + hz), (x0, Ly, z - hz)], c="#7a5a3a")
            d, v = self.dist(s, t)
            u = d / self.L
            px, py = x0 + Lx * u, Ly * (1 - u)
            nx, ny = math.sin(self.ang), math.cos(self.ang)             # out of the slope
            if s == "ball":
                pen.sphere(px + nx * 18, py + ny * 18, z, r=18, c=RED, rings=6, sides=10)
            else:
                pen.push()
                pen.move(px + nx * 16, py + ny * 16, z)
                pen.rotate_z(-math.degrees(self.ang))
                pen.box(0, -16, 0, w=44, h=32, d=40, c=BLUE if i % 2 else "#e76f51")
                pen.pop()
            if self.spec.get("arrows", True) and v > 0.05:
                a = (px + nx * 40, py + ny * 40, z - 30)
                arrow(pen, a, (a[0] + v * 25 * math.cos(self.ang), a[1] - v * 25 * math.sin(self.ang), a[2]), ARROW_V, r=3)

    def values(self, t):
        out = [("slope", f"{math.degrees(self.ang):.0f}°, {self.L:g} m")]
        for s in self.lanes:
            d, v = self.dist(s, t)
            mu = "" if s == "ball" else f" μ={self.MU.get(s, 0.3):.2f}"
            out.append((f"{s}{mu}", f"a={self.acc(s):.2f} m/s², {d:.2f} m"))
        return out

    def graph(self):
        return ("time (s)", "distance (m)", lambda t: [self.dist(s, t)[0] for s in self.lanes], self.L,
                [self.COL.get(s, RED) if s != "ice" else "#5fb0d8" for s in self.lanes])


class InclinedPlane(Slope):
    name, title = "inclined_plane", "Inclined plane: less force, longer way"

    def setup(self):
        super().setup()
        self.m = _num(self.spec, "mass", 20.0, 0.1, 1000.0)
        self.lanes = ["wood"]

    def dist(self, s, t):
        v = 0.5
        d = min(self.L, v * t)
        return self.L - d, (v if d < self.L else 0.0)

    def values(self, t):
        lift = self.m * self.g
        push = self.m * self.g * math.sin(self.ang)
        return [("mass", f"{self.m:g} kg"), ("lift straight up", f"{lift:.0f} N"),
                ("push up the slope", f"{push:.0f} N"), ("slope", f"{math.degrees(self.ang):.0f}°")]

    def graph(self):
        return None


# ---------------------------------------------------------------------------- collisions, Newton's cradle
class Collision(Exp):
    name, title = "collision", "Two carts collide"

    def setup(self):
        self.m1 = _num(self.spec, "m1", 1.0, 0.05, 1000.0)
        self.m2 = _num(self.spec, "m2", 1.0, 0.05, 1000.0)
        self.v1 = _num(self.spec, "v1", 1.5, -20, 20)
        self.v2 = _num(self.spec, "v2", 0.0, -20, 20)
        e = self.spec.get("e", self.spec.get("bounce", 1.0))
        self.e = {"elastic": 1.0, "sticky": 0.0, "inelastic": 0.0}.get(str(e).lower(), None)
        if self.e is None:
            self.e = _num(self.spec, "e", 1.0, 0.0, 1.0)
        self.w1 = 0.42 * self.m1 ** (1 / 3.0)
        self.w2 = 0.42 * self.m2 ** (1 / 3.0)
        self.gap = _num(self.spec, "gap", 1.5, 0.2, 10)
        self.x1, self.x2 = -self.gap / 2 - self.w1, self.gap / 2
        rel = self.v1 - self.v2
        self.tc = self.gap / rel if rel > 1e-6 else 1e9
        P = self.m1 * self.v1 + self.m2 * self.v2
        self.u1 = (P - self.m2 * self.e * (self.v1 - self.v2)) / (self.m1 + self.m2)
        self.u2 = (P + self.m1 * self.e * (self.v1 - self.v2)) / (self.m1 + self.m2)

    def at(self, t):
        if t < self.tc:
            return self.x1 + self.v1 * t, self.x2 + self.v2 * t, self.v1, self.v2
        a1 = self.x1 + self.v1 * self.tc
        a2 = self.x2 + self.v2 * self.tc
        d = t - self.tc
        return a1 + self.u1 * d, a2 + self.u2 * d, self.u1, self.u2

    def length(self):
        return min(20.0, (self.tc if self.tc < 1e8 else 0) + 3.0)

    def size(self):
        return 4.4 * M, 200.0

    def draw(self, pen, t):
        span = 2.2 * M
        pen.box(0, 0, 0, w=2 * span + 200, h=10, d=90, c="#6b6f76")
        for zz in (-30, 30):
            pen.box(0, 10, zz, w=2 * span + 200, h=4, d=6, c="#c0c6cc")
        p1, p2, v1, v2 = self.at(t)
        for p, w, m, col, v in ((p1, self.w1, self.m1, RED, v1), (p2, self.w2, self.m2, BLUE, v2)):
            x = max(-span, min(span, p * M)) + w * M / 2
            h = w * M * 0.7
            pen.round_box(x, 22, 0, w=w * M, h=h, d=70, c=col, r=8)
            for wx in (-w * M * 0.3, w * M * 0.3):
                for zz in (-38, 38):
                    pen.cylinder_axis(x + wx, 22, zz, 12, 6, "#222222", axis="z")
            if self.spec.get("arrows", True) and abs(v) > 0.02:
                arrow(pen, (x, 22 + h + 20, 0), (x + v * 60, 22 + h + 20, 0), ARROW_V, r=4)
        if self.tc < 1e8:                                  # where they hit: a little burst
            hx = (self.x1 + self.v1 * self.tc + self.w1) * M
            puff(pen, hx, 60, 0, t - self.tc, c="#ffe066", n=12, size=4, spread=50)

    def sounds(self):
        return [(self.tc, "clap")] if self.tc < 1e8 else []

    def values(self, t):
        p1, p2, v1, v2 = self.at(t)
        P0 = self.m1 * self.v1 + self.m2 * self.v2
        return [("red", f"{self.m1:g} kg, {v1:+.2f} m/s"), ("blue", f"{self.m2:g} kg, {v2:+.2f} m/s"),
                ("momentum p = m·v", f"{self.m1 * v1 + self.m2 * v2:+.2f} kg·m/s (start {P0:+.2f})"),
                ("bounciness e", f"{self.e:.2f}")]

    def graph(self):
        vm = max(abs(self.v1), abs(self.v2), abs(self.u1), abs(self.u2), 0.5)
        return ("time (s)", "speed (m/s)", lambda t: [self.at(t)[2], self.at(t)[3]], vm, [RED, BLUE])


class Cradle(Exp):
    name, title = "newtons_cradle", "Newton's cradle"

    def setup(self):
        self.n = int(_num(self.spec, "balls", 5, 3, 7))
        self.th0 = math.radians(_num(self.spec, "angle", 30, 5, 60))
        self.L = _num(self.spec, "length", 0.5, 0.2, 2.0)
        self.T = TAU * math.sqrt(self.L / (self.g or 9.81))

    def angles(self, t):
        a = self.th0 * math.exp(-0.05 * t) * math.cos(TAU * t / self.T)
        return (min(0.0, -a) if a > 0 else 0.0), (max(0.0, -a) if a < 0 else 0.0)

    def length(self):
        return 8.0

    def size(self):
        return 400.0, self.L * M + 120

    def draw(self, pen, t):
        r = 22
        top = self.L * M + 60
        frame(pen, self.n * 2 * r + 120, top)
        left, right = self.angles(t)
        for i in range(self.n):
            px = (i - (self.n - 1) / 2) * 2 * r
            th = left if i == 0 else (right if i == self.n - 1 else 0.0)
            bx, by = px + self.L * M * math.sin(th), top - self.L * M * math.cos(th)
            for zz in (-30, 30):
                pen.line([(px, top, zz), (bx, by, 0)], c="#dddddd", w=1.5)
            pen.sphere(bx, by, 0, r=r, c="#c0c8d0", rings=6, sides=10)

    def values(self, t):
        return [("balls", str(self.n)), ("energy and momentum", "pass through the middle balls")]


# ---------------------------------------------------------------------------- floating and sinking
class Buoyancy(Exp):
    name, title = "buoyancy", "Floating and sinking"
    RHO = {"wood": 600, "cork": 240, "ice": 917, "plastic": 950, "apple": 850, "stone": 2600, "iron": 7870,
           "coin": 8900, "egg": 1030}
    COL = {"wood": "#b07d4f", "cork": "#c8a070", "ice": "#dff3fb", "plastic": "#ff8fab", "apple": "#d62828",
           "stone": "#7d7a74", "iron": "#5a5f66", "coin": "#e0b030", "egg": "#f5ecd8"}

    def setup(self):
        self.objs = _list(self.spec.get("objects"), ["wood", "ice", "stone"])[:5]
        self.rho_w = 1025.0 if str(self.spec.get("water", "")).lower() in ("sea", "salt", "salty") else 1000.0
        self.load = str(self.spec.get("mode", "")).lower() == "boat"

    def length(self):
        return 8.0

    def size(self):
        return 160.0 * max(3, len(self.objs)) + 100, 300.0

    def depth(self, o, t):
        """(y of the object's bottom in m, frac under water)"""
        Hw, s = 1.0, 0.25
        rho = self.RHO.get(o, 1000.0)
        if rho < self.rho_w:
            f = rho / self.rho_w
            eq = Hw - f * s
        else:
            f = 1.0
            eq = 0.0
        y0 = Hw + 0.35
        if rho >= self.rho_w:                                      # sinks: slows in the water
            if t < 0.27:
                return y0 - 0.5 * 9.81 * t * t, f
            tt = t - 0.27
            v = 0.9 * (1 - self.rho_w / rho) ** 0.5
            return max(eq, Hw - 0.0 - v * tt - 0.02), f
        k = math.exp(-1.6 * t)
        return eq + (y0 - eq) * k * math.cos(3.2 * t), f

    def draw(self, pen, t):
        n = max(3, len(self.objs))
        W, D, H = 160 * n, 220, 1.0 * M + 60
        # the glass tank
        glass = pen.material("#cfe8f5", roughness=0.1, transparency=0.75)
        pen.box(0, 0, 0, w=W, h=8, d=D, c="#3a4a5a")
        for (x, w, z, d) in ((-W / 2, 6, 0, D), (W / 2, 6, 0, D)):
            pen.box(x, 0, z, w=w, h=H, d=d, c=glass)
        pen.box(0, 0, D / 2, w=W, h=H, d=6, c=glass)
        water = pen.material("#3a86c8", roughness=0.2, transparency=0.45)
        pen.box(0, 8, 0, w=W - 8, h=1.0 * M - 8, d=D - 8, c=water)
        for i, o in enumerate(self.objs):
            x = -W / 2 + 80 + 160 * i
            y, f = self.depth(o, t)
            s = 0.25 * M
            pen.box(x, max(8, y * M), 0, w=s, h=s, d=s, c=self.COL.get(o, "#888"))
            age = t - 0.27
            if 0 <= age < 1.2:                             # it hits the water: rings and spray
                for k in range(2):
                    rr = 20 + (age - k * 0.25) * 140
                    if rr > 20:
                        ring(pen, x, 1.0 * M + 2, 0, rr, c=(1, 1, 1, max(0.0, 0.8 - age * 0.7)), w=2, n=24)
                puff(pen, x, 1.0 * M, 0, age, c="#dff3ff", n=10, size=4, spread=45)
        pen.box(0, H - 2, -D / 2, w=W, h=4, d=4, c=glass)

    def sounds(self):
        return [(0.27, "splash")]

    def values(self, t):
        out = [("water", f"{self.rho_w:.0f} kg/m³")]
        for o in self.objs:
            rho = self.RHO.get(o, 1000.0)
            out.append((o, f"{rho} kg/m³ - " + (f"floats, {100 * rho / self.rho_w:.0f}% under" if rho < self.rho_w
                                                  else "sinks")))
        return out


class BoatLoad(Exp):
    name, title = "boat_load", "A boat with more and more load"

    def setup(self):
        self.cap = _num(self.spec, "capacity", 6, 1, 20)
        self.every = _num(self.spec, "every", 1.2, 0.3, 5)

    def length(self):
        return self.every * (self.cap + 2) + 2

    def size(self):
        return 500.0, 260.0

    def draw(self, pen, t):
        n = int(t / self.every)
        water = pen.material("#3a86c8", roughness=0.2, transparency=0.35)
        pen.box(0, 0, 0, w=700, h=60, d=300, c=water)
        sink = min(1.0, n / self.cap)
        over = n > self.cap
        y = 60 - 15 - 40 * sink - (min(120.0, (t - (self.cap + 1) * self.every) * 80) if over else 0)
        pen.round_box(0, y, 0, w=320, h=60, d=130, c="#8b5a2b", r=12)
        for i in range(min(n, self.cap + 1)):
            pen.box(-120 + (i % 4) * 80, y + 60, -30 + (i // 4) * 50, w=60, h=40, d=40, c="#d9bf8a")

    def values(self, t):
        n = int(t / self.every)
        return [("sacks", str(n)), ("boat holds", f"{self.cap:g} sacks"),
                ("", "sinks!" if n > self.cap else "floats (it pushes away its weight in water)")]


# ---------------------------------------------------------------------------- lever, pulley
class Lever(Exp):
    name, title = "lever", "Lever (see-saw)"

    def setup(self):
        self.m1 = _num(self.spec, "m1", 10, 0.1, 500)
        self.d1 = _num(self.spec, "d1", 1.0, 0.1, 5)
        self.m2 = _num(self.spec, "m2", 5, 0.1, 500)
        self.d2 = _num(self.spec, "d2", 2.0, 0.1, 5)

    def tilt(self, t):
        tq = self.m1 * self.d1 - self.m2 * self.d2
        if abs(tq) < 1e-6 * (self.m1 * self.d1 + self.m2 * self.d2):
            target = 0.0
        else:
            target = math.radians(14) * (1 if tq > 0 else -1)
        k = 1 - math.exp(-2.2 * max(0.0, t - 0.8)) * math.cos(4 * max(0.0, t - 0.8)) if t > 0.8 else 0.0
        return target * k

    def length(self):
        return 5.0

    def size(self):
        return (self.d1 + self.d2) * M + 200, 260.0

    def draw(self, pen, t):
        H = 90
        pen.poly([(-50, 0, -40), (50, 0, -40), (0, H, -40)], c="#7a5a3a")
        pen.poly([(-50, 0, 40), (50, 0, 40), (0, H, 40)], c="#7a5a3a")
        pen.poly([(-50, 0, -40), (0, H, -40), (0, H, 40), (-50, 0, 40)], c="#8b6b4a")
        pen.poly([(50, 0, -40), (0, H, -40), (0, H, 40), (50, 0, 40)], c="#8b6b4a")
        a = self.tilt(t)                                 # + = left side down
        L = (max(self.d1, self.d2) + 0.3) * M
        plank(pen, 0, H + 6, 0, 2 * L, 12, 70, -a, c="wood")
        for d, m, side, col in ((self.d1, self.m1, -1, RED), (self.d2, self.m2, 1, BLUE)):
            px = side * d * M * math.cos(a)
            py = H + 12 - side * d * M * math.sin(a)
            s = 30 + 14 * m ** (1 / 3.0)
            pen.box(px, py, 0, w=s, h=s, d=s, c=col)
            arrow(pen, (px, py - 6, -50), (px, py - 6 - 30 - 6 * m ** 0.5, -50), ARROW_F, r=3)

    def values(self, t):
        a, b = self.m1 * self.d1, self.m2 * self.d2
        res = "balanced" if abs(a - b) < 1e-6 * (a + b) else ("left goes down" if a > b else "right goes down")
        return [("left", f"{self.m1:g} kg × {self.d1:g} m = {a:g}"), ("right", f"{self.m2:g} kg × {self.d2:g} m = {b:g}"),
                ("", res)]


class Pulley(Exp):
    name, title = "pulley", "Pulley: a bucket from the well"

    def setup(self):
        self.m = _num(self.spec, "mass", 10, 0.1, 500)
        self.n = int(_num(self.spec, "ropes", 1, 1, 4))
        self.depth = _num(self.spec, "depth", 3.0, 0.5, 20)
        self.v = _num(self.spec, "speed", 0.6, 0.05, 5)

    def length(self):
        return self.depth / self.v + 2

    def size(self):
        return 400.0, 360.0

    def draw(self, pen, t):
        pen.cylinder(0, 0, 0, r=90, h=90, c="#9a9a92", sides=16)
        pen.cylinder(0, 0, 0, r=72, h=92, c="#2a2f35", sides=16)
        top = 330
        for x in (-95, 95):
            pen.box(x, 0, 0, w=14, h=top, d=14, c="#6b4528")
        pen.tube([(-100, top, 0), (100, top, 0)], 6, c="#6b4528", sides=6, smooth=False)
        pen.wheel(0, top - 26, 0, r=24, c="#8b5a2b", w=10, spokes=6, turn=-t * 4)
        up = min(self.depth, self.v * t)
        by = 90 - (self.depth - up) * 50 if up < self.depth else 110
        by = max(-200, by)
        pen.line([(0, top - 26, 0), (0, by + 50, 0)], c="#c8a070", w=3)
        pen.line([(24, top - 26, 0), (150, 90, 0)], c="#c8a070", w=3)
        if by > 80:
            pen.cylinder(0, by, 0, r=26, h=46, c="#8a8f96", r2=30, sides=12)
        arrow(pen, (150, 90, -20), (150 + 30, 90 - 60, -20), ARROW_F, r=3)

    def values(self, t):
        up = min(self.depth, self.v * t)
        return [("bucket", f"{self.m:g} kg = {self.m * 9.81:.0f} N"), ("ropes holding it", str(self.n)),
                ("pull needed", f"{self.m * 9.81 / self.n:.0f} N"), ("raised", f"{up:.1f} of {self.depth:g} m")]


# ---------------------------------------------------------------------------- going round
class Circular(Exp):
    name, title = "circular", "A stone on a rope"

    def setup(self):
        self.r = _num(self.spec, "radius", 1.0, 0.2, 5)
        self.T = _num(self.spec, "period", 1.2, 0.2, 20)
        self.release = self.spec.get("release")
        self.release = None if self.release is None else float(self.release)
        self.m = _num(self.spec, "mass", 0.2, 0.01, 50)

    def at(self, t):
        w = TAU / self.T
        if self.release is not None and t > self.release:
            a = w * self.release
            x0, z0 = self.r * math.cos(a), self.r * math.sin(a)
            vx, vz = -self.r * w * math.sin(a), self.r * w * math.cos(a)
            d = t - self.release
            return x0 + vx * d, z0 + vz * d, vx, vz, True
        a = w * t
        return self.r * math.cos(a), self.r * math.sin(a), -self.r * w * math.sin(a), self.r * w * math.cos(a), False

    def length(self):
        return 8.0

    def size(self):
        return 2 * self.r * M + 200, 260.0

    def draw(self, pen, t):
        H = 1.3 * M
        pen.tube([(0, 0, 0), (0, H, 0)], 8, c="#6b4528", sides=6)
        x, z, vx, vz, free = self.at(t)
        if not free:
            pen.line([(0, H, 0), (x * M, H, z * M)], c="#c8a070", w=3)
        ring(pen, 0, H - 1, 0, self.r * M, c="#ffffff", w=1.5)
        pen.sphere(x * M, H, z * M, r=20, c="#7d7a74", rings=6, sides=10)
        if self.spec.get("arrows", True):
            arrow(pen, (x * M, H + 26, z * M), (x * M + vx * 40, H + 26, z * M + vz * 40), ARROW_V, r=4)
            if not free:
                arrow(pen, (x * M, H + 10, z * M), (x * M * 0.55, H + 10, z * M * 0.55), ARROW_F, r=4)

    def values(self, t):
        v = TAU * self.r / self.T
        return [("radius", f"{self.r:g} m"), ("one turn", f"{self.T:g} s"), ("speed", f"{v:.2f} m/s"),
                ("pull to the middle", f"m·v²/r = {self.m * v * v / self.r:.1f} N")]


class MerryGoRound(Exp):
    name, title = "merry_go_round", "Merry-go-round"

    def setup(self):
        self.r = _num(self.spec, "radius", 1.5, 0.5, 5)
        self.T = _num(self.spec, "period", 4.0, 0.5, 30)

    def length(self):
        return 8.0

    def size(self):
        return 2 * self.r * M + 100, 200.0

    def draw(self, pen, t):
        a = TAU * t / self.T
        R = self.r * M
        pen.cylinder(0, 0, 0, r=R, h=24, c="#e76f51", sides=24)
        pen.tube([(0, 24, 0), (0, 160, 0)], 8, c="#c0c6cc", sides=6)
        for k in range(4):
            b = a + TAU * k / 4
            x, z = R * 0.8 * math.cos(b), R * 0.8 * math.sin(b)
            pen.tube([(x, 24, z), (x, 120, z)], 4, c="#c0c6cc", sides=5)
            pen.sphere(x, 50, z, r=22, c=[RED, BLUE, GREEN, YELLOW][k], rings=5, sides=8)
            if k == 0 and self.spec.get("arrows", True):
                v = TAU * R / self.T * 0.25
                arrow(pen, (x, 90, z), (x - v * math.sin(b), 90, z + v * math.cos(b)), ARROW_V, r=4)

    def values(self, t):
        return [("radius", f"{self.r:g} m"), ("one turn", f"{self.T:g} s"),
                ("edge speed", f"{TAU * self.r / self.T:.2f} m/s"), ("middle", "0 m/s - the edge goes fastest")]


class Orbit(Exp):
    name, title = "orbit", "Sun, Earth and Moon"

    def setup(self):
        self.year = _num(self.spec, "year", 12.0, 2.0, 120.0)            # seconds for one Earth year in the video
        self.month = self.year / 12.37

    def length(self):
        return self.year

    def size(self):
        return 1300.0, 500.0

    def draw(self, pen, t):
        pen.sphere(0, 200, 0, r=90, c=pen.material("#ffcc33", emission=1.0), rings=8, sides=14)
        pen.glow(0, 200, 0, r=220, c="#ffb703", strength=0.6)
        R = 520
        ring(pen, 0, 200, 0, R, c="#8aa0b8", w=1.5, n=80)
        a = TAU * t / self.year
        ex, ez = R * math.cos(a), R * math.sin(a)
        pen.sphere(ex, 200, ez, r=34, c="#2a7ab8", rings=6, sides=12)
        pen.blob(ex + 6, 210, ez - 4, r=18, c="#3a9a4a")
        m = TAU * t / self.month
        pen.sphere(ex + 80 * math.cos(m), 200, ez + 80 * math.sin(m), r=11, c="#d0d0d0", rings=5, sides=8)
        ring(pen, ex, 200, ez, 80, c="#9a9a9a", w=1, n=30)

    def values(self, t):
        days = 365.25 * (t % self.year) / self.year
        return [("Earth", f"day {days:.0f} of 365"), ("Moon", f"{(t / self.month) % 1 * 29.5:.0f} days into its month"),
                ("", "the Moon goes round the Earth, the Earth round the Sun")]


# ---------------------------------------------------------------------------- light
class Shadow(Exp):
    name, title = "shadow", "Shadows move with the Sun"

    def setup(self):
        self.h = _num(self.spec, "height", 1.5, 0.2, 10)
        self.day = _num(self.spec, "seconds", 10.0, 2, 60)

    def sun(self, t):
        u = min(1.0, max(0.0, t / self.day))
        return math.radians(10 + 160 * u)                            # east -> overhead -> west

    def length(self):
        return self.day + 1

    def size(self):
        return 1200.0, 900.0

    def draw(self, pen, t):
        a = self.sun(t)
        el = math.sin(a) * math.radians(70)
        H = self.h * M
        pen.box(0, 0, 0, w=24, h=H, d=24, c="#8b5a2b")
        pen.box(0, 0, 0, w=900, h=2, d=300, c="#d9c8a0")
        L = H / max(0.06, math.tan(el)) if el > 0.02 else 1500
        L = min(L, 600)
        dirx = -math.cos(a)                                          # the shadow points away from the sun
        pen.poly([(-12, 3, -10), (12, 3, -10), (12 + dirx * L, 3, -10), (-12 + dirx * L, 3, -10)], c="#3a3a3a")
        sx, sy = 700 * math.cos(a), 150 + 650 * math.sin(a)
        pen.sphere(sx, sy, 200, r=50, c=pen.material("#ffcc33", emission=1.0), rings=6, sides=10)
        dashed(pen, (sx, sy, 200), (0, H, 0), c="#ffd166", n=16)

    def values(self, t):
        a = self.sun(t)
        el = math.degrees(math.sin(a) * math.radians(70))
        L = self.h / max(0.06, math.tan(math.radians(el)))
        return [("Sun height", f"{el:.0f}°"), ("pole", f"{self.h:g} m"), ("shadow", f"{min(L, 99):.2f} m")]


class Mirror(Exp):
    name, title = "mirror", "Reflection in a mirror"

    def setup(self):
        self.i = math.radians(_num(self.spec, "angle", 40, 5, 85))

    def length(self):
        return 5.0

    def size(self):
        return 700.0, 450.0

    def draw(self, pen, t):
        glass = pen.material("#d8eef8", roughness=0.05, metallic=0.9)
        pen.box(0, 0, 0, w=500, h=12, d=160, c=glass)
        u = min(1.0, t / 1.2)
        u2 = min(1.0, max(0.0, (t - 1.2) / 1.2))
        L = 380
        p0 = (-L * math.sin(self.i), 12 + L * math.cos(self.i), 0)
        hit = (0, 12, 0)
        p1 = (p0[0] + (hit[0] - p0[0]) * u, p0[1] + (hit[1] - p0[1]) * u, 0)
        pen.tube([p0, p1], 5, c="#ffd166", sides=6, smooth=False)
        if u2 > 0:
            q = (L * math.sin(self.i) * u2, 12 + L * math.cos(self.i) * u2, 0)
            pen.tube([hit, q], 5, c="#ffd166", sides=6, smooth=False)
        dashed(pen, (0, 12, -2), (0, 420, -2), c="#ffffff")

    def values(self, t):
        d = math.degrees(self.i)
        return [("light comes in at", f"{d:.0f}°"), ("goes out at", f"{d:.0f}°"), ("", "angle in = angle out")]


class Prism(Exp):
    name, title = "prism", "A prism makes a rainbow"
    COLS = ["#e63946", "#f77f00", "#ffd60a", "#2a9d48", "#3a86ff", "#4b3fae", "#8338ec"]

    def length(self):
        return 5.0

    def size(self):
        return 900.0, 420.0

    def draw(self, pen, t):
        glass = pen.material("#e8f6ff", roughness=0.05, transparency=0.55)
        s = 160
        tri = [(-s, 0), (s, 0), (0, s * 1.6)]
        for zz in (-70, 70):
            pen.poly([(x, y + 20, zz) for x, y in tri], c=glass)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            pa, pb = tri[a], tri[b]
            pen.poly([(pa[0], pa[1] + 20, -70), (pb[0], pb[1] + 20, -70), (pb[0], pb[1] + 20, 70),
                      (pa[0], pa[1] + 20, 70)], c=glass)
        pen.box(0, 0, 0, w=420, h=20, d=200, c="#3a3a3a")
        u = min(1.0, t / 1.0)
        p0 = (-480, 120, 0)
        hit = (-s * 0.55, 20 + s * 1.6 * 0.45, 0)
        pen.tube([p0, (p0[0] + (hit[0] - p0[0]) * u, p0[1] + (hit[1] - p0[1]) * u, 0)], 6, c="#ffffff", sides=6,
                 smooth=False)
        if t > 1.0:
            out = (s * 0.5, 20 + s * 1.6 * 0.5, 0)
            pen.tube([hit, out], 4, c="#f4f4f4", sides=5, smooth=False)
            u2 = min(1.0, (t - 1.0) / 1.2)
            for k, c in enumerate(self.COLS):
                ang = math.radians(-12 - 4.5 * k)
                L = 420 * u2
                q = (out[0] + L * math.cos(ang), out[1] + L * math.sin(ang), 0)
                pen.tube([out, q], 4, c=c, sides=5, smooth=False)

    def values(self, t):
        return [("white light", "is all the colours together"), ("the glass", "bends violet most, red least"),
                ("", "VIBGYOR")]


# ---------------------------------------------------------------------------- waves
class Ripples(Exp):
    name, title = "ripples", "Ripples in a pond"

    def setup(self):
        self.v = _num(self.spec, "speed", 0.5, 0.05, 5)
        self.every = _num(self.spec, "every", 1.5, 0.3, 10)

    def length(self):
        return 8.0

    def size(self):
        return 900.0, 120.0

    def draw(self, pen, t):
        pen.water(w=900, d=700, x=0, z=0, y=1.0, t=t)
        n = int(t / self.every) + 1
        for k in range(n):
            age = t - k * self.every
            if age < 0:
                continue
            r = self.v * age * M
            if r > 440:
                continue
            a = max(0.15, 1 - r / 440)
            c = "#%02x%02x%02x" % (int(200 + 55 * a), int(225 + 30 * a), 255)
            ring(pen, 0, 3, 0, max(4, r), c=c, w=3 * a + 1, n=48)
        if t % self.every < 0.25:
            pen.sphere(0, 30 - 120 * (t % self.every), 0, r=10, c="#7d7a74")

    def values(self, t):
        return [("wave speed", f"{self.v:g} m/s"), ("a drop every", f"{self.every:g} s"),
                ("wavelength", f"{self.v * self.every:.2f} m")]


class RopeWave(Exp):
    name, title = "rope_wave", "A wave on a rope"

    def setup(self):
        self.L = _num(self.spec, "length", 4.0, 1, 10)
        self.A = _num(self.spec, "amplitude", 0.25, 0.02, 1.0)
        self.f = _num(self.spec, "frequency", 1.0, 0.1, 5)
        self.v = _num(self.spec, "speed", 2.0, 0.2, 10)

    def y(self, x, t):
        if x > self.v * t:
            return 0.0
        return self.A * math.sin(TAU * self.f * (t - x / self.v))

    def length(self):
        return 6.0

    def size(self):
        return self.L * M + 120, 300.0

    def draw(self, pen, t):
        H = 120
        x0 = -self.L * M / 2
        pen.box(x0 - 20, 0, 0, w=20, h=H + 60, d=20, c="#6b4528")
        pen.box(-x0 + 20, 0, 0, w=20, h=H + 60, d=20, c="#6b4528")
        pts = []
        n = 80
        for i in range(n + 1):
            xm = self.L * i / n
            pts.append((x0 + xm * M, H + self.y(xm, t) * M, 0))
        pen.tube(pts, 5, c="#e76f51", sides=6, smooth=False)
        pen.sphere(x0, H + self.y(0, t) * M, 0, r=12, c=BLUE, rings=5, sides=8)

    def values(self, t):
        return [("frequency", f"{self.f:g} Hz"), ("speed", f"{self.v:g} m/s"),
                ("wavelength λ = v / f", f"{self.v / self.f:.2f} m")]


class Sound(Exp):
    name, title = "sound", "Sound spreads in rings"

    def setup(self):
        self.every = _num(self.spec, "every", 0.6, 0.2, 5)

    def length(self):
        return 6.0

    def size(self):
        return 900.0, 400.0

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=40, h=120, d=40, c="#6b4528")
        pen.cylinder(0, 120, 0, r=40, h=60, c="#d4a017", r2=12, sides=14)
        n = int(t / self.every) + 1
        for k in range(n):
            age = t - k * self.every
            r = 343 / 300.0 * age * M * 0.6
            if r < 4 or r > 600:
                continue
            a = 1 - r / 600
            col = "#%02x%02x%02x" % (int(255 * a + 120 * (1 - a)), int(214 * a + 120 * (1 - a)), int(102 * a + 140 * (1 - a)))
            ring(pen, 0, 150, 0, r, c=col, w=2 + 2 * a, plane="xy", n=48)
            ring(pen, 0, 150, 0, r, c=col, w=1 + a, plane="xz", n=48)

    def values(self, t):
        return [("sound in air", "343 m/s"), ("", "it spreads out in every direction")]


# ---------------------------------------------------------------------------- from "Computational Physics with Python"
class Chaos(Pendulum):
    """a pendulum pushed in rhythm, with friction (ch. 5): the same start twice, a tiny bit apart - after a few
    swings they do completely different things (chaos). The graph shows angle against speed (phase space)."""
    name, title = "chaos", "Chaos: a pushed pendulum"

    def setup(self):
        sp = dict(self.spec)
        sp.setdefault("drive", 1.2)
        sp.setdefault("drive_speed", 0.667)
        sp.setdefault("damping", 0.25)
        sp.setdefault("angle", 10)
        self.spec = sp
        super().setup()
        self.Ls = [_num(sp, "length", 1.0, 0.2, 3.0)] * 2
        self.th0s = [self.th0, self.th0 + math.radians(_num(sp, "difference", 0.5, 0.001, 10.0))]

    def table(self, L, k=0):
        key = (L, k)
        tb = self.tables.get(key)
        if tb is None:
            w0 = math.sqrt(self.g / L)
            q, F, W = 2 * self.damp, self.F * w0 * w0, self.W * w0
            tb = Table(lambda t, y: [y[1], -w0 * w0 * math.sin(y[0]) - q * y[1] + F * math.sin(W * t)],
                       [self.th0s[k], 0.0], 62.0, dt=min(0.004, 0.02 / w0))
            self.tables[key] = tb
        return tb

    def theta(self, L, t, k=0):
        th, om = self.table(L, k).at(t)
        return (th + math.pi) % TAU - math.pi, om

    def length(self):
        return 20.0

    def size(self):
        return 2 * self.Ls[0] * M + 300, 2 * self.Ls[0] * M + 160

    def draw(self, pen, t):
        L = self.Ls[0]
        top = L * M + 90
        frame(pen, 2 * L * M + 160, top + L * M * 0 + 10)
        for k, (c, z) in enumerate(((RED, -30), (BLUE, 30))):
            def one(p_, tt, al, k=k, c=c, z=z):
                th2, _ = self.theta(L, tt, k)
                p_.sphere(L * M * math.sin(th2), top - L * M * math.cos(th2), z, r=16, c=ghost_c(c, al), rings=4, sides=8)
            ghosts(pen, one, t, n=5, step=0.04)
            th, om = self.theta(L, t, k)
            bx, by = L * M * math.sin(th), top - L * M * math.cos(th)
            pen.tube([(0, top, z), (bx, by, z)], 3, c="#c0c6cc", sides=5, smooth=False)       # a stiff rod
            pen.sphere(bx, by, z, r=20, c=c, rings=6, sides=10)

    def values(self, t):
        a1, _ = self.theta(self.Ls[0], t, 0)
        a2, _ = self.theta(self.Ls[0], t, 1)
        return [("red starts at", f"{math.degrees(self.th0s[0]):.1f}°"),
                ("blue starts at", f"{math.degrees(self.th0s[1]):.1f}° (just a tiny bit more)"),
                ("now", f"red {math.degrees(a1):+.0f}°, blue {math.degrees(a2):+.0f}°"),
                ("", "a tiny change at the start -> a big change later")]

    def graph(self):
        L = self.Ls[0]
        wmax = max(abs(y[1]) for y in self.table(L).ys) or 1.0
        return {"kind": "xy", "xl": "angle", "yl": "speed", "fx": lambda t: math.degrees(self.theta(L, t)[0]),
                "fy": lambda t: self.theta(L, t)[1], "xmax": 180.0, "ymax": wmax * 1.1, "col": RED,
                "fx2": lambda t: math.degrees(self.theta(L, t, 1)[0]), "fy2": lambda t: self.theta(L, t, 1)[1],
                "col2": BLUE}

    def energy(self, t):
        return None


class Diffusion(Exp):
    """a drop of ink in still water: every bit takes random little steps (a random walk, ch. 7) and the drop
    spreads out - the spread grows like √t"""
    name, title = "diffusion", "A drop of ink spreads (diffusion)"

    def setup(self):
        self.n = int(_num(self.spec, "bits", 160, 20, 400))
        self.D = _num(self.spec, "speed", 1.0, 0.1, 5.0)          # how fast it spreads
        self.col = self.spec.get("color", "#3a2a8a")

    def length(self):
        return 12.0

    def size(self):
        return 700.0, 300.0

    def pos(self, i, t):
        """bit i at time t: a random walk made of seeded steps (the same every frame)"""
        import random as _r
        r = _r.Random(i * 7919 + 13)
        steps = int(t * 20)
        x = y = z = 0.0
        sd = 9.0 * self.D
        for _ in range(steps):
            x += r.gauss(0, sd)
            y += r.gauss(0, sd * 0.6)
            z += r.gauss(0, sd)
        frac = t * 20 - steps
        x += r.gauss(0, sd) * frac
        return x, y, z

    def spread(self, t):
        return 9.0 * self.D * math.sqrt(max(0.0, t * 20)) / M

    def draw(self, pen, t):
        W, D, Hh = 600, 300, 230
        glass = pen.material("#cfe8f5", roughness=0.1, transparency=0.78)
        pen.box(0, 0, 0, w=W, h=8, d=D, c="#3a4a5a")
        pen.box(-W / 2, 0, 0, w=6, h=Hh, d=D, c=glass)
        pen.box(W / 2, 0, 0, w=6, h=Hh, d=D, c=glass)
        pen.box(0, 0, D / 2, w=W, h=Hh, d=6, c=glass)
        water = pen.material("#bfe3f2", roughness=0.2, transparency=0.7)
        pen.box(0, 8, 0, w=W - 8, h=Hh - 30, d=D - 8, c=water)
        cy = Hh * 0.55
        if t < 0.3:                                        # the drop falls in
            pen.sphere(0, Hh + 60 - 200 * t, 0, r=10, c=self.col)
        for i in range(self.n):
            x, y, z = self.pos(i, max(0.0, t - 0.3))
            x = max(-W / 2 + 10, min(W / 2 - 10, x))
            z = max(-D / 2 + 10, min(D / 2 - 10, z))
            y = max(14, min(Hh - 36, cy + y))
            pen.dot(x, y, z, r=4.5, c=(0.23, 0.16, 0.54, max(0.25, 0.9 - t * 0.04)))

    def values(self, t):
        return [("bits of ink", str(self.n)), ("spread", f"{self.spread(max(0, t - 0.3)) * 100:.1f} cm"),
                ("", "each bit wanders at random - together they spread out")]

    def graph(self):
        return ("time (s)", "spread (cm)", lambda t: self.spread(max(0.0, t - 0.3)) * 100,
                self.spread(self.length()) * 100, ["#3a2a8a"])


class StringWave(Exp):
    """a plucked string (the wave equation, ch. 8, solved step by step): the bump splits in two, runs to the
    ends, turns over and comes back - like a guitar / sitar string"""
    name, title = "string", "A plucked string (wave equation)"

    def setup(self):
        self.L = _num(self.spec, "length", 3.0, 0.5, 8.0)
        self.c = _num(self.spec, "speed", 3.0, 0.5, 20.0)
        self.at_ = _num(self.spec, "pluck", 0.3, 0.05, 0.95)          # where it is pulled (part of the length)
        self.A = _num(self.spec, "amplitude", 0.25, 0.02, 1.0)
        self.N = 80
        self.frames = None

    def solve(self):
        """finite differences: y(next) = 2y - y(before) + r²·(y left - 2y + y right), ends held still"""
        N, dx = self.N, self.L / self.N
        dt = 0.9 * dx / self.c
        r2 = (self.c * dt / dx) ** 2
        k0 = int(self.at_ * N)
        y0 = [self.A * (i / k0 if i <= k0 else (N - i) / (N - k0)) for i in range(N + 1)]
        y0[0] = y0[N] = 0.0
        prev, cur = list(y0), list(y0)
        frames = [list(y0)]
        T = self.length()
        damp = 0.9995
        for _ in range(int(T / dt) + 2):
            nxt = [0.0] * (N + 1)
            for i in range(1, N):
                nxt[i] = (2 * cur[i] - prev[i] + r2 * (cur[i - 1] - 2 * cur[i] + cur[i + 1])) * damp
            prev, cur = cur, nxt
            frames.append(cur)
        self.frames, self.dt = frames, dt

    def shape(self, t):
        if self.frames is None:
            self.solve()
        k = min(len(self.frames) - 1, max(0, int(t / self.dt)))
        return self.frames[k]

    def length(self):
        return 6.0

    def size(self):
        return self.L * M + 160, 300.0

    def draw(self, pen, t):
        H = 150
        x0 = -self.L * M / 2
        for x in (x0, -x0):
            pen.box(x, 0, 0, w=24, h=H + 30, d=24, c="#6b4528")
        ys = self.shape(t)
        pts = [(x0 + self.L * M * i / self.N, H + ys[i] * M, 0) for i in range(self.N + 1)]
        pen.tube(pts, 3.5, c="#d4a017", sides=5, smooth=False)
        pen.line([(x0, H, 6), (-x0, H, 6)], c=(1, 1, 1, 0.3), w=1.5)

    def values(self, t):
        f = self.c / (2 * self.L)
        return [("wave speed", f"{self.c:g} m/s"), ("string", f"{self.L:g} m"),
                ("lowest note", f"f = v / 2L = {f:.2f} per second"), ("", "the bump splits, runs, turns over")]

    def graph(self):
        mid = self.N // 2
        return ("time (s)", "middle (cm)", lambda t: self.shape(t)[mid] * 100, self.A * 100, ["#d4a017"])


class MonteCarloPi(Exp):
    """throwing darts at random on a square with a circle in it (ch. 6): the part that lands inside -> π"""
    name, title = "monte_carlo_pi", "Finding π with random darts"

    def setup(self):
        self.n = int(_num(self.spec, "darts", 400, 20, 2000))
        self.rate = _num(self.spec, "per_second", 60, 5, 500)
        import random as _r
        r = _r.Random(int(_num(self.spec, "seed", 7, 0, 1e6)))
        self.pts = [(r.uniform(-1, 1), r.uniform(-1, 1)) for _ in range(self.n)]

    def shown(self, t):
        return min(self.n, int(t * self.rate))

    def estimate(self, t):
        k = self.shown(t)
        if k == 0:
            return 0.0, 0
        inside = sum(1 for x, y in self.pts[:k] if x * x + y * y <= 1)
        return 4.0 * inside / k, k

    def length(self):
        return self.n / self.rate + 2

    def size(self):
        return 500.0, 460.0

    def draw(self, pen, t):
        S = 200
        H = 230
        n = 8                                              # the board, in tiles (so the darts are never hidden
        tw = (2 * S + 20) / n                              #  behind one big face)
        for i in range(n):
            for j in range(n):
                xa, ya = -S - 10 + i * tw, H - S - 6 + j * (2 * S + 12) / n
                pen.poly([(xa, ya, 8), (xa + tw, ya, 8), (xa + tw, ya + (2 * S + 12) / n, 8), (xa, ya + (2 * S + 12) / n, 8)],
                         c="#f4f1ea")
        sq = [(-S, H - S, 0), (S, H - S, 0), (S, H + S, 0), (-S, H + S, 0), (-S, H - S, 0)]
        pen.line(sq, c="#333333", w=3)
        ring(pen, 0, H, 0, S, c="#e63946", w=3, plane="xy", n=60)
        k = self.shown(t)
        for i, (x, y) in enumerate(self.pts[:k]):
            inside = x * x + y * y <= 1
            pen.dot(x * S, H + y * S, -2, r=4, c="#e63946" if inside else "#3a86ff")
        pen.box(0, 0, 0, w=30, h=H - S - 6, d=30, c="#6b4528")

    def values(self, t):
        est, k = self.estimate(t)
        return [("darts", str(k)), ("π is about", f"4 × inside / all = {est:.4f}"), ("real π", "3.1416")]

    def graph(self):
        return ("time (s)", "estimate of π", lambda t: self.estimate(t)[0], 4.0, ["#e63946"])

    def sounds(self):
        return []


EXPERIMENTS = {c.name: c for c in (Fall, Projectile, Catapult, Bounce, Pendulum, Swing, Spring, Slope, InclinedPlane,
                                    Collision, Cradle, Buoyancy, BoatLoad, Lever, Pulley, Circular, MerryGoRound,
                                    Orbit, Shadow, Mirror, Prism, Ripples, RopeWave, Sound, Chaos, Diffusion,
                                    StringWave, MonteCarloPi)}
ALIASES = {"drop": "fall", "free_fall": "fall", "freefall": "fall", "throw": "projectile", "ball_throw": "projectile",
           "bouncing": "bounce", "bouncing_ball": "bounce", "bounce_ball": "bounce", "jhoola": "swing",
           "jhula": "swing", "spring_mass": "spring", "ramp": "slope", "friction": "slope", "incline": "inclined_plane",
           "carts": "collision", "momentum": "collision", "cradle": "newtons_cradle", "newton_cradle": "newtons_cradle",
           "float": "buoyancy", "floating": "buoyancy", "sink": "buoyancy", "float_sink": "buoyancy",
           "boat": "boat_load", "seesaw": "lever", "see_saw": "lever", "well": "pulley", "stone_on_rope": "circular",
           "sling": "circular", "solar_system": "orbit", "solar": "orbit", "sun_earth_moon": "orbit",
           "shadows": "shadow", "reflection": "mirror", "rainbow": "prism", "pond": "ripples", "wave": "rope_wave",
           "waves": "rope_wave", "sound_waves": "sound", "chaos_pendulum": "chaos", "driven_pendulum": "chaos",
           "butterfly": "chaos", "ink": "diffusion", "random_walk": "diffusion", "spread": "diffusion",
           "guitar": "string", "sitar": "string", "plucked_string": "string", "wave_equation": "string",
           "pi": "monte_carlo_pi", "darts": "monte_carlo_pi", "monte_carlo": "monte_carlo_pi"}
from . import physics_school as _school                 # noqa: E402  Class 6-8 school experiments

from . import physics_class9 as _c9                     # noqa: E402  Class 9
from . import physics_class10 as _c10                   # noqa: E402  Class 10
from . import physics_class11 as _c11                   # noqa: E402  Class 11
from . import physics_class12 as _c12                   # noqa: E402  Class 12

EXPERIMENTS.update({c.name: c for c in _school.SCHOOL})
ALIASES.update(_school.SCHOOL_ALIASES)
EXPERIMENTS.update({c.name: c for c in _c9.CLASS9})
ALIASES.update(_c9.CLASS9_ALIASES)
EXPERIMENTS.update({c.name: c for c in _c10.CLASS10})
ALIASES.update(_c10.CLASS10_ALIASES)
EXPERIMENTS.update({c.name: c for c in _c11.CLASS11})
ALIASES.update(_c11.CLASS11_ALIASES)
EXPERIMENTS.update({c.name: c for c in _c12.CLASS12})
ALIASES.update(_c12.CLASS12_ALIASES)
NAMES = tuple(EXPERIMENTS)


def kind_of(name):
    k = str(name or "").lower().strip().replace(" ", "_").replace("-", "_").replace("'", "")
    k = ALIASES.get(k, k)
    return k if k in EXPERIMENTS else None


_CACHE = {}


def get(spec):
    """the experiment object for a prop / event spec (cached by its settings)"""
    key = repr(sorted((k, repr(v)) for k, v in spec.items() if not str(k).startswith("_")))
    e = _CACHE.get(key)
    if e is None:
        if len(_CACHE) > 200:
            _CACHE.clear()
        e = EXPERIMENTS[kind_of(spec.get("experiment")) or "fall"](spec)
        _CACHE[key] = e
    return e


def local_time(spec, t):
    """scene time -> the experiment's own time: starts at its event, slow motion, frozen stretches"""
    t0 = float(spec.get("_start", 0.0))
    if t <= t0:
        return 0.0
    run = t - t0
    for a, d in spec.get("_freezes", []) or []:
        if t <= a:
            continue
        run -= min(d, t - a)
    return max(0.0, run) * float(spec.get("slowmo", 1.0) or 1.0)


def faces(spec, t):
    """Pen3 faces of the experiment at scene time t (story units, bottom-centre at 0, 0, 0)"""
    from .code3d import Pen3
    e = get(spec)
    pen = Pen3()
    e.draw(pen, local_time(spec, t))
    return pen.faces


def size(spec):
    try:
        return get(spec).size()
    except Exception:                                  # noqa: BLE001
        return 400.0, 300.0


def draw_object(ctx, pr, x, y, t, alpha=1.0):
    """an experiment prop: real 3D in a 3D scene, the front view in a 2D one"""
    from . import code3d
    sp = pr.spec
    early = 0.0 if sp.get("_hide_before") else float(sp.get("show_before", 0.6))   # set up a moment before
    if t > float(sp.get("_end", 1e9)) or t < float(sp.get("_start", 0.0)) - early:
        return
    fs = faces(sp, t)
    got = code3d.draw_in_scene(ctx, fs, x, y, None, None, flip=bool(sp.get("flip")), alpha=alpha, recolor=False)
    if got:
        return
    # 2D scene: a flat front view (x right, y up)
    ctx.save()
    ctx.translate(x, y)
    pts_faces = []
    for f in fs:
        if f.kind == "poly":
            pts_faces.append((max(p[2] for p in f.pts), f))
    for _z, f in sorted(pts_faces, key=lambda q: -q[0]):
        ctx.move_to(f.pts[0][0], f.pts[0][1])
        for p in f.pts[1:]:
            ctx.line_to(p[0], p[1])
        ctx.close_path()
        ctx.set_source_rgba(f.c[0], f.c[1], f.c[2], (f.c[3] if len(f.c) > 3 else 1.0) * alpha)
        ctx.fill()
    for f in fs:
        if f.kind == "line" and len(f.pts) == 2:
            ctx.move_to(f.pts[0][0], f.pts[0][1])
            ctx.line_to(f.pts[1][0], f.pts[1][1])
            ctx.set_line_width(max(1.0, f.w))
            ctx.set_source_rgba(f.c[0], f.c[1], f.c[2], alpha)
            ctx.stroke()
        elif f.kind == "dot":
            ctx.arc(f.pts[0][0], f.pts[0][1], max(1.0, f.w), 0, TAU)
            ctx.set_source_rgba(f.c[0], f.c[1], f.c[2], alpha)
            ctx.fill()
    ctx.restore()


# ============================================================================ the panel: stopwatch, numbers, graph
def draw_hud(ctx, hud, lt, W, H, S):
    """hud = dict(start, dur, spec, graph, numbers, watch). Drawn on top of the picture (screen pixels)."""
    import cairo
    from . import textfx
    spec = hud["spec"]
    e = get(spec)
    t = local_time(spec, lt)
    u = lt - hud["start"]
    a = max(0.0, min(1.0, u / 0.4, (hud["dur"] - u) / 0.4))
    if a <= 0:
        return
    ctx.save()
    ctx.identity_matrix()
    ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)

    def text(s, x, y, size, col):
        if textfx.needs(s):
            textfx.show_at(ctx, s, x, y, size, col)
        else:
            ctx.set_font_size(size)
            ctx.set_source_rgba(*col)
            ctx.move_to(x, y)
            ctx.show_text(s)
    pad = 16 * S
    # ---- title + stopwatch (top left)
    x0, y0 = 30 * S, 30 * S
    if hud.get("watch", True):
        r = 44 * S
        cx, cy = x0 + r, y0 + r + 8 * S
        ctx.set_source_rgba(1, 1, 1, 0.92 * a)
        ctx.arc(cx, cy, r, 0, TAU)
        ctx.fill()
        ctx.set_source_rgba(0.15, 0.15, 0.18, a)
        ctx.set_line_width(4 * S)
        ctx.arc(cx, cy, r, 0, TAU)
        ctx.stroke()
        ctx.rectangle(cx - 6 * S, cy - r - 12 * S, 12 * S, 10 * S)
        ctx.fill()
        for k in range(12):
            q = TAU * k / 12
            ctx.move_to(cx + math.sin(q) * r * 0.8, cy - math.cos(q) * r * 0.8)
            ctx.line_to(cx + math.sin(q) * r * 0.92, cy - math.cos(q) * r * 0.92)
        ctx.set_line_width(2 * S)
        ctx.stroke()
        q = TAU * (t % 1.0)
        ctx.set_source_rgba(0.85, 0.15, 0.2, a)
        ctx.set_line_width(3 * S)
        ctx.move_to(cx, cy)
        ctx.line_to(cx + math.sin(q) * r * 0.78, cy - math.cos(q) * r * 0.78)
        ctx.stroke()
        text(f"{t:5.2f} s", cx + r + 14 * S, cy + 12 * S, 34 * S, (1, 1, 1, a))
        if float(spec.get("slowmo", 1) or 1) < 0.99:
            text(f"slow motion ×{float(spec['slowmo']):g}", cx + r + 14 * S, cy + 44 * S, 20 * S, (1, 0.85, 0.3, a))
        y0 = cy + r + 20 * S
    # ---- the numbers
    if hud.get("numbers", True):
        rows = [(e.title, "")] + list(e.values(t))
        size = 22 * S
        ctx.set_font_size(size)
        wmax = 0.0
        for k, v in rows:
            s = f"{k}: {v}" if k and v else (k or v)
            wmax = max(wmax, textfx.width(s, size) if textfx.needs(s) else ctx.text_extents(s).x_advance)
        hh = len(rows) * size * 1.45 + pad
        ctx.set_source_rgba(0.05, 0.08, 0.12, 0.62 * a)
        ctx.rectangle(x0, y0, wmax + 2 * pad, hh)
        ctx.fill()
        for i, (k, v) in enumerate(rows):
            s = f"{k}: {v}" if k and v else (k or v)
            col = (1, 0.85, 0.3, a) if i == 0 else (1, 1, 1, a)
            text(s, x0 + pad, y0 + pad / 2 + (i + 0.85) * size * 1.45 - size * 0.25, size, col)
    # ---- the graph that draws itself (bottom right)
    gr = e.graph() if hud.get("graph", True) else None
    # ---- energy bars (moving energy / height energy) under the numbers
    en = e.energy(t) if hud.get("energy", True) else None
    if en is not None and hud.get("numbers", True):
        ke, pe = max(0.0, min(1.2, en[0])), max(0.0, min(1.2, en[1]))
        bx, by = x0, y0 + hh + 10 * S
        bw, bh = 220 * S, 18 * S
        for k_, (lab, v, col) in enumerate((("moving energy", ke, (0.16, 0.62, 0.28)),
                                            ("height energy", pe, (0.23, 0.53, 1.0)))):
            yy = by + k_ * (bh + 26 * S)
            ctx.set_source_rgba(0.05, 0.08, 0.12, 0.62 * a)
            ctx.rectangle(bx, yy, bw + 2 * pad, bh + 22 * S)
            ctx.fill()
            ctx.set_source_rgba(1, 1, 1, 0.25 * a)
            ctx.rectangle(bx + pad, yy + 18 * S, bw, bh * 0.6)
            ctx.fill()
            ctx.set_source_rgba(col[0], col[1], col[2], a)
            ctx.rectangle(bx + pad, yy + 18 * S, bw * min(1.0, v), bh * 0.6)
            ctx.fill()
            text(lab, bx + pad, yy + 15 * S, 15 * S, (1, 1, 1, a))
    if isinstance(gr, dict) and gr.get("kind") == "xy":     # phase space: a dot that draws its path
        gw, gh = 300 * S, 260 * S
        gx, gy = W - gw - 50 * S, H - gh - 80 * S
        ctx.set_source_rgba(1, 1, 1, 0.9 * a)
        ctx.rectangle(gx - 30 * S, gy - 34 * S, gw + 60 * S, gh + 74 * S)
        ctx.fill()
        cx_, cy_ = gx + gw / 2, gy + gh / 2
        ctx.set_source_rgba(0.6, 0.6, 0.6, a)
        ctx.set_line_width(1.5 * S)
        ctx.move_to(gx, cy_)
        ctx.line_to(gx + gw, cy_)
        ctx.move_to(cx_, gy)
        ctx.line_to(cx_, gy + gh)
        ctx.stroke()
        text("speed ↕   angle ↔", gx - 20 * S, gy - 12 * S, 15 * S, (0.2, 0.2, 0.22, a))
        from .util import hex_to_rgb
        for fx, fy, colh in ((gr["fx"], gr["fy"], gr["col"]), (gr.get("fx2"), gr.get("fy2"), gr.get("col2"))):
            if fx is None:
                continue
            c = hex_to_rgb(colh)
            ctx.set_source_rgba(c[0], c[1], c[2], 0.85 * a)
            ctx.set_line_width(2 * S)
            n = 220
            last = None
            for i in range(n + 1):
                ti = t * i / n
                px = cx_ + max(-1.0, min(1.0, fx(ti) / gr["xmax"])) * gw / 2
                py = cy_ - max(-1.0, min(1.0, fy(ti) / gr["ymax"])) * gh / 2
                if last is not None and abs(px - last[0]) > gw * 0.6:    # it went over the top: a jump, not a line
                    ctx.stroke()
                    ctx.move_to(px, py)
                elif last is None:
                    ctx.move_to(px, py)
                else:
                    ctx.line_to(px, py)
                last = (px, py)
            ctx.stroke()
            if last:
                ctx.arc(last[0], last[1], 5 * S, 0, TAU)
                ctx.fill()
        gr = None
    if gr:
        xl, yl, fn, ymax, cols = gr
        T = max(1.0, e.length())
        gw, gh = 380 * S, 220 * S
        gx, gy = W - gw - 40 * S, H - gh - 70 * S
        ctx.set_source_rgba(1, 1, 1, 0.9 * a)
        ctx.rectangle(gx - 50 * S, gy - 34 * S, gw + 70 * S, gh + 80 * S)
        ctx.fill()
        ctx.set_source_rgba(0.2, 0.2, 0.22, a)
        ctx.set_line_width(2 * S)
        lo = -abs(ymax) if any(v < -1e-6 for v in _flat(fn, T)) else 0.0
        hi = abs(ymax) * 1.1 or 1.0
        Y = lambda v: gy + gh - (v - lo) / (hi - lo) * gh
        ctx.move_to(gx, gy)
        ctx.line_to(gx, gy + gh)
        ctx.line_to(gx + gw, gy + gh)
        ctx.stroke()
        if lo < 0:
            ctx.set_source_rgba(0.6, 0.6, 0.6, a)
            ctx.move_to(gx, Y(0))
            ctx.line_to(gx + gw, Y(0))
            ctx.stroke()
        text(yl, gx - 40 * S, gy - 12 * S, 16 * S, (0.2, 0.2, 0.22, a))
        text(xl, gx + gw - 90 * S, gy + gh + 30 * S, 16 * S, (0.2, 0.2, 0.22, a))
        text(f"{hi:.1f}", gx - 46 * S, gy + 12 * S, 14 * S, (0.4, 0.4, 0.4, a))
        text(f"{T:.0f}", gx + gw - 10 * S, gy + gh + 18 * S, 14 * S, (0.4, 0.4, 0.4, a))
        n = 120
        tt_now = min(t, T)
        series = None
        pts = []
        for i in range(n + 1):
            ti = tt_now * i / n
            v = fn(ti)
            vs = v if isinstance(v, (list, tuple)) else [v]
            pts.append((gx + ti / T * gw, [Y(max(lo, min(hi, vv))) for vv in vs]))
            series = len(vs)
        from .util import hex_to_rgb
        for k in range(series or 0):
            c = hex_to_rgb(cols[k % len(cols)]) if cols else (0.9, 0.2, 0.2)
            ctx.set_source_rgba(c[0] * 0.85, c[1] * 0.85, c[2] * 0.85, a)
            ctx.set_line_width(3 * S)
            for i, (px, ys) in enumerate(pts):
                (ctx.move_to if i == 0 else ctx.line_to)(px, ys[k])
            ctx.stroke()
    ctx.restore()


def _flat(fn, T):
    out = []
    for i in range(30):
        v = fn(T * i / 29)
        out.extend(v if isinstance(v, (list, tuple)) else [v])
    return out


def describe():
    """for the AI prompt: one line per experiment"""
    keys = {
        "fall": '"height": 3, "objects": "stone,feather", "air": true, "planet": "earth|moon"',
        "projectile": '"speed": 12, "angle": 45, "from": 1.5, "air": true (air slows it; the no-air path shown faint)',
        "catapult": '"speed": 15, "angle": 40',
        "bounce": '"height": 2, "balls": "rubber,cricket,clay"',
        "pendulum": '"length": 1.5 (or "lengths": "0.5,1,2"), "angle": 20 (big angles are real too), "phase": true',
        "swing": '"length": 2, "angle": 30',
        "spring": '"k": 20, "mass": 0.5, "pull": 0.15',
        "slope": '"angle": 25, "length": 3, "surfaces": "ice,wood,sand,ball"',
        "inclined_plane": '"angle": 20, "mass": 20',
        "collision": '"m1": 1, "v1": 2, "m2": 2, "v2": 0, "e": "elastic|sticky|0.5"',
        "newtons_cradle": '"balls": 5, "angle": 30',
        "buoyancy": '"objects": "wood,ice,stone,iron"',
        "boat_load": '"capacity": 6',
        "lever": '"m1": 10, "d1": 1, "m2": 5, "d2": 2',
        "pulley": '"mass": 10, "ropes": 1, "depth": 3',
        "circular": '"radius": 1, "period": 1.2, "release": 3',
        "merry_go_round": '"radius": 1.5, "period": 4',
        "orbit": '"year": 12',
        "shadow": '"height": 1.5, "seconds": 10',
        "mirror": '"angle": 40',
        "prism": '',
        "ripples": '"speed": 0.5, "every": 1.5',
        "rope_wave": '"frequency": 1, "speed": 2, "amplitude": 0.25',
        "sound": '"every": 0.6',
        "chaos": '"drive": 1.2, "damping": 0.25, "difference": 0.5 (two pendulums start 0.5° apart)',
        "diffusion": '"bits": 160, "speed": 1',
        "string": '"length": 3, "speed": 3, "pluck": 0.3',
        "monte_carlo_pi": '"darts": 400, "per_second": 60',
    }
    keys.update(_school.SCHOOL_KEYS)
    keys.update(_c9.CLASS9_KEYS)
    keys.update(_c10.CLASS10_KEYS)
    keys.update(_c11.CLASS11_KEYS)
    keys.update(_c12.CLASS12_KEYS)
    return "\n".join(f'  {k}: {EXPERIMENTS[k].title}  ({v})' for k, v in keys.items())
