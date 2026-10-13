"""Lived-in places: small props that tell who lives here (3D Game Environments - environmental storytelling).

Story / scene setting  "lived_in": true  (or "lived_in": "busy" for more). Round every house, hut, well, hand pump,
stall and shop of the scene a few fitting things appear: a washing line with clothes, a stack of clay pots, a broom,
grain sacks, firewood, a bicycle leaning on a wall, a tea tray at a stall, a basket (sometimes knocked over).

They are placed AFTER everyone's moves are known, never where anyone walks, drives or stands, and are seeded by the
scene, so the same story always gets the same things in the same places.
"""
import math
import random

from .util import stable_hash

PIC = ""                     # assets/code/lived_in_3d.py saves each thing under its own name
FOR = {
    "house": ["washing_line", "matka_stack", "broom", "bicycle_leaning", "firewood", "grain_sacks"],
    "hut": ["washing_line", "matka_stack", "firewood", "broom", "basket"],
    "home": ["washing_line", "matka_stack", "broom", "bicycle_leaning"],
    "haveli": ["bicycle_leaning", "matka_stack", "washing_line"],
    "well": ["matka_stack", "basket"],
    "handpump": ["matka_stack", "basket"],
    "pump": ["matka_stack", "basket"],
    "stall": ["tea_tray", "basket", "grain_sacks"],
    "shop": ["grain_sacks", "basket", "bicycle_leaning"],
    "tea": ["tea_tray", "bicycle_leaning"],
    "barn": ["grain_sacks", "firewood"],
    "cot": ["basket"],
    "charpai": ["basket"],
}
SKIP = ("tree", "bush", "rock", "fence", "grass", "flower", "cloud", "hill", "road", "path", "lived_in")


def _kind(name):
    for k in FOR:
        if k in name:
            return k
    return None


CLAY = {"washing_line": "clay_washing_line_3d", "matka_stack": "clay_matka_stack_3d", "broom": "jhadu",
        "firewood": "clay_firewood_3d", "grain_sacks": "clay_grain_sacks_3d", "basket": "clay_basket_3d",
        "tea_tray": "clay_tea_tray_3d", "bicycle_leaning": "clay_bicycle_3d", "charpai": "charpai",
        "bucket": "bucket"}
CLAY_FOR = {"house": ["charpai", "bucket"], "hut": ["charpai"], "well": ["bucket"], "handpump": ["bucket"]}


def place(scene, how=True):
    """Add the props to scene.props. -> list of (id, picture, x, z). In a clay world (Ghatti Nagar) the sculpted
    ones (engine/sculpt_village.py), and a charpai or a bucket by some houses too."""
    from . import images, objects
    from .timeline import PropTrack
    clay = bool(getattr(getattr(scene, "bg", None), "spec", {}).get("clay"))
    busy = str(how).lower() == "busy"
    rng = random.Random(stable_hash(f"livedin{scene.index}{scene.world_w}") % 1000003)
    anchors = []
    for pid, pr in list(scene.props.items()):
        if pr.vtype:
            continue
        name = f"{pid} {pr.type}".lower()
        if any(w in name for w in SKIP):
            continue
        k = _kind(name)
        if k is None:
            continue
        try:
            st, _ = pr.at(0.0)
            if st[0] != "rest":
                continue
            w, _h = objects.size(pr)
            anchors.append((pid, k, st[1], pr.z_at(0.0), w))
        except Exception:
            continue
    if not anchors:
        return []
    # everywhere anyone is during the scene (story x, z) - the props keep clear of it
    busy_pts = []
    dur = max(1.0, scene.duration)
    n = int(min(300, dur / 0.25))
    for j in range(n + 1):
        t = dur * j / max(n, 1)
        for tr in scene.tracks.values():
            try:
                busy_pts.append((tr.x_at(t), tr.z_at(t), 130.0))
            except Exception:
                pass
        for pr in scene.props.values():
            if pr.vtype:
                try:
                    busy_pts.append((pr.pos(t)[0], pr.z_at(t), 300.0))
                except Exception:
                    pass
    solid = []
    for pid, pr in scene.props.items():                  # and from the other things
        if pr.vtype:
            continue
        try:
            st, _ = pr.at(0.0)
            if st[0] == "rest":
                w, _h = objects.size(pr)
                nm = f"{pid} {pr.type}".lower()
                if any(k in nm for k in ("tree", "banyan", "palm", "neem", "peepal", "mango")):
                    w = min(w, 160.0)                    # a tree: only its trunk is in the way
                solid.append((st[1], pr.z_at(0.0), w * 0.5 + 30.0))
        except Exception:
            pass
    from .timeline import ZK
    k_ = ZK * 2.5

    def free(x, z, r):
        for bx, bz, br in busy_pts:
            if math.hypot(x - bx, (z - bz) * k_) < br + r:
                return False
        for bx, bz, br in solid:
            if math.hypot(x - bx, (z - bz) * k_) < br + r:
                return False
        return 60 < x < scene.world_w - 60 and -60 < z < 2600

    out = []
    per = 3 if busy else 2
    for pid, k, ax, az, w in anchors:
        choices = list(FOR[k]) + (list(CLAY_FOR.get(k, ())) if clay else [])
        rng.shuffle(choices)
        put = 0
        for what in choices:
            if put >= per:
                break
            pic = CLAY.get(what, PIC + what) if clay else PIC + what
            if not images.exists(pic):
                continue
            r = 70.0 if what in ("washing_line",) else 40.0
            for _try in range(14):
                side = rng.choice((-1, 1))
                ang = rng.uniform(-0.9, 0.9) if _try < 8 else rng.uniform(-math.pi, math.pi)
                dist = w * 0.5 + 45.0 + r + rng.uniform(10, 140)
                x = ax + side * math.cos(ang) * dist
                z = az + math.sin(ang) * dist / k_
                if free(x, z, r):
                    nid = f"_lived_{pid}_{what}"
                    if nid in scene.props:
                        break
                    if what == "basket" and not clay and rng.random() < 0.35 and images.exists(PIC + "basket_fallen"):
                        pic = PIC + "basket_fallen"
                    scene.props[nid] = PropTrack({"id": nid, "type": pic, "x": round(x, 1), "z": round(z, 1),
                                                  "facing": "left" if side < 0 else "right", "_dressing": True})
                    solid.append((x, z, r))
                    out.append((nid, pic, x, z))
                    put += 1
                    break
    return out
