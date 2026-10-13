"""Style knobs for every place + real water scenes.

background: {
  "preset": "village",
  "season": "spring | summer | monsoon | autumn | winter",
  "region": "north | south | rajasthan | hills | city | western | fairy",
  "density": "sparse | normal | busy",
  "mood": "bright | warm | cool | dull | magical",
  "landmark": "temple | school | well | water_tank | banyan | clock_tower | statue | fountain | windmill | lighthouse",
  "far": "mountains | hills | city | sea | fields | none",
  "seed": 42,                                   # or leave out: every scene gets its own layout
  "water": "sea | river | lake | stormy",       # the ground itself becomes water
  "shore": {"x": 900, "land": "left"}           # part land, part water
}
"""
import math

import cairo

from . import realworld as rw
from .util import hex_to_rgb, mix, darker, lighter, seeded, TAU, clamp

SEASONS = ("spring", "summer", "monsoon", "autumn", "winter")
REGIONS = ("north", "south", "rajasthan", "hills", "city", "western", "fairy")
MOODS = ("bright", "warm", "cool", "dull", "magical")
LANDMARKS = ("temple", "school", "well", "water_tank", "banyan", "clock_tower", "statue", "fountain", "windmill",
             "lighthouse", "big_tree")
WATER_KINDS = ("sea", "river", "lake", "stormy", "pond")

SEASON_LEAF = {
    "spring": ["#6cc24a", "#7ed957", "#f7a8c8"],
    "summer": ["#8fb04a", "#a3b94c", "#7a9e3e"],
    "monsoon": ["#2f8f3a", "#3aa047", "#237a30"],
    "autumn": ["#e07b24", "#d9a032", "#c4562a", "#b8862f"],
    "winter": ["#8aa39a", "#9fb5ab", "#c9d6d0"],
}
SEASON_GROUND = {"spring": "#7ccb5a", "summer": "#b9b86a", "monsoon": "#5a9c3c", "autumn": "#a8a05a",
                 "winter": "#c7d0bd"}
REGION_TREES = {
    "north": ["round", "mango", "banyan", "round"],
    "south": ["coconut", "coconut", "banana_tree", "mango"],
    "rajasthan": ["acacia", "acacia", "cactus_tree"],
    "hills": ["pine", "pine", "round"],
    "city": ["round", "round", "pine"],
    "western": ["round", "blossom", "pine"],
    "fairy": ["blossom", "mushroom_tree", "round"],
}
REGION_HOUSE = {"north": "brick", "south": "tiled", "rajasthan": "mud", "hills": "cottage", "city": "flat",
                "western": "gabled", "fairy": "candy"}
MOOD_TINT = {"warm": (1.0, 0.6, 0.25, 0.10), "cool": (0.3, 0.55, 1.0, 0.10), "dull": (0.5, 0.5, 0.5, 0.22),
             "magical": (0.65, 0.35, 0.95, 0.12), "bright": (1.0, 1.0, 0.9, 0.04)}
WATER_COL = {"sea": ("#2a8bd0", "#0b4f8a"), "river": ("#3f9fc6", "#1d6f8f"), "lake": ("#4aa9d8", "#2474a6"),
             "pond": ("#5aa98a", "#2f7a5e"), "stormy": ("#4f6f7a", "#1f3a45")}
WAVE_AMP = {"lake": 3, "pond": 2, "river": 5, "sea": 9, "stormy": 22}


class StyleMixin:
    # ================================================================== setup
    def _style_init(self):
        sp = self.spec
        self.season = str(sp.get("season", "")).lower() or None
        if self.season not in SEASONS:
            self.season = None
        self.region = str(sp.get("region", "")).lower() or None
        if self.region not in REGIONS:
            self.region = None
        self.density = str(sp.get("density", "normal")).lower()
        self.mood = str(sp.get("mood", "")).lower() or None
        w = sp.get("water")
        if w is True:
            w = "sea"
        self.water = str(w).lower() if w else None
        if self.water and self.water not in WATER_KINDS:
            self.water = "sea"
        if self.water == "stormy" and self.weather == "clear" and "weather" not in sp:
            self.weather = "storm"
        shore = sp.get("shore")
        self.shore_x, self.land_side = None, None
        if isinstance(shore, dict) and self.water:
            self.shore_x = float(shore.get("x", self.world_w * 0.35))
            self.land_side = str(shore.get("land", "left")).lower()
        elif isinstance(shore, (int, float)) and self.water:
            self.shore_x, self.land_side = float(shore), "left"
        if self.season == "monsoon" and self.weather == "clear" and "weather" not in sp:
            self.weather = "rain"
        if self.season == "winter" and "weather" not in sp and self.preset in ("hills", "mountains", "snow"):
            self.weather = "snow"

    def is_water(self, x):
        if not self.water:
            return False
        if self.shore_x is None:
            return True
        return x > self.shore_x if self.land_side == "left" else x < self.shore_x

    def water_y(self):
        return -22.0

    def sea_amp(self):
        return WAVE_AMP.get(self.water, 6) if self.water else 0

    def _apply_style(self):
        r = seeded(int(self.rng.random() * 1e9))
        # --- region: swap tree kinds + house styles
        if self.region:
            kinds = REGION_TREES[self.region]
            for e in self.elements:
                if e["type"] == "tree" and e.get("kind", "round") in ("round", "pine", "palm") and e["p"] >= 0.6:
                    e["kind"] = r.choice(kinds)
                if e["type"] in ("house", "hut"):
                    e["type"] = "house"
                    e["style"] = REGION_HOUSE[self.region]
        # --- season: leaf colours, ground, extras
        if self.season:
            leaves = SEASON_LEAF[self.season]
            for e in self.elements:
                if e["type"] in ("tree", "jungle_tree") and e.get("kind") not in ("coconut", "palm", "cactus_tree"):
                    e["color"] = r.choice(leaves)
                    if self.season == "winter" and r.random() < 0.4 and e.get("kind") in ("round", "mango", None):
                        e["kind"] = "bare"
                    if self.season == "spring" and r.random() < 0.3 and e.get("kind") in ("round", None):
                        e["kind"] = "blossom"
                if e["type"] == "hills":
                    e["color"] = mix(hex_to_rgb(SEASON_GROUND[self.season]), (1, 1, 1), 0.15)
            if not self.indoor and self.preset not in ("space", "desert", "beach") and self.ground in (
                    None, "#7cc15a", "#4f8f3f", "#8cc063"):
                self.ground = SEASON_GROUND[self.season]
            W = self.world_w
            if self.season == "monsoon":
                for x in range(-400, int(W) + 400, 260):
                    if r.random() < 0.5:
                        self._add("puddle", x + r.uniform(-60, 60), layer="front", y=-r.uniform(40, 150),
                                  scale=r.uniform(0.6, 1.3))
            if self.season == "autumn":
                for x in range(-400, int(W) + 400, 70):
                    self._add("leaf_litter", x + r.uniform(-30, 30), layer="front", y=-r.uniform(10, 160),
                              color=r.choice(leaves))
            if self.season == "spring":
                for x in range(-400, int(W) + 400, 120):
                    if r.random() < 0.5:
                        self._add("flower", x + r.uniform(-40, 40), layer="front", y=-r.uniform(30, 150),
                                  color=r.choice(["#ff6b6b", "#ffd166", "#f7a8c8", "#c77dff", "#ffffff"]))
        # --- density
        if self.density in ("sparse", "empty"):
            keep = []
            for e in self.elements:
                if e["type"] in ("tree", "house", "hut", "shop", "building", "grass", "flower", "jungle_tree") and \
                        r.random() < (0.55 if self.density == "sparse" else 0.8):
                    continue
                keep.append(e)
            self.elements = keep
        elif self.density in ("busy", "dense"):
            extra = []
            for e in self.elements:
                if e["type"] in ("tree", "house", "shop", "grass", "flower", "stall") and e["p"] >= 0.6 and r.random() < 0.6:
                    d = dict(e)
                    d["x"] = e["x"] + r.uniform(120, 220)
                    d["scale"] = e.get("scale", 1) * r.uniform(0.8, 1.05)
                    extra.append(d)
            self.elements += extra
        # --- far view override
        far = self.spec.get("far")
        if far:
            self.elements = [e for e in self.elements if not (e["layer"] == "far")]
            fars = far if isinstance(far, (list, tuple)) else [far]      # several: "far": ["mountains", "hills"]
            for far in fars:
                far = str(far).lower().strip().replace(" ", "_")
                if far in ("mountains", "mountain", "snow_mountains", "himalaya"):
                    self._add("mountains", 0, p=0.12, layer="far", color="#8fa7c0", seed=r.random(), big=True)
                elif far in ("rocky_mountains", "low_mountains", "blue_mountains"):
                    self._add("mountains", 0, p=0.16, layer="far", color="#7f95b0", seed=r.random())
                elif far in ("hills", "hill", "green_hills"):
                    self._add("hills", 0, p=0.3, layer="far", color="#9fd07a", seed=r.random())
                elif far in ("dry_hills", "brown_hills"):
                    self._add("hills", 0, p=0.28, layer="far", color="#c9b27a", seed=r.random())
                elif far in ("dunes", "sand_dunes", "desert"):
                    self._add("dunes", 0, p=0.3, layer="far")
                elif far in ("city", "town", "buildings", "skyline"):
                    for x in range(-700, int(self.world_w * 0.6) + 1200, 150):
                        self._add("building", x, p=0.45, layer="far", w=r.uniform(110, 150), h=r.uniform(220, 480),
                                  color=r.choice(["#8d99ae", "#7b8ba3", "#a3b1c6"]))
                elif far in ("sea", "ocean"):
                    self._add("sea", 0, p=0.3, layer="far")
                elif far in ("fields", "farms", "crops"):
                    self._add("crops", 0, p=0.5, layer="far")
                elif far in ("forest", "far_forest", "trees", "jungle"):
                    for x in range(-900, int(self.world_w) + 900, 70):
                        self._add("tree", x + r.uniform(-25, 25), p=0.42, layer="far", y=r.uniform(40, 70),
                                  kind=r.choice(["round", "pine", "round"]), scale=r.uniform(0.35, 0.5),
                                  color=r.choice(["#4f8a45", "#5a9a4c", "#3f7a3a"]))
        # --- landmark in the middle distance
        lm = str(self.spec.get("landmark", "")).lower()
        if lm in LANDMARKS:
            lx = float(self.spec.get("landmark_x", self.world_w * 0.5 + r.uniform(-250, 250)))
            self.elements = [e for e in self.elements if not (e["p"] >= 0.85 and e["layer"] == "mid"
                                                              and abs(e["x"] - lx) < 260 and e["type"] in ("tree", "house", "hut", "shop"))]
            if lm in ("banyan", "big_tree"):
                self._add("tree", lx, p=0.9, layer="back", kind="banyan", scale=1.5)
            else:
                self._add("lm_" + lm, lx, p=0.88, layer="back")
        # --- water: remove land things standing in the water, add sea extras
        if self.water:
            self.elements = [e for e in self.elements
                             if not (e["p"] >= 0.85 and e["layer"] in ("mid", "front", "back")
                                     and self.is_water(e["x"]) and e["type"] not in ("vine", "cloud"))]
            self._add("water_front", 0, layer="front", p=1.0)
            if self.water in ("sea", "stormy"):
                hz = 230 if self.shore_x is None else 120
                self.elements = [e for e in self.elements if e["type"] != "sea"]
                self._add("sea", 0, p=0.3, layer="far", horizon=hz)
                self._add("island", self.world_w * r.uniform(0.2, 0.8), p=0.18, layer="far", y=hz - 20)
                self._add("seagulls", 0, p=0.3, layer="far")
                if r.random() < 0.6:
                    self._add("lm_lighthouse", self.world_w * r.uniform(0.6, 0.9), p=0.25, layer="far", scale=0.6,
                              y=hz - 10)
            if self.shore_x is not None:
                self._add("shore", self.shore_x, p=1.0, layer="back")

    # ================================================================== drawing: water
    def _draw_water_ground(self, ctx, x0, x1, t):
        top, deep = (hex_to_rgb(c) for c in WATER_COL.get(self.water, WATER_COL["sea"]))
        top, deep = self._shade(top), self._shade(deep)
        wy = self.water_y()
        g = cairo.LinearGradient(0, wy + 30, 0, -420)
        g.add_color_stop_rgb(0, *lighter(top, 0.08))
        g.add_color_stop_rgb(1, *deep)
        ctx.set_source(g)
        ctx.rectangle(x0, -3000, x1 - x0, 3000 + wy + 30)
        ctx.fill()
        amp = self.sea_amp()
        flow = 40 if self.water == "river" else 10
        ctx.set_line_width(3)
        for row in range(6):
            y = wy - 25 - row * 34
            ctx.set_source_rgba(1, 1, 1, 0.28 - row * 0.03)
            span = 110 + row * 20
            off = (t * flow * (1 + row * 0.2) + row * 37) % span
            x = x0 - span + off
            while x < x1:
                ph = math.sin(t * 1.3 + x * 0.01 + row)
                ctx.move_to(x, y)
                ctx.curve_to(x + 14, y + 4 + ph * amp * 0.15, x + 28, y + 4, x + 42, y)
                x += span
            ctx.stroke()
        rr = seeded(21)
        for k in range(40):                     # sun glitter
            gx = rr.uniform(x0, x1)
            gy = wy - rr.uniform(10, 200)
            a = 0.5 + 0.5 * math.sin(t * rr.uniform(2, 5) + k)
            ctx.set_source_rgba(1, 1, 0.95, 0.35 * a)
            ctx.rectangle(gx, gy, 10, 2)
            ctx.fill()

    def _d_water_front(self, ctx, e, t):
        """Wave crest band in FRONT of boats and feet (drawn after characters)."""
        if not self.water:
            return
        top = hex_to_rgb(WATER_COL.get(self.water, WATER_COL["sea"])[0])
        top = self._shade(top)
        amp = self.sea_amp()
        wy = self.water_y()
        x0, x1 = -3000.0, self.world_w + 3000.0
        if self.shore_x is not None:
            if self.land_side == "left":
                x0 = self.shore_x + 110
            else:
                x1 = self.shore_x - 110
        speed = 2.4 if self.water == "stormy" else 1.3
        bottom = wy - 40 - amp
        fade = self.shore_x is not None
        if fade:
            ctx.push_group()
        ctx.move_to(x0, bottom)
        x = x0
        while x <= x1:
            y = wy + 8 + amp * (0.6 * math.sin(x * 0.012 + t * speed) + 0.4 * math.sin(x * 0.031 - t * speed * 1.4))
            ctx.line_to(x, y)
            x += 20
        ctx.line_to(x1, bottom)
        ctx.close_path()
        g = cairo.LinearGradient(0, wy + 12, 0, bottom)
        g.add_color_stop_rgba(0, *lighter(top, 0.1), 0.96)
        g.add_color_stop_rgba(1, *top, 1)
        ctx.set_source(g)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.75 if self.water == "stormy" else 0.55)
        ctx.set_line_width(4 if self.water == "stormy" else 2.5)
        x = x0
        first = True
        while x <= x1:
            y = wy + 8 + amp * (0.6 * math.sin(x * 0.012 + t * speed) + 0.4 * math.sin(x * 0.031 - t * speed * 1.4))
            (ctx.move_to if first else ctx.line_to)(x, y)
            first = False
            x += 20
        ctx.stroke()
        if fade:                                   # soft start where the waves meet the beach
            pat = ctx.pop_group()
            edge = x0 if self.land_side == "left" else x1
            inner = edge + (320 if self.land_side == "left" else -320)
            m = cairo.LinearGradient(edge, 0, inner, 0)
            m.add_color_stop_rgba(0, 0, 0, 0, 0)
            m.add_color_stop_rgba(1, 0, 0, 0, 1)
            ctx.set_source(pat)
            ctx.mask(m)

    def _d_shore(self, ctx, e, t):
        x = e["x"]
        sand = self._shade(self.ground) if self.preset in ("beach", "sea", "desert") and self.ground else self._shade("#e6cf97")
        wet = darker(sand, 0.88)
        s = 1 if self.land_side == "left" else -1
        ph = math.sin(t * 1.4)
        for col, off in ((wet, 60 + 18 * ph), (sand, 0)):
            ctx.move_to(x - s * 260, 4)
            ctx.line_to(x + s * (30 + off * 0.4), 4)             # cover the top edge of the water fully
            ctx.curve_to(x + s * (55 + off * 0.6), 4, x + s * (70 + off), -30, x + s * (80 + off), -60)
            ctx.line_to(x + s * (600 + off * 3), -1200)
            ctx.line_to(x - s * 260, -1200)
            ctx.close_path()
            ctx.set_source_rgb(*col)
            ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.7)
        ctx.set_line_width(4)
        ctx.move_to(x + s * (75 + 60 + 18 * ph), -60)
        ctx.line_to(x + s * (600 + (60 + 18 * ph) * 3), -1200)
        ctx.stroke()

    def _d_island(self, ctx, e, t):
        x = e["x"]
        ctx.translate(0, e.get("y", 0))
        ctx.set_source_rgb(*self._shade("#d9c38d"))
        ctx.move_to(x - 180, 20)
        ctx.curve_to(x - 120, 70, x + 120, 70, x + 180, 20)
        ctx.close_path()
        ctx.fill()
        self._d_tree(ctx, dict(x=x - 20, y=55, kind="palm", scale=0.45), t)
        self._d_tree(ctx, dict(x=x + 50, y=50, kind="palm", scale=0.38), t)

    def _d_seagulls(self, ctx, e, t):
        rr = seeded(33)
        ctx.set_source_rgba(0.2, 0.2, 0.25, 0.8)
        ctx.set_line_width(3)
        for k in range(5):
            x = (rr.uniform(0, 2400) + t * rr.uniform(20, 45)) % 2800 - 200
            y = rr.uniform(420, 650) + 12 * math.sin(t * 1.3 + k)
            w = 16 * (0.6 + 0.4 * abs(math.sin(t * 5 + k)))
            ctx.move_to(x - 18, y + w * 0.5)
            ctx.curve_to(x - 10, y + w, x - 4, y + w * 0.4, x, y)
            ctx.curve_to(x + 4, y + w * 0.4, x + 10, y + w, x + 18, y + w * 0.5)
            ctx.stroke()

    # ================================================================== drawing: season extras
    def _d_puddle(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", -60)
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(60 * s, 10 * s)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(*self._shade("#8fb8d8"), 0.8)
        ctx.fill()
        if self.weather == "rain":
            ph = (t * 1.5 + x) % 1
            ctx.save()
            ctx.translate(x + 15 * s, y)
            ctx.scale((6 + 30 * ph) * s, (1 + 5 * ph) * s)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(1, 1, 1, 0.6 * (1 - ph))
            ctx.set_line_width(1.5)
            ctx.stroke()

    def _d_leaf_litter(self, ctx, e, t):
        x, y = e["x"], e.get("y", -60)
        c = e.get("color", "#d9a032")
        c = self._shade(hex_to_rgb(c) if isinstance(c, str) else c)
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(x * 0.37)
        ctx.scale(9, 4)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgb(*c)
        ctx.fill()

    # ================================================================== extra tree kinds
    def _tree_extra(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", 0)
        kind = e.get("kind")
        trunk = self._shade("#6b4a2b")
        c = e.get("color")
        leaf = self._shade(hex_to_rgb(c) if isinstance(c, str) else (c or hex_to_rgb("#3f9142")))
        sway = 3 * rw.sway(t, x, 0.9)                       # the scene wind (engine/realworld.py)
        if kind == "banyan":
            ctx.set_source_rgb(*trunk)
            ctx.rectangle(x - 26 * s, y, 52 * s, 170 * s)
            ctx.fill()
            ctx.set_line_width(4 * s)
            for dx in (-150, -95, -40, 60, 120, 170):
                ctx.move_to(x + dx * s, y + 190 * s)
                ctx.line_to(x + dx * s + sway * 0.3, y)
            ctx.stroke()
            for dx, dy, rr in ((-130, 200, 80), (0, 250, 110), (130, 205, 85), (-60, 230, 90), (70, 235, 95),
                               (-190, 180, 55), (190, 180, 55)):
                ctx.set_source_rgb(*mix(leaf, (0, 0, 0), 0.06 if dx % 2 else 0))
                ctx.arc(x + dx * s + sway, y + dy * s, rr * s, 0, TAU)
                ctx.fill()
        elif kind == "mango":
            ctx.set_source_rgb(*trunk)
            ctx.rectangle(x - 12 * s, y, 24 * s, 120 * s)
            ctx.fill()
            ctx.set_source_rgb(*darker(leaf, 0.85))
            ctx.save()
            ctx.translate(x + sway, y + 190 * s)
            ctx.scale(115 * s, 90 * s)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.fill()
            ctx.set_source_rgba(1, 1, 1, 0.1)
            ctx.arc(x - 40 * s + sway, y + 230 * s, 40 * s, 0, TAU)
            ctx.fill()
        elif kind in ("coconut", "banana_tree"):
            if kind == "coconut":
                self._d_tree(ctx, dict(e, kind="palm", scale=s * 1.15), t)
            else:
                self._d_banana(ctx, dict(e, scale=s * 1.3), t)
        elif kind == "acacia":
            ctx.set_source_rgb(*trunk)
            ctx.set_line_width(12 * s)
            ctx.move_to(x, y)
            ctx.line_to(x + 10 * s, y + 150 * s)
            ctx.move_to(x + 5 * s, y + 90 * s)
            ctx.line_to(x - 50 * s, y + 160 * s)
            ctx.stroke()
            ctx.set_source_rgb(*self._shade(mix(leaf, hex_to_rgb("#8a9a4a"), 0.5)))
            ctx.save()
            ctx.translate(x - 10 * s + sway, y + 175 * s)
            ctx.scale(130 * s, 32 * s)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.fill()
        elif kind == "cactus_tree":
            self._d_cactus(ctx, dict(e, scale=s * 1.2), t)
        elif kind == "bare":
            ctx.set_source_rgb(*self._shade("#6b5a4a"))
            ctx.set_line_width(12 * s)
            ctx.move_to(x, y)
            ctx.line_to(x + sway * 0.3, y + 200 * s)
            ctx.stroke()
            ctx.set_line_width(5 * s)
            for k, (a, L) in enumerate(((-40, 90), (35, 80), (-20, 70), (50, 60), (0, 60))):
                by = y + (100 + k * 22) * s
                ctx.move_to(x, by)
                ctx.line_to(x + math.sin(math.radians(a)) * L * s + sway, by + math.cos(math.radians(a)) * L * s)
            ctx.stroke()
        elif kind == "blossom":
            ctx.set_source_rgb(*trunk)
            ctx.rectangle(x - 12 * s, y, 24 * s, 130 * s)
            ctx.fill()
            for dx, dy, rr in ((-50, 170, 60), (50, 175, 58), (0, 220, 70), (-10, 160, 55)):
                ctx.set_source_rgb(*self._shade("#f7a8c8"))
                ctx.arc(x + dx * s + sway, y + dy * s, rr * s, 0, TAU)
                ctx.fill()
            rr_ = seeded(int(x))
            ctx.set_source_rgb(*self._shade("#ffffff"))
            for k in range(14):
                ctx.arc(x + rr_.uniform(-90, 90) * s + sway, y + rr_.uniform(140, 260) * s, 5 * s, 0, TAU)
                ctx.fill()
        elif kind == "mushroom_tree":
            ctx.set_source_rgb(*self._shade("#f1e3c8"))
            ctx.rectangle(x - 18 * s, y, 36 * s, 150 * s)
            ctx.fill()
            ctx.set_source_rgb(*self._shade("#e63946"))
            ctx.arc(x, y + 150 * s, 100 * s, 0, math.pi)
            ctx.fill()
            ctx.set_source_rgb(1, 1, 1)
            for dx, dy in ((-50, 190), (20, 220), (60, 180)):
                ctx.arc(x + dx * s, y + dy * s, 12 * s, 0, TAU)
                ctx.fill()

    # ================================================================== house styles
    def _house_style(self, ctx, e, t):
        style = e.get("style", "brick")
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", 0)
        base_cols = {"brick": "#c8553d", "tiled": "#f2e8cf", "mud": "#d9a86c", "cottage": "#f4f1de",
                     "flat": "#adb5bd", "gabled": "#90be6d", "candy": "#ffafcc"}
        c = self._shade(e.get("color") if e.get("style_color") else base_cols.get(style, "#e76f51"))
        w, h = 250 * s, 180 * s
        ctx.set_source_rgb(*c)
        if style == "mud":
            ctx.move_to(x - w / 2, y)
            ctx.line_to(x - w / 2, y + h)
            ctx.curve_to(x - w / 4, y + h + 25 * s, x + w / 4, y + h + 25 * s, x + w / 2, y + h)
            ctx.line_to(x + w / 2, y)
            ctx.close_path()
            ctx.fill()
            ctx.set_source_rgb(*self._shade("#8a5a2b"))
            for k in range(6):
                ctx.arc(x - w / 2 + 25 * s + k * 40 * s, y + h - 25 * s, 7 * s, 0, TAU)
                ctx.fill()
        else:
            ctx.rectangle(x - w / 2, y, w, h)
            ctx.fill()
        roof = {"brick": None, "tiled": "#b5462c", "cottage": "#7f4f24", "gabled": "#6d4c41", "candy": "#9b5de5",
                "flat": None, "mud": None}.get(style)
        if roof:
            ctx.set_source_rgb(*self._shade(roof))
            peak = 130 if style in ("cottage", "gabled", "candy") else 80
            ctx.move_to(x - w / 2 - 30 * s, y + h)
            ctx.line_to(x, y + h + peak * s)
            ctx.line_to(x + w / 2 + 30 * s, y + h)
            ctx.close_path()
            ctx.fill()
            if style == "tiled":
                ctx.set_source_rgba(0, 0, 0, 0.18)
                ctx.set_line_width(2)
                for k in range(1, 5):
                    ctx.move_to(x - w / 2 - 30 * s + k * 10 * s, y + h + k * 12 * s)
                    ctx.line_to(x + w / 2 + 30 * s - k * 10 * s, y + h + k * 12 * s)
                ctx.stroke()
        else:
            ctx.set_source_rgb(*darker(c, 0.8))
            ctx.rectangle(x - w / 2 - 8 * s, y + h, w + 16 * s, 14 * s)
            ctx.fill()
            if style == "brick":
                ctx.set_source_rgba(0, 0, 0, 0.12)
                ctx.set_line_width(1.5)
                for k in range(1, 9):
                    ctx.move_to(x - w / 2, y + k * 20 * s)
                    ctx.line_to(x + w / 2, y + k * 20 * s)
                ctx.stroke()
        ctx.set_source_rgb(*self._shade("#5a3825"))
        ctx.rectangle(x - 26 * s, y, 52 * s, 118 * s)        # fits a person at real size
        ctx.fill()
        win = self._shade("#fff3b0") if self.night else self._shade("#bde0fe")
        for dx in (-90, 50):
            ctx.set_source_rgb(*win)
            ctx.rectangle(x + dx * s, y + 88 * s, 40 * s, 40 * s)
            ctx.fill()
            ctx.set_source_rgb(*darker(c, 0.55))
            ctx.set_line_width(4 * s)
            ctx.rectangle(x + dx * s, y + 88 * s, 40 * s, 40 * s)
            ctx.stroke()

    # ================================================================== landmarks
    def _d_lm_temple(self, ctx, e, t):
        x = e["x"]
        stone, dark = self._shade("#f1d9a8"), self._shade("#c9a86a")
        ctx.set_source_rgb(*dark)
        ctx.rectangle(x - 220, 0, 440, 40)
        ctx.fill()
        ctx.set_source_rgb(*stone)
        ctx.rectangle(x - 180, 40, 360, 180)
        ctx.fill()
        ctx.move_to(x - 110, 220)
        ctx.curve_to(x - 100, 360, x - 40, 470, x, 520)
        ctx.curve_to(x + 40, 470, x + 100, 360, x + 110, 220)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.12)
        ctx.set_line_width(3)
        for k in range(1, 7):
            yy = 220 + k * 45
            ww = 110 * (1 - k / 7.5)
            ctx.move_to(x - ww, yy)
            ctx.line_to(x + ww, yy)
        ctx.stroke()
        ctx.set_source_rgb(*self._shade("#5a3825"))
        ctx.move_to(x - 45, 40)
        ctx.line_to(x - 45, 140)
        ctx.curve_to(x - 45, 175, x + 45, 175, x + 45, 140)
        ctx.line_to(x + 45, 40)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#8b5e34"))
        ctx.rectangle(x - 3, 520, 6, 90)
        ctx.fill()
        wave = 8 * math.sin(t * 3)
        ctx.set_source_rgb(*self._shade("#f77f00"))
        ctx.move_to(x + 3, 605)
        ctx.line_to(x + 70, 585 + wave)
        ctx.line_to(x + 3, 565)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#f4a261"))
        for k in range(9):
            ctx.arc(x - 160 + k * 40, 215 + 8 * math.sin(k), 7, 0, TAU)
            ctx.fill()

    def _d_lm_school(self, ctx, e, t):
        x = e["x"]
        wall, trim = self._shade("#f6e7c1"), self._shade("#c1121f")
        ctx.set_source_rgb(*wall)
        ctx.rectangle(x - 330, 0, 660, 330)
        ctx.fill()
        ctx.set_source_rgb(*trim)
        ctx.rectangle(x - 340, 330, 680, 22)
        ctx.rectangle(x - 330, 160, 660, 10)
        ctx.fill()
        win = self._shade("#bde0fe")
        for row in (40, 200):
            for k in range(6):
                if row == 40 and k in (2, 3):
                    continue
                ctx.set_source_rgb(*win)
                ctx.rectangle(x - 300 + k * 104, row, 60, 80)
                ctx.fill()
        ctx.set_source_rgb(*self._shade("#5a3825"))
        ctx.rectangle(x - 60, 0, 120, 130)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#1d3557"))
        ctx.rectangle(x - 150, 365, 300, 60)
        ctx.fill()
        ctx.save()
        ctx.translate(x, 385)
        ctx.scale(1, -1)
        ctx.select_font_face("DejaVu Sans", 0, 1)
        ctx.set_font_size(34)
        txt = str(self.spec.get("school_name", "SCHOOL"))[:14]
        ext = ctx.text_extents(txt)
        ctx.move_to(-ext.width / 2 - ext.x_bearing, -8)
        ctx.set_source_rgb(1, 1, 1)
        ctx.show_text(txt)
        ctx.restore()
        self._flag(ctx, x + 420, t)

    def _flag(self, ctx, x, t, cols=("#ff9933", "#ffffff", "#138808")):
        ctx.set_source_rgb(*self._shade("#8d8d8d"))
        ctx.rectangle(x - 3, 0, 6, 420)
        ctx.fill()
        wnd = rw.wind()                                  # flies downwind; hangs down when the air is still
        d = wnd.direction
        lift = clamp(wnd.strength * (1.0 + wnd.gust(t, x)) / 1.6, 0.15, 1.0)
        fq = 2.5 + 1.5 * min(4.0, wnd.strength)

        def pt(i, y0):
            u = i / 8.0
            reach = 12 * i * (0.35 + 0.65 * lift)
            return x + d * reach, y0 - (1 - lift) * 70 * u + 5 * lift * math.sin(t * fq + i * 0.6)
        for k, c in enumerate(cols):
            ctx.set_source_rgb(*self._shade(c))
            y0 = 400 - k * 26
            ctx.move_to(x, y0)
            for i in range(9):
                ctx.line_to(*pt(i, y0))
            for i in range(8, -1, -1):
                ctx.line_to(*pt(i, y0 - 26))
            ctx.close_path()
            ctx.fill()
        ctx.set_source_rgb(*self._shade("#000080"))
        ctx.set_line_width(2)
        cx_, cy_ = pt(4, 361)                             # the wheel in the middle band
        ctx.arc(cx_, cy_, 8, 0, TAU)
        ctx.stroke()

    def _d_lm_well(self, ctx, e, t):
        self._d_well(ctx, e, t)

    def _d_lm_water_tank(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#9aa0a6"))
        ctx.set_line_width(10)
        for dx in (-70, 70):
            ctx.move_to(x + dx, 0)
            ctx.line_to(x + dx * 0.6, 330)
        ctx.stroke()
        ctx.set_source_rgb(*self._shade("#dfe3e6"))
        ctx.rectangle(x - 100, 330, 200, 130)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#adb5bd"))
        ctx.move_to(x - 110, 460)
        ctx.line_to(x, 510)
        ctx.line_to(x + 110, 460)
        ctx.close_path()
        ctx.fill()

    def _d_lm_clock_tower(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#c9a27e"))
        ctx.rectangle(x - 70, 0, 140, 560)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#8b5e34"))
        ctx.move_to(x - 90, 560)
        ctx.line_to(x, 680)
        ctx.line_to(x + 90, 560)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(1, 1, 1)
        ctx.arc(x, 470, 50, 0, TAU)
        ctx.fill()
        ctx.set_source_rgb(0.1, 0.1, 0.1)
        ctx.set_line_width(5)
        ctx.move_to(x, 470)
        ctx.line_to(x + 35 * math.sin(t * 0.3), 470 + 35 * math.cos(t * 0.3))
        ctx.move_to(x, 470)
        ctx.line_to(x + 22, 470 + 10)
        ctx.stroke()

    def _d_lm_statue(self, ctx, e, t):
        x = e["x"]
        stone = self._shade("#b8b8b0")
        ctx.set_source_rgb(*darker(stone, 0.8))
        ctx.rectangle(x - 70, 0, 140, 120)
        ctx.fill()
        ctx.set_source_rgb(*stone)
        ctx.rectangle(x - 16, 120, 32, 140)
        ctx.fill()
        ctx.arc(x, 290, 30, 0, TAU)
        ctx.fill()
        ctx.set_line_width(16)
        ctx.set_source_rgb(*stone)
        ctx.move_to(x, 240)
        ctx.line_to(x + 60, 300)
        ctx.stroke()

    def _d_lm_fountain(self, ctx, e, t):
        x = e["x"]
        stone = self._shade("#c8c2b4")
        ctx.set_source_rgb(*stone)
        ctx.rectangle(x - 170, 0, 340, 50)
        ctx.rectangle(x - 18, 50, 36, 100)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#79b8e6"))
        ctx.rectangle(x - 160, 40, 320, 10)
        ctx.fill()
        ctx.set_source_rgba(0.6, 0.85, 1, 0.8)
        ctx.set_line_width(4)
        for k in range(6):
            a = -0.9 + k * 0.36
            ph = (t * 1.5 + k * 0.2) % 1
            ctx.move_to(x, 150)
            ctx.curve_to(x + math.sin(a) * 60, 230, x + math.sin(a) * 110, 200, x + math.sin(a) * 140, 60)
            ctx.stroke()

    def _d_lm_windmill(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#e9e4da"))
        ctx.move_to(x - 70, 0)
        ctx.line_to(x - 40, 380)
        ctx.line_to(x + 40, 380)
        ctx.line_to(x + 70, 0)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#6d4c41"))
        a0 = t * 0.9 * self.wind * rw.wind().direction
        for k in range(4):
            a = a0 + k * math.pi / 2
            ctx.save()
            ctx.translate(x, 380)
            ctx.rotate(a)
            ctx.rectangle(10, -14, 190, 28)
            ctx.restore()
            ctx.fill()
        ctx.arc(x, 380, 16, 0, TAU)
        ctx.fill()

    def _d_lm_lighthouse(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        ctx.translate(0, e.get("y", 0))
        for k in range(5):
            ctx.set_source_rgb(*self._shade("#e63946" if k % 2 else "#f8f9fa"))
            y0 = k * 80 * s
            w0, w1 = 70 - k * 8, 70 - (k + 1) * 8
            ctx.move_to(x - w0 * s, y0)
            ctx.line_to(x - w1 * s, y0 + 80 * s)
            ctx.line_to(x + w1 * s, y0 + 80 * s)
            ctx.line_to(x + w0 * s, y0)
            ctx.close_path()
            ctx.fill()
        ctx.set_source_rgb(*self._shade("#fff3b0"))
        ctx.rectangle(x - 30 * s, 400 * s, 60 * s, 45 * s)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#343a40"))
        ctx.move_to(x - 40 * s, 445 * s)
        ctx.line_to(x, 490 * s)
        ctx.line_to(x + 40 * s, 445 * s)
        ctx.close_path()
        ctx.fill()
        if self.night or self.weather in ("storm", "cyclone"):
            a = t * 1.2
            ctx.set_source_rgba(1, 0.95, 0.6, 0.18)
            ctx.move_to(x, 422 * s)
            ctx.line_to(x + math.cos(a) * 900, 422 * s + 60)
            ctx.line_to(x + math.cos(a) * 900, 422 * s - 60)
            ctx.close_path()
            ctx.fill()

    # ================================================================== tint
    def _mood_tint(self, ctx, W, H):
        if self.mood in MOOD_TINT:
            r, g, b, a = MOOD_TINT[self.mood]
            ctx.set_source_rgba(r, g, b, a)
            ctx.paint()
        if self.season == "winter" and not self.indoor:
            gr = cairo.LinearGradient(0, 0, 0, H)
            gr.add_color_stop_rgba(0, 1, 1, 1, 0.0)
            gr.add_color_stop_rgba(0.6, 1, 1, 1, 0.16)
            gr.add_color_stop_rgba(1, 1, 1, 1, 0.08)
            ctx.set_source(gr)
            ctx.paint()
