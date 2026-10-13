"""✏ The sketch engine: a story drawn in pencil and ink on sketchbook paper ("art": "sketch").

Black stickmen with round heads, hand-drawn scenery (houses, huts, trees, hills, the sun, clouds, boats, a well),
and comic speech bubbles instead of subtitles. The lines "boil": every few frames each one is redrawn with a new
little wobble, the way a hand-drawn cartoon's lines shiver. The story itself (Gemini's JSON, timing, walking,
poses, voices, the camera) is the normal one; only the drawing is new. It is flat line art, so a frame is drawn in
a few milliseconds (no 3D, no lighting passes).

A story turns it on with  "settings": {"art": "sketch"}.
"""
import math
import random
import zlib

import cairo

from .depth import p_of_z, lift_of_p
from .background import set_layer
from .util import clamp

PAPER = (0.957, 0.937, 0.882)       # sketchbook cream
INK = (0.10, 0.09, 0.09)
PENCIL = (0.36, 0.35, 0.34)         # the softer grey for far things and shading
BOIL = 4                            # the people's lines get a new wobble every BOIL frames (6 a second at 24 fps)
BACK_BOIL = 12                      # the scenery's lines more slowly (2 a second): a still picture costs the video
                                    # encoder almost nothing, a whole page that shivers costs it a full picture
HEAD_R = 40.0                       # a stickman's head is big and round (the body skeleton is the engine's)
_PAPER = {}
_BACK = {}                          # the last backdrop drawn: (key, surface) - it only changes every BOIL frames


# ---------------------------------------------------------------------------- paper and ink
def _paper(W, H):
    """the sheet: cream, a faint grain and a soft darker edge (made once per size)"""
    s = _PAPER.get((W, H))
    if s is not None:
        return s
    import numpy as np
    rng = np.random.default_rng(5)
    g = rng.normal(0.0, 1.0, (H // 4 + 1, W // 4 + 1)).astype(np.float32)
    g = np.kron(g, np.ones((4, 4), np.float32))[:H, :W] * 0.5 + rng.normal(0.0, 1.0, (H, W)).astype(np.float32) * 0.5
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = ((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 0.28          # (the page is a little darker at the edges)
    img = np.empty((H, W, 4), np.uint8)
    for i, c in enumerate(PAPER[::-1]):                                # cairo is BGRA
        img[..., i] = np.clip((c - edge) * 255 + g * 4.0, 0, 255)
    img[..., 3] = 255
    s = cairo.ImageSurface.create_for_data(memoryview(img), cairo.FORMAT_ARGB32, W, H, W * 4)
    _PAPER[(W, H)] = (s, img)
    return _PAPER[(W, H)]


class Pen:
    """draws wobbly hand-made lines; the same seed gives the same wobble (so lines only boil every BOIL frames)"""

    def __init__(self, ctx, seed, unit=1.0):
        self.ctx, self.seed, self.unit = ctx, seed, unit
        self.rng = random.Random(seed)
        self.fade = 0.0                                    # far things: the ink goes paler toward the paper (0..1)

    def col(self, c):
        k = self.fade
        return tuple(c[i] + (PAPER[i] - c[i]) * k for i in range(3)) if k > 0 else c

    def set_fill(self, fill):
        if len(fill) == 4 and tuple(fill[:3]) != PAPER:
            self.ctx.set_source_rgba(*self.col(fill[:3]), fill[3])
        else:
            self.ctx.set_source_rgba(*fill)

    def thing(self, key):
        """a fresh random stream for one drawn thing (its wobble doesn't change when other things move)"""
        self.rng = random.Random(zlib.crc32(repr((self.seed, key)).encode()))   # (the same in every worker)

    def _wob(self, pts, amp):
        out = []
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            d = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(d / (40 * self.unit)))
            nx, ny = (-(y1 - y0) / d, (x1 - x0) / d) if d > 1e-6 else (0.0, 0.0)
            for k in range(n):
                u = k / n
                j = self.rng.uniform(-amp, amp) * self.unit if (k or i) else self.rng.uniform(-amp, amp) * 0.5 * self.unit
                out.append((x0 + (x1 - x0) * u + nx * j, y0 + (y1 - y0) * u + ny * j))
        out.append(pts[-1])
        return out

    def line(self, pts, w=4.0, c=INK, a=1.0, amp=1.6, twice=True, close=False):
        """a pencil-and-ink stroke through pts: a wobbly main line and (twice) a lighter second pass beside it"""
        if len(pts) < 2:
            return
        ctx = self.ctx
        if close:
            pts = list(pts) + [pts[0]]
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        for k in range(2 if twice else 1):
            q = self._wob(pts, amp * (1.0 + k))
            ctx.move_to(*q[0])
            if len(q) > 2:                                   # smooth through the wobble points (a hand, not a ruler)
                for i in range(1, len(q) - 1):
                    mx, my = (q[i][0] + q[i + 1][0]) / 2, (q[i][1] + q[i + 1][1]) / 2
                    ctx.curve_to(q[i][0], q[i][1], q[i][0], q[i][1], mx, my)
                ctx.line_to(*q[-1])
            else:
                ctx.line_to(*q[1])
            ctx.set_source_rgba(*self.col(c), a * (1.0 if k == 0 else 0.35))
            ctx.set_line_width(w * self.unit * (1.0 if k == 0 else 0.55))
            ctx.stroke()

    def circle(self, x, y, r, w=4.0, c=INK, a=1.0, fill=None, amp=1.2):
        n = max(10, int(r / (6 * self.unit)) + 10)
        pts = [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        if fill is not None:
            self.ctx.arc(x, y, r, 0, 2 * math.pi)
            self.set_fill(fill)
            self.ctx.fill()
        self.line(pts, w, c, a, amp, close=True)

    def poly(self, pts, w=4.0, c=INK, a=1.0, fill=None, amp=1.6):
        if fill is not None:
            self.ctx.move_to(*pts[0])
            for p in pts[1:]:
                self.ctx.line_to(*p)
            self.ctx.close_path()
            self.set_fill(fill)
            self.ctx.fill()
        self.line(pts, w, c, a, amp, close=True)

    def hatch(self, x0, y0, x1, y1, gap=16.0, c=PENCIL, a=0.5, w=1.6):
        """pencil shading: short slanted strokes inside a box (y up)"""
        k = 0
        x = x0
        while x < x1 + (y1 - y0):
            ax, ay = x, y0
            bx, by = x - (y1 - y0), y1
            if bx < x0:                                     # clip the stroke to the box
                by = y0 + (ax - x0)
                bx = x0
            if ax > x1:
                ay = y0 + (ax - x1)
                ax = x1
            if ay < y1:
                self.line([(ax, ay), (bx, by)], w, c, a, amp=0.6, twice=False)
            x += gap * self.unit
            k += 1


# ---------------------------------------------------------------------------- scenery (world units, y up)
def _kind_of(o):
    """which drawing a place's thing gets: by its id / type words"""
    for s in (str(o.get("id", "")).lower(), str(o.get("type", "")).lower()):   # its id first: a type carries the
        k = _kind_of_words(s)                                                   # place's name (temple_fair_3d_lamp)
        if k:
            return None if k == "skip" else k
    return None


def _kind_of_words(s):
    for words, kind in ((("pine", "fir", "deodar", "cedar"), "tree"), (("cabin", "cottage"), "hut"),
                        (("ceiling", "floor", "gallery", "door", "dhanush", "varmala", "mountain", "peak"), "skip"),
                        (("haveli",), "haveli"), (("field", "khet", "farmland", "crop"), "field"),
                        (("fence", "bada", "baad"), "fence"), (("cactus", "nagphani"), "cactus"),
                        (("tulsi",), "tulsi"), (("railing", "balcony", "stairs", "wall"), "skip"),
                        (("stall", "dukan", "tent", "booth", "kiosk"), "stall"),
                        (("chita", "pyre", "dhuni", "havan", "fire", "bonfire", "chulha", "angithi"), "fire"),
                        (("singhasan", "throne", "gaddi"), "throne"), (("pillar", "column", "stambh"), "pillar"),
                        (("umbrella",), "umbrella"), (("street", "road"), "skip"),
                        (("kosh", "chest", "treasure", "box", "trunk"), "chest"),
                        (("hut", "jhopdi", "shack"), "hut"),
                        (("temple", "mandir", "mahakal", "shrine", "chhatri"), "temple"),
                        (("palace", "mahal", "castle", "fort", "house", "home", "ghar", "shop", "school", "building",
                          "station", "hospital", "sabha"), "house"),
                        (("palm", "coconut"), "palm"),
                        (("tree", "banyan", "peepal", "neem", "mango", "siddhavat", "forest", "bush"), "tree"),
                        (("well", "kuan"), "well"), (("boat", "nav"), "boat"),
                        (("hay", "straw"), "hay"), (("cot", "khat", "bench", "takht", "charpai", "bed"), "bench"),
                        (("lamp", "diya", "torch", "pole"), "lamp"), (("flag", "jhanda"), "flag"),
                        (("ladder",), "ladder"), (("wheel", "ferris", "jhoola", "swing"), "wheel"),
                        (("rock", "stone", "boulder"), "rock"), (("car", "bus", "jeep", "cart", "auto"), "cart"),
                        (("pump", "nal"), "pump"), (("shisham",), "tree"),
                        (("reed", "bush", "thorn", "jhadi", "grass"), "bush"), (("log", "lakdi"), "log"),
                        (("step", "ghat", "jetty", "dais", "stage", "chabutra"), "steps"),
                        (("pot", "matka", "ghada"), "pots"), (("shipra", "river", "pond", "lake", "water", "pool"), "water"),
                        (("deck_chair", "chair", "seat"), "bench")):
        if any(w in s for w in words):
            return kind
    return None


def _scenery_thing(pen, kind, x, h, t):
    """one hand-drawn thing standing on the ground at x (h = its height, world units)"""
    ln = pen.line
    if kind == "house":
        w = h * 1.1
        b = h * 0.62
        pen.poly([(x - w / 2, 0), (x + w / 2, 0), (x + w / 2, b), (x - w / 2, b)], 4, fill=(*PAPER, 1))
        pen.poly([(x - w / 2 - 18, b), (x, h), (x + w / 2 + 18, b)], 4, fill=(*PAPER, 1))
        pen.hatch(x - w / 2 + 6, b + 4, x + w / 2 - 6, b + (h - b) * 0.45, 14)
        ln([(x - w * 0.12, 0), (x - w * 0.12, b * 0.6), (x + w * 0.12, b * 0.6), (x + w * 0.12, 0)], 3.5)
        for dx in (-0.33, 0.33):
            cx = x + dx * w
            pen.poly([(cx - 26, b * 0.55), (cx + 26, b * 0.55), (cx + 26, b * 0.85), (cx - 26, b * 0.85)], 3)
            ln([(cx, b * 0.55), (cx, b * 0.85)], 2)
    elif kind == "hut":
        w = h * 1.05
        b = h * 0.48
        pen.poly([(x - w / 2, 0), (x + w / 2, 0), (x + w / 2, b), (x - w / 2, b)], 4, fill=(*PAPER, 1))
        pen.poly([(x - w / 2 - 30, b - 10), (x, h), (x + w / 2 + 30, b - 10)], 4, fill=(*PAPER, 1))
        for k in range(7):                                       # thatch strokes
            u = (k + 0.5) / 7
            ln([(x - w / 2 - 30 + u * (w + 60), b - 6), (x + (u - 0.5) * 30, h - 20)], 1.6, PENCIL, 0.6, twice=False)
        pen.poly([(x - 30, 0), (x + 30, 0), (x + 30, b * 0.75), (x - 30, b * 0.75)], 3, fill=(*INK, 0.85))
    elif kind == "temple":
        w = h * 0.55
        b = h * 0.45
        pen.poly([(x - w / 2, 0), (x + w / 2, 0), (x + w / 2, b), (x - w / 2, b)], 4, fill=(*PAPER, 1))
        pts = [(x - w / 2 + 10, b)] + [(x + s * w * (0.42 - 0.38 * u ** 1.5), b + (h - b) * u)
                                         for s, us in ((-1, (0.3, 0.6, 0.85)),) for u in us] + [(x, h)]
        pts += [(x + w * (0.42 - 0.38 * u ** 1.5), b + (h - b) * u) for u in (0.85, 0.6, 0.3)] + [(x + w / 2 - 10, b)]
        pen.poly(pts, 4, fill=(*PAPER, 1))
        for u in (0.3, 0.6):
            yy = b + (h - b) * u
            ww = w * (0.42 - 0.38 * u ** 1.5)
            ln([(x - ww, yy), (x + ww, yy)], 2, PENCIL)
        ln([(x, h), (x, h + 60)], 3)
        wv = 8 * math.sin(t * 3)
        pen.poly([(x, h + 60), (x + 50, h + 48 + wv), (x, h + 36)], 3, fill=(*INK, 0.25))
        ln([(x - 26, 0), (x - 26, b * 0.7), (x, b * 0.85), (x + 26, b * 0.7), (x + 26, 0)], 3.5)
    elif kind == "tree":
        ln([(x - 14, 0), (x - 8, h * 0.45), (x - 16, h * 0.55)], 4)
        ln([(x + 14, 0), (x + 8, h * 0.45), (x + 18, h * 0.55)], 4)
        pen.hatch(x - 10, 4, x + 10, h * 0.42, 9)
        r = h * 0.3
        cy = h * 0.68
        pts = []
        for i in range(14):                                     # a cloud of leaves: bumpy outline
            a = 2 * math.pi * i / 14
            rr = r * (1.0 + 0.18 * math.sin(i * 2.7))
            pts.append((x + rr * 1.25 * math.cos(a), cy + rr * math.sin(a)))
        pen.poly(pts, 4, fill=(*PAPER, 1), amp=2.5)
        for i in range(5):
            a = 0.9 * i
            ln([(x + r * 0.6 * math.cos(a), cy + r * 0.5 * math.sin(a)),
                (x + r * 0.6 * math.cos(a) + 18, cy + r * 0.5 * math.sin(a) + 10)], 2, PENCIL, 0.7, twice=False)
    elif kind == "palm":
        ln([(x, 0), (x + h * 0.08, h * 0.5), (x + h * 0.05, h)], 6)
        for a in (-150, -110, -60, -20, 20):
            ra = math.radians(a)
            ln([(x + h * 0.05, h), (x + h * 0.05 + 0.3 * h * math.cos(ra), h + 0.12 * h + 0.18 * h * math.sin(ra))], 4)
    elif kind == "well":
        pen.poly([(x - 70, 0), (x + 70, 0), (x + 70, 70), (x - 70, 70)], 4, fill=(*PAPER, 1))
        pen.hatch(x - 66, 6, x + 66, 64, 22)
        ln([(x - 60, 70), (x - 60, 190)], 4)
        ln([(x + 60, 70), (x + 60, 190)], 4)
        ln([(x - 75, 190), (x + 75, 190)], 4)
        ln([(x, 190), (x, 120)], 2)
        pen.poly([(x - 14, 120), (x + 14, 120), (x + 11, 96), (x - 11, 96)], 3)
    elif kind == "boat":
        bob = 6 * math.sin(t * 1.6)
        pen.poly([(x - 140, 40 + bob), (x + 140, 40 + bob), (x + 100, bob), (x - 100, bob)], 4, fill=(*PAPER, 1))
        ln([(x, 40 + bob), (x, 230 + bob)], 4)
        pen.poly([(x + 4, 225 + bob), (x + 110, 70 + bob), (x + 4, 70 + bob)], 3.5, fill=(*PAPER, 1))
    elif kind == "hay":
        pts = [(x + 110 * math.cos(a), 110 * math.sin(a) * 1.2) for a in [math.pi * i / 10 for i in range(11)]]
        pen.poly(pts, 4, fill=(*PAPER, 1))
        for k in range(6):
            ln([(x - 70 + k * 28, 20), (x - 60 + k * 26, 90)], 1.6, PENCIL, 0.6, twice=False)
    elif kind == "bench":
        ln([(x - 110, 55), (x + 110, 55)], 5)
        ln([(x - 95, 0), (x - 95, 55)], 4)
        ln([(x + 95, 0), (x + 95, 55)], 4)
    elif kind == "lamp":
        ln([(x, 0), (x, 210)], 4)
        pen.poly([(x - 18, 210), (x + 18, 210), (x + 12, 250), (x - 12, 250)], 3)
        for a in range(0, 360, 45):                                  # little light rays
            ra = math.radians(a)
            ln([(x + 32 * math.cos(ra), 232 + 32 * math.sin(ra)), (x + 46 * math.cos(ra), 232 + 46 * math.sin(ra))],
               1.8, PENCIL, 0.7, twice=False)
    elif kind == "flag":
        ln([(x, 0), (x, h)], 4)
        wv = 10 * math.sin(t * 3)
        pen.poly([(x, h), (x + 90, h - 25 + wv), (x, h - 55)], 3.5, fill=(*INK, 0.2))
    elif kind == "ladder":
        ln([(x - 30, 0), (x - 20, h)], 4)
        ln([(x + 30, 0), (x + 40, h)], 4)
        for k in range(1, int(h / 45)):
            yy = k * 45
            ln([(x - 30 + 10 * yy / h, yy), (x + 30 + 10 * yy / h, yy)], 3)
    elif kind == "wheel":
        r = h * 0.42
        cy = h * 0.52
        ln([(x - r * 0.6, 0), (x, cy), (x + r * 0.6, 0)], 4)
        pen.circle(x, cy, r, 4)
        a0 = t * 0.4                                               # it turns slowly
        for k in range(8):
            a = a0 + k * math.pi / 4
            ln([(x, cy), (x + r * math.cos(a), cy + r * math.sin(a))], 2)
            pen.poly([(x + r * math.cos(a) - 14, cy + r * math.sin(a) - 26), (x + r * math.cos(a) + 14,
                      cy + r * math.sin(a) - 26), (x + r * math.cos(a) + 14, cy + r * math.sin(a) - 4),
                      (x + r * math.cos(a) - 14, cy + r * math.sin(a) - 4)], 2.5)
    elif kind == "rock":
        pen.poly([(x - 70, 0), (x - 50, 45), (x + 10, 60), (x + 65, 30), (x + 75, 0)], 4, fill=(*PAPER, 1))
        pen.hatch(x - 40, 4, x + 50, 30, 14)
    elif kind == "cart":
        pen.poly([(x - 120, 40), (x + 120, 40), (x + 120, 120), (x - 120, 120)], 4, fill=(*PAPER, 1))
        pen.circle(x - 75, 30, 30, 4, fill=(*PAPER, 1))
        pen.circle(x + 75, 30, 30, 4, fill=(*PAPER, 1))
    elif kind == "haveli":                                     # a two-storey haveli: arches below, a jharokha above
        w = 620
        pen.poly([(x - w / 2, 0), (x + w / 2, 0), (x + w / 2, 420), (x - w / 2, 420)], 4, fill=(*PAPER, 1))
        ln([(x - w / 2 - 14, 420), (x + w / 2 + 14, 420)], 5)
        ln([(x - w / 2, 210), (x + w / 2, 210)], 3)
        for k in range(4):
            ax = x - w / 2 + 80 + k * 153
            ln([(ax - 40, 0), (ax - 40, 120), (ax, 165), (ax + 40, 120), (ax + 40, 0)], 3.5)
            pen.poly([(ax - 30, 260), (ax + 30, 260), (ax + 30, 350), (ax - 30, 350)], 3)
            ln([(ax - 40, 250), (ax + 40, 250)], 2.5)
        for k in range(9):
            ln([(x - w / 2 + 20 + k * 72, 420), (x - w / 2 + 20 + k * 72, 450)], 3)
        ln([(x - w / 2 - 10, 450), (x + w / 2 + 10, 450)], 3.5)
        pen.hatch(x - w / 2 + 6, 214, x + w / 2 - 6, 240, 18)
    elif kind == "field":                                      # a ploughed field: furrows and young bajra
        for row in range(4):
            y = -10 - row * 22
            ln([(x - 520 + row * 20, y), (x + 520 - row * 20, y)], 2, PENCIL, 0.75, twice=False, amp=1.5)
        for k in range(16):
            sx = x - 480 + k * 64
            ln([(sx, 0), (sx - 6, 26)], 2, PENCIL, 0.8, twice=False)
            ln([(sx, 0), (sx + 8, 30)], 2, PENCIL, 0.8, twice=False)
    elif kind == "fence":
        ln([(x - 400, 60), (x + 400, 60)], 3)
        ln([(x - 400, 30), (x + 400, 30)], 3)
        for k in range(9):
            ln([(x - 400 + k * 100, 0), (x - 400 + k * 100, 80)], 3.5)
    elif kind == "cactus":
        ln([(x, 0), (x, 200)], 14)
        ln([(x, 90), (x - 50, 100), (x - 50, 160)], 10)
        ln([(x, 120), (x + 45, 130), (x + 45, 175)], 10)
    elif kind == "tulsi":
        pen.poly([(x - 45, 0), (x + 45, 0), (x + 45, 90), (x - 45, 90)], 4, fill=(*PAPER, 1))
        ln([(x - 55, 90), (x + 55, 90)], 4)
        for a in (-40, -15, 15, 40):
            ra = math.radians(90 + a)
            ln([(x, 90), (x + 70 * math.cos(ra), 90 + 70 * math.sin(ra))], 2.5)
    elif kind == "stall":                                       # a fair stall: posts, a striped awning, a counter
        w = 230
        ln([(x - w / 2, 0), (x - w / 2, 200)], 4)
        ln([(x + w / 2, 0), (x + w / 2, 200)], 4)
        pen.poly([(x - w / 2, 70), (x + w / 2, 70), (x + w / 2, 110), (x - w / 2, 110)], 4, fill=(*PAPER, 1))
        pen.poly([(x - w / 2 - 20, 200), (x, 290), (x + w / 2 + 20, 200)], 4, fill=(*PAPER, 1))
        for k in range(6):                                      # the scalloped edge, every other one shaded
            a0 = x - w / 2 - 20 + k * (w + 40) / 6
            pts = [(a0 + (w + 40) / 6 * u / 6, 200 - 22 * math.sin(math.pi * u / 6)) for u in range(7)]
            pen.line(pts, 3)
            if k % 2 == 0:
                pen.poly([(a0, 200), (x + (a0 - x) * 0.05, 288), (a0 + (w + 40) / 6, 200)], 1.5, PENCIL, 0.5,
                         fill=(*INK, 0.18))
        ln([(x, 290), (x, 330)], 3)
        wv = 6 * math.sin(t * 3 + x)
        pen.poly([(x, 330), (x + 40, 320 + wv), (x, 308)], 2.5, fill=(*INK, 0.3))
        for k in range(3):                                      # things for sale on the counter
            pen.circle(x - 60 + k * 60, 126, 15, 3)
    elif kind == "fire":                                        # a fire / pyre: crossed logs and boiling flames
        for dx in (-60, 0, 60):
            ln([(x + dx - 55, 8), (x + dx + 55, 40)], 7)
        n = 5
        for k in range(n):
            fx = x + (k - (n - 1) / 2) * 34
            fh = 90 + 50 * abs(math.sin(t * 7 + k * 1.7))
            pen.poly([(fx - 22, 40), (fx - 10, 40 + fh * 0.5), (fx + 2 * math.sin(t * 9 + k), 40 + fh),
                      (fx + 12, 40 + fh * 0.55), (fx + 22, 40)], 3, fill=(*PAPER, 1), amp=2.2)
            ln([(fx - 6, 44), (fx, 40 + fh * 0.55), (fx + 5, 44)], 2, PENCIL, 0.8, twice=False)
        for k in range(3):                                      # smoke curls
            yy = 220 + k * 60 + (t * 40) % 60
            pen.line([(x - 10 + 14 * math.sin(yy / 30), yy), (x + 14 * math.sin(yy / 30 + 1), yy + 40)], 2, PENCIL,
                     0.6, twice=False)
    elif kind == "throne":
        pen.poly([(x - 80, 0), (x + 80, 0), (x + 80, 90), (x - 80, 90)], 4, fill=(*PAPER, 1))
        pen.poly([(x - 70, 90), (x - 70, 260), (x - 40, 300), (x, 320), (x + 40, 300), (x + 70, 260), (x + 70, 90)], 4,
                 fill=(*PAPER, 1))
        pen.hatch(x - 60, 100, x + 60, 240, 18)
        pen.circle(x, 270, 16, 3)
    elif kind == "pillar":
        for dx in (-140, 140):
            pen.poly([(x + dx - 24, 0), (x + dx + 24, 0), (x + dx + 24, 420), (x + dx - 24, 420)], 4,
                     fill=(*PAPER, 1))
            ln([(x + dx - 40, 420), (x + dx + 40, 420)], 5)
            ln([(x + dx - 6, 20), (x + dx - 6, 400)], 1.6, PENCIL, 0.6, twice=False)
    elif kind == "chest":
        pen.poly([(x - 60, 0), (x + 60, 0), (x + 60, 70), (x - 60, 70)], 4, fill=(*PAPER, 1))
        pen.poly([(x - 64, 70), (x + 64, 70), (x + 56, 100), (x - 56, 100)], 4, fill=(*PAPER, 1))
        pen.circle(x, 70, 9, 3)
    elif kind == "bush":
        pts = [(x + 90 * math.cos(a), 60 * math.sin(a) * (1 + 0.15 * math.sin(a * 7))) for a in
               [math.pi * i / 12 for i in range(13)]]
        pen.poly(pts, 3.5, fill=(*PAPER, 1), amp=2.5)
        for k in range(4):
            ln([(x - 50 + k * 30, 6), (x - 40 + k * 30, 40)], 1.6, PENCIL, 0.6, twice=False)
    elif kind == "log":
        pen.poly([(x - 110, 0), (x + 110, 0), (x + 110, 44), (x - 110, 44)], 4, fill=(*PAPER, 1))
        pen.circle(x + 110, 22, 22, 3.5, fill=(*PAPER, 1))
        pen.circle(x + 110, 22, 9, 2)
    elif kind == "steps":
        for k in range(3):
            w = 420 - k * 90
            pen.poly([(x - w / 2, k * 28), (x + w / 2, k * 28), (x + w / 2, k * 28 + 28), (x - w / 2, k * 28 + 28)],
                     3.5, fill=(*PAPER, 1))
    elif kind == "pots":
        for k, dx in enumerate((-40, 10, 55)):
            r = 24 - 4 * (k % 2)
            pen.circle(x + dx, r, r, 3.5, fill=(*PAPER, 1))
            ln([(x + dx - r * 0.45, 2 * r - 2), (x + dx - r * 0.45, 2 * r + 8), (x + dx + r * 0.45, 2 * r + 8),
                (x + dx + r * 0.45, 2 * r - 2)], 3)
    elif kind == "water":
        for row in range(3):
            y = -40 - row * 26
            xx = x - 500 + (row * 41 + 30 * math.sin(t + row)) % 100
            while xx < x + 500:
                ln([(xx, y), (xx + 22, y + 9), (xx + 44, y)], 2.5, PENCIL, 0.8, twice=False, amp=0.6)
                xx += 120
    elif kind == "umbrella":
        ln([(x, 0), (x, 230)], 4)
        pts = [(x + 150 * math.cos(a), 230 + 70 * math.sin(a)) for a in [math.pi * i / 12 for i in range(13)]]
        pen.poly(pts, 4, fill=(*PAPER, 1))
        for k in range(1, 4):
            ln([(x, 300), (x - 150 + k * 75, 232)], 2, PENCIL, 0.7, twice=False)
    elif kind == "pump":
        ln([(x, 0), (x, 120)], 6)
        ln([(x, 110), (x + 50, 90)], 4)
        ln([(x, 120), (x - 70, 150)], 4)


def _far_line(pen, kind, x0, x1, t):
    """the far edge of the world: hills, the sea or a row of trees, drawn light along the horizon"""
    if kind in ("hills", "mountains", "mountain", "snow"):
        pts = []
        x = x0
        while x <= x1:
            pts.append((x, 200 + 160 * abs(math.sin(x / 520.0)) + 60 * math.sin(x / 170.0)))
            x += 60
        pen.line(pts, 3, PENCIL, 0.8, amp=2.5)
        for i in range(1, len(pts) - 1, 3):                      # a few shading strokes under the ridges
            px, py = pts[i]
            pen.line([(px - 30, py - 30), (px - 60, py - 70)], 1.5, PENCIL, 0.45, twice=False)
    elif kind in ("sea", "river", "lake", "water"):
        for row in range(3):
            y = 40 + row * 45
            x = x0 + (row * 37 + 20 * math.sin(t * 0.8 + row)) % 120
            while x < x1:
                pen.line([(x, y), (x + 20, y + 10), (x + 40, y)], 2, PENCIL, 0.7, twice=False, amp=0.8)
                x += 150
    elif kind in ("dunes", "desert", "sand"):
        pts = []
        x = x0
        while x <= x1:
            pts.append((x, 120 + 90 * abs(math.sin(x / 700.0)) + 25 * math.sin(x / 230.0)))
            x += 60
        pen.line(pts, 3, PENCIL, 0.8, amp=1.5)
        for i in range(2, len(pts) - 1, 4):
            px, py = pts[i]
            pen.line([(px - 40, py - 20), (px + 30, py - 34)], 1.5, PENCIL, 0.45, twice=False)
    elif kind in ("fields", "farmland"):
        for row in range(3):
            y = 30 + row * 40
            pen.line([(x0, y), (x1, y + 6)], 1.8, PENCIL, 0.55, twice=False, amp=2.0)
    elif kind in ("city", "town", "skyline"):
        x = x0
        r = random.Random(4)
        while x < x1:
            w, h = r.uniform(90, 170), r.uniform(150, 330)
            pen.poly([(x, 0), (x + w, 0), (x + w, h), (x, h)], 2.5, PENCIL, 0.7)
            for k in range(2):
                pen.line([(x + w * 0.3, h * (0.4 + 0.3 * k)), (x + w * 0.45, h * (0.4 + 0.3 * k))], 2, PENCIL, 0.5,
                         twice=False)
            x += w + r.uniform(10, 60)
    elif kind in ("forest", "trees", "jungle"):
        x = x0
        while x < x1:
            h = 150 + 50 * math.sin(x * 0.37)
            pen.line([(x, 0), (x, h * 0.5)], 2, PENCIL, 0.6, twice=False)
            pen.circle(x, h * 0.65, h * 0.2, 2, PENCIL, 0.7)
            x += 140 + 40 * abs(math.sin(x))


def _sky(pen, bg, cam, W, H, S, t, night, evening=False):
    """the sun or moon and a few clouds, in screen space (they don't scroll much: far away)"""
    ctx = pen.ctx
    ctx.identity_matrix()
    u = S
    pen.unit = u
    sx = W * 0.8 - (cam.x - 960) * 0.05 * S
    sy = H * 0.18
    if night:
        pen.circle(sx, sy, 48 * u, 3.5, fill=(*PAPER, 1))
        ctx.arc(sx + 22 * u, sy - 10 * u, 44 * u, 0, 2 * math.pi)            # the crescent: shade the rest
        ctx.set_source_rgba(*PENCIL, 0.35)
        ctx.fill()
        r = random.Random(3)
        for _ in range(16):                                                  # stars: little pencil crosses
            x, y = r.uniform(0, W), r.uniform(0, H * 0.35)
            s = r.uniform(5, 10) * u
            pen.line([(x - s, y), (x + s, y)], 1.6, INK, 0.7, twice=False, amp=0.3)
            pen.line([(x, y - s), (x, y + s)], 1.6, INK, 0.7, twice=False, amp=0.3)
    else:
        if evening:                                                          # a low sun, near the hills
            sy = H * 0.27
        pen.circle(sx, sy, 50 * u, 3.5)
        for k in range(12):                                                  # sun rays (they turn a little)
            a = k * math.pi / 6 + t * 0.15
            pen.line([(sx + 66 * u * math.cos(a), sy + 66 * u * math.sin(a)),
                      (sx + 92 * u * math.cos(a), sy + 92 * u * math.sin(a))], 3, INK, 0.9, twice=False)
    n = 0
    for e in bg.elements:
        if e.get("type") != "cloud" or n >= 4:
            continue
        n += 1
        x = (e["x"] * 0.3 + t * 8 - cam.x * 0.08) * S % (W + 300 * u) - 150 * u
        y = H * (0.08 + 0.07 * (n % 3))
        s = 0.7 * u * min(1.4, e.get("scale", 1.0))
        bumps = [(-70, 0, 34), (-25, -18, 44), (25, -14, 40), (68, 2, 30)]
        for bx, by, br in bumps:
            ctx.arc(x + bx * s, y + by * s, br * s, 0, 2 * math.pi)
            ctx.new_sub_path()
        ctx.set_source_rgba(*PAPER, 1)
        ctx.fill()
        for bx, by, br in bumps:
            pen.line([(x + bx * s + br * s * math.cos(a), y + by * s + br * s * math.sin(a))
                      for a in [math.pi * (0.95 + 1.1 * i / 8) for i in range(9)]], 3, INK, 0.85, amp=0.8)
        pen.line([(x - 100 * s, y + 30 * s), (x + 96 * s, y + 30 * s)], 3, INK, 0.85, amp=0.8)
    pen.unit = 1.0


# ---------------------------------------------------------------------------- the stickman (world units, y up)
def _mouth_and_eyes(pen, hx, hy, r, f, face, mouth, blink, view):
    """dot eyes looking the way he faces and a mouth that shows the feeling (and opens to talk)"""
    ln = pen.line
    ctx = pen.ctx
    face = str(face or "neutral").lower()
    if view == "away":
        return
    ex = (0.0 if view == "camera" else 0.32 * r * f)
    eyes = [(hx + ex - 0.28 * r, hy + 0.12 * r), (hx + ex + 0.28 * r, hy + 0.12 * r)]
    if view != "camera":
        eyes = [(hx + ex - 0.05 * r * f, hy + 0.12 * r), (hx + ex + 0.42 * r * f, hy + 0.12 * r)]
    for (x, y) in eyes:
        if blink:
            ln([(x - 0.11 * r, y), (x + 0.11 * r, y)], 3, twice=False, amp=0.3)
        elif face in ("surprised", "scared", "shocked"):
            pen.circle(x, y, 0.13 * r, 2.5, amp=0.3)
            ctx.arc(x, y, 0.05 * r, 0, 2 * math.pi)
            ctx.set_source_rgb(*INK)
            ctx.fill()
        else:
            ctx.arc(x, y, 0.085 * r, 0, 2 * math.pi)
            ctx.set_source_rgb(*INK)
            ctx.fill()
    eyes_lr = sorted(eyes)                                              # (left eye first, whichever way he faces)
    if face in ("angry", "furious"):                                    # brows: the inner ends pulled down
        for (x, y), s in zip(eyes_lr, (-1, 1)):
            ln([(x - 0.15 * r, y + 0.3 * r - 0.08 * r * s), (x + 0.15 * r, y + 0.3 * r + 0.08 * r * s)], 3,
               twice=False, amp=0.3)
    elif face in ("sad", "worried", "scared", "cry", "crying"):         # brows: the inner ends raised
        for (x, y), s in zip(eyes_lr, (-1, 1)):
            ln([(x - 0.15 * r, y + 0.26 * r + 0.08 * r * s), (x + 0.15 * r, y + 0.26 * r - 0.08 * r * s)], 3,
               twice=False, amp=0.3)
    mx = hx + (0.0 if view == "camera" else 0.3 * r * f)
    my = hy - 0.38 * r
    w = 0.3 * r
    m = clamp(float(mouth or 0.0), 0.0, 1.0)
    if m > 0.15 or face in ("surprised", "shocked"):                    # talking / gasping: an open mouth
        hgt = 0.08 * r + 0.22 * r * max(m, 0.6 if face in ("surprised", "shocked") else 0.0)
        ctx.save()
        ctx.translate(mx, my)
        ctx.scale(w * 0.75, hgt)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgb(*INK)
        ctx.fill()
    elif face in ("laugh", "laughing"):                                 # laughing: a big open smile (a "D" on its side)
        ctx.move_to(mx - w, my + 0.04 * r)
        ctx.curve_to(mx - w * 0.6, my - 0.3 * r, mx + w * 0.6, my - 0.3 * r, mx + w, my + 0.04 * r)
        ctx.close_path()
        ctx.set_source_rgb(*INK)
        ctx.fill()
    elif face in ("happy", "excited", "love", "proud"):
        ln([(mx - w, my + 0.06 * r), (mx - w * 0.5, my - 0.08 * r), (mx, my - 0.11 * r), (mx + w * 0.5, my - 0.08 * r),
            (mx + w, my + 0.06 * r)], 3, twice=False, amp=0.3)
    elif face in ("cry", "crying"):                                     # crying: a wobbly turned-down mouth
        ln([(mx - w, my - 0.1 * r), (mx - w * 0.5, my + 0.02 * r), (mx, my + 0.06 * r), (mx + w * 0.5, my + 0.02 * r),
            (mx + w, my - 0.1 * r)], 3.5, twice=False, amp=0.8)
    elif face in ("sad", "worried"):
        ln([(mx - w, my - 0.08 * r), (mx, my + 0.04 * r), (mx + w, my - 0.08 * r)], 3, twice=False, amp=0.3)
    elif face in ("angry", "furious"):
        ln([(mx - w, my - 0.04 * r), (mx + w, my + 0.02 * r)], 3.5, twice=False, amp=0.6)
    else:
        ln([(mx - w * 0.6, my), (mx + w * 0.6, my - 0.02 * r)], 3, twice=False, amp=0.3)
    if face in ("cry", "crying"):                                       # tears down both cheeks, a drop falling
        for ex, ey in eyes:
            ln([(ex, ey - 0.12 * r), (ex - 0.03 * r, ey - 0.35 * r), (ex + 0.01 * r, ey - 0.6 * r)], 2.5,
               (0.35, 0.6, 0.9), twice=False)
            ctx.arc(ex + 0.01 * r, ey - 0.68 * r, 0.06 * r, 0, 2 * math.pi)
            ctx.set_source_rgb(0.45, 0.7, 0.95)
            ctx.fill()


def _hat(pen, c, hx, hy, r, f):
    ln = pen.line
    hat = getattr(c, "hat", "none")
    top = hy + r
    if hat == "cap":
        pen.poly([(hx - r, top - 0.35 * r), (hx + r, top - 0.35 * r), (hx + 0.7 * r, top + 0.15 * r),
                  (hx - 0.7 * r, top + 0.15 * r)], 3.5, fill=(*INK, 1))
        ln([(hx + 0.6 * r * f, top - 0.35 * r), (hx + 1.55 * r * f, top - 0.42 * r)], 5)
    elif hat == "top":
        pen.poly([(hx - 0.6 * r, top - 0.2 * r), (hx + 0.6 * r, top - 0.2 * r), (hx + 0.6 * r, top + 0.9 * r),
                  (hx - 0.6 * r, top + 0.9 * r)], 3.5, fill=(*INK, 1))
        ln([(hx - 1.0 * r, top - 0.2 * r), (hx + 1.0 * r, top - 0.2 * r)], 5)
    elif hat == "crown":
        pen.poly([(hx - 0.7 * r, top - 0.25 * r), (hx + 0.7 * r, top - 0.25 * r), (hx + 0.8 * r, top + 0.5 * r),
                  (hx + 0.4 * r, top + 0.15 * r), (hx, top + 0.6 * r), (hx - 0.4 * r, top + 0.15 * r),
                  (hx - 0.8 * r, top + 0.5 * r)], 3.5, fill=(*PAPER, 1))
    elif hat == "turban":
        ctx = pen.ctx
        ctx.save()
        ctx.translate(hx, top - 0.05 * r)
        ctx.scale(1.12 * r, 0.55 * r)
        ctx.arc(0, 0, 1, math.pi * 0.0, math.pi)
        ctx.restore()
        ctx.set_source_rgba(*PAPER, 1)
        ctx.fill()
        ln([(hx - 1.1 * r, top - 0.1 * r), (hx - 0.9 * r, top + 0.3 * r), (hx - 0.3 * r, top + 0.52 * r),
            (hx + 0.4 * r, top + 0.5 * r), (hx + 1.0 * r, top + 0.25 * r), (hx + 1.1 * r, top - 0.1 * r)], 3.5)
        ln([(hx - 0.9 * r, top + 0.1 * r), (hx + 0.9 * r, top + 0.35 * r)], 2.5)
    elif hat in ("straw", "helmet", "police", "hard_hat", "chef"):
        ln([(hx - 1.3 * r, top - 0.2 * r), (hx + 1.3 * r, top - 0.2 * r)], 4)
        pen.poly([(hx - 0.7 * r, top - 0.2 * r), (hx - 0.6 * r, top + 0.45 * r), (hx + 0.6 * r, top + 0.45 * r),
                  (hx + 0.7 * r, top - 0.2 * r)], 3.5, fill=(*PAPER, 1))


def draw_stickman(pen, c, stt, t):
    """a black stickman on the engine's skeleton (character.solve: the same poses, walks and acting)"""
    from .character import solve
    thing = str((getattr(c, "spec", {}) or {}).get("thing", "") or "").lower()
    if thing:                                             # ✏ a talking thing: a peg, the fire, the sea ...
        return _draw_thing(pen, c, stt, t, thing)
    if c.kind != "human":
        return _draw_animal(pen, c, stt, t)
    sp_ = str((getattr(c, "spec", {}) or {}).get("species", "") or "").lower()
    if sp_ in ANIMALS or sp_ in BIRDS:                    # (an animal the 3D engine doesn't know: drawn in ink)
        return _draw_animal(pen, c, stt, t, sp_)
    ln = pen.line
    s = c.scale
    pose = stt.pose
    r = HEAD_R * s
    J = solve(pose, s, head_r=HEAD_R)
    f = 1 if (stt.facing or 1) >= 0 else -1
    x0, y0 = stt.x, stt.y
    front = stt.view in ("camera", "away")

    def W(p):
        return (x0 + p[0] * f * (0.35 if front else 1.0), y0 + p[1])

    a = stt.alpha
    w = 7.0 * s ** 0.5
    far_a = 0.75 * a
    if front:                                         # facing us / away: arms and legs spread to both sides
        J = dict(J)
    # far limbs first (a touch lighter), then the body, then near limbs
    ln([W(J["sh"]), W(J["ef"]), W(J["hf"])], w * 0.9, INK, far_a)
    ln([W(J["hip"]), W(J["kf"]), W(J["ff"]), W(J["toe_f"])], w * 0.9, INK, far_a)
    ln([W(J["hip"]), W(J["neck"])], w, INK, a)
    if c.gender == "female":                         # a simple A-line dress
        nx, ny = W(J["sh"])
        hx_, hy_ = W(J["hip"])
        ux = hx_ - nx
        pen.poly([(nx - 10 * s, ny), (nx + 10 * s, ny), (hx_ + 40 * s - ux * 0.25, hy_ - 40 * s),
                  (hx_ - 40 * s - ux * 0.25, hy_ - 40 * s)], w * 0.7, INK, a, fill=(*INK, 0.85 * a))
    ln([W(J["hip"]), W(J["kn"]), W(J["fn"]), W(J["toe_n"])], w, INK, a)
    ln([W(J["sh"]), W(J["en"]), W(J["hn"])], w, INK, a)
    hx, hy = W(J["head"])
    if c.gender == "female" or getattr(c, "hair", "") in ("long", "ponytail", "braid"):
        sw = math.sin(t * 6) * 0.08 * r if (stt.mouth or 0) or pose.get("lift", 0) else 0.0
        ln([(hx - 0.7 * r * f, hy + 0.55 * r), (hx - 1.35 * r * f, hy + 0.1 * r + sw), (hx - 1.25 * r * f, hy - 0.5 * r)],
           w * 1.1, INK, a)
    if getattr(c, "species", "") == "monkey":            # a monkey: a curling tail and round ears
        hpx, hpy = W(J["hip"])
        sw = 10 * s * math.sin(t * 3)
        ln([(hpx, hpy), (hpx - 60 * s * f, hpy - 20 * s), (hpx - 90 * s * f, hpy + 40 * s + sw),
            (hpx - 70 * s * f, hpy + 70 * s + sw)], w * 0.7, INK, a)
        pen.circle(hx - 0.9 * r * f, hy + 0.3 * r, 0.32 * r, w * 0.6, INK, a, fill=(*PAPER, a))
    pen.circle(hx, hy, r, w * 0.85, INK, a, fill=(*PAPER, a), amp=0.8)
    if getattr(c, "beard", None) not in (None, "none", "", False) or getattr(c, "mustache", None) not in (None, "none", ""):
        ln([(hx + 0.05 * r * f, hy - 0.22 * r), (hx + 0.55 * r * f, hy - 0.22 * r)], 4, INK, a, twice=False)
    _mouth_and_eyes(pen, hx, hy, r, f, stt.face, stt.mouth, stt.blink, stt.view)
    _hat(pen, c, hx, hy, r, f)
    return {"head": (hx, hy), "r": r, "hand": W(J["hn"]), "facing": f}


# the shape of each animal in ink: body length / height, leg length, head size (story units at scale 1) and its marks
ANIMALS = {
    "dog": dict(bl=120, bh=46, leg=70, hr=26),
    "elephant": dict(bl=240, bh=150, leg=110, hr=62, trunk=True, ears=True, tail=0.5, pillar=True),
    "horse": dict(bl=180, bh=64, leg=140, hr=30, neck=1.0, long_head=True, mane=True),
    "camel": dict(bl=180, bh=64, leg=180, hr=28, neck=1.3, hump=True, long_head=True),
    "cow": dict(bl=190, bh=86, leg=95, hr=36, horns=True, long_head=True),
    "goat": dict(bl=110, bh=50, leg=75, hr=24, horns=True, beard=True),
    "sheep": dict(bl=120, bh=70, leg=55, hr=24, wool=True),
    "fox": dict(bl=120, bh=40, leg=55, hr=24, pointy=True, bushy=True),
    "wolf": dict(bl=140, bh=50, leg=70, hr=28, pointy=True, bushy=True),
    "mouse": dict(bl=46, bh=26, leg=12, hr=14, round_ears=True, thin_tail=True),
    "leopard": dict(bl=160, bh=52, leg=72, hr=28, spots=True),
    "tiger": dict(bl=180, bh=62, leg=80, hr=34, stripes=True),
    "lion": dict(bl=180, bh=62, leg=80, hr=40, mane=True),
    "rhino": dict(bl=220, bh=100, leg=80, hr=42, horn=True, long_head=True, pillar=True),
    "crocodile": dict(bl=380, bh=64, leg=30, hr=32, snout=True, scales=True),
    "donkey": dict(bl=150, bh=56, leg=100, hr=28, neck=0.7, long_ears=True, long_head=True),
    "buffalo": dict(bl=200, bh=90, leg=90, hr=38, horns=True, long_head=True),
    "deer": dict(bl=130, bh=46, leg=110, hr=22, neck=0.8, antlers=True),
    "cat": dict(bl=90, bh=36, leg=45, hr=22, pointy=True),
    "pig": dict(bl=140, bh=70, leg=40, hr=30),
    "rabbit": dict(bl=60, bh=40, leg=20, hr=20, long_ears=True),
}
BIRDS = {"sparrow": dict(r=18), "parrot": dict(r=20, beak="hook", long_tail=True), "hen": dict(r=30, comb=True),
         "eagle": dict(r=30, beak="hook", big=True), "vulture": dict(r=32, beak="hook", big=True, bald=True),
         "crow": dict(r=20), "pigeon": dict(r=20), "duck": dict(r=26, beak="flat"), "owl": dict(r=26),
         "peacock": dict(r=26, long_tail=True), "bird": dict(r=20)}


def _animal_mouth(pen, hx, hy, r, f, stt, a):
    """talking animals open their mouths too"""
    m = clamp(float(stt.mouth or 0.0), 0.0, 1.0)
    mx = hx + 0.55 * r * f
    if m > 0.15:
        pen.line([(mx - 0.25 * r * f, hy - 0.25 * r), (mx + 0.2 * r * f, hy - 0.25 * r - 0.25 * r * m),
                  (mx + 0.2 * r * f, hy - 0.25 * r + 0.1 * r)], 3, INK, a, twice=False, amp=0.3)
    elif str(stt.face or "") in ("happy", "laugh", "excited"):
        pen.line([(mx - 0.25 * r * f, hy - 0.2 * r), (mx, hy - 0.32 * r), (mx + 0.2 * r * f, hy - 0.22 * r)], 2.5,
                 INK, a, twice=False, amp=0.3)


def _draw_animal(pen, c, stt, t, species=None):
    """an ink animal by its species: body, legs that follow the engine's pose, head, ears, horns, trunk, tail"""
    sp = species or getattr(c, "species", "dog")
    s = c.scale
    f = 1 if (stt.facing or 1) >= 0 else -1
    x, y = stt.x, stt.y
    a = stt.alpha
    ctx = pen.ctx
    ln = pen.line
    if c.kind == "bird" or sp in BIRDS:
        B = BIRDS.get(sp, BIRDS["bird"])
        r = B["r"] * s * (1.0 + 0.4 * bool(B.get("big")))
        fly = float(stt.pose.get("lift", 0.0)) > 10.0 or float(stt.pose.get("leg", 0.0)) > 0.6
        flap = math.sin(t * 12) * (1.4 if fly else 0.3) * r
        by = y + (2.2 * r if not fly else 3 * r)
        if not fly:
            ln([(x - 0.2 * r, by - 0.8 * r), (x - 0.25 * r, y)], 2.5, INK, a)
            ln([(x + 0.2 * r, by - 0.8 * r), (x + 0.15 * r, y)], 2.5, INK, a)
        tl = 1.8 if B.get("long_tail") else 1.0
        pen.poly([(x - f * 0.9 * r, by + 0.1 * r), (x - f * (0.9 + 0.9 * tl) * r, by + 0.5 * r),
                  (x - f * (0.9 + 0.8 * tl) * r, by - 0.1 * r)], 3, INK, a, fill=(*PAPER, a))
        pts = [(x + 1.1 * r * math.cos(u), by + 0.8 * r * math.sin(u)) for u in [2 * math.pi * i / 14 for i in range(14)]]
        pen.poly(pts, 3.5, INK, a, fill=(*PAPER, a))
        ln([(x - f * 0.2 * r, by + 0.2 * r), (x - f * 1.0 * r, by + 0.4 * r + flap), (x - f * 0.6 * r, by - 0.1 * r)],
           3, INK, a)
        hx, hy = x + f * 0.95 * r, by + 0.75 * r
        pen.circle(hx, hy, 0.55 * r, 3.5, INK, a, fill=(*PAPER, a))
        if B.get("bald"):
            ln([(hx - 0.6 * r * f, hy - 0.5 * r), (hx - 0.9 * r * f, hy - 0.7 * r)], 2, INK, a, twice=False)
            ln([(x + f * 0.4 * r, by + 0.7 * r), (hx - 0.3 * r * f, hy - 0.3 * r)], 5, PENCIL, a, twice=False)
        if B.get("comb"):
            pen.poly([(hx - 0.3 * r, hy + 0.5 * r), (hx - 0.1 * r, hy + 0.85 * r), (hx + 0.05 * r, hy + 0.55 * r),
                      (hx + 0.25 * r, hy + 0.85 * r), (hx + 0.35 * r, hy + 0.45 * r)], 2.5, INK, a, fill=(*INK, a))
        m = clamp(float(stt.mouth or 0.0), 0.0, 1.0)
        bk = 0.5 * r
        if B.get("beak") == "hook":
            pen.poly([(hx + f * 0.45 * r, hy + 0.15 * r), (hx + f * (0.45 * r + bk), hy - 0.05 * r),
                      (hx + f * (0.35 * r + bk), hy - 0.3 * r), (hx + f * 0.45 * r, hy - 0.12 * r)], 2.5, INK, a,
                     fill=(*INK, a))
        else:
            ln([(hx + f * 0.5 * r, hy + 0.1 * r), (hx + f * (0.5 * r + bk), hy + 0.02 * r + 0.1 * r * m),
                (hx + f * 0.5 * r, hy - 0.08 * r - 0.1 * r * m)], 3, INK, a, twice=False)
        ctx.arc(hx + f * 0.2 * r, hy + 0.12 * r, 0.09 * r, 0, 2 * math.pi)
        ctx.set_source_rgba(*INK, a)
        ctx.fill()
        return {"head": (hx, hy), "r": 0.6 * r, "hand": (hx + f * 0.8 * r, hy), "facing": f}
    A = ANIMALS.get(sp, ANIMALS["dog"])
    pose = stt.pose
    bl, bh, leg, hr = A["bl"] * s, A["bh"] * s, A["leg"] * s, A["hr"] * s
    cy = y + leg + bh * 0.4 + float(pose.get("lift", 0.0)) * s
    for key, dx in (("ff", 0.3), ("bf", -0.32), ("fl", 0.38), ("bl", -0.24)):     # the engine's leg angles (far first)
        a1 = math.radians(float(pose.get(key + "_t", 0.0)))
        a2 = a1 + math.radians(float(pose.get(key + "_s", 0.0)))
        if A.get("pillar"):                               # (an elephant's legs are straight pillars)
            a1 *= 0.6
            a2 = a1
        r0 = (x + f * dx * bl, cy - bh * 0.3)
        kx, ky = r0[0] + f * math.sin(a1) * leg * 0.55, r0[1] - math.cos(a1) * leg * 0.55
        fx, fy = kx + f * math.sin(a2) * leg * 0.5, ky - math.cos(a2) * leg * 0.5
        w_ = 5 if sp != "elephant" else 16
        ln([r0, (kx, ky), (fx, max(fy, y))], w_ * s ** 0.3, INK, a * (0.75 if key[1] == "f" else 1.0))
    if A.get("snout"):                                    # the crocodile: a long low body that narrows to the tail
        pts = [(x + f * bl * 0.45, cy + bh * 0.4), (x - f * bl * 0.1, cy + bh * 0.55), (x - f * bl * 0.6, cy + bh * 0.1),
               (x - f * bl * 0.62, cy - bh * 0.05), (x - f * bl * 0.1, cy - bh * 0.45), (x + f * bl * 0.45, cy - bh * 0.4)]
    else:
        pts = [(x + bl * 0.5 * math.cos(u), cy + bh * 0.5 * math.sin(u)) for u in [2 * math.pi * i / 16 for i in range(16)]]
    if A.get("hump"):
        pts += []
        ln([(x - f * bl * 0.25, cy + bh * 0.4), (x, cy + bh * 1.2), (x + f * bl * 0.2, cy + bh * 0.4)], 4.5, INK, a)
    pen.poly(pts, 5, INK, a, fill=(*PAPER, a))
    if A.get("wool"):
        for k in range(10):
            u = 2 * math.pi * k / 10
            pen.circle(x + bl * 0.45 * math.cos(u), cy + bh * 0.45 * math.sin(u), bh * 0.18, 2.5, INK, a,
                       fill=(*PAPER, a), amp=0.5)
    if A.get("spots") or A.get("stripes") or A.get("scales"):
        rr = random.Random(7)
        for k in range(9):
            sx_, sy_ = x + rr.uniform(-0.38, 0.38) * bl, cy + rr.uniform(-0.25, 0.25) * bh
            if A.get("stripes"):
                ln([(sx_, sy_ + 0.15 * bh), (sx_ + 6 * s, sy_ - 0.15 * bh)], 3, INK, a, twice=False)
            elif A.get("scales"):
                ln([(sx_ - 6 * s, sy_ + 4 * s), (sx_, sy_ + 10 * s), (sx_ + 6 * s, sy_ + 4 * s)], 2, INK, a, twice=False)
            else:
                pen.circle(sx_, sy_, 5 * s, 2, INK, a, fill=(*INK, 0.6 * a), amp=0.3)
    # the head: on a neck for horses / camels, at the front for the rest
    nk = A.get("neck", 0.0)
    if A.get("snout"):
        hx, hy = x + f * (bl * 0.45 + hr * 0.8), cy + bh * 0.05
    elif nk:
        hx, hy = x + f * (bl * 0.55 + hr * 0.5), cy + bh * 0.5 + leg * 0.5 * nk
        ln([(x + f * bl * 0.38, cy + bh * 0.25), (hx - f * hr * 0.4, hy - hr * 0.3)], 9 * s ** 0.4, INK, a)
        if A.get("mane"):
            for k in range(5):
                u = k / 5
                bx_, by_ = x + f * bl * (0.38 + 0.2 * u), cy + bh * 0.4 + (hy - cy - bh * 0.4) * u
                ln([(bx_, by_), (bx_ - f * 14 * s, by_ - 10 * s)], 2.5, INK, a, twice=False)
    else:
        hx, hy = x + f * (bl * 0.5 + hr * 0.4), cy + bh * 0.45
    if A.get("snout"):                                    # a long jaw with teeth
        top = [(hx - f * hr, hy + hr * 0.5), (hx + f * hr * 2.6, hy + hr * 0.15), (hx + f * hr * 2.6, hy - hr * 0.1)]
        m = clamp(float(stt.mouth or 0.0), 0.0, 1.0) * 0.8 + 0.1
        bot = [(hx + f * hr * 2.5, hy - hr * (0.2 + m)), (hx - f * hr * 0.8, hy - hr * 0.5)]
        pen.poly(top + bot, 4, INK, a, fill=(*PAPER, a))
        for k in range(6):
            tx_ = hx + f * hr * (0.1 + 0.4 * k)
            ln([(tx_, hy - hr * 0.08), (tx_ + f * 4 * s, hy - hr * 0.25)], 2, INK, a, twice=False)
        pen.circle(hx - f * hr * 0.2, hy + hr * 0.75, hr * 0.32, 3, INK, a, fill=(*PAPER, a))
        ctx.arc(hx - f * hr * 0.15, hy + hr * 0.78, hr * 0.1, 0, 2 * math.pi)
        ctx.set_source_rgba(*INK, a)
        ctx.fill()
        tail = math.sin(t * 3) * 8 * s
        ln([(x - f * bl * 0.6, cy), (x - f * bl * 0.85, cy - bh * 0.3 + tail)], 4, INK, a)
        return {"head": (hx, hy + hr), "r": hr, "hand": (hx + f * hr, hy), "facing": f}
    if A.get("ears"):                                     # (the elephant's big ear sits behind its head)
        pen.poly([(hx - f * hr * 0.6, hy + hr * 0.9), (hx - f * hr * 1.7, hy + hr * 0.5), (hx - f * hr * 1.6, hy - hr * 1.0),
                  (hx - f * hr * 0.5, hy - hr * 0.7)], 4, INK, a, fill=(*PAPER, a))
    if A.get("long_head"):
        pen.poly([(hx - f * hr * 0.8, hy + hr * 0.6), (hx + f * hr * 1.3, hy + hr * 0.2), (hx + f * hr * 1.3, hy - hr * 0.5),
                  (hx - f * hr * 0.8, hy - hr * 0.6)], 4.5, INK, a, fill=(*PAPER, a))
    else:
        pen.circle(hx, hy, hr, 4.5, INK, a, fill=(*PAPER, a))
    if A.get("trunk"):
        sw = 0.3 * hr * math.sin(t * 2)
        ln([(hx + f * hr * 0.7, hy - hr * 0.2), (hx + f * hr * 1.2, hy - hr * 1.0), (hx + f * (hr * 1.0 + sw), hy - hr * 1.9),
            (hx + f * hr * 1.4, hy - hr * 2.1)], 11 * s ** 0.4, INK, a)
        ln([(hx + f * hr * 0.6, hy - hr * 0.5), (hx + f * hr * 0.9, hy - hr * 0.7)], 4, PAPER, a, twice=False)  # a tusk
    if A.get("ears"):
        pass
    elif A.get("pointy"):
        pen.poly([(hx - f * hr * 0.6, hy + hr * 0.6), (hx - f * hr * 0.5, hy + hr * 1.5), (hx - f * hr * 0.05, hy + hr * 0.85)],
                 3.5, INK, a, fill=(*PAPER, a))
    elif A.get("round_ears"):
        pen.circle(hx - f * hr * 0.3, hy + hr * 0.95, hr * 0.5, 3, INK, a, fill=(*PAPER, a))
    elif A.get("long_ears"):
        ln([(hx - f * hr * 0.3, hy + hr * 0.6), (hx - f * hr * 0.7, hy + hr * 2.0)], 7 * s ** 0.4, INK, a)
    else:
        ln([(hx - 8 * s * f, hy + hr * 0.75), (hx - 16 * s * f, hy + hr * 1.45)], 4, INK, a)
    if A.get("horns"):
        ln([(hx - f * hr * 0.2, hy + hr * 0.8), (hx - f * hr * 0.1, hy + hr * 1.6), (hx + f * hr * 0.3, hy + hr * 1.9)], 4, INK, a)
    if A.get("antlers"):
        ln([(hx - f * hr * 0.1, hy + hr * 0.8), (hx - f * hr * 0.3, hy + hr * 2.2)], 3, INK, a)
        ln([(hx - f * hr * 0.2, hy + hr * 1.6), (hx + f * hr * 0.4, hy + hr * 2.1)], 3, INK, a)
    if A.get("horn"):
        pen.poly([(hx + f * hr * 0.9, hy + hr * 0.15), (hx + f * hr * 1.2, hy + hr * 1.2), (hx + f * hr * 1.3, hy + hr * 0.1)],
                 3, INK, a, fill=(*INK, a))
    if A.get("beard"):
        ln([(hx + f * hr * 0.2, hy - hr * 0.8), (hx + f * hr * 0.1, hy - hr * 1.4)], 3, INK, a, twice=False)
    if A.get("mane") and not nk:                          # a lion: a ring of strokes round the face
        for k in range(12):
            u = 2 * math.pi * k / 12
            ln([(hx + hr * math.cos(u), hy + hr * math.sin(u)), (hx + 1.4 * hr * math.cos(u), hy + 1.4 * hr * math.sin(u))],
               3, INK, a, twice=False)
    ex = hx + f * hr * (0.6 if A.get("long_head") else 0.35)
    ctx.arc(ex, hy + hr * 0.2, max(2.5, 0.12 * hr), 0, 2 * math.pi)
    ctx.set_source_rgba(*INK, a)
    ctx.fill()
    _animal_mouth(pen, hx + f * hr * (0.5 if A.get("long_head") else 0.0), hy, hr, f, stt, a)
    tail = math.sin(t * 5) * 10 * s + float(pose.get("tail", 20.0)) * 0.8 * s
    tx0, ty0 = x - f * bl * 0.5, cy + bh * 0.1
    if A.get("bushy"):
        pen.poly([(tx0, ty0), (tx0 - f * bl * 0.3, ty0 + tail * 0.5 + 10 * s), (tx0 - f * bl * 0.55, ty0 + tail),
                  (tx0 - f * bl * 0.3, ty0 + tail * 0.4 - 12 * s)], 3.5, INK, a, fill=(*PAPER, a))
    elif A.get("thin_tail"):
        ln([(tx0, ty0), (tx0 - f * bl * 0.6, ty0 + 6 * s + tail * 0.4), (tx0 - f * bl * 1.1, ty0 + 30 * s)], 2, INK, a)
    else:
        ln([(tx0, ty0), (tx0 - f * bl * A.get("tail", 0.25), ty0 + tail)], 4, INK, a)
    return {"head": (hx, hy + hr * 0.5), "r": hr, "hand": (hx + f * hr, hy - hr * 0.5), "facing": f}


# ---------------------------------------------------------------------------- talking things (a face on an object)
THINGS = ("fish", "peg", "khoonta", "fire", "aag", "sea", "samudra", "net", "jaal", "stick", "lathi", "snake", "saanp", "clod",
          "dhela", "tree", "pot", "moon", "sun", "cloud", "river", "wind")


def _face_on(pen, x, y, r, f, stt, a):
    """dot eyes and a mouth on a thing (it talks and feels like a person)"""
    _mouth_and_eyes(pen, x, y, r * 1.2, f, stt.face, stt.mouth, stt.blink, "camera")   # (big: it reads from afar)


THING_K = {"peg": 1.7, "fire": 2.3, "sea": 1.3, "net": 1.8, "stick": 1.0, "snake": 1.4, "clod": 2.4, "fish": 2.0}


def _draw_thing(pen, c, stt, t, kind):
    """a talking thing, drawn about as tall as a person (so its face sits where the camera looks for a face)"""
    k = THING_K.get({"khoonta": "peg", "aag": "fire", "samudra": "sea", "jaal": "net", "lathi": "stick",
                     "saanp": "snake", "dhela": "clod", "machhli": "fish"}.get(kind, kind), 1.0)
    if k == 1.0:
        return _draw_thing_at(pen, c, stt, t, kind)
    ctx = pen.ctx
    x, y = stt.x, stt.y
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(k, k)
    ctx.translate(-x, -y)
    info = _draw_thing_at(pen, c, stt, t, kind)
    ctx.restore()
    hx, hy = info["head"]
    info["head"] = (x + (hx - x) * k, y + (hy - y) * k)
    info["r"] *= k
    info["hand"] = (x + (info["hand"][0] - x) * k, y + (info["hand"][1] - y) * k)
    return info


def _draw_thing_at(pen, c, stt, t, kind):
    """a talking peg, fire, sea, net, stick, snake or clod of earth - the old tales give them voices"""
    s = c.scale
    f = 1 if (stt.facing or 1) >= 0 else -1
    x, y = stt.x, stt.y
    a = stt.alpha
    ln = pen.line
    k = {"khoonta": "peg", "aag": "fire", "samudra": "sea", "jaal": "net", "lathi": "stick", "saanp": "snake",
         "dhela": "clod"}.get(kind, kind)
    if k in ("crocodile", "rhino", "magar", "gainda"):
        return _draw_animal(pen, c, stt, t, {"magar": "crocodile", "gainda": "rhino"}.get(k, k))
    if k in ("vulture", "gidh"):
        return _draw_animal(pen, c, stt, t, "vulture")
    if k == "peg":                                       # a wooden peg with a crack in it
        w, h = 70 * s, 190 * s
        pen.poly([(x - w / 2, y), (x + w / 2, y), (x + w * 0.45, y + h), (x + 8 * s, y + h + 14 * s), (x - w * 0.45, y + h)],
                 4.5, INK, a, fill=(*PAPER, a))
        for j in range(3):
            ln([(x - w * 0.3 + j * 18 * s, y + 10 * s), (x - w * 0.25 + j * 18 * s, y + h * 0.45)], 1.6, PENCIL, a,
               twice=False)
        ln([(x - 4 * s, y + h + 10 * s), (x + 4 * s, y + h * 0.75)], 3, INK, a)
        hx, hy, r = x, y + h * 0.62, 34 * s
    elif k == "fire":
        n = 3
        for i in range(n):
            fx = x + (i - 1) * 40 * s
            fh = (170 if i == 1 else 120) * s * (1 + 0.1 * math.sin(t * 7 + i))
            lean = 12 * s * math.sin(t * 5 + i)
            pen.poly([(fx - 40 * s, y), (fx - 38 * s, y + fh * 0.4), (fx - 10 * s + lean, y + fh * 0.75), (fx + lean, y + fh),
                      (fx + 12 * s, y + fh * 0.6), (fx + 40 * s, y + fh * 0.3), (fx + 40 * s, y)], 4, INK, a,
                     fill=(*PAPER, a), amp=1.4)
        hx, hy, r = x, y + 70 * s, 34 * s
    elif k == "sea":                                     # a big wave that rears up
        rise = 10 * s * math.sin(t * 1.5)
        pts = [(x - 200 * s, y), (x - 180 * s, y + 90 * s), (x - 100 * s, y + 170 * s + rise), (x + 20 * s, y + 200 * s + rise),
               (x + 120 * s, y + 160 * s), (x + 90 * s, y + 120 * s), (x + 150 * s, y + 110 * s), (x + 200 * s, y)]
        pen.poly(pts, 4.5, INK, a, fill=(*PAPER, a))
        for j in range(3):
            yy = y + 30 * s + j * 30 * s
            ln([(x - 150 * s, yy), (x - 110 * s, yy + 10 * s), (x - 70 * s, yy)], 2, PENCIL, a, twice=False)
        hx, hy, r = x - 10 * s, y + 120 * s, 40 * s
    elif k == "net":
        pts = [(x - 110 * s, y), (x - 120 * s, y + 90 * s), (x - 40 * s, y + 150 * s), (x + 80 * s, y + 130 * s),
               (x + 120 * s, y + 40 * s), (x + 90 * s, y)]
        pen.poly(pts, 4, INK, a, fill=(*PAPER, a))
        for j in range(7):
            ln([(x - 110 * s + j * 32 * s, y), (x - 70 * s + j * 30 * s, y + 140 * s)], 1.6, PENCIL, a, twice=False)
            ln([(x - 115 * s, y + j * 22 * s), (x + 110 * s, y + 10 * s + j * 18 * s)], 1.6, PENCIL, a, twice=False)
        hx, hy, r = x, y + 80 * s, 34 * s
    elif k == "stick":
        ln([(x, y), (x + 8 * s, y + 260 * s)], 14 * s ** 0.5, INK, a)
        hx, hy, r = x + 5 * s, y + 210 * s, 26 * s
        pen.circle(hx, hy, r, 3.5, INK, a, fill=(*PAPER, a))
    elif k in ("fish", "machhli"):                       # a fish leaping out of the water
        bob = 14 * s * math.sin(t * 3)
        pen.poly([(x - 90 * s, y + 60 * s + bob), (x - 20 * s, y + 110 * s + bob), (x + 70 * s, y + 90 * s + bob),
                  (x + 100 * s, y + 60 * s + bob), (x + 70 * s, y + 30 * s + bob), (x - 20 * s, y + 14 * s + bob)], 4, INK, a,
                 fill=(*PAPER, a))
        pen.poly([(x - 90 * s, y + 60 * s + bob), (x - 140 * s, y + 100 * s + bob), (x - 140 * s, y + 20 * s + bob)], 3.5,
                 INK, a, fill=(*PAPER, a))
        for j in range(3):
            ln([(x - 40 * s + j * 28 * s, y + 40 * s + bob), (x - 30 * s + j * 28 * s, y + 80 * s + bob)], 1.6, PENCIL, a,
               twice=False)
        hx, hy, r = x + 50 * s, y + 66 * s + bob, 30 * s
    elif k == "snake":                                   # coiled, the head raised
        pts = [(x - 120 * s + 240 * s * u, y + 12 * s + 14 * s * math.sin(u * 9 + t * 4)) for u in [i / 16 for i in range(17)]]
        ln(pts, 12 * s ** 0.5, INK, a)
        hx0 = x + f * 120 * s
        ln([(hx0, y + 12 * s), (hx0 + f * 10 * s, y + 80 * s), (hx0 - f * 4 * s, y + 130 * s)], 12 * s ** 0.5, INK, a)
        hx, hy, r = hx0, y + 150 * s, 28 * s
        pen.circle(hx, hy, r, 4, INK, a, fill=(*PAPER, a))
        if (t * 3) % 1 < 0.5:                            # the tongue flicks
            ln([(hx + f * r, hy - r * 0.3), (hx + f * r * 1.6, hy - r * 0.3), (hx + f * r * 1.9, hy - r * 0.1)], 2, INK, a,
               twice=False)
    else:                                                # a clod of earth / anything else: a round lump
        pts = [(x + 70 * s * math.cos(u) * (1 + 0.1 * math.sin(u * 5)), y + 60 * s + 60 * s * math.sin(u))
               for u in [2 * math.pi * i / 16 for i in range(16)]]
        pen.poly(pts, 4.5, INK, a, fill=(*PAPER, a), amp=2.0)
        pen.hatch(x - 40 * s, y + 10 * s, x + 40 * s, y + 40 * s, 12)
        hx, hy, r = x, y + 70 * s, 36 * s
    if k != "stick" and k != "snake":
        pass
    _face_on(pen, hx, hy, r, f, stt, a)
    return {"head": (hx, hy), "r": r, "hand": (hx + f * r, hy - r), "facing": f}


# ---------------------------------------------------------------------------- the story's props (world units)
def _prop_kind(pr):
    s = (str(pr.id) + " " + str(pr.type)).lower()
    for words, kind in ((("sign", "board", "takhti"), "sign"), (("saw", "aari"), "saw"),
                        (("slingshot", "gulel", "catapult"), "slingshot"), (("laddoo", "laddu", "ladoo"), "laddoo"),
                        (("musal", "pestle"), "musal"), (("lakdi", "wood", "gattha", "firewood", "bundle"), "wood"),
                        (("shield", "dhaal", "dhal"), "shield"), (("fish", "machhli", "machli"), "fish"),
                        (("diya", "deepak", "lamp"), "diya"), (("bone", "haddi"), "bone"), (("cap", "topi"), "cap"),
                        (("plate", "thali"), "plate"), (("flower", "phool"), "flower"),
                        (("sack", "bag", "bori", "potli", "jhola"), "sack"),
                        (("cart", "gaadi", "gadi", "bail"), "cart"), (("kalash", "pot", "matka", "ghada", "lota"), "pot"),
                        (("sword", "talwar"), "sword"), (("axe", "farsa", "kulhadi", "pharsa"), "axe"),
                        (("spear", "bhala"), "spear"), (("stick", "lathi", "danda", "tada"), "stick"),
                        (("chest", "box", "trunk", "crate", "sandook"), "chest"),
                        (("sack", "bag", "bori", "potli", "jhola"), "sack"), (("coin", "mohar", "mohur"), "coin"),
                        (("letter", "paper", "chitthi", "scroll"), "letter"), (("stone", "rock", "dhela"), "stone"),
                        (("hukka", "hookah"), "hookah"), (("fire", "alav", "aag"), "fire"),
                        (("roti", "bread"), "roti"), (("apple", "fruit", "mango", "aam"), "fruit"),
                        (("hen", "murgi", "chicken"), "hen"), (("ball",), "ball"), (("book",), "book"),
                        (("spade", "kudal", "phawda", "hoe"), "spade")):
        if any(w in s for w in words):
            return kind
    return "box"


def draw_prop(pen, pr, x, y, f, t, held=False):
    """one of the story's things, drawn in ink; held = (x, y) is the hand that holds it"""
    kind = _prop_kind(pr)
    k = float(getattr(pr, "scale", 1.0) or 1.0)
    gold = any(w in (str(pr.id) + str(pr.type) + str(pr.spec.get("look", ""))).lower()
               for w in ("gold", "mohar", "mohur", "sona", "kalash", "treasure"))
    ln = pen.line
    ctx = pen.ctx
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(k * (f or 1), k)
    if kind == "pot":
        if held:
            ctx.translate(0, -30)                        # (carried against the chest: the hand is under it)
        pen.circle(0, 34, 32, 4, fill=(*PAPER, 1))
        pen.poly([(-16, 60), (16, 60), (20, 76), (-20, 76)], 3.5, fill=(*PAPER, 1))
        ln([(-22, 30), (22, 30)], 2, PENCIL, twice=False)
        if gold:                                          # gold coins shining at the mouth
            for dx in (-12, 0, 12):
                pen.circle(dx, 80, 7, 2.5, fill=(*INK, 0.15))
            for a in (-60, -20, 20, 60):
                ra = math.radians(a + 90)
                ln([(28 * math.cos(ra), 84 + 28 * math.sin(ra)), (44 * math.cos(ra), 84 + 44 * math.sin(ra))], 2,
                   PENCIL, twice=False)
    elif kind == "cart":                                  # a bullock cart: two big wheels, a bed and the bull
        bob = 3 * math.sin(t * 5)
        pen.circle(-40, 55, 55, 4.5, fill=(*PAPER, 1))
        for a in range(0, 180, 45):
            ra = math.radians(a + t * 120)
            ln([(-40 - 55 * math.cos(ra), 55 - 55 * math.sin(ra)), (-40 + 55 * math.cos(ra), 55 + 55 * math.sin(ra))],
               2.2, twice=False)
        pen.poly([(-150, 80), (90, 80), (90, 110), (-150, 110)], 4, fill=(*PAPER, 1))
        ln([(90, 95), (200, 110)], 4)                     # the shaft to the yoke
        bx = 260                                          # the bull
        pen.poly([(bx - 70, 70 + bob), (bx + 60, 70 + bob), (bx + 60, 130 + bob), (bx - 70, 130 + bob)], 4,
                 fill=(*PAPER, 1))
        for dx in (-55, -30, 35, 50):
            sw = 10 * math.sin(t * 6 + dx) if abs(t) > 0 else 0
            ln([(bx + dx, 72 + bob), (bx + dx + sw, 0)], 4.5)
        pen.circle(bx + 85, 125 + bob, 24, 4, fill=(*PAPER, 1))
        ln([(bx + 75, 145 + bob), (bx + 65, 170 + bob)], 3.5)
        ln([(bx + 95, 145 + bob), (bx + 105, 170 + bob)], 3.5)
        ln([(bx - 70, 120 + bob), (bx - 95, 80 + bob)], 3)
        ln([(bx + 70, 70 + bob), (bx + 70, 40 + bob)], 3)    # the hump
    elif kind == "sign":                                  # a signboard on two posts, with its words written on it
        ln([(-110, 0), (-110, 190)], 4)
        ln([(110, 0), (110, 190)], 4)
        pen.poly([(-170, 150), (170, 150), (170, 260), (-170, 260)], 4, fill=(*PAPER, 1))
        text = str(pr.spec.get("text", "") or "")
        if text and not hasattr(ctx, "ops"):
            from . import textfx
            ctx.save()
            if f and f < 0:
                ctx.scale(-1, 1)
            cx_, cy_ = ctx.user_to_device(0, 205)
            dx_, dy_ = ctx.user_to_device_distance(300, 0)
            ctx.restore()
            wpx = math.hypot(dx_, dy_)
            size = max(8.0, wpx / max(4, len(text)) * 1.7)
            lines = textfx.wrap(text, size, wpx)[:2]
            if len(lines) > 1:
                size *= 0.8
                lines = textfx.wrap(text, size, wpx)[:2]
            yy = cy_ + size * 0.35 - (len(lines) - 1) * size * 0.6
            for l_ in lines:
                textfx.show_at(ctx, l_, cx_ - textfx.width(l_, size) / 2, yy, size, (*INK, 1.0))
                yy += size * 1.2
    elif kind == "saw":
        pen.poly([(0, -6), (0, 20), (130, 10), (130, 0)], 3, fill=(*PAPER, 1))
        for k in range(10):
            ln([(10 + k * 12, -2), (16 + k * 12, -10)], 1.6, twice=False)
        pen.poly([(-30, -10), (0, -10), (0, 26), (-30, 26)], 3.5, fill=(*INK, 0.3))
    elif kind == "slingshot":
        ln([(0, -40), (0, 20)], 5)
        ln([(0, 20), (-16, 50)], 4)
        ln([(0, 20), (16, 50)], 4)
        ln([(-16, 50), (0, 30), (16, 50)], 1.6, twice=False)
    elif kind == "laddoo":
        for dx, dy in ((-20, 0), (0, 0), (20, 0), (-10, 18), (10, 18)):
            pen.circle(dx, dy + 12, 11, 2.5, fill=(*PAPER, 1), amp=0.4)
    elif kind == "plate":
        pen.poly([(-40, 0), (40, 0), (50, 10), (-50, 10)], 3, fill=(*PAPER, 1))
    elif kind == "musal":
        ln([(0, -40), (4, 200)], 9)
        ln([(-8, 190), (14, 190)], 4)
    elif kind == "wood":                                  # a bundle of firewood tied with rope
        for k in range(5):
            ln([(-60, 10 + k * 8), (60, 14 + k * 7)], 5)
        ln([(-20, 4), (-20, 52)], 2.5)
        ln([(25, 6), (25, 54)], 2.5)
    elif kind == "shield":
        pen.circle(0, 40, 40, 4, fill=(*PAPER, 1))
        pen.circle(0, 40, 8, 3, fill=(*INK, 1))
    elif kind == "fish":
        pen.poly([(-40, 20), (-10, 38), (30, 30), (44, 20), (30, 10), (-10, 4)], 3.5, fill=(*PAPER, 1))
        pen.poly([(-40, 20), (-62, 36), (-62, 4)], 3, fill=(*PAPER, 1))
        pen.circle(26, 24, 3, 2, fill=(*INK, 1))
    elif kind == "diya":
        pen.poly([(-22, 0), (22, 0), (30, 14), (-30, 14)], 3, fill=(*PAPER, 1))
        fh = 22 + 4 * math.sin(t * 9)
        pen.poly([(-6, 14), (0, 14 + fh), (6, 14)], 2.5, fill=(*PAPER, 1))
    elif kind == "bone":
        ln([(-50, 10), (50, 10)], 9)
        for x_ in (-50, 50):
            pen.circle(x_, 16, 8, 3, fill=(*PAPER, 1))
            pen.circle(x_, 4, 8, 3, fill=(*PAPER, 1))
    elif kind == "cap":
        pen.poly([(-30, 0), (30, 0), (24, 26), (0, 34), (-24, 26)], 3.5, fill=(*PAPER, 1))
    elif kind == "flower":
        ln([(0, 0), (0, 40)], 2.5)
        for a_ in range(0, 360, 60):
            ra = math.radians(a_)
            pen.circle(10 * math.cos(ra), 48 + 10 * math.sin(ra), 7, 2, fill=(*PAPER, 1), amp=0.3)
    elif kind == "sword":
        ln([(0, 0), (8, 150)], 4.5)
        ln([(-16, 6), (16, 0)], 5)
    elif kind == "axe":
        ln([(0, -10), (0, 150)], 5)
        pen.poly([(0, 130), (36, 150), (36, 108), (0, 118)], 3.5, fill=(*PAPER, 1))
    elif kind == "spear":
        ln([(0, -60), (0, 220)], 4)
        pen.poly([(-8, 220), (0, 252), (8, 220)], 3, fill=(*INK, 1))
    elif kind == "stick":
        ln([(0, -60), (6, 160)], 5)
    elif kind == "spade":
        ln([(0, -20), (0, 150)], 5)
        pen.poly([(-22, -20), (22, -20), (16, -60), (-16, -60)], 3.5, fill=(*PAPER, 1))
    elif kind == "chest":
        pen.poly([(-50, 0), (50, 0), (50, 55), (-50, 55)], 4, fill=(*PAPER, 1))
        pen.poly([(-54, 55), (54, 55), (46, 78), (-46, 78)], 4, fill=(*PAPER, 1))
        pen.circle(0, 55, 7, 2.5)
    elif kind == "sack":
        pen.poly([(-34, 0), (34, 0), (38, 56), (14, 72), (-14, 72), (-38, 56)], 4, fill=(*PAPER, 1))
        ln([(-12, 74), (0, 88), (12, 74)], 3)
    elif kind == "coin":
        pen.circle(0, 10, 10, 3, fill=(*PAPER, 1))
    elif kind == "letter":
        pen.poly([(-24, 0), (24, 0), (24, 32), (-24, 32)], 3, fill=(*PAPER, 1))
        ln([(-24, 32), (0, 14), (24, 32)], 2)
    elif kind == "stone":
        pen.poly([(-22, 0), (-16, 20), (8, 26), (22, 10), (20, 0)], 3.5, fill=(*PAPER, 1))
    elif kind == "hookah":
        pen.circle(0, 24, 22, 3.5, fill=(*PAPER, 1))
        ln([(0, 46), (0, 100)], 4)
        pen.poly([(-12, 100), (12, 100), (8, 118), (-8, 118)], 3)
        ln([(0, 60), (-40, 50), (-60, 70)], 2.5)
    elif kind == "fire":                                  # a fire: logs, curling flames, sparks and a little smoke
        for dx in (-40, 0, 40):
            ln([(dx - 40, 6), (dx + 40, 24)], 6)
        for i in range(4):
            fx = (i - 1.5) * 26
            fh = 70 + 40 * abs(math.sin(t * 7 + i * 1.7))
            lean = 10 * math.sin(t * 5 + i)
            pts = [(fx - 18, 26), (fx - 16, 26 + fh * 0.35), (fx - 6 + lean * 0.5, 26 + fh * 0.7), (fx + lean, 26 + fh),
                   (fx + 6 + lean * 0.4, 26 + fh * 0.62), (fx + 16, 26 + fh * 0.3), (fx + 18, 26)]
            pen.poly(pts, 3, fill=(*PAPER, 1), amp=1.2)
            ln([(fx - 5, 30), (fx + lean * 0.4, 26 + fh * 0.5), (fx + 5, 30)], 2, PENCIL, 0.8, twice=False)
        for i in range(3):                                # sparks rising
            u = (t * 0.9 + i * 0.33) % 1.0
            sx_, sy_ = 30 * math.sin(i * 2.1 + t), 120 + 120 * u
            ln([(sx_, sy_), (sx_ + 3, sy_ + 8)], 2.5, INK, 1.0 - u, twice=False, amp=0.2)
        for i in range(2):                                # smoke curls
            yy = 170 + i * 60 + (t * 30) % 60
            ln([(14 * math.sin(yy / 25), yy), (14 * math.sin(yy / 25 + 1), yy + 40)], 2, PENCIL, 0.5, twice=False)
    elif kind == "roti":
        pen.circle(0, 6, 22, 3, fill=(*PAPER, 1))
    elif kind == "fruit":
        pen.circle(0, 14, 14, 3, fill=(*PAPER, 1))
        ln([(0, 28), (4, 38)], 2)
    elif kind == "hen":
        pen.circle(0, 30, 26, 3.5, fill=(*PAPER, 1))
        pen.circle(22, 58, 13, 3, fill=(*PAPER, 1))
        pen.poly([(34, 60), (46, 56), (34, 52)], 2.5, fill=(*INK, 1))
        ln([(-8, 4), (-8, -14)], 3)
        ln([(8, 4), (8, -14)], 3)
    elif kind == "ball":
        pen.circle(0, 16, 16, 3.5, fill=(*PAPER, 1))
    elif kind == "book":
        pen.poly([(-26, 0), (26, 0), (26, 36), (-26, 36)], 3.5, fill=(*PAPER, 1))
    else:
        pen.poly([(-30, 0), (30, 0), (30, 44), (-30, 44)], 3.5, fill=(*PAPER, 1))
    ctx.restore()


# ---------------------------------------------------------------------------- speech bubbles (screen pixels)
def _bubble(pen, text, hx, hy, W, H, S, narration=False):
    """a comic speech bubble near the speaker's head (hx, hy in pixels) with a tail pointing at the mouth"""
    from . import textfx
    ctx = pen.ctx
    ctx.identity_matrix()
    pen.unit = S
    size = (40 if narration else 46) * S
    lines = textfx.wrap(text, size, W * (0.72 if narration else 0.4))[:6]   # (the storyteller gets a wide box)
    tw = max(textfx.width(ln_, size) for ln_ in lines) if lines else 0
    lh = size * 1.25
    bw, bh = tw + 56 * S, lh * len(lines) + 34 * S
    if narration:                                       # the storyteller: a caption box at the top of the page
        bx, by = (W - bw) / 2, 24 * S
        pen.poly([(bx, by), (bx + bw, by), (bx + bw, by + bh), (bx, by + bh)], 3, fill=(1.0, 0.98, 0.9, 1))
    else:
        bx = clamp(hx - bw / 2, 16 * S, W - bw - 16 * S)
        by = clamp(hy - bh - 70 * S, 12 * S, H - bh - 12 * S)
        cx, cy = bx + bw / 2, by + bh / 2
        pts = [(cx + (bw / 2 + 6 * S) * math.cos(a) * min(1.0, 1.25 * abs(math.cos(a)) ** 0.35),
                cy + (bh / 2 + 6 * S) * math.sin(a) * min(1.0, 1.25 * abs(math.sin(a)) ** 0.35))
               for a in [2 * math.pi * i / 28 for i in range(28)]]
        tx = clamp(hx, bx + 30 * S, bx + bw - 30 * S)
        tail = [(tx - 18 * S, by + bh - 2 * S), (hx + (8 if hx > tx else -8) * S, hy - 34 * S),
                (tx + 18 * S, by + bh - 2 * S)]
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        ctx.move_to(*tail[0])
        for p in tail[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        ctx.set_source_rgb(1.0, 0.995, 0.97)
        ctx.fill()
        pen.line(pts, 3.2, close=True, amp=0.7)
        pen.line(tail, 3.2, amp=0.5)
    y = by + 17 * S + size
    for ln_ in lines:
        textfx.show_at(ctx, ln_, bx + (bw - textfx.width(ln_, size)) / 2, y, size, (*INK, 1.0))
        y += lh
    pen.unit = 1.0


# ---------------------------------------------------------------------------- one frame
def _backdrop(ctx, P, it, cam, t, pen, things):
    """everything behind the people: paper, sky, the far world, the ground and the place's deeper things"""
    W, H, S = P.W, P.H, P.S
    bg = it.bg
    ctx.identity_matrix()
    if hasattr(ctx, "ops"):                               # ▶ live player: plain paper (no picture is sent)
        ctx.set_source_rgb(*PAPER)
    else:
        ctx.set_source_surface(_paper(W, H)[0], 0, 0)
    ctx.paint()
    tw = str(getattr(bg, "time", "day") or "day").lower()
    night = tw in ("night", "midnight")
    if night:                                             # night: the page is shaded over with soft pencil
        ctx.set_source_rgba(0.2, 0.22, 0.3, 0.22)
        ctx.paint()
    elif tw in ("evening", "sunset", "dusk"):             # evening: a warm wash, like a tea-stained page
        ctx.set_source_rgba(0.85, 0.55, 0.25, 0.08)
        ctx.paint()
    pen.thing("sky")
    _sky(pen, bg, cam, W, H, S, t, night, tw in ("evening", "sunset", "dusk", "morning", "dawn", "sunrise"))
    # the far world and the ground line (in the far / ground layers so the camera moves them with depth)
    x_lo = cam.x - W / (S * max(cam.z, 0.3)) * 0.9 - 400
    x_hi = cam.x + W / (S * max(cam.z, 0.3)) * 0.9 + 400
    far = (bg.spec or {}).get("far") if isinstance(getattr(bg, "spec", None), dict) else None
    if isinstance(far, str):
        far = [far]
    pf = p_of_z(1000)
    for k, kind in enumerate(far or ["hills"]):
        set_layer(ctx, cam, pf, W, H, S)
        ctx.translate(0, lift_of_p(pf))
        pen.thing(("far", k))
        _far_line(pen, str(kind).lower(), x_lo / pf - 600, x_hi / pf + 600, t)
    set_layer(ctx, cam, pf, W, H, S)
    ctx.translate(0, lift_of_p(pf))
    pen.thing("horizon")
    pen.line([(x_lo - 900, 0), (x_hi + 900, 0)], 2.5, PENCIL, 0.7, amp=1.0)
    set_layer(ctx, cam, 1.0, W, H, S)
    pen.thing("ground")
    pen.line([(x_lo, -6), (x_hi, -6)], 4, INK, 0.9, amp=2.0)
    r = random.Random(11)
    x = x_lo - (x_lo % 260)
    while x < x_hi:                                       # grass tufts along the ground
        if r.random() < 0.6:
            pen.line([(x - 8, -6), (x - 2, 14)], 2, PENCIL, 0.7, twice=False, amp=0.4)
            pen.line([(x + 2, -6), (x + 8, 18)], 2, PENCIL, 0.7, twice=False, amp=0.4)
        x += 120 + 140 * r.random()
    for z, key, o, kind in things:
        _thing_at(ctx, P, cam, pen, z, key, o, kind, t)


def _thing_at(ctx, P, cam, pen, z, key, o, kind, t):
    p = p_of_z(z)
    set_layer(ctx, cam, p, P.W, P.H, P.S)
    ctx.translate(0, lift_of_p(p))
    pen.thing(key)
    h = clamp(float(o.get("height") or 300) * float(o.get("scale", 1.0) or 1.0), 160, 520)
    pen.fade = clamp(0.62 - 0.9 * (p - 0.42) / 0.58, 0.0, 0.55)       # (far = paler: the air between us)
    _scenery_thing(pen, kind, float(o.get("x", 0)), h, t)
    pen.fade = 0.0


def draw_scene(ctx, P, it, lt, cue=None):
    """a whole scene frame in the sketch look"""
    W, H, S = P.W, P.H, P.S
    sc, bg = it.scene, it.bg
    f = clamp(int(lt * P.fps), 0, len(it.cams) - 1)
    cam = it.cams[f]
    frame = int(lt * P.fps)
    step = frame // BOIL
    t = step * BOIL / P.fps                               # the wobble and little moving things are drawn "on fours"
    sid = 7919 * (zlib.crc32(str(getattr(sc, "id", "")).encode()) & 0xFFFF)
    seed = step + sid
    bstep = frame // BACK_BOIL
    bseed, bt = bstep + sid, bstep * BACK_BOIL / P.fps
    states, people = {}, []
    for cid, tr in sc.tracks.items():
        stt = tr.state(lt, sc)
        if stt.alpha <= 0.02:
            continue
        states[cid] = stt
        people.append((float(getattr(stt, "z", 0.0) or 0.0), cid, tr, stt))
    zcut = max((e[0] for e in people), default=-1e9)
    back, front = [], []                                  # things deeper than everyone go in the cached backdrop
    for i, o in enumerate(getattr(bg, "place_objects", None) or []):
        kind = _kind_of(o)
        if kind:
            z = float(o.get("z", 600) or 0)
            (back if z > zcut else front).append((z, ("o", i), o, kind))
    back.sort(key=lambda e: -e[0])
    key = (id(it), bseed, W, H, round(cam.x, 2), round(cam.y, 2), round(cam.z, 4), round(cam.sx, 2), round(cam.sy, 2),
           tuple(e[1] for e in back))
    got = _BACK.get("k")
    if hasattr(ctx, "ops"):                               # ▶ live player: the backdrop is drawn as steps too
        _backdrop(ctx, P, it, cam, bt, Pen(ctx, bseed), back)
    elif got is None or got[0] != key:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        bctx = cairo.Context(surf)
        bctx.set_antialias(cairo.ANTIALIAS_BEST)
        _backdrop(bctx, P, it, cam, bt, Pen(bctx, bseed), back)
        got = _BACK["k"] = (key, surf)
    if not hasattr(ctx, "ops"):
        ctx.identity_matrix()
        ctx.set_source_surface(got[1], 0, 0)
        ctx.paint()
    pen = Pen(ctx, seed)
    # the nearer things and the people, back to front (deeper = smaller, higher and paler)
    layers = [(z, 0, k, ("thing", o, kind)) for z, k, o, kind in front]
    layers += [(z, 1, cid, ("who", tr, stt)) for z, cid, tr, stt in people]
    held = {}                                             # the story's props: in a hand, on the ground, a cart
    place_ids = {o.get("id") for o in (getattr(bg, "place_objects", None) or [])}
    for pid, pr in (getattr(sc, "props", None) or {}).items():
        if pid in place_ids:
            continue
        st_ = pr.at(lt)[0]
        if st_[0] == "in":
            continue                                      # (in a bag / a trunk: not seen)
        if st_[0] == "held":
            held.setdefault(st_[1], []).append(pr)
        else:
            layers.append((float(pr.z_at(lt) or 0.0), 0.5, pid, ("prop", pr, None)))
    layers.sort(key=lambda e: (-e[0], e[1], str(e[2])))
    heads = {}
    for z, _k, key, (what, a1, a2) in layers:
        if what == "thing":
            _thing_at(ctx, P, cam, pen, z, key, a1, a2, t)
            continue
        if what == "prop":
            p = p_of_z(z)
            set_layer(ctx, cam, p, W, H, S)
            ctx.translate(0, lift_of_p(p))
            pen.thing(key)
            x_, y_, f_ = a1.pos(lt)
            draw_prop(pen, a1, x_, y_, f_, t, held=False)
            continue
        p = p_of_z(z)
        set_layer(ctx, cam, p, W, H, S)
        ctx.translate(0, lift_of_p(p))
        pen.thing(key)
        st_ = a2                                                         # a scribbled shadow at the feet
        if getattr(st_, "y", 0.0) < 400:
            sw = 46 * a1.cdef.scale * (1.6 if a1.cdef.kind != "human" else 1.0)
            k_ = clamp(1.0 - st_.y / 400.0, 0.2, 1.0)
            for j in range(4):
                pen.line([(st_.x - sw * k_ + j * 6, -4 - j * 3), (st_.x + sw * k_ - j * 6, -2 - j * 3)], 2.2,
                         PENCIL, 0.55 * st_.alpha, twice=False, amp=1.2)
        info = draw_stickman(pen, a1.cdef, a2, t)
        for pr in held.get(key, ()):                      # what they hold, in their hand
            draw_prop(pen, pr, info["hand"][0], info["hand"][1], info["facing"], t, held=True)
        hx, hy = ctx.user_to_device(*info["head"])
        heads[key] = (hx, hy, info["r"] * S * p * max(cam.z, 0.3))
    # the talking: a speech bubble by the speaker (subtitles are not drawn in the sketch look)
    if cue is not None:
        who = None
        for cid, tr in sc.tracks.items():
            if cue.speaker and cue.speaker in (cid, tr.cdef.name) and cid in heads:
                who = cid
        if who is not None and not cue.narration:
            hx, hy, hr = heads[who]
            _bubble(pen, cue.text, hx, hy - hr, W, H, S)
        else:
            _bubble(pen, cue.text, W / 2, 0, W, H, S, narration=True)
    ctx.identity_matrix()


def draw_card(ctx, P, it, lt):
    """the title / end page: big hand-lettered words on the paper"""
    from . import textfx
    W, H, S = P.W, P.H, P.S
    ctx.identity_matrix()
    if hasattr(ctx, "ops"):
        ctx.set_source_rgb(*PAPER)
    else:
        ctx.set_source_surface(_paper(W, H)[0], 0, 0)
    ctx.paint()
    title = it.kind == "title"
    text = P.title if title else it.spec.get("text", "The End")
    sub = P.settings.get("subtitle", "") if title else it.spec.get("sub", "")
    pen = Pen(ctx, int(lt * P.fps) // BOIL, S)
    size = (110 if len(text) < 22 else 76) * S
    wd = textfx.width(text, size)
    if wd > W * 0.86:
        size *= W * 0.86 / wd
        wd = textfx.width(text, size)
    x, y = (W - wd) / 2, H * 0.47
    textfx.show_at(ctx, text, x, y, size, (*INK, 1.0))
    pen.line([(x, y + 22 * S), (x + wd, y + 16 * S)], 5, amp=2.0)                   # a hand-drawn underline
    if sub:
        s2 = 44 * S
        textfx.show_at(ctx, sub, (W - textfx.width(sub, s2)) / 2, y + 100 * S, s2, (*PENCIL, 1.0))
    # a little stickman waving in the corner (the page's signature)
    from .timeline import CharState
    from .character import CharacterDef
    from . import poses
    st = CharState()
    st.x, st.y, st.facing, st.alpha, st.blink, st.view = 0.0, 0.0, 1, 1.0, False, "side"
    st.face, st.mouth, st.z = "happy", 0.0, 0.0
    pz = poses.a_wave(lt, 3.0, {})
    st.pose = pz[0] if isinstance(pz, tuple) else pz
    ctx.identity_matrix()
    ctx.translate(W * 0.82, H * 0.9)
    ctx.scale(0.9 * S, -0.9 * S)
    pen.unit = 1.0
    draw_stickman(pen, CharacterDef("sketch_signer", {}), st, lt)
    ctx.identity_matrix()
