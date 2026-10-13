"""Night lights: street lamps, diyas, lanterns, candles, windows, shop signs and headlights glow after sunset and
light what is near them.

Every light registers itself while the frame is drawn (add(...), screen coordinates). After the scene is drawn,
apply() does one pass over the picture:
  1. the rest of the scene gets darker and bluer (moonlight) - more at night, a little in the evening
  2. round each light the darkness opens up: a pool of light on the ground and on whoever stands near it
     (a face lit from the side by a diya)
  3. a soft glow round the light, a bigger halo in rain or fog, flicker for flames (diya, candle, fire)
CPU budget: only the brightest few lights open the darkness and light people; the rest are glow only.

Lights switch on by themselves at evening (night_amount >= 0.3), or with {"who": .., "do": "turn_on",
"object": "lamp1"} for a lamp / diya / lantern object.
"""
import math

from .util import clamp

LIGHTS = []          # this frame: dict(x, y, r, c, k, flame, gx, gy, kind)
ON = [False]         # this frame: are lamps / lanterns switched on by themselves (evening, night, a dark storm)
MAIN = 10            # how many lights open the darkness (the rest only glow)
NIGHT_TIMES = {"night": 1.0, "midnight": 1.0, "late_night": 1.0, "dusk": 0.75, "twilight": 0.75,
               "evening": 0.5, "sunset": 0.35, "dawn": 0.35, "sunrise": 0.25}
LIGHT_WORDS = ("lamp", "diya", "deepak", "lantern", "candle", "torch", "bulb", "light", "fire", "bonfire",
               "campfire", "mashaal", "chimney", "lalten")
FLAME_WORDS = ("diya", "deepak", "candle", "torch", "fire", "bonfire", "campfire", "mashaal", "lalten")
WARM = (1.0, 0.78, 0.42)
FLAME = (1.0, 0.68, 0.28)
COOL = (0.82, 0.9, 1.0)


def reset(bg=None):
    LIGHTS.clear()
    ON[0] = lights_on(bg) if bg is not None else False
    if bg is not None:
        bg.lamps_on = ON[0]


def add(x, y, r, c=WARM, k=0.7, flame=False, gx=None, gy=None, kind="lamp"):
    """A light at screen (x, y), reach r pixels, colour c, strength k (0..1); (gx, gy) = where its pool of light
    falls on the ground (screen)."""
    if r <= 1 or k <= 0.01:
        return
    LIGHTS.append(dict(x=float(x), y=float(y), r=float(r), c=c, k=float(k), flame=bool(flame),
                       gx=gx, gy=gy, kind=kind))


def add_device(ctx, x, y, r, c=WARM, k=0.7, flame=False, ground=None, kind="lamp"):
    """add() from the current drawing coordinates (world units of a layer): converts to the screen."""
    try:
        dx, dy = ctx.user_to_device(x, y)
        rx, ry = ctx.user_to_device_distance(r, 0)
        rr = math.hypot(rx, ry)
        gx = gy = None
        if ground is not None:
            gx, gy = ctx.user_to_device(*ground)
        add(dx, dy, rr, c, k, flame, gx, gy, kind)
    except Exception:                                   # noqa: BLE001
        pass


def night_amount(bg):
    """0 = full day .. 1 = deep night (time of day; a dark storm switches lights on too)."""
    t = str((getattr(bg, "spec", None) or {}).get("time") or getattr(bg, "time", "day")).lower().replace(" ", "_")
    k = NIGHT_TIMES.get(t, 1.0 if getattr(bg, "night", False) else 0.0)
    if getattr(bg, "time", "") == "space":
        return 0.0
    wx = getattr(bg, "wx", None) or {}
    storm = max(wx.get("storm", 0.0), 1.0 if getattr(bg, "weather", "") in ("storm", "cyclone") else 0.0)
    return clamp(max(k, 0.35 * storm + 0.25 * wx.get("cloud", 0.0) * wx.get("rain", 0.0)), 0.0, 1.0)


def lights_on(bg):
    return night_amount(bg) >= 0.3


def is_light_name(name):
    n = str(name or "").lower()
    return any(w in n for w in LIGHT_WORDS) and "lighthouse" not in n and "flashlight_off" not in n


def is_flame_name(name):
    n = str(name or "").lower()
    return any(w in n for w in FLAME_WORDS)


def flicker(t, seed=0.0, flame=True):
    if not flame:
        return 1.0
    return 0.86 + 0.08 * math.sin(t * 13.0 + seed) + 0.06 * math.sin(t * 29.0 + seed * 1.7)


def apply(ctx, W, H, S, bg, t, extra_dark=True, dark_k=0.32):
    """The night pass (see the module doc). Clears the list afterwards."""
    import cairo
    night = night_amount(bg)
    lights = list(LIGHTS)
    LIGHTS.clear()
    if night < 0.05 or not lights:                   # (no lights: the place's own night look stays as it is)
        return
    wx = getattr(bg, "wx", None) or {}
    wet = max(wx.get("rain", 0.0), 1.0 if getattr(bg, "weather", "") in ("rain", "storm") else 0.0)
    fog = max(wx.get("fog", 0.0), 1.0 if getattr(bg, "weather", "") in ("fog", "mist") else 0.0)
    halo = 1.0 + 0.8 * wet + 1.2 * fog                   # light spreads in wet / foggy air
    lights.sort(key=lambda L: -L["k"] * L["r"])
    main = lights[:MAIN]
    ctx.save()
    ctx.identity_matrix()
    # 1 + 2: darker, bluer scene with pools of light cut out round the brightest lights
    if extra_dark:
        dark = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        dc = cairo.Context(dark)
        dc.set_source_rgba(0.02, 0.04, 0.14, dark_k * night)
        dc.paint()
        dc.set_operator(cairo.OPERATOR_DEST_OUT)
        for i, L in enumerate(main):
            f = flicker(t, i * 1.9, L["flame"])
            R = L["r"] * 1.6 * f
            g = cairo.RadialGradient(L["x"], L["y"], 0, L["x"], L["y"], R)
            g.add_color_stop_rgba(0, 0, 0, 0, 0.95 * L["k"])
            g.add_color_stop_rgba(0.5, 0, 0, 0, 0.5 * L["k"])
            g.add_color_stop_rgba(1, 0, 0, 0, 0)
            dc.set_source(g)
            dc.arc(L["x"], L["y"], R, 0, 2 * math.pi)
            dc.fill()
            if L["gx"] is not None and L["gy"] is not None:     # the pool of light on the ground
                dc.save()
                dc.translate(L["gx"], L["gy"])
                dc.scale(1.0, 0.28)
                g2 = cairo.RadialGradient(0, 0, 0, 0, 0, R * 1.1)
                g2.add_color_stop_rgba(0, 0, 0, 0, 0.9 * L["k"])
                g2.add_color_stop_rgba(1, 0, 0, 0, 0)
                dc.set_source(g2)
                dc.arc(0, 0, R * 1.1, 0, 2 * math.pi)
                dc.fill()
                dc.restore()
        ctx.set_source_surface(dark, 0, 0)
        ctx.paint()
    # 3: warm light added round each light (people and walls near it take its colour), glow and halo
    ctx.set_operator(cairo.OPERATOR_ADD)
    for i, L in enumerate(lights):
        f = flicker(t, i * 1.9, L["flame"])
        c = L["c"]
        k = L["k"] * night * f
        if i < MAIN:                                      # the light falling on things round it
            R = L["r"] * 1.3
            g = cairo.RadialGradient(L["x"], L["y"], 0, L["x"], L["y"], R)
            g.add_color_stop_rgba(0, c[0], c[1], c[2], 0.22 * k)
            g.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
            ctx.set_source(g)
            ctx.arc(L["x"], L["y"], R, 0, 2 * math.pi)
            ctx.fill()
            if L["gx"] is not None and L["gy"] is not None:
                ctx.save()
                ctx.translate(L["gx"], L["gy"])
                ctx.scale(1.0, 0.28)
                g2 = cairo.RadialGradient(0, 0, 0, 0, 0, R * 0.9)
                g2.add_color_stop_rgba(0, c[0], c[1], c[2], 0.18 * k)
                g2.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
                ctx.set_source(g2)
                ctx.arc(0, 0, R * 0.9, 0, 2 * math.pi)
                ctx.fill()
                ctx.restore()
        if L["kind"] in ("window", "shop"):               # a lit window is itself the bright part: no blob
            continue
        hr = max(3.0, L["r"] * 0.35 * halo)               # the glow / halo round the light itself
        g = cairo.RadialGradient(L["x"], L["y"], 0, L["x"], L["y"], hr)
        g.add_color_stop_rgba(0, c[0], c[1], c[2], 0.55 * k)
        g.add_color_stop_rgba(0.35, c[0], c[1], c[2], 0.18 * k * (0.6 + 0.4 * halo))
        g.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
        ctx.set_source(g)
        ctx.arc(L["x"], L["y"], hr, 0, 2 * math.pi)
        ctx.fill()
    ctx.restore()


def string_lights(ctx, x0, x1, y, t, sag=18.0, n=None, seed=0):
    """A string of small coloured bulbs (Diwali) hung between x0 and x1 at height y (layer coordinates, y up);
    each bulb registers as a small light."""
    cols = ((1.0, 0.85, 0.3), (1.0, 0.4, 0.3), (0.4, 0.9, 0.4), (0.4, 0.7, 1.0), (1.0, 0.55, 0.9))
    n = n or max(4, int(abs(x1 - x0) / 22))
    ctx.set_source_rgba(0.15, 0.15, 0.15, 0.8)
    ctx.set_line_width(1.5)
    ctx.move_to(x0, y)
    ctx.curve_to(x0 + (x1 - x0) * 0.33, y - sag, x0 + (x1 - x0) * 0.66, y - sag, x1, y)
    ctx.stroke()
    for i in range(n + 1):
        u = i / n
        bx = x0 + (x1 - x0) * u
        by = y - sag * 4 * u * (1 - u) * 0.75 - 4
        c = cols[(i + seed) % len(cols)]
        on = 0.6 + 0.4 * (math.sin(t * 3.0 + i * 1.3 + seed) > -0.3)
        ctx.set_source_rgb(*[min(1.0, v * on + 0.1) for v in c])
        ctx.arc(bx, by, 4, 0, 2 * math.pi)
        ctx.fill()
        if i % 3 == 0:
            add_device(ctx, bx, by, 26, c, 0.35 * on, kind="string")
