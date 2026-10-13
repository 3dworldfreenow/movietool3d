"""Test Lab: run a small test story and MEASURE how it moves - no video needed.

Used by the 🧪 Test Lab page (/lab) and by tests/physics_check.py. For every scene of a story it samples every
character and vehicle every 0.1 s and checks the rules of the real world:

  people     never inside a solid thing (huts, trees, walls, rocks) or walking into water
  vehicles   never through solid things or into water; never spin round on the spot; never slide sideways
             (the nose points the way it drives - or exactly the other way when backing up)
  walking    how far the standing foot slides on the ground while walking / running (should be ~0)
  talking    every line has body language; how long anybody stands like a statue in a talk scene
  (optional) shot check: can the audience see whoever is talking (renders small frames - slower)

A test story is any story JSON. It may carry a "lab" block that the page shows:
  "lab": {"title": "...", "about": "...", "look_for": ["...", "..."], "stills": [1, 3.5, 6]}
"""
import glob
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB_DIR = os.path.join(ROOT, "tests", "lab")
PHYS_DIR = os.path.join(ROOT, "tests", "physics")
OUT_DIR = os.path.join(ROOT, "output", "lab")
CAR_HALF = 245 * 0.8
PHYS_TITLE = {"1_hut_and_trees": "Walk past the hut and trees", "2_river_edge": "Walk toward the river",
              "3_behind_a_tree": "Walk to a spot behind a tree", "4_start_inside_hut": "Story places Sita inside the hut",
              "5_pillars": "Cross a hall full of pillars", "6_car": "Car: drive, turn back, reverse, drive round",
              "7_jeep_to_river": "Jeep told to drive to the river"}


# ----------------------------------------------------------------------------------------------- the tests on offer
def scenarios():
    """[{name, title, about, look_for, stills, group, file}] - tests/lab/*.json then tests/physics/*.json."""
    out = []
    for group, d in (("lab", LAB_DIR), ("physics", PHYS_DIR)):
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            try:
                with open(p, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            name = os.path.basename(p)[:-5]
            lab = data.get("lab") if isinstance(data.get("lab"), dict) else {}
            out.append(dict(name=name, group=group, file=os.path.relpath(p, ROOT),
                            title=lab.get("title") or PHYS_TITLE.get(name) or data.get("title") or name,
                            about=lab.get("about", "Physics rule test: people / vehicles must never go through "
                                                   "solid things or into water." if group == "physics" else ""),
                            look_for=lab.get("look_for", []), stills=lab.get("stills") or default_stills(data)))
    return out


def default_stills(data):
    return [1.0, 3.0, 5.0, 8.0, 11.0, 14.0]


def story_path(name):
    for d in (LAB_DIR, PHYS_DIR):
        p = os.path.join(d, os.path.basename(str(name)) + ".json")
        if os.path.exists(p):
            return p
    return None


# ----------------------------------------------------------------------------------------------- solid things
def _meta(name):
    try:
        with open(os.path.join(ROOT, "assets", "images", name + ".json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def solids(tl):
    """[(id, x0, x1, z0, z1)] ground footprints (story units) of the solid things standing in the scene."""
    from . import objects
    from .codedraw import z_from_depth
    from .world3d import Z_of_z, p3
    from .scene3d import FOCAL
    out = []
    for pid, o in tl.props.items():
        if o.vtype or not objects.is_object(o):
            continue
        st, _ = o.at(0.0)
        if st[0] != "rest":
            continue
        img = objects._image_name(o)
        meta = _meta(img) if img else {}
        fp = meta.get("foot")
        if not fp or meta.get("walk") or float(o.spec.get("y") or 0) > 40 or float(meta.get("height") or 99) < 38:
            continue
        h_draw = objects.size(o)[1]
        sc = h_draw / max(1.0, float(meta.get("height") or h_draw))
        zc = o.z_at(0.0)
        Zc = Z_of_z(zc) - FOCAL
        k = p3(zc)
        for f in (meta.get("feet") or [fp]):
            out.append([pid, st[1] + f[0] * sc * k, st[1] + f[1] * sc * k, z_from_depth(Zc + f[2] * sc),
                        z_from_depth(Zc + f[3] * sc)])
    return out


def _raised(tr, t):
    """sitting / standing on top of something, or carried by someone (then a footprint below is fine)"""
    try:
        if tr.mounted_at(t) is not None:
            return True
        i = tr.seg_index(t)
        if i >= 0 and tr.segments[i].action in ("sit_on", "perch", "climb", "step_up") and t >= tr.segments[i].start + 0.2:
            return True
        return tr.y_at(t) > 25.0
    except Exception:                                    # noqa: BLE001
        return False


# ----------------------------------------------------------------------------------------------- sampling
def sample(tl, step=0.1):
    bg = tl.bg
    d = {"solids": solids(tl), "shore": bg.shore_x if getattr(bg, "water", None) else None,
         "land": getattr(bg, "land_side", None), "water": getattr(bg, "water", None), "world_w": tl.world_w,
         "dur": tl.duration, "people": {}, "vehicles": {}}
    ts = [k * step for k in range(int(tl.duration / step) + 1)]
    for cid, tr in tl.tracks.items():
        if tr.crowd:
            continue
        d["people"][cid] = [[round(t, 2), tr.x_at(t), tr.z_at(t), bool(tl._visible(cid, t))] for t in ts]
        d.setdefault("raised", {})[cid] = [_raised(tr, t) for t in ts]     # up on something / carried: not "inside" it
        d.setdefault("riders", {})[cid] = [tr.riding_at(t) is not None or bool(tr.segments and any(
            sg.params.get("_exit") and sg.start <= t <= sg.start + 2.0 for sg in tr.segments)) for t in ts]
    for vid, v in tl.props.items():
        if v.vtype:
            rows = []
            for t in ts:
                x, _y, f = v.pos(t)
                hx, hz = v.heading_at(t)
                rows.append([round(t, 2), x, v.z_at(t), f, v.view_at(t), hx, hz, bool(v.moving(t))])
            d["vehicles"][vid] = rows
    return d


def _in_water(d, x):
    if not d["water"] or d["shore"] is None:
        return False
    return x > d["shore"] if d["land"] == "left" else x < d["shore"]


def _ang(hx, hz):
    from .timeline import ZK
    return math.atan2(hz * ZK * 2.5, hx)


def judge(name, d, start_ok=True):
    """(fails, info) for one sampled scene."""
    fails, info = [], []
    for cid, pts in d["people"].items():
        hit = set()
        up = (d.get("raised") or {}).get(cid) or []
        for j, (t, x, z, vis) in enumerate(pts):
            if not vis or (j < len(up) and up[j]):
                continue
            if t < 0.05 and start_ok:
                continue                                 # the story's own start spot
            for pid, x0, x1, z0, z1 in d["solids"]:
                if x0 + 10 < x < x1 - 10 and z0 + 8 < z < z1 - 8 and pid not in hit:
                    hit.add(pid)
                    fails.append(f"{cid} is INSIDE {pid} at {t:.1f}s")
            if _in_water(d, x) and "water" not in hit:
                hit.add("water")
                fails.append(f"{cid} walks INTO the river at {t:.1f}s (x={x:.0f}, shore {d['shore']:.0f})")
        info.append(f"{cid}: ends at x={pts[-1][1]:.0f}, z={pts[-1][2]:.0f}")
    for vid, pts in d["vehicles"].items():
        hit = set()
        prev = None
        spun = slid = False
        for row in pts:
            t, x, z, f, view, hx, hz, moving = row
            a_ = _ang(hx, hz)                              # its length along the nose, its width across
            ext = abs(math.cos(a_)) * CAR_HALF + abs(math.sin(a_)) * 100.0
            for pid, x0, x1, z0, z1 in d["solids"]:
                if x - ext < x1 - 10 and x + ext > x0 + 10 and z0 + 8 < z < z1 - 8 and pid not in hit:
                    hit.add(pid)
                    fails.append(f"{vid} DRIVES THROUGH {pid} at {t:.1f}s")
            if _in_water(d, x + f * 245) and "water" not in hit:
                hit.add("water")
                fails.append(f"{vid} DRIVES INTO the river at {t:.1f}s")
            if prev is not None:
                a0, a1 = _ang(prev[5], prev[6]), _ang(hx, hz)
                turn = abs((a1 - a0 + math.pi) % (2 * math.pi) - math.pi)
                dist = math.hypot(x - prev[1], (z - prev[2]) * 2.0)
                if turn > math.radians(40) and not spun:
                    spun = True
                    fails.append(f"{vid} SPINS round on the spot at {t:.1f}s ({math.degrees(turn):.0f} degrees in 0.1 s)")
                if moving and dist > 4.0 and not slid:
                    am = math.atan2((z - prev[2]) * 2.0, x - prev[1])
                    off = abs((am - a1 + math.pi) % (2 * math.pi) - math.pi)
                    off = min(off, math.pi - off)                  # backing up = exactly the other way: fine
                    if off > math.radians(40):
                        slid = True
                        fails.append(f"{vid} SLIDES SIDEWAYS at {t:.1f}s (moves {math.degrees(off):.0f} degrees "
                                     f"off where its nose points)")
            prev = row
        info.append(f"{vid}: ends at x={pts[-1][1]:.0f}, z={pts[-1][2]:.0f}")
    # moving vehicles never run into people or into each other
    vids = list(d["vehicles"])
    told = set()
    for vid in vids:
        rows = d["vehicles"][vid]
        for j, row in enumerate(rows):
            t, x, z, f, view, hx, hz, moving = row
            if not moving:
                continue
            a_ = _ang(hx, hz)
            ext = abs(math.cos(a_)) * CAR_HALF + abs(math.sin(a_)) * 100.0
            for cid, pts in d["people"].items():
                if j < len(pts) and (vid, cid) not in told:
                    _t, px, pz, vis = pts[j]
                    if vis and abs(px - x) < ext * 0.9 and abs(pz - z) < 45 and not _riding(d, cid, j):
                        told.add((vid, cid))
                        fails.append(f"{vid} RUNS INTO {cid} at {t:.1f}s")
            for wid in vids:
                if wid == vid or (wid, vid) in told or (vid, wid) in told:
                    continue
                r2 = d["vehicles"][wid][j]
                a2 = _ang(r2[5], r2[6])
                e2 = abs(math.cos(a2)) * CAR_HALF + abs(math.sin(a2)) * 100.0
                if abs(r2[1] - x) < (ext + e2) * 0.85 and abs(r2[2] - z) < 70:
                    told.add((vid, wid))
                    fails.append(f"{vid} CRASHES INTO {wid} at {t:.1f}s")
    return fails, info


def _riding(d, cid, j):
    return cid in d.get("riders", {}) and j < len(d["riders"][cid]) and d["riders"][cid][j]


# ----------------------------------------------------------------------------------------------- walking feet
def foot_slide():
    """{walk: units/s, run: units/s} - how fast the foot on the ground slides (median; 0 = locked), worst of
    an ordinary adult, a heavy adult and a light child (the weight changes the gait - engine/realworld.py)."""
    from . import poses, realworld
    from .character import CharacterDef
    bodies = [None] + [dict(realworld.gait(CharacterDef(k, sp)), land=0.35, real=False)
                       for k, sp in (("heavy", {"build": "fat"}), ("child", {"age": "child"}))]
    out = {}
    for name, v in (("walk", poses.WALK_SPEED), ("run", poses.RUN_SPEED)):
        out[name] = max([_slide(name, v, b) for b in bodies] + [_slide(name, v * 0.5, None, "toddler")])   # + a toddler
    return out


def _slide(name, v, body, age=None):
    from . import poses
    from .character import solve, AGE_BODY
    fps, prev, sl = 60, None, []
    prop = AGE_BODY.get(age) if age else None
    for f in range(240):
        t = f / fps
        ctx = {"speed": v, "dist": v * t, "params": {}}
        if body:
            ctx["body"] = body
        if prop:
            ctx.update(age=age, legk=prop["leg"])
        p, _ = poses.ACTIONS[name].fn(t, 4, ctx)
        J = solve(p, 1.0, None, prop)
        k = "n" if J["fn"][1] <= J["ff"][1] else "f"
        wx = v * t + J["f" + k][0]
        if prev and prev[1] == k:
            sl.append(abs(wx - prev[0]) * fps)
        prev = (wx, k)
    sl.sort()
    return round(sl[len(sl) // 2], 1) if sl else 0.0


# ----------------------------------------------------------------------------------------------- talking
def acting_report(tl):
    """Body language in the talk: gestures per line and the longest 'statue' stretch (nobody moves at all)."""
    from .timeline import _act_prepare
    sp = [s for s in tl.speeches if s.who in tl.tracks]
    if not sp:
        return None
    mode = str(getattr(tl, "acting", "auto") or "auto").lower()
    gest = {}
    if mode not in ("off", "none", "no", "false"):
        _act_prepare(tl)
        for s in sp:
            gest[getattr(s, "gest", "talk")] = gest.get(getattr(s, "gest", "talk"), 0) + 1
    moves = []
    for tr in tl.tracks.values():
        for sg in tr.segments:
            if sg.spec.moving or sg.action not in ("idle", "stand", "appear", "talk"):
                moves.append((sg.start, sg.end))
    longest, run_start = 0.0, sp[0].start
    for s in sp:
        if any(a <= s.end and b >= s.start for a, b in moves) or gest:
            run_start = s.end
        longest = max(longest, s.end - run_start)
    return {"lines": len(sp), "acting": mode, "gestures": gest, "statue_seconds": round(longest, 1),
            "moves": len(moves)}


# ----------------------------------------------------------------------------------------------- whole story
def run(path, shots=False, log=None):
    """Check a story file. -> {ok, scenes: [{n, fails, info, map, acting}], notes, feet, shots}"""
    from .project import Project
    P = Project(path, {"tts": "silent", "cache": os.path.join(ROOT, "cache", "validate"),
                       **({"resolution": "480x270", "fps": 12} if shots else {})}, log=log or (lambda *a: None))
    scenes = []
    start_ok = not os.path.basename(path).startswith("4_")
    for it in P.items:
        if it.kind != "scene":
            continue
        tl = it.scene
        d = sample(tl)
        fails, info = judge(os.path.basename(path), d, start_ok)
        scenes.append({"n": tl.index + 1, "fails": fails, "info": info, "acting": acting_report(tl),
                       "map": {"w": d["world_w"], "solids": d["solids"],
                               "water": ({"shore": d["shore"], "land": d["land"]} if d["water"] and d["shore"]
                                         is not None else None),
                               "people": {k: [[r[1], r[2]] for r in v[::3]] for k, v in d["people"].items()},
                               "vehicles": {k: [[r[1], r[2]] for r in v[::3]] for k, v in d["vehicles"].items()}}})
    res = {"ok": not any(s["fails"] for s in scenes), "scenes": scenes, "notes": list(P.warnings) + list(P.notes),
           "feet": foot_slide(), "duration": round(float(getattr(P.items[-1], "end", 0.0) or 0.0), 1) if P.items
           else 0.0}
    if shots:
        from . import shotcheck
        res["shots"] = shotcheck.check(P)
        if res["shots"]:
            res["ok"] = False
    return res
