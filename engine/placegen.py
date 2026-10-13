"""Places from a simple English list (a "place JSON"): the engine arranges everything by itself.

    {
      "place": "dipanshi_village",
      "description": "small village near a river, evening",
      "ground": "mud", "time": "evening", "sky": "golden", "clouds": "puffy", "far": "hills",
      "water": {"kind": "river", "side": "right"},          (or "none"; side left / right / all)
      "path": true,
      "things": [
        {"what": "neem tree", "count": 6, "where": "back"},
        {"what": "hut", "count": 3, "where": "left"},
        {"what": "my_rock", "count": 4, "where": "near water"},
        {"what": "well", "where": "middle"},
        {"what": "gulmohar tree", "count": 20, "where": "far"}
      ]
    }

"what"   a built-in thing (tree kinds, hut, house, well, temple, rock, log, pot, bench, lamp ...) or the name of
         one of YOUR pictures (Studio > Images). Unknown names are reported (with "did you mean"), so they can be
         drawn by Gemini on one object sheet and cut out.
"where"  plain words: near / front, middle, back, far, horizon  +  left, right, center, sides, everywhere
         + near water, along path, around <other thing>.  "count", "size" (tiny / small / medium / big / huge, or a number), "height" (your pictures only)

Rules applied automatically: real sizes, real depth (z) with parallax (2D) or a real 3D world (3D), no overlapping, the middle of the stage
stays free for the characters, land things stay on land, the path stays open, same JSON + seed = same place.
Small things near the stage become real objects (people walk around them, sit, hide behind them).
"""
import difflib
import math

from . import sizes
import random
import re

GROUND_WORDS = {"grass": "grass", "green": "grass", "lawn": "grass", "dry_grass": "dark_grass", "dark_grass": "dark_grass",
                "mud": "dirt", "dirt": "dirt", "soil": "dirt", "earth": "dirt", "kaccha": "dirt", "sand": "sand",
                "beach": "sand", "desert": "sand", "road": "road", "tar": "road", "asphalt": "road", "stone": "stone",
                "rocky": "stone", "snow": "snow", "ice": "snow", "tiles": "tiles", "floor": "tiles", "wood": "wood",
                "wooden": "wood", "farm": "#8cc063", "field": "#8cc063"}
# depth words -> story z range (0 = front of the stage, 1000 = back of the stage, beyond = the distance)
DEPTH = {"near": (60, 230), "front": (60, 230), "close": (60, 230), "foreground": (0, 120),
         "middle": (280, 560), "mid": (280, 560), "center_depth": (280, 560),
         "back": (620, 950), "behind": (620, 950), "background": (700, 1000),
         "far": (1300, 2600), "distance": (1300, 2600), "distant": (1300, 2600),
         "horizon": (2800, 5000), "very_far": (2800, 5000)}
SIDE = {"left": (0.02, 0.36), "right": (0.64, 0.98), "center": (0.4, 0.6), "centre": (0.4, 0.6),
        "everywhere": (0.02, 0.98), "all": (0.02, 0.98), "around": (0.02, 0.98), "across": (0.02, 0.98),
        "sides": None, "both_sides": None, "edges": None}
DROP = {"a", "an", "the", "some", "few", "many", "of", "and", "with", "old", "new", "nice", "pretty", "little"}

# built-in background things (engine drawers) and the words people use for them
SCENERY = {"hut": "hut", "jhopdi": "hut", "house": "house", "home": "house", "ghar": "house", "shop": "shop",
           "dukaan": "shop", "building": "building", "flat": "building", "apartment": "building",
           "temple": "lm_temple", "mandir": "lm_temple", "school": "lm_school", "well": "lm_well", "kuan": "lm_well",
           "water_tank": "lm_water_tank", "tank": "lm_water_tank", "statue": "lm_statue", "windmill": "lm_windmill",
           "lighthouse": "lm_lighthouse", "clock_tower": "lm_clock_tower", "fountain": "lm_fountain",
           "bench": "bench", "lamp": "lamp", "street_lamp": "lamp", "lamp_post": "lamp", "fence": "fence",
           "stall": "stall", "market_stall": "stall", "thela": "stall", "barn": "barn", "cow_shed": "barn",
           "shed": "barn", "sign": "sign", "signboard": "sign", "board": "sign", "swing": "swing", "jhula": "swing",
           "slide": "slide", "umbrella": "umbrella", "flower": "flower", "flowers": "flower", "grass": "grass",
           "reeds": "reeds", "mushroom": "mushroom", "cactus": "cactus", "fern": "fern", "plant": "plant",
           "tombstone": "tombstone", "grave": "tombstone", "bus_shelter": "bus_shelter", "bus_stop": "bus_shelter",
           "chai_stall": "chai_stall", "tea_stall": "chai_stall", "ferris_wheel": "ferris_wheel",
           "clothesline": "clothesline", "pole": "pole", "electric_pole": "pole", "crops": "crops",
           "mustard": "mustard", "bridge": "bridge", "diya": "diya", "lantern": "lantern", "torch": "torch",
           "bell": "bell_post", "banana_plant": "banana", "hay": "haystack"}
# things that become REAL objects (walk around, sit, hide) when they are near the stage
OBJECTISH = ("stone", "rock", "boulder", "log", "chest", "crate", "barrel", "pot", "bush", "haystack", "ball",
             "box", "gift", "apple", "bag", "book", "stick")
# things of the SKY and the FAR VIEW can also be listed in "things" (no position needed)
SKY_THINGS = {"cloud": "clouds", "clouds": "clouds", "rainbow": "rainbow", "moon": "moon", "full_moon": "moon",
              "half_moon": "moon", "crescent_moon": "moon", "sun": "sun", "birds": "birds", "bird_flock": "birds",
              "flock": "birds", "kite": "kites", "kites": "kites", "aurora": "aurora", "northern_lights": "aurora",
              "shooting_star": "shooting_star", "stars": "stars", "milky_way": "milky_way"}
FAR_THINGS = {"mountains": "mountains", "mountain": "mountains", "snow_mountains": "mountains",
              "himalaya": "mountains", "blue_mountains": "blue_mountains", "hills": "hills", "far_hills": "hills",
              "green_hills": "hills", "dry_hills": "dry_hills", "brown_hills": "dry_hills", "dunes": "dunes",
              "sand_dunes": "dunes", "city": "city", "skyline": "city", "far_city": "city", "town": "city",
              "sea": "sea", "ocean": "sea", "fields": "fields", "far_fields": "fields", "farms": "fields",
              "far_forest": "forest", "forest": "forest", "jungle": "forest"}
FAR_LIST = ("mountains", "blue_mountains", "hills", "dry_hills", "dunes", "city", "sea", "fields", "forest")
# footprint (story units wide) used for spacing
WIDTH = {"tree": 420, "hut": 620, "house": 850, "shop": 750, "building": 300, "barn": 720, "lm_temple": 1100,
         "lm_school": 1180, "lm_well": 200, "lm_water_tank": 260, "stall": 340, "bench": 220, "lamp": 60,
         "fence": 600, "sign": 120, "swing": 300, "slide": 300, "flower": 40, "grass": 60, "reeds": 80,
         "mushroom": 50, "cactus": 120, "fern": 120, "plant": 90, "tombstone": 100, "bus_shelter": 600,
         "chai_stall": 520, "ferris_wheel": 700, "pole": 60, "bridge": 700, "diya": 30, "umbrella": 300}
BIG = 200     # things taller than this keep the middle of the stage free


def _lit_look(name, time):
    """a clay house's "night" picture (a lamp inside, its windows glowing) after dark, a lamp's "on" one from sunset
    (the same hours as engine/world3d.py World3D._lit_state)"""
    from . import images
    from .world3d import World3D
    t = str(time or "").lower().strip().replace(" ", "_")
    if t in World3D.WINDOWS_LIT and images.exists(f"{name}_night"):
        return f"{name}_night"
    if t in World3D.LAMPS_ON and images.exists(f"{name}_on"):
        return f"{name}_on"
    return None


def _norm(s):
    s = re.sub(r"[^a-z0-9 _-]+", " ", str(s or "").lower()).replace("-", " ").replace("_", " ")
    return [w for w in s.split() if w]


def _key(words):
    return "_".join(words)


# ============================================================================ what is it?
def known_names():
    """Everything a place can use: built-in words + tree kinds + objects + your pictures."""
    from . import images, objects
    from .nature import MORE_TREES, TREE_ALIASES
    trees = ["round", "pine", "palm", "banyan", "mango", "coconut", "banana_tree", "acacia", "cactus_tree", "bare",
             "blossom", "mushroom_tree"] + list(MORE_TREES)
    return {"scenery": sorted(SCENERY), "trees": [t if t.endswith("tree") else t + "_tree" for t in trees]
            + sorted(TREE_ALIASES), "objects": sorted(set(objects.BUILTIN) | set(objects.ALIASES)),
            "pictures": sorted(images.list_images())}


def resolve(what):
    """-> dict(kind = scenery | tree | object | image, type, kind_of_tree, size) or dict(missing, suggest)."""
    from . import images, objects
    from .nature import MORE_TREES, TREE_ALIASES, canon_tree
    raw = str(what or "").strip()
    pics = images.list_images()
    for cand in (raw, _key(_norm(raw))):
        if cand in pics:
            return {"kind": "image", "type": cand, "size": 1.0, "sw": None}
    words = _norm(raw)
    size = 1.0
    sw, words = sizes.split_words(words)             # "big hut" -> big + hut  (engine/sizes.py)
    words = [w for w in words if w not in DROP] or words
    key = _key(words)
    if not key:
        return {"missing": raw, "suggest": []}
    k2 = key[4:] if key.startswith("far_") and key[4:] in FAR_THINGS else key
    if k2 in FAR_THINGS:
        return {"kind": "far", "type": FAR_THINGS[k2], "size": 1.0}
    if key in SKY_THINGS:
        return {"kind": "sky", "type": SKY_THINGS[key], "size": 1.0, "words": words}
    # 1. your own pictures (exact name, with or without _ / s)
    for cand in (raw.strip(), key, key.rstrip("s"), key.replace("_", "")):
        if cand in pics:
            return {"kind": "image", "type": cand, "size": size, "sw": sw}
    # 2. trees
    tree_kinds = {"round", "pine", "palm", "banyan", "mango", "coconut", "banana_tree", "acacia", "cactus_tree",
                  "bare", "blossom", "mushroom_tree"} | set(MORE_TREES)
    t_words = [w for w in words if w not in ("tree", "trees", "ped", "paed")]
    if "tree" in words or "trees" in words or key in TREE_ALIASES or canon_tree(key) in tree_kinds:
        k = canon_tree(_key(t_words) or "round")
        k = k.rstrip("s") if k not in tree_kinds and k.rstrip("s") in tree_kinds else k
        k = k + "_tree" if k not in tree_kinds and k + "_tree" in tree_kinds else k
        if k in tree_kinds:
            return {"kind": "tree", "type": "tree", "tree": k, "size": size, "sw": sw}
        if not t_words:
            return {"kind": "tree", "type": "tree", "tree": "round", "size": size, "sw": sw}
    # 3. built-in objects (stone, rock, log, pot, chest ...)
    for cand in (key, key.rstrip("s")):
        bt = objects.base_type(cand)
        if bt in objects.BUILTIN:
            return {"kind": "object", "type": bt, "size": size, "sw": sw}
    # 4. built-in scenery
    for cand in (key, key.rstrip("s"), words[-1], words[-1].rstrip("s")):
        if cand in SCENERY:
            return {"kind": "scenery", "type": SCENERY[cand], "size": size, "sw": sw}
    # 5. your pictures by description ("the red cart" -> a picture described as "red wooden cart")
    best, score = None, 0.0
    for n, m in pics.items():
        d = set(_norm((m or {}).get("description", "")) + _norm(n))
        s = len(set(words) & d) / max(1, len(words))
        if s > score:
            best, score = n, s
    if best and score >= 0.99:
        return {"kind": "image", "type": best, "size": size, "sw": sw}
    pool = list(SCENERY) + [t + "_tree" for t in tree_kinds] + list(objects.BUILTIN) + list(pics)
    sug = difflib.get_close_matches(key, pool, n=3, cutoff=0.6)
    return {"missing": raw, "name": key, "suggest": sug}


# ============================================================================ where does it go?
def _where(where, rng, W, shore):
    """-> (x_lo, x_hi) in story x, (z_lo, z_hi), flags"""
    words = _norm(where or "middle")
    joined = " ".join(words)
    zr = None
    for w in words:
        if w in DEPTH:
            zr = DEPTH[w]
    if "very far" in joined:
        zr = DEPTH["horizon"]
    xr = None
    for w in words:
        if w in SIDE:
            xr = SIDE[w] if SIDE[w] else (SIDE["left"] if rng.random() < 0.5 else SIDE["right"])
            if w in ("sides", "both_sides", "edges"):
                xr = "sides"
    flags = {"water": any(w in words for w in ("water", "river", "lake", "shore", "bank", "riverbank", "pond")),
             "on_hill": ("hill" in words or "hilltop" in words or "top" in words) and
             any(w in words for w in ("on", "top", "hilltop", "upon", "atop")),
             "path": "path" in words or "road" in words,
             "center": "center" in words or "centre" in words,
             "around": None}
    m = re.search(r"(around|near|beside|next to|by)\s+(the\s+)?([a-z0-9_ ]+)$", joined)
    if m and not flags["water"] and not flags["on_hill"] and m.group(3).strip() not in DEPTH and m.group(3).strip() not in SIDE:
        flags["around"] = m.group(3).strip().replace(" ", "_")
    if zr is None:
        zr = DEPTH["middle"] if not flags["water"] else (150, 700)
    if xr is None:
        xr = SIDE["everywhere"]
    if flags["water"] and shore:
        sx, land = shore
        xr = ((sx - 260) / W, (sx - 40) / W) if land == "left" else ((sx + 40) / W, (sx + 260) / W)
    elif shore and xr != "sides":                       # keep the range on the land
        sx, land = shore
        lo, hi = xr
        if land == "left":
            lo, hi = lo, min(hi, (sx - 80) / W)
            if hi - lo < 0.06:
                lo, hi = max(0.02, (sx - 600) / W), (sx - 80) / W
        else:
            lo, hi = max(lo, (sx + 80) / W), hi
            if hi - lo < 0.06:
                lo, hi = (sx + 80) / W, min(0.98, (sx + 600) / W)
        xr = (lo, hi)
    return xr, zr, flags


ROAD_WORDS = {"road": "tar", "tar_road": "tar", "pakki_sadak": "tar", "sadak": "tar", "highway": "highway",
              "main_road": "tar", "street": "tar", "dirt_road": "dirt", "mud_road": "dirt", "kaccha_road": "kaccha",
              "kachcha_road": "kaccha", "village_road": "village", "gravel_road": "stone", "stone_road": "stone",
              "footpath": "footpath", "foot_path": "footpath", "pagdandi": "footpath", "trail": "footpath",
              "sand_road": "sand"}
ROAD_DEPTH = {"near": (0, 230), "front": (0, 230), "middle": (250, 520), "mid": (250, 520),
              "back": (600, 880), "far": (1100, 1500)}


HILL_WORDS = ("hill", "mound", "tila", "teela", "pahadi", "hillock", "knoll", "hilltop")
HILL_STYLE = {"rocky": "rocky", "stony": "rocky", "dry": "dry", "brown": "dry", "snow": "snow", "snowy": "snow",
              "sandy": "sand", "sand": "sand", "forest": "forest", "green": "grass", "grassy": "grass"}


def _is_pic(what):
    """A picture in the library by exactly this name (code places: 'hill_station_3d_bench' is a picture, not a hill)."""
    from . import images
    return bool(what) and str(what).strip() in images.list_images()


def hill_info(what):
    """'big rocky hill with a path' -> {'sw': 'big', 'style': 'rocky', 'trail': True, 'steep': False} or None"""
    words = _norm(what)
    if not any(w in HILL_WORDS for w in words):
        return None
    sw, rest = sizes.split_words(words)
    style = next((HILL_STYLE[w] for w in rest if w in HILL_STYLE), "grass")
    return {"sw": sw or "medium", "style": style, "trail": any(w in ("path", "trail", "steps", "road") for w in rest),
            "steep": any(w in ("steep", "tall", "pointed", "sharp") for w in rest)}


def _hill_h(h, x, z, with_depth=True):
    u = abs(x - h["xc"]) / h["a"]
    v = abs(z - h["zc"]) / h["b"]
    if u >= 1.0 or (with_depth and v >= 1.0):
        return 0.0
    fu = 1.0 if u < h["top"] else math.cos(math.pi / 2 * (u - h["top"]) / (1.0 - h["top"])) ** 2
    fv = 1.0 if (not with_depth or v < 0.35) else math.cos(math.pi / 2 * (v - 0.35) / 0.65) ** 2
    return h["H"] * fu * fv


def road_word(what):
    k = _key([w for w in _norm(what) if w not in DROP])
    return ROAD_WORDS.get(k)


def road_element(r):
    """"near" / {"where": "middle", "style": "dirt"} / {"what": "dirt road", "where": "back"} -> a road_band"""
    if isinstance(r, str):
        r = {"where": r}
    if not isinstance(r, dict):
        return None
    style = str(r.get("style") or road_word(r.get("what", "road")) or "tar").lower()
    words = _norm(r.get("where", "middle"))
    z0, z1 = ROAD_DEPTH["middle"]
    for w in words:
        if w in ROAD_DEPTH:
            z0, z1 = ROAD_DEPTH[w]
    # a real width across (world units, adult = 300): tar road ~6 m, dirt ~4.5 m, footpath ~2 m
    from .world3d import Z_of_z
    width = {"highway": 1300, "tar": 1000, "road": 1000, "stone": 800, "dirt": 750, "kaccha": 750,
             "village": 750, "sand": 700, "footpath": 320}.get(style, 900)
    width *= {"narrow": 0.7, "small": 0.7, "wide": 1.3, "big": 1.3}.get(str(r.get("size", "")).lower(), 1.0)
    z0 = max(0.0, z0 - 20)
    z1 = _z_of_Z(Z_of_z(z0) + width)
    if "z0" in r:
        z0, z1 = float(r["z0"]), float(r.get("z1", _z_of_Z(Z_of_z(float(r["z0"])) + width)))
    return {"type": "road_band", "x": 0, "z": z1, "z0": z0, "z1": z1, "style": style, "layer": "back"}


def base_image_of(spec):
    for k in ("base_image", "photo", "image", "background_image"):
        v = spec.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _z_of_Z(Z):
    from .world3d import FOCAL
    if Z <= FOCAL / 0.42:
        return max(0.0, (1.0 - FOCAL / Z) * 1000.0 / 0.58)
    return 1000.0 + (Z - FOCAL / 0.42) / 4.0


class PhotoGround:
    """Where the real ground of a 2.5D photo is (from its per-pixel depth): things are stood on it, not on
    walls, trees or water of the picture."""

    def __init__(self, name, world_w):
        import os
        import numpy as np
        from . import photodepth
        from .world3d import FOCAL
        meta = photodepth.status(name) or photodepth.process(name, log=lambda *a: None, preview=False)
        zp = os.path.join(photodepth.folder(name), "zmap.npz")
        z = np.load(zp)["z"].astype(np.float32)
        ih, iw = z.shape
        s = float(meta["scale"]) * (meta["width"] / float(iw))
        yh = float(meta["horizon"]) * ih
        cam_h = float(meta["cam_h"])
        rows = np.arange(ih, dtype=np.float32)[:, None]
        Zg = FOCAL * cam_h / (np.maximum(rows - yh, 0.5) * s)
        ground = (rows > yh + 2) & (np.abs(np.log(np.maximum(z, 1.0) / Zg)) < 0.1)
        # the photo's water (marked by Gemini / you): exact outline from water.png - nothing stands in it
        water = np.zeros_like(ground)
        from scipy import ndimage
        for c in meta.get("cards", []):
            if c.get("kind") != "water":
                continue
            try:
                from PIL import Image
                wm = np.asarray(Image.open(os.path.join(photodepth.folder(name), c["file"])).convert("L"),
                                np.float32) / 255.0
                s0 = float(meta["scale"]) * (meta["width"] / float(iw))
                x0 = int(round((c["u"] - (960.0 - iw * s0 / 2.0)) / s0))
                y0 = int(round((c["v"] - (540.0 - ih * s0 / 2.0)) / s0))
                hh, ww = wm.shape
                ys0, xs0 = max(0, y0), max(0, x0)
                ys1, xs1 = min(ih, y0 + hh), min(iw, x0 + ww)
                if ys1 > ys0 and xs1 > xs0:
                    water[ys0:ys1, xs0:xs1] |= wm[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0] > 0.35
            except Exception:
                pass
        # water nobody marked: clearly blue "ground" is water too (rivers / ponds in the picture)
        try:
            from PIL import Image
            rgb = np.asarray(Image.open(os.path.join(photodepth.folder(name), "photo.jpg")).convert("RGB"),
                             np.float32)[:ih, :iw] / 255.0
            if rgb.shape[:2] == (ih, iw):
                r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
                blue = ground & (b_ > r_ + 0.12) & (b_ > g_ + 0.02)
                blue = ndimage.binary_opening(blue, iterations=2)
                lab, n = ndimage.label(blue)
                if n:
                    area = ndimage.sum(blue, lab, range(1, n + 1))
                    water |= np.isin(lab, np.nonzero(area > iw * ih * 0.004)[0] + 1)
        except Exception:
            pass
        water = ndimage.binary_closing(water, iterations=3)
        self.near_water = ndimage.binary_dilation(water, iterations=max(4, iw // 60)) & ~water if water.any() \
            else np.zeros_like(ground)
        ground &= ~ndimage.binary_dilation(water, iterations=2)
        self.has_water = bool(water.any())
        # only real ground: big connected pieces (not the lower edge of a tree crown read as "ground")
        lab, n = ndimage.label(ground)
        if n:
            area = ndimage.sum(ground, lab, range(1, n + 1))
            ground = np.isin(lab, np.nonzero(area >= iw * ih * 0.008)[0] + 1)
        self.near_water &= ground
        self.ground, self.z, self.s, self.iw, self.ih = ground, z, s, iw, ih
        self.ox, self.oy = 960.0 - iw * s / 2.0, 540.0 - ih * s / 2.0
        self.cx = world_w / 2.0
        self.water = photodepth.zones(meta, world_w)
        step = 3
        ys, xs = np.nonzero(ground[::step, ::step])
        ys, xs = ys * step, xs * step
        Zs = z[ys, xs]
        u = self.ox + (xs + 0.5) * s
        ps = FOCAL / Zs
        X = self.cx + (u - 960.0) / ps
        self.cand = dict(i=xs, j=ys, Z=Zs, z=np.array([_z_of_Z(float(v)) for v in Zs]),
                         x=X * ps + self.cx * (1.0 - ps), uf=u / 1920.0)
        self.meta = meta

    def in_water(self, x, z):
        return any(x0 - 30 <= x <= x1 + 30 and z0 - 60 <= z <= z1 + 60 for x0, x1, z0, z1 in self.water)

    def sample(self, rng, zr, xr, width, near_water=False):
        """A random spot on the photo's ground in this depth / side range where the whole foot of a thing this
        wide stands on ground. -> (x, z) or None"""
        import numpy as np
        from .world3d import FOCAL
        c = self.cand
        if not len(c["z"]):
            return None
        m = (c["z"] >= zr[0]) & (c["z"] <= zr[1])
        if not m.any():                                  # the photo has no ground that deep: nearest there is
            d = np.minimum(np.abs(c["z"] - zr[0]), np.abs(c["z"] - zr[1]))
            m = d <= d.min() + 120
        if xr != "sides":
            mx = m & (c["uf"] >= xr[0]) & (c["uf"] <= xr[1])
        else:
            mx = m & ((c["uf"] < 0.36) | (c["uf"] > 0.64))
        m = mx if mx.any() else m
        if near_water and self.has_water:                  # on the bank: ground right next to the water
            w = self.near_water[c["j"], c["i"]]
            if (m & w).any():
                m = m & w
        idx = np.nonzero(m)[0]
        for _ in range(12):
            k = int(idx[rng.randrange(len(idx))])
            j, i, Z = int(c["j"][k]), int(c["i"][k]), float(c["Z"][k])
            half = max(2, int(width * 0.5 * FOCAL / Z / self.s))
            a, b = max(0, i - half), min(self.iw, i + half + 1)
            foot = self.ground[j, a:b]
            if foot.size and foot.mean() >= 0.65 and (b - a) >= half:
                return float(c["x"][k]), float(c["z"][k])
        return None


def _p(z):
    from .world3d import p3
    return p3(z)


# ============================================================================ build
def is_place_json(spec):
    return isinstance(spec, dict) and isinstance(spec.get("things"), list)


_CACHE = {}


def compile_place(spec, world_w, seed=None):
    """Place JSON -> {"background": <engine background spec>, "objects": [scene objects], "notes": [...],
    "missing": [...]} (cached: the same JSON, width and seed always give the same place)."""
    import json
    ck = (json.dumps(spec, sort_keys=True, default=str), int(world_w), seed)
    if ck in _CACHE:
        return _CACHE[ck]
    from . import images, objects
    W = float(world_w)
    rng = random.Random(int(spec.get("seed", seed if seed is not None else 11)))
    notes, missing = [], []
    bg = {k: v for k, v in spec.items() if k in ("time", "weather", "season", "sky", "clouds", "rainbow", "birds",
                                                 "moon", "stars", "shooting_star", "sun", "mood", "region", "far",
                                                 "density", "foreground", "description", "seed", "skyline")}
    bg["preset"] = str(spec.get("base", "plain"))
    bg["elements_only"] = not spec.get("keep_base")
    bg["_place_json"] = True
    photo = None
    pic = base_image_of(spec)
    if pic:                                              # a 2.5D photo is the place: things stand on its ground
        if not images.exists(pic):
            notes.append(f"base picture '{pic}' not found in your pictures - using a drawn place")
        else:
            try:
                photo = PhotoGround(pic, W)
                bg = {k: v for k, v in bg.items() if k in ("time", "weather", "mood", "description", "seed",
                                                           "_place_json")}
                bg["image"] = pic
                bg["preset"] = "plain"
                bg["camera_note"] = "use settings camera_mode 3d for real depth"
            except Exception as ex:
                notes.append(f"could not read the depth of '{pic}' ({ex}) - using a drawn place")
                photo = None
    if photo is None:
        g = str(spec.get("ground", "grass")).lower().replace(" ", "_")
        bg["ground"] = GROUND_WORDS.get(g, g if g.startswith("#") else "grass")
        bg.setdefault("clouds", "some")
    far = spec.get("far", "hills")
    fars = list(far) if isinstance(far, (list, tuple)) else ([] if str(far).lower() == "none" else [far])
    if "path" in spec and photo is None:
        bg["path"] = bool(spec["path"])
    if photo is None:
        bg["fill"] = bool(spec.get("fill_distance", False))
    if spec.get("clay"):
        bg["clay"] = True                                # a clay world: its ground and plants in clay too
    if spec.get("indoor"):
        bg["indoor"] = True
        if isinstance(spec.get("room"), dict):           # a 3D code room's own size and colours (engine/room3d.py)
            bg["room"] = dict(spec["room"])
    shore = None
    wt = spec.get("water")
    if isinstance(wt, str) and wt.lower() not in ("none", "no", "false", ""):
        wt = {"kind": wt}
    if photo is None and isinstance(wt, dict) and str(wt.get("kind", "river")).lower() not in ("none", "no"):
        kind = str(wt.get("kind", "river")).lower()
        bg["water"] = kind
        side = str(wt.get("side", "right")).lower()
        if side not in ("all", "everywhere", "full"):
            sx = float(wt.get("x", W * (0.62 if side == "right" else 0.38)))
            land = "left" if side == "right" else "right"
            bg["shore"] = {"x": sx, "land": land}
            shore = (sx, land)
    els, objs, placed = [], [], []           # placed: (x, z, halfwidth, name)
    counts = {}
    roads = []                                           # roads first: nothing else stands on them
    for th in spec.get("things") or []:
        th_ = {"what": th} if isinstance(th, str) else th
        if road_word(th_.get("what", "")) and photo is None and not _is_pic(th_.get("what", "")):
            re_ = road_element(th_)
            els.append(re_)
            roads.append((re_["z0"] - 25, re_["z1"] + 25))
            counts[re_["style"] + " road"] = counts.get(re_["style"] + " road", 0) + 1
    hills = []                                           # hills next: things can stand on them
    for th in spec.get("things") or []:
        th_ = {"what": th} if isinstance(th, str) else th
        hi = None if _is_pic(th_.get("what", "")) else hill_info(th_.get("what", ""))
        if not hi or photo is not None:
            continue
        sz = th_.get("size")
        if isinstance(sz, str) and sz.strip():
            hi["sw"] = sizes.word(sz)[0]
        for k_ in range(max(1, min(4, int(th_.get("count", 1) or 1)))):
            H = sizes.real_height("hill_mound", None, hi["sw"]) * (float(sz) if isinstance(sz, (int, float)) else 1.0)
            wdt = H * (2.2 if hi["steep"] else 3.4) + 600
            xr_, zr_, fl_ = _where(th_.get("where", "back"), rng, W, shore)
            if xr_ == "sides":
                xr_ = SIDE["left"] if k_ % 2 == 0 else SIDE["right"]
            zc = rng.uniform(*zr_)
            xc = W * (rng.uniform(*xr_) if not fl_["center"] else rng.uniform(0.45, 0.55))
            pz = _p(zc)
            h = dict(xc=xc, zc=zc, a=wdt / 2.0 * pz, b=260.0, H=H, top=0.2 if not hi["steep"] else 0.08)
            hills.append(h)
            els.append({"type": "hill_mound", "x": round(xc, 1), "z": round(zc, 1), "h": round(H, 1),
                        "w": round(wdt, 1), "style": hi["style"], "trail": hi["trail"],
                        "top": h["top"], "sw": hi["sw"], "_thing": "hill"})
            counts["hill"] = counts.get("hill", 0) + 1
    ps = spec.get("path")
    if isinstance(ps, str) and photo is None and ps.lower() not in ("none", "false", "no"):
        bg["path"] = True
        bg["path_style"] = ROAD_WORDS.get(ps.lower().replace(" ", "_"), ps.lower())
    clay = bool(spec.get("clay"))
    if clay:
        from .worldmap import clay_thing
    for n_th, th in enumerate(spec.get("things") or []):
        if isinstance(th, str):
            th = {"what": th}
        if clay and isinstance(th.get("x"), (int, float)):    # a clay world (Ghatti Nagar): its places in clay too
            cl = clay_thing(th.get("id"))
            if cl and images.exists(cl):
                th = {k: v for k, v in th.items() if k != "height"}
                th["what"] = cl
                lit = _lit_look(cl, spec.get("time"))
                if lit:                                     # after dark: its windows lit, its lamps on
                    th["what"] = lit
        what = th.get("what") or th.get("name") or th.get("type")
        if not _is_pic(what) and (road_word(what or "") or (hill_info(what or "") and photo is None)):
            continue                                        # done above
        info = resolve(what)
        if "missing" in info:
            missing.append({"what": str(what), "name": info.get("name") or str(what), "suggest": info["suggest"],
                            "count": int(th.get("count", 1) or 1), "where": th.get("where", ""),
                            "height": th.get("height")})
            continue
        if info["kind"] in ("far", "sky") and photo is not None:
            counts[info["kind"] + " " + info["type"]] = 1
            continue
        if info["kind"] == "far":                           # a far-view layer (mountains, hills, city ...)
            if info["type"] not in fars:
                fars.append(info["type"])
            counts["far " + info["type"]] = 1
            continue
        if info["kind"] == "sky":                           # the sky: clouds, moon, rainbow, birds ...
            st = info["type"]
            wd = " ".join(_norm(str(th.get("what", ""))) + _norm(str(th.get("where", ""))))
            if st == "clouds":
                c = th.get("count")
                bg["clouds"] = int(c) if isinstance(c, (int, float)) else (
                    th.get("style") or next((k for k in ("puffy", "cirrus", "storm", "overcast") if k in wd), "some"))
            elif st == "moon":
                bg["moon"] = "full" if "full" in wd else ("half" if "half" in wd else bg.get("moon", "crescent"))
            elif st == "sun":
                bg["sun"] = True
            elif st == "milky_way":
                bg["sky"] = "milky_way"
            elif st == "aurora":
                bg["aurora"] = True
            elif st == "kites":
                els.append({"type": "kites", "x": 0, "layer": "sky", "p": 0.05, "seed": rng.random()})
            else:
                bg[st] = True
            counts["sky " + st] = 1
            continue
        n = max(1, min(80, int(th.get("count", 1) or 1)))
        xr, zr, fl = _where(th.get("where"), rng, W, shore)
        # size: a word (tiny / small / medium / big / huge - in the name or in "size") and / or a number
        sw, size = info.get("sw"), 1.0
        sz = th.get("size")
        if isinstance(sz, (int, float)):
            size = float(sz)
        elif isinstance(sz, str) and sz.strip():
            w_, size = sizes.word(sz)
            if w_ != "medium" or sz.lower().strip() in ("medium", "normal", "regular", "average"):
                sw = w_
        sw = sw or "medium"
        typ = info["type"]
        # footprint + height (story units, adult = 300) - real sizes from engine/sizes.py
        if info["kind"] == "image":
            m = images.info(typ) or {}
            h = float(th.get("height") or m.get("height") or 300) * sizes.factor("image", sw) * size
            aspect = (m.get("w") or 1) / float(m.get("h") or 1)
            width = h * aspect
            # a real 3D thing standing on the ground (a fence, a wall, a stall) is SOLID even with no abilities:
            # it is a real object people walk round, not painted scenery they pass through
            has_ab = bool(m.get("abilities")) or bool(m.get("is3d") and m.get("foot") and not m.get("walk")
                                                      and float(m.get("height") or 0) >= 40)
        elif info["kind"] == "object":
            b = objects.BUILTIN[typ]
            f = sizes.factor(typ, sw) * size
            h, width = b["h"] * f, b["w"] * f
            size = f
            has_ab = True
        elif info["kind"] == "tree":
            h = sizes.real_height("tree", info["tree"], sw) * size
            width = WIDTH["tree"] * h / 1200.0
            has_ab = False
        else:
            rh = sizes.real_height(typ, None, sw)
            base = sizes.REAL.get(typ)
            small = typ in ("flower", "grass", "reeds", "mushroom", "diya")
            h = (rh if rh else (40 if small else 300) * sizes.factor(typ, sw)) * size
            width = WIDTH.get(typ, 250) * (h / base if base else h / (40 if small else 300))
            has_ab = False
        is_vehicle_pic = info["kind"] == "image" and (images.info(typ) or {}).get("kind") == "vehicle"
        around = None
        if fl["around"]:
            a_info = resolve(fl["around"])
            a_nm = a_info.get("tree", "") + "_tree" if a_info.get("kind") == "tree" else a_info.get("type", fl["around"])
            around = [p for p in placed if p[3] in (a_nm, fl["around"]) or fl["around"] in p[3]]
            if not around:
                notes.append(f"'{what}': nothing called '{fl['around']}' placed before it - put it after that thing")
        got = 0
        exact = isinstance(th.get("x"), (int, float)) and isinstance(th.get("z"), (int, float))
        if exact:                                            # an exact spot (code-drawn places): x from the middle
            n = 1
        for i in range(n):
            ok = False
            for attempt in range(60):
                if exact:
                    x, z = W / 2 + float(th["x"]), max(0.0, float(th["z"]))
                    ok = True
                    break
                if fl.get("on_hill") and hills:                # on top of a hill (flat top, a little down the slope)
                    hh = hills[(got + attempt) % len(hills)]
                    x = hh["xc"] + rng.uniform(-0.32, 0.32) * hh["a"]
                    z = max(0.0, hh["zc"] - 8.0)
                elif around:
                    a = rng.choice(around)
                    ang = rng.uniform(0, math.tau)
                    x = a[0] + math.cos(ang) * (a[2] + width / 2 + rng.uniform(30, 160)) / max(_p(a[1]), 0.2)
                    z = max(0.0, a[1] + math.sin(ang) * rng.uniform(60, 220))
                elif photo is not None:                       # on the photo's real ground
                    got_ = photo.sample(rng, (zr[0], zr[1] * (1.0 if attempt < 40 else 1.7)), xr, width,
                                        near_water=fl["water"])
                    if got_ is None:
                        continue
                    x, z = got_
                else:
                    z = rng.uniform(zr[0], zr[1] * (1.0 if attempt < 40 else 1.7))   # crowded: a bit further back
                    if xr == "sides":
                        lo, hi = SIDE["left"] if rng.random() < 0.5 else SIDE["right"]
                    else:
                        lo, hi = xr
                    x = W * rng.uniform(lo, hi)
                    if z > 1000:                              # the distance is wider than the stage
                        x = W / 2 + (x - W / 2) * (1.0 + (z - 1000) / 900.0)
                if z <= 1000 and photo is None:               # on the stage: stay inside the world
                    x = min(max(x, 60.0 + width * 0.3), W - 60.0 - width * 0.3)
                p = _p(z)
                if any(a_ <= z <= b_ for a_, b_ in roads) and not (info["kind"] == "image" and is_vehicle_pic) \
                        and not fl.get("on_hill"):
                    continue                                  # nothing stands on the road
                # the stage stays free: big things never stand in the middle in front
                if h > BIG and z < 700 and 0.3 * W < x < 0.7 * W and not fl["center"] and not fl.get("on_hill"):
                    continue
                # land things stay on land, water things by the water
                if shore and typ not in ("reeds", "bridge"):
                    sx, land = shore
                    if (land == "left" and x + width * 0.3 > sx) or (land == "right" and x - width * 0.3 < sx):
                        continue
                # no overlapping (distance measured on screen: far things are closer together in story x)
                bad = False
                gap = 0.8 if attempt < 25 else (0.55 if attempt < 45 else 0.35)   # squeeze in if it is crowded
                for (px, pz, pw, _nm) in placed:
                    pp = _p(pz)
                    if abs(z - pz) < max(60.0, 0.08 * (z + pz), (width * 0.5 + pw) * 0.55) and \
                            abs(x * p - px * pp) < (width * 0.5 + pw) * gap * min(p, pp) + 15:
                        bad = True
                        break
                if bad:
                    continue
                ok = True
                break
            if not ok:
                continue
            got += 1
            nm = typ if info["kind"] != "tree" else (info["tree"] if info["tree"].endswith("_tree")
                                                     else info["tree"] + "_tree")
            counts[nm] = counts.get(nm, 0) + 1
            placed.append((x, z, width * 0.5, nm))
            flip = rng.random() < 0.5 and not exact              # code-drawn places are built as drawn
            is_vehicle = info["kind"] == "image" and (images.info(typ) or {}).get("kind") == "vehicle"
            real = z <= 1000 and (info["kind"] == "object" or (info["kind"] == "image" and (has_ab or is_vehicle)))
            if real:                                         # a real object: walk around, sit, hide behind
                objs.append({"id": str(th["id"]) if exact and th.get("id") else f"{nm}_{counts[nm]}", "type": typ, "x": round(x, 1), "z": round(z, 1),
                             "scale": round(size, 3), "flip": flip, "_place": True,
                             **({"vehicle": True, "facing": "left" if flip else "right"} if is_vehicle else {}),
                             **({"height": round(h, 1)} if info["kind"] == "image" else {}),
                             **({"y": float(th["y"])} if exact and th.get("y") else {})})   # raised: a balcony
                continue
            el = {"type": typ if info["kind"] != "image" else "image", "x": round(x, 1), "z": round(z, 1),
                  "flip": flip, "_thing": nm}
            ty = max([_hill_h(hh, x, z) for hh in hills] or [0.0])
            if ty > 1.0:
                el["ty"] = round(ty, 1)
            if exact:
                el["exact"] = True                            # a code-drawn place: exactly where it was built
                if th.get("y"):
                    el["y"] = float(th["y"])                  # a raised part of a code place (a balcony, a flag)
            el["sw"] = sw
            if info["kind"] == "tree":
                el["kind"] = info["tree"]
                el["size"] = round(size * rng.uniform(0.88, 1.12), 3)
            elif info["kind"] == "image":
                el["name"] = typ
                el["height"] = round(h * rng.uniform(0.92, 1.08), 1)
            else:
                el["size"] = round(size * rng.uniform(0.94, 1.06), 3)
                if th.get("color"):
                    el["color"] = th["color"]
            els.append(el)
        if got < n:
            notes.append(f"'{what}': placed {got} of {n} - not enough room {th.get('where') or ''}".strip())
    if photo is None:
        bg["far"] = fars or "none"
    elif any(k.startswith(("sky ", "far ")) for k in counts):
        notes.append("sky and far-view things are skipped on a photo (the photo has its own sky)")
    bg["elements"] = els
    out = {"background": bg, "objects": objs, "notes": notes, "missing": missing,
           "summary": {k: v for k, v in sorted(counts.items())}}
    _CACHE[ck] = out
    return out


def check(spec, world_w=2400):
    """What is found / missing, without building pictures."""
    found, missing = [], []
    for th in spec.get("things") or []:
        if isinstance(th, str):
            th = {"what": th}
        what = th.get("what") or th.get("name") or th.get("type")
        if road_word(what or ""):
            found.append({"what": str(what), "as": "road", "type": road_word(what)})
            continue
        info = resolve(what)
        if "missing" in info:
            missing.append({"what": str(what), "name": info.get("name") or str(what), "suggest": info["suggest"],
                            "count": int(th.get("count", 1) or 1), "height": th.get("height")})
        else:
            found.append({"what": str(what), "as": info["kind"],
                          "type": info.get("tree", info["type"]) if info["kind"] == "tree" else info["type"]})
    return {"found": found, "missing": missing}


def validate(spec):
    """Problems with the JSON itself (not missing pictures)."""
    probs = []
    if not isinstance(spec, dict):
        return ["the place must be a JSON object { ... }"]
    if not isinstance(spec.get("things"), list) or (not spec["things"] and not base_image_of(spec)):
        probs.append('add "things": [ {"what": "neem tree", "count": 5, "where": "back"}, ... ]')
    if not str(spec.get("place") or spec.get("name") or "").strip():
        probs.append('add "place": "a_name" (used in stories as "background": {"preset": "a_name"})')
    return probs


# ============================================================================ the prompt (Gemini or any AI)
TREE_HINTS = {"round": "ordinary leafy tree", "pine": "pine / conifer", "palm": "palm", "banyan": "huge banyan with roots",
              "mango": "mango tree", "coconut": "coconut palm", "banana_tree": "banana plant", "acacia": "flat-top dry tree",
              "cactus_tree": "big cactus", "bare": "leafless", "blossom": "pink cherry blossom",
              "mushroom_tree": "fantasy mushroom", "neem": "neem", "peepal": "big peepal", "gulmohar": "red flowers",
              "jacaranda": "purple flowers", "amaltas": "yellow hanging flowers", "bamboo": "bamboo clump",
              "willow": "weeping willow", "birch": "white birch", "autumn": "orange autumn leaves",
              "cypress": "tall thin cypress", "fir": "layered fir (snowy in cold places)", "ashoka": "tall narrow ashoka",
              "eucalyptus": "tall eucalyptus", "oak": "big oak", "apple": "apple tree with fruit",
              "dead": "twisted spooky dead tree", "baobab": "fat baobab"}


def full_prompt(sentence=""):
    """Everything the engine can build a place with - made fresh every time, so new pictures, object sheets and
    saved places are always in it. Works for Gemini inside the app and for any other AI (ChatGPT, Claude ...)."""
    from . import catalog, images, objects, registry
    o = catalog.options()
    pics = images.list_images()
    mine = []
    for n, m in sorted(pics.items()):
        m = m or {}
        if m.get("state_of") or m.get("part_of") or (m.get("kind") in ("background", "picture", "state")) or \
                (m.get("ground") and not m.get("has_alpha")):
            continue
        d = str(m.get("description") or "").split(" - ")[0][:70]
        mine.append(f"  - {n}" + (" [REAL 3D]" if m.get("is3d") else "") + (f": {d}" if d else "") +
                    (f" (height {int(m['height'])})" if m.get("height") else ""))
    places = sorted(registry.load()["places"])
    photos = photo_bases()
    obj_list = ", ".join(sorted(objects.BUILTIN))
    scenery = sorted(set(SCENERY))
    trees = "\n".join(f"  - {k}_tree: {v}" if not k.endswith("_tree") else f"  - {k}: {v}" for k, v in TREE_HINTS.items())
    ex1 = {"place": "river_village_evening", "description": "small Indian village next to a river in the evening",
           "ground": "mud", "time": "evening", "sky": "golden", "clouds": "puffy", "far": ["mountains", "hills"],
           "water": {"kind": "river", "side": "right"}, "path": True,
           "things": [{"what": "neem tree", "count": 5, "where": "back"},
                      {"what": "hut", "count": 3, "where": "left back"},
                      {"what": "well", "where": "left middle"},
                      {"what": "clay pot", "count": 2, "where": "around well"},
                      {"what": "rock", "count": 2, "where": "near right"},
                      {"what": "stone", "count": 5, "where": "near water"},
                      {"what": "gulmohar tree", "count": 16, "where": "far"},
                      {"what": "flowers", "count": 10, "where": "near"},
                      {"what": "birds"}]}
    ex2 = {"place": "haunted_graveyard", "description": "spooky graveyard on a foggy full-moon night",
           "ground": "dry_grass", "time": "night", "weather": "fog", "clouds": "few", "far": ["dry_hills"],
           "things": [{"what": "dead tree", "count": 6, "where": "back"},
                      {"what": "tombstone", "count": 8, "where": "middle sides"},
                      {"what": "fence", "count": 2, "where": "back"},
                      {"what": "bare tree", "count": 14, "where": "far"},
                      {"what": "full moon"}, {"what": "shooting star"}]}
    import json as _j
    return f"""# Place JSON for Stickman Studio (a cartoon engine: 2D and real 3D)

You design a PLACE (a background world) for a cartoon animation (it is used both in 2D and with the 3D camera). Answer with ONE JSON object only - no
comments, no explanation, no markdown fences. The engine arranges everything by itself: real sizes (a person is
300 tall, a hut about 1.2x a person, a house 2x, trees 2-3x), real depth, nothing overlapping, the middle of the
stage kept free for the characters, things kept on land. So NEVER give x/y positions or sizes of people and
buildings - only WHAT is there and roughly WHERE.

## Format
{{
  "place": "<short_snake_case_name>",
  "description": "<one line: what the place is - the story writer reads this>",
  "base_image": "<optional: one of the user's background PHOTOS below - then the photo IS the place, things
                  stand on its real ground, and ground / sky / far / water come from the photo>",
  "ground": "{" | ".join(sorted(set(GROUND_WORDS)))}",
  "time": "{" | ".join(o["times"])}",
  "weather": "{" | ".join(o["weather"])}",
  "season": "{" | ".join(o["seasons"])}",
  "sky": "{" | ".join(o["skies"])}",
  "clouds": "{" | ".join(o["clouds"])}",
  "far": [ one or more of: {", ".join(FAR_LIST)} ]   (the view behind everything; "none" for no far view)
  "water": {{"kind": "none | river | lake | pond | sea", "side": "left | right | all"}},
  "path": true | "road" | "dirt" | "footpath",   (a path / road running into the distance, 3D mode)
  "rainbow": false, "birds": false, "moon": "full | half | crescent", "shooting_star": false, "stars": false,
  "seed": 7,               (optional: another number = another arrangement of the same list)
  "things": [ {{"what": "<thing>", "count": 1, "where": "<words>"}} ]
}}
Optional per thing: "size": "tiny | small | medium | big | huge" (no size = medium = the real normal size),
"height": 450 (only for YOUR pictures). Size words can also be in the name: "big hut", "huge banyan tree".
NEVER give sizes as numbers for built-in things - the engine knows them. What the words mean (x a person):
  hut 1.3 / 1.8 / 2.3 / 2.8 / 3.3      house 2 / 2.5 / 3 (1 floor) / 4 (2 floors) / 5.5 (haveli)
  tree 1 (sapling) / 2.5 / 4 / 5.5 / 7 (old banyan)      temple 1 (roadside shrine) / 3 / 6 / 9 / 12
  rock: pebble / knee / waist (sit on it) / chest (hide behind) / boulder (climb)      pot, box: cup .. chest

## "where" words (combine them)
depth: near, middle, back, far, horizon
side:  left, right, center, sides, everywhere
also:  "near water", "along path", "around <an earlier thing>" (e.g. "around well"), "middle sides", "left back"

## Things you can use
### Trees ("what": "<kind> tree")
{trees}
### Scenery
  {", ".join(scenery)}
### Objects (people can sit on / hide behind / push them when they are near or middle)
  {obj_list}
### Hills people can climb (land you walk up; "hills" = only the far view)
  {{"what": "hill" | "big hill" | "small rocky hill" | "hill with path" | "steep hill" | "snowy hill", "where": "back center"}}
  sizes: tiny (a mound) .. huge (11x a person); words: rocky, dry, snowy, sandy, forest, steep, "with path"
  things ON it: {{"what": "temple", "where": "on hill"}} {{"what": "tree", "count": 2, "where": "on hill"}}
  (in the story: {{"who": "ravi", "do": "walk", "to": {{"x": <hill x>, "z": <hill z>}}}} climbs it; the camera rises too)
### Roads across the place (flat on the ground, real width; nothing else is put on them)
  {{"what": "road" | "highway" | "dirt road" | "village road" | "stone road" | "footpath", "where": "near | middle | back"}}
  (a "near" road = the characters stand on it; vehicles can drive along it)
### Sky and far view (can also be written as things: {{"what": "rainbow"}}, {{"what": "mountains"}})
  sky:  {", ".join(sorted(set(SKY_THINGS)))}
  far:  {", ".join(sorted(set(FAR_THINGS)))}
### The user's background photos (for "base_image")
{chr(10).join("  - " + n + (": " + d if d else "") for n, d in photos) if photos else "  (none yet)"}
### The user's own pictures and 3D things (use the exact name; [REAL 3D] = real 3D shape - seen from every side
### with the 3D camera, so prefer them for places used in 3D videos)
{chr(10).join(mine) if mine else "  (none yet)"}
{("### Places the user already saved (for ideas; do not repeat them)" + chr(10) + "  " + ", ".join(places)) if places else ""}

## Good places
- 6-16 things. Big things (trees, huts, houses, temples) at back / sides / far; the middle near the camera stays
  open for the characters; a few small things near (stones, pots, flowers, grass) for depth; 10-25 far trees or
  a far view for a deep world; match the ground, sky and far view to the place.
- If the place truly needs something that is not in these lists (a bullock cart, a tractor, a tulsi plant, a
  swing bed ...), use it with a clear snake_case name - the app will draw it as a new picture.

## Example 1
{_j.dumps(ex1, indent=1)}

## Example 2
{_j.dumps(ex2, indent=1)}

## The place to make
{sentence.strip() if str(sentence or "").strip() else "<describe your place here, e.g. a busy village market at noon with a big banyan tree>"}
"""


def photo_bases():
    """[(name, description)] of the user's background pictures (usable as "base_image")."""
    from . import images
    out = []
    for n, m in sorted(images.list_images().items()):
        m = m or {}
        if m.get("kind") == "background" or (m.get("ground") and not m.get("has_alpha")):
            out.append((n, str(m.get("description") or "").split(" - ")[0][:70]))
    return out


def gemini_prompt(sentence):
    return full_prompt(sentence)


PLACE_PROMPT_FILE = None


def write_prompt_file():
    """prompts/place_to_json_prompt.md - refreshed whenever a picture, sheet or place is saved."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "prompts", "place_to_json_prompt.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(full_prompt(""))
    return path


def missing_sheet(missing, place_name=""):
    """An object sheet (engine/objsheet.py) for the missing things: Gemini draws them all on one picture."""
    from . import objsheet
    items, used = [], set()
    for m in missing[:12]:
        what = str(m.get("what")).replace("_", " ")
        it = objsheet.item(what, name=m.get("name") or what, height=m.get("height"), states=[])
        while it["name"] in used:
            it["name"] += "_2"
        used.add(it["name"])
        items.append(it)
    return objsheet.new(items, (place_name or "place") + " things", "cartoon", True)
