"""More nature for backgrounds: sky looks, cloud styles, sky extras and more kinds of trees.

Background options (any preset):
  "sky":    "dawn" | "golden" | "dusk" | "pink" | "overcast" | "stormy" | "hazy" | "deep_blue" | "aurora" |
            "milky_way" | "clear"                      the colours of the sky (the light still follows "time")
  "time":   also accepts dawn, golden_hour, dusk, twilight, noon, afternoon, midnight (mapped to the light + sky)
  "clouds": "none" | "few" | "some" | "many" | "overcast" | "puffy" | "cirrus" | "storm" | "mixed" or a number
  "rainbow": true    "stars": true (evening too)   "shooting_star": true   "moon": "full" | "half" | "crescent"
  "sun": false       "birds": true (a flock crossing the sky)
  "trees":  "neem" or ["gulmohar", "neem"] - the kinds of tree the place grows (every preset)
Tree kinds (elements {"type": "tree", "kind": ...}):
  round pine palm banyan mango coconut banana_tree acacia cactus_tree bare blossom mushroom_tree
  neem peepal gulmohar jacaranda amaltas bamboo willow birch autumn cypress fir ashoka eucalyptus oak apple
  dead baobab
"""
import math

import cairo

from . import realworld as rw
from .util import hex_to_rgb, mix, darker, lighter, seeded, TAU

# sky colours: (top, middle or None, bottom)
SKY_LOOKS = {
    "clear": ("#4ea8e8", None, "#d8f1fd"),
    "deep_blue": ("#1f6fd1", None, "#9fd3f5"),
    "dawn": ("#5b6bb0", "#e8a5b5", "#fcd9b0"),
    "golden": ("#6aa3d8", "#f7c77e", "#ffd99a"),
    "dusk": ("#232553", "#7a4a8a", "#e9866b"),
    "pink": ("#b98bd8", "#f4a6c6", "#ffd1dc"),
    "overcast": ("#8d98a6", None, "#c9d0d8"),
    "stormy": ("#3b4250", "#56606e", "#7c8591"),
    "hazy": ("#9ec3dc", None, "#efe6d2"),
    "aurora": ("#030a1e", "#0b2a3d", "#123a4a"),
    "milky_way": ("#02040f", "#0a1030", "#1b2350"),
}
TIME_WORDS = {"dawn": ("morning", "dawn"), "sunrise": ("morning", "dawn"), "golden_hour": ("sunset", "golden"),
              "golden": ("sunset", "golden"), "dusk": ("evening", "dusk"), "twilight": ("evening", "dusk"),
              "noon": ("day", "deep_blue"), "afternoon": ("day", None), "midday": ("day", "deep_blue"),
              "midnight": ("night", "milky_way"), "late_night": ("night", None)}
CLOUD_STYLES = ("none", "few", "some", "many", "overcast", "puffy", "cirrus", "storm", "mixed")
MORE_TREES = ("neem", "peepal", "gulmohar", "jacaranda", "amaltas", "bamboo", "willow", "birch", "autumn",
              "cypress", "fir", "ashoka", "eucalyptus", "oak", "apple", "dead", "baobab")
TREE_ALIASES = {"pipal": "peepal", "bodhi": "peepal", "peepal_tree": "peepal", "neem_tree": "neem",
                "gulmohur": "gulmohar", "flame_tree": "gulmohar", "golden_shower": "amaltas", "laburnum": "amaltas",
                "maple": "autumn", "fall": "autumn", "autumn_tree": "autumn", "christmas_tree": "fir", "spruce": "fir",
                "weeping_willow": "willow", "white_birch": "birch", "apple_tree": "apple", "fruit_tree": "apple",
                "spooky": "dead", "dead_tree": "dead", "haunted": "dead", "cherry": "blossom", "sakura": "blossom",
                "palm_tree": "palm", "coconut_tree": "coconut", "pine_tree": "pine", "banyan_tree": "banyan",
                "mango_tree": "mango", "oak_tree": "oak", "bamboo_grove": "bamboo"}


def canon_tree(k):
    k = str(k or "round").lower().strip().replace(" ", "_").replace("-", "_")
    return TREE_ALIASES.get(k, k)


class NatureMixin:
    # ================================================================== options
    def _nature_setup(self):
        """Called from Background.__init__ after the preset: sky look, clouds, extras, tree kinds."""
        spec, r = self.spec, seeded(int(self.spec.get("seed", 5)) + 17)
        W = self.world_w
        self.sky_look = self._sky_look_name()
        if self.indoor or self.time == "space":
            return
        w = self.weather
        # --- clouds
        style = spec.get("clouds")
        if style is None and w in ("overcast", "cloudy"):
            style = "overcast"
        if style is None and self.sky_look in ("stormy",):
            style = "storm"
        if style is not None:
            self._set_clouds(style, r)
        if w in ("overcast", "cloudy", "fog", "mist", "foggy") or self.sky_look in ("overcast", "stormy"):
            for e in self.elements:
                if e["type"] == "sun":
                    e["type"] = "_hidden_sun"
        if w in ("fog", "mist", "foggy") and not any(e["type"] == "fog" for e in self.elements):
            self._add("fog", 0, p=0.9, layer="front")
        # --- extras
        if spec.get("sun") is False:
            self.elements = [e for e in self.elements if e["type"] != "sun"]
        if spec.get("moon") and not any(e["type"] == "moon" for e in self.elements) and self.time in (
                "night", "evening", "sunset"):
            self._add("moon", 1480, p=0.02, layer="sky")
        if spec.get("rainbow"):
            self._add("rainbow", float(spec.get("rainbow_x", self.world_w * 0.55)), p=0.05, layer="sky")
        if spec.get("shooting_star") or spec.get("shooting_stars"):
            self._add("shooting_star", 0, p=0.02, layer="sky")
        if self.sky_look == "aurora" or spec.get("aurora"):
            self._add("aurora", 0, p=0.02, layer="sky")
        if spec.get("birds") and not getattr(self, "_flock", False):
            self._flock = True
            self._add("flock", 0, p=0.06, layer="sky", seed=r.random())
        # --- trees
        kinds = spec.get("trees") or spec.get("tree")
        if kinds:
            kinds = [canon_tree(k) for k in (kinds if isinstance(kinds, (list, tuple)) else [kinds])]
            snow = self.preset in ("snow",)
            if not any(e["type"] in ("tree", "jungle_tree") for e in self.elements):
                for x in range(-400, int(W) + 500, 330):          # the place had no trees: plant a row behind
                    self._add("tree", x + r.uniform(-90, 90), p=0.72, layer="back", kind=r.choice(kinds),
                              scale=r.uniform(0.75, 1.05))
            for e in self.elements:
                if e["type"] in ("tree", "jungle_tree") and not (snow and e.get("kind") == "pine"):
                    e["type"] = "tree"
                    e["kind"] = r.choice(kinds)
                    e.pop("color", None) if e["kind"] in MORE_TREES else None

    def _sky_look_name(self):
        s = self.spec.get("sky")
        if isinstance(s, str) and s.lower() in SKY_LOOKS:
            return s.lower()
        return getattr(self, "_time_sky", None)

    def _set_clouds(self, style, r):
        self.elements = [e for e in self.elements if e["type"] != "cloud"]
        if isinstance(style, (int, float)):
            n, kind = int(style), "normal"
        else:
            style = str(style).lower()
            n, kind = {"none": (0, "normal"), "few": (3, "normal"), "some": (6, "normal"), "many": (12, "normal"),
                       "overcast": (16, "overcast"), "puffy": (7, "puffy"), "cirrus": (7, "cirrus"),
                       "storm": (12, "storm"), "mixed": (10, "mixed")}.get(style, (6, "normal"))
        for k in range(n):
            kd = kind if kind != "mixed" else r.choice(["normal", "puffy", "cirrus", "normal"])
            y = r.uniform(560, 830) if kd != "cirrus" else r.uniform(760, 900)
            if kd in ("overcast", "storm"):
                y = r.uniform(620, 900)
            sc = r.uniform(0.6, 1.2) * {"puffy": 1.5, "overcast": 2.2, "storm": 2.0}.get(kd, 1.0)
            self._add("cloud", r.uniform(-400, 2800), p=0.08, layer="sky", y=y, scale=sc, speed=r.uniform(4, 12),
                      kind=kd)

    # ================================================================== sky colours
    def sky_colors(self):
        """(top, middle or None, bottom) rgb for the sky gradient, or None for the normal time-of-day sky."""
        look = getattr(self, "sky_look", None)
        if not look:
            return None
        top, mid, bot = SKY_LOOKS[look]
        top, bot = hex_to_rgb(top), hex_to_rgb(bot)
        mid = hex_to_rgb(mid) if mid else None
        dark = {"night": 0.55, "evening": 0.2}.get(self.time, 0.0) if look not in ("aurora", "milky_way", "dusk") else 0.0
        if dark:
            top, bot = mix(top, (0.02, 0.04, 0.12), dark), mix(bot, (0.05, 0.08, 0.2), dark)
            mid = mix(mid, (0.04, 0.06, 0.16), dark) if mid else None
        return top, mid, bot

    def sky_stars(self):
        look = getattr(self, "sky_look", None)
        return look in ("aurora", "milky_way", "dusk") or bool(self.spec.get("stars")) and self.time != "day"

    def draw_sky_extras(self, ctx, W, H, t):
        """Stars for the special night skies + the milky way band (screen space, behind everything)."""
        look = getattr(self, "sky_look", None)
        if look == "milky_way":
            ctx.save()
            ctx.translate(W * 0.5, H * 0.3)
            ctx.rotate(-0.5)
            for k, (a, wmul) in enumerate(((0.10, 0.34), (0.08, 0.2), (0.12, 0.1))):
                g = cairo.LinearGradient(0, -H * wmul, 0, H * wmul)
                g.add_color_stop_rgba(0, 0.8, 0.8, 1.0, 0)
                g.add_color_stop_rgba(0.5, 0.85, 0.82, 1.0, a)
                g.add_color_stop_rgba(1, 0.8, 0.8, 1.0, 0)
                ctx.set_source(g)
                ctx.rectangle(-W, -H * wmul, W * 2, H * wmul * 2)
                ctx.fill()
            rr = seeded(31)
            for k in range(420):
                x, y = rr.uniform(-W, W), rr.gauss(0, H * 0.09)
                ctx.set_source_rgba(1, 1, 1, rr.uniform(0.25, 0.8))
                ctx.arc(x, y, rr.uniform(0.4, 1.3) * H / 1080, 0, TAU)
                ctx.fill()
            ctx.restore()
        if self.sky_stars() and not self.night:
            rr = seeded(8)
            fade = 0.55 if look == "dusk" else 0.9
            for k in range(110):
                x, y = rr.uniform(0, W), rr.uniform(0, H * (0.4 if look == "dusk" else 0.62))
                tw = 0.55 + 0.45 * math.sin(t * rr.uniform(1, 3) + k)
                ctx.set_source_rgba(1, 1, 0.92, fade * tw * (1 - y / (H * 0.7)))
                ctx.arc(x, y, rr.uniform(0.7, 2.0) * H / 1080, 0, TAU)
                ctx.fill()

    # ================================================================== sky elements
    def _d__hidden_sun(self, ctx, e, t):
        return

    def _cloud_kind(self, ctx, e, t, x, y, s, col):
        kind = e.get("kind", "normal")
        if kind == "cirrus":                                   # thin wispy streaks high up
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            for k in range(4):
                ctx.set_source_rgba(*col, 0.35 - k * 0.05)
                ctx.set_line_width((10 - k * 2) * s)
                ctx.move_to(x - 120 * s + k * 20 * s, y + k * 10 * s)
                ctx.curve_to(x - 40 * s, y + 18 * s + k * 8 * s, x + 60 * s, y - 6 * s + k * 6 * s,
                             x + 170 * s - k * 15 * s, y + 14 * s + k * 9 * s)
                ctx.stroke()
            return True
        if kind == "puffy":                                    # tall cumulus with a shaded base
            base = darker(col, 0.86)
            ctx.set_source_rgba(*base, 0.95)
            ctx.save()
            ctx.translate(x + 50 * s, y - 18 * s)
            ctx.scale(150 * s, 30 * s)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.fill()
            for dx, dy, rr in ((-60, 0, 42), (-15, 30, 58), (45, 52, 66), (100, 25, 52), (140, -2, 38),
                               (25, 5, 55)):
                ctx.set_source_rgba(*col, 0.97)
                ctx.arc(x + dx * s, y + dy * s, rr * s, 0, TAU)
                ctx.fill()
            ctx.set_source_rgba(1, 1, 1, 0.35)
            ctx.arc(x + 30 * s, y + 80 * s, 30 * s, 0, TAU)
            ctx.fill()
            return True
        if kind in ("overcast", "storm"):                      # wide flat grey sheets
            c2 = col if kind == "overcast" else mix(col, (0.22, 0.24, 0.3), 0.55)
            for k, (dx, dy, rx, ry) in enumerate(((0, 0, 220, 55), (160, 20, 180, 50), (-150, 15, 170, 45),
                                                  (60, -25, 240, 40))):
                ctx.set_source_rgba(*darker(c2, 1.0 - 0.05 * k), 0.93)
                ctx.save()
                ctx.translate(x + dx * s, y + dy * s)
                ctx.scale(rx * s, ry * s)
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.restore()
                ctx.fill()
            return True
        return False

    def _d_rainbow(self, ctx, e, t):
        if self.weather in ("storm", "cyclone") or self.night:
            return
        x, R = e["x"], float(e.get("radius", 900))
        cols = ("#ff595e", "#ff924c", "#ffca3a", "#8ac926", "#1982c4", "#4267ac", "#6a4c93")
        ctx.set_line_width(26)
        for k, c in enumerate(cols):
            ctx.set_source_rgba(*hex_to_rgb(c), 0.42)
            ctx.arc(x, -150, R - k * 24, 0.05 * math.pi, 0.95 * math.pi)
            ctx.stroke()

    def _d_shooting_star(self, ctx, e, t):
        per = float(e.get("every", 5.0))
        u = (t % per) / 0.9
        if u > 1.0:
            return
        k = int(t // per)
        rr = seeded(k * 7 + 3)
        x0, y0 = rr.uniform(300, 1700), rr.uniform(780, 960)
        x, y = x0 + 520 * u, y0 - 240 * u
        g = cairo.LinearGradient(x, y, x - 180, y + 80)
        g.add_color_stop_rgba(0, 1, 1, 1, 0.95 * (1 - u))
        g.add_color_stop_rgba(1, 1, 1, 1, 0)
        ctx.set_source(g)
        ctx.set_line_width(3)
        ctx.move_to(x, y)
        ctx.line_to(x - 180, y + 80)
        ctx.stroke()

    def _d_aurora(self, ctx, e, t):
        for k, (c, yb, amp) in enumerate((("#39ff9f", 700, 60), ("#4fd1ff", 780, 45), ("#b36bff", 860, 35))):
            rgb = hex_to_rgb(c)
            for j in range(3):
                ph = t * (0.25 + 0.1 * k) + j * 1.7 + k
                ctx.move_to(-2400, yb)
                for xx in range(-2400, int(self.world_w) + 2600, 120):
                    ctx.line_to(xx, yb + amp * math.sin(xx * 0.0023 + ph) + 20 * math.sin(xx * 0.009 + ph * 1.7))
                g = cairo.LinearGradient(0, yb - 40, 0, yb + 260)
                g.add_color_stop_rgba(0, *rgb, 0.0)
                g.add_color_stop_rgba(0.25, *rgb, 0.16)
                g.add_color_stop_rgba(1, *rgb, 0.0)
                ctx.line_to(self.world_w + 2600, yb + 300)
                ctx.line_to(-2400, yb + 300)
                ctx.close_path()
                ctx.set_source(g)
                ctx.fill()

    def _d_flock(self, ctx, e, t):
        """A flock of birds crossing the sky every ~14 s - real flocking (boids), not a fixed V."""
        from . import boids
        per = 14.0
        tt = t + e.get("seed", 0.3) * per
        n = int(tt / per)
        u = (tt % per) / per
        if u > 0.85:
            return
        Wf = self.world_w + 1800
        sim = boids.sky_flock(int(Wf), 900, int(e.get("seed", 0.3) * 1000 + n * 13) % 997, period=per * 0.85,
                              n=7 + n % 5)
        col = (0.12, 0.12, 0.16) if not self.night else (0.7, 0.7, 0.8)
        ctx.save()
        ctx.translate(-600, 1180)
        ctx.scale(1, -1)                                   # the flock works in screen space (y down)
        boids.draw_birds(ctx, sim, u * per, 1.3, col, 0.8, size=12)
        ctx.restore()

    # ================================================================== trees
    def _tree_more(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", 0)
        kind = e.get("kind")
        sh = self._shade
        trunk = sh("#6b4a2b")
        sway = 3 * rw.sway(t, x, 0.9)                       # the scene wind (engine/realworld.py)
        rr = seeded(int(x * 7) + 1)

        def blobs(items, col, dark=0.1):
            for k, (dx, dy, r_) in enumerate(items):
                ctx.set_source_rgb(*mix(col, (0, 0, 0), dark * ((k % 3) / 2.0)))
                ctx.arc(x + dx * s + sway * dy / 220, y + dy * s, r_ * s, 0, TAU)
                ctx.fill()

        def dots(col, n, cx, cy, rx, ry, r_):
            ctx.set_source_rgb(*col)
            for _ in range(n):
                a, d = rr.uniform(0, TAU), math.sqrt(rr.random())
                ctx.arc(x + (cx + math.cos(a) * rx * d) * s + sway * 0.8, y + (cy + math.sin(a) * ry * d) * s,
                        r_ * s, 0, TAU)
                ctx.fill()

        def trunk_poly(w0, w1, h, col=None, lean=0.0):
            ctx.set_source_rgb(*(col or trunk))
            ctx.move_to(x - w0 * s, y)
            ctx.line_to(x - w1 * s + lean * s, y + h * s)
            ctx.line_to(x + w1 * s + lean * s, y + h * s)
            ctx.line_to(x + w0 * s, y)
            ctx.close_path()
            ctx.fill()

        def branches(pts, w):
            ctx.set_source_rgb(*trunk)
            ctx.set_line_width(w * s)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            for (ax, ay, bx, by) in pts:
                ctx.move_to(x + ax * s, y + ay * s)
                ctx.line_to(x + bx * s + sway * by / 300, y + by * s)
            ctx.stroke()

        if kind == "neem":                                     # airy, many small dark-green clumps
            trunk_poly(13, 8, 140)
            branches(((0, 120, -60, 190), (0, 130, 55, 200)), 8)
            leaf = sh("#3d7a2a")
            blobs(((-85, 190, 45), (-35, 230, 50), (25, 245, 52), (80, 205, 46), (0, 190, 48), (-60, 250, 38),
                   (60, 260, 36), (110, 175, 30), (-115, 170, 30)), leaf, 0.25)
            dots(lighter(leaf, 0.2), 26, 0, 215, 120, 60, 7)
        elif kind == "peepal":                                 # big, wide, heart-leaf shimmer, thick trunk
            trunk_poly(30, 20, 170, sh("#7a6552"))
            branches(((0, 150, -100, 230), (0, 160, 100, 235), (0, 165, 0, 260)), 14)
            leaf = sh("#4a9a3a")
            blobs(((-140, 230, 70), (-60, 280, 88), (40, 290, 92), (130, 240, 75), (0, 230, 80), (-180, 200, 50),
                   (185, 205, 52)), leaf, 0.18)
            ctx.set_source_rgba(1, 1, 1, 0.18)
            for _ in range(18):
                a, d = rr.uniform(0, TAU), math.sqrt(rr.random())
                px, py = x + math.cos(a) * 170 * d * s + sway, y + (250 + math.sin(a) * 70 * d) * s
                ctx.move_to(px, py)
                ctx.line_to(px - 6 * s, py + 7 * s)
                ctx.line_to(px + 6 * s, py + 7 * s)
                ctx.close_path()
                ctx.fill()
        elif kind in ("gulmohar", "jacaranda", "amaltas"):     # flowering: spread canopy covered in colour
            flower = {"gulmohar": "#e8452c", "jacaranda": "#9b72cf", "amaltas": "#f6c61d"}[kind]
            trunk_poly(14, 8, 130)
            branches(((0, 110, -80, 175), (0, 120, 85, 180)), 9)
            leaf = sh("#4c8f3a")
            blobs(((-110, 180, 50), (-45, 205, 62), (40, 210, 64), (110, 185, 52), (0, 175, 55)), leaf, 0.15)
            fl = sh(flower)
            if kind == "amaltas":                              # hanging yellow chains
                ctx.set_source_rgb(*fl)
                for _ in range(16):
                    hx = x + rr.uniform(-130, 130) * s + sway
                    hy = y + rr.uniform(150, 200) * s
                    for j in range(5):
                        ctx.arc(hx, hy - j * 9 * s, 5 * s, 0, TAU)
                        ctx.fill()
            blobs(((-95, 200, 38), (-30, 230, 44), (50, 228, 44), (105, 200, 36), (5, 195, 40)), fl, 0.12)
            dots(lighter(fl, 0.25), 30, 0, 205, 140, 45, 6)
        elif kind == "bamboo":                                 # a clump of tall thin segmented stalks
            for k in range(7):
                bx = x + (k - 3) * 16 * s + rr.uniform(-4, 4) * s
                h = rr.uniform(300, 420) * s
                col = sh(mix(hex_to_rgb("#7fb241"), hex_to_rgb("#5c8f2e"), rr.random()))
                ctx.set_source_rgb(*col)
                ctx.set_line_width(9 * s)
                lean = (k - 3) * 10 * s + sway * 1.5
                ctx.move_to(bx, y)
                ctx.curve_to(bx, y + h * 0.5, bx + lean * 0.5, y + h * 0.8, bx + lean, y + h)
                ctx.stroke()
                ctx.set_source_rgb(*darker(col, 0.75))
                for j in range(1, 7):
                    u = j / 7.0
                    ctx.rectangle(bx + lean * u * u - 6 * s, y + h * u, 12 * s, 3 * s)
                    ctx.fill()
                ctx.set_source_rgb(*sh("#6fae3c"))
                for j in range(3):
                    lx, ly = bx + lean, y + h - j * 40 * s
                    for d in (-1, 1):
                        ctx.save()
                        ctx.translate(lx, ly)
                        ctx.rotate(d * 0.5)
                        ctx.scale(34 * s, 7 * s)
                        ctx.arc(d * 0.9, 0, 1, 0, TAU)
                        ctx.restore()
                        ctx.fill()
        elif kind == "willow":                                 # drooping curtains of leaves
            trunk_poly(16, 10, 170, sh("#5d4a3a"))
            leaf = sh("#7fb069")
            blobs(((-40, 210, 60), (40, 215, 62), (0, 240, 58)), leaf, 0.2)
            ctx.set_line_width(5 * s)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            for k in range(22):
                fx = x + (-130 + k * 12) * s
                top = y + (230 - abs(k - 11) * 7) * s
                ctx.set_source_rgb(*mix(leaf, (0, 0, 0), 0.1 * (k % 3)))
                ctx.move_to(fx, top)
                sw = sway * 1.6 * math.sin(t * 1.2 + k)
                ctx.curve_to(fx + sw * 0.3, top - 60 * s, fx + sw, top - 110 * s, fx + sw * 1.4, y + 40 * s)
                ctx.stroke()
        elif kind == "birch":                                  # white trunk with black marks, light small canopy
            trunk_poly(9, 6, 240, sh("#f1efe9"))
            ctx.set_source_rgb(*sh("#2b2b2b"))
            for j in range(9):
                ctx.rectangle(x - (9 - j * 0.3) * s, y + (20 + j * 24) * s, rr.uniform(6, 12) * s, 3 * s)
                ctx.fill()
            leaf = sh("#9ccc65")
            blobs(((-40, 250, 40), (30, 265, 42), (0, 295, 40), (-10, 230, 34)), leaf, 0.15)
        elif kind in ("autumn", "oak", "apple"):               # broad round crowns
            trunk_poly(18, 11, 140)
            branches(((0, 120, -70, 180), (0, 125, 75, 185)), 10)
            leaf = sh({"autumn": "#e07a1f", "oak": "#3f7d32", "apple": "#4f9a3f"}[kind])
            blobs(((-90, 190, 62), (0, 235, 80), (90, 195, 62), (-40, 175, 58), (45, 180, 58)), leaf, 0.2)
            if kind == "autumn":
                dots(sh("#c0392b"), 22, 0, 205, 130, 60, 8)
                dots(sh("#f4c430"), 18, 0, 205, 130, 60, 7)
                ctx.set_source_rgb(*sh("#d35400"))              # leaves falling
                for k in range(5):
                    ph = (t * 0.25 + k * 0.2) % 1.0
                    ctx.arc(x + (-90 + k * 45) * s + 25 * math.sin(t * 2 + k), y + (180 - ph * 180) * s, 5 * s, 0, TAU)
                    ctx.fill()
            elif kind == "apple":
                dots(sh("#d62828"), 16, 0, 200, 120, 60, 9)
        elif kind in ("cypress", "ashoka", "eucalyptus"):       # tall and narrow
            if kind == "eucalyptus":
                trunk_poly(10, 6, 330, sh("#d8cfc2"))
                leaf = sh("#7a9e7e")
                blobs(((-30, 320, 34), (25, 345, 36), (0, 375, 32), (-15, 290, 28), (30, 300, 26)), leaf, 0.2)
            else:
                trunk_poly(8, 5, 40)
                leaf = sh("#2d5a27" if kind == "cypress" else "#2f7a32")
                ctx.set_source_rgb(*leaf)
                ctx.save()
                ctx.translate(x + sway * 0.6, y + 200 * s)
                ctx.scale(42 * s if kind == "cypress" else 55 * s, 175 * s)
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.restore()
                ctx.fill()
                if kind == "ashoka":                            # drooping layered leaves
                    ctx.set_source_rgb(*darker(leaf, 0.8))
                    for j in range(7):
                        yy = y + (70 + j * 42) * s
                        wv = (55 - abs(j - 3) * 6) * s
                        ctx.move_to(x - wv + sway * 0.5, yy)
                        ctx.curve_to(x - wv * 0.3, yy - 20 * s, x + wv * 0.3, yy - 20 * s, x + wv + sway * 0.5, yy)
                        ctx.set_line_width(4 * s)
                        ctx.stroke()
        elif kind == "fir":                                    # layered conifer, snow if it is cold
            trunk_poly(9, 9, 40)
            leaf = sh("#1f5e3a")
            snow = self.preset == "snow" or self.weather == "snow" or e.get("snow")
            for k in range(5):
                by, w = y + (30 + k * 52) * s, (110 - k * 20) * s
                ctx.set_source_rgb(*darker(leaf, 0.9 + 0.03 * k))
                ctx.move_to(x - w, by)
                ctx.line_to(x + sway * (k + 1) * 0.25, by + 95 * s)
                ctx.line_to(x + w, by)
                ctx.close_path()
                ctx.fill()
                if snow:
                    ctx.set_source_rgb(*sh("#ffffff"))
                    ctx.rectangle(x - w * 0.9, by - 2 * s, w * 1.8, 7 * s)
                    ctx.fill()
        elif kind == "dead":                                   # twisted, spooky, no leaves
            col = sh("#3b2f2a")
            ctx.set_source_rgb(*col)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)

            def limb(px, py, ang, L, w, depth):
                if depth == 0 or L < 12:
                    return
                ex = px + math.sin(ang) * L * s + sway * 0.2
                ey = py + math.cos(ang) * L * s
                ctx.set_line_width(w * s)
                ctx.move_to(px, py)
                ctx.curve_to(px + math.sin(ang + 0.4) * L * 0.4 * s, py + math.cos(ang + 0.4) * L * 0.4 * s,
                             ex - math.sin(ang - 0.3) * L * 0.3 * s, ey - math.cos(ang - 0.3) * L * 0.3 * s, ex, ey)
                ctx.stroke()
                limb(ex, ey, ang - rr.uniform(0.35, 0.7), L * 0.68, w * 0.62, depth - 1)
                limb(ex, ey, ang + rr.uniform(0.35, 0.7), L * 0.64, w * 0.62, depth - 1)
            limb(x, y, rr.uniform(-0.1, 0.1), 150, 22, 5)
        elif kind == "baobab":                                 # fat bottle trunk, tiny crown
            ctx.set_source_rgb(*sh("#8d7662"))
            ctx.move_to(x - 55 * s, y)
            ctx.curve_to(x - 75 * s, y + 120 * s, x - 40 * s, y + 200 * s, x - 30 * s, y + 230 * s)
            ctx.line_to(x + 30 * s, y + 230 * s)
            ctx.curve_to(x + 40 * s, y + 200 * s, x + 75 * s, y + 120 * s, x + 55 * s, y)
            ctx.close_path()
            ctx.fill()
            branches(((-20, 225, -90, 280), (0, 228, -20, 300), (20, 225, 80, 285), (10, 228, 40, 300)), 11)
            blobs(((-95, 285, 30), (-25, 305, 32), (45, 305, 30), (85, 285, 28)), sh("#6d9a3c"), 0.2)
        else:
            return False
        return True
