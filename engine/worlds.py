"""Extra worlds: river, jungle, space / solar system, kitchen, bedroom, road, market, farm,
plus indoor objects (ceiling fan, table fan, TV, fridge, stove...) and the cyclone weather."""
import math

import cairo

from . import realworld as rw
from .util import hex_to_rgb, mix, darker, lighter, seeded, TAU

EXTRA_PRESETS = ("river", "jungle", "space", "kitchen", "bedroom", "road", "market", "farm")
PRESET_ALIASES = {"home": "room", "house": "room", "living_room": "room", "school": "classroom",
                  "city": "street", "town": "street", "solar": "space", "solar_system": "space", "moon": "space",
                  "galaxy": "space", "bazaar": "market", "shop": "market", "highway": "road", "rainforest": "jungle",
                   "village_road": "road", "field": "farm", "garden": "park",
                  "hills": "hill_station", "woods": "forest"}
INDOOR = ("room", "classroom", "kitchen", "bedroom")


class WorldsMixin:
    # ================================================================== presets
    def _preset_extra(self, pr):
        r, W = self.rng, self.world_w
        if pr not in ("space", "kitchen", "bedroom"):
            self._add("sun" if self.time != "night" else "moon", 1480, p=0.02, layer="sky")
            for k in range(7):
                self._add("cloud", r.uniform(-400, 2600), p=0.08, layer="sky", y=r.uniform(560, 820),
                          scale=r.uniform(0.6, 1.2), speed=r.uniform(4, 12))
        if pr == "river":
            self.ground = self.ground or "#7cc15a"
            self._add("mountains", 0, p=0.12, layer="far", color="#9fb3c8", seed=r.random())
            self._add("hills", 0, p=0.3, layer="far", color="#94c77a", seed=r.random())
            self._add("river", 0, p=0.9, layer="back")
            for x in range(-500, int(W) + 700, 150):
                self._add("tree", x + r.uniform(-50, 50), p=0.8, layer="back", y=78, kind=r.choice(["round", "round", "pine"]),
                          scale=r.uniform(0.45, 0.7), color="#5aa048")
            for x in range(-200, int(W) + 300, 900):
                self._add("tree", x + r.uniform(-100, 100), kind="round", scale=r.uniform(1.0, 1.3))
            for x in range(-400, int(W) + 500, 160):
                if r.random() < 0.5:
                    self._add("reeds", x + r.uniform(-40, 40), layer="front", y=-r.uniform(20, 120))
            if self.spec.get("bridge"):
                self._add("bridge", float(self.spec["bridge"]) if not isinstance(self.spec["bridge"], bool) else W / 2,
                          p=0.9, layer="back")
            self._front_grass(flowers=True)
        elif pr == "jungle":
            self.ground = self.ground or "#3f7d34"
            self._add("mountains", 0, p=0.1, layer="far", color="#8fb3a0", seed=r.random())
            for p, sc, step, col in ((0.35, 0.55, 110, "#2f6b45"), (0.55, 0.75, 140, "#2b7a3c"), (0.75, 0.9, 200, "#23702f")):
                for x in range(-800, int(W) + 900, step):
                    self._add("jungle_tree", x + r.uniform(-40, 40), p=p, layer="back", scale=sc * r.uniform(0.85, 1.15),
                              color=col, seed=r.random())
            for x in range(-300, int(W) + 400, 480):
                self._add("jungle_tree", x + r.uniform(-120, 120), scale=r.uniform(1.1, 1.4), color="#1f6a2c",
                          seed=r.random())
                self._add("banana", x + 230 + r.uniform(-60, 60), scale=r.uniform(0.8, 1.2))
            for x in range(-400, int(W) + 500, 210):
                self._add("vine", x + r.uniform(-60, 60), p=1.0, layer="front", length=r.uniform(320, 560))
            for x in range(-500, int(W) + 600, 120):
                if r.random() < 0.6:
                    self._add("fern", x + r.uniform(-40, 40), layer="front", y=-r.uniform(30, 140), scale=r.uniform(0.7, 1.3))
            if self.weather == "clear" and "ambient" not in self.spec:
                pass
        elif pr == "space":
            self.ground = self.ground or "#9b9ea6"
            self.time = "space"
            self.no_air = True                             # (engine/weatherline.py: no weather changes either)
            if self.weather not in ("clear", "", None):     # no air on the Moon: no rain, snow, fog or wind
                self.weather = "clear"
            self._add("nebula", 0, p=0.02, layer="sky")
            if self.spec.get("orbits", True) or self.preset_alias == "solar":
                self._add("solar", 0, p=0.03, layer="sky")
            self._add("planet", 400, p=0.06, layer="sky", y=720, radius=42, color="#d9583b")
            self._add("saturn", 1500, p=0.05, layer="sky", y=640, radius=60)
            self._add("earth", 900, p=0.04, layer="sky", y=560, radius=85)
            for x in range(-300, int(W) + 400, 260):
                self._add("crater", x + r.uniform(-80, 80), layer="front", y=-r.uniform(20, 140), scale=r.uniform(0.5, 1.4))
            for x in range(-300, int(W) + 400, 700):
                self._add("rock", x + r.uniform(0, 300), scale=r.uniform(0.5, 1.0), color="#7d8089")
        elif pr == "kitchen":
            self.ground = self.ground or "#d9d4c7"
            self._add("wall", 0, color=self.spec.get("wall", "#f7e7c6"))
            self._add("ceiling", 0)
            self._add("tiles_wall", 0)
            self._add("counter", W * 0.5 - 120, width=700)
            self._add("stove", W * 0.5 + 60)
            self._add("cabinet", W * 0.5 - 200, width=520)
            self._add("fridge", W * 0.5 + 420)
            self._add("window", W * 0.5 - 900)
            self._add("table", W * 0.5 - 600, scale=1.1)
            self._add("clock", W * 0.5 + 900)
            if self.spec.get("fan", True):
                self._add("fan", W * 0.5 - 500)
        elif pr == "bedroom":
            self.ground = self.ground or "#b07d4f"
            self._add("wall", 0, color=self.spec.get("wall", "#dfe7f2"))
            self._add("ceiling", 0)
            self._add("window", W * 0.5 - 700)
            self._add("bed", W * 0.5 + 250)
            self._add("wardrobe", W * 0.5 + 800)
            self._add("bookshelf", W * 0.5 - 250)
            self._add("lamp_floor", W * 0.5 - 1000)
            self._add("picture", W * 0.5 + 250)
            self._add("rug", W * 0.5, layer="front", y=-60)
            if self.spec.get("fan", True):
                self._add("fan", W * 0.5)
        elif pr == "road":
            self.ground = self.ground or "#5f6369"
            self._add("hills", 0, p=0.3, layer="far", color="#a5d58a", seed=r.random())
            for x in range(-600, int(W) + 800, 180):
                self._add("tree", x + r.uniform(-60, 60), p=0.65, layer="back", kind=r.choice(["round", "pine"]),
                          scale=r.uniform(0.5, 0.75), color="#62a64d")
            for x in range(-400, int(W) + 600, 520):
                self._add("pole", x, p=0.92, layer="back", span=520)
            for x in range(200, int(W), 1400):
                self._add("sign", x, p=0.95, layer="back", text=self.spec.get("sign_text", "SLOW"))
            self._add("verge", 0)
        elif pr == "market":
            self.ground = self.ground or "#b9a88f"
            for x in range(-700, int(W * 0.6) + 1200, 150):
                self._add("building", x, p=0.5, layer="far", w=r.uniform(110, 150), h=r.uniform(200, 380),
                          color=r.choice(["#e0b98a", "#d99f8a", "#c7b299", "#e8cfa0"]))
            cols = ["#e63946", "#2a9d8f", "#f4a261", "#8338ec", "#fb8500", "#219ebc"]
            goods = ["fruit", "veg", "cloth", "pots", "flowers", "sweets"]
            for i, x in enumerate(range(-200, int(W) + 300, 380)):
                self._add("stall", x, color=cols[i % len(cols)], goods=goods[(i * 7) % len(goods)], seed=r.random())
            for x in range(-100, int(W) + 300, 900):
                self._add("lamp", x + 190)
        elif pr == "farm":
            self.ground = self.ground or "#8cc063"
            self._add("hills", 0, p=0.25, layer="far", color="#b6d98d", seed=r.random())
            self._add("crops", 0, p=0.55, layer="back")
            self._add("barn", W * 0.5 + 500, p=0.85, layer="back")
            self._add("haystack", W * 0.5 - 300, p=0.9, layer="back")
            self._add("haystack", W * 0.5 - 520, p=0.9, layer="back", scale=0.7)
            self._add("fence", -600, x2=W + 600, p=0.95, layer="back")
            for x in range(-200, int(W) + 300, 800):
                self._add("tree", x + r.uniform(-100, 100), kind="round", scale=r.uniform(1.0, 1.3))
            self._front_grass(flowers=True)
        return True

    def _extra_setup(self):
        """Called at the end of __init__: weather extras."""
        if self.weather in ("cyclone", "tornado", "hurricane"):
            self.weather = "cyclone"
            self._add("cyclone", float(self.spec.get("cyclone_x", self.world_w * 0.75)), p=0.7, layer="back",
                      speed=float(self.spec.get("cyclone_speed", -40)))
            self.elements.sort(key=lambda e: (e.get("layer") == "front", e["p"]))
        self.wind = {"cyclone": 6.0, "storm": 2.2, "windy": 2.8, "wind": 2.8}.get(self.weather, 1.0)

    # ================================================================== element drawers
    def _d_river(self, ctx, e, t):
        W = self.world_w
        g = cairo.LinearGradient(0, 0, 0, 80)
        g.add_color_stop_rgb(0, *self._shade("#2f7fbf"))
        g.add_color_stop_rgb(1, *self._shade("#5fb0e3"))
        ctx.set_source(g)
        ctx.rectangle(-3000, -10, W + 6000, 92)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.55)
        ctx.set_line_width(3)
        for row in range(4):
            y = 10 + row * 17
            for x in range(-2000, int(W) + 2500, 120):
                xx = x + (t * 35 * (1 + row * 0.3) + row * 40) % 120
                ctx.move_to(xx, y)
                ctx.curve_to(xx + 12, y + 5, xx + 24, y + 5, xx + 36, y)
            ctx.stroke()
        ctx.set_source_rgb(*self._shade("#6aa84f"))
        ctx.rectangle(-3000, 80, W + 6000, 30)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#8a6a45"))
        ctx.rectangle(-3000, 76, W + 6000, 8)
        ctx.fill()
        # a fish jumps now and then
        ph = (t % 7.0) / 7.0
        if ph < 0.12:
            u = ph / 0.12
            fx = (W * 0.3 + int(t / 7.0) * 530) % W
            fy = 10 + 60 * math.sin(math.pi * u)
            ctx.save()
            ctx.translate(fx + u * 80, fy)
            ctx.rotate(0.9 - 1.8 * u)
            ctx.scale(16, 7)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgb(*self._shade("#f4a261"))
            ctx.fill()

    def _d_bridge(self, ctx, e, t):
        x = e["x"]
        wood, dark = self._shade("#9c6b3f"), self._shade("#6b4526")
        ctx.set_source_rgb(*wood)
        ctx.set_line_width(22)
        ctx.arc(x, -280, 420, math.radians(45), math.radians(135))
        ctx.stroke()
        ctx.set_source_rgb(*dark)
        ctx.set_line_width(6)
        for k in range(-5, 6):
            px = x + k * 55
            top = -280 + math.sqrt(max(0, 420 ** 2 - (px - x) ** 2))
            ctx.move_to(px, top)
            ctx.line_to(px, top + 45)
        ctx.stroke()

    def _d_reeds(self, ctx, e, t):
        x, y = e["x"], e.get("y", -40)
        sway = 4 * rw.sway(t, x, 1.3, x)
        ctx.set_source_rgb(*self._shade("#4f7d32"))
        ctx.set_line_width(3)
        for dx in (-6, 0, 6):
            ctx.move_to(x + dx, y)
            ctx.line_to(x + dx * 2 + sway, y + 60)
        ctx.stroke()
        ctx.set_source_rgb(*self._shade("#7a5230"))
        ctx.save()
        ctx.translate(x + sway, y + 62)
        ctx.scale(4, 12)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.fill()

    def _d_jungle_tree(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        rr = seeded(int(e.get("seed", 0.5) * 1e6))
        trunk, leaf = self._shade("#6b4a2b"), self._shade(e.get("color", "#23702f"))
        sway = 4 * rw.sway(t, x, 0.8)
        ctx.set_source_rgb(*trunk)
        ctx.move_to(x - 22 * s, 0)
        ctx.curve_to(x - 14 * s, 200 * s, x - 18 * s, 330 * s, x - 8 * s + sway * 0.5, 430 * s)
        ctx.line_to(x + 8 * s + sway * 0.5, 430 * s)
        ctx.curve_to(x + 16 * s, 300 * s, x + 12 * s, 180 * s, x + 24 * s, 0)
        ctx.close_path()
        ctx.fill()
        for k in range(9):
            a = rr.uniform(0, TAU)
            d = rr.uniform(0, 110)
            cx, cy = x + math.cos(a) * d * s + sway, 440 * s + math.sin(a) * d * 0.55 * s
            ctx.set_source_rgb(*mix(leaf, (0, 0, 0), rr.uniform(0, 0.18)))
            ctx.arc(cx, cy, rr.uniform(50, 80) * s, 0, TAU)
            ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.08)
        ctx.arc(x - 30 * s + sway, 490 * s, 45 * s, 0, TAU)
        ctx.fill()

    def _d_banana(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        sway = 5 * rw.sway(t, x, 1.1, x)
        ctx.set_source_rgb(*self._shade("#5a8f3a"))
        ctx.rectangle(x - 7 * s, 0, 14 * s, 130 * s)
        ctx.fill()
        leaf = self._shade("#4caf50")
        for k, a in enumerate((-2.6, -2.0, -1.2, -0.6, 0.2)):
            ctx.save()
            ctx.translate(x, 130 * s)
            ctx.rotate(a + 0.05 * sway)
            ctx.move_to(0, 0)
            ctx.curve_to(40 * s, 30 * s, 110 * s, 30 * s, 150 * s, 0)
            ctx.curve_to(110 * s, -20 * s, 40 * s, -20 * s, 0, 0)
            ctx.set_source_rgb(*mix(leaf, (0, 0, 0), 0.08 * (k % 2)))
            ctx.fill()
            ctx.restore()

    def _d_vine(self, ctx, e, t):
        x, L = e["x"], e.get("length", 400)
        top = 1000
        sway = 10 * rw.sway(t, x, 0.9, x * 0.01)
        ctx.set_source_rgb(*self._shade("#2f6b2a"))
        ctx.set_line_width(5)
        ctx.move_to(x, top)
        ctx.curve_to(x + sway, top - L * 0.4, x - sway, top - L * 0.7, x + sway * 1.5, top - L)
        ctx.stroke()
        for k in range(6):
            u = (k + 1) / 7
            lx = x + sway * (1.5 * u) * (1 if k % 2 else -0.5)
            ly = top - L * u
            ctx.save()
            ctx.translate(lx, ly)
            ctx.rotate(0.6 if k % 2 else -0.6)
            ctx.scale(14, 7)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgb(*self._shade("#3f8f3a"))
            ctx.fill()

    def _d_fern(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", -50)
        sway = 3 * rw.sway(t, x, 1.4, x)
        ctx.set_source_rgb(*self._shade("#2e7d32"))
        for a in (-1.1, -0.5, 0.0, 0.5, 1.1):
            ctx.save()
            ctx.translate(x, y)
            ctx.rotate(a * 0.9 + 0.03 * sway)
            ctx.move_to(0, 0)
            ctx.curve_to(-10 * s, 30 * s, -6 * s, 60 * s, 0, 75 * s)
            ctx.curve_to(6 * s, 60 * s, 10 * s, 30 * s, 0, 0)
            ctx.fill()
            ctx.restore()

    # ------------------------------------------------------------------ space
    def _d_nebula(self, ctx, e, t):
        for cx, cy, rr, col in ((500, 650, 380, (0.55, 0.25, 0.75)), (1500, 450, 320, (0.2, 0.45, 0.85)),
                                (1100, 800, 260, (0.85, 0.3, 0.55))):
            g = cairo.RadialGradient(cx, cy, 10, cx, cy, rr)
            g.add_color_stop_rgba(0, *col, 0.28)
            g.add_color_stop_rgba(1, *col, 0)
            ctx.set_source(g)
            ctx.arc(cx, cy, rr, 0, TAU)
            ctx.fill()

    def _d_solar(self, ctx, e, t):
        sx, sy = -150, 700
        g = cairo.RadialGradient(sx, sy, 20, sx, sy, 260)
        g.add_color_stop_rgba(0, 1, 0.95, 0.6, 1)
        g.add_color_stop_rgba(0.4, 1, 0.7, 0.2, 0.9)
        g.add_color_stop_rgba(1, 1, 0.5, 0.1, 0)
        ctx.set_source(g)
        ctx.arc(sx, sy, 260, 0, TAU)
        ctx.fill()
        planets = [(260, 7, "#b0a08a", 0.9), (360, 11, "#e6b35a", 0.6), (470, 12, "#3f7fd6", 0.45),
                   (570, 9, "#d9583b", 0.35), (740, 26, "#d9a066", 0.18), (900, 21, "#e3cf8c", 0.13)]
        for rad, pr, col, sp in planets:
            ctx.save()
            ctx.translate(sx, sy)
            ctx.scale(1, 0.32)
            ctx.arc(0, 0, rad, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(1, 1, 1, 0.12)
            ctx.set_line_width(1.5)
            ctx.stroke()
            a = t * sp + rad
            ctx.arc(sx + math.cos(a) * rad, sy + math.sin(a) * rad * 0.32, pr, 0, TAU)
            ctx.set_source_rgb(*hex_to_rgb(col))
            ctx.fill()

    def _planet_disc(self, ctx, x, y, r, col):
        g = cairo.RadialGradient(x - r * 0.35, y + r * 0.35, r * 0.1, x, y, r)
        g.add_color_stop_rgb(0, *lighter(col, 0.3))
        g.add_color_stop_rgb(1, *darker(col, 0.55))
        ctx.set_source(g)
        ctx.arc(x, y, r, 0, TAU)
        ctx.fill()

    def _d_planet(self, ctx, e, t):
        self._planet_disc(ctx, e["x"], e.get("y", 700), e.get("radius", 40), hex_to_rgb(e.get("color", "#d9583b")))

    def _d_earth(self, ctx, e, t):
        x, y, r = e["x"], e.get("y", 560), e.get("radius", 85)
        self._planet_disc(ctx, x, y, r, hex_to_rgb("#2f78c4"))
        ctx.save()
        ctx.arc(x, y, r, 0, TAU)
        ctx.clip()
        ctx.set_source_rgba(0.3, 0.7, 0.3, 0.9)
        off = (t * 6) % (4 * r)
        for dx, dy, rx, ry in ((-0.3, 0.2, 0.35, 0.25), (0.3, -0.25, 0.3, 0.2), (0.6, 0.35, 0.2, 0.15)):
            for rep in (0, -4 * r):
                ctx.save()
                ctx.translate(x - 2 * r + ((dx * r + off + 2 * r) % (4 * r)) + rep, y + dy * r)
                ctx.scale(rx * r, ry * r)
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.restore()
                ctx.fill()
        ctx.restore()
        ctx.arc(x, y, r * 1.06, 0, TAU)
        ctx.set_source_rgba(0.5, 0.8, 1, 0.25)
        ctx.set_line_width(r * 0.1)
        ctx.stroke()

    def _d_saturn(self, ctx, e, t):
        x, y, r = e["x"], e.get("y", 640), e.get("radius", 60)
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(0.35)
        ctx.scale(1, 0.28)
        ctx.arc(0, 0, r * 2.0, math.pi, TAU)
        ctx.restore()
        ctx.set_source_rgba(0.88, 0.8, 0.6, 0.9)
        ctx.set_line_width(10)
        ctx.stroke()
        self._planet_disc(ctx, x, y, r, hex_to_rgb("#e3cf8c"))
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(0.35)
        ctx.scale(1, 0.28)
        ctx.arc(0, 0, r * 2.0, 0, math.pi)
        ctx.restore()
        ctx.set_source_rgba(0.88, 0.8, 0.6, 0.9)
        ctx.stroke()

    def _d_crater(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", -60)
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(50 * s, 12 * s)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(0, 0, 0, 0.18)
        ctx.fill()
        ctx.save()
        ctx.translate(x, y + 3 * s)
        ctx.scale(50 * s, 12 * s)
        ctx.arc(0, 0, 1, math.pi, TAU)
        ctx.restore()
        ctx.set_source_rgba(1, 1, 1, 0.25)
        ctx.set_line_width(3)
        ctx.stroke()

    # ------------------------------------------------------------------ indoor
    def _d_ceiling(self, ctx, e, t):
        ctx.set_source_rgb(*self._shade("#f2efe8"))
        ctx.rectangle(-3000, 660, self.world_w + 6000, 3000)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#cfc8b8"))
        ctx.rectangle(-3000, 650, self.world_w + 6000, 16)
        ctx.fill()

    def _d_tiles_wall(self, ctx, e, t):
        ctx.set_source_rgba(1, 1, 1, 0.45)
        for x in range(-3000, int(self.world_w) + 3000, 60):
            for y in range(100, 230, 60):
                ctx.rectangle(x + 2, y + 2, 56, 56)
        ctx.fill()

    def _d_fan(self, ctx, e, t):
        x = e["x"]
        top = 660
        on = e.get("on", True)
        ang = (t * TAU * 1.1) if on else 0.4
        ctx.set_source_rgb(*self._shade("#8d8d8d"))
        ctx.rectangle(x - 4, top - 80, 8, 80)
        ctx.fill()
        ctx.save()
        ctx.translate(x, top - 95)
        ctx.scale(34, 16)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgb(*self._shade("#6c757d"))
        ctx.fill()
        blades = sorted(((ang + k * TAU / 3) for k in range(3)), key=lambda a: -math.sin(a))
        for a in blades:
            front = math.sin(a) > 0
            length = 170 * math.cos(a)
            col = self._shade("#b08968") if front else darker(self._shade("#b08968"), 0.8)
            ctx.set_source_rgb(*col)
            ctx.move_to(x, top - 98)
            ctx.line_to(x + length, top - 98 - 6 * (1 if front else 0))
            ctx.set_line_width(14 * (0.6 + 0.4 * abs(math.sin(a))))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.stroke()
        if on:
            ctx.set_source_rgba(1, 1, 1, 0.15)
            ctx.save()
            ctx.translate(x, top - 98)
            ctx.scale(175, 10)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.fill()

    def _d_table_fan(self, ctx, e, t):
        x, y = e["x"], e.get("y", 0)
        ctx.set_source_rgb(*self._shade("#495057"))
        ctx.rectangle(x - 40, y, 80, 12)
        ctx.rectangle(x - 5, y, 10, 110)
        ctx.fill()
        cx, cy = x, y + 150
        ctx.arc(cx, cy, 55, 0, TAU)
        ctx.set_source_rgba(*self._shade("#dee2e6"), 0.35)
        ctx.fill()
        a0 = t * TAU * 2.2 if e.get("on", True) else 0
        ctx.set_source_rgba(*self._shade("#4dabf7"), 0.8)
        for k in range(3):
            a = a0 + k * TAU / 3
            ctx.save()
            ctx.translate(cx, cy)
            ctx.rotate(a)
            ctx.scale(48, 16)
            ctx.arc(0.5, 0, 0.5, 0, TAU)
            ctx.restore()
            ctx.fill()
        ctx.arc(cx, cy, 55, 0, TAU)
        ctx.set_source_rgb(*self._shade("#868e96"))
        ctx.set_line_width(4)
        ctx.stroke()

    def _d_tv(self, ctx, e, t):
        x, y = e["x"], e.get("y", 150)
        if y > 60:
            ctx.set_source_rgb(*self._shade("#6f4518"))
            ctx.rectangle(x - 150, 0, 300, y - 34)
            ctx.fill()
            ctx.set_source_rgb(*self._shade("#8b5e34"))
            ctx.rectangle(x - 140, 10, 130, y - 54)
            ctx.rectangle(x + 10, 10, 130, y - 54)
            ctx.fill()
        ctx.set_source_rgb(0.1, 0.1, 0.12)
        ctx.rectangle(x - 120, y, 240, 150)
        ctx.fill()
        ph = int(t * 1.5) % 4
        col = [(0.3, 0.6, 0.9), (0.9, 0.5, 0.3), (0.4, 0.8, 0.5), (0.8, 0.4, 0.8)][ph]
        g = cairo.LinearGradient(x - 110, y + 10, x + 110, y + 140)
        g.add_color_stop_rgb(0, *col)
        g.add_color_stop_rgb(1, *darker(col, 0.5))
        ctx.set_source(g)
        ctx.rectangle(x - 110, y + 10, 220, 130)
        ctx.fill()
        ctx.set_source_rgb(0.2, 0.2, 0.22)
        ctx.rectangle(x - 10, y - 30, 20, 30)
        ctx.rectangle(x - 60, y - 34, 120, 8)
        ctx.fill()

    def _d_fridge(self, ctx, e, t):
        x = e["x"]
        c = self._shade(e.get("color", "#e9ecef"))
        ctx.set_source_rgb(*c)
        ctx.rectangle(x - 90, 0, 180, 400)
        ctx.fill_preserve()
        ctx.set_source_rgb(*darker(c, 0.7))
        ctx.set_line_width(4)
        ctx.stroke()
        ctx.move_to(x - 90, 260)
        ctx.line_to(x + 90, 260)
        ctx.stroke()
        ctx.set_line_width(8)
        ctx.move_to(x + 65, 290)
        ctx.line_to(x + 65, 350)
        ctx.move_to(x + 65, 170)
        ctx.line_to(x + 65, 230)
        ctx.stroke()

    def _d_counter(self, ctx, e, t):
        x, w = e["x"], e.get("width", 600)
        ctx.set_source_rgb(*self._shade("#a47148"))
        ctx.rectangle(x - w / 2, 0, w, 175)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#6c584c"))
        ctx.rectangle(x - w / 2 - 10, 170, w + 20, 16)
        ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.2)
        ctx.set_line_width(3)
        for k in range(1, int(w / 150)):
            ctx.move_to(x - w / 2 + k * 150, 10)
            ctx.line_to(x - w / 2 + k * 150, 160)
        ctx.stroke()

    def _d_stove(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(0.2, 0.2, 0.22)
        ctx.rectangle(x - 90, 186, 180, 14)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#adb5bd"))
        ctx.rectangle(x - 55, 200, 110, 70)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#495057"))
        ctx.rectangle(x - 65, 265, 130, 10)
        ctx.fill()
        for k in range(3):
            ph = (t * 0.5 + k / 3) % 1
            ctx.arc(x - 20 + k * 20 + 10 * math.sin(t * 2 + k), 285 + ph * 90, 10 + 14 * ph, 0, TAU)
            ctx.set_source_rgba(1, 1, 1, 0.35 * (1 - ph))
            ctx.fill()

    def _d_cabinet(self, ctx, e, t):
        x, w = e["x"], e.get("width", 500)
        ctx.set_source_rgb(*self._shade("#bc8a5f"))
        ctx.rectangle(x - w / 2, 420, w, 170)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#8b5e34"))
        ctx.set_line_width(4)
        for k in range(int(w / 125)):
            ctx.rectangle(x - w / 2 + k * 125 + 8, 428, 109, 154)
        ctx.stroke()

    def _d_wardrobe(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#8b5e34"))
        ctx.rectangle(x - 140, 0, 280, 460)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#6f4518"))
        ctx.set_line_width(5)
        ctx.move_to(x, 10)
        ctx.line_to(x, 450)
        ctx.stroke()
        ctx.set_source_rgb(*self._shade("#f2c14e"))
        for dx in (-18, 18):
            ctx.arc(x + dx, 230, 6, 0, TAU)
            ctx.fill()

    def _d_bookshelf(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#7f5539"))
        ctx.rectangle(x - 130, 0, 260, 380)
        ctx.fill()
        rr = seeded(int(x))
        cols = ["#e63946", "#457b9d", "#2a9d8f", "#e9c46a", "#8338ec", "#f4a261"]
        for shelf in range(4):
            y = 20 + shelf * 90
            ctx.set_source_rgb(*self._shade("#5e3a23"))
            ctx.rectangle(x - 120, y - 8, 240, 8)
            ctx.fill()
            bx = x - 115
            while bx < x + 105:
                w = rr.uniform(14, 26)
                h = rr.uniform(55, 78)
                ctx.set_source_rgb(*self._shade(rr.choice(cols)))
                ctx.rectangle(bx, y, w - 2, h)
                ctx.fill()
                bx += w

    def _d_rug(self, ctx, e, t):
        x, y = e["x"], e.get("y", -60)
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(360, 40)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(*self._shade("#c1121f"), 0.8)
        ctx.fill()

    # ------------------------------------------------------------------ road / market / farm
    def _d_verge(self, ctx, e, t):
        ctx.set_source_rgb(*self._shade("#7cb85a"))
        ctx.rectangle(-3000, -14, self.world_w + 6000, 18)
        ctx.fill()

    def _d_pole(self, ctx, e, t):
        x, span = e["x"], e.get("span", 520)
        ctx.set_source_rgb(*self._shade("#7a6a58"))
        ctx.rectangle(x - 6, 0, 12, 380)
        ctx.rectangle(x - 40, 350, 80, 8)
        ctx.fill()
        ctx.set_source_rgba(0.15, 0.15, 0.15, 0.7)
        ctx.set_line_width(2)
        for dx in (-34, 34):
            ctx.move_to(x + dx, 356)
            ctx.curve_to(x + dx + span * 0.3, 310, x + dx + span * 0.7, 310, x + dx + span, 356)
        ctx.stroke()

    def _d_sign(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#6c757d"))
        ctx.rectangle(x - 4, 0, 8, 200)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#f4c430"))
        ctx.move_to(x, 290)
        ctx.line_to(x + 60, 230)
        ctx.line_to(x, 170)
        ctx.line_to(x - 60, 230)
        ctx.close_path()
        ctx.fill()
        txt = str(e.get("text", ""))[:6]
        if txt:
            ctx.save()
            ctx.translate(x, 222)
            ctx.scale(1, -1)
            ctx.select_font_face("DejaVu Sans", 0, 1)
            ctx.set_font_size(20)
            ext = ctx.text_extents(txt)
            ctx.move_to(-ext.width / 2 - ext.x_bearing, 0)
            ctx.set_source_rgb(0.1, 0.1, 0.1)
            ctx.show_text(txt)
            ctx.restore()

    def _d_stall(self, ctx, e, t):
        x = e["x"]
        c = self._shade(e.get("color", "#e63946"))
        wood = self._shade("#8b5e34")
        ctx.set_source_rgb(*wood)
        ctx.rectangle(x - 150, 0, 300, 110)
        ctx.fill()
        ctx.rectangle(x - 150, 0, 10, 300)
        ctx.rectangle(x + 140, 0, 10, 300)
        ctx.fill()
        for k in range(6):
            ctx.set_source_rgb(*(c if k % 2 == 0 else self._shade("#fdfcdc")))
            ctx.move_to(x - 175 + k * 58, 300)
            ctx.line_to(x - 175 + (k + 1) * 58, 300)
            ctx.line_to(x - 175 + (k + 1) * 58, 250)
            ctx.line_to(x - 175 + k * 58 + 29, 235)
            ctx.line_to(x - 175 + k * 58, 250)
            ctx.close_path()
            ctx.fill()
        rr = seeded(int(e.get("seed", 0.3) * 1e6))
        goods = e.get("goods", "fruit")
        palette = {"fruit": ["#e63946", "#f4a261", "#ffd166", "#90be6d"], "veg": ["#43aa8b", "#90be6d", "#f94144", "#f8961e"],
                   "cloth": ["#8338ec", "#ff006e", "#3a86ff", "#ffbe0b"], "pots": ["#b5651d", "#8d5524", "#c68642"],
                   "flowers": ["#ff70a6", "#ff9770", "#ffd670", "#e9ff70"], "sweets": ["#ffd166", "#f4a261", "#ffffff", "#ef476f"]}[goods]
        for row in range(2):
            for k in range(9):
                gx = x - 125 + k * 31 + row * 14
                gy = 118 + row * 22
                ctx.set_source_rgb(*self._shade(rr.choice(palette)))
                if goods in ("cloth",):
                    ctx.rectangle(gx - 12, gy - 8, 26, 18)
                else:
                    ctx.arc(gx, gy, 12, 0, TAU)
                ctx.fill()

    def _d_crops(self, ctx, e, t):
        W = self.world_w
        ctx.set_source_rgb(*self._shade("#c9a86a"))
        ctx.rectangle(-3000, 0, W + 6000, 70)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#5f9e3a"))
        sway = 3 * rw.sway(t, 0.0, 1.0)
        for row in range(3):
            for x in range(-2000, int(W) + 2500, 26):
                y = 8 + row * 22
                ctx.move_to(x + row * 9, y)
                ctx.line_to(x + row * 9 + sway, y + 30)
        ctx.set_line_width(4)
        ctx.stroke()

    def _d_barn(self, ctx, e, t):
        x = e["x"]
        red = self._shade("#b23a48")
        ctx.set_source_rgb(*red)
        ctx.rectangle(x - 200, 0, 400, 260)
        ctx.fill()
        ctx.move_to(x - 230, 250)
        ctx.line_to(x, 420)
        ctx.line_to(x + 230, 250)
        ctx.close_path()
        ctx.set_source_rgb(*darker(red, 0.75))
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#f8f9fa"))
        ctx.set_line_width(8)
        ctx.rectangle(x - 80, 0, 160, 170)
        ctx.move_to(x - 80, 0)
        ctx.line_to(x + 80, 170)
        ctx.move_to(x + 80, 0)
        ctx.line_to(x - 80, 170)
        ctx.stroke()

    def _d_haystack(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#e9c46a"))
        ctx.move_to(x - 110 * s, 0)
        ctx.curve_to(x - 100 * s, 150 * s, x + 100 * s, 150 * s, x + 110 * s, 0)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgba(0.7, 0.55, 0.2, 0.6)
        ctx.set_line_width(2)
        for k in range(-5, 6):
            ctx.move_to(x + k * 16 * s, 5)
            ctx.line_to(x + k * 12 * s, 90 * s)
        ctx.stroke()

    # ------------------------------------------------------------------ weather: cyclone
    def _d_cyclone(self, ctx, e, t):
        W = self.world_w
        x = (e["x"] + e.get("speed", -40) * t) % (W + 800) - 400
        ctx.save()
        for k in range(22):
            u = k / 21
            y = u * 900
            r = 40 + 260 * u ** 1.6
            off = 30 * math.sin(t * 2 + u * 5)
            ctx.save()
            ctx.translate(x + off, y)
            ctx.scale(r, r * 0.22)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(0.42, 0.42, 0.45, 0.16 + 0.1 * (1 - u))
            ctx.fill()
        ctx.set_source_rgba(0.25, 0.25, 0.28, 0.5)
        ctx.set_line_width(4)
        for k in range(10):
            u = (k / 10 + t * 0.3) % 1
            y = u * 850
            r = 40 + 260 * u ** 1.6
            a0 = t * 6 + k
            ctx.save()
            ctx.translate(x + 30 * math.sin(t * 2 + u * 5), y)
            ctx.scale(r, r * 0.22)
            ctx.arc(0, 0, 1, a0, a0 + 2.2)
            ctx.restore()
            ctx.stroke()
        rr = seeded(11)
        for k in range(24):
            u = rr.random()
            a = t * rr.uniform(3, 6) + k
            r = 60 + 280 * u
            px, py = x + math.cos(a) * r, u * 800 + math.sin(a) * r * 0.2
            ctx.set_source_rgba(*rr.choice([(0.45, 0.33, 0.2), (0.35, 0.55, 0.25), (0.5, 0.5, 0.5)]), 0.85)
            ctx.rectangle(px, py, rr.uniform(6, 16), rr.uniform(4, 10))
            ctx.fill()
        ctx.restore()
