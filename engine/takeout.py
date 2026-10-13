"""Take a thing (a tree, a rock, a hut) OUT of a background picture so characters can use it - free, no model.

  1. you drag a box around the thing (and may click on it)            - or Gemini points things out (free tier)
  2. cut():   OpenCV GrabCut finds its outline; the 2.5D depth map tells what is in front and what is behind,
              so a tree trunk is not mixed up with the jungle behind it
  3. commit(): the thing becomes a library object (with abilities: climb, hide, sit ...) and the hole it leaves
              in the background is filled with OpenCV inpaint. The engine puts the object back at exactly the same
              spot whenever a story uses this background, now as a real object at its real depth.
The original picture is kept (assets/images/_takeout/) - "Undo all" brings it back.
"""
import io
import json
import os
import shutil

import numpy as np
from PIL import Image

from . import images, photodepth

WORK = 1600                                  # same size the 2.5D layers are made at
BACKUP = os.path.join(images.DIR, "_takeout")


def _load(name):
    meta = images.info(name)
    if not meta:
        raise ValueError(f"unknown picture '{name}'")
    im = Image.open(meta["file"])
    try:
        im.seek(0)
    except Exception:
        pass
    im = im.convert("RGB")
    if im.width > WORK:
        im = im.resize((WORK, round(im.height * WORK / im.width)), Image.LANCZOS)
    return im, meta


def _depth(name, im):
    """Relative inverse depth (bigger = nearer) at the picture's size, from the 2.5D step if it was saved."""
    d = photodepth.folder(name)
    p = os.path.join(d, "depth_raw.npz") if d else None
    if p and os.path.exists(p):
        a = np.load(p)["d"].astype(np.float32)
        return np.asarray(Image.fromarray(a).resize(im.size, Image.BILINEAR), dtype=np.float32)
    if photodepth.backend() != "basic":
        return photodepth.estimate(im)[0]
    return None


def _key(name):
    meta = images.info(name) or {}
    try:
        return f"{name}:{os.path.getmtime(meta['file'])}"
    except OSError:
        return name


def _guess(rgb, mask, box):
    """A name from shape and colour (no model can name things at this size): tree / rock / bush / log / thing."""
    import colorsys
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    px = rgb[mask]
    if len(px) > 4000:
        px = px[:: len(px) // 4000]
    hsv = np.array([colorsys.rgb_to_hsv(*(p / 255.0)) for p in px])
    sat, hue, val = np.median(hsv[:, 1]), hsv[:, 0], np.median(hsv[:, 2])
    green = ((hue > 0.17) & (hue < 0.45) & (hsv[:, 1] > 0.25)).mean()
    brown = ((hue > 0.03) & (hue < 0.12) & (hsv[:, 1] > 0.3)).mean()
    grey = (hsv[:, 1] < 0.18).mean()
    if grey > 0.5 and h < 1.4 * w:
        return "rock", ["sit", "stand", "hide"]
    if (h > 1.3 * w and (brown > 0.2 or green > 0.3)) or (h > 0.9 * w and brown > 0.06 and green > 0.3
                                                          and h > 0.25 * mask.shape[0]):
        return "tree", ["climb", "hide"]
    if brown > 0.45 and w > 1.8 * h:
        return "log", ["sit", "stand"]
    if green > 0.55:
        return "bush", ["hide"]
    if brown > 0.4:
        return "wooden thing", ["hide"]
    return "thing", ["hide"]


def find_local(name, log=print):
    """Things in the picture, found on this computer (small SAM + the depth map). No internet after the first
    model download. Returns [{name, what, box (0..1), abilities, score}]."""
    from . import sam
    im, _ = _load(name)
    W, H = im.size
    rgb = np.asarray(im)
    d = _depth(name, im)
    if not sam.available():
        raise RuntimeError("the small model needs torch + transformers (see requirements-depth.txt)")
    shapes = sam.find(_key(name), im)
    out, used = [], {}
    from scipy import ndimage
    for score, m, box in shapes:
        x0, y0, x1, y1 = box
        edges = (x0 <= 2) + (y0 <= 2) + (x1 >= W - 2) + (y1 >= H - 2)
        if edges >= 2 or (x1 - x0) > 0.6 * W:
            continue                                     # a corner of foliage / a whole band, not one thing
        if y1 < 0.25 * H and (rgb[m][:, 2].astype(int) - rgb[m][:, 0]).mean() > 30:
            continue                                     # a piece of sky / cloud
        near = 0.0
        if d is not None:
            ring = ndimage.binary_dilation(m, iterations=12) & ~m
            if ring.any():
                near = float(np.median(d[m]) - np.median(d[ring]))
            if near < -0.08:                             # clearly behind its surroundings: a gap, not a thing
                continue
        what, ab = _guess(rgb, m, box)
        used[what] = used.get(what, 0) + 1
        nm = what.replace(" ", "_") + (f"_{used[what]}" if used[what] > 1 else "")
        out.append({"name": nm, "what": what, "abilities": ab, "score": round(score + 2 * max(near, 0), 3),
                    "box": [round(x0 / W, 4), round(y0 / H, 4), round(x1 / W, 4), round(y1 / H, 4)]})
    out.sort(key=lambda o: -o["score"])
    return out[:10]


def cut(name, box, click=None):
    """box = (x0, y0, x1, y1) as 0..1 of the picture; click = (x, y) 0..1 on the thing (optional).
    Returns a dict with the mask (bool array), crop box, base point and preview PNGs (bytes)."""
    import cv2
    im, _ = _load(name)
    W, H = im.size
    rgb = np.asarray(im)
    x0, y0, x1, y1 = [float(v) for v in box]
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    X0, Y0 = int(max(0, x0 * W)), int(max(0, y0 * H))
    X1, Y1 = int(min(W, x1 * W)), int(min(H, y1 * H))
    if X1 - X0 < 8 or Y1 - Y0 < 8:
        raise ValueError("draw a bigger box around the thing")
    cx, cy = (click if click else ((x0 + x1) / 2, y0 + (y1 - y0) * 0.45))
    cx, cy = int(np.clip(cx * W, X0, X1 - 1)), int(np.clip(cy * H, Y0, Y1 - 1))
    fg = None
    from . import sam
    if sam.available():
        try:
            fg, _ = sam.box_mask(_key(name), im, (X0, Y0, X1, Y1), (cx, cy) if click else None)
            if fg.sum() < 30:
                fg = None
        except Exception as ex:                          # no model yet / no internet: the OpenCV way
            print("small SAM not used:", ex)
            fg = None
    if fg is not None:
        return _finish(name, fg, cx, cy, W, H, "sam")
    mask = np.full((H, W), cv2.GC_BGD, np.uint8)
    mask[Y0:Y1, X0:X1] = cv2.GC_PR_BGD
    d = _depth(name, im)
    inner = np.zeros((H, W), bool)
    inner[Y0 + (Y1 - Y0) // 10:Y1 - (Y1 - Y0) // 20, X0 + (X1 - X0) // 8:X1 - (X1 - X0) // 8] = True
    if d is not None:
        r = max(3, min(X1 - X0, Y1 - Y0) // 12)
        seed = float(np.median(d[max(0, cy - r):cy + r, max(0, cx - r):cx + r]))
        near = d >= seed - 0.06                        # as near as the thing (or nearer): probably the thing
        mask[(mask == cv2.GC_PR_BGD) & near & inner] = cv2.GC_PR_FGD
        mask[(mask == cv2.GC_PR_FGD) & (d < seed - 0.18)] = cv2.GC_PR_BGD      # clearly behind it
    else:
        mask[inner] = cv2.GC_PR_FGD
    rr = max(2, min(X1 - X0, Y1 - Y0) // 25)
    cv2.circle(mask, (cx, cy), rr, cv2.GC_FGD, -1)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    fg = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
    return _finish(name, fg, cx, cy, W, H, "opencv")


def _finish(name, fg, cx, cy, W, H, how):
    import cv2
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8), 8)
    if n <= 1:
        raise ValueError("nothing found in the box - click right on the thing and try again")
    keep = lab[cy, cx] if lab[cy, cx] > 0 else 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    big = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 0.15 * stats[keep, cv2.CC_STAT_AREA]]
    fg = np.isin(lab, [keep] + big)
    ys, xs = np.nonzero(fg)
    base_y = int(ys.max())
    low = ys >= base_y - max(2, (ys.max() - ys.min()) // 20)
    base_x = float(np.median(xs[low]))
    return {"name": name, "mask": fg, "box": (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
            "base": (base_x, float(base_y)), "size": (W, H), "how": how}


def cutout_png(name, c, feather=1.2):
    """The thing alone, transparent around it (soft 1-2 px edge)."""
    from scipy import ndimage
    im, _ = _load(name)
    x0, y0, x1, y1 = c["box"]
    a = ndimage.gaussian_filter(c["mask"].astype(np.float32), feather)
    a = np.maximum(a, c["mask"] * 0.0)
    rgba = np.dstack([np.asarray(im), (np.clip(a, 0, 1) * 255).astype(np.uint8)])[y0:y1, x0:x1]
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def filled(name, c, grow=7):
    """The background with the hole filled (OpenCV inpaint; big holes at half size, then blended in)."""
    import cv2
    im, meta = _load(name)
    src = Image.open(meta["file"]).convert("RGB")                # fill at the picture's full size
    sw, sh = src.size
    m = Image.fromarray((c["mask"] * 255).astype(np.uint8)).resize((sw, sh), Image.NEAREST)
    m = cv2.dilate(np.asarray(m), np.ones((3, 3), np.uint8), iterations=max(1, int(grow * sw / WORK)))
    bgr = cv2.cvtColor(np.asarray(src), cv2.COLOR_RGB2BGR)
    area = (m > 0).mean()
    if area > 0.02:                                    # large hole: fill at half size (smoother, faster)
        small = cv2.resize(bgr, (sw // 2, sh // 2), interpolation=cv2.INTER_AREA)
        ms = cv2.resize(m, (sw // 2, sh // 2), interpolation=cv2.INTER_NEAREST)
        f = cv2.inpaint(small, ms, 9, cv2.INPAINT_TELEA)
        f = cv2.resize(f, (sw, sh), interpolation=cv2.INTER_CUBIC)
        k = cv2.GaussianBlur((m > 0).astype(np.float32), (0, 0), 3)[..., None]
        out = (bgr * (1 - k) + f * k).astype(np.uint8)
    else:
        out = cv2.inpaint(bgr, m, 7, cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))


def preview(name, c):
    """PNG: the picture with the thing outlined (left) and the filled background (right)."""
    import cv2
    im, _ = _load(name)
    rgb = np.asarray(im).copy()
    tint = rgb.copy()
    tint[c["mask"]] = (tint[c["mask"]] * 0.45 + np.array([255, 60, 60]) * 0.55).astype(np.uint8)
    edge = cv2.morphologyEx(c["mask"].astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    tint[edge] = (255, 255, 0)
    fill = np.asarray(filled(name, c).resize(im.size, Image.LANCZOS))
    both = np.concatenate([tint, np.full((im.height, 12, 3), 255, np.uint8), fill], axis=1)
    out = Image.fromarray(both)
    if out.width > 1400:
        out = out.resize((1400, round(out.height * 1400 / out.width)), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def place(name, c):
    """Where the thing stands in story units: {"dx": x offset from the scene's middle, "z": depth, "height"}."""
    m = photodepth.status(name)
    W, H = c["size"]
    bx, by = c["base"]
    top = c["box"][1]
    if not m:                                          # no 2.5D yet: flat picture, front of the stage
        s = max(1920.0 / W, 1080.0 / H)
        return {"dx": round((bx - W / 2) * s), "z": 0, "height": round((by - top) * s)}
    k = m["width"] / W                                 # our work size == the 2.5D size (both 1600 wide)
    s, ih = m["scale"], m["height"]
    yh = m["horizon"] * ih
    ox = 960.0 - m["width"] * s / 2.0
    u = ox + bx * k * s
    y = by * k
    y_d = _row_of_depth(name, c, yh / k)               # where the ground is as near as the thing (base hidden?)
    if y_d is not None:
        y = max(y, y_d * k)
    y = max(y, yh + 0.03 * ih)
    Z = photodepth.F * m["cam_h"] / (max(y - yh, 0.5) * s)
    from .world3d import FOCAL as FO
    z = (1 - FO / Z) * 1000 / 0.58 if Z <= FO / 0.42 else 1000 + (Z - FO / 0.42) / 4
    height = (y - top * k) * s * Z / photodepth.F
    return {"dx": round(u - 960.0), "z": round(float(np.clip(z, 0, 3000))), "height": round(height)}


def _row_of_depth(name, c, yh):
    """The picture row where the open ground is as near as the thing itself (for things whose foot is hidden
    behind bushes). None without a depth map."""
    im, _ = _load(name)
    d = _depth(name, im)
    if d is None:
        return None
    H, W = d.shape
    d_obj = float(np.median(d[c["mask"]]))
    rows = np.arange(int(yh) + 2, H)
    if len(rows) < 5:
        return None
    ground = np.median(d[rows][:, W // 4: 3 * W // 4], axis=1)          # the ground gets nearer row by row
    ground = np.maximum.accumulate(ground)
    i = int(np.searchsorted(ground, d_obj))
    return float(rows[min(i, len(rows) - 1)])


def commit(name, c, obj_name, description="", abilities=None, fill=True):
    """Save the thing as a library object and (if fill) replace the background by the filled one."""
    meta = images.info(name)
    at = place(name, c)
    oname = images.save_upload(obj_name, cutout_png(name, c), obj_name + ".png", description or obj_name.replace("_", " "),
                               at["height"], None, "object", abilities or [], cutout="off")
    images.update_meta(oname, cut_from=images._clean(name), at=at)
    if fill:
        os.makedirs(BACKUP, exist_ok=True)
        ext = os.path.splitext(meta["file"])[1]
        bak = os.path.join(BACKUP, images._clean(name) + ext)
        if not os.path.exists(bak):                    # the very first original is kept once
            shutil.copyfile(meta["file"], bak)
        f = filled(name, c)
        hp = holes_path(name)                          # the 2.5D step pushes these areas back (see photodepth)
        hole = c["mask"]
        if os.path.exists(hp):
            old = np.asarray(Image.open(hp).convert("L").resize(c["size"], Image.NEAREST)) > 127
            hole = hole | old
        Image.fromarray((hole * 255).astype(np.uint8)).save(hp)
        if ext.lower() in (".jpg", ".jpeg"):
            f.save(meta["file"], quality=92)
        else:
            f.save(meta["file"])
    raw = images.info(name) or {}
    cuts = [x for x in _meta_list(name) if x != oname] + [oname]
    images.update_meta(name, cut_objects=cuts)
    return oname, at


def _meta_list(name):
    meta = images.info(name) or {}
    p = os.path.splitext(meta.get("file", ""))[0] + ".json"
    try:
        with open(p, encoding="utf-8") as fh:
            return list(json.load(fh).get("cut_objects") or [])
    except (OSError, ValueError):
        return []


def holes_path(name):
    return os.path.join(BACKUP, images._clean(name) + "_holes.png")


def undo_all(name):
    """Bring the original picture back (the cut-out objects stay in the library, but are no longer auto-placed)."""
    meta = images.info(name)
    if not meta:
        return False
    ext = os.path.splitext(meta["file"])[1]
    bak = os.path.join(BACKUP, images._clean(name) + ext)
    if os.path.exists(bak):
        shutil.copyfile(bak, meta["file"])
        os.remove(bak)
    if os.path.exists(holes_path(name)):
        os.remove(holes_path(name))
    images.update_meta(name, cut_objects=None)
    return True


def cut_objects(name):
    return _meta_list(name)


# ---------------------------------------------------------------------------- all in one: photo -> interactive place
ABILITY_WORDS = {"tree": ["climb", "hide"], "rock": ["sit", "stand", "hide"], "stone": ["sit", "stand"],
                 "boulder": ["climb", "hide", "stand"], "bush": ["hide"], "log": ["sit", "stand"],
                 "bench": ["sit"], "chair": ["sit"], "pot": ["movable", "break"], "box": ["movable", "open"],
                 "chest": ["open", "sit"], "cart": ["hide"], "well": ["hide"], "wall": ["hide"],
                 "barrel": ["movable", "sit"], "stump": ["sit", "stand"], "fence": ["hide"], "car": ["hide"]}


def _abilities_for(what, given=None):
    if given:
        return list(given)
    w = str(what).lower()
    for k, ab in ABILITY_WORDS.items():
        if k in w:
            return list(ab)
    return ["hide"]


def make_interactive(name, place_name=None, finder="auto", log=print, max_things=8, things=None):
    """One go: 2.5D depth (Depth Anything V2) -> find the things in the photo -> take each out as a REAL object
    (sit / hide / climb ...) with the hole filled -> new depth -> save the photo as an interactive PLACE that
    stories use by name. Returns {"place": name, "objects": [...], "skipped": [...]}."""
    from . import photodepth, registry
    meta = images.info(name)
    if not meta:
        raise ValueError(f"unknown picture '{name}'")
    if not photodepth.status(name):
        log("🧊 making the 2.5D depth (Depth Anything V2)…")
        photodepth.process(name, log=log, preview=False)
    if things is None:
        things = []
        if finder in ("auto", "local"):
            try:
                log("🔍 finding the things in the photo (on this computer)…")
                things = find_local(name, log=log)
            except Exception as ex:
                log(f"  local finder not available ({ex})")
                if finder == "local":
                    raise
        if not things and finder in ("auto", "gemini"):
            from . import vision
            log("✨ asking Gemini what is in the photo…")
            with open(meta["file"], "rb") as fh:
                data = fh.read()
            things = vision.find_things(data, "image/png" if meta["file"].endswith(".png") else "image/jpeg")
    # biggest / clearest first, not the whole picture, not specks
    good = []
    for t in things:
        a, b, c, d = t["box"]
        a, c = min(a, c), max(a, c)
        b, d = min(b, d), max(b, d)
        area = (c - a) * (d - b)
        if not (0.002 < area < 0.2):
            continue                                   # specks, or half the picture
        if b < 0.04 or a < 0.012 or c > 0.988:
            continue                                   # cut by the picture's edge: it can't be taken out cleanly
        good.append(t)
    good.sort(key=lambda t: -(t.get("score") or 0))
    good = good[:max_things]
    made, skipped, used = [], [], set(images.list_images())
    for t in good:
        base = images._clean(t.get("name") or t.get("what") or "thing") or "thing"
        nm, k = base, 1
        while nm in used:
            k += 1
            nm = f"{base}_{k}"
        try:
            log(f"✂ taking out {nm}…")
            c = cut(name, t["box"], t.get("click"))
            oname, at = commit(name, c, nm, t.get("what", nm.replace("_", " ")),
                               _abilities_for(t.get("what", nm), t.get("abilities")), fill=True)
            used.add(oname)
            made.append({"name": oname, "abilities": _abilities_for(t.get("what", nm), t.get("abilities")),
                         "what": t.get("what", nm), "at": at})
        except Exception as ex:
            skipped.append(f"{nm}: {ex}")
    if made:
        log("🧊 new 2.5D depth for the filled photo…")
        photodepth.process(name, log=log, preview=False)
    pn = images._clean(place_name or (name + "_place"))
    have = [x for x in cut_objects(name)] if hasattr(cut_objects, "__call__") else []
    desc = str(meta.get("description") or name.replace("_", " ")).split(" - ")[0]
    objs = made or [{"name": n, "abilities": (images.info(n) or {}).get("abilities") or [], "what": n} for n in have]
    uses = "; ".join(f"{o['name']} ({', '.join(o['abilities'])})" for o in objs)
    spec = {"place": pn, "description": f"{desc}. Real objects in it: {uses}" if uses else desc,
            "base_image": name, "things": [], "interactive": True,
            "objects_in_photo": [o["name"] for o in objs]}
    registry.save("places", pn, spec)
    log(f"💾 saved the interactive place '{pn}'")
    return {"place": pn, "objects": objs, "skipped": skipped}
