"""Real 3D code drawings (KIND = "object3d" / "prop3d" / "vehicle3d" / "objects3d" / "place3d").

You build the thing from simple solid shapes - boxes, roofs, cylinders, cones, spheres, extruded outlines - in
story units (a person is 300 tall).  x = right, y = UP, z = AWAY from the camera (depth).  The object stands on
y = 0 and is centred on x = 0, z = 0.

    KIND = "object3d"
    def draw(pen, t, state):
        wall = pen.box(0, 0, 0, w=440, h=245, d=320, c="mud")
        pen.roof(0, 245, 0, w=520, d=400, h=190, c="thatch")
        pen.door(wall, x=0, w=110, h=215)
        pen.window(wall, x=-140, y=120, w=60, h=60)

How it is shown
  * 3D camera mode ("camera_mode": "3d"): every face is projected by the real scene camera, so pans, dollies,
    crane and arc shots show the sides and the roof. Faces are lit by the sun (morning light from the left,
    evening light from the right), and each thing throws a soft shadow on the ground.
  * Normal (2D) mode, the Studio library and the backup picture: a front view (like an architect's elevation).
Characters stay 2D cut-outs; they always face the camera, so mixing never shows a paper edge.

No extra software: pure Python + cairo, CPU only.  A hut is ~60-150 faces (about 1-2 ms a frame).
"""
import math
import os
import random

import cairo

from .codedraw import color, _hex, _Thing, _clean   # noqa: F401  (same colours / palette as 2D drawings)

AMBIENT = 0.62          # how bright a face is that the sun does not reach
SKIN_FILL = 0.32        # the camera-side fill light on skin (faces keep their true colour, not muddy in shade)
SKIN = [True]           # skin shading for people's skin (wrap light, warm edge, soft dark corners, rim light)


def skin_light(r, g, b, nd, ny, nv):
    """🙂 how skin takes light (film look, faked cheaply): light wraps a little past the shadow line (it scatters
    inside the skin) and that edge turns warm red; faces pointing down (under the chin, nose, jaw, the neck) get
    less sky light - soft dark corners; a thin rim of light on the edges (nv = |normal · view|)."""
    wrap = max(0.0, min(1.0, (nd + 0.55) / 1.55))
    hemi = 0.58 + 0.42 * (ny * 0.5 + 0.5)
    # a soft fill from the camera side (a film reflector): faces stay their real colour even when the sun is
    # behind them; the edges turning away stay darker, so the face keeps its shape
    lit = AMBIENT * hemi + DIFFUSE * 1.1 * wrap + SKIN_FILL * nv * nv
    term = max(0.0, min(0.5, wrap - max(0.0, nd)))
    rim = 0.3 * (1.0 - nv) ** 3
    # skin's colour shifts with the light (blood under it): the shade turns warmer and richer, never grey;
    # the lit side a touch lighter and golden; a soft sheen where the light meets the face (forehead, nose, cheeks)
    sh = max(0.0, min(1.0, 1.0 - wrap)) * 0.85
    sheen = 0.11 * max(0.0, nd) ** 6 * nv ** 3
    gold = 0.07 * max(0.0, nd)
    return (min(1.0, r * (lit + 0.3 * term) * (1 + 0.1 * sh) + rim + sheen + gold * 0.6),
            min(1.0, g * (lit + 0.08 * term) * (1 - 0.1 * sh) + rim * 0.93 + sheen * 0.96 + gold * 0.45),
            min(1.0, b * (lit - 0.02 * term) * (1 - 0.18 * sh) + rim * 0.88 + sheen * 0.9 + gold * 0.15))


def skin_light_np(C, nd, ny, nv):
    """skin_light for many faces / corners at once (numpy): C (N, 3), nd / ny / nv (N,) -> (N, 3)"""
    import numpy as np
    wrap = np.clip((nd + 0.55) / 1.55, 0.0, 1.0)
    lit = AMBIENT * (0.58 + 0.42 * (ny * 0.5 + 0.5)) + DIFFUSE * 1.1 * wrap + SKIN_FILL * nv * nv
    term = np.clip(wrap - np.maximum(0.0, nd), 0.0, 0.5)
    rim = 0.3 * (1.0 - nv) ** 3
    sh = np.clip(1.0 - wrap, 0.0, 1.0) * 0.85                    # (see skin_light: warm shade, golden light, sheen)
    pos = np.maximum(0.0, nd)
    sheen = 0.11 * pos ** 6 * nv ** 3
    gold = 0.07 * pos
    out = C * (lit[:, None] + term[:, None] * np.array([0.3, 0.08, -0.02]))
    out = out * (1.0 + sh[:, None] * np.array([0.1, -0.1, -0.18]))
    out = out + rim[:, None] * np.array([1.0, 0.93, 0.88]) + sheen[:, None] * np.array([1.0, 0.96, 0.9]) \
        + gold[:, None] * np.array([0.6, 0.45, 0.15])
    return np.minimum(1.0, out)
DIFFUSE = 0.42


def _norm(v):
    L = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / L, v[1] / L, v[2] / L)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


LOD_NEAR = 0.3             # a sculpted thing taller than this part of the frame gets its full mesh


class Face:
    __slots__ = ("pts", "n", "c", "cull", "line", "w", "parent", "sub", "edge", "kind", "mat", "walk", "tex", "uv", "vn",
                 "lod", "vc")

    def __init__(self, pts, n, c, cull=True, line=False, w=0.0, parent=None, sub=0, edge=None, kind="poly",
                 mat=None, walk=False, tex=None, uv=None, vn=None, lod=None, vc=None):
        self.pts, self.n, self.c, self.cull, self.line, self.w = pts, n, c, cull, line, w
        self.vc = vc                                    # a colour per corner (sculpted clay: soft colour edges) or None
        self.lod = lod                                  # None: always; 0: only near (big on screen); 1: only far
        self.vn = vn                                    # a normal per corner: smooth (Gouraud) shading, or None = flat
        self.tex, self.uv = tex, uv                     # a picture on the face (imported models): cairo surface + uv px
        self.parent, self.sub, self.edge = parent, sub, edge
        self.kind = "line" if line else kind            # poly | line | dot (a round blob) | glow (soft light)
        self.mat = mat                                  # (shine, sharpness, emission) or None
        self.walk = walk                                # people can walk on it (its upward faces)


TEXTURES = [True]          # draw imported models' pictures on their faces (False = one colour per face)
_TEXSURF = {}


def tex_surface(arr):
    """uint8 RGBA picture (numpy) -> cairo surface (cached)"""
    if arr is None:
        return None
    got = _TEXSURF.get(id(arr))
    if got is not None and got[0] is arr:
        return got[1]
    import numpy as _np
    a = _np.asarray(arr)
    if a.ndim != 3 or a.shape[2] < 3:
        return None
    h, w = a.shape[:2]
    rgba = a if a.shape[2] == 4 else _np.concatenate([a, _np.full((h, w, 1), 255, _np.uint8)], 2)
    al = rgba[:, :, 3:4].astype(_np.uint16)
    pm = (rgba[:, :, :3].astype(_np.uint16) * al // 255).astype(_np.uint8)
    bgra = _np.ascontiguousarray(_np.concatenate([pm[:, :, ::-1], rgba[:, :, 3:4]], 2))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    stride = surf.get_stride()
    view = _np.ndarray((h, stride // 4, 4), _np.uint8, buffer=surf.get_data())
    view[:, :w] = bgra
    surf.mark_dirty()
    if len(_TEXSURF) > 600:
        _TEXSURF.clear()
    _TEXSURF[id(arr)] = (arr, surf)
    return surf


def _tex_fill(ctx, f, pts, lit, spec, alpha):
    """fill the current path with the face's picture, mapped by its uv (affine), then its light and shade.
    pts = the 3 screen points. False when the face can't be mapped (then it is filled with its colour)."""
    if isinstance(ctx.get_target(), cairo.RecordingSurface):
        return False                                     # (saved pictures: plain colours - a repeating picture
    (u0, v0), (u1, v1), (u2, v2) = f.uv                 #  on an endless recording can't be played back)
    (x0, y0), (x1, y1), (x2, y2) = pts[0], pts[1], pts[2]
    if max(abs(x0), abs(y0), abs(x1), abs(y1), abs(x2), abs(y2)) > 20000.0 or \
            max(abs(u0), abs(v0), abs(u1), abs(v1), abs(u2), abs(v2)) > 1e6:
        return False                                     # (a face at the lens / broken uv: just its colour)
    du1, dv1, du2, dv2 = u1 - u0, v1 - v0, u2 - u0, v2 - v0
    det = du1 * dv2 - du2 * dv1
    if abs(det) < 1e-6:
        return False
    # texture -> screen:  [x y] = [x0 y0] + A [u-u0 v-v0]
    dx1, dy1, dx2, dy2 = x1 - x0, y1 - y0, x2 - x0, y2 - y0
    a = (dx1 * dv2 - dx2 * dv1) / det
    b = (dx2 * du1 - dx1 * du2) / det
    c = (dy1 * dv2 - dy2 * dv1) / det
    d = (dy2 * du1 - dy1 * du2) / det
    if max(abs(a), abs(b), abs(c), abs(d)) > 2000.0 or abs(a * d - b * c) < 2e-3 or \
            abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)) < 6.0:
        return False                                     # (a picture squeezed to a sliver: just its colour)
    m = cairo.Matrix(a, c, b, d, x0 - a * u0 - b * v0, y0 - c * u0 - d * v0)
    try:
        m.invert()
    except cairo.Error:
        return False
    pat = cairo.SurfacePattern(f.tex)
    pat.set_extend(cairo.EXTEND_REPEAT)
    pat.set_filter(cairo.FILTER_BILINEAR)
    pat.set_matrix(m)
    ctx.set_source(pat)
    try:
        if alpha < 0.99:
            ctx.save()
            ctx.clip_preserve()
            ctx.paint_with_alpha(alpha)
            ctx.restore()
        else:
            ctx.fill_preserve()
    except (cairo.Error, MemoryError):
        return False
    if lit < 0.995:                                      # the sun: darker on the shaded side
        ctx.set_source_rgba(0, 0, 0, min(0.85, (1.0 - lit)) * alpha)
        ctx.fill_preserve()
    elif lit > 1.005 or spec > 0.01:
        ctx.set_source_rgba(1, 1, 1, min(0.6, (lit - 1.0) * 0.8 + spec) * alpha)
        ctx.fill_preserve()
    ctx.new_path()
    return True


class Material:
    """pen.material("metal", roughness=0.3, metallic=0.9, transparency=0.0, emission=0.0) - use it as a colour."""
    __slots__ = ("c", "shine", "sharp", "emit")

    def __init__(self, c, roughness=0.5, metallic=0.0, transparency=0.0, emission=0.0):
        r, g, b, a = color(c)
        self.c = (r, g, b, a * max(0.0, min(1.0, 1.0 - float(transparency))))
        rough = max(0.02, min(1.0, float(roughness)))
        self.shine = max(0.0, min(1.0, 0.15 + 0.85 * float(metallic))) * (1.0 - 0.7 * rough)
        self.sharp = 4.0 + 60.0 * (1.0 - rough) ** 2
        self.emit = max(0.0, min(1.0, float(emission)))


MATERIALS = {                                           # ready-made looks: pen.material("glass") etc.
    "metal": dict(c="metal", roughness=0.3, metallic=0.9), "iron": dict(c="iron", roughness=0.5, metallic=0.8),
    "gold": dict(c="gold", roughness=0.25, metallic=1.0), "silver": dict(c="silver", roughness=0.2, metallic=1.0),
    "copper": dict(c="copper", roughness=0.35, metallic=0.9),
    "glass": dict(c="glass", roughness=0.05, metallic=0.3, transparency=0.55),
    "water": dict(c="water", roughness=0.1, metallic=0.3, transparency=0.25),
    "ice": dict(c="#dff4ff", roughness=0.1, metallic=0.3, transparency=0.3),
    "plastic": dict(c="red", roughness=0.35, metallic=0.2), "rubber": dict(c="#222222", roughness=0.95),
    "wood": dict(c="wood", roughness=0.8), "stone": dict(c="stone", roughness=0.95), "mud": dict(c="mud", roughness=1),
    "clay": dict(c="clay", roughness=0.85), "cloth": dict(c="cloth", roughness=1.0),
    "skin": dict(c="skin", roughness=0.7, metallic=0.05),
}


SMOOTH = [True]           # smooth shading on faces that carry corner normals (False = flat everywhere)
SMOOTH_MIN_PX = 3.0       # faces smaller than this on screen are painted flat (looks the same, much faster)


def _gouraud(ctx, xy, cols, alpha):
    """Fill the current path (a 3- or 4-corner face) with colours blended between its corners (cairo mesh).
    cols = [(r, g, b, a)] per corner. A hair-thin stroke with the same blend hides the seams (one solid colour would
    show as a grid where the corners differ)."""
    m = cairo.MeshPattern()
    m.begin_patch()
    m.move_to(*xy[0])
    for p in xy[1:]:
        m.line_to(*p)
    for i, c in enumerate(cols):
        m.set_corner_color_rgba(i, c[0], c[1], c[2], c[3] * alpha)
    m.end_patch()
    ctx.set_source(m)
    ctx.fill_preserve()
    ctx.stroke()


def _rw_wind():
    from .realworld import wind
    return wind()


class Pen3:
    """3D pen. All sizes in story units (person = 300). x right, y up, z away from the camera."""

    def __init__(self, seed=7):
        self.rand = random.Random(seed)
        self.faces = []
        self.outline = False
        self.px_unit = None             # screen pixels per unit of this drawing (set by char3d: close-ups get more detail)
        self._m = [(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)]   # rotation+scale, move
        self._stack = []
        self._things = None
        self._cur_thing = None
        self._thing_faces = {}
        self.opacity = 1.0              # 0..1 for everything drawn after it (pen.opacity = 0.5)
        self.walkable = False           # True: people walk ON the tops of what you draw next (floors, steps)
        self.doors = []                 # [x, y, z, nx, nz, w, h] of every door people can walk through
        self.detail = 1.0               # 1 = full detail; lower = fewer sides on round shapes
        self._nm = None                 # normal matrix (inverse transpose), rebuilt when the pen moves

    # ---------------------------------------------------------------- colours (same as the 2D pen)
    def color(self, c):
        return _hex(color(c))

    def dark(self, c, k=0.7):
        if isinstance(c, Material):                      # a material: the same look, a darker colour
            m = Material.__new__(Material)
            r, g, b, a = c.c
            m.c, m.shine, m.sharp, m.emit = (r * k, g * k, b * k, a), c.shine, c.sharp, c.emit
            return m
        r, g, b, a = color(c)
        return _hex((r * k, g * k, b * k, a))

    def light(self, c=None, k=0.35, *more, **kw):
        """pen.light("mud", 0.35) = a lighter colour.  pen.light(x, y, z, c, strength, radius) = a glow of light."""
        if isinstance(c, (int, float)):
            args = (c, k) + more
            return self.light_at(*args, **kw)
        r, g, b, a = color(c)
        return _hex((r + (1 - r) * k, g + (1 - g) * k, b + (1 - b) * k, a))

    def mix(self, c1, c2, k=0.5):
        a, b = color(c1), color(c2)
        return _hex(tuple(a[i] + (b[i] - a[i]) * k for i in range(4)))

    def wave(self, t, speed=1.0, size=1.0, phase=0.0):
        return size * math.sin(2 * math.pi * speed * t + phase)

    # ---------------------------------------------------------------- moving the pen
    def push(self):
        self._stack.append((self._m[0], self._m[1]))

    def pop(self):
        if self._stack:
            self._m = list(self._stack.pop())

    def move(self, x=0.0, y=0.0, z=0.0):
        self._m[1] = self._pt((x, y, z))

    def turn(self, deg):
        """Turn around the up axis (positive = the front turns to the right)."""
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        R = self._m[0]
        rot = (c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c)
        self._m[0] = _mul(R, rot)

    def tilt(self, deg):
        """Lean forward / back (around the x axis)."""
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        rot = (1.0, 0.0, 0.0, 0.0, c, -s, 0.0, s, c)
        self._m[0] = _mul(self._m[0], rot)

    def grow(self, s):
        self._m[0] = tuple(v * s for v in self._m[0])

    def _pt(self, p):
        R, T = self._m
        x, y, z = p
        return (R[0] * x + R[1] * y + R[2] * z + T[0], R[3] * x + R[4] * y + R[5] * z + T[1],
                R[6] * x + R[7] * y + R[8] * z + T[2])

    def _dir(self, n):
        R = _inv_t(self._m[0])
        x, y, z = n
        return _norm((R[0] * x + R[1] * y + R[2] * z, R[3] * x + R[4] * y + R[5] * z, R[6] * x + R[7] * y + R[8] * z))

    # ---------------------------------------------------------------- places / many objects
    def thing(self, name, z=None, depth=None, abilities=None, states=None, animated=None, height=None, kind=None,
              walkable=False, seat=None):
        """walkable=True: people walk on the tops of this thing (a stage, a jetty, steps, a bridge, a balcony).
        seat = the height people sit at on it (measured from the thing's own bottom: a throne 122, a sofa 45)."""
        return _Thing3(self, str(name), dict(z=z, depth=depth, abilities=abilities, states=states,
                                             animated=animated, height=height, kind=kind, walkable=walkable,
                                             seat=seat))

    # ---------------------------------------------------------------- faces
    def _col(self, c):
        """colour or material -> (rgba with pen.opacity, material)"""
        if isinstance(c, Material):
            r, g, b, a = c.c
            return (r, g, b, a * self.opacity), (c.shine, c.sharp, c.emit)
        r, g, b, a = color(c)
        return (r, g, b, a * self.opacity), None

    def _add(self, pts, n, c, cull=True, parent=None, sub=0, vn=None):
        col, mat = self._col(c)
        f = Face([self._pt(p) for p in pts], self._dir(n), col, cull, parent=parent, sub=sub,
                 edge=True if self.outline else None, mat=mat, walk=bool(self.walkable),
                 vn=[self._dir(v) for v in vn] if vn else None)
        self.faces.append(f)
        return f

    def _sides(self, n):
        return max(5, int(round(n * max(0.3, min(1.5, self.detail)))))

    # ---------------------------------------------------------------- materials
    def material(self, c="metal", roughness=None, metallic=None, transparency=None, emission=None):
        """A look for a surface: pen.material("gold") or pen.material("red", roughness=0.3, metallic=0.2)."""
        base = dict(MATERIALS.get(str(c).lower(), {"c": c}))
        for k, v in (("roughness", roughness), ("metallic", metallic), ("transparency", transparency),
                     ("emission", emission)):
            if v is not None:
                base[k] = v
        return Material(**base)

    # ---------------------------------------------------------------- more moving
    def rotate_y(self, deg):
        self.turn(deg)

    def rotate_x(self, deg):
        self.tilt(deg)

    def rotate_z(self, deg):
        """Roll (around the depth axis): lean left / right."""
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        self._m[0] = _mul(self._m[0], (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0))

    def roll(self, deg):
        self.rotate_z(deg)

    def scale(self, sx=1.0, sy=None, sz=None):
        sy = sx if sy is None else sy
        sz = sx if sz is None else sz
        self._m[0] = _mul(self._m[0], (sx, 0.0, 0.0, 0.0, sy, 0.0, 0.0, 0.0, sz))

    def transform(self, x=0, y=0, z=0, rx=0, ry=0, rz=0, sx=1, sy=None, sz=None):
        self.move(x, y, z)
        if ry:
            self.rotate_y(ry)
        if rx:
            self.rotate_x(rx)
        if rz:
            self.rotate_z(rz)
        self.scale(sx, sy, sz)

    def group(self, x=0, y=0, z=0, rx=0, ry=0, rz=0, s=1.0):
        """with pen.group(x, y, z, ry=30):  - everything inside moves / turns / grows together."""
        return _Group(self, (x, y, z, rx, ry, rz, s))

    def loop(self, t, duration=1.0):
        """0 .. 1 over and over (duration seconds)."""
        return (float(t) / max(1e-6, float(duration))) % 1.0

    def pingpong(self, t, duration=1.0):
        """0 .. 1 .. 0 smoothly."""
        u = self.loop(t, duration * 2.0)
        return 1.0 - abs(1.0 - 2.0 * u)

    def poly(self, pts, c="wood", two_sided=True):
        """Any flat face through 3D points [(x, y, z), ...]."""
        pts = [tuple(float(v) for v in p) for p in pts]
        if len(pts) < 3:
            return None
        n = _norm(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])))
        return self._add(pts, n, c, cull=not two_sided)

    def line(self, pts, c="ink", w=4):
        """A stick / rope / pole through 3D points (w = thickness)."""
        pts = [self._pt(tuple(float(v) for v in p)) for p in pts]
        for a, b in zip(pts, pts[1:]):
            self.faces.append(Face([a, b], (0.0, 1.0, 0.0), color(c), cull=False, line=True, w=float(w)))

    def box(self, x=0, y=0, z=0, w=100, h=100, d=100, c="wood", top=None, sides=None, front=None):
        """A solid box: (x, z) = middle of its floor, y = bottom. Returns the box (for doors / windows)."""
        x0, x1, y0, y1, z0, z1 = x - w / 2, x + w / 2, y, y + h, z - d / 2, z + d / 2
        sc = sides or c
        f = {}
        f["front"] = self._add([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1), front or c)
        f["back"] = self._add([(x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1)], (0, 0, 1), sc)
        f["left"] = self._add([(x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1)], (-1, 0, 0), sc)
        f["right"] = self._add([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], (1, 0, 0), sc)
        f["top"] = self._add([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0), top or c)
        return {"faces": f, "box": (x0, x1, y0, y1, z0, z1), "m": (self._m[0], self._m[1])}

    def roof(self, x=0, y=0, z=0, w=300, d=300, h=120, c="thatch", style="gable", over=0.0, ends=None, lines=None):
        """A roof sitting on y. style: gable (two slopes, ridge left-right), hip (four slopes),
        pyramid (to a point), flat, shed (one slope). over = how far it hangs over (units)."""
        x0, x1, z0, z1 = x - w / 2 - over, x + w / 2 + over, z - d / 2 - over, z + d / 2 + over
        y0, y1 = y, y + h
        zc, xc = (z0 + z1) / 2, (x0 + x1) / 2
        slope = max(1e-3, (z1 - z0) / 2)
        ec = ends or self.dark(c, 0.85)
        f = {}
        if style == "flat":
            return self.box(x, y, z, w + 2 * over, max(8.0, h), d + 2 * over, c)
        if style == "shed":
            f["front"] = self._add([(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)],
                                   _norm((0, (z1 - z0), -h)), c)
            f["left"] = self._add([(x0, y0, z1), (x0, y0, z0), (x0, y1, z1)], (-1, 0, 0), ec)
            f["right"] = self._add([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1)], (1, 0, 0), ec)
            f["back"] = self._add([(x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1)], (0, 0, 1), ec)
            return {"faces": f, "box": (x0, x1, y0, y1, z0, z1), "m": (self._m[0], self._m[1])}
        if style in ("pyramid", "hip"):
            inset = 0.0 if style == "pyramid" else max(0.0, (x1 - x0) / 2 - (z1 - z0) / 2)
            ra, rb = (xc - inset, y1, zc), (xc + inset, y1, zc)
            f["front"] = self._add([(x0, y0, z0), (x1, y0, z0), rb, ra], _norm((0, slope, -h)), c)
            f["back"] = self._add([(x1, y0, z1), (x0, y0, z1), ra, rb], _norm((0, slope, h)), c)
            f["left"] = self._add([(x0, y0, z1), (x0, y0, z0), ra], _norm((-h, (x1 - x0) / 2 - inset or 1, 0)), c)
            f["right"] = self._add([(x1, y0, z0), (x1, y0, z1), rb], _norm((h, (x1 - x0) / 2 - inset or 1, 0)), c)
            return {"faces": f, "box": (x0, x1, y0, y1, z0, z1), "m": (self._m[0], self._m[1])}
        # gable: ridge along x
        f["front"] = self._add([(x0, y0, z0), (x1, y0, z0), (x1, y1, zc), (x0, y1, zc)], _norm((0, slope, -h)), c)
        f["back"] = self._add([(x1, y0, z1), (x0, y0, z1), (x0, y1, zc), (x1, y1, zc)], _norm((0, slope, h)), c)
        xi0, xi1 = x - w / 2, x + w / 2                       # gable ends sit on the walls
        zi0, zi1 = z - d / 2, z + d / 2
        k = (zi1 - zi0) / max(1e-3, (z1 - z0))
        f["left"] = self._add([(xi0, y0, zi1), (xi0, y0, zi0), (xi0, y0 + h * k, zc)], (-1, 0, 0), ec)
        f["right"] = self._add([(xi1, y0, zi0), (xi1, y0, zi1), (xi1, y0 + h * k, zc)], (1, 0, 0), ec)
        if lines is None:
            lines = str(c).lower() in ("thatch", "straw", "bamboo", "grass")
        if lines:                                         # thatch / tiles: lines down the slopes
            lc = self.dark(c, 0.78)
            n = max(6, int((x1 - x0) / 38))
            for side, (za, zb), fc in (("front", (z0, zc), f["front"]), ("back", (z1, zc), f["back"])):
                sub = 1
                for i in range(n):
                    u = x0 + (x1 - x0) * (i + 0.5) / n
                    hw = max(2.0, (x1 - x0) / n * 0.09)
                    lift = 0.8 if side == "front" else 0.8
                    dz = -lift if side == "front" else lift
                    pts = [(u - hw, y0 + 2, za + dz), (u + hw, y0 + 2, za + dz), (u + hw * 0.6, y1 - 4, zb + dz),
                           (u - hw * 0.6, y1 - 4, zb + dz)]
                    face = Face([self._pt(p) for p in pts], fc.n, color(lc), True, parent=fc, sub=sub)
                    sub += 1
                    self.faces.append(face)
        f["under_f"] = self._add([(x1, y0, z0), (x0, y0, z0), (x0, y1, zc), (x1, y1, zc)],
                                 _norm((0, -slope, h)), self.dark(c, 0.6))
        f["under_b"] = self._add([(x0, y0, z1), (x1, y0, z1), (x1, y1, zc), (x0, y1, zc)],
                                 _norm((0, -slope, -h)), self.dark(c, 0.6))
        return {"faces": f, "box": (x0, x1, y0, y1, z0, z1), "m": (self._m[0], self._m[1])}

    def cylinder(self, x=0, y=0, z=0, r=50, h=100, c="wood", r2=None, sides=14, top=True, top_c=None,
                 bottom=False):
        """Upright cylinder (r2 = a different top radius: a pot, a bucket, a tree trunk)."""
        r2 = r if r2 is None else r2
        pts0 = [(x + r * math.cos(2 * math.pi * i / sides), y, z + r * math.sin(2 * math.pi * i / sides))
                for i in range(sides)]
        pts1 = [(x + r2 * math.cos(2 * math.pi * i / sides), y + h, z + r2 * math.sin(2 * math.pi * i / sides))
                for i in range(sides)]
        for i in range(sides):
            j = (i + 1) % sides
            a = 2 * math.pi * (i + 0.5) / sides
            n = _norm((math.cos(a), (r - r2) / max(h, 1e-3), math.sin(a)))
            self._add([pts0[j], pts0[i], pts1[i], pts1[j]], n, c)
        if top and r2 > 0.5:
            self._add(list(reversed(pts1)), (0, 1, 0), top_c or self.light(c, 0.1))
        if bottom and r > 0.5:
            self._add(list(pts0), (0, -1, 0), top_c or self.light(c, 0.1))

    def wheel(self, x=0, y=None, z=0, r=60, c="dark_wood", w=12, spokes=6, turn=0.0, hub="iron"):
        """A wheel standing up, facing sideways (seen round from the side of a cart / car).
        y = height of its middle (default r: touching the ground). turn = how far it rolled (radians)."""
        y = r if y is None else y
        self.push()
        self.move(x, y, z)
        self.tilt(90)                                   # axle along z
        self.cylinder(0, -w / 2, 0, r, w, c, sides=18, top=True, bottom=True, top_c=self.dark(c, 0.85))
        for k in range(spokes):
            a = turn + 2 * math.pi * k / spokes
            for sgn in (-1, 1):
                self.line([(0, sgn * (w / 2 + 1), 0), (math.cos(a) * r * 0.85, sgn * (w / 2 + 1), math.sin(a) * r * 0.85)],
                          self.light(c, 0.3), max(2.0, r / 12))
        self.cylinder(0, -w / 2 - 3, 0, r * 0.18, w + 6, hub, sides=8, top=True, bottom=True)
        self.pop()

    def cone(self, x=0, y=0, z=0, r=50, h=100, c="wood", sides=14):
        self.cylinder(x, y, z, r, h, c, r2=0.0, sides=sides, top=False)

    def sphere(self, x=0, y=0, z=0, r=50, c="stone", rings=6, sides=10, squash=1.0, bumps=0.0):
        """Ball (squash < 1 = flatter). bumps = 0.1 makes it lumpy (leaves, rocks)."""
        rnd = random.Random(int(x * 13 + y * 7 + z * 3 + r))
        grid = []
        for i in range(rings + 1):
            a = math.pi * i / rings - math.pi / 2
            row = []
            for j in range(sides):
                b = 2 * math.pi * j / sides
                k = 1.0 + (rnd.uniform(-bumps, bumps) if 0 < i < rings else 0.0)
                row.append((x + r * k * math.cos(a) * math.cos(b), y + r * squash * k * math.sin(a),
                            z + r * k * math.cos(a) * math.sin(b)))
            grid.append(row)
        for i in range(rings):
            for j in range(sides):
                jj = (j + 1) % sides
                p = [grid[i][j], grid[i][jj], grid[i + 1][jj], grid[i + 1][j]]
                cx = sum(q[0] for q in p) / 4 - x
                cy = (sum(q[1] for q in p) / 4 - y) / max(squash, 1e-3)
                cz = sum(q[2] for q in p) / 4 - z
                if i == 0:
                    p = [grid[0][0], grid[1][jj], grid[1][j]]
                elif i == rings - 1:
                    p = [grid[i][j], grid[i][jj], grid[rings][0]]
                self._add(p, _norm((cx, cy, cz)), c)

    def blob(self, x=0, y=0, z=0, r=100, c="leaf"):
        """A leafy crown / bush: a lumpy ball."""
        self.sphere(x, y, z, r, c, rings=5, sides=9, squash=0.85, bumps=0.14)

    def extrude(self, pts, z=0, d=20, c="wood", side_c=None):
        """A flat outline [(x, y), ...] (seen from the front) made thick: from depth z to z + d."""
        pts = [(float(a), float(b)) for a, b in pts]
        n = len(pts)
        if n < 3:
            return None
        area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
        if area < 0:                                       # make the outline anti-clockwise
            pts = list(reversed(pts))
        z0, z1 = z - d / 2, z + d / 2
        front = self._add([(px, py, z0) for px, py in pts], (0, 0, -1), c)
        self._add([(px, py, z1) for px, py in reversed(pts)], (0, 0, 1), c)
        sc = side_c or self.dark(c, 0.85)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            nx, ny = (b[1] - a[1]), -(b[0] - a[0])
            self._add([(a[0], a[1], z1), (b[0], b[1], z1), (b[0], b[1], z0), (a[0], a[1], z0)],
                      _norm((nx, ny, 0.0)), sc)
        return {"faces": {"front": front}, "box": None, "m": (self._m[0], self._m[1])}

    # ---------------------------------------------------------------- things painted on a side of a box
    def paint(self, box, side, pts, c="dark_wood"):
        """A flat shape painted on one side of a box: pts [(u, v), ...] measured on that side
        (u = from the middle of the side to the right, v = up from the bottom)."""
        if not box or side not in box["faces"] or not box.get("box"):
            return None
        x0, x1, y0, y1, z0, z1 = box["box"]
        e = 0.8
        if side == "front":
            P = [((x0 + x1) / 2 + u, y0 + v, z0 - e) for u, v in pts]
        elif side == "back":
            P = [((x0 + x1) / 2 - u, y0 + v, z1 + e) for u, v in pts]
        elif side == "left":
            P = [(x0 - e, y0 + v, (z0 + z1) / 2 - u) for u, v in pts]
        elif side == "right":
            P = [(x1 + e, y0 + v, (z0 + z1) / 2 + u) for u, v in pts]
        else:                                             # top: u = x, v = depth
            P = [((x0 + x1) / 2 + u, y1 + e, (z0 + z1) / 2 + v) for u, v in pts]
        parent = box["faces"][side]
        saved = self._m
        self._m = list(box["m"])
        f = Face([self._pt(p) for p in P], parent.n, color(c), True, parent=parent,
                 sub=1 + sum(1 for q in self.faces if q.parent is parent))
        self._m = saved
        self.faces.append(f)
        return f

    def door(self, box, x=0, w=52, h=125, c="dark_wood", side="front", arch=False, enter=True):
        """A door on a side of a box (125 tall = a grown-up fits). People can walk in and out through it
        ("do": "enter" / "come_out_of") unless enter=False (a painted, fake door)."""
        if enter and box and box.get("box") and side in ("front", "back", "left", "right") and h >= 100:
            x0, x1, y0, _y1, z0, z1 = box["box"]
            local = {"front": (((x0 + x1) / 2 + x, y0, z0), (0.0, 0.0, -1.0)),
                     "back": (((x0 + x1) / 2 - x, y0, z1), (0.0, 0.0, 1.0)),
                     "left": ((x0, y0, (z0 + z1) / 2 - x), (-1.0, 0.0, 0.0)),
                     "right": ((x1, y0, (z0 + z1) / 2 + x), (1.0, 0.0, 0.0))}[side]
            saved = self._m
            self._m = list(box["m"])
            p = self._pt(local[0])
            q = self._pt((local[0][0] + local[1][0], local[0][1], local[0][2] + local[1][2]))
            u_ = self._pt((local[0][0], local[0][1] + 1.0, local[0][2]))
            self._m = saved
            nx, nz = q[0] - p[0], q[2] - p[2]
            L = math.hypot(nx, nz) or 1.0
            kk = math.dist(u_, p) or 1.0                  # a grown drawing (the clay home): its door is bigger too
            self.doors.append([round(p[0], 1), round(p[1], 1), round(p[2], 1), round(nx / L, 3), round(nz / L, 3),
                               round(w * kk, 1), round(h * kk, 1)])
        if arch:
            pts = [(x - w / 2, 0), (x + w / 2, 0), (x + w / 2, h - w / 2)]
            pts += [(x + w / 2 * math.cos(a), h - w / 2 + w / 2 * math.sin(a))
                    for a in [math.pi * k / 8 for k in range(1, 8)]]
            pts += [(x - w / 2, h - w / 2)]
        else:
            pts = [(x - w / 2, 0), (x + w / 2, 0), (x + w / 2, h), (x - w / 2, h)]
        return self.paint(box, side, pts, c)

    def window(self, box, x=0, y=100, w=50, h=50, c="dark_wood", side="front", glow=None):
        return self.paint(box, side, [(x - w / 2, y), (x + w / 2, y), (x + w / 2, y + h), (x - w / 2, y + h)],
                          glow or c)

    def stripe(self, box, side, y, h, c="dark_wood"):
        """A band all along one side (a plinth, a painted border)."""
        if not box or not box.get("box"):
            return None
        x0, x1, _y0, _y1, z0, z1 = box["box"]
        half = ((x1 - x0) if side in ("front", "back") else (z1 - z0)) / 2
        return self.paint(box, side, [(-half, y), (half, y), (half, y + h), (-half, y + h)], c)

    # ---------------------------------------------------------------- ready-made
    def tree(self, x=0, z=0, h=600, crown="leaf", trunk="wood", r=None):
        """A simple round tree: trunk + leafy crown (h = full height)."""
        r = r or h * 0.28
        self.cylinder(x, 0, z, h * 0.045, h - r * 1.2, trunk, r2=h * 0.03, sides=8)
        self.blob(x, h - r, z, r, crown)

    def fence(self, x0, x1, z=0, h=90, c="wood", gap=45):
        n = max(2, int(abs(x1 - x0) / gap) + 1)
        for i in range(n):
            px = x0 + (x1 - x0) * i / (n - 1)
            self.box(px, 0, z, 10, h, 10, c)
        for yy in (h * 0.35, h * 0.75):
            self.box((x0 + x1) / 2, yy, z, abs(x1 - x0), 7, 6, self.dark(c, 0.9))

    # ================================================================= more solid shapes
    def _solid(self, grid, c, center, closed=True):
        """Faces from a grid of points (rows x cols, cols wrap around). Normals point away from center."""
        rows, cols = len(grid), len(grid[0])
        for i in range(rows - 1):
            for j in range(cols):
                jj = (j + 1) % cols
                p = [grid[i][j], grid[i][jj], grid[i + 1][jj], grid[i + 1][j]]
                q = []
                for v in p:
                    if not q or max(abs(v[0] - q[-1][0]), abs(v[1] - q[-1][1]), abs(v[2] - q[-1][2])) > 1e-6:
                        q.append(v)
                if len(q) > 1 and max(abs(q[0][k] - q[-1][k]) for k in range(3)) < 1e-6:
                    q.pop()
                if len(q) < 3:
                    continue
                self._face_auto(q, c, center)

    def _face_auto(self, pts, c, center=None, cull=True):
        n = _norm(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])))
        if n == (0.0, 0.0, 0.0) and len(pts) > 3:
            n = _norm(_cross(_sub(pts[2], pts[0]), _sub(pts[3], pts[0])))
        if center is not None:
            cx = sum(p[0] for p in pts) / len(pts) - center[0]
            cy = sum(p[1] for p in pts) / len(pts) - center[1]
            cz = sum(p[2] for p in pts) / len(pts) - center[2]
            if n[0] * cx + n[1] * cy + n[2] * cz < 0:
                n = (-n[0], -n[1], -n[2])
        return self._add(pts, n, c, cull=cull)

    def smooth_grid(self, grid, c, center, closed=True, normals=None):
        """Like _solid, but every corner gets a normal (the average of the faces round it, or normals[i][j]
        when given), so the light changes softly across the surface (faces, heads, eyeballs)."""
        rows, cols = len(grid), len(grid[0])
        if normals is None:
            acc = [[[0.0, 0.0, 0.0] for _ in range(cols)] for _ in range(rows)]
            for i in range(rows - 1):
                for j in range(cols if closed else cols - 1):
                    jj = (j + 1) % cols
                    a, b, d = grid[i][j], grid[i][jj], grid[i + 1][j]
                    n = _cross(_sub(b, a), _sub(d, a))
                    if n == (0.0, 0.0, 0.0):
                        n = _cross(_sub(grid[i + 1][jj], a), _sub(d, a))
                    for (ii, kk) in ((i, j), (i, jj), (i + 1, j), (i + 1, jj)):
                        acc[ii][kk][0] += n[0]
                        acc[ii][kk][1] += n[1]
                        acc[ii][kk][2] += n[2]
            normals = []
            for i in range(rows):
                row = []
                for j in range(cols):
                    v = _norm(tuple(acc[i][j]))
                    p = grid[i][j]
                    if _dot(v, _sub(p, center)) < 0:
                        v = (-v[0], -v[1], -v[2])
                    if v == (0.0, 0.0, 0.0):
                        v = _norm(_sub(p, center))
                    row.append(v)
                normals.append(row)
        for i in range(rows - 1):
            for j in range(cols if closed else cols - 1):
                jj = (j + 1) % cols
                idx = [(i, j), (i, jj), (i + 1, jj), (i + 1, j)]
                pts, ns = [], []
                for (ii, kk) in idx:
                    v = grid[ii][kk]
                    if pts and max(abs(v[0] - pts[-1][0]), abs(v[1] - pts[-1][1]), abs(v[2] - pts[-1][2])) < 1e-6:
                        continue
                    pts.append(v)
                    ns.append(normals[ii][kk])
                if len(pts) > 1 and max(abs(pts[0][k] - pts[-1][k]) for k in range(3)) < 1e-6:
                    pts.pop()
                    ns.pop()
                if len(pts) < 3:
                    continue
                n = _norm(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])))
                if n == (0.0, 0.0, 0.0) and len(pts) > 3:
                    n = _norm(_cross(_sub(pts[2], pts[0]), _sub(pts[3], pts[0])))
                cx = sum(p[0] for p in pts) / len(pts) - center[0]
                cy = sum(p[1] for p in pts) / len(pts) - center[1]
                cz = sum(p[2] for p in pts) / len(pts) - center[2]
                if n[0] * cx + n[1] * cy + n[2] * cz < 0:
                    n = (-n[0], -n[1], -n[2])
                self._add(pts, n, c, vn=ns)

    def smooth_ellipsoid(self, x=0, y=0, z=0, rx=50, ry=50, rz=50, c="skin", rings=8, sides=14):
        """An ellipsoid with smooth shading (true normals of the ellipsoid at every corner)."""
        rings, sides = self._sides(rings), self._sides(sides)
        grid, nrm = [], []
        for i in range(rings + 1):
            a = math.pi * i / rings - math.pi / 2
            row, nr = [], []
            for j in range(sides):
                b = 2 * math.pi * j / sides
                ux, uy, uz = math.cos(a) * math.cos(b), math.sin(a), math.cos(a) * math.sin(b)
                row.append((x + rx * ux, y + ry * uy, z + rz * uz))
                nr.append(_norm((ux / max(rx, 1e-6), uy / max(ry, 1e-6), uz / max(rz, 1e-6))))
            grid.append(row)
            nrm.append(nr)
        self.smooth_grid(grid, c, (x, y, z), normals=nrm)

    def ellipsoid(self, x=0, y=0, z=0, rx=50, ry=50, rz=50, c="stone", rings=8, sides=14):
        """A stretched ball (x, y, z = its middle)."""
        rings, sides = self._sides(rings), self._sides(sides)
        grid = []
        for i in range(rings + 1):
            a = math.pi * i / rings - math.pi / 2
            grid.append([(x + rx * math.cos(a) * math.cos(2 * math.pi * j / sides), y + ry * math.sin(a),
                          z + rz * math.cos(a) * math.sin(2 * math.pi * j / sides)) for j in range(sides)])
        self._solid(grid, c, (x, y, z))

    def round_box(self, x=0, y=0, z=0, w=100, h=100, d=100, c="wood", r=20):
        """A box with rounded edges and corners (car bodies, cushions, bread). Stands on y like box()."""
        e = max(0.08, min(1.0, 1.1 * float(r) / max(1.0, min(w, h, d))))   # 1 = ball, small = sharp box
        rings, sides = self._sides(10), self._sides(20)
        cy = y + h / 2

        def sp(v, k):
            return math.copysign(abs(v) ** k, v)
        grid = []
        for i in range(rings + 1):
            a = math.pi * i / rings - math.pi / 2
            row = []
            for j in range(sides):
                b = 2 * math.pi * j / sides
                row.append((x + w / 2 * sp(math.cos(a), e) * sp(math.cos(b), e), cy + h / 2 * sp(math.sin(a), e),
                            z + d / 2 * sp(math.cos(a), e) * sp(math.sin(b), e)))
            grid.append(row)
        self._solid(grid, c, (x, cy, z))
        return {"faces": {}, "box": (x - w / 2, x + w / 2, y, y + h, z - d / 2, z + d / 2),
                "m": (self._m[0], self._m[1])}

    def capsule(self, x=0, y=0, z=0, r=30, h=120, c="skin", axis="y", sides=12):
        """A pill shape: a cylinder with round ends (h = full length). axis y (standing), x or z (lying)."""
        self.push()
        self.move(x, y, z)
        if axis == "x":
            self.rotate_z(-90)
        elif axis == "z":
            self.rotate_x(90)
        sides = self._sides(sides)
        h = max(h, 2 * r)
        grid = []
        half = max(2, sides // 3)
        for i in range(half + 1):                          # bottom half-ball
            a = -math.pi / 2 + (math.pi / 2) * i / half
            grid.append([(r * math.cos(a) * math.cos(2 * math.pi * j / sides), r + r * math.sin(a),
                          r * math.cos(a) * math.sin(2 * math.pi * j / sides)) for j in range(sides)])
        for i in range(half + 1):                          # top half-ball
            a = (math.pi / 2) * i / half
            grid.append([(r * math.cos(a) * math.cos(2 * math.pi * j / sides), h - r + r * math.sin(a),
                          r * math.cos(a) * math.sin(2 * math.pi * j / sides)) for j in range(sides)])
        self._solid(grid, c, (0.0, h / 2, 0.0))
        self.pop()

    def lathe(self, profile, c="clay", x=0, y=0, z=0, sides=16):
        """Spin an outline around the up axis: profile = [(radius, height), ...] from the bottom up.
        Pots, vases, domes, pillars, bottles, lamps, bells."""
        sides = self._sides(sides)
        grid = [[(x + r * math.cos(2 * math.pi * j / sides), y + yy, z + r * math.sin(2 * math.pi * j / sides))
                 for j in range(sides)] for r, yy in profile]
        cy = y + sum(p[1] for p in profile) / max(1, len(profile))
        self._solid(grid, c, (x, cy, z))
        top_r, top_y = profile[-1]
        if top_r > 0.5:                                    # an open top shows the dark inside
            self._add([(x + top_r * math.cos(2 * math.pi * j / sides), y + top_y - 0.5,
                        z + top_r * math.sin(2 * math.pi * j / sides)) for j in range(sides)][::-1],
                      (0, 1, 0), self.dark(c if not isinstance(c, Material) else "#555555", 0.45))

    def pot(self, x=0, y=0, z=0, r=40, c="clay", h=None):
        """A round clay pot (matka) with a neck and a rim."""
        h = h or r * 1.6
        prof = [(r * 0.45, 0), (r * 0.85, h * 0.12), (r, h * 0.38), (r * 0.9, h * 0.62), (r * 0.55, h * 0.82),
                (r * 0.45, h * 0.9), (r * 0.55, h * 0.97), (r * 0.5, h)]
        self.lathe(prof, c, x, y, z)

    def cylinder_axis(self, x, y, z, r, h, c, axis="x", **kw):
        """A cylinder lying along x or z (axles, logs, pipes, rolling pins)."""
        self.push()
        self.move(x, y, z)
        if axis == "x":
            self.rotate_z(-90)
        elif axis == "z":
            self.rotate_x(90)
        self.cylinder(0, -h / 2 if axis != "y" else 0, 0, r, h, c, bottom=True, **kw)
        self.pop()

    def log(self, x=0, y=None, z=0, r=25, length=200, c="wood", axis="x"):
        """A fallen log lying on the ground."""
        self.cylinder_axis(x, r if y is None else y, z, r, length, c, axis=axis, top_c=self.light(c, 0.3))

    def tube(self, points, radius=10, c="wood", sides=8, smooth=True, ends=True):
        """A round tube along a 3D path [(x, y, z), ...]: pipes, branches, horns, tails, handles, cables."""
        pts = _smooth([tuple(float(v) for v in p) for p in points]) if smooth else \
            [tuple(float(v) for v in p) for p in points]
        if len(pts) < 2:
            return
        sides = self._sides(sides)
        rad = radius if isinstance(radius, (list, tuple)) else [radius] * len(pts)
        if len(rad) != len(pts):
            rad = [rad[min(len(rad) - 1, int(i * len(rad) / len(pts)))] for i in range(len(pts))]
        up = (0.0, 1.0, 0.0)
        rings = []
        for i, p in enumerate(pts):
            a = pts[max(0, i - 1)]
            b = pts[min(len(pts) - 1, i + 1)]
            tdir = _norm(_sub(b, a))
            if abs(_dot(tdir, up)) > 0.95:
                up = (1.0, 0.0, 0.0)
            u = _norm(_cross(tdir, up))
            v = _norm(_cross(u, tdir))
            up = v
            rr = rad[i]
            rings.append([(p[0] + rr * (math.cos(2 * math.pi * j / sides) * u[0] + math.sin(2 * math.pi * j / sides) * v[0]),
                           p[1] + rr * (math.cos(2 * math.pi * j / sides) * u[1] + math.sin(2 * math.pi * j / sides) * v[1]),
                           p[2] + rr * (math.cos(2 * math.pi * j / sides) * u[2] + math.sin(2 * math.pi * j / sides) * v[2]))
                          for j in range(sides)])
        for i in range(len(rings) - 1):
            ci = pts[i]
            for j in range(sides):
                jj = (j + 1) % sides
                self._face_auto([rings[i][j], rings[i][jj], rings[i + 1][jj], rings[i + 1][j]], c,
                                ((ci[0] + pts[i + 1][0]) / 2, (ci[1] + pts[i + 1][1]) / 2, (ci[2] + pts[i + 1][2]) / 2))
        if ends:                                        # caps: their normal points away from the tube
            for ring, other in ((rings[0], pts[1]), (rings[-1], pts[-2])):
                self._face_auto(ring, c, other)

    def rope(self, points, radius=4, c="rope", sag=0.0):
        """A rope / cable (sag = how much it hangs down between the ends)."""
        pts = [tuple(float(v) for v in p) for p in points]
        if sag and len(pts) == 2:
            a, b = pts
            pts = [(a[0] + (b[0] - a[0]) * k / 8, a[1] + (b[1] - a[1]) * k / 8 - sag * math.sin(math.pi * k / 8),
                    a[2] + (b[2] - a[2]) * k / 8) for k in range(9)]
        self.tube(pts, radius, c, sides=6, ends=False)

    def curve3d(self, points, c="ink", w=4):
        """A smooth 3D line (thin: grass blades, whiskers, strings)."""
        self.line(_smooth([tuple(float(v) for v in p) for p in points]), c, w)

    def mesh(self, vertices, faces, c="metal", two_sided=True):
        """Your own shape: vertices [(x, y, z), ...], faces [(0, 1, 2), (0, 2, 3), ...] (any size).
        c = one colour, or a list with one colour per face."""
        V = [tuple(float(v) for v in p) for p in vertices]
        cols = c if isinstance(c, (list, tuple)) and c and not isinstance(c[0], (int, float)) else None
        cx = sum(p[0] for p in V) / max(1, len(V))
        cy = sum(p[1] for p in V) / max(1, len(V))
        cz = sum(p[2] for p in V) / max(1, len(V))
        for i, f in enumerate(faces):
            pts = [V[k] for k in f if 0 <= k < len(V)]
            if len(pts) >= 3:
                self._face_auto(pts, cols[i % len(cols)] if cols else c, (cx, cy, cz), cull=not two_sided)

    def surface(self, grid, c="grass", two_sided=True):
        """A bendy sheet from rows of points [[(x, y, z), ...], ...] (cloth, a hammock, a curved roof)."""
        for i in range(len(grid) - 1):
            for j in range(min(len(grid[i]), len(grid[i + 1])) - 1):
                p = [grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]]
                n = _norm(_cross(_sub(p[1], p[0]), _sub(p[3], p[0])))
                if n[1] < 0:
                    n = (-n[0], -n[1], -n[2])
                self._add(p, n, c, cull=not two_sided)

    def trunk(self, x=0, y=0, z=0, w=40, h=300, c="wood", lean=0.0):
        """A tree trunk that gets thinner toward the top (lean = degrees)."""
        self.push()
        self.move(x, y, z)
        if lean:
            self.rotate_z(-lean)
        self.cylinder(0, 0, 0, w / 2, h, c, r2=w * 0.32, sides=9)
        self.pop()

    def leaves(self, x=0, y=0, z=0, r=100, c="leaf"):
        """A cluster of leaves (a few lumpy balls)."""
        rnd = random.Random(int(x * 3 + y * 5 + z * 7 + r))
        self.blob(x, y, z, r * 0.8, c)
        for k in range(4):
            a = 2 * math.pi * k / 4 + rnd.uniform(-0.4, 0.4)
            self.blob(x + math.cos(a) * r * 0.55, y + rnd.uniform(-0.25, 0.2) * r, z + math.sin(a) * r * 0.5,
                      r * rnd.uniform(0.45, 0.6), self.dark(c, rnd.uniform(0.85, 1.0)))

    def planks(self, x=0, y=0, z=0, w=200, h=150, d=12, c="wood", n=5, across=False, gap=3):
        """A wall / floor of separate wooden boards."""
        for i in range(n):
            if across:
                bh = (h - gap * (n - 1)) / n
                self.box(x, y + i * (bh + gap), z, w, bh, d, self.dark(c, 1.0 - 0.06 * (i % 2)))
            else:
                bw = (w - gap * (n - 1)) / n
                self.box(x - w / 2 + bw / 2 + i * (bw + gap), y, z, bw, h, d, self.dark(c, 1.0 - 0.06 * (i % 2)))

    def bricks(self, x=0, y=0, z=0, w=300, h=200, d=30, c="brick", bw=34, bh=16):
        """A brick wall (mortar lines on its faces)."""
        b = self.box(x, y, z, w, h, d, c)
        mort = self.light(c, 0.35)
        rows = max(1, int(h / bh))
        for side, width in (("front", w), ("back", w), ("left", d), ("right", d)):
            for i in range(1, rows):
                v = i * h / rows
                self.paint(b, side, [(-width / 2, v - 1), (width / 2, v - 1), (width / 2, v + 1), (-width / 2, v + 1)],
                           mort)
            if side in ("front", "back"):
                for i in range(rows):
                    off = bw / 2 if i % 2 else 0.0
                    u = -width / 2 + off + bw
                    while u < width / 2 - 2:
                        self.paint(b, side, [(u - 1, i * h / rows), (u + 1, i * h / rows), (u + 1, (i + 1) * h / rows),
                                             (u - 1, (i + 1) * h / rows)], mort)
                        u += bw
        return b

    def stairs(self, x=0, y=0, z=0, w=200, h=150, d=240, steps=6, c="stone"):
        """Steps going up and away from the camera (people can walk up them)."""
        sh, sd = h / steps, d / steps
        old, self.walkable = self.walkable, True
        for i in range(steps):
            self.box(x, y, z - d / 2 + sd * (i + 0.5) + sd * (steps - i - 1) / 2, w, sh * (i + 1),
                     sd * (steps - i), self.dark(c, 1.0 - 0.03 * i))
        self.walkable = old

    def platform(self, x=0, y=0, z=0, w=300, h=40, d=200, c="wood", boards=True):
        """A floor people can stand and walk on (a stage, a jetty, a chabutra, a bridge deck)."""
        old, self.walkable = self.walkable, True
        b = self.box(x, y, z, w, h, d, c)
        self.walkable = old
        if boards:
            n = max(2, int(w / 40))
            for i in range(1, n):
                u = -w / 2 + w * i / n
                self.paint(b, "top", [(u - 1, -d / 2), (u + 1, -d / 2), (u + 1, d / 2), (u - 1, d / 2)], self.dark(c, 0.7))
        return b

    def bridge(self, x0, x1, z=0, w=160, y=60, c="wood", rails=True, arch=40):
        """A wooden foot bridge from x0 to x1 at depth z (people walk across it)."""
        n = max(4, int(abs(x1 - x0) / 45))
        old, self.walkable = self.walkable, True
        for i in range(n):
            u = (i + 0.5) / n
            hy = y + arch * math.sin(math.pi * u)
            self.box(x0 + (x1 - x0) * u, hy, z, abs(x1 - x0) / n - 3, 10, w, self.dark(c, 1.0 - 0.05 * (i % 2)))
        self.walkable = old
        for side in (-1, 1):
            for i in range(n + 1):
                u = i / n
                self.box(x0 + (x1 - x0) * u, 0, z + side * w / 2, 10, y + arch * math.sin(math.pi * u) + 10, 10,
                         self.dark(c, 0.8))
            if rails:
                pts = [(x0 + (x1 - x0) * i / n, y + arch * math.sin(math.pi * i / n) + 70, z + side * w / 2)
                       for i in range(n + 1)]
                self.tube(pts, 4, self.dark(c, 0.75), sides=5, ends=False)
                for q in pts:
                    self.box(q[0], q[1] - 60, q[2], 6, 60, 6, self.dark(c, 0.75))

    # ---------------------------------------------------------------- light, fire, particles
    def glow(self, x=0, y=0, z=0, r=80, c="flame", strength=0.5):
        """A soft glow of light (around a lamp, a fire, a magic stone)."""
        r_, g_, b_, _a = color(c)
        self.faces.append(Face([self._pt((x, y, z))], (0.0, 0.0, -1.0), (r_, g_, b_, max(0.0, min(1.0, strength))),
                               cull=False, w=float(r) * _scale_of(self._m[0]), kind="glow"))

    def light_at(self, x=0, y=0, z=0, c="flame", strength=0.6, radius=150):
        """A light you can see (a glow). The sun lights everything else by itself."""
        self.glow(x, y, z, radius, c, strength)

    point_light = light_at

    def dot(self, x=0, y=0, z=0, r=5, c="white"):
        col, _m = self._col(c)
        self.faces.append(Face([self._pt((x, y, z))], (0.0, 0.0, -1.0), col, cull=False,
                               w=float(r) * _scale_of(self._m[0]), kind="dot"))

    def flame(self, x=0, y=0, z=0, h=60, t=0.0, c="fire"):
        """A flickering 3D flame (seen from every side) with a glow."""
        f = 1 + 0.14 * math.sin(t * 13 + x) + 0.07 * math.sin(t * 29 + z)
        sway = h * 0.08 * math.sin(t * 9 + x * 0.1)
        w = h * 0.4
        hot = self.material(c, emission=1.0, roughness=1.0)
        core = self.material("flame", emission=1.0, roughness=1.0)
        for turn in (0, 60, 120):
            self.push()
            self.move(x, y, z)
            self.turn(turn)
            outline = [(-w, 0.1 * h), (-w * 0.5, 0.55 * h * f), (sway, h * f), (w * 0.55, 0.5 * h * f), (w, 0.1 * h),
                       (0, 0)]
            self.poly([(px, py, 0.0) for px, py in outline], hot)
            inner = [(-w * 0.45, 0.1 * h), (sway * 0.6, 0.62 * h * f), (w * 0.45, 0.1 * h), (0, 0.02 * h)]
            self.poly([(px, py, -0.5) for px, py in inner], core)
            self.pop()
        self.glow(x, y + h * 0.4, z, h * 1.4, "flame", 0.35)

    def fire(self, x=0, y=0, z=0, amount=3, t=0.0, size=60):
        """A small fire: flames + sparks."""
        rnd = random.Random(int(x + z * 3))
        for k in range(max(1, int(amount))):
            self.flame(x + rnd.uniform(-0.3, 0.3) * size, y, z + rnd.uniform(-0.3, 0.3) * size,
                       size * rnd.uniform(0.7, 1.1), t + k * 0.37)
        self.sparks(x, y + size * 0.6, z, amount * 3, 3, t)

    def particles(self, x=0, y=0, z=0, count=20, c="white", size=5, speed=40, t=0.0, spread=60, rise=1.0,
                  life=2.0, fade=True, grow=0.0):
        """Little floating dots (dust, sparks, bubbles, fireflies). Always the same for the same t."""
        rnd = random.Random(int(x * 7 + y * 3 + z * 11 + count))
        r0, g0, b0, a0 = color(c)
        for i in range(int(count)):
            ph = rnd.random() * life
            age = (float(t) + ph) % life
            k = age / life
            px = x + rnd.uniform(-1, 1) * spread * (0.3 + k) + _rw_wind().speed(t) * 0.3 * age   # carried by the wind
            pz = z + rnd.uniform(-1, 1) * spread * 0.5
            py = y + rise * speed * age + rnd.uniform(-1, 1) * spread * 0.2
            a = a0 * ((1.0 - k) if fade else 1.0) * self.opacity
            self.faces.append(Face([self._pt((px, py, pz))], (0.0, 0.0, -1.0), (r0, g0, b0, a), cull=False,
                                   w=float(size) * (1.0 + grow * k) * _scale_of(self._m[0]), kind="dot"))

    def smoke(self, x=0, y=0, z=0, amount=8, size=20, t=0.0):
        self.particles(x, y, z, amount, "#9a9a9aaa", size, 45, t, spread=20, life=3.0, grow=2.0)

    def dust(self, x=0, y=0, z=0, amount=12, size=8, t=0.0):
        self.particles(x, y, z, amount, "#c9a978aa", size, 15, t, spread=80, rise=0.5, life=2.0, grow=1.0)

    def sparks(self, x=0, y=0, z=0, amount=10, size=3, t=0.0):
        self.particles(x, y, z, amount, "#ffd23f", size, 90, t, spread=25, life=1.0)

    def rain(self, x=0, y=0, z=0, amount=60, speed=900, t=0.0, area=600, top=700):
        """Rain falling in a box of ground `area` wide, from `top` down."""
        rnd = random.Random(int(x + z + amount))
        for i in range(int(amount)):
            px, pz = x + rnd.uniform(-area / 2, area / 2), z + rnd.uniform(-area / 2, area / 2)
            py = y + top - ((float(t) * speed + rnd.random() * top) % top)
            sl = _rw_wind().speed(t) / max(1.0, speed)        # slanted by the wind
            self.line([(px + sl * (y + top - py), py, pz), (px + sl * (y + top - py) - 28 * sl, py + 28, pz)],
                      "#bfd9ffaa", 2)

    def snow(self, x=0, y=0, z=0, amount=60, speed=80, t=0.0, area=600, top=700):
        rnd = random.Random(int(x + z + amount))
        for i in range(int(amount)):
            px, pz = x + rnd.uniform(-area / 2, area / 2), z + rnd.uniform(-area / 2, area / 2)
            py = y + top - ((float(t) * speed + rnd.random() * top) % top)
            self.dot(px + 10 * math.sin(t * 2 + i), py, pz, 4, "white")

    # ---------------------------------------------------------------- ground things
    def ground(self, w=1000, d=1000, c="grass", x=0, z=0, y=0.5):
        """A flat patch of ground (w wide, d deep)."""
        if y > 5:
            old, self.walkable = self.walkable, True
            self._add([(x - w / 2, y, z - d / 2), (x + w / 2, y, z - d / 2), (x + w / 2, y, z + d / 2),
                       (x - w / 2, y, z + d / 2)], (0, 1, 0), c)
            self.walkable = old
            return
        self._add([(x - w / 2, y, z - d / 2), (x + w / 2, y, z - d / 2), (x + w / 2, y, z + d / 2),
                   (x - w / 2, y, z + d / 2)], (0, 1, 0), c)

    def water(self, w=600, d=400, c="water", x=0, z=0, y=1.0, t=0.0):
        """A flat pool of water with a few ripples."""
        self.ground(w, d, self.material(c, roughness=0.1, metallic=0.4), x, z, y)
        rnd = random.Random(int(w + d))
        for i in range(5):
            cx, cz = x + rnd.uniform(-0.35, 0.35) * w, z + rnd.uniform(-0.35, 0.35) * d
            rr = 20 + 10 * ((t * 0.5 + i * 0.2) % 1.0)
            self.line([(cx - rr, y + 0.5, cz), (cx + rr, y + 0.5, cz)], "#ffffff88", 2)

    def ribbon(self, points, width=100, c="road", y=0.8, smooth=True):
        """A flat band on the ground along points [(x, z), ...] (roads, rivers, paths)."""
        pts = [(float(p[0]), float(p[-1])) for p in points]
        if smooth:
            pts = [(p[0], p[2]) for p in _smooth([(a, 0.0, b) for a, b in pts])]
        L, R = [], []
        for i, p in enumerate(pts):
            a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dz) or 1.0
            nx, nz = -dz / ln, dx / ln
            L.append((p[0] + nx * width / 2, y, p[1] + nz * width / 2))
            R.append((p[0] - nx * width / 2, y, p[1] - nz * width / 2))
        for i in range(len(pts) - 1):
            self._add([L[i], R[i], R[i + 1], L[i + 1]], (0, 1, 0), c, cull=False)

    def road(self, points, width=220, c="#55595f", lines=True):
        self.ribbon(points, width, c)
        if lines:
            pts = _smooth([(float(p[0]), 0.0, float(p[-1])) for p in points])
            for i in range(0, len(pts) - 1, 2):
                self.line([(pts[i][0], 1.4, pts[i][2]), (pts[i + 1][0], 1.4, pts[i + 1][2])], "#f5e27a", 5)

    def river(self, points, width=300, c="water"):
        self.ribbon(points, width, self.material(c, roughness=0.15, metallic=0.4), y=0.6)

    def terrain(self, heights, cell=100, c="grass", x=0, z=0):
        """Hilly ground from a grid of heights (rows go away from the camera)."""
        rows, cols = len(heights), len(heights[0])
        grid = [[(x + (j - (cols - 1) / 2) * cell, float(heights[i][j]), z + (i - (rows - 1) / 2) * cell)
                 for j in range(cols)] for i in range(rows)]
        old, self.walkable = self.walkable, True
        self.surface(grid, c, two_sided=False)
        self.walkable = old

    def hill(self, x=0, z=0, w=900, d=700, h=260, c="grass", rock="#8d8173", rocky=0.25, path=True,
             path_c="#c9a36b", steps=False, flat_top=0.35, seed=None, bushes=6):
        """A real hill people WALK up (not a pointed pyramid): a smooth round slope with a flattish top, grass
        that gets darker down the sides, rocky patches (rocky 0..1: 1 = a rocky hill / cliff), a footpath that
        winds up to the top on the front (path=True; steps=True cuts stone steps into it) and a few bushes.
        Gentle slopes are walkable everywhere; on a steep hill people use the path. Stand things ON it with
        pen.hill_y(x, z, ...) (same numbers) - a temple on the top, a tree on the side."""
        rnd = random.Random(int(x * 7 + z * 13 + h * 3) if seed is None else seed)
        nx, nz = 26, 20
        bumps = [(rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0.04, 0.09)) for _ in range(4)]

        def hy(u, v):
            r = math.hypot(u, v)
            if r >= 1.0:
                return 0.0
            k = 1.0 if r < flat_top else math.cos(math.pi / 2 * (r - flat_top) / (1.0 - flat_top)) ** 2
            b = sum(a * math.exp(-((u - bu) ** 2 + (v - bv) ** 2) * 9) for bu, bv, a in bumps)
            return h * (k + b * k)
        grid = [[(x + (j / (nx - 1) - 0.5) * w * 1.04, 0.0, z + (i / (nz - 1) - 0.5) * d * 1.04)
                 for j in range(nx)] for i in range(nz)]
        grid = [[(p[0], hy((p[0] - x) / (w / 2), (p[2] - z) / (d / 2)), p[2]) for p in row] for row in grid]
        dark_c = self.dark(c, 0.78)
        old, self.walkable = self.walkable, True
        for i in range(nz - 1):
            for j in range(nx - 1):
                q = [grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]]
                ym = sum(p[1] for p in q) / 4.0
                if ym < 1.0:
                    continue                                   # flat ground outside: the place's own ground
                n = _norm(_cross(_sub(q[1], q[0]), _sub(q[3], q[0])))
                if n[1] < 0:
                    n = (-n[0], -n[1], -n[2])
                steep = 1.0 - n[1]
                k = ym / max(1.0, h)
                col = self.mix(dark_c, c, min(1.0, 0.35 + 0.8 * k))
                col = self.mix(col, self.light(c, 0.12) if rnd.random() < 0.5 else self.dark(c, 0.9), rnd.random() * 0.3)
                if steep > 0.25 and rnd.random() < rocky * (0.3 + 2.5 * steep):     # bare rock on the steep parts
                    col = self.mix(rock, self.dark(rock, 0.8), rnd.random())
                self._add(q, n, col, cull=False)
        self.walkable = old
        self._hill_last = (x, z, w, d, hy)
        # ---- a footpath winding up the front to the top
        if path:
            def H(px_, pz_):
                return hy((px_ - x) / (w / 2), (pz_ - z) / (d / 2))
            # a real switchback path: from the front foot it climbs across the slope as steeply as a person can
            # walk (about 23 degrees), turns back at the sides, and ends on the top
            L = max(24.0, min(w, d) / 30.0)
            px, pz, sgn = x, z - d / 2 * 0.99, 1.0
            pts = [(px, H(px, pz) + 2.0, pz)]
            for _ in range(500):
                u, v = (px - x) / (w / 2), (pz - z) / (d / 2)
                if math.hypot(u, v) < flat_top * 0.8:
                    break
                rx, rz = -(px - x) / (w / 2) ** 2, -(pz - z) / (d / 2) ** 2        # toward the top
                rl = math.hypot(rx, rz) or 1.0
                rx, rz = rx / rl, rz / rl
                tx, tz = -rz * sgn, rx * sgn                                       # across the slope
                if (u > 0.55 and tx > 0) or (u < -0.55 and tx < 0):                # the side: turn back
                    sgn = -sgn
                    tx, tz = -tx, -tz
                nxt = None
                for k in range(10, -1, -1):                                        # as far up as it can go
                    a = k / 10.0 * math.pi / 2
                    qx, qz = px + (tx * math.cos(a) + rx * math.sin(a)) * L, pz + (tz * math.cos(a) + rz * math.sin(a)) * L
                    if H(qx, qz) - H(px, pz) <= 0.42 * L:
                        nxt = (qx, qz)
                        break
                px, pz = nxt if nxt else (px + tx * L, pz + tz * L)
                pts.append((px, H(px, pz) + 2.0, pz))
            pw = max(40.0, w * 0.06) / 2
            old_w, self.walkable = self.walkable, True        # the path is the gentle way up: people walk it
            for a, b in zip(pts, pts[1:]):                     # a strip lying ON the slope
                dx, dz = b[0] - a[0], b[2] - a[2]
                ln = math.hypot(dx, dz) or 1.0
                ox, oz = -dz / ln * pw, dx / ln * pw
                q = [(a[0] + ox, a[1], a[2] + oz), (b[0] + ox, b[1], b[2] + oz), (b[0] - ox, b[1], b[2] - oz),
                     (a[0] - ox, a[1], a[2] - oz)]
                n = _norm(_cross(_sub(q[1], q[0]), _sub(q[3], q[0])))
                if n[1] < 0:
                    n = (-n[0], -n[1], -n[2])
                self._add(q, n, path_c, cull=False)
            if steps:
                for a, b in zip(pts[::3], pts[3::3]):
                    if b[1] - a[1] > 12:
                        self.box(b[0], a[1] - 4, b[2], max(40.0, w * 0.06), b[1] - a[1] + 4, 14, "#b3a58f")
            self.walkable = old_w
        # ---- rocks and bushes on the slopes
        for k in range(int(3 + rocky * 8)):
            u, v = rnd.uniform(-0.8, 0.8), rnd.uniform(-0.7, 0.8)
            if math.hypot(u, v) > 0.95:
                continue
            self.sphere(x + u * w / 2, hy(u, v) + 6, z + v * d / 2, r=rnd.uniform(18, 42), c=rock, squash=0.6,
                        bumps=0.12)
        for k in range(int(bushes)):
            u, v = rnd.uniform(-0.85, 0.85), rnd.uniform(-0.2, 0.9)
            if math.hypot(u, v) > 0.9:
                continue
            self.blob(x + u * w / 2, hy(u, v) + 25, z + v * d / 2, r=rnd.uniform(30, 55),
                      c=self.dark("leaf", rnd.uniform(0.8, 1.05)))

    def hill_y(self, x, z, hx=0, hz=0, w=900, d=700, h=260, flat_top=0.35):
        """How high the ground of a hill (drawn with pen.hill(hx, hz, w, d, h)) is at (x, z) - to stand a temple
        on top or a tree on the side (without the small bumps)."""
        u, v = (x - hx) / (w / 2), (z - hz) / (d / 2)
        r = math.hypot(u, v)
        if r >= 1.0:
            return 0.0
        return h * (1.0 if r < flat_top else math.cos(math.pi / 2 * (r - flat_top) / (1.0 - flat_top)) ** 2)

    def grass(self, x=0, y=0, z=0, r=40, c="grass", count=12):
        """A tuft of grass blades."""
        rnd = random.Random(int(x * 5 + z * 3 + r))
        for i in range(int(count)):
            a = rnd.uniform(0, 2 * math.pi)
            d = rnd.uniform(0, r)
            bx, bz = x + math.cos(a) * d, z + math.sin(a) * d
            hh = rnd.uniform(0.6, 1.2) * r
            self.line([(bx, y, bz), (bx + rnd.uniform(-0.3, 0.3) * hh, y + hh, bz)], self.dark(c, rnd.uniform(0.8, 1.1)), 3)

    def cloud(self, x=0, y=600, z=0, w=300, h=100, d=150, c="white"):
        m = self.material(c, roughness=1.0, emission=0.35)
        rnd = random.Random(int(x + y + z))
        for k in range(5):
            self.ellipsoid(x + (k - 2) * w / 5 + rnd.uniform(-10, 10), y + rnd.uniform(0, h * 0.4), z,
                           w / 4.5, h / 2 * rnd.uniform(0.7, 1.0), d / 2, m, rings=5, sides=9)

    def mountain(self, x=0, y=0, z=0, w=800, h=600, d=600, c="#7f9bb8", snow=True):
        rnd = random.Random(int(x + z + h))
        sides = 9
        base = [(x + w / 2 * math.cos(2 * math.pi * j / sides) * rnd.uniform(0.8, 1.1), y,
                 z + d / 2 * math.sin(2 * math.pi * j / sides) * rnd.uniform(0.8, 1.1)) for j in range(sides)]
        mid = [(x + (p[0] - x) * 0.45, y + h * rnd.uniform(0.5, 0.62), z + (p[2] - z) * 0.45) for p in base]
        top = (x + rnd.uniform(-0.05, 0.05) * w, y + h, z)
        for j in range(sides):
            jj = (j + 1) % sides
            self._face_auto([base[j], base[jj], mid[jj], mid[j]], c, (x, y + h * 0.3, z))
            self._face_auto([mid[j], mid[jj], top], "white" if snow else self.light(c, 0.1), (x, y + h * 0.6, z))

    # ---------------------------------------------------------------- reuse another drawing
    def instance(self, name, x=0, y=0, z=0, scale=1.0, turn=0.0, state=None, t=0.0, vary=None, palette=None):
        """Put a copy of another 3D code drawing here (reuse your library: trees, rocks, huts ...).
        palette: "alien_pink" / "autumn" / "snow" / "random:7" / {...} - this copy in a world palette's colours.
        vary: True / False - each copy gets its own small size, turn and colour change (on by itself for trees,
        bushes, rocks and plants, so a forest of the same three models never looks copy-pasted)."""
        faces = _instance_faces(name, state, t)
        if not faces:
            return False
        if vary is None:
            vary = any(k in str(name).lower() for k in VARY_WORDS)
        tint = None
        if vary:
            import random as _r
            rv = _r.Random(f"{name}|{round(float(x))}|{round(float(z))}")
            scale = scale * rv.uniform(0.88, 1.12)
            turn = turn + rv.uniform(-35.0, 35.0)
            tint = (rv.uniform(-0.07, 0.07), rv.uniform(-0.05, 0.06),    # (lighter / darker, toward yellow,
                    rv.uniform(-0.03, 0.03))                              #  a small hue turn for leaves / flowers)
        self.push()
        self.move(x, y, z)
        if turn:
            self.turn(turn)
        if scale != 1.0:
            self.grow(scale)
        mapping = {}
        if palette:
            faces = recolored(faces, palette)
        for f in faces:
            c = f.c
            if tint is not None and isinstance(c, tuple) and len(c) >= 3:
                k, yl = 1.0 + tint[0], tint[1]
                r_, g_, b_ = c[0] * k, c[1] * k, c[2] * k
                if g_ > r_ and g_ > b_:                     # leaves: a little greener or more yellow
                    r_, b_ = r_ + yl * 0.5, b_ - yl * 0.3
                if tint[2] and max(r_, g_, b_) - min(r_, g_, b_) > 0.12:   # coloured parts: hue turned a bit
                    import colorsys as _cs
                    hh, ss, vv = _cs.rgb_to_hsv(min(1.0, max(0.0, r_)), min(1.0, max(0.0, g_)), min(1.0, max(0.0, b_)))
                    r_, g_, b_ = _cs.hsv_to_rgb((hh + tint[2]) % 1.0, ss, vv)
                c = (min(1.0, max(0.0, r_)), min(1.0, max(0.0, g_)), min(1.0, max(0.0, b_))) + tuple(c[3:])
            g = Face([self._pt(p) for p in f.pts], self._dir(f.n) if f.kind == "poly" else f.n, c, f.cull,
                     w=f.w * _scale_of(self._m[0]), sub=f.sub, edge=f.edge, kind=f.kind, mat=f.mat,
                     walk=f.walk or self.walkable, tex=f.tex if c is f.c else None, uv=f.uv)
            mapping[id(f)] = g
            self.faces.append(g)
        for f in faces:
            if f.parent is not None:
                mapping[id(f)].parent = mapping.get(id(f.parent))
        try:                                             # its doors come along (a house in a village place)
            from . import images
            for d in (images.info(name) or {}).get("doors") or []:
                p = self._pt((d[0], d[1], d[2]))
                q = self._pt((d[0] + d[3], d[1], d[2] + d[4]))
                nx, nz = q[0] - p[0], q[2] - p[2]
                L = math.hypot(nx, nz) or 1.0
                self.doors.append([round(p[0], 1), round(p[1], 1), round(p[2], 1), round(nx / L, 3),
                                   round(nz / L, 3), d[5] * scale, d[6] * scale])
        except Exception:
            pass
        self.pop()
        return True


    def _add_tris(self, T, C, colors=None, two_sided=False, uv=None, tid=None, texs=None):
        """many triangles at once: T (n,3,3) in the pen's local space, C (n,4) colours 0..1.
        colors = {"#hex": new colour / material} (close shades too, keeping the texture's light and dark)"""
        import numpy as _np
        from . import model3d
        keys = [k for k, v in (colors or {}).items() if str(v).lower() != str(k).lower()]
        vals = [colors[k] for k in keys]
        which, K = model3d.recolor_index(C, keys) if keys else (None, None)
        R, Tm = self._m
        Rm = _np.array(R, _np.float64).reshape(3, 3)
        P = T @ Rm.T + _np.array(Tm)
        N = _np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        if _np.linalg.det(Rm) < 0:
            N = -N
        ln = _np.linalg.norm(N, axis=1)
        keep = ln > 1e-9
        N = N / _np.where(keep, ln, 1.0)[:, None]
        cull, edge, walk, op = not two_sided, (True if self.outline else None), bool(self.walkable), self.opacity
        lum = lambda c: 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
        surfs = [tex_surface(t) for t in texs] if (texs is not None and len(texs) and tid is not None
                                                     and TEXTURES[0]) else None
        for i in _np.nonzero(keep)[0]:
            w = which[i] if which is not None else -1
            if w >= 0:
                col, mat = self._col(vals[w])
                if mat is None:                               # keep the texture's light and dark shades
                    k2 = min(1.4, max(0.6, (lum(C[i]) + 0.02) / (lum(K[w]) + 0.02)))
                    col = (min(1.0, col[0] * k2), min(1.0, col[1] * k2), min(1.0, col[2] * k2), col[3])
            else:
                c = C[i]
                col, mat = (float(c[0]), float(c[1]), float(c[2]), float(c[3]) * op), None
            pts = P[i]
            tx = tu = None
            if surfs is not None and w < 0 and tid[i] >= 0:      # draw the model's own picture on this face
                sf = surfs[int(tid[i])]
                if sf is not None:
                    W_, H_ = sf.get_width(), sf.get_height()
                    u3 = uv[i]
                    tx, tu = sf, ((float(u3[0][0]) * W_, float(u3[0][1]) * H_), (float(u3[1][0]) * W_, float(u3[1][1]) * H_),
                                  (float(u3[2][0]) * W_, float(u3[2][1]) * H_))
            self.faces.append(Face([tuple(pts[0]), tuple(pts[1]), tuple(pts[2])], tuple(N[i]), col, cull,
                                   edge=edge, mat=mat, walk=walk, tex=tx, uv=tu))
        return int(keep.sum())

    def sculpt(self, name, x=0, y=0, z=0, turn=0.0, scale=1.0, colors=None):
        """a sculpted clay thing of Ghatti Nagar (engine/sculpt_things.py: lota, glass, thali, matka, chair, table,
        charpai, bed, almirah ...) at its real size; turn = degrees round the up axis; colors = {"#old": "#new"}"""
        return _sculpt_into(self, name, x, y, z, turn, scale, colors)

    def doorway(self, x=0, y=0, z=0, w=120, h=330, turn=0.0):
        """a door people walk in and out through ("do": "enter" / "come_out_of") without drawing anything - for a
        sculpted house whose door is painted on its clay (x, z = the middle of the doorstep, it faces -z, turned)"""
        self.push()
        self.move(x, y, z)
        if turn:
            self.turn(turn)
        p = self._pt((0.0, 0.0, 0.0))
        q = self._pt((0.0, 0.0, -1.0))
        u = self._pt((0.0, 1.0, 0.0))
        self.pop()
        nx, nz = q[0] - p[0], q[2] - p[2]
        L = math.hypot(nx, nz) or 1.0
        k = math.dist(u, p) or 1.0                       # (grown with the drawing: a clay house is drawn bigger)
        self.doors.append([round(p[0], 1), round(p[1], 1), round(p[2], 1), round(nx / L, 3), round(nz / L, 3),
                           round(w * k, 1), round(h * k, 1)])

    def clay_scale(self):
        """how much bigger the clay world is drawn than its recipes (the sculpted people's measure)"""
        from . import sculpt_things
        return sculpt_things.CLAY_SCALE

    def sculpt_info(self, name=None):
        """the sculpted things' names (no name), or one thing's {"abilities": [...], "seat": height or None,
        "top": height things are put down on, or None}"""
        from . import sculpt_things
        if name is None:
            return sculpt_things.names()
        ab = sculpt_things.abilities(name)
        return {"abilities": ab, "seat": sculpt_things.TOPS.get(name) if "sit" in ab else None,
                "top": sculpt_things.TOPS.get(name)}

    def model(self, name, x=0, y=0, z=0, height=None, scale=1.0, turn=0.0, colors=None, max_faces=None,
              two_sided=False, up=None, ground=True, palette=None, part=None, detail=None):
        """A ready-made model from another website (GLB / glTF / OBJ / STL in assets/models/<name>/).
        height = how tall (our units, person = 300); or scale = 1 keeps the file's real size (1 m = 175).
        turn = degrees round the up axis.  colors = {"#8b5a2b": "wood", ...} changes a colour (or makes it a
        material: pen.material("gold")).  max_faces = simplify heavy models (default 2500).
        up = "z" for files made with Z up (CAD, STL).  ground=True: stands on y (its lowest point at y).
        part = one piece of a big model (a building of a city) - it stays where it is in the whole model.
        detail = "normal" | "high" | "very_high" | "place" | "full" (instead of max_faces)."""
        from . import model3d
        mf = int(max_faces or model3d.DETAIL.get(str(detail or ""), model3d.MAX_FACES))
        m = model3d.load(name, mf, up, part=part)
        T, C, lo, hi = m["tris"], m["cols"], m["lo"], m["hi"]
        if part is not None:                              # placed as a piece of the whole model
            lo, hi = m.get("lo_all", lo), m.get("hi_all", hi)
        if palette:                                       # the whole model in a world palette's colours
            from . import palette as _pal
            pc = _pal.compile_palette(palette)
            if pc is not None:
                C = C.copy()
                C[:, :3] = _pal.recolor(C[:, :3], pc)
        mh = float(hi[1] - lo[1]) or 1.0
        k = float(height) / mh if height else model3d.UNITS_PER_M * float(scale)
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        by = lo[1] if ground else 0.0
        self.push()
        self.move(x, y, z)
        if turn:
            self.turn(turn)
        import numpy as _np
        n = self._add_tris((T - _np.array([cx, by, cz])) * k, C, colors, two_sided,
                           uv=m.get("uv"), tid=m.get("tid"), texs=m.get("texs"))
        self.pop()
        return {"faces": n, "height": mh * k, "width": float(hi[0] - lo[0]) * k,
                "depth": float(hi[2] - lo[2]) * k}


def _sculpt_into(pen, name, x=0, y=0, z=0, turn=0.0, scale=1.0, colors=None):
    """pen.sculpt: a sculpted clay thing (engine/sculpt_things.py) at its real size, smooth-shaded"""
    from . import sculpt_things
    big = float(max(sculpt_things.size(name).values())) > 250.0     # a house, a tree: a far mesh too
    n = _sculpt_mesh_into(pen, sculpt_things.mesh(name), x, y, z, turn, scale, colors, 0 if big else None)
    if big:
        _sculpt_mesh_into(pen, sculpt_things.mesh(name, far=True), x, y, z, turn, scale, colors, 1)
    return n


def _sculpt_mesh_into(pen, got, x, y, z, turn, scale, colors, lod):
    import numpy as _np
    V, Q, N, C, G = got
    pen.push()
    pen.move(x, y, z)
    if turn:
        pen.turn(turn)
    if scale != 1.0:
        pen.grow(scale)
    R9, T3 = pen._m
    M = _np.array(R9, float).reshape(3, 3)
    W = V @ M.T + _np.array(T3, float)
    NM = _np.array(_inv_t(R9), float).reshape(3, 3)
    NW = N @ NM.T
    NW /= _np.maximum(_np.linalg.norm(NW, axis=1, keepdims=True), 1e-9)
    Cv = _np.array(C[:, :3], float)
    col = Cv[Q].mean(axis=1)
    if colors:                                          # {"#old": "#new"} recolours the parts of that colour
        from .sculpt3d import rgb
        for k_, v_ in colors.items():
            a_, b_ = rgb(k_), pen._col(v_)[0]
            hit = _np.abs(col - a_).max(axis=1) < 0.12
            col[hit] = _np.array(b_[:3])
            Cv[_np.abs(Cv - a_).max(axis=1) < 0.12] = _np.array(b_[:3])
    sm = NW[Q].sum(axis=1)
    WQ = W[Q]                                           # the face's own normal (its diagonals) decides what is seen:
    fn = _np.cross(WQ[:, 2] - WQ[:, 0], WQ[:, 3] - WQ[:, 1])   # the corners' mean culled faces that do face us on a
    fn *= _np.where((fn * sm).sum(axis=1) < 0, -1.0, 1.0)[:, None]   # stepped clay surface (rows of holes)
    bad = _np.linalg.norm(fn, axis=1) < 1e-9
    fn[bad] = sm[bad]
    fn /= _np.maximum(_np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
    gl = G[Q].mean(axis=1)
    op, walk, edge = pen.opacity, bool(pen.walkable), (True if pen.outline else None)
    Wl, NWl, coll, fnl, Cvl = W.tolist(), NW.tolist(), col.tolist(), fn.tolist(), Cv.tolist()
    for i, q in enumerate(Q.tolist()):
        cc = coll[i]
        pen.faces.append(Face([tuple(Wl[q[0]]), tuple(Wl[q[1]]), tuple(Wl[q[2]]), tuple(Wl[q[3]])], tuple(fnl[i]),
                              (cc[0], cc[1], cc[2], op), True, edge=edge, mat=(0.6, 40.0, 0.0) if gl[i] > 0.6 else None,
                              walk=walk, vn=[NWl[q[0]], NWl[q[1]], NWl[q[2]], NWl[q[3]]], lod=lod,
                              vc=[Cvl[q[0]], Cvl[q[1]], Cvl[q[2]], Cvl[q[3]]]))
    pen.pop()
    return len(Q)


def _inv_t(R):
    """Inverse transpose of a 3x3 (normals under uneven scaling)."""
    a, b, c, d, e, f, g, h, i = R
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        return R
    inv = ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det,
           (f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det,
           (d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det)
    return (inv[0], inv[3], inv[6], inv[1], inv[4], inv[7], inv[2], inv[5], inv[8])


def _scale_of(R):
    return abs(R[0] * (R[4] * R[8] - R[5] * R[7]) - R[1] * (R[3] * R[8] - R[5] * R[6]) +
               R[2] * (R[3] * R[7] - R[4] * R[6])) ** (1.0 / 3.0) or 1.0


def _smooth(pts, n=4):
    """Catmull-Rom: a smooth path through the points."""
    if len(pts) < 3:
        return list(pts)
    out = []
    P = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 +
                                    (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(3)))
    out.append(tuple(pts[-1]))
    return out


_INST = {}
_INST_DEPTH = [0]


def _instance_faces(name, state=None, t=0.0):
    """Faces of another 3D code drawing (for pen.instance) - cached, no endless nesting."""
    from . import codedraw
    got = codedraw._load(name)
    if not got or not codedraw.is3d(got[2].get("KIND")):
        return None
    key = (name, got[0], state, round(float(t), 3))
    if key in _INST:
        return _INST[key]
    if _INST_DEPTH[0] > 3:
        return None
    _INST_DEPTH[0] += 1
    try:
        faces = build(got[1], t, state)
    finally:
        _INST_DEPTH[0] -= 1
    if len(_INST) > 200:
        _INST.clear()
    _INST[key] = faces
    return faces


class _Group:
    def __init__(self, pen, args):
        self.pen, self.args = pen, args

    def __enter__(self):
        x, y, z, rx, ry, rz, s = self.args
        self.pen.push()
        self.pen.move(x, y, z)
        if ry:
            self.pen.rotate_y(ry)
        if rx:
            self.pen.rotate_x(rx)
        if rz:
            self.pen.rotate_z(rz)
        if s != 1.0:
            self.pen.grow(s)
        return self.pen

    def __exit__(self, *exc):
        self.pen.pop()
        return False


def _mul(A, B):
    return tuple(sum(A[r * 3 + k] * B[k * 3 + c] for k in range(3)) for r in range(3) for c in range(3))


class _Thing3(_Thing):
    """with pen.thing(...): faces drawn inside go to that thing."""

    def __enter__(self):
        if self.pen._things is not None:
            self._start = len(self.pen.faces)
        self._door0 = len(self.pen.doors)
        self._walk0 = self.pen.walkable
        if self.opts.get("walkable"):
            self.pen.walkable = True
        return self.pen

    def __exit__(self, *exc):
        self.pen.walkable = self._walk0
        if self.pen._things is not None and exc[0] is None:
            name = _clean(self.name) or f"thing{len(self.pen._things) + 1}"
            while name in self.pen._things:
                name += "_2"
            self.opts["_doors"] = [list(d) for d in self.pen.doors[self._door0:]]
            self.pen._things[name] = (self.pen.faces[self._start:], self.opts)
        return False


# ============================================================================ building the faces of a drawing
LAST_DOORS = []     # the doors of the last build() (object files: saved as "doors" in the picture's info)


def build(fn, t=0.0, state=None, things=False):
    """Run a 3D drawing. -> faces  (things=True: ({name: (faces, opts)}, loose_faces))"""
    global LAST_DOORS
    from .codedraw import _call
    pen = Pen3()
    if things:
        pen._things = {}
    _call(fn, pen, t, state)
    LAST_DOORS = pen.doors
    if things:
        used = set()
        for fs, _o in pen._things.values():
            used.update(id(f) for f in fs)
        return pen._things, [f for f in pen.faces if id(f) not in used]
    return pen.faces


def recolored(faces, spec=None):
    """copies of faces in a world palette's colours (spec = a palette setting; None = the current one)"""
    import numpy as np
    from . import palette as _pal
    pal = _pal.compile_palette(spec) if spec is not None else _pal.CURRENT[0]
    if pal is None or not faces:
        return faces
    C = np.array([f.c[:3] for f in faces], float)
    up = np.array([f.n[1] if len(f.n) == 3 else 0.0 for f in faces], float)
    N = _pal.recolor(C, pal, up=up)
    out, mp = [], {}
    for f, c in zip(faces, N):
        g = Face(f.pts, f.n, (float(c[0]), float(c[1]), float(c[2])) + tuple(f.c[3:]), f.cull, w=f.w, sub=f.sub,
                 edge=f.edge, kind=f.kind, mat=f.mat, walk=f.walk)
        mp[id(f)] = g
        out.append(g)
    for f in faces:
        if f.parent is not None:
            mp[id(f)].parent = mp.get(id(f.parent))
    return out


def walk_polys(faces):
    """Tops people can walk on: [[(x, y, z), ...], ...] (faces marked walk that look up)."""
    out = []
    for f in faces:
        if f.walk and f.kind == "poly" and f.n[1] > 0.5 and len(f.pts) >= 3:
            out.append([[round(p[0], 1), round(p[1], 1), round(p[2], 1)] for p in f.pts])
    return out


def footprint(faces):
    """[x0, x1, z0, z1] of the solid parts on the ground (for walking around it)."""
    xs, zs = [], []
    for f in faces:
        if f.kind == "poly" and f.c[3] > 0.3:
            for p in f.pts:
                if p[1] < 200:
                    xs.append(p[0])
                    zs.append(p[2])
    if not xs:
        return None
    return [round(min(xs), 1), round(max(xs), 1), round(min(zs), 1), round(max(zs), 1)]


def feet(faces, gap=30.0, most=16):
    """[[x0, x1, z0, z1], ...]: the separate solid pieces on the ground - a row of bushes, two pillars, a trunk -
    so people can walk BETWEEN them (footprint() is one box round all of them)."""
    boxes = []
    for f in faces:
        if f.kind != "poly" or f.c[3] <= 0.3:
            continue
        low = [p for p in f.pts if p[1] < 200]
        if not low:
            continue
        boxes.append([min(p[0] for p in low), max(p[0] for p in low), min(p[2] for p in low), max(p[2] for p in low)])
    if not boxes:
        return None
    merged = True
    while merged:                                   # join pieces that touch (or nearly): one solid lump
        merged = False
        out = []
        for b in boxes:
            for o in out:
                if b[0] <= o[1] + gap and o[0] <= b[1] + gap and b[2] <= o[3] + gap and o[2] <= b[3] + gap:
                    o[0], o[1], o[2], o[3] = min(o[0], b[0]), max(o[1], b[1]), min(o[2], b[2]), max(o[3], b[3])
                    merged = True
                    break
            else:
                out.append(list(b))
        boxes = out
    boxes = [b for b in boxes if (b[1] - b[0]) > 8 or (b[3] - b[2]) > 8]
    if len(boxes) > most:                           # too many little bits: one box is good enough
        return None
    return [[round(v, 1) for v in b] for b in sorted(boxes)]


def turned(faces, deg):
    """The same faces turned around the up axis (story "turn": 90)."""
    a = math.radians(deg)
    c, s_ = math.cos(a), math.sin(a)

    def rp(p):
        return (p[0] * c + p[2] * s_, p[1], -p[0] * s_ + p[2] * c)
    out = [Face([rp(p) for p in f.pts], rp(f.n) if f.kind == "poly" else f.n, f.c, f.cull, f.line, f.w, None, f.sub,
                f.edge, f.kind, f.mat, f.walk, f.tex, f.uv, [rp(v) for v in f.vn] if f.vn else None,
                getattr(f, "lod", None), getattr(f, "vc", None)) for f in faces]
    idx = {id(f): g for f, g in zip(faces, out)}
    for f, g in zip(faces, out):
        if f.parent is not None:
            g.parent = idx.get(id(f.parent))
    return out


def extent(faces):
    xs, ys, zs = [], [], []
    for f in faces:
        for p in f.pts:
            xs.append(p[0])
            ys.append(p[1])
            zs.append(p[2])
    if not xs:
        return None
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def recentre(faces, dx, dy, dz):
    out = []
    for f in faces:
        g = Face([(p[0] - dx, p[1] - dy, p[2] - dz) for p in f.pts], f.n, f.c, f.cull, f.line, f.w, None, f.sub,
                 f.edge, f.kind, f.mat, f.walk, f.tex, f.uv, f.vn, getattr(f, "lod", None), getattr(f, "vc", None))
        out.append(g)
    idx = {id(f): g for f, g in zip(faces, out)}
    for f, g in zip(faces, out):
        if f.parent is not None:
            g.parent = idx.get(id(f.parent))
    return out


# ============================================================================ drawing faces
def sun_dir(time_word=None):
    """Where the light comes from (unit vector toward the sun): its real height for the time of day - low at
    dawn and sunset (long shadows), high at noon (short ones) - engine/realworld.py."""
    from . import realworld
    return realworld.sun(time_word)["dir"]


SHADOW_K = 0.55    # how much of the true shadow length the soft footprint shows (it is a blurred blob)
FAST = [os.environ.get("SS_SLOW3D") is None]    # numpy drawing (SS_SLOW3D=1 = the old one-by-one way)
TOON = [False]      # anime look for 3D: 2 flat shades + dark outlines ("toon": true in the story settings)


def _clip_near(P, depth, dn):
    """Cut a polygon (world points) at the camera's near plane: keeps the part with depth(p) >= dn."""
    out = []
    for i, a in enumerate(P):
        b = P[(i + 1) % len(P)]
        da, db = depth(a), depth(b)
        if da >= dn:
            out.append(a)
        if (da >= dn) != (db >= dn):
            f = (dn - da) / (db - da)
            out.append(tuple(a[j] + (b[j] - a[j]) * f for j in range(3)))
    return out


def draw_faces(ctx, faces, to_world, project, cam_pos, light=None, alpha=1.0, px=1.0, shadow=True,
               normal_flip=1.0, to_normal=None, toon=None, depth=None, near=None):
    """Paint 3D faces. to_world(p) -> world point; project(P) -> (sx, sy, k) or None (screen, y down);
    cam_pos = camera position in world units; px = line width scale (screen px per unit at k=1).
    depth(P) + near: faces partly behind the camera are cut at the near plane (walls right at the lens)."""
    L = light or sun_dir()
    items = []
    keys = {}
    if any(getattr(f, "lod", None) == 1 for f in faces):
        faces = [f for f in faces if getattr(f, "lod", None) != 1]   # (the near mesh of sculpted things)
    for i, f in enumerate(faces):
        P = [to_world(p) for p in f.pts]
        c = (sum(p[0] for p in P) / len(P), sum(p[1] for p in P) / len(P), sum(p[2] for p in P) / len(P))
        n = to_normal(f.n) if to_normal else (f.n[0] * normal_flip, f.n[1], f.n[2])
        if f.cull and f.kind == "poly" and _dot(n, _sub(c, cam_pos)) >= 0:
            keys[id(f)] = None
            continue
        S = [project(p) for p in P]
        if any(s is None for s in S):
            if depth is None or f.kind != "poly" or len(P) < 3:
                keys[id(f)] = None
                continue
            P2 = _clip_near(P, depth, near + 1.0)       # cut at the near plane instead of dropping it
            S = [project(p) for p in P2]
            if len(P2) < 3 or any(s is None for s in S):
                keys[id(f)] = None
                continue
        dist = math.sqrt(sum((c[j] - cam_pos[j]) ** 2 for j in range(3)))
        keys[id(f)] = dist
        items.append((f, S, n, dist, i))
    order = []
    for f, S, n, dist, i in items:
        if f.parent is not None:
            pd = keys.get(id(f.parent))
            if pd is None:
                continue                                 # its wall is facing away
            order.append(((-pd, 1, f.sub, i), f, S, n))
        else:
            order.append(((-dist, 0, 0, i), f, S, n))
    order.sort(key=lambda x: x[0])
    if shadow:
        _shadow(ctx, faces, to_world, project, L, alpha)
    wscale = to_world_scale(to_world)
    for _k, f, S, n in order:
        r, g, b, a = f.c
        if f.kind in ("dot", "glow"):
            sx, sy, kk = S[0]
            rad = max(0.5, f.w * kk * wscale)
            if f.kind == "dot":
                ctx.arc(sx, sy, rad, 0, 2 * math.pi)
                ctx.set_source_rgba(r, g, b, a * alpha)
                ctx.fill()
            else:
                gr = cairo.RadialGradient(sx, sy, 0, sx, sy, rad)
                gr.add_color_stop_rgba(0, r, g, b, a * alpha)
                gr.add_color_stop_rgba(1, r, g, b, 0)
                ctx.set_source(gr)
                ctx.arc(sx, sy, rad, 0, 2 * math.pi)
                ctx.fill()
                _night_light(sx, sy, rad, (r, g, b), a * alpha)
            continue
        if f.line:
            k = (S[0][2] + S[1][2]) / 2
            ctx.move_to(S[0][0], S[0][1])
            ctx.line_to(S[1][0], S[1][1])
            ctx.set_source_rgba(r, g, b, a * alpha)
            ctx.set_line_width(max(0.6, f.w * k))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.stroke()
            continue
        nl = n
        if f.vn and len(f.vn) == len(S):                 # lit by its corners' mean normal (its own steps on clay)
            m_ = [sum(v[j] for v in f.vn) for j in range(3)]
            nl = _norm(to_normal(m_) if to_normal else (m_[0] * normal_flip, m_[1], m_[2]))
        lit = AMBIENT + DIFFUSE * max(0.0, _dot(nl, L))
        spec = 0.0
        if f.mat:
            shine, sharp, emit = f.mat[:3]
            if emit:
                lit = lit + (1.0 - lit) * emit
            if shine > 0.01:                             # a shiny highlight where the sun reflects
                cen = [sum(p[j] for p in S) / len(S) for j in range(2)]
                P0 = to_world(f.pts[0])
                V = _norm(_sub(cam_pos, P0))
                Hh = _norm((L[0] + V[0], L[1] + V[1], L[2] + V[2]))
                spec = shine * max(0.0, _dot(n, Hh)) ** sharp
        toon_on = TOON[0] if toon is None else toon
        if toon_on:                                      # cel shading: lit or in shadow, hard highlight
            nd = _dot(n, L)
            lit = 1.02 if nd > 0.28 else (0.86 if nd > -0.1 else 0.72)
            if f.mat and f.mat[2]:
                lit = 1.0
            spec = 0.35 if spec > 0.45 else 0.0
        rr, gg, bb = min(1.0, r * lit + spec), min(1.0, g * lit + spec), min(1.0, b * lit + spec)
        is_skin = f.mat is not None and len(f.mat) > 3 and f.mat[3] and SKIN[0] and not toon_on
        if is_skin:
            Vs = _norm(_sub(cam_pos, to_world(f.pts[0])))
            rr, gg, bb = skin_light(r, g, b, _dot(n, L), n[1], abs(_dot(n, Vs)))
        ctx.move_to(S[0][0], S[0][1])
        for s in S[1:]:
            ctx.line_to(s[0], s[1])
        ctx.close_path()
        if f.vn and SMOOTH[0] and not toon_on and len(f.vn) == len(S) and len(S) in (3, 4) and a >= 0.99 and \
                max(q[0] for q in S) - min(q[0] for q in S) + max(q[1] for q in S) - min(q[1] for q in S) > SMOOTH_MIN_PX:
            cols = []
            vcs = getattr(f, "vc", None) if not is_skin else None
            for j_, v in enumerate(f.vn):                # smooth: the light at every corner
                vv = to_normal(v) if to_normal else (v[0] * normal_flip, v[1], v[2])
                if vcs:                                  # (and its own clay colour)
                    r, g, b = vcs[j_][0], vcs[j_][1], vcs[j_][2]
                if is_skin:
                    cols.append(skin_light(r, g, b, _dot(vv, L), vv[1], abs(_dot(vv, Vs))) + (a,))
                    continue
                lv = AMBIENT + DIFFUSE * max(0.0, _dot(vv, L))
                if f.mat and f.mat[2]:
                    lv = lv + (1.0 - lv) * f.mat[2]
                cols.append((min(1.0, r * lv + spec), min(1.0, g * lv + spec), min(1.0, b * lv + spec), a))
            ctx.set_line_width(0.9 * px)
            _gouraud(ctx, [(q[0], q[1]) for q in S], cols, alpha)
            continue
        if getattr(f, "tex", None) is not None and len(S) == 3 and not toon_on and \
                max(q[0] for q in S) - min(q[0] for q in S) + max(q[1] for q in S) - min(q[1] for q in S) > 7.0:
            ctx.set_source_rgba(rr, gg, bb, a * alpha)
            ctx.set_line_width(0.9 * px)
            ctx.stroke_preserve()
            if _tex_fill(ctx, f, [(q[0], q[1]) for q in S], lit, spec, a * alpha):
                continue
        ctx.set_source_rgba(rr, gg, bb, a * alpha)
        if a >= 0.99:                                    # a hair-thin edge of the same colour hides seams
            ctx.fill_preserve()
            ctx.set_line_width(0.9 * px)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            if f.edge or toon_on:
                ctx.set_source_rgba(rr * 0.35, gg * 0.35, bb * 0.35, alpha)
                ctx.set_line_width(max(1.0, (2.2 if toon_on else 1.6) * px))
            ctx.stroke()
        else:
            ctx.fill()


def to_world_scale(to_world):
    """How much to_world() grows things (for dot / glow sizes)."""
    try:
        a, b = to_world((0.0, 0.0, 0.0)), to_world((1.0, 0.0, 0.0))
        return math.sqrt(sum((b[j] - a[j]) ** 2 for j in range(3))) or 1.0
    except Exception:
        return 1.0


def _night_light(sx, sy, rad, c, a):
    """A 3D glow (a lamp, a fire, a lit window) is also a light at night (engine/nightlights.py)."""
    if a > 0.15 and rad > 4 and CURRENT is not None:
        from .nightlights import add
        warm = c[0] > 0.6 and c[2] < 0.7
        add(sx, sy, rad * 2.2, c, min(1.0, a * 1.1), flame=warm and c[1] < 0.75, gx=sx, gy=sy + rad * 1.2,
            kind="glow3d")


def _shadow_k():
    from .realworld import SHADOW_3D                     # clouds over the sun: fainter shadows
    return SHADOW_3D[0]


def _hull(pts):
    """Convex hull of 2D points (monotone chain), counter-clockwise."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) -
                                     (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    lo, hi = half(pts), half(reversed(pts))
    return lo[:-1] + hi[:-1]


def _shadow_ring(x0, x1, y0, y1, z0, z1, L, project):
    """Screen outline of a soft ground shadow: the footprint and, stretched away from the sun, a narrower tip
    (its real length h / tan(sun height) - long at sunrise and sunset, short at noon), joined into one shape."""
    hgt = y1 - max(0.0, y0)
    sx = -L[0] / max(L[1], 0.25) * hgt * SHADOW_K
    sz = -L[2] / max(L[1], 0.25) * hgt * SHADOW_K
    pad = 0.08 * max(x1 - x0, z1 - z0)
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    rx, rz = (x1 - x0) / 2 + pad, (z1 - z0) / 2 + pad
    pts = []
    for (ox, oz, k) in ((0.0, 0.0, 1.0), (sx * 0.5, sz * 0.5, 0.85), (sx, sz, 0.6)):
        for i in range(16):
            a = 2 * math.pi * i / 16
            q = project(cx + ox + rx * k * math.cos(a), cz + oz + rz * k * math.sin(a))
            if q is None:
                return None
            pts.append((q[0], q[1]))
    return _hull(pts)


def _shadow(ctx, faces, to_world, project, L, alpha):
    """A soft dark footprint on the ground, pushed away from the sun."""
    pts = [to_world(p) for f in faces if f.kind == "poly" and f.c[3] > 0.3 for p in f.pts]
    if not pts:
        return
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    z0, z1 = min(p[2] for p in pts), max(p[2] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    if y0 > 30:
        return
    ring = _shadow_ring(x0, x1, y0, y1, z0, z1, L, lambda X, Z: project((X, 0.0, Z)))
    if ring is None:
        return
    ctx.move_to(ring[0][0], ring[0][1])
    for s in ring[1:]:
        ctx.line_to(s[0], s[1])
    ctx.close_path()
    ctx.set_source_rgba(0, 0, 0, 0.16 * alpha * _shadow_k())
    ctx.fill()


# ============================================================================ views (no scene camera)
class View:
    """A simple camera: position, turn (yaw), look down (pitch), focal length (screen units)."""

    def __init__(self, pos, yaw=0.0, pitch=0.0, f=1000.0, cx=0.0, cy=0.0, flip_y=True):
        self.pos, self.f, self.cx, self.cy, self.flip_y = pos, f, cx, cy, flip_y
        self.cyw, self.syw = math.cos(yaw), math.sin(yaw)
        self.cp, self.sp = math.cos(pitch), math.sin(pitch)

    def project(self, P):
        x, y, z = P[0] - self.pos[0], P[1] - self.pos[1], P[2] - self.pos[2]
        x, z = x * self.cyw - z * self.syw, x * self.syw + z * self.cyw
        y, z = y * self.cp + z * self.sp, -y * self.sp + z * self.cp
        if z < 5.0:
            return None
        k = self.f / z
        return (self.cx + x * k, self.cy - y * k if self.flip_y else self.cy + y * k, k)


def front_recording(faces, light=None):
    """The front view (like an elevation) as a vector recording in story units, same convention as the 2D
    drawings (recording y-down = story y-up).  -> (recording, (x0, y0, x1, y1) y-up)"""
    ex = extent(faces)
    rec = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)
    ctx = cairo.Context(rec)
    if not ex:
        return rec, (0, 0, 0, 0)
    size = max(ex[1] - ex[0], ex[3] - ex[2], ex[5] - ex[4], 100.0)
    D = max(2200.0, size * 3.2)
    eye = min(165.0, max(60.0, ex[3] * 0.45))
    # screen units = story units at depth z = 0; flip_y False + recording y = -story y
    v = View((0.0, eye, -D), f=D, cx=0.0, cy=-eye, flip_y=True)
    v.cy = -eye

    def proj(P):
        s = v.project(P)
        if s is None:
            return None
        return (s[0], s[1] - 0.0, s[2])

    # View.project gives y down around cy: y_screen = cy - (y - eye)*k -> with cy = -eye: = -(eye + (y-eye)k)
    draw_faces(ctx, faces, lambda p: p, proj, (0.0, eye, -D), light or sun_dir(), px=1.0, shadow=False)
    x0, y0, w, h = rec.ink_extents()
    return rec, (x0, -(y0 + h), x0 + w, -y0)


def preview_view(faces, width, height, angle=-28.0, elev=18.0, light=None, bg=True, person=True, labels=None,
                 zoom=1.0, shadow=True):
    """A turntable view (angle degrees around the thing, elev degrees looking down). -> cairo ImageSurface"""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surf)
    ex = extent(faces) or (-100, 100, 0, 200, -100, 100)
    cx, cy, cz = (ex[0] + ex[1]) / 2, (ex[2] + ex[3]) / 2, (ex[4] + ex[5]) / 2
    size = max(ex[1] - ex[0], ex[3] - ex[2], ex[5] - ex[4], 320.0)
    D = size * 2.2 / zoom
    a, e = math.radians(angle), math.radians(elev)
    pos = (cx + math.sin(a) * math.cos(e) * D, cy + math.sin(e) * D, cz - math.cos(a) * math.cos(e) * D)
    f = min(width, height) * 1.35
    v = View(pos, yaw=-a, pitch=e, f=f, cx=width / 2, cy=height * 0.52)
    if bg:
        g = cairo.LinearGradient(0, 0, 0, height)
        g.add_color_stop_rgb(0, 0.64, 0.8, 0.93)
        g.add_color_stop_rgb(1, 0.93, 0.94, 0.9)
        ctx.set_source(g)
        ctx.paint()
        R = size * 1.6                                   # a round patch of ground
        ring = [v.project((cx + R * math.cos(2 * math.pi * i / 40), 0.0, cz + R * math.sin(2 * math.pi * i / 40)))
                for i in range(40)]
        ring = [s for s in ring if s]
        if len(ring) > 3:
            ctx.move_to(ring[0][0], ring[0][1])
            for s in ring[1:]:
                ctx.line_to(s[0], s[1])
            ctx.close_path()
            ctx.set_source_rgb(0.72, 0.8, 0.6)
            ctx.fill()
    if person:                                           # a 300-tall person for size, standing beside it
        base = (ex[0] - 90.0, 0.0, ex[4])
        top = (base[0], 300.0, base[2])
        sb, st = v.project(base), v.project(top)
        if sb and st:
            ctx.set_source_rgb(0.15, 0.15, 0.2)
            hgt = sb[1] - st[1]
            ctx.set_line_width(max(1.5, hgt * 0.04))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            x, y0 = sb[0], sb[1]
            for (ax, ay), (bx, by) in (((0, .5), (0, .78)), ((0, .5), (-.1, 0)), ((0, .5), (.1, 0)),
                                       ((0, .75), (-.13, .5)), ((0, .75), (.13, .5))):
                ctx.move_to(x + ax * hgt, y0 - ay * hgt)
                ctx.line_to(x + bx * hgt, y0 - by * hgt)
            ctx.stroke()
            ctx.arc(x, y0 - 0.89 * hgt, 0.105 * hgt, 0, 2 * math.pi)
            ctx.fill()
    draw_faces(ctx, faces, lambda p: p, v.project, pos, light or sun_dir(), px=1.0, shadow=shadow)
    if labels:
        ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(11)
        for i, (name, pt) in enumerate(labels):
            s = v.project(pt)
            if not s:
                continue
            xb = ctx.text_extents(name)
            ctx.set_source_rgba(1, 1, 1, 0.85)
            ctx.rectangle(s[0] - xb.x_advance / 2 - 3, s[1] - 14, xb.x_advance + 6, 15)
            ctx.fill()
            ctx.set_source_rgb(*((0.85, 0.2, 0.2), (0.1, 0.4, 0.85), (0.1, 0.55, 0.2))[i % 3])
            ctx.move_to(s[0] - xb.x_advance / 2, s[1] - 3)
            ctx.show_text(name)
    surf.flush()
    return surf


# ============================================================================ inside the 3D camera mode
CURRENT = None      # (scene, cam, obj, sx, sy, k) while scene3d draws an object - set by scene3d.draw_obj
CONTACT = [True]
PLANT_WORDS = ("tree", "bush", "plant", "palm", "banana", "fern", "grass", "flower", "banyan", "shrub", "mango",
               "neem", "peepal", "reed", "bamboo", "pine", "crop", "wheat", "sugarcane")     # they bend in the wind
VARY_WORDS = ("tree", "bush", "rock", "stone", "plant", "palm", "banana", "fern", "grass", "flower", "banyan",
              "shrub", "boulder", "mango", "neem", "peepal", "reed", "cactus", "mushroom", "pine", "bamboo")    # a dark contact shadow where things meet the ground (story setting "contact_shadows": false)


from collections import OrderedDict as _OD
_EXT = _OD()


def draw_in_scene(ctx, faces, x, y, height, meta_h, flip=False, alpha=1.0, light=None, recolor=True, bend=0.0, turn=0.0):
    """Draw faces with the REAL scene camera. (x, y) = where images.draw was asked to put the thing (in the
    caller's local coordinates, bottom-centre). Returns (w, h) or None when this is not a plain 3D placement."""
    if CURRENT is None:
        return None
    scene, cam, o, sx, sy, k = CURRENT
    M = ctx.get_matrix()
    if abs(M.xy) > 1e-3 * abs(M.xx) + 1e-6 or abs(M.yx) > 1e-3 * abs(M.yy) + 1e-6:
        return None                                      # turned (thrown, carried at an angle): front view
    dx, dy = M.transform_point(x, y)
    lx, ly = (dx - sx) / k, -(dy - sy) / k               # offset from the object's anchor, world units
    rel = abs(M.xx) / k
    mirror = (M.xx < 0) != bool(flip)
    s = rel * (float(height) / meta_h if (height and meta_h) else 1.0)
    X0, Y0, Z0 = o.X + lx, o.Y + ly, o.Z
    fx = -1.0 if mirror else 1.0
    if getattr(ctx, "live3d", False):                    # 🎥 live 3D play: the browser draws it (engine/live3d.py)
        from .live3d import placed
        return placed(ctx, faces, X0, Y0, Z0, s, fx, turn, alpha)

    def to_world(p):
        return (X0 + fx * s * p[0], Y0 + s * p[1], Z0 + s * p[2])

    def proj(P):
        r = scene.project(cam, P[0], P[1], P[2])
        return None if r is None else (r[0], r[1], r[2])

    cam_pos = (cam.x, cam.h, cam.z)
    cy_, sy_ = math.cos(cam.yaw or 0.0), math.sin(cam.yaw or 0.0)

    def depth(P):                                        # distance along the view (as scene.project)
        return (P[0] - cam.x) * sy_ + (P[2] - cam.z) * cy_

    from .scene3d import NEAR
    ctx.save()
    ctx.identity_matrix()
    L_ = light or getattr(scene, "_sun3", None) or sun_dir()
    if FAST[0]:                                          # numpy: the same picture, much faster
        draw_faces_fast(ctx, faces, X0, Y0, Z0, s, fx, scene, cam, L_, alpha=alpha,
                        px=max(0.5, getattr(scene, "S", 1.0)), shadow=abs(ly) < 5, recolor=recolor, bend=bend,
                        turn=turn)
        ctx.restore()
        pk = _pack(faces)                                # (its size from the packed points: no Python loop)
        if pk.F == 0:
            return (0, 0)
        lo, hi = pk.P.min(axis=0), pk.P.max(axis=0)
        return ((hi[0] - lo[0]) * s, (hi[1] - lo[1]) * s)
    else:
        if turn:
            faces = turned(faces, turn)
        draw_faces(ctx, faces, to_world, proj, cam_pos, L_, alpha=alpha, px=max(0.5, getattr(scene, "S", 1.0)),
                   shadow=abs(ly) < 5, normal_flip=fx, depth=depth, near=NEAR)
    ctx.restore()
    if len(faces) > 4000:                                # a big list made fresh every frame (a sculpted person):
        ex = extent(faces)                               # measured, never kept (400 of them held gigabytes)
        return ((ex[1] - ex[0]) * s, (ex[3] - ex[2]) * s) if ex else (0, 0)
    ek = id(faces)
    got = _EXT.get(ek)
    if got is None or got[0] is not faces:
        while len(_EXT) > 400:                           # oldest first (it keeps the face lists alive)
            _EXT.popitem(last=False)
        got = _EXT[ek] = (faces, extent(faces))
    else:
        _EXT.move_to_end(ek)
    ex = got[1]
    return ((ex[1] - ex[0]) * s, (ex[3] - ex[2]) * s) if ex else (0, 0)


# ============================================================================ fast path (numpy): the same pictures,
# the maths for all faces at once instead of one point at a time (3D places, people, animals, worlds)
_PACK = _OD()
_PACK_BYTES = [0]
PACK_BUDGET = [220e6]       # bytes of packed faces kept (the render's low-RAM mode makes it smaller)
_KIND = {"poly": 0, "line": 1, "dot": 2, "glow": 3}
_BIG_SEEN = set()


class _Packed:
    __slots__ = ("faces", "P", "start", "count", "n", "c", "cull", "kind", "w", "parent", "sub", "edge", "shine",
                 "sharp", "emit", "first", "shadow_pts", "F", "pal_key", "pal_c", "nbytes", "tex", "VN", "ns", "VC", "smooth", "skin",
                 "lod", "has_lod", "subs")


def _pack(faces):
    """Faces -> numpy arrays (cached per face list; the lists themselves are cached by the callers)."""
    import numpy as np
    key = id(faces)
    got = _PACK.get(key)
    if got is not None and got.faces is faces:
        _PACK.move_to_end(key)
        return got
    # least recently used out first: people and moving things make new face lists every frame, and each
    # packed list keeps its faces alive - an unlimited store filled the RAM (3+ GB on a long scene)
    while _PACK and (len(_PACK) > 600 or _PACK_BYTES[0] > PACK_BUDGET[0]):
        _k, old = _PACK.popitem(last=False)
        _PACK_BYTES[0] -= getattr(old, "nbytes", 0)
    if got is not None:
        _PACK.pop(key, None)
        _PACK_BYTES[0] -= getattr(got, "nbytes", 0)
    pk = _Packed()
    pk.pal_key, pk.pal_c = None, None
    pk.tex = [f for f in faces] if any(getattr(f, "tex", None) is not None for f in faces) else None
    pk.faces = faces
    F = len(faces)
    pk.F = F
    idx = {id(f): i for i, f in enumerate(faces)}
    pts, start, count = [], [], []
    for f in faces:
        start.append(len(pts))
        count.append(len(f.pts))
        pts.extend(f.pts)
    pk.P = np.array(pts, dtype=np.float64).reshape(-1, 3)
    pk.start = np.array(start, dtype=np.int64)
    pk.count = np.array(count, dtype=np.int64)
    pk.n = np.array([f.n if len(f.n) == 3 else (0.0, 1.0, 0.0) for f in faces], dtype=np.float64).reshape(-1, 3)
    pk.smooth = np.array([bool(f.vn) and len(f.vn) == len(f.pts) and len(f.pts) in (3, 4) for f in faces])
    if pk.smooth.any():                                   # a normal per corner (smooth faces; others: the face's)
        vn = []
        for f, sm in zip(faces, pk.smooth.tolist()):
            vn.extend(f.vn if sm else [f.n if len(f.n) == 3 else (0.0, 1.0, 0.0)] * len(f.pts))
        pk.VN = np.array(vn, dtype=np.float64).reshape(-1, 3)
        # the light of a face too small to blend: its corners' mean normal, not its own (a clay mesh's faces step
        # like terraces - lit by their own normals they show as stripes across a tree's crown)
        ns = np.add.reduceat(pk.VN, pk.start, axis=0)
        ns /= np.maximum(1e-9, np.sqrt((ns * ns).sum(axis=1)))[:, None]
        pk.ns = np.where(pk.smooth[:, None], ns, pk.n)
    else:
        pk.VN, pk.ns = None, pk.n
    pk.VC = None
    if any(getattr(f, "vc", None) for f in faces):       # a colour per corner (sculpted clay): soft colour edges
        vc = []
        for f in faces:
            v = getattr(f, "vc", None)
            vc.extend(v if v and len(v) == len(f.pts) else [f.c[:3]] * len(f.pts))
        pk.VC = np.array(vc, dtype=np.float64).reshape(-1, 3)
    pk.c = np.array([f.c for f in faces], dtype=np.float64).reshape(-1, 4)
    pk.cull = np.array([bool(f.cull) for f in faces])
    pk.kind = np.array([_KIND.get(f.kind, 0) for f in faces], dtype=np.int8)
    pk.w = np.array([float(f.w or 0.0) for f in faces])
    pk.parent = np.array([idx.get(id(f.parent), -1) if f.parent is not None else -1 for f in faces], dtype=np.int64)
    pk.sub = np.array([float(f.sub or 0) for f in faces])
    pk.edge = np.array([bool(f.edge) for f in faces])
    pk.shine = np.array([f.mat[0] if f.mat else 0.0 for f in faces])
    pk.sharp = np.array([f.mat[1] if f.mat else 1.0 for f in faces])
    pk.emit = np.array([f.mat[2] if f.mat else 0.0 for f in faces])
    pk.skin = np.array([bool(f.mat and len(f.mat) > 3 and f.mat[3]) for f in faces])
    pk.lod = np.array([-1 if getattr(f, "lod", None) is None else int(f.lod) for f in faces], dtype=np.int8)
    pk.has_lod = bool((pk.lod >= 0).any())
    pk.first = pk.start.copy()
    solid = np.array([f.kind == "poly" and f.c[3] > 0.3 for f in faces])
    pk.shadow_pts = np.concatenate([pk.P[s:s + k] for s, k, ok in zip(start, count, solid) if ok]) \
        if solid.any() else np.zeros((0, 3))
    pk.nbytes = int(pk.P.nbytes * 2.2 + F * 260)       # arrays + the faces it keeps alive (roughly)
    if len(faces) > 4000 and key not in _BIG_SEEN:  # a big list made fresh every frame (a sculpted person): used once,
        if len(_BIG_SEEN) > 4000:                   # not kept - but one drawn again (a sculpted house) is kept
            _BIG_SEEN.clear()
        _BIG_SEEN.add(key)
        return pk
    _PACK_BYTES[0] += pk.nbytes
    _PACK[key] = pk
    return pk


def draw_faces_fast(ctx, faces, X0, Y0, Z0, s, fx, scene, cam, light, alpha=1.0, px=1.0, shadow=True, toon=None,
                    recolor=True, bend=0.0, turn=0.0, _one_lod=False):
    """draw_faces for the real scene camera, with numpy. Same look: sorting, culling, sun, shine, toon, edges."""
    import numpy as np
    from .scene3d import FOCAL, NEAR
    pk = _pack(faces)
    if pk.F == 0:
        return
    if getattr(pk, "has_lod", False) and not _one_lod:   # a sculpted thing: draw only its near OR its far mesh
        lo, hi = pk.P.min(axis=0), pk.P.max(axis=0)
        cx_, cz_ = X0 + fx * s * (lo[0] + hi[0]) / 2, Z0 + s * (lo[2] + hi[2]) / 2
        yaw_ = cam.yaw or 0.0
        dd = (cx_ - cam.x) * math.sin(yaw_) + (cz_ - cam.z) * math.cos(yaw_)
        span = (hi[1] - lo[1]) * s * FOCAL * scene.S * cam.fz / max(dd, 1.0)
        level = 0 if (dd < 1.0 or span > LOD_NEAR * scene.H) else 1
        if getattr(pk, "subs", None) is None:
            pk.subs = {}
        sub = pk.subs.get(level)
        if sub is None:
            sub = pk.subs[level] = [f for f in faces if getattr(f, "lod", None) in (None, level)]
        return draw_faces_fast(ctx, sub, X0, Y0, Z0, s, fx, scene, cam, light, alpha, px, shadow, toon, recolor, bend,
                               turn, _one_lod=True)
    P0, N0, VN0, NS0 = pk.P, pk.n, pk.VN, pk.ns
    if turn:                                             # turned round its up axis ("turn": 90): one shared pack
        a_ = math.radians(turn)
        R_ = np.array([[math.cos(a_), 0.0, -math.sin(a_)], [0.0, 1.0, 0.0], [math.sin(a_), 0.0, math.cos(a_)]])
        P0, N0, NS0 = P0 @ R_, N0 @ R_, NS0 @ R_
        VN0 = VN0 @ R_ if VN0 is not None else None
    W_, H_, S_ = scene.W, scene.H, scene.S
    # ---- to the world and into the camera
    Wp = P0 * np.array([fx * s, s, s]) + np.array([X0, Y0, Z0])
    if bend:                                             # a plant in the wind: the top bends, the foot stays
        top = max(1e-6, float(P0[:, 1].max()))
        u = np.clip(P0[:, 1] / top, 0.0, 1.0)
        Wp[:, 0] += bend * top * s * u * u
    yaw = cam.yaw or 0.0
    dx, d = Wp[:, 0] - cam.x, Wp[:, 2] - cam.z
    if yaw:
        c_, s_ = math.cos(yaw), math.sin(yaw)
        dx, d = dx * c_ - d * s_, dx * s_ + d * c_
    ok_pt = d >= NEAR
    dsafe = np.where(ok_pt, d, 1.0)
    k = FOCAL * S_ * cam.fz / dsafe
    sgn = -1.0 if cam.mirror else 1.0
    SX = W_ / 2 + cam.shift * S_ + sgn * dx * k
    SY = H_ * cam.horizon + (cam.h - Wp[:, 1]) * k
    # ---- per face: centre, normal, what the camera sees
    st, cnt = pk.start, pk.count
    cen = np.add.reduceat(Wp, st, axis=0) / cnt[:, None]
    n = N0 * np.array([fx, 1.0, 1.0])
    cam_pos = np.array([cam.x, cam.h, cam.z])
    to_c = cen - cam_pos
    facing_away = pk.cull & (pk.kind == 0) & ((n * to_c).sum(axis=1) >= 0)
    all_ok = np.logical_and.reduceat(ok_pt, st)
    any_ok = np.logical_or.reduceat(ok_pt, st)
    dist = np.sqrt((to_c * to_c).sum(axis=1))
    # screen box: skip what is off screen or smaller than a pixel
    x0 = np.minimum.reduceat(np.where(ok_pt, SX, 1e9), st)
    x1 = np.maximum.reduceat(np.where(ok_pt, SX, -1e9), st)
    y0 = np.minimum.reduceat(np.where(ok_pt, SY, 1e9), st)
    y1 = np.maximum.reduceat(np.where(ok_pt, SY, -1e9), st)
    onscreen = (x1 >= -40) & (x0 <= W_ + 40) & (y1 >= -40) & (y0 <= H_ + 40)
    tiny = ((x1 - x0) < 0.35) & ((y1 - y0) < 0.35) & (pk.kind == 0)
    clip = ~all_ok & any_ok & (pk.kind == 0) & (cnt >= 3)       # cut at the near plane (walls at the lens)
    visible = ~facing_away & (all_ok | clip) & (onscreen | clip) & ~tiny
    # decals (doors, windows ...) follow their wall: drawn right after it, only when it is seen
    par = pk.parent
    has_par = par >= 0
    par_vis = np.where(has_par, (~facing_away[np.maximum(par, 0)]) & (all_ok | clip)[np.maximum(par, 0)], True)
    visible &= par_vis
    sort_d = np.where(has_par, dist[np.maximum(par, 0)], dist)
    ids = np.nonzero(visible)[0]
    if not len(ids):
        return
    order = ids[np.lexsort((ids, pk.sub[ids] * has_par[ids], has_par[ids].astype(np.int8), -sort_d[ids]))]
    # ---- light
    L = np.array(light, dtype=np.float64)
    ns = NS0 * np.array([fx, 1.0, 1.0])                  # (the shading normal: smooth faces' mean corner normal)
    nd = ns @ L
    lit = AMBIENT + DIFFUSE * np.maximum(0.0, nd)
    lit = np.where(pk.emit > 0, lit + (1.0 - lit) * pk.emit, lit)
    spec = np.zeros(pk.F)
    shiny = pk.shine > 0.01
    if shiny.any():
        V = cam_pos - Wp[pk.first]
        V /= np.maximum(1e-9, np.sqrt((V * V).sum(axis=1)))[:, None]
        Hh = V + L
        Hh /= np.maximum(1e-9, np.sqrt((Hh * Hh).sum(axis=1)))[:, None]
        spec = np.where(shiny, pk.shine * np.maximum(0.0, (n * Hh).sum(axis=1)) ** pk.sharp, 0.0)
    toon_on = TOON[0] if toon is None else toon
    if toon_on:
        lit = np.where(nd > 0.28, 1.02, np.where(nd > -0.1, 0.86, 0.72))
        lit = np.where(pk.emit > 0, 1.0, lit)
        spec = np.where(spec > 0.45, 0.35, 0.0)
    C = pk.c
    from . import palette as _pal
    pal = _pal.CURRENT[0] if recolor else None
    if pal is not None:                                  # a world palette (alien pink grass ...): kept per face list
        if pk.pal_key != pal["key"]:
            C = pk.c.copy()
            C[:, :3] = _pal.recolor(pk.c[:, :3], pal, up=pk.n[:, 1], height=cen[:, 1])
            pk.pal_c, pk.pal_key = C, pal["key"]
        C = pk.pal_c
    rgb = np.minimum(1.0, C[:, :3] * lit[:, None] + spec[:, None])
    skin_on = SKIN[0] and not toon_on and getattr(pk, "skin", None) is not None and pk.skin.any()
    if skin_on:                                          # people's skin: wrap light, warm edge, soft corners, rim
        Vk = cam_pos - Wp[pk.first]
        Vk /= np.maximum(1e-9, np.sqrt((Vk * Vk).sum(axis=1)))[:, None]
        sk = pk.skin
        rgb[sk] = skin_light_np(C[sk, :3], nd[sk], n[sk, 1], np.abs((n[sk] * Vk[sk]).sum(axis=1)))
    vrgb = None
    if VN0 is not None and SMOOTH[0] and not toon_on:   # smooth faces: the light at every corner
        big = pk.smooth & ((x1 - x0) + (y1 - y0) > SMOOTH_MIN_PX)
        if big.any():
            ndv = (VN0 * np.array([fx, 1.0, 1.0])) @ L
            litv = AMBIENT + DIFFUSE * np.maximum(0.0, ndv)
            fid = np.repeat(np.arange(pk.F), cnt)
            litv = np.where(pk.emit[fid] > 0, litv + (1.0 - litv) * pk.emit[fid], litv)
            Cc = pk.VC if (pk.VC is not None and pal is None) else C[fid, :3]   # each corner its own clay colour
            vr = np.minimum(1.0, Cc * litv[:, None] + spec[fid][:, None])
            if skin_on:
                sv = pk.skin[fid]
                if sv.any():
                    VNw = VN0 * np.array([fx, 1.0, 1.0])
                    vr[sv] = skin_light_np(C[fid[sv], :3], ndv[sv], VNw[sv, 1], np.abs((VNw[sv] * Vk[fid[sv]]).sum(axis=1)))
            vrgb = vr                                    # (to Python lists below: only the drawn corners)
            bigl = big.tolist()
    if shadow:
        _shadow_fast(ctx, pk, X0, Y0, Z0, s, fx, scene, cam, L, alpha)
    # ---- paint, far to near
    sto = st.tolist()                                    # where each face's points start in Wp
    if len(order) * 2 < pk.F:                            # only a few faces are drawn (a far sculpted house: its light
        cs = cnt[order]                                  # mesh; things behind): move just their corners to Python
        offs = np.cumsum(cs) - cs
        pidx = np.repeat(st[order] - offs, cs) + np.arange(int(cs.sum()))
        st2 = np.zeros(pk.F, dtype=np.int64)
        st2[order] = offs
        SXl, SYl, kl = SX[pidx].tolist(), SY[pidx].tolist(), k[pidx].tolist()
        stl = st2.tolist()
        if vrgb is not None:
            vrgb = vr[pidx].tolist()
    else:
        SXl, SYl, kl = SX.tolist(), SY.tolist(), k.tolist()
        stl = sto
        if vrgb is not None:
            vrgb = vrgb.tolist()
    cntl = cnt.tolist()
    kinds, cl = pk.kind.tolist(), C.tolist()
    rgbl, wl, edgel, clipl = rgb.tolist(), pk.w.tolist(), pk.edge.tolist(), clip.tolist()
    lw_thin, lw_edge = 0.9 * px, max(1.0, (2.2 if toon_on else 1.6) * px)
    wscale = abs(fx * s)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    depth_of = None
    texf = pk.tex if (pk.tex is not None and not toon_on) else None
    litl, specl = (lit.tolist(), spec.tolist()) if texf is not None else (None, None)
    for i in order.tolist():
        a = cl[i][3]
        kd = kinds[i]
        b0 = stl[i]
        if kd >= 2:                                      # a round blob / a soft glow
            sx0, sy0 = SXl[b0], SYl[b0]
            rad = max(0.5, wl[i] * kl[b0] * wscale)
            r, g, b = cl[i][0], cl[i][1], cl[i][2]
            if kd == 2:
                ctx.arc(sx0, sy0, rad, 0, 2 * math.pi)
                ctx.set_source_rgba(r, g, b, a * alpha)
                ctx.fill()
            else:
                gr = cairo.RadialGradient(sx0, sy0, 0, sx0, sy0, rad)
                gr.add_color_stop_rgba(0, r, g, b, a * alpha)
                gr.add_color_stop_rgba(1, r, g, b, 0)
                ctx.set_source(gr)
                ctx.arc(sx0, sy0, rad, 0, 2 * math.pi)
                ctx.fill()
                _night_light(sx0, sy0, rad, (r, g, b), a * alpha)
            continue
        if kd == 1:                                      # a line
            ctx.move_to(SXl[b0], SYl[b0])
            ctx.line_to(SXl[b0 + 1], SYl[b0 + 1])
            ctx.set_source_rgba(cl[i][0], cl[i][1], cl[i][2], a * alpha)
            ctx.set_line_width(max(0.6, wl[i] * (kl[b0] + kl[b0 + 1]) / 2))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.stroke()
            continue
        rr, gg, bb = rgbl[i]
        if clipl[i]:                                     # partly behind the lens: cut it (rare, slow way)
            if depth_of is None:
                cy_, sy_ = math.cos(yaw), math.sin(yaw)

                def depth_of(P):
                    return (P[0] - cam.x) * sy_ + (P[2] - cam.z) * cy_
            P2 = _clip_near([tuple(p) for p in Wp[sto[i]:sto[i] + cntl[i]].tolist()], depth_of, NEAR + 1.0)
            S2 = [scene.project(cam, p[0], p[1], p[2]) for p in P2]
            if len(P2) < 3 or any(q is None for q in S2):
                continue
            ctx.move_to(S2[0][0], S2[0][1])
            for q in S2[1:]:
                ctx.line_to(q[0], q[1])
        else:
            ctx.move_to(SXl[b0], SYl[b0])
            for j in range(b0 + 1, b0 + cntl[i]):
                ctx.line_to(SXl[j], SYl[j])
            if vrgb is not None and bigl[i] and a >= 0.99:   # smooth: colours blended between the corners
                ctx.close_path()
                ctx.set_line_width(lw_thin)
                _gouraud(ctx, [(SXl[j], SYl[j]) for j in range(b0, b0 + cntl[i])],
                         [(*vrgb[j], a) for j in range(b0, b0 + cntl[i])], alpha)
                continue
            if texf is not None:                         # the model's own picture on a face big enough to see
                fo = texf[i]
                if fo.tex is not None and cntl[i] == 3 and pal is None:
                    xs_ = SXl[b0:b0 + 3]
                    ys_ = SYl[b0:b0 + 3]
                    if max(xs_) - min(xs_) + max(ys_) - min(ys_) > 7.0:
                        ctx.close_path()
                        # a hair-thin edge in the face's own colour first hides the seams
                        ctx.set_source_rgba(rr, gg, bb, a * alpha)
                        ctx.set_line_width(lw_thin)
                        ctx.stroke_preserve()
                        if _tex_fill(ctx, fo, list(zip(xs_, ys_)), litl[i], specl[i], a * alpha):
                            continue
                        ctx.new_path()
                        ctx.move_to(SXl[b0], SYl[b0])
                        for j in range(b0 + 1, b0 + cntl[i]):
                            ctx.line_to(SXl[j], SYl[j])
        ctx.close_path()
        ctx.set_source_rgba(rr, gg, bb, a * alpha)
        if a >= 0.99:                                    # a hair-thin edge of the same colour hides seams
            ctx.fill_preserve()
            if edgel[i] or toon_on:
                ctx.set_source_rgba(rr * 0.35, gg * 0.35, bb * 0.35, alpha)
                ctx.set_line_width(lw_edge)
            else:
                ctx.set_line_width(lw_thin)
            ctx.stroke()
        else:
            ctx.fill()


def _shadow_fast(ctx, pk, X0, Y0, Z0, s, fx, scene, cam, L, alpha):
    """The soft ground shadow (same as _shadow), from the packed points."""
    import numpy as np
    P = pk.shadow_pts
    if not len(P):
        return
    mn, mx = P.min(axis=0), P.max(axis=0)
    xs = sorted((X0 + fx * s * mn[0], X0 + fx * s * mx[0]))
    x0, x1 = xs
    y0, y1 = Y0 + s * mn[1], Y0 + s * mx[1]
    z0, z1 = Z0 + s * mn[2], Z0 + s * mx[2]
    if y0 > 30:
        return
    ring = _shadow_ring(x0, x1, y0, y1, z0, z1, L, lambda X, Z: scene.project(cam, X, 0.0, Z))
    if ring is None:
        return
    ctx.move_to(ring[0][0], ring[0][1])
    for q in ring[1:]:
        ctx.line_to(q[0], q[1])
    ctx.close_path()
    ctx.set_source_rgba(0, 0, 0, 0.16 * alpha * _shadow_k())
    ctx.fill()
    if CONTACT[0]:                                       # contact shadow: dark right where it meets the ground
        low = P[(Y0 + s * P[:, 1]) < 18.0]
        if len(low) >= 3:
            mn2, mx2 = low.min(axis=0), low.max(axis=0)
            xs2 = sorted((X0 + fx * s * mn2[0], X0 + fx * s * mx2[0]))
            za, zb = Z0 + s * mn2[2], Z0 + s * mx2[2]
            cx2, cz2 = (xs2[0] + xs2[1]) / 2, (za + zb) / 2
            for pad2, a2 in ((0.16, 0.09), (0.05, 0.13)):
                rx2 = (xs2[1] - xs2[0]) / 2 * (1 + pad2) + 4
                rz2 = (zb - za) / 2 * (1 + pad2) + 4
                ring2 = []
                for i in range(14):
                    a = 2 * math.pi * i / 14
                    q = scene.project(cam, cx2 + rx2 * math.cos(a), 0.0, cz2 + rz2 * math.sin(a))
                    if q is None:
                        ring2 = None
                        break
                    ring2.append(q)
                if not ring2:
                    break
                ctx.move_to(ring2[0][0], ring2[0][1])
                for q in ring2[1:]:
                    ctx.line_to(q[0], q[1])
                ctx.close_path()
                ctx.set_source_rgba(0, 0, 0, a2 * alpha)
                ctx.fill()
