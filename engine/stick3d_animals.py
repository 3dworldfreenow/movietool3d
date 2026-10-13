"""🐄 Stick 3D: animals as real 3D models, built like the rest of the world (houses, cars, trees): a round body, tapered
legs, a neck, a head with its snout, ears, horns / antlers / trunk, eyes and a tail - solid shapes lit by the sun
(a light side and a shaded side) with ink outlines, so an animal has volume from every side and the camera can go
round it. The markings are shapes on the body too (the cow's patches, the chital's spots, tiger / zebra stripes, the
giraffe's patches, the panda's black legs and band).

The skeleton and every action come from engine/animals.py (walk, run, sit, lie, sleep, eat, jump, wag, roar ...):
the joints it solves for the side view stand the legs half a body's width either side of the spine. A story animal
is {"species": "cow"} in "characters" and takes "do" like a person; a place can keep animals of its own
(w.animals: [{"species": "cow", "pos": (x, y, z), "dir": 0.3, "do": "eat"}]). Real sizes: a desi cow 1.3 m at
the shoulder, a hen 0.4 m.

    LIBRARY                    every species (quadrupeds, birds, the monkey)
    meshes(S3, it, t)          one animal -> (its 3D parts as stick3d Meshes, where its head is)
"""
import math

import numpy as np

from . import animals as A
from .util import hex_to_rgb

M = 190.0                                   # world units per metre (as stick3d)
BIRD_M = {"hen": 0.42, "duck": 0.40, "peacock": 1.0, "flamingo": 1.3, "eagle": 0.7, "owl": 0.45, "crow": 0.35,
          "parrot": 0.32, "pigeon": 0.28}
MONKEY = {"fur": (0.45, 0.27, 0.15), "face": (0.96, 0.82, 0.68), "tall_m": 1.0}
LIBRARY = sorted(set(A.QUADS) | set(A.BIRDS) | {"monkey"})
EYE_W, PUPIL = (0.98, 0.98, 0.96), (0.08, 0.06, 0.06)
_STAND = {}


def kind_of(species):
    """'quad' | 'bird' | 'monkey' | None for a species word (aliases: bull, chicken, bhains ...)"""
    s = A.canon(species)
    if s == "monkey":
        return "monkey"
    if s in A.QUADS:
        return "quad"
    if s in A.BIRDS:
        return "bird"
    return None


def _sp(species):
    s = A.canon(species)
    d = dict(A.QUADS.get(s) or A.BIRDS.get(s) or {})
    for k in ("fur", "belly", "mane", "muzzle", "wing", "tail_tip", "headc"):
        if isinstance(d.get(k), str):
            d[k] = hex_to_rgb(d[k])
    if isinstance(d.get("beak"), tuple) and isinstance(d["beak"][0], str):
        d["beak"] = (hex_to_rgb(d["beak"][0]), d["beak"][1])
    d["name"] = s
    return d


def _darker(c, k=0.7):
    return tuple(v * k for v in c)


def _lighter(c, k=0.35):
    return tuple(v + (1 - v) * k for v in c)


def size_m(species):
    """its real height at the shoulder (birds / the monkey: standing), metres"""
    s = A.canon(species)
    if s == "monkey":
        return MONKEY["tall_m"]
    if s in A.BIRDS:
        return BIRD_M.get(s, 0.25)
    return A.REAL_SHOULDER_M.get(s, 0.9)


def shadow_size(species):
    """(rx, rz) of its shadow on the ground, world units"""
    s = A.canon(species)
    h = size_m(s) * M
    if s in A.QUADS:
        return h * 0.85, h * 0.32
    return h * 0.4, h * 0.22


# ---------------------------------------------------------------------------- solid shapes, anywhere, any way round
class Kit:
    """builds the parts of one animal in the world: points are given in the animal's own units - x forward, y up,
    s to its left side - and land in the world at its place, size and heading"""

    def __init__(self, S3, base, fwd, k, tag):
        self.S3, self.base, self.k, self.tag = S3, np.asarray(base, float), k, tag
        self.fwd = np.asarray(fwd, float)
        self.up = np.array([0.0, 1.0, 0.0])
        self.side = -np.cross(self.fwd, self.up)                       # (its left side)
        self.out = []

    def P(self, x, y, s=0.0):
        return self.base + (self.fwd * x + self.up * y + self.side * s) * self.k

    def V(self, x, y, s=0.0):                                          # a direction (no position)
        v = self.fwd * x + self.up * y + self.side * s
        n = np.linalg.norm(v)
        return v / n if n > 1e-9 else self.fwd

    def colour(self, part, col):
        name = f"a_{self.tag}_{part}"
        self.S3.WASH[name] = tuple(float(c) for c in col)
        self.S3.NO_SHADOW.add(name)
        return name

    def blob(self, c, u, a, b, w, col, part, n=12, m=8):
        """an ellipsoid: centre c (world), its long axis along direction u with half-length a, b across it upward,
        w to the side"""
        u = np.asarray(u, float)
        u = u / max(1e-9, np.linalg.norm(u))
        sd = self.side - u * float(np.dot(self.side, u))
        if np.linalg.norm(sd) < 1e-6:
            sd = np.cross(u, self.up) if np.linalg.norm(np.cross(u, self.up)) > 1e-6 else self.fwd
        sd = sd / np.linalg.norm(sd)
        vv = np.cross(sd, u)                                           # (u, vv, sd) turns like (x, y, z)
        V = [(0, 1, 0), (0, -1, 0)]
        for j in range(1, m):
            ph = math.pi * j / m
            for i in range(n):
                t = 2 * math.pi * i / n
                V.append((math.sin(ph) * math.cos(t), math.cos(ph), math.sin(ph) * math.sin(t)))
        V = np.array(V, float)
        W = c + np.outer(V[:, 0] * a, u) + np.outer(V[:, 1] * b, vv) + np.outer(V[:, 2] * w, sd)
        F = []
        ring = lambda j, i: 2 + (j - 1) * n + (i % n)
        for i in range(n):
            F.append((0, ring(1, i + 1), ring(1, i)))
            F.append((1, ring(m - 1, i), ring(m - 1, i + 1)))
        for j in range(1, m - 1):
            for i in range(n):
                F.append((ring(j, i), ring(j, i + 1), ring(j + 1, i + 1), ring(j + 1, i)))
        mesh = self.S3.Mesh(W, F, ink=0.7, name=self.colour(part, col), smooth=True)
        self.out.append(mesh)
        return mesh

    def ball(self, c, r, col, part, n=10, m=6):
        return self.blob(c, self.fwd, r, r, r, col, part, n, m)

    def tube(self, p0, p1, r0, r1, col, part, n=9):
        """a tapered round limb from p0 (radius r0) to p1 (radius r1), world points, closed at both ends"""
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        d = p1 - p0
        L = float(np.linalg.norm(d))
        if L < 1e-6:
            return None
        d = d / L
        e1 = np.cross(d, self.side)
        if np.linalg.norm(e1) < 1e-6:
            e1 = np.cross(d, self.fwd)
        e1 = e1 / np.linalg.norm(e1)
        e2 = np.cross(e1, d)                                           # (e1, d, e2) turns like (x, y, z)
        V = []
        for p, r in ((p0, r0), (p1, r1)):
            for i in range(n):
                t = 2 * math.pi * i / n
                V.append(p + (e1 * math.cos(t) + e2 * math.sin(t)) * r)
        F = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            i2 = (i + 1) % n
            F.append((i, i2, n + i2, n + i))
        mesh = self.S3.Mesh(V, F, ink=0.7, name=self.colour(part, col), smooth=True)
        self.out.append(mesh)
        return mesh

    def chain(self, pts, r0, r1, col, part):
        """a bending limb (a tail, a trunk): tubes through world points, tapering, a ball at each bend"""
        n = len(pts) - 1
        for i in range(n):
            ra = r0 + (r1 - r0) * i / n
            rb = r0 + (r1 - r0) * (i + 1) / n
            self.tube(pts[i], pts[i + 1], ra, rb, col, part)
            if i > 0:
                self.ball(pts[i], ra, col, part, 8, 4)


# ---------------------------------------------------------------------------- the four-legged ones
def _stand_height(sp):
    k = sp["name"]
    if k not in _STAND:
        J = A.q_solve(A.Q_STAND, sp, 1.0)
        _STAND[k] = max(1.0, J["sh"][1])
    return _STAND[k]


def _quad(K, sp, pose, t, mouth, blink):
    J = A.q_solve(pose, sp, 1.0)
    name = sp["name"]
    fur = sp["fur"]
    belly = sp.get("belly") or _lighter(fur)
    g = sp["girth"]
    lw = sp.get("leg_w", g * 0.34)
    pat = sp.get("pattern")
    legc = (0.1, 0.1, 0.11) if pat == "panda" else fur
    hoof = (0.2, 0.17, 0.15) if sp.get("step") in ("hoof", "stomp") else None
    P = K.P
    # the body: one rounded mass along the spine (rump to chest), a little deeper than wide
    hx, hy = J["hip"]
    sx, sy = J["sh"]
    L = math.hypot(sx - hx, sy - hy)
    u = K.V(sx - hx, sy - hy)
    cb = P((hx + sx) / 2, (hy + sy) / 2 - g * 0.05)
    a, b, w = (L / 2 + g * 0.5) * K.k, g * 0.55 * K.k, g * 0.45 * K.k
    body = K.blob(cb, u, a, b, w, fur, "body", 16, 10)
    body.shadow = True
    vv = np.cross(K.side - u * float(np.dot(K.side, u)), u)
    vv = vv / max(1e-9, np.linalg.norm(vv))
    if vv[1] < 0:
        vv = -vv
    K.blob(cb - vv * b * 0.42, u, a * 0.82, b * 0.62, w * 0.9, belly, "belly", 14, 8)   # the lighter underside
    # its markings: shapes lying on the body
    rng = np.random.default_rng(sum(map(ord, name)))

    def on_body(fu, fv, side):                                        # a point on the body's surface
        return cb + u * (fu * a) + vv * (fv * b) + K.side * (side * w * math.sqrt(max(0.05, 1 - fu * fu - fv * fv)))
    if pat == "patches":
        for fu, fv, r in ((-0.45, 0.25, 0.32), (0.1, 0.35, 0.26), (0.45, -0.05, 0.2), (-0.1, -0.2, 0.18)):
            for side in (1, -1):
                K.blob(on_body(fu, fv, side), u, g * r * K.k, g * r * 0.8 * K.k, g * 0.06 * K.k,
                       (0.12, 0.11, 0.12), "patch", 10, 6)
    elif pat in ("spots", "leopard", "giraffe"):
        col = {"spots": (1, 0.97, 0.9), "leopard": (0.22, 0.14, 0.08), "giraffe": (0.6, 0.34, 0.13)}[pat]
        size = {"spots": 0.06, "leopard": 0.07, "giraffe": 0.14}[pat]
        for i in range(14 if pat != "giraffe" else 10):
            fu, fv = rng.uniform(-0.7, 0.65), rng.uniform(-0.1, 0.55)
            for side in (1, -1):
                K.blob(on_body(fu, fv, side), u, g * size * K.k, g * size * K.k, g * 0.03 * K.k, col, "spot", 8, 5)
    elif pat in ("stripes", "stripes_light", "zebra"):
        col = (0.08, 0.08, 0.09) if pat != "stripes_light" else _darker(fur, 0.72)
        nst = 7 if pat == "zebra" else 6
        for i in range(nst):
            fu = -0.7 + i * (1.4 / (nst - 1))
            sq = math.sqrt(max(0.1, 1 - fu * fu))
            K.blob(cb + u * (fu * a * 0.9) + vv * b * 0.1, u, g * 0.045 * K.k, b * 0.95 * sq, w * 1.04 * sq,
                   col, "stripe", 12, 4)
    elif pat == "panda":
        K.blob(cb + u * a * 0.45, u, a * 0.24, b * 0.95, w * 1.04, (0.1, 0.1, 0.11), "band", 14, 6)
    if sp.get("hump"):
        K.blob(P((hx + sx) / 2, (hy + sy) / 2 + g * 0.55), K.up, g * 0.38 * K.k, g * 0.35 * K.k, g * 0.3 * K.k,
               fur, "hump")
    if sp.get("udder"):
        K.ball(P(hx + L * 0.15, hy - g * 0.52), g * 0.13 * K.k, (0.96, 0.72, 0.74), "udder")
    # the legs, half a body's width either side: a thigh and a shin, a hoof or a paw
    for root, kn, pa, kf, pf, front in (("sj", "kfn", "pfn", "kff", "pff", True),
                                        ("hj", "kbn", "pbn", "kbf", "pbf", False)):
        for knee, paw, s in ((J[kn], J[pa], 1.0), (J[kf], J[pf], -1.0)):
            so = s * g * 0.3
            top = P(J[root][0], J[root][1] + g * 0.15, so)
            kp, pp = P(knee[0], knee[1], so), P(paw[0], paw[1] + lw * 0.2, so)
            K.tube(top, kp, lw * (0.62 if front else 0.75) * K.k, lw * 0.4 * K.k, legc, "leg")
            K.ball(kp, lw * 0.4 * K.k, legc, "leg", 8, 4)
            K.tube(kp, pp, lw * 0.4 * K.k, lw * 0.32 * K.k, legc, "leg")
            if hoof:
                K.tube(P(paw[0], paw[1] + lw * 0.32, so), P(paw[0], paw[1], so), lw * 0.33 * K.k, lw * 0.37 * K.k,
                       hoof, "hoof")
            else:
                K.blob(P(paw[0] + lw * 0.15, paw[1] + lw * 0.18, so), K.fwd, lw * 0.42 * K.k, lw * 0.2 * K.k,
                       lw * 0.32 * K.k, legc, "paw", 8, 5)
    # the neck and the head (a little big: a cartoon reads by its face)
    nb, ne = np.array(J["nb"], float), np.array(J["ne"], float)
    nw = sp.get("neck_w", g * 0.5)
    if np.hypot(*(ne - nb)) > 4:
        K.tube(P(*nb), P(*ne), nw * 0.55 * K.k, nw * 0.42 * K.k, fur, "neck")
    R = sp["head"] * 1.2
    na = math.atan2(ne[1] - nb[1], ne[0] - nb[0])
    rot = (na - math.radians(sp.get("neck_angle", 32))) * 0.55 - 0.3 + math.radians(pose.get("head", 0)) * 0.7
    hd = K.V(math.cos(rot), math.sin(rot))                            # the way the face points
    hup = np.cross(K.side, hd)
    if hup[1] < 0:
        hup = -hup
    C = P(*J["head"])

    def H(f, upw, s):                                                 # a point on the head, in head radii
        return C + (hd * f + hup * upw + K.side * s) * R * K.k
    _head(K, sp, C, hd, hup, H, R * K.k, t, mouth, blink, name, fur)
    _tail(K, sp, cb + vv * b * 0.35, t, pose, u, g, a)
    return H(0, 1.0, 0)


def _head(K, sp, C, hd, hup, H, r, t, mouth, blink, name, fur):
    headc = sp.get("headc") or fur
    mz = sp.get("muzzle") or _lighter(fur, 0.25)
    sl, sw = sp.get("snout", (20, 18))
    sl, sw = sl * K.k, sw * K.k
    if sp.get("mane") and name == "lion":                              # a big mane behind the face
        K.blob(C - hd * r * 0.35, hd, r * 1.05, r * 1.35, r * 1.3, sp["mane"], "mane", 12, 8)
    K.blob(C, hd, r * 1.0, r * 0.92, r * 0.85, headc, "head")
    if name == "elephant":                                             # the trunk hangs, sways, curls at the tip
        sw_ = 0.25 * math.sin(t * 1.6)
        pts, a, p = [], -1.35 + sw_, H(0.7, -0.1, 0)
        for i in range(7):
            pts.append(p)
            a += 0.08 if i < 5 else 0.55
            p = p + (hd * math.cos(a) + hup * math.sin(a)) * r * 0.42
        K.chain(pts, r * 0.32, r * 0.12, fur, "trunk")
        for s in (1, -1):
            K.tube(H(0.55, -0.45, 0.35 * s), H(1.15, -0.85, 0.45 * s), r * 0.09, r * 0.05, (1, 0.97, 0.88), "tusk")
    elif sp.get("snout_flat"):                                         # a pig: a short snout, a flat pink end
        K.tube(H(0.6, -0.15, 0), H(1.15, -0.2, 0), r * 0.4, r * 0.36, headc, "snout")
        K.blob(H(1.17, -0.2, 0), hd, r * 0.06, r * 0.36, r * 0.36, mz, "nose")
        for s in (1, -1):
            K.ball(H(1.22, -0.2, 0.13 * s), r * 0.07, _darker(mz, 0.45), "nostril", 6, 4)
    else:                                                              # a muzzle as long as the species' face
        tip = C + hd * (r * 0.55 + sl) - hup * (r * 0.28 + sl * 0.12)
        K.tube(H(0.4, -0.12, 0), tip, max(r * 0.42, sw * 0.55), sw * 0.48, mz, "snout")
        K.ball(tip, sw * 0.5, mz, "snout")
        nose = (0.15, 0.1, 0.1) if name not in ("cow", "pig", "buffalo") else _darker(mz, 0.75)
        K.blob(tip + hd * sw * 0.42 + hup * sw * 0.12, hd, sw * 0.12, sw * 0.2, sw * 0.32, nose, "nose", 8, 5)
        if mouth > 0.15:                                               # an open mouth: a dark wedge under the muzzle
            K.blob(tip - hup * sw * 0.45 - hd * sl * 0.25, hd, sl * 0.35, sw * 0.18 * (0.5 + mouth), sw * 0.3,
                   (0.4, 0.1, 0.12), "mouth", 8, 5)
    # the eyes: a white, a dark pupil (on both sides; the far one hides behind the head)
    for s in (1, -1):
        e = H(0.45, 0.3, 0.62 * s)
        if blink:
            K.blob(e, hd, r * 0.17, r * 0.04, r * 0.05, _darker(headc, 0.55), "lid", 8, 4)
        else:
            K.blob(e, hd, r * 0.17, r * 0.19, r * 0.08, EYE_W, "eye", 10, 6)
            K.ball(e + K.side * s * r * 0.06 + hd * r * 0.05, r * 0.1, PUPIL, "pupil", 8, 5)
    # the ears
    ears = sp.get("ears", "round")
    for s in (1, -1):
        if ears == "huge":                                             # an elephant's big flaps
            fl = 0.15 * math.sin(t * 2.0)
            K.blob(H(-0.25, 0.1, (0.95 + fl) * s), hd, r * 0.75, r * 0.95, r * 0.08, _darker(fur, 0.9), "ear", 12, 6)
        elif ears in ("side", "floppy"):
            dn = -0.35 if ears == "floppy" else 0.05
            K.blob(H(-0.15, 0.45 + dn, 0.95 * s), K.side * s + hup * (dn * 2), r * 0.45, r * 0.12, r * 0.25,
                   fur if ears == "side" else _darker(fur, 0.85), "ear", 10, 5)
        elif ears in ("pointy", "pointy_tall", "long"):
            h = {"pointy": 0.75, "pointy_tall": 1.0, "long": 1.7}[ears]
            K.tube(H(-0.2, 0.7, 0.45 * s), H(-0.3, 0.7 + h, 0.55 * s), r * 0.24, r * 0.03, fur, "ear", 6)
        else:                                                          # round
            K.blob(H(-0.3, 0.8, 0.6 * s), hd, r * 0.26, r * 0.28, r * 0.1,
                   (0.1, 0.1, 0.11) if sp.get("pattern") == "panda" else fur, "ear", 8, 5)
    if sp.get("pattern") == "panda":                                   # the black eye patches
        for s in (1, -1):
            K.blob(H(0.4, 0.25, 0.58 * s), hd, r * 0.26, r * 0.3, r * 0.06, (0.1, 0.1, 0.11), "patch", 8, 5)
    horns = sp.get("horns")
    if horns:
        hc = (0.93, 0.88, 0.76)
        for s in (1, -1):
            if horns == "curved":                                      # a goat's, swept back
                K.chain([H(-0.05, 0.8, 0.3 * s), H(-0.35, 1.35, 0.35 * s), H(-0.9, 1.45, 0.4 * s),
                         H(-1.15, 1.1, 0.42 * s)], r * 0.12, r * 0.05, hc, "horn")
            else:                                                      # a cow's short horns
                K.chain([H(-0.15, 0.75, 0.5 * s), H(-0.2, 1.0, 0.75 * s), H(-0.05, 1.25, 0.85 * s)], r * 0.1,
                        r * 0.04, hc, "horn")
    if sp.get("antlers"):
        ac = (0.62, 0.46, 0.3)
        for s in (1, -1):
            K.chain([H(-0.2, 0.8, 0.3 * s), H(-0.4, 1.6, 0.55 * s), H(-0.7, 2.3, 0.7 * s)], r * 0.08, r * 0.04, ac,
                    "antler")
            K.tube(H(-0.45, 1.7, 0.57 * s), H(0.05, 2.15, 0.62 * s), r * 0.06, r * 0.03, ac, "antler")
    if sp.get("mane") and name != "lion":                              # a horse's / zebra's mane down the crest
        K.blob(H(-0.75, 0.55, 0), hd - hup * 0.6, r * 0.9, r * 0.22, r * 0.1, sp["mane"], "mane", 10, 5)
    if sp.get("beard"):
        K.tube(H(0.7, -0.7, 0), H(0.6, -1.25, 0), r * 0.12, r * 0.03, _lighter(fur, 0.3), "beard", 6)


def _tail(K, sp, top, t, pose, u, g, a):
    """the tail, from the top of the rump (top: a point on the body's back, a the body's half-length)"""
    kind = sp.get("tail", "short_up")
    fur = sp["fur"]
    root = top - u * a * 0.88
    sw = math.radians(pose.get("tail", 15)) * 0.6 + 0.25 * math.sin(t * 2.4)
    if kind in ("short_up", "puff"):
        K.ball(root - u * g * 0.06 * K.k, g * 0.13 * K.k, sp.get("belly") if kind == "puff" else fur, "tail")
        return
    ln = {"tuft": 1.0, "tuft_thin": 0.9, "long": 1.4, "long_up": 1.3, "long_hair": 1.1, "bushy": 1.1, "curve": 0.9,
          "curly": 0.4}.get(kind, 1.0) * g * K.k
    up = 0.6 if kind in ("long_up", "curve", "bushy") else -1.2
    pts, p = [], root
    for i in range(5):
        pts.append(p)
        ang = up * (i + 1) / 5 + sw * (i / 5)
        d = -u * math.cos(ang) + K.up * math.sin(ang) + K.side * 0.25 * math.sin(t * 2.4 + i * 0.4)
        p = p + d / np.linalg.norm(d) * ln / 5
    pts.append(p)
    thick = g * K.k * (0.2 if kind in ("bushy", "long_hair") else 0.06)
    col = sp.get("mane") if kind == "long_hair" and sp.get("mane") else fur
    K.chain(pts, thick, thick * 0.6, col, "tail")
    if kind.startswith("tuft"):
        K.blob(p, -u, g * 0.1 * K.k, g * 0.14 * K.k, g * 0.1 * K.k, _darker(fur, 0.5), "tuft", 8, 5)
    if sp.get("tail_tip"):
        K.ball(p, thick * 1.1, sp["tail_tip"], "tailtip", 8, 5)


# ---------------------------------------------------------------------------- birds and the monkey
def _bird(K, sp, pose, t, moving, blink):
    b = sp.get("body", 30) * 1.25
    hr = sp.get("head", 14) * 1.1
    fur, belly = sp["fur"], sp.get("belly") or _lighter(sp["fur"])
    wing = sp.get("wing") or _darker(fur, 0.9)
    lift = pose.get("lift", 0) * 0.5
    peck = max(0.0, -pose.get("head", 0)) / 40.0
    leg_h = b * 0.55 * sp.get("leg_k", 1.0)
    ph = t * 6.0 if moving else 0.0
    ly = leg_h + lift
    for s, sh in ((1, 0.0), (-1, math.pi)):                            # two thin legs, stepping when it walks
        fx = math.sin(ph + sh) * b * 0.22 if moving else 0.0
        fy = max(0.0, math.cos(ph + sh)) * b * 0.12 if moving else 0.0
        K.tube(K.P(0, ly, s * b * 0.18), K.P(fx, fy, s * b * 0.18), b * 0.04 * K.k, b * 0.035 * K.k,
               (0.95, 0.62, 0.12), "leg", 6)
    by = ly + b * 0.5
    body = K.blob(K.P(0, by), K.V(1, 0.15), b * 0.75 * K.k, b * 0.55 * K.k, b * 0.5 * K.k, fur, "body", 14, 8)
    body.shadow = True
    K.blob(K.P(b * 0.2, by - b * 0.18), K.V(1, 0.1), b * 0.5 * K.k, b * 0.38 * K.k, b * 0.44 * K.k, belly, "belly")
    for s in (1, -1):                                                  # the folded wings
        K.blob(K.P(-b * 0.1, by + b * 0.05, s * b * 0.45), K.V(1, -0.2), b * 0.55 * K.k, b * 0.3 * K.k,
               b * 0.08 * K.k, wing, "wing", 10, 5)
    if sp.get("fan"):                                                  # a peacock's fan, open behind it
        p0 = K.P(-b * 0.5, by)
        for i in range(9):
            a = math.radians(-60 + i * 15)
            d = K.V(-0.35, 1.0) * math.cos(a) + K.side * math.sin(a)
            p1 = p0 + d * b * 2.2 * K.k
            K.tube(p0, p1, b * 0.05 * K.k, b * 0.05 * K.k, (0.15, 0.45, 0.3), "fan", 6)
            K.blob(p1, d, b * 0.2 * K.k, b * 0.16 * K.k, b * 0.04 * K.k, (0.12, 0.55, 0.42), "fan_eye", 8, 5)
            K.ball(p1 - K.fwd * b * 0.04 * K.k, b * 0.08 * K.k, (0.12, 0.3, 0.75), "fan_dot", 6, 4)
    else:
        tl = b * (1.6 if sp.get("tail_long") else 0.7)
        K.blob(K.P(-b * 0.65 - tl * 0.4, by + b * 0.15), K.V(-1, 0.35), tl * 0.5 * K.k, b * 0.1 * K.k,
               b * 0.28 * K.k, _darker(fur, 0.9), "tail", 10, 5)
    hx, hy = b * 0.6 + peck * b * 0.4, by + b * 0.55 - peck * b * 0.9
    C = K.P(hx, hy)
    K.ball(C, hr * K.k, sp.get("headc") or fur, "head")
    bc, bl = sp.get("beak", ((0.95, 0.62, 0.12), 10))
    if sp.get("flat_beak"):
        K.blob(K.P(hx + hr * 0.9 + bl * 0.35, hy - hr * 0.15), K.fwd, bl * 0.6 * K.k, hr * 0.15 * K.k,
               hr * 0.35 * K.k, bc, "beak", 10, 5)
    else:
        K.tube(K.P(hx + hr * 0.8, hy - hr * 0.1), K.P(hx + hr * 0.85 + bl * 1.2, hy - hr * 0.25), hr * 0.28 * K.k,
               hr * 0.02 * K.k, bc, "beak", 8)
    if sp.get("comb"):
        for i in range(3):
            K.ball(K.P(hx - hr * 0.3 + i * hr * 0.3, hy + hr * 0.95), hr * 0.22 * K.k, (0.88, 0.16, 0.16), "comb",
                   8, 5)
        K.ball(K.P(hx + hr * 0.75, hy - hr * 0.6), hr * 0.18 * K.k, (0.88, 0.16, 0.16), "wattle", 8, 5)
    for s in (1, -1):
        e = K.P(hx + hr * 0.35, hy + hr * 0.2, s * hr * 0.72)
        K.blob(e, K.fwd, hr * 0.2 * K.k, hr * 0.22 * K.k, hr * 0.08 * K.k, (1, 0.85, 0.3), "eye", 8, 5)
        if not blink:
            K.ball(e + K.side * s * hr * 0.06 * K.k, hr * 0.11 * K.k, PUPIL, "pupil", 6, 4)
    return K.P(hx, hy + hr)


def _monkey(K, t, moving, sitting, mouth, blink):
    fur, fc = MONKEY["fur"], MONKEY["face"]
    u = 30.0
    ph = t * 7.0 if moving else 0.0
    hip_y = u * (1.2 if sitting else 2.4)
    for s, sh in ((1, 0.0), (-1, math.pi)):                            # legs
        a = math.sin(ph + sh) * 0.5 if moving else 0.0
        hip = K.P(0, hip_y, s * u * 0.4)
        if sitting:
            knee, foot = K.P(u * 1.3, hip_y + u * 0.1, s * u * 0.5), K.P(u * 1.4, u * 0.15, s * u * 0.5)
        else:
            knee = K.P(math.sin(a) * u * 0.8, hip_y - u * 1.2, s * u * 0.4)
            foot = K.P(math.sin(a) * u * 1.2, u * 0.15, s * u * 0.4)
        K.tube(hip, knee, u * 0.3 * K.k, u * 0.24 * K.k, fur, "leg")
        K.ball(knee, u * 0.24 * K.k, fur, "leg", 8, 4)
        K.tube(knee, foot, u * 0.24 * K.k, u * 0.2 * K.k, fur, "leg")
        K.blob(foot + K.fwd * u * 0.25 * K.k, K.fwd, u * 0.38 * K.k, u * 0.14 * K.k, u * 0.2 * K.k, fc, "foot", 8, 5)
    by = hip_y + u * 1.0
    body = K.blob(K.P(0, by), K.up, u * 1.3 * K.k, u * 1.0 * K.k, u * 0.85 * K.k, fur, "body", 12, 8)
    body.shadow = True
    K.blob(K.P(u * 0.45, by - u * 0.1), K.up, u * 0.85 * K.k, u * 0.45 * K.k, u * 0.6 * K.k, fc, "belly")
    tail, p = [], K.P(-u * 0.8, hip_y + u * 0.3)                       # the long curling tail
    for i in range(9):
        tail.append(p)
        a = i * 0.45 + math.sin(t * 2) * 0.2
        p = p + (-K.fwd * math.cos(a) + K.up * math.sin(a) * 0.9) * u * 0.42 * K.k
    K.chain(tail, u * 0.14 * K.k, u * 0.09 * K.k, fur, "tail")
    sw = math.sin(ph) * 0.6 if moving else 0.25 * math.sin(t * 1.5)
    for s in (1, -1):                                                  # arms
        sh_ = K.P(u * 0.15, by + u * 0.85, s * u * 0.85)
        el = sh_ + K.V(math.sin(sw * s) * 0.6, -1, 0.1 * s) * u * 1.1 * K.k
        hd = el + K.V(0.4 + math.sin(sw * s) * 0.4, -0.9, 0) * u * 1.0 * K.k
        K.tube(sh_, el, u * 0.24 * K.k, u * 0.2 * K.k, fur, "arm")
        K.tube(el, hd, u * 0.2 * K.k, u * 0.18 * K.k, fur, "arm")
        K.ball(hd, u * 0.22 * K.k, fc, "hand", 8, 5)
    R = u * 0.95
    C = K.P(u * 0.25, by + u * 1.3 + R * 0.8)
    for s in (1, -1):                                                  # big round ears
        K.blob(C + (K.side * s * R * 0.98 + K.up * R * 0.1) * K.k, K.fwd, R * 0.38 * K.k, R * 0.42 * K.k,
               R * 0.12 * K.k, fc, "ear", 10, 5)
    K.ball(C, R * K.k, fur, "head", 12, 8)
    K.blob(C + (K.fwd * R * 0.55 - K.up * R * 0.15) * K.k, K.fwd, R * 0.5 * K.k, R * 0.62 * K.k, R * 0.72 * K.k,
           fc, "face", 12, 6)
    K.blob(C + (K.fwd * R * 0.95 - K.up * R * 0.4) * K.k, K.fwd, R * 0.3 * K.k, R * 0.28 * K.k, R * 0.4 * K.k,
           fc, "muzzle", 10, 6)
    if mouth > 0.15:
        K.blob(C + (K.fwd * R * 1.15 - K.up * R * 0.55) * K.k, K.fwd, R * 0.08 * K.k, (R * 0.1 * mouth + 1) * K.k,
               R * 0.22 * K.k, (0.4, 0.1, 0.12), "mouth", 8, 4)
    for s in (1, -1):
        e = C + (K.fwd * R * 0.9 + K.up * R * 0.15 + K.side * s * R * 0.32) * K.k
        K.blob(e, K.fwd, R * 0.07 * K.k, R * 0.2 * K.k, R * 0.17 * K.k, EYE_W if not blink else fc, "eye", 8, 5)
        if not blink:
            K.ball(e + K.fwd * R * 0.08 * K.k, R * 0.1 * K.k, PUPIL, "pupil", 6, 4)
    return C + K.up * R * K.k


# ---------------------------------------------------------------------------- one animal in the world
def meshes(S3, it, t):
    """one animal -> (its parts as Meshes in the world, the top of its head - for a speech bubble)"""
    sp_name = A.canon(it.get("species", "cow"))
    kind = kind_of(sp_name)
    ang = float(it.get("dir", 0.0))
    fwd = np.array([math.cos(ang), 0.0, math.sin(ang)])
    base = np.array(it["pos"], float)
    pose = it.get("pose") or {}
    moving = bool(it.get("moving"))
    act = str(it.get("do") or "")
    blink = (t * 0.37 + (sum(map(ord, str(it.get("id", "")))) % 7) * 0.13) % 3.3 < 0.12
    mouth = float(it.get("mouth") or 0.0)
    scale = float(it.get("scale", 1.0) or 1.0)
    if kind == "quad":
        sp = _sp(sp_name)
        if not isinstance(pose, dict) or "fl_t" not in pose:          # a place's animal: an action by name
            spec = A.Q_ACTIONS.get(act) or A.Q_ACTIONS["walk" if moving else "idle"]
            pose, _ = spec.fn(t, 2.0, {"sp": sp, "scale": 1.0, "speed": 0})
        k = size_m(sp_name) * M * scale / _stand_height(sp)
        K = Kit(S3, base, fwd, k, sp_name)
        head = _quad(K, sp, pose, t, mouth, blink)
    elif kind == "bird":
        sp = _sp(sp_name)
        if not isinstance(pose, dict) or "body" not in pose:
            spec = A.B_ACTIONS.get(act) or A.B_ACTIONS["walk" if moving else "idle"]
            pose, _ = spec.fn(t, 2.0, {"sp": sp, "scale": 1.0, "speed": 0})
        b = sp.get("body", 30) * 1.25
        k = size_m(sp_name) * M * scale / (b * 0.55 * sp.get("leg_k", 1.0) + b * 1.05 + sp.get("head", 14) * 1.1)
        K = Kit(S3, base, fwd, k, sp_name)
        head = _bird(K, sp, pose, t, moving, blink)
    else:
        k = MONKEY["tall_m"] * M * scale / (30.0 * 6.8)
        K = Kit(S3, base, fwd, k, "monkey")
        head = _monkey(K, t, moving, act in ("sit", "eat") or bool(it.get("sitting")), mouth, blink)
    return K.out, head
