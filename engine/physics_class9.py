"""School physics, Class 9 (NCERT order) - the same pattern as engine/physics.py: true formulas, simple 3D
shapes, the numbers and a graph on the panel (pure physics).

    motion_graphs       two carts: one at a steady speed, one speeding up - distance-time and speed-time graphs
    newton_second       the same push on a light and a heavy cart: a = F / m
    action_reaction     a balloon rocket on a string (and a gun's recoil): every push has an equal push back
    impulse             catching an egg with stiff vs soft hands (a seat belt): same change of speed, longer time
                        = smaller force (F = m·Δv / Δt)
    gravitation         two masses pull each other: F = G·m₁·m₂ / r² - the pull as they move apart
    mass_weight         the same 10 kg on the Earth, the Moon, Mars, Jupiter: mass stays, weight changes (W = m·g)
    archimedes          a stone on a spring balance lowered into water: the weight lost = the water pushed out
    work_power          two people lift the same load, one fast, one slow: same work (m·g·h), different power
    energy_chain        water from a dam turns a turbine that lights a bulb: height energy -> motion -> electricity
    echo                a clap and its echo from a wall: distance = speed × time / 2
    sonar               a ship's ping to the sea floor and back: depth = 1500 m/s × time / 2
"""
import math

from .physics import Exp, M, TAU, _num, _list, arrow, ring, ARROW_F, ARROW_V, RED, BLUE, GREEN, YELLOW


def _floor(pen, w=1600, d=360):
    pen.box(w / 2 - 300, 0, 0, w=w, h=8, d=d, c="#b9b6ad")


def _cart(pen, x, y, z, c, w=120, h=50, turn=0.0):
    pen.box(x, y + 18, z, w=w, h=h, d=70, c=c)
    for k in (-1, 1):
        for zz in (-30, 30):
            pen.wheel(x + k * w * 0.32, y + 12, z + zz, r=12, c="#333333", w=6, spokes=4, turn=turn)


SCALE = 0.35 * M              # 1 m on the track drawn this long


class MotionGraphs(Exp):
    name, title = "motion_graphs", "Motion: distance-time and speed-time"

    def setup(self):
        self.v = _num(self.spec, "speed", 1.0, 0.1, 10)                     # the steady cart (m/s)
        self.a = _num(self.spec, "acceleration", 0.4, 0.05, 5)              # the other speeds up from rest

    def length(self):
        return 6.0

    def size(self):
        return 1700.0, 260.0

    def d1(self, t):
        return self.v * t

    def d2(self, t):
        return 0.5 * self.a * t * t

    def draw(self, pen, t):
        _floor(pen)
        for k in range(0, 9):                                               # metre marks
            pen.box(-300 + k * SCALE, 8, 150, w=3, h=2, d=40, c="#555555")
        _cart(pen, -300 + self.d1(t) * SCALE, 8, -70, BLUE, turn=-self.d1(t) * 8)
        _cart(pen, -300 + self.d2(t) * SCALE, 8, 70, RED, turn=-self.d2(t) * 8)

    def values(self, t):
        return [("blue (steady)", f"{self.d1(t):.2f} m, {self.v:.2f} m/s"),
                ("red (speeding up)", f"{self.d2(t):.2f} m, {self.a * t:.2f} m/s"),
                ("", "steady speed: a straight distance line; speeding up: a curve")]

    def graph(self):
        return ("time (s)", "distance (m)", lambda t: [self.d1(t), self.d2(t)],
                max(self.d1(6.0), self.d2(6.0)) * 1.1, ["#3a86ff", "#e63946"])


class NewtonSecond(Exp):
    name, title = "newton_second", "Newton's second law: F = m·a"

    def setup(self):
        self.F = _num(self.spec, "force", 10, 0.5, 500)
        self.m1 = _num(self.spec, "m1", 2, 0.1, 500)
        self.m2 = _num(self.spec, "m2", 8, 0.1, 500)
        self.push = _num(self.spec, "push", 2.0, 0.2, 10)                    # the push lasts this long

    def x(self, m, t):
        a = self.F / m
        if t <= self.push:
            return 0.5 * a * t * t
        v = a * self.push
        return 0.5 * a * self.push ** 2 + v * (t - self.push)

    def length(self):
        return self.push + 2.0

    def size(self):
        return 1700.0, 260.0

    def draw(self, pen, t):
        _floor(pen)
        for m, z, c in ((self.m1, -70, BLUE), (self.m2, 70, RED)):
            x = -300 + min(self.x(m, t), 7.5) * SCALE
            _cart(pen, x, 8, z, c, w=80 + 10 * m ** (1 / 3.0) * 4)
            if t <= self.push:
                arrow(pen, (x - 160, 50, z), (x - 80, 50, z), ARROW_F, r=4)

    def values(self, t):
        a1, a2 = self.F / self.m1, self.F / self.m2
        return [("same push", f"{self.F:g} N for {self.push:g} s"), (f"{self.m1:g} kg cart", f"a = F/m = {a1:.2f} m/s²"),
                (f"{self.m2:g} kg cart", f"a = F/m = {a2:.2f} m/s²"), ("", "more mass, less acceleration")]

    def graph(self):
        return ("time (s)", "speed (m/s)",
                lambda t: [self.F / self.m1 * min(t, self.push), self.F / self.m2 * min(t, self.push)],
                self.F / min(self.m1, self.m2) * self.push * 1.1, ["#3a86ff", "#e63946"])


class ActionReaction(Exp):
    name, title = "action_reaction", "Action and reaction (Newton's third law)"

    def setup(self):
        self.kind = str(self.spec.get("kind", "balloon")).lower()
        self.thrust = 0.6                                                   # N (air out of the balloon)
        self.m = 0.05                                                       # kg
        self.burn = 2.0
        self.gun_m, self.bullet_m, self.bullet_v = 4.0, 0.02, 350.0

    def x(self, t):
        if self.kind == "gun":
            v = self.bullet_m * self.bullet_v / self.gun_m                  # recoil speed
            return -v * min(t, 0.3) * max(0.0, 1 - t / 0.6) if t > 1.0 else 0.0
        a = self.thrust / self.m - 0.5 * 9.81                               # string friction
        tb = min(t, self.burn)
        x = 0.5 * a * tb * tb
        if t > self.burn:
            v = a * self.burn
            dt_ = t - self.burn
            x += v * dt_ - 0.5 * 4.0 * dt_ * dt_ if dt_ < v / 4.0 else v * v / 8.0
        return min(x, 9.0)

    def length(self):
        return 4.5

    def size(self):
        return 1700.0, 360.0

    def draw(self, pen, t):
        if self.kind == "gun":
            _floor(pen, 900)
            rx = self.x(t) * M * 3
            pen.box(rx, 60, 0, w=200, h=30, d=30, c="#4a4e69")
            pen.box(rx - 60, 30, 0, w=40, h=60, d=30, c="#6b4528")
            if t > 1.0:
                bx = 110 + (t - 1.0) * 1200
                if bx < 900:
                    pen.sphere(bx, 75, 0, r=6, c="#d4a017")
            return
        y = 220
        pen.box(-320, 0, 0, w=20, h=y + 20, d=20, c="#6b4528")
        pen.box(1300, 0, 0, w=20, h=y + 20, d=20, c="#6b4528")
        pen.line([(-320, y, 0), (1300, y, 0)], c="#dddddd", w=2)
        x = -250 + self.x(t) * SCALE
        on = t < self.burn
        r = 40 * (1.0 - 0.45 * min(1.0, t / self.burn)) if on else 22
        pen.ellipsoid(x, y - 10, 0, rx=r * 1.5, ry=r, rz=r, c=RED)
        pen.cylinder(x, y + 5, 0, r=4, h=14, c="#cccccc")
        if on:
            for k in range(6):
                pen.dot(x - r * 1.5 - 10 - 18 * k, y - 10 + 5 * math.sin(t * 20 + k), 0, r=6 - k * 0.8, c="#e8f4ff")
            arrow(pen, (x - r * 1.5, y - 60, -20), (x - r * 1.5 - 70, y - 60, -20), "#3a86ff", r=3)
            arrow(pen, (x + r * 1.5, y - 60, -20), (x + r * 1.5 + 70, y - 60, -20), ARROW_F, r=3)

    def values(self, t):
        if self.kind == "gun":
            v = self.bullet_m * self.bullet_v / self.gun_m
            return [("bullet", f"{self.bullet_m * 1000:g} g at {self.bullet_v:g} m/s"),
                    ("gun", f"{self.gun_m:g} kg kicks back at {v:.2f} m/s"),
                    ("momentum", f"{self.bullet_m * self.bullet_v:.1f} = {self.gun_m * v:.1f} kg·m/s (equal, opposite)")]
        return [("air pushed out", "backwards"), ("the balloon is pushed", "forwards - equally hard"),
                ("", "every action has an equal and opposite reaction"), ("travelled", f"{self.x(t):.2f} m")]


class Impulse(Exp):
    name, title = "impulse", "Soft hands: stopping slowly makes the force small"

    def setup(self):
        self.m = _num(self.spec, "mass", 0.06, 0.01, 100)                   # an egg
        self.v = _num(self.spec, "speed", 5.0, 0.5, 40)
        self.t_hard = _num(self.spec, "stiff", 0.005, 0.001, 1)             # time to stop: stiff hands / a wall
        self.t_soft = _num(self.spec, "soft", 0.2, 0.01, 2)                 # soft hands moving back / a seat belt
        self.catch = 1.2

    def force(self, dt_):
        return self.m * self.v / dt_

    def length(self):
        return 4.0

    def size(self):
        return 900.0, 360.0

    def draw(self, pen, t):
        for z, dt_, hard in ((-90, self.t_hard, True), (90, self.t_soft, False)):
            y = 150 + max(0.0, self.catch - t) * self.v * 30
            stop = t >= self.catch
            if hard:
                pen.box(0, 0, z, w=90, h=100, d=80, c="#7a7a7a")             # a hard hand / the floor
                if stop:
                    for k in range(6):
                        a = k * TAU / 6
                        pen.dot(math.cos(a) * 30 * min(1, (t - self.catch) * 4), 110, z + math.sin(a) * 20, r=6,
                                c="#fff3d6")
                else:
                    pen.ellipsoid(0, y, z, rx=16, ry=22, rz=16, c="#fff3d6")
            else:
                give = min(1.0, (t - self.catch) / max(self.t_soft, 0.05)) if stop else 0.0
                pen.round_box(0, 100 - 60 * give, z, w=110, h=30, d=80, c="#e0ac69", r=12)
                pen.ellipsoid(0, (130 - 60 * give) if stop else y, z, rx=16, ry=22, rz=16, c="#fff3d6")

    def values(self, t):
        return [("egg", f"{self.m * 1000:g} g at {self.v:g} m/s"),
                ("stiff hands", f"stops in {self.t_hard * 1000:g} ms: F = {self.force(self.t_hard):.0f} N - it breaks"),
                ("soft hands", f"stops in {self.t_soft * 1000:g} ms: F = {self.force(self.t_soft):.1f} N - safe"),
                ("F = m·Δv / Δt", "longer stopping time, smaller force (seat belts, airbags)")]


class Gravitation(Exp):
    name, title = "gravitation", "Newton's law of gravitation"

    G = 6.674e-11

    def setup(self):
        self.m1 = _num(self.spec, "m1", 1000.0, 1, 1e30)
        self.m2 = _num(self.spec, "m2", 1000.0, 1, 1e30)
        self.r0 = _num(self.spec, "distance", 1.0, 0.1, 1e9)

    def r(self, t):
        return self.r0 * (1 + 0.5 * max(0.0, t - 1.0))                      # they move apart (2x, 3x ...)

    def F(self, t):
        return self.G * self.m1 * self.m2 / self.r(t) ** 2

    def length(self):
        return 5.0

    def size(self):
        return 1200.0, 300.0

    def draw(self, pen, t):
        d = min(500.0, 120 * self.r(t) / self.r0)
        for s, c in ((-1, BLUE), (1, RED)):
            pen.sphere(s * d, 120, 0, r=60, c=c)
            L = 120 * (self.F(t) / self.F(0.0))
            arrow(pen, (s * (d - 60), 120, -70), (s * (d - 60 - max(8, L)), 120, -70), ARROW_F, r=4)

    def values(self, t):
        k = self.r(t) / self.r0
        return [("masses", f"{self.m1:g} kg and {self.m2:g} kg"), ("distance", f"{self.r(t):.2f} m ({k:.1f}×)"),
                ("pull F = G·m₁·m₂ / r²", f"{self.F(t):.3g} N"), ("", "twice as far = a quarter of the pull")]

    def graph(self):
        return ("time (s)", "pull (×10⁻⁶ N)", lambda t: self.F(t) * 1e6, self.F(0.0) * 1.1e6, ["#e63946"])


class MassWeight(Exp):
    name, title = "mass_weight", "Mass and weight"

    PLACES = (("Earth", 9.81), ("Moon", 1.62), ("Mars", 3.71), ("Jupiter", 24.79))

    def setup(self):
        self.m = _num(self.spec, "mass", 10, 0.1, 1000)
        self.each = 2.0

    def now(self, t):
        return self.PLACES[min(3, int(t / self.each))]

    def length(self):
        return self.each * 4

    def size(self):
        return 600.0, 360.0

    def draw(self, pen, t):
        name, g = self.now(t)
        pen.box(0, 0, 0, w=220, h=40, d=160, c="#d7dadf")                  # a weighing scale
        squeeze = min(30.0, 30 * g / 24.79)
        pen.box(0, 40, 0, w=200, h=12 - squeeze * 0.2, d=140, c="#adb5bd")
        pen.box(0, 52 - squeeze * 0.2, 0, w=90, h=90, d=90, c="#6c757d")
        col = {"Earth": "#4f9be0", "Moon": "#bbbbbb", "Mars": "#c1440e", "Jupiter": "#d9a066"}[name]
        pen.sphere(260, 220, 60, r=50, c=col)

    def values(self, t):
        name, g = self.now(t)
        return [("place", name), ("mass", f"{self.m:g} kg (the same everywhere)"),
                ("weight W = m·g", f"{self.m * g:.1f} N (g = {g} m/s²)")]


class Archimedes(Exp):
    name, title = "archimedes", "Archimedes: the weight lost in water"

    def setup(self):
        self.m = _num(self.spec, "mass", 0.5, 0.05, 20)                     # kg
        self.rho = _num(self.spec, "density", 2600, 100, 20000)            # stone
        self.V = self.m / self.rho                                          # m³
        self.dip = 1.5

    def under(self, t):
        return min(1.0, max(0.0, (t - self.dip) / 1.5))

    def reading(self, t):
        return self.m * 9.81 - 1000 * self.V * self.under(t) * 9.81

    def length(self):
        return self.dip + 3.5

    def size(self):
        return 700.0, 520.0

    def draw(self, pen, t):
        u = self.under(t)
        pen.box(0, 0, 0, w=260, h=10, d=200, c="#7a5a3a")
        pen.box(0, 10, 0, w=180, h=160, d=140, c=(0.75, 0.88, 0.95, 0.3))
        rise = 1000 * self.V * u * 4e5                                      # the water level rises (exaggerated)
        pen.box(0, 10, 0, w=172, h=110 + rise, d=132, c=(0.25, 0.55, 0.9, 0.5))
        top = 470
        pen.box(0, top, 0, w=40, h=60, d=30, c="#d7dadf")                  # the spring balance
        stretch = 30 * self.reading(t) / (self.m * 9.81)
        pen.line([(0, top, 0), (0, top - 40 - stretch, 0)], c="#888888", w=3)
        sy = top - 60 - stretch - 120 * u
        pen.sphere(0, sy, 0, r=36, c="#8e8e8e")
        pen.box(150, 10, 0, w=60, h=40 * u + 2, d=60, c=(0.25, 0.55, 0.9, 0.7))   # the water pushed out

    def values(self, t):
        u = self.under(t)
        lost = 1000 * self.V * u * 9.81
        return [("in air", f"{self.m * 9.81:.2f} N"), ("balance now", f"{self.reading(t):.2f} N"),
                ("weight lost", f"{lost:.2f} N"), ("water pushed out", f"{self.V * u * 1e6:.0f} cm³ = {lost:.2f} N"),
                ("", "the upthrust equals the weight of the water pushed out")]


class WorkPower(Exp):
    name, title = "work_power", "Work and power"

    def setup(self):
        self.m = _num(self.spec, "mass", 20, 1, 500)
        self.h = _num(self.spec, "height", 2.0, 0.2, 20)
        self.t_fast = _num(self.spec, "fast", 2.0, 0.5, 60)
        self.t_slow = _num(self.spec, "slow", 6.0, 0.5, 120)

    def y(self, T, t):
        return self.h * min(1.0, max(0.0, t) / T)

    def length(self):
        return self.t_slow + 1.0

    def size(self):
        return 800.0, self.h * M * 0.6 + 200

    def draw(self, pen, t):
        k = M * 0.6
        for x, T, c in ((-180, self.t_fast, RED), (180, self.t_slow, BLUE)):
            pen.box(x, 0, 0, w=10, h=self.h * k + 40, d=10, c="#6b4528")
            pen.wheel(x, self.h * k + 40, 0, r=18, c="#8b5a2b", w=8, spokes=4, turn=-t * 3)
            pen.box(x, self.y(T, t) * k, 0, w=60, h=50, d=60, c=c)

    def values(self, t):
        W = self.m * 9.81 * self.h
        return [("work W = m·g·h", f"{W:.0f} J (the same for both)"), ("fast", f"{self.t_fast:g} s -> power {W / self.t_fast:.0f} W"),
                ("slow", f"{self.t_slow:g} s -> power {W / self.t_slow:.0f} W"), ("", "power = work / time")]


class EnergyChain(Exp):
    name, title = "energy_chain", "Energy changes form: dam -> turbine -> bulb"

    def setup(self):
        self.h = _num(self.spec, "height", 10.0, 1, 200)                   # m
        self.flow = _num(self.spec, "flow", 2.0, 0.1, 1000)                # kg of water per second
        self.eff = _num(self.spec, "efficiency", 0.8, 0.1, 1.0)

    def power(self):
        return self.flow * 9.81 * self.h * self.eff

    def length(self):
        return 6.0

    def size(self):
        return 1000.0, 420.0

    def draw(self, pen, t):
        pen.box(-300, 0, 0, w=120, h=320, d=200, c="#9a9a92")
        pen.box(-420, 0, 0, w=120, h=280, d=200, c=(0.25, 0.55, 0.9, 0.7))
        pts = [(-240, 280, 0), (-150, 200, 0), (-60, 90, 0)]
        pen.tube(pts, 14, c="#4a90c8", sides=8)
        pen.wheel(0, 90, 0, r=60, c="#d4a017", w=14, spokes=8, turn=-t * 5)
        pen.box(130, 60, 0, w=80, h=60, d=60, c="#555555")
        pen.line([(170, 90, 0), (330, 90, 0), (330, 200, 0)], c=RED, w=4)
        on = min(1.0, t / 1.5)
        pen.sphere(330, 230, 0, r=30, c="#fff6cc")
        pen.glow(330, 230, 0, 140 * on, "#fff2a0", 0.7 * on)

    def values(self, t):
        return [("water falls", f"{self.h:g} m, {self.flow:g} kg every second"),
                ("height energy", f"m·g·h = {self.flow * 9.81 * self.h:.0f} J every second"),
                ("electricity", f"{self.power():.0f} W ({self.eff * 100:.0f}% of it)"),
                ("", "height -> motion -> electricity -> light (and a little heat)")]


class Echo(Exp):
    name, title = "echo", "Echo: sound bounces back"

    def setup(self):
        self.d = _num(self.spec, "distance", 170.0, 17.0, 2000)            # m to the wall / cliff
        self.v = _num(self.spec, "speed", 343.0, 300, 1600)
        self.clap = 0.6

    def back(self):
        return 2 * self.d / self.v

    def length(self):
        return self.clap + self.back() + 1.5

    def size(self):
        return 1400.0, 400.0

    def draw(self, pen, t):
        wall = 1100
        pen.box(wall, 0, 0, w=60, h=380, d=300, c="#8e8e8e")
        pen.capsule(-100, 0, 0, r=30, h=170, c="#3a86ff")
        u = (t - self.clap) / self.back() if t >= self.clap else -1
        if 0 <= u <= 1:
            x = -60 + (wall - 30 + 60) * (2 * u if u < 0.5 else 2 - 2 * u)
            ring(pen, x, 150, 0, 40, c="#ffd166" if u < 0.5 else "#8ecae6", w=4, plane="xy", n=24)

    def values(self, t):
        heard = t >= self.clap + self.back()
        return [("wall", f"{self.d:g} m away"), ("sound", f"{self.v:g} m/s"),
                ("echo after", f"2 × {self.d:g} / {self.v:g} = {self.back():.2f} s" + (" - heard!" if heard else "")),
                ("", "distance = speed × time / 2 (to the wall and back)")]

    def sounds(self):
        return [(self.clap, "clap"), (self.clap + self.back(), "clap")]


class Sonar(Exp):
    name, title = "sonar", "Sonar: finding the depth of the sea"

    def setup(self):
        self.depth = _num(self.spec, "depth", 1500.0, 10, 11000)
        self.v = 1500.0
        self.ping = 0.6
        self.show = 4.0                                                     # the round trip shown in this many seconds

    def back(self):
        return 2 * self.depth / self.v

    def length(self):
        return self.ping + self.show + 1.5

    def size(self):
        return 900.0, 600.0

    def draw(self, pen, t):
        top = 520
        pen.box(0, top - 60, 0, w=900, h=4, d=400, c=(0.25, 0.55, 0.9, 0.6))
        pen.box(0, 0, 0, w=900, h=20, d=400, c="#c2b280")
        pen.box(0, top - 60, 0, w=220, h=50, d=70, c="#e63946")
        pen.box(0, top - 10, 0, w=90, h=40, d=50, c="#f4f1de")
        u = (t - self.ping) / self.show if t >= self.ping else -1
        if 0 <= u <= 1:
            y = top - 70 - (top - 90) * (2 * u if u < 0.5 else 2 - 2 * u)
            ring(pen, 0, y, 0, 40 + 30 * (u if u < 0.5 else 1 - u), c="#ffd166" if u < 0.5 else "#8ecae6", w=4,
                 plane="xz", n=24)

    def values(self, t):
        return [("sound in sea water", f"{self.v:g} m/s"), ("ping comes back after", f"{self.back():.2f} s"),
                ("depth = v × t / 2", f"{self.depth:g} m"), ("", "bats and dolphins find things the same way")]

    def sounds(self):
        return [(self.ping, "ding"), (self.ping + self.show, "ding")]


CLASS9 = (MotionGraphs, NewtonSecond, ActionReaction, Impulse, Gravitation, MassWeight, Archimedes, WorkPower,
          EnergyChain, Echo, Sonar)
CLASS9_ALIASES = {
    "distance_time": "motion_graphs", "speed_time": "motion_graphs", "uniform_motion": "motion_graphs",
    "f_ma": "newton_second", "second_law": "newton_second", "push_cart": "newton_second",
    "balloon_rocket": "action_reaction", "third_law": "action_reaction", "recoil": "action_reaction",
    "seat_belt": "impulse", "catch_egg": "impulse", "soft_hands": "impulse", "gravity_law": "gravitation",
    "universal_gravitation": "gravitation", "weight": "mass_weight", "mass_vs_weight": "mass_weight",
    "upthrust": "archimedes", "spring_balance": "archimedes", "work": "work_power", "power": "work_power",
    "dam": "energy_chain", "energy_change": "energy_chain", "turbine": "energy_chain", "echoes": "echo",
    "ultrasound": "sonar", "depth_sounding": "sonar",
}
CLASS9_KEYS = {
    "motion_graphs": '"speed": 1, "acceleration": 0.4',
    "newton_second": '"force": 10, "m1": 2, "m2": 8, "push": 2',
    "action_reaction": '"kind": "balloon" | "gun"',
    "impulse": '"mass": 0.06, "speed": 5, "stiff": 0.005, "soft": 0.2 (seconds to stop)',
    "gravitation": '"m1": 1000, "m2": 1000, "distance": 1',
    "mass_weight": '"mass": 10',
    "archimedes": '"mass": 0.5, "density": 2600',
    "work_power": '"mass": 20, "height": 2, "fast": 2, "slow": 6',
    "energy_chain": '"height": 10, "flow": 2, "efficiency": 0.8',
    "echo": '"distance": 170 (m to the wall)',
    "sonar": '"depth": 1500',
}
