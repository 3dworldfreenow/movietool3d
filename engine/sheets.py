"""Cut a picture of several separate drawings on a plain (white) background into its pieces.

Used by puppet parts sheets (engine/puppet.py) and object sheets (engine/objsheet.py). No model: the white is
removed (engine/cutout.py), touching pixels are grouped, small crumbs join the nearest big piece, and the
pieces are put in reading order (rows top -> bottom, each row left -> right).
"""
import io

import numpy as np


def load_rgba(data_bytes, max_side=3000):
    from PIL import Image
    im = Image.open(io.BytesIO(data_bytes))
    im.seek(0)
    im = im.convert("RGBA")
    if max(im.size) > max_side:
        k = max_side / max(im.size)
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    return im


def cut_pieces(im, min_share=0.03, pad=4, gap=3):
    """im: RGBA PIL image. Returns [(crop RGBA np.array, (x0, y0, x1, y1), solid_height_px)] in reading order."""
    from scipy import ndimage
    from . import cutout
    rgba = im if cutout.has_alpha(im) else cutout.cut_white(im)
    arr = np.asarray(rgba)
    solid = arr[..., 3] > 90
    joined = ndimage.binary_dilation(solid, iterations=gap)
    lab, n = ndimage.label(joined, structure=np.ones((3, 3)))
    if n == 0:
        raise ValueError("no drawings found - is the background plain white?")
    areas = ndimage.sum(solid, lab, range(1, n + 1))
    big = [i + 1 for i in range(n) if areas[i] >= min_share * areas.max()]
    coms = {i: ndimage.center_of_mass(solid, lab, i) for i in range(1, n + 1)}
    owner = {i: i for i in big}
    for i in range(1, n + 1):                           # crumbs (a hair strand, a spark) join the nearest piece
        if i not in owner:
            owner[i] = min(big, key=lambda b: (coms[b][0] - coms[i][0]) ** 2 + (coms[b][1] - coms[i][1]) ** 2)
    own = np.zeros_like(lab)
    for i, b in owner.items():
        own[lab == i] = b
    boxes = []
    for b in big:
        ys, xs = np.nonzero((own == b) & (arr[..., 3] > 8))
        if len(ys):
            boxes.append((b, ys.min(), ys.max() + 1, xs.min(), xs.max() + 1))
    hmed = np.median([y1 - y0 for _, y0, y1, _, _ in boxes])
    boxes.sort(key=lambda bx: (bx[1] + bx[2]) / 2)
    rows, cur = [], []
    for bx in boxes:                                    # rows by centre height, then left -> right
        if cur and abs((bx[1] + bx[2]) / 2 - np.mean([(c[1] + c[2]) / 2 for c in cur])) > 0.6 * hmed:
            rows.append(cur)
            cur = []
        cur.append(bx)
    rows.append(cur)
    ordered = [bx for row in rows for bx in sorted(row, key=lambda c: c[3])]
    out = []
    for b, y0, y1, x0, x1 in ordered:
        sy0, sy1 = y0, y1
        y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
        y1, x1 = min(arr.shape[0], y1 + pad), min(arr.shape[1], x1 + pad)
        crop = arr[y0:y1, x0:x1].copy()
        crop[..., 3] = np.where(own[y0:y1, x0:x1] == b, crop[..., 3], 0)
        out.append((crop, (int(x0), int(y0), int(x1), int(y1)), int(sy1 - sy0)))
    return out


def _gaps(mask_1d, min_len):
    """Interior runs of empty lines: [(start, end)], longest first."""
    runs, start = [], None
    n = len(mask_1d)
    for i, v in enumerate(mask_1d):
        if not v and start is None:
            start = i
        elif v and start is not None:
            if start > 0 and i - start >= min_len:
                runs.append((start, i))
            start = None
    return sorted(runs, key=lambda r: r[0] - r[1])


def _content(mask_1d):
    idx = [i for i, v in enumerate(mask_1d) if v]
    return (idx[0], idx[-1] + 1) if idx else (0, 0)


def cut_grid(im, per_row, pad=4):
    """Cut a sheet drawn as a grid when we know how many drawings each row has (per_row = [4, 3]).
    Everything inside one cell is ONE piece - a pot broken into shards stays one drawing.
    Returns the same list as cut_pieces, or None when the picture does not show that grid."""
    from . import cutout
    rgba = im if cutout.has_alpha(im) else cutout.cut_white(im)
    arr = np.asarray(rgba)
    solid = arr[..., 3] > 90
    H, W = solid.shape
    rows_any = solid.any(axis=1)
    y0, y1 = _content(rows_any)
    need = len(per_row) - 1
    gaps = _gaps(rows_any[y0:y1], max(4, H // 150))
    if len(gaps) < need:
        return None
    cuts = sorted((y0 + (a + b) // 2) for a, b in gaps[:need])
    bands = list(zip([y0] + cuts, cuts + [y1]))
    out = []
    for (b0, b1), n in zip(bands, per_row):
        cols_any = solid[b0:b1].any(axis=0)
        x0, x1 = _content(cols_any)
        g = _gaps(cols_any[x0:x1], max(4, W // 200))
        if len(g) < n - 1:
            return None
        cx = sorted((x0 + (a + b) // 2) for a, b in g[:n - 1])
        for c0, c1 in zip([x0] + cx, cx + [x1]):
            cell = solid[b0:b1, c0:c1]
            ys, xs = np.nonzero(cell)
            if not len(ys):
                return None
            yy0, yy1 = b0 + ys.min(), b0 + ys.max() + 1
            xx0, xx1 = c0 + xs.min(), c0 + xs.max() + 1
            py0, px0 = max(0, yy0 - pad), max(0, xx0 - pad)
            py1, px1 = min(H, yy1 + pad), min(W, xx1 + pad)
            crop = arr[py0:py1, px0:px1].copy()
            keep = np.zeros(crop.shape[:2], bool)           # only this cell's pixels
            keep[max(0, b0 - py0):b1 - py0, max(0, c0 - px0):c1 - px0] = True
            crop[..., 3] = np.where(keep, crop[..., 3], 0)
            out.append((crop, (int(px0), int(py0), int(px1), int(py1)), int(yy1 - yy0)))
    return out
