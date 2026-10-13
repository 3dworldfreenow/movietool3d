"""🎨 Each galaxy of the journey has its own nature (engine/saga.py's nine): every world in it gets the galaxy's look - names
for its plants and creatures, a colour cast, light in the dark where it fits - and one special stone of its own, a real
mineral that forms there (worth finding: a sample sells high on other worlds - engine/market.py).

    🌱 Cradle   green and gentle - jade, pushed up from deep, hot pressure by young mountains
    🔥 Ember    a young, burning galaxy - pyrite ("fool's gold", FeS₂: stable up to ~540 °C)
    ❄ Frost    far, cold suns - nitrogen ice (N₂ freezes at −210 °C)
    🕳 Hollow   old and dying - zircon, crystals that outlast everything (the oldest on Earth: 4.4 billion years)
    🌊 Tide     water worlds - aragonite, the mineral of shells and reefs
    🌺 Bloom    the richest life - amber, tree resin turned to stone
    ⛈ Storm    two galaxies crashed: wild air - fulgurite, glass made where lightning hits sand
    💠 Crystal  an advanced people - amethyst geodes (quartz coloured by iron and natural radiation)
    🌀 Heart    near the galaxy's centre - iron-nickel meteorites (crowded stars: more falling stones)
Only the look and the names are the theme's (🎮); the physics of each world (what can live there at all) is untouched."""
import colorsys
import random

T = {
    "cradle": dict(pre=["moss", "reed", "fern", "dew", "meadow"], ani=["grazer", "hopper", "loper", "warbler", "nuzzler"], hue=0.30, glow=0.0,
                   rock=("jade", "#3f9b6b", "made deep down under heat and pressure, then pushed up by young mountains", 0.12)),
    "ember": dict(pre=["ash", "cinder", "ember", "scorch", "flare"], ani=["crawler", "basker", "snapper", "runner", "drake"], hue=0.04, glow=0.6,
                  rock=("pyrite", "#c9a83a", "iron sulfide (FeS₂, 'fool's gold'): it stays solid up to ~540 °C - golden cubes in the hot rock", 0.15)),
    "frost": dict(pre=["rime", "frost", "hoar", "glacier", "pale"], ani=["shuffler", "burrower", "puff", "stalker", "glider"], hue=0.55, glow=0.2,
                  rock=("nitrogen ice", "#e8f4ff", "the air's own nitrogen, frozen solid (N₂ freezes at −210 °C)", 0.2)),
    "hollow": dict(pre=["dust", "old", "dusk", "ash", "silent"], ani=["creeper", "watcher", "sleeper", "drifter", "gnawer"], hue=0.08, glow=0.1,
                   rock=("zircon", "#b06a4a", "tiny hard crystals that outlast everything - on Earth the oldest are 4.4 billion years old", 0.1)),
    "tide": dict(pre=["tide", "reef", "brine", "foam", "kelp"], ani=["wader", "diver", "shell-back", "skimmer", "paddler"], hue=0.50, glow=0.5,
                 rock=("aragonite", "#f2e6d8", "calcium carbonate laid down by sea life - the mineral of shells and reefs", 0.15)),
    "bloom": dict(pre=["bloom", "petal", "honey", "blossom", "vine"], ani=["nectar-bat", "petal-back", "grazer", "dancer", "singer"], hue=0.88, glow=0.3,
                  rock=("amber", "#e39a2a", "tree resin hardened into stone over millions of years - sometimes with a bug inside", 0.1)),
    "storm": dict(pre=["gale", "thunder", "squall", "spark", "gust"], ani=["clinger", "flattener", "roller", "kite", "anchor"], hue=0.66, glow=0.2,
                  rock=("fulgurite", "#8a7f6a", "glass tubes made where lightning struck sand - fused in a millionth of a second at ~1800 °C", 0.12)),
    "crystal": dict(pre=["glass", "prism", "lattice", "shard", "lumen"], ani=["strider", "chimer", "glimmer", "sentinel", "weaver"], hue=0.75, glow=0.7,
                    rock=("amethyst geode", "#8e5bd6", "hollow stones lined with quartz, coloured violet by iron and natural radiation", 0.1)),
    "heart": dict(pre=["star", "void", "halo", "core", "night"], ani=["drifter", "watcher", "eclipse", "seeker", "lurker"], hue=0.70, glow=0.8,
                  rock=("iron-nickel meteorite", "#6b6e75", "near a galaxy's centre the stars are crowded - more stones fall from the sky", 0.15)),
}


def theme(p):
    """the region key of this world (engine/regions.py: the Milky Way's nine), or None (the Solar System, other galaxies)"""
    g = p.get("galaxy")
    if g is None or p.get("solar") or str(g).lower() != "milkyway" or p.get("star") is None:
        return None
    from . import regions
    return regions.of_star(p["star"])


def _tint(hexc, hue, k):
    """pull a colour k of the way toward the theme's hue (keeps its brightness)"""
    try:
        r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except (ValueError, TypeError, IndexError):
        return hexc
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    d = ((hue - h + 0.5) % 1.0) - 0.5
    r, g, b = colorsys.hsv_to_rgb((h + d * k) % 1.0, s, v)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def plants(p, out):
    t = theme(p)
    if not t:
        return out
    th, r = T[t], random.Random(f"theme-plants|{p.get('name')}")
    pre = r.sample(th["pre"], 5)                                         # (each kind its own name)
    for i, k in enumerate(out):
        k["kind"] = f"{pre[i % 5]}-{['stalk', 'tree', 'bush', 'cup', 'frond', 'crystal'][i % 6] if k.get('form') not in ('tree', 'bush') else k['form']}"
        k["colour"] = _tint(k.get("colour", "#3f9142"), th["hue"], 0.45)
        if r.random() < th["glow"]:
            k["glow"] = True                                             # (they shine in the dark - the theme's look)
        if t == "crystal" and i == 0:
            k["top"] = "crystals"
    return out


def creatures(p, out):
    t = theme(p)
    if not t:
        return out
    th, r = T[t], random.Random(f"theme-animals|{p.get('name')}")
    pre, ani = r.sample(th["pre"], 5), r.sample(th["ani"], 5)
    for i, k in enumerate(out):
        k["tname"] = f"{pre[(i + 2) % 5]} {ani[i % 5]}" + (f" {['I', 'II', 'III'][i // 5]}" if i >= 5 else "")   # (the logbook and the look card read it)
        k["fur"] = _tint(k.get("fur", "#888888"), th["hue"], 0.35)
    return out


def rocks(p, out):
    t = theme(p)
    if not t or not out:
        return out
    n, c, why, share = T[t]["rock"]
    Tc = float(p.get("temperature_c") or 0)
    if n == "nitrogen ice" and Tc > -210:                                 # (physics first: it would melt)
        n, c, why = "water ice", "#dfeef7", "frozen water, hard as rock in this cold"
    if n == "aragonite" and not p.get("life"):
        return out
    if any(x["name"] == n for x in out):
        return out
    out = out[:4] + [dict(name=n, colour=c, why=f"⭐ {why}", share=share, shiny=True, glow=T[t]["glow"] > 0.5, special=True)]
    tot = sum(x["share"] for x in out)
    for x in out:
        x["share"] = round(x["share"] / tot, 3)
    return out
