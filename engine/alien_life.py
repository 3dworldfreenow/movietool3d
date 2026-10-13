"""Living planets: plants and creatures made from parts, picked by the planet's seed and shaped by its rules
(engine/galaxy.py) - the same planet always grows the same life.

    plants      a stem (or a few), a top (leaves / balls / spikes / crystals / fronds), glowing tips, vines
    creatures   a body copied from an animal skeleton (tiger, dog, cow, horse, goat, rabbit, elephant, a bird ...)
                with its own size, legs, neck, head, colours and pattern - 3 to 5 kinds per planet, tiny to elephant-big
    shaped by   strong gravity -> short, thick legs and low plants; weak -> tall, thin plants, long legs, big jumps;
                thick air -> more flyers; no air -> no life (maybe crystals); a red star -> dark plants, a blue star ->
                pale ones; cold -> furry and round; hot -> low, lizard-like; gas giants -> floating jellyfish (flyers)
    behaviour   grazers wander and eat in herds, flyers cross the sky, small ones keep away from people
    story       creatures are characters "creature_1" ... "creature_N" on that planet:
                {"who": "creature_2", "do": "run", "to": {"x": 1600}}; "life": false on the scene = none
CPU budget: 20-40 creatures at most (default 6-12), a few hundred plants near the camera (2D sprites in 3D).
"""
import math
import random

from .util import clamp, stable_hash

QUAD_BASES = ("dog", "cow", "horse", "goat", "rabbit", "elephant", "pig", "deer", "fox", "bear", "tiger", "cat")
BIRD_BASES = ("parrot", "crow", "pigeon", "eagle")
TOPS = ("leaves", "balls", "spikes", "crystals", "fronds", "cups", "fan")
SOUNDS = ("moo", "bleat", "howl", "growl", "oink", "trumpet", "neigh", "hoot", "coo", "squawk", "caw", "meow")


def _rng(*parts):
    return random.Random(stable_hash("|".join(str(p) for p in parts)) % (2 ** 31))


def _hsv(h, s, v):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s, 0, 1), clamp(v, 0, 1))
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def _key(p):
    return p.get("name", "planet")


def g_rel(p):
    return clamp(p["g"] / 9.81, 0.1, 4.0)


# ============================================================================ plants
# today's Earth (heights in drawing units: the walk turns ~500 into a ~12 m tree)
EARTH_PLANTS = [
    dict(kind="broadleaf tree", height=480, width=16, top="leaves", colour="#3e7a32", tip="#e9d47c", glow=False, stems=1, vine=False,
         seed=101, form="tree", why=["a broadleaf tree (oak, neem, mango, banyan): a woody trunk lifts the leaves over the others to the light"]),
    dict(kind="conifer", height=540, width=14, top="spikes", colour="#4a7d48", tip="#6b4a2b", glow=False, stems=1, vine=False,
         seed=102, form="tree", why=["a conifer (pine, deodar): needles that lose little water - they keep their leaves all winter"]),
    dict(kind="shrub", height=110, width=8, top="leaves", colour="#4b7b31", tip="#f4f1e6", glow=False, stems=1, vine=False,
         seed=103, form="bush", why=["a shrub: many woody stems, low and wide"]),
    dict(kind="wildflower", height=55, width=3, top="balls", colour="#5f9a3c", tip="#e44d6e", glow=False, stems=3, vine=False,
         seed=104, form="stalk", why=["a flowering herb: bright petals for the bees that carry its pollen"]),
    dict(kind="water lily", height=40, width=6, top="leaves", colour="#4f8a3a", tip="#f6c6d8", glow=False, stems=1, vine=False,
         seed=105, form="floating", why=["a water lily: air spaces in its leaves keep them floating on still water"]),
]


def plant_kinds(p):
    """2-4 kinds of plant for this planet: dicts read by Background._d_alien_plant"""
    if p.get("solar") == "earth" and not p.get("era"):   # 🌍 today's Earth: its real plants, not invented ones
        return [dict(k) for k in EARTH_PLANTS]
    if p.get("solar"):                              # a real world: nothing invented
        return []
    if p.get("life_stage") in ("microbes", "oxygen_rising", "seas"):   # 🦠 life has not reached the land yet
        return []
    if isinstance(p.get("life"), dict) and p["life"].get("plants") is False:
        return []
    if p["air"] == "none":                          # no air, no life: on some, glittering crystals
        r = _rng("crystal", _key(p))
        if r.random() > 0.4:
            return []
        return [dict(kind="crystal", height=r.uniform(40, 120), width=r.uniform(20, 50), top="crystals",
                     colour=_hsv(r.random(), 0.5, 0.9), glow=True, stems=1, vine=False, seed=r.randint(0, 9999))]
    r = _rng("plants", _key(p))
    g = g_rel(p)
    Tc = p["temperature_c"]
    tall = 1.0 / math.sqrt(g)                      # weak gravity: tall, thin
    base_col = p["colours"].get("plant", "#3f9142")
    out = []
    for i in range(r.randint(2, 4)):
        top = r.choice(TOPS)
        h = r.uniform(60, 260) * tall * (0.6 if Tc < 0 else 1.0)
        h = min(h, 600 / max(0.5, g))                                       # the square-cube law: a trunk must hold its own weight
        out.append(dict(kind=f"plant_{i + 1}", height=clamp(h, 30, 600), width=clamp(r.uniform(6, 22) * math.sqrt(g),
                                                                                     4, 50),
                        top=top, colour=_shift(base_col, r.uniform(-0.08, 0.08), r), tip=_hsv(r.random(), 0.7, 0.95),
                        glow=r.random() < (0.5 if "red" in p.get("star_kind", "") else 0.2),
                        stems=r.choice((1, 1, 2, 3, 5)), vine=r.random() < 0.25, seed=r.randint(0, 9999),
                        furry=Tc < -5))
        out[-1].update(plant_form(p, out[-1], i))
    return out


def plant_form(p, k, i):
    """the plant's form, by physics (separate random stream): -> {"form", "why"}
      tree       a thick trunk and a wide crown - only where gravity lets a tall trunk stand (and air to breathe in)
      bush       low and wide; strong gravity or cold keeps plants near the ground
      succulent  a thick, water-storing column: hot and dry
      moss       flat carpets: cold (or very strong gravity)
      floating   pads on the water: liquid water that is not too cold or hot
      stalk      a stem with a top (the plain kind)"""
    r = _rng("plantform", _key(p), i)
    g, Tc = g_rel(p), p["temperature_c"]
    wet = p["water"] in ("oceans", "lakes")
    w = [("stalk", 3), ("tree", 2.5 if g < 1.5 and Tc > -5 else 0), ("bush", 1.5 + (2 if g > 1.6 else 0)),
         ("succulent", 4 if (Tc > 30 and not wet) else 0), ("moss", 3 if Tc < 0 else (2 if g > 2.2 else 0)),
         ("floating", 2.5 if wet and 2 < Tc < 40 and i > 0 else 0)]
    if k["top"] == "crystals":
        w = [("stalk", 1)]
    form = _pick(r, [x for x in w if x[1] > 0])
    why = []
    if form == "tree" and g < 0.8:
        why.append("very tall: weak gravity lets a trunk grow high")
    elif form == "tree":
        why.append("a trunk: it reaches over the others for light")
    if form == "bush" and g > 1.6:
        why.append("low and wide: strong gravity")
    if form == "succulent":
        why.append("thick and fleshy: it stores water - hot and dry here")
    if form == "moss":
        why.append("a flat carpet: " + ("cold here" if Tc < 0 else "strong gravity"))
    if form == "floating":
        why.append("floats: its roots hang in the water")
    st = p.get("star_kind", "")
    if "red" in st:
        why.append("dark leaves: they catch every bit of the dim red light")
    elif any(x in st for x in ("blue", "white")):
        why.append("pale leaves: they reflect the strong blue light")
    return {"form": form, "why": why}


# ============================================================================ rocks: their colour from chemistry
REAL_ROCKS = {
    "mars": [("iron oxide (rust)", "#b0532e", "oxygen once rusted the iron in the rocks red", 0.6),
             ("basalt", "#4b4440", "old lava rock under the red dust", 0.3), ("clay", "#c7a07a", "made by water long ago", 0.1)],
    "moon": [("anorthosite", "#b9b8b4", "the bright highlands: light rock that floated up when the Moon was molten", 0.55),
             ("basalt", "#55545a", "the dark 'seas': old lava flows", 0.45)],
    "mercury": [("dark silicate", "#5f5a55", "scorched and darkened by the Sun", 0.7), ("basalt", "#46423f", "old lava", 0.3)],
    "venus": [("basalt", "#4a3a2c", "volcanoes cover the whole planet", 0.8), ("sulfur-stained rock", "#b39a3c", "sulfur from the volcanoes", 0.2)],
    "earth": [("granite", "#a39a92", "slow-cooled rock with crystals", 0.5), ("sandstone", "#c79c6b", "sand pressed into stone", 0.3),
              ("basalt", "#3f3d3c", "lava rock", 0.2)],
}


def rock_chemistry(p):
    """1-4 kinds of stone, each with a colour and the chemistry behind it (picked by the planet's seed, allowed by
    its physics): [{name, colour, why, share, shiny, glow}]"""
    if p.get("gas"):
        return []
    real = p.get("solar")
    if real:
        rows = REAL_ROCKS.get(real) or [("rock", p["colours"].get("rock", "#8e8e8e"), "", 1.0)]
        return [dict(name=n, colour=c, why=w, share=sh, shiny=False, glow=False) for n, c, w, sh in rows]
    r = _rng("rocks", _key(p))
    Tc = p["temperature_c"]
    try:                                                                  # the planet's elements (12.8) steer which stones there are
        from . import elements
        comp = elements.composition(p)
    except Exception:                                                     # noqa: BLE001
        comp = {"metallicity": 0.0, "c_to_o": 0.55}
    metal = 10 ** comp.get("metallicity", 0.0)
    mix = str(p.get("air_mix") or "").lower()
    oxy = "oxygen" in mix or bool(p.get("breathable"))
    terrain = set(p.get("terrain") or [])
    out = [dict(name="basalt" if Tc > 200 or "volcanoes" in terrain else "common rock", colour=p["colours"].get("rock", "#8e8e8e"),
                why="the planet's ordinary rock", share=1.0, shiny=False, glow=False)]
    def add(name, colour, why, share, shiny=False, glow=False):
        out.append(dict(name=name, colour=colour, why=why, share=share, shiny=shiny, glow=glow))
    if oxy and p["water"] != "none":                      # rust needs BOTH free oxygen and water (4Fe + 3O₂ + nH₂O)
        add("iron oxide (rust)", r.choice(("#a5482a", "#b5622f", "#8f3b25")), "oxygen and water rusted the iron in the rock (4Fe + 3O₂ → 2Fe₂O₃)", 0.6)
    bulk = comp.get("bulk") or {}
    fe, sul = float(bulk.get("Fe", 0)), float(bulk.get("S", 0))
    if "volcanoes" in terrain or Tc > 300 or (p.get("surface") == "lava"):
        if Tc < 115:                                                      # native sulfur melts at 115 °C
            add("sulfur", "#d9c13a", "volcanoes breathe out sulfur - it crusts yellow round the vents", 0.35)
        else:
            add("sulfur-stained rock", "#8a7a3a", f"too hot for solid sulfur (it melts at 115 °C): it stains the rock as sulfides (S {sul:.1f} % here)", 0.3)
        add("obsidian", "#1d1a22", "lava that cooled very fast into black glass", 0.25, shiny=True)
    elif sul > 3.5:
        add("sulfur-stained rock", "#9c8a40", f"formed cool, so it kept its sulfur (S {sul:.1f} %): yellow-brown sulfide stains", 0.2)
    if fe > 35 and not (oxy and p["water"] != "none"):                   # an iron-rich world, nothing to rust it
        add("dark silicate", "#3a3634", f"iron-rich rock (Fe {fe:.0f} % of the planet): dark grey-black - no oxygen to rust it", 0.4)
    if (comp.get("layers") or {}).get("ice", 0) > 20 and Tc < -20:
        add("ice boulder", "#dfeef7", f"formed past the snow line: {comp['layers']['ice']:.0f} % of it is ice - here ice is the 'rock'", 0.45, shiny=True)
    if any("kilonova" in x for x in comp.get("extras") or []) and r.random() < 0.7:
        add("gold-flecked quartz", "#e9dcae", "its birth cloud caught a kilonova's debris: ~3× the gold - flecks in white quartz", 0.06, shiny=True)
    if p["water"] != "none" and r.random() < 0.3 * metal:              # more heavy elements -> more metal ores
        add("copper ore", r.choice(("#3f8f7a", "#4aa38c")), "copper in the rock turned green-blue with water", 0.2)
    if comp.get("c_to_o", 0.55) > 0.85:                                   # a carbon world: dark carbon rock everywhere
        add("carbon-rich rock", "#1f1d1b", "more carbon than oxygen: graphite and carbide rock", 0.6, shiny=True)
    elif any(x in mix for x in ("methane", "carbon", "co2")) and r.random() < 0.6:
        add("carbon-rich rock", "#2a2826", "carbon from the air settled into dark rock", 0.3, shiny=r.random() < 0.4)
    if p["water"] in ("none", "steam") and ("dunes" in terrain or "canyons" in terrain or r.random() < 0.25) and Tc < 200:
        add("salt", "#ecebe6", "seas dried up long ago and left their salt", 0.25)
    if r.random() < 0.35:
        add("quartz crystals", r.choice(("#cfc8ff", "#a37be0", "#f1f1f7")), "slow-grown crystals of silica",
            0.12, shiny=True, glow="red" in p.get("star_kind", "") and r.random() < 0.5)
    tot = sum(x["share"] for x in out)
    for x in out:
        x["share"] = round(x["share"] / tot, 3)
    out[1:] = sorted(out[1:], key=lambda x: -x["share"])                 # (the ordinary rock stays first)
    return out[:5]


# ============================================================================ small life: insects and such
def small_life(p):
    """Butterflies, night moths, glowing bugs, beetles and spiders - only where physics allows them:
    life and air, not too cold or hot; flyers need enough air and not too much gravity; more oxygen (thick, breathable
    air) lets bugs grow bigger (as on Earth long ago: dragonflies as big as crows); spiders only where there are
    flying bugs to catch. -> [{kind, colour, colour2, size, count, act, why}]"""
    if p.get("solar") or p["air"] == "none" or not p.get("life") or p.get("gas"):
        return []
    if isinstance(p.get("life"), dict) and p["life"].get("creatures") == 0:
        return []
    Tc = p["temperature_c"]
    if Tc < -15 or Tc > 55:
        return []
    r = _rng("bugs", _key(p))
    g, rho = g_rel(p), air_density(p)
    oxy = "oxygen" in str(p.get("air_mix") or "").lower() or bool(p.get("breathable"))
    big = clamp((1.0 + (0.8 if (oxy and rho > 2) else 0)) / math.sqrt(g), 0.6, 2.2)
    can_fly = rho >= 0.4 and g < 2.5 and Tc > 0
    dim = "red" in p.get("star_kind", "")
    out = []
    hue = r.random()
    why_big = "big: thick oxygen-rich air feeds bigger bugs" if big > 1.3 else ("small: strong gravity" if big < 0.8 else "")
    if can_fly:
        out.append(dict(kind="butterfly", colour=_hsv(hue, 0.75, 0.95), colour2=_hsv(hue + 0.5, 0.6, 0.35), size=round(0.09 * big, 3),
                        count=r.randint(6, 14), act="day", why=[w for w in ("flies by day, from plant to plant", why_big) if w]))
        if r.random() < 0.6:
            out.append(dict(kind="moth", colour=_hsv(0.1, 0.25, 0.8), colour2=_hsv(0.08, 0.3, 0.45), size=round(0.07 * big, 3),
                            count=r.randint(4, 9), act="night", why=["flies at night"]))
        damp = p.get("water") in ("oceans", "lakes") or str(p.get("weather")) in ("rain", "storm")
        if damp and 10 < Tc < 40:                 # 🦟 small biters: their larvae need still water; they find you by your breath
            out.append(dict(kind="gnat", colour="#2b2a24", colour2="#151410", size=0.006, count=r.randint(30, 60), act="dusk",
                            why=["breeds in still water: its larvae wriggle in ponds and puddles",
                                 "finds warm-blooded animals (and you) by the CO₂ they breathe out - it follows you",
                                 "it cannot fly in a wind of more than ~3 m/s"]))
        if damp and (dim or r.random() < 0.5):   # ✨ glowing bugs: their larvae live in damp soil and leaf litter
            out.append(dict(kind="glowbug", colour=r.choice(("#c8ff6a", "#7affd4", "#ffd36a")), colour2="#202010", size=0.03,
                            count=r.randint(20, 50), act="night",
                            why=["glows at night to find a mate" + (" - easy to see under a dim red sun" if dim else "")]))
    out.append(dict(kind="beetle", colour=_hsv(r.random(), 0.6, 0.45), colour2=_hsv(r.random(), 0.3, 0.2), size=round(0.05 * big, 3),
                    count=r.randint(6, 14), act="any", why=["walks on 6 legs, hides from you", "a hard shell keeps it from drying out"]))
    # 🐜 a colony crawler (ant-like) - only where the rules let one live: plants to eat, a warm enough season to raise
    # the brood (5-45 °C), solid ground to dig (not ice, not a lava field). A queen lays every egg; eggs -> larvae ->
    # pupae grow hidden underground (they take ~40 days at 25 °C, ×2 slower for every 10 °C colder); workers forage,
    # soldiers guard the nest. The nest suits the planet: hot and dry -> a tall ventilated mound (taller where gravity is
    # weak), otherwise a burrow under a small soil mound - dug deeper where it is very cold or very hot (steadier warmth)
    plants_ok = bool(plant_kinds(p)) if p.get("life") else False
    if plants_ok and 5 < Tc < 45 and p.get("surface") not in ("ice", "lava") and p.get("water") != "ice":
        hot_dry = Tc > 28 and p.get("water") in ("none", "lakes")
        hunters = any(c["base"] in HUNTER_BASES for c in creature_kinds(p)) if p.get("life") else False
        out.append(dict(kind="colony", colour=_hsv(r.choice((0.02, 0.06, 0.1, 0.0)), 0.55, 0.22), colour2=_hsv(0.08, 0.4, 0.5),
                        size=round(0.012 * big, 4), count=0, act="day" if Tc < 30 else "dusk",
                        nest="mound" if hot_dry else "burrow", mound_m=round(min(4.0, 1.6 / math.sqrt(g)), 2) if hot_dry else 0.0,
                        depth_m=round(0.6 + abs(Tc - 25) * 0.05, 2), soldiers=round(0.08 + (0.07 if hunters else 0), 2),
                        eggs_day=round(clamp(25 * big, 8, 60)), dev_days_25=40,
                        name="ant-like" if oxy else "colony crawler",
                        why=[w for w in ("lives in a colony: one queen lays all the eggs, workers forage, soldiers guard",
                                         "builds a tall ventilated mound - cool inside in the heat" + (" (tall: weak gravity)" if g < 0.8 else "") if hot_dry else
                                         "nests underground under a small soil mound", why_big) if w]))
    if can_fly and r.random() < 0.8:
        out.append(dict(kind="spider", colour=_hsv(r.random(), 0.3, 0.3), colour2=_hsv(r.random(), 0.7, 0.75), size=round(0.05 * big, 3),
                        count=r.randint(2, 5), act="any", why=["8 legs; spins a web between plants to catch flying bugs"]))
    return out


def _mix_hex(a, b, t):
    a, b = str(a).lstrip("#"), str(b).lstrip("#")
    try:
        return "#" + "".join(f"{round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t):02x}" for i in (0, 2, 4))
    except ValueError:
        return "#" + b


def _shift(hexc, dh, r):
    import colorsys
    c = tuple(int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(*c)
    return _hsv(h + dh, s * r.uniform(0.85, 1.1), v * r.uniform(0.85, 1.1))


def plant_elements(p, world_w, n=None):
    """background elements (type "alien_plant") scattered over the scene"""
    kinds = plant_kinds(p)
    if not kinds:
        return []
    r = _rng("plant_pos", _key(p))
    n = n or (10 if p["air"] == "none" else 26)
    out = []
    for i in range(n):
        k = r.choice(kinds)
        front = r.random() < 0.3
        out.append(dict(type="alien_plant", x=r.uniform(-300, world_w + 300), p=1.0 if front else r.uniform(0.55, 0.95),
                        layer="front" if front else "back", y=-r.uniform(20, 160) if front else 0.0,
                        scale=r.uniform(0.7, 1.3), **k))
    return out


def draw_plant(ctx, e, t, sway=0.0):
    """a plant from its parts, y-up, foot at (e.x, e.y); drawn as a 2D sprite (also inside the 3D world)"""
    import cairo
    x, y = float(e["x"]), float(e.get("y", 0) or 0)
    s = float(e.get("scale", 1.0))
    h, w = float(e.get("height", 120)) * s, float(e.get("width", 12)) * s
    col = _rgb(e.get("colour", "#3f9142"))
    tip = _rgb(e.get("tip", "#ffd166"))
    r = random.Random(int(e.get("seed", 1)))
    n = int(e.get("stems", 1))
    top = e.get("top", "leaves")
    dark = tuple(c * 0.6 for c in col)
    light = tuple(min(1.0, c * 1.25 + 0.06) for c in col)
    if top != "crystals":                                               # a soft contact shadow where it meets the ground
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(w * (1.6 + 0.6 * n), w * 0.5)
        ctx.arc(0, 0, 1.0, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgba(0, 0, 0, 0.18)
        ctx.fill()

    def leaf(lx, ly, ang, L, W_):
        """a pointed leaf: lit on top, darker below, with a midrib"""
        ctx.save()
        ctx.translate(lx, ly)
        ctx.rotate(ang)
        ctx.move_to(0, 0)
        ctx.curve_to(L * 0.3, W_, L * 0.75, W_ * 0.8, L, 0)
        ctx.curve_to(L * 0.75, -W_ * 0.8, L * 0.3, -W_, 0, 0)
        g = cairo.LinearGradient(0, W_, 0, -W_)
        g.add_color_stop_rgb(0, *light)
        g.add_color_stop_rgb(1, *dark)
        ctx.set_source(g)
        ctx.fill()
        ctx.set_source_rgba(*dark, 0.8)
        ctx.set_line_width(max(0.6, W_ * 0.12))
        ctx.move_to(0, 0)
        ctx.line_to(L * 0.92, 0)
        ctx.stroke()
        ctx.restore()

    for k in range(n):
        lean = (k - (n - 1) / 2) * 0.35 + r.uniform(-0.1, 0.1)
        hh = h * r.uniform(0.75, 1.1)
        bx = x + (k - (n - 1) / 2) * w * 0.8
        tx = bx + math.sin(lean) * hh + sway * (hh / 100.0)
        ty = y + math.cos(lean) * hh
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        size = w * 2.5 + hh * 0.12
        if top != "crystals":                                           # a stem that tapers (thick at the foot, as weight needs)
            c1, c2 = (bx, y + hh * 0.4), (tx - sway * 0.3, y + hh * 0.7)

            def bez(u):
                a_, b_ = (1 - u) ** 3, 3 * (1 - u) ** 2 * u
                c_, d_ = 3 * (1 - u) * u * u, u ** 3
                return (a_ * bx + b_ * c1[0] + c_ * c2[0] + d_ * tx, a_ * y + b_ * c1[1] + c_ * c2[1] + d_ * ty)
            pts = [bez(i / 10) for i in range(11)]
            wid = [max(0.8, w * 0.55 * (1 - 0.6 * i / 10)) for i in range(11)]
            left, right = [], []
            for i, (px, py) in enumerate(pts):
                qx, qy = pts[min(10, i + 1)] if i < 10 else pts[i]
                ox, oy = pts[max(0, i - 1)]
                dx, dy = qx - ox, qy - oy
                L_ = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / L_ * wid[i], dx / L_ * wid[i]
                left.append((px + nx, py + ny))
                right.append((px - nx, py - ny))
            ctx.move_to(*left[0])
            for q in left[1:]:
                ctx.line_to(*q)
            for q in reversed(right):
                ctx.line_to(*q)
            ctx.close_path()
            g = cairo.LinearGradient(bx - w, y, bx + w, y)
            g.add_color_stop_rgb(0, *[c * 0.55 for c in col])
            g.add_color_stop_rgb(0.45, *[c * 0.85 for c in col])
            g.add_color_stop_rgb(1, *[c * 0.5 for c in col])
            ctx.set_source(g)
            ctx.fill()
            if top in ("leaves", "fronds") and hh > 60:                 # side leaves up a tall stem
                for j in range(2, 8, 2):
                    px, py = pts[j]
                    side = 1 if (j // 2) % 2 else -1
                    leaf(px, py, math.pi / 2 - side * (0.9 + r.uniform(-0.2, 0.2)) + sway * 0.01, size * 0.55, size * 0.18)
        ctx.set_source_rgb(*col)
        if top == "leaves":
            for j in range(6):
                a = math.pi / 2 + (j - 2.5) * 0.5 + r.uniform(-0.12, 0.12)
                leaf(tx, ty, a + sway * 0.01, size * r.uniform(0.85, 1.15) * 1.6, size * 0.38)
        elif top == "balls":
            for j in range(r.randint(3, 6)):
                ctx.arc(tx + r.uniform(-1, 1) * size, ty + r.uniform(-0.3, 1.0) * size, size * r.uniform(0.35, 0.6),
                        0, 2 * math.pi)
                ctx.fill()
        elif top == "spikes":
            for j in range(7):
                a = math.pi / 2 + (j - 3) * 0.32
                ctx.move_to(tx - 3, ty)
                ctx.line_to(tx + math.cos(a) * size * 1.4, ty + math.sin(a) * size * 1.4)
                ctx.line_to(tx + 3, ty)
                ctx.fill()
        elif top == "crystals":
            for j in range(r.randint(3, 6)):
                a = math.pi / 2 + r.uniform(-0.7, 0.7)
                L = hh * r.uniform(0.5, 1.0)
                ww = w * r.uniform(0.4, 0.8)
                ca, sa = math.cos(a), math.sin(a)
                ctx.move_to(bx - sa * ww, y + ca * ww * 0.2)
                ctx.line_to(bx + ca * L - sa * ww * 0.3, y + sa * L)
                ctx.line_to(bx + ca * L * 1.15, y + sa * L * 1.15)
                ctx.line_to(bx + ca * L + sa * ww * 0.3, y + sa * L)
                ctx.line_to(bx + sa * ww, y - ca * ww * 0.2)
                ctx.close_path()
                ctx.set_source_rgba(*col, 0.85)
                ctx.fill()
            tx, ty = bx, y + hh * 0.8
        elif top == "fronds":
            ctx.set_line_width(max(1.0, w * 0.4))
            for j in range(6):
                a = math.pi / 2 + (j - 2.5) * 0.45
                ctx.move_to(tx, ty)
                ctx.curve_to(tx + math.cos(a) * size, ty + math.sin(a) * size * 1.2, tx + math.cos(a) * size * 1.8,
                             ty + math.sin(a) * size * 0.6, tx + math.cos(a) * size * 2.2, ty - size * 0.3)
                ctx.stroke()
        elif top == "cups":
            for j in (-1, 1):
                ctx.move_to(tx, ty)
                ctx.curve_to(tx + j * size, ty + size * 0.2, tx + j * size * 1.2, ty + size, tx + j * size * 0.3,
                             ty + size * 1.1)
                ctx.close_path()
                ctx.fill()
        else:                                                            # fan: ribs that hold it open
            ctx.move_to(tx, ty)
            ctx.arc(tx, ty, size * 1.4, math.pi * 0.15, math.pi * 0.85)
            ctx.close_path()
            g = cairo.RadialGradient(tx, ty, 0, tx, ty, size * 1.4)
            g.add_color_stop_rgb(0, *dark)
            g.add_color_stop_rgb(1, *light)
            ctx.set_source(g)
            ctx.fill()
            ctx.set_source_rgba(*dark, 0.8)
            ctx.set_line_width(max(0.6, w * 0.15))
            for j in range(7):
                a = math.pi * (0.18 + 0.64 * j / 6)
                ctx.move_to(tx, ty)
                ctx.line_to(tx + math.cos(a) * size * 1.35, ty + math.sin(a) * size * 1.35)
            ctx.stroke()
        if e.get("glow") or top in ("balls", "spikes", "cups"):          # bright tips
            ctx.set_source_rgb(*tip)
            ctx.arc(tx, ty + size * 0.2, max(2.0, size * 0.22), 0, 2 * math.pi)
            ctx.fill()
            if e.get("glow"):
                g = cairo.RadialGradient(tx, ty, 0, tx, ty, size * 2.2)
                g.add_color_stop_rgba(0, *tip, 0.45)
                g.add_color_stop_rgba(1, *tip, 0)
                ctx.set_source(g)
                ctx.arc(tx, ty, size * 2.2, 0, 2 * math.pi)
                ctx.fill()
                from .nightlights import add_device
                add_device(ctx, tx, ty, size * 4, tip, 0.35, kind="plant")
        if e.get("vine"):
            ctx.set_source_rgb(*[c * 0.6 for c in col])
            ctx.set_line_width(max(1.0, w * 0.25))
            ctx.move_to(tx, ty)
            for j in range(6):
                ctx.line_to(tx + math.sin(j * 1.3 + sway * 0.05) * size * 0.4, ty - j * hh * 0.12)
            ctx.stroke()


_PF = {}


def plant_faces(e):
    """🌿 the same plant as a real 3D shape (for the 3D world): tapering stems spread round the foot, and its top
    (leaves / balls / spikes / crystals / fronds / cups / fan) built from solids - lit by the scene's sun, seen from
    any side. Cached per plant (built once). Units: story units, foot at (0, 0, 0)."""
    from .code3d import Pen3
    s_ = float(e.get("scale", 1.0))
    key = (int(e.get("seed", 1)), e.get("top"), int(e.get("stems", 1)), round(float(e.get("height", 120)) * s_),
           round(float(e.get("width", 12)) * s_), e.get("colour"), e.get("tip"), bool(e.get("glow")))
    got = _PF.get(key)
    if got is not None:
        return got
    h, w = float(e.get("height", 120)) * s_, float(e.get("width", 12)) * s_
    col, tip = e.get("colour", "#3f9142"), e.get("tip", "#ffd166")
    rgb = _rgb(col)
    dark = "#%02x%02x%02x" % tuple(int(c * 255 * 0.62) for c in rgb)
    r = random.Random(int(e.get("seed", 1)))
    n, top = int(e.get("stems", 1)), e.get("top", "leaves")
    pen = Pen3(int(e.get("seed", 1)))
    size = w * 2.5 + h * 0.12
    for k in range(n):
        az = 2 * math.pi * k / max(1, n) + r.uniform(-0.4, 0.4)        # stems spread round the foot
        lean = (0.0 if n == 1 else 0.35) + r.uniform(-0.08, 0.08)
        hh = h * r.uniform(0.75, 1.1)
        tx, tz = math.sin(lean) * hh * math.cos(az), math.sin(lean) * hh * math.sin(az)
        ty = math.cos(lean) * hh
        if top == "crystals":                                           # mineral spires: no stem
            for j in range(r.randint(3, 6)):
                a_, L = r.uniform(-0.6, 0.6), hh * r.uniform(0.5, 1.0)
                b_ = r.uniform(0, 2 * math.pi)
                p0 = (k * w * 0.6, 0.0, 0.0)
                p1 = (p0[0] + math.sin(a_) * L * math.cos(b_), L * math.cos(a_), math.sin(a_) * L * math.sin(b_))
                pen.tube([p0, p1], [w * r.uniform(0.4, 0.8), w * 0.05], c=col, sides=5, smooth=False)
            continue
        mid = (tx * 0.35, ty * 0.55, tz * 0.35)
        pen.tube([(0, 0, 0), mid, (tx, ty, tz)], [w * 0.55, w * 0.38, w * 0.22], c=dark, sides=7, smooth=True)
        if top in ("leaves", "fronds") and hh > 60:                     # side leaves up a tall stem
            for j in range(3):
                f_ = 0.3 + 0.18 * j
                p = (tx * f_ * 0.7, ty * f_, tz * f_ * 0.7)
                pen.push()
                pen.move(*p)
                pen.turn(r.uniform(0, 360))
                pen.roll(25)
                pen.ellipsoid(size * 0.3, 0, 0, rx=size * 0.3, ry=size * 0.04, rz=size * 0.1, c=col, rings=3, sides=6)
                pen.pop()
        pen.push()
        pen.move(tx, ty, tz)
        if top == "leaves":                                             # a rosette of long leaves, drooping a little
            for j in range(7):
                pen.push()
                pen.turn(j * 360 / 7 + r.uniform(-12, 12))
                pen.roll(r.uniform(-25, 5))
                L = size * r.uniform(0.75, 1.0)
                pen.ellipsoid(L, 0, 0, rx=L, ry=size * 0.05, rz=size * 0.24, c=col, rings=4, sides=8)
                pen.pop()
        elif top == "balls":
            for j in range(r.randint(3, 6)):
                pen.sphere(r.uniform(-1, 1) * size * 0.6, r.uniform(-0.3, 0.8) * size, r.uniform(-1, 1) * size * 0.6,
                           r=size * r.uniform(0.35, 0.55), c=col, rings=5, sides=9)
        elif top == "spikes":
            for j in range(9):
                pen.push()
                pen.turn(j * 40)
                pen.roll(r.uniform(25, 70))
                pen.cone(0, 0, 0, r=w * 0.35, h=size * 1.4, c=col, sides=5)
                pen.pop()
        elif top == "fronds":                                           # arching fronds
            for j in range(7):
                a_ = j * 2 * math.pi / 7
                ca, sa = math.cos(a_), math.sin(a_)
                pts = [(0, 0, 0), (ca * size, size * 0.6, sa * size), (ca * size * 1.9, size * 0.2, sa * size * 1.9),
                       (ca * size * 2.3, -size * 0.5, sa * size * 2.3)]
                pen.tube(pts, [w * 0.25, w * 0.2, w * 0.15, w * 0.05], c=col, sides=5, smooth=True)
        elif top == "cups":                                             # open cups facing the sky (they catch rain / light)
            for j in (-1, 1):
                pen.push()
                pen.move(j * size * 0.5, size * 0.2, 0)
                pen.roll(180)
                pen.cone(0, -size * 0.9, 0, r=size * 0.55, h=size * 0.9, c=col, sides=10)
                pen.pop()
        else:                                                           # fan: a broad, thin disc held up to the light
            pen.push()
            pen.turn(r.uniform(0, 180))
            pen.ellipsoid(0, size * 0.7, 0, rx=size * 1.3, ry=size * 0.8, rz=size * 0.06, c=col, rings=5, sides=12)
            pen.pop()
        if e.get("glow") or top in ("balls", "spikes", "cups"):          # bright tips / fruit
            pen.sphere(0, size * 0.2, 0, r=max(2.0, size * 0.2), c=tip, rings=4, sides=7)
        pen.pop()
    faces = pen.faces
    while len(_PF) > 300:
        _PF.pop(next(iter(_PF)))
    _PF[key] = faces
    return faces

def _rgb(c):
    if isinstance(c, (tuple, list)):
        return tuple(c[:3])
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


# ============================================================================ creatures
KG_BASE = {"elephant": 4000, "cow": 600, "horse": 500, "bear": 300, "tiger": 200, "deer": 90, "pig": 100, "goat": 50, "dog": 25,
           "fox": 7, "cat": 4, "rabbit": 2, "snake": 15, "parrot": 0.4, "crow": 0.5, "pigeon": 0.35, "eagle": 5}
KG_REF = {"elephant": 2.7, "cow": 1.4, "horse": 1.4, "rabbit": 0.4, "cat": 0.45, "fox": 0.5}


def kg_of(c, young=False):
    """the weight (kg) of a kind (the same rule as the walk: its base animal scaled by size³ and girth)"""
    return KG_BASE.get(c.get("base"), 60) * ((c.get("size") or 1) * (0.55 if young else 1) / KG_REF.get(c.get("base"), 1)) ** 3 * (c.get("girth") or 1)


def sleep_of(c):
    """😴 how much of its day a kind sleeps (15.6), from its body: small animals burn energy fast (Kleiber: metabolism ∝
    mass^-¼ per kg) and sleep long; big grazers must eat most of the day and sleep little; hunters sleep long after a
    meal; herd animals take turns (less each); legless cold-blooded hunters rest most of the time"""
    if c.get("serpent"):
        return {"share": 0.7, "why": "cold-blooded: it needs little food - it rests most of the day"}
    kg = max(0.05, kg_of(c))
    hunter = c.get("base") in HUNTER_BASES and not c.get("fly")
    sh = clamp(0.62 * kg ** -0.1 * (1.25 if hunter else 1.0) * (0.8 if c.get("herd") else 1.0), 0.12, 0.8)
    why = ("a hunter: it sleeps long between meals" if hunter else "a big grazer: it must eat most of the day" if kg > 200
           else "small: it burns energy fast and sleeps a lot" if kg < 5 else "sleeps a middling share")
    return {"share": round(sh, 2), "kg": round(kg, 1), "why": why + (" (the herd takes turns keeping watch)" if c.get("herd") else "")}


# 🌍 today's Earth: its real animals, with their real colours and sizes (size: 1 ≈ a big dog's body)
EARTH_ANIMALS = [  # base, size, fur, belly, pattern, sound, herd, count, why
    ("deer", 1.3, "#8b5a2b", "#e9dcc6", "spots", "bleat", True, 4, "a grazer on long thin legs: it runs from danger (spotted deer, chital)"),
    ("cow", 1.9, "#efe9df", "#ffffff", None, "moo", True, 3, "a big grazer: four stomachs to get the food out of grass"),
    ("goat", 0.8, "#4a3b30", "#d9cbb8", None, "bleat", True, 4, "a small grazer and browser: it eats leaves too, and climbs"),
    ("fox", 0.75, "#b5552a", "#efe3d3", None, "howl", False, 1, "a small hunter (fox, jackal): it catches rabbits and mice by smell and hearing"),
    ("rabbit", 0.32, "#9c8a74", "#efe8dc", None, "squeak", False, 3, "small and fast-breeding: the hunters' everyday food; it hides in a burrow"),
    ("pigeon", 0.3, "#8e9aa8", "#c9d1da", None, "coo", False, 4, "a bird: hollow bones and feathers - light enough for wings to lift it"),
    ("crow", 0.35, "#1f1f22", "#3a3a3f", None, "caw", False, 3, "a clever bird: it eats almost anything, and remembers faces"),
]


def _earth_creatures(p):
    out = []
    for i, (base, size, fur, belly, pat, snd, herd, cnt, why) in enumerate(EARTH_ANIMALS):
        fly = base in BIRD_BASES
        c = dict(index=i + 1, fly=fly, base=base, size=size, leg=1.0, girth=1.0, fur=fur, belly=belly, pattern=pat, sound=snd,
                 furry=False, lizard=False, jelly=False, herd=herd, shy=size < 0.8 and base != "fox", count=cnt)
        if fly:                                                             # the real bodies, not invented ones
            c["body"] = dict(kind="flyer", wings=2, wing="feather", span=2.4, flap=round(9 / math.sqrt(size), 1), glide=False, eyes=2,
                             eye_size="normal", stalks=False, mouth="beak", extras=[], why=[why])
        else:
            hunter = base in HUNTER_BASES
            c["body"] = dict(kind="walker", legs=4, neck="long" if base == "deer" else "short", head="small" if base == "rabbit" else "normal",
                             shape="long" if base in ("deer", "fox") else "round", eyes=2, eye_size="normal", stalks=False, side_eyes=not hunter,
                             mouth="jaws" if hunter else "snout", extras=["horns"] if base in ("deer", "cow", "goat") else [],
                             tail="long" if base in ("fox", "cow") else "short", arms="none", why=[why])
        c["chem"] = creature_chem(p, c)
        out.append(c)
    sn = dict(index=len(out) + 1, fly=False, base="snake", size=0.9, leg=1.0, girth=0.3, fur="#4b4232", belly="#d8c9a3", pattern="spots",
              sound="hiss", furry=False, lizard=False, jelly=False, herd=False, shy=True, count=1, serpent=True, venom=True)
    sn["body"] = dict(kind="walker", legs=0, neck="none", head="normal", shape="long", eyes=2, eye_size="normal", stalks=False, side_eyes=False,
                      mouth="fangs", extras=[], tail="none", why=["a cobra: it bites with venom and waits", "cold-blooded: it basks in the sun to warm up"])
    sn["chem"] = creature_chem(p, sn)
    out.append(sn)
    return out


def creature_kinds(p):
    """3-5 kinds of creature: dicts with the species settings (see the module doc)"""
    if p.get("solar") == "earth" and not p.get("era"):
        return _earth_creatures(p)
    if p["air"] == "none" or not p.get("life") or p.get("solar"):
        return []
    r = _rng("creatures", _key(p))
    g = g_rel(p)
    Tc = p["temperature_c"]
    thick = p["air"] == "thick" or (p.get("pressure") or 1.0) > 3
    gas = p.get("gas")
    n = r.randint(3, 5)
    if isinstance(p.get("life"), dict) and p["life"].get("creatures") is not None:    # planet data: how many kinds
        try:
            n = int(clamp(int(p["life"]["creatures"]), 0, 5))
        except (TypeError, ValueError):
            pass
        if n == 0:
            return []
    flyers = (n if gas else max(1, int(n * (0.6 if thick else 0.3))))
    hue0 = r.random()
    out = []
    for i in range(n):
        fly = i < flyers
        size = math.exp(r.uniform(math.log(0.3), math.log(3.2)))          # tiny .. elephant-big
        size = min(size, clamp(3.2 / g, 0.6, 4.5))                          # the square-cube law: bones must hold the weight (∝ size³·g)
        if fly:
            size = min(size, fly_max(p))                                     # wings must lift it: thick air / weak gravity
            base = r.choice(BIRD_BASES)
        elif size > 2.2:
            base = r.choice(("elephant", "cow", "horse"))
        elif size < 0.6:
            base = r.choice(("rabbit", "cat", "fox"))
        else:
            base = r.choice(QUAD_BASES)
        leg = clamp(1.0 / g ** 0.45, 0.55, 1.8)                             # weak gravity: long legs; strong: short
        girth = clamp(g ** 0.35, 0.7, 1.6) * (1.25 if Tc < -5 else (0.85 if Tc > 35 else 1.0))
        hue = (hue0 + i * 0.618 + r.uniform(-0.05, 0.05)) % 1.0         # every kind its own colour
        fur = _hsv(hue, r.uniform(0.3, 0.8), r.uniform(0.45, 0.9))
        if Tc > 35 and not fly:                                             # hot: low, lizard-like greens / browns
            fur = _hsv(r.choice((0.25, 0.3, 0.08, 0.1)), 0.6, 0.55)
            leg *= 0.7
        if "red" in p.get("star_kind", ""):
            fur = _hsv(hue, 0.45, 0.5)                                      # a red sun: dim, dark colours
        belly = _hsv(hue + 0.05, 0.25, 0.92)
        out.append(dict(index=i + 1, fly=fly, base=base, size=round(size, 2), leg=round(leg, 2),
                        girth=round(girth, 2), fur=fur, belly=belly,
                        pattern=r.choice((None, None, "spots", "stripes")) if not fly else None,
                        sound=r.choice(SOUNDS), furry=Tc < -5, lizard=Tc > 35 and not fly, jelly=bool(gas),
                        herd=not fly and size > 0.8, shy=size < 0.8, count=1 if size > 2.0 else r.randint(2, 4)))
        if out[-1]["furry"] and not fly and stable_hash(f"panda|{_key(p)}|{i}") % 100 < 35:
            out[-1].update(pattern="panda", fur="#f1efe8", belly="#ffffff")   # 🐼 bold black and white: hard to see against snow and dark shade
        out[-1]["body"] = body_plan(p, out[-1])
        if out[-1]["pattern"] == "panda":
            out[-1]["body"]["why"] = list(out[-1]["body"]["why"]) + ["black and white coat: it breaks up its outline on snow and in dark shade (camouflage)"]
        out[-1]["chem"] = creature_chem(p, out[-1])
    # 🐭 small, fast-breeding prey: wherever there are hunters on the ground, small burrowers fill the bottom of the food
    # chain (as mice, voles and rabbits do on Earth) - small enough to hide in a hole, many young, the hunters' everyday
    # snack; how small follows gravity (bones and muscles: smaller where gravity is strong)
    _ensure_prey(p, out, gas, g, Tc, r, hue0)
    # 🐍 legless hunters: a long thin body has no legs to break, so gravity barely limits it - it slides on its whole belly
    # (strong gravity only makes it lie flatter); it goes where legs cannot: through gaps, up rough trunks, into water,
    # and down the burrows of animals as wide as itself. It is cold-blooded, so a cold world keeps it small and slow
    # (Earth: no snakes where summers stay cold; the biggest ones lived in the hottest jungles); small ones kill with
    # venom (too thin to squeeze), big ones squeeze (constrict). They need prey on the ground to live on.
    if not gas and 2 <= Tc <= 55 and any(not c["fly"] for c in out):
        warm_cap = clamp(Tc / 10.0, 0.3, 3.0)                              # warmth lets a cold-blooded body grow big
        grav_cap = clamp(4.5 / math.sqrt(g), 0.8, 4.0)
        prey_small = min([c["size"] for c in out if not c["fly"]] or [0.5])
        kinds_s = [("small", clamp(prey_small * r.uniform(1.4, 2.2), 0.3, 0.8))]
        if Tc >= 22 and g <= 1.6 and any(not c["fly"] and 0.6 <= c["size"] <= 2.2 and c["base"] not in HUNTER_BASES for c in out):
            kinds_s.append(("big", r.uniform(1.6, 2.8)))
        ground_c = (p.get("colours") or {}).get("ground") or "#8a7a5a"
        for kind, sz in kinds_s:
            sz = round(min(sz, warm_cap, grav_cap), 2)
            if kind == "big" and sz < 1.2:
                continue                                                  # (too cold / heavy here for a giant one)
            venom = sz < 1.2
            hue = (hue0 + (0.55 if kind == "small" else 0.8)) % 1.0
            sn = dict(index=len(out) + 1, fly=False, base="snake", size=sz, leg=1.0, girth=round(clamp(0.3 * g ** 0.15, 0.25, 0.4), 2),
                      fur=_mix_hex(ground_c, _hsv(hue, 0.5, 0.45), 0.45), belly=_hsv(hue + 0.08, 0.2, 0.8),
                      pattern=r.choice(("stripes", "spots", None)), sound="hiss", furry=False, lizard=False, jelly=False, herd=False,
                      shy=kind == "small", count=1, serpent=True, venom=venom)
            why = ["no legs: a long body slides on its belly - nothing for gravity to break, so it can be long even here" if g > 1.3 else
                   "no legs: it slides on its belly, through gaps and up rough trunks where legs cannot go",
                   "it tastes the air with its tongue - it finds animals hidden in holes and grass",
                   "thin enough to follow small prey down their burrows" if kind == "small" else "too big for burrows: it waits in water and thick plants",
                   ("venom: too thin to squeeze, it bites and waits" if venom else "it squeezes its prey (constricts) - big enough to eat a grazer"),
                   "cold-blooded: it basks in the sun to warm up and is slow when cold"]
            sn["body"] = dict(kind="walker", legs=0, neck="none", head="small" if kind == "small" else "normal", shape="long", eyes=2,
                              eye_size="normal", stalks=False, side_eyes=False, mouth="fangs" if venom else "jaws", extras=[], tail="none", why=why)
            sn["chem"] = creature_chem(p, sn)
            out.append(sn)
    _ensure_prey(p, out, gas, g, Tc, r, hue0)                              # (a snake too must have something it can swallow)
    # 🎈 dense air carries big floaters: a sac of light gas lifts (ρ_air - ρ_gas)·V - with air ≥ 4 kg/m³ (Earth 1.2) a
    # 2-3 m sac lifts a body the size of a sheep; one flyer kind becomes a drifting balloon (Venus-like / thick worlds)
    rho = _rho_kg(p) if not gas else 0.0
    fl = [c for c in out if c["fly"]]
    if not gas and rho >= 4.0 and fl:
        c = fl[-1]
        c["jelly"] = True
        c["size"] = round(clamp(0.9 + rho / 5.0, 1.2, 3.5), 2)
        c["lift_kg_m3"] = round(rho * 0.93, 2)                             # (hydrogen weighs ~7 % of air)
        c["body"] = body_plan(p, c)
    for c in out:                                   # 😴 each kind's sleep, kept on the server (the walk uses this number)
        c["sleep"] = sleep_of(c)
    era = p.get("era")
    if era == "jurassic":                         # 🦕 big scaly reptiles: plant-eating giants and their hunters
        for c in out:
            if not c["fly"] and not c.get("small_prey"):
                c.update(size=round(min(4.5, c["size"] * 1.7), 2), furry=False, lizard=True, pattern=c.get("pattern") if c.get("pattern") != "panda" else None)
    elif era == "ice_age":                        # 🦣 thick fur, big bodies keep warm (less skin per kg)
        for c in out:
            if not c["fly"]:
                c.update(size=round(min(4.0, c["size"] * 1.25), 2), furry=True, lizard=False)
    elif era == "carboniferous":                  # 🐸 the land animals were amphibians and early reptiles - small to mid
        for c in out:
            if not c["fly"]:
                c.update(size=round(min(1.6, c["size"]), 2), furry=False)
    return out


def life_kind(p):
    """which kind of life the physics allows here, with an honesty label (see the TODO's table)"""
    from . import atmos
    a = atmos.air(p)
    T = p["temperature_c"]
    if a.get("liquid") == "water":
        return {"kind": "carbon + water life (like ours)", "label": "✅ known", "solvent": "water"}
    if a.get("liquid", "") and a["liquid"].startswith("methane"):
        return {"kind": "carbon life in liquid methane", "label": "🔬 a serious scientific idea", "solvent": "methane"}
    if -80 < T < -33 and "NH₃" in (a.get("gases") or {}):
        return {"kind": "carbon life in liquid ammonia", "label": "🔬 a serious scientific idea", "solvent": "ammonia"}
    if p.get("water") == "ice":
        return {"kind": "microbes in a dark ocean under the ice, living off rock chemistry at hot vents", "label": "✅ real on Earth", "solvent": "water"}
    if T < -100:
        return {"kind": "silicon-based life (very unlikely)", "label": "🔬 a scientific idea", "solvent": "methane / nitrogen"}
    return {"kind": "none (no liquid to live in)", "label": "-", "solvent": None}


def creature_chem(p, c):
    """what this kind breathes, its blood, metal-hardened parts, a magnetic sense - from the planet's air, elements,
    field (real biology: iron-red / copper-blue blood, iron-plated shells, magnetite compasses)"""
    from . import atmos, elements, shields
    a = atmos.air(p)
    gas = a.get("gases") or {}
    o2 = gas.get("O₂", 0) * a.get("pressure", 1.0)                          # % × bar ≈ oxygen pressure ×100
    T = p["temperature_c"]
    comp = elements.composition(p)
    fld = shields.shields(p).get("field", 0)
    if o2 >= 10:
        breathes, blood = "oxygen in, CO₂ out (like us)", ("red", "iron (haemoglobin) carries its oxygen")
        if T < 5:
            blood = ("blue", "copper (haemocyanin) carries its oxygen - it works better in the cold")
    elif o2 > 0.5:
        breathes, blood = "thin oxygen in, CO₂ out", ("blue", "copper (haemocyanin): better with little oxygen")
    else:
        breathes, blood = "no oxygen - it lives off chemistry (sulfur / methane) like Earth's vent microbes", ("colourless", "no oxygen to carry")
    bp = c.get("body") or {}
    iron = comp.get("metallicity", 0) > 0.2 and "shell" in (bp.get("extras") or [])
    sense = fld >= 0.3 and (c.get("fly") or r_choice(p, c))
    return {"breathes": breathes, "blood": blood[0], "blood_why": blood[1], "iron_shell": bool(iron),
            "magnetic_sense": bool(sense), "label": "✅ real on Earth"}


def r_choice(p, c):
    return _rng("magsense", _key(p), c["index"]).random() < 0.3


# ---------------------------------------------------------------------------- body plans (shaped by physics)
def _ensure_prey(p, out, gas, g, Tc, r, hue0):
    """🐭 small, fast-breeding prey wherever hunters live on the ground (as mice, voles and rabbits do on Earth): small
    enough to hide in a burrow, many young - sized so the SMALLEST hunter (or snake) can catch it (well under its own
    size); nothing is added when such a plant-eater already exists (half the planets used to have hunters with
    nothing they could eat). How small follows gravity (bones and muscles: smaller where gravity is strong)."""
    is_h = lambda c: (c["base"] in HUNTER_BASES or c["base"] == "snake") and not c["fly"]
    hs = min([c["size"] for c in out if is_h(c)] or [0.0])
    if gas or not hs or any(not c["fly"] and not is_h(c) and c["size"] < 0.7 * hs for c in out):
        return
    hue = (hue0 + 0.37) % 1.0
    ground_c = (p.get("colours") or {}).get("ground") or "#8a7a5a"
    sm = dict(index=len(out) + 1, fly=False, base="rabbit", size=round(clamp(min(0.3 / math.sqrt(g), 0.55 * hs), 0.1, 0.45), 2),
              leg=round(clamp(1.0 / g ** 0.45, 0.55, 1.6), 2), girth=round(clamp(g ** 0.35, 0.7, 1.5), 2),
              fur=_mix_hex(ground_c, _hsv(hue, 0.3, 0.5), 0.35), belly=_hsv(hue + 0.05, 0.15, 0.85), pattern=None,
              sound="squeak", furry=Tc < 10, lizard=Tc > 35, jelly=False, herd=False, shy=True, count=r.randint(4, 8), small_prey=True)
    sm["body"] = body_plan(p, sm)
    sm["body"]["why"] = list(sm["body"].get("why") or []) + ["small and quick to breed: the hunters' everyday snack - it lives in a burrow and runs for cover",
                                                              "its fur matches the ground (camouflage)"]
    sm["chem"] = creature_chem(p, sm)
    out.append(sm)


HUNTER_BASES = ("tiger", "fox", "dog", "cat", "bear")


def _rho_kg(p):
    """the air's real density in kg/m³: ρ = 1.2 · (p / 1 bar) · (288 K / T) (an Earth-like mean molar mass)"""
    return air_density(p) * 1.2 * 288.0 / max(60.0, float(p.get("temperature_c") or 15) + 273.15)


def air_density(p):
    """the air's density next to Earth's (1): from the pressure in bar, 0 with no air"""
    if p["air"] == "none":
        return 0.0
    pr = p.get("pressure")
    if pr is None:
        pr = 10.0 if p["air"] == "thick" else 1.0
    return clamp(float(pr), 0.01, 100.0)


def fly_max(p):
    """the biggest size (1 = a medium animal) that can still fly here. Lift grows with the air's density and the
    wing area (size^2), weight with size^3 x gravity -> the largest flyer ~ sqrt(density / gravity). Earth: ~1.3
    (the biggest flying animals ever were about that); thick air + weak gravity: elephant-sized flyers."""
    rho = air_density(p)
    if rho <= 0:
        return 0.0
    return round(clamp(1.3 * math.sqrt(rho / g_rel(p)), 0.25, 3.2), 2)


def _pick(r, weights):
    tot = sum(w for _, w in weights)
    x = r.random() * tot
    for v, w in weights:
        x -= w
        if x <= 0:
            return v
    return weights[-1][0]


def body_plan(p, c):
    """What this kind's body is made of - legs, neck, head, body, eyes, mouth, extras - picked by the planet's seed
    but only from what its physics allows (separate random stream, so the rest of the creature stays the same):
      strong gravity  more legs to spread the weight (6 / 8), no long necks, big heads sit on the body (no neck)
      weak gravity    2 legs (hoppers / runners), long thin necks, bigger heads are fine
      hot             flat, low bodies; cold: round ones (less skin to lose heat through)
      a dim red sun   big eyes (more light in); hunters: eyes to the front, plant-eaters: to the sides
      flyers          2 or 4 wings, feathers or skin, big ones glide and flap slowly; gas giants: floating balloons"""
    r = _rng("body", _key(p), c["index"])
    g = g_rel(p)
    Tc = p["temperature_c"]
    size = c["size"]
    dim = "red" in p.get("star_kind", "")
    hunter = c["base"] in HUNTER_BASES and not c["fly"]
    eyes = _pick(r, [(2, 8), (1, 0.6), (3, 0.8), (4, 0.7)])
    eye_size = "big" if dim or c.get("sound") == "hoot" else _pick(r, [("normal", 3), ("small", 1), ("big", 1)])
    why = []
    if c["fly"]:
        if c.get("jelly"):
            return dict(kind="balloon", wings=0, eyes=eyes, eye_size=eye_size, stalks=False, mouth="tube", extras=["tentacles"],
                        why=["floats: a gas giant has no ground - a gas bag lifts it"] if p.get("gas") else
                        [f"floats: the air here is so dense ({_rho_kg(p):.1f} kg/m³, Earth 1.2) that a sac of hydrogen it makes lifts "
                         f"~{_rho_kg(p) * 0.93 * 4.19 * (0.5 * size) ** 3:.0f} kg - it drifts with the wind"])
        big = size > 1.4
        wings = 4 if (not big and r.random() < 0.3) else 2
        wing = "skin" if r.random() < 0.4 else "feather"
        if big:
            why.append(f"big wings: the air here lets something this size fly (the biggest flyer here: size {fly_max(p)})")
        if wings == 4:
            why.append("4 wings: quick turns in the air")
        return dict(kind="flyer", wings=wings, wing=wing, span=round(2.2 + (1.2 if big else 0) + r.uniform(-0.3, 0.4), 2),
                    flap=round(clamp(9 / math.sqrt(max(0.3, size)), 2.5, 12), 1), glide=big, eyes=eyes if eyes < 3 else 2,
                    eye_size=eye_size, stalks=False, mouth="beak" if wing == "feather" else _pick(r, [("jaws", 1), ("beak", 1)]),
                    extras=[e for e in ("crest", "tail_fan") if r.random() < 0.3], why=why)
    # walkers: legs first (weight!)
    if g > 1.6:
        lw = [(4, 2), (6, 3), (8, 2)]
    elif g < 0.6:
        lw = [(2, 3), (4, 2), (6, 1), (0, 0.6)]
    else:
        lw = [(4, 5), (6, 1.2), (2, 1.0), (8, 0.7), (0, 0.5)]
    if size > 2.2:
        lw = [x for x in lw if x[0] >= 4 or g < 0.6]                    # heavy: never on 2 legs (or none) unless gravity is weak
    if size > 2.0 and g <= 1.6:
        lw = [x for x in lw if x[0] != 8]                               # 8 thin legs: only small ones (or a heavy world)
    if c.get("furry"):
        lw = [x for x in lw if x[0] != 0]
    legs = _pick(r, lw)
    head = _pick(r, [("normal", 5), ("big", 2), ("small", 1.5)])
    if legs == 0:
        neck, body = "none", "long"
    else:
        nw = [("short", 4), ("none", 1.5 + 2 * max(0, g - 1)), ("long", 2.5 if g < 1.3 else 0)]
        if head == "big" and g > 1.0:
            nw = [("none", 3), ("short", 2)]                            # a heavy head needs no lever arm
        neck = _pick(r, nw)
        bw = [("round", 3 + (3 if Tc < -5 else 0)), ("long", 2 + (2 if legs >= 6 else 0)), ("flat", 1 + (3 if Tc > 35 else 0)),
              ("tall", 1.5 if g < 0.8 else 0.2)]
        body = _pick(r, bw)
    if legs == 0:
        why.append("no legs: it slides on its belly like a snake")
    elif legs >= 6 and g > 1.3:
        why.append(f"{legs} legs: strong gravity - more legs share the weight")
    elif legs >= 6:
        why.append(f"{legs} legs: steady on rough ground")
    elif legs == 2 and g < 0.8:
        why.append("2 legs: weak gravity - it hops and runs upright")
    elif legs == 2:
        why.append("2 legs: it runs upright")
    if neck == "long":
        why.append("long neck: weak gravity makes it easy to hold a head up high" if g < 0.8 else "long neck: it reaches high leaves")
    if head == "big" and neck == "none":
        why.append("big head right on the body: no neck to strain")
    if body == "flat" and Tc > 35:
        why.append("flat and low: hides from the heat")
    if body == "round" and Tc < -5:
        why.append("round: keeps its heat in")
    if eye_size == "big" and dim:
        why.append("big eyes: the red sun is dim")
    mouth = (_pick(r, [("jaws", 3), ("fangs", 2)]) if hunter else
             _pick(r, [("snout", 4), ("beak", 1.5), ("round", 1)] + ([("trunk", 2)] if size > 1.5 else [])))
    extras = []
    if not hunter and size > 1.0 and r.random() < 0.45:
        extras.append("horns")
    if legs >= 6 and r.random() < 0.7:
        extras.append("antennae")
    if g > 1.2 and r.random() < 0.35:
        extras.append("shell")
        why.append("a hard shell: falls hurt more where gravity is strong")
    if c.get("shy") and r.random() < 0.4:
        extras.append("spikes")
    if Tc > 30 and r.random() < 0.3:
        extras.append("frill")
        why.append("a frill: it sheds heat")
    tail = "none" if legs == 0 else _pick(r, [("long", 2), ("short", 2), ("club", 0.6 if "shell" in extras else 0.2), ("none", 0.6)])
    arms = "none"
    if legs == 2:                                                       # 🐒 two legs: the front pair became arms
        try:
            tall = max([k.get("height", 0) for k in plant_kinds(p)] or [0])
        except Exception:                                               # noqa: BLE001
            tall = 0
        if tall >= 4 and g <= 1.3 and size <= 1.6:
            arms = "long"
            why.append("long arms: tall plants and gravity weak enough to climb - it climbs and swings (like a monkey)")
        else:
            arms = "small"
            why.append("small arms: it holds food with its front pair, the back legs do the walking")
    return dict(kind="walker", legs=legs, neck=neck, head=head, shape=body, eyes=eyes, eye_size=eye_size,
                stalks=r.random() < 0.15 and eyes <= 2, side_eyes=not hunter, mouth=mouth, extras=extras, tail=tail, why=why, arms=arms)


def body_words(c):
    b = c.get("body") or {}
    if not b or b.get("kind") != "walker":
        if b.get("kind") == "flyer":
            return f"{b['wings']} {b['wing']} wings" + (", glides" if b.get("glide") else "")
        return ""
    legs = "no legs (slides)" if b["legs"] == 0 else f"{b['legs']} legs"
    bits = [legs, {"none": "no neck", "short": "", "long": "a long neck"}[b["neck"]],
            {"big": "a big head", "small": "a small head", "normal": ""}[b["head"]],
            f"{b['eyes']} eye" + ("s" if b["eyes"] != 1 else "") + (" on stalks" if b.get("stalks") else "")]
    bits += [{"horns": "horns", "antennae": "antennae", "shell": "a shell", "spikes": "spikes", "frill": "a frill"}[e] for e in b["extras"]]
    return ", ".join(x for x in bits if x)


def species_name(p, c):
    return f"alien_{stable_hash(_key(p)) % 100000}_{c['index']}"


def install(p):
    """register this planet's creatures as species (once per run): [(species name, kind dict)]"""
    from . import animals, registry
    out = []
    for c in creature_kinds(p):
        nm = species_name(p, c)
        if nm not in animals.QUADS and nm not in animals.BIRDS:
            base = animals.canon("cat" if c.get("serpent") else c["base"])
            tbl = animals.QUADS if base in animals.QUADS else animals.BIRDS
            b = tbl[base]
            ref = {"elephant": 2.7, "cow": 1.4, "horse": 1.4, "rabbit": 0.4, "cat": 0.45, "fox": 0.5}.get(c["base"], 1.0)
            S = {"base": "cat" if c.get("serpent") else c["base"], "size": round(c["size"] / (0.45 if c.get("serpent") else ref), 3),   # (size is already "how big" - the base body is only the shape) "fur": c["fur"], "belly": c["belly"],
                 "aliases": [], "kind": "bird" if c["fly"] else ""}
            if not c["fly"]:
                S.update(thigh=b["thigh"] * c["leg"], shin=b["shin"] * c["leg"], girth=b["girth"] * c["girth"],
                         sound=c["sound"])
                if c["pattern"]:
                    S["pattern"] = c["pattern"]
                if c["lizard"]:
                    S.update(ears="none", tail="long")
                bp = c.get("body") or {}                                    # the body plan, as far as a side view shows it
                if bp.get("kind") == "walker":
                    S["neck"] = b["neck"] * {"none": 0.15, "short": 1.0, "long": 2.2}[bp["neck"]]
                    if bp["neck"] == "long":
                        S["neck_angle"] = 62
                    S["head"] = b["head"] * {"big": 1.5, "small": 0.75, "normal": 1.0}[bp["head"]]
                    if "horns" in bp["extras"]:
                        S["horns"] = "curved"
                    if bp["tail"] == "none":
                        S["tail"] = "none"
                    S["legs"] = int(bp.get("legs", 4))                       # 0 / 2 (+ arms) / 4 / 6 / 8 - drawn as the physics made it
                    if S["legs"] == 0:
                        S.update(body=b["body"] * (2.6 if c.get("serpent") else 1.6), girth=b["girth"] * (0.45 if c.get("serpent") else 0.8),
                                 ears="none", neck=b["neck"] * 0.2, tail="long")
                    if S["legs"] == 2 and bp.get("arms") == "long":
                        S["arms"] = "long"
                    if "shell" in bp["extras"]:
                        S["hump"] = 1
            else:
                S["wing"] = c["fur"]
            try:
                registry.install_code_species(nm, S, description=describe_one(c))
            except Exception:                                               # noqa: BLE001
                continue
        out.append((nm, c))
    return out


def describe_one(c):
    size = "tiny" if c["size"] < 0.5 else ("small" if c["size"] < 0.9 else ("big" if c["size"] > 1.6 else
                                                                           "medium-sized"))
    if c["fly"]:
        what = "floating jellyfish-like flyer" if c.get("jelly") else "flyer"
    else:
        what = ("long-legged " if c["leg"] > 1.2 else "short-legged " if c["leg"] < 0.8 else "") + \
            ("furry " if c["furry"] else "") + ("lizard-like " if c["lizard"] else "") + ("snake-like hunter" if c.get("serpent") else "walker")
    bw = body_words(c)
    return f"a {size} {what} ({c['fur']})" + (f" with {bw}" if bw else "") + (", lives in herds" if c["herd"] else "") + \
        (", shy" if c["shy"] else "")


def describe(p):
    cs = creature_kinds(p)
    if not cs:
        return ""
    return "; ".join(f"creature_{c['index']}: {describe_one(c)}" for c in cs)


def populate(p, sc, characters, world_w, char_def):
    """Add this planet's creatures to a scene: characters creature_1 ... (unless the story places them itself
    or says "life": false), standing in the land, with a little life of their own:
      herds     plant-eaters that live in herds come as a group (2-4 adults, the young in the middle), close together,
                walking the same way, then grazing
      flocks    flyers cross the sky together, a little apart
      hunters   if there is a herd, a hunter creeps toward it; the herd sees it and runs (each at its own top speed),
                the hunter chases and gives up when it falls behind (the chase follows speed, not luck)
      shy ones  small shy animals run away from people in the scene
    Up to 12 animals per scene. -> the new scene dict. char_def(cid, spec, i) makes a character."""
    if sc.get("life") is False:
        return sc
    kinds = install(p)
    if not kinds:
        return sc
    sc = dict(sc)
    placed = {c.get("id") for c in (sc.get("characters") or []) if isinstance(c, dict)}
    chars = list(sc.get("characters") or [])
    events = list(sc.get("events") or [])
    r = _rng("herd", _key(p), sc.get("id", ""))
    people = [c for c in chars if isinstance(c, dict) and characters.get(c.get("id")) is not None
              and getattr(characters[c.get("id")], "kind", "") == "human"]
    total, herd_at, hunter_ids = 0, None, []

    def add(cid, nm, idx, spec_extra=None):
        if cid not in characters:
            sp = {"species": nm, "name": f"creature {idx}"}
            sp.update(spec_extra or {})
            characters[cid] = char_def(cid, sp, len(characters))

    for nm, c in kinds:
        cid0 = f"creature_{c['index']}"
        add(cid0, nm, c["index"])
        if cid0 in placed or total >= 12:
            continue
        hunter = (c["base"] in HUNTER_BASES or c.get("serpent")) and not c["fly"]
        if c["fly"]:                                                    # a small flock crosses the sky together
            n = min(1 + r.randint(0, 2), 12 - total)
            to_right = r.random() < 0.5
            x0, z0, t0 = r.uniform(200, world_w - 200), r.uniform(300, 700), r.uniform(0.5, 3.0)
            for k in range(n):
                cid = cid0 if k == 0 else f"{cid0}_{k + 1}"
                add(cid, nm, c["index"])
                chars.append({"id": cid, "x": x0 - k * 90, "z": z0 + r.uniform(-60, 60), "facing": "right" if to_right else "left"})
                events.append({"who": cid, "do": "fly", "to": {"x": world_w + 300 if to_right else -300}, "at": t0 + k * 0.25})
            total += n
        elif c.get("herd") and not hunter:                              # 🐃 a herd: together, the young in the middle
            n = min(max(2, min(4, c.get("count") or 3)), 12 - total)
            gap = 150 * c["size"] + 60
            x0 = r.uniform(300 + gap, world_w - 300 - gap * n)
            z0 = r.uniform(500, 850)
            dx = r.choice((-1, 1)) * r.uniform(150, 320)
            t0 = r.uniform(0.3, 1.5)
            ids = []
            for k in range(n):
                cid = cid0 if k == 0 else f"{cid0}_{k + 1}"
                add(cid, nm, c["index"])
                chars.append({"id": cid, "x": x0 + k * gap + r.uniform(-20, 20), "z": z0 + r.uniform(-50, 50), "facing": "right" if dx > 0 else "left"})
                ids.append(cid)
            if n >= 2 and total + n < 12 and r.random() < 0.75:          # a young one, between the adults
                cid = f"{cid0}_young"
                add(cid, nm, c["index"], {"age": "child"})
                chars.append({"id": cid, "x": x0 + gap * 0.5, "z": z0 + 40, "facing": "right" if dx > 0 else "left"})
                ids.append(cid)
            for cid in ids:
                ch = next(q for q in chars if q.get("id") == cid)
                events.append({"who": cid, "do": "walk", "to": {"x": clamp(ch["x"] + dx, 100, world_w - 100)}, "at": t0 + r.uniform(0, 0.25)})
                events.append({"who": cid, "do": "eat", "at": t0 + 3.5 + r.uniform(0, 1.0)})
            total += len(ids)
            if herd_at is None:
                herd_at = (x0 + gap * (n - 1) / 2 + dx, ids)
        else:                                                           # one alone: wanders and eats (or hunts)
            x = r.uniform(200, world_w - 200)
            chars.append({"id": cid0, "x": x, "z": r.uniform(450, 900), "facing": r.choice(("left", "right"))})
            total += 1
            if hunter:
                hunter_ids.append((cid0, x))
            else:
                events.append({"who": cid0, "do": "walk", "to": {"x": clamp(x + r.uniform(-260, 260), 100, world_w - 100)}, "at": r.uniform(0.3, 2.0)})
                events.append({"who": cid0, "do": "eat", "at": r.uniform(4.0, 7.0)})
                if people and c["size"] < 0.8:                          # 🐭 a small shy one runs from people
                    px = min((q.get("x", 0) for q in people), key=lambda v: abs(v - x))
                    if abs(px - x) < 600:
                        events.append({"who": cid0, "do": "run", "to": {"x": clamp(x + (500 if x > px else -500), 60, world_w - 60)}, "at": r.uniform(1.0, 2.5)})
    for cid, x in hunter_ids:                                           # 🐾 hunters: stalk the herd, it bolts, the chase
        if herd_at is None:
            events.append({"who": cid, "do": "walk", "to": {"x": clamp(x + r.uniform(-200, 200), 100, world_w - 100)}, "at": r.uniform(0.5, 2.5)})
            continue
        hx, ids = herd_at
        away = 1 if hx >= x else -1                                     # the herd runs on, away from the hunter
        t_stalk, t_bolt = r.uniform(1.5, 2.5), None
        events.append({"who": cid, "do": "walk", "to": {"x": clamp(hx - away * 260, 60, world_w - 60)}, "at": t_stalk})
        t_bolt = t_stalk + r.uniform(1.6, 2.4)                          # it is seen
        for hid in ids:
            events.append({"who": hid, "do": "run", "to": {"x": clamp(hx + away * 900, 60, world_w - 60)}, "at": t_bolt + r.uniform(0, 0.3)})
        events.append({"who": cid, "do": "run", "to": {"x": clamp(hx + away * 500, 60, world_w - 60)}, "at": t_bolt + 0.2})
        events.append({"who": cid, "do": "idle", "at": t_bolt + 3.2})  # out of breath: it gives up
        break
    sc["characters"] = chars
    sc["events"] = events
    return sc

def pigment(star_T, air_scatter=1.0, pressure=1.0):
    """🌿 the colour of leaves from the star's light (real chemistry, after the 'photon budget' idea in exoplanet
    biology): photosynthesis needs photons, so pigments evolve to absorb the colours where the most photons arrive at
    the ground (the star's Planck spectrum, minus the blue the air scatters away) - and reflect the rest. Our Sun
    peaks in photons near red: chlorophyll takes red + blue and leaves look green. A cool red dwarf sends mostly red
    and infrared: leaves take everything they can get - nearly black. A hot white / blue star sends lots of blue:
    leaves take the blue and look yellow, orange or red.  -> (hex colour, why)"""
    import math as _m
    T = max(1500.0, float(star_T or 5778))
    h, c, k = 6.626e-34, 2.998e8, 1.381e-23
    bands = {"red": 650e-9, "green": 550e-9, "blue": 450e-9}
    tau = 0.1 * float(air_scatter or 1.0) * max(0.0, float(pressure or 1.0))       # Rayleigh optical depth at 550 nm
    flux = {}
    for nm, lam in bands.items():
        n = (2 * c / lam ** 4) / (_m.exp(min(700.0, h * c / (lam * k * T))) - 1.0)    # photons per band (Planck, photon form)
        flux[nm] = n * _m.exp(-tau * (550e-9 / lam) ** 4)                             # less blue reaches the ground
    top = max(flux.values()) or 1.0
    rel = {b: v / top for b, v in flux.items()}
    if T < 3400:                                                    # a dim red sun: take every photon - dark leaves
        absorb = {"red": 0.95, "green": 0.88, "blue": 0.85}
    else:
        absorb = {b: 0.92 * rel[b] ** 4 for b in bands}             # the peak band is taken hard, the others much less
        top_b = max(rel, key=rel.get)
        absorb[top_b] = 0.92
        absorb["blue"] = max(absorb["blue"], 0.9)                   # blue photons carry the most energy: always used
    refl = {b: 1.0 - a for b, a in absorb.items()}
    col = "#%02x%02x%02x" % tuple(int(max(14, min(255, (refl[x] ** 0.7) * 0.75 * 255))) for x in ("red", "green", "blue"))   # (eyes adapt: a perceptual curve)
    peak = max(rel, key=rel.get)
    why = (f"its star ({T:.0f} K) sends most of its photons as {peak} light: the leaves' pigments soak up the plentiful "
           f"colours and reflect the rest")
    if T < 3400:
        why = f"a dim red star ({T:.0f} K): plants take every photon they can - leaves look almost black"
    return col, why


# ---------------------------------------------------------------- 👽 the people of a civilization (any shape - by physics)
SYL = ("ka", "ri", "zo", "ma", "tu", "ve", "lo", "na", "shi", "ra", "di", "po", "en", "ar", "il", "ku", "tha", "mi", "ox", "ul")


def people_of(p):
    """the beings who built the boats, towns or ruins: their body follows the planet like every animal's does -
      gravity     the square-cube law again: strong gravity -> short, wide, and over ~1.8 g four legs carry the body
                  while two arms are left free (a 'centaur' plan: a tall two-legged body would break or topple);
                  weak gravity -> tall and slender
      thick air   (≥ 10 kg/m³) a body can float: a gas-sac with hanging arms (like a jellyfish of the air)
      warmth      cold -> thick fur, round (less skin per body to lose heat); hot -> thin, long-limbed, pale (sheds heat)
      starlight   a dim red star -> big eyes; a hot blue-white star (strong UV) -> dark skin that blocks it
    their temper: groups differ - some welcome you, some keep away, some attack strangers (planet-wide share fixed by
    the planet); their tools: an ancient people throw spears, an advanced one shoot and fly ships - but only where a
    rocket can leave: the escape speed √(2gR) grows with gravity and size; above ~2.5 g no ship reaches space"""
    civ = p.get("civilization") or "none"
    if civ == "none" or p.get("gas") or not p.get("life"):
        return None
    if p.get("solar") == "earth" and not p.get("era"):          # 🌍 today's Earth: real humans, not invented beings
        return {"name": "locals", "human": True, "plan": "biped", "height": 1.7, "wide": 1.0, "furry": False, "eyes": 0.45,
                "skin": "#c68a5c", "cloth": "#3b6ea5", "limbs": 4, "tech": "modern", "ships": False, "v_esc": 11.2,
                "hostile": 0.0, "friendly": 0.7,
                "why": ["humans: two legs, upright, ~1.7 m - Earth's gravity (1 g) is what our bones grew for",
                        "skin colour follows the sunlight where your family came from: more melanin where the UV is strong",
                        "clothes instead of fur: we make our own warmth (and shade)"]}
    r = _rng("people", _key(p))
    g = g_rel(p)
    Tc = float(p.get("temperature_c") or 15)
    rho = _rho_kg(p)
    starT = float(p.get("star_temp") or 5800)
    why = []
    if rho >= 10.0:                                  # lift = ρ_air·V·g, weight = m·g: g cancels - only the air's density counts
        plan, height = "floater", clamp(1.6 + rho / 20.0, 1.8, 3.2)
        why.append(f"the air is very thick ({rho:.0f} kg/m³ - Earth 1.2): a ~{70 / max(rho, 1):.1f} m³ sac of light gas lifts a whole body - they float, arms hanging below")
    elif g > 1.8:
        plan, height = "centaur", clamp(1.7 / math.sqrt(g), 0.9, 1.4)
        why.append(f"gravity {g:.1f}× Earth: four legs carry the weight and two arms stay free - a tall two-legged body would break or topple")
    elif g < 0.6:
        plan, height = "lanky", clamp(1.75 / math.sqrt(g), 2.2, 3.2)
        why.append(f"weak gravity ({g:.2f}×): bones carry little weight - they grow tall and slender")
    else:
        plan, height = "biped", clamp(1.75 / math.sqrt(g), 1.3, 2.1)
        why.append(f"gravity {g:.2f}× Earth: two legs, upright - about {height:.1f} m tall")
    furry = Tc < 2
    wide = clamp(math.sqrt(g) * (1.25 if furry else 1.0) * (0.85 if Tc > 35 else 1.0), 0.7, 1.7)
    if furry:
        why.append(f"cold ({Tc:.0f} °C): thick fur and a round body - less skin to lose heat through")
    elif Tc > 35:
        why.append(f"hot ({Tc:.0f} °C): thin bodies with long limbs - more skin to shed heat")
    eyes = clamp(0.9 * (5800 / max(2500.0, starT)) ** 1.2, 0.6, 2.2)
    if starT < 4200:
        why.append("a dim red sun: big eyes to catch the light")
    uv = clamp((starT - 4500) / 3000, 0, 1)
    skin_h = r.random()
    skin = _hsv(skin_h, 0.25 + 0.3 * r.random(), clamp(0.85 - 0.55 * uv, 0.25, 0.9))
    if uv > 0.5:
        why.append("a hot sun with strong ultraviolet: dark skin that blocks it")
    cloth = _hsv((skin_h + 0.5) % 1, 0.45, 0.55)
    hostile = round(0.15 + 0.5 * r.random(), 2)                               # share of groups that attack strangers
    friendly = round((1 - hostile) * (0.4 + 0.4 * r.random()), 2)
    R_km = float(p.get("radius_km") or 6371 * math.sqrt(max(0.05, g)))       # (bigger planets: stronger gravity)
    v_esc = math.sqrt(2 * 9.81 * g * R_km * 1000) / 1000
    ships = civ == "advanced" and g <= 2.5
    if civ == "advanced":
        why.append(f"escape speed {v_esc:.1f} km/s (Earth 11.2): " + ("their ships can reach space" if ships else "too strong a pull - no rocket of theirs can leave, their ships stay on the ground"))
    name = "".join(r.choice(SYL) for _ in range(r.randint(2, 3))).capitalize()
    return {"name": name, "plan": plan, "height": round(height, 2), "wide": round(wide, 2), "furry": furry, "eyes": round(eyes, 2),
            "skin": skin, "cloth": cloth, "limbs": 6 if plan == "centaur" else 4, "tech": civ, "ships": ships, "v_esc": round(v_esc, 1),
            "hostile": hostile, "friendly": friendly, "why": why}


# 🎨 the journey's nine galaxies each have their own look, names and a special stone (engine/themes.py)
from . import themes as _themes                                            # noqa: E402
_plant_kinds0, _creature_kinds0, _rock_chemistry0 = plant_kinds, creature_kinds, rock_chemistry


def plant_kinds(p):                                                         # noqa: F811
    return _themes.plants(p, _plant_kinds0(p))


def creature_kinds(p):                                                      # noqa: F811
    return _themes.creatures(p, _creature_kinds0(p))


def rock_chemistry(p):                                                      # noqa: F811
    return _themes.rocks(p, _rock_chemistry0(p))
