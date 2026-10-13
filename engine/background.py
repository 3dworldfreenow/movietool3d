"""Procedural backgrounds with parallax layers.

World coordinates are y-up with the ground at y = 0.  Each element lives on a
layer with a depth factor p (0 = infinitely far / fixed to screen, 1 = same
plane as the characters). The camera moves far layers less => parallax.
"""
import math

import cairo

from . import realworld as rw
from .util import hex_to_rgb, mix, darker, lighter, seeded, TAU, clamp, stable_hash
from .depth import p_of_z, lift_of_p, P_HORIZON
from .sizes import REAL as _SIZED
from .worlds import WorldsMixin, EXTRA_PRESETS, PRESET_ALIASES, INDOOR
from .places import PlacesMixin, PLACE_PRESETS, PLACE_ALIASES, PLACE_INDOOR
from .styles import StyleMixin
from .nature import NatureMixin, MORE_TREES, TIME_WORDS, canon_tree

SKIES = {
    "day": ("#62b3e6", "#d5f0fc"),
    "morning": ("#86c5ee", "#fde3c4"),
    "sunset": ("#4d3f84", "#ffc98a"),
    "evening": ("#3a4a8c", "#f6a67a"),
    "night": ("#070f29", "#223567"),
    "space": ("#02030a", "#0d1433"),
}
GROUNDS = {"grass": "#7cc15a", "dark_grass": "#4f8f3f", "road": "#6b6f76", "sand": "#ecd29a",
           "dirt": "#c49a6c", "snow": "#eef4f8", "wood": "#b07d4f", "tiles": "#d9d4c7", "stone": "#9a9a92"}

PRESETS = ("park", "street", "village", "forest", "mountains", "beach", "room", "classroom", "plain",
           "desert", "snow") + EXTRA_PRESETS + PLACE_PRESETS
EXTRA_TREES = ("banyan", "mango", "coconut", "banana_tree", "acacia", "cactus_tree", "bare", "blossom", "mushroom_tree")


class Camera:
    __slots__ = ("x", "y", "z", "sx", "sy", "d", "dh", "hor", "arc", "roll", "rev", "pov", "inside", "foc", "ap", "fg",
                 "blur", "aim", "lens", "dim", "bars", "orb", "yaw", "look", "bob", "sub", "keep")

    def __init__(self, x=960.0, y=345.0, z=1.0, sx=0.0, sy=0.0, d=0.0):
        self.x, self.y, self.z, self.sx, self.sy = x, y, z, sx, sy
        self.d = d          # 3D mode: depth (story z) of the subject the zoom refers to
        self.dh = 0.0       # 3D: camera height offset (crane up +, low angle -)
        self.hor = 0.5      # 3D: horizon position on screen (0 top .. 1 bottom): tilt up = larger
        self.arc = 0.0      # 3D: camera moved sideways around the subject (subject kept centred)
        self.roll = 0.0     # degrees (dutch angle, handheld)
        self.rev = None     # 3D reverse angle: depth pivot (story z) the scene is seen back across
        self.pov = None     # 3D point of view: character id whose eyes the camera uses
        self.inside = None  # 3D: vehicle id - the camera rides inside it
        self.foc = None     # focus pulled to this character (rack focus)
        self.sub = None     # the character the shot is about (kept sharp in 3D)
        self.keep = False   # 3D feature style: a long lens keeps the low / high / 3-4 angle
        self.ap = 0.0       # extra lens blur (aperture) for rack focus / dreamy shots
        self.blur = 0.0     # motion blur: screen px (1080p) the picture moved since the last frame
        self.aim = 0.0      # 3D: 0 = normal framing, 1 = the camera aims (tilts) at the subject (high / low angles)
        self.lens = 1.0     # 3D: focal length multiplier at the same subject size (2.5 telephoto, 0.6 wide-angle)
        self.dim = 0.0      # darker picture + vignette (dark_wide, "dark": 0.4)
        self.bars = 0.0     # cinema letterbox bars (0..1)
        self.orb = 0.0      # 3D page: true orbit around the subject (degrees, the camera really goes round)
        self.yaw = 0.0      # 3D page: the camera turns its head (degrees, + = to the right) - look around
        self.look = None    # point of view: who / what the eyes look at
        self.bob = 0.0      # point of view: walking head bob (0..1)
        self.fg = None      # soft foreground framing near the lens: {"kind", "side", "seed", "dx", "t"}


def set_layer(ctx, cam, p, W, H, S):
    ctx.identity_matrix()
    zp = 1.0 + (cam.z - 1.0) * p
    lcx = cam.x * p + (1.0 - p) * 960.0
    lcy = cam.y * p + (1.0 - p) * 345.0
    ctx.translate(W / 2 + cam.sx * S * p, H / 2 + cam.sy * S * p)
    ctx.scale(zp * S, -zp * S)
    ctx.translate(-lcx, -lcy)


# ---------------------------------------------------------------- back walls stay BEHIND the people
# the big building at the back of a place (a wall across the stage): nobody may stand behind it
BACKDROP_BUILDINGS = ("palace_building", "castle_building", "lm_school", "station_building", "hospital_building",
                      "police_building", "pandal")


def push_back_walls(bg, max_z, margin=120.0):
    """Characters / things go as deep as max_z (story depth): every back wall that is nearer than that moves
    back behind them (same look: only its depth changes). -> [(type, old z, new z)]"""
    from .depth import p_of_z, P_HORIZON
    moved = []
    want = min(1000.0, float(max_z) + margin)
    for e in getattr(bg, "elements", []):
        if e.get("type") not in BACKDROP_BUILDINGS or e.get("z") is not None:
            continue
        p = float(e.get("p", 1.0))
        z_now = (1.0 - p) / (1.0 - P_HORIZON) * 1000.0
        if z_now < want - 1:
            e["p"] = p_of_z(want)
            moved.append((e["type"], z_now, want))
    if moved:
        bg.elements.sort(key=lambda e: (e.get("layer") == "front", e.get("p", 1.0)))
    return moved


# what a planet place keeps of its visual template (engine/galaxy.py): land, water, rocks, sky - and plants only
# when the planet has life (recoloured by its palette)
PLANET_KEEP = ("hills", "mountains", "dunes", "rock", "rocks", "boulder", "stones", "crater", "sea", "lake", "river",
               "water", "shore", "waves", "ice", "snowdrift", "snow_mound", "cloud", "sun", "moon", "planet", "earth",
               "saturn", "sky_ring", "nebula", "solar", "hill_mound", "cliff", "puddle")
PLANET_LIFE = ("grass", "grass_tuft", "reeds", "tall_grass", "alien_plant")   # its trees are its own (alien_life.py)
EARTH_LIFE = ("tree", "bush", "grass", "grass_tuft", "flower", "flowers", "fern", "cactus", "palm", "reeds", "shrub",
              "pine", "vine", "banana", "plant", "tall_grass", "crop")             # the real Earth keeps its plants

# ---------------------------------------------------------------- 3D page: normal places -> their 3D code versions
PLACE3D_EXTRA = {"ghat": "river", "riverside": "river", "sea": "beach", "bus_stand": "street", "festival": "temple_fair",
                 "zoo": "park", "fields": "farm", "field": "farm", "snowy": "snow"}


def place3d_for(spec):
    """On the 3D page: the name of the real-3D code place for a scene background (village -> village_3d), or None.
    Keeps the scene as it is when it already uses a 3D place, a photo, an indoor room, or says "code3d": false."""
    if isinstance(spec, str):
        spec = {"preset": spec}
    if not isinstance(spec, dict) or spec.get("image") or spec.get("code3d") is False or spec.get("things"):
        return None
    raw = str(spec.get("preset", spec.get("type", "park"))).lower().strip().replace(" ", "_")
    if raw.endswith("_3d"):
        return None
    from . import registry
    canon = PLACE_ALIASES.get(raw) or PRESET_ALIASES.get(raw, raw)
    for cand in (raw, canon, PLACE3D_EXTRA.get(raw), PLACE3D_EXTRA.get(canon)):
        if not cand:
            continue
        got = registry.place(cand + "_3d")
        if got and got.get("made_by") == "code":
            return cand + "_3d"
    return None


def places3d():
    """{normal place: its 3D code place} for every 3D place in the library."""
    from . import registry
    out = {}
    for nm, sp in sorted(registry.load().get("places", {}).items()):
        if nm.endswith("_3d") and sp.get("made_by") == "code":
            out[nm[:-3]] = nm
    return out


class Background(WorldsMixin, PlacesMixin, StyleMixin, NatureMixin):
    def __init__(self, spec, world_w, seed=0):
        if isinstance(spec, str):
            spec = {"preset": spec}
        spec = dict(spec or {})
        raw = str(spec.get("preset", spec.get("type", "park"))).lower().strip().replace(" ", "_")
        from . import registry
        saved = registry.place(raw)                   # a place saved from the Studio
        if saved:
            merged = dict(saved)
            merged.update({k: v for k, v in spec.items() if k != "preset"})
            merged["elements"] = list(saved.get("elements", [])) + list(spec.get("elements", []))
            spec = merged
            raw = str(spec.get("preset", "park")).lower()
        from . import placegen
        self.place_objects, self.place_notes, self.place_missing = [], [], []
        if placegen.is_place_json(spec):                 # a place written as a list of things: arrange it
            comp = placegen.compile_place(spec, world_w, seed)
            spec = dict(comp["background"])
            self.place_objects, self.place_notes = comp["objects"], comp["notes"]
            self.place_missing = comp["missing"]
            raw = spec["preset"]
        self.spec = spec
        self.world_w = world_w
        self.preset_alias = "solar" if raw in ("solar", "solar_system") else raw
        if raw in PRESETS:
            self.preset = raw
        else:
            self.preset = PLACE_ALIASES.get(raw) or PRESET_ALIASES.get(raw, raw)
        if self.preset not in PRESETS:
            self.preset = "plain"
        self.time = str(spec.get("time", "day")).lower().strip().replace(" ", "_")
        self._time_sky = None
        if self.time in TIME_WORDS:                        # dawn, golden hour, dusk ... = a light + a sky look
            self.time, self._time_sky = TIME_WORDS[self.time]
        if self.time not in SKIES:
            self.time = "day"
        self.weather = str(spec.get("weather", "clear")).lower()
        self.rng = seeded(spec.get("seed", seed))
        self.indoor = self.preset in INDOOR or self.preset in PLACE_INDOOR or bool(spec.get("indoor"))
        self.wind = 1.0
        g = spec.get("ground")
        self.ground = GROUNDS.get(g) or (g if isinstance(g, str) and g.startswith("#") else None)
        self.elements = []
        self._style_init()
        from . import images as _img
        self.backdrop = None
        bimg = spec.get("image") or spec.get("backdrop")
        if bimg and _img.exists(bimg):
            meta = _img.info(bimg) or {}
            self.backdrop = {"name": bimg, "ground": float(spec.get("ground_line", spec.get("floor",
                             meta.get("ground") or 0.86))), "parallax": float(spec.get("parallax", 0.85))}
            self.indoor = bool(spec.get("indoor", self.indoor))
        elif bimg:
            self._warn_img = f"background image '{bimg}' not found in assets/images"
        if not spec.get("elements_only") and not self.backdrop:
            self._preset()
        if spec.get("planet_place"):                        # another planet (engine/galaxy.py): no village, no
            keep = PLANET_KEEP + ((EARTH_LIFE if spec.get("solar") else PLANET_LIFE) if spec.get("life") else ())      # people's things; plants only with life
            if spec.get("gas"):                             # a gas giant: no ground at all - clouds round a platform
                keep = ("cloud",)
            self.elements = [e for e in self.elements if e.get("layer") == "sky" or e["type"] in keep]
        extra = spec.get("sky_extra")                       # a planet's own sky (engine/galaxy.py): its star, moons, rings
        if isinstance(extra, list) and extra:
            if any(isinstance(e, dict) and e.get("type") == "sun" for e in extra):
                self.elements = [e for e in self.elements if e["type"] not in ("sun", "moon", "solar", "earth",
                                                                                "saturn", "planet")]
            for e in extra:
                if isinstance(e, dict) and e.get("type"):
                    kw = {k: v for k, v in e.items() if k not in ("type", "x", "p", "layer")}
                    self._add(e["type"], float(e.get("x", 0)), p=float(e.get("p", 0.03)), layer=e.get("layer", "sky"),
                              **kw)
        rd = spec.get("road") or spec.get("roads")
        if rd and not spec.get("_place_json"):                # "road": "near" / {"where": "middle", "style": "dirt"}
            from .placegen import road_element
            for r_ in (rd if isinstance(rd, list) else [rd]):
                re_ = road_element(r_)
                if re_:
                    spec.setdefault("elements", [])
                    spec["elements"] = list(spec["elements"]) + [re_]
        for el in spec.get("elements", []) or []:
            el = dict(el)
            if isinstance(el.get("size"), str):             # "size": "big" (tiny / small / medium / big / huge)
                from .sizes import word as _word
                el["sw"], el["size"] = _word(el["size"])
                if el.get("z") is None and el["size"] != 1.0:
                    el["scale"] = float(el.get("scale", 1.0)) * el["size"]
            elif el.get("sw") is None and el.get("z") is None and el.get("size") is not None:
                el["scale"] = float(el.get("scale", 1.0)) * float(el["size"])
            if el.get("z") is not None:                    # a thing at a real depth (like a character at that z)
                z = float(el["z"])
                p = p_of_z(z) if z <= 1000 else max(0.16, P_HORIZON * (1000.0 / z) ** 0.6)
                el["p"], el["layer"] = p, ("back" if z > 30 else "mid")
                # raised to where the ground is at that depth (applied when drawn - works for every drawing)
                el["_lift"] = lift_of_p(min(p, 1.0)) + ((P_HORIZON - p) * 420.0 if z > 1000 else 0.0)
                shrink = 1.0 if z <= 1000 else p / P_HORIZON
                depth_k = shrink * min(p, 1.0)            # on screen: real size x p, exactly like the 3D camera
                if el.get("ty"):
                    el["_ty2d"] = float(el["ty"]) * depth_k          # standing up on a hill
                el["scale"] = depth_k * (1.0 if el.get("type") in _SIZED else float(el.get("size", 1.0)))
                if el.get("type") == "image" and el.get("height"):
                    el["height"] = float(el["height"]) * depth_k
            el.setdefault("layer", "mid")
            el.setdefault("p", {"far": 0.35, "back": 0.7, "mid": 1.0, "front": 1.0}.get(el["layer"], 1.0))
            self.elements.append(el)
        self._apply_style()
        self._nature_setup()
        for el in self.elements:                           # {"type": "<image name>"} -> image element
            if el["type"] != "image" and not hasattr(self, "_d_" + el["type"]) and _img.exists(el["type"]):
                el["name"], el["type"] = el["type"], "image"
        self.elements.sort(key=lambda e: (e.get("layer") == "front", e["p"]))
        self._extra_setup()
        self.night = self.time == "night"
        self._real_sizes()                                  # needs the finished background (night, wind ...)
        self.hills = []                                     # walkable hills (story units) - timeline.ground_y
        for e in self.elements:
            if e["type"] == "hill_mound" and e.get("z") is not None:
                z = float(e["z"])
                p3_ = 1.0 - 0.58 * min(z, 1000.0) / 1000.0 if z <= 1000 else 0.42 * 1000.0 / (1000.0 + (z - 1000) * 4 * 0.42)
                self.hills.append(dict(xc=float(e["x"]), zc=z, a=float(e.get("w", 3000)) / 2.0 * p3_,
                                       b=float(e.get("depth", 260)), H=float(e.get("h", 900)),
                                       top=float(e.get("top", 0.2)), p=p_of_z(min(z, 1000.0))))

    # ----------------------------------------------------------------- real sizes (engine/sizes.py)
    def _real_sizes(self):
        """Every hut, house, tree ... is drawn at its REAL height next to a person (adult = 300), with its size
        word (tiny .. huge). The factor is applied when it is drawn (the 3D world uses its own real scale)."""
        from . import sizes
        from .world3d import drawn_height
        for e in self.elements:
            typ = e["type"]
            if e.get("layer") in ("far", "sky", "front") or typ not in sizes.REAL or typ == "hill_mound":
                continue                                    # (a hill is drawn at its own given size)
            kind = e.get("kind") if typ == "tree" else None
            rh = sizes.real_height(typ, kind, e.get("sw") or "medium")
            dh = drawn_height(self, typ, kind)
            if rh and dh and dh > 20:
                rf = rh / dh * float(e.get("size", 1.0) if e.get("z") is not None else 1.0)
                if e.get("z") is None:
                    # 2D layers: further back = smaller on screen (like the real 3D camera: size x p)
                    p = float(e.get("p", 1.0))
                    rf *= p if p < 0.999 else 1.0
                    if p >= 0.999 and sizes.FAMILY.get(typ) == "tree":
                        rf *= 0.7          # a stage-side tree: keep its crown in the frame
                    elif p >= 0.999 and sizes.FAMILY.get(typ) in ("house", "temple"):
                        rf *= 0.72         # houses on the main row stand a few metres behind the people
                e["_rf"] = rf

    @staticmethod
    def _real(ctx, e):
        if e.get("_ty2d"):
            ctx.translate(0, e["_ty2d"])
        rf = e.get("_rf")
        if rf and abs(rf - 1.0) > 0.01:
            x, y = float(e.get("x", 0)), float(e.get("y", 0) or 0)
            ctx.translate(x, y)
            ctx.scale(rf, rf)
            ctx.translate(-x, -y)

    # ----------------------------------------------------------------- composition
    def _add(self, typ, x, p=1.0, layer="mid", **kw):
        self.elements.append(dict(type=typ, x=x, p=p, layer=layer, **kw))

    def _preset(self):
        r, W = self.rng, self.world_w
        pr = self.preset
        if pr in EXTRA_PRESETS:
            return self._preset_extra(pr)
        if pr in PLACE_PRESETS:
            return self._preset_place(pr)
        if not self.indoor:
            self._add("sun" if self.time != "night" else "moon", 1480, p=0.02, layer="sky")
            for k in range(7):
                self._add("cloud", r.uniform(-400, 2600), p=0.08, layer="sky", y=r.uniform(560, 820),
                          scale=r.uniform(0.6, 1.2), speed=r.uniform(4, 12))
        if pr == "park":
            self.ground = self.ground or GROUNDS["grass"]
            self._add("hills", 0, p=0.35, layer="far", color="#9fd07a", seed=r.random())
            for x in range(-500, int(W * 0.7) + 900, 170):
                self._add("tree", x + r.uniform(-50, 50), p=0.62, layer="back", kind="round",
                          scale=r.uniform(0.55, 0.8), color="#5fa84a")
            for x in range(-200, int(W) + 400, 520):
                self._add("tree", x + r.uniform(-90, 90), kind=r.choice(["round", "round", "pine"]),
                          scale=r.uniform(0.95, 1.25))
            self._add("bench", W * 0.5 + 330)
            self._front_grass(flowers=True)
        elif pr == "street":
            self.ground = self.ground or GROUNDS["road"]
            for x in range(-700, int(W * 0.6) + 1200, 150):
                self._add("building", x, p=0.5, layer="far", w=r.uniform(110, 150), h=r.uniform(260, 520),
                          color=r.choice(["#8d99ae", "#7b8ba3", "#a3b1c6", "#6c7a93"]))
            colors = ["#e76f51", "#f4a261", "#2a9d8f", "#e9c46a", "#8ab17d", "#b56576"]
            for i, x in enumerate(range(-300, int(W) + 500, 430)):
                if r.random() < 0.5:
                    self._add("house", x, color=colors[i % len(colors)], scale=r.uniform(0.95, 1.15), y=40)
                else:
                    self._add("shop", x, color=colors[(i + 2) % len(colors)], y=40)
            for x in range(-100, int(W) + 300, 640):
                self._add("lamp", x + 200)
            self._add("sidewalk", 0)
        elif pr == "village":
            self.ground = self.ground or GROUNDS["dirt"]
            self._add("hills", 0, p=0.3, layer="far", color="#a7c77f", seed=r.random())
            self._add("mountains", 0, p=0.15, layer="far", color="#8fa7c0", seed=r.random())
            for x in range(-400, int(W) + 500, 210):
                self._add("tree", x + r.uniform(-60, 60), p=0.65, layer="back", kind="round",
                          scale=r.uniform(0.5, 0.75), color="#6fae55")
            for x in range(-200, int(W) + 300, 700):
                self._add("hut", x + r.uniform(-60, 60), scale=r.uniform(0.95, 1.15))
                self._add("tree", x + 320, kind=r.choice(["round", "palm"]), scale=r.uniform(1.0, 1.25))
            self._add("well", W * 0.5 + 250)
            self._add("fence", -600, x2=W + 600, p=0.85, layer="back")
            self._front_grass()
        elif pr == "forest":
            self.ground = self.ground or GROUNDS["dark_grass"]
            self._add("mountains", 0, p=0.15, layer="far", color="#7c9bb5", seed=r.random())
            for p, col, sc, step in ((0.4, "#2f6b4f", 0.55, 90), (0.62, "#2a7a45", 0.75, 130)):
                for x in range(-700, int(W) + 900, step):
                    self._add("tree", x + r.uniform(-30, 30), p=p, layer="back", kind="pine",
                              scale=sc * r.uniform(0.85, 1.2), color=col)
            for x in range(-300, int(W) + 400, 330):
                self._add("tree", x + r.uniform(-80, 80), kind=r.choice(["pine", "pine", "round"]),
                          scale=r.uniform(1.1, 1.5), color="#1f6e3a")
            self._add("rock", W * 0.35, scale=0.8)
            self._front_grass(mushrooms=True)
        elif pr == "mountains":
            self.ground = self.ground or GROUNDS["grass"]
            self._add("mountains", 0, p=0.12, layer="far", color="#8aa0bd", seed=r.random(), big=True)
            self._add("mountains", 0, p=0.3, layer="far", color="#6d8aa8", seed=r.random())
            for x in range(-300, int(W) + 400, 420):
                self._add("tree", x + r.uniform(-120, 120), kind="pine", scale=r.uniform(0.9, 1.3), color="#2d6a4f")
            for x in range(-100, int(W), 700):
                self._add("rock", x + r.uniform(0, 300), scale=r.uniform(0.6, 1.1))
            self._front_grass()
        elif pr == "beach":
            self.ground = self.ground or GROUNDS["sand"]
            self._add("sea", 0, p=0.3, layer="far")
            for x in range(-100, int(W) + 300, 800):
                self._add("tree", x + r.uniform(-100, 100), kind="palm", scale=r.uniform(1.0, 1.25))
            self._add("umbrella", W * 0.5 + 380)
        elif pr == "desert":
            self.ground = self.ground or GROUNDS["sand"]
            self._add("dunes", 0, p=0.3, layer="far")
            for x in range(-100, int(W), 600):
                self._add("cactus", x + r.uniform(0, 300), scale=r.uniform(0.8, 1.2))
        elif pr == "snow":
            self.ground = self.ground or GROUNDS["snow"]
            self._add("mountains", 0, p=0.15, layer="far", color="#b8c7d9", seed=r.random(), big=True)
            for x in range(-300, int(W) + 400, 360):
                self._add("tree", x + r.uniform(-90, 90), kind="pine", scale=r.uniform(0.9, 1.3), color="#2d5a4a", snow=True)
            if self.weather == "clear" and "weather" not in self.spec:
                self.weather = "snow"
        elif pr == "room":
            self.ground = self.ground or GROUNDS["wood"]
            self._add("wall", 0, color=self.spec.get("wall", "#f1e3c8"))
            self._add("ceiling", 0)
            if self.spec.get("fan", True):
                self._add("fan", W * 0.5 - 150)
            if self.spec.get("tv"):
                self._add("tv", W * 0.5 - 450, y=120)
            for x in range(200, int(W), 900):
                self._add("window", x)
            self._add("door", W - 260)
            self._add("picture", W * 0.5 - 60)
            self._add("lamp_floor", 120)
            self._add("sofa", W * 0.5 + 330)
        elif pr == "classroom":
            self.ground = self.ground or GROUNDS["tiles"]
            self._add("wall", 0, color=self.spec.get("wall", "#dfe9e3"))
            self._add("ceiling", 0)
            if self.spec.get("fan", True):
                self._add("fan", W * 0.5 - 700)
                self._add("fan", W * 0.5 + 700)
            self._add("board", W * 0.5)
            self._add("window", 150)
            self._add("door", W - 200)
            self._add("clock", W * 0.5 + 460)
            for x in range(-200, int(W) + 200, 380):
                self._add("desk", x, layer="front", p=1.0, y=-110)
        else:  # plain
            self.ground = self.ground or GROUNDS["grass"]
            self._add("hills", 0, p=0.35, layer="far", color="#a5d58a", seed=r.random())
        if self.ground is None:
            self.ground = GROUNDS["grass"]

    def _front_grass(self, flowers=False, mushrooms=False):
        r, W = self.rng, self.world_w
        for x in range(-600, int(W) + 700, 95):
            if r.random() < 0.55:
                self._add("grass", x + r.uniform(-40, 40), layer="front", y=-r.uniform(25, 150),
                          scale=r.uniform(0.7, 1.3))
            if flowers and r.random() < 0.18:
                self._add("flower", x + r.uniform(-40, 40), layer="front", y=-r.uniform(40, 150),
                          color=r.choice(["#ff6b6b", "#ffd166", "#f9f7f3", "#c77dff"]))
            if mushrooms and r.random() < 0.06:
                self._add("mushroom", x, layer="front", y=-r.uniform(40, 140))

    # ----------------------------------------------------------------- surfaces
    def seat_at(self, x, scale=1.0):
        """Is there furniture to sit/lie on near x? -> ('seat'|'bed', height) or None."""
        for e in self.elements:
            if e["p"] != 1.0:
                continue
            if e["type"] in ("bench", "sofa") and abs(e["x"] - x) < 130 * e.get("scale", 1):
                return ("seat", 64)
            if e["type"] == "bed" and abs(e["x"] - x) < 170 * e.get("scale", 1):
                return ("bed", 62 * e.get("scale", 1))
        return None

    # ----------------------------------------------------------------- drawing
    def draw_sky(self, ctx, W, H, t, cam):
        ctx.identity_matrix()
        top, bot = SKIES[self.time]
        top, bot = hex_to_rgb(top), hex_to_rgb(bot)
        mid = hex_to_rgb("#e9799a") if (self.time == "sunset" and self.weather == "clear") else None
        look = self.sky_colors() if self.time != "space" else None
        if look:
            top, mid, bot = look
        wx = getattr(self, "wx", None)
        if wx is not None and wx.get("changing") and self.time != "space":
            k = clamp(0.62 * max(0.0, wx["cloud"] - 0.15) / 0.85 + 0.15 * wx["storm"], 0.0, 0.7)
            fogk = wx["fog"]
            grey = mix((0.3, 0.33, 0.38), (0.78, 0.8, 0.82), fogk)       # clouds gather: the sky greys
            k = max(k, 0.4 * fogk)
            top, bot = mix(top, grey, k), mix(bot, mix((0.55, 0.58, 0.6), (0.86, 0.87, 0.88), fogk), k)
            mid = mix(mid, grey, k) if mid else None
        elif self.weather in ("rain", "storm", "cyclone", "overcast", "cloudy", "fog", "mist", "foggy") \
                and self.time != "space":
            k = {"cyclone": 0.65, "overcast": 0.45, "cloudy": 0.35, "fog": 0.4, "mist": 0.35, "foggy": 0.4}.get(
                self.weather, 0.5)
            grey = (0.3, 0.33, 0.38) if self.weather not in ("fog", "mist", "foggy") else (0.78, 0.8, 0.82)
            top, bot = mix(top, grey, k), mix(bot, (0.55, 0.58, 0.6) if grey[0] < 0.5 else (0.86, 0.87, 0.88), k)
            mid = mix(mid, grey, k) if mid else None
        g = cairo.LinearGradient(0, 0, 0, H * 0.85)
        g.add_color_stop_rgb(0, *top)
        if mid:
            g.add_color_stop_rgb(0.55, *mid)
        g.add_color_stop_rgb(1, *bot)
        ctx.set_source(g)
        ctx.paint()
        self.draw_sky_extras(ctx, W, H, t)
        if wx is not None and wx.get("rainbow", 0) > 0.01:     # after the rain, opposite the sun
            from .weatherline import draw_rainbow
            from .realworld import sun as _sun
            draw_rainbow(ctx, W, H, wx["rainbow"], _sun(self.time)["side"])
        if self.time == "space":
            rr = seeded(9)
            for k in range(320):
                x, y = rr.uniform(0, W), rr.uniform(0, H)
                tw = 0.6 + 0.4 * math.sin(t * rr.uniform(1, 3) + k)
                ctx.set_source_rgba(1, 1, rr.uniform(0.8, 1), 0.95 * tw)
                ctx.arc(x, y, rr.uniform(0.6, 2.4) * H / 1080, 0, TAU)
                ctx.fill()
        elif self.night:
            rr = seeded(7)
            for k in range(130):
                x, y = rr.uniform(0, W), rr.uniform(0, H * 0.62)
                tw = 0.55 + 0.45 * math.sin(t * rr.uniform(1, 3) + k)
                ctx.set_source_rgba(1, 1, 0.9, 0.9 * tw)
                ctx.arc(x, y, rr.uniform(0.8, 2.2) * H / 1080, 0, TAU)
                ctx.fill()

    def draw_back(self, ctx, cam, t, W, H, S):
        self._t = t
        self.draw_sky(ctx, W, H, t, cam)
        ground_drawn = False
        if self.backdrop:
            self._draw_backdrop(ctx, cam, W, H, S)
            ground_drawn = True
        for e in self.elements:
            if e["layer"] == "front":
                continue
            if e["p"] >= 1.0 and not ground_drawn:
                self._ground(ctx, cam, W, H, S)
                ground_drawn = True
            set_layer(ctx, cam, e["p"], W, H, S)
            fn = getattr(self, "_d_" + e["type"], None)
            if fn:
                ctx.save()
                if e.get("_lift"):
                    ctx.translate(0, e["_lift"])
                self._real(ctx, e)
                fn(ctx, e, t)
                ctx.restore()
        if not ground_drawn:
            self._ground(ctx, cam, W, H, S)

    # ================================================================== real images
    def _d_hill_mound(self, ctx, e, t):
        """A hill standing on the ground (place JSON "hill"): grassy (or dry / rocky / snowy) mound with a flat top,
        drawn at its real size; people climb it, things stand on it."""
        s = float(e.get("scale", 1.0))
        x = e["x"]
        H, a, top = float(e.get("h", 900)) * s, float(e.get("w", 3000)) * s / 2.0, float(e.get("top", 0.2))
        style = str(e.get("style", "grass")).lower()
        base = {"grass": "#6fb24c", "dry": "#b9a06a", "rocky": "#8f8a7e", "snow": "#e9f0f5", "sand": "#dcbf86",
                "forest": "#4d8a3c"}.get(style, style if style.startswith("#") else "#6fb24c")
        if style == "grass" and self.ground:
            base = self.ground if isinstance(self.ground, str) else base
        col = self._shade(hex_to_rgb(base) if isinstance(base, str) else base)
        n = 48
        pts = []
        for k in range(n + 1):
            u = -1.0 + 2.0 * k / n
            au = abs(u)
            f = 1.0 if au < top else math.cos(math.pi / 2 * (au - top) / (1.0 - top)) ** 2
            pts.append((x + u * a, H * f))
        ctx.move_to(x - a, -2)
        for q in pts:
            ctx.line_to(*q)
        ctx.line_to(x + a, -2)
        ctx.close_path()
        g = cairo.LinearGradient(0, H, 0, 0)
        g.add_color_stop_rgb(0, *lighter(col, 0.12))
        g.add_color_stop_rgb(1, *darker(col, 0.86))
        ctx.set_source(g)
        ctx.fill()
        # sunny side + a few tufts / rocks for texture
        ctx.set_source_rgba(1, 1, 1, 0.08)
        ctx.move_to(x - a * 0.2, H)
        for q in pts[n // 2 - n // 10: n // 2 + n // 3]:
            ctx.line_to(q[0], q[1] - 6 * s)
        ctx.line_to(x - a * 0.2, H * 0.3)
        ctx.close_path()
        ctx.fill()
        rr = seeded(int(x) + 3)
        tuft = darker(col, 0.75)
        for _ in range(int(14 + a / 120)):
            u = rr.uniform(-0.9, 0.9)
            au = abs(u)
            f = 1.0 if au < top else math.cos(math.pi / 2 * (au - top) / (1.0 - top)) ** 2
            yy = H * f * rr.uniform(0.15, 0.95)
            if style == "rocky" or rr.random() < 0.2:
                ctx.set_source_rgba(*self._shade("#8a857b"), 0.9)
                ctx.save()
                ctx.translate(x + u * a, yy)
                ctx.scale(rr.uniform(18, 34) * s ** 0.5, rr.uniform(10, 18) * s ** 0.5)
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.restore()
                ctx.fill()
            else:
                ctx.set_source_rgba(*tuft, 0.55)
                ctx.set_line_width(3)
                for d in (-6, 0, 6):
                    ctx.move_to(x + u * a + d, yy)
                    ctx.line_to(x + u * a + d * 1.6, yy + 14)
                ctx.stroke()
        if e.get("trail"):                                     # a footpath winding up to the top
            ctx.set_source_rgba(*self._shade("#d8c7a0"), 0.9)
            ctx.set_line_width(max(6.0, 26 * s ** 0.5))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.move_to(x - a * 0.85, 4)
            ctx.curve_to(x - a * 0.2, H * 0.25, x - a * 0.6, H * 0.6, x - a * 0.05, H * 0.97)
            ctx.stroke()

    def _d_road_band(self, ctx, e, t):
        """A road across the place (2D look): a flat band on the ground between depths z0 and z1."""
        from .world3d import ROAD_COLORS
        z0, z1 = float(e.get("z0", 0)), float(e.get("z1", e.get("z", 200)))
        base = float(e.get("_lift", 0.0) or 0.0)
        y_far = lift_of_p(p_of_z(z1)) - base
        y_near = lift_of_p(p_of_z(z0)) - base
        th = max(42.0, y_far - y_near)
        top = y_far + 4
        style = str(e.get("style", "tar")).lower()
        col = self._shade(hex_to_rgb(ROAD_COLORS.get(style, ROAD_COLORS["tar"])))
        W = self.world_w
        ctx.set_source_rgb(*col)
        ctx.rectangle(-4000, top - th, W + 8000, th)
        ctx.fill()
        if style in ("tar", "road", "highway"):
            ctx.set_source_rgba(0.93, 0.93, 0.9, 0.85)
            ctx.rectangle(-4000, top - 5, W + 8000, 3)
            ctx.rectangle(-4000, top - th + 2, W + 8000, 3)
            ctx.fill()
            ctx.set_source_rgba(0.98, 0.9, 0.35, 0.9)
            for x in range(-4000, int(W) + 4000, 180):
                ctx.rectangle(x, top - th / 2 - 2, 95, 4)
            ctx.fill()

    def _d_image(self, ctx, e, t):
        from . import images
        name = e.get("name") or e.get("image")
        if not name:
            return
        bob = float(e.get("bob", 0)) * math.sin(t * 2.0 + e["x"] * 0.01)
        images.draw(ctx, name, e["x"], float(e.get("y", 0)) + bob, e.get("height"), bool(e.get("flip")),
                    float(e.get("alpha", 1.0)), t=t, turn=float(e.get("turn") or 0),
                    **images.anim_opts(e, default_phase=(e["x"] % 997) * 0.003))

    def _draw_backdrop(self, ctx, cam, W, H, S):
        """A real picture as the whole background; its floor line sits on the ground (y = 0)."""
        from . import images
        bd = self.backdrop
        sp = self.spec
        got = images.surface(bd["name"], getattr(self, "_t", 0.0), float(sp.get("image_speed", sp.get("speed", 1.0))),
                             sp.get("image_loop", "loop"))
        if not got:
            return
        w, h = got[1], got[2]
        p = bd["parallax"]
        g = min(max(bd["ground"], 0.3), 0.97)
        # height: enough picture above the floor line for the sky (~950 units) and below it for the floor
        dh = max(950.0 / g, 260.0 / (1.0 - g)) * float(self.spec.get("image_zoom", 1.0))
        sc = dh / h
        set_layer(ctx, cam, p, W, H, S)
        dw = w * sc
        x0 = self.world_w / 2 - dw / 2
        top = g * dh                                # world y of the image top edge
        ctx.save()
        ctx.translate(x0, top)
        ctx.scale(sc, -sc)
        pat = cairo.SurfacePattern(got[0])
        pat.set_filter(cairo.FILTER_GOOD)
        pat.set_extend(cairo.EXTEND_REFLECT)        # wide scenes: the picture continues mirrored
        ctx.set_source(pat)
        ctx.rectangle(-w * 4, -h, w * 9, h * 3)
        ctx.fill()
        ctx.restore()

    # ================================================================== 2.5D depth drawing
    WALL_TYPES = ("wall", "ceiling", "tiles_wall", "window", "door", "picture", "board", "clock", "cabinet",
                  "lamp_floor", "bookshelf", "wardrobe", "tv")

    def haze_color(self):
        if self.indoor:
            return (0.55, 0.55, 0.6)
        return hex_to_rgb(SKIES.get(self.time, SKIES["day"])[1])

    def _depth_p(self, e):
        from .depth import P_HORIZON
        if self.indoor and e["type"] in self.WALL_TYPES and e["p"] >= 0.99:
            return P_HORIZON + 0.0005           # the wall stands at the back of the room; the floor recedes
        return e["p"]

    def _device_y(self, ctx, cam, p, y, W, H, S):
        set_layer(ctx, cam, p, W, H, S)
        return ctx.user_to_device(0, y)[1]

    def _perspective_band(self, ctx, cam, W, H, S, t):
        """The walkable ground between the front line (z=0) and the horizon (z=1000), drawn in perspective."""
        from .depth import P_HORIZON, lift_of_p
        yh = self._device_y(ctx, cam, P_HORIZON, lift_of_p(P_HORIZON), W, H, S)
        yf = self._device_y(ctx, cam, 1.0, 0.0, W, H, S)
        if yf - yh < 2:
            return
        haze = self.haze_color()
        water_all = self.water and self.shore_x is None
        if water_all:
            from .styles import WATER_COL
            base = self._shade(hex_to_rgb(WATER_COL.get(self.water, WATER_COL["sea"])[0]))
        else:
            base = self._shade(self.ground or GROUNDS["grass"])
        ctx.identity_matrix()
        g = cairo.LinearGradient(0, yh, 0, yf)
        g.add_color_stop_rgb(0, *mix(base, haze, 0.45))
        g.add_color_stop_rgb(1, *base)
        ctx.set_source(g)
        ctx.rectangle(-10, yh - 1, W + 20, yf - yh + 2)
        ctx.fill()
        # rows that get closer together toward the horizon (fields, tiles, wave lines)
        n = 9
        for i in range(1, n):
            u = (i / n) ** 1.8
            p = P_HORIZON + (1.0 - P_HORIZON) * u
            y = self._device_y(ctx, cam, p, lift_of_p(p), W, H, S)
            ctx.identity_matrix()
            if water_all:
                ctx.set_source_rgba(1, 1, 1, 0.12 + 0.12 * u)
                ctx.set_line_width(max(1.0, 3 * u * S))
                span = 160 * (0.4 + u)
                off = (t * 30 * (0.4 + u)) % span
                x = -span + off
                while x < W + span:
                    ctx.move_to(x, y)
                    ctx.curve_to(x + span * 0.15, y + 3 * u, x + span * 0.3, y + 3 * u, x + span * 0.45, y)
                    x += span
                ctx.stroke()
            else:
                ctx.set_source_rgba(*darker(base, 0.8), 0.10 + 0.08 * u)
                ctx.rectangle(-10, y, W + 20, max(1.0, 3.5 * u * S))
                ctx.fill()
        # part land / part water: water band on the water side of the shore line
        if self.water and self.shore_x is not None:
            from .styles import WATER_COL
            wcol = self._shade(hex_to_rgb(WATER_COL.get(self.water, WATER_COL["sea"])[0]))
            set_layer(ctx, cam, 1.0, W, H, S)
            xf = ctx.user_to_device(self.shore_x, 0)[0]
            set_layer(ctx, cam, P_HORIZON, W, H, S)
            xh = ctx.user_to_device(self.shore_x, lift_of_p(P_HORIZON))[0]
            ctx.identity_matrix()
            edge = W + 20 if self.land_side == "left" else -20
            ctx.move_to(xh, yh)
            ctx.line_to(edge, yh)
            ctx.line_to(edge, yf)
            ctx.line_to(xf, yf)
            ctx.close_path()
            gw = cairo.LinearGradient(0, yh, 0, yf)
            gw.add_color_stop_rgb(0, *mix(wcol, haze, 0.4))
            gw.add_color_stop_rgb(1, *wcol)
            ctx.set_source(gw)
            ctx.fill()

    def draw_back_depth(self, ctx, cam, t, W, H, S, inserts=(), elements_only=False):
        """Background with real depth ordering. inserts: [(p, fn)] - characters/vehicles drawn between the
        background layers at their own depth, so near trees hide them and far trees are hidden by them."""
        from .depth import P_HORIZON, lift_of_p
        self._t = t
        self.draw_sky(ctx, W, H, t, cam)
        items = []
        for i, e in enumerate(self.elements):
            if e["layer"] == "front":
                continue
            p = self._depth_p(e)
            if p < P_HORIZON:
                set_layer(ctx, cam, p, W, H, S)
                fn = getattr(self, "_d_" + e["type"], None)
                if fn:
                    ctx.save()
                    if e.get("_lift"):
                        ctx.translate(0, e["_lift"])
                    self._real(ctx, e)
                    fn(ctx, e, t)
                    ctx.restore()
            else:
                items.append((p, 0, i, e))
        if self.backdrop:
            self._draw_backdrop(ctx, cam, W, H, S)
        else:
            self._ground(ctx, cam, W, H, S)
            self._perspective_band(ctx, cam, W, H, S, t)
        if not elements_only:
            for j, (p, fn) in enumerate(inserts):
                items.append((p, 1, j, fn))
        items.sort(key=lambda it: (it[0], it[1], it[2]))
        for p, kind, _, obj in items:
            if kind == 1:
                obj()
                continue
            set_layer(ctx, cam, p, W, H, S)
            ctx.translate(0, lift_of_p(p))
            fn = getattr(self, "_d_" + obj["type"], None)
            if fn:
                ctx.save()
                self._real(ctx, obj)
                fn(ctx, obj, t)
                ctx.restore()

    def draw_front(self, ctx, cam, t, W, H, S):
        for e in self.elements:
            if e["layer"] != "front":
                continue
            set_layer(ctx, cam, e["p"], W, H, S)
            fn = getattr(self, "_d_" + e["type"], None)
            if fn:
                ctx.save()
                self._real(ctx, e)
                fn(ctx, e, t)
                ctx.restore()

    def draw_weather(self, ctx, t, W, H):
        ctx.identity_matrix()
        k = H / 1080
        wnd = rw.wind()                                  # one wind: streaks, rain and snow all go its way
        d, ws = wnd.direction, wnd.strength
        if self.weather in ("cyclone", "windy", "wind") or ws >= 2.5:
            rr = seeded(13)
            n = 70 if self.weather == "cyclone" else 30
            for i in range(n):
                sp = rr.uniform(700, 1500) * (1.5 if self.weather == "cyclone" else 0.8) * (0.6 + 0.4 * ws / 2.8)
                x = (rr.uniform(0, W) + d * t * sp * (1.0 + 0.5 * wnd.gust(t, i * 40.0))) % (W + 200) - 100
                y = (rr.uniform(0, H) + 40 * math.sin(t * 3 + i)) % H
                if i % 3 == 0:
                    ctx.set_source_rgba(0.9, 0.9, 0.95, 0.35)
                    ctx.set_line_width(2 * k)
                    ctx.move_to(x, y)
                    ctx.line_to(x - d * 90 * k, y - 6 * k)
                    ctx.stroke()
                else:
                    ctx.save()
                    ctx.translate(x, y)
                    ctx.rotate(t * rr.uniform(4, 9))
                    ctx.scale(9 * k, 4 * k)
                    ctx.arc(0, 0, 1, 0, TAU)
                    ctx.restore()
                    ctx.set_source_rgba(*rr.choice([(0.4, 0.6, 0.2), (0.7, 0.5, 0.2), (0.5, 0.4, 0.3)]), 0.85)
                    ctx.fill()
        wx = getattr(self, "wx", None)
        rain_n = 160 if self.weather in ("rain", "storm", "cyclone") else 0
        if wx is not None and wx.get("changing"):        # the first drops, heavier, then fewer as it stops
            rain_n = int(160 * wx["rain"])
        if getattr(self, "_rain3d", False):
            rain_n = 0
        if rain_n > 0:
            rr = seeded(3)
            ctx.set_source_rgba(0.8, 0.85, 1.0, 0.55)
            ctx.set_line_width(2 * k)
            for i in range(rain_n):
                x0, sp = rr.uniform(-100, W + 100), rr.uniform(1100, 1500)
                y = (rr.uniform(0, H) + t * sp) % (H + 60) - 30
                slant = clamp(0.06 + 0.1 * ws, 0.0, 0.75) * d   # rain slants with the wind
                x = x0 + y * slant
                ctx.move_to(x, y)
                ctx.line_to(x + 30 * k * slant, y + 30 * k)
            ctx.stroke()
            if self.weather in ("storm", "cyclone") and (t % 6.0) < 0.12:
                ctx.set_source_rgba(1, 1, 1, 0.55)
                ctx.paint()
        snow_n = 140 if self.weather == "snow" else 0
        if wx is not None and wx.get("changing"):
            snow_n = int(140 * wx["snow"])
        if snow_n > 0 and rain_n <= 0:
            rr = seeded(5)
            ctx.set_source_rgba(1, 1, 1, 0.9)
            for i in range(snow_n):
                x0, sp, rad_ = rr.uniform(0, W), rr.uniform(40, 110), rr.uniform(2, 5)
                y = (rr.uniform(0, H) + t * sp) % (H + 20) - 10
                x = (x0 + d * t * 22 * ws + 25 * math.sin(t * 0.8 + i)) % W      # snow drifts downwind
                ctx.arc(x, y, rad_ * k, 0, TAU)
                ctx.fill()

    def tint(self, ctx, W, H):
        ctx.identity_matrix()
        if self.night:
            ctx.set_source_rgba(0.05, 0.08, 0.25, 0.28)
            ctx.paint()
        elif self.time == "sunset":
            ctx.set_source_rgba(1.0, 0.45, 0.2, 0.08)
            ctx.paint()
        elif getattr(self, "wx", None) is not None and self.wx.get("changing"):
            if self.wx["rain"] > 0.01:                     # darker as the rain gets heavier (no sudden step)
                ctx.set_source_rgba(0.2, 0.25, 0.3, 0.18 * self.wx["rain"] + 0.08 * self.wx["storm"])
                ctx.paint()
        elif self.weather in ("rain", "storm", "cyclone"):
            ctx.set_source_rgba(0.2, 0.25, 0.3, 0.26 if self.weather == "cyclone" else 0.18)
            ctx.paint()
        self._mood_tint(ctx, W, H)

    def _shade(self, c):
        c = hex_to_rgb(c) if isinstance(c, str) else c
        from . import palette as _palette
        if _palette.CURRENT[0] is not None:            # a world palette: far trees, bushes, hills in its colours
            c = _palette.one(c)
        if self.night:
            return mix(c, (0.1, 0.13, 0.28), 0.45)
        if self.time == "sunset":
            return mix(c, (0.95, 0.55, 0.4), 0.12)
        return c

    def _ground(self, ctx, cam, W, H, S):
        self._ground_plain(ctx, cam, W, H, S)
        wx = getattr(self, "wx", None)
        if wx is not None and wx.get("changing") and wx.get("snow_cover", 0) > 0.01:
            ctx.save()                                   # snow settling on the ground (engine/weatherline.py)
            set_layer(ctx, cam, 1.0, W, H, S)
            gy = ctx.user_to_device(0, 0)[1]
            ctx.identity_matrix()
            g_ = cairo.LinearGradient(0, gy - 4 * S, 0, H)
            g_.add_color_stop_rgba(0, 0.95, 0.97, 1.0, 0.0)
            g_.add_color_stop_rgba(0.06, 0.95, 0.97, 1.0, 0.85 * wx["snow_cover"])
            g_.add_color_stop_rgba(1, 0.9, 0.93, 0.98, 0.75 * wx["snow_cover"])
            ctx.set_source(g_)
            ctx.rectangle(0, gy - 4 * S, W, H - gy + 4 * S)
            ctx.fill()
            ctx.restore()

    def _ground_plain(self, ctx, cam, W, H, S):
        set_layer(ctx, cam, 1.0, W, H, S)
        g = self._shade(self.ground or GROUNDS["grass"])
        x0, x1 = -3000, self.world_w + 3000
        if self.water:
            t = getattr(self, "_t", 0.0)
            if self.shore_x is None:
                self._draw_water_ground(ctx, x0, x1, t)
                return
            lx0, lx1 = (x0, self.shore_x) if self.land_side == "left" else (self.shore_x, x1)
            wx0, wx1 = (self.shore_x, x1) if self.land_side == "left" else (x0, self.shore_x)
            self._draw_water_ground(ctx, wx0, wx1, t)
            ctx.set_source_rgb(*g)
            ctx.rectangle(lx0, -3000, lx1 - lx0, 3000)
            ctx.fill()
            return
        ctx.set_source_rgb(*g)
        ctx.rectangle(x0, -3000, x1 - x0, 3000)
        ctx.fill()
        if not self.indoor and self.preset != "space" and self.spec.get("ground_paint", True) is not False:
            self._ground_patches(ctx, g, x0, x1)
        ctx.set_source_rgb(*darker(g, 0.88))
        ctx.rectangle(x0, -6, x1 - x0, 6)
        ctx.fill()
        if self.preset == "space":
            rr = seeded(4)
            for k in range(60):
                cx, cy = rr.uniform(-2000, self.world_w + 2000), rr.uniform(-190, -20)
                ctx.save()
                ctx.translate(cx, cy)
                ctx.scale(rr.uniform(10, 40), rr.uniform(3, 8))
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.restore()
                ctx.set_source_rgba(0, 0, 0, 0.12)
                ctx.fill()
        if self.preset in ("street", "road"):
            ctx.set_source_rgb(*self._shade("#f4f1de"))
            for x in range(-3000, int(x1), 180):
                ctx.rectangle(x, -128, 90, 8)
            ctx.fill()
        if self.preset == "room":
            ctx.set_source_rgba(0, 0, 0, 0.12)
            ctx.set_line_width(2)
            for y in (-45, -100, -170):
                ctx.move_to(x0, y)
                ctx.line_to(x1, y)
            ctx.stroke()
        if self.preset == "classroom":
            ctx.set_source_rgba(0, 0, 0, 0.1)
            ctx.set_line_width(2)
            for x in range(-3000, int(x1), 120):
                ctx.move_to(x, 0)
                ctx.line_to(x - 60, -400)
            ctx.stroke()

    def _ground_patches(self, ctx, g, x0, x1):
        """The ground painted in layers: soft darker / lighter / dry / bare patches, so it is not one flat colour."""
        rr = seeded(stable_hash(f"gp{self.preset}") % 100000)
        kind = {v: k for k, v in GROUNDS.items()}.get(self.ground or "", "grass")
        if kind in ("grass", "dark_grass"):
            pal = [darker(g, 0.86), mix(g, (0.8, 0.72, 0.38), 0.4), lighter(g, 0.1), mix(g, (0.55, 0.42, 0.28), 0.5)]
        elif kind == "dirt":
            pal = [darker(g, 0.88), lighter(g, 0.09), mix(g, (0.42, 0.6, 0.28), 0.45)]
        elif kind == "sand":
            pal = [lighter(g, 0.07), darker(g, 0.93)]
        elif kind == "snow":
            pal = [mix(g, (0.75, 0.83, 0.93), 0.4)]
        else:
            pal = [darker(g, 0.92), lighter(g, 0.05)]
        n = int((x1 - x0) / 140)
        for k in range(n):
            cx = rr.uniform(x0, x1)
            cy = -rr.uniform(14, 420) ** 1.0
            w = rr.uniform(90, 360) * (1 + (-cy) / 400.0)
            ctx.save()
            ctx.translate(cx, cy)
            ctx.scale(w, w * rr.uniform(0.07, 0.13))
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            c = pal[k % len(pal)]
            ctx.set_source_rgba(c[0], c[1], c[2], rr.uniform(0.25, 0.5))
            ctx.fill()

    # ----------------------------------------------------------------- element drawers
    def _d_sun(self, ctx, e, t):
        if self.weather in ("rain", "storm", "cyclone"):
            return
        x, y = e["x"], e.get("y", 700)
        col = (1.0, 0.86, 0.3) if self.time != "sunset" else (1.0, 0.55, 0.3)
        if e.get("color"):                                  # another star: its own colour and size (engine/galaxy.py)
            col = hex_to_rgb(e["color"]) if isinstance(e["color"], str) else tuple(e["color"])
            R = float(e.get("radius", 56))
            lum = 1.0
            if e.get("pulse_s"):                             # 💫 a pulsar: a flash each time its beam sweeps over us
                vis = max(0.6, float(e["pulse_s"]))           # (too fast to see: shown as a flicker of ~1 a second)
                lum = 0.25 + 0.75 * max(0.0, math.cos(TAU * t / vis)) ** 20
            if e.get("disk"):                                # a young star still in its dusty disk: a glowing band through it
                ctx.save()
                ctx.translate(x, y)
                ctx.rotate(-0.18)
                ctx.scale(1.0, 0.12)
                for rr, a in ((R * 9, 0.08), (R * 6, 0.14), (R * 3.5, 0.2)):
                    ctx.set_source_rgba(0.95, 0.72, 0.45, a)
                    ctx.arc(0, 0, rr, 0, TAU)
                    ctx.fill()
                ctx.restore()
            for k, a in ((R * 1.7, 0.12), (R * 1.35, 0.2)):
                ctx.set_source_rgba(*col, a * lum)
                ctx.arc(x, y, k, 0, TAU)
                ctx.fill()
            ctx.set_source_rgba(*col, min(1.0, 0.3 + 0.7 * lum))
            ctx.arc(x, y, R, 0, TAU)
            ctx.fill()
            return
        look = getattr(self, "sky_look", None)
        if look == "dusk":
            return                                          # the sun has just set
        if self.time == "sunset":
            y = 330
        elif look == "dawn":
            y, col = 360, (1.0, 0.72, 0.45)
        elif self.time == "evening":
            y, col = 430, (1.0, 0.62, 0.35)
        for k, a in ((95, 0.12), (75, 0.2)):
            ctx.set_source_rgba(*col, a)
            ctx.arc(x, y, k, 0, TAU)
            ctx.fill()
        ctx.set_source_rgb(*col)
        ctx.arc(x, y, 56, 0, TAU)
        ctx.fill()

    def _d_moon(self, ctx, e, t):
        x, y = e["x"], 720
        ctx.set_source_rgba(1, 1, 0.9, 0.12)
        ctx.arc(x, y, 90, 0, TAU)
        ctx.fill()
        phase = str(self.spec.get("moon", "crescent")).lower()
        ctx.push_group()                                   # lit part only: works on any sky colour
        ctx.set_source_rgb(0.97, 0.96, 0.86)
        ctx.arc(x, y, 50, 0, TAU)
        ctx.fill()
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        if phase in ("half", "half_moon"):
            ctx.rectangle(x, y - 52, 54, 104)
            ctx.fill()
        elif phase not in ("full", "full_moon", "purnima"):
            ctx.arc(x + 22, y + 14, 44, 0, TAU)
            ctx.fill()
        ctx.set_operator(cairo.OPERATOR_OVER)
        if phase in ("full", "full_moon", "purnima"):
            ctx.set_source_rgba(0.85, 0.84, 0.74, 0.5)     # a few craters
            for dx, dy, r_ in ((-14, 10, 9), (12, -12, 7), (16, 16, 5)):
                ctx.arc(x + dx, y + dy, r_, 0, TAU)
                ctx.fill()
        ctx.pop_group_to_source()
        ctx.paint()

    def _d_cloud(self, ctx, e, t):
        s = e.get("scale", 1)
        x = (e["x"] + t * e.get("speed", 8) * rw.wind().drift() + 600) % 3400 - 600    # drifts with the wind
        y = e.get("y", 700)
        col = (1, 1, 1) if not self.night else (0.35, 0.4, 0.55)
        if self.weather in ("rain", "storm", "cyclone"):
            col = (0.55, 0.58, 0.64)
        elif self.weather in ("overcast", "cloudy") or getattr(self, "sky_look", None) in ("overcast", "stormy"):
            col = (0.78, 0.8, 0.84) if not self.night else (0.3, 0.33, 0.42)
        if self.time in ("sunset", "evening") and not self.night and col == (1, 1, 1):
            col = (1.0, 0.86, 0.8)                          # clouds catch the warm light
        if self._cloud_kind(ctx, e, t, x, y, s, col):
            return
        ctx.set_source_rgba(*col, 0.92)
        for dx, dy, rr in ((0, 0, 40), (40, 12, 50), (85, 0, 38), (40, -14, 36), (-30, -8, 30), (115, -10, 28)):
            ctx.arc(x + dx * s, y + dy * s, rr * s, 0, TAU)
            ctx.fill()

    def _ridge(self, ctx, e, amp, base_amp, n):
        rr = seeded(int(e.get("seed", 0.5) * 1e6))
        phases = [rr.uniform(0, TAU) for _ in range(4)]
        freqs = [rr.uniform(0.6, 1.4) * f for f in (0.0021, 0.0043, 0.0091, 0.017)]
        pts = []
        for x in range(-2500, int(self.world_w) + 3000, 40):
            y = base_amp + sum(amp[i] * math.sin(freqs[i] * x + phases[i]) for i in range(n))
            pts.append((x, y))
        return pts

    def _d_hills(self, ctx, e, t):
        pts = self._ridge(ctx, e, [70, 40, 15, 0], 110, 3)
        c = self._shade(e.get("color", "#9fd07a"))
        ctx.set_source_rgb(*c)
        ctx.move_to(pts[0][0], -800)
        for p in pts:
            ctx.line_to(*p)
        ctx.line_to(pts[-1][0], -800)
        ctx.close_path()
        ctx.fill()

    def _d_dunes(self, ctx, e, t):
        e = dict(e, seed=0.3)
        pts = self._ridge(ctx, e, [60, 30, 0, 0], 90, 2)
        ctx.set_source_rgb(*self._shade("#e2bf7d"))
        ctx.move_to(pts[0][0], -800)
        for p in pts:
            ctx.line_to(*p)
        ctx.line_to(pts[-1][0], -800)
        ctx.close_path()
        ctx.fill()

    def _d_mountains(self, ctx, e, t):
        rr = seeded(int(e.get("seed", 0.5) * 1e6))
        c = self._shade(e.get("color", "#8aa0bd"))
        big = e.get("big")
        x = -2400
        while x < self.world_w + 2600:
            w = rr.uniform(380, 700) * (1.3 if big else 1)
            h = rr.uniform(260, 470) * (1.25 if big else 1)
            px = x + w / 2 + rr.uniform(-60, 60)
            ctx.set_source_rgb(*c)
            ctx.move_to(x, -300)
            ctx.line_to(px, h)
            ctx.line_to(x + w, -300)
            ctx.close_path()
            ctx.fill()
            ctx.set_source_rgb(*darker(c, 0.88))
            ctx.move_to(px, h)
            ctx.line_to(x + w, -300)
            ctx.line_to(px + w * 0.08, -300)
            ctx.close_path()
            ctx.fill()
            if h > 330 and e.get("snow", True):              # (a warm planet: no snow caps)
                cap = (h - 300) / h
                ctx.set_source_rgb(*self._shade(e.get("cap", "#f7fbff")))
                ctx.move_to(px, h)
                ctx.line_to(px - (w / 2) * cap * 0.55, h - (h + 300) * cap * 0.55)
                ctx.line_to(px, h - (h + 300) * cap * 0.4)
                ctx.line_to(px + (w / 2) * cap * 0.55, h - (h + 300) * cap * 0.55)
                ctx.close_path()
                ctx.fill()
            x += w * 0.62

    def _d_sea(self, ctx, e, t):
        hz = e.get("horizon", 60)
        g = cairo.LinearGradient(0, hz, 0, -300)
        g.add_color_stop_rgb(0, *self._shade("#5aaee0"))
        g.add_color_stop_rgb(1, *self._shade("#2a7fc0"))
        ctx.set_source(g)
        ctx.rectangle(-3000, -800, self.world_w + 6000, 800 + hz)
        ctx.fill()
        ctx.translate(0, hz - 60)
        ctx.set_source_rgba(1, 1, 1, 0.5)
        ctx.set_line_width(3)
        for row in range(4):
            y = 40 - row * 30
            for x in range(-2000, int(self.world_w) + 2500, 140):
                xx = x + 30 * math.sin(t * 0.8 + row + x)
                ctx.move_to(xx, y)
                ctx.curve_to(xx + 15, y + 8, xx + 30, y + 8, xx + 45, y)
            ctx.stroke()

    def _d_tree(self, ctx, e, t):
        kind = canon_tree(e.get("kind"))
        if kind != e.get("kind", "round"):
            e = dict(e, kind=kind)
        if kind in MORE_TREES and self._tree_more(ctx, e, t):
            return
        if e.get("kind") in EXTRA_TREES:
            return self._tree_extra(ctx, e, t)
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", 0)
        kind = e.get("kind", "round")
        trunk = self._shade("#7a4f2b")
        leaf = self._shade(e.get("color", "#3f9142"))
        sway = 3 * rw.sway(t, x, 0.9)                       # the scene wind (engine/realworld.py)
        if kind == "pine":
            ctx.set_source_rgb(*trunk)
            ctx.rectangle(x - 9 * s, y, 18 * s, 50 * s)
            ctx.fill()
            for k in range(3):
                by, w, h = y + (40 + k * 60) * s, (95 - k * 22) * s, 110 * s
                ctx.set_source_rgb(*darker(leaf, 0.9 + 0.05 * k))
                ctx.move_to(x - w, by)
                ctx.line_to(x + sway * (k + 1) * 0.3, by + h)
                ctx.line_to(x + w, by)
                ctx.close_path()
                ctx.fill()
                if e.get("snow"):
                    ctx.set_source_rgb(*self._shade("#ffffff"))
                    ctx.move_to(x - w * 0.35, by + h * 0.65)
                    ctx.line_to(x + sway * (k + 1) * 0.3, by + h)
                    ctx.line_to(x + w * 0.35, by + h * 0.65)
                    ctx.close_path()
                    ctx.fill()
        elif kind == "palm":
            ctx.set_source_rgb(*trunk)
            ctx.set_line_width(18 * s)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.move_to(x, y)
            ctx.curve_to(x + 10 * s, y + 120 * s, x + 30 * s, y + 220 * s, x + 20 * s + sway, y + 300 * s)
            ctx.stroke()
            tx, ty = x + 20 * s + sway, y + 300 * s
            ctx.set_source_rgb(*self._shade("#3c9d4e"))
            for a in (-160, -120, -60, -20, 30, 150, 200):
                ar = math.radians(a)
                ctx.move_to(tx, ty)
                ctx.curve_to(tx + math.cos(ar) * 60 * s, ty + 50 * s, tx + math.cos(ar) * 120 * s,
                             ty + math.sin(ar) * 40 * s, tx + math.cos(ar) * 150 * s, ty + math.sin(ar) * 60 * s - 30 * s)
                ctx.curve_to(tx + math.cos(ar) * 100 * s, ty + 10 * s, tx + math.cos(ar) * 50 * s, ty + 20 * s, tx, ty)
                ctx.fill()
            ctx.set_source_rgb(*self._shade("#7a4f2b"))
            for dx in (-10, 12):
                ctx.arc(tx + dx * s, ty - 12 * s, 11 * s, 0, TAU)
                ctx.fill()
        else:
            ctx.set_source_rgb(*trunk)
            ctx.move_to(x - 14 * s, y)
            ctx.line_to(x - 8 * s, y + 130 * s)
            ctx.line_to(x + 8 * s, y + 130 * s)
            ctx.line_to(x + 14 * s, y)
            ctx.close_path()
            ctx.fill()
            for dx, dy, rr, f in ((-45, 150, 62, 0.9), (48, 155, 58, 0.93), (0, 205, 75, 1.0), (-8, 145, 60, 1.0)):
                ctx.set_source_rgb(*mix(leaf, (0, 0, 0), 1 - f))
                ctx.arc(x + dx * s + sway * dy / 200, y + dy * s, rr * s, 0, TAU)
                ctx.fill()
            ctx.set_source_rgba(1, 1, 1, 0.12)
            ctx.arc(x - 20 * s, y + 230 * s, 30 * s, 0, TAU)
            ctx.fill()

    def _d_house(self, ctx, e, t):
        self._d_house_body(ctx, e, t)
        diwali = str(self.spec.get("festival", "")).lower() == "diwali" or e.get("lights")
        if diwali and getattr(self, "lamps_on", self.night):    # Diwali: string lights on the eaves, diyas below
            from . import nightlights as nl
            s = e.get("scale", 1.0)
            x, y = e["x"], e.get("y", 0)
            nl.string_lights(ctx, x - 135 * s, x + 135 * s, y + 178 * s, t, sag=14 * s, seed=int(x) % 5)
            for k in range(4):
                dx = (-110 + k * 73) * s
                ctx.set_source_rgb(*self._shade("#b5651d"))
                ctx.arc(x + dx, y + 4, 7 * s, math.pi, TAU)
                ctx.fill()
                fl = 1 + 0.2 * math.sin(t * 13 + x + k)
                ctx.set_source_rgb(1, 0.78, 0.25)
                ctx.arc(x + dx, y + 4 + 9 * s * fl, 3.5 * s, 0, TAU)
                ctx.fill()
                nl.add_device(ctx, x + dx, y + 14 * s, 70 * s, nl.FLAME, 0.4, flame=True, kind="diya")

    def _d_house_body(self, ctx, e, t):
        if e.get("style"):
            return self._house_style(ctx, e, t)
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", 0)
        w, h = 250 * s, 180 * s
        c = self._shade(e.get("color", "#e76f51"))
        roof = self._shade(e.get("roof", "#8d3b2f"))
        ctx.set_source_rgb(*c)
        ctx.rectangle(x - w / 2, y, w, h)
        ctx.fill()
        ctx.set_source_rgb(*roof)
        ctx.move_to(x - w / 2 - 25 * s, y + h)
        ctx.line_to(x, y + h + 120 * s)
        ctx.line_to(x + w / 2 + 25 * s, y + h)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#6b3e26"))
        ctx.rectangle(x - 26 * s, y, 52 * s, 118 * s)          # fits a person at real size (engine/sizes.py)
        ctx.fill()
        lit = getattr(self, "lamps_on", self.night)
        win = self._shade("#fff3b0") if lit else self._shade("#bde0fe")
        for dx in (-85, 55):
            ctx.set_source_rgb(*((1.0, 0.86, 0.5) if lit else win))
            ctx.rectangle(x + dx * s, y + 90 * s, 42 * s, 42 * s)
            ctx.fill()
            if lit:                                      # a lit window: its light falls on the ground outside
                from .nightlights import add_device
                add_device(ctx, x + (dx + 21) * s, y + 111 * s, 90 * s, k=0.45, ground=(x + (dx + 21) * s, y - 20),
                           kind="window")
            ctx.set_source_rgb(*darker(c, 0.6))
            ctx.set_line_width(4 * s)
            ctx.rectangle(x + dx * s, y + 90 * s, 42 * s, 42 * s)
            ctx.move_to(x + (dx + 21) * s, y + 90 * s)
            ctx.line_to(x + (dx + 21) * s, y + 132 * s)
            ctx.stroke()

    def _d_shop(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", 0)
        w, h = 300 * s, 250 * s
        c = self._shade(e.get("color", "#2a9d8f"))
        ctx.set_source_rgb(*c)
        ctx.rectangle(x - w / 2, y, w, h)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#f4f1de"))
        for k in range(6):
            ctx.rectangle(x - w / 2 + k * w / 6, y + h * 0.62, w / 12, 34 * s)
        ctx.fill()
        lit = getattr(self, "lamps_on", self.night)
        win = (1.0, 0.88, 0.55) if lit else self._shade("#cfe8ff")
        ctx.set_source_rgb(*win)
        ctx.rectangle(x - w / 2 + 20 * s, y + 20 * s, w * 0.5, h * 0.45)
        ctx.fill()
        if lit:                                          # the shop's lit front
            from .nightlights import add_device
            add_device(ctx, x - w / 2 + 20 * s + w * 0.25, y + 20 * s + h * 0.22, 120 * s, k=0.4,
                       ground=(x - w / 2 + 20 * s + w * 0.25, y - 30), kind="shop")
        ctx.set_source_rgb(*darker(c, 0.55))
        ctx.rectangle(x + w * 0.18, y, 58 * s, 120 * s)
        ctx.fill()

    def _d_building(self, ctx, e, t):
        x, y = e["x"], 0
        w, h = e.get("w", 130), e.get("h", 380)
        c = self._shade(e.get("color", "#8d99ae"))
        ctx.set_source_rgb(*c)
        ctx.rectangle(x, y, w, h)
        ctx.fill()
        lit = getattr(self, "lamps_on", self.night)
        win = (1.0, 0.92, 0.55) if lit else lighter(c, 0.35)
        rr = seeded(int(x * 7 + h))
        n_lit = 0
        for wy in range(int(y + 30), int(y + h - 20), 42):
            for wx in range(int(x + 16), int(x + w - 20), 34):
                if not lit or rr.random() < 0.55:
                    ctx.set_source_rgb(*win)
                    ctx.rectangle(wx, wy, 18, 24)
                    ctx.fill()
                    if lit and n_lit < 6 and wy < y + 200:     # the lower lit windows light the street a little
                        from .nightlights import add_device
                        add_device(ctx, wx + 9, wy + 12, 60, k=0.3, kind="window")
                        n_lit += 1

    def _d_sidewalk(self, ctx, e, t):
        ctx.set_source_rgb(*self._shade("#b9b6ad"))
        ctx.rectangle(-3000, -48, self.world_w + 6000, 48)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#8f8c84"))
        ctx.rectangle(-3000, -56, self.world_w + 6000, 10)
        ctx.fill()

    def _d_sky_ring(self, ctx, e, t):
        """the rings of the giant planet you stand on (engine/galaxy.py): a wide band across the sky"""
        col = hex_to_rgb(e.get("color", "#e3cf8c"))
        ctx.save()
        ctx.translate(900, 300)
        ctx.rotate(0.12)
        ctx.scale(1.0, 0.32)
        for k, (r, a) in enumerate(((1500, 0.55), (1390, 0.35), (1290, 0.5))):
            ctx.new_path()
            ctx.arc(0, 0, r, 0.0, math.pi)                   # (the sky is y-up: the upper half of the ellipse)
            ctx.set_line_width(60 - 12 * k)
            ctx.set_source_rgba(*col, a)
            ctx.stroke()
        ctx.restore()

    def _d_lamp(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#343a40"))
        ctx.rectangle(x - 5, 0, 10, 300)
        ctx.fill()
        ctx.rectangle(x - 5, 290, 50, 8)
        ctx.fill()
        lit = getattr(self, "lamps_on", self.night)        # switches on by itself in the evening
        if lit:
            from .nightlights import add_device
            add_device(ctx, x + 40, 280, 260, ground=(x + 40, 0), kind="street_lamp")
            g = cairo.RadialGradient(x + 40, 280, 5, x + 40, 280, 180)
            g.add_color_stop_rgba(0, 1, 0.9, 0.5, 0.55)
            g.add_color_stop_rgba(1, 1, 0.9, 0.5, 0)
            ctx.set_source(g)
            ctx.arc(x + 40, 280, 180, 0, TAU)
            ctx.fill()
        ctx.set_source_rgb(1, 0.9, 0.55)
        ctx.arc(x + 40, 280, 12, 0, TAU)
        ctx.fill()

    def _d_hut(self, ctx, e, t):
        """Mud-walled hut with a thatch roof. Drawn at 260 tall; engine/sizes.py scales it to its real height
        (medium 690 = 2.3x a person), so walls come to 1.4x a person and the door (0.48) fits a grown-up."""
        s = e.get("scale", 1.0)
        x = e["x"]
        wall = self._shade("#d4a373")
        ctx.set_source_rgb(*wall)
        ctx.rectangle(x - 118 * s, 0, 236 * s, 158 * s)
        ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.08)                  # a plinth line at the bottom
        ctx.rectangle(x - 118 * s, 0, 236 * s, 10 * s)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#bc8a3c"))         # thatch roof
        ctx.move_to(x - 150 * s, 146 * s)
        ctx.line_to(x, 260 * s)
        ctx.line_to(x + 150 * s, 146 * s)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.15)
        ctx.set_line_width(3 * s)
        for k in range(-5, 6):
            ctx.move_to(x + k * 25 * s, 150 * s)
            ctx.line_to(x + k * 8 * s, 252 * s)
        ctx.stroke()
        ctx.set_source_rgb(*self._shade("#5a3a22"))         # door: 125 = 1.1x a person at real size
        ctx.rectangle(x - 26 * s, 0, 52 * s, 125 * s)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#3e2716"))
        ctx.rectangle(x + 58 * s, 70 * s, 34 * s, 30 * s)   # small window
        ctx.fill()

    def _d_well(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#9a8c7a"))
        ctx.rectangle(x - 60, 0, 120, 70)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#6b4f35"))
        ctx.rectangle(x - 55, 70, 8, 90)
        ctx.rectangle(x + 47, 70, 8, 90)
        ctx.fill()
        ctx.move_to(x - 75, 150)
        ctx.line_to(x, 190)
        ctx.line_to(x + 75, 150)
        ctx.close_path()
        ctx.fill()

    def _d_fence(self, ctx, e, t):
        x1, x2 = e["x"], e.get("x2", e["x"] + 600)
        ctx.set_source_rgb(*self._shade("#c8a27a"))
        for x in range(int(x1), int(x2), 45):
            ctx.rectangle(x, 0, 12, 70)
        ctx.rectangle(x1, 45, x2 - x1, 8)
        ctx.rectangle(x1, 18, x2 - x1, 8)
        ctx.fill()

    def _d_rock(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#8d8d8d"))
        ctx.move_to(x - 70 * s, 0)
        ctx.curve_to(x - 60 * s, 70 * s, x + 50 * s, 80 * s, x + 75 * s, 0)
        ctx.close_path()
        ctx.fill()

    def _d_bench(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        wood, iron = self._shade("#a0673a"), self._shade("#3d3d3d")
        ctx.set_source_rgb(*iron)
        for dx in (-95, 85):
            ctx.rectangle(x + dx * s, 0, 10 * s, 60 * s)
        ctx.fill()
        ctx.set_source_rgb(*wood)
        ctx.rectangle(x - 115 * s, 56 * s, 230 * s, 12 * s)
        ctx.rectangle(x - 115 * s, 95 * s, 230 * s, 12 * s)
        ctx.rectangle(x - 115 * s, 120 * s, 230 * s, 12 * s)
        ctx.fill()

    def _d_umbrella(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#555555"))
        ctx.rectangle(x - 3, 0, 6, 220)
        ctx.fill()
        for k, c in enumerate(("#e63946", "#f1faee", "#e63946", "#f1faee")):
            ctx.set_source_rgb(*self._shade(c))
            a0, a1 = math.pi * k / 4, math.pi * (k + 1) / 4
            ctx.move_to(x, 220)
            ctx.arc(x, 180, 130, a0, a1)
            ctx.close_path()
            ctx.fill()

    def _d_alien_plant(self, ctx, e, t):
        """a plant of another planet, made from parts (engine/alien_life.py); it sways in the scene wind"""
        from . import alien_life, realworld as rw
        sw = rw.sway(t, float(e.get("x", 0)), 0.8, float(e.get("seed", 0)) % 7) * 6.0
        from . import code3d
        if code3d.CURRENT is not None:                  # the 3D world: a real solid plant when it is big enough to see
            M = ctx.get_matrix()
            full_ = bool(getattr(code3d.CURRENT[0], "full", False))   # the full 3D world: solid plants all the way out
            if abs(M.xx) * float(e.get("height", 120)) * float(e.get("scale", 1.0)) > (6 if full_ else 30):
                got = code3d.draw_in_scene(ctx, alien_life.plant_faces(e), float(e.get("x", 0)), float(e.get("y", 0) or 0),
                                           None, None, recolor=False, bend=max(-0.12, min(0.12, sw * 0.01)))
                if got is not None:
                    return
        alien_life.draw_plant(ctx, e, t, sway=sw)

    def _d_cactus(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#4c9a2a"))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_width(34 * s)
        ctx.move_to(x, 0)
        ctx.line_to(x, 180 * s)
        ctx.move_to(x, 80 * s)
        ctx.line_to(x - 45 * s, 90 * s)
        ctx.line_to(x - 45 * s, 140 * s)
        ctx.move_to(x, 110 * s)
        ctx.line_to(x + 45 * s, 115 * s)
        ctx.line_to(x + 45 * s, 160 * s)
        ctx.stroke()

    def _d_grass(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x, y = e["x"], e.get("y", -40)
        ctx.set_source_rgb(*darker(self._shade(self.ground), 0.72))
        ctx.set_line_width(4 * s)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        sway = 3 * rw.sway(t, x, 1.5, x)
        for dx, h in ((-10, 22), (0, 30), (10, 20)):
            ctx.move_to(x + dx * s, y)
            ctx.line_to(x + (dx * 1.6 + sway) * s, y + h * s)
        ctx.stroke()

    def _d_flower(self, ctx, e, t):
        x, y = e["x"], e.get("y", -40)
        ctx.set_source_rgb(*self._shade("#3c7d34"))
        ctx.set_line_width(3)
        ctx.move_to(x, y)
        ctx.line_to(x, y + 28)
        ctx.stroke()
        ctx.set_source_rgb(*self._shade(e.get("color", "#ff6b6b")))
        for a in range(0, 360, 72):
            ctx.arc(x + 7 * math.cos(math.radians(a)), y + 30 + 7 * math.sin(math.radians(a)), 5.5, 0, TAU)
            ctx.fill()
        ctx.set_source_rgb(*self._shade("#ffd166"))
        ctx.arc(x, y + 30, 4.5, 0, TAU)
        ctx.fill()

    def _d_mushroom(self, ctx, e, t):
        x, y = e["x"], e.get("y", -40)
        ctx.set_source_rgb(*self._shade("#f1e3c8"))
        ctx.rectangle(x - 5, y, 10, 18)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#d62828"))
        ctx.arc(x, y + 18, 16, 0, math.pi)
        ctx.fill()

    # indoor
    def _d_wall(self, ctx, e, t):
        c = self._shade(e.get("color", "#f1e3c8"))
        ctx.set_source_rgb(*c)
        ctx.rectangle(-3000, 0, self.world_w + 6000, 3000)
        ctx.fill()
        ctx.set_source_rgb(*darker(c, 0.93))
        for x in range(-3000, int(self.world_w) + 3000, 120):
            ctx.rectangle(x, 0, 60, 3000)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#8a5a3b"))
        ctx.rectangle(-3000, 0, self.world_w + 6000, 26)
        ctx.fill()

    def _d_window(self, ctx, e, t):
        x, y, w, h = e["x"], 200, 220, 230
        top, bot = SKIES[self.time]
        g = cairo.LinearGradient(0, y + h, 0, y)
        g.add_color_stop_rgb(0, *hex_to_rgb(top))
        g.add_color_stop_rgb(1, *hex_to_rgb(bot))
        ctx.set_source(g)
        ctx.rectangle(x, y, w, h)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#ffffff"))
        ctx.set_line_width(12)
        ctx.rectangle(x, y, w, h)
        ctx.move_to(x + w / 2, y)
        ctx.line_to(x + w / 2, y + h)
        ctx.move_to(x, y + h / 2)
        ctx.line_to(x + w, y + h / 2)
        ctx.stroke()
        ctx.set_source_rgba(*self._shade("#e63946"), 0.85)
        ctx.rectangle(x - 40, y - 20, 40, h + 50)
        ctx.rectangle(x + w, y - 20, 40, h + 50)
        ctx.fill()

    def _d_door(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#7b4a2a"))
        ctx.rectangle(x - 65, 0, 130, 270)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#5a3520"))
        ctx.set_line_width(6)
        ctx.rectangle(x - 45, 150, 90, 95)
        ctx.rectangle(x - 45, 25, 90, 105)
        ctx.stroke()
        ctx.set_source_rgb(*self._shade("#f2c14e"))
        ctx.arc(x + 45, 130, 8, 0, TAU)
        ctx.fill()

    def _d_picture(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#6b4226"))
        ctx.rectangle(x - 80, 250, 160, 120)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#bde0fe"))
        ctx.rectangle(x - 68, 262, 136, 96)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#6aa84f"))
        ctx.move_to(x - 68, 262)
        ctx.line_to(x - 20, 320)
        ctx.line_to(x + 10, 290)
        ctx.line_to(x + 68, 340)
        ctx.line_to(x + 68, 262)
        ctx.close_path()
        ctx.fill()

    def _d_lamp_floor(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#333333"))
        ctx.rectangle(x - 4, 0, 8, 240)
        ctx.rectangle(x - 30, 0, 60, 8)
        ctx.fill()
        if getattr(self, "lamps_on", self.night):        # a room lamp lights the room round it
            from .nightlights import add_device
            add_device(ctx, x, 262, 280, k=0.75, ground=(x, 0), kind="room_lamp")
        ctx.set_source_rgb(*self._shade("#f4d35e"))
        ctx.move_to(x - 45, 230)
        ctx.line_to(x - 25, 300)
        ctx.line_to(x + 25, 300)
        ctx.line_to(x + 45, 230)
        ctx.close_path()
        ctx.fill()

    def _d_sofa(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        c = self._shade(e.get("color", "#457b9d"))
        ctx.set_source_rgb(*darker(c, 0.85))
        ctx.rectangle(x - 150 * s, 40 * s, 300 * s, 110 * s)
        ctx.fill()
        ctx.set_source_rgb(*c)
        ctx.rectangle(x - 150 * s, 10 * s, 300 * s, 55 * s)
        ctx.rectangle(x - 175 * s, 10 * s, 40 * s, 95 * s)
        ctx.rectangle(x + 135 * s, 10 * s, 40 * s, 95 * s)
        ctx.fill()

    def _d_bed(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#8b5a3c"))
        ctx.rectangle(x - 180 * s, 0, 16 * s, 150 * s)
        ctx.rectangle(x + 164 * s, 0, 16 * s, 100 * s)
        ctx.rectangle(x - 180 * s, 20 * s, 360 * s, 30 * s)
        ctx.fill()
        ctx.set_source_rgb(*self._shade(e.get("color", "#a8dadc")))
        ctx.rectangle(x - 165 * s, 48 * s, 330 * s, 16 * s)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#ffffff"))
        ctx.rectangle(x - 160 * s, 62 * s, 70 * s, 22 * s)
        ctx.fill()

    def _d_table(self, ctx, e, t):
        s = e.get("scale", 1.0)
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#8b5a3c"))
        ctx.rectangle(x - 100 * s, 95 * s, 200 * s, 14 * s)
        ctx.rectangle(x - 85 * s, 0, 10 * s, 95 * s)
        ctx.rectangle(x + 75 * s, 0, 10 * s, 95 * s)
        ctx.fill()

    def _d_board(self, ctx, e, t):
        x = e["x"]
        ctx.set_source_rgb(*self._shade("#7b5b3a"))
        ctx.rectangle(x - 330, 150, 660, 300)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#2f4f3f"))
        ctx.rectangle(x - 315, 165, 630, 270)
        ctx.fill()
        text = self.spec.get("board_text", "")
        if text:
            ctx.save()
            ctx.translate(x - 280, 380)
            ctx.scale(1, -1)
            ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            ctx.set_font_size(44)
            ctx.set_source_rgb(0.95, 0.95, 0.95)
            for i, line in enumerate(str(text).split("\n")[:4]):
                ctx.move_to(0, i * 58)
                ctx.show_text(line)
            ctx.restore()

    def _d_clock(self, ctx, e, t):
        x, y = e["x"], 400
        ctx.set_source_rgb(*self._shade("#ffffff"))
        ctx.arc(x, y, 38, 0, TAU)
        ctx.fill_preserve()
        ctx.set_source_rgb(*self._shade("#333333"))
        ctx.set_line_width(5)
        ctx.stroke()
        ctx.set_line_width(4)
        a = -t * 0.5
        ctx.move_to(x, y)
        ctx.line_to(x + 28 * math.sin(a), y + 28 * math.cos(a))
        ctx.move_to(x, y)
        ctx.line_to(x + 18, y + 8)
        ctx.stroke()

    def _d_desk(self, ctx, e, t):
        x, y = e["x"], e.get("y", -110)
        ctx.set_source_rgb(*self._shade("#c08552"))
        ctx.rectangle(x - 90, y + 80, 180, 14)
        ctx.fill()
        ctx.set_source_rgb(*self._shade("#5e503f"))
        ctx.rectangle(x - 80, y, 8, 80)
        ctx.rectangle(x + 72, y, 8, 80)
        ctx.fill()
