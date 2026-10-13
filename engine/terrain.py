"""🏞 Land made by physics for the big 3D worlds (worlds/<name>.json) - the same rules as the planet walk, on Earth:

    the land     a height field (metres) from layered noise: gentle plains, rolling hills, a ridge of higher hills
                 on one side; slope = how steep each 50 m cell is
    the water    rain falls everywhere and runs downhill: every cell drains to its lowest neighbour (D8); hollows with
                 no way out fill up to their rim first (lakes and ponds - "priority flood"); the water that passes each
                 cell is counted (the land that drains through it). Where enough land drains through a line of cells,
                 a stream runs; more land -> a river. A river's width grows with its flow (w ∝ Q^½, Leopold's
                 hydraulic geometry)
    the floods   the low, flat land right by a river is its flood plain (it goes under water in a big flood - and is
                 the most fertile: the silt): fields there, no houses
    land use     steep slopes and high ground: forest / hills; flat fertile land near water: fields; dry flat land:
                 grass; bare rock on the steepest
    the town     where people really settle: flat land, close to water, but above the flood plain, on a road -
                 the best-scoring spot becomes the town's chowk
Nothing here is drawn: it writes a world map (rivers, areas, places, roads) that engine/world3d.py already draws,
plus a small height grid ("terrain") so the slopes and the flood level are known. A story can still change any of it
(the world's "edits" / its own scene settings win).
"""
import math

import numpy as np

from .util import stable_hash

CELL = 50.0                                      # metres per grid cell
POND_DEPTH, POND_CELLS = 0.8, 2                  # a hollow this deep (m) and big (cells) holds a pond


def _noise(seed, n):
    """smooth value noise on an n×n grid, several octaves (fbm), 0..1"""
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n))
    amp, tot = 1.0, 0.0
    for octv in range(5):
        k = 2 ** octv * 2 + 1                     # control points per side
        g = rng.random((k + 1, k + 1))
        xs = np.linspace(0, k, n)
        i0 = np.floor(xs).astype(int).clip(0, k - 1)
        f = xs - i0
        f = f * f * (3 - 2 * f)                   # smoothstep
        a = g[i0][:, i0]; b = g[i0][:, i0 + 1]; c = g[i0 + 1][:, i0]; d = g[i0 + 1][:, i0 + 1]
        fx, fy = f[None, :], f[:, None]
        out += amp * (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy)
        tot += amp
        amp *= 0.5
    return out / tot


def heights(seed, n=100, relief=60.0):
    """the land (metres): plains + hills + a ridge on one side (which side: from the seed)"""
    base = _noise(seed, n)
    detail = _noise(seed + 7, n)
    side = stable_hash(f"ridge|{seed}") % 4
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
    edge = [xx, 1 - xx, yy, 1 - yy][side]          # 0 at the ridge side .. 1 far from it
    ridge = np.clip(1 - edge * 2.2, 0, 1) ** 1.6
    tilt = (1 - edge) * 0.35                       # the whole land slopes gently away from the ridge
    h = relief * (0.55 * base + 0.15 * detail + 1.6 * ridge + tilt)
    return h - h.min()


def fill(h):
    """priority flood: raise every hollow to its spill height (lakes / ponds) -> (filled, depth)"""
    import heapq
    n = h.shape[0]
    f = np.full_like(h, np.inf)
    seen = np.zeros(h.shape, bool)
    pq = []
    for i in range(n):
        for j in (0, n - 1):
            for (a, b) in ((i, j), (j, i)):
                if not seen[a, b]:
                    seen[a, b] = True; f[a, b] = h[a, b]; heapq.heappush(pq, (h[a, b], a, b))
    while pq:
        z, a, b = heapq.heappop(pq)
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                x, y = a + da, b + db
                if (da or db) and 0 <= x < n and 0 <= y < n and not seen[x, y]:
                    seen[x, y] = True
                    f[x, y] = max(h[x, y], z + 1e-3)
                    heapq.heappush(pq, (f[x, y], x, y))
    return f, f - h


def flow(f):
    """D8: every cell drains to its steepest lower neighbour; accumulation = cells draining through it"""
    n = f.shape[0]
    down = -np.ones((n, n, 2), int)
    for a in range(n):
        for b in range(n):
            best, drop = None, 0.0
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    x, y = a + da, b + db
                    if (da or db) and 0 <= x < n and 0 <= y < n:
                        d = (f[a, b] - f[x, y]) / (1.414 if da and db else 1.0)
                        if d > drop:
                            drop, best = d, (x, y)
            if best:
                down[a, b] = best
    acc = np.ones((n, n))
    order = np.dstack(np.unravel_index(np.argsort(-f, axis=None), f.shape))[0]
    for a, b in order:
        x, y = down[a, b]
        if x >= 0:
            acc[x, y] += acc[a, b]
    return down, acc


def rivers(down, acc, stream_cells=300, river_cells=1500):
    """the stream / river lines (grid cells), from where enough land drains through them down to the edge"""
    n = acc.shape[0]
    on = acc >= stream_cells
    lines, used = [], np.zeros((n, n), bool)
    # start at the heads: stream cells no stream cell flows into
    feeds = np.zeros((n, n), int)
    for a in range(n):
        for b in range(n):
            x, y = down[a, b]
            if on[a, b] and x >= 0:
                feeds[x, y] += 1
    heads = [(a, b) for a in range(n) for b in range(n) if on[a, b] and feeds[a, b] == 0]
    heads.sort(key=lambda p: -acc[p])
    for a, b in heads:                              # follow each one downhill until it meets a river already traced or the edge
        pts, cur = [], (a, b)
        while True:
            pts.append(cur)
            if used[cur] and len(pts) > 1:
                break                                   # (it joins a bigger river here)
            nx = tuple(down[cur])
            if nx[0] < 0:
                break                                   # (it leaves the map)
            cur = nx
        for c in pts:
            used[c] = True
        if len(pts) >= 3:
            lines.append(pts)
    return lines


def make(seed, size=5000.0, name="world", title=None, h=None, base=0.0):
    """the physics part of a world map: {"terrain", "rivers", "areas", "site", "why"} (metres, x east, z north).
    h = a real height grid (engine/realterrain.py, row 0 = south) instead of the made-up one; base = its height
    above sea level (kept in the terrain as "base_m": the grid itself starts at 0)."""
    if h is None:
        n = int(size / CELL)
        h = heights(seed, n)
    else:
        h = np.asarray(h, float)
        n = h.shape[0]
        base = base + float(h.min())
        h = h - h.min()
    f, depth = fill(h)
    down, acc = flow(f)
    gy, gx = np.gradient(h, CELL)
    slope = np.hypot(gx, gy)                                          # rise per metre
    km2 = CELL * CELL / 1e6
    out = {"terrain": {"cell": CELL, "n": n, "seed": int(seed), "base_m": round(float(base), 1),
                       "h": [[int(round(v)) for v in row] for row in h.tolist()]},
           "rivers": [], "areas": [], "why": []}

    def xz(p):
        return [round(float(p[1]) * CELL + CELL / 2, 1), round(float(p[0]) * CELL + CELL / 2, 1)]
    # rivers and streams
    river_mask = np.zeros_like(acc, bool)
    for k, line in enumerate(rivers(down, acc)):
        q = max(acc[c] for c in line) * km2                              # km² draining through its end
        w = round(min(60.0, 2.0 + 6.5 * math.sqrt(q)), 1)              # w ∝ Q^½ (Q ∝ the area that drains)
        pts = [xz(c) for c in line[::2]] + [xz(line[-1])]
        out["rivers"].append({"id": f"nadi_{k + 1}" if w >= 12 else f"nala_{k + 1}", "points": pts, "width": w,
                              "why": f"rain from {q:.1f} km² runs down to here"})
        for c in line:
            river_mask[c] = True
    # lakes and ponds: the filled hollows
    lab = np.zeros_like(depth, int)
    k = 0
    for a in range(n):
        for b in range(n):
            if depth[a, b] > POND_DEPTH and not lab[a, b]:
                k += 1
                stack, cells = [(a, b)], []
                lab[a, b] = k
                while stack:
                    x, y = stack.pop(); cells.append((x, y))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        u, v = x + dx, y + dy
                        if 0 <= u < n and 0 <= v < n and depth[u, v] > POND_DEPTH * 0.5 and not lab[u, v]:
                            lab[u, v] = k; stack.append((u, v))
                if len(cells) >= POND_CELLS:
                    ca = np.mean([c[0] for c in cells]); cb = np.mean([c[1] for c in cells])
                    r = math.sqrt(len(cells) / math.pi) * CELL
                    kind = "lake" if len(cells) > 20 else "pond"
                    out["areas"].append({"id": f"{kind}_{k}", "kind": kind, "at": xz((ca, cb)), "radius": round(r),
                                         "why": f"a hollow with no way out: rain fills it {depth[tuple(cells[0])]:.1f} m deep up to its rim"})
    # hills / forest on the high and steep land
    hi = np.percentile(h, 85)
    seen = np.zeros_like(h, bool)
    for a in range(0, n, 6):
        for b in range(0, n, 6):
            blk = (slice(a, a + 6), slice(b, b + 6))
            hh, ss = h[blk].mean(), slope[blk].mean()
            if hh > hi:
                out["areas"].append({"id": f"pahadi_{a}_{b}", "kind": "hills", "at": xz((a + 3, b + 3)), "radius": 170,
                                     "height": round(float(hh)), "why": "the high ridge"})
            elif ss > 0.06:
                out["areas"].append({"id": f"jungle_{a}_{b}", "kind": "jungle", "at": xz((a + 3, b + 3)), "radius": 160,
                                     "why": f"too steep to plough ({ss * 100:.0f} % slope): left as forest"})
    # the flood plain and fields: low, flat land beside the rivers
    from scipy.ndimage import distance_transform_edt as edt
    dist = edt(~river_mask) * CELL
    plain = (dist < 220) & (slope < 0.03)
    for a in range(0, n, 5):
        for b in range(0, n, 5):
            blk = (slice(a, a + 5), slice(b, b + 5))
            if plain[blk].mean() > 0.6 and not river_mask[blk].any():
                out["areas"].append({"id": f"khet_{a}_{b}", "kind": "fields", "at": xz((a + 2.5, b + 2.5)), "radius": 120,
                                     "why": "flat land in the flood plain: river silt makes it fertile"})
    # the town: flat, close to water, above the flood plain, not too high
    score = np.full_like(h, -1e9)
    for a in range(4, n - 4):
        for b in range(4, n - 4):
            if river_mask[a, b] or depth[a, b] > 0.3:
                continue
            d = dist[a, b]
            local = h[a - 3:a + 4, b - 3:b + 4]
            flat = slope[a - 3:a + 4, b - 3:b + 4].mean()
            above = h[a, b] - local.min()
            water_ok = 1.0 if 250 <= d <= 700 else (0.4 if d < 250 else max(0.0, 1.2 - d / 1500))
            dry = 1.0 if above >= 2.0 or d > 300 else 0.2                 # above the flood
            centre = 1 - (abs(a - n / 2) + abs(b - n / 2)) / n             # (a bit toward the middle of the map)
            score[a, b] = 3 * water_ok * dry - 40 * flat + 0.8 * centre - h[a, b] / 150
    a, b = np.unravel_index(np.argmax(score), score.shape)
    out["site"] = {"at": xz((a, b)), "height": round(float(h[a, b]), 1), "river_m": round(float(dist[a, b])),
                   "slope_pct": round(float(slope[a, b]) * 100, 1)}
    out["why"] = [f"rain runs downhill: {len(out['rivers'])} streams / rivers, wider the more land drains into them",
                  f"{sum(1 for x in out['areas'] if x['kind'] in ('pond', 'lake'))} ponds / lakes in hollows with no way out",
                  "forest on slopes too steep to plough, fields on the flat fertile flood plain",
                  f"the town sits where people settle: flat ({out['site']['slope_pct']} % slope), "
                  f"{out['site']['river_m']} m from the river, above its flood plain"]
    return out


def height_at(terrain, x, z):
    """the ground height (m) at world x, z from a saved terrain grid (bilinear)"""
    c, n, H = terrain["cell"], terrain["n"], terrain["h"]
    u, v = max(0.0, min(n - 1.001, x / c - 0.5)), max(0.0, min(n - 1.001, z / c - 0.5))
    i, j = int(v), int(u)
    fu, fv = u - j, v - i
    return (H[i][j] * (1 - fu) * (1 - fv) + H[i][j + 1] * fu * (1 - fv) + H[i + 1][j] * (1 - fu) * fv + H[i + 1][j + 1] * fu * fv)


# ------------------------------------------------------------------------------------------------ a town on the land
def town_world(name, seed, title, description, layout, residents=None, size=5000.0, h=None, base=0.0):
    """a whole world map: the land by physics (make) + a town laid out round its best site.
    layout = [{"id", "type" (an object3d) | "place" (a place3d), "off": [east, north] metres from the chowk, "turn",
    "description"}]. Roads: a main road through the chowk to the map edges, and a lane down to the river (the ghat)."""
    w = make(seed, size, name, title, h=h, base=base)
    sx, sz = (float(v) for v in w["site"]["at"])
    places, objects = [], []
    for it in layout:
        ox, oz = it.get("off", [0, 0])
        at = [round(sx + ox, 1), round(sz + oz, 1)]
        row = {"id": it["id"], "at": at, "turn": it.get("turn", 0), "description": it.get("description", "")}
        if it.get("place"):
            places.append(dict(row, place=it["place"]))
        if it.get("type"):
            objects.append(dict(row, id=it["id"] + ("_ghar" if it.get("place") else ""), type=it["type"]))
    # the nearest river: the ghat lane and the ghat itself
    best = None
    for r in w["rivers"]:
        for p in r["points"]:
            d = math.hypot(p[0] - sx, p[1] - sz)
            if best is None or d < best[0]:
                best = (d, p, r)
    roads = [{"id": "main_sadak", "points": [[0, round(sz)], [round(sx - 300), round(sz + 10)], [round(sx), round(sz)],
                                              [round(sx + 300), round(sz - 10)], [round(size), round(sz)]], "width": 7, "style": "tar"}]
    if best:
        d, p, r = best
        k = max(0.0, (d - 25) / max(d, 1.0))
        gx, gz = sx + (p[0] - sx) * k, sz + (p[1] - sz) * k
        roads.append({"id": "ghat_rasta", "points": [[round(sx), round(sz)], [round(gx), round(gz)]], "width": 4, "style": "dirt"})
        places.append({"id": "ghat", "place": "river_3d", "at": [round(gx, 1), round(gz, 1)],
                       **({"water": "none"} if h is not None else {}),
                       "turn": round(math.degrees(math.atan2(p[0] - sx, p[1] - sz))),
                       "description": f"the ghat on the {r['id']} ({r['width']} m wide)"})
    areas = list(w["areas"]) + [{"id": "basti", "kind": "village", "at": [round(sx), round(sz)], "radius": 320,
                                 "why": "the town: flat, dry land by the river"}]
    spec = {"world": name, "title": title, "description": description, "size": [size, size], "ground": "grass",
            "time": "morning", "far": ["hills", "fields"], "places": places, "roads": roads, "rivers": w["rivers"],
            "areas": areas, "objects": objects, "residents": residents or {}, "edits": {}, "removed": [],
            "terrain": w["terrain"], "physics": {"site": w["site"], "why": w["why"]}}
    return spec
