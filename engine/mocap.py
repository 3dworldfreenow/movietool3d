"""Mixamo moves (motion capture) -> our actions, for every character (stick figure, cartoon, puppet, 3D).

A Mixamo animation (FBX -> GLB by engine/fbx.py, or any rigged GLB with an animation) is played once here: the
skeleton's joints are followed frame by frame, and every frame becomes one of our poses (the same angles a hand-made
action uses: thighs, shins, upper arms, forearms, spine lean, head nod, hips height). The poses are saved small in
assets/moves/<name>.json, so the video never needs the big model again - and the move works on everybody:

    {"who": "ravi", "do": "samba"}            (the move's name)
    {"who": "ravi", "do": "samba", "duration": 6}   (loops / stops after 6 s)

Our figures are drawn from the side, so a move is kept in the body's own front / up plane (arms out to the side
become arms raised - the energy and timing of the real dancer stay).
"""
import json
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOVES = os.path.join(ROOT, "assets", "moves")
FPS = 15.0
_LOADED = {"stamp": None}


def _clean(n):
    import re
    return re.sub(r"[^a-z0-9_]+", "_", str(n).strip().lower()).strip("_")


def _trs(t, q, s):
    x, y, z, w = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4)
    M[:3, :3] = R * np.array(s)[None, :]
    M[:3, 3] = t
    return M


def _slerp(a, b, u):
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        r = a + (b - a) * u
        return r / np.linalg.norm(r)
    th = math.acos(min(1.0, d))
    return (math.sin((1 - u) * th) * a + math.sin(u * th) * b) / math.sin(th)


def clip_poses(path, clip=0, fps=FPS):
    """-> (poses [dict per frame], seconds, name) for animation `clip` of a GLB / glTF."""
    from . import model3d, rigmodel
    gf = model3d._gltf_open(path)
    G, acc = gf.G, gf.accessor
    anims = G.get("animations") or []
    if not anims:
        raise ValueError("this model has no animation (download it from Mixamo WITH the move: 'With Skin' or not)")
    an = anims[min(int(clip), len(anims) - 1)]
    nodes = G.get("nodes") or []
    N = len(nodes)
    parent = [-1] * N
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    base_T = [np.array(n.get("translation", [0, 0, 0]), float) for n in nodes]
    base_R = [np.array(n.get("rotation", [0, 0, 0, 1]), float) for n in nodes]
    base_S = [np.array(n.get("scale", [1, 1, 1]), float) for n in nodes]
    fixed = [np.array(n["matrix"], float).reshape(4, 4).T if "matrix" in n else None for n in nodes]
    tracks = {}
    t_end = 0.0
    for ch in an.get("channels", []):
        sm = an["samplers"][ch["sampler"]]
        tt = acc(sm["input"]).reshape(-1)
        vv = acc(sm["output"])
        node, path_ = ch["target"].get("node"), ch["target"].get("path")
        if node is None or path_ not in ("translation", "rotation", "scale"):
            continue
        tracks[(node, path_)] = (tt, vv)
        t_end = max(t_end, float(tt[-1]) if len(tt) else 0.0)
    if t_end <= 0:
        raise ValueError("the animation is empty")
    skin = (G.get("skins") or [{}])[0]
    joints = skin.get("joints") or []
    jnames = [str(nodes[j].get("name") or f"j{j}") for j in joints]
    jparent = []
    for j in joints:
        p = parent[j]
        while p >= 0 and p not in joints:
            p = parent[p]
        jparent.append(joints.index(p) if p in joints else -1)

    def worlds(t):
        W = [None] * N

        def w(i):
            if W[i] is None:
                if fixed[i] is not None:
                    L = fixed[i]
                else:
                    T_, R_, S_ = base_T[i], base_R[i], base_S[i]
                    for pth in ("translation", "rotation", "scale"):
                        got = tracks.get((i, pth))
                        if got is None:
                            continue
                        tt, vv = got
                        k = int(np.searchsorted(tt, t, side="right")) - 1
                        k = max(0, min(len(tt) - 1, k))
                        k2 = min(len(tt) - 1, k + 1)
                        u = 0.0 if k2 == k else float(np.clip((t - tt[k]) / max(1e-9, tt[k2] - tt[k]), 0, 1))
                        if pth == "rotation":
                            R_ = _slerp(vv[k], vv[k2], u)
                        elif pth == "translation":
                            T_ = vv[k] + (vv[k2] - vv[k]) * u
                        else:
                            S_ = vv[k] + (vv[k2] - vv[k]) * u
                    L = _trs(T_, R_, S_)
                W[i] = L if parent[i] < 0 else w(parent[i]) @ L
            return W[i]
        return [w(j)[:3, 3] for j in joints], w

    rest_pos, _ = worlds(0.0)
    rest = np.array(rest_pos)
    found = rigmodel.auto_bones(jnames, jparent, rest)
    ix = {n: i for i, n in enumerate(jnames)}
    role = {k: (ix[v[0]] if isinstance(v, list) else ix[v]) for k, v in found.items() if v}
    spine_top = None
    if isinstance(found.get("spine"), list) and found["spine"]:
        spine_top = ix[found["spine"][-1]]
    need = ("hips", "r_thigh", "l_thigh", "r_shin", "l_shin", "r_foot", "l_foot")
    if any(r not in role for r in need):
        raise ValueError("could not find the leg bones of this model's skeleton")
    up = np.array([0.0, 1.0, 0.0])
    left = rest[role["l_thigh"]] - rest[role["r_thigh"]]
    left[1] = 0
    fwd = np.cross(left, up)                             # (the character's left x up = its front)
    fwd = fwd / (np.linalg.norm(fwd) or 1.0)
    leg_len = np.linalg.norm(rest[role["r_thigh"]] - rest[role["r_shin"]]) + \
        np.linalg.norm(rest[role["r_shin"]] - rest[role["r_foot"]])
    hip0 = rest[role["hips"]][1]
    K = (72.0 + 70.0) / max(leg_len, 1e-6)              # model metres -> our units (thigh + shin = 142)

    def ang(v):
        """our angle of a bone: from straight DOWN, + toward the front (degrees). A bone held out to the SIDE
        (no front / back part) counts as raised by the same amount - our figures move in the front / up plane."""
        L = float(np.linalg.norm(v)) or 1.0
        f, u = float(np.dot(v, fwd)) / L, float(np.dot(v, up)) / L
        elev = math.degrees(math.acos(max(-1.0, min(1.0, -u))))
        if abs(f) > 0.25:
            return elev if f > 0 else -elev
        side = 1.0 if f >= -0.05 else -1.0
        return side * elev

    def lean(v):
        """+ = leaning forward, from straight UP"""
        return math.degrees(math.atan2(float(np.dot(v, fwd)), float(np.dot(v, up))))

    def wrap(a):
        return (a + 180.0) % 360.0 - 180.0
    n = max(2, int(t_end * fps) + 1)
    poses = []
    for f in range(n):
        P, _w = worlds(min(t_end, f / fps))
        P = np.array(P)
        g = lambda r: P[role[r]] if r in role else None      # noqa: E731
        p = {}
        neck = g("neck") if "neck" in role else (P[spine_top] if spine_top is not None else g("head"))
        p["torso"] = lean(neck - g("hips"))
        hd = g("head")
        head_top = None
        for k_, nm in enumerate(jnames):
            if "headtop" in nm.lower().replace("_", ""):
                head_top = P[k_]
        if hd is not None:
            hv = (head_top - hd) if head_top is not None else (hd - neck)
            p["head"] = wrap(lean(hv) - p["torso"])
        for side, s in (("n", "r"), ("f", "l")):                # near = the right side (toward the camera)
            th = ang(g(f"{s}_shin") - g(f"{s}_thigh"))
            sh = ang(g(f"{s}_foot") - g(f"{s}_shin"))
            p[f"l{side}_t"] = th
            p[f"l{side}_s"] = wrap(sh - th)
            if f"{s}_upper_arm" in role and f"{s}_forearm" in role:
                hand = g(f"{s}_hand") if f"{s}_hand" in role else g(f"{s}_forearm")
                ua = ang(g(f"{s}_forearm") - g(f"{s}_upper_arm"))
                fa = ang(hand - g(f"{s}_forearm"))
                p[f"a{side}_u"] = ua
                p[f"a{side}_l"] = wrap(fa - ua)
        feet = min(g("r_foot")[1], g("l_foot")[1])
        p["lift"] = max(0.0, (feet - min(rest[role["r_foot"]][1], rest[role["l_foot"]][1])) * K)
        p["rot"] = 0.0
        poses.append({k_: round(float(v), 2) for k_, v in p.items()})
    del hip0
    return poses, round(t_end, 3), an.get("name") or "clip"


def save_move(name, poses, seconds, source="", loop=True):
    os.makedirs(MOVES, exist_ok=True)
    nm = _clean(name)
    with open(os.path.join(MOVES, nm + ".json"), "w", encoding="utf-8") as fh:
        json.dump({"name": nm, "fps": FPS, "seconds": seconds, "loop": loop, "source": source,
                   "frames": poses}, fh, separators=(",", ":"))
    _LOADED["stamp"] = None
    return nm


def import_move(path, name=None, clip=0):
    """A GLB / glTF / FBX with an animation -> a saved move. -> (name, seconds, frames)"""
    src = path
    if path.lower().endswith(".fbx"):
        from . import fbx
        import tempfile
        tmp = os.path.join(tempfile.mkdtemp(prefix="move_"), "m.glb")
        fbx.to_glb(path, tmp)
        src = tmp
    poses, secs, cname = clip_poses(src, clip)
    nm = save_move(name or os.path.splitext(os.path.basename(path))[0], poses, secs, os.path.basename(path))
    return nm, secs, len(poses)


def list_moves():
    out = {}
    if os.path.isdir(MOVES):
        for f in sorted(os.listdir(MOVES)):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(MOVES, f), encoding="utf-8") as fh:
                        d = json.load(fh)
                    out[d.get("name") or f[:-5]] = d
                except (OSError, ValueError):
                    continue
    return out


def _action_fn(d):
    frames = d["frames"]
    fps = float(d.get("fps", FPS))
    loop = bool(d.get("loop", True))
    n = len(frames)

    def fn(t, dur, ctx):
        from .poses import P
        f = t * fps
        if loop:
            f = f % max(1, n - 1)
        else:
            f = min(f, n - 1.001)
        i = int(f)
        u = f - i
        a, b = frames[i], frames[min(n - 1, i + 1)]
        p = P()
        ex = {}
        ta, tb = a.get("_talk"), b.get("_talk")
        if ta:                                             # a captured face (videomocap): jaw, smile, brows, blinks
            tb = tb or ta
            ex["talk"] = {k: ta[k] + (tb.get(k, ta[k]) - ta[k]) * u for k in ta}
            ex["mouth"] = ex["talk"].get("jaw", 0.0)
        for k in set(a) | set(b):
            if k.startswith("_"):
                continue
            va, vb = a.get(k, 0.0), b.get(k, a.get(k, 0.0))
            if k in ("an_u", "af_u", "ln_t", "lf_t", "torso", "head", "an_l", "af_l", "ln_s", "lf_s"):
                d_ = (vb - va + 180.0) % 360.0 - 180.0         # angles: the short way round
                p[k] = va + d_ * u
            else:
                p[k] = va + (vb - va) * u
        return p, ex
    return fn


def register():
    """Add every saved move to the action list (once, again when the folder changes)."""
    try:
        stamp = tuple(sorted((f, os.path.getmtime(os.path.join(MOVES, f))) for f in os.listdir(MOVES)))
    except OSError:
        stamp = ()
    if _LOADED["stamp"] == stamp:
        return
    _LOADED["stamp"] = stamp
    from .poses import ACTIONS, ActionSpec
    for nm, d in list_moves().items():
        if not d.get("frames"):
            continue
        secs = float(d.get("seconds", len(d["frames"]) / FPS))
        ACTIONS[nm] = ActionSpec(_action_fn(d), secs, blend_in=0.35)


def moves_from_model(path, base):
    """Every animation inside a model file -> saved moves (Mixamo exports one: "mixamo.com"). -> [names]"""
    from . import rigmodel
    out = []
    clips = rigmodel.clips_of(path)
    for i, (cname, secs) in enumerate(clips):
        if secs <= 0.2:
            continue
        nm = base if len(clips) == 1 or cname in ("mixamo.com", "clip", "Take 001") else f"{base}_{cname}"
        try:
            poses, sec, _n = clip_poses(path, i)
        except ValueError:
            continue
        out.append(save_move(nm, poses, sec, os.path.basename(path)))
    return out
