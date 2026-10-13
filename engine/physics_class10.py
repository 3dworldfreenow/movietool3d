"""School physics, Class 10 (NCERT order): light, electricity, magnetism - the same pattern as engine/physics.py.

    refraction          a straw in a glass looks bent; a light ray bends at the water (Snell's law n₁ sin i = n₂ sin r)
    lens                a convex / concave lens: rays to the focus, the image (bigger / smaller, upside down) as the
                        object moves (1/v - 1/u = 1/f)
    curved_mirror       a concave mirror (torch, shaving mirror) and a convex one (car side mirror)
    eye                 the eye lens focusing; short sight / long sight and the glasses that fix it
    scattering          why the sky is blue and the sunset red (short blue light scatters most, ∝ 1/λ⁴)
    ohm                 V = I·R: turn the voltage up, the current rises in a straight line
    series_parallel     two bulbs in series (dim, one goes out = both out) and in parallel (bright)
    power_bill          electric power and the bill: P = V·I, kWh = kW × hours
    magnetic_field      field lines round a wire and a coil (iron filings, compass needles), right-hand rule
    motor               a coil turning between magnets (electricity -> motion)
    generator           a magnet moved in a coil lights a bulb (motion -> electricity), AC vs DC
    fuse                a short circuit: the current jumps and the fuse wire melts
"""
import math

from .physics import Exp, M, TAU, _num, _list, arrow, ring, dashed, ARROW_F, ARROW_V, RED, BLUE, GREEN, YELLOW

RAY = "#ffd166"


def _ray(pen, pts, c=RAY, w=3.5):
    for a, b in zip(pts, pts[1:]):
        pen.line([a, b], c=c, w=w)


def _table(pen, w=700):
    pen.box(0, 0, 0, w=w, h=60, d=260, c="#7a5a3a", top="#a07850")


# ============================================================================ light
class Refraction(Exp):
    name, title = "refraction", "Refraction: light bends at the water"

    def setup(self):
        self.i = math.radians(_num(self.spec, "angle", 40, 0, 85))
        self.n2 = _num(self.spec, "n", 1.33, 1.0, 2.5)                     # water 1.33, glass 1.5, diamond 2.42

    def r(self):
        return math.asin(min(1.0, math.sin(self.i) / self.n2))

    def length(self):
        return 5.0

    def size(self):
        return 900.0, 520.0

    def draw(self, pen, t):
        # a glass of water with a straw (left) that looks bent at the surface
        gx, top = -250, 260
        pen.cylinder(gx, 0, 0, r=70, h=300, c=(0.8, 0.9, 1.0, 0.25), sides=20)
        pen.cylinder(gx, 0, 0, r=66, h=top, c=(0.3, 0.6, 0.95, 0.35), sides=20)
        sx0, sy0 = gx + 70, 380
        dx = (gx - 40 - sx0) / (sy0 - 20)
        sxs = sx0 + dx * (sy0 - top)
        pen.tube([(sx0, sy0, -10), (sxs, top, -10)], 6, c="#e63946", sides=6, smooth=False)
        k = 0.6                                                             # under water it looks shallower / shifted
        pen.tube([(sxs + 12, top, -10), (sxs + 12 + dx * (top - 20) * k, 20, -10)], 6, c="#e63946", sides=6, smooth=False)
        # the ray at a water surface (right)
        cx, sy = 220, 220
        pen.box(cx, 0, 0, w=360, h=sy, d=160, c=(0.3, 0.6, 0.95, 0.35))
        dashed(pen, (cx, sy - 180, -90), (cx, sy + 180, -90), c="#ffffff")
        u = min(1.0, t / 1.2)
        L = 200
        p0 = (cx - L * math.sin(self.i), sy + L * math.cos(self.i), -90)
        hit = (cx, sy, -90)
        _ray(pen, [p0, (p0[0] + (hit[0] - p0[0]) * u, p0[1] + (hit[1] - p0[1]) * u, -90)])
        if t > 1.2:
            v = min(1.0, (t - 1.2) / 1.2)
            r = self.r()
            q = (cx + L * math.sin(r) * v, sy - L * math.cos(r) * v, -90)
            _ray(pen, [hit, q])

    def values(self, t):
        return [("light in air at", f"{math.degrees(self.i):.0f}°"), ("bends to (in water)", f"{math.degrees(self.r()):.1f}°"),
                ("Snell's law", f"1.00 × sin {math.degrees(self.i):.0f}° = {self.n2:g} × sin r"),
                ("", "light slows in water and bends toward the normal")]


class Lens(Exp):
    name, title = "lens", "Lenses and images"

    def setup(self):
        self.kind = str(self.spec.get("kind", "convex")).lower()
        f = _num(self.spec, "focal", 0.2, 0.02, 2.0)
        self.f = -f if self.kind == "concave" else f
        self.u0 = _num(self.spec, "from", 0.6, 0.05, 5.0)                   # object distance at the start (m)
        self.u1 = _num(self.spec, "to", 0.12, 0.02, 5.0)                    # ... moves to here
        self.h = 0.05                                                        # object height (m)
        self.k = 700.0                                                       # drawn: 1 m = 700 units

    def u(self, t):
        a = min(1.0, max(0.0, (t - 1.0) / 6.0))
        return self.u0 + (self.u1 - self.u0) * a

    def image(self, t):
        """(v, magnification): 1/v - 1/u = 1/f with u negative (object on the left)"""
        u = -self.u(t)
        if abs(1 / self.f + 1 / u) < 1e-9:
            return float("inf"), float("inf")
        v = 1 / (1 / self.f + 1 / u)
        return v, v / u

    def length(self):
        return 8.0

    def size(self):
        return 1300.0, 420.0

    def draw(self, pen, t):
        k, y0 = self.k, 200
        pen.line([(-650, y0, 0), (650, y0, 0)], c="#888888", w=2)
        lh = 140
        if self.kind == "concave":
            pen.ellipsoid(0, y0, 0, rx=8, ry=lh, rz=60, c=(0.7, 0.9, 1.0, 0.45))
            pen.box(-14, y0 - lh, 0, w=8, h=2 * lh, d=110, c=(0.7, 0.9, 1.0, 0.25))
            pen.box(14, y0 - lh, 0, w=8, h=2 * lh, d=110, c=(0.7, 0.9, 1.0, 0.25))
        else:
            pen.ellipsoid(0, y0, 0, rx=20, ry=lh, rz=60, c=(0.7, 0.9, 1.0, 0.45))
        for s in (-1, 1):
            pen.dot(s * abs(self.f) * k, y0, 0, r=7, c="#e63946")              # the focal points
        u = self.u(t)
        ox, oh = -u * k, self.h * k * 2.5
        pen.tube([(ox, y0, 0), (ox, y0 + oh, 0)], 6, c=BLUE, sides=6)       # the object (an arrow)
        pen.cone(ox, y0 + oh, 0, r=14, h=24, c=BLUE)
        v, m = self.image(t)
        top = (ox, y0 + oh, 0)
        # ray 1: parallel, then through (or from) the focus; ray 2: through the centre
        _ray(pen, [top, (0, y0 + oh, 0)])
        if math.isfinite(v):
            ix, ih = v * k, m * oh
            far = 650
            d1x, d1y = (ix - 0, (y0 + ih) - (y0 + oh))
            L1 = math.hypot(d1x, d1y) or 1
            end1 = (far * d1x / L1 * (1 if v > 0 else -1), y0 + oh + far * d1y / L1 * (1 if v > 0 else -1), 0)
            _ray(pen, [(0, y0 + oh, 0), end1])
            d2x, d2y = (0 - ox, y0 - (y0 + oh))
            L2 = math.hypot(d2x, d2y) or 1
            _ray(pen, [top, (ox + d2x / L2 * 1400, y0 + oh + d2y / L2 * 1400, 0)])
            if v < 0:                                                        # a virtual image: dashed rays back
                dashed(pen, (0, y0 + oh, 0), (ix, y0 + ih, 0), c="#ffe8a3")
                dashed(pen, top, (ix, y0 + ih, 0), c="#ffe8a3")
            if abs(ix) < 640 and abs(ih) < 300:
                col = (0.9, 0.3, 0.3, 1.0) if v > 0 else (0.9, 0.3, 0.3, 0.45)
                pen.tube([(ix, y0, 0), (ix, y0 + ih, 0)], 6, c=col, sides=6)

    def values(self, t):
        u = self.u(t)
        v, m = self.image(t)
        if not math.isfinite(v):
            return [("object at", f"{u * 100:.0f} cm"), ("image", "at infinity (object at the focus)")]
        kind = ("real, upside down" if v > 0 else "virtual, upright") + (", bigger" if abs(m) > 1 else ", smaller")
        return [("lens", f"{self.kind}, f = {abs(self.f) * 100:.0f} cm"), ("object at", f"{u * 100:.0f} cm"),
                ("image at", f"{abs(v) * 100:.0f} cm {'behind' if v > 0 else 'in front of'} the lens"),
                ("magnification", f"{abs(m):.2f}× - {kind}"), ("lens formula", "1/v - 1/u = 1/f")]


class CurvedMirror(Exp):
    name, title = "curved_mirror", "Concave and convex mirrors"

    def setup(self):
        self.kind = str(self.spec.get("kind", "concave")).lower()
        self.R = _num(self.spec, "radius", 0.4, 0.05, 5.0)

    def length(self):
        return 5.0

    def size(self):
        return 1000.0, 420.0

    def draw(self, pen, t):
        k, y0 = 900.0, 200
        R = self.R * k
        s = 1 if self.kind == "concave" else -1
        pts = []
        for i in range(21):
            a = math.radians(-25 + 50 * i / 20)
            pts.append((s * (R - R * math.cos(a)) * -1 + 300, y0 + R * math.sin(a), 0))
        pen.tube(pts, 6, c="#c0d8e8", sides=6)
        f = R / 2
        fx = 300 - s * f
        pen.dot(fx, y0, 0, r=7, c="#e63946")
        u = min(1.0, t / 1.5)
        for h in (-90, -45, 0, 45, 90):                                     # parallel rays
            yy = y0 + h
            mx = 300 - s * (R - math.sqrt(max(0.0, R * R - h * h)))           # where the ray meets the mirror
            _ray(pen, [(-450, yy, 0), (-450 + (mx + 450) * u, yy, 0)])
            if t > 1.5:
                v = min(1.0, (t - 1.5) / 1.2)
                if self.kind == "concave":                                  # back through the focus
                    ex, ey = mx + (fx - mx) * 2.0 * v, yy + (y0 - yy) * 2.0 * v
                else:                                                       # spreads out, as if from the focus behind
                    dx, dy = mx - fx, yy - y0
                    L = math.hypot(dx, dy) or 1
                    ex, ey = mx + dx / L * 400 * v, yy + dy / L * 400 * v
                    dashed(pen, (mx, yy, 0), (fx, y0, 0), c="#ffe8a3")
                _ray(pen, [(mx, yy, 0), (ex, ey, 0)])

    def values(self, t):
        f = self.R / 2
        if self.kind == "concave":
            return [("concave mirror", f"R = {self.R * 100:.0f} cm, f = R/2 = {f * 100:.0f} cm"),
                    ("", "parallel light meets at the focus"), ("used in", "torches, shaving mirrors, solar cookers")]
        return [("convex mirror", f"R = {self.R * 100:.0f} cm, f = {f * 100:.0f} cm (behind it)"),
                ("", "light spreads out - a smaller, upright, wide view"), ("used in", "car side mirrors, road corners")]


class Eye(Exp):
    name, title = "eye", "The eye, short sight and long sight"

    def setup(self):
        self.kind = str(self.spec.get("kind", "short")).lower()            # normal | short | long
        self.each = 3.0

    def stage(self, t):
        return min(2, int(t / self.each))                                  # 0 normal eye, 1 the problem, 2 with glasses

    def length(self):
        return self.each * 3

    def size(self):
        return 1000.0, 400.0

    def draw(self, pen, t):
        y0 = 200
        pen.sphere(200, y0, 0, r=150, c=(0.95, 0.95, 0.97, 0.35))
        pen.ellipsoid(70, y0, 0, rx=22, ry=60, rz=40, c=(0.75, 0.9, 1.0, 0.7))
        retina = 345
        st = self.stage(t)
        if st == 0 or self.kind == "normal":
            meet = retina
        elif self.kind == "short":
            meet = retina - 70 if st == 1 else retina
        else:
            meet = retina + 80 if st == 1 else retina
        if st == 2 and self.kind != "normal":
            c = (0.6, 0.85, 1.0, 0.6)
            pen.ellipsoid(-80, y0, 0, rx=10 if self.kind == "long" else 4, ry=70, rz=40, c=c)
            if self.kind == "short":
                pen.box(-90, y0 - 70, 0, w=6, h=140, d=60, c=c)
        for h in (-45, 0, 45):
            _ray(pen, [(-450, y0 + h, 0), (70, y0 + h, 0), (meet, y0, 0)])
            if meet < retina:
                _ray(pen, [(meet, y0, 0), (retina, y0 - h * (retina - meet) / (meet - 70), 0)], c="#ffb703")
        pen.box(retina, y0 - 70, 0, w=8, h=140, d=80, c="#e63946")

    def values(self, t):
        st = self.stage(t)
        if self.kind == "short":
            msgs = ("normal eye: the picture forms on the retina", "short sight: it forms in front - far things blur",
                    "a concave (diverging) lens moves it back onto the retina")
        elif self.kind == "long":
            msgs = ("normal eye: the picture forms on the retina", "long sight: it would form behind - near things blur",
                    "a convex (converging) lens brings it onto the retina")
        else:
            msgs = ("the eye lens changes shape to focus near and far",) * 3
        return [("", msgs[st])]


class Scattering(Exp):
    name, title = "scattering", "Why the sky is blue and the sunset red"

    def setup(self):
        self.day = 4.0

    def sun_angle(self, t):
        return max(0.0, 60.0 - 60.0 * min(1.0, t / (self.day + 3)))       # the Sun goes down

    def length(self):
        return self.day + 4.0

    def size(self):
        return 1000.0, 500.0

    def path(self, t):
        e = math.radians(max(2.0, self.sun_angle(t)))
        return 1.0 / math.sin(e)                                           # how much air the light crosses

    def keep(self, lam_nm, t):
        """the part of light of this colour still in the beam after the air: exp(-k·path / λ⁴) (Rayleigh)"""
        return math.exp(-0.25 * self.path(t) * (450.0 / lam_nm) ** 4)

    def draw(self, pen, t):
        a = math.radians(self.sun_angle(t))
        sx, sy = -380 * math.cos(a), 60 + 400 * math.sin(a)
        r_, g_, b_ = self.keep(650, t), self.keep(530, t), self.keep(450, t)
        m = max(r_, g_, b_)
        col = "#%02x%02x%02x" % (int(255 * r_ / m), int(230 * g_ / m), int(170 * b_ / m))
        pen.sphere(sx, sy, 200, r=50, c=col)
        pen.glow(sx, sy, 200, 220, col, 0.6)
        pen.box(0, 0, 0, w=1000, h=10, d=400, c="#3a5a40")
        pen.capsule(200, 10, -50, r=20, h=110, c="#3a86ff")
        rr = __import__("random").Random(4)                                # air molecules sending blue light round
        for i in range(30):
            x, y = rr.uniform(-450, 450), rr.uniform(150, 450)
            pen.dot(x, y, 100, r=4, c="#8ecae6")

    def values(self, t):
        return [("Sun height", f"{self.sun_angle(t):.0f}°"), ("path through the air", f"{self.path(t):.1f}× the overhead path"),
                ("blue left in the beam", f"{self.keep(450, t) * 100:.0f} %"), ("red left", f"{self.keep(650, t) * 100:.0f} %"),
                ("", "air scatters blue most (∝ 1/λ⁴): blue sky; a long path at sunset leaves red")]


# ============================================================================ electricity
class Ohm(Exp):
    name, title = "ohm", "Ohm's law: V = I·R"

    def setup(self):
        self.R = _num(self.spec, "resistance", 10.0, 0.5, 1000)
        self.Vmax = _num(self.spec, "volts", 12.0, 1, 240)

    def V(self, t):
        return self.Vmax * min(1.0, max(0.0, (t - 0.5) / 5.0))

    def length(self):
        return 6.5

    def size(self):
        return 760.0, 320.0

    def draw(self, pen, t):
        _table(pen)
        y = 62
        pen.box(-220, y, 0, w=110, h=80, d=80, c="#2b2d42")                 # a battery eliminator with a knob
        pen.cylinder_axis(-220, y + 50, -42, 16, 8, "#e63946", axis="z")
        pen.box(60, y + 20, 0, w=160, h=30, d=40, c="#d4a017")              # the resistor
        for k in range(4):
            pen.box(10 + 30 * k, y + 20, 0, w=8, h=32, d=42, c=("#a52a2a", "#000000", "#e63946", "#ffd700")[k])
        for x, lab in ((260, "A"), (-40, "V")):
            pen.cylinder(x, y, -60, r=40, h=20, c="#f4f1de")
        pen.line([(-165, y + 35, 0), (-20, y + 35, 0)], c="#d62828", w=4)
        pen.line([(140, y + 35, 0), (260, y + 20, -60)], c="#d62828", w=4)

    def values(self, t):
        V = self.V(t)
        return [("resistance", f"{self.R:g} Ω"), ("voltage", f"{V:.1f} V"), ("current I = V / R", f"{V / self.R:.2f} A"),
                ("", "double the voltage, double the current (a straight line)")]

    def graph(self):
        return ("time (s)", "current (A)", lambda t: self.V(t) / self.R, self.Vmax / self.R * 1.1, ["#e63946"])


class SeriesParallel(Exp):
    name, title = "series_parallel", "Bulbs in series and in parallel"

    def setup(self):
        self.V = _num(self.spec, "volts", 6.0, 1.5, 240)
        self.R = _num(self.spec, "bulb", 6.0, 0.5, 1000)
        self.out_at = _num(self.spec, "remove", 3.0, 0.5, 30)              # one bulb is taken out

    def length(self):
        return self.out_at + 3.0

    def size(self):
        return 1000.0, 360.0

    def _bulb(self, pen, x, y, z, P, gone=False):
        pen.cylinder(x, y, z, r=16, h=20, c="#555555")
        if gone:
            return
        b = min(1.0, P / (self.V * self.V / self.R))
        pen.sphere(x, y + 42, z, r=24, c="#fff6cc" if b > 0.05 else "#e8eef2")
        if b > 0.05:
            pen.glow(x, y + 42, z, 120 * b, "#fff2a0", 0.75 * b)

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=1000, h=60, d=300, c="#7a5a3a", top="#a07850")
        y = 62
        out = t >= self.out_at
        # series (left): the same current through both
        I_s = 0.0 if out else self.V / (2 * self.R)
        self._bulb(pen, -330, y, 0, I_s * I_s * self.R)
        self._bulb(pen, -170, y, 0, I_s * I_s * self.R, gone=out)
        pen.line([(-380, y + 10, 0), (-120, y + 10, 0)], c="#d62828", w=4)
        # parallel (right): each bulb gets the full voltage
        P_p = self.V * self.V / self.R
        self._bulb(pen, 170, y, -60, P_p)
        self._bulb(pen, 330, y, 60, P_p, gone=out)
        pen.line([(120, y + 10, -60), (120, y + 10, 60), (380, y + 10, 60), (380, y + 10, -60)], c="#d62828", w=4)

    def values(self, t):
        out = t >= self.out_at
        I_s = self.V / (2 * self.R)
        return [("each bulb", f"{self.R:g} Ω, battery {self.V:g} V"),
                ("series", (f"I = {I_s:.2f} A, each bulb {I_s * I_s * self.R:.1f} W - dim" if not out
                            else "one bulb out: the circuit is broken - both go dark")),
                ("parallel", f"each bulb {self.V / self.R:.2f} A, {self.V * self.V / self.R:.1f} W - bright"
                 + (" (the other stays on)" if out else "")),
                ("", "houses are wired in parallel")]


class PowerBill(Exp):
    name, title = "power_bill", "Electric power and the bill"

    def setup(self):
        self.items = [("bulb", 60.0, 6.0), ("fan", 75.0, 10.0), ("TV", 120.0, 4.0), ("iron", 1000.0, 0.5)]
        self.rate = _num(self.spec, "rate", 7.0, 0.1, 100)                 # ₹ per unit (kWh)
        self.days = int(_num(self.spec, "days", 30, 1, 365))

    def length(self):
        return 8.0

    def size(self):
        return 900.0, 360.0

    def kwh(self):
        return sum(w * h for _n, w, h in self.items) / 1000.0 * self.days

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=900, h=10, d=300, c="#b9b6ad")
        n = min(len(self.items), int(t / 1.5) + 1)
        for k in range(n):
            x = -300 + 200 * k
            pen.box(x, 10, 0, w=120, h=90 + 40 * k, d=80, c=("#ffd166", "#8ecae6", "#2b2d42", "#adb5bd")[k])
        pen.box(380, 200, 60, w=90, h=140, d=40, c="#f4f1de")             # the meter
        pen.cylinder_axis(380, 300, 38, 22, 6, "#333333", axis="z")

    def values(self, t):
        n = min(len(self.items), int(t / 1.5) + 1)
        rows = [(f"{nm}", f"{w:g} W × {h:g} h a day = {w * h / 1000:.2f} kWh") for nm, w, h in self.items[:n]]
        if t > 6.0:
            rows.append((f"{self.days} days", f"{self.kwh():.0f} units (kWh) × ₹{self.rate:g} = ₹{self.kwh() * self.rate:.0f}"))
        return rows


class MagneticField(Exp):
    name, title = "magnetic_field", "Magnetic field of a current"

    def setup(self):
        self.kind = str(self.spec.get("kind", "wire")).lower()             # wire | coil
        self.on_at = 1.0

    def length(self):
        return 6.0

    def size(self):
        return 800.0, 420.0

    def draw(self, pen, t):
        on = t >= self.on_at
        pen.box(0, 120, 0, w=600, h=8, d=400, c="#f4f1de")                 # a card with iron filings
        if self.kind == "coil":
            for k in range(6):
                x = -100 + 40 * k
                ring(pen, x, 200, 0, 70, c="#c87533", w=5, plane="yz", n=24)
            if on:
                for r in (90, 140, 190):
                    ring(pen, 0, 124, 0, r, c="#555555", w=2, plane="xz", n=36)
                arrow(pen, (-160, 200, 0), (160, 200, 0), "#e63946", r=4)
            return
        pen.cylinder(0, 0, 0, r=6, h=400, c="#c87533")                     # the wire, straight up through the card
        if on:
            sp = (t - self.on_at) * 1.5
            for r in (50, 90, 130, 170):
                ring(pen, 0, 124, 0, r, c="#555555", w=2, plane="xz", n=40)
                a = sp + r * 0.02                                           # compasses point round the wire
                arrow(pen, (r * math.cos(a), 130, r * math.sin(a)),
                      (r * math.cos(a) - 25 * math.sin(a), 130, r * math.sin(a) + 25 * math.cos(a)), "#e63946", r=2)
            arrow(pen, (0, 300, -20), (0, 380, -20), "#ffd166", r=4)

    def values(self, t):
        on = t >= self.on_at
        if self.kind == "coil":
            return [("current", "on" if on else "off"), ("", "a coil acts like a bar magnet: N at one end, S at the other")]
        return [("current", "up the wire" if on else "off"),
                ("", "the filings make circles round the wire" if on else "no current - no field"),
                ("right-hand rule", "thumb along the current, fingers curl the way the field goes")]


class Motor(Exp):
    name, title = "motor", "Electric motor: electricity -> motion"

    def setup(self):
        self.on_at = 0.8
        self.rps = _num(self.spec, "speed", 2.0, 0.2, 20)

    def angle(self, t):
        if t < self.on_at:
            return 0.0
        u = t - self.on_at
        return TAU * self.rps * (u - (1 - math.exp(-u * 2)) / 2)

    def length(self):
        return 6.0

    def size(self):
        return 700.0, 380.0

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=600, h=20, d=260, c="#7a5a3a")
        pen.box(-200, 20, 0, w=80, h=220, d=140, c="#e63946")              # N
        pen.box(200, 20, 0, w=80, h=220, d=140, c="#3a86ff")               # S
        a = self.angle(t)
        c, s = math.cos(a), math.sin(a)
        y0 = 140
        pts = [(-120, y0 + 70 * c, 70 * s), (120, y0 + 70 * c, 70 * s), (120, y0 - 70 * c, -70 * s),
               (-120, y0 - 70 * c, -70 * s), (-120, y0 + 70 * c, 70 * s)]
        pen.tube(pts, 6, c="#c87533", sides=6, smooth=False)
        pen.cylinder_axis(0, y0, 0, 4, 330, "#888888", axis="x")

    def values(self, t):
        on = t >= self.on_at
        return [("current", "on" if on else "off"), ("turns a second", f"{self.rps if on else 0:g}"),
                ("", "the field pushes the two sides of the coil opposite ways - it turns"),
                ("", "electricity -> motion (fans, mixers, pumps)")]


class Generator(Exp):
    name, title = "generator", "Generator: motion -> electricity"

    def setup(self):
        self.f = _num(self.spec, "frequency", 1.0, 0.2, 5)                 # magnet in-out per second
        self.peak = _num(self.spec, "volts", 3.0, 0.1, 240)

    def emf(self, t):
        return self.peak * math.sin(TAU * self.f * max(0.0, t - 0.5)) if t > 0.5 else 0.0

    def length(self):
        return 6.0

    def size(self):
        return 760.0, 360.0

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=700, h=20, d=260, c="#7a5a3a")
        for k in range(8):
            ring(pen, -60 + 20 * k, 120, 0, 50, c="#c87533", w=5, plane="yz", n=20)
        x = -60 + 220 * math.cos(TAU * self.f * max(0.0, t - 0.5)) if t > 0.5 else 160
        pen.box(x, 105, 0, w=60, h=30, d=30, c="#e63946")
        pen.box(x + 60, 105, 0, w=60, h=30, d=30, c="#3a86ff")
        b = abs(self.emf(t)) / self.peak
        pen.sphere(260, 160, 0, r=24, c="#fff6cc")
        if b > 0.1:
            pen.glow(260, 160, 0, 110 * b, "#fff2a0", 0.7 * b)

    def values(self, t):
        return [("voltage now", f"{self.emf(t):+.2f} V"), ("", "a moving magnet makes a current in the coil"),
                ("AC", "the current changes direction as the magnet goes in and out"),
                ("DC", "a cell's current always goes one way")]

    def graph(self):
        return ("time (s)", "volts", lambda t: self.emf(t), self.peak * 1.1, ["#e63946"])


class Fuse(Exp):
    name, title = "fuse", "Fuse and short circuit"

    def setup(self):
        self.V = 230.0
        self.rating = _num(self.spec, "rating", 5.0, 0.5, 63)
        self.short_at = _num(self.spec, "short", 3.0, 0.5, 30)

    def I(self, t):
        if t < self.short_at:
            return 1000.0 / self.V                                         # a 1000 W heater
        return 0.0 if t > self.short_at + 0.15 else 40.0                   # the short: the current jumps, then the fuse blows

    def length(self):
        return self.short_at + 3.0

    def size(self):
        return 800.0, 320.0

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=700, h=20, d=240, c="#7a5a3a")
        pen.box(-200, 20, 0, w=120, h=70, d=80, c="#f4f1de")              # the fuse holder
        blown = t > self.short_at + 0.15
        if not blown:
            hot = t >= self.short_at
            pen.line([(-250, 60, -42), (-150, 60, -42)], c="#ffb703" if hot else "#c0c0c0", w=3)
            if hot:
                pen.glow(-200, 60, -42, 80, "#ffb703", 0.8)
        else:
            pen.line([(-250, 60, -42), (-215, 60, -42)], c="#555555", w=3)
            pen.line([(-185, 60, -42), (-150, 60, -42)], c="#555555", w=3)
        pen.box(200, 20, 0, w=160, h=60, d=100, c="#adb5bd")               # the heater
        if t < self.short_at:
            pen.glow(200, 60, 0, 90, "#ff6b35", 0.5)
        if self.short_at <= t < self.short_at + 0.3:
            pen.glow(60, 40, 0, 120, "#ffffff", 0.9)                       # the spark where the wires touch

    def values(self, t):
        return [("fuse rating", f"{self.rating:g} A"), ("current", f"{self.I(t):.1f} A"),
                ("", "normal: 1000 W heater, I = P / V = 4.3 A" if t < self.short_at else
                 ("short circuit! the fuse wire melts and breaks the circuit" if t > self.short_at + 0.15 else
                  "short circuit: the current jumps to 40 A"))]

    def facts(self):
        """key results for the physics auto-check (engine/physcheck.py)"""
        return [("normal current", f"{1000.0 / self.V:.2f} A"), ("short-circuit current", "40 A"),
                ("mains", f"{self.V:g} V"), ("heater", "1000 W")]

    def sounds(self):
        return [(self.short_at, "crackle"), (self.short_at + 0.15, "pop")]


CLASS10 = (Refraction, Lens, CurvedMirror, Eye, Scattering, Ohm, SeriesParallel, PowerBill, MagneticField, Motor,
           Generator, Fuse)
CLASS10_ALIASES = {
    "snell": "refraction", "bent_straw": "refraction", "straw": "refraction", "convex_lens": "lens",
    "concave_lens": "lens", "lenses": "lens", "concave_mirror": "curved_mirror", "convex_mirror": "curved_mirror",
    "spherical_mirror": "curved_mirror", "short_sight": "eye", "long_sight": "eye", "myopia": "eye",
    "hypermetropia": "eye", "blue_sky": "scattering", "sunset": "scattering", "ohms_law": "ohm", "v_ir": "ohm",
    "series": "series_parallel", "parallel": "series_parallel", "bill": "power_bill", "kwh": "power_bill",
    "electric_power": "power_bill", "magnetic_field_lines": "magnetic_field", "right_hand_rule": "magnetic_field",
    "electric_motor": "motor", "dynamo": "generator", "ac_dc": "generator", "short_circuit": "fuse",
}
CLASS10_KEYS = {
    "refraction": '"angle": 40, "n": 1.33 (water) | 1.5 (glass)',
    "lens": '"kind": "convex|concave", "focal": 0.2, "from": 0.6, "to": 0.12 (the object moves, metres)',
    "curved_mirror": '"kind": "concave|convex", "radius": 0.4',
    "eye": '"kind": "short|long|normal"',
    "scattering": '',
    "ohm": '"resistance": 10, "volts": 12',
    "series_parallel": '"volts": 6, "bulb": 6, "remove": 3',
    "power_bill": '"rate": 7, "days": 30',
    "magnetic_field": '"kind": "wire|coil"',
    "motor": '"speed": 2',
    "generator": '"frequency": 1, "volts": 3',
    "fuse": '"rating": 5, "short": 3',
}
