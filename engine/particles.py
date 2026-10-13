"""Particle system: one emitter idea, many effects (Python Playground ch. 10, the fountain model).

Every particle leaves a point at a random angle inside a cone, flies in a parabola under gravity (with a little air
drag), lives for a while, changes colour and size, fades out - and glows if it is fire. Nothing is stored between
frames: particle k's whole life is worked out from (seed, k) and the time, so any frame can be drawn on its own
(parallel rendering keeps working) and the CPU cost is just the particles alive now.

Effects built on it ("effect": name in a story event):
    fireworks   rockets go up, burst into rings of coloured sparks that fall and fade (Diwali)
    anaar       fountain cracker: a cone of golden sparks from the ground
    phuljhadi   sparkler: tiny white-gold sparks round a point (held in the hand when "who" is given)
    chakri      ground spinner: sparks thrown round in a circle
    holi        clouds of coloured powder (gulal) thrown up, drifting and settling
    fountain    water jets falling back in drops
    dust_trail  dust kicked up behind a moving vehicle / runner ("follow": the vehicle id)
    sparks      a short shower of hot sparks (metal hit, fire)
    waterfall_mist  spray and mist at the foot of a waterfall
    petals      flower petals thrown and drifting down (weddings, welcomes)
"""
import math
import random

import cairo

from .util import TAU, clamp, stable_hash

G = 900.0                       # gravity, story units / s^2 (a person is ~300 tall)

GOLD = [(1.0, 0.86, 0.42), (1.0, 0.7, 0.25), (1.0, 0.95, 0.75)]
FIRE = [(1.0, 0.35, 0.2), (0.25, 0.85, 1.0), (0.45, 1.0, 0.35), (1.0, 0.85, 0.2), (0.95, 0.35, 0.95),
        (1.0, 0.55, 0.15), (1.0, 1.0, 1.0)]
GULAL = [(0.95, 0.18, 0.55), (0.98, 0.82, 0.1), (0.15, 0.7, 0.35), (0.2, 0.45, 0.95), (0.95, 0.45, 0.1),
         (0.6, 0.25, 0.85)]


def _wind():
    from .realworld import wind
    return wind()


def _rng(seed, k):
    return random.Random(seed * 1000003 + k * 7919)


def _pos(x0, y0, vx, vy, age, g=G, drag=0.0):
    """Where a particle is after age seconds (y up). drag slows it like air (exponential)."""
    if drag > 1e-6:
        e = (1.0 - math.exp(-drag * age)) / drag
        x = x0 + vx * e
        y = y0 + vy * e - g / drag * (age - e)
    else:
        x = x0 + vx * age
        y = y0 + vy * age - 0.5 * g * age * age
    return x, y


def _vel(vx, vy, age, g=G, drag=0.0):
    if drag > 1e-6:
        e = math.exp(-drag * age)
        return vx * e, vy * e - g / drag * (1.0 - e)
    return vx, vy - g * age


def _glow_dot(ctx, x, y, r, col, a, glow=True):
    if a <= 0.01 or r <= 0.05:
        return
    if glow:
        g = cairo.RadialGradient(x, y, 0, x, y, r * 3.2)
        g.add_color_stop_rgba(0, col[0], col[1], col[2], a * 0.55)
        g.add_color_stop_rgba(1, col[0], col[1], col[2], 0.0)
        ctx.set_source(g)
        ctx.arc(x, y, r * 3.2, 0, TAU)
        ctx.fill()
    ctx.set_source_rgba(min(1, col[0] * 0.4 + 0.6), min(1, col[1] * 0.4 + 0.6), min(1, col[2] * 0.4 + 0.6), a)
    ctx.arc(x, y, r, 0, TAU)
    ctx.fill()


def _streak(ctx, x0, y0, x1, y1, w, col, a):
    if a <= 0.01:
        return
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_width(w)
    ctx.set_source_rgba(col[0], col[1], col[2], a)
    ctx.move_to(x0, y0)
    ctx.line_to(x1, y1)
    ctx.stroke()


def emit(ctx, t, x, y, s=1.0, seed=1, rate=60.0, start=0.0, stop=None, life=(0.8, 1.4), angle=90.0, spread=30.0,
         speed=(300, 500), g=G, drag=0.0, size=(3.0, 1.0), colors=GOLD, glow=True, streak=0.0, fade_in=0.0,
         jitter=0.0, puff=False, origin=None):
    """Draw one emitter at time t. Particles are born at `rate` per second from `start` (to `stop`) at (x, y),
    angle (degrees, 90 = straight up) +- spread, speed range, life range. size = (birth, death) radius.
    streak > 0 draws motion streaks (sparks), puff = soft clouds (smoke, powder).
    origin(born_time) -> (x, y, angle or None): the emitter moves (dust behind a jeep) - each particle starts where
    the emitter was when it was born, then stays in the world."""
    if t < start:
        return
    last = t if stop is None else min(t, stop)
    lmax = life[1]
    k0 = max(0, int((t - lmax - start) * rate))
    k1 = int((last - start) * rate)
    if glow and not puff:
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_ADD)
    for k in range(k0, k1 + 1):
        born = start + k / rate
        age = t - born
        if age < 0:
            continue
        r = _rng(seed, k)
        lf = r.uniform(*life)
        if age > lf:
            continue
        ang0, ox, oy = angle, x, y
        if origin is not None:
            got = origin(born)
            if got is None:
                continue
            ox, oy = got[0], got[1]
            if len(got) > 2 and got[2] is not None:
                ang0 = got[2]
        a = math.radians(ang0 + r.uniform(-spread, spread))
        sp = r.uniform(*speed) * s
        vx, vy = math.cos(a) * sp, math.sin(a) * sp
        u = age / lf
        px, py = _pos(ox + r.uniform(-jitter, jitter) * s, oy, vx, vy, age, g * s, drag)
        if puff:                                           # smoke, dust, powder ride the scene wind
            px += _wind().speed(born) * 0.4 * age * s
        col = colors[r.randrange(len(colors))]
        alpha = (1.0 - u) ** 1.3 * (min(1.0, age / fade_in) if fade_in > 0 else 1.0)
        rad = (size[0] + (size[1] - size[0]) * u) * s
        if puff:
            ctx.set_source_rgba(col[0], col[1], col[2], alpha * 0.55)
            ctx.arc(px, py, rad, 0, TAU)
            ctx.fill()
        elif streak > 0:
            ux, uy = _vel(vx, vy, age, g * s, drag)
            L = streak * s / max(1.0, math.hypot(ux, uy)) * 1.0
            _streak(ctx, px, py, px - ux * L, py - uy * L, max(0.8, rad), col, alpha)
        else:
            _glow_dot(ctx, px, py, rad, col, alpha, glow)
    if glow and not puff:
        ctx.restore()


# ------------------------------------------------------------------ the effects
def fireworks(ctx, age, dur, x, y, s, seed, inten):
    """Several rockets: a rising spark trail, then a burst of 40-70 sparks (a ring that droops under gravity)."""
    n = max(1, int(round(3 * inten)))
    sky = y + 640 * s
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    for i in range(n):
        r = _rng(seed, 900 + i)
        t0 = i * max(0.35, dur / max(n, 1)) * 0.8 + r.uniform(0, 0.3)
        a = age - t0
        if a < 0:
            continue
        rise = r.uniform(0.9, 1.25)
        bx = x + r.uniform(-320, 320) * s
        by = sky + r.uniform(-60, 200) * s
        if a < rise:                                     # the rocket going up with a short trail
            u = a / rise
            e = 1 - (1 - u) ** 2
            px, py = x + (bx - x) * e, y + (by - y) * e
            for j in range(6):
                v = max(0.0, e - j * 0.025)
                qx, qy = x + (bx - x) * v, y + (by - y) * v
                _glow_dot(ctx, qx + r.uniform(-2, 2) * s, qy, (2.6 - j * 0.35) * s, GOLD[0], 0.9 - j * 0.14, j == 0)
            continue
        b = a - rise                                     # the burst
        if b > 2.4:
            continue
        cols = [FIRE[r.randrange(len(FIRE))], FIRE[r.randrange(len(FIRE))]]
        m = r.randint(40, 70)
        pw = r.uniform(520, 720) * s
        if b < 0.12:                                     # the flash
            g = cairo.RadialGradient(bx, by, 0, bx, by, 160 * s)
            g.add_color_stop_rgba(0, 1, 1, 0.9, 0.5 * (1 - b / 0.12))
            g.add_color_stop_rgba(1, 1, 1, 0.9, 0)
            ctx.set_source(g)
            ctx.arc(bx, by, 160 * s, 0, TAU)
            ctx.fill()
        for k in range(m):
            ang = TAU * k / m + r.uniform(-0.05, 0.05)
            sp = pw * r.uniform(0.85, 1.05)
            vx, vy = math.cos(ang) * sp, math.sin(ang) * sp
            px, py = _pos(bx, by, vx, vy, b, 300 * s, 1.6)
            qx, qy = _pos(bx, by, vx, vy, max(0.0, b - 0.09), 300 * s, 1.6)
            al = clamp(1.0 - b / 2.2, 0, 1) ** 1.2
            if b > 1.2 and (k * 7 + int(b * 20)) % 3 == 0:
                al *= 0.3                                # twinkle as they die
            col = cols[k % 2]
            _streak(ctx, qx, qy, px, py, 4.6 * s, col, al)
            _glow_dot(ctx, px, py, 3.4 * s, col, al, k % 2 == 0)
    ctx.restore()


def anaar(ctx, age, dur, x, y, s, seed, inten):
    on = clamp(age / 0.4, 0, 1) * clamp((dur - age) / 0.5 + 1.0, 0, 1)
    if on <= 0:
        return
    h = 0.85 + 0.15 * math.sin(age * 9)
    emit(ctx, age, x, y + 4 * s, s, seed, rate=120 * inten, stop=dur, life=(0.7, 1.3), angle=90, spread=16,
         speed=(480 * h, 720 * h), g=G, drag=0.4, size=(2.6, 0.8), colors=GOLD, streak=28)
    _glow_dot(ctx, x, y + 6 * s, 14 * s * on, (1.0, 0.8, 0.4), 0.8 * on)
    ctx.set_source_rgba(0.55, 0.2, 0.15, 1)              # the clay pot
    ctx.move_to(x - 16 * s, y)
    ctx.curve_to(x - 20 * s, y + 18 * s, x - 6 * s, y + 26 * s, x, y + 26 * s)
    ctx.curve_to(x + 6 * s, y + 26 * s, x + 20 * s, y + 18 * s, x + 16 * s, y)
    ctx.close_path()
    ctx.fill()


def phuljhadi(ctx, age, dur, x, y, s, seed, inten):
    if age > dur:
        return
    emit(ctx, age, x, y, s, seed, rate=160 * inten, stop=dur, life=(0.12, 0.35), angle=90, spread=180,
         speed=(160, 330), g=200, size=(1.8, 0.6), colors=[(1, 1, 0.9), (1, 0.85, 0.5)], streak=14)
    _glow_dot(ctx, x, y, 7 * s, (1, 0.95, 0.75), 0.95)


def chakri(ctx, age, dur, x, y, s, seed, inten):
    if age > dur:
        return
    spin = age * 18
    for j in range(3):
        a = spin + j * TAU / 3
        emit(ctx, age, x + math.cos(a) * 10 * s, y + 6 * s, s, seed + j, rate=50 * inten, stop=dur,
             life=(0.25, 0.5), angle=math.degrees(a + 1.57), spread=12, speed=(260, 380), g=300, size=(2.0, 0.7),
             colors=[(1, 0.7, 0.3), (0.5, 1.0, 0.5), (1, 1, 0.8)], streak=18)
    _glow_dot(ctx, x, y + 6 * s, 9 * s, (1, 0.9, 0.6), 0.9)


def holi(ctx, age, dur, x, y, s, seed, inten):
    """Throws of gulal: each throw is a burst of coloured puffs that spread, rise a little, drift and settle."""
    n = max(1, int(round(4 * inten)))
    for i in range(n):
        r = _rng(seed, 500 + i)
        t0 = i * max(0.3, dur / (n + 1)) + r.uniform(0, 0.25)
        a = age - t0
        if a < 0 or a > 3.2:
            continue
        col = GULAL[r.randrange(len(GULAL))]
        cx = x + r.uniform(-200, 200) * s
        cy = y + r.uniform(120, 230) * s
        for k in range(22):
            rk = _rng(seed + i, k)
            ang = rk.uniform(0, TAU)
            sp = rk.uniform(120, 380) * s
            vx, vy = math.cos(ang) * sp, math.sin(ang) * sp * 0.75 + 40 * s
            px, py = _pos(cx, cy, vx, vy, a, 60 * s, 2.2)
            px += 25 * s * math.sin(a * 1.3 + k)          # drifting in the air
            rad = (18 + 85 * (1 - math.exp(-a * 1.4))) * s * rk.uniform(0.6, 1.2)
            al = 0.34 * clamp(a / 0.08, 0, 1) * (1 - clamp((a - 1.4) / 1.8, 0, 1))
            c2 = tuple(min(1.0, v * rk.uniform(0.9, 1.1)) for v in col)
            ctx.set_source_rgba(*c2, al)
            ctx.arc(px, py, rad, 0, TAU)
            ctx.fill()


def fountain(ctx, age, dur, x, y, s, seed, inten):
    on = clamp(age / 0.3, 0, 1)
    emit(ctx, age, x, y, s, seed, rate=110 * inten, stop=dur, life=(0.9, 1.3), angle=90, spread=9,
         speed=(520, 600), g=G, size=(4.0, 3.0), colors=[(0.75, 0.9, 1.0), (0.9, 0.97, 1.0)], glow=False,
         fade_in=0.05)
    if on > 0:
        ctx.save()
        ctx.translate(x, y + 2)
        ctx.scale(1.0, 0.25)
        for k in range(3):
            u = ((age * 0.8 + k / 3.0) % 1.0)
            ctx.arc(0, 0, (30 + 120 * u) * s, 0, TAU)
            ctx.set_source_rgba(0.85, 0.95, 1.0, 0.5 * (1 - u) * on)
            ctx.set_line_width(4 * s)
            ctx.stroke()
        ctx.restore()


def dust_trail(ctx, age, dur, x, y, s, seed, inten, back=-1.0, speed=1.0, origin=None):
    """Puffs of dust left behind a moving thing. origin(born age) -> (x, y, angle) or None (not moving then)."""
    emit(ctx, age, x, y + 6 * s, s, seed, rate=26 * inten, stop=dur, life=(0.9, 1.6),
         angle=90 + 60 * (-back), spread=25, speed=(30, 90), g=-15, drag=1.2, size=(10.0, 42.0),
         colors=[(0.76, 0.66, 0.52), (0.7, 0.6, 0.47), (0.8, 0.72, 0.6)], glow=False, puff=True, jitter=25,
         origin=origin)


def sparks(ctx, age, dur, x, y, s, seed, inten):
    emit(ctx, age, x, y + 40 * s, s, seed, rate=90 * inten, stop=min(dur, 0.6), life=(0.3, 0.7), angle=90,
         spread=70, speed=(250, 520), g=G, size=(2.0, 0.6), colors=GOLD, streak=20)


def waterfall_mist(ctx, age, dur, x, y, s, seed, inten, width=200.0):
    emit(ctx, age, x, y + 10 * s, s, seed, rate=30 * inten, life=(1.0, 2.0), angle=90, spread=55,
         speed=(40, 120), g=-20, drag=1.0, size=(14.0, 60.0), colors=[(0.95, 0.97, 1.0)], glow=False, puff=True,
         jitter=width * 0.5)
    emit(ctx, age, x, y + 10 * s, s, seed + 7, rate=70 * inten, life=(0.4, 0.8), angle=90, spread=60,
         speed=(160, 330), g=G, size=(2.6, 1.6), colors=[(0.85, 0.95, 1.0)], glow=False, jitter=width * 0.45)


def petals(ctx, age, dur, x, y, s, seed, inten):
    cols = [(0.98, 0.55, 0.15), (0.95, 0.85, 0.2), (0.95, 0.3, 0.45), (0.98, 0.98, 0.95)]
    for k in range(int(40 * inten)):
        r = _rng(seed, k)
        t0 = r.uniform(0, max(0.2, dur * 0.4))
        a = age - t0
        if a < 0 or a > 3.5:
            continue
        ang = math.radians(90 + r.uniform(-40, 40))
        sp = r.uniform(220, 380) * s
        px, py = _pos(x + r.uniform(-30, 30) * s, y + 170 * s, math.cos(ang) * sp, math.sin(ang) * sp, a, 260 * s, 2.5)
        px += 20 * s * math.sin(a * 4 + k)
        if py < y:
            py = y
        ctx.save()
        ctx.translate(px, py)
        ctx.rotate(a * r.uniform(3, 7))
        ctx.scale(5 * s, 3 * s)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(*cols[k % len(cols)], 1 - clamp((a - 2.8) / 0.7, 0, 1))
        ctx.fill()



def _burst(ctx, age, x, y, s, seed, n, cols, speed=(120, 260), size=(4.0, 2.0), g=G, life=0.8, spread=70,
           puff=False, shape="dot"):
    """A one-off burst from the ground (landing, a dropped thing)."""
    for k in range(n):
        r = _rng(seed, k)
        lf = life * r.uniform(0.7, 1.1)
        if age > lf:
            continue
        a = math.radians(90 + r.uniform(-spread, spread))
        sp = r.uniform(*speed) * s
        px, py = _pos(x + r.uniform(-20, 20) * s, y + 4 * s, math.cos(a) * sp, math.sin(a) * sp, age, g * s,
                      2.0 if puff else 0.3)
        if py < y and not puff:
            py = y
        u = age / lf
        col = cols[k % len(cols)]
        rad = (size[0] + (size[1] - size[0]) * u) * s
        al = (1 - u) ** 1.2
        if shape == "leaf":
            ctx.save()
            ctx.translate(px, py)
            ctx.rotate(age * r.uniform(4, 9) + k)
            ctx.scale(rad * 1.6, rad * 0.7)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(*col, al)
            ctx.fill()
        else:
            ctx.set_source_rgba(*col, al * (0.55 if puff else 1.0))
            ctx.arc(px, py, rad, 0, TAU)
            ctx.fill()


def grass_burst(ctx, age, dur, x, y, s, seed, inten):
    _burst(ctx, age, x, y, s, seed, int(14 * inten), [(0.35, 0.62, 0.22), (0.5, 0.72, 0.28), (0.62, 0.55, 0.25)],
           speed=(90, 220), size=(4.0, 3.0), g=500, life=1.0, shape="leaf")


def sand_puff(ctx, age, dur, x, y, s, seed, inten):
    _burst(ctx, age, x, y, s, seed, int(12 * inten), [(0.93, 0.83, 0.6), (0.88, 0.77, 0.55)], speed=(40, 120),
           size=(10.0, 34.0), g=-10, life=1.2, spread=80, puff=True)
    _burst(ctx, age, x, y, s, seed + 3, int(16 * inten), [(0.86, 0.75, 0.5)], speed=(150, 280), size=(2.2, 1.6),
           life=0.6)


def snow_puff(ctx, age, dur, x, y, s, seed, inten):
    _burst(ctx, age, x, y, s, seed, int(14 * inten), [(0.97, 0.98, 1.0), (0.9, 0.94, 0.98)], speed=(50, 140),
           size=(10.0, 30.0), g=-5, life=1.2, spread=80, puff=True)


def mud_splat(ctx, age, dur, x, y, s, seed, inten):
    _burst(ctx, age, x, y, s, seed, int(14 * inten), [(0.38, 0.27, 0.16), (0.3, 0.22, 0.13)], speed=(120, 260),
           size=(4.5, 3.5), life=0.7)


def stone_chips(ctx, age, dur, x, y, s, seed, inten):
    _burst(ctx, age, x, y, s, seed, int(8 * inten), [(0.78, 0.76, 0.72), (0.6, 0.6, 0.58)], speed=(30, 80),
           size=(6.0, 16.0), g=-10, life=0.6, spread=80, puff=True)

EFFECTS = {"fireworks": fireworks, "firework": fireworks, "patakhe": fireworks, "rocket_burst": fireworks,
           "anaar": anaar, "fountain_cracker": anaar, "flowerpot": anaar,
           "phuljhadi": phuljhadi, "sparkler": phuljhadi, "fuljhadi": phuljhadi,
           "chakri": chakri, "spinner": chakri,
           "holi": holi, "gulal": holi, "colour_powder": holi, "color_powder": holi, "colors": holi,
           "fountain": fountain, "water_fountain": fountain,
           "dust_trail": dust_trail, "dust_cloud": dust_trail,
           "sparks": sparks, "waterfall_mist": waterfall_mist, "spray": waterfall_mist,
           "petals": petals, "flower_petals": petals, "phool": petals,
           "grass_burst": grass_burst, "sand_puff": sand_puff, "snow_puff": snow_puff, "mud_splat": mud_splat,
           "stone_chips": stone_chips}


def _boid_fx(name):
    def f(ctx, age, dur, x, y, s, seed, inten):
        from . import boids
        getattr(boids, name)(ctx, age, dur, x, y, s, seed, inten)
    return f


EFFECTS.update({"fish_school": _boid_fx("fish_school"), "fish": _boid_fx("fish_school"),
                "butterflies": _boid_fx("butterflies"), "titli": _boid_fx("butterflies")})
SOUND = {"fireworks": "firework", "anaar": "fizz", "phuljhadi": "fizz", "chakri": "fizz", "sparks": "crackle",
         "holi": "whoosh", "fountain": None, "petals": None}


def draw(ctx, eff, t, anchor, s=1.0, track=None):
    """Draw a particle effect (eff dict from the timeline). True when it was one of ours.
    track(time) -> (x, y, facing, speed) of the thing the effect follows (dust behind a jeep)."""
    fn = EFFECTS.get(eff["kind"])
    if fn is None:
        return False
    age = t - eff["start"]
    dur = eff.get("dur", 2.0)
    if age < 0 or age > dur + 3.0:
        return True
    seed = (stable_hash(eff["kind"]) % 9973) + int(eff["start"] * 1000)
    x, y = anchor
    if fn is dust_trail:
        origin = None
        if track is not None:
            st0 = eff["start"]

            def origin(born):
                got = track(st0 + born)
                if got is None or got[3] < 40.0:
                    return None                              # standing still: no dust
                bx, by, f, _sp = got
                return (bx - f * 60.0 * s, by, 90.0 + 55.0 * f)
        dust_trail(ctx, age, dur, x, y, s, seed, eff.get("intensity", 1.0), eff.get("_back", -1.0), 1.0, origin)
    else:
        fn(ctx, age, dur, x, y + float(eff.get("_lift", 0.0)), s, seed, eff.get("intensity", 1.0))
    return True
