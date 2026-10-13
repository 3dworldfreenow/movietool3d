"""Real images (photos, drawings, PNG cut-outs) inside stories.

Put files in assets/images/ (or upload them in the Studio > Images tab):
    assets/images/temple.png          the picture (png / jpg / jpeg / webp)
    assets/images/temple.json         optional: {"description": "...", "height": 420, "ground": 0.86}

Use them in a story in four ways:
  1. Object in the scene   "elements": [{"type": "image", "name": "temple", "x": 900, "height": 420}]
                           (or simply {"type": "temple", "x": 900})
  2. Prop                  "props": [{"id": "cup", "type": "trophy", "x": 700, "height": 60}]
                           characters can pick / drop / give it, or it can be thrown ("prop": ..., "to": ...)
  3. Whole background      "background": {"image": "my_school", "ground": 0.86}
                           ground = where the floor line is, as a fraction of the picture height from the top
  4. Picture moment        {"picture": "taj_mahal", "caption": "The real Taj Mahal", "duration": 4}
                           full-screen photo with a slow zoom (style "frame" shows it as a framed photo instead)
PNG images with a transparent background look best as objects and props.

Animated pictures: GIF, animated WebP, APNG, or a short video clip (MP4 / WebM / MOV, first 8 s) are
stored as an animated WebP and play by themselves in all four uses. Options on any of them:
    "speed": 0.5 (slower) | 2 (faster)      "loop": "loop" (default) | "once" | "pingpong"
    "phase": 0.3   (start that many seconds into the animation - so two copies don't move in sync)
"""
import bisect
import json
import os

import cairo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "assets", "images")
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".apng")
VIDEO_EXTS = (".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv")
MAX_SIDE = 2048
MAX_SIDE_ANIM = 1024        # animated pictures keep every frame in memory
MAX_FRAMES = 160
MAX_CLIP = 8.0              # seconds taken from an uploaded video clip
CLIP_FPS = 15

_SURF = {}          # name -> (cairo surface, w, h)   (per process)
_LIST = {"stamp": None, "data": {}}


def _clean(name):
    import re
    n = "".join(c if c.isalnum() or c in "_-" else "_" for c in str(name).lower().strip())
    return re.sub(r"_+", "_", n).strip("_-")[:40]


_STAMP = {"t": 0.0, "v": ()}


def _stamp():
    """Which pictures exist and when they changed - checked at most every 2 s (a frame asks thousands of times)."""
    import time as _time
    now = _time.monotonic()
    if not os.path.isdir(DIR):
        return ()
    dm = os.path.getmtime(DIR)                          # a picture added / removed: the folder changes
    if now - _STAMP["t"] < 2.0 and _STAMP["v"] and _STAMP.get("dm") == dm:
        return _STAMP["v"]
    _STAMP["dm"] = dm
    v = tuple((f, os.path.getmtime(os.path.join(DIR, f))) for f in sorted(os.listdir(DIR)))
    _STAMP["t"], _STAMP["v"] = now, v
    return v


def refresh():
    """Forget the cached list (after saving / deleting pictures)."""
    _STAMP["t"] = 0.0
    _LIST["stamp"] = None


def list_images():
    """{name: {"file", "description", "height", "ground", "w", "h", "has_alpha"}}"""
    st = _stamp()
    if _LIST["stamp"] == st:
        return _LIST["data"]
    data = {}
    if os.path.isdir(DIR):
        for f in sorted(os.listdir(DIR)):
            base, ext = os.path.splitext(f)
            if ext.lower() not in EXTS:
                continue
            name = _clean(base)
            meta = {}
            mp = os.path.join(DIR, base + ".json")
            if os.path.exists(mp):
                try:
                    with open(mp, encoding="utf-8") as fh:
                        meta = json.load(fh)
                except (OSError, ValueError):
                    meta = {}
            info = {"file": os.path.join(DIR, f), "description": meta.get("description", ""),
                    "height": meta.get("height"), "ground": meta.get("ground"), "kind": meta.get("kind", "any"),
                    "abilities": list(meta.get("abilities") or [])}
            for k in ("water", "horizon", "depth_file", "plate", "max_w", "overscan", "kit", "kit_piece", "states", "state_of", "state", "sheet", "sheet_px", "cut_from", "at", "cut_objects", "made_by", "code", "part_of", "set_of", "live", "box", "thing", "draw_state", "scale", "is3d", "c3", "walk", "foot", "feet", "doors", "seat", "ride", "seats", "speed", "seat_height", "sound", "faces"):
                if meta.get(k) is not None:
                    info[k] = meta[k]
            try:
                from PIL import Image
                with Image.open(info["file"]) as im:
                    info["w"], info["h"] = im.size
                    info["has_alpha"] = im.mode in ("RGBA", "LA", "P") or "transparency" in im.info
                    n = int(getattr(im, "n_frames", 1) or 1)
            except Exception:
                continue
            info["frames"] = n
            info["animated"] = n > 1
            if "alpha" in meta:
                info["has_alpha"] = bool(meta["alpha"])
            if n > 1:
                durs = meta.get("durations")
                if not durs or len(durs) != n:
                    durs = [float(meta.get("frame_ms", 100))] * n
                info["durations"] = durs
                info["duration"] = round(sum(durs) / 1000.0, 2)
            data[name] = info
    _LIST.update(stamp=st, data=data)
    _SURF.clear()
    return data


def update_meta(name, **kw):
    """Change some fields of a picture's .json (None removes a field)."""
    refresh()
    meta = info(name)
    if not meta:
        return False
    p = os.path.splitext(meta["file"])[0] + ".json"
    try:
        with open(p, encoding="utf-8") as fh:
            m = json.load(fh)
    except (OSError, ValueError):
        m = {}
    for k, v in kw.items():
        if v is None:
            m.pop(k, None)
        else:
            m[k] = v
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=2, ensure_ascii=False)
    _LIST["stamp"] = None
    list_images()
    return True


def exists(name):
    return bool(name) and _clean(name) in list_images()


def info(name):
    return list_images().get(_clean(name))


def _to_surface(im):
    """PIL RGBA image -> (cairo surface, w, h, buffer)  (cairo wants premultiplied BGRA)."""
    import numpy as np
    w, h = im.size
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    a[..., :3] *= a[..., 3:4] / 255.0
    bgra = a[..., [2, 1, 0, 3]].astype(np.uint8)
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, w)
    buf = bytearray(stride * h)
    row = w * 4
    flat = bgra.tobytes()
    for y in range(h):
        buf[y * stride: y * stride + row] = flat[y * row:(y + 1) * row]
    surf = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, w, h, stride)
    return (surf, w, h, buf)


def _load(key, meta):
    from PIL import Image, ImageSequence
    im = Image.open(meta["file"])
    frames = []
    side = MAX_SIDE_ANIM if meta.get("animated") else MAX_SIDE
    for fr in ImageSequence.Iterator(im):
        f = fr.convert("RGBA")
        w, h = f.size
        k = min(1.0, side / max(w, h))
        if k < 1.0:
            f = f.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)
        frames.append(_to_surface(f))
        if len(frames) >= MAX_FRAMES or not meta.get("animated"):
            break
    durs = (meta.get("durations") or [100.0] * len(frames))[:len(frames)]
    ends, acc = [], 0.0
    for d in durs:
        acc += max(float(d), 20.0) / 1000.0
        ends.append(acc)
    return {"frames": frames, "ends": ends, "total": acc or 0.1}


def frame_index(anim, t=0.0, speed=1.0, loop="loop", phase=0.0):
    n = len(anim["frames"])
    if n <= 1:
        return 0
    T = anim["total"]
    tt = max(0.0, float(t) * float(speed) + float(phase))
    loop = str(loop).lower()
    if loop in ("once", "false", "no", "0"):
        tt = min(tt, T - 1e-4)
    elif loop in ("pingpong", "bounce"):
        m = tt % (2 * T)
        tt = m if m < T else 2 * T - m - 1e-4
    else:
        tt %= T
    return min(n - 1, bisect.bisect_right(anim["ends"], tt))


def surface(name, t=0.0, speed=1.0, loop="loop", phase=0.0):
    """Cairo surface for an image at scene time t (animated pictures pick their frame; loaded once per process).
    Returns (surface, w, h, buffer)."""
    key = _clean(name)
    anim = _SURF.get(key)
    if anim is None:
        meta = list_images().get(key)
        if not meta:
            return None
        anim = _SURF[key] = _load(key, meta)
    return anim["frames"][frame_index(anim, t, speed, loop, phase)]


def anim_opts(spec, default_phase=0.0):
    """speed / loop / phase from an element, prop or picture spec."""
    spec = spec or {}
    return dict(speed=float(spec.get("speed", spec.get("anim_speed", 1.0)) or 1.0),
                loop=spec.get("loop", "loop"), phase=float(spec.get("phase", default_phase) or 0.0))


def draw(ctx, name, x, y, height=None, flip=False, alpha=1.0, anchor="bottom", rotate=0.0, t=0.0, speed=1.0,
         loop="loop", phase=0.0, turn=0.0):
    """Draw in WORLD coordinates (y-up). anchor bottom: (x, y) = bottom-centre; center: (x, y) = centre.
    t = scene time (animated pictures)."""
    meta = info(name) or {}
    if meta.get("live") and meta.get("code"):          # a Python drawing: drawn from its code (sharp, fast)
        from . import codedraw
        got = codedraw.draw_live(ctx, meta, x, y, height, flip, alpha, anchor, rotate, t, speed, loop, phase,
                                 turn=turn)
        if got:
            return got
    got = surface(name, t, speed, loop, phase)
    if not got:
        return None
    surf, w, h = got[0], got[1], got[2]
    height = float(height or meta.get("height") or 300)
    sc = height / h
    if getattr(ctx, "live3d", False) and not rotate:     # 🎥 live 3D play: a picture card the browser stands there
        from .live3d import picture
        if picture(ctx, surf, w * sc, height, x, y, flip, alpha, anchor):
            return (w * sc, height)
    ctx.save()
    ctx.translate(x, y)
    if rotate:
        ctx.rotate(rotate)
    top = height if anchor == "bottom" else height / 2
    ctx.translate(0, top)
    ctx.scale(-sc if flip else sc, -sc)
    ctx.translate(-w / 2, 0)
    pat = cairo.SurfacePattern(surf)
    pat.set_filter(cairo.FILTER_GOOD)
    ctx.set_source(pat)
    ctx.rectangle(0, 0, w, h)
    ctx.clip()
    ctx.paint_with_alpha(alpha)
    ctx.restore()
    return (w * sc, height)


def draw_cover(ctx, name, W, H, zoom=1.0, pan=(0.5, 0.5), alpha=1.0, t=0.0, speed=1.0, loop="loop"):
    """Fill the whole screen (device coords) with the image, like CSS object-fit: cover."""
    got = surface(name, t, speed, loop)
    if not got:
        return False
    surf, w, h = got[0], got[1], got[2]
    sc = max(W / w, H / h) * zoom
    dw, dh = w * sc, h * sc
    ox = (W - dw) * pan[0]
    oy = (H - dh) * pan[1]
    ctx.save()
    ctx.identity_matrix()
    ctx.translate(ox, oy)
    ctx.scale(sc, sc)
    pat = cairo.SurfacePattern(surf)
    pat.set_filter(cairo.FILTER_GOOD)
    ctx.set_source(pat)
    ctx.rectangle(0, 0, w, h)
    ctx.clip()
    ctx.paint_with_alpha(alpha)
    ctx.restore()
    return True


def _video_frames(data_bytes, filename):
    """First MAX_CLIP seconds of a video clip -> ([PIL frames], ms per frame) via FFmpeg."""
    import shutil
    import subprocess
    import tempfile
    from PIL import Image
    try:
        from .render import find_ffmpeg
        ff = find_ffmpeg()
    except (Exception, SystemExit):
        raise ValueError("FFmpeg is needed to read video clips")
    tmp = tempfile.mkdtemp(prefix="clip_")
    try:
        src = os.path.join(tmp, "in" + (os.path.splitext(filename or "")[1] or ".mp4"))
        with open(src, "wb") as f:
            f.write(data_bytes)
        vf = (f"fps={CLIP_FPS},scale='if(gt(iw,ih),min({MAX_SIDE_ANIM},iw),-2)':"
              f"'if(gt(iw,ih),-2,min({MAX_SIDE_ANIM},ih))'")
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", src, "-t", str(MAX_CLIP), "-vf", vf,
                            "-frames:v", str(MAX_FRAMES), os.path.join(tmp, "f%04d.png")],
                           capture_output=True, text=True, timeout=180)
        files = sorted(p for p in os.listdir(tmp) if p.startswith("f") and p.endswith(".png"))
        if not files:
            raise ValueError("could not read frames from the video " + (r.stderr or "").strip()[:200])
        frames = []
        for p in files:
            with Image.open(os.path.join(tmp, p)) as im:
                frames.append(im.convert("RGB").copy())
        return frames, 1000.0 / CLIP_FPS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def save_upload(name, data_bytes, filename, description="", height=None, ground=None, kind="any", abilities=None,
                cutout="off"):
    refresh()
    """Store an uploaded image + its description. Still pictures become PNG (transparent) or JPG;
    GIF / animated WebP / APNG / video clips become an animated WebP. Returns the clean name."""
    from PIL import Image, ImageSequence
    import io
    name = _clean(name or os.path.splitext(os.path.basename(filename or "image"))[0])
    if not name:
        raise ValueError("name required")
    os.makedirs(DIR, exist_ok=True)
    ext = os.path.splitext(filename or "")[1].lower()
    durations = None
    if ext in VIDEO_EXTS:
        frames, ms = _video_frames(data_bytes, filename)
        durations = [ms] * len(frames)
    else:
        im = Image.open(io.BytesIO(data_bytes))
        im.load()
        if int(getattr(im, "n_frames", 1) or 1) > 1:
            frames, durations = [], []
            for fr in ImageSequence.Iterator(im):
                durations.append(float(fr.info.get("duration") or im.info.get("duration") or 100))
                frames.append(fr.convert("RGBA").copy())
                if len(frames) >= MAX_FRAMES:
                    break
        else:
            frames = [im]
    cut_method = "none"
    if cutout not in (None, "", "off", "none"):      # make the background transparent (engine/cutout.py)
        from . import cutout as _cut
        if len(frames) == 1:
            frames[0], cut_method = _cut.cutout(frames[0], cutout)
        elif not any(_cut.has_alpha(f) for f in frames[:3]) and _cut.plain_border(frames[0])[0] >= 0.7:
            frames = [_cut.cut_white(f) for f in frames]            # moving pictures: the quick white cut
            cut_method = "white"
    for e in EXTS:                                   # replace any older version
        p = os.path.join(DIR, name + e)
        if os.path.exists(p):
            os.remove(p)
    if len(frames) > 1:
        k = min(1.0, MAX_SIDE_ANIM / max(frames[0].size))
        if k < 1.0:
            size = (max(1, int(frames[0].width * k)), max(1, int(frames[0].height * k)))
            frames = [f.resize(size, Image.LANCZOS) for f in frames]
        alpha = any(f.mode == "RGBA" and f.getextrema()[3][0] < 250 for f in frames[:5])
        frames = [f.convert("RGBA" if alpha else "RGB") for f in frames]
        frames[0].save(os.path.join(DIR, name + ".webp"), save_all=True, append_images=frames[1:],
                       duration=[int(d) for d in durations], loop=0, quality=88, method=4)
    else:
        im = frames[0]
        k = min(1.0, MAX_SIDE / max(im.size))
        if k < 1.0:
            im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
        if im.mode in ("RGBA", "LA", "P"):
            im.convert("RGBA").save(os.path.join(DIR, name + ".png"), optimize=True)
        else:
            im.convert("RGB").save(os.path.join(DIR, name + ".jpg"), quality=90)
    meta = {"description": description or "", "kind": kind or "any"}
    if cut_method in ("white", "ai"):
        meta["cutout"] = cut_method
    ab = [a.strip() for a in (abilities.split(",") if isinstance(abilities, str) else (abilities or [])) if a.strip()]
    if ab:
        meta["abilities"] = ab
    if durations and len(frames) > 1:
        meta["durations"] = [round(float(d), 1) for d in durations]
        meta["alpha"] = bool(alpha)
    if height:
        meta["height"] = float(height)
    if ground:
        meta["ground"] = float(ground)
    with open(os.path.join(DIR, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    list_images()
    return name


def delete(name):
    refresh()
    import shutil
    name = _clean(name)
    for ext in EXTS + (".json",):
        p = os.path.join(DIR, name + ext)
        if os.path.exists(p):
            os.remove(p)
    shutil.rmtree(os.path.join(DIR, name + "_2p5d"), ignore_errors=True)     # its 2.5D depth layers
    list_images()
