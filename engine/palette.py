"""World palettes: one setting recolours a whole 3D world (No Man's Sky idea) - grass, leaves, wood, rock, water,
sand, sky and ground - keeping every thing's own light and dark shades. People are never recoloured.

    "palette": "alien_pink" | "autumn" | "snow" | "desert" | "fantasy" | "night_glow" | "mars" | "ice" | "candy"
               | "golden" | "random" | {"seed": 7} | {"grass": "#d44fa0", "leaves": "#7a3cff", "rock": "#30e0c0", ...}
    (story "settings" or one scene)

How: every colour is sorted into what it IS by its hue / strength (green = plants, brown = wood / earth, grey =
stone, blue = water, pale yellow = sand) and moved to the palette's colour for that, at the same brightness.
Reds, pinks, whites, blacks and strong colours (flowers, signs, clothes, lamps) stay as they are.
Seeded: "random" with the same seed is the same world every time.
"""
import colorsys
import random

import numpy as np

ROLES = ("plant", "leaves", "wood", "rock", "water", "sand", "ground", "sky", "fog")

PRESETS = {
    "alien_pink": {"plant": "#e0559f", "leaves": "#b03aa8", "wood": "#4a3a6e", "rock": "#3fb8a8",
                   "water": "#59e0d0", "sand": "#f2b6d0", "ground": "#c95a9a", "sky": "#ffb37a", "fog": "#f4c9d8"},
    "autumn": {"plant": "#c9a03a", "leaves": "#d2652a", "wood": "#6b4528", "rock": "#8a7f72", "water": "#4f7f8f",
               "sand": "#d9bf8a", "ground": "#b08a3e", "sky": "#9fc0d8", "fog": "#e8d9c0"},
    "snow": {"plant": "#e9eef2", "leaves": "#dfe8ee", "wood": "#5a4a3e", "rock": "#9aa6b0", "water": "#7fa9c9",
             "sand": "#f2f4f6", "ground": "#f1f4f7", "sky": "#c9d8e6", "fog": "#eef2f6", "snow_tops": True},
    "desert": {"plant": "#9a9a4a", "leaves": "#8a8f3e", "wood": "#7a5530", "rock": "#c08a5a", "water": "#3f9fb0",
               "sand": "#e8c88a", "ground": "#dcb47a", "sky": "#a8cde6", "fog": "#f0dcc0"},
    "fantasy": {"plant": "#3fd0a0", "leaves": "#7a4cff", "wood": "#3e3a7a", "rock": "#6a8fd0", "water": "#ff7ad9",
                "sand": "#f0e0ff", "ground": "#4fb890", "sky": "#c7a6ff", "fog": "#e6d6ff"},
    "night_glow": {"plant": "#1f8f7a", "leaves": "#1a5fa0", "wood": "#2a2440", "rock": "#3a3f6a", "water": "#30e0ff",
                   "sand": "#4a4a7a", "ground": "#1d4a52", "sky": "#1a1f4a", "fog": "#2a3060", "glow": True},
    "mars": {"plant": "#b8643a", "leaves": "#a0502a", "wood": "#5a3020", "rock": "#9a4a2e", "water": "#6a8a9a",
             "sand": "#d08a5a", "ground": "#c06a3e", "sky": "#e8b08a", "fog": "#e8c0a0"},
    "ice": {"plant": "#9fe6ff", "leaves": "#7fd0f0", "wood": "#4a6a8a", "rock": "#b0d8ee", "water": "#3f8fd0",
            "sand": "#e0f4ff", "ground": "#bfe8f6", "sky": "#bfe0ff", "fog": "#e6f6ff", "snow_tops": True},
    "candy": {"plant": "#7fe08a", "leaves": "#ff8ac0", "wood": "#c07a50", "rock": "#b8a0ff", "water": "#7ad0ff",
              "sand": "#ffe0a0", "ground": "#a0f0b0", "sky": "#ffd6ec", "fog": "#fff0f6"},
    "golden": {"plant": "#d6b04a", "leaves": "#c99a2e", "wood": "#7a5228", "rock": "#b09070", "water": "#5aa0b0",
               "sand": "#f0d8a0", "ground": "#caa04a", "sky": "#ffd9a0", "fog": "#ffe8c8"},
}
NAMES = tuple(PRESETS) + ("random",)

CURRENT = [None]           # the palette of the frame being drawn (render sets it per scene)


def _rgb(h):
    h = str(h).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _hex(c):
    return "#" + "".join(f"{int(max(0, min(1, v)) * 255 + 0.5):02x}" for v in c[:3])


def random_palette(seed=0):
    """A new world: one base hue for plants, the rest chosen round the colour wheel so they match.
    The same seed gives the same palette."""
    r = random.Random(f"palette{seed}")
    base = r.random()

    def hsv(h, s, v):
        return _hex(colorsys.hsv_to_rgb(h % 1.0, s, v))
    plant_s = r.uniform(0.45, 0.75)
    return {"plant": hsv(base, plant_s, r.uniform(0.6, 0.85)),
            "leaves": hsv(base + r.uniform(-0.12, 0.12), plant_s + 0.1, r.uniform(0.45, 0.7)),
            "wood": hsv(base + 0.5 + r.uniform(-0.1, 0.1), 0.35, 0.35),
            "rock": hsv(base + 0.5 + r.uniform(-0.15, 0.15), r.uniform(0.15, 0.45), r.uniform(0.5, 0.75)),
            "water": hsv(base + r.choice((0.33, -0.33)), 0.55, 0.85),
            "sand": hsv(base + 0.08, 0.25, 0.9),
            "ground": hsv(base + r.uniform(-0.05, 0.05), plant_s * 0.85, r.uniform(0.55, 0.75)),
            "sky": hsv(base + r.uniform(0.4, 0.6), r.uniform(0.2, 0.45), 0.95),
            "fog": hsv(base + 0.5, 0.12, 0.95)}


def compile_palette(spec):
    """setting -> {role: (r, g, b), "name": ..., flags} or None"""
    if not spec or spec in ("none", "off", "normal", False):
        return None
    seed = 0
    if isinstance(spec, dict):
        base = dict(PRESETS.get(str(spec.get("base", "")).lower(), {}))
        if "seed" in spec and not any(k in spec for k in ROLES):
            base = random_palette(spec["seed"])
        base.update({k: v for k, v in spec.items() if k in ROLES or k in ("snow_tops", "glow")})
        name = "custom"
        seed = spec.get("seed", 0)
    else:
        s = str(spec).lower().strip()
        if s.startswith("random"):
            seed = s.split(":", 1)[1] if ":" in s else 0
            base, name = random_palette(seed), f"random:{seed}"
        elif s in PRESETS:
            base, name = dict(PRESETS[s]), s
        else:
            return None
    out = {"name": name}
    for k in ROLES:
        if k in base:
            out[k] = np.array(_rgb(base[k]), float)
    if "leaves" not in out and "plant" in out:
        out["leaves"] = out["plant"] * 0.8
    if "ground" not in out and "plant" in out:
        out["ground"] = out["plant"] * 0.9
    out["snow_tops"] = bool(base.get("snow_tops"))
    out["glow"] = bool(base.get("glow"))
    out["key"] = repr(sorted((k, tuple(np.round(v, 3)) if isinstance(v, np.ndarray) else v) for k, v in out.items()))
    return out


def use(spec):
    """make spec the palette for what is drawn next (None = the normal colours)"""
    if spec is None:
        CURRENT[0] = None
        return None
    got = _COMPILED.get(repr(spec))
    if got is None:
        got = compile_palette(spec)
        _COMPILED[repr(spec)] = got
    CURRENT[0] = got
    return got


_COMPILED = {}


# ---------------------------------------------------------------------------- sorting colours into roles
# role numbers: -1 keep, 0 plant (light green), 1 leaves (dark green), 2 wood / earth (brown), 3 rock (grey),
#               4 water (blue), 5 sand (pale yellow)
ROLE_KEYS = ("plant", "leaves", "wood", "rock", "water", "sand")
# what a role's colour looks like in the normal world (its brightness is matched)
REF = {0: 0.52, 1: 0.36, 2: 0.36, 3: 0.55, 4: 0.55, 5: 0.75}


def classify(rgb):
    """(N, 3) colours 0..1 -> (N,) role numbers"""
    rgb = np.asarray(rgb, float).reshape(-1, 3)
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    v = mx
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    d = np.maximum(mx - mn, 1e-6)
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    role = np.full(len(rgb), -1, np.int64)
    green = (h > 0.17) & (h < 0.47) & (s > 0.18) & (v > 0.12)
    role[green & (lum >= 0.42)] = 0
    role[green & (lum < 0.42)] = 1
    brown = (h > 0.02) & (h < 0.13) & (s > 0.22) & (v > 0.12) & (v < 0.72)
    role[brown] = 2
    grey = (s < 0.13) & (v > 0.22) & (v < 0.86)
    role[grey] = 3
    blue = (h > 0.5) & (h < 0.64) & (s > 0.25) & (v > 0.3)
    role[blue] = 4
    sand = (h > 0.08) & (h < 0.17) & (s > 0.12) & (s < 0.55) & (v >= 0.72)
    role[sand] = 5
    return role


def recolor(rgb, pal, up=None, height=None):
    """(N, 3) colours -> recoloured (N, 3) with the palette (same brightness ratio as before).
    up: (N,) how much each face looks up (0..1) - snow on the tops; height: (N,) world height (higher = drier)"""
    rgb = np.asarray(rgb, float).reshape(-1, 3)
    if pal is None or not len(rgb):
        return rgb
    role = classify(rgb)
    out = rgb.copy()
    lum = 0.3 * rgb[:, 0] + 0.59 * rgb[:, 1] + 0.11 * rgb[:, 2]
    for k, key in enumerate(ROLE_KEYS):
        tgt = pal.get(key)
        if tgt is None:
            continue
        sel = role == k
        if not sel.any():
            continue
        tl = 0.3 * tgt[0] + 0.59 * tgt[1] + 0.11 * tgt[2]
        ratio = np.clip((lum[sel] + 0.03) / (REF[k] + 0.03), 0.55, 1.6)
        # keep a little of the thing's own hue so copies don't look painted with one pot
        out[sel] = np.clip(tgt[None, :] * ratio[:, None] * 0.88 + rgb[sel] * 0.12 * (tl / max(REF[k], 0.05)), 0, 1)
    if height is not None and "plant" in pal:          # higher land = a little drier / lighter
        hk = np.clip((np.asarray(height, float) - 250.0) / 1500.0, 0, 0.3)
        pl = (role == 0) | (role == 1)
        out[pl] = out[pl] * (1 - hk[pl, None]) + np.array([0.85, 0.78, 0.5]) * hk[pl, None]
    if up is not None and pal.get("snow_tops"):         # snow lies on what looks up
        u = np.asarray(up, float)
        sn = ((role == 3) | (role == 0) | (role == 1) | (role == 2)) & (u > 0.72)
        out[sn] = out[sn] * 0.15 + np.array([0.95, 0.97, 1.0]) * 0.85
    return out


_ONE = {}


def one(c):
    """one colour through the current palette (cached) - for the painted (2D) parts of a 3D world"""
    pal = CURRENT[0]
    if pal is None:
        return c
    k = (pal["key"], tuple(round(float(v), 3) for v in c[:3]))
    got = _ONE.get(k)
    if got is None:
        if len(_ONE) > 5000:
            _ONE.clear()
        got = _ONE[k] = tuple(float(v) for v in recolor([c[:3]], pal)[0])
    return got + tuple(c[3:])


def map_colour(c, role, pal=None):
    """one colour (r, g, b) -> the palette's colour for that role at the same brightness (sky, ground, water)"""
    pal = CURRENT[0] if pal is None else pal
    if pal is None or role not in pal:
        return c
    tgt = pal[role]
    lum = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    tl = 0.3 * tgt[0] + 0.59 * tgt[1] + 0.11 * tgt[2]
    k = max(0.5, min(1.7, (lum + 0.03) / (tl + 0.03)))
    return tuple(float(min(1.0, v * k)) for v in tgt)


def hsl_overlay(ctx, role, x, y, w, h, alpha=0.85):
    """Repaint an area's hue / strength with the palette's colour for role, keeping its light and dark
    (cairo's HSL colour blend): the whole ground or sky at once."""
    pal = CURRENT[0]
    if pal is None or role not in pal:
        return
    import cairo
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_HSL_COLOR)
    ctx.set_source_rgba(*[float(v) for v in pal[role]], alpha)
    ctx.rectangle(x, y, w, h)
    ctx.fill()
    ctx.restore()


def swatches(spec):
    """for the Studio: [(role, hex)]"""
    p = compile_palette(spec)
    if not p:
        return []
    return [(k, _hex(p[k])) for k in ROLES if k in p]
