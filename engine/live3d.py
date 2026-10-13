"""🎥 Live play for 3D stories: the browser draws the 3D (three.js, static/live3d.js) - the server only says what is
where. Each frame the server works out the story as always (who stands where, poses, faces, camera) but:
  - every 3D thing (a clay house, a tree, the well) is sent ONCE as a mesh, then only "this mesh, here, this big";
  - every clay person is sent ONCE as a rest mesh with its bone weights, then only the turn of each of its 10 bones
    (engine/sculpt_rig.py: the same linear blend skinning, done in the browser);
  - the flat parts (sky, ground, grass, moods, subtitles) stay drawing ops like the 2.5D live play (livedraw.py):
    what is drawn before the 3D things goes behind them, what is drawn after goes in front.
So a frame is a few KB and takes milliseconds, instead of seconds of Python drawing 100 000 faces."""
import json
import math
import struct

import numpy as np

from .livedraw import Recorder, _r

LIVE = [False]           # True while a live 3D frame is recorded (sculpt_rig.code_fn reads it)
LOD_CAP = [None]         # "mid" / "far": the clay people at most this detailed (phones, low quality)
_LODS = ("far", "mid", "near")


def cap(lod):
    """a clay person's detail, no finer than the player asked for"""
    c = LOD_CAP[0]
    if LIVE[0] and c in _LODS and lod in _LODS and _LODS.index(lod) > _LODS.index(c):
        return c
    return lod
RIG_PENDING = {}         # id(pen.faces) -> the bones of the person drawn with that face list (see sculpt_rig)
MESHES = {}              # key -> faces (kept alive so the key stays theirs)
_MESH_KEY = {}           # id(faces) -> key
MODELS = {}              # key -> sculpt_rig.Model
GROUNDS = {}             # key -> (scene, centre X, centre Z, span, t): the ground picture of a scene, made on request
_MODEL_KEY = {}          # id(model) -> key
_EXTENT = {}             # mesh key -> its extent
PICS = {}                # key -> cairo surface (a picture the video stands in the scene, sent as a card)
_PIC_KEY = {}
_N = [0]


def mesh_key(faces):
    k = _MESH_KEY.get(id(faces))
    if k is not None and MESHES.get(k) is faces:
        return k
    _N[0] += 1
    k = f"m{_N[0]}"
    MESHES[k], _MESH_KEY[id(faces)] = faces, k
    return k


def model_key(m):
    k = _MODEL_KEY.get(id(m))
    if k is not None and MODELS.get(k) is m:
        return k
    _N[0] += 1
    k = f"p{_N[0]}"
    MODELS[k], _MODEL_KEY[id(m)] = m, k
    return k


class Recorder3D(Recorder):
    """the 2D recorder + the 3D things of the frame"""
    live3d = True

    def __init__(self):
        super().__init__()
        self.meshes = []                               # [key, X0, Y0, Z0, s, fx, turn, alpha]
        self.rigs = []                                 # {"models", "q", "k", "moves", "M", "T", "at", "alpha"}
        self.pics = []                                 # [key, X0, Y0, Z0, width, height, flip, alpha]
        self.cam = None
        self.fade = 1.0                                # (scene3d: a thing at the lens fades away)

    def ground(self, scene, cam, t):
        """the ground is one picture per scene (looked at from straight above), laid flat by the browser"""
        span = 24000.0
        fwd_x, fwd_z = math.sin(cam.yaw or 0.0), math.cos(cam.yaw or 0.0)
        cx, cz = cam.x + 0.4 * span * fwd_x, cam.z + 0.4 * span * fwd_z
        key = f"g{id(scene)}_{int(cx // 6000)}_{int(cz // 6000)}"
        if key not in GROUNDS:
            GROUNDS[key] = (scene, round(cx / 6000) * 6000.0, round(cz / 6000) * 6000.0, span, t)
        _, X, Z, sp, _t = GROUNDS[key]
        self.ground_tile = [key, _r(X), _r(Z), sp, [round(float(c), 3) for c in scene.ground]]

    def layer3d(self, cam, scene):
        """here the 3D things go (what came before is behind them)"""
        self.op("L3")
        self.cam = [_r(cam.x), _r(cam.h), _r(cam.z), round(float(cam.yaw or 0.0), 5), round(float(cam.fz), 4),
                    round(float(cam.horizon), 4), _r(float(cam.shift or 0.0)), 1 if cam.mirror else 0]
        sun = getattr(scene, "_sun3", None)
        self.env = {"sun": [round(float(v), 3) for v in sun] if sun else None, "S": _r(float(scene.S)),
                    "fog": [round(float(v), 3) for v in scene.fog_now()], "sky": [[round(float(c), 3) for c in s]
                                                                                   for s in scene.sky]}


def _sort_depth():
    """the depth the video sorts the object being drawn by (scene3d.render: its anchor, or its back edge)"""
    from . import code3d
    if code3d.CURRENT is None:
        return 0.0
    scene, cam, o = code3d.CURRENT[:3]
    Z = getattr(o, "sortZ", None)
    Z = o.Z if Z is None else Z
    if cam.yaw:
        return round((o.X - cam.x) * math.sin(cam.yaw) + (Z - cam.z) * math.cos(cam.yaw), 1)
    return round(Z - cam.z, 1)


def placed(ctx, faces, X0, Y0, Z0, s, fx, turn, alpha):
    """draw_in_scene, live: note the thing instead of drawing it -> its size (w, h) like the drawing returns"""
    rec = RIG_PENDING.pop(id(faces), None)
    if rec is not None:                                # a clay person / animal: its pieces + the turn of each bone
        ctx.rigs.append({"models": [model_key(m) for m in rec["models"]], "q": rec.get("q", 1),
                         "k": round(float(rec["k"]), 5),
                         "moves": [[round(float(v), 5) for v in np.concatenate([np.ravel(R), np.ravel(t)])]
                                   for R, t in (rec["moves"][b] for b in rec["bones"])],
                         "M": [round(float(v), 5) for v in rec["M"]], "T": [_r(float(v)) for v in rec["T"]],
                         "at": [_r(X0), _r(Y0), _r(Z0), round(float(s), 5), fx],
                         "alpha": round(float(alpha) * float(rec.get("alpha", 1.0)) * ctx.fade, 3), "sd": _sort_depth()})
        h = rec["k"] * rec.get("top", 1.6) * s
        return (0.45 * h, h)
    if not faces:
        return (0, 0)
    ctx.meshes.append([mesh_key(faces), _r(X0), _r(Y0), _r(Z0), round(float(s), 5), fx, round(float(turn), 3),
                       round(float(alpha) * ctx.fade, 3), _sort_depth()])
    k = mesh_key(faces)
    ex = _EXTENT.get(k)
    if ex is None:                                     # (its size, measured once per mesh)
        from .code3d import extent
        ex = _EXTENT[k] = extent(faces) or (0, 0, 0, 0)
    return ((ex[1] - ex[0]) * s, (ex[3] - ex[2]) * s)


def picture(ctx, surf, w, h, x, y, flip, alpha, anchor):
    """images.draw, live: the video stands this picture in the scene facing the camera (a far house, a well, a
    bush) - so does the browser: a card at the same place and size -> True (False: not in a 3D scene)"""
    from . import code3d
    if code3d.CURRENT is None:
        return False
    scene, cam, o, sx, sy, k = code3d.CURRENT
    M = ctx.get_matrix()
    if abs(M.xy) > 1e-3 * abs(M.xx) + 1e-6 or abs(M.yx) > 1e-3 * abs(M.yy) + 1e-6:
        return False
    dx, dy = M.transform_point(x, y)
    rel = abs(M.yy) / k                                # local units -> world units
    X0, Y0 = o.X + (dx - sx) / k, o.Y - (dy - sy) / k
    if anchor != "bottom":
        Y0 -= h * rel / 2
    pk = _PIC_KEY.get(id(surf))
    if pk is None or PICS.get(pk) is not surf:
        _N[0] += 1
        pk = f"i{_N[0]}"
        PICS[pk], _PIC_KEY[id(surf)] = surf, pk
    ctx.pics.append([pk, _r(X0), _r(Y0), _r(o.Z), _r(w * rel), _r(h * rel), 1 if flip else 0,
                     round(float(alpha) * ctx.fade, 3), _sort_depth()])
    return True


def see_through(ctx, scene, cam, near, mark, feature):
    """scene3d's see-through rule for live play: scenery standing in front of a person is measured on the
    screen (a card: its picture's own pixels; a mesh: its box) - a feature frame moves it out of the shot (>6 %
    of the person covered), otherwise it turns see-through (>20 %), as the video does"""
    import numpy as np
    from .util import smoothstep
    new_m, new_p = ctx.meshes[mark[0]:], ctx.pics[mark[1]:]
    if not new_m and not new_p:
        return
    rects = []                                         # (x0, x1, y0, y1, alpha array or None, flip)
    for p in new_p:
        a = scene.project(cam, p[1] - p[4] / 2, p[2], p[3])
        b = scene.project(cam, p[1] + p[4] / 2, p[2] + p[5], p[3])
        if a and b:
            surf = PICS.get(p[0])
            al = None
            if surf is not None:
                surf.flush()
                al = np.ndarray((surf.get_height(), surf.get_stride() // 4), np.uint32,
                                surf.get_data())[:, :surf.get_width()] >> 24
            rects.append((min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), al, p[6]))
    for m in new_m:
        ex = _EXTENT.get(m[0])
        if ex:
            a = scene.project(cam, m[1] + ex[0] * m[4], m[2] + ex[2] * m[4], m[3])
            b = scene.project(cam, m[1] + ex[1] * m[4], m[2] + ex[3] * m[4], m[3])
            if a and b:
                rects.append((min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), None, 0))
    cov = 0.0
    for x0, x1, y0, y1, _ in near:
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1, 3.0), np.arange(y0, y1, 3.0))
        hit = np.zeros(xs.shape, bool)
        for rx0, rx1, ry0, ry1, al, flip in rects:
            inside = (xs >= rx0) & (xs < rx1) & (ys >= ry0) & (ys < ry1)
            if not inside.any():
                continue
            if al is None:
                hit |= inside
                continue
            u = (xs[inside] - rx0) / max(1e-6, rx1 - rx0)
            if flip:
                u = 1.0 - u
            v = (ys[inside] - ry0) / max(1e-6, ry1 - ry0)
            hh, ww = al.shape
            got = al[np.clip((v * hh).astype(int), 0, hh - 1), np.clip((u * ww).astype(int), 0, ww - 1)] > 128
            sub = np.zeros(inside.sum(), bool) | got
            h2 = hit[inside]
            hit[inside] = h2 | sub
        cov = max(cov, float(hit.mean()) if hit.size else 0.0)
    if feature and cov > 0.06:                         # film layout cheat: the set piece leaves the shot
        del ctx.meshes[mark[0]:]
        del ctx.pics[mark[1]:]
    elif cov > 0.2:
        f = 1.0 - 0.7 * smoothstep((cov - 0.2) / 0.3)
        for m in new_m:
            m[7] = round(m[7] * f, 3)
        for p in new_p:
            p[7] = round(p[7] * f, 3)


def pic_png(key):
    surf = PICS.get(key)
    if surf is None:
        return None
    import io
    buf = io.BytesIO()
    surf.write_to_png(buf)
    return buf.getvalue()


def frame(fi, P, lod=None):
    """one frame: {"ops": 2D ops (with an "L3" where the 3D goes), "cam", "env", "meshes", "rigs"}"""
    from . import render as R
    rec = Recorder3D()
    LIVE[0] = True
    LOD_CAP[0] = lod
    try:
        R.render_frame(fi, P, ctx=rec)
    finally:
        LIVE[0] = False
        LOD_CAP[0] = None
        RIG_PENDING.clear()
    out = {"ops": rec.ops}
    cut = next((i for i, o in enumerate(rec.ops) if o and o[0] == "L3"), None)
    if cut is not None:                                # a fingerprint of the drawing behind the 3D: the browser
        import zlib                                    # draws it again only when it changed (phones: still shots)
        out["bh"] = zlib.crc32(json.dumps(rec.ops[:cut], separators=(",", ":")).encode())
    if rec.cam is not None:
        out.update(cam=rec.cam, env=rec.env, meshes=rec.meshes, rigs=rec.rigs, pics=rec.pics,
                   ground=getattr(rec, "ground_tile", None))
    return out


# ---------------------------------------------------------------------------- the meshes, sent once (binary)
def _lin(c):
    return np.clip(c, 0.0, 1.0)                         # sRGB as it is: the browser lights it the same way as
                                                        # code3d (colour x (0.62 + 0.42 sun)) - no colour management


def mesh_bin(key, far=False):
    """a thing's faces -> triangles: 'T3M2', n vertices, the box (min x3, size x3, f32), positions in the box
    (u16 x3), normals i8 x4, colours u8 x4 (sRGB, alpha). far: the thing's far copy when it has one (a clay
    house: ~40 faces instead of ~4000 - for phones and the far distance)"""
    faces = MESHES.get(key)
    if faces is None:
        return None
    has_far = far and any(getattr(f, "lod", None) == 1 for f in faces)
    skip = 0 if has_far else 1                          # (the near copy, or the far one)
    P, N, C = [], [], []
    for f in faces:
        if f.kind != "poly" or len(f.pts) < 3 or getattr(f, "lod", None) == skip:
            continue                                     # (lines, dots, glows; the other copy of a big thing)
        pts = f.pts
        vn = f.vn if f.vn and len(f.vn) == len(pts) else [f.n] * len(pts)
        vc = f.vc if getattr(f, "vc", None) and len(f.vc) == len(pts) else [f.c[:3]] * len(pts)
        a = f.c[3] if len(f.c) > 3 else 1.0
        for i in range(1, len(pts) - 1):                 # a fan of triangles
            for j in (0, i, i + 1):
                P.append(pts[j])
                N.append(vn[j])
                C.append((*vc[j][:3], a))
    return _pack(np.array(P, np.float32).reshape(-1, 3), np.array(N, np.float32).reshape(-1, 3),
                 np.array(C, np.float32).reshape(-1, 4))


def _q16(P):
    """positions -> (box min, box size, u16 x3): half the bytes, ~1/65000 of the thing's size (invisible)"""
    if not len(P):
        return np.zeros(3, np.float32), np.ones(3, np.float32), np.zeros((0, 3), np.uint16)
    lo, hi = P.min(axis=0), P.max(axis=0)
    size = np.maximum(hi - lo, 1e-6)
    return lo.astype(np.float32), size.astype(np.float32), np.round((P - lo) / size * 65535).astype("<u2")


def _pack(P, N, C):
    n = len(P)
    Nn = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9) if n else N
    Ni = np.zeros((n, 4), np.int8)
    Ni[:, :3] = np.clip(np.round(Nn * 127), -127, 127)
    Ci = np.zeros((n, 4), np.uint8)
    if n:
        Ci[:, :3] = np.round(_lin(C[:, :3]) * 255)
        Ci[:, 3] = np.round(np.clip(C[:, 3], 0, 1) * 255)
    lo, size, Pq = _q16(P)
    return (b"T3M2" + struct.pack("<I", n) + lo.astype("<f4").tobytes() + size.astype("<f4").tobytes()
            + Pq.tobytes() + Ni.tobytes() + Ci.tobytes())


def model_bin(key):
    """a clay person's / animal's piece at rest: 'T3P3', n vertices, m triangles, then the box (min x3, size x3,
    f32), rest positions in the box (u16 x3), normals i8 x4, colours u8 x4, its 4 strongest bones (u8 x4) and their
    weights (u8 x4, summing to 255), triangle indices u32 x3 - the browser's graphics chip bends it by the bones"""
    m = MODELS.get(key)
    if m is None:
        return None
    V = np.asarray(m.V, np.float32)
    n = len(V)
    Q = np.asarray(m.Q, np.int64)
    if Q.ndim == 2 and Q.shape[1] == 4:
        T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    else:
        T = Q.reshape(-1, 3)
    Nn = np.asarray(m.N, np.float32)
    Nn = Nn / np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
    Ni = np.zeros((n, 4), np.int8)
    Ni[:, :3] = np.clip(np.round(Nn * 127), -127, 127)
    Ci = np.full((n, 4), 255, np.uint8)
    Ci[:, :3] = np.round(_lin(np.asarray(m.C, np.float32)[:, :3]) * 255)
    W = np.asarray(m.W, np.float32)
    W = W / np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
    top = np.argsort(-W, axis=1)[:, :4]                # the 4 bones that move it most (the rest is < 1 %)
    if top.shape[1] < 4:
        top = np.pad(top, ((0, 0), (0, 4 - top.shape[1])))
    tw = np.take_along_axis(W, top, axis=1)
    tw = tw / np.maximum(tw.sum(axis=1, keepdims=True), 1e-9)
    w8 = np.round(tw * 255).astype(np.int32)
    w8[:, 0] += 255 - w8.sum(axis=1)                   # exactly 255: the vertex never drifts
    lo, size, Vq = _q16(V)
    return (b"T3P3" + struct.pack("<II", n, len(T)) + lo.astype("<f4").tobytes() + size.astype("<f4").tobytes()
            + Vq.tobytes() + Ni.tobytes() + Ci.tobytes() + top.astype(np.uint8).tobytes()
            + w8.astype(np.uint8).tobytes() + T.astype("<u4").tobytes())


def ground_png(key, size=4096):
    """the ground of a scene seen from straight above: the scene's own ground drawing (fields, paths, roads,
    water, patches) with a top-down camera - world (X, Z) -> picture pixels, north (far) up"""
    got = GROUNDS.get(key)
    if got is None:
        return None
    import cairo
    from .scene3d import Cam3
    scene, cx, cz, span, t = got
    upp = span / size                                  # world units per pixel
    X0, Z1 = cx - span / 2, cz + span / 2
    top = Cam3(x=0.0, h=0.0, z=cz - span / 2 - 100.0, horizon=0.0)
    top.mirror = True                                  # (a world ground draws its roads and water for any view)
    saved = {k: scene.__dict__.get(k) for k in ("_cs", "_scr", "project", "W", "H", "fog_now")}
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, size, size)
    ctx = cairo.Context(surf)
    try:
        scene._cs = lambda cam, X, Z: (X, Z - cam.z)
        scene._scr = lambda cam, u, d, Y=0.0: ((u - X0) / upp, (Z1 - (d + cam.z)) / upp)
        scene.project = lambda cam, X, Y, Z: ((X - X0) / upp, (Z1 - Z) / upp, 1.0 / upp, Z - cam.z)
        scene.W = scene.H = size
        g0 = tuple(scene.ground)
        scene.fog_now = lambda: g0                     # (no haze from above: the browser adds its own)
        scene._ground(ctx, top, t)
    finally:
        for k, v in saved.items():
            if v is None:
                scene.__dict__.pop(k, None)
            else:
                scene.__dict__[k] = v
    import io
    from PIL import Image
    surf.flush()
    im = Image.frombuffer("RGBX", (size, size), bytes(surf.get_data()), "raw", "BGRX", 0, 1).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()
