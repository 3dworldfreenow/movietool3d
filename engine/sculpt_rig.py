"""🦴 Sculpt 3D characters in the videos: the clay figure (engine/sculpt_people.py) is sculpted ONCE in its rest pose
and kept (memory + cache/sculpt/), then every frame it is bent by the SAME skeleton every 3D person uses
(char3d's rig: hips, knees, feet, shoulders, elbows, hands, chest, head) - so every action works: walk, run, sit,
dance, fight, ride ... The face is sculpted again for each expression and mouth shape (talking) - small, cached.

    "golu_dada": {..., "look3d": "sculpt", "sculpt": {<character card>}}     (no card: the story card is used)

How: every clay shape belongs to a bone (thigh, shin, upper arm, forearm, spine, head); each vertex gets smooth
weights from how near it is to the shapes of each bone (so knees and elbows bend softly); a bone's move is the
turn that takes its rest direction to the rig's direction now, plus the shift that puts its root on the joint
(linear blend skinning). The faces go to the scene's own renderer: the same sun, night lights, shadows, camera.
"""
import hashlib
import json
import math
import os

import numpy as np

from . import sculpt3d as s3
from . import sculpt_people as sp

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(HERE, "cache", "sculpt")
# cell sizes (metres) per detail level: the body, the head, and the small parts (eyes, lids, brows, glasses ...)
LODS = {"far": (0.036, 0.02, 0.009), "mid": (0.026, 0.014, 0.0065), "near": (0.016, 0.009, 0.0042)}
SMALL = ("eyes", "lids", "brows", "glasses", "mustache", "mouth", "props", "shoes", "hat", "hands")
_MEM = {}
OUTLINE = [False]                                    # the ink line round the figure (off in scenes: the scene sort makes it hatch through)
BONES = ("spine", "head", "l_thigh", "l_shin", "r_thigh", "r_shin", "l_upper_arm", "l_forearm", "r_upper_arm",
         "r_forearm")
SEGMENTS = {"spine": ("pelvis", "chest"), "l_thigh": ("l_hip", "l_knee"), "l_shin": ("l_knee", "l_ankle"),
            "r_thigh": ("r_hip", "r_knee"), "r_shin": ("r_knee", "r_ankle"), "l_upper_arm": ("l_shoulder", "l_elbow"),
            "l_forearm": ("l_elbow", "l_wrist"), "r_upper_arm": ("r_shoulder", "r_elbow"), "r_forearm": ("r_elbow", "r_wrist")}
# the emotion -> the sculpted face; "smile" is the open laugh (teeth showing): only laughing / excited, never
# "happy" - a happy person keeps a closed smile and opens the mouth only while talking (the jaw from the voice)
FACES = {"happy": "happy", "laughing": "smile", "excited": "smile", "in_love": "happy", "proud": "happy",
         "scared": "surprised", "afraid": "surprised", "shocked": "surprised", "surprised": "surprised",
         "sad": "sad", "crying": "sad", "gloomy": "sad", "angry": "angry", "sleeping": "sleeping",
         "neutral": "neutral", "thinking": "neutral", "tired": "neutral"}


class Model:
    """one cached piece: verts (rest, metres), quads, normals, colours (sRGB), gloss, bone weights (N x bones)"""

    def __init__(self, V, Q, N, C, G, W, skin):
        self.V, self.Q, self.N, self.C, self.G, self.W, self.skin = V, Q, N, C, G, W, skin


CACHE_VERSION = 7                                    # bump when the sculpting changes: old cached pieces are made again


def _key(card, *bits):
    h = hashlib.sha1(json.dumps([CACHE_VERSION, card], sort_keys=True, default=str).encode()).hexdigest()[:16]
    return h + "_" + "_".join(str(b) for b in bits)


def _weights(S, part, tau=0.02):
    """bone weights for the vertices of one part: each shape pulls its own bone, the nearer the stronger"""
    solid = [x for x in S.shapes if x.group == part.name and x.mode == "add"]
    D = np.stack([x.d(part.V) for x in solid])
    W = np.exp(-(D - D.min(axis=0)) / tau)
    out = np.zeros((len(part.V), len(BONES)))
    for i, x in enumerate(solid):
        out[:, BONES.index(x.bone if x.bone in BONES else "spine")] += W[i]
    return out / np.maximum(out.sum(axis=1, keepdims=True), 1e-9)


def _models(S, parts, skin):
    out = []
    for p in parts:
        W = _weights(S, p)
        col = np.clip(p.C, 0, 1)
        out.append(Model(p.V.astype(np.float32), p.T.astype(np.int32), p.N.astype(np.float32), col.astype(np.float32),
                         p.G.astype(np.float32), W.astype(np.float32), skin))
    return out


def _cached(key, make):
    if key in _MEM:
        return _MEM[key]
    path = os.path.join(CACHE_DIR, key + ".npz")
    if os.path.exists(path):
        try:
            z = np.load(path, allow_pickle=False)
            n = int(z["n"])
            got = ([Model(*(z[f"{k}{i}"] for k in ("V", "Q", "N", "C", "G", "W")), z["skin"]) for i in range(n)],
                   json.loads(str(z["joints"])))
            _MEM[key] = got
            return got
        except Exception:                               # noqa: BLE001 - a broken cache file: make it again
            pass
    models, joints = make()
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        arrs = {"n": len(models), "skin": models[0].skin if models else np.zeros(3), "joints": json.dumps(joints)}
        for i, m in enumerate(models):
            arrs.update({f"V{i}": m.V, f"Q{i}": m.Q, f"N{i}": m.N, f"C{i}": m.C, f"G{i}": m.G, f"W{i}": m.W})
        tmp = f"{path}.{os.getpid()}.tmp.npz"          # (each render worker its own temporary file)
        np.savez_compressed(tmp, **arrs)
        os.replace(tmp, path)
    except OSError:
        pass
    _MEM[key] = (models, joints)
    return _MEM[key]


def _joints_json(S):
    return {k: (v.tolist() if hasattr(v, "tolist") else float(v)) for k, v in S.joints.items()}


_JOINTS = {}


def joints_of(card):
    """the rest skeleton only (no mesh): cheap, kept in memory"""
    full, _ = sp.check(card)
    k = _key(full, "joints")
    if k not in _JOINTS:
        _JOINTS[k] = _joints_json(sp.person(full, pose="rest", expr="neutral"))
    return _JOINTS[k]


def pieces(card, lod="mid", face="neutral", jaw=0.0, blink=False):
    """-> ([Model] body + head for this face, joints) - made once, then from the cache"""
    full, _ = sp.check(card)
    cb, ch, cs = LODS.get(lod, LODS["mid"])
    skin = s3.rgb(full["skin"])

    def cells(S, main):
        S.res = {g: (cs if g in SMALL else main) for g in S.groups()}

    def body():
        S = sp.person(full, pose="rest", expr="neutral")
        cells(S, cb)
        cut = S.joints["neck_cut"]
        parts = S.build(cell=cb, region=(-1.0, cut + 0.012), quads=True)
        return _models(S, parts, skin), _joints_json(S)
    bm, joints = _cached(_key(full, "body", lod), body)
    j = round(float(jaw) * 2) / 2.0                        # three mouth openings: shut, half, open

    def head():
        S = sp.person(full, pose="rest", expr=face, jaw=j, blink=blink)
        cells(S, ch)
        cut = S.joints["neck_cut"]
        parts = S.build(cell=ch, region=(cut - 0.012, 9.0), quads=True)
        return _models(S, parts, skin), _joints_json(S)
    hm, _ = _cached(_key(full, "head", lod, face, j, int(bool(blink))), head)
    return bm + hm, joints


# ---------------------------------------------------------------------------- posing with the rig
def _q(v):
    """sculpt (x side, y up, z forward) -> rig's local frame (x forward, y up, z side; the left side is the near one)"""
    v = np.asarray(v, float)
    return np.stack([v[..., 2], v[..., 1], v[..., 0]], -1)


def _rot_between(a, b):
    a = a / max(np.linalg.norm(a), 1e-9)
    b = b / max(np.linalg.norm(b), 1e-9)
    v = np.cross(a, b)
    c = float(a @ b)
    if c < -0.9999:                                      # opposite: turn half round any side axis
        ax = np.cross(a, [0, 0, 1.0]) if abs(a[2]) < 0.9 else np.cross(a, [1.0, 0, 0])
        ax /= np.linalg.norm(ax)
        return 2 * np.outer(ax, ax) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def bone_moves(joints, rig):
    """-> scale k (story units per metre) and {bone: (R, t)}: the rig gives the DIRECTION of every bone, the
    character keeps its OWN proportions - a chain from the hips: spine, then head and arms on it, legs below"""
    J = {k: np.array(v) for k, v in joints.items() if isinstance(v, list)}
    near_leg, far_leg = rig.leg("near"), rig.leg("far")
    near_arm, far_arm = rig.arm("near"), rig.arm("far")
    now = {"pelvis": rig.hip, "chest": rig.chest, "l_hip": near_leg[0], "l_knee": near_leg[1], "l_ankle": near_leg[2],
           "r_hip": far_leg[0], "r_knee": far_leg[1], "r_ankle": far_leg[2], "l_shoulder": near_arm[0],
           "l_elbow": near_arm[1], "l_wrist": near_arm[2], "r_shoulder": far_arm[0], "r_elbow": far_arm[1],
           "r_wrist": far_arm[2]}
    now = {k: np.array(v, float) for k, v in now.items()}
    leg0 = sum(np.linalg.norm(J[b] - J[a]) for a, b in (("l_hip", "l_knee"), ("l_knee", "l_ankle")))
    leg1 = sum(np.linalg.norm(now[b] - now[a]) for a, b in (("l_hip", "l_knee"), ("l_knee", "l_ankle")))
    k = leg1 / max(leg0, 1e-6)                          # the legs set the size: the feet stay on the ground
    rest = {n: _q(v) * k for n, v in J.items()}
    moves = {}

    def put(bone, root_now):
        a, b = SEGMENTS[bone]
        R = _rot_between(rest[b] - rest[a], now[b] - now[a])
        moves[bone] = (R, root_now - R @ rest[a])
        return R
    # the spine stands on the rig's hips; legs hang from its hip points
    Rs = put("spine", now["pelvis"])
    Ts = moves["spine"][1]
    for side in ("l", "r"):
        hip = Rs @ rest[side + "_hip"] + Ts
        Rt = put(side + "_thigh", hip)
        knee = Rt @ rest[side + "_knee"] + moves[side + "_thigh"][1]
        put(side + "_shin", knee)
        sh = Rs @ rest[side + "_shoulder"] + Ts               # arms from the character's own shoulders
        Ru = put(side + "_upper_arm", sh)
        el = Ru @ rest[side + "_elbow"] + moves[side + "_upper_arm"][1]
        put(side + "_forearm", el)
    # the head turns with the rig's nod, on the character's own neck
    fwd = np.array(rig.fwd, float)
    up = np.array(rig.up, float)
    side_ = np.cross(fwd, up)
    Rh = np.stack([fwd, up, side_], 1)
    neck = rest["chest"] + (rest["head"] - rest["chest"]) * 0.45
    pivot = Rs @ neck + Ts
    moves["head"] = (Rh @ Rs if False else Rh, pivot - Rh @ neck)
    return k, moves


def pose_verts(m, k, moves):
    """linear blend skinning: every vertex = the weighted sum of where each of its bones would put it"""
    V0 = _q(m.V) * k
    N0 = _q(m.N)
    V = np.zeros_like(V0)
    N = np.zeros_like(N0)
    for bi, bone in enumerate(BONES):
        w = m.W[:, bi]
        if not w.any():
            continue
        R, t = moves[bone]
        V += w[:, None] * (V0 @ R.T + t)
        N += w[:, None] * (N0 @ R.T)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    return V, N


# ---------------------------------------------------------------------------- the character code hook
def card_of(c):
    spec = dict(getattr(c, "spec", None) or {})
    card = spec.get("sculpt") if isinstance(spec.get("sculpt"), dict) else spec
    card = dict(card)
    card.setdefault("gender", getattr(c, "gender", "male"))
    card.setdefault("age", getattr(c, "age", "adult"))
    return card


def screen_height(k, height_m=1.6):
    """how tall the figure is on screen (pixels), from the real scene camera (None outside a 3D scene)"""
    from . import code3d
    if code3d.CURRENT is None:
        return None
    try:
        scene, cam, o = code3d.CURRENT[:3]
        a = scene.project(cam, o.X, o.Y, o.Z)
        b = scene.project(cam, o.X, o.Y + k * height_m, o.Z)
        if a is None or b is None:
            return None
        return abs(a[1] - b[1]) / max(0.5, float(getattr(scene, "S", 1.0) or 1.0))   # in 360p-ish pixels
    except Exception:                                   # noqa: BLE001
        return None


def lod_for(pen, k, height_m=1.6):
    px = screen_height(k, height_m)
    if px is None:
        px = (getattr(pen, "px_unit", None) or 0.5) * k * height_m
    return "near" if px > 230 else "mid" if px > 95 else "far"


def code_fn(pen, rig, t, state):
    """the character code for "look3d": "sculpt" (same call as every 3D character file)"""
    from .code3d import Face, _inv_t
    c = rig._c
    card = card_of(c)
    face = FACES.get(str(getattr(rig, "face", "neutral")), "neutral")
    jaw = float((getattr(rig, "mouth_shape", None) or {}).get("jaw", 0.0))
    blink = float(getattr(rig, "lid", 0.0)) > 0.5
    joints0 = joints_of(card)
    k, moves = bone_moves(joints0, rig)
    from . import live3d
    models, joints = pieces(card, live3d.cap(lod_for(pen, k, joints0.get("top", 1.6))), face, jaw, blink)
    R9, T3 = pen._m
    if live3d.LIVE[0]:                                   # 🎥 live 3D play: the bones go to the browser, not the faces
        live3d.RIG_PENDING[id(pen.faces)] = dict(models=models, k=k, moves=moves, bones=BONES, M=R9, T=T3,
                                                 top=joints0.get("top", 1.6), alpha=pen.opacity, q=1)
        return None
    M = np.array(R9, float).reshape(3, 3)
    T = np.array(T3, float)
    NM = np.array(_inv_t(R9), float).reshape(3, 3)
    ink = (0.16, 0.1, 0.08, pen.opacity)
    hull = (0.9 * getattr(rig, "s", 1.0)) if OUTLINE[0] else 0.0
    for m in models:
        if not len(m.Q):
            continue
        V, N = pose_verts(m, k, moves)
        W = V @ M.T + T
        NW = N @ NM.T
        NW /= np.maximum(np.linalg.norm(NW, axis=1, keepdims=True), 1e-9)
        Q = m.Q
        col = m.C[Q].mean(axis=1)
        fn = NW[Q].sum(axis=1)
        fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
        is_skin = np.abs(col - m.skin[None, :]).max(axis=1) < 0.06
        gl = m.G[Q].mean(axis=1)
        Wl, NWl, coll, fnl = W.tolist(), NW.tolist(), col.tolist(), fn.tolist()
        for i, q in enumerate(Q.tolist()):
            cc = coll[i]
            mat = (0.0, 1.0, 0.0, 1) if is_skin[i] else ((0.6, 40.0, 0.0) if gl[i] > 0.6 else None)
            pen.faces.append(Face([Wl[q[0]], Wl[q[1]], Wl[q[2]], Wl[q[3]]], tuple(fnl[i]), (cc[0], cc[1], cc[2], pen.opacity),
                                  True, mat=mat, vn=[NWl[q[0]], NWl[q[1]], NWl[q[2]], NWl[q[3]]]))
        if hull and len(Q) > 60:                           # 🖋 the ink line: the grown far side, drawn behind
            Hv = (W + NW * hull).tolist()
            for i, q in enumerate(Q.tolist()):
                n = fnl[i]
                pen.faces.append(Face([Hv[q[3]], Hv[q[2]], Hv[q[1]], Hv[q[0]]], (-n[0], -n[1], -n[2]), ink, True))
    return None
