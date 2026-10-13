"""🗿 People for Sculpt 3D: a CHARACTER CARD (JSON - what the AI writes) -> a smooth sculpted toon person,
TV-cartoon proportions (a big head, a round body, short legs - Motu Patlu / Pixar style). The AI only fills in the
card; the shapes, the blending, the ink outline and the light make the quality.

Every field is OPTIONAL (good defaults), grouped, and checked: numbers are kept in their safe range, unknown words
fall back to the default, and check(card) says what it fixed - so a card can never make a broken character.
Start from a "preset" and change only what is different.

CARD (all colours "#rrggbb"; numbers: 1.0 = normal):
  "preset": "chubby_uncle|slim_young_man|strong_man|auntie|young_woman|grandpa|grandma|boy|girl"
  "gender": "male|female", "age": "child|teen|adult|old", "skin": "#c49a72" | fair|light|wheat|medium|tan|brown|dark|deep
  "body":   {"height", "build": "slim|normal|strong|chubby|fat", "belly": 0..1, "head_size", "shoulders",
             "arm_length", "leg_length", "neck", "proportions": "toon|real"}
  "face":   {"shape": "round|oval|square|long", "chubby": 0..1, "cheek", "jaw", "chin", "nose", "nose_w",
             "nose_shape": "round|pointed|button", "mouth", "lips": "#hex", "eyes", "eye_color": "#hex",
             "eye_spacing", "eye_height", "lashes": true, "ears", "brows", "brow_color": "#hex", "blush": "#hex"|false}
  "hair":   {"style": "short|quiff|spiky|curly|side_part|long|ponytail|bun|braid|bald|bald_sides", "color", "volume"}
  "facial_hair": {"mustache": "none|thin|thick|handlebar", "beard": "none|stubble|short|full", "color"}
  "top":    {"type": "kurta|tshirt|shirt|hoodie|sweater|vest|blouse", "color", "color2",
             "sleeves": "long|three_quarter|half|none", "length": "hip|thigh|knee", "collar": "none|round|v|shirt|hood",
             "pattern": "plain|stripes|checks", "pattern_color", "pocket": true, "buttons": true}
  "bottom": {"type": "pyjama|pants|jeans|shorts|dhoti|lungi|skirt|long_skirt", "color"}
  "shoes":  {"type": "shoes|sneakers|chappal|boots|barefoot", "color", "sole"}
  "accessories": [{"type": "glasses|sunglasses|cap|gandhi_topi|turban|gamchha|scarf|watch|pens|bindi|earrings|
                   chain|stethoscope", "color", "color2", "colors": [...]}]
  "expression": "smile|happy|neutral|sad|angry|surprised",  "pose": "rest|open|wave|hips"
The older story cards work too ("outfit", "outfit_color", "pants", "shoes", "accent", "hair", "hair_color",
"mustache", "beard", "build", "height", "face": {...}, "sculpt": {"glasses": true, "pens": [...]}).

    from engine import sculpt_people as sp, sculpt3d as s3
    S = sp.person(card); parts = s3.light(S, S.build()); s3.render(parts, angle=30).save("me.png")
Units: metres. The figure stands on y = 0 and faces +z.
"""
import re

import numpy as np

from .sculpt3d import Sculpt, _sd_plane, _sd_ellipsoid

SKIN = {"fair": "#f1d0b5", "light": "#e8bf9c", "wheat": "#d9a97c", "medium": "#c99069", "tan": "#b57a52",
        "brown": "#9a6440", "dark": "#7a4a2e", "deep": "#5a3520"}
HAIR = {"black": "#1b1410", "dark_brown": "#3a2416", "brown": "#6a4128", "light_brown": "#8a6040", "grey": "#9a9a98",
        "gray": "#9a9a98", "white": "#e8e6e0", "blonde": "#d8b060", "red": "#9a3a1a"}
ALIASES = {"build": {"muscular": "strong", "heavy": "fat", "thin": "slim", "average": "normal"},
           "shape": {"heart": "oval", "egg": "oval", "wide": "round"}}
OUTFIT_TOP = {"kurta": "kurta", "shirt": "shirt", "tshirt": "tshirt", "sports": "tshirt", "farmer": "kurta",
              "dhoti": "vest", "suit": "coat", "uniform": "shirt", "police": "shirt", "labcoat": "coat",
              "saree": "blouse", "salwar": "kurta", "dress": "kurta", "frock": "kurta", "overalls": "shirt",
              "army": "shirt", "pilot": "shirt", "chef": "coat", "nurse": "coat", "firefighter": "coat", "royal": "coat",
              "astronaut": "coat", "sadhu": "kurta", "cape": "tshirt", "shorts": "tshirt", "none": "vest"}

# the safe range of every number (anything outside is pulled back in, and check() says so)
RANGES = {"height": (0.6, 1.4), "belly": (0, 1), "head_size": (0.7, 1.5), "shoulders": (0.7, 1.4), "arm_length": (0.8, 1.25),
          "leg_length": (0.7, 1.3), "neck": (0.5, 1.6), "chubby": (0, 1), "cheek": (0.6, 1.8), "jaw": (0.7, 1.4),
          "chin": (0.6, 1.5), "nose": (0.6, 1.8), "nose_w": (0.6, 1.6), "mouth": (0.6, 1.5), "eyes": (0.7, 1.5),
          "eye_spacing": (0.8, 1.25), "eye_height": (0.6, 1.5), "ears": (0.6, 1.6), "brows": (0.4, 1.8), "volume": (0.6, 1.6)}
CHOICES = {"gender": ("male", "female"), "age": ("child", "teen", "adult", "old"),
           "build": ("slim", "normal", "strong", "chubby", "fat"), "shape": ("round", "oval", "square", "long"),
           "nose_shape": ("round", "pointed", "button"),
           "style": ("short", "quiff", "spiky", "curly", "side_part", "long", "ponytail", "bun", "braid", "bald", "bald_sides"),
           "mustache": ("none", "thin", "thick", "handlebar"), "beard": ("none", "stubble", "short", "full"),
           "top_type": ("kurta", "tshirt", "shirt", "hoodie", "sweater", "vest", "blouse", "coat"),
           "sleeves": ("long", "three_quarter", "half", "none"), "length": ("hip", "thigh", "knee"),
           "collar": ("none", "round", "v", "shirt", "hood"), "pattern": ("plain", "stripes", "checks"),
           "proportions": ("toon", "real"), "bottom_type": ("pyjama", "pants", "jeans", "shorts", "dhoti", "lungi", "skirt", "long_skirt"),
           "shoe_type": ("shoes", "sneakers", "chappal", "boots", "barefoot"),
           "accessory": ("glasses", "sunglasses", "cap", "gandhi_topi", "turban", "gamchha", "scarf", "watch", "pens", "bindi",
                         "earrings", "chain", "stethoscope", "nehru_jacket", "lawyer_bands", "kada", "pallu", "comb_scissors",
                         "backpack", "camera"),
           "expression": ("smile", "happy", "neutral", "sad", "angry", "surprised"), "pose": ("rest", "open", "wave", "hips")}

PRESETS = {
    "chubby_uncle": {"gender": "male", "body": {"build": "chubby", "belly": 0.8}, "face": {"chubby": 0.8, "nose": 1.3},
                     "hair": {"style": "short"}, "facial_hair": {"mustache": "thick"},
                     "top": {"type": "kurta", "color": "#f6c445"}, "bottom": {"type": "pyjama", "color": "#f3ecdc"}},
    "slim_young_man": {"gender": "male", "body": {"build": "slim", "height": 1.05}, "hair": {"style": "quiff"},
                       "top": {"type": "tshirt", "color": "#2563eb"}, "bottom": {"type": "jeans", "color": "#2f3e5c"},
                       "shoes": {"type": "sneakers", "color": "#f4f4f2"}},
    "strong_man": {"gender": "male", "body": {"build": "strong", "shoulders": 1.25, "height": 1.08},
                   "facial_hair": {"mustache": "handlebar"}, "top": {"type": "vest", "color": "#f4f2ee", "sleeves": "none"},
                   "bottom": {"type": "dhoti", "color": "#f3ecdc"}, "shoes": {"type": "chappal"}},
    "auntie": {"gender": "female", "body": {"build": "chubby"}, "hair": {"style": "bun"}, "face": {"lips": "#b8524a"},
               "top": {"type": "blouse", "color": "#be185d"}, "bottom": {"type": "long_skirt", "color": "#db2777"},
               "accessories": [{"type": "bindi"}, {"type": "earrings"}, {"type": "pallu", "color": "#db2777"}]},
    "young_woman": {"gender": "female", "body": {"build": "slim"}, "hair": {"style": "ponytail"},
                    "top": {"type": "kurta", "color": "#0d9488", "length": "thigh"}, "bottom": {"type": "pyjama", "color": "#f1e9da"}},
    "grandpa": {"gender": "male", "age": "old", "hair": {"style": "bald_sides", "color": "#e8e6e0"},
                "facial_hair": {"mustache": "thick", "beard": "short", "color": "#e8e6e0"},
                "top": {"type": "kurta", "color": "#f4f2ee"}, "bottom": {"type": "dhoti", "color": "#f4f2ee"},
                "accessories": [{"type": "glasses"}]},
    "grandma": {"gender": "female", "age": "old", "hair": {"style": "bun", "color": "#cfcac2"},
                "top": {"type": "blouse", "color": "#f4f2ee"}, "bottom": {"type": "long_skirt", "color": "#f4f2ee"},
                "accessories": [{"type": "glasses"}]},
    "boy": {"gender": "male", "age": "child", "hair": {"style": "spiky"}, "top": {"type": "tshirt", "color": "#ef4444"},
            "bottom": {"type": "shorts", "color": "#1e3a8a"}, "shoes": {"type": "sneakers"}},
    "girl": {"gender": "female", "age": "child", "hair": {"style": "braid"}, "top": {"type": "kurta", "color": "#f472b6", "length": "thigh"},
             "bottom": {"type": "pyjama", "color": "#fde68a"}, "shoes": {"type": "chappal", "color": "#a16207"}},
}


def _c(v, table, dflt):
    if not v:
        return dflt
    v = str(v)
    return v if v.startswith("#") else table.get(v, dflt)


def _darker(hexc, k=0.75):
    h = str(hexc).lstrip("#")
    if not re.match(r"^[0-9a-fA-F]{6}$", h):              # (not a colour: the checker replaces it; meanwhile grey)
        h = "808080"
    return "#" + "".join(f"{min(255, int(int(h[i:i + 2], 16) * k)):02x}" for i in (0, 2, 4))


def _merge(a, b):
    """b over a, group by group (dicts merge, everything else replaces)"""
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def normalize(card):
    """any card (new or the older story card, with or without a preset) -> the full card with every field filled"""
    c = dict(card or {})
    if c.get("preset") in PRESETS:
        c = _merge(PRESETS[c["preset"]], {k: v for k, v in c.items() if k != "preset"})
    f = dict(c.get("face") or {})
    sx = c.get("sculpt") or {}
    body = dict(c.get("body") or {})
    body.setdefault("height", c.get("height", 1.0))
    body.setdefault("build", c.get("build", "normal"))
    body["build"] = ALIASES["build"].get(str(body["build"]), body["build"])
    if "shape" in f:
        f["shape"] = ALIASES["shape"].get(str(f["shape"]), f["shape"])
    hair = c.get("hair")
    hair = dict(hair) if isinstance(hair, dict) else {"style": hair or "short"}
    hair.setdefault("color", c.get("hair_color"))
    hair["color"] = _c(hair.get("color"), HAIR, "#1b1410")
    fh = dict(c.get("facial_hair") or {})
    if "mustache" not in fh:
        m = c.get("mustache")
        fh["mustache"] = "thick" if m is True else (m if isinstance(m, str) else "none")
    if "beard" not in fh:
        b = c.get("beard")
        fh["beard"] = "short" if b is True else (b if isinstance(b, str) else "none")
    fh["color"] = _c(fh.get("color"), HAIR, hair["color"])
    outfit = str(c.get("outfit", "kurta"))
    top = c.get("top") if isinstance(c.get("top"), dict) else {}
    top = dict({"type": OUTFIT_TOP.get(outfit, "kurta"), "color": c.get("outfit_color", "#f6c445")}, **top)
    top.setdefault("sleeves", {"kurta": "three_quarter", "tshirt": "half", "blouse": "half", "vest": "none"}.get(top["type"], "long"))
    top.setdefault("length", {"kurta": "knee", "coat": "thigh"}.get(top["type"], "hip"))
    top.setdefault("collar", {"hoodie": "hood", "shirt": "shirt", "kurta": "round", "vest": "round", "coat": "v"}.get(top["type"], "round"))
    top.setdefault("pocket", bool(sx.get("pens")) or top["type"] in ("kurta", "shirt"))
    top.setdefault("buttons", top["type"] in ("kurta", "shirt"))
    if top["type"] == "coat":                                   # a coat: open in front over a shirt (color2)
        top.setdefault("inner", c.get("accent", "#f4f2ee"))
    top.setdefault("color2", c.get("accent", _darker(top["color"], 0.8)))
    bottom = c.get("bottom") if isinstance(c.get("bottom"), dict) else {}
    dflt_bottom = {"dhoti": "dhoti", "saree": "long_skirt", "frock": "skirt", "dress": "skirt", "shorts": "shorts",
                   "sadhu": "dhoti", "army": "pants", "police": "pants", "suit": "pants", "uniform": "pants", "pilot": "pants",
                   "chef": "pants", "labcoat": "pants", "royal": "pants", "farmer": "dhoti"}.get(outfit, "pyjama")
    bottom = dict({"type": dflt_bottom, "color": c.get("pants", "#f3ecdc")}, **bottom)
    shoes = c.get("shoes")
    shoes = dict(shoes) if isinstance(shoes, dict) else {"type": "shoes", "color": shoes or "#5a3a22"}
    shoes.setdefault("type", "shoes")
    shoes.setdefault("color", "#f4f4f2" if shoes["type"] == "sneakers" else "#5a3a22")
    acc = [dict(a) for a in (c.get("accessories") or []) if isinstance(a, dict)]
    if sx.get("glasses") or c.get("glasses") is True:
        acc.append({"type": "glasses", "color": sx.get("glasses_color", "#3a2416")})
    if sx.get("pens"):
        acc.append({"type": "pens", "colors": sx["pens"]})
    hat = c.get("hat")
    if hat and hat != "none" and not any(a.get("type") in ("cap", "turban", "gandhi_topi") for a in acc):
        uniform = outfit in ("army", "police", "uniform", "pilot", "firefighter")      # a uniform's cap matches it
        acc.append({"type": {"turban": "turban", "cap": "cap"}.get(hat, "cap"),
                    "color": _darker(top["color"], 0.85) if uniform else c.get("accent", "#c0392b")})
    return {"gender": c.get("gender", "male"), "age": c.get("age", "adult"),
            "skin": _c(c.get("skin"), SKIN, "#c49a72"), "body": body, "face": f, "hair": hair, "facial_hair": fh,
            "top": top, "bottom": bottom, "shoes": shoes, "accessories": acc,
            "expression": c.get("expression", "smile"), "pose": c.get("pose", "rest")}


HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def check(card):
    """-> (the full card, made safe, [what was fixed]) - the notes go back to the AI like the story checker's"""
    c = normalize(card)
    notes = []

    def num(group, key):
        g = c[group]
        if key not in g:
            return
        lo, hi = RANGES[key]
        try:
            v = float(g[key])
        except (TypeError, ValueError):
            notes.append(f"{group}.{key}: '{g[key]}' is not a number - using 1.0")
            g[key] = 1.0 if lo <= 1.0 <= hi else lo
            return
        if not lo <= v <= hi:
            notes.append(f"{group}.{key}: {v} is outside {lo}..{hi} - using {min(hi, max(lo, v))}")
        g[key] = min(hi, max(lo, v))

    def choice(where, key, opts, dflt):
        g = c if where is None else c[where]
        if g.get(key) not in opts:
            if key in g:
                notes.append(f"{(where + '.') if where else ''}{key}: '{g.get(key)}' is not one of {', '.join(opts)} - using '{dflt}'")
            g[key] = dflt

    def colour(where, key, dflt):
        g = c[where]
        v = g.get(key)
        if v is None or v is False:
            return
        if not HEX.match(str(v)):
            notes.append(f"{where}.{key}: '{v}' is not a #rrggbb colour - using {dflt}")
            g[key] = dflt

    for k in ("height", "belly", "head_size", "shoulders", "arm_length", "leg_length", "neck"):
        num("body", k)
    for k in ("chubby", "cheek", "jaw", "chin", "nose", "nose_w", "mouth", "eyes", "eye_spacing", "eye_height", "ears", "brows"):
        num("face", k)
    num("hair", "volume")
    choice(None, "gender", CHOICES["gender"], "male")
    choice(None, "age", CHOICES["age"], "adult")
    choice("body", "build", CHOICES["build"], "normal")
    choice(None, "expression", CHOICES["expression"], "smile")
    choice(None, "pose", CHOICES["pose"], "rest")
    if "shape" in c["face"]:
        choice("face", "shape", CHOICES["shape"], "round")
    if "nose_shape" in c["face"]:
        choice("face", "nose_shape", CHOICES["nose_shape"], "round")
    choice("hair", "style", CHOICES["style"], "short")
    choice("facial_hair", "mustache", CHOICES["mustache"], "none")
    choice("facial_hair", "beard", CHOICES["beard"], "none")
    choice("top", "type", CHOICES["top_type"], "kurta")
    choice("top", "sleeves", CHOICES["sleeves"], "long")
    choice("top", "length", CHOICES["length"], "hip")
    choice("top", "collar", CHOICES["collar"], "round")
    if "pattern" in c["top"]:
        choice("top", "pattern", CHOICES["pattern"], "plain")
    choice("bottom", "type", CHOICES["bottom_type"], "pyjama")
    choice("shoes", "type", CHOICES["shoe_type"], "shoes")
    if not HEX.match(str(c["skin"])):
        notes.append(f"skin: '{c['skin']}' is not a skin word or #rrggbb - using #c49a72")
        c["skin"] = "#c49a72"
    for g, k, d in (("hair", "color", "#1b1410"), ("facial_hair", "color", "#1b1410"), ("top", "color", "#f6c445"),
                    ("top", "color2", "#7a4a2a"), ("top", "pattern_color", "#555555"), ("bottom", "color", "#f3ecdc"),
                    ("shoes", "color", "#5a3a22"), ("shoes", "sole", "#f4f4f2"), ("face", "eye_color", "#4a2c18"),
                    ("face", "lips", "#b8524a"), ("face", "brow_color", "#1b1410"), ("face", "blush", "#d98c74")):
        colour(g, k, d)
    keep = []
    for a in c["accessories"]:
        if a.get("type") in CHOICES["accessory"]:
            keep.append(a)
        else:
            notes.append(f"accessory '{a.get('type')}' is not known ({', '.join(CHOICES['accessory'])}) - left out")
    c["accessories"] = keep
    return c, notes


def _num(d, k, dflt=1.0):
    try:
        v = float(d.get(k, dflt))
    except (TypeError, ValueError):
        return dflt
    lo, hi = RANGES.get(k, (-1e9, 1e9))
    return min(hi, max(lo, v))


def person(card, pose=None, expr=None, jaw=0.0, blink=False):
    """the whole figure from a character card (jaw 0..1 = how open the mouth is for talking; blink = eyes shut)"""
    c, _ = check(card)
    S = Sculpt()
    b, f, top, bot = c["body"], c["face"], c["top"], c["bottom"]
    pose = pose or c["pose"]
    expr = expr or c["expression"]
    female = c["gender"] == "female"
    age = c["age"]
    base_h = {"child": 1.1, "teen": 1.45, "old": 1.55}.get(age, 1.55 if female else 1.62)
    H = base_h * _num(b, "height")
    build = str(b.get("build", "normal"))
    fat = {"slim": 0.0, "normal": 0.25, "strong": 0.35, "chubby": 0.8, "fat": 1.0}.get(build, 0.25)
    fat = max(fat, _num(f, "chubby", 0.0) * 0.9, _num(b, "belly", 0.0))
    strong = 1.0 if build == "strong" else 0.0
    skin = c["skin"]
    hairc = c["hair"]["color"]
    tc, tc2 = top["color"], top["color2"]
    pc = bot["color"]
    head_k = {"child": 1.35, "teen": 1.12}.get(age, 1.0) * _num(b, "head_size")
    legk = _num(b, "leg_length")

    # ---- proportions (toon: the head about a quarter of the height; "proportions": "real" - a film hero / heroine:
    # the head about a seventh, long legs, a slim waist, slender arms and legs)
    real = str(b.get("proportions", "toon")).lower() in ("real", "realistic", "heroine", "hero", "model", "tall")
    lk = 0.66 if real else 1.0                              # limb thickness
    if real:
        hip_y = 0.49 * H * legk
        sh_y = hip_y + 0.31 * H
        R = 0.074 * H * head_k * (1.0 + 0.05 * fat)
        head_y = sh_y + 0.07 * H * _num(b, "neck") + 0.9 * R
        sw = (0.118 + 0.02 * fat + 0.025 * strong - (0.012 if female else 0.0)) * H * _num(b, "shoulders")
        belly = (0.068 + 0.06 * fat + (0.014 if not female else 0.0)) * H
        hips = belly * (1.45 if female else 1.1)
    else:
        hip_y = 0.40 * H * legk
        sh_y = hip_y + 0.30 * H
        R = 0.118 * H * head_k * (1.0 + 0.05 * fat)
        head_y = max(hip_y + 0.45 * H, sh_y + 0.75 * R) + 0.04 * H * (_num(b, "neck") - 1.0)
        sw = (0.155 + 0.03 * fat + 0.03 * strong - (0.02 if female else 0.0)) * H * _num(b, "shoulders")
        belly = (0.15 + 0.07 * fat) * H
        if female and fat < 0.5:                            # a woman's figure: a narrower waist, the hips wider than it
            belly *= 0.8 + 0.3 * fat
        hips = belly * (1.22 if female and fat < 0.5 else 1.08 if female else 1.0)

    # ---- legs and feet
    ftype = c["shoes"]["type"]
    for s in (-1, 1):
        lx = 0.72 if real else 1.0                          # (slim legs stand closer together)
        hipp, knee, ank = (s * 0.075 * H * lx, hip_y, 0.0), (s * 0.08 * H * lx, hip_y * 0.52, 0.012 * H), \
            (s * 0.08 * H * lx, 0.055 * H, 0.0)
        lr = [0.075 * H * (1 + 0.2 * fat) * lk, 0.058 * H * (1 + 0.15 * fat) * lk, 0.045 * H * lk]
        side = "l" if s < 0 else "r"
        S.joints.update({side + "_hip": np.array(hipp), side + "_knee": np.array(knee), side + "_ankle": np.array(ank)})
        thigh, shin = side + "_thigh", side + "_shin"
        if bot["type"] == "shorts":
            S.capsule(hipp, knee, lr[0] * 1.08, lr[1] * 1.15, pc, k=0.03, gloss=0.06, bone=thigh)
            S.capsule(knee, ank, lr[1] * 0.85, lr[2] * 0.85, skin, k=0.02, gloss=0.18, bone=shin)
        elif bot["type"] in ("dhoti", "lungi"):
            S.capsule(hipp, knee, lr[0] * 1.2, lr[1] * 1.22, pc, k=0.05, gloss=0.05, bone=thigh)
            S.capsule(knee, (s * 0.085 * H, 0.09 * H, 0.0), lr[1] * 1.22, lr[1] * 1.25, pc, k=0.05, gloss=0.05, bone=shin)
            S.capsule((s * 0.08 * H, 0.1 * H, 0), ank, lr[2] * 0.85, lr[2] * 0.8, skin, k=0.02, gloss=0.18, bone=shin)
        elif bot["type"] in ("skirt", "long_skirt"):
            S.capsule(knee, ank, lr[1] * 0.85, lr[2] * 0.85, skin, k=0.02, gloss=0.18, bone=shin)
        else:
            S.capsule(hipp, knee, lr[0], lr[1], pc, k=0.03, gloss=0.12 if bot["type"] == "jeans" else 0.05, bone=thigh)
            S.capsule(knee, ank, lr[1], lr[2], pc, k=0.03, gloss=0.12 if bot["type"] == "jeans" else 0.05, bone=shin)
        S.bone = shin
        fc = c["shoes"].get("color", "#5a3a22")
        foot = (s * 0.082 * H * lx, 0.03 * H, 0.03 * H)
        if ftype in ("barefoot", "chappal"):
            S.ellipsoid((foot[0], 0.022 * H, foot[2]), (0.042 * H, 0.022 * H, 0.08 * H), skin, k=0.02, gloss=0.18)
            if ftype == "chappal":
                S.ellipsoid((foot[0], 0.004 * H, foot[2]), (0.05 * H, 0.006 * H, 0.09 * H), fc, k=0.0, group="shoes")
        else:
            S.ellipsoid(foot, (0.05 * H * lx, 0.032 * H * lx, 0.085 * H * (0.85 if real else 1.0)), fc, k=0.02, gloss=0.35)
            if ftype == "boots":
                S.capsule(ank, (ank[0], 0.13 * H, 0.0), 0.05 * H, 0.05 * H, fc, k=0.02, gloss=0.3)
            if ftype == "sneakers":
                sole = c["shoes"].get("sole", "#f4f4f2")
                S.paint(lambda P, x=foot[0]: np.maximum(P[:, 1] - 0.012 * H, np.abs(P[:, 0] - x) - 0.07 * H), sole, soft=0.002)
    S.bone = "spine"
    if bot["type"] in ("skirt", "long_skirt", "lungi"):
        # a skirt / saree / lungi: the cloth hangs round EACH leg - a wide piece on the thigh and one on the shin, that
        # melt into one smooth skirt standing, and bend with the legs sitting / walking / being carried (a stiff cone
        # stuck straight out). The hem is cut flat above the ankles, so the feet show.
        low = {"skirt": 0.24 * H, "long_skirt": 0.075 * H, "lungi": 0.08 * H}[bot["type"]]
        S.capsule((0, hip_y + 0.03 * H, 0), (0, hip_y - 0.05 * H, 0), hips * 0.82, hips * 0.9, pc, k=0.06, gloss=0.06)
        hem_cut = (lambda P, low=low: low - P[:, 1])
        for s in (-1, 1):
            side = "l" if s < 0 else "r"
            hipp, knee = S.joints[side + "_hip"], S.joints[side + "_knee"]
            r0, r1, r2 = hips * 0.62, hips * 0.66, hips * (0.7 if bot["type"] == "long_skirt" else 0.62)
            S.capsule(hipp + np.array([s * 0.01 * H, 0.0, 0.0]), knee, r0, r1, pc, k=0.07, gloss=0.06, bone=side + "_thigh",
                      clip=hem_cut)
            if low < knee[1] - 0.02 * H:
                S.capsule(knee, (knee[0] + s * 0.012 * H, low, 0.0), r1, r2, pc, k=0.07, gloss=0.06, bone=side + "_shin",
                          clip=hem_cut)

    # ---- body: the top covers chest and belly
    if real:                                                # a slim torso: chest, a narrow waist, the hips
        S.ellipsoid((0, hip_y + 0.13 * H, 0.0), (belly, 0.15 * H, belly * 0.85), tc, k=0.08, gloss=0.08)
        S.ellipsoid((0, sh_y - 0.07 * H, 0.0), (sw * 0.85, 0.1 * H, 0.068 * H), tc, k=0.08, gloss=0.08)
        if female:
            for s in (-1, 1):
                S.sphere((s * 0.042 * H, sh_y - 0.095 * H, 0.04 * H + 0.02 * H * fat), 0.042 * H, tc, k=0.04, gloss=0.08)
    else:
        S.ellipsoid((0, hip_y + 0.16 * H, 0.02 * H * (1 + fat)), (belly * 1.0, 0.18 * H, belly * 0.92), tc, k=0.12, gloss=0.08)
        S.ellipsoid((0, hip_y + 0.25 * H, -0.03 * H), (sw * 0.98, 0.085 * H, 0.09 * H), tc, k=0.1, gloss=0.08)
        if female:
            for s in (-1, 1):
                S.sphere((s * 0.05 * H, hip_y + 0.235 * H, 0.06 * H + 0.02 * H * fat), 0.05 * H, tc, k=0.05, gloss=0.08)
    hem = {"hip": hip_y - 0.01 * H, "thigh": hip_y - 0.07 * H, "knee": hip_y - 0.13 * H}.get(top.get("length"), hip_y)
    if hem < hip_y - 0.02 * H:                              # a long top (kurta): it flares a little to the hem
        S.capsule((0, hip_y + 0.03 * H, 0.01 * H), (0, hem, 0.0), belly * 0.78, belly * 0.72 + 0.015 * H, tc, k=0.07, gloss=0.08)
    elif bot["type"] not in ("skirt", "long_skirt", "lungi"):
        S.capsule((0, hip_y + 0.05 * H, 0.01 * H), (0, hip_y - 0.02 * H, 0.0), hips * 0.92, hips * 0.88, pc, k=0.05, gloss=0.06)
    S.paint(lambda P: np.abs(P[:, 1] - hem) - 0.006 * H, _darker(tc, 0.8), soft=0.002)      # the hem
    for s in (-1, 1):                                       # round shoulders
        S.sphere((s * sw, sh_y - 0.012 * H, -0.005 * H), 0.062 * H * (1 + 0.15 * fat + 0.25 * strong) * (0.62 if real else 1.0),
                 tc, k=0.05, gloss=0.08)
    pat = top.get("pattern", "plain")
    if pat in ("stripes", "checks"):
        pcol = top.get("pattern_color", _darker(tc, 0.75))
        if pat == "stripes":
            S.paint(lambda P: np.abs(((P[:, 1] / (0.035 * H)) % 1.0) - 0.5) * 0.035 * H - 0.008 * H, pcol, soft=0.0015)
        else:
            S.paint(lambda P: np.minimum(np.abs(((P[:, 1] / (0.04 * H)) % 1.0) - 0.5), np.abs(((P[:, 0] / (0.04 * H)) % 1.0) - 0.5))
                    * 0.04 * H - 0.004 * H, pcol, soft=0.0015)
    if top.get("buttons"):
        S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) - 0.012 * H, -P[:, 2]),          # the placket (front)
                                     np.maximum(P[:, 1] - sh_y, hip_y + 0.16 * H - P[:, 1])), _darker(tc, 0.85), soft=0.002)
        for i in range(3):
            S.sphere((0.0, sh_y - (0.035 + 0.035 * i) * H, 0.122 * H + 0.012 * H * i * fat), 0.007 * H, tc2, k=0.004, gloss=0.5)
    if top.get("pocket"):
        S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0] - 0.08 * H) - 0.035 * H, np.abs(P[:, 1] - (sh_y - 0.075 * H)) - 0.035 * H),
                                     -P[:, 2]), _darker(tc, 0.88), soft=0.002)
    col = top.get("collar")
    nk = np.array([0, sh_y + 0.005 * H, 0.0])
    if col == "hood":                                       # a hood lying round the back of the neck, drawstrings
        S.torus(nk + np.array([0, 0.0, -0.02 * H]), 0.075 * H, 0.03 * H, tc2, axis=(0, 1, 0.35), k=0.02, gloss=0.08)
        for s in (-1, 1):
            S.capsule((s * 0.03 * H, sh_y - 0.01 * H, 0.1 * H), (s * 0.033 * H, sh_y - 0.1 * H, 0.13 * H + 0.02 * H * fat),
                      0.004 * H, 0.004 * H, "#f4f2ee", group="props", k=0.0, gloss=0.3)
        box = lambda P: np.maximum(np.abs(P[:, 0]) - 0.1 * H, np.abs(P[:, 1] - (hip_y + 0.08 * H)) - 0.045 * H)
        S.paint(lambda P: np.maximum(np.abs(box(P)) - 0.0035 * H, -P[:, 2]), tc2, soft=0.0015)   # kangaroo pocket: its seam
    elif col == "v" and top["type"] == "coat":                # an open coat: the shirt in a V, lapels, the front edge
        inner = top.get("inner", "#f4f2ee")
        S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) * 2.2 - (P[:, 1] - (hip_y + 0.12 * H)), -P[:, 2]),
                                     P[:, 1] - (sh_y + 0.01 * H)), inner, soft=0.002)
        S.paint(lambda P: np.maximum(np.abs(np.abs(P[:, 0]) * 2.2 - (P[:, 1] - (hip_y + 0.12 * H))) - 0.012 * H,
                                     np.maximum(-P[:, 2], P[:, 1] - sh_y)), _darker(tc, 0.7), soft=0.002)
        S.paint(lambda P: np.maximum(np.abs(P[:, 0]) - 0.004 * H, np.maximum(-P[:, 2], P[:, 1] - (hip_y + 0.12 * H))),
                _darker(tc, 0.7), soft=0.0015)
    elif col == "v":
        S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) * 1.6 - (P[:, 1] - (sh_y - 0.09 * H)), -P[:, 2]),
                                     P[:, 1] - (sh_y + 0.03 * H)), skin, soft=0.002)        # (the V stops at the neck)
    elif col == "shirt":
        for s in (-1, 1):
            S.ellipsoid((s * 0.045 * H, sh_y + 0.005 * H, 0.06 * H), (0.04 * H, 0.012 * H, 0.03 * H), tc, k=0.01, gloss=0.08)
    elif col == "round":
        S.torus(nk, 0.058 * H, 0.008 * H, _darker(tc, 0.85), axis=(0, 1, 0.2), k=0.01, gloss=0.08)

    # ---- arms (sleeves as long as the card says), hands - their own parts: an arm follows only the arm's bones (made
    # hanging by the hips, a shared mesh pulled the hand back to the hip when the arm lifted: stretched "squid" hands),
    # and the hands are meshed finer (crisp fingers)
    S.group = "arms"
    sleeve = top.get("sleeves", "long")
    armk = _num(b, "arm_length")
    for s in (-1, 1):
        sh = np.array([s * (sw + 0.012 * H), sh_y - 0.03 * H, -0.01 * H])
        ra = 0.048 * H * (1 + 0.35 * fat + 0.4 * strong) * (0.85 if female else 1.0) * (0.62 if real else 1.0)
        up = pose == "wave" and s > 0
        if pose == "open":
            el = sh + np.array([s * 0.06 * H, -0.15 * H * armk, 0.0])
            wr = el + np.array([s * 0.11 * H, -0.01 * H, 0.08 * H]) * armk
        elif up:
            el = sh + np.array([s * 0.1 * H, -0.06 * H, 0.02 * H]) * armk
            wr = el + np.array([s * 0.03 * H, 0.14 * H, 0.02 * H]) * armk
        elif pose == "hips":
            el = sh + np.array([s * 0.12 * H, -0.12 * H * armk, -0.02 * H])
            wr = np.array([s * (hips + 0.01 * H), hip_y + 0.07 * H, 0.0])
        else:
            el = np.array([s * (sw + (0.05 * H + 0.03 * H * fat) * (0.4 if real else 1.0)), sh_y - 0.18 * H * armk * (1.08 if real else 1.0), 0.0])
            wr = el + np.array([s * 0.005 * H, -0.11 * H * armk * (1.35 if real else 1.0), 0.025 * H])
        side = "l" if s < 0 else "r"
        S.joints.update({side + "_shoulder": sh, side + "_elbow": el, side + "_wrist": wr})
        cut = {"none": 0.0, "half": 0.55, "three_quarter": 1.3, "long": 2.0}.get(sleeve, 2.0)
        S.bone = side + "_upper_arm"
        if cut > 0:                                         # cut = how far the sleeve goes (1 = the elbow, 2 = the wrist)
            end = sh + (el - sh) * cut if cut <= 1 else el + (wr - el) * (cut - 1.0)
            S.capsule(sh, el if cut > 1 else end, ra, ra * 0.92, tc, k=0.03, gloss=0.08)
            if cut > 1:
                S.capsule(el, end, ra * 0.92, ra * 0.86, tc, k=0.02, gloss=0.08, bone=side + "_forearm")
        S.capsule(sh, el, ra * 0.85, ra * 0.78, skin, k=0.02, gloss=0.18)
        S.bone = side + "_forearm"
        S.capsule(el, wr, ra * 0.8, ra * 0.62, skin, k=0.02, gloss=0.18)
        Hh = H * (0.8 if real else 1.0)                    # (slender hands for the real proportions)
        S.group = "hands"
        out = (wr - el) / np.linalg.norm(wr - el)
        if pose == "open" or up:                            # a flat open hand, fingers out, thumb forward
            hand = wr + out * 0.035 * Hh + np.array([0, 0.004 * Hh, 0])
            S.ellipsoid(hand, (0.04 * Hh, 0.016 * Hh, 0.036 * Hh) if not up else (0.034 * Hh, 0.04 * Hh, 0.016 * Hh), skin, k=0.02, gloss=0.18)
            side = np.array([0, 0, 1.0]) if not up else np.array([1.0, 0, 0])
            for j, dz in enumerate((-0.024, -0.008, 0.008, 0.022)):
                base = hand + out * 0.03 * Hh + side * dz * Hh
                S.capsule(base, base + out * (0.034 - 0.004 * abs(j - 1.5)) * Hh, 0.0085 * Hh, 0.0075 * Hh, skin, k=0.006, gloss=0.18)
            S.capsule(hand + side * 0.03 * Hh, hand + out * 0.015 * Hh + side * 0.055 * Hh + np.array([0, 0.012 * Hh, 0]),
                      0.011 * Hh, 0.009 * Hh, skin, k=0.01, gloss=0.18)                       # thumb
        else:                                               # a relaxed round hand with a thumb
            hand = wr + out * 0.045 * Hh
            S.ellipsoid(hand, (0.03 * Hh, 0.045 * Hh, 0.038 * Hh), skin, k=0.02, gloss=0.18)
            S.capsule(hand + np.array([0, 0.005 * Hh, 0.03 * Hh]), hand + np.array([-s * 0.006 * Hh, -0.02 * Hh, 0.05 * Hh]),
                      0.013 * Hh, 0.011 * Hh, skin, k=0.012, gloss=0.18)
            for j, dz in enumerate((-0.021, -0.007, 0.007, 0.02)):     # four fingers, a little curled in toward the body
                ln_ = (0.036 - 0.006 * abs(j - 1.5)) * Hh
                base = hand + out * 0.028 * Hh + np.array([0, 0, dz * Hh + 0.008 * Hh])
                mid = base + out * ln_ * 0.6
                S.capsule(base, mid, 0.0095 * Hh, 0.0088 * Hh, skin, k=0.006, gloss=0.18)
                S.capsule(mid, mid + out * ln_ * 0.45 + np.array([-s * 0.008 * Hh, 0, 0.003 * Hh]), 0.0088 * Hh, 0.0075 * Hh,
                          skin, k=0.004, gloss=0.18)

    S.group = "body"
    # ---- neck and head
    S.bone = "spine"
    S.capsule((0, sh_y - 0.02 * H, 0), (0, head_y - (0.5 * R if real else 0.06 * H), 0.01 * H), 0.05 * H * (1 + 0.3 * fat) * lk * 0.85,
              0.055 * H * lk * 0.85, skin, k=0.04 * lk)
    hc = np.array([0.0, head_y, 0.0])
    S.joints.update({"front": (belly * 0.85 + 0.012 * H) if real else (0.12 * H + 0.03 * H * fat),   # the chest's front
                     "slim": 0.6 if real else 1.0})
    S.joints.update({"pelvis": np.array([0, hip_y, 0.0]), "chest": np.array([0, sh_y, 0.0]), "head": hc,
                     "neck_cut": sh_y + 0.35 * (head_y - sh_y), "top": head_y + R, "R": R, "H": H})
    i_head, R_real = len(S.shapes), R
    if real:          # the face is made at the toon size (its blends and details are tuned for it), then shrunk as one
        R = 0.118 * H * head_k * (1.0 + 0.05 * fat)
    S.bone = "head"
    shape = f.get("shape", "round")
    hr = {"round": (0.98, 1.0, 0.97), "oval": (0.9, 1.06, 0.95), "square": (1.0, 0.98, 0.95), "long": (0.86, 1.12, 0.93)}.get(shape, (0.98, 1.0, 0.97))
    S.ellipsoid(hc, np.array(hr) * R, skin, k=0.02, gloss=0.2)
    cheek = 1.0 + 0.25 * (_num(f, "cheek") - 1.0)
    for s in (-1, 1):                                       # cheeks and a soft jaw
        S.sphere(hc + np.array([s * 0.5 * R, -0.3 * R, 0.42 * R]), 0.4 * R * cheek * (1 + 0.1 * fat) * (0.85 if female else 1.0),
                 skin, k=0.08, gloss=0.2)
    jaw_w = _num(f, "jaw") * (1.15 if shape == "square" else 1.0)     # the jaw's width (not "jaw": how open the mouth is)
    S.ellipsoid(hc + np.array([0, -0.6 * R, 0.35 * R]), (0.48 * R * jaw_w, 0.36 * R * _num(f, "chin"), 0.5 * R), skin, k=0.08, gloss=0.2)
    nose, nose_w = _num(f, "nose") * (0.8 if female else 1.0), _num(f, "nose_w")
    ns = f.get("nose_shape", "round")
    nc = hc + np.array([0, -0.12 * R, 0.98 * R])
    if ns == "pointed":
        S.capsule(hc + np.array([0, 0.15 * R, 0.85 * R]), nc + np.array([0, -0.02 * R, 0.12 * R * nose]), 0.08 * R, 0.07 * R * nose_w, skin, k=0.05)
    else:
        k_ = 0.75 if ns == "button" else 1.0
        S.ellipsoid(nc, (0.2 * R * nose_w * k_, 0.2 * R * nose * k_, 0.2 * R * nose * k_), skin, k=0.05, gloss=0.3)
        S.capsule(hc + np.array([0, 0.18 * R, 0.86 * R]), nc + np.array([0, 0.05 * R, -0.02 * R]), 0.08 * R, 0.13 * R * k_, skin, k=0.06)
    ears = _num(f, "ears")
    for s in (-1, 1):
        S.ellipsoid(hc + np.array([s * 0.97 * R * hr[0], 0.0, -0.05 * R]), (0.12 * R, 0.27 * R * ears, 0.2 * R * ears), skin, k=0.02)
        S.paint_ball(hc + np.array([s * 1.05 * R * hr[0], 0.0, -0.02 * R]), 0.11 * R, _darker(skin, 0.85), soft=0.006)
    blush = f.get("blush", "#d98c74")
    if blush:
        for s in (-1, 1):
            S.paint_ball(hc + np.array([s * 0.55 * R, -0.33 * R, 0.85 * R]), 0.22 * R, blush, soft=0.03)

    _hair(S, c, hc, R, hairc, female)

    # ---- eyes
    eyes = _num(f, "eyes") * (1.12 if age == "child" else 1.0)
    er = 0.19 * R * eyes
    gaze = np.array([0.0, -0.05, 1.0])
    eye_col = f.get("eye_color", "#4a2c18")
    spacing, eh = _num(f, "eye_spacing"), _num(f, "eye_height")
    lid_cut = {"surprised": -0.95, "angry": -0.45, "sad": -0.55, "happy": -0.6, "sleeping": 1.2}.get(expr, -0.75)
    if blink:
        lid_cut = 1.2                                       # the lids meet: eyes shut
    browc = f.get("brow_color", hairc)
    lid_n = np.array([0, -1, 0.35]) / np.linalg.norm([0, -1, 0.35])
    for s in (-1, 1):
        ec = hc + np.array([s * 0.36 * R * spacing, 0.14 * R * eh, 0.8 * R])
        S.sphere(ec, er, "#fbfaf6", group="eyes", k=0.0, gloss=0.9)
        S.paint_cone(ec, gaze + np.array([-s * 0.04, 0, 0]), 38, eye_col, group="eyes", soft=0.0012)
        S.paint_cone(ec, gaze + np.array([-s * 0.04, 0, 0]), 18, "#0b0705", group="eyes", soft=0.001)
        S.paint_cone(ec, gaze + np.array([0.28, 0.32, 0]), 8, "#ffffff", group="eyes", soft=0.0008, gloss=1.0)    # catchlight
        S._add(lambda P, ec=ec: _sd_ellipsoid(P, ec, np.array([1.1, 1.1, 1.1]) * er), skin, k=0.0, group="lids",
               gloss=0.2, clip=lambda P, ec=ec: (P - ec) @ lid_n - lid_cut * er)
        lw = 0.022 * R if (female or f.get("lashes")) else 0.012 * R
        S.paint(lambda P, ec=ec: np.abs((P - ec) @ lid_n - lid_cut * er) - lw,
                _darker(skin, 0.45 if lw > 0.015 * R else 0.6), soft=0.002, group="lids")   # lash line
        bc = ec + np.array([0, 0.4 * R + 0.05 * R * (expr == "surprised"), 0.06 * R])
        tilt = {"angry": -0.09, "sad": 0.07}.get(expr, 0.0)
        S.tube([bc + np.array([-s * 0.2 * R, -0.04 * R + tilt * R, 0.0]), bc + np.array([0, 0.04 * R, 0.0]),
                bc + np.array([s * 0.22 * R, -0.03 * R - tilt * R, -0.06 * R])],
               0.045 * R * _num(f, "brows") * (0.75 if female else 1.0), browc, group="brows", k=0.0, gloss=0.2)

    _mouth(S, f, hc, R, expr, female, jaw)
    _facial_hair(S, c, hc, R)
    on_head = ("glasses", "sunglasses", "cap", "gandhi_topi", "turban", "bindi", "earrings")
    for a in c["accessories"]:
        if a.get("type") in on_head:
            S.bone = "head"
            _accessory(S, a, hc, R, H, er, sh_y, hip_y, sw, fat, f)
    if R != R_real:
        _shrink(S.shapes[i_head:], hc, R_real / R)
        S.color_tau = 0.0025 * R_real / R
        R = R_real
    for a in c["accessories"]:
        if a.get("type") not in on_head:
            S.bone = "l_forearm" if a.get("type") == "watch" else "spine"
            _accessory(S, a, hc, R, H, er, sh_y, hip_y, sw, fat, f)
    S.no_shadow = {"glasses", "brows", "props", "eyes", "lids", "mustache", "mouth", "shoes", "hat"}
    S.res.update({"mouth": 0.0025, "eyes": 0.0018, "lids": 0.0022, "glasses": 0.002, "brows": 0.0025, "mustache": 0.003,
                  "props": 0.002, "shoes": 0.003, "hat": 0.004})
    return S


def _shrink(shapes, c, k):
    """scale shapes about the point c by k (the distance functions, their boxes, blends and paint edges)"""
    c = np.asarray(c, float)
    for x in shapes:
        f = x.fn
        x.fn = (lambda P, f=f: f(c + (P - c) / k) * k)
        if x.clip is not None:
            cl = x.clip
            x.clip = (lambda P, cl=cl: cl(c + (P - c) / k) * k)
        if x.box is not None:
            x.box = (c + (np.asarray(x.box[0]) - c) * k, c + (np.asarray(x.box[1]) - c) * k)
        x.k = x.k * k


def _hair(S, c, hc, R, hairc, female):
    style = c["hair"].get("style", "short")
    vol = _num(c["hair"], "volume")
    if style == "bald":
        return
    if style == "bald_sides":                               # a fringe round the back only
        S._add(lambda P: _sd_ellipsoid(P, hc + np.array([0, -0.05 * R, -0.08 * R]), np.array([1.04, 0.75, 1.02]) * R),
               hairc, k=0.01, gloss=0.25, clip=lambda P: _sd_plane(P - hc, (0, 0.3, 1.0), -0.25 * R))
        return
    cap = lambda P: _sd_plane(P - hc, (0, -1.0, 0.75), -0.18 * R)              # keep the top and back of the head
    S._add(lambda P: _sd_ellipsoid(P, hc + np.array([0, 0.06 * R, -0.04 * R]), np.array([1.04, 1.0, 1.04]) * R * (1 + 0.03 * (vol - 1))),
           hairc, k=0.01, gloss=0.25, clip=cap)
    S._add(lambda P: _sd_ellipsoid(P, hc + np.array([0, 0.35 * R, 0.0]), np.array([0.98, 0.72, 1.0]) * R * vol), hairc,
           k=0.04, gloss=0.25, clip=lambda P: _sd_plane(P - hc, (0, -1, 0.8), -0.42 * R))
    if style in ("quiff", "short", "side_part"):
        S.ellipsoid(hc + np.array([0.08 * R, 0.78 * R, 0.55 * R]), (0.5 * R, 0.24 * R * vol, 0.32 * R), hairc, k=0.06, gloss=0.25)
        S.ellipsoid(hc + np.array([-0.25 * R, 0.82 * R, 0.4 * R]), (0.35 * R, 0.2 * R * vol, 0.3 * R), hairc, k=0.06, gloss=0.25)
        if style == "quiff":
            S.ellipsoid(hc + np.array([0.1 * R, 0.98 * R, 0.6 * R]), (0.42 * R, 0.22 * R * vol, 0.28 * R), hairc, k=0.07, gloss=0.25)
    elif style == "spiky":
        for i in range(7):
            a = -1.1 + i * 0.37
            base = hc + np.array([np.sin(a) * 0.6 * R, 0.75 * R, np.cos(a) * 0.3 * R])
            S.capsule(base, base + np.array([np.sin(a) * 0.25 * R, 0.4 * R * vol, 0.15 * R]), 0.16 * R, 0.02 * R, hairc, k=0.05, gloss=0.25)
    elif style == "curly":
        rng = np.random.default_rng(7)
        for _ in range(26):
            v = rng.normal(size=3)
            v[1] = abs(v[1]) + 0.25
            v[2] = v[2] - 0.2 if v[2] > 0.6 else v[2]
            v /= np.linalg.norm(v)
            S.sphere(hc + v * 1.0 * R + np.array([0, 0.08 * R, -0.05 * R]), 0.22 * R * vol, hairc, k=0.05, gloss=0.2)
    if style in ("long", "ponytail", "bun", "braid") or (female and style == "short"):
        S.ellipsoid(hc + np.array([0, -0.15 * R, -0.35 * R]), (1.02 * R, 1.0 * R, 0.75 * R), hairc, k=0.06, gloss=0.3)
        if style == "long":
            S.capsule(hc + np.array([0, -0.4 * R, -0.45 * R]), hc + np.array([0, -1.6 * R, -0.5 * R]), 0.85 * R, 0.7 * R, hairc,
                      k=0.08, gloss=0.3)
            # a side-swept fringe over the forehead and two locks framing the face down past the shoulders
            S.ellipsoid(hc + np.array([0.18 * R, 0.6 * R, 0.6 * R]), (0.78 * R, 0.3 * R * vol, 0.42 * R), hairc, k=0.07, gloss=0.3)
            S.ellipsoid(hc + np.array([-0.55 * R, 0.45 * R, 0.55 * R]), (0.4 * R, 0.32 * R * vol, 0.36 * R), hairc, k=0.07,
                        gloss=0.3)
            for s_ in (-1, 1):
                S.capsule(hc + np.array([s_ * 0.88 * R, 0.35 * R, 0.25 * R]), hc + np.array([s_ * 0.95 * R, -1.7 * R, 0.1 * R]),
                          0.3 * R * vol, 0.24 * R * vol, hairc, k=0.06, gloss=0.3)
        elif style == "ponytail":
            S.capsule(hc + np.array([0, 0.2 * R, -1.0 * R]), hc + np.array([0, -1.3 * R, -1.25 * R]), 0.26 * R, 0.12 * R, hairc,
                      k=0.05, gloss=0.3)
        elif style == "bun":
            S.sphere(hc + np.array([0, 0.45 * R, -0.95 * R]), 0.38 * R, hairc, k=0.05, gloss=0.3)
        elif style == "braid":
            for i in range(6):
                S.sphere(hc + np.array([0, -0.4 * R - i * 0.28 * R, -1.0 * R - 0.05 * R * i]), 0.2 * R - 0.012 * R * i, hairc,
                         k=0.03, gloss=0.3)
    for s in (-1, 1):                                       # sideburns
        S.ellipsoid(hc + np.array([s * 0.9 * R, 0.12 * R, 0.08 * R]), (0.1 * R, 0.25 * R, 0.14 * R), hairc, k=0.02, gloss=0.2)


def _mouth(S, f, hc, R, expr, female, jaw=0.0):
    mouth = _num(f, "mouth")
    lips = f.get("lips", "#b8524a" if female else None)
    mc = hc + np.array([0, -0.58 * R, 0.86 * R])
    jaw = max(0.0, min(1.0, float(jaw or 0.0)))
    if jaw > 0.12 and expr not in ("smile", "surprised"):  # talking: the mouth opens as the voice says
        expr = "talk"
    if expr in ("smile", "surprised", "talk"):              # open: a carved D (smile) or O (surprised / talking)
        if expr == "smile":
            mr = np.array([0.3 * R * mouth, 0.2 * R * (0.75 + 0.5 * jaw), 0.3 * R])
            flat = lambda P: _sd_plane(P - mc, (0, 1, 0.25), 0.02 * R)
        elif expr == "talk":
            mr = np.array([0.2 * R * mouth, (0.05 + 0.17 * jaw) * R, 0.25 * R])
            flat = lambda P: P[:, 0] * 0 - 1.0
        else:
            mr = np.array([0.14 * R * mouth, 0.18 * R, 0.25 * R])
            flat = lambda P: P[:, 0] * 0 - 1.0
        S._add(lambda P: np.maximum(_sd_ellipsoid(P, mc, mr), flat(P)), "#000000", k=0.025, mode="sub")
        inside = lambda P: np.maximum(_sd_ellipsoid(P, mc, mr * 1.04), flat(P) - 0.01 * R)
        S.paint(inside, "#5a1a16", soft=0.003)
        if expr == "smile":
            S.paint(lambda P: np.maximum(inside(P), -((P - mc) @ np.array([0, 1, 0.25]) / 1.03 + 0.06 * R)), "#fbf6ee",
                    soft=0.002, gloss=0.5)                  # teeth
        S.ellipsoid(mc + np.array([0, -mr[1] * 0.6, -0.08 * R]), (0.2 * R * min(1, mr[0] / (0.3 * R)), min(0.08 * R, mr[1] * 0.4), 0.18 * R),
                    "#d9666a", group="mouth", k=0.0, gloss=0.5)                     # tongue
        if lips:
            S.paint(lambda P: np.abs(_sd_ellipsoid(P, mc, mr * 1.12)) - 0.03 * R, lips, soft=0.004)
        return
    curve = {"happy": 0.16, "neutral": 0.02, "sad": -0.12, "angry": -0.08}.get(expr, 0.1)
    w = {"happy": 0.34, "neutral": 0.2, "sad": 0.22, "angry": 0.2}.get(expr, 0.28) * mouth
    pts = [hc + np.array([x * w * R, -0.6 * R + curve * R * (x * x), 0.82 * R + 0.06 * R * (1 - x * x)])
           for x in np.linspace(-1, 1, 7)]
    S.paint_line(pts, 0.025 * R if not lips else 0.04 * R, lips or "#5a2418", soft=0.002)


def _facial_hair(S, c, hc, R):
    fh = c["facial_hair"]
    col = fh.get("color", c["hair"]["color"])
    m = fh.get("mustache", "none")
    if m and m != "none":
        th = {"thin": 0.035, "thick": 0.07, "handlebar": 0.06}.get(m, 0.06) * R
        for s in (-1, 1):
            tip = hc + np.array([s * 0.4 * R, -0.3 * R, 0.86 * R])
            if m == "handlebar":
                tip = hc + np.array([s * 0.55 * R, -0.16 * R, 0.8 * R])
            S.tube([hc + np.array([s * 0.03 * R, -0.3 * R, 1.04 * R]), hc + np.array([s * 0.22 * R, -0.35 * R, 0.98 * R]), tip],
                   th, col, group="mustache", k=0.0, gloss=0.25)
            if m != "thin":
                S.sphere(hc + np.array([s * 0.13 * R, -0.32 * R, 1.02 * R]), th * 1.45, col, group="mustache", k=0.06, gloss=0.25)
    bd = fh.get("beard", "none")
    if bd == "stubble":
        S.paint(lambda P: np.maximum(np.linalg.norm((P - (hc + np.array([0, -0.55 * R, 0.4 * R]))) / np.array([0.75, 0.45, 0.8]), axis=1)
                                     - 0.75 * R, -(P[:, 2] - hc[2])), _darker(col, 1.6), soft=0.01)
    elif bd in ("short", "full"):
        big = 1.0 if bd == "full" else 0.7
        below = lambda P: _sd_plane(P - hc, (0, 1, -0.15), -0.66 * R)            # under the mouth line
        S._add(lambda P: _sd_ellipsoid(P, hc + np.array([0, -0.62 * R, 0.38 * R]), np.array([0.66, 0.42 + 0.25 * big, 0.62]) * R),
               col, k=0.05, gloss=0.2, clip=below)
        for s_ in (-1, 1):                                                       # along the jaw to the ears
            S._add(lambda P, s_=s_: _sd_ellipsoid(P, hc + np.array([s_ * 0.62 * R, -0.35 * R, 0.25 * R]), np.array([0.3, 0.42, 0.45]) * R),
                   col, k=0.05, gloss=0.2, clip=lambda P: _sd_plane(P - hc, (0, 1, 0), -0.12 * R))


def _accessory(S, a, hc, R, H, er, sh_y, hip_y, sw, fat, f):
    t = a.get("type")
    col = a.get("color")
    if t in ("glasses", "sunglasses"):
        gc = col or ("#1a1a1a" if t == "sunglasses" else "#3a2416")
        sp_ = _num(f, "eye_spacing")
        eh = _num(f, "eye_height")
        for s in (-1, 1):
            ec = hc + np.array([s * 0.36 * R * sp_, 0.14 * R * eh, 0.8 * R])
            S.torus(ec + np.array([0, 0.02 * R, er * 1.45]), er * 1.4, 0.03 * R, gc, axis=(0.0, 0.0, 1.0), group="glasses", k=0.0, gloss=0.6)
            S.capsule(ec + np.array([s * er * 1.4, 0.03 * R, er * 1.25]), hc + np.array([s * 0.98 * R, 0.1 * R, -0.05 * R]),
                      0.025 * R, 0.025 * R, gc, group="glasses", k=0.0, gloss=0.6)
            if t == "sunglasses":
                S.ellipsoid(ec + np.array([0, 0.02 * R, er * 1.45]), (er * 1.38, er * 1.2, 0.02 * R), a.get("color2", "#20262e"),
                            group="glasses", k=0.0, gloss=0.9)
        S.capsule(hc + np.array([-0.36 * R * sp_ + er * 1.4, 0.16 * R * eh, 0.8 * R + er * 1.4]),
                  hc + np.array([0.36 * R * sp_ - er * 1.4, 0.16 * R * eh, 0.8 * R + er * 1.4]), 0.03 * R, 0.03 * R, gc,
                  group="glasses", k=0.0, gloss=0.6)
    elif t == "pens":
        for i, pc in enumerate(a.get("colors") or [col or "#1d4ed8"]):
            x = 0.07 * H + 0.012 * H * i
            S.capsule((x, sh_y - 0.06 * H, 0.105 * H + 0.02 * H * fat), (x, sh_y - 0.01 * H, 0.1 * H + 0.02 * H * fat),
                      0.006 * H, 0.006 * H, pc, group="props", k=0.0, gloss=0.6)
    elif t == "cap":
        cc = col or "#c0392b"
        S._add(lambda P: _sd_ellipsoid(P, hc + np.array([0, 0.2 * R, -0.02 * R]), np.array([1.08, 0.95, 1.08]) * R), cc, k=0.0,
               group="hat", gloss=0.15, clip=lambda P: _sd_plane(P - hc, (0, -1, 0.1), -0.45 * R))
        S.ellipsoid(hc + np.array([0, 0.48 * R, 0.95 * R]), (0.62 * R, 0.05 * R, 0.5 * R), a.get("color2", cc), group="hat", k=0.02, gloss=0.15)
    elif t == "gandhi_topi":
        S.ellipsoid(hc + np.array([0, 1.02 * R, -0.05 * R]), (0.5 * R, 0.3 * R, 1.02 * R), col or "#f6f4ee", group="hat", k=0.02, gloss=0.1)
        S.paint(lambda P: np.abs(P[:, 2] - hc[2] + 0.05 * R) - 0.012 * R, _darker(col or "#f6f4ee", 0.85), soft=0.002, group="hat")
    elif t == "turban":
        tc = col or "#e8a33a"
        S.ellipsoid(hc + np.array([0, 0.62 * R, -0.04 * R]), (1.12 * R, 0.6 * R, 1.12 * R), tc, group="hat", k=0.02, gloss=0.15)
        S.torus(hc + np.array([0, 0.45 * R, 0.0]), 1.0 * R, 0.16 * R, _darker(tc, 0.85), axis=(0, 1, 0.15), group="hat", k=0.04, gloss=0.15)
    elif t == "gamchha":
        gc = col or "#c0392b"
        S.torus(np.array([0, sh_y + 0.005 * H, 0.0]), 0.075 * H + 0.03 * H * fat, 0.026 * H, gc, axis=(0, 1, 0.3), group="props", k=0.0, gloss=0.05)
        S.capsule((0.05 * H, sh_y, 0.07 * H), (0.07 * H, sh_y - 0.14 * H, 0.1 * H + 0.03 * H * fat), 0.02 * H, 0.018 * H, gc,
                  group="props", k=0.0, gloss=0.05)
    elif t == "scarf":
        S.torus(np.array([0, sh_y + 0.02 * H, 0.0]), 0.065 * H, 0.026 * H, col or "#7c3aed", axis=(0, 1, 0.25), group="props", k=0.0, gloss=0.05)
    elif t == "chain":
        k_ = S.joints.get("slim", 1.0)
        S.torus(np.array([0, sh_y - 0.03 * H, 0.03 * H * k_]), 0.07 * H * k_, 0.004 * H, col or "#e6b422", axis=(0, 1, 0.9),
                group="props", k=0.0, gloss=0.9)
    elif t == "stethoscope":
        S.torus(np.array([0, sh_y - 0.01 * H, 0.02 * H]), 0.07 * H, 0.005 * H, col or "#2a2a2a", axis=(0, 1, 0.6), group="props", k=0.0, gloss=0.6)
        S.sphere((0.03 * H, sh_y - 0.17 * H, 0.12 * H + 0.03 * H * fat), 0.014 * H, "#c8ccd0", group="props", k=0.0, gloss=0.9)
    elif t == "watch":
        S.torus(np.array([-sw - 0.1 * H, hip_y + 0.02 * H, 0.03 * H]), 0.022 * H, 0.006 * H, col or "#3a2416", axis=(0, 1, 0), group="props", k=0.0, gloss=0.6)
    elif t == "nehru_jacket":                       # a sleeveless jacket over the kurta: armholes, a short collar, buttons
        jc = col or "#1f6b45"
        arm = lambda P: np.hypot((np.abs(P[:, 0]) - sw * 0.98) / (0.07 * H), (P[:, 1] - (sh_y - 0.06 * H)) / (0.1 * H)) - 1.0
        S.paint(lambda P: np.maximum(np.maximum(np.maximum(np.abs(P[:, 0]) - sw * 0.98, P[:, 1] - (sh_y + 0.015 * H)),
                                                hip_y - 0.03 * H - P[:, 1]), -arm(P) * 0.05 * H), jc, soft=0.003)
        S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) - 0.006 * H, -P[:, 2]), np.maximum(P[:, 1] - sh_y, hip_y - P[:, 1])),
                _darker(jc, 0.7), soft=0.0015)
        for i in range(4):
            S.sphere((0.012 * H, sh_y - (0.03 + 0.05 * i) * H, 0.12 * H + 0.03 * H * fat * (i / 3)), 0.006 * H, "#e6b422",
                     group="props", k=0.0, gloss=0.9)
    elif t == "lawyer_bands":                       # the two white bands at the collar
        for s_ in (-1, 1):
            S.capsule((s_ * 0.008 * H, sh_y - 0.005 * H, 0.085 * H), (s_ * 0.01 * H, sh_y - 0.05 * H, 0.1 * H), 0.006 * H, 0.008 * H,
                      col or "#fbfbfb", group="props", k=0.0, gloss=0.2)
    elif t == "kada":                               # a steel bangle on the wrist
        S.torus(np.array([sw + 0.06 * H + 0.03 * H * fat, hip_y + 0.0 * H, 0.03 * H]), 0.026 * H, 0.006 * H, col or "#c8ccd0",
                axis=(0, 1, 0), group="props", k=0.0, gloss=0.9)
    elif t == "pallu":                              # a saree's loose end: over the left shoulder, across the chest
        pc_ = col or "#db2777"
        S.tube([(0.1 * H, hip_y + 0.0 * H, 0.1 * H + 0.02 * H * fat), (0.0, hip_y + 0.15 * H, 0.13 * H + 0.03 * H * fat),
                (-sw * 0.8, sh_y, 0.04 * H)], 0.035 * H, pc_, group="props", k=0.0, gloss=0.1)
        S.tube([(-sw * 0.8, sh_y, 0.04 * H), (-sw * 0.85, sh_y + 0.005 * H, -0.06 * H), (-sw * 0.9, hip_y - 0.1 * H, -0.1 * H)],
               0.04 * H, pc_, group="props", k=0.0, gloss=0.1)
    elif t == "comb_scissors":                      # the barber: a comb and scissors in the shirt pocket
        S.capsule((0.07 * H, sh_y - 0.06 * H, 0.105 * H + 0.02 * H * fat), (0.07 * H, sh_y - 0.0 * H, 0.1 * H + 0.02 * H * fat),
                  0.008 * H, 0.008 * H, "#2b2d42", group="props", k=0.0, gloss=0.6)
        S.torus((0.09 * H, sh_y - 0.005 * H, 0.1 * H + 0.02 * H * fat), 0.01 * H, 0.0025 * H, "#c8ccd0", axis=(0, 0, 1),
                group="props", k=0.0, gloss=0.9)
    elif t == "backpack":                           # a traveller's rucksack on the back, two straps over the shoulders
        bc = col or "#2f5d50"
        fz, k_ = S.joints.get("front", 0.12 * H), S.joints.get("slim", 1.0)
        back = -fz * 0.92
        S.ellipsoid((0, sh_y - 0.13 * H, back - 0.05 * H), (0.105 * H * k_ ** 0.5, 0.13 * H, 0.06 * H), bc, group="props",
                    k=0.0, gloss=0.12)
        S.ellipsoid((0, sh_y - 0.19 * H, back - 0.1 * H), (0.075 * H * k_ ** 0.5, 0.05 * H, 0.025 * H), _darker(bc, 0.8),
                    group="props", k=0.0, gloss=0.12)                                   # the front pocket
        for s_ in (-1, 1):
            x_ = s_ * 0.075 * H * k_ ** 0.5
            S.tube([(x_, sh_y - 0.17 * H, fz * 0.95), (x_, sh_y + 0.005 * H, fz * 0.6),
                    (x_, sh_y + 0.025 * H, -0.01 * H), (x_, sh_y - 0.03 * H, back - 0.02 * H)], 0.012 * H * k_ ** 0.5,
                   _darker(bc, 0.7), group="props", k=0.0, gloss=0.12)
    elif t == "camera":                             # a camera on a strap across the body (the travel vlogger)
        cz = S.joints.get("front", 0.12 * H) * 0.98 + 0.02 * H   # (on the belly, hanging from the strap)
        S.ellipsoid((0.04 * H, sh_y - 0.2 * H, cz), (0.05 * H, 0.032 * H, 0.025 * H), col or "#1d1d1f", group="props",
                    k=0.0, gloss=0.5)
        S.capsule((0.04 * H, sh_y - 0.2 * H, cz + 0.02 * H), (0.04 * H, sh_y - 0.2 * H, cz + 0.045 * H), 0.02 * H,
                  0.018 * H, "#2b2b2e", group="props", k=0.0, gloss=0.8)                # the lens
        S.paint_line([(-0.09 * H, sh_y + 0.01 * H, 0.06 * H), (0.04 * H, sh_y - 0.17 * H, cz)], 0.008 * H, "#1d1d1f",
                     soft=0.002)                                                        # the strap
    elif t == "bindi":
        S.paint_ball(hc + np.array([0, 0.36 * R, 0.96 * R]), 0.05 * R, col or "#c0182a", soft=0.003)
    elif t == "earrings":
        for s in (-1, 1):
            S.sphere(hc + np.array([s * 1.0 * R, -0.3 * R, 0.0]), 0.06 * R, col or "#e6b422", group="props", k=0.0, gloss=0.9)
