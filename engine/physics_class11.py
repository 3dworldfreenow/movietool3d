"""School physics, Class 11 (NCERT order) - the same pattern as engine/physics.py (true formulas, simple 3D shapes,
numbers and a graph on the panel). "S" topics are shown simpler (a model, not a full simulation).

    measurement        many readings of a pendulum's time: the average and the error
    vectors            two forces added head-to-tail: the resultant
    river_boat         a boat crossing a river: it heads straight across and drifts downstream
    relative_speed     two trains: same way (slow pass) or opposite ways (fast pass)
    banked_road        a car on a curve: the bank angle that needs no friction, tan θ = v² / r g
    torque             opening a door near the hinge vs at the handle: τ = F × r
    rolling_race       a ring, a disc and a ball roll down a slope: the ball wins (moment of inertia)
    skater             an ice skater pulls her arms in and spins faster: I·ω stays the same
    gyroscope          a spinning top leans but does not fall - it goes round (precession)
    satellite          a satellite in orbit: v = √(GM/r), its period; escape speed; floating astronauts
    kepler             a planet on an ellipse: faster near the Sun, equal areas in equal times
    elasticity         a wire stretched by weights: Hooke's law, then the elastic limit and breaking
    hydraulic_lift     Pascal's law: a small push lifts a car (F₁/A₁ = F₂/A₂)
    bernoulli          (S) a wing and a spinning ball: faster air, lower pressure - lift
    viscosity          a ball falling in oil reaches a terminal speed (Stokes)
    surface_tension    a needle floating, water drops round, a soap film pulling
    expansion          a rail and a bimetal strip heated: ΔL = α·L·ΔT, the strip bends
    heating_curve      ice heated to steam: the temperature stays flat while it melts and boils
    cooling            hot tea cooling: Newton's law of cooling
    gas_particles      particles in a box: hotter = faster; pressure from the hits (PV = nRT)
    heat_engine        a piston engine cycle: heat in, work out, heat out (efficiency)
    resonance          a swing / bridge pushed at its own rhythm swings higher and higher; damping
    standing_waves     a string vibrating in 1, 2, 3 loops (harmonics)
    beats              two notes a little apart: loud-soft-loud (f₁ - f₂ beats a second)
    doppler            a passing car horn: higher coming, lower going
"""
import math
import random

from .physics import (Exp, M, TAU, Table, _num, _list, arrow, ring, dashed, plank, ARROW_F, ARROW_V, ARROW_A, RED,
                      BLUE, GREEN, YELLOW)


def _floor(pen, w=1400, d=360, c="#b9b6ad"):
    pen.box(w / 2 - 300, 0, 0, w=w, h=8, d=d, c=c)


# ============================================================================ measurement and motion in a plane
class Measurement(Exp):
    name, title = "measurement", "Measurement: many readings, the average, the error"

    def setup(self):
        self.true = _num(self.spec, "value", 2.006, 0.01, 1000)            # the true time of 1 swing (L = 1 m)
        self.n = int(_num(self.spec, "readings", 8, 3, 30))
        rr = random.Random(int(_num(self.spec, "seed", 7, 0, 9999)))
        self.readings = [round(self.true + rr.gauss(0, 0.08), 2) for _ in range(self.n)]

    def shown(self, t):
        return self.readings[:max(1, min(self.n, int(t / 0.7) + 1))]

    def length(self):
        return self.n * 0.7 + 2.5

    def size(self):
        return 700.0, 300.0

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=600, h=8, d=200, c="#7a5a3a")
        r = self.shown(t)
        lo, hi = self.true - 0.3, self.true + 0.3
        for i, v in enumerate(r):
            x = -260 + 520 * (v - lo) / (hi - lo)
            pen.sphere(x, 30 + 22 * (i % 4), 0, r=10, c="#3a86ff")
        mean = sum(r) / len(r)
        xm = -260 + 520 * (mean - lo) / (hi - lo)
        pen.box(xm, 8, 0, w=4, h=140, d=4, c="#e63946")

    def values(self, t):
        r = self.shown(t)
        mean = sum(r) / len(r)
        err = sum(abs(v - mean) for v in r) / len(r)
        return [("readings", ", ".join(f"{v:.2f}" for v in r[-6:]) + " s"), ("average", f"{mean:.3f} s"),
                ("mean absolute error", f"± {err:.3f} s ({100 * err / mean:.1f} %)"),
                ("", "more readings -> the average comes nearer the true value")]


class Vectors(Exp):
    name, title = "vectors", "Adding vectors"

    def setup(self):
        self.a = (_num(self.spec, "a", 30, 0, 1000), math.radians(_num(self.spec, "a_angle", 0, -360, 360)))
        self.b = (_num(self.spec, "b", 40, 0, 1000), math.radians(_num(self.spec, "b_angle", 90, -360, 360)))

    def R(self):
        x = self.a[0] * math.cos(self.a[1]) + self.b[0] * math.cos(self.b[1])
        y = self.a[0] * math.sin(self.a[1]) + self.b[0] * math.sin(self.b[1])
        return math.hypot(x, y), math.degrees(math.atan2(y, x)), x, y

    def length(self):
        return 5.0

    def size(self):
        return 700.0, 500.0

    def draw(self, pen, t):
        k = 6.0
        o = (-150, 60, 0)
        ax, ay = self.a[0] * k * math.cos(self.a[1]), self.a[0] * k * math.sin(self.a[1])
        bx, by = self.b[0] * k * math.cos(self.b[1]), self.b[0] * k * math.sin(self.b[1])
        u = min(1.0, t / 1.0)
        arrow(pen, o, (o[0] + ax * u, o[1] + ay * u, 0), RED, r=5)
        if t > 1.0:
            v = min(1.0, (t - 1.0) / 1.0)
            arrow(pen, (o[0] + ax, o[1] + ay, 0), (o[0] + ax + bx * v, o[1] + ay + by * v, 0), BLUE, r=5)
        if t > 2.2:
            w = min(1.0, (t - 2.2) / 1.0)
            arrow(pen, o, (o[0] + (ax + bx) * w, o[1] + (ay + by) * w, -4), GREEN, r=6)

    def values(self, t):
        R, ang, _x, _y = self.R()
        return [("A", f"{self.a[0]:g} N at {math.degrees(self.a[1]):.0f}°"), ("B", f"{self.b[0]:g} N at {math.degrees(self.b[1]):.0f}°"),
                ("A + B", f"{R:.1f} N at {ang:.0f}° (head to tail)")]


class RiverBoat(Exp):
    name, title = "river_boat", "A boat crossing a river"

    def setup(self):
        self.vb = _num(self.spec, "boat", 4.0, 0.1, 30)
        self.vr = _num(self.spec, "river", 3.0, 0.0, 30)
        self.w = _num(self.spec, "width", 40.0, 2, 2000)
        self.T = self.w / self.vb

    def pos(self, t):
        tt = min(max(0.0, t - 0.5) * (self.T / 6.0), self.T)                 # the crossing shown in 6 s
        return self.vr * tt, self.vb * tt, tt

    def length(self):
        return 7.0

    def size(self):
        return 1200.0, 300.0

    def draw(self, pen, t):
        k = 600.0 / self.w
        pen.box(250, 0, 0, w=1300, h=4, d=self.w * k + 40, c=(0.25, 0.55, 0.9, 0.7))
        for z in (-self.w * k / 2 - 40, self.w * k / 2 + 40):
            pen.box(250, 0, z, w=1300, h=12, d=60, c="#6a994e")
        x, y, _tt = self.pos(t)
        bx, bz = -300 + x * k, -self.w * k / 2 + y * k
        pen.box(bx, 6, bz, w=40, h=20, d=70, c="#8b5a2b")
        arrow(pen, (bx, 40, bz), (bx, 40, bz + 80), BLUE, r=3)
        arrow(pen, (bx, 40, bz), (bx + 60, 40, bz), "#8ecae6", r=3)

    def values(self, t):
        x, y, tt = self.pos(t)
        v = math.hypot(self.vb, self.vr)
        return [("boat", f"{self.vb:g} m/s straight across"), ("river", f"{self.vr:g} m/s downstream"),
                ("real speed", f"{v:.1f} m/s"), ("time to cross", f"{self.T:.1f} s"),
                ("lands downstream", f"{self.vr * self.T:.1f} m")]


class RelativeSpeed(Exp):
    name, title = "relative_speed", "Relative speed: two trains"

    def setup(self):
        self.v1 = _num(self.spec, "v1", 20.0, 0, 100)
        self.v2 = _num(self.spec, "v2", 15.0, 0, 100)
        self.same = str(self.spec.get("way", "opposite")).lower().startswith("same")
        self.L = _num(self.spec, "train", 100.0, 10, 1000)

    def rel(self):
        return abs(self.v1 - self.v2) if self.same else self.v1 + self.v2

    def length(self):
        return 6.0

    def size(self):
        return 1400.0, 260.0

    def draw(self, pen, t):
        _floor(pen, 1600, 300)
        k = 2.0
        x1 = -500 + self.v1 * k * t * 6
        x2 = (-500 + self.v2 * k * t * 6) if self.same else (900 - self.v2 * k * t * 6)
        for x, z, c in ((x1, -60, RED), (x2, 60, BLUE)):
            pen.box(x, 10, z, w=self.L * 1.2, h=60, d=50, c=c)

    def values(self, t):
        return [("train 1", f"{self.v1:g} m/s"), ("train 2", f"{self.v2:g} m/s " + ("same way" if self.same else "towards it")),
                ("relative speed", f"{self.rel():g} m/s"), ("to pass each other", f"{2 * self.L / max(self.rel(), 1e-6):.1f} s")]


class BankedRoad(Exp):
    name, title = "banked_road", "A car on a banked curve"

    def setup(self):
        self.v = _num(self.spec, "speed", 20.0, 1, 100)
        self.r = _num(self.spec, "radius", 100.0, 5, 5000)

    def theta(self):
        return math.degrees(math.atan(self.v ** 2 / (self.r * 9.81)))

    def length(self):
        return 8.0

    def size(self):
        return 900.0, 400.0

    def draw(self, pen, t):
        th = math.radians(self.theta())
        R = 300
        for k in range(36):
            a0, a1 = TAU * k / 36, TAU * (k + 1) / 36
            pen.poly([(R * math.cos(a0), 0, R * math.sin(a0)), (R * math.cos(a1), 0, R * math.sin(a1)),
                      ((R + 90) * math.cos(a1), 90 * math.tan(th), (R + 90) * math.sin(a1)),
                      ((R + 90) * math.cos(a0), 90 * math.tan(th), (R + 90) * math.sin(a0))], c="#555555")
        a = TAU * t / 6.0
        cx, cz = (R + 45) * math.cos(a), (R + 45) * math.sin(a)
        pen.push()
        pen.move(cx, 45 * math.tan(th) + 10, cz)
        pen.turn(-math.degrees(a))
        pen.tilt(-math.degrees(th))
        pen.box(0, 0, 0, w=70, h=30, d=40, c=RED)
        pen.pop()

    def values(self, t):
        return [("speed", f"{self.v:g} m/s"), ("radius", f"{self.r:g} m"),
                ("bank angle", f"tan θ = v² / r g -> θ = {self.theta():.1f}°"), ("", "at that angle the car needs no friction")]


# ============================================================================ rotation
class Torque(Exp):
    name, title = "torque", "Torque: pushing a door"

    def setup(self):
        self.tau_need = _num(self.spec, "need", 6.0, 0.5, 200)            # N·m to swing the door open
        self.r_near = _num(self.spec, "near", 0.1, 0.02, 2)
        self.r_far = _num(self.spec, "far", 0.8, 0.05, 3)

    def length(self):
        return 6.0

    def size(self):
        return 900.0, 520.0

    def draw(self, pen, t):
        for z, r, c in ((-150, self.r_near, RED), (150, self.r_far, BLUE)):
            pen.box(-10, 0, z, w=20, h=420, d=20, c="#555555")             # hinge side
            F = self.tau_need / r
            open_ = min(70.0, 70.0 * max(0.0, t - 1.0) / 2.0) if F <= 40 else min(8.0, 8.0 * max(0.0, t - 1.0))
            pen.push()
            pen.move(0, 0, z)
            pen.turn(-open_)
            pen.box(160, 0, 0, w=320, h=400, d=12, c="#8b5a2b")
            pen.pop()
            arrow(pen, (r * 400, 200, z - 60), (r * 400, 200, z - 20), c, r=4)

    def values(self, t):
        return [("door needs", f"{self.tau_need:g} N·m"), ("push near the hinge", f"{self.r_near * 100:.0f} cm -> {self.tau_need / self.r_near:.0f} N"),
                ("push at the handle", f"{self.r_far * 100:.0f} cm -> {self.tau_need / self.r_far:.1f} N"),
                ("torque τ = F × r", "farther from the hinge, less force")]


class RollingRace(Exp):
    name, title = "rolling_race", "Rolling race: ring, disc, ball"

    SHAPES = (("ring", 1.0, "#e63946"), ("disc", 0.5, "#3a86ff"), ("ball", 0.4, "#2a9d48"))

    def setup(self):
        self.angle = math.radians(_num(self.spec, "angle", 20, 3, 60))
        self.L = _num(self.spec, "length", 2.0, 0.3, 10)

    def a(self, k):
        return 9.81 * math.sin(self.angle) / (1 + k)                        # k = I / (m r²)

    def x(self, k, t):
        return min(self.L, 0.5 * self.a(k) * max(0.0, t - 0.5) ** 2)

    def t_end(self, k):
        return math.sqrt(2 * self.L / self.a(k))

    def length(self):
        return 0.5 + self.t_end(1.0) + 1.0

    def size(self):
        return self.L * M * 1.2 + 200, self.L * M * math.sin(self.angle) * 1.2 + 120

    def draw(self, pen, t):
        k = M * 1.2
        Lk = self.L * k
        top = Lk * math.sin(self.angle)
        for i, (nm, kk, c) in enumerate(self.SHAPES):
            z = -120 + 120 * i
            plank(pen, Lk * math.cos(self.angle) / 2, top / 2, z, Lk, 10, 90, self.angle, c="wood")
            d = self.x(kk, t) * k
            cx = d * math.cos(self.angle)
            cy = top - d * math.sin(self.angle) + 30
            if nm == "ball":
                pen.sphere(cx, cy, z, r=24, c=c)
            else:
                pen.wheel(cx, cy, z, r=24, c=c, w=10, spokes=0 if nm == "ring" else 6, turn=-d / 24)

    def values(self, t):
        return [(nm, f"a = {self.a(kk):.2f} m/s², down in {self.t_end(kk):.2f} s") for nm, kk, _c in self.SHAPES] + \
            [("", "mass far from the middle (big I) rolls slower: the ball wins")]


class Skater(Exp):
    name, title = "skater", "Angular momentum: a spinning skater"

    def setup(self):
        self.I_out = _num(self.spec, "arms_out", 4.0, 0.5, 20)            # kg·m²
        self.I_in = _num(self.spec, "arms_in", 1.6, 0.2, 20)
        self.w0 = _num(self.spec, "spin", 2.0, 0.2, 20)                    # turns a second, arms out
        self.pull = 2.0

    def I(self, t):
        u = min(1.0, max(0.0, (t - self.pull) / 0.8))
        return self.I_out + (self.I_in - self.I_out) * u

    def w(self, t):
        return self.w0 * self.I_out / self.I(t)                             # I·ω is conserved

    def angle(self, t):
        n = 200
        dt_ = t / n
        return sum(self.w(i * dt_) * dt_ for i in range(n)) * TAU

    def length(self):
        return 6.0

    def size(self):
        return 500.0, 480.0

    def draw(self, pen, t):
        pen.cylinder(0, 0, 0, r=220, h=4, c="#e0f7ff", sides=30)
        a = self.angle(t)
        u = (self.I(t) - self.I_in) / (self.I_out - self.I_in)
        reach = 40 + 120 * u
        pen.capsule(0, 10, 0, r=28, h=300, c="#9b5de5")
        pen.sphere(0, 350, 0, r=30, c="#e0ac69")
        for s in (-1, 1):
            pen.tube([(0, 270, 0), (s * reach * math.cos(a), 270 - 20 * (1 - u), s * reach * math.sin(a))], 9,
                     c="#9b5de5", sides=6)

    def values(self, t):
        return [("arms", "out" if t < self.pull else "pulled in"), ("I", f"{self.I(t):.1f} kg·m²"),
                ("spin", f"{self.w(t):.1f} turns a second"), ("I × ω", f"{self.I(t) * self.w(t):.1f} (stays the same)")]


class Gyroscope(Exp):
    name, title = "gyroscope", "A spinning top precesses"

    def setup(self):
        self.spin = _num(self.spec, "spin", 20.0, 2, 200)                  # turns a second
        self.tilt = _num(self.spec, "tilt", 25.0, 0, 70)
        self.I_axis = 2e-4                                                  # kg·m² (a 100 g top)
        self.m, self.r = 0.1, 0.03

    def omega_p(self):
        """precession turns a second: Ω = m g r / (I ω)"""
        w = TAU * self.spin
        return self.m * 9.81 * self.r / (self.I_axis * w) / TAU

    def length(self):
        return 8.0

    def size(self):
        return 500.0, 400.0

    def draw(self, pen, t):
        pen.cylinder(0, 0, 0, r=200, h=4, c="#d7dadf", sides=24)
        pa = TAU * self.omega_p() * t
        pen.push()
        pen.move(0, 4, 0)
        pen.turn(math.degrees(pa))
        pen.rotate_z(-self.tilt)
        pen.cone(0, 0, 0, r=4, h=40, c="#333333")
        pen.lathe([(0, 40), (70, 80), (60, 100), (10, 120), (6, 170)], "#e63946", 0, 0, 0, 18)
        spin_a = TAU * self.spin * t * 0.02                                # (stripes show the spin, slowed down)
        for k in range(3):
            a = spin_a + k * TAU / 3
            pen.dot(62 * math.cos(a), 92, 62 * math.sin(a), r=6, c="#ffd23f")
        pen.pop()

    def values(self, t):
        return [("spin", f"{self.spin:g} turns a second"), ("tilt", f"{self.tilt:g}°"),
                ("goes round (precession)", f"{self.omega_p():.2f} turns a second"),
                ("", "gravity's torque turns the spin axis sideways instead of tipping it over")]


# ============================================================================ gravitation
GM_EARTH, R_EARTH = 3.986e14, 6.371e6


class Satellite(Exp):
    name, title = "satellite", "Satellites, escape speed, weightlessness"

    def setup(self):
        self.h = _num(self.spec, "height", 400.0, 100, 40000) * 1000.0     # km above the ground
        self.r = R_EARTH + self.h
        self.v = math.sqrt(GM_EARTH / self.r)
        self.T = TAU * self.r / self.v
        self.show = 8.0

    def length(self):
        return self.show + 1.0

    def size(self):
        return 900.0, 700.0

    def draw(self, pen, t):
        y0 = 340
        pen.sphere(0, y0, 0, r=150, c="#4f9be0", rings=10, sides=18)
        R = 150 * self.r / R_EARTH if self.h < 3e6 else 330
        R = min(330.0, max(175.0, R))
        ring(pen, 0, y0, 0, R, c="#8d99ae", w=2, plane="xy", n=60)
        a = TAU * t / self.show
        x, y = R * math.cos(a), y0 + R * math.sin(a)
        pen.box(x, y - 12, 0, w=30, h=24, d=24, c="#d7dadf")
        pen.box(x, y - 4, 0, w=90, h=6, d=40, c="#1d3557")
        arrow(pen, (x, y, -30), (x - 60 * math.sin(a), y + 60 * math.cos(a), -30), ARROW_V, r=3)
        arrow(pen, (x, y, -30), (x - 40 * math.cos(a), y - 40 * math.sin(a), -30), ARROW_F, r=3)

    def values(self, t):
        ve = math.sqrt(2 * GM_EARTH / R_EARTH)
        return [("height", f"{self.h / 1000:.0f} km"), ("orbit speed v = √(GM/r)", f"{self.v / 1000:.2f} km/s"),
                ("once round", f"{self.T / 60:.0f} min"), ("escape speed (from the ground)", f"{ve / 1000:.1f} km/s"),
                ("", "astronauts float: they and the station fall round the Earth together")]


class Kepler(Exp):
    name, title = "kepler", "Kepler's laws: an elliptical orbit"

    def setup(self):
        self.e = _num(self.spec, "e", 0.6, 0.0, 0.9)
        self.year = _num(self.spec, "year", 8.0, 2, 60)

    def E_of(self, t):
        Mn = TAU * (t % self.year) / self.year
        E = Mn
        for _ in range(30):                                                # Kepler's equation M = E - e sin E
            E = E - (E - self.e * math.sin(E) - Mn) / (1 - self.e * math.cos(E))
        return E

    def pos(self, t, a=300.0):
        E = self.E_of(t)
        b = a * math.sqrt(1 - self.e ** 2)
        return a * (math.cos(E) - self.e), b * math.sin(E)

    def length(self):
        return self.year * 1.25

    def size(self):
        return 800.0, 600.0

    def draw(self, pen, t):
        y0 = 300
        pen.sphere(0, y0, 0, r=40, c="#ffd23f")
        pen.glow(0, y0, 0, 120, "#ffdd66", 0.5)
        pts = [self.pos(self.year * k / 60.0) for k in range(61)]
        pen.tube([(x, y0 + y, 0) for x, y in pts], 2, c="#8d99ae", sides=4)
        x, y = self.pos(t)
        pen.sphere(x, y0 + y, 0, r=18, c="#4f9be0")
        for k in range(12):                                               # equal slices of time
            t0 = (t // (self.year / 12)) * (self.year / 12)
            if k == 0:
                for j in range(6):
                    a0, a1 = self.pos(t0 + j * self.year / 72), self.pos(t0 + (j + 1) * self.year / 72)
                    pen.poly([(0, y0, 1), (a0[0], y0 + a0[1], 1), (a1[0], y0 + a1[1], 1)], c=(1.0, 0.8, 0.3, 0.35))

    def values(self, t):
        x, y = self.pos(t)
        r = math.hypot(x, y)
        a = 300.0
        v_rel = math.sqrt(2 / (r / a) - 1)
        return [("orbit", f"an ellipse, e = {self.e:g}"), ("speed now", f"{v_rel:.2f} × the average"),
                ("", "nearer the Sun = faster; equal areas in equal times"), ("T² ∝ a³", "farther planets have longer years")]


# ============================================================================ elasticity and fluids
class Elasticity(Exp):
    name, title = "elasticity", "Stretching a wire: Hooke's law"

    def setup(self):
        self.L = _num(self.spec, "length", 2.0, 0.2, 10)
        self.d = _num(self.spec, "diameter", 0.5, 0.05, 5) / 1000            # mm -> m
        self.Y = _num(self.spec, "young", 2.0e11, 1e9, 5e11)                 # steel
        self.A = math.pi * (self.d / 2) ** 2
        self.limit = 2.5e8                                                  # elastic limit stress (Pa)
        self.break_ = 4.0e8

    def load(self, t):
        return max(0.0, t - 0.5) * 2.0                                     # kg added every second

    def stress(self, t):
        return self.load(t) * 9.81 / self.A

    def strain(self, t):
        s = self.stress(t)
        if s <= self.limit:
            return s / self.Y
        return self.limit / self.Y + (s - self.limit) / (self.Y * 0.05)   # it gives much more past the limit

    def broke(self, t):
        return self.stress(t) >= self.break_

    def length(self):
        tb = self.break_ * self.A / 9.81 / 2.0 + 0.5
        return min(30.0, tb + 1.5)

    def size(self):
        return 400.0, 600.0

    def draw(self, pen, t):
        pen.box(0, 560, 0, w=200, h=20, d=100, c="#555555")
        ext = min(80.0, self.strain(t) * self.L * 1000 * 4)               # mm, drawn 4x
        bot = 560 - 360 - ext
        if not self.broke(t):
            pen.line([(0, 560, 0), (0, bot, 0)], c="#c0c0c0", w=3)
            n = int(self.load(t) // 2) + 1
            for k in range(min(n, 8)):
                pen.cylinder(0, bot - 30 - 22 * k, 0, r=30, h=20, c="#6c757d")
        else:
            pen.line([(0, 560, 0), (0, 400, 0)], c="#c0c0c0", w=3)
            pen.cylinder(0, 0, 0, r=30, h=60, c="#6c757d")

    def values(self, t):
        s = self.stress(t)
        e = self.strain(t)
        state = "broken!" if self.broke(t) else ("past the elastic limit - it stays stretched" if s > self.limit
                                                  else "elastic: stretch ∝ load (Hooke's law)")
        return [("load", f"{self.load(t):.1f} kg"), ("stress", f"{s / 1e6:.0f} MPa"),
                ("stretch", f"{e * self.L * 1000:.2f} mm"), ("", state)]

    def graph(self):
        return ("time (s)", "stretch (mm)", lambda t: min(10.0, self.strain(t) * self.L * 1000), 10.0, ["#e63946"])


class HydraulicLift(Exp):
    name, title = "hydraulic_lift", "Pascal's law: a hydraulic lift"

    def setup(self):
        self.A1 = _num(self.spec, "small", 0.001, 1e-5, 1)                 # m²
        self.A2 = _num(self.spec, "big", 0.1, 1e-4, 10)
        self.m = _num(self.spec, "mass", 1000, 1, 50000)

    def F1(self):
        return self.m * 9.81 * self.A1 / self.A2

    def lift(self, t):
        return min(0.3, 0.05 * max(0.0, t - 1.0))                         # m (big piston)

    def length(self):
        return 8.0

    def size(self):
        return 900.0, 420.0

    def draw(self, pen, t):
        up = self.lift(t) * M
        down = up * self.A2 / self.A1 / 20                                # (the small piston goes down much more)
        pen.box(-200, 0, 0, w=60, h=200 - min(150, down), d=60, c=(0.25, 0.55, 0.9, 0.7))
        pen.box(200, 0, 0, w=260, h=120 + up, d=200, c=(0.25, 0.55, 0.9, 0.7))
        pen.box(0, 0, 0, w=420, h=30, d=60, c=(0.25, 0.55, 0.9, 0.7))
        pen.box(200, 120 + up, 0, w=260, h=14, d=200, c="#555555")
        pen.box(200, 134 + up, 0, w=200, h=60, d=110, c=RED)               # the car
        arrow(pen, (-200, 320, -40), (-200, 230 - min(150, down), -40), ARROW_F, r=3)

    def values(self, t):
        return [("car", f"{self.m:g} kg = {self.m * 9.81:.0f} N"), ("areas", f"{self.A1 * 1e4:g} cm² and {self.A2 * 1e4:g} cm²"),
                ("push needed", f"F₁ = F₂ × A₁/A₂ = {self.F1():.0f} N"), ("", "the same pressure goes everywhere in the liquid")]


class Bernoulli(Exp):
    name, title = "bernoulli", "Bernoulli: faster air, lower pressure (a wing)"

    def setup(self):
        self.v = _num(self.spec, "speed", 60.0, 1, 300)                    # m/s
        self.A = _num(self.spec, "area", 16.0, 0.1, 1000)                  # wing area m²
        self.top = 1.1                                                       # air on top goes 10 % faster

    def lift(self):
        rho = 1.2
        return 0.5 * rho * ((self.v * self.top) ** 2 - self.v ** 2) * self.A

    def length(self):
        return 6.0

    def size(self):
        return 1000.0, 360.0

    def draw(self, pen, t):
        y0 = 180
        prof = [(-200, 0), (-150, 25), (-50, 40), (100, 25), (220, 0), (100, -8), (-50, -10), (-150, -8)]
        pen.poly([(x, y0 + y, -40) for x, y in prof], c="#adb5bd")
        pen.poly([(x, y0 + y, 40) for x, y in prof], c="#adb5bd")
        rr = random.Random(2)
        for i in range(24):
            above = i % 2 == 0
            sp = (1.3 if above else 1.0) * 220
            x = (-450 + ((t * sp + rr.uniform(0, 900)) % 900))
            yy = y0 + (60 + 30 * math.exp(-((x - 0) / 200) ** 2)) * (1 if above else -1)
            pen.dot(x, yy, rr.uniform(-40, 40), r=4, c="#8ecae6")
        arrow(pen, (0, y0 + 50, -60), (0, y0 + 50 + min(150, self.lift() / 1000), -60), ARROW_F, r=4)

    def values(self, t):
        return [("air below", f"{self.v:g} m/s"), ("air above", f"{self.v * self.top:.0f} m/s (it goes round the curve)"),
                ("lift = ½ρ(v₁² - v₂²)A", f"{self.lift() / 1000:.1f} kN"), ("", "a spinning ball curves the same way")]


class Viscosity(Exp):
    name, title = "viscosity", "A ball falling in oil: terminal speed"

    def setup(self):
        self.r = _num(self.spec, "radius", 2.0, 0.2, 20) / 1000             # mm
        self.rho_b = _num(self.spec, "ball", 7800, 1000, 20000)
        self.rho_f = _num(self.spec, "oil", 900, 500, 2000)
        self.eta = _num(self.spec, "viscosity", 0.9, 0.001, 50)
        self.vt = 2 * self.r ** 2 * (self.rho_b - self.rho_f) * 9.81 / (9 * self.eta)
        m = self.rho_b * 4 / 3 * math.pi * self.r ** 3
        self.tau = m / (6 * math.pi * self.eta * self.r)

    def v(self, t):
        return self.vt * (1 - math.exp(-max(0.0, t - 0.5) / self.tau))

    def y(self, t):
        tt = max(0.0, t - 0.5)
        return self.vt * (tt - self.tau * (1 - math.exp(-tt / self.tau)))

    def length(self):
        return min(12.0, 0.5 + 0.5 / max(self.vt, 1e-4) + 1.0)

    def size(self):
        return 400.0, 640.0

    def draw(self, pen, t):
        pen.cylinder(0, 0, 0, r=70, h=560, c=(0.95, 0.8, 0.3, 0.45), sides=20)
        d = min(0.5, self.y(t)) / 0.5 * 520
        pen.sphere(0, 540 - d, 0, r=14, c="#6c757d")

    def values(self, t):
        return [("ball", f"r = {self.r * 1000:g} mm, steel"), ("speed now", f"{self.v(t) * 100:.2f} cm/s"),
                ("terminal speed (Stokes)", f"{self.vt * 100:.2f} cm/s"),
                ("", "the drag grows with speed until it balances the weight")]

    def graph(self):
        return ("time (s)", "speed (cm/s)", lambda t: self.v(t) * 100, self.vt * 110, ["#e63946"])


class SurfaceTension(Exp):
    name, title = "surface_tension", "Surface tension: water's skin"

    def setup(self):
        self.soap_at = _num(self.spec, "soap", 4.0, 0.5, 30)

    def length(self):
        return self.soap_at + 3.0

    def size(self):
        return 700.0, 300.0

    def draw(self, pen, t):
        pen.cylinder(0, 0, 0, r=260, h=40, c=(0.25, 0.55, 0.9, 0.5), sides=28)
        soap = t >= self.soap_at
        y = 42 if not soap else max(0.0, 42 - (t - self.soap_at) * 80)
        pen.cylinder_axis(-60, y, 0, 3, 200, "#c0c0c0", axis="x")           # a needle resting on the skin
        if not soap:
            pen.ellipsoid(-60, 40, 0, rx=110, ry=2, rz=18, c=(0.6, 0.8, 1.0, 0.6))
        for k in range(3):                                                 # round drops on a leaf
            pen.sphere(150 + 30 * k, 50, 120, r=10 - 2 * k, c=(0.7, 0.9, 1.0, 0.8))
        if soap:
            pen.dot(-200, 45, -60, r=10, c="#ffffff")

    def values(self, t):
        soap = t >= self.soap_at
        return [("water", "72 mN/m - a stretchy skin"), ("", "the steel needle floats on the skin" if not soap else
                                                       "a drop of soap weakens the skin - the needle sinks"),
                ("", "drops pull themselves round (the smallest surface)")]


# ============================================================================ heat
class Expansion(Exp):
    name, title = "expansion", "Thermal expansion: rails and a bimetal strip"

    def setup(self):
        self.L = _num(self.spec, "length", 12.0, 0.1, 100)                # a rail (m)
        self.alpha = _num(self.spec, "alpha", 1.2e-5, 1e-7, 1e-3)
        self.dT = _num(self.spec, "heat", 40.0, 1, 1000)

    def dL(self, t):
        return self.alpha * self.L * self.dT * min(1.0, max(0.0, (t - 0.5) / 3.0))

    def length(self):
        return 5.0

    def size(self):
        return 900.0, 300.0

    def draw(self, pen, t):
        gap = 20 - self.dL(t) / (self.alpha * self.L * self.dT) * 14       # the gap between rails closes (drawn)
        for k in range(3):
            x0 = -400 + k * (260 + gap)
            pen.box(x0 + 130, 10, 0, w=260, h=20, d=20, c="#8a8f96")
        u = min(1.0, max(0.0, (t - 0.5) / 3.0))                            # the bimetal strip bends as it heats
        pts = []
        for i in range(11):
            s = i / 10
            pts.append((-200 + 400 * s, 150 + 120 * u * s * s, 100))
        pen.tube(pts, 6, c="#c87533", sides=5)
        pen.tube([(x, y - 10, z) for x, y, z in pts], 6, c="#9aa3ad", sides=5)
        pen.flame(-100, 70, 100, h=50, t=t)

    def values(self, t):
        return [("rail", f"{self.L:g} m steel, α = {self.alpha:g} /°C"), ("heated by", f"{self.dT:g} °C"),
                ("it grows ΔL = α·L·ΔT", f"{self.dL(t) * 1000:.1f} mm"), ("", "so rails have gaps; brass grows more than iron - the strip bends")]


class HeatingCurve(Exp):
    name, title = "heating_curve", "Ice to steam: the heating curve"

    def setup(self):
        self.m = _num(self.spec, "mass", 0.5, 0.01, 10)
        self.P = _num(self.spec, "power", 2000.0, 10, 1e5)                 # heater watts
        c_ice, c_w, c_s, Lf, Lv = 2100, 4186, 2010, 3.34e5, 2.26e6
        m = self.m
        self.stages = [("ice warms", m * c_ice * 20, -20, 0), ("melting", m * Lf, 0, 0), ("water warms", m * c_w * 100, 0, 100),
                       ("boiling", m * Lv, 100, 100), ("steam warms", m * c_s * 20, 100, 120)]
        self.total = sum(q for _n, q, _a, _b in self.stages) / self.P       # real seconds
        self.show = 12.0

    def state(self, t):
        q = max(0.0, t - 0.5) / self.show * self.total * self.P
        for n, qq, a, b in self.stages:
            if q <= qq:
                return n, a + (b - a) * q / qq
            q -= qq
        return "steam warms", 120.0

    def length(self):
        return self.show + 1.5

    def size(self):
        return 500.0, 400.0

    def draw(self, pen, t):
        n, T = self.state(t)
        pen.flame(0, 0, 0, h=60, t=t)
        pen.cylinder(0, 70, 0, r=110, h=150, c="#9aa3ad", sides=22)
        if n in ("ice warms", "melting"):
            k = 1.0 if n == "ice warms" else 0.6
            for i in range(5):
                pen.box(-60 + 30 * i, 220, 0, w=30 * k, h=30 * k, d=30 * k, c=(0.85, 0.95, 1.0, 0.9))
        if n in ("melting", "water warms", "boiling"):
            pen.cylinder(0, 72, 0, r=105, h=120, c=(0.3, 0.6, 0.95, 0.6), sides=22)
        if n in ("boiling", "steam warms"):
            pen.particles(0, 230, 0, 18, "#ffffffaa", 14, 60, t, spread=60, life=1.5, grow=1.5)

    def values(self, t):
        n, T = self.state(t)
        real = max(0.0, t - 0.5) / self.show * self.total
        return [("now", n), ("temperature", f"{T:.0f} °C"), ("heater", f"{self.P:g} W, {real / 60:.1f} min so far"),
                ("", "while it melts or boils the heat breaks bonds - the temperature stays flat")]

    def graph(self):
        return ("time", "°C", lambda t: self.state(t)[1], 130, ["#e63946"])


class Cooling(Exp):
    name, title = "cooling", "Newton's law of cooling"

    def setup(self):
        self.T0 = _num(self.spec, "start", 90.0, 30, 300)
        self.Ta = _num(self.spec, "room", 25.0, -20, 50)
        self.k = _num(self.spec, "k", 0.05, 0.001, 2)                     # per minute
        self.speed = 3.0                                                     # 1 s on screen = 3 real minutes

    def T(self, t):
        mins = t * self.speed
        return self.Ta + (self.T0 - self.Ta) * math.exp(-self.k * mins)

    def length(self):
        return 10.0

    def size(self):
        return 400.0, 300.0

    def draw(self, pen, t):
        pen.box(0, 0, 0, w=300, h=8, d=200, c="#7a5a3a")
        pen.cylinder(0, 8, 0, r=50, h=100, c="#f4f1de", sides=20)
        hot = (self.T(t) - self.Ta) / (self.T0 - self.Ta)
        if hot > 0.15:
            pen.particles(0, 120, 0, int(10 * hot) + 1, "#ffffff99", 10, 30, t, spread=25, life=1.8, grow=1.5)

    def values(self, t):
        return [("tea", f"{self.T(t):.1f} °C"), ("room", f"{self.Ta:g} °C"), ("time", f"{t * self.speed:.0f} min"),
                ("", "it cools fast while hot, slower as it nears the room (dT/dt = -k(T - T room))")]

    def graph(self):
        return ("time", "°C", lambda t: self.T(t), self.T0 * 1.05, ["#e63946"])


class GasParticles(Exp):
    name, title = "gas_particles", "Kinetic theory: gas particles in a box"

    def setup(self):
        self.T1 = _num(self.spec, "temperature", 300.0, 10, 3000)          # K
        self.heat_at = _num(self.spec, "heat", 3.0, 0.5, 30)
        self.T2 = _num(self.spec, "hot", 600.0, 10, 3000)
        self.n = int(_num(self.spec, "particles", 40, 5, 150))

    def T(self, t):
        return self.T1 if t < self.heat_at else self.T2

    def vrms(self, t):
        return math.sqrt(3 * 1.380649e-23 * self.T(t) / 4.65e-26)          # nitrogen

    def length(self):
        return self.heat_at + 4.0

    def size(self):
        return 500.0, 460.0

    def draw(self, pen, t):
        B = 200.0
        pen.box(0, 0, 0, w=2 * B + 10, h=6, d=2 * B + 10, c="#555555")
        for (a, b) in (((-B, 0, -B), (B, 0, -B)), ((-B, 2 * B, -B), (B, 2 * B, -B)), ((-B, 0, -B), (-B, 2 * B, -B)),
                       ((B, 0, -B), (B, 2 * B, -B))):
            pen.line([a, b], c="#adb5bd", w=2)
        rr = random.Random(8)
        for i in range(self.n):                                            # straight paths bouncing off the walls
            p = [rr.uniform(-B, B), rr.uniform(0, 2 * B), rr.uniform(-B, B)]
            v = [rr.gauss(0, 1) for _ in range(3)]
            n = math.sqrt(sum(c * c for c in v)) or 1
            s1 = 0.25 * self.vrms(0.0)
            d1 = min(t, self.heat_at) * s1
            d2 = max(0.0, t - self.heat_at) * 0.25 * self.vrms(t)
            dist = d1 + d2
            pos = []
            for k in range(3):
                lo, hi = (-B, B) if k != 1 else (0, 2 * B)
                x = p[k] - lo + v[k] / n * dist
                span = hi - lo
                x %= 2 * span
                pos.append(lo + (x if x <= span else 2 * span - x))
            pen.sphere(pos[0], pos[1], pos[2], r=7, c="#e63946" if t >= self.heat_at else "#3a86ff", rings=3, sides=6)

    def values(self, t):
        T = self.T(t)
        return [("temperature", f"{T:.0f} K"), ("average speed (vrms)", f"{self.vrms(t):.0f} m/s"),
                ("pressure (same box)", f"{T / self.T1:.1f}× the start (PV = nRT)"),
                ("", "hotter = faster particles = harder, more frequent hits on the walls")]


class HeatEngine(Exp):
    name, title = "heat_engine", "A heat engine: heat in, work out"

    def setup(self):
        self.Th = _num(self.spec, "hot", 600.0, 300, 3000)                 # K
        self.Tc = _num(self.spec, "cold", 300.0, 100, 1000)
        self.rpm = _num(self.spec, "speed", 1.0, 0.2, 5)                   # cycles a second (shown)

    def length(self):
        return 6.0

    def size(self):
        return 600.0, 480.0

    def draw(self, pen, t):
        a = TAU * self.rpm * t
        pen.cylinder(0, 120, 0, r=70, h=260, c=(0.7, 0.7, 0.75, 0.4), sides=20)
        y = 230 + 70 * math.cos(a)
        pen.cylinder(0, y, 0, r=66, h=40, c="#6c757d", sides=20)
        hot = math.cos(a) < 0
        pen.cylinder(0, 125, 0, r=64, h=max(10, y - 125), c=(1.0, 0.5, 0.2, 0.4) if hot else (0.5, 0.7, 1.0, 0.3), sides=20)
        cx, cy = 0, 60
        px, py = 60 * math.sin(a), cy + 60 * math.cos(a)
        pen.wheel(cx, cy, -90, r=70, c="#555555", w=10, spokes=4, turn=-a)
        pen.tube([(0, y, 0), (px, py, -80)], 6, c="#adb5bd", sides=5)

    def values(self, t):
        eff = 1 - self.Tc / self.Th
        return [("hot side", f"{self.Th:g} K"), ("cold side", f"{self.Tc:g} K"),
                ("best possible efficiency", f"1 - Tc/Th = {eff * 100:.0f} %"),
                ("", "some heat must always go out to the cold side - no engine is 100 %")]


# ============================================================================ oscillations and waves
class Resonance(Exp):
    name, title = "resonance", "Resonance: pushing a swing at its own rhythm"

    def setup(self):
        self.f0 = _num(self.spec, "natural", 0.5, 0.05, 10)                # Hz (a swing)
        self.fd = _num(self.spec, "push", 0.5, 0.05, 10)                   # Hz of the pushes
        self.b = _num(self.spec, "damping", 0.08, 0.0, 2)
        w0 = TAU * self.f0
        wd = TAU * self.fd
        self.tb = Table(lambda t, y: [y[1], math.cos(wd * t) * 0.5 - 2 * self.b * y[1] - w0 * w0 * y[0]], [0.0, 0.0],
                        30.0, dt=0.01)

    def x(self, t):
        return self.tb.at(t)[0]

    def length(self):
        return 20.0

    def size(self):
        return 500.0, 500.0

    def draw(self, pen, t):
        pen.box(0, 460, 0, w=300, h=12, d=60, c="#6b4528")
        amax = max(1e-6, max(abs(self.tb.ys[k][0]) for k in range(0, len(self.tb.ys), 50)))
        ang = 50 * self.x(t) / amax
        L = 380
        a = math.radians(ang)
        bx, by = L * math.sin(a), 460 - L * math.cos(a)
        for s in (-30, 30):
            pen.line([(s, 460, 0), (bx + s, by, 0)], c="#c8a070", w=3)
        pen.box(bx, by - 8, 0, w=90, h=10, d=40, c="#8b5a2b")

    def values(self, t):
        return [("the swing's own rhythm", f"{self.f0:g} pushes a second"), ("pushed at", f"{self.fd:g} a second"),
                ("", "same rhythm: it swings higher and higher (resonance)" if abs(self.f0 - self.fd) < 0.05 * self.f0
                 else "a different rhythm: the pushes fight the swing - it stays small"),
                ("damping", f"{self.b:g} (friction keeps it from growing forever)")]

    def graph(self):
        amax = max(abs(y[0]) for y in self.tb.ys) or 1
        return ("time (s)", "swing", lambda t: self.x(t) / amax, 1.1, ["#e63946"])


class StandingWaves(Exp):
    name, title = "standing_waves", "Standing waves: harmonics on a string"

    def setup(self):
        self.L = _num(self.spec, "length", 1.0, 0.1, 10)
        self.v = _num(self.spec, "speed", 100.0, 1, 2000)
        self.each = 3.0

    def n(self, t):
        return min(3, int(t / self.each) + 1)

    def length(self):
        return self.each * 3

    def size(self):
        return 900.0, 300.0

    def draw(self, pen, t):
        n = self.n(t)
        for x in (-400, 400):
            pen.box(x, 0, 0, w=20, h=200, d=20, c="#555555")
        A = 60 * math.cos(TAU * 1.5 * t)
        pts = [(-400 + 800 * k / 60, 180 + A * math.sin(n * math.pi * k / 60), 0) for k in range(61)]
        pen.tube(pts, 3, c="#e63946", sides=5)
        for k in range(n + 1):
            pen.dot(-400 + 800 * k / n, 180, -10, r=8, c="#1d3557")       # the still points (nodes)

    def values(self, t):
        n = self.n(t)
        f = n * self.v / (2 * self.L)
        return [("loops", str(n)), ("wavelength", f"2L/n = {2 * self.L / n:.2f} m"), ("frequency", f"n·v / 2L = {f:.0f} Hz"),
                ("", "the string can only ring at these notes (harmonics)")]


class Beats(Exp):
    name, title = "beats", "Beats: two notes a little apart"

    def setup(self):
        self.f1 = _num(self.spec, "f1", 256.0, 20, 5000)
        self.f2 = _num(self.spec, "f2", 260.0, 20, 5000)

    def env(self, t):
        return abs(math.cos(math.pi * (self.f1 - self.f2) * t))

    def length(self):
        return 5.0

    def size(self):
        return 900.0, 300.0

    def draw(self, pen, t):
        for x, c in ((-300, "#3a86ff"), (300, "#e63946")):
            pen.box(x, 0, 0, w=20, h=120, d=20, c="#555555")
            pen.box(x - 20, 120, 0, w=10, h=100, d=10, c="#c0c0c0")
            pen.box(x + 20, 120, 0, w=10, h=100, d=10, c="#c0c0c0")
        e = self.env(t)
        ring(pen, 0, 160, 0, 60 + 120 * e, c="#ffd166", w=1 + 6 * e, plane="xy", n=40)

    def values(self, t):
        return [("forks", f"{self.f1:g} Hz and {self.f2:g} Hz"), ("beats", f"{abs(self.f1 - self.f2):g} a second (f₁ - f₂)"),
                ("loudness now", f"{self.env(t) * 100:.0f} %"), ("", "musicians tune until the beats stop")]

    def graph(self):
        return ("time (s)", "loudness", lambda t: self.env(t), 1.1, ["#e9c46a"])


class Doppler(Exp):
    name, title = "doppler", "Doppler effect: a passing car horn"

    def setup(self):
        self.f = _num(self.spec, "horn", 400.0, 50, 5000)
        self.v = _num(self.spec, "speed", 25.0, 1, 150)
        self.c = 343.0

    def x(self, t):
        return (t - 3.0) * self.v                                          # m, passes the listener at t = 3

    def heard(self, t):
        x = self.x(t)
        vr = self.v * (-x) / math.hypot(x, 5.0)                            # speed toward the listener
        return self.f * self.c / (self.c - vr)

    def length(self):
        return 6.0

    def size(self):
        return 1400.0, 260.0

    def draw(self, pen, t):
        _floor(pen, 1600, 300, "#555555")
        k = 5.0
        cx = 400 + self.x(t) * k
        pen.box(cx, 10, -60, w=140, h=50, d=70, c=RED)
        pen.capsule(400, 10, 100, r=20, h=120, c="#3a86ff")
        for j in range(6):                                                 # wave crests bunch up in front
            age = (t * 2 + j / 6.0) % 1.0
            tx = cx - self.v * k * age * 0.6
            ring(pen, tx, 40, -60, 20 + self.c * k * age * 0.08, c="#ffd166", w=2, plane="xz", n=30)

    def values(self, t):
        return [("horn", f"{self.f:g} Hz"), ("car speed", f"{self.v:g} m/s"), ("you hear", f"{self.heard(t):.0f} Hz"),
                ("", "coming: higher (waves squeezed), going: lower (waves stretched)")]

    def graph(self):
        return ("time (s)", "Hz heard", lambda t: self.heard(t), self.f * 1.15, ["#3a86ff"])

    def sounds(self):
        return [(2.5, "car_horn")]


CLASS11 = (Measurement, Vectors, RiverBoat, RelativeSpeed, BankedRoad, Torque, RollingRace, Skater, Gyroscope, Satellite,
           Kepler, Elasticity, HydraulicLift, Bernoulli, Viscosity, SurfaceTension, Expansion, HeatingCurve, Cooling,
           GasParticles, HeatEngine, Resonance, StandingWaves, Beats, Doppler)
CLASS11_ALIASES = {
    "errors": "measurement", "average": "measurement", "vector": "vectors", "resultant": "vectors",
    "boat_river": "river_boat", "crossing": "river_boat", "trains": "relative_speed", "banking": "banked_road",
    "door": "torque", "moment": "torque", "moment_of_inertia": "rolling_race", "ring_disc_ball": "rolling_race",
    "angular_momentum": "skater", "ice_skater": "skater", "top": "gyroscope", "spinning_top": "gyroscope",
    "precession": "gyroscope", "orbit_speed": "satellite", "escape_speed": "satellite", "weightless": "satellite",
    "ellipse": "kepler", "keplers_laws": "kepler", "hookes_law": "elasticity", "stress_strain": "elasticity",
    "pascal": "hydraulic_lift", "hydraulic": "hydraulic_lift", "wing": "bernoulli", "lift": "bernoulli",
    "terminal_speed": "viscosity", "stokes": "viscosity", "needle_float": "surface_tension",
    "thermal_expansion": "expansion", "bimetal": "expansion", "melting_boiling": "heating_curve",
    "latent_heat": "heating_curve", "newton_cooling": "cooling", "kinetic_theory": "gas_particles",
    "gas_laws": "gas_particles", "engine": "heat_engine", "thermodynamics": "heat_engine",
    "harmonics": "standing_waves", "doppler_effect": "doppler",
}
CLASS11_KEYS = {
    "measurement": '"readings": 8', "vectors": '"a": 30, "a_angle": 0, "b": 40, "b_angle": 90',
    "river_boat": '"boat": 4, "river": 3, "width": 40', "relative_speed": '"v1": 20, "v2": 15, "way": "same|opposite"',
    "banked_road": '"speed": 20, "radius": 100', "torque": '"need": 6, "near": 0.1, "far": 0.8',
    "rolling_race": '"angle": 20, "length": 2', "skater": '"arms_out": 4, "arms_in": 1.6, "spin": 2',
    "gyroscope": '"spin": 20, "tilt": 25', "satellite": '"height": 400 (km)', "kepler": '"e": 0.6, "year": 8',
    "elasticity": '"length": 2, "diameter": 0.5 (mm)', "hydraulic_lift": '"small": 0.001, "big": 0.1, "mass": 1000',
    "bernoulli": '"speed": 60, "area": 16', "viscosity": '"radius": 2 (mm), "viscosity": 0.9',
    "surface_tension": '"soap": 4', "expansion": '"length": 12, "heat": 40',
    "heating_curve": '"mass": 0.5, "power": 2000', "cooling": '"start": 90, "room": 25, "k": 0.05',
    "gas_particles": '"temperature": 300, "hot": 600, "heat": 3', "heat_engine": '"hot": 600, "cold": 300',
    "resonance": '"natural": 0.5, "push": 0.5, "damping": 0.08', "standing_waves": '"length": 1, "speed": 100',
    "beats": '"f1": 256, "f2": 260', "doppler": '"horn": 400, "speed": 25',
}
