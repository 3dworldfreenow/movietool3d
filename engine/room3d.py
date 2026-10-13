"""True 2.5D rooms: indoor places (room, classroom, kitchen, bedroom, office, restaurant, hospital room)
as a real box the camera can move through - floor in perspective, back wall with its board / windows /
clock, side walls, ceiling with fans, furniture standing at real depths (classroom: rows of desks).

Story x is the real position across the room (no spreading with depth like outdoors), z is the depth
from the camera side (0) to the back wall (~1000, where the board hangs).
"""
import math
import random

import cairo

from .scene3d import Obj, FOCAL, NEAR
from .world3d import World3D, Z_of_z
from .util import clamp, lerp, mix, darker, lighter, hex_to_rgb

ON_WALL = ("window", "city_window", "picture", "board", "clock", "menu_board", "curtain", "med_cabinet",
           "cabinet", "tiles_wall", "door", "mirror", "shelf", "poster", "calendar", "photo")
AGAINST_WALL = ("counter", "stove", "fridge", "bookshelf", "wardrobe", "water_cooler", "lamp_floor", "tv",
                "cupboard", "sink", "almirah")
HANGING = ("fan", "hanging_lamp", "chandelier")
SKIP = ("wall", "ceiling", "rug", "sun", "moon", "cloud")
ROOM_H = 900.0          # ceiling height
WALL_K = 1.6            # wall pictures / board bigger than in the flat look (they are far away)


class Room3D(World3D):
    room = True

    def __init__(self, bg, W, H, seed=0):
        self.Zb = Z_of_z(840) + 120.0                      # the back wall (story z ~ 900)
        self.XL, self.XR = -80.0, bg.world_w + 80.0          # the side walls
        wall = next((e for e in bg.elements if e["type"] == "wall"), None)
        self.wall_col = bg._shade(hex_to_rgb((wall or {}).get("color", "#efe4cf")))
        # a room drawn in 3D code says its own size: PLACE = {"room": {"w": 1990, "back": 880, "h": 560, "wall": ...}}
        # (back = how far behind the front of the stage its back wall stands; the furniture is the place's own things)
        room = (bg.spec.get("room") if isinstance(bg.spec.get("room"), dict) else None) or {}
        self.room_h = float(room.get("h", ROOM_H))
        self.ceiling_col = bg._shade(hex_to_rgb(room.get("ceiling", "#f4f1ea")))
        self.floor_lines = room.get("floor_lines", True) is not False
        if room.get("back"):
            self.Zb = FOCAL + float(room["back"]) + 10.0
        if room.get("w"):
            self.XL, self.XR = bg.world_w / 2.0 - float(room["w"]) / 2.0, bg.world_w / 2.0 + float(room["w"]) / 2.0
        if room.get("wall"):
            self.wall_col = bg._shade(hex_to_rgb(room["wall"]))
        super().__init__(bg, W, H, seed)
        self.shafts = False
        self.birds = False
        self.has_path = False
        self.vignette = 0.28
        self.fog = lighter(self.wall_col, 0.2)

    # ------------------------------------------------------------------ composition
    def _build(self):
        bg = self.bg
        r = random.Random(self.seed * 5 + 1)
        add = self.objs.append
        self.sky_els, self.backdrop_els = [], []
        self.has_path = False
        self.sea_from = None
        W = bg.world_w
        mids = []
        for e in bg.elements:
            typ = e["type"]
            if typ in SKIP or typ == "desk" or e.get("layer") == "sky":
                continue
            x = float(e.get("x", 0))
            if typ in ON_WALL:
                o = self._elem_obj(e, self.Zb - 2.0, WALL_K, self._wall_x(x), "place")
            elif typ in AGAINST_WALL:
                o = self._elem_obj(e, self.Zb - 140.0, 1.15, x, "place", y0=e.get("y", 0) if typ == "tv" else 0.0)
            elif typ in HANGING:
                s = ROOM_H / 660.0 if typ == "fan" else 1.2
                o = self._elem_obj(e, Z_of_z(480 if len(mids) % 2 == 0 else 330), s, x, "place")
                mids.append(e)
            elif e.get("layer") == "front":
                o = self._elem_obj(e, Z_of_z(40), 1.0, x, "place", y0=0.0)
            else:
                z = 480.0 if typ in ("bed", "sofa", "desk_pc", "dining_table", "table", "iv_stand") else 620.0
                z += r.uniform(-60, 60)
                o = self._elem_obj(e, Z_of_z(z), 1.1, x, "place", y0=0.0)
            if o:
                add(o)
        if bg.preset == "classroom":                          # rows of desks facing the board
            for row, z in enumerate((110.0, 330.0, 550.0)):
                x = 280.0 + (row % 2) * 60
                while x < W - 200:
                    o = self._elem_obj({"type": "desk", "x": x, "y": 0}, Z_of_z(z), 1.25, x, "place", y0=0.0)
                    if o:
                        add(o)
                    x += 330.0

    def _wall_x(self, x):
        """Wall pictures keep their place across the room (spread a little so they fill the wall)."""
        c = self.bg.world_w / 2.0
        return c + (x - c) * 1.05

    def _build_rain(self):
        self.puddles, self.rain_objs, self.rain_base = [], [], []

    def _haze_amount(self, d):
        return clamp(1 - math.exp(-d / 30000.0), 0, 0.12)

    def _life(self, *a, **k):
        self.birds = False

    # ------------------------------------------------------------------ box
    def _sky(self, ctx, cam, t):
        ctx.set_source_rgb(*darker(self.wall_col, 0.8))
        ctx.paint()

    def _quad(self, ctx, cam, pts):
        got = [self.project(cam, X, Y, Z) for X, Y, Z in pts]
        if any(g is None for g in got):
            # a corner behind the camera (it turned, or the room reaches past it): cut the shape at the near
            # plane instead of dropping it - else the floor vanishes as soon as the camera looks a little sideways
            c, s_ = (math.cos(cam.yaw), math.sin(cam.yaw)) if cam.yaw else (1.0, 0.0)

            def depth(q):
                return (q[0] - cam.x) * s_ + (q[2] - cam.z) * c

            lim = NEAR + 1.0
            cut = []
            for i, a in enumerate(pts):
                b = pts[(i + 1) % len(pts)]
                da, db = depth(a), depth(b)
                if da >= lim:
                    cut.append(a)
                if (da >= lim) != (db >= lim):
                    u = (lim - da) / (db - da)
                    cut.append(tuple(a[j] + (b[j] - a[j]) * u for j in range(3)))
            got = [self.project(cam, X, Y, Z) for X, Y, Z in cut]
            if len(got) < 3 or any(g is None for g in got):
                return False
        ctx.move_to(got[0][0], got[0][1])
        for g in got[1:]:
            ctx.line_to(g[0], g[1])
        ctx.close_path()
        return True

    def _ground(self, ctx, cam, t):
        bg, W, H, S = self.bg, self.W, self.H, self.S
        Zn = cam.z + NEAR + 2
        Zb, XL, XR = self.Zb, self.XL, self.XR
        floor = bg._shade(hex_to_rgb(bg.ground or "#c9b99a") if isinstance(bg.ground, str) else bg.ground)
        wall = self.wall_col
        RH = self.room_h
        # ceiling, back wall, side walls, floor - painter's order
        if self._quad(ctx, cam, [(XL - 4000, RH, Zn), (XR + 4000, RH, Zn), (XR, RH, Zb), (XL, RH, Zb)]):
            ctx.set_source_rgb(*self.ceiling_col)
            ctx.fill()
        if self._quad(ctx, cam, [(XL, 0, Zb), (XR, 0, Zb), (XR, RH, Zb), (XL, RH, Zb)]):
            ctx.set_source_rgb(*wall)
            ctx.fill()
        for X, shade in ((XL, 0.86), (XR, 0.8)):
            if self._quad(ctx, cam, [(X, 0, Zn), (X, 0, Zb), (X, RH, Zb), (X, RH, Zn)]):
                ctx.set_source_rgb(*darker(wall, shade))
                ctx.fill()
        if self._quad(ctx, cam, [(XL, 0, Zn), (XR, 0, Zn), (XR, 0, Zb), (XL, 0, Zb)]):
            pf = self.project(cam, cam.x, 0, Zn)
            pb = self.project(cam, cam.x, 0, Zb)
            yb = pb[1] if pb else H * cam.horizon             # (the camera turned: those points can be behind it)
            yf = pf[1] if pf else H
            g = cairo.LinearGradient(0, yb, 0, max(yf, yb + 1))
            g.add_color_stop_rgb(0, *darker(floor, 0.85))
            g.add_color_stop_rgb(1, *floor)
            ctx.set_source(g)
            ctx.fill()
        # floor pattern: tiles / planks in perspective
        ctx.set_source_rgba(*darker(floor, 0.75), 0.35)
        ctx.set_line_width(max(0.8, 1.6 * S))
        step = 160.0
        z = Zb
        while z > Zn and self.floor_lines:
            a, b = self.project(cam, XL, 0, z), self.project(cam, XR, 0, z)
            if a and b:
                ctx.move_to(a[0], a[1])
                ctx.line_to(b[0], b[1])
            z -= step
        x = XL
        tiles = str(bg.ground or "").lower() not in ("#b07d4f", "#a47148") and self.floor_lines
        while x <= XR and tiles:
            a, b = self.project(cam, x, 0, Zn), self.project(cam, x, 0, Zb)
            if a and b:
                ctx.move_to(a[0], a[1])
                ctx.line_to(b[0], b[1])
            x += step
        ctx.stroke()
        # skirting boards + corners
        ctx.set_source_rgb(*bg._shade(hex_to_rgb("#8a5a3b")))
        for pts in ([(XL, 0, Zb), (XR, 0, Zb), (XR, 28, Zb), (XL, 28, Zb)],
                    [(XL, 0, Zn), (XL, 0, Zb), (XL, 28, Zb), (XL, 28, Zn)],
                    [(XR, 0, Zn), (XR, 0, Zb), (XR, 28, Zb), (XR, 28, Zn)]):
            if self._quad(ctx, cam, pts):
                ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.18)
        ctx.set_line_width(max(1.0, 2 * S))
        for X in (XL, XR):
            a, b = self.project(cam, X, 0, Zb), self.project(cam, X, RH, Zb)
            if a and b:
                ctx.move_to(a[0], a[1])
                ctx.line_to(b[0], b[1])
        ctx.stroke()
        # daylight from the windows: soft bright patches on the floor
        if bg.time in ("day", "morning"):
            for e in bg.elements:
                if e["type"] in ("window", "city_window"):
                    X = self._wall_x(float(e["x"])) + 110
                    if self._quad(ctx, cam, [(X - 150, 0, Zb - 200), (X + 150, 0, Zb - 200),
                                             (X + 320, 0, Zb - 900), (X - 20, 0, Zb - 900)]):
                        ctx.set_source_rgba(1.0, 0.97, 0.85, 0.18)
                        ctx.fill()

    def render(self, ctx, cam, t, actors=()):
        from .scene3d import DepthScene
        DepthScene.render(self, ctx, cam, t, actors)
