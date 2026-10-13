"""🌩 Stick 3D weather and effects: the storm sky, rain, hail, lightning, wind in the trees, sparks, fire, smoke,
explosions and the camera shake that goes with them.

The story already says it (the same words as the other looks):
    {"weather": "storm_comes", "over": 10}       weather over time (engine/weatherline.py): clouds, rain, wind,
                                                  storm (lightning now and then); its sound follows by itself
    {"effect": "sparks" | "fire" | "smoke" | "explosion" | "lightning", "x": .., "z": .., "y": .., "who": ..,
     "duration": .., "intensity": ..}             (sounds: zap, boom, thunder)
    scene "stick_hail": {"start": 2, "end": 9}    hail: ice stones falling hard and bouncing (sound: hail)
    scene "stick_shake": [{"start": 3, "end": 4, "amount": 1}]   the camera shakes (lightning and explosions
                                                  shake it by themselves)

Everything is drawn flat over the 3D frame (streaks, puffs, glows) so it costs little: a storm scene renders
only a little slower than a calm one, and a scene without weather not at all.
"""
import math
import random

import cairo
import numpy as np

SWAY = ("crown", "palm_leaf", "palm_trunk", "leaf", "leaf_dark", "crop", "cabbage", "flower_o", "flower_y")


def levels(sc, bg, lt):
    """the weather now (0..1 levels) or None when the scene has none"""
    fx = getattr(sc, "weather_fx", None)
    base = str(getattr(bg, "weather", "") or "clear").lower()
    if not fx and base in ("", "clear", "sunny", "calm"):
        return None
    from . import weatherline
    return weatherline.state(sc, bg, lt)


class swayed:
    """trees and crops lean and rock in the wind while one frame is drawn (the meshes are put back after): the
    sway grows with height above the ground (a trunk is stiff at the root, the crown moves most)"""

    def __init__(self, world, wind, t, M):
        self.items = []
        if wind <= 1.3:
            return
        amp = min(1.6, (wind - 1.0) * 0.35) * 0.18 * M                 # metres of lean at 5 m height
        for m in world:
            if getattr(m, "name", "") in ("sea_face", "foam"):         # the surf rolls in: each crest swells and
                ph = (m.center[0] * 0.002 + m.center[2] * 0.004) % 6.28 # surges shoreward and draws back (a swell
                k = math.sin(t * 1.1 + ph)                             # of ~6 s, sped up a little for the eye)
                self.items.append((m, m.v.copy()))
                m.v = m.v + np.stack([np.zeros(len(m.v)), m.v[:, 1] * 0.25 * k,
                                      np.full(len(m.v), -1.8 * M * k)], axis=-1)
                continue
            if getattr(m, "name", "") in SWAY:
                ph = (m.center[0] * 0.013 + m.center[2] * 0.007) % 6.28
                k = amp * (0.6 + 0.4 * math.sin(t * 2.3 + ph)) + amp * 0.25 * math.sin(t * 7.0 + ph * 3)
                h = np.clip(m.v[:, 1] / (5.0 * M), 0.0, 1.6)
                self.items.append((m, m.v.copy()))
                m.v = m.v + np.stack([h * k, np.zeros_like(h), h * k * 0.35], axis=-1)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        for m, v in self.items:
            m.v = v
        return False


def shake_amount(sc, spec, lt):
    """how hard the camera shakes now: lightning close by, an explosion, or the story's own "stick_shake"""
    amt = 0.0
    for e in getattr(sc, "effects", None) or ():
        k = e.get("kind")
        u = lt - float(e.get("start", 0))
        if k == "explosion" and 0 <= u < 1.0:
            amt = max(amt, float(e.get("intensity", 1.0)) * (1.0 - u))
        elif k == "lightning" and 0 <= u < 0.4:
            amt = max(amt, 0.35 * (1.0 - u / 0.4))
    for s in spec.get("stick_shake") or ():
        if float(s.get("start", 0)) <= lt < float(s.get("end", 0)):
            amt = max(amt, float(s.get("amount", 0.6)))
    return amt


def shaken(cam, amount, frame, Cam, M):
    """the camera knocked about a little (a few centimetres at the lens, a little more at the look point)"""
    if amount <= 0.01:
        return cam
    r = random.Random(frame * 131)
    j = np.array([r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)]) * 0.06 * M * amount
    jl = np.array([r.uniform(-1, 1), r.uniform(-1, 1), 0.0]) * 0.12 * M * amount
    fov = 2 * math.degrees(math.atan((cam.H / 2) / cam.focal))
    return Cam(tuple(cam.pos + j), tuple(np.asarray(cam.look, float) + jl), fov=fov, W=cam.W, H=cam.H)


def storm_sky(ctx, W, H, lv):
    """clouds over the sun: the whole frame darker and greyer as the storm gathers"""
    a = 0.30 * lv.get("cloud", 0.0) * (0.4 + 0.6 * max(lv.get("rain", 0.0), lv.get("storm", 0.0))) + \
        0.12 * lv.get("storm", 0.0)
    if a > 0.01:
        ctx.set_source_rgba(0.20, 0.23, 0.30, min(0.55, a))
        ctx.paint()


def rain_clouds(ctx, W, S, hz, amount, t):
    """the monsoon sky: low banks of dark rain cloud rolling over (darkest overhead, paler and softer toward the
    horizon), and a band of mist where the hills meet the fields (rain in the air hides the far land)"""
    if hz <= 0:
        return
    for row, (y0, col, a, R) in enumerate(((0.05, (0.26, 0.29, 0.33), 0.92, 120), (0.30, (0.36, 0.39, 0.43), 0.85, 95),
                                           (0.55, (0.47, 0.50, 0.54), 0.75, 75), (0.78, (0.58, 0.61, 0.64), 0.6, 60))):
        r = random.Random(row * 17 + 5)
        drift = (t * (14 - row * 3) * S) % (W * 0.25)                    # the higher banks move faster
        y = hz * y0
        x = -W * 0.25 + drift
        while x < W * 1.25:
            rr = R * S * r.uniform(0.7, 1.3) * amount
            ctx.save()
            ctx.translate(x, y + r.uniform(-0.04, 0.04) * hz)
            ctx.scale(1.0, 0.55)
            ctx.new_sub_path()
            ctx.arc(0, 0, rr, 0, 2 * math.pi)
            ctx.restore()
            x += rr * r.uniform(0.9, 1.4)
        ctx.set_source_rgba(*col, a * amount)
        ctx.fill()
    g = cairo.LinearGradient(0, hz - 90 * S, 0, hz + 30 * S)            # the mist on the horizon
    g.add_color_stop_rgba(0, 0.70, 0.74, 0.77, 0.0)
    g.add_color_stop_rgba(0.7, 0.70, 0.74, 0.77, 0.55 * amount)
    g.add_color_stop_rgba(1, 0.70, 0.74, 0.77, 0.0)
    ctx.set_source(g)
    ctx.rectangle(0, hz - 90 * S, W, 120 * S)
    ctx.fill()


def rain(ctx, W, H, S, amount, wind, frame):
    """rain: thin falling streaks (each raindrop smeared by the shutter), slanted by the wind"""
    n = int(520 * amount * W / 1920)
    if n <= 0:
        return
    r = random.Random(frame * 7919 + 3)
    slant = 0.10 + 0.07 * max(0.0, wind - 1.0)
    ctx.set_line_width(1.6 * S)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(0.82, 0.86, 0.93, 0.42)
    for _ in range(n):
        x, y = r.uniform(-0.1 * W, 1.05 * W), r.uniform(-0.05 * H, H)
        L = r.uniform(26, 52) * S
        ctx.move_to(x, y)
        ctx.line_to(x + L * slant, y + L)
    ctx.stroke()


def hail(ctx, W, H, S, amount, frame, t):
    """hail: white ice stones falling fast and bouncing where they land (the lower part of the frame)"""
    n = int(260 * amount * W / 1920)
    r = random.Random(frame * 104729 + 11)
    ctx.set_source_rgba(0.97, 0.98, 1.0, 0.9)
    for _ in range(n):
        x, y = r.uniform(0, W), r.uniform(0, H)
        rr = r.uniform(2.0, 4.5) * S
        ctx.new_sub_path()
        ctx.arc(x, y, rr, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(0.95, 0.97, 1.0, 0.75)                         # the bounce: a little up again on the ground
    for _ in range(int(n * 0.4)):
        x = r.uniform(0, W)
        y = r.uniform(0.62, 0.98) * H - abs(math.sin(t * 9 + x)) * 10 * S
        ctx.new_sub_path()
        ctx.arc(x, y, r.uniform(1.5, 3.0) * S, 0, 2 * math.pi)
    ctx.fill()


def lightning(ctx, W, H, S, effects, lt):
    """lightning: a white flash over everything that dies in a quarter second, and the bolt (a jagged line from
    the clouds) for its first few frames"""
    for e in effects:
        if e.get("kind") != "lightning":
            continue
        u = lt - float(e.get("start", 0))
        if not 0 <= u < 0.6:
            continue
        flash = math.exp(-u / 0.09) + 0.5 * math.exp(-max(0.0, u - 0.18) / 0.07) * (u > 0.18)
        ctx.set_source_rgba(0.95, 0.96, 1.0, min(0.6, 0.6 * flash))
        ctx.paint()
        if u < 0.22:
            r = random.Random(int(float(e.get("start", 0)) * 1000))
            x = W * r.uniform(0.2, 0.8)
            y = 0.0
            pts = [(x, y)]
            while y < H * 0.45:
                y += r.uniform(20, 55) * S
                x += r.uniform(-40, 40) * S
                pts.append((x, y))
            for wdt, col in ((10 * S, (0.75, 0.80, 1.0, 0.35)), (3.2 * S, (1, 1, 1, 0.95))):
                ctx.move_to(*pts[0])
                for q in pts[1:]:
                    ctx.line_to(*q)
                ctx.set_source_rgba(*col)
                ctx.set_line_width(wdt)
                ctx.stroke()


def _soft(ctx, x, y, r, col, a):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, *col, a)
    g.add_color_stop_rgba(0.6, *col, a * 0.55)
    g.add_color_stop_rgba(1, *col, 0.0)
    ctx.set_source(g)
    ctx.new_sub_path()
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.fill()


def effects(ctx, cam, M, S, effs, lt, where):
    """sparks, fire, smoke, explosions at their places in the 3D world (where(e) -> world point or None)"""
    for e in effs:
        k = e.get("kind")
        if k not in ("sparks", "fire", "smoke", "explosion", "dust", "rocks"):
            continue
        t0, dur = float(e.get("start", 0)), float(e.get("dur", 2.0))
        u = lt - t0
        if not 0 <= u < dur + (2.5 if k in ("explosion", "smoke") else 0.8):
            continue
        p0 = where(e)
        if p0 is None:
            continue
        p0 = np.asarray(p0, float)
        dz = float(np.dot(p0 - cam.pos, cam.fwd))
        if dz < 0.3 * M:
            continue
        px = lambda p: cam.project(np.asarray(p, float)[None])[0]
        k_ = cam.focal / dz                                            # screen px per world unit there
        inten = float(e.get("intensity", 1.0))
        seed = int(t0 * 997) + 17
        if k == "rocks":                                               # a slope gives way: rocks fall (free fall,
            for i in range(int(16 * inten)):                           # 9.8 m/s2), hit the ground and roll on
                r = random.Random(seed + i)
                born = r.uniform(0, max(0.1, dur * 0.7))
                a = u - born
                if a < 0:
                    continue
                h0 = r.uniform(3.0, 7.0) * M
                off = np.array([r.uniform(-2.5, 2.5) * M, 0.0, r.uniform(-1.5, 1.5) * M])
                tf = math.sqrt(2 * h0 / (9.8 * M))                     # time to hit the ground
                if a < tf:
                    q = p0 + off + np.array([0.0, h0 - 4.9 * M * a * a, 0.0])
                else:
                    roll = min(1.2, a - tf)
                    q = p0 + off + np.array([r.uniform(0.5, 1.5) * M * roll, 0.25 * M * abs(math.sin(roll * 6)) *
                                             max(0.0, 1 - roll), 0.0])
                x, y = px(q)
                rr = r.uniform(0.18, 0.45) * M * k_
                pts = [(x + rr * math.cos(j * 1.05 + a * 4) * r.uniform(0.75, 1.1),
                        y + rr * math.sin(j * 1.05 + a * 4) * r.uniform(0.75, 1.1)) for j in range(6)]
                ctx.move_to(*pts[0])
                for q2 in pts[1:]:
                    ctx.line_to(*q2)
                ctx.close_path()
                ctx.set_source_rgb(0.46, 0.36, 0.28)
                ctx.fill_preserve()
                ctx.set_source_rgb(0.18, 0.14, 0.12)
                ctx.set_line_width(max(1.0, 1.6 * S))
                ctx.stroke()
            continue
        if k == "sparks":                                              # hot metal bits flying, falling, dying
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            for i in range(int(70 * inten)):
                r = random.Random(seed + i)
                born = r.uniform(0, max(0.05, dur))
                a = u - born
                if not 0 <= a < 0.55:
                    continue
                v = np.array([r.uniform(-1, 1), r.uniform(0.2, 1.4), r.uniform(-1, 1)]) * r.uniform(2.5, 5.5) * M
                q = p0 + v * a + np.array([0, -4.9 * M * a * a, 0])
                q2 = p0 + v * max(0.0, a - 0.03) + np.array([0, -4.9 * M * max(0.0, a - 0.03) ** 2, 0])
                x1, y1 = px(q)
                x2, y2 = px(q2)
                heat = 1.0 - a / 0.55
                ctx.set_source_rgba(1.0, 0.85 + 0.15 * heat, 0.35 + 0.6 * heat, 0.95 * heat)
                ctx.set_line_width(max(1.0, 2.2 * S))
                ctx.move_to(x2, y2)
                ctx.line_to(x1, y1)
                ctx.stroke()
            if u < dur:
                x, y = px(p0)
                _soft(ctx, x, y, 0.5 * M * k_, (1.0, 0.95, 0.7), 0.6)
        elif k == "fire":
            fade = min(1.0, u / 0.4, max(0.0, (dur + 0.8 - u) / 0.8))
            x, y = px(p0)
            sz = 0.5 * M * k_ * inten
            _soft(ctx, x, y - sz * 0.5, sz * 1.6, (1.0, 0.55, 0.15), 0.35 * fade)   # the glow on things around
            for i in range(7):
                r = random.Random(seed + i)
                ph = lt * r.uniform(5, 9) + i
                fx = x + (i - 3) * sz * 0.16 + math.sin(ph) * sz * 0.05
                h = sz * r.uniform(0.6, 1.1) * (0.8 + 0.2 * math.sin(ph * 1.7))
                for col, kk in (((1.0, 0.45, 0.10), 1.0), ((1.0, 0.85, 0.30), 0.55)):
                    w_ = sz * 0.22 * kk
                    ctx.move_to(fx - w_, y)
                    ctx.curve_to(fx - w_, y - h * 0.5 * kk, fx + math.sin(ph) * w_, y - h * 0.8 * kk,
                                 fx + math.sin(ph * 1.3) * w_ * 0.6, y - h * kk)
                    ctx.curve_to(fx + w_, y - h * 0.6 * kk, fx + w_, y - h * 0.3 * kk, fx + w_, y)
                    ctx.close_path()
                    ctx.set_source_rgba(*col, 0.9 * fade)
                    ctx.fill()
        if k in ("smoke", "fire", "explosion", "dust"):                # smoke rising and spreading as it cools
            col = (0.80, 0.72, 0.58) if k == "dust" else (0.32, 0.31, 0.33)
            for i in range(10 if k != "dust" else 6):
                r = random.Random(seed + 100 + i)
                born = r.uniform(0, max(0.1, dur))
                a = u - born
                life = 2.2 if k != "dust" else 1.2
                if not 0 <= a < life:
                    continue
                q = p0 + np.array([r.uniform(-0.4, 0.4) * M + a * 0.4 * M, (0.6 + a * 1.4) * M * (1 if k != "dust" else 0.4),
                                   r.uniform(-0.4, 0.4) * M])
                x, y = px(q)
                _soft(ctx, x, y, (0.35 + a * 0.7) * M * k_ * inten, col, 0.45 * (1 - a / life))
        if k == "explosion":                                           # the flash and the fireball
            x, y = px(p0 + np.array([0, 0.8 * M, 0]))
            if u < 0.12:
                ctx.set_source_rgba(1, 0.95, 0.85, 0.7 * (1 - u / 0.12))
                ctx.paint()
            if u < 0.9:
                rr = (0.5 + 3.0 * min(1.0, u / 0.35)) * M * k_ * inten
                _soft(ctx, x, y, rr, (1.0, 0.55, 0.12), 0.9 * (1 - u / 0.9))
                _soft(ctx, x, y, rr * 0.55, (1.0, 0.92, 0.55), 0.95 * (1 - u / 0.9))


def headlights(ctx, cam, cars, M, S, strength=1.0):
    """at night: each vehicle's headlights throw a cone of light on the road ahead (a soft yellow wedge), and
    the lamps themselves glow"""
    for cid, pos, head, moving, col, kind in cars:
        if kind in ("excavator", "bulldozer", "loader", "mixer", "dump_truck"):
            continue
        if kind in ("helicopter", "heli", "chopper", "apache", "gunship", "army_helicopter", "jet", "plane", "aircraft"):
            continue                                                   # (its searchlight: fx.searchlight)
        bike = kind in ("bike", "motorbike", "scooter")
        fw = np.array([math.cos(head), 0.0, math.sin(head)])
        sd = np.array([-fw[2], 0.0, fw[0]])
        lamp = pos + fw * (0.65 if bike else 2.35) * M + np.array([0.0, (0.95 if bike else 0.72) * M, 0.0])
        if float(np.dot(lamp - cam.pos, cam.fwd)) < 0.5 * M:
            continue
        far = pos + fw * 14 * M
        quad = [lamp + sd * 0.3 * M, lamp - sd * 0.3 * M, far - sd * 3.2 * M + np.array([0, 0.05 * M, 0]),
                far + sd * 3.2 * M + np.array([0, 0.05 * M, 0])]
        z = [float(np.dot(q - cam.pos, cam.fwd)) for q in quad]
        if min(z) < 0.3 * M:
            continue
        pts = cam.project(np.array(quad))
        lx, ly = cam.project(lamp[None])[0]
        fx_, fy_ = (pts[2] + pts[3]) / 2
        g = cairo.LinearGradient(lx, ly, fx_, fy_)
        g.add_color_stop_rgba(0, 1.0, 0.95, 0.70, 0.45 * strength)
        g.add_color_stop_rgba(1, 1.0, 0.95, 0.70, 0.0)
        ctx.move_to(*pts[0])
        for q in pts[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        ctx.set_source(g)
        ctx.fill()
        dz = float(np.dot(lamp - cam.pos, cam.fwd))
        _soft(ctx, lx, ly, max(6.0, 0.6 * M * cam.focal / dz), (1.0, 0.97, 0.80), 0.8 * strength)


def storm_wall(ctx, cam, W, S, hz, u, frame):
    """the storm front coming over the horizon (drawn into the sky, behind everything): a dark wall of cloud
    rising as it comes closer (u = 0..1), its top boiling, lightning flickering inside it"""
    if u <= 0:
        return
    top = hz - (0.05 + 0.85 * u) * hz
    r = random.Random(42)
    ctx.move_to(-20, hz + 4)
    xs = np.linspace(-20, W + 20, 28)
    for i, x in enumerate(xs):
        bump = r.uniform(0.0, 1.0) * 0.18 * hz * (0.5 + u) + 12 * S * math.sin(frame * 0.05 + i)
        ctx.line_to(x, top + bump)
    ctx.line_to(W + 20, hz + 4)
    ctx.close_path()
    g = cairo.LinearGradient(0, top, 0, hz)                           # (its top catches the last light: it reads
    g.add_color_stop_rgba(0, 0.36, 0.38, 0.46, 0.97)                   # even against a night sky)
    g.add_color_stop_rgba(0.35, 0.20, 0.21, 0.27, 0.98)
    g.add_color_stop_rgba(1, 0.08, 0.08, 0.11, 0.99)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_source_rgba(0.55, 0.58, 0.70, 0.6)
    ctx.set_line_width(3 * S)
    ctx.stroke()
    if (frame // 3) % 7 == 0:                                          # lightning inside the cloud
        x = W * ((frame * 37) % 100) / 100.0
        _soft(ctx, x, (top + hz) / 2, 0.35 * hz * (0.5 + u), (0.85, 0.88, 1.0), 0.7)


def blackout(ctx, W, H, lt, at):
    """the power goes: two flickers, then the lights are out (a dark veil)"""
    u = lt - at
    if u < -0.4:
        return
    if u < 0:
        a = 0.45 if int((u + 0.4) * 20) % 3 == 0 else 0.0
    else:
        a = 0.45
    if a > 0:
        ctx.set_source_rgba(0.0, 0.0, 0.03, a)
        ctx.paint()


_GRAIN = {}


def cinema(ctx, W, H, frame):
    """the film look: a fine moving grain (four noise frames made once and cycled) and the 2.39:1 widescreen frame
    (black bars top and bottom, as feature films are shot)"""
    key = (int(W), int(H))
    if key not in _GRAIN:
        rng = np.random.default_rng(7)
        frames = []
        for k in range(4):
            n = rng.integers(0, 255, size=(int(H) // 2, int(W) // 2), dtype=np.uint8)
            a = np.zeros((int(H) // 2, int(W) // 2, 4), np.uint8)
            a[..., 0] = a[..., 1] = a[..., 2] = n
            a[..., 3] = 14                                             # very faint
            a[..., :3] = (a[..., :3].astype(np.uint16) * 14 // 255).astype(np.uint8)   # premultiplied alpha
            surf = cairo.ImageSurface.create_for_data(memoryview(np.ascontiguousarray(a)), cairo.FORMAT_ARGB32,
                                                      int(W) // 2, int(H) // 2)
            frames.append((surf, a))
        _GRAIN[key] = frames
    surf, _a = _GRAIN[key][frame % 4]
    ctx.save()
    ctx.identity_matrix()
    ctx.scale(2.0, 2.0)
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint()
    ctx.restore()
    bar = max(0.0, (H - W / 2.39) / 2)
    ctx.set_source_rgb(0, 0, 0)
    ctx.rectangle(0, 0, W, bar)
    ctx.rectangle(0, H - bar, W, bar)
    ctx.fill()


def ripples(ctx, cam, puddles, lt, rain_amt, S, M):
    """rain on the puddles: each drop makes a ring that spreads and fades (about half a second)"""
    for i, (x, z, rx, rz) in enumerate(puddles):
        c = np.array([x, 1.0, z])
        d = float(np.dot(c - cam.pos, cam.fwd))
        if d < 0.5 * M or d > 45 * M:
            continue
        r = random.Random(i * 31 + int(lt * 2.0))
        for k in range(int(4 * rain_amt) + 1):
            ph = (lt * 2.0 + k * 0.37 + i * 0.11) % 1.0                  # where this ring is in its life
            px, pz = x + r.uniform(-0.6, 0.6) * rx, z + r.uniform(-0.6, 0.6) * rz
            rr = (0.04 + 0.22 * ph) * M
            pts = np.array([[px + math.cos(a) * rr, 1.5, pz + math.sin(a) * rr]
                            for a in np.linspace(0, 2 * math.pi, 13)])
            if np.any((pts - cam.pos) @ cam.fwd < 0.2 * M):
                continue
            q = cam.project(pts)
            ctx.move_to(*q[0])
            for p_ in q[1:]:
                ctx.line_to(*p_)
            ctx.set_source_rgba(0.88, 0.92, 0.96, 0.55 * (1 - ph))
            ctx.set_line_width(max(1.0, 1.4 * S))
            ctx.stroke()


def car_inside(ctx, cam, W, H, S, inside, lt, frame, rain_amt, M):
    """inside the car (drawn over the 3D view, which sees out through the glass): from the passenger seat the door
    and roof frame the driver, the steering wheel in front of him; through the windscreen the dashboard, the wheel,
    the pillars and the mirror - with rain drops on the glass and the wiper sweeping them away"""
    kind, cp, head = inside[:3]
    sx_, sy_ = inside[3] if len(inside) > 3 else (-0.3, 0.08)
    lift = np.array([0.0, (sy_ - 0.08) * M, 0.0])                       # (a pickup's seat is higher and further on)
    dark, dash = (0.10, 0.10, 0.12), (0.16, 0.16, 0.19)
    if kind == "driver":
        g = cairo.LinearGradient(0, H * 0.70, 0, H)                    # the door below the window
        g.add_color_stop_rgb(0, *dash)
        g.add_color_stop_rgb(1, *dark)
        ctx.move_to(0, H * 0.72)
        ctx.curve_to(W * 0.3, H * 0.70, W * 0.7, H * 0.69, W, H * 0.66)
        ctx.line_to(W, H)
        ctx.line_to(0, H)
        ctx.close_path()
        ctx.set_source(g)
        ctx.fill()
        ctx.rectangle(0, 0, W, H * 0.09)                                 # the roof lining
        ctx.set_source_rgb(0.30, 0.29, 0.28)
        ctx.fill()
        ctx.move_to(W * 0.93, 0)                                         # the windscreen pillar
        ctx.line_to(W, 0)
        ctx.line_to(W, H * 0.7)
        ctx.line_to(W * 0.97, H * 0.68)
        ctx.close_path()
        ctx.set_source_rgb(*dark)
        ctx.fill()
        fw = np.array([math.cos(head), 0.0, math.sin(head)])
        sd = np.array([-fw[2], 0.0, fw[0]])
        c = cp + fw * (sx_ + 0.5) * M - sd * 0.42 * M + np.array([0.0, 0.95 * M, 0.0]) + lift   # the wheel
        if float(np.dot(c - cam.pos, cam.fwd)) > 0.1 * M:
            x, y = cam.project(c[None])[0]
            r = 0.19 * M * cam.focal / float(np.dot(c - cam.pos, cam.fwd))
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(0.45, 1.0)
            ctx.arc(0, 0, r, 0, 2 * math.pi)
            ctx.restore()
            ctx.set_source_rgb(0.08, 0.08, 0.09)
            ctx.set_line_width(max(4.0, r * 0.18))
            ctx.stroke()
    elif kind == "shoulder":
        if rain_amt > 0.02:                                            # drops on the windscreen, the wipers sweeping
            wa = math.sin(lt * 2.4)
            r = random.Random(int(lt * 3) * 13 + 7)
            for i in range(int(110 * rain_amt)):
                x, y = r.uniform(0, W), r.uniform(H * 0.08, H * 0.62)
                rr = r.uniform(2.0, 6.0) * S
                ctx.new_sub_path()
                ctx.arc(x, y, rr, 0, 2 * math.pi)
                ctx.set_source_rgba(0.85, 0.90, 0.98, 0.3)
                ctx.fill()
            for px_ in (0.28, 0.62):
                ang = -math.pi / 2 - 0.2 + wa * 1.0
                ctx.move_to(W * px_, H * 0.66)
                ctx.line_to(W * px_ + math.cos(ang) * W * 0.32, H * 0.66 + math.sin(ang) * W * 0.32)
                ctx.set_source_rgb(0.05, 0.05, 0.06)
                ctx.set_line_width(7 * S)
                ctx.stroke()
        ctx.rectangle(0, 0, W, H * 0.09)                                 # the roof lining and the mirror
        ctx.set_source_rgb(0.24, 0.23, 0.22)
        ctx.fill()
        _rr(ctx, W * 0.44, H * 0.08, W * 0.17, H * 0.07, 10 * S, (0.10, 0.10, 0.12))
        _rr(ctx, W * 0.45, H * 0.09, W * 0.15, H * 0.05, 8 * S, (0.42, 0.50, 0.56))
        for pts in (((0, 0), (W * 0.07, 0), (W * 0.02, H * 0.64), (0, H * 0.66)),
                    ((W * 0.93, 0), (W, 0), (W, H * 0.66), (W * 0.98, H * 0.64))):   # the windscreen pillars
            ctx.move_to(*pts[0])
            for q in pts[1:]:
                ctx.line_to(*q)
            ctx.close_path()
            ctx.set_source_rgb(*dark)
            ctx.fill()
        ctx.move_to(0, H * 0.70)                                         # the dashboard
        ctx.curve_to(W * 0.3, H * 0.64, W * 0.7, H * 0.64, W, H * 0.68)
        ctx.line_to(W, H)
        ctx.line_to(0, H)
        ctx.close_path()
        ctx.set_source_rgb(*dash)
        ctx.fill()
        for vx in (0.38, 0.80):                                          # the air vents and the radio between them
            _rr(ctx, W * vx, H * 0.78, W * 0.09, H * 0.08, 6 * S, (0.08, 0.08, 0.09))
            for k_ in range(4):
                ctx.rectangle(W * (vx + 0.008), H * (0.79 + 0.018 * k_), W * 0.074, H * 0.006)
            ctx.set_source_rgb(0.20, 0.20, 0.22)
            ctx.fill()
        _rr(ctx, W * 0.52, H * 0.78, W * 0.22, H * 0.10, 6 * S, (0.10, 0.10, 0.11))
        _rr(ctx, W * 0.56, H * 0.80, W * 0.12, H * 0.04, 4 * S, (0.16, 0.30, 0.34))
        ctx.move_to(0, H * 0.30)                                         # the driver's seat back at the left edge
        ctx.curve_to(W * 0.08, H * 0.28, W * 0.12, H * 0.40, W * 0.11, H)
        ctx.line_to(0, H)
        ctx.close_path()
        ctx.set_source_rgb(0.12, 0.12, 0.13)
        ctx.fill()
        nav = inside[5] if len(inside) > 5 else {}
        fw = np.array([math.cos(head), 0.0, math.sin(head)])
        sd = np.array([-fw[2], 0.0, fw[0]])
        up = np.array([0.0, 1.0, 0.0])
        seat = cp + fw * sx_ * M - sd * 0.42 * M + lift
        ph3 = seat + fw * 0.78 * M + sd * 0.5 * M + up * 1.2 * M         # the phone on its mount, in the car (so the
        dd = float(np.dot(ph3 - cam.pos, cam.fwd))                       # lens sizes it: far things are smaller)
        if dd > 0.1 * M:
            cx, cy = cam.project(ph3[None])[0]
            pw = 0.16 * M * cam.focal / dd                              # (a real phone: 16 cm across)
            ph = pw * 500 / 900
            px, py = cx - pw / 2, cy - ph / 2
            _rr(ctx, cx - pw * 0.04, py + ph, pw * 0.08, pw * 0.25, 4 * S, (0.08, 0.08, 0.09))
            _rr(ctx, px - pw * 0.025, py - pw * 0.025, pw * 1.05, ph + pw * 0.05, pw * 0.05, (0.06, 0.06, 0.07))
            from . import stick3d_screens as scr
            u = max(0.0, min(1.0, lt / max(0.1, float(nav.get("arrive", 3.0)))))
            scr.nav_phone(ctx, px, py, pw, ph, u, str(nav.get("to", "Weather Station 133")))
        c = seat + fw * 0.5 * M + up * 0.95 * M                         # the wheel
        dd = float(np.dot(c - cam.pos, cam.fwd))
        if dd > 0.1 * M:
            x, y = cam.project(c[None])[0]
            rr = 0.19 * M * cam.focal / dd
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(1.0, 0.72)
            ctx.arc(0, 0, rr, 0, 2 * math.pi)
            ctx.restore()
            ctx.set_source_rgb(0.06, 0.06, 0.07)
            ctx.set_line_width(max(6.0, rr * 0.16))
            ctx.stroke()
    elif kind == "profile":
        fw = np.array([math.cos(head), 0.0, math.sin(head)])
        sd = np.array([-fw[2], 0.0, fw[0]])
        up = np.array([0.0, 1.0, 0.0])
        seat = cp + fw * sx_ * M - sd * 0.42 * M + lift
        a = seat + up * 1.0 * M + fw * 1.0 * M                          # which way is the front on screen
        fr = 1.0 if cam.project(a[None])[0][0] > W / 2 else -1.0
        X = (lambda u: W * u) if fr > 0 else (lambda u: W * (1 - u))
        b = seat + up * 0.8 * M + fw * 0.2 * M                          # where he sits (no rain on him: it is outside)
        bd = max(0.2 * M, float(np.dot(b - cam.pos, cam.fwd)))
        bx, by = cam.project(b[None])[0]
        rx_, ry_ = 0.55 * M * cam.focal / bd, 0.75 * M * cam.focal / bd
        if rain_amt > 0.02:                                            # the rain out of the window, slanted by the
            r = random.Random(frame * 7 + 3)                            # car's speed, and drops on the glass
            for i in range(int(160 * rain_amt)):
                x, y = r.uniform(0, W), r.uniform(H * 0.10, H * 0.64)
                if ((x - bx) / rx_) ** 2 + ((y - by) / ry_) ** 2 < 1.0:
                    continue
                ln = r.uniform(25, 60) * S
                ctx.move_to(x, y)
                ctx.line_to(x - fr * ln * 0.45, y + ln)
                ctx.set_source_rgba(0.85, 0.90, 0.98, 0.30)
                ctx.set_line_width(1.6 * S)
                ctx.stroke()
            r = random.Random(int(lt * 6) * 17 + 3)
            for i in range(int(50 * rain_amt)):
                x, y = r.uniform(0, W), r.uniform(H * 0.12, H * 0.64)
                if ((x - bx) / rx_) ** 2 + ((y - by) / ry_) ** 2 < 1.0:
                    continue
                ln = r.uniform(12, 40) * S
                ctx.move_to(x, y)
                ctx.line_to(x - fr * ln, y + ln * 0.18)
                ctx.set_source_rgba(0.85, 0.90, 0.98, 0.35)
                ctx.set_line_width(2.2 * S)
                ctx.stroke()
        g = cairo.LinearGradient(0, H * 0.64, 0, H)                    # the far door below the window
        g.add_color_stop_rgb(0, 0.22, 0.22, 0.25)
        g.add_color_stop_rgb(1, *dark)
        ctx.move_to(0, H * 0.66)
        ctx.line_to(W, H * 0.64)
        ctx.line_to(W, H)
        ctx.line_to(0, H)
        ctx.close_path()
        ctx.set_source(g)
        ctx.fill()
        ctx.move_to(0, H * 0.66)                                         # the window sill, catching the light
        ctx.line_to(W, H * 0.64)
        ctx.set_source_rgb(0.38, 0.38, 0.42)
        ctx.set_line_width(6 * S)
        ctx.stroke()
        ctx.rectangle(0, 0, W, H * 0.11)                                 # the roof lining
        ctx.set_source_rgb(0.30, 0.29, 0.28)
        ctx.fill()
        ctx.move_to(X(0.0), 0)                                           # the B pillar behind his seat
        ctx.line_to(X(0.09), 0)
        ctx.line_to(X(0.07), H)
        ctx.line_to(X(0.0), H)
        ctx.close_path()
        ctx.set_source_rgb(*dark)
        ctx.fill()
        ctx.move_to(X(0.84), 0)                                          # the A pillar, sloping with the windscreen
        ctx.line_to(X(1.0), 0)
        ctx.line_to(X(1.0), H * 0.62)
        ctx.close_path()
        ctx.fill()
        ctx.move_to(X(0.80), H)                                          # the dashboard reaching in at the front
        ctx.curve_to(X(0.82), H * 0.72, X(0.92), H * 0.62, X(1.0), H * 0.60)
        ctx.line_to(X(1.0), H)
        ctx.close_path()
        ctx.set_source_rgb(*dash)
        ctx.fill()
        c = seat + fw * 0.5 * M + up * 0.95 * M                         # the steering wheel, seen edge-on
        dd = float(np.dot(c - cam.pos, cam.fwd))
        if dd > 0.1 * M:
            x, y = cam.project(c[None])[0]
            r = 0.19 * M * cam.focal / dd
            ctx.save()
            ctx.translate(x, y)
            ctx.rotate(-fr * 0.35)
            ctx.scale(0.28, 1.0)
            ctx.arc(0, 0, r, 0, 2 * math.pi)
            ctx.restore()
            ctx.set_source_rgb(0.07, 0.07, 0.08)
            ctx.set_line_width(max(5.0, r * 0.16))
            ctx.stroke()
            ctx.move_to(x, y)                                            # its column into the dashboard
            ctx.line_to(x + fr * r * 0.9, y + r * 0.5)
            ctx.set_line_width(max(6.0, r * 0.2))
            ctx.stroke()
    else:
        if rain_amt > 0.02:                                            # drops on the glass; the wiper clears a fan
            wa = math.sin(lt * 2.4)                                    # the wiper's angle, -1..1 (one sweep / 1.3 s)
            r = random.Random(int(lt * 3) * 13 + 1)
            for i in range(int(90 * rain_amt)):
                x, y = r.uniform(0, W), r.uniform(0, H * 0.72)
                ang = math.atan2(y - H * 0.95, x - W * 0.42)
                ang_w = -math.pi / 2 + wa * 1.1
                if abs(ang - ang_w) < 0.5 and math.hypot(x - W * 0.42, y - H * 0.95) < W * 0.62:
                    continue                                           # (just wiped)
                rr = r.uniform(2.0, 6.0) * S
                ctx.new_sub_path()
                ctx.arc(x, y, rr, 0, 2 * math.pi)
                ctx.set_source_rgba(0.85, 0.90, 0.98, 0.35)
                ctx.fill_preserve()
                ctx.set_source_rgba(1, 1, 1, 0.5)
                ctx.set_line_width(1.0)
                ctx.stroke()
            ang_w = -math.pi / 2 + wa * 1.1
            ctx.move_to(W * 0.42, H * 0.95)
            ctx.line_to(W * 0.42 + math.cos(ang_w) * W * 0.6, H * 0.95 + math.sin(ang_w) * W * 0.6)
            ctx.set_source_rgb(0.06, 0.06, 0.07)
            ctx.set_line_width(7 * S)
            ctx.stroke()
        for sx in (1, -1):                                             # the pillars
            x0 = 0 if sx > 0 else W
            ctx.move_to(x0, 0)
            ctx.line_to(x0 + sx * W * 0.13, 0)
            ctx.line_to(x0 + sx * W * 0.03, H * 0.75)
            ctx.line_to(x0, H * 0.75)
            ctx.close_path()
            ctx.set_source_rgb(*dark)
            ctx.fill()
        ctx.rectangle(0, 0, W, H * 0.06)
        ctx.set_source_rgb(0.28, 0.27, 0.26)
        ctx.fill()
        _rr(ctx, W * 0.42, H * 0.07, W * 0.16, H * 0.07, 10 * S, (0.12, 0.12, 0.14))   # the mirror
        _rr(ctx, W * 0.43, H * 0.08, W * 0.14, H * 0.05, 8 * S, (0.45, 0.55, 0.62))
        ctx.move_to(0, H * 0.78)                                       # the dashboard
        ctx.curve_to(W * 0.3, H * 0.70, W * 0.7, H * 0.70, W, H * 0.76)
        ctx.line_to(W, H)
        ctx.line_to(0, H)
        ctx.close_path()
        ctx.set_source_rgb(*dash)
        ctx.fill()
        cx, cy, rr = W * 0.66, H * 0.98, H * 0.30                      # the steering wheel (right-hand drive)
        ctx.new_sub_path()
        ctx.arc(cx, cy, rr, math.pi, 2 * math.pi)
        ctx.set_source_rgb(0.07, 0.07, 0.08)
        ctx.set_line_width(26 * S)
        ctx.stroke()
        ctx.move_to(cx - rr, cy)
        ctx.line_to(cx + rr, cy)
        ctx.set_line_width(18 * S)
        ctx.stroke()
        _rr(ctx, W * 0.30, H * 0.80, W * 0.12, H * 0.06, 6 * S, (0.08, 0.09, 0.10))    # the radio, its display
        ctx.rectangle(W * 0.31, H * 0.815, W * 0.10 * (0.6 + 0.4 * abs(math.sin(lt * 1.7))), H * 0.03)
        ctx.set_source_rgba(0.35, 0.85, 0.95, 0.9)
        ctx.fill()


def _rr(ctx, x, y, w, h, r, col):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()
    ctx.set_source_rgb(*col)
    ctx.fill()


def broadcast(ctx, W, H, spec, t, frame):
    """a TV news camera's picture: the red LIVE badge, the channel's corner logo, the reporter's name strap and the
    ticker, laid over the 3D shot (inside the 2.39 frame so the film bars don't cover it). spec: "channel", "name",
    "role", "place", "ticker", "rec" (the camera's red dot + time code instead of LIVE)"""
    S = H / 1080.0
    bar = max(0.0, (H - W / 2.39) / 2)
    top, bot = bar + 26 * S, H - bar - 26 * S
    ctx.save()
    ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)

    def text(s, x, y, size, col):
        ctx.set_font_size(size)
        ctx.move_to(x, y)
        ctx.set_source_rgb(*col)
        ctx.show_text(s)

    def width(s, size):
        ctx.set_font_size(size)
        return ctx.text_extents(s).x_advance

    x0 = 40 * S                                                        # LIVE (blinks a little, as on air)
    ctx.rectangle(x0, top, 120 * S, 46 * S)
    ctx.set_source_rgb(0.86, 0.12, 0.14)
    ctx.fill()
    if (frame // 15) % 4 != 3:
        ctx.arc(x0 + 22 * S, top + 23 * S, 8 * S, 0, 2 * math.pi)
        ctx.set_source_rgb(1, 1, 1)
        ctx.fill()
    text("LIVE", x0 + 38 * S, top + 34 * S, 28 * S, (1, 1, 1))
    ch = str(spec.get("channel", "WNN 24"))                            # the channel's logo, see-through
    ctx.set_font_size(34 * S)
    cw = width(ch, 34 * S)
    ctx.rectangle(W - cw - 70 * S, top, cw + 30 * S, 46 * S)
    ctx.set_source_rgba(0, 0, 0, 0.35)
    ctx.fill()
    text(ch, W - cw - 55 * S, top + 35 * S, 34 * S, (0.95, 0.95, 0.95))
    name, role = str(spec.get("name", "")), str(spec.get("role", ""))
    if name:                                                           # the name strap slides in after half a second
        u = min(1.0, max(0.0, (t - 0.4) / 0.35))
        u = 1 - (1 - u) ** 3
        sw = max(width(name, 40 * S), width(role, 26 * S)) + 60 * S
        sx = 40 * S - (1 - u) * (sw + 60 * S)
        sy = bot - 150 * S
        ctx.rectangle(sx, sy, sw, 62 * S)
        ctx.set_source_rgb(0.97, 0.97, 0.96)
        ctx.fill()
        ctx.rectangle(sx, sy, 10 * S, 62 * S + 42 * S)
        ctx.set_source_rgb(0.86, 0.12, 0.14)
        ctx.fill()
        text(name, sx + 30 * S, sy + 45 * S, 40 * S, (0.08, 0.08, 0.10))
        ctx.rectangle(sx + 10 * S, sy + 62 * S, sw - 10 * S, 42 * S)
        ctx.set_source_rgb(0.10, 0.16, 0.32)
        ctx.fill()
        text(role, sx + 30 * S, sy + 93 * S, 26 * S, (0.92, 0.94, 1.0))
    tk = str(spec.get("ticker", ""))
    if tk:                                                             # the ticker runs right to left
        ctx.rectangle(0, bot - 38 * S, W, 38 * S)
        ctx.set_source_rgba(0.05, 0.06, 0.10, 0.85)
        ctx.fill()
        place = str(spec.get("place", ""))
        tw = width(tk + "   ·   ", 24 * S)
        off = (t * 160 * S) % tw
        ctx.save()
        ctx.rectangle(0, bot - 38 * S, W, 38 * S)
        ctx.clip()
        for k in range(int(W / tw) + 2):
            text(tk + "   ·   ", W - off - (int(W / tw) + 1 - k) * tw + tw, bot - 11 * S, 24 * S, (0.95, 0.85, 0.3))
        ctx.restore()
        if place:
            pw = width(place, 24 * S) + 40 * S
            ctx.rectangle(0, bot - 38 * S, pw, 38 * S)
            ctx.set_source_rgb(0.86, 0.12, 0.14)
            ctx.fill()
            text(place, 20 * S, bot - 11 * S, 24 * S, (1, 1, 1))
    ctx.restore()


def hurricane_sky(ctx, W, S, hz, spec, t):
    """a hurricane's cloud spiral filling the sky, seen from the coast at an angle (squashed: we look at the
    disc from the side): bands of cloud wound in a log spiral round the clear eye, turning anticlockwise (the
    northern hemisphere: the Coriolis force turns the inflow to the right, so the storm spins left). spec: "eye"
    [x, y] as parts of the width / the sky's height, "size" (part of the width), "glow" (a gold break on the
    horizon, after the storm)"""
    if hz <= 0:
        return
    ex, ey = spec.get("eye", (0.42, 0.42))
    cx, cy = W * float(ex), hz * float(ey)
    R = W * float(spec.get("size", 0.75))
    sq = float(spec.get("squash", 0.42))
    rot = -t * float(spec.get("spin", 0.05))
    if spec.get("glow"):                                               # the evening light under the storm's edge
        g = cairo.LinearGradient(0, hz * 0.55, 0, hz)
        g.add_color_stop_rgba(0, 0.95, 0.72, 0.42, 0.0)
        g.add_color_stop_rgba(1, 0.98, 0.78, 0.48, 0.75)
        ctx.set_source(g)
        ctx.rectangle(0, hz * 0.55, W * 0.45, hz * 0.45)
        ctx.fill()
    ctx.save()
    ctx.rectangle(0, 0, W, hz + 2)
    ctx.clip()
    rng = random.Random(77)
    for layer, (col, a, kr) in enumerate((((0.30, 0.32, 0.36), 0.95, 1.0), ((0.52, 0.55, 0.58), 0.85, 0.8),
                                          ((0.80, 0.82, 0.84), 0.75, 0.55))):
        for arm in range(4):
            a0 = arm * math.pi / 2 + rot + layer * 0.25
            for i in range(70):
                u = i / 69.0
                ang = a0 + u * 4.2                                     # a log spiral: r grows as e^(b*angle)
                rr = R * (0.06 + 0.94 * u ** 1.25)
                px = cx + math.cos(ang) * rr
                py = cy + math.sin(ang) * rr * sq
                pr = (14 + 70 * u) * S * kr * rng.uniform(0.8, 1.25)
                ctx.save()
                ctx.translate(px, py)
                ctx.scale(1.0, 0.6)
                ctx.new_sub_path()
                ctx.arc(0, 0, pr, 0, 2 * math.pi)
                ctx.restore()
            ctx.set_source_rgba(*col, a * (0.85 if layer else 1.0))
            ctx.fill()
    for k in range(5):                                                 # lightning inside the cloud bands: a
        ph = (t * 0.9 + k * 0.371) % 1.0                               # flash lights a patch of cloud from inside
        if ph < 0.07:                                                  # (two quick flickers, as real strokes do)
            fl = 1.0 if ph < 0.025 or 0.045 < ph < 0.06 else 0.35
            r_ = random.Random(k * 13 + int(t * 0.9 + k * 0.371))
            ang = r_.uniform(0, 2 * math.pi)
            rr = R * r_.uniform(0.15, 0.7)
            lx, ly = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr * sq
            gl = cairo.RadialGradient(lx, ly, 0, lx, ly, 220 * S)
            gl.add_color_stop_rgba(0, 0.92, 0.94, 1.0, 0.75 * fl)
            gl.add_color_stop_rgba(1, 0.70, 0.75, 0.95, 0.0)
            ctx.set_source(gl)
            ctx.paint()
    g = cairo.RadialGradient(cx, cy, 0, cx, cy, 40 * S)                # the eye: a bright hole straight up
    g.add_color_stop_rgba(0, 0.92, 0.94, 0.96, 0.95)
    g.add_color_stop_rgba(1, 0.70, 0.74, 0.78, 0.0)
    ctx.set_source(g)
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(1.0, sq)
    ctx.arc(0, 0, 40 * S / sq * 0.5, 0, 2 * math.pi)
    ctx.restore()
    ctx.fill()
    ctx.restore()


def debris(ctx, W, H, S, amount, t, wind=1.0):
    """things flying in the hurricane wind: planks, roof tin, palm fronds and leaves, across the frame down-wind
    (left to right), tumbling; the near ones big and blurred-fast, the far ones small (parallax)"""
    if amount <= 0:
        return
    n = int(70 * amount)
    for k in range(n):
        r = random.Random(k * 7919 + 3)
        depth = r.uniform(0.25, 1.0)
        sp = (900 + 1500 * depth) * S * wind
        x = (r.uniform(0, W * 1.4) + t * sp) % (W * 1.4) - W * 0.2
        y = r.uniform(-0.1, 0.9) * H + math.sin(t * 2 + k) * 40 * S + (x / W) * 120 * S * r.uniform(-1, 1)
        ang = t * r.uniform(4, 12) * r.choice((-1, 1)) + k
        kind = r.random()
        sz = (10 + 46 * depth ** 2) * S
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(ang)
        if kind < 0.3:                                                 # a plank
            ctx.rectangle(-sz * 1.4, -sz * 0.16, sz * 2.8, sz * 0.32)
            ctx.set_source_rgb(0.56, 0.42, 0.28)
        elif kind < 0.45:                                              # a piece of roof tin, bent
            ctx.move_to(-sz, -sz * 0.6)
            ctx.line_to(sz, -sz * 0.4)
            ctx.line_to(sz * 0.8, sz * 0.6)
            ctx.line_to(-sz * 0.9, sz * 0.5)
            ctx.close_path()
            ctx.set_source_rgb(0.62, 0.66, 0.70)
        else:                                                          # leaves and bits of frond
            ctx.scale(1.0, 0.45)
            ctx.arc(0, 0, sz * 0.45, 0, 2 * math.pi)
            ctx.set_source_rgb(*r.choice(((0.30, 0.48, 0.22), (0.42, 0.55, 0.25), (0.36, 0.40, 0.20))))
        ctx.fill_preserve()
        ctx.set_source_rgba(0.12, 0.11, 0.12, 0.8)
        ctx.set_line_width(1.6 * S)
        ctx.stroke()
        ctx.restore()


def camera_falls(ctx, W, H, S, u, frame):
    """the news camera blown over: the picture tips and drops (it swings about the tripod's foot, faster and
    faster: a falling body), then the feed breaks into static. u = seconds since it went"""
    if u <= 0:
        return
    src = ctx.get_target()
    snap = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W), int(H))
    c2 = cairo.Context(snap)
    c2.set_source_surface(src, 0, 0)
    c2.paint()
    k = min(1.0, u / 0.7) ** 2
    ctx.save()
    ctx.set_source_rgb(0.05, 0.05, 0.06)
    ctx.paint()
    ctx.translate(W * 0.5, H * (0.5 + 0.55 * k))
    ctx.rotate(math.radians(78) * k)
    ctx.translate(-W * 0.5, -H * 0.5)
    ctx.set_source_surface(snap, 0, 0)
    ctx.paint()
    ctx.restore()
    if u > 0.7:                                                        # the feed breaks: static, then bars
        rng = np.random.default_rng(frame)
        n = rng.integers(0, 255, size=(int(H) // 4, int(W) // 4), dtype=np.uint8)
        a = np.zeros((int(H) // 4, int(W) // 4, 4), np.uint8)
        a[..., 0] = a[..., 1] = a[..., 2] = n
        a[..., 3] = 255
        st = cairo.ImageSurface.create_for_data(memoryview(a), cairo.FORMAT_ARGB32, int(W) // 4, int(H) // 4)
        ctx.save()
        ctx.scale(4, 4)
        ctx.set_source_surface(st, 0, 0)
        ctx.get_source().set_filter(cairo.FILTER_NEAREST)
        ctx.paint_with_alpha(min(1.0, (u - 0.7) / 0.2))
        ctx.restore()
        if u > 1.1:
            ctx.rectangle(0, H * 0.43, W, H * 0.14)
            ctx.set_source_rgb(0.05, 0.05, 0.08)
            ctx.fill()
            ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(54 * S)
            msg = "SIGNAL LOST"
            ext = ctx.text_extents(msg)
            ctx.move_to(W / 2 - ext.x_advance / 2, H * 0.52)
            ctx.set_source_rgb(0.95, 0.95, 0.95)
            ctx.show_text(msg)


def searchlight(ctx, cam, pos, alt, head, M, S, t):
    """a rescue helicopter's searchlight: a pale cone from its belly down through the rain to a bright pool on
    the water (it sweeps slowly, looking for people)"""
    top = np.array([pos[0], alt * M - 1.0 * M, pos[2]])
    sw = math.sin(t * 0.7) * 6 * M
    fw = np.array([math.cos(head), 0.0, math.sin(head)])
    sd = np.array([-fw[2], 0.0, fw[0]])
    spot = np.array([pos[0], 0.2 * M, pos[2]]) + fw * 8 * M + sd * sw
    if min(float(np.dot(q - cam.pos, cam.fwd)) for q in (top, spot)) < 1.0 * M:
        return
    r = 3.5 * M
    pts = cam.project(np.array([top, spot + sd * r, spot - sd * r]))
    ctx.move_to(*pts[0])
    ctx.line_to(*pts[1])
    ctx.line_to(*pts[2])
    ctx.close_path()
    g = cairo.LinearGradient(pts[0][0], pts[0][1], (pts[1][0] + pts[2][0]) / 2, (pts[1][1] + pts[2][1]) / 2)
    g.add_color_stop_rgba(0, 1.0, 0.98, 0.85, 0.45)
    g.add_color_stop_rgba(1, 1.0, 0.98, 0.85, 0.12)
    ctx.set_source(g)
    ctx.fill()
    cx, cy = cam.project(spot[None])[0]
    rx = abs(pts[1][0] - pts[2][0]) / 2
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(1.0, 0.3)
    ctx.arc(0, 0, max(1.0, rx), 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(1.0, 0.98, 0.85, 0.35)
    ctx.fill()


def lens_rain(ctx, W, H, S, t, amount=1.0):
    """rain on a camera lens in a storm: drops land and stay (each a little lens: dark rim, a bright point where
    it catches the sky), some grow heavy and run down in a streak"""
    n = int(46 * amount)
    for k in range(n):
        r = random.Random(k * 271 + 9)
        born = r.uniform(-4, 6)
        if t < born:
            continue
        x, y0 = r.uniform(0, W), r.uniform(0, H)
        rad = r.uniform(5, 16) * S
        run = r.random() < 0.35 and t - born > 0.8
        y = y0 + ((t - born - 0.8) * r.uniform(60, 160) * S if run else 0)
        if y > H + rad:
            continue
        if run:                                                       # the wet trail it leaves
            ctx.move_to(x, y0)
            ctx.line_to(x, y)
            ctx.set_source_rgba(0.85, 0.9, 0.95, 0.12)
            ctx.set_line_width(rad * 0.8)
            ctx.stroke()
        ctx.arc(x, y, rad, 0, 2 * math.pi)
        ctx.set_source_rgba(0.85, 0.9, 0.95, 0.16)
        ctx.fill_preserve()
        ctx.set_source_rgba(0.1, 0.12, 0.15, 0.35)
        ctx.set_line_width(1.4 * S)
        ctx.stroke()
        ctx.arc(x - rad * 0.3, y - rad * 0.35, rad * 0.22, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.7)
        ctx.fill()


def big_screen(ctx, cam, W, H, corners, spec, t, frame):
    """a screen kind (a slide, a graph, a paper) shown on a place's big screen: drawn full size, then laid onto the
    screen's corners in the picture (an affine fit to three corners - the screen is far enough to look flat)"""
    from . import stick3d_screens
    pts = np.array(corners, float)
    if min(float(np.dot(p - cam.pos, cam.fwd)) for p in pts) < 1.0:
        return
    sp = cam.project(pts)
    if sp[1][0] < sp[0][0]:                                            # seen from the other side: the picture's left
        sp = sp[[1, 0, 3, 2]]                                          # edge is the screen's other end (no mirror)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W), int(H))
    c2 = cairo.Context(surf)
    if not stick3d_screens.draw(c2, W, H, dict(spec, tv=False) if isinstance(spec, dict) else spec, t, frame):
        return
    (x0, y0), (x1, y1), _, (x3, y3) = sp                                # top-left, top-right, -, bottom-left
    m = cairo.Matrix((x1 - x0) / W, (y1 - y0) / W, (x3 - x0) / H, (y3 - y0) / H, x0, y0)
    ctx.save()
    ctx.move_to(*sp[0])
    for p in sp[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.clip()
    ctx.transform(m)
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint_with_alpha(0.96)
    ctx.restore()


def place_title(ctx, W, H, text, t):
    """the film's place card: small capitals typed in at the lower left (inside the 2.39 frame), held, then gone"""
    S = H / 1080.0
    bar = max(0.0, (H - W / 2.39) / 2)
    n = int(max(0.0, t - 0.3) * 22)
    if t > 4.5 or n <= 0:
        return
    a = 1.0 if t < 3.9 else max(0.0, (4.5 - t) / 0.6)
    ctx.save()
    ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(34 * S)
    ctx.move_to(70 * S, H - bar - 60 * S)
    ctx.set_source_rgba(0.95, 0.95, 0.92, a)
    ctx.show_text(text[:n])
    ctx.restore()
