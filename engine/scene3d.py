"""True 2.5D renderer (prototype): a real pinhole depth camera over flat 2D cartoon artwork.

Every object has a world position (X across, Y up, Z into the scene). The camera has a position
(x, height, z) and a focal length; an object at distance d = Z - cam.z is drawn at scale f/d.
So when the camera trucks left/right, near things slide past faster than far things (parallax), and
when it dollies forward, near things grow much faster than far things (real depth) - unlike a zoom.

Depth bands (drawn far -> near, each with its own haze and depth-of-field blur):
  far background (mountains, sky)  ->  background forest  ->  middle ground (characters)
  ->  foreground (bushes, trees)  ->  extreme foreground (big trunks/leaves partly covering the frame)
"""
import math
import os
import random

import cairo

from . import realworld as rw
from .util import clamp, lerp, mix, darker, lighter, hex_to_rgb, TAU, smoothstep
from .depth import blur_surface

FOCAL = 1100.0          # px at 1080p for an object 1 world unit wide at distance 1100 -> 1 px per unit
NEAR = 60.0


class Cam3:
    __slots__ = ("x", "h", "z", "horizon", "focus", "aperture", "fz", "shift", "mirror", "yaw", "pov")

    def __init__(self, x=0.0, h=210.0, z=0.0, horizon=0.40, focus=1300.0, aperture=1.0):
        self.x, self.h, self.z = x, h, z
        self.horizon = horizon          # screen height fraction of the horizon line (camera tilt)
        self.focus = focus              # distance that is sharp
        self.aperture = aperture        # depth-of-field strength
        self.fz = 1.0                   # lens zoom (focal length multiplier) on top of the dolly
        self.shift = 0.0                # lens shift (1080p px): keeps the subject centred while the camera arcs
        self.mirror = False             # reverse angle: the world is seen from the other side
        self.yaw = 0.0                  # radians, + = turned toward +X (point-of-view shots look at someone)
        self.pov = False                # through someone's eyes: near things frame the view instead of fading


PLATE_EMPTY = [False]    # tools/make_plates.py: draw only the ground, the sky and the far land (see photodepth.py)


class Obj:
    __slots__ = ("X", "Y", "Z", "draw", "w", "tag", "person", "h", "seethru", "tint", "sortZ")

    def __init__(self, X, Z, draw, Y=0.0, w=400.0, tag=""):
        self.X, self.Y, self.Z, self.draw, self.w, self.tag = X, Y, Z, draw, w, tag
        self.person, self.h, self.seethru, self.tint = False, 300.0, False, False
        self.sortZ = None               # ground-like things (a hill, a stage) sort by their BACK edge: what stands
                                        # on them or in front is drawn after them, what is behind them before


# ============================================================================ artwork (world units, y-up)
SUN = (1.0, 0.96, 0.82)


def _blob(ctx, x, y, r):
    ctx.new_sub_path()
    ctx.arc(x, y, r, 0, TAU)


CLAY = [False]              # a clay world (Ghatti Nagar): the small plants and stones are soft lit clumps too


def _clay_blob(ctx, x, y, rx, ry, col, rot=0.0):
    """one soft clay lump lit from above (y is up here): light on its top, shade underneath"""
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(max(rx, 0.1), max(ry, 0.1))
    g = cairo.RadialGradient(-0.3, 0.45, 0.05, 0.0, 0.0, 1.05)
    g.add_color_stop_rgb(0, *lighter(col, 0.32))
    g.add_color_stop_rgb(0.55, *col)
    g.add_color_stop_rgb(1, *darker(col, 0.62))
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.set_source(g)
    ctx.fill()
    ctx.restore()


def tree_tall(ctx, rng_seed, t, scale=1.0, leaf="#3b8f3a", trunk="#6b4526", light=0.0):
    """Tall jungle tree: slightly curved trunk, clustered canopy lit from the right."""
    r = random.Random(rng_seed)
    s = scale
    lc, tc = hex_to_rgb(leaf), hex_to_rgb(trunk)
    sway = 5 * rw.sway(t, 0.0, 0.8, rng_seed % 7)
    H = r.uniform(520, 760) * s
    w0 = r.uniform(26, 38) * s
    bend = r.uniform(-30, 30) * s
    # trunk with shading
    ctx.move_to(-w0, 0)
    ctx.curve_to(-w0 * 0.8, H * 0.4, -w0 * 0.55 + bend, H * 0.75, -w0 * 0.4 + bend + sway * 0.3, H)
    ctx.line_to(w0 * 0.4 + bend + sway * 0.3, H)
    ctx.curve_to(w0 * 0.55 + bend, H * 0.75, w0 * 0.8, H * 0.4, w0, 0)
    ctx.close_path()
    g = cairo.LinearGradient(-w0, 0, w0, 0)
    g.add_color_stop_rgb(0, *darker(tc, 0.72))
    g.add_color_stop_rgb(0.65, *tc)
    g.add_color_stop_rgb(1, *lighter(tc, 0.18))
    ctx.set_source(g)
    ctx.fill()
    ctx.set_source_rgba(0, 0, 0, 0.18)
    ctx.set_line_width(3 * s)
    for k in range(4):                                  # bark lines
        yy = r.uniform(0.1, 0.7) * H
        ctx.move_to(-w0 * 0.5, yy)
        ctx.curve_to(-w0 * 0.2, yy + 20 * s, w0 * 0.1, yy + 10 * s, w0 * 0.3, yy + 35 * s)
    ctx.stroke()
    for k in range(r.randint(1, 3)):                    # side branches
        by = r.uniform(0.45, 0.8) * H
        side = r.choice((-1, 1))
        ctx.move_to(side * w0 * 0.3 + bend * 0.6, by)
        ctx.curve_to(side * 60 * s, by + 40 * s, side * 110 * s, by + 70 * s, side * 150 * s + sway, by + 120 * s)
        ctx.set_source_rgb(*tc)
        ctx.set_line_width(11 * s)
        ctx.stroke()
    # canopy: dark core, then mid, then light side (sun top-right)
    cx, cy = bend + sway, H + 60 * s
    blobs = [(r.uniform(-190, 190) * s, r.uniform(-90, 170) * s, r.uniform(70, 125) * s) for _ in range(12)]
    for layer, (col, dx, dy, k) in enumerate(((darker(lc, 0.62), -6, -8, 1.0), (lc, 0, 0, 0.9),
                                               (lighter(lc, 0.22 + light), 14, 16, 0.55))):
        ctx.set_source_rgb(*col)
        for bx, by, br in blobs:
            if layer == 2 and bx < -40 * s:
                continue
            _blob(ctx, cx + bx + dx * s, cy + by + dy * s, br * k)
        ctx.fill()


def tree_pine(ctx, rng_seed, t, scale=1.0, leaf="#2e6f4a", trunk="#5a3b22"):
    r = random.Random(rng_seed)
    s = scale
    lc = hex_to_rgb(leaf)
    ctx.set_source_rgb(*hex_to_rgb(trunk))
    ctx.rectangle(-12 * s, 0, 24 * s, 120 * s)
    ctx.fill()
    n = 4
    for k in range(n):
        by = (90 + k * 95) * s
        w = (170 - k * 32) * s
        hgt = 170 * s
        ctx.move_to(-w, by)
        ctx.line_to(0, by + hgt)
        ctx.line_to(w, by)
        ctx.close_path()
        ctx.set_source_rgb(*darker(lc, 0.8 + 0.05 * k))
        ctx.fill()
        ctx.move_to(0, by + hgt)
        ctx.line_to(w, by)
        ctx.line_to(w * 0.25, by)
        ctx.close_path()
        ctx.set_source_rgb(*lighter(lc, 0.15))
        ctx.fill()


def bush(ctx, rng_seed, t, scale=1.0, leaf="#3f9a3c", flowers=False):
    r = random.Random(rng_seed)
    s = scale
    lc = hex_to_rgb(leaf)
    blobs = [(r.uniform(-110, 110) * s, r.uniform(20, 90) * s, r.uniform(38, 70) * s) for _ in range(9)]
    if CLAY[0]:
        for bx, by, br in sorted(blobs, key=lambda b: b[1]):
            _clay_blob(ctx, bx, by, br, br * 0.88, lc)
        if flowers:
            for _ in range(6):
                _clay_blob(ctx, r.uniform(-90, 90) * s, r.uniform(40, 130) * s, 8 * s, 8 * s,
                           hex_to_rgb(r.choice(["#ff6b6b", "#ffd166", "#ffffff", "#f78fb3"])))
        return
    for col, dx, dy, k in ((darker(lc, 0.65), -4, -6, 1.0), (lc, 0, 0, 0.88), (lighter(lc, 0.25), 10, 12, 0.5)):
        ctx.set_source_rgb(*col)
        for bx, by, br in blobs:
            _blob(ctx, bx + dx * s, by + dy * s, br * k)
        ctx.fill()
    if flowers:
        for _ in range(6):
            ctx.set_source_rgb(*hex_to_rgb(r.choice(["#ff6b6b", "#ffd166", "#ffffff", "#f78fb3"])))
            _blob(ctx, r.uniform(-90, 90) * s, r.uniform(40, 130) * s, 7 * s)
            ctx.fill()


def fern(ctx, rng_seed, t, scale=1.0, leaf="#2f8f3a"):
    r = random.Random(rng_seed)
    s = scale
    lc = hex_to_rgb(leaf)
    sway = 0.05 * rw.sway(t, 0.0, 1.3, rng_seed % 5)
    if CLAY[0]:                                          # fat rounded fronds, lit, no ink
        for k in range(9):
            a = -1.25 + k * 0.31 + r.uniform(-0.08, 0.08) + sway
            L = r.uniform(130, 200) * s
            _clay_blob(ctx, -math.sin(a) * L * 0.5, math.cos(a) * L * 0.5, 24 * s, L * 0.5,
                       lighter(lc, 0.08) if k % 2 else lc, rot=a)
        return
    for k in range(9):
        a = -1.25 + k * 0.31 + r.uniform(-0.08, 0.08) + sway
        L = r.uniform(150, 230) * s
        ctx.save()
        ctx.rotate(a)
        ctx.move_to(0, 0)
        ctx.curve_to(-26 * s, L * 0.35, -20 * s, L * 0.8, 0, L)
        ctx.curve_to(20 * s, L * 0.8, 26 * s, L * 0.35, 0, 0)
        ctx.set_source_rgb(*(lighter(lc, 0.12) if k % 2 else darker(lc, 0.85)))
        ctx.fill()
        ctx.move_to(0, 0)
        ctx.line_to(0, L * 0.95)
        ctx.set_source_rgba(0, 0, 0, 0.18)
        ctx.set_line_width(3 * s)
        ctx.stroke()
        ctx.restore()


def big_leaf_plant(ctx, rng_seed, t, scale=1.0, leaf="#3aa048"):
    """Banana-like broad leaves (foreground plants)."""
    r = random.Random(rng_seed)
    s = scale
    lc = hex_to_rgb(leaf)
    sway = 0.04 * rw.sway(t, 0.0, 1.1, rng_seed % 3)
    if CLAY[0]:
        for k in range(6):
            a = -1.1 + k * 0.45 + r.uniform(-0.1, 0.1) + sway
            L = r.uniform(210, 300) * s
            _clay_blob(ctx, -math.sin(a) * L * 0.5, math.cos(a) * L * 0.5, r.uniform(55, 75) * s, L * 0.5, lc, rot=a)
        return
    for k in range(6):
        a = -1.1 + k * 0.45 + r.uniform(-0.1, 0.1) + sway
        L = r.uniform(230, 330) * s
        W_ = r.uniform(60, 85) * s
        ctx.save()
        ctx.rotate(a)
        ctx.move_to(0, 0)
        ctx.curve_to(-W_, L * 0.3, -W_ * 0.8, L * 0.8, 0, L)
        ctx.curve_to(W_ * 0.8, L * 0.8, W_, L * 0.3, 0, 0)
        g = cairo.LinearGradient(-W_, 0, W_, 0)
        g.add_color_stop_rgb(0, *darker(lc, 0.75))
        g.add_color_stop_rgb(1, *lighter(lc, 0.15))
        ctx.set_source(g)
        ctx.fill()
        ctx.move_to(0, 0)
        ctx.line_to(0, L * 0.96)
        ctx.set_source_rgba(1, 1, 1, 0.25)
        ctx.set_line_width(4 * s)
        ctx.stroke()
        ctx.restore()


def rock(ctx, rng_seed, t, scale=1.0, col="#8e8a80"):
    r = random.Random(rng_seed)
    s = scale
    c = hex_to_rgb(col)
    w, h = r.uniform(70, 130) * s, r.uniform(40, 80) * s
    if CLAY[0]:
        _clay_blob(ctx, 0, h * 0.4, w, h * 0.75, c)
        _clay_blob(ctx, w * 0.45, h * 0.3, w * 0.45, h * 0.5, c)
        return
    ctx.move_to(-w, 0)
    ctx.curve_to(-w, h * 0.9, -w * 0.3, h * 1.3, w * 0.2, h)
    ctx.curve_to(w * 0.8, h * 0.8, w, h * 0.4, w, 0)
    ctx.close_path()
    g = cairo.LinearGradient(-w, 0, w, h)
    g.add_color_stop_rgb(0, *darker(c, 0.75))
    g.add_color_stop_rgb(1, *lighter(c, 0.2))
    ctx.set_source(g)
    ctx.fill()


def grass_tuft(ctx, rng_seed, t, scale=1.0, col="#4f9a3a"):
    r = random.Random(rng_seed)
    s = scale
    c = hex_to_rgb(col)
    sway = 4 * rw.sway(t, 0.0, 1.6, rng_seed % 9)
    if CLAY[0]:                                          # a soft clump of thick rounded blades
        for k in range(6):
            dx = r.uniform(-18, 18) * s
            h = r.uniform(26, 46) * s
            lean = (sway + r.uniform(-8, 8)) * s
            _clay_blob(ctx, dx + lean * 0.5, h * 0.5, 5.5 * s, h * 0.55, lighter(c, r.uniform(0, 0.08)),
                       rot=-math.atan2(lean, h))
        return
    ctx.set_source_rgb(*c)
    for k in range(5):
        dx = r.uniform(-18, 18) * s
        h = r.uniform(26, 48) * s
        ctx.move_to(dx - 4 * s, 0)
        ctx.line_to(dx + sway * s + r.uniform(-8, 8) * s, h)
        ctx.line_to(dx + 4 * s, 0)
        ctx.close_path()
    ctx.fill()


def flower(ctx, rng_seed, t, scale=1.0):
    r = random.Random(rng_seed)
    s = scale
    ctx.set_source_rgb(0.25, 0.55, 0.22)
    ctx.set_line_width(3 * s)
    ctx.move_to(0, 0)
    ctx.line_to(0, 26 * s)
    ctx.stroke()
    ctx.set_source_rgb(*hex_to_rgb(r.choice(["#ff6b6b", "#ffd166", "#ffffff", "#c77dff", "#ff9f1c"])))
    for a in range(0, 360, 72):
        _blob(ctx, 7 * s * math.cos(math.radians(a)), 28 * s + 7 * s * math.sin(math.radians(a)), 5.5 * s)
    ctx.fill()
    ctx.set_source_rgb(1, 0.85, 0.2)
    _blob(ctx, 0, 28 * s, 4 * s)
    ctx.fill()


def mountain_range(ctx, rng_seed, t, scale=1.0, col="#7f9bb8", snow=True):
    r = random.Random(rng_seed)
    s = scale
    c = hex_to_rgb(col)
    x = -9000 * s
    while x < 9000 * s:
        w = r.uniform(1800, 3200) * s
        h = r.uniform(1200, 2300) * s
        px = x + w / 2
        ctx.move_to(x, -200 * s)
        ctx.line_to(px, h)
        ctx.line_to(x + w, -200 * s)
        ctx.close_path()
        ctx.set_source_rgb(*c)
        ctx.fill()
        ctx.move_to(px, h)
        ctx.line_to(x + w, -200 * s)
        ctx.line_to(px + w * 0.05, -200 * s)
        ctx.close_path()
        ctx.set_source_rgb(*lighter(c, 0.12))
        ctx.fill()
        if snow and h > 1700 * s:
            k = 0.22
            ctx.move_to(px, h)
            ctx.line_to(px - w / 2 * k, h * (1 - k))
            ctx.line_to(px - w * 0.05, h * (1 - k * 0.7))
            ctx.line_to(px + w / 2 * k, h * (1 - k))
            ctx.close_path()
            ctx.set_source_rgb(0.96, 0.98, 1.0)
            ctx.fill()
        x += w * 0.6


def big_trunk(ctx, rng_seed, t, scale=1.0, trunk="#5e3d22"):
    """Extreme-foreground tree trunk (partly covers the frame edge)."""
    s = scale
    tc = hex_to_rgb(trunk)
    w = 70 * s
    ctx.move_to(-w * 1.2, 0)
    ctx.curve_to(-w, 600 * s, -w * 0.8, 1300 * s, -w * 0.75, 2400 * s)
    ctx.line_to(w * 0.75, 2400 * s)
    ctx.curve_to(w * 0.8, 1300 * s, w, 600 * s, w * 1.2, 0)
    ctx.close_path()
    g = cairo.LinearGradient(-w, 0, w, 0)
    g.add_color_stop_rgb(0, *darker(tc, 0.6))
    g.add_color_stop_rgb(0.7, *tc)
    g.add_color_stop_rgb(1, *lighter(tc, 0.22))
    ctx.set_source(g)
    ctx.fill()
    ctx.set_source_rgba(0, 0, 0, 0.2)
    ctx.set_line_width(5 * s)
    r = random.Random(rng_seed)
    for k in range(8):
        yy = r.uniform(50, 1400) * s
        ctx.move_to(-w * 0.6, yy)
        ctx.curve_to(-w * 0.2, yy + 30 * s, w * 0.2, yy + 10 * s, w * 0.6, yy + 50 * s)
    ctx.stroke()


def hanging_leaves(ctx, rng_seed, t, scale=1.0, leaf="#2f7f38"):
    """A branch of leaves hanging into the top of the frame (extreme foreground)."""
    r = random.Random(rng_seed)
    s = scale
    lc = hex_to_rgb(leaf)
    sway = 0.05 * rw.sway(t, 0.0, 0.9, rng_seed % 4)
    ctx.save()
    ctx.rotate(sway)
    ctx.set_source_rgb(*darker(lc, 0.55))
    ctx.set_line_width(9 * s)
    ctx.move_to(0, 0)
    ctx.curve_to(30 * s, 900 * s, -40 * s, 2600 * s, 10 * s, 5200 * s)
    ctx.stroke()
    for k in range(9):
        ang = math.pi + r.uniform(-0.9, 0.9)
        L = r.uniform(160, 260) * s
        ox, oy = r.uniform(-150, 150) * s, r.uniform(-40, 40) * s
        ctx.save()
        ctx.translate(ox, oy)
        ctx.rotate(ang - math.pi / 2)
        ctx.move_to(0, 0)
        ctx.curve_to(-45 * s, L * 0.35, -35 * s, L * 0.8, 0, L)
        ctx.curve_to(35 * s, L * 0.8, 45 * s, L * 0.35, 0, 0)
        ctx.set_source_rgb(*(darker(lc, 0.8) if k % 2 else lc))
        ctx.fill()
        ctx.restore()
    ctx.restore()



def jeep_front(ctx, t, color="#5b7f3a", lights=1.0, speed=0.0, wet=0.0, back=False, riders_fn=None, driver=True):
    """Open jungle jeep seen from the front (or back). World units, origin = ground centre, y-up.
    ~340 wide, ~370 tall (a child is ~245)."""
    c = hex_to_rgb(color)
    bounce = (3.0 * math.sin(t * 17) if speed > 30 else 0.6 * math.sin(t * 9))
    # shadow
    ctx.save()
    ctx.scale(210, 26)
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()
    ctx.set_source_rgba(0, 0, 0, 0.35)
    ctx.fill()
    # wet-road reflection of the lights
    if wet > 0.05 and lights > 0.05 and not back:
        for sx in (-112, 112):
            g = cairo.LinearGradient(0, 0, 0, -330)
            g.add_color_stop_rgba(0, 1, 0.95, 0.7, 0.45 * wet * lights)
            g.add_color_stop_rgba(1, 1, 0.95, 0.7, 0)
            ctx.set_source(g)
            ctx.move_to(sx - 20, 0)
            ctx.line_to(sx + 20, 0)
            ctx.line_to(sx + 34, -330)
            ctx.line_to(sx - 34, -330)
            ctx.close_path()
            ctx.fill()
    # wheels
    for sx in (-138, 138):
        ctx.set_source_rgb(0.08, 0.08, 0.09)
        ctx.rectangle(sx - 26, 0, 52, 92)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.08)
        ctx.rectangle(sx - 26, 70, 52, 8)
        ctx.fill()
    ctx.save()
    ctx.translate(0, bounce)
    # chassis + bumper
    ctx.set_source_rgb(0.16, 0.16, 0.17)
    ctx.rectangle(-175, 44, 350, 30)
    ctx.fill()
    # body
    body = cairo.LinearGradient(-170, 0, 170, 0)
    body.add_color_stop_rgb(0, *darker(c, 0.72))
    body.add_color_stop_rgb(0.6, *c)
    body.add_color_stop_rgb(1, *lighter(c, 0.18))
    ctx.set_source(body)
    ctx.move_to(-168, 74)
    ctx.line_to(168, 74)
    ctx.line_to(160, 200)
    ctx.line_to(-160, 200)
    ctx.close_path()
    ctx.fill()
    # fenders
    for sx in (-1, 1):
        ctx.set_source_rgb(*darker(c, 0.8))
        ctx.rectangle(sx * 150 - 32, 150, 64, 22)
        ctx.fill()
    if not back:
        # grille
        ctx.set_source_rgb(*darker(c, 0.5))
        ctx.rectangle(-62, 88, 124, 92)
        ctx.fill()
        ctx.set_source_rgb(*darker(c, 0.85))
        for k in range(7):
            ctx.rectangle(-54 + k * 17, 94, 8, 80)
        ctx.fill()
        # headlights
        for sx in (-112, 112):
            ctx.set_source_rgb(0.2, 0.2, 0.2)
            ctx.arc(sx, 138, 27, 0, TAU)
            ctx.fill()
            ctx.set_source_rgb(*mix((0.8, 0.8, 0.75), (1, 0.98, 0.85), lights))
            ctx.arc(sx, 138, 21, 0, TAU)
            ctx.fill()
        # indicator lights
        ctx.set_source_rgb(1, 0.6, 0.1)
        for sx in (-148, 148):
            ctx.rectangle(sx - 9, 96, 18, 12)
        ctx.fill()
    else:
        ctx.set_source_rgb(0.85, 0.1, 0.1)
        for sx in (-140, 140):
            ctx.rectangle(sx - 14, 110, 28, 40)
        ctx.fill()
        ctx.set_source_rgb(0.12, 0.12, 0.12)       # spare wheel
        ctx.arc(0, 140, 50, 0, TAU)
        ctx.fill()
    # windshield frame + glass
    ctx.set_source_rgb(*darker(c, 0.6))
    ctx.move_to(-150, 200)
    ctx.line_to(150, 200)
    ctx.line_to(140, 318)
    ctx.line_to(-140, 318)
    ctx.close_path()
    ctx.fill()
    ctx.set_source_rgb(0.16, 0.2, 0.25)            # dark cabin
    ctx.rectangle(-132, 210, 264, 98)
    ctx.fill()
    if riders_fn is not None:                       # the people inside, seen through the glass
        ctx.save()
        ctx.rectangle(-132, 210, 264, 98)
        ctx.clip()
        riders_fn(ctx)
        ctx.restore()
    elif driver:                                    # nobody named inside: just the driver's silhouette
        ctx.set_source_rgba(0.08, 0.08, 0.1, 0.55)
        ctx.arc(-60, 262, 22, 0, TAU)
        ctx.fill()
        ctx.rectangle(-92, 210, 64, 32)
        ctx.fill()
    glass = cairo.LinearGradient(-130, 300, 130, 210)
    glass.add_color_stop_rgba(0, 0.55, 0.7, 0.8, 0.28)
    glass.add_color_stop_rgba(1, 0.3, 0.4, 0.5, 0.22)
    ctx.set_source(glass)
    ctx.rectangle(-132, 210, 264, 98)
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.18)
    ctx.move_to(20, 210)
    ctx.line_to(60, 210)
    ctx.line_to(110, 308)
    ctx.line_to(70, 308)
    ctx.close_path()
    ctx.fill()
    # canvas roof
    ctx.set_source_rgb(0.42, 0.38, 0.28)
    ctx.move_to(-150, 318)
    ctx.curve_to(-150, 360, 150, 360, 150, 318)
    ctx.close_path()
    ctx.fill()
    # mirrors
    ctx.set_source_rgb(0.12, 0.12, 0.12)
    for sx in (-1, 1):
        ctx.rectangle(sx * 176 - 12, 215, 24, 30)
    ctx.fill()
    # headlight glow
    if lights > 0.02 and not back:
        from .nightlights import add_device, COOL
        for sx in (-112, 112):                            # the headlights light the road ahead at night
            add_device(ctx, sx, 138, 300, COOL, 0.6 * lights, kind="headlight")
        ctx.set_operator(cairo.OPERATOR_ADD)
        for sx in (-112, 112):
            g = cairo.RadialGradient(sx, 138, 5, sx, 138, 170)
            g.add_color_stop_rgba(0, 1, 0.95, 0.75, 0.75 * lights)
            g.add_color_stop_rgba(0.25, 1, 0.9, 0.6, 0.25 * lights)
            g.add_color_stop_rgba(1, 1, 0.9, 0.6, 0)
            ctx.set_source(g)
            ctx.arc(sx, 138, 170, 0, TAU)
            ctx.fill()
        ctx.set_operator(cairo.OPERATOR_OVER)
    ctx.restore()
    # spray from the wheels on a wet road
    if wet > 0.05 and speed > 60:
        r = random.Random(int(t * 30))
        amt = clamp(speed / 900.0, 0, 1) * wet
        ctx.set_source_rgba(0.9, 0.93, 0.97, 0.55 * amt)
        for sx in (-1, 1):
            for _ in range(22):
                u = r.random()
                x = sx * (160 + 170 * u + r.uniform(-15, 15))
                y = 10 + 150 * u * (1.2 - u) + r.uniform(-10, 10)
                _blob(ctx, x, y, r.uniform(3, 8) * (1.2 - u))
            ctx.fill()

def _make_lut():
    import numpy as np
    x = np.arange(256, dtype=np.float32) / 255.0
    s_ = x - 0.3 * np.sin(2 * math.pi * x) / (2 * math.pi)                         # a soft S (more contrast)
    s_ = np.clip(0.012 + s_ * 0.985, 0, 1)                                        # blacks never crush
    return (s_ * 255.0 + 0.5).astype(np.uint8)


try:
    _FEATURE_LUT = _make_lut()
except Exception:                                   # noqa: BLE001  (numpy missing: no grade)
    _FEATURE_LUT = None


# ============================================================================ the scene
HAZE_DIST = 20000.0      # story units (≈115 m) for the haze to reach 63 % in clear air


class DepthScene:
    def __init__(self, W, H, seed=4, sky=("#5fb0e8", "#d8f0fb"), ground="#6fb04c", path_col="#c9a36b",
                 fog=(0.78, 0.9, 0.95)):
        self.W, self.H, self.S = W, H, H / 1080.0
        self.seed = seed
        self.sky = [hex_to_rgb(c) for c in sky]
        self.ground = hex_to_rgb(ground)
        self.path_col = hex_to_rgb(path_col)
        self.fog = fog
        self.objs = []
        self.actors = []           # callables (t) -> list of Obj  (characters change every frame)
        self.clouds = []
        self.rain = 0.0            # 0..1, set per frame
        self.flash = 0.0           # lightning 0..1, set per frame
        self.frame = 0
        self.look = "flat"         # "feature": animated-film light (set per scene from the story's "cinema")
        self._build()
        self._build_rain()

    # ---------------------------------------------------------------- composition
    def path_x(self, Z):
        """Centre of the winding trail at depth Z."""
        return 90 * math.sin(Z / 1300.0 + 0.6) - 60 + 0.05 * Z * math.sin(Z / 5200.0)

    def _build(self):
        r = random.Random(self.seed)
        add = self.objs.append
        add(Obj(0, 16000, lambda c, t: mountain_range(c, 11, t, 1.0, "#8fb0cf"), w=30000, tag="far"))
        add(Obj(2500, 11000, lambda c, t: mountain_range(c, 23, t, 0.7, "#7596b3", snow=False), w=20000, tag="far"))
        for k in range(8):
            self.clouds.append((r.uniform(-1.2, 1.2), r.uniform(0.05, 0.28), r.uniform(0.6, 1.3), r.uniform(4, 10)))
        # trees across all depths, leaving the trail and the clearing open
        for _ in range(420):
            Z = r.uniform(700, 9500)
            X = r.uniform(-4200, 4200) * (0.6 + Z / 9500)
            gap = 260 + (380 if 900 < Z < 2600 else 0)
            if abs(X - self.path_x(Z)) < gap + 60 * r.random():
                continue
            kind = r.random()
            leaf = r.choice(["#3b8f3a", "#2f7f35", "#469c3f", "#347f3c"])
            sd = r.randint(0, 10 ** 6)
            sc = r.uniform(0.85, 1.35)
            if kind < 0.72:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc, lf=leaf: tree_tall(c, sd, t, sc, lf), w=500 * sc, tag="tree"))
            else:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: tree_pine(c, sd, t, sc), w=360 * sc, tag="tree"))
        # undergrowth
        for _ in range(520):
            Z = r.uniform(380, 6000)
            X = r.uniform(-2600, 2600) * (0.55 + Z / 6000)
            if abs(X - self.path_x(Z)) < 190:
                continue
            if 700 < Z < 2800 and abs(X - self.path_x(Z)) < 560:
                continue
            k = r.random()
            sd = r.randint(0, 10 ** 6)
            sc = r.uniform(0.6, 1.2)
            if k < 0.35:
                bl, bf = r.choice(["#3f9a3c", "#4aa845", "#368a36"]), r.random() < 0.3
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc, bl=bl, bf=bf: bush(c, sd, t, sc, bl, bf), w=260 * sc, tag="bush"))
            elif k < 0.55:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: fern(c, sd, t, sc), w=300 * sc, tag="fern"))
            elif k < 0.65:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: rock(c, sd, t, sc), w=260 * sc, tag="rock"))
            elif k < 0.85:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: grass_tuft(c, sd, t, sc), w=60, tag="grass"))
            else:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: flower(c, sd, t, sc), w=40, tag="flower"))
        # foreground plants framing the clearing
        for X, Z, kind in ((-620, 520, "leaf"), (560, 480, "leaf"), (-380, 430, "fern"), (420, 600, "bush"),
                           (-900, 700, "bush"), (820, 760, "fern"), (-150, 360, "grass"), (230, 390, "flower")):
            sd = r.randint(0, 10 ** 6)
            fn = {"leaf": lambda c, t, sd=sd: big_leaf_plant(c, sd, t, 1.0),
                  "fern": lambda c, t, sd=sd: fern(c, sd, t, 1.1),
                  "bush": lambda c, t, sd=sd: bush(c, sd, t, 1.1, "#3f9a3c", True),
                  "grass": lambda c, t, sd=sd: grass_tuft(c, sd, t, 1.4),
                  "flower": lambda c, t, sd=sd: flower(c, sd, t, 1.3)}[kind]
            add(Obj(X, Z, fn, w=400, tag="fg"))
        # extreme foreground: big trunks at the frame edges + hanging leaves at the top
        add(Obj(-420, 230, lambda c, t: big_trunk(c, 5, t, 1.0), w=300, tag="xfg"))
        add(Obj(430, 260, lambda c, t: big_trunk(c, 8, t, 0.9, "#6a4527"), w=300, tag="xfg"))
        add(Obj(-250, 170, lambda c, t: big_leaf_plant(c, 77, t, 0.5, "#2f8a3c"), w=400, tag="xfg"))
        add(Obj(300, 175, lambda c, t: fern(c, 91, t, 0.55, "#2a7a35"), w=400, tag="xfg"))
        add(Obj(-190, 240, lambda c, t: hanging_leaves(c, 3, t, 0.45), Y=330, w=500, tag="xfg"))
        add(Obj(210, 250, lambda c, t: hanging_leaves(c, 9, t, 0.4, "#357f3a"), Y=345, w=500, tag="xfg"))

    def _build_rain(self):
        """Rain lives in the world: thin sheets of falling drops at many depths, so near drops are big,
        fast and blurred, far drops are fine and hazy, and characters stand between them."""
        r = random.Random(self.seed + 99)
        self.puddles = []
        for Z in (700, 1250, 1750, 2400, 3300, 4300):
            self.puddles.append((self.path_x(Z) + r.uniform(-60, 60), Z, r.uniform(55, 95), r.uniform(1.3, 2.2)))
        Z = 150.0
        while Z < 5200:
            drops = [(r.uniform(-1, 1), r.random(), r.uniform(0.8, 1.2)) for _ in range(46)]
            self.objs.append(Obj(0, Z, lambda c, t, Z=Z, drops=drops: self._rain_sheet(c, t, Z, drops),
                                 w=10 ** 6, tag="rain"))
            Z *= 1.2

    def _rain_sheet(self, ctx, t, Z, drops):
        if self.rain <= 0.01:
            return
        n = int(len(drops) * self.rain)
        halfw = 0.9 * Z * 1.25 + 300
        top = 320 + 0.45 * Z
        L = 70.0
        ctx.set_line_width(1.5 if Z > 400 else 2.2)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgba(0.88, 0.92, 1.0, 0.4 if Z > 400 else 0.16)
        if Z < 400:
            n = n // 2
        wnd = rw.wind()                       # the drops slant with the scene wind
        sl = clamp(0.06 + 0.06 * wnd.strength * (1.0 + wnd.gust(t)), 0.0, 0.8) * wnd.direction
        for fx, fy, sp in drops[:n]:
            y = top - ((fy * top + t * 2600 * sp) % (top + L))
            x = fx * halfw + sl * (top - y)
            ctx.move_to(x, y)
            ctx.line_to(x - sl * L, y + L)
        ctx.stroke()

    # ---------------------------------------------------------------- projection
    def project(self, cam, X, Y, Z):
        dx, d = X - cam.x, Z - cam.z
        if cam.yaw:
            c, s = math.cos(cam.yaw), math.sin(cam.yaw)
            dx, d = dx * c - d * s, dx * s + d * c
        if d < NEAR:
            return None
        k = FOCAL * self.S * cam.fz / d
        hy = self.H * cam.horizon
        if cam.mirror:
            dx = -dx
        return self.W / 2 + cam.shift * self.S + dx * k, hy + (cam.h - Y) * k, k, d

    # ---------------------------------------------------------------- drawing
    def _sky(self, ctx, cam, t):
        W, H = self.W, self.H
        hy = H * cam.horizon
        wet = self.rain
        grey0, grey1 = (0.42, 0.47, 0.52), (0.7, 0.74, 0.77)
        g = cairo.LinearGradient(0, 0, 0, hy + 40 * self.S)
        g.add_color_stop_rgb(0, *mix(mix(self.sky[0], grey0, 0.8 * wet), (0.95, 0.95, 1), self.flash))
        g.add_color_stop_rgb(1, *mix(mix(self.sky[1], grey1, 0.8 * wet), (1, 1, 1), self.flash))
        ctx.set_source(g)
        ctx.paint()
        if wet > 0.3:
            return
        # sun glow (top right)
        sx, sy = W * (0.22 if cam.mirror else 0.78) - cam.x * 0.02 * self.S, H * 0.1
        rg = cairo.RadialGradient(sx, sy, 10, sx, sy, 420 * self.S)
        rg.add_color_stop_rgba(0, 1, 0.98, 0.85, 0.9)
        rg.add_color_stop_rgba(1, 1, 0.98, 0.85, 0)
        ctx.set_source(rg)
        ctx.paint()
        for cx, cy, sc, sp in self.clouds:
            x = ((cx * W + t * sp * self.S - cam.x * 0.03 * self.S) % (W * 2.4)) - W * 0.7
            y = H * cy
            ctx.set_source_rgba(1, 1, 1, 0.9)
            for dx, dy, rr in ((0, 0, 40), (42, 12, 52), (90, 0, 38), (40, -14, 36), (-32, -6, 30)):
                ctx.arc(x + dx * sc * self.S, y - dy * sc * self.S, rr * sc * self.S, 0, TAU)
                ctx.fill()

    def _ground(self, ctx, cam, t):
        """Perspective ground plane + a winding trail, drawn in screen space from horizon to bottom."""
        W, H = self.W, self.H
        hy = H * cam.horizon
        wet = self.rain
        gr = darker(self.ground, 1 - 0.22 * wet)
        fog = self.fog_now()
        g = cairo.LinearGradient(0, hy, 0, H)
        g.add_color_stop_rgb(0, *mix(gr, fog, 0.55))
        g.add_color_stop_rgb(0.25, *mix(gr, fog, 0.18))
        g.add_color_stop_rgb(1, *darker(gr, 0.92))
        ctx.set_source(g)
        ctx.rectangle(0, hy - 1, W, H - hy + 1)
        ctx.fill()
        # grass rows (closer together toward the horizon)
        z = cam.z + 250
        i = 0
        while z < cam.z + 14000:
            pr = self.project(cam, 0, 0, z)
            if pr:
                y = pr[1]
                if y < H:
                    ctx.set_source_rgba(*darker(self.ground, 0.85), 0.10 if i % 2 else 0.05)
                    ctx.rectangle(0, y, W, max(1.0, 26 * pr[2]))
                    ctx.fill()
            z += 70 + (z - cam.z) * 0.18
            i += 1
        # trail
        zs = []
        z = cam.z + NEAR + 20
        while z < cam.z + 13000:
            zs.append(z)
            z += 30 + (z - cam.z) * 0.08
        left, right = [], []
        for zz in zs:
            half = 150 + 40 * math.sin(zz / 900.0)
            pl = self.project(cam, self.path_x(zz) - half, 0, zz)
            pr = self.project(cam, self.path_x(zz) + half, 0, zz)
            if pl and pr:
                left.append(pl[:2])
                right.append(pr[:2])
        if len(left) > 2:
            ctx.move_to(*left[0])
            for p in left[1:]:
                ctx.line_to(*p)
            for p in reversed(right):
                ctx.line_to(*p)
            ctx.close_path()
            pc = darker(self.path_col, 1 - 0.3 * wet)
            pg = cairo.LinearGradient(0, hy, 0, H)
            pg.add_color_stop_rgb(0, *mix(pc, fog, 0.5))
            pg.add_color_stop_rgb(1, *pc)
            ctx.set_source(pg)
            ctx.fill_preserve()
            ctx.set_source_rgba(*darker(self.path_col, 0.8), 0.6)
            ctx.set_line_width(2 * self.S)
            ctx.stroke()
            # pebbles / dirt marks on the trail
            rr = random.Random(5)
            for _ in range(160):
                zz = rr.uniform(300, 6000)
                if zz - cam.z < NEAR + 40:
                    continue
                p = self.project(cam, self.path_x(zz) + rr.uniform(-130, 130), 0, zz)
                if p and p[1] < H:
                    ctx.set_source_rgba(*darker(self.path_col, 0.75), 0.5)
                    ctx.save()
                    ctx.translate(p[0], p[1])
                    ctx.scale(max(1.0, 9 * p[2]), max(0.6, 4 * p[2]))
                    ctx.arc(0, 0, 1, 0, TAU)
                    ctx.restore()
                    ctx.fill()

        if wet > 0.02:
            self._wet_ground(ctx, cam, t)

    def fog_now(self):
        f = mix(self.fog, (0.66, 0.7, 0.74), 0.7 * self.rain)
        wx = getattr(self, "wx", None) or {}
        if wx.get("changing") and wx.get("fog", 0) > 0.01:     # fog rolling in: everything far fades to white
            f = mix(f, (0.85, 0.87, 0.89), 0.8 * wx["fog"])
        return f

    def _ground_ellipse(self, ctx, cam, X, Z, r):
        p = self.project(cam, X, 0, Z)
        if not p or p[1] > self.H + 50:
            return None
        k, d = p[2], p[3]
        ctx.save()
        ctx.translate(p[0], p[1])
        ctx.scale(r * k, max(0.5, r * k * cam.h / d))
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        return p

    def _wetness(self):
        """(how wet the ground is, how big the puddles have grown 0..1) - stays wet after the rain stops."""
        wx = getattr(self, "wx", None) or {}
        if wx.get("changing"):
            return max(self.rain, wx.get("wet", 0.0)), 0.3 + 0.7 * wx.get("puddle", 0.0)
        return self.rain, 1.0

    def _dim(self):
        """How much rain / clouds take away from the sunlight (0 .. 0.8)."""
        return clamp(max(self.rain * 1.4, getattr(self, "cloud", 0.0) * 0.8), 0, 0.8)

    def _wet_ground(self, ctx, cam, t):
        wet, grow = self._wetness()
        rain = self.rain
        sky = mix(self.sky[1], (0.7, 0.74, 0.77), 0.8)
        for X, Z, r, ar in (self.puddles if getattr(self, "has_path", True) else ()):
            if Z - cam.z < NEAR + 30:
                continue
            r = r * grow                                 # puddles grow while it rains
            if self._ground_ellipse(ctx, cam, X, Z, r * 1.0):
                ctx.save()
                ctx.set_source_rgba(*darker(self.path_col, 0.55), 0.55 * wet)
                ctx.fill()
                ctx.restore()
            if self._ground_ellipse(ctx, cam, X + 8, Z - 5, r * 0.8):
                ctx.set_source_rgba(*sky, 0.5 * wet)
                ctx.fill()
            rr = random.Random(int(Z))
            for j in range(4):
                ph = (t * 1.3 + rr.random()) % 1.0
                if self._ground_ellipse(ctx, cam, X + rr.uniform(-0.5, 0.5) * r, Z + rr.uniform(-0.3, 0.3) * r,
                                        6 + 26 * ph):
                    ctx.set_source_rgba(1, 1, 1, 0.5 * (1 - ph) * rain)      # rings where drops hit
                    ctx.set_line_width(max(0.6, 1.4 * self.S))
                    ctx.stroke()
        # tiny splashes all over the ground (new random set each frame)
        rr = random.Random(self.frame)
        ctx.set_source_rgba(0.92, 0.95, 1.0, 0.55 * rain)
        for _ in range(int(140 * rain)):
            Z = cam.z + 120 + rr.random() ** 1.6 * 3000
            X = cam.x + rr.uniform(-1, 1) * (Z - cam.z) * 0.95
            p = self.project(cam, X, 0, Z)
            if p and p[1] < self.H:
                k = p[2]
                ctx.move_to(p[0] - 5 * k, p[1])
                ctx.line_to(p[0] - 2 * k, p[1] - 7 * k)
                ctx.move_to(p[0] + 5 * k, p[1])
                ctx.line_to(p[0] + 2 * k, p[1] - 7 * k)
        ctx.set_line_width(max(0.6, 1.2 * self.S))
        ctx.stroke()

    def _haze_amount(self, d):
        wx = getattr(self, "wx", None) or {}
        fog = wx.get("fog", 0.0) if wx.get("changing") else 0.0
        # clear air: things fade over ~115 m (20000 units), not 40 m - a clean picture with depth; the story's fog
        # (and rain, via fog_now) still brings it in close
        return clamp(1 - math.exp(-d / (HAZE_DIST * (1.0 - 0.92 * fog))), 0, 0.7 + 0.25 * fog)

    def _blur_div(self, cam, d):
        coc = abs(1.0 / max(d, 1.0) - 1.0 / cam.focus) * FOCAL * 7.0 * cam.aperture
        return 1 if coc < 0.6 else int(clamp(1 + coc * 1.4, 2, 14))

    def draw_obj(self, ctx, cam, o, t):
        pr = self.project(cam, o.X, o.Y, o.Z)
        if not pr:
            return
        from . import code3d                            # 3D code drawings project their own faces
        prev = code3d.CURRENT
        code3d.CURRENT = (self, cam, o, pr[0], pr[1], pr[2])
        try:
            self._draw_obj(ctx, cam, o, t, pr)
        finally:
            code3d.CURRENT = prev

    def _draw_obj(self, ctx, cam, o, t, pr):
        sx, sy, k, d = pr
        half = o.w * k
        if sx + half < -50 or sx - half > self.W + 50 or sy < -300 * self.S and o.tag not in ("far", "photo",
                                                                                                "photo_far"):
            return
        fade = 1.0
        if getattr(cam, "pov", False) and o.tag not in ("actor", "rain", "photo", "photo_far"):
            if d < 420:                                     # through the eyes: a bush / wall right in front
                off = abs(sx - self.W / 2) / self.W         # frames the view (like peeking from behind it)
                fade = clamp((d - 70) / 90.0, 0.0, 1.0) * (0.35 + 0.65 * smoothstep(min(1.0, off / 0.32)))
                if fade <= 0.02:
                    return
        elif o.tag not in ("actor", "rain", "photo", "photo_far") and d < 420:
            fade = clamp((d - 200) / 220.0, 0.0, 1.0)      # the lens passes through foliage: it fades away
            if getattr(self, "look", "flat") == "feature":
                fade = 1.0 if fade > 0.6 else 0.0       # no ghosts in a feature frame
            if fade <= 0.02:
                return
        if getattr(self, "look", "flat") == "feature" and o.tag in ("fg", "xfg", "scatter") and \
                d < 0.8 * getattr(cam, "focus", 1e9) and half > 0.35 * self.W:
            return                                      # a long lens made it a wall of blur: out of the shot
        if o.tag in ("fg", "xfg") and d < 0.8 * getattr(cam, "focus", 1e9):
            off = abs(sx - self.W / 2) / self.W             # foreground frames the shot, never covers its middle
            if getattr(self, "look", "flat") == "feature":
                if off < 0.3:                           # feature: a piece frames the edge at full strength, or is
                    fade = min(fade, smoothstep(clamp((off - 0.2) / 0.1, 0.0, 1.0)))    # not there at all
                    if fade <= 0.02:
                        return
            elif off < 0.3:
                fade = min(fade, 0.25 + 0.75 * smoothstep(off / 0.3))
                if fade <= 0.02:
                    return
        if getattr(self, "look", "flat") == "feature" and o.tag not in ("actor", "rain", "photo", "photo_far", "fg", "xfg") \
                and d < 0.7 * getattr(cam, "focus", 1e9) and abs(sx - self.W / 2) < half + 0.12 * self.W \
                and half > 0.08 * self.W:
            return                                      # a big thing right in front of a long lens: the layout
                                                        # artist moves it out of the shot (animated-film cheat)
        people = getattr(self, "_people", None)
        if people and (o.tag in ("place", "scatter", "fg", "xfg") or getattr(o, "seethru", False)) and \
                not getattr(ctx, "live3d", False):
            near = [b for b in people if b[4] > d + 60 and b[0] < sx + half and b[1] > sx - half]
            if near:                                    # the see-through rule (like a game camera):
                tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.W, self.H)
                c2 = cairo.Context(tmp)                 # scenery that covers a person in front of the
                c2.translate(sx, sy)                    # camera turns see-through, so nobody is ever hidden
                c2.scale(k, -k)                         # by a house, a barn or a parked bus
                o.draw(c2, t)
                tmp.flush()
                import numpy as np
                a_ = np.ndarray((self.H, tmp.get_stride() // 4), np.uint32, tmp.get_data())[:, :self.W] >> 24
                cov = 0.0
                for x0, x1, y0, y1, _ in near:
                    X0, X1 = int(max(0, x0)), int(min(self.W, x1))
                    Y0, Y1 = int(max(0, y0)), int(min(self.H, y1))
                    if X1 - X0 < 2 or Y1 - Y0 < 2:
                        continue
                    box = a_[Y0:Y1:3, X0:X1:3]
                    cov = max(cov, float((box > 128).mean()) if box.size else 0.0)
                if getattr(self, "look", "flat") == "feature":
                    if cov > 0.06:
                        return                          # film layout cheat: the set piece is moved out of the shot
                elif cov > 0.2:
                    fade = min(fade, 1.0 - 0.7 * smoothstep((cov - 0.2) / 0.3))
                ctx.save()
                ctx.set_source_surface(tmp, 0, 0)
                ctx.paint_with_alpha(fade)
                ctx.restore()
                return
        if o.tint:                                      # shot check: this person drawn in flat magenta
            import numpy as np
            tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.W, self.H)
            c2 = cairo.Context(tmp)
            c2.translate(sx, sy)
            c2.scale(k, -k)
            o.draw(c2, t)
            tmp.flush()
            a_ = np.ndarray((self.H, tmp.get_stride() // 4), np.uint32, tmp.get_data())[:, :self.W] >> 24
            self._tint_area = int((a_ > 100).sum())
            hh = o.h * k
            dy = 0.0
            ys_ = np.nonzero((a_ > 100).any(axis=1))[0]
            if len(ys_) and ys_.max() < self.H - 2:           # drawn higher (up a hill, on a perch): follow it
                dy = float(ys_.max()) - sy
            self._tint_box = (sx - 0.28 * hh, sy - hh + dy, sx + 0.28 * hh, sy + dy)
            ctx.save()
            ctx.set_source_rgb(1, 0, 1)
            ctx.mask_surface(tmp, 0, 0)
            ctx.restore()
            return
        live_near = None
        if people and getattr(ctx, "live3d", False) and (o.tag in ("place", "scatter", "fg", "xfg") or
                                                         getattr(o, "seethru", False)):
            live_near = [b for b in people if b[4] > d + 60 and b[0] < sx + half and b[1] > sx - half] or None
        mark = (len(ctx.meshes), len(ctx.pics)) if live_near else None
        ctx.save()
        if getattr(ctx, "live3d", False):              # 🎥 live 3D: the fade goes with the meshes and cards
            ctx.fade = fade
        if fade < 0.999:
            ctx.push_group()
        ctx.translate(sx, sy)
        ctx.scale(k, -k)
        o.draw(ctx, t)
        if getattr(ctx, "live3d", False):
            ctx.fade = 1.0
            if mark:                                    # the see-through rule, measured on what was just placed
                from .live3d import see_through
                see_through(ctx, self, cam, live_near, mark, getattr(self, "look", "flat") == "feature")
        if fade < 0.999:
            ctx.identity_matrix()
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(fade)
        ctx.restore()

    BANDS = (9000, 5000, 3000, 1800, 900, 450, 0)

    def render(self, ctx, cam, t, actors=()):
        """Draw the frame. actors: extra Obj list (characters) for this frame."""
        W, H = self.W, self.H
        if getattr(ctx, "live3d", False):              # 🎥 live 3D play (engine/live3d.py)
            return self._render_live3d(ctx, cam, t, actors)
        self._sky(ctx, cam, t)
        allo = [o for o in self.objs] + list(actors)
        if PLATE_EMPTY[0]:                              # making a 2.5D plate (tools/make_plates.py): the place
            allo = [o for o in allo if o.tag in ("grass", "flower", "leaf")]   # without what stands on it
        if cam.yaw:                                     # depth along the (turned) view direction
            c_, s_ = math.cos(cam.yaw), math.sin(cam.yaw)
            dep = lambda o: (o.X - cam.x) * s_ + (o.Z - cam.z) * c_   # noqa: E731
        else:
            dep = lambda o: o.Z - cam.z                  # noqa: E731

        def sort_dep(o):
            sz = getattr(o, "sortZ", None)
            if sz is None:
                return dep(o)
            return (o.X - cam.x) * s_ + (sz - cam.z) * c_ if cam.yaw else sz - cam.z
        if getattr(self, "people_on_top", False):       # a 2.5D plate: its cards first (at their own depths), then
            allo.sort(key=lambda o: (0 if str(o.tag).startswith("photo") else 1, -sort_dep(o)))   # everyone else
        else:
            allo.sort(key=lambda o: -sort_dep(o))
        self._people = []                               # screen boxes of the people (see-through rule)
        for o in actors:
            if getattr(o, "person", False):
                pr = self.project(cam, o.X, o.Y, o.Z)
                if pr:
                    sx, sy, k, d = pr
                    hh = getattr(o, "h", 300.0) * k
                    self._people.append((sx - 0.28 * hh, sx + 0.28 * hh, sy - hh, sy, dep(o)))
        # ground belongs to the far/mid bands; draw it first, blurred by the far band amount
        ground_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        gctx = cairo.Context(ground_surf)
        self._ground(gctx, cam, t)
        ctx.set_source_surface(ground_surf, 0, 0)
        ctx.paint()
        bands = [[] for _ in self.BANDS]
        for o in allo:
            if dep(o) < NEAR:
                continue
            d = sort_dep(o)                             # (a hill / stage goes with its back edge)
            for i, lim in enumerate(self.BANDS):
                if d >= lim:
                    bands[i].append(o)
                    break
        for i, items in enumerate(bands):
            if not items:
                continue
            lim_hi = self.BANDS[i - 1] if i > 0 else 20000
            d_rep = (self.BANDS[i] + lim_hi) / 2 if i > 0 else 12000
            if i == len(self.BANDS) - 1:
                d_rep = 280
            # objects are drawn far -> near; an actor (character) gets its own layer so its focus
            # and haze follow its exact distance while bushes of the same band can still pass in front
            run = []
            xfg = i == len(self.BANDS) - 1
            band_div = self._div(cam, d_rep, xfg)
            for o in items + [None]:
                if o is not None and o.tag == "actor" and self._div(cam, dep(o)) == band_div:
                    run.append(o)                      # same focus as its band: no extra layer needed
                    continue
                if o is None or o.tag == "actor":
                    if run:
                        self._composite(ctx, cam, run, t, d_rep, xfg=xfg)
                        run = []
                    if o is not None:
                        self._composite(ctx, cam, [o], t, dep(o))
                else:
                    run.append(o)
        self._light(ctx, t)

    def _render_live3d(self, ctx, cam, t, actors):
        """live 3D play: the sky and the ground as drawing (behind), every 3D thing as "this mesh, here" (the
        browser draws them with depth), the flat things that stand in the scene as drawing behind the 3D too"""
        self._sky(ctx, cam, t)
        ctx.ground(self, cam, t)                      # (one picture from above, laid flat by the browser)
        allo = [o for o in self.objs] + list(actors)
        if cam.yaw:
            c_, s_ = math.cos(cam.yaw), math.sin(cam.yaw)
            dep = lambda o: (o.X - cam.x) * s_ + (o.Z - cam.z) * c_   # noqa: E731
        else:
            dep = lambda o: o.Z - cam.z                  # noqa: E731
        allo.sort(key=lambda o: -dep(o))
        self._people = []                             # screen boxes of the people (the see-through rule)
        for o in actors:
            if getattr(o, "person", False):
                pr = self.project(cam, o.X, o.Y, o.Z)
                if pr:
                    sx, sy, k, d = pr
                    hh = getattr(o, "h", 300.0) * k
                    self._people.append((sx - 0.28 * hh, sx + 0.28 * hh, sy - hh, sy, dep(o)))
        for o in allo:
            if dep(o) >= NEAR:
                ctx.save()
                self.draw_obj(ctx, cam, o, t)
                ctx.restore()
        ctx.layer3d(cam, self)
        self._light(ctx, t)

    def _div(self, cam, d, xfg=False):
        div = self._blur_div(cam, d)
        if xfg:
            div = max(div, 6)
        return max(1, int(round(div * min(1.0, self.S * 1.3))))

    def _composite(self, ctx, cam, items, t, d_rep, xfg=False):
        W, H = self.W, self.H
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        c2 = cairo.Context(surf)
        for o in items:
            self.draw_obj(c2, cam, o, t)
        feat = getattr(self, "look", "flat") == "feature"
        if feat and items and all(getattr(o, "person", False) for o in items):
            self._rim(surf, c2)                 # a thin warm edge on the sun side lifts people off the scene
            self._bounce(c2)                    # + the colour of the sunlit ground bounced onto them
        hz = self._haze_amount(d_rep) * (1 + 0.5 * self.rain)
        fog = self.fog_now()
        if feat:                                # aerial perspective: far things turn cooler and bluer
            far = smoothstep(clamp((d_rep - 900.0) / 8000.0, 0.0, 1.0))
            fog = tuple(lerp(a, b, 0.4 * far) for a, b in zip(fog, self._cool_sky()))
            hz = min(0.78, hz * 1.15)
        if hz > 0.01:                          # atmospheric haze: tint only where something was drawn
            c2.set_operator(cairo.OPERATOR_ATOP)
            c2.set_source_rgba(*fog, hz)
            c2.paint()
        div = self._div(cam, d_rep, xfg)       # same look at 360p and 1080p; extreme fg always soft
        # speed: only the part of the frame where something was drawn is blurred and painted
        import numpy as np
        surf.flush()
        al = np.ndarray((H, surf.get_stride() // 4), np.uint32, surf.get_data())[:, :W][::4, ::4] >> 24
        rows = np.nonzero(al.any(axis=1))[0]
        if not len(rows):
            return
        cols = np.nonzero(al.any(axis=0))[0]
        pad = 8 + 3 * div
        x0, x1 = max(0, cols[0] * 4 - pad), min(W, cols[-1] * 4 + 4 + pad)
        y0, y1 = max(0, rows[0] * 4 - pad), min(H, rows[-1] * 4 + 4 + pad)
        if (x1 - x0) * (y1 - y0) > 0.7 * W * H or os.environ.get("SS_FULL"):
            src = blur_surface(surf, div) if div > 1 else surf
            ctx.set_source_surface(src, 0, 0)
            ctx.paint()
            return
        if div > 1:
            part = cairo.ImageSurface(cairo.FORMAT_ARGB32, x1 - x0, y1 - y0)
            pc = cairo.Context(part)
            pc.set_source_surface(surf, -x0, -y0)
            pc.paint()
            src, ox, oy = blur_surface(part, div), x0, y0
        else:
            src, ox, oy = surf, 0, 0
        ctx.save()
        ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
        ctx.clip()
        ctx.set_source_surface(src, ox, oy)
        ctx.paint()
        ctx.restore()

    def _light(self, ctx, t):
        """Warm sun shafts from the top right + soft vignette."""
        W, H, S = self.W, self.H, self.S
        sun = (1 - clamp(max(self.rain * 1.6, getattr(self, "cloud", 0.0) * 1.2), 0, 1)) * \
            (1.0 if getattr(self, "shafts", True) else 0.0)
        for i in range(4 if sun > 0.02 else 0):
            x = W * (0.55 + 0.12 * i) + 30 * S * math.sin(t * 0.3 + i)
            w = (90 + 40 * (i % 2)) * S
            g = cairo.LinearGradient(x, 0, x - 420 * S, H)
            g.add_color_stop_rgba(0, *SUN, 0.16 * sun)
            g.add_color_stop_rgba(1, *SUN, 0)
            ctx.set_source(g)
            ctx.move_to(x - w / 2, 0)
            ctx.line_to(x + w / 2, 0)
            ctx.line_to(x + w / 2 - 520 * S, H)
            ctx.line_to(x - w / 2 - 600 * S, H)
            ctx.close_path()
            ctx.fill()
        ctx.set_source_rgba(1.0, 0.85, 0.55, 0.06 * sun)
        ctx.paint()
        if self.rain > 0.02:                   # cool, dim storm light
            ctx.set_source_rgba(0.25, 0.32, 0.4, 0.14 * self.rain)
            ctx.paint()
        if self.flash > 0.01:
            ctx.set_source_rgba(0.92, 0.95, 1.0, 0.55 * self.flash)
            ctx.paint()
        if getattr(self, "look", "flat") == "feature":
            self._feature_light(ctx)
        g = cairo.RadialGradient(W / 2, H / 2, H * 0.4, W / 2, H / 2, H * 1.0)
        g.add_color_stop_rgba(0, 0, 0, 0, 0)
        g.add_color_stop_rgba(1, 0, 0, 0, getattr(self, "vignette", 0.35))
        ctx.set_source(g)
        ctx.paint()

    # ---------------------------------------------------------------- the animated-feature look
    def _night(self):
        return str(getattr(getattr(self, "bg", None), "time", "day") or "day").lower() in ("night", "midnight")

    def _sun_side(self):
        """+1 = the sun is on the right of the picture, -1 = on the left."""
        v = getattr(self, "_sun3", None)
        try:
            return 1.0 if float(v[0]) >= 0 else -1.0
        except (TypeError, IndexError, ValueError):
            return 1.0

    def _cool_sky(self):
        return (0.38, 0.5, 0.78) if self._night() else (0.56, 0.72, 0.95)

    def _rim(self, surf, c2):
        """Rim light: the edge of the figure that faces the light gets a thin warm (moon: cool) line."""
        W, H, S = self.W, self.H, self.S
        k = max(1.0, 2.6 * S)
        edge = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        e = cairo.Context(edge)
        e.set_source_surface(surf, 0, 0)
        e.paint()
        e.set_operator(cairo.OPERATOR_DEST_OUT)
        e.set_source_surface(surf, -k * self._sun_side(), k * 0.8)   # what is left: the edge toward the light
        e.paint()
        sun = self._sun_info()
        col = (0.72, 0.82, 1.0) if self._night() else tuple(min(1.0, 0.2 + 0.8 * v) for v in sun["color"])
        c2.save()
        c2.set_operator(cairo.OPERATOR_ATOP)
        c2.set_source_rgba(*col, (0.45 + 0.2 * sun["warmth"]) * (1 - self._dim()))
        c2.mask_surface(edge, 0, 0)
        c2.restore()

    def _sun_info(self):
        from . import realworld
        bg = getattr(self, "bg", None)
        return realworld.sun(realworld.time_word(bg) if bg is not None else "day")

    def _bounce(self, c2):
        """Light bounced off the ground onto people: sunlit grass tints them a little green, sand warm, snow
        bright (more when the sun is high and the ground well lit; none at night or in heavy rain)."""
        sun = self._sun_info()
        if sun["night"]:
            return
        g = getattr(self, "ground", None)
        if not g:
            return
        k = 0.05 + 0.07 * math.sin(math.radians(sun["elev"]))
        k *= 1 - self._dim()
        c2.save()
        c2.set_operator(cairo.OPERATOR_ATOP)
        c2.set_source_rgba(*[min(1.0, v * 1.15) for v in g[:3]], k)
        c2.paint()
        c2.restore()

    def _feature_light(self, ctx):
        """Warm key from the sun side, cool sky fill in the shadow side, a soft bloom on the bright parts and
        a vibrant grade (a gentle S-curve + a little more colour) - the feature-film light."""
        import numpy as np
        W, H = self.W, self.H
        tgt = ctx.get_target()
        c = cairo.Context(tgt)
        night, side = self._night(), self._sun_side()
        wet = self._dim()                       # rain or clouds over the sun: a softer, cooler light
        # 1. key / fill (soft light keeps the drawing, shifts the colour temperature)
        g = cairo.LinearGradient(W if side > 0 else 0, 0, 0 if side > 0 else W, H)
        sun = self._sun_info()                  # low sun (morning / evening): warmer and stronger from the side
        warm = (0.62, 0.72, 1.0) if night else tuple(0.5 * a + 0.5 * b for a, b in zip(sun["color"], (1.0, 0.8, 0.52)))
        cool = (0.3, 0.4, 0.75) if night else (0.42, 0.58, 0.95)
        g.add_color_stop_rgba(0, *warm, (0.30 if night else 0.2 + 0.18 * sun["warmth"]) * (1 - wet))
        g.add_color_stop_rgba(0.55, 0.5, 0.5, 0.5, 0.0)
        g.add_color_stop_rgba(1, *cool, 0.26 * (1 - 0.5 * wet))
        c.set_operator(cairo.OPERATOR_SOFT_LIGHT)
        c.set_source(g)
        c.paint()
        c.set_operator(cairo.OPERATOR_OVER)
        tgt.flush()
        # 2. bloom: bright parts glow softly (worked out at 1/8 size, cheap at any resolution)
        sw, sh = max(8, W // 8), max(8, H // 8)
        small = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
        sc_ = cairo.Context(small)
        sc_.scale(sw / W, sh / H)
        pat = cairo.SurfacePattern(tgt)
        pat.set_filter(cairo.FILTER_GOOD)
        sc_.set_source(pat)
        sc_.paint()
        small.flush()
        a = np.ndarray((sh, small.get_stride() // 4, 4), np.uint8, small.get_data())[:, :sw]
        lum = a[..., :3].max(axis=2).astype(np.int16)
        keep = np.clip((lum - 232) * 10, 0, 255).astype(np.uint16)        # only what is really bright
        for ch in range(3):
            a[..., ch] = (a[..., ch].astype(np.uint16) * keep >> 8).astype(np.uint8)
        small.mark_dirty()
        from .depth import blur_surface
        glow = blur_surface(blur_surface(small, 2), 2)
        c.save()
        c.scale(W / sw, H / sh)
        gp = cairo.SurfacePattern(glow)
        gp.set_filter(cairo.FILTER_BILINEAR)
        c.set_source(gp)
        c.set_operator(cairo.OPERATOR_SCREEN)
        c.paint_with_alpha(0.45 if night else 0.22)
        c.restore()
        tgt.flush()
        # 3. grade: gentle S-curve + saturation (integer maths on the frame, a few ms)
        stride = tgt.get_stride() // 4
        px = np.ndarray((tgt.get_height(), stride, 4), np.uint8, tgt.get_data())[:H, :W]
        lut = _FEATURE_LUT
        if lut is None:
            return
        rgb = px[..., :3]
        l_ = ((rgb[..., 2].astype(np.int32) * 77 + rgb[..., 1].astype(np.int32) * 150 +
               rgb[..., 0].astype(np.int32) * 29) >> 8)
        for ch in range(3):
            v = rgb[..., ch].astype(np.int32)
            v = v + (((v - l_) * 40) >> 8)                                   # +16 % colour
            rgb[..., ch] = lut[np.clip(v, 0, 255)]
        tgt.mark_dirty()
