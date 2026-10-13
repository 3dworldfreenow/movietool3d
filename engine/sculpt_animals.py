"""🐯 Sculpt 3D animals: every four-legged animal (engine/animals.py QUADS: tiger, cow, dog, goat, elephant, horse ...)
modelled like clay from its own skeleton - one smooth body (belly, legs, neck, head and snout melted together),
cartoon eyes with a catchlight, ears / horns / antlers / trunk / tusks / mane / tail by species, stripes, spots and
patches painted on - then bent every frame by the SAME skeleton the engine walks, runs, sits and pounces with.

    "gauri": {"species": "cow", "look3d": "sculpt"}        (in a 3D story every animal is sculpted by itself)

The model is built once in the rest pose, in the rig's own units (story units: a person is ~300 tall), and cached.
Bones: spine (hips -> shoulders), neck, head, tail, and two per leg (top -> knee, knee -> paw); each vertex follows
the bones of the shapes nearest to it (the same skinning as the sculpted people, engine/sculpt_rig.py).
"""
import math

import numpy as np

from . import sculpt3d as s3
from .sculpt3d import Sculpt
from . import sculpt_rig as srig

FINE = ("eyes", "lids", "horns", "tail", "teeth")              # thin parts: meshed with the finer (head) cell
LODS = {"far": (0.24, 0.1), "mid": (0.15, 0.065), "near": (0.095, 0.042)}   # cells: x body girth, x head size


CATS = ("tiger", "lion", "leopard", "cheetah", "cat")


def make_cute(sp):
    """🧸 the cartoon proportions (a game rule, not anatomy): a big round head, a short chubby body, short thick legs, a
    small muzzle - the cute-animal look. Changes the species numbers, so the skeleton, the walk (stride from the leg
    length) and the feet on the ground all follow. "animal_style": "real" in settings keeps the true proportions."""
    if sp.get("_cute"):
        return sp
    sp = dict(sp)
    sp["_cute"] = True
    sp["body"] = sp["body"] * 0.78
    sp["thigh"], sp["shin"] = sp["thigh"] * 0.7, sp["shin"] * 0.62
    sp["girth"] = sp["girth"] * 1.22
    sp["neck"] = sp["neck"] * (0.75 if sp.get("neck_angle", 32) > 45 else 0.45)   # (horses and giraffes keep a neck)
    sp["head"] = sp["head"] * (1.3 if sp.get("scale", 1.0) >= 1.3 else 1.6)       # (giants: a smaller step)
    sp["leg_w"] = sp.get("leg_w", sp["girth"] / 1.22 * 0.34) * 1.45
    sp["neck_w"] = sp["neck_w"] * 1.3
    sl, sw = sp.get("snout", (20, 18))
    sp["snout"] = (sl * 0.55, sw * 1.05)
    return sp


LEAN = ("tiger", "lion", "leopard", "cheetah", "cat", "dog", "wolf", "fox", "deer", "horse", "zebra", "donkey", "giraffe",
        "goat", "camel")                                  # runners and hunters: a deep chest and a tucked-up waist
FIERCE = ("tiger", "lion", "leopard", "cheetah", "wolf")   # the hunters: a fierce face by default


def make_fierce(sp):
    """🐅 a powerful hunter (a look, not anatomy): heavy shoulders, thick legs, big paws, a broad head. The face (sculpt)
    gets a heavy brow angled down to the nose, narrowed eyes with small pupils, and fangs when it roars or is angry."""
    if sp.get("_fierce"):
        return sp
    sp = dict(sp)
    sp["_fierce"] = True
    sp["girth"] = sp["girth"] * 1.08
    sp["leg_w"] = sp.get("leg_w", sp["girth"] / 1.08 * 0.34) * 1.3
    sp["head"] = sp["head"] * 1.1
    sp["neck_w"] = sp["neck_w"] * 1.15
    return sp


def _darker(c, k):
    r, g, b = s3.rgb(c)
    return (r * k, g * k, b * k)


def rest_rig(c):
    """the animal's skeleton standing still (the shape is modelled on it)"""
    from . import char3d
    p, _ = char3d.pose_at(c, "idle", 0.0)
    return char3d.make_rig(c, p, "neutral", 0.0, False, 0.0)


def _tail_points(rig):
    sp, g = rig.sp, rig.g
    kind = sp.get("tail")
    tl = {"long": 1.0, "long_up": 0.8, "bushy": 0.8, "tuft": 0.75, "tuft_thin": 0.5, "long_hair": 0.8,
          "curve": 0.6, "short_up": 0.2, "puff": 0.1, "curly": 0.25}.get(kind, 0.5) * rig.length
    ta, wag = math.radians(rig.tail), math.radians(rig.wag)
    root = rig.along(-0.05)
    root = (root[0] - g * 0.4, root[1] + g * 0.35, 0.0)
    hang = kind in ("long_hair", "tuft", "tuft_thin")
    pts = [root]
    for k in range(1, 4):
        f = k / 3.0
        if hang:
            pts.append((root[0] - tl * 0.25 * f, root[1] - tl * f * 0.95, tl * f * math.sin(wag) * 0.4))
        else:
            pts.append((root[0] - tl * f * math.cos(ta * 0.8), root[1] + tl * f * (math.sin(ta) - 0.35 * f),
                        tl * f * math.sin(wag) * 0.6))
    return pts, tl


def skeleton(rig):
    """named joints of a posed animal (rig units)"""
    J = {"hip": np.array(rig.along(0.0)), "sh": np.array(rig.along(1.0)), "nb": np.array(rig.neck_base, float),
         "ne": np.array(rig.neck_end, float), "head": np.array(rig.head, float)}
    for i, (top, knee, paw, end, side) in enumerate(rig.legs()):
        J[f"l{i}t"], J[f"l{i}k"], J[f"l{i}p"] = np.array(top, float), np.array(knee, float), np.array(paw, float)
    pts, _ = _tail_points(rig)
    J["t0"], J["t1"] = np.array(pts[0], float), np.array(pts[-1], float)
    J["fwd"] = np.array(rig.fwd, float)
    return J


def bones_of(J):
    b = {"spine": ("hip", "sh"), "neck": ("nb", "ne"), "tail": ("t0", "t1")}
    i = 0
    while f"l{i}t" in J:
        b[f"leg{i}a"], b[f"leg{i}b"] = (f"l{i}t", f"l{i}k"), (f"l{i}k", f"l{i}p")
        i += 1
    return b


def sculpt(rig, jaw=0.0, blink=False, angry=False):
    """the clay animal on its rest skeleton -> Sculpt (shapes tagged with bones)"""
    sp, g, hr = rig.sp, rig.g, rig.head_r
    fur = sp.get("fur", "#999999")
    belly = sp.get("belly", fur)
    leg_col = sp.get("leg_color") or fur
    hoof = "#2a2220" if (sp.get("hooves") or sp.get("step") == "hoof") else _darker(leg_col, 0.8)
    muzzle = sp.get("muzzle") or belly
    S = Sculpt()
    # ---- body: a real animal's build - a deep chest behind the front legs, ribs, a waist tucked up behind them (the
    # runners and hunters) or a round barrel (cattle, elephants, bears), the rump over the hind legs, and muscle over
    # the shoulder blades and the haunches
    S.bone = "spine"
    lean = rig.species in LEAN
    pts = [rig.along(f) for f in (-0.12, 0.2, 0.55, 0.85, 1.08)]
    rr = [g * 0.55, g * 0.82, g * (0.78 if lean else 0.95), g * 0.9, g * 0.62]
    for a, b, ra, rb in zip(pts[:-1], pts[1:], rr[:-1], rr[1:]):
        S.capsule(a, b, ra, rb, fur, k=g * 0.35, gloss=0.12)
    m = rig.along(0.5)
    ch, rp, mid = rig.along(0.8), rig.along(0.08), rig.along(0.42)
    S.ellipsoid((ch[0], ch[1] - g * 0.12, 0), (g * 0.95, g * (1.15 if lean else 1.05), g * 0.86), fur, k=g * 0.3, gloss=0.12)
    S.ellipsoid((mid[0], mid[1] + (g * 0.1 if lean else -g * 0.02), 0), (g * 1.0, g * (0.8 if lean else 1.02), g * 0.9),
                fur, k=g * 0.35, gloss=0.12)                                        # ribs / belly (tucked up when lean)
    S.ellipsoid((rp[0], rp[1] + g * 0.05, 0), (g * 0.85, g * 0.92, g * 0.82), fur, k=g * 0.3, gloss=0.12)   # the rump
    for s_ in (-1, 1):
        S.sphere((ch[0] - g * 0.05, ch[1] + g * 0.2, s_ * g * 0.5), g * 0.48, fur, k=g * 0.3, gloss=0.12)     # shoulders
        S.sphere((rp[0] + g * 0.05, rp[1] - g * 0.05, s_ * g * 0.52), g * 0.55, fur, k=g * 0.3, gloss=0.12)  # haunches
    a0, a1 = np.array(rig.along(-0.12)), np.array(rig.along(1.08))
    S.paint(lambda P, m=m: np.maximum(P[:, 1] - (m[1] - g * 0.35), s3._sd_capsule(P, a0, a1, g * 1.04, g * 1.04)), belly,
            soft=g * 0.12)                                                           # the belly side (not the legs)
    if sp.get("hump"):
        S.sphere((m[0], m[1] + g * 0.85, 0), g * 0.62, fur, k=g * 0.35, gloss=0.12)
    if sp.get("udder"):
        S.sphere((rig.along(0.18)[0], m[1] - g * 0.95, 0), g * 0.3, "#f5b6b6", k=g * 0.15, gloss=0.2)
    # ---- legs (each its own part: it follows only its own two bones - legs swinging past each other never pull the
    # clay between them), muscle at the top, a slim lower leg, a knee / hock, paws with toes or hooves
    pawed = sp.get("step") != "hoof" and not sp.get("hooves")
    split = rig.species in ("cow", "buffalo", "goat", "sheep", "deer", "pig", "giraffe", "camel")
    for i, (top, knee, paw, end, side) in enumerate(rig.legs()):
        w = rig.legw * (0.5 if end == "arm" else 0.65 if sp.get("legs", 4) >= 6 else 1.0)
        S.group = "body"                                     # the thigh / upper arm melts into the body ...
        S.bone = f"leg{i}a"
        S.capsule(top, knee, w * 1.75, w * 0.95, leg_col, k=g * 0.2, gloss=0.12)
        S.group = f"leg{i}"                                  # ... and from the knee down the leg is its own part
        S.sphere(knee, w * 0.97, leg_col, k=w * 0.3, gloss=0.12)
        S.bone = f"leg{i}b"
        S.capsule(knee, paw, w * 0.88, w * 0.68, leg_col, k=w * 0.3, gloss=0.12)
        if end != "arm":
            pk = 1.25 if sp.get("_fierce") else 1.0         # a hunter's big paws
            pc = np.array([paw[0] + w * 0.3 * pk, paw[1] + w * 0.32 * pk, paw[2]])
            if pawed:                                        # a paw: a pad and four toes in front
                S.ellipsoid(pc, (w * 1.1 * pk, w * 0.55 * pk, w * 1.0 * pk), leg_col, k=w * 0.3, gloss=0.15)
                for dz in (-0.55, -0.18, 0.18, 0.55):
                    S.sphere(pc + np.array([w * 0.85 * pk, -w * 0.12 * pk, dz * w * pk]), w * 0.32 * pk, leg_col,
                             k=w * 0.12, gloss=0.15)
            else:
                S.ellipsoid(pc, (w * 1.0, w * 0.62, w * 0.95), hoof, k=w * 0.25, gloss=0.35)
                if split:                                    # a cloven hoof: the cleft down the middle
                    S.paint(lambda P, c_=pc, w_=w: np.maximum(np.abs(P[:, 2] - c_[2]) - w_ * 0.07, P[:, 0] - c_[0] + w_ * 0.2),
                            "#0d0908", soft=w * 0.03)
        if rig.species == "zebra":                           # stripes round the legs
            S.paint(lambda P, w_=w: np.abs(((P[:, 1] / (w_ * 2.2)) % 1.0) - 0.5) * w_ * 2.2 - w_ * 0.5,
                    sp.get("stripe_color", "#161616"), soft=w * 0.08)
    S.group = "body"
    # ---- neck and head (melted into the body)
    nb, ne, hd = rig.neck_base, rig.neck_end, rig.head
    S.bone = "neck"
    S.capsule(nb, ne, rig.neck_w * 1.1, rig.neck_w * 0.9, fur, k=g * 0.3, gloss=0.12)
    if rig.mane is not None and rig.species in ("horse", "zebra", "donkey"):
        S.capsule((nb[0] - rig.neck_w * 0.2, nb[1] + rig.neck_w * 0.95, 0), (ne[0] - rig.neck_w * 0.3, ne[1] + rig.neck_w * 0.75, 0),
                  rig.neck_w * 0.36, rig.neck_w * 0.3, sp.get("mane"), k=rig.neck_w * 0.15, gloss=0.2)
    S.bone = "head"
    if rig.mane is not None and rig.species == "lion":   # a shaggy mane: a ring of locks round the face, down the neck
        mc_ = sp.get("mane")
        p = np.array(rig.face_point(-0.4, 0, 0))
        S.ellipsoid(p, (hr * 0.75, hr * 1.25, hr * 1.25), mc_, k=hr * 0.3, gloss=0.15)
        for k_ in range(18):
            a_ = 2 * math.pi * k_ / 18
            d_ = np.array([-0.25, math.cos(a_), math.sin(a_)])
            r0 = p + np.array([0, math.cos(a_), math.sin(a_)]) * hr * 0.9
            S.capsule(r0, r0 + d_ / np.linalg.norm(d_) * hr * (0.75 + 0.2 * ((k_ * 7) % 3) / 2), hr * 0.32, hr * 0.12,
                      _darker(mc_, 0.9 + 0.1 * (k_ % 2)), k=hr * 0.15, gloss=0.15)
        for k_ in range(4):
            q_ = np.array(nb) + (np.array(ne) - np.array(nb)) * (0.2 + 0.2 * k_)
            S.sphere(q_ + np.array([-rig.neck_w * 0.1, -rig.neck_w * 0.55, 0]), rig.neck_w * 0.75, mc_, k=rig.neck_w * 0.4,
                     gloss=0.15)
    cute = bool(sp.get("_cute"))
    cat = rig.species in CATS
    S.sphere(hd, hr, fur, k=hr * 0.35, gloss=0.15)
    if rig.species == "pig":                             # the pig's flat round snout with two nostrils
        sn = np.array(hd) + np.array([hr * 1.05, -hr * 0.2, 0])
        S.capsule(np.array(hd) + np.array([hr * 0.6, -hr * 0.15, 0]), sn, hr * 0.42, hr * 0.4, "#f2a3b3", k=hr * 0.15, gloss=0.3)
        for s_ in (-1, 1):
            S.paint_ball(sn + np.array([hr * 0.4, 0, s_ * hr * 0.14]), hr * 0.08, "#7a3540", soft=hr * 0.02)
    if rig.species == "panda":                           # black eye patches, black ears, the black band over the shoulders
        for s_ in (-1, 1):
            S.paint(lambda P, c_=np.array(hd) + np.array([hr * 0.72, hr * 0.12, s_ * hr * 0.42]):
                    np.linalg.norm((P - c_) / np.array([1.0, 1.25, 0.8]), axis=1) - hr * 0.3, "#1a1a1a", soft=hr * 0.05)
        ch_ = rig.along(0.88)
        S.paint(lambda P, c_=ch_: np.abs(P[:, 0] - c_[0]) - g * 0.35, "#1a1a1a", soft=g * 0.08)
    if rig.species == "sheep":                           # wool: a lumpy fleece over the body
        for k_ in range(40):
            f_ = 0.0 + 1.05 * ((k_ * 29) % 40) / 40.0
            a_ = math.pi * (0.1 + 0.8 * ((k_ * 17) % 11) / 11.0)
            c_ = np.array(rig.along(f_))
            S.sphere(c_ + np.array([0, math.sin(a_) * g * 0.85 - g * 0.05, math.cos(a_) * g * 0.85]), g * 0.3, fur,
                     k=g * 0.12, gloss=0.05)
    fw = np.array(rig.fwd)
    sl, sw = rig.snout
    lvl = np.array([1.0, 0.0, 0.0])                         # level forward (fwd points forward-down)
    fierce = bool(sp.get("_fierce"))

    def on(v, r=1.0):                                       # a point on the skull in direction v
        v = np.asarray(v, float)
        return np.array(hd) + v / np.linalg.norm(v) * hr * r
    if fierce and cat:
        # a big cat's face: a long nose bridge, broad white whisker pads, a strong chin, a wide nose
        S.capsule(on((0.45, 0.35, 0), 0.85), np.array(hd) + np.array([hr * 1.08, -hr * 0.1, 0]), hr * 0.32, hr * 0.24, fur,
                  k=hr * 0.2, gloss=0.15)
        for s_ in (-1, 1):
            S.sphere(np.array(hd) + np.array([hr * 0.92, -hr * 0.36, s_ * hr * 0.22]), hr * 0.27, muzzle, k=hr * 0.12,
                     gloss=0.2)
        S.sphere(np.array(hd) + np.array([hr * 0.72, -hr * 0.62, 0]), hr * 0.22, muzzle, k=hr * 0.12, gloss=0.2)
        S.ellipsoid(np.array(hd) + np.array([hr * 1.24, -hr * 0.12, 0]), (hr * 0.1, hr * 0.1, hr * 0.17),
                    "#2c1a16" if rig.species in ("lion", "wolf") else "#a85a4c", k=hr * 0.05, gloss=0.6)
        S.paint_line([np.array(hd) + np.array([hr * 1.2, -hr * 0.3, 0]), np.array(hd) + np.array([hr * 1.12, -hr * 0.46, 0])],
                     hr * 0.03, "#2c1a16", soft=hr * 0.01)                                      # the line under the nose
        for s_ in (-1, 1):                                  # white over the eyes and the cheek ruff
            S.paint_ball(on((0.5, 0.62, s_ * 0.55)), hr * 0.14, belly, soft=hr * 0.04)
            S.ellipsoid(np.array(hd) + np.array([0.0, -hr * 0.45, s_ * hr * 0.85]), (hr * 0.38, hr * 0.32, hr * 0.22), belly,
                        k=hr * 0.2, gloss=0.15)
        if jaw > 0.1:                                       # the roar: a wide open mouth under the pads
            mc = np.array(hd) + np.array([hr * 0.92, -hr * 0.6, 0])
            S.carve(("ellipsoid", mc, np.array([hr * 0.36, hr * (0.08 + 0.18 * jaw), hr * 0.28])), k=hr * 0.04)
            S.paint_ball(mc, hr * 0.34, "#6a1620", soft=hr * 0.05)
            lo_ = mc + np.array([-hr * 0.06, -hr * (0.14 + 0.2 * jaw), 0])     # the dropped lower jaw, hinged at the throat
            S.capsule(np.array(hd) + np.array([hr * 0.2, -hr * 0.7, 0]), lo_, hr * 0.24, hr * 0.15, muzzle, k=hr * 0.1,
                      gloss=0.2)
            S.ellipsoid(lo_, (hr * 0.3, hr * 0.12, hr * 0.24), muzzle, k=hr * 0.08, gloss=0.2)
        if jaw > 0.1 or angry:                              # fangs: two above (and two below when it roars)
            for s_ in (-1, 1):
                t0 = np.array(hd) + np.array([hr * 1.06, -hr * 0.5, s_ * hr * 0.16])
                S.capsule(t0, t0 + np.array([-hr * 0.02, -hr * (0.17 + 0.08 * jaw), 0]), hr * 0.065, hr * 0.02, "#fbf6ea",
                          group="teeth", k=hr * 0.01, gloss=0.6)
                if jaw > 0.3:
                    b0 = lo_ + np.array([hr * 0.14, hr * 0.06, s_ * hr * 0.14])
                    S.capsule(b0, b0 + np.array([0, hr * 0.13, 0]), hr * 0.055, hr * 0.018, "#fbf6ea", group="teeth",
                              k=hr * 0.01, gloss=0.6)
            if angry:                                       # the snarl: wrinkles up the nose
                for k_ in range(3):
                    y_ = -0.02 + 0.1 * k_
                    S.paint_line([np.array(hd) + np.array([hr * (1.02 - 0.1 * k_), hr * y_, -hr * 0.2]),
                                  np.array(hd) + np.array([hr * (1.06 - 0.1 * k_), hr * (y_ + 0.04), 0]),
                                  np.array(hd) + np.array([hr * (1.02 - 0.1 * k_), hr * y_, hr * 0.2])], hr * 0.025, "#5a2e16",
                                 soft=hr * 0.01)
    elif cat and cute:
        # a cartoon cat face: two puffy cheeks (whisker pads) side by side, a small chin, a little pink nose
        fc = np.array(hd) + lvl * hr * 0.78 + np.array([0, -hr * 0.3, 0])
        for s_ in (-1, 1):
            S.sphere(fc + np.array([0, 0, s_ * hr * 0.2]), hr * 0.3, muzzle, k=hr * 0.12, gloss=0.2)
        S.sphere(fc + np.array([-hr * 0.05, -hr * 0.2, 0]), hr * 0.18, muzzle, k=hr * 0.1, gloss=0.2)
        nose = fc + np.array([hr * 0.24, hr * 0.17, 0])
        S.ellipsoid(nose, (hr * 0.1, hr * 0.08, hr * 0.14), "#d9707a" if rig.species != "lion" else "#3a2420",
                    k=hr * 0.04, gloss=0.7)
        S.paint_ball(fc + np.array([hr * 0.31, -hr * 0.05, 0]), hr * 0.035, "#3a2420", soft=hr * 0.01)  # the mouth line
        for s_ in (-1, 1):                                  # cheek fluff: the white ruff at the sides of the face
            S.ellipsoid(np.array(hd) + np.array([hr * 0.1, -hr * 0.42, s_ * hr * 0.78]), (hr * 0.32, hr * 0.3, hr * 0.22),
                        belly, k=hr * 0.18, gloss=0.15)
        if jaw > 0.1:                                       # roar / talk: the mouth opens under the cheeks
            mc = fc + np.array([hr * 0.12, -hr * 0.26, 0])
            S.carve(("ellipsoid", mc, np.array([hr * 0.2, hr * (0.06 + 0.16 * jaw), hr * 0.22])), k=hr * 0.04)
            S.paint_ball(mc, hr * 0.26, "#7a1e26", soft=hr * 0.04)
    elif sl > 1:
        a, tip = rig.face_point(0.45, -0.05, 0), rig.face_point(0.75 + sl / hr * 0.6, -0.05, 0)
        if cute:                                            # a short snout that comes out of the big round head
            d_ = np.array([1.0, -0.4, 0.0]) / math.hypot(1.0, 0.4)
            a = np.array(hd) + d_ * hr * 0.55 + np.array([0, -hr * 0.12, 0])
            tip = np.array(hd) + d_ * hr * (0.9 + max(sl / hr * 0.5, 0.22)) + np.array([0, -hr * 0.12, 0])
            fw = d_
        S.capsule(a, tip, sw * 0.62, sw * 0.5, muzzle, k=hr * 0.3, gloss=0.25)
        nose = np.array(tip) + fw * sw * 0.42 + np.array([0, sw * 0.12, 0])
        S.ellipsoid(nose, (sw * 0.2, sw * 0.16, sw * 0.26), "#1f1414", k=sw * 0.08, gloss=0.7)
        if jaw > 0.1:                                       # roar / bark / talk: the mouth opens under the snout
            mc = np.array(tip) - fw * sw * 0.25 + np.array([0, -sw * 0.32, 0])
            mr = np.array([sw * 0.55, sw * (0.12 + 0.32 * jaw), sw * 0.42])
            S.carve(("ellipsoid", mc, mr), k=sw * 0.08)
            S.paint_ball(mc, sw * 0.6, "#5a1418", soft=sw * 0.1)
    if cat and (cute or fierce) and sp.get("pattern") == "stripes":     # forehead and cheek stripes
        for dz in (-0.28, 0.0, 0.28):                   # three bold forehead stripes
            S.paint_line([on((0.45, 0.85, dz)), on((0.7, 0.5, dz * 0.8))], hr * 0.075, "#291a0f", soft=hr * 0.02)
        for s_ in (-1, 1):                              # two on each cheek, pointing at the nose
            for dy in (0.15, -0.12):
                S.paint_line([on((0.0, dy, s_)), on((0.4, dy - 0.05, s_ * 0.85))], hr * 0.07, "#291a0f",
                             soft=hr * 0.02)
    # eyes: cartoon eyes (white, iris, pupil, catchlight), blinking = fur lids
    for s in (-1, 1):
        dv = np.array([0.78, 0.12, s * 0.5]) if cute else np.array([0.72, 0.24, s * 0.52]) if fierce else \
            np.array([0.72, 0.3, s * 0.62])                 # cute: big, low, close; fierce: small, forward
        dv /= np.linalg.norm(dv)
        er = hr * (0.25 if cute else 0.19 if fierce else 0.22)
        p = np.array(hd) + dv * hr * (0.93 if fierce else 0.9)
        S.sphere(p, er, "#fbfaf6" if not fierce else "#f3e7b0", group="eyes", k=0.0, gloss=0.9)
        look = dv * 0.45 + np.array([0.55, 0.0, 0.0])
        S.paint_cone(p, look, 62 if fierce else 40, "#e09a12" if fierce else (
            "#4a2c10" if rig.species not in ("tiger", "lion", "cat", "leopard") else "#b88a10"), group="eyes", soft=er * 0.03)
        S.paint_cone(p, look, 16 if fierce else 22, "#0b0705", group="eyes", soft=er * 0.03)
        if fierce:                                          # 😠 a heavy brow in a V down to the nose, a slanted lid
            inner = p + np.array([er * 0.95, er * 0.25, -s * er * 1.25])
            outer = p + np.array([-er * 0.3, er * 1.35, s * er * 1.1])
            S.capsule(inner, outer, er * 0.75, er * 0.55, fur, k=er * 0.45, gloss=0.12)
            S.paint_line([inner + np.array([er * 0.1, er * 0.55, 0]), outer + np.array([0, er * 0.45, 0])], er * 0.32,
                         "#241509", soft=er * 0.08)                            # the black brow marking
            S.capsule(p + np.array([er * 0.75, er * 0.05, -s * er * 0.85]), p + np.array([-er * 0.45, er * 0.85, s * er * 0.85]),
                      er * 0.7, er * 0.6, fur, group="lids", k=0.0, gloss=0.12)  # the lid: the top of the eye cut on a slant
            S.paint_line([p + np.array([er * 0.9, -er * 0.4, -s * er * 0.6]), p + np.array([er * 1.6, -er * 1.5, -s * er * 0.9])],
                         er * 0.18, "#2c1a16", soft=er * 0.05)                 # the dark line from the eye down the nose
        S.paint_cone(p, look + np.array([0, 0.5, 0]), 9, "#ffffff", group="eyes", soft=er * 0.02, gloss=1.0)
        if blink:
            S.sphere(p, er * 1.12, fur, group="lids", k=0.0, gloss=0.15)
    # ears
    ears = sp.get("ears", "round")
    back = np.array(rig.face_point(-0.2, 0.85, 0))
    dk = "#1a1a1a" if rig.species == "panda" else _darker(fur, 0.85)
    for s in (-1, 1):
        z = s * hr * 0.6
        if ears in ("pointy", "pointy_tall"):
            h = hr * (0.75 if ears == "pointy" else 1.05)
            S.capsule(back + np.array([0, -hr * 0.1, z]), back + np.array([-hr * 0.08, h, z * 1.1]), hr * 0.3, hr * 0.05, fur,
                      k=hr * 0.12, gloss=0.15)
        elif ears == "long":
            S.capsule(back + np.array([0, -hr * 0.1, z * 0.6]), back + np.array([-hr * 0.3, hr * 1.6, z * 0.8]), hr * 0.24, hr * 0.15,
                      fur, k=hr * 0.1, gloss=0.15)
        elif ears == "huge":
            pp = np.array(rig.face_point(-0.3, 0.1, 0))
            S.ellipsoid((pp[0], pp[1], s * hr * 0.98), (hr * 0.72, hr * 0.88, hr * 0.12), dk, k=hr * 0.15, gloss=0.12)
        elif ears in ("floppy", "side"):
            S.ellipsoid(back + np.array([0, -hr * (0.55 if ears == "floppy" else 0.25), s * hr * 0.95]),
                        (hr * 0.26, hr * (0.46 if ears == "floppy" else 0.2), hr * 0.12), dk, k=hr * 0.1, gloss=0.15)
        elif fierce:                                        # small ears set wide; angry: pinned back and flat
            e0 = np.array(rig.face_point(-0.45, 0.55, 0)) if angry else back + np.array([-hr * 0.05, -hr * 0.12, 0])
            S.ellipsoid(e0 + np.array([0, 0, s * hr * 0.72]), (hr * 0.26, hr * (0.14 if angry else 0.24), hr * 0.12), fur,
                        k=hr * 0.08, gloss=0.15)
            S.paint_ball(e0 + np.array([0, hr * 0.05, s * hr * 0.72]), hr * 0.1, "#241509", soft=hr * 0.03)
        else:
            S.ellipsoid(back + np.array([0, 0, z]), (hr * 0.3, hr * 0.3, hr * 0.18), fur, k=hr * 0.1, gloss=0.15)
    # horns / antlers
    horns = sp.get("horns")
    if horns or sp.get("antlers"):
        for s in (-1, 1):
            b0 = back + np.array([fw[0] * hr * 0.2, hr * 0.05, s * hr * 0.35])
            if sp.get("antlers"):
                p1 = b0 + np.array([-hr * 0.2, hr * 1.2, s * hr * 0.45])
                S.tube([b0, p1], hr * 0.08, "#735433", group="horns", k=0.0, gloss=0.3)
                S.tube([(b0 + p1) / 2, b0 + np.array([hr * 0.3, hr * 1.0, s * hr * 0.25])], hr * 0.06, "#735433", group="horns",
                       k=0.0, gloss=0.3)
            elif horns == "curved":
                S.tube([b0, b0 + np.array([-hr * 0.4, hr * 0.5, s * hr * 0.35]), b0 + np.array([-hr * 0.2, hr * 0.2, s * hr * 0.65])],
                       hr * 0.1, "#d9ccb3", group="horns", k=0.0, gloss=0.4)
            else:
                S.capsule(b0, b0 + np.array([0, hr * 0.45, s * hr * 0.1]), hr * 0.11, hr * 0.03, "#e6dbc2", group="horns",
                          k=0.0, gloss=0.4)
    # trunk and tusks
    if sp.get("trunk"):
        p0 = rig.face_point(0.8, -0.1, 0)
        tp, ang, x, y = [np.array(p0)], -1.35, p0[0], p0[1]
        for _ in range(4):
            x += math.cos(ang) * hr * 0.5
            y += math.sin(ang) * hr * 0.5
            tp.append(np.array([x, y, 0.0]))
            ang += 0.25
        rr = [hr * 0.32, hr * 0.25, hr * 0.2, hr * 0.15, hr * 0.11]
        for a, b, ra, rb in zip(tp[:-1], tp[1:], rr[:-1], rr[1:]):
            S.capsule(a, b, ra, rb, fur, k=hr * 0.12, gloss=0.15)
        if sp.get("tusks"):
            for s in (-1, 1):
                a = np.array(p0) + np.array([0, -hr * 0.1, s * hr * 0.35])
                S.tube([a, a + np.array([hr * 0.5, -hr * 0.35, 0]), a + np.array([hr * 0.75, -hr * 0.1, 0])], hr * 0.07, "#f7f2e0",
                       group="horns", k=0.0, gloss=0.5)
    if sp.get("beard"):
        c0 = (np.array(hd) + np.array([hr * 0.55, -hr * 0.8, 0])) if cute else rig.face_point(0.6, -0.9, 0)
        S.capsule(c0, np.array(c0) + np.array([0, -hr * 0.4, 0]), hr * 0.12, hr * 0.04, _darker(fur, 0.9), k=hr * 0.08)
    # ---- tail
    S.bone = "tail"
    tpts, tl = _tail_points(rig)
    kind = sp.get("tail")
    tw = g * (0.28 if kind in ("bushy", "long_hair") else 0.15 if sp.get("_cute") else 0.11)
    if tl > 5:
        tcol = _darker(fur, 0.55) if kind == "long_hair" else fur
        rr = [tw, tw, tw * 0.8, tw * 0.5]
        for a, b, ra, rb in zip(tpts[:-1], tpts[1:], rr[:-1], rr[1:]):
            S.capsule(a, b, ra, rb, tcol, k=tw * 0.6, gloss=0.15, group="tail")
    end = tpts[-1]
    if sp.get("pattern") == "stripes" and tl > 5:            # rings round the tail, a dark tip
        for f in (0.35, 0.55, 0.75):
            k_ = min(int(f * 3), 2)
            q = np.array(tpts[k_]) + (np.array(tpts[k_ + 1]) - np.array(tpts[k_])) * (f * 3 - k_)
            S.paint_ball(q, tw * 1.25 * 0.5, "#291a0f", group="tail", soft=tw * 0.1)
        S.paint_ball(end, tw * 1.3, "#291a0f", group="tail", soft=tw * 0.1)
    if kind in ("tuft", "tuft_thin") or sp.get("tail_tip"):
        S.sphere(end, g * 0.17, sp.get("tail_tip") or _darker(fur, 0.55), k=g * 0.08, gloss=0.15,
                 group="tail")
    if kind == "puff":
        S.sphere(end, g * 0.3, "#ffffff", k=g * 0.1, gloss=0.15, group="tail")
    # ---- coat patterns (paint on the skin)
    pat = sp.get("pattern")
    hip, sh = np.array(rig.along(0.0)), np.array(rig.along(1.0))
    ax = (sh - hip) / max(np.linalg.norm(sh - hip), 1e-6)
    L = np.linalg.norm(sh - hip)
    if pat in ("stripes", "zebra", "stripes_light"):
        col = sp.get("stripe_color", "#161616") if pat == "zebra" else (_darker(fur, 0.55) if pat == "stripes_light" else "#291a0f")
        period = L / 6.5

        def stripes(P):
            u = (P - hip) @ ax
            band = np.abs(((u / period) % 1.0) - 0.5) * period - period * 0.13
            return np.maximum(band, np.maximum(-(u + L * 0.1), u - L * 1.05)) + np.maximum(0, m[1] - g * 0.45 - P[:, 1]) * 3
        S.paint(stripes, col, soft=g * 0.04)
        if pat == "zebra":                                  # the stripes go on round the neck, over the head and the upper legs
            nb_, hd_ = np.array(rig.neck_base, float), np.array(rig.head, float)
            nax = (hd_ - nb_) / max(np.linalg.norm(hd_ - nb_), 1e-6)
            per_n = np.linalg.norm(hd_ - nb_) / 5.5
            S.paint(lambda P: np.maximum(np.abs(((((P - nb_) @ nax) / per_n) % 1.0) - 0.5) * per_n - per_n * 0.14,
                                         np.maximum(-((P - nb_) @ nax) - g * 0.2, (P - nb_) @ nax - np.linalg.norm(hd_ - nb_) * 0.9)),
                    col, soft=g * 0.04)
            low_ = m[1] - g * 0.75
            S.paint(lambda P: np.maximum(np.abs(((P[:, 1] / (g * 0.42)) % 1.0) - 0.5) * g * 0.42 - g * 0.09, P[:, 1] - low_),
                    col, soft=g * 0.04)
    elif pat == "giraffe":                                 # the giraffe's net of brown patches, over the body and the neck
        nb_, hd_ = np.array(rig.neck_base, float), np.array(rig.head, float)
        cells = [np.array(rig.along(0.05 + 0.18 * i)) + np.array([0, g * (0.55 * ((j % 3) - 1)), s_ * g * 0.75])
                 for i in range(6) for j in range(3) for s_ in (-1, 1)]
        cells += [nb_ + (hd_ - nb_) * (0.12 + 0.13 * i) + np.array([0, 0, s_ * rig.neck_w * 0.8]) for i in range(6) for s_ in (-1, 1)]
        for k_, c_ in enumerate(cells):
            S.paint_ball(c_, g * (0.36 if k_ < 36 else 0.22), "#9a531f", soft=g * 0.03)
    elif pat in ("spots", "leopard", "patches", "panda"):
        col = {"spots": "#ffffff", "giraffe": "#8c4a1c", "panda": "#1a1a1a", "patches": "#26211f"}.get(pat, "#1f140c")
        size = 0.16 if pat in ("spots", "leopard") else 0.34
        for k in range(14 if pat != "panda" else 2):
            p = rig.along(0.12 + 0.76 * ((k * 37) % 13) / 13.0)
            up = 0.3 + 0.45 * ((k * 53) % 7) / 7.0
            side = 1 if k % 2 else -1
            S.paint_ball((p[0], p[1] + g * up, side * g * math.sqrt(max(0.0, 1 - up * up)) * 0.98), g * size, col,
                         soft=g * 0.03)
    S.no_shadow = {"eyes", "lids", "horns", "tail", "teeth"}
    return S


# ---------------------------------------------------------------------------- cache, pose, draw
U = 1.0 / 190.0                       # rig units -> metres (a person is ~300 units = 1.6 m): sculpt3d's seams are in metres


def _to_metres(S, u=U):
    """the same clay, scaled into metres (shapes keep their own functions: P is scaled back before them)"""
    for x in S.shapes:
        f, clip = x.fn, x.clip
        x.fn = (lambda P, f=f: f(P / u) * u)
        if clip is not None:
            x.clip = (lambda P, c=clip: c(P / u) * u)
        x.k = x.k * u
        if x.box is not None:                               # grown by the blend reach (smooth joins bulge out a little)
            x.box = (np.asarray(x.box[0]) * u - x.k, np.asarray(x.box[1]) * u + x.k)
    return S


def pieces(c, rig0, lod, jaw, blink, angry=False):
    """-> ([Model] in rig units, {"bones": [...]}) - sculpted once per detail / mouth / blink, then from the cache"""
    g, hr = rig0.g, rig0.head_r
    cb, ch = LODS.get(lod, LODS["mid"])
    j = round(min(1.0, float(jaw)) * 2) / 2.0               # three mouth openings: shut, half, open
    key_card = {"species": c.species, "scale": float(getattr(c, "scale", 1.0)),
                "sp": {k: v for k, v in rig0.sp.items() if isinstance(v, (str, int, float, bool, list, tuple))}}

    def make():
        S = _to_metres(sculpt(rig0, jaw=j, blink=blink, angry=angry))
        S.res = {gn: (hr * ch * U if gn in FINE else g * cb * U * (0.7 if gn.startswith("leg") else 1.0)) for gn in S.groups()}
        parts = S.build(cell=g * cb * U, quads=True)
        names = list(bones_of(skeleton(rig0))) + ["head"]
        skin = s3.rgb(rig0.sp.get("fur", "#999999"))
        models = []
        for p in parts:
            solid = [x for x in S.shapes if x.group == p.name and x.mode == "add"]
            D = np.stack([x.d(p.V) for x in solid])
            Wt = np.exp(-(D - D.min(axis=0)) / max(g * U * 0.12, 1e-6))
            W = np.zeros((len(p.V), len(names)))
            for i, x in enumerate(solid):
                W[:, names.index(x.bone if x.bone in names else "spine")] += Wt[i]
            W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
            models.append(srig.Model((p.V / U).astype(np.float32), p.T.astype(np.int32), p.N.astype(np.float32),
                                     np.clip(p.C, 0, 1).astype(np.float32), p.G.astype(np.float32), W.astype(np.float32),
                                     skin))
        return models, {"bones": names}
    return srig._cached(srig._key(key_card, "animal7", lod, j, int(bool(blink)), int(bool(angry))), make)


def bone_moves(J0, J1, names):
    moves = {}
    for b in names:
        if b == "head":
            continue
        a, e = bones_of(J0)[b]
        R = srig._rot_between(J0[e] - J0[a], J1[e] - J1[a])
        moves[b] = (R, J1[a] - R @ J0[a])
    # the head: turns with the neck and the way the face looks
    f0, f1 = J0["fwd"], J1["fwd"]
    R = srig._rot_between(f0, f1)
    moves["head"] = (R, J1["head"] - R @ J0["head"])
    return moves


def emit(pen, models, names, moves):
    """skin the cached pieces with the bone moves {bone: (R, t)} and add their faces to the scene pen (shared by the
    sculpted animals and birds)"""
    from .code3d import Face, _inv_t
    R9, T3 = pen._m
    from . import live3d
    if live3d.LIVE[0]:                                   # 🎥 live 3D play: the bones go to the browser, not the faces
        live3d.RIG_PENDING[id(pen.faces)] = dict(models=models, k=1.0, moves=moves, bones=list(names), M=R9, T=T3,
                                                 top=1.0, alpha=pen.opacity, q=0)
        return
    M = np.array(R9, float).reshape(3, 3)
    T = np.array(T3, float)
    NM = np.array(_inv_t(R9), float).reshape(3, 3)
    for m in models:
        if not len(m.Q):
            continue
        V = np.zeros(m.V.shape)
        N = np.zeros(m.N.shape)
        for bi, b in enumerate(names):
            w = m.W[:, bi]
            if not w.any():
                continue
            R, tt = moves[b]
            V += w[:, None] * (m.V @ R.T + tt)
            N += w[:, None] * (m.N @ R.T)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
        W = V @ M.T + T
        NW = N @ NM.T
        NW /= np.maximum(np.linalg.norm(NW, axis=1, keepdims=True), 1e-9)
        Q = m.Q
        col = m.C[Q].mean(axis=1)
        fn = NW[Q].sum(axis=1)
        fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
        gl = m.G[Q].mean(axis=1)
        Wl, NWl, coll, fnl = W.tolist(), NW.tolist(), col.tolist(), fn.tolist()
        for i, q in enumerate(Q.tolist()):
            cc = coll[i]
            pen.faces.append(Face([Wl[q[0]], Wl[q[1]], Wl[q[2]], Wl[q[3]]], tuple(fnl[i]), (cc[0], cc[1], cc[2], pen.opacity),
                                  True, mat=(0.6, 40.0, 0.0) if gl[i] > 0.6 else None,
                                  vn=[NWl[q[0]], NWl[q[1]], NWl[q[2]], NWl[q[3]]]))


_REST = {}


def code_fn(pen, rig, t, state):
    """the character code for an animal with "look3d": "sculpt" (same call as every 3D animal file)"""
    c = rig._c
    key = (c.id, c.species, round(float(c.scale), 4))
    if key not in _REST:
        _REST[key] = rest_rig(c)
    rig0 = _REST[key]
    J0, J1 = skeleton(rig0), skeleton(rig)
    if set(bones_of(J0)) != set(bones_of(J1)):
        raise ValueError("the skeleton changed shape")       # (char3d then draws the normal animal)
    height = max(1.0, rig0.head[1] + rig0.head_r)
    px = srig.screen_height(1.0, height)
    if px is None:
        px = (getattr(pen, "px_unit", None) or 0.5) * height
    lod = "near" if px > 200 else "mid" if px > 80 else "far"
    from . import live3d
    lod = live3d.cap(lod)                              # (live play on a phone: lighter pieces)
    ms = getattr(rig, "mouth_shape", None) or {}
    jaw = max(float(ms.get("jaw", 0.0)) * (1.0 - float(ms.get("closed", 0.0))), abs(float(getattr(rig, "jaw", 0.0) or 0.0)) / 20.0)
    angry = str(getattr(rig, "face", "")) in ("angry", "furious", "fierce") and bool(rig0.sp.get("_fierce"))
    models, meta = pieces(c, rig0, lod, jaw, bool(getattr(rig, "blink", False)), angry)
    names = meta["bones"]
    moves = bone_moves(J0, J1, names)
    emit(pen, models, names, moves)
    return None
