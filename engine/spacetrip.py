"""Rocket trips between planets (the journey feature for space - engine/journey.py makes the scenes):

    lift-off      the first planet: a countdown, the rocket rises with fire and smoke, the camera shakes
    the trip      a full-screen shot drawn here (on top of the scene):
                    1. the route map - our Solar System's orbits with the transfer arc (Hohmann), a star's own
                       planets, or the galaxy with "you are here" and a line to the far star
                    2. space - the old planet shrinking below, stars streaming past, the new one growing ahead
                  with a label: "Earth → Mars · 0.52 AU · about 8½ months" (real distance + travel time)
    landing       the new planet: the rocket comes down on its fire, the planet's name

Travel times are real school physics: inside one star system the transfer orbit, t = ½·√(a³/M) years (a = half
of r1 + r2 in AU, M in Suns); Earth -> Moon 3 days. Between stars no rocket is fast enough - the label says how
long even light takes, and the trip is a "jump".
"""
import math
import random

from .util import clamp, stable_hash

SOLAR_AU = {"mercury": 0.39, "venus": 0.72, "earth": 1.0, "moon": 1.0, "mars": 1.52, "jupiter": 5.2,
            "saturn": 9.58, "uranus": 19.2, "neptune": 30.1, "pluto": 39.5}
GALAXY_LY = 50000.0                       # the galaxy's radius in light years (map units 0..1)
SUN_SPOT = (0.52, -0.08)                  # where our Sun is on any galaxy map ("you are here" from Earth)
EARTH = {"name": "Earth", "solar": "earth", "colours": {"ground": "#3f8f4a", "sky": "#4f8fdc", "water": "#2f6fc0"},
         "gas": False, "rings": False, "air": "thin", "water": "oceans", "star_colour": "#fff2c8", "star_name": "the Sun"}


def _rgb(c, default=(0.6, 0.6, 0.6)):
    try:
        c = str(c).lstrip("#")
        return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, TypeError):
        return default


def _pretty_time(years):
    days = years * 365.25
    if days < 1.5:
        return f"about {max(1, round(days * 24))} hours"
    if days < 45:
        return f"about {round(days)} days"
    months = days / 30.44
    if months < 24:
        return f"about {round(months * 2) / 2:g} months"
    return f"about {years:.1f} years"


def route(pa, pb, sa=None, sb=None, settings=None):
    """what the trip is: kind (solar / star / stars / far), from / to names, distance + time labels, map data.
    pa / pb = planet dicts (engine/galaxy.py) or None for Earth; sa / sb = the two scenes (for galaxy / star)."""
    from . import galaxy
    settings = settings or {}
    sa, sb = sa or {}, sb or {}
    pa, pb = pa or EARTH, pb or EARTH
    na, nb = pa["name"], pb["name"]
    out = {"from": na, "to": nb, "a": _look(pa), "b": _look(pb), "kind": "far", "dist": "", "time": "", "map": {}}
    sola, solb = pa.get("solar"), pb.get("solar")
    if sola and solb:                                          # inside our Solar System
        out["kind"] = "solar"
        if {sola, solb} == {"earth", "moon"}:
            out["dist"], out["time"] = "384,400 km", "about 3 days"
        else:
            r1, r2 = SOLAR_AU[sola], SOLAR_AU[solb]
            a = (r1 + r2) / 2
            out["dist"] = f"{abs(r2 - r1):.2f} AU ({abs(r2 - r1) * 150:.0f} million km)"
            out["time"] = _pretty_time(0.5 * a ** 1.5)
        out["map"] = {"star": "#fff2c8", "orbits": [(n, SOLAR_AU[n], _look(galaxy.solar(n))["ground"])
                                                    for n in SOLAR_AU if n != "moon"],
                      "a": SOLAR_AU[sola], "b": SOLAR_AU[solb], "na": na, "nb": nb,
                      "belts": [(2.2, 3.3, "rock"), (30.0, 50.0, "ice")]}             # the real main belt and Kuiper belt
        return out
    if pa.get("mw") or pb.get("mw"):                              # 🌌 a real known star: real light years, honest travel time
        from . import milkyway
        ma, mb = pa.get("mw"), pb.get("mw")
        if ma and mb and milkyway.PLANETS[ma][0] == milkyway.PLANETS[mb][0]:
            ra, rb = pa.get("distance_au") or 0.03, pb.get("distance_au") or 0.03
            out.update(kind="star", dist=f"{abs(rb - ra):.3f} AU", time=_pretty_time(0.5 * math.sqrt(((ra + rb) / 2) ** 3 / 0.1)))
            out["map"] = {"star": pa.get("star_colour") or "#ffb070", "orbits": [(milkyway.nice(k), v[1], _look(milkyway.planet(k))["ground"])
                          for k, v in milkyway.PLANETS.items() if v[0] == milkyway.PLANETS[ma][0]], "a": ra, "b": rb, "na": na, "nb": nb}
            return out
        def spot(p):
            if p.get("mw"):
                d, l = milkyway.STARS[milkyway.PLANETS[p["mw"]][0]][:2]
                return milkyway.xy(d, l), d, l
            return milkyway.SUN_XY, 0.0, 0.0
        (xa, da, la), (xb, db, lb) = spot(pa), spot(pb)
        ly = math.sqrt(da * da + db * db - 2 * da * db * math.cos(math.radians(la - lb)))   # (in the plane: close enough)
        out["kind"] = "stars"
        out["dist"] = f"{ly:,.3g} light years"
        out["time"] = f"light takes {ly:,.3g} years; today's fastest probe (Voyager 1, 17 km/s) would need ≈ {ly * 9.4607e12 / 17 / 3.156e7:,.0f} years - in the story: a jump"
        out["map"] = {"seed": "milkyway", "rules": 2, "a": xa, "b": xb, "na": pa.get("star_name") or na, "nb": pb.get("star_name") or nb}
        return out
    ga = pa.get("galaxy") if pa.get("galaxy") is not None else None
    gb = pb.get("galaxy") if pb.get("galaxy") is not None else None
    if ga is not None and ga == gb and pa.get("star") == pb.get("star"):          # one star's planets
        rl = pa.get("rules", 1)
        s = galaxy.star(ga, pa["star"], rl)
        r1, r2 = pa.get("distance_au") or 1.0, pb.get("distance_au") or 1.0
        a = (r1 + r2) / 2
        out["kind"] = "star"
        out["dist"] = f"{abs(r2 - r1):.2f} AU"
        out["time"] = _pretty_time(0.5 * math.sqrt(a ** 3 / max(0.1, s["mass"])))
        orbits = []
        for k in range(1, s["planets"] + 1):
            p = galaxy.planet(ga, pa["star"], k, rl)
            orbits.append((p["name"], p.get("distance_au") or k, _look(p)["ground"]))
        out["map"] = {"star": s["colour"], "orbits": orbits, "a": r1, "b": r2, "na": na, "nb": nb,
                      "belts": [(x["from_au"], x["to_au"], "rock" if x["kind"] == "asteroid belt" else "ice") for x in galaxy.belts(ga, pa["star"], rl)]}
        return out
    seed = ga if ga is not None else (gb if gb is not None else int(settings.get("galaxy", 1) or 1))
    xa = _star_xy(seed, pa)
    xb = _star_xy(seed, pb)
    if xa is not None and xb is not None:                        # between stars: a jump
        ly = math.hypot(xa[0] - xb[0], xa[1] - xb[1]) * GALAXY_LY
        out["kind"] = "stars"
        out["dist"] = f"{ly:,.0f} light years"
        out["time"] = "a jump - light itself would need that many years"
        out["map"] = {"seed": seed, "rules": pa.get("rules", pb.get("rules", 1)), "a": xa, "b": xb, "na": pa.get("star_name") or na, "nb": pb.get("star_name") or nb}
        return out
    out["dist"] = f"to the star {pb.get('star_name') or nb}"
    out["time"] = "a long jump"
    return out


def _star_xy(seed, p):
    from . import galaxy
    if p.get("solar"):
        return SUN_SPOT
    if p.get("galaxy") is not None and p.get("star") is not None:
        s = galaxy.star(p["galaxy"], p["star"], p.get("rules", 1))
        return (s["x"], s["y"])
    nm = str(p.get("star_name") or p.get("name") or "")                   # a planet written as data: its own spot
    r = random.Random(stable_hash("star_spot|" + nm) % (2 ** 31))
    d, a = 0.2 + 0.7 * r.random(), r.uniform(0, 2 * math.pi)
    return (d * math.cos(a), d * math.sin(a))


def _look(p):
    c = p.get("colours") or {}
    return {"ground": c.get("ground") or "#888888", "sky": c.get("sky") or "#aaaaaa", "water": c.get("water"),
            "gas": bool(p.get("gas")), "rings": bool(p.get("rings")), "oceans": p.get("water") == "oceans",
            "air": p.get("air") != "none", "name": p.get("name", "")}


# ============================================================================ drawing (screen space, y down)
def draw(ctx, tr, t, W, H, S):
    """the trip shot over the whole frame; tr = {"route": route(), "dur": seconds}; t = seconds into it"""
    import cairo
    R = tr["route"]
    dur = max(1.0, float(tr.get("dur", 8.0)))
    u = clamp(t / dur, 0.0, 1.0)
    ctx.save()
    ctx.identity_matrix()
    ctx.set_source_rgb(0.012, 0.016, 0.05)
    ctx.rectangle(0, 0, W, H)
    ctx.fill()
    split = 0.38 if R.get("map") else 0.0
    if u < split:
        _draw_map(ctx, R, u / split, W, H, S)
    elif R.get("bh") and 0.3 < (u - split) / max(0.01, 1 - split) < 0.85:     # ⚫ the black-hole pass in the middle of the cruise
        _draw_bh(ctx, R, ((u - split) / max(0.01, 1 - split) - 0.3) / 0.55, t, W, H, S)
    else:
        _draw_cruise(ctx, R, (u - split) / max(0.01, 1 - split), t, W, H, S)
    # the label
    a = clamp(min(u / 0.08, (1 - u) / 0.06), 0, 1)
    if a > 0:
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        fs = H * 0.05
        ctx.set_font_size(fs)
        line1 = f"{R['from']}  →  {R['to']}"
        line2 = " · ".join(x for x in (R.get("dist"), R.get("time")) if x)
        for k, (txt, size) in enumerate(((line1, fs), (line2, fs * 0.62))):
            ctx.set_font_size(size)
            ext = ctx.text_extents(txt)
            x, y = W / 2 - ext.width / 2 - ext.x_bearing, H * (0.09 + 0.065 * k)
            ctx.set_source_rgba(0, 0, 0, 0.55 * a)
            ctx.move_to(x + 2, y + 2)
            ctx.show_text(txt)
            ctx.set_source_rgba(1, 1, 1, a)
            ctx.move_to(x, y)
            ctx.show_text(txt)
    # fade in / out (the cut from lift-off and to the landing)
    f = max(clamp(1 - t / 0.35, 0, 1), clamp(1 - (dur - t) / 0.35, 0, 1))
    if f > 0:
        ctx.set_source_rgba(0, 0, 0, f)
        ctx.rectangle(0, 0, W, H)
        ctx.fill()
    ctx.restore()


def _stars(ctx, W, H, seed=3, n=220, alpha=1.0):
    r = random.Random(seed)
    for _ in range(n):
        x, y, s = r.random() * W, r.random() * H, r.random()
        ctx.set_source_rgba(1, 1, 1, (0.25 + 0.6 * s) * alpha)
        ctx.arc(x, y, 0.6 + 1.6 * s * H / 1080, 0, 2 * math.pi)
        ctx.fill()


def _draw_map(ctx, R, u, W, H, S):
    m = R["map"]
    _stars(ctx, W, H, 5, 160, 0.6)
    cx, cy = W / 2, H * 0.58
    if R["kind"] in ("solar", "star"):
        orbits = m["orbits"]
        top = max([o[1] for o in orbits] + [m["a"], m["b"]])
        far = max(m["a"], m["b"]) * 1.25
        top = min(top, far) if far > 0 else top
        scale = (H * 0.36) / math.sqrt(max(0.05, top))

        def rad(au):
            return math.sqrt(max(0.0, au)) * scale
        sc = _rgb(m["star"])
        ctx.set_source_rgb(*sc)
        ctx.arc(cx, cy, H * 0.025, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_line_width(max(1.0, H / 900))
        for k, (nm, au, col) in enumerate(orbits):
            if au > top * 1.01:
                continue
            ctx.set_source_rgba(1, 1, 1, 0.18)
            ctx.arc(cx, cy, rad(au), 0, 2 * math.pi)
            ctx.stroke()
            if str(nm).lower() in (str(m["na"]).lower(), str(m["nb"]).lower()):
                continue                                         # (the trip's own two are drawn on the route)
            ang = 0.9 + k * 1.7
            ctx.set_source_rgb(*_rgb(col))
            ctx.arc(cx + math.cos(ang) * rad(au), cy + math.sin(ang) * rad(au) * 0.999, H * 0.008, 0, 2 * math.pi)
            ctx.fill()
        rb_ = random.Random(23)
        for b in m.get("belts") or []:                           # 🪨 the belts: a ring of dots (asteroids / icy Kuiper objects)
            if b[0] > top * 1.01:
                continue
            col = (0.62, 0.55, 0.45) if b[2] == "rock" else (0.6, 0.78, 0.9)
            for _ in range(260):
                rr = rad(rb_.uniform(b[0], min(b[1], top * 1.01)))
                th = rb_.random() * 2 * math.pi
                ctx.set_source_rgba(*col, 0.75)
                ctx.arc(cx + math.cos(th) * rr, cy + math.sin(th) * rr, max(0.7, H / 1100), 0, 2 * math.pi)
                ctx.fill()
        ra, rb = rad(m["a"]), rad(m["b"])
        a0 = math.pi * 0.8                                      # start, then half way round (the transfer orbit)
        ax, ay = cx + math.cos(a0) * ra, cy + math.sin(a0) * ra
        pts = []
        for i in range(61):
            th = i / 60 * math.pi
            rr = ra + (rb - ra) * (1 - math.cos(th)) / 2
            pts.append((cx + math.cos(a0 + th) * rr, cy + math.sin(a0 + th) * rr))
        _route_line(ctx, pts, u, H)
        _dot(ctx, ax, ay, _rgb(R["a"]["ground"]), H * 0.016, "you are here", H, below=True)
        bx, by = pts[-1]
        _dot(ctx, bx, by, _rgb(R["b"]["ground"]), H * 0.016, m["nb"], H)
    else:                                                       # the galaxy
        from . import galaxy
        g = H * 0.40
        d = math.hypot(m["a"][0] - m["b"][0], m["a"][1] - m["b"][1])
        if d * g < H * 0.32:                                     # close stars: zoom in on the route (map grows in)
            z = min(6.0, H * 0.32 / max(1e-3, d * g))
            z = 1.0 + (z - 1.0) * clamp(u * 2.0, 0, 1)
            g *= z
            mx, my = (m["a"][0] + m["b"][0]) / 2, (m["a"][1] + m["b"][1]) / 2
            cx, cy = cx - mx * g * (1 - 1 / z), cy - my * g * 0.92 * (1 - 1 / z)
        for i in range(260):
            s = galaxy.star(m["seed"], i, m.get("rules", 1))
            if not s["mass"]:
                continue
            ctx.set_source_rgba(*_rgb(s["colour"]), 0.75)
            ctx.arc(cx + s["x"] * g, cy + s["y"] * g * 0.92, max(0.8, H / 700) * (1 + min(2.0, s["mass"] * 0.5)),
                    0, 2 * math.pi)
            ctx.fill()
        ax, ay = cx + m["a"][0] * g, cy + m["a"][1] * g * 0.92
        bx, by = cx + m["b"][0] * g, cy + m["b"][1] * g * 0.92
        pts = [(ax + (bx - ax) * i / 40, ay + (by - ay) * i / 40 - math.sin(i / 40 * math.pi) * H * 0.05)
               for i in range(41)]
        _route_line(ctx, pts, u, H)
        _dot(ctx, ax, ay, (1, 0.95, 0.75), H * 0.012, "you are here", H, below=True)
        _dot(ctx, bx, by, (0.6, 1.0, 0.7), H * 0.012, m["nb"], H)


def _route_line(ctx, pts, u, H):
    n = max(2, int(len(pts) * clamp(u * 1.25, 0, 1)))
    ctx.set_source_rgba(1.0, 0.82, 0.3, 0.95)
    ctx.set_line_width(max(2.0, H / 300))
    ctx.set_dash([H / 90, H / 140])
    ctx.move_to(*pts[0])
    for p in pts[1:n]:
        ctx.line_to(*p)
    ctx.stroke()
    ctx.set_dash([])
    x, y = pts[n - 1]                                          # the rocket on the way
    ctx.set_source_rgb(1, 1, 1)
    ctx.arc(x, y, H * 0.009, 0, 2 * math.pi)
    ctx.fill()


def _dot(ctx, x, y, col, r, label, H, below=False):
    import cairo
    ctx.set_source_rgb(*col)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.8)
    ctx.set_line_width(max(1.0, H / 700))
    ctx.arc(x, y, r * 1.8, 0, 2 * math.pi)
    ctx.stroke()
    if label:
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(H * 0.026)
        ctx.set_source_rgba(1, 1, 1, 0.92)
        if below:                                                # under the dot, so two close labels never overlap
            ext = ctx.text_extents(label)
            ctx.move_to(x - ext.width / 2, y + r * 2.4 + H * 0.026)
        else:
            ctx.move_to(x + r * 2.4, y - r * 1.2)
        ctx.show_text(label)


def _planet_ball(ctx, x, y, r, look):
    import cairo
    g, s = _rgb(look["ground"]), _rgb(look["sky"])
    ctx.save()
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.clip()
    ctx.set_source_rgb(*g)
    ctx.paint()
    rr = random.Random(stable_hash(look["name"]) % 99991)
    if look["gas"]:                                             # bands
        for k in range(9):
            ctx.set_source_rgba(*s, 0.35 + 0.3 * rr.random())
            yy = y - r + (k + rr.random() * 0.5) * 2 * r / 9
            ctx.rectangle(x - r, yy, 2 * r, r * rr.uniform(0.05, 0.14))
            ctx.fill()
    else:
        if look["oceans"] and look.get("water"):                # seas between the land
            ctx.set_source_rgb(*_rgb(look["water"]))
            ctx.paint()
            ctx.set_source_rgb(*g)
        for k in range(7):
            ctx.save()
            ctx.translate(x + rr.uniform(-0.8, 0.8) * r, y + rr.uniform(-0.8, 0.8) * r)
            ctx.scale(r * rr.uniform(0.15, 0.4), r * rr.uniform(0.1, 0.3))
            ctx.arc(0, 0, 1, 0, 2 * math.pi)
            ctx.restore()
            ctx.set_source_rgba(*(g if look["oceans"] else [c * 0.8 for c in g]), 0.9)
            ctx.fill()
    shade = cairo.RadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r * 1.05)
    shade.add_color_stop_rgba(0, 1, 1, 1, 0.12)
    shade.add_color_stop_rgba(0.7, 0, 0, 0, 0.1)
    shade.add_color_stop_rgba(1, 0, 0, 0, 0.75)
    ctx.set_source(shade)
    ctx.paint()
    ctx.restore()
    if look["air"]:                                             # a thin glow of air
        ctx.set_source_rgba(*s, 0.35)
        ctx.set_line_width(max(1.5, r * 0.04))
        ctx.arc(x, y, r * 1.02, 0, 2 * math.pi)
        ctx.stroke()
    if look["rings"]:
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(1.0, 0.28)
        ctx.set_source_rgba(*s, 0.7)
        ctx.set_line_width(r * 0.18)
        ctx.arc(0, 0, r * 1.7, math.pi, 2 * math.pi)                 # the back half shows above the ball
        ctx.stroke()
        ctx.restore()


def _rocket(ctx, x, y, h, t):
    """the rocket going up (screen space), its fire flickering"""
    w = h * 0.2
    for k in range(3):
        fl = h * (0.35 + 0.12 * math.sin(t * 37 + k * 2))
        ctx.move_to(x - w * (0.55 - k * 0.15), y + h * 0.5)
        ctx.line_to(x, y + h * 0.5 + fl * (1 - k * 0.25))
        ctx.line_to(x + w * (0.55 - k * 0.15), y + h * 0.5)
        ctx.close_path()
        ctx.set_source_rgb(*[(1, 0.5, 0.1), (1, 0.78, 0.2), (1, 1, 0.85)][k])
        ctx.fill()
    ctx.move_to(x - w / 2, y + h * 0.5)
    ctx.line_to(x - w / 2, y - h * 0.15)
    ctx.curve_to(x - w / 2, y - h * 0.38, x, y - h * 0.5, x, y - h * 0.5)
    ctx.curve_to(x, y - h * 0.5, x + w / 2, y - h * 0.38, x + w / 2, y - h * 0.15)
    ctx.line_to(x + w / 2, y + h * 0.5)
    ctx.close_path()
    ctx.set_source_rgb(0.92, 0.93, 0.95)
    ctx.fill()
    for sgn in (-1, 1):                                          # fins
        ctx.move_to(x + sgn * w / 2, y + h * 0.15)
        ctx.line_to(x + sgn * w * 1.05, y + h * 0.52)
        ctx.line_to(x + sgn * w / 2, y + h * 0.45)
        ctx.close_path()
        ctx.set_source_rgb(0.85, 0.2, 0.2)
        ctx.fill()
    ctx.set_source_rgb(0.35, 0.65, 0.95)
    ctx.arc(x, y - h * 0.1, w * 0.22, 0, 2 * math.pi)
    ctx.fill()


def _draw_cruise(ctx, R, v, t, W, H, S):
    # stars streaming down past the rocket (it flies up the screen)
    r = random.Random(11)
    speed = H * (0.6 + 1.6 * math.sin(math.pi * clamp(v, 0, 1)))
    ctx.set_line_cap(1)
    for _ in range(170):
        x, y0, s = r.random() * W, r.random() * H, r.random()
        y = (y0 + t * speed * (0.3 + s)) % H
        ln = (2 + 26 * s) * speed / H
        ctx.set_source_rgba(1, 1, 1, 0.3 + 0.6 * s)
        ctx.set_line_width(0.8 + 1.4 * s * H / 1080)
        ctx.move_to(x, y)
        ctx.line_to(x, y - ln)
        ctx.stroke()
    # the old planet falling away below, the new one coming from above
    ra = H * (1.4 * (1 - v) ** 2 + 0.03)
    _planet_ball(ctx, W * 0.5, H + ra * 0.55 + v * H * 0.4, ra, R["a"])
    rb = H * (0.03 + 0.95 * v ** 2.2)
    _planet_ball(ctx, W * 0.62, -rb * 0.15 + H * 0.22 * (1 - v) - rb * 0.25 * v, rb, R["b"])
    _rocket(ctx, W * 0.42 + math.sin(t * 1.3) * W * 0.01, H * 0.6, H * 0.26, t)


# ============================================================================ ⚫ a pass by a black hole (12.15)
BH_WORDS = ("black hole", "blackhole", "black_hole", "ब्लैक होल")


def wants_black_hole(spec):
    """the story asks for it: {"via": "black hole"} / {"black_hole": true} / "past a black hole" in the journey"""
    spec = spec or {}
    if spec.get("black_hole"):
        return True
    txt = " ".join(str(spec.get(k) or "") for k in ("via", "by", "past", "name", "note")).lower()
    return any(w in txt for w in BH_WORDS)


def bh_pass(R, spec=None, settings=None):
    """the real numbers for the flyby: r_s = 2GM/c², the closest pass (≥ 2 r_s - closer, a coasting ship can't
    get out again), clocks: dt/dτ = 1 / (1 - r_s/r) on a free (parabolic) flyby, the head-to-foot tidal pull"""
    from . import compact
    spec, settings = spec or {}, settings or {}
    m = spec.get("bh_mass") or spec.get("mass_sun")
    if m:
        b = compact.black_hole(float(m))
        b["name"] = str(spec.get("bh_name") or "a black hole")
    else:
        mw = (R.get("map") or {}).get("seed") == "milkyway" or settings.get("galaxy") in ("milkyway", None) and R.get("kind") in ("solar", "stars")
        b = compact.centre(1, "spiral", bool(mw))
    q = max(2.0, float(spec.get("closest_rs") or 2.5))
    rs = b["r_s_m"]
    G, M = 6.674e-11, b["mass_sun"] * 1.989e30
    tidal = 2 * G * M * 2.0 / (q * rs) ** 3                     # over a 2 m body
    v = math.sqrt(1.0 / q)                                      # parabolic speed at the closest point, as a fraction of c
    return {"name": b.get("name") or "a black hole", "mass_sun": b["mass_sun"], "r_s_m": rs, "horizon": b["horizon"], "closest_rs": q,
            "closest": compact._km(q * rs), "factor": round(1 / (1 - 1 / q), 3), "speed_c": round(v, 2), "tidal_g": tidal / 9.81,
            "supermassive": bool(b.get("supermassive")), "pass_s": math.pi * q * rs / (v * 3e8) * 2}


def _bh_factor(B, w):
    """the clock factor at pass progress w (0..1, closest at 0.5): r = q·r_s·(1 + 30·(w-½)²)"""
    r = B["closest_rs"] * (1 + 30 * (w - 0.5) ** 2)
    return 1 / (1 - 1 / r)


def _bh_clocks(B, w):
    """(ship seconds, far-away seconds) from the start of the pass to w: the ship's clock runs at 1, far away at f"""
    n = 60
    T = B["pass_s"] * 6                                         # the shot covers ~6 pass-times of ship clock
    ship = T * w
    far = sum(_bh_factor(B, (k + 0.5) / n * w) for k in range(n)) / n * ship
    return ship, far


def _clock_txt(s):
    s = max(0.0, s)
    if s >= 86400 * 2:
        return f"{s / 86400:.1f} days"
    h, m, x = int(s // 3600), int(s % 3600 // 60), int(s % 60)
    return f"{h:02d}:{m:02d}:{x:02d}"


def _draw_bh(ctx, R, w, t, W, H, S):
    """the pass: background stars lensed by the hole (a point-mass lens: two images θ± = (β ± √(β² + 4θE²)) / 2),
    the black shadow (2.6 r_s), the photon ring, the hot disk (the side coming toward us brighter) whose far side
    is bent up over the top; two clocks"""
    import cairo
    B = R["bh"]
    ctx.set_source_rgb(0.004, 0.006, 0.02)
    ctx.paint()
    cx = W * (0.85 - 0.7 * w)                                    # it slides past us, biggest when closest
    cy = H * 0.46
    near = math.exp(-((w - 0.5) / 0.22) ** 2)
    sh = H * (0.05 + 0.13 * near)                                # shadow radius on screen
    thE = sh * 1.25                                              # Einstein radius
    r = random.Random(17)
    for _ in range(420):                                         # the stars behind, drifting the other way
        bx = (r.random() * W * 1.6 - W * 0.3 + t * W * 0.03 * (0.3 + r.random())) % (W * 1.6) - W * 0.3
        by, s = r.random() * H, r.random()
        dx, dy = bx - cx, by - cy
        beta = math.hypot(dx, dy) or 0.01
        ux, uy = dx / beta, dy / beta
        for sg in (1, -1):
            th = (beta + sg * math.sqrt(beta * beta + 4 * thE * thE)) / 2
            if abs(th) < sh * 1.02:                              # inside the shadow: swallowed
                continue
            mag = abs(1 / (1 - (thE / th) ** 4)) if abs(th) != thE else 30
            mag = min(mag, 12)
            if sg < 0 and mag < 0.05:
                continue
            x, y = cx + ux * th, cy + uy * th
            ang = math.atan2(y - cy, x - cx)
            ln = (0.6 + 1.2 * s) * H / 1080 * min(10, mag)       # stretched along the ring
            ctx.set_source_rgba(1, 1, 1, min(1, (0.25 + 0.6 * s) * min(2, 0.5 + 0.5 * mag)))
            ctx.set_line_width((0.8 + 1.2 * s) * H / 1080)
            a0 = ln / max(5, abs(th))
            ctx.arc(cx, cy, abs(th), ang - a0, ang + a0)
            ctx.stroke()
    # the disk: a flat ring seen nearly edge-on; light from its far side is bent over the top (and under the bottom)
    def disk_half(front):
        ctx.save()
        ctx.rectangle(0, cy if front else 0, W, H)                # front half: below the middle line
        if not front:
            ctx.rectangle(0, 0, W, cy)
        ctx.clip()
        ctx.translate(cx, cy)
        ctx.scale(1, 0.17)
        g = cairo.LinearGradient(-sh * 3.6, 0, sh * 3.6, 0)      # Doppler: the side coming toward us (left) brighter
        g.add_color_stop_rgba(0, 1, 0.93, 0.75, 0.95)
        g.add_color_stop_rgba(0.5, 1, 0.66, 0.3, 0.85)
        g.add_color_stop_rgba(1, 0.75, 0.3, 0.1, 0.55)
        ctx.arc(0, 0, sh * 3.6, 0, 2 * math.pi)
        ctx.arc_negative(0, 0, sh * 1.5, 2 * math.pi, 0)
        ctx.set_source(g)
        ctx.fill()
        ctx.restore()
    ctx.save()                                                   # the far half of the disk (behind the hole)
    ctx.rectangle(0, 0, W, cy)
    ctx.clip()
    ctx.translate(cx, cy); ctx.scale(1, 0.17)
    g = cairo.LinearGradient(-sh * 3.6, 0, sh * 3.6, 0)
    g.add_color_stop_rgba(0, 1, 0.9, 0.7, 0.9); g.add_color_stop_rgba(1, 0.75, 0.3, 0.1, 0.5)
    ctx.arc(0, 0, sh * 3.6, 0, 2 * math.pi); ctx.arc_negative(0, 0, sh * 1.5, 2 * math.pi, 0)
    ctx.set_source(g); ctx.fill(); ctx.restore()
    for up, a in ((True, 0.95), (False, 0.45)):                  # the lifted image of the far side: a glowing arch
        ctx.save()
        ctx.rectangle(0, 0 if up else cy, W, cy if up else H - cy)
        ctx.clip()
        rg = cairo.RadialGradient(cx, cy, sh * 1.05, cx, cy, sh * (2.0 if up else 1.6))
        rg.add_color_stop_rgba(0, 1, 0.9, 0.7, a)
        rg.add_color_stop_rgba(0.25, 1, 0.65, 0.28, a * 0.8)
        rg.add_color_stop_rgba(1, 0.6, 0.2, 0.05, 0)
        ctx.arc(cx, cy, sh * (2.0 if up else 1.6), 0, 2 * math.pi)
        ctx.set_source(rg)
        ctx.fill()
        ctx.restore()
    ctx.set_source_rgb(0, 0, 0)                                  # the shadow (2.6 r_s)
    ctx.arc(cx, cy, sh, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(1, 0.88, 0.65, 0.95)                     # the photon ring
    ctx.set_line_width(max(1.2, sh * 0.035))
    ctx.arc(cx, cy, sh * 1.03, 0, 2 * math.pi)
    ctx.stroke()
    disk_half(True)                                              # the near half, in front of the shadow
    _rocket(ctx, W * 0.5 + math.sin(t * 1.3) * W * 0.01, H * 0.7, H * 0.15, t)
    # the clocks
    ship, far = _bh_clocks(B, w)
    f = _bh_factor(B, w)
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    fs = H * 0.034
    rows = [(f"ship clock     {_clock_txt(ship)}", (0.75, 0.9, 1)), (f"far away         {_clock_txt(far)}", (1, 0.85, 0.55)),
            (f"time here runs {f:.2f}× slower", (1, 1, 1))]
    bx, by = W * 0.04, H * 0.3
    ctx.set_source_rgba(0, 0, 0, 0.55)
    ctx.rectangle(bx - fs * 0.5, by - fs * 1.3, fs * 15, fs * 4.6)
    ctx.fill()
    for k, (txt, col) in enumerate(rows):
        ctx.set_font_size(fs if k < 2 else fs * 0.8)
        ctx.set_source_rgb(*col)
        ctx.move_to(bx, by + k * fs * 1.35)
        ctx.show_text(txt)
    # the explanation line
    ctx.set_font_size(H * 0.026)
    m = B["mass_sun"]
    mtxt = f"{m / 1e9:.3g} billion" if m >= 1e9 else f"{m / 1e6:.3g} million" if m >= 1e6 else f"{m:,.3g}"
    ln = (f"{B['name']}: {mtxt} Suns · horizon {B['horizon']} · closest pass {B['closest']} ({B['closest_rs']:g}× the horizon) at {B['speed_c']:g} c · "
          + ("light is bent round it (lensing): the stars behind smear into rings" if w < 0.5 else
             ("the tidal pull is gentle here - " if B["tidal_g"] < 1 else "the tidal pull would tear a ship apart - ") + "big black holes are the safest to pass"))
    words, lines, cur = ln.split(" "), [], ""
    for wd in words:
        if ctx.text_extents(cur + " " + wd).width > W * 0.86 and cur:
            lines.append(cur); cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    for k, txt in enumerate(lines[:3]):
        e = ctx.text_extents(txt)
        ctx.set_source_rgba(0, 0, 0, 0.6)
        ctx.move_to(W / 2 - e.width / 2 + 2, H * (0.9 + 0.035 * k) + 2)
        ctx.show_text(txt)
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(W / 2 - e.width / 2, H * (0.9 + 0.035 * k))
        ctx.show_text(txt)
