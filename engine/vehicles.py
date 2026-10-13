"""Vehicles: car, bus, auto-rickshaw, bike, boat, rocket.

Each vehicle is drawn in two passes so riders appear *inside* it:
  draw_back()  -> interior / frame (drawn before the riders)
  draw_front() -> body with transparent window holes (drawn after the riders)
"""
import math

import cairo

from .util import hex_to_rgb, darker, lighter, TAU

DEFAULT_COLORS = {"car": "#e63946", "bus": "#f4b400", "auto": "#2a9d4f", "bike": "#1d4e89",
                  "boat": "#a0522d", "rocket": "#e9ecef", "rowboat": "#8b5a2b", "fishing_boat": "#1d6fa3",
                  "sailboat": "#f8f9fa", "ship": "#e9ecef", "paper_boat": "#fdfcdc"}
BOATS = ("boat", "rowboat", "fishing_boat", "sailboat", "ship", "paper_boat")


CAR_DOORS = {0: (-18, 190), 1: (-205, -18)}      # local x ranges of the front / rear door (car facing right)


def _rr(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def _poly(ctx, pts):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.close_path()


def _fill(ctx, col, outline=None, ow=3.0, alpha=1.0):
    ctx.set_source_rgba(*col, alpha)
    if outline is not None:
        ctx.fill_preserve()
        ctx.set_source_rgba(*outline, alpha)
        ctx.set_line_width(ow)
        ctx.stroke()
    else:
        ctx.fill()


def _wheel(ctx, x, y, r, spin, dark=(0.13, 0.13, 0.15)):
    ctx.arc(x, y, r, 0, TAU)
    _fill(ctx, dark)
    ctx.arc(x, y, r * 0.58, 0, TAU)
    _fill(ctx, (0.72, 0.74, 0.78), (0.4, 0.42, 0.45), 2.5)
    ctx.set_source_rgb(0.4, 0.42, 0.45)
    ctx.set_line_width(3.5)
    for k in range(5):
        a = spin + k * TAU / 5
        ctx.move_to(x, y)
        ctx.line_to(x + math.cos(a) * r * 0.55, y + math.sin(a) * r * 0.55)
    ctx.stroke()
    ctx.arc(x, y, r * 0.14, 0, TAU)
    _fill(ctx, (0.3, 0.3, 0.33))


class VehicleDraw:
    def __init__(self, vtype, spec):
        self.t = "car" if vtype == "jeep" else vtype          # side view of a jeep = the car shape
        self.col = hex_to_rgb(spec.get("color", DEFAULT_COLORS.get(vtype, "#5b7f3a" if vtype == "jeep" else "#e63946")))
        self.s = float(spec.get("scale", 1.0))
        self.text = str(spec.get("text", ""))
        self.spec = spec
        self.sea = float(spec.get("_sea", 0))

    def _begin(self, ctx, x, y, facing):
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(self.s * (-1 if facing < 0 else 1), self.s)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # ------------------------------------------------------------------ back pass
    def _picture(self, ctx, x, y, facing, t, moving):
        """A picture used as a vehicle: the whole picture, bumping along while it moves."""
        from . import images
        name = self.spec.get("type")
        m = images.info(name) or {}
        h = float(self.spec.get("height") or m.get("height") or 240) * self.s
        bounce = (2.5 * abs(math.sin(t * 9.0)) + 1.0 * math.sin(t * 23)) if moving else 0.0
        faces_left = str(self.spec.get("faces", m.get("faces", "right"))).lower() == "left"
        ctx.save()
        k = 1.0
        ctx.translate(x, y + 1)
        ctx.scale(h * 0.9 * k, 14 * k)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.set_source_rgba(0, 0, 0, 0.16)
        ctx.fill()
        ctx.restore()
        images.draw(ctx, name, x, y + bounce, h, (facing < 0) != faces_left, t=t)

    def draw_back(self, ctx, x, y, facing, spin, t, moving, shadow_y=0.0, doors=None):
        if self.t == "picture":
            from . import images
            m = images.info(self.spec.get("type")) or {}
            if m.get("made_by") == "code":                   # code vehicles: t = driving time (wheels stop)
                sp = float((m.get("ride") or {}).get("speed") or 220.0)
                t = spin * 55.0 / sp
            return self._picture(ctx, x, y, facing, t, moving)
        ctx.save()
        if y < 400:
            k = max(0.2, 1 - y / 500)
            ctx.translate(x, shadow_y + 1)
            w = {"car": 330, "bus": 560, "auto": 250, "bike": 170, "rocket": 120}.get(self.t, 0) * self.s
            if w:
                ctx.scale(w * k, 16 * k * self.s)
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.set_source_rgba(0, 0, 0, 0.18 * k)
                ctx.fill()
        ctx.restore()
        self._begin(ctx, x, y, facing)
        c, d = self.col, darker(self.col, 0.6)
        interior = (0.2, 0.22, 0.26)
        bounce = 2.0 * math.sin(t * 23) if moving else 0.0
        if self.t == "car":
            ctx.translate(0, bounce)
            _poly(ctx, [(-235, 150), (-180, 246), (135, 246), (215, 150)])
            _fill(ctx, interior)
            for seat, amt in (doors or {}).items():         # open door: the inside (seat, floor) shows
                if amt > 0.02:
                    x0, x1 = CAR_DOORS[min(seat, 1)]
                    _rr(ctx, x0, 45, x1 - x0, 190, 10)
                    _fill(ctx, interior)
                    _rr(ctx, x0 + 12, 60, x1 - x0 - 24, 55, 12)
                    _fill(ctx, (0.35, 0.22, 0.2))              # seat
        elif self.t == "bus":
            ctx.translate(0, bounce)
            _rr(ctx, -540, 60, 1080, 360, 30)
            _fill(ctx, interior)
        elif self.t == "auto":
            ctx.translate(0, bounce)
            _poly(ctx, [(-200, 90), (-200, 300), (130, 300), (130, 90)])
            _fill(ctx, (0.15, 0.15, 0.15))
        elif self.t == "bike":
            r = 62
            for wx in (-120, 120):
                ctx.arc(wx, r, r, 0, TAU)
                ctx.set_source_rgb(0.15, 0.15, 0.17)
                ctx.set_line_width(9)
                ctx.stroke()
                ctx.set_line_width(1.5)
                ctx.set_source_rgb(0.55, 0.55, 0.6)
                for k in range(12):
                    a = spin + k * TAU / 12
                    ctx.move_to(wx, r)
                    ctx.line_to(wx + math.cos(a) * r, r + math.sin(a) * r)
                ctx.stroke()
            ctx.set_source_rgb(*c)
            ctx.set_line_width(9)
            _poly(ctx, [(-120, r), (-15, r), (60, 175), (-50, 170)])
            ctx.stroke()
            ctx.move_to(-15, r)
            ctx.line_to(-50, 170)
            ctx.move_to(60, 175)
            ctx.line_to(120, r)
            ctx.move_to(60, 175)
            ctx.line_to(72, 205)
            ctx.stroke()
            ctx.set_source_rgb(0.1, 0.1, 0.1)
            ctx.set_line_width(10)
            ctx.move_to(56, 208)
            ctx.line_to(88, 204)
            ctx.stroke()
            _rr(ctx, -80, 172, 56, 12, 6)
            _fill(ctx, (0.12, 0.12, 0.12))
            ctx.set_line_width(5)
            ctx.set_source_rgb(0.3, 0.3, 0.3)
            ctx.move_to(-15 + math.cos(spin * 0.5) * 22, r + math.sin(spin * 0.5) * 22)
            ctx.line_to(-15 - math.cos(spin * 0.5) * 22, r - math.sin(spin * 0.5) * 22)
            ctx.stroke()
        elif self.t in BOATS:
            self._boat_back(ctx, t, moving)
        elif self.t == "rocket":
            if moving:
                for k in range(3):
                    fl = 90 + 40 * math.sin(t * 40 + k)
                    ctx.move_to(-45 + k * 10, 10)
                    ctx.line_to(0, -fl + k * 25)
                    ctx.line_to(45 - k * 10, 10)
                    ctx.close_path()
                    _fill(ctx, [(1, 0.55, 0.1), (1, 0.8, 0.2), (1, 1, 0.8)][k])
            _poly(ctx, [(-70, 30), (-70, 520), (0, 700), (70, 520), (70, 30)])
            _fill(ctx, c, darker(c, 0.6), 4)
            ctx.arc(0, 420, 58, 0, TAU)
            _fill(ctx, interior)
        ctx.restore()

    # ------------------------------------------------------------------ front pass
    def draw_front(self, ctx, x, y, facing, spin, t, moving, doors=None):
        if self.t == "picture":
            return                                          # riders sit on top of the picture
        self._begin(ctx, x, y, facing)
        c, d = self.col, darker(self.col, 0.6)
        glass = (0.75, 0.9, 1.0)
        bounce = 2.0 * math.sin(t * 23) if moving else 0.0
        open_doors = {k: v for k, v in (doors or {}).items() if v > 0.02} if self.t == "car" else {}
        if open_doors:                                      # cut the open doors out of the body
            ctx.save()
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            ctx.rectangle(-2000, -2000, 4000, 4000)
            for seat in open_doors:
                x0, x1 = CAR_DOORS[min(seat, 1)]
                ctx.rectangle(x0, 44, x1 - x0, 192)
            ctx.clip()
            ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
        if self.t == "car":
            ctx.translate(0, bounce)
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            _poly(ctx, [(-235, 150), (-180, 246), (135, 246), (215, 150)])
            _poly(ctx, [(-208, 158), (-168, 234), (-28, 234), (-28, 158)])
            _poly(ctx, [(-8, 158), (-8, 234), (122, 234), (188, 158)])
            _fill(ctx, c, d, 4)
            _rr(ctx, -310, 40, 620, 120, 34)
            _fill(ctx, c, d, 4)
            ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
            for w in ([(-208, 158), (-168, 234), (-28, 234), (-28, 158)], [(-8, 158), (-8, 234), (122, 234), (188, 158)]):
                _poly(ctx, w)
                _fill(ctx, glass, alpha=0.22)
            ctx.set_source_rgba(*d, 1)
            ctx.set_line_width(3)
            ctx.move_to(-18, 150)
            ctx.line_to(-18, 60)
            ctx.stroke()
            _rr(ctx, 30, 118, 40, 9, 4)
            _fill(ctx, darker(c, 0.5))
            _rr(ctx, 288, 105, 26, 22, 8)
            _fill(ctx, (1, 0.95, 0.6))
            _rr(ctx, -316, 105, 16, 22, 6)
            _fill(ctx, (0.9, 0.15, 0.15))
            for wx in (-195, 195):
                ctx.arc(wx, 55, 70, math.pi * 0.05, math.pi * 0.95)
                _fill(ctx, darker(c, 0.75))
                _wheel(ctx, wx, 55, 55, -spin)
            if moving:
                ctx.set_source_rgba(0.6, 0.6, 0.6, 0.5)
                for k in range(3):
                    r = 12 + ((t * 3 + k / 3) % 1) * 22
                    ctx.arc(-330 - ((t * 3 + k / 3) % 1) * 60, 60, r, 0, TAU)
                    ctx.fill()
            if open_doors:
                ctx.restore()
                ctx.save()
                ctx.translate(0, bounce)
                for seat, amt in open_doors.items():         # the door swings out toward the camera
                    x0, x1 = CAR_DOORS[min(seat, 1)]
                    w = (x1 - x0) * (1 - 0.84 * amt)
                    sk = 26 * amt                               # the free edge is nearer: it looks bigger
                    panel = [(x1, 45), (x1, 234), (x1 - w, 234 + sk * 0.6), (x1 - w, 45 - sk)]
                    _poly(ctx, panel)
                    _fill(ctx, darker(c, 0.92), d, 4)
                    win = [(x1 - 6, 158), (x1 - 6, 226), (x1 - w + 8, 226 + sk * 0.55), (x1 - w + 8, 158 + sk * 0.2)]
                    _poly(ctx, win)
                    _fill(ctx, glass, alpha=0.35)
                    _rr(ctx, x1 - w + 14, 112 - sk * 0.15, 28, 8, 4)
                    _fill(ctx, darker(c, 0.5))
                ctx.restore()
                open_doors = {}
        elif self.t == "bus":
            ctx.translate(0, bounce)
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            _rr(ctx, -550, 45, 1100, 380, 34)
            wins = []
            for k in range(6):
                wx = -500 + k * 140
                wins.append([(wx, 215), (wx, 345), (wx + 115, 345), (wx + 115, 215)])
            wins.append([(390, 200), (390, 360), (520, 360), (535, 200)])
            for w in wins:
                _poly(ctx, w)
            _fill(ctx, c, d, 4)
            ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
            for w in wins:
                _poly(ctx, w)
                _fill(ctx, glass, alpha=0.2)
            ctx.set_source_rgb(*darker(c, 0.35))
            ctx.rectangle(-550, 170, 1100, 16)
            ctx.fill()
            _rr(ctx, 300, 60, 70, 280, 8)
            _fill(ctx, darker(c, 0.75), d, 3)
            if self.text:
                ctx.save()
                ctx.translate(-440, 110)
                ctx.scale(1, -1)
                ctx.select_font_face("DejaVu Sans", 0, 1)
                ctx.set_font_size(48)
                ctx.set_source_rgb(0.1, 0.1, 0.1)
                ctx.show_text(self.text[:20])
                ctx.restore()
            _rr(ctx, 520, 80, 30, 30, 8)
            _fill(ctx, (1, 0.95, 0.6))
            for wx in (-340, 360):
                ctx.arc(wx, 60, 76, math.pi * 0.05, math.pi * 0.95)
                _fill(ctx, darker(c, 0.7))
                _wheel(ctx, wx, 60, 60, -spin)
        elif self.t == "auto":
            ctx.translate(0, bounce)
            yel = (0.98, 0.8, 0.1)
            _poly(ctx, [(-230, 40), (-230, 150), (100, 150), (200, 240), (235, 240), (235, 40)])
            _fill(ctx, c, d, 4)
            ctx.set_source_rgb(*yel)
            ctx.rectangle(-230, 125, 330, 22)
            ctx.fill()
            _rr(ctx, -245, 290, 400, 50, 20)
            _fill(ctx, (0.12, 0.12, 0.12), (0.05, 0.05, 0.05), 3)
            ctx.set_source_rgb(*yel)
            ctx.rectangle(-240, 300, 390, 10)
            ctx.fill()
            ctx.set_source_rgb(0.1, 0.1, 0.1)
            ctx.set_line_width(9)
            ctx.move_to(-225, 150)
            ctx.line_to(-225, 295)
            ctx.move_to(140, 240)
            ctx.line_to(140, 295)
            ctx.stroke()
            _poly(ctx, [(150, 245), (150, 290), (225, 290), (235, 245)])
            _fill(ctx, glass, (0.1, 0.1, 0.1), 5, alpha=0.6)
            _rr(ctx, 222, 150, 20, 26, 8)
            _fill(ctx, (1, 0.95, 0.6))
            for wx in (-150, 180):
                _wheel(ctx, wx, 42, 42, -spin)
        elif self.t in BOATS:
            self._boat_front(ctx, t, moving)
        elif self.t == "rocket":
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            _poly(ctx, [(-70, 30), (-70, 520), (0, 700), (70, 520), (70, 30)])
            ctx.new_sub_path()
            ctx.arc(0, 420, 50, 0, TAU)
            _fill(ctx, c, darker(c, 0.6), 4)
            ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
            ctx.arc(0, 420, 50, 0, TAU)
            _fill(ctx, glass, (0.35, 0.4, 0.5), 8, alpha=0.25)
            red = (0.9, 0.2, 0.2)
            _poly(ctx, [(0, 700), (-42, 600), (42, 600)])
            _fill(ctx, red, darker(red, 0.6), 3)
            for sgn in (-1, 1):
                _poly(ctx, [(sgn * 70, 30), (sgn * 70, 190), (sgn * 140, 0), (sgn * 140, -30)])
                _fill(ctx, red, darker(red, 0.6), 3)
            ctx.set_source_rgb(0.3, 0.32, 0.36)
            ctx.rectangle(-55, 0, 110, 32)
            ctx.fill()
            if self.text:
                ctx.save()
                ctx.translate(-22, 250)
                ctx.rotate(math.pi / 2)
                ctx.scale(1, -1)
                ctx.select_font_face("DejaVu Sans", 0, 1)
                ctx.set_font_size(40)
                ctx.set_source_rgb(0.15, 0.2, 0.5)
                ctx.show_text(self.text[:10])
                ctx.restore()
        ctx.restore()


    # ------------------------------------------------------------------ boats
    def _tilt(self, ctx, t):
        ctx.rotate((0.006 + 0.0022 * self.sea) * math.sin(t * 1.7))

    def _wake(self, ctx, t, length):
        ctx.set_source_rgba(1, 1, 1, 0.75)
        ctx.set_line_width(4)
        for k in range(5):
            ph = (t * 1.8 + k / 5) % 1
            x = -length / 2 - 20 - ph * 220
            ctx.move_to(x, 14 + 6 * math.sin(k))
            ctx.line_to(x + 40 * (1 - ph), 14 + 6 * math.sin(k))
        ctx.stroke()

    def _boat_back(self, ctx, t, moving):
        c = self.col
        self._tilt(ctx, t)
        if self.t == "sailboat":
            ctx.set_source_rgb(0.35, 0.25, 0.15)
            ctx.rectangle(-6, 60, 12, 520)
            ctx.fill()
            bil = 40 + 25 * math.sin(t * 1.3) + (30 if moving else 0)
            ctx.move_to(10, 560)
            ctx.curve_to(10 + bil * 2.2, 420, 10 + bil * 2.2, 220, 10, 110)
            ctx.line_to(250, 110)
            ctx.close_path()
            _fill(ctx, (0.98, 0.98, 0.95), (0.6, 0.6, 0.6), 3)
            ctx.move_to(-10, 520)
            ctx.line_to(-10, 110)
            ctx.line_to(-200, 110)
            ctx.close_path()
            _fill(ctx, (0.9, 0.3, 0.3), (0.6, 0.2, 0.2), 3)
        elif self.t == "fishing_boat":
            _rr(ctx, -300, 80, 190, 170, 10)
            _fill(ctx, (0.95, 0.95, 0.95), (0.5, 0.5, 0.5), 3)
            ctx.rectangle(-280, 170, 60, 50)
            ctx.rectangle(-200, 170, 60, 50)
            _fill(ctx, (0.6, 0.85, 1.0))
            ctx.set_source_rgb(0.35, 0.25, 0.15)
            ctx.rectangle(-60, 80, 8, 330)
            ctx.fill()
            ctx.set_source_rgba(0.3, 0.3, 0.3, 0.6)
            ctx.set_line_width(2)
            ctx.move_to(-56, 400)
            ctx.line_to(260, 150)
            ctx.stroke()
        elif self.t == "ship":
            _rr(ctx, -520, 200, 760, 190, 14)
            _fill(ctx, (0.97, 0.97, 0.97), (0.55, 0.55, 0.55), 4)
            for k in range(8):
                ctx.arc(-470 + k * 95, 300, 20, 0, TAU)
                _fill(ctx, (0.6, 0.85, 1.0), (0.4, 0.45, 0.5), 3)
            _rr(ctx, -300, 390, 360, 110, 10)
            _fill(ctx, (0.97, 0.97, 0.97), (0.55, 0.55, 0.55), 4)
            ctx.rectangle(-120, 500, 90, 150)
            _fill(ctx, (0.85, 0.15, 0.2), (0.5, 0.1, 0.1), 3)
            ctx.rectangle(-120, 610, 90, 22)
            _fill(ctx, (0.15, 0.15, 0.15))
            for k in range(4):
                ph = (t * 0.6 + k / 4) % 1
                ctx.arc(-75 - ph * 160, 660 + ph * 170, 25 + 60 * ph, 0, TAU)
                ctx.set_source_rgba(0.75, 0.75, 0.78, 0.5 * (1 - ph))
                ctx.fill()

    def _boat_front(self, ctx, t, moving):
        c, d = self.col, darker(self.col, 0.6)
        self._tilt(ctx, t)
        if self.t == "boat":
            if moving:
                self._wake(ctx, t, 540)
            _poly(ctx, [(-270, 90), (-230, 0), (220, 0), (290, 100)])
            _fill(ctx, c, d, 4)
            ctx.set_source_rgb(*lighter(c, 0.3))
            ctx.rectangle(-255, 70, 530, 14)
            ctx.fill()
        elif self.t == "rowboat":
            if moving:
                self._wake(ctx, t, 380)
            _poly(ctx, [(-200, 70), (-160, 0), (160, 0), (205, 75)])
            _fill(ctx, c, d, 4)
            ctx.set_source_rgb(*lighter(c, 0.25))
            ctx.rectangle(-190, 55, 385, 10)
            ctx.fill()
            a = 0.6 * math.sin(t * 3.5) if moving else 0.2
            for ox in (60, -80):
                ctx.save()
                ctx.translate(ox, 70)
                ctx.rotate(-0.9 + a)
                ctx.set_source_rgb(0.45, 0.3, 0.15)
                ctx.rectangle(-4, -150, 8, 190)
                ctx.fill()
                ctx.rectangle(-12, -170, 24, 45)
                ctx.fill()
                ctx.restore()
        elif self.t == "fishing_boat":
            if moving:
                self._wake(ctx, t, 620)
            _poly(ctx, [(-320, 95), (-290, 0), (260, 0), (340, 110)])
            _fill(ctx, c, d, 4)
            ctx.set_source_rgb(0.95, 0.95, 0.95)
            ctx.rectangle(-305, 60, 620, 14)
            ctx.fill()
            if self.text:
                self._name(ctx, self.text, -60, 22, 34)
        elif self.t == "sailboat":
            if moving:
                self._wake(ctx, t, 500)
            _poly(ctx, [(-250, 80), (-200, 0), (200, 0), (270, 90)])
            _fill(ctx, c, (0.5, 0.5, 0.5), 4)
            ctx.set_source_rgb(0.15, 0.35, 0.65)
            ctx.rectangle(-240, 55, 500, 14)
            ctx.fill()
        elif self.t == "ship":
            if moving:
                self._wake(ctx, t, 1400)
            _poly(ctx, [(-640, 210), (-600, 0), (560, 0), (700, 230)])
            _fill(ctx, (0.12, 0.2, 0.35), (0.05, 0.1, 0.2), 4)
            ctx.set_source_rgb(0.85, 0.15, 0.2)
            ctx.rectangle(-620, 0, 1230, 30)
            ctx.fill()
            ctx.set_source_rgb(0.95, 0.95, 0.95)
            ctx.rectangle(-630, 190, 1310, 18)
            ctx.fill()
            ctx.set_source_rgba(0.9, 0.9, 0.9, 1)
            ctx.set_line_width(3)
            ctx.move_to(-630, 290)
            ctx.line_to(680, 290)
            for k in range(28):
                ctx.move_to(-630 + k * 47, 208)
                ctx.line_to(-630 + k * 47, 290)
            ctx.stroke()
            if self.text:
                self._name(ctx, self.text, 250, 90, 46)
        elif self.t == "paper_boat":
            ctx.scale(0.5, 0.5)
            _poly(ctx, [(-120, 50), (-80, 0), (80, 0), (120, 50)])
            _fill(ctx, c, (0.6, 0.6, 0.55), 3)
            _poly(ctx, [(-60, 50), (0, 140), (60, 50)])
            _fill(ctx, lighter(c, 0.1), (0.6, 0.6, 0.55), 3)

    def _name(self, ctx, txt, x, y, size):
        ctx.save()
        ctx.translate(x, y + size)
        ctx.scale(1, -1)
        ctx.select_font_face("DejaVu Sans", 0, 1)
        ctx.set_font_size(size)
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(0, 0)
        ctx.show_text(txt[:16])
        ctx.restore()
