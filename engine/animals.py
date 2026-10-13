"""Animals: four-legged animals (tiger, lion, dog, cat, fox, wolf, cow, horse, goat, deer,
elephant, rabbit, bear, pig) and birds (bird, sparrow, crow, parrot, eagle, hen, duck).
Monkeys use the human rig (see character.py).

Use in JSON:  "sheru": {"name": "Sheru", "species": "tiger"}
Animals understand the normal actions (walk, run, sit, sleep, jump, talk, happy/sad...) plus
their own: roar/bark/meow/moo/neigh/trumpet/call, eat, wag, pounce, hop, fly, peck, sing.
"""
import math

import cairo

from .poses import ActionSpec, keyframes, blend
from .util import hex_to_rgb, darker, lighter, clamp, smoothstep, TAU, rotate, dirv

QUADS = {
    # body length, thigh, shin, girth, neck len, neck width, head r, snout len/width, ears, tail, fur, belly, extras
    "tiger":    dict(body=150, thigh=52, shin=52, girth=54, neck=26, neck_w=40, head=33, snout=(24, 22), ears="round",
                     tail="long", fur="#ef8a22", belly="#fff3df", pattern="stripes", whiskers=True, scale=1.0,
                     walk=170, run=620, sound="roar", step="paw"),
    "lion":     dict(body=150, thigh=54, shin=54, girth=52, neck=28, neck_w=42, head=32, snout=(24, 22), ears="round",
                     tail="tuft", fur="#d8a444", belly="#f5dfae", mane="#8a4b1b", whiskers=True, scale=1.05,
                     walk=160, run=600, sound="roar", step="paw"),
    "dog":      dict(body=104, thigh=40, shin=40, girth=38, neck=24, neck_w=26, head=25, snout=(22, 17), ears="floppy",
                     tail="curve", fur="#b8773b", belly="#f3d6ae", scale=0.82, walk=180, run=560, sound="bark", step="paw"),
    "cat":      dict(body=86, thigh=32, shin=32, girth=30, neck=18, neck_w=20, head=22, snout=(9, 11), ears="pointy",
                     tail="long_up", fur="#e59a4d", belly="#fff1dd", pattern="stripes_light", whiskers=True, scale=0.62,
                     walk=140, run=480, sound="meow", step="paw"),
    "fox":      dict(body=100, thigh=38, shin=38, girth=34, neck=22, neck_w=24, head=23, snout=(24, 14), ears="pointy_tall",
                     tail="bushy", fur="#e2661d", belly="#ffffff", tail_tip="#ffffff", scale=0.78, walk=170, run=560,
                     sound="bark", step="paw"),
    "wolf":     dict(body=120, thigh=46, shin=46, girth=40, neck=26, neck_w=30, head=27, snout=(26, 17), ears="pointy_tall",
                     tail="bushy", fur="#8d939c", belly="#e8e8e8", scale=0.95, walk=170, run=600, sound="howl", step="paw"),
    "cow":      dict(body=172, thigh=56, shin=52, girth=72, neck=26, neck_w=44, head=30, snout=(26, 26), ears="side",
                     tail="tuft", fur="#f7f3ea", belly="#f7f3ea", pattern="patches", horns="small", muzzle="#f5b6b6",
                     udder=True, scale=1.15, walk=120, run=320, sound="moo", step="hoof"),
    "horse":    dict(body=160, thigh=72, shin=74, girth=58, neck=66, neck_w=34, neck_angle=58, head=22, snout=(46, 22),
                     ears="pointy", tail="long_hair", fur="#8b5a2b", belly="#9c6a39", mane="#3a2414", hooves=True,
                     scale=1.2, walk=170, run=720, sound="neigh", step="hoof"),
    "goat":     dict(body=110, thigh=48, shin=44, girth=40, neck=26, neck_w=24, head=22, snout=(22, 16), ears="side",
                     tail="short_up", fur="#ebe4d2", belly="#ffffff", horns="curved", beard=True, scale=0.85,
                     walk=140, run=420, sound="bleat", step="hoof"),
    "deer":     dict(body=126, thigh=66, shin=64, girth=42, neck=46, neck_w=22, neck_angle=55, head=21, snout=(26, 15),
                     ears="pointy_tall", tail="short_up", fur="#b97a3d", belly="#fff4e6", pattern="spots",
                     antlers=True, scale=1.0, walk=160, run=650, sound=None, step="hoof"),
    "elephant": dict(body=200, thigh=68, shin=58, girth=112, neck=6, neck_w=70, head=56, snout=(0, 0), ears="huge",
                     tail="tuft_thin", fur="#98a2b3", belly="#8d97a8", trunk=True, tusks=True, leg_w=36,
                     scale=1.45, walk=110, run=260, sound="trumpet", step="stomp"),
    "rabbit":   dict(body=60, thigh=28, shin=26, girth=36, neck=10, neck_w=22, head=21, snout=(8, 12), ears="long",
                     tail="puff", fur="#e6e0d6", belly="#ffffff", whiskers=True, scale=0.55, walk=150, run=380,
                     sound=None, step=None, hop=True),
    "bear":     dict(body=150, thigh=50, shin=44, girth=84, neck=18, neck_w=48, head=34, snout=(20, 20), ears="round",
                     tail="short_up", fur="#6b4226", belly="#8a5a36", muzzle="#c9a17a", scale=1.2, walk=120, run=420,
                     sound="growl", step="paw"),
    "pig":      dict(body=120, thigh=28, shin=26, girth=66, neck=10, neck_w=46, head=30, snout=(14, 20), ears="floppy",
                     tail="curly", fur="#f4a6b8", belly="#f7bccb", muzzle="#ec8fa6", scale=0.85, walk=110, run=300,
                     sound="oink", step="hoof", snout_flat=True),
    "camel":    dict(body=165, thigh=78, shin=76, girth=54, neck=74, neck_w=26, neck_angle=62, head=20, snout=(34, 17),
                     ears="side", tail="tuft_thin", fur="#c9a36a", belly="#d8b782", hump=1, hooves=True, scale=1.35,
                     walk=120, run=420, sound="bleat", step="hoof"),
    "zebra":    dict(body=150, thigh=66, shin=68, girth=56, neck=58, neck_w=32, neck_angle=58, head=21, snout=(42, 21),
                     ears="pointy", tail="tuft", fur="#fbfbfb", belly="#f4f4f4", mane="#161616", pattern="zebra",
                     stripe_color="#161616", hooves=True, scale=1.1, walk=160, run=700, sound="neigh", step="hoof"),
    "giraffe":  dict(body=140, thigh=92, shin=90, girth=50, neck=150, neck_w=26, neck_angle=72, head=20, snout=(30, 16),
                     ears="pointy", tail="tuft_thin", fur="#eab45c", belly="#f3dcaa", pattern="giraffe",
                     spot_color="#8b4a1c", horns="small", hooves=True, scale=1.6, walk=140, run=450, sound=None,
                     step="hoof"),
    "leopard":  dict(body=140, thigh=48, shin=48, girth=46, neck=24, neck_w=34, head=29, snout=(20, 19), ears="round",
                     tail="long", fur="#e7b55c", belly="#fbf0d8", pattern="leopard", spot_color="#2a1a10",
                     whiskers=True, scale=0.95, walk=170, run=640, sound="growl", step="paw"),
    "cheetah":  dict(body=138, thigh=54, shin=56, girth=40, neck=26, neck_w=28, head=24, snout=(18, 16), ears="round",
                     tail="long", fur="#e9bf6b", belly="#fbf2dc", pattern="leopard", spot_color="#1c140e",
                     whiskers=True, scale=0.95, walk=180, run=900, sound="growl", step="paw"),
    "panda":    dict(body=140, thigh=46, shin=40, girth=86, neck=16, neck_w=48, head=36, snout=(16, 18), ears="round",
                     tail="short_up", fur="#f7f7f5", belly="#f7f7f5", muzzle="#ffffff", pattern="panda",
                     scale=1.1, walk=100, run=300, sound="growl", step="paw"),
    "buffalo":  dict(body=176, thigh=54, shin=48, girth=78, neck=22, neck_w=48, head=31, snout=(24, 26), ears="side",
                     tail="tuft", fur="#3a3a3f", belly="#434349", horns="curved", muzzle="#57575e", scale=1.2,
                     walk=110, run=300, sound="moo", step="hoof"),
    "sheep":    dict(body=108, thigh=36, shin=34, girth=56, neck=16, neck_w=30, head=20, snout=(16, 15), ears="side",
                     tail="short_up", fur="#f5f2ea", belly="#ffffff", pattern="wool", muzzle="#e6d8c6",
                     leg_color="#3b3b3b", scale=0.8, walk=120, run=380, sound="bleat", step="hoof"),
    "donkey":   dict(body=135, thigh=56, shin=56, girth=54, neck=46, neck_w=30, neck_angle=50, head=22, snout=(36, 20),
                     ears="long", tail="tuft", fur="#8f8a86", belly="#dcd7d0", mane="#4a4540", muzzle="#e8e3dc",
                     hooves=True, scale=1.0, walk=130, run=480, sound="neigh", step="hoof"),
    "squirrel": dict(body=44, thigh=18, shin=16, girth=22, neck=6, neck_w=14, head=14, snout=(8, 9), ears="pointy",
                     tail="bushy", fur="#b5651d", belly="#f2dab5", scale=0.35, walk=150, run=520, sound=None,
                     step=None, hop=True),
    "mouse":    dict(body=34, thigh=12, shin=10, girth=18, neck=4, neck_w=12, head=12, snout=(10, 8), ears="round",
                     tail="long", fur="#9c9c9c", belly="#e2e2e2", whiskers=True, scale=0.25, walk=160, run=520,
                     sound=None, step=None),
    "hippo":    dict(body=185, thigh=36, shin=30, girth=100, neck=10, neck_w=70, head=44, snout=(34, 36), ears="round",
                     tail="tuft_thin", fur="#8e7f9c", belly="#c9a5b8", muzzle="#c79bb0", scale=1.35, walk=90, run=260,
                     sound="growl", step="stomp", snout_flat=True),
}
BIRDS = {
    "bird":    dict(body=26, head=13, beak=("#f6a21e", 12), fur="#3d8fd6", belly="#dbeeff", wing="#2d6fae", scale=1.0,
                    sound="chirp", fly=True),
    "sparrow": dict(body=22, head=12, beak=("#e0a44a", 9), fur="#9a6a3f", belly="#efe1c9", wing="#6b4424", scale=0.9,
                    sound="chirp", fly=True),
    "crow":    dict(body=30, head=14, beak=("#222222", 16), fur="#25262b", belly="#34353c", wing="#1b1c20", scale=1.1,
                    sound="caw", fly=True),
    "parrot":  dict(body=28, head=15, beak=("#e63946", 13), fur="#2fb24c", belly="#b5e48c", wing="#1f7a35", scale=1.1,
                    sound="squawk", fly=True, tail_long=True),
    "eagle":   dict(body=40, head=17, beak=("#f4c20d", 16), fur="#6b4226", belly="#8a5a36", wing="#4e2f18",
                    headc="#ffffff", scale=1.5, sound="screech", fly=True),
    "hen":     dict(body=38, head=16, beak=("#f4a300", 11), fur="#ffffff", belly="#f4f1ea", wing="#e9e4da", comb=True,
                    scale=1.1, sound="cluck", fly=False),
    "duck":    dict(body=34, head=16, beak=("#ff9f1c", 18), fur="#ffffff", belly="#f7f7f7", wing="#e6e6e6", scale=1.0,
                    sound="quack", fly=True, flat_beak=True),
    "peacock": dict(body=36, head=15, beak=("#8a8a8a", 11), fur="#1f4fbf", belly="#2a5fd0", wing="#2e8a64",
                    scale=1.3, sound="squawk", fly=False, fan=True, crest=True, tail_long=True),
    "owl":     dict(body=34, head=20, beak=("#e0a44a", 8), fur="#8b6b4a", belly="#dcc6a3", wing="#6b4f36", scale=1.1,
                    sound="hoot", fly=True, big_eyes=True),
    "pigeon":  dict(body=28, head=13, beak=("#5a5a5a", 9), fur="#8a93a6", belly="#b8bfd0", wing="#6c7488",
                    headc="#6f7a92", scale=1.0, sound="coo", fly=True),
    "kingfisher": dict(body=24, head=14, beak=("#1c1c1c", 20), fur="#1e8fd6", belly="#ff8c1a", wing="#136aa6",
                       scale=0.9, sound="chirp", fly=True),
    "myna":    dict(body=26, head=13, beak=("#f6c21e", 11), fur="#4a3b36", belly="#6b5a52", wing="#2b221f",
                    headc="#161212", scale=0.95, sound="chirp", fly=True),
    "flamingo": dict(body=36, head=13, beak=("#222222", 16), fur="#f6a0bf", belly="#fbc2d5", wing="#e5738f",
                     scale=1.4, sound="squawk", fly=True, leg_k=4.2, neck_k=3.2, bent_beak=True),
}
# 📏 real shoulder heights of adults (metres; Indian kinds where there is one: chital deer, desi cow, sloth bear,
# water buffalo, Asian elephant). In 3D stories the animals are made this big next to the people (a person ~1.6 m
# = ~300 units), never smaller than their cartoon size: engine/project.py, "real_size": false turns it off.
REAL_SHOULDER_M = {"bear": 0.85, "buffalo": 1.45, "camel": 1.85, "cat": 0.25, "cheetah": 0.8, "cow": 1.3, "deer": 0.9,
                   "dog": 0.55, "donkey": 1.05, "elephant": 2.6, "fox": 0.4, "giraffe": 3.0, "goat": 0.7, "hippo": 1.5,
                   "horse": 1.55, "leopard": 0.65, "lion": 1.15, "mouse": 0.05, "panda": 0.75, "pig": 0.8,
                   "rabbit": 0.2, "sheep": 0.75, "squirrel": 0.1, "tiger": 1.0, "wolf": 0.75, "zebra": 1.35}
UNITS_PER_M = 190.0


ALIASES = {"jaguar": "leopard", "panther": "leopard", "puppy": "dog", "kitten": "cat", "kitty": "cat", "bull": "cow",
           "bhains": "buffalo", "ox": "cow", "calf": "cow", "pony": "horse", "ass": "donkey", "mule": "donkey",
           "gadha": "donkey", "lamb": "sheep", "ram": "sheep", "bhed": "sheep", "oont": "camel", "unt": "camel",
           "bunny": "rabbit", "hare": "rabbit", "fawn": "deer", "stag": "deer", "jackal": "wolf", "rat": "mouse",
           "chuha": "mouse", "gilhari": "squirrel", "chipmunk": "squirrel", "hippopotamus": "hippo",
           "piglet": "pig", "chicken": "hen", "rooster": "hen", "cock": "hen", "dove": "pigeon", "kabutar": "pigeon",
           "birdie": "bird", "peafowl": "peacock", "mor": "peacock", "peahen": "peacock", "hawk": "eagle",
           "raven": "crow", "ullu": "owl", "maina": "myna", "mynah": "myna",
           "cub": "lion", "ape": "monkey", "gorilla": "monkey", "chimpanzee": "monkey", "langur": "monkey"}


CUSTOM = {}      # custom species loaded from assets/species (name -> description)
BUILTIN = set(QUADS) | set(BIRDS)
FROM_CODE = {}   # species made by a 3D animal code file: name -> code file


def canon(species):
    s = str(species or "human").lower().strip().replace(" ", "_")
    s = ALIASES.get(s, s)
    if s in QUADS or s in BIRDS or s in ("human", "person", "man", "woman", "boy", "girl", "monkey"):
        return "human" if s in ("person", "man", "woman", "boy", "girl") else s
    import difflib
    close = difflib.get_close_matches(s, list(QUADS) + list(BIRDS) + list(ALIASES) + ["monkey"], n=1, cutoff=0.72)
    if close:
        return ALIASES.get(close[0], close[0])
    return "human"


def kind_of(species):
    s = canon(species)
    if s in QUADS:
        return "quadruped"
    if s in BIRDS:
        return "bird"
    return "human"


def species_def(species, spec):
    s = canon(species)
    base = dict(QUADS.get(s) or BIRDS.get(s))
    base["name"] = s
    for k in ("fur", "belly", "mane", "wing"):
        if k in spec:
            base[k] = spec[k]
    if "color" in spec and "fur" not in spec:
        base["fur"] = spec["color"]
    for k in ("fur", "belly", "mane", "muzzle", "wing", "tail_tip", "headc"):
        if isinstance(base.get(k), str):
            base[k] = hex_to_rgb(base[k])
    if isinstance(base.get("beak"), tuple):
        base["beak"] = (hex_to_rgb(base["beak"][0]), base["beak"][1])
    if spec.get("gender") == "female" and s == "deer":
        base["antlers"] = False
    if s == "lion" and spec.get("gender") == "female":
        base["mane"] = None
    return base


# =========================================================================== four-legged rig
Q_KEYS = ("spine", "neck", "head", "jaw", "fl_t", "fl_s", "ff_t", "ff_s", "bl_t", "bl_s", "bf_t", "bf_s",
          "tail", "wag", "lift", "rot", "ear", "trunk")


def Q(**kw):
    p = {k: 0.0 for k in Q_KEYS}
    p.update(kw)
    return p


def qadd(p, **kw):
    q = dict(p)
    for k, v in kw.items():
        q[k] = q.get(k, 0.0) + v
    return q


Q_STAND = Q(neck=32, head=-4, fl_t=-2, fl_s=4, ff_t=4, ff_s=4, bl_t=10, bl_s=-16, bf_t=2, bf_s=-12, tail=18)
Q_SIT = Q(spine=34, neck=18, head=-4, fl_t=-34, fl_s=4, ff_t=-28, ff_s=2, bl_t=62, bl_s=-150, bf_t=58, bf_s=-146, tail=-10)
Q_LIE = Q(spine=0, neck=8, head=-2, fl_t=86, fl_s=4, ff_t=82, ff_s=6, bl_t=80, bl_s=-158, bf_t=76, bf_s=-156, tail=-5)
Q_CROUCH = qadd(Q_STAND, spine=-6, neck=-14, fl_t=30, fl_s=-60, ff_t=30, ff_s=-60, bl_t=45, bl_s=-80, bf_t=45, bf_s=-80, tail=5)
Q_STRETCH = Q(spine=8, neck=25, head=-2, fl_t=65, fl_s=10, ff_t=55, ff_s=10, bl_t=-45, bl_s=10, bf_t=-40, bf_s=8, tail=10)


def q_solve(p, sp, scale):
    L, T, S = sp["body"], sp["thigh"], sp["shin"]
    nl = int(sp.get("legs", 4))
    a = math.radians(p["spine"] + (38 if nl == 2 else 0))              # two legs: the body stands up over its hips
    hip = (0.0, 0.0)
    sh = (L * math.cos(a), L * math.sin(a))

    def leg(root, t1, t2):
        d1 = dirv(t1)
        k = (root[0] + d1[0] * T, root[1] + d1[1] * T)
        d2 = dirv(t1 + t2)
        return k, (k[0] + d2[0] * S, k[1] + d2[1] * S)

    ca, sa = math.cos(a), math.sin(a)
    drop = sp["girth"] * 0.12
    hr_ = (hip[0] + L * 0.1 * ca + drop * sa, hip[1] + L * 0.1 * sa - drop * ca)      # hip joint
    sr_ = (sh[0] - L * 0.08 * ca + drop * sa, sh[1] - L * 0.08 * sa - drop * ca)      # shoulder joint
    kfn, pfn = leg(sr_, p["fl_t"], p["fl_s"])
    kff, pff = leg(sr_, p["ff_t"], p["ff_s"])
    kbn, pbn = leg(hr_, p["bl_t"], p["bl_s"])
    kbf, pbf = leg(hr_, p["bf_t"], p["bf_s"])
    if nl == 2:                                                       # the front pair are small arms (they do not reach the ground)
        T2, S2 = T, S
        T, S = (T2 * 0.95, S2 * 0.9) if sp.get("arms") == "long" else (T2 * 0.55, S2 * 0.55)   # (a climber: long arms)
        kfn, pfn = leg(sr_, p["fl_t"] * 0.5 - 40, p["fl_s"] * 0.5 + 60)
        kff, pff = leg(sr_, p["ff_t"] * 0.5 - 30, p["ff_s"] * 0.5 + 60)
        T, S = T2, S2
    mids = {}
    if nl in (6, 8):                                                  # more pairs along the body: a ripple / tripod gait
        fr = (0.5,) if nl == 6 else (0.66, 0.33)
        for i, fx in enumerate(fr):
            root = (hr_[0] + (sr_[0] - hr_[0]) * fx, hr_[1] + (sr_[1] - hr_[1]) * fx)
            near_, far_ = (("ff", "fl") if i % 2 == 0 else ("bf", "bl"))
            mids[f"km{i}n"], mids[f"pm{i}n"] = leg(root, p[near_ + "_t"], p[near_ + "_s"])
            mids[f"km{i}f"], mids[f"pm{i}f"] = leg(root, p[far_ + "_t"], p[far_ + "_s"])
            mids[f"rm{i}"] = root
    na = math.radians(p["neck"] + p["spine"] * 0.5 + (sp.get("neck_angle", 32) - 32))
    nb = (sh[0] + sp["girth"] * 0.18, sh[1] + sp["girth"] * 0.22)
    ne = (nb[0] + sp["neck"] * math.cos(na), nb[1] + sp["neck"] * math.sin(na))
    head = (ne[0] + sp["head"] * 0.45 * math.cos(na), ne[1] + sp["head"] * 0.45 * math.sin(na))
    g2 = sp["girth"] / 2
    pts = dict(hip=hip, sh=sh, hj=hr_, sj=sr_, kfn=kfn, pfn=pfn, kff=kff, pff=pff, kbn=kbn, pbn=pbn, kbf=kbf, pbf=pbf,
               nb=nb, ne=ne, head=head, under_h=(hip[0], hip[1] - g2 * 0.9), under_s=(sh[0], sh[1] - g2 * 0.9), **mids)
    if abs(p.get("rot", 0)) > 1e-3:
        pts = {k: rotate(v, p["rot"]) for k, v in pts.items()}
    feet = (() if nl == 0 else ("pbn", "pbf", "kbn", "kbf") if nl == 2 else ("pfn", "pff", "pbn", "pbf", "kfn", "kff", "kbn", "kbf")) + \
        ("under_h", "under_s") + tuple(k for k in mids if k[0] in "pk")
    min_y = min(min(pts[k][1] for k in feet), pts["head"][1] - sp["head"])
    base = -min_y + p.get("lift", 0.0)
    # centre the animal on x: the middle of the body sits at x
    cx = (pts["hip"][0] + pts["sh"][0]) / 2
    return {k: ((v[0] - cx) * scale, (v[1] + base) * scale) for k, v in pts.items()}


def _qphase(t, ctx, stride, cadence):
    if ctx.get("speed", 0) > 1:
        return ctx.get("dist", 0.0) / stride
    return t * cadence


def q_idle(t, dur, ctx):
    b = math.sin(TAU * t / 3.2)
    return qadd(Q_STAND, neck=2 * b, head=2 * math.sin(TAU * t / 4.3), tail=8 * math.sin(TAU * t / 2.6),
                spine=0.6 * b), {}


def q_talk(t, dur, ctx):
    s = math.sin(TAU * 1.1 * t)
    return qadd(Q_STAND, neck=6 + 4 * s, head=4 * math.sin(TAU * 1.7 * t), tail=10 * s), {}


def q_walk(t, dur, ctx):
    sp = ctx["sp"]
    if sp.get("hop"):
        return q_hop(t, dur, ctx)
    p = _qphase(t, ctx, (sp["thigh"] + sp["shin"]) * 2.2 * ctx["scale"], 1.2)
    s1, c1 = math.sin(TAU * p), math.cos(TAU * p)
    s2, c2 = math.sin(TAU * p + math.pi), math.cos(TAU * p + math.pi)
    A = 20
    return Q(spine=1.5 * s1, neck=28 + 3 * math.sin(TAU * 2 * p), head=-4, tail=15 + 10 * s1,
             fl_t=-2 + A * s1, fl_s=4 - 38 * max(0, c1), bf_t=4 + A * s1, bf_s=-12 - 30 * max(0, c1),
             ff_t=-2 + A * s2, ff_s=4 - 38 * max(0, c2), bl_t=10 + A * s2, bl_s=-16 - 30 * max(0, c2)), {}


def q_run(t, dur, ctx):
    sp = ctx["sp"]
    if sp.get("hop"):
        return q_hop(t, dur, ctx, big=True)
    p = _qphase(t, ctx, (sp["thigh"] + sp["shin"]) * 3.6 * ctx["scale"], 2.0)
    w = TAU * p
    s = math.sin(w)
    return Q(spine=7 * s, neck=18 - 6 * s, head=-6, tail=5 + 6 * s,
             fl_t=8 + 36 * math.sin(w), fl_s=-5 - 35 * max(0, math.cos(w)),
             ff_t=8 + 36 * math.sin(w - 0.5), ff_s=-5 - 35 * max(0, math.cos(w - 0.5)),
             bl_t=10 + 34 * math.sin(w + math.pi), bl_s=-18 - 30 * max(0, math.cos(w + math.pi)),
             bf_t=10 + 34 * math.sin(w + math.pi - 0.5), bf_s=-18 - 30 * max(0, math.cos(w + math.pi - 0.5)),
             lift=14 * max(0.0, math.sin(w + 1.2))), {}


def q_hop(t, dur, ctx, big=False):
    sp = ctx["sp"]
    p = _qphase(t, ctx, 90 * ctx["scale"] * (1.6 if big else 1), 1.6)
    u = p % 1.0
    air = math.sin(math.pi * u)
    pose = blend(Q_CROUCH, Q_STRETCH, air)
    pose["lift"] = (60 if big else 35) * air
    pose["neck"] = 30
    return pose, {}


def q_sit(t, dur, ctx):
    return qadd(Q_SIT, neck=2 * math.sin(TAU * t / 3.4), tail=6 * math.sin(TAU * t / 2.5)), {"seat": False}


def q_lie(t, dur, ctx):
    return qadd(Q_LIE, spine=0.5 * math.sin(TAU * t / 3.2)), {}


def q_sleep(t, dur, ctx):
    return qadd(Q_LIE, neck=-6, head=-8, spine=0.7 * math.sin(TAU * t / 3.2), tail=-10), {"face": "sleeping", "zzz": True}


def q_jump(t, dur, ctx):
    u = t / max(dur, 0.1)
    pose = keyframes(u, [(0, Q_STAND), (0.2, Q_CROUCH), (0.35, Q_STRETCH), (0.7, Q_STRETCH), (0.85, Q_CROUCH), (1, Q_STAND)])
    h = float(ctx.get("params", {}).get("height", 90))
    if 0.2 < u < 0.85:
        pose["lift"] = pose.get("lift", 0) + h * math.sin(math.pi * (u - 0.2) / 0.65)
    return pose, {}


def q_roar(t, dur, ctx):
    u = clamp(t / 0.35, 0, 1)
    k = smoothstep(u) * (1 - smoothstep((t - dur + 0.3) / 0.3))
    pose = blend(Q_STAND, qadd(Q_STAND, neck=22, head=22, jaw=1.0, spine=4, tail=40, trunk=1.0,
                               fl_t=-6, ff_t=-2), k)
    pose["jaw"] = k * (0.8 + 0.2 * math.sin(TAU * 9 * t))
    return pose, {"face": "angry" if ctx["sp"].get("sound") in ("roar", "growl", "howl") else "happy"}


def q_eat(t, dur, ctx):
    chew = math.sin(TAU * 3 * t)
    return qadd(Q_STAND, neck=-58, head=-32, jaw=0.3 + 0.3 * chew, fl_t=6, ff_t=8, tail=10 * math.sin(TAU * t)), {}


def q_happy(t, dur, ctx):
    b = abs(math.sin(TAU * 1.4 * t))
    return qadd(Q_STAND, neck=10, head=6, lift=14 * b, wag=1.0, tail=45, fl_t=-10 * b, ff_t=-6 * b), {"face": "happy"}


def q_wag(t, dur, ctx):
    return qadd(Q_STAND, neck=6, head=4, wag=1.0, tail=48), {"face": "happy"}


def q_sad(t, dur, ctx):
    return qadd(Q_STAND, neck=-6, head=-22, tail=-55, ear=-1, spine=-2), {"face": "sad"}


def q_cry(t, dur, ctx):
    p, _ = q_sad(t, dur, ctx)
    return p, {"face": "crying", "tears": True}


def q_scared(t, dur, ctx):
    s = math.sin(TAU * 11 * t)
    return qadd(Q_CROUCH, spine=-4, neck=4, head=2 + 2 * s, tail=-70, ear=-1), {"face": "scared"}


def q_angry(t, dur, ctx):
    return qadd(Q_CROUCH, neck=10, head=-4, tail=55, jaw=0.35 + 0.1 * math.sin(TAU * 6 * t), fl_t=-20, ff_t=-18,
                fl_s=30, ff_s=30), {"face": "angry"}


def q_surprised(t, dur, ctx):
    hop = 20 * math.sin(math.pi * clamp(t / 0.35, 0, 1))
    return qadd(Q_STAND, neck=16, head=10, lift=hop, tail=50, ear=1), {"face": "surprised"}


def q_look(t, dur, ctx):
    u = t / max(dur, 0.1)
    return qadd(Q_STAND, neck=14, head=6), {"flip": 0.3 < u < 0.7}


def q_pick(t, dur, ctx):
    u = t / max(dur, 0.1)
    down = qadd(Q_STAND, neck=-60, head=-35, fl_t=8, ff_t=10)
    return keyframes(u, [(0, Q_STAND), (0.45, down), (0.55, down), (1, Q_STAND)]), {"attach": 0.5}


def q_drop(t, dur, ctx):
    p, _ = q_pick(t, dur, ctx)
    return p, {"detach": 0.5}


def q_trunk(t, dur, ctx):
    return qadd(Q_STAND, neck=10, head=10, trunk=1.0, jaw=0.2), {"face": "happy"}


def _appear(fn, fade_in):
    def f(t, dur, ctx):
        p, _ = fn(t, dur, ctx)
        k = clamp(t / max(dur, 0.01), 0, 1)
        return p, {"alpha": k if fade_in else 1 - k}
    return f


Q_ACTIONS = {
    "idle": ActionSpec(q_idle, 1.0, persistent=True),
    "stand": ActionSpec(q_idle, 0.6, persistent=True, blend_in=0.6),
    "talk": ActionSpec(q_talk, 2.0),
    "walk": ActionSpec(q_walk, 0, moving=True, blend_in=0.25),
    "run": ActionSpec(q_run, 0, moving=True, blend_in=0.2),
    "hop": ActionSpec(q_hop, 0, moving=True, blend_in=0.2),
    "jump": ActionSpec(q_jump, 1.1, blend_in=0.1, oneshot=True),
    "pounce": ActionSpec(q_jump, 1.0, blend_in=0.1, oneshot=True),
    "sit": ActionSpec(q_sit, 0.8, persistent=True, blend_in=0.7),
    "lie": ActionSpec(q_lie, 1.0, persistent=True, blend_in=0.8),
    "sleep": ActionSpec(q_sleep, 1.2, persistent=True, blend_in=1.0),
    "roar": ActionSpec(q_roar, 1.8, blend_in=0.2),
    "eat": ActionSpec(q_eat, 3.0, blend_in=0.5),
    "happy": ActionSpec(q_happy, 2.0),
    "wag": ActionSpec(q_wag, 2.0),
    "sad": ActionSpec(q_sad, 2.0, persistent=True, blend_in=0.7),
    "cry": ActionSpec(q_cry, 2.5, blend_in=0.6),
    "scared": ActionSpec(q_scared, 2.0, blend_in=0.15),
    "angry": ActionSpec(q_angry, 2.0, blend_in=0.3),
    "surprised": ActionSpec(q_surprised, 1.3, blend_in=0.12),
    "look_around": ActionSpec(q_look, 2.0),
    "pick": ActionSpec(q_pick, 1.4, oneshot=True),
    "drop": ActionSpec(q_drop, 1.4, oneshot=True),
    "trunk": ActionSpec(q_trunk, 2.0, blend_in=0.4),
    "turn": ActionSpec(q_idle, 0.3, blend_in=0.1),
    "appear": ActionSpec(_appear(q_idle, True), 0.6, persistent=True, blend_in=0.0),
    "disappear": ActionSpec(_appear(q_idle, False), 0.6, persistent=True, blend_in=0.0),
}
Q_MAP = {"wave": "wag", "laugh": "happy", "celebrate": "happy", "dance": "happy", "clap": "happy", "hug": "wag",
         "point": "look_around", "think": "idle", "shrug": "idle", "nod": "talk", "bow": "eat", "kick": "pounce",
         "fall": "lie", "give": "drop", "graze": "eat", "chew": "eat", "bark": "roar", "meow": "roar", "moo": "roar",
         "neigh": "roar", "howl": "roar", "growl": "roar", "trumpet": "roar", "bleat": "roar", "oink": "roar",
         "call": "roar", "sound": "roar", "speak": "talk", "attack": "pounce", "leap": "pounce", "gallop": "run",
         "trot": "walk", "crawl": "walk", "rest": "lie", "lay": "lie", "lie_down": "lie", "sniff": "eat",
         "drink": "eat", "play": "happy", "excited": "happy", "shake_trunk": "trunk", "spray": "trunk",
         "fly": "jump", "peck": "eat", "sing": "roar"}


# =========================================================================== birds
B_KEYS = ("body", "head", "wing", "leg", "lift", "jaw", "tail", "rot")


def B(**kw):
    p = {k: 0.0 for k in B_KEYS}
    p.update(kw)
    return p


B_STAND = B(body=-12, head=0, wing=0, leg=0, tail=10)


def b_idle(t, dur, ctx):
    peck = max(0, math.sin(TAU * t / 2.7)) ** 8
    return B(body=-12 + 20 * peck, head=-40 * peck, tail=10 + 5 * math.sin(TAU * t)), {}


def b_talk(t, dur, ctx):
    return B(body=-14, head=6 * math.sin(TAU * 1.5 * t), tail=12), {}


def b_walk(t, dur, ctx):
    p = _qphase(t, ctx, 36 * ctx["scale"], 2.5)
    u = p % 1.0
    return B(body=-10, lift=12 * math.sin(math.pi * u), leg=0.3 * math.sin(math.pi * u), tail=12), {}


def b_fly(t, dur, ctx):
    sp = ctx["sp"]
    h = float(ctx.get("params", {}).get("height", 230))
    u = t / max(dur, 0.1)
    rise = smoothstep(u / 0.2) * (1 - smoothstep((u - 0.8) / 0.2)) if sp.get("fly", True) else 0.12
    flap = math.sin(TAU * (6 if sp["body"] < 32 else 3.5) * t)
    return B(body=6 * rise - 10 * (1 - rise), head=-6 * rise, wing=0.5 + 0.5 * flap if rise > 0.02 else 0,
             leg=1.0 * rise, lift=h * rise + 8 * math.sin(TAU * 0.8 * t) * rise, tail=0), {}


def b_hover(t, dur, ctx):
    h = float(ctx.get("params", {}).get("height", 230))
    flap = math.sin(TAU * 6 * t)
    return B(body=4, wing=0.5 + 0.5 * flap, leg=1, lift=h + 10 * math.sin(TAU * 0.7 * t)), {}


def b_sit(t, dur, ctx):
    return B(body=-6, leg=0.8, tail=8), {}


def b_sleep(t, dur, ctx):
    return B(body=-4, head=-20, leg=0.8, tail=5), {"face": "sleeping", "zzz": True}


def b_sing(t, dur, ctx):
    return B(body=-25, head=25, jaw=0.5 + 0.5 * abs(math.sin(TAU * 4 * t)), tail=15), {"face": "happy"}


def b_peck(t, dur, ctx):
    peck = max(0, math.sin(TAU * 2.2 * t)) ** 3
    return B(body=-10 + 35 * peck, head=-50 * peck, tail=15), {}


def b_happy(t, dur, ctx):
    b = abs(math.sin(TAU * 1.6 * t))
    p = B(body=-15, lift=16 * b, wing=0.6 * b, tail=15)
    p["display"] = smoothstep(t / 0.5) * (1 - smoothstep((t - dur + 0.5) / 0.5))   # (a peacock opens its fan)
    return p, {"face": "happy"}


def b_dance(t, dur, ctx):
    """a display dance: the fan (peacock) or the wings open, the body bobs and turns side to side, little steps"""
    k = smoothstep(t / 0.6) * (1 - smoothstep((t - dur + 0.6) / 0.6))
    s = math.sin(TAU * 1.2 * t)
    p = B(body=-8 + 6 * s, head=-6 * s, wing=0.35 * k, lift=5 * abs(math.sin(TAU * 2.4 * t)), tail=20, rot=8 * s * k)
    p["display"] = k
    return p, {"face": "happy"}


def b_scared(t, dur, ctx):
    return B(body=-20 + 3 * math.sin(TAU * 12 * t), wing=0.3, tail=20), {"face": "scared"}


def b_sad(t, dur, ctx):
    return B(body=6, head=-25, tail=-5), {"face": "sad"}


B_ACTIONS = {
    "idle": ActionSpec(b_idle, 1.0, persistent=True),
    "stand": ActionSpec(b_idle, 0.5, persistent=True),
    "talk": ActionSpec(b_talk, 2.0),
    "walk": ActionSpec(b_walk, 0, moving=True),
    "run": ActionSpec(b_walk, 0, moving=True),
    "hop": ActionSpec(b_walk, 0, moving=True),
    "fly": ActionSpec(b_fly, 0, moving=True, blend_in=0.15),
    "hover": ActionSpec(b_hover, 2.0, persistent=True, blend_in=0.5),
    "sit": ActionSpec(b_sit, 0.6, persistent=True),
    "sleep": ActionSpec(b_sleep, 1.0, persistent=True, blend_in=0.8),
    "sing": ActionSpec(b_sing, 2.0),
    "peck": ActionSpec(b_peck, 2.0),
    "happy": ActionSpec(b_happy, 2.0),
    "dance": ActionSpec(b_dance, 4.0, blend_in=0.3),
    "scared": ActionSpec(b_scared, 1.5),
    "sad": ActionSpec(b_sad, 2.0, persistent=True),
    "turn": ActionSpec(b_idle, 0.3),
    "appear": ActionSpec(_appear(b_idle, True), 0.6, persistent=True, blend_in=0.0),
    "disappear": ActionSpec(_appear(b_idle, False), 0.6, persistent=True, blend_in=0.0),
}
B_MAP = {"eat": "peck", "roar": "sing", "call": "sing", "chirp": "sing", "caw": "sing", "squawk": "sing",
         "cluck": "sing", "quack": "sing", "jump": "happy", "celebrate": "happy", "display": "dance", "show_off": "dance",
         "open_fan": "dance", "fan": "dance", "nachna": "dance", "laugh": "happy",
         "wave": "happy", "clap": "happy", "lie": "sit", "rest": "sit", "perch": "sit", "cry": "sad",
         "angry": "scared", "surprised": "happy", "look_around": "peck", "pick": "peck", "drop": "peck",
         "think": "idle", "point": "idle", "wag": "happy", "flap": "happy", "land": "idle", "glide": "fly",
         "fall": "sit", "hug": "idle", "pounce": "fly"}

WALK_SPEED_BIRD, FLY_SPEED = 90, 420


def actions_for(cdef):
    if cdef.kind == "quadruped":
        return Q_ACTIONS
    if cdef.kind == "bird":
        return B_ACTIONS
    return None


def resolve_animal_action(cdef, name):
    from .poses import resolve_action
    key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    table = actions_for(cdef)
    own = (cdef.animal or {}).get("actions") or {}         # the species' own words: {"attack": "pounce", ...}
    if isinstance(own, dict) and key in own and str(own[key]) in table:
        return str(own[key]), None
    mapping = Q_MAP if cdef.kind == "quadruped" else B_MAP
    if key in table:
        return key, None
    if key in mapping and mapping[key] in table:
        return mapping[key], None
    human, msg = resolve_action(key)
    if human in table:
        return human, None
    if human in mapping and mapping[human] in table:
        return mapping[human], None
    return "idle", f"{cdef.name} ({cdef.species}) can't '{name}', using 'idle'"


def speed_of(cdef, action):
    a = cdef.animal
    if cdef.kind == "bird":
        return FLY_SPEED if action == "fly" else WALK_SPEED_BIRD
    return {"walk": a["walk"], "hop": a["walk"] * 1.2, "run": a["run"]}.get(action, a["walk"])


def animal_ctx(cdef):
    return {"sp": cdef.animal, "scale": cdef.scale}


# =========================================================================== drawing helpers
def _stroke(ctx, pts, w, col, alpha, outline=None, ow=0.0):
    if outline is not None:
        ctx.set_source_rgba(*outline, alpha)
        ctx.set_line_width(w + 2 * ow)
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.stroke()
    if isinstance(col, tuple):
        ctx.set_source_rgba(*col, alpha)
    else:
        ctx.set_source(col)
    ctx.set_line_width(w)
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.stroke()


def _ellipse(ctx, cx, cy, rx, ry, ang=0.0):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(ang)
    ctx.scale(max(rx, 0.01), max(ry, 0.01))
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()


def _fill(ctx, col, alpha, outline=None, ow=0.0):
    ctx.set_source_rgba(*col, alpha)
    if outline is not None:
        ctx.fill_preserve()
        ctx.set_source_rgba(*outline, alpha)
        ctx.set_line_width(ow)
        ctx.stroke()
    else:
        ctx.fill()


def _capsule(ctx, a, b, w):
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    r = w / 2
    ctx.new_path()
    ctx.arc(b[0], b[1], r, ang - math.pi / 2, ang + math.pi / 2)
    ctx.arc(a[0], a[1], r, ang + math.pi / 2, ang + 3 * math.pi / 2)
    ctx.close_path()


def draw_animal(ctx, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink, y=0.0, shadow=True):
    extras = extras or {}
    if cdef.kind == "bird":
        return _draw_bird(ctx, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink, y, shadow)
    return _draw_quad(ctx, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink, y, shadow)


def _draw_quad(ctx, c, pose, x, facing, face, mouth, t, extras, alpha, blink, y, shadow):
    from .character import draw_shadow
    sp = c.animal
    s = c.scale
    J = q_solve(pose, sp, s)
    f = -1.0 if facing < 0 else 1.0

    def W(p):
        return (x + f * p[0], p[1] + y)

    fur, belly = sp["fur"], sp["belly"]
    OW = 2.6 * s
    fo = darker(fur, 0.58)
    leg_w = sp.get("leg_w", sp["girth"] * 0.34) * s
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    if shadow:
        low = min(J["pfn"][1], J["pbn"][1], J["under_h"][1])
        draw_shadow(ctx, x, max(0.0, low / max(s, 0.1) - 2), (sp["body"] * 0.7 + 30) * s, alpha, y)

    leg_base = _rgb(sp["leg_color"]) if sp.get("leg_color") else (
        (0.1, 0.1, 0.1) if sp.get("pattern") == "panda" else fur)

    nl = int(sp.get("legs", 4))
    mids = sorted({k[2] for k in J if k.startswith("rm")})

    def legdraw(root, knee, paw, dark, arm=False):
        k = 0.8 if dark else 1.0
        col = tuple(v * k for v in leg_base)
        lw = leg_w * (0.55 if arm else 0.6 if nl >= 6 else 1.0)          # (many legs: each one thinner)
        _stroke(ctx, [W(root), W(knee), W(paw)], lw, col, alpha, darker(col, 0.58), OW)
        if arm:
            ctx.arc(W(paw)[0], W(paw)[1], lw * 0.6, 0, TAU)
            _fill(ctx, col, alpha, darker(col, 0.58), OW * 0.7)
            return
        pw = W(paw)
        if sp.get("hooves"):
            _stroke(ctx, [pw, (pw[0] + f * 3 * s, pw[1])], leg_w * 0.95, (0.2, 0.17, 0.15), alpha)
        else:
            ctx.arc(pw[0] + f * leg_w * 0.2, pw[1] + leg_w * 0.2, leg_w * 0.55, 0, TAU)
            _fill(ctx, col, alpha, darker(col, 0.58), OW * 0.8)

    # far legs (none for a slider; a two-legged walker's front pair are arms, drawn later)
    if nl > 0:
        if nl != 2:
            legdraw(J["sj"], J["kff"], J["pff"], True)
        for i in mids:
            legdraw(J["rm" + i], J["km" + i + "f"], J["pm" + i + "f"], True)
        legdraw(J["hj"], J["kbf"], J["pbf"], True)

    # tail (behind body)
    _tail(ctx, c, sp, J, W, f, t, pose, alpha, OW, s)

    # far ear for elephants goes behind; body
    hip, sh = W(J["hip"]), W(J["sh"])
    gw = sp["girth"] * s
    _capsule(ctx, hip, sh, gw)
    mid = ((hip[0] + sh[0]) / 2, (hip[1] + sh[1]) / 2)
    g = cairo.LinearGradient(mid[0], mid[1] - gw / 2, mid[0], mid[1] + gw / 2)
    g.add_color_stop_rgba(0, *darker(fur, 0.85), alpha)
    g.add_color_stop_rgba(0.6, *fur, alpha)
    g.add_color_stop_rgba(1, *lighter(fur, 0.12), alpha)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    ctx.new_path()
    # belly + patterns clipped to the body
    _ellipse(ctx, mid[0], mid[1] - gw * 0.42, abs(sh[0] - hip[0]) * 0.55 + gw * 0.2, gw * 0.32)
    ctx.set_source_rgba(*belly, alpha)
    ctx.fill()
    _pattern(ctx, c, sp, hip, sh, gw, f, alpha, s)
    ctx.restore()
    _capsule(ctx, hip, sh, gw)
    ctx.set_source_rgba(*fo, alpha)
    ctx.set_line_width(OW)
    ctx.stroke()
    if sp.get("hump"):
        for k, fx in enumerate((0.38, 0.62)[: int(sp.get("hump", 1))] if sp.get("hump") in (2, "2", "double") else (0.5,)):
            hx_ = hip[0] + (sh[0] - hip[0]) * fx
            hy_ = hip[1] + (sh[1] - hip[1]) * fx + gw * 0.42
            _ellipse(ctx, hx_, hy_, gw * 0.42, gw * 0.42)
            _fill(ctx, fur, alpha)
            ctx.arc(hx_, hy_, gw * 0.42, math.radians(10), math.radians(170))
            ctx.set_source_rgba(*fo, alpha)
            ctx.set_line_width(OW)
            ctx.stroke()
    if sp.get("udder"):
        u = (hip[0] + (sh[0] - hip[0]) * 0.3, hip[1] - gw * 0.45)
        _ellipse(ctx, u[0], u[1], 14 * s, 9 * s)
        _fill(ctx, (0.96, 0.7, 0.72), alpha, darker((0.96, 0.7, 0.72), 0.7), OW * 0.7)

    # near legs + rounded haunch / shoulder so legs grow out of the body
    if nl > 0:
        legdraw(J["hj"], J["kbn"], J["pbn"], False)
        for i in mids:
            legdraw(J["rm" + i], J["km" + i + "n"], J["pm" + i + "n"], False)
        if nl == 2:
            legdraw(J["sj"], J["kff"], J["pff"], True, arm=True)
        legdraw(J["sj"], J["kfn"], J["pfn"], False, arm=nl == 2)
    for key, k in ((("hj", 0.46), ("sj", 0.38)) if nl in (2, 4) else ()):
        jx, jy = W(J[key])
        _ellipse(ctx, jx, jy + gw * 0.08, gw * k, gw * k * 0.95)
        _fill(ctx, fur, alpha)
        ctx.save()
        ctx.arc(jx, jy + gw * 0.08, gw * k, math.radians(200), math.radians(340))
        ctx.set_source_rgba(*fo, alpha)
        ctx.set_line_width(OW)
        ctx.stroke()
        ctx.restore()

    # neck + mane
    nb, ne = W(J["nb"]), W(J["ne"])
    if sp["neck"] > 8:
        _stroke(ctx, [nb, ne], sp["neck_w"] * s, fur, alpha, fo, OW)
    if sp["name"] in ("horse", "zebra", "donkey") and sp.get("mane"):
        ctx.set_source_rgba(*sp["mane"], alpha)
        ctx.set_line_width(12 * s)
        ctx.move_to(nb[0] - f * 8 * s, nb[1] + 14 * s)
        ctx.curve_to(nb[0] + f * 2 * s, nb[1] + 40 * s, ne[0] - f * 20 * s, ne[1] + 10 * s, ne[0] - f * 6 * s, ne[1] + 16 * s)
        ctx.stroke()

    # head
    hx, hy = W(J["head"])
    hr = sp["head"] * s
    ang = math.radians(pose.get("head", 0) + pose.get("neck", 0) * 0.25 + pose.get("rot", 0) * 0.5)
    if sp.get("mane"):
        if sp["name"] == "lion":
            ctx.save()
            ctx.translate(hx - f * hr * 0.25, hy)
            n = 18
            ctx.move_to(hr * 1.75, 0)
            for k in range(1, n * 2 + 1):
                a = math.pi * k / n
                rr = hr * (1.75 if k % 2 == 0 else 1.45)
                ctx.line_to(rr * math.cos(a), rr * math.sin(a))
            ctx.close_path()
            ctx.restore()
            _fill(ctx, sp["mane"], alpha, darker(sp["mane"], 0.6), OW)
    ctx.save()
    ctx.translate(hx, hy)
    ctx.scale(f, 1)
    ctx.rotate(ang)
    mouth_pt = _quad_head(ctx, c, sp, hr, face, max(mouth, pose.get("jaw", 0)), blink, alpha, OW, t, pose, s)
    ctx.restore()
    mx = hx + f * (mouth_pt[0] * math.cos(ang) - mouth_pt[1] * math.sin(ang))
    my = hy + (mouth_pt[0] * math.sin(ang) + mouth_pt[1] * math.cos(ang))

    if extras.get("tears"):
        ctx.set_source_rgba(0.35, 0.68, 1.0, alpha * 0.9)
        for k in range(3):
            ph = (t * 1.6 + k / 3.0) % 1.0
            ctx.arc(hx + f * hr * 0.55, hy - ph * 50 * s, (4.4 - 2 * ph) * s, 0, TAU)
            ctx.fill()
    if extras.get("zzz"):
        _zzz(ctx, hx + f * hr * 0.4, hy + hr, t, s, alpha, f)
    return {"hand": (mx, my), "head": (hx, hy), "hip": W(J["hip"]), "head_r": hr, "mouth": (mx, my)}


def _zzz(ctx, x, y, t, s, alpha, f):
    for k in range(3):
        ph = (t * 0.45 + k / 3.0) % 1.0
        ctx.save()
        ctx.translate(x + f * 40 * ph * s, y + 90 * ph * s)
        ctx.scale(1, -1)
        ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size((20 + 22 * ph) * max(s, 0.6))
        ctx.set_source_rgba(0.25, 0.3, 0.5, alpha * (1 - ph))
        ctx.move_to(0, 0)
        ctx.show_text("Z")
        ctx.restore()


def _pattern(ctx, c, sp, hip, sh, gw, f, alpha, s):
    pat = sp.get("pattern")
    if pat == "giraffe":
        ctx.set_source_rgba(*_rgb(sp.get("spot_color", "#8b4a1c")), alpha)
        for k in range(12):
            fx = 0.08 + 0.075 * k
            cx = hip[0] + (sh[0] - hip[0]) * fx
            cy = hip[1] + (sh[1] - hip[1]) * fx + gw * (0.05 if k % 2 else 0.3)
            ctx.save()
            ctx.translate(cx, cy)
            ctx.rotate(0.4 * k)
            ctx.scale(10 * s, 8 * s)
            ctx.move_to(1, 0)
            for a in range(1, 6):
                ctx.line_to(math.cos(a * 1.25) * (1 + 0.2 * (a % 2)), math.sin(a * 1.25) * (1 + 0.2 * (a % 2)))
            ctx.close_path()
            ctx.restore()
            ctx.fill()
        return
    if pat in ("stripes", "stripes_light", "zebra"):
        col = (0.12, 0.08, 0.06) if pat != "stripes_light" else darker(sp["fur"], 0.7)
        if sp.get("stripe_color"):
            col = _rgb(sp["stripe_color"])
        ctx.set_source_rgba(*col, alpha * (0.95 if pat == "stripes" else 0.7))
        n = 11 if pat == "zebra" else 7
        for k in range(n):
            fx = 0.12 + k * 0.76 / (n - 1)
            px = hip[0] + (sh[0] - hip[0]) * fx
            py = hip[1] + (sh[1] - hip[1]) * fx
            ctx.move_to(px - 6 * s, py + gw * 0.55)
            ctx.curve_to(px + 4 * s, py + gw * 0.2, px - 4 * s, py - gw * 0.05, px + 3 * s, py - gw * 0.25)
            ctx.line_to(px + 9 * s, py - gw * 0.2)
            ctx.curve_to(px + 3 * s, py, px + 10 * s, py + gw * 0.25, px + 5 * s, py + gw * 0.55)
            ctx.close_path()
            ctx.fill()
    elif pat == "patches":
        ctx.set_source_rgba(0.12, 0.12, 0.13, alpha)
        for fx, fy, rx, ry in ((0.25, 0.15, 0.2, 0.3), (0.62, 0.25, 0.14, 0.24), (0.45, -0.2, 0.12, 0.16), (0.85, -0.05, 0.1, 0.18)):
            cx = hip[0] + (sh[0] - hip[0]) * fx
            cy = hip[1] + (sh[1] - hip[1]) * fx + gw * fy
            _ellipse(ctx, cx, cy, abs(sh[0] - hip[0]) * rx, gw * ry, 0.3)
            ctx.fill()
    elif pat == "leopard":                                   # dark rosettes all over
        col = _rgb(sp.get("spot_color", "#2a1a10"))
        rr = [(0.12 + 0.07 * k, (0.55, 0.15, -0.25, 0.35, -0.05, 0.5)[k % 6]) for k in range(12)]
        for fx, fy in rr:
            cx = hip[0] + (sh[0] - hip[0]) * fx
            cy = hip[1] + (sh[1] - hip[1]) * fx + gw * fy * 0.8
            ctx.set_source_rgba(*col, alpha * 0.9)
            ctx.arc(cx, cy, 4.5 * s, 0, TAU)
            ctx.fill()
            ctx.arc(cx + 5 * s, cy + 3 * s, 2.2 * s, 0, TAU)
            ctx.fill()
    elif pat == "wool":                                      # fluffy curls
        ctx.set_line_width(2 * s)
        for k in range(16):
            fx = 0.06 + 0.058 * k
            cx = hip[0] + (sh[0] - hip[0]) * fx
            for fy in (-0.35, 0.05, 0.42):
                cy = hip[1] + (sh[1] - hip[1]) * fx + gw * fy
                ctx.arc(cx + (k % 2) * 3 * s, cy, 7 * s, 0, TAU)
                ctx.set_source_rgba(1, 1, 1, alpha * 0.9)
                ctx.fill_preserve()
                ctx.set_source_rgba(0.8, 0.77, 0.7, alpha * 0.8)
                ctx.stroke()
    elif pat == "spots":
        ctx.set_source_rgba(1, 1, 1, alpha * 0.85)
        for k in range(9):
            fx = 0.15 + 0.08 * k
            cx = hip[0] + (sh[0] - hip[0]) * fx
            cy = hip[1] + (sh[1] - hip[1]) * fx + gw * (0.12 if k % 2 else 0.28)
            ctx.arc(cx, cy, 4 * s, 0, TAU)
            ctx.fill()


def _rgb(c):
    return hex_to_rgb(c) if isinstance(c, str) else tuple(c)


def _tail(ctx, c, sp, J, W, f, t, pose, alpha, OW, s):
    kind = sp.get("tail")
    fur = sp["fur"]
    root = W((J["hip"][0] - sp["girth"] * 0.35 * s, J["hip"][1] + sp["girth"] * 0.15 * s))
    base_ang = math.radians(pose.get("tail", 15))
    wag = pose.get("wag", 0) * math.sin(TAU * 5 * t) * 0.6
    sway = 0.15 * math.sin(TAU * t / 2.3)

    def chain(n, seg, curl):
        pts = [root]
        a = base_ang + wag + sway
        for k in range(n):
            a += curl
            lx, ly = pts[-1]
            pts.append((lx - f * math.cos(a) * seg * s, ly + math.sin(a) * seg * s))
        return pts

    if kind == "long":
        pts = chain(7, 14, 0.12)
        _stroke(ctx, pts, 9 * s, fur, alpha, darker(fur, 0.58), OW)
        ctx.set_source_rgba(0.12, 0.08, 0.06, alpha)
        for p in pts[2::2]:
            ctx.arc(p[0], p[1], 4.8 * s, 0, TAU)
            ctx.fill()
    elif kind in ("tuft", "tuft_thin"):
        pts = chain(6, 13 if kind == "tuft" else 10, -0.18)
        _stroke(ctx, pts, (6 if kind == "tuft" else 4) * s, fur, alpha, darker(fur, 0.58), OW * 0.8)
        e = pts[-1]
        ctx.arc(e[0], e[1], 8 * s, 0, TAU)
        _fill(ctx, sp.get("mane") or darker(fur, 0.6), alpha)
    elif kind == "long_up":
        pts = chain(7, 12, 0.22)
        _stroke(ctx, pts, 8 * s, fur, alpha, darker(fur, 0.58), OW)
    elif kind == "curve":
        pts = chain(5, 11, 0.28)
        _stroke(ctx, pts, 10 * s, fur, alpha, darker(fur, 0.58), OW)
    elif kind == "bushy":
        pts = chain(5, 16, 0.1)
        for k in range(len(pts) - 1):
            w = (10 + 14 * math.sin(math.pi * (k + 0.5) / (len(pts) - 1))) * s
            col = sp.get("tail_tip") if (sp.get("tail_tip") and k == len(pts) - 2) else fur
            _stroke(ctx, [pts[k], pts[k + 1]], w, col, alpha, darker(fur, 0.58), OW)
    elif kind == "long_hair":
        pts = chain(6, 16, -0.2)
        _stroke(ctx, pts, 16 * s, sp.get("mane") or darker(fur, 0.6), alpha)
    elif kind == "puff":
        ctx.arc(root[0] - f * 4 * s, root[1], 11 * s, 0, TAU)
        _fill(ctx, (1, 1, 1), alpha, (0.75, 0.75, 0.75), OW * 0.7)
    elif kind == "short_up":
        pts = chain(2, 10, 0.4)
        _stroke(ctx, pts, 9 * s, fur, alpha, darker(fur, 0.58), OW)
    elif kind == "curly":
        ctx.set_source_rgba(*darker(fur, 0.8), alpha)
        ctx.set_line_width(4 * s)
        for k in range(20):
            a = k * 0.6
            rr = 3 + k * 0.5
            px, py = root[0] - f * (6 + rr * math.cos(a)) * s, root[1] + (4 + rr * math.sin(a)) * s
            (ctx.move_to if k == 0 else ctx.line_to)(px, py)
        ctx.stroke()


def _quad_head(ctx, c, sp, hr, face, mouth, blink, alpha, ow, t, pose, s):
    """Draw the head in a local frame (+x = nose direction, y up). Returns the mouth point."""
    fur = sp["fur"]
    fo = darker(fur, 0.58)
    name = sp["name"]
    ear = pose.get("ear", 0)
    # ears behind
    ek = sp.get("ears")
    ctx.set_line_width(ow)
    if ek == "long":
        for dx, k in ((-0.25, 0.85), (0.1, 1.0)):
            _ellipse(ctx, hr * dx, hr * (1.35 + 0.1 * ear), hr * 0.28 * k, hr * 0.95, -0.15 + 0.3 * dx - 0.3 * ear)
            _fill(ctx, fur, alpha, fo, ow)
            _ellipse(ctx, hr * dx, hr * (1.35 + 0.1 * ear), hr * 0.13 * k, hr * 0.7, -0.15 + 0.3 * dx - 0.3 * ear)
            _fill(ctx, (0.95, 0.7, 0.75), alpha)
    elif ek in ("pointy", "pointy_tall"):
        hgt = 0.9 if ek == "pointy_tall" else 0.6
        for dx in (-0.45, 0.1):
            ctx.move_to(hr * (dx - 0.25), hr * 0.6)
            ctx.line_to(hr * (dx - 0.05 - 0.2 * ear), hr * (0.6 + hgt + 0.2 * ear))
            ctx.line_to(hr * (dx + 0.25), hr * 0.7)
            ctx.close_path()
            _fill(ctx, fur, alpha, fo, ow)
    elif ek == "round":
        ear_col = (0.1, 0.1, 0.1) if sp.get("pattern") == "panda" else fur
        for dx in (-0.55, 0.05):
            ctx.arc(hr * dx, hr * 0.78, hr * 0.28, 0, TAU)
            _fill(ctx, ear_col, alpha, fo, ow)
            ctx.arc(hr * dx, hr * 0.78, hr * 0.14, 0, TAU)
            _fill(ctx, darker(fur, 0.6), alpha)
    elif ek == "side":
        _ellipse(ctx, -hr * 0.6, hr * 0.35, hr * 0.45, hr * 0.18, 0.4 - 0.4 * ear)
        _fill(ctx, fur, alpha, fo, ow)

    # skull
    ctx.arc(0, 0, hr, 0, TAU)
    g = cairo.RadialGradient(hr * 0.3, hr * 0.3, hr * 0.1, 0, 0, hr * 1.05)
    g.add_color_stop_rgba(0, *lighter(fur, 0.12), alpha)
    g.add_color_stop_rgba(1, *darker(fur, 0.9), alpha)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_source_rgba(*fo, alpha)
    ctx.stroke()
    if sp.get("pattern") == "stripes":
        ctx.set_source_rgba(0.12, 0.08, 0.06, alpha)
        for k, (px, py) in enumerate(((-0.1, 0.75), (0.2, 0.82), (-0.5, 0.5))):
            _ellipse(ctx, px * hr, py * hr, 0.07 * hr, 0.2 * hr, 0.2 * k)
            ctx.fill()
    if ek == "huge":
        flap = 0.12 * math.sin(TAU * t / 2.5)
        _ellipse(ctx, -hr * 0.3, -hr * 0.05, hr * 0.62, hr * 0.8, flap - 0.2)
        _fill(ctx, darker(fur, 0.9), alpha, fo, ow)
        _ellipse(ctx, -hr * 0.28, -hr * 0.05, hr * 0.42, hr * 0.58, flap - 0.2)
        _fill(ctx, (0.93, 0.74, 0.76), alpha * 0.55)
    if ek == "floppy":
        _ellipse(ctx, -hr * 0.35, hr * 0.05, hr * 0.28, hr * 0.62, 0.35 - 0.3 * ear)
        _fill(ctx, darker(fur, 0.75), alpha, fo, ow)
    # snout
    sl, sw = sp["snout"]
    mouth_pt = (hr * 0.95, -hr * 0.35)
    if name == "elephant":
        _trunk(ctx, sp, hr, alpha, ow, t, pose, s)
        mouth_pt = (hr * 0.75, -hr * 0.55)
        if sp.get("tusks"):
            ctx.set_source_rgba(0.98, 0.97, 0.9, alpha)
            ctx.set_line_width(7 * s)
            ctx.move_to(hr * 0.6, -hr * 0.45)
            ctx.curve_to(hr * 0.85, -hr * 0.85, hr * 1.1, -hr * 0.8, hr * 1.2, -hr * 0.55)
            ctx.stroke()
    elif sl > 0:
        mc = sp.get("muzzle") or lighter(fur, 0.35)
        cx = hr * 0.72 + sl * s * 0.35
        _ellipse(ctx, cx, -hr * 0.22, sl * s * 0.75 + hr * 0.2, sw * s * 0.6)
        _fill(ctx, mc if sp.get("muzzle") else fur, alpha, fo, ow)
        if not sp.get("muzzle"):
            _ellipse(ctx, cx + 2 * s, -hr * 0.3, sl * s * 0.6 + hr * 0.1, sw * s * 0.38)
            _fill(ctx, lighter(fur, 0.4), alpha)
        tip = cx + sl * s * 0.75 + hr * 0.2
        if sp.get("snout_flat"):
            _ellipse(ctx, tip - 3 * s, -hr * 0.22, 5 * s, 9 * s)
            _fill(ctx, darker(mc, 0.85), alpha, darker(mc, 0.6), ow * 0.7)
            for dy in (-3, 3):
                ctx.arc(tip - 3 * s, -hr * 0.22 + dy * s, 1.6 * s, 0, TAU)
                _fill(ctx, darker(mc, 0.5), alpha)
        else:
            ctx.arc(tip - 3 * s, -hr * 0.12, 5.5 * s, 0, TAU)
            _fill(ctx, (0.15, 0.1, 0.1), alpha)
        mouth_pt = (tip - 6 * s, -hr * 0.42)
        # jaw / mouth
        if mouth > 0.06:
            _ellipse(ctx, tip - sl * s * 0.45, -hr * 0.42 - mouth * 7 * s, sl * s * 0.45 + 4 * s, mouth * 10 * s + 2 * s)
            _fill(ctx, (0.45, 0.1, 0.12), alpha)
            if mouth > 0.5 and name in ("tiger", "lion", "wolf", "dog", "fox", "bear", "cat"):
                ctx.set_source_rgba(1, 1, 1, alpha)
                for dx in (-0.2, 0.25):
                    ctx.move_to(tip + (dx - 0.35) * sl * s - 2 * s, -hr * 0.36)
                    ctx.line_to(tip + (dx - 0.35) * sl * s, -hr * 0.36 - 7 * s)
                    ctx.line_to(tip + (dx - 0.35) * sl * s + 2 * s, -hr * 0.36)
                    ctx.fill()
        else:
            ctx.set_source_rgba(0.2, 0.12, 0.1, alpha)
            ctx.set_line_width(ow * 0.8)
            smile = 3 * s if face in ("happy", "laughing") else (-2 * s if face in ("sad", "crying") else 0)
            ctx.move_to(tip - sl * s * 0.9, -hr * 0.42)
            ctx.curve_to(tip - sl * s * 0.6, -hr * 0.42 - smile, tip - sl * s * 0.3, -hr * 0.42 - smile, tip - 5 * s, -hr * 0.36)
            ctx.stroke()
        if sp.get("whiskers"):
            ctx.set_source_rgba(0.15, 0.1, 0.1, alpha * 0.7)
            ctx.set_line_width(1.2 * s)
            for dy in (-4, 0, 4):
                ctx.move_to(tip - 10 * s, -hr * 0.2 + dy * s * 0.5)
                ctx.line_to(tip + 12 * s, -hr * 0.2 + dy * s * 1.6)
            ctx.stroke()
    # horns / antlers
    if sp.get("horns") == "small":
        for dx in (-0.35, 0.05):
            ctx.move_to(hr * dx, hr * 0.85)
            ctx.curve_to(hr * (dx - 0.05), hr * 1.2, hr * (dx + 0.2), hr * 1.3, hr * (dx + 0.25), hr * 1.25)
            ctx.set_source_rgba(0.95, 0.9, 0.78, alpha)
            ctx.set_line_width(6 * s)
            ctx.stroke()
    elif sp.get("horns") == "curved":
        ctx.move_to(hr * 0.1, hr * 0.85)
        ctx.curve_to(-hr * 0.2, hr * 1.5, -hr * 0.9, hr * 1.2, -hr * 0.8, hr * 0.6)
        ctx.set_source_rgba(0.55, 0.47, 0.38, alpha)
        ctx.set_line_width(6 * s)
        ctx.stroke()
    if sp.get("antlers"):
        ctx.set_source_rgba(0.55, 0.38, 0.2, alpha)
        ctx.set_line_width(4 * s)
        for dx in (-0.3, 0.05):
            bx = hr * dx
            ctx.move_to(bx, hr * 0.85)
            ctx.line_to(bx - hr * 0.2, hr * 1.9)
            for k, ly in enumerate((1.2, 1.5, 1.75)):
                ctx.move_to(bx - hr * 0.2 * (ly - 0.85) / 1.05, hr * ly)
                ctx.line_to(bx + hr * (0.35 if k % 2 == 0 else -0.35), hr * (ly + 0.3))
            ctx.stroke()
    if sp.get("beard"):
        ctx.move_to(hr * 0.9, -hr * 0.6)
        ctx.line_to(hr * 0.75, -hr * 1.2)
        ctx.line_to(hr * 1.1, -hr * 0.65)
        ctx.close_path()
        _fill(ctx, darker(fur, 0.85), alpha)
    # eye
    ex, ey = hr * 0.38, hr * 0.28
    er = hr * 0.2
    if sp.get("pattern") == "panda":
        _ellipse(ctx, ex, ey - er * 0.2, er * 1.7, er * 2.1, -0.4)
        _fill(ctx, (0.1, 0.1, 0.1), alpha)
    dark = (0.1, 0.08, 0.08)
    ctx.set_line_width(ow)
    if blink or face in ("sleeping", "crying"):
        ctx.move_to(ex - er, ey)
        ctx.curve_to(ex - er * 0.4, ey - er * 0.6, ex + er * 0.4, ey - er * 0.6, ex + er, ey)
        ctx.set_source_rgba(*dark, alpha)
        ctx.stroke()
    elif face == "laughing":
        ctx.move_to(ex - er, ey - er * 0.2)
        ctx.curve_to(ex - er * 0.4, ey + er * 0.7, ex + er * 0.4, ey + er * 0.7, ex + er, ey - er * 0.2)
        ctx.set_source_rgba(*dark, alpha)
        ctx.stroke()
    else:
        big = 1.25 if face in ("surprised", "scared") else 1.0
        _ellipse(ctx, ex, ey, er * big, er * 1.15 * big)
        _fill(ctx, (1, 1, 1), alpha, darker(fur, 0.5), ow * 0.6)
        ctx.arc(ex + er * 0.25, ey, er * 0.6, 0, TAU)
        _fill(ctx, dark, alpha)
        ctx.arc(ex + er * 0.4, ey + er * 0.3, er * 0.2, 0, TAU)
        _fill(ctx, (1, 1, 1), alpha)
    if face in ("angry", "sad", "scared", "crying"):
        ctx.set_source_rgba(*darker(fur, 0.45), alpha)
        ctx.set_line_width(ow * 1.2)
        if face == "angry":
            ctx.move_to(ex - er, ey + er * 1.8)
            ctx.line_to(ex + er * 1.1, ey + er * 1.1)
        else:
            ctx.move_to(ex - er, ey + er * 1.1)
            ctx.line_to(ex + er * 1.1, ey + er * 1.7)
        ctx.stroke()
    return mouth_pt


def _trunk(ctx, sp, hr, alpha, ow, t, pose, s):
    fur = sp["fur"]
    up = pose.get("trunk", 0)
    sway = 0.25 * math.sin(TAU * t / 2.2)
    pts = [(hr * 0.75, -hr * 0.1)]
    a = -1.25 + sway * 0.3 + up * 2.3
    for k in range(9):
        a += (0.05 + sway * 0.05) + up * 0.12
        lx, ly = pts[-1]
        pts.append((lx + math.cos(a) * hr * 0.2, ly + math.sin(a) * hr * 0.2))
    for k in range(len(pts) - 1):
        w = (hr * 0.42) * (1 - 0.55 * k / len(pts))
        _stroke(ctx, [pts[k], pts[k + 1]], w, fur, alpha, darker(fur, 0.58), ow)
    for k in range(len(pts) - 1):
        w = (hr * 0.42) * (1 - 0.55 * k / len(pts))
        _stroke(ctx, [pts[k], pts[k + 1]], w, fur, alpha)


def _draw_bird(ctx, c, pose, x, facing, face, mouth, t, extras, alpha, blink, y, shadow):
    from .character import draw_shadow
    sp = c.animal
    s = c.scale
    f = -1.0 if facing < 0 else 1.0
    br, hr = sp["body"] * s, sp["head"] * s
    lift = pose.get("lift", 0) * s
    leg_len = (0 if pose.get("leg", 0) > 0.7 else 18 * (1 - pose.get("leg", 0))) * s + 4 * s
    cy = y + lift + leg_len + br * 0.75
    ang = math.radians(pose.get("body", -12))
    fur, belly, wingc = sp["fur"], sp["belly"], sp["wing"]
    fo = darker(fur, 0.55) if sum(fur) > 0.4 else (0.35, 0.35, 0.4)
    OW = 2.2 * s
    if shadow:
        draw_shadow(ctx, x, lift / max(s, 0.1), br * 1.3, alpha, y)
    ctx.save()
    ctx.translate(x, cy)
    ctx.scale(f, 1)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    # legs
    if leg_len > 5 * s:
        ctx.set_source_rgba(0.95, 0.6, 0.15, alpha)
        ctx.set_line_width(3 * s)
        for dx in (-0.15, 0.15):
            fx = br * dx
            ctx.move_to(fx, -br * 0.6)
            ctx.line_to(fx, -br * 0.75 - leg_len)
            ctx.line_to(fx + 8 * s, -br * 0.75 - leg_len)
        ctx.stroke()
    wing = pose.get("wing", 0)
    # far wing
    if wing > 0.02:
        ctx.save()
        ctx.rotate(ang + wing * 1.4)
        _ellipse(ctx, -br * 0.1, br * 0.9, br * 0.45, br * 1.0)
        _fill(ctx, darker(wingc, 0.8), alpha, fo, OW)
        ctx.restore()
    ctx.save()
    ctx.rotate(ang)
    if sp.get("fan"):                                        # peacock: a big fan of eye feathers
        open_fan = 1.0 if pose.get("fan", 1.0) else 0.0
        cxf, cyf = -br * 0.6, br * 0.1
        L = br * (3.4 if open_fan else 2.4)
        for k in range(15):
            a = math.radians(95 + k * 7.5 if open_fan else 170 + k * 1.2)
            ex_, ey_ = cxf + math.cos(a) * L, cyf + math.sin(a) * L
            ctx.set_source_rgba(0.18, 0.45, 0.3, alpha)
            ctx.set_line_width(br * 0.28)
            ctx.move_to(cxf, cyf)
            ctx.line_to(ex_, ey_)
            ctx.stroke()
            ctx.arc(ex_, ey_, br * 0.2, 0, TAU)
            _fill(ctx, (0.1, 0.55, 0.45), alpha)
            ctx.arc(ex_, ey_, br * 0.11, 0, TAU)
            _fill(ctx, (0.95, 0.75, 0.2), alpha)
            ctx.arc(ex_, ey_, br * 0.06, 0, TAU)
            _fill(ctx, (0.1, 0.2, 0.6), alpha)
    # tail
    tl = (2.2 if sp.get("tail_long") else 1.0) * br
    ctx.move_to(-br * 0.7, br * 0.1)
    ctx.line_to(-br * 0.7 - tl, br * 0.1 + br * 0.5 * math.sin(math.radians(pose.get("tail", 10))))
    ctx.line_to(-br * 0.7 - tl * 0.9, -br * 0.3)
    ctx.close_path()
    _fill(ctx, wingc, alpha, fo, OW)
    # body
    _ellipse(ctx, 0, 0, br, br * 0.75)
    g = cairo.LinearGradient(0, br * 0.75, 0, -br * 0.75)
    g.add_color_stop_rgba(0, *fur, alpha)
    g.add_color_stop_rgba(1, *belly, alpha)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_source_rgba(*fo, alpha)
    ctx.set_line_width(OW)
    ctx.stroke()
    # near wing
    if wing <= 0.02:
        _ellipse(ctx, -br * 0.15, br * 0.05, br * 0.65, br * 0.4, 0.15)
        _fill(ctx, wingc, alpha, fo, OW)
    ctx.restore()
    if wing > 0.02:
        ctx.save()
        ctx.rotate(ang + wing * 1.2)
        _ellipse(ctx, 0.1 * br, br * 0.95, br * 0.5, br * 1.05)
        _fill(ctx, wingc, alpha, fo, OW)
        ctx.restore()
    # head
    hx = br * 0.85 * math.cos(ang) - br * 0.55 * math.sin(ang)
    hy = br * 0.85 * math.sin(ang) + br * 0.55 * math.cos(ang)
    ha = math.radians(pose.get("head", 0)) + ang * 0.3
    ctx.save()
    ctx.translate(hx, hy)
    ctx.rotate(ha)
    hc = sp.get("headc") or fur
    if sp.get("crest"):
        ctx.set_source_rgba(*darker(hc, 0.8), alpha)
        ctx.set_line_width(1.5 * s)
        for k in range(4):
            a = math.radians(70 + k * 12)
            ctx.move_to(0, hr * 0.8)
            ctx.line_to(math.cos(a) * hr * 1.9, math.sin(a) * hr * 1.9)
            ctx.stroke()
            ctx.arc(math.cos(a) * hr * 1.9, math.sin(a) * hr * 1.9, hr * 0.14, 0, TAU)
            ctx.fill()
    if sp.get("comb"):
        for k in range(3):
            ctx.arc(-hr * 0.2 + k * hr * 0.3, hr * 0.95, hr * 0.25, 0, TAU)
            _fill(ctx, (0.9, 0.15, 0.15), alpha)
    ctx.arc(0, 0, hr, 0, TAU)
    _fill(ctx, hc, alpha, fo, OW)
    beakc, bl = sp["beak"]
    open_ = max(mouth, pose.get("jaw", 0))
    bl *= s
    if sp.get("flat_beak"):
        _ellipse(ctx, hr * 0.9 + bl * 0.4, -hr * 0.15, bl * 0.6, hr * 0.22)
        _fill(ctx, beakc, alpha, darker(beakc, 0.6), OW * 0.8)
    else:
        ctx.move_to(hr * 0.8, hr * 0.2)
        ctx.line_to(hr * 0.8 + bl, -hr * 0.05 + open_ * 3 * s)
        ctx.line_to(hr * 0.8, -hr * 0.1)
        ctx.close_path()
        _fill(ctx, beakc, alpha, darker(beakc, 0.6), OW * 0.7)
        ctx.move_to(hr * 0.8, -hr * 0.1 - open_ * 2 * s)
        ctx.line_to(hr * 0.8 + bl * 0.8, -hr * 0.12 - open_ * 8 * s)
        ctx.line_to(hr * 0.75, -hr * 0.3 - open_ * 4 * s)
        ctx.close_path()
        _fill(ctx, darker(beakc, 0.85), alpha, darker(beakc, 0.6), OW * 0.7)
    ex, ey, er = hr * 0.35, hr * 0.25, hr * 0.26
    if sp.get("big_eyes"):                                   # owl: big round yellow-ringed eyes
        ex, ey, er = hr * 0.42, hr * 0.12, hr * 0.42
        if not (blink or face in ("sleeping",)):
            ctx.arc(ex, ey, er * 1.15, 0, TAU)
            _fill(ctx, (0.96, 0.78, 0.2), alpha)
    if blink or face in ("sleeping",):
        ctx.move_to(ex - er, ey)
        ctx.line_to(ex + er, ey)
        ctx.set_source_rgba(0.1, 0.1, 0.1, alpha)
        ctx.set_line_width(OW)
        ctx.stroke()
    else:
        ctx.arc(ex, ey, er, 0, TAU)
        _fill(ctx, (1, 1, 1), alpha, (0.2, 0.2, 0.2), OW * 0.5)
        ctx.arc(ex + er * 0.25, ey, er * 0.6, 0, TAU)
        _fill(ctx, (0.08, 0.08, 0.08), alpha)
        ctx.arc(ex + er * 0.4, ey + er * 0.3, er * 0.2, 0, TAU)
        _fill(ctx, (1, 1, 1), alpha)
    ctx.restore()
    ctx.restore()
    wx, wy = x + f * hx, cy + hy
    mouth_pt = (wx + f * (hr * 0.8 + bl * 0.5), wy - hr * 0.1)
    if extras.get("zzz"):
        _zzz(ctx, wx, wy + hr, t, s, alpha, f)
    return {"hand": mouth_pt, "head": (wx, wy), "hip": (x, cy), "head_r": hr, "mouth": mouth_pt}
