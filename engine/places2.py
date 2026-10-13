"""More places: river ghat, bus stand, rooftop terrace, chai stall, mustard field, bamboo forest, haunted graveyard,
library, village road, riverside (with a bridge)."""
import math

import cairo

from .util import darker, seeded, TAU

MORE_PLACES = ("ghat", "bus_stand", "rooftop", "tea_stall", "mustard_field", "bamboo_forest", "graveyard", "library",
               "village_road", "riverside")
MORE_ALIASES = {"river_ghat": "ghat", "ghats": "ghat", "varanasi": "ghat", "banaras": "ghat", "bus_stop": "bus_stand",
                "bus_station": "bus_stand", "bus_adda": "bus_stand", "terrace": "rooftop", "chhat": "rooftop",
                "roof": "rooftop", "chai_stall": "tea_stall", "chai_shop": "tea_stall", "tea_shop": "tea_stall",
                "tapri": "tea_stall", "sarson": "mustard_field", "sarson_field": "mustard_field",
                "yellow_field": "mustard_field", "field": "mustard_field", "bamboo": "bamboo_forest",
                "bamboo_grove": "bamboo_forest", "cemetery": "graveyard", "kabristan": "graveyard",
                "haunted": "graveyard", "spooky": "graveyard", "bhoot": "graveyard", "books": "library",
                "reading_room": "library", "gaon_road": "village_road", "country_road": "village_road",
                "kacchi_sadak": "village_road", "river_bank": "riverside", "riverbank": "riverside",
                "bridge": "riverside"}
MORE_INDOOR = ("library",)


class MorePlacesMixin:
    def _preset_more(self, pr):
        r, W = self.rng, self.world_w
        cols = ["#4f9a3f", "#5fa84a", "#3f8a35"]

        def row(kinds, p=0.7, step=260, sc=(0.6, 0.85), layer="back"):
            for x in range(-500, int(W) + 600, step):
                self._add("tree", x + r.uniform(-60, 60), p=p, layer=layer, kind=r.choice(kinds),
                          scale=r.uniform(*sc), color=r.choice(cols))

        if pr == "ghat":
            self.ground = self.ground or "#c9b79c"
            self.water = self.water or "river"
            self.shore_x, self.land_side = W * 0.62, "left"
            self._add("hills", 0, p=0.25, layer="far", color="#b9c9a0", seed=r.random())
            for x in range(-600, int(W * 0.6), 190):
                self._add("building", x, p=0.55, layer="far", w=r.uniform(120, 170), h=r.uniform(220, 380),
                          color=r.choice(["#e9c46a", "#f4a261", "#e76f51", "#f1e3c8", "#d4a373"]))
            self._add("lm_temple", W * 0.3, p=0.8, layer="back")
            self._add("ghat_steps", 0, p=0.98, layer="back", x2=W * 0.62)
            for x in (W * 0.12, W * 0.42):
                self._add("ghat_umbrella", x, p=0.95, layer="back")
            for k in range(6):
                self._add("diya", W * 0.2 + k * 110, y=-30)
            self._add("bell_post", W * 0.55)
        elif pr == "bus_stand":
            self.ground = self.ground or "#8d8f94"
            for x in range(-700, int(W) + 800, 180):
                self._add("building", x, p=0.5, layer="far", w=r.uniform(110, 160), h=r.uniform(180, 360),
                          color=r.choice(["#e0b98a", "#b8c4cc", "#d99f8a", "#e8cfa0"]))
            row(["neem", "round"], p=0.72, step=520)
            self._add("sidewalk", 0, p=0.95, layer="back")
            self._add("bus_shelter", W * 0.5, p=0.96, layer="back")
            self._add("sign", W * 0.5 + 330, text="BUS")
            self._add("lamp", W * 0.2)
            self._add("lamp", W * 0.8)
            self._add("bench", W * 0.5 - 520)
        elif pr == "rooftop":
            self.ground = self.ground or "#b7aea2"
            for x in range(-900, int(W) + 900, 140):
                self._add("building", x, p=0.35, layer="far", w=r.uniform(100, 150), h=r.uniform(160, 420),
                          color=r.choice(["#c9b8a6", "#b5a894", "#d8c7b0", "#a89f91"]))
            for x in range(-700, int(W) + 700, 230):
                self._add("building", x, p=0.6, layer="far", w=r.uniform(150, 210), h=r.uniform(120, 260),
                          color=r.choice(["#e8d5b7", "#f2e2c4", "#d9c2a0"]))
            self._add("kites", 0, p=0.05, layer="sky", seed=r.random())
            self._add("lm_water_tank", W * 0.82, p=0.93, layer="back")
            self._add("clothesline", W * 0.3, p=0.97, layer="back")
            self._add("parapet", 0, p=0.99, layer="back")
            self._add("plant", W * 0.12)
            self._add("plant", W * 0.6)
        elif pr == "tea_stall":
            self.ground = self.ground or "#b9a88f"
            self._add("hills", 0, p=0.25, layer="far", color="#a5d58a", seed=r.random())
            row(["neem", "peepal", "round"], p=0.7, step=300)
            self._add("chai_stall", W * 0.5, p=0.97, layer="back")
            self._add("bench", W * 0.5 - 430)
            self._add("bench", W * 0.5 + 430)
            self._add("sign", W * 0.5 - 700, text="CHAI")
            self._front_grass()
        elif pr == "mustard_field":
            self.ground = self.ground or "#7dbb4a"
            self._add("hills", 0, p=0.2, layer="far", color="#b6d98d", seed=r.random())
            row(["round", "neem", "mango"], p=0.55, step=420, sc=(0.45, 0.6))
            self._add("mustard", 0, p=0.75, layer="back")
            self._add("mustard", 0, p=0.9, layer="back", dense=True)
            self._add("hut", W * 0.8, p=0.8, layer="back")
            self._add("lm_well", W * 0.18, p=0.95, layer="back")
            self._add("mustard", 0, p=1.0, layer="front", y=-160, front=True)
        elif pr == "bamboo_forest":
            self.ground = self.ground or "#6f9f4a"
            self._add("hills", 0, p=0.2, layer="far", color="#9cc28a", seed=r.random())
            for p, step, sc in ((0.45, 90, (0.5, 0.65)), (0.7, 120, (0.7, 0.9)), (0.9, 260, (1.0, 1.2))):
                for x in range(-500, int(W) + 600, step):
                    self._add("tree", x + r.uniform(-30, 30), p=p, layer="back", kind="bamboo", scale=r.uniform(*sc))
            self._add("fog", 0, p=0.9, layer="front")
            self._front_grass()
        elif pr == "graveyard":
            self.ground = self.ground or "#4f6b45"
            if "time" not in self.spec:
                self.time = "night"
            self.spec.setdefault("moon", "full")
            self._add("hills", 0, p=0.2, layer="far", color="#3d5244", seed=r.random())
            row(["dead", "bare", "dead"], p=0.7, step=340, sc=(0.8, 1.1))
            for k, x in enumerate(range(-200, int(W) + 300, 230)):
                self._add("tombstone", x + r.uniform(-50, 50), p=0.93, layer="back", shape=k % 3,
                          tilt=r.uniform(-8, 8))
            self._add("fence", -600, x2=W + 600, p=0.85, layer="back")
            self._add("fog", 0, p=0.9, layer="front")
        elif pr == "library":
            self.ground = self.ground or "#8b5e3c"
            self._add("wall", 0, color=self.spec.get("wall", "#e9dcc4"))
            self._add("ceiling", 0)
            for x in range(150, int(W), 360):
                self._add("bookshelf", x)
            self._add("window", W * 0.5, y=260)
            for x in range(int(W * 0.25), int(W * 0.8), 700):
                self._add("table", x)
                self._add("lamp_floor", x + 220)
            self._add("clock", W * 0.5 - 300)
            self._add("plant", W - 120)
        elif pr == "village_road":
            self.ground = self.ground or "#c49a6c"
            self._add("mountains", 0, p=0.12, layer="far", color="#9fb3c8", seed=r.random())
            self._add("hills", 0, p=0.3, layer="far", color="#a5d58a", seed=r.random())
            self._add("crops", 0, p=0.6, layer="back")
            row(["neem", "peepal", "mango", "coconut"], p=0.75, step=380, sc=(0.7, 0.95))
            for x in (W * 0.15, W * 0.75):
                self._add("hut", x, p=0.85, layer="back")
            self._add("pole", -300, p=0.9, layer="back", span=620)
            self._add("haystack", W * 0.45, p=0.9, layer="back", scale=0.7)
            self._front_grass()
        elif pr == "riverside":
            self.ground = self.ground or "#7cc15a"
            self._add("mountains", 0, p=0.12, layer="far", color="#9fb3c8", seed=r.random())
            self._add("hills", 0, p=0.3, layer="far", color="#94c77a", seed=r.random())
            self._add("river", 0, p=0.9, layer="back")
            self._add("bridge", W * 0.5, p=0.9, layer="back", y=78)
            row(["willow", "round", "neem"], p=0.82, step=300, sc=(0.5, 0.7))
            for x in range(-400, int(W) + 500, 180):
                if r.random() < 0.5:
                    self._add("reeds", x + r.uniform(-40, 40), layer="front", y=-r.uniform(20, 120))
        return True

    # ================================================================== element drawers
    def _d_ghat_steps(self, ctx, e, t):
        x2 = e.get("x2", self.world_w * 0.6)
        stone = self._shade("#d8c8ad")
        for k in range(6):
            y = -k * 22
            ctx.set_source_rgb(*(stone if k % 2 == 0 else darker(stone, 0.9)))
            ctx.rectangle(-3000, y - 22, x2 + 3000 + k * 40, 22)
            ctx.fill()
            ctx.set_source_rgba(0, 0, 0, 0.12)
            ctx.rectangle(-3000, y - 3, x2 + 3000 + k * 40, 3)
            ctx.fill()

    def _d_ghat_umbrella(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#6b4a2b"))
        ctx.rectangle(x - 4, 0, 8, 220)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#c9a063"))
        ctx.move_to(x - 150, 200)
        ctx.curve_to(x - 80, 250, x + 80, 250, x + 150, 200)
        ctx.line_to(x, 262)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.15)
        for dx in (-100, -50, 0, 50, 100):
            ctx.move_to(x, 262)
            ctx.line_to(x + dx * 1.5, 205)
        ctx.set_line_width(2)
        ctx.stroke()

    def _d_bell_post(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#6b4a2b"))
        ctx.rectangle(x - 5, 0, 10, 190)
        ctx.rectangle(x - 45, 185, 90, 8)
        ctx.fill()
        sw = 6 * math.sin(t * 2.0)
        ctx.set_source_rgb(*self._shade("#d4a017"))
        ctx.move_to(x - 16 + sw, 150)
        ctx.curve_to(x - 14 + sw, 180, x + 14 + sw, 180, x + 16 + sw, 150)
        ctx.close_path()
        ctx.fill()

    def _d_bus_shelter(self, ctx, e, t):
        x = e["x"]
        w = 560
        ctx.set_source_rgb(*self._shade("#5c6770"))
        for dx in (-w / 2 + 10, w / 2 - 10):
            ctx.rectangle(x + dx - 7, 0, 14, 260)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#2a9d8f"))
        ctx.move_to(x - w / 2 - 30, 255)
        ctx.line_to(x + w / 2 + 30, 255)
        ctx.line_to(x + w / 2 + 10, 290)
        ctx.line_to(x - w / 2 - 10, 290)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgba(0.75, 0.88, 0.95, 0.35)
        ctx.rectangle(x - w / 2 + 17, 60, w - 34, 190)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#8d6e63"))
        ctx.rectangle(x - 180, 70, 360, 14)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#f4a261"))
        ctx.rectangle(x - 110, 205, 220, 36)
        ctx.fill()

    def _d_parapet(self, ctx, e, t):
        c = self._shade("#d6cfc4")
        ctx.set_source_rgb(*c)
        ctx.rectangle(-3000, 0, self.world_w + 6000, 95)
        ctx.fill()
        ctx.set_source_rgb(*darker(c, 0.85))
        ctx.rectangle(-3000, 88, self.world_w + 6000, 12)
        ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.08)
        for x in range(-3000, int(self.world_w) + 3000, 160):
            ctx.rectangle(x, 0, 3, 88)
        ctx.fill()

    def _d_clothesline(self, ctx, e, t):
        x = e["x"]
        span = 520
        ctx.set_source_rgb(*self._shade("#6b6b6b"))
        for dx in (-span / 2, span / 2):
            ctx.rectangle(x + dx - 4, 0, 8, 230)
        ctx.fill()
        ctx.set_line_width(2)
        ctx.move_to(x - span / 2, 225)
        ctx.curve_to(x - span / 6, 205, x + span / 6, 205, x + span / 2, 225)
        ctx.stroke()
        cols = ["#e63946", "#f1faee", "#457b9d", "#ffb703", "#8338ec"]
        for k in range(5):
            cx = x - span / 2 + 70 + k * 95
            sw = 5 * math.sin(t * 1.8 + k)
            ctx.set_source_rgb(*self._shade(cols[k]))
            ctx.move_to(cx - 26, 214)
            ctx.line_to(cx + 26, 214)
            ctx.line_to(cx + 22 + sw, 150 + (k % 2) * 20)
            ctx.line_to(cx - 22 + sw, 150 + (k % 2) * 20)
            ctx.close_path()
            ctx.fill()

    def _d_kites(self, ctx, e, t):
        rr = seeded(int(e.get("seed", 0.4) * 1e6))
        for k in range(5):
            kx = rr.uniform(0, self.world_w) + 40 * math.sin(t * 0.5 + k)
            ky = rr.uniform(620, 900) + 25 * math.sin(t * 0.8 + k * 2)
            col = self._shade(rr.choice(["#e63946", "#ffb703", "#8338ec", "#06d6a0", "#118ab2"]))
            ctx.save()
            ctx.translate(kx, ky)
            ctx.rotate(0.2 * math.sin(t + k))
            ctx.set_source_rgb(*col)
            ctx.move_to(0, 26)
            ctx.line_to(20, 0)
            ctx.line_to(0, -26)
            ctx.line_to(-20, 0)
            ctx.close_path()
            ctx.fill()
            ctx.restore()
            ctx.set_source_rgba(0.2, 0.2, 0.2, 0.35)
            ctx.set_line_width(1)
            ctx.move_to(kx, ky - 26)
            ctx.curve_to(kx - 80, ky - 200, kx - 140, ky - 400, kx - 200, 0)
            ctx.stroke()

    def _d_chai_stall(self, ctx, e, t):
        x = e["x"]
        wood = self._shade("#8b5e34")
        ctx.set_source_rgb(*wood)
        for dx in (-230, 230):
            ctx.rectangle(x + dx - 8, 0, 16, 300)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#1d3557"))
        ctx.move_to(x - 290, 290)
        ctx.line_to(x + 290, 290)
        ctx.line_to(x + 250, 340)
        ctx.line_to(x - 250, 340)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#a47148"))
        ctx.rectangle(x - 240, 0, 480, 120)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#f1c40f"))
        ctx.rectangle(x - 150, 235, 300, 44)
        ctx.fill()
        ctx.set_source_rgb(0.3, 0.15, 0.05)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(32)
        ctx.save()
        ctx.translate(x - 60, 245)
        ctx.scale(1, -1)
        ctx.move_to(0, 0)
        ctx.show_text("CHAI")
        ctx.restore()
        ctx.set_source_rgb(*self._shade("#9e9e9e"))               # kettle on a stove
        ctx.arc(x - 90, 150, 30, 0, TAU)
        ctx.fill()
        ctx.rectangle(x - 125, 120, 70, 12)
        ctx.fill()
        for k in range(3):                                          # steam
            sx = x - 90 + 10 * math.sin(t * 2 + k)
            ctx.set_source_rgba(1, 1, 1, 0.35 - k * 0.1)
            ctx.arc(sx, 195 + k * 22 + (t * 20 % 22), 9 + k * 3, 0, TAU)
            ctx.fill()
        ctx.set_source_rgba(0.95, 0.85, 0.6, 0.9)                   # glasses of tea
        for k in range(4):
            ctx.rectangle(x + 30 + k * 40, 120, 20, 30)
            ctx.fill()

    def _d_mustard(self, ctx, e, t):
        W = self.world_w
        rr = seeded(5 if not e.get("dense") else 9)
        y0 = e.get("y", 0)
        ctx.set_source_rgb(*self._shade("#6aa84f"))
        ctx.rectangle(-3000, y0 - (60 if e.get("front") else 0), W + 6000, 60 if not e.get("front") else 120)
        ctx.fill()
        n = 700 if e.get("dense") else 450
        for k in range(n):
            fx = rr.uniform(-2500, W + 2500)
            fy = y0 + rr.uniform(10, 70 if not e.get("front") else 60) - (60 if e.get("front") else 0)
            sw = 4 * math.sin(t * 1.5 + fx * 0.01)
            ctx.set_source_rgb(*self._shade("#5c8f2e"))
            ctx.rectangle(fx, fy - 30, 2, 30)
            ctx.fill()
            ctx.set_source_rgb(*self._shade(rr.choice(["#f7d117", "#f4c20d", "#ffe45c"])))
            ctx.arc(fx + sw, fy, rr.uniform(6, 11), 0, TAU)
            ctx.fill()

    def _d_tombstone(self, ctx, e, t):
        x = e["x"]
        ctx.save()
        ctx.translate(x, 0)
        ctx.rotate(math.radians(e.get("tilt", 0)))
        c = self._shade("#9aa0a6")
        ctx.set_source_rgb(*c)
        shape = e.get("shape", 0)
        if shape == 0:
            ctx.move_to(-40, 0)
            ctx.line_to(-40, 90)
            ctx.arc(0, 90, 40, math.pi, 0)
            ctx.line_to(40, 0)
            ctx.close_path()
            ctx.fill()
        elif shape == 1:
            ctx.rectangle(-10, 0, 20, 150)
            ctx.rectangle(-45, 95, 90, 20)
            ctx.fill()
        else:
            ctx.rectangle(-45, 0, 90, 110)
            ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.18)
        ctx.rectangle(-22, 60, 44, 5)
        ctx.rectangle(-22, 45, 44, 5)
        ctx.fill()
        ctx.restore()
