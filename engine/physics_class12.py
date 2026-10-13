"""School physics, Class 12 (NCERT order) - the same pattern as engine/physics.py. "S" = shown simpler (a model).

    coulomb            a comb rubbed on hair picks up paper; two charges: F = k·q₁·q₂ / r², attract / repel
    field_lines        (S) field lines round + and - charges
    potential          (S) electric potential like height on a hill: a charge rolls "downhill"
    capacitor          charging and discharging through a bulb: V = V₀(1 - e^(-t/RC)), the bulb fades
    kirchhoff          two loops: the currents at a junction add up (I₁ = I₂ + I₃), voltages round a loop
    wheatstone         a Wheatstone bridge: balanced when P/Q = R/S (no current in the galvanometer)
    cyclotron          (M) a charge circling in a magnetic field: r = m·v / q·B, spiralling out in a cyclotron
    earth_magnet       (S) the Earth as a big magnet: field lines, the dip of a compass needle
    induction          (M) a magnet pushed into a coil: the needle jumps (Faraday), Lenz's law, eddy currents
    transformer        (M) step up / step down: Vs / Vp = Ns / Np
    spectrum           the electromagnetic spectrum, radio to gamma, with uses
    tir                total internal reflection: light trapped in an optical fibre (past the critical angle)
    telescope          a telescope / microscope: two lenses, the magnification
    double_slit        (M) Young's two slits: bright and dark bands, fringe width β = λD / d
    polarisation       (M) two polaroids: the light dims as one turns (Malus: I = I₀ cos²θ)
    photoelectric      (S) light knocks electrons out only above a frequency (E = hf - φ)
    rutherford         (S) alpha particles at gold foil: most go through, a few bounce back
    bohr               (S) Bohr's orbits: an electron jumping down gives a line of colour
    half_life          atoms decaying at random: half are left after each half-life
    fission            (S) a chain reaction: one neutron splits a nucleus, which frees more neutrons
    diode              (S) a diode lets current one way; an LED lights; a solar cell
    logic_gate         (S) AND / OR / NOT gates with switches and a bulb
"""
import math
import random

from .physics import Exp, M, TAU, _num, _list, arrow, ring, dashed, ARROW_F, ARROW_V, RED, BLUE, GREEN, YELLOW

K_E = 8.99e9


def _table(pen, w=700):
    pen.box(0, 0, 0, w=w, h=60, d=260, c="#7a5a3a", top="#a07850")


def _charge(pen, x, y, z, q, r=26):
    pen.sphere(x, y, z, r=r, c=RED if q > 0 else BLUE)
    pen.box(x, y - 3, z - r - 1, w=r * 1.1, h=6, d=2, c="#ffffff")
    if q > 0:
        pen.box(x, y - r * 0.55, z - r - 1, w=6, h=r * 1.1, d=2, c="#ffffff")


# ============================================================================ electrostatics
class Coulomb(Exp):
    name, title = "coulomb", "Electric charges: Coulomb's law"

    def setup(self):
        self.q1 = _num(self.spec, "q1", 1.0, -100, 100) * 1e-6              # µC
        self.q2 = _num(self.spec, "q2", -1.0, -100, 100) * 1e-6
        self.r0 = _num(self.spec, "distance", 0.1, 0.01, 10)

    def r(self, t):
        return self.r0 * (1 + max(0.0, t - 3.0) * 0.5)

    def F(self, t):
        return K_E * self.q1 * self.q2 / self.r(t) ** 2

    def length(self):
        return 6.0

    def size(self):
        return 900.0, 320.0

    def draw(self, pen, t):
        _table(pen)
        y = 62
        if t < 2.5:                                                        # a comb rubbed on hair picks up paper bits
            pen.box(-200, y + 60 + 30 * math.sin(t * 6), 0, w=160, h=16, d=20, c="#3a86ff")
            for k in range(6):
                up = min(1.0, max(0.0, t - 0.8) / 0.4)
                pen.box(-260 + 24 * k, y + 2 + 50 * up * (k % 2), 30, w=14, h=2, d=14, c="#ffffff")
        d = min(300.0, 120 * self.r(t) / self.r0)
        _charge(pen, 150 - d / 2, y + 60, 0, self.q1)
        _charge(pen, 150 + d / 2, y + 60, 0, self.q2)
        s = 1 if self.F(t) < 0 else -1                                     # attract: arrows toward each other
        L = 70 * min(1.0, abs(self.F(t)) / abs(self.F(0.0)) + 0.1)
        arrow(pen, (150 - d / 2, y + 110, -30), (150 - d / 2 + s * L, y + 110, -30), ARROW_F, r=3)
        arrow(pen, (150 + d / 2, y + 110, -30), (150 + d / 2 - s * L, y + 110, -30), ARROW_F, r=3)

    def facts(self):
        F0 = abs(self.F(0.0))
        return [("force at the start", f"{F0:.3f} N"), ("at twice the distance", f"{F0 / 4:.3f} N"),
                ("start distance", f"{self.r0:g} m")]

    def values(self, t):
        F = self.F(t)
        return [("charges", f"{self.q1 * 1e6:+g} µC and {self.q2 * 1e6:+g} µC"), ("distance", f"{self.r(t) * 100:.0f} cm"),
                ("force F = k·q₁·q₂ / r²", f"{abs(F):.2f} N - {'attract' if F < 0 else 'repel'}"),
                ("", "unlike charges attract, like charges repel; twice as far = ¼ the force")]


class FieldLines(Exp):
    name, title = "field_lines", "Electric field lines"

    def setup(self):
        self.kind = str(self.spec.get("kind", "dipole")).lower()           # dipole | like | single

    def length(self):
        return 5.0

    def size(self):
        return 800.0, 500.0

    def draw(self, pen, t):
        y0 = 250
        qs = [(-150, 1), (150, -1)] if self.kind == "dipole" else ([(-150, 1), (150, 1)] if self.kind == "like" else [(0, 1)])
        for x, q in qs:
            _charge(pen, x, y0, 0, q)
        u = min(1.0, t / 2.0)
        for x0, q0 in qs:
            if q0 < 0:
                continue
            for k in range(12):                                            # trace each line by small steps along E
                a = TAU * k / 12
                px, py = x0 + 30 * math.cos(a), y0 + 30 * math.sin(a)
                pts = [(px, py, 0)]
                for _ in range(int(60 * u) + 1):
                    ex = ey = 0.0
                    for xq, q in qs:
                        dx, dy = px - xq, py - y0
                        r3 = (dx * dx + dy * dy) ** 1.5 + 1e-6
                        ex += q * dx / r3
                        ey += q * dy / r3
                    n = math.hypot(ex, ey) or 1
                    px, py = px + 10 * ex / n, py + 10 * ey / n
                    if any(math.hypot(px - xq, py - y0) < 26 for xq, q in qs if q < 0) or abs(px) > 400 or \
                            abs(py - y0) > 240:
                        break
                    pts.append((px, py, 0))
                if len(pts) > 1:
                    pen.tube(pts, 2, c="#ffd166", sides=4)

    def values(self, t):
        return [("", "lines start on + and end on -"), ("", "closer lines = a stronger field"),
                ("", "a + charge put on a line is pushed along it")]


class Potential(Exp):
    name, title = "potential", "Electric potential: like height on a hill"

    def length(self):
        return 6.0

    def size(self):
        return 800.0, 400.0

    def h(self, x, z):
        return 180 * math.exp(-((x + 150) ** 2 + z ** 2) / 15000) - 180 * math.exp(-((x - 150) ** 2 + z ** 2) / 15000)

    def draw(self, pen, t):
        y0 = 200
        n = 16
        for i in range(n):
            for j in range(n):
                x0, x1 = -400 + 800 * i / n, -400 + 800 * (i + 1) / n
                z0, z1 = -200 + 400 * j / n, -200 + 400 * (j + 1) / n
                hh = self.h((x0 + x1) / 2, (z0 + z1) / 2)
                c = (min(1.0, 0.5 + hh / 300), 0.5, min(1.0, 0.5 - hh / 300))
                pen.poly([(x0, y0 + self.h(x0, z0), z0), (x1, y0 + self.h(x1, z0), z0), (x1, y0 + self.h(x1, z1), z1),
                          (x0, y0 + self.h(x0, z1), z1)], c=c)
        x = -150 + 300 * min(1.0, max(0.0, t - 1.0) / 3.0) ** 2
        pen.sphere(x, y0 + self.h(x, 0) + 14, 0, r=12, c="#ffd23f")

    def values(self, t):
        return [("+ charge", "a hill (high potential)"), ("- charge", "a valley (low potential)"),
                ("", "a + charge rolls from high to low potential, like a ball downhill"), ("V", "energy per coulomb (volts)")]


# ============================================================================ circuits
class Capacitor(Exp):
    name, title = "capacitor", "A capacitor charging and discharging"

    def setup(self):
        self.R = _num(self.spec, "resistance", 1000.0, 1, 1e7)
        self.C = _num(self.spec, "capacitance", 1000e-6, 1e-9, 10)
        self.V0 = _num(self.spec, "volts", 9.0, 0.5, 1000)
        self.tau = self.R * self.C
        self.switch = _num(self.spec, "switch", 3.0 * self.tau + 1.0, 0.5, 60)

    def V(self, t):
        if t < self.switch:
            return self.V0 * (1 - math.exp(-t / self.tau))
        Vs = self.V0 * (1 - math.exp(-self.switch / self.tau))
        return Vs * math.exp(-(t - self.switch) / self.tau)

    def length(self):
        return self.switch + 3.5 * self.tau + 1.0

    def size(self):
        return 700.0, 320.0

    def draw(self, pen, t):
        _table(pen)
        y = 62
        pen.box(-80, y, 0, w=14, h=100, d=80, c="#adb5bd")
        pen.box(-50, y, 0, w=14, h=100, d=80, c="#adb5bd")
        q = self.V(t) / self.V0
        for k in range(int(q * 8)):
            pen.dot(-88, y + 15 + 10 * k, -42, r=4, c=RED)
            pen.dot(-42, y + 15 + 10 * k, -42, r=4, c=BLUE)
        b = abs(self.V(t + 0.02) - self.V(t)) / 0.02 * self.tau / self.V0  # the bulb glows with the current
        pen.sphere(180, y + 60, 0, r=28, c="#fff6cc")
        if b > 0.05:
            pen.glow(180, y + 60, 0, 120 * min(1.0, b), "#fff2a0", 0.7 * min(1.0, b))

    def values(self, t):
        st = "charging" if t < self.switch else "discharging through the bulb"
        return [("RC (time constant)", f"{self.tau:.2f} s"), ("now", st), ("voltage", f"{self.V(t):.2f} V"),
                ("", "it fills (and empties) fast at first, then slower: 63 % in one RC")]

    def graph(self):
        return ("time (s)", "volts", lambda t: self.V(t), self.V0 * 1.1, ["#3a86ff"])

    def facts(self):
        return [("supply", f"{self.V0:g} V"), ("time constant RC", f"{self.tau:g} s"),
                ("after one RC (63 %)", f"{self.V0 * (1 - math.exp(-1)):.2f} V"), ("63 %", "63 %")]


class Kirchhoff(Exp):
    name, title = "kirchhoff", "Kirchhoff's rules"

    def setup(self):
        self.V = _num(self.spec, "volts", 12.0, 1, 1000)
        self.R1 = _num(self.spec, "r1", 2.0, 0.1, 1e6)
        self.R2 = _num(self.spec, "r2", 6.0, 0.1, 1e6)
        self.R3 = _num(self.spec, "r3", 3.0, 0.1, 1e6)
        Rp = self.R2 * self.R3 / (self.R2 + self.R3)
        self.I1 = self.V / (self.R1 + Rp)
        Vp = self.I1 * Rp
        self.I2, self.I3 = Vp / self.R2, Vp / self.R3

    def length(self):
        return 6.0

    def size(self):
        return 800.0, 360.0

    def draw(self, pen, t):
        _table(pen, 760)
        y = 62
        pen.box(-280, y, 0, w=60, h=80, d=60, c="#2b2d42")
        for x, z, c in ((-100, -60, "#d4a017"), (150, -100, "#e63946"), (150, 40, "#3a86ff")):
            pen.box(x, y + 10, z, w=120, h=26, d=26, c=c)
        pen.dot(40, y + 22, -60, r=10, c="#ffffff")                         # the junction
        loop = [(-280, -60), (40, -60), (40, -100), (260, -100), (260, 40), (40, 40), (40, -60)]
        for k in range(18):                                                # charges flowing
            d = (k / 18.0 + t * 0.25) % 1.0
            i = int(d * (len(loop) - 1))
            u = d * (len(loop) - 1) - i
            a, b = loop[i], loop[i + 1]
            pen.dot(a[0] + (b[0] - a[0]) * u, y + 30, a[1] + (b[1] - a[1]) * u, r=5, c="#ffd23f")

    def facts(self):
        return [("I₁", f"{self.I1:.2f} A"), ("I₂", f"{self.I2:.2f} A"), ("I₃", f"{self.I3:.2f} A"),
                ("battery", f"{self.V:g} V")]

    def values(self, t):
        return [("into the junction", f"I₁ = {self.I1:.2f} A"), ("out of it", f"I₂ + I₃ = {self.I2:.2f} + {self.I3:.2f} A"),
                ("junction rule", "current in = current out"),
                ("loop rule", f"{self.V:g} V = {self.I1 * self.R1:.1f} V + {self.I2 * self.R2:.1f} V (the drops add up)")]


class Wheatstone(Exp):
    name, title = "wheatstone", "Wheatstone bridge"

    def setup(self):
        self.P = _num(self.spec, "p", 10.0, 0.1, 1e6)
        self.Q = _num(self.spec, "q", 20.0, 0.1, 1e6)
        self.R = _num(self.spec, "r", 15.0, 0.1, 1e6)
        self.S0 = 10.0
        self.S_bal = self.Q * self.R / self.P

    def S(self, t):
        return self.S0 + (self.S_bal - self.S0) * min(1.0, max(0.0, (t - 1.0) / 4.0))

    def needle(self, t):
        S = self.S(t)
        return 40 * (self.R / (self.R + S) - self.P / (self.P + self.Q)) / 0.1

    def length(self):
        return 6.5

    def size(self):
        return 700.0, 400.0

    def draw(self, pen, t):
        _table(pen)
        y = 62
        pts = [(0, y + 260), (-200, y + 140), (0, y + 20), (200, y + 140)]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            pen.line([(a[0], a[1], 0), (b[0], b[1], 0)], c="#d62828", w=3)
        pen.cylinder_axis(0, y + 140, -5, 40, 10, "#f4f1de", axis="z")       # the galvanometer
        a = math.radians(max(-60, min(60, self.needle(t))))
        pen.line([(0, y + 140, -12), (32 * math.sin(a), y + 140 + 32 * math.cos(a), -12)], c="#e63946", w=3)

    def values(self, t):
        S = self.S(t)
        bal = abs(S - self.S_bal) < 0.05 * self.S_bal
        return [("P, Q, R", f"{self.P:g} Ω, {self.Q:g} Ω, {self.R:g} Ω"), ("S now", f"{S:.1f} Ω"),
                ("", f"balanced at S = Q·R / P = {self.S_bal:.1f} Ω - no current in the galvanometer" if bal
                 else "not balanced - the needle moves")]


# ============================================================================ magnetism
class Cyclotron(Exp):
    name, title = "cyclotron", "Charges circling in a magnetic field"

    def setup(self):
        self.B = _num(self.spec, "field", 1.0, 0.01, 20)                   # tesla
        self.m, self.q = 1.67e-27, 1.6e-19                                  # a proton
        self.f = self.q * self.B / (TAU * self.m)

    def length(self):
        return 8.0

    def size(self):
        return 700.0, 600.0

    def draw(self, pen, t):
        y0 = 300
        for s in (-1, 1):                                                  # the two D-shaped boxes
            pts = [(s * 8 + s * 250 * math.sin(a), y0 + 250 * math.cos(a), 0) for a in [k * math.pi / 16 for k in range(17)]]
            pen.tube(pts, 4, c="#adb5bd", sides=4)
        pts = []
        n = 120
        for k in range(int(n * min(1.0, t / 7.0)) + 1):                     # a spiral: each half-turn a little faster
            a = k * math.pi / 12
            r = 20 + 230 * math.sqrt(k / n)
            pts.append((r * math.cos(a), y0 + r * math.sin(a), -6))
        if len(pts) > 1:
            pen.tube(pts, 2.5, c="#e63946", sides=4)
            pen.sphere(*pts[-1], r=8, c=RED)

    def values(self, t):
        return [("field", f"{self.B:g} T"), ("proton turns", f"{self.f / 1e6:.1f} million times a second (f = qB / 2πm)"),
                ("radius r = m·v / q·B", "grows as it speeds up - a spiral"), ("", "the force is always at right angles: it circles")]


class EarthMagnet(Exp):
    name, title = "earth_magnet", "The Earth is a magnet"

    def length(self):
        return 6.0

    def size(self):
        return 800.0, 600.0

    def draw(self, pen, t):
        y0 = 300
        pen.sphere(0, y0, 0, r=140, c="#4f9be0", rings=10, sides=18)
        pen.box(0, y0 - 100, 0, w=30, h=200, d=30, c=RED)                  # (its south pole is near the north)
        u = min(1.0, t / 2.0)
        for k in (-3, -2, -1, 1, 2, 3):
            pts = []
            for i in range(int(40 * u) + 1):
                th = 0.15 + (math.pi - 0.3) * i / 40
                r = 140 + 60 * abs(k) * math.sin(th) ** 2 * 1.5
                pts.append((math.copysign(r * math.sin(th), k), y0 + r * math.cos(th), 0))
            if len(pts) > 1:
                pen.tube(pts, 2, c="#ffd166", sides=4)

    def values(self, t):
        return [("", "the Earth acts like a giant bar magnet"), ("", "a compass's north end points to geographic north"),
                ("dip", "the needle tips down more and more toward the poles (about 40° in Delhi)")]


class Induction(Exp):
    name, title = "induction", "Electromagnetic induction"

    def setup(self):
        self.turns = int(_num(self.spec, "turns", 100, 1, 10000))
        self.speed = _num(self.spec, "speed", 1.0, 0.1, 10)

    def x(self, t):
        return 220 * math.cos(math.pi * self.speed * max(0.0, t - 0.5) / 2) if t > 0.5 else 220

    def emf(self, t, dt=0.01):
        flux = lambda tt: 1.0 / (1 + (self.x(tt) / 60.0) ** 2)
        return -self.turns * (flux(t + dt) - flux(t - dt)) / (2 * dt) * 0.01

    def length(self):
        return 8.0

    def size(self):
        return 800.0, 360.0

    def draw(self, pen, t):
        _table(pen, 760)
        y = 62
        for k in range(10):
            ring(pen, -90 + 20 * k, y + 80, 0, 60, c="#c87533", w=5, plane="yz", n=20)
        mx = self.x(t)
        pen.box(mx + 40, y + 65, 0, w=80, h=30, d=30, c=RED)
        pen.box(mx + 120, y + 65, 0, w=80, h=30, d=30, c=BLUE)
        pen.cylinder_axis(-260, y + 50, 60, 40, 10, "#f4f1de", axis="z")
        a = math.radians(max(-60, min(60, self.emf(t) * 30)))
        pen.line([(-260, y + 50, 52), (-260 + 32 * math.sin(a), y + 50 + 32 * math.cos(a), 52)], c="#e63946", w=3)

    def values(self, t):
        e = self.emf(t)
        return [("turns", str(self.turns)), ("voltage", f"{e:+.2f} V"),
                ("Faraday", "a changing magnetic field makes a voltage; faster = bigger"),
                ("Lenz", "the current flows so as to push against the moving magnet")]

    def graph(self):
        peak = max(abs(self.emf(k * 0.05)) for k in range(160)) or 1
        return ("time (s)", "volts", lambda t: self.emf(t), peak * 1.1, ["#e63946"])


class Transformer(Exp):
    name, title = "transformer", "Transformer: step up, step down"

    def setup(self):
        self.Vp = _num(self.spec, "primary", 230.0, 1, 1e6)
        self.Np = int(_num(self.spec, "np", 1000, 1, 1e6))
        self.Ns = int(_num(self.spec, "ns", 50, 1, 1e6))

    def Vs(self):
        return self.Vp * self.Ns / self.Np

    def length(self):
        return 5.0

    def size(self):
        return 700.0, 400.0

    def draw(self, pen, t):
        _table(pen)
        y = 62
        for x0, x1, z0, z1 in ((-150, 150, -20, 20), (-150, -110, -20, 20), (110, 150, -20, 20)):
            pen.box((x0 + x1) / 2, y, 0, w=x1 - x0, h=40, d=60, c="#6c757d")
        pen.box(-130, y, 0, w=40, h=260, d=60, c="#6c757d")
        pen.box(130, y, 0, w=40, h=260, d=60, c="#6c757d")
        pen.box(0, y + 220, 0, w=300, h=40, d=60, c="#6c757d")
        for x, n in ((-130, min(30, self.Np // 40 + 3)), (130, min(30, self.Ns // 40 + 3))):
            for k in range(n):
                ring(pen, x, y + 60 + 150 * k / n, 0, 40, c="#c87533", w=3, plane="xz", n=16)
        a = math.sin(TAU * 2 * t)
        pen.glow(260, y + 120, 0, 60 + 30 * abs(a), "#fff2a0", 0.4)

    def values(self, t):
        return [("primary", f"{self.Vp:g} V, {self.Np} turns"), ("secondary", f"{self.Ns} turns"),
                ("Vs = Vp × Ns / Np", f"{self.Vs():.1f} V - {'step down' if self.Ns < self.Np else 'step up'}"),
                ("", "power lines use very high voltage so less is lost as heat")]


SPECTRUM = (("radio", "1 m - 1 km", "radio, TV"), ("microwave", "1 mm - 1 m", "cooking, phones, radar"),
            ("infrared", "700 nm - 1 mm", "remote controls, heat"), ("visible", "400 - 700 nm", "our eyes"),
            ("ultraviolet", "10 - 400 nm", "sunburn, killing germs"), ("X-ray", "0.01 - 10 nm", "seeing bones"),
            ("gamma", "< 0.01 nm", "cancer treatment"))


class Spectrum(Exp):
    name, title = "spectrum", "The electromagnetic spectrum"

    def length(self):
        return len(SPECTRUM) * 1.5 + 1

    def size(self):
        return 1100.0, 300.0

    def draw(self, pen, t):
        cols = ("#8d6e63", "#a1887f", "#e63946", "#ffd166", "#9b5de5", "#7ad1e6", "#2a9d48")
        k = min(len(SPECTRUM) - 1, int(t / 1.5))
        for i, (_n, _r, _u) in enumerate(SPECTRUM):
            pen.box(-450 + 150 * i, 0, 0, w=140, h=40 + (60 if i == k else 0), d=60, c=cols[i])
        pts = []
        for j in range(200):                                               # the wave gets shorter left to right
            x = -520 + 1040 * j / 200
            lam = 160 * (0.92 ** (j / 6))
            pts.append((x, 200 + 50 * math.sin(TAU * x / max(lam, 4)), -40))
        pen.tube(pts, 2, c="#ffffff", sides=4)

    def values(self, t):
        k = min(len(SPECTRUM) - 1, int(t / 1.5))
        n, r, u = SPECTRUM[k]
        return [("now", n), ("wavelength", r), ("used for", u), ("", "all travel at 3 × 10⁸ m/s in space")]


# ============================================================================ optics
class TIR(Exp):
    name, title = "tir", "Total internal reflection: an optical fibre"

    def setup(self):
        self.n = _num(self.spec, "n", 1.5, 1.01, 3.0)
        self.crit = math.degrees(math.asin(1 / self.n))

    def length(self):
        return 6.0

    def size(self):
        return 1000.0, 300.0

    def draw(self, pen, t):
        y0, h = 150, 50
        pen.box(0, y0 - h, 0, w=900, h=2 * h, d=60, c=(0.7, 0.9, 1.0, 0.35))
        x, y, d = -450.0, y0, 1
        pts = [(x - 60, y0 + 40, 0)]
        slope = 0.5
        L = min(1.0, t / 4.0) * 900
        travelled = 0.0
        while travelled < L and x < 450:
            dx = h / slope
            x += dx
            y = y0 + d * h
            travelled += dx
            pts.append((min(x, 450), y, 0))
            d = -d
        pen.tube(pts, 3, c="#ffd166", sides=4, smooth=False)

    def values(self, t):
        return [("glass", f"n = {self.n:g}"), ("critical angle", f"sin c = 1/n -> {self.crit:.1f}°"),
                ("", "hitting the side at more than that, all the light reflects back in"),
                ("used in", "optical fibres (internet), the sparkle of a diamond (n = 2.42, c = 24°)")]


class Telescope(Exp):
    name, title = "telescope", "Telescope: two lenses"

    def setup(self):
        self.fo = _num(self.spec, "objective", 1.0, 0.05, 50)              # m
        self.fe = _num(self.spec, "eyepiece", 0.05, 0.005, 1)

    def length(self):
        return 5.0

    def size(self):
        return 1000.0, 300.0

    def draw(self, pen, t):
        y0 = 150
        k = 500 / (self.fo + self.fe)
        xo, xe = -300, -300 + (self.fo + self.fe) * k
        pen.cylinder_axis((xo + xe) / 2, y0, 0, 60, xe - xo, (0.4, 0.4, 0.45, 0.3), axis="x")
        pen.ellipsoid(xo, y0, 0, rx=12, ry=70, rz=70, c=(0.7, 0.9, 1.0, 0.6))
        pen.ellipsoid(xe, y0, 0, rx=8, ry=35, rz=35, c=(0.7, 0.9, 1.0, 0.6))
        fx = xo + self.fo * k
        for h in (-40, 0, 40):
            pen.line([(-480, y0 + h, 0), (xo, y0 + h, 0)], c="#ffd166", w=2)
            pen.line([(xo, y0 + h, 0), (fx, y0, 0)], c="#ffd166", w=2)
            pen.line([(fx, y0, 0), (xe, y0 - h * self.fe / self.fo * 3, 0)], c="#ffd166", w=2)

    def values(self, t):
        return [("objective", f"f = {self.fo * 100:g} cm"), ("eyepiece", f"f = {self.fe * 100:g} cm"),
                ("magnification", f"fo / fe = {self.fo / self.fe:.0f}×"), ("length", f"fo + fe = {(self.fo + self.fe) * 100:.0f} cm")]


class DoubleSlit(Exp):
    name, title = "double_slit", "Young's double slit: interference"

    def setup(self):
        self.lam = _num(self.spec, "wavelength", 600.0, 380, 750) * 1e-9
        self.d = _num(self.spec, "gap", 0.2, 0.01, 5) * 1e-3               # mm
        self.D = _num(self.spec, "screen", 1.0, 0.1, 10)

    def beta(self):
        return self.lam * self.D / self.d

    def length(self):
        return 5.0

    def size(self):
        return 900.0, 400.0

    def draw(self, pen, t):
        y0 = 200
        pen.box(-200, y0 - 150, 0, w=10, h=300, d=10, c="#333333")
        for s in (-1, 1):
            pen.box(-200, y0 + s * 20 - 4, 0, w=12, h=8, d=12, c="#ffffff")
        u = min(1.0, t / 2.0)
        for r in range(1, int(10 * u) + 1):
            for s in (-1, 1):
                ring(pen, -200, y0 + s * 20, 0, 50 * r, c="#ffd166", w=1.5, plane="xy", n=24)
        if t > 2.0:                                                        # the bands on the screen
            for i in range(-12, 13):
                y = y0 + i * 12
                b = math.cos(TAU * i / 6.0) ** 2
                c = (1.0 * b, 0.4 * b, 0.1 * b) if self.lam > 580e-9 else (0.2 * b, 0.9 * b, 0.3 * b)
                pen.box(300, y - 6, 0, w=10, h=12, d=80, c=c)

    def values(self, t):
        return [("light", f"{self.lam * 1e9:.0f} nm"), ("slits", f"{self.d * 1000:g} mm apart, screen {self.D:g} m away"),
                ("fringe width β = λD / d", f"{self.beta() * 1000:.1f} mm"),
                ("", "where the waves meet in step: bright; out of step: dark")]


class Polarisation(Exp):
    name, title = "polarisation", "Polarisation: two polaroids"

    def angle(self, t):
        return min(90.0, max(0.0, t - 1.0) * 20.0)

    def I(self, t):
        return math.cos(math.radians(self.angle(t))) ** 2

    def length(self):
        return 6.5

    def size(self):
        return 900.0, 320.0

    def draw(self, pen, t):
        y0 = 160
        pen.box(-150, y0 - 80, 0, w=8, h=160, d=160, c=(0.3, 0.3, 0.3, 0.5))
        pen.push()
        pen.move(150, y0, 0)
        pen.rotate_x(self.angle(t))
        pen.box(0, -80, 0, w=8, h=160, d=160, c=(0.3, 0.3, 0.3, 0.5))
        pen.pop()
        pen.line([(-450, y0, 0), (-150, y0, 0)], c="#ffffff", w=6)
        pen.line([(-150, y0, 0), (150, y0, 0)], c="#ffd166", w=5)
        b = self.I(t)
        if b > 0.02:
            pen.line([(150, y0, 0), (450, y0, 0)], c="#ffd166", w=1 + 4 * b)
            pen.glow(450, y0, 0, 80 * b, "#fff2a0", 0.6 * b)

    def values(self, t):
        return [("turned by", f"{self.angle(t):.0f}°"), ("light through", f"I = I₀ cos²θ = {self.I(t) * 100:.0f} %"),
                ("", "at 90° no light gets through - light is a transverse wave"), ("used in", "sunglasses, 3D glasses")]


# ============================================================================ modern physics
H, E_CH = 6.626e-34, 1.602e-19


class Photoelectric(Exp):
    name, title = "photoelectric", "The photoelectric effect"

    COLOURS = (("red", 700), ("green", 530), ("violet", 400), ("ultraviolet", 250))

    def setup(self):
        self.phi = _num(self.spec, "work", 2.3, 0.5, 10)                   # eV (sodium)
        self.each = 2.0

    def now(self, t):
        return self.COLOURS[min(3, int(t / self.each))]

    def KE(self, lam):
        return H * 3e8 / (lam * 1e-9) / E_CH - self.phi

    def length(self):
        return self.each * 4

    def size(self):
        return 800.0, 320.0

    def draw(self, pen, t):
        nm, lam = self.now(t)
        pen.box(0, 0, 0, w=200, h=20, d=200, c="#b0b7bf")                  # the metal plate
        col = {"red": "#e63946", "green": "#2a9d48", "violet": "#9b5de5", "ultraviolet": "#c77dff"}[nm]
        for k in range(5):
            x = -300 + 60 * k
            pen.line([(x, 300, 0), (x + 200, 20, 0)], c=col, w=3)
        ke = self.KE(lam)
        if ke > 0:
            u = (t % self.each) / self.each
            for k in range(6):
                pen.sphere(-60 + 24 * k, 30 + 250 * u * math.sqrt(ke), 0, r=6, c="#3a86ff")

    def values(self, t):
        nm, lam = self.now(t)
        E = H * 3e8 / (lam * 1e-9) / E_CH
        ke = E - self.phi
        return [("light", f"{nm}, {lam} nm, E = hf = {E:.2f} eV"), ("metal needs", f"φ = {self.phi:g} eV"),
                ("", f"electrons fly out with {ke:.2f} eV" if ke > 0 else "no electrons, however bright the light"),
                ("", "light comes in packets (photons): only the colour (frequency) decides")]


class Rutherford(Exp):
    name, title = "rutherford", "Rutherford's gold foil"

    def length(self):
        return 6.0

    def size(self):
        return 900.0, 400.0

    def draw(self, pen, t):
        y0 = 200
        pen.box(0, y0 - 150, 0, w=6, h=300, d=200, c="#d4af37")
        rr = random.Random(5)
        for i in range(40):
            b = rr.uniform(-140, 140)                                      # how close it passes a nucleus
            start = rr.uniform(0, 3.0)
            u = (t - start) / 2.0
            if u < 0 or u > 1:
                continue
            x = -450 + 900 * u
            close = abs(b) < 6
            if x > 0 and close:
                x = -900 * (u - 0.5)                                       # bounced back
            y = y0 + b + (0 if x < 0 else math.copysign(min(80.0, 300.0 / max(abs(b), 1)), b) * (x / 450))
            pen.dot(x, y, 0, r=5, c="#e63946")

    def values(self, t):
        return [("alpha particles", "shot at a thin gold foil"), ("most", "go straight through: the atom is mostly empty"),
                ("a few", "bounce back: a tiny, heavy, + nucleus in the middle")]


class Bohr(Exp):
    name, title = "bohr", "Bohr's atom and line spectra"

    LINES = ((3, 656, "#e63946"), (4, 486, "#2ab7ca"), (5, 434, "#5e60ce"))     # Balmer lines of hydrogen

    def length(self):
        return 9.0

    def size(self):
        return 800.0, 500.0

    def draw(self, pen, t):
        y0 = 250
        pen.sphere(0, y0, 0, r=14, c=RED)
        for n in range(1, 6):
            ring(pen, 0, y0, 0, 30 * n * n * 0.6 + 20, c="#8d99ae", w=1.5, plane="xy", n=40)
        k = min(2, int(t / 3.0))
        n, lam, col = self.LINES[k]
        u = (t % 3.0) / 3.0
        r_hi, r_lo = 30 * n * n * 0.6 + 20, 30 * 4 * 0.6 + 20
        r = r_hi if u < 0.4 else (r_hi + (r_lo - r_hi) * min(1.0, (u - 0.4) / 0.2))
        pen.sphere(r, y0, 0, r=8, c=BLUE)
        if u > 0.6:
            pen.line([(r_lo, y0, 0), (r_lo + 300 * (u - 0.6) / 0.4, y0 + 60, 0)], c=col, w=4)
            pen.box(300, 60, 0, w=6, h=80, d=30, c=col)

    def values(self, t):
        k = min(2, int(t / 3.0))
        n, lam, _c = self.LINES[k]
        E = 13.6 * (1 / 4 - 1 / n ** 2)
        return [("jump", f"orbit {n} -> orbit 2"), ("energy given out", f"{E:.2f} eV"), ("light", f"{lam} nm"),
                ("", "only certain orbits are allowed: only certain colours (a line spectrum)")]


class HalfLife(Exp):
    name, title = "half_life", "Radioactive decay: half-life"

    def setup(self):
        self.N0 = int(_num(self.spec, "atoms", 400, 20, 2000))
        self.T = _num(self.spec, "half_life", 2.0, 0.2, 20)               # seconds on screen
        rr = random.Random(11)
        self.when = [rr.expovariate(math.log(2) / self.T) for _ in range(self.N0)]

    def left(self, t):
        return sum(1 for w in self.when if w > t)

    def length(self):
        return self.T * 4 + 1

    def size(self):
        return 700.0, 500.0

    def draw(self, pen, t):
        n = int(math.sqrt(self.N0)) + 1
        for i, w in enumerate(self.when):
            x, y = -250 + 500 * (i % n) / n, 20 + 450 * (i // n) / n
            pen.dot(x, y, 0, r=6, c="#2a9d48" if w > t else "#6c757d")

    def values(self, t):
        N = self.left(t)
        return [("half-life", f"{self.T:g} s"), ("atoms left", f"{N} of {self.N0} ({100 * N / self.N0:.0f} %)"),
                ("expected", f"N = N₀ (½)^(t/T) = {self.N0 * 0.5 ** (t / self.T):.0f}"),
                ("", "each atom decays at random - but half are always gone after one half-life")]

    def graph(self):
        return ("time (s)", "atoms left", lambda t: self.left(t), self.N0 * 1.05, ["#2a9d48"])


class Fission(Exp):
    name, title = "fission", "Nuclear fission: a chain reaction"

    def length(self):
        return 6.0

    def size(self):
        return 900.0, 500.0

    def draw(self, pen, t):
        y0 = 250
        gen = min(4, int(t / 1.2))
        rr = random.Random(3)
        for g in range(gen + 1):
            n = 3 ** g if g < 4 else 27
            for i in range(min(n, 27)):
                a = TAU * (i + rr.random() * 0.3) / min(n, 27)
                r = 80 * g
                x, y = r * math.cos(a), y0 + r * math.sin(a) * 0.8
                split = g < gen
                pen.sphere(x, y, 0, r=16 if not split else 8, c="#ffb703" if not split else "#adb5bd")
                if split:
                    pen.glow(x, y, 0, 40, "#ffdd66", 0.3)

    def values(self, t):
        gen = min(4, int(t / 1.2))
        return [("step", str(gen)), ("nuclei split so far", f"{sum(3 ** g for g in range(gen))}"),
                ("", "each split gives energy (E = mc²) and 2-3 neutrons that split more nuclei"),
                ("", "a reactor controls the chain; a bomb does not")]


class Diode(Exp):
    name, title = "diode", "Semiconductors: a diode, an LED, a solar cell"

    def setup(self):
        self.each = 2.5

    def stage(self, t):
        return min(2, int(t / self.each))

    def length(self):
        return self.each * 3

    def size(self):
        return 700.0, 320.0

    def draw(self, pen, t):
        _table(pen)
        y = 62
        st = self.stage(t)
        pen.cylinder_axis(-200, y + 30, 0, 26, 64, "#2b2d42", axis="x")
        pen.cone(60, y + 30, 0, r=20, h=40, c="#333333")
        led_on = st == 0
        pen.sphere(200, y + 50, 0, r=22, c="#ff4d6d" if led_on else "#552222")
        if led_on:
            pen.glow(200, y + 50, 0, 120, "#ff4d6d", 0.7)
        if st == 2:                                                        # a solar cell in the sun
            pen.box(0, y + 100, 100, w=200, h=6, d=120, c="#1d3557")
            pen.sphere(-250, y + 260, 100, r=30, c="#ffd23f")

    def values(self, t):
        st = self.stage(t)
        return [("", ("forward: current flows - the LED lights", "reversed: the diode blocks it - no light",
                      "a solar cell: light makes a current (about 0.5 V a cell)")[st]),
                ("", "a diode lets current go one way only")]


class LogicGate(Exp):
    name, title = "logic_gate", "Logic gates: AND, OR, NOT"

    def setup(self):
        self.kind = str(self.spec.get("kind", "and")).lower()

    def inputs(self, t):
        k = min(3, int(t / 1.5))
        return (k >> 1) & 1, k & 1

    def out(self, t):
        a, b = self.inputs(t)
        return {"and": a & b, "or": a | b, "not": 1 - a, "nand": 1 - (a & b), "nor": 1 - (a | b)}.get(self.kind, a & b)

    def length(self):
        return 6.0

    def size(self):
        return 700.0, 320.0

    def draw(self, pen, t):
        _table(pen)
        y = 62
        a, b = self.inputs(t)
        for z, v in ((-60, a), (60, b)) if self.kind != "not" else ((0, a),):
            pen.box(-200, y, z, w=40, h=20 + 20 * v, d=30, c="#2a9d48" if v else "#6c757d")
        pen.box(0, y, 0, w=120, h=80, d=100, c="#1d3557")
        o = self.out(t)
        pen.sphere(220, y + 40, 0, r=24, c="#fff6cc" if o else "#e8eef2")
        if o:
            pen.glow(220, y + 40, 0, 110, "#fff2a0", 0.7)

    def values(self, t):
        a, b = self.inputs(t)
        rule = {"and": "on only if both are on", "or": "on if either is on", "not": "the opposite of the input",
                "nand": "off only if both are on", "nor": "on only if both are off"}.get(self.kind, "")
        ins = f"A = {a}" if self.kind == "not" else f"A = {a}, B = {b}"
        return [("gate", self.kind.upper()), ("inputs", ins), ("output", str(self.out(t))), ("", rule)]


CLASS12 = (Coulomb, FieldLines, Potential, Capacitor, Kirchhoff, Wheatstone, Cyclotron, EarthMagnet, Induction,
           Transformer, Spectrum, TIR, Telescope, DoubleSlit, Polarisation, Photoelectric, Rutherford, Bohr, HalfLife,
           Fission, Diode, LogicGate)
CLASS12_ALIASES = {
    "charges": "coulomb", "static": "coulomb", "comb": "coulomb", "electric_field": "field_lines",
    "voltage_hill": "potential", "rc": "capacitor", "capacitors": "capacitor", "junction_rule": "kirchhoff",
    "bridge": "wheatstone", "magnetic_force": "cyclotron", "earths_magnetism": "earth_magnet",
    "faraday": "induction", "lenz": "induction", "eddy_currents": "induction", "step_up": "transformer",
    "step_down": "transformer", "em_spectrum": "spectrum", "electromagnetic_spectrum": "spectrum",
    "optical_fibre": "tir", "total_internal_reflection": "tir", "microscope": "telescope",
    "interference": "double_slit", "young": "double_slit", "diffraction": "double_slit", "polaroid": "polarisation",
    "polarization": "polarisation", "photons": "photoelectric", "gold_foil": "rutherford", "atom_model": "bohr",
    "line_spectrum": "bohr", "decay": "half_life", "radioactivity": "half_life", "chain_reaction": "fission",
    "fusion": "fission", "led": "diode", "solar_cell": "diode", "semiconductor": "diode", "gates": "logic_gate",
}
CLASS12_KEYS = {
    "coulomb": '"q1": 1, "q2": -1 (µC), "distance": 0.1', "field_lines": '"kind": "dipole|like|single"',
    "potential": '', "capacitor": '"resistance": 1000, "capacitance": 0.001, "volts": 9',
    "kirchhoff": '"volts": 12, "r1": 2, "r2": 6, "r3": 3', "wheatstone": '"p": 10, "q": 20, "r": 15',
    "cyclotron": '"field": 1', "earth_magnet": '', "induction": '"turns": 100, "speed": 1',
    "transformer": '"primary": 230, "np": 1000, "ns": 50', "spectrum": '', "tir": '"n": 1.5',
    "telescope": '"objective": 1, "eyepiece": 0.05', "double_slit": '"wavelength": 600, "gap": 0.2, "screen": 1',
    "polarisation": '', "photoelectric": '"work": 2.3', "rutherford": '', "bohr": '',
    "half_life": '"atoms": 400, "half_life": 2', "fission": '', "diode": '', "logic_gate": '"kind": "and|or|not|nand|nor"',
}
