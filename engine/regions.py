"""🗺 The nine regions of the Milky Way (the game's only galaxy): the road of the journey (engine/saga.py), from the far side
back to Earth. Each region is a slice of the galaxy's disk on the map (engine/galaxy.py: x, y with the centre at 0 and the
Sun at (0, 0.55)) named after a real place in it; the core is its own region round the black hole. Every star belongs to one,
and every world takes its region's look (engine/themes.py).
🎮 game rule: the real places are spread round the disk for the journey - their names are real, the map is the game's."""
import math

# key (the chapter's), the real place, its Hindi name, the wedge's middle (degrees round the centre)
REGIONS = [
    ("cradle", "Carina Nebula", "कैराइना नीहारिका", -90),
    ("ember", "Crab Nebula", "केकड़ा नीहारिका", -45),
    ("frost", "Outer Arm", "बाहरी भुजा", 0),
    ("hollow", "Omega Centauri", "ओमेगा सेंटॉरी", 45),
    ("tide", "Lagoon Nebula", "लैगून नीहारिका", 90),
    ("bloom", "Pleiades", "कृत्तिका", 135),
    ("storm", "Eagle Nebula", "गरुड़ नीहारिका", 180),
    ("crystal", "Cygnus Rift", "हंस दरार", 225),
    ("heart", "Sagittarius A*", "धनु A*", None),
]
CORE = 0.15                                                       # (map units: the core, ~2 kpc round the black hole)
NAME = {k: n for k, n, _, _ in REGIONS}
HI = {n: h for _, n, h, _ in REGIONS}


def of(x, y):
    """the region key of a place on the map"""
    if math.hypot(x, y) < CORE:
        return "heart"
    a = math.degrees(math.atan2(y, x))
    return min((r for r in REGIONS if r[3] is not None), key=lambda r: abs((a - r[3] + 180) % 360 - 180))[0]


def of_star(index):
    from . import galaxy
    s = galaxy.star("milkyway", int(index))
    return of(float(s.get("x") or 0), float(s.get("y") or 0))
