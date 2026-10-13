"""Make an uploaded object / prop transparent (remove its background).

  white  built in, instant: removes the plain white (or near-white / light grey) background that touches the
         picture's border - exactly what our object prompts ask for ("alone on pure white"). White INSIDE the
         object (a shirt, a highlight) stays, because the object's outline closes it off. Edges are softened
         and the white fringe is taken out of the edge colours.
  ai     rembg (U2-Net, optional: pip install "rembg[cpu]"), ~1-2 s on a CPU: cuts an object out of any
         background (busy, photo, coloured). The model (176 MB) downloads once on first use.
  auto   already transparent -> keep; plain light border -> white; otherwise -> ai if installed.
"""
import numpy as np
from PIL import Image

_SESSION = None


def ai_available():
    try:
        import rembg  # noqa: F401
        return True
    except Exception:
        return False


def _border(a):
    return np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])


def has_alpha(im):
    if im.mode not in ("RGBA", "LA", "P") and "transparency" not in im.info:
        return False
    a = np.asarray(im.convert("RGBA"))[..., 3]
    return (a < 250).mean() > 0.02


def plain_border(im, tol=28):
    """Share of border pixels that are one plain light colour (white / off-white / light grey)."""
    rgb = np.asarray(im.convert("RGB"), dtype=np.int16)
    b = _border(rgb)
    ref = np.median(b, axis=0)
    if ref.min() < 170:                                # dark or coloured border: not a studio background
        return 0.0, ref
    close = np.abs(b - ref).max(axis=1) <= tol
    return float(close.mean()), ref


def cut_white(im, tol=30):
    """Remove the plain light background connected to the border (flood fill), soft edge, no white fringe."""
    from scipy import ndimage
    rgba = np.asarray(im.convert("RGBA"), dtype=np.float32)
    rgb = rgba[..., :3]
    share, ref = plain_border(im, tol)
    ref = np.asarray(ref, dtype=np.float32)
    near = np.abs(rgb - ref).max(axis=2) <= tol
    lab, n = ndimage.label(near)
    edge_labels = np.unique(_border(lab))
    bg = np.isin(lab, edge_labels[edge_labels > 0])
    alpha = (~bg).astype(np.float32)
    # soft edge: a pixel next to the background gets partial alpha from how far its colour is from the bg
    ring = ndimage.binary_dilation(bg, iterations=2) & ~bg
    dist = np.abs(rgb - ref).max(axis=2) / 255.0
    soft = np.clip(dist / max(tol / 255.0 * 3, 1e-3), 0, 1)
    alpha = np.where(ring, np.minimum(alpha, soft), alpha)
    alpha = ndimage.gaussian_filter(alpha, 0.6) * (~bg) + 0.0
    alpha = np.clip(alpha, 0, 1)
    # take the background colour out of half-transparent edge pixels (no white halo on dark scenes)
    a3 = np.maximum(alpha[..., None], 1e-3)
    clean = np.clip((rgb - ref * (1 - a3)) / a3, 0, 255)
    rgb = np.where(alpha[..., None] < 0.999, clean, rgb)
    a0 = rgba[..., 3] / 255.0
    out = np.dstack([rgb, np.clip(alpha * a0, 0, 1) * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def cut_ai(im):
    global _SESSION
    from rembg import remove, new_session
    if _SESSION is None:
        _SESSION = new_session("u2net")
    return remove(im.convert("RGB"), session=_SESSION).convert("RGBA")


def _trim(im, pad=6):
    """Crop to the object (keeps a small margin) so its height means the object's height."""
    a = np.asarray(im)[..., 3]
    ys, xs = np.nonzero(a > 8)
    if not len(ys):
        return im
    y0, y1 = max(0, ys.min() - pad), min(im.height, ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(im.width, xs.max() + 1 + pad)
    return im.crop((x0, y0, x1, y1))


def cutout(im, mode="auto", trim=True):
    """Returns (RGBA image, method) - method is 'kept' | 'white' | 'ai' | 'none'."""
    mode = (mode or "auto").lower()
    if mode in ("off", "none", "no", "false"):
        return im, "none"
    if mode == "auto" and has_alpha(im):
        return im, "kept"
    method = None
    if mode == "white":
        method = "white"
    elif mode == "ai":
        method = "ai" if ai_available() else "white"
    else:
        share, _ = plain_border(im)
        if share >= 0.85:
            method = "white"
        elif ai_available():
            method = "ai"
        elif share >= 0.55:
            method = "white"
    if method is None:
        return im, "none"
    out = cut_white(im) if method == "white" else cut_ai(im)
    a = np.asarray(out)[..., 3]
    if (a > 8).mean() < 0.01:                          # cut everything away: something went wrong - keep it
        return im, "none"
    return (_trim(out) if trim else out), method
