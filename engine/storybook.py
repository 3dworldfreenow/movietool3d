"""🖌 The storybook look for 2.5D (settings "art": "storybook"): a hand-made film frame in the spirit of the Irish
hand-drawn features (Wolfwalkers, Song of the Sea) - a rough ink line where shapes meet, pigment pooling at colour
edges like watercolour, paper grain over everything and softer, earthier colours.

It works on the finished frame (numpy on the cairo surface, a few ms a frame), so every place, person and prop gets
the same hand-made look and the render stays fast. Art only - nothing here is physics."""
import numpy as np

_PAPER = {}


def _noise(rng, W, H, cell):
    """smooth value noise: random values on a coarse grid, blown up with bicubic smoothing (0 .. 1)"""
    from PIL import Image
    h, w = max(2, H // cell + 2), max(2, W // cell + 2)
    n = (rng.random((h, w)) * 255).astype(np.uint8)
    im = Image.fromarray(n).resize((W + cell, H + cell), Image.BICUBIC).crop((cell // 2, cell // 2,
                                                                             cell // 2 + W, cell // 2 + H))
    return np.asarray(im, np.float32) / 255.0


def paper(W, H):
    """(texture x1, grain 0..1) for this frame size: soft washes, paper fibres and grain - made once"""
    key = (W, H)
    got = _PAPER.get(key)
    if got is None:
        rng = np.random.default_rng(7)
        s = max(1, round(W / 1280))
        wash = 0.55 * _noise(rng, W, H, 180 * s) + 0.3 * _noise(rng, W, H, 48 * s) + 0.15 * _noise(rng, W, H, 12 * s)
        grain = _noise(rng, W, H, max(2, 2 * s))
        tex = 1.0 - 0.16 * (wash - 0.5) - 0.07 * (grain - 0.5)
        got = _PAPER[key] = (tex.astype(np.float32), grain.astype(np.float32))
    return got


def apply(surf, strength=1.0):
    """the storybook pass, in place, on a cairo ARGB32 surface (BGRA bytes)"""
    surf.flush()
    W, H = surf.get_width(), surf.get_height()
    a = np.ndarray((H, surf.get_stride() // 4, 4), np.uint8, surf.get_data())[:, :W]
    img = a[..., :3].astype(np.float32) * (1.0 / 255.0)          # B, G, R
    lum = img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299
    tex, grain = paper(W, H)
    # ---- ink: where shapes meet (edges of the light), found at half size so the line is a brush, not a hair
    h2, w2 = H // 2 * 2, W // 2 * 2
    sm = lum[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2).mean(axis=(1, 3))
    gx = np.zeros_like(sm)
    gy = np.zeros_like(sm)
    gx[:, 1:-1] = sm[:, 2:] - sm[:, :-2]
    gy[1:-1, :] = sm[2:, :] - sm[:-2, :]
    mag = np.abs(gx) + np.abs(gy)
    ink = np.clip((mag - 0.06) * (1.0 / 0.17), 0.0, 1.0)
    edge = np.zeros((H, W), np.float32)
    edge[:h2, :w2] = np.repeat(np.repeat(ink, 2, axis=0), 2, axis=1)
    # ---- one multiplier per pixel: the ink / pigment at edges (a charcoal line, heavier and lighter by the paper)
    # times the paper texture
    mul = (1.0 - (0.42 * strength) * edge * (0.55 + 0.45 * grain)) * (tex if strength == 1.0 else tex ** strength)
    # ---- colour: softer and earthier, a warm paper white, the darks lifted a little (no pure black)
    img -= lum[..., None]
    img *= 0.86
    img += lum[..., None]
    img *= np.array([0.92, 0.97, 1.0], np.float32)
    img += np.array([0.02, 0.025, 0.035], np.float32)
    img *= mul[..., None] * 255.0
    np.clip(img, 0, 255, out=img)
    a[..., :3] = img.astype(np.uint8)
    surf.mark_dirty()
