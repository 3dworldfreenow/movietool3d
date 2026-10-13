"""✏🧊 Stick 3D: the sketch look in a real 3D world (step 1 - a test).

Everything is a few simple 3D shapes (box, prism roof, cylinder, cone, low ball, dome) made to be drawn as ink:
each frame the shapes are seen through a real camera (any angle, moving), and only the lines a hand would draw
are inked - the outline (silhouette) and the hard corners (creases) - with the faces filled with paper so things in
front hide things behind. People are the same black stickmen, their pose skeleton set into 3D (near limbs one
side, far limbs the other), so they can face any way; the round head turns its face to where they look.
No colour, no light, no textures: that is what keeps it fast.

World units: y up, the ground is y = 0; 1 unit = 1 story unit (a person is about 330 tall).
"""
import math
import random
import zlib

import sys

import cairo
import numpy as np

from . import sketch
from . import stick3d_places as places
from . import stick3d_animals
from .sketch import Pen, INK, PENCIL, PAPER

# the look: "lines" = ink only; "bold" = + thick outlines / thin inside lines + a soft shadow under everything;
# "wash" = bold + soft watercolour inside the shapes (the storybook look)
STYLE = ["wash"]            # "lines" | "bold" | "wash" | "flat"
FLAT_SKY = (0.62, 0.84, 0.97)
FLAT_GROUND = (0.93, 0.83, 0.58)
SKY_NOW = [FLAT_SKY]        # the sky of the place being drawn (far things fade into it)
FLAT_INK = (0.16, 0.14, 0.18)
FLAT_SAT = 1.08             # flat colours a touch brighter than the watercolour ones
WASH = {"hut": (0.86, 0.71, 0.52), "hut_roof": (0.74, 0.55, 0.30), "house": (0.94, 0.86, 0.72),
        "house_roof": (0.72, 0.36, 0.27), "door": (0.55, 0.38, 0.25), "window": (0.42, 0.55, 0.66),
        "trunk": (0.55, 0.40, 0.28), "crown": (0.52, 0.70, 0.40), "haystack": (0.90, 0.76, 0.42),
        "well": (0.68, 0.66, 0.62), "well_post": (0.55, 0.40, 0.28), "well_beam": (0.55, 0.40, 0.28),
        "cot": (0.66, 0.48, 0.32), "cot_leg": (0.55, 0.40, 0.28), "fence": (0.60, 0.46, 0.32),
        "fence_rail": (0.60, 0.46, 0.32),
        # 2030 (stick3d_places.village_2030): sun-bleached, dusty, a few strong colours for the people's things
        "mud": (0.80, 0.62, 0.42), "house30": (0.90, 0.80, 0.66), "roof30": (0.70, 0.60, 0.50),
        "solar": (0.22, 0.32, 0.52), "tank": (0.42, 0.52, 0.60), "cloth": (0.86, 0.46, 0.30),
        "bamboo": (0.62, 0.48, 0.30), "drum": (0.30, 0.48, 0.62), "rubble": (0.70, 0.62, 0.54),
        "deadwood": (0.46, 0.34, 0.26), "net": (0.93, 0.90, 0.80), "wilted": (0.62, 0.52, 0.28),
        "cart": (0.60, 0.42, 0.26), "town": (0.88, 0.78, 0.64), "temple": (0.92, 0.84, 0.70),
        "shikhara": (0.90, 0.76, 0.56), "flag": (0.95, 0.55, 0.15), "tower": (0.50, 0.50, 0.54),
        "river": (0.55, 0.62, 0.62), "hill": (0.84, 0.70, 0.62),
        # 2026 (stick3d_places.home_2026 / field_2026): the ordinary green Madhya Pradesh before
        "wall26": (0.96, 0.90, 0.76), "roof26": (0.80, 0.74, 0.66), "tank26": (0.25, 0.25, 0.27),
        "steel": (0.72, 0.74, 0.78), "station": (0.98, 0.98, 0.96), "antenna": (0.20, 0.20, 0.22),
        "tin": (0.66, 0.70, 0.74), "bench": (0.62, 0.44, 0.28), "laptop": (0.30, 0.31, 0.34),
        "screen": (0.30, 0.62, 0.90), "crate": (0.82, 0.66, 0.44), "crop": (0.46, 0.68, 0.30),
        "road": (0.74, 0.62, 0.46), "concrete": (0.78, 0.78, 0.76), "hill26": (0.62, 0.72, 0.66),
        # the basement and the land
        "concrete_wall": (0.66, 0.67, 0.69), "ceiling": (0.58, 0.59, 0.61), "tube": (0.99, 0.99, 0.95),
        "monitor_map": (0.20, 0.55, 0.45), "monitor_graph": (0.85, 0.35, 0.30), "monitor_term": (0.15, 0.25, 0.40),
        "chair": (0.25, 0.27, 0.30), "rack": (0.20, 0.21, 0.24), "led_green": (0.30, 0.90, 0.50),
        "led_red": (0.95, 0.30, 0.25), "whiteboard": (0.97, 0.97, 0.95), "pit": (0.55, 0.42, 0.30),
        "pit_deep": (0.32, 0.24, 0.18), "mound": (0.66, 0.52, 0.36), "track": (0.25, 0.25, 0.27),
        "digger": (0.96, 0.74, 0.15),
        # the farm (stick3d_places.farm_2026): lush storybook greens
        "sand": (0.90, 0.78, 0.52), "soil": (0.52, 0.38, 0.26), "cabbage": (0.58, 0.80, 0.42),
        "leaf": (0.36, 0.62, 0.28), "tomato": (0.92, 0.32, 0.25), "flower_o": (0.98, 0.58, 0.18),
        "flower_y": (0.99, 0.86, 0.30), "wood": (0.62, 0.48, 0.34), "woodwall": (0.66, 0.56, 0.44),
        "tinroof": (0.66, 0.68, 0.70), "brick": (0.70, 0.36, 0.28), "barn": (0.78, 0.30, 0.24),
        "barnroof": (0.48, 0.32, 0.26), "leaf_dark": (0.30, 0.54, 0.30), "greenhill": (0.60, 0.78, 0.42),
        "mountain": (0.48, 0.62, 0.78), "grass2": (0.44, 0.62, 0.27),
        "limewall": (0.95, 0.90, 0.80), "tiles": (0.76, 0.40, 0.28), "water": (0.42, 0.66, 0.88),
        "ceiling_wood": (0.80, 0.70, 0.56), "fan": (0.55, 0.36, 0.26), "window_view": (0.62, 0.84, 0.96),
        "window_field": (0.52, 0.74, 0.36), "map_land": (0.62, 0.82, 0.62), "hatch": (0.42, 0.45, 0.50),
        "hole": (0.10, 0.10, 0.12), "car_glass": (0.14, 0.18, 0.24), "car_win": (0.45, 0.78, 0.96), "car_win_dark": (0.16, 0.20, 0.26),
        "car_trim": (0.45, 0.46, 0.48),
        "car_white": (0.97, 0.97, 0.97), "hub": (0.80, 0.82, 0.86), "siren_red": (0.95, 0.15, 0.12),
        "siren_blue": (0.15, 0.35, 0.95), "dust": (0.86, 0.78, 0.62), "tyre": (0.08, 0.08, 0.09),
        "headlight": (1.0, 0.97, 0.80), "taillight": (0.85, 0.12, 0.10), "panel_wall": (0.86, 0.80, 0.70), "city_sky": (0.78, 0.86, 0.92),
        "citytower": (0.70, 0.74, 0.78), "bigscreen": (0.12, 0.20, 0.30), "table_top": (0.46, 0.30, 0.20),
        "table_base": (0.36, 0.24, 0.16), "paper": (0.97, 0.97, 0.95), "limewall_in": (0.98, 0.95, 0.86), "redfloor": (0.66, 0.30, 0.24),
        # the film's bigger places (stick3d_places: city_street, highway, site_2027, ruined_city)
        "asphalt": (0.36, 0.37, 0.40), "asphalt_old": (0.33, 0.31, 0.30), "lane": (0.96, 0.94, 0.86),
        "bldg1": (0.86, 0.78, 0.66), "bldg2": (0.74, 0.76, 0.80), "bldg3": (0.90, 0.86, 0.78),
        "bldg4": (0.70, 0.62, 0.56), "bldg_win": (0.30, 0.42, 0.55), "win_lit": (1.0, 0.86, 0.50),
        "ministry": (0.86, 0.66, 0.50), "ministry_top": (0.80, 0.58, 0.44), "column": (0.93, 0.86, 0.76),
        "steps": (0.88, 0.80, 0.70), "door_dark": (0.30, 0.22, 0.18), "flag_saffron": (1.0, 0.60, 0.20),
        "flag_white": (0.98, 0.98, 0.96), "flag_green": (0.10, 0.53, 0.22), "lamppost": (0.40, 0.42, 0.45),
        "lamp": (1.0, 0.92, 0.62), "barrier": (0.95, 0.80, 0.20), "sign_green": (0.12, 0.50, 0.30),
        "pit_wall": (0.72, 0.56, 0.38), "pit_wall2": (0.64, 0.48, 0.32), "pit_floor": (0.82, 0.70, 0.50),
        "tunnel": (0.10, 0.10, 0.12), "crane": (0.98, 0.78, 0.16), "cabin": (0.86, 0.90, 0.95),
        "truck": (0.98, 0.72, 0.16), "truck_bed": (0.90, 0.62, 0.14), "ruin": (0.62, 0.58, 0.54),
        "ruin2": (0.52, 0.48, 0.46), "ruin_dark": (0.38, 0.34, 0.33), "crack": (0.14, 0.12, 0.12),
        "rubble": (0.56, 0.52, 0.48), "deadtree": (0.30, 0.24, 0.20), "smoke": (0.36, 0.33, 0.34),
        "hill_dead": (0.56, 0.42, 0.36), "mach_yellow": (0.99, 0.75, 0.15), "mach_orange": (0.97, 0.56, 0.12),
        "mach_grey": (0.47, 0.48, 0.51), "mach_dark": (0.29, 0.30, 0.33), "mach_tyre": (0.40, 0.41, 0.44),
        "mach_win": (0.24, 0.60, 0.72), "gravel": (0.50, 0.45, 0.40), "rock": (0.46, 0.38, 0.32),
        "rock2": (0.40, 0.33, 0.28), "steel_rib": (0.42, 0.44, 0.48), "tube_light": (1.0, 0.95, 0.76),
        "rail": (0.56, 0.56, 0.58), "sleeper": (0.42, 0.31, 0.22), "cart": (0.52, 0.36, 0.28),
        "ore": (0.20, 0.18, 0.18), "cutter": (0.62, 0.62, 0.64), "silo": (0.80, 0.82, 0.86),
        "office_wall": (0.90, 0.86, 0.78), "office_wall2": (0.70, 0.76, 0.80), "turbine": (0.95, 0.96, 0.97),
        "sea_night": (0.10, 0.16, 0.30), "citytower_n": (0.22, 0.24, 0.32), "bldg_win_n": (0.14, 0.16, 0.22),
        "corn": (0.36, 0.60, 0.22), "corn_dark": (0.26, 0.46, 0.18), "track": (0.76, 0.66, 0.50),
        "tuft": (0.62, 0.58, 0.30), "mud_track": (0.66, 0.48, 0.24), "rut": (0.52, 0.36, 0.18), "mud_edge": (0.42, 0.28, 0.14),
        "puddle": (0.52, 0.70, 0.84), "puddle_rim": (0.38, 0.25, 0.13), "puddle_shine": (0.80, 0.90, 0.96),
        "grass_edge": (0.36, 0.62, 0.22), "soy": (0.50, 0.72, 0.30), "soy_row": (0.28, 0.48, 0.16),
        "grass_mid": (0.46, 0.58, 0.28), "hill_blue": (0.38, 0.47, 0.60), "mud_splash": (0.42, 0.32, 0.22), "car_gap": (0.10, 0.10, 0.12), "car_trim_dark": (0.13, 0.13, 0.15), "gauge_cap": (0.86, 0.68, 0.14),
        "ship": (0.30, 0.32, 0.38), "charred": (0.16, 0.14, 0.13), "flag_red": (0.80, 0.18, 0.20), "flag_blue": (0.16, 0.24, 0.52),
        "flood": (0.46, 0.47, 0.42), "sea_storm": (0.20, 0.29, 0.34), "foam": (0.86, 0.91, 0.92), "sea_face": (0.13, 0.19, 0.23),
        "asphalt_wet": (0.24, 0.25, 0.28), "kerb": (0.62, 0.62, 0.60), "palm_trunk": (0.52, 0.42, 0.32),
        "dirt_road": (0.80, 0.64, 0.44), "grass_edge_flat": (0.40, 0.56, 0.26), "pond_bank": (0.36, 0.52, 0.26),
        "lily": (0.30, 0.58, 0.30), "mango_crown": (0.30, 0.52, 0.24), "mango": (0.98, 0.62, 0.16),
        "banana_stem": (0.50, 0.66, 0.34), "banana_leaf": (0.40, 0.66, 0.28), "bike_frame": (0.12, 0.12, 0.14),
        "seat_black": (0.20, 0.16, 0.12), "cow": (0.95, 0.94, 0.90), "cow_spot": (0.14, 0.13, 0.13),
        "goat": (0.92, 0.90, 0.86), "hen": (0.66, 0.36, 0.20), "wall_blue": (0.44, 0.70, 0.86),
        "wall_blue_trim": (0.92, 0.92, 0.88), "wall_yellow": (0.96, 0.82, 0.38), "wall_yellow_trim": (0.92, 0.92, 0.88),
        "post": (0.50, 0.38, 0.28), "plinth": (0.78, 0.72, 0.64), "counter": (0.62, 0.44, 0.28),
        "jar_red": (0.90, 0.30, 0.22), "jar_yellow": (0.98, 0.80, 0.25), "jar_green": (0.40, 0.72, 0.34),
        "shop_sign": (0.98, 0.84, 0.30), "awning": (0.88, 0.28, 0.22), "bamboo": (0.78, 0.66, 0.42),
        "tank": (0.18, 0.18, 0.20), "village_wall": (0.88, 0.74, 0.56),
        "palm_leaf": (0.28, 0.46, 0.24), "beach_wall_a": (0.93, 0.87, 0.70), "beach_wall_b": (0.70, 0.83, 0.86),
        "beach_wall_c": (0.92, 0.75, 0.66), "roof_red": (0.66, 0.27, 0.21), "roof_blue": (0.30, 0.43, 0.58),
        "roof_hole": (0.14, 0.12, 0.12), "plank": (0.64, 0.48, 0.32), "tin": (0.68, 0.72, 0.76), "pole": (0.42, 0.34, 0.26), "heli_glass": (0.13, 0.15, 0.17), "tv_screen": (0.62, 0.78, 0.95)}
NO_SHADOW = {"dirt_road", "grass_edge_flat", "pond_bank", "lily", "cow_spot", "dust", "tv_screen", "sea_face", "flood", "sea_storm", "foam", "asphalt_wet", "kerb", "track", "mud_track", "rut", "puddle", "mud_splash", "mud_edge", "puddle_rim", "puddle_shine", "soy", "soy_row", "grass_mid", "corn_dark", "sea_night", "bldg_win_n", "office_wall", "office_wall2", "tube_light", "gravel", "rock", "rock2", "lane", "crack", "asphalt", "asphalt_old", "bldg_win", "win_lit", "smoke", "tunnel", "lamp", "headlight", "taillight", "panel_wall", "city_sky", "citytower", "bigscreen", "paper", "limewall_in", "redfloor", "hole", "window_view", "window_field", "map_land", "ceiling_wood", "fan", "limewall", "water", "grass2", "sand", "soil", "greenhill", "mountain", "tomato", "flower_o", "flower_y", "concrete_wall", "ceiling", "tube", "whiteboard", "pit", "pit_deep", "led_green", "led_red",
             "monitor_map", "monitor_graph", "monitor_term", "road", "crop", "antenna", "screen", "laptop", "mud", "river", "net", "cloth", "solar", "hill", "town", "temple", "shikhara", "tower", "flag", "door",
             "window", "roof30", "tank"}
SUN = np.array([-0.55, 0.75, -0.35])                       # light from the upper left, a little toward us
SUN = SUN / np.linalg.norm(SUN)
CREASE = math.cos(math.radians(32))       # faces meeting at more than ~32 degrees make an inked corner


# ---------------------------------------------------------------------------- shapes (each a small mesh)
class Mesh:
    """vertices + faces (counter-clockwise seen from outside) + which edges are corners; ink weight"""

    def __init__(self, verts, faces, ink=1.0, hatch=False, name="", smooth=False):
        self.v = np.asarray(verts, np.float64)
        self.f = [list(f) for f in faces]
        self.ink = ink
        self.hatch = hatch
        self.name = name
        self.key = name + repr(tuple(np.round(self.v[0], 1)))     # (a stable id for the steady wobble)
        n = []
        for f in self.f:
            a, b, c = self.v[f[0]], self.v[f[1]], self.v[f[2]]
            nn = np.cross(b - a, c - a)
            ln = np.linalg.norm(nn)
            n.append(nn / ln if ln > 1e-9 else nn)
        self.n = np.array(n)
        self.c = np.array([self.v[f].mean(axis=0) for f in self.f])           # face centres
        edges = {}
        for fi, f in enumerate(self.f):
            for k in range(len(f)):
                a, b = f[k], f[(k + 1) % len(f)]
                edges.setdefault((min(a, b), max(a, b)), []).append(fi)
        self.edges = list(edges.items())
        self.smooth = smooth
        if smooth:                                    # a round thing: only its outline is inked, never the facets
            self.crease = [len(fs) == 1 for _e, fs in self.edges]
        else:
            self.crease = [len(fs) == 1 or float(np.dot(self.n[fs[0]], self.n[fs[1]])) < CREASE
                           for _e, fs in self.edges]
        self.E = np.array([e for e, _ in self.edges], int).reshape(-1, 2)        # the edges as arrays (fast tests)
        self.F0 = np.array([fs[0] for _e, fs in self.edges], int)
        self.F1 = np.array([fs[1] if len(fs) == 2 else -1 for _e, fs in self.edges], int)
        self.CR = np.array(self.crease, bool)
        self.center = self.v.mean(axis=0)
        self.under = False                            # True: lies on the ground (cracks, a river) - drawn first
        self.radius = float(np.max(np.linalg.norm(self.v - self.center, axis=1)))


def box(x, y, z, w, h, d, **kw):
    """a box standing on (x, y, z) - w along x, h up, d along z"""
    x0, x1, z0, z1, y0, y1 = x - w / 2, x + w / 2, z - d / 2, z + d / 2, y, y + h
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 1, 2, 3)[::-1], (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return Mesh(v, f, **kw)


def panel(x, y, z, w, h, **kw):
    """a flat outline on a wall facing -z (a door, a window): one face, so just its four edges"""
    v = [(x - w / 2, y, z), (x + w / 2, y, z), (x + w / 2, y + h, z), (x - w / 2, y + h, z)]
    return Mesh(v, [(0, 3, 2, 1)], **kw)                             # (its face looks toward -z, out of the wall)


def roof(x, y, z, w, h, d, over=20, **kw):
    """a pitched roof (a prism) - the ridge runs along x"""
    x0, x1 = x - w / 2 - over, x + w / 2 + over
    z0, z1 = z - d / 2 - over, z + d / 2 + over
    v = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), (x0, y + h, z), (x1, y + h, z)]
    f = [(3, 2, 1, 0), (0, 1, 5, 4), (2, 3, 4, 5), (1, 2, 5), (3, 0, 4)]
    return Mesh(v, f, **kw)


def pyramid(x, y, z, w, h, d, **kw):
    """a cone-like hut roof with 4 sides"""
    x0, x1, z0, z1 = x - w / 2, x + w / 2, z - d / 2, z + d / 2
    v = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), (x, y + h, z)]
    f = [(3, 2, 1, 0), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    return Mesh(v, f, **kw)


def cylinder(x, y, z, r, h, n=12, top_r=None, **kw):
    """a cylinder (or a cone when top_r is small) - its side faces are smooth: only the outline is inked"""
    tr = r if top_r is None else top_r
    v = []
    for k in range(n):
        a = 2 * math.pi * k / n
        v.append((x + r * math.cos(a), y, z + r * math.sin(a)))
    for k in range(n):
        a = 2 * math.pi * k / n
        v.append((x + tr * math.cos(a), y + h, z + tr * math.sin(a)))
    f = [tuple(range(n))[::-1] if False else tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for k in range(n):
        k2 = (k + 1) % n
        f.append((k, k2, n + k2, n + k))
    return Mesh(v, f, **kw)


def ball(x, y, z, r, sy=1.0, n=10, m=6, floor=None, **kw):
    """a low-poly ball (a tree crown; a haystack when cut flat by the ground: floor=0)"""
    v = [(x, y + r * sy, z), (x, y - r * sy, z)]
    for j in range(1, m):
        ph = math.pi * j / m
        for k in range(n):
            a = 2 * math.pi * k / n
            v.append((x + r * math.sin(ph) * math.cos(a), y + r * sy * math.cos(ph), z + r * math.sin(ph) * math.sin(a)))
    f = []
    ring = lambda j, k: 2 + (j - 1) * n + (k % n)
    for k in range(n):
        f.append((0, ring(1, k + 1), ring(1, k)))
        f.append((1, ring(m - 1, k), ring(m - 1, k + 1)))
    for j in range(1, m - 1):
        for k in range(n):
            f.append((ring(j, k), ring(j, k + 1), ring(j + 1, k + 1), ring(j + 1, k)))
    if floor is not None:
        v = [(a, max(b, floor), c) for a, b, c in v]
    kw.setdefault("smooth", True)
    return Mesh(v, f, **kw)


# ---------------------------------------------------------------------------- a place: the sketch village
M = 190.0          # world units per metre: a stickman (head top ~330) is 1.75 m tall, so everything else is real size


def village():
    """a small Indian village in 3D, real size around an open square where the people act (the square is at
    x 0, z 450; the camera stands on the near side, so nothing is built there)"""
    out = []

    def hut(x, z, s=1.0):                         # mud hut: 4 x 3.5 m, walls 2.3 m, a thatch roof 1.9 m high
        w, h, d = 4.0 * M * s, 2.3 * M * s, 3.5 * M * s
        out.append(box(x, 0, z, w, h, d, name="hut"))
        out.append(pyramid(x, h, z, w + 0.8 * M * s, 1.9 * M * s, d + 0.8 * M * s, name="hut_roof"))
        out.append(panel(x, 0, z - d / 2 - 1, 0.9 * M * s, 1.9 * M * s, ink=0.9, name="door"))

    def house(x, z):                              # pucca house: 7 x 5 m, walls 3.2 m, a tiled roof
        w, h, d = 7.0 * M, 3.2 * M, 5.0 * M
        out.append(box(x, 0, z, w, h, d, name="house"))
        out.append(roof(x, h, z, w, 1.6 * M, d, over=0.3 * M, name="house_roof"))
        for wx in (-2.2, 2.2):
            out.append(panel(x + wx * M, 1.0 * M, z - d / 2 - 1, 1.0 * M, 1.1 * M, ink=0.8, name="window"))
        out.append(panel(x, 0, z - d / 2 - 1, 1.1 * M, 2.1 * M, ink=0.9, name="door"))

    def tree(x, z, s=1.0):                        # neem tree: a 3 m trunk, a 4.5 m wide crown
        out.append(cylinder(x, 0, z, 0.22 * M * s, 3.2 * M * s, n=8, top_r=0.15 * M * s, name="trunk"))
        out.append(ball(x, 4.6 * M * s, z, 2.3 * M * s, sy=0.75, n=9, m=5, name="crown"))

    cz = 450.0
    house(0, cz + 10 * M)                                                  # the back of the square
    hut(-8.0 * M, cz + 5.5 * M)                                            # left side
    hut(8.5 * M, cz + 6.5 * M, 0.9)                                        # right side
    wx, wz = -5.0 * M, cz + 0.5 * M                                        # the well, at the left edge
    out.append(cylinder(wx, 0, wz, 0.75 * M, 0.8 * M, n=14, name="well"))
    for dx in (-0.8, 0.8):
        out.append(box(wx + dx * M, 0.8 * M, wz, 0.1 * M, 1.4 * M, 0.1 * M, name="well_post"))
    out.append(box(wx, 2.2 * M, wz, 1.8 * M, 0.1 * M, 0.1 * M, name="well_beam"))
    for x, z, s in ((-4.5, 15, 1.1), (5.0, 15.5, 1.0), (-13, 3, 1.0), (13.5, 2, 0.95), (-12, 11, 1.2), (12, 12, 1.0)):
        tree(x * M, cz + z * M, s)
    for x, z in ((-12.8, 6.0), (13.2, 10.0)):                                # haystacks beside the huts
        out.append(ball(x * M, 0, cz + z * M, 1.3 * M, sy=1.3, n=10, m=6, floor=0.0, name="haystack"))
    kx, kz = 5.0 * M, cz + 2.8 * M                                         # a cot (charpai) in front of the right hut
    out.append(box(kx, 0.45 * M, kz, 2.0 * M, 0.08 * M, 0.95 * M, name="cot"))
    for dx in (-0.95, 0.95):
        for dz in (-0.42, 0.42):
            out.append(box(kx + dx * M, 0, kz + dz * M, 0.07 * M, 0.45 * M, 0.07 * M, ink=0.8, name="cot_leg"))
    for k in range(9):                                                     # a bamboo fence behind the left hut
        out.append(box(-13 * M + k * 1.2 * M, 0, cz + 8.8 * M, 0.08 * M, 1.1 * M, 0.08 * M, ink=0.8, name="fence"))
    out.append(box(-8.2 * M, 0.75 * M, cz + 8.8 * M, 9.6 * M, 0.06 * M, 0.06 * M, ink=0.8, name="fence_rail"))
    return out


# ---------------------------------------------------------------------------- the camera
class Cam:
    def __init__(self, pos, look, fov=50.0, W=1920, H=1080):
        self.pos = np.asarray(pos, np.float64)
        self.look = tuple(look)
        f = np.asarray(look, np.float64) - self.pos
        self.fwd = f / np.linalg.norm(f)
        r = np.cross(self.fwd, (0.0, 1.0, 0.0))
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.right, self.fwd)
        self.W, self.H = W, H
        self.focal = (H / 2) / math.tan(math.radians(fov) / 2)

    def view(self, p):
        """world points (N,3) -> camera space (x right, y up, z forward)"""
        d = np.asarray(p, np.float64) - self.pos
        return np.stack([d @ self.right, d @ self.up, d @ self.fwd], axis=-1)

    def screen(self, c):
        z = np.maximum(c[..., 2], 1.0)
        return np.stack([self.W / 2 + self.focal * c[..., 0] / z, self.H / 2 - self.focal * c[..., 1] / z], axis=-1)

    def project(self, p):
        return self.screen(self.view(p))


# ---------------------------------------------------------------------------- drawing
def _steady(ctx, p0, p1, w, col, key, step):
    """one inked edge: a hand wobble that belongs to the edge (the same few bumps along it every frame, changing
    only gently every few frames), so lines don't shake as the camera moves - and a lighter second pass"""
    rng = random.Random(zlib.crc32(repr((key, step)).encode()))
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy)
    if ln < 0.5:
        return
    nx, ny = -dy / ln, dx / ln
    amp = min(2.2, 0.6 + ln / 260.0) * (w / 3.0) ** 0.5
    bumps = [rng.uniform(-1, 1) for _ in range(4)]
    for k, (aw, aa) in enumerate(((1.0, 1.0), (0.5, 0.35))):
        ctx.move_to(x0 + nx * bumps[0] * amp * 0.3 * k, y0 + ny * bumps[0] * amp * 0.3 * k)
        for i in range(1, 5):                                          # (5 points: a gentle curve, not a zigzag)
            u = i / 4
            off = math.sin(math.pi * u) * bumps[i - 1] * amp * (1 + k)
            ctx.line_to(x0 + dx * u + nx * off, y0 + dy * u + ny * off)
        ctx.set_source_rgba(*col, aa)
        ctx.set_line_width(w * aw)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()


def _ink_mesh(ctx, pen, cam, m, S, fade):
    cv = cam.view(m.v)
    if np.all(cv[:, 2] < 5):
        return
    sv = cam.screen(cv)
    seen = np.einsum("ij,ij->i", m.c - cam.pos, m.n)
    vis = seen < 0                                                     # faces turned toward the camera
    depth = np.einsum("ij,j->i", m.c - cam.pos, cam.fwd)
    order = [i for i in np.argsort(-depth) if vis[i]]
    base = WASH.get(m.name)
    flat = STYLE[0] == "flat" and base is not None
    if not flat:
        ctx.set_source_rgb(*PAPER)                                     # paper fills hide what is behind
        for i in order:
            f = m.f[i]
            if np.any(cv[f, 2] < 5):
                continue
            ctx.move_to(*sv[f[0]])
            for j in f[1:]:
                ctx.line_to(*sv[j])
            ctx.close_path()
        ctx.fill()
    if flat:                                                          # flat vector colour: two tones, sun or shade
        tone = np.where(np.asarray(m.n @ SUN) > 0.25, 1.0, np.where(np.asarray(m.n @ SUN) > -0.2, 0.86, 0.74))
        run_col = None

        def flush():
            if run_col is not None:
                ctx.set_source_rgb(*run_col)
                ctx.fill_preserve()
                ctx.set_line_width(1.0)                               # (hides hairline seams between faces)
                ctx.stroke()
        svl = sv.tolist()
        okz = (cv[:, 2] >= 5).tolist()
        cols = {}
        for lit in (0.74, 0.86, 1.0):
            col = tuple(min(1.0, FLAT_SAT * base[k] * lit) for k in range(3))
            cols[lit] = tuple(c + (sk - c) * fade * 0.6 for c, sk in zip(col, SKY_NOW[0]))
        for i in order:                                               # faces of one colour in a row: one fill
            f = m.f[i]
            if not all(okz[j] for j in f):
                continue
            col = cols[1.0 if m.smooth else float(tone[i])]
            if col != run_col:
                flush()
                ctx.new_path()
                run_col = col
            ctx.move_to(*svl[f[0]])
            for j in f[1:]:
                ctx.line_to(*svl[j])
            ctx.close_path()
        flush()
        ctx.new_path()
    if STYLE[0] == "wash" and base is not None:                       # watercolour: lit side light, far side deeper,
        for i in order:                                               # a little off the lines (as a brush would be)
            f = m.f[i]
            if np.any(cv[f, 2] < 5):
                continue
            lit = 0.55 + 0.45 * max(0.0, float(np.dot(m.n[i], SUN)))
            if m.smooth:                                              # round things: a soft even tone, no facets
                lit = 0.88 + 0.12 * max(0.0, float(np.dot(m.n[i], SUN)))
            col = tuple(PAPER[k] + (base[k] * lit - PAPER[k]) * 0.72 for k in range(3))
            col = tuple(c + (p - c) * fade for c, p in zip(col, PAPER))
            ctx.move_to(sv[f[0]][0] + 2.5 * S, sv[f[0]][1] + 1.5 * S)
            for j in f[1:]:
                ctx.line_to(sv[j][0] + 2.5 * S, sv[j][1] + 1.5 * S)
            ctx.close_path()
            ctx.set_source_rgba(*col, 0.85)
            ctx.fill()
    col = tuple(c + (p - c) * fade for c, p in zip(INK, PAPER))
    dist = float(np.dot(m.center - cam.pos, cam.fwd))
    w = max(1.2, min(5.0, 3.2 * m.ink * 1600.0 / max(300.0, dist))) * S * INK_K[0]
    if STYLE[0] == "flat":                                            # vector art: clean straight lines, all the
        va0 = vis[m.F0]                                               # outline in one stroke, the inside in another
        two = m.F1 >= 0
        va1 = np.where(two, vis[np.maximum(m.F1, 0)], va0)
        sil = two & (va0 != va1)
        front = (cv[m.E[:, 0], 2] >= 5) & (cv[m.E[:, 1], 2] >= 5)
        ctx.set_source_rgb(*FLAT_INK)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for sel, ww in ((~sil & m.CR & (va0 | va1) & front, w * 0.6 * 0.7), (sil & front, w * 1.35)):
            idx = np.nonzero(sel)[0]
            if len(idx):
                P0, P1 = sv[m.E[idx, 0]], sv[m.E[idx, 1]]
                for (x0, y0), (x1, y1) in zip(P0.tolist(), P1.tolist()):
                    ctx.move_to(x0, y0)
                    ctx.line_to(x1, y1)
                ctx.set_line_width(ww)
                ctx.stroke()
        return
    for (a, b), fs, cr in zip((e for e, _ in m.edges), (fs for _, fs in m.edges), m.crease):
        va = [vis[fi] for fi in fs]
        sil = len(fs) == 2 and va[0] != va[1]
        if not (sil or (cr and any(va))):
            continue
        if cv[a, 2] < 5 or cv[b, 2] < 5:
            continue
        ww = w if STYLE[0] == "lines" else (w * 1.35 if sil else w * 0.6)   # outline bold, inside lines fine
        _steady(ctx, sv[a], sv[b], ww, col, (m.key, a, b), pen.seed)


def _person(ctx, pen, cam, p, t, S):
    """a 3D stickman: the pose skeleton (side view) set into the world, near limbs on one side, far on the other"""
    from .character import solve
    pose = p["pose"]
    if p.get("look") and abs(float(pose.get("torso", 0) or 0)) <= 20:  # doodle people stay upright when they laugh /
        pose = dict(pose)                                              # cry (a small lean, not a bend: a rigid shirt
        pose["torso"] = float(pose.get("torso", 0) or 0) * 0.3         # tilted far back looks broken off the legs)
        pose["head"] = float(pose.get("head", 0) or 0) * 0.35
    J = solve(pose, p.get("scale", 1.0), head_r=sketch.HEAD_R)
    ang = p["dir"]                                                     # the way they face (radians, 0 = +x)
    fwd = np.array([math.cos(ang), 0.0, math.sin(ang)])
    side = np.array([-math.sin(ang), 0.0, math.cos(ang)])
    base = np.array(p["pos"], np.float64)
    half = 13.0

    open_ = 0.55 if p.get("look") and not p.get("riding") else 0.0     # (doodle people: a hand that reaches forward
    x_sh = J["sh"][0]                                                  # also opens out to the side, so a gesture
    #                                                                    still reads when they face the camera)

    def W3(k, s=0.0):
        x, y = J[k]
        if open_ and k in ("en", "hn", "ef", "hf") and s:
            s = s + math.copysign(open_ * max(0.0, x - x_sh) + 0.25 * max(0.0, y - J["sh"][1] + 40), s)
        return base + fwd * x + side * s + np.array([0.0, y, 0.0])

    # which side is near the camera: draw the far limbs first
    near_s = -half if float(np.dot(side, cam.pos - base)) < 0 else half
    far_s = -near_s
    seg = lambda keys, s: cam.project(np.array([W3(k, s) for k in keys]))
    dist = float(np.dot(base - cam.pos, cam.fwd))
    k = cam.focal / max(200.0, dist)                                    # screen px per world unit here
    w = max(2.0, 7.0 * k * p.get("scale", 1.0))
    hx, hy = cam.project(W3("head")[None])[0]
    r = sketch.HEAD_R * p.get("scale", 1.0) * k
    look = p.get("look")
    if look and p.get("muddy"):
        look = dict(look, muddy=True)
    if look:                                                           # a doodle kid: clothes, hair, a sticker edge
        r *= float(look.get("head_k", DOODLE_HEAD))                   # kids: a big head; grown-ups: smaller
        _doodle(ctx, pen, look, seg, near_s, far_s, hx, hy, r, w * 0.55, fwd, side, cam, base)
    else:
        for keys, s in ((("sh", "ef", "hf"), far_s), (("hip", "kf", "ff", "toe_f"), far_s)):
            pen.line([tuple(q) for q in seg(keys, s)], w / pen.unit, INK, 0.8)
        pen.line([tuple(q) for q in seg(("hip", "neck"), 0.0)], w / pen.unit, INK, 1.0)
        for keys, s in ((("hip", "kn", "fn", "toe_n"), near_s), (("sh", "en", "hn"), near_s)):
            pen.line([tuple(q) for q in seg(keys, s)], w / pen.unit, INK, 1.0)
        pen.circle(hx, hy, r, w * 0.85 / pen.unit, INK, 1.0, fill=(*PAPER, 1.0), amp=0.6)
    # the face: toward the camera = both eyes; side-on = eyes to the side they look; away = no face
    to_cam = cam.pos - base
    to_cam[1] = 0
    to_cam /= max(1e-6, np.linalg.norm(to_cam))
    cosf = float(np.dot(fwd, to_cam))
    if cosf > 0.55:
        view, f = "camera", 1
    elif cosf < -0.55:
        view, f = "away", 1
    else:
        sx = cam.project((base + fwd * 100)[None])[0][0] - cam.project(base[None])[0][0]
        view, f = "side", (1 if sx >= 0 else -1)
    ctx.save()
    ctx.translate(hx, hy)
    ctx.scale(1, -1)                                                   # (the face code draws y-up)
    u0 = pen.unit
    pen.unit = 1.0
    if look and view != "away" and float(look.get("head_k", DOODLE_HEAD)) > 1.2:   # rosy cheeks (kids)
        for cx in ((-0.5, 0.5) if view == "camera" else (0.45 * f,)):
            ctx.arc(cx * r, -0.28 * r, 0.16 * r, 0, 2 * math.pi)
            ctx.set_source_rgba(0.95, 0.45, 0.45, 0.45)
            ctx.fill()
    sketch._mouth_and_eyes(pen, 0, 0, r, f, p.get("face", "neutral"), p.get("mouth", 0.0), False, view)
    if look and look.get("shades") and view != "away":                # dark glasses (agents): two black lenses
        xs_ = (-0.36, 0.36) if view == "camera" else (0.45 * f,)       # and a bridge over the eyes
        for ex in xs_:
            ctx.save()
            ctx.translate(ex * r, 0.12 * r)
            ctx.scale(1.0, 0.72)
            ctx.arc(0, 0, r * 0.27, 0, 2 * math.pi)
            ctx.restore()
            ctx.set_source_rgb(0.06, 0.06, 0.08)
            ctx.fill()
        if view == "camera":
            ctx.move_to(-0.12 * r, 0.16 * r)
            ctx.line_to(0.12 * r, 0.16 * r)
        else:
            ctx.move_to(f * 0.2 * r, 0.14 * r)
            ctx.line_to(-f * 0.6 * r, 0.18 * r)
        ctx.set_source_rgb(0.06, 0.06, 0.08)
        ctx.set_line_width(max(1.0, 0.06 * r))
        ctx.stroke()
    if look and look.get("mustache") and view != "away":              # a mustache over the mouth
        mx = 0.0 if view == "camera" else f * 0.4 * r
        for sgn in ((-1, 1) if view == "camera" else (1,)):
            ctx.move_to(mx, -0.2 * r)
            ctx.curve_to(mx + sgn * 0.15 * r, -0.12 * r, mx + sgn * 0.3 * r, -0.18 * r, mx + sgn * 0.38 * r, -0.3 * r)
        ctx.set_source_rgb(*tuple(look.get("hair_col") or (0.15, 0.1, 0.08)))
        ctx.set_line_width(max(1.5, 0.11 * r))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()
    if look and view != "away":
        _gear(ctx, look, r, view, f, w * 0.5)
    pen.unit = u0
    ctx.restore()
    p["_hand"] = tuple(cam.project(W3("hn", near_s)[None])[0])          # where held things go
    sxf = cam.project((base + fwd * 100)[None])[0][0] - cam.project(base[None])[0][0]
    p["_k"], p["_f"] = k, (1 if sxf >= 0 else -1)
    return hx, hy - r


HOOD = (0.86, 0.80, 0.66)                # a sun hood's default cloth: undyed cotton
MASK = (0.94, 0.94, 0.90)
DOODLE_HEAD = 1.35                       # doodle kids: a bigger head (cute proportions; a story rule, not anatomy)
SKIN = {"light": (1.0, 0.87, 0.74), "wheat": (0.96, 0.78, 0.60), "brown": (0.80, 0.58, 0.42), "dark": (0.58, 0.40, 0.28)}


def _gear(ctx, look, r, view, f, lw):
    """2030 gear over the face (y up here): a cloth mask over nose and mouth, dark goggles over the eyes
    (no ozone: the UV would burn skin and eyes)"""
    if look.get("mask"):
        ctx.save()
        ctx.arc(0, 0, r * 0.99, 0, 2 * math.pi)
        ctx.clip()
        x0 = -r if view == "camera" else (-r * 0.1 if f > 0 else -r)
        ctx.move_to(x0 - r * 0.2, -r * 1.2)
        ctx.line_to(x0 - r * 0.2, -r * 0.05)
        ctx.curve_to(-r * 0.3, -r * 0.12, r * 0.3, -r * 0.12, r * 1.2, -r * 0.05)
        ctx.line_to(r * 1.2, -r * 1.2)
        ctx.close_path()
        ctx.set_source_rgb(*tuple(look.get("mask_col") or MASK))
        ctx.fill()
        ctx.restore()
        ctx.move_to(-r * 0.98, -r * 0.08)                              # its top edge
        ctx.curve_to(-r * 0.3, -r * 0.15, r * 0.3, -r * 0.15, r * 0.98, -r * 0.08)
        ctx.set_source_rgb(0.55, 0.55, 0.52)
        ctx.set_line_width(lw)
        ctx.stroke()
    if look.get("goggles"):
        ey = r * 0.12
        xs = (-0.36, 0.36) if view == "camera" else (0.42 * f,)
        ctx.move_to(-r * 0.98, ey)                                     # the strap
        ctx.line_to(r * 0.98, ey)
        ctx.set_source_rgb(0.25, 0.22, 0.22)
        ctx.set_line_width(r * 0.12)
        ctx.stroke()
        for ex in xs:
            ctx.arc(ex * r, ey, r * 0.22, 0, 2 * math.pi)
            ctx.set_source_rgb(0.16, 0.18, 0.24)
            ctx.fill_preserve()
            ctx.set_source_rgb(0.45, 0.40, 0.35)
            ctx.set_line_width(lw * 1.2)
            ctx.stroke()
            ctx.arc(ex * r + r * 0.07, ey + r * 0.07, r * 0.06, 0, 2 * math.pi)   # a glint
            ctx.set_source_rgb(1, 1, 1)
            ctx.fill()


def _doodle(ctx, pen, look, seg, near_s, far_s, hx, hy, r, lw, fwd, side, cam, base):
    """a cute doodle kid (like clip-art stickers): thin grey limbs, a coloured shirt or dress, hair, and a white
    sticker edge round the whole body so it pops off the background"""
    skin = look.get("skin", "wheat")
    skin = tuple(skin) if isinstance(skin, (tuple, list)) else SKIN.get(skin, SKIN["wheat"])
    shirt = tuple(look.get("shirt") or (0.95, 0.45, 0.55))           # (no colour given: a default one)
    pants = tuple(look.get("pants") or (0.30, 0.38, 0.62))
    hair = tuple(look.get("hair_col") or (0.18, 0.12, 0.08))
    dress = look.get("dress", False)
    limb = (0.35, 0.33, 0.32)
    far_arm, far_leg = seg(("sh", "ef", "hf"), far_s), seg(("hip", "kf", "ff", "toe_f"), far_s)
    near_leg, near_arm = seg(("hip", "kn", "fn", "toe_n"), near_s), seg(("sh", "en", "hn"), near_s)
    neck, hip = seg(("neck",), 0.0)[0], seg(("hip",), 0.0)[0]
    d = hip - neck
    L = max(1e-6, float(np.hypot(*d)))
    nrm = np.array([-d[1], d[0]]) / L
    face_on = abs(float(np.dot(fwd, (cam.pos - base) / max(1e-6, np.linalg.norm(cam.pos - base)))))
    rb = r * 1.3 / float(look.get("head_k", DOODLE_HEAD))             # the body's size (not the head's)
    tw = rb * (0.42 + 0.30 * face_on)                                  # side-on bodies look narrower
    top, bot = neck + d * 0.08, hip + d * (0.10 if not dress else 0.35)
    bw = tw * (1.55 if dress else 0.95)
    body = [top + nrm * tw * 0.8, top - nrm * tw * 0.8, bot - nrm * bw, bot + nrm * bw]

    def poly(pts, fill, edge, ew):
        ctx.move_to(*pts[0])
        for q in pts[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        if fill:
            ctx.set_source_rgb(*fill)
            ctx.fill_preserve() if edge else ctx.fill()
        if edge:
            ctx.set_source_rgb(*edge)
            ctx.set_line_width(ew)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.stroke()

    def stroke(pts, col, ww):
        ctx.move_to(*pts[0])
        for q in pts[1:]:
            ctx.line_to(*q)
        ctx.set_source_rgb(*col)
        ctx.set_line_width(ww)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke()

    # 1) a white sticker edge round everything - only when asked ("sticker": true); by default people stand
    #    straight on the scene with just their own lines
    if look.get("sticker"):
        sw = lw * 4.5
        for pts in (far_arm, far_leg, near_leg, near_arm):
            stroke(pts, (1, 1, 1), sw)
        poly(body, (1, 1, 1), (1, 1, 1), sw)
        ctx.arc(hx, hy, r + sw / 2, 0, 2 * math.pi)
        ctx.fill()
    # 2) far limbs, legs (trousers to the knee when not in a dress), body, near limbs
    stroke(far_arm, limb, lw)
    stroke(far_leg, limb, lw)
    stroke(near_leg, limb, lw)
    if not dress:
        for leg in (far_leg, near_leg):
            stroke(leg[:2] + [leg[1]], pants, lw * 3.2)
            stroke([leg[0], leg[0] + (leg[1] - leg[0]) * 1.08], pants, lw * 3.2)
    for leg in (far_leg, near_leg):                                    # shoes
        stroke(leg[-2:], (0.40, 0.29, 0.18) if look.get("muddy") else (0.25, 0.22, 0.22), lw * 2.4)
        if look.get("muddy") and len(leg) >= 3:                        # mud splashed up the trouser ends
            for f_ in (0.62, 0.78, 0.9):
                q_ = leg[-3] + (leg[-2] - leg[-3]) * f_
                ctx.arc(q_[0] + lw * (1.2 if f_ == 0.78 else -0.8), q_[1], lw * (1.5 - f_), 0, 2 * math.pi)
                ctx.set_source_rgb(0.40, 0.29, 0.18)
                ctx.fill()
    nk = [tuple(neck), (hx, hy)]                                       # the neck: shirt to head (the head covers its
    stroke(nk, tuple(c * 0.55 for c in skin), lw * 3.4)                # top, the shirt its foot)
    stroke(nk, skin, lw * 2.6)
    poly(body, shirt, tuple(c * 0.6 for c in shirt), lw * 0.8)
    stroke(near_arm, limb, lw)
    for arm in (far_arm, near_arm):                                    # sleeves and hands
        stroke([arm[0], arm[0] + (arm[1] - arm[0]) * 0.55], shirt, lw * 3.0)
        ctx.arc(*arm[-1], lw * 2.6, 0, 2 * math.pi)                    # a round hand (big enough to read)
        ctx.set_source_rgb(*skin)
        ctx.fill()
    # 3) the head: hair that hangs behind it first ("bob"), skin, then a cap of hair on top ("bunches": two bunches)
    style = look.get("hair", "short")
    if style == "bob":                                                 # hair to the jaw, behind the face
        ctx.save()
        ctx.translate(hx, hy)
        ctx.arc(0, -r * 0.05, r * 1.12, math.pi, 2 * math.pi)
        ctx.line_to(r * 1.12, r * 0.55)
        ctx.curve_to(r * 1.12, r * 0.8, -r * 1.12, r * 0.8, -r * 1.12, r * 0.55)
        ctx.close_path()
        ctx.set_source_rgb(*hair)
        ctx.fill()
        ctx.restore()
    ctx.arc(hx, hy, r, 0, 2 * math.pi)
    ctx.set_source_rgb(*skin)
    ctx.fill_preserve()
    ctx.set_source_rgb(*tuple(c * 0.55 for c in skin))
    ctx.set_line_width(lw * 0.8)
    ctx.stroke()
    if look.get("beard"):                                              # a beard round the jaw (the hair's colour)
        ctx.save()
        ctx.arc(hx, hy, r, 0, 2 * math.pi)
        ctx.clip()
        ctx.arc(hx, hy + r * 0.25, r * 0.95, 0.05 * math.pi, 0.95 * math.pi)
        ctx.arc_negative(hx, hy - r * 0.05, r * 0.62, 0.9 * math.pi, 0.1 * math.pi)
        ctx.close_path()
        ctx.set_source_rgb(*hair)
        ctx.fill()
        ctx.restore()
    sx = cam.project((base + fwd * 100)[None])[0][0] - cam.project(base[None])[0][0]
    back = -1.0 if sx >= 0 else 1.0                                    # the screen side behind the face
    turned = 1.0 - face_on                                             # 0 = facing us, 1 = side-on
    ctx.save()
    ctx.translate(hx, hy)
    ctx.set_source_rgb(*hair)
    if style == "bunches":
        for bx in ((-1, 1) if turned < 0.6 else (back,)):
            ctx.arc(bx * r * 1.02, -r * 0.15, r * 0.36, 0, 2 * math.pi)
            ctx.fill()
    if look.get("hood") == "rain":                                     # a raincoat's hood, up: a stiff ring round the
        cl = tuple(look.get("cloth") or (0.95, 0.78, 0.18))            # face (only the face shows), toggles hanging
        ox = -back * r * 0.28 * turned
        ctx.new_path()
        ctx.arc(0, -r * 0.06, r * 1.34, 0, 2 * math.pi)
        ctx.new_sub_path()
        ctx.save()
        ctx.translate(ox, r * 0.12)
        ctx.scale(0.84 - 0.12 * turned, 0.90)
        ctx.arc_negative(0, 0, r, 2 * math.pi, 0)
        ctx.restore()
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.set_source_rgb(*cl)
        ctx.fill_preserve()
        ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
        ctx.set_source_rgb(*tuple(c * 0.6 for c in cl))
        ctx.set_line_width(lw * 0.8)
        ctx.stroke()
        for sx_ in (-0.38, 0.38):                                      # the drawstrings
            ctx.move_to(ox + sx_ * r, r * 0.95)
            ctx.line_to(ox + sx_ * r * 1.1, r * 1.45)
        ctx.set_source_rgb(0.2, 0.2, 0.22)
        ctx.set_line_width(lw * 0.5)
        ctx.stroke()
    elif look.get("hood"):                                             # a hood / head cloth against the sun: over the
        cl = tuple(look.get("cloth") or HOOD)                          # top of the head and hanging to the shoulders
        R = r * 1.18
        ctx.arc(0, -r * 0.02, R, math.pi, 2 * math.pi)
        if turned < 0.5:                                               # facing us: it hangs down both sides
            ctx.line_to(R * 1.05, r * 1.15)
            ctx.line_to(r * 0.78, r * 1.15)
            ctx.line_to(r * 0.86, r * 0.02)
            ctx.line_to(-r * 0.86, r * 0.02)
            ctx.line_to(-r * 0.78, r * 1.15)
            ctx.line_to(-R * 1.05, r * 1.15)
        else:                                                          # side-on: down the back of the head
            if back < 0:
                ctx.new_path()
                ctx.arc_negative(0, -r * 0.02, R, 2 * math.pi, math.pi)
            ctx.line_to(back * R * 1.1, r * 1.2)
            ctx.line_to(back * r * 0.35, r * 1.15)
            ctx.line_to(back * r * 0.45, r * 0.1)
            ctx.line_to(-back * r * 0.75, -r * 0.2)
        ctx.close_path()
        ctx.set_source_rgb(*cl)
        ctx.fill_preserve()
        ctx.set_source_rgb(*tuple(c * 0.6 for c in cl))
        ctx.set_line_width(lw * 0.8)
        ctx.stroke()
    else:                                                              # a cap of hair, fuller at the back
        a0 = math.pi * (1.0 + 0.10 * turned * back)
        ctx.arc(back * r * 0.12 * turned, -r * 0.05, r * 1.06, a0 - 0.15, math.pi * 2 + 0.15 + 0.10 * turned * back)
        ctx.curve_to(r * 0.5, -r * 0.35, -r * 0.5, -r * 0.55, -r * 1.06, -r * 0.05)
        ctx.close_path()
        ctx.fill()
    if look.get("cap"):                                                # a cap: a crown over the hair, the peak
        cl = tuple(look.get("cloth") or (0.18, 0.20, 0.23))           # pointing the way the face looks
        ctx.new_path()
        ctx.arc(0, -r * 0.12, r * 1.08, math.pi, 2 * math.pi)
        ctx.close_path()
        if turned < 0.5:                                               # facing us: the peak is a band on the brow
            ctx.rectangle(-r * 1.12, -r * 0.24, r * 2.24, r * 0.16)
        else:                                                          # side-on: it sticks out over the face
            ctx.save()
            ctx.translate(-back * r * 1.05, -r * 0.16)
            ctx.scale(1.0, 0.2)
            ctx.arc(0, 0, r * 0.62, 0, 2 * math.pi)
            ctx.restore()
        ctx.set_source_rgb(*cl)
        ctx.fill()
    ctx.restore()


# ---------------------------------------------------------------------------- a flat cartoon T-rex
# its side outline in metres (x forward, y up), facing +x; points are joined by a smooth spline
_REX_TOP = [(-4.6, 2.75), (-3.2, 2.85), (-1.8, 3.05), (-0.6, 3.35), (0.6, 3.45), (1.3, 3.75), (1.8, 4.15),
            (2.5, 4.3), (3.25, 4.15), (3.6, 3.85)]                     # tail tip -> back -> head top -> snout
_REX_JAW_TOP = [(3.6, 3.85), (3.55, 3.62), (2.2, 3.55)]                 # snout tip -> the upper lip -> mouth corner
_REX_BOTTOM = [(2.2, 3.55), (1.95, 3.15), (1.5, 2.55), (0.6, 2.05), (-0.4, 2.0), (-1.4, 2.3), (-2.8, 2.55)]
_REX_JAW = [(2.2, 3.5), (3.25, 3.45), (3.2, 3.22), (2.35, 3.1), (2.0, 3.25)]   # the lower jaw (it opens)
REX = {"body": (0.40, 0.74, 0.36), "belly": (0.98, 0.86, 0.45), "spike": (0.97, 0.55, 0.22),
       "far": (0.30, 0.58, 0.28), "mouth": (0.62, 0.16, 0.20)}


def _spline(pts, n=6):
    """Catmull-Rom through the points (a smooth hand-drawn outline from a few numbers)"""
    out = []
    P = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = (np.array(P[j], float) for j in (i - 1, i, i + 1, i + 2))
        for k in range(n):
            u = k / n
            out.append(0.5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    out.append(np.array(pts[-1], float))
    return out


def _leg2(hip, foot, a, b, bend=1.0):
    """two-bone leg: where the knee goes for this hip and foot (law of cosines), bending backward like a bird's"""
    hip, foot = np.asarray(hip, float), np.asarray(foot, float)
    d = foot - hip
    L = min(a + b - 1e-3, max(1e-3, float(np.hypot(*d))))
    ca = (a * a + L * L - b * b) / (2 * a * L)
    ang = math.atan2(d[1], d[0]) + bend * math.acos(max(-1.0, min(1.0, ca)))
    return hip + a * np.array([math.cos(ang), math.sin(ang)])


def _dino(ctx, cam, d, t, S):
    """a flat cartoon T-rex in the 3D world: a side-on cut-out that runs (bird-like legs on a cycle), bobs, sways
    its tail and snaps its jaw. Real-ish size: 4.3 m tall, 8 m long (a T-rex was ~12 m; smaller reads better)."""
    ang = d["dir"]
    fwd = np.array([math.cos(ang), 0.0, math.sin(ang)])
    side = np.array([-math.sin(ang), 0.0, math.cos(ang)])
    base = np.array(d["pos"], float)
    k = d.get("scale", 1.0)
    run = d.get("run", 1.0)                                            # 0 = standing, 1 = full run
    ph = t * 2 * math.pi * 1.6                                          # ~1.6 strides a second
    bob = 0.12 * run * abs(math.sin(ph))
    sway = 0.25 * run * math.sin(ph + 0.8)
    jaw = 0.35 * (0.5 + 0.5 * math.sin(t * 9.0)) * d.get("roar", 1.0)    # radians the jaw opens

    def W(pts, s=0.0):
        P = np.array([[base[i] + (fwd[i] * x + (0 if i != 1 else y)) * M * k + side[i] * s for i in range(3)]
                      for x, y in pts])
        return cam.project(P)

    def bend(pts):                                                     # body bob + a tail that sways more at the tip
        out = []
        for x, y in pts:
            yy = y + bob
            if x < -0.8:
                yy += sway * ((-0.8 - x) / 3.8) ** 1.5
            out.append((x, yy))
        return out

    def fill(q, col, ink=True, w=None):
        ctx.move_to(*q[0])
        for p in q[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        ctx.set_source_rgb(*col)
        if ink:
            ctx.fill_preserve()
            ctx.set_source_rgb(*FLAT_INK)
            ctx.set_line_width(w or lw)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.stroke()
        else:
            ctx.fill()

    ends = np.array([base + fwd * x * M * k + np.array([0.0, 3.0 * M * k, 0.0]) for x in (-4.6, 3.6)])
    if np.any(cam.view(ends)[:, 2] < 30):                               # (partly behind the camera: not drawn)
        return (-1e4, -1e4)
    dist = float(np.dot(base - cam.pos, cam.fwd))
    px = cam.focal / max(200.0, dist) * M * k                           # screen px per metre here
    lw = max(1.5, 0.045 * px)
    # the legs: each foot runs round a flat loop (on the ground for half the cycle, lifted for the other half)
    legs = []
    for s_off, phase in ((-0.45, math.pi), (0.45, 0.0)):
        p = ph + phase
        fx = 0.2 + 1.1 * run * math.sin(p)
        fy = max(0.0, 0.55 * run * math.cos(p))
        hip = (-0.1, 2.45 + bob)
        foot = (fx, fy + 0.12)
        knee = _leg2(hip, foot, 1.35, 1.3, bend=-1.0)
        legs.append((s_off, hip, knee, foot))
    near_s = 0.45 if float(np.dot(side, cam.pos - base)) > 0 else -0.45
    legs.sort(key=lambda L: L[0] == near_s)                             # far leg first

    def limb(q, wid, col):                                             # a round-ended tube: ink first, colour inside
        for c, ww in ((FLAT_INK, wid + 2 * lw), (col, wid)):
            ctx.move_to(*q[0])
            for p in q[1:]:
                ctx.line_to(*p)
            ctx.set_source_rgb(*c)
            ctx.set_line_width(ww)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.stroke()

    def leg(L, col):
        s_off, hip, knee, foot = L
        limb(W([(hip[0] + 0.1, hip[1] + 0.15), tuple(knee)], s_off), 0.85 * px, col)   # a big drumstick thigh
        limb(W([tuple(knee), (foot[0], foot[1] + 0.05)], s_off), 0.36 * px, col)
        limb(W([(foot[0] - 0.15, foot[1] - 0.05), (foot[0] + 0.5, foot[1] - 0.07)], s_off), 0.24 * px, col)

    leg(legs[0], REX["far"])
    # the far arm (tiny, as a T-rex's were)
    fa = bend([(1.55, 2.75), (1.95, 2.45), (2.15, 2.6)])
    q = W(fa, -0.3)
    ctx.move_to(*q[0]); ctx.line_to(*q[1]); ctx.line_to(*q[2])
    ctx.set_source_rgb(*REX["far"]); ctx.set_line_width(0.16 * px); ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.stroke()
    # the lower jaw, swung open about the mouth corner (drawn before the head, so the head covers its hinge)
    cx, cy = 2.1, 3.5
    ca, sa = math.cos(-jaw), math.sin(-jaw)
    jaw_pts = [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in _REX_JAW]
    mouth = bend([(2.1, 3.55), (3.5, 3.6)] + [jaw_pts[1], jaw_pts[2], jaw_pts[3]])
    fill(W(mouth), REX["mouth"], ink=False)
    for i in range(5):                                                 # lower teeth, pointing up
        u = 0.15 + 0.17 * i
        x0, y0 = jaw_pts[0][0] + (jaw_pts[1][0] - jaw_pts[0][0]) * u, jaw_pts[0][1] + (jaw_pts[1][1] - jaw_pts[0][1]) * u
        tooth = [(x0 - 0.07, y0), (x0 + 0.07, y0), (x0 + 0.0 + 0.1 * math.sin(jaw), y0 + 0.17)]
        tooth = [(cx + (x - cx), y) for x, y in tooth]
        fill(W(bend(tooth)), (1, 1, 1), w=lw * 0.5)
    fill(W(bend(jaw_pts)), REX["body"])
    # the body: back spikes, then the outline filled, then a yellow belly clipped inside it
    top = _spline(bend(_REX_TOP), 6)
    for i in range(8, len(top) - 22, 4):                               # spikes along the back
        a, b = top[i], top[i + 4]
        mid = (a + b) / 2
        nrm = np.array([-(b - a)[1], (b - a)[0]])
        nrm = nrm / max(1e-6, np.hypot(*nrm))
        tip = mid + nrm * 0.38 - (b - a) * 0.25
        fill(W([tuple(a), tuple(b), tuple(tip)]), REX["spike"], w=lw * 0.8)
    outline = top + _spline(bend(_REX_JAW_TOP), 4)[1:] + _spline(bend(_REX_BOTTOM + [(-4.6, 2.75)]), 6)[1:]
    q = W([tuple(p) for p in outline])
    fill(q, REX["body"])
    for i in range(6):                                                 # upper teeth, pointing down
        x0 = 2.35 + 0.2 * i
        y0 = 3.58 + bob - 0.01 * i
        fill(W([(x0 - 0.07, y0), (x0 + 0.07, y0), (x0, y0 - 0.18)]), (1, 1, 1), w=lw * 0.5)
    ctx.save()                                                         # the belly: a yellow band along the underside
    ctx.move_to(*q[0])
    for p in q[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.clip()
    belly = _spline(bend([(1.95, 3.15), (1.5, 2.55), (0.6, 2.05), (-0.4, 2.0), (-1.4, 2.3), (-2.8, 2.55),
                          (-2.6, 2.75), (-1.2, 2.6), (0.2, 2.45), (1.1, 2.85), (1.75, 3.3)]), 5)
    fill(W([tuple(p) for p in belly]), REX["belly"], ink=False)
    ctx.restore()
    ctx.move_to(*q[0])                                                 # the outline again, over the belly
    for p in q[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.set_source_rgb(*FLAT_INK)
    ctx.set_line_width(lw)
    ctx.stroke()
    # the eye (a white with a pupil looking ahead), a brow, a nostril
    ex, ey = W(bend([(2.75, 3.98)]))[0]
    er = 0.17 * px
    ctx.arc(ex, ey, er, 0, 2 * math.pi)
    ctx.set_source_rgb(1, 1, 1); ctx.fill_preserve()
    ctx.set_source_rgb(*FLAT_INK); ctx.set_line_width(lw * 0.7); ctx.stroke()
    fx = W(bend([(2.85, 3.98)]))[0][0] - ex
    ctx.arc(ex + fx * 0.6, ey, er * 0.5, 0, 2 * math.pi)
    ctx.fill()
    br = W(bend([(2.5, 4.12), (3.0, 4.22)]))
    ctx.move_to(*br[0]); ctx.line_to(*br[1]); ctx.set_line_width(lw * 1.3); ctx.stroke()
    nx, ny = W(bend([(3.45, 3.9)]))[0]
    ctx.arc(nx, ny, 0.05 * px, 0, 2 * math.pi); ctx.fill()
    # the near leg and arm
    leg(legs[1], REX["body"])
    q = W(bend([(1.55, 2.75), (1.95, 2.45), (2.15, 2.6)]), 0.3)
    ctx.move_to(*q[0]); ctx.line_to(*q[1]); ctx.line_to(*q[2])
    ctx.set_source_rgb(*FLAT_INK); ctx.set_line_width(0.2 * px); ctx.stroke()
    ctx.move_to(*q[0]); ctx.line_to(*q[1]); ctx.line_to(*q[2])
    ctx.set_source_rgb(*REX["body"]); ctx.set_line_width(0.2 * px - 2 * lw); ctx.stroke()
    if run > 0.3:
        _speed_lines(ctx, cam, d, t, int(t * 24), S, 4.0 * k)
    hx, hy = W(bend([(2.6, 4.3)]))[0]
    return hx, hy


def _speed_lines(ctx, cam, it, t, frame, S, height_m):
    """motion lines streaming off the back of something running fast (they redraw every other frame)"""
    ang = it["dir"]
    fwd = np.array([math.cos(ang), 0.0, math.sin(ang)])
    base = np.array(it["pos"], float)
    rng = random.Random(zlib.crc32(repr((it["id"], frame // 2)).encode()))
    for i in range(5):
        h = rng.uniform(0.25, 0.95) * height_m * M
        back = rng.uniform(0.3, 0.9) * height_m * M * (1.6 if height_m > 2 else 0.5)
        ln = rng.uniform(0.5, 1.2) * height_m * M * 0.35
        p = base - fwd * back + np.array([0.0, h, 0.0])
        q = cam.project(np.array([p, p - fwd * ln]))
        ctx.move_to(*q[0]); ctx.line_to(*q[1])
        ctx.set_source_rgba(*FLAT_INK, 0.55)
        ctx.set_line_width(max(1.5, 3.0 * S))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()


def _sky_fx(ctx, cam, world, frame, S, hz):
    """the place's sun (a big white-hot disc with rays) and falling particle streaks (story rule for 2030: with no
    magnetic field, storms of charged particles reach the ground and glow on the way down)"""
    W, H = cam.W, cam.H
    sd = getattr(world, "sun", None)
    if sd is not None:
        d = np.asarray(sd, float)
        c = cam.view((cam.pos + d / np.linalg.norm(d) * 1e7)[None])[0]
        if c[2] > 0:
            sx, sy = cam.screen(c[None])[0]
            r = 95 * S
            for k in range(28):                                        # rays (they turn very slowly)
                a = 2 * math.pi * k / 28 + frame * 0.002
                ln = (2.2 if k % 2 else 3.4) * r
                ctx.move_to(sx + math.cos(a) * r * 1.25, sy + math.sin(a) * r * 1.25)
                ctx.line_to(sx + math.cos(a) * ln, sy + math.sin(a) * ln)
            ctx.set_source_rgba(1.0, 0.86, 0.45, 0.55)
            ctx.set_line_width(4 * S)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.stroke()
            ctx.arc(sx, sy, r * 1.15, 0, 2 * math.pi)
            ctx.set_source_rgba(1.0, 0.95, 0.75, 0.6)
            ctx.fill()
            ctx.arc(sx, sy, r, 0, 2 * math.pi)
            ctx.set_source_rgb(1.0, 0.99, 0.92)
            ctx.fill_preserve()
            ctx.set_source_rgb(0.95, 0.66, 0.25)
            ctx.set_line_width(3 * S)
            ctx.stroke()
    for az, el, sz in getattr(world, "clouds", None) or ():          # white storybook clouds (flat, a soft edge)
        d = np.array([math.sin(az), el, math.cos(az)])
        c = cam.view((cam.pos + d / np.linalg.norm(d) * 1e7)[None])[0]
        if c[2] <= 0:
            continue
        cx, cy = cam.screen(c[None])[0]
        if cy > hz:
            continue
        R = 90 * S * sz
        rng = random.Random(int(az * 1000))
        puffs = [(0, 0, 1.0), (-1.1, 0.25, 0.75), (1.1, 0.2, 0.8), (-0.5, -0.45, 0.8), (0.55, -0.5, 0.7),
                 (-1.9, 0.45, 0.5), (1.9, 0.4, 0.55)]
        for k_, (px, py, pr) in enumerate(puffs):
            ctx.arc(cx + px * R + rng.uniform(-6, 6) * S, cy + py * R, pr * R, 0, 2 * math.pi)
            ctx.new_sub_path()
        ctx.rectangle(cx - 2.3 * R, cy + 0.3 * R, 4.6 * R, 0.5 * R)
        ctx.set_source_rgba(1, 1, 1, 0.95)
        ctx.fill()
    n = int(getattr(world, "streaks", 0) or 0)
    if n:
        rng = random.Random(77)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for k in range(n):                                             # each streak slides down and repeats
            x0 = rng.uniform(-0.2, 1.1) * W
            ln = rng.uniform(0.08, 0.22) * H
            sp = rng.uniform(0.6, 1.4)
            y = (rng.uniform(0, 1) * (hz + ln) + frame * 9 * S * sp) % (hz + ln) - ln
            x = x0 + y * 0.35
            ctx.move_to(x, y)
            ctx.line_to(x + ln * 0.35, y + ln)
            ctx.set_source_rgba(0.96, 0.45, 0.22, 0.38)
            ctx.set_line_width(rng.uniform(1.5, 3.5) * S)
            ctx.stroke()


INK_K = [1.0]               # outline weight of the scenery (the cinema look draws thinner lines: less "cartoon")
SKY_HOOK = []               # drawn into the sky behind everything (the storm wall): f(ctx, cam, horizon_y)
MOOD = [None]               # the time of day of the scene being drawn ("sunset", "night", "dawn"; None = the place's own)
TIMES = {
    "sunset": {"top": (0.36, 0.40, 0.70), "sky": (0.99, 0.66, 0.40), "veil": (0.95, 0.45, 0.20, 0.16), "sun": -0.02},
    "evening": {"top": (0.36, 0.40, 0.70), "sky": (0.99, 0.66, 0.40), "veil": (0.95, 0.45, 0.20, 0.16), "sun": -0.02},
    "dawn": {"top": (0.55, 0.68, 0.90), "sky": (0.99, 0.84, 0.70), "veil": (1.0, 0.85, 0.65, 0.08), "sun": 0.01},
    "morning": {"top": (0.55, 0.68, 0.90), "sky": (0.99, 0.84, 0.70), "veil": (1.0, 0.85, 0.65, 0.08), "sun": 0.01},
    "night": {"top": (0.02, 0.03, 0.10), "sky": (0.08, 0.11, 0.26), "veil": (0.03, 0.05, 0.18, 0.50), "moon": True},
}


def _time_sky(ctx, cam, name, frame, S, hz):
    """the sky of an hour: a low red-gold sun at sunset / dawn (on the horizon, a band of glow); at night stars and a
    moon (stars twinkle slowly)"""
    W = cam.W
    t = TIMES[name]
    if "sun" in t:
        d = np.array([-0.35, t["sun"], 1.0])
        c = cam.view((cam.pos + d / np.linalg.norm(d) * 1e7)[None])[0]
        if c[2] > 0:
            sx, sy = cam.screen(c[None])[0]
            for rr, a in ((260, 0.10), (170, 0.18), (110, 0.30)):
                ctx.arc(sx, sy, rr * S, 0, 2 * math.pi)
                ctx.set_source_rgba(1.0, 0.75, 0.40, a)
                ctx.fill()
            ctx.arc(sx, sy, 70 * S, 0, 2 * math.pi)
            ctx.set_source_rgb(1.0, 0.86, 0.55)
            ctx.fill()
    if t.get("moon"):
        rng = random.Random(11)
        for k in range(140):
            x, y = rng.uniform(0, W), rng.uniform(0, max(1.0, hz) * 0.95)
            tw = 0.5 + 0.5 * math.sin(frame * 0.08 + k)
            ctx.arc(x, y, rng.uniform(0.8, 2.2) * S, 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 0.95, 0.35 + 0.5 * tw)
            ctx.fill()
        d = np.array([0.4, 0.45, 1.0])
        c = cam.view((cam.pos + d / np.linalg.norm(d) * 1e7)[None])[0]
        if c[2] > 0:
            mx, my = cam.screen(c[None])[0]
            ctx.arc(mx, my, 46 * S, 0, 2 * math.pi)
            ctx.set_source_rgb(0.97, 0.96, 0.88)
            ctx.fill()


def panel_x(x, y, z, w, h, **kw):
    """a flat outline on a wall facing +x (a door, a window on a house side that faces the lane)"""
    v = [(x, y, z - w / 2), (x, y, z + w / 2), (x, y + h, z + w / 2), (x, y + h, z - w / 2)]
    return Mesh(v, [(0, 1, 2, 3)], **kw)


def _ground(ctx, pen, cam, S, seed):
    """the ground is only the horizon line (economy of line: nothing else is drawn on it)"""
    W = cam.W
    hz = cam.project(cam.pos[None] + np.array([[cam.fwd[0] * 1e6, 0.0 - cam.pos[1], cam.fwd[2] * 1e6]]))[0][1]
    _steady(ctx, (-50, hz), (W + 50, hz), 2.0 * S, PENCIL, "horizon", seed)


def _shadow(ctx, cam, x, z, rx, rz, S):
    """a soft pencil shadow on the ground under a thing (it sits on the ground instead of floating)"""
    sx, sz = x + 0.35 * rx, z + 0.25 * rz                               # (pushed away from the sun a little)
    pts = np.array([(sx + rx * math.cos(a), 0.5, sz + rz * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 18)])
    c = cam.view(pts)
    if np.any(c[:, 2] < 10):
        return
    q = cam.screen(c)
    ctx.move_to(*q[0])
    for p in q[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.set_source_rgba(0.25, 0.22, 0.2, 0.16)
    ctx.fill()


def _sky_ground(ctx, cam):
    """storybook washes: a pale sky above the horizon, a warm earth below"""
    W, H = cam.W, cam.H
    hz = cam.project(cam.pos[None] + np.array([[cam.fwd[0] * 1e6, 0.0 - cam.pos[1], cam.fwd[2] * 1e6]]))[0][1]
    g = cairo.LinearGradient(0, 0, 0, max(1.0, hz))
    g.add_color_stop_rgba(0, 0.62, 0.78, 0.90, 0.45)
    g.add_color_stop_rgba(1, 0.80, 0.88, 0.92, 0.25)
    ctx.rectangle(0, 0, W, hz)
    ctx.set_source(g)
    ctx.fill()
    g = cairo.LinearGradient(0, hz, 0, H)
    g.add_color_stop_rgba(0, 0.80, 0.78, 0.55, 0.30)
    g.add_color_stop_rgba(1, 0.76, 0.66, 0.46, 0.40)
    ctx.rectangle(0, hz, W, H - hz)
    ctx.set_source(g)
    ctx.fill()


def draw_frame(W, H, cam, world, people, t, frame, bubble=None):
    """one frame (BGRA bytes): paper, ground, the world's shapes and the people back to front, a bubble"""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    draw(ctx, W, H, cam, world, people, t, frame, bubble)
    surf.flush()
    return bytes(surf.get_data())


def _in_house(world, pos):
    h = getattr(world, "house", None)
    return bool(h) and h[0] < pos[0] < h[1] and h[2] < pos[2] < h[3]


def _house_order(world, cam):
    """the drawing order (a sort key, bigger = drawn earlier) when the place has a house you can go into. Painting
    back to front by each thing's middle can't settle walls with holes, so the house sets layers:
    from outside - the far world, the inner wall faces, the floor, what is inside (seen through the door and
    windows), the outer walls and roof, then the near world; from inside - the whole outside first (seen through
    the windows), the walls and ceiling, the floor, then the room and its people back to front."""
    h = getattr(world, "house", None)
    if not h:
        return lambda m, d: 1e12 if getattr(m, "under", False) else d
    x0, x1, z0, z1, H = h
    hd = float(np.dot(np.array([(x0 + x1) / 2, H / 2, (z0 + z1) / 2]) - cam.pos, cam.fwd))
    inside_cam = x0 < cam.pos[0] < x1 and z0 < cam.pos[2] < z1 and cam.pos[1] < H

    def key(m, d):
        if isinstance(m, dict):                                        # a person / a prop on the ground
            pos = m.get("pos")
            ins = _in_house(world, pos)
            shell = False
            name = ""
        else:
            ins, shell, name = getattr(m, "inside", False), getattr(m, "shell", False), m.name
            if getattr(m, "under", False):
                return 1e12
        if inside_cam:
            if shell:
                return 1e9 + (2.0 if name in ("limewall", "tiles") else 1.0) * 1e3 + d * 1e-3
            if ins:                                                    # (floor, then things on walls, then the room)
                return 5e8 if name == "redfloor" else (4e8 if name in ("hole", "whiteboard") else d)
            return 2e9 + d
        if ins:
            return hd + 2.0 + (0.6 if name == "redfloor" else (0.5 if name == "hole" else d * 1e-6))
        if shell:
            return hd + (3.0 if name in ("limewall_in", "ceiling_wood") else d * 1e-6)
        return d
    return key


CAR_COL = {"black": (0.12, 0.12, 0.14), "white": (0.92, 0.92, 0.90), "grey": (0.55, 0.57, 0.60),
           "olive": (0.33, 0.38, 0.24), "red": (0.70, 0.16, 0.14)}


def cars_at(spec, t):
    """the scene's cars ("stick_cars"): each drives from "from" to "to" (stage x / z, like people) between "start"
    and "end" seconds, easing in and out, and parks; [(id, pos, heading, speed, colour, kind)]"""
    out = []
    for c in spec or ():
        if c.get("path"):                                              # a route: through each point in turn, at
            out.append(_on_path(c, t))                                 # one speed, easing at the start and end
            continue
        a, b = c.get("from") or c.get("to"), c.get("to") or c.get("from")
        if not a:
            continue
        t0, t1 = float(c.get("start", 0)), float(c.get("end", 0))
        u = 0.0 if t1 <= t0 else max(0.0, min(1.0, (t - t0) / (t1 - t0)))
        e = u * u * (3 - 2 * u)
        x = a["x"] + (b["x"] - a["x"]) * e
        z = a.get("z", 0) + (b.get("z", 0) - a.get("z", 0)) * e
        p0 = np.array(stage_to_world(a["x"], 0, a.get("z", 0)))
        p1 = np.array(stage_to_world(b["x"], 0, b.get("z", 0)))
        d = p1 - p0
        head = math.atan2(d[2], d[0]) if np.linalg.norm(d) > 1 else math.radians(float(c.get("heading", 0)))
        moving = t0 < t < t1
        col = c.get("color", "black")
        col = CAR_COL.get(col, None) or (tuple(int(col[i:i + 2], 16) / 255 for i in (1, 3, 5)) if str(col).startswith("#")
                                         else CAR_COL["black"])
        out.append((c.get("id", "car"), np.array(stage_to_world(x, 0, z)), head, moving, col, c.get("kind", "car")))
    return out


def _car_col(c):
    col = c.get("color", "black")
    return CAR_COL.get(col, None) or (tuple(int(col[i:i + 2], 16) / 255 for i in (1, 3, 5))
                                      if str(col).startswith("#") else CAR_COL["black"])


def _on_path(c, t):
    """a vehicle on a route ("path": [{x, z}, ...] stage points): the whole route between "start" and "end" at a
    steady speed (easing out of the start and into the stop), turning to follow each leg"""
    pts = [np.array(stage_to_world(q["x"], 0, q.get("z", 0)), float) for q in c["path"]]
    seg = [float(np.linalg.norm(b - a)) for a, b in zip(pts, pts[1:])]
    total = sum(seg) or 1.0
    t0, t1 = float(c.get("start", 0)), float(c.get("end", 0))
    u = 0.0 if t1 <= t0 else max(0.0, min(1.0, (t - t0) / (t1 - t0)))
    ease = float(c.get("ease", 0.12))                                  # share of the time spent speeding up / down
    if ease > 0:                                                       # (constant speed in the middle)
        if u < ease:
            s_ = u * u / (2 * ease)
        elif u > 1 - ease:
            s_ = 1 - (1 - u) ** 2 / (2 * ease)
        else:
            s_ = u - ease / 2
        s_ /= (1 - ease)
    else:
        s_ = u
    d = max(0.0, min(1.0, s_)) * total
    k = 0
    while k < len(seg) - 1 and d > seg[k]:
        d -= seg[k]
        k += 1
    a, b = pts[k], pts[min(k + 1, len(pts) - 1)]
    f = 0.0 if seg[k] <= 0 else min(1.0, d / seg[k])
    pos = a + (b - a) * f
    dv = b - a
    head = math.atan2(dv[2], dv[0]) if np.linalg.norm(dv) > 1 else math.radians(float(c.get("heading", 0)))
    return (c.get("id", "car"), pos, head, t0 < t < t1, _car_col(c), c.get("kind", "car"))


def bike_meshes(cid, pos, head, col, t=0.0):
    """a motorbike (a 125 cc village bike, 2 m long): two spoked wheels, the tank and seat, a headlight, the
    handlebar, the exhaust pipe. The rider is drawn by the story (the "rider" of the vehicle)"""
    parts = []
    ca, sa = math.cos(head), math.sin(head)

    def turn(x, y, z):
        return (pos[0] + x * ca - z * sa, y, pos[2] + x * sa + z * ca)

    def add(vf, name, ink=0.9, key=""):
        v, f = vf
        m = Mesh([turn(*q) for q in v], f, ink=ink, name=name)
        m.key = f"{cid}{name}{key}"
        parts.append(m)
    body = "car_%02x%02x%02x" % tuple(int(x * 255) for x in col)
    WASH.setdefault(body, tuple(col))
    for k, x in enumerate((-0.68, 0.68)):                              # the wheels
        v, f = places.disk_parts((x * M, 0.32 * M, 0.0), (0, 0, 1), 0.32 * M, 0.1 * M, n=12)
        add(([tuple(q) for q in v], f), "tyre", key=f"w{k}")
        v, f = places.disk_parts((x * M, 0.32 * M, 0.0), (0, 0, 1), 0.14 * M, 0.12 * M, n=8)
        add(([tuple(q) for q in v], f), "hub", ink=0.6, key=f"h{k}")
    add(_extrude([(-0.55, 0.55), (0.35, 0.55), (0.55, 0.85), (0.20, 0.95), (-0.15, 0.82), (-0.65, 0.80)], -0.14, 0.14),
        body, key="body")                                              # frame, tank and side panels
    add(_extrude([(-0.70, 0.80), (-0.10, 0.82), (-0.10, 0.90), (-0.70, 0.90)], -0.13, 0.13), "chair", ink=0.7, key="seat")
    add(places.rod_parts((0.45 * M, 0.85 * M, 0), (0.68 * M, 0.32 * M, 0), 0.06 * M), "steel", ink=0.7, key="fork")
    add(places.rod_parts((0.42 * M, 1.05 * M, -0.32 * M), (0.42 * M, 1.05 * M, 0.32 * M), 0.04 * M), "steel", ink=0.7,
        key="bar")
    add(places.rod_parts((0.45 * M, 0.85 * M, 0), (0.42 * M, 1.05 * M, 0), 0.05 * M), "steel", ink=0.7, key="stem")
    add(_cube((0.62 * M, 0.95 * M, 0.0), 0.08 * M, 0.14 * M, 0.16 * M), "headlight", ink=0.6, key="hl")
    add(places.rod_parts((-0.2 * M, 0.38 * M, 0.17 * M), (-0.8 * M, 0.45 * M, 0.17 * M), 0.07 * M), "steel", ink=0.6,
        key="pipe")
    return parts


MOTO = None
DRIVE = None
INSIDE = [None]          # the camera is inside a car this frame: ("driver" | "profile" | "pov", car pos, heading)


def _drive_pose():
    """at the wheel: sitting, hands up on the steering wheel in front"""
    global DRIVE
    if DRIVE is None:
        from .poses import SIT, add
        DRIVE = add(SIT, torso=-6, head=-2, an_u=62, an_l=-12, af_u=58, af_l=-10)
    return DRIVE


def _moto_pose():
    """the rider's pose on a motorbike: sitting astride, leaning a little forward, hands on the bars"""
    global MOTO
    if MOTO is None:
        from .poses import SIT, add
        MOTO = add(SIT, torso=14, head=-10, an_u=78, an_l=-30, af_u=74, af_l=-30, ln_t=62, ln_s=-80, lf_t=58, lf_s=-78)
    return MOTO


CAR_SIDE = [(-2.30, 0.32), (-2.36, 0.62), (-2.25, 0.88), (-1.85, 0.97), (-1.35, 1.00), (-0.95, 1.42), (0.35, 1.45),
            (1.05, 1.00), (1.75, 0.93), (2.25, 0.80), (2.38, 0.55), (2.30, 0.32)]   # a cartoon sedan's side, metres
CAR_WIN = [[(-1.22, 1.03), (-0.88, 1.36), (0.30, 1.38), (0.88, 1.03)]]             # the window band (front to back)
SUV_SIDE = [(-2.20, 0.40), (-2.26, 0.95), (-2.20, 1.78), (-2.05, 1.88), (0.75, 1.88), (1.30, 1.22), (2.05, 1.10),
            (2.26, 0.95), (2.30, 0.60), (2.22, 0.40)]          # a tall boxy SUV (like a Scorpio): flat roof, short bonnet
SUV_WIN = [[(-2.02, 1.24), (-2.02, 1.74), (-1.05, 1.74), (-1.05, 1.24)],             # back quarter window
           [(-0.92, 1.24), (-0.92, 1.74), (-0.02, 1.74), (-0.02, 1.24)],             # back door
           [(0.10, 1.24), (0.10, 1.74), (0.80, 1.74), (1.16, 1.24)]]                 # front door
PICKUP_SIDE = [(-2.62, 0.45), (-2.66, 1.08), (-0.62, 1.08), (-0.58, 1.80), (0.50, 1.82), (1.30, 1.24),
               (2.40, 1.12), (2.62, 0.96), (2.66, 0.55), (2.58, 0.42)]  # an extended-cab pickup: open bed behind
PICKUP_WIN = [[(-0.48, 1.20), (-0.48, 1.72), (-0.06, 1.72), (-0.06, 1.20)],             # the small rear cab window
              [(0.04, 1.20), (0.04, 1.72), (0.48, 1.74), (1.18, 1.24)]]                 # the door window
CAR_SHAPE = {  # side, windows, wheel x / radius, headlight (x, y), taillight (x, y, h), roof top
    "sedan": (CAR_SIDE, CAR_WIN, 1.45, 0.38, (2.34, 0.70), (-2.36, 0.72, 0.16), 1.45),
    "suv": (SUV_SIDE, SUV_WIN, 1.40, 0.42, (2.27, 0.95), (-2.24, 1.35, 0.40), 1.88),
    "pickup": (PICKUP_SIDE, PICKUP_WIN, 1.66, 0.44, (2.58, 0.98), (-2.65, 0.92, 0.30), 1.82),
}
SEAT = {"pickup": (0.38, 0.36), "suv": (0.35, 0.34), "agent": (0.35, 0.34)}   # driver's seat: metres ahead, up


def seat_of(kind):
    """where the driver sits in a vehicle kind: (metres ahead of its middle, seat height above a sedan's)"""
    return SEAT.get(kind, (-0.3, 0.08))


CAR_EXTRA = {}           # this scene's car specs by id: "mud" (splashed with mud), "door" [open, close] (seconds)


def _flown(meshes, pos, head, fly, t):
    """a car picked up by hurricane wind (story rule: a real car needs ~70 m/s gusts or a tornado to lift; we
    let a Cat 4 do it on camera): it rises on a curve, rolls over sideways (the wind under the floor) and pitches.
    fly: {"at": s, "up": metres, "roll": degrees a second, "pitch": degrees a second}"""
    u = t - float(fly.get("at", 0.0))
    if u <= 0:
        return meshes
    if fly.get("mode", "shake") == "shake":                            # what really happens to a 1.5 t car in a Cat 4:
        g = (u / 1.6) % 1.0                                            # each gust rocks it up on its far wheels and
        gust = math.exp(-((g - 0.2) / 0.12) ** 2)                      # drops it back (it rings on its springs)
        roll = math.radians(float(fly.get("rock", 9.0))) * (gust + 0.25 * math.sin(u * 11.0) * gust)
        pitch = math.radians(1.5) * math.sin(u * 7.0)
        up = 0.0
    else:                                                              # (story only: blown into the air)
        up = float(fly.get("up", 5.0)) * M * (1.0 - math.exp(-u / 0.6))
        roll = math.radians(float(fly.get("roll", 220.0))) * u
        pitch = math.radians(float(fly.get("pitch", 60.0))) * u
    c = np.array([pos[0], 0.8 * M, pos[2]])
    fw = np.array([math.cos(head), 0.0, math.sin(head)])

    def rot(v, axis, a):                                               # Rodrigues: v turned by a about axis
        axis = axis / np.linalg.norm(axis)
        return (v * math.cos(a) + np.cross(axis, v) * math.sin(a) +
                np.outer(v @ axis, axis) * (1 - math.cos(a)))
    side = np.array([-fw[2], 0.0, fw[0]])
    out = []
    for m in meshes:
        v = rot(m.v - c, fw, roll)
        v = rot(v, side, pitch) + c + np.array([0.0, up, 0.0])
        m2 = Mesh(v, m.f, ink=m.ink, hatch=m.hatch, name=m.name)
        for a_ in ("key", "car_id"):
            if hasattr(m, a_):
                setattr(m2, a_, getattr(m, a_))
        out.append(m2)
    return out


def jet_meshes(cid, pos, head, col, t=0.0, alt=0.0, stairs=False):
    """a Government of India business jet (VIP flight, Indian Air Force): white, the tricolour stripe down its
    side, the IAF roundel (saffron, white, green rings) on the T-tail, oval cabin windows, two engines at the rear,
    swept wings set low; on the ground its wheels are down and its airstair can stand open at the front door.
    ~19 m long, 19 m wingspan (a real VIP jet's size)"""
    from . import stick3d_places as pl
    ca, sa = math.cos(head), math.sin(head)
    pitch = math.radians(min(10.0, alt * 0.8)) if alt > 0.5 else 0.0  # (nose up while it climbs)
    y0 = alt * M

    def tw(x, y, z):
        y2 = y + x * math.sin(pitch)
        return (pos[0] + x * ca - z * sa, y0 + y2, pos[2] + x * sa + z * ca)

    out = []

    def add(m):
        m.key = f"{cid}{m.name}{len(out)}"
        m.car_id = str(cid)
        out.append(m)

    def nm(c):
        n_ = "car_%02x%02x%02x" % tuple(int(x * 255) for x in c)
        WASH.setdefault(n_, tuple(c))
        return n_

    def loft(rings, n=10, name="", ink=0.9):
        V, F = [], []
        for x, yc, hh, hw in rings:
            for k in range(n):
                a = 2 * math.pi * (k + 0.5) / n
                V.append(tw(x * M, (yc + hh * math.sin(a)) * M, hw * math.cos(a) * M))
        for r in range(len(rings) - 1):
            for k in range(n):
                a, b = r * n + k, r * n + (k + 1) % n
                F.append((a, b, b + n, a + n))
        F.append(tuple(range(n)))
        last = (len(rings) - 1) * n
        F.append(tuple(range(last + n - 1, last - 1, -1)))
        add(Mesh(V, F, ink=ink, name=name))
    white = nm((0.95, 0.95, 0.94))
    gy = 1.6                                                           # fuselage centre height on the ground
    loft([(9.6, gy - 0.1, 0.15, 0.12), (8.8, gy, 0.75, 0.7), (7.0, gy + 0.05, 1.05, 1.0), (0.0, gy + 0.05, 1.1, 1.05),
          (-6.0, gy + 0.15, 1.0, 0.95), (-8.6, gy + 0.6, 0.55, 0.45), (-9.4, gy + 0.9, 0.25, 0.2)], name=white)
    for k, c in enumerate(((1.0, 0.6, 0.2), (0.07, 0.53, 0.03))):      # the tricolour stripe (saffron over green)
        for sd in (-1, 1):
            y_ = gy - 0.2 - 0.18 * k
            add(Mesh(*pl.sheet_parts([tw(8.0 * M, y_ * M, sd * 1.07 * M), tw(-7.5 * M, (y_ + 0.08) * M, sd * 1.0 * M),
                                      tw(-7.5 * M, (y_ + 0.24) * M, sd * 1.0 * M),
                                      tw(8.0 * M, (y_ + 0.16) * M, sd * 1.07 * M)]), ink=0.2, name=nm(c)))
    win = []
    for sd in (-1, 1):                                                 # oval windows (dark: the night outside)
        for k in range(7):
            x = 5.6 - k * 1.3
            win.append(([tw(x * M, (gy + 0.25) * M, sd * 1.09 * M), tw((x - 0.45) * M, (gy + 0.25) * M, sd * 1.09 * M),
                         tw((x - 0.45) * M, (gy + 0.65) * M, sd * 1.08 * M), tw(x * M, (gy + 0.65) * M, sd * 1.08 * M)],
                        [(0, 1, 2, 3), (3, 2, 1, 0)]))
    win.append(([tw(8.6 * M, (gy + 0.45) * M, -0.6 * M), tw(8.0 * M, (gy + 0.8) * M, -0.75 * M),
                 tw(8.0 * M, (gy + 0.8) * M, 0.75 * M), tw(8.6 * M, (gy + 0.45) * M, 0.6 * M)], [(0, 1, 2, 3), (3, 2, 1, 0)]))
    add(pl.merged(win, Mesh, ink=0.6, name="heli_glass"))
    wing = []
    for sd in (-1, 1):                                                 # swept wings, set low, with winglets
        wing.append(([tw(1.6 * M, (gy - 0.6) * M, sd * 1.0 * M), tw(-1.8 * M, (gy - 0.6) * M, sd * 1.0 * M),
                      tw(-4.6 * M, (gy - 0.3) * M, sd * 9.4 * M), tw(-3.0 * M, (gy - 0.3) * M, sd * 9.4 * M)],
                     [(0, 1, 2, 3), (3, 2, 1, 0)]))
        wing.append(([tw(-3.0 * M, (gy - 0.3) * M, sd * 9.4 * M), tw(-4.6 * M, (gy - 0.3) * M, sd * 9.4 * M),
                      tw(-5.0 * M, (gy + 0.9) * M, sd * 9.6 * M), tw(-4.2 * M, (gy + 0.9) * M, sd * 9.6 * M)],
                     [(0, 1, 2, 3), (3, 2, 1, 0)]))
    add(pl.merged(wing, Mesh, ink=0.8, name=white))
    for sd in (-1, 1):                                                 # the two rear engines
        loft([(-4.6, gy + 0.55, 0.42, 0.42), (-7.2, gy + 0.55, 0.38, 0.38)], n=10, name=nm((0.80, 0.81, 0.83)))
        m = out.pop()
        m2 = Mesh([(p_[0] - sa * sd * 1.55 * M, p_[1], p_[2] + ca * sd * 1.55 * M) for p_ in m.v], m.f, ink=0.8,
                  name=m.name)
        add(m2)
    add(Mesh(*pl.sheet_parts([tw(-6.6 * M, (gy + 0.9) * M, 0), tw(-9.0 * M, (gy + 0.9) * M, 0),
                              tw(-10.4 * M, (gy + 4.0) * M, 0), tw(-9.0 * M, (gy + 4.0) * M, 0)]), ink=0.8, name=white))
    add(Mesh(*pl.sheet_parts([tw(-9.0 * M, (gy + 4.0) * M, -3.2 * M), tw(-10.6 * M, (gy + 4.0) * M, -3.2 * M),
                              tw(-10.6 * M, (gy + 4.0) * M, 3.2 * M), tw(-9.0 * M, (gy + 4.0) * M, 3.2 * M)]), ink=0.8,
             name=white))                                              # the T-tail
    for r, c in ((0.55, (1.0, 0.6, 0.2)), (0.36, (0.97, 0.97, 0.97)), (0.18, (0.07, 0.53, 0.03))):
        for sd in (-1, 1):                                             # the IAF roundel on the fin, both sides
            V = [tw((-8.8 + r * math.cos(a)) * M, (gy + 2.6 + r * math.sin(a)) * M, sd * (0.03 + 0.01 * (0.6 - r)) * M)
                 for a in [2 * math.pi * k / 14 for k in range(14)]]
            F = [tuple(range(14)), tuple(range(13, -1, -1))]
            add(Mesh(V, F, ink=0.3, name=nm(c)))
    if alt < 3.0:                                                      # wheels down
        gear = []
        for x_, z_ in ((7.6, 0.0), (-1.2, -1.6), (-1.2, 1.6)):
            gear.append(pl.rod_parts(tw(x_ * M, (gy - 0.7) * M, z_ * M), tw(x_ * M, 0.35 * M, z_ * M), 0.12 * M))
            gear.append(pl.disk_parts(tw(x_ * M, 0.32 * M, z_ * M), np.array([-sa, 0, ca]), 0.32 * M, 0.25 * M))
        add(pl.merged(gear, Mesh, ink=0.6, name="car_trim_dark"))
    if stairs and alt < 0.5:                                           # the airstair down from the front door
        st = []
        dx, dz = 6.6, -1.1
        for k in range(7):
            u = k / 6.0
            x_ = dx
            zz = dz - u * 2.2
            yy = (gy - 0.3) * (1 - u) + 0.05
            st.append(pl.rod_parts(tw((x_ - 0.55) * M, yy * M, zz * M), tw((x_ + 0.55) * M, yy * M, zz * M), 0.12 * M))
        for sx in (-0.6, 0.6):
            st.append(pl.rod_parts(tw((dx + sx) * M, (gy + 0.5) * M, dz * M), tw((dx + sx) * M, 0.9 * M, (dz - 2.2) * M),
                                   0.05 * M))
        add(pl.merged(st, Mesh, ink=0.6, name="car_trim_dark"))
        add(Mesh(*pl.sheet_parts([tw(7.1 * M, (gy - 0.45) * M, -1.1 * M), tw(6.1 * M, (gy - 0.45) * M, -1.1 * M),
                                  tw(6.1 * M, (gy + 0.85) * M, -1.08 * M), tw(7.1 * M, (gy + 0.85) * M, -1.08 * M)]),
                 ink=0.6, name="win_lit"))                             # the lit open door
    return out


def apache_meshes(cid, pos, head, col, t=0.0, alt=25.0):
    """an attack-helicopter shape (like an AH-64, the user's picture): a slim body that narrows into the tail boom,
    the stepped two-seat canopy with framed panes, the sensor ball on the nose, engine pods on the shoulders,
    stub wings with a rocket pod and missiles, two main wheels and a tail wheel, the swept fin with its
    4-blade tail rotor and the tailplane, and the 4-blade main rotor on its mast and hub dome (about 17.7 m long,
    rotor 14.6 m across; drawn turning 2 a second - the real 4.8 strobe on film)"""
    from . import stick3d_places as pl
    ca, sa = math.cos(head), math.sin(head)
    y0 = alt * M + 0.08 * M * math.sin(t * 1.7)

    def tw(x, y, z):                                                   # local (forward, up, side) -> world
        return (pos[0] + x * ca - z * sa, y0 + y, pos[2] + x * sa + z * ca)

    out = []

    def add(m):
        m.key = f"{cid}{m.name}{len(out)}"
        m.car_id = str(cid)
        out.append(m)

    def nm(c):
        n_ = "car_%02x%02x%02x" % tuple(int(x * 255) for x in c)
        WASH.setdefault(n_, tuple(c))
        return n_
    body_c = nm(col)
    dark_c = nm(tuple(c * 0.72 for c in col))

    def loft(rings, n=8):                                              # rings: (x, y centre, half height, half width)
        V, F = [], []
        for x, yc, hh, hw in rings:
            for k in range(n):
                a = 2 * math.pi * (k + 0.5) / n
                V.append(tw(x * M, (yc + hh * math.sin(a)) * M, hw * math.cos(a) * M))
        for r in range(len(rings) - 1):
            for k in range(n):
                a, b = r * n + k, r * n + (k + 1) % n
                F.append((a, b, b + n, a + n))
        F.append(tuple(range(n)))
        last = (len(rings) - 1) * n
        F.append(tuple(range(last + n - 1, last - 1, -1)))
        return V, F
    v, f = loft([(4.1, 0.05, 0.25, 0.22), (3.4, 0.1, 0.45, 0.48), (2.0, 0.15, 0.62, 0.6), (0.0, 0.2, 0.78, 0.66),
                 (-1.8, 0.4, 0.8, 0.58), (-3.2, 0.55, 0.42, 0.34), (-7.6, 0.75, 0.26, 0.2), (-8.6, 0.8, 0.22, 0.16)])
    m = Mesh(v, f[::-1] if False else f, ink=0.9, name=body_c)
    add(m)
    add(Mesh([tw(*q) for q in [(1.0 * M, 0.82 * M, -0.5 * M), (2.7 * M, 0.55 * M, -0.46 * M),
                               (2.7 * M, 0.55 * M, 0.46 * M), (1.0 * M, 0.82 * M, 0.5 * M),
                               (1.1 * M, 1.45 * M, -0.36 * M), (2.4 * M, 1.05 * M, -0.34 * M),
                               (2.4 * M, 1.05 * M, 0.34 * M), (1.1 * M, 1.45 * M, 0.36 * M)]],
             [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)], ink=1.0, name="heli_glass"))
    add(Mesh([tw(*q) for q in [(-0.4 * M, 0.95 * M, -0.5 * M), (1.1 * M, 0.82 * M, -0.5 * M),
                               (1.1 * M, 0.82 * M, 0.5 * M), (-0.4 * M, 0.95 * M, 0.5 * M),
                               (-0.3 * M, 1.7 * M, -0.34 * M), (1.0 * M, 1.5 * M, -0.36 * M),
                               (1.0 * M, 1.5 * M, 0.36 * M), (-0.3 * M, 1.7 * M, 0.34 * M)]],
             [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)], ink=1.0, name="heli_glass"))
    fr = [pl.rod_parts(tw(1.05 * M, 1.02 * M, sd * 0.46 * M), tw(1.05 * M, 1.5 * M, sd * 0.37 * M), 0.06 * M)
          for sd in (-1, 1)]                                           # the canopy frames
    fr += [pl.rod_parts(tw(-0.35 * M, 1.72 * M, 0), tw(2.4 * M, 1.07 * M, 0), 0.05 * M)]
    add(pl.merged(fr, Mesh, ink=0.6, name=dark_c))
    b = ball(0, 0, 0, 0.32 * M, n=8, m=5)                              # the sensor turret on the nose
    add(Mesh([tw(4.2 * M + x, -0.05 * M + y, z) for x, y, z in b.v], b.f, ink=0.8, name=dark_c))
    for sd in (-1, 1):                                                 # engine pods on the shoulders
        v, f = loft([(0.8, 0.95, 0.28, 0.28), (0.4, 1.0, 0.36, 0.36), (-1.6, 1.0, 0.36, 0.36), (-2.0, 0.95, 0.24, 0.24)])
        add(Mesh([(p_[0] - sa * sd * 0.82 * M, p_[1], p_[2] + ca * sd * 0.82 * M) for p_ in v], f, ink=0.85,
                 name=body_c))
    wing = []                                                          # stub wings, a rocket pod and missiles
    for sd in (-1, 1):
        wing.append(([tw(0.9 * M, 0.25 * M, sd * 0.6 * M), tw(-0.1 * M, 0.25 * M, sd * 0.6 * M),
                      tw(-0.2 * M, 0.15 * M, sd * 2.3 * M), tw(0.6 * M, 0.15 * M, sd * 2.3 * M)],
                     [(0, 1, 2, 3), (3, 2, 1, 0)]))
    add(pl.merged(wing, Mesh, ink=0.8, name=dark_c))
    for sd in (-1, 1):
        v, f = loft([(1.0, -0.2, 0.22, 0.22), (-0.6, -0.2, 0.22, 0.22)], n=8)
        add(Mesh([(p_[0] - sa * sd * 1.9 * M, p_[1], p_[2] + ca * sd * 1.9 * M) for p_ in v], f, ink=0.8, name=dark_c))
        for mz in (1.25, 1.45):
            v, f = loft([(1.1, -0.15, 0.07, 0.07), (-0.2, -0.15, 0.07, 0.07)], n=6)
            add(Mesh([(p_[0] - sa * sd * mz * M, p_[1], p_[2] + ca * sd * mz * M) for p_ in v], f, ink=0.6,
                     name=nm((0.94, 0.94, 0.92))))
    gear = []                                                          # wheels: two mains and a tail wheel
    for sd in (-1, 1):
        gear.append(pl.rod_parts(tw(1.6 * M, -0.4 * M, sd * 0.5 * M), tw(2.0 * M, -1.2 * M, sd * 0.95 * M), 0.08 * M))
        gear.append(pl.disk_parts(tw(2.0 * M, -1.25 * M, sd * 1.0 * M), np.array([-sa, 0, ca]), 0.32 * M, 0.2 * M))
    gear.append(pl.rod_parts(tw(-8.0 * M, 0.55 * M, 0), tw(-8.1 * M, -0.1 * M, 0), 0.06 * M))
    gear.append(pl.disk_parts(tw(-8.1 * M, -0.15 * M, 0), np.array([-sa, 0, ca]), 0.16 * M, 0.1 * M))
    add(pl.merged(gear, Mesh, ink=0.6, name="car_trim_dark"))
    add(Mesh(*pl.sheet_parts([tw(-7.6 * M, 0.85 * M, 0), tw(-8.7 * M, 0.9 * M, 0), tw(-9.5 * M, 2.6 * M, 0),
                              tw(-8.9 * M, 2.6 * M, 0)]), ink=0.8, name=body_c))         # the fin, swept back
    add(Mesh(*pl.sheet_parts([tw(-8.2 * M, 0.75 * M, -1.3 * M), tw(-8.9 * M, 0.75 * M, -1.3 * M),
                              tw(-8.9 * M, 0.75 * M, 1.3 * M), tw(-8.2 * M, 0.75 * M, 1.3 * M)]), ink=0.8,
             name=body_c))                                             # the tailplane
    a = t * 2 * math.pi * 2.0
    tr = []                                                            # 4-blade tail rotor, on the fin's left
    c_ = (-9.1 * M, 2.3 * M, -0.25 * M)
    for k in range(4):
        ang = a * 2.5 + k * math.pi / 2
        tr.append(pl.rod_parts(tw(*c_), tw(c_[0] + 0.95 * M * math.cos(ang), c_[1] + 0.95 * M * math.sin(ang), c_[2]),
                               0.12 * M))
    add(pl.merged(tr, Mesh, ink=0.6, name=dark_c))
    add(pl.merged([pl.rod_parts(tw(0, 1.3 * M, 0), tw(0, 2.1 * M, 0), 0.18 * M)], Mesh, ink=0.7, name=dark_c))
    b = ball(0, 0, 0, 0.42 * M, sy=0.6, n=10, m=5)                     # the hub dome
    add(Mesh([tw(x, 2.35 * M + y, z) for x, y, z in b.v], b.f, ink=0.8, name=body_c))
    bl = []                                                            # 4 long flat blades (7.3 m each)
    for k in range(4):
        ang = a + k * math.pi / 2
        dx, dz = math.cos(ang), math.sin(ang)
        px, pz = -dz * 0.25 * M, dx * 0.25 * M
        r0, r1 = 0.3 * M, 7.3 * M
        bl.append(([tw(dx * r0 + px, 2.15 * M, dz * r0 + pz), tw(dx * r1 + px, 2.1 * M, dz * r1 + pz),
                    tw(dx * r1 - px, 2.1 * M, dz * r1 - pz), tw(dx * r0 - px, 2.15 * M, dz * r0 - pz)],
                   [(0, 1, 2, 3), (3, 2, 1, 0)]))
    add(pl.merged(bl, Mesh, ink=0.7, name=dark_c))
    return out


def heli_meshes(cid, pos, head, col, t=0.0, alt=25.0):
    """a rescue helicopter (Coast Guard style: red-orange and white), hovering or flying at alt metres: a rounded
    cabin with its bubble window, a tail boom with a fin and tail rotor, skids, and the main rotor turning (shown
    at 2 turns a second - the real ~5 a second would strobe on film, the wagon-wheel effect)"""
    from . import stick3d_places as pl
    ca, sa = math.cos(head), math.sin(head)
    y0 = alt * M + 0.08 * M * math.sin(t * 1.7)                        # (hovering: it never holds quite still)

    def tw(x, y, z):                                                   # local (forward x, up y, side z) -> world
        return (pos[0] + x * ca - z * sa, y0 + y, pos[2] + x * sa + z * ca)

    out = []

    def add(m, cid_=cid):
        m.key = f"{cid_}{m.name}{len(out)}"
        m.car_id = str(cid_)
        out.append(m)

    def nm(c):
        n_ = "car_%02x%02x%02x" % tuple(int(x * 255) for x in c)
        WASH.setdefault(n_, tuple(c))
        return n_
    b = ball(0, 0, 0, 1.0, sy=0.62, n=12, m=7)                         # the cabin: a ball stretched along the nose
    v = [tw(x * 2.2 * M, (y + 0.1) * 1.6 * M, z * 1.15 * M) for x, y, z in b.v]
    add(Mesh(v, b.f, ink=0.9, name=nm(col)))
    bw = ball(0, 0, 0, 1.0, sy=0.7, n=10, m=5)                         # the bubble window at the nose
    v = [tw(1.15 * M + x * 1.0 * M, 0.45 * M + y * 0.75 * M, z * 0.95 * M) for x, y, z in bw.v]
    add(Mesh(v, bw.f, ink=0.6, name="window"))
    add(pl.merged([pl.rod_parts(tw(-1.8 * M, 0.4 * M, 0), tw(-6.6 * M, 0.9 * M, 0), 0.32 * M)], Mesh, ink=0.8,
                  name=nm((0.95, 0.95, 0.93))))
    add(Mesh(*pl.sheet_parts([tw(-6.0 * M, 0.8 * M, 0), tw(-6.9 * M, 0.9 * M, 0), tw(-7.2 * M, 2.1 * M, 0),
                              tw(-6.6 * M, 2.0 * M, 0)]), ink=0.8, name=nm(col)))
    a = t * 2 * math.pi * 2.0                                          # main rotor
    blades = []
    for k in range(4):
        ang = a + k * math.pi / 2
        blades.append(pl.rod_parts(tw(0, 1.85 * M, 0), tw(5.4 * M * math.cos(ang), 1.9 * M, 5.4 * M * math.sin(ang)),
                                   0.16 * M))
    blades.append(pl.rod_parts(tw(0, 1.0 * M, 0), tw(0, 1.9 * M, 0), 0.18 * M))
    add(pl.merged(blades, Mesh, ink=0.7, name="car_trim_dark"))
    tr = []
    for k in range(2):                                                 # tail rotor (in the fin's plane)
        ang = a * 2.5 + k * math.pi / 2
        c_ = (-7.0 * M, 1.5 * M, 0.25 * M)
        tr.append(pl.rod_parts(tw(*c_), tw(c_[0] + 0.9 * M * math.cos(ang), c_[1] + 0.9 * M * math.sin(ang), c_[2]),
                               0.08 * M))
        tr.append(pl.rod_parts(tw(*c_), tw(c_[0] - 0.9 * M * math.cos(ang), c_[1] - 0.9 * M * math.sin(ang), c_[2]),
                               0.08 * M))
    add(pl.merged(tr, Mesh, ink=0.6, name="car_trim_dark"))
    sk = []
    for sd in (-0.9, 0.9):                                             # skids and struts
        sk.append(pl.rod_parts(tw(-1.6 * M, -0.95 * M, sd * M), tw(1.8 * M, -0.95 * M, sd * M), 0.1 * M))
        for fx_ in (-0.8, 0.8):
            sk.append(pl.rod_parts(tw(fx_ * M, -0.95 * M, sd * M), tw(fx_ * M, -0.3 * M, sd * 0.6 * M), 0.08 * M))
    add(pl.merged(sk, Mesh, ink=0.6, name="car_trim_dark"))
    return out


def car_meshes(cid, pos, head, col, kind="car", t=0.0):
    """a cartoon car (like a sticker): a side profile pushed out to the car's width, light-blue windows with
    pillars, black tyres with silver hubs, yellow headlights, red taillights. kind "police": a black sedan with white
    doors and a roof light flashing red / blue; "suv": a tall boxy SUV with roof rails and a spare wheel on the back;
    "agent": that SUV all black with dark windows; "car": a sedan. World units, turned to its heading.
    (sedan 4.75 m long, 1.45 m high; SUV 4.5 m long, 1.9 m high; both 1.85 m wide)"""
    Wd = 1.85 * M
    parts = []
    ca, sa = math.cos(head), math.sin(head)

    def turn(x, y, z):
        return (pos[0] + x * ca - z * sa, y, pos[2] + x * sa + z * ca)

    def add(v, f, name, ink=0.9, key=""):
        m = Mesh([turn(*q) for q in v], f, ink=ink, name=name)
        m.key = f"{cid}{name}{key}"
        m.car_id = str(cid)
        parts.append(m)

    def colour_name(c):
        nm = "car_%02x%02x%02x" % tuple(int(x * 255) for x in c)
        WASH.setdefault(nm, tuple(c))
        return nm
    side, wins, wx, wr, hl, tl, top = CAR_SHAPE["suv" if kind in ("suv", "agent") else
                                                "pickup" if kind in ("pickup", "truck_small") else "sedan"]
    body = (0.10, 0.10, 0.12) if kind in ("police", "agent") else tuple(col)
    prof = [(x * M, y * M) for x, y in side]
    n = len(prof)
    v = [(x, y, -Wd / 2) for x, y in prof] + [(x, y, Wd / 2) for x, y in prof]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]         # the two sides
    for i in range(n):
        j = (i + 1) % n
        f.append((i, n + i, n + j, j))                                 # the skin round the profile
    add(v, f, colour_name(body), key="b")
    win = "car_win_dark" if kind == "agent" else "car_win"
    for sz in (-1, 1):                                                 # windows on both sides, a hair outside
        z = sz * (Wd / 2 + 2)
        for k_, w_ in enumerate(wins):
            wv = [(x * M, y * M, z) for x, y in w_]
            add(wv, [(0, 1, 2, 3) if sz < 0 else (3, 2, 1, 0)], win, ink=0.8, key=f"w{sz}{k_}")
        if len(wins) == 1:                                             # the sedan's door pillar
            add([(0.02 * M, 1.02 * M, z * 1.001), (0.10 * M, 1.02 * M, z * 1.001), (0.10 * M, 1.40 * M, z * 1.001),
                 (0.02 * M, 1.40 * M, z * 1.001)], [(3, 2, 1, 0) if sz < 0 else (0, 1, 2, 3)], colour_name(body),
                ink=0.6, key=f"p{sz}")
        else:                                                          # the SUV's grey lower trim and door handles
            add([(-1.95 * M, 0.50 * M, z * 1.001), (1.95 * M, 0.50 * M, z * 1.001), (1.95 * M, 0.66 * M, z * 1.001),
                 (-1.95 * M, 0.66 * M, z * 1.001)], [(3, 2, 1, 0) if sz < 0 else (0, 1, 2, 3)], "car_trim",
                ink=0.5, key=f"r{sz}")
            for hx in (-0.55, 0.40):
                add([(hx * M, 1.10 * M, z * 1.002), ((hx + 0.22) * M, 1.10 * M, z * 1.002),
                     ((hx + 0.22) * M, 1.15 * M, z * 1.002), (hx * M, 1.15 * M, z * 1.002)],
                    [(3, 2, 1, 0) if sz < 0 else (0, 1, 2, 3)], "car_trim", ink=0.5, key=f"k{sz}{hx}")
        if kind == "police":                                           # the white door panels
            pv = [(-1.0 * M, 0.42 * M, z * 1.002), (1.0 * M, 0.42 * M, z * 1.002), (0.95 * M, 0.98 * M, z * 1.002),
                  (-1.05 * M, 0.98 * M, z * 1.002)]
            add(pv, [(3, 2, 1, 0) if sz < 0 else (0, 1, 2, 3)], "car_white", ink=0.6, key=f"d{sz}")
    for sx in (-wx, wx):                                               # wheels: tyre + hub, each side
        for sz in (-1, 1):
            tv, tf = places.disk_parts((sx * M, wr * M, sz * (Wd / 2 - 0.08 * M)), (0, 0, 1), wr * M, 0.28 * M, n=12)
            add([tuple(q) for q in tv], tf, "tyre", key=f"t{sx}{sz}")
            hv, hf = places.disk_parts((sx * M, wr * M, sz * (Wd / 2 + 0.07 * M)), (0, 0, 1), 0.53 * wr * M,
                                       0.04 * M, n=10)
            add([tuple(q) for q in hv], hf, "hub", ink=0.6, key=f"h{sx}{sz}")
    if kind in ("pickup", "truck_small"):                               # the pickup's open bed, grille, bumpers,
        add([(-2.55 * M, 1.081 * M, -0.82 * M), (-0.68 * M, 1.081 * M, -0.82 * M), (-0.68 * M, 1.081 * M, 0.82 * M),
             (-2.55 * M, 1.081 * M, 0.82 * M)], [(3, 2, 1, 0)], "car_gap", ink=0.6, key="bed")   # black wheel arches
        add(*_cube((2.64 * M, 0.62 * M, 0), 0.06 * M, 0.30 * M, 1.20 * M), "car_trim_dark", ink=0.7, key="grille")
        for bx_ in (2.66, -2.68):
            add(*_cube((bx_ * M, 0.38 * M, 0), 0.10 * M, 0.16 * M, 1.80 * M), "car_trim_dark", ink=0.6, key=f"bp{bx_}")
        for sz in (-1, 1):
            z = sz * (Wd / 2 + 2.5)
            for ax_ in (-wx, wx):
                arc = [((ax_ + 0.62 * math.cos(a)) * M, (wr + 0.62 * math.sin(a)) * M, z)
                       for a in np.linspace(0.05, math.pi - 0.05, 9)]
                arc += [((ax_ + 0.50 * math.cos(a)) * M, (wr + 0.50 * math.sin(a)) * M, z)
                        for a in np.linspace(math.pi - 0.05, 0.05, 9)]
                add(arc, [tuple(range(18)) if sz > 0 else tuple(range(17, -1, -1))], "car_trim_dark", ink=0.5,
                    key=f"arch{sz}{ax_}")
            add(*_cube((1.25 * M, 1.30 * M, sz * (Wd / 2 + 0.12 * M)), 0.08 * M, 0.14 * M, 0.18 * M), "car_trim_dark",
                ink=0.6, key=f"mir{sz}")                               # the wing mirrors
        add(*_cube((-0.4 * M, 1.82 * M, 0.5 * M), 0.02 * M, 0.45 * M, 0.02 * M), "antenna", ink=0.6, key="ant")
        rb = []                                                        # the roll bar behind the cab
        for sz in (-0.78, 0.78):
            rb.append(places.rod_parts((-0.78 * M, 1.08 * M, sz * M), (-0.78 * M, 1.92 * M, sz * M), 0.07 * M))
        rb.append(places.rod_parts((-0.78 * M, 1.92 * M, -0.78 * M), (-0.78 * M, 1.92 * M, 0.78 * M), 0.07 * M))
        v_, f_ = [], []
        for pv, pf in rb:
            o_ = len(v_)
            v_ += [tuple(q) for q in pv]
            f_ += [tuple(i + o_ for i in ff) for ff in pf]
        add(v_, f_, "car_trim_dark", ink=0.7, key="rollbar")
        add(*_cube((-1.0 * M, 1.08 * M, 0), 0.45 * M, 0.34 * M, 1.5 * M), "car_trim_dark", ink=0.7, key="toolbox")
        add(*_cube((-1.75 * M, 1.08 * M, -0.3 * M), 0.4 * M, 0.26 * M, 0.55 * M), "gauge_cap", ink=0.7, key="case")
    ex = CAR_EXTRA.get(str(cid)) or {}
    if ex.get("mud"):                                                  # mud thrown up by the wheels: thickest low
        mr = random.Random(sum(map(ord, str(cid))))                    # down and behind each wheel
        for sz in (-1, 1):
            z = sz * (Wd / 2 + 3)
            for k in range(34):
                bx = mr.choice((-wx, wx)) + mr.uniform(-0.75, 0.75) if k % 3 else mr.uniform(-2.3, 2.3)
                near = min(abs(bx - wx), abs(bx + wx))
                bot = min(y_ for _, y_ in side) + 0.1                    # (on the body, not hanging below it)
                by = mr.uniform(bot, bot + (0.18 if near > 0.6 else 0.45))
                rr = mr.uniform(0.025, 0.09)
                bl = [((bx + math.cos(a) * rr * mr.uniform(0.8, 1.6)) * M, (by + math.sin(a) * rr * mr.uniform(0.5, 1.0)) * M, z)
                      for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
                add(bl, [tuple(range(5, -1, -1)) if sz < 0 else tuple(range(6))], "mud_splash", ink=0.0, key=f"m{sz}{k}")
    dr = ex.get("door")
    if dr:                                                             # the driver's door (right side: India) swings
        t0, t1 = float(dr[0]), float(dr[1]) if len(dr) > 1 else 1e9    # open on its front hinge, then shuts
        u = max(0.0, min(1.0, (t - t0) / 0.5, (t1 - t) / 0.35))
        if u > 0.01:
            z0 = -(Wd / 2 + 4)
            hx, L = (1.18 * M, 1.2 * M) if kind in ("pickup", "truck_small") else (0.15 * M, 1.15 * M)
            ht = 1.72 if kind in ("pickup", "truck_small") else 1.36
            add([(hx - L, 0.35 * M, z0), (hx, 0.35 * M, z0), (hx, ht * M, z0), (hx - L, ht * M, z0)],
                [(0, 1, 2, 3)], "car_gap", ink=0.6, key="gap")
            a = math.radians(68) * u * u * (3 - 2 * u)
            ex_, ez_ = hx - L * math.cos(a), z0 - L * math.sin(a)
            for y0, y1, nm in ((0.35, ht - 0.52, colour_name(body)), (ht - 0.52, ht, win)):
                add([(ex_, y0 * M, ez_), (hx, y0 * M, z0 - 2), (hx, y1 * M, z0 - 2), (ex_, y1 * M, ez_)],
                    [(0, 1, 2, 3), (3, 2, 1, 0)], nm, ink=0.8, key=f"door{y0}")
    for sz in (-0.6, 0.6):
        add(*_cube((hl[0] * M, hl[1] * M, sz * M), 0.06 * M, 0.14 * M, 0.32 * M), "headlight", ink=0.6, key=f"hl{sz}")
        add(*_cube((tl[0] * M, tl[1] * M, sz * 1.15 * M), 0.06 * M, tl[2] * M, 0.18 * M), "taillight", ink=0.6,
            key=f"tl{sz}")
    if kind in ("suv", "agent"):                                       # roof rails and the spare wheel on the back
        for sz in (-0.7, 0.7):
            add(*_cube((-0.6 * M, (top + 0.06) * M, sz * M), 2.6 * M, 0.06 * M, 0.06 * M), "car_trim", ink=0.6,
                key=f"rr{sz}")
        tv, tf = places.disk_parts((-2.38 * M, 1.05 * M, 0), (1, 0, 0), 0.36 * M, 0.22 * M, n=12)
        add([tuple(q) for q in tv], tf, "tyre", key="sp")
    if kind == "police":                                               # the roof light, flashing red and blue
        lit = "siren_red" if int(t * 4) % 2 == 0 else "siren_blue"
        add(*_cube((-0.3 * M, 1.53 * M, 0), 0.35 * M, 0.16 * M, 0.9 * M), lit, ink=0.8, key="s")
    return parts


HELIS = ("helicopter", "heli", "chopper", "apache", "gunship", "army_helicopter", "jet", "plane", "aircraft")
MACHINES = ("dump_truck", "excavator", "bulldozer", "mixer", "loader")


def _extrude(pts, z0, z1):
    """a side outline (x forward, y up, metres) pushed out from z0 to z1 (metres): verts + faces"""
    if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) > 0:
        pts = pts[::-1]                                                # (clockwise, like the car's outline)
    n = len(pts)
    v = [(x * M, y * M, z0 * M) for x, y in pts] + [(x * M, y * M, z1 * M) for x, y in pts]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        j = (i + 1) % n
        f.append((i, n + i, n + j, j))
    return v, f


def _lathe(a, b, radii, n=12):
    """a round drum along the axis a -> b (metres, in the x-y plane), radius changing along it (metres)"""
    a, b = np.array([a[0], a[1], 0.0]), np.array([b[0], b[1], 0.0])
    ax = (b - a) / np.linalg.norm(b - a)
    up = np.array([-ax[1], ax[0], 0.0])
    zz = np.array([0.0, 0.0, 1.0])
    v = []
    for k, r in enumerate(radii):
        c = a + (b - a) * k / (len(radii) - 1)
        for j in range(n):
            t = 2 * math.pi * j / n
            v.append(tuple((c + (up * math.cos(t) + zz * math.sin(t)) * r) * M))
    f = []
    for k in range(len(radii) - 1):
        for j in range(n):
            j2 = (j + 1) % n
            f.append((k * n + j, k * n + j2, (k + 1) * n + j2, (k + 1) * n + j))
    f.append(tuple(range(n))[::-1])
    f.append(tuple(range((len(radii) - 1) * n, len(radii) * n)))
    return v, f


def machine_meshes(cid, pos, head, kind="dump_truck", t=0.0):
    """a cartoon building-site machine (flat yellow, like a sticker): "dump_truck" (a tipper, 3 axles), "excavator"
    (tracks, a turning body, the boom and bucket), "bulldozer" (tracks, the blade), "mixer" (the cement drum turns
    as it drives), "loader" (big wheels, the front bucket). Grey tyres with yellow hubs, teal windows, dark steel
    for buckets and blades. World units, turned to its heading; real sizes (a dump truck 7.5 m long)"""
    parts = []
    ca, sa = math.cos(head), math.sin(head)

    def turn(x, y, z):
        return (pos[0] + x * ca - z * sa, y, pos[2] + x * sa + z * ca)

    def add(vf, name, ink=0.9, key="", smooth=False):
        v, f = vf
        m = Mesh([turn(*q) for q in v], f, ink=ink, name=name, smooth=smooth)
        m.key = f"{cid}{name}{key}"
        parts.append(m)

    def win(pts, z, k):                                                # a window on both sides, a hair outside
        if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) > 0:
            pts = pts[::-1]                                            # (clockwise, like the car's windows)
        for sz in (-1, 1):
            zz = sz * (z + 0.01) * M
            add(([(x * M, y * M, zz) for x, y in pts], [(0, 1, 2, 3) if sz < 0 else (3, 2, 1, 0)]), "mach_win",
                ink=0.7, key=f"w{k}{sz}")

    def wheel(x, r, z, k, y=None):
        y = r if y is None else y
        for sz in (-1, 1):
            tv, tf = places.disk_parts((x * M, y * M, sz * z * M), (0, 0, 1), r * M, 0.45 * M, n=12)
            add(([tuple(q) for q in tv], tf), "mach_tyre", key=f"t{k}{sz}")
            hv, hf = places.disk_parts((x * M, y * M, sz * (z + 0.24) * M), (0, 0, 1), 0.5 * r * M, 0.04 * M, n=10)
            add(([tuple(q) for q in hv], hf), "mach_yellow", ink=0.6, key=f"h{k}{sz}")
            cv, cf = places.disk_parts((x * M, y * M, sz * (z + 0.27) * M), (0, 0, 1), 0.18 * r * M, 0.03 * M, n=8)
            add(([tuple(q) for q in cv], cf), "mach_dark", ink=0.5, key=f"c{k}{sz}")

    def tracks(x0, x1, z, k):                                          # crawler tracks with their road wheels
        L = x1 - x0
        prof = [(x0, 0.45), (x0 + 0.3, 0.0), (x1 - 0.3, 0.0), (x1, 0.45), (x1 - 0.3, 0.9), (x0 + 0.3, 0.9)]
        for sz in (-1, 1):
            add(_extrude(prof, sz * z - 0.32, sz * z + 0.32), "mach_dark", key=f"tr{k}{sz}")
            for j in range(5):
                xx = x0 + 0.35 + j * (L - 0.7) / 4
                hv, hf = places.disk_parts((xx * M, 0.45 * M, sz * (z + 0.34) * M), (0, 0, 1), 0.26 * M, 0.04 * M, n=10)
                add(([tuple(q) for q in hv], hf), "mach_grey", ink=0.6, key=f"rw{k}{j}{sz}")

    def rod(p0, p1, w, name="mach_yellow", k=""):
        add(places.rod_parts((p0[0] * M, p0[1] * M, 0.0), (p1[0] * M, p1[1] * M, 0.0), w * M), name, key=f"r{k}")

    def cab(x0, x1, y0, y1, z, k, slope=0.1):
        add(_extrude([(x0, y0), (x1, y0), (x1 - slope, y1), (x0 + 0.05, y1)], -z, z), "mach_yellow", key=f"cab{k}")
        add(_extrude([(x0 - 0.1, y1), (x1 - slope + 0.1, y1), (x1 - slope + 0.05, y1 + 0.12), (x0 - 0.05, y1 + 0.12)],
                     -z - 0.05, z + 0.05), "mach_orange", ink=0.7, key=f"roof{k}")
        win([(x0 + 0.15, y0 + 0.55), (x1 - 0.15, y0 + 0.55), (x1 - slope - 0.1, y1 - 0.15), (x0 + 0.18, y1 - 0.15)], z, k)

    if kind in ("dump_truck", "mixer"):
        add(_extrude([(-3.5, 0.72), (3.3, 0.72), (3.3, 1.05), (-3.5, 1.05)], -1.0, 1.0), "mach_grey", key="ch")
        cab(1.7, 3.5, 1.05, 2.95, 1.15, "c", slope=0.15)
        add(_extrude([(3.3, 0.55), (3.6, 0.55), (3.6, 1.05), (3.3, 1.05)], -1.2, 1.2), "mach_dark", key="bump")
        if kind == "dump_truck":
            add(_extrude([(-3.7, 1.1), (1.5, 1.1), (1.6, 3.0), (-3.9, 3.0)], -1.2, 1.2), "mach_yellow", key="bed")
            for j in range(4):                                         # the bed's ribs
                x = -3.2 + j * 1.2
                for sz in (-1, 1):
                    add(([(x * M, 1.4 * M, sz * 1.21 * M), ((x + 0.7) * M, 1.4 * M, sz * 1.21 * M),
                          ((x + 0.7) * M, 2.7 * M, sz * 1.21 * M), (x * M, 2.7 * M, sz * 1.21 * M)],
                         [(0, 1, 2, 3) if sz < 0 else (3, 2, 1, 0)]), "mach_orange", ink=0.4, key=f"rib{j}{sz}")
        else:                                                          # the drum turns: its stripes go round
            add(_lathe((-3.4, 1.55), (1.2, 2.85), [0.35, 1.0, 1.2, 1.15, 0.85, 0.4], n=14), "mach_yellow", ink=0.9,
                key="drum", smooth=True)
            for j in range(3):
                ph = t * 1.6 + j * 2.1
                xx = -2.6 + j * 1.3
                yy = 1.55 + (xx + 3.4) / 4.6 * 1.3
                y_ = yy + 1.17 * math.cos(ph)
                z_ = 1.17 * math.sin(ph)
                if math.sin(ph) > -0.2:
                    add(*[(([(xx * M, (y_ - 0.12) * M, z_ * M * 1.02), ((xx + 0.5) * M, (y_ - 0.02) * M, z_ * M * 1.02),
                              ((xx + 0.5) * M, (y_ + 0.18) * M, z_ * M * 1.02), (xx * M, (y_ + 0.08) * M, z_ * M * 1.02)],
                             [(0, 1, 2, 3), (3, 2, 1, 0)]))], "mach_orange", ink=0.4, key=f"st{j}")
            rod((1.2, 2.85), (1.5, 1.1), 0.18, "mach_grey", "drumleg")
        for k, x in enumerate((-2.6, -1.3, 2.4)):
            wheel(x, 0.58, 0.95, k)
    elif kind == "excavator":
        tracks(-2.3, 2.3, 1.0, "x")
        sw = 0.25 * math.sin(t * 0.8)                                  # the body swings a little as it works
        add(_extrude([(-2.5, 0.95), (1.0, 0.95), (1.0, 2.05), (-2.3, 2.05), (-2.6, 1.6)], -1.15, 1.15), "mach_yellow",
            key="body")
        add(_extrude([(-2.7, 1.0), (-2.4, 1.0), (-2.4, 1.9), (-2.75, 1.8)], -1.1, 1.1), "mach_dark", key="cw")
        add(_extrude([(0.0, 2.05), (1.2, 2.05), (1.1, 3.2), (0.15, 3.2)], 0.15, 1.1), "mach_yellow", key="cab")
        for zz, fo in ((1.11, (0, 1, 2, 3)), (0.14, (3, 2, 1, 0))):   # the cab's windows, both sides
            add(([(0.2 * M, 2.4 * M, zz * M), (1.0 * M, 2.4 * M, zz * M), (0.95 * M, 3.05 * M, zz * M),
                  (0.25 * M, 3.05 * M, zz * M)], [fo]), "mach_win", ink=0.7, key=f"w{zz}")
        tip = (3.4 + sw, 3.9)
        hand = (4.6 + sw, 1.1 + 0.4 * math.sin(t * 1.3))
        rod((0.9, 2.0), tip, 0.38, k="boom")
        rod(tip, hand, 0.3, k="stick")
        hx, hy = hand
        add(_extrude([(hx - 0.1, hy + 0.3), (hx + 0.7, hy + 0.1), (hx + 0.5, hy - 0.6), (hx - 0.3, hy - 0.5)], -0.55,
                     0.55), "mach_dark", key="bucket")
    elif kind == "bulldozer":
        tracks(-1.9, 1.9, 1.05, "b")
        add(_extrude([(-2.0, 0.9), (1.4, 0.9), (1.5, 1.75), (-1.9, 1.85)], -1.1, 1.1), "mach_yellow", key="body")
        cab(-1.5, 0.4, 1.85, 3.1, 0.9, "c", slope=0.15)
        add(_extrude([(2.2, 0.0), (2.55, 0.0), (2.65, 1.4), (2.3, 1.5), (2.15, 0.8)], -1.6, 1.6), "mach_dark",
            key="blade")
        rod((1.2, 1.2), (2.25, 0.6), 0.2, "mach_grey", "push")
        add(_extrude([(-2.2, 0.4), (-1.9, 0.5), (-2.1, 0.0), (-2.4, 0.0)], -0.2, 0.2), "mach_dark", key="ripper")
    else:                                                              # loader
        add(_extrude([(-2.2, 0.9), (1.4, 0.9), (1.5, 1.8), (-2.0, 1.9), (-2.4, 1.5)], -1.05, 1.05), "mach_yellow",
            key="body")
        cab(-1.2, 0.5, 1.85, 3.25, 0.85, "c", slope=0.15)
        up = 0.4 + 0.3 * math.sin(t * 0.9)
        rod((0.2, 1.7), (2.6, 0.9 + up), 0.32, k="arm")
        bx, by = 2.6, 0.9 + up
        add(_extrude([(bx - 0.2, by + 0.6), (bx + 0.8, by + 0.4), (bx + 0.9, by - 0.6), (bx - 0.1, by - 0.5)], -1.3,
                     1.3), "mach_dark", key="bucket")
        for k, x in enumerate((-1.5, 1.0)):
            wheel(x, 0.82, 0.95, k)
    beacon = "siren_red" if int(t * 3) % 2 == 0 else "mach_orange"     # the roof's flashing beacon
    top = {"dump_truck": (2.6, 3.07), "mixer": (2.6, 3.07), "excavator": (0.6, 3.2), "bulldozer": (-0.6, 3.22),
           "loader": (-0.4, 3.37)}[kind]
    add(_cube((top[0] * M, top[1] * M + 0.1 * M, 0.0), 0.2 * M, 0.2 * M, 0.2 * M), beacon, ink=0.6, key="bc")
    return parts


def _cube(c, w, h, d):
    x, y, z = c
    x0, x1, y0, y1, z0, z1 = x - w / 2, x + w / 2, y - h / 2, y + h / 2, z - d / 2, z + d / 2
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]
    f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


DRAMA = ("surprised", "scared", "angry", "crying", "sad", "shocked")


def _dramatic(sp):
    """a line that deserves a close-up: a strong feeling, a "!" or a trailing "...", or "close": true on the line"""
    tx = str(getattr(sp, "text", "") or "").strip()
    return bool(getattr(sp, "close", False) or str(getattr(sp, "emotion", "") or "").lower() in DRAMA
                or tx.endswith("!") or tx.endswith("...") or tx.endswith("…"))


def _boxes(m):
    """each face of a mesh in its own box (a mesh may hold all the posts of a porch: one box round it would hide the
    gaps between them): (lo (F,3), hi (F,3)), kept on the mesh"""
    bb = getattr(m, "_fb", None)
    if bb is None:
        lo = np.array([m.v[f].min(axis=0) for f in m.f])
        hi = np.array([m.v[f].max(axis=0) for f in m.f])
        bb = m._fb = (lo, hi, m.v.min(axis=0), m.v.max(axis=0))
    return bb


def _blocked(world, eye, target):
    """does a thing of the place stand between the lens and a face? (a pillar, a wall, a car). Each face of each
    mesh is tested in its own box; a box that holds the lens or the face (a room, the ground) does not count"""
    a = np.asarray(eye, float)
    b = np.asarray(target, float)
    d = b - a
    L = float(np.linalg.norm(d))
    if L < 1e-6:
        return False
    a2 = a + d * (0.06 * M / L)
    d2 = d * (1.0 - 0.45 * M / L - 0.06 * M / L)                       # stop short of the face (its own body)
    seg_lo, seg_hi = np.minimum(a2, a2 + d2), np.maximum(a2, a2 + d2)
    pad = 2.0
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = np.where(np.abs(d2) > 1e-9, 1.0 / d2, np.inf)
    for m in world:
        if getattr(m, "under", False) or m.name in ("dust",):
            continue
        lo, hi, mlo, mhi = _boxes(m)
        if m.radius < 4.0 * M and np.all(a >= mlo) and np.all(a <= mhi):
            return True                                                # (the lens inside a car or a box: no)
        if np.any(mhi < seg_lo) or np.any(mlo > seg_hi):
            continue
        keep = ~(np.all((a >= lo - pad) & (a <= hi + pad), axis=1) | np.all((b >= lo - pad) & (b <= hi + pad), axis=1))
        if not keep.any():
            continue
        lo_, hi_ = lo[keep], hi[keep]
        with np.errstate(invalid="ignore"):
            u0 = (lo_ - a2) * inv
            u1 = (hi_ - a2) * inv
        flat = ~np.isfinite(inv)                                       # a ray parallel to an axis: inside the slab?
        if flat.any():
            ins = (a2 >= lo_) & (a2 <= hi_)
            u0 = np.where(flat, np.where(ins, -np.inf, np.inf), u0)
            u1 = np.where(flat, np.where(ins, np.inf, -np.inf), u1)
        t0 = np.maximum(np.minimum(u0, u1).max(axis=1), 0.0)
        t1 = np.minimum(np.maximum(u0, u1).min(axis=1), 1.0)
        if np.any(t0 <= t1):
            return True
    return False


def _talk_cam(sc, people, lt, world, spec, base_cam, W, H):
    """the conversation camera (as films cut a talk): after a wide look at the place, each line is seen over the
    listener's shoulder, as a medium shot or a two-shot, a strong line in a slow push to a close-up, and a long line
    cuts away to the listener's face. All shots stay on one side of the two people (the 180-degree rule) and swing
    round a pillar or a wall that would hide the face. A scene can say "stick_talk": false to keep its own camera."""
    if spec.get("stick_talk") is False or not people:
        return None
    sps = [q for q in (getattr(sc, "speeches", None) or []) if q.who != "narrator"]
    if not sps or lt < 2.2:
        return None                                                    # the first seconds: the wide look
    cur = None
    for k, q in enumerate(sps):
        if q.start - 0.15 <= lt < q.end + 0.35:
            cur = (k, q)
    if cur is None:
        return None
    k, sp = cur
    byid = {q["id"]: q for q in people if q.get("look")}
    S = byid.get(sp.who)
    L = byid.get(getattr(sp, "to", None) or "")
    if S is None:                                                      # an unseen voice (a phone): stay on the
        S, L = L, None                                                 # one who listens
        if S is None:
            return None
    if L is None or L is S:
        others = [q for q in byid.values() if q is not S]
        L = min(others, key=lambda q: np.linalg.norm(np.array(q["pos"]) - S["pos"])) if others else None
    sp_pos = np.array(S["pos"], float)
    sc_ = float(S.get("scale", 1.0) or 1.0)
    if L is not None and np.linalg.norm(np.array(L["pos"]) - sp_pos) > 1e-3:
        u = np.array(L["pos"], float) - sp_pos
    else:
        u = np.array([math.cos(S["dir"]), 0.0, math.sin(S["dir"])]) * 100.0
    u[1] = 0.0
    dist = float(np.linalg.norm(u))
    u /= max(1e-6, dist)
    n = np.array([-u[2], 0.0, u[0]])
    if float(np.dot(n, base_cam.pos - sp_pos)) < 0:                    # the side the wide shot was on (180 rule)
        n = -n
    piece = int(max(0.0, lt - sp.start) / MAX_SHOT[0])
    uu = max(0.0, min(1.0, (lt - sp.start - piece * MAX_SHOT[0]) / max(0.5, min(MAX_SHOT[0], sp.dur))))
    head = lambda q, h: np.array(q["pos"], float) + np.array([0.0, h * M * float(q.get("scale", 1.0) or 1.0), 0.0])

    def around(c, v, deg):
        a_ = math.radians(deg)
        return np.array([v[0] * math.cos(a_) - v[2] * math.sin(a_), v[1], v[0] * math.sin(a_) + v[2] * math.cos(a_)])
    if _dramatic(sp) and piece == 0:
        kind = "close"
    elif piece % 2 == 1 and L is not None:
        kind = "react"
    else:
        kind = ("ots", "medium", "two")[k % 3] if L is not None else ("medium", "close")[k % 2]
    if kind == "two" and dist > 6 * M:
        kind = "medium"

    def shot(kind):
        fov = 40.0
        if kind == "close":
            tgt = head(S, 1.45)
            v = (u * 0.45 + n * 0.9)
            v = v / np.linalg.norm(v) * (2.7 - 0.6 * uu) * M              # a slow push in on the face
            eye, fov = tgt + v + np.array([0.0, 0.05 * M, 0.0]), 36.0
        elif kind == "ots":      # over the listener's shoulder: the speaker
            tgt = head(S, 1.35)
            eye = np.array(L["pos"], float) + u * 1.5 * M + n * 0.9 * M + np.array([0.0, 1.65 * M, 0.0])
            eye = eye + (tgt - eye) * 0.04 * uu
        elif kind == "react":      # the listener's face as the line goes on
            tgt = head(L, 1.35)
            v = (-u * 0.5 + n * 0.85)
            v = v / np.linalg.norm(v) * 3.4 * M
            eye = tgt + v + np.array([0.0, 0.05 * M, 0.0])
            fov = 38.0
        elif kind == "two":                                                # both, side on
            mid = (sp_pos + np.array(L["pos"], float)) / 2
            tgt = mid + np.array([0.0, 1.25 * M * sc_, 0.0])
            eye = tgt + n * (dist * 0.9 + 3.6 * M) + np.array([0.0, 0.2 * M, 0.0])
            fov = 44.0
        else:                                                              # medium: the speaker, chest up
            tgt = head(S, 1.20)
            v = (u * 0.35 + n * 0.94)
            v = v / np.linalg.norm(v) * (4.3 - 0.3 * uu) * M
            eye = tgt + v + np.array([0.0, 0.15 * M, 0.0])
        ceil = getattr(world, "ceiling", None)
        face = head(S if kind != "react" else L, 1.5)
        faces = [face] + ([head(L, 1.5)] if kind == "two" else [])           # a two-shot keeps both faces clear
        best = None
        for deg in (0, 18, -18, 36, -36, 55, -55, 75, -75):               # swing round whatever hides the face
            e_ = tgt + around(tgt, eye - tgt, deg)
            if ceil:
                e_[1] = min(e_[1], ceil - 0.25 * M)
            sd_ = np.cross(face - e_, (0.0, 1.0, 0.0))
            sd_ = sd_ / max(1e-6, float(np.linalg.norm(sd_))) * 0.55 * M     # the face and a little either side of it
            if not any(_blocked(world, e_, fc_ + o_) for fc_ in faces for o_ in (0 * sd_, sd_, -sd_)):
                best = e_
                break
        return None if best is None else Cam(tuple(best), tuple(tgt), fov=fov, W=W, H=H)
    for kd in dict.fromkeys((kind, "medium", "close")):               # blocked from every side: a single, then
        c_ = shot(kd)                                                  # a close-up of the face
        if c_ is not None:
            if kd in ("medium", "close", "react", "ots"):              # framed on the thirds
                who, oth = (L, S) if kd == "react" else (S, L)
                ahead = np.array(who["pos"], float) + np.array([math.cos(who["dir"]), 0.0, math.sin(who["dir"])]) * M
                c_ = _thirds(c_, head(who, 1.55), head(oth, 1.5) if oth is not None else ahead, W, H)
            return c_
    return None


def _dust(ctx, cam, puffs):
    """soft see-through dust puffs (no ink: dust has no outline), farthest first"""
    col = WASH["dust"]
    for q, r, a in sorted(puffs, key=lambda z: -float(np.dot(z[0] - cam.pos, cam.fwd))):
        dz = float(np.dot(q - cam.pos, cam.fwd))
        if dz < 0.5 * M or a <= 0.01:
            continue
        x, y = cam.project(q[None])[0]
        rp = cam.focal * r / dz
        g = cairo.RadialGradient(x, y, 0, x, y, rp)
        g.add_color_stop_rgba(0, *col, a)
        g.add_color_stop_rgba(0.6, *col, a * 0.6)
        g.add_color_stop_rgba(1, *col, 0.0)
        ctx.set_source(g)
        ctx.arc(x, y, rp, 0, 2 * math.pi)
        ctx.fill()


GRADES = {   # the colour script: each story beat has its own colour (as a film's colour script plans it)
    #            tint (r, g, b, strength), saturation (below 1 drains colour), vignette (dark edges)
    "calm": ((1.00, 0.96, 0.90, 0.00), 1.00, 0.10),
    "warm": ((1.00, 0.78, 0.50, 0.12), 1.08, 0.12),     # home, friends: warm light, rich colour
    "hope": ((1.00, 0.86, 0.60, 0.10), 1.10, 0.08),
    "wonder": ((0.70, 0.86, 1.00, 0.10), 1.12, 0.10),   # a reveal: clear, cool, bright
    "secret": ((0.30, 0.42, 0.55, 0.14), 0.80, 0.38),   # hidden rooms, files: cold, muted, closed in
    "tense": ((0.35, 0.45, 0.55, 0.16), 0.75, 0.35),    # the threat comes closer: colour drains out
    "danger": ((0.85, 0.18, 0.10, 0.14), 0.90, 0.45),   # the agents, the storms: red pressure at the edges
    "sad": ((0.40, 0.50, 0.72, 0.18), 0.60, 0.30),      # loss, worry: blue and grey
    "doom": ((0.75, 0.30, 0.15, 0.18), 0.70, 0.55),     # the world after: rust and ash
    "monsoon": ((0.55, 0.62, 0.66, 0.16), 0.82, 0.32),  # rain on the fields: cool, wet, the greens deep
    "hurricane": ((0.28, 0.46, 0.52, 0.16), 0.80, 0.50),
    "hall": ((1.00, 0.72, 0.42, 0.10), 0.95, 0.42),     # the Delhi hall: warm wood and lamps, edges dark (tense)  # the Gulf storm: cold steel-teal, colour drained, closed in
}
EMO_MOOD = {"scared": "tense", "worried": "tense", "angry": "danger", "sad": "sad", "crying": "sad", "happy": "warm"}


def scene_mood(sc, spec):
    """the scene's beat for the colour script: "mood" in the scene, else read from the feelings of its lines"""
    m = str(spec.get("mood") or "").lower()
    if m in GRADES:
        return m
    votes = {}
    for q in getattr(sc, "speeches", None) or []:
        k = EMO_MOOD.get(str(getattr(q, "emotion", "") or "").lower())
        if k:
            votes[k] = votes.get(k, 0) + 1
    return max(votes, key=votes.get) if votes else None


_VIG = {}


def _grade(ctx, W, H, mood, amount=1.0):
    """the colour grade of a beat over the finished frame - cheap washes (each ~0.5 ms a frame; blend modes like
    'saturation' or 'soft light' cost 15-30 ms on a full frame): a grey-tinted wash mutes the colour, a thin wash
    of the tint colours it, a vignette (drawn once per frame size) darkens the edges"""
    g = GRADES.get(mood)
    if not g or amount <= 0:
        return
    (r, gg, b, k), sat, vig = g
    ctx.save()
    ctx.identity_matrix()
    ctx.set_operator(cairo.OPERATOR_OVER)
    if sat < 1.0:                                                      # mute: towards a dim grey of the beat's tint
        ctx.set_source_rgba(0.42 + 0.16 * r, 0.42 + 0.16 * gg, 0.42 + 0.16 * b, (1.0 - sat) * 0.7 * amount)
        ctx.paint()
    if k > 0:                                                          # colour: a thin wash of the tint
        ctx.set_source_rgba(r, gg, b, k * 0.55 * amount)
        ctx.paint()
    if vig > 0:                                                        # dark edges pull the eye to the middle
        key = (int(W), int(H), round(vig * amount, 3))
        vs = _VIG.get(key)
        if vs is None:
            vs = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W), int(H))
            vc = cairo.Context(vs)
            rg = cairo.RadialGradient(W / 2, H / 2, 0.35 * max(W, H), W / 2, H / 2, 0.75 * max(W, H))
            rg.add_color_stop_rgba(0, 0, 0, 0, 0)
            rg.add_color_stop_rgba(1, 0.02, 0.02, 0.04, vig * amount)
            vc.set_source(rg)
            vc.paint()
            if len(_VIG) > 24:
                _VIG.clear()
            _VIG[key] = vs
        ctx.set_source_surface(vs, 0, 0)
        ctx.paint()
    ctx.restore()


def _thirds(cam, face, other, W, H):
    """composition: the face on a third of the frame (not dead centre), with the free space on the side the
    person looks toward (looking room), and the eyes on the upper third line (headroom)"""
    F = np.asarray(face, float)
    d = F - cam.pos
    z = float(np.dot(d, cam.fwd))
    if z < 0.5 * M:
        return cam
    sx = W / 6.0
    if other is not None:
        ox = float(np.dot(np.asarray(other, float) - cam.pos, cam.right))
        fx = float(np.dot(d, cam.right))
        side = -1.0 if ox > fx else 1.0                                # look toward the right -> sit on the left third
    else:
        side = 1.0
    sy = H / 7.0
    look = F - cam.right * (z * side * sx / cam.focal) - cam.up * (z * sy / cam.focal)
    fov = 2 * math.degrees(math.atan((H / 2) / cam.focal))
    return Cam(tuple(cam.pos), tuple(look), fov=fov, W=W, H=H)


def _look_at_partners(people, sc, lt):
    """people look at each other, not at the camera (as actors do): while a line is spoken, the speaker turns to
    the one spoken to and everyone near who is standing still turns to the speaker; the camera finds their faces
    (the talk camera). Walkers and people the story turned ("facing") are left alone."""
    byid = {q["id"]: q for q in people if q.get("look")}
    cur = None
    for q in getattr(sc, "speeches", None) or []:
        if q.start - 0.2 <= lt < q.end + 0.6:
            cur = q
    if cur is None or cur.who not in byid:
        return
    S = byid[cur.who]
    L = byid.get(getattr(cur, "to", None) or "")

    def face(p, target):
        if p.get("moving") or p.get("keep_back") or p.get("to_camera") or target is None or target is p:
            return
        d = np.array(target["pos"], float) - np.array(p["pos"], float)
        if math.hypot(d[0], d[2]) > 1e-3:
            p["dir"] = math.atan2(d[2], d[0])
    if L is None:
        others = [q for q in byid.values() if q is not S]
        L = min(others, key=lambda q: np.linalg.norm(np.array(q["pos"]) - S["pos"])) if others else None
    face(S, L)
    for q in byid.values():
        if q is not S and np.linalg.norm(np.array(q["pos"]) - S["pos"]) < 12 * M:
            face(q, S)


def _turn_to_camera(p, cam):
    """a cartoon rule (not life): the audience must see faces. A person who is not walking and would show us the back
    of the head turns three-quarters toward the camera (keeping the side they faced); one who is talking is turned
    at least that far. Walkers, animals and "keep_back" people are left as they are."""
    if not p.get("look") or p.get("moving") or p.get("keep_back") or p.get("kind"):
        return
    base = np.array(p["pos"], float)
    to = cam.pos - base
    to[1] = 0
    n = float(np.linalg.norm(to))
    if n < 1e-6:
        return
    to /= n
    a = p["dir"]
    fwd = np.array([math.cos(a), 0.0, math.sin(a)])
    cosf = float(np.dot(fwd, to))
    if cosf > (0.35 if p.get("talking") else -0.2):
        return
    ac = math.atan2(to[2], to[0])                                      # the way to the camera
    side = 1.0 if (math.sin(a - ac)) >= 0 else -1.0                    # stay on the side they faced
    p["dir"] = ac + side * math.radians(50)


def _prop(ctx, pen, pr, at, k, f, held, t):
    """one story prop: the flat drawing (stick3d_props), else the 2.5D ink drawing stood up at that spot"""
    from . import stick3d_props
    if stick3d_props.draw(ctx, pr, stick3d_props.kind_of(pr), at[0], at[1], k, f, held, t):
        return
    ctx.save()
    ctx.translate(*at)
    ctx.scale(k, -k)
    u0 = pen.unit
    pen.unit = 1.0 / max(k, 1e-3)
    pen.thing(("prop", getattr(pr, "id", "")))
    sketch.draw_prop(pen, pr, 0.0, 0.0, f, t, held=held)
    pen.unit = u0
    ctx.restore()


def draw(ctx, W, H, cam, world, people, t, frame, bubble=None, near_cut=0.0, ground=None):
    """draw one frame onto ctx; returns where each person's head is (for bubbles). near_cut: scenery nearer to the
    camera than this is left out (a close-up never has a wall or a well between the lens and the face)"""
    S = H / 1080.0
    mood = TIMES.get(MOOD[0])
    sky_ = mood["sky"] if mood else getattr(world, "sky", FLAT_SKY)
    SKY_NOW[0] = sky_
    if STYLE[0] == "flat":                                        # flat: one sky colour, one ground colour
        hz = cam.project(cam.pos[None] + np.array([[cam.fwd[0] * 1e6, 0.0 - cam.pos[1], cam.fwd[2] * 1e6]]))[0][1]
        top = mood["top"] if mood else getattr(world, "sky_top", None)
        if top:
            g = cairo.LinearGradient(0, 0, 0, max(1.0, hz))
            g.add_color_stop_rgb(0, *top)
            g.add_color_stop_rgb(1, *sky_)
            ctx.set_source(g)
        else:
            ctx.set_source_rgb(*sky_)
        ctx.paint()
        if mood:
            _time_sky(ctx, cam, MOOD[0], frame, S, hz)
        else:
            _sky_fx(ctx, cam, world, frame, S, hz)
        for f_ in SKY_HOOK:                                            # things in the sky behind the world
            f_(ctx, cam, hz)                                           # (the storm front)
        ctx.rectangle(0, hz, W, H - hz)
        ctx.set_source_rgb(*getattr(world, "ground", FLAT_GROUND))
        ctx.fill()
    else:
        ctx.set_source_surface(sketch._paper(W, H)[0], 0, 0)
        ctx.paint()
    pen = Pen(ctx, frame // (2 * sketch.BOIL), unit=1.0)          # (the lines shiver gently: every 8 frames)
    if STYLE[0] == "wash":
        _sky_ground(ctx, cam)
    pen.thing("ground")
    if STYLE[0] != "flat":
        _ground(ctx, pen, cam, S, pen.seed)
    items = []
    order = _house_order(world, cam)                                   # (a house you can go into: see _house_order)
    for i, m in enumerate(world):
        d = float(np.dot(m.center - cam.pos, cam.fwd))
        if d + m.radius < 10 or (d < near_cut and not m.under and not getattr(m, "shell", False)
                                 and m.name != "redfloor"):           # (floors and walls never block a shot)
            continue
        items.append((order(m, d), 0, i, m, d))
    for p in people:                                                   # (old rule, by request only: "stick_faces":
        if p.get("reporter"):                                          # a reporter faces the lens, a little
            to = cam.pos - np.array(p["pos"], float)                   # turned (as TV reporters stand)
            p["dir"] = math.atan2(to[2], to[0]) + 0.35
        elif p.get("to_camera"):                                       # "camera" turns idle people toward the lens)
            _turn_to_camera(p, cam)
    people = list(people) + [dict(a, kind="animal", id=a.get("id") or f"_animal{k}")   # the place's own animals
                             for k, a in enumerate(getattr(world, "animals", None) or ())]
    me = sys.modules[__name__]
    for j, p in enumerate(people):
        d = float(np.dot(np.array(p["pos"]) - cam.pos, cam.fwd))
        if p.get("kind") == "animal" and d > 10:                       # 🐄 an animal: its 3D parts join the world
            parts, p["_head"] = stick3d_animals.meshes(me, p, t)
            for m in parts:
                dm = float(np.dot(m.center - cam.pos, cam.fwd))
                if dm + m.radius > 10:
                    items.append((order(m, dm), 0, -1, m, dm))
        if d > 10:
            items.append((order(p, d), 1, j, p, d))
    for j, g in enumerate(ground or ()):                              # props standing on the ground / a table
        c = cam.view(np.array([g["pos"]], float))[0]
        if c[2] > 10:
            items.append((order(g, float(c[2])), 2, j, g, float(c[2])))
    heads = {}
    for _key, kind, i, it, d in sorted(items, key=lambda e: -e[0]):
        pen.thing((kind, i))
        if STYLE[0] != "lines":                                       # its shadow first, then the thing on it
            if kind == 0 and it.v[:, 1].min() < 2 and it.name not in NO_SHADOW and not it.under:
                lo, hi = it.v.min(axis=0), it.v.max(axis=0)
                _shadow(ctx, cam, (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2, (hi[0] - lo[0]) * 0.62,
                        (hi[2] - lo[2]) * 0.62, S)
            elif kind == 0 and it.name == "crown":
                _shadow(ctx, cam, it.center[0], it.center[2], it.radius * 0.9, it.radius * 0.8, S)
            elif kind == 2:
                pass
            elif kind == 1 and it.get("kind") == "animal":
                rx_, rz_ = stick3d_animals.shadow_size(it.get("species"))
                _shadow(ctx, cam, it["pos"][0], it["pos"][2], rx_, rz_, S)
            elif kind == 1:
                big = it.get("kind") == "dino"
                _shadow(ctx, cam, it["pos"][0], it["pos"][2], 2.4 * M if big else 45, 0.9 * M if big else 30, S)
        if kind == 2:
            c = cam.view(np.array([it["pos"]], float))[0]
            _prop(ctx, pen, it["pr"], tuple(cam.screen(c[None])[0]), cam.focal / c[2], it["f"], False, t)
            continue
        if kind == 0:
            fade = min(0.5, max(0.0, (d - 3500.0) / 8000.0))   # far things paler (air)
            _ink_mesh(ctx, pen, cam, it, S, fade)
        elif it.get("kind") == "dino":
            heads[it["id"]] = _dino(ctx, cam, it, t, S)
        elif it.get("kind") == "animal":                               # (its parts are drawn as meshes)
            hc = cam.view(np.array([it["_head"]], float))[0]
            heads[it["id"]] = tuple(cam.screen(hc[None])[0]) if hc[2] > 10 else (-1e4, -1e4)
        elif it.get("kind") == "ink":                                 # anything else from the 2.5D sketch engine
            heads[it["id"]] = _billboard(ctx, pen, cam, it, t)
        else:
            if it.get("speed"):
                _speed_lines(ctx, cam, it, t, frame, S, 1.6)
            heads[it["id"]] = _person(ctx, pen, cam, it, t, S)
            for pr in it.get("held") or ():                           # what they hold, in the near hand
                _prop(ctx, pen, pr, it["_hand"], it["_k"], it["_f"], True, t)
    if mood and mood.get("veil"):                                     # the light of the hour over everything (the
        inside = getattr(world, "ceiling", None) or (                  # bubbles stay readable on top); a lit room
            getattr(world, "house", None) and _in_house(world, cam.pos))   # at night is darkened less
        ctx.identity_matrix()
        ctx.rectangle(0, 0, W, H)
        ctx.set_source_rgba(*mood["veil"][:3], mood["veil"][3] * (0.75 if inside else 1.0))
        ctx.fill()
    if bubble and bubble[0] in heads:
        hx, hy = heads[bubble[0]]
        sketch._bubble(pen, bubble[1], hx, hy, W, H, S)
    elif bubble and bubble[0] == "narrator":
        sketch._bubble(pen, bubble[1], W / 2, 0, W, H, S, narration=True)
    return heads


def _billboard(ctx, pen, cam, it, t):
    """a 2.5D sketch drawing (an animal, a talking thing) stood up in the 3D world as a flat cut-out"""
    st = it["state"]
    base = np.array(it["pos"], float)
    c = cam.view(base[None])[0]
    if c[2] < 10:
        return (0, 0)
    sx, sy = cam.screen(c[None])[0]
    k = cam.focal / c[2]
    ctx.save()
    ctx.translate(sx, sy)
    ctx.scale(k, -k)
    ctx.translate(-st.x, -st.y)
    u0 = pen.unit
    pen.unit = 1.0 / k
    pen.thing(it["id"])
    info = sketch.draw_stickman(pen, it["cdef"], st, t)
    pen.unit = u0
    hx, hy = ctx.user_to_device(*info["head"])
    r = info.get("r", 40) * k
    ctx.restore()
    return hx, hy - r


# ---------------------------------------------------------------------------- stories: "art": "stick3d"
DINOS = ("dinosaur", "dino", "t-rex", "trex", "t_rex", "tyrannosaurus", "rex", "raptor")
_WORLDS = {}


PLACES = {"village": lambda: village(), "village_2030": lambda: places.village_2030(sys.modules[__name__]),
          "home_2026": lambda: places.home_2026(sys.modules[__name__]),
          "field_2026": lambda: places.field_2026(sys.modules[__name__]),
          "basement_2026": lambda: places.basement_2026(sys.modules[__name__]),
          "land_2027": lambda: places.land_2027(sys.modules[__name__]),
          "farm_2026": lambda: places.farm_2026(sys.modules[__name__]),
          "farmhouse_office": lambda: places.farmhouse_office(sys.modules[__name__]),
          "meeting_room": lambda: places.meeting_room(sys.modules[__name__]),
          "city_street": lambda: places.city_street(sys.modules[__name__]),
          "highway": lambda: places.highway(sys.modules[__name__]),
          "site_2027": lambda: places.site_2027(sys.modules[__name__]),
          "ruined_city": lambda: places.ruined_city(sys.modules[__name__]),
          "tunnel_2030": lambda: places.tunnel_2030(sys.modules[__name__]),
          "texas_lab": lambda: places.abroad_office(sys.modules[__name__], "texas"),
          "panama_office": lambda: places.abroad_office(sys.modules[__name__], "panama"),
          "corn_field": lambda: places.corn_field(sys.modules[__name__]),
          "village_road": lambda: places.village_road(sys.modules[__name__]),
          "storm_coast": lambda: places.storm_coast(sys.modules[__name__]),
          "airstrip": lambda: places.airstrip(sys.modules[__name__]),
          "jet_cabin": lambda: places.jet_cabin(sys.modules[__name__]),
          "auditorium": lambda: places.auditorium(sys.modules[__name__]),
          "weather_center": lambda: places.weather_center(sys.modules[__name__])}
PLACE_WORDS = (("2030", "village_2030"), ("apocalyp", "village_2030"), ("ozone", "village_2030"),
               ("workshop", "home_2026"), ("field", "field_2026"), ("farm", "field_2026"),
               ("basement", "basement_2026"), ("office", "farmhouse_office"), ("meeting", "meeting_room"), ("ruin", "ruined_city"),
               ("street", "city_street"), ("ministry", "city_street"), ("delhi", "meeting_room"),
               ("highway", "highway"), ("road", "highway"), ("site", "site_2027"), ("pit", "site_2027"),
               ("village_road", "village_road"), ("mud_road", "village_road"), ("kacha", "village_road"), ("corn", "corn_field"), ("maize", "corn_field"), ("makka", "corn_field"), ("galveston", "storm_coast"), ("airstrip", "airstrip"), ("auditorium", "auditorium"), ("weather_center", "weather_center"), ("noaa", "weather_center"), ("control_room", "weather_center"), ("conference", "auditorium"), ("hall", "auditorium"), ("airport", "airstrip"), ("cabin", "jet_cabin"), ("coast", "storm_coast"), ("texas", "texas_lab"), ("usa", "texas_lab"), ("panama", "panama_office"), ("tunnel", "tunnel_2030"), ("mine", "tunnel_2030"), ("bunker", "site_2027"), ("land", "land_2027"))


def place_name(name):
    """a place word from a story -> one of PLACES (unknown places are drawn as the village)"""
    n = str(name or "").lower()
    if n in PLACES:
        return n
    for w, key in PLACE_WORDS:
        if w in n:
            return key
    return "village"


def world(name):
    key = place_name(name)
    if key not in _WORLDS:
        _WORLDS[key] = PLACES[key]()
    return _WORLDS[key]


def _world_for(P, sc, bg):
    """the 3D place for a scene: the scene's "stick_place", else the story's settings "stick_place", else its
    background preset name (words like 2030 / apocalypse pick the 2030 village)"""
    raw = getattr(sc, "data", None) or getattr(sc, "spec", None) or {}
    name = (raw.get("stick_place") if isinstance(raw, dict) else None) or P.settings.get("stick_place") \
        or getattr(bg, "preset_alias", None) or getattr(bg, "preset", "")
    return world(name)


def _rgb(c):
    """a colour from the story: "#rrggbb" or [r, g, b] (0..1) -> (r, g, b); None stays None"""
    if isinstance(c, str) and c.startswith("#") and len(c) == 7:
        return tuple(int(c[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return tuple(c) if c else None


def _look_of(c, wld=None):
    """a doodle-kid look from the story's character (its shirt, trousers or dress, skin and hair); in a place with
    gear (2030) everyone wears a mask, goggles and a hood unless the character says "mask": false etc."""
    long_ = c.hair in ("long", "ponytail", "braid", "bun", "bob")
    sp = c.spec or {}
    gear = bool(getattr(wld, "gear", False))
    extra = {k: sp.get(k, gear) for k in ("mask", "goggles", "hood")}
    extra["cap"] = bool(sp.get("cap"))
    head_k = {"child": DOODLE_HEAD, "toddler": DOODLE_HEAD * 1.05, "baby": DOODLE_HEAD * 1.1,
              "teen": 1.12}.get(c.age, 0.98)                           # grown-ups get a grown-up head
    return {**extra, "head_k": head_k, "beard": bool(c.beard), "mustache": bool(c.mustache), "shades": bool(sp.get("shades")),
            "cloth": _rgb(sp.get("cloth")), "shirt": c.top, "pants": c.bottom, "dress": c.bottom_kind in ("skirt", "long_skirt"), "skin": c.skin,
            "hair_col": c.hair_color, "hair": ("bunches" if c.age in ("child", "toddler", "baby") else "bob")
            if (c.gender == "female" or long_) else "short"}


ANCHOR = [(0.0, 0.0)]      # where the stage sits in the place this scene: a world offset (x, z)


def stage_to_world(x, y, z):
    """the 2D stage (x 0..1920 across, z 0 front .. 1000 back) -> the 3D place: by default the village square; a
    scene's "stick_spot" (a named spot of the place: "gate", "porch", "desk" ...) puts the stage's middle there"""
    ox, oz = ANCHOR[0]
    return (x - 960.0 + ox, y, 250.0 + 0.9 * z + oz)


def story_cam(cam2d, W, H, shot=None, u=0.0, ceiling=None, depth=None):
    """the story director's 2D shot (centre x/y and zoom) -> a 3D camera. shot = this shot's style (yaw, height,
    move) so each cut sees the place from its own side; u = how far through the shot we are (0..1) for the move:
    "push" creeps in, "orbit" slides round, "crane" rises, "still" holds."""
    zoom = min(1.9, max(0.3, float(cam2d.z)))                          # (no tighter than head and shoulders)
    d = 1272.0 / zoom                                                  # (at zoom 1 the frame is 1080 units tall)
    lx = float(cam2d.x) - 960.0
    ly = min(400.0, max(150.0, float(cam2d.y) * 0.75))
    if zoom > 1.2:                                                     # closer shots aim at the faces (doodle heads
        ly = max(ly, 260.0 + 40.0 * (zoom - 1.2))                      # are big and sit high)
    _x, _y, lz = stage_to_world(cam2d.x, 0, 120)
    if depth is not None:                                              # look at the depth of who is in the shot
        lz = float(depth)
    sh = shot or {}
    yaw = float(sh.get("yaw", 0.22))
    move = sh.get("move", "still")
    e = 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, u)))         # eased: moves start and stop softly
    if move == "push":
        d *= 1.0 - 0.16 * e
    elif move == "pull":
        d *= 0.86 + 0.16 * e
    elif move == "orbit":
        yaw += float(sh.get("swing", 0.35)) * (e - 0.5)
    height = sh.get("height", "eye")
    if move == "crane":                                                # from low to high over the shot
        y = 0.35 * ly + (ly + 0.5 * d - 0.35 * ly) * e
    elif height == "low":
        y = max(40.0, 0.35 * ly)
    elif height == "high":
        y = ly + 0.45 * d
    else:
        y = ly + 0.06 * d
    if ceiling:
        y = min(y, ceiling - 40.0)
    return Cam((lx + math.sin(yaw) * d, y, lz - math.cos(yaw) * d), (lx, ly, lz), fov=46, W=W, H=H)


_SHOTS = {}
HEIGHTS = ("eye", "eye", "eye", "low", "high")
MOVES = ("still", "still", "push", "orbit", "crane", "push")


MAX_SHOT = [5.0]            # seconds: no shot holds longer (a cut to a new angle keeps the eye busy, as films do)


def shot_at(it, f, spec, fps=24):
    """which shot of the scene frame f is in, how far through it (0..1), and that shot's camera style. The director
    makes the cuts (its 2D shots); each cut gets a side, a height and a move of its own, picked steadily from the
    scene's id so a re-render looks the same. A scene's "stick_camera" sets them: {"move": "orbit", "yaw": -20,
    "height": "low"}."""
    key = id(it)
    plan = _SHOTS.get(key)
    if plan is None:
        cams = it.cams
        cuts = [0]
        for i in range(1, len(cams)):
            a, b = cams[i - 1], cams[i]
            if abs(float(b.z) - float(a.z)) > 0.06 * max(0.3, float(a.z)) or abs(float(b.x) - float(a.x)) > 60:
                cuts.append(i)
        cuts.append(len(cams))
        mx = max(1, int(MAX_SHOT[0] * fps))                            # long shots are split into pieces of at
        split = [cuts[0]]                                              # most MAX_SHOT seconds, each its own angle
        for a, b in zip(cuts, cuts[1:]):
            n = max(1, int(math.ceil((b - a) / mx)))
            split += [a + (b - a) * k // n for k in range(1, n)] + [b]
        cuts = split
        sid = str((spec or {}).get("id", ""))
        styles = []
        for k_ in range(len(cuts) - 1):
            rng = random.Random(zlib.crc32(f"{sid}:{k_}".encode()))
            zoom = float(cams[cuts[k_]].z)
            st = {"yaw": rng.choice((-0.34, -0.2, 0.0, 0.2, 0.32)), "height": rng.choice(HEIGHTS),
                  "move": rng.choice(MOVES)}
            if zoom > 1.3:                                             # close-ups: eye level, a slow push at most
                st["height"], st["move"] = "eye", rng.choice(("still", "push"))
            elif zoom < 0.8:                                           # wide shots: show the place from above
                st["height"] = rng.choice(("high", "eye"))
            styles.append(st)
        plan = _SHOTS[key] = (cuts, styles)
        if len(_SHOTS) > 64:
            _SHOTS.pop(next(iter(_SHOTS)))
    cuts, styles = plan
    k_ = max(0, min(len(styles) - 1, next((i for i in range(len(cuts) - 1) if cuts[i] <= f < cuts[i + 1]), 0)))
    st = dict(styles[k_])
    over = (spec or {}).get("stick_camera")
    if isinstance(over, str):
        over = {"move": over}
    if isinstance(over, dict):
        st.update({k: v for k, v in over.items() if k in ("move", "height", "swing")})
        if "yaw" in over:
            st["yaw"] = math.radians(float(over["yaw"]))
    st["seg"] = k_
    u = (f - cuts[k_]) / max(1, cuts[k_ + 1] - cuts[k_])
    return st, u


def draw_scene(ctx, P, it, lt, cue=None):
    """a story scene in Stick 3D: the story's people, poses, faces and director's shots, in the 3D village"""
    W, H = P.W, P.H
    sc = it.scene
    f = max(0, min(int(lt * P.fps), len(it.cams) - 1))
    frame = int(lt * P.fps)
    STYLE[0] = str(P.settings.get("stick_look", "flat")).lower()
    INK_K[0] = 0.55 if (getattr(sc, "spec", None) or {}).get("stick_cinema", P.settings.get("stick_cinema")) else 1.0
    screen = (getattr(sc, "spec", None) or {}).get("stick_screen")
    if screen:                                                        # a screen shot: the map, graphs, a forum
        from . import stick3d_screens
        tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)            # each 5 s piece of a screen: a slow push
        tctx = cairo.Context(tmp)                                      # toward a new spot of it (a cut on the screen)
        if stick3d_screens.draw(tctx, W, H, screen, lt, frame):
            seg = int(lt / MAX_SHOT[0])
            uu = (lt % MAX_SHOT[0]) / MAX_SHOT[0]
            anchors = ((0.5, 0.5), (0.3, 0.35), (0.7, 0.4), (0.4, 0.65), (0.65, 0.6))
            ax, ay = anchors[seg % len(anchors)]
            z_ = 1.0 + (0.0 if seg == 0 else 0.10) + 0.06 * uu
            ctx.identity_matrix()
            ctx.translate(ax * W, ay * H)
            ctx.scale(z_, z_)
            ctx.translate(-ax * W, -ay * H)
            ctx.set_source_surface(tmp, 0, 0)
            ctx.paint()
            ctx.identity_matrix()
            if cue is not None and P.settings.get("stick_bubbles"):   # (words on screen only when asked for)
                stick3d_screens.caption(ctx, W, H, cue.text)
            if (getattr(sc, "spec", None) or {}).get("stick_cinema", P.settings.get("stick_cinema")):
                from . import stick3d_fx
                stick3d_fx.cinema(ctx, W, H, frame)
            return
    wld = _world_for(P, sc, it.bg)
    spec_s = getattr(sc, "spec", None) or {}
    tm = str(spec_s.get("stick_time") or P.settings.get("stick_time") or "").lower()   # (only when asked for)
    MOOD[0] = tm if tm in TIMES else None
    spot = (getattr(wld, "spots", None) or {}).get(str(spec_s.get("stick_spot", "")))
    ANCHOR[0] = (spot[0], spot[1] - (250.0 + 0.9 * 120)) if spot else (0.0, 0.0)
    shot, su = shot_at(it, f, getattr(sc, "spec", None), P.fps)
    people = []
    for cid, tr in sc.tracks.items():
        st = tr.state(lt, sc)
        if st.alpha <= 0.02:
            continue
        c = tr.cdef
        pos = stage_to_world(st.x, st.y, float(getattr(st, "z", 0.0) or 0.0))
        face = 1 if (st.facing or 1) >= 0 else -1
        dir_ = {"camera": -math.pi / 2, "away": math.pi / 2}.get(st.view, 0.0 if face > 0 else math.pi)
        sp = str((c.spec or {}).get("species", "") or "").lower()
        if sp in DINOS:
            moving = abs(tr.state(lt + 0.1, sc).x - st.x) > 2.0
            people.append({"id": cid, "kind": "dino", "pos": pos, "dir": dir_, "run": 1.0 if moving else 0.0,
                           "scale": float((c.spec or {}).get("scale", 1.0)), "roar": 1.0 if st.mouth else 0.25})
        elif stick3d_animals.kind_of(sp or c.species) and not (c.spec or {}).get("thing") and \
                not (c.spec or {}).get("sketch"):                      # 🐄 a cartoon animal (stick3d_animals)
            moving = abs(tr.state(lt + 0.1, sc).x - st.x) > 2.0
            people.append({"id": cid, "kind": "animal", "species": c.species, "pos": pos, "dir": dir_,
                           "pose": st.pose, "face": st.face, "mouth": st.mouth or 0.0, "moving": moving,
                           "scale": float((c.spec or {}).get("size", 1.0)),
                           "sitting": str(getattr(tr, "action_at", lambda *_: "")(lt) or "") == "sit"})
        elif c.kind != "human" or (c.spec or {}).get("thing"):
            people.append({"id": cid, "kind": "ink", "pos": pos, "dir": dir_, "cdef": c, "state": st})
        else:
            dx_ = abs(tr.state(lt + 0.1, sc).x - st.x)
            running = dx_ > 30.0                                       # (faster than 3 m/s: speed lines)
            people.append({"id": cid, "pos": pos, "dir": dir_, "pose": st.pose, "face": st.face or "neutral",
                           "mouth": st.mouth or 0.0, "scale": c.scale, "look": _look_of(c, wld), "speed": running,
                           "moving": dx_ > 2.0, "talking": bool(cue is not None and not cue.narration and cue.speaker
                                                                 in (cid, c.name)),
                           "keep_back": bool((c.spec or {}).get("keep_back") or spec_s.get("stick_backs")),
                           "to_camera": bool((c.spec or {}).get("to_camera")),
                           "reporter": bool((c.spec or {}).get("to_camera")) or cid in (spec_s.get("stick_to_camera") or ())})
    #                                                                   (a reporter talks to the lens; "stick_to_camera":
    #                                                                    [ids] turns people to it in one scene)
    lx_ = float(it.cams[f].x) - 960.0                                  # the people the shot is on: nearest to its
    near_ = sorted(people, key=lambda q: abs(q["pos"][0] - lx_))[:2]   # centre; the camera looks at their depth
    depth = (sum(q["pos"][2] for q in near_) / len(near_)) if near_ else None
    cam = story_cam(it.cams[f], W, H, shot, su, getattr(wld, "ceiling", None), depth)
    cam_look = cam.look
    named_cam = False
    named = spec_s.get("stick_shot")                                   # a named camera of the place ("desk",
    if named:                                                          # "through_window", "from_gate" ...), or
        if isinstance(named, str):                                     # [eye, look] in metres from the spot
            named = (getattr(wld, "shots", None) or {}).get(named)
        elif isinstance(named, (list, tuple)) and len(named) == 2:
            ox_, oz_ = spot if spot else (0.0, 450.0)
            named = tuple((ox_ + float(p_[0]) * M, float(p_[1]) * M, oz_ + float(p_[2]) * M) for p_ in named)
        if named:
            e_, l_ = np.array(named[0], float), np.array(named[1], float)
            seg = int(shot.get("seg", 0))
            if seg % 2 == 1 and not spec_s.get("stick_shot_hold"):    # every other piece: closer, from a side
                side_ = 1 if (seg // 2) % 2 == 0 else -1               # (the same place, a new angle - the cut)
                parked = [c_[1] for c_ in cars_at(spec_s.get("stick_cars"), lt)]
                for sd_ in (side_, -side_):                            # not from inside a parked car
                    v_ = e_ - l_
                    ang_ = math.radians(28) * sd_
                    ca_, sa_ = math.cos(ang_), math.sin(ang_)
                    v_ = np.array([v_[0] * ca_ - v_[2] * sa_, v_[1] * 0.8, v_[0] * sa_ + v_[2] * ca_]) * 0.62
                    if all(math.hypot(l_[0] + v_[0] - q[0], l_[2] + v_[2] - q[2]) > 3.0 * M for q in parked) \
                            and not _blocked(wld, l_ + v_, l_):        # (nor through a wall)
                        e_ = l_ + v_
                        break
            u_ = 0.5 - 0.5 * math.cos(math.pi * su)                    # a slow creep in over every piece
            e_ = e_ + (l_ - e_) * (0.18 if spec_s.get("stick_shot_move") else 0.08) * u_
            cam = Cam(tuple(e_), tuple(l_), fov=52, W=W, H=H)
            cam_look = cam.look
            named_cam = True
    cars = cars_at(spec_s.get("stick_cars"), lt)
    CAR_EXTRA.clear()
    CAR_EXTRA.update({str(c_.get("id")): c_ for c_ in spec_s.get("stick_cars") or ()})
    for q in people:                                                   # shoes and trouser ends caked in mud
        if q["id"] in (spec_s.get("stick_muddy") or ()):
            q["muddy"] = True
    if cars:                                                           # the scene's cars (and the dust they raise)
        import copy
        wld = copy.copy(wld)
        riders = {str(c.get("id")): c.get("rider") for c in spec_s.get("stick_cars") or () if c.get("rider")}
        byid_ = {q["id"]: q for q in people}
        for cid_, cpos, chead, cmov, ccol, _k in cars:
            if _k in ("bike", "motorbike", "scooter"):
                wld.extend(bike_meshes(cid_, cpos, chead, ccol, lt))
            elif _k in ("jet", "plane", "aircraft"):
                ex_ = CAR_EXTRA.get(str(cid_)) or {}
                al_ = float(ex_.get("alt", 0))
                cl_ = ex_.get("climb")
                if isinstance(cl_, dict) and lt > float(cl_.get("at", 0)):     # lifting off: it climbs faster and
                    u_ = lt - float(cl_.get("at", 0))                           # faster (the lift grows with speed)
                    al_ += float(cl_.get("rate", 2.5)) * u_ * u_
                wld.extend(jet_meshes(cid_, cpos, chead, ccol, lt, al_, bool(ex_.get("stairs"))))
            elif _k in ("apache", "gunship", "army_helicopter"):
                wld.extend(apache_meshes(cid_, cpos, chead, ccol, lt,
                                         float((CAR_EXTRA.get(str(cid_)) or {}).get("alt", 25))))
            elif _k in ("helicopter", "heli", "chopper"):
                wld.extend(heli_meshes(cid_, cpos, chead, ccol, lt,
                                       float((CAR_EXTRA.get(str(cid_)) or {}).get("alt", 25))))
            else:
                ms_ = (machine_meshes(cid_, cpos, chead, _k, lt) if _k in MACHINES
                       else car_meshes(cid_, cpos, chead, ccol, _k, lt))
                fly_ = (CAR_EXTRA.get(str(cid_)) or {}).get("fly")
                wld.extend(_flown(ms_, cpos, chead, fly_, lt) if fly_ else ms_)
            rq = byid_.get(riders.get(str(cid_)))
            if rq is not None:                                         # the rider goes with the vehicle
                fwd_ = np.array([math.cos(chead), 0.0, math.sin(chead)])
                sd_ = np.array([-fwd_[2], 0.0, fwd_[0]])
                if _k in ("bike", "motorbike", "scooter"):
                    rq["pos"] = tuple(cpos - fwd_ * 0.35 * M + np.array([0.0, 0.45 * M, 0.0]))
                    rq["pose"] = _moto_pose()
                else:                                                  # the driver's seat (on the right: India)
                    sx_, sy_ = seat_of(_k)
                    rq["pos"] = tuple(cpos + fwd_ * sx_ * M - sd_ * 0.42 * M + np.array([0.0, sy_ * M, 0.0]))
                    rq["pose"] = _drive_pose()
                rq["dir"] = chead
                rq["riding"] = True                                    # (hands stay on the bars / the wheel)
                rq["moving"] = True
    if str(spec_s.get("stick_faces") or P.settings.get("stick_faces") or "").lower() == "camera":
        for q in people:
            q["to_camera"] = True
    else:
        _look_at_partners(people, sc, lt)
    for rule in spec_s.get("stick_watch") or ():                       # everyone turns to look at someone (a hall
        if not isinstance(rule, dict) or lt < float(rule.get("at", 0)):    # turning to the door); each a beat
            continue                                                   # later than the last, as people notice
        tgt = next((q for q in people if q["id"] == rule.get("target")), None)
        if tgt is None:
            continue
        who = rule.get("who", "all")
        for k_, q in enumerate(people):
            if q is tgt or (who != "all" and q["id"] not in who):
                continue
            if lt < float(rule.get("at", 0)) + 0.12 * (k_ % 6):
                continue
            d_ = np.array(tgt["pos"], float) - np.array(q["pos"], float)
            q["dir"] = math.atan2(d_[2], d_[0])
    tc = None if spec_s.get("stick_shot_hold") else _talk_cam(sc, people, lt, wld, spec_s, cam, W, H)   # (a held
    #                                                                   shot - one news camera - never cuts away)
    if tc is not None:
        cam, cam_look, named_cam = tc, tc.look, True
    INSIDE[0] = None
    fol = spec_s.get("stick_follow")
    if fol and cars:                                                   # a tracking shot: the camera rides with a
        if isinstance(fol, str):                                       # vehicle (behind it, beside it, ahead)
            fol = {"car": fol}
        hit = [c_ for c_ in cars if str(c_[0]) == str(fol.get("car"))]
        if hit:
            _id, cp_, ch_ = hit[0][:3]
            fw_ = np.array([math.cos(ch_), 0.0, math.sin(ch_)])
            sd_ = np.array([-fw_[2], 0.0, fw_[0]])
            dist_ = float(fol.get("dist", 6.0)) * M
            h_ = float(fol.get("height", 1.8)) * M
            side = str(fol.get("side", "behind"))
            up_ = np.array([0.0, 1.0, 0.0])
            st_ = seat_of(hit[0][5])                                   # the driver (see the riders above)
            seat_ = cp_ + fw_ * st_[0] * M - sd_ * 0.42 * M + up_ * (st_[1] - 0.08) * M
            if side == "driver":                                       # from the passenger seat, at the driver
                eye_ = seat_ + fw_ * 0.75 * M + sd_ * 1.04 * M + up_ * 1.05 * M
                look_ = seat_ + up_ * 1.0 * M + fw_ * 0.05 * M
                INSIDE[0] = ("driver", cp_, ch_, st_)
            elif side in ("profile", "passenger", "sideways"):         # sitting beside him: the driver side-on,
                eye_ = seat_ + sd_ * 0.85 * M + up_ * 1.12 * M + fw_ * 0.05 * M   # the window and the field behind
                look_ = seat_ + up_ * 1.02 * M + fw_ * 0.12 * M
                INSIDE[0] = ("profile", cp_, ch_, st_)
            elif side in ("shoulder", "over_shoulder"):                # from just behind him, over his shoulder:
                eye_ = seat_ - fw_ * 0.5 * M + sd_ * 0.34 * M + up_ * 1.18 * M    # at his head height: his cap and
                look_ = seat_ + fw_ * 6 * M - sd_ * 0.1 * M + up_ * 1.45 * M      # shoulder big, the road beyond
                drv_ = [str(c_.get("rider")) for c_ in spec_s.get("stick_cars") or ()
                        if str(c_.get("id")) == str(fol.get("car"))]
                INSIDE[0] = ("shoulder", cp_, ch_, st_, drv_[0] if drv_ else None, spec_s.get("stick_nav") or {})
                w2_ = copy.copy(wld)                                   # (we sit inside it: its own body would
                w2_[:] = [m_ for m_ in wld if getattr(m_, "car_id", None) != str(_id)]   # fill the windscreen)
                wld = w2_
            elif side == "pov":                                        # the driver's eyes, through the windscreen
                eye_ = seat_ + up_ * 1.22 * M + fw_ * 0.15 * M
                look_ = eye_ + fw_ * 20 * M - up_ * 0.9 * M
                INSIDE[0] = ("pov", cp_, ch_, st_)
                drv_ = {str(c_.get("rider")) for c_ in spec_s.get("stick_cars") or ()
                        if str(c_.get("id")) == str(fol.get("car"))}
                people[:] = [q for q in people if str(q["id"]) not in drv_]   # (we are in his eyes)
            elif side in ("drone_behind", "chase_drone"):              # high behind it: the track runs on ahead;
                u_ = min(1.0, lt / max(0.1, float(fol.get("over", 4.0))))   # "height_to": it swoops down to a low chase
                u_ = u_ * u_ * (3 - 2 * u_)
                h0_ = float(fol.get("height", 8))
                h_ = h0_ + (float(fol.get("height_to", h0_)) - h0_) * u_
                d0_ = float(fol.get("dist", 13))
                d_ = d0_ + (float(fol.get("dist_to", d0_)) - d0_) * u_
                eye_ = cp_ - fw_ * d_ * M + sd_ * 0.6 * M + up_ * h_ * M
                look_ = cp_ + fw_ * 12 * M
            elif side == "drone":                                      # high and to the side, sweeping along
                eye_ = cp_ - fw_ * 14 * M + sd_ * 9 * M + up_ * float(fol.get("height", 12)) * M
                look_ = cp_ + fw_ * 6 * M
            elif side == "side":
                eye_, look_ = cp_ + sd_ * dist_ + up_ * h_ + fw_ * 1.0 * M, cp_ + up_ * 1.0 * M + fw_ * 1.5 * M
            elif side == "front":
                eye_, look_ = cp_ + fw_ * dist_ + up_ * h_, cp_ + up_ * 1.0 * M
            else:
                eye_, look_ = cp_ - fw_ * dist_ + up_ * h_ + sd_ * 0.8 * M, cp_ + fw_ * 8.0 * M + up_ * 0.9 * M
            fov_ = 58 if INSIDE[0] and INSIDE[0][0] == "shoulder" else (72 if INSIDE[0] else 50)
            cam = Cam(tuple(eye_), tuple(look_), fov=float(fol.get("fov", fov_)), W=W, H=H)
            cam_look, named_cam = cam.look, True
    ground = []                                                        # the story's props: held, or standing
    byid = {q["id"]: q for q in people}
    spec_ = getattr(sc, "spec", None) or {}
    own = {str(q.get("id")) for q in (spec_.get("props") or []) if isinstance(q, dict)}
    own |= {str(e.get("prop")) for e in (spec_.get("events") or []) if isinstance(e, dict) and e.get("prop")}
    for pid, pr in (getattr(sc, "props", None) or {}).items():
        st_ = pr.at(lt)[0]
        if st_[0] == "in":
            continue                                                  # (in a bag / a box: not seen)
        if st_[0] == "held":
            if st_[1] in byid:
                byid[st_[1]].setdefault("held", []).append(pr)
            continue
        if str(pid) not in own:
            continue                                                  # (left in another place: not here)
        x_, y_, f_ = pr.pos(lt)
        ground.append({"pr": pr, "pos": stage_to_world(x_, y_, float(pr.z_at(lt) or 0.0)), "f": 1 if (f_ or 1) >= 0 else -1})
    chase = [q for q in people if q.get("kind") == "dino"]
    if chase:                                                          # a dino about: a side-on camera that keeps it
        near = [q for q in people if q.get("kind") != "dino"           # and the people near it in the frame together
                and abs(q["pos"][0] - chase[0]["pos"][0]) < 20 * M]
        runners = chase + near
        xs = [q["pos"][0] for q in runners] + [q["pos"][0] + 3.6 * M * math.cos(q["dir"]) for q in chase]
        lo, hi = min(xs), max(xs)
        d = max(11.0 * M, (hi - lo) * 1.05 + 4.0 * M)
        cx = (lo + hi) / 2
        lz = chase[0]["pos"][2]
        cam = Cam((cx + 0.08 * d, 1.5 * M, lz - d), (cx, 2.0 * M, lz), fov=46, W=W, H=H)
        cam_look = cam.look
    bubble = None
    if cue is not None and P.settings.get("stick_bubbles"):            # the voices carry the lines: no speech
        who = next((cid for cid, tr in sc.tracks.items()
                    if cue.speaker and cue.speaker in (cid, tr.cdef.name)), None)
        bubble = (who, cue.text) if who and not cue.narration else ("narrator", cue.text)
    ctx.identity_matrix()
    look_d = float(np.linalg.norm(cam.pos - np.array(cam_look)))
    puffs = []
    if cars and not getattr(wld, "ceiling", None):                     # dust: a puff left behind the car every
        for j in range(1, 9):                                          # 0.12 s on the dirt, growing and thinning
            age = j * 0.12                                             # as it spreads in the air
            for cid_, cpos, chead, cmov, ccol, _k in cars_at(spec_s.get("stick_cars"), lt - age):
                if not cmov or _k in HELIS or (CAR_EXTRA.get(str(cid_)) or {}).get("fly"):
                    continue
                back = -np.array([math.cos(chead), 0.0, math.sin(chead)])
                side = np.array([-back[2], 0.0, back[0]])
                jit = math.sin(j * 2.3 + sum(map(ord, cid_)) % 7) * 0.4 * M
                q = cpos + back * 2.6 * M + side * jit + np.array([0.0, (0.35 + 0.5 * age) * M, 0.0])
                puffs.append((q, (0.45 + 1.4 * age) * M, 0.30 * (1.0 - age / 1.08)))
    from . import stick3d_fx as fx                                    # weather, effects, shake (stick3d_fx)
    lv = fx.levels(sc, it.bg, lt)
    SKY_HOOK.clear()
    if lv and lv.get("rain", 0) > 0.25 and not getattr(sc, "indoor", False):   # the monsoon sky over the place
        ra_ = min(1.0, lv["rain"])
        SKY_HOOK.append(lambda c_, cm_, hz_: fx.rain_clouds(c_, W, H / 1080.0, hz_, ra_, lt))
    hu_ = spec_s.get("stick_hurricane")
    if hu_:                                                            # the storm's spiral over the sea
        SKY_HOOK.append(lambda c_, cm_, hz_: fx.hurricane_sky(c_, W, H / 1080.0, hz_, hu_ if isinstance(hu_, dict)
                                                              else {}, lt))
    sw = spec_s.get("stick_stormwall")
    if sw:
        u_sw = max(0.0, min(1.0, (lt - float(sw.get("start", 0))) / max(0.5, float(sw.get("end", 10)) -
                                                                        float(sw.get("start", 0)))))
        SKY_HOOK.append(lambda c_, cm_, hz_: fx.storm_wall(c_, cm_, W, H / 1080.0, hz_, u_sw, frame))
    if spec_s.get("stick_burnt"):                                     # a station burnt out: its box and panel black
        import copy as _cp
        wld = _cp.copy(wld)
        for i_, m_ in enumerate(wld):
            if m_.name in ("station", "solar"):
                m2 = _cp.copy(m_)
                m2.name = "charred"
                wld[i_] = m2
    effs = getattr(sc, "effects", None) or []
    cam = fx.shaken(cam, fx.shake_amount(sc, spec_s, lt), frame, Cam, M)
    with fx.swayed(wld, lv["wind"] if lv else 0.0, lt, M):
        draw(ctx, W, H, cam, wld, people, lt, frame, bubble, near_cut=0.0 if named_cam else 0.55 * look_d,
             ground=ground)
    S_ = H / 1080.0
    bs = spec_s.get("stick_bigscreen")
    if bs and getattr(wld, "screens", None):                           # a video wall: one kind for all, or a list
        for k_, corners in enumerate(wld.screens):
            sp_ = bs[k_ % len(bs)] if isinstance(bs, list) else bs
            if sp_:
                fx.big_screen(ctx, cam, W, H, corners, sp_, lt, frame)
        for q in people:                                               # (people stand in front of the wall)
            _person(ctx, Pen(ctx, frame // (2 * sketch.BOIL), unit=1.0), cam, q, lt, H / 1080.0) \
                if q["pos"][2] > wld.screens[0][0][2] - 6 * M else None
    elif bs and getattr(wld, "bigscreen", None):                       # the hall's giant screen shows a slide
        fx.big_screen(ctx, cam, W, H, wld.bigscreen, bs, lt, frame)
        if getattr(wld, "bigscreen2", None):                           # (and its side screen the same)
            fx.big_screen(ctx, cam, W, H, wld.bigscreen2, bs, lt, frame)
        for q in people:                                               # (the people on stage stand in front of it)
            if q["pos"][2] > wld.bigscreen[0][2] - 8 * M:
                _person(ctx, Pen(ctx, frame // (2 * sketch.BOIL), unit=1.0), cam, q, lt, H / 1080.0)
    if lv:
        fx.storm_sky(ctx, W, H, lv)
    if effs:
        pos_of = {q["id"]: q["pos"] for q in people}

        def where(e):
            if e.get("who") in pos_of:
                return np.asarray(pos_of[e["who"]], float) + np.array([0.0, 1.2 * M, 0.0])
            x_ = e.get("x")
            if x_ is None:
                return None
            return stage_to_world(float(x_), float(e.get("y", 0) or 0), float(e.get("z", 0) or 0))
        fx.effects(ctx, cam, M, S_, effs, lt, where)
    if lv and lv.get("rain", 0) > 0.05 and getattr(wld, "puddles", None) and not INSIDE[0]:
        fx.ripples(ctx, cam, wld.puddles, lt, lv["rain"], S_, M)
    if lv and lv.get("rain", 0) > 0.02 and not (INSIDE[0] and INSIDE[0][0] == "profile"):
        fx.rain(ctx, W, H, S_, lv["rain"], lv.get("wind", 1.0), frame)   # (side-on inside: only on the glass)
    hl = spec_s.get("stick_hail")
    if hl and float(hl.get("start", 0)) <= lt < float(hl.get("end", 1e9)):
        u_ = min(1.0, (lt - float(hl.get("start", 0))) / 0.8, (float(hl.get("end", 1e9)) - lt) / 0.8)
        fx.hail(ctx, W, H, S_, u_, frame, lt)
    if effs:
        fx.lightning(ctx, W, H, S_, effs, lt)
    if cars and (MOOD[0] in ("night", "evening") or (lv and lv.get("storm", 0) > 0.5)):
        lit_ = [c_ for c_ in cars if (CAR_EXTRA.get(str(c_[0])) or {}).get(           # (a parked car with nobody
            "lights", (CAR_EXTRA.get(str(c_[0])) or {}).get("rider", True) is not None)]   # in it is dark)
        fx.headlights(ctx, cam, lit_, M, S_)
    for c_ in cars or ():                                              # rescue helicopters' searchlights
        if c_[5] in HELIS and c_[5] not in ("jet", "plane", "aircraft") and (CAR_EXTRA.get(str(c_[0])) or {}).get("light", True):
            fx.searchlight(ctx, cam, c_[1], float((CAR_EXTRA.get(str(c_[0])) or {}).get("alt", 25)), c_[2], M,
                           H / 1080.0, lt)
    bo = spec_s.get("stick_blackout")
    if bo:
        fx.blackout(ctx, W, H, lt, float(bo.get("at", 0)) if isinstance(bo, dict) else float(bo))
    SKY_HOOK.clear()
    if puffs:
        _dust(ctx, cam, puffs)
    if INSIDE[0]:                                                      # inside the car: dashboard, wheel, glass
        fx.car_inside(ctx, cam, W, H, H / 1080.0, INSIDE[0], lt, frame, (lv or {}).get("rain", 0.0), M)
        if INSIDE[0][0] == "shoulder":                                 # the driver is nearer than the dashboard
            for q in people:
                if str(q["id"]) == str(INSIDE[0][4]):
                    _person(ctx, Pen(ctx, frame // (2 * sketch.BOIL), unit=1.0), cam, q, lt, H / 1080.0)
    if P.settings.get("stick_grade", True):                            # the colour script's grade of this beat
        _grade(ctx, W, H, scene_mood(sc, spec_s))
    if spec_s.get("stick_lens_rain"):                                  # rain hitting the news camera's lens
        fx.lens_rain(ctx, W, H, H / 1080.0, lt, float(spec_s["stick_lens_rain"]))
    if spec_s.get("stick_debris"):                                     # the hurricane throwing things about
        fx.debris(ctx, W, H, H / 1080.0, float(spec_s["stick_debris"]), lt)
    live_ = spec_s.get("stick_live") if isinstance(spec_s.get("stick_live"), dict) else {}
    if live_.get("fall_at") is not None:                               # the news camera blown over
        fx.camera_falls(ctx, W, H, H / 1080.0, lt - float(live_["fall_at"]), frame)
    if spec_s.get("stick_live") and not (live_.get("fall_at") is not None and lt - float(live_["fall_at"]) > 0.7):
        fx.broadcast(ctx, W, H, spec_s["stick_live"] if isinstance(spec_s["stick_live"], dict) else {}, lt, frame)
    if spec_s.get("stick_title"):                                      # "NEW DELHI · 6:10 AM", typed in
        fx.place_title(ctx, W, H, str(spec_s["stick_title"]), lt)
    if spec_s.get("stick_cinema", P.settings.get("stick_cinema")):     # the film look: grain and the 2.39 frame
        fx.cinema(ctx, W, H, frame)
