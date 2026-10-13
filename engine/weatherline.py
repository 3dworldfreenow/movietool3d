"""Weather that changes during a scene: clouds gather, the sky darkens, the first drops, heavy rain, it stops,
the sun comes out again - with everything that goes with it (light, shadows, wind, wet ground, puddles, snow
settling, fog rolling in, drips and a rainbow after the rain, the sounds).

Story words (an item without "who"):
    {"weather": "rain", "over": 6}                 change slowly to rain over 6 s ("fade" works the same)
    {"weather": "passing_shower", "over": 30}      a whole sequence: clouds -> drizzle -> rain -> drizzle -> sun
    {"weather": ["clouds", "rain", "clear"], "over": 20}     your own steps, evenly spread
    sequences: rain_comes, storm_comes, passing_shower, storm_passes, rain_stops, fog_rolls_in, fog_lifts,
               snow_starts, snow_stops, wind_picks_up, wind_dies_down
    "react": false  -> people do not react by themselves; "react": "run" -> they run for cover

state(sc, bg, t) -> dict of 0..1 levels: cloud, rain, snow, fog, wind (strength), storm, plus
    wet (how wet the ground is), puddle (how big the puddles have grown), snow_cover, rainbow, drips, steam.
"""
import math

from .util import clamp, smoothstep

# what each weather word means: cloud cover, rain, snow, fog, wind strength, storm (lightning)
LEVELS = {
    "clear": dict(cloud=0.1, rain=0.0, snow=0.0, fog=0.0, wind=1.0, storm=0.0),
    "sunny": dict(cloud=0.0, rain=0.0, snow=0.0, fog=0.0, wind=0.8, storm=0.0),
    "clouds": dict(cloud=0.75, rain=0.0, snow=0.0, fog=0.0, wind=1.4, storm=0.0),
    "overcast": dict(cloud=0.95, rain=0.0, snow=0.0, fog=0.1, wind=1.2, storm=0.0),
    "drizzle": dict(cloud=0.85, rain=0.45, snow=0.0, fog=0.1, wind=1.3, storm=0.0),
    "rain": dict(cloud=1.0, rain=1.0, snow=0.0, fog=0.15, wind=1.6, storm=0.0),
    "storm": dict(cloud=1.0, rain=1.0, snow=0.0, fog=0.2, wind=3.2, storm=1.0),
    "fog": dict(cloud=0.5, rain=0.0, snow=0.0, fog=1.0, wind=0.4, storm=0.0),
    "snow": dict(cloud=0.85, rain=0.0, snow=1.0, fog=0.2, wind=1.2, storm=0.0),
    "windy": dict(cloud=0.35, rain=0.0, snow=0.0, fog=0.0, wind=2.8, storm=0.0),
    "cyclone": dict(cloud=1.0, rain=1.0, snow=0.0, fog=0.3, wind=6.0, storm=1.0),
    "calm": dict(cloud=0.1, rain=0.0, snow=0.0, fog=0.0, wind=0.2, storm=0.0),
}
ALIASES = {"cloudy": "clouds", "cloud": "clouds", "light_rain": "drizzle", "heavy_rain": "rain", "monsoon": "rain",
           "thunderstorm": "storm", "stop": "clear", "none": "clear", "mist": "fog", "foggy": "fog",
           "wind": "windy", "snowfall": "snow", "blizzard": "snow", "dry": "clear", "fine": "clear",
           "tornado": "cyclone", "hurricane": "cyclone", "baarish": "rain", "barish": "rain", "aandhi": "windy"}
# sequences: (weather, share of the time "over")
SEQUENCES = {
    "rain_comes": [("clouds", 0.35), ("drizzle", 0.25), ("rain", 0.4)],
    "storm_comes": [("clouds", 0.3), ("windy", 0.15), ("rain", 0.2), ("storm", 0.35)],
    "passing_shower": [("clouds", 0.15), ("drizzle", 0.1), ("rain", 0.35), ("drizzle", 0.1), ("clear", 0.3)],
    "storm_passes": [("clouds", 0.15), ("storm", 0.45), ("rain", 0.1), ("clouds", 0.1), ("clear", 0.2)],
    "rain_stops": [("drizzle", 0.4), ("clear", 0.6)],
    "fog_rolls_in": [("overcast", 0.3), ("fog", 0.7)],
    "fog_lifts": [("overcast", 0.5), ("clear", 0.5)],
    "snow_starts": [("overcast", 0.35), ("snow", 0.65)],
    "snow_stops": [("overcast", 0.4), ("clear", 0.6)],
    "wind_picks_up": [("clouds", 0.4), ("windy", 0.6)],
    "wind_dies_down": [("clouds", 0.5), ("calm", 0.5)],
}
SEQ_ALIASES = {"shower": "passing_shower", "rain_starts": "rain_comes", "storm_starts": "storm_comes",
               "rain_passes": "passing_shower", "clears_up": "rain_stops", "clear_up": "rain_stops"}
KEYS = ("cloud", "rain", "snow", "fog", "wind", "storm")


def canon(name):
    n = str(name or "clear").lower().strip().replace(" ", "_")
    n = ALIASES.get(n, n)
    return n if n in LEVELS else "clear"


def is_sequence(name):
    n = str(name or "").lower().strip().replace(" ", "_")
    return SEQ_ALIASES.get(n, n) in SEQUENCES


def steps(name, start, over):
    """[(start, weather, fade)] for a word, a sequence or a list of words spread over `over` seconds."""
    if isinstance(name, (list, tuple)):
        seq = [(w, 1.0 / max(1, len(name))) for w in name]
    else:
        n = str(name).lower().strip().replace(" ", "_")
        n = SEQ_ALIASES.get(n, n)
        if n not in SEQUENCES:
            return [(start, canon(n), max(0.05, over))]
        seq = SEQUENCES[n]
    out, t = [], start
    for w, share in seq:
        d = max(0.3, over * share)
        out.append((t, canon(w), d * 0.8))           # each step blends in over most of its share
        t += d
    return out


def base_levels(weather):
    return dict(LEVELS[canon(weather)])


def _levels_at(fx, base, t):
    lv = dict(base)
    for st, w, fade in fx:
        if st > t:
            break
        tgt = LEVELS[canon(w)]
        k = smoothstep((t - st) / max(fade, 0.01))
        for key in KEYS:
            lv[key] = lv[key] + (tgt[key] - lv[key]) * k
    return lv


def state(sc, bg, t):
    """The weather now (see the module doc). Cached per scene and time step."""
    fx = list(getattr(sc, "weather_fx", None) or ())
    w0 = getattr(bg, "_weather0", None) or getattr(bg, "weather", "clear")
    base = base_levels(w0)
    if getattr(bg, "no_air", False):                    # the Moon / space: no weather at all
        return dict(base, cloud=0.0, rain=0.0, snow=0.0, fog=0.0, wind=0.0, storm=0.0, wet=0.0, puddle=0.0,
                    snow_cover=0.0, rainbow=0.0, drips=0.0, steam=0.0, changing=False)
    if not fx:
        lv = dict(base)
        r0 = lv["rain"]
        lv.update(wet=r0, puddle=r0, snow_cover=lv["snow"], rainbow=0.0, drips=0.0, steam=0.0, changing=False)
        return lv
    lv = _levels_at(fx, base, t)
    # history: how much rain / snow has fallen (wet ground, puddles grow, snow settles) and when it stopped
    dt = 0.25
    wet = base["rain"]
    puddle = base["rain"]
    cover = base["snow"]
    last_rain_end, was_rain = None, base["rain"] > 0.5
    n = int(max(0.0, t) / dt)
    for i in range(n + 1):
        tt = i * dt
        lt = _levels_at(fx, base, tt)
        r, s = lt["rain"], lt["snow"]
        wet = clamp(wet + (r * 0.25 - (1 - r) * 0.012) * dt, 0.0, 1.0)      # wets in ~4 s, dries slowly
        puddle = clamp(puddle + (r * 0.07 - (1 - r) * 0.004) * dt, 0.0, 1.0)  # puddles grow over ~15 s
        cover = clamp(cover + (s * 0.05 - 0.002) * dt, 0.0, 1.0)              # snow settles over ~20 s
        if was_rain and r < 0.15:
            last_rain_end = tt
            was_rain = False
        elif r > 0.5:
            was_rain = True
            last_rain_end = None
    lv["wet"] = max(wet, lv["rain"] * 0.6)
    lv["puddle"] = puddle
    lv["snow_cover"] = cover
    since = (t - last_rain_end) if last_rain_end is not None else None
    sunny = 1.0 - lv["cloud"]
    night = bool(getattr(bg, "night", False))
    lv["rainbow"] = 0.0
    lv["drips"] = 0.0
    lv["steam"] = 0.0
    if since is not None:
        lv["drips"] = clamp(lv["wet"] * (1.0 - since / 25.0), 0.0, 1.0)            # drips from roofs and leaves
        if not night:
            lv["rainbow"] = clamp(sunny * 1.6 - 0.3, 0.0, 1.0) * smoothstep(since / 2.0) * \
                clamp(1.0 - (since - 12.0) / 8.0, 0.0, 1.0)
            hot = str(getattr(bg, "time", "day")) in ("day", "noon", "afternoon") or \
                getattr(bg, "preset", "") in ("desert", "beach", "city", "street", "road")
            if hot:
                lv["steam"] = clamp(sunny * lv["wet"] * (1.0 - since / 30.0), 0.0, 0.8)    # steam off the warm ground
    lv["changing"] = True
    return lv


def name_for(lv):
    """The plain weather word for these levels (for code that only knows names)."""
    if lv["snow"] > 0.3:
        return "snow"
    if lv["rain"] > 0.3:
        return "storm" if lv["storm"] > 0.5 else "rain"
    if lv["fog"] > 0.5:
        return "fog"
    if lv["wind"] > 2.2:
        return "windy"
    return "clear"


def rain_starts(fx, base_weather="clear"):
    """Times at which rain begins in a scene (rain level crosses 0.3 going up) - people react then."""
    base = base_levels(base_weather)
    out, prev = [], base["rain"]
    if not fx:
        return out
    end = max(st + fade for st, _w, fade in fx) + 0.5
    t = 0.0
    while t <= end:
        r = _levels_at(fx, base, t)["rain"]
        if prev < 0.3 <= r:
            out.append((t, 1.0 if _levels_at(fx, base, t + 6.0)["rain"] > 0.8 else 0.5))
        prev = r
        t += 0.1
    return out


# ============================================================================ drawing helpers (screen space)
def draw_rainbow(ctx, W, H, amount, side=1.0, horizon=0.55):
    """A soft rainbow arc in the sky, opposite the sun."""
    if amount <= 0.01:
        return
    cx = W * (0.5 - 0.22 * side)
    cy = H * (horizon + 0.12)
    R = W * 0.42
    cols = ((0.58, 0.2, 0.85), (0.3, 0.3, 0.95), (0.2, 0.6, 1.0), (0.3, 0.85, 0.35), (1.0, 0.92, 0.2),
            (1.0, 0.6, 0.1), (0.95, 0.2, 0.2))
    bw = W * 0.009
    ctx.save()
    ctx.set_line_width(bw * 1.15)
    for i, c in enumerate(cols):
        ctx.new_path()
        ctx.arc(cx, cy, R + i * bw, math.pi * 1.05, math.pi * 1.95)
        ctx.set_source_rgba(*c, 0.22 * amount)
        ctx.stroke()
    ctx.restore()


def draw_drips(ctx, W, H, t, amount, seed=7):
    """Drops falling from roofs and leaves after the rain (a few streaks, near the top of the picture)."""
    if amount <= 0.02:
        return
    import random
    r = random.Random(seed)
    ctx.save()
    ctx.set_line_width(max(1.0, H / 540.0))
    for i in range(int(30 * amount)):
        x = r.uniform(0, W)
        y0 = r.uniform(0.05, 0.45) * H
        per = r.uniform(0.8, 2.2)
        u = ((t + r.random() * per) % per) / per
        y = y0 + u * u * H * 0.5
        ctx.set_source_rgba(0.85, 0.92, 1.0, 0.6 * amount * (1 - u))
        ctx.move_to(x, y)
        ctx.line_to(x, y + H * 0.012)
        ctx.stroke()
    ctx.restore()


def draw_steam(ctx, W, H, t, amount, ground=0.8, seed=11):
    """Faint steam rising off a warm wet ground after rain."""
    if amount <= 0.02:
        return
    import random
    r = random.Random(seed)
    ctx.save()
    for i in range(18):                                 # thin wisps that rise, sway and fade
        x0 = r.uniform(0, W)
        per = r.uniform(3.0, 5.0)
        u = ((t + r.random() * per) % per) / per
        x = x0 + math.sin(t * 0.7 + i + u * 3) * W * 0.012
        y = H * ground - u * H * 0.22
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(H * (0.006 + 0.01 * u), H * (0.03 + 0.04 * u))
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgba(1, 1, 1, 0.07 * amount * math.sin(math.pi * u))
        ctx.fill()
    ctx.restore()


def draw_fog(ctx, W, H, amount, horizon=0.5, color=(0.86, 0.88, 0.9)):
    """Fog rolling in: thick near the ground and in the distance, thinner up in the sky."""
    if amount <= 0.01:
        return
    import cairo
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgba(0.0, *color, 0.25 * amount)
    g.add_color_stop_rgba(clamp(horizon, 0.1, 0.9), *color, 0.75 * amount)
    g.add_color_stop_rgba(1.0, *color, 0.35 * amount)
    ctx.save()
    ctx.identity_matrix()
    ctx.set_source(g)
    ctx.paint()
    ctx.restore()


def draw_clouds_cover(ctx, W, H, amount, horizon=0.5):
    """Clouds over the sun: the whole picture a little greyer and dimmer (soft light, no strong colour)."""
    if amount <= 0.02:
        return
    ctx.save()
    ctx.identity_matrix()
    ctx.set_source_rgba(0.32, 0.36, 0.42, 0.16 * amount)
    ctx.paint()
    ctx.restore()
