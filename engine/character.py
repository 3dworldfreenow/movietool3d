"""Characters: definition (look, outfit, species), kinematics and the coloured cartoon renderer.

Styles
  "cartoon" (default)  coloured chunky stickman: skin tones, clothes, hair, shading, outlines
  "classic"            the original thin single-line stickman (engine/classic.py)
Species
  human (default), monkey, astronaut outfit ... and animals (engine/animals.py)
"""
import colorsys
import math

import cairo

from .poses import BONES, SHOULDER_DROP
from .util import hex_to_rgb, darker, lighter, mix, rotate, dirv, clamp, TAU, stable_hash

DEFAULT_PALETTE = ["#1d3557", "#9d0208", "#2d6a4f", "#6a3fa0", "#b5651d", "#0077b6", "#d62828", "#3a0ca3"]

# real human skin (close to the Monk Skin Tone scale, with a little cartoon warmth): skin is never very
# saturated - the darker it is, the less orange; strong orange / pink reads as paint, not people
SKIN = {"fair": "#f2dccb", "light": "#ead0b4", "wheat": "#dcb894", "medium": "#c49a72", "tan": "#a98058",
        "brown": "#8c6448", "dark": "#6c4a38", "deep": "#4a3428"}
HAIR = {"black": "#1e1916", "dark_brown": "#3b2518", "brown": "#6b4226", "light_brown": "#9a6a3f",
        "blonde": "#e0bd6a", "red": "#a33b20", "grey": "#a4a4a4", "gray": "#a4a4a4", "white": "#ececec"}

# outfit type -> defaults. bottom_kind: pants | shorts | skirt | long_skirt | dhoti
OUTFITS = {
    "shirt":     dict(top="#3d6fb6", bottom="#2f3e55", sleeves="long", bottom_kind="pants"),
    "tshirt":    dict(top="#e76f51", bottom="#34497a", sleeves="short", bottom_kind="pants"),
    "shorts":    dict(top="#f4a261", bottom="#2a9d8f", sleeves="short", bottom_kind="shorts"),
    "kurta":     dict(top="#f4a261", bottom="#f3eee4", sleeves="long", bottom_kind="pants", tunic=0.95),
    "salwar":    dict(top="#e56b9f", bottom="#fbe3ec", sleeves="long", bottom_kind="pants", tunic=1.05, dupatta=True),
    "dress":     dict(top="#ff70a6", bottom="#ff70a6", sleeves="short", bottom_kind="skirt"),
    "frock":     dict(top="#ffb3c6", bottom="#ffb3c6", sleeves="short", bottom_kind="skirt"),
    "saree":     dict(top="#c9184a", bottom="#c9184a", sleeves="short", bottom_kind="long_skirt", pallu=True),
    "suit":      dict(top="#2b2d42", bottom="#2b2d42", sleeves="long", bottom_kind="pants", tie=True, collar=True),
    "uniform":   dict(top="#f8f9fa", bottom="#1d3557", sleeves="short", bottom_kind="pants", tie=True, belt=True),
    "dhoti":     dict(top="#fdf6e3", bottom="#fbfaf5", sleeves="long", bottom_kind="dhoti", tunic=0.6),
    "labcoat":   dict(top="#fbfbfb", bottom="#6c757d", sleeves="long", bottom_kind="pants", tunic=1.25),
    "police":    dict(top="#b59b6a", bottom="#a8905f", sleeves="short", bottom_kind="pants", belt=True),
    "astronaut": dict(top="#f1f3f5", bottom="#e9ecef", sleeves="long", bottom_kind="pants", helmet=True,
                      pack=True, shoes="#8d99ae"),
    "cape":      dict(top="#1d4e89", bottom="#1d3557", sleeves="long", bottom_kind="pants", cape=True, belt=True),
    "farmer":    dict(top="#d8c3a5", bottom="#8e7a5c", sleeves="long", bottom_kind="dhoti", tunic=0.5),
    "nurse":     dict(top="#f8f9fa", bottom="#f8f9fa", sleeves="short", bottom_kind="skirt", belt=True, shoes="#f1f1f1"),
    "chef":      dict(top="#fbfbfb", bottom="#343a40", sleeves="long", bottom_kind="pants", tunic=0.7, buttons=True),
    "army":      dict(top="#5b6b3a", bottom="#4b5a2f", sleeves="long", bottom_kind="pants", belt=True, camo=True,
                      shoes="#2b2b2b"),
    "firefighter": dict(top="#3a2e2a", bottom="#3a2e2a", sleeves="long", bottom_kind="pants", bands=True,
                        shoes="#1f1f1f"),
    "royal":     dict(top="#7b2cbf", bottom="#f4e3c1", sleeves="long", bottom_kind="pants", tunic=1.25, cape=True,
                      trim=True),
    "sadhu":     dict(top="#f18701", bottom="#f18701", sleeves="none", bottom_kind="dhoti", tunic=0.9, shawl=True),
    "pilot":     dict(top="#f8f9fa", bottom="#1d3557", sleeves="short", bottom_kind="pants", tie=True),
    "sports":    dict(top="#1d4ed8", bottom="#f8f9fa", sleeves="short", bottom_kind="shorts", number=True),
    "overalls":  dict(top="#2f5d8a", bottom="#2f5d8a", sleeves="long", bottom_kind="pants", straps=True),
    "none":      dict(top=None, bottom=None, sleeves="none", bottom_kind="none"),
}
OUTFIT_ALIASES = {"tie": "shirt", "casual": "tshirt", "school": "uniform", "school_uniform": "uniform",
                  "doctor": "labcoat", "coat": "labcoat", "jacket": "suit", "superhero": "cape", "sari": "saree",
                  "gown": "dress", "skirt": "dress", "lehenga": "saree", "space": "astronaut", "spacesuit": "astronaut",
                  "kurti": "salwar", "salwar_kameez": "salwar", "pajama": "kurta", "t-shirt": "tshirt",
                  "military": "army", "fireman": "firefighter", "king": "royal", "robe": "royal", "saffron": "sadhu",
                  "jersey": "sports", "sportswear": "sports", "boiler_suit": "overalls", "uniform_nurse": "nurse"}

BUILD = {"slim": 0.82, "thin": 0.82, "normal": 1.0, "average": 1.0, "strong": 1.18, "muscular": 1.18,
         "chubby": 1.38, "fat": 1.45, "big": 1.3}


def _hex(c):
    return hex_to_rgb(c) if c is not None else None


def _shift_hue(rgb, amount):
    h, l, s = colorsys.rgb_to_hls(*rgb)
    return colorsys.hls_to_rgb((h + amount) % 1.0, l, s)


class CharacterDef:
    def __init__(self, cid, spec, index=0, default_style="cartoon"):
        from . import animals, professions, registry
        registry.load()
        spec = professions.apply(dict(spec or {}))
        self.profession = spec.get("profession")
        self.tool = spec.get("tool")
        self.spec = spec
        self.id = cid
        self.name = spec.get("name", cid.replace("_", " ").title())
        self.species = animals.canon(spec.get("species", spec.get("animal", "human")))
        self.kind = animals.kind_of(self.species)            # human | quadruped | bird
        self.gender = str(spec.get("gender", "male")).lower()
        if self.gender in ("f", "girl", "woman", "lady"):
            self.gender = "female"
        self.age = age_word(spec.get("age", "adult"))
        self.style = str(spec.get("style", default_style)).lower()
        self.look = spec.get("look") or spec.get("puppet")      # a puppet costume (assets/puppets/<look>)
        rng = stable_hash(cid)
        # --- classic-compatible colours
        self.color = hex_to_rgb(spec.get("color", DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]))
        self.accent = hex_to_rgb(spec.get("accent", spec.get("color", "#e63946")))
        self.head_fill = hex_to_rgb(spec.get("head_fill", "#ffffff"))
        default_scale = {"baby": 0.56, "toddler": 0.6, "child": 0.8, "teen": 0.92, "old": 0.96}.get(self.age, 1.0)
        self.scale = float(spec.get("scale", spec.get("height", default_scale)))
        self.build = BUILD.get(str(spec.get("build", "normal")).lower(), 1.0)
        # --- skin / hair
        sk = spec.get("skin", spec.get("skin_tone"))
        if sk is None:
            sk = ["wheat", "medium", "light", "tan", "wheat", "brown"][rng % 6]
        self.skin = hex_to_rgb(SKIN.get(str(sk).lower(), sk))
        if self.species == "monkey":
            self.skin = hex_to_rgb(spec.get("fur", "#8b5a2b"))
        default_hair = ("bun" if self.gender == "female" else "bald_sides") if self.age == "old" else \
                       ("short" if self.age in ("baby", "toddler") else ("long" if self.gender == "female" else "short"))
        self.hair = str(spec.get("hair", default_hair)).lower()
        hc = spec.get("hair_color", "grey" if self.age == "old" else ["black", "black", "dark_brown", "black"][rng % 4])
        self.hair_color = hex_to_rgb(HAIR.get(str(hc).lower(), hc))
        self.hat = str(spec.get("hat", "none")).lower()
        self.glasses = bool(spec.get("glasses", False))
        self.beard = bool(spec.get("beard", False))
        self.mustache = bool(spec.get("mustache", False))
        self.thickness = float(spec.get("thickness", 1.0))
        # --- outfit
        default_outfit = ("dress" if self.age in KID_AGES else "salwar") if self.gender == "female" else \
                         ("tshirt" if self.age in KID_AGES + ("teen",) else "shirt")
        if self.species == "monkey":
            default_outfit = "none"
        o = str(spec.get("outfit", default_outfit)).lower()
        self.tie = o == "tie"
        o = OUTFIT_ALIASES.get(o, o)
        if o not in OUTFITS:
            o = default_outfit
        self.outfit = o
        od = dict(OUTFITS[o])
        top_c = spec.get("outfit_color", spec.get("shirt", spec.get("top")))
        if top_c is None and "color" in spec and self.style != "classic":
            top_c = spec["accent"] if o in ("dress", "frock", "saree", "salwar") and "accent" in spec else spec["color"]
        self.top = _hex(top_c) if top_c else _hex(od["top"])
        bot = spec.get("pants", spec.get("bottom", spec.get("bottom_color")))
        if bot:
            self.bottom = _hex(bot)
        elif od["bottom_kind"] in ("skirt", "long_skirt") and od["bottom"]:
            self.bottom = self.top
        else:
            self.bottom = _hex(od["bottom"])
        self.shoes = hex_to_rgb(spec.get("shoes", od.get("shoes", "#3a2e2a")))
        self.sleeves, self.bottom_kind = od["sleeves"], od["bottom_kind"]
        if spec.get("sleeves") in ("long", "short", "none"):          # e.g. a sleeveless vest over a dhoti
            self.sleeves = spec["sleeves"]
        self.tunic = od.get("tunic", 0)
        self.extras = {k for k in ("pallu", "dupatta", "tie", "collar", "belt", "helmet", "pack", "cape", "buttons",
                                   "camo", "bands", "trim", "shawl", "number", "straps") if od.get(k)}
        if self.tie:
            self.extras.add("tie")
        if spec.get("cape"):
            self.extras.add("cape")
        self.voice = spec.get("voice", {}) if isinstance(spec.get("voice"), dict) else {"name": spec.get("voice")}
        self.seed = rng
        self.animal = animals.species_def(self.species, spec) if self.kind != "human" else None
        if self.kind != "human" and "scale" not in spec:
            self.scale = self.animal["scale"] * (0.7 if self.age == "child" else 1.0)

    @property
    def main_color(self):
        if self.kind != "human":
            return self.animal["fur"]
        return self.top or self.color

    def recolor(self, amount):
        if self.kind != "human":
            return
        self.top = _shift_hue(self.top, amount) if self.top else self.top


def make_distinct(chars):
    """If two characters would look almost identical, shift the later one's clothes colour."""
    seen = []
    for c in chars:
        if c.kind != "human" or c.top is None:
            continue
        for tries in range(6):
            clash = any(o.outfit == c.outfit and sum(abs(a - b) for a, b in zip(o.top, c.top)) < 0.35
                        and abs(o.scale - c.scale) < 0.1 for o in seen)
            if not clash:
                break
            c.recolor(0.17)
        seen.append(c)


# ---------------------------------------------------------------------------- kinematics
KID_AGES = ("baby", "toddler", "child")
# small children are not small adults: a much bigger head, a short body and short legs (head x, the rest scaled)
AGE_BODY = {"baby": {"head": 1.72, "torso": 0.64, "neck": 0.4, "arm": 0.52, "leg": 0.45},
            "toddler": {"head": 1.52, "torso": 0.74, "neck": 0.6, "arm": 0.64, "leg": 0.58}}
HEAD_K = {"baby": 1.72, "toddler": 1.52, "child": 1.24}


def age_word(a):
    """"baby" (about 0-1 year: crawls), "toddler" (1-3: toddles), "child", "teen", "adult", "old" - from a word or
    a number of years ("age": 2)."""
    try:
        n = float(a)
        return "baby" if n < 1.5 else "toddler" if n < 4 else "child" if n < 13 else "teen" if n < 20 else \
            "adult" if n < 60 else "old"
    except (TypeError, ValueError):
        pass
    w = str(a or "adult").lower().strip()
    if w in ("baby", "infant", "newborn", "baccha", "shishu"):
        return "baby"
    if w in ("toddler", "tot", "little one"):
        return "toddler"
    if w in ("kid", "boy", "girl"):
        return "child"
    return w


# "toon" (the 2.5D cartoon look, like a TV cartoon): a big head with big eyes, a short neck, short legs and chunky
# limbs - the face and the acting read at a glance even when the person is small on the screen
TOON_BODY = {"torso": 0.86, "neck": 0.45, "arm": 0.86, "leg": 0.8}
TOON_HEAD = {"baby": 1.1, "toddler": 1.15, "child": 1.3}       # x the age's own head size


def is_toon(c):
    return getattr(c, "style", "") == "toon" and getattr(c, "kind", "human") == "human"


def body_of(c, toon=True):
    """the body proportions of this person's age (None = the normal ones); toon: shorter and stockier (2.5D only:
    the 3D figures pass toon=False and keep their own shapes)"""
    b = AGE_BODY.get(getattr(c, "age", ""))
    if toon and is_toon(c):
        return {k: (b or {}).get(k, 1.0) * v for k, v in TOON_BODY.items()} | ({"head": b["head"]} if b else {})
    return b


def head_k(c, toon=True):
    k = HEAD_K.get(getattr(c, "age", ""), 1.1)
    return k * TOON_HEAD.get(getattr(c, "age", ""), 1.38) if toon and is_toon(c) else k


def solve(pose, scale=1.0, head_r=None, body=None):
    """Joint positions (local: +x forward, +y up), grounded on y=0. body = {torso, neck, arm, leg} length
    multipliers (babies / toddlers)."""
    B = BONES
    if body:
        B = dict(BONES)
        for k, m in (("torso", "torso"), ("neck", "neck"), ("upper_arm", "arm"), ("fore_arm", "arm"), ("thigh", "leg"),
                     ("shin", "leg"), ("foot", "leg")):
            B[k] = BONES[k] * body.get(m, 1.0)
    hr = head_r or B["head_r"]
    a = pose["torso"]
    ux, uy = math.sin(math.radians(a)), math.cos(math.radians(a))
    hip = (0.0, 0.0)
    neck = (ux * B["torso"], uy * B["torso"])
    sh = (ux * (B["torso"] - SHOULDER_DROP), uy * (B["torso"] - SHOULDER_DROP))
    ha = a + pose["head"]
    hd = B["neck"] + hr
    head = (neck[0] + math.sin(math.radians(ha)) * hd, neck[1] + math.cos(math.radians(ha)) * hd)

    def limb(root, a1, a2, l1, l2):
        d1 = dirv(a1)
        j = (root[0] + d1[0] * l1, root[1] + d1[1] * l1)
        d2 = dirv(a1 + a2)
        return j, (j[0] + d2[0] * l2, j[1] + d2[1] * l2)

    en, hn = limb(sh, pose["an_u"], pose["an_l"], B["upper_arm"], B["fore_arm"])
    ef, hf = limb(sh, pose["af_u"], pose["af_l"], B["upper_arm"], B["fore_arm"])
    kn, fn = limb(hip, pose["ln_t"], pose["ln_s"], B["thigh"], B["shin"])
    kf, ff = limb(hip, pose["lf_t"], pose["lf_s"], B["thigh"], B["shin"])
    tn = dirv(pose["ln_t"] + pose["ln_s"] + 90)
    tf = dirv(pose["lf_t"] + pose["lf_s"] + 90)
    toe_n = (fn[0] + tn[0] * B["foot"], fn[1] + tn[1] * B["foot"])
    toe_f = (ff[0] + tf[0] * B["foot"], ff[1] + tf[1] * B["foot"])
    nx, ny = uy, -ux
    waist = (ux * B["torso"] * 0.55, uy * B["torso"] * 0.55)
    skirt_l = (-ux * 28 - nx * 34, -uy * 28 - ny * 34)
    skirt_r = (-ux * 28 + nx * 30, -uy * 28 + ny * 30)
    pts = dict(hip=hip, neck=neck, sh=sh, head=head, en=en, hn=hn, ef=ef, hf=hf,
               kn=kn, fn=fn, kf=kf, ff=ff, toe_n=toe_n, toe_f=toe_f,
               waist=waist, skirt_l=skirt_l, skirt_r=skirt_r)
    rot = pose.get("rot", 0.0)
    if abs(rot) > 1e-3:
        pts = {k: rotate(v, rot) for k, v in pts.items()}
    ground_keys = ("hip", "neck", "sh", "kn", "kf", "fn", "ff", "toe_n", "toe_f")
    min_y = min(min(pts[k][1] for k in ground_keys), pts["head"][1] - hr)
    base = -min_y + pose.get("lift", 0.0)
    return {k: (v[0] * scale, (v[1] + base) * scale) for k, v in pts.items()}


# ---------------------------------------------------------------------------- dispatch
def draw_character(ctx, cdef, pose, x, facing, face="neutral", mouth=0.0, t=0.0,
                   extras=None, alpha=1.0, blink=False, seat=False, y=0.0, shadow=True):
    """Draw any character in WORLD coordinates (y-up context). Returns key world points.
    With a Klaus light (engine/klaus.py, 2.5D "art": "klaus") the character is lit: a shadow side, a rim."""
    from . import klaus
    if klaus.LIGHT[0] is not None and alpha > 0.05 and cdef.kind != "bird":
        s = cdef.scale
        if shadow:                                       # (the ground shadow stays outside the light)
            wid = 46 * s * cdef.build ** 0.5 if cdef.kind == "human" else \
                ((cdef.animal or {}).get("body", 60) * 0.7 + 30) * s
            draw_shadow(ctx, x, 0.0, wid, alpha, y)
        return klaus.lit(ctx, lambda c: _draw_any(c, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink,
                                                  seat, y, False), x, y, s, alpha)
    return _draw_any(ctx, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink, seat, y, shadow)


def _draw_any(ctx, cdef, pose, x, facing, face="neutral", mouth=0.0, t=0.0,
              extras=None, alpha=1.0, blink=False, seat=False, y=0.0, shadow=True):
    if cdef.kind != "human":
        from .animals import draw_animal
        return draw_animal(ctx, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink, y, shadow)
    if getattr(cdef, "look", None):
        from . import puppet
        if puppet.available(cdef.look):
            return puppet.draw_side(ctx, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink, seat, y,
                                    shadow)
    if cdef.style == "classic":
        from .classic import draw_classic
        if y:
            ctx.save()
            ctx.translate(0, y)
        out = draw_classic(ctx, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink, seat)
        if y:
            ctx.restore()
            out = {k: ((v[0], v[1] + y) if isinstance(v, tuple) else v) for k, v in out.items()}
        return out
    return draw_cartoon(ctx, cdef, pose, x, facing, face, mouth, t, extras, alpha, blink, seat, y, shadow)


def draw_shadow(ctx, x, height_above, width, alpha=1.0, y=0.0):
    from .realworld import SHADOW
    stretch, shift, sa = SHADOW[0]                  # the sun: long and to one side in the morning / evening
    k = clamp(1 - height_above / 380.0, 0.25, 1)
    alpha *= sa / (0.75 + 0.25 * stretch)
    ctx.save()
    ctx.translate(x + shift * width * 0.55 * k, y + 1)
    ctx.scale(width * k * stretch, width * 0.16 * k)
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()
    ctx.set_source_rgba(0, 0, 0, 0.16 * alpha * k)
    ctx.fill()


# ---------------------------------------------------------------------------- cartoon renderer
def _stroke(ctx, pts, width, color, alpha, outline=None, ow=0.0):
    if outline is not None and ow > 0:
        ctx.set_source_rgba(*outline, alpha)
        ctx.set_line_width(width + 2 * ow)
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.stroke()
    ctx.set_source_rgba(*color, alpha) if isinstance(color, tuple) else ctx.set_source(color)
    ctx.set_line_width(width)
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.stroke()


def _dot(ctx, p, r, color, alpha, outline=None, ow=0.0):
    ctx.arc(p[0], p[1], r, 0, TAU)
    ctx.set_source_rgba(*color, alpha)
    if outline is not None and ow > 0:
        ctx.fill_preserve()
        ctx.set_source_rgba(*outline, alpha)
        ctx.set_line_width(ow)
        ctx.stroke()
    else:
        ctx.fill()


def _along(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def _leg_point(J, side, frac):
    """Point along a leg: frac 0 = hip, 1 = knee, 2 = ankle."""
    hip, knee, foot = J["hip"], J["k" + side], J["f" + side]
    return _along(hip, knee, frac) if frac <= 1 else _along(knee, foot, frac - 1)


def draw_cartoon(ctx, c, pose, x, facing, face, mouth, t, extras, alpha, blink, seat, y=0.0, shadow=True):
    extras = extras or {}
    s = c.scale
    child = c.age in KID_AGES
    hr = BONES["head_r"] * head_k(c)
    J = solve(pose, s, hr, body_of(c))
    f = -1.0 if facing < 0 else 1.0

    def W(p):
        return (x + f * p[0], p[1] + y)

    K = s * c.thickness
    OW = 2.6 * K                                         # outline width
    toon = is_toon(c)
    if toon:                                             # chunky limbs, a bold ink line
        K *= 1.55
        OW = 3.3 * s * c.thickness
    arm_w, leg_w = 11.5 * K * c.build ** 0.4, 13.5 * K * c.build ** 0.4
    torso_w = (26 if c.gender == "female" else 30) * K * c.build
    skin, skin_o = c.skin, darker(c.skin, 0.62)
    top = c.top or c.skin
    bottom = c.bottom or c.skin
    shade = 0.8                                          # far limbs are darker
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    if shadow:
        hip_h = J["hip"][1] / max(s, 0.1)
        feet = min(J["fn"][1], J["ff"][1]) / max(s, 0.1)
        draw_shadow(ctx, x, max(0.0, feet - 2), 46 * s * c.build ** 0.5, alpha, y)
    if seat:
        from .classic import _draw_stool
        _draw_stool(ctx, W(J["hip"]), s, alpha)

    # ---------------- behind the body: cape, backpack, long hair
    head_ang = pose.get("rot", 0.0) - pose["torso"] - pose["head"]
    hx, hy = W(J["head"])
    r = hr * s
    drag, dlift = extras.get("drag") or (0.0, 0.0)
    if "cape" in c.extras:
        sway = 7 * math.sin(TAU * 0.7 * t)
        shp, hp = W(J["sh"]), W(J["hip"])
        a_ = math.radians(26.0 + sway * 0.4 + max(-20.0, drag) + 0.5 * dlift)    # trails behind when moving
        L_ = 140 * s
        tip = (shp[0] - f * math.sin(a_) * L_, shp[1] - math.cos(a_) * L_)
        a2 = math.radians(4.0 + 0.45 * max(-20.0, drag) + 0.3 * dlift)
        inner = (shp[0] - f * (math.sin(a2) * 122 * s + 4 * s), shp[1] - math.cos(a2) * 122 * s)
        ctx.move_to(shp[0] + f * 6 * s, shp[1] + 4 * s)
        ctx.line_to(shp[0] - f * 16 * s, shp[1])
        ctx.line_to(*tip)
        ctx.line_to(*inner)
        ctx.close_path()
        ctx.set_source_rgba(*c.accent, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*darker(c.accent, 0.6), alpha)
        ctx.set_line_width(OW)
        ctx.stroke()
    if "pack" in c.extras:
        a, b = W(_along(J["hip"], J["neck"], 0.35)), W(_along(J["hip"], J["neck"], 0.92))
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        nxp, nyp = -math.sin(ang) * f, math.cos(ang) * f
        off = -torso_w * 0.55
        _stroke(ctx, [(a[0] + nxp * off, a[1] + nyp * off), (b[0] + nxp * off, b[1] + nyp * off)],
                torso_w * 0.75, (0.72, 0.74, 0.78), alpha, (0.4, 0.42, 0.46), OW)
    if c.species == "monkey":
        hp = W(J["hip"])
        sw = 0.25 * math.sin(TAU * t / 2.1)
        pts = [hp]
        a = (-0.55 if toon else 0.3) + sw                 # (toon: out behind first, then curling up - not hidden by the body)
        for k in range(9):
            a += 0.3 if toon else 0.32
            lx, ly = pts[-1]
            seg = (19 if toon else 13) * s                # (toon: a longer, thicker tail that shows past the body)
            pts.append((lx - f * math.cos(a) * seg, ly + math.sin(a) * seg - (4 * s if k < 3 else 0)))
        _stroke(ctx, pts, (10 if toon else 7) * s, c.skin, alpha, darker(c.skin, 0.6), OW)
    ctx.save()
    ctx.translate(hx, hy)
    ctx.scale(f, 1)
    ctx.rotate(math.radians(head_ang))
    if (drag or dlift) and c.hair in ("long", "braid", "ponytail"):
        piv = (-0.4 * r, 0.75 * r)                     # long hair swings from the top of the head
        ctx.translate(*piv)
        ctx.rotate(-math.radians(0.6 * max(-30.0, drag) + 0.4 * dlift))
        ctx.translate(-piv[0], -piv[1])
    _hair_back(ctx, c, r, alpha, OW)
    ctx.restore()

    # ---------------- far limbs
    def arm(side, dark):
        sh, el, hd = W(J["sh"]), W(J["e" + side]), W(J["h" + side])
        k = shade if dark else 1.0
        sk = tuple(v * k for v in skin)
        tp = tuple(v * k for v in top)
        so = darker(sk, 0.62)
        if toon:                                          # 🎨 tapered: thick at the shoulder, slim at the wrist
            from . import toonbody as TB
            ws = [arm_w * 1.25, arm_w * 1.0, arm_w * 0.82]
            if c.sleeves == "long":
                TB.limb(ctx, [sh, el, hd], [w * 1.06 for w in ws], tp, alpha, darker(tp, 0.55), OW)
            else:
                TB.limb(ctx, [sh, el, hd], ws, sk, alpha, so, OW)
                if c.sleeves == "short":
                    TB.limb(ctx, [sh, _along(sh, el, 0.72)], [ws[0] * 1.2, ws[1] * 1.15], tp, alpha, darker(tp, 0.55), OW)
            gl = c.outfit == "astronaut"
            TB.hand(ctx, el, hd, arm_w * 0.95, (0.62, 0.66, 0.72) if gl else sk, alpha, so, OW, f)
            return hd
        if c.sleeves == "long":
            _stroke(ctx, [sh, el, hd], arm_w * 1.08, tp, alpha, darker(tp, 0.62), OW)
        else:
            _stroke(ctx, [el, hd], arm_w, sk, alpha, so, OW)
            if c.sleeves == "short":
                _stroke(ctx, [sh, _along(sh, el, 0.7)], arm_w * 1.25, tp, alpha, darker(tp, 0.62), OW)
            else:
                _stroke(ctx, [sh, el], arm_w, sk, alpha, so, OW)
        gl = c.outfit == "astronaut"
        _dot(ctx, hd, arm_w * 0.72, (0.62, 0.66, 0.72) if gl else sk, alpha, so, OW * 0.8)
        return hd

    def leg(side, dark):
        hp, kn, ft, toe = W(J["hip"]), W(J["k" + side]), W(J["f" + side]), W(J["toe_" + side])
        k = shade if dark else 1.0
        sk = tuple(v * k for v in skin)
        bt = tuple(v * k for v in bottom)
        so = darker(sk, 0.62)
        bk = c.bottom_kind
        if toon:                                          # 🎨 tapered: a thigh, a calf, an ankle, and a real shoe
            from . import toonbody as TB
            ws = [leg_w * 1.32, leg_w * 1.05, leg_w * 0.82]
            if bk == "pants":
                TB.limb(ctx, [hp, kn, ft], [w * 1.05 for w in ws], bt, alpha, darker(bt, 0.55), OW)
            elif bk in ("dhoti", "shorts"):
                TB.limb(ctx, [kn, ft], ws[1:], sk, alpha, so, OW)
                end = W(_leg_point(J, side, 1.45 if bk == "dhoti" else 0.85))
                TB.limb(ctx, [hp, kn, end] if bk == "dhoti" else [hp, end], ([ws[0] * 1.35, ws[1] * 1.4, ws[1] * 1.3] if bk == "dhoti"
                        else [ws[0] * 1.25, ws[1] * 1.3]), bt, alpha, darker(bt, 0.62), OW)
            else:
                TB.limb(ctx, [hp, kn, ft], [w * 0.92 for w in ws], sk, alpha, so, OW)
            shoe = c.skin if c.species == "monkey" else tuple(v * k for v in c.shoes)   # (a monkey has bare paws)
            TB.shoe(ctx, ft, toe, leg_w * 0.8, shoe, alpha, darker(shoe, 0.5), OW)
            return
        if bk in ("pants",):
            _stroke(ctx, [hp, kn, ft], leg_w * 1.08, bt, alpha, darker(bt, 0.62), OW)
        elif bk == "dhoti":
            _stroke(ctx, [kn, ft], leg_w * 0.9, sk, alpha, so, OW)
            _stroke(ctx, [hp, kn, W(_leg_point(J, side, 1.45))], leg_w * 1.55, bt, alpha, darker(bt, 0.7), OW)
        elif bk == "shorts":
            _stroke(ctx, [kn, ft], leg_w * 0.95, sk, alpha, so, OW)
            _stroke(ctx, [hp, W(_leg_point(J, side, 0.85))], leg_w * 1.3, bt, alpha, darker(bt, 0.62), OW)
        else:  # skin legs (skirt / saree / none)
            _stroke(ctx, [hp, kn, ft], leg_w * 0.92, sk, alpha, so, OW)
        shoe = tuple(v * k for v in c.shoes)
        _stroke(ctx, [ft, toe], leg_w * 0.95, shoe, alpha, darker(shoe, 0.55), OW)

    arm("f", True)
    leg("f", True)
    leg("n", False)

    # ---------------- torso
    hip, neck = W(J["hip"]), W(J["neck"])
    body_top = _along(hip, neck, 0.93)
    dx, dy = body_top[0] - hip[0], body_top[1] - hip[1]
    ln = math.hypot(dx, dy) or 1
    px, py = dy / ln, -dx / ln                        # perpendicular, pointing to the front
    if f < 0:
        px, py = -px, -py
    mid = _along(hip, body_top, 0.5)
    g = cairo.LinearGradient(mid[0] - px * torso_w / 2, mid[1] - py * torso_w / 2,
                             mid[0] + px * torso_w / 2, mid[1] + py * torso_w / 2)
    g.add_color_stop_rgba(0, *darker(top, 0.78), alpha)
    g.add_color_stop_rgba(0.55, *top, alpha)
    g.add_color_stop_rgba(1, *lighter(top, 0.12), alpha)
    belly = (c.build - 1.0) * 10 * s
    if toon:                                              # 🎨 shoulders, a waist, hips; a cel shadow down the back
        from . import toonbody as TB
        TB.torso(ctx, hip, body_top, px, py, torso_w * 1.3, top, alpha, darker(top, 0.55), OW,
                 belly=max(0.0, belly) * 1.6, female=c.gender == "female")
        if c.species == "monkey":                         # the pale belly fur
            bc = _along(hip, body_top, 0.42)
            _dot(ctx, (bc[0] + px * torso_w * 0.25, bc[1] + py * torso_w * 0.25), torso_w * 0.5, lighter(top, 0.45), alpha)
    else:
        _stroke(ctx, [hip, body_top], torso_w, g, alpha, darker(top, 0.6), OW)
    if belly > 1 and not toon:
        bc = _along(hip, body_top, 0.35)
        _dot(ctx, (bc[0] + px * torso_w * 0.3, bc[1] + py * torso_w * 0.3), torso_w * 0.45, top, alpha)

    # ---------------- skirts / tunics over the hips
    def cloth(frac_leg, color, flare=10):
        wf = W(_along(J["hip"], J["neck"], 0.5))
        pn, pf = W(_leg_point(J, "n", frac_leg)), W(_leg_point(J, "f", frac_leg))
        front, back = (pn, pf) if (pn[0] - pf[0]) * f >= 0 else (pf, pn)
        fl = flare * s
        ctx.move_to(wf[0] - px * torso_w * 0.5, wf[1] - py * torso_w * 0.5)
        ctx.line_to(wf[0] + px * torso_w * 0.5, wf[1] + py * torso_w * 0.5)
        ctx.line_to(front[0] + f * fl, front[1])
        ctx.line_to(back[0] - f * fl, back[1])
        ctx.close_path()
        gg = cairo.LinearGradient(back[0], back[1], front[0], front[1])
        gg.add_color_stop_rgba(0, *darker(color, 0.8), alpha)
        gg.add_color_stop_rgba(1, *color, alpha)
        ctx.set_source(gg)
        ctx.fill_preserve()
        ctx.set_source_rgba(*darker(color, 0.6), alpha)
        ctx.set_line_width(OW)
        ctx.stroke()

    if c.bottom_kind == "skirt":
        cloth(1.05, bottom, 14)
    elif c.bottom_kind == "long_skirt":
        cloth(1.9, bottom, 12)
        if toon and c.outfit == "saree":                 # 🎨 the saree's gold border along the hem
            from . import toonbody as TB
            pn, pf = W(_leg_point(J, "n", 1.9)), W(_leg_point(J, "f", 1.9))
            TB.hem(ctx, (pn[0] + f * 12 * s, pn[1] + 3 * s), (pf[0] - f * 12 * s, pf[1] + 3 * s), s, alpha)
    if c.tunic:
        cloth(c.tunic, top, 6)

    # ---------------- outfit details
    if "belt" in c.extras:
        b0 = _along(hip, body_top, 0.08)
        _stroke(ctx, [(b0[0] - px * torso_w * 0.5, b0[1] - py * torso_w * 0.5),
                      (b0[0] + px * torso_w * 0.5, b0[1] + py * torso_w * 0.5)], 5 * s, (0.2, 0.15, 0.12), alpha)
    if "collar" in c.extras:
        n0 = _along(hip, body_top, 0.98)
        ctx.move_to(n0[0] + px * torso_w * 0.05, n0[1] + py * torso_w * 0.05)
        ctx.line_to(n0[0] + px * torso_w * 0.45, n0[1] + py * torso_w * 0.45)
        n1 = _along(hip, body_top, 0.72)
        ctx.line_to(n1[0] + px * torso_w * 0.42, n1[1] + py * torso_w * 0.42)
        ctx.close_path()
        ctx.set_source_rgba(0.97, 0.97, 0.97, alpha)
        ctx.fill()
    if "tie" in c.extras:
        tc = c.accent if c.outfit != "uniform" or "accent" in c.spec else (0.75, 0.1, 0.15)
        a0, a1 = _along(hip, body_top, 0.95), _along(hip, body_top, 0.35)
        o = torso_w * 0.36
        _stroke(ctx, [(a0[0] + px * o, a0[1] + py * o), (a1[0] + px * o, a1[1] + py * o)], 6 * s, tc, alpha,
                darker(tc, 0.6), 1.2 * s)
    if "pallu" in c.extras and not toon:                 # (🎨 toon: toonbody.clothes draws a real pallu)
        wf = _along(hip, body_top, 0.25)
        sp = _along(hip, body_top, 1.0)
        back = W(_along(J["hip"], J["kf"], 0.5))
        acc = c.accent if "accent" in c.spec else lighter(bottom, 0.25)
        p1 = (sp[0] - px * torso_w * 0.2, sp[1] - py * torso_w * 0.2)
        _stroke(ctx, [(wf[0] + px * torso_w * 0.45, wf[1] + py * torso_w * 0.45), p1,
                      _swing(p1, (back[0] - f * 18 * s, back[1]), drag, dlift, f)], 11 * s, darker(bottom, 0.9), alpha, (0.95, 0.75, 0.2), 2.2 * s)
    if "dupatta" in c.extras:
        s0 = _along(hip, body_top, 0.98)
        acc = c.accent if "accent" in c.spec else lighter(top, 0.45)
        p1 = (s0[0] - px * torso_w * 0.55, s0[1] - py * torso_w * 0.55)
        _stroke(ctx, [(s0[0] + px * torso_w * 0.4, s0[1] + py * torso_w * 0.4), p1,
                      _swing(p1, W(_along(J["hip"], J["kf"], 0.2)), drag, dlift, f)], 9 * s, acc, alpha, darker(acc, 0.7), OW * 0.8)

    # ---------------- neck + head
    _stroke(ctx, [neck, _along(neck, (hx, hy), 0.55)], 9 * s, skin, alpha, skin_o, OW)
    ctx.save()
    ctx.translate(hx, hy)
    ctx.scale(f, 1)
    ctx.rotate(math.radians(head_ang))
    _head(ctx, c, r, face, mouth, blink, alpha, OW, t)
    ctx.restore()

    # ---------------- outfit details on the chest
    if toon:
        from . import toonbody as TB
        TB.clothes(ctx, c, hip, body_top, px, py, torso_w * 1.3, s, alpha, OW, f)
    else:
        _outfit_marks(ctx, c, hip, body_top, px, py, torso_w, s, alpha, OW, f)

    # ---------------- near arm on top (+ tool in hand)
    hand = arm("n", False)
    if c.tool and not extras.get("no_tool"):
        el = W(J["en"])
        _tool(ctx, c.tool, hand, math.atan2(hand[1] - el[1], hand[0] - el[0]), s, alpha, f)

    # ---------------- effects
    if extras.get("tears"):
        eye = rotate((0.55 * r, 0.1 * r), head_ang)
        ex, ey = hx + f * eye[0], hy + eye[1]
        ctx.set_source_rgba(0.35, 0.68, 1.0, alpha * 0.9)
        for k in range(3):
            ph = (t * 1.6 + k / 3.0) % 1.0
            ctx.arc(ex + f * 8 * s, ey - ph * 64 * s, (4.8 - 2 * ph) * s, 0, TAU)
            ctx.fill()
    if extras.get("zzz"):
        for k in range(3):
            ph = (t * 0.45 + k / 3.0) % 1.0
            ctx.save()
            ctx.translate(hx + f * (22 + 40 * ph) * s, hy + (34 + 90 * ph) * s)
            ctx.scale(1, -1)
            ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size((20 + 22 * ph) * s)
            ctx.set_source_rgba(0.25, 0.3, 0.5, alpha * (1 - ph))
            ctx.move_to(0, 0)
            ctx.show_text("Z")
            ctx.restore()
    return {"hand": hand, "head": (hx, hy), "hip": W(J["hip"]), "head_r": r, "mouth": (hx + f * 0.6 * r, hy - 0.4 * r)}


def _swing(pivot, end, drag, lift, f):
    """end point of a hanging cloth swung back by drag degrees (and up by lift) round pivot."""
    if not drag and not lift:
        return end
    a = -math.radians(0.8 * max(-35.0, min(80.0, drag)) + 0.5 * lift) * f
    dx, dy = end[0] - pivot[0], end[1] - pivot[1]
    ca, sa = math.cos(a), math.sin(a)
    return (pivot[0] + dx * ca - dy * sa, pivot[1] + dx * sa + dy * ca)


# ---------------------------------------------------------------------------- head parts
def _hair_back(ctx, c, r, alpha, ow):
    hc, ho = c.hair_color, darker(c.hair_color, 0.6)
    ctx.set_line_width(ow)
    if c.hair in ("long", "braid"):
        ctx.move_to(0.25 * r, 0.95 * r)
        ctx.curve_to(-1.25 * r, 1.2 * r, -1.4 * r, -0.6 * r, -1.0 * r, -1.75 * r)
        ctx.line_to(-0.35 * r, -1.55 * r)
        ctx.curve_to(-0.7 * r, -0.6 * r, -0.4 * r, 0.3 * r, 0.25 * r, 0.95 * r)
        ctx.close_path()
        ctx.set_source_rgba(*hc, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*ho, alpha)
        ctx.stroke()
        if c.hair == "braid":
            for k in range(4):
                ctx.arc(-0.85 * r, (-1.9 - k * 0.32) * r, 0.2 * r, 0, TAU)
                ctx.set_source_rgba(*hc, alpha)
                ctx.fill_preserve()
                ctx.set_source_rgba(*ho, alpha)
                ctx.stroke()
    elif c.hair == "ponytail":
        ctx.move_to(-0.85 * r, 0.45 * r)
        ctx.curve_to(-1.7 * r, 0.4 * r, -1.75 * r, -0.6 * r, -1.35 * r, -1.2 * r)
        ctx.curve_to(-1.35 * r, -0.5 * r, -1.2 * r, 0.0, -0.8 * r, 0.1 * r)
        ctx.close_path()
        ctx.set_source_rgba(*hc, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*ho, alpha)
        ctx.stroke()
    elif c.hair == "bun":
        ctx.arc(-0.7 * r, 0.85 * r, 0.42 * r, 0, TAU)
        ctx.set_source_rgba(*hc, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*ho, alpha)
        ctx.stroke()
    if c.species == "monkey":
        ctx.arc(-0.2 * r, 0.1 * r, 0.42 * r, 0, TAU)            # big round ear
        ctx.set_source_rgba(*c.skin, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*darker(c.skin, 0.6), alpha)
        ctx.stroke()


def _head(ctx, c, r, face, mouth, blink, alpha, ow, t):
    skin, so = c.skin, darker(c.skin, 0.62)
    ctx.set_line_width(ow)
    # skull
    ctx.arc(0, 0, r, 0, TAU)
    g = cairo.RadialGradient(0.35 * r, 0.3 * r, 0.1 * r, 0, 0, r * 1.05)
    g.add_color_stop_rgba(0, *lighter(skin, 0.12), alpha)
    g.add_color_stop_rgba(1, *darker(skin, 0.88), alpha)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_source_rgba(*so, alpha)
    ctx.stroke()
    # nose bump
    ctx.arc(0.97 * r, -0.05 * r, 0.16 * r, -1.9, 1.9)
    ctx.set_source_rgba(*skin, alpha)
    ctx.fill_preserve()
    ctx.set_source_rgba(*so, alpha)
    ctx.stroke()
    if c.species == "monkey":
        ctx.save()
        ctx.translate(0.45 * r, -0.12 * r)
        ctx.scale(0.55 * r, 0.62 * r)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(*lighter(skin, 0.5), alpha)
        ctx.fill()
    else:
        # ear (🎨 toon: at the back of the head, where it is seen from the side - not beside the eye)
        ex_, er_ = (-0.42 * r, 0.19 * r) if is_toon(c) else (-0.12 * r, 0.2 * r)
        ctx.arc(ex_, -0.02 * r, er_, 0, TAU)
        ctx.set_source_rgba(*skin, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*so, alpha)
        ctx.set_line_width(ow * 0.8)
        ctx.stroke()
        if is_toon(c):
            ctx.arc(ex_ + 0.02 * r, -0.02 * r, er_ * 0.5, math.radians(-70), math.radians(70))
            ctx.set_line_width(ow * 0.6)
            ctx.stroke()
    # blush
    if face in ("happy", "laughing", "love", "shy") or (mouth > 0.1 and face == "neutral"):
        ctx.save()
        ctx.translate(0.42 * r, -0.28 * r)
        ctx.scale(0.18 * r, 0.1 * r)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(1.0, 0.45, 0.5, 0.35 * alpha)
        ctx.fill()
    _eyes(ctx, c, r, face, blink, alpha, ow, getattr(mouth, "ctl", None))
    _mouth(ctx, c, r, face, mouth, alpha, ow)
    if c.mustache:
        ctx.move_to(0.4 * r, -0.26 * r)
        ctx.curve_to(0.55 * r, -0.18 * r, 0.8 * r, -0.2 * r, 0.9 * r, -0.32 * r)
        ctx.set_source_rgba(*c.hair_color, alpha)
        ctx.set_line_width(0.13 * r)
        ctx.stroke()
    if c.beard:
        ctx.move_to(-0.35 * r, -0.2 * r)
        ctx.curve_to(-0.25 * r, -1.25 * r, 0.95 * r, -1.2 * r, 0.95 * r, -0.28 * r)
        ctx.curve_to(0.75 * r, -0.62 * r, 0.1 * r, -0.62 * r, -0.35 * r, -0.2 * r)
        ctx.set_source_rgba(*c.hair_color, alpha)
        ctx.fill()
    _hair_top(ctx, c, r, alpha, ow)
    _hat(ctx, c, r, alpha, ow)
    if c.glasses:
        ctx.set_source_rgba(0.15, 0.15, 0.18, alpha)
        ctx.set_line_width(ow * 0.9)
        for ex in (0.18 * r, 0.6 * r):
            ctx.arc(ex, 0.12 * r, 0.21 * r, 0, TAU)
            ctx.stroke()
        ctx.move_to(0.39 * r, 0.14 * r)
        ctx.line_to(0.4 * r, 0.14 * r)
        ctx.move_to(-0.03 * r, 0.14 * r)
        ctx.line_to(-0.3 * r, 0.1 * r)
        ctx.stroke()
    if "helmet" in c.extras:
        ctx.arc(0.1 * r, 0.05 * r, r * 1.5, 0, TAU)
        ctx.set_source_rgba(0.75, 0.9, 1.0, 0.22 * alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(0.92, 0.94, 0.96, alpha)
        ctx.set_line_width(ow * 2.2)
        ctx.stroke()
        ctx.arc(0.1 * r, 0.05 * r, r * 1.2, math.radians(20), math.radians(70))
        ctx.set_source_rgba(1, 1, 1, 0.6 * alpha)
        ctx.set_line_width(ow * 1.4)
        ctx.stroke()


def _eyes(ctx, c, r, face, blink, alpha, ow, ctl=None):
    eyes = ((0.18 * r, 0.12 * r, 0.8), (0.6 * r, 0.12 * r, 1.0))
    dark = (0.12, 0.1, 0.1)
    ctl = ctl or {}
    gx, gy = float(ctl.get("gx", 0.0)), float(ctl.get("gy", 0.0))       # where the eyes look
    lid = float(ctl.get("lid", 0.0))                                   # upper eyelid down (0 open .. 1 shut)
    lift = float(ctl.get("brow", 0.0)) * 0.09 * r                      # brows up on stressed words / questions
    ctx.set_line_width(ow * 1.1)
    closed = blink or face == "sleeping"
    for ex, ey, k in eyes:
        if face == "laughing":
            ctx.move_to(ex - 0.13 * r * k, ey - 0.03 * r)
            ctx.curve_to(ex - 0.06 * r, ey + 0.12 * r, ex + 0.06 * r, ey + 0.12 * r, ex + 0.13 * r * k, ey - 0.03 * r)
            ctx.set_source_rgba(*dark, alpha)
            ctx.stroke()
        elif face == "crying" or closed:
            ctx.move_to(ex - 0.13 * r * k, ey)
            ctx.curve_to(ex - 0.06 * r, ey - 0.08 * r, ex + 0.06 * r, ey - 0.08 * r, ex + 0.13 * r * k, ey)
            ctx.set_source_rgba(*dark, alpha)
            ctx.stroke()
        else:
            big = 1.25 if face in ("surprised", "scared") else 1.0
            ctx.save()
            ctx.translate(ex, ey)
            ctx.scale(0.14 * r * k * big, 0.18 * r * big)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(1, 1, 1, alpha)
            ctx.fill_preserve()
            ctx.set_source_rgba(*dark, alpha * 0.8)
            ctx.set_line_width(ow * 0.6)
            ctx.stroke()
            pr = 0.085 * r * (0.8 if face in ("surprised", "scared") else 1.0)
            px, py = ex + 0.04 * r + gx * 0.07 * r, ey - 0.01 * r + gy * 0.08 * r
            if is_toon(c):                                # 🎨 a brown iris round the pupil, a bold lash line on top
                ctx.arc(px, py, pr * 1.3 * k ** 0.5, 0, TAU)
                ctx.set_source_rgba(0.33, 0.2, 0.12, alpha)
                ctx.fill()
                ctx.save()
                ctx.translate(ex, ey)
                ctx.scale(0.14 * r * k * big, 0.18 * r * big)
                ctx.arc(0, 0, 1.0, math.radians(15), math.radians(165))
                ctx.restore()
                ctx.set_source_rgba(*dark, alpha)
                ctx.set_line_width(ow * 1.3)
                ctx.stroke()
                pr *= 0.65
            ctx.arc(px, py, pr * k ** 0.5, 0, TAU)
            ctx.set_source_rgba(*dark, alpha)
            ctx.fill()
            ctx.arc(px + 0.03 * r, py + 0.05 * r, pr * 0.35, 0, TAU)
            ctx.set_source_rgba(1, 1, 1, alpha)
            ctx.fill()
            if lid > 0.05:                                    # the upper lid comes down (thinking, half-blink)
                eh = 0.18 * r * big
                ctx.save()
                ctx.translate(ex, ey)
                ctx.scale(0.14 * r * k * big, eh)
                ctx.arc(0, 0, 1.06, 0, TAU)
                ctx.restore()
                ctx.save()
                ctx.clip()
                ctx.rectangle(ex - 0.3 * r, ey + eh * (1.0 - 2.0 * min(1.0, lid)), 0.6 * r, 0.5 * r)
                ctx.set_source_rgba(*c.skin, alpha)
                ctx.fill()
                ctx.restore()
    # brows
    bc = darker(c.hair_color, 0.9) if c.hair_color[0] < 0.6 else (0.35, 0.3, 0.28)
    ctx.set_source_rgba(*bc, alpha)
    ctx.set_line_width(ow * 1.2)
    by = 0.38 * r + lift
    for ex, _, k in eyes:
        inner = 1 if ex > 0.4 * r else -1          # direction toward the other eye
        if face == "angry":
            ctx.move_to(ex - inner * 0.14 * r, by + 0.06 * r)
            ctx.line_to(ex + inner * 0.08 * r, by - 0.06 * r)
        elif face in ("sad", "crying", "scared"):
            ctx.move_to(ex - inner * 0.14 * r, by - 0.05 * r)
            ctx.line_to(ex + inner * 0.08 * r, by + 0.06 * r)
        elif face == "surprised":
            ctx.move_to(ex - 0.13 * r, by + 0.07 * r)
            ctx.curve_to(ex - 0.05 * r, by + 0.14 * r, ex + 0.05 * r, by + 0.14 * r, ex + 0.13 * r, by + 0.07 * r)
        elif face == "thinking" and ex > 0.4 * r:
            ctx.move_to(ex - 0.12 * r, by + 0.02 * r)
            ctx.line_to(ex + 0.12 * r, by + 0.1 * r)
        else:
            ctx.move_to(ex - 0.12 * r, by)
            ctx.curve_to(ex - 0.04 * r, by + 0.05 * r, ex + 0.04 * r, by + 0.05 * r, ex + 0.12 * r, by)
        ctx.stroke()


def _mouth_shaped(ctx, c, r, face, ctl, alpha, ow):
    """Talking: the real mouth shape of this moment (closed M/B/P, teeth, wide open, round O, OO, F/V, L)."""
    mx, my, mw = 0.55 * r, -0.42 * r, 0.34 * r
    dark, lipc = (0.45, 0.1, 0.12), (0.3, 0.12, 0.1)
    jaw, wide, rnd = ctl.get("jaw", 0.0), ctl.get("wide", 0.5), ctl.get("round", 0.0)
    closed, teeth, tongue = ctl.get("closed", 0.0), ctl.get("teeth", 0.0), ctl.get("tongue", 0.0)
    w = mw * (0.42 + 0.5 * wide - 0.28 * rnd)                 # half-width
    h = r * (0.025 + 0.3 * jaw) * (1.0 - 0.92 * closed)       # half-height
    smile = {"happy": 0.07, "laughing": 0.09}.get(face, -0.05 if face in ("sad", "crying") else 0.0) * r
    ctx.set_line_width(ow * 1.1)
    if h < 0.035 * r:                                         # lips together: a line (pressed for M / B / P)
        ctx.move_to(mx - w, my + smile)
        ctx.curve_to(mx - w * 0.4, my - 0.02 * r, mx + w * 0.4, my - 0.02 * r, mx + w, my + smile)
        ctx.set_source_rgba(*lipc, alpha)
        ctx.set_line_width(ow * (1.1 + 0.8 * closed))
        ctx.stroke()
        return
    ctx.save()
    ctx.translate(mx, my)
    ctx.scale(w, h)
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()
    ctx.set_source_rgba(*dark, alpha)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    if teeth > 0.2:                                           # the top teeth
        ctx.rectangle(mx - w, my + h * (1.0 - 0.55 * teeth), 2 * w, h)
        ctx.set_source_rgba(1, 1, 1, alpha)
        ctx.fill()
    if tongue > 0.3 or h > 0.12 * r:                          # the tongue (up for L / TH)
        ty = my - h * (0.55 if tongue < 0.3 else 0.05)
        ctx.save()
        ctx.translate(mx + w * 0.1, ty)
        ctx.scale(w * 0.7, h * (0.45 + 0.3 * tongue))
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(0.95, 0.45, 0.5, alpha)
        ctx.fill()
    ctx.restore()
    ctx.save()                                                # lips round the opening (thick when rounded)
    ctx.translate(mx, my)
    ctx.scale(w, h)
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()
    ctx.set_source_rgba(*lipc, alpha)
    ctx.set_line_width(ow * (0.7 + 1.1 * rnd))
    ctx.stroke()
    if abs(smile) > 0.01:                                     # corners up (happy) / down (sad) while talking
        for sd in (-1, 1):
            ctx.move_to(mx + sd * w * 0.92, my)
            ctx.line_to(mx + sd * (w + 0.05 * r), my + smile)
        ctx.set_line_width(ow)
        ctx.stroke()


def _mouth(ctx, c, r, face, mouth, alpha, ow):
    mx, my, mw = 0.55 * r, -0.42 * r, 0.34 * r
    dark, lip = (0.45, 0.1, 0.12), (0.3, 0.12, 0.1)
    ctx.set_line_width(ow * 1.1)
    ctl = getattr(mouth, "ctl", None)
    if ctl and "jaw" in ctl:
        return _mouth_shaped(ctx, c, r, face, ctl, alpha, ow)
    if mouth > 0.06:
        h = (0.06 + 0.32 * mouth) * r
        ctx.save()
        ctx.translate(mx, my)
        ctx.scale(mw * 0.55, h)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(*dark, alpha)
        ctx.fill()
        if h > 0.14 * r:
            ctx.save()
            ctx.translate(mx, my - h * 0.55)
            ctx.scale(mw * 0.35, h * 0.35)
            ctx.arc(0, 0, 1, 0, math.pi)
            ctx.restore()
            ctx.set_source_rgba(0.95, 0.45, 0.5, alpha)
            ctx.fill()
        return
    ctx.set_source_rgba(*lip, alpha)
    if face == "laughing":
        ctx.move_to(mx - mw * 0.75, my + 0.06 * r)
        ctx.line_to(mx + mw * 0.75, my + 0.06 * r)
        ctx.curve_to(mx + mw * 0.7, my - 0.34 * r, mx - mw * 0.7, my - 0.34 * r, mx - mw * 0.75, my + 0.06 * r)
        ctx.close_path()
        ctx.set_source_rgba(*dark, alpha)
        ctx.fill()
        ctx.rectangle(mx - mw * 0.6, my - 0.02 * r, mw * 1.2, 0.08 * r)
        ctx.set_source_rgba(1, 1, 1, alpha)
        ctx.fill()
    elif face in ("surprised", "scared"):
        ctx.save()
        ctx.translate(mx, my)
        ctx.scale(0.1 * r, 0.13 * r if face == "surprised" else 0.08 * r)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(*dark, alpha)
        ctx.fill()
    elif face in ("sad", "crying"):
        ctx.move_to(mx - mw / 2, my - 0.1 * r)
        ctx.curve_to(mx - mw / 4, my + 0.05 * r, mx + mw / 4, my + 0.05 * r, mx + mw / 2, my - 0.1 * r)
        ctx.stroke()
    elif face == "angry":
        ctx.move_to(mx - mw / 2, my - 0.04 * r)
        ctx.curve_to(mx - mw / 4, my + 0.03 * r, mx + mw / 4, my + 0.03 * r, mx + mw / 2, my - 0.04 * r)
        ctx.stroke()
    elif face in ("sleeping", "thinking"):
        ctx.move_to(mx - mw / 3, my)
        ctx.line_to(mx + mw / 3, my - (0.04 * r if face == "thinking" else 0))
        ctx.stroke()
    elif face == "happy":
        ctx.move_to(mx - mw * 0.6, my + 0.05 * r)
        ctx.curve_to(mx - mw * 0.3, my - 0.24 * r, mx + mw * 0.3, my - 0.24 * r, mx + mw * 0.6, my + 0.05 * r)
        ctx.close_path()
        ctx.set_source_rgba(*dark, alpha)
        ctx.fill()
    else:
        ctx.move_to(mx - mw / 2, my + 0.04 * r)
        ctx.curve_to(mx - mw / 4, my - 0.09 * r, mx + mw / 4, my - 0.09 * r, mx + mw / 2, my + 0.04 * r)
        ctx.stroke()


def _hair_top(ctx, c, r, alpha, ow):
    hc, ho = c.hair_color, darker(c.hair_color, 0.6)
    if c.hat in ("top", "turban", "police", "cap", "crown", "straw", "helmet", "hard_hat", "fire_helmet", "chef",
                 "pilot", "beret") and c.hair not in ("long", "ponytail", "braid"):
        return
    if c.hat not in _BUILTIN_HATS and c.hair not in ("long", "ponytail", "braid"):
        from . import codedraw                          # a hat / crown written in Studio > 🐍 Code
        if codedraw.hides_hair(c.hat):
            return
    ctx.set_line_width(ow)
    h = c.hair
    if h in ("bald", "none") or c.species == "monkey" and h in ("short", "none"):
        if c.species == "monkey":
            ctx.arc(0, 0, r * 1.02, math.radians(30), math.radians(215))
            ctx.arc_negative(0.3 * r, 0.1 * r, 0.62 * r, math.radians(200), math.radians(40))
            ctx.close_path()
            ctx.set_source_rgba(*darker(c.skin, 0.8), alpha)
            ctx.fill()
        return
    if h == "bald_sides":
        ctx.arc(0, 0, r * 1.04, math.radians(150), math.radians(215))
        ctx.arc_negative(-0.2 * r, 0, r * 0.8, math.radians(215), math.radians(150))
        ctx.close_path()
        ctx.set_source_rgba(*hc, alpha)
        ctx.fill()
        return
    if h == "spiky":
        ctx.move_to(-0.95 * r, 0.1 * r)
        for k in range(7):
            a0 = math.radians(175 - k * 22)
            a1 = math.radians(175 - k * 22 - 11)
            ctx.line_to(math.cos(a0) * r * 1.05, math.sin(a0) * r * 1.05)
            ctx.line_to(math.cos(a1) * r * 1.5, math.sin(a1) * r * 1.5)
        ctx.line_to(0.75 * r, 0.55 * r)
        ctx.curve_to(0.3 * r, 0.45 * r, -0.4 * r, 0.3 * r, -0.95 * r, 0.1 * r)
        ctx.close_path()
    elif h == "curly":
        for k in range(8):
            a = math.radians(20 + k * 24)
            ctx.new_sub_path()
            ctx.arc(math.cos(a) * r * 0.95, math.sin(a) * r * 0.95, 0.3 * r, 0, TAU)
    elif is_toon(c):  # 🎨 a fuller cap with a soft fringe of three tufts over the forehead
        ctx.arc(0, 0, r * 1.12, math.radians(28), math.radians(212))
        ctx.curve_to(-0.75 * r, 0.25 * r, -0.45 * r, 0.62 * r, -0.15 * r, 0.6 * r)
        for k, (x0, y0) in enumerate(((0.15, 0.48), (0.45, 0.56), (0.78, 0.5))):
            ctx.curve_to((x0 - 0.12) * r, (y0 + 0.22) * r, (x0 + 0.02) * r, (y0 + 0.18) * r, x0 * r, y0 * r)
        ctx.curve_to(0.92 * r, 0.62 * r, 0.98 * r, 0.62 * r, math.cos(math.radians(28)) * 1.12 * r, math.sin(math.radians(28)) * 1.12 * r)
        ctx.close_path()
    else:  # short / long / ponytail / bun / braid -> fringe cap
        ctx.arc(0, 0, r * 1.07, math.radians(38), math.radians(205))
        ctx.curve_to(-0.8 * r, 0.1 * r, -0.4 * r, 0.52 * r, 0.1 * r, 0.5 * r)
        ctx.curve_to(0.45 * r, 0.62 * r, 0.7 * r, 0.52 * r, 0.84 * r, 0.66 * r)
        ctx.close_path()
    ctx.set_source_rgba(*hc, alpha)
    ctx.fill_preserve()
    ctx.set_source_rgba(*ho, alpha)
    ctx.stroke()
    if is_toon(c):                                       # 🎨 a thin shine along the hair (not a grey blob)
        ctx.set_source_rgba(*lighter(hc, 0.35), 0.7 * alpha)
        ctx.set_line_width(ow * 0.9)
        ctx.arc(0, 0, r * 0.82, math.radians(105), math.radians(140))
        ctx.stroke()
        return
    ctx.set_source_rgba(1, 1, 1, 0.14 * alpha)
    ctx.arc(-0.1 * r, 0.75 * r, 0.22 * r, 0, TAU)
    ctx.fill()


_BUILTIN_HATS = ("none", "", "cap", "top", "crown", "bow", "turban", "police", "straw", "helmet", "hard_hat",
                 "fire_helmet", "chef", "nurse", "beret", "pilot")


def _hat(ctx, c, r, alpha, ow):
    acc = c.accent
    hat = c.hat
    if hat not in _BUILTIN_HATS:                        # something worn, drawn from assets/code/<hat>.py
        from . import codedraw
        codedraw.draw_wear(ctx, hat, r, alpha, ow, accent=acc, skin=c.skin, hair=c.hair_color)
        return
    ctx.set_line_width(ow)

    def fill(col):
        ctx.set_source_rgba(*col, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*darker(col, 0.6), alpha)
        ctx.stroke()

    if hat == "cap" or hat == "police":
        col = (0.2, 0.2, 0.25) if hat == "police" else acc
        ctx.arc(-0.05 * r, 0.3 * r, r * 1.02, math.radians(-6), math.radians(186))
        ctx.close_path()
        fill(col if hat != "police" else (0.66, 0.57, 0.38))
        ctx.rectangle(0.25 * r, 0.22 * r, 1.0 * r, 0.16 * r)
        fill(col if hat != "police" else (0.12, 0.12, 0.14))
        if hat == "police":
            ctx.arc(0.3 * r, 0.75 * r, 0.14 * r, 0, TAU)
            fill((0.95, 0.8, 0.25))
    elif hat == "top":
        ctx.rectangle(-1.05 * r, 0.72 * r, 2.1 * r, 0.2 * r)
        fill((0.12, 0.12, 0.14))
        ctx.rectangle(-0.72 * r, 0.9 * r, 1.44 * r, 1.1 * r)
        fill((0.12, 0.12, 0.14))
        ctx.rectangle(-0.72 * r, 0.93 * r, 1.44 * r, 0.2 * r)
        ctx.set_source_rgba(*acc, alpha)
        ctx.fill()
    elif hat == "crown":
        ctx.move_to(-0.7 * r, 0.72 * r)
        for px, py in [(-0.7, 1.45), (-0.35, 1.05), (0, 1.58), (0.35, 1.05), (0.7, 1.45), (0.7, 0.72)]:
            ctx.line_to(px * r, py * r)
        ctx.close_path()
        fill((0.98, 0.78, 0.18))
    elif hat == "bow":
        cx, cy = -0.45 * r, 0.98 * r
        for sgn in (-1, 1):
            ctx.move_to(cx, cy)
            ctx.line_to(cx + sgn * 0.5 * r, cy + 0.3 * r)
            ctx.line_to(cx + sgn * 0.5 * r, cy - 0.3 * r)
            ctx.close_path()
            fill(acc)
        ctx.arc(cx, cy, 0.14 * r, 0, TAU)
        fill(acc)
    elif hat == "turban":
        ctx.arc(0, 0.22 * r, r * 1.1, math.radians(-8), math.radians(188))
        ctx.close_path()
        fill(acc)
        ctx.set_source_rgba(*darker(acc, 0.72), alpha)
        ctx.set_line_width(ow * 1.1)
        for k in range(3):
            ctx.move_to(-0.95 * r, (0.35 + 0.25 * k) * r)
            ctx.curve_to(-0.3 * r, (0.7 + 0.25 * k) * r, 0.3 * r, (0.5 + 0.2 * k) * r, 0.95 * r, (0.3 + 0.2 * k) * r)
        ctx.stroke()
    elif hat == "straw":
        ctx.save()
        ctx.translate(0, 0.62 * r)
        ctx.scale(1.55 * r, 0.22 * r)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        fill((0.9, 0.78, 0.45))
        ctx.arc(0, 0.62 * r, 0.7 * r, 0, math.pi)
        ctx.close_path()
        fill((0.9, 0.78, 0.45))
    elif hat == "helmet":
        ctx.arc(0, 0.2 * r, r * 1.1, 0, math.pi)
        ctx.close_path()
        fill(acc)
    elif hat in ("hard_hat", "fire_helmet"):
        col = acc if hat == "hard_hat" else (0.78, 0.07, 0.12)
        ctx.arc(0, 0.25 * r, r * 1.08, 0, math.pi)
        ctx.close_path()
        fill(col)
        ctx.rectangle(-1.2 * r, 0.18 * r, 2.5 * r, 0.16 * r)
        fill(col)
        if hat == "fire_helmet":
            ctx.rectangle(-0.15 * r, 0.9 * r, 0.3 * r, 0.35 * r)
            fill((0.95, 0.8, 0.2))
    elif hat == "chef":
        ctx.rectangle(-0.72 * r, 0.62 * r, 1.44 * r, 0.42 * r)
        fill((1, 1, 1))
        for dx in (-0.45, 0.0, 0.45):
            ctx.arc(dx * r, 1.25 * r, 0.42 * r, 0, TAU)
            fill((1, 1, 1))
    elif hat == "nurse":
        ctx.move_to(-0.6 * r, 0.75 * r)
        ctx.line_to(0.6 * r, 0.75 * r)
        ctx.line_to(0.45 * r, 1.15 * r)
        ctx.line_to(-0.45 * r, 1.15 * r)
        ctx.close_path()
        fill((1, 1, 1))
        ctx.set_source_rgba(0.85, 0.1, 0.15, alpha)
        ctx.rectangle(-0.05 * r, 0.83 * r, 0.1 * r, 0.24 * r)
        ctx.rectangle(-0.12 * r, 0.9 * r, 0.24 * r, 0.1 * r)
        ctx.fill()
    elif hat == "beret":
        ctx.save()
        ctx.translate(-0.1 * r, 0.72 * r)
        ctx.rotate(-0.2)
        ctx.scale(1.05 * r, 0.38 * r)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        fill(acc)
    elif hat == "pilot":
        ctx.arc(-0.05 * r, 0.42 * r, r * 0.98, math.radians(-8), math.radians(188))
        ctx.close_path()
        fill(acc)
        ctx.rectangle(0.2 * r, 0.3 * r, 0.95 * r, 0.14 * r)
        fill((0.1, 0.1, 0.1))
        ctx.arc(0.2 * r, 0.95 * r, 0.12 * r, 0, TAU)
        fill((0.95, 0.8, 0.25))


# ---------------------------------------------------------------------------- profession details
def _outfit_marks(ctx, c, hip, top, px, py, w, s, alpha, ow, f):
    def at(u, side):
        p = (hip[0] + (top[0] - hip[0]) * u, hip[1] + (top[1] - hip[1]) * u)
        return (p[0] + px * w * side, p[1] + py * w * side)
    ex = c.extras
    if "buttons" in ex:
        for u in (0.35, 0.55, 0.75):
            p = at(u, 0.25)
            ctx.arc(p[0], p[1], 2.6 * s, 0, TAU)
            ctx.set_source_rgba(0.3, 0.3, 0.3, alpha)
            ctx.fill()
    if "camo" in ex:
        for u, side, r in ((0.3, -0.1, 7), (0.55, 0.2, 6), (0.75, -0.2, 5), (0.15, 0.25, 5)):
            p = at(u, side)
            ctx.arc(p[0], p[1], r * s, 0, TAU)
            ctx.set_source_rgba(0.28, 0.33, 0.18, alpha)
            ctx.fill()
    if "bands" in ex:
        for u in (0.25, 0.7):
            a, b = at(u, -0.5), at(u, 0.5)
            _stroke(ctx, [a, b], 5 * s, (0.98, 0.85, 0.2), alpha)
    if "trim" in ex:
        a, b = at(0.02, 0.5), at(0.95, 0.5)
        _stroke(ctx, [a, b], 4 * s, (0.95, 0.75, 0.2), alpha)
    if "shawl" in ex:
        a, b, d = at(0.95, 0.45), at(0.95, -0.5), at(0.2, -0.45)
        _stroke(ctx, [a, b, d], 10 * s, (0.95, 0.55, 0.05), alpha, (0.75, 0.35, 0.02), 1.5 * s)
    if "number" in ex:
        p = at(0.55, -0.05)
        ctx.save()
        ctx.translate(p[0], p[1])
        ctx.scale(1, -1)
        ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(15 * s)
        ctx.set_source_rgba(1, 1, 1, alpha)
        ctx.move_to(-6 * s, 5 * s)
        ctx.show_text(str(c.spec.get("number", 7))[:2])
        ctx.restore()
    if "straps" in ex:
        for side in (-0.2, 0.25):
            _stroke(ctx, [at(0.55, side), at(0.98, side)], 4 * s, darker(c.top, 0.7), alpha)
    if c.tool == "stethoscope":
        a, b = at(0.95, 0.4), at(0.95, -0.4)
        m = at(0.5, 0.45)
        ctx.set_source_rgba(0.15, 0.15, 0.2, alpha)
        ctx.set_line_width(2.5 * s)
        ctx.move_to(*a)
        ctx.curve_to(a[0], a[1] - 20 * s, m[0], m[1] + 10 * s, m[0], m[1])
        ctx.stroke()
        ctx.arc(m[0], m[1] - 3 * s, 4.5 * s, 0, TAU)
        ctx.set_source_rgba(0.75, 0.75, 0.8, alpha)
        ctx.fill()


def _tool(ctx, tool, hand, ang, s, alpha, f):
    """Small item held in the near hand, pointing along the forearm."""
    if tool in (None, "", "stethoscope"):
        return
    ctx.save()
    ctx.translate(*hand)
    ctx.rotate(ang)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    wood, metal, dark = (0.55, 0.36, 0.18), (0.72, 0.74, 0.78), (0.15, 0.15, 0.17)

    def line(x0, y0, x1, y1, w, col):
        ctx.set_source_rgba(*col, alpha)
        ctx.set_line_width(w * s)
        ctx.move_to(x0 * s, y0 * s)
        ctx.line_to(x1 * s, y1 * s)
        ctx.stroke()

    def box(x, y, w, h, col):
        ctx.rectangle(x * s, y * s, w * s, h * s)
        ctx.set_source_rgba(*col, alpha)
        ctx.fill()

    if tool == "baton":
        line(-10, 0, 34, 0, 6, dark)
    elif tool in ("staff", "walking_stick"):
        ctx.rotate(-ang)
        line(0, -95, 0, 110 if tool == "staff" else 30, 5, wood)
    elif tool == "book":
        box(-2, -12, 20, 24, (0.12, 0.35, 0.65))
        box(0, -10, 3, 20, (0.95, 0.95, 0.9))
    elif tool == "clipboard":
        box(-2, -14, 22, 28, (0.6, 0.45, 0.3))
        box(1, -11, 16, 20, (1, 1, 1))
    elif tool == "bag":
        box(-6, -24, 24, 22, (0.55, 0.25, 0.25))
    elif tool == "letters":
        box(-4, -8, 22, 15, (0.98, 0.96, 0.88))
        box(-2, -6, 22, 15, (0.95, 0.9, 0.75))
    elif tool == "sickle":
        line(-4, 0, 16, 0, 5, wood)
        ctx.set_source_rgba(*metal, alpha)
        ctx.set_line_width(4 * s)
        ctx.arc(26 * s, 8 * s, 12 * s, math.radians(200), math.radians(40))
        ctx.stroke()
    elif tool == "ladle":
        line(-4, 0, 30, 0, 3.5, metal)
        ctx.arc(34 * s, 0, 7 * s, 0, TAU)
        ctx.set_source_rgba(*metal, alpha)
        ctx.fill()
    elif tool == "wrench":
        line(-4, 0, 26, 0, 5, metal)
        ctx.arc(30 * s, 0, 6 * s, 0, TAU)
        ctx.set_source_rgba(*metal, alpha)
        ctx.fill()
    elif tool == "test_tube":
        box(-2, -4, 26, 8, (0.85, 0.95, 1.0))
        box(10, -4, 14, 8, (0.3, 0.85, 0.4))
    elif tool == "brush":
        line(-4, 0, 26, 0, 3, wood)
        line(26, 0, 34, 0, 6, (0.9, 0.2, 0.25))
    elif tool == "flute":
        line(-24, 0, 30, 0, 4, (0.7, 0.5, 0.25))
    elif tool == "scepter":
        ctx.rotate(-ang)
        line(0, -30, 0, 50, 4, (0.85, 0.65, 0.15))
        ctx.arc(0, 54 * s, 7 * s, 0, TAU)
        ctx.set_source_rgba(0.9, 0.2, 0.3, alpha)
        ctx.fill()
    elif tool == "sword":
        line(-6, 0, 6, 0, 5, (0.85, 0.65, 0.15))
        line(6, 0, 52, 0, 4, metal)
    elif tool == "axe":
        line(-6, 0, 34, 0, 5, wood)
        box(26, -2, 12, 14, metal)
    elif tool == "bat":
        line(-4, 0, 14, 0, 4, dark)
        line(14, 0, 60, 0, 9, (0.9, 0.78, 0.55))
    elif tool == "scale":
        line(0, 0, 0, -30, 2, dark)
        line(-18, -30, 18, -30, 2, dark)
        for dx in (-18, 18):
            ctx.arc(dx * s, -38 * s, 7 * s, 0, math.pi)
            ctx.set_source_rgba(0.75, 0.6, 0.25, alpha)
            ctx.fill()
    elif tool == "briefcase":
        box(-14, -30, 30, 22, (0.3, 0.2, 0.15))
    elif tool == "tray":
        ctx.rotate(-ang)
        line(-26, 6, 26, 6, 4, metal)
        ctx.arc(-8 * s, 14 * s, 6 * s, 0, TAU)
        ctx.arc(10 * s, 14 * s, 6 * s, 0, TAU)
        ctx.set_source_rgba(0.95, 0.95, 0.95, alpha)
        ctx.fill()
    else:
        box(-4, -6, 16, 12, (0.6, 0.6, 0.6))
    ctx.restore()
