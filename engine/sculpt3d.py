"""🗿 Sculpt 3D: characters modelled like clay, by code - smooth surfaces where head, cheeks, belly, arms and hands
blend into ONE skin the way a 3D artist models them (signed distance fields), then lit like a studio render.

    S = Sculpt()
    S.ellipsoid((0, 1.3, 0), (0.17, 0.16, 0.15), "#f6c445", k=0.04)      # a shape; k = how softly it melts into the rest
    S.capsule((0.2, 1.1, 0), (0.25, 0.8, 0), 0.05, 0.04, "#c49a72")      # a limb: two ends, two radii
    S.paint_line([...], 0.004, "#5a2a20")                                   # colour only (a mouth line, a hem)
    S.ellipsoid(..., group="eyes")                                          # a separate crisp part (eyes, glasses)
    parts = S.build()          # -> [Part(verts, tris, normals, colours, gloss)]  (one smooth mesh per group)
    img = render(parts, angle=30)                                           # PIL image, soft studio light

How: every shape is a distance function; the body is their smooth union (smooth min); a grid is sampled and the
surface is pulled out with "surface nets" (one vertex per surface cell, then pushed exactly onto the surface along
the gradient); normals come from the field itself, so the skin is truly smooth. Light per vertex: a warm key with
soft shadows marched through the field, a cool sky fill, ground bounce, ambient occlusion from the field, a rim
light and a little gloss (eyes: a wet highlight). Only numpy + cairo.
"""
import math

import numpy as np


def rgb(c):
    if isinstance(c, (tuple, list, np.ndarray)):
        return np.array(c[:3], float)
    c = str(c).lstrip("#")
    return np.array([int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def _lin(c):
    return np.power(c, 2.2)


# ---------------------------------------------------------------------------- distance functions (P: N x 3)
def _sd_ellipsoid(P, c, r):
    q = (P - c) / r
    k0 = np.linalg.norm(q, axis=1)
    k1 = np.linalg.norm(q / r, axis=1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def _sd_capsule(P, a, b, ra, rb):
    """a round cone: radius ra at a, rb at b"""
    ba = b - a
    L2 = max(float(ba @ ba), 1e-12)
    h = np.clip(((P - a) @ ba) / L2, 0.0, 1.0)
    d = np.linalg.norm(P - a - h[:, None] * ba, axis=1)
    return d - (ra + (rb - ra) * h)


def _sd_torus(P, c, R, r, axis):
    q = P - c
    ax = np.asarray(axis, float)
    ax = ax / np.linalg.norm(ax)
    along = q @ ax
    flat = np.linalg.norm(q - along[:, None] * ax, axis=1)
    return np.hypot(flat - R, along) - r


def _sd_plane(P, n, d):
    n = np.asarray(n, float)
    n = n / np.linalg.norm(n)
    return P @ n - d


def _sd_polyline(P, pts, r):
    out = None
    for a, b in zip(pts[:-1], pts[1:]):
        d = _sd_capsule(P, np.asarray(a, float), np.asarray(b, float), r, r)
        out = d if out is None else np.minimum(out, d)
    return out


def _sd_rbox(P, c, b, r):
    """a box (half sizes b) with rounded edges (radius r)"""
    q = np.abs(P - c) - (np.asarray(b) - r)
    return np.linalg.norm(np.maximum(q, 0.0), axis=1) + np.minimum(q.max(axis=1), 0.0) - r


def _sd_cyl(P, c, r, h, rr=0.0):
    """an upright cylinder (radius r, height h, standing on c) with rounded rims (rr)"""
    q = P - c
    d = np.stack([np.hypot(q[:, 0], q[:, 2]) - (r - rr), np.abs(q[:, 1] - h / 2.0) - (h / 2.0 - rr)], 1)
    return np.linalg.norm(np.maximum(d, 0.0), axis=1) + np.minimum(d.max(axis=1), 0.0) - rr


def _sd_lathe(P, c, prof):
    """a shape turned on a lathe: prof = a closed outline [(radius, height), ...] spun round the up axis through c
    (pots, glasses, cups, plates: the outline goes up the outside and back down the inside)"""
    q = P - c
    p2 = np.stack([np.hypot(q[:, 0], q[:, 2]), q[:, 1]], 1)
    V = np.asarray(prof, float)
    d = np.full(len(p2), np.inf)
    s = np.ones(len(p2))
    for i in range(len(V)):
        a, b = V[i - 1], V[i]
        e = b - a
        w = p2 - a
        if not (abs(a[0]) < 1e-9 and abs(b[0]) < 1e-9):     # (the spin axis itself is not a surface)
            t = np.clip((w @ e) / max(e @ e, 1e-12), 0.0, 1.0)
            d = np.minimum(d, np.linalg.norm(w - np.outer(t, e), axis=1))
        c1 = p2[:, 1] >= a[1]
        c2 = p2[:, 1] < b[1]
        c3 = e[0] * w[:, 1] > e[1] * w[:, 0]
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * d


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


class Shape:
    def __init__(self, fn, colour, k, group, mode, gloss, bone, clip=None, box=None):
        self.fn, self.colour, self.k, self.group, self.mode, self.gloss, self.bone, self.clip = \
            fn, rgb(colour), k, group, mode, gloss, bone, clip
        self.box = box                 # (lo, hi) the shape lies inside (None = unknown: always evaluated)

    def near(self, lo, hi):
        """can this shape touch the box (lo, hi)? (its own box grown by its blend reach)"""
        if self.box is None:
            return True
        m = self.k * 2.0 + 1e-3
        return bool(np.all(self.box[0] - m <= hi) and np.all(self.box[1] + m >= lo))

    def d(self, P):
        v = self.fn(P)
        if self.clip is not None:                       # cut by a plane: keep where the plane's distance < 0
            v = np.maximum(v, self.clip(P))
        return v


class Part:
    def __init__(self, name, V, T, N, C, G):
        self.name, self.V, self.T, self.N, self.C, self.G = name, V, T, N, C, G


class Sculpt:
    def __init__(self):
        self.shapes = []
        self.res = {}                  # group -> cell size (m)
        self.no_shadow = set()         # small parts that cast no shadow (glasses, brows: thin things look scratchy)
        self.bone = "spine"            # the bone new shapes follow (engine/sculpt_rig.py moves them)
        self.group = "body"            # the part new shapes go into (each part is meshed and skinned on its own)
        self.joints = {}               # rest-pose joint positions (metres) for the bones

    # ---- shapes
    def _add(self, fn, colour, k=0.02, group=None, mode="add", gloss=0.15, bone=None, clip=None, box=None):
        self.shapes.append(Shape(fn, colour, k, group or self.group, mode, gloss, bone or self.bone, clip, box))
        return self

    def ellipsoid(self, c, r, colour, **kw):
        c, r = np.asarray(c, float), np.maximum(np.asarray(r, float), 1e-4)
        kw.setdefault("box", (c - r, c + r))
        return self._add(lambda P: _sd_ellipsoid(P, c, r), colour, **kw)

    def sphere(self, c, r, colour, **kw):
        return self.ellipsoid(c, (r, r, r), colour, **kw)

    def capsule(self, a, b, ra, rb=None, colour="#888888", **kw):
        a, b = np.asarray(a, float), np.asarray(b, float)
        rb = ra if rb is None else rb
        rm = max(ra, rb)
        kw.setdefault("box", (np.minimum(a, b) - rm, np.maximum(a, b) + rm))
        return self._add(lambda P: _sd_capsule(P, a, b, ra, rb), colour, **kw)

    def rbox(self, c, b, colour, r=None, **kw):
        """a rounded box: centre c, half sizes b, edge radius r"""
        c, b = np.asarray(c, float), np.asarray(b, float)
        r = float(min(b) * 0.25 if r is None else min(r, min(b) * 0.999))
        kw.setdefault("box", (c - b, c + b))
        return self._add(lambda P: _sd_rbox(P, c, b, r), colour, **kw)

    def cyl(self, c, r, h, colour, rr=None, **kw):
        """an upright cylinder standing on c (a drum, a stool seat, a bucket)"""
        c = np.asarray(c, float)
        rr = float(min(r, h / 2.0) * 0.2 if rr is None else rr)
        kw.setdefault("box", (c - np.array([r, 0, r]), c + np.array([r, h, r])))
        return self._add(lambda P: _sd_cyl(P, c, r, h, rr), colour, **kw)

    def lathe(self, c, prof, colour, **kw):
        """a turned shape: prof = closed outline [(radius, height), ...] round the up axis through c"""
        c = np.asarray(c, float)
        V = np.asarray(prof, float)
        rm = float(V[:, 0].max())
        kw.setdefault("box", (c + np.array([-rm, V[:, 1].min(), -rm]), c + np.array([rm, V[:, 1].max(), rm])))
        return self._add(lambda P: _sd_lathe(P, c, prof), colour, **kw)

    def limb(self, pts, radii, colour, **kw):
        """a chain of round cones through pts (shoulder, elbow, wrist ...) with a radius at each point"""
        for i in range(len(pts) - 1):
            self.capsule(pts[i], pts[i + 1], radii[i], radii[i + 1], colour, **kw)
        return self

    def torus(self, c, R, r, colour, axis=(0, 0, 1), **kw):
        c = np.asarray(c, float)
        kw.setdefault("box", (c - (R + r), c + (R + r)))
        return self._add(lambda P: _sd_torus(P, c, R, r, axis), colour, **kw)

    def tube(self, pts, r, colour, **kw):
        A = np.array([np.asarray(p, float) for p in pts])
        kw.setdefault("box", (A.min(axis=0) - r, A.max(axis=0) + r))
        return self._add(lambda P: _sd_polyline(P, list(A), r), colour, **kw)

    def carve(self, shape_fn_maker, k=0.01, group="body"):
        """subtract a shape (eye sockets, a mouth groove): carve(lambda: ('ellipsoid', c, r))"""
        kind, *a = shape_fn_maker
        fn = {"ellipsoid": lambda P: _sd_ellipsoid(P, np.asarray(a[0], float), np.asarray(a[1], float)),
              "capsule": lambda P: _sd_capsule(P, np.asarray(a[0], float), np.asarray(a[1], float), a[2], a[3])}[kind]
        return self._add(fn, "#000000", k=k, group=group, mode="sub")

    # ---- colour only
    def paint(self, fn, colour, soft=0.002, group=None, gloss=None):
        """colour the surface where fn(P) < 0 (soft = how wide the edge fades)"""
        self.shapes.append(Shape(fn, colour, soft, group or self.group, "paint", gloss, None))
        return self

    def paint_line(self, pts, r, colour, **kw):
        P0 = [np.asarray(p, float) for p in pts]
        return self.paint(lambda P: _sd_polyline(P, P0, r), colour, **kw)

    def paint_ball(self, c, r, colour, **kw):
        c = np.asarray(c, float)
        return self.paint(lambda P: np.linalg.norm(P - c, axis=1) - r, colour, **kw)

    def paint_cone(self, c, direction, deg, colour, **kw):
        """the part of a round thing (an eye) facing `direction` within `deg` degrees: the iris, the pupil"""
        c = np.asarray(c, float)
        dv = np.asarray(direction, float)
        dv = dv / np.linalg.norm(dv)
        cosd = math.cos(math.radians(deg))

        def fn(P):
            q = P - c
            n = np.linalg.norm(q, axis=1) + 1e-9
            return (cosd - (q @ dv) / n) * n               # < 0 inside the cone (scaled to roughly metres)
        return self.paint(fn, colour, **kw)

    # ---- the field
    def groups(self):
        out = []
        for s in self.shapes:
            if s.group not in out:
                out.append(s.group)
        return out

    def field(self, P, group, box=None):
        d = None
        for s in self.shapes:
            if s.group != group or s.mode == "paint":
                continue
            if box is not None and not s.near(*box):
                continue
            v = s.d(P)
            if s.mode == "sub":
                d = d if d is None else smax(d, -v, s.k)
            else:
                d = v if d is None else smin(d, v, s.k)
        return d

    def colours(self, P, group):
        """colour + gloss at surface points: each shape's colour weighted by how near it is (a soft seam), then paints"""
        best, wsum, col, gl = None, None, None, None
        lo, hi = P.min(axis=0), P.max(axis=0)
        solid = [s for s in self.shapes if s.group == group and s.mode == "add" and s.near(lo, hi)] or \
            [s for s in self.shapes if s.group == group and s.mode == "add"]
        D = np.stack([s.d(P) for s in solid])                # S x N
        if getattr(self, "color_abs", False):               # (openings cut into a wall, a door set back in them:
            D = np.abs(D)                                    # the shape whose own surface is here gives the colour)
        dmin = D.min(axis=0)
        W = np.exp(-(D - dmin) / getattr(self, "color_tau", 0.0025))      # (a smaller figure: a sharper colour seam)
        W /= W.sum(axis=0)
        col = np.einsum("sn,sc->nc", W, np.stack([s.colour for s in solid]))
        gl = W.T @ np.array([s.gloss for s in solid])
        for s in self.shapes:
            if s.group == group and s.mode == "paint":
                v = s.d(P)
                a = np.clip(0.5 - v / max(s.k, 1e-5), 0.0, 1.0)
                col = col * (1 - a[:, None]) + s.colour[None, :] * a[:, None]
                if s.gloss is not None:
                    gl = gl * (1 - a) + s.gloss * a
        return col, gl

    def all_field(self, P):
        d = None
        for g in self.groups():
            v = self.field(P, g)
            if v is not None:
                d = v if d is None else np.minimum(d, v)
        return d

    # ---- meshing
    def build(self, cell=0.006, fine=None, region=None, scale=1.0, groups=None, quads=False):
        """-> [Part] one mesh per group. region = (y_low, y_high): only that slice (the head is rebuilt per face);
        scale > 1 = coarser everywhere (far away: fewer faces); groups = only these groups."""
        fine = fine or {}
        parts = []
        for g in self.groups():
            if groups is not None and g not in groups:
                continue
            if not any(s.group == g and s.mode == "add" for s in self.shapes):
                continue
            h = self.res.get(g, fine.get(g, cell)) * scale
            lo, hi = self._bounds(g)
            if region is not None:
                lo, hi = lo.copy(), hi.copy()
                lo[1], hi[1] = max(lo[1], region[0]), min(hi[1], region[1])
                if hi[1] <= lo[1] + h * 2:
                    continue
            box = (lo - h * 2, hi + h * 2)
            F = (lambda P, g=g, box=box: self.field(P, g, box))
            V, T = surface_nets(F, (lo, hi), h, quads=quads)
            if not len(T):
                continue
            V = _project(V, F, h)
            N = _gradient(F, V, h * 0.5)
            fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
            wrong = (fn * N[T].sum(1)).sum(1) < 0           # every triangle wound to face out (along the field's gradient)
            T[wrong] = T[wrong][:, ::-1]
            C, G = self.colours(V, g)
            parts.append(Part(g, V, T, N, C, G))
        return parts

    def _bounds(self, g):
        """a box round a group: from its shapes' boxes, or sampled on a coarse grid when a shape has none"""
        sh = [s for s in self.shapes if s.group == g and s.mode == "add"]
        if sh and all(s.box is not None for s in sh):
            lo = np.min([s.box[0] for s in sh], axis=0) - 0.02
            hi = np.max([s.box[1] for s in sh], axis=0) + 0.02
            return lo, hi
        lo, hi = np.array([-1.2, -0.1, -1.0]), np.array([1.2, 2.6, 1.0])
        n = 48
        xs = [np.linspace(lo[i], hi[i], n) for i in range(3)]
        G = np.stack(np.meshgrid(*xs, indexing="ij"), -1).reshape(-1, 3)
        d = self.field(G, g)
        step = (hi - lo) / (n - 1)
        inside = G[d < step.max()]
        if not len(inside):
            return lo, hi
        return inside.min(axis=0) - step * 2, inside.max(axis=0) + step * 2


def surface_nets(F, bounds, h, quads=False):
    """the surface F = 0 as a mesh: one vertex in every grid cell the surface crosses (at the mean of its edge
    crossings), a quad across every grid edge with a sign change -> (V, triangles)"""
    lo, hi = bounds
    n = np.maximum(((hi - lo) / h).astype(int) + 2, 3)
    xs = [lo[i] + np.arange(n[i]) * h for i in range(3)]
    G = np.stack(np.meshgrid(*xs, indexing="ij"), -1)
    D = F(G.reshape(-1, 3)).reshape(n)
    inside = D < 0
    nx, ny, nz = n
    # corners of every cell
    c = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
    S = np.stack([inside[i:nx - 1 + i, j:ny - 1 + j, k:nz - 1 + k] for i, j, k in c], -1)
    active = S.any(-1) & ~S.all(-1)
    idx = -np.ones((nx - 1, ny - 1, nz - 1), int)
    cells = np.argwhere(active)
    idx[tuple(cells.T)] = np.arange(len(cells))
    # vertex = mean of the edge crossings of the cell
    edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    acc = np.zeros((len(cells), 3))
    cnt = np.zeros(len(cells))
    ci, cj, ck = cells.T
    corner_d = np.stack([D[ci + i, cj + j, ck + k] for i, j, k in c], -1)
    corner_p = np.array(c, float)
    for a, b in edges:
        da, db = corner_d[:, a], corner_d[:, b]
        m = (da < 0) != (db < 0)
        t = da[m] / (da[m] - db[m])
        p = corner_p[a] + (corner_p[b] - corner_p[a]) * t[:, None]
        acc[m] += p
        cnt[m] += 1
    V = lo + (cells + acc / np.maximum(cnt, 1)[:, None]) * h
    # faces across sign-changing grid edges
    tris = []
    for axis in range(3):
        sl0 = [slice(0, nx), slice(0, ny), slice(0, nz)]
        sl1 = list(sl0)
        sl0[axis] = slice(0, n[axis] - 1)
        sl1[axis] = slice(1, n[axis])
        a, b = inside[tuple(sl0)], inside[tuple(sl1)]
        e = np.argwhere(a != b)
        flip = a[tuple(e.T)]
        o = [ax for ax in range(3) if ax != axis]
        ok = np.ones(len(e), bool)
        for ax in o:
            ok &= e[:, ax] >= 1
            ok &= e[:, ax] <= n[ax] - 2
        e, flip = e[ok], flip[ok]
        q = []
        for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
            cc = e.copy()
            cc[:, o[0]] -= 1 - du
            cc[:, o[1]] -= 1 - dv
            q.append(idx[tuple(cc.T)])
        q = np.stack(q, -1)
        good = (q >= 0).all(-1)
        q, flip = q[good], flip[good]
        if axis == 1:
            flip = ~flip
        q[flip] = q[flip][:, ::-1]
        if quads:
            tris.append(q)
        else:
            tris.append(q[:, [0, 1, 2]])
            tris.append(q[:, [0, 2, 3]])
    T = np.concatenate(tris) if tris else np.zeros((0, 4 if quads else 3), int)
    return V, T


def _gradient(F, P, e):
    g = np.zeros_like(P)
    for i in range(3):
        d = np.zeros(3)
        d[i] = e
        g[:, i] = F(P + d) - F(P - d)
    n = np.linalg.norm(g, axis=1, keepdims=True)
    return g / np.maximum(n, 1e-12)


def _project(V, F, h, steps=2):
    """push vertices exactly onto the surface (Newton steps along the gradient)"""
    for _ in range(steps):
        d = F(V)
        g = _gradient(F, V, h * 0.5)
        V = V - g * np.clip(d, -h, h)[:, None]
    return V


# ---------------------------------------------------------------------------- light (per vertex, world space)
KEY = np.array([-0.55, 0.75, 0.65])                 # warm sun from front-left, high
KEY = KEY / np.linalg.norm(KEY)


def light(sculpt, parts, key=KEY, key_col=(1.0, 0.93, 0.82), sky=(0.55, 0.66, 0.85), ground=(0.62, 0.5, 0.38)):
    """per-vertex light that does not depend on the camera: soft shadow, sky / ground, ambient occlusion"""
    key_col, sky, ground = np.array(key_col), np.array(sky), np.array(ground)
    def F(P):
        d = None
        for g in sculpt.groups():
            if g in sculpt.no_shadow:
                continue
            v = sculpt.field(P, g)
            if v is not None:
                d = v if d is None else np.minimum(d, v)
        return d
    for p in parts:
        N, V = p.N, p.V
        ndl = N @ key
        wrap = 0.35                                          # skin and cloth let light round the edge a little
        diff = np.clip((ndl + wrap) / (1 + wrap), 0, 1)
        sh = _soft_shadow(F, V + N * 0.004, key)
        ao = _ao(F, V, N)
        hemi = (N[:, 1] * 0.5 + 0.5)[:, None]
        amb = sky[None, :] * hemi + ground[None, :] * (1 - hemi)
        p.L = (diff * sh)[:, None] * key_col[None, :] * 1.25 + amb * 0.38 * ao[:, None]
        p.ao = ao
    return parts


def _soft_shadow(F, P, Ldir, k=10.0, tmax=1.2):
    res = np.ones(len(P))
    t = np.full(len(P), 0.01)
    alive = np.ones(len(P), bool)
    for _ in range(36):
        if not alive.any():
            break
        Q = P[alive] + Ldir[None, :] * t[alive, None]
        d = F(Q)
        r = res[alive]
        r = np.minimum(r, k * np.maximum(d, 0) / t[alive])
        res[alive] = r
        t[alive] += np.clip(d, 0.006, 0.12)
        done = (t > tmax) | (res < 0.02)
        alive &= ~done
    res = np.clip(res, 0, 1)
    return res * res * (3 - 2 * res)


def _ao(F, P, N, n=5, step=0.018):
    occ = np.zeros(len(P))
    w = 1.0
    for i in range(1, n + 1):
        h = step * i
        d = F(P + N * h)
        occ += w * np.clip(h - d, 0, None)
        w *= 0.6
    return np.clip(1.0 - 4.0 * occ, 0.25, 1.0)


# ---------------------------------------------------------------------------- render (cairo, Gouraud triangles)
def render(parts, width=640, height=860, angle=20.0, elev=6.0, fov=28.0, target=None, dist=None, bg=None, ss=2,
           outline=0.0045, ink=(0.16, 0.1, 0.08)):
    """a picture of the lit parts seen from `angle` degrees round the figure (0 = from the front)"""
    import cairo
    from PIL import Image
    allV = np.concatenate([p.V for p in parts])
    lo, hi = allV.min(0), allV.max(0)
    tgt = np.array(target if target is not None else (lo + hi) / 2)
    H = hi[1] - lo[1]
    dist = dist or H * 0.62 / math.tan(math.radians(fov / 2))
    a, e = math.radians(angle), math.radians(elev)
    eye = tgt + dist * np.array([math.sin(a) * math.cos(e), math.sin(e), math.cos(a) * math.cos(e)])
    fwd = tgt - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 1, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    W, Hh = width * ss, height * ss
    f = (Hh / 2) / math.tan(math.radians(fov / 2))
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, Hh)
    ctx = cairo.Context(surf)
    top, bot = bg or ((0.80, 0.86, 0.93), (0.95, 0.92, 0.86))
    g = cairo.LinearGradient(0, 0, 0, Hh)
    g.add_color_stop_rgb(0, *top)
    g.add_color_stop_rgb(1, *bot)
    ctx.set_source(g)
    ctx.paint()
    # a soft contact shadow under the feet
    feet = np.array([tgt[0], lo[1], tgt[2]])
    q = feet - eye
    sx, sy = W / 2 + f * (q @ right) / (q @ fwd), Hh / 2 - f * (q @ up) / (q @ fwd)
    rad = f * (hi[0] - lo[0]) * 0.55 / (q @ fwd)
    ctx.save()
    ctx.translate(sx, sy)
    ctx.scale(1.0, 0.22)
    rg = cairo.RadialGradient(0, 0, 0, 0, 0, rad)
    rg.add_color_stop_rgba(0, 0.2, 0.17, 0.14, 0.45)
    rg.add_color_stop_rgba(1, 0.2, 0.17, 0.14, 0.0)
    ctx.set_source(rg)
    ctx.arc(0, 0, rad, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()
    allX, allY, allZ, allC, tris = [], [], [], [], []
    off = 0
    if outline:                                         # 🖋 ink line: each part grown a little, only its far side drawn
        hulls = []
        for p in parts:
            if len(p.V) < 200:
                continue
            w = outline * (0.45 if p.name in ("eyes", "lids", "glasses", "brows", "mouth", "props") else 1.0)
            hulls.append(Part(p.name + "_ink", p.V + p.N * w, p.T[:, ::-1], p.N, np.tile(ink, (len(p.V), 1)), p.G * 0))
        parts = hulls + list(parts)
    for p in parts:
        Q = p.V - eye
        z = Q @ fwd
        X = W / 2 + f * (Q @ right) / z
        Y = Hh / 2 - f * (Q @ up) / z
        view = -Q / np.linalg.norm(Q, axis=1, keepdims=True)
        ndv = np.clip((p.N * view).sum(1), 0, 1)
        rim = np.power(1 - ndv, 4.0) * 0.5 * np.clip(p.N[:, 1] * 0.5 + 0.6, 0, 1) * (p.ao if hasattr(p, "ao") else 1)
        hv = KEY[None, :] + view
        hv /= np.linalg.norm(hv, axis=1, keepdims=True)
        spec = np.power(np.clip((p.N * hv).sum(1), 0, 1), 20 + 160 * p.G) * p.G * 1.6 * (p.ao if hasattr(p, "ao") else 1)
        if p.name.endswith("_ink"):
            col = p.C
        else:
            base = _lin(p.C)
            col = base * (p.L + rim[:, None] * np.array([0.8, 0.88, 1.0])) + spec[:, None] * (0.25 + 0.75 * base)
            col = col * 1.15 / (1 + col * 0.15)               # a soft film shoulder, the darks stay dark
            col = np.power(np.clip(col, 0, 1), 1 / 2.2)
        T = p.T
        cz = z[T].mean(1)
        front = np.cross(p.V[T[:, 1]] - p.V[T[:, 0]], p.V[T[:, 2]] - p.V[T[:, 0]])
        facing = (front * (-(p.V[T].mean(1) - eye))).sum(1)
        vis = facing > 0 if p.name.endswith("_ink") else facing > -1e9   # ink: only the hull's far side; the rest: all
        T = T[vis]
        allX.append(X)
        allY.append(Y)
        allC.append(col)
        tris.append((T + off, cz[vis]))
        off += len(p.V)
    X, Y, C = np.concatenate(allX), np.concatenate(allY), np.concatenate(allC)
    T = np.concatenate([t for t, _ in tris])
    Z = np.concatenate([z for _, z in tris])
    order = np.argsort(-Z)
    mesh = cairo.MeshPattern()
    for i in T[order]:
        mesh.begin_patch()
        mesh.move_to(X[i[0]], Y[i[0]])
        mesh.line_to(X[i[1]], Y[i[1]])
        mesh.line_to(X[i[2]], Y[i[2]])
        for k in range(3):
            mesh.set_corner_color_rgb(k, *C[i[k]])
        mesh.end_patch()
    ctx.set_source(mesh)
    ctx.paint()
    img = Image.frombuffer("RGBA", (W, Hh), bytes(surf.get_data()), "raw", "BGRA", 0, 1).convert("RGB")
    return img.resize((width, height), Image.LANCZOS) if ss > 1 else img
