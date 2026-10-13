"""True 2.5D ("camera_mode": "3d"): any outdoor place rebuilt as a real depth world.

The place's own artwork is reused - every background element keeps the look it has in the normal mode -
but now it stands at a real distance from a pinhole camera:
  * sky, sun, moon, clouds, far mountains/hills/dunes/city  -> painted backdrop on the horizon
  * the ground is a perspective plane (grass, sand, snow, water, shore, an optional winding path)
  * trees, huts, stalls ... stand at the distance of their old layer (back rows really are far away)
  * extra copies of the place's own trees/rocks/plants are scattered deep into the distance and in the
    foreground, so there are 5 depth bands: far background / background / stage / foreground / extreme fg
  * characters, animals and vehicles walk and drive through that space (z 0 = front ... 1000 = back of the
    stage ... up to 3000 = deep into the distance), get smaller, hazier, go behind trees and come out again.

Distances are in world units; the stage front (z = 0) is at Z = FOCAL, where 1 world unit = 1 px at 1080p,
so a 3D scene is framed exactly like the normal mode at the same camera settings.
"""
import math
import random

import cairo

from .scene3d import (DepthScene, Obj, FOCAL, NEAR, tree_tall, tree_pine, bush, fern, big_leaf_plant, rock,
                      grass_tuft, flower, hanging_leaves)
from .background import set_layer, Camera
from .util import clamp, lerp, mix, darker, lighter, hex_to_rgb, TAU, stable_hash

MAX_DOLLY = 520.0        # the camera moves at most this far into the scene; beyond it the lens zooms
CAM_H = 345.0            # camera height that reproduces the normal mode's framing (see camera.cy_for_zoom)
HORIZON = 0.5

FAR_TYPES = ("hills", "mountains", "dunes", "sea", "nebula", "solar", "earth", "saturn", "planet")
NATURE = ("tree", "jungle_tree", "banana", "rock", "cactus", "fern", "plant", "reeds", "stumps", "bush",
          "haystack", "hedge", "alien_plant")
SMALL = ("grass", "flower", "fern", "rock", "reeds", "mushroom", "bush", "plant", "banana")
TOWN = ("house", "hut", "shop", "stall", "barn", "lamp")
PATH_PRESETS = ("jungle", "forest", "village", "farm", "mountains", "hill_station", "park", "garden", "zoo",
                "desert_village", "coconut_village", "plain", "river", "snow")
JUNGLE_KIT = ("jungle", "forest")
PATH_OK_TYPES = ("crops", "sidewalk", "verge", "river", "string_lights", "rug", "water_front", "flower", "grass",
                 "image")
ROAD_COLORS = {"road": "#55595f", "tar": "#55595f", "highway": "#4a4d52", "dirt": "#b98e5e", "kaccha": "#c29a68",
               "village": "#c29a68", "stone": "#9a958c", "footpath": "#d8c7a0", "sand": "#e2c48f"}
PATH_COLORS = {"snow": "#dfe7ee", "desert_village": "#e2c48f", "village": "#b98e5e", "farm": "#b98e5e",
               "park": "#d9c49a", "garden": "#d9c49a", "zoo": "#d9c49a"}


# solid width of set dressing in story units (an adult is 300 tall): what a character cannot walk through
FOOTPRINT = {"house": 830, "barn": 720, "hut": 610, "shop": 750, "stall": 340, "temple": 1100, "school": 1180,
             "well": 220, "tree": 200, "jungle_tree": 220, "banana": 120, "palm": 160, "rock": 230, "haystack": 260,
             "cart": 330, "bench": 260, "tower": 300, "statue": 200, "fountain": 320, "windmill": 300,
             "water_tank": 300, "clock_tower": 320, "lighthouse": 300, "big_tree": 330, "banyan": 560,
             "cactus": 90, "lamp": 60, "sign": 60, "swing": 260, "slide": 300, "goal": 360, "umbrella": 200,
             "bush": 200, "hedge": 0, "fence": 0, "grass": 0, "flower": 0, "fern": 0, "plant": 0, "reeds": 0,
             "stumps": 120, "mushroom": 0, "crops": 0}


# real heights (story units, an adult is 300 tall): houses, trees and wells keep true size next to people
from . import sizes as _sizes                                        # noqa: E402
REAL_H = _sizes.REAL                     # real heights (adult = 300) - see engine/sizes.py



from . import palette as _palette


def _pw(c):
    """water colour -> the world palette's water (same brightness)"""
    return _palette.map_colour(c, "water")

def images_exists(name):
    from . import images
    return images.exists(name)


def _pic_h(e):
    """height of a picture / 3D drawing element: its own "height", else the drawing's real saved height"""
    if e.get("height"):
        return float(e["height"])
    try:
        from . import images
        h = (images.info(e.get("name") or e.get("image") or "") or {}).get("height")
        return float(h) if h else 300.0
    except Exception:
        return 300.0
_DRAWN_H = {}


REAL_H_KIND = _sizes.TREE_KIND


def drawn_height(bg, typ, kind=None):
    """How tall an element is drawn at scale 1 (measured once)."""
    key = (typ, kind) if kind else typ
    if key in _DRAWN_H:
        return _DRAWN_H[key]
    import cairo
    import numpy as np
    fn = getattr(bg, "_d_" + typ, None)
    h = None
    if fn is not None:
        try:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 700)
            c = cairo.Context(surf)
            c.translate(400, 650)
            c.scale(0.25, -0.25)
            old = getattr(bg, "_t", 0.0)
            bg._t = 0.0
            el = {"type": typ, "x": 0, "y": 0}
            if kind:
                el["kind"] = kind
            fn(c, el, 0.0)
            bg._t = old
            surf.flush()
            a = np.ndarray((700, surf.get_stride() // 4), np.uint32, surf.get_data())[:, :800] >> 24
            ys = np.nonzero((a > 20).any(axis=1))[0]
            if len(ys):
                h = (650 - ys.min()) * 4.0
        except Exception:
            return None                              # not ready yet: don't remember a failure
    _DRAWN_H[key] = h
    return h


def real_scale(bg, typ, fallback, var=1.0, kind=None, word=None):
    """Scale that gives an element its real height (fallback: the old depth scale). word = tiny..huge."""
    rh = _sizes.real_height(typ, kind if typ == "tree" else None, word or "medium")
    if not rh:
        return fallback
    dh = drawn_height(bg, typ, kind if typ == "tree" else None)
    if not dh or dh < 20:
        return fallback
    return rh / dh * var


# ---------------------------------------------------------------------------- depth mapping
def element_obj(bg, e, cx, tag="actor"):
    """A background thing placed at story depth z (place JSON) as a 3D object - used on photo backgrounds,
    where the photo is the world and these things stand in it (hidden by the photo's nearer parts)."""
    from .scene3d import Obj
    typ = e["type"]
    fn = getattr(bg, "_d_" + typ, None)
    if fn is None or e.get("z") is None or typ == "road_band":
        return None
    z = float(e["z"])
    Z, p = Z_of_z(z), p3(z)
    X = X_of(e["x"], p, cx)
    e2 = dict(e, y=0.0, scale=1.0)
    if typ == "image":
        sc_ = 1.0
        e2["height"] = _pic_h(e)
    else:
        sc_ = real_scale(bg, typ, 1.0, float(e.get("size", 1.0)), kind=e.get("kind"), word=e.get("sw"))
    x0 = e2["x"]

    def draw(ctx, t, e2=e2, x0=x0, s=sc_, fn=fn):
        bg._t = t
        ctx.scale(s, s)
        ctx.translate(-x0, 0)
        fn(ctx, e2, t)
    return Obj(X, Z, draw, w=2600 * sc_, tag=tag)


def Z_of_z(z):
    """Story depth z (0 front ... 1000 back of the stage ... 3000 far away) -> camera distance."""
    z = clamp(float(z or 0.0), 0.0, 3000.0)
    if z <= 1000.0:
        return FOCAL / (1.0 - 0.58 * z / 1000.0)
    return FOCAL / 0.42 + (z - 1000.0) * 4.0


def p3(z):
    return FOCAL / Z_of_z(z)


def X_of(x, p, anchor=960.0):
    """Story x at depth scale p -> world X. In 3D mode the anchor is the middle of the scene, so a character
    at the scene's centre x stays on the centre line (the path) however far away it walks; x left/right of the
    centre spreads out with distance like a real field of view."""
    return (x - anchor * (1.0 - p)) / p


def cam3_from(cam, shake_s=1.0):
    """Normal-mode camera (x, y, zoom, subject depth d) -> 3D camera: a zoom becomes a real dolly toward
    the subject, so push-ins and pull-backs have true parallax."""
    from .scene3d import Cam3
    d = getattr(cam, "d", 0.0) or 0.0
    Zs = Z_of_z(d)
    zoom = max(0.3, cam.z)
    cz = Zs - FOCAL / zoom                    # pure dolly: the subject appears at the requested size
    h = max(35.0, cam.y + (getattr(cam, "dh", 0.0) or 0.0))
    lim = max(MAX_DOLLY, min(Zs - 240.0, 950.0)) if d < 400 else MAX_DOLLY   # near subjects: come in closer
    c = Cam3(x=cam.x, h=h, z=min(cz, lim), horizon=getattr(cam, "hor", HORIZON) or HORIZON)
    if cz > lim:                        # far subject: move in a little, then zoom the lens the rest
        c.fz = zoom * (Zs - c.z) / FOCAL
    lens = getattr(cam, "lens", 1.0) or 1.0
    ang_k = 1.0
    if abs(lens - 1.0) > 0.01:                # telephoto / wide-angle: same subject size, camera further / nearer
        ds0 = max(Zs - c.z, 80.0)
        ds1 = max(ds0 * lens, 150.0)
        c.z = Zs - ds1
        c.fz *= ds1 / ds0
        if getattr(cam, "keep", False):       # feature layout: a low / high / 3-4 angle stays the same angle
            ang_k = (ds1 / ds0) ** 0.85       # when the lens pushes the camera back
            dh = getattr(cam, "dh", 0.0) or 0.0
            c.h = max(35.0, cam.y + dh * ang_k)
            if not (getattr(cam, "aim", 0.0) or 0.0) > 0:     # tilt so the eye line stays where it was framed
                c.horizon += (cam.y - c.h) * FOCAL * c.fz / max(Zs - c.z, 80.0) / 1080.0
    ds = max(Zs - c.z, 80.0)
    c.focus = ds
    aim = getattr(cam, "aim", 0.0) or 0.0
    if aim > 0:                               # tilt the camera so the subject's middle sits at 55% height
        k = FOCAL * c.fz / ds / 1080.0
        c.horizon = lerp(HORIZON, 0.55 - (c.h - 150.0) * k, aim) + (c.horizon - HORIZON)
    arc = (getattr(cam, "arc", 0.0) or 0.0) * ang_k
    if arc:                                   # swing around the subject, lens shift keeps it centred
        c.x = cam.x + arc
        c.shift = arc * FOCAL * c.fz / ds
    c.mirror = getattr(cam, "rev", None) is not None
    return c


class World3D(DepthScene):
    def __init__(self, bg, W, H, seed=0):
        self.bg = bg
        self.cx = bg.world_w / 2.0
        self.kit = bg.preset in JUNGLE_KIT and not (bg.spec.get("trees") or bg.spec.get("tree"))
        want_path = bg.spec.get("path")
        self.has_path = bool(want_path) if want_path is not None else (bg.preset in PATH_PRESETS and not bg.water)
        self.sea_from = None
        self.backdrop_els, self.sky_els = [], []
        self.shafts = bg.preset in JUNGLE_KIT and bg.time in ("day", "morning")
        self.rain_objs = []
        self.path_style = str(bg.spec.get("path_style", bg.spec.get("path") if isinstance(bg.spec.get("path"), str)
                                          else "")).lower()
        pc = ROAD_COLORS.get(self.path_style) or PATH_COLORS.get(bg.preset, "#c9a36b")
        self.roads = [e for e in bg.elements if e["type"] == "road_band"]
        gcol = bg._shade(bg.ground or "#7cc15a")
        self.full = bool(getattr(bg, "full3d", False))   # the 3D page: a whole world all around the camera
        self.wm = getattr(bg, "worldmap", None)          # a big world map: the real surroundings of this spot
        if self.wm:
            self.has_path = False                        # the world's own roads instead of the endless path
        super().__init__(W, H, seed=seed, ground="#000000", path_col=pc, fog=bg.haze_color())
        self.ground = gcol
        from . import code3d
        from . import realworld
        self._time = realworld.time_word(bg)
        self._sun3 = code3d.sun_dir(self._time)
        if str(bg.weather or "").lower() in realworld.OVERCAST:   # clouds: light from the whole sky, short shadows
            self._sun3 = (0.1 * self._sun3[0], 0.99, -0.08)             # 3D code drawings are lit from where the sun is

    # ================================================================== composition
    def path_x(self, Z):
        """Centre of the path at distance Z: gentle bends around the scene's centre line (x = width / 2),
        so a character walking at the centre x stays on the path however far away it goes."""
        return self.cx + 70 * math.sin(Z / 1500.0 + 0.4) - 25 * math.sin(Z / 4100.0)

    def _split_at_path(self, e, p, Z):
        """A fence/hedge row across the scene gets a gap where the path goes through it."""
        x1, x2 = float(e["x"]), float(e.get("x2", e["x"] + 600))
        xg = self.path_x(Z) * p + self.cx * (1 - p)          # story x of the path at this depth
        half = 260.0 * p
        parts = []
        if xg - half > x1 + 40:
            parts.append(dict(e, x=x1, x2=min(x2, xg - half)))
        if xg + half < x2 - 40:
            parts.append(dict(e, x=max(x1, xg + half), x2=x2))
        return parts or [e]

    def _clear_of_action(self, typ, X, Z, scale):
        """Real-world rule: a house, barn, tree trunk or well is SOLID. Where the story's characters, animals,
        objects or vehicles stand or move, the set dressing moves aside (like a film set is dressed around
        the action), so nobody walks through a house or ends up inside it."""
        pts = getattr(self.bg, "_keep_clear", None)
        if not pts:
            return X
        half = FOOTPRINT.get(typ, 200.0) * scale / 2.0 + 90.0
        depth = 260.0 + FOOTPRINT.get(typ, 200.0) * scale * 0.35
        band = [px for px, pz in pts if abs(pz - Z) < depth]
        if not band or all(abs(px - X) >= half for px in band):
            return X
        for step in range(1, 40):
            for sgn in (1, -1):
                Xn = X + sgn * step * 60.0
                if all(abs(px - Xn) >= half for px in band):
                    return Xn
        return X

    def _depth_elem(self, e):
        """An element placed at story depth z: real position, real height, off the path, clear of the action."""
        bg, typ = self.bg, e["type"]
        z = float(e["z"])
        Z, p = Z_of_z(z), p3(z)
        X = X_of(e["x"], p, self.cx)
        e2 = dict(e, y=0.0, scale=1.0)
        if typ == "image":
            sc_ = 1.0                                   # pictures carry their real height (story units)
            e2["height"] = _pic_h(e)
        else:
            sc_ = real_scale(bg, typ, 1.0, float(e.get("size", 1.0)), kind=e.get("kind"), word=e.get("sw"))
        small = typ in ("flower", "grass", "reeds", "mushroom", "diya", "fern", "plant")
        if e.get("exact"):                                     # a code-drawn place: exactly as built, raised parts too
            return self._elem_obj(e2, Z, sc_, X, "place", y0=0.0, Y=float(e.get("y", 0.0) or 0.0))
        if typ == "hill_mound" or e.get("ty"):                 # land shape / things standing on it: exactly there
            return self._elem_obj(e2, Z + (10.0 if typ == "hill_mound" else -6.0), 1.0 if typ == "hill_mound" else sc_,
                                  X, "hill" if typ == "hill_mound" else "place", y0=0.0,
                                  Y=float(e.get("ty", 0.0)))
        if self.has_path and not small and z < 2600:
            off = X - self.path_x(Z)
            clear = 230.0 + 60.0 / max(p, 0.2)
            if abs(off) < clear:
                X = self.path_x(Z) + (clear if off >= 0 else -clear)
        if not small and z < 1000:
            X = self._clear_of_action(typ, X, Z, sc_)
        return self._elem_obj(e2, Z, sc_, X, "place" if not small else "scatter", y0=0.0)

    def _elem_obj(self, e, Z, scale, X, tag, y0=None, Y=0.0):
        bg = self.bg
        fn = getattr(bg, "_d_" + e["type"], None)
        if fn is None:
            return None
        e2 = dict(e)
        if y0 is not None:
            e2["y"] = y0
        x0 = e2["x"]

        def draw(ctx, t, e2=e2, x0=x0, s=scale, fn=fn):
            bg._t = t
            ctx.scale(s, s)
            ctx.translate(-x0, 0)
            fn(ctx, e2, t)
        return Obj(X, Z, draw, Y=Y, w=2600 * scale, tag=tag)

    def _build(self):
        bg = self.bg
        r = random.Random(self.seed * 7 + 3)
        add = self.objs.append
        nature, smalls, town = [], [], []
        for e in bg.elements:
            typ, layer, p = e["type"], e.get("layer", "mid"), float(e.get("p", 1.0))
            if layer == "sky" or p < 0.12:
                self.sky_els.append(e)
                continue
            if self.kit and typ in ("jungle_tree", "tree", "vine"):
                continue                               # the painted jungle kit replaces the flat tree rows
            if typ == "river" and bg.water:
                continue                               # the 3D water surface replaces the flat river band
            if typ == "hill_road":
                continue                               # a flat 2D drawing: looks like a wire in the 3D sky
            if typ == "road_band":
                continue                                 # lies on the ground (drawn with it)
            if e.get("z") is not None and not e.get("_sky"):
                o = self._depth_elem(e)                  # a thing at a real depth (place JSON)
                if o:
                    add(o)
                continue
            if layer == "far" or typ in FAR_TYPES:
                self.backdrop_els.append(e)
                if typ == "sea":
                    self.sea_from = 3400.0
                continue
            y = float(e.get("y", 0) or 0)
            if bg.water and typ in NATURE + TOWN + ("tree",) and layer != "front":
                Xw = X_of(e["x"], p, self.cx)
                on_water = bg.shore_x is None or (Xw > bg.shore_x - 60 if bg.land_side == "left"
                                                  else Xw < bg.shore_x + 60)
                if on_water:
                    continue                           # trees and huts stay on the land side
            if layer == "front" and y < 0:             # front strips: lower on screen = nearer the camera
                pe = p * (CAM_H + -y) / CAM_H
                Z = FOCAL / pe
                o = self._elem_obj(e, Z, 1.0 / pe, X_of(e["x"], pe, self.cx), "fg", y0=0.0)
            else:
                pe = p
                Z = FOCAL / p + (60.0 if p >= 0.999 else 0.0)
                X = X_of(e["x"], p, self.cx)
                if self.has_path and layer != "front":
                    if typ in ("fence", "hedge") and "x2" in e or typ == "fence":
                        for part in self._split_at_path(e, p, Z):     # a gap where the path passes
                            o = self._elem_obj(part, Z, 1.0 / p, X_of(part["x"], p, self.cx), "place")
                            if o:
                                add(o)
                        continue
                    if typ not in PATH_OK_TYPES:
                        off = X - self.path_x(Z)
                        clear = 330.0 + 140.0 / p                      # keep the view down the path open
                        if abs(off) < clear:
                            X = self.path_x(Z) + (clear if off >= 0 else -clear)
                sc_ = 1.0 / p
                if layer != "front":
                    sc_ = real_scale(bg, typ, sc_, 0.92 + 0.16 * ((stable_hash(str(e.get("x"))) % 100) / 100.0),
                                     kind=e.get("kind"), word=e.get("sw"))
                    X = self._clear_of_action(typ, X, Z, sc_)
                o = self._elem_obj(e, Z, sc_, X, "fg" if layer == "front" else "place")
            if o:
                add(o)
            if typ in NATURE or (typ == "tree"):
                nature.append((e, pe))
            if typ in SMALL:
                smalls.append((e, pe))
            if typ in TOWN:
                town.append((e, pe))
        dens = {"sparse": 0.55, "empty": 0.3, "normal": 1.0, "busy": 1.35, "dense": 1.5}.get(bg.density, 1.0)
        lo, hi = -400.0, bg.world_w + 400.0
        stage_ok = lambda X, Z: not (lo - 200 < X < hi + 200 and Z < FOCAL / 0.42 + 250)   # noqa: E731
        def path_ok(X, Z):
            if self.has_path and abs(X - self.path_x(Z)) < 260:
                return False
            if bg.water:                                # nothing grows on the water
                if bg.shore_x is None:
                    return False
                return X < bg.shore_x - 120 if bg.land_side == "left" else X > bg.shore_x + 120
            return True
        # --- the place's own nature, scattered deep into the distance
        if nature and not self.kit and bg.spec.get("fill", True):
            for _ in range(int(170 * dens)):
                e, pe = r.choice(nature)
                Z = r.uniform(FOCAL / 0.42 + 300, 12000) if r.random() < 0.8 else r.uniform(1400, 2900)
                X = self.cx + r.uniform(-1.0, 1.0) * (Z * 1.05 + 1800)
                if not stage_ok(X, Z) or not path_ok(X, Z) or (self.sea_from and Z > self.sea_from - 150):
                    continue
                s = real_scale(bg, e["type"], (1.0 / pe), 1.0, kind=e.get("kind")) * r.uniform(0.8, 1.3)
                o = self._elem_obj(dict(e, flip=r.random() < 0.5), Z, s, X, "scatter", y0=0.0)
                if o:
                    add(o)
        if town:
            for _ in range(int(40 * dens)):
                e, pe = r.choice(town)
                Z = r.uniform(3200, 9000)
                X = self.cx + r.uniform(-1.0, 1.0) * (Z * 0.9 + 1200)
                if not path_ok(X, Z) or abs(X - self.cx) < 400 or (self.sea_from and Z > self.sea_from - 150):
                    continue
                o = self._elem_obj(e, Z, real_scale(bg, e["type"], 1.0 / pe) * r.uniform(0.9, 1.15), X, "scatter",
                                   y0=0.0)
                if o:
                    add(o)
        # --- foreground framing: the place's small plants just in front of the stage (tops peek in at the bottom)
        fg_pool = smalls
        if fg_pool and bg.spec.get("foreground", "normal") != "none":
            x = lo
            while x < hi:
                x += r.uniform(380, 700) / dens
                e, pe = r.choice(fg_pool)
                Z = r.uniform(430, 700)
                s = (1.0 / pe) * r.uniform(1.0, 1.6)
                if e["type"] in ("grass", "flower"):
                    s *= 2.2
                o = self._elem_obj(e, Z, s, x, "fg", y0=0.0)
                if o:
                    add(o)
        if bg.spec.get("clay") and not bg.indoor:            # 🏘 a clay village's ground is not bare: soft grass
            for _p in range(int(14 * dens)):                    # clumps grow in patches (where feet don't go),
                Zc = r.uniform(380, 2200)                       # pebbles lie about
                Xc = self.cx + r.uniform(-1, 1) * (Zc * 0.95 + 600)
                gc = r.choice(["#4f8a33", "#5c9438", "#6a9a3c", "#7c9a40"])
                for _k in range(r.randint(2, 6)):
                    X, Z = Xc + r.uniform(-90, 90), Zc + r.uniform(-40, 40)
                    sd = r.randint(0, 10 ** 6)
                    sc_ = r.uniform(0.8, 1.6)
                    add(Obj(X, Z, lambda c, t, sd=sd, sc_=sc_, gc=gc: grass_tuft(c, sd, t, sc_, gc), w=60, tag="grass"))
                if r.random() < 0.6:
                    sd = r.randint(0, 10 ** 6)
                    sc_ = r.uniform(0.12, 0.26)
                    add(Obj(Xc + r.uniform(-150, 150), Zc + r.uniform(-60, 60),
                            lambda c, t, sd=sd, sc_=sc_: rock(c, sd, t, sc_, "#a3937e"), w=60, tag="rock"))
        if self.kit:
            self._jungle_kit(r, dens, stage_ok, path_ok)
        if bg.spec.get("foreground", "normal") != "none":
            self._life(r, dens, lo, hi)
        if bg.spec.get("foreground") == "rich":
            for k, x in enumerate(range(int(lo), int(hi), 1100)):
                sd = r.randint(0, 10 ** 6)
                add(Obj(x + r.uniform(-200, 200), r.uniform(230, 330),
                        lambda c, t, sd=sd: big_leaf_plant(c, sd, t, 0.55, "#2f8a3c"), w=500, tag="xfg"))
        if self.wm:
            self._world_build()
        elif self.full:
            self._ring(r, nature, town, dens, path_ok,
                       bool(nature and not self.kit and bg.spec.get("fill", True)))

    # ================================================================== a big world map around this spot
    WORLD_NEAR = 320.0          # metres: the world's things drawn round the scene (far ones = its places)
    WORLD_FAR = 3200.0
    # "world_detail": how much of a big world is drawn round a scene - (near metres, most near things, far metres,
    # most far places). Fewer things = much faster frames and less RAM per render worker.
    DETAIL = {"low": (120.0, 250, 1200.0, 6), "medium": (200.0, 500, 2200.0, 12), "high": (320.0, 1000, 3200.0, None)}

    def _detail(self):
        d = str((self.wm or {}).get("detail") or "high").lower()
        return self.DETAIL.get(d, self.DETAIL["high"])

    LAMPS_ON = ("sunset", "dusk", "night", "midnight")         # street lamps and chulhas lit
    WINDOWS_LIT = ("dusk", "night", "midnight")                 # a lamp inside every house

    def _lit_state(self, typ):
        """after dark the world's houses have their windows lit and its lamps are on (their "night" / "on" look)"""
        t = getattr(self, "_time", "day")
        if t in self.WINDOWS_LIT and images_exists(f"{typ}_night"):
            return "night"
        if t in self.LAMPS_ON and images_exists(f"{typ}_on"):
            return "on"
        return None

    def _wpt(self, p):
        from .worldmap import to_scene
        X, Z = to_scene(p, self.wm["anchor"], self.wm["heading"])
        return self.cx + X, Z

    def _world_build(self):
        """The real surroundings from the world map: its trees, huts, rocks, fields ... around this spot, and the
        other places (villages, the mela, the jungle ...) far away in their true direction."""
        from . import images, registry
        from .worldmap import UNITS
        wm = self.wm
        w, (ax, az) = wm["world"], wm["anchor"]
        skip = set(wm.get("exclude") or ())
        add = self.objs.append
        hdeg = math.degrees(wm["heading"])
        near_m, near_n, far_m, far_n = self._detail()
        self.WORLD_FAR = far_m                           # (this scene only) roads, fields, far places
        for o in w.things_near(ax, az, near_m, view=True, limit=near_n):
            if o["id"] in skip:
                continue
            X, Z = self._wpt(o["at"])
            if Z < -9000:
                pass
            typ = o["type"]
            st = o.get("state") or self._lit_state(typ)
            name = f"{typ}_{st}" if st and images.exists(f"{typ}_{st}") else typ
            m = images.info(name) or images.info(typ)
            if not m:
                continue
            e2 = {"type": "image", "name": name, "x": 0.0, "y": 0.0, "flip": False,
                  "height": float(m.get("height") or 300) * float(o.get("scale", 1.0) or 1.0),
                  "turn": (float(o.get("turn", 0.0) or 0.0) - hdeg) % 360.0}
            ob = self._elem_obj(e2, Z, 1.0, X, "place" if typ not in ("crops_3d", "bush_3d", "rock_3d") else "scatter",
                                y0=0.0)
            if ob:
                add(ob)
        own = wm.get("own")
        far_places = [pl for pl in w.places_near(ax, az, self.WORLD_FAR) if pl["id"] != own]
        for pl in far_places[:far_n] if far_n else far_places:   # the other places, as they really stand
            if pl["id"] == own:
                continue
            spec = registry.place(pl.get("place")) or {}
            if "andar" in str(pl.get("place", "")) or (pl["id"] + "_ghar") in w.byid or spec.get("indoor"):
                continue                                 # an inside room (its house stands outside): not seen from out here
            t = math.radians(pl.get("turn", 0.0) or 0.0)
            for th in spec.get("things") or []:
                what = th.get("what") if isinstance(th, dict) else None
                m = images.info(what) if what else None
                if not m:
                    continue
                c3 = m.get("c3") or [0.0, 0.0, 0.0]
                mx, mz = float(c3[0]) / UNITS, float(c3[2]) / UNITS          # its spot in the place (metres)
                wx = pl["at"][0] + mx * math.cos(t) + mz * math.sin(t)
                wz = pl["at"][1] - mx * math.sin(t) + mz * math.cos(t)
                X, Z = self._wpt((wx, wz))
                e2 = {"type": "image", "name": what, "x": 0.0, "y": 0.0, "flip": False,
                      "height": float(m.get("height") or 300), "turn": (math.degrees(t) - hdeg) % 360.0}
                ob = self._elem_obj(e2, Z, 1.0, X, "place", y0=0.0)
                if ob:
                    add(ob)

    def _world_ground(self, ctx, cam, t, fog, wet):
        """The world's areas (fields, village ground, ponds), rivers and roads, as flat shapes on the ground."""
        from .worldmap import AREA_KINDS
        wm = self.wm
        w, (ax, az) = wm["world"], wm["anchor"]
        W, H = self.W, self.H
        hy = H * cam.horizon
        far = self.WORLD_FAR * 1.5
        for a in w.areas:
            bx0, bz0, bx1, bz1 = a["bbox"]
            if bx1 < ax - far or bx0 > ax + far or bz1 < az - far or bz0 > az + far:
                continue
            info = AREA_KINDS.get(a["kind"], {})
            col = info.get("ground")
            if not col:
                continue
            ctx.new_path()
            if self._ground_poly(ctx, cam, [self._wpt(q) for q in a["shape"]]):
                rgb = self.bg._shade(hex_to_rgb(col))
                if info.get("water"):
                    self._water_fill(ctx, cam, t, rgb, fog)
                else:
                    g = cairo.LinearGradient(0, hy, 0, H)
                    g.add_color_stop_rgb(0, *mix(rgb, fog, 0.55))
                    g.add_color_stop_rgb(0.25, *mix(rgb, fog, 0.15))
                    g.add_color_stop_rgb(1, *darker(rgb, 0.92))
                    ctx.set_source(g)
                    ctx.fill()
        if not self.bg.water:                                  # (a place with its own water keeps that water)
            for rv in w.rivers:
                ctx.new_path()
                if self._line_strip(ctx, cam, rv["line"], rv["width"] / 2.0):
                    from .styles import WATER_COL
                    self._water_fill(ctx, cam, t, _pw(self.bg._shade(hex_to_rgb(WATER_COL["river"][0]))), fog)
        cols = {"dirt": "#b98e5e", "tar": "#55595f", "stone": "#9a958c", "footpath": "#d8c7a0", "sand": "#e2c48f"}
        clay = bool(self.bg.spec.get("clay"))
        if clay:                                          # the clay village: a warm worn tar, never cold asphalt
            cols = dict(cols, tar="#a08f7c", stone="#a89e90")
        for rd in w.roads:
            if clay and rd.get("style", "dirt") == "tar":   # dusty earth shoulders either side of the tar
                ctx.new_path()
                if self._line_strip(ctx, cam, rd["line"], rd["width"] * 0.85):
                    rgb = darker(self.bg._shade(hex_to_rgb("#b48a5f")), 1 - 0.3 * wet)
                    ctx.set_source_rgb(*mix(rgb, fog, 0.15))
                    ctx.fill()
            ctx.new_path()
            got = self._line_strip(ctx, cam, rd["line"], rd["width"] / 2.0)
            for end in (rd["line"][0], rd["line"][-1]):           # round ends (a path opening into a clearing)
                r_ = rd["width"] * 0.9
                if self._ground_poly(ctx, cam, [self._wpt((end[0] + r_ * math.cos(2 * math.pi * k / 18),
                                                           end[1] + r_ * math.sin(2 * math.pi * k / 18)))
                                                for k in range(18)]):
                    got = True
            if got:
                rgb = darker(self.bg._shade(hex_to_rgb(cols.get(rd.get("style", "dirt"), "#b98e5e"))), 1 - 0.3 * wet)
                g = cairo.LinearGradient(0, hy, 0, H)
                g.add_color_stop_rgb(0, *mix(rgb, fog, 0.5))
                g.add_color_stop_rgb(1, *rgb)
                ctx.set_source(g)
                ctx.fill()
        ctx.new_path()

    def _line_strip(self, ctx, cam, line, half):
        """A band along a world line (metres), as ground quads cut at the near plane. -> something added?"""
        from .worldmap import UNITS
        (ax, az), far = self.wm["anchor"], self.WORLD_FAR * 1.6
        hw = half
        got = False
        for a, b in zip(line, line[1:]):
            if min(math.hypot(a[0] - ax, a[1] - az), math.hypot(b[0] - ax, b[1] - az)) > far and \
                    math.hypot((a[0] + b[0]) / 2 - ax, (a[1] + b[1]) / 2 - az) > far:
                continue
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz) or 1.0
            nx, nz = -dz / L * hw, dx / L * hw
            ex, ez = dx / L * hw * 0.3, dz / L * hw * 0.3          # a little overlap: no seams at the bends
            quad = [(a[0] + nx - ex, a[1] + nz - ez), (a[0] - nx - ex, a[1] - nz - ez),
                    (b[0] - nx + ex, b[1] - nz + ez), (b[0] + nx + ex, b[1] + nz + ez)]
            if self._ground_poly(ctx, cam, [self._wpt(q) for q in quad]):
                got = True
        return got

    def _water_fill(self, ctx, cam, t, col, fog):
        W, H = self.W, self.H
        hy = H * cam.horizon
        gw = cairo.LinearGradient(0, hy, 0, H)
        gw.add_color_stop_rgb(0, *mix(col, fog, 0.45))
        gw.add_color_stop_rgb(1, *col)
        ctx.set_source(gw)
        ctx.fill_preserve()
        ctx.save()
        ctx.clip()
        self._waves(ctx, cam, t, cam.z + 150.0)
        ctx.restore()
        ctx.new_path()

    RING_TOWN = ("house", "hut", "shop", "haystack", "stall", "building", "cottage", "cabin", "mudhouse")
    RING_WORDS = ("tree", "palm", "pine", "banyan", "bush", "rock", "bamboo", "cactus", "boulder", "stones")

    def _ring(self, r, nature, town, dens, path_ok, front_done):
        """The 3D page: the world goes on all around - behind the camera and far to the sides - so the camera
        can turn any way (point-of-view shots, orbits, reverse angles). Far things are the place's own trees,
        bushes and rocks as pictures (cheap), plus a few of its houses."""
        bg = self.bg
        add = self.objs.append
        if bg.spec.get("gas"):                           # a gas giant: nothing stands out there, only clouds
            return
        pool = [(e, pe, False) for e, pe in nature]
        if not pool:                                     # code places: their own trees / bushes / rocks
            for e in bg.elements:
                if e["type"] == "image" and e.get("z") is not None and \
                        any(w in str(e.get("name", "")) for w in self.RING_WORDS):
                    pool.append((e, 1.0, True))
        if not pool and bg.spec.get("planet_place"):    # another planet: rocks (plants only with life)
            pool = [({"type": "rock", "x": 0.0, "y": 0.0, "color": "#7d7a74"}, 1.0, False)]
            if bg.spec.get("life"):
                pool.append(({"type": "bush", "x": 0.0, "y": 0.0}, 1.0, False))
        if not pool:
            pool = [({"type": "tree", "x": 0.0, "y": 0.0}, 1.0, False),
                    ({"type": "bush", "x": 0.0, "y": 0.0}, 1.0, False)]
        lo, hi = -500.0, bg.world_w + 500.0
        Zc = Z_of_z(500.0)
        zfar = FOCAL / 0.42 + 300
        n = int(300 * dens)
        for _ in range(n):
            a = r.uniform(-math.pi, math.pi)
            rad = 1700.0 + (r.random() ** 1.4) * 10500.0
            X, Z = self.cx + rad * math.sin(a), Zc + rad * math.cos(a)
            if lo < X < hi and -2600.0 < Z < zfar:        # the stage and where the camera usually stands
                continue
            if front_done and Z > zfar and abs(X - self.cx) < Z * 1.05 + 1800:
                continue                                 # already filled by the place's own scatter
            if not path_ok(X, Z) or (self.sea_from and Z > self.sea_from - 150):
                continue
            e, pe, pic = r.choice(pool)
            if pic:
                e2 = dict(e, y=0.0, flip=r.random() < 0.5, height=_pic_h(e))
                o = self._elem_obj(e2, Z, r.uniform(0.8, 1.25), X, "scatter", y0=0.0)
            else:
                s_ = real_scale(bg, e["type"], (1.0 / pe), 1.0, kind=e.get("kind")) * r.uniform(0.8, 1.3)
                o = self._elem_obj(dict(e, flip=r.random() < 0.5), Z, s_, X, "scatter", y0=0.0)
            if o:
                add(o)
        town = [(e, pe, False) for e, pe in town]
        if not town:                                     # code places: their own houses / huts / shops
            for e in bg.elements:
                if e["type"] == "image" and e.get("z") is not None and \
                        any(w in str(e.get("name", "")) for w in self.RING_TOWN):
                    town.append((e, 1.0, True))
        for _ in range(int(24 * dens) if town else 0):   # a few houses around (villages go on behind you)
            e, pe, pic = r.choice(town)
            a = r.uniform(-math.pi, math.pi)
            rad = r.uniform(3200, 9000)
            X, Z = self.cx + rad * math.sin(a), Zc + rad * math.cos(a)
            if (lo < X < hi and -2600.0 < Z < zfar) or not path_ok(X, Z):
                continue
            if pic:
                o = self._elem_obj(dict(e, y=0.0, height=_pic_h(e)), Z, r.uniform(0.9, 1.1), X,
                                   "scatter", y0=0.0)
            else:
                o = self._elem_obj(e, Z, real_scale(bg, e["type"], 1.0 / pe) * r.uniform(0.9, 1.15), X, "scatter",
                                   y0=0.0)
            if o:
                add(o)

    def _life(self, r, dens, lo, hi):
        """Film depth + a living world: soft plants right in front of the lens (they slide past when the
        camera tracks), leaves drifting down, birds crossing the sky."""
        bg = self.bg
        add = self.objs.append
        pr = bg.preset
        green = not (pr in ("desert", "desert_village", "snow", "beach", "city", "space") or bg.water and bg.shore_x is None)
        if bg.spec.get("planet_place") and not bg.spec.get("life"):
            green = False                                   # a lifeless planet: no grass, ferns or birds
        alien = [e for e in bg.elements if e.get("type") == "alien_plant"] if bg.spec.get("planet_place") else []
        if alien:                                           # 🪐 a living planet: its OWN plants in front of the lens
            green = False                                   # (no Earth ferns, grass or birds - its flyers are its own)
            x = lo - 400.0
            while x < hi + 400:
                x += r.uniform(500, 900)
                e0 = dict(r.choice(alien))
                e0.update(x=0.0, y=0.0, seed=r.randint(1, 10 ** 6), scale=float(e0.get("scale", 1.0)) * r.uniform(0.8, 1.2))
                add(Obj(x, r.uniform(250, 340), lambda c, t, e0=e0: bg._d_alien_plant(c, e0, t), w=360, tag="xfg"))
        town = pr in ("city", "market", "road", "street", "school_ground", "playground", "station")
        if not self.kit:
            x = lo - 400.0
            while x < hi + 400:
                x += r.uniform(900, 1500) / dens
                sd = r.randint(0, 10 ** 6)
                Z = r.uniform(250, 340)
                if town:
                    add(Obj(x, Z, lambda c, t, sd=sd: _post(c, sd, t), w=200, tag="xfg"))
                elif green:
                    k = r.random()
                    if k < 0.45:
                        add(Obj(x, Z, lambda c, t, sd=sd: grass_tuft(c, sd, t, 1.6), w=300, tag="xfg"))
                    elif k < 0.75:
                        add(Obj(x, Z, lambda c, t, sd=sd: fern(c, sd, t, 0.7), w=360, tag="xfg"))
                    else:
                        fl = r.random() < 0.4
                        add(Obj(x, Z, lambda c, t, sd=sd, fl=fl: bush(c, sd, t, 0.55, "#3f9a3c", fl),
                                w=360, tag="xfg"))
                elif pr in ("desert", "desert_village", "beach"):
                    add(Obj(x, Z, lambda c, t, sd=sd: grass_tuft(c, sd, t, 1.3, "#b9a55a"), w=300, tag="xfg"))
        leafy = (pr in ("jungle", "forest", "park", "garden", "village", "hill_station", "farm", "zoo") or
                 bg.season == "autumn") and not alien
        if leafy and bg.weather not in ("rain", "storm", "snow"):
            cols = ["#d9a441", "#c8702f", "#9bbf4a", "#e0b84a"] if bg.season == "autumn" else ["#6fae46", "#9bbf4a",
                                                                                                "#c9a54a"]
            for _ in range(int(34 * dens)):
                Z = r.uniform(380, 2600)
                X = self.cx + r.uniform(-1, 1) * (Z * 0.9 + 700)
                sd = r.random() * 100
                col = hex_to_rgb(r.choice(cols))
                add(Obj(X, Z, lambda c, t, sd=sd, col=col: _falling_leaf(c, t, sd, col), w=60, tag="leaf"))
        self.birds = green and bg.time in ("morning", "day", "evening", "sunset") and bg.weather in ("clear", None, "")

    def _jungle_kit(self, r, dens, stage_ok, path_ok):
        """Richer painted jungle/forest: tall trees, pines, bushes, ferns deep into the distance."""
        add = self.objs.append
        pine = self.bg.preset == "forest"
        for k in range(int(420 * dens)):
            inner = k % 9 == 0                              # a few trees inside the walking zone
            Z = r.uniform(1350, 2700) if inner else r.uniform(1300, 10000)
            X = self.cx + r.uniform(-1, 1) * (Z * 1.1 + 1600)
            if (not inner and not stage_ok(X, Z)) or not path_ok(X, Z) or (inner and abs(X - self.path_x(Z)) < 450):
                continue
            sd = r.randint(0, 10 ** 6)
            sc = r.uniform(0.85, 1.35)
            leaf = r.choice(["#3b8f3a", "#2f7f35", "#469c3f", "#347f3c"])
            if r.random() < (0.55 if pine else 0.75):
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc, lf=leaf: tree_tall(c, sd, t, sc, lf), w=500 * sc, tag="tree"))
            else:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: tree_pine(c, sd, t, sc), w=360 * sc, tag="tree"))
        for _ in range(int(420 * dens)):
            Z = r.uniform(1200, 6500)
            X = self.cx + r.uniform(-1, 1) * (Z * 1.0 + 1400)
            if not stage_ok(X, Z) or not path_ok(X, Z):
                continue
            sd = r.randint(0, 10 ** 6)
            sc = r.uniform(0.6, 1.2)
            k = r.random()
            if k < 0.35:
                bl, bf = r.choice(["#3f9a3c", "#4aa845", "#368a36"]), r.random() < 0.3
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc, bl=bl, bf=bf: bush(c, sd, t, sc, bl, bf), w=260 * sc, tag="bush"))
            elif k < 0.6:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: fern(c, sd, t, sc), w=300 * sc, tag="fern"))
            elif k < 0.7:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: rock(c, sd, t, sc), w=260 * sc, tag="rock"))
            elif k < 0.9:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: grass_tuft(c, sd, t, sc), w=60, tag="grass"))
            else:
                add(Obj(X, Z, lambda c, t, sd=sd, sc=sc: flower(c, sd, t, sc), w=40, tag="flower"))
        # big plants framing the stage at the bottom of the frame + vines hanging from the canopy
        x = -300.0
        while x < self.bg.world_w + 300:
            x += r.uniform(420, 800)
            sd = r.randint(0, 10 ** 6)
            Z = r.uniform(400, 560)
            kind = r.random()
            if kind < 0.45:
                add(Obj(x, Z, lambda c, t, sd=sd: big_leaf_plant(c, sd, t, 0.6), w=420, tag="fg"))
            elif kind < 0.8:
                add(Obj(x, Z, lambda c, t, sd=sd: fern(c, sd, t, 0.85), w=420, tag="fg"))
            else:
                add(Obj(x, Z, lambda c, t, sd=sd: bush(c, sd, t, 0.9, "#3f9a3c", True), w=420, tag="fg"))
        for x in range(-200, int(self.bg.world_w) + 400, 1700):
            sd = r.randint(0, 10 ** 6)
            add(Obj(x + r.uniform(-250, 250), r.uniform(700, 1000),
                    lambda c, t, sd=sd: hanging_leaves(c, sd, t, 0.45), Y=CAM_H + r.uniform(230, 330), w=500, tag="vine"))

    def _build_rain(self):
        super()._build_rain()
        self.rain_objs = [o for o in self.objs if o.tag == "rain"]
        self.rain_base = [o.Z for o in self.rain_objs]

    # ================================================================== any-direction ground (3D page)
    @staticmethod
    def _cs(cam, X, Z):
        """World (X, Z) -> camera space (across, depth) - the same turn as DepthScene.project."""
        dx, d = X - cam.x, Z - cam.z
        if cam.yaw:
            c, s_ = math.cos(cam.yaw), math.sin(cam.yaw)
            dx, d = dx * c - d * s_, dx * s_ + d * c
        return dx, d

    def _scr(self, cam, u, d, Y=0.0):
        k = FOCAL * self.S * cam.fz / d
        if cam.mirror:
            u = -u
        return self.W / 2 + cam.shift * self.S + u * k, self.H * cam.horizon + (cam.h - Y) * k

    def _ground_poly(self, ctx, cam, pts, near=None):
        """Add a flat polygon on the ground (world (X, Z) points) to the current path, cut at the near plane so
        it is right even when part of it is behind the camera. -> True when something was added."""
        dn = (near or NEAR) + 2.0
        cs = [self._cs(cam, X, Z) for X, Z in pts]
        out = []
        for i, a in enumerate(cs):
            b = cs[(i + 1) % len(cs)]
            ina, inb = a[1] >= dn, b[1] >= dn
            if ina:
                out.append(a)
            if ina != inb:
                f = (dn - a[1]) / (b[1] - a[1])
                out.append((a[0] + (b[0] - a[0]) * f, dn))
        if len(out) < 3:
            return False
        sp = [self._scr(cam, u, d) for u, d in out]
        ctx.move_to(*sp[0])
        for q in sp[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        return True

    def _strip(self, ctx, cam, centre, half, z0, z1):
        """A band on the ground along Z (the path through the whole world), cut at the near plane."""
        z = z0
        prev = None
        while z <= z1:
            X, hw = centre(z), half(z)
            if prev is not None:
                pX, pz, phw = prev
                self._ground_poly(ctx, cam, [(pX - phw, pz), (pX + phw, pz), (X + hw, z), (X - hw, z)])
            prev = (X, z, hw)
            dist = math.hypot(X - cam.x, z - cam.z)
            z += 30.0 + dist * 0.07

    def _pano(self, ctx, cam, fn):
        """Far view all around: fn(ctx) paints the far layers for the front view; it is repeated around a
        360-degree circle and turned with the camera (cam.yaw), so looking back shows land and sky too."""
        W, H = self.W, self.H
        f = FOCAL * self.S * cam.fz
        yaw = (cam.yaw + math.pi) % TAU - math.pi if cam.yaw else 0.0
        C = TAU * f
        for k in ((-1, 0, 1) if (self.full or yaw) else (0,)):
            x0 = W / 2 + (-math.pi + TAU * k - yaw) * f
            x1 = W / 2 + (math.pi + TAU * k - yaw) * f
            if x1 < -5 or x0 > W + 5:
                continue
            ctx.save()
            if cam.mirror:
                ctx.translate(W, 0)
                ctx.scale(-1, 1)
            if self.full or yaw:
                ctx.rectangle(x0, -H, x1 - x0, 3 * H)
                ctx.clip()
            fn(ctx, (TAU * k - yaw) * f + (0.0 if not cam.mirror else 0.0), C)
            ctx.restore()

    # ================================================================== sky + backdrop
    def _real_skyline(self, ctx, dx, cam, sky):
        """the real land's ridges, back to front: forest (crowns along the edge) or bare sandstone cliff; the
        farther, the more of the air's blue haze (clear air after the rains: half gone by ~5.5 km)"""
        W, H, S = self.W, self.H, self.S
        f = FOCAL * S * cam.fz
        hy = H * cam.horizon
        fog = self.fog_now()
        az = [math.radians(a) for a in sky["az"]] + [math.radians(sky["az"][0] + 360)]
        for li, L in enumerate(reversed(sky["layers"])):
            d = float(L["dist"])
            haze = 1.0 - math.exp(-d / 8000.0)
            forest = mix((0.24, 0.40, 0.21), fog, min(0.85, haze + 0.08))
            rockc = mix((0.78, 0.62, 0.47), fog, min(0.85, haze + 0.05))
            bump = math.radians(0.7) * 660.0 / max(660.0, d)      # a tree crown: ~10 m tall seen from d
            el = list(L["elev"]) + [L["elev"][0]]
            rk = list(L["rock"]) + [L["rock"][0]]
            pts = []
            for i in range(len(az) - 1):
                for q in range(4):                                 # in between: the crowns along the ridge
                    u = q / 4.0
                    a = az[i] + (az[i + 1] - az[i]) * u
                    e = math.radians(el[i] + (el[i + 1] - el[i]) * u)
                    if not rk[i]:
                        e += bump * (0.5 + 0.5 * math.sin(a * 900.0 + li * 7.0)) * (0.6 + 0.4 * math.sin(a * 313.0))
                    pts.append((W / 2 + dx + a * f, hy - math.tan(max(e, -0.02)) * f))
            ctx.move_to(pts[0][0], hy + 4 * S)
            for p in pts:
                ctx.line_to(*p)
            ctx.line_to(pts[-1][0], hy + 4 * S)
            ctx.close_path()
            ctx.set_source_rgb(*forest)
            ctx.fill()
            for i in range(len(az) - 1):                           # cliffs: the bare rock face under the edge
                if not rk[i]:
                    continue
                x0, x1 = W / 2 + dx + az[i] * f, W / 2 + dx + az[i + 1] * f
                y0 = hy - math.tan(math.radians(el[i])) * f
                y1 = hy - math.tan(math.radians(el[i + 1])) * f
                drop = max(4 * S, (hy - min(y0, y1)) * 0.45)
                ctx.move_to(x0, y0)
                ctx.line_to(x1, y1)
                ctx.line_to(x1, y1 + drop)
                ctx.line_to(x0, y0 + drop * 0.8)
                ctx.close_path()
                ctx.set_source_rgb(*rockc)
                ctx.fill()

    def _old_cam(self, cam):
        return Camera(cam.x, CAM_H, 1.0)

    def _sky(self, ctx, cam, t):
        bg, W, H, S = self.bg, self.W, self.H, self.S
        oc = self._old_cam(cam)
        saved = bg.weather
        if self.rain > 0.3 and bg.weather not in ("rain", "storm"):
            bg.weather = "rain"
        bg._t = t
        bg.draw_sky(ctx, W, H, t, oc)
        hy = H * cam.horizon
        _palette.hsl_overlay(ctx, "sky", 0, 0, W, hy + 2)          # a world palette: its own sky colour

        def far(c2, dx, C):
            base = c2.get_matrix()
            for e in self.sky_els:
                fn = getattr(bg, "_d_" + e["type"], None)
                if fn:
                    set_layer(c2, oc, e["p"], W, H, S)
                    m = c2.get_matrix()
                    c2.set_matrix(base)
                    c2.translate(dx, 0)
                    c2.transform(m)
                    c2.save()
                    fn(c2, e, t)
                    c2.restore()
            sky_line = bg.spec.get("skyline")
            if sky_line:                                  # 🏔 the REAL ridges round this spot (worldmap.skyline)
                c2.set_matrix(base)
                self._real_skyline(c2, dx, cam, sky_line)
            # far mountains/hills/dunes/sea painted onto the horizon (their ground line sits on the horizon)
            for e in sorted(self.backdrop_els if not sky_line else
                            [e for e in self.backdrop_els if e["type"] in ("sea", "nebula", "solar", "earth", "saturn", "planet")],
                            key=lambda e: e["p"]):
                fn = getattr(bg, "_d_" + e["type"], None)
                if not fn:
                    continue
                set_layer(c2, oc, e["p"], W, H, S)
                y0 = c2.user_to_device(0, 0)[1]
                m = c2.get_matrix()
                c2.set_matrix(base)
                c2.translate(dx, hy - y0 + 3 * S)
                c2.transform(m)
                c2.save()
                fn(c2, e, t)
                c2.restore()
            c2.set_matrix(base)
        self._pano(ctx, cam, far)
        ctx.identity_matrix()
        _palette.hsl_overlay(ctx, "fog", 0, 0, W, hy + 2, alpha=0.35)   # far hills take the world's haze
        bg.weather = saved
        if getattr(self, "birds", False) and self.rain < 0.2:
            _birds(ctx, W, H, S, t, cam, self.seed)
        if self.flash > 0.01:
            ctx.set_source_rgba(0.95, 0.96, 1.0, 0.6 * self.flash)
            ctx.paint()

    # ================================================================== ground
    def _ground(self, ctx, cam, t):
        bg, W, H, S = self.bg, self.W, self.H, self.S
        hy = H * cam.horizon
        fog = self.fog_now()
        wet = self._wetness()[0]                           # stays dark and wet after the rain has stopped
        gr = darker(self.ground, 1 - 0.2 * wet)
        wx = getattr(self, "wx", None) or {}
        if wx.get("changing") and wx.get("snow_cover", 0) > 0.01:    # snow settling: the ground turns white
            gr = mix(gr, (0.93, 0.95, 0.98), 0.85 * wx["snow_cover"])
        from .styles import WATER_COL
        if bg.water and bg.shore_x is None:
            gr = _pw(bg._shade(hex_to_rgb(WATER_COL.get(bg.water, WATER_COL["sea"])[0])))
        g = cairo.LinearGradient(0, hy, 0, H)
        g.add_color_stop_rgb(0, *mix(gr, fog, 0.6))
        g.add_color_stop_rgb(0.2, *mix(gr, fog, 0.2))
        g.add_color_stop_rgb(1, *darker(gr, 0.9))
        ctx.set_source(g)
        ctx.rectangle(0, hy - 1, W, H - hy + 1)
        ctx.fill()
        # rows closer together toward the horizon (texture that shows the ground recedes)
        d = 200.0
        i = 0
        while d < 16000:                                   # (depth along the view: right however the camera turns)
            k = FOCAL * S * cam.fz / d
            y = hy + cam.h * k
            if y < H:
                ctx.set_source_rgba(*darker(gr, 0.85), 0.09 if i % 2 else 0.045)
                ctx.rectangle(0, y, W, max(1.0, 24 * k))
                ctx.fill()
            d += 70 + d * 0.18
            i += 1
        if getattr(bg, "spec", {}).get("ground_paint", True) is not False and not (bg.water and bg.shore_x is None):
            self._paint_patches(ctx, cam, fog, wet)
        if not (bg.water and bg.shore_x is None):              # a world palette: the land in its colour
            _palette.hsl_overlay(ctx, "ground", 0, hy - 1, W, H - hy + 1, alpha=0.8)
        # water: all water, a shore (part land / part water) or a far sea behind a beach
        if self.full or cam.yaw or cam.mirror:
            self._ground_any(ctx, cam, t, fog, wet, gr)
            if wet > 0.02:
                self._wet_ground(ctx, cam, t)
            self._marks(ctx, cam, fog)
            return
        if bg.water:
            wcol = _pw(bg._shade(hex_to_rgb(WATER_COL.get(bg.water, WATER_COL["sea"])[0])))
            if bg.shore_x is not None:
                self._water_side(ctx, cam, bg.shore_x, bg.land_side, wcol, fog, t)
            else:
                self._waves(ctx, cam, t, cam.z + 150)
        elif self.sea_from:
            wcol = _pw(bg._shade(hex_to_rgb(WATER_COL["sea"][0])))
            p = self.project(cam, cam.x, 0, self.sea_from)
            if p and p[1] > hy:
                gw = cairo.LinearGradient(0, hy, 0, p[1])
                gw.add_color_stop_rgb(0, *mix(wcol, fog, 0.45))
                gw.add_color_stop_rgb(1, *wcol)
                ctx.set_source(gw)
                ctx.rectangle(0, hy - 1, W, p[1] - hy + 1)
                ctx.fill()
                ctx.set_source_rgba(1, 1, 1, 0.8)                      # surf line
                ctx.rectangle(0, p[1] - 2 * S, W, 3 * S)
                ctx.fill()
        if self.has_path:
            self._path(ctx, cam, t, fog, wet)
        for r in self.roads:
            self._road(ctx, cam, r, fog, wet)
        if wet > 0.02:
            self._wet_ground(ctx, cam, t)
        self._marks(ctx, cam, fog)

    # ------------------------------------------------------------------ the ground painted in layers
    def ground_kind(self):
        from .background import GROUNDS
        g = getattr(self.bg, "ground", None)
        k = {v: k for k, v in GROUNDS.items()}.get(g) if g else None
        if k is None:
            pr = str(getattr(self.bg, "preset", "")).lower()
            k = "sand" if pr in ("beach", "desert", "desert_village") else ("snow" if pr == "snow" else
                                                                         ("moon" if pr == "space" else "grass"))
        return {"dark_grass": "grass"}.get(k, k)

    def _patch_list(self):
        """Soft patches over the plain ground: darker and lighter grass, dry yellow, bare earth, leaf litter,
        damp spots - the way real ground looks (3D Game Environments: terrain painted in layers). Built once."""
        got = getattr(self, "_gpatches", None)
        if got is not None:
            return got
        rng = random.Random(stable_hash(f"ground{self.bg.preset}{self.bg.world_w}") % 100000)
        g = self.ground
        kind = self.ground_kind()
        if kind == "grass":
            pal = [(darker(g, 0.84), 0.5), (mix(g, (0.8, 0.72, 0.38), 0.45), 0.45), (lighter(g, 0.12), 0.4),
                   (mix(g, (0.55, 0.42, 0.28), 0.55), 0.4), (mix(g, (0.45, 0.33, 0.18), 0.35), 0.3)]
        elif kind in ("dirt", "mud"):
            pal = [(darker(g, 0.86), 0.45), (lighter(g, 0.1), 0.45), (mix(g, (0.5, 0.36, 0.22), 0.35), 0.35),
                   (mix(g, (0.42, 0.6, 0.28), 0.5), 0.45), (mix(g, (0.62, 0.52, 0.36), 0.4), 0.35)]
        elif kind == "sand":
            pal = [(lighter(g, 0.08), 0.45), (darker(g, 0.93), 0.4), (mix(g, (0.85, 0.7, 0.45), 0.4), 0.35)]
        elif kind == "snow":
            pal = [(mix(g, (0.75, 0.83, 0.93), 0.45), 0.4), (lighter(g, 0.05), 0.4)]
        elif kind == "moon":                               # grey dust: lighter and darker grey, no green / brown
            pal = [(darker(g, 0.8), 0.45), (lighter(g, 0.1), 0.4), (darker(g, 0.9), 0.35)]
        elif kind in ("road", "stone", "tiles"):
            pal = [(darker(g, 0.9), 0.35), (lighter(g, 0.06), 0.3)]
        else:
            pal = [(darker(g, 0.9), 0.3)]
        out = []
        lvl = str((self.wm or {}).get("detail") or "high").lower() if self.wm else "high"
        n = {"low": 40, "medium": 75}.get(lvl, 110)
        for i in range(n):
            u = rng.random()
            Z = FOCAL * 0.6 + 9500.0 * u * u
            X = self.cx + rng.uniform(-1.0, 1.0) * (2500.0 + Z * 0.9)
            r0 = rng.uniform(140, 520) * (1.0 + Z / 5000.0)
            col, al = pal[rng.randrange(len(pal))]
            m = 11
            ph = rng.uniform(0, TAU)
            pts = []
            for j in range(m):
                a = TAU * j / m + ph
                rr = r0 * (0.7 + 0.3 * math.sin(3 * a + i) + rng.uniform(-0.12, 0.12))
                pts.append((X + math.cos(a) * rr, Z + math.sin(a) * rr * rng.uniform(0.55, 0.9)))
            out.append((pts, col, al * rng.uniform(0.6, 1.0), Z))
        for (X, Z, r) in getattr(self, "ground_marks", []) or []:     # worn earth where people stand and work
            wc = mix(g, (0.62, 0.5, 0.36), 0.55) if kind == "grass" else lighter(g, 0.07)
            pts = []
            for j in range(12):
                a = TAU * j / 12
                rr = r * (0.85 + 0.2 * math.sin(2 * a + X * 0.01))
                pts.append((X + math.cos(a) * rr, Z + math.sin(a) * rr * 0.7))
            out.append((pts, wc, 0.28 if kind == "grass" else 0.22, Z))
        out.sort(key=lambda p: -p[3])
        self._gpatches = out
        return out

    def _paint_patches(self, ctx, cam, fog, wet):
        for pts, col, al, Z in self._patch_list():
            d = Z - cam.z if not (cam.yaw or cam.mirror) else abs(Z - cam.z) + 1.0
            if d > 14000:
                continue
            ctx.new_path()
            if self._ground_poly(ctx, cam, pts):
                k = clamp(d / 9000.0, 0.0, 1.0)             # far patches fade into the haze
                c = mix(darker(col, 1 - 0.2 * wet), fog, 0.55 * k)
                ctx.set_source_rgba(c[0], c[1], c[2], al * (1.0 - 0.6 * k))
                ctx.fill()
        ctx.new_path()

    def _marks(self, ctx, cam, fog):
        """Footprints and tyre tracks (set each frame by the renderer in self.decals)."""
        for dc in getattr(self, "decals", None) or []:
            ctx.new_path()
            if dc[0] == "ellipse":
                _k, X, Z, rx, rz, ang, rgba = dc
                ca, sa = math.cos(ang), math.sin(ang)
                pts = [(X + rx * math.cos(a) * ca - rz * math.sin(a) * sa, Z + rx * math.cos(a) * sa + rz * math.sin(a) * ca)
                       for a in [TAU * j / 8 for j in range(8)]]
                if self._ground_poly(ctx, cam, pts):
                    ctx.set_source_rgba(*rgba)
                    ctx.fill()
            elif dc[0] == "strip":
                _k, line, half, rgba = dc
                for (X0, Z0), (X1, Z1) in zip(line, line[1:]):
                    dx, dz = X1 - X0, Z1 - Z0
                    L = math.hypot(dx, dz)
                    if L < 1e-6:
                        continue
                    nx, nz = -dz / L * half, dx / L * half
                    self._ground_poly(ctx, cam, [(X0 - nx, Z0 - nz), (X0 + nx, Z0 + nz), (X1 + nx, Z1 + nz),
                                                 (X1 - nx, Z1 - nz)])
                ctx.set_source_rgba(*rgba)
                ctx.fill()
        ctx.new_path()

    def _ground_any(self, ctx, cam, t, fog, wet, gr):
        """The ground for a camera that can look any way: water, sea, the path and roads as real flat shapes
        (cut at the near plane), so they stay right when the camera turns or looks back."""
        bg, W, H, S = self.bg, self.W, self.H, self.S
        hy = H * cam.horizon
        from .styles import WATER_COL
        big = 80000.0

        def water_fill(col):
            gw = cairo.LinearGradient(0, hy, 0, H)
            gw.add_color_stop_rgb(0, *mix(col, fog, 0.45))
            gw.add_color_stop_rgb(1, *col)
            ctx.set_source(gw)
            ctx.fill_preserve()
            ctx.save()
            ctx.clip()
            self._waves(ctx, cam, t, cam.z + 150.0)
            ctx.restore()
            ctx.new_path()

        if self.wm:
            self._world_ground(ctx, cam, t, fog, wet)
        if bg.water and bg.shore_x is not None:
            wcol = _pw(bg._shade(hex_to_rgb(WATER_COL.get(bg.water, WATER_COL["sea"])[0])))
            Xs = X_of(bg.shore_x, 1.0, self.cx)
            far = Xs + big if bg.land_side == "left" else Xs - big
            ctx.new_path()
            if self._ground_poly(ctx, cam, [(Xs, -big), (far, -big), (far, big), (Xs, big)]):
                water_fill(wcol)
            ctx.new_path()                                       # sandy edge along the shore
            if self._ground_poly(ctx, cam, [(Xs - 5, -big), (Xs + 5, -big), (Xs + 5, big), (Xs - 5, big)]):
                ctx.set_source_rgba(0.93, 0.85, 0.62, 0.9)
                ctx.fill()
        elif bg.water:
            ctx.new_path()
            ctx.rectangle(0, hy, W, H - hy)
            ctx.save()
            ctx.clip()
            self._waves(ctx, cam, t, cam.z + 150.0)
            ctx.restore()
            ctx.new_path()
        elif self.sea_from:
            wcol = _pw(bg._shade(hex_to_rgb(WATER_COL["sea"][0])))
            ctx.new_path()
            if self._ground_poly(ctx, cam, [(-big, self.sea_from), (big, self.sea_from), (big, big), (-big, big)]):
                water_fill(wcol)
            ctx.new_path()
            if self._ground_poly(ctx, cam, [(-big, self.sea_from - 8), (big, self.sea_from - 8),
                                            (big, self.sea_from + 8), (-big, self.sea_from + 8)]):
                ctx.set_source_rgba(1, 1, 1, 0.8)
                ctx.fill()
        if self.has_path:                                        # the path runs right through the world
            ctx.new_path()
            self._strip(ctx, cam, self.path_x, lambda z: 150 + 40 * math.sin(z / 900.0),
                        min(cam.z, 0.0) - 14000.0, max(cam.z, 0.0) + 14000.0)
            pc = darker(self.path_col, 1 - 0.3 * wet)
            pg = cairo.LinearGradient(0, hy, 0, H)
            pg.add_color_stop_rgb(0, *mix(pc, fog, 0.5))
            pg.add_color_stop_rgb(1, *pc)
            ctx.set_source(pg)
            ctx.fill()
            if self.path_style in ("road", "tar", "highway"):
                ctx.new_path()
                z = min(cam.z, 0.0) - 14000.0
                n = 0
                while z < max(cam.z, 0.0) + 14000.0:
                    if n % 2 == 0:
                        X0, X1 = self.path_x(z), self.path_x(z + 170)
                        self._ground_poly(ctx, cam, [(X0 - 7, z), (X0 + 7, z), (X1 + 7, z + 170), (X1 - 7, z + 170)])
                    z += 170
                    n += 1
                ctx.set_source_rgba(0.96, 0.95, 0.9, 0.85)
                ctx.fill()
        for r in self.roads:                                     # roads across the place
            Z0, Z1 = Z_of_z(float(r.get("z0", 0))), Z_of_z(float(r.get("z1", r.get("z", 200))))
            style = str(r.get("style", "tar")).lower()
            col = darker(self.bg._shade(hex_to_rgb(ROAD_COLORS.get(style, ROAD_COLORS["tar"]))), 1 - 0.25 * wet)
            ctx.new_path()
            if self._ground_poly(ctx, cam, [(-big, Z0), (big, Z0), (big, Z1), (-big, Z1)]):
                ctx.set_source_rgb(*mix(col, fog, 0.1))
                ctx.fill()
            if style in ("tar", "road", "highway"):
                ctx.new_path()
                Zm = (Z0 + Z1) / 2.0
                x = cam.x - 8000 - (cam.x % 320)
                while x < cam.x + 8000:
                    self._ground_poly(ctx, cam, [(x, Zm - 6), (x + 170, Zm - 6), (x + 170, Zm + 6), (x, Zm + 6)])
                    x += 320
                ctx.set_source_rgba(0.98, 0.9, 0.35, 0.9)
                ctx.fill()
        ctx.new_path()

    def _waves(self, ctx, cam, t, z_from, x_range=None):
        W, H, S = self.W, self.H, self.S
        d = max(NEAR + 5.0, z_from - cam.z)
        z = cam.z + d
        while z < cam.z + 12000:
            k = FOCAL * S * cam.fz / (z - cam.z)
            p = (0.0, H * cam.horizon + cam.h * k, k)
            if p[1] < H:
                span = 240 * k * S / S
                off = (t * 40 * k + z * 0.37) % max(span, 1)
                ctx.set_source_rgba(1, 1, 1, clamp(0.08 + 0.25 * k, 0, 0.35))
                ctx.set_line_width(max(0.7, 2.2 * k))
                x = -span + off
                while x < W + span:
                    ctx.move_to(x, p[1])
                    ctx.curve_to(x + span * 0.15, p[1] + 3 * k, x + span * 0.3, p[1] + 3 * k, x + span * 0.45, p[1])
                    x += span
                ctx.stroke()
            z += 90 + (z - cam.z) * 0.22

    def _water_side(self, ctx, cam, shore_x, land_side, wcol, fog, t):
        W, H = self.W, self.H
        hy = H * cam.horizon
        pts = []
        for Z in (cam.z + NEAR + 5, cam.z + 200, cam.z + 600, cam.z + 1500, cam.z + 4000, cam.z + 20000):
            p = self.project(cam, X_of(shore_x, 1.0, self.cx), 0, Z)
            if p:
                pts.append((p[0], p[1]))
        if len(pts) < 2:
            return
        edge = W + 10 if (land_side == "left") != bool(cam.mirror) else -10
        ctx.move_to(*pts[0])
        for q in pts[1:]:
            ctx.line_to(*q)
        ctx.line_to(edge, hy)
        ctx.line_to(edge, H + 10)
        ctx.line_to(pts[0][0], H + 10)
        ctx.close_path()
        gw = cairo.LinearGradient(0, hy, 0, H)
        gw.add_color_stop_rgb(0, *mix(wcol, fog, 0.45))
        gw.add_color_stop_rgb(1, *wcol)
        ctx.set_source(gw)
        ctx.fill_preserve()
        ctx.save()
        ctx.clip()
        self._waves(ctx, cam, t, cam.z + 150)
        ctx.restore()
        ctx.move_to(*pts[0])                                   # sandy edge along the shore
        for q in pts[1:]:
            ctx.line_to(*q)
        ctx.set_source_rgba(0.93, 0.85, 0.62, 0.9)
        ctx.set_line_width(6 * self.S)
        ctx.stroke()

    def _path(self, ctx, cam, t, fog, wet):
        H = self.H
        zs = []
        z = cam.z + NEAR + 20
        while z < cam.z + 14000:
            zs.append(z)
            z += 30 + (z - cam.z) * 0.08
        left, right = [], []
        for zz in zs:
            half = 150 + 40 * math.sin(zz / 900.0)
            pl = self.project(cam, self.path_x(zz) - half, 0, zz)
            pr = self.project(cam, self.path_x(zz) + half, 0, zz)
            if pl and pr:
                left.append(pl[:2])
                right.append(pr[:2])
        if len(left) < 3:
            return
        ctx.move_to(*left[0])
        for q in left[1:]:
            ctx.line_to(*q)
        for q in reversed(right):
            ctx.line_to(*q)
        ctx.close_path()
        pc = darker(self.path_col, 1 - 0.3 * wet)
        pg = cairo.LinearGradient(0, H * cam.horizon, 0, H)
        pg.add_color_stop_rgb(0, *mix(pc, fog, 0.5))
        pg.add_color_stop_rgb(1, *pc)
        ctx.set_source(pg)
        ctx.fill()
        if self.path_style in ("road", "tar", "highway"):          # a real road: white centre dashes
            ctx.set_source_rgba(0.96, 0.95, 0.9, 0.85)
            k = 0
            for z0, z1 in zip(zs, zs[1:]):
                k += 1
                if k % 3:
                    continue
                a = self.project(cam, self.path_x(z0) - 7, 0, z0)
                b = self.project(cam, self.path_x(z0) + 7, 0, z0)
                c = self.project(cam, self.path_x(z1) + 7, 0, z1)
                d = self.project(cam, self.path_x(z1) - 7, 0, z1)
                if a and b and c and d:
                    ctx.move_to(*a[:2])
                    for q in (b, c, d):
                        ctx.line_to(*q[:2])
                    ctx.close_path()
                    ctx.fill()
            return
        rr = random.Random(5)
        ctx.set_source_rgba(*darker(self.path_col, 0.75), 0.45)
        for _ in range(140):
            zz = rr.uniform(300, 7000)
            if zz - cam.z < NEAR + 40:
                continue
            p = self.project(cam, self.path_x(zz) + rr.uniform(-130, 130), 0, zz)
            if p and p[1] < H:
                ctx.save()
                ctx.translate(p[0], p[1])
                ctx.scale(max(0.8, 9 * p[2]), max(0.5, 4 * p[2]))
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.restore()
                ctx.fill()

    def _road(self, ctx, cam, r, fog, wet):
        """A road running ACROSS the place at a depth (place JSON "road"): asphalt with lane marks, dirt or a
        footpath, lying flat on the ground."""
        Z0, Z1 = Z_of_z(float(r.get("z0", 0))), Z_of_z(float(r.get("z1", r.get("z", 200))))
        Z0 = max(Z0, cam.z + NEAR + 5)
        if Z1 <= Z0:
            return
        span = 60000.0
        pts = [self.project(cam, cam.x - span, 0, Z0), self.project(cam, cam.x + span, 0, Z0),
               self.project(cam, cam.x + span, 0, Z1), self.project(cam, cam.x - span, 0, Z1)]
        if not all(pts):
            return
        style = str(r.get("style", "tar")).lower()
        col = hex_to_rgb(ROAD_COLORS.get(style, ROAD_COLORS["tar"]))
        col = darker(self.bg._shade(col), 1 - 0.25 * wet)
        ctx.move_to(*pts[0][:2])
        for q in pts[1:]:
            ctx.line_to(*q[:2])
        ctx.close_path()
        g = cairo.LinearGradient(0, pts[2][1], 0, pts[0][1])
        g.add_color_stop_rgb(0, *mix(col, fog, 0.25))
        g.add_color_stop_rgb(1, *col)
        ctx.set_source(g)
        ctx.fill()
        if style in ("tar", "road", "highway"):
            ZL = [Z0 + (Z1 - Z0) * f for f in (0.04, 0.96)]
            ctx.set_source_rgba(0.93, 0.93, 0.9, 0.8)      # edge lines
            for ZZ in ZL:
                a, b = self.project(cam, cam.x - span, 0, ZZ), self.project(cam, cam.x + span, 0, ZZ)
                c, d = self.project(cam, cam.x + span, 0, ZZ + 8), self.project(cam, cam.x - span, 0, ZZ + 8)
                if a and b and c and d:
                    ctx.move_to(*a[:2])
                    for q in (b, c, d):
                        ctx.line_to(*q[:2])
                    ctx.close_path()
                    ctx.fill()
            Zm = (Z0 + Z1) / 2.0                             # dashed centre line
            ctx.set_source_rgba(0.98, 0.9, 0.35, 0.9)
            x = cam.x - 6000 - (cam.x % 320)
            while x < cam.x + 6000:
                a, b = self.project(cam, x, 0, Zm - 6), self.project(cam, x + 170, 0, Zm - 6)
                c, d = self.project(cam, x + 170, 0, Zm + 6), self.project(cam, x, 0, Zm + 6)
                if a and b and c and d:
                    ctx.move_to(*a[:2])
                    for q in (b, c, d):
                        ctx.line_to(*q[:2])
                    ctx.close_path()
                    ctx.fill()
                x += 320

    # ================================================================== frame
    def render(self, ctx, cam, t, actors=()):
        from . import scene3d as _s3
        _s3.CLAY[0] = bool((getattr(self.bg, "spec", None) or {}).get("clay"))
        yw = cam.yaw or 0.0
        c_, s_ = math.cos(yw), math.sin(yw)
        for o, z0 in zip(self.rain_objs, self.rain_base):     # the rain volume travels with the camera
            o.X, o.Z = cam.x + z0 * s_, cam.z + z0 * c_
        if not hasattr(self, "_shafts0"):
            self._shafts0 = self.shafts
        if yw or cam.mirror:                                  # sun shafts only while the sun is in view
            rel = ((0.45 - yw) + math.pi) % TAU - math.pi
            self.shafts = self._shafts0 and abs(rel) < 0.7 and not cam.mirror
        else:
            self.shafts = self._shafts0
        super().render(ctx, cam, t, actors)


# ---------------------------------------------------------------------------- small living things
def _post(ctx, sd, t):
    """A street bollard / wooden post right in front of the lens."""
    r = random.Random(sd)
    h = r.uniform(120, 190)
    col = r.choice([(0.35, 0.33, 0.32), (0.55, 0.38, 0.22), (0.8, 0.75, 0.2)])
    ctx.set_source_rgb(*col)
    ctx.rectangle(-9, 0, 18, h)
    ctx.fill()
    ctx.set_source_rgb(*darker(col, 0.7))
    ctx.rectangle(-11, h - 6, 22, 8)
    ctx.fill()


def _falling_leaf(ctx, t, sd, col):
    """A leaf drifting down in a loop (world units, y-up), turning as it falls."""
    fall = 420.0
    y = fall - ((t * 38.0 + sd * 13.0) % fall) + 30.0
    x = 40.0 * math.sin(t * 1.1 + sd) + 12.0 * math.sin(t * 2.7 + sd * 2)
    ctx.translate(x, y)
    ctx.rotate(math.sin(t * 2.0 + sd) * 1.2)
    ctx.scale(1.0, 0.45 + 0.55 * abs(math.sin(t * 1.7 + sd)))
    ctx.move_to(-9, 0)
    ctx.curve_to(-4, 6, 4, 6, 9, 0)
    ctx.curve_to(4, -6, -4, -6, -9, 0)
    ctx.set_source_rgb(*col)
    ctx.fill()


def _birds(ctx, W, H, S, t, cam, seed):
    """A flock crossing the sky every ~16 s: real flocking (boids - apart, same way, together), so it swirls and
    stretches like birds do instead of a fixed V. Moves a little against the camera for parallax."""
    from . import boids
    period = 16.0
    for k in range(2):
        tt = t + k * 8.3 + seed % 7
        n = int(tt / period)
        ph = (tt % period) / period
        if ph > 0.8:
            continue
        sim = boids.sky_flock(int(W), int(H), int(seed * 7 + n * 13 + k) % 997, period=period * 0.8,
                              n=7 + (n + k) % 6)
        boids.draw_birds(ctx, sim, ph * period, S, alpha=0.75, size=9 + 2 * k, dx=-cam.x * 0.04 * S)