"""🐦 Sculpt 3D birds: every bird (engine/animals.py BIRDS: sparrow, crow, parrot, eagle, hen, duck, peacock, owl, pigeon,
kingfisher, myna, flamingo ...) modelled like clay - a teardrop body melted into the head, the breast colour, cartoon
eyes, a beak in two halves (it opens to sing / squawk), wings that fold or flap, a fan of tail feathers, thin legs
with three toes - and the species' own things: the hen's comb and wattle, the peacock's crest and eyed train, the
owl's face disc and ear tufts, the duck's flat bill and webbed feet, hooked beaks for the parrot and the eagle.

    "kalu": {"species": "crow", "look3d": "sculpt"}        (in a 3D story every bird is sculpted by itself)

Built once standing (cached), then moved every frame from the bird's pose: the body tilts (peck, lean), the head
turns on the neck, the lower beak opens (jaw), the wings flap in flight (each wing its own part), the tail tilts,
the legs tuck up when flying. Bones: body, head, beak, wing_l, wing_r, tail, legs.
"""
import math

import numpy as np

from . import sculpt3d as s3
from .sculpt3d import Sculpt
from . import sculpt_rig as srig
from .sculpt_animals import _to_metres, U, emit, _darker

LODS = {"far": (0.2, 0.09), "mid": (0.13, 0.06), "near": (0.085, 0.04)}     # cells: x body size, x head size
FINE = ("eyes", "beak", "beak_lo", "legs", "crest", "comb", "fan")
BONES = ("body", "head", "beak", "wing_l", "wing_r", "tail", "legs", "fan")


def head_r(sp, scale):
    """the sculpted head: a little smaller than the flat drawing's (a grown bird, not a chick) - the owl keeps its big one"""
    return sp["head"] * scale * (1.0 if sp.get("big_eyes") else 0.8)


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


def frame(b, hr, sp=None):
    """the rest skeleton (rig units: x forward, y up, z side): pivots of the moving parts (the same long legs / neck as
    engine/char3d.py BirdRig: "leg_k", "neck_k")"""
    sp = sp or {}
    lk, nk = float(sp.get("leg_k", 1.0)), float(sp.get("neck_k", 1.0))
    y0 = b * (0.9 + 0.5 * (lk - 1.0))
    hd = np.array([b * (0.75 + 0.12 * (nk - 1.0)), y0 + b * (0.45 + 0.55 * (nk - 1.0)), 0.0])
    return {"y0": y0, "body": np.array([0.0, y0, 0.0]), "neck": np.array([b * 0.55, y0 + b * 0.3, 0.0]),
            "head": hd, "beak": hd + np.array([hr * 0.82, -hr * 0.12, 0]),
            "wing_l": np.array([b * 0.25, y0 + b * 0.25, -b * 0.42]), "wing_r": np.array([b * 0.25, y0 + b * 0.25, b * 0.42]),
            "tail": np.array([-b * 0.62, y0 + b * 0.05, 0.0]), "legs": np.array([0.0, y0 - b * 0.4, 0.0]),
            "fan": np.array([-b * 0.55, y0 + b * 0.2, 0.0])}


def sculpt(c, sp, scale, jaw=0.0, blink=False):
    """the clay bird standing (rig units) -> Sculpt"""
    b, hr = sp["body"] * scale, head_r(sp, scale)
    F = frame(b, hr, sp)
    y0 = F["y0"]
    fur, belly = sp.get("fur", "#999999"), sp.get("belly", sp.get("fur", "#999999"))
    wing = sp.get("wing") if isinstance(sp.get("wing"), (str, tuple)) else _darker(fur, 0.8)
    headc = sp.get("headc") if isinstance(sp.get("headc"), (str, tuple)) else fur
    bc, bl = sp.get("beak", ("#f6a21e", 10))
    bl = bl * scale
    name = str(getattr(c, "species", ""))
    S = Sculpt()
    # ---- body: a teardrop (round breast, tapering to the tail), the breast colour underneath
    S.bone = "body"
    S.ellipsoid((b * 0.05, y0, 0), (b * 0.78, b * 0.6, b * 0.52), fur, k=b * 0.2, gloss=0.18)
    S.capsule((-b * 0.2, y0 + b * 0.02, 0), (-b * 0.75, y0 + b * 0.02, 0), b * 0.42, b * 0.14, fur, k=b * 0.2, gloss=0.18)
    S.ellipsoid((b * 0.32, y0 + b * 0.18, 0), (b * 0.42, b * 0.4, b * 0.4), fur, k=b * 0.2, gloss=0.18)     # chest / neck
    S.paint(lambda P: np.maximum(np.hypot((P[:, 0] - b * 0.25) / (b * 0.75), (P[:, 1] - (y0 - b * 0.15)) / (b * 0.62)) - 1.0,
                                 -P[:, 1] + y0 - b * 0.75) * b, belly, soft=b * 0.06)
    # ---- head (melted onto the neck - its own bone, so the neck bends softly)
    S.bone = "head"
    hd = F["head"]
    big = sp.get("big_eyes")
    if float(sp.get("neck_k", 1.0)) > 1.3:               # a long S-curved neck (flamingo): chest -> back -> forward to the head
        n0 = np.array([b * 0.45, y0 + b * 0.25, 0.0])
        S.tube([n0, n0 + np.array([-b * 0.05, (hd[1] - n0[1]) * 0.35, 0]), n0 + np.array([b * 0.25, (hd[1] - n0[1]) * 0.62, 0]),
                hd - np.array([hr * 0.6, hr * 0.5, 0])], b * 0.13, fur, k=b * 0.1, gloss=0.18)
    S.sphere(hd, hr * (1.08 if big else 1.0), headc, k=hr * 0.3, gloss=0.2)
    if big:                                              # the owl: a pale face disc and ear tufts
        S.ellipsoid(hd + np.array([hr * 0.55, -hr * 0.05, 0]), (hr * 0.45, hr * 0.85, hr * 0.95), belly, k=hr * 0.15, gloss=0.15)
        for s_ in (-1, 1):
            S.capsule(hd + np.array([0, hr * 0.75, s_ * hr * 0.5]), hd + np.array([-hr * 0.15, hr * 1.35, s_ * hr * 0.62]),
                      hr * 0.22, hr * 0.05, headc, k=hr * 0.1, gloss=0.15)
    if name == "myna":                                   # the myna's yellow eye patch
        for s_ in (-1, 1):
            S.paint_ball(hd + np.array([hr * 0.5, hr * 0.15, s_ * hr * 0.65]), hr * 0.32, "#f6c21e", soft=hr * 0.04)
    if sp.get("comb"):                                   # the hen: a red comb on top, a wattle under the beak
        for k_ in range(4):
            S.sphere(hd + np.array([hr * (0.45 - 0.3 * k_), hr * (0.95 + 0.06 * (k_ % 2)), 0]), hr * 0.24, "#d62828",
                     group="comb", k=hr * 0.08, gloss=0.4)
        S.ellipsoid(hd + np.array([hr * 0.75, -hr * 0.6, 0]), (hr * 0.14, hr * 0.26, hr * 0.12), "#d62828", group="comb",
                    k=hr * 0.05, gloss=0.4)
    if sp.get("crest"):                                  # the peacock's crest: thin stalks with little fans
        for k_ in (-1, 0, 1):
            top = hd + np.array([-hr * 0.1 + k_ * hr * 0.15, hr * 1.7, k_ * hr * 0.2])
            S.tube([hd + np.array([0, hr * 0.8, k_ * hr * 0.08]), top], hr * 0.04, _darker(fur, 0.8), group="crest", k=0.0)
            S.sphere(top, hr * 0.13, fur, group="crest", k=0.0, gloss=0.5)
    # eyes
    for s_ in (-1, 1):
        er = hr * (0.36 if big else 0.2)
        dv = np.array([0.55 if not big else 0.85, 0.25, s_ * (0.75 if not big else 0.42)])
        dv /= np.linalg.norm(dv)
        p = hd + dv * hr * (0.88 if not big else 0.98)
        S.sphere(p, er, "#fbfaf6", group="eyes", k=0.0, gloss=0.9)
        look = dv * 0.5 + np.array([0.5, 0, 0])
        S.paint_cone(p, look, 55 if big else 40, "#f08c00" if big else "#3a2410", group="eyes", soft=er * 0.03)
        S.paint_cone(p, look, 26 if big else 24, "#0b0705", group="eyes", soft=er * 0.03)
        S.paint_cone(p, look + np.array([0, 0.5, 0]), 9, "#ffffff", group="eyes", soft=er * 0.02, gloss=1.0)
        if blink:
            S.sphere(p, er * 1.1, headc, group="eyes", k=0.0, gloss=0.2)
    # ---- the beak: the upper half on the head, the lower half on its own bone (it opens)
    S.bone = "head"
    base = F["beak"]
    tip = base + np.array([bl, -bl * 0.08, 0])
    hooked = name in ("parrot", "eagle")
    if sp.get("bent_beak"):                              # the flamingo: a thick beak bent down halfway, a black tip
        S.tube([base, base + np.array([bl * 0.45, -hr * 0.05, 0]), base + np.array([bl * 0.75, -bl * 0.45, 0])], hr * 0.2,
               "#f4d9e2", group="beak", k=hr * 0.05, gloss=0.4)
        S.paint(lambda P, c_=base + np.array([bl * 0.7, -bl * 0.35, 0]): np.linalg.norm(P - c_, axis=1) - bl * 0.22, bc,
                group="beak", soft=hr * 0.03)
    elif sp.get("flat_beak"):                            # a duck's bill: flat and wide
        S.ellipsoid(base + np.array([bl * 0.5, 0, 0]), (bl * 0.6, hr * 0.12, hr * 0.32), bc, group="beak", k=hr * 0.05, gloss=0.4)
    elif hooked:                                         # a hooked beak (parrot, eagle)
        S.tube([base + np.array([0, hr * 0.12, 0]), base + np.array([bl * 0.55, hr * 0.15, 0]),
                base + np.array([bl * 0.85, -hr * 0.15, 0])], hr * 0.18, bc, group="beak", k=hr * 0.08, gloss=0.5)
        S.capsule(base, base + np.array([bl * 0.5, hr * 0.05, 0]), hr * 0.3, hr * 0.16, bc, group="beak", k=hr * 0.08, gloss=0.5)
    else:
        S.capsule(base + np.array([0, hr * 0.06, 0]), tip + np.array([0, hr * 0.03, 0]), hr * 0.26, hr * 0.03, bc,
                  group="beak", k=hr * 0.04, gloss=0.5)
    S.bone = "beak"
    lo_tip = base + np.array([bl * (0.55 if hooked else 0.9), -hr * 0.12, 0])
    if sp.get("flat_beak"):
        S.ellipsoid(base + np.array([bl * 0.45, -hr * 0.14, 0]), (bl * 0.55, hr * 0.08, hr * 0.28), _darker(bc, 0.9),
                    group="beak_lo", k=hr * 0.04, gloss=0.4)
    else:
        S.capsule(base + np.array([0, -hr * 0.08, 0]), lo_tip, hr * 0.2, hr * 0.03, _darker(bc, 0.9), group="beak_lo",
                  k=hr * 0.04, gloss=0.45)
    if jaw > 0.1:                                        # (the mouth inside, seen when it opens)
        S.sphere(base + np.array([bl * 0.15, -hr * 0.05, 0]), hr * 0.16, "#8a2a2a", group="beak_lo", k=hr * 0.03)
    # ---- wings: folded along the sides (each its own part: it flaps on its own bone)
    for s_, wn in ((-1, "wing_l"), (1, "wing_r")):
        S.bone, S.group = wn, wn
        sh = F[wn]
        S.ellipsoid(sh + np.array([-b * 0.3, -b * 0.12, s_ * b * 0.08]), (b * 0.62, b * 0.36, b * 0.12), wing, k=b * 0.08,
                    gloss=0.2)
        for k_ in range(4):                              # the flight feathers at the back edge
            r0 = sh + np.array([-b * (0.45 + 0.08 * k_), -b * (0.15 + 0.05 * k_), s_ * b * 0.1])
            S.capsule(r0, r0 + np.array([-b * 0.45, -b * 0.05, 0]), b * 0.09, b * 0.03, _darker(wing, 0.85), k=b * 0.05,
                      gloss=0.2)
    # ---- tail: a fan of feathers (a long train for the peacock, long for the parrot)
    S.bone, S.group = "tail", "tail"
    tb = F["tail"]
    long_ = 2.8 if sp.get("fan") else (1.8 if sp.get("tail_long") else 1.15)
    if sp.get("comb"):                                   # the hen: an upright curved tail
        for k_ in range(5):
            a_ = math.radians(70 + 14 * (k_ - 2))
            S.tube([tb, tb + np.array([-b * 0.25, b * 0.35, (k_ - 2) * b * 0.06]),
                    tb + np.array([-b * 0.55 * math.cos(a_ - 0.4), b * 0.55 * math.sin(a_), (k_ - 2) * b * 0.1])], b * 0.08,
                   wing, k=b * 0.05, gloss=0.25)
    else:
        for k_ in range(5):
            z_ = (k_ - 2) * b * (0.09 + 0.05 * long_)
            S.capsule(tb, tb + np.array([-b * long_, -b * 0.1 * long_ ** 0.5, z_]), b * 0.14, b * 0.08 + 0.02 * b * long_,
                      wing if k_ % 2 else _darker(wing, 0.88), k=b * 0.08, gloss=0.25)
        if sp.get("fan"):                                # the peacock's train: eye-spots along it
            for k_ in range(12):
                f_ = 0.35 + 0.6 * (k_ // 3) / 3.0
                z_ = ((k_ % 3) - 1) * b * 0.4 * f_
                c_ = tb + np.array([-b * long_ * f_, -b * 0.1 * long_ ** 0.5 * f_ + b * 0.08, z_])
                S.paint_ball(c_, b * 0.12, "#e0b020", soft=b * 0.02)
                S.paint_ball(c_, b * 0.07, "#1a3a8a", soft=b * 0.015)
    if sp.get("fan"):                                    # the peacock's fan: folded away inside, opened by its bone (dance)
        S.bone, S.group = "fan", "fan"
        fb = F["fan"]
        for k_ in range(31):
            a_ = math.radians(-8 + 196 * k_ / 30.0)                # a half-wheel standing up behind the body
            d_ = np.array([-0.25, math.sin(a_), math.cos(a_)])
            d_ /= np.linalg.norm(d_)
            tip = fb + d_ * b * 2.4
            S.capsule(fb + d_ * b * 0.3, tip, b * 0.04, b * 0.13, "#1f7a58" if k_ % 2 else "#2a8f66", k=b * 0.05, gloss=0.35)
            for c_, r_ in ((tip, 1.0), (fb + d_ * b * 1.6, 0.7)) if k_ % 2 == 0 else ((tip, 1.0),):   # eye-spots
                S.paint_ball(c_, b * 0.2 * r_, "#e0b020", soft=b * 0.02)
                S.paint_ball(c_, b * 0.15 * r_, "#1a8a8a", soft=b * 0.015)
                S.paint_ball(c_, b * 0.1 * r_, "#14246a", soft=b * 0.01)
    # ---- legs and feet (three toes forward, one back; webbed for the duck)
    S.bone, S.group = "legs", "legs"
    lc = "#e8862e" if name in ("duck", "hen", "eagle", "pigeon", "myna") else ("#d9607f" if name == "flamingo" else "#7a6a5a")
    lw = max(b * (0.075 if float(sp.get("leg_k", 1.0)) > 1.5 else 0.055), 0.8)    # (long legs: thick enough to see far)
    S.leg_w = lw
    for s_ in (-1, 1):
        top = np.array([b * 0.02, y0 - b * 0.35, s_ * b * 0.22])
        ank = np.array([b * 0.02, b * 0.05, s_ * b * 0.24])
        if float(sp.get("leg_k", 1.0)) > 1.5:            # long legs: the "knee" that bends backwards is really the ankle
            mid = np.array([-b * 0.12, (top[1] + ank[1]) * 0.5, s_ * b * 0.23])
            S.capsule(top, mid, lw * 1.2, lw, lc, k=lw * 0.4, gloss=0.3)
            S.sphere(mid, lw * 1.35, lc, k=lw * 0.4, gloss=0.3)
            S.capsule(mid, ank, lw, lw * 0.9, lc, k=lw * 0.4, gloss=0.3)
        else:
            S.capsule(top, ank, lw * 1.4, lw, lc, k=lw * 0.5, gloss=0.3)
        for dz in (-0.4, 0.0, 0.4):
            S.capsule(ank, ank + np.array([b * 0.28, -b * 0.04, dz * b * 0.3]), lw * 0.8, lw * 0.55, lc, k=lw * 0.4, gloss=0.3)
        S.capsule(ank, ank + np.array([-b * 0.16, -b * 0.04, 0]), lw * 0.7, lw * 0.5, lc, k=lw * 0.4, gloss=0.3)
        if sp.get("flat_beak"):
            S.ellipsoid(ank + np.array([b * 0.17, -b * 0.03, 0]), (b * 0.16, b * 0.015, b * 0.16), lc, k=lw * 0.3)
    S.group, S.bone = "body", "body"
    S.no_shadow = {"eyes", "beak", "beak_lo", "crest", "comb", "legs"}
    return S, F


# ---------------------------------------------------------------------------- cache, pose, draw
def pieces(c, lod, jaw, blink):
    sp, scale = dict(c.animal), float(c.scale)
    b, hr = sp["body"] * scale, head_r(sp, scale)
    cb, ch = LODS.get(lod, LODS["mid"])
    j = round(min(1.0, float(jaw)) * 2) / 2.0
    key_card = {"species": c.species, "scale": scale,
                "sp": {k: v for k, v in sp.items() if isinstance(v, (str, int, float, bool, list, tuple))}}

    def make():
        S, F = sculpt(c, sp, scale, jaw=j, blink=blink)
        S = _to_metres(S)
        S.res = {gn: (hr * ch * U if gn in FINE else b * cb * U * (0.7 if gn in ("tail", "wing_l", "wing_r") else 1.0))
                 for gn in S.groups()}
        # the legs: cells sized to the leg (tiny faces on a long thin leg vanish from far away - the scene skips them)
        S.res["legs"] = max(hr * ch, getattr(S, "leg_w", b * 0.05) * (0.5 if lod == "near" else 0.75)) * U
        parts = S.build(cell=b * cb * U, quads=True)
        skin = s3.rgb(sp.get("fur", "#999999"))
        models = []
        for p in parts:
            solid = [x for x in S.shapes if x.group == p.name and x.mode == "add"]
            D = np.stack([x.d(p.V) for x in solid])
            Wt = np.exp(-(D - D.min(axis=0)) / max(b * U * 0.1, 1e-6))
            W = np.zeros((len(p.V), len(BONES)))
            for i, x in enumerate(solid):
                W[:, BONES.index(x.bone if x.bone in BONES else "body")] += Wt[i]
            W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
            models.append(srig.Model((p.V / U).astype(np.float32), p.T.astype(np.int32), p.N.astype(np.float32),
                                     np.clip(p.C, 0, 1).astype(np.float32), p.G.astype(np.float32), W.astype(np.float32),
                                     skin))
        return models, {"bones": list(BONES)}
    return srig._cached(srig._key(key_card, "bird6", lod, j, int(bool(blink))), make)


def bone_moves(F, rig, t):
    """the pose -> {bone: (R, t)}: the body tilts about its middle and rides at the rig's height, the head turns on the
    neck, the lower beak opens, the wings fold / flap about the shoulders, the tail tilts, the legs tuck in flight"""
    pose = getattr(rig, "pose", {}) or {}
    yw = float(getattr(rig, "y0", F["y0"]))
    flying = bool(getattr(rig, "flying", False))
    a_body = -math.radians(float(pose.get("body", -12.0)) + 12.0)
    if flying:
        a_body = -math.radians(8.0)                       # (flying: level, a little nose down)
    Rb = _rz(a_body)
    cw = np.array([0.0, yw, 0.0])
    moves = {"body": (Rb, cw - Rb @ F["body"])}

    def child(name, R_local, parent="body"):
        Rp, tp = moves[parent]
        pv = F[name]
        R = Rp @ R_local
        moves[name] = (R, (Rp @ pv + tp) - R @ pv)
    # head: turns on the neck (the pivot is the neck, not the head's middle)
    Rp, tp = moves["body"]
    Rh = Rp @ _rz(math.radians(float(pose.get("head", 0.0))) * 0.6)
    moves["head"] = (Rh, (Rp @ F["neck"] + tp) - Rh @ F["neck"])
    ms = getattr(rig, "mouth_shape", None) or {}
    jaw = max(float(pose.get("jaw", 0.0)), float(ms.get("jaw", 0.0)) * (1 - float(ms.get("closed", 0.0))))
    child("beak", _rz(-math.radians(28.0) * min(1.0, jaw)), "head")
    wing_open = float(pose.get("wing", 0.0))
    if flying:
        flap = math.sin(t * 2 * math.pi * 4.5)
        up = math.radians(10 + 55 * flap)
    else:
        up = math.radians(70 * wing_open)
    for s_, wn in ((-1, "wing_l"), (1, "wing_r")):
        child(wn, _rx(-s_ * up))
    child("tail", _rz(math.radians(float(pose.get("tail", 10.0)) - 10.0) * 0.6))
    disp = max(0.0, min(1.0, float(pose.get("display", 0.0))))
    # the fan opens: it grows out of the body (hidden at 2 %) and the closed train behind shrinks into it
    child("fan", np.eye(3) * (0.02 + 0.98 * disp), "body")
    if disp > 0.0:
        R, tt = moves["tail"]
        k = 1.0 - 0.95 * disp
        pv = F["tail"]
        moves["tail"] = (R * k, (R @ pv + tt) - (R * k) @ pv)
    tuck = 1.0 if flying else min(1.0, max(0.0, float(pose.get("leg", 0.0))))
    child("legs", _rz(math.radians(75.0) * tuck))
    # (the legs stay upright under the body when it tilts: undo the body's tilt for them on the ground)
    if not flying:
        Rl = _rz(math.radians(75.0) * tuck)
        hip = Rb @ F["legs"] + moves["body"][1]
        moves["legs"] = (Rl, hip - Rl @ F["legs"])
    return moves


def code_fn(pen, rig, t, state):
    """the character code for a bird with "look3d": "sculpt" (same call as every 3D bird file)"""
    c = rig._c
    sp = dict(c.animal)
    b = sp["body"] * float(c.scale)
    F = frame(b, head_r(sp, float(c.scale)), sp)
    height = max(1.0, b * 2.0, F["head"][1] + b * 0.4)
    px = srig.screen_height(1.0, height)
    if px is None:
        px = (getattr(pen, "px_unit", None) or 0.5) * height
    lod = "near" if px > 160 else "mid" if px > 60 else "far"
    models, meta = pieces(c, lod, 0.0, bool(getattr(rig, "blink", False)))       # (the beak opens on its bone)
    emit(pen, models, meta["bones"], bone_moves(F, rig, t))
    return None
