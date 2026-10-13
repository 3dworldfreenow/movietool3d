"""Puppet characters: a character "costume" made from AI-drawn body parts, worn on the engine's skeleton.

The skeleton, the poses and every action stay exactly as they are - only the look changes. Each bone
carries its picture (like a paper / cut-out puppet): when the bone turns, its picture turns with it.

  sheet A (side view, facing right, one row):  head, torso, upper arm, lower arm, hand, thigh, lower leg, foot
  sheet B (optional):  head front, torso front, head back, torso back, head talking (mouth open), head eyes closed
  sheet C (optional):  side heads happy, sad, angry, scared
  sheet D (optional, face):  8 side heads, one per MOUTH SHAPE (M-B-P, EE, EH, AA, OH, OO, F-V, L) - real lip sync
  sheet E (optional, face):  8 front heads: the same mouth shapes seen from the front + eyes closed
  sheet F (optional, face):  side half-closed eyes, side brows raised, side surprised, front happy / sad / angry /
                             scared / surprised
The face sheets swap the whole head picture each frame (like the mouth charts of cut-out animation), so there is
nothing to line up: the speech's sounds (engine/lipsync.py) pick the head with the matching mouth.

Upload a sheet -> the white background is removed -> the parts are found and named in order (you can
change any name) -> "Build" measures where every part joins (its joint points) -> use it in a story:
    "characters": { "ravi": { "name": "Ravi", "age": "child", "look": "ravi_puppet" } }
Saved in assets/puppets/<name>/.
"""
import json
import math
import os
import re
import shutil

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "assets", "puppets")
VERSION = 1

SHEET_ORDER = {
    "A": ["head", "torso", "upper_arm", "lower_arm", "hand", "thigh", "lower_leg", "foot"],
    "B": ["head_front", "torso_front", "head_back", "torso_back", "head_talk", "head_blink"],
    "C": ["head_happy", "head_sad", "head_angry", "head_scared"],
    "D": ["head_mbp", "head_ee", "head_eh", "head_aa", "head_oh", "head_oo", "head_fv", "head_l"],
    "E": ["head_front_mbp", "head_front_ee", "head_front_eh", "head_front_aa", "head_front_oh", "head_front_oo",
          "head_front_fv", "head_front_blink"],
    "F": ["head_half", "head_brows", "head_surprised", "head_front_happy", "head_front_sad", "head_front_angry",
          "head_front_scared", "head_front_surprised"],
}
SHEETS = tuple(SHEET_ORDER)
FACE_SHEETS = ("D", "E", "F")
LABELS = [lab for k in SHEETS for lab in SHEET_ORDER[k] if lab != "head_surprised"] + [
    "head_surprised", "foot_front", "ignore"]
REQUIRED = SHEET_ORDER["A"]
LIMBS = ("upper_arm", "lower_arm", "thigh", "lower_leg")
EMOTION_HEAD = {"happy": "head_happy", "laughing": "head_happy", "sad": "head_sad", "crying": "head_sad",
                "angry": "head_angry", "scared": "head_scared", "surprised": "head_surprised"}
# lipsync shape (engine/lipsync.py) -> mouth head, and what to try when that head was not drawn
VISEME = {"A": "mbp", "B": "ee", "C": "eh", "D": "aa", "E": "oh", "F": "oo", "G": "fv", "H": "l"}
VISEME_NEAR = {"mbp": [], "ee": ["eh"], "eh": ["aa"], "aa": ["eh"], "oh": ["oo", "aa"], "oo": ["oh"],
               "fv": ["ee", "mbp"], "l": ["eh", "aa"]}
HALF_EYES = ("thinking", "sleepy", "tired", "bored", "suspicious", "shy")

STYLE = ("2D cartoon for a children's animated series, flat colours with soft shading, thick clean dark "
         "outline, light from the top right")


def _clean(name):
    return re.sub(r"[^a-z0-9_]+", "_", str(name).lower()).strip("_")[:40]


def folder(name):
    return os.path.join(DIR, _clean(name))


# ---------------------------------------------------------------------------- prompts
def prompts(desc, style=STYLE):
    desc = (desc or "a friendly Indian boy, 8 years old, spiky black hair, blue t-shirt, grey shorts, "
            "red sneakers").strip()
    rules = ("All parts at the SAME scale, clear white space between them (no part touches another), pure white "
             "background, no shadows, no ground, no text, no labels, no numbers, no extra objects.")
    same = (f"{style}. The SAME character ({desc}), exactly the same style, line thickness, colours and scale as "
            f"the parts sheet I give you.")
    heads = ("Every head is EXACTLY the same size, the same outline, hair and ears, with the same short neck stub "
             "at the bottom - only the parts named below change. Draw them like an animator's model sheet / mouth "
             "chart: if you laid them on top of each other, only the mouth, eyes or brows would move. A big, clear "
             "face (it is used for close-ups): visible lips, teeth and tongue where they show, eye whites and "
             "pupils, eyebrows. Arrange the 8 heads in 2 rows of 4, read left to right, top row first.")
    a = (f"{style}. A body PARTS SHEET for a cut-out puppet animation of {desc}, drawn exactly from the SIDE "
         f"(profile, facing RIGHT). Draw 8 separate parts in ONE horizontal row from left to right: "
         f"1) the head with hair, facing right, eyes open, mouth closed in a relaxed neutral line, with a short "
         f"neck stub at the bottom; "
         f"2) the upper body / torso with its clothes, upright, WITHOUT head and WITHOUT arms; "
         f"3) one upper arm hanging straight down (with the sleeve); 4) one lower arm hanging straight down; "
         f"5) one relaxed hand hanging down; 6) one thigh (upper leg) straight down, with the trousers / skirt; "
         f"7) one lower leg straight down; 8) one foot with its shoe in side view, toes pointing RIGHT. "
         f"Every arm and leg part has ROUNDED ends so the joints can overlap. {rules}")
    b = (f"{same} Draw 6 separate parts in ONE horizontal row from left to right: "
         f"1) the head seen from the FRONT (looking at us, mouth closed); 2) the torso seen from the FRONT, "
         f"without head and arms; 3) the head seen from the BACK (back of the hair); 4) the torso seen from the BACK; "
         f"5) the side-view head (facing right) with the MOUTH WIDE OPEN, talking; "
         f"6) the side-view head (facing right) with the EYES CLOSED. {rules}")
    c = (f"{same} Draw 4 side-view heads (facing right) in ONE horizontal row from left to right: 1) happy with a big "
         f"smile, 2) sad, 3) angry, 4) scared. {heads.split(' Arrange')[0]} {rules}")
    d = (f"{same} A MOUTH CHART for lip sync: 8 side-view heads (profile, facing RIGHT, eyes open, neutral brows), "
         f"each saying a different sound: "
         f"1) M / B / P - lips pressed together, slightly pushed out; "
         f"2) EE / S / T - lips stretched wide, teeth together and showing, mouth nearly shut; "
         f"3) EH - mouth half open, a little teeth showing; "
         f"4) AA - jaw dropped, mouth wide open, tongue low; "
         f"5) OH - round open mouth; "
         f"6) OO / W - small tight round lips pushed forward; "
         f"7) F / V - upper teeth resting on the lower lip; "
         f"8) L / TH - mouth open, tongue tip up behind the upper teeth. "
         f"{heads} {rules}")
    e = (f"{same} A FRONT MOUTH CHART: 8 heads seen from the FRONT (looking straight at us, eyes open, neutral "
         f"brows), each saying a different sound: "
         f"1) M / B / P - lips pressed together; "
         f"2) EE / S / T - wide stretched lips, teeth together and showing; "
         f"3) EH - mouth half open; 4) AA - jaw dropped, mouth wide open; 5) OH - round open mouth; "
         f"6) OO / W - small tight round lips; 7) F / V - upper teeth on the lower lip; "
         f"8) mouth closed and EYES CLOSED (a blink). "
         f"{heads} {rules}")
    f = (f"{same} FACIAL EXPRESSIONS, mouth closed unless said: "
         f"1) side view (facing right), eyelids HALF closed (sleepy / thinking); "
         f"2) side view, eyebrows RAISED high, eyes wide (asking a question); "
         f"3) side view, SURPRISED - brows up, eyes wide, small open 'o' mouth; "
         f"4) FRONT view (looking at us), HAPPY - big smile; 5) FRONT view, SAD - brows tilted up in the middle, "
         f"mouth turned down; 6) FRONT view, ANGRY - brows pulled down, teeth clenched; "
         f"7) FRONT view, SCARED - eyes wide, brows up, mouth open in a wobbly line; "
         f"8) FRONT view, SURPRISED - brows up, eyes wide, round open mouth. "
         f"{heads} {rules}")
    return {"A": a, "B": b, "C": c, "D": d, "E": e, "F": f}


def desc_from_character(spec):
    """A short look description from a saved character spec (colours, hair, outfit)."""
    age = spec.get("age", "adult")
    who = {"child": "child", "teen": "teenager", "old": "old"}.get(age, "adult")
    g = "girl" if spec.get("gender") == "female" and age == "child" else (
        "boy" if age == "child" else ("woman" if spec.get("gender") == "female" else "man"))
    bits = [f"a friendly Indian {g}" if who == "child" else f"a friendly Indian {who} {g}"]
    if spec.get("hair"):
        bits.append(f"{spec.get('hair_color', 'black')} {spec['hair']} hair")
    if spec.get("outfit"):
        bits.append(f"{spec['outfit']} in {spec.get('outfit_color', '')}".strip())
    if spec.get("hat"):
        bits.append(f"a {spec['hat']}")
    if spec.get("glasses"):
        bits.append("glasses")
    if spec.get("mustache"):
        bits.append("a mustache")
    if spec.get("profession"):
        bits.append(f"dressed as a {spec['profession']}")
    return ", ".join(bits)


# ---------------------------------------------------------------------------- sheet -> parts
def split_sheet(name, sheet, data_bytes):
    """Cut a parts sheet into its parts. Returns [{id, label, w, h}] in reading order."""
    from PIL import Image
    from . import sheets
    sheet = str(sheet).upper()[:1] or "A"
    im = sheets.load_rgba(data_bytes)
    os.makedirs(os.path.join(folder(name), "sheets"), exist_ok=True)
    im.save(os.path.join(folder(name), "sheets", sheet + ".png"))    # kept: sheets B / C are drawn to match A
    pieces = sheets.cut_pieces(im)
    d = os.path.join(folder(name), "parts")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):                             # replace this sheet's old parts
        if f.startswith(sheet):
            os.remove(os.path.join(d, f))
    labels = load_labels(name)
    labels = {k: v for k, v in labels.items() if not k.startswith(sheet)}
    order = SHEET_ORDER.get(sheet, [])
    out = []
    for k, (crop, (x0, y0, x1, y1), _) in enumerate(pieces):
        pid = f"{sheet}{k + 1}"
        Image.fromarray(crop, "RGBA").save(os.path.join(d, pid + ".png"))
        labels[pid] = order[k] if k < len(order) else "ignore"
        out.append({"id": pid, "label": labels[pid], "w": int(x1 - x0), "h": int(y1 - y0)})
    save_labels(name, labels)
    return out


def sheet_bytes(name, sheet="A"):
    p = os.path.join(folder(name), "sheets", str(sheet).upper()[:1] + ".png")
    if os.path.exists(p):
        with open(p, "rb") as fh:
            return fh.read()
    return None


def load_labels(name):
    try:
        with open(os.path.join(folder(name), "labels.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_labels(name, labels):
    os.makedirs(folder(name), exist_ok=True)
    with open(os.path.join(folder(name), "labels.json"), "w", encoding="utf-8") as fh:
        json.dump(labels, fh, indent=1)


def list_parts(name):
    d = os.path.join(folder(name), "parts")
    labels = load_labels(name)
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d), key=lambda s: (s[0], int(re.sub(r"\D", "", s) or 0))):
            if f.endswith(".png"):
                pid = f[:-4]
                out.append({"id": pid, "label": labels.get(pid, "ignore")})
    return out


# ---------------------------------------------------------------------------- joint points of a part
def _rows_center(a, y0, y1):
    ys, xs = np.nonzero(a[max(0, y0):max(y0 + 1, y1)] > 90)
    return float(xs.mean()) if len(xs) else a.shape[1] / 2.0


def anchors(label, alpha):
    """(p0, p1) in picture pixels: where the part joins its parent and its child (p1 None if none)."""
    a = alpha
    ys, xs = np.nonzero(a > 90)
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    h, w = y1 - y0, x1 - x0
    if label in LIMBS:                                 # hangs straight down: joint centres one "radius" in
        widths = (a > 90).sum(axis=1)
        wmed = float(np.median(widths[widths > 0]))
        r = min(wmed * 0.5, h * 0.2)
        return ((_rows_center(a, y0, int(y0 + 2 * r)), y0 + r), (_rows_center(a, int(y1 - 2 * r), y1), y1 - r))
    if label.startswith("torso"):                      # p0 = hips (bottom), p1 = neck (top)
        return ((_rows_center(a, int(y1 - 0.12 * h), y1), y1 - 0.08 * h),
                (_rows_center(a, y0, int(y0 + 0.1 * h)), y0 + 0.06 * h))
    if label == "hand":
        return ((_rows_center(a, y0, int(y0 + 0.2 * h)), y0 + 0.12 * h), None)
    if label == "foot":                                # side foot pointing right: ankle above the heel part
        cx = x0 + 0.32 * w
        return ((cx, y0 + 0.28 * h), (x1 - 0.05 * w, y1 - 0.25 * h))
    if label == "foot_front":
        return ((_rows_center(a, y0, int(y0 + 0.3 * h)), y0 + 0.2 * h), None)
    if label.startswith("head"):                       # the neck point at the bottom
        cx = _rows_center(a, int(y1 - 0.12 * h), y1)
        return ((cx, y1 - 0.04 * h), None)
    return (((x0 + x1) / 2.0, (y0 + y1) / 2.0), None)


def build(name, labels=None):
    """Measure every labelled part and write puppet.json. Returns (meta, missing required labels)."""
    from PIL import Image
    if labels is not None:
        save_labels(name, labels)
    labels = load_labels(name)
    d = folder(name)
    parts = {}
    for pid, lab in labels.items():
        if lab in (None, "", "ignore") or lab not in LABELS:
            continue
        src = os.path.join(d, "parts", pid + ".png")
        if not os.path.exists(src):
            continue
        im = Image.open(src).convert("RGBA")
        al = np.asarray(im)[..., 3]
        if (al > 90).sum() < 20:
            continue
        p0, p1 = anchors(lab, al)
        shutil.copyfile(src, os.path.join(d, lab + ".png"))
        parts[lab] = {"file": lab + ".png", "w": im.width, "h": im.height, "p0": [float(p0[0]), float(p0[1])],
                      "p1": [float(p1[0]), float(p1[1])] if p1 else None,
                      "hpx": float(np.ptp(np.nonzero(al > 90)[0]) + 1)}
    missing = [r for r in REQUIRED if r not in parts]
    meta = {"version": VERSION, "name": _clean(name), "parts": parts, "missing": missing}
    with open(os.path.join(d, "puppet.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    _CACHE.pop(_clean(name), None)
    return meta, missing


def list_puppets():
    out = []
    if os.path.isdir(DIR):
        for n in sorted(os.listdir(DIR)):
            m = load(n)
            if m:
                out.append({"name": n, "ready": not m.get("missing"), "parts": sorted(m["parts"]),
                            "missing": m.get("missing", [])})
    return out


def delete(name):
    shutil.rmtree(folder(name), ignore_errors=True)
    _CACHE.pop(_clean(name), None)


# ---------------------------------------------------------------------------- drawing
_CACHE = {}


def load(name):
    key = _clean(name)
    got = _CACHE.get(key)
    if got is not None:
        return got
    try:
        with open(os.path.join(DIR, key, "puppet.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    if meta.get("missing"):
        return None
    import cairo
    meta["_surf"] = {lab: cairo.ImageSurface.create_from_png(os.path.join(DIR, key, p["file"]))
                     for lab, p in meta["parts"].items()}
    ks = []
    from .poses import BONES
    for lab, bone in (("upper_arm", "upper_arm"), ("lower_arm", "fore_arm"), ("thigh", "thigh"), ("lower_leg", "shin")):
        p = meta["parts"][lab]
        ks.append(BONES[bone] / max(math.dist(p["p0"], p["p1"]), 1.0))
    meta["_k"] = float(np.median(ks))                  # the art's scale: picture px -> skeleton units
    _CACHE[key] = meta
    return meta


def available(name):
    return bool(name) and load(name) is not None


def _blit(ctx, pup, lab, P0, P1=None, angle=None, k=None, alpha=1.0, dark=0.0):
    """Draw part `lab` so its p0 sits on P0 and (if given) its p1 on P1. World coords, y-up."""
    p = pup["parts"].get(lab)
    if p is None:
        return False
    surf = pup["_surf"][lab]
    (ax, ay) = p["p0"]
    if P1 is not None and p["p1"] is not None:
        bx, by = p["p1"]
        iv = (bx - ax, -(by - ay))
        v = (P1[0] - P0[0], P1[1] - P0[1])
        angle = math.atan2(v[1], v[0]) - math.atan2(iv[1], iv[0])
        k = math.hypot(*v) / max(math.hypot(*iv), 1e-6)
    ctx.save()
    ctx.translate(P0[0], P0[1])
    ctx.rotate(angle or 0.0)
    ctx.scale(k, -k)
    ctx.translate(-ax, -ay)
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint_with_alpha(alpha)
    if dark > 0:                                       # far limbs a little darker
        ctx.set_source_rgba(0.05, 0.05, 0.12, dark * alpha)
        ctx.mask_surface(surf, 0, 0)
    ctx.restore()
    return True


def _viseme_head(parts, mouth, prefix):
    """The head drawn with this moment's mouth shape (sheet D / E), or None."""
    ctl = getattr(mouth, "ctl", None) or {}
    sh = ctl.get("shape")
    if sh is None:                                     # no lip-sync data: the opening decides
        if mouth > 0.6:
            sh = "D"
        elif mouth > 0.3:
            sh = "C"
        elif mouth > 0.1:
            sh = "B"
        else:
            return None
    v = VISEME.get(sh)
    if v is None:                                      # "X": rest
        return None
    for name in [v] + VISEME_NEAR.get(v, []):
        if prefix + name in parts:
            return prefix + name
    return None


def _head_label(pup, face, mouth, blink):
    parts = pup["parts"]
    ctl = getattr(mouth, "ctl", None) or {}
    if (blink or face == "sleeping") and "head_blink" in parts:
        return "head_blink"
    talk = _viseme_head(parts, mouth, "head_")
    if talk:
        return talk
    if mouth > 0.3 and "head_talk" in parts:
        return "head_talk"
    emo = EMOTION_HEAD.get(face or "")
    if emo and emo in parts:
        return emo
    if (face in HALF_EYES or 0.2 < ctl.get("lid", 0.0) < 0.8) and "head_half" in parts:
        return "head_half"
    if ctl.get("brow", 0.0) > 0.45 and "head_brows" in parts:
        return "head_brows"                            # a question / a stressed word: brows go up
    return "head"


def _front_head_label(pup, face, mouth, blink):
    parts = pup["parts"]
    if (blink or face == "sleeping") and "head_front_blink" in parts:
        return "head_front_blink"
    talk = _viseme_head(parts, mouth, "head_front_")
    if talk:
        return talk
    emo = EMOTION_HEAD.get(face or "", "")
    emo = emo.replace("head_", "head_front_") if emo else ""
    if emo and emo in parts:
        return emo
    return "head_front"


def draw_side(ctx, c, pose, x, facing, face, mouth, t, extras, alpha, blink, seat, y=0.0, shadow=True):
    """Side view on the skeleton (same joints as the drawn cartoon). Returns the usual info dict."""
    from .character import solve, draw_shadow, BONES
    pup = load(c.look)
    s = c.scale
    from .character import KID_AGES, body_of, head_k
    child = c.age in KID_AGES
    hr = BONES["head_r"] * head_k(c)
    J = solve(pose, s, hr, body_of(c))
    f = -1.0 if facing < 0 else 1.0
    ka = pup["_k"] * s
    if shadow:
        feet = min(J["fn"][1], J["ff"][1]) / max(s, 0.1)
        draw_shadow(ctx, x, max(0.0, feet - 2), 46 * s * c.build ** 0.5, alpha, y)
    if seat:
        from .classic import _draw_stool
        _draw_stool(ctx, (x + f * J["hip"][0], J["hip"][1] + y), s, alpha)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(f, 1)                                    # local frame: +x = forward, y up
    head_ang = math.radians(pose.get("rot", 0.0) - pose["torso"] - pose["head"])

    def arm(side, dark):
        e, h = J["e" + side], J["h" + side]
        _blit(ctx, pup, "upper_arm", J["sh"], e, alpha=alpha, dark=dark)
        _blit(ctx, pup, "lower_arm", e, h, alpha=alpha, dark=dark)
        ang = math.atan2(h[1] - e[1], h[0] - e[0]) + math.pi / 2      # the hand hangs on along the forearm
        _blit(ctx, pup, "hand", h, angle=ang, k=ka, alpha=alpha, dark=dark)

    def leg(side, dark):
        kn, fo, toe = J["k" + side], J["f" + side], J["toe_" + side]
        _blit(ctx, pup, "thigh", J["hip"], kn, alpha=alpha, dark=dark)
        _blit(ctx, pup, "lower_leg", kn, fo, alpha=alpha, dark=dark)
        p = pup["parts"]["foot"]
        tv = (toe[0] - fo[0], toe[1] - fo[1])
        iv = (p["p1"][0] - p["p0"][0], -(p["p1"][1] - p["p0"][1]))
        ang = math.atan2(tv[1], tv[0]) - math.atan2(iv[1], iv[0])
        _blit(ctx, pup, "foot", fo, angle=ang, k=ka, alpha=alpha, dark=dark)

    arm("f", 0.22)
    leg("f", 0.22)
    _blit(ctx, pup, "torso", J["hip"], J["neck"], alpha=alpha)
    leg("n", 0.0)
    hl = _head_label(pup, face, mouth, blink)
    bob = 0.0
    if hl in ("head", "head_brows", "head_half") and mouth > 0.3 and "head_talk" not in pup["parts"]:
        bob = 0.04 * math.sin(t * 20)                  # no talking head drawn: a little nod while speaking
    _blit(ctx, pup, hl, J["neck"], angle=head_ang + bob, k=ka * _head_fix(pup, hl), alpha=alpha)
    arm("n", 0.0)
    ctx.restore()

    def W(p):
        return (x + f * p[0], p[1] + y)
    r = hr * s
    hx, hy = W(J["head"])
    return {"hand": W(J["hn"]), "head": (hx, hy), "hip": W(J["hip"]), "head_r": r,
            "mouth": (hx + f * 0.6 * r, hy - 0.4 * r)}


def _head_fix(pup, lab):
    """Head variants drawn at a slightly different size are matched to the main head of their view."""
    base = "head_front" if lab.startswith("head_front") else ("head_back" if lab == "head_back" else "head")
    if lab in ("head", "head_front", "head_back") or base not in pup["parts"]:
        base = "head"
    if lab == base:
        return 1.0
    a, b = pup["parts"][base]["hpx"], pup["parts"][lab]["hpx"]
    return a / b if 0.5 < a / b < 2.0 else 1.0


def has_front(c, view):
    pup = load(getattr(c, "look", None))
    if not pup:
        return False
    need = ("head_front", "torso_front") if view == "camera" else ("head_back", "torso_back")
    return all(n in pup["parts"] for n in need)


def draw_front(ctx, c, pose, x, y, view, face, mouth, t, alpha, blink, astride=0.0, scale_mul=1.0):
    """Front ("camera") or back ("away") view, same joint layout as the drawn cartoon's front view."""
    from .character import draw_shadow, BONES
    pup = load(c.look)
    s = c.scale * scale_mul
    back = view == "away"
    ka = pup["_k"] * s
    tp = pup["parts"]["torso_back" if back else "torso_front"]
    tw = (np.clip(tp["w"] * pup["_k"], 20, 90)) * s
    lift = pose.get("lift", 0.0) * s
    ph = (pose.get("ln_t", 0) - pose.get("lf_t", 0)) / 48.0
    lk, rk = max(0.0, ph), max(0.0, -ph)
    thigh, shin = BONES["thigh"] * s, BONES["shin"] * s
    hip_y = y + thigh + shin + lift
    if astride > 0:
        lk = rk = 0.0
    neck_y = hip_y + BONES["torso"] * s
    if astride <= 0:
        draw_shadow(ctx, x, lift / max(s, 0.1), 34 * s * c.build ** 0.5, alpha, y)
    for side, kk in ((-1, lk), (1, rk)):               # legs
        fx = x + side * tw * 0.26
        foot_y = y + lift + 26 * s * kk
        knee = (fx + side * 4 * s, hip_y - thigh * (1 - 0.35 * kk))
        if astride > 0:
            knee = (x + side * (astride + 6 * s), hip_y - thigh * 0.45)
            foot_y = hip_y - thigh * 0.45 - shin * 0.8
            fx = x + side * astride * 0.92
        _blit(ctx, pup, "thigh", (fx, hip_y), knee, alpha=alpha)
        _blit(ctx, pup, "lower_leg", knee, (fx, foot_y), alpha=alpha)
        if "foot_front" in pup["parts"]:
            _blit(ctx, pup, "foot_front", (fx, foot_y + 8 * s), angle=0.0, k=ka, alpha=alpha)
        else:
            ctx.save()
            ctx.translate(fx, 0)
            ctx.scale(side * 0.8, 1)                   # a side foot, turned a little outwards
            _blit(ctx, pup, "foot", (0.0, foot_y), angle=0.0, k=ka, alpha=alpha)
            ctx.restore()

    def arm(side):
        sx_, sy_ = x + side * tw * 0.47, neck_y - 10 * s
        a1 = math.radians(abs(pose.get("an_u" if side > 0 else "af_u", 8)) * 0.55)
        e = (sx_ + side * math.sin(a1) * BONES["upper_arm"] * s, sy_ - math.cos(a1) * BONES["upper_arm"] * s)
        a2 = a1 + math.radians(abs(pose.get("an_l" if side > 0 else "af_l", 8)) * 0.35)
        h = (e[0] + side * math.sin(a2) * BONES["fore_arm"] * s, e[1] - math.cos(a2) * BONES["fore_arm"] * s)
        _blit(ctx, pup, "upper_arm", (sx_, sy_), e, alpha=alpha)
        _blit(ctx, pup, "lower_arm", e, h, alpha=alpha)
        _blit(ctx, pup, "hand", h, angle=math.atan2(h[1] - e[1], h[0] - e[0]) + math.pi / 2, k=ka, alpha=alpha)
        return h
    if back:
        hand = arm(1)
        arm(-1)
    _blit(ctx, pup, "torso_back" if back else "torso_front", (x, hip_y), (x, neck_y), alpha=alpha)
    if not back:
        hand = arm(1)
        arm(-1)
    hl = "head_back" if back else _front_head_label(pup, face, mouth, blink)
    bob = 0.0
    if hl == "head_front" and mouth > 0.3:
        bob = 0.03 * math.sin(t * 20)                  # no front mouth heads drawn: a little nod while speaking
    _blit(ctx, pup, hl, (x, neck_y), angle=bob, k=ka * _head_fix(pup, hl), alpha=alpha)
    r = BONES["head_r"] * s * 1.15
    hx, hy = x, neck_y + 12 * s + r
    return {"hand": hand, "head": (hx, hy), "hip": (x, hip_y), "head_r": r, "mouth": (hx, hy - 0.4 * r)}


# ---------------------------------------------------------------------------- Studio preview
def preview(name, spec=None, seconds=6.0, fps=12, W=640, H=360):
    """Animated WebP: walks, talks and waves in side view, then turns to the front and the back. The talking goes
    through every mouth shape, so the face sheets (D / E) can be checked here."""
    import io
    import cairo
    from PIL import Image
    from .character import CharacterDef, draw_character
    from .depth import draw_front_view
    from .lipsync import Mouth, SHAPES
    from .poses import ACTIONS

    def say(t):                                        # "M-AA-EE-OH-OO-F-L-EH ..." at about 8 sounds a second
        seq = "ADBEFGHCXADEB"
        sh = seq[int(t * 8) % len(seq)]
        jaw, _, _, closed = SHAPES[sh][:4]
        return Mouth(jaw * (1 - 0.85 * closed), {"shape": sh, "brow": 0.6 if sh == "X" else 0.0})
    sp = dict(spec or {"age": "child", "name": "Puppet"})
    sp["look"] = _clean(name)
    c = CharacterDef("puppet_preview", sp, 0)
    frames = []
    n = int(seconds * fps)
    for i in range(n):
        t = i / fps
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        ctx = cairo.Context(surf)
        g = cairo.LinearGradient(0, 0, 0, H)
        g.add_color_stop_rgb(0, 0.86, 0.93, 0.98)
        g.add_color_stop_rgb(0.75, 0.97, 0.97, 0.95)
        g.add_color_stop_rgb(0.76, 0.78, 0.86, 0.7)
        g.add_color_stop_rgb(1, 0.7, 0.8, 0.6)
        ctx.set_source(g)
        ctx.paint()
        sc = H / 1080.0 * 2.4
        ctx.translate(W / 2, H * 0.9)
        ctx.scale(sc, -sc)
        if t < 2.2:
            pose, ex = ACTIONS["walk"].fn(t, 2.2, {"speed": 200, "dist": t * 200, "params": {}})
            draw_character(ctx, c, pose, -80, 1, "happy", 0.0, t, ex, 1.0, False, False)
        elif t < 3.6:
            pose, ex = ACTIONS["wave"].fn(t - 2.2, 1.4, {"params": {}})
            draw_character(ctx, c, pose, 0, 1, "neutral", say(t), t, ex, 1.0, (t % 1.3) < 0.1, False)
        elif t < 4.8:
            pose, ex = ACTIONS["walk"].fn(t, 1.2, {"speed": 0, "params": {}})
            draw_front_view(ctx, c, pose, 0, 0, "camera", "neutral" if t < 4.3 else "happy", say(t) if t < 4.3 else 0.0,
                            t, 1.0, 4.1 < t < 4.2)
        else:
            pose, ex = ACTIONS["walk"].fn(t, 1.2, {"speed": 0, "params": {}})
            draw_front_view(ctx, c, pose, 0, 0, "away", "neutral", 0.0, t, 1.0, False)
        surf.flush()
        im = Image.frombuffer("RGBA", (W, H), bytes(surf.get_data()), "raw", "BGRA", 0, 1).convert("RGB")
        frames.append(im)
    buf = io.BytesIO()
    frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0,
                   quality=80)
    return buf.getvalue()
