"""Photo -> 2.5D: turn an uploaded background picture into depth layers the 3D camera can move through.

1. depth    Depth Anything V2 Small (Apache-2.0, runs on the CPU in ~2 s) estimates how far every pixel is.
            Without PyTorch/transformers a simple "basic" depth is used (the ground recedes, the rest is far).
2. geometry the picture's floor line (where characters stand at the front) + the way the ground's depth
            changes row by row give the picture's horizon, so the photo matches the engine's camera:
            a character at story z walks exactly on the photo's ground and gets the right size.
3. layers   ground strips (the floor at its real distance, with the parts behind objects painted in),
            3-4 object cards (trees, rocks, plants - near ones can hide characters), and a far backdrop
            card (sky + distance, with everything nearer painted out so moving never shows holes).
Everything is saved next to the picture in assets/images/<name>_2p5d/ (meta.json + PNG layers +
depth.png / layers.png / preview.mp4 for the Studio).
"""
import json
import math
import os
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

MODEL = "depth-anything/Depth-Anything-V2-Small-hf"
VERSION = 4
F = 1100.0          # engine focal length (world units = px at 1080p at the stage front)
H0 = 345.0          # default camera height
HY0 = 540.0         # default horizon row (1080p)
FEET0 = 885.0       # row where a character at story z = 0 stands (1080p)
FAR_Z = 6500.0      # further than this = part of the far backdrop card
N_STRIPS = 18
N_BINS = 4
MAX_W = 1600
OVERSCAN = 1.1      # the picture is shown 10% bigger than the screen, so camera moves find picture, not edges

_PIPE = None


def backend():
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return "depth-anything-v2-small"
    except Exception:
        return "basic"


def folder(name):
    from . import images
    meta = images.info(name)
    if not meta:
        return None
    return os.path.splitext(meta["file"])[0] + "_2p5d"


def status(name):
    """None if the picture has no 2.5D layers yet, else its meta dict."""
    d = folder(name)
    if not d:
        return None
    try:
        with open(os.path.join(d, "meta.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        return m if m.get("version") == VERSION else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------- depth
def _model_depth(im):
    global _PIPE
    if _PIPE is None:
        from transformers import pipeline
        _PIPE = pipeline("depth-estimation", model=MODEL, device="cpu")
    out = _PIPE(im)
    d = out["predicted_depth"]
    d = np.asarray(d.squeeze().detach().cpu().numpy(), dtype=np.float32)
    if d.shape != (im.height, im.width):
        d = np.asarray(Image.fromarray(d).resize(im.size, Image.BILINEAR), dtype=np.float32)
    return d


def _basic_depth(ih, iw, g):
    yh = max(0.05, g - 0.32) * ih
    y = np.arange(ih, dtype=np.float32)[:, None]
    d = np.clip((y - yh) / (ih - yh), 0, None) + 0.002
    return np.repeat(d, iw, axis=1).astype(np.float32)


def _push_back_holes(name, d):
    """Where things were taken out of the picture (engine/takeout.py) the filled patch must stay BEHIND the
    taken-out object, so it gets the depth of the farther part of its surroundings."""
    try:
        from . import takeout
        from scipy import ndimage
        hp = takeout.holes_path(name)
        if not os.path.exists(hp):
            return d
        hole = np.asarray(Image.open(hp).convert("L").resize((d.shape[1], d.shape[0]), Image.NEAREST)) > 127
        lab, n = ndimage.label(hole)
        d = d.copy()
        for i in range(1, n + 1):
            m = lab == i
            ring = ndimage.binary_dilation(m, iterations=12) & ~m
            if ring.any():
                d[m] = min(float(np.percentile(d[ring], 10)), float(d[m].min()))
        return d
    except Exception as ex:
        print("take-out holes skipped:", ex)
        return d


def estimate(im, ground=0.82, given=None):
    """(relative inverse depth 0..1 - bigger = nearer, backend name). given: a depth picture that came with it
    (a plate rendered from our own 3D world knows its depth exactly - tools/make_plates.py)."""
    if given and os.path.exists(given):
        g16 = Image.open(given).resize((im.width, im.height), Image.NEAREST)
        d = np.asarray(g16, dtype=np.float32) / 65535.0
        return np.clip(d, 0, 1).astype(np.float32), "given"
    be = backend()
    if be != "basic":
        try:
            d = _model_depth(im)
        except Exception as ex:                       # model download / runtime problem
            print("depth model failed, using basic depth:", ex)
            be = "basic"
    if be == "basic":
        d = _basic_depth(im.height, im.width, ground)
    lo, hi = np.percentile(d, 0.5), np.percentile(d, 99.5)
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1).astype(np.float32), be


# ---------------------------------------------------------------------------- helpers
def _down(a):
    h, w = a.shape[:2]
    if h % 2:
        a = np.concatenate([a, a[-1:]], 0)
    if w % 2:
        a = np.concatenate([a, a[:, -1:]], 1)
    return (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2])


def _up(a, shape):
    """Smooth (bilinear) 2x upsampling - nearest neighbour would leave blocky patches in the fill."""
    from scipy.ndimage import zoom
    f = (shape[0] / a.shape[0], shape[1] / a.shape[1]) + ((1.0,) if a.ndim == 3 else ())
    b = zoom(a, f, order=1, mode="nearest", grid_mode=True)
    if b.shape[0] < shape[0] or b.shape[1] < shape[1]:
        pads = [(0, max(0, shape[0] - b.shape[0])), (0, max(0, shape[1] - b.shape[1]))] + ([(0, 0)] if a.ndim == 3 else [])
        b = np.pad(b, pads, mode="edge")
    return b[:shape[0], :shape[1]]


def fill(rgb, keep):
    """Paint the pixels where keep is False from the kept ones around them (push-pull fill)."""
    w = keep.astype(np.float32)
    c = rgb * w[..., None]
    pyr = [(c, w)]
    while min(pyr[-1][1].shape) > 2:
        c, w = _down(pyr[-1][0]), _down(pyr[-1][1])
        pyr.append((c, w))
    c, w = pyr[-1]
    val = c / np.maximum(w, 1e-6)[..., None]
    for c, w in reversed(pyr[:-1]):
        upv = _up(val, w.shape)
        a = np.clip(w, 0, 1)[..., None]
        val = np.where(w[..., None] > 1e-4, (c / np.maximum(w, 1e-6)[..., None]) * a + upv * (1 - a), upv)
    return np.where(keep[..., None], rgb, val)


def _colormap(d):
    stops = np.array([[0.05, 0.05, 0.25], [0.2, 0.2, 0.7], [0.1, 0.6, 0.7], [0.5, 0.85, 0.3], [1.0, 0.85, 0.2],
                      [1.0, 0.95, 0.85]])
    x = np.clip(d, 0, 1) * (len(stops) - 1)
    i = np.clip(x.astype(int), 0, len(stops) - 2)
    f = (x - i)[..., None]
    return ((stops[i] * (1 - f) + stops[i + 1] * f) * 255).astype(np.uint8)


# ---------------------------------------------------------------------------- the pipeline
def process(name, ground=None, horizon=None, log=print, preview=True):
    """Make the 2.5D layers for picture `name`. Returns the meta dict."""
    from . import images
    from scipy import ndimage
    meta_img = images.info(name)
    if not meta_img:
        raise ValueError(f"unknown picture '{name}'")
    src = Image.open(meta_img["file"])
    try:
        src.seek(0)
    except Exception:
        pass
    im = src.convert("RGB")
    max_w = int(meta_img.get("max_w") or MAX_W)            # (a plate keeps more pixels: the camera zooms into it)
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    iw, ih = im.size
    g = float(ground or meta_img.get("ground") or 0.82)
    g = min(max(g, 0.45), 0.97)
    log(f"  depth: {name} ({iw}x{ih}) with {backend()}")
    dfile = meta_img.get("depth_file")
    d, be = estimate(im, g, os.path.join(os.path.dirname(meta_img["file"]), dfile) if dfile else None)
    d = _push_back_holes(name, d)
    rgb = np.asarray(im, dtype=np.float32) / 255.0
    gy = g * ih

    # -- the picture's horizon from how the ground's depth changes row by row (ground: m = a (y - yh))
    cols = slice(int(iw * 0.3), int(iw * 0.7))
    r0, r1 = int(max(0, gy - 0.07 * ih)), int(min(ih - 1, gy + 0.10 * ih))
    ys = np.arange(r0, r1)
    ms = np.median(d[r0:r1, cols], axis=1)
    a, yh = None, None
    if horizon is None and meta_img.get("horizon"):
        horizon = meta_img["horizon"]                  # marked by Gemini / you
    if horizon is not None:
        yh = float(horizon) * ih
    elif len(ys) > 5:
        A, B = np.polyfit(ys.astype(np.float64), ms.astype(np.float64), 1)
        if A > 1e-6:
            cand = -B / A
            if 0.02 * ih < cand < gy - 0.08 * ih:
                yh = cand
    if yh is None:
        yh = max(0.05 * ih, gy - 0.34 * ih)
    yh = min(max(yh, gy - 0.45 * ih, 0.02 * ih), gy - 0.06 * ih)   # sane: not too far above / near the floor
    m_g = float(np.median(d[int(gy) - 2:int(gy) + 3, cols])) if 2 < gy < ih - 3 else 0.5
    a = max(m_g, 0.02) / max(gy - yh, 1.0)
    over = float(meta_img.get("overscan") or OVERSCAN)    # a plate is made wider than the screen (room to frame)
    s = max(1920.0 / iw, 1080.0 / ih) * over          # picture px -> 1080p screen px (fills it + a margin)
    ox, oy = 960.0 - iw * s / 2.0, 540.0 - ih * s / 2.0
    hy_s = oy + yh * s                                 # the picture's horizon on screen
    cam_h = max(90.0, (gy - yh) * s)                   # camera height so z = 0 stands on the floor line

    # -- distance of every pixel (engine world units) and of the ground plane under each row
    yy = np.arange(ih, dtype=np.float32)[:, None]
    Zp = F * cam_h * a / (s * np.maximum(d, 1e-4))
    Zp = np.clip(Zp, 250.0, 60000.0)
    with np.errstate(divide="ignore"):
        Zg = np.where(yy > yh + 0.5, F * cam_h / (np.maximum(yy - yh, 0.5) * s), 1e9)
    ground = (yy > yh + 1) & (np.abs(np.log(Zp / Zg)) < 0.32)
    ground = ndimage.binary_opening(ground, iterations=2)
    far = (Zp > FAR_Z) & ~ground
    obj = ~ground & ~far
    obj = ndimage.binary_opening(obj, iterations=1)
    lab, n = ndimage.label(obj)                       # tiny specks go back to ground / far
    if n:
        sizes = ndimage.sum(obj, lab, range(1, n + 1))
        small = np.isin(lab, np.nonzero(sizes < iw * ih * 0.0006)[0] + 1)
        obj &= ~small
    far = ~ground & ~obj

    out_dir = folder(name)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    cards = []

    def save_card(fname, arr_rgba, x0, y0, Z, kind, pad=False):
        Image.fromarray((np.clip(arr_rgba, 0, 1) * 255).astype(np.uint8), "RGBA").save(os.path.join(out_dir, fname))
        h, w = arr_rgba.shape[:2]
        cards.append(dict(file=fname, u=ox + x0 * s, v=oy + y0 * s, w=w * s, h=h * s, Z=float(Z), kind=kind,
                          pad=bool(pad)))

    # far backdrop: sky + distance, everything nearer painted out
    base = fill(rgb, far | (yy < yh - 2) & (Zp > FAR_Z * 0.6))
    zb = float(np.clip(np.median(Zp[far]) if far.any() else 20000.0, 8000.0, 30000.0))
    # smooth mode (engine/photoworld.py): the distance of EVERY pixel, for a DepthFlow-style per-pixel parallax
    zmap = np.where(ground, Zg, np.where(obj, ndimage.median_filter(Zp, 3), zb)).astype(np.float32)
    np.savez_compressed(os.path.join(out_dir, "zmap.npz"), z=np.minimum(zmap, 60000.0).astype(np.float16))
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(out_dir, "photo.jpg"), quality=93)
    save_card("far.png", np.dstack([base, np.ones((ih, iw), np.float32)]), 0, 0, zb, "far", pad=True)
    # ground strips at their real distance, objects standing on them painted out
    groundimg = fill(rgb, ground | (yy > gy + 0.1 * ih) & ~obj)
    top = int(math.ceil(yh + 1))
    edges = np.linspace(top, ih, N_STRIPS + 1).astype(int)
    for k in range(N_STRIPS):
        y0, y1 = edges[k], min(ih, edges[k + 1] + 2)
        if y1 - y0 < 1:
            continue
        ym = (y0 + y1) / 2.0
        Zs = F * cam_h / (max(ym - yh, 0.5) * s)
        strip = np.dstack([groundimg[y0:y1], np.ones((y1 - y0, iw), np.float32)])
        save_card(f"ground_{k:02d}.png", strip, 0, y0, Zs, "ground", pad=True)
    # object cards (trees, rocks, near plants) in depth bins
    if obj.any():
        lz = np.log(Zp[obj])
        qs = np.quantile(lz, np.linspace(0, 1, N_BINS + 1))
        logz = np.log(Zp)
        for k in range(N_BINS):
            lo, hi = qs[k], qs[k + 1] + (1e-6 if k == N_BINS - 1 else 0)
            m = obj & (logz >= lo) & (logz < hi)
            if m.sum() < iw * ih * 0.002:
                continue
            soft = ndimage.gaussian_filter(m.astype(np.float32), 1.1)
            soft = np.clip(soft * 1.6, 0, 1) * ndimage.binary_dilation(m, iterations=2)
            ys_, xs_ = np.nonzero(soft > 0.01)
            y0, y1, x0, x1 = ys_.min(), ys_.max() + 1, xs_.min(), xs_.max() + 1
            col = fill(rgb[y0:y1, x0:x1], m[y0:y1, x0:x1])          # edge colours from the object itself
            Zc = float(np.exp(np.median(lz[(lz >= lo) & (lz < hi)])))
            save_card(f"obj_{k}.png", np.dstack([col, soft[y0:y1, x0:x1]]), x0, y0, Zc, "object")

    # water marked on the picture (Gemini / you): a mask for moving ripples + where the water is for the story
    water_meta = None
    wbox = meta_img.get("water") if isinstance(meta_img.get("water"), dict) else None
    if wbox:
        x0, x1 = int(wbox["x0"] * iw), int(max(wbox["x1"] * iw, wbox["x0"] * iw + 4))
        y0, y1 = int(max(wbox["y0"] * ih, yh + 2)), int(min(wbox["y1"] * ih, ih))
        if y1 > y0 + 3 and x1 > x0 + 3:
            box = np.zeros((ih, iw), bool)
            box[y0:y1, x0:x1] = True
            r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            blue = (b_ > r_ + 0.04) & (b_ >= g_ - 0.12)
            foam = (rgb.mean(axis=2) > 0.78) & (rgb.max(axis=2) - rgb.min(axis=2) < 0.18)
            wm = box & (blue | foam)
            wm = ndimage.binary_closing(wm, iterations=3)
            wm = ndimage.binary_fill_holes(ndimage.binary_opening(wm, iterations=2))
            if wm.sum() < 0.15 * box.sum():
                wm = box.copy()
            ys_, xs_ = np.nonzero(wm)
            ry0, ry1, rx0, rx1 = ys_.min(), ys_.max() + 1, xs_.min(), xs_.max() + 1
            soft = ndimage.gaussian_filter(wm.astype(np.float32), 1.5)[ry0:ry1, rx0:rx1]
            Image.fromarray((np.clip(soft, 0, 1) * 255).astype(np.uint8), "L").save(os.path.join(out_dir, "water.png"))
            rows = np.nonzero(wm.any(axis=1))[0]
            near_rows = rows[rows >= np.quantile(rows, 0.6)]
            cols = np.nonzero(wm[near_rows].any(axis=0))[0]

            def z_of_row(y):
                Z = F * cam_h / (max(y - yh, 0.5) * s)
                from .world3d import FOCAL as FO
                return float(np.clip((1 - FO / Z) * 1000 / 0.58 if Z <= FO / 0.42 else 1000 + (Z - FO / 0.42) / 4,
                                     0, 3000))
            zm = F * cam_h / (max(float(np.median(rows)) - yh, 0.5) * s)
            cards.append(dict(file="water.png", u=ox + rx0 * s, v=oy + ry0 * s, w=(rx1 - rx0) * s,
                              h=(ry1 - ry0) * s, Z=float(zm), kind="water", pad=False))
            water_meta = dict(kind=wbox.get("kind", "river"), u0=float(ox + cols.min() * s),
                              u1=float(ox + (cols.max() + 1) * s), z0=z_of_row(float(rows.max())),
                              z1=z_of_row(float(rows.min())))

    # views for the Studio: depth map + layers map
    Image.fromarray(_colormap(d)).save(os.path.join(out_dir, "depth.png"))
    np.savez_compressed(os.path.join(out_dir, "depth_raw.npz"), d=d[::2, ::2].astype(np.float16))  # take-out hints
    vis = (rgb * 0.45 * 255).astype(np.float32)
    vis[ground] += np.array([150, 105, 50]) * 0.55
    vis[far] += np.array([70, 110, 190]) * 0.55
    tints = [(230, 70, 70), (240, 170, 40), (80, 200, 90), (200, 90, 220)]
    if obj.any():
        logz = np.log(Zp)
        for k in range(N_BINS):
            m = obj & (logz >= qs[k]) & (logz <= qs[k + 1])
            vis[m] += np.array(tints[k]) * 0.55
    if water_meta is not None:
        vis[wm] = rgb[wm] * 0.45 * 255 + np.array([40, 200, 230]) * 0.55
    Image.fromarray(np.clip(vis, 0, 255).astype(np.uint8)).save(os.path.join(out_dir, "layers.png"))
    meta = dict(version=VERSION, name=name, backend=be, width=iw, height=ih, ground=g,
                horizon=float(yh / ih), scale=float(s), cam_h=float(cam_h), hor=float(hy_s / 1080.0), cards=cards,
                objects=int(sum(1 for c in cards if c["kind"] == "object")), water=water_meta,
                people_on_top=bool(meta_img.get("plate")),     # a plate (tools/make_plates.py): people stay in front
                overscan=over)
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    if preview:
        try:
            make_preview(name, log=log)
            meta["preview"] = True
        except Exception as ex:
            log(f"  preview failed: {ex}")
    return meta


def zones(meta, world_w):
    """Water of the picture in story units [(x0, x1, z_near, z_far)] (story x = screen offset from the centre)."""
    w = (meta or {}).get("water")
    if not w:
        return []
    c = world_w / 2.0
    return [(c + w["u0"] - 960.0, c + w["u1"] - 960.0, w["z0"], w["z1"])]


def ensure(name, log=print):
    return status(name) or process(name, log=log, preview=False)


# ---------------------------------------------------------------------------- preview clip
def make_preview(name, seconds=4.0, fps=24, W=640, H=360, log=print):
    """A short clip: the camera tracks and pushes in while a character walks into the picture."""
    import cairo
    from .photoworld import PhotoWorld3D
    from .scene3d import Cam3, Obj
    from .world3d import Z_of_z, p3, X_of
    from .character import CharacterDef, draw_character
    from .poses import ACTIONS
    from .render import find_ffmpeg
    ff = find_ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg not found")
    world = PhotoWorld3D(name, 2400.0, W, H)
    kid = CharacterDef("preview_kid", {"age": "child", "outfit": "tshirt", "outfit_color": "#1d4e89",
                                        "hair": "spiky", "skin": "wheat"}, 0)
    out = os.path.join(folder(name), "preview.mp4")
    tmp = tempfile.mkdtemp()
    n = int(seconds * fps)
    try:
        cmd = [ff, "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r",
               str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
               "-movflags", "+faststart", out]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for f in range(n):
            t = f / fps
            u = t / seconds
            e = 0.5 - 0.5 * math.cos(math.pi * u)
            z = 60 + 520 * e                          # walks away into the picture
            x = 1000 + 300 * e
            p = p3(z)
            X, Z = X_of(x, p, 1200.0), Z_of_z(z)
            pose, ex = ACTIONS["walk"].fn(t, seconds, {"speed": 150, "dist": t * 150, "params": {}})

            def draw(c, tt, x=x, pose=pose):
                c.translate(-x, 0)
                draw_character(c, kid, pose, x, 1, "happy", 0.0, tt, {}, 1.0, False, False)
            mh = world.meta
            cam = Cam3(x=1200 - 70 + 140 * e, h=mh["cam_h"] * (1 + 0.25 * e), z=260 * e, horizon=mh["hor"],
                       focus=Z - 260 * e, aperture=0.5)
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
            ctx = cairo.Context(surf)
            world.render(ctx, cam, t, [Obj(X, Z, draw, w=320, tag="actor")])
            surf.flush()
            pr.stdin.write(bytes(surf.get_data()))
        pr.stdin.close()
        pr.wait()
        subprocess.run([ff, "-loglevel", "error", "-y", "-i", out, "-c:v", "libvpx", "-b:v", "1200k",
                        out[:-4] + ".webm"], check=False)       # for browsers without H.264
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out
