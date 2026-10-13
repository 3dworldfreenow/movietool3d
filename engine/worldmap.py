"""Big 3D worlds (worlds/<name>.json): villages, rivers, roads, fields and jungles on a map in METRES (5 km+).

One world is reused by many stories:  "settings": {"world": "sonpur_valley"},  each scene  "at": "ghat".

    {
      "world": "sonpur_valley", "title": "Sonpur valley", "size": [5000, 5000],
      "ground": "grass", "time": "morning", "far": ["hills"],
      "places":  [ {"id": "ghat", "place": "river_3d", "at": [2310, 2050], "turn": 90} ],
      "roads":   [ {"id": "main_road", "points": [[1200, 1800], [2300, 2100]], "width": 6, "style": "dirt"} ],
      "rivers":  [ {"id": "son", "points": [[2000, 0], [2350, 2000], [2600, 5000]], "width": 40} ],
      "areas":   [ {"id": "north_jungle", "kind": "jungle", "shape": [[x, z], ...]},
                   {"id": "hill_1", "kind": "hills", "at": [4400, 900], "radius": 450, "height": 120} ],
      "objects": [ {"id": "big_banyan", "type": "banyan_3d", "at": [1230, 1860], "turn": 30} ],
      "edits":   { "north_jungle.61.72.3": {"type": "pine_3d"} },     (changes to auto-filled things)
      "removed": [ "north_jungle.61.72.4" ]
    }

x = east, z = north (metres). "turn" in degrees. Areas are filled by themselves (seeded: always the same trees)
in 50 m cells, so a 5 km world costs nothing until someone looks at a part of it.
"""
import json
import math
import os
import random

from .util import stable_hash

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "worlds")
UNITS = 175.0                       # story / 3D-code units per metre (an adult = 300 units = 1.7 m)
CELL = 50.0                         # metres: areas are filled cell by cell

# what grows / stands in each kind of area: (type, share), things per hectare, what the ground looks like
AREA_KINDS = {
    "jungle":  dict(things=[("tree_round_3d", 0.3), ("banyan_3d", 0.14), ("palm_3d", 0.14), ("bush_3d", 0.3),
                            ("rock_3d", 0.12)], per_ha=70, ground="#4f8f3a", abilities=True),
    "forest":  dict(things=[("pine_3d", 0.5), ("tree_round_3d", 0.3), ("bush_3d", 0.1), ("rock_3d", 0.1)],
                    per_ha=55, ground="#5d9640"),
    "grove":   dict(things=[("palm_3d", 0.8), ("bush_3d", 0.2)], per_ha=35, ground="#7fb04c"),
    "fields":  dict(things=[("crops_3d", 1.0)], per_ha=150, ground="#8cc063", near=True),
    "village": dict(things=[("house_3d", 0.18), ("hut_3d", 0.24), ("haystack_3d", 0.1), ("tree_round_3d", 0.14),
                            ("bush_3d", 0.1), ("well_3d", 0.05), ("cot_3d", 0.06), ("handpump_3d", 0.05),
                            ("stall_3d", 0.04), ("banyan_3d", 0.04)], per_ha=22, ground="#b98e5e", spacing=9.0),
    "town":    dict(things=[("building_3d", 0.35), ("shop_3d", 0.3), ("stall_3d", 0.15), ("lamp_3d", 0.12),
                            ("tree_round_3d", 0.08)], per_ha=30, ground="#9a958c", spacing=9.0),
    "desert":  dict(things=[("cactus_3d", 0.55), ("rock_3d", 0.45)], per_ha=10, ground="#e2c48f"),
    "rocks":   dict(things=[("rock_3d", 1.0)], per_ha=25, ground="#9aa08a"),
    "park":    dict(things=[("tree_round_3d", 0.4), ("bench_3d", 0.2), ("bush_3d", 0.25), ("lamp_3d", 0.15)],
                    per_ha=30, ground="#7cc15a"),
    "hills":   dict(things=[("pine_3d", 0.5), ("rock_3d", 0.3), ("bush_3d", 0.2)], per_ha=12, ground="#6f9a4a"),
    "lake":    dict(things=[], per_ha=0, ground="#3f8fc6", water=True),
    "pond":    dict(things=[], per_ha=0, ground="#3f8fc6", water=True),
    "sand":    dict(things=[], per_ha=0, ground="#e2c48f"),
    "open":    dict(things=[], per_ha=0, ground=None),
}
AREA_ALIASES = {"jungles": "jungle", "woods": "forest", "trees": "forest", "field": "fields", "farm": "fields",
                "farms": "fields", "crops": "fields", "mustard": "fields", "palms": "grove", "coconut": "grove",
                "houses": "village", "city": "town", "market": "town", "hill": "hills", "mountain": "hills",
                "mountains": "hills", "water": "lake", "rocky": "rocks", "garden": "park", "beach": "sand"}
# how far away things are worth drawing (metres): small things only near the camera
VIEW = {"crops_3d": 160.0, "bush_3d": 350.0, "rock_3d": 350.0, "cot_3d": 200.0, "bench_3d": 200.0,
        "handpump_3d": 200.0, "lamp_3d": 350.0, "stall_3d": 450.0, "well_3d": 450.0}
VIEW_DEFAULT = 1200.0
# 🗿 a world with "look": "clay" (Ghatti Nagar) is made of the sculpted clay village (assets/code/clay_village_3d.py,
# engine/sculpt_village.py) instead of the older flat-shaded things, and its homes open into the sculpted home
CLAY = {"khaprail_house_3d": "clay_khaprail_house_3d", "hut_3d": "clay_hut_3d", "house_3d": "clay_pucca_house_3d",
        "building_3d": "clay_building_3d", "shop_3d": "clay_shop_3d", "banyan_3d": "clay_banyan_3d",
        "mahua_tree_3d": "clay_mahua_3d", "mango_tree_3d": "clay_mango_3d", "neem_tree_3d": "clay_neem_3d",
        "bush_3d": "clay_bush_3d", "well_3d": "clay_well_3d", "haystack_3d": "clay_haystack_3d",
        "handpump_3d": "clay_handpump_3d", "cot_3d": "charpai", "sal_tree_3d": "clay_sal_3d",
        "teak_tree_3d": "clay_teak_3d", "bamboo_clump_3d": "clay_bamboo_3d", "rock_3d": "clay_rock_3d",
        "tree_round_3d": "clay_tree_3d", "cart_3d": "clay_cart_3d", "fence_3d": "clay_fence_3d",
        "gothan_3d": "clay_gothan_3d", "temple_3d": "clay_temple_3d", "stall_3d": "clay_stall_3d",
        "lamp_3d": "clay_lamp_3d", "bench_3d": "clay_bench_3d", "swing_3d": "clay_swing_3d"}
CLAY_PLACES = {"ghar_andar_3d": "ghatti_ghar_3d"}
VIEW.update({"clay_bush_3d": 350.0, "charpai": 200.0, "clay_handpump_3d": 200.0, "clay_well_3d": 450.0,
             "clay_rock_3d": 350.0})


def clay_thing(name):
    """a thing of a code place (village_3d's "house", "banyan", "tree_back" ...) -> its clay version, or None"""
    import re
    n = re.sub(r"_?\d+$", "", str(name or "").lower())
    if "banyan" in n:
        return "clay_banyan_3d"
    if "neem" in n:
        return "clay_neem_3d"
    if "mango" in n:
        return "clay_mango_3d"
    if "mahua" in n:
        return "clay_mahua_3d"
    if n == "tree" or n.startswith("tree_") or n.endswith("_tree"):
        return ("clay_mango_3d", "clay_mahua_3d", "clay_neem_3d")[sum(map(ord, n)) % 3]
    if n.startswith("fence"):
        return "clay_fence_3d"
    if n.startswith("haystack"):
        return "clay_haystack_3d"
    if n.startswith("bush"):
        return "clay_bush_3d"
    if n in ("cot", "charpai", "khat"):
        return "charpai"
    if n == "hut" or n.endswith("_hut"):
        return "clay_hut_3d"
    if n == "house" or n.endswith("_house"):
        return "clay_khaprail_house_3d"
    if n in ("well", "kuan") or n.endswith("_well"):
        return "clay_well_3d"
    if n.startswith("handpump"):
        return "clay_handpump_3d"
    if n == "tea_shop":
        return "clay_tea_shop_3d"
    if n.startswith("shop") or n == "dukaan":
        return "clay_shop_3d"
    one = {"haveli": "clay_haveli_3d", "balcony": "clay_balcony_3d", "balcony_railing": "clay_railing_3d",
           "stairs": "clay_stairs_3d", "stairs_wall": "clay_stairs_wall_3d", "tulsi": "clay_tulsi_3d",
           "temple": "clay_temple_3d", "school": "clay_school_3d", "swing": "clay_swing_3d", "goal": "clay_goal_3d",
           "stove": "clay_stove_3d", "shrine": "clay_shrine_3d", "reeds": "clay_reeds_3d", "rocks": "clay_rock_3d",
           "ghat_bank": "clay_ghat_3d", "front_steps": "clay_front_steps_3d", "river_steps": "clay_side_steps_3d",
           "jetty": "clay_jetty_3d"}
    if n in one:
        return one[n]
    if n.startswith("stall"):
        return "clay_stall_3d"
    if n.startswith("lamp"):
        return "clay_lamp_3d"
    if n.startswith("bench"):
        return "clay_bench_3d"
    if n.startswith("building"):
        return "clay_building_3d"
    return None


def clay_look(spec):
    """the world spec with its things swapped for the clay ones (only the ones that are built)"""
    from . import images
    swap = {a: b for a, b in CLAY.items() if images.exists(b)}

    def t(x):
        return swap.get(x, x)
    spec = dict(spec)
    spec["objects"] = [dict(o, type=t(o["type"])) if isinstance(o, dict) and o.get("type") else o
                       for o in spec.get("objects") or []]
    areas = []
    for a in spec.get("areas") or []:
        if isinstance(a, dict):
            a = dict(a)
            if a.get("things"):
                a["things"] = [[t(x[0])] + list(x[1:]) for x in a["things"]]
            if a.get("rows"):
                a["rows"] = [t(x) for x in a["rows"]]
        areas.append(a)
    spec["areas"] = areas
    spec["places"] = [dict(p, type=t(p["type"]) if p.get("type") else p.get("type"),
                           place=CLAY_PLACES.get(p.get("place"), p.get("place")))
                      if isinstance(p, dict) else p for p in spec.get("places") or []]
    for p in spec["places"]:
        if isinstance(p, dict) and p.get("type") is None:
            p.pop("type", None)
        if isinstance(p, dict) and p.get("place") is None:
            p.pop("place", None)
    return spec
ROAD_STYLES = ("dirt", "tar", "stone", "footpath", "sand")
PLACE_CLEAR = 28.0                  # metres kept free round a place (its stage + where the camera stands)


# ============================================================================ files
def path_of(name):
    return os.path.join(DIR, _clean(name) + ".json")


def _clean(name):
    s = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(name or "").strip().lower())
    return s.strip("_")[:60]


def list_worlds():
    if not os.path.isdir(DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(DIR) if f.endswith(".json"))


_CACHE = {}


def load(name):
    """-> World (cached until the file changes) or None."""
    p = path_of(name)
    if not os.path.exists(p):
        return None
    mt = os.path.getmtime(p)
    got = _CACHE.get(p)
    if got and got[0] == mt:
        return got[1]
    with open(p, encoding="utf-8") as fh:
        spec = json.load(fh)
    w = World(spec, _clean(name))
    _CACHE[p] = (mt, w)
    return w


def save(name, spec):
    os.makedirs(DIR, exist_ok=True)
    spec = dict(spec)
    spec["world"] = _clean(name)
    with open(path_of(name), "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=1, ensure_ascii=False)
    _CACHE.pop(path_of(name), None)
    return path_of(name)


# ============================================================================ geometry helpers
def _pt(p):
    return (float(p[0]), float(p[1]))


def seg_dist(p, a, b):
    ax, az, bx, bz = a[0], a[1], b[0], b[1]
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    u = 0.0 if L <= 1e-9 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - az) * dz) / L))
    return math.hypot(p[0] - (ax + u * dx), p[1] - (az + u * dz))


def line_dist(p, pts):
    if len(pts) == 1:
        return math.hypot(p[0] - pts[0][0], p[1] - pts[0][1])
    return min(seg_dist(p, a, b) for a, b in zip(pts, pts[1:]))


def in_poly(p, poly):
    x, z = p
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / ((zj - zi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


def smooth_line(pts, steps=6):
    """Centripetal Catmull-Rom through the points (roads and rivers bend smoothly). Centripetal (the knots spaced by
    the square root of the distances): a short piece next to a long one does not overshoot and loop back on itself."""
    pts = [_pt(p) for p in pts]
    if len(pts) < 3:
        return pts
    out = []
    P = [pts[0]] + pts + [pts[-1]]

    def knot(t, a, b):
        return t + max(1e-6, math.hypot(b[0] - a[0], b[1] - a[1]) ** 0.5)

    def lerp(a, b, ta, tb, t):
        if tb - ta < 1e-9:
            return a
        return tuple(a[j] + (b[j] - a[j]) * (t - ta) / (tb - ta) for j in range(2))
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        if p0 == p1:                                   # the ends: extend the line straight on
            p0 = (2 * p1[0] - p2[0], 2 * p1[1] - p2[1])
        if p3 == p2:
            p3 = (2 * p2[0] - p1[0], 2 * p2[1] - p1[1])
        t0 = 0.0
        t1 = knot(t0, p0, p1)
        t2 = knot(t1, p1, p2)
        t3 = knot(t2, p2, p3)
        for k in range(steps):
            t = t1 + (t2 - t1) * k / steps
            a1, a2, a3 = lerp(p0, p1, t0, t1, t), lerp(p1, p2, t1, t2, t), lerp(p2, p3, t2, t3, t)
            b1, b2 = lerp(a1, a2, t0, t2, t), lerp(a2, a3, t1, t3, t)
            out.append(lerp(b1, b2, t1, t2, t))
    out.append(pts[-1])
    return out


_RADIUS = {}


def _radius_of(typ):
    """Footprint radius (metres) of a library thing (from its saved picture box)."""
    if typ in _RADIUS:
        return _RADIUS[typ]
    _RADIUS[typ] = _radius_calc(typ)
    return _RADIUS[typ]


def _radius_calc(typ):
    from . import images
    m = images.info(typ) or {}
    box = m.get("box") or m.get("foot")
    if box and len(box) >= 2:
        return max(0.4, abs(float(box[1]) - float(box[0])) / UNITS / 2.0)
    return 1.0


# ============================================================================ the world
class World:
    def __init__(self, spec, name):
        self.clay = {}
        if str(spec.get("look", "")).lower() == "clay":
            spec = clay_look(spec)
            from . import images
            self.clay = {a: b for a, b in CLAY.items() if images.exists(b)}
        self.spec = spec
        self.name = name
        self.title = spec.get("title") or name.replace("_", " ").title()
        sz = spec.get("size") or [5000, 5000]
        self.size = (float(sz[0]), float(sz[1] if len(sz) > 1 else sz[0]))
        self.notes = []
        self.places = []
        for i, p in enumerate(spec.get("places") or []):
            if not isinstance(p, dict) or "at" not in p:
                continue
            self.places.append(dict(p, id=_clean(p.get("id") or f"place_{i + 1}"), at=_pt(p["at"]),
                                    turn=float(p.get("turn", 0.0) or 0.0)))
        self.byid = {p["id"]: p for p in self.places}
        self.roads = self._lines(spec.get("roads"), "road", 6.0)
        self.rivers = self._lines(spec.get("rivers"), "river", 40.0)
        self.areas = []
        for i, a in enumerate(spec.get("areas") or []):
            if not isinstance(a, dict):
                continue
            kind = AREA_ALIASES.get(str(a.get("kind", "open")).lower(), str(a.get("kind", "open")).lower())
            if kind not in AREA_KINDS:
                self.notes.append(f"area '{a.get('id', i + 1)}': unknown kind '{kind}' - using 'open'")
                kind = "open"
            area = dict(a, id=_clean(a.get("id") or f"area_{i + 1}"), kind=kind)
            if a.get("shape"):
                area["shape"] = [_pt(q) for q in a["shape"]]
            elif a.get("at"):
                c, r = _pt(a["at"]), float(a.get("radius", 150))
                area["shape"] = [(c[0] + r * math.cos(2 * math.pi * k / 24), c[1] + r * math.sin(2 * math.pi * k / 24))
                                 for k in range(24)]
            else:
                continue
            xs, zs = [q[0] for q in area["shape"]], [q[1] for q in area["shape"]]
            area["bbox"] = (min(xs), min(zs), max(xs), max(zs))
            self.areas.append(area)
        self.objects = []
        for i, o in enumerate(spec.get("objects") or []):
            if isinstance(o, dict) and o.get("type") and o.get("at") is not None:
                self.objects.append(dict(o, id=_clean(o.get("id") or f"{o['type']}_{i + 1}"), at=_pt(o["at"])))
        self.edits = dict(spec.get("edits") or {})
        self.removed = set(spec.get("removed") or [])
        for a in self.areas:                                  # named things everyone can use
            self.byid.setdefault(a["id"], dict(a, at=self._centre(a["shape"])))
        for o in self.objects:
            self.byid.setdefault(o["id"], o)
        for r in self.roads + self.rivers:
            self.byid.setdefault(r["id"], dict(r, at=r["line"][len(r["line"]) // 2]))
        self._segs = {}                                   # 100 m grid -> the road / river pieces near it
        for r in self.roads + self.rivers:
            pad = r["width"] / 2 + (3.0 if r["kind"] == "river" else 1.5) + 12.0
            for a, b in zip(r["line"], r["line"][1:]):
                for gi in range(int((min(a[0], b[0]) - pad) // 100), int((max(a[0], b[0]) + pad) // 100) + 1):
                    for gj in range(int((min(a[1], b[1]) - pad) // 100), int((max(a[1], b[1]) + pad) // 100) + 1):
                        self._segs.setdefault((gi, gj), []).append((a, b, r))
        self._cells = {}

    def _lines(self, items, kind, width):
        out = []
        for i, r in enumerate(items or []):
            if not isinstance(r, dict):
                continue
            pts = [_pt(q) for q in (r.get("points") or [])]
            if not pts and (r.get("from") or r.get("to")):     # a road between two named places
                ends = [self._where(r.get("from")), self._where(r.get("to"))]
                if None in ends:
                    self.notes.append(f"{kind} '{r.get('id', i + 1)}': unknown place in from / to")
                    continue
                pts = [ends[0]] + [_pt(q) for q in (r.get("via") or [])] + [ends[1]]
            if len(pts) < 2:
                continue
            out.append(dict(r, id=_clean(r.get("id") or f"{kind}_{i + 1}"), points=pts, line=smooth_line(pts),
                            width=float(r.get("width", width)), kind=kind))
        return out

    def _where(self, name):
        if name is None:
            return None
        if isinstance(name, (list, tuple)):
            return _pt(name)
        p = self.byid.get(_clean(name)) if hasattr(self, "byid") else None
        if p is None:
            for q in self.places:
                if q["id"] == _clean(name):
                    return q["at"]
            return None
        return p["at"]

    @staticmethod
    def _centre(poly):
        return (sum(q[0] for q in poly) / len(poly), sum(q[1] for q in poly) / len(poly))

    def where(self, name):
        """A place / area / object / road by name -> (x, z) metres, or None."""
        return self._where(name)

    # ---------------------------------------------------------------- what is free ground
    def blocked(self, p, r=1.0, skip_place=None):
        """Why nothing can stand here (river / road / lake / place) or None."""
        for a, b, ln in self._segs.get((int(p[0] // 100), int(p[1] // 100)), ()):
            if seg_dist(p, a, b) < ln["width"] / 2 + (3.0 if ln["kind"] == "river" else 1.5) + r:
                return ln["kind"]
        for a in self.areas:
            if AREA_KINDS[a["kind"]].get("water") and in_poly(p, a["shape"]):
                return "water"
        for pl in self.places:
            if pl["id"] != skip_place and math.hypot(p[0] - pl["at"][0], p[1] - pl["at"][1]) < PLACE_CLEAR + r:
                return "place"
        for o in self.objects:                    # a named house / well / car: nothing auto-filled on top of it
            d = math.hypot(p[0] - o["at"][0], p[1] - o["at"][1])
            if 0.01 < d < _radius_of(o["type"]) * float(o.get("scale", 1.0) or 1.0) + r + 2.0:
                return "object"
        return None

    def ground_at(self, p):
        """The ground colour / kind at a point (the last area that covers it wins)."""
        g = None
        for a in self.areas:
            if a["bbox"][0] <= p[0] <= a["bbox"][2] and a["bbox"][1] <= p[1] <= a["bbox"][3] and in_poly(p, a["shape"]):
                g = a
        return g

    # ---------------------------------------------------------------- the things of an area, cell by cell
    def _cell_things(self, a, ci, cj):
        key = (a["id"], ci, cj)
        got = self._cells.get(key)
        if got is None:
            if len(self._cells) > 20000:
                self._cells.clear()
            got = self._cells[key] = self._cell_make(a, ci, cj)
        return [dict(o) for o in got]

    def _cell_make(self, a, ci, cj):
        info = AREA_KINDS[a["kind"]]
        if not info["things"] or info["per_ha"] <= 0:
            return []
        dens = float(a.get("density", 1.0))
        n_f = info["per_ha"] * (CELL * CELL / 10000.0) * dens
        rng = random.Random(stable_hash(f"{self.name}|{a['id']}|{ci}|{cj}|{a.get('seed', 0)}"))
        n = int(n_f) + (1 if rng.random() < n_f - int(n_f) else 0)
        things = a.get("things")
        pool = [(str(t[0]), float(t[1])) for t in things] if things else info["things"]
        if self.clay:                                    # (an area that only says its kind: its default things in clay)
            pool = [(self.clay.get(t, t), w) for t, w in pool]
        if a["kind"] == "fields":
            crop = str(a.get("crop", "green")).lower()
            state = {"mustard": "mustard", "wheat": "wheat", "rice": None, "green": None}.get(crop)
        else:
            state = None
        total = sum(w for _t, w in pool) or 1.0
        out, placed = [], []
        spacing = info.get("spacing", 3.0)
        lane = None
        if a.get("rows"):
            # 🏘 a hamlet (tola) of the Satpura villages: the houses stand side by side in two rows facing each other
            # across a wide lane (the shared yard where grain is dried and cattle are tied), not scattered; between
            # the hamlets: gardens, trees, haystacks, cattle sheds. A hamlet runs along a cell row for ~150 m.
            houses = list(a["rows"])                                # (a name twice = twice as common)
            cx, cz = self._centre(a["shape"])
            d = math.hypot((ci + 0.5) * CELL - cx, (cj + 0.5) * CELL - cz)
            hr = random.Random(stable_hash(f"{self.name}|{a['id']}|tola|{ci // 3}|{cj}"))
            if hr.random() < max(0.0, 0.75 - d / 500.0):
                lane = (cj + 0.5) * CELL + hr.uniform(-6, 6)
                x = ci * CELL + rng.uniform(0, 4)
                k = 0
                while x < (ci + 1) * CELL - 3:
                    step = rng.uniform(5.2, 6.4)
                    for side in (1, -1):
                        if rng.random() < 0.12:
                            continue                                  # a gap: a path to the back yards
                        typ = houses[int(rng.random() * len(houses))]
                        z = lane + side * (7.5 + rng.uniform(0, 1.2))
                        r = _radius_of(typ)
                        if not in_poly((x, z), a["shape"]) or self.blocked((x, z), r * 0.6):
                            continue
                        placed.append((x, z, r * 0.6))
                        out.append({"id": f"{a['id']}.{ci}.{cj}.h{k}", "type": typ, "at": (x, z),
                                    "turn": (0.0 if side > 0 else 180.0) + rng.uniform(-3, 3),
                                    "scale": round(rng.uniform(0.92, 1.08), 2), "area": a["id"], "auto": True})
                        k += 1
                        step = max(step, 2.0 * r * 0.93)               # (a big house takes its own width)
                    x += step                                            # house beside house (walls nearly touching)
            pool = [(t, w) for t, w in pool if t not in a["rows"]]
            total = sum(w for _t, w in pool) or 1.0
        for k in range(n * 2):
            if len(out) >= n:
                break
            x = (ci + rng.random()) * CELL
            z = (cj + rng.random()) * CELL
            u = rng.random() * total
            for typ, w in pool:
                u -= w
                if u <= 0:
                    break
            r = _radius_of(typ)
            if not in_poly((x, z), a["shape"]) or self.blocked((x, z), r):
                continue
            if lane is not None and abs(z - lane) < 11:
                continue                                              # the lane and the house rows stay as they are
            if any(math.hypot(x - px, z - pz) < max(spacing, r + pr) for px, pz, pr in placed):
                continue
            placed.append((x, z, r))
            oid = f"{a['id']}.{ci}.{cj}.{k}"
            o = {"id": oid, "type": typ, "at": (x, z), "turn": round(rng.uniform(0, 360), 1),
                 "scale": round(rng.uniform(0.85, 1.2), 2), "area": a["id"], "auto": True}
            if state:
                o["state"] = state
            if a["kind"] == "fields":
                o["turn"] = float(a.get("turn", 0.0))
                o["scale"] = 1.0
            out.append(o)
        return out

    def things_near(self, x, z, radius, view=True, limit=None):
        """Every object (placed + auto-filled + edited) within radius metres of (x, z), nearest first.
        view=True: small things only when near (crops within 160 m ...)."""
        out = []
        for o in self._objects_near(x, z, radius):     # spatial hash: only the cells round the spot
            d = math.hypot(o["at"][0] - x, o["at"][1] - z)
            if d <= radius and (not view or d <= VIEW.get(o["type"], VIEW_DEFAULT)):
                out.append((d, o))
        for a in self.areas:
            bx0, bz0, bx1, bz1 = a["bbox"]
            if bx1 < x - radius or bx0 > x + radius or bz1 < z - radius or bz0 > z + radius:
                continue
            i0, i1 = int(max(bx0, x - radius) // CELL), int(min(bx1, x + radius) // CELL)
            j0, j1 = int(max(bz0, z - radius) // CELL), int(min(bz1, z + radius) // CELL)
            for ci in range(i0, i1 + 1):
                for cj in range(j0, j1 + 1):
                    cx, cz = (ci + 0.5) * CELL, (cj + 0.5) * CELL
                    if math.hypot(cx - x, cz - z) > radius + CELL:
                        continue
                    for o in self._cell_things(a, ci, cj):
                        if o["id"] in self.removed:
                            continue
                        if o["id"] in self.edits:
                            o = dict(o, **{k: (_pt(v) if k == "at" else v) for k, v in self.edits[o["id"]].items()})
                            o["auto"] = False
                        d = math.hypot(o["at"][0] - x, o["at"][1] - z)
                        if d <= radius and (not view or d <= VIEW.get(o["type"], VIEW_DEFAULT)):
                            out.append((d, o))
        out.sort(key=lambda it: it[0])
        got = [o for _d, o in out]
        return got[:limit] if limit else got

    HASH = 100.0                                         # metres per spatial-hash cell for the placed objects

    def _objects_near(self, x, z, radius):
        """The placed objects in the hash cells that touch the circle (book ch. 12 / 16: spatial hashing - a world
        with thousands of things only looks at the few cells near the camera)."""
        key = (len(self.objects), id(self.objects))
        g = getattr(self, "_ohash", None)
        if g is None or g[0] != key:
            cells = {}
            for o in self.objects:
                c = (int(o["at"][0] // self.HASH), int(o["at"][1] // self.HASH))
                cells.setdefault(c, []).append(o)
            g = self._ohash = (key, cells)
        cells = g[1]
        if len(self.objects) < 64:
            return self.objects
        i0, i1 = int((x - radius) // self.HASH), int((x + radius) // self.HASH)
        j0, j1 = int((z - radius) // self.HASH), int((z + radius) // self.HASH)
        if (i1 - i0 + 1) * (j1 - j0 + 1) > len(cells):
            return self.objects
        out = []
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                out.extend(cells.get((i, j), ()))
        return out

    def places_near(self, x, z, radius):
        return sorted((p for p in self.places if math.hypot(p["at"][0] - x, p["at"][1] - z) <= radius),
                      key=lambda p: math.hypot(p["at"][0] - x, p["at"][1] - z))

    # ---------------------------------------------------------------- summary for people and the AI
    def summary(self, max_objects=40):
        """Text for the story prompt: places, areas, roads, rivers and the named objects with abilities."""
        from . import images
        lines = [f'WORLD "{self.name}" ({self.title}), {int(self.size[0])} x {int(self.size[1])} m. '
                 f'x = east, z = north, in metres.']
        if self.spec.get("description"):
            lines.append(str(self.spec["description"]))
        lines.append("Places (a scene happens AT one of these):")
        for p in self.places:
            desc = p.get("description") or ""
            lines.append(f'  {p["id"]}: {p.get("place")} at {int(p["at"][0])},{int(p["at"][1])}'
                         f'{" - " + desc if desc else ""}{_things_of_place(p.get("place"))}')
        if self.areas:
            lines.append("Areas: " + "; ".join(f'{a["id"]} ({a["kind"]})' for a in self.areas))
        if self.roads or self.rivers:
            lines.append("Roads / rivers: " + "; ".join(f'{r["id"]} ({r["kind"]}'
                                                        f'{", " + r.get("style", "") if r["kind"] == "road" else ""})'
                                                        for r in self.roads + self.rivers))
        named = []
        for o in self.objects[:max_objects]:
            ab = o.get("abilities") or (images.info(o["type"]) or {}).get("abilities") or []
            reach = [p["id"] for p in self.places
                     if to_story(o["at"], p["at"], math.radians(p.get("turn", 0.0) or 0.0), 2400) is not None]
            desc = f' - {o["description"]}' if o.get("description") else ""
            where = (f"usable in scenes at {', '.join(reach)}" if reach else
                     f'a scene can be "at": "{o["id"]}" (near {self.nearest_place(o["at"]) or "nothing"})')
            drive = ""
            if str((images.info(o["type"]) or {}).get("kind", "")).lower() == "vehicle":
                drive = (f' - a VEHICLE people can get in and drive: {{"who": "ramu", "do": "ride", "vehicle": "{o["id"]}"}}'
                         f' then {{"vehicle": "{o["id"]}", "to": {{"x": 2100}}}}')
            named.append(f'  {o["id"]}: {o["type"]}{" (" + "/".join(ab) + ")" if ab else ""}{desc}; {where}{drive}')
        if named:
            lines.append("Named objects (use their ids in events):")
            lines += named
        return "\n".join(lines)

    def nearest_place(self, p, within=400.0):
        best = None
        for q in self.places:
            d = math.hypot(q["at"][0] - p[0], q["at"][1] - p[1])
            if d <= within and (best is None or d < best[0]):
                best = (d, q["id"])
        return best[1] if best else None

    # ---------------------------------------------------------------- checking
    def check(self):
        """(problems, notes) - problems = things that will not work; notes = what was fixed / worth knowing."""
        from . import registry, images
        probs, notes = [], list(self.notes)
        places = registry.load().get("places", {})
        seen = set()
        W, H = self.size
        for p in self.places:
            if p["id"] in seen:
                probs.append(f"two places are called '{p['id']}'")
            seen.add(p["id"])
            if p.get("place") not in places:
                have = [n for n in places if n.endswith("_3d")]
                probs.append(f"place '{p['id']}': there is no place called '{p.get('place')}' "
                             f"(3D places: {', '.join(sorted(have))})")
            if not (0 <= p["at"][0] <= W and 0 <= p["at"][1] <= H):
                probs.append(f"place '{p['id']}' is outside the map ({W:.0f} x {H:.0f} m)")
            for q in self.places:
                if q is not p and q["id"] > p["id"] and math.hypot(q["at"][0] - p["at"][0], q["at"][1] - p["at"][1]) < 40:
                    notes.append(f"places '{p['id']}' and '{q['id']}' are very close ({math.hypot(q['at'][0] - p['at'][0], q['at'][1] - p['at'][1]):.0f} m)")
            for rv in self.rivers:
                if line_dist(p["at"], rv["line"]) < rv["width"] / 2 and "river" not in str(p.get("place")) \
                        and "ghat" not in p["id"] and "lake" not in str(p.get("place")):
                    probs.append(f"place '{p['id']}' is in the river '{rv['id']}' - move it to the bank")
        for o in self.objects:
            if not images.exists(o["type"]):
                probs.append(f"object '{o['id']}': unknown type '{o['type']}' (use a 3D thing from your library)")
            why = self.blocked(o["at"], 0.5)
            if why in ("river", "water"):
                notes.append(f"object '{o['id']}' stands in the {why}")
        for a in self.areas:
            for typ, _w in (a.get("things") or []):
                if not images.exists(typ):
                    probs.append(f"area '{a['id']}': unknown thing '{typ}'")
        try:
            from .animals import QUADS, BIRDS, ALIASES
            kinds = set(QUADS) | set(BIRDS) | set(ALIASES)
        except Exception:                                   # noqa: BLE001
            kinds = set()
        for rid, rv in residents(self).items():
            for key in ("home", "works_at", "enclosure"):
                where = rv.get(key)
                if where and _clean(where) not in self.byid:
                    probs.append(f"resident '{rid}': {key} '{where}' is not a place / object of this world")
            for t_, what in (rv.get("routine") or {}).items():       # "at <id>" in a routine must be real
                import re as _re
                for m in _re.findall(r"\bat (?:the |a |an )?([a-z][a-z0-9_]*)", str(what).lower()):
                    if m not in self.byid and m not in ("home", "night", "noon", "dawn", "dusk", "work", "last",
                                                        "first", "once", "least", "all", "his", "her", "their"):
                        probs.append(f"resident '{rid}': routine '{t_}' says 'at {m}' - no such place / object")
            if rv.get("species") and kinds and str(rv["species"]).lower() not in kinds:
                notes.append(f"resident '{rid}': species '{rv['species']}' is not a built-in animal (make it in the Studio)")
        for r in self.roads:
            if r.get("style") and r["style"] not in ROAD_STYLES:
                notes.append(f"road '{r['id']}': style '{r['style']}' - use one of {', '.join(ROAD_STYLES)}")
        return probs, notes


def _things_of_place(place):
    """' [well (hide), cot (sit/stand) ...]' - the interactive things inside a 3D place."""
    from . import registry, images
    spec = registry.place(place) or {}
    got = []
    for t in spec.get("things") or []:
        if isinstance(t, dict) and t.get("id"):
            ab = (images.info(t.get("what")) or {}).get("abilities") or []
            if ab:
                got.append(f"{t['id']} ({'/'.join(ab[:3])})")
    return (" [" + ", ".join(got[:10]) + "]") if got else ""


# ============================================================================ a story scene inside the world
AREA_PRESET = {"jungle": "jungle_3d", "forest": "forest_3d", "grove": "coconut_village_3d", "fields": "farm_3d",
               "village": "village_3d", "town": "street_3d", "desert": "desert_3d", "hills": "mountains_3d",
               "rocks": "mountains_3d", "park": "park_3d", "sand": "beach_3d"}


def heading_to(a, b):
    """Map direction (radians, 0 = north, + = east) from a to b."""
    return math.atan2(b[0] - a[0], b[1] - a[1])


def scene_spec(w, at, look=None, background=None):
    """Where a scene stands in the world. -> dict(bg_spec, anchor (x, z) m, heading (rad), own place id, notes)
    or raises ValueError with a helpful message."""
    key = _clean(at) if not isinstance(at, (list, tuple)) else None
    notes = []
    extra = {k: v for k, v in (background or {}).items() if k not in ("preset", "type", "at")} \
        if isinstance(background, dict) else {}
    if key is not None and key not in w.byid:
        names = [p["id"] for p in w.places] + [o["id"] for o in w.objects] + [a["id"] for a in w.areas]
        raise ValueError(f"'{at}' is not in the world '{w.name}' (places: {', '.join(p['id'] for p in w.places)}"
                         f"{'; objects / areas: ' + ', '.join(names[len(w.places):][:20]) if len(names) > len(w.places) else ''})")
    own = None
    if key is None:                                        # "at": [x, z] metres
        anchor = _pt(at)
        area = w.ground_at(anchor)
        preset = AREA_PRESET.get(area["kind"]) if area else None
        spec = {"preset": "plain", "ground": w.spec.get("ground", "grass")}
        heading = 0.0
    else:
        item = w.byid[key]
        heading = math.radians(float(item.get("turn", 0.0) or 0.0))
        if item in w.places or item.get("place"):
            own = item["id"]
            anchor = item["at"]
            spec = {"preset": item["place"]}
            area = w.ground_at(anchor)
            if area and area.get("ground"):                # the real soil of the land here (engine/landphysics.py)
                spec["ground"] = area["ground"]
            if item.get("water"):                          # "none": the map's own river (real width) instead of the
                spec["water"] = item["water"]              # place's endless painted water
        elif item.get("type"):                             # a named object: the stage in front of it
            obj = item["at"]
            anchor = (obj[0] - 9.0 * math.sin(heading), obj[1] - 9.0 * math.cos(heading))
            area = w.ground_at(anchor)
            spec = {"preset": "plain", "ground": _ground_word(area, w)}
        else:                                              # an area: its middle
            anchor = item["at"]
            spec = {"preset": "plain", "ground": _ground_word(item, w)}
    if look is not None:                                   # "look": "rampur" / 90 -> which way the camera looks
        if isinstance(look, (int, float)):
            heading = math.radians(float(look))
        else:
            tgt = w.where(look)
            if tgt is None:
                notes.append(f"look: '{look}' is not in the world - looking the place's own way")
            else:
                heading = heading_to(anchor, tgt)
    sk = skyline(w, anchor, heading)
    if sk:
        spec["skyline"] = sk                              # the real ridges round the spot (world3d draws them)
    spec.setdefault("time", w.spec.get("time", "day"))
    if w.spec.get("far"):
        spec.setdefault("far", w.spec.get("far"))
    spec.update(extra)
    return dict(bg_spec=spec, anchor=anchor, heading=heading, own=own, notes=notes)


def skyline(w, anchor, heading, eye=1.6):
    """🏔 the REAL horizon from a spot: looking all round (every 2°), the highest the land rises above the eye -
    near / middle / far ridges kept apart (they are drawn back to front, the far ones hazier), and whether it is a
    cliff (steep: bare rock) or forest. From the world's terrain (and its wider "horizon" grid when it has one).
    -> {"az": [deg, relative to the view], "layers": [{"dist": m, "elev": [deg], "rock": [0/1]}]} or None"""
    T = w.spec.get("terrain")
    if not T or not T.get("h"):
        return None
    from .terrain import height_at
    Hz = w.spec.get("horizon")
    size = T["cell"] * T["n"]

    def hgt(x, z):
        if 0 <= x <= size and 0 <= z <= size:
            return height_at(T, x, z)
        if Hz:                                            # beyond the map: the coarse wider grid (same base)
            return height_at(Hz, x - Hz["origin"][0], z - Hz["origin"][1])
        return None
    h0 = hgt(anchor[0], anchor[1]) or 0.0
    reach = Hz["cell"] * Hz["n"] / 2 if Hz else size / 2
    bands = ((120.0, 1200.0), (1200.0, 3000.0), (3000.0, reach))
    azs = list(range(-180, 180, 2))
    layers = [{"dist": round((a + b) / 2), "elev": [], "rock": []} for a, b in bands]
    for az in azs:
        a = heading + math.radians(az)
        sx, sz = math.sin(a), math.cos(a)
        best = [(-9.0, 0) for _ in bands]
        r = 120.0
        while r < reach:
            x, z = anchor[0] + sx * r, anchor[1] + sz * r
            hh = hgt(x, z)
            if hh is None:
                break
            e = math.degrees(math.atan2(hh - h0 - eye, r))
            k = 0 if r < bands[0][1] else (1 if r < bands[1][1] else 2)
            if e > best[k][0]:
                h2 = hgt(x + sx * 60, z + sz * 60)
                steep = h2 is not None and abs(h2 - hh) / 60.0 > 0.45
                best[k] = (e, 1 if steep else 0)
            r += 40.0 if r < 1200 else (80.0 if r < 3000 else 160.0)
        for k in range(len(bands)):
            layers[k]["elev"].append(round(best[k][0], 2))
            layers[k]["rock"].append(best[k][1])
    return {"az": azs, "layers": layers}


def _ground_word(area, w):
    g = (area.get("ground") or AREA_KINDS.get(area["kind"], {}).get("ground")) if area else None   # (an area can
    # carry its own soil colour: engine/landphysics.py works it out from the rock, the rain and the slope)
    return g or w.spec.get("ground", "grass")


def to_scene(p, anchor, heading):
    """World metres -> the scene's 3D world units (X across, Z into the scene; the stage front is Z = FOCAL)."""
    from .scene3d import FOCAL
    dx, dz = p[0] - anchor[0], p[1] - anchor[1]
    s, c = math.sin(heading), math.cos(heading)
    fwd = dx * s + dz * c
    right = dx * c - dz * s
    return right * UNITS, FOCAL + fwd * UNITS           # X relative to the scene's centre line


def to_story(p, anchor, heading, width):
    """World metres -> story (x, z) of this scene, or None when it is out of the scene's reach."""
    from .world3d import Z_of_z
    from .scene3d import FOCAL
    Xr, Z = to_scene(p, anchor, heading)
    if Z < FOCAL - 1.0:
        return None
    Zb = Z_of_z(1000.0)
    if Z <= Zb:
        z = (1.0 - FOCAL / Z) * 1000.0 / 0.58
    else:
        z = 1000.0 + (Z - Zb) / 4.0
    if z > 2600:
        return None
    pz = FOCAL / Z
    x = width / 2.0 + Xr * pz
    if not (-200 <= x <= width + 200):
        return None
    return round(x, 1), round(z, 1)


# ============================================================================ prompts: an AI writes worlds, stories use them
def library_text():
    """3D places and things the world may use (for the world prompt)."""
    from . import codedraw, images
    places, things = [], []
    for n, m in sorted(codedraw.list_code().items()):
        if m["kind"] == "place3d":
            places.append(f"  {n}: {str(m['description'])[:110]}")
        elif m["kind"] in ("object3d", "prop3d", "vehicle3d"):
            ab = (images.info(n) or {}).get("abilities") or []
            st = f" (looks: {', '.join(m['states'])})" if m["states"] else ""
            things.append(f"  {n}: {str(m['description'])[:80]}{st}{' - ' + '/'.join(ab) if ab else ''}")
    return places, things


WORLD_EXAMPLE = """{
 "world": "chandpur", "title": "Chandpur", "description": "a small village by a lake with a mango grove",
 "size": [5000, 5000], "ground": "grass", "time": "morning", "far": ["hills"],
 "places": [
  {"id": "chandpur", "place": "village_3d", "at": [2000, 2000], "turn": 0, "description": "the village square"},
  {"id": "lake_side", "place": "lake_3d", "at": [2400, 2600], "turn": 0, "description": "the lake jetty"},
  {"id": "school", "place": "school_ground_3d", "at": [1700, 1750], "turn": 180}
 ],
 "roads": [{"id": "lake_road", "from": "chandpur", "to": "lake_side", "width": 5, "style": "dirt"},
           {"id": "school_road", "from": "chandpur", "to": "school", "width": 4, "style": "footpath"}],
 "rivers": [],
 "areas": [
  {"id": "chandpur_houses", "kind": "village", "at": [2000, 2000], "radius": 200},
  {"id": "big_lake", "kind": "lake", "at": [2500, 2750], "radius": 140},
  {"id": "mango_grove", "kind": "forest", "things": [["tree_round_3d", 0.8], ["bush_3d", 0.2]],
   "shape": [[1300, 2300], [1700, 2300], [1700, 2700], [1300, 2700]]},
  {"id": "rice_fields", "kind": "fields", "crop": "green", "shape": [[2300, 1200], [3100, 1200], [3100, 1700], [2300, 1700]]}
 ],
 "objects": [{"id": "old_banyan", "type": "banyan_3d", "at": [2006, 2038], "turn": 0, "description": "the old banyan"},
             {"id": "raju_ka_ghar", "type": "house_3d", "at": [1990, 2024], "turn": 0, "description": "Raju's house"},
             {"id": "raju_ki_cycle_rickshaw", "type": "cart_3d", "at": [2012, 2020], "turn": 90, "description": "Raju's cart"}],
 "residents": {
  "raju": {"name": "Raju", "gender": "male", "age": "adult", "outfit": "kurta", "outfit_color": "#f1f1e6", "skin": "medium",
           "job": "fisherman", "home": "raju_ka_ghar", "works_at": "lake_side", "family": "father of Pinki",
           "about": "cheerful, sings while he fishes",
           "routine": {"morning": "fishes at the lake_side", "day": "sells fish at the chandpur square",
                       "evening": "mends his nets under the old_banyan", "night": "sleeps at raju_ka_ghar"},
           "duties": ["catches fish", "sells fish in the square"]},
  "pinki": {"name": "Pinki", "gender": "female", "age": "child", "outfit": "frock", "outfit_color": "#ff70a6",
            "hair": "ponytail", "job": "student", "home": "raju_ka_ghar", "works_at": "school",
            "routine": {"morning": "goes to school", "evening": "plays at the lake_side"}},
  "moti": {"name": "Moti", "species": "dog", "home": "raju_ka_ghar", "about": "Raju's dog"}
 }
}"""


def world_prompt(idea, current=None):
    """The prompt for Gemini / any AI: write (or change) a world JSON."""
    places, things = library_text()
    kinds = "\n".join(f"  {k}: " + (", ".join(t for t, _w in v["things"]) or "nothing grows (" +
                                    ("water" if v.get("water") else "open ground") + ")")
                      for k, v in AREA_KINDS.items())
    try:
        from .animals import QUADS, BIRDS, CUSTOM
        animal_list = (", ".join(sorted(QUADS)) + "; birds: " + ", ".join(sorted(b for b in BIRDS if b != "bird")) +
                       ("; your own: " + ", ".join(sorted(CUSTOM)) if CUSTOM else ""))
    except Exception:                                    # noqa: BLE001
        animal_list = "lion, tiger, elephant, giraffe, zebra, deer, hippo, dog, cow; birds: peacock, parrot, flamingo"
    change = ""
    if current:
        change = ("\nCHANGE this world as asked. Keep every id that stays, keep \"edits\" and \"removed\" as they are, "
                  "and answer with the WHOLE changed world JSON.\nThe current world:\n```json\n" +
                  json.dumps(current, indent=1, ensure_ascii=False) + "\n```\n")
    return f"""You design a big 3D world (a map) for an animated story engine. Many videos are made in the same world.
Write ONE world JSON for: {idea}
{change}
RULES
- Units are METRES. "size": [5000, 5000] unless asked otherwise. x = east (0 .. size[0]), z = north (0 .. size[1]).
- "places": the spots where scenes happen. "place" MUST be one of the 3D places below. Give each a short snake_case
  "id" (sonpur, ghat, mela ...) and a "description". Keep places at least 150 m apart; a village is a place with a
  "village" area round it (radius 150-250). "turn" (degrees) = which way the place faces (0 = north).
- "roads": {{"id", "from": <place id>, "to": <place id>, "via": [[x, z], ...] (bends, optional), "width": 3-8,
  "style": "dirt" | "tar" | "stone" | "footpath" | "sand"}}. Connect every place by roads or footpaths.
- "rivers": {{"id", "points": [[x, z], ...] from one map edge to another, "width": 20-80}}. Places that are NOT
  river places stay at least 60 m from a river; a ghat / river place sits right on the bank (about width/2 + 30 m
  from the river line).
- "areas": {{"id", "kind", "shape": [[x, z], ...]}} or {{"id", "kind", "at": [x, z], "radius": r}}. They fill
  themselves with things (trees, huts, crops ...). Kinds and what grows in them:
{kinds}
  fields can have "crop": "mustard" | "wheat" | "green". hills can have "height" (metres). Any area can have
  "things": [["tree_round_3d", 0.7], ["bush_3d", 0.3]] (types + shares) and "density" (1 = normal).
- "objects": special named things stories will use by id (the old banyan, the haunted well, the broken cart):
  {{"id", "type": <a 3D thing below>, "at": [x, z], "turn": 0, "description"}}. 5-15 of them, near places.
- Also "world" (snake_case name), "title", "description", "ground": "grass" | "mud" | "sand" | "snow",
  "time": "morning" | "day" | "evening" | "night", "far": ["hills" | "mountains" | "sea" | "forest" | "city"],
  "edits": {{}}, "removed": [].
- Plan it like a real place: villages near water and fields, a road network, a jungle or forest at the edges,
  hills in a corner, special spots (temple, mela, school, ghat, well) where stories happen.
- WHAT A SCENE SEES: a scene at a place (turn 0) sees the world 12-44 m in FRONT of it (north for turn 0; turn 90 =
  east ...), up to about half that distance to each side. Put each place's landmarks (the old banyan, the well,
  the houses of the people who live there, their car / cart) in that zone, so they stand behind the actors.
  Never put an object on a road, in a river or lake, or on another object (keep 4 m between objects).
- Roads never cross a river (there are no bridges): the other bank is reached by a ghat place + a boat_3d object
  ("the ferry") next to it on the water, and a road that starts again on the far bank.
- "residents": the people and animals who LIVE in this world (8-25). Each is a character (the same look in every
  video) with a life - that is what makes stories easy and real:
    people: {{"name", "gender", "age": "child" | "teen" | "adult" | "old", "outfit" (kurta, saree, shirt, tshirt,
    frock, salwar, dhoti, uniform, farmer, chef, police, nurse ...), "outfit_color", "skin", "hair", "hat",
    "mustache", "glasses",
    "job" (farmer, tea seller, teacher, zookeeper, ferryman, shopkeeper, priest, doctor, student ...),
    "home": <an object id - give every family its own house_3d / hut_3d object, e.g. "ramu_ka_ghar">,
    "works_at": <a place id>, "family": "wife of Ramu, mother of Chhotu", "about": "kind, a little lazy",
    "routine": {{"morning": "...", "day": "...", "evening": "...", "night": "..."}} - WHERE they are and what they
    do at each time; write "at <place or object id>" (e.g. "makes tea at chai_dukaan"),
    "duties": ["what their work is", "..."]}}
    animals: {{"name", "species": <an animal below>, "home": <place / object id>, "enclosure": <zoo place id>,
    "about"}}. Pets live at their family's house; zoo animals in their enclosure.
  Give every job a workplace that EXISTS in the world (a tea seller needs a tea_stall_3d place, a ferryman a
  ghat + a boat, a zookeeper a zoo). Vehicles people own (car_3d, cart_3d, boat_3d) are named objects near where
  they are used - stories can drive them.
- A ZOO: an entrance (garden_3d, the "zoo_gate") + one zoo_enclosure_3d place per big animal group (lions, tigers,
  elephants, giraffes + zebras + deer - its fence runs across the whole stage so animals stay inside), a lake_3d for
  hippos / flamingos / ducks, a garden_3d for birds, footpaths from the gate to each, a "park" area round it all,
  and a zookeeper resident with a hut by the gate. Keep enclosures 150+ m apart.
- Animals that can live here: {animal_list}

3D PLACES (use exactly these names in "place"):
{chr(10).join(places)}

3D THINGS (use exactly these names in "type" and in area "things"):
{chr(10).join(things)}

EXAMPLE (small):
{WORLD_EXAMPLE}

Answer with the world JSON only."""


def write_prompt_file():
    os.makedirs(os.path.join(HERE, "prompts"), exist_ok=True)
    p = os.path.join(HERE, "prompts", "world_prompt.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(world_prompt("<DESCRIBE YOUR WORLD HERE: villages, rivers, jungle, hills, special places ...>"))
    return p


def split_only(name):
    """"ratibad+only" -> ("ratibad", True): the story may use ONLY what is already in the world."""
    n = str(name or "").strip()
    only = n.lower().endswith("+only")
    return (n[:-5].strip() if only else n), only


ONLY_RULES = """ONLY WHAT IS IN THIS WORLD (strict): build the whole story from the world below and nothing else.
- Every scene is "at" one of its places, named objects or areas. Never a "background" "preset" (only
  "time" / "weather" may be set), never a place, building, shop, temple, river or road that is not listed.
- Vehicles: only the world's own vehicles (by id). Never add "vehicles".
- Big things (trees, rocks, huts, wells, carts, stalls ...): only the places' own objects and the world's named
  objects. Never add "objects".
- Allowed: the characters, and small things people carry in their hands ("props" with "held_by": a cup, a
  phone, a bag, a letter, a stick, a ball, a kite, a flower, a book, an umbrella).
- If the idea asks for something the world does not have, use the nearest thing the world HAS and say so in
  "notes" (e.g. no temple -> the shrine at the ghat).
- Put "world_only": true in "settings"."""


def only_check(story, w):
    """Things a "world_only" story added that are not in the world. -> list of messages."""
    from .props import PROP_TYPES
    out = []
    ids = set(w.byid)
    for i, sc in enumerate(story.get("scenes") or []):
        if not isinstance(sc, dict):
            continue
        where = f"scene {i + 1} ({sc.get('id', '')})"
        at = sc.get("at")
        if at is None:
            out.append(f"world only: {where} has no \"at\" - pick one of the world's places "
                       f"({', '.join(p['id'] for p in w.places[:8])})")
        own = set()
        if isinstance(at, str) and _clean(at) in w.byid and w.byid[_clean(at)].get("place"):
            own = set(_place_things(w.byid[_clean(at)]["place"]))
        bg = sc.get("background")
        if isinstance(bg, str) or (isinstance(bg, dict) and (bg.get("preset") or bg.get("type"))):
            out.append(f"world only: {where} sets its own background "
                       f"'{bg if isinstance(bg, str) else bg.get('preset') or bg.get('type')}' - use \"at\" a world place "
                       f"(only \"time\" / \"weather\" in \"background\")")
        for k in ("objects", "vehicles"):
            for o in sc.get(k) or []:
                oid = o if isinstance(o, str) else (o.get("id") if isinstance(o, dict) else None)
                if oid and _clean(oid) not in ids and oid not in own:
                    out.append(f"world only: {where} adds {k[:-1]} '{oid}' - it is not in the world "
                               f"(use one of the world's, or add it in the World Explorer first)")
        for pr in sc.get("props") or []:
            typ = pr if isinstance(pr, str) else (pr.get("type") or pr.get("id") if isinstance(pr, dict) else None)
            if typ and str(typ).lower() not in PROP_TYPES and _clean(typ) not in ids:
                out.append(f"world only: {where} adds prop '{typ}' - only small hand-held things are allowed "
                           f"({', '.join(PROP_TYPES[:8])} ...)")
    return out


def _place_things(place):
    try:
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "code",
                                place + ".py"), encoding="utf-8").read()
    except OSError:
        return []
    import re as _re
    return _re.findall(r"thing\(\s*[\"']([^\"']+)", src)


RESIDENT_INFO = ("home", "works_at", "job", "about", "family", "enclosure", "routine", "duties")
TIMES = ("morning", "day", "evening", "night")


def residents(w):
    """{id: spec} - the people and animals who live in world w (their looks stay the same in every video)."""
    r = (getattr(w, "spec", None) or {}).get("residents") or {}
    return {_clean(k): v for k, v in r.items() if isinstance(v, dict)}


def resident_look(spec):
    """A resident's character spec without the world-only notes (home, job ...)."""
    return {k: v for k, v in spec.items() if k not in RESIDENT_INFO}


def residents_text(w):
    rs = residents(w)
    if not rs:
        return ""
    people = [(k, v) for k, v in rs.items() if not v.get("species")]
    animals = [(k, v) for k, v in rs.items() if v.get("species")]
    lines = ["PEOPLE AND ANIMALS WHO LIVE HERE - use these ids in \"characters\" with an EMPTY spec, e.g. "
             "\"ramu\": {} (their looks, clothes and voices are fixed by the world, the same in every video). You may "
             "add visitors, but the world's own people are these:"]
    for k, v in people + animals:
        bits = [v.get("name", k)]
        if v.get("species"):
            bits.append(v["species"])
        else:
            bits.append(" ".join(str(v.get(x)) for x in ("age", "gender") if v.get(x)))
        if v.get("job"):
            bits.append(str(v["job"]))
        where = []
        if v.get("home"):
            where.append(f'lives at {v["home"]}')
        if v.get("works_at"):
            where.append(f'works at {v["works_at"]}')
        extra = f' - {v["about"]}' if v.get("about") else ""
        fam = f' ({v["family"]})' if v.get("family") else ""
        lines.append(f"  {k}: {', '.join(b for b in bits if b)}{fam}; {'; '.join(where)}{extra}")
        rt = v.get("routine") if isinstance(v.get("routine"), dict) else {}
        if rt:                                        # where they are and what they do through the day
            lines.append("      day: " + " | ".join(f"{t_}: {rt[t_]}" for t_ in TIMES if rt.get(t_)))
        if v.get("duties"):
            lines.append("      work: " + "; ".join(v["duties"] if isinstance(v["duties"], list) else [str(v["duties"])]))
    lines.append("  Use the routines: a scene in the morning at the tea stall has Shyam working there; somebody who is "
                 "somewhere else than their routine says why (a holiday, a visit, trouble) - that makes the story feel real.")
    if animals:
        lines.append("  Zoo animals stay INSIDE their enclosure. At a zoo_enclosure_3d place the fence runs across the whole "
                     "stage at z 620: put the animals BEHIND it (z 700-950) and the visitors in front (z 100-550); the "
                     "keeper goes in through the keeper_gate (\"do\": \"open\"). Water animals (hippo, flamingo, duck) "
                     "stay in / at their lake, birds in their garden. An animal outside its enclosure is a big story event "
                     "(it escaped) - only if the idea asks for it.")
    return "\n".join(lines) + "\n"


_LAYOUT = {}


def place_layout(place, width=2400):
    """Where things stand on this place's stage, in STORY units (what "to": {"x", "z"} uses):
    (things [(id, x, z, size, abilities)], water text or None)."""
    key = (place, width)
    if key in _LAYOUT:
        return _LAYOUT[key]
    things, water = [], None
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "places",
                               place + ".json"), encoding="utf-8") as fh:
            spec = json.load(fh)
    except (OSError, ValueError):
        spec = {}
    from . import images
    for t in spec.get("things") or []:
        if not isinstance(t, dict) or t.get("id") is None:
            continue
        meta = images.info(t.get("what")) or {}
        h = float(t.get("height") or meta.get("height") or 0)
        if meta.get("walk") and h < 40:
            continue                                   # a floor / a road: ground, not a thing
        size = "tall" if h >= 250 else ("low" if h < 90 else "")
        ab = [a for a in (meta.get("abilities") or []) if a in ("sit", "stand", "hide", "climb", "open", "switch")]
        if meta.get("walk") and "stand" not in ab:
            ab.append("stand on")
        things.append((t["id"], round(width / 2.0 + float(t.get("x", 0))), round(float(t.get("z", 0))), size, ab))
    w_ = spec.get("water")
    if w_:
        try:
            from .background import Background
            bg = Background({"preset": place}, width)
            if bg.water and bg.shore_x is not None:
                side = "right" if bg.land_side == "left" else "left"
                water = f"{bg.water} from x {bg.shore_x:.0f} to the {side} edge (nobody walks into it; boats float on it)"
        except Exception:                               # noqa: BLE001 - the layout is only a help
            water = f"{w_.get('kind', 'water') if isinstance(w_, dict) else 'water'} on the " \
                    f"{w_.get('side', 'right') if isinstance(w_, dict) else 'right'} side"
    _LAYOUT[key] = (sorted(things, key=lambda q: q[1]), water)
    return _LAYOUT[key]


def layout_text(w, width=2400):
    """STAGE LAYOUT of every place of world w (story units), plus the named world objects each scene can reach."""
    lines = [f"STAGE LAYOUT of every place (story units: x 0 = left edge ... {width} = right edge of the stage, "
             "z 0 = front, near the camera ... 1000 = back of the stage). Use it like a film director: stand people "
             "next to things (a little IN FRONT: z about 80 less than the thing), keep them clear of tall things, "
             "send them to a thing with \"to\": \"<id>\", and put the camera where what is behind the actors makes "
             "the shot (a tall thing at the back = a good background)."]
    for p in w.places:
        things, water = place_layout(p.get("place"), width)
        near = []
        for o in w.objects:
            got = to_story(o["at"], p["at"], math.radians(p.get("turn", 0.0) or 0.0), width)
            if got is not None:
                near.append(f'{o["id"]} x {got[0]:.0f} z {got[1]:.0f}')
        if not things and not water and not near:
            continue
        lines.append(f'  {p["id"]} ({p.get("place")}):')
        if water:
            lines.append(f"    water: {water}")
        if things:
            lines.append("    " + " · ".join(f"{i} x {x} z {z}{' ' + sz if sz else ''}{' (' + '/'.join(ab) + ')' if ab else ''}"
                                             for i, x, z, sz, ab in things))
        if near:
            lines.append("    world things in this scene: " + " · ".join(near))
    return "\n".join(lines)


def story_block(name, only=False):
    """The part of the story prompt that describes a world (the story must happen inside it)."""
    name, only_ = split_only(name)
    only = only or only_
    w = load(name)
    if w is None:
        return ""
    return (ONLY_RULES + "\n\n" if only else "") + f"""WORLD MAP: this story happens in the world "{w.name}". Put "map": "{w.name}" in "settings".
- Every scene says WHERE it is with "at": "<place id>" (or a named object id) instead of "background" (you may
  still add "background": {{"time": "night", "weather": "rain"}} for time / weather). Optional "look": "<place id>"
  = the camera looks toward that place (so it shows in the distance).
- Inside a scene, use the place's own objects (listed after each place) and the named objects close to it by id.
- Travel between places = a new scene at the other place (walk out of frame, cut, arrive).
{w.summary()}
{residents_text(w)}
{layout_text(w)}"""


def empty_world(name, title=None):
    """A blank 5 km map to build on in the World Explorer (click to add places and things)."""
    return {"world": _clean(name), "title": title or _clean(name).replace("_", " ").title(),
            "description": "", "size": [5000, 5000], "ground": "grass", "time": "day", "far": ["hills"],
            "places": [], "roads": [], "rivers": [], "areas": [], "objects": [], "edits": {}, "removed": []}


def parse_text(text):
    """World JSON from pasted text (plain JSON, or an AI answer with ```json fences and words around it)."""
    t = str(text or "").strip()
    try:
        spec = json.loads(t)
    except ValueError:
        from .ai import extract_json
        spec = extract_json(t)
    if not isinstance(spec, dict):
        raise ValueError("that is not a world: it must be one JSON object { ... }")
    return spec


def create(name, spec, force=False, overwrite=False):
    """Check + save a new world. -> (ok, problems, notes)."""
    name = _clean(name or spec.get("world") or "")
    if not name:
        raise ValueError("give the world a name (letters, numbers, _)")
    if os.path.exists(path_of(name)) and not overwrite:
        raise ValueError(f"a world called '{name}' already exists - pick another name")
    for k, v in (("places", []), ("roads", []), ("rivers", []), ("areas", []), ("objects", []), ("edits", {}),
                 ("removed", [])):
        spec.setdefault(k, v)
    spec.setdefault("size", [5000, 5000])
    probs, notes = World(spec, name).check()
    if probs and not force:
        return False, probs, notes, name
    save(name, spec)
    return True, probs, notes, name
