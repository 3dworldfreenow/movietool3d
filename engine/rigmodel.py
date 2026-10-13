"""Imported models WITH a skeleton (rigged glTF / GLB) moved by OUR skeleton.

rig.model(pen, "villager_3d") inside a character3d code file:
  * the model's bones are matched to ours (found by itself from the bone names and the shape of the skeleton,
    or given as BONES = {...} in the code file)
  * every frame our pose solver says where hips, knees, feet, elbows, hands and head are;
    the matching bones are turned to point the same way (their own lengths are kept - long legs stay long)
  * the body bends with the bones (linear blend skinning, numpy) and is drawn as our flat-coloured faces
Local frame (same as the rig): x = forward, y = up, z = to the side (+z = the model's LEFT, "far").
"""
import math
import os
import re

import numpy as np

from . import model3d
from .model3d import ModelError

ARM = ("clavicle", "upper_arm", "forearm", "hand")
LEG = ("thigh", "shin", "foot", "toe")
ROLES = ["hips", "spine", "neck", "head"] + [f"{s}_{r}" for s in ("r", "l") for r in ARM + LEG]
_CACHE = {}
MAX_FACES = 1800                   # people are drawn many times per frame: a bit lighter than objects


# ============================================================================ reading the skinned file
def _world_mats(G, node_matrix):
    nodes = G.get("nodes") or []
    parent = [-1] * len(nodes)
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            if c < len(nodes):
                parent[c] = i
    W = [None] * len(nodes)

    def w(i, depth=0):
        if W[i] is None:
            L = node_matrix(nodes[i])
            W[i] = L if parent[i] < 0 or depth > 200 else w(parent[i], depth + 1) @ L
        return W[i]
    for i in range(len(nodes)):
        w(i)
    return W, parent


def read_skinned(path):
    """-> dict in glTF axes and units: V (n,3) rest vertices, JI (n,4) joint ids, W (n,4) weights,
    T (m,3) triangles (vertex ids), C (m,4) colours, names [material per tri],
    joints [node ids], jnames, jparent (index into joints or -1), rest (J,3) joint positions"""
    gf = model3d._gltf_open(path)
    G, acc = gf.G, gf.accessor
    if not G.get("skins"):
        raise ModelError("this model has no skeleton (bones) - import it as an object instead")
    nodes = G.get("nodes") or []
    Wm, nparent = _world_mats(G, gf.node_matrix)
    joints = []
    for sk in G["skins"]:
        for j in sk.get("joints", []):
            if j not in joints:
                joints.append(j)
    jidx = {n: i for i, n in enumerate(joints)}

    def joint_anc(n):                                     # nearest ancestor that is a joint
        p = nparent[n]
        while p >= 0 and p not in jidx:
            p = nparent[p]
        return jidx.get(p, -1)
    jparent = [joint_anc(n) for n in joints]
    rest = np.array([Wm[n][:3, 3] for n in joints], np.float64)
    Vs, JIs, Ws, Ts, Cs, names = [], [], [], [], [], []
    morph_parts = {}                                      # face shape name -> [(first vertex, deltas)]
    base = 0
    for ni, n in enumerate(nodes):
        if "mesh" not in n:
            continue
        sk = G["skins"][n["skin"]] if "skin" in n else None
        if sk is not None:
            sj = [jidx[j] for j in sk["joints"]]
            if "inverseBindMatrices" in sk:
                ibm = acc(sk["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
            else:
                ibm = np.tile(np.eye(4), (len(sj), 1, 1))
            S = np.array([Wm[j] for j in sk["joints"]]) @ ibm          # rest skin matrices
        else:                                             # a stiff part (a hat on the head bone ...)
            p, anc = nparent[ni], -1
            while p >= 0:
                if p in jidx:
                    anc = jidx[p]
                    break
                p = nparent[p]
        for p in G["meshes"][n["mesh"]].get("primitives", []):
            at = p.get("attributes") or {}
            if "POSITION" not in at or p.get("mode", 4) != 4:
                continue
            P = acc(at["POSITION"])[:, :3]
            nv = len(P)
            idx = acc(p["indices"]).reshape(-1).astype(np.int64) if "indices" in p else np.arange(nv)
            idx = idx[: len(idx) // 3 * 3].reshape(-1, 3)
            idx = idx[(idx < nv).all(axis=1)]
            if not len(idx):
                continue
            if sk is not None and "JOINTS_0" in at and "WEIGHTS_0" in at:
                J = acc(at["JOINTS_0"]).astype(np.int64)[:, :4]
                Wt = acc(at["WEIGHTS_0"])[:, :4]
                J = np.clip(J, 0, len(sj) - 1)
                Wt = Wt / np.maximum(Wt.sum(1, keepdims=True), 1e-9)
                M = S[J]                                          # (nv,4,4,4)
                Ph = np.concatenate([P, np.ones((nv, 1))], 1)
                V = np.einsum("vk,vkij,vj->vi", Wt, M, Ph)[:, :3]
                JI = np.array(sj)[J]
            else:
                V = (P @ Wm[ni][:3, :3].T) + Wm[ni][:3, 3]
                JI = np.full((nv, 4), anc if sk is None else sj[0], np.int64)
                Wt = np.tile([1.0, 0, 0, 0], (nv, 1))
            tnames = (G["meshes"][n["mesh"]].get("extras") or {}).get("targetNames") or \
                (p.get("extras") or {}).get("targetNames") or []
            for ti, tg in enumerate(p.get("targets") or []):
                nm_ = str(tnames[ti]) if ti < len(tnames) else f"morph_{ti}"
                if "POSITION" not in tg or not face_role(nm_):
                    continue                              # only the face shapes we can drive
                D = acc(tg["POSITION"])[:, :3]
                if len(D) != nv:
                    continue
                if sk is not None and "JOINTS_0" in at and "WEIGHTS_0" in at:
                    D = np.einsum("vk,vkij,vj->vi", Wt, M[:, :, :3, :3], D)
                else:
                    D = D @ Wm[ni][:3, :3].T
                if np.abs(D).max() > 1e-7:
                    morph_parts.setdefault(nm_, []).append((base, D))
            f, tex, tc, mname = gf.material(p.get("material"))
            C = np.tile(f, (len(idx), 1))
            uvk = f"TEXCOORD_{tc}"
            if tex is not None and uvk in at:
                UV = acc(at[uvk])[:, :2]
                C = C * model3d._sample(tex, model3d._tri_uv_samples(UV[idx]), flip_v=False)
            if "COLOR_0" in at:
                VC = acc(at["COLOR_0"])
                if VC.shape[1] == 3:
                    VC = np.concatenate([VC, np.ones((len(VC), 1))], 1)
                C = C * VC[idx].mean(axis=1)
            Vs.append(V)
            JIs.append(JI)
            Ws.append(Wt)
            Ts.append(idx + base)
            Cs.append(C)
            names += [mname] * len(idx)
            base += nv
    if not Vs:
        raise ModelError("no triangles found in this file")
    JI = np.concatenate(JIs)
    JI[JI < 0] = 0
    nV = sum(len(v) for v in Vs)
    morphs = {}
    for nm_, parts in morph_parts.items():
        D = np.zeros((nV, 3))
        for b0, d in parts:
            D[b0:b0 + len(d)] += d
        morphs[nm_] = D
    return {"morphs": morphs, "V": np.concatenate(Vs), "JI": JI, "W": np.concatenate(Ws), "T": np.concatenate(Ts),
            "C": np.clip(np.concatenate(Cs), 0, 1), "names": names, "joints": joints,
            "jnames": [str(nodes[n].get("name") or f"joint_{i}") for i, n in enumerate(joints)],
            "jparent": jparent, "rest": rest}


def rest_tris_gltf(path):
    """Static import of a skinned model: its triangles in the rest pose (glTF axes)."""
    d = read_skinned(path)
    return d["V"][d["T"]], d["C"], d["names"]


# ============================================================================ which bone is which
def _norm_name(n):
    n = str(n).split(":")[-1].split("|")[-1]
    n = re.sub(r"([a-z])([A-Z])", r"\1_\2", n)            # camelCase -> camel_case
    return re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")


def _side(n):
    toks = _norm_name(n).split("_")
    for t in toks:
        if t.startswith("left") or t == "l" or re.fullmatch(r"l\d+", t):
            return "l"
        if t.startswith("right") or t == "r" or re.fullmatch(r"r\d+", t):
            return "r"
    return None


def _base(n):
    toks = [t for t in _norm_name(n).split("_") if not (t in ("l", "r", "left", "right", "mixamorig", "def", "bip01",
                                                                 "bip", "b", "armature", "skeleton", "joint", "jnt",
                                                                 "bone", "c", "cc", "base")
                                                        or re.fullmatch(r"[lr]\d+", t))]
    s = "".join(toks)
    return re.sub(r"^(left|right)|(left|right)$", "", s)


_FINGER = re.compile(r"thumb|index|middle|ring|pinky|pinkie|finger|palm|digit|claw")
_ENDISH = re.compile(r"end$|nub$|tip$|top$|^ik|ik$|pole|target|ctrl|control|twist|roll|helper|aim|^j?sec|adj|eye|jaw|tongue|teeth|"
                     r"hair|breast|weapon|prop")


def _role_by_name(n):
    b = _base(n)
    b0 = re.sub(r"\d+$", "", b)
    if _FINGER.search(b) or _ENDISH.search(b):
        return None
    side = _side(n)
    if side:
        if re.search(r"toe|ball", b):
            return "toe"
        if re.search(r"foot|ankle", b):
            return "foot"
        if re.search(r"upleg|upperleg|thigh", b) or b0 in ("hip", "leg1", "legupper"):
            return "thigh"
        if re.search(r"shin|calf|knee|lowerleg|legl?ower", b) or b0 in ("leg", "leg2"):
            return "shin"
        if re.search(r"hand|wrist", b):
            return "hand"
        if re.search(r"forearm|lowerarm|elbow|armlower", b):
            return "forearm"
        if re.search(r"upperarm|armupper", b) or b0 in ("arm", "arm1"):
            return "upper_arm"
        if re.search(r"shoulder|clavicle|collar", b):
            return "clavicle"
        return None
    if re.search(r"hips|pelvis", b) or b0 == "hip":
        return "hips"
    if re.search(r"head", b):
        return "head"
    if re.search(r"neck", b):
        return "neck"
    if re.search(r"spine|chest|torso|abdomen|back|belly|waist|stomach", b):
        return "spine"
    return None


def auto_bones(jnames, jparent, rest):
    """-> {role: joint name} (spine: [names]) found by itself.  rest in glTF axes (y up)."""
    J = len(jnames)
    kids = [[] for _ in range(J)]
    for i, p in enumerate(jparent):
        if p >= 0:
            kids[p].append(i)
    depth = [0] * J
    for i in range(J):
        p, d = jparent[i], 0
        while p >= 0 and d < 500:
            p, d = jparent[p], d + 1
        depth[i] = d

    def anc(i):
        out, p = [], jparent[i]
        while p >= 0 and len(out) < 500:
            out.append(p)
            p = jparent[p]
        return out

    def path(a, b):                                        # joints from a (excl.) down to b (incl.)
        out, p = [], b
        while p >= 0 and p != a and len(out) < 500:
            out.append(p)
            p = jparent[p]
        return out[::-1] if p == a else []

    role = {i: _role_by_name(jnames[i]) for i in range(J)}
    side = {i: _side(jnames[i]) for i in range(J)}
    out = {}
    # ---- hips
    hips = [i for i in range(J) if role[i] == "hips"]
    h = min(hips, key=lambda i: depth[i]) if hips else None
    if h is None:                                          # where the two legs meet
        lows = {}
        for s in ("l", "r"):
            c = [i for i in range(J) if side[i] == s]
            if c:
                lows[s] = min(c, key=lambda i: rest[i][1])
        if len(lows) == 2:
            a1, a2 = set(anc(lows["l"])), anc(lows["r"])
            common = [a for a in a2 if a in a1]
            h = common[0] if common else None
        if h is None:
            h = min(range(J), key=lambda i: (depth[i], -len(kids[i])))
    th = {sd: [i for i in range(J) if role[i] == "thigh" and side[i] == sd] for sd in ("l", "r")}
    if th["l"] and th["r"]:                                # the legs hang from where the two thighs meet
        a1 = set(anc(min(th["l"], key=lambda i: depth[i])))
        common = [a for a in anc(min(th["r"], key=lambda i: depth[i])) if a in a1]
        if common and (h is None or h not in a1):
            h = common[0]
    out["hips"] = h
    under = set()
    stack = [h]
    while stack:
        i = stack.pop()
        under.add(i)
        stack.extend(kids[i])
    hy = rest[h][1]
    # ---- legs and arms per side
    for s in ("l", "r"):
        sided = [i for i in under if side[i] == s and i != h]
        legs = [i for i in sided if rest[i][1] < hy]
        byname = {}
        for i in sorted(sided, key=lambda i: depth[i]):
            if role[i] in LEG and role[i] not in byname:
                byname[role[i]] = i
        if "thigh" in byname and "shin" in byname:
            for r_, i in byname.items():
                out[f"{s}_{r_}"] = i
            legs = []
        if legs:
            low = min(legs, key=lambda i: rest[i][1])
            chain = [i for i in path(h, low) if side[i] == s]
            named = {role[i]: i for i in chain if role[i] in LEG}
            if len(named) < 3 and chain:
                rest_roles = [r for r in LEG]
                named = {rest_roles[k]: i for k, i in enumerate(chain[:4])}
                if len(chain) == 2:
                    named = {"thigh": chain[0], "shin": chain[1]}
            for r_, i in named.items():
                out[f"{s}_{r_}"] = i
        taken = {v for k, v in out.items() if k != "spine" and not isinstance(v, list)}
        arms = [i for i in sided if rest[i][1] >= hy and not _FINGER.search(_base(jnames[i])) and i not in taken
                and role[i] not in LEG]
        if arms:
            far = max(arms, key=lambda i: abs(rest[i][0] - rest[h][0]) + abs(rest[i][2] - rest[h][2]))
            chain = [i for i in path(h, far) if side[i] == s]
            named = {}
            for i in chain:
                if role[i] in ARM and role[i] not in named:
                    named[role[i]] = i
            if not ({"upper_arm", "forearm"} <= set(named)) and chain:
                n = len(chain)
                order = ARM if n >= 4 else ARM[1:]
                named = {order[k]: i for k, i in enumerate(chain[:len(order)])}
            for r_, i in named.items():
                out[f"{s}_{r_}"] = i
    # ---- spine, neck, head: the line from the hips up to the top
    top = max(under, key=lambda i: rest[i][1])
    up = [i for i in path(h, top) if side[i] is None]
    heads = [i for i in up if role[i] == "head"]
    necks = [i for i in up if role[i] == "neck"]
    if heads:
        out["head"] = heads[0]
    elif len(necks) >= 2:
        out["head"] = necks[-1]
    elif up:
        cand = [i for i in up if not _ENDISH.search(_base(jnames[i]))] or up
        out["head"] = cand[-1] if len(cand) > 1 else cand[0]
    if necks and necks[0] != out.get("head"):
        out["neck"] = necks[0]
    hd = out.get("head")
    stop = up.index(hd) if hd in up else len(up)
    nk = out.get("neck")
    sp = [i for i in up[:stop] if i != nk and (role[i] in ("spine", "hips") or role[i] is None)]
    if nk is None and len(sp) >= 2 and not any(role[i] == "spine" for i in sp[-1:]):
        out["neck"] = sp.pop()
    out["spine"] = sp
    names = {}
    for k, v in out.items():
        names[k] = [jnames[i] for i in v] if k == "spine" else jnames[v]
    return names


# ============================================================================ loading, ready to pose
def _rot_y_to_x(fwd):
    a = math.atan2(fwd[2], fwd[0])
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _simplify(V, JI, W, T, C, names, max_faces, keep=None):
    """keep: vertices never merged (the head: the face keeps all its detail - it does not count in max_faces)."""
    hold = keep if (keep is not None and keep.any()) else None
    if hold is not None:
        max_faces = max_faces + int(hold[T].all(axis=1).sum())
    if len(T) <= max_faces:
        return V, JI, W, T, C, names, np.arange(len(V))
    lo = V.min(0)
    size = float((V.max(0) - lo).max()) or 1.0
    nm = np.array(names, dtype=object)

    def cluster(n):
        q = np.floor((V - lo) / (size / n)).astype(np.int64)
        dom = JI[np.arange(len(JI)), W.argmax(1)]              # only vertices that follow the same bone merge
        key = ((q[:, 0] * n + q[:, 1]) * n + q[:, 2]) * (int(JI.max()) + 1) + dom
        if hold is not None:                                   # head vertices: each its own (never merged)
            key = np.where(hold, -1 - np.arange(len(V), dtype=np.int64), key)
        uk, first, inv = np.unique(key, return_index=True, return_inverse=True)
        t = inv[T]
        ok = (t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])
        t2 = t[ok]
        _, keep = np.unique(np.sort(t2, 1), axis=0, return_index=True)
        keep.sort()
        sel = np.nonzero(ok)[0][keep]
        return first, t2[keep], sel

    best, a, b = None, 4, 512
    while a <= b:
        m = (a + b) // 2
        r = cluster(m)
        if len(r[1]) <= max_faces:
            best, a = r, m + 1
        else:
            b = m - 1
    first, t, sel = best if best is not None else cluster(4)
    return V[first], JI[first], W[first], t, C[sel], list(nm[sel]), first


def load(name, max_faces=None, bones=None, head="full"):
    """-> the model ready to pose (rig axes, feet on y = 0, facing +x, model units = metres).
    head="full": the head keeps every triangle (faces stay sharp); "simple": simplified like the body (far away)."""
    path = model3d.find_file(name) if not os.path.isfile(str(name)) else str(name)
    if not path:
        raise ModelError(f"no model called '{name}' (import it in 🧊 3D Code > 📦 Import)")
    mf = int(max_faces or MAX_FACES)
    key = (path, os.path.getmtime(path), mf, repr(sorted((bones or {}).items())), head)
    if key in _CACHE:
        return _CACHE[key]
    if not path.lower().endswith((".glb", ".gltf", ".vrm")):
        raise ModelError("moving people / animals need a rigged .glb or .gltf file (with bones)")
    d = read_skinned(path)
    jnames, jparent = d["jnames"], d["jparent"]
    found = auto_bones(jnames, jparent, d["rest"])
    if bones:                                              # the code file's BONES win
        for k, v in bones.items():
            if k in ROLES and v:
                found[k] = v
    bad = [n for k, v in found.items() for n in (v if isinstance(v, list) else [v]) if n not in jnames]
    if bad:
        raise ModelError("BONES: no bone called " + ", ".join(repr(b) for b in bad) +
                         " in this model. Its bones: " + ", ".join(jnames[:60]))
    ix = {n: i for i, n in enumerate(jnames)}
    roles = {k: ([ix[n] for n in v] if isinstance(v, list) else ix[v]) for k, v in found.items()}
    missing = [r for r in ("hips", "r_thigh", "l_thigh", "r_shin", "l_shin") if r not in roles]
    if missing:
        raise ModelError("could not find these bones: " + ", ".join(missing) +
                         " - write them in BONES = {...} (the model's bones: " + ", ".join(jnames[:60]) + ")")
    # glTF (right-handed, y up, front +z) -> rig axes (x forward, y up, z = left)
    conv = np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]], np.float64)
    V = d["V"] @ conv.T
    rest = d["rest"] @ conv.T
    morphs = {k: D @ conv.T for k, D in (d.get("morphs") or {}).items()}
    T = d["T"][:, ::-1]
    # which way does it face?  forward = up x left
    left = np.zeros(3)
    for a_, b_ in (("l_thigh", "r_thigh"), ("l_upper_arm", "r_upper_arm")):
        if a_ in roles and b_ in roles:
            left += rest[roles[a_]] - rest[roles[b_]]
    if np.linalg.norm(left[[0, 2]]) > 1e-9:
        fwd = np.cross([0.0, 1.0, 0.0], left)
        Ry = _rot_y_to_x(fwd)
        V, rest = V @ Ry.T, rest @ Ry.T
        morphs = {k: D @ Ry.T for k, D in morphs.items()}
    y0 = V[:, 1].min()
    V[:, 1] -= y0
    rest[:, 1] -= y0
    ctr = np.array([rest[roles["hips"]][0], 0.0, rest[roles["hips"]][2]])
    V, rest = V - ctr, rest - ctr
    keep = None
    if head == "full" and "head" in roles:                 # the head and everything on it (eyes, hair ends)
        hj = roles["head"]
        sub = {hj}
        grew = True
        while grew:
            grew = False
            for i_, p_ in enumerate(jparent):
                if p_ in sub and i_ not in sub:
                    sub.add(i_)
                    grew = True
        dom = d["JI"][np.arange(len(d["JI"])), d["W"].argmax(1)]
        keep = np.isin(dom, list(sub))
        if keep.sum() > 0.45 * len(keep):                  # (not a sensible head: simplify everything)
            keep = None
    V, JI, W, T, C, names, keep_ix = _simplify(V, d["JI"], d["W"], T, d["C"], d["names"], mf, keep)
    morphs = {k: D[keep_ix] for k, D in morphs.items()}
    # head: its middle and size (the vertices that mostly follow the head bone)
    hc, hr = None, None
    if "head" in roles:
        hj = roles["head"]
        mask = (JI[:, 0] == hj) & (W[:, 0] > 0.5)
        if mask.sum() >= 4:
            pts = V[mask]
            hc = (pts.min(0) + pts.max(0)) / 2
            hr = float((pts.max(0) - pts.min(0)).max() / 2)
        else:
            hc, hr = rest[hj] + np.array([0.0, 0.08 * V[:, 1].max(), 0.0]), 0.07 * V[:, 1].max()
    J = len(jnames)
    kids = [[] for _ in range(J)]
    for i, p in enumerate(jparent):
        if p >= 0:
            kids[p].append(i)
    out = {"V": V, "JI": JI, "W": W, "T": T, "C": C, "names": names, "jnames": jnames, "jparent": jparent,
           "kids": kids, "rest": rest, "roles": roles, "bones": found, "height": float(V[:, 1].max()),
           "head_c": hc, "head_r": hr, "file": path, "faces_in": int(len(d["T"])),
           "morphs": morphs, "face_map": face_map(list(morphs))}
    out["order"] = _order(out)
    if len(_CACHE) > 20:
        _CACHE.clear()
    _CACHE[key] = out
    return out


def _order(m):
    """joints in the order they are posed: the hips' tree first, then everything else"""
    h = m["roles"]["hips"]
    seen, order, q = {h}, [h], [h]
    while q:
        i = q.pop(0)
        for k in m["kids"][i]:
            if k not in seen:
                seen.add(k)
                order.append(k)
                q.append(k)
    under = len(order)
    rest_ = [i for i in range(len(m["jnames"])) if i not in seen]
    rest_.sort(key=lambda i: _depth(m["jparent"], i))
    return order, under, rest_


def _depth(par, i):
    d = 0
    while par[i] >= 0 and d < 500:
        i, d = par[i], d + 1
    return d


# ============================================================================ posing
def _unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else v


def _frame(up, side=(0.0, 0.0, 1.0)):
    u = _unit(np.asarray(up, np.float64))
    sd = np.asarray(side, np.float64) - u * float(np.dot(side, u))
    sd = _unit(sd)
    f = np.cross(u, sd)
    return np.stack([f, u, sd], 1)


def _swing(a, b):
    """the smallest turn taking direction a to direction b"""
    a, b = _unit(a), _unit(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    s = float(np.linalg.norm(v))
    if s < 1e-9:
        if c > 0:
            return np.eye(3)
        ax = _unit(np.cross(a, [1.0, 0, 0] if abs(a[0]) < 0.9 else [0, 1.0, 0]))
        return 2 * np.outer(ax, ax) - np.eye(3)
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * (K @ K)


_REST = {}


def _rest_rig(rig):
    """our own skeleton standing still (for sizes: hip height, ankle height, head top)"""
    c = rig._c
    key = (getattr(c, "id", ""), round(float(c.scale), 4), c.age, c.gender)
    if key not in _REST:
        from .char3d import HumanRig, pose_at
        p, _ = pose_at(c, "idle", 0.0)
        _REST[key] = HumanRig(c, p)
        if len(_REST) > 64:
            _REST.clear()
    return _REST[key]


def pose(m, rig, height=None):
    """-> (vertices (n,3) posed in the rig frame, joint positions, joint turns, scale)"""
    rr = _rest_rig(rig)
    top_ours = rr.head[1] + rr.head_r
    s = float(height or top_ours) / max(m["height"], 1e-9)
    rest = m["rest"] * s
    V = (m["V"] + face_offsets(m, rig)) * s
    R = m["roles"]
    J = len(m["jnames"])
    D = np.zeros((J, 3, 3))
    P = np.zeros((J, 3))
    done = np.zeros(J, bool)
    A = np.asarray
    # ---- our targets
    tgt = {}
    for side, s_ in (("near", "r"), ("far", "l")):
        hip, knee, foot, toe = (A(p, np.float64) for p in rig.leg(side))
        sh, el, hd = (A(p, np.float64) for p in rig.arm(side))
        tgt[f"{s_}_thigh"] = knee - hip
        tgt[f"{s_}_shin"] = foot - knee
        tgt[f"{s_}_foot"] = toe - foot
        tgt[f"{s_}_upper_arm"] = el - sh
        tgt[f"{s_}_forearm"] = hd - el
    hipc, waist, chest, neck, head = (A(p, np.float64) for p in (rig.hip, rig.waist, rig.chest, rig.neck, rig.head))
    frames = {"hips": _frame(waist - hipc), "neck": _frame(head - neck), "head": _frame(A(rig.up, np.float64))}
    line = [hipc, waist, chest, neck]
    seg = [float(np.linalg.norm(line[i + 1] - line[i])) for i in range(3)]
    tot = sum(seg) or 1.0

    def spine_dir(f):
        d = f * tot
        for i in range(3):
            if d <= seg[i] or i == 2:
                return line[i + 1] - line[i]
            d -= seg[i]
    sp = R.get("spine", [])
    for k, j in enumerate(sp):
        frames[("spine", j)] = _frame(spine_dir((k + 0.5) / max(1, len(sp))))
    role_of = {}
    for k, v in R.items():
        if k == "spine":
            for j in v:
                role_of[j] = ("spine", j)
        else:
            role_of[v] = k
    child_of = {}                                          # the next mapped joint along each limb
    for s_ in ("r", "l"):
        for chain in (ARM, LEG):
            ids = [R.get(f"{s_}_{r}") for r in chain]
            for a_, b_ in zip(ids, ids[1:]):
                if a_ is not None and b_ is not None:
                    child_of[a_] = b_
    # ---- the hips: where our hips are (model sizes)
    h = R["hips"]
    k_ = rest[h][1] / max(rr.hip[1], 1e-6)
    D[h] = frames["hips"]
    P[h] = np.array([rig.hip[0] * k_, rest[h][1] + (rig.hip[1] - rr.hip[1]) * k_, rest[h][2]])
    done[h] = True
    order, under, others = m["order"]
    par = m["jparent"]
    for j in order[1:under]:
        p = par[j]
        Dp = D[p]
        r = role_of.get(j)
        if r in frames:
            Dj = frames[r]
        elif r in tgt and j in child_of:
            d_rest = rest[child_of[j]] - rest[j]
            Dj = _swing(Dp @ d_rest, tgt[r]) @ Dp
        elif r in tgt and m["kids"][j]:
            d_rest = rest[m["kids"][j][0]] - rest[j]
            Dj = _swing(Dp @ d_rest, tgt[r]) @ Dp
        else:
            Dj = Dp
        D[j] = Dj
        P[j] = P[p] + Dp @ (rest[j] - rest[p])
        done[j] = True
    anc = set()
    p = par[h]
    while p >= 0:
        anc.add(p)
        p = par[p]
    posed = np.array(order[:under])
    for j in others:                                       # above the hips / loose bones (IK helpers ...)
        if j in anc:
            D[j], P[j] = D[h], P[h] + D[h] @ (rest[j] - rest[h])
        elif par[j] >= 0 and done[par[j]] and par[j] not in anc:
            p = par[j]
            D[j], P[j] = D[p], P[p] + D[p] @ (rest[j] - rest[p])
        else:
            a_ = posed[np.argmin(np.linalg.norm(rest[posed] - rest[j], axis=1))]
            D[j], P[j] = D[a_], P[a_] + D[a_] @ (rest[j] - rest[a_])
        done[j] = True
    # ---- feet on the ground like ours (sitting, jumping, lying down ...)
    feet = [R[k] for k in ("r_foot", "l_foot") if k in R] or [R[k] for k in ("r_shin", "l_shin") if k in R]
    if feet:
        ours_now = min(rig.leg("near")[2][1], rig.leg("far")[2][1])
        ours_rest = min(rr.leg("near")[2][1], rr.leg("far")[2][1])
        want = min(rest[f][1] for f in feet) + (ours_now - ours_rest) * k_
        P[:, 1] += want - min(P[f][1] for f in feet)
    # ---- the body follows the bones
    JI, W = m["JI"], m["W"]
    out = np.zeros_like(V)
    for c in range(JI.shape[1]):
        w = W[:, c]
        if not w.any():
            continue
        j = JI[:, c]
        out += w[:, None] * (np.einsum("nij,nj->ni", D[j], V - rest[j]) + P[j])
    return out, P, D, s


def draw_on_rig(pen, rig, name, height=None, colors=None, bones=None, max_faces=None, two_sided=False, head=None):
    if head is None:                                       # far away (crowds, wide shots): a lighter head too
        head = "full" if getattr(pen, "detail", 1.0) >= 0.55 else "simple"
    m = load(name, max_faces, bones, head)
    Vp, P, D, s = pose(m, rig, height)
    tris = Vp[m["T"]]
    pen._add_tris(tris, m["C"], colors, two_sided)
    R = m["roles"]
    if m["head_c"] is not None and "head" in R:            # speech bubbles, hats and looks go to the new head
        hj = R["head"]
        c = P[hj] + D[hj] @ (m["head_c"] * s - m["rest"][hj] * s)
        rig.head = (float(c[0]), float(c[1]), float(c[2]))
        rig.head_r = float(m["head_r"] * s)
    for side, s_ in (("near", "r"), ("far", "l")):         # held things go to the new hands
        j = R.get(f"{s_}_hand", R.get(f"{s_}_forearm"))
        if j is not None:
            setattr(rig, "hand_" + side, (float(P[j][0]), float(P[j][1]), float(P[j][2])))
    return {"faces": int(len(tris)), "height": float(m["height"] * s)}


def info(name, max_faces=None, bones=None, head="full"):
    m = load(name, max_faces, bones, head)
    return {"faces_in": m["faces_in"], "faces": int(len(m["T"])), "bones": m["bones"], "all_bones": m["jnames"],
            "height_m": round(m["height"], 3), "animations": clips_of(m["file"])}


def clips_of(path):
    """[(name, seconds)] of the animations saved in a .glb (a Mixamo move)."""
    try:
        G = model3d._gltf_open(path).G
    except Exception:
        return []
    out = []
    for a in G.get("animations") or []:
        secs = (a.get("extras") or {}).get("seconds")
        if secs is None:
            try:
                acc = G["accessors"][a["samplers"][0]["input"]]
                secs = float((acc.get("max") or [0])[0])
            except (KeyError, IndexError):
                secs = 0.0
        out.append((a.get("name") or "clip", round(float(secs), 2)))
    return out


def has_bones(name):
    p = model3d.find_file(name)
    if not p or not p.lower().endswith((".glb", ".gltf", ".vrm")):
        return False
    try:
        return bool(model3d._gltf_open(p).G.get("skins"))
    except Exception:
        return False


def make_code(name, kind="character3d", height=None, description="", max_faces=None, head="full"):
    """An editable character3d file: the model on our skeleton, with its bone matching written out."""
    import json
    nm = model3d._clean(name)
    i = info(nm)
    meta = model3d.list_models().get(nm, {})
    m = load(nm)
    pal = model3d._groups(m["C"], m["names"])[:8]
    cols = "\n".join(f'        "{h}": "{h}",   # {n} faces ({mat})' for h, n, mat, _ in pal)
    b = i["bones"]
    order = ["hips", "spine", "neck", "head"] + [f"{s}_{r}" for s in ("r", "l") for r in ARM + LEG]
    rows = []
    for k in order:
        if k in b:
            rows.append(f'    "{k}": {json.dumps(b[k])},')
        else:
            rows.append(f'    # "{k}": "",   (not found - optional)')
    lines = ['KIND = "character3d"', 'FOR = "human"',
             f'DESCRIPTION = {json.dumps(description or re.sub(r"_3d$", "", nm).replace("_", " ") + " (imported model)")}',
             'PREVIEW = {"age": "adult", "gender": "male"}',
             f'MODEL = "{nm}"',
             f'CREDIT = {json.dumps(meta.get("credit") or "")}',
             f'LICENSE = {json.dumps(meta.get("license") or "")}',
             f'SOURCE = {json.dumps(meta.get("source") or "")}',
             "",
             f"# Imported from {os.path.basename(m['file'])}: {i['faces_in']} triangles, {i['faces']} drawn,"
             f" {len(i['all_bones'])} bones.",
             "# BONES: which bone of the model is which part of our skeleton (r = right, l = left).",
             "# Found by itself - if an arm or leg moves wrong, put the right bone name here. All its bones:",
             "#   " + ", ".join(i["all_bones"][:80])[:1500],
             "BONES = {", *rows, "}", "",
             "# Every action works (walk, run, sit, dance, wave, fight ...). Use it on a character:",
             f'#   "look3d": "{nm}"   (3D page)   - or name this file <character id>_3d.',
             "# height = None: as tall as the character (children smaller).  colors: like pen.model.",
             "def draw(pen, rig, t, state):",
             f'    rig.model(pen, "{nm}", bones=BONES, height={height if height else None},'
             f'{" max_faces=" + str(int(max_faces)) + "," if max_faces else ""}'
             f'{" head=" + json.dumps(head) + "," if head and head != "full" else ""} colors={{',
             cols, "    })", ""]
    return "\n".join(lines)


# ============================================================================ face shapes (morph targets)
def _fn(name):
    n = str(name).split(".")[-1].split(":")[-1]
    return re.sub(r"[^a-z0-9]", "", n.lower())


# our face control -> name patterns (ARKit, Oculus visemes, VRoid / VRM, simple names)
_FACE = [
    # mouth shapes by letter (A closed .. H tongue): Oculus / VRoid / VRM vowels
    ("vA", r"^(visemepp|pp|vrcvpp|mthpp)$"), ("vB", r"^(visemess|visemei|visemeih|visemedd|visemenn|visemekk|visemech|ih|fclmthi|mthi|i|ee|vrcvih|vrcvss)$"),
    ("vC", r"^(visemee|fclmthe|mthe|e|vrcve)$"), ("vD", r"^(visemeaa|fclmtha|mtha|a|aa|vrcvaa)$"),
    ("vE", r"^(visemeo|visemeoh|fclmtho|mtho|o|oh|vrcvoh)$"), ("vF", r"^(visemeu|visemeou|fclmthu|mthu|u|ou|vrcvou)$"),
    ("vG", r"^(visemeff|ff|vrcvff)$"), ("vH", r"^(visemeth|visemerr|th|vrcvth)$"),
    # continuous (ARKit)
    ("jaw", r"^(jawopen|mouthopen|open|mouthopened)$"), ("round", r"^(mouthfunnel|mouthpucker)$"),
    ("wide", r"^(mouthstretch(l|r|left|right)?)$"), ("closed", r"^(mouthclose|mouthpress(l|r|left|right)?)$"),
    ("blink", r"^(eyeblink(l|r|left|right)?|blink(l|r|left|right)?|fcleyeclose|fcleyeclose(l|r)|eyesclosed|eyeclose)$"),
    ("brow", r"^(browinnerup|browouterup(l|r|left|right)?|browsup|browup|fclbrwsurprised)$"),
    # emotions
    ("happy", r"^(fclalljoy|mouthsmile(l|r|left|right)?|smile|happy|joy|fun|fclallfun)$"),
    ("sad", r"^(fclallsorrow|mouthfrown(l|r|left|right)?|sad|sorrow)$"),
    ("angry", r"^(fclallangry|browdown(l|r|left|right)?|angry|anger)$"),
    ("surprised", r"^(fclallsurprised|eyewide(l|r|left|right)?|surprised|surprise|shock)$"),
]


def face_role(name):
    n = _fn(name)
    for role, pat in _FACE:
        if re.match(pat, n):
            return role
    return None


def face_map(names):
    """{role: [shape names]} for a model's face shapes"""
    out = {}
    for nm in names:
        r = face_role(nm)
        if r:
            out.setdefault(r, []).append(nm)
    return out


def face_weights(fm, rig):
    """{shape name: weight 0..1} for this moment (the voice's mouth shape, blink, brows, emotion)."""
    ms = getattr(rig, "mouth_shape", None) or {}
    ctl = getattr(rig, "talk", None) or {}
    w = {}

    def put(role, val):
        for nm in fm.get(role, ()):
            w[nm] = max(w.get(nm, 0.0), max(0.0, min(1.0, float(val))))
    open_ = ms.get("jaw", 0.0) * (1.0 - ms.get("closed", 0.0))
    letters = [r for r in fm if r.startswith("v")]
    if letters and ctl.get("shape"):                        # the model has mouth shapes per sound: use them
        sh = ctl["shape"]
        if sh != "X" and ("v" + sh) in fm:
            put("v" + sh, 1.0 if sh == "A" else min(1.0, 0.45 + 0.9 * open_))
        elif sh != "X" and "vD" in fm:
            put("vD", open_)
    else:
        put("jaw", open_)
        put("vD", open_ if "jaw" not in fm else 0.0)
        put("round", ms.get("round", 0.0) * min(1.0, open_ * 2.5 + 0.3))
        put("wide", max(0.0, ms.get("wide", 0.5) - 0.5) * 1.6 * min(1.0, open_ * 3))
        put("closed", ms.get("closed", 0.0) * 0.5 if ctl.get("shape") == "A" else 0.0)
    put("blink", getattr(rig, "lid", 0.0))
    put("brow", getattr(rig, "brow", 0.0))
    face = getattr(rig, "face", "neutral")
    put("happy", {"happy": 0.8, "laughing": 1.0}.get(face, 0.0))
    put("sad", {"sad": 0.8, "crying": 1.0}.get(face, 0.0))
    put("angry", 0.8 if face == "angry" else 0.0)
    put("surprised", {"surprised": 0.9, "scared": 0.6}.get(face, 0.0))
    return w


def face_offsets(m, rig):
    """sum of the face shapes (model units, rest pose) for this moment"""
    fm = m.get("face_map") or {}
    if not fm:
        return 0.0
    out = None
    for nm, wt in face_weights(fm, rig).items():
        if wt > 1e-3 and nm in m["morphs"]:
            d = m["morphs"][nm] * wt
            out = d if out is None else out + d
    return 0.0 if out is None else out
