"""🧊 Stick 3D places beyond the first village.

    village_2030()   2030, no ozone layer, no magnetic field: an Indian village under a white-hot sun.
                     Everything in it answers that one fact (so the world hangs together):
                     - the sun burns (UV from no ozone): shade cloth over the lanes and the crops, people in masks,
                       goggles and hoods, plants wilted, trees dead, the earth dried and cracked into plates
                     - power and water are precious: solar panels on every roof, tanks on the roofs, pots and drums
                     - storms of charged particles reach the ground (no magnetic field to turn them away): the
                       streaks falling from the sky, a dead phone tower, a temple still standing
                     - life goes on: a bullock cart (no fuel), a water tower, a far river, the hills

A place is a World: a list of meshes plus its sky, ground and sun (the look of the light is part of the place).
Sizes are real (M units per metre, the same as stick3d's village).
"""
import math
import random

import numpy as np


class World(list):
    """the meshes of a place + how its sky looks"""
    sky = (0.62, 0.84, 0.97)
    sky_top = None             # a second sky colour at the top of the frame (a gradient), or None
    ground = (0.93, 0.83, 0.58)
    sun = None                 # (dx, dy, dz) direction to a sun drawn in the sky, or None
    streaks = 0                # falling particle streaks in the sky (story rule: shows the storms)
    gear = False               # people wear masks / goggles / hoods by default
    ceiling = None             # a roof over the place (inside): the camera stays under it


def _frame(axis):
    """two directions at right angles to an axis (a, b) so that (a, axis, b) turns like (x, y, z)"""
    ax = np.asarray(axis, float)
    ax = ax / np.linalg.norm(ax)
    ref = np.array([0.0, 0.0, 1.0]) if abs(ax[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    a = np.cross(ax, ref)
    a /= np.linalg.norm(a)
    b = np.cross(a, ax)
    return a, ax, b


def rod_parts(p0, p1, w):
    """the 8 corners + 6 faces of a square beam from p0 to p1 (w thick)"""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    a, ax, b = _frame(p1 - p0)
    h = w / 2
    v = []
    for p in (p0, p1):
        for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            v.append(p + a * sa * h + b * sb * h)
    f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


def merged(parts, Mesh, **kw):
    """many (verts, faces) pieces as one mesh (one painter's sort, one shape for the ink)"""
    V, F = [], []
    for v, f in parts:
        o = len(V)
        V.extend(list(map(tuple, v)))
        F.extend([tuple(i + o for i in ff) for ff in f])
    return Mesh(V, F, **kw)


def sheet_parts(pts):
    """a thin cloth / panel through 4 points, seen from both sides"""
    return [tuple(map(float, p)) for p in pts], [(0, 1, 2, 3), (3, 2, 1, 0)]


def disk_parts(c, axis, r, thick, n=12):
    """a wheel: a short cylinder around an axis"""
    a, ax, b = _frame(axis)
    c = np.asarray(c, float)
    v = []
    for s in (-thick / 2, thick / 2):
        for k in range(n):
            t = 2 * math.pi * k / n
            v.append(c + ax * s + (a * math.cos(t) + b * math.sin(t)) * r)
    f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for k in range(n):
        k2 = (k + 1) % n
        f.append((k, k2, n + k2, n + k))
    return v, f


def village_2030(S3):
    """the 2030 village (S3 = the stick3d module: its Mesh, box, cylinder, pyramid, M)"""
    M, Mesh, box, cyl, pyr = S3.M, S3.Mesh, S3.box, S3.cylinder, S3.pyramid
    rng = random.Random(2030)
    w = World()
    w.sky = (0.99, 0.93, 0.74)                 # a white-hot, washed-out sky (UV haze)
    w.sky_top = (0.97, 0.80, 0.52)
    w.ground = (0.84, 0.66, 0.44)              # dry earth
    w.sun = (-0.30, 0.36, 1.0)                 # high and ahead: the camera looks toward it
    w.streaks = 46
    w.gear = True
    cz = 450.0

    # --- the cracked earth: plates of dried mud (one mesh drawn under everything)
    parts = []
    for gx in range(-14, 15):
        for gz in range(-4, 16):
            if abs(gx) < 4 and -1 <= gz <= 5:               # the lane where people stand stays packed earth
                continue
            x0 = gx * 1.25 * M + rng.uniform(-0.2, 0.2) * M
            z0 = cz + gz * 1.1 * M + rng.uniform(-0.2, 0.2) * M
            rr = rng.uniform(0.62, 0.72) * M
            n = rng.choice((5, 6, 6, 7))
            ph = rng.uniform(0, math.pi)
            v = [(x0 + rr * math.cos(ph + 2 * math.pi * k / n) * rng.uniform(0.85, 1.1), 0.6,
                  z0 + rr * 0.85 * math.sin(ph + 2 * math.pi * k / n) * rng.uniform(0.85, 1.1)) for k in range(n)]
            parts.append((v, [tuple(range(n - 1, -1, -1))]))   # (faces look up)
    m = merged(parts, Mesh, ink=0.35, name="mud")
    m.under = True
    w.append(m)

    # --- the row of houses on the left: flat roofs, solar panels, water tanks, shade cloth over the doors
    for i, (hz, wd, ht) in enumerate(((2.0, 5.0, 3.0), (7.6, 4.6, 3.4), (12.8, 5.4, 2.9), (18.4, 4.8, 3.2))):
        x = -8.6 * M
        z = cz + hz * M
        d = 4.2 * M
        w.append(box(x, 0, z, d, ht * M, wd * M, name="house30"))
        w.append(box(x, ht * M, z, d + 0.2 * M, 0.25 * M, wd * M + 0.2 * M, name="roof30"))
        fx = x + d / 2 + 1                                   # the front wall faces the lane (+x)
        w.append(S3.panel_x(fx, 0, z - 0.6 * M, 1.0 * M, 2.0 * M, name="door"))
        w.append(S3.panel_x(fx, 1.1 * M, z + 1.3 * M, 0.8 * M, 0.8 * M, name="window"))
        sp = []                                              # solar panels: tilted to the sun, a gap between each
        for k in range(3):
            zz = z - wd * M / 2 + (0.4 + k * 1.5) * M
            y0 = ht * M + 0.3 * M
            sp.append(sheet_parts([(x - 1.4 * M, y0, zz), (x - 1.4 * M, y0, zz + 1.3 * M),
                                   (x + 1.0 * M, y0 + 1.0 * M, zz + 1.3 * M), (x + 1.0 * M, y0 + 1.0 * M, zz)]))
        w.append(merged(sp, Mesh, ink=0.7, name="solar"))
        if i % 2 == 0:                                       # a water tank on the roof
            w.append(cyl(x - 1.0 * M, ht * M + 0.25 * M, z + wd * M / 2 - 1.0 * M, 0.7 * M, 1.4 * M, n=12, name="tank"))
        # shade cloth from the roof edge out over the lane, on two bamboo poles
        px = fx + 2.2 * M
        z0, z1 = z - wd * M / 2 + 0.3 * M, z + wd * M / 2 - 0.3 * M
        cloth = sheet_parts([(fx, ht * M - 0.2 * M, z0), (fx, ht * M - 0.2 * M, z1),
                             (px, 2.2 * M, z1), (px, 2.2 * M, z0)])
        poles = [rod_parts((px, 0, zz), (px, 2.3 * M, zz), 0.1 * M) for zz in (z0, z1)]
        w.append(merged([cloth], Mesh, ink=0.7, name="cloth"))
        w.append(merged(poles, Mesh, ink=0.7, name="bamboo"))
        for k in range(2):                                   # pots and drums by the door
            w.append(cyl(fx + 0.6 * M, 0, z + (1.6 + k * 0.7) * M, 0.3 * M, 0.75 * M, n=10, name="drum"))
    # a broken wall and rubble at the end of the row
    w.append(box(-8.6 * M, 0, cz + 23.5 * M, 4.0 * M, 1.6 * M, 0.4 * M, name="house30"))
    for k in range(9):
        s = rng.uniform(0.3, 0.7) * M
        w.append(box(rng.uniform(-7.0, -4.5) * M, 0, cz + rng.uniform(-1.5, 22) * M, s, s * 0.6, s * 0.9,
                     ink=0.7, name="rubble"))

    # --- dead trees: bare branches (no leaves under this sun)
    def dead_tree(x, z, s):
        parts = [rod_parts((x, 0, z), (x, 3.0 * M * s, z), 0.32 * M * s)]
        tips = []
        for k in range(5):
            ang = 2 * math.pi * k / 5 + rng.uniform(-0.3, 0.3)
            y0 = rng.uniform(1.8, 2.9) * M * s
            p0 = np.array([x, y0, z])
            p1 = p0 + np.array([math.cos(ang) * 1.6 * M * s, rng.uniform(1.4, 2.4) * M * s, math.sin(ang) * 1.2 * M * s])
            parts.append(rod_parts(p0, p1, 0.16 * M * s))
            tips.append(p1)
        for p in tips:                                       # twigs
            for _ in range(2):
                q = p + np.array([rng.uniform(-0.9, 0.9), rng.uniform(0.4, 1.0), rng.uniform(-0.6, 0.6)]) * M * s
                parts.append(rod_parts(p, q, 0.07 * M * s))
        w.append(merged(parts, Mesh, ink=0.8, name="deadwood"))

    for x, z, s in ((-4.8, 9.0, 1.25), (6.5, 24.0, 1.0), (-13.0, 28.0, 1.1), (15.0, 11.0, 0.9), (2.5, 34.0, 1.0)):
        dead_tree(x * M, cz + z * M, s)

    # --- the field on the right: rows of poles with shade nets, wilted plants under them
    net_parts, pole_parts, plants = [], [], []
    for row in range(3):
        z0 = cz + (2.5 + row * 4.2) * M
        for col in range(3):
            x0 = (6.0 + col * 3.2) * M
            pts = [(x0, 2.0 * M, z0), (x0, 2.0 * M, z0 + 3.4 * M), (x0 + 2.8 * M, 1.7 * M, z0 + 3.4 * M),
                   (x0 + 2.8 * M, 1.7 * M, z0)]
            net_parts.append(sheet_parts(pts))
            for p in pts:
                pole_parts.append(rod_parts((p[0], 0, p[2]), (p[0], p[1] + 0.1 * M, p[2]), 0.08 * M))
            for k in range(4):                               # wilted plants: drooping brown cones
                px = x0 + rng.uniform(0.4, 2.4) * M
                pz = z0 + rng.uniform(0.4, 3.0) * M
                plants.append(pyr(px, 0, pz, 0.45 * M, 0.9 * M, 0.45 * M, ink=0.6, name="wilted"))
    w.append(merged(net_parts, Mesh, ink=0.55, name="net"))
    w.append(merged(pole_parts, Mesh, ink=0.6, name="bamboo"))
    w.extend(plants)
    w.append(box(10.0 * M, 0, cz + 0.8 * M, 9.0 * M, 0.5 * M, 0.5 * M, ink=0.7, name="rubble"))   # a field wall

    # --- the bullock cart (no fuel left: animals pull again), parked in the lane
    cx, cz2 = 3.2 * M, cz + 6.5 * M
    cart = [rod_parts((cx - 1.1 * M, 0.95 * M, cz2), (cx + 1.1 * M, 0.95 * M, cz2), 0.0001)]
    cart = [(list(map(tuple, v)), f) for v, f in [(  # the bed: a flat box 2.2 x 1.4 m, side rails
        [(cx - 1.1 * M, 0.85 * M, cz2 - 0.7 * M), (cx + 1.1 * M, 0.85 * M, cz2 - 0.7 * M),
         (cx + 1.1 * M, 0.85 * M, cz2 + 0.7 * M), (cx - 1.1 * M, 0.85 * M, cz2 + 0.7 * M),
         (cx - 1.1 * M, 1.05 * M, cz2 - 0.7 * M), (cx + 1.1 * M, 1.05 * M, cz2 - 0.7 * M),
         (cx + 1.1 * M, 1.05 * M, cz2 + 0.7 * M), (cx - 1.1 * M, 1.05 * M, cz2 + 0.7 * M)],
        [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])]]
    cart += [rod_parts((cx - 1.1 * M, 1.05 * M, cz2 + s * 0.65 * M), (cx + 1.1 * M, 1.5 * M, cz2 + s * 0.65 * M), 0.1 * M)
             for s in (-1, 1)]
    cart += [disk_parts((cx, 0.7 * M, cz2 + s * 0.8 * M), (0, 0, 1), 0.7 * M, 0.12 * M) for s in (-1, 1)]
    cart += [rod_parts((cx - 1.0 * M, 0.9 * M, cz2 + s * 0.4 * M), (cx - 3.0 * M, 0.8 * M, cz2 + s * 0.3 * M), 0.1 * M)
             for s in (-1, 1)]
    w.append(merged(cart, Mesh, ink=0.85, name="cart"))

    # --- the town beyond: houses, two temples, the dead phone tower, a water tower
    for k in range(16):
        x = rng.uniform(-30, 30) * M
        z = cz + rng.uniform(38, 70) * M
        s = rng.uniform(3, 6) * M
        w.append(box(x, 0, z, s, rng.uniform(2.5, 5) * M, s, ink=0.6, name="town"))
    for x, z, h in ((-4.0, 52.0, 13.0), (9.0, 47.0, 10.0)):  # temples: a block and a tall shikhara with a flag
        w.append(box(x * M, 0, cz + z * M, 5 * M, 4 * M, 5 * M, ink=0.7, name="temple"))
        w.append(pyr(x * M, 4 * M, cz + z * M, 4.2 * M, h * M, 4.2 * M, ink=0.7, name="shikhara"))
        top = 4 * M + h * M
        w.append(merged([rod_parts((x * M, top, cz + z * M), (x * M, top + 2.0 * M, cz + z * M), 0.12 * M),
                         sheet_parts([(x * M, top + 2.0 * M, cz + z * M), (x * M + 1.4 * M, top + 1.7 * M, cz + z * M),
                                      (x * M + 1.4 * M, top + 1.3 * M, cz + z * M), (x * M, top + 1.3 * M, cz + z * M)])],
                        Mesh, ink=0.7, name="flag"))
    tx, tz, th = 1.0 * M, cz + 44 * M, 26 * M                # the phone tower: four legs to a point, braces
    legs = [(tx - 2.2 * M, tz - 2.2 * M), (tx + 2.2 * M, tz - 2.2 * M), (tx + 2.2 * M, tz + 2.2 * M), (tx - 2.2 * M, tz + 2.2 * M)]
    tw = []
    for lx, lz in legs:
        tw.append(rod_parts((lx, 0, lz), (tx + (lx - tx) * 0.15, th, tz + (lz - tz) * 0.15), 0.35 * M))
    for f in (0.25, 0.5, 0.75):
        ring = [(tx + (lx - tx) * (1 - 0.85 * f), th * f, tz + (lz - tz) * (1 - 0.85 * f)) for lx, lz in legs]
        for a, b in zip(ring, ring[1:] + ring[:1]):
            tw.append(rod_parts(a, b, 0.2 * M))
    tw.append(rod_parts((tx, th, tz), (tx, th + 4 * M, tz), 0.3 * M))
    for s in (-1, 1):                                        # dish antennas hanging dead
        tw.append(disk_parts((tx + s * 0.9 * M, th - 1.5 * M, tz - 0.6 * M), (s * 0.5, -0.4, -1), 0.8 * M, 0.2 * M))
    w.append(merged(tw, Mesh, ink=0.75, name="tower"))
    wx, wz = 17.0 * M, cz + 50 * M                           # the water tower
    w.append(cyl(wx, 9 * M, wz, 3.0 * M, 3.5 * M, n=14, name="tank"))
    w.append(merged([rod_parts((wx + sx * 2.2 * M, 0, wz + sz * 2.2 * M), (wx + sx * 2.0 * M, 9 * M, wz + sz * 2.0 * M), 0.3 * M)
                     for sx in (-1, 1) for sz in (-1, 1)], Mesh, ink=0.75, name="bamboo"))

    # --- the river far off to the right (a low ribbon) and the hills on the horizon
    rv = []
    for k in range(10):
        z0 = cz + (40 + k * 18) * M
        x0 = (24 + 8 * math.sin(k * 0.7)) * M
        x1 = (24 + 8 * math.sin((k + 1) * 0.7)) * M
        rv.append(([(x0, 0.8, z0), (x0 + 7 * M, 0.8, z0), (x1 + 7 * M, 0.8, z0 + 18 * M), (x1, 0.8, z0 + 18 * M)],
                   [(3, 2, 1, 0)]))
    m = merged(rv, Mesh, ink=0.3, name="river")
    m.under = True
    w.append(m)
    for k in range(9):
        x = (-260 + k * 65 + rng.uniform(-20, 20)) * M
        z = cz + rng.uniform(320, 420) * M
        wd = rng.uniform(120, 190) * M
        w.append(pyr(x, 0, z, wd, rng.uniform(35, 70) * M, wd * 0.6, ink=0.5, name="hill"))
    return w


# ---------------------------------------------------------------------------- 2026: Deepak's Madhya Pradesh
def weather_station(S3, x, z, y0=0.0, pole=3.0):
    """Deepak's weather station (one design for every district, a pro research mast): a steel tripod with braced
    legs, the mast with its clamp collars, a crossarm on top with the wind vane and the cup anemometer, a tall
    lightning rod (the highest point takes the strike, not the electronics), a tilted solar panel facing the sun,
    the white louvred radiation shield (it reads the air, not the sunshine), the white logger box with the LoRa
    radio, and a rain gauge on its own post a step away (out of the mast's drip and wind shadow)"""
    M, Mesh = S3.M, S3.Mesh
    out = []
    top = y0 + pole * M
    steel = []
    steel.append(rod_parts((x, y0, z), (x, top, z), 0.08 * M))          # the mast
    hub = y0 + 0.62 * pole * M * 0.5                                    # where the legs meet the mast
    for k in range(3):                                                 # the tripod: three legs splayed out
        t = math.radians(90 + 120 * k)
        fx_, fz_ = x + math.cos(t) * 1.25 * M, z + math.sin(t) * 1.25 * M
        steel.append(rod_parts((x, hub, z), (fx_, y0, fz_), 0.06 * M))
        mx_, mz_ = x + math.cos(t) * 0.62 * M, z + math.sin(t) * 0.62 * M
        steel.append(rod_parts((x, y0 + 0.25 * M, z), (mx_, (hub + y0) / 2 + 0.02 * M, mz_), 0.035 * M))  # brace
        steel.append(disk_parts((fx_, y0 + 0.01 * M, fz_), (0, 1, 0), 0.09 * M, 0.02 * M, n=6))   # foot plate
    for yy in (hub, y0 + 0.62 * pole * M, top - 0.5 * M):            # clamp collars on the mast
        steel.append(disk_parts((x, yy, z), (0, 1, 0), 0.075 * M, 0.12 * M, n=8))
    ya = top - 0.35 * M                                                # the crossarm across the top
    steel.append(rod_parts((x - 0.75 * M, ya, z), (x + 0.75 * M, ya, z), 0.05 * M))
    steel.append(rod_parts((x + 0.7 * M, ya, z), (x + 0.7 * M, ya + 0.55 * M, z), 0.035 * M))  # the sensor post
    steel.append(rod_parts((x + 0.45 * M, ya + 0.55 * M, z), (x + 0.95 * M, ya + 0.55 * M, z), 0.03 * M))
    steel.append(rod_parts((x - 0.75 * M, ya, z), (x - 0.75 * M, ya + 0.12 * M, z), 0.04 * M))  # the sun sensor
    out.append(merged(steel, Mesh, ink=0.8, name="steel"))
    # the wind vane (left) and the three-cup anemometer (right) on the sensor post
    vx, cx_, yv = x + 0.45 * M, x + 0.95 * M, ya + 0.55 * M
    wind = [rod_parts((vx, yv, z), (vx, yv + 0.2 * M, z), 0.025 * M),
            rod_parts((vx - 0.3 * M, yv + 0.2 * M, z), (vx + 0.12 * M, yv + 0.2 * M, z), 0.02 * M),
            sheet_parts([(vx - 0.42 * M, yv + 0.08 * M, z), (vx - 0.28 * M, yv + 0.12 * M, z),
                         (vx - 0.28 * M, yv + 0.30 * M, z), (vx - 0.42 * M, yv + 0.34 * M, z)]),
            rod_parts((cx_, yv, z), (cx_, yv + 0.22 * M, z), 0.025 * M)]
    for k in range(3):
        t = math.radians(120 * k + 30)
        ex, ez = cx_ + math.cos(t) * 0.16 * M, z + math.sin(t) * 0.16 * M
        wind.append(rod_parts((cx_, yv + 0.22 * M, z), (ex, yv + 0.22 * M, ez), 0.015 * M))
        wind.append(disk_parts((ex, yv + 0.22 * M, ez), (math.cos(t + 1.57), 0, math.sin(t + 1.57)),
                               0.05 * M, 0.05 * M, n=8))
    out.append(merged(wind, Mesh, ink=0.8, name="antenna"))
    # the lightning rod / LoRa whip: a thin rod far above everything
    out.append(merged([rod_parts((x, top, z), (x, top + 1.6 * M, z), 0.022 * M)], Mesh, ink=0.9, name="antenna"))
    # the solar panel on the left, tilted up toward the sky
    ys = y0 + 0.62 * pole * M + 0.15 * M
    out.append(merged([sheet_parts([(x - 0.12 * M, ys - 0.35 * M, z - 0.08 * M), (x - 0.62 * M, ys - 0.35 * M, z - 0.08 * M),
                                    (x - 0.62 * M, ys + 0.30 * M, z + 0.18 * M), (x - 0.12 * M, ys + 0.30 * M, z + 0.18 * M)])],
                      Mesh, ink=0.8, name="solar"))
    # the radiation shield on the right: a stack of white plates on a short arm
    rx, ry = x + 0.32 * M, ys - 0.25 * M
    shield = [rod_parts((x, ry + 0.1 * M, z), (rx, ry + 0.1 * M, z), 0.03 * M)]
    shield += [disk_parts((rx, ry + k * 0.055 * M, z), (0, 1, 0), 0.085 * M - k * 0.004 * M, 0.035 * M, n=10)
               for k in range(5)]
    out.append(merged(shield, Mesh, ink=0.6, name="station"))
    # the logger box (a louvred white case, solar glass on its roof): front to the person (-z)
    yb = y0 + 1.1 * M                                                  # chest height: read without a ladder
    out.append(S3.box(x, yb, z - 0.12 * M, 0.42 * M, 0.48 * M, 0.22 * M, ink=0.8, name="station"))
    lv = [rod_parts((x - 0.17 * M, yb + (0.07 + 0.05 * k) * M, z - 0.235 * M),
                    (x + 0.17 * M, yb + (0.07 + 0.05 * k) * M, z - 0.235 * M), 0.018 * M) for k in range(7)]
    out.append(merged(lv, Mesh, ink=0.4, name="steel"))               # the louvres of the door
    out.append(S3.box(x, yb + 0.48 * M, z - 0.12 * M, 0.52 * M, 0.04 * M, 0.32 * M, ink=0.8, name="station"))  # the roof
    out.append(merged([sheet_parts([(x - 0.24 * M, yb + 0.525 * M, z - 0.27 * M), (x + 0.24 * M, yb + 0.525 * M, z - 0.27 * M),
                                    (x + 0.24 * M, yb + 0.525 * M, z + 0.03 * M), (x - 0.24 * M, yb + 0.525 * M, z + 0.03 * M)])],
                      Mesh, ink=0.5, name="solar"))                    # the solar glass on the roof
    out.append(merged([rod_parts((x - 0.17 * M, yb + 0.52 * M, z - 0.2 * M), (x - 0.19 * M, yb + 0.85 * M, z - 0.2 * M),
                                 0.03 * M)], Mesh, ink=0.8, name="antenna"))   # the stubby LoRa antenna
    # the rain gauge on its own black post and a round concrete foot, a step to the right and behind
    gx, gz = x + 1.0 * M, z + 0.55 * M
    out.append(S3.cylinder(gx, y0, gz, 0.32 * M, 0.06 * M, n=14, name="concrete"))
    out.append(merged([rod_parts((gx, y0 + 0.06 * M, gz), (gx, y0 + 1.05 * M, gz), 0.1 * M)], Mesh, ink=0.8, name="antenna"))
    out.append(S3.cylinder(gx + 0.1 * M, y0 + 0.82 * M, gz, 0.12 * M, 0.2 * M, n=12, name="station"))
    out.append(S3.cylinder(gx + 0.1 * M, y0 + 1.02 * M, gz, 0.125 * M, 0.08 * M, n=12, name="gauge_cap"))
    return out


def _tree(S3, w, x, z, s=1.0):
    M = S3.M
    w.append(S3.cylinder(x, 0, z, 0.22 * M * s, 3.0 * M * s, n=8, top_r=0.15 * M * s, name="trunk"))
    w.append(S3.ball(x, 4.4 * M * s, z, 2.2 * M * s, sy=0.75, n=9, m=5, name="crown"))


def _hills(S3, w, cz, rng, col="hill26"):
    M = S3.M
    for k in range(8):                                                 # the Vindhya hills on the horizon
        x = (-240 + k * 70 + rng.uniform(-20, 20)) * M
        z = cz + rng.uniform(300, 420) * M
        wd = rng.uniform(130, 200) * M
        w.append(S3.pyramid(x, 0, z, wd, rng.uniform(25, 45) * M, wd * 0.6, ink=0.45, name=col))


def home_2026(S3):
    """Deepak's home in a small Madhya Pradesh town, 2026 (before anything went wrong): a two-room pucca house
    with a flat roof - his first weather station on it and a LoRa mast - a tin-roofed workshop beside it with a
    workbench, a laptop and boxes of parts, a test station in the yard, neem trees, green fields behind"""
    M, Mesh, box, cyl = S3.M, S3.Mesh, S3.box, S3.cylinder
    rng = random.Random(2026)
    w = World()
    w.sky = (0.62, 0.84, 0.97)
    w.ground = (0.80, 0.82, 0.52)                                      # dry grass and earth (before the monsoon)
    cz = 450.0
    hx, hz = -1.0 * M, cz + 10.5 * M                                  # the house at the back of the yard
    w.append(box(hx, 0, hz, 8.0 * M, 3.2 * M, 5.5 * M, name="wall26"))
    w.append(box(hx, 3.2 * M, hz, 8.3 * M, 0.25 * M, 5.8 * M, name="roof26"))
    w.append(box(hx, 3.45 * M, hz, 8.3 * M, 0.6 * M, 0.15 * M, ink=0.7, name="roof26"))   # the parapet
    w.append(S3.panel(hx + 1.5 * M, 0, hz - 2.76 * M, 1.1 * M, 2.1 * M, ink=0.9, name="door"))
    for wx in (-2.2, 3.4):
        w.append(S3.panel(hx + wx * M, 1.0 * M, hz - 2.76 * M, 1.1 * M, 1.1 * M, ink=0.8, name="window"))
    w.append(cyl(hx + 2.6 * M, 3.45 * M, hz + 1.2 * M, 0.6 * M, 1.2 * M, n=12, name="tank26"))
    w.extend(weather_station(S3, hx - 2.4 * M, hz - 0.8 * M, y0=3.45 * M, pole=2.2))
    w.append(merged([rod_parts((hx - 3.4 * M, 3.45 * M, hz + 1.5 * M), (hx - 3.4 * M, 11.0 * M, hz + 1.5 * M), 0.08 * M)],
                    Mesh, ink=0.8, name="steel"))                      # the tall LoRa mast
    w.append(merged([sheet_parts([(hx + 0.5 * M, 3.6 * M, hz + 0.2 * M), (hx - 1.2 * M, 3.6 * M, hz + 0.2 * M),
                                  (hx - 1.2 * M, 4.4 * M, hz + 1.6 * M), (hx + 0.5 * M, 4.4 * M, hz + 1.6 * M)])],
                    Mesh, ink=0.7, name="solar"))
    # the workshop: a tin roof on four poles (screen left), a workbench with a laptop, boxes of parts
    sx, sz = 7.0 * M, cz + 5.0 * M
    poles = [rod_parts((sx + dx * M, 0, sz + dz * M), (sx + dx * M, (2.6 if dz < 0 else 2.9) * M, sz + dz * M), 0.12 * M)
             for dx in (-2.2, 2.2) for dz in (-1.6, 1.6)]
    w.append(merged(poles, Mesh, ink=0.8, name="steel"))
    w.append(merged([sheet_parts([(sx - 2.5 * M, 2.6 * M, sz - 1.9 * M), (sx + 2.5 * M, 2.6 * M, sz - 1.9 * M),
                                  (sx + 2.5 * M, 2.95 * M, sz + 1.9 * M), (sx - 2.5 * M, 2.95 * M, sz + 1.9 * M)])],
                    Mesh, ink=0.8, name="tin"))
    w.append(box(sx, 0.75 * M, sz + 0.6 * M, 3.0 * M, 0.08 * M, 0.9 * M, name="bench"))
    for dx in (-1.4, 1.4):
        for dz in (0.25, 0.95):
            w.append(box(sx + dx * M, 0, sz + dz * M, 0.07 * M, 0.75 * M, 0.07 * M, ink=0.7, name="bench"))
    w.append(box(sx - 0.6 * M, 0.83 * M, sz + 0.5 * M, 0.5 * M, 0.03 * M, 0.35 * M, ink=0.8, name="laptop"))
    w.append(merged([sheet_parts([(sx - 0.85 * M, 0.86 * M, sz + 0.7 * M), (sx - 0.35 * M, 0.86 * M, sz + 0.7 * M),
                                  (sx - 0.35 * M, 1.18 * M, sz + 0.78 * M), (sx - 0.85 * M, 1.18 * M, sz + 0.78 * M)])],
                    Mesh, ink=0.8, name="screen"))
    for k, (bx, s) in enumerate(((0.5, 0.35), (1.0, 0.28), (0.8, 0.22))):   # boxes of sensors on the bench
        w.append(box(sx + bx * M, 0.83 * M + (0.35 * M if k == 2 else 0), sz + 0.55 * M, s * M, s * M, s * M,
                     ink=0.7, name="crate"))
    for k in range(4):                                                 # cartons stacked under the shed
        w.append(box(sx + (1.8 - 0.1 * k) * M, k % 2 * 0.5 * M, sz - 1.0 * M, 0.6 * M, 0.5 * M, 0.5 * M, ink=0.7, name="crate"))
    w.extend(weather_station(S3, -4.5 * M, cz + 3.5 * M))              # the test station in the yard
    w.append(box(-6.5 * M, 0.45 * M, cz + 6.5 * M, 2.0 * M, 0.08 * M, 0.95 * M, name="cot"))   # a charpai
    for dx in (-0.95, 0.95):
        for dz in (-0.42, 0.42):
            w.append(box(-6.5 * M + dx * M, 0, cz + 6.5 * M + dz * M, 0.07 * M, 0.45 * M, 0.07 * M, ink=0.8, name="cot_leg"))
    for k in range(12):                                                # a low boundary wall at the back
        w.append(box((-14 + k * 2.4) * M, 0, cz + 15.5 * M, 2.4 * M, 1.2 * M, 0.25 * M, ink=0.6, name="wall26"))
    for x, z, s in ((-9.5, 12.0, 1.2), (11.5, 11.0, 1.1), (4.5, 19.0, 1.0), (-13.0, 4.0, 1.0), (14.0, 2.0, 0.9)):
        _tree(S3, w, x * M, cz + z * M, s)
    for k in range(6):                                                 # green fields beyond the wall
        w.append(box((-20 + k * 7.0) * M, 0, cz + 24 * M, 6.0 * M, 0.5 * M, 6.0 * M, ink=0.4, name="crop"))
    _hills(S3, w, cz, rng)
    return w


def field_2026(S3):
    """a field in a Madhya Pradesh district, 2026: rows of soybean, a dirt road, an electric line, a village
    far off - and one of Deepak's weather stations on its pole (50 km from the next one)"""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    rng = random.Random(2027)
    w = World()
    w.sky = (0.60, 0.83, 0.97)
    w.ground = (0.62, 0.74, 0.40)                                      # green after the rain
    cz = 450.0
    road = ([(-60 * M, 0.6, cz - 1.5 * M), (60 * M, 0.6, cz - 1.5 * M), (60 * M, 0.6, cz + 1.5 * M),
              (-60 * M, 0.6, cz + 1.5 * M)], [(3, 2, 1, 0)])
    m = merged([road], Mesh, ink=0.4, name="road")
    m.under = True
    w.append(m)
    for row in range(10):                                              # the crop rows (low and long)
        z = cz + (4.0 + row * 1.6) * M
        for seg in range(3):
            x0 = (-24 + seg * 17) * M
            w.append(box(x0 + 7.5 * M, 0, z, 15 * M, 0.55 * M, 0.7 * M, ink=0.35, name="crop"))
    w.extend(weather_station(S3, 2.0 * M, cz + 3.0 * M))
    for k in range(7):                                                 # an electric line beyond the field
        x = (-30 + k * 10) * M
        zl = cz + 22.0 * M
        w.append(merged([rod_parts((x, 0, zl), (x, 7.5 * M, zl), 0.18 * M),
                         rod_parts((x - 0.8 * M, 7.0 * M, zl), (x + 0.8 * M, 7.0 * M, zl), 0.1 * M)],
                        Mesh, ink=0.7, name="concrete"))
    for x, z, s in ((-9, 2.5, 1.1), (12, 4.0, 1.0), (-18, 26, 1.2), (20, 30, 1.0), (4, 34, 0.9)):
        _tree(S3, w, x * M, cz + z * M, s)
    for k in range(10):                                                # a village far away
        w.append(box(rng.uniform(-35, 5) * M, 0, cz + rng.uniform(45, 60) * M, 4 * M, rng.uniform(2.5, 4) * M, 4 * M,
                     ink=0.5, name="wall26"))
    _hills(S3, w, cz, rng)
    sx_, sz_ = 2.0 * M, cz + 3.0 * M                                   # the station: work spot and close cameras
    w.spots = {"station": (sx_, sz_ - 0.75 * M), "road": (0.0, cz)}
    w.shots = {
        "station_low": ((sx_ - 1.6 * M, 0.35 * M, sz_ - 2.6 * M), (sx_, 2.4 * M, sz_)),
        "station_close": ((sx_ + 1.5 * M, 1.75 * M, sz_ - 1.6 * M), (sx_, 1.65 * M, sz_ - 0.3 * M)),
        "hands": ((sx_ + 0.55 * M, 1.95 * M, sz_ - 1.05 * M), (sx_, 1.75 * M, sz_ - 0.33 * M)),
        "antenna": ((sx_ - 0.9 * M, 1.2 * M, sz_ - 1.4 * M), (sx_ + 0.12 * M, 3.6 * M, sz_)),
        "station_wide": ((sx_ - 9 * M, 2.2 * M, sz_ - 10 * M), (sx_, 1.6 * M, sz_)),
        "behind": ((sx_ - 0.6 * M, 1.7 * M, sz_ + 1.6 * M), (sx_ + 0.2 * M, 1.4 * M, sz_ - 1.2 * M)),
    }
    return w


def grid_sheet(p0, du, dv, nu, nv):
    """a flat sheet from corner p0 along du and dv, cut into nu x nv tiles that share their corners (no ink between
    them): a big wall or ceiling stays drawn even when part of it is behind the camera (each tile is tested alone).
    It faces the side du x dv points to."""
    p0, du, dv = (np.asarray(a, float) for a in (p0, du, dv))
    v = [tuple(p0 + du * (i / nu) + dv * (j / nv)) for j in range(nv + 1) for i in range(nu + 1)]
    f = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            f.append((a, a + 1, a + nu + 2, a + nu + 1))
    return v, f


def basement_2026(S3):
    """Deepak's basement workstation, under his house: bare concrete, a low ceiling with one tube light, a long
    desk against the back wall with three monitors (the station map, graphs, a terminal), a server rack with its
    lights, the LoRa base radio with its cable going up through the ceiling, shelves of station boxes, a
    whiteboard with the 50 km grid, and the stairs coming down on the left. The front (camera side) is open."""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    w = World()
    w.sky = (0.20, 0.22, 0.26)                                         # (no sky down here)
    w.ground = (0.52, 0.53, 0.55)                                      # the concrete floor
    w.ceiling = 3.0 * M
    cz = 450.0
    zb = cz + 4.6 * M                                                  # the back wall
    xl, xr = 6.4 * M, -6.4 * M                                         # left (screen left) and right walls
    zf = cz - 11.0 * M                                                 # (the walls run back past the camera)
    H_ = 3.0 * M
    # walls and ceiling as tiled sheets facing into the room
    w.append(merged([grid_sheet((xl, 0, zb), (xr - xl, 0, 0), (0, H_, 0), 6, 2)], Mesh, ink=0.6, name="concrete_wall"))
    w.append(merged([grid_sheet((xl, 0, zf), (0, 0, zb - zf), (0, H_, 0), 16, 2)], Mesh, ink=0.6, name="concrete_wall"))
    w.append(merged([grid_sheet((xr, 0, zb), (0, 0, zf - zb), (0, H_, 0), 16, 2)], Mesh, ink=0.6, name="concrete_wall"))
    w.append(merged([grid_sheet((xr, H_, zf), (xl - xr, 0, 0), (0, 0, zb - zf), 6, 16)], Mesh, ink=0.5, name="ceiling"))
    for m in w[-4:]:                                                   # the room's shell is drawn first: all that
        m.under = True                                                 # is in the room stands in front of it
    w.append(box(0, 2.88 * M, cz + 1.0 * M, 1.6 * M, 0.08 * M, 0.14 * M, ink=0.6, name="tube"))     # the tube light
    # the desk along the back wall and its three monitors
    w.append(box(0.5 * M, 0.75 * M, zb - 0.45 * M, 4.4 * M, 0.08 * M, 0.9 * M, name="bench"))
    for dx in (-2.0, 2.0):
        w.append(box(0.5 * M + dx * M, 0, zb - 0.45 * M, 0.08 * M, 0.75 * M, 0.8 * M, ink=0.7, name="bench"))
    for k, (mx, ang) in enumerate(((-0.9, 0.25), (0.5, 0.0), (1.9, -0.25))):
        cx_, cy_ = (0.5 + mx) * M, 1.35 * M
        hw, hh = 0.55 * M, 0.36 * M
        dz = math.sin(ang) * hw
        z_ = zb - 0.7 * M
        w.append(merged([sheet_parts([(cx_ - hw * math.cos(ang), cy_ - hh, z_ - dz), (cx_ + hw * math.cos(ang), cy_ - hh, z_ + dz),
                                      (cx_ + hw * math.cos(ang), cy_ + hh, z_ + dz), (cx_ - hw * math.cos(ang), cy_ + hh, z_ - dz)])],
                        Mesh, ink=0.9, name=("monitor_map", "monitor_graph", "monitor_term")[k]))
        w.append(box(cx_, 0.83 * M, z_ + 0.15 * M, 0.08 * M, 0.2 * M, 0.08 * M, ink=0.7, name="laptop"))
    w.append(box(0.5 * M, 0.83 * M, zb - 0.95 * M, 0.9 * M, 0.03 * M, 0.3 * M, ink=0.7, name="laptop"))   # keyboard
    w.append(box(0.5 * M, 0.36 * M, zb - 1.6 * M, 0.6 * M, 0.08 * M, 0.6 * M, ink=0.7, name="chair"))     # the chair:
    w.append(box(0.5 * M, 0.44 * M, zb - 1.92 * M, 0.6 * M, 0.75 * M, 0.06 * M, ink=0.7, name="chair"))   # seat at
    w.append(merged([rod_parts((0.5 * M, 0, zb - 1.6 * M), (0.5 * M, 0.36 * M, zb - 1.6 * M), 0.08 * M)], Mesh,
                    ink=0.7, name="steel"))                            # sitting height (the sit pose's hips)
    # the server rack, its lights, the LoRa base radio and its cable up through the ceiling
    rx = -4.2 * M
    w.append(box(rx, 0, zb - 0.6 * M, 1.0 * M, 2.1 * M, 0.9 * M, ink=0.8, name="rack"))
    for j in range(6):
        w.append(merged([sheet_parts([(rx - 0.35 * M, (0.3 + 0.3 * j) * M, zb - 1.06 * M),
                                      (rx - 0.15 * M, (0.3 + 0.3 * j) * M, zb - 1.06 * M),
                                      (rx - 0.15 * M, (0.36 + 0.3 * j) * M, zb - 1.06 * M),
                                      (rx - 0.35 * M, (0.36 + 0.3 * j) * M, zb - 1.06 * M)])], Mesh, ink=0.3,
                        name="led_green" if j % 3 else "led_red"))
    w.append(box(rx, 2.1 * M, zb - 0.6 * M, 0.5 * M, 0.25 * M, 0.4 * M, ink=0.8, name="station"))
    w.append(merged([rod_parts((rx + 0.1 * M, 2.35 * M, zb - 0.6 * M), (rx + 0.1 * M, 3.0 * M, zb - 0.6 * M), 0.05 * M)],
                    Mesh, ink=0.8, name="antenna"))
    # shelves of station boxes on the right wall
    for j in range(3):
        y = (0.5 + 0.7 * j) * M
        w.append(box(xr + 0.5 * M, y, cz + 0.5 * M, 0.6 * M, 0.06 * M, 3.2 * M, ink=0.7, name="bench"))
        for k in range(4):
            w.append(box(xr + 0.5 * M, y + 0.06 * M, cz + (-0.8 + 0.8 * k) * M, 0.35 * M, 0.4 * M, 0.35 * M,
                         ink=0.7, name="station"))
    # the whiteboard with the grid on the left wall
    wbx = xl - 0.02 * M
    w.append(merged([([(wbx, 0.9 * M, cz - 0.5 * M), (wbx, 0.9 * M, cz + 2.5 * M), (wbx, 2.3 * M, cz + 2.5 * M),
                       (wbx, 2.3 * M, cz - 0.5 * M)], [(0, 1, 2, 3)])], Mesh, ink=0.9, name="whiteboard"))
    grid = []
    for g in range(1, 6):
        zz = cz + (-0.5 + 0.5 * g) * M
        grid.append(rod_parts((wbx - 0.03 * M, 0.95 * M, zz), (wbx - 0.03 * M, 2.25 * M, zz), 0.015 * M))
    for g in range(1, 4):
        yy = (0.9 + 0.35 * g) * M
        grid.append(rod_parts((wbx - 0.03 * M, yy, cz - 0.45 * M), (wbx - 0.03 * M, yy, cz + 2.45 * M), 0.015 * M))
    w.append(merged(grid, Mesh, ink=0.4, name="led_green"))
    # the stairs down on the left, toward the front
    for j in range(8):
        w.append(box(xl - 0.9 * M, 0, cz - 2.6 * M + j * 0.3 * M, 1.6 * M, (3.0 - 0.36 * j) * M, 0.3 * M,
                     ink=0.6, name="concrete_wall"))
    return w


def land_2027(S3):
    """the land, 2027: 300 acres of dry scrub near Bhopal with a boundary of stone posts and wire, survey flags,
    a site office (a tin shed), a digger and the first pit of the underground home with its mounds of earth"""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    rng = random.Random(2028)
    w = World()
    w.sky = (0.64, 0.84, 0.97)
    w.ground = (0.84, 0.76, 0.52)
    cz = 450.0
    # the pit: a dark hole in the ground (drawn on the ground) with mounds of earth round it
    px, pz = -3.0 * M, cz + 9.0 * M
    pit = ([(px - 7 * M, 0.6, pz - 3 * M), (px + 7 * M, 0.6, pz - 3 * M), (px + 7 * M, 0.6, pz + 3 * M),
            (px - 7 * M, 0.6, pz + 3 * M)], [(3, 2, 1, 0)])
    m = merged([pit], Mesh, ink=0.8, name="pit")
    m.under = True
    w.append(m)
    inner = ([(px - 6 * M, 0.8, pz - 2.2 * M), (px + 6 * M, 0.8, pz - 2.2 * M), (px + 6 * M, 0.8, pz + 2.2 * M),
              (px - 6 * M, 0.8, pz + 2.2 * M)], [(3, 2, 1, 0)])
    m = merged([inner], Mesh, ink=0.4, name="pit_deep")
    m.under = True
    w.append(m)
    for k in range(5):
        w.append(S3.ball((-11 + k * 4.0) * M, 0, pz + 5.0 * M, 1.6 * M, sy=0.6, n=9, m=5, floor=0.0, name="mound"))
    # the digger: tracks, cab, boom and bucket over the pit
    dx_, dz_ = 6.0 * M, cz + 7.0 * M
    w.append(box(dx_, 0, dz_, 3.4 * M, 0.8 * M, 2.4 * M, ink=0.8, name="track"))
    w.append(box(dx_, 0.8 * M, dz_, 2.4 * M, 1.0 * M, 2.0 * M, ink=0.8, name="digger"))
    w.append(box(dx_ + 0.4 * M, 1.8 * M, dz_, 1.4 * M, 1.4 * M, 1.6 * M, ink=0.8, name="digger"))
    w.append(merged([rod_parts((dx_ - 0.8 * M, 1.6 * M, dz_), (dx_ - 4.0 * M, 4.2 * M, dz_), 0.4 * M),
                     rod_parts((dx_ - 4.0 * M, 4.2 * M, dz_), (dx_ - 6.0 * M, 1.2 * M, dz_), 0.3 * M)],
                    Mesh, ink=0.8, name="digger"))
    w.append(box(dx_ - 6.2 * M, 0.6 * M, dz_, 1.0 * M, 0.7 * M, 1.2 * M, ink=0.8, name="track"))
    # the site office (a tin shed) and a water tank
    sx, sz = -12.0 * M, cz + 3.0 * M
    w.append(box(sx, 0, sz, 4.0 * M, 2.6 * M, 3.0 * M, ink=0.8, name="tin"))
    w.append(box(sx, 2.6 * M, sz, 4.4 * M, 0.15 * M, 3.4 * M, ink=0.8, name="roof26"))
    w.append(S3.panel_x(sx + 2.01 * M, 0, sz - 0.4 * M, 0.9 * M, 2.0 * M, ink=0.9, name="door"))
    w.append(S3.cylinder(sx - 1.0 * M, 2.75 * M, sz + 0.8 * M, 0.6 * M, 1.2 * M, n=12, name="tank26"))
    # the boundary: stone posts and wire far round the land; survey flags
    posts = []
    for k in range(26):
        x = (-60 + k * 5) * M
        posts.append(rod_parts((x, 0, cz + 30 * M), (x, 1.3 * M, cz + 30 * M), 0.25 * M))
    w.append(merged(posts, Mesh, ink=0.6, name="concrete"))
    w.append(merged([rod_parts((-60 * M, 1.0 * M, cz + 30 * M), (65 * M, 1.0 * M, cz + 30 * M), 0.04 * M)],
                    Mesh, ink=0.6, name="steel"))
    for k in range(6):
        fx, fz = rng.uniform(-14, 14) * M, cz + rng.uniform(14, 26) * M
        w.append(merged([rod_parts((fx, 0, fz), (fx, 1.4 * M, fz), 0.05 * M),
                         sheet_parts([(fx, 1.4 * M, fz), (fx + 0.5 * M, 1.3 * M, fz), (fx + 0.5 * M, 1.05 * M, fz),
                                      (fx, 1.0 * M, fz)])], Mesh, ink=0.7, name="flag"))
    for x, z, s in ((-18, 18, 1.1), (16, 22, 1.0), (24, 6, 0.9), (-26, 8, 1.0)):
        _tree(S3, w, x * M, cz + z * M, s)
    for k in range(14):                                                # scrub bushes
        w.append(S3.ball(rng.uniform(-30, 30) * M, 0, cz + rng.uniform(12, 40) * M, rng.uniform(0.5, 0.9) * M,
                         sy=0.7, n=7, m=4, floor=0.0, name="crown"))
    _hills(S3, w, cz, rng)
    return w


def _ball_parts(S3, x, y, z, r, sy=1.0, n=9, m=5, floor=None):
    b = S3.ball(x, y, z, r, sy=sy, n=n, m=m, floor=floor)
    return [tuple(p) for p in b.v], [tuple(f) for f in b.f]


def _wall(p0, p1, H, holes, inward):
    """one wall face from p0 to p1 (x, z) and 0..H high, cut by holes [(u0, u1, v0, v1) metres along / up], as a grid
    of tiles that share their corners (only the outline and the holes are inked). inward: which side it faces"""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    us = sorted({0.0, L} | {h[0] for h in holes} | {h[1] for h in holes})
    vs = sorted({0.0, H} | {h[2] for h in holes} | {h[3] for h in holes})
    d = (p1 - p0) / max(L, 1e-6)
    V = [(p0[0] + d[0] * u, v, p0[1] + d[1] * u) for v in vs for u in us]
    F = []
    nu = len(us)
    for j in range(len(vs) - 1):
        for i in range(nu - 1):
            cu, cv = (us[i] + us[i + 1]) / 2, (vs[j] + vs[j + 1]) / 2
            if any(h[0] <= cu <= h[1] and h[2] <= cv <= h[3] for h in holes):
                continue
            a = j * nu + i
            f = (a, a + 1, a + nu + 1, a + nu)
            F.append(f if inward else tuple(reversed(f)))
    return V, F


def house_shell(S3, w, hx, hz, W_=8.0, D_=5.5, H_=3.0):
    """a house you can go into: four walls with a door and windows - an outer face and an inner face (0.25 m apart),
    the clay-tiled roof, and a ceiling under it. Its meshes are marked shell; w.house holds its footprint"""
    M, Mesh = S3.M, S3.Mesh
    x0, x1, z0, z1, H = hx - W_ / 2 * M, hx + W_ / 2 * M, hz - D_ / 2 * M, hz + D_ / 2 * M, H_ * M
    t = 0.25 * M
    door = (2.5 * M - 0.55 * M, 2.5 * M + 0.55 * M, 0.0, 2.0 * M)       # front wall, measured from its left end x0
    fw = [door, (4.8 * M, 5.6 * M, 1.0 * M, 1.9 * M), (6.4 * M, 7.2 * M, 1.0 * M, 1.9 * M)]
    bw = [(1.6 * M, 2.8 * M, 1.0 * M, 2.1 * M), (5.2 * M, 6.4 * M, 1.0 * M, 2.1 * M)]
    sw = [(2.2 * M, 3.3 * M, 1.0 * M, 2.0 * M)]
    walls = (((x0, z0), (x1, z0), fw), ((x1, z1), (x0, z1), bw), ((x1, z0), (x1, z1), sw), ((x0, z1), (x0, z0), sw))
    outer, inner = [], []
    for (a, b, holes) in walls:
        outer.append(_wall(a, b, H, holes, inward=False))
        a_, b_ = np.array(a, float), np.array(b, float)
        dd = (b_ - a_) / np.linalg.norm(b_ - a_)
        n_in = np.array([-dd[1], dd[0]])                               # (the room is to the left going a -> b)
        inner.append(_wall(tuple(a_ + n_in * t), tuple(b_ + n_in * t), H, holes, inward=True))
    for parts, nm in ((outer, "limewall"), (inner, "limewall_in")):
        m = merged(parts, Mesh, ink=0.8, name=nm)
        m.shell = True
        w.append(m)
    sill = []                                                          # the thickness round the door and windows
    for (a, b, holes) in walls:
        a_, b_ = np.array(a, float), np.array(b, float)
        dd = (b_ - a_) / np.linalg.norm(b_ - a_)
        n_in = np.array([-dd[1], dd[0]])
        for u0, u1, v0, v1 in holes:
            for u in (u0, u1):
                p = a_ + dd * u
                sill.append(sheet_parts([(p[0], v0, p[1]), (p[0] + n_in[0] * t, v0, p[1] + n_in[1] * t),
                                         (p[0] + n_in[0] * t, v1, p[1] + n_in[1] * t), (p[0], v1, p[1])]))
            for v in ((v0, v1) if v0 > 0 else (v1,)):
                pa, pb = a_ + dd * u0, a_ + dd * u1
                sill.append(sheet_parts([(pa[0], v, pa[1]), (pb[0], v, pb[1]), (pb[0] + n_in[0] * t, v, pb[1] + n_in[1] * t),
                                         (pa[0] + n_in[0] * t, v, pa[1] + n_in[1] * t)]))
    m = merged(sill, Mesh, ink=0.6, name="limewall")
    m.shell = True
    w.append(m)
    r = S3.roof(hx, H, hz, W_ * M, 2.0 * M, D_ * M, over=0.5 * M, name="tiles")
    r.shell = True
    w.append(r)
    c = merged([grid_sheet((x0 + t, H - 2, z0 + t), (x1 - x0 - 2 * t, 0, 0), (0, 0, z1 - z0 - 2 * t), 6, 5)],
               Mesh, ink=0.5, name="ceiling_wood")                    # (faces down: seen from the room)
    c.shell = True
    w.append(c)
    fl = merged([grid_sheet((x1 - t, 1.2, z0 + t), (-(x1 - x0 - 2 * t), 0, 0), (0, 0, z1 - z0 - 2 * t), 14, 10)],
                Mesh, ink=0.5, name="redfloor")                        # (tiles: still drawn when the camera stands on it)
    fl.inside = True
    w.append(fl)
    w.house = (x0, x1, z0, z1, H)


def office_inside(S3, w, hx, hz):
    """Deepak's office inside the farmhouse (marked inside): the desk against the back wall with two monitors and a
    laptop, his chair at sitting height, the station map on the left wall, shelves of stations on the right, the
    ceiling fan, and the steel hatch standing open over the way down (the future underground)"""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    n0 = len(w)
    zb = hz + 2.5 * M
    dz = zb - 0.5 * M
    dx0 = hx + 0.6 * M
    w.append(box(dx0, 0.75 * M, dz, 2.8 * M, 0.08 * M, 0.8 * M, name="bench"))
    for dx in (-1.25, 1.25):
        w.append(box(dx0 + dx * M, 0, dz, 0.08 * M, 0.75 * M, 0.7 * M, ink=0.7, name="bench"))
    for k, (mx, ang) in enumerate(((-0.55, 0.18), (0.55, -0.18))):
        cx_, cy_, hw, hh = dx0 + mx * M, 1.3 * M, 0.45 * M, 0.3 * M
        dzz = math.sin(ang) * hw
        z_ = dz - 0.05 * M
        w.append(merged([sheet_parts([(cx_ - hw * math.cos(ang), cy_ - hh, z_ - dzz), (cx_ + hw * math.cos(ang), cy_ - hh, z_ + dzz),
                                      (cx_ + hw * math.cos(ang), cy_ + hh, z_ + dzz), (cx_ - hw * math.cos(ang), cy_ + hh, z_ - dzz)])],
                        Mesh, ink=0.9, name=("monitor_map", "monitor_graph")[k]))
    w.append(box(dx0, 0.83 * M, dz - 0.35 * M, 0.8 * M, 0.03 * M, 0.25 * M, ink=0.7, name="laptop"))
    w.append(box(dx0, 0.36 * M, dz - 1.2 * M, 0.55 * M, 0.08 * M, 0.55 * M, ink=0.7, name="chair"))
    w.append(box(dx0, 0.44 * M, dz - 1.5 * M, 0.55 * M, 0.7 * M, 0.06 * M, ink=0.7, name="chair"))
    w.append(merged([rod_parts((dx0, 0, dz - 1.2 * M), (dx0, 0.36 * M, dz - 1.2 * M), 0.07 * M)], Mesh, ink=0.7, name="steel"))
    xl = hx + 4.0 * M - 0.3 * M                                        # the left wall's inner face (screen left)
    for j in range(3):
        y = (0.5 + 0.65 * j) * M
        w.append(box(xl - 0.25 * M, y, hz + 0.6 * M, 0.45 * M, 0.05 * M, 2.0 * M, ink=0.7, name="bench"))
        for k in range(3):
            w.append(box(xl - 0.25 * M, y + 0.05 * M, hz + (-0.1 + 0.7 * k) * M, 0.3 * M, 0.35 * M, 0.3 * M, ink=0.7,
                         name="station"))
    xr = hx - 4.0 * M + 0.3 * M                                        # the station map on the right wall's inner face
    mxw = xr + 0.02 * M
    w.append(merged([([(mxw, 1.0 * M, hz - 0.2 * M), (mxw, 1.0 * M, hz + 2.0 * M), (mxw, 2.3 * M, hz + 2.0 * M),
                       (mxw, 2.3 * M, hz - 0.2 * M)], [(3, 2, 1, 0)])], Mesh, ink=0.9, name="whiteboard"))
    w[-1].wall_item = True
    outline = [(0.0, 0.3), (0.4, 0.75), (1.0, 0.95), (1.6, 0.7), (2.0, 0.5), (1.7, 0.15), (1.1, 0.05), (0.4, 0.0)]
    pts = [(mxw + 0.03 * M, (1.15 + y * 1.0) * M, hz + (-0.1 + x) * M) for x, y in outline]
    n_ = len(pts)
    cx_ = tuple(np.mean(np.array(pts), axis=0))
    w.append(merged([(pts + [cx_], [(n_, i, (i + 1) % n_) for i in range(n_)])], Mesh, ink=0.0, name="map_land"))
    fan = [rod_parts((hx, 3.0 * M, hz), (hx, 2.6 * M, hz), 0.05 * M), disk_parts((hx, 2.58 * M, hz), (0, 1, 0), 0.16 * M, 0.08 * M, n=8)]
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.3
        ca, sa = math.cos(a), math.sin(a)
        fan.append(sheet_parts([(hx + ca * 0.14 * M - sa * 0.07 * M, 2.57 * M, hz + sa * 0.14 * M + ca * 0.07 * M),
                                (hx + ca * 0.9 * M - sa * 0.11 * M, 2.55 * M, hz + sa * 0.9 * M + ca * 0.11 * M),
                                (hx + ca * 0.9 * M + sa * 0.11 * M, 2.55 * M, hz + sa * 0.9 * M - ca * 0.11 * M),
                                (hx + ca * 0.14 * M + sa * 0.07 * M, 2.57 * M, hz + sa * 0.14 * M - ca * 0.07 * M)]))
    w.append(merged(fan, Mesh, ink=0.8, name="fan"))
    hx2, hz2 = hx - 2.6 * M, hz - 0.9 * M                              # the hatch over the way down
    hole = merged([([(hx2 - 0.6 * M, 1.6, hz2 - 0.7 * M), (hx2 + 0.6 * M, 1.6, hz2 - 0.7 * M), (hx2 + 0.6 * M, 1.6, hz2 + 0.7 * M),
                     (hx2 - 0.6 * M, 1.6, hz2 + 0.7 * M)], [(3, 2, 1, 0)])], Mesh, ink=0.9, name="hole")
    w.append(hole)
    w.append(box(hx2, 0, hz2 - 0.75 * M, 1.35 * M, 0.1 * M, 0.1 * M, ink=0.8, name="steel"))
    w.append(box(hx2, 0, hz2 + 0.75 * M, 1.35 * M, 0.1 * M, 0.1 * M, ink=0.8, name="steel"))
    w.append(merged([sheet_parts([(hx2 - 0.6 * M, 0.1 * M, hz2 + 0.75 * M), (hx2 + 0.6 * M, 0.1 * M, hz2 + 0.75 * M),
                                  (hx2 + 0.6 * M, 1.45 * M, hz2 + 1.05 * M), (hx2 - 0.6 * M, 1.45 * M, hz2 + 1.05 * M)])],
                    Mesh, ink=0.9, name="hatch"))
    for m in w[n0:]:
        m.inside = True


def farm_2026(S3):
    """a green family farm near Bhopal, 2026 (before the sun turned): beds of cabbages and tomatoes in grass all
    round, a sandy path winding back, a bamboo fence, a lime-plastered brick farmhouse with a clay-tiled roof and a
    verandah, a charpai and a tulsi in the yard, a thatched cow shed and haystacks, the tube well and its water
    channel, mango and neem trees, a line of woods, green rolling hills, blue mountains and white clouds"""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    rng = random.Random(2031)
    w = World()
    w.sky = (0.70, 0.88, 0.96)
    w.sky_top = (0.42, 0.72, 0.90)
    w.ground = (0.56, 0.74, 0.34)
    w.clouds = [(-0.55, 0.30, 1.0), (0.10, 0.36, 1.3), (0.50, 0.26, 0.9), (0.85, 0.32, 0.8), (-0.95, 0.22, 0.7)]
    cz = 450.0
    # the sandy path: from the front, winding back to the house (flat on the ground)
    pts = [(-0.5, -6), (0.5, 0), (-0.5, 5), (-2.5, 10), (-4.5, 15), (-6.0, 19)]
    path = []
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        wd = 1.3
        path.append(([(x0 * M - wd * M, 0.6, cz + z0 * M), (x0 * M + wd * M, 0.6, cz + z0 * M),
                      (x1 * M + wd * M, 0.6, cz + z1 * M), (x1 * M - wd * M, 0.6, cz + z1 * M)], [(3, 2, 1, 0)]))
    m = merged(path, Mesh, ink=0.3, name="sand")
    m.under = True
    w.append(m)
    beds = []                                                          # the beds: dark soil under the plants
    for bx0, bx1, bz0, bz1 in ((-9.5, -2.5, 3.0, 9.0), (-17, -10.5, 3.0, 10.0)):
        beds.append(([(bx0 * M, 0.7, cz + bz0 * M), (bx1 * M, 0.7, cz + bz0 * M), (bx1 * M, 0.7, cz + bz1 * M),
                      (bx0 * M, 0.7, cz + bz1 * M)], [(3, 2, 1, 0)]))
    m = merged(beds, Mesh, ink=0.4, name="soil")
    m.under = True
    w.append(m)
    cab = []                                                           # cabbages in rows
    for row in range(4):
        for k in range(6):
            x = (-9.0 + k * 1.2 + rng.uniform(-0.1, 0.1)) * M
            z = cz + (3.8 + row * 1.4) * M
            cab.append(_ball_parts(S3, x, 0, z, 0.55 * M, sy=0.8, floor=0.0))
    w.append(merged(cab, Mesh, ink=0.6, smooth=True, name="cabbage"))
    tom = []                                                           # a second bed of leafy plants
    for row in range(4):
        for k in range(5):
            x = (-16.3 + k * 1.3) * M
            z = cz + (3.8 + row * 1.6) * M
            tom.append(_ball_parts(S3, x, 0, z, 0.5 * M, sy=1.1, n=7, m=4, floor=0.0))
    w.append(merged(tom, Mesh, ink=0.5, smooth=True, name="leaf"))
    # a bamboo fence (two thin rails on posts) across the farm, and along the front right
    fence = []

    def bamboo_fence(x0, z0, x1, z1, n):
        for k in range(n + 1):
            u = k / n
            x, z = x0 + (x1 - x0) * u, z0 + (z1 - z0) * u
            fence.append(rod_parts((x, 0, z), (x, 1.2 * M, z), 0.1 * M))
        for hgt in (0.5, 1.0):
            fence.append(rod_parts((x0, hgt * M, z0), (x1, hgt * M, z1), 0.06 * M))

    bamboo_fence(-26 * M, cz + 12.5 * M, -7.5 * M, cz + 12.5 * M, 10)
    bamboo_fence(-2.5 * M, cz + 12.5 * M, 26 * M, cz + 12.5 * M, 14)
    bamboo_fence(-12 * M, cz - 1.0 * M, -20 * M, cz + 2.0 * M, 4)
    w.append(merged(fence, Mesh, ink=0.7, name="bamboo"))
    # the farmhouse - a real house you can walk into: walls with a door and windows (outer and inner faces), a
    # clay-tiled roof with a ceiling under it, a verandah, a courtyard wall; inside, Deepak's office (see below)
    hx, hz = -10.0 * M, cz + 21.0 * M
    house_shell(S3, w, hx, hz)
    ver = [rod_parts((hx + dx * M, 0, hz - 4.6 * M), (hx + dx * M, 2.3 * M, hz - 4.6 * M), 0.14 * M) for dx in (-3.8, -0.5, 3.0)]
    ver.append(sheet_parts([(hx - 4.1 * M, 2.3 * M, hz - 4.9 * M), (hx + 3.3 * M, 2.3 * M, hz - 4.9 * M),
                            (hx + 3.3 * M, 2.9 * M, hz - 2.75 * M), (hx - 4.1 * M, 2.9 * M, hz - 2.75 * M)]))
    w.append(merged(ver[:-1], Mesh, ink=0.8, name="wood"))
    w.append(merged([ver[-1]], Mesh, ink=0.8, name="tiles"))
    w.append(box(hx - 0.4 * M, 0, hz - 3.8 * M, 7.6 * M, 0.2 * M, 2.1 * M, ink=0.7, name="limewall"))  # the verandah floor
    for dx, ww in ((-7.2, 6.0), (7.0, 5.0)):                           # the courtyard wall either side
        w.append(box(hx + dx * M, 0, hz - 1.0 * M, ww * M, 1.4 * M, 0.3 * M, ink=0.7, name="limewall"))
    office_inside(S3, w, hx, hz)
    # the gate in the bamboo fence where the path comes through
    gate = [rod_parts((gx * M, 0, cz + 12.5 * M), (gx * M, 1.6 * M, cz + 12.5 * M), 0.18 * M) for gx in (-7.5, -2.5)]
    for gx, sgn in ((-7.5, 1), (-2.5, -1)):                            # two gate leaves, swung open
        x0, z0 = gx * M, cz + 12.5 * M
        x1, z1 = x0 + sgn * 1.4 * M, z0 - 1.6 * M
        for hgt in (0.35, 0.8, 1.25):
            gate.append(rod_parts((x0, hgt * M, z0), (x1, hgt * M, z1), 0.07 * M))
        gate.append(rod_parts((x1, 0.2 * M, z1), (x1, 1.35 * M, z1), 0.08 * M))
    w.append(merged(gate, Mesh, ink=0.8, name="bamboo"))
    tx_, tz_ = hx - 6.5 * M, hz - 2.0 * M                              # the toilet hut beside the house (brick, a tin
    w.append(box(tx_, 0, tz_, 1.5 * M, 2.2 * M, 1.5 * M, ink=0.8, name="brick"))   # roof, a wooden door, a bucket)
    w.append(box(tx_, 2.2 * M, tz_, 1.8 * M, 0.08 * M, 1.8 * M, ink=0.7, name="tinroof"))
    w.append(S3.panel(tx_, 0.05 * M, tz_ - 0.76 * M, 0.8 * M, 1.8 * M, ink=0.8, name="wood"))
    w.append(S3.cylinder(tx_ + 1.1 * M, 0, tz_ - 0.5 * M, 0.22 * M, 0.35 * M, n=10, name="water"))
    w.spots = {"toilet": (tx_, tz_ - 1.9 * M),
               "gate": (-5.0 * M, cz + 11.5 * M), "path": (-0.5 * M, cz + 2.0 * M), "field": (-6.0 * M, cz + 6.0 * M),
               "yard": (-6.0 * M, cz + 15.5 * M), "porch": (hx - 0.5 * M, hz - 3.9 * M), "door": (hx - 1.5 * M, hz - 3.2 * M),
               "inside": (hx, hz), "room": (hx, hz - 1.73 * M), "desk": (hx + 0.6 * M, hz + 1.2 * M), "hatch": (hx - 2.6 * M, hz - 0.9 * M),
               "well": (5.5 * M - 2.5 * M, cz + 15.5 * M), "shed": (12.0 * M, cz + 19.0 * M)}
    w.shots = {   # named cameras: (eye, look-at) in world units
        "farm_wide": ((2.5 * M, 2.0 * M, cz - 7.0 * M), (-3.0 * M, 2.9 * M, cz + 30.0 * M)),
        "from_gate": ((-4.5 * M, 1.6 * M, cz + 9.0 * M), (hx, 1.6 * M, hz)),
        "through_window": ((hx + 1.4 * M, 1.6 * M, hz - 4.0 * M), (hx + 2.2 * M, 1.3 * M, hz + 2.5 * M)),
        "window_out": ((hx + 2.2 * M, 1.6 * M, hz + 1.5 * M), (-4.5 * M, 1.2 * M, cz + 10.0 * M)),
        "inside_wide": ((hx + 3.4 * M, 2.2 * M, hz - 2.2 * M), (hx - 1.0 * M, 1.0 * M, hz + 1.5 * M)),
        "desk": ((hx - 1.6 * M, 1.5 * M, hz - 0.6 * M), (hx + 0.6 * M, 1.1 * M, hz + 2.2 * M)),
        "hatch": ((hx - 0.6 * M, 2.2 * M, hz - 2.2 * M), (hx - 2.6 * M, 0.0, hz - 0.9 * M)),
        "toilet": ((tx_ - 4.0 * M, 1.6 * M, tz_ - 6.5 * M), (tx_ + 0.5 * M, 1.1 * M, tz_ - 0.5 * M)),
        "well": ((5.5 * M - 2.5 * M + 3.5 * M, 1.5 * M, cz + 15.5 * M - 5.0 * M), (5.5 * M - 2.5 * M, 1.0 * M, cz + 15.5 * M)),
    }
    n_tv = len(w)
    tvx, tvz = hx + 3.62 * M, hz - 1.75 * M                            # the TV on its cabinet by the right wall, a
    w.append(box(tvx - 0.15 * M, 0, tvz, 0.5 * M, 0.55 * M, 1.3 * M, ink=0.8, name="wood"))   # plastic chair
    w.append(box(tvx - 0.05 * M, 0.58 * M, tvz, 0.08 * M, 0.72 * M, 1.25 * M, ink=0.9, name="car_trim_dark"))
    w.append(Mesh(*sheet_parts([(tvx - 0.1 * M, 0.64 * M, tvz - 0.57 * M), (tvx - 0.1 * M, 0.64 * M, tvz + 0.57 * M),
                                (tvx - 0.1 * M, 1.24 * M, tvz + 0.57 * M), (tvx - 0.1 * M, 1.24 * M, tvz - 0.57 * M)]),
                  ink=0.4, name="tv_screen"))
    chx = hx + 1.8 * M                                                 # (facing the TV)
    w.append(box(chx, 0.42 * M, tvz, 0.5 * M, 0.06 * M, 0.5 * M, ink=0.7, name="chair"))
    w.append(box(chx - 0.25 * M, 0.42 * M, tvz, 0.06 * M, 0.5 * M, 0.5 * M, ink=0.7, name="chair"))
    for m in w[n_tv:]:                                                 # (inside the house: drawn in its room)
        m.inside = True
    w.spots["tv_seat"] = (chx, tvz)
    w.shots["tv"] = ((hx + 0.2 * M, 1.55 * M, tvz - 0.7 * M), (tvx, 0.95 * M, tvz + 0.2 * M))       # over his shoulder
    w.shots["tv_face"] = ((tvx - 0.9 * M, 1.15 * M, tvz - 0.25 * M), (chx, 1.05 * M, tvz))          # the TV's view of him
    w.shots["porch_door"] = ((hx - 1.5 * M, 1.6 * M, hz - 7.0 * M), (hx - 1.5 * M, 1.3 * M, hz - 3.2 * M))
    w.shots["gate_night"] = ((hx - 4.0 * M, 1.4 * M, hz - 4.6 * M), (-5.0 * M, 1.0 * M, cz + 11.0 * M))
    # a charpai in the yard, a tulsi pot on its stand
    kx, kz = -4.0 * M, cz + 15.5 * M
    w.append(box(kx, 0.45 * M, kz, 2.0 * M, 0.08 * M, 0.95 * M, name="cot"))
    for dx in (-0.95, 0.95):
        for dz in (-0.42, 0.42):
            w.append(box(kx + dx * M, 0, kz + dz * M, 0.07 * M, 0.45 * M, 0.07 * M, ink=0.8, name="cot_leg"))
    w.append(box(-14.5 * M, 0, cz + 16.0 * M, 0.9 * M, 0.9 * M, 0.9 * M, ink=0.7, name="limewall"))
    w.append(S3.ball(-14.5 * M, 1.2 * M, cz + 16.0 * M, 0.45 * M, sy=0.9, n=8, m=4, name="leaf"))
    # the cow shed: a thatched roof on poles, a haystack beside it, the tube well with its water channel
    sx, sz = 12.0 * M, cz + 22.0 * M
    w.append(merged([rod_parts((sx + dx * M, 0, sz + dz * M), (sx + dx * M, 2.4 * M, sz + dz * M), 0.14 * M)
                     for dx in (-2.5, 2.5) for dz in (-1.8, 1.8)], Mesh, ink=0.8, name="wood"))
    w.append(S3.pyramid(sx, 2.4 * M, sz, 6.2 * M, 1.8 * M, 4.6 * M, name="hut_roof"))
    for k in range(2):
        w.append(S3.ball(sx + (5.5 + 2.6 * k) * M, 0, sz + (0.5 - 1.2 * k) * M, 1.5 * M, sy=1.3, n=10, m=6, floor=0.0,
                         name="haystack"))
    px, pz = 5.5 * M, cz + 16.5 * M
    w.append(box(px, 0, pz, 1.6 * M, 1.6 * M, 1.4 * M, ink=0.8, name="limewall"))         # the pump room
    w.append(box(px, 1.6 * M, pz, 1.9 * M, 0.15 * M, 1.7 * M, ink=0.8, name="tiles"))
    w.append(merged([rod_parts((px - 0.8 * M, 0.9 * M, pz - 0.4 * M), (px - 1.6 * M, 0.9 * M, pz - 0.4 * M), 0.18 * M)],
                    Mesh, ink=0.8, name="steel"))                      # the outlet pipe
    ch = ([(px - 1.9 * M, 0.7, pz - 0.9 * M), (px - 1.4 * M, 0.7, pz - 0.9 * M), (-1.0 * M, 0.7, cz + 5.0 * M),
           (-1.6 * M, 0.7, cz + 5.0 * M)], [(3, 2, 1, 0)])
    pool = ([(px - 2.6 * M, 0.65, pz - 1.2 * M), (px - 1.0 * M, 0.65, pz - 1.2 * M), (px - 1.0 * M, 0.65, pz + 0.2 * M),
             (px - 2.6 * M, 0.65, pz + 0.2 * M)], [(3, 2, 1, 0)])
    m = merged([ch, pool], Mesh, ink=0.4, name="water")
    m.under = True
    w.append(m)

    def tree(x, z, s, dark=False):                                     # a big tree: trunk + a cluster of leaf balls
        w.append(merged([rod_parts((x, 0, z), (x + 0.3 * M * s, 4.0 * M * s, z), 0.55 * M * s),
                         rod_parts((x + 0.2 * M * s, 3.0 * M * s, z), (x + 1.6 * M * s, 4.6 * M * s, z), 0.3 * M * s),
                         rod_parts((x + 0.2 * M * s, 3.2 * M * s, z), (x - 1.4 * M * s, 4.8 * M * s, z), 0.3 * M * s)],
                        Mesh, ink=0.8, name="trunk"))
        parts = []
        for dx, dy, rr in ((0, 6.2, 2.6), (-2.0, 5.2, 1.9), (2.1, 5.4, 2.0), (-1.0, 7.4, 1.8), (1.2, 7.2, 1.7), (0.2, 4.6, 1.8)):
            parts.append(_ball_parts(S3, x + dx * M * s, dy * M * s, z + rng.uniform(-0.5, 0.5) * M * s, rr * M * s,
                                     sy=0.85, n=9, m=5))
        w.append(merged(parts, Mesh, ink=0.3, smooth=True, name="leaf_dark" if dark else "crown"))

    tree(16 * M, cz + 9 * M, 1.25, True)                               # a mango tree and a neem
    tree(-21 * M, cz + 7 * M, 1.1)
    tree(4 * M, cz + 26 * M, 0.9, True)
    tree(-20 * M, cz + 28 * M, 0.9, True)
    woods = []                                                         # the line of woods behind
    for k in range(26):
        x = (-70 + k * 5.4 + rng.uniform(-1.5, 1.5)) * M
        z = cz + rng.uniform(55, 70) * M
        rr = rng.uniform(2.6, 4.2) * M
        woods.append(_ball_parts(S3, x, rr * 0.9, z, rr, sy=1.1, n=8, m=5))
    w.append(merged(woods, Mesh, ink=0.35, smooth=True, name="leaf_dark"))
    hills = []                                                         # green rolling hills
    for k in range(7):
        x = (-130 + k * 42 + rng.uniform(-10, 10)) * M
        z = cz + rng.uniform(90, 130) * M
        hills.append(_ball_parts(S3, x, 0, z, rng.uniform(40, 60) * M, sy=0.28, n=12, m=6, floor=0.0))
    w.append(merged(hills, Mesh, ink=0.25, smooth=True, name="greenhill"))
    mts = []                                                           # blue mountains: soft rounded ranges
    for k in range(9):
        x = (-300 + k * 75 + rng.uniform(-25, 25)) * M
        z = cz + rng.uniform(380, 470) * M
        mts.append(_ball_parts(S3, x, 0, z, rng.uniform(80, 130) * M, sy=rng.uniform(0.55, 0.85), n=12, m=6, floor=0.0))
    w.append(merged(mts, Mesh, ink=0.25, smooth=True, name="mountain"))

    return w


def farmhouse_office(S3):
    """inside the farmhouse (farm_2026): Deepak's office for now - and the way down to the underground home the
    300 acres will hold. Lime-washed walls, a red-oxide floor, wooden beams under the ceiling and a ceiling fan,
    windows full of green fields, his desk with two monitors and a laptop at sitting height, the Madhya Pradesh
    station map on the wall, shelves of weather stations, and in the floor a steel hatch standing open over the
    stairs that go down. The front (camera side) is open."""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    w = World()
    w.sky = (0.94, 0.90, 0.80)
    w.ground = (0.66, 0.30, 0.24)                                      # red-oxide floor
    w.ceiling = 3.2 * M
    cz = 450.0
    zb = cz + 4.8 * M
    xl, xr = 6.0 * M, -6.0 * M
    zf = cz - 11.0 * M
    H_ = 3.2 * M
    w.append(merged([grid_sheet((xl, 0, zb), (xr - xl, 0, 0), (0, H_, 0), 6, 2)], Mesh, ink=0.6, name="limewall"))
    w.append(merged([grid_sheet((xl, 0, zf), (0, 0, zb - zf), (0, H_, 0), 16, 2)], Mesh, ink=0.6, name="limewall"))
    w.append(merged([grid_sheet((xr, 0, zb), (0, 0, zf - zb), (0, H_, 0), 16, 2)], Mesh, ink=0.6, name="limewall"))
    w.append(merged([grid_sheet((xr, H_, zf), (xl - xr, 0, 0), (0, 0, zb - zf), 6, 16)], Mesh, ink=0.4, name="ceiling_wood"))
    for m in w[-4:]:
        m.under = True
    beams = [rod_parts((xr, H_ - 0.12 * M, cz + k * 2.4 * M), (xl, H_ - 0.12 * M, cz + k * 2.4 * M), 0.22 * M)
             for k in range(-1, 3)]
    w.append(merged(beams, Mesh, ink=0.7, name="wood"))
    # the ceiling fan
    fx, fz = 0.0, cz + 0.8 * M
    fan = [rod_parts((fx, H_, fz), (fx, H_ - 0.6 * M, fz), 0.05 * M)]
    fan += [disk_parts((fx, H_ - 0.62 * M, fz), (0, 1, 0), 0.18 * M, 0.1 * M, n=8)]
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.3
        fan.append(sheet_parts([(fx + math.cos(a) * 0.15 * M - math.sin(a) * 0.08 * M, H_ - 0.62 * M, fz + math.sin(a) * 0.15 * M + math.cos(a) * 0.08 * M),
                                (fx + math.cos(a) * 1.0 * M - math.sin(a) * 0.12 * M, H_ - 0.64 * M, fz + math.sin(a) * 1.0 * M + math.cos(a) * 0.12 * M),
                                (fx + math.cos(a) * 1.0 * M + math.sin(a) * 0.12 * M, H_ - 0.64 * M, fz + math.sin(a) * 1.0 * M - math.cos(a) * 0.12 * M),
                                (fx + math.cos(a) * 0.15 * M + math.sin(a) * 0.08 * M, H_ - 0.62 * M, fz + math.sin(a) * 0.15 * M - math.cos(a) * 0.08 * M)]))
    w.append(merged(fan, Mesh, ink=0.8, name="fan"))
    # windows in the back wall: frames with the green fields outside
    for wx in (-3.6, 3.6):
        x0 = wx * M
        w.append(merged([([(x0 + 0.8 * M, 1.45 * M, zb - 2), (x0 - 0.8 * M, 1.45 * M, zb - 2), (x0 - 0.8 * M, 2.3 * M, zb - 2),
                            (x0 + 0.8 * M, 2.3 * M, zb - 2)], [(0, 1, 2, 3)])], Mesh, ink=0.9, name="window_view"))
        w.append(merged([([(x0 + 0.8 * M, 1.0 * M, zb - 2), (x0 - 0.8 * M, 1.0 * M, zb - 2), (x0 - 0.8 * M, 1.45 * M, zb - 2),
                            (x0 + 0.8 * M, 1.45 * M, zb - 2)], [(0, 1, 2, 3)])], Mesh, ink=0.9, name="window_field"))
        w[-1].under = w[-2].under = True                               # (the glass: drawn before its bars)
        bars = [rod_parts((x0 + dx * M, 1.0 * M, zb - 6), (x0 + dx * M, 2.3 * M, zb - 6), 0.04 * M) for dx in (-0.4, 0.0, 0.4)]
        bars.append(rod_parts((x0 - 0.8 * M, 1.65 * M, zb - 6), (x0 + 0.8 * M, 1.65 * M, zb - 6), 0.05 * M))
        w.append(merged(bars, Mesh, ink=0.7, name="steel"))
    # the desk against the back wall, between the windows: two monitors, a laptop, the chair at sitting height
    dz = zb - 0.5 * M
    w.append(box(0, 0.75 * M, dz, 3.4 * M, 0.08 * M, 0.9 * M, name="bench"))
    for dx in (-1.55, 1.55):
        w.append(box(dx * M, 0, dz, 0.08 * M, 0.75 * M, 0.8 * M, ink=0.7, name="bench"))
    for k, (mx, ang) in enumerate(((-0.6, 0.18), (0.6, -0.18))):
        cx_, cy_, hw, hh = mx * M, 1.33 * M, 0.5 * M, 0.32 * M
        dzz = math.sin(ang) * hw
        z_ = dz - 0.1 * M
        w.append(merged([sheet_parts([(cx_ - hw * math.cos(ang), cy_ - hh, z_ - dzz), (cx_ + hw * math.cos(ang), cy_ - hh, z_ + dzz),
                                      (cx_ + hw * math.cos(ang), cy_ + hh, z_ + dzz), (cx_ - hw * math.cos(ang), cy_ + hh, z_ - dzz)])],
                        Mesh, ink=0.9, name=("monitor_map", "monitor_graph")[k]))
        w.append(box(cx_, 0.83 * M, z_ + 0.15 * M, 0.08 * M, 0.2 * M, 0.08 * M, ink=0.7, name="laptop"))
    w.append(box(0, 0.83 * M, dz - 0.5 * M, 0.8 * M, 0.03 * M, 0.25 * M, ink=0.7, name="laptop"))
    w.append(box(1.2 * M, 0.83 * M, dz - 0.25 * M, 0.45 * M, 0.03 * M, 0.32 * M, ink=0.7, name="laptop"))
    w.append(merged([sheet_parts([(0.97 * M, 0.86 * M, dz - 0.1 * M), (1.43 * M, 0.86 * M, dz - 0.1 * M),
                                  (1.43 * M, 1.15 * M, dz - 0.02 * M), (0.97 * M, 1.15 * M, dz - 0.02 * M)])],
                    Mesh, ink=0.8, name="screen"))
    w.append(box(0, 0.36 * M, dz - 1.2 * M, 0.6 * M, 0.08 * M, 0.6 * M, ink=0.7, name="chair"))
    w.append(box(0, 0.44 * M, dz - 1.52 * M, 0.6 * M, 0.75 * M, 0.06 * M, ink=0.7, name="chair"))
    w.append(merged([rod_parts((0, 0, dz - 1.2 * M), (0, 0.36 * M, dz - 1.2 * M), 0.08 * M)], Mesh, ink=0.7, name="steel"))
    # the station map on the right wall (a big framed sheet with the state outline and dots), shelves on the left
    mxw = xr + 0.03 * M
    w.append(merged([([(mxw, 0.9 * M, cz - 1.0 * M), (mxw, 0.9 * M, cz + 2.4 * M), (mxw, 2.5 * M, cz + 2.4 * M),
                       (mxw, 2.5 * M, cz - 1.0 * M)], [(3, 2, 1, 0)])], Mesh, ink=0.9, name="whiteboard"))
    outline = [(0.0, 0.3), (0.5, 0.75), (1.4, 0.95), (2.3, 0.7), (3.0, 0.5), (2.6, 0.15), (1.6, 0.05), (0.6, 0.0)]
    pts = [(mxw + 0.02 * M, (1.1 + y * 1.2) * M, cz + (-0.8 + x) * M) for x, y in outline]
    cx_ = tuple(np.mean(np.array(pts), axis=0))                        # a fan from its middle (the outline is not
    n_ = len(pts)                                                      # convex: one face would face the wrong way)
    w.append(merged([(pts + [cx_], [(n_, i, (i + 1) % n_) for i in range(n_)])], Mesh, ink=0.0, name="map_land"))
    w[-2].under = True                                                 # (the map's sheet first, the land on it)
    dots = []
    for i in range(6):
        for j in range(3):
            dots.append(disk_parts((mxw + 0.05 * M, (1.35 + 0.28 * j) * M, cz + (-0.3 + 0.42 * i) * M), (1, 0, 0),
                                   0.05 * M, 0.02 * M, n=6))
    w.append(merged(dots, Mesh, ink=0.3, name="led_green"))
    for j in range(3):
        y = (0.5 + 0.7 * j) * M
        w.append(box(xl - 0.4 * M, y, cz + 1.2 * M, 0.5 * M, 0.06 * M, 2.6 * M, ink=0.7, name="bench"))
        for k in range(3):
            w.append(box(xl - 0.4 * M, y + 0.06 * M, cz + (0.3 + 0.9 * k) * M, 0.35 * M, 0.4 * M, 0.35 * M, ink=0.7,
                         name="station"))
    # the way down: a hole in the floor with a heavy steel hatch standing open, a railing, the first steps
    hx, hz = 3.2 * M, cz - 2.2 * M
    hole = ([(hx - 0.8 * M, 1.0, hz - 0.9 * M), (hx + 0.8 * M, 1.0, hz - 0.9 * M), (hx + 0.8 * M, 1.0, hz + 0.9 * M),
             (hx - 0.8 * M, 1.0, hz + 0.9 * M)], [(3, 2, 1, 0)])
    m = merged([hole], Mesh, ink=0.9, name="hole")
    m.under = True
    w.append(m)
    w.append(box(hx, 0, hz - 0.95 * M, 1.8 * M, 0.12 * M, 0.12 * M, ink=0.8, name="steel"))     # the frame
    w.append(box(hx, 0, hz + 0.95 * M, 1.8 * M, 0.12 * M, 0.12 * M, ink=0.8, name="steel"))
    w.append(merged([sheet_parts([(hx - 0.8 * M, 0.1 * M, hz + 0.95 * M), (hx + 0.8 * M, 0.1 * M, hz + 0.95 * M),
                                  (hx + 0.8 * M, 1.9 * M, hz + 1.3 * M), (hx - 0.8 * M, 1.9 * M, hz + 1.3 * M)])],
                    Mesh, ink=0.9, name="hatch"))                      # the lid, open, leaning back
    rail = [rod_parts((hx + 0.85 * M, 0, hz + dz_ * M), (hx + 0.85 * M, 1.0 * M, hz + dz_ * M), 0.05 * M) for dz_ in (-0.9, 0.9)]
    rail.append(rod_parts((hx + 0.85 * M, 1.0 * M, hz - 0.9 * M), (hx + 0.85 * M, 1.0 * M, hz + 0.9 * M), 0.05 * M))
    w.append(merged(rail, Mesh, ink=0.8, name="hatch"))
    return w


def meeting_room(S3):
    """a secure government meeting room in Delhi: panelled walls, a long table with chairs down both sides, a big
    screen on the back wall (maps and charts), a lectern beside it, tall windows on the right with the city outside,
    ceiling lights. The front (camera side) is open. The table runs back from the camera."""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    w = World()
    w.sky = (0.78, 0.84, 0.88)
    w.ground = (0.42, 0.36, 0.34)                                      # dark carpet
    w.ceiling = 3.4 * M
    cz = 450.0
    zb = cz + 7.0 * M
    xl, xr = 5.5 * M, -5.5 * M
    zf = cz - 12.0 * M
    H_ = 3.4 * M
    w.append(merged([grid_sheet((xl, 0, zb), (xr - xl, 0, 0), (0, H_, 0), 6, 2)], Mesh, ink=0.6, name="panel_wall"))
    w.append(merged([grid_sheet((xl, 0, zf), (0, 0, zb - zf), (0, H_, 0), 16, 2)], Mesh, ink=0.6, name="panel_wall"))
    rw = []                                                            # the right wall: tall windows between pillars
    for k in range(9):
        z0 = zf + (zb - zf) * k / 9
        z1 = zf + (zb - zf) * (k + 1) / 9
        rw.append(([(xr, 0, z1), (xr, 0, z0), (xr, 0.9 * M, z0), (xr, 0.9 * M, z1)], [(0, 1, 2, 3)]))
        rw.append(([(xr, 2.9 * M, z1), (xr, 2.9 * M, z0), (xr, H_, z0), (xr, H_, z1)], [(0, 1, 2, 3)]))
    w.append(merged(rw, Mesh, ink=0.6, name="panel_wall"))
    glass = merged([grid_sheet((xr + 2, 0.9 * M, zb), (0, 0, zf - zb), (0, 2.0 * M, 0), 9, 1)], Mesh, ink=0.2, name="city_sky")
    w.append(glass)
    w.append(merged([grid_sheet((xr, H_, zf), (xl - xr, 0, 0), (0, 0, zb - zf), 6, 16)], Mesh, ink=0.4, name="ceiling"))
    for m in w[-5:]:
        m.under = True
    mull = [rod_parts((xr + 3, 0.9 * M, zf + (zb - zf) * k / 9), (xr + 3, 2.9 * M, zf + (zb - zf) * k / 9), 0.12 * M) for k in range(10)]
    w.append(merged(mull, Mesh, ink=0.8, name="steel"))
    city = []                                                          # Delhi outside: towers seen through the glass
    rng = random.Random(110)
    for k in range(14):
        z = cz + rng.uniform(-10, 8) * M
        x = xr - rng.uniform(25, 60) * M
        h = rng.uniform(8, 30) * M
        city.append(S3.box(x, 0, z, rng.uniform(5, 9) * M, h, rng.uniform(5, 9) * M, ink=0.4, name="citytower"))
    w.extend(city)
    for k in range(3):                                                 # ceiling lights
        w.append(box(0, H_ - 0.08 * M, cz + (-2 + 3.0 * k) * M, 2.4 * M, 0.06 * M, 0.5 * M, ink=0.5, name="tube"))
    # the big screen on the back wall, its frame, and the lectern
    sz = zb - 0.06 * M
    w.append(box(0, 1.0 * M, sz - 0.05 * M, 5.0 * M, 2.1 * M, 0.08 * M, ink=0.9, name="laptop"))
    w.append(merged([([(2.35 * M, 1.1 * M, sz - 0.12 * M), (-2.35 * M, 1.1 * M, sz - 0.12 * M), (-2.35 * M, 3.0 * M, sz - 0.12 * M),
                       (2.35 * M, 3.0 * M, sz - 0.12 * M)], [(0, 1, 2, 3)])], Mesh, ink=0.9, name="bigscreen"))
    w[-1].under = w[-2].under = True                                   # (on the wall: drawn before what is on it)
    land = [(-1.6, 1.4), (-0.6, 2.6), (0.8, 2.75), (1.9, 2.3), (1.4, 1.5), (0.2, 1.25)]
    pts = [(x * M, y * M, sz - 0.16 * M) for x, y in land]
    n_ = len(pts)
    cx_ = tuple(np.mean(np.array(pts), axis=0))
    w.append(merged([(pts + [cx_], [(n_, i, (i + 1) % n_) for i in range(n_)])], Mesh, ink=0.0, name="map_land"))
    w.append(box(3.6 * M, 0, sz - 0.9 * M, 0.7 * M, 1.15 * M, 0.5 * M, ink=0.8, name="bench"))
    # the long table and the chairs down both sides
    tz0, tz1 = cz - 3.0 * M, cz + 4.5 * M
    w.append(box(0, 0.72 * M, (tz0 + tz1) / 2, 2.2 * M, 0.1 * M, tz1 - tz0, name="table_top"))
    w.append(box(0, 0, (tz0 + tz1) / 2, 1.2 * M, 0.72 * M, tz1 - tz0 - 1.0 * M, ink=0.7, name="table_base"))
    for k in range(5):
        z = tz0 + (0.8 + k * 1.5) * M
        for sx in (-1, 1):
            x = sx * 1.6 * M
            w.append(box(x, 0.36 * M, z, 0.55 * M, 0.08 * M, 0.55 * M, ink=0.7, name="chair"))
            w.append(box(x + sx * 0.3 * M, 0.44 * M, z, 0.06 * M, 0.75 * M, 0.55 * M, ink=0.7, name="chair"))
        w.append(box(-0.6 * M, 0.82 * M, z, 0.3 * M, 0.02 * M, 0.4 * M, ink=0.5, name="paper"))
        w.append(box(0.6 * M, 0.82 * M, z + 0.3 * M, 0.3 * M, 0.02 * M, 0.4 * M, ink=0.5, name="paper"))
    w.spots = {"front": (0.0, cz - 4.5 * M), "screen": (1.2 * M, zb - 1.6 * M), "table": (0.0, cz + 0.8 * M)}
    w.shots = {
        "room": ((-3.8 * M, 2.6 * M, cz - 7.5 * M), (0.6 * M, 1.2 * M, cz + 4.5 * M)),
        "screen": ((-0.9 * M, 1.9 * M, cz + 1.0 * M), (0.9 * M, 1.6 * M, zb)),
        "table": ((3.6 * M, 1.6 * M, cz - 4.5 * M), (-0.5 * M, 1.0 * M, cz + 2.5 * M)),
    }
    return w


# ------------------------------------------------------------------ the film's bigger places (Last Signal and on)
def _facade(S3, x0, x1, y0, y1, z, rng, lit=0.0, gap=3.0, ww=1.3, wh=1.6, name="bldg_win"):
    """the windows of a building front facing -z: a grid of dark panes (a few lit at night)"""
    M = S3.M
    parts, lit_parts = [], []
    nx = max(1, int((x1 - x0) / (gap * M)))
    ny = max(1, int((y1 - y0) / (gap * M)))
    for i in range(nx):
        for j in range(ny):
            cx = x0 + (i + 0.5) * (x1 - x0) / nx
            cy = y0 + (j + 0.5) * (y1 - y0) / ny
            v = [(cx - ww * M / 2, cy - wh * M / 2, z), (cx + ww * M / 2, cy - wh * M / 2, z),
                 (cx + ww * M / 2, cy + wh * M / 2, z), (cx - ww * M / 2, cy + wh * M / 2, z)]
            (lit_parts if rng.random() < lit else parts).append((v, [(0, 3, 2, 1)]))
    out = []
    if parts:
        out.append(merged(parts, S3.Mesh, ink=0.35, name=name))
    if lit_parts:
        out.append(merged(lit_parts, S3.Mesh, ink=0.35, name="win_lit"))
    return out


def _lamp(S3, x, z, h=7.0, toward=-1, name="lamp"):
    """a street lamp: a pole, an arm over the road, the lamp head"""
    M = S3.M
    out = [merged([rod_parts((x, 0, z), (x, h * M, z), 0.16 * M),
                   rod_parts((x, h * M, z), (x, h * M, z + toward * 1.6 * M), 0.1 * M)], S3.Mesh, ink=0.7,
                  name="lamppost")]
    out.append(S3.box(x, h * M - 0.18 * M, z + toward * 1.6 * M, 0.5 * M, 0.18 * M, 0.9 * M, ink=0.6, name=name))
    return out


def _road(S3, w, cz, half=4.0, length=90.0, dash=True, name="asphalt"):
    M = S3.M
    m = merged([grid_sheet((-length * M, 0.5, cz + half * M), (2 * length * M, 0, 0), (0, 0, -2 * half * M),
                           int(length / 3), 2)], S3.Mesh, ink=0.3, name=name)   # (in tiles: a long road stays
    #                                                                             drawn when it runs past the lens)
    m.under = True
    w.append(m)
    if dash:                                                           # the dashed centre line
        parts = []
        for k in range(int(-length / 6), int(length / 6)):
            x = k * 6.0 * M
            parts.append(([(x, 1.0, cz - 0.08 * M), (x + 3 * M, 1.0, cz - 0.08 * M), (x + 3 * M, 1.0, cz + 0.08 * M),
                           (x, 1.0, cz + 0.08 * M)], [(3, 2, 1, 0)]))
        m = merged(parts, S3.Mesh, ink=0.0, name="lane")
        m.under = True
        w.append(m)


def city_street(S3):
    """a street in New Delhi: a wide road with a dashed line, footpaths, office blocks with rows of windows, and the
    ministry - a long sandstone front with columns, steps and the flag - where the black cars pull up"""
    M, box = S3.M, S3.box
    rng = random.Random(1947)
    w = World()
    w.sky = (0.70, 0.82, 0.92)
    w.ground = (0.74, 0.72, 0.68)                                      # stone footpaths and paving
    cz = 450.0
    _road(S3, w, cz, half=5.0)
    zb = cz + 8.0 * M                                                  # where the buildings start (back side)
    x = -70.0 * M
    while x < 70 * M:                                                  # office blocks either side of the ministry
        wd = rng.uniform(9, 15) * M
        if abs(x + wd / 2) < 20 * M:
            x = 20 * M
            continue
        h = rng.uniform(12, 32) * M
        d = rng.uniform(10, 16) * M
        col = rng.choice(("bldg1", "bldg2", "bldg3", "bldg4"))
        w.append(box(x + wd / 2, 0, zb + d / 2, wd - 0.6 * M, h, d, ink=0.6, name=col))
        w.extend(_facade(S3, x + 1.0 * M, x + wd - 1.6 * M, 2.0 * M, h - 1.0 * M, zb - 2.0, rng, lit=0.15))
        x += wd
    mz = zb + 4.0 * M                                                  # the ministry: 36 m wide, 15 m high
    w.append(box(0, 0, mz + 7 * M, 36 * M, 15 * M, 14 * M, ink=0.7, name="ministry"))
    w.append(box(0, 15 * M, mz + 7 * M, 37 * M, 1.0 * M, 15 * M, ink=0.7, name="ministry_top"))
    w.extend(_facade(S3, -16 * M, 16 * M, 6.5 * M, 14 * M, mz - 2.0, rng, gap=3.4, ww=1.2, wh=2.0))
    for k in range(10):                                                # the colonnade
        cx = (-13.5 + k * 3.0) * M
        w.append(S3.cylinder(cx, 1.2 * M, mz - 2.2 * M, 0.45 * M, 4.6 * M, n=10, name="column"))
    w.append(box(0, 5.8 * M, mz - 2.2 * M, 30 * M, 0.8 * M, 1.6 * M, ink=0.7, name="ministry_top"))
    for s in range(3):                                                 # the steps up to the doors
        w.append(box(0, s * 0.4 * M, mz - 3.6 * M + s * 0.7 * M, 30 * M - s * 1.2 * M, 0.4 * M, 2.4 * M - s * 0.7 * M,
                     ink=0.6, name="steps"))
    w.append(S3.panel(0, 1.2 * M, mz - 0.02 * M, 3.2 * M, 4.0 * M, ink=0.8, name="door_dark"))
    fx, fz = 0.0, mz + 7 * M                                           # the flag on the roof
    w.append(merged([rod_parts((fx, 16 * M, fz), (fx, 24 * M, fz), 0.12 * M)], S3.Mesh, ink=0.7, name="lamppost"))
    for j, col in enumerate(("flag_saffron", "flag_white", "flag_green")):
        y0 = 23.4 * M - j * 0.6 * M
        w.append(S3.Mesh(*sheet_parts([(fx, y0 - 0.6 * M, fz), (fx + 2.7 * M, y0 - 0.6 * M, fz),
                                       (fx + 2.7 * M, y0, fz), (fx, y0, fz)]), ink=0.5, name=col))
    for k in range(-5, 6):                                             # lamps on both footpaths, neem trees behind
        w.extend(_lamp(S3, k * 14 * M, cz + 6.2 * M, toward=-1))
        w.extend(_lamp(S3, k * 14 * M + 7 * M, cz - 6.2 * M, toward=1))
        if abs(k) > 1:
            _tree(S3, w, k * 14 * M + 7 * M, cz + 6.8 * M, 0.9)
    for k in range(3):                                                 # a guard post and barriers at the gate
        w.append(box((-6 + k * 6) * M, 0, cz + 6.0 * M, 2.4 * M, 1.0 * M, 0.4 * M, ink=0.7, name="barrier"))
    w.spots = {"road": (0.0, cz), "steps": (0.0, mz - 5.6 * M), "footpath": (0.0, cz + 6.0 * M)}
    w.shots = {
        "street": ((-16 * M, 3.0 * M, cz - 16 * M), (0.0, 4.0 * M, cz + 8 * M)),
        "ministry": ((0.0, 1.2 * M, cz - 12 * M), (0.0, 8.0 * M, mz + 4 * M)),
        "steps": ((5 * M, 1.7 * M, cz + 1.5 * M), (0.0, 1.8 * M, mz - 3 * M)),
        "low": ((-4 * M, 0.45 * M, cz - 6 * M), (3 * M, 2.4 * M, cz + 5 * M)),
    }
    return w


def highway(S3):
    """a highway across the plains: two lanes with a dashed line, sandy shoulders, fields, street lamps every
    25 m, a green sign board, hills far off. Made for the night ("stick_time": "night") but works by day"""
    M, box = S3.M, S3.box
    rng = random.Random(44)
    w = World()
    w.sky = (0.62, 0.80, 0.94)
    w.ground = (0.58, 0.66, 0.38)
    cz = 450.0
    m = merged([grid_sheet((-120 * M, 0.3, cz + 5.5 * M), (240 * M, 0, 0), (0, 0, -11 * M), 40, 2)], S3.Mesh,
               ink=0.2, name="sand")
    m.under = True
    w.append(m)
    _road(S3, w, cz, half=3.6, length=120)
    for k in range(-5, 6):
        w.extend(_lamp(S3, k * 25 * M, cz + 5.0 * M, h=8.0, toward=-1))
    for row in range(6):                                               # fields beyond the road
        z = cz + (10 + row * 2.0) * M
        for seg in range(5):
            w.append(box((-60 + seg * 26) * M, 0, z, 22 * M, 0.5 * M, 0.8 * M, ink=0.3, name="crop"))
    for k in range(14):
        x = rng.uniform(-100, 100) * M
        z = cz + rng.choice((-1, 1)) * rng.uniform(9, 30) * M
        _tree(S3, w, x, z, rng.uniform(0.8, 1.2))
    sx = 18 * M                                                        # a green sign board
    w.append(merged([rod_parts((sx - 1.8 * M, 0, cz + 6.5 * M), (sx - 1.8 * M, 4.6 * M, cz + 6.5 * M), 0.14 * M),
                     rod_parts((sx + 1.8 * M, 0, cz + 6.5 * M), (sx + 1.8 * M, 4.6 * M, cz + 6.5 * M), 0.14 * M)],
                    S3.Mesh, ink=0.7, name="lamppost"))
    w.append(box(sx, 3.0 * M, cz + 6.4 * M, 4.6 * M, 2.0 * M, 0.12 * M, ink=0.8, name="sign_green"))
    _hills(S3, w, cz, rng)
    w.spots = {"road": (0.0, cz), "shoulder": (0.0, cz - 4.5 * M)}
    w.shots = {
        "roadside": ((-10 * M, 1.5 * M, cz - 10 * M), (6 * M, 1.0 * M, cz)),
        "reporter": ((1.2 * M, 1.6 * M, cz - 7.6 * M), (-0.2 * M, 1.4 * M, cz - 4.5 * M)),        # a TV news camera on
        "reporter_close": ((0.6 * M, 1.62 * M, cz - 6.4 * M), (-0.15 * M, 1.5 * M, cz - 4.5 * M)),  # the shoulder
        "low": ((0.0, 0.5 * M, cz - 5.5 * M), (0.0, 1.0 * M, cz + 3 * M)),
        "long": ((-34 * M, 2.2 * M, cz - 2.0 * M), (30 * M, 0.8 * M, cz)),
        "above": ((-6 * M, 14 * M, cz - 16 * M), (8 * M, 0.0, cz + 2 * M)),
    }
    return w


def site_2027(S3):
    """the underground home's building site (2027-2035): a stepped pit going down in benches of 4 m (the real dig
    goes 100 m down; we see its top levels and the tunnel mouth at the bottom), a tower crane, dump trucks on the
    ramps, floodlight masts, site cabins, a fence and gate"""
    M, box = S3.M, S3.box
    rng = random.Random(2035)
    w = World()
    w.sky = (0.72, 0.80, 0.88)
    w.ground = (0.80, 0.68, 0.48)                                      # dug, dusty earth
    cz = 450.0
    pcx, pcz = 0.0, cz + 20 * M                                        # the pit's centre
    hx, hz = 26 * M, 15 * M                                            # half size at the top
    lev, step, inset = 5, 4.0 * M, 3.0 * M
    for k in range(lev):                                               # the benches, top to bottom
        y0, y1 = -k * step, -(k + 1) * step
        ax, az = hx - k * inset, hz - k * inset
        bx, bz = ax - inset, az - inset
        q = lambda x, y, z: (pcx + x, y, pcz + z)
        walls = [sheet_parts([q(-ax, y0, az), q(ax, y0, az), q(ax, y1, az), q(-ax, y1, az)]),
                 sheet_parts([q(-ax, y0, -az), q(ax, y0, -az), q(ax, y1, -az), q(-ax, y1, -az)]),
                 sheet_parts([q(-ax, y0, -az), q(-ax, y0, az), q(-ax, y1, az), q(-ax, y1, -az)]),
                 sheet_parts([q(ax, y0, -az), q(ax, y0, az), q(ax, y1, az), q(ax, y1, -az)])]
        w.append(merged(walls, S3.Mesh, ink=0.5, name="pit_wall" if k % 2 == 0 else "pit_wall2"))
        if k < lev - 1:                                                # the bench (a ring of flat ground)
            ring = [sheet_parts([q(-ax, y1, az), q(ax, y1, az), q(bx, y1, bz), q(-bx, y1, bz)]),
                    sheet_parts([q(-ax, y1, -az), q(ax, y1, -az), q(bx, y1, -bz), q(-bx, y1, -bz)]),
                    sheet_parts([q(-ax, y1, -az), q(-ax, y1, az), q(-bx, y1, bz), q(-bx, y1, -bz)]),
                    sheet_parts([q(ax, y1, -az), q(ax, y1, az), q(bx, y1, bz), q(bx, y1, -bz)])]
            w.append(merged(ring, S3.Mesh, ink=0.35, name="pit_floor"))
    yb = -lev * step                                                   # the bottom and the tunnel mouth
    fx, fz = hx - (lev - 1) * inset, hz - (lev - 1) * inset
    w.append(S3.Mesh(*sheet_parts([(pcx - fx, yb, pcz - fz), (pcx + fx, yb, pcz - fz), (pcx + fx, yb, pcz + fz),
                                   (pcx - fx, yb, pcz + fz)]), ink=0.35, name="pit_floor"))
    tz = pcz + fz - 0.05 * M
    arch = [(pcx + 4.5 * M * math.cos(a), yb + 3.0 * M + 4.0 * M * math.sin(a), tz)
            for a in np.linspace(0, math.pi, 9)] + [(pcx - 4.5 * M, yb, tz), (pcx + 4.5 * M, yb, tz)]
    w.append(S3.Mesh(arch, [tuple(range(len(arch)))[::-1], tuple(range(len(arch)))], ink=0.8, name="tunnel"))
    for k in range(-2, 3):                                             # tunnel ribs
        w.append(box(pcx + k * 2.0 * M, yb, tz - 0.3 * M, 0.3 * M, 3.0 * M if abs(k) == 2 else 6.5 * M, 0.3 * M,
                     ink=0.6, name="concrete"))
    cx_, cz_ = pcx + hx + 5 * M, pcz + 4 * M                           # the tower crane
    w.append(box(cx_, 0, cz_, 1.8 * M, 34 * M, 1.8 * M, ink=0.7, name="crane"))
    w.append(box(cx_ - 14 * M, 34 * M, cz_, 46 * M, 1.2 * M, 1.4 * M, ink=0.7, name="crane"))
    w.append(box(cx_ + 6 * M, 31.5 * M, cz_, 4 * M, 2.5 * M, 2.2 * M, ink=0.7, name="concrete"))   # counterweight
    w.append(box(cx_ - 1.5 * M, 31.6 * M, cz_ - 1.6 * M, 2.0 * M, 2.2 * M, 1.6 * M, ink=0.7, name="cabin"))
    hook = cx_ - 26 * M
    w.append(merged([rod_parts((hook, 34 * M, cz_), (hook, 8 * M, cz_), 0.06 * M)], S3.Mesh, ink=0.6, name="lamppost"))
    w.append(box(hook, 6.4 * M, cz_, 3.0 * M, 1.6 * M, 3.0 * M, ink=0.7, name="concrete"))       # a load on the hook
    def machine(kind, x, y, z, hd, t=0.0):                             # the site's machines (stick3d machines),
        for m in S3.machine_meshes(f"site_{kind}{int(x)}", np.array([x, 0.0, z]), hd, kind, t):   # set on a bench
            m.v[:, 1] += y
            m.c[:, 1] += y
            m.center[1] += y
            w.append(m)
    machine("excavator", pcx - 3 * M, yb, pcz + fz - 6 * M, -0.4, 0.6)   # digging at the bottom, by the tunnel
    machine("dump_truck", pcx - 8 * M, -1 * step, pcz - hz + 1.5 * M, 0.0)
    machine("bulldozer", pcx + 7 * M, -2 * step, pcz - hz + 2 * inset + 1.5 * M, math.pi)
    machine("mixer", -10 * M, 0.0, cz - 2.5 * M, 0.0, 0.0)
    machine("loader", 14 * M, 0.0, pcz - hz - 4 * M, math.pi * 0.85, 0.5)
    hfx, hfz = pcx - hx - 7 * M, pcz - 6 * M                           # the headframe over the lift shaft (as at a
    legs = [(hfx + dx * M, hfz + dz * M) for dx in (-2.5, 2.5) for dz in (-2.5, 2.5)]   # mine): a steel lattice
    lat = [rod_parts((x, 0, z), (hfx + (x - hfx) * 0.3, 20 * M, hfz + (z - hfz) * 0.3), 0.3 * M) for x, z in legs]
    for k in range(5):
        y0, y1 = k * 4 * M, (k + 1) * 4 * M
        f0, f1 = 1 - 0.7 * y0 / (20 * M), 1 - 0.7 * y1 / (20 * M)
        lat.append(rod_parts((hfx - 2.5 * M * f0, y0, hfz - 2.5 * M * f0), (hfx + 2.5 * M * f1, y1, hfz - 2.5 * M * f1),
                             0.15 * M))
        lat.append(rod_parts((hfx + 2.5 * M * f0, y0, hfz - 2.5 * M * f0), (hfx - 2.5 * M * f1, y1, hfz - 2.5 * M * f1),
                             0.15 * M))
    w.append(merged(lat, S3.Mesh, ink=0.7, name="steel_rib"))
    v, f = disk_parts((hfx, 20.5 * M, hfz), (0, 0, 1), 2.0 * M, 0.4 * M, n=14)
    w.append(S3.Mesh(v, f, ink=0.8, name="mach_dark"))
    w.append(box(hfx, 0, hfz, 4.0 * M, 3.0 * M, 4.0 * M, ink=0.7, name="cabin"))                  # the winding house
    for k, sx_ in enumerate((42 * M, 48 * M)):                         # two silos on legs, a conveyor up to them
        w.append(S3.cylinder(sx_, 4 * M, pcz - 6 * M, 2.4 * M, 9 * M, n=12, name="silo"))
        w.append(S3.cylinder(sx_, 1.6 * M, pcz - 6 * M, 0.4 * M, 2.4 * M, n=12, top_r=2.4 * M, name="silo"))
        w.append(merged([rod_parts((sx_ + dx * M, 0, pcz - 6 * M + dz * M), (sx_ + dx * M, 4 * M, pcz - 6 * M + dz * M),
                                   0.2 * M) for dx in (-1.6, 1.6) for dz in (-1.6, 1.6)], S3.Mesh, ink=0.6,
                        name="steel_rib"))
    w.append(merged([rod_parts((pcx + hx + 1 * M, 0.5 * M, pcz - 6 * M), (40 * M, 13 * M, pcz - 6 * M), 0.6 * M)], S3.Mesh,
                    ink=0.7, name="mach_dark"))
    for k, (x_, h_) in enumerate(((34 * M, 3.0 * M), (54 * M, 4.0 * M))):   # heaps of dark rock from the tunnels
        w.append(S3.pyramid(x_, 0, pcz - 1 * M, 7 * M, h_, 6 * M, ink=0.5, name="ore"))
    for k in range(4):                                                 # floodlight masts at the corners
        mx = pcx + (-1 if k % 2 == 0 else 1) * (hx + 2.5 * M)
        mz = pcz + (-1 if k < 2 else 1) * (hz + 2.5 * M)
        w.append(merged([rod_parts((mx, 0, mz), (mx, 16 * M, mz), 0.3 * M)], S3.Mesh, ink=0.7, name="lamppost"))
        w.append(box(mx, 16 * M, mz, 3.0 * M, 1.4 * M, 0.5 * M, ink=0.7, name="lamp"))
    for k in range(3):                                                 # site cabins near the gate
        w.append(box((-26 + k * 6.5) * M, 0, cz - 3 * M, 6.0 * M, 2.7 * M, 2.5 * M, ink=0.8, name="cabin"))
        w.append(S3.panel((-26 + k * 6.5) * M, 0.9 * M, cz - 4.26 * M, 1.4 * M, 0.9 * M, ink=0.6, name="window_view"))
    for k in range(-12, 13):                                           # the fence along the front, a gate gap
        if abs(k) <= 1:
            continue
        w.append(box(k * 3.0 * M, 0, cz - 8 * M, 0.1 * M, 2.2 * M, 0.1 * M, ink=0.6, name="lamppost"))
    w.append(box(-20 * M, 1.8 * M, cz - 8 * M, 30 * M, 0.06 * M, 0.06 * M, ink=0.5, name="lamppost"))
    w.append(box(20 * M, 1.8 * M, cz - 8 * M, 30 * M, 0.06 * M, 0.06 * M, ink=0.5, name="lamppost"))
    for k in range(6):                                                 # mounds of dug earth
        w.append(S3.pyramid(rng.uniform(-40, 40) * M, 0, pcz + rng.uniform(19, 28) * M,               # (behind it)
                            rng.uniform(6, 10) * M, rng.uniform(2.5, 4.5) * M, rng.uniform(5, 8) * M, ink=0.4,
                            name="soil"))
    _hills(S3, w, cz, rng)
    w.spots = {"edge": (0.0, cz + 2.5 * M), "office": (-20 * M, cz - 5.5 * M), "gate": (0.0, cz - 10 * M)}
    w.shots = {
        "pit_wide": ((-30 * M, 16 * M, cz - 16 * M), (0.0, -6 * M, pcz)),
        "edge": ((7 * M, 1.8 * M, cz - 3 * M), (-2 * M, 1.4 * M, cz + 4 * M)),
        "down": ((0.0, 3.5 * M, cz + 3.5 * M), (0.0, -16 * M, pcz + 8 * M)),
        "crane": ((cx_ - 30 * M, 1.6 * M, cz - 9 * M), (cx_ - 10 * M, 20 * M, cz_)),
        "headframe": ((hfx + 14 * M, 2.0 * M, hfz - 16 * M), (hfx, 10 * M, hfz)),
        "silos": ((24 * M, 2.0 * M, cz - 10 * M), (42 * M, 6 * M, pcz - 6 * M)),
    }
    return w


def ruined_city(S3):
    """a city after the storms (the film's later chapters): broken towers with jagged tops and dark empty windows,
    rubble across a cracked road, burnt-out cars, dead trees, smoke, under a rust-red sky"""
    M, box = S3.M, S3.box
    rng = random.Random(2041)
    w = World()
    w.sky = (0.86, 0.56, 0.40)
    w.sky_top = (0.40, 0.22, 0.24)
    w.ground = (0.52, 0.48, 0.44)                                      # ash
    w.gear = True
    cz = 450.0
    _road(S3, w, cz, half=5.0, dash=False, name="asphalt_old")
    cracks = []                                                        # cracks across the road
    for k in range(18):
        x = rng.uniform(-40, 40) * M
        z = cz + rng.uniform(-4.5, 4.5) * M
        pts = [(x, 2.0, z)]
        for j in range(4):
            x += rng.uniform(0.6, 1.6) * M
            z += rng.uniform(-0.7, 0.7) * M
            pts.append((x, 2.0, z))
        for a, b in zip(pts, pts[1:]):
            cracks.append(([(a[0], 2.0, a[2] - 4), (b[0], 2.0, b[2] - 4), (b[0], 2.0, b[2] + 4), (a[0], 2.0, a[2] + 4)],
                           [(3, 2, 1, 0)]))
    m = merged(cracks, S3.Mesh, ink=0.0, name="crack")
    m.under = True
    w.append(m)
    for side in (1, -1):                                               # broken towers both sides of the road
        x = -70.0 * M
        while x < 70 * M:
            wd = rng.uniform(8, 14) * M
            h = rng.uniform(8, 28) * M
            zf = cz + side * 8 * M
            d = rng.uniform(9, 14) * M
            zc = zf + side * d / 2
            prof = [(x, 0.0), (x + wd, 0.0)]                           # the front's outline: a jagged broken top
            n_ = 6
            for j in range(n_ + 1):
                lo_ = 0.55 if 0 < j < n_ else 0.6
                prof.append((x + wd - j * wd / n_, h * rng.uniform(lo_, 1.0)))
            V = [(px, py, zc - d / 2) for px, py in prof] + [(px, py, zc + d / 2) for px, py in prof]
            n = len(prof)
            F = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
            for i in range(n):
                j = (i + 1) % n
                F.append((i, j, n + j, n + i))
            w.append(S3.Mesh(V, F, ink=0.7, name=rng.choice(("ruin", "ruin2", "ruin_dark"))))
            x += wd + rng.uniform(0, 3) * M
    for k in range(14):                                                # rubble heaps
        w.append(S3.pyramid(rng.uniform(-40, 40) * M, 0, cz + rng.uniform(-7, 7) * M, rng.uniform(2, 5) * M,
                            rng.uniform(0.8, 2.2) * M, rng.uniform(2, 4) * M, ink=0.5, name="rubble"))
    for k in range(10):                                                # broken slabs
        w.append(box(rng.uniform(-40, 40) * M, 0, cz + rng.uniform(-6.5, 6.5) * M, rng.uniform(1, 2.5) * M,
                     rng.uniform(0.2, 0.6) * M, rng.uniform(0.8, 2) * M, ink=0.6, name="concrete"))
    for k, (x, z, hd) in enumerate(((-9, -2.0, 0.3), (11, 2.2, 2.9), (24, -1.0, 1.4), (-22, 2.5, -0.4))):
        w.extend(S3.car_meshes(f"burnt{k}", np.array([x * M, 0.0, cz + z * M]), hd, (0.24, 0.20, 0.18), "car", 0.0))
    for k in range(8):                                                 # dead trees: a bare trunk and a few branches
        x, z = rng.uniform(-45, 45) * M, cz + rng.choice((-1, 1)) * rng.uniform(6.2, 7.0) * M
        br = [rod_parts((x, 0, z), (x, 3.6 * M, z), 0.22 * M)]
        for j in range(4):
            a = rng.uniform(0, 2 * math.pi)
            y = rng.uniform(1.8, 3.4) * M
            br.append(rod_parts((x, y, z), (x + math.cos(a) * 1.5 * M, y + 1.2 * M, z + math.sin(a) * 1.5 * M),
                                0.09 * M))
        w.append(merged(br, S3.Mesh, ink=0.7, name="deadtree"))
    for k in range(5):                                                 # smoke rising from the fires
        sx, sz = rng.uniform(-50, 50) * M, cz + rng.uniform(20, 40) * M
        for j in range(5):
            w.append(S3.ball(sx + j * 1.6 * M, (3 + j * 4.5) * M, sz, (2.0 + j * 1.2) * M, n=9, m=5, ink=0.2,
                             name="smoke"))
    _hills(S3, w, cz, rng, col="hill_dead")
    w.spots = {"street": (0.0, cz), "rubble": (8 * M, cz + 4 * M)}
    w.shots = {
        "ruins_wide": ((-20 * M, 5 * M, cz - 3 * M), (6 * M, 5 * M, cz + 6 * M)),
        "street_low": ((-6 * M, 0.5 * M, cz - 3.5 * M), (4 * M, 2.6 * M, cz + 6 * M)),
        "down_road": ((-34 * M, 2.0 * M, cz - 1 * M), (30 * M, 2.5 * M, cz)),
    }
    return w


def tunnel_2030(S3):
    """inside the underground works (a mine tunnel, as in the cut-away): a rock tunnel 6 m wide and 4.5 m high,
    open on the camera side like a stage, steel arches every 4 m, lamps along the roof, rails with ore carts, the
    tunnel boring machine at the far end (its cutter faces the rock) and the lift cage at the shaft end"""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    rng = random.Random(30)
    w = World()
    w.sky = (0.16, 0.14, 0.13)                                         # (no sky down here: dark rock)
    w.ground = (0.30, 0.26, 0.23)
    w.ceiling = 4.4 * M
    cz = 450.0
    z0, z1 = cz - 2.0 * M, cz + 4.0 * M                                # front (open) and back of the tunnel
    L = 40.0 * M
    arch = [(0.0, 3.0), (0.25, 3.8), (0.6, 4.3), (1.0, 4.45)]          # the roof curving from the back wall to the front
    seg = 8.0 * M
    for k in range(int(2 * L / seg)):                                  # in 8 m sections (each its own mesh, so the
        xa = -L + k * seg                                              # haze is right when one runs past the lens)
        fl = merged([grid_sheet((xa, 0.5, z1), (seg, 0, 0), (0, 0, z0 - z1), 4, 3)], Mesh, ink=0.2, name="gravel")
        fl.under = True
        w.append(fl)
        wall = merged([grid_sheet((xa, 0, z1), (0, 3.0 * M, 0), (seg, 0, 0), 2, 4)], Mesh, ink=0.3, name="rock")
        wall.under = True                                              # (the rock shell: drawn first, all else is
        w.append(wall)                                                 # inside it)
        parts = []
        for (a, ya), (b, yb) in zip(arch, arch[1:]):
            za, zb_ = z1 - a * (z1 - z0) * 0.6, z1 - b * (z1 - z0) * 0.6
            parts.append(grid_sheet((xa, ya * M, za), (0, (yb - ya) * M, zb_ - za), (seg, 0, 0), 1, 4))
        parts.append(grid_sheet((xa, 4.45 * M, z1 - 0.6 * (z1 - z0)), (0, 0, -0.4 * (z1 - z0)), (seg, 0, 0), 1, 4))
        roof_ = merged(parts, Mesh, ink=0.25, name="rock2")
        roof_.under = True
        w.append(roof_)
    for k in range(-9, 10):                                            # steel arches
        x = k * 4.0 * M
        pts = [(x, 0, z1 - 0.05 * M), (x, 3.0 * M, z1 - 0.05 * M)] + \
              [(x, (ya - 0.08) * M, z1 - a * (z1 - z0) * 0.6 - 0.05 * M) for a, ya in arch[1:]] + \
              [(x, 4.35 * M, z0 + 0.2 * M)]
        w.append(merged([rod_parts(p, q, 0.14 * M) for p, q in zip(pts, pts[1:])], Mesh, ink=0.6, name="steel_rib"))
        if k % 2 == 0:                                                 # a lamp on every other arch
            w.append(box(x + 2.0 * M, 4.2 * M, cz + 1.4 * M, 1.2 * M, 0.12 * M, 0.25 * M, ink=0.5, name="tube_light"))
    for zr in (cz + 0.6 * M, cz + 1.7 * M):                            # the rails and sleepers
        w.append(box(0, 0.12 * M, zr, 2 * L, 0.1 * M, 0.08 * M, ink=0.5, name="rail"))
    sl = [rod_parts((x * M, 0.06 * M, cz + 0.35 * M), (x * M, 0.06 * M, cz + 1.95 * M), 0.18 * M)
          for x in range(-39, 40)]
    w.append(merged(sl, Mesh, ink=0.3, name="sleeper"))
    for k in range(5):                                                 # a train of ore carts
        x = (-14 + k * 2.2) * M
        w.append(box(x, 0.35 * M, cz + 1.15 * M, 1.8 * M, 1.0 * M, 1.3 * M, ink=0.8, name="cart"))
        w.append(S3.pyramid(x, 1.35 * M, cz + 1.15 * M, 1.6 * M, 0.45 * M, 1.1 * M, ink=0.5, name="ore"))
        for wx in (-0.55, 0.55):
            for wz in (0.55, 1.75):
                v, f = disk_parts((x + wx * M, 0.25 * M, cz + wz * M), (0, 0, 1), 0.22 * M, 0.1 * M, n=8)
                w.append(Mesh(v, f, ink=0.6, name="mach_dark"))
    tx = 30 * M                                                        # the tunnel boring machine at the face
    for m in S3.machine_meshes("tbm_body", np.array([tx - 6 * M, 0.0, cz + 1.2 * M]), math.pi, "bulldozer", 0.0):
        w.append(m)
    v, f = disk_parts((tx, 2.2 * M, cz + 1.2 * M), (1, 0, 0), 2.1 * M, 0.5 * M, n=16)
    w.append(Mesh(v, f, ink=0.8, name="cutter"))
    for j in range(6):                                                 # the cutter's spokes
        a = j * math.pi / 3
        w.append(merged([rod_parts((tx - 0.3 * M, 2.2 * M, cz + 1.2 * M),
                                   (tx - 0.3 * M, 2.2 * M + 1.9 * M * math.sin(a), cz + 1.2 * M + 1.9 * M * math.cos(a)),
                                   0.18 * M)], Mesh, ink=0.6, name="mach_dark"))
    w.append(box(tx - 2.2 * M, 0.4 * M, cz + 1.2 * M, 3.6 * M, 3.2 * M, 3.4 * M, ink=0.8, name="mach_yellow"))
    w.append(box(tx + 1.2 * M, 0, cz + 1.0 * M, 1.0 * M, 4.4 * M, 6.2 * M, ink=0.4, name="rock"))   # the rock face
    lx = -32 * M                                                       # the lift cage at the shaft
    cage = [rod_parts((lx + dx * M, 0, cz + dz * M), (lx + dx * M, 4.4 * M, cz + dz * M), 0.12 * M)
            for dx in (-1.2, 1.2) for dz in (0.0, 2.6)]
    w.append(merged(cage, Mesh, ink=0.7, name="steel_rib"))
    w.append(box(lx, 0, cz + 1.3 * M, 2.3 * M, 2.6 * M, 2.5 * M, ink=0.8, name="cabin"))
    w.append(S3.panel(lx, 0.1 * M, cz + 0.04 * M, 1.6 * M, 2.2 * M, ink=0.7, name="tube_light"))
    for k in range(10):                                                # rocks along the back wall
        w.append(S3.ball(rng.uniform(-38, 38) * M, 0.2 * M, z1 - rng.uniform(0.3, 0.8) * M, rng.uniform(0.25, 0.6) * M,
                         sy=0.7, n=7, m=4, ink=0.4, name="rubble"))
    w.spots = {"tunnel": (0.0, cz - 0.8 * M), "face": (tx - 9 * M, cz - 0.8 * M), "lift": (lx + 4 * M, cz - 0.8 * M)}
    w.shots = {
        "tunnel": ((-12 * M, 2.4 * M, cz - 8 * M), (2 * M, 1.8 * M, cz + 2 * M)),
        "down_tunnel": ((-20 * M, 1.8 * M, cz - 0.5 * M), (10 * M, 1.6 * M, cz + 1.5 * M)),
        "face": ((tx - 14 * M, 2.0 * M, cz - 5 * M), (tx - 1 * M, 2.0 * M, cz + 1.5 * M)),
        "lift": ((lx + 9 * M, 1.8 * M, cz - 4.5 * M), (lx, 1.8 * M, cz + 1.5 * M)),
    }
    return w


def abroad_office(S3, where="texas"):
    """the other end of a phone call: a small research office abroad, open on the camera side like a stage. A desk
    in front of a big window (the person sits facing us with their country behind them), two monitors, a
    whiteboard of graphs, a shelf of binders, a door. where = "texas" (Mark: flat land, a water tower, wind
    turbines turning, a small US flag on the desk) or "panama" (Carlos: the sea, a ship, towers of the city)"""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    rng = random.Random(77 if where == "texas" else 507)
    w = World()
    w.sky = (0.72, 0.84, 0.94) if where == "texas" else (0.20, 0.24, 0.38)
    w.ground = (0.60, 0.52, 0.44) if where == "texas" else (0.36, 0.40, 0.46)
    w.ceiling = 3.0 * M
    cz = 450.0
    zb = cz + 3.5 * M
    xl, xr = 4.0 * M, -4.0 * M
    zf = cz - 6.0 * M
    H_ = 3.0 * M
    wall = "office_wall" if where == "texas" else "office_wall2"
    wx0, wx1, wy0, wy1 = -2.6 * M, 2.6 * M, 0.9 * M, 2.6 * M          # the window in the back wall
    back = [grid_sheet((xl, 0, zb), (xr - xl, 0, 0), (0, wy0, 0), 4, 1),
            grid_sheet((xl, wy1, zb), (xr - xl, 0, 0), (0, H_ - wy1, 0), 4, 1),
            grid_sheet((xl, wy0, zb), (wx1 - xl, 0, 0), (0, wy1 - wy0, 0), 1, 1),
            grid_sheet((wx0, wy0, zb), (xr - wx0, 0, 0), (0, wy1 - wy0, 0), 1, 1)]
    w.append(merged(back, Mesh, ink=0.5, name=wall))
    w.append(merged([grid_sheet((xl, 0, zf), (0, 0, zb - zf), (0, H_, 0), 6, 2)], Mesh, ink=0.5, name=wall))
    w.append(merged([grid_sheet((xr, 0, zb), (0, 0, zf - zb), (0, H_, 0), 6, 2)], Mesh, ink=0.5, name=wall))
    w.append(merged([grid_sheet((xr, H_, zf), (xl - xr, 0, 0), (0, 0, zb - zf), 4, 6)], Mesh, ink=0.4, name="ceiling"))
    for m in w[-4:]:
        m.under = True
    w.append(merged([rod_parts((x, wy0, zb - 3), (x, wy1, zb - 3), 0.1 * M) for x in (wx0, 0.0, wx1)] +
                    [rod_parts((wx0, y, zb - 3), (wx1, y, zb - 3), 0.1 * M) for y in (wy0, wy1)], Mesh, ink=0.7,
                    name="steel"))
    if where == "texas":                                               # outside: flat land, a water tower, turbines
        w.append(S3.cylinder(-14 * M, 9 * M, zb + 30 * M, 3.0 * M, 3.5 * M, n=12, name="silo"))
        w.append(merged([rod_parts((-14 * M + dx * M, 0, zb + 30 * M + dz * M), (-14 * M + dx * 0.6 * M, 9 * M,
                                                                                  zb + 30 * M + dz * 0.6 * M), 0.25 * M)
                         for dx in (-2, 2) for dz in (-2, 2)], Mesh, ink=0.6, name="steel"))
        for k, (x, z) in enumerate(((6 * M, zb + 60 * M), (16 * M, zb + 80 * M), (26 * M, zb + 70 * M))):
            w.append(merged([rod_parts((x, 0, z), (x, 22 * M, z), 0.6 * M)], Mesh, ink=0.5, name="turbine"))
            blades = []
            for j in range(3):                                         # (the blades are set at the hour: they turn
                a = j * 2 * math.pi / 3 + k                            # in the light of the window, not timed)
                blades.append(rod_parts((x, 22 * M, z - 0.8 * M),
                                        (x + 9 * M * math.cos(a), 22 * M + 9 * M * math.sin(a), z - 0.8 * M), 0.5 * M))
            w.append(merged(blades, Mesh, ink=0.5, name="turbine"))
        for k in range(6):
            w.append(box(rng.uniform(-30, 30) * M, 0, zb + rng.uniform(40, 90) * M, rng.uniform(6, 14) * M,
                         rng.uniform(2, 4) * M, 5 * M, ink=0.3, name="wall26"))
    else:                                                              # outside: the sea, a ship, the city at night
        sea = merged([grid_sheet((-80 * M, 0.3 * M, zb + 120 * M), (160 * M, 0, 0), (0, 0, -100 * M), 8, 4)], Mesh,
                     ink=0.0, name="sea_night")
        sea.under = True
        w.append(sea)
        for k in range(12):
            x = rng.uniform(-30, 30) * M
            h = rng.uniform(15, 55) * M
            z = zb + rng.uniform(15, 30) * M
            w.append(box(x, 0, z, rng.uniform(5, 9) * M, h, 6 * M, ink=0.4, name="citytower_n"))
            w.extend(_facade(S3, x - 2 * M, x + 2 * M, 2 * M, h - 2 * M, z - 3.0 * M - 2, rng, lit=0.5, gap=3.2,
                             ww=0.9, wh=1.0, name="bldg_win_n"))
        w.append(box(18 * M, 0.3 * M, zb + 70 * M, 22 * M, 3 * M, 4 * M, ink=0.5, name="ship"))
        w.append(box(22 * M, 3.3 * M, zb + 70 * M, 6 * M, 4 * M, 4 * M, ink=0.5, name="ship"))
    dz = zb - 1.3 * M                                                  # the desk, its chair, two monitors
    w.append(box(0.0, 0.74 * M, dz, 2.4 * M, 0.06 * M, 0.9 * M, ink=0.8, name="table_top"))
    for sx in (-1.1, 1.1):
        w.append(box(sx * M, 0, dz, 0.08 * M, 0.74 * M, 0.8 * M, ink=0.7, name="table_base"))
    w.append(box(0.0, 0.45 * M, zb - 0.55 * M, 0.55 * M, 0.08 * M, 0.55 * M, ink=0.7, name="chair"))
    w.append(box(0.0, 0.5 * M, zb - 0.3 * M, 0.55 * M, 0.8 * M, 0.08 * M, ink=0.7, name="chair"))
    for sx, ang in ((-1.0, 0.6), (1.0, -0.6)):                       # (at the desk's ends: the face stays clear)
        mx, mz_ = sx * M, dz + 0.1 * M
        w.append(box(mx, 0.8 * M, mz_, 0.1 * M, 0.16 * M, 0.1 * M, ink=0.6, name="steel"))
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(-0.26, 0.0), (0.26, 0.0), (0.26, 0.3), (-0.26, 0.3)]
        v = [(mx + px * M * ca, 0.95 * M + py * M, mz_ + px * M * sa) for px, py in pts]
        w.append(Mesh(v, [(0, 1, 2, 3), (3, 2, 1, 0)], ink=0.8, name="monitor_graph"))
    if where == "texas":                                               # a small flag on the desk
        fx, fz = -1.05 * M, dz - 0.2 * M
        w.append(merged([rod_parts((fx, 0.77 * M, fz), (fx, 1.12 * M, fz), 0.015 * M)], Mesh, ink=0.6, name="steel"))
        for j in range(5):
            y0 = 1.12 * M - j * 0.03 * M
            w.append(Mesh(*sheet_parts([(fx, y0 - 0.03 * M, fz), (fx - 0.2 * M, y0 - 0.03 * M, fz),
                                        (fx - 0.2 * M, y0, fz), (fx, y0, fz)]), ink=0.2,
                          name="flag_red" if j % 2 == 0 else "flag_white"))
        w.append(Mesh(*sheet_parts([(fx, 1.05 * M, fz - 1), (fx - 0.09 * M, 1.05 * M, fz - 1), (fx - 0.09 * M, 1.12 * M, fz - 1),
                                    (fx, 1.12 * M, fz - 1)]), ink=0.2, name="flag_blue"))
    wb = [((xl - 2, 1.0 * M, cz - 3.0 * M), (xl - 2, 1.0 * M, cz + 0.5 * M), (xl - 2, 2.2 * M, cz + 0.5 * M),
           (xl - 2, 2.2 * M, cz - 3.0 * M))]                           # the whiteboard and its graphs
    w.append(Mesh(list(wb[0]), [(0, 1, 2, 3), (3, 2, 1, 0)], ink=0.7, name="whiteboard"))
    for j in range(2):
        pts = [(xl - 4, (1.3 + 0.45 * j + 0.25 * math.sin(k * 0.9 + j)) * M, cz - 2.7 * M + k * 0.42 * M) for k in range(8)]
        w.append(merged([rod_parts(a, b, 0.03 * M) for a, b in zip(pts, pts[1:])], Mesh, ink=0.3,
                        name="flag_red" if j == 0 else "flag_blue"))
    w.append(box(xr + 0.25 * M, 1.2 * M, cz - 1.0 * M, 0.4 * M, 0.05 * M, 2.4 * M, ink=0.6, name="wood"))
    for k in range(9):                                                 # binders on a shelf
        w.append(box(xr + 0.25 * M, 1.25 * M, cz - 2.0 * M + k * 0.24 * M, 0.3 * M, 0.34 * M, 0.08 * M, ink=0.5,
                     name=rng.choice(("flag_red", "flag_blue", "barrier", "sign_green"))))
    w.append(S3.panel(xr + 3, 0, cz + 1.8 * M, 1.0 * M, 2.1 * M, ink=0.7, name="door_dark"))
    w.spots = {"desk": (0.0, zb - 0.55 * M), "room": (0.0, cz - 1.0 * M)}
    w.shots = {
        "desk": ((0.9 * M, 1.45 * M, zb - 3.6 * M), (0.0, 1.2 * M, zb - 0.5 * M)),
        "close": ((0.5 * M, 1.3 * M, zb - 2.3 * M), (0.0, 1.2 * M, zb - 0.5 * M)),
        "room": ((-2.6 * M, 1.9 * M, cz - 5.5 * M), (0.3 * M, 1.1 * M, zb - 1.0 * M)),
        "side": ((3.2 * M, 1.4 * M, zb - 2.0 * M), (-0.5 * M, 1.1 * M, zb - 0.6 * M)),
    }
    return w


def corn_field(S3):
    """a field of maize in late summer (as in the user's photo): a dirt track along the edge, a verge of dry grass,
    and the corn standing taller than a man (2.2-2.8 m) - the front row as single stalks with their long leaves and
    tassels, the rest of the field a dense green wall behind them. One of Deepak's stations stands on the verge.
    The camera can see over it from a drone ("aerial") or stand on the track."""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    rng = random.Random(1717)
    w = World()
    w.sky = (0.72, 0.82, 0.92)
    w.sky_top = (0.50, 0.64, 0.82)
    w.ground = (0.70, 0.62, 0.42)                                      # dry grass
    cz = 450.0
    zt = cz                                                            # the track's middle
    zc = cz + 2.6 * M                                                  # where the corn starts
    L = 90.0

    def strip(z_lo, z_hi, y, n=40):
        """a long flat band along the track (tiles, so it stays drawn when part of it is behind the lens)"""
        return grid_sheet((-L * M, y, z_hi), (2 * L * M, 0, 0), (0, 0, z_lo - z_hi), n, 1)
    trk = merged([grid_sheet((-L * M, 0.4, zt + 1.6 * M), (2 * L * M, 0, 0), (0, 0, -3.2 * M), 60, 2)], Mesh, ink=0.2,
                 name="mud_track")
    trk.under = True
    w.append(trk)
    seg = 6.0 * M                                                      # the corn behind the front row: a green wall
    for k in range(int(2 * L * M / seg)):                              # with a ragged top (sections, so the haze is
        x0 = -L * M + k * seg                                          # right near the lens)
        prof = [(x0, 0.0), (x0 + seg, 0.0)]
        for j in range(12, -1, -1):
            prof.append((x0 + j * seg / 12, rng.uniform(2.3, 2.9) * M))
        V = [(px, py, zc + 0.6 * M) for px, py in prof] + [(px, py, zc + 70 * M) for px, py in prof]
        n = len(prof)
        F = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            F.append((i, j, n + j, n + i))
        w.append(Mesh(V, F, ink=0.06, name="corn_dark"))                # (soft: from above it reads as one canopy)
    for k in range(int(2 * L / 4.0)):                                  # the front row: stalk by stalk, 4 m a mesh
        parts = []
        x0 = (-L + k * 4.0) * M
        for i in range(12):
            x = x0 + (i + rng.uniform(0.1, 0.9)) * 4.0 / 12 * M
            z = zc + rng.uniform(0.0, 0.5) * M
            h = rng.uniform(2.2, 2.8) * M
            lean = rng.uniform(-0.12, 0.12) * M
            parts.append(rod_parts((x, 0, z), (x + lean, h, z), 0.05 * M))
            for j in range(4):                                         # long leaves arching out from the stalk
                y = h * (0.3 + 0.16 * j)
                a = rng.uniform(0, 2 * math.pi)
                L_ = rng.uniform(0.6, 0.9) * M
                tip = (x + math.cos(a) * L_, y + rng.uniform(-0.25, 0.1) * M, z + math.sin(a) * L_ * 0.6)
                mid = (x + math.cos(a) * L_ * 0.5, y + 0.18 * M, z + math.sin(a) * L_ * 0.3)
                parts.append(([(x, y - 0.04 * M, z), (mid[0], mid[1] + 0.05 * M, mid[2]), tip,
                               (mid[0], mid[1] - 0.05 * M, mid[2])], [(0, 1, 2, 3), (3, 2, 1, 0)]))
            parts.append(rod_parts((x + lean, h, z), (x + lean, h + 0.3 * M, z), 0.03 * M))   # the tassel
        w.append(merged(parts, Mesh, ink=0.45, name="corn"))
    # the rain has turned the track to mud: two wheel ruts and puddles in them (they mirror the grey sky)
    ruts = []
    for zz in (zt - 0.78 * M, zt + 0.78 * M):
        ruts.append(strip(zz - 0.2 * M, zz + 0.2 * M, 0.7))
    ruts.append(strip(zt - 0.3 * M, zt + 0.3 * M, 0.75))             # grass on the hump between the ruts
    rm = merged(ruts[:2], Mesh, ink=0.0, name="rut")
    gm = merged(ruts[2:], Mesh, ink=0.0, name="grass_mid")
    gm.under = True
    w.append(gm)
    rm.under = True
    w.append(rm)
    w.puddles = []
    pr = random.Random(77)
    for k in range(34):
        x = pr.uniform(-40, 40) * M if k > 7 else (6.0 - 4.0 + pr.uniform(-5, 5)) * M   # most near the car stop
        z = zt + pr.choice((-0.78, 0.78, 0.1)) * M + pr.uniform(-0.15, 0.15) * M
        rx_, rz_ = pr.uniform(0.35, 1.1) * M, pr.uniform(0.18, 0.4) * M
        if k == 0:                                                     # the one right under the driver's door
            x, z, rx_, rz_ = 1.45 * M, zt - 1.1 * M, 0.8 * M, 0.32 * M
        elif k == 1:                                                   # and the one he steps into behind the car
            x, z, rx_, rz_ = -0.5 * M, zt - 1.45 * M, 0.7 * M, 0.3 * M
        pts = []
        for j in range(9):
            a = 2 * math.pi * j / 9
            q = pr.uniform(0.75, 1.15)
            pts.append((x + math.cos(a) * rx_ * q, 1.0, z + math.sin(a) * rz_ * q))
        rim = [(x + (px - x) * 1.22, 0.85, z + (pz - z) * 1.3) for px, _, pz in pts]   # wet dark mud round it
        rm_ = Mesh(rim, [tuple(range(9)), tuple(range(8, -1, -1))], ink=0.0, name="puddle_rim")
        rm_.under = True
        w.append(rm_)
        pm = Mesh(pts, [tuple(range(9)), tuple(range(8, -1, -1))], ink=0.0, name="puddle")
        pm.under = True
        w.append(pm)
        hl = [(x + (px - x) * 0.45 - rx_ * 0.2, 1.1, z + (pz - z) * 0.3) for px, _, pz in pts]   # the sky's shine
        hm = Mesh(hl, [tuple(range(9)), tuple(range(8, -1, -1))], ink=0.0, name="puddle_shine")
        hm.under = True
        w.append(hm)
        w.puddles.append((x, z, rx_, rz_))
    edges = []                                                         # the track's darker wet edges, and grass
    for zz in (zt - 1.45 * M, zt + 1.45 * M):                          # leaning in over them on both sides
        edges.append(strip(zz - 0.18 * M, zz + 0.18 * M, 0.6))
    em = merged(edges, Mesh, ink=0.0, name="mud_edge")
    em.under = True
    w.append(em)
    gr = random.Random(5)
    for side in (-1, 1):
        for k in range(int(2 * L / 3.0)):
            blades = []
            x0 = (-L + k * 3.0) * M
            for i in range(14):
                x = x0 + gr.uniform(0, 3.0) * M
                z = zt + side * gr.uniform(1.45, 1.9) * M
                if side < 0 and -3.0 * M < x < 6.5 * M:                 # trampled flat where cars pull over
                    continue
                h = gr.uniform(0.25, 0.6) * M
                lean = -side * gr.uniform(0.05, 0.2) * M
                blades.append(([(x - 0.05 * M, 0, z), (x + 0.05 * M, 0, z), (x + lean, h, z + lean * 0.5)],
                               [(0, 1, 2), (2, 1, 0)]))
            if blades:
                w.append(merged(blades, Mesh, ink=0.3, name="grass_edge"))
    for k in range(40):                                                # weeds and tufts on the verge
        x = rng.uniform(-L, L) * M
        z = zt - rng.uniform(1.8, 4.5) * M
        w.append(S3.pyramid(x, 0, z, 0.5 * M, rng.uniform(0.25, 0.5) * M, 0.4 * M, ink=0.3, name="tuft"))
    sx, sz = 6.0 * M, zt + 2.0 * M                                     # the station on the edge of the field
    w.extend(weather_station(S3, sx, sz))
    soy = merged([grid_sheet((-L * M, 0.3, zt - 4.8 * M), (2 * L * M, 0, 0), (0, 0, -66 * M), 30, 8)], Mesh, ink=0.0,
                 name="soy")                                           # across the track: a soybean field (Madhya
    soy.under = True                                                   # Pradesh's monsoon crop), low and bright
    w.append(soy)
    rows = [strip(zt - (5.65 + 0.9 * j) * M, zt - (5.2 + 0.9 * j) * M, 0.5, n=20)   # its rows, and two tramlines
            for j in range(40)]
    for z0 in (12.0, 12.7, 31.0, 31.7):
        rows.append(strip(zt - (z0 + 0.3) * M, zt - z0 * M, 0.6, n=20))
    sr = merged(rows, Mesh, ink=0.0, name="soy_row")
    sr.under = True
    w.append(sr)
    for x, z, s in ((-40, -22, 1.2), (-12, -30, 1.0), (30, -26, 1.1), (55, -18, 0.9)):
        _tree(S3, w, x * M, cz + z * M, s)
    tr = random.Random(9)
    for k in range(26):                                                # a tree line along the far edge of the fields
        _tree(S3, w, (-90 + k * 7 + tr.uniform(-2, 2)) * M, cz - tr.uniform(58, 66) * M, tr.uniform(1.3, 2.0))
    posts, wires = [], []                                              # old wire fences of wooden posts on both
    for fz, gap in ((zt - 2.1 * M, (-3.5 * M, 7.5 * M)), (zt + 2.45 * M, (4.6 * M, 7.4 * M))):   # sides (a gate
        run = []                                                       # where cars pull over, and at the station)
        for k in range(60):
            px = (-88 + k * 3.0) * M
            if gap[0] < px < gap[1]:
                if len(run) > 1:
                    wires.append(run)
                run = []
                continue
            posts.append(rod_parts((px, 0, fz), (px + 0.03 * M, 1.15 * M, fz), 0.11 * M))
            run.append(px)
        if len(run) > 1:
            wires.append(run)
        for run in wires:
            for y in (0.55 * M, 0.95 * M):                             # two strands of wire
                for x0, x1 in zip(run, run[1:]):
                    posts.append(rod_parts((x0, y, fz), (x1, y - 0.03 * M, fz), 0.018 * M))
        wires = []
    w.append(merged(posts, Mesh, ink=0.5, name="fence"))
    cl = random.Random(21)                                             # clods of mud thrown up along the ruts
    clods = [S3.pyramid(cl.uniform(-40, 40) * M, 0, zt + cl.choice((-1.05, -0.5, 0.5, 1.05)) * M + cl.uniform(-0.1, 0.1) * M,
                        cl.uniform(0.15, 0.3) * M, cl.uniform(0.05, 0.12) * M, cl.uniform(0.12, 0.25) * M, ink=0.3,
                        name="rut") for _ in range(60)]
    w.extend(clods)
    for x, z, s_ in ((-26, -15, 2.0), (18, -21, 2.3), (47, -13, 1.9), (74, -26, 2.4), (-58, -24, 2.2)):
        _tree(S3, w, x * M, zt + z * M, s_)                            # big lone trees left standing in the fields
    for k in range(8):                                                 # white marker posts with red tops on the verge
        px = (-80 + k * 25) * M
        w.append(S3.box(px, 0, zt - 1.95 * M, 0.1 * M, 0.85 * M, 0.1 * M, ink=0.6, name="station"))
        w.append(S3.box(px, 0.85 * M, zt - 1.95 * M, 0.1 * M, 0.15 * M, 0.1 * M, ink=0.6, name="flag_red"))
    for k in range(5):                                                 # an electric line across the far side
        x = (-60 + k * 30) * M
        w.append(merged([rod_parts((x, 0, cz - 35 * M), (x, 8 * M, cz - 35 * M), 0.18 * M),
                         rod_parts((x - 0.8 * M, 7.4 * M, cz - 35 * M), (x + 0.8 * M, 7.4 * M, cz - 35 * M), 0.1 * M)],
                        Mesh, ink=0.6, name="concrete"))
    _hills(S3, w, cz - 120 * M, rng, col="hill_blue")                  # blue-grey ranges in the rain haze
    fg = []                                                            # corn on the verge right by the wide camera:
    for (fx_, fz_) in ((sx + 2.3 * M, zt - 3.8 * M),):                              # big soft leaves in the corner
        fg.append(rod_parts((fx_, 0, fz_), (fx_, 2.3 * M, fz_), 0.05 * M))
        for j in range(5):
            a = 0.9 + j * 1.25
            y = (0.6 + 0.32 * j) * M
            tip = (fx_ + math.cos(a) * 0.9 * M, y - 0.15 * M, fz_ + math.sin(a) * 0.9 * M)
            mid = (fx_ + math.cos(a) * 0.45 * M, y + 0.2 * M, fz_ + math.sin(a) * 0.45 * M)
            fg.append(([(fx_, y - 0.06 * M, fz_), (mid[0], mid[1] + 0.09 * M, mid[2]), tip, (mid[0], mid[1] - 0.09 * M, mid[2])],
                       [(0, 1, 2, 3), (3, 2, 1, 0)]))
    w.append(merged(fg, Mesh, ink=0.45, name="corn"))
    w.spots = {"track": (0.0, zt), "station": (sx, sz - 0.75 * M), "car_stop": (sx - 4.0 * M, zt)}
    w.shots = {
        "aerial": ((-28 * M, 16 * M, zt - 24 * M), (0.0, 0.0, zt + 6 * M)),
        "track_low": ((-6 * M, 0.5 * M, zt - 2.4 * M), (8 * M, 1.4 * M, zt + 1.5 * M)),
        "track_side": ((sx - 4 * M, 1.6 * M, zt - 8 * M), (sx - 4 * M, 1.2 * M, zt + 1 * M)),
        "station_close": ((sx + 1.5 * M, 1.75 * M, sz - 1.6 * M), (sx, 1.65 * M, sz - 0.3 * M)),
        "station_wide": ((sx - 7 * M, 1.8 * M, sz - 6 * M), (sx, 1.6 * M, sz)),
        "corn_edge": ((sx - 12 * M, 1.4 * M, zt + 0.4 * M), (sx + 6 * M, 1.4 * M, zt + 1.4 * M)),
        "station_truck": ((sx + 2.0 * M, 1.65 * M, zt + 2.3 * M), (sx - 1.2 * M, 1.35 * M, zt + 0.6 * M)),   # him, the truck behind
        "verge_wide": ((sx + 5 * M, 1.4 * M, zt - 4.0 * M), (sx - 2.5 * M, 1.2 * M, zt + 0.5 * M)),
        "mud_low": ((-1.4 * M, 0.9 * M, zt - 4.6 * M), (0.2 * M, 0.75 * M, zt - 1.0 * M)),   # feet, mud, car
        "laptop": ((sx + 2.4 * M, 1.5 * M, sz - 3.2 * M), (sx + 0.3 * M, 1.0 * M, sz - 0.7 * M)),   # him at the case
    }
    return w


def _palm(S3, w, x, z, h=7.0, lean=1.4, rng=None):
    """a coconut / cabbage palm in a hurricane: a thin trunk curving down-wind (+x) and its fronds streaming the
    same way (the wind pushes the crown hardest: drag grows with the square of the speed)"""
    M = S3.M
    rng = rng or random.Random(int(x + z))
    n = 6
    pts = [(x + lean * M * (i / n) ** 2, h * M * i / n, z) for i in range(n + 1)]
    w.append(merged([rod_parts(a, b, (0.32 - 0.12 * i / n) * M) for i, (a, b) in enumerate(zip(pts, pts[1:]))],
                    S3.Mesh, ink=0.6, name="palm_trunk"))
    tx, ty, tz = pts[-1]
    fr = []
    for k in range(9):
        a = k * 2 * math.pi / 9 + rng.uniform(-0.2, 0.2)
        L = rng.uniform(2.2, 3.0) * M
        dx, dz = math.cos(a), math.sin(a)
        dx = dx * 0.45 + 0.9                                           # (blown down-wind)
        ln = math.hypot(dx, dz)
        dx, dz = dx / ln, dz / ln
        tip = (tx + dx * L, ty - rng.uniform(0.3, 1.2) * M, tz + dz * L)
        mid = (tx + dx * L * 0.5, ty + 0.25 * M, tz + dz * L * 0.5)
        sx, sz = -dz * 0.35 * M, dx * 0.35 * M
        fr.append(([(tx, ty, tz), (mid[0] + sx, mid[1], mid[2] + sz), tip, (mid[0] - sx, mid[1], mid[2] - sz)],
                   [(0, 1, 2, 3), (3, 2, 1, 0)]))
    w.append(merged(fr, S3.Mesh, ink=0.5, name="palm_leaf"))


def _stilt_house(S3, w, x, z, rng, broken=0.0, turn=0.0):
    """a Gulf-coast beach house up on stilts (built over the storm-surge line); broken > 0: roof sheets torn
    off, a wall missing, planks hanging"""
    M = S3.M
    wd, dp, ht, up = rng.uniform(6, 9) * M, rng.uniform(5, 7) * M, 3.0 * M, 2.2 * M
    wall = rng.choice(("beach_wall_a", "beach_wall_b", "beach_wall_c"))
    st = []
    for sx in (-0.45, 0.0, 0.45):
        for sz in (-0.42, 0.42):
            st.append(rod_parts((x + sx * wd, 0, z + sz * dp), (x + sx * wd, up, z + sz * dp), 0.25 * M))
    w.append(merged(st, S3.Mesh, ink=0.6, name="wood"))
    w.append(S3.box(x, up, z, wd, ht, dp, ink=0.8, name=wall))
    w.append(S3.box(x, up - 0.1 * M, z - dp / 2 - 0.9 * M, wd * 0.9, 0.15 * M, 1.8 * M, ink=0.6, name="wood"))  # deck
    w.extend(_facade(S3, x - wd / 2 + 0.6 * M, x + wd / 2 - 0.6 * M, up + 0.6 * M, up + ht - 0.4 * M, z - dp / 2 - 2,
                     rng, gap=2.4, ww=1.0, wh=1.2, name="window"))
    roof = rng.choice(("roof_red", "roof_blue", "roof_red"))
    if broken < 0.5:
        w.append(S3.pyramid(x, up + ht, z, wd * 1.12, 2.0 * M, dp * 1.15, ink=0.7, name=roof))
    else:                                                              # the roof half gone: rafters and a hole
        w.append(S3.box(x, up + ht, z, wd * 0.95, 0.1 * M, dp * 0.9, ink=0.5, name="roof_hole"))
        raf = [rod_parts((x + k * wd / 6, up + ht, z - dp / 2), (x + k * wd / 6, up + ht + 1.6 * M, z), 0.14 * M)
               for k in range(-2, 3)]
        w.append(merged(raf, S3.Mesh, ink=0.6, name="wood"))
        w.append(S3.pyramid(x - wd * 0.25, up + ht, z + dp * 0.1, wd * 0.55, 1.6 * M, dp * 0.9, ink=0.7, name=roof))
        pl = []
        for k in range(4):                                             # planks hanging off the side
            px = x + rng.uniform(-0.4, 0.4) * wd
            a = (px, up + rng.uniform(0.2, 1.5) * M, z - dp / 2 - 3)
            b = (px + rng.uniform(-0.8, 0.8) * M, a[1] - rng.uniform(1.2, 2.0) * M, z - dp / 2 - 0.3 * M)
            pl.append(rod_parts(a, b, 0.16 * M))
        w.append(merged(pl, S3.Mesh, ink=0.6, name="plank"))


def storm_coast(S3):
    """Galveston, Texas, in Hurricane Delia: the seafront road (Seawall Boulevard) under a few centimetres of surge
    water, palms bent down-wind, beach houses up on stilts with roofs torn off, leaning power poles and their
    wires, planks and roof tin on the road, and the Gulf behind in long breaking waves. Spots: "street" (where the
    reporter stands, on the near pavement), "road". Shots for the news camera, the street and from the air"""
    M, box = S3.M, S3.box
    rng = random.Random(1900)                                          # (the Galveston hurricane of 1900)
    w = World()
    w.sky = (0.40, 0.44, 0.48)
    w.ground = (0.44, 0.45, 0.41)                                      # the surge: grey-brown water everywhere
    cz = 450.0
    _road(S3, w, cz, half=4.0, length=120, name="asphalt_wet")
    kerb = merged([grid_sheet((-120 * M, 2.0, cz - 4.0 * M), (240 * M, 0, 0), (0, 0, -2.5 * M), 60, 1)], S3.Mesh,
                  ink=0.3, name="kerb")
    kerb.under = True
    w.append(kerb)
    fl = []                                                            # surge water lying over the road in sheets
    for k in range(10):
        x = rng.uniform(-60, 60) * M
        z = cz + rng.uniform(-3, 3) * M
        r = rng.uniform(2.5, 6) * M
        fl.append(([(x - r, 3.0, z - r * 0.4), (x + r, 3.0, z - r * 0.5), (x + r * 0.8, 3.0, z + r * 0.5),
                    (x - r * 0.9, 3.0, z + r * 0.4)], [(3, 2, 1, 0)]))
    m = merged(fl, S3.Mesh, ink=0.0, name="flood")
    m.under = True
    w.append(m)
    for row, zz in enumerate((cz + 10 * M, cz + 22 * M, cz - 16 * M, cz - 30 * M, cz - 44 * M)):
        for k in range(-6, 7):                                         # the beach houses, rows of them
            x = k * 12 * M + rng.uniform(-2, 2) * M + (6 * M if row % 2 else 0)
            if row == 2 and abs(x) < 9 * M:
                continue                                               # (the camera stands here)
            _stilt_house(S3, w, x, zz + rng.uniform(-1.5, 1.5) * M, rng, broken=rng.random())
    for k in range(-10, 11):                                           # palms along both kerbs and among the houses
        _palm(S3, w, k * 7 * M + rng.uniform(-1, 1) * M, cz + 5.5 * M, h=rng.uniform(6, 8.5), lean=rng.uniform(1.0, 2.0),
              rng=rng)
        if abs(k) > 1:
            _palm(S3, w, k * 7 * M + 3 * M, cz - 7.5 * M - rng.uniform(0, 2) * M, h=rng.uniform(6, 8),
                  lean=rng.uniform(1.0, 2.0), rng=rng)
    for k in range(10):
        _palm(S3, w, rng.uniform(-70, 70) * M, cz + rng.choice((-1, 1)) * rng.uniform(12, 50) * M,
              h=rng.uniform(6, 9), lean=rng.uniform(1.0, 2.2), rng=rng)
    poles, wires = [], []
    tops = []
    for k in range(-5, 6):                                             # power poles, leaning, wires sagging
        x = k * 20 * M + 4 * M
        tilt = rng.uniform(-0.2, 0.35) * 9 * M
        a, b = (x, 0, cz + 7.5 * M), (x + tilt, 9 * M, cz + 7.5 * M)
        poles.append(rod_parts(a, b, 0.28 * M))
        poles.append(rod_parts((b[0] - 1.2 * M, 8.4 * M, b[2]), (b[0] + 1.2 * M, 8.4 * M, b[2]), 0.16 * M))
        tops.append(b)
    for p, q in zip(tops, tops[1:]):
        for dx in (-1.1, 1.1):
            seg = 6
            pts = [(p[0] + dx * M + (q[0] - p[0]) * i / seg, 8.4 * M - 1.4 * M * math.sin(math.pi * i / seg),
                    p[2]) for i in range(seg + 1)]
            wires.extend(rod_parts(a, b, 0.04 * M) for a, b in zip(pts, pts[1:]))
    w.append(merged(poles, S3.Mesh, ink=0.7, name="pole"))
    w.append(merged(wires, S3.Mesh, ink=0.4, name="car_trim_dark"))
    deb = []                                                           # debris on the road: planks, roof tin
    tin = []
    for k in range(26):
        x, z = rng.uniform(-40, 40) * M, cz + rng.uniform(-6, 6) * M
        a = rng.uniform(0, math.pi)
        L = rng.uniform(1.2, 3.0) * M
        p0 = (x, 4.0, z)
        p1 = (x + math.cos(a) * L, rng.uniform(4, 30), z + math.sin(a) * L)
        (deb if k % 3 else tin).append(rod_parts(p0, p1, 0.18 * M) if k % 3 else
                                        sheet_parts([(x, 5, z), (x + 1.6 * M, 5, z + 0.2 * M),
                                                     (x + 1.5 * M, 0.5 * M, z + 1.1 * M), (x - 0.1 * M, 0.3 * M, z + 0.9 * M)]))
    w.append(merged(deb, S3.Mesh, ink=0.6, name="plank"))
    w.append(merged(tin, S3.Mesh, ink=0.6, name="tin"))
    sea = merged([grid_sheet((-200 * M, 1.0, cz + 220 * M), (400 * M, 0, 0), (0, 0, -186 * M), 20, 8)], S3.Mesh,
                 ink=0.0, name="sea_storm")
    sea.under = True
    w.append(sea)
    for k in range(10):                                                # the surf: long breaking lines, broken up,
        parts, foam = [], []                                           # each row a little skewed (seen from the
        z_row = cz + 36 * M + k * (10 + 1.5 * k) * M                   # shore: wavy white lines to the horizon)
        x = -220 * M
        while x < 220 * M:
            L = rng.uniform(18, 50) * M
            x0, x1 = x, x + L
            x += L + rng.uniform(2, 12) * M
            z0, z1 = z_row + rng.uniform(-2, 2) * M, z_row + rng.uniform(-2, 2) * M
            hgt = (2.5 + k * 0.8) * M * rng.uniform(0.7, 1.2)
            t0, t1 = x0 + 4 * M, x1 - 4 * M                            # (the crest tapers at both ends)
            parts.append(([(x0, 0, z0), (x1, 0, z1), (t1, hgt, z1 + 2.5 * M), (t0, hgt, z0 + 2.5 * M)],
                          [(0, 1, 2, 3), (3, 2, 1, 0)]))
            parts.append(([(t0, hgt, z0 + 2.5 * M), (t1, hgt, z1 + 2.5 * M), (x1, 0, z1 + 9 * M), (x0, 0, z0 + 9 * M)],
                          [(0, 1, 2, 3), (3, 2, 1, 0)]))
            foam.append(([(t0, hgt * 0.93, z0 + 2.25 * M), (t1, hgt * 0.93, z1 + 2.25 * M), (t1, hgt + 0.1 * M, z1 + 2.55 * M),
                          (t0, hgt + 0.1 * M, z0 + 2.55 * M)], [(0, 1, 2, 3), (3, 2, 1, 0)]))
        w.append(merged(parts, S3.Mesh, ink=0.15, name="sea_face"))
        w.append(merged(foam, S3.Mesh, ink=0.1, name="foam"))
    w.spots = {"street": (0.0, cz - 6.6 * M), "road": (0.0, cz)}
    rz = cz - 6.6 * M
    w.shots = {
        "reporter": ((1.4 * M, 1.6 * M, rz - 3.2 * M), (-0.3 * M, 1.5 * M, rz)),
        "reporter_close": ((0.7 * M, 1.62 * M, rz - 2.0 * M), (-0.2 * M, 1.55 * M, rz)),
        "street_wide": ((-16 * M, 1.3 * M, cz - 3.0 * M), (8 * M, 3.0 * M, cz + 2.5 * M)),
        "street_up": ((-6 * M, 0.6 * M, cz - 2.0 * M), (6 * M, 5.5 * M, cz + 3.0 * M)),   # looking up at the flying
        "aerial": ((-10 * M, 46 * M, cz - 70 * M), (8 * M, 0.0, cz - 6 * M)),
        "coast_wide": ((-20 * M, 9 * M, cz - 34 * M), (12 * M, 9 * M, cz + 80 * M)),
        "coast_high": ((-4 * M, 9 * M, cz + 2 * M), (10 * M, 20 * M, cz + 120 * M)),   # over the roofs to the sea
        "storm_low": ((-22 * M, 1.2 * M, cz - 8 * M), (4 * M, 4.5 * M, cz + 3 * M)),    # down the road, low
    }
    return w


def airstrip(S3):
    """a small airfield at night (the government jet waits): a runway with its centre dashes and edge lights, the
    apron in floodlight, a hangar, a little control tower with a lit window, a windsock, a wire fence and dark
    fields. The jet itself is a vehicle ("kind": "jet" in "stick_cars") so it can stand, taxi and take off.
    Spots: "apron" (where the cars stop), "stairs" (the foot of the jet's airstair), "runway"."""
    M, box = S3.M, S3.box
    rng = random.Random(737)
    w = World()
    w.sky = (0.36, 0.44, 0.58)
    w.ground = (0.30, 0.38, 0.24)
    cz = 450.0
    rz = cz + 30 * M                                                   # the runway, along x
    _road(S3, w, rz, half=15.0, length=220, dash=False, name="asphalt")
    dash, lights = [], []
    for k in range(-36, 37):
        x = k * 6.0 * M
        dash.append(([(x, 1.2, rz - 0.4 * M), (x + 3 * M, 1.2, rz - 0.4 * M), (x + 3 * M, 1.2, rz + 0.4 * M),
                      (x, 1.2, rz + 0.4 * M)], [(3, 2, 1, 0)]))
        for sd in (-1, 1):                                             # edge lights every 6 m
            lights.append(rod_parts((x, 0, rz + sd * 15.5 * M), (x, 0.35 * M, rz + sd * 15.5 * M), 0.22 * M))
    m = merged(dash, S3.Mesh, ink=0.0, name="lane")
    m.under = True
    w.append(m)
    w.append(merged(lights, S3.Mesh, ink=0.4, name="win_lit"))
    ap = merged([grid_sheet((-40 * M, 1.0, cz + 14 * M), (80 * M, 0, 0), (0, 0, -24 * M), 16, 6)], S3.Mesh, ink=0.2,
                name="concrete_wall")                                  # the apron (concrete)
    ap.under = True
    w.append(ap)
    hx, hz = -26 * M, cz + 2 * M                                       # the hangar
    w.append(box(hx, 0, hz, 22 * M, 9 * M, 16 * M, ink=0.7, name="tin"))
    w.append(box(hx, 9 * M, hz, 23 * M, 1.5 * M, 17 * M, ink=0.7, name="roof30"))
    w.append(S3.panel(hx, 0.05 * M, hz - 8.05 * M, 16 * M, 7.5 * M, ink=0.6, name="door_dark"))
    tx, tz = 24 * M, cz - 2 * M                                        # the control tower
    w.append(box(tx, 0, tz, 4 * M, 9 * M, 4 * M, ink=0.7, name="concrete_wall"))
    w.append(box(tx, 9 * M, tz, 5.2 * M, 2.6 * M, 5.2 * M, ink=0.7, name="win_lit"))
    w.append(box(tx, 11.6 * M, tz, 5.6 * M, 0.4 * M, 5.6 * M, ink=0.7, name="roof30"))
    for fx in (-14 * M, 14 * M):                                       # floodlight masts over the apron
        w.append(merged([rod_parts((fx, 0, cz + 1 * M), (fx, 14 * M, cz + 1 * M), 0.3 * M)], S3.Mesh, ink=0.7,
                        name="lamppost"))
        w.append(box(fx, 14 * M, cz + 1 * M, 2.2 * M, 0.8 * M, 1.0 * M, ink=0.6, name="lamp"))
    w.append(merged([rod_parts((34 * M, 0, rz - 20 * M), (34 * M, 6 * M, rz - 20 * M), 0.12 * M)], S3.Mesh, ink=0.6,
                    name="lamppost"))
    w.append(S3.cylinder(35.2 * M, 5.5 * M, rz - 20 * M, 0.35 * M, 0.5 * M, n=8, top_r=0.15 * M, name="flag_red"))
    fence = []
    for k in range(-30, 31):                                           # the wire fence along the near side
        x = k * 5 * M
        fence.append(rod_parts((x, 0, cz - 16 * M), (x, 2.2 * M, cz - 16 * M), 0.08 * M))
    for y in (0.6, 1.3, 2.0):
        fence.append(rod_parts((-150 * M, y * M, cz - 16 * M), (150 * M, y * M, cz - 16 * M), 0.03 * M))
    w.append(merged(fence, S3.Mesh, ink=0.4, name="car_trim_dark"))
    for k in range(10):
        _tree(S3, w, rng.uniform(-120, 120) * M, cz + rng.choice((-1, 1)) * rng.uniform(30, 70) * M + 30 * M,
              rng.uniform(0.9, 1.3))
    _hills(S3, w, cz, rng)
    w.spots = {"apron": (6 * M, cz - 4 * M), "stairs": (2.0 * M, cz + 1.2 * M), "runway": (0.0, rz)}
    w.shots = {
        "apron_wide": ((-2 * M, 3.5 * M, cz - 24 * M), (-2 * M, 2.5 * M, cz + 5 * M)),
        "stairs": ((5.5 * M, 1.6 * M, cz - 3.6 * M), (1.2 * M, 2.0 * M, cz + 2.0 * M)),
        "stairs_low": ((3.6 * M, 0.5 * M, cz - 1.8 * M), (1.4 * M, 2.6 * M, cz + 2.0 * M)),
        "runway": ((-30 * M, 2.0 * M, rz - 30 * M), (20 * M, 6.0 * M, rz)),
        "takeoff": ((40 * M, 1.2 * M, rz - 24 * M), (-10 * M, 9.0 * M, rz)),
    }
    return w


def jet_cabin(S3):
    """inside the government jet at night: a narrow cabin (2 m wide, 1.8 m high) with cream leather seats in facing
    pairs, a small table between them, oval windows of night sky down both sides, a soft ceiling light line, and the
    curtain at the far end. The camera stands at the rear looking forward, so the near end is open.
    Spots: "seat" (Deepak's seat, facing back toward us), "opposite" (the seat facing him), "aisle"."""
    M, box = S3.M, S3.box
    w = World()
    w.sky = (0.05, 0.06, 0.10)
    w.ground = (0.32, 0.30, 0.34)
    w.ceiling = 1.9 * 190.0
    cz = 450.0
    z0, z1, half = cz - 3 * M, cz + 8 * M, 1.0 * M
    for sd in (-1, 1):                                                 # the walls, curving in toward the ceiling
        x = sd * half
        w.append(S3.Mesh(*grid_sheet((x, 0, z0 if sd > 0 else z1), (0, 1.2 * M, 0),
                                     (0, 0, (z1 - z0) * (1 if sd > 0 else -1)), 1, 6), ink=0.3, name="office_wall"))
        w.append(S3.Mesh(*grid_sheet((x, 1.2 * M, z0 if sd > 0 else z1), (-sd * 0.35 * M, 0.7 * M, 0),
                                     (0, 0, (z1 - z0) * (1 if sd > 0 else -1)), 1, 6), ink=0.3, name="office_wall"))
        win = []
        for k in range(6):                                             # oval windows: night outside
            z = z0 + (k + 0.6) * (z1 - z0) / 6.5
            win.append(([(x - sd * 2, 1.0 * M, z - 0.22 * M), (x - sd * 2, 1.0 * M, z + 0.22 * M),
                         (x - sd * 2, 1.45 * M, z + 0.2 * M), (x - sd * 2, 1.45 * M, z - 0.2 * M)],
                        [(0, 1, 2, 3), (3, 2, 1, 0)]))
        w.append(merged(win, S3.Mesh, ink=0.6, name="bldg_win_n"))
    ceil = merged([grid_sheet((-0.65 * M, 1.9 * M, z0), (1.3 * M, 0, 0), (0, 0, z1 - z0), 2, 6)], S3.Mesh, ink=0.2,
                  name="ceiling")
    w.append(ceil)
    w.append(box(0, 1.86 * M, (z0 + z1) / 2, 0.12 * M, 0.03 * M, z1 - z0 - 1 * M, ink=0.1, name="tube_light"))
    w.append(S3.panel(0, 0, z1 - 0.05 * M, 1.9 * M, 1.85 * M, ink=0.6, name="cloth"))      # the curtain forward
    for zc, face in ((cz + 1.2 * M, -1), (cz + 3.0 * M, 1)):           # a facing pair of seats on each side
        for sd in (-1, 1):
            x = sd * 0.55 * M
            w.append(box(x, 0.25 * M, zc, 0.62 * M, 0.22 * M, 0.6 * M, ink=0.8, name="beach_wall_a"))
            w.append(box(x, 0.47 * M, zc + face * 0.3 * M, 0.62 * M, 0.75 * M, 0.14 * M, ink=0.8, name="beach_wall_a"))
            w.append(box(x, 0, zc, 0.4 * M, 0.25 * M, 0.4 * M, ink=0.6, name="car_trim_dark"))
    for sd in (-1, 1):
        w.append(box(sd * 0.55 * M, 0.62 * M, cz + 2.1 * M, 0.55 * M, 0.05 * M, 0.7 * M, ink=0.7, name="wood"))
    w.spots = {"seat": (-0.55 * M, cz + 1.15 * M), "opposite": (-0.55 * M, cz + 3.05 * M), "aisle": (0.0, cz)}
    w.shots = {
        "cabin": ((0.35 * M, 1.45 * M, cz - 2.6 * M), (-0.2 * M, 1.0 * M, cz + 4.0 * M)),
        "deepak": ((0.25 * M, 1.25 * M, cz + 2.6 * M), (-0.55 * M, 1.05 * M, cz + 1.1 * M)),
        "agent": ((0.2 * M, 1.25 * M, cz + 0.2 * M), (-0.55 * M, 1.1 * M, cz + 3.1 * M)),
        "window": ((-0.1 * M, 1.3 * M, cz + 0.4 * M), (-1.0 * M, 1.25 * M, cz + 1.9 * M)),
    }
    return w


def auditorium(S3):
    """the national science auditorium in New Delhi, like a cinema hall: rows of red seats down a gentle rake, a
    centre aisle, the wide stage with the panel's long table and the lectern, and a giant screen behind them (what
    it shows is the scene's "stick_bigscreen"); wood panels on the walls, lights down the ceiling, the double doors
    at the back. Most seats are filled (the far crowd is part of the hall; the story's people sit near the aisle).
    Spots: "doors" (just inside the back doors), "aisle" (half way down), "mark_seat" (an aisle seat), "lectern",
    "panel" (the middle of the panel table)."""
    M, box = S3.M, S3.box
    rng = random.Random(1947)
    w = World()
    w.sky = (0.10, 0.09, 0.10)
    w.ground = (0.42, 0.16, 0.14)                                      # the carpet
    w.ceiling = 9.0 * M
    cz = 450.0
    zb, zf, zs, half = cz - 9 * M, cz + 18 * M, cz + 10.5 * M, 13 * M   # back wall, front wall, stage edge, half width
    for x0, x1, z0_, z1_ in ((-half, half, zb, zb), (half, -half, zf, zf)):
        pass
    for c, v in (("hall_wood", (0.60, 0.36, 0.20)), ("hall_wood_lt", (0.86, 0.60, 0.34)), ("hall_ceiling", (0.16, 0.11, 0.09)),
                 ("hall_stage", (0.80, 0.55, 0.32)), ("hall_lamp", (1.0, 0.93, 0.72))):
        S3.WASH.setdefault(c, v)

    def panels(p0, p1, n):                                             # a wall of tall wood panels, dark and light
        p0, p1 = np.array(p0, float), np.array(p1, float)
        for k in range(n):
            a_, b_ = p0 + (p1 - p0) * k / n, p0 + (p1 - p0) * (k + 1) / n
            w.append(S3.Mesh(*grid_sheet(tuple(a_), tuple(b_ - a_), (0, 9 * M, 0), 1, 3), ink=0.25,
                             name="hall_wood_lt" if k % 3 == 1 else "hall_wood"))
    panels((-half, 0, zf), (half, 0, zf), 12)
    panels((half, 0, zb), (-half, 0, zb), 12)
    panels((half, 0, zb), (half, 0, zf), 14)
    panels((-half, 0, zf), (-half, 0, zb), 14)
    ceil = merged([grid_sheet((-half, 9 * M, zb), (2 * half, 0, 0), (0, 0, zf - zb), 6, 10)], S3.Mesh, ink=0.1,
                  name="hall_ceiling")
    w.append(ceil)
    for zz in [zb + k * 2.6 * M for k in range(1, 11)]:               # down-lights in rows across the ceiling
        lamps = []                                                     # (a row each: sorted with the ceiling tiles)
        for xx in [(-10 + 2.5 * j) * M for j in range(9)]:
            lamps.append(S3.cylinder(xx, 8.75 * M, zz, 0.2 * M, 0.2 * M, n=10))
        w.append(merged([([tuple(v) for v in c.v], [tuple(f) for f in c.f]) for c in lamps], S3.Mesh, ink=0.0,
                        name="hall_lamp"))
    st = merged([grid_sheet((-half, 2.0, zf), (2 * half, 0, 0), (0, 0, zs - zf), 8, 2)], S3.Mesh, ink=0.2,
                name="hall_stage")
    st.under = True                                                    # the stage floor (wood)
    w.append(st)
    arc, lip = [], []                                                  # its front swells out toward the seats
    xs_ = [(-half + 2 * half * k / 24) for k in range(25)]
    zarc = [zs - 1.8 * M * (1 - (x / half) ** 2) for x in xs_]
    for k in range(24):
        arc.append(([(xs_[k], 2.5, zs), (xs_[k + 1], 2.5, zs), (xs_[k + 1], 2.5, zarc[k + 1]), (xs_[k], 2.5, zarc[k])],
                    [(3, 2, 1, 0)]))
        lip.append(([(xs_[k], 0, zarc[k]), (xs_[k + 1], 0, zarc[k + 1]), (xs_[k + 1], 0.18 * M, zarc[k + 1]),
                     (xs_[k], 0.18 * M, zarc[k])], [(0, 1, 2, 3), (3, 2, 1, 0)]))
    m_ = merged(arc, S3.Mesh, ink=0.0, name="hall_stage")
    m_.under = True
    w.append(m_)
    w.append(merged(lip, S3.Mesh, ink=0.3, name="hall_wood"))
    sx0, sx1, sy0, sy1 = -8.5 * M, 8.5 * M, 2.4 * M, 8.0 * M           # the giant screen on the front wall
    w.bigscreen = [(sx0, sy1, zf - 3), (sx1, sy1, zf - 3), (sx1, sy0, zf - 3), (sx0, sy0, zf - 3)]
    rz0, rz1, ry0, ry1 = cz + 2.0 * M, cz + 9.0 * M, 3.2 * M, 7.2 * M   # the side screen on the right wall
    w.bigscreen2 = [(half - 3, ry1, rz0), (half - 3, ry1, rz1), (half - 3, ry0, rz1), (half - 3, ry0, rz0)]
    w.append(S3.Mesh([(half - 2, ry0, rz0), (half - 2, ry0, rz1), (half - 2, ry1, rz1), (half - 2, ry1, rz0)],
                     [(0, 1, 2, 3), (3, 2, 1, 0)], ink=0.6, name="bigscreen"))
    w.append(S3.Mesh([(sx0, sy0, zf - 2), (sx1, sy0, zf - 2), (sx1, sy1, zf - 2), (sx0, sy1, zf - 2)],
                     [(0, 1, 2, 3), (3, 2, 1, 0)], ink=0.6, name="bigscreen"))
    w.append(box(-3.5 * M, 0.74 * M, cz + 13.0 * M, 7.0 * M, 0.08 * M, 1.0 * M, ink=0.8, name="table_top"))
    w.append(box(-3.5 * M, 0, cz + 12.6 * M, 6.8 * M, 0.74 * M, 0.06 * M, ink=0.7, name="cloth"))   # the table's skirt
    for k in range(5):                                                 # the panel's chairs, mics and name cards
        x = (-6.4 + k * 1.45) * M
        w.append(box(x, 0.45 * M, cz + 14.0 * M, 0.55 * M, 0.08 * M, 0.55 * M, ink=0.7, name="chair"))
        w.append(box(x, 0.5 * M, cz + 14.3 * M, 0.55 * M, 0.9 * M, 0.08 * M, ink=0.7, name="chair"))
        w.append(box(x, 0.82 * M, cz + 12.7 * M, 0.4 * M, 0.12 * M, 0.03 * M, ink=0.5, name="paper"))
        w.append(merged([rod_parts((x + 0.3 * M, 0.78 * M, cz + 12.9 * M), (x + 0.3 * M, 1.12 * M, cz + 12.7 * M),
                                   0.03 * M)], S3.Mesh, ink=0.5, name="car_trim_dark"))
    lx, lz = 5.0 * M, cz + 12.2 * M                                    # the lectern with its emblem
    w.append(box(lx, 0, lz, 0.9 * M, 1.15 * M, 0.6 * M, ink=0.8, name="wood"))
    w.append(box(lx, 1.15 * M, lz + 0.05 * M, 1.0 * M, 0.06 * M, 0.7 * M, ink=0.8, name="wood"))
    w.append(S3.cylinder(lx, 0.6 * M, lz - 0.31 * M, 0.2 * M, 0.02 * M, n=12, name="gauge_cap"))
    pal = {"car_2b3a55": (0.17, 0.23, 0.33), "car_7a3b2e": (0.48, 0.23, 0.18), "car_e0d8c8": (0.88, 0.85, 0.78),
           "car_3d6b4a": (0.24, 0.42, 0.29), "car_5a5a62": (0.35, 0.35, 0.38), "car_c8a050": (0.78, 0.63, 0.31)}
    for c, v in pal.items():
        S3.WASH.setdefault(c, v)
    S3.WASH.setdefault("crowd_skin", (0.66, 0.48, 0.35))
    for c, v in (("hair_black", (0.10, 0.09, 0.10)), ("hair_dark", (0.22, 0.15, 0.11)), ("hair_brown", (0.40, 0.26, 0.15)),
                 ("hair_grey", (0.62, 0.62, 0.60)), ("hair_blond", (0.78, 0.62, 0.34))):
        S3.WASH.setdefault(c, v)
    rows = [cz + 7.5 * M - r * 1.15 * M for r in range(13)]             # 13 rows back from the stage

    def bx(x, y, z, w_, h_, d_):                                       # a box as (verts, faces) to merge
        m_ = box(x, y, z, w_, h_, d_)
        return [tuple(v) for v in m_.v], [tuple(f) for f in m_.f]
    for r, z0_ in enumerate(rows):                                     # the seats in blocks of 6 (each block its own
        for sd in (-1, 1):                                             # mesh: the painter's sort then puts people
            for c0 in range(0, 17, 6):                                 # in front of / behind the right seats)
                seats, backs, heads = [], [], []
                crowd = {c: [] for c in pal}
                hair = {c: [] for c in ("hair_black", "hair_dark", "hair_brown", "hair_grey", "hair_blond")}
                for k in range(c0, min(17, c0 + 6)):
                    x = sd * (1.1 + k * 0.62) * M
                    z = z0_ + 0.012 * (x / M) ** 2 * M                  # (the rows curve round the stage)
                    seats.append(bx(x, 0.40 * M, z, 0.5 * M, 0.1 * M, 0.46 * M))           # the cushion
                    backs.append(bx(x, 0.45 * M, z - 0.27 * M, 0.5 * M, 0.55 * M, 0.07 * M))  # the back
                    free = (k < 6 and r < 8)                           # (near the aisle: the story's people sit here)
                    if not free and rng.random() < 0.85:              # the far crowd: seated people, seen
                        col = rng.choice(list(pal))                    # mostly from behind: shoulders, the back
                        crowd[col].append(bx(x, 0.52 * M, z - 0.08 * M, 0.3 * M, 0.42 * M, 0.2 * M))   # of the head
                        crowd[col].append(bx(x, 0.90 * M, z - 0.08 * M, 0.42 * M, 0.14 * M, 0.22 * M))  # (shoulders)
                        hy, hz_ = (1.15 + rng.uniform(-0.04, 0.05)) * M, z - 0.07 * M
                        heads.append(_ball_parts(S3, x, hy, hz_, 0.12 * M, n=8, m=5))
                        hc = rng.choices(list(hair), weights=[5, 4, 2, 1, 1])[0]
                        long_ = rng.random() < 0.3                     # (longer hair hangs lower at the back)
                        hair[hc].append(_ball_parts(S3, x, hy + 0.025 * M, hz_ - 0.03 * M, 0.132 * M, n=8, m=5,
                                                    floor=hy - (0.11 if long_ else 0.04) * M))
                w.append(merged(seats, S3.Mesh, ink=0.15, name="flag_red"))
                w.append(merged(backs, S3.Mesh, ink=0.15, name="flag_red"))
                for c, parts in crowd.items():
                    if parts:
                        w.append(merged(parts, S3.Mesh, ink=0.2, name=c))
                if heads:
                    w.append(merged(heads, S3.Mesh, ink=0.2, name="crowd_skin"))
                for c, parts in hair.items():
                    if parts:
                        w.append(merged(parts, S3.Mesh, ink=0.25, name=c))
    for sd in (-1, 1):                                                 # the double doors at the back
        w.append(S3.panel(sd * 0.75 * M, 0, zb + 3, 1.4 * M, 2.4 * M, ink=0.7, name="door_dark"))
    w.append(box(0, 2.6 * M, zb + 0.1 * M, 2.0 * M, 0.35 * M, 0.08 * M, ink=0.4, name="led_green"))   # EXIT
    w.spots = {"doors": (0.0, zb + 1.2 * M), "aisle": (0.0, cz + 1.0 * M), "mark_seat": (-1.1 * M, rows[5]),
               "lectern": (lx, lz - 0.7 * M), "panel": (-3.5 * M, cz + 14.0 * M)}
    w.shots = {
        "hall_back": ((2.5 * M, 3.6 * M, zb + 0.8 * M), (0.0, 3.4 * M, zf)),
        "stage_view": ((1.0 * M, 2.6 * M, cz + 12.5 * M), (0.0, 1.2 * M, zb + 2 * M)),
        "doors": ((1.4 * M, 1.6 * M, zb + 7.0 * M), (0.0, 1.5 * M, zb + 1.0 * M)),
        "aisle_follow": ((1.3 * M, 2.7 * M, zb + 0.4 * M), (0.0, 1.0 * M, cz + 2.0 * M)),
        "aisle_front": ((0.7 * M, 1.9 * M, cz + 1.5 * M), (0.0, 1.3 * M, zb + 2.0 * M)),   # him walking at us
        "lectern": ((6.4 * M, 1.7 * M, cz + 9.4 * M), (lx, 1.6 * M, lz)),
        "panel": ((-1.6 * M, 1.6 * M, cz + 9.4 * M), (-3.5 * M, 1.3 * M, cz + 13.8 * M)),
        "mark_seat": ((-0.3 * M, 1.5 * M, rows[5] + 1.3 * M), (-1.45 * M, 0.95 * M, rows[5])),   # from the row in front
        "mark_seat_wide": ((1.6 * M, 1.7 * M, rows[5] + 2.2 * M), (-1.3 * M, 0.9 * M, rows[5] - 0.6 * M)),
        "screen": ((0.0, 2.0 * M, cz + 2.0 * M), (0.0, 5.0 * M, zf)),
        "audience": ((9.0 * M, 2.8 * M, cz + 9.5 * M), (-2.0 * M, 1.0 * M, cz + 1.0 * M)),
        "rows_close": ((2.4 * M, 1.4 * M, rows[2] + 1.6 * M), (-0.6 * M, 1.2 * M, rows[6])),
    }
    return w


def weather_center(S3):
    """a national weather forecasting centre at night (NOAA in Miami, or IMD's in Delhi): a tall dark-blue hall
    with a video wall of five screens across the front (what they show is the scene's "stick_bigscreen": one screen
    kind for all, or a list, one per screen), rows of desks each with three glowing monitors, office chairs, tall
    windows on the left with the city's evening glow, and lines of light down the ceiling.
    Spots: "wall" (in front of the video wall), "desk" (an analyst's desk in the front row), "floor" (the middle)."""
    M, box = S3.M, S3.box
    w = World()
    w.sky = (0.05, 0.07, 0.12)
    w.ground = (0.11, 0.13, 0.19)                                      # a dark polished floor
    w.ceiling = 10.0 * M
    cz = 450.0
    zb, zf, half = cz - 10 * M, cz + 14 * M, 15 * M
    for c, v in (("ops_wall", (0.10, 0.14, 0.26)), ("ops_wall_lt", (0.16, 0.22, 0.38)), ("ops_glow", (0.55, 0.78, 1.0)),
                 ("ops_window", (0.95, 0.68, 0.36)), ("ops_desk", (0.82, 0.84, 0.88)), ("ops_screen", (0.30, 0.62, 0.85)),
                 ("hall_ceiling", (0.16, 0.11, 0.09))):
        S3.WASH.setdefault(c, v)
    for p0, p1, n in (((-half, 0, zf), (half, 0, zf), 10), ((half, 0, zb), (-half, 0, zb), 10),
                      ((half, 0, zb), (half, 0, zf), 8)):
        p0, p1 = np.array(p0, float), np.array(p1, float)
        for k in range(n):                                             # dark wall panels
            a, b = p0 + (p1 - p0) * k / n, p0 + (p1 - p0) * (k + 1) / n
            w.append(S3.Mesh(*grid_sheet(tuple(a), tuple(b - a), (0, 10 * M, 0), 1, 3), ink=0.2,
                             name="ops_wall_lt" if k % 4 == 2 else "ops_wall"))
    for k in range(8):                                                 # the left wall: tall windows, evening glow
        z0_, z1_ = zf - (k + 1) * 3 * M, zf - k * 3 * M
        w.append(S3.Mesh(*grid_sheet((-half, 0, z1_), (0, 0, z0_ - z1_), (0, 10 * M, 0), 1, 3), ink=0.25, name="ops_wall"))
        w.append(S3.Mesh(*sheet_parts([(-half + 3, 1.5 * M, z1_ - 0.3 * M), (-half + 3, 1.5 * M, z0_ + 0.3 * M),
                                       (-half + 3, 8.8 * M, z0_ + 0.3 * M), (-half + 3, 8.8 * M, z1_ - 0.3 * M)]),
                         ink=0.4, name="ops_window" if k > 2 else "bldg_win_n"))
    w.append(merged([grid_sheet((-half, 10 * M, zb), (2 * half, 0, 0), (0, 0, zf - zb), 6, 8)], S3.Mesh, ink=0.1,
                    name="hall_ceiling"))
    w.append(merged([rod_parts((x, 9.9 * M, zb + M), (x, 9.9 * M, zf - M), 0.1 * M) for x in (-8 * M, 0.0, 8 * M)],
                    S3.Mesh, ink=0.0, name="ops_glow"))
    # the video wall: a big middle screen, a tall one on each side, two stacked on the right
    scr = [(-6.5 * M, 6.5 * M, 3.0 * M, 9.0 * M), (-13.5 * M, -7.0 * M, 3.0 * M, 7.0 * M),
           (7.0 * M, 13.5 * M, 6.2 * M, 9.4 * M), (7.0 * M, 13.5 * M, 2.6 * M, 5.8 * M), (-13.5 * M, -7.0 * M, 7.2 * M, 9.4 * M)]
    w.screens = []
    for x0, x1, y0, y1 in scr:
        w.append(box((x0 + x1) / 2, y0 - 0.15 * M, zf - 0.25 * M, x1 - x0 + 0.3 * M, y1 - y0 + 0.3 * M, 0.2 * M, ink=0.5,
                     name="car_trim_dark"))
        w.screens.append([(x0, y1, zf - 0.4 * M), (x1, y1, zf - 0.4 * M), (x1, y0, zf - 0.4 * M), (x0, y0, zf - 0.4 * M)])
    desks, mons, chairs = [], [], []
    for r, z in enumerate((cz + 7.0 * M, cz + 2.0 * M, cz - 3.0 * M)):    # three rows of desks facing the wall
        for x in (-10.5 * M, -4.5 * M, 4.5 * M, 10.5 * M):
            m_ = box(x, 0.74 * M, z, 4.6 * M, 0.06 * M, 1.0 * M)
            desks.append(([tuple(v) for v in m_.v], [tuple(f) for f in m_.f]))
            m_ = box(x, 0.0, z + 0.3 * M, 4.4 * M, 0.74 * M, 0.3 * M)
            desks.append(([tuple(v) for v in m_.v], [tuple(f) for f in m_.f]))
            for j in (-1, 0, 1):                                        # three monitors per seat, glowing
                mx = x + j * 0.62 * M
                mons.append(sheet_parts([(mx - 0.3 * M, 0.95 * M, z + 0.2 * M), (mx + 0.3 * M, 0.95 * M, z + 0.2 * M),
                                         (mx + 0.3 * M, 1.35 * M, z + 0.2 * M), (mx - 0.3 * M, 1.35 * M, z + 0.2 * M)]))
            m_ = box(x, 0.45 * M, z - 0.8 * M, 0.55 * M, 0.08 * M, 0.55 * M)
            chairs.append(([tuple(v) for v in m_.v], [tuple(f) for f in m_.f]))
            m_ = box(x, 0.5 * M, z - 1.05 * M, 0.55 * M, 0.7 * M, 0.08 * M)
            chairs.append(([tuple(v) for v in m_.v], [tuple(f) for f in m_.f]))
        w.append(merged(desks, S3.Mesh, ink=0.4, name="ops_desk"))
        w.append(merged(mons, S3.Mesh, ink=0.5, name="ops_screen"))
        w.append(merged(chairs, S3.Mesh, ink=0.4, name="car_trim_dark"))
        desks, mons, chairs = [], [], []
    w.spots = {"wall": (0.0, cz + 10.5 * M), "desk": (-4.5 * M, cz + 6.2 * M), "floor": (0.0, cz)}
    w.shots = {
        "ops_wide": ((11 * M, 4.2 * M, zb + 2 * M), (-2 * M, 4.0 * M, zf)),      # like the reference: from the back
        "wall": ((0.0, 2.2 * M, cz - 2 * M), (0.0, 5.8 * M, zf)),
        "desk": ((-2.6 * M, 1.6 * M, cz + 4.0 * M), (-4.5 * M, 1.2 * M, cz + 7.0 * M)),
        "floor_low": ((3 * M, 1.2 * M, cz - 6 * M), (0.0, 3.0 * M, zf)),
        "faces": ((1.0 * M, 2.3 * M, cz + 11.5 * M), (0.0, 1.1 * M, cz + 2.0 * M)),     # from the wall, at them
    }
    return w



def _fronds(S3, w, tx, ty, tz, rng, n=9, L=(2.0, 2.8), droop=(0.6, 1.4), wide=0.35, name="palm_leaf"):
    """leaves spreading round a crown and drooping (a coconut palm, a banana plant)"""
    M = S3.M
    fr = []
    for k in range(n):
        a = k * 2 * math.pi / n + rng.uniform(-0.25, 0.25)
        ln = rng.uniform(*L) * M
        dx, dz = math.cos(a), math.sin(a)
        tip = (tx + dx * ln, ty - rng.uniform(*droop) * M, tz + dz * ln)
        mid = (tx + dx * ln * 0.5, ty + 0.3 * M, tz + dz * ln * 0.5)
        sx, sz = -dz * wide * M, dx * wide * M
        fr.append(([(tx, ty, tz), (mid[0] + sx, mid[1], mid[2] + sz), tip, (mid[0] - sx, mid[1], mid[2] - sz)],
                   [(0, 1, 2, 3), (3, 2, 1, 0)]))
    w.append(merged(fr, S3.Mesh, ink=0.5, name=name))


def _coconut(S3, w, x, z, h, rng):
    """a coconut palm on a still day: a slim trunk with a gentle curve"""
    M = S3.M
    lean = rng.uniform(-0.8, 0.8)
    pts = [(x + lean * M * (i / 6) ** 2, h * M * i / 6, z) for i in range(7)]
    w.append(merged([rod_parts(a, b, (0.30 - 0.1 * i / 6) * M) for i, (a, b) in enumerate(zip(pts, pts[1:]))],
                    S3.Mesh, ink=0.6, name="palm_trunk"))
    _fronds(S3, w, *pts[-1], rng)


def _banana(S3, w, x, z, rng):
    """a banana plant: a soft green stem 2 m, a few huge paddle leaves"""
    M = S3.M
    w.append(S3.cylinder(x, 0, z, 0.16 * M, 2.0 * M, n=7, top_r=0.11 * M, ink=0.5, name="banana_stem"))
    _fronds(S3, w, x, 2.0 * M, z, rng, n=6, L=(1.4, 1.9), droop=(0.1, 0.8), wide=0.42, name="banana_leaf")


def _mango(S3, w, x, z, s, rng):
    """a mango tree: a short thick trunk, a wide dark crown, ripe fruit hanging under it"""
    M = S3.M
    w.append(S3.cylinder(x, 0, z, 0.3 * M * s, 2.4 * M * s, n=8, top_r=0.2 * M * s, name="trunk"))
    w.append(S3.ball(x, 3.9 * M * s, z, 2.8 * M * s, sy=0.7, n=10, m=5, name="mango_crown"))
    fruit = []
    for k in range(14):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(1.6, 2.5) * M * s
        fruit.append(S3.box(x + math.cos(a) * r, rng.uniform(2.3, 3.0) * M * s, z + math.sin(a) * r,
                            0.16 * M, 0.22 * M, 0.16 * M, ink=0.3, name="mango"))
    w.extend(fruit)


def _bicycle(S3, w, x, z, turn=0.0):
    """an old black roadster bicycle standing on its stand"""
    M = S3.M
    c, s_ = math.cos(turn), math.sin(turn)
    P = lambda u, y: (x + u * c * M, y * M, z + u * s_ * M)
    parts = [disk_parts(P(-0.55, 0.34), (-s_, 0, c), 0.34 * M, 0.04 * M, n=14),
             disk_parts(P(0.55, 0.34), (-s_, 0, c), 0.34 * M, 0.04 * M, n=14)]
    for a, b in (((-0.55, 0.34), (-0.1, 0.85)), ((-0.1, 0.85), (0.45, 0.85)), ((-0.1, 0.85), (0.05, 0.34)),
                 ((0.05, 0.34), (-0.55, 0.34)), ((0.05, 0.34), (0.45, 0.85)), ((0.45, 0.85), (0.55, 0.34)),
                 ((0.45, 0.85), (0.4, 1.05)), ((-0.12, 0.85), (-0.15, 0.95))):
        parts.append(rod_parts(P(*a), P(*b), 0.035 * M))
    parts.append(rod_parts(P(0.4, 1.05) , (P(0.4, 1.05)[0] - s_ * 0.28 * M, 1.05 * M, P(0.4, 1.05)[2] + c * 0.28 * M), 0.035 * M))
    parts.append(rod_parts(P(0.4, 1.05) , (P(0.4, 1.05)[0] + s_ * 0.28 * M, 1.05 * M, P(0.4, 1.05)[2] - c * 0.28 * M), 0.035 * M))
    w.append(merged(parts, S3.Mesh, ink=0.7, name="bike_frame"))
    w.append(S3.box(*P(-0.17, 0.95), 0.25 * M, 0.05 * M, 0.1 * M, ink=0.6, name="seat_black"))


def village_road(S3):
    """the villages near Deepak's farm (Madhya Pradesh), as in the user's picture: a dirt road winding between
    houses - red-tiled roofs on verandas, flat-roofed concrete houses painted blue and yellow with black water
    tanks on top, a tin-roofed house - a kirana shop with its awning, jars and a bench, bamboo fences, a pond with
    lilies, mango trees with fruit, banana plants and coconut palms, a cow, a goat, hens, bicycles, an electric
    line, green fields and hills behind. After the rain the road is wet: ruts and puddles. Cars drive along x
    (the near stretch of road is straight; it bends away into the back of the picture on the right)."""
    M, Mesh, box = S3.M, S3.Mesh, S3.box
    rng = random.Random(4747)
    w = World()
    w.sky = (0.70, 0.84, 0.92)
    w.sky_top = (0.48, 0.66, 0.86)
    w.ground = (0.46, 0.62, 0.30)                                      # green after the monsoon
    cz = 450.0
    zt = cz
    L = 80.0

    def strip(z_lo, z_hi, y, x0=-L, x1=L, n=40):
        return grid_sheet((x0 * M, y, z_hi), ((x1 - x0) * M, 0, 0), (0, 0, z_lo - z_hi), n, 1)
    trk = merged([grid_sheet((-L * M, 0.4, zt + 2.2 * M), (2 * L * M, 0, 0), (0, 0, -4.4 * M), 60, 2)], Mesh, ink=0.2,
                 name="dirt_road")
    trk.under = True
    w.append(trk)
    bend = []                                                          # the lane bending away behind the shop
    for k in range(14):
        u0, u1 = k / 14, (k + 1) / 14
        def c(u): return ((14 + 26 * u + 6 * math.sin(u * 3)) * M, zt + (2.0 + 40 * u) * M)
        (ax, az), (bx, bz) = c(u0), c(u1)
        hw0, hw1 = (1.8 - 0.6 * u0) * M, (1.8 - 0.6 * u1) * M
        bend.append(([(ax - hw0, 0.45, az), (ax + hw0, 0.45, az), (bx + hw1, 0.45, bz), (bx - hw1, 0.45, bz)],
                     [(0, 1, 2, 3), (3, 2, 1, 0)]))
    bm = merged(bend, Mesh, ink=0.1, name="dirt_road")
    bm.under = True
    w.append(bm)
    rm = merged([strip(zz - 0.22 * M, zz + 0.22 * M, 0.7) for zz in (zt - 0.8 * M, zt + 0.8 * M)], Mesh, ink=0.0,
                name="rut")
    rm.under = True
    w.append(rm)
    em = merged([strip(zz - 0.25 * M, zz + 0.25 * M, 0.6) for zz in (zt - 2.2 * M, zt + 2.2 * M)], Mesh, ink=0.0,
                name="grass_edge_flat")
    em.under = True
    w.append(em)
    w.puddles = []                                                     # rain water standing in the ruts
    pr = random.Random(88)
    for k in range(30):
        x = pr.uniform(-45, 45) * M
        z = zt + pr.choice((-0.8, 0.8, 0.0)) * M + pr.uniform(-0.15, 0.15) * M
        rx_, rz_ = pr.uniform(0.5, 1.3) * M, pr.uniform(0.2, 0.42) * M
        pts = [(x + math.cos(2 * math.pi * j / 9) * rx_ * pr.uniform(0.75, 1.15), 1.0,
                z + math.sin(2 * math.pi * j / 9) * rz_ * pr.uniform(0.75, 1.15)) for j in range(9)]
        for scale, y, nm in ((1.25, 0.85, "puddle_rim"), (1.0, 1.0, "puddle"), (0.4, 1.1, "puddle_shine")):
            V = [(x + (px - x) * scale, y, z + (pz - z) * scale) for px, _, pz in pts]
            m = Mesh(V, [tuple(range(9)), tuple(range(8, -1, -1))], ink=0.0, name=nm)
            m.under = True
            w.append(m)
        w.puddles.append((x, z, rx_, rz_))

    def tiled(x, z, wd=6.5, d=5.0, face=-1, wall="village_wall", lit=False):
        """a village house with a red-tiled pitched roof running out over a veranda on two posts"""
        h = 2.8 * M
        w.append(box(x, 0, z, wd * M, h, d * M, name=wall))
        w.append(S3.roof(x, h, z + face * 0.6 * M, wd * M, 1.5 * M, (d + 1.6) * M, over=0.3 * M, name="house_roof"))
        fz = z + face * (d / 2 * M + 2)
        for px in (-wd / 2 + 0.5, wd / 2 - 0.5):                       # veranda posts and its raised floor
            w.append(box(x + px * M, 0, z + face * (d / 2 + 1.4) * M, 0.18 * M, h - 0.1 * M, 0.18 * M, ink=0.7,
                         name="post"))
        w.append(box(x, 0, z + face * (d / 2 + 0.8) * M, wd * M, 0.35 * M, 1.6 * M, ink=0.5, name="plinth"))
        w.append(S3.panel(x - 1.2 * M, 0.35 * M, fz, 1.0 * M, 1.9 * M, ink=0.9, name="door"))
        w.append(box(x + 1.4 * M, 1.1 * M, fz, 1.0 * M, 0.9 * M, 4, ink=0.5, name="win_lit" if lit else "window"))

    def flat(x, z, wd=6.0, d=5.0, h=3.2, face=-1, wall="wall_blue", lit=False):
        """a flat-roofed concrete house painted bright, a black water tank on the roof"""
        w.append(box(x, 0, z, wd * M, h * M, d * M, name=wall))
        w.append(box(x, h * M, z, (wd + 0.15) * M, 0.3 * M, (d + 0.15) * M, ink=0.6, name=wall + "_trim"))
        w.append(S3.cylinder(x + 1.5 * M, (h + 0.3) * M, z + 1.0 * M, 0.55 * M, 1.0 * M, n=10, name="tank"))
        fz = z + face * (d / 2 * M + 2)
        w.append(S3.panel(x - 1.0 * M, 0, fz, 1.0 * M, 2.1 * M, ink=0.9, name="door"))
        for wx in (1.2, 2.4):
            w.append(box(x + (wx - 0.6) * M, 1.2 * M, fz, 0.8 * M, 0.9 * M, 4, ink=0.5,
                         name="win_lit" if (lit and wx < 2) else "window"))

    def tin(x, z, wd=6.0, d=4.6, face=-1):
        """a mud-plastered house under a sloping corrugated tin roof"""
        w.append(box(x, 0, z, wd * M, 2.6 * M, d * M, name="hut"))
        y0, y1 = 2.5 * M, 3.4 * M
        za, zb = z + face * (d / 2 + 0.5) * M, z - face * (d / 2 + 0.4) * M
        w.append(Mesh([(x - (wd / 2 + 0.3) * M, y0, za), (x + (wd / 2 + 0.3) * M, y0, za),
                       (x + (wd / 2 + 0.3) * M, y1, zb), (x - (wd / 2 + 0.3) * M, y1, zb)],
                      [(0, 1, 2, 3), (3, 2, 1, 0)], ink=0.6, name="tinroof"))
        w.append(S3.panel(x, 0, z + face * (d / 2 * M + 2), 1.0 * M, 2.0 * M, ink=0.9, name="door"))

    def fence(x0, x1, z, h=1.1):
        """a bamboo fence: poles and two rails"""
        parts = []
        n = max(2, int(abs(x1 - x0) / 0.45))
        for k in range(n + 1):
            xx = (x0 + (x1 - x0) * k / n) * M
            parts.append(rod_parts((xx, 0, z * M + zt), (xx, h * M * rng.uniform(0.9, 1.05), z * M + zt), 0.07 * M))
        for y in (0.4, 0.85):
            parts.append(rod_parts((x0 * M, y * h * M, z * M + zt), (x1 * M, y * h * M, z * M + zt), 0.06 * M))
        w.append(merged(parts, Mesh, ink=0.6, name="bamboo"))

    # --- the far side of the road (facing it): tiled house, blue house, the shop, yellow house, tin house
    tiled(-30 * M, zt + 7.5 * M, lit=True)
    flat(-12 * M, zt + 8.0 * M, wall="wall_blue", lit=True)
    sx_, sz_ = 6.0 * M, zt + 4.6 * M                                   # the kirana shop
    w.append(box(sx_, 0, sz_ + 1.6 * M, 4.2 * M, 2.7 * M, 3.0 * M, name="hut"))
    w.append(Mesh([(sx_ - 2.4 * M, 2.6 * M, sz_ + 0.1 * M), (sx_ + 2.4 * M, 2.6 * M, sz_ + 0.1 * M),
                   (sx_ + 2.4 * M, 2.15 * M, sz_ - 1.6 * M), (sx_ - 2.4 * M, 2.15 * M, sz_ - 1.6 * M)],
                  [(0, 1, 2, 3), (3, 2, 1, 0)], ink=0.6, name="tinroof"))            # the awning
    for px in (-2.2, 2.2):
        w.append(box(sx_ + px * M, 0, sz_ - 1.5 * M, 0.1 * M, 2.15 * M, 0.1 * M, ink=0.7, name="post"))
    w.append(box(sx_, 0, sz_ - 0.2 * M, 3.6 * M, 1.0 * M, 0.7 * M, ink=0.6, name="counter"))
    for k in range(7):                                                 # jars of sweets and namkeen on the counter
        w.append(S3.cylinder(sx_ + (-1.5 + k * 0.5) * M, 1.0 * M, sz_ - 0.25 * M, 0.14 * M, 0.35 * M, n=8, ink=0.4,
                             name=("jar_red", "jar_yellow", "jar_green")[k % 3]))
    w.append(box(sx_, 2.15 * M, sz_ + 0.05 * M, 3.8 * M, 0.5 * M, 0.1 * M, ink=0.7, name="shop_sign"))
    for k in range(6):                                                 # packets hanging in strips
        w.append(box(sx_ + (-1.6 + k * 0.64) * M, 1.35 * M, sz_ + 0.3 * M, 0.3 * M, 0.7 * M, 0.05 * M, ink=0.3,
                     name=("jar_red", "jar_yellow", "jar_green", "awning")[k % 4]))
    w.append(box(sx_ + 0.3 * M, 1.6 * M, sz_ + 0.6 * M, 0.25 * M, 0.25 * M, 0.25 * M, ink=0.3, name="win_lit"))  # its bulb
    w.append(box(sx_ - 3.6 * M, 0.42 * M, sz_ - 0.6 * M, 2.0 * M, 0.08 * M, 0.45 * M, name="cot"))   # the bench
    for dx in (-0.85, 0.85):
        w.append(box(sx_ - 3.6 * M + dx * M, 0, sz_ - 0.6 * M, 0.08 * M, 0.42 * M, 0.35 * M, ink=0.7, name="cot_leg"))
    flat(24 * M, zt + 14.0 * M, wd=5.5, wall="wall_yellow", lit=False)
    tin(40 * M, zt + 8.0 * M)
    tiled(58 * M, zt + 7.5 * M, wall="house")
    # --- the near side: a tiled house with a veranda (right), the pond and a mango tree (left), fences
    tiled(24 * M, zt - 9.5 * M, face=1, lit=True)
    tiled(-48 * M, zt - 9.0 * M, face=1)
    flat(12 * M, zt - 10.0 * M, wd=5.0, face=1, wall="wall_yellow", lit=True)
    tin(36 * M, zt - 9.0 * M, face=1)
    tiled(-30 * M, zt - 18.0 * M, face=1)
    fence(16, 31, -5.6)
    fence(-30, -18, 4.8)
    fence(-6, 2, 4.4)
    pcx, pcz = -12 * M, zt - 9.5 * M                                   # the pond (rain-fed, lilies on it)
    pts = [(pcx + math.cos(a) * 8.0 * M * (1 + 0.12 * math.sin(3 * a)), 0.5, pcz + math.sin(a) * 3.6 * M)
           for a in [2 * math.pi * k / 18 for k in range(18)]]
    bank = Mesh([(pcx + (x - pcx) * 1.1, 0.3, pcz + (z - pcz) * 1.18) for x, _, z in pts],
                [tuple(range(18)), tuple(range(17, -1, -1))], ink=0.0, name="pond_bank")
    bank.under = True
    w.append(bank)
    pm = Mesh(pts, [tuple(range(18)), tuple(range(17, -1, -1))], ink=0.4, name="water")
    pm.under = True
    w.append(pm)
    for k in range(10):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.3, 0.8)
        lx, lz = pcx + math.cos(a) * r * 7 * M, pcz + math.sin(a) * r * 3 * M
        lp = Mesh([(lx + math.cos(b) * 0.4 * M, 0.8, lz + math.sin(b) * 0.25 * M) for b in
                   [2 * math.pi * j / 7 for j in range(7)]], [tuple(range(7)), tuple(range(6, -1, -1))], ink=0.0,
                  name="lily")
        lp.under = True
        w.append(lp)
    # --- trees: mangoes, coconut palms, banana plants
    for x, z, s in ((-36, -4.5, 1.1), (-6, 13, 1.0), (32, 16, 1.2), (12, -12, 1.0), (-58, 12, 1.1)):
        _mango(S3, w, x * M, zt + z * M, s, rng)
    for x, z, h in ((-20, 12, 9.0), (-17, 15, 8.0), (16, 12, 10.0), (48, 15, 8.5), (-44, 14, 9.5), (66, 12, 9.0)):
        _coconut(S3, w, x * M, zt + z * M, h, rng)
    for x, z in ((-3, 5.0), (-1.5, 6.0), (13, 5.5), (33, 5.2), (30, -6.0), (-40, 5.5)):
        _banana(S3, w, x * M, zt + z * M, rng)
    # --- life: a cow and a goat by the pond, hens in the road edge, bicycles by the shop and the house
    w.animals = [   # 🐄 cartoon animals of the place (stick3d_animals): grazing by the pond, hens in the verge
        {"species": "cow", "pos": (-3 * M, 0.0, zt - 5.2 * M), "dir": 0.2, "do": "eat"},
        {"species": "goat", "pos": (0.5 * M, 0.0, zt - 5.8 * M), "dir": math.pi - 0.2, "do": "idle"},
        {"species": "dog", "pos": (sx_ - 2.0 * M, 0.0, sz_ - 2.6 * M), "dir": 0.0, "do": "lie"},
        {"species": "hen", "pos": (-4.0 * M, 0.0, zt - 2.8 * M), "dir": 0.0, "do": "peck"},
        {"species": "hen", "pos": (-3.2 * M, 0.0, zt - 3.1 * M), "dir": math.pi, "do": "idle"},
        {"species": "hen", "pos": (8.5 * M, 0.0, zt + 2.7 * M), "dir": 0.0, "do": "peck"},
        {"species": "buffalo", "pos": (30 * M, 0.0, zt + 11.0 * M), "dir": math.pi, "do": "eat"},
    ]
    _bicycle(S3, w, sx_ + 3.0 * M, sz_ - 1.0 * M, turn=0.2)
    _bicycle(S3, w, 22 * M, zt - 5.0 * M, turn=-0.1)
    _bicycle(S3, w, -27 * M, zt + 4.4 * M, turn=0.1)
    for k in range(7):                                                 # the electric line along the road
        x = (-60 + k * 20) * M
        w.append(merged([rod_parts((x, 0, zt + 3.2 * M), (x, 7 * M, zt + 3.2 * M), 0.16 * M),
                         rod_parts((x - 0.7 * M, 6.6 * M, zt + 3.2 * M), (x + 0.7 * M, 6.6 * M, zt + 3.2 * M),
                                   0.08 * M)], Mesh, ink=0.6, name="concrete"))
        if k % 2 == 0:
            w.append(box(x + 0.3 * M, 5.4 * M, zt + 3.2 * M, 0.25 * M, 0.2 * M, 0.25 * M, ink=0.4, name="win_lit"))
    fields = merged([grid_sheet((-120 * M, 0.2, zt + 60 * M), (240 * M, 0, 0), (0, 0, -36 * M), 20, 4)], Mesh,
                    ink=0.0, name="soy")                               # the green fields behind the village
    fields.under = True
    w.append(fields)
    tr = random.Random(9)
    for k in range(22):
        _tree(S3, w, (-100 + k * 9.5 + tr.uniform(-2, 2)) * M, zt + tr.uniform(64, 72) * M, tr.uniform(1.3, 1.9))
    _hills(S3, w, cz + 60 * M, rng, col="hill_blue")
    w.spots = {"road": (0.0, zt), "shop": (sx_, sz_ - 2.6 * M), "pond": (pcx + 6 * M, pcz + 4.6 * M)}
    w.shots = {   # (eye, look-at)
        "road_low": ((14 * M, 0.55 * M, zt - 1.7 * M), (-12 * M, 1.1 * M, zt + 0.2 * M)),    # in the ruts: cars come at us
        "road_side": ((0.0, 1.5 * M, zt - 8.0 * M), (0.0, 1.4 * M, zt + 2.0 * M)),          # the verge: they pass by
        "village_high": ((-22 * M, 12 * M, zt - 22 * M), (8 * M, 0.0, zt + 6 * M)),        # like the picture: from up high
        "lane": ((-16 * M, 1.7 * M, zt - 3.2 * M), (10 * M, 1.4 * M, zt + 2.2 * M)),        # along the road
        "shop": ((sx_ - 4.5 * M, 1.6 * M, zt - 4.0 * M), (sx_ - 0.5 * M, 1.3 * M, sz_ - 1.5 * M)),   # villagers at the shop
    }
    return w
