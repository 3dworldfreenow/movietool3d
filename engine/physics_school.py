"""School physics, Class 6-8 (NCERT order): one experiment per topic, the same pattern as engine/physics.py -
the true formula, simple 3D shapes, and the numbers / graph on the panel (pure physics, no exaggeration).

    circuit             cell, bulb, switch; conductors vs insulators (the bulb lights or not)
    magnets             two bar magnets: opposite poles attract, like poles repel
    compass             a compass needle points north, then turns to a magnet brought near
    pressure            the same push on a pin and on a palm: pressure = force / area
    water_pressure      a tank with holes: the lower the hole, the farther the water jet (more pressure)
    rolling             the same push on a box that slides and a box on wheels (rolling vs sliding friction)
    pitch               a ruler twanged at the table edge: shorter = faster = higher pitch; bigger = louder
    bell_jar            a ringing bell in a jar while the air is pumped out: sound needs air
    heating_wire        current heats a wire until it glows red / orange / yellow (P = I²R)
    electromagnet       a coil round a nail picks up pins while the current flows
    moon_phases         the Moon going round the Earth, half lit by the Sun: new, crescent, half, full
    day_night           the Earth turning: day on the side facing the Sun
    seasons             the tilted Earth round the Sun: summer when your half leans toward it
    lightning           charges build in a cloud, the spark, the thunder later (light is fast, sound slow)
    conduction          heat along a rod: wax drops fall one by one (copper fast, iron slower, glass, wood)
    convection          water in a pot on the fire: hot water rises, cool water sinks (a loop)
    radiation           a dark and a shiny can in the sun: the dark one warms faster
Each is registered into physics.EXPERIMENTS (imported at the end of engine/physics.py).
"""
import math
import random

from .physics import Exp, M, TAU, _num, _list, arrow, ring, plank, RED, BLUE, GREEN, YELLOW, ARROW_F, ARROW_V

WOOD, METAL, COPPER = "#8b6b4a", "#9aa3ad", "#c87533"


def _table(pen, w=700, h=60, d=260):
    pen.box(0, 0, 0, w=w, h=h, d=d, c="#7a5a3a", top="#a07850")


def _heat_col(T):
    """colour of hot metal by its temperature (°C): dark, dull red, cherry, orange, yellow, white"""
    stops = [(20, (0.45, 0.45, 0.48)), (450, (0.42, 0.2, 0.18)), (600, (0.7, 0.08, 0.05)), (800, (0.95, 0.25, 0.05)),
             (1000, (1.0, 0.6, 0.1)), (1200, (1.0, 0.9, 0.4)), (1500, (1.0, 1.0, 0.9))]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if T <= t1:
            u = max(0.0, (T - t0) / (t1 - t0))
            c = tuple(a + (b - a) * u for a, b in zip(c0, c1))
            return "#%02x%02x%02x" % tuple(int(255 * v) for v in c)
    return "#ffffee"


def _sun(pen, x, y, z, r=60, t=0.0):
    pen.sphere(x, y, z, r=r, c="#ffd23f")
    pen.glow(x, y, z, r * 3.2, "#ffdd66", 0.55)


def _half_lit(pen, x, y, z, r, toward, lit="#f2f2f2", dark="#3b3f4a"):
    """a ball lit on one half: `toward` = angle (radians, in the x-z plane) of the light"""
    pen.sphere(x, y, z, r=r, c=dark, rings=8, sides=14)
    prof = [(r * 1.02 * math.cos(a), r * 1.02 * math.sin(a)) for a in [k * math.pi / 16 for k in range(9)]]
    pen.push()
    pen.move(x, y, z)
    pen.rotate_y(-math.degrees(toward))
    pen.rotate_z(-90)                                   # the half-shell's axis now points along +x (to the light)
    pen.lathe(prof, lit, 0, 0, 0, sides=16)
    pen.pop()


# ============================================================================ electricity
CONDUCTORS = {"copper": 1.0, "iron": 0.9, "steel": 0.9, "aluminium": 1.0, "aluminum": 1.0, "coin": 0.95,
              "key": 0.95, "nail": 0.9, "safety_pin": 0.9, "pencil_lead": 0.5, "graphite": 0.5, "salt_water": 0.35}
INSULATORS = ("wood", "plastic", "rubber", "glass", "paper", "eraser", "cloth", "chalk", "stone", "dry_leaf")
MAT_COL = {"copper": COPPER, "iron": "#6e6e6e", "steel": "#b0b7bf", "aluminium": "#d7dadf", "aluminum": "#d7dadf",
           "coin": "#d4af37", "key": "#c9a227", "nail": "#7d7d7d", "safety_pin": "#c0c0c0", "pencil_lead": "#333333",
           "graphite": "#333333", "salt_water": "#8ecae6", "wood": "#a0703c", "plastic": "#3a86ff",
           "rubber": "#222222", "glass": "#cfe8f0", "paper": "#f4f1de", "eraser": "#ff8fab", "cloth": "#9b5de5",
           "chalk": "#ffffff", "stone": "#8e8e8e", "dry_leaf": "#b08040"}


class Circuit(Exp):
    name, title = "circuit", "Electric circuit: conductors and insulators"

    def setup(self):
        self.cells = int(_num(self.spec, "cells", 1, 1, 6))
        self.tests = _list(self.spec.get("tests", self.spec.get("materials", self.spec.get("material"))),
                           ["copper", "wood", "coin", "plastic", "pencil_lead", "rubber"])
        self.each = _num(self.spec, "each", 2.5, 1.0, 10.0)
        self.switch_at = _num(self.spec, "switch_at", 0.8, 0.0, 20.0)

    def length(self):
        return self.switch_at + self.each * len(self.tests) + 0.5

    def size(self):
        return 760.0, 320.0

    def now(self, t):
        if t < self.switch_at:
            return None, 0.0
        k = min(len(self.tests) - 1, int((t - self.switch_at) / self.each))
        m = str(self.tests[k]).lower().replace(" ", "_")
        return m, CONDUCTORS.get(m, 0.0)

    def current(self, t):
        m, g = self.now(t)
        V = 1.5 * self.cells
        R = 5.0 / max(g, 1e-6) if g > 0 else 1e9          # bulb 5 Ω; a poor conductor adds resistance
        return V / R if g > 0 else 0.0

    def draw(self, pen, t):
        _table(pen)
        y = 62
        on = t >= self.switch_at
        m, g = self.now(t)
        I = self.current(t)
        bright = min(1.0, I / 0.3)
        # the cell(s)
        for k in range(self.cells):
            cx = -260 + k * 70
            pen.cylinder_axis(cx, y + 30, 40, 26, 64, "#2b2d42", axis="x")
            pen.cylinder_axis(cx + 36, y + 30, 40, 8, 10, "#c0c0c0", axis="x")
        # bulb on its holder
        bx = 220
        pen.cylinder(bx, y, 40, r=26, h=34, c="#555555")
        pen.sphere(bx, y + 70, 40, r=36, c="#fff6cc" if bright > 0.05 else "#e8eef2")
        if bright > 0.05:
            pen.glow(bx, y + 70, 40, 160 * bright, "#fff2a0", 0.75 * bright)
        # the switch (a lever that closes)
        sx = -60
        pen.box(sx, y, -60, w=90, h=8, d=40, c="#444444")
        ang = 0.0 if on else 35.0
        pen.push()
        pen.move(sx - 40, y + 10, -60)
        pen.rotate_z(ang)
        pen.box(40, 0, 0, w=84, h=6, d=12, c="#c0c0c0")
        pen.pop()
        # the test gap with the thing being tested
        gx = 80
        pen.box(gx - 40, y, -60, w=12, h=20, d=12, c="#c0c0c0")
        pen.box(gx + 40, y, -60, w=12, h=20, d=12, c="#c0c0c0")
        if m:
            pen.box(gx, y + 20, -60, w=86, h=14, d=26, c=MAT_COL.get(m, "#999999"))
        # wires (a loop round the table)
        wire = "#d62828"
        pts = [(-230, y + 30, 40), (-230, y + 8, -60), (sx - 45, y + 8, -60)]
        pen.tube(pts, 4, c=wire, sides=6, smooth=False)
        pen.tube([(sx + 45, y + 8, -60), (gx - 40, y + 8, -60)], 4, c=wire, sides=6, smooth=False)
        pen.tube([(gx + 40, y + 8, -60), (bx, y + 8, -60), (bx, y + 8, 40)], 4, c=wire, sides=6, smooth=False)
        pen.tube([(bx, y + 8, 40), (bx, y + 8, 90), (-260 - 36, y + 8, 90), (-296, y + 30, 40)], 4, c="#1d3557",
                 sides=6, smooth=False)
        if I > 0:                                       # electrons moving round the loop
            loop = [(-230, -60), (bx, -60), (bx, 90), (-296, 90)]
            per = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(loop, loop[1:] + loop[:1]))
            for k in range(14):
                d = (k / 14.0 * per + t * 220 * bright) % per
                for a, b in zip(loop, loop[1:] + loop[:1]):
                    seg = math.hypot(b[0] - a[0], b[1] - a[1])
                    if d <= seg:
                        u = d / seg
                        pen.dot(a[0] + (b[0] - a[0]) * u, y + 16, a[1] + (b[1] - a[1]) * u, r=5, c="#ffd23f")
                        break
                    d -= seg

    def values(self, t):
        m, g = self.now(t)
        out = [("cells", f"{self.cells} × 1.5 V = {1.5 * self.cells:g} V")]
        if m is None:
            return out + [("switch", "open - no current")]
        I = self.current(t)
        out.append(("in the gap", m.replace("_", " ")))
        out.append(("", "conductor - the bulb lights" if g > 0 else "insulator - no current, no light"))
        out.append(("current", f"{I:.2f} A"))
        return out

    def graph(self):
        return ("time (s)", "current (A)", lambda t: self.current(t), 0.4 * self.cells, ["#e63946"])


class Electromagnet(Exp):
    name, title = "electromagnet", "Electromagnet: a coil round a nail"

    def setup(self):
        self.turns = int(_num(self.spec, "turns", 50, 5, 500))
        self.cells = int(_num(self.spec, "cells", 1, 1, 6))
        self.on_at = _num(self.spec, "on", 1.0, 0, 30)
        self.off_at = _num(self.spec, "off", 5.0, 0, 60)
        self.pins = int(_num(self.spec, "pins", 12, 1, 40))

    def strength(self):
        return self.turns * 0.3 * self.cells             # ampere-turns (0.3 A per cell)

    def lifted(self):
        return min(self.pins, int(self.strength() / 4.0))

    def length(self):
        return self.off_at + 2.0

    def size(self):
        return 640.0, 360.0

    def draw(self, pen, t):
        _table(pen, 640)
        y = 62
        on = self.on_at <= t < self.off_at
        nail_y = y + 150
        pen.cylinder_axis(0, nail_y, 0, 8, 260, "#8a8f96", axis="x")          # the nail
        n = max(6, min(30, self.turns // 4))
        for k in range(n):                                                   # the coil
            x = -90 + 180 * k / (n - 1)
            pen.tube([(x, nail_y - 12, -12), (x, nail_y + 12, 0), (x, nail_y - 12, 12)], 2.5, c=COPPER, sides=5,
                     smooth=True, ends=False)
        pen.tube([(-90, nail_y - 12, 0), (-200, y + 30, 60)], 3, c=COPPER, sides=5)
        pen.tube([(90, nail_y - 12, 0), (200, y + 30, 60)], 3, c=COPPER, sides=5)
        pen.cylinder_axis(0, y + 30, 70, 26, 90, "#2b2d42", axis="x")
        if on:
            pen.glow(130, nail_y, 0, 60, "#9bd0ff", 0.25)
        rr = random.Random(5)
        k_up = self.lifted()
        for i in range(self.pins):
            px, pz = rr.uniform(60, 220), rr.uniform(-80, 80)
            up = on and i < k_up
            if up:                                                           # jump to the nail's end and hang
                u = min(1.0, (t - self.on_at) / 0.25)
                tx, ty = 130 + (i % 4) * 6, nail_y - 14 - (i // 4) * 30
                x, yy = px + (tx - px) * u, y + (ty - y) * u
                pen.line([(x, yy, pz * (1 - u)), (x + 4, yy - 26, pz * (1 - u))], c="#d0d0d0", w=2)
            else:
                fall = t - self.off_at if t >= self.off_at and i < k_up else None
                if fall is not None and fall < 0.4:
                    yy = (nail_y - 14) - (nail_y - 14 - y) * min(1.0, (fall / 0.4) ** 2)
                    pen.line([(130, yy, 0), (134, yy - 26, 0)], c="#d0d0d0", w=2)
                else:
                    pen.line([(px, y + 2, pz), (px + 24, y + 2, pz + 6)], c="#d0d0d0", w=2)

    def values(self, t):
        on = self.on_at <= t < self.off_at
        return [("turns of wire", str(self.turns)), ("cells", str(self.cells)),
                ("current", f"{0.3 * self.cells if on else 0:.1f} A"),
                ("pins picked up", str(self.lifted() if on else 0)),
                ("", "a magnet only while the current flows" if on else "current off - the pins drop")]

    def sounds(self):
        return [(self.on_at + 0.25, "knock"), (self.off_at + 0.4, "knock")]


class HeatingWire(Exp):
    name, title = "heating_wire", "Heating effect of current"

    def setup(self):
        self.R = _num(self.spec, "resistance", 2.0, 0.1, 100)              # nichrome, ohms
        self.cells = int(_num(self.spec, "cells", 4, 1, 12))
        self.on_at = _num(self.spec, "on", 0.5, 0, 30)

    def T(self, t):
        if t < self.on_at:
            return 25.0
        V = 1.5 * self.cells
        P = V * V / self.R                                                   # watts
        Tmax = 25.0 + 75.0 * P                                               # where heat in = heat out (thin wire)
        return 25.0 + (Tmax - 25.0) * (1 - math.exp(-(t - self.on_at) / 1.6))

    def length(self):
        return self.on_at + 8.0

    def size(self):
        return 640.0, 320.0

    def draw(self, pen, t):
        _table(pen, 640)
        y = 62
        for x in (-200, 200):
            pen.box(x, y, 0, w=24, h=150, d=24, c="#444444")
        T = self.T(t)
        col = _heat_col(T)
        pts = [(-200 + 400 * k / 24.0, y + 140 + 8 * math.sin(k * 1.3), 0) for k in range(25)]
        pen.tube(pts, 3.5, c=col, sides=6, smooth=True)
        if T > 520:
            k = min(1.0, (T - 520) / 700)
            for p in pts[2::5]:
                pen.glow(p[0], p[1], p[2], 70 + 90 * k, col, 0.35 + 0.4 * k)
        pen.cylinder_axis(0, y + 30, 90, 26, 60 * min(self.cells, 4), "#2b2d42", axis="x")

    def values(self, t):
        V = 1.5 * self.cells
        I = V / self.R if t >= self.on_at else 0.0
        T = self.T(t)
        glow = "no glow" if T < 520 else ("dull red" if T < 650 else ("red" if T < 850 else
                                                                       ("orange" if T < 1050 else "yellow-white")))
        return [("voltage", f"{V:g} V"), ("current I = V / R", f"{I:.2f} A"), ("heat P = I²R", f"{I * I * self.R:.1f} W"),
                ("wire temperature", f"{T:.0f} °C - {glow}")]

    def graph(self):
        return ("time (s)", "temperature (°C)", lambda t: self.T(t), max(200.0, self.T(60.0) * 1.1), ["#e63946"])


# ============================================================================ magnets
class Magnets(Exp):
    name, title = "magnets", "Magnets: attract and repel"

    def setup(self):
        ends = str(self.spec.get("ends", self.spec.get("facing", "N-S"))).upper().replace(" ", "")
        if ends in ("ATTRACT", "OPPOSITE"):
            ends = "N-S"
        if ends in ("REPEL", "SAME", "LIKE"):
            ends = "N-N"
        self.ends = ends if ends in ("N-S", "S-N", "N-N", "S-S") else "N-S"
        self.attract = self.ends in ("N-S", "S-N")
        self.gap0 = _num(self.spec, "gap", 0.25, 0.05, 1.0)
        k, m, mu = 0.004, 0.2, 0.02                    # pull at 1 m (N·m²), kg, rolling friction of the cart
        g = 9.81
        x, v, ts = self.gap0, 0.0, []
        dt = 0.005
        t = 0.0
        while t < 6.0:                                                       # the free magnet on a cart
            F = k / max(x, 0.03) ** 2 * (-1 if self.attract else 1)
            fr = mu * m * g
            a = (F - math.copysign(fr, v if abs(v) > 1e-6 else F)) / m if abs(F) > fr or abs(v) > 1e-6 else 0.0
            v += a * dt
            x += v * dt
            if x <= 0.0:
                x, v = 0.0, 0.0
                ts.append((t, x))
                self.click = t
                break
            if not self.attract and abs(v) < 1e-4 and a == 0.0 and t > 0.3:
                ts.append((t, x))
                break
            ts.append((t, x))
            t += dt
        self.path = ts
        self.click = getattr(self, "click", None)

    def gap(self, t):
        t = max(0.0, t - 0.6)
        for tt, x in self.path:
            if tt >= t:
                return x
        return self.path[-1][1]

    def length(self):
        return 0.6 + self.path[-1][0] + 1.5

    def size(self):
        return 760.0, 240.0

    def _bar(self, pen, x, y, flip):
        a, b = ("#e63946", "#3a86ff") if not flip else ("#3a86ff", "#e63946")
        pen.box(x - 45, y, 0, w=90, h=36, d=50, c=a)
        pen.box(x + 45, y, 0, w=90, h=36, d=50, c=b)

    def draw(self, pen, t):
        _table(pen, 760)
        y = 62
        left_end = self.ends[0]
        right_end = self.ends[2]
        self._bar(pen, -110, y, flip=(left_end == "S"))                       # the end facing the gap
        x2 = -20 + self.gap(t) * M * 1.2 + 90
        self._bar(pen, x2, y + 18, flip=(right_end == "N"))
        for k in (-1, 1):
            pen.wheel(x2 + k * 60, y + 9, 30, r=9, c="#333333", w=6, spokes=0)
        d = self.gap(t)
        if d > 0.01:
            L = min(120.0, 25.0 / max(d, 0.05))
            s = -1 if self.attract else 1
            arrow(pen, (x2 - 90, y + 40, -40), (x2 - 90 + s * L, y + 40, -40), ARROW_F, r=3)

    def values(self, t):
        rule = "opposite poles attract" if self.attract else "like poles repel"
        return [("ends facing", self.ends.replace("-", " and ")), ("", rule), ("gap", f"{self.gap(t) * 100:.1f} cm")]

    def sounds(self):
        return [(0.6 + self.click, "knock")] if self.click else []


class Compass(Exp):
    name, title = "compass", "A compass points north"

    def setup(self):
        self.magnet_at = _num(self.spec, "magnet", 2.0, 0.0, 30)
        self.near = _num(self.spec, "distance", 0.15, 0.05, 1.0)

    def angle(self, t):
        """needle angle from north (degrees, + = toward the east / the magnet on the right)"""
        Be = 1.0
        if t < self.magnet_at:
            return 4.0 * math.sin(t * 2.2) * math.exp(-t)                   # it settles pointing north
        u = min(1.0, (t - self.magnet_at) / 1.5)
        d = 1.2 - (1.2 - self.near) * u                                    # the magnet comes closer
        Bm = (0.15 / d) ** 3 * 6.0
        target = math.degrees(math.atan2(Bm, Be))
        return target * (1 - math.exp(-3 * (t - self.magnet_at))) + 6 * math.exp(-2 * (t - self.magnet_at)) * \
            math.sin(6 * (t - self.magnet_at))

    def length(self):
        return self.magnet_at + 4.0

    def size(self):
        return 560.0, 240.0

    def draw(self, pen, t):
        _table(pen, 560)
        y = 62
        pen.cylinder(0, y, 0, r=80, h=14, c="#f4f1de", sides=24)
        ring(pen, 0, y + 15, 0, 80, c="#6b4528", w=4, plane="xz", n=40)
        a = math.radians(self.angle(t))
        nx, nz = math.sin(a), math.cos(a)                                  # north = +z (into the picture)
        pen.line([(0, y + 18, 0), (nx * 70, y + 18, nz * 70)], c="#e63946", w=6)
        pen.line([(0, y + 18, 0), (-nx * 70, y + 18, -nz * 70)], c="#cfd8dc", w=6)
        pen.dot(0, y + 20, 0, r=6, c="#333333")
        if t >= self.magnet_at:
            u = min(1.0, (t - self.magnet_at) / 1.5)
            mx = 300 - (300 - (90 + self.near * 400)) * u
            pen.box(mx - 30, y, 0, w=60, h=30, d=40, c="#e63946")
            pen.box(mx + 30, y, 0, w=60, h=30, d=40, c="#3a86ff")

    def values(self, t):
        a = self.angle(t)
        return [("needle", f"{abs(a):.0f}° {'east' if a > 0 else 'west'} of north"),
                ("", "it points north" if t < self.magnet_at else "a magnet nearby pulls it round")]


# ============================================================================ force and pressure
class Pressure(Exp):
    name, title = "pressure", "Force and pressure: a pin and a palm"

    def setup(self):
        self.F = _num(self.spec, "force", 20, 1, 1000)                      # newtons
        self.a_pin = 0.1e-6                                                  # m² (the point of a pin: 0.1 mm²)
        self.a_palm = 0.008                                                  # m²
        self.press_at = 1.0

    def length(self):
        return 4.0

    def size(self):
        return 700.0, 320.0

    def depth(self, area, t):
        if t < self.press_at:
            return 0.0
        p = self.F / area
        d = min(70.0, 6.0 * math.log10(max(p, 1.0)) - 20.0)               # dent in the clay (units)
        return max(1.0, d) * min(1.0, (t - self.press_at) / 0.6)

    def draw(self, pen, t):
        y = 0
        for x in (-170, 170):
            pen.box(x, y, 0, w=200, h=90, d=160, c="#c98e5a")              # clay blocks
        dp, dh = self.depth(self.a_pin, t), self.depth(self.a_palm, t)
        pen.cylinder(-170, 90 - dp, 0, r=1.5, h=110, c="#c0c0c0", sides=6)     # the pin
        pen.sphere(-170, 200 - dp, 0, r=10, c="#e63946")
        pen.round_box(170, 90 - dh, 0, w=110, h=40, d=90, c="#e0ac69", r=14)   # the palm
        for x, d in ((-170, dp), (170, dh)):
            arrow(pen, (x, 300, -60), (x, 230, -60), ARROW_F, r=4)

    def values(self, t):
        pp, ph = self.F / self.a_pin, self.F / self.a_palm
        return [("same push", f"{self.F:g} N"), ("pin point", f"{self.a_pin * 1e6:g} mm² -> {pp / 1e6:,.0f} MPa"),
                ("palm", f"{self.a_palm * 1e4:g} cm² -> {ph / 1e3:.1f} kPa"),
                ("pressure = force / area", "small area, big pressure")]


class WaterPressure(Exp):
    name, title = "water_pressure", "Water pressure grows with depth"

    def setup(self):
        self.H = _num(self.spec, "depth", 0.6, 0.2, 3.0)                    # water depth in the tank (m)
        self.holes = [self.H * f for f in (0.25, 0.55, 0.85)]               # hole depths below the surface
        self.base = 0.4                                                      # the tank stands 0.4 m high

    def length(self):
        return 5.0

    def size(self):
        return 900.0, (self.H + self.base) * M + 120

    def jet(self, h):
        """(speed, range on the ground) of the jet from a hole h below the surface (Torricelli: v = √(2gh))"""
        v = math.sqrt(2 * 9.81 * h)
        y0 = self.base + (self.H - h)
        return v, v * math.sqrt(2 * y0 / 9.81)

    def draw(self, pen, t):
        tw = 160
        top = (self.base + self.H) * M
        pen.box(-tw / 2, 0, 0, w=60, h=self.base * M, d=60, c="#7a5a3a")
        pen.box(0, self.base * M, 0, w=tw, h=self.H * M + 20, d=tw, c=(0.75, 0.88, 0.95, 0.35))
        pen.box(0, self.base * M, 0, w=tw - 8, h=self.H * M, d=tw - 8, c=(0.25, 0.55, 0.9, 0.55))
        on = min(1.0, t / 0.8)
        for h, col in zip(self.holes, ("#8ecae6", "#219ebc", "#126782")):
            v, R = self.jet(h)
            y0 = top - h * M
            n = 18
            pts = []
            for k in range(n + 1):
                tt = (k / n) * math.sqrt(2 * (y0 / M) / 9.81)
                x = v * tt * M
                yy = y0 - 0.5 * 9.81 * tt * tt * M
                if x > R * M * on + 1:
                    break
                pts.append((tw / 2 + x, max(0.0, yy), -10))
            if len(pts) >= 2:
                pen.tube(pts, 5, c=col, sides=6)
            pen.dot(tw / 2 + 2, y0, -10, r=7, c="#1d3557")

    def values(self, t):
        out = []
        for h, name in zip(self.holes, ("top hole", "middle hole", "bottom hole")):
            v, R = self.jet(h)
            out.append((name, f"{h * 100:.0f} cm deep: {1000 * 9.81 * h / 1000:.1f} kPa, {v:.2f} m/s, lands {R:.2f} m"))
        out.append(("", "deeper = more pressure = the jet goes farther"))
        return out


# ============================================================================ friction: rolling vs sliding
class Rolling(Exp):
    name, title = "rolling", "Rolling is easier than sliding"

    def setup(self):
        self.v0 = _num(self.spec, "speed", 2.0, 0.2, 10)                    # the push gives this speed (m/s)
        self.mu_s = _num(self.spec, "sliding", 0.4, 0.05, 1.0)
        self.mu_r = _num(self.spec, "rolling", 0.03, 0.002, 0.3)

    def x(self, mu, t):
        a = mu * 9.81
        ts = self.v0 / a
        t = min(max(0.0, t - 0.5), ts)
        return self.v0 * t - 0.5 * a * t * t

    def v(self, mu, t):
        return max(0.0, self.v0 - mu * 9.81 * max(0.0, t - 0.5))

    def length(self):
        return 0.5 + self.v0 / (self.mu_r * 9.81) + 0.8 if self.v0 / (self.mu_r * 9.81) < 12 else 12.0

    def size(self):
        return 1500.0, 260.0

    def draw(self, pen, t):
        pen.box(400, 0, 0, w=1800, h=10, d=420, c="#b9b6ad")
        x1 = -480 + self.x(self.mu_s, t) * M * 0.35
        x2 = -480 + self.x(self.mu_r, t) * M * 0.35
        pen.box(x1, 10, -100, w=110, h=80, d=90, c="#c8905b")              # slides on the floor
        pen.box(x2, 34, 100, w=110, h=80, d=90, c="#c8905b")               # on wheels
        turn = self.x(self.mu_r, t) * M * 0.35 / 12.0
        for k in (-1, 1):
            pen.wheel(x2 + k * 38, 12, 100 - 50, r=12, c="#333333", w=8, spokes=4, turn=-turn)
            pen.wheel(x2 + k * 38, 12, 100 + 50, r=12, c="#333333", w=8, spokes=4, turn=-turn)
        if t < 0.6:
            for z in (-100, 100):
                arrow(pen, (-640, 50, z), (-545, 50, z), ARROW_F, r=4)

    def values(self, t):
        d_s = self.v0 ** 2 / (2 * self.mu_s * 9.81)
        d_r = self.v0 ** 2 / (2 * self.mu_r * 9.81)
        return [("same push", f"{self.v0:g} m/s"), (f"sliding μ={self.mu_s:g}", f"stops after {d_s:.2f} m"),
                (f"rolling μ={self.mu_r:g}", f"goes {d_r:.2f} m"), ("", "wheels and ball bearings cut friction")]

    def graph(self):
        return ("time (s)", "speed (m/s)", lambda t: [self.v(self.mu_s, t), self.v(self.mu_r, t)], self.v0 * 1.1,
                ["#e63946", "#2a9d48"])


# ============================================================================ sound
class Pitch(Exp):
    name, title = "pitch", "Pitch and loudness: a twanged ruler"

    def setup(self):
        self.Ls = [float(x) for x in _list(self.spec.get("lengths", self.spec.get("length")), ["0.2", "0.1"])][:3]
        self.amp = _num(self.spec, "pluck", 1.0, 0.2, 2.0)                  # bigger pluck = louder
        self.each = 3.0

    def f(self, L):
        """first mode of a steel ruler (1 mm thick) held at one end: f = 0.56 / L² · √(E I / ρ A)"""
        return 0.815 / (L * L)

    def now(self, t):
        k = min(len(self.Ls) - 1, int(t / self.each))
        return k, self.Ls[k], t - k * self.each

    def length(self):
        return self.each * len(self.Ls)

    def size(self):
        return 700.0, 300.0

    def draw(self, pen, t):
        _table(pen, 500)
        pen.box(-80, 60, 0, w=120, h=30, d=80, c="#555555")                 # a hand / clamp holding it
        k, L, u = self.now(t)
        f = self.f(L)
        A = 40 * self.amp * math.exp(-u * 1.2) * (1 if u > 0.2 else 0)
        Lu = L * M * 2.2
        tip = A * math.sin(TAU * min(f, 12.0) * u)                          # (shown slowed down above 12 Hz)
        pts = [(170 + Lu * (i / 10), 70 + tip * (i / 10) ** 2, 0) for i in range(11)]
        pen.tube([(-80, 70, 0), (170, 70, 0)], 4, c="#c0c0c0", sides=4, smooth=False)
        pen.tube(pts, 4, c="#c0c0c0", sides=4, smooth=True)
        for r in range(3):                                                   # sound rings, louder = bolder
            age = (u * 1.5 + r / 3.0) % 1.0
            if A > 1:
                ring(pen, 170 + Lu, 70, 0, 20 + 160 * age, c="#ffd166", w=1 + 3 * self.amp * (1 - age), plane="xy", n=30)

    def values(self, t):
        k, L, u = self.now(t)
        f = self.f(L)
        db = 60 + 20 * math.log10(self.amp)
        return [("part over the edge", f"{L * 100:.0f} cm"), ("vibrations", f"{f:.0f} per second (Hz)"),
                ("", "shorter = faster = higher pitch"), ("loudness", f"about {db:.0f} dB (bigger swing = louder)")]


class BellJar(Exp):
    name, title = "bell_jar", "Sound needs air: a bell in a jar"

    def setup(self):
        self.tau = _num(self.spec, "pump", 2.5, 0.5, 20)                    # how fast the pump takes the air out

    def air(self, t):
        return math.exp(-max(0.0, t - 1.0) / self.tau)

    def length(self):
        return 1.0 + self.tau * 4

    def size(self):
        return 600.0, 420.0

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=360, h=20, d=360, c="#555555")
        pen.lathe([(150, 20), (150, 260), (120, 320), (60, 345), (0, 350)], (0.8, 0.92, 1.0, 0.25), 0, 0, 0, 24)
        pen.box(0, 20, 0, w=16, h=170, d=16, c="#888888")
        sw = 10 * math.sin(t * 25)
        pen.cylinder(0, 150, 0, r=45, h=50, c="#d4a017", r2=18, sides=16)
        pen.sphere(sw * 0.4, 145, 0, r=10, c="#666666")
        pen.tube([(170, 10, 0), (300, 10, 0)], 8, c="#333333", sides=6)
        a = self.air(t)
        for k in range(3):
            age = (t * 1.2 + k / 3.0) % 1.0
            r = 60 + 300 * age
            if a > 0.05:
                ring(pen, 0, 175, 0, r, c="#ffd166", w=1 + 3 * a * (1 - age), plane="xy", n=36)

    def values(self, t):
        a = self.air(t)
        db = 70 + 20 * math.log10(max(a, 1e-4))
        return [("air left in the jar", f"{a * 100:.0f} %"), ("sound outside", f"about {max(0, db):.0f} dB"),
                ("", "no air - no sound (it cannot travel in empty space)")]

    def graph(self):
        return ("time (s)", "air left (%)", lambda t: self.air(t) * 100, 110, ["#3a86ff"])

    def sounds(self):
        return [(0.2, "bell")]


# ============================================================================ the Earth, Sun and Moon
class MoonPhases(Exp):
    name, title = "moon_phases", "Phases of the Moon"

    def setup(self):
        self.period = _num(self.spec, "month", 12.0, 3, 60)                 # seconds for one month (29.5 days)

    def a(self, t):
        return TAU * (t / self.period) + math.pi                           # starts at new moon (between)

    def length(self):
        return self.period

    def size(self):
        return 1000.0, 360.0

    def phase(self, t):
        ang = (self.a(t) - math.pi) % TAU                                   # 0 = new, π = full
        lit = (1 - math.cos(ang)) / 2
        day = ang / TAU * 29.5
        names = ((0.03, "new moon"), (0.22, "waxing crescent"), (0.28, "first quarter (half)"),
                 (0.47, "waxing gibbous"), (0.53, "full moon"), (0.72, "waning gibbous"),
                 (0.78, "last quarter (half)"), (0.97, "waning crescent"), (1.01, "new moon"))
        f = ang / TAU
        name = next(n for lim, n in names if f <= lim)
        return lit, day, name

    def draw(self, pen, t):
        y = 160
        _sun(pen, -460, y, 0, 60)
        for k in range(5):                                                  # sunlight from the left
            arrow(pen, (-380, y - 80 + 40 * k, 0), (-300, y - 80 + 40 * k, 0), "#ffd166", r=2)
        pen.push()
        _half_lit(pen, 60, y, 0, 46, math.pi, lit="#4f9be0", dark="#1d3557")
        pen.pop()
        ring(pen, 60, y, 0, 210, c="#8d99ae", w=2, plane="xz", n=48)
        a = self.a(t)
        mx, mz = 60 + 210 * math.cos(a), 210 * math.sin(a)
        _half_lit(pen, mx, y, mz, 22, math.pi)
        lit, _d, _n = self.phase(t)                                         # what we see from the Earth
        px = 380
        pen.sphere(px, y + 120, -120, r=40, c="#3b3f4a")
        if lit > 0.02:
            ang = (self.a(t) - math.pi) % TAU
            pen.push()
            pen.move(px, y + 120, -121)
            k = 1 - 2 * lit
            side = 1 if ang < math.pi else -1                               # waxing: lit on the right
            pen.ellipsoid(side * 40 * (1 - lit) * 0.5, 0, -2, rx=40 * max(0.05, lit), ry=40, rz=4, c="#f2f2f2")
            pen.pop()

    def values(self, t):
        lit, day, name = self.phase(t)
        return [("day of the month", f"{day:.0f} of 29.5"), ("we see", name), ("lit part we see", f"{lit * 100:.0f} %"),
                ("", "the Sun always lights half the Moon - we see more or less of that half")]


class DayNight(Exp):
    name, title = "day_night", "Day and night: the Earth turns"

    def setup(self):
        self.day = _num(self.spec, "day", 8.0, 2, 60)                       # seconds for one turn (24 h)

    def hour(self, t):
        return (12.0 + 24.0 * t / self.day) % 24.0

    def length(self):
        return self.day * 1.5

    def size(self):
        return 900.0, 400.0

    def draw(self, pen, t):
        y = 180
        _sun(pen, -420, y, 0, 70)
        _half_lit(pen, 120, y, 0, 120, math.pi, lit="#4f9be0", dark="#14213d")
        a = TAU * t / self.day + math.pi                                    # your town on the equator
        px, pz = 120 + 124 * math.cos(a), 124 * math.sin(a)
        pen.sphere(px, y, pz, r=12, c="#e63946")
        pen.tube([(120, y - 150, 0), (120, y + 150, 0)], 3, c="#888888", sides=4, smooth=False)

    def values(self, t):
        h = self.hour(t)
        return [("time in your town", f"{int(h):02d}:{int((h % 1) * 60):02d}"),
                ("", "day - facing the Sun" if 6 <= h < 18 else "night - turned away from the Sun"),
                ("one turn", "24 hours")]


class Seasons(Exp):
    name, title = "seasons", "Seasons: the tilted Earth"

    def setup(self):
        self.year = _num(self.spec, "year", 12.0, 4, 60)
        self.lat = _num(self.spec, "latitude", 23.0, -66, 66)              # your town (23° N: middle India)

    def a(self, t):
        return TAU * t / self.year

    def length(self):
        return self.year

    def size(self):
        return 1000.0, 420.0

    def noon_sun(self, t):
        decl = 23.44 * math.sin(self.a(t))                                  # the Sun's height shifts through the year
        return 90.0 - abs(self.lat - decl), decl

    def draw(self, pen, t):
        y = 180
        _sun(pen, 0, y, 0, 70)
        ring(pen, 0, y, 0, 380, c="#8d99ae", w=2, plane="xz", n=60)
        a = self.a(t)
        ex, ez = 380 * math.cos(a + math.pi / 2), 380 * math.sin(a + math.pi / 2) * 0.6
        toward = math.atan2(-ez, -ex)
        _half_lit(pen, ex, y, ez, 48, toward, lit="#4f9be0", dark="#14213d")
        tilt = math.radians(23.44)                                         # the axis always leans the same way
        pen.tube([(ex - 70 * math.sin(tilt), y - 70 * math.cos(tilt), ez),
                  (ex + 70 * math.sin(tilt), y + 70 * math.cos(tilt), ez)], 2.5, c="#cccccc", sides=4, smooth=False)

    def values(self, t):
        h, decl = self.noon_sun(t)
        month = ["March", "April", "May", "June", "July", "August", "September", "October", "November", "December",
                 "January", "February"][int((self.a(t) / TAU) * 12) % 12]
        north = "summer in the north (India)" if decl > 8 else ("winter in the north (India)" if decl < -8 else
                                                                "spring / autumn")
        return [("month", month), ("", north), ("noon Sun height at 23° N", f"{h:.0f}°"),
                ("", "the axis leans 23.4° - the half leaning to the Sun gets more direct sunlight")]

    def graph(self):
        return ("time", "noon Sun height (°)", lambda t: self.noon_sun(t)[0], 95, ["#f4a261"])


class Lightning(Exp):
    name, title = "lightning", "Lightning and thunder"

    def setup(self):
        self.km = _num(self.spec, "distance", 1.0, 0.1, 20)
        self.flash = _num(self.spec, "flash", 2.5, 0.5, 20)

    def delay(self):
        return self.km * 1000.0 / 343.0

    def length(self):
        return self.flash + self.delay() + 1.5

    def size(self):
        return 900.0, 600.0

    def draw(self, pen, t):
        y = 450
        for dx, dy, r in ((-120, 0, 90), (0, 30, 110), (130, 0, 90), (60, -20, 80), (-60, -25, 80)):
            pen.sphere(dx, y + dy, 0, r=r, c="#5c677d" if t < self.flash + 0.3 else "#6c757d")
        n = int(min(1.0, t / self.flash) * 8)                               # charges building up
        for k in range(n):
            pen.dot(-150 + 40 * k, y + 95, -100, r=9, c="#e63946")           # + at the top
            pen.dot(-150 + 40 * k, y - 75, -100, r=9, c="#3a86ff")           # - at the bottom
        if self.flash <= t < self.flash + 0.35:                              # the spark
            rr = random.Random(3)
            pts, x, yy = [], 0.0, y - 80
            while yy > 0:
                pts.append((x, yy, -60))
                x += rr.uniform(-40, 40)
                yy -= rr.uniform(40, 80)
            pts.append((x, 0, -60))
            pen.tube(pts, 6, c="#ffffff", sides=4, smooth=False)
            pen.glow(0, y - 200, -60, 500, "#e0e8ff", 0.8)
        pen.box(0, 0, 0, w=900, h=4, d=400, c="#3a5a40")

    def values(self, t):
        heard = t >= self.flash + self.delay()
        return [("distance", f"{self.km:g} km"), ("light arrives after", f"{self.km * 1000 / 3e8 * 1e6:.1f} microseconds"),
                ("thunder arrives after", f"{self.delay():.1f} s" + (" - now!" if heard else "")),
                ("", "count the seconds and divide by 3: that many km")]

    def sounds(self):
        return [(self.flash + self.delay(), "thunder")]


# ============================================================================ heat
DIFFUSIVITY = {"copper": 1.1e-4, "aluminium": 9.7e-5, "aluminum": 9.7e-5, "iron": 2.3e-5, "steel": 1.2e-5,
               "glass": 3.4e-7, "wood": 1.0e-7, "plastic": 1.0e-7}


class Conduction(Exp):
    name, title = "conduction", "Heat travels along a rod (conduction)"

    def setup(self):
        self.mat = str(self.spec.get("material", "copper")).lower()
        self.alpha = DIFFUSIVITY.get(self.mat, 2.3e-5)
        self.L = _num(self.spec, "length", 0.3, 0.1, 1.0)                   # m
        self.pins = [self.L * f for f in (0.15, 0.3, 0.45, 0.6, 0.75, 0.9)]
        self.melt = 60.0
        if self.spec.get("speed") is not None:                              # 1 s on screen = this many real seconds
            self.speed = _num(self.spec, "speed", 60.0, 1.0, 3600.0)
        else:                                       # by itself: the last bead drops after about 8 s on screen
            x = self.pins[-1]
            z = 1.28                                                         # erfc(z) = 35/500 (25 °C + 35 = 60 °C)
            s_last = (x / (2 * z)) ** 2 / self.alpha
            self.speed = max(1.0, min(3600.0 * 6, s_last / 8.0))

    def T(self, x, t):
        """temperature (°C) at x along the rod after real time s: 25 + 500·erfc(x / 2√(αs))"""
        s = t * self.speed
        if s <= 0:
            return 25.0
        return 25.0 + 500.0 * math.erfc(x / (2 * math.sqrt(self.alpha * s)))

    def drop_time(self, x):
        lo, hi = 0.0, 3600.0 * 3 / self.speed
        if self.T(x, hi) < self.melt:
            return None
        for _ in range(40):
            mid = (lo + hi) / 2
            if self.T(x, mid) >= self.melt:
                hi = mid
            else:
                lo = mid
        return hi

    def length(self):
        last = self.drop_time(self.pins[-1])
        return min(30.0, (last or 20.0) + 2.0)

    def size(self):
        return self.L * M * 4 + 300, 320.0

    def draw(self, pen, t):
        k = M * 4                                        # drawn twice real size, so the rod reads on screen
        y = 200
        pen.box(-80, 0, 0, w=40, h=y, d=40, c="#555555")
        n = 24
        for i in range(n):
            x0 = self.L * i / n
            pen.cylinder_axis(x0 * k + self.L * k / n / 2, y, 0, 13, self.L * k / n + 1, _heat_col(self.T(x0, t)),
                              axis="x")
        pen.flame(0, y - 70, 0, h=60, t=t)
        for x in self.pins:
            dt_ = self.drop_time(x)
            if dt_ is not None and t >= dt_:
                fall = t - dt_
                yy = max(0.0, y - 20 - 0.5 * 9.81 * fall * fall * M)
                pen.sphere(x * k, yy, 0, r=8, c="#f6e7b8")
            else:
                pen.sphere(x * k, y - 18, 0, r=8, c="#f6e7b8")              # a wax bead holding a pin
        pen.box(self.L * k / 2, 0, 0, w=self.L * k + 200, h=6, d=180, c="#7a5a3a")

    def values(self, t):
        fallen = sum(1 for x in self.pins if (self.drop_time(x) or 1e9) <= t)
        real = t * self.speed
        when = f"{real / 3600:.1f} h" if real >= 7200 else (f"{real / 60:.1f} min" if real >= 60 else f"{real:.0f} s")
        return [("rod", self.mat), ("real time", when),
                ("wax beads fallen", f"{fallen} of {len(self.pins)}"),
                ("", "metals carry heat fast; glass and wood hardly at all")]

    def graph(self):
        return ("time", "°C along the rod", lambda t: [self.T(x, t) for x in self.pins[:3]], 540,
                ["#e63946", "#f4a261", "#e9c46a"])

    def sounds(self):
        return [(d, "plop") for d in (self.drop_time(x) for x in self.pins) if d is not None]


class Convection(Exp):
    name, title = "convection", "Hot water rises (convection)"

    def length(self):
        return 8.0

    def size(self):
        return 500.0, 420.0

    def draw(self, pen, t):
        pen.flame(0, 0, 0, h=70, t=t)
        pen.cylinder(0, 80, 0, r=150, h=200, c=(0.75, 0.85, 0.9, 0.35), sides=24)
        heat = min(1.0, t / 2.0)
        rr = random.Random(9)
        for i in range(40):                                                  # tea leaves going round the loop
            ph = rr.random()
            side = 1 if i % 2 else -1
            u = (ph + t * 0.18 * heat) % 1.0
            if u < 0.5:                                                      # up the hot middle
                x, yv = side * 30 * math.sin(u * 6), 90 + 180 * (u / 0.5)
            else:                                                            # out and down the cool sides
                v = (u - 0.5) / 0.5
                x, yv = side * (30 + 100 * math.sin(v * math.pi / 2)), 270 - 180 * v
            col = "#e63946" if yv > 200 or abs(x) < 40 else "#3a86ff"
            pen.dot(x, yv, rr.uniform(-60, 60), r=6, c=col)

    def values(self, t):
        return [("", "hot water is lighter - it rises in the middle"), ("", "cooler water sinks at the sides"),
                ("", "a loop: convection carries the heat round")]


class Radiation(Exp):
    name, title = "radiation", "Heat from the Sun (radiation)"

    def setup(self):
        self.speed = _num(self.spec, "speed", 120.0, 1.0, 3600.0)

    def T(self, absorb, t):
        s = t * self.speed
        return 25.0 + 30.0 * absorb * (1 - math.exp(-s / 900.0))

    def length(self):
        return 10.0

    def size(self):
        return 700.0, 420.0

    def draw(self, pen, t):
        _sun(pen, 0, 380, 0, 50)
        for x, c in ((-150, "#1d1d1f"), (150, "#d7dadf")):
            pen.cylinder(x, 0, 0, r=55, h=140, c=c, sides=18)
            arrow(pen, (x * 0.4, 330, -40), (x * 0.9, 170, -40), "#ffd166", r=3)

    def values(self, t):
        real = t * self.speed
        return [("time in the sun", f"{real / 60:.0f} min"), ("black can", f"{self.T(0.9, t):.1f} °C"),
                ("shiny can", f"{self.T(0.15, t):.1f} °C"), ("", "dark things soak up the Sun's heat, shiny ones send it back")]

    def graph(self):
        return ("time", "°C", lambda t: [self.T(0.9, t), self.T(0.15, t)], 60, ["#1d1d1f", "#adb5bd"])


SCHOOL = (Circuit, Electromagnet, HeatingWire, Magnets, Compass, Pressure, WaterPressure, Rolling, Pitch, BellJar,
          MoonPhases, DayNight, Seasons, Lightning, Conduction, Convection, Radiation)
SCHOOL_ALIASES = {
    "electric_circuit": "circuit", "bulb": "circuit", "conductors": "circuit", "insulators": "circuit",
    "battery": "circuit", "magnet": "magnets", "attract_repel": "magnets", "poles": "magnets",
    "needle": "compass", "north": "compass", "pin_and_palm": "pressure", "force_and_pressure": "pressure",
    "tank_holes": "water_pressure", "depth_pressure": "water_pressure", "rolling_vs_sliding": "rolling",
    "ball_bearing": "rolling", "wheels": "rolling", "sliding": "rolling", "loudness": "pitch", "ruler": "pitch",
    "vacuum_bell": "bell_jar", "sound_needs_air": "bell_jar", "heating_effect": "heating_wire",
    "hot_wire": "heating_wire", "coil": "electromagnet", "moon": "moon_phases", "phases": "moon_phases",
    "day_and_night": "day_night", "earth_turns": "day_night", "season": "seasons", "thunder": "lightning",
    "heat_conduction": "conduction", "heat_convection": "convection", "heat_radiation": "radiation",
}
SCHOOL_KEYS = {
    "circuit": '"cells": 1, "tests": "copper,wood,coin,plastic,pencil_lead"',
    "electromagnet": '"turns": 50, "cells": 1, "on": 1, "off": 5',
    "heating_wire": '"cells": 4, "resistance": 2',
    "magnets": '"ends": "N-S" (attract) | "N-N" (repel), "gap": 0.25',
    "compass": '"magnet": 2 (when a magnet is brought near), "distance": 0.15',
    "pressure": '"force": 20',
    "water_pressure": '"depth": 0.6',
    "rolling": '"speed": 2, "sliding": 0.4, "rolling": 0.03',
    "pitch": '"lengths": "0.2,0.1", "pluck": 1',
    "bell_jar": '"pump": 2.5',
    "moon_phases": '"month": 12 (seconds for 29.5 days)',
    "day_night": '"day": 8',
    "seasons": '"year": 12, "latitude": 23',
    "lightning": '"distance": 1 (km), "flash": 2.5',
    "conduction": '"material": "copper|iron|glass|wood", "speed": 60 (x real time)',
    "convection": '',
    "radiation": '"speed": 120',
}
