"""What the story SAYS is there, is shown: a scene whose narration or dialogue names a waterfall (झरना), a well
(कुआँ), a temple (मंदिर) ... but has none of it, gets one put in at the back, where the camera sees it behind the
people - with a note.  Setting  "show_mentioned": false  turns it off.

It runs after everyone's moves are known, keeps clear of where anyone walks, drives or stands, and is seeded by
the scene, so the same story always gives the same place.
"""
import math
import re

# thing -> (words in the story that mean it, the 3D drawing, how wide it is, how far back it goes (story z))
THINGS = [
    ("waterfall", ("waterfall", "water fall", "jharna", "jharne", "jharnaa", "झरना", "झरने", "झरनों", "प्रपात"),
     "waterfall_3d", 620, (950, 1350)),
    ("well", (r"\bwell\b(?! done)", "kuan", "kuaan", "कुआँ", "कुआं", "कुएँ", "कुएं"), "well_3d", 220, (520, 800)),
    ("temple", ("temple", "mandir", "मंदिर", "मन्दिर"), "temple_3d", 520, (800, 1100)),
    ("handpump", ("handpump", "hand pump", "हैंडपंप", "हैंड पंप", "नलका"), "handpump_3d", 120, (450, 700)),
]


def _texts(scene):
    out = []
    for e in scene.spec.get("events", []) or []:
        if isinstance(e, dict):
            for k in ("narrate", "say", "think", "caption"):
                v = e.get(k)
                if isinstance(v, str):
                    out.append(v.lower())
    for k in ("narrate", "caption", "title"):
        if isinstance(scene.spec.get(k), str):
            out.append(scene.spec[k].lower())
    return " ".join(out)


def _has(scene, key):
    for pid, pr in scene.props.items():
        if key in f"{pid} {getattr(pr, 'type', '')}".lower():
            return True
    try:                                                   # a place that already has one (kishkindha's pool ...)
        bg = scene.spec.get("background") or {}
        if key in str(bg.get("preset", "") if isinstance(bg, dict) else bg).lower():
            return True
    except Exception:
        pass
    return False


def place(scene):
    """Add the missing things to scene.props. -> [(id, drawing, x, z)]"""
    from . import images, objects
    from .timeline import PropTrack, ZK
    text = _texts(scene)
    if not text:
        return []
    want = []
    for key, words, pic, w, zr in THINGS:
        if any(re.search(wd, text) if wd.startswith("\\b") else wd in text for wd in words) and not _has(scene, key):
            if images.exists(pic):
                want.append((key, pic, w, zr))
    if not want:
        return []
    k_ = ZK * 2.5
    # where everyone is during the scene: the thing goes behind them, never on them
    pts, xs = [], []
    dur = max(1.0, scene.duration)
    n = int(min(240, dur / 0.25))
    for j in range(n + 1):
        t = dur * j / max(n, 1)
        for tr in scene.tracks.values():
            try:
                x, z = tr.x_at(t), tr.z_at(t)
                pts.append((x, z, 130.0))
                xs.append(x)
            except Exception:
                pass
        for pr in scene.props.values():
            if pr.vtype:
                try:
                    x = pr.pos(t)[0]
                    pts.append((x, pr.z_at(t), 300.0))
                    xs.append(x)
                except Exception:
                    pass
    solids = []
    for pid, pr in scene.props.items():
        if pr.vtype:
            continue
        try:
            st, _ = pr.at(0.0)
            if st[0] == "rest":
                ww, _h = objects.size(pr)
                nm = f"{pid} {pr.type}".lower()
                if any(k in nm for k in ("tree", "banyan", "palm", "neem", "peepal", "mango", "bush")):
                    ww = min(ww, 160.0)                  # a tree / bush: only its middle is in the way
                solids.append((st[1], pr.z_at(0.0), ww * 0.5 + 20.0))
        except Exception:
            pass
    # the people's last half of the scene matters most (that is where they talk about it)
    tail = xs[len(xs) // 2:] or xs or [scene.world_w * 0.5]
    mid = sorted(tail)[len(tail) // 2]

    def free(x, z, r):
        for bx, bz, br in pts:
            if math.hypot(x - bx, (z - bz) * k_) < br + r:
                return False
        for bx, bz, br in solids:                       # a tree well in front only hides a bit of it: fine
            if abs(z - bz) < 160 and abs(x - bx) < br + r:
                return False
        return r * 0.6 < x < scene.world_w - r * 0.6

    out = []
    for key, pic, w, (z0, z1) in want:
        r = w * 0.5
        done = False
        # right behind the people first (a bit further back if a tree is there), then more to the side
        tries = [(dx, dz) for dx in (0, 1, -1, 2, -2, 3, -3, 4, -4, 6, -6) for dz in (0.0, 0.33, 0.66, 1.0)]
        for dx, dz in tries:
            z = z0 + (z1 - z0) * dz
            if True:
                x = mid + dx * 160.0 + (220.0 if key != "waterfall" else 0.0)
                if free(x, z, r):
                    nid = f"_said_{key}"
                    sp = {"id": nid, "type": pic, "x": round(x, 1), "z": round(z, 1), "_dressing": True}
                    if key == "waterfall":                 # far back: a bit bigger so it still reads as a waterfall
                        sp["scale"] = round(1.0 + 0.4 * (z - 900) / 450.0, 2)
                    scene.props[nid] = PropTrack(sp)
                    solids.append((x, z, r))
                    out.append((nid, pic, x, z))
                    done = True
                    break
            if done:
                break
    return out
