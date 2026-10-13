"""▶ The live 2.5D player: the server works out a frame (who stands where, poses, faces, camera) but draws no pixels -
it records the drawing (lines, curves, colours) and the browser replays it on a canvas over the background picture
(static/live25d.js). Canvas 2D is almost the same API as cairo, so every character, prop and effect drawn with paths
plays in the browser at full speed and full sharpness; the phone's graphics chip does the drawing.

The recorder wraps a real cairo context on a 1x1 surface: every call goes to it too, so transforms, current points
and text sizes are exact, and filling 1 pixel costs nothing."""
import math

import cairo

# short op names (the browser's live25d.js reads the same)
_PLAIN = {"move_to": "M", "line_to": "L", "curve_to": "C", "close_path": "Z", "new_path": "N", "rectangle": "R",
          "fill": "F", "fill_preserve": "f", "stroke": "S", "stroke_preserve": "s", "save": "(", "restore": ")",
          "translate": "T", "scale": "K", "rotate": "O", "set_line_width": "W", "clip": "P", "clip_preserve": "p",
          "paint": "Q", "paint_with_alpha": "q", "identity_matrix": "I", "set_font_size": "z",
          "new_sub_path": "n"}
_CAP = {cairo.LINE_CAP_BUTT: 0, cairo.LINE_CAP_ROUND: 1, cairo.LINE_CAP_SQUARE: 2}
_JOIN = {cairo.LINE_JOIN_MITER: 0, cairo.LINE_JOIN_ROUND: 1, cairo.LINE_JOIN_BEVEL: 2}
_OPS = {cairo.OPERATOR_OVER: "source-over", cairo.OPERATOR_ADD: "lighter", cairo.OPERATOR_DEST_OUT: "destination-out",
        cairo.OPERATOR_MULTIPLY: "multiply", cairo.OPERATOR_SCREEN: "screen", cairo.OPERATOR_SOURCE: "copy",
        cairo.OPERATOR_DEST_IN: "destination-in", cairo.OPERATOR_ATOP: "source-atop",
        cairo.OPERATOR_OVERLAY: "overlay", cairo.OPERATOR_SOFT_LIGHT: "soft-light"}


def _r(v):
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, (str, int)) or v is None:
        return v
    try:                                               # numpy numbers (the drawing code uses them too)
        return round(float(v), 2)
    except (TypeError, ValueError):
        return v


def _pattern(p):
    """a cairo pattern -> a small list the browser turns into a canvas style (None: not drawable there)"""
    if isinstance(p, cairo.SolidPattern):
        return ["c", *[round(c, 3) for c in p.get_rgba()]]
    stops = []
    if isinstance(p, cairo.Gradient):
        stops = [[round(s[0], 3), round(s[1], 3), round(s[2], 3), round(s[3], 3), round(s[4], 3)]
                 for s in p.get_color_stops_rgba()]
        m = list(p.get_matrix())                       # pattern space -> user space at set_source time
    if isinstance(p, cairo.LinearGradient):
        return ["l", [_r(v) for v in p.get_linear_points()], stops, [_r(v) for v in m]]
    if isinstance(p, cairo.RadialGradient):
        return ["r", [_r(v) for v in p.get_radial_circles()], stops, [_r(v) for v in m]]
    return None


class Recorder:
    """a stand-in cairo.Context: forwards to a real one and keeps the ops of one frame in .ops"""

    def __init__(self):
        self._surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        self._c = cairo.Context(self._surf)
        self.ops = []

    # ---- anything we do not need to record (queries, antialias, fonts) goes straight to the real context
    def __getattr__(self, name):
        return getattr(self._c, name)

    def op(self, *a):
        self.ops.append(list(a))

    def _rec(name):                                    # noqa: N805 (a small factory for the plain ops)
        code = _PLAIN[name]

        def f(self, *a):
            getattr(self._c, name)(*a)
            self.ops.append([code, *[_r(v) for v in a]] if a else [code])
        f.__name__ = name
        return f

    for _n in _PLAIN:
        locals()[_n] = _rec(_n)
    del _n

    # ---- the ones that need a little translation
    def arc(self, xc, yc, r, a1, a2):
        self._c.arc(xc, yc, r, a1, a2)
        self.ops.append(["A", _r(xc), _r(yc), _r(max(0.0, r)), round(a1, 4), round(a2, 4), 0])

    def arc_negative(self, xc, yc, r, a1, a2):
        self._c.arc_negative(xc, yc, r, a1, a2)
        self.ops.append(["A", _r(xc), _r(yc), _r(max(0.0, r)), round(a1, 4), round(a2, 4), 1])

    def _rel(self, real, *a):
        getattr(self._c, real)(*a)
        x, y = self._c.get_current_point()
        if real == "rel_curve_to":
            x0, y0 = x - a[4], y - a[5]
            self.ops.append(["C", _r(x0 + a[0]), _r(y0 + a[1]), _r(x0 + a[2]), _r(y0 + a[3]), _r(x), _r(y)])
        else:
            self.ops.append(["M" if real == "rel_move_to" else "L", _r(x), _r(y)])

    def rel_line_to(self, dx, dy):
        self._rel("rel_line_to", dx, dy)

    def rel_move_to(self, dx, dy):
        self._rel("rel_move_to", dx, dy)

    def rel_curve_to(self, *a):
        self._rel("rel_curve_to", *a)

    def set_source_rgb(self, r, g, b):
        self._c.set_source_rgb(r, g, b)
        self.ops.append(["c", round(r, 3), round(g, 3), round(b, 3), 1])

    def set_source_rgba(self, r, g, b, a=1.0):
        self._c.set_source_rgba(r, g, b, a)
        self.ops.append(["c", round(r, 3), round(g, 3), round(b, 3), round(a, 3)])

    def set_source(self, p):
        self._c.set_source(p)
        if p is getattr(self, "_group", None):
            self.ops.append(["gG"])                    # the last group as the source
            return
        pat = _pattern(p)
        self.ops.append(["g", pat] if pat else ["c", 0, 0, 0, 0])

    def set_source_surface(self, s, x=0.0, y=0.0):     # pictures made on the server are not sent (yet)
        self._c.set_source_rgba(0, 0, 0, 0)
        self.ops.append(["c", 0, 0, 0, 0])

    def set_line_cap(self, v):
        self._c.set_line_cap(v)
        self.ops.append(["j", 0, _CAP.get(v, 0)])

    def set_line_join(self, v):
        self._c.set_line_join(v)
        self.ops.append(["j", 1, _JOIN.get(v, 0)])

    def set_dash(self, dashes, offset=0.0):
        self._c.set_dash(dashes, offset)
        self.ops.append(["D", [_r(float(d)) for d in dashes], _r(float(offset))])

    def set_fill_rule(self, v):
        self._c.set_fill_rule(v)
        self.ops.append(["E", 1 if v == cairo.FILL_RULE_EVEN_ODD else 0])

    def set_operator(self, v):
        self._c.set_operator(v)
        self.ops.append(["o", _OPS.get(v, "source-over")])

    def set_matrix(self, m):
        self._c.set_matrix(m)
        self.ops.append(["X", *[_r(v) for v in m]])

    def transform(self, m):
        self._c.transform(m)
        self.ops.append(["Y", *[_r(v) for v in m]])

    def select_font_face(self, family, slant=cairo.FONT_SLANT_NORMAL, weight=cairo.FONT_WEIGHT_NORMAL):
        self._c.select_font_face(family, slant, weight)
        self.ops.append(["y", family, 1 if weight == cairo.FONT_WEIGHT_BOLD else 0])

    def show_text(self, s):
        x, y = self._c.get_current_point() if self._c.has_current_point() else (0.0, 0.0)
        adv = self._c.text_extents(s).x_advance          # the browser stretches its font to this width
        self._c.show_text(s)
        self.ops.append(["t", s, _r(x), _r(y), _r(adv)])

    def text_path(self, s):
        x, y = self._c.get_current_point() if self._c.has_current_point() else (0.0, 0.0)
        adv = self._c.text_extents(s).x_advance
        self._c.text_path(s)
        self.ops.append(["x", s, _r(x), _r(y), _r(adv)])

    # groups (offscreen layers): the browser draws them on an offscreen canvas of its own
    def push_group(self):
        self._c.push_group()
        self.ops.append(["G"])

    def push_group_with_content(self, c):
        self._c.push_group_with_content(c)
        self.ops.append(["G"])

    def pop_group(self):
        self._group = self._c.pop_group()
        self.ops.append(["Gp"])                        # the layer is kept as "the last group"
        return self._group

    def pop_group_to_source(self):
        self._c.pop_group_to_source()
        self.ops.append(["Gs"])                        # the layer becomes the source (then a paint)

    def mask(self, p):
        self._c.mask(p)
        if p is getattr(self, "_group", None):
            self.ops.append(["Mg"])                    # the source, where the last group is drawn

    def mask_surface(self, s, x=0.0, y=0.0):
        self._c.mask_surface(s, x, y)


def frame_ops(fi, P):
    """the drawing of frame fi of a built project, as a list of ops (and the plate it stands on)"""
    from . import render as R
    rec = Recorder()
    R.render_frame(fi, P, ctx=rec)
    return rec.ops


def plate_op(world, cam, W, H, S):
    """where the plate picture lands on the screen for this camera (photoworld smooth mode, camera at the plate's own
    point: zoom = scale, turning = a slide, tilt = a slide - the same sums as photoworld._warp with cam at the plate)"""
    m = world.meta
    s, iw, ih = m["scale"], m["width"], m["height"]           # photo.jpg is width x height; scale: px -> 1080p px
    k = S * cam.fz
    dw, dh = iw * s * k, ih * s * k
    from .scene3d import FOCAL
    dx = W / 2 + cam.shift * S - dw / 2 - FOCAL * k * math.tan(cam.yaw or 0.0)
    dy = H * cam.horizon + (540.0 - ih * s / 2 - world.hy) * k
    return ["B", m["name"], _r(dx), _r(dy), _r(dw), _r(dh), 1 if cam.mirror else 0]
