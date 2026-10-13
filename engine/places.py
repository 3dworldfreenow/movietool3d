"""New places: school ground, temple fair, cricket ground, railway station, hospital (+ ward), police station,
hill station, desert village, coconut village, wedding, festival street (diwali / holi), palace, castle, cave,
zoo, garden, office, restaurant, open sea, lake."""
import math

import cairo

from .util import hex_to_rgb, mix, darker, lighter, seeded, TAU

PLACE_PRESETS = ("school_ground", "temple_fair", "cricket_ground", "railway_station", "hospital", "hospital_room",
                 "police_station", "hill_station", "desert_village", "coconut_village", "wedding", "festival",
                 "palace", "castle", "cave", "zoo", "garden", "office", "restaurant", "sea", "lake")
PLACE_ALIASES = {"school_field": "school_ground", "playground": "school_ground", "mela": "temple_fair", "fair": "temple_fair",
                 "temple": "temple_fair", "cricket": "cricket_ground", "stadium": "cricket_ground",
                 "station": "railway_station", "railway": "railway_station", "train_station": "railway_station",
                 "clinic": "hospital", "ward": "hospital_room", "police": "police_station", "thana": "police_station",
                 "hills": "hill_station", "shimla": "hill_station", "rajasthan": "desert_village",
                 "kerala": "coconut_village", "backwaters": "coconut_village", "marriage": "wedding",
                 "shaadi": "wedding", "diwali": "festival", "holi": "festival", "fort": "palace", "mahal": "palace",
                 "kingdom": "castle", "cavern": "cave", "office_room": "office", "cafe": "restaurant",
                 "dhaba": "restaurant", "ocean": "sea", "open_sea": "sea", "pond": "lake", "park_garden": "garden"}
PLACE_INDOOR = ("hospital_room", "office", "restaurant", "cave")
from .places2 import MorePlacesMixin, MORE_PLACES, MORE_ALIASES, MORE_INDOOR  # noqa: E402
PLACE_PRESETS = PLACE_PRESETS + MORE_PLACES
PLACE_ALIASES = {**PLACE_ALIASES, **MORE_ALIASES}
PLACE_INDOOR = PLACE_INDOOR + MORE_INDOOR


class PlacesMixin(MorePlacesMixin):
    def _preset_place(self, pr):
        r, W = self.rng, self.world_w
        sky = pr not in PLACE_INDOOR
        if sky:
            self._add("sun" if self.time != "night" else "moon", 1480, p=0.02, layer="sky")
            for k in range(r.randint(3, 8)):
                self._add("cloud", r.uniform(-400, 2600), p=0.08, layer="sky", y=r.uniform(560, 820),
                          scale=r.uniform(0.6, 1.2), speed=r.uniform(4, 12))

        if pr in MORE_PLACES:
            return self._preset_more(pr)

        def trees(p, step, kinds, sc=(0.9, 1.25), layer="back", col=None, y=0):
            for x in range(-500, int(W) + 600, step):
                self._add("tree", x + r.uniform(-60, 60), p=p, layer=layer, kind=r.choice(kinds),
                          scale=r.uniform(*sc), color=col or r.choice(["#4f9a3f", "#5fa84a", "#3f8a35"]), y=y)

        if pr == "school_ground":
            self.ground = self.ground or "#c9a878"
            self._add("hills", 0, p=0.3, layer="far", color="#a5d58a", seed=r.random())
            trees(0.6, 240, ["round", "mango"], (0.5, 0.7))
            self._add("lm_school", W * 0.5, p=0.85, layer="back")
            self._add("swing", W * 0.5 - 700)
            self._add("slide", W * 0.5 + 700)
            self._add("goal", W - 250)
            self._add("fence", -600, x2=W + 600, p=0.8, layer="back")
            self._front_grass()
        elif pr == "temple_fair":
            self.ground = self.ground or "#d2b48c"
            self._add("hills", 0, p=0.3, layer="far", color="#9fd07a", seed=r.random())
            self._add("ferris_wheel", W * 0.2, p=0.6, layer="back")
            self._add("lm_temple", W * 0.62, p=0.82, layer="back")
            cols = ["#e63946", "#f4a261", "#2a9d8f", "#8338ec", "#fb8500"]
            for i, x in enumerate(range(-150, int(W) + 300, 520)):
                self._add("stall", x, color=cols[i % len(cols)], goods=["sweets", "flowers", "pots", "cloth"][i % 4],
                          seed=r.random())
            self._add("string_lights", 0, p=0.95, layer="back", y=420)
            self.spec.setdefault("_crowd_hint", True)
        elif pr == "cricket_ground":
            self.ground = self.ground or "#6fbf4f"
            self._add("stands", 0, p=0.4, layer="far")
            self._add("scoreboard", W * 0.8, p=0.5, layer="far")
            self._add("pitch", W * 0.5, layer="back")
            self._add("stumps", W * 0.5 - 280)
            self._add("stumps", W * 0.5 + 280)
            self._add("boundary", 0, layer="front", y=-150)
        elif pr == "railway_station":
            self.ground = self.ground or "#b9b6ad"
            self._add("hills", 0, p=0.2, layer="far", color="#a9c98b", seed=r.random())
            self._add("track", 0, p=0.8, layer="back")
            self._add("train", 0, p=0.8, layer="back", moving=self.spec.get("train_moving", True))
            self._add("station_building", W * 0.5, p=0.92, layer="back")
            self._add("platform_edge", 0, layer="back")
            for x in (W * 0.25, W * 0.75):
                self._add("bench", x)
            self._add("lamp", W * 0.1)
            self._add("lamp", W * 0.9)
        elif pr == "hospital":
            self.ground = self.ground or "#9ccc7a"
            trees(0.6, 260, ["round"], (0.5, 0.7))
            self._add("hospital_building", W * 0.5, p=0.88, layer="back")
            self._add("ambulance", W * 0.5 + 520, p=0.95, layer="back")
            self._add("sidewalk", 0)
        elif pr == "hospital_room":
            self.ground = self.ground or "#d9e2dc"
            self._add("wall", 0, color=self.spec.get("wall", "#dff3ea"))
            self._add("ceiling", 0)
            self._add("window", W * 0.5 - 700)
            self._add("bed", W * 0.5 + 100, color="#bde0fe")
            self._add("iv_stand", W * 0.5 + 320)
            self._add("curtain", W * 0.5 - 380)
            self._add("med_cabinet", W * 0.5 + 700)
            self._add("clock", W * 0.5 + 100)
        elif pr == "police_station":
            self.ground = self.ground or "#b9b6ad"
            trees(0.6, 300, ["round"], (0.5, 0.7))
            self._add("police_building", W * 0.5, p=0.88, layer="back")
            self._add("police_jeep", W * 0.5 - 600, p=0.95, layer="back")
            self._add("barricade", W * 0.5 + 520)
            self._add("sidewalk", 0)
        elif pr == "hill_station":
            self.ground = self.ground or "#7fb069"
            self._add("mountains", 0, p=0.1, layer="far", color="#9db4cc", seed=r.random(), big=True)
            self._add("mountains", 0, p=0.25, layer="far", color="#7d9a86", seed=r.random())
            self._add("hill_road", 0, p=0.45, layer="far")
            trees(0.6, 110, ["pine"], (0.5, 0.8), col="#2d6a4f")
            for x in range(-200, int(W) + 300, 800):
                self._add("house", x + r.uniform(-80, 80), style="cottage", scale=r.uniform(0.9, 1.1))
                self._add("tree", x + 380, kind="pine", scale=r.uniform(1.1, 1.4), color="#2d6a4f")
            self._add("fog", 0, layer="front", p=1.0)
            self._front_grass(flowers=True)
        elif pr == "desert_village":
            self.ground = self.ground or "#e6c88a"
            self._add("dunes", 0, p=0.3, layer="far")
            self._add("fort", W * 0.35, p=0.2, layer="far")
            for x in range(-200, int(W) + 300, 560):
                self._add("house", x + r.uniform(-60, 60), style="mud", scale=r.uniform(0.85, 1.05))
            trees(0.95, 700, ["acacia"], (0.9, 1.2), layer="mid")
        elif pr == "coconut_village":
            self.ground = self.ground or "#7cc15a"
            self._add("crops", 0, p=0.5, layer="far", color="#6cc24a")
            self._add("river", 0, p=0.9, layer="back")
            for x in range(-500, int(W) + 700, 170):
                self._add("tree", x + r.uniform(-50, 50), p=0.8, layer="back", y=78, kind="palm",
                          scale=r.uniform(0.5, 0.7))
            for x in range(-200, int(W) + 300, 640):
                self._add("house", x, style="tiled", scale=r.uniform(0.9, 1.1))
                self._add("tree", x + 300, kind="palm", scale=r.uniform(1.1, 1.4))
            self._front_grass()
        elif pr == "wedding":
            self.ground = self.ground or "#c9a878"
            if self.time == "day" and "time" not in self.spec:
                self.time = "evening"
            self._add("pandal", W * 0.5, p=0.9, layer="back")
            self._add("string_lights", 0, p=0.95, layer="back", y=480)
            for x in (W * 0.5 - 700, W * 0.5 + 700):
                self._add("table", x, scale=1.1)
            self._add("flower_arch", W * 0.15)
        elif pr == "festival":
            kind = str(self.spec.get("festival", "diwali")).lower()
            self.spec["festival"] = kind
            self.ground = self.ground or "#b9a88f"
            if kind == "diwali" and "time" not in self.spec:
                self.time = "night"
            colors = ["#e76f51", "#f4a261", "#2a9d8f", "#e9c46a", "#b56576"]
            for i, x in enumerate(range(-300, int(W) + 500, 430)):
                self._add("house", x, color=colors[i % len(colors)], scale=r.uniform(0.95, 1.1), y=0,
                          style=r.choice(["brick", "flat"]))
            self._add("string_lights", 0, p=0.97, layer="back", y=380)
            if kind == "diwali":
                for x in range(-200, int(W) + 300, 90):
                    self._add("diya", x + r.uniform(-20, 20), layer="front", y=-r.uniform(20, 60))
                for x in range(-100, int(W) + 300, 430):
                    self._add("lantern", x + 215, p=0.97, layer="back")
                self._add("fireworks", 0, p=0.05, layer="sky")
                self._add("rangoli", W * 0.5, layer="front", y=-100)
            else:
                self._add("holi_colors", 0, layer="front", p=1.0)
        elif pr == "palace":
            self.ground = self.ground or "#d8c8a0"
            self._add("hills", 0, p=0.25, layer="far", color="#b7d18f", seed=r.random())
            self._add("palace_building", W * 0.5, p=0.85, layer="back")
            self._add("lm_fountain", W * 0.5, p=0.95, layer="back")
            for x in range(-200, int(W) + 300, 380):
                self._add("hedge", x)
        elif pr == "castle":
            self.ground = self.ground or "#7fb069"
            self._add("mountains", 0, p=0.12, layer="far", color="#a3b8d0", seed=r.random(), big=True)
            self._add("castle_building", W * 0.5, p=0.75, layer="back")
            trees(0.9, 520, ["round", "pine"], (0.9, 1.2), layer="mid")
            self._front_grass(flowers=True)
        elif pr == "cave":
            self.ground = self.ground or "#5b5048"
            self._add("cave_wall", 0, p=1.0, layer="back")
            self._add("crystals", W * 0.3)
            self._add("crystals", W * 0.75, scale=0.8)
            self._add("torch", W * 0.15)
            self._add("torch", W * 0.85)
            self._add("stalactites", 0, layer="front", p=1.0)
        elif pr == "zoo":
            self.ground = self.ground or "#9ccc7a"
            trees(0.6, 200, ["round", "banyan"], (0.5, 0.75))
            for x in range(-100, int(W) + 300, 700):
                self._add("enclosure", x)
                self._add("sign", x + 300, p=0.97, layer="back", text=r.choice(["LION", "BIRDS", "ZOO", "DEER"]))
            self._add("sidewalk", 0)
        elif pr == "garden":
            self.ground = self.ground or "#7ccb5a"
            self._add("hills", 0, p=0.3, layer="far", color="#a5d58a", seed=r.random())
            trees(0.65, 260, ["round", "blossom"], (0.5, 0.8))
            self._add("lm_fountain", W * 0.5, p=0.92, layer="back")
            for x in range(-200, int(W) + 300, 300):
                self._add("hedge", x)
            self._add("bench", W * 0.5 - 500)
            self._add("bench", W * 0.5 + 500)
            self._add("butterflies", 0, layer="front", p=1.0)
            self._front_grass(flowers=True)
        elif pr == "office":
            self.ground = self.ground or "#9aa5b1"
            self._add("wall", 0, color=self.spec.get("wall", "#e9ecef"))
            self._add("ceiling", 0)
            self._add("city_window", W * 0.5 - 500)
            self._add("city_window", W * 0.5 + 300)
            for x in range(200, int(W), 650):
                self._add("desk_pc", x + r.uniform(-40, 40))
            self._add("water_cooler", W - 180)
            self._add("plant", 120)
            self._add("clock", W * 0.5 - 100)
        elif pr == "restaurant":
            self.ground = self.ground or "#a47148"
            self._add("wall", 0, color=self.spec.get("wall", "#f3d9b1"))
            self._add("ceiling", 0)
            self._add("menu_board", W * 0.5 - 250)
            self._add("counter", W - 350, width=500)
            for x in range(250, int(W) - 500, 450):
                self._add("dining_table", x)
                self._add("hanging_lamp", x)
            self._add("plant", 80)
        elif pr == "sea":
            self.water = self.water or "sea"
            self.ground = self.ground or "#e6cf97"
        elif pr == "lake":
            self.water = self.water or "lake"
            self.ground = self.ground or "#7cc15a"
            self._add("mountains", 0, p=0.12, layer="far", color="#9fb3c8", seed=r.random(), big=True)
            self._add("river", 0, p=0.85, layer="back")
            for x in range(-500, int(W) + 700, 150):
                self._add("tree", x + r.uniform(-50, 50), p=0.78, layer="back", y=78, kind="pine",
                          scale=r.uniform(0.45, 0.65), color="#2d6a4f")
        return True

    # ================================================================== element drawers
    def _d_swing(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#c1121f"))
        ctx.set_line_width(10)
        ctx.move_to(x - 120, 0)
        ctx.line_to(x - 90, 260)
        ctx.line_to(x + 90, 260)
        ctx.line_to(x + 120, 0)
        ctx.stroke()
        a = 0.35 * math.sin(t * 1.6)
        for dx in (-40, 40):
            sx = x + dx + math.sin(a) * 200
            sy = 260 - math.cos(a) * 200
            ctx.set_source_rgb(0.3, 0.3, 0.3)
            ctx.set_line_width(2.5)
            ctx.move_to(x + dx, 260)
            ctx.line_to(sx, sy)
            ctx.stroke()
        sx = x + math.sin(a) * 200
        sy = 260 - math.cos(a) * 200
        ctx.set_source_rgb(*self._shade("#8b5e34"))
        ctx.rectangle(sx - 50, sy - 6, 100, 10)
        ctx.fill()

    def _d_slide(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#1d4e89"))
        ctx.set_line_width(8)
        ctx.move_to(x - 120, 0)
        ctx.line_to(x - 120, 200)
        ctx.move_to(x - 70, 0)
        ctx.line_to(x - 70, 200)
        ctx.stroke()
        ctx.set_source_rgb(*self._shade("#f4c430"))
        ctx.set_line_width(22)
        ctx.move_to(x - 80, 200)
        ctx.curve_to(x, 150, x + 60, 40, x + 150, 10)
        ctx.stroke()

    def _d_goal(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#f8f9fa"))
        ctx.set_line_width(7)
        ctx.move_to(x - 90, 0)
        ctx.line_to(x - 90, 170)
        ctx.line_to(x + 90, 170)
        ctx.line_to(x + 90, 0)
        ctx.stroke()
        ctx.set_source_rgba(1, 1, 1, 0.35)
        ctx.set_line_width(1.5)
        for k in range(1, 9):
            ctx.move_to(x - 90 + k * 20, 0)
            ctx.line_to(x - 90 + k * 20, 170)
        for k in range(1, 8):
            ctx.move_to(x - 90, k * 21)
            ctx.line_to(x + 90, k * 21)
        ctx.stroke()

    def _d_ferris_wheel(self, ctx, e, t):
        x, cy, R = e["x"], 330, 250
        ctx.set_source_rgb(*self._shade("#6c757d"))
        ctx.set_line_width(10)
        ctx.move_to(x - 150, 0)
        ctx.line_to(x, cy)
        ctx.line_to(x + 150, 0)
        ctx.stroke()
        ctx.set_line_width(5)
        ctx.arc(x, cy, R, 0, TAU)
        ctx.stroke()
        a0 = t * 0.25
        cols = ["#e63946", "#f4a261", "#2a9d8f", "#e9c46a", "#8338ec", "#219ebc"]
        for k in range(12):
            a = a0 + k * TAU / 12
            px, py = x + math.cos(a) * R, cy + math.sin(a) * R
            ctx.set_source_rgb(*self._shade("#adb5bd"))
            ctx.set_line_width(2)
            ctx.move_to(x, cy)
            ctx.line_to(px, py)
            ctx.stroke()
            ctx.set_source_rgb(*self._shade(cols[k % len(cols)]))
            ctx.rectangle(px - 18, py - 30, 36, 26)
            ctx.fill()
            if self.night:
                ctx.arc(px, py, 5, 0, TAU)
                ctx.set_source_rgba(1, 0.9, 0.5, 0.9)
                ctx.fill()

    def _d_string_lights(self, ctx, e, t):
        y = e.get("y", 420)
        W = self.world_w
        cols = [(1, 0.3, 0.3), (1, 0.85, 0.3), (0.4, 1, 0.5), (0.4, 0.7, 1), (1, 0.5, 1)]
        for seg in range(-4, int(W / 400) + 5):
            x0, x1 = seg * 400, seg * 400 + 400
            ctx.set_source_rgb(0.2, 0.2, 0.2)
            ctx.set_line_width(2)
            ctx.move_to(x0, y)
            ctx.curve_to(x0 + 130, y - 70, x1 - 130, y - 70, x1, y)
            ctx.stroke()
            for k in range(1, 10):
                u = k / 10
                bx = x0 + 400 * u
                by = y - 70 * 4 * u * (1 - u) * 0.75
                on = self.night or self.time in ("evening", "sunset")
                c = cols[(k + seg) % len(cols)]
                blink = 0.6 + 0.4 * math.sin(t * 4 + k + seg)
                if on and k % 3 == 0:                        # every third bulb lights its surroundings a little
                    from .nightlights import add_device
                    add_device(ctx, bx, by, 60, c, 0.35 * blink, kind="string")
                if on:
                    g = cairo.RadialGradient(bx, by, 1, bx, by, 22)
                    g.add_color_stop_rgba(0, *c, 0.7 * blink)
                    g.add_color_stop_rgba(1, *c, 0)
                    ctx.set_source(g)
                    ctx.arc(bx, by, 22, 0, TAU)
                    ctx.fill()
                ctx.set_source_rgba(*c, 1)
                ctx.arc(bx, by, 5, 0, TAU)
                ctx.fill()

    def _d_stands(self, ctx, e, t):
        W = self.world_w
        ctx.set_source_rgb(*self._shade("#8d99ae"))
        ctx.move_to(-2000, 0)
        ctx.line_to(-2000, 260)
        ctx.line_to(W + 2000, 260)
        ctx.line_to(W + 2000, 0)
        ctx.close_path()
        ctx.fill()
        rr = seeded(5)
        for row in range(6):
            for x in range(-2000, int(W) + 2000, 22):
                ctx.set_source_rgb(*self._shade(rr.choice(["#e63946", "#1d4ed8", "#f4c430", "#ffffff", "#2a9d8f"])))
                ctx.arc(x + (row % 2) * 11, 30 + row * 38 + 3 * math.sin(t * 3 + x), 6, 0, TAU)
                ctx.fill()

    def _d_scoreboard(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(0.1, 0.12, 0.15)
        ctx.rectangle(x - 150, 280, 300, 150)
        ctx.fill()
        ctx.save()
        ctx.translate(x - 120, 380)
        ctx.scale(1, -1)
        ctx.select_font_face("DejaVu Sans Mono", 0, 1)
        ctx.set_font_size(36)
        ctx.set_source_rgb(1, 0.85, 0.2)
        ctx.move_to(0, 0)
        ctx.show_text(str(self.spec.get("score", "142/3")))
        ctx.restore()

    def _d_pitch(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#d9c08f"))
        ctx.rectangle(x - 330, -110, 660, 90)
        ctx.fill()
        ctx.set_source_rgb(1, 1, 1)
        for dx in (-270, 270):
            ctx.rectangle(x + dx - 2, -110, 4, 90)
        ctx.fill()

    def _d_stumps(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#f1e3c8"))
        for dx in (-10, 0, 10):
            ctx.rectangle(x + dx - 2, -60, 4, 80)
        ctx.fill()

    def _d_boundary(self, ctx, e, t):
        ctx.set_source_rgb(*self._shade("#ffffff"))
        ctx.rectangle(-3000, e.get("y", -150), self.world_w + 6000, 6)
        ctx.fill()

    def _d_track(self, ctx, e, t):
        W = self.world_w
        ctx.set_source_rgb(*self._shade("#6c584c"))
        ctx.rectangle(-3000, 20, W + 6000, 30)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#495057"))
        for x in range(-3000, int(W) + 3000, 40):
            ctx.rectangle(x, 22, 18, 8)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#adb5bd"))
        ctx.rectangle(-3000, 42, W + 6000, 5)
        ctx.fill()

    def _d_train(self, ctx, e, t):
        W = self.world_w
        L = 2400
        if e.get("moving", True):
            x0 = (t * 260) % (W + L + 3000) - L - 1500
        else:
            x0 = W * 0.1
        cols = ["#1d4e89", "#1d4e89", "#1d4e89", "#9d0208"]
        for k in range(4):
            cx = x0 + k * 560
            c = self._shade(cols[k])
            ctx.set_source_rgb(*c)
            ctx.rectangle(cx, 50, 540, 200)
            ctx.fill()
            ctx.set_source_rgb(*self._shade("#f4c430"))
            ctx.rectangle(cx, 150, 540, 10)
            ctx.fill()
            for w in range(6):
                ctx.set_source_rgb(*self._shade("#bde0fe") if not self.night else (1, 0.92, 0.6))
                ctx.rectangle(cx + 30 + w * 85, 170, 55, 50)
                ctx.fill()
            for wx in (80, 460):
                ctx.set_source_rgb(0.15, 0.15, 0.17)
                ctx.arc(cx + wx, 50, 28, 0, TAU)
                ctx.fill()

    def _d_platform_edge(self, ctx, e, t):
        ctx.set_source_rgb(*self._shade("#f4c430"))
        ctx.rectangle(-3000, -8, self.world_w + 6000, 10)
        ctx.fill()

    def _d_station_building(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#e9c46a"))
        ctx.rectangle(x - 400, 0, 800, 300)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#9d0208"))
        ctx.rectangle(x - 430, 300, 860, 40)
        ctx.fill()
        for k in range(5):
            ctx.set_source_rgb(*self._shade("#8b5e34"))
            ctx.move_to(x - 330 + k * 160, 0)
            ctx.line_to(x - 330 + k * 160, 170)
            ctx.curve_to(x - 330 + k * 160, 230, x - 230 + k * 160, 230, x - 230 + k * 160, 170)
            ctx.line_to(x - 230 + k * 160, 0)
            ctx.close_path()
            ctx.fill()
        ctx.set_source_rgb(*self._shade("#ffffff"))
        ctx.rectangle(x - 220, 245, 440, 45)
        ctx.fill()
        ctx.save()
        ctx.translate(x, 258)
        ctx.scale(1, -1)
        ctx.select_font_face("DejaVu Sans", 0, 1)
        ctx.set_font_size(30)
        txt = str(self.spec.get("station_name", "RAMPUR JN."))[:18]
        ext = ctx.text_extents(txt)
        ctx.move_to(-ext.width / 2 - ext.x_bearing, -6)
        ctx.set_source_rgb(0.1, 0.1, 0.1)
        ctx.show_text(txt)
        ctx.restore()

    def _d_hospital_building(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#f8f9fa"))
        ctx.rectangle(x - 380, 0, 760, 420)
        ctx.fill()
        win = self._shade("#bde0fe") if not self.night else (1, 0.92, 0.6)
        for row in range(3):
            for k in range(7):
                if row == 0 and k == 3:
                    continue
                ctx.set_source_rgb(*win)
                ctx.rectangle(x - 350 + k * 100, 40 + row * 120, 60, 70)
                ctx.fill()
        ctx.set_source_rgb(*self._shade("#adb5bd"))
        ctx.rectangle(x - 60, 0, 120, 140)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#e63946"))
        ctx.rectangle(x - 20, 440, 40, 110)
        ctx.rectangle(x - 55, 475, 110, 40)
        ctx.fill()

    def _d_ambulance(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#f8f9fa"))
        ctx.rectangle(x - 200, 40, 400, 170)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#e63946"))
        ctx.rectangle(x - 200, 100, 400, 18)
        ctx.rectangle(x - 30, 140, 20, 55)
        ctx.rectangle(x - 47, 157, 54, 20)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#bde0fe"))
        ctx.rectangle(x + 120, 140, 70, 55)
        ctx.fill()
        on = int(t * 4) % 2
        ctx.set_source_rgb(*((1, 0.2, 0.2) if on else (0.3, 0.4, 1)))
        ctx.rectangle(x - 20, 210, 40, 16)
        ctx.fill()
        for wx in (-120, 130):
            ctx.set_source_rgb(0.12, 0.12, 0.14)
            ctx.arc(x + wx, 40, 36, 0, TAU)
            ctx.fill()

    def _d_iv_stand(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#adb5bd"))
        ctx.rectangle(x - 3, 0, 6, 320)
        ctx.rectangle(x - 40, 0, 80, 6)
        ctx.fill()
        ctx.set_source_rgba(0.8, 0.9, 1, 0.8)
        ctx.rectangle(x - 18, 250, 36, 55)
        ctx.fill()

    def _d_curtain(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#9fd8cb"))
        for k in range(8):
            ctx.rectangle(x - 150 + k * 38, 20, 32, 480)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#adb5bd"))
        ctx.rectangle(x - 170, 500, 340, 8)
        ctx.fill()

    def _d_med_cabinet(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#f8f9fa"))
        ctx.rectangle(x - 90, 0, 180, 300)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#e63946"))
        ctx.rectangle(x - 12, 240, 24, 50)
        ctx.rectangle(x - 25, 253, 50, 24)
        ctx.fill()

    def _d_police_building(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#dfe7f2"))
        ctx.rectangle(x - 360, 0, 720, 330)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#1d3557"))
        ctx.rectangle(x - 380, 330, 760, 30)
        ctx.rectangle(x - 200, 280, 400, 45)
        ctx.fill()
        ctx.save()
        ctx.translate(x, 292)
        ctx.scale(1, -1)
        ctx.select_font_face("DejaVu Sans", 0, 1)
        ctx.set_font_size(30)
        ext = ctx.text_extents("POLICE STATION")
        ctx.move_to(-ext.width / 2 - ext.x_bearing, -6)
        ctx.set_source_rgb(1, 1, 1)
        ctx.show_text("POLICE STATION")
        ctx.restore()
        for k in range(6):
            if k in (2, 3):
                continue
            ctx.set_source_rgb(*self._shade("#bde0fe"))
            ctx.rectangle(x - 320 + k * 110, 110, 70, 90)
            ctx.fill()
        ctx.set_source_rgb(*self._shade("#5a3825"))
        ctx.rectangle(x - 70, 0, 140, 160)
        ctx.fill()
        on = int(t * 3) % 2
        ctx.set_source_rgb(*((1, 0.2, 0.2) if on else (0.3, 0.4, 1)))
        ctx.arc(x, 390, 14, 0, TAU)
        ctx.fill()

    def _d_police_jeep(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#f8f9fa"))
        ctx.rectangle(x - 200, 45, 400, 110)
        ctx.rectangle(x - 170, 150, 250, 80)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#1d3557"))
        ctx.rectangle(x - 200, 90, 400, 16)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#bde0fe"))
        ctx.rectangle(x - 150, 162, 100, 55)
        ctx.rectangle(x - 30, 162, 95, 55)
        ctx.fill()
        for wx in (-120, 130):
            ctx.set_source_rgb(0.12, 0.12, 0.14)
            ctx.arc(x + wx, 45, 40, 0, TAU)
            ctx.fill()

    def _d_barricade(self, ctx, e, t):
        x = e["x"]
        for k in range(5):
            ctx.set_source_rgb(*self._shade("#e63946" if k % 2 else "#f8f9fa"))
            ctx.rectangle(x - 120 + k * 48, 60, 48, 36)
            ctx.fill()
        ctx.set_source_rgb(*self._shade("#495057"))
        ctx.rectangle(x - 110, 0, 10, 100)
        ctx.rectangle(x + 100, 0, 10, 100)
        ctx.fill()

    def _d_hill_road(self, ctx, e, t):
        ctx.set_source_rgb(*self._shade("#8d8d8d"))
        ctx.set_line_width(26)
        ctx.move_to(-800, 60)
        ctx.curve_to(400, 260, 900, 20, 1600, 220)
        ctx.curve_to(2000, 330, 2600, 120, 3400, 260)
        ctx.stroke()

    def _d_fog(self, ctx, e, t):
        W = self.world_w
        for k in range(4):
            x = (t * 12 * (k + 1) + k * 700) % (W + 1400) - 700
            g = cairo.RadialGradient(x, 150 + k * 60, 20, x, 150 + k * 60, 520)
            g.add_color_stop_rgba(0, 1, 1, 1, 0.3)
            g.add_color_stop_rgba(1, 1, 1, 1, 0)
            ctx.set_source(g)
            ctx.arc(x, 150 + k * 60, 520, 0, TAU)
            ctx.fill()

    def _d_fort(self, ctx, e, t):
        x = e["x"]
        c = self._shade("#d4a373")
        ctx.set_source_rgb(*darker(c, 0.9))
        ctx.move_to(x - 500, 0)
        ctx.curve_to(x - 300, 140, x + 300, 140, x + 500, 0)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*c)
        ctx.rectangle(x - 280, 110, 560, 150)
        ctx.fill()
        for k in range(8):
            ctx.rectangle(x - 280 + k * 75, 255, 40, 30)
        for dx in (-300, 300):
            ctx.rectangle(x + dx - 40, 110, 80, 230)
        ctx.fill()
        for dx in (-300, 300):
            ctx.arc(x + dx, 340, 45, 0, math.pi)
            ctx.fill()

    def _d_pandal(self, ctx, e, t):
        x = e["x"]
        W = 900
        red, gold = self._shade("#c1121f"), self._shade("#f4a300")
        ctx.set_source_rgb(*darker(red, 0.8))
        for dx in (-W / 2, -W / 6, W / 6, W / 2):
            ctx.rectangle(x + dx - 8, 0, 16, 400)
        ctx.fill()
        ctx.set_source_rgb(*red)
        ctx.move_to(x - W / 2 - 60, 400)
        for k in range(10):
            xx = x - W / 2 - 60 + (k + 1) * (W + 120) / 10
            ctx.curve_to(xx - 40, 360, xx - 20, 360, xx, 400)
        ctx.line_to(x + W / 2 + 60, 470)
        ctx.line_to(x, 560)
        ctx.line_to(x - W / 2 - 60, 470)
        ctx.close_path()
        ctx.fill()
        for k in range(14):
            gx = x - W / 2 + k * W / 13
            for j in range(6):
                ctx.arc(gx + 3 * math.sin(t * 2 + k), 395 - j * 16, 7, 0, TAU)
                ctx.set_source_rgb(*(gold if j % 2 else self._shade("#fb8500")))
                ctx.fill()
        ctx.set_source_rgb(*self._shade("#8b0000"))
        ctx.rectangle(x - 200, 0, 400, 60)
        ctx.fill()
        for dx in (-70, 70):
            ctx.set_source_rgb(*gold)
            ctx.rectangle(x + dx - 40, 60, 80, 130)
            ctx.fill()
            ctx.set_source_rgb(*red)
            ctx.rectangle(x + dx - 32, 70, 64, 80)
            ctx.fill()

    def _d_flower_arch(self, ctx, e, t):
        x = e["x"]
        for k in range(24):
            a = math.pi * k / 23
            ctx.arc(x + math.cos(a) * 170, math.sin(a) * 300, 18, 0, TAU)
            ctx.set_source_rgb(*self._shade(["#fb8500", "#ffb703", "#e63946"][k % 3]))
            ctx.fill()

    def _d_diya(self, ctx, e, t):
        x, y = e["x"], e.get("y", -40)
        ctx.set_source_rgb(*self._shade("#b5651d"))
        ctx.arc(x, y + 6, 12, math.pi, TAU)
        ctx.close_path()
        ctx.fill()
        from .nightlights import add_device, FLAME
        add_device(ctx, x, y + 18, 120, FLAME, 0.6, flame=True, ground=(x, y), kind="diya")
        fl = 1 + 0.2 * math.sin(t * 13 + x)
        g = cairo.RadialGradient(x, y + 16, 1, x, y + 16, 34)
        g.add_color_stop_rgba(0, 1, 0.85, 0.4, 0.8)
        g.add_color_stop_rgba(1, 1, 0.6, 0.2, 0)
        ctx.set_source(g)
        ctx.arc(x, y + 16, 34, 0, TAU)
        ctx.fill()
        ctx.move_to(x - 5, y + 8)
        ctx.curve_to(x - 5, y + 16 * fl, x, y + 24 * fl, x, y + 26 * fl)
        ctx.curve_to(x, y + 24 * fl, x + 5, y + 16 * fl, x + 5, y + 8)
        ctx.close_path()
        ctx.set_source_rgb(1, 0.75, 0.2)
        ctx.fill()

    def _d_lantern(self, ctx, e, t):
        x = e["x"]
        sw = 6 * math.sin(t * 1.5 + x)
        ctx.set_source_rgb(0.2, 0.2, 0.2)
        ctx.set_line_width(2)
        ctx.move_to(x, 560)
        ctx.line_to(x + sw, 470)
        ctx.stroke()
        from .nightlights import add_device, FLAME
        add_device(ctx, x + sw, 440, 220, FLAME, 0.6, flame=True, kind="lantern")
        g = cairo.RadialGradient(x + sw, 440, 5, x + sw, 440, 90)
        g.add_color_stop_rgba(0, 1, 0.7, 0.3, 0.5)
        g.add_color_stop_rgba(1, 1, 0.5, 0.2, 0)
        ctx.set_source(g)
        ctx.arc(x + sw, 440, 90, 0, TAU)
        ctx.fill()
        ctx.set_source_rgb(*hex_to_rgb("#f77f00"))
        ctx.move_to(x + sw, 475)
        ctx.line_to(x + sw + 32, 440)
        ctx.line_to(x + sw, 400)
        ctx.line_to(x + sw - 32, 440)
        ctx.close_path()
        ctx.fill()

    def _d_rangoli(self, ctx, e, t):
        x, y = e["x"], e.get("y", -100)
        cols = ["#e63946", "#ffb703", "#2a9d8f", "#8338ec", "#fb8500"]
        for k, rr in enumerate((90, 70, 50, 30, 12)):
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(1, 0.3)
            for j in range(8):
                a = j * TAU / 8 + k * 0.2
                ctx.arc(math.cos(a) * rr, math.sin(a) * rr, 14 - k * 2, 0, TAU)
            ctx.restore()
            ctx.set_source_rgb(*hex_to_rgb(cols[k]))
            ctx.fill()

    def _d_fireworks(self, ctx, e, t):
        if not self.night:
            return
        rr = seeded(44)
        for k in range(5):
            period = rr.uniform(2.5, 4.0)
            ph = ((t + k * 0.9) % period) / period
            if ph > 0.55:
                continue
            u = ph / 0.55
            cx, cy = rr.uniform(300, 1700), rr.uniform(520, 820)
            col = rr.choice([(1, 0.3, 0.3), (1, 0.85, 0.3), (0.4, 1, 0.5), (0.5, 0.7, 1), (1, 0.5, 1)])
            for j in range(22):
                a = j * TAU / 22
                d = 150 * u
                ctx.arc(cx + math.cos(a) * d, cy + math.sin(a) * d - 40 * u * u, 4 * (1 - u) + 1, 0, TAU)
                ctx.set_source_rgba(*col, 1 - u)
                ctx.fill()

    def _d_holi_colors(self, ctx, e, t):
        rr = seeded(55)
        cols = [(1, 0.2, 0.55), (1, 0.85, 0.1), (0.2, 0.8, 0.3), (0.2, 0.5, 1), (1, 0.5, 0.1)]
        for k in range(26):
            ph = (t * rr.uniform(0.15, 0.3) + rr.random()) % 1
            x = rr.uniform(-200, self.world_w + 200)
            y = 60 + ph * 500
            ctx.arc(x + 30 * math.sin(t + k), y, 40 + 90 * ph, 0, TAU)
            ctx.set_source_rgba(*cols[k % len(cols)], 0.28 * (1 - ph))
            ctx.fill()

    def _d_palace_building(self, ctx, e, t):
        x = e["x"]
        c = self._shade("#f4e4c1")
        d = self._shade("#d9b77a")
        ctx.set_source_rgb(*c)
        ctx.rectangle(x - 520, 0, 1040, 360)
        ctx.fill()
        for k in range(7):
            ax = x - 450 + k * 150
            ctx.set_source_rgb(*d)
            ctx.move_to(ax - 45, 0)
            ctx.line_to(ax - 45, 170)
            ctx.curve_to(ax - 45, 240, ax + 45, 240, ax + 45, 170)
            ctx.line_to(ax + 45, 0)
            ctx.close_path()
            ctx.fill()
        for dx, rr in ((0, 150), (-380, 80), (380, 80)):
            ctx.set_source_rgb(*c)
            ctx.arc(x + dx, 360, rr, 0, math.pi)
            ctx.fill()
            ctx.set_source_rgb(*d)
            ctx.rectangle(x + dx - 4, 360 + rr, 8, 50)
            ctx.fill()
        for dx in (-540, 540):
            ctx.set_source_rgb(*c)
            ctx.rectangle(x + dx - 30, 0, 60, 480)
            ctx.fill()
            ctx.arc(x + dx, 480, 38, 0, math.pi)
            ctx.fill()

    def _d_castle_building(self, ctx, e, t):
        x = e["x"]
        stone = self._shade("#a8a29e")
        dark = darker(stone, 0.8)
        ctx.set_source_rgb(*stone)
        ctx.rectangle(x - 350, 0, 700, 300)
        ctx.fill()
        for k in range(10):
            ctx.rectangle(x - 350 + k * 72, 300, 40, 36)
        ctx.fill()
        for dx in (-380, 380, 0):
            h = 520 if dx == 0 else 440
            ctx.set_source_rgb(*stone)
            ctx.rectangle(x + dx - 70, 0, 140, h)
            ctx.fill()
            ctx.set_source_rgb(*self._shade("#5c4d7d"))
            ctx.move_to(x + dx - 85, h)
            ctx.line_to(x + dx, h + 160)
            ctx.line_to(x + dx + 85, h)
            ctx.close_path()
            ctx.fill()
            ctx.set_source_rgb(*self._shade("#e63946"))
            wv = 6 * math.sin(t * 3 + dx)
            ctx.move_to(x + dx, h + 190)
            ctx.line_to(x + dx + 50, h + 175 + wv)
            ctx.line_to(x + dx, h + 160)
            ctx.close_path()
            ctx.fill()
        ctx.set_source_rgb(*dark)
        ctx.move_to(x - 70, 0)
        ctx.line_to(x - 70, 120)
        ctx.curve_to(x - 70, 190, x + 70, 190, x + 70, 120)
        ctx.line_to(x + 70, 0)
        ctx.close_path()
        ctx.fill()

    def _d_hedge(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#3a7d44"))
        ctx.rectangle(x - 110, 0, 220, 80)
        ctx.fill()
        ctx.arc(x - 60, 80, 50, math.pi, TAU)
        ctx.arc(x + 60, 80, 50, math.pi, TAU)
        ctx.fill()

    def _d_cave_wall(self, ctx, e, t):
        W = self.world_w
        rr = seeded(8)
        ctx.set_source_rgb(*self._shade("#3d3530"))
        ctx.rectangle(-3000, 0, W + 6000, 3000)
        ctx.fill()
        for k in range(40):
            x, y = rr.uniform(-500, W + 500), rr.uniform(20, 700)
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(rr.uniform(60, 160), rr.uniform(30, 80))
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(*self._shade(rr.choice(["#4a403a", "#342c28", "#51463f"])), 1)
            ctx.fill()

    def _d_stalactites(self, ctx, e, t):
        rr = seeded(9)
        ctx.set_source_rgb(*self._shade("#2b2420"))
        ctx.rectangle(-3000, 900, self.world_w + 6000, 2000)
        ctx.fill()
        for k in range(50):
            x = rr.uniform(-500, self.world_w + 500)
            L = rr.uniform(60, 240)
            w = rr.uniform(20, 55)
            ctx.move_to(x - w, 905)
            ctx.line_to(x, 905 - L)
            ctx.line_to(x + w, 905)
            ctx.close_path()
            ctx.fill()

    def _d_crystals(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        glow = 0.5 + 0.3 * math.sin(t * 2 + x)
        g = cairo.RadialGradient(x, 60 * s, 5, x, 60 * s, 200 * s)
        g.add_color_stop_rgba(0, 0.5, 0.9, 1, 0.45 * glow)
        g.add_color_stop_rgba(1, 0.5, 0.9, 1, 0)
        ctx.set_source(g)
        ctx.arc(x, 60 * s, 200 * s, 0, TAU)
        ctx.fill()
        for k, (dx, h, a) in enumerate(((-40, 120, -0.3), (0, 170, 0), (40, 110, 0.35), (-70, 70, -0.6), (75, 80, 0.6))):
            ctx.save()
            ctx.translate(x + dx * s, 0)
            ctx.rotate(-a)
            ctx.move_to(-14 * s, 0)
            ctx.line_to(-14 * s, h * s * 0.8)
            ctx.line_to(0, h * s)
            ctx.line_to(14 * s, h * s * 0.8)
            ctx.line_to(14 * s, 0)
            ctx.close_path()
            ctx.restore()
            ctx.set_source_rgba(0.55, 0.85, 1, 0.9)
            ctx.fill()

    def _d_torch(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#6b4a2b"))
        ctx.rectangle(x - 6, 200, 12, 90)
        ctx.fill()
        g = cairo.RadialGradient(x, 320, 5, x, 320, 260)
        g.add_color_stop_rgba(0, 1, 0.7, 0.3, 0.45)
        g.add_color_stop_rgba(1, 1, 0.5, 0.2, 0)
        ctx.set_source(g)
        ctx.arc(x, 320, 260, 0, TAU)
        ctx.fill()
        for k in range(3):
            fl = 1 + 0.25 * math.sin(t * 11 + k * 2)
            ctx.move_to(x - 16 + k * 4, 290)
            ctx.curve_to(x - 20, 320 * 1, x - 5, 340 * fl, x, 350 * fl)
            ctx.curve_to(x + 5, 340 * fl, x + 20, 320, x + 16 - k * 4, 290)
            ctx.close_path()
            ctx.set_source_rgb(*[(1, 0.4, 0.1), (1, 0.7, 0.2), (1, 0.95, 0.6)][k])
            ctx.fill()

    def _d_enclosure(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#495057"))
        for k in range(13):
            ctx.rectangle(x - 300 + k * 50, 0, 6, 260)
        ctx.rectangle(x - 300, 250, 606, 10)
        ctx.rectangle(x - 300, 120, 606, 6)
        ctx.fill()

    def _d_butterflies(self, ctx, e, t):
        rr = seeded(66)
        for k in range(6):
            bx = (rr.uniform(0, self.world_w) + 40 * math.sin(t * 0.7 + k) + t * 15) % self.world_w
            by = rr.uniform(40, 260) + 30 * math.sin(t * 1.3 + k)
            flap = abs(math.sin(t * 12 + k))
            col = rr.choice([(1, 0.6, 0.1), (0.9, 0.3, 0.6), (0.3, 0.6, 1)])
            for sgn in (-1, 1):
                ctx.save()
                ctx.translate(bx + sgn * 6 * flap, by)
                ctx.scale(8 * flap + 2, 10)
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.restore()
                ctx.set_source_rgb(*col)
                ctx.fill()

    def _d_city_window(self, ctx, e, t):
        x, y, w, h = e["x"], 190, 320, 260
        ctx.set_source_rgb(*self._shade("#a9d6f5"))
        ctx.rectangle(x, y, w, h)
        ctx.fill()
        rr = seeded(int(x))
        for k in range(8):
            bw, bh = rr.uniform(25, 45), rr.uniform(60, 200)
            ctx.set_source_rgb(*self._shade(rr.choice(["#8d99ae", "#6c7a93", "#a3b1c6"])))
            ctx.rectangle(x + k * 40, y, bw, bh)
            ctx.fill()
        ctx.set_source_rgb(*self._shade("#ffffff"))
        ctx.set_line_width(10)
        ctx.rectangle(x, y, w, h)
        ctx.stroke()

    def _d_desk_pc(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#8b5e34"))
        ctx.rectangle(x - 130, 100, 260, 14)
        ctx.rectangle(x - 120, 0, 12, 100)
        ctx.rectangle(x + 108, 0, 12, 100)
        ctx.fill()
        ctx.set_source_rgb(0.12, 0.12, 0.14)
        ctx.rectangle(x - 55, 150, 110, 75)
        ctx.fill()
        ph = (t * 0.5 + x) % 1
        ctx.set_source_rgb(*self._shade("#4dabf7"))
        ctx.rectangle(x - 48, 157, 96, 61)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.6)
        for k in range(4):
            ctx.rectangle(x - 40, 205 - k * 12, 60 * ((k + ph * 3) % 1 + 0.3), 4)
        ctx.fill()
        ctx.set_source_rgb(0.2, 0.2, 0.22)
        ctx.rectangle(x - 6, 114, 12, 36)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#343a40"))
        ctx.rectangle(x + 150, 0, 10, 70)
        ctx.rectangle(x + 130, 60, 60, 12)
        ctx.rectangle(x + 175, 60, 12, 90)
        ctx.fill()

    def _d_water_cooler(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#dee2e6"))
        ctx.rectangle(x - 40, 0, 80, 170)
        ctx.fill()
        ctx.set_source_rgba(0.5, 0.75, 1, 0.8)
        ctx.arc(x, 220, 42, 0, TAU)
        ctx.fill()

    def _d_plant(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#b5651d"))
        ctx.move_to(x - 35, 0)
        ctx.line_to(x - 45, 70)
        ctx.line_to(x + 45, 70)
        ctx.line_to(x + 35, 0)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#2d6a4f"))
        for a in (-0.9, -0.4, 0, 0.4, 0.9):
            ctx.save()
            ctx.translate(x, 70)
            ctx.rotate(a)
            ctx.scale(14, 70)
            ctx.arc(0, 1, 1, 0, TAU)
            ctx.restore()
            ctx.fill()

    def _d_menu_board(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(0.15, 0.18, 0.16)
        ctx.rectangle(x - 150, 220, 300, 200)
        ctx.fill()
        ctx.save()
        ctx.translate(x - 125, 380)
        ctx.scale(1, -1)
        ctx.select_font_face("DejaVu Sans", 0, 1)
        ctx.set_font_size(24)
        ctx.set_source_rgb(1, 0.95, 0.8)
        for i, line in enumerate(("MENU", "Dosa ... 60", "Chai ... 20", "Samosa .. 15")):
            ctx.move_to(0, i * 36)
            ctx.show_text(line)
        ctx.restore()

    def _d_dining_table(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#8b5e34"))
        ctx.rectangle(x - 8, 0, 16, 100)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#ffffff"))
        ctx.move_to(x - 120, 100)
        ctx.line_to(x + 120, 100)
        ctx.line_to(x + 130, 60)
        ctx.line_to(x - 130, 60)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#e63946"))
        ctx.rectangle(x - 120, 92, 240, 8)
        ctx.fill()
        for dx in (-170, 170):
            ctx.set_source_rgb(*self._shade("#6f4518"))
            ctx.rectangle(x + dx - 30, 50, 60, 10)
            ctx.rectangle(x + dx + (25 if dx > 0 else -35), 50, 10, 90)
            ctx.rectangle(x + dx - 25, 0, 8, 50)
            ctx.rectangle(x + dx + 17, 0, 8, 50)
            ctx.fill()

    def _d_hanging_lamp(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(0.2, 0.2, 0.2)
        ctx.rectangle(x - 2, 460, 4, 200)
        ctx.fill()
        g = cairo.RadialGradient(x, 440, 5, x, 440, 200)
        g.add_color_stop_rgba(0, 1, 0.85, 0.5, 0.35)
        g.add_color_stop_rgba(1, 1, 0.85, 0.5, 0)
        ctx.set_source(g)
        ctx.arc(x, 440, 200, 0, TAU)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#e9c46a"))
        ctx.move_to(x - 50, 440)
        ctx.line_to(x - 20, 470)
        ctx.line_to(x + 20, 470)
        ctx.line_to(x + 50, 440)
        ctx.close_path()
        ctx.fill()
