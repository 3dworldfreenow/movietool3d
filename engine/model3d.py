"""Ready-made 3D models from other websites (GLB / glTF / OBJ / STL) -> our flat-coloured 3D faces.

Files live in assets/models/<name>/ (one model per folder, with its textures).  pen.model("<name>") draws it.

What happens to a model:
  * every mesh of the file is read in its placed position (node moves / turns / sizes are applied)
  * each triangle gets ONE colour: material colour x texture colour (sampled at the triangle) x vertex colour
  * heavy models are simplified (vertex clustering) to at most `max_faces` triangles
  * units: the file's metres -> our units (a person = 300 = 1.7 m), or any height you ask for
  * axes: glTF / OBJ look at you along +z; ours has z going AWAY from the camera, so z is flipped
    (the model's front faces the camera, nothing is mirrored)
Skinned / animated models are imported in the pose they are saved in.  Draco / meshopt compressed files
cannot be read (export again without compression).
"""
import io
import json
import os
import re
import struct
import zipfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(ROOT, "assets", "models")
UNITS_PER_M = 175.0                     # same as the world maps: a 1.7 m person is 300 tall
EXTS = (".glb", ".gltf", ".vrm", ".obj", ".stl")     # .vrm = a glTF avatar (VRoid)
MAX_FACES = 2500                        # default limit after simplifying
DETAIL = {"normal": 2500, "high": 12000, "very_high": 30000, "place": 60000, "full": 250000}
_CACHE = {}
_PIECE_OF = {}                          # model file -> piece label of every triangle (as read)
_UV_OF = {}                             # model file -> (uv (N,3,2), texture index (N,), [texture pictures])
TEX_MAX = 384                           # textures drawn on the faces are kept this big (pixels)
MAX_PIECES = 260                        # more separate pieces than this: the smallest are joined by area


class ModelError(Exception):
    pass


# ============================================================================ finding files
def _clean(name):
    return re.sub(r"[^a-z0-9_]+", "_", str(name).strip().lower()).strip("_")


def folder(name):
    return os.path.join(MODELS_DIR, _clean(name))


def find_file(name):
    """'barrel' -> assets/models/barrel/<the model file>.  'barrel/other.glb' picks a file in the folder."""
    name = str(name).strip()
    if "/" in name:
        d, f = name.split("/", 1)
        p = os.path.join(folder(d), os.path.basename(f))
        return p if os.path.isfile(p) else None
    d = folder(name)
    if not os.path.isdir(d):
        return None
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(EXTS))
    for ext in EXTS:                                     # glb first, then gltf, obj, stl
        for f in files:
            if f.lower().endswith(ext):
                return os.path.join(d, f)
    return None


def list_models():
    out = {}
    if not os.path.isdir(MODELS_DIR):
        return out
    for n in sorted(os.listdir(MODELS_DIR)):
        p = find_file(n)
        if p:
            meta = {}
            mp = os.path.join(folder(n), "meta.json")
            if os.path.isfile(mp):
                try:
                    meta = json.load(open(mp))
                except Exception:
                    meta = {}
            out[n] = dict(meta, file=os.path.basename(p))
    return out


# ============================================================================ textures
NOTES = {}                                  # model file -> [what was wrong with its colours / textures]


def find_near(base, fn):
    """A texture the model names: next to it, by its own name anywhere in the uploaded folder (any capitals),
    or with another picture extension (.png <-> .jpg). -> path or None"""
    fn = str(fn).replace("\\", "/").strip().strip('"')
    from urllib.parse import unquote
    fn = unquote(fn)
    for cand in (os.path.join(base, fn), os.path.join(base, os.path.basename(fn))):
        if os.path.isfile(cand):
            return cand
    want = os.path.basename(fn).lower()
    stem = os.path.splitext(want)[0]
    alt = None
    for dirpath, _d, fnames in os.walk(base):
        for f in fnames:
            fl = f.lower()
            if fl == want:
                return os.path.join(dirpath, f)
            if os.path.splitext(fl)[0] == stem and fl.endswith((".png", ".jpg", ".jpeg", ".webp", ".tga", ".bmp")):
                alt = alt or os.path.join(dirpath, f)
    return alt


def _open_image(data):
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None
    if max(im.size) > 512:                               # colours only - a small copy is plenty
        im.thumbnail((512, 512))
    return np.asarray(im, dtype=np.float32) / 255.0


class _Tex(np.ndarray):
    """a texture picture that also carries its KHR_texture_transform (offset, rotation, scale)"""
    xf = None


def _sample(tex, uv, flip_v):
    """tex HxWx4, uv (N,k,2) -> middle colour (N,4) of the k samples"""
    xf = getattr(tex, "xf", None)
    if xf is not None:                                   # the picture is a part of an atlas: move the uv onto it
        (ox, oy), r, (sx, sy) = xf
        c, s_ = np.cos(r), np.sin(r)
        u0, v0 = uv[..., 0] * sx, uv[..., 1] * sy
        uv = np.stack([c * u0 + s_ * v0 + ox, -s_ * u0 + c * v0 + oy], axis=-1)
    tex = np.asarray(tex)
    H, W = tex.shape[:2]
    u = np.mod(uv[..., 0], 1.0)
    v = np.mod(uv[..., 1], 1.0)
    if flip_v:
        v = 1.0 - v
    x = np.clip((u * W).astype(np.int64), 0, W - 1)
    y = np.clip((v * H).astype(np.int64), 0, H - 1)
    # the middle value of the samples, not the average: a triangle across two colours keeps one of them
    # (averaging red and green gave muddy brown - the colours looked lost)
    return np.median(tex[y, x], axis=1)


def _tri_uv_samples(uv3):
    """uv of the 3 corners (N,3,2) -> 5 sample points: the middle (twice: it wins ties) and 3 points halfway to
    the corners"""
    c = uv3.mean(axis=1, keepdims=True)
    return np.concatenate([c, c, (uv3 + c) * 0.5], axis=1)


# ============================================================================ glTF / GLB
_CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_NORM = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}


def _gltf_open(path):
    """-> namespace(G, accessor(i), material(i), texture(i), node_matrix(node))"""
    base = os.path.dirname(path)
    raw = open(path, "rb").read()
    bin_chunk = None
    if raw[:4] == b"glTF":
        _, _, total = struct.unpack_from("<III", raw, 0)
        off, js = 12, None
        while off < min(total, len(raw)):
            ln, typ = struct.unpack_from("<II", raw, off)
            chunk = raw[off + 8: off + 8 + ln]
            if typ == 0x4E4F534A:
                js = json.loads(chunk.decode("utf-8"))
            elif typ == 0x004E4942:
                bin_chunk = chunk
            off += 8 + ln
        if js is None:
            raise ModelError("broken GLB file (no JSON part)")
        G = js
    else:
        try:
            G = json.loads(raw.decode("utf-8"))
        except Exception:
            raise ModelError("not a glTF file")
    need = set(G.get("extensionsRequired") or [])
    if "EXT_meshopt_compression" in need or ("KHR_draco_mesh_compression" in need and not _draco_ok()):
        raise ModelError("this file is compressed (Draco / meshopt) - export it again without compression "
                         "(Blender: File > Export > glTF, untick 'Compression')" +
                         (" or install the Draco reader: pip install DracoPy" if "KHR_draco_mesh_compression" in need
                          else ""))

    def load_uri(uri):
        if uri.startswith("data:"):
            import base64
            return base64.b64decode(uri.split(",", 1)[1])
        from urllib.parse import unquote
        p = os.path.join(base, unquote(uri))
        if not os.path.isfile(p):
            p = find_near(base, uri) or p
        if not os.path.isfile(p):
            raise ModelError(f"missing file next to the model: {uri} (upload the whole folder / zip)")
        return open(p, "rb").read()

    buffers = []
    for i, b in enumerate(G.get("buffers") or []):
        if "uri" in b:
            buffers.append(load_uri(b["uri"]))
        else:
            buffers.append(bin_chunk or b"")

    def view_bytes(vi):
        bv = G["bufferViews"][vi]
        buf = buffers[bv["buffer"]]
        o = bv.get("byteOffset", 0)
        return buf[o: o + bv["byteLength"]], bv.get("byteStride")

    acc_cache = {}

    def accessor(ai):
        if ai in acc_cache:
            return acc_cache[ai]
        a = G["accessors"][ai]
        dt = np.dtype(_CT[a["componentType"]])
        nc = _NC[a["type"]]
        cnt = a["count"]
        if "bufferView" in a:
            data, stride = view_bytes(a["bufferView"])
            o = a.get("byteOffset", 0)
            item = dt.itemsize * nc
            if stride and stride != item:
                rows = np.frombuffer(data, np.uint8, count=stride * (cnt - 1) + item, offset=o)
                rows = np.lib.stride_tricks.as_strided(rows, (cnt, item), (stride, 1))
                arr = np.ascontiguousarray(rows).view(dt).reshape(cnt, nc)
            else:
                arr = np.frombuffer(data, dt, count=cnt * nc, offset=o).reshape(cnt, nc)
        else:
            arr = np.zeros((cnt, nc), dt)
        arr = arr.astype(np.float64) if dt != np.uint32 else arr.astype(np.int64)
        if a.get("normalized") and a["componentType"] in _NORM:
            arr = np.maximum(arr / _NORM[a["componentType"]], -1.0)
        sp = a.get("sparse")
        if sp:
            idx = accessor_like(sp["indices"], sp["count"], 1).reshape(-1).astype(np.int64)
            val = accessor_like(sp["values"], sp["count"], nc, a["componentType"])
            arr = arr.copy()
            arr[idx] = val
        acc_cache[ai] = arr
        return arr

    def accessor_like(spec, cnt, nc, ctype=None):
        dt = np.dtype(_CT[ctype if ctype is not None else spec["componentType"]])
        data, _ = view_bytes(spec["bufferView"])
        return np.frombuffer(data, dt, count=cnt * nc, offset=spec.get("byteOffset", 0)).reshape(cnt, nc).astype(np.float64)

    # --- textures -> numpy images (only when used)
    tex_cache = {}
    problems = []

    def texture(ti):
        if ti in tex_cache:
            return tex_cache[ti]
        img = None
        what = f"texture {ti}"
        try:
            t = G["textures"][ti]
            src = t.get("source")
            exts = t.get("extensions") or {}
            if src is None:
                for ext in exts.values():
                    src = ext.get("source", src)
            im = G["images"][src]
            what = im.get("name") or im.get("uri") or what
            if "KHR_texture_basisu" in exts or str(im.get("mimeType", "")).endswith("ktx2") or \
                    str(im.get("uri", "")).lower().endswith(".ktx2"):
                problems.append(f"the texture '{what}' is KTX2 (compressed for games) - colours are lost; "
                                "export the model with PNG / JPEG textures")
                tex_cache[ti] = None
                return None
            if "bufferView" in im:
                data, _ = view_bytes(im["bufferView"])
            else:
                data = load_uri(im["uri"])
            img = _open_image(bytes(data))
            if img is None:
                problems.append(f"the texture '{what}' could not be opened (unknown picture type)")
        except ModelError as ex:
            problems.append(str(ex))
            img = None
        except (KeyError, IndexError, TypeError):
            img = None
        tex_cache[ti] = img
        return img

    def material(mi):
        if mi is None:
            return (np.array([0.8, 0.8, 0.8, 1.0]), None, 0, "default")
        m = (G.get("materials") or [])[mi]
        pbr = m.get("pbrMetallicRoughness") or {}
        f = np.array(pbr.get("baseColorFactor", [1, 1, 1, 1]), np.float64)
        bt = pbr.get("baseColorTexture")
        if bt is None:                                   # old "specular-glossiness" files
            sg = (m.get("extensions") or {}).get("KHR_materials_pbrSpecularGlossiness") or {}
            if sg:
                f = np.array(sg.get("diffuseFactor", [1, 1, 1, 1]), np.float64)
                bt = sg.get("diffuseTexture")
        tex = texture(bt["index"]) if bt else None
        tt = ((bt or {}).get("extensions") or {}).get("KHR_texture_transform")
        if tex is not None and tt:
            tex = tex.view(_Tex)
            tex.xf = (tuple(tt.get("offset", [0, 0])), float(tt.get("rotation", 0)), tuple(tt.get("scale", [1, 1])))
            if "texCoord" in tt:
                bt = dict(bt, texCoord=tt["texCoord"])
        return (f, tex, (bt or {}).get("texCoord", 0), m.get("name") or f"material_{mi}")

    # --- node transforms
    def node_matrix(n):
        if "matrix" in n:
            return np.array(n["matrix"], np.float64).reshape(4, 4).T
        T = np.eye(4)
        t = n.get("translation", [0, 0, 0])
        q = n.get("rotation", [0, 0, 0, 1])
        s = n.get("scale", [1, 1, 1])
        x, y, z, w = q
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        T[:3, :3] = R * np.array(s)[None, :]
        T[:3, 3] = t
        return T

    from types import SimpleNamespace
    for n_ in ((G.get("asset") or {}).get("extras") or {}).get("notes") or []:
        problems.append(str(n_))                        # (what the FBX converter noticed)
    NOTES[os.path.abspath(path)] = problems
    return SimpleNamespace(G=G, accessor=accessor, material=material, texture=texture, node_matrix=node_matrix,
                           problems=problems)


_CUT = re.compile(r"_(?:sub|mdl|material|mat|lod|LOD|dmg|geo|mesh|primitive)(?:_|\d|$)")


def piece_name(name, i=0):
    """a node name -> the piece it belongs to: "unit_039_sub_018_4944" -> "unit_039",
    "prop_069_mdl_002_dmg_000_lod_000_215" -> "prop_069", "Tree.003" -> "Tree" ... """
    s = str(name or f"part_{i}")
    m = _CUT.search(s)
    if m and m.start() > 0:
        s = s[:m.start()]
    s = re.sub(r"\.\d+$", "", s)                         # Blender copies: "House.001"
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_").lower()
    return s or f"part_{i}"


def _read_gltf(path):
    gf = _gltf_open(path)
    if gf.G.get("skins"):                                   # a model with bones: its rest pose
        from .rigmodel import rest_tris_gltf
        return rest_tris_gltf(path)
    G, accessor, material, node_matrix = gf.G, gf.accessor, gf.material, gf.node_matrix
    tris, cols, names, pieces = [], [], [], []
    uvs, tids, texlist, texid = [], [], [], {}

    def tex_index(tex):
        """the texture as a small uint8 picture (drawn on the faces later), its number in the list"""
        k = id(tex)
        if k not in texid:
            a = np.asarray(tex)
            h, w = a.shape[:2]
            if max(h, w) > TEX_MAX:
                st = int(np.ceil(max(h, w) / TEX_MAX))
                a = a[::st, ::st]
            texid[k] = len(texlist)
            texlist.append((np.clip(a, 0, 1) * 255).astype(np.uint8))
        return texid[k]
    nodes = G.get("nodes") or []
    scenes = G.get("scenes") or []
    if scenes:
        roots = scenes[G.get("scene", 0)].get("nodes", [])
    else:
        child = {c for n in nodes for c in n.get("children", [])}
        roots = [i for i in range(len(nodes)) if i not in child]

    def prim_tris(p, M, piece="model"):
        mode = p.get("mode", 4)
        at = p.get("attributes") or {}
        if "POSITION" not in at or mode not in (4, 5, 6):
            return
        P = accessor(at["POSITION"])[:, :3]
        n = len(P)
        idx = accessor(p["indices"]).reshape(-1).astype(np.int64) if "indices" in p else np.arange(n)
        if mode == 5:                                    # strip
            k = np.arange(len(idx) - 2)
            a, b, c = idx[k], idx[k + 1], idx[k + 2]
            odd = (k % 2) == 1
            a, b = np.where(odd, b, a), np.where(odd, a, b)
            idx = np.stack([a, b, c], 1).reshape(-1)
        elif mode == 6:                                  # fan
            k = np.arange(1, len(idx) - 1)
            idx = np.stack([np.full_like(k, idx[0]), idx[k], idx[k + 1]], 1).reshape(-1)
        idx = idx[: len(idx) // 3 * 3].reshape(-1, 3)
        idx = idx[(idx < n).all(axis=1)]
        if not len(idx):
            return
        Pw = P @ M[:3, :3].T + M[:3, 3]
        T = Pw[idx]
        if np.linalg.det(M[:3, :3]) < 0:                 # mirrored node: keep the front side out
            T = T[:, ::-1]
        f, tex, tc, mname = material(p.get("material"))
        C = np.tile(f, (len(idx), 1))
        uvk = f"TEXCOORD_{tc}"
        if tex is not None and uvk in at:
            UV = accessor(at[uvk])[:, :2]
            C = C * _sample(tex, _tri_uv_samples(UV[idx]), flip_v=False)
            if getattr(tex, "xf", None) is None:          # the picture itself is drawn on big faces
                uvs.append(UV[idx].astype(np.float32))
                tids.append(np.full(len(idx), tex_index(tex), np.int32))
            else:
                uvs.append(np.zeros((len(idx), 3, 2), np.float32))
                tids.append(np.full(len(idx), -1, np.int32))
        else:
            uvs.append(np.zeros((len(idx), 3, 2), np.float32))
            tids.append(np.full(len(idx), -1, np.int32))
        if "COLOR_0" in at:
            VC = accessor(at["COLOR_0"])
            if VC.shape[1] == 3:
                VC = np.concatenate([VC, np.ones((len(VC), 1))], 1)
            C = C * VC[idx].mean(axis=1)
        tris.append(T)
        cols.append(C)
        names.extend([mname] * len(T))
        pieces.extend([piece] * len(T))

    def walk(i, M, depth=0, piece=None):
        """piece: the part of the model this node belongs to - the children of the first node that
        branches out (a city: each building, each prop) start their own piece"""
        if depth > 64 or i >= len(nodes):
            return
        n = nodes[i]
        M2 = M @ node_matrix(n)
        kids = n.get("children", [])
        here = piece if piece is not None else (piece_name(n.get("name"), i) if "mesh" in n else None)
        if "mesh" in n:
            for p in G["meshes"][n["mesh"]].get("primitives", []):
                prim_tris(p, M2, here or "model")
        branch = here is None and len(kids) > 1
        for c in kids:
            walk(c, M2, depth + 1, piece_name(nodes[c].get("name"), c) if branch else here)

    for r in roots:
        walk(r, np.eye(4), 0, piece_name(nodes[r].get("name"), r) if len(roots) > 1 and r < len(nodes) else None)
    if not tris and G.get("meshes"):                     # no scene graph: take the meshes as they are
        for m in G["meshes"]:
            for p in m.get("primitives", []):
                prim_tris(p, np.eye(4))
    if not tris:
        raise ModelError("no triangles found in this file")
    _PIECE_OF[os.path.abspath(path)] = pieces
    if uvs and sum(len(u) for u in uvs) == sum(len(t) for t in tris):
        _UV_OF[os.path.abspath(path)] = (np.concatenate(uvs), np.concatenate(tids), texlist)
    return np.concatenate(tris), np.concatenate(cols), names


# ============================================================================ OBJ (+ MTL + textures)
def _read_mtl(path):
    mats, cur = {}, None
    base = os.path.dirname(path)
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return mats
    for ln in lines:
        p = ln.strip().split()
        if not p or p[0].startswith("#"):
            continue
        k = p[0]
        if k == "newmtl":
            cur = " ".join(p[1:])
            mats[cur] = {"Kd": [0.8, 0.8, 0.8], "d": 1.0, "tex": None}
        elif cur is None:
            continue
        elif k == "Kd" and len(p) >= 4:
            mats[cur]["Kd"] = [float(v) for v in p[1:4]]
        elif k == "d" and len(p) >= 2:
            mats[cur]["d"] = float(p[1])
        elif k == "Tr" and len(p) >= 2:
            mats[cur]["d"] = 1.0 - float(p[1])
        elif k == "map_Kd" and len(p) >= 2:
            fn = p[-1].replace("\\", "/")
            cand = find_near(base, fn)
            if cand:
                try:
                    mats[cur]["tex"] = _open_image(open(cand, "rb").read())
                except Exception:
                    pass
            if mats[cur]["tex"] is None:
                NOTES.setdefault(os.path.abspath(path), []).append(
                    f"the texture '{os.path.basename(fn)}' was not uploaded - upload the model and its pictures "
                    "together (a .zip) to keep the colours")
    return mats


def _read_obj(path):
    base = os.path.dirname(path)
    V, VT, VC = [], [], []
    faces = []                                            # (v idx list, vt idx list, material)
    mats, cur = {}, None
    for ln in open(path, encoding="utf-8", errors="replace"):
        if not ln or ln[0] == "#":
            continue
        p = ln.split()
        if not p:
            continue
        k = p[0]
        if k == "v" and len(p) >= 4:
            V.append([float(p[1]), float(p[2]), float(p[3])])
            VC.append([float(x) for x in p[4:7]] if len(p) >= 7 else None)
        elif k == "vt" and len(p) >= 3:
            VT.append([float(p[1]), float(p[2])])
        elif k == "f" and len(p) >= 4:
            vi, ti = [], []
            for tok in p[1:]:
                parts = tok.split("/")
                a = int(parts[0])
                vi.append(a - 1 if a > 0 else len(V) + a)
                if len(parts) > 1 and parts[1]:
                    b = int(parts[1])
                    ti.append(b - 1 if b > 0 else len(VT) + b)
            faces.append((vi, ti if len(ti) == len(vi) else None, cur))
        elif k == "usemtl":
            cur = " ".join(p[1:])
        elif k == "mtllib":
            mp = os.path.join(base, " ".join(p[1:]))
            if not os.path.isfile(mp):
                mp = find_near(base, " ".join(p[1:])) or mp
            if not os.path.isfile(mp):
                NOTES.setdefault(os.path.abspath(path), []).append(
                    f"the colours file '{' '.join(p[1:])}' (.mtl) was not uploaded - upload the .obj with its .mtl "
                    "and pictures (a .zip) to keep the colours")
            else:
                mats.update(_read_mtl(mp))
                for n_ in NOTES.get(os.path.abspath(mp), []):
                    NOTES.setdefault(os.path.abspath(path), []).append(n_)
    if not faces:
        raise ModelError("no faces found in this OBJ file")
    V = np.array(V, np.float64)
    VTa = np.array(VT, np.float64) if VT else None
    has_vc = any(c is not None for c in VC)
    VCa = np.array([c if c is not None else [1, 1, 1] for c in VC], np.float64) if has_vc else None
    tris, cols, names = [], [], []
    for vi, ti, m in faces:
        md = mats.get(m) or {"Kd": [0.8, 0.8, 0.8], "d": 1.0, "tex": None}
        base_c = np.array(md["Kd"] + [md["d"]], np.float64)
        for j in range(1, len(vi) - 1):                   # fan the polygon into triangles
            k3 = [vi[0], vi[j], vi[j + 1]]
            if max(k3) >= len(V) or min(k3) < 0:
                continue
            c = base_c.copy()
            if md["tex"] is not None and ti is not None and VTa is not None:
                t3 = [ti[0], ti[j], ti[j + 1]]
                if max(t3) < len(VTa):
                    c = c * _sample(md["tex"], _tri_uv_samples(VTa[t3][None]), flip_v=True)[0]
            if VCa is not None:
                c[:3] = c[:3] * VCa[k3].mean(axis=0)
            tris.append(V[k3])
            cols.append(c)
            names.append(m or "default")
    return np.array(tris), np.array(cols), names


# ============================================================================ STL
def _read_stl(path):
    raw = open(path, "rb").read()
    if len(raw) >= 84:
        n = struct.unpack_from("<I", raw, 80)[0]
        if 84 + n * 50 == len(raw):
            rec = np.frombuffer(raw, np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
            T = rec["v"].astype(np.float64)
            return T, np.tile([0.75, 0.75, 0.75, 1.0], (len(T), 1)), ["default"] * len(T)
    txt = raw.decode("utf-8", errors="replace")
    vs = [list(map(float, m)) for m in re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", txt)]
    if len(vs) < 3:
        raise ModelError("no triangles found in this STL file")
    T = np.array(vs[: len(vs) // 3 * 3], np.float64).reshape(-1, 3, 3)
    return T, np.tile([0.75, 0.75, 0.75, 1.0], (len(T), 1)), ["default"] * len(T)


# ============================================================================ simplify
def simplify(T, C, max_faces):
    """Vertex clustering: snap corners to a grid, drop squashed triangles, merge copies.
    The grid gets finer until the count fits (the biggest grid that still fits keeps the most detail)."""
    if len(T) <= max_faces:
        return T, C
    lo = T.reshape(-1, 3).min(0)
    size = float((T.reshape(-1, 3).max(0) - lo).max()) or 1.0

    def cluster(n):
        cell = size / n
        V = T.reshape(-1, 3)
        q = np.floor((V - lo) / cell).astype(np.int64)
        key = (q[:, 0] * n + q[:, 1]) * n + q[:, 2]
        uk, inv = np.unique(key, return_inverse=True)
        sums = np.zeros((len(uk), 3))
        np.add.at(sums, inv, V)
        cnt = np.bincount(inv, minlength=len(uk))[:, None]
        rep = sums / cnt
        tri = inv.reshape(-1, 3)
        ok = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
        tri, cc = tri[ok], C[ok]
        srt = np.sort(tri, axis=1)                         # the same triangle twice -> keep one
        _, first = np.unique(srt, axis=0, return_index=True)
        first.sort()
        return rep[tri[first]], cc[first]

    best = None
    a, b = 4, 512
    while a <= b:                                          # largest grid whose result still fits
        m = (a + b) // 2
        R = cluster(m)
        if len(R[0]) <= max_faces:
            best, a = R, m + 1
        else:
            b = m - 1
    if best is None:
        best = cluster(4)
    return best


# ============================================================================ the public part
def _join_small(labels, T, keep=MAX_PIECES):
    """Too many pieces (a city with 1,300 props): the biggest stay on their own, the small ones are joined
    with their neighbours (by area on the ground) -> new label array"""
    labels = np.asarray(labels, dtype=object)
    uniq, inv, cnt = np.unique(labels, return_inverse=True, return_counts=True)
    if len(uniq) <= keep:
        return labels
    order = np.argsort(-cnt)
    big = set(order[:keep - 64].tolist())
    cen = T.mean(axis=1)
    lo, hi = cen.min(0), cen.max(0)
    span = np.maximum(hi - lo, 1e-6)
    cell = np.clip(((cen[:, [0, 2]] - lo[[0, 2]]) / span[[0, 2]] * 8).astype(np.int64), 0, 7)
    out = labels.copy()
    small = ~np.isin(inv, list(big))
    out[small] = np.array([f"small_things_{a}_{b}" for a, b in cell[small]], dtype=object)
    return out


def _budgets(counts, total):
    """triangles each piece may keep: every piece keeps its shape (at least 24 or all it has), the rest of
    the budget is shared by size"""
    counts = np.asarray(counts, np.float64)
    base = np.minimum(counts, 24.0)
    rest = max(0.0, total - base.sum())
    extra = counts - base
    if extra.sum() > 0:
        base = base + np.minimum(extra, extra / extra.sum() * rest)
    return np.maximum(1, base.astype(np.int64))


def load(name, max_faces=MAX_FACES, up=None, part=None):
    """-> dict(tris (N,3,3) in METRES with our axes, cols (N,4) 0..1, names [material per tri],
    pieces [piece per tri], lo, hi (bounds), faces_in (before simplifying), file)
    Big models are simplified PIECE BY PIECE (each building / prop keeps its own shape - a city simplified
    as one lump became a blur). part = only that piece (its own full budget)."""
    path = find_file(name) if not os.path.isfile(str(name)) else str(name)
    if not path:
        raise ModelError(f"no model called '{name}' (put it in assets/models/{_clean(name)}/)")
    key = (path, os.path.getmtime(path), int(max_faces), up, part)
    if key in _CACHE:
        return _CACHE[key]
    disk = os.path.join(os.path.dirname(path), f".cache_{int(max_faces)}_{up or 'y'}_{part or 'all'}.npz")
    try:                                                   # a big model: simplified once, kept on disk
        if os.path.isfile(disk) and os.path.getmtime(disk) >= os.path.getmtime(path):
            z = np.load(disk, allow_pickle=True)
            out = dict(tris=z["tris"], cols=z["cols"], names=list(z["names"]), pieces=list(z["pieces"]),
                       uv=z["uv"] if "uv" in z else None, tid=z["tid"] if "tid" in z else None,
                       texs=list(z["texs"]) if "texs" in z else [],
                       lo=z["lo"], hi=z["hi"], faces_in=int(z["faces_in"]), file=path,
                       lo_all=z["lo_all"] if "lo_all" in z else z["lo"], hi_all=z["hi_all"] if "hi_all" in z else z["hi"])
            _CACHE[key] = out
            return out
    except Exception:                                      # noqa: BLE001 - a broken cache is just made again
        pass
    ext = os.path.splitext(path)[1].lower()
    NOTES.pop(os.path.abspath(path), None)
    if ext in (".glb", ".gltf", ".vrm"):
        T, C, names = _read_gltf(path)
    elif ext == ".obj":
        T, C, names = _read_obj(path)
    elif ext == ".stl":
        T, C, names = _read_stl(path)
    else:
        raise ModelError("unknown model type " + ext + " (use .glb .gltf .obj .stl)")
    T = np.asarray(T, np.float64)
    C = np.clip(np.asarray(C, np.float64), 0.0, 1.0)
    plab = _PIECE_OF.pop(os.path.abspath(path), None)
    if plab is None or len(plab) != len(T):
        plab = ["model"] * len(T)
    UVT = _UV_OF.pop(os.path.abspath(path), None)
    if UVT is None or len(UVT[0]) != len(T):
        UV, TID, TEXS = np.zeros((len(T), 3, 2), np.float32), np.full(len(T), -1, np.int32), []
    else:
        UV, TID, TEXS = UVT
    good = np.isfinite(T).all(axis=(1, 2))
    T, C = T[good], C[good]
    UV, TID = UV[good], TID[good]
    names = [n for n, g in zip(names, good) if g]
    plab = [p for p, g in zip(plab, good) if g]
    n_in = len(T)
    vol = np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum()
    ref = np.abs(np.einsum("ij,ij->i", T[:, 0] - T[:, 0].mean(0), np.cross(T[:, 1] - T[:, 0].mean(0), T[:, 2] - T[:, 0].mean(0)))).sum()
    if ref > 0 and vol < -0.2 * ref:                        # inside out (faces wound the wrong way): turn it over
        T = T[:, ::-1]
    flips = 0
    if ref > 0 and vol < -0.2 * ref:
        flips += 1
    if (up or ("z" if ext == ".stl" else "y")) == "z":
        T = T[:, :, [0, 2, 1]] * np.array([1, 1, -1])      # Z-up (STL / CAD) -> Y-up, not mirrored
    T = T * np.array([1.0, 1.0, -1.0])                     # our z goes away from the camera
    T = T[:, ::-1]                                          # (that flip turns the winding over - turn it back)
    flips += 1
    if flips % 2:                                          # the corners' uv follow the corners
        UV = UV[:, ::-1]
    name_arr = np.array(names, dtype=object)
    plab = _join_small(plab, T)
    lo_all, hi_all = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    if part is not None:                                   # one piece of it
        sel = plab == part
        if not sel.any():
            raise ModelError(f"'{name}' has no piece called '{part}'")
        T, C, name_arr, plab = T[sel], C[sel], name_arr[sel], plab[sel]
        UV, TID = UV[sel], TID[sel]
        n_in = len(T)
    idx = np.arange(len(T))
    if len(T) > max_faces:
        uniq, inv, cnt = np.unique(plab, return_inverse=True, return_counts=True)
        if len(uniq) == 1:
            T2, C2 = simplify(T, np.concatenate([C, idx[:, None].astype(np.float64)], 1), max_faces)
            keep_i = C2[:, 4].astype(np.int64)
            T, C = T2, C2[:, :4]
        else:                                              # piece by piece, each with its share
            bud = _budgets(cnt, max_faces)
            Ts, Cs, Ks = [], [], []
            for k in range(len(uniq)):
                sel = inv == k
                Tk, Ck, ik = T[sel], C[sel], idx[sel]
                if len(Tk) > bud[k]:
                    T2, C2 = simplify(Tk, np.concatenate([Ck, ik[:, None].astype(np.float64)], 1), int(bud[k]))
                    Tk, Ck, ik = T2, C2[:, :4], C2[:, 4].astype(np.int64)
                Ts.append(Tk)
                Cs.append(Ck)
                Ks.append(ik)
            T, C, keep_i = np.concatenate(Ts), np.concatenate(Cs), np.concatenate(Ks)
        names, pieces = list(name_arr[keep_i]), list(plab[keep_i])
        UV, TID = UV[keep_i], TID[keep_i]
    else:
        names, pieces = list(name_arr), list(plab)
    V = T.reshape(-1, 3)
    out = dict(tris=T, cols=C, names=names, pieces=pieces, lo=V.min(0), hi=V.max(0), faces_in=n_in, file=path,
               lo_all=lo_all, hi_all=hi_all, uv=UV, tid=TID, texs=TEXS)
    if n_in > 20000:                                       # worth keeping on disk
        try:
            np.savez_compressed(disk, tris=T.astype(np.float32), cols=C.astype(np.float32),
                                names=np.array(names, dtype=object), pieces=np.array(pieces, dtype=object),
                                lo=out["lo"], hi=out["hi"], faces_in=n_in, lo_all=lo_all, hi_all=hi_all,
                                uv=UV.astype(np.float32), tid=TID, texs=_objarr(TEXS))
        except Exception:                                  # noqa: BLE001
            pass
    if len(_CACHE) > 40:
        _CACHE.clear()
    _CACHE[key] = out
    return out


def _objarr(items):
    arr = np.empty(len(items), dtype=object)
    for i, it in enumerate(items):
        arr[i] = it
    return arr


def pieces(name, max_faces=None):
    """The pieces of a model (a city: buildings, props, ground ...):
    [{"name", "faces_in", "lo", "hi"}] - bounds in metres, our axes"""
    m = load(name, int(max_faces or DETAIL["full"]))
    P = np.asarray(m["pieces"], dtype=object)
    out = []
    for p in sorted(set(m["pieces"])):
        sel = P == p
        V = m["tris"][sel].reshape(-1, 3)
        out.append({"name": p, "faces": int(sel.sum()), "lo": V.min(0).round(3).tolist(),
                    "hi": V.max(0).round(3).tolist()})
    return out


def hexc(c):
    return "#%02x%02x%02x" % tuple(int(round(max(0, min(1, v)) * 255)) for v in c[:3])


def _groups(cols, names, dist=0.16):
    """close colours -> one group each: [(hex of the biggest, count, material, [indices])] biggest first"""
    q = np.round(cols[:, :3] * 255).astype(np.int64)
    key = (q[:, 0] << 16) | (q[:, 1] << 8) | q[:, 2]
    uk, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    order = np.argsort(-cnt)
    ucol = np.stack([(uk >> 16) & 255, (uk >> 8) & 255, uk & 255], 1) / 255.0
    centers, members = [], []
    gid = np.empty(len(uk), np.int64)
    for u in order:
        c = ucol[u]
        if centers:
            d = np.linalg.norm(np.array(centers) - c, axis=1)
            j = int(d.argmin())
            if d[j] < dist:
                gid[u] = j
                continue
        gid[u] = len(centers)
        centers.append(c)
    fg = gid[inv]
    out = []
    for j, c in enumerate(centers):
        idx = np.nonzero(fg == j)[0]
        out.append((hexc(c), len(idx), names[idx[0]] if len(names) else "", idx))
    return sorted(out, key=lambda x: -x[1])


def palette(name, top=10, max_faces=MAX_FACES):
    """The main colours of a model (close shades together): [(hex, faces, material name)] biggest first"""
    m = load(name, max_faces)
    return [(h, n, mat) for h, n, mat, _ in _groups(m["cols"], m["names"])[:top]]


ALL_KEYS = ("*", "all", "any", "everything")


def recolor_index(cols, keys, dist=0.16, wide=0.6):
    """for pen.model(colors=...): the key each face belongs to (nearest key colour within dist) or -1.
    "*" (or "all") = every face no other key took - a whole-model tint (light and dark shades kept).
    A key that matches NO face (a guessed colour - e.g. an AI wrote "#eeeeee" for a grey model) takes the faces
    still left within a wider distance, so "make it red" works even when the guess is a bit off."""
    from .codedraw import color as _color
    star = [i for i, k in enumerate(keys) if str(k).strip().lower() in ALL_KEYS]
    K = np.array([(0.5, 0.5, 0.5) if i in star else _color(k)[:3] for i, k in enumerate(keys)], np.float64)
    cols = np.asarray(cols)
    real = [i for i in range(len(keys)) if i not in star]
    j = -np.ones(len(cols), np.int64)
    if real:
        R = K[real]
        d = np.linalg.norm(cols[:, None, :3] - R[None, :, :], axis=2)
        jj = d.argmin(axis=1)
        dd = d[np.arange(len(cols)), jj]
        ok = dd < dist
        j[ok] = np.array(real)[jj[ok]]
        lost = [r for n, r in enumerate(real) if not np.any(ok & (jj == n))]
        if lost:                                          # guessed colours: match the faces left, more loosely
            L = K[lost]
            free = j < 0
            d2 = np.linalg.norm(cols[free][:, None, :3] - L[None, :, :], axis=2)
            j2 = d2.argmin(axis=1)
            near = d2[np.arange(len(j2)), j2] < wide
            idx = np.nonzero(free)[0]
            j[idx[near]] = np.array(lost)[j2[near]]
    if star:
        sel = j < 0
        j[sel] = star[0]
        # a tint keeps the model's own light / dark: compare with the faces' own average brightness
        if sel.any():
            K[star[0]] = cols[sel, :3].mean(axis=0)
    return j, K


def info(name, max_faces=MAX_FACES):
    m = load(name, max_faces)
    size = m["hi"] - m["lo"]
    return {"faces_in": int(m["faces_in"]), "faces": int(len(m["tris"])), "size_m": [round(float(v), 3) for v in size],
            "file": os.path.basename(m["file"]), "notes": colour_notes(m["file"], m["cols"])}


def colour_notes(path, cols=None):
    """Why a model may look grey / white: missing or unreadable textures, no colours in the file."""
    out = list(dict.fromkeys(NOTES.get(os.path.abspath(path), [])))
    if cols is not None and len(cols):
        c = np.asarray(cols)[:, :3]
        if float(c.std(axis=0).max()) < 0.02 and not out:
            out.append("the model has only one colour (the file has no textures or colours) - change it with "
                       "colors={...} in its code, or upload the version with textures")
    return out


def _draco_ok():
    try:
        import DracoPy  # noqa: F401
        return True
    except Exception:
        return False


# ============================================================================ importing uploads
def import_files(name, files, credit="", license_="", source=""):
    """files: [(filename, bytes)] - one model file (+ .bin / .mtl / textures), or one .zip with all of them.
    -> the folder name.  Replaces a model of the same name."""
    import shutil
    nm = _clean(name)
    if not nm:
        raise ModelError("give the model a name")
    flat = []
    for fn, data in files:
        if fn.lower().endswith(".zip"):
            try:
                z = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile:
                raise ModelError("broken zip file")
            total = 0
            for zi in z.infolist():
                if zi.is_dir() or "__MACOSX" in zi.filename:
                    continue
                total += zi.file_size
                if total > 200 * 1024 * 1024:
                    raise ModelError("zip is too big (over 200 MB unpacked)")
                flat.append((zi.filename, z.read(zi)))
        else:
            flat.append((fn, data))
    if not any(fn.lower().endswith(EXTS + (".fbx",)) for fn, _ in flat):
        raise ModelError("no model file found - upload a .glb, .gltf, .vrm, .fbx, .obj or .stl (or a .zip with one)")
    d = folder(nm)
    tmp = d + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    for fn, data in flat:
        rel = os.path.normpath(fn.replace("\\", "/")).lstrip("/")
        if rel.startswith(".."):
            continue
        p = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
    # FBX (Mixamo ...): turned into a .glb here once (engine/fbx.py) - skin, bones, texture and its move
    for dirpath, _, fnames in os.walk(tmp):
        for f in fnames:
            if f.lower().endswith(".fbx"):
                src = os.path.join(dirpath, f)
                try:
                    from . import fbx
                    fbx.to_glb(src, os.path.splitext(src)[0] + ".glb")
                except Exception as ex:
                    shutil.rmtree(tmp, ignore_errors=True)
                    raise ModelError(f"could not read the FBX file: {ex}")
                os.remove(src)                           # (the .glb has everything; saves space)
    # a model inside a sub folder of the zip: move that folder up
    top = [f for f in os.listdir(tmp) if f.lower().endswith(EXTS)]
    if not top:
        for dirpath, _, fnames in os.walk(tmp):
            if any(f.lower().endswith(EXTS) for f in fnames):
                for f in os.listdir(dirpath):
                    shutil.move(os.path.join(dirpath, f), os.path.join(tmp, "_" + f if os.path.exists(os.path.join(tmp, f)) else f))
                break
    # OBJ textures are often somewhere else in the zip: put every picture next to the model as well
    for dirpath, _, fnames in os.walk(tmp):
        if os.path.abspath(dirpath) == os.path.abspath(tmp):
            continue
        for f in fnames:
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".mtl", ".bin")) and not os.path.exists(os.path.join(tmp, f)):
                shutil.copy(os.path.join(dirpath, f), os.path.join(tmp, f))
    meta = {"credit": credit, "license": license_, "source": source}
    with open(os.path.join(tmp, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    shutil.rmtree(d, ignore_errors=True)
    os.rename(tmp, d)
    try:
        load(nm)
    except ModelError:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as ex:
        shutil.rmtree(d, ignore_errors=True)
        raise ModelError(f"could not read this model: {ex}")
    return nm


def delete(name):
    import shutil
    d = folder(name)
    if os.path.isdir(d):
        shutil.rmtree(d)


def make_code(name, kind="object3d", height=None, description="", abilities=None):
    """An editable 3D code file that draws the imported model (colours listed so you can change them)."""
    nm = _clean(name)
    i = info(nm)
    meta = list_models().get(nm, {})
    real_h = i["size_m"][1] * UNITS_PER_M
    if not height:
        # a sensible first size: the real size when it looks real, else about as tall as a person's waist
        height = int(round(real_h)) if 20 <= real_h <= 3000 else 150
    big = "place" if i["faces_in"] > 40000 else ("high" if i["faces_in"] > 8000 else "")   # big models keep more
    pal = palette(nm, 8)
    cols = "\n".join(f'        "{h}": "{h}",   # {n} faces ({mat})' for h, n, mat in pal)
    cols += '\n        # "*": "#cc2222",   # <- un-comment to paint the WHOLE model one colour (shading kept)'
    kind = kind if kind in ("object3d", "prop3d", "vehicle3d") else "object3d"
    lines = [f'KIND = "{kind}"',
             f'DESCRIPTION = {json.dumps(description or re.sub(r"_3d$", "", nm).replace("_", " ") + " (imported model)")}']
    if kind == "prop3d":
        lines.append(f"ABILITIES = {json.dumps(abilities or ['movable'])}")
    lines += [f'MODEL = "{nm}"',
              f'CREDIT = {json.dumps(meta.get("credit") or "")}',
              f'LICENSE = {json.dumps(meta.get("license") or "")}',
              f'SOURCE = {json.dumps(meta.get("source") or "")}',
              "",
              f"# Imported from {i['file']}: {i['faces_in']} triangles in the file, {i['faces']} drawn"
              f" (max_faces simplifies it more).",
              f"# Real size {i['size_m'][0]} x {i['size_m'][1]} x {i['size_m'][2]} m.  height = how tall here (a person is 300).",
              "# colors: the model's real colours (left) -> change the right side to any colour, a colour name"
              " (\"mud\") or pen.material(\"gold\").  \"*\": \"red\" paints everything not listed.",
              "# turn = degrees round the up axis.  You can draw more things round it with the pen as usual.",
              "def draw(pen, t, state):",
              (f'    pen.model("{nm}", x=0, y=0, z=0, height={height}, turn=0, detail="{big}", two_sided=True, colors={{'
               if big else f'    pen.model("{nm}", x=0, y=0, z=0, height={height}, turn=0, colors={{'),
              cols,
              "    })",
              ""]
    return "\n".join(lines)


def credits_for(text):
    """Credits of the imported models a story uses.  text = the story (+ its world) as JSON text.
    Follows pen.instance(...) inside code files too (a place built from an imported model)."""
    from . import codedraw
    try:
        codes = codedraw.list_code()
    except Exception:
        return []
    src = {}
    for n, m in codes.items():
        try:
            src[n] = open(m["file"], encoding="utf-8").read()
        except OSError:
            src[n] = ""
    used = {n for n in codes if f'"{n}"' in text}
    todo = list(used)
    while todo:                                           # code files used by used code files
        n = todo.pop()
        for k in re.findall(r'pen\.instance\(\s*["\']([a-z0-9_]+)', src.get(n, "")):
            if k in codes and k not in used:
                used.add(k)
                todo.append(k)
    out = []
    for n in sorted(used):
        s = src.get(n, "")
        for mn in re.findall(r'(?:pen|rig)\.model\((?:\s*pen\s*,)?\s*["\']([a-z0-9_/]+)', s):
            st = codedraw.settings_of(s)
            meta = list_models().get(_clean(mn.split("/")[0]), {})
            who = str(st.get("CREDIT") or meta.get("credit") or "").strip()
            lic = str(st.get("LICENSE") or meta.get("license") or "").strip()
            if who and "my own" not in lic.lower():
                line = f"{who} ({lic})" if lic and lic.lower() not in who.lower() else who
                if line not in out:
                    out.append(line)
    return out
