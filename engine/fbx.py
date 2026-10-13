"""FBX (Mixamo and most 3D tools) -> GLB, so it works like every other imported model.

Pure Python + numpy (no Blender, no SDK, CPU only). Reads binary FBX (Mixamo's "FBX Binary" and "FBX for Unity"):
  * meshes (triangulated), UVs, the embedded skin texture (or the .fbm folder next to the file)
  * the skeleton (Mixamo bone names), skin weights (up to 4 bones per vertex), the bind pose
  * animations (a Mixamo move: dance, punch, wave ...) - sampled at 30 fps into glTF animation channels
  * units (Mixamo = centimetres) and the up axis
Writes assets/models/<name>/<name>.glb. engine/rigmodel.py then moves it with our skeleton, and engine/mocap.py turns
its animation into one of our actions.

    from engine import fbx;  fbx.convert("Samba Dancing.fbx", "samba")      ->  path of the .glb
"""
import json
import math
import os
import struct
import zlib

import numpy as np

MAGIC = b"Kaydara FBX Binary  \x00"
KTIME = 46186158000.0                    # FBX time units per second


class FBXError(Exception):
    pass


# ============================================================================ 1. the binary file -> node tree
class Node:
    __slots__ = ("name", "props", "kids")

    def __init__(self, name, props, kids):
        self.name, self.props, self.kids = name, props, kids

    def find(self, name):
        for k in self.kids:
            if k.name == name:
                return k
        return None

    def all(self, name):
        return [k for k in self.kids if k.name == name]

    def p70(self):
        """Properties70 -> {name: [values]}"""
        out = {}
        b = self.find("Properties70")
        if b is not None:
            for p in b.kids:
                if p.name == "P" and p.props:
                    out[p.props[0]] = p.props[4:]
        return out


def _read_prop(data, o):
    t = chr(data[o])
    o += 1
    if t == "Y":
        return struct.unpack_from("<h", data, o)[0], o + 2
    if t == "C":
        return bool(data[o]), o + 1
    if t == "I":
        return struct.unpack_from("<i", data, o)[0], o + 4
    if t == "F":
        return struct.unpack_from("<f", data, o)[0], o + 4
    if t == "D":
        return struct.unpack_from("<d", data, o)[0], o + 8
    if t == "L":
        return struct.unpack_from("<q", data, o)[0], o + 8
    if t in "fdlib":
        n, enc, clen = struct.unpack_from("<III", data, o)
        o += 12
        raw = data[o:o + clen]
        o += clen
        if enc == 1:
            raw = zlib.decompress(raw)
        dt = {"f": "<f4", "d": "<f8", "l": "<i8", "i": "<i4", "b": "u1"}[t]
        return np.frombuffer(raw, dt, count=n).copy(), o
    if t in "SR":
        n = struct.unpack_from("<I", data, o)[0]
        o += 4
        raw = bytes(data[o:o + n])
        o += n
        if t == "S":
            return raw.decode("utf-8", "replace").replace("\x00\x01", "::"), o
        return raw, o
    raise FBXError(f"unknown FBX property type {t!r}")


def _read_node(data, o, v75):
    if v75:
        end, nprops, _plen = struct.unpack_from("<QQQ", data, o)
        o += 24
    else:
        end, nprops, _plen = struct.unpack_from("<III", data, o)
        o += 12
    nlen = data[o]
    o += 1
    if end == 0:
        return None, o
    name = bytes(data[o:o + nlen]).decode("ascii", "replace")
    o += nlen
    props = []
    for _ in range(nprops):
        v, o = _read_prop(data, o)
        props.append(v)
    kids = []
    null = 25 if v75 else 13
    while o < end - null + 1 and o < end:
        if end - o == null and not any(data[o:end]):
            o = end
            break
        k, o2 = _read_node(data, o, v75)
        if k is None:
            o = o2
            break
        kids.append(k)
        o = o2
    return Node(name, props, kids), end


def parse(path):
    data = open(path, "rb").read()
    if not data.startswith(MAGIC):
        if data[:200].lstrip().startswith(b";") or b"FBXHeaderExtension" in data[:2000]:
            raise FBXError("this is a text (ASCII) FBX - export it again as FBX Binary (Mixamo: Format 'FBX Binary')")
        raise FBXError("not an FBX file")
    ver = struct.unpack_from("<I", data, 23)[0]
    v75 = ver >= 7500
    o = 27
    top = []
    while o < len(data) - 160:
        n, o = _read_node(data, o, v75)
        if n is None:
            break
        top.append(n)
    return Node("root", [], top), ver


# ============================================================================ 2. maths
def _euler(rx, ry, rz, order=0):
    """FBX euler (degrees) -> 3x3. order 0 = XYZ (rotate X first)."""
    a, b, c = math.radians(rx), math.radians(ry), math.radians(rz)
    X = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Y = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    Z = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    seq = {0: (X, Y, Z), 1: (X, Z, Y), 2: (Y, Z, X), 3: (Y, X, Z), 4: (Z, X, Y), 5: (Z, Y, X)}.get(int(order), (X, Y, Z))
    return seq[2] @ seq[1] @ seq[0]


def _m4(R=None, t=None, s=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if s is not None:
        M[:3, :3] = M[:3, :3] @ np.diag(s)
    if t is not None:
        M[:3, 3] = t
    return M


def _local(props, T=None, R=None, S=None):
    """FBX local transform: T * Roff * Rp * Rpre * R * Rpost^-1 * Rp^-1 * Soff * Sp * S * Sp^-1"""
    def v(k, d):
        x = props.get(k)
        return np.array(x[:3], float) if x and len(x) >= 3 else np.array(d, float)
    order = int((props.get("RotationOrder") or [0])[0]) if props.get("RotationOrder") else 0
    t = v("Lcl Translation", (0, 0, 0)) if T is None else np.array(T, float)
    r = v("Lcl Rotation", (0, 0, 0)) if R is None else np.array(R, float)
    s = v("Lcl Scaling", (1, 1, 1)) if S is None else np.array(S, float)
    pre, post = v("PreRotation", (0, 0, 0)), v("PostRotation", (0, 0, 0))
    roff, rp = v("RotationOffset", (0, 0, 0)), v("RotationPivot", (0, 0, 0))
    soff, sp = v("ScalingOffset", (0, 0, 0)), v("ScalingPivot", (0, 0, 0))
    Rm = _euler(*r, order=order)
    Rpre, Rpost = _euler(*pre), _euler(*post)
    M = _m4(t=t) @ _m4(t=roff) @ _m4(t=rp) @ _m4(R=Rpre) @ _m4(R=Rm) @ np.linalg.inv(_m4(R=Rpost)) @ \
        _m4(t=-rp) @ _m4(t=soff) @ _m4(t=sp) @ _m4(s=s) @ _m4(t=-sp)
    return M


def _quat(R):
    """3x3 rotation (may carry scale) -> (x, y, z, w)"""
    U, _S, Vt = np.linalg.svd(R)
    R = U @ Vt
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w, x, y, z = (R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w, x, y, z = (R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w, x, y, z = (R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s
    q = np.array([x, y, z, w])
    return q / (np.linalg.norm(q) or 1.0)


# ============================================================================ 3. the FBX scene
class Scene:
    def __init__(self, path):
        root, self.version = parse(path)
        self.path = path
        self.notes = []
        objs = root.find("Objects")
        if objs is None:
            raise FBXError("no Objects in this FBX")
        self.obj = {}
        for n in objs.kids:
            if n.props:
                self.obj[n.props[0]] = n
        self.parent = {}                 # child id -> [(parent id, property)]
        self.children = {}               # parent id -> [(child id, property)]
        con = root.find("Connections")
        for c in (con.kids if con is not None else []):
            if c.name != "C" or len(c.props) < 3:
                continue
            kind, a, b = c.props[0], c.props[1], c.props[2]
            prop = c.props[3] if len(c.props) > 3 else None
            self.parent.setdefault(a, []).append((b, prop))
            self.children.setdefault(b, []).append((a, prop))
        gs = root.find("GlobalSettings")
        g = gs.p70() if gs is not None else {}
        self.unit = float((g.get("UnitScaleFactor") or [1.0])[0])         # centimetres per unit
        self.up = int((g.get("UpAxis") or [1])[0])
        self.up_sign = int((g.get("UpAxisSign") or [1])[0])

    def kind(self, i):
        n = self.obj.get(i)
        return (n.name, n.props[2] if n is not None and len(n.props) > 2 else "") if n is not None else (None, None)

    def name(self, i):
        n = self.obj.get(i)
        if n is None or len(n.props) < 2:
            return str(i)
        return str(n.props[1]).split("::")[0]

    def models(self):
        return [i for i, n in self.obj.items() if n.name == "Model"]

    def model_parent(self, i):
        for p, _prop in self.parent.get(i, []):
            if p == 0 or (p in self.obj and self.obj[p].name == "Model"):
                return p if p != 0 else None
        return None


# ============================================================================ 4. scene -> GLB
class _Bin:
    def __init__(self):
        self.data = bytearray()
        self.views, self.accs = [], []

    def add(self, arr, ctype, typ, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        while len(self.data) % 4:
            self.data += b"\x00"
        off = len(self.data)
        self.data += arr.tobytes()
        v = {"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes}
        if target:
            v["target"] = target
        self.views.append(v)
        nc = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[typ]
        a = {"bufferView": len(self.views) - 1, "componentType": ctype, "count": int(arr.size // nc), "type": typ}
        if minmax:
            r = arr.reshape(-1, nc)
            a["min"], a["max"] = [float(x) for x in r.min(0)], [float(x) for x in r.max(0)]
        self.accs.append(a)
        return len(self.accs) - 1

    def raw(self, b):
        while len(self.data) % 4:
            self.data += b"\x00"
        off = len(self.data)
        self.data += b
        self.views.append({"buffer": 0, "byteOffset": off, "byteLength": len(b)})
        return len(self.views) - 1


def _texture_bytes(sc, tex_id):
    """The picture of a Texture: embedded Video content, or the file next to the FBX / in its .fbm folder."""
    for vid, _p in sc.children.get(tex_id, []):
        n = sc.obj.get(vid)
        if n is not None and n.name == "Video":
            c = n.find("Content")
            if c is not None and c.props and isinstance(c.props[0], (bytes, bytearray)) and len(c.props[0]) > 16:
                return bytes(c.props[0])
    n = sc.obj.get(tex_id)
    if n is None:
        return None
    base = os.path.dirname(sc.path)
    stem = os.path.splitext(os.path.basename(sc.path))[0]
    from .model3d import find_near
    names = []
    for key in ("RelativeFilename", "FileName"):
        f = n.find(key)
        if f is not None and f.props and str(f.props[0]).strip():
            fn = str(f.props[0]).replace("\\", "/")
            names.append(fn)
            for cand in (os.path.join(base, fn), os.path.join(base, os.path.basename(fn)),
                         os.path.join(base, stem + ".fbm", os.path.basename(fn))):
                if os.path.isfile(cand):
                    return open(cand, "rb").read()
    for fn in names:                                      # anywhere in the uploaded folder, any capitals
        cand = find_near(base, fn)
        if cand:
            return open(cand, "rb").read()
    if names:
        sc.notes.append(f"the texture '{os.path.basename(names[0])}' was not uploaded - upload the .fbx with its "
                        "pictures (a .zip, or the .fbm folder), or export from Mixamo/Blender with 'embed textures'")
    return None


COLOR_PROPS = ("diffuse", "basecolor", "base_color", "albedo", "maya|basecolor", "color")
NOT_COLOR = ("normal", "bump", "specular", "rough", "metal", "emissive", "opacity", "transparen", "shininess",
             "reflect", "displace", "ambient", "height", "occlu")


def _is_colour_prop(prop):
    p = (prop or "").lower().replace(" ", "")
    return any(w in p for w in COLOR_PROPS) and not any(w in p for w in NOT_COLOR)


def to_glb(src, out_path, fps=30.0, max_anim_s=30.0):
    """Convert an FBX file to a GLB. -> dict(info) (bones, triangles, clips, seconds)."""
    sc = Scene(src)
    k = sc.unit / 100.0                                   # file units -> metres (Mixamo: cm -> 0.01)
    if sc.up == 2:                                        # Z up -> Y up
        AX = _m4(R=np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float) * (1 if sc.up_sign >= 0 else -1))
    else:
        AX = np.eye(4)
    ROOT = AX @ np.diag([k, k, k, 1.0])
    models = sc.models()
    mprops = {i: sc.obj[i].p70() for i in models}
    local = {i: _local(mprops[i]) for i in models}
    par = {i: sc.model_parent(i) for i in models}
    world_cache = {}

    def world(i):
        if i in world_cache:
            return world_cache[i]
        p = par[i]
        w = (world(p) if p is not None else np.eye(4)) @ local[i]
        world_cache[i] = w
        return w

    # ---- skin clusters: bone model id -> (cluster node), mesh geometry -> skin
    geo_skin = {}
    for i, n in sc.obj.items():
        if n.name == "Deformer" and len(n.props) > 2 and n.props[2] == "Skin":
            for g, _p in sc.parent.get(i, []):
                geo_skin[g] = i
    bones = set()
    clusters = {}                                          # skin id -> [(bone id, cluster node)]
    for skin_id in set(geo_skin.values()):
        lst = []
        for cid, _p in sc.children.get(skin_id, []):
            cn = sc.obj.get(cid)
            if cn is None or cn.name != "Deformer":
                continue
            bone = next((b for b, _pp in sc.children.get(cid, []) if b in mprops), None)
            if bone is None:
                continue
            lst.append((bone, cn))
            bones.add(bone)
        clusters[skin_id] = lst
    for i in models:                                       # every LimbNode is a bone (and its parents up the chain)
        if len(sc.obj[i].props) > 2 and sc.obj[i].props[2] in ("LimbNode", "Root"):
            bones.add(i)
    for b in list(bones):
        p = par[b]
        while p is not None and p not in bones:
            if len(sc.obj[p].props) > 2 and sc.obj[p].props[2] in ("LimbNode", "Root", "Null"):
                bones.add(p)
            p = par[p]
    # ---- glTF nodes: one root (axes + units), then every model that is a bone or holds a mesh
    B = _Bin()
    nodes = [{"name": "fbx_root", "matrix": [float(x) for x in ROOT.T.reshape(-1)], "children": []}]
    nid = {}
    order = sorted(models, key=lambda i: _depth(par, i))
    for i in order:
        n_ = {"name": sc.name(i)}
        L = local[i]
        t = L[:3, 3]
        sx = np.linalg.norm(L[:3, :3], axis=0)
        n_["translation"] = [float(x) for x in t]
        n_["rotation"] = [float(x) for x in _quat(L[:3, :3] / np.maximum(sx, 1e-9))]
        if np.abs(sx - 1).max() > 1e-4:
            n_["scale"] = [float(x) for x in sx]
        nid[i] = len(nodes)
        nodes.append(n_)
    for i in order:
        p = par[i]
        host = nodes[nid[p]] if p in nid else nodes[0]
        host.setdefault("children", []).append(nid[i])
    joint_list = [b for b in order if b in bones]
    jix = {b: j for j, b in enumerate(joint_list)}
    # ---- meshes
    meshes, materials, images, textures = [], [], [], []
    mat_index = {}
    n_tris = 0
    for i in order:
        geos = [g for g, _p in sc.children.get(i, []) if g in sc.obj and sc.obj[g].name == "Geometry"]
        for g in geos:
            gn = sc.obj[g]
            Vn, Pn = gn.find("Vertices"), gn.find("PolygonVertexIndex")
            if Vn is None or Pn is None:
                continue
            V = np.asarray(Vn.props[0], float).reshape(-1, 3)
            PV = np.asarray(Pn.props[0], np.int64)
            # polygons -> triangles (fan), one glTF vertex per polygon corner
            ends = np.nonzero(PV < 0)[0]
            cp = np.where(PV < 0, ~PV, PV)
            tris = []
            start = 0
            for e in ends:
                for a in range(start + 1, e):
                    tris.append((start, a, a + 1))
                start = e + 1
            tris = np.array(tris, np.int64)
            if not len(tris):
                continue
            uv = _layer(gn, "LayerElementUV", "UV", "UVIndex", len(PV), cp, 2)
            vcol = _layer(gn, "LayerElementColor", "Colors", "ColorIndex", len(PV), cp, 4)   # vertex paint
            mats = _layer_mat(gn, len(ends))
            poly_of_corner = np.zeros(len(PV), np.int64)
            start = 0
            for pi, e in enumerate(ends):
                poly_of_corner[start:e + 1] = pi
                start = e + 1
            pos = V[cp]
            # skin weights per control point -> corners
            J = np.zeros((len(V), 4), np.int64)
            Wt = np.zeros((len(V), 4), np.float64)
            skin_id = geo_skin.get(g)
            ibms = None
            if skin_id is not None and joint_list:
                allw = [[] for _ in range(len(V))]
                ibms = np.tile(np.eye(4), (len(joint_list), 1, 1))
                for bone, cn in clusters.get(skin_id, []):
                    ix, wn = cn.find("Indexes"), cn.find("Weights")
                    tl = cn.find("TransformLink")
                    if tl is not None:
                        # bind: the bone's world matrix then (TransformLink); the mesh's own world matrix from
                        # the model (exporters disagree on what "Transform" holds, so it is not used)
                        TL = np.asarray(tl.props[0], float).reshape(4, 4).T
                        ibms[jix[bone]] = np.linalg.inv(TL) @ world(i)
                    if ix is None or wn is None:
                        continue
                    for vi, w in zip(np.asarray(ix.props[0], np.int64), np.asarray(wn.props[0], float)):
                        if 0 <= vi < len(V) and w > 1e-4:
                            allw[vi].append((w, jix[bone]))
                for vi, lst in enumerate(allw):
                    lst.sort(reverse=True)
                    lst = lst[:4]
                    s = sum(w for w, _j in lst) or 1.0
                    for kk, (w, j) in enumerate(lst):
                        J[vi, kk], Wt[vi, kk] = j, w / s
                    if not lst:
                        Wt[vi, 0] = 1.0
            # one primitive per material
            prims = []
            for mslot in sorted(set(mats[poly_of_corner[tris[:, 0]]].tolist())):
                sel = tris[mats[poly_of_corner[tris[:, 0]]] == mslot]
                used = np.unique(sel.reshape(-1))
                remap = -np.ones(len(PV), np.int64)
                remap[used] = np.arange(len(used))
                idx = remap[sel].astype(np.uint32)
                att = {"POSITION": B.add(pos[used].astype(np.float32), 5126, "VEC3", 34962, True)}
                if uv is not None:
                    u = uv[used].astype(np.float32).copy()
                    u[:, 1] = 1.0 - u[:, 1]                    # FBX v goes up, glTF v goes down
                    att["TEXCOORD_0"] = B.add(u, 5126, "VEC2", 34962)
                if vcol is not None:
                    att["COLOR_0"] = B.add(np.clip(vcol[used], 0, 1).astype(np.float32), 5126, "VEC4", 34962)
                if ibms is not None:
                    att["JOINTS_0"] = B.add(J[cp[used]].astype(np.uint16), 5123, "VEC4", 34962)
                    att["WEIGHTS_0"] = B.add(Wt[cp[used]].astype(np.float32), 5126, "VEC4", 34962)
                prim = {"attributes": att, "indices": B.add(idx.reshape(-1), 5125, "SCALAR", 34963), "mode": 4}
                mat_id = _material_of(sc, i, mslot)
                if mat_id is not None:
                    if mat_id not in mat_index:
                        mat_index[mat_id] = len(materials)
                        materials.append(_gltf_material(sc, mat_id, B, images, textures))
                    prim["material"] = mat_index[mat_id]
                prims.append(prim)
                n_tris += len(sel)
            if not prims:
                continue
            nodes[nid[i]]["mesh"] = len(meshes)
            meshes.append({"name": sc.name(g), "primitives": prims})
            if ibms is not None:
                nodes[nid[i]]["skin"] = 0
                skin_ibm = ibms
    gl = {"asset": {"version": "2.0", "generator": "stickman-studio fbx.py",
                    "extras": {"notes": list(dict.fromkeys(sc.notes))}}, "scene": 0,
          "scenes": [{"nodes": [0]}], "nodes": nodes, "meshes": meshes}
    if joint_list:
        if "skin_ibm" not in dir():
            skin_ibm = np.array([np.linalg.inv(world(b)) for b in joint_list])
        gl["skins"] = [{"joints": [nid[b] for b in joint_list], "skeleton": nid[joint_list[0]],
                        "inverseBindMatrices": B.add(skin_ibm.transpose(0, 2, 1).astype(np.float32).reshape(-1, 16),
                                                     5126, "MAT4")}]
    if materials:
        gl["materials"] = materials
    if images:
        gl["images"], gl["textures"] = images, textures
        gl["samplers"] = [{}]
    # ---- animations
    clips = _animations(sc, models, mprops, nid, fps, max_anim_s, B)
    if clips:
        gl["animations"] = clips
    gl["accessors"], gl["bufferViews"] = B.accs, B.views
    gl["buffers"] = [{"byteLength": len(B.data)}]
    js = json.dumps(gl, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    bn = bytes(B.data)
    while len(bn) % 4:
        bn += b"\x00"
    total = 12 + 8 + len(js) + 8 + len(bn)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(bn), 0x004E4942) + bn)
    secs = max([c.get("extras", {}).get("seconds", 0) for c in clips] or [0])
    return {"path": out_path, "bones": len(joint_list), "triangles": int(n_tris), "clips": [c["name"] for c in clips],
            "seconds": secs, "textures": len(images), "unit_m": k}


def _depth(par, i):
    d = 0
    while par.get(i) is not None and d < 500:
        i = par[i]
        d += 1
    return d


def _layer(gn, lname, dname, iname, n_corners, cp, nc):
    L = gn.find(lname)
    if L is None:
        return None
    d = L.find(dname)
    if d is None:
        return None
    data = np.asarray(d.props[0], float).reshape(-1, nc)
    mp = L.find("MappingInformationType")
    rf = L.find("ReferenceInformationType")
    mp = str(mp.props[0]) if mp is not None else "ByPolygonVertex"
    rf = str(rf.props[0]) if rf is not None else "Direct"
    if mp in ("ByPolygonVertex", "ByPolygonVertices"):
        if rf == "IndexToDirect" and L.find(iname) is not None:
            ix = np.asarray(L.find(iname).props[0], np.int64)
            ix = np.clip(ix, 0, len(data) - 1)
            return data[ix[:n_corners]] if len(ix) >= n_corners else None
        return data[:n_corners] if len(data) >= n_corners else None
    if mp in ("ByVertex", "ByVertice", "ByControlPoint"):
        if rf == "IndexToDirect" and L.find(iname) is not None:
            ix = np.asarray(L.find(iname).props[0], np.int64)
            return data[np.clip(ix[cp], 0, len(data) - 1)]
        return data[np.clip(cp, 0, len(data) - 1)]
    return None


def _layer_mat(gn, n_polys):
    L = gn.find("LayerElementMaterial")
    if L is None or L.find("Materials") is None:
        return np.zeros(n_polys, np.int64)
    m = np.asarray(L.find("Materials").props[0], np.int64)
    mp = L.find("MappingInformationType")
    if mp is not None and str(mp.props[0]) == "AllSame" or len(m) < n_polys:
        return np.full(n_polys, int(m[0]) if len(m) else 0, np.int64)
    return m[:n_polys]


def _material_of(sc, model_id, slot):
    mats = [c for c, _p in sc.children.get(model_id, []) if c in sc.obj and sc.obj[c].name == "Material"]
    if not mats:
        return None
    return mats[min(slot, len(mats) - 1)]


def _gltf_material(sc, mid, B, images, textures):
    p = sc.obj[mid].p70()
    col = p.get("DiffuseColor") or p.get("Diffuse") or p.get("Maya|baseColor") or p.get("BaseColor") \
        or [0.8, 0.8, 0.8]
    f = p.get("DiffuseFactor")
    fk = float(f[0]) if isinstance(f, (list, tuple)) and f else (float(f) if isinstance(f, (int, float)) else 1.0)
    if 0.05 < fk < 1.0:                                   # (a factor of 0 is an exporter bug: ignore it)
        col = [float(c) * fk for c in col[:3]]
    m = {"name": sc.name(mid), "pbrMetallicRoughness": {"baseColorFactor": [float(col[0]), float(col[1]),
                                                                            float(col[2]), 1.0],
                                                         "metallicFactor": 0.0, "roughnessFactor": 0.8}}
    for tid, prop in sc.children.get(mid, []):
        if tid in sc.obj and sc.obj[tid].name == "Texture" and _is_colour_prop(prop):
            data = _texture_bytes(sc, tid)
            if data:
                mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
                if data[:2] not in (b"\xff\xd8",) and data[:4] != b"\x89PNG":
                    try:                                  # (tga / bmp / psd ...) -> png
                        import io
                        from PIL import Image
                        buf = io.BytesIO()
                        Image.open(io.BytesIO(data)).convert("RGBA").save(buf, "PNG")
                        data, mime = buf.getvalue(), "image/png"
                    except Exception:
                        sc.notes.append(f"the texture of '{sc.name(mid)}' is a picture type that could not be read "
                                        "- save it as PNG or JPEG")
                        continue
                images.append({"bufferView": B.raw(data), "mimeType": mime})
                textures.append({"source": len(images) - 1, "sampler": 0})
                m["pbrMetallicRoughness"]["baseColorTexture"] = {"index": len(textures) - 1}
                m["pbrMetallicRoughness"]["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
                break
    return m


def _curve(sc, cid):
    n = sc.obj.get(cid)
    if n is None or n.name != "AnimationCurve":
        return None
    kt, kv = n.find("KeyTime"), n.find("KeyValueFloat")
    if kt is None or kv is None:
        return None
    t = np.asarray(kt.props[0], np.int64) / KTIME
    v = np.asarray(kv.props[0], float)
    if not len(t):
        return None
    return t, v


def _animations(sc, models, mprops, nid, fps, max_s, B):
    stacks = [i for i, n in sc.obj.items() if n.name == "AnimationStack"]
    clips = []
    for st in stacks:
        layers = [c for c, _p in sc.children.get(st, []) if c in sc.obj and sc.obj[c].name == "AnimationLayer"]
        if not layers:
            continue
        chans = {}                                          # model -> {"T"|"R"|"S": {axis: (t, v)}}
        t_end = 0.0
        for cn, _p in sc.children.get(layers[0], []):
            node = sc.obj.get(cn)
            if node is None or node.name != "AnimationCurveNode":
                continue
            tgt = [(m, prop) for m, prop in sc.parent.get(cn, []) if m in mprops]
            if not tgt:
                continue
            m, prop = tgt[0]
            key = {"Lcl Translation": "T", "Lcl Rotation": "R", "Lcl Scaling": "S"}.get(prop)
            if key is None:
                continue
            axes = {}
            for cv, cprop in sc.children.get(cn, []):
                got = _curve(sc, cv)
                if got is None:
                    continue
                ax = {"d|X": 0, "d|Y": 1, "d|Z": 2}.get(cprop)
                if ax is not None:
                    axes[ax] = got
                    t_end = max(t_end, float(got[0][-1]))
            if axes:
                chans.setdefault(m, {})[key] = axes
        if not chans or t_end <= 0:
            continue
        t_end = min(t_end, max_s)
        nfr = max(2, int(round(t_end * fps)) + 1)
        times = np.arange(nfr) / fps
        tacc = B.add(times.astype(np.float32), 5126, "SCALAR", minmax=True)
        samplers, channels = [], []
        for m, ch in chans.items():
            if m not in nid:
                continue
            props = mprops[m]
            base = {k_: np.array((props.get(nm) or d)[:3], float) for k_, nm, d in
                    (("T", "Lcl Translation", (0, 0, 0)), ("R", "Lcl Rotation", (0, 0, 0)), ("S", "Lcl Scaling", (1, 1, 1)))}

            def sample(key):
                arr = np.tile(base[key], (nfr, 1))
                for ax, (kt, kv) in ch.get(key, {}).items():
                    arr[:, ax] = np.interp(times, kt, kv)
                return arr
            T, R, S = sample("T"), sample("R"), sample("S")
            Ts, Qs = np.zeros((nfr, 3)), np.zeros((nfr, 4))
            prevq = None
            for f in range(nfr):
                L = _local(props, T[f], R[f], S[f])
                Ts[f] = L[:3, 3]
                sx = np.linalg.norm(L[:3, :3], axis=0)
                q = _quat(L[:3, :3] / np.maximum(sx, 1e-9))
                if prevq is not None and np.dot(q, prevq) < 0:
                    q = -q                                   # keep the shortest way round
                Qs[f], prevq = q, q
            for path, data, typ in (("translation", Ts, "VEC3"), ("rotation", Qs, "VEC4")):
                if path == "translation" and "T" not in ch:
                    continue
                oacc = B.add(data.astype(np.float32), 5126, typ)
                samplers.append({"input": tacc, "output": oacc, "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1, "target": {"node": nid[m], "path": path}})
        if channels:
            nm = sc.name(st)
            clips.append({"name": nm.split("|")[-1] or "clip", "samplers": samplers, "channels": channels,
                          "extras": {"seconds": round(t_end, 3)}})
    return clips


def convert(src, name=None, models_dir=None):
    """FBX -> assets/models/<name>/<name>.glb. -> info dict"""
    from . import model3d
    name = model3d._clean(name or os.path.splitext(os.path.basename(src))[0])
    d = models_dir or model3d.folder(name)
    out = os.path.join(d, name + ".glb")
    info = to_glb(src, out)
    info["name"] = name
    return info
