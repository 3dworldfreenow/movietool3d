"""Code-drawn assets: write a small Python drawing and it becomes a real thing in your stories.

Studio > 🐍 Code  (or put files in assets/code/<name>.py yourself)

Every file is plain Python with a few settings at the top and one function:

    KIND = "object"                 # object | prop | vehicle | wear | place
    DESCRIPTION = "clay water pot"  # what it is (the AI prompts see this)
    STATES = ["full", "broken"]     # optional: other looks (first one = normal look)
    ANIMATED = 2.0                  # optional: seconds of a looping animation (t goes 0 .. 2)
    ABILITIES = ["movable"]         # optional: movable, sit, climb, open, light ...
    HIDE_HAIR = True                # wear only: hide the hair under it

    def draw(pen, t, state):
        pen.ellipse(0, 40, 45, 40, "clay")
        pen.rect(-20, 70, 40, 18, pen.dark("clay"))

Units are story units: an adult person is 300 tall, a door 125, a hut 690.  y goes UP, the ground is y = 0,
x = 0 is the middle of the thing.  What you draw at real size is the real size in the story.

KIND "place" = a whole place: every  with pen.thing("name", z=..., abilities=[...]):  block becomes a real
thing (its own picture at its own depth) and a place is saved (assets/places/<name>.json) - see README.

KIND "objects" = many separate objects in one file: every pen.thing block is saved as its own object
(named after the block) that you can use anywhere.

LIVE: code drawings are drawn from their code every frame (sharp at any zoom, and faster than big pictures);
the saved picture is the backup (used if the code fails, or if it is slower than LIVE_MAX_MS per frame).
LIVE = False in a file always uses the picture.

KIND "wear" = something a character wears on the head (hat, crown, mask, glasses, flower, horns ...).
Then the head is a circle of radius 100 at (0, 0), the face looks to the RIGHT (+x), y goes up.
Use it in a story with  "hat": "<name>"  on the character.  pen.accent / pen.skin / pen.hair are the
character's colours.

Objects, props and vehicles are saved as pictures in assets/images/ (a PNG, or an animated WebP), so they work
everywhere a picture works: place JSON lists, "elements", "props", picture vehicles, 2D and 3D.
The code itself stays in assets/code/ - change a number and save again.

Safety: the drawing runs in its own process with a time limit and without files, network or imports
(only math and random).
"""
import ast
import json
import re
import math
import os
import random
import subprocess
import sys

import cairo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "assets", "code")
KINDS = ("object", "prop", "vehicle", "wear", "place", "objects",
         "object3d", "prop3d", "vehicle3d", "place3d", "objects3d", "character3d", "animal3d")
CHAR_KINDS = ("character3d", "animal3d")      # 3D people / animals: drawn on a posed skeleton (engine/char3d.py)
PX = 2.0                    # pixels per story unit in the saved picture
LOD_PX = 60.0               # 3D page: a 3D thing smaller than this on screen (1080p px) is drawn from its picture
LIVE_MAX_MS = 60.0          # a drawing slower than this per frame is shown from its picture, not live
FPS = 12                    # frames per second of an animated drawing
MAX_ANIM = 4.0              # longest loop (seconds)
SETTINGS = ("KIND", "DESCRIPTION", "STATES", "ANIMATED", "ABILITIES", "HIDE_HAIR", "HEIGHT", "PLACE", "SCALE", "LIVE",
            "FOR", "PREVIEW", "SPECIES", "RIDE", "MODEL", "CREDIT", "LICENSE", "SOURCE", "SEAT")

# -------------------------------------------------------------------------------------------- colours
PALETTE = {
    "mud": "#d4a373", "clay": "#c0703f", "terracotta": "#c65d3b", "thatch": "#bc8a3c", "straw": "#e0c068",
    "wood": "#8b5a2b", "dark_wood": "#5a3a22", "bamboo": "#c9b458", "stone": "#9a8c7a", "rock": "#8d8d8d",
    "brick": "#b5523b", "plaster": "#efe3cf", "white": "#ffffff", "black": "#1d1d1f", "ink": "#2b2b2b",
    "metal": "#9aa3ad", "iron": "#5f6670", "gold": "#e8b923", "silver": "#c8ccd2", "copper": "#b87333",
    "leaf": "#4f8f3a", "dark_leaf": "#2f6b2a", "grass": "#6cae45", "flower": "#e85d75", "sky": "#8ecae6",
    "water": "#4a90c8", "fire": "#ff8c1a", "flame": "#ffd23f", "red": "#d62828", "orange": "#f77f00",
    "yellow": "#fcbf49", "green": "#2a9d4f", "blue": "#1d4e89", "purple": "#7b2cbf", "pink": "#ff8fab",
    "brown": "#7f5539", "grey": "#8a8f98", "gray": "#8a8f98", "cloth": "#e76f51", "saffron": "#ff9933",
    "skin": "#e0ac69", "glass": "#bde0fe", "rope": "#c8a165", "shadow": "#00000033",
}


def color(c):
    """'#aabbcc' / '#aabbccdd' / 'wood' / (r, g, b[, a]) 0..1 or 0..255 -> (r, g, b, a) 0..1"""
    if c is None:
        return (0, 0, 0, 1)
    if isinstance(c, (tuple, list)):
        v = [float(x) for x in c]
        if any(x > 1 for x in v[:3]):
            v = [x / 255.0 for x in v[:3]] + ([v[3] / 255.0 if v[3] > 1 else v[3]] if len(v) > 3 else [])
        return tuple(v[:3]) + ((v[3],) if len(v) > 3 else (1.0,))
    s = str(c).strip().lower()
    s = PALETTE.get(s.replace(" ", "_"), s)
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    try:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        a = int(s[6:8], 16) / 255.0 if len(s) >= 8 else 1.0
        return (r / 255.0, g / 255.0, b / 255.0, a)
    except (ValueError, IndexError):
        return (1.0, 0.0, 1.0, 1.0)            # magenta = "I don't know this colour"


def _hex(c):
    r, g, b, a = c
    h = "#%02x%02x%02x" % (int(max(0, min(1, r)) * 255), int(max(0, min(1, g)) * 255), int(max(0, min(1, b)) * 255))
    return h if a >= 0.999 else h + "%02x" % int(max(0, min(1, a)) * 255)


# -------------------------------------------------------------------------------------------- the pen
class Pen:
    """Everything a drawing needs. Coordinates: story units, y up, ground y = 0 (wear: head radius 100)."""

    def __init__(self, ctx, seed=7, outline=False, width=4.0, alpha=1.0, accent=None, skin=None, hair=None):
        self.ctx = ctx
        self.rand = random.Random(seed)
        self.outline = outline          # True: every shape gets a darker edge (like characters)
        self.width = width              # edge width
        self.alpha = alpha
        self.accent = _hex(color(accent or "#1d4e89"))
        self.skin = _hex(color(skin or "skin"))
        self.hair = _hex(color(hair or "#2b1d14"))

    # colours
    def color(self, c):
        return _hex(color(c))

    def dark(self, c, k=0.7):
        r, g, b, a = color(c)
        return _hex((r * k, g * k, b * k, a))

    def light(self, c, k=0.35):
        r, g, b, a = color(c)
        return _hex((r + (1 - r) * k, g + (1 - g) * k, b + (1 - b) * k, a))

    def mix(self, c1, c2, k=0.5):
        a, b = color(c1), color(c2)
        return _hex(tuple(a[i] + (b[i] - a[i]) * k for i in range(4)))

    # painting the current path
    def _src(self, c, a=1.0):
        r, g, b, al = color(c)
        self.ctx.set_source_rgba(r, g, b, al * a * self.alpha)

    def _paint(self, c, edge=None):
        ctx = self.ctx
        if c is None:
            ctx.new_path()
            return
        self._src(c)
        if self.outline or edge:
            ctx.fill_preserve()
            self._src(edge or self.dark(c, 0.6))
            ctx.set_line_width(self.width)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.stroke()
        else:
            ctx.fill()

    # shapes (c = fill colour, edge = optional edge colour)
    def rect(self, x, y, w, h, c="wood", r=0, edge=None):
        """Box with its bottom-left corner at (x, y). r = round corners."""
        ctx = self.ctx
        if r:
            r = min(r, abs(w) / 2, abs(h) / 2)
            ctx.new_sub_path()
            ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
            ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
            ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
            ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
            ctx.close_path()
        else:
            ctx.rectangle(x, y, w, h)
        self._paint(c, edge)

    def box(self, cx, y, w, h, c="wood", r=0, edge=None):
        """Box standing on y, centred on cx."""
        self.rect(cx - w / 2, y, w, h, c, r, edge)

    def poly(self, pts, c="wood", edge=None):
        """Filled shape through the points [(x, y), ...]."""
        ctx = self.ctx
        pts = list(pts)
        if len(pts) < 2:
            return
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        self._paint(c, edge)

    def tri(self, a, b, c3, c="wood", edge=None):
        self.poly([a, b, c3], c, edge)

    def circle(self, x, y, r, c="stone", edge=None):
        self.ctx.new_sub_path()
        self.ctx.arc(x, y, max(0.01, r), 0, 2 * math.pi)
        self._paint(c, edge)

    def ellipse(self, x, y, rx, ry, c="stone", edge=None, turn=0.0):
        ctx = self.ctx
        ctx.save()
        ctx.translate(x, y)
        if turn:
            ctx.rotate(turn)
        ctx.scale(max(0.01, rx), max(0.01, ry))
        ctx.new_sub_path()
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        self._paint(c, edge)

    def arc(self, x, y, r, a1, a2, c="stone", edge=None):
        """Pie slice / half circle (angles in degrees, 0 = right, 90 = up)."""
        ctx = self.ctx
        ctx.move_to(x, y)
        ctx.arc(x, y, r, math.radians(a1), math.radians(a2))
        ctx.close_path()
        self._paint(c, edge)

    def shape(self, pts, c="wood", edge=None, smooth=True):
        """Soft blob through the points (a smooth closed curve)."""
        pts = list(pts)
        n = len(pts)
        if n < 3 or not smooth:
            return self.poly(pts, c, edge)
        ctx = self.ctx
        mid = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
        ctx.move_to(*mid[-1])
        for i in range(n):
            p, m = pts[i], mid[i]
            ctx.curve_to(mid[i - 1][0] + (p[0] - mid[i - 1][0]) * 0.66, mid[i - 1][1] + (p[1] - mid[i - 1][1]) * 0.66,
                         m[0] + (p[0] - m[0]) * 0.66, m[1] + (p[1] - m[1]) * 0.66, m[0], m[1])
        ctx.close_path()
        self._paint(c, edge)

    # lines
    def line(self, pts, c="ink", w=4, cap="round"):
        ctx = self.ctx
        pts = list(pts)
        if len(pts) < 2:
            return
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        self._stroke(c, w, cap)

    def curve(self, p0, p1, p2, p3, c="ink", w=4):
        """Bezier curve from p0 to p3 (p1, p2 pull it)."""
        ctx = self.ctx
        ctx.move_to(*p0)
        ctx.curve_to(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
        self._stroke(c, w)

    def ring(self, x, y, r, c="ink", w=4):
        self.ctx.new_sub_path()
        self.ctx.arc(x, y, r, 0, 2 * math.pi)
        self._stroke(c, w)

    def _stroke(self, c, w, cap="round"):
        ctx = self.ctx
        self._src(c)
        ctx.set_line_width(max(0.1, w))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND if cap == "round" else cairo.LINE_CAP_BUTT)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke()

    # ready-made parts in the engine's look
    def roof(self, cx, y, w, h, c="thatch", lines=True):
        """Triangle roof sitting on y (thatch lines on top)."""
        self.poly([(cx - w / 2, y), (cx, y + h), (cx + w / 2, y)], c)
        if lines:
            ctx = self.ctx
            ctx.save()
            ctx.move_to(cx - w / 2, y)
            ctx.line_to(cx, y + h)
            ctx.line_to(cx + w / 2, y)
            ctx.close_path()
            ctx.clip()
            for k in range(-5, 6):
                self.line([(cx + k * w / 12, y + 4), (cx + k * w / 38, y + h - 8)], "#00000026", w=max(1.5, w / 100))
            ctx.restore()

    def door(self, cx, y=0, w=52, h=125, c="dark_wood", arch=False):
        """A door a grown-up fits through (125 tall = 1.1x a person's shoulders)."""
        if arch:
            self.rect(cx - w / 2, y, w, h - w / 2, c)
            self.arc(cx, y + h - w / 2, w / 2, 0, 180, c)
        else:
            self.rect(cx - w / 2, y, w, h, c)
        self.circle(cx + w * 0.3, y + h * 0.45, max(2, w * 0.05), self.dark(c, 0.5))

    def window(self, cx, y, w=40, h=36, c="dark_wood", bars=True, glow=None):
        self.rect(cx - w / 2, y, w, h, glow or c)
        if bars:
            self.line([(cx, y), (cx, y + h)], self.light(c, 0.3), w=max(1.5, w / 14))
            self.line([(cx - w / 2, y + h / 2), (cx + w / 2, y + h / 2)], self.light(c, 0.3), w=max(1.5, w / 14))

    def planks(self, x, y, w, h, c="wood", n=5, across=False):
        """Wooden boards (lines show each board)."""
        self.rect(x, y, w, h, c)
        for k in range(1, n):
            if across:
                yy = y + h * k / n
                self.line([(x, yy), (x + w, yy)], self.dark(c, 0.7), w=max(1.2, h / 60))
            else:
                xx = x + w * k / n
                self.line([(xx, y), (xx, y + h)], self.dark(c, 0.7), w=max(1.2, w / 60))

    def bricks(self, x, y, w, h, c="brick", bw=34, bh=16):
        self.rect(x, y, w, h, c)
        rows = max(1, int(h / bh))
        for i in range(1, rows + 1):
            yy = y + i * h / rows
            self.line([(x, yy), (x + w, yy)], self.dark(c, 0.75), w=1.5)
        for i in range(rows):
            off = (bw / 2) if i % 2 else 0
            xx = x + off + bw
            while xx < x + w:
                self.line([(xx, y + i * h / rows), (xx, y + (i + 1) * h / rows)], self.dark(c, 0.75), w=1.5)
                xx += bw

    def stripes(self, x, y, w, h, c1="red", c2="white", n=6, across=False):
        for k in range(n):
            col = c1 if k % 2 == 0 else c2
            if across:
                self.rect(x, y + h * k / n, w, h / n + 0.5, col)
            else:
                self.rect(x + w * k / n, y, w / n + 0.5, h, col)

    def leaves(self, x, y, r, c="leaf", bumps=8, spots=True):
        """Leafy crown / bush: a round cloud of leaves."""
        rnd = random.Random(int(x * 7 + y * 13 + r))
        for k in range(bumps):
            a = 2 * math.pi * k / bumps + rnd.uniform(-0.2, 0.2)
            self.circle(x + math.cos(a) * r * 0.55, y + math.sin(a) * r * 0.45, r * rnd.uniform(0.42, 0.55),
                        self.dark(c, rnd.uniform(0.82, 1.0)))
        self.circle(x, y, r * 0.62, c)
        if spots:
            for _ in range(5):
                self.circle(x + rnd.uniform(-r, r) * 0.5, y + rnd.uniform(0, r) * 0.5, r * 0.09, self.light(c, 0.35))

    def trunk(self, x, y, w, h, c="wood", lean=0.0):
        self.poly([(x - w / 2, y), (x - w * 0.35 + lean, y + h), (x + w * 0.35 + lean, y + h), (x + w / 2, y)], c)

    def wheel(self, x, y, r, c="dark_wood", spokes=6, turn=0.0, rim=None):
        """Cart / car wheel; turn = how far it has rolled (radians)."""
        self.circle(x, y, r, rim or self.dark(c, 0.7))
        self.circle(x, y, r * 0.8, c)
        for k in range(spokes):
            a = turn + 2 * math.pi * k / spokes
            self.line([(x, y), (x + math.cos(a) * r * 0.8, y + math.sin(a) * r * 0.8)], self.dark(c, 0.6),
                      w=max(1.5, r / 7))
        self.circle(x, y, r * 0.18, self.dark(c, 0.5))

    def flame(self, x, y, h, t=0.0, c="fire"):
        """A flickering flame (pass t so it moves)."""
        f = 1 + 0.12 * math.sin(t * 13 + x) + 0.07 * math.sin(t * 29 + y)
        sway = h * 0.08 * math.sin(t * 9 + x * 0.1)
        w = h * 0.42
        self.shape([(x - w, y + h * 0.15), (x - w * 0.5, y + h * 0.55 * f), (x + sway, y + h * f),
                    (x + w * 0.55, y + h * 0.5 * f), (x + w, y + h * 0.12), (x, y)], c)
        self.shape([(x - w * 0.5, y + h * 0.12), (x + sway * 0.6, y + h * 0.62 * f), (x + w * 0.5, y + h * 0.12),
                    (x, y + h * 0.02)], "flame")

    def glow(self, x, y, r, c="flame", strength=0.5):
        """Soft light around a lamp / fire."""
        rr, gg, bb, _ = color(c)
        g = cairo.RadialGradient(x, y, 0, x, y, r)
        g.add_color_stop_rgba(0, rr, gg, bb, strength * self.alpha)
        g.add_color_stop_rgba(1, rr, gg, bb, 0)
        self.ctx.set_source(g)
        self.ctx.arc(x, y, r, 0, 2 * math.pi)
        self.ctx.fill()

    def gradient(self, pts, c1, c2, vertical=True):
        """Shape filled with a colour fade (bottom c1 -> top c2, or left -> right)."""
        pts = list(pts)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        a, b = color(c1), color(c2)
        g = (cairo.LinearGradient(0, min(ys), 0, max(ys)) if vertical else
             cairo.LinearGradient(min(xs), 0, max(xs), 0))
        g.add_color_stop_rgba(0, a[0], a[1], a[2], a[3] * self.alpha)
        g.add_color_stop_rgba(1, b[0], b[1], b[2], b[3] * self.alpha)
        ctx = self.ctx
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        ctx.set_source(g)
        ctx.fill()

    def shade(self, pts, k=0.18):
        """Darken a part (the side in shadow)."""
        self.poly(pts, (0, 0, 0, k))

    def shine(self, pts, k=0.18):
        """Lighten a part (the side in the light)."""
        self.poly(pts, (1, 1, 1, k))

    # ---------------------------------------------------------------- more shapes
    def ngon(self, x, y, r, n=6, c="stone", turn=0.0, edge=None):
        """A regular shape with n corners (triangle 3, square 4, hexagon 6 ...)."""
        a0 = math.radians(turn) + math.pi / 2
        self.poly([(x + r * math.cos(a0 + 2 * math.pi * k / n), y + r * math.sin(a0 + 2 * math.pi * k / n))
                   for k in range(int(n))], c, edge)

    def star(self, x, y, r, c="gold", points=5, inner=0.45, turn=0.0, edge=None):
        a0 = math.radians(turn) + math.pi / 2
        pts = []
        for k in range(int(points) * 2):
            rr = r if k % 2 == 0 else r * inner
            a = a0 + math.pi * k / points
            pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
        self.poly(pts, c, edge)

    def pill(self, x, y, w, h, c="skin", edge=None):
        """A rounded bar (bottom-left corner at x, y)."""
        self.rect(x, y, w, h, c, r=min(w, h) / 2, edge=edge)

    def heart(self, x, y, s=40, c="red", edge=None):
        """A heart shape (x, y = its bottom point)."""
        ctx = self.ctx
        ctx.move_to(x, y)
        ctx.curve_to(x - s * 1.2, y + s * 0.7, x - s * 0.6, y + s * 1.6, x, y + s * 1.1)
        ctx.curve_to(x + s * 0.6, y + s * 1.6, x + s * 1.2, y + s * 0.7, x, y)
        ctx.close_path()
        self._paint(c, edge)

    def crescent(self, x, y, r, c="#f5f3ce", cut=0.35, turn=0.0):
        """A moon crescent."""
        ctx = self.ctx
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(math.radians(turn))
        ctx.new_sub_path()
        ctx.arc(0, 0, r, 0, 2 * math.pi)
        ctx.new_sub_path()
        ctx.arc_negative(r * cut * 1.4, r * cut * 0.4, r * 0.95, 2 * math.pi, 0)
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.restore()
        self._paint(c)
        self.ctx.set_fill_rule(cairo.FILL_RULE_WINDING)

    def spiral(self, x, y, r, c="ink", w=3, turns=3):
        pts = [(x + r * k / 200 * math.cos(turns * 2 * math.pi * k / 200),
                y + r * k / 200 * math.sin(turns * 2 * math.pi * k / 200)) for k in range(201)]
        self.line(pts, c, w)

    def dashes(self, pts, c="ink", w=3, dash=12, gap=8):
        """A dashed line (road marks, stitches, a dotted path)."""
        self.ctx.set_dash([dash, gap])
        self.line(pts, c, w, cap="butt")
        self.ctx.set_dash([])

    def arrow(self, x0, y0, x1, y1, c="red", w=6, head=22):
        self.line([(x0, y0), (x1, y1)], c, w)
        a = math.atan2(y1 - y0, x1 - x0)
        self.poly([(x1 + head * 0.4 * math.cos(a), y1 + head * 0.4 * math.sin(a)),
                   (x1 - head * math.cos(a - 0.5), y1 - head * math.sin(a - 0.5)),
                   (x1 - head * math.cos(a + 0.5), y1 - head * math.sin(a + 0.5))], c)

    def zigzag(self, x0, y, x1, c="ink", h=10, n=10, w=3):
        self.line([(x0 + (x1 - x0) * k / n, y + (h if k % 2 else 0)) for k in range(int(n) + 1)], c, w)

    def dots(self, x, y, w, h, c="white", r=3, gap=14):
        """A pattern of dots filling a box (cloth prints, stars on a sign)."""
        yy, row = y + gap / 2, 0
        while yy < y + h:
            xx = x + gap / 2 + (gap / 2 if row % 2 else 0)
            while xx < x + w:
                self.circle(xx, yy, r, c)
                xx += gap
            yy += gap
            row += 1

    def text(self, x, y, words, size=30, c="ink", bold=True, center=True, font="sans-serif"):
        """Words on a sign, a shop board, a book (Hindi works too)."""
        ctx = self.ctx
        from . import textfx
        if textfx.needs(str(words)):                         # Hindi, Tamil ...: shaped with the bundled Noto fonts
            from PIL import Image, ImageDraw
            import numpy as np
            S = 4.0
            fs = max(4, int(size * S))
            w = textfx.width(str(words), fs)
            img = Image.new("RGBA", (int(w) + 12, int(fs * 1.7)), (0, 0, 0, 0))
            r_, g_, b_, a_ = color(c)
            textfx.draw_line(ImageDraw.Draw(img), 6, fs * 1.2, str(words), fs,
                             (int(r_ * 255), int(g_ * 255), int(b_ * 255), int(a_ * self.alpha * 255)))
            a = np.asarray(img, dtype=np.uint16)
            al = a[..., 3:4]
            pre = (a[..., :3] * al // 255).astype(np.uint8)
            bgra = np.dstack([pre[..., 2], pre[..., 1], pre[..., 0], a[..., 3].astype(np.uint8)]).copy()
            hh, ww = bgra.shape[:2]
            surf = cairo.ImageSurface.create_for_data(memoryview(bgra), cairo.FORMAT_ARGB32, ww, hh, ww * 4)
            self._keep = getattr(self, "_keep", []) + [bgra, surf]
            ctx.save()
            ctx.translate(x - (w / S / 2 if center else 0), y)
            ctx.scale(1 / S, -1 / S)
            ctx.set_source_surface(surf, -6, -fs * 1.2)
            ctx.paint()
            ctx.restore()
            return
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(1, -1)                                     # the page is y-up; text must not be upside down
        fam = font
        ctx.select_font_face(fam, cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(size)
        ext = ctx.text_extents(str(words))
        ctx.move_to(-ext.x_advance / 2 if center else 0, 0)
        self._src(c)
        ctx.show_text(str(words))
        ctx.restore()

    def cloud(self, x, y, w=200, c="white"):
        rnd = random.Random(int(x * 3 + y))
        for k in range(5):
            self.circle(x + (k - 2) * w / 5, y + rnd.uniform(0, w * 0.1), w * rnd.uniform(0.16, 0.24), c)
        self.rect(x - w / 2, y - w * 0.12, w, w * 0.14, c, r=w * 0.07)

    def grass(self, x, y, w=60, c="grass", n=9, h=30):
        """A tuft of grass blades."""
        rnd = random.Random(int(x * 7 + y))
        for k in range(int(n)):
            bx = x - w / 2 + w * k / max(1, n - 1)
            self.line([(bx, y), (bx + rnd.uniform(-8, 8), y + h * rnd.uniform(0.6, 1.2))],
                      self.dark(c, rnd.uniform(0.8, 1.1)), 3)

    def pot(self, x, y=0, r=40, c="clay", h=None):
        """A round clay pot (matka) standing on y."""
        h = h or r * 1.6
        self.shape([(x - r * 0.45, y), (x - r, y + h * 0.4), (x - r * 0.6, y + h * 0.82), (x - r * 0.5, y + h),
                    (x + r * 0.5, y + h), (x + r * 0.6, y + h * 0.82), (x + r, y + h * 0.4), (x + r * 0.45, y)], c)
        self.ellipse(x, y + h, r * 0.5, r * 0.12, self.dark(c, 0.5))
        self.shade([(x + r * 0.3, y + 2), (x + r * 0.95, y + h * 0.4), (x + r * 0.55, y + h * 0.8)], 0.12)

    def rope(self, x0, y0, x1, y1, c="rope", w=5, sag=20):
        """A hanging rope / clothes line between two points."""
        self.curve((x0, y0), (x0 + (x1 - x0) / 3, y0 - sag), (x0 + 2 * (x1 - x0) / 3, y1 - sag), (x1, y1), c, w)

    def flag(self, x, y, w=120, h=80, c="saffron", t=0.0, pole="dark_wood"):
        """A waving flag on a pole (x, y = bottom of the pole)."""
        self.rect(x - 3, y, 6, h * 3, pole)
        top = y + h * 3
        from .realworld import wind as _wind              # flies downwind; hangs when the air is still
        wnd = _wind()
        d = wnd.direction
        lift = max(0.15, min(1.0, wnd.strength * (1.0 + wnd.gust(t, x)) / 1.6))
        fq = 4.0 + 1.5 * min(4.0, wnd.strength)
        pts = []
        for k in range(11):
            u = k / 10
            pts.append((x + d * w * u * (0.35 + 0.65 * lift),
                        top - h * 0.05 - (1 - lift) * h * 0.9 * u + 8 * lift * u * math.sin(t * fq - u * 5)))
        for k in range(10, -1, -1):
            u = k / 10
            pts.append((x + d * w * u * (0.35 + 0.65 * lift),
                        top - h - (1 - lift) * h * 0.9 * u + 8 * lift * u * math.sin(t * fq - u * 5)))
        self.poly(pts, c)

    def ripples(self, x, y, w=200, c="#ffffff99", t=0.0, n=4):
        """Moving ripple lines on water."""
        for k in range(n):
            u = (t * 0.4 + k / n) % 1.0
            rr = w * 0.5 * u
            self.ellipse(x, y, max(1, rr), max(1, rr * 0.18), None, edge=c)

    def particles(self, x, y, n=12, c="white", size=4, speed=40, t=0.0, spread=40, life=2.0, rise=1.0, grow=0.0):
        """Little floating dots: dust, sparks, bubbles, fireflies (same for the same t)."""
        rnd = random.Random(int(x * 3 + y * 7 + n))
        r0, g0, b0, a0 = color(c)
        for i in range(int(n)):
            age = (float(t) + rnd.random() * life) % life
            k = age / life
            from .realworld import wind as _wind                 # carried by the scene wind
            self.circle(x + rnd.uniform(-1, 1) * spread * (0.3 + k) + _wind().speed(t) * 0.3 * age,
                        y + rise * speed * age, size * (1 + grow * k),
                        (r0, g0, b0, a0 * (1 - k)))

    def smoke(self, x, y, n=8, size=12, t=0.0):
        self.particles(x, y, n, "#9a9a9aaa", size, 35, t, spread=12, life=3.0, grow=1.5)

    def sparkle(self, x, y, r=14, c="#fff7b0", t=0.0):
        """A twinkling star of light."""
        k = 0.6 + 0.4 * math.sin(t * 8 + x)
        self.star(x, y, r * k, c, points=4, inner=0.25)

    def radial(self, x, y, r, c1="white", c2="#ffffff00"):
        """A round colour fade (a sun, a lamp's light, a shiny spot)."""
        a, b = color(c1), color(c2)
        g = cairo.RadialGradient(x, y, 0, x, y, r)
        g.add_color_stop_rgba(0, a[0], a[1], a[2], a[3] * self.alpha)
        g.add_color_stop_rgba(1, b[0], b[1], b[2], b[3] * self.alpha)
        self.ctx.set_source(g)
        self.ctx.arc(x, y, r, 0, 2 * math.pi)
        self.ctx.fill()

    def scale(self, sx, sy=None):
        self.ctx.scale(sx, sx if sy is None else sy)

    def rotate(self, deg):
        self.turn(deg)

    def loop(self, t, duration=1.0):
        return (float(t) / max(1e-6, float(duration))) % 1.0

    def pingpong(self, t, duration=1.0):
        u = self.loop(t, duration * 2.0)
        return 1.0 - abs(1.0 - 2.0 * u)

    # places: every  with pen.thing("name"):  block becomes its own real thing
    def thing(self, name, z=None, depth=None, abilities=None, states=None, animated=None, height=None, kind=None):
        """KIND = "place": the drawing inside this block is one thing of the place (its own picture, its own
        depth, people can use it). z = depth (0 front .. 1000 back of the stage, 1500+ far away) or
        depth = "front" / "middle" / "back" / "far". abilities = ["sit", "climb", "hide", "open" ...].
        states = ["normal", "fire"] (the state given to draw()). animated = seconds."""
        return _Thing(self, str(name), dict(z=z, depth=depth, abilities=abilities, states=states,
                                            animated=animated, height=height, kind=kind))

    # moving things
    def move(self, x, y):
        self.ctx.translate(x, y)

    def turn(self, deg):
        self.ctx.rotate(math.radians(deg))

    def grow(self, sx, sy=None):
        self.ctx.scale(sx, sx if sy is None else sy)

    def push(self):
        """Save position / turn (use with pen.pop())."""
        self.ctx.save()

    def pop(self):
        self.ctx.restore()

    def wave(self, t, speed=1.0, size=1.0, phase=0.0):
        """-size .. +size, smoothly (handy for swinging, bobbing, blinking lights)."""
        return size * math.sin(2 * math.pi * speed * t + phase)


class _Thing:
    """with pen.thing(...):  - while a place is being cut into things, each block is drawn on its own layer."""

    def __init__(self, pen, name, opts):
        self.pen, self.name, self.opts = pen, name, opts

    def __enter__(self):
        cap = getattr(self.pen, "_things", None)
        if cap is not None:
            self.pen.ctx.save()
            self.pen.ctx.push_group()
        return self.pen

    def __exit__(self, *exc):
        cap = getattr(self.pen, "_things", None)
        if cap is not None:
            pat = self.pen.ctx.pop_group()
            self.pen.ctx.restore()
            if exc[0] is None:
                name = _clean(self.name) or f"thing{len(cap) + 1}"
                while name in cap:
                    name += "_2"
                cap[name] = (pat.get_surface(), self.opts)
        return False


# -------------------------------------------------------------------------------------------- reading files
def _clean(name):
    import re
    n = "".join(c if c.isalnum() or c in "_-" else "_" for c in str(name).lower().strip())
    return re.sub(r"_+", "_", n).strip("_-")[:40]


def path_of(name):
    return os.path.join(DIR, _clean(name) + ".py")


def settings_of(code):
    """Read KIND / DESCRIPTION / STATES ... without running anything."""
    out = {}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return out
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            k = node.targets[0].id
            if k in SETTINGS:
                try:
                    out[k] = ast.literal_eval(node.value)
                except Exception:
                    pass
    kind = str(out.get("KIND", "object")).lower()
    out["KIND"] = kind if kind in KINDS else "object"
    st = out.get("STATES") or []
    out["STATES"] = [str(s) for s in st] if isinstance(st, (list, tuple)) else []
    try:
        out["ANIMATED"] = max(0.0, min(MAX_ANIM, float(out.get("ANIMATED") or 0)))
    except (TypeError, ValueError):
        out["ANIMATED"] = 0.0
    ab = out.get("ABILITIES") or []
    out["ABILITIES"] = [str(a) for a in ab] if isinstance(ab, (list, tuple)) else []
    return out


def list_code():
    """{name: {"kind", "description", "states", "animated", "file"}}"""
    data = {}
    if not os.path.isdir(DIR):
        return data
    for f in sorted(os.listdir(DIR)):
        if not f.endswith(".py") or f.startswith("_"):
            continue
        p = os.path.join(DIR, f)
        try:
            with open(p, encoding="utf-8") as fh:
                s = settings_of(fh.read())
        except OSError:
            continue
        data[f[:-3]] = {"kind": s["KIND"], "description": s.get("DESCRIPTION", ""), "states": s["STATES"],
                        "animated": s["ANIMATED"], "file": p, "hide_hair": bool(s.get("HIDE_HAIR")),
                        "for": str(s.get("FOR") or "").lower().strip().replace(" ", "_"),
                        "species": s.get("SPECIES") if isinstance(s.get("SPECIES"), dict) else None,
                        "ride": s.get("RIDE") if isinstance(s.get("RIDE"), dict) else None}
    return data


def wearables():
    return sorted(n for n, m in list_code().items() if m["kind"] == "wear")


def read(name):
    p = path_of(name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# -------------------------------------------------------------------------------------------- safety
BAD_NAMES = {"open", "eval", "exec", "compile", "globals", "locals", "vars", "getattr", "setattr", "delattr",
             "input", "breakpoint", "__import__", "memoryview", "help", "exit", "quit", "type", "super",
             "classmethod", "staticmethod", "property", "object", "dir"}
BAD_ATTRS = {"write_to_png", "get_target", "get_group_target", "create_similar", "create_similar_image",
             "map_to_image", "finish", "flush", "get_data", "set_source_surface"}
OK_IMPORTS = {"math", "random", "colorsys"}
SAFE_BUILTINS = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k) for k in (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "int", "isinstance", "len", "list",
    "map", "max", "min", "pow", "print", "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip",
    "ValueError", "ZeroDivisionError", "Exception", "True", "False", "None")}


def check_code(code):
    """Problems (list of strings) - empty list = fine to run."""
    try:
        tree = ast.parse(code)
    except SyntaxError as ex:
        return [f"line {ex.lineno}: {ex.msg}"]
    probs = []
    has_draw = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for m in mods:
                if m.split(".")[0] not in OK_IMPORTS:
                    probs.append(f"line {node.lineno}: only math and random can be imported (not {m})")
        elif isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr in BAD_ATTRS):
            probs.append(f"line {node.lineno}: '{node.attr}' is not allowed in drawings")
        elif isinstance(node, ast.Name) and (node.id in BAD_NAMES or node.id.startswith("__")):
            probs.append(f"line {node.lineno}: '{node.id}' is not allowed in drawings")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            probs.append(f"line {node.lineno}: global / nonlocal are not allowed")
        elif isinstance(node, ast.FunctionDef) and node.name == "draw":
            has_draw = True
    if not has_draw:
        probs.append("there is no  def draw(pen, t, state):  function")
    return probs


def _import(name, *a, **k):
    if name.split(".")[0] not in OK_IMPORTS:
        raise ImportError(f"only math and random can be imported, not {name}")
    return __import__(name, *a, **k)


def compile_code(code, name="drawing"):
    """-> draw function (runs the top of the file with safe builtins). Raises ValueError on problems."""
    probs = check_code(code)
    if probs:
        raise ValueError("; ".join(probs[:4]))
    b = dict(SAFE_BUILTINS)
    b["__import__"] = _import
    env = {"__builtins__": b, "math": math, "random": random, "__name__": "drawing_" + _clean(name)}
    exec(compile(code, f"<{name}>", "exec"), env)
    fn = env.get("draw")
    if not callable(fn):
        raise ValueError("there is no  def draw(pen, t, state):  function")
    return fn


def _call(fn, pen, t, state):
    import inspect
    try:
        n = len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        n = 3
    if n >= 3:
        return fn(pen, t, state)
    if n == 2:
        return fn(pen, t)
    return fn(pen)


# -------------------------------------------------------------------------------------------- drawing to pictures
def _record(fn, t, state, wear=False, seed=7):
    """Draw once onto an unbounded recording surface (story units, y up). -> (surface, extents x0, y0, x1, y1)"""
    rec = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)
    ctx = cairo.Context(rec)
    ctx.scale(1, -1)                                    # y up
    pen = Pen(ctx, seed=seed, outline=wear, width=5.0 if wear else 4.0)
    _call(fn, pen, t, state)
    x0, y0, w, h = rec.ink_extents()
    return rec, (x0, -(y0 + h), x0 + w, -y0)            # back to y-up extents


def frames_for(fn, settings, state):
    """[(recording, extents)] for a state (one frame, or ANIMATED seconds at FPS)."""
    dur = settings.get("ANIMATED") or 0.0
    n = max(1, int(round(dur * FPS))) if dur else 1
    wear = settings.get("KIND") == "wear"
    if is3d(settings.get("KIND")):
        from . import code3d
        return [code3d.front_recording(code3d.build(fn, (k / FPS) if n > 1 else 0.0, state))
                for k in range(n)]
    return [_record(fn, (k / FPS) if n > 1 else 0.0, state, wear) for k in range(n)]


def is3d(kind):
    return str(kind or "").endswith("3d")


def base_kind(kind):
    k = str(kind or "object")
    return k[:-2] if k.endswith("3d") else k


def _bounds(frames, ground=True):
    x0 = min(f[1][0] for f in frames)
    x1 = max(f[1][2] for f in frames)
    y0 = min(f[1][1] for f in frames)
    y1 = max(f[1][3] for f in frames)
    half = max(abs(x0), abs(x1), 1.0)                   # keep x = 0 in the middle of the picture
    bottom = 0.0 if ground else y0
    if ground and y0 > 0:
        bottom = 0.0                                    # floating things keep their gap above the ground
    return -half, bottom, half, max(y1, bottom + 1.0)


def _to_png(rec, box, px, pad=2):
    """Render a recording into a PIL image covering box (x0, y0, x1, y1) at px pixels per unit."""
    from PIL import Image
    x0, y0, x1, y1 = box
    k = max(1, math.ceil(px - 1e-6))
    if abs(px - k) > 1e-6 and (x1 - x0) * (y1 - y0) * k * k < 2.4e7:   # painted at a whole scale, then made smaller:
        big = _to_png(rec, box, float(k), pad)           # a 3D recording replayed at a fractional scale opens hairline
                                                         # seams between its faces (cairo's blended patches)
        W = max(1, int(math.ceil((x1 - x0) * px)) + 2 * pad)
        H = max(1, int(math.ceil((y1 - y0) * px)) + pad)
        return big.resize((W, H), Image.LANCZOS)
    W = max(1, int(math.ceil((x1 - x0) * px)) + 2 * pad)
    H = max(1, int(math.ceil((y1 - y0) * px)) + pad)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.translate(pad, 0)
    ctx.scale(px, px)
    ctx.translate(-x0, y1)                              # top of the box at the top of the picture
    ctx.rectangle(x0, -y1, x1 - x0, y1 - y0 + 0.001)    # nothing below the ground line
    ctx.clip()
    ctx.set_source_surface(rec, 0, 0)
    ctx.paint()
    surf.flush()
    import numpy as np
    a = np.ndarray((H, surf.get_stride() // 4, 4), np.uint8, surf.get_data())[:, :W].copy()
    rgba = a[..., [2, 1, 0, 3]].astype(np.float32)
    al = rgba[..., 3:4]
    rgba[..., :3] = np.where(al > 0, rgba[..., :3] * 255.0 / np.maximum(al, 1), 0)   # un-premultiply
    return Image.fromarray(rgba.clip(0, 255).astype(np.uint8), "RGBA")


def _px_for(box, animated):
    side = max(box[2] - box[0], box[3] - box[1])
    cap = 1000 if animated else 2000
    return max(0.25, min(1.25 if animated else PX, cap / max(side, 1.0)))


def preview_png(code, state=None, t=None, name="drawing", width=640, height=400, person=True, frame=None,
                palette=None):
    """PNG bytes: the drawing at real size next to a stick person (wear: on a head)."""
    import io
    from . import palette as _pal
    _pal.use(palette or None)                            # 🎨 the Look-in-a-world-palette menu
    s = settings_of(code)
    fn = compile_code(code, name)
    if s["KIND"] in CHAR_KINDS:                          # a 3D person / animal: many camera angles, any pose
        from . import char3d
        return char3d.preview_png(fn, s, state, t, frame, max(width, 900), max(height, 560))
    if is3d(s["KIND"]):
        return preview3d_png(fn, s, state, t, frame, width, height)
    if s["KIND"] in ("place", "objects"):
        return preview_place_png(fn, s, state, t, frame, width, height)
    states = s["STATES"]
    st = state if state else (states[0] if states else None)
    wear = s["KIND"] == "wear"
    dur = s["ANIMATED"]
    tt = float(t) if t is not None else (0.0 if not dur else (float(frame or 0) / FPS) % max(dur, 1e-3))
    rec, ext = _record(fn, tt, st, wear)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(0.95, 0.94, 0.9)
    ctx.paint()
    if wear:
        # a head (radius 100) in the middle, face to the right, and the wearable on top
        box = (min(ext[0], -130), min(ext[1], -130), max(ext[2], 130), max(ext[3], 130))
        k = min(width / (box[2] - box[0]), height / (box[3] - box[1])) * 0.82
        ctx.translate(width / 2 - (box[0] + box[2]) / 2 * k, height / 2 + (box[1] + box[3]) / 2 * k)
        ctx.scale(k, -k)
        ctx.arc(0, 0, 100, 0, 2 * math.pi)
        ctx.set_source_rgb(0.88, 0.67, 0.41)
        ctx.fill_preserve()
        ctx.set_source_rgb(0.5, 0.35, 0.2)
        ctx.set_line_width(5)
        ctx.stroke()
        ctx.arc(45, 15, 10, 0, 2 * math.pi)
        ctx.set_source_rgb(0.1, 0.1, 0.1)
        ctx.fill()
        ctx.move_to(40, -45)
        ctx.curve_to(55, -55, 70, -55, 80, -40)
        ctx.set_line_width(5)
        ctx.stroke()
        ctx.move_to(0, -100)
        ctx.line_to(0, -170)
        ctx.stroke()
    else:
        x0, y0, x1, y1 = ext
        half = max(abs(x0), abs(x1), 60)
        top = max(y1, 320)
        bottom = min(y0, 0)
        left = -half - (190 if person else 20)
        right = half + 20
        k = min(width / (right - left), height / (top - bottom + 40)) * 0.92
        ctx.translate(width / 2 - (left + right) / 2 * k, height - 24 - (-bottom) * k)
        ctx.scale(k, -k)
        ctx.set_source_rgb(0.72, 0.8, 0.6)             # ground
        ctx.rectangle(left - 2000, -2000, 6000, 2000)
        ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.25)
        ctx.set_line_width(2 / k)
        ctx.move_to(left - 2000, 0)
        ctx.line_to(right + 2000, 0)
        ctx.stroke()
        if person:                                      # a 300-tall person for size
            px_ = -half - 95
            ctx.set_source_rgb(0.15, 0.15, 0.2)
            ctx.set_line_width(12)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            for a, b in (((0, 150), (0, 235)), ((0, 150), (-30, 0)), ((0, 150), (30, 0)),
                         ((0, 225), (-40, 150)), ((0, 225), (40, 150))):
                ctx.move_to(px_ + a[0], a[1])
                ctx.line_to(px_ + b[0], b[1])
            ctx.stroke()
            ctx.arc(px_, 268, 32, 0, 2 * math.pi)
            ctx.fill()
    ctx.save()
    ctx.scale(1, -1)
    ctx.set_source_surface(rec, 0, 0)
    ctx.paint()
    ctx.restore()
    surf.flush()
    buf = io.BytesIO()
    surf.write_to_png(buf)
    return buf.getvalue()


def save(name, code, description=None):
    """(see _save)"""
    from . import images as _im
    try:
        return _save(name, code, description)
    finally:
        _im.refresh()


def _save(name, code, description=None):
    """Store the code (assets/code/) and, for objects / props / vehicles, the pictures (assets/images/).
    Returns {"name", "kind", "pictures": [...], "height"}."""
    from . import images
    name = _clean(name)
    if not name:
        raise ValueError("give it a name")
    s = settings_of(code)
    fn = compile_code(code, name)
    desc = description if description is not None else str(s.get("DESCRIPTION") or name.replace("_", " "))
    os.makedirs(DIR, exist_ok=True)
    with open(path_of(name), "w", encoding="utf-8") as fh:
        fh.write(code if code.endswith("\n") else code + "\n")
    _CACHE.pop(name, None)
    if s["KIND"] in CHAR_KINDS:                          # tried in a few poses; nothing to draw into pictures
        from . import char3d
        try:
            n = char3d.check(fn, s)
        except Exception as ex:
            raise ValueError(f"the character code does not work yet: {ex}")
        return {"name": name, "kind": s["KIND"], "pictures": [], "is3d": True, "height": 0, "shapes": n,
                "for": str(s.get("FOR") or ("human" if s["KIND"] == "character3d" else "quadruped"))}
    if base_kind(s["KIND"]) in ("place", "objects"):
        return save_place(name, code, s, fn, desc, mode=base_kind(s["KIND"]))
    out = {"name": name, "kind": s["KIND"], "pictures": [], "is3d": is3d(s["KIND"])}
    if s["KIND"] == "wear":
        _drop_pictures(name)
        return out
    states = s["STATES"] or [None]
    import time as _time
    t0 = _time.perf_counter()
    all_frames = {st: frames_for(fn, s, st) for st in states}
    per_frame = (_time.perf_counter() - t0) * 1000.0 / max(1, sum(len(v) for v in all_frames.values()))
    live = s.get("LIVE", True) is not False and per_frame <= (4000.0 if is3d(s["KIND"]) else LIVE_MAX_MS)
    box = _bounds([f for fr in all_frames.values() for f in fr])
    if s.get("HEIGHT"):                                   # HEIGHT = 450 -> stretch the drawing to that height
        try:
            want = float(s["HEIGHT"])
        except (TypeError, ValueError):
            want = 0
    else:
        want = 0
    px = _px_for(box, s["ANIMATED"] > 0)
    height = box[3] - box[1]
    for i, st in enumerate(states):
        pic = name if i == 0 else f"{name}_{_clean(st)}"
        ims = [_to_png(rec, box, px) for rec, _ in all_frames[st]]
        _write_picture(pic, ims)
        meta = {"description": desc if i == 0 else f"{desc} - {st}",
                "kind": base_kind(s["KIND"]) if i == 0 else "state",
                "height": round(want or height, 1), "made_by": "code", "code": name,
                "live": live, "box": [round(v, 2) for v in box], "draw_state": st}
        if is3d(s["KIND"]):
            meta["is3d"] = True
            if i == 0:
                from . import code3d as _c3
                f0 = _c3.build(fn, 0.0, st)
                wp, fp = _c3.walk_polys(f0), _c3.footprint(f0)
                if wp:
                    meta["walk"] = wp
                    if not s["ABILITIES"]:
                        meta["abilities"] = ["stand"]
                if fp:
                    meta["foot"] = fp
                ft = _c3.feet(f0)
                if ft and len(ft) > 1:
                    meta["feet"] = ft                        # separate pieces on the ground: walk between them
                if _c3.LAST_DOORS:                           # doors people walk in and out through
                    meta["doors"] = [list(d) for d in _c3.LAST_DOORS]
        if i == 0 and isinstance(s.get("SEAT"), (int, float)):   # where people sit (a throne, a sofa)
            meta["seat"] = float(s["SEAT"])
        if s["ABILITIES"] and i == 0:
            meta["abilities"] = s["ABILITIES"]
        if i == 0 and base_kind(s["KIND"]) == "vehicle" and isinstance(s.get("RIDE"), dict):
            meta["ride"] = ride_settings(s["RIDE"])
        if len(ims) > 1:
            meta["durations"] = [round(1000.0 / FPS, 1)] * len(ims)
            meta["alpha"] = True
        if box[1] < 0:
            meta["ground"] = round(box[3] / (box[3] - box[1]), 4)
        if i == 0 and len(states) > 1:
            meta["states"] = {str(x): f"{name}_{_clean(x)}" for x in states[1:]}
        if i > 0:
            meta["state_of"], meta["state"] = name, str(st)
        with open(os.path.join(images.DIR, pic + ".json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2, ensure_ascii=False)
            fh.flush()
        out["pictures"].append(pic)
    images._LIST["stamp"] = None
    images.list_images()
    out["height"] = round(want or height, 1)
    out["live"] = live
    if not live and s.get("LIVE", True) is not False:
        out["notes"] = [f"drawing takes {per_frame:.0f} ms a frame - shown from its picture (fast) instead of live"]
    return out


RIDE_POSES = ("pedal", "sit", "stand", "row")


def ride_settings(r):
    """RIDE = {"seats": [[-20, 95, 0]], "pose": "pedal", "speed": 260, "sound": None, "push": 1}
    seats = the seat POINTS [x, y, z] of your drawing: x along it (+ = front), y = height of the seat top,
      z = side (+ = away from the camera). The rider's hips go exactly there. (Just x: y = seat_height, z = 0.)
    pose: pedal (bicycle, the legs go round while it moves), sit (cart, car), stand (raft, scooter), row (boat)."""
    out = {}
    for k in ("seat_height", "speed"):
        if isinstance(r.get(k), (int, float)):
            out[k] = float(r[k])
    sh = out.get("seat_height", 60.0)
    seats = r.get("seats", [0])
    if isinstance(seats, (int, float)):
        seats = [0.0] * max(1, int(seats))
    pts = []
    for p in seats if isinstance(seats, (list, tuple)) else []:
        if isinstance(p, (int, float)):                    # just x: on the middle line, at seat_height
            pts.append([float(p), sh, 0.0])
        elif isinstance(p, dict):
            pts.append([float(p.get("x", 0)), float(p.get("y", sh)), float(p.get("z", 0))])
        elif isinstance(p, (list, tuple)) and p and all(isinstance(v, (int, float)) for v in p):
            q = list(p) + [None, None]
            pts.append([float(q[0]), float(q[1]) if q[1] is not None else sh, float(q[2]) if q[2] is not None else 0.0])
    out["seats"] = pts[:12] or [[0.0, sh, 0.0]]
    out["seat_height"] = sh
    pose = str(r.get("pose", "sit")).lower()
    out["pose"] = pose if pose in RIDE_POSES else "sit"
    if r.get("sound"):
        out["sound"] = str(r["sound"])
    if isinstance(r.get("push"), (int, float)):
        out["push"] = int(r["push"])
    if r.get("water"):
        out["water"] = True
    return out


def _write_picture(pic, ims):
    from . import images as _im
    _im.refresh()
    from . import images
    os.makedirs(images.DIR, exist_ok=True)
    for e in images.EXTS:
        p = os.path.join(images.DIR, pic + e)
        if os.path.exists(p):
            os.remove(p)
    if len(ims) > 1:
        ims[0].save(os.path.join(images.DIR, pic + ".webp"), save_all=True, append_images=ims[1:],
                    duration=int(1000 / FPS), loop=0, lossless=False, quality=90, method=4)
    else:
        ims[0].save(os.path.join(images.DIR, pic + ".png"), optimize=True)
    _im.refresh()


def _drop_pictures(name):
    from . import images as _im
    _im.refresh()
    """A drawing that became 'wear' no longer needs its pictures."""
    from . import images
    for n, m in list(images.list_images().items()):
        if m.get("code") == name or (n == name and m.get("made_by") == "code"):
            base = os.path.splitext(m["file"])[0]
            for e in images.EXTS + (".json",):
                if os.path.exists(base + e):
                    os.remove(base + e)
    images._LIST["stamp"] = None


# -------------------------------------------------------------------------------------------- places
DEPTH_WORDS = {"front": 180, "near": 180, "middle": 450, "mid": 450, "back": 800, "behind": 800,
               "far": 1800, "distance": 1800, "horizon": 3500}


def _place_settings(s):
    pl = s.get("PLACE") if isinstance(s.get("PLACE"), dict) else {}
    try:
        scale = max(0.1, min(10.0, float(s.get("SCALE") or 1.0)))
    except (TypeError, ValueError):
        scale = 1.0
    return pl, scale


def capture_things(fn, t, state, scale=1.0):
    """Run a place drawing once; every  with pen.thing(...)  block lands on its own layer.
    -> ({name: (surface, (x0, y0, x1, y1) y-up, opts)}, loose)   loose = something was drawn outside the blocks"""
    rec = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)
    ctx = cairo.Context(rec)
    ctx.scale(scale, -scale)
    pen = Pen(ctx, seed=7)
    pen._things = {}
    _call(fn, pen, t, state)
    out = {}
    for nm, (surf, opts) in pen._things.items():
        x0, y0, w, h = surf.ink_extents()
        if w <= 0 or h <= 0:
            continue
        out[nm] = (surf, (x0, -(y0 + h), x0 + w, -y0), opts)
    lx, ly, lw, lh = rec.ink_extents()
    return out, (lw > 0 and lh > 0)


def z_from_depth(dz):
    """World depth offset from the front of the stage (units) -> story z (see world3d.Z_of_z)."""
    from .world3d import Z_of_z
    from .scene3d import FOCAL
    Z = FOCAL + max(0.0, float(dz))
    Zb = Z_of_z(1000.0)
    if Z <= Zb:
        return round((1.0 - FOCAL / Z) * 1000.0 / 0.58, 1)
    return round(1000.0 + (Z - Zb) / 4.0, 1)


def capture_any(fn, t, state, scale=1.0, kind="place", c3=None):
    """capture_things for 2D and 3D drawings. -> (things {name: (rec, ext, opts)}, loose, c3 {name: [cx, dy, cz]})
    3D: each thing is moved to its own middle (c3) and recorded as a front view, placed back at its x."""
    if not is3d(kind):
        th, loose = capture_things(fn, t, state, scale)
        return th, loose, {}
    from . import code3d
    got, loose_faces = _build3(fn, t, state, scale)
    out, cmap = {}, {}
    for nm, (faces, opts) in got.items():
        ex = code3d.extent(faces)
        if not ex:
            continue
        if c3 and nm in c3:
            cx, dy, cz = c3[nm]
        else:
            cx, cz = (ex[0] + ex[1]) / 2, (ex[4] + ex[5]) / 2
            dy = ex[2] if ex[2] > 0 else 0.0
        cmap[nm] = [round(cx, 2), round(dy, 2), round(cz, 2)]
        rec, e = code3d.front_recording(code3d.recentre(faces, cx, dy, cz))
        rec2 = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)
        c2 = cairo.Context(rec2)
        c2.set_source_surface(rec, cx, 0)
        c2.paint()
        out[nm] = (rec2, (e[0] + cx, e[1], e[2] + cx, e[3]), opts)
    return out, bool(loose_faces), cmap


def _build3(fn, t, state, scale):
    from . import code3d
    from .codedraw import _call  # noqa
    pen = code3d.Pen3()
    if scale != 1.0:
        pen.grow(scale)
    pen._things = {}
    _call(fn, pen, t, state)
    used = set()
    for fs, _o in pen._things.values():
        used.update(id(f) for f in fs)
    return pen._things, [f for f in pen.faces if id(f) not in used]


def _thing_z(opts, y0):
    z = opts.get("z")
    if isinstance(z, (int, float)):
        return float(z)
    d = str(opts.get("depth") or "").lower().strip()
    if d in DEPTH_WORDS:
        return float(DEPTH_WORDS[d])
    return round(min(2600.0, 380.0 + max(0.0, y0) * 5.0), 1)   # higher up in the drawing = further back


def _thing_states(opts):
    st = opts.get("states") or []
    return [str(x) for x in st] if isinstance(st, (list, tuple)) else []


def save_place(name, code, s, fn, desc, mode="place"):
    """KIND = "place": every pen.thing block -> its own picture (real size, own depth, abilities, looks),
    then a saved place (assets/places/<name>.json) that puts them all at their spots.
    KIND = "objects": every block -> its own object, usable anywhere (no place is saved)."""
    import time as _time
    from . import images, registry
    pl, scale = _place_settings(s)
    t0 = _time.perf_counter()
    first, loose, c3map = capture_any(fn, 0.0, None, scale, s["KIND"])
    per_frame = (_time.perf_counter() - t0) * 1000.0
    live = s.get("LIVE", True) is not False and per_frame <= LIVE_MAX_MS
    if is3d(s["KIND"]):                                  # 3D shapes are built once and cached: only the (fast)
        live = s.get("LIVE", True) is not False and per_frame <= 4000.0      # drawing happens per frame
    if not first:
        raise ValueError(f"KIND = \"{mode}\" needs  with pen.thing(\"name\"):  blocks - each block becomes one thing")
    if mode == "objects":                                # separate objects must not overwrite other pictures
        for nm in first:
            old = images.info(nm)
            if old and not (old.get("made_by") == "code" and (old.get("set_of") == name or old.get("code") == name)):
                raise ValueError(f"a picture called '{nm}' already exists - rename that block")
    anim_all = s.get("ANIMATED") or 0.0
    caps = {}

    def cap(st, k):
        if (st, k) not in caps:
            caps[(st, k)] = capture_any(fn, k / FPS, st, scale, s["KIND"], c3map)[0]
        return caps[(st, k)]

    things, pics, keep = [], [], set()
    shapes3 = {}                                         # 3D: walkable tops + footprint of every thing
    if is3d(s["KIND"]):
        from . import code3d as _c3
        got3, _l = _build3(fn, 0.0, None, scale)
        for nm3, (faces3, _o3) in got3.items():
            if nm3 in c3map:
                rc = _c3.recentre(faces3, *c3map[nm3])
                dx, dy, dz = c3map[nm3][:3]
                doors = [[round(d[0] - dx, 1), round(d[1] - dy, 1), round(d[2] - dz, 1)] + list(d[3:])
                         for d in (_o3.get("_doors") or [])]
                shapes3[nm3] = (_c3.walk_polys(rc), _c3.footprint(rc), doors, _c3.feet(rc))
    for nm, (_surf, _ext, opts) in first.items():
        states = _thing_states(opts) or [None]
        try:
            anim = max(0.0, min(MAX_ANIM, float(opts.get("animated") or 0.0)))   # only things that say so move
        except (TypeError, ValueError):
            anim = 0.0
        n = max(1, int(round(anim * FPS))) if anim else 1
        layers = {st: [cap(st, k).get(nm) for k in range(n)] for st in states}
        exts = [l[1] for ls in layers.values() for l in ls if l]
        if not exts:
            continue
        box = (min(e[0] for e in exts), min(e[1] for e in exts), max(e[2] for e in exts), max(e[3] for e in exts))
        if box[1] < 0:                                   # a glow / shadow below the ground is cut off
            box = (box[0], 0.0, box[2], box[3])
        px = _px_for(box, n > 1)
        cx = (box[0] + box[2]) / 2
        h = box[3] - box[1]
        pic = nm[:40] if mode == "objects" else f"{name}_{nm}"[:40]
        keep.add(pic)
        ab = [str(a) for a in (opts.get("abilities") or [])]
        if not ab:
            ab = ["hide"] if h >= 250 else (["sit"] if h < 80 else [])
        for i, st in enumerate(states):
            sp = pic if i == 0 else f"{pic}_{_clean(st)}"[:40]
            keep.add(sp)
            ims = [_to_png(l[0], box, px) if l else _to_png(cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None),
                                                               box, px) for l in layers[st]]
            _write_picture(sp, ims)
            kind = str(opts.get("kind") or "object").lower()
            kind = kind if kind in ("object", "prop", "vehicle") else "object"
            meta = {"description": f"{nm.replace('_', ' ')} ({name.replace('_', ' ')})" + (f" - {st}" if i else ""),
                    "kind": kind if i == 0 else "state", "height": round(h, 1), "made_by": "code",
                    "code": name, "thing": nm, "scale": scale, "live": live,
                    "box": [round(v, 2) for v in box], "draw_state": st}
            meta["set_of" if mode == "objects" else "part_of"] = name
            if is3d(s["KIND"]):
                meta["is3d"] = True
                meta["c3"] = c3map.get(nm)
                if i == 0 and nm in shapes3:
                    wp, fp, doors, ft = shapes3[nm]
                    if wp:
                        meta["walk"] = wp
                        if "stand" not in (meta.get("abilities") or []):
                            meta["abilities"] = list(meta.get("abilities") or []) + ["stand"]
                    if fp:
                        meta["foot"] = fp
                    if ft and len(ft) > 1:
                        meta["feet"] = ft                # separate pieces (a row of bushes): walk between them
                    if doors:
                        meta["doors"] = doors
                if i == 0 and isinstance(opts.get("seat"), (int, float)):
                    meta["seat"] = float(opts["seat"])    # pen.thing(..., seat=122): where people sit on it
            if i == 0 and ab:
                meta["abilities"] = ab
            if n > 1:
                meta["durations"] = [round(1000.0 / FPS, 1)] * n
                meta["alpha"] = True
            if i == 0 and len(states) > 1:
                meta["states"] = {str(x): f"{pic}_{_clean(x)}"[:40] for x in states[1:]}
            if i > 0:
                meta["state_of"], meta["state"] = pic, str(st)
            with open(os.path.join(images.DIR, sp + ".json"), "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=2, ensure_ascii=False)
                fh.flush()
            pics.append(sp)
        if mode == "objects":
            continue
        if is3d(s["KIND"]) and nm in c3map:           # real depth from the 3D drawing (unless z / depth is given)
            zz = _thing_z(opts, 0.0) if (opts.get("z") is not None or opts.get("depth")) else \
                z_from_depth(c3map[nm][2])
            from .world3d import p3
            # (indoors - a real 3D room, engine/room3d.py - x is the real place across the room: no spreading with depth)
            things.append({"what": pic, "id": nm, "x": round(cx * (1.0 if pl.get("indoor") else p3(zz)), 1), "z": zz,
                           "height": round(h, 1)})
            if c3map[nm][1] > 0.5:                      # a raised thing (a balcony, a roof): keeps its height
                things[-1]["y"] = round(c3map[nm][1], 1)
        else:
            things.append({"what": pic, "id": nm, "x": round(cx, 1), "z": _thing_z(opts, box[1]),
                           "height": round(h, 1)})
    _drop_parts(name, keep)
    if mode == "objects":
        images._LIST["stamp"] = None
        images.list_images()
        return {"name": name, "kind": "objects", "pictures": pics, "things": sorted(first), "live": live,
                "notes": ["some shapes are outside  with pen.thing(...)  blocks - they are not used"] if loose else [],
                "height": 0}
    spec = {"place": name, "description": desc, "ground": "grass", "far": "hills", "time": "day"}
    spec.update({k: v for k, v in pl.items() if k not in ("things", "place")})
    spec.update({"things": things + list(pl.get("things") or []), "made_by": "code", "interactive": True})
    uses = "; ".join(f"{t['id']} ({', '.join((images.info(t['what']) or {}).get('abilities') or [])})"
                     for t in things if t["z"] <= 1000 and (images.info(t["what"]) or {}).get("abilities"))
    spec["description"] = f"{desc}. Real objects in it (use these ids in events): {uses}" if uses else desc
    registry.save("places", name, spec)
    images._LIST["stamp"] = None
    images.list_images()
    notes = []
    if loose:
        notes.append("some shapes are outside  with pen.thing(...)  blocks - they are not in the place "
                     "(ground, sky and far hills come from PLACE = {...})")
    return {"name": name, "kind": "place", "pictures": pics, "things": [t["what"] for t in things],
            "notes": notes, "live": live, "height": max((t["height"] for t in things), default=0)}


def _drop_parts(name, keep=()):
    """Remove the pictures of a code place that are not in it any more."""
    from . import images
    for n, m in list(images.list_images().items()):
        if (m.get("part_of") == name or m.get("set_of") == name) and n not in keep:
            base = os.path.splitext(m["file"])[0]
            for e in images.EXTS + (".json",):
                if os.path.exists(base + e):
                    os.remove(base + e)
    images._LIST["stamp"] = None


def preview3d_png(fn, s, state=None, t=None, frame=None, width=640, height=400):
    """3D drawings: a turntable view (frame = step around it) with a person for size; places show names."""
    import io
    from . import code3d
    dur = s.get("ANIMATED") or 0.0
    fr = int(frame or 0)
    tt = float(t) if t is not None else ((fr / FPS) % max(dur, 1e-3) if dur else 0.0)
    labels = None
    if base_kind(s["KIND"]) in ("place", "objects"):
        _pl, scale = _place_settings(s)
        got, loose = _build3(fn, tt, state, scale)
        faces = [f for fs, _o in got.values() for f in fs]
        labels = []
        for nm, (fs, _o) in got.items():
            ex = code3d.extent(fs)
            if ex:
                labels.append((nm, ((ex[0] + ex[1]) / 2, ex[3] + 12, (ex[4] + ex[5]) / 2)))
        angle = -18.0 + 22.0 * math.sin(2 * math.pi * fr / 24.0) if frame else -18.0
        elev = 24.0
    else:
        faces = code3d.build(fn, tt, state)
        angle = -28.0 + 15.0 * fr
        elev = 16.0
    zoom = 1.9 if labels is not None else 1.0
    if base_kind(s["KIND"]) != "vehicle":
        faces = code3d.recolored(faces)                   # 🎨 in a world palette (when one is picked)
    if base_kind(s["KIND"]) == "vehicle" and isinstance(s.get("RIDE"), dict):   # show where people sit
        r = ride_settings(s["RIDE"])
        pen = code3d.Pen3()
        labels = []
        for k, (x, y, z) in enumerate(r["seats"]):
            pen.sphere(x, y, z, r=7, c="#e63946", rings=4, sides=8)
            labels.append((f"seat {k + 1}", (x, y + 22, z)))
        faces = list(faces) + pen.faces
    surf = code3d.preview_view(faces, width, height, angle=angle, elev=elev, labels=labels,
                               zoom=zoom, shadow=zoom == 1.0)
    buf = io.BytesIO()
    surf.write_to_png(buf)
    return buf.getvalue()


def preview_place_png(fn, s, state=None, t=None, frame=None, width=640, height=400):
    """The whole place with a box and a name around each thing; loose shapes (not in a thing) faded."""
    import io
    pl, scale = _place_settings(s)
    dur = s.get("ANIMATED") or 0.0
    tt = float(t) if t is not None else (float(frame or 0) / FPS if frame else 0.0)
    if dur:
        tt %= max(dur, 1e-3)
    things, loose = capture_things(fn, tt, state, scale)
    rec = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)
    c2 = cairo.Context(rec)
    c2.scale(scale, -scale)
    _call(fn, Pen(c2, seed=7), tt, state)
    lx, ly, lw, lh = rec.ink_extents()
    x0, y0, x1, y1 = lx, -(ly + lh), lx + lw, -ly
    for _s, e, _o in things.values():
        x0, y0, x1, y1 = min(x0, e[0]), min(y0, e[1]), max(x1, e[2]), max(y1, e[3])
    x0, x1 = min(x0, -200), max(x1, 200)
    top = max(y1, 330)
    bottom = min(y0, 0)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surf)
    sky = cairo.LinearGradient(0, 0, 0, height)
    sky.add_color_stop_rgb(0, 0.62, 0.8, 0.93)
    sky.add_color_stop_rgb(1, 0.93, 0.94, 0.9)
    ctx.set_source(sky)
    ctx.paint()
    k = min(width / (x1 - x0 + 80), (height - 30) / (top - bottom + 40))
    ctx.translate(width / 2 - (x0 + x1) / 2 * k, height - 16 + bottom * k)
    ctx.scale(k, -k)
    ctx.set_source_rgb(0.72, 0.8, 0.6)
    ctx.rectangle(x0 - 5000, -3000, 10000, 3000)
    ctx.fill()
    # a 300-tall person at the far left for size
    pxp = x0 - 20
    ctx.set_source_rgb(0.15, 0.15, 0.2)
    ctx.set_line_width(12)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for a, b in (((0, 150), (0, 235)), ((0, 150), (-30, 0)), ((0, 150), (30, 0)), ((0, 225), (-40, 150)),
                 ((0, 225), (40, 150))):
        ctx.move_to(pxp + a[0], a[1])
        ctx.line_to(pxp + b[0], b[1])
    ctx.stroke()
    ctx.arc(pxp, 268, 32, 0, 2 * math.pi)
    ctx.fill()
    ctx.save()
    ctx.scale(1, -1)
    if loose:                                     # shapes outside the blocks: faded (not part of the place)
        ctx.set_source_surface(rec, 0, 0)
        ctx.paint_with_alpha(0.3)
    order = sorted(things.items(), key=lambda kv: -_thing_z(kv[1][2], kv[1][1][1]))   # far ones first
    for _nm, (sf, _e, _o) in order:
        ctx.set_source_surface(sf, 0, 0)
        ctx.paint()
    ctx.restore()
    ctx.set_line_width(2.0 / k)
    ctx.set_dash([6.0 / k, 4.0 / k])
    for i, (nm, (_sf, e, o)) in enumerate(things.items()):
        hue = (0.85, 0.2, 0.2) if i % 3 == 0 else ((0.1, 0.4, 0.85) if i % 3 == 1 else (0.1, 0.55, 0.2))
        ctx.set_source_rgba(*hue, 0.9)
        ctx.rectangle(e[0], e[1], e[2] - e[0], e[3] - e[1])
        ctx.stroke()
        ctx.save()
        ctx.translate(e[0] + 2 / k, e[3] - 2 / k)
        ctx.scale(1 / k, -1 / k)
        ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(11)
        label = f"{nm} z{int(_thing_z(o, e[1]))}"
        xb = ctx.text_extents(label)
        ctx.set_source_rgba(1, 1, 1, 0.85)
        ctx.rectangle(0, 2, xb.x_advance + 6, 14)
        ctx.fill()
        ctx.set_source_rgba(*hue, 1)
        ctx.move_to(3, 13)
        ctx.show_text(label)
        ctx.restore()
    surf.flush()
    buf = io.BytesIO()
    surf.write_to_png(buf)
    return buf.getvalue()


def _meta_code(n):
    from . import images
    p = os.path.join(images.DIR, n + ".json")
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh).get("code")
    except (OSError, ValueError):
        return None


def delete(name):
    name = _clean(name)
    p = path_of(name)
    was_place = False
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            was_place = settings_of(fh.read())["KIND"] == "place"
        os.remove(p)
    _drop_pictures(name)
    _drop_parts(name)
    if was_place:
        from . import registry
        spec = registry.place(name) or {}
        if spec.get("made_by") == "code":
            registry.delete("places", name)
    _CACHE.pop(name, None)
    return True


# -------------------------------------------------------------------------------------------- wear (live)
_CACHE = {}         # name -> (mtime, draw fn, settings)


def _wear(name):
    name = _clean(name)
    p = path_of(name)
    if not os.path.exists(p):
        return None
    mt = os.path.getmtime(p)
    got = _CACHE.get(name)
    if got and got[0] == mt:
        return got
    try:
        with open(p, encoding="utf-8") as fh:
            code = fh.read()
        s = settings_of(code)
        fn = compile_code(code, name) if s["KIND"] == "wear" else None
    except Exception as ex:
        print(f"wear '{name}' could not be drawn: {ex}")
        fn, s = None, {}
    got = _CACHE[name] = (mt, fn, s)
    return got


def is_wear(name):
    got = _wear(name) if name and name not in ("none", "") else None
    return bool(got and got[1])


def hides_hair(name):
    got = _wear(name)
    return bool(got and got[1] and got[2].get("HIDE_HAIR"))


def draw_wear(ctx, name, r, alpha=1.0, ow=3.0, accent=None, skin=None, hair=None, t=0.0, state=None):
    """Draw a code wearable on a head: ctx is at the head centre, y up, face to +x, head radius r."""
    got = _wear(name)
    if not got or not got[1]:
        return False
    k = r / 100.0
    ctx.save()
    ctx.scale(k, k)
    pen = Pen(ctx, seed=7, outline=True, width=ow / max(k, 1e-3), alpha=alpha,
              accent=accent, skin=skin, hair=hair)
    try:
        _call(got[1], pen, t, state or ((got[2].get("STATES") or [None])[0]))
    except Exception as ex:
        if not got[2].get("_warned"):
            print(f"wear '{name}' failed: {ex}")
            got[2]["_warned"] = True
    ctx.restore()
    return True


# -------------------------------------------------------------------------------------------- live drawing
# Code drawings are drawn from their code every frame (sharp at any zoom, fast), with the saved picture as the
# backup: a drawing that fails is shown from its picture for the rest of the render. Each look / frame is
# recorded once (a vector recording) and replayed after that, so a drawing's code runs only a few times.
_LIVE = {}          # (code, mtime, thing, state, frame) -> recording surface (or None)
_FAILED = set()


def _load(name):
    """(mtime, draw fn, settings) of any code drawing (cached by file time)."""
    name = _clean(name)
    p = path_of(name)
    if not os.path.exists(p):
        return None
    mt = os.path.getmtime(p)
    got = _CACHE.get(("any", name))
    if got and got[0] == mt:
        return got
    with open(p, encoding="utf-8") as fh:
        code = fh.read()
    s = settings_of(code)
    got = _CACHE[("any", name)] = (mt, compile_code(code, name), s)
    return got


def _live_frame(meta, t, speed, loop, phase):
    n = len(meta.get("durations") or []) or 1
    if n <= 1:
        return 0
    T = n / float(FPS)
    tt = max(0.0, float(t) * float(speed) + float(phase))
    lp = str(loop).lower()
    if lp in ("once", "false", "no", "0"):
        tt = min(tt, T - 1e-4)
    elif lp in ("pingpong", "bounce"):
        m = tt % (2 * T)
        tt = m if m < T else 2 * T - m - 1e-4
    else:
        tt %= T
    return min(n - 1, int(tt * FPS))


def live_recording(meta, t=0.0, speed=1.0, loop="loop", phase=0.0):
    """Vector recording of a code picture at scene time t (None = use the picture)."""
    code = meta.get("code")
    if not code or not meta.get("live") or not meta.get("box") or code in _FAILED:
        return None
    try:
        got = _load(code)
        if not got:
            return None
        mt, fn, s = got
        thing = meta.get("thing")
        st = meta.get("draw_state")
        fr = _live_frame(meta, t, speed, loop, phase)
        key = (code, mt, thing, st, fr)
        if key in _LIVE:
            return _LIVE[key]
        if len(_LIVE) > 800:
            _LIVE.clear()
        if thing:
            c3 = {thing: meta["c3"]} if meta.get("c3") else None
            caps = capture_any(fn, fr / float(FPS), st, float(meta.get("scale") or 1.0), s["KIND"], c3)[0]
            for nm, (surf, _e, _o) in caps.items():     # one run records every thing of the file
                if nm == thing or not c3:
                    _LIVE[(code, mt, nm, st, fr)] = surf
            rec = _LIVE.get(key)
            _LIVE[key] = rec
        elif is3d(s["KIND"]):
            from . import code3d
            rec = code3d.front_recording(code3d.build(fn, fr / float(FPS), st))[0]
            _LIVE[key] = rec
        else:
            rec = _record(fn, fr / float(FPS), st)[0]
            _LIVE[key] = rec
        return rec
    except Exception as ex:
        _FAILED.add(code)
        print(f"code drawing '{code}' could not be drawn live ({ex}) - using its picture")
        return None


_FACES = {}


def live_faces(meta, t=0.0, speed=1.0, loop="loop", phase=0.0):
    """3D faces of a code picture (moved to the thing's own middle), cached per look / frame."""
    code = meta.get("code")
    if not code or code in _FAILED:
        return None
    try:
        got = _load(code)
        if not got:
            return None
        mt, fn, s = got
        thing, st = meta.get("thing"), meta.get("draw_state")
        fr = _live_frame(meta, t, speed, loop, phase)
        key = (code, mt, thing, st, fr)
        if key in _FACES:
            return _FACES[key]
        if len(_FACES) > 400:
            _FACES.clear()
        from . import code3d
        if thing:
            got3, _loose = _build3(fn, fr / float(FPS), st, float(meta.get("scale") or 1.0))
            for nm, (faces, _o) in got3.items():
                c3 = meta.get("c3") if nm == thing else None
                if nm != thing and (code, mt, nm, st, fr) in _FACES:
                    continue
                if nm != thing:
                    continue                            # other things keep their own saved middles
                cx, dy, cz = c3 or (0.0, 0.0, 0.0)
                _FACES[key] = code3d.recentre(faces, cx, dy, cz)
            return _FACES.get(key)
        _FACES[key] = code3d.build(fn, fr / float(FPS), st)
        return _FACES[key]
    except Exception as ex:
        _FAILED.add(code)
        print(f"3D drawing '{code}' failed ({ex}) - using its picture")
        return None


_TURNED = {}
_TURN3 = {}


def draw_live(ctx, meta, x, y, height=None, flip=False, alpha=1.0, anchor="bottom", rotate=0.0, t=0.0,
              speed=1.0, loop="loop", phase=0.0, turn=0.0):
    """Like images.draw, but from the code (sharp at any size). Returns (w, h) or None (-> use the picture).
    turn = degrees a 3D thing is turned around its up axis ("turn": 90 in the story)."""
    turn = float(turn or 0.0) % 360.0
    if meta.get("is3d") and anchor == "bottom" and not rotate:
        from . import code3d
        if code3d.CURRENT is not None and not turn and not getattr(ctx, "live3d", False):
            # LOD: far away (small on screen) -> its saved picture (live 3D play: the browser draws the mesh)
            px_h = float(height or meta.get("height") or 300) * abs(ctx.get_matrix().yy)
            if px_h < LOD_PX * max(0.5, getattr(code3d.CURRENT[0], "S", 1.0)):
                return None
        faces = live_faces(meta, t, speed, loop, phase)
        if faces and turn and code3d.CURRENT is not None and code3d.FAST[0]:
            got = code3d.draw_in_scene(ctx, faces, x, y, height, float(meta.get("height") or 0), flip, alpha,
                                       recolor=not any(w in str(meta.get("kind") or "") for w in
                                                       ("vehicle", "character", "animal")), turn=turn)
            if got:                                     # turned in the drawing itself: one shared mesh for all copies
                return got
        if faces and turn:                              # turned copies are kept (the same every frame)
            tk = (id(faces), round(turn, 1))
            got_t = _TURN3.get(tk)
            if got_t is None or got_t[0] is not faces:
                if len(_TURN3) > 600:
                    _TURN3.clear()
                got_t = _TURN3[tk] = (faces, code3d.turned(faces, turn))
            faces = got_t[1]
        if faces and code3d.CURRENT is not None:       # 3D camera mode: the real solid shape
            kd = str(meta.get("kind") or "")
            nm = f'{meta.get("name") or ""} {meta.get("code") or ""} {meta.get("thing") or ""}'.lower()
            bend = 0.0
            if "3d" in kd and "animal" not in kd and "character" not in kd and \
                    any(w in nm for w in code3d.PLANT_WORDS):   # the shared scene wind (engine/realworld.py)
                from . import realworld
                bend = max(-0.12, min(0.12, 0.008 * realworld.sway(t, x, 0.7, x * 0.37)))
            got = code3d.draw_in_scene(ctx, faces, x, y, height, float(meta.get("height") or 0), flip, alpha,
                                       recolor=not any(w in kd for w in ("vehicle", "character", "animal")),
                                       bend=bend)
            if got:
                return got
        if faces and turn:                              # 2D mode: the front view of the turned thing
            key = (meta.get("code"), meta.get("thing"), meta.get("draw_state"), _live_frame(meta, t, speed, loop, phase),
                   round(turn, 1))
            got = _TURNED.get(key)
            if got is None:
                if len(_TURNED) > 200:
                    _TURNED.clear()
                rec, e = code3d.front_recording(faces)
                got = _TURNED[key] = (rec, [e[0], 0.0, e[2], e[3]])
            m2 = dict(meta, box=got[1])
            return _paint_rec(ctx, got[0], m2, x, y, height, flip, alpha, anchor, rotate,
                              scale_h=float(meta.get("height") or 1) / max(1e-3, meta["box"][3] - meta["box"][1]))
    rec = live_recording(meta, t, speed, loop, phase)
    if rec is None:
        return None
    return _paint_rec(ctx, rec, meta, x, y, height, flip, alpha, anchor, rotate)


def _paint_rec(ctx, rec, meta, x, y, height=None, flip=False, alpha=1.0, anchor="bottom", rotate=0.0, scale_h=None):
    x0, y0, x1, y1 = [float(v) for v in meta["box"]]
    bh = y1 - y0
    if bh <= 0 or x1 <= x0:
        return None
    H = float(height or meta.get("height") or bh)
    if scale_h:                                         # same units as the saved picture (a turned front view)
        H = H / float(meta.get("height") or bh) * bh * scale_h
    k = H / bh
    ctx.save()
    ctx.translate(x, y)
    if rotate:
        ctx.rotate(rotate)
    if anchor != "bottom":
        ctx.translate(0, -H / 2)
    ctx.scale(-k if flip else k, k)
    ctx.translate(-(x0 + x1) / 2, -y0)
    ctx.rectangle(x0, y0, x1 - x0, bh)
    ctx.clip()
    ctx.scale(1, -1)
    ctx.set_source_surface(rec, 0, 0)
    if alpha >= 0.999:
        ctx.paint()
    else:
        ctx.paint_with_alpha(alpha)
    ctx.restore()
    return (H * (x1 - x0) / bh, H)


# -------------------------------------------------------------------------------------------- safe runner
def _instances(code):
    import re
    return set(re.findall(r"pen\.instance\(\s*[\"']([A-Za-z0-9_]+)[\"']", code or ""))


_BUILD_LOCK = __import__("threading").Lock()


def ensure_built(log=print, only=None, force=False):
    with _BUILD_LOCK:
        return _ensure_built(log, only, force)


def _ensure_built(log=print, only=None, force=False):
    """Make the pictures of code drawings that are missing or older than their code file (a fresh copy of the
    project ships only the code). Kit drawings first, then places (a place is rebuilt when a kit drawing it uses
    changed). -> number of drawings (re)built."""
    from . import images
    codes = list_code()
    if only is not None:
        codes = {k: v for k, v in codes.items() if k in set(only)}
    if not codes:
        return 0
    imgs = images.list_images()
    by_code = {}
    for n, m in imgs.items():
        if m.get("made_by") == "code" and m.get("code"):
            by_code.setdefault(m["code"], []).append(n)

    def mt(p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0.0

    py_mt = {n: mt(m["file"]) for n, m in list_code().items()}
    texts = {}
    for n, m in codes.items():
        try:
            with open(m["file"], encoding="utf-8") as fh:
                texts[n] = fh.read()
        except OSError:
            texts[n] = ""
    places_dir = os.path.join(os.path.dirname(DIR), "places")
    order = sorted(codes, key=lambda n: (codes[n]["kind"] in ("place", "place3d"), n))
    todo = []
    for n in order:
        kind = codes[n]["kind"]
        if kind == "wear" or kind in CHAR_KINDS:
            continue
        deps = max([py_mt.get(d, 0.0) for d in _instances(texts[n])] + [py_mt.get(n, 0.0)])
        if kind in ("place", "place3d"):
            pj = os.path.join(places_dir, n + ".json")
            need = mt(pj) < deps
            if not need:
                try:
                    with open(pj, encoding="utf-8") as fh:
                        spec = json.load(fh)
                    need = any(isinstance(t, dict) and t.get("what") and t["what"] not in imgs
                               for t in spec.get("things") or [])
                except (OSError, ValueError):
                    need = True
        else:
            outs = by_code.get(n) or []
            need = not outs or min(mt(os.path.join(images.DIR, o + ".json")) for o in outs) < deps
        if need or force:
            todo.append(n)
    if todo and log:
        log(f"building {len(todo)} code drawing(s) from assets/code (only when new or changed): {', '.join(todo)}")
    done = 0
    for n in todo:
        r = run_safe({"do": "save", "name": n, "code": extract_code(texts[n])}, timeout=180)
        if r.get("ok"):
            done += 1
        elif log:
            log(f"  ! could not build '{n}': {r.get('error')}")
    return done


def run_safe(job, timeout=25):
    """Run a preview / save in a separate process (time limit). job = {"do": "preview"|"save", ...}.
    -> dict (preview: {"ok", "png" (hex)} ; save: {"ok", ...})"""
    try:
        p = subprocess.run([sys.executable, "-m", "engine.codedraw"], input=json.dumps(job).encode(),
                           capture_output=True, timeout=timeout, cwd=HERE)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"the drawing took longer than {timeout} s (an endless loop?)"}
    out = p.stdout.decode(errors="replace").strip().splitlines()
    for line in reversed(out):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    err = p.stderr.decode(errors="replace").strip().splitlines()
    return {"ok": False, "error": (err[-1] if err else "the drawing stopped without an answer")[:400]}


def _friendly(ex):
    import traceback
    tb = traceback.extract_tb(ex.__traceback__)
    line = next((f.lineno for f in reversed(tb) if f.filename.startswith("<")), None)
    return (f"line {line}: " if line else "") + f"{type(ex).__name__}: {ex}"


def _worker():
    job = json.loads(sys.stdin.read() or "{}")
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024 * 1024, 1536 * 1024 * 1024))
    except Exception:
        pass
    try:
        if job.get("do") == "save":
            res = save(job["name"], job["code"], job.get("description"))
            print(json.dumps(dict(ok=True, **res)))
        elif job.get("all_frames"):
            s = settings_of(job["code"])
            n = max(1, int(round(s["ANIMATED"] * FPS))) if s["ANIMATED"] else 1
            if is3d(s["KIND"]):
                n = 24                                   # a full turn around it
            if s["KIND"] in CHAR_KINDS:
                n = 36                                   # round it once while it moves
            pngs = [preview_png(job["code"], job.get("state"), None, job.get("name") or "drawing",
                                int(job.get("width", 560)), int(job.get("height", 350)), frame=k,
                                palette=job.get("palette")).hex()
                    for k in range(min(n, 48))]
            print(json.dumps({"ok": True, "pngs": pngs}))
        else:
            png = preview_png(job["code"], job.get("state"), job.get("t"), job.get("name") or "drawing",
                              int(job.get("width", 640)), int(job.get("height", 400)), frame=job.get("frame"),
                              palette=job.get("palette"))
            print(json.dumps({"ok": True, "png": png.hex()}))
    except Exception as ex:
        print(json.dumps({"ok": False, "error": _friendly(ex)}))


# -------------------------------------------------------------------------------------------- help for people and AI
EXAMPLES = {
    "clay_lamp": '''KIND = "prop"
DESCRIPTION = "small clay oil lamp (diya) with a flickering flame"
ANIMATED = 1.5
STATES = ["lit", "off"]
ABILITIES = ["movable", "light"]

def draw(pen, t, state):
    # bowl
    pen.shape([(-28, 14), (-18, 2), (18, 2), (28, 14), (0, 20)], "terracotta")
    pen.ellipse(0, 14, 28, 6, pen.dark("terracotta"))
    if state == "lit":
        pen.glow(0, 34, 40, "flame", 0.45)
        pen.flame(4, 16, 26, t)
''',
    "water_well": '''KIND = "object"
DESCRIPTION = "old stone village well with a wooden roof and a bucket"
ABILITIES = ["hide"]

def draw(pen, t, state):
    pen.bricks(-70, 0, 140, 80, "stone", bw=30, bh=16)     # stone ring
    pen.rect(-76, 76, 152, 10, pen.dark("stone"))
    pen.rect(-62, 86, 9, 110, "dark_wood")                   # posts
    pen.rect(53, 86, 9, 110, "dark_wood")
    pen.roof(0, 190, 180, 60, "thatch")
    pen.line([(-58, 170), (58, 170)], "rope", 5)             # crossbar + rope
    pen.line([(10, 170), (10, 110)], "rope", 3)
    pen.box(10, 92, 22, 20, "metal", r=3)                    # bucket
''',
    "mango_tree_small": '''KIND = "object"
DESCRIPTION = "young mango tree with a few mangoes"

def draw(pen, t, state):
    pen.trunk(0, 0, 44, 330, "wood", lean=8)
    pen.line([(4, 250), (-60, 330)], "wood", 14)
    pen.line([(6, 270), (70, 340)], "wood", 12)
    pen.leaves(0, 400, 170, "leaf")
    for x, y in [(-60, 360), (40, 380), (90, 330), (-20, 320)]:
        pen.ellipse(x, y, 11, 14, "yellow")
''',
    "bullock_cart": '''KIND = "vehicle"
DESCRIPTION = "wooden bullock cart (no bullock) with big spoked wheels"

def draw(pen, t, state):
    pen.planks(-150, 70, 260, 60, "wood", n=6)               # bed
    pen.rect(-150, 130, 260, 10, pen.dark("wood"))
    pen.line([(110, 90), (260, 110)], "dark_wood", 12)       # pole to the bullock
    pen.wheel(-30, 70, 70, "dark_wood", spokes=8, turn=t * 3)
''',
    "village_yard": '''KIND = "place"
DESCRIPTION = "small village yard with a hut, a cot, a water pot and a tree"
PLACE = {"ground": "mud", "time": "day", "far": "hills", "path": True}

# every  with pen.thing(...)  block = one real thing of the place (own depth z, own abilities)
def draw(pen, t, state):
    with pen.thing("hut", z=750, abilities=["hide", "open"]):
        pen.rect(-160, 0, 320, 330, "mud")
        pen.roof(0, 320, 400, 190, "thatch")
        pen.door(0, 0, 90, 260)
    with pen.thing("tree", z=850, abilities=["climb", "hide"]):
        pen.trunk(-600, 0, 60, 500, "wood")
        pen.leaves(-600, 620, 220, "leaf")
    with pen.thing("cot", z=300, abilities=["sit"]):
        pen.rect(250, 55, 220, 18, "rope")
        pen.rect(250, 0, 12, 60, "dark_wood")
        pen.rect(458, 0, 12, 60, "dark_wood")
    with pen.thing("water_pot", z=220, abilities=["movable", "break"]):
        pen.ellipse(-300, 35, 32, 36, "clay")
        pen.ellipse(-300, 70, 16, 6, pen.dark("clay"))
''',
    "hut_3d": '''KIND = "object3d"
DESCRIPTION = "mud hut with a thatch roof (real 3D)"
ABILITIES = ["hide", "open"]

# 3D: x = right, y = up, z = away from the camera. The hut stands on y = 0, centred on x = 0, z = 0.
def draw(pen, t, state):
    pen.box(0, 0, 0, w=470, h=40, d=350, c=pen.dark("mud", 0.8))       # plinth
    wall = pen.box(0, 40, 0, w=440, h=260, d=320, c="mud")
    pen.roof(0, 300, 0, w=440, d=320, h=210, c="thatch", over=45)
    pen.door(wall, x=0, w=110, h=220)
    pen.window(wall, x=-140, y=110, w=60, h=60)
    pen.window(wall, side="right", x=0, y=110, w=60, h=60)
''',
    "cart_3d": '''KIND = "vehicle3d"
DESCRIPTION = "wooden hand cart with two big wheels (real 3D)"

def draw(pen, t, state):
    pen.box(0, 80, 0, w=260, h=14, d=140, c="wood")                     # bed
    pen.box(0, 94, -66, w=260, h=40, d=8, c="dark_wood")                # sides
    pen.box(0, 94, 66, w=260, h=40, d=8, c="dark_wood")
    for z in (-82, 82):                                                  # two big wheels
        pen.wheel(0, 70, z, r=70, c="dark_wood", turn=t * 3)
    pen.box(190, 90, 0, w=140, h=8, d=8, c="wood")                      # handle
''',
    "kit_place_3d": '''KIND = "place3d"
DESCRIPTION = "small village square in real 3D built from the 3D kit"
PLACE = {"ground": "mud", "time": "day", "far": ["hills"], "path": True, "clouds": "puffy"}

def draw(pen, t, state):
    with pen.thing("house", abilities=["hide", "open"]):
        pen.instance("house_3d", -560, 0, 820, turn=8)
    with pen.thing("well", abilities=["hide"]):
        pen.instance("well_3d", 330, 0, 470)
    with pen.thing("tree", abilities=["climb", "hide"]):
        pen.instance("tree_round_3d", 900, 0, 900, scale=1.1, t=t)
    with pen.thing("cot", abilities=["sit", "stand"]):
        pen.instance("cot_3d", -480, 0, 420)
''',
    "village_yard_3d": '''KIND = "place3d"
DESCRIPTION = "small village yard in 3D: a hut, a cot, a water pot and a tree"
PLACE = {"ground": "mud", "time": "morning", "far": "hills", "path": True}

# build each thing where it stands: z 0 = front of the stage, 1000 = back
def draw(pen, t, state):
    with pen.thing("hut", abilities=["hide", "open"]):
        wall = pen.box(0, 0, 800, w=420, h=260, d=320, c="mud")
        pen.roof(0, 260, 800, w=420, d=320, h=200, c="thatch", over=40)
        pen.door(wall, x=0, w=110, h=220)
    with pen.thing("tree", abilities=["climb", "hide"]):
        pen.trunk(-700, 0, 850, w=60, h=520, c="wood")
        pen.leaves(-700, 600, 850, r=220, c="leaf")
    with pen.thing("cot", abilities=["sit"]):
        pen.box(450, 55, 300, w=220, h=14, d=100, c="rope")
        for lx in (350, 550):
            for lz in (260, 340):
                pen.box(lx, 0, lz, w=10, h=55, d=10, c="dark_wood")
    with pen.thing("water_pot", abilities=["movable", "break"]):
        pen.pot(-420, 0, 260, r=35)
''',
"car_3d": '''KIND = "vehicle3d"
DESCRIPTION = "small modern car (real 3D)"
ABILITIES = ["movable", "heavy", "sit", "open"]

def draw(pen, t, state):
    paint = pen.material("red", roughness=0.3, metallic=0.5)
    glass = pen.material("glass")
    pen.round_box(0, 40, 0, w=420, h=95, d=180, c=paint, r=40)            # body
    pen.round_box(-20, 120, 0, w=240, h=85, d=160, c=glass, r=30)        # cabin
    for x in (-140, 140):
        for z in (-92, 92):
            pen.wheel(x, 45, z, r=45, c="#222222", spokes=5, turn=-t * 4)
    pen.light(205, 90, -60, "yellow", 0.6, 30)                            # head lights
    pen.light(205, 90, 60, "yellow", 0.6, 30)
''',
    "shapes_3d": '''KIND = "object3d"
DESCRIPTION = "a sampler of 3D shapes (open it to learn the pen)"
ANIMATED = 2

def draw(pen, t, state):
    pen.ground(900, 500, "grass")
    pen.pot(-350, 0, 0, r=40)
    pen.capsule(-250, 0, 0, r=25, h=120, c="skin")
    pen.ellipsoid(-150, 50, 0, 40, 50, 30, "leaf")
    pen.round_box(-40, 0, 0, 90, 80, 90, "blue", r=25)
    pen.tube([(40, 0, 0), (70, 120, 0), (140, 150, 0), (170, 60, 0)], 10, "wood")
    pen.lathe([(0, 0), (40, 0), (45, 60), (30, 120), (0, 140)], pen.material("gold"), 250, 0, 0)
    pen.log(0, None, 150, r=25, length=220)
    pen.stairs(380, 0, 0, 120, 100, 150, 5)
    pen.flame(-100, 0, -150, 60, t)
    pen.smoke(-100, 60, -150, 8, 14, t)
    pen.grass(100, 0, -150, 40)
    pen.mesh([(300, 0, -150), (380, 0, -150), (340, 90, -130)], [(0, 1, 2)], "purple")
    pen.rope([(-300, 150, -120), (-150, 150, -120)], 4, sag=40)
    with pen.group(0, 200, 0, ry=pen.loop(t, 2) * 360):
        pen.box(0, 0, 0, 60, 60, 60, pen.material("metal"))
''',
    "shapes_2d": '''KIND = "object"
DESCRIPTION = "a tea stall sign - a sampler of 2D shapes (open it to learn the pen)"
ANIMATED = 1

def draw(pen, t, state):
    pen.rect(-300, 0, 600, 180, "plaster")
    pen.text(0, 130, "चाय की दुकान", 34, "red")
    pen.text(0, 90, "TEA STALL", 26, "blue")
    pen.star(-240, 150, 20)
    pen.heart(240, 130, 16)
    pen.ngon(-240, 60, 25, 6, "green")
    pen.pot(200, 0, 30)
    pen.flag(-330, 0, 70, 45, t=t)
    pen.dashes([(-280, 20), (120, 20)], "ink", 3)
    pen.crescent(120, 60, 22, turn=20)
    pen.smoke(200, 50, t=t)
    pen.grass(-100, 0, 80)
    pen.sparkle(0, 170, 12, t=t)
''',
    "gold_crown": '''KIND = "wear"
DESCRIPTION = "king's gold crown with red jewels"
HIDE_HAIR = False

def draw(pen, t, state):
    # head radius 100 at (0, 0), face looks right
    base = 70
    pen.poly([(-80, base), (-85, base + 70), (-45, base + 35), (0, base + 80),
              (45, base + 35), (85, base + 70), (80, base)], "gold")
    pen.rect(-82, base - 5, 164, 20, pen.dark("gold", 0.85))
    for x in (-50, 0, 50):
        pen.circle(x, base + 5, 7, "red")
''',
    "flower_hair": '''KIND = "wear"
DESCRIPTION = "a big pink flower tucked behind the ear"

def draw(pen, t, state):
    x, y = -40, 70
    for k in range(6):
        a = k * 60
        pen.push(); pen.move(x, y); pen.turn(a)
        pen.ellipse(18, 0, 18, 10, "pink")
        pen.pop()
    pen.circle(x, y, 9, "yellow")
''',
}

PEN3_HELP = """3D pen - KIND "object3d" | "prop3d" | "vehicle3d" | "objects3d" | "place3d"
  x = right, y = UP, z = AWAY from the camera (depth). Stand on y = 0, centred on x = 0, z = 0. Story units
  (a person is 300 tall). c = a colour name / "#aabbcc" / "#aabbcc80" (see-through) / a material.
  SOLIDS    pen.box(x, y, z, w, h, d, c)  -> keep it (b = pen.box(...)) to put doors / windows on it
            pen.round_box(x, y, z, w, h, d, c, r=20)   (car bodies, cushions, bread, rounded tanks)
            pen.sphere(x, y, z, r, c, squash=1, bumps=0)   pen.ellipsoid(x, y, z, rx, ry, rz, c)
            pen.cylinder(x, y, z, r, h, c, r2=None)  (r2 = other top size: bucket, trunk)   pen.cone(x, y, z, r, h, c)
            pen.cylinder_axis(x, y, z, r, h, c, axis="x"|"z")  (lying: axles, pipes)   pen.log(x, None, z, r, length)
            pen.capsule(x, y, z, r, h, c, axis="y"|"x"|"z")   pen.lathe([(radius, height), ...], c, x, y, z)
            pen.extrude([(x, y), ...], z, d, c)  (a flat outline made thick)   pen.mesh(vertices, faces, c)
            pen.poly([(x, y, z), ...], c)  (one flat face)   pen.surface(rows_of_points, c)  (a bendy sheet)
  PATHS     pen.tube([(x, y, z), ...], radius, c)  (branches, horns, tails, pipes, handles)
            pen.rope([(x, y, z), (x, y, z)], radius=4, sag=30)   pen.line(pts, c, w)   pen.curve3d(pts, c, w)
  PARTS     pen.roof(x, y, z, w, d, h, c, style="gable|hip|pyramid|shed|flat", over=40)  (thatch gets lines)
            pen.door(b, x=0, w=52, h=125, side="front")  pen.window(b, x, y, w, h, side, glow=None)
            pen.stripe(b, side, y, h, c)  pen.paint(b, side, [(u, v), ...], c)   sides: front back left right top
            pen.wheel(x, y, z, r, c, w=12, spokes=6, turn=t*3)  pen.pot(x, y, z, r, c)  pen.stairs(x, y, z, w, h, d, steps)
            pen.planks(x, y, z, w, h, d, c, n)  pen.bricks(x, y, z, w, h, d, c)  pen.fence(x0, x1, z, h, c)
            pen.trunk(x, y, z, w, h, c, lean)  pen.leaves(x, y, z, r, c)  pen.blob(x, y, z, r, c)  pen.tree(x, z, h)
  SCULPTED  pen.sculpt("lota", x, y, z, turn=0, scale=1, colors={"#old": "#new"})  a soft clay thing of Ghatti Nagar at its
            real size (lota glass cup saucer thali katori patila kettle cooker tiffin dabba tawa belan matka bucket mug
            broom pillow blanket lantern phone radio clock book books school_bag umbrella chappal newspaper photo_frame
            mirror comb bottle diya chair stool table charpai bed almirah trunk shelf platform tv sofa mandir);
            pen.sculpt_info() = all names, pen.sculpt_info("table") = {"abilities", "seat", "top"}. Put each small thing in
            its own  with pen.thing(...)  on the surface it rests on (y = the table's top 130): people pick it up and
            put it somewhere else (assets/code/ghatti_ghar_3d.py)
  NATURE    pen.ground(w, d, c)  pen.water(w, d, c, t=t)  pen.terrain(height_rows, cell, c)  pen.grass(x, y, z, r)
            pen.road([(x, z), ...], width)  pen.river([(x, z), ...], width)  pen.ribbon(pts, width, c)
            pen.cloud(x, y, z, w, h, d)  pen.mountain(x, y, z, w, h, d, c, snow=True)
  LIGHT/FX  pen.flame(x, y, z, h, t)  pen.fire(x, y, z, amount, t)  pen.glow(x, y, z, r, c, strength)
            pen.light(x, y, z, c, strength, radius)  pen.smoke / dust / sparks(x, y, z, amount, size, t)
            pen.rain / snow(x, y, z, amount, speed, t)  pen.particles(x, y, z, count, c, size, speed, t)  pen.dot(x, y, z, r, c)
  LOOKS     pen.material("metal"|"gold"|"silver"|"copper"|"glass"|"water"|"ice"|"plastic"|"rubber"|"wood"|"stone"|
            "clay"|"cloth"|"skin", roughness=, metallic=, transparency=, emission=)  -> use it as c
            pen.dark(c, 0.7)  pen.light(c, 0.35)  pen.mix(c1, c2)  pen.opacity = 0.5  pen.outline = True
  MOVE      pen.push() / pen.pop()  pen.move(x, y, z)  pen.rotate_y(deg) (= turn)  pen.rotate_x(deg) (= tilt)
            pen.rotate_z(deg) (= roll)  pen.scale(sx, sy, sz)  pen.grow(s)  pen.transform(x, y, z, rx, ry, rz, sx)
            with pen.group(x, y, z, ry=30, s=1):  ...  (a group that moves / turns together)
  REUSE     pen.instance("hut_3d", x, y, z, scale=1, turn=0)  (put another 3D drawing of the library here)
  RIDE      (vehicles) RIDE = {"seats": [[x, y, z], ...], "pose": "pedal"|"sit"|"stand"|"row", "speed": 220,
            "sound": None}  seat POINTS where riders sit (y = seat top, z = side); t runs only while it moves
  MODELS    pen.model("barrel", x, y, z, height=120, turn=0, colors={"#8b5a2b": "wood"})  (a GLB / glTF / OBJ /
            STL model imported in 🧊 3D Code > 📦 Import - flat colours, lit like everything else;
            colors keys = the model's REAL colours (keep the keys already written in the code, change only the
            right side); {"*": "red"} = the whole model one colour (its light and dark kept);
            scale=1 keeps its real size (1 m = 175), max_faces=2500 simplifies, up="z" for Z-up files)
  TIME      t (seconds)  pen.wave(t, speed, size)  pen.loop(t, dur) (0..1)  pen.pingpong(t, dur)  pen.rand
  PLACES    with pen.thing("name", abilities=[...], states=[...], animated=2):  - each block = one real thing;
            its depth comes from where you build it (z 0 = front of the stage, 1000 = back);
            keep x -300..300, z < 350 free for the characters.
            walkable=True: people WALK on its tops (a floor, a stage, a balcony, a roof) - with stairs they
            climb up by themselves; seat=122: where people sit on it (a throne / charpai seat height)
  WALK/ENTER pen.stairs(...) inside a walkable thing = real steps (each riser < 64)
            pen.door(b, x, w, h, side, enter=True)  a door people really walk in / out through (h >= 100):
            story "do": "enter" | "come_out_of" and characters placed behind the building come out of it
            pen.hill(x, z, w=900, d=700, h=260, c="grass", rock=, rocky=0.25, path=True, steps=False,
            flat_top=0.35, bushes=6)  a real walkable hill (round top, rocks on the steep parts, a winding
            footpath people use when it is steep)   pen.hill_y(x, z, hx, hz, w, d, h, flat_top) = ground
            height on that hill (stand a temple on top: pen.instance("temple_3d", x, pen.hill_y(...), z))
  INDOOR    PLACE = {..., "indoor": True} for a room / hall: walls, a ceiling, a walkable floor"""

PEN_HELP = """2D pen - KIND "object" | "prop" | "vehicle" | "wear" | "objects" | "place"
  Story units (a person is 300 tall), y goes UP, the ground is y = 0, x = 0 is the middle.
  (wear: the head is a circle of radius 100 at (0, 0), the face looks right; pen.accent / pen.skin / pen.hair)
  COLOURS   "#aabbcc", "#aabbcc80" (see-through), names: """ + ", ".join(sorted(PALETTE)) + """
            pen.dark(c, 0.7)  pen.light(c, 0.35)  pen.mix(c1, c2, 0.5)
  SHAPES    pen.rect(x, y, w, h, c, r=0)  pen.box(cx, y, w, h, c)  pen.pill(x, y, w, h, c)  pen.poly([(x, y), ...], c)
            pen.tri(a, b, c3, c)  pen.circle(x, y, r, c)  pen.ellipse(x, y, rx, ry, c, turn=0)  pen.arc(x, y, r, deg1, deg2, c)
            pen.ngon(x, y, r, n, c)  pen.star(x, y, r, c, points=5)  pen.heart(x, y, s, c)  pen.crescent(x, y, r)
            pen.shape([(x, y), ...], c)  (smooth blob)
  FILLS     pen.gradient(pts, c_bottom, c_top)  pen.radial(x, y, r, c1, c2)  pen.shade(pts)  pen.shine(pts)
            pen.dots(x, y, w, h, c, r, gap)  pen.stripes(x, y, w, h, c1, c2, n)
  LINES     pen.line([(x, y), ...], c, w)  pen.curve(p0, p1, p2, p3, c, w)  pen.ring(x, y, r, c, w)
            pen.dashes(pts, c, w)  pen.arrow(x0, y0, x1, y1, c)  pen.zigzag(x0, y, x1, c)  pen.spiral(x, y, r, c)
            pen.rope(x0, y0, x1, y1, c, w, sag)
  PARTS     pen.roof(cx, y, w, h, "thatch")  pen.door(cx, y=0, w=52, h=125)  pen.window(cx, y, w, h, glow=None)
            pen.planks(x, y, w, h, c, n)  pen.bricks(x, y, w, h, c)  pen.wheel(x, y, r, c, spokes, turn)
            pen.leaves(x, y, r, c)  pen.trunk(x, y, w, h, c, lean)  pen.pot(x, y, r, c)  pen.grass(x, y, w, c)
            pen.cloud(x, y, w)  pen.flag(x, y, w, h, c, t)  pen.text(x, y, "words", size, c)  (Hindi works too)
  LIGHT/FX  pen.flame(x, y, h, t)  pen.glow(x, y, r, c, strength)  pen.sparkle(x, y, r, t=t)
            pen.smoke(x, y, n, size, t)  pen.particles(x, y, n, c, size, speed, t)  pen.ripples(x, y, w, t=t)
  MOVE      pen.push() / pen.pop()  pen.move(x, y)  pen.turn(deg)  pen.grow(s)  pen.scale(sx, sy)
  TIME      t (seconds)  pen.wave(t, speed, size)  pen.loop(t, dur)  pen.pingpong(t, dur)  pen.rand
  OTHER     pen.outline = True (dark edges)  pen.alpha = 0.5
  PLACES    with pen.thing("name", z=..., abilities=[...], states=[...]):  - each block = one real thing
Real sizes (adult person = 300): child 220, door 125, chair seat 90, table 150, pot 60, bucket 45,
  well 180, cart 240, car 300, hut 690, house 900, tree 1200, temple 1800."""

RULES_COMMON = """- Only plain Python: settings at the top, then def draw(pen, t, state). No imports except math and random.
  No files, no classes, no names starting with _.
- DESCRIPTION = one short line. STATES = [...] only if it has other looks (first = normal). ANIMATED = seconds
  only if something moves (use t; the loop must join up: use pen.wave(t, speed) with speed = 1/ANIMATED
  or whole multiples of it). ABILITIES from: movable, light (= easy to carry), heavy, round, throw, sit, stand,
  climb, hide, open, break, floats, sinks, switch (STATES "off" / "on": people turn it on / off).
- Draw at REAL size in story units (a person is 300 tall).
- Friendly cartoon look: 3-6 colours, a darker shade for sides, a few details. 15-80 lines."""

RULES_2D = """- KIND = "object" (big things standing on the ground), "prop" (small things people carry), "vehicle" (things
  that roll), "wear" (worn on a character's head: hats, crowns, masks, glasses, flowers), "objects" (many separate
  objects in one file: each  with pen.thing("pot", kind="prop"):  block is its own object), or "place" (a whole
  place: EVERY thing in its own  with pen.thing("name", z=..., abilities=[...]):  block - z = depth, 0 front ..
  1000 back of the stage, 1800 far; x from -1150 to 1150; each thing stands on y = 0; the ground, sky and far view
  are NOT drawn, they come from PLACE = {"ground": "grass|mud|sand|stone", "time": "day",
  "far": "hills|mountains|fields|city|sea|forest", "path": True}; keep x -300..300, z < 400 free for the characters).
- FLAT 2D drawing seen from the front: y goes UP, stand on y = 0, centred on x = 0."""

RULES_3D = """- KIND = "object3d" (big things), "prop3d" (small things people carry), "vehicle3d" (things that roll: use
  pen.wheel), "objects3d" (many separate objects: each  with pen.thing("pot", kind="prop"):  block), or "place3d"
  (a whole place: EVERY thing in its own  with pen.thing("name", abilities=[...]):  block; build each thing where
  it stands: x -1150..1150, z 0 (front of the stage) .. 1000 (back); keep x -300..300, z < 350 free for the
  characters; the ground, sky and far view come from PLACE = {"ground": "mud", "time": "morning",
  "far": "hills", "path": True}).
- REAL 3D: build from solids. x = right, y = UP, z = AWAY from the camera. Stand on y = 0, centred on x = 0, z = 0.
  The camera sees the front (-z side) first, so put doors and faces on the front. Use materials for metal / glass.
- A vehicle people RIDE (bicycle, cart, rickshaw, scooter, raft ...): the front is +x; add
  RIDE = {"seats": [[x, y, z], ...], "pose": "pedal" | "sit" | "stand" | "row", "speed": 220, "sound": None}
  (one seat POINT per rider: y = top of the seat, z = side) and turn wheels / pedals with t
  (pen.wheel(..., turn=-t * speed / radius)) - t runs only while it moves, so they stop when it stops."""


CHAR_HELP = """3D PEOPLE AND ANIMALS - KIND "character3d" (a person) or "animal3d" (an animal)
  def draw(pen, rig, t, state):      rig = the posed skeleton - what you draw moves with every action
  FOR = "human" | "quadruped" | "bird" | a species ("dog", "tiger" ...)   PREVIEW = {"age": "child", ...} (the try-out)
  A NEW ANIMAL: FOR = "dinosaur" (any name that is not an animal yet) + SPECIES = {"base": "tiger", "size": 2.2,
    "walk": 150, "run": 520, "sound": "roar", "fur": "#5a8f3c", "belly": "#d9e4a8", "aliases": ["dino"],
    "actions": {"attack": "pounce"}, "thigh": 64, "shin": 62, "neck_angle": 50 ...}  -> after saving, stories use
    "species": "dinosaur" and it does every animal action (walk, run, sit, lie, sleep, talk, roar, eat, jump ...).
    base = the skeleton it borrows ("kind": "bird" + a bird base for birds); rig.mouth opens the jaw when it talks.
  STATES = ["normal", "festival"] = looks;  on a character: "look3d": "name", "look3d_state": "festival"
  Which file a character uses: its "look3d" > <character id>_3d > <species>_3d > person_3d / quadruped_3d / bird_3d
  x = forward (where they look), y = up, z = to the side. An adult person is about 300 tall.
  rig.body(pen, hide=["hair", "shoes"])   the normal body (person_3d / quadruped_3d / bird_3d) minus some parts
  rig.show("hair")        False when that part is hidden (use it in your own body files)
  rig.mix(a, b, 0.5)      the point half way from a to b          rig.color("#aabbcc")
  PERSON:  rig.leg("near"|"far") -> (hip, knee, foot, toe)      rig.arm("near"|"far") -> (shoulder, elbow, hand)
           rig.hip rig.waist rig.chest rig.neck rig.neck_top rig.head rig.head_r rig.hand_near rig.hand_far
           rig.on_head(forward, up, side)   a point on the head (1 = on the surface; 0.9 forward = on the face)
           rig.cap(pen, covered, colour, size)   part of a ball round the head: covered(up, forward) -> True/False
           TALKING FACE (from the voice + text, every frame): rig.mouth_shape = {"jaw", "wide", "round", "closed",
             "teeth", "tongue"} (0..1: M/B/P closed, AA wide open, O / OO round, EE / S teeth, L tongue up),
             rig.brow (0..1 up on stressed words / questions), rig.gaze = (x, y) eye glances, rig.lid (0 open ..
             1 shut, blinks in the pauses), rig.nod (head dip, degrees) - the normal bodies use them already
           rig.model(pen, "name", bones=BONES, height=None, colors={...})   an imported RIGGED model (📦 Import
             as "3D person") moved by this skeleton - every action works; BONES matches its bones to ours
                  e.g. hair: lambda up, fwd: up > 0.4 or fwd < 0.1      a turban: lambda up, fwd: up > -0.1, size 1.18
           rig.s (scale) rig.K (limb thickness) rig.sw (half shoulder width) rig.hw (half hip width)
           colours: rig.skin rig.top rig.bottom rig.shoes rig.hair_color rig.accent
           looks: rig.gender rig.age rig.child rig.hair rig.outfit rig.bottom_kind rig.sleeves rig.mustache rig.beard
           now: rig.face ("happy", "sad", "angry", "surprised" ...) rig.mouth (0..1 talking) rig.blink rig.pose
  ANIMAL:  rig.legs() -> [(top, knee, paw, "front"|"back", side), ...]    rig.along(f) a point on the spine
           (f 0 = hips, 1 = shoulders)   rig.neck_base rig.neck_end rig.neck_w rig.head rig.head_r rig.fwd
           rig.face_point(forward, up, side)   rig.g (body radius) rig.lat rig.legw rig.length rig.snout
           colours: rig.fur rig.belly rig.dark rig.leg_color rig.hoof rig.muzzle rig.mane rig.tail_tip
           rig.species rig.sp (the species settings)  now: rig.tail rig.wag rig.jaw rig.trunk rig.mouth rig.blink
  BIRD:    rig.b (body size) rig.head_r rig.y0 (body height) rig.flying rig.head  colours: rig.fur rig.belly
           rig.wing rig.head_color rig.beak_color rig.beak_len
  Draw with the normal 3D pen (tube, sphere, ellipsoid, cone, cylinder, box, poly, material ...), using rig points.
  The Studio preview shows 6 camera angles and every pose (idle, walk, run, talk, wave, sit, dance, jump)."""

RULES_CHAR = """- This is a 3D PERSON or ANIMAL on a posed skeleton: KIND = "character3d" (person) or "animal3d" (animal),
  FOR = "human" or the species ("dog", "tiger", "cow" ...), PREVIEW = {...character settings to try it on...}.
- def draw(pen, rig, t, state):  start with  rig.body(pen, hide=[...])  (the normal body) and add the special
  parts ON the rig points (rig.head, rig.on_head(...), rig.hand_near, rig.neck, rig.along(...) ...), so they move
  with every action. Hide a normal part only when you draw your own instead (e.g. hide=["hair"] for braids).
- Keep it light: under 40 extra shapes, small sides (6-10) on round things.
- A NEW animal (not a known species - a dinosaur, a dragon, a unicorn ...): KIND = "animal3d", FOR = its name
  (snake_case) and SPECIES = {"base": "<the known animal whose skeleton it moves with: tiger, horse, dog, cow,
  elephant ... or a bird + "kind": "bird">, "size": 1.0, "walk": .., "run": .., "sound": "roar", "fur": "#hex",
  "belly": "#hex", "aliases": [...], "actions": {"<story word>": "<animal action>"}, and body shape if needed:
  "body", "thigh", "shin", "girth", "neck", "neck_angle", "head"}. Draw it with rig.body(pen) + extra parts, or a
  whole new body on the rig points; open the jaw with rig.mouth (talking) and rig.jaw (roaring)."""


EXAMPLES["village_girl_3d"] = '''KIND = "character3d"
FOR = "human"
DESCRIPTION = "village girl: two long braids with red ribbons, a bindi and gold earrings (festival: a flower garland)"
PREVIEW = {"age": "child", "gender": "female", "outfit": "frock", "outfit_color": "#2a9d8f", "hair": "short"}
STATES = ["normal", "festival"]

# Use it on a character:  "sita": {"name": "Sita", "look3d": "village_girl_3d"}


def draw(pen, rig, t, state):
    rig.body(pen, hide=["hair"])                 # the normal body without its hair - we make our own
    r = rig.head_r
    rig.cap(pen, lambda up, fwd: up > 0.45 or (fwd < 0.15 and up > -0.45), rig.hair_color, 1.07)
    for side in (-1, 1):
        top = rig.on_head(-0.35, -0.2, side * 0.85)                   # two braids
        mid = rig.on_head(-0.2, -1.6, side * 0.95)
        end = rig.on_head(-0.15, -2.6, side * 0.9)
        pen.tube([top, mid, end], [r * 0.22, r * 0.18, r * 0.12], c=rig.hair_color, sides=7)
        pen.sphere(end[0], end[1] - r * 0.12, end[2], r=r * 0.15, c="#d62828", rings=3, sides=6)   # ribbons
        ear = rig.on_head(0.0, -0.35, side * 1.02)                    # gold earrings
        pen.sphere(ear[0], ear[1] - r * 0.15, ear[2], r=r * 0.09, c=pen.material("gold"), rings=3, sides=6)
    b = rig.on_head(0.99, 0.42, 0)                                    # bindi
    pen.sphere(b[0], b[1], b[2], r=r * 0.07, c="#c1121f", rings=2, sides=5)
    if state == "festival":                                           # a marigold garland round the neck
        n = rig.neck
        for k in range(10):
            a = 2 * math.pi * k / 10
            pen.sphere(n[0] + 12 * rig.s * math.cos(a), n[1] - 6 * rig.s - 5 * rig.s * math.cos(a),
                       14 * rig.s * math.sin(a), r=3.5 * rig.s, c="#f4a300" if k % 2 else "#e85d04", rings=3, sides=5)
'''
EXAMPLES["pet_dog_3d"] = '''KIND = "animal3d"
FOR = "dog"
DESCRIPTION = "a pet dog with a red collar and a little gold bell"
PREVIEW = {"species": "dog"}

# Use it on a dog:  "moti": {"name": "Moti", "species": "dog", "look3d": "pet_dog_3d"}
# (a file called dog_3d.py would change EVERY dog; moti_3d.py only the dog called moti)


def draw(pen, rig, t, state):
    rig.body(pen)                                 # the normal dog
    a, b = rig.neck_base, rig.neck_end
    c = rig.mix(a, b, 0.55)                        # a collar round the neck
    d = rig.mix(a, b, 0.62)
    pen.tube([c, d], rig.neck_w * 1.02, c="#c1121f", sides=10, smooth=False)
    front = (c[0] + rig.neck_w * 0.9, c[1] - rig.neck_w * 0.5, 0)
    pen.sphere(front[0], front[1], front[2], r=rig.neck_w * 0.28, c=pen.material("gold"), rings=3, sides=7)
'''


# ---- examples for "➕ New animal" and "➕ New vehicle people ride" (open them from the Examples list)
EXAMPLES["dinosaur_3d"] = 'KIND = "animal3d"\nFOR = "dinosaur"\nDESCRIPTION = "a big green dinosaur (T-rex) - walks on its back legs, roars, talks"\nPREVIEW = {"species": "dinosaur"}\n\n# FOR = a NEW animal: saving this file makes "species": "dinosaur" work in every story, with every animal\n# action (walk, run, sit, lie, sleep, talk, roar, eat, jump, happy, sad, scared ...).\n# SPECIES: base = the skeleton it borrows (tiger, horse, dog, cow, elephant ... or "kind": "bird" for birds),\n#   size = how much bigger than the base, walk / run = speed, sound, colours (fur, belly),\n#   body shape: body (length), thigh + shin (leg length), girth, neck, neck_angle, head (head size),\n#   aliases = other names, actions = which action to use for a word in the story.\nSPECIES = {\n    "base": "tiger",\n    "size": 2.2,\n    "walk": 150,\n    "run": 520,\n    "sound": "roar",\n    "thigh": 64,\n    "shin": 62,\n    "girth": 50,\n    "neck": 30,\n    "neck_angle": 50,\n    "fur": "#5a8f3c",\n    "belly": "#d9e4a8",\n    "aliases": ["dino", "trex", "t_rex", "tyrannosaurus"],\n    "actions": {"attack": "pounce", "stomp": "jump", "dance": "happy", "chase": "run"},\n}\n\n\n# rig = the posed skeleton (same as every four-legged animal): rig.legs() gives the back legs it walks on\n# and the front legs (drawn here as tiny arms).  rig.mouth (0..1) opens the jaw when it talks, rig.jaw when it roars.\ndef draw(pen, rig, t, state):\n    g = rig.g\n    fur, belly = rig.fur, rig.belly\n    dark = pen.dark(fur, 0.75)\n    up = g * 0.75                                                   # how much the chest is lifted\n    # ---------------- back legs (big) and tiny arms\n    for top, knee, paw, end, side in rig.legs():\n        if end == "back":\n            w = rig.legw * 1.9\n            pen.tube([top, knee, paw], [w * 1.6, w * 1.0, w * 0.7], c=fur, sides=9, smooth=False)\n            for k in (-1, 0, 1):                                   # three toes with claws\n                tip = (paw[0] + w * 1.4, paw[1] + w * 0.25, paw[2] + k * w * 0.45)\n                pen.tube([(paw[0], paw[1] + w * 0.35, paw[2]), tip], [w * 0.35, w * 0.2], c=dark, sides=5,\n                         smooth=False)\n                pen.cone(tip[0], tip[1] - w * 0.15, tip[2], r=w * 0.14, h=w * 0.35, c="#f2ecd8", sides=5)\n        elif rig.show("arms"):\n            top = (top[0], top[1] + up * 0.8, top[2])\n            elbow = (top[0] + g * 0.15, top[1] - g * 0.45, top[2])\n            hand = (elbow[0] + g * 0.35, elbow[1] - g * 0.05, elbow[2])\n            pen.tube([top, elbow, hand], [g * 0.14, g * 0.1, g * 0.08], c=fur, sides=6, smooth=False)\n    # ---------------- body and belly: the chest is lifted (it stands up on its back legs)\n\n    def body(f):\n        p = rig.along(f)\n        return (p[0], p[1] + up * max(0.0, f), p[2])\n    pts = [body(f) for f in (-0.2, 0.2, 0.6, 1.0, 1.18)]\n    pen.tube(pts, [g * 0.9, g * 1.15, g * 1.05, g * 0.85, g * 0.6], c=fur, sides=12, smooth=True)\n    m = body(0.55)\n    pen.ellipsoid(m[0], m[1] - g * 0.45, 0, rx=rig.length * 0.5, ry=g * 0.6, rz=g * 0.8, c=belly, rings=4, sides=9)\n    # ---------------- a long tail that sways\n    h0 = rig.along(-0.2)\n    sway = math.sin(t * 2.2) * 0.25 + rig.wag / 40.0\n    lift = rig.tail / 90.0\n    tail = [h0]\n    for k in range(1, 5):\n        f = k / 4.0\n        tail.append((h0[0] - rig.length * 1.1 * f, h0[1] + g * (0.3 * lift - 0.35) * f * (1 + f),\n                     g * 1.4 * sway * f * f))\n    pen.tube(tail, [g * 0.85, g * 0.6, g * 0.4, g * 0.22, g * 0.05], c=fur, sides=9, smooth=True)\n    for k in range(6):                                              # spikes along the back and tail\n        p = body(0.9 - 0.3 * k) if k < 4 else tail[k - 2]\n        pen.cone(p[0], p[1] + g * (1.0 if k < 4 else 0.45), p[2], r=g * 0.14, h=g * 0.35, c=dark, sides=5)\n    # ---------------- neck and the big head with a jaw that opens\n    nb, ne = rig.neck_base, rig.neck_end\n    nb, ne = (nb[0], nb[1] + up, 0.0), (ne[0], ne[1] + up, 0.0)\n    pen.tube([nb, ne], [rig.neck_w * 1.3, rig.neck_w * 1.05], c=fur, sides=10, smooth=False)\n    hr = rig.head_r * 1.15\n    hx, hy = ne[0] + hr * 0.5, ne[1] + hr * 0.25\n    open_ = min(1.0, rig.mouth * 0.9 + max(0.0, rig.jaw) / 25.0)\n    pen.push()\n    pen.move(hx, hy, 0)\n    pen.roll(-8)                                                    # the face looks a little down\n    pen.ellipsoid(hr * 0.35, hr * 0.15, 0, rx=hr * 1.45, ry=hr * 0.7, rz=hr * 0.75, c=fur, rings=6, sides=12)\n    pen.push()                                                      # lower jaw: hinged at the back of the head\n    pen.move(-hr * 0.35, -hr * 0.2, 0)\n    pen.roll(-28 * open_)\n    pen.ellipsoid(hr * 0.85, -hr * 0.15, 0, rx=hr * 1.15, ry=hr * 0.28, rz=hr * 0.6, c=belly, rings=4, sides=10)\n    for k in range(5):                                              # bottom teeth\n        for sd in (-1, 1):\n            pen.cone(hr * (0.6 + 0.3 * k), -hr * 0.02, sd * hr * (0.45 - 0.05 * k), r=hr * 0.06, h=hr * 0.16,\n                     c="#fbf6e6", sides=4)\n    pen.pop()\n    if open_ > 0.15:                                                # inside of the mouth\n        pen.ellipsoid(hr * 0.9, -hr * 0.3, 0, rx=hr * 0.9, ry=hr * 0.25 * open_, rz=hr * 0.45, c="#7a1f24",\n                      rings=3, sides=8)\n    for k in range(5):                                              # top teeth\n        for sd in (-1, 1):\n            pen.push()\n            pen.move(hr * (0.65 + 0.3 * k), -hr * 0.45, sd * hr * (0.48 - 0.05 * k))\n            pen.roll(180)\n            pen.cone(0, 0, 0, r=hr * 0.06, h=hr * 0.18, c="#fbf6e6", sides=4)\n            pen.pop()\n    for sd in (-1, 1):                                              # eyes with brows, nostrils\n        if rig.blink:\n            pen.ellipsoid(hr * 0.35, hr * 0.5, sd * hr * 0.62, rx=hr * 0.14, ry=hr * 0.03, rz=hr * 0.1,\n                          c="#1d1d1f", rings=3, sides=6)\n        else:\n            pen.sphere(hr * 0.35, hr * 0.5, sd * hr * 0.6, r=hr * 0.16, c="#fff8d6", rings=4, sides=7)\n            pen.sphere(hr * 0.43, hr * 0.52, sd * hr * 0.68, r=hr * 0.08, c="#1d1d1f", rings=3, sides=6)\n        pen.ellipsoid(hr * 0.35, hr * 0.72, sd * hr * 0.55, rx=hr * 0.25, ry=hr * 0.06, rz=hr * 0.1, c=dark,\n                      rings=3, sides=6)\n        pen.sphere(hr * 1.7, hr * 0.3, sd * hr * 0.2, r=hr * 0.06, c="#22301a", rings=3, sides=5)\n    pen.pop()\n'
EXAMPLES["bicycle_3d"] = 'KIND = "vehicle3d"\nDESCRIPTION = "a village bicycle - one rider pedals it"\n\n# RIDE says how people use it:\n#   seats       = one POINT per rider [x, y, z]: x along it (+ = front), y = top of the seat, z = side\n#                 (the red dots in the preview - the rider\'s hips go exactly there)\n#   pose        = "pedal" (legs go round while it moves), "sit" (cart, car), "stand" (raft, scooter), "row" (boat)\n#   speed       = how fast it goes (a person walks about 150)   sound = "engine" / "ding" / None\n# In a story: {"who": "ravi", "do": "ride", "vehicle": "cycle1", "to": 1600}  ... {"who": "ravi", "do": "get_off"}\n# t runs only while it moves, so the wheels and the chain stop when it stops.\nRIDE = {"seats": [[-22, 128, 0]], "pose": "pedal", "speed": 260, "sound": None}\n\n\ndef draw(pen, t, state):\n    frame = pen.material("#1d4e89", roughness=0.35, metallic=0.4)\n    steel = pen.material("silver")\n    turn = -t * 5.6                                        # wheel turn (radians: speed / radius) - stops when it stops\n    for wx in (-72, 72):\n        pen.wheel(wx, None, 0, r=46, c="#1f1f22", w=5, spokes=10, turn=turn, hub="silver")\n    # the frame: seat tube, top tube, down tube, chain stays, fork\n    seat = (-22, 118, 0)\n    head = (52, 122, 0)\n    crank = (-8, 44, 0)\n    for a, b in ((crank, seat), (seat, head), (crank, head), (crank, (-72, 46, 0)), (seat, (-72, 46, 0)),\n                 (head, (72, 46, 0))):\n        pen.tube([a, b], 3.2, c=frame, sides=6, smooth=False)\n    # seat, handlebar\n    pen.ellipsoid(-24, 128, 0, rx=15, ry=4, rz=8, c="#2b2b2b", rings=3, sides=8)\n    pen.tube([(52, 122, 0), (58, 146, 0)], 2.6, c=steel, sides=6, smooth=False)\n    pen.tube([(56, 146, -24), (56, 146, 24)], 2.4, c=steel, sides=6, smooth=False)\n    for sd in (-1, 1):\n        pen.tube([(56, 146, sd * 24), (56, 146, sd * 30)], 3.4, c="#2b2b2b", sides=6, smooth=False)\n    # the chain wheel and pedals go round with the wheels\n    pen.cylinder_axis(-8, 44, 5, 11, 3, "#444444", axis="z")\n    a = turn * 0.6\n    for sd, ph in ((-1, 0.0), (1, math.pi)):\n        px, py = -8 + 16 * math.cos(a + ph), 44 + 16 * math.sin(a + ph)\n        pen.tube([(-8, 44, sd * 7), (px, py, sd * 10)], 1.8, c=steel, sides=5, smooth=False)\n        pen.box(px, py - 1.5, sd * 13, w=10, h=3, d=7, c="#2b2b2b")\n    pen.box(66, 104, 0, w=22, h=12, d=22, c="#8b5a2b")     # a small basket in front\n'


def kit3d_text(limit=60):
    """The user's reusable 3D drawings (for pen.instance in new 3D places)."""
    from . import images
    rows = []
    for nm, m in list_code().items():
        if m["kind"] not in ("object3d", "prop3d", "vehicle3d"):
            continue
        h = (images.info(nm) or {}).get("height")
        st = f", states {'/'.join(m['states'])}" if m["states"] else ""
        rows.append(f"  {nm} ({int(h) if h else '?'} tall{st}): {str(m['description'])[:70]}")
    return "\n".join(rows[:limit])


def models_text(limit=40):
    """Imported GLB / OBJ models (for pen.model)."""
    try:
        from . import model3d
        rows = []
        for nm, m in list(model3d.list_models().items())[:limit]:
            try:
                i = model3d.info(nm)
                h = i["size_m"][1] * model3d.UNITS_PER_M
                pal = ", ".join(h for h, _n, _m in model3d.palette(nm, 5))
                rows.append(f"  {nm} (real size about {int(h)} tall, {i['faces']} faces; its colours: {pal})")
            except Exception:
                continue
        return "\n".join(rows)
    except Exception:
        return ""


def gemini_prompt(idea, mode=None):
    """The prompt for Gemini / any AI. mode "2d" | "3d" (None = guess from the idea)."""
    low = str(idea).lower()
    if mode not in ("2d", "3d"):
        mode = "3d" if ("3d" in low or "3 d" in low) else "2d"
    is_place = any(w in low for w in ("place", "yard", "village", "home", "house with", "courtyard", "scene",
                                        "market", "farm", "street", "forest", "camp", "garden"))
    char_words = ("person", "man", "woman", "girl", "boy", "character", "kid", "child", "grandma", "grandpa",
                  "dadi", "nani", "king", "queen", "soldier", "farmer", "animal", "dog", "cat", "tiger", "lion",
                  "cow", "horse", "elephant", "monkey", "bird", "parrot", "crow", "goat", "deer")
    new_animal = ("dinosaur", "dino", "dragon", "unicorn", "creature", "monster", "beast", "species", "griffin",
                  "phoenix", "yeti", "mammoth", "t-rex", "trex", "new animal")
    words = low.replace("_", " ").split()
    is_new = mode == "3d" and "place" not in low and (any(w in low for w in new_animal) or "new animal" in low)
    ride_words = ("bicycle", "cycle", "cart", "rickshaw", "scooter", "raft", "tonga", "chariot", "bike", "sled",
                  "sledge", "tricycle", "wagon", "trolley", "boat", "canoe", "palki", "palanquin", "ride")
    if mode == "3d" and is_new:
        helps = PEN3_HELP + "\n\n" + CHAR_HELP
        ex = EXAMPLES["dinosaur_3d"] + "\n# ---- an animal that uses the normal body ----\n" + EXAMPLES["pet_dog_3d"]
        return f"""You write small Python drawings for a cartoon video engine (low-poly 3D cartoon, Indian village / city
stories). Write ONE file for a NEW animal: {idea}

Rules:
{RULES_COMMON}
{RULES_CHAR}

{helps}

Example:
{ex}
Answer with the Python code only."""
    if mode == "3d" and any(w in words for w in ride_words) and "place" not in low:
        ex = EXAMPLES["bicycle_3d"] + "\n# ---- another vehicle ----\n" + EXAMPLES["cart_3d"]
        return f"""You write small Python drawings for a cartoon video engine (low-poly 3D cartoon, Indian village / city
stories). Write ONE file for a vehicle people ride: {idea}

Rules:
{RULES_COMMON}
{RULES_3D}

{PEN3_HELP}

Example:
{ex}
Answer with the Python code only."""
    if mode == "3d" and any(w in words for w in char_words) and "place" not in low:
        helps = PEN3_HELP + "\n\n" + CHAR_HELP
        ex = EXAMPLES["village_girl_3d"] + "\n# ---- an animal ----\n" + EXAMPLES["pet_dog_3d"]
        return f"""You write small Python drawings for a cartoon video engine (low-poly 3D cartoon, Indian village / city
stories). Write ONE file for: {idea}

Rules:
{RULES_COMMON}
{RULES_CHAR}

{helps}

Example:
{ex}
Answer with the Python code only."""
    if mode == "3d":
        ex = EXAMPLES["hut_3d"] + "\n# ---- a vehicle ----\n" + EXAMPLES["cart_3d"]
        if is_place:
            ex += "\n# ---- a place ----\n" + EXAMPLES.get("village_yard_3d", "")
            kit = kit3d_text()
            if kit:
                ex += ("\n# ---- a place built from the 3D KIT (fastest, looks the same everywhere) ----\n" +
                       EXAMPLES.get("kit_place_3d", ""))
        rules, helps, look = RULES_3D, PEN3_HELP, "low-poly 3D cartoon (flat colours, lit by the sun)"
        kit = kit3d_text()
        if kit:
            helps += ("\n\n3D KIT - ready 3D drawings you can reuse: pen.instance(\"name\", x, 0, z, scale=1.0, turn=0, "
                      "state=None, t=t)\n(heights: an adult is about 300 tall)\n" + kit)
        mods = models_text()
        if mods:
            helps += ("\n\nIMPORTED MODELS - ready-made 3D models you can place: pen.model(\"name\", x, 0, z, height=..., "
                      "turn=0)\n" + mods)
    else:
        ex = EXAMPLES["water_well"] + "\n# ---- a wearable ----\n" + EXAMPLES["gold_crown"]
        if is_place:
            ex += "\n# ---- a place ----\n" + EXAMPLES["village_yard"]
        rules, helps, look = RULES_2D, PEN_HELP, "flat 2D cartoon (simple shapes, flat colours)"
    return f"""You write small Python drawings for a cartoon video engine ({look}, Indian village / city stories).
Write ONE file for: {idea}

Rules:
{RULES_COMMON}
{rules}

{helps}

Example:
{ex}
Answer with the Python code only."""


def extract_code(text):
    """Code from an AI answer (with or without ``` fences)."""
    import re
    t = str(text or "")
    m = re.findall(r"```(?:python|py)?\s*\n(.*?)```", t, re.S)
    if m:
        return max(m, key=len).strip() + "\n"
    return t.strip() + "\n"


def write_help_file():
    """prompts/code_drawing_prompt.md (2D) and prompts/code3d_drawing_prompt.md (3D) - paste into any AI."""
    out = None
    for mode, fname, tab, idea in (("2d", "code_drawing_prompt.md", "🐍 2D Code", "a blue tin trunk with a lock"),
                                   ("3d", "code3d_drawing_prompt.md", "🧊 3D Code", "a 3D blue tin trunk with a lock")):
        p = os.path.join(HERE, "prompts", fname)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(f"# {mode.upper()} code drawing prompt (paste into any AI, replace the idea at the end)\n\n")
            fh.write(gemini_prompt(f"<WRITE YOUR THING HERE, e.g. {idea}>", mode))
            fh.write(f"\n\nThen paste the answer into Studio > {tab} and press Save "
                     "(or save it as assets/code/<name>.py and run  python main.py code <name>).\n")
        out = out or p
    return out


if __name__ == "__main__":
    _worker()


# ============================================================================ ➕ new animal / new ridden vehicle
def _py(v):
    """a Python literal written with double quotes (for code files we make)"""
    return re.sub(r"\bnull\b", "None", re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", json.dumps(v))))


def _num(v, d):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def new_animal_code(o):
    """Studio "➕ New animal": a ready animal3d file for a NEW species (FOR = its name, SPECIES = its settings)."""
    from . import animals
    name = _clean(o.get("name") or "")
    if not name:
        raise ValueError("give the animal a name (e.g. dinosaur, unicorn, dragon)")
    if name in animals.BUILTIN:
        raise ValueError(f"'{name}' is already an animal - to change its look, open 'quadruped_3d' / 'bird_3d' or "
                         f"make a file called {name}_3d with FOR = \"{name}\"")
    base = animals.canon(o.get("base") or "tiger")
    if base == "human":
        base = "tiger"
    bird = base in animals.BIRDS
    sp = {"base": base}
    if bird:
        sp["kind"] = "bird"
    size = _num(o.get("size"), 1.0)
    if abs(size - 1.0) > 1e-3:
        sp["size"] = round(size, 2)
    for k in ("walk", "run"):
        v = _num(o.get(k), 0)
        if v > 0 and not bird:
            sp[k] = int(v)
    for k in ("fur", "belly"):
        if o.get(k):
            sp[k] = str(o[k])
    if o.get("sound"):
        sp["sound"] = str(o["sound"])
    al = [a.strip().lower().replace(" ", "_") for a in str(o.get("aliases") or "").split(",") if a.strip()]
    if al:
        sp["aliases"] = al
    acts = {}
    for part in str(o.get("actions") or "").split(","):
        if "=" in part:
            a, b = (x.strip().lower().replace(" ", "_") for x in part.split("=", 1))
            if a and b:
                acts[a] = b
    if acts:
        sp["actions"] = acts
    rows = ",\n".join(f"    {json.dumps(k)}: {json.dumps(v)}" for k, v in sp.items())
    desc = str(o.get("description") or f"a {name.replace('_', ' ')}")
    head = f'''KIND = "animal3d"
FOR = "{name}"
DESCRIPTION = {json.dumps(desc)}
PREVIEW = {{"species": "{name}"}}

# A NEW animal: after 💾 Save, stories can use "species": "{name}"{' (or ' + ', '.join(al) + ')' if al else ''}
# and it does every {'bird' if bird else 'animal'} action: walk, run, sit, sleep, talk, eat, jump, happy, sad ...
# SPECIES: base = the skeleton it borrows, size = x the base, walk / run = speed, sound, fur / belly colours,
#   aliases = other names, actions = {{"word in the story": "action it does"}}.
#   Body shape too: body (length), thigh, shin (legs), girth, neck, neck_angle, head (size) ...
SPECIES = {{
{rows},
}}

'''
    if o.get("start") == "copy":                           # every part of the body, to change anything
        base_file = "bird_3d" if bird else "quadruped_3d"
        code = read(base_file) or ""
        i = code.find("\n# ") if code.find("\n# ") >= 0 else 0
        body = code[code.find("\n", code.find("PREVIEW")) + 1:] if "PREVIEW" in code else code
        return head + body.lstrip("\n")
    if bird:
        return head + '''# rig = the posed bird skeleton: rig.b (body size), rig.head, rig.head_r, rig.y0 (body height), rig.flying
def draw(pen, rig, t, state):
    rig.body(pen)                    # the normal bird body in this animal's colours
    # add your own parts, e.g. a crest on the head:
    # hx, hy = rig.head[0], rig.head[1]
    # pen.cone(hx, hy + rig.head_r * 0.8, 0, r=rig.head_r * 0.3, h=rig.head_r, c="#e63946")
'''
    return head + '''# rig = the posed skeleton: rig.legs(), rig.along(f) (spine), rig.neck_base, rig.neck_end, rig.head, rig.head_r,
#   rig.face_point(forward, up, side), rig.g (body thickness), rig.mouth (talking 0..1), rig.jaw (roar), rig.tail
def draw(pen, rig, t, state):
    rig.body(pen)                    # the normal body of its base animal, in this animal's colours and size
    # add your own parts (or hide some: rig.body(pen, hide=["ears", "tail"])), e.g. a horn:
    # p = rig.face_point(0.3, 1.0, 0)
    # pen.cone(p[0], p[1], p[2], r=rig.head_r * 0.18, h=rig.head_r * 1.1, c=pen.material("gold"))
'''


def new_vehicle_code(o):
    """Studio "➕ New vehicle people ride": a vehicle3d file with RIDE (seats, seat height, pose, speed) and a
    simple body + wheels to change."""
    name = _clean(o.get("name") or "")
    pose = str(o.get("pose") or "sit")
    pose = pose if pose in RIDE_POSES else "sit"
    n = max(1, min(8, int(_num(o.get("seats"), 1))))
    L = max(60.0, _num(o.get("length"), 220))
    seat_h = max(10.0, _num(o.get("seat_height"), 120 if pose == "pedal" else 70))
    speed = max(20.0, _num(o.get("speed"), 260 if pose == "pedal" else 200))
    wheels = int(_num(o.get("wheels"), 2 if pose == "pedal" else 4))
    wr = max(8.0, _num(o.get("wheel_size"), 46 if pose == "pedal" else 32))
    col = str(o.get("color") or "#1d4e89")
    sound = o.get("sound") or None
    span = L * 0.55
    xs = [0.0] if n == 1 else [round(span / 2 - span * k / (n - 1), 1) for k in range(n)]
    if pose == "pedal" and n == 1:
        xs = [round(-L * 0.12, 1)]
    seats = [[x, round(seat_h, 1), 0] for x in xs]
    ride = {"seats": seats, "pose": pose, "speed": round(speed), "sound": sound}
    wx = [0.0] if wheels == 1 else [round(-L / 2 + wr + (L - 2 * wr) * k / max(1, (wheels // 2 if wheels >= 4 else wheels) - 1), 1)
                                   for k in range(wheels // 2 if wheels >= 4 else wheels)]
    zs = "(-45, 45)" if wheels >= 4 else "(0,)"
    wheel_code = ""
    if wheels > 0:
        wheel_code = f'''    turn = -t * {round(speed / wr, 2)}                     # rolling (radians) - stops when it stops
    for wx in {wx}:
        for wz in {zs}:
            pen.wheel(wx, None, wz, r={round(wr)}, c="#1f1f22", w=8, spokes=8, turn=turn, hub="silver")
'''
    deck_y = round(wr * 1.1 if wheels else 20, 1)
    return f'''KIND = "vehicle3d"
DESCRIPTION = {json.dumps(str(o.get("description") or name.replace("_", " ") or "my vehicle"))}

# RIDE = how people use it (the red dots in the preview are the seat points - riders sit exactly there):
#   seats = one point per rider: [x, y, z]  x = along it (+ = front), y = height of the seat top,
#           z = side (+ = away from the camera, - = the camera side)
#   pose = "pedal" (bicycle: legs go round while it moves), "sit" (cart, car), "stand" (raft, scooter), "row" (boat)
#   speed (a person walks about 150), sound = "engine" / "ding" / None
# In a story: "vehicles": [{{"id": "v1", "type": "{name or 'my_vehicle_3d'}", "x": 600}}]
#   {{"who": "ravi", "do": "ride", "vehicle": "v1", "to": 1500}}   {{"who": "ravi", "do": "get_off"}}
#   {{"who": "ravi", "do": "push", "vehicle": "v1", "to": 900}}   (pushing works too)
# t (time) runs only while it moves: wheels, pedals, a flag ... stop when it stops.
RIDE = {_py(ride)}


def draw(pen, t, state):
    body = pen.material({json.dumps(col)}, roughness=0.4, metallic=0.2)
{wheel_code}    # the body - change it into your vehicle (a cart, a scooter, a raft ...)
    pen.round_box(0, {deck_y}, 0, w={round(L)}, h=18, d=70, c=body, r=6)
    for sx, sy, sz in RIDE["seats"]:                 # a seat at each seat point (move the points, the seats follow)
        pen.box(sx, sy - 8, sz, w=36, h=8, d=34, c="#2b2b2b")
        if sy - 8 > {deck_y + 18}:
            pen.box(sx, {deck_y + 18}, sz, w=8, h=sy - 8 - {deck_y + 18}, d=8, c=body)
'''


# ---------------------------------------------------------------------------- reference code for the AI
_REF_STOP = {"a", "an", "the", "with", "and", "of", "in", "on", "for", "to", "my", "new", "3d", "big", "small", "real",
             "that", "this", "it", "is", "at", "by", "from", "very", "some", "one", "two", "like"}


def _words(text):
    return {w for w in re.findall(r"[a-z]+", str(text).lower().replace("_", " ")) if len(w) > 2 and w not in _REF_STOP}


def reference_candidates(mode=None):
    """[(name, kind, description)] of every drawing the AI may study: your own files first, then the examples."""
    out, seen = [], set()
    for n, m in sorted(list_code().items()):
        if mode in ("2d", "3d") and is3d(m.get("kind", "")) != (mode == "3d"):
            continue
        out.append((n, m.get("kind", ""), m.get("description", "")))
        seen.add(n)
    for n, code in sorted(EXAMPLES.items()):
        if n in seen:
            continue
        st = settings_of(code)
        if mode in ("2d", "3d") and is3d(st["KIND"]) != (mode == "3d"):
            continue
        out.append((n, st["KIND"], st.get("DESCRIPTION", "")))
    return out


def similar_refs(idea, mode=None, n=2):
    """The n drawings most like the idea (shared words in name + description) - picked when you choose none."""
    want = _words(idea)
    if not want:
        return []
    scored = []
    for name, kind, desc in reference_candidates(mode):
        have = _words(name) | _words(desc)
        hit = len(want & have)
        if hit:
            scored.append((hit + (0.5 if _words(name) & want else 0.0), name))
    scored.sort(reverse=True)
    return [nm for _, nm in scored[:n]]


def reference_block(names=None, own_code="", limit=18000):
    """The part of the prompt that shows the AI real, working drawings of THIS engine to learn from."""
    parts = []
    for nm in list(dict.fromkeys(names or []))[:4]:
        code = read(nm) or EXAMPLES.get(nm)
        if code:
            parts.append((nm, code))
    own = str(own_code or "").strip()
    if own:
        parts.append(("code the user gave", own))
    if not parts:
        return ""
    each = max(2500, limit // len(parts))
    body = []
    for nm, code in parts:
        c = code if len(code) <= each else code[:each] + "\n# ... (cut here - the rest is similar)\n"
        body.append(f"### {nm}\n```python\n{c}\n```")
    return ("\n\nREFERENCE DRAWINGS - real, working files of this engine. Study how they use the pen (the calls, sizes, "
            "materials, pen.thing blocks, abilities), how much detail they have and their style. Make the new file at "
            "least as detailed and in the same style, but for the new idea - do NOT copy their names or copy them "
            "as they are:\n\n" + "\n\n".join(body))
