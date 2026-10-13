"""🗺 Real land: the true ground heights of any place on Earth (AWS Terrain Tiles - open data from SRTM and others,
~10-30 m detail) as a grid for engine/terrain.py, so a world can sit on the real hills, valleys and cliffs and then
run OUR physics on them (rain runs down, rivers, ponds, where people settle, soil, plants).

    h, info = realterrain.grid(22.4675, 78.4346, size=6000)    # 6 km square round Pachmarhi, 50 m cells, north up

Tiles are fetched once and kept in cache/dem/.  Terrarium encoding: height = R*256 + G + B/256 - 32768 (metres).
"""
import io
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache", "dem")
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
R_EARTH = 6378137.0


def _tile(z, x, y):
    path = os.path.join(CACHE, str(z), str(x), f"{y}.png")
    if not os.path.exists(path):
        import urllib.request
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with urllib.request.urlopen(URL.format(z=z, x=x, y=y), timeout=30) as r:
            data = r.read()
        with open(path, "wb") as fh:
            fh.write(data)
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float64)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


def _xy(lat, lon, z):
    """-> the global pixel position (256-px tiles) of lat / lon at zoom z"""
    n = 256 * 2 ** z
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def grid(lat, lon, size=6000.0, cell=50.0, z=14):
    """-> (h [n x n] metres above sea level, row 0 = SOUTH edge, column 0 = WEST edge; info)"""
    n = int(size / cell)
    mpp = 2 * math.pi * R_EARTH * math.cos(math.radians(lat)) / (256 * 2 ** z)    # metres per pixel here
    cx, cy = _xy(lat, lon, z)
    half = size / 2 / mpp
    x0, x1, y0, y1 = cx - half, cx + half, cy - half, cy + half
    tx0, tx1, ty0, ty1 = int(x0 // 256), int(x1 // 256), int(y0 // 256), int(y1 // 256)
    big = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            big[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = _tile(z, tx, ty)
    # sample the cell centres (bilinear), north up -> flip so row 0 is the south edge
    h = np.zeros((n, n))
    for i in range(n):                                  # i: north -> south in pixel rows
        py = y0 + (i + 0.5) * cell / mpp - ty0 * 256
        for j in range(n):
            px = x0 + (j + 0.5) * cell / mpp - tx0 * 256
            a, b = int(py), int(px)
            fa, fb = py - a, px - b
            a1, b1 = min(a + 1, big.shape[0] - 1), min(b + 1, big.shape[1] - 1)
            h[i, j] = (big[a, b] * (1 - fa) * (1 - fb) + big[a, b1] * (1 - fa) * fb + big[a1, b] * fa * (1 - fb) +
                       big[a1, b1] * fa * fb)
    h = h[::-1].copy()
    # a cell is the average of what it covers (the tile pixels are smaller): a light blur against single-pixel noise
    from scipy.ndimage import uniform_filter
    h = uniform_filter(h, size=2, mode="nearest")
    info = {"lat": lat, "lon": lon, "size_m": size, "cell_m": cell, "zoom": z, "m_per_px": round(mpp, 2),
            "min_m": round(float(h.min()), 1), "max_m": round(float(h.max()), 1),
            "source": "AWS Terrain Tiles (Mapzen terrarium; SRTM / NED / ETOPO and others, open data)"}
    return h, info


def offset(lat, lon, east_m, north_m):
    """the lat / lon that is east_m east and north_m north of lat / lon"""
    return (lat + math.degrees(north_m / R_EARTH),
            lon + math.degrees(east_m / (R_EARTH * math.cos(math.radians(lat)))))
