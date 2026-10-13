"""🧊 Stick 3D screen shots: full-frame flat graphics that tell the science part of a story.

A scene says "stick_screen": {...} and is drawn as a screen instead of the 3D world (the speech of the scene still
shows, as captions). Kinds:

  {"kind": "mp_map", "grow": 12, "alarm": 0.3, "title": "..."}
      Madhya Pradesh with a 50 km grid; Deepak's stations switch on one by one from his home (Bhopal) outward over
      `grow` seconds; LoRa links join neighbours (each radio reaches the next station, 50 km); data hops to the hub.
      `alarm` (0..1) turns that share of stations red: they read something wrong.
  {"kind": "data", "title": "...", "series": [{"name": "UV index", "from": 7, "to": 13, "unit": ""}, ...],
   "warn": "..."}
      line graphs drawn as time goes on (a month of readings); a red warning when `warn` is given.
  {"kind": "forum", "title": "...", "posts": [["user", "text", votes], ...]}
      a discussion page; the posts appear one after another.
  {"kind": "chat", "title": "...", "messages": [["who", "text"], ...]}
      phone messages appearing one by one.
  {"kind": "mine", "grow": 10, "depth": 100, "title": "..."}
      the underground works in cut-away: headframe, lift shaft, two tunnel levels, carts, the boring machine, miners.
  {"kind": "station_log", "station": 133}  the station's log on a rugged tablet, readings ticked green one by one.
  {"kind": "station_box", "open": 1.0}     a close-up inside the opened station box: board, LoRa radio, battery.
  {"kind": "car_nav", "to": "...", "arrive": 2.2}   the phone map on the dashboard: the route, then "You have arrived".
"""
import math
import random

import cairo

BG = (0.07, 0.10, 0.14)
PANEL = (0.11, 0.15, 0.20)
LINE = (0.24, 0.32, 0.40)
TEXT = (0.92, 0.95, 0.97)
DIM = (0.58, 0.66, 0.72)
OK = (0.30, 0.90, 0.55)
BAD = (0.98, 0.30, 0.28)

# Madhya Pradesh, roughly (lon, lat) - a cartoon outline, close enough to be recognised
MP = [(74.6, 24.6), (75.3, 24.9), (76.4, 24.8), (77.0, 25.9), (77.6, 26.8), (78.9, 26.6), (78.6, 25.6), (79.1, 25.2),
      (80.2, 25.3), (81.5, 25.0), (82.7, 24.3), (82.0, 23.2), (81.2, 22.4), (80.6, 21.7), (79.3, 21.6), (78.0, 21.3),
      (76.3, 21.1), (74.9, 21.6), (74.1, 22.3), (74.3, 23.2), (74.8, 23.8)]
HOME = (77.41, 23.26)                       # Bhopal: Deepak's home and the hub
CITIES = [("Bhopal", 77.41, 23.26), ("Indore", 75.86, 22.72), ("Jabalpur", 79.95, 23.18), ("Gwalior", 78.18, 26.22),
          ("Ujjain", 75.78, 23.18), ("Rewa", 81.30, 24.53), ("Sagar", 78.74, 23.84)]
KM_DEG = 111.0                              # km per degree of latitude


def _text(ctx, s, x, y, size, col):
    from . import textfx
    textfx.show_at(ctx, str(s), x, y, size, (*col, 1.0))


def _width(s, size):
    from . import textfx
    return textfx.width(str(s), size)


def _inside(pt, poly):
    x, y = pt
    c = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            c = not c
    return c


def _stations():
    """the 50 km grid cells inside the state (cell centres), nearest to the hub first"""
    dlat = 50.0 / KM_DEG
    dlon = 50.0 / (KM_DEG * math.cos(math.radians(23.5)))
    pts = []
    lat = 21.1 + dlat / 2
    while lat < 26.9:
        lon = 74.1 + dlon / 2
        while lon < 82.8:
            if _inside((lon, lat), MP):
                pts.append((lon, lat))
            lon += dlon
        lat += dlat
    pts.sort(key=lambda p: math.hypot(p[0] - HOME[0], p[1] - HOME[1]))
    return pts, dlon, dlat


def _frame(ctx, W, H, S, title):
    ctx.set_source_rgb(*BG)
    ctx.paint()
    ctx.rectangle(0, 0, W, 70 * S)
    ctx.set_source_rgb(*PANEL)
    ctx.fill()
    for k, c in enumerate(((0.95, 0.35, 0.3), (0.95, 0.75, 0.25), (0.35, 0.85, 0.45))):
        ctx.arc(34 * S + k * 28 * S, 35 * S, 8 * S, 0, 2 * math.pi)
        ctx.set_source_rgb(*c)
        ctx.fill()
    if title:
        _text(ctx, title, 130 * S, 47 * S, 30 * S, TEXT)


def mp_map(ctx, W, H, S, spec, t, frame):
    _frame(ctx, W, H, S, spec.get("title", "Weather network · Madhya Pradesh · 50 km grid"))
    pts, dlon, dlat = _stations()
    lon0, lon1, lat0, lat1 = 73.8, 83.1, 20.8, 27.1
    mh, mw = H - 170 * S, W * 0.66
    sc = min(mh / (lat1 - lat0), mw / ((lon1 - lon0) * math.cos(math.radians(23.5))))
    ox, oy = 60 * S, 100 * S

    def xy(lon, lat):
        return ox + (lon - lon0) * sc * math.cos(math.radians(23.5)), oy + (lat1 - lat) * sc

    # the state, its grid
    q = [xy(*p) for p in MP]
    ctx.move_to(*q[0])
    for p in q[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.set_source_rgb(0.13, 0.22, 0.20)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip_preserve()
    ctx.new_path()
    lon = 74.1
    while lon < 83:
        a, b = xy(lon, lat0), xy(lon, lat1)
        ctx.move_to(*a)
        ctx.line_to(*b)
        lon += dlon
    lat = 21.1
    while lat < 27:
        a, b = xy(lon0, lat), xy(lon1, lat)
        ctx.move_to(*a)
        ctx.line_to(*b)
        lat += dlat
    ctx.set_source_rgba(*LINE, 0.8)
    ctx.set_line_width(1.2 * S)
    ctx.stroke()
    ctx.restore()
    ctx.move_to(*q[0])
    for p in q[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.set_source_rgb(0.40, 0.75, 0.62)
    ctx.set_line_width(3 * S)
    ctx.stroke()
    # stations switch on from the hub outward
    grow = float(spec.get("grow", 12.0))
    on = len(pts) if grow <= 0 else int(len(pts) * min(1.0, max(0.0, t / grow)))
    alarm = float(spec.get("alarm", 0.0))
    rng = random.Random(7)
    bad = set(rng.sample(range(len(pts)), int(len(pts) * alarm))) if alarm > 0 else set()
    P = [xy(*p) for p in pts]
    ctx.set_line_width(1.5 * S)                                        # LoRa links to the neighbours
    for i in range(on):
        for j in range(i):
            if math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) <= max(dlon, dlat) * 1.05:
                ctx.move_to(*P[i])
                ctx.line_to(*P[j])
    ctx.set_source_rgba(*OK, 0.25)
    ctx.stroke()
    for i in range(on):                                                # the stations, blinking
        blink = 0.6 + 0.4 * math.sin(frame * 0.35 + i * 1.7)
        col = BAD if i in bad else OK
        ctx.arc(*P[i], 9 * S, 0, 2 * math.pi)
        ctx.set_source_rgba(*col, 0.25 * blink)
        ctx.fill()
        ctx.arc(*P[i], 4.5 * S, 0, 2 * math.pi)
        ctx.set_source_rgb(*col)
        ctx.fill()
    if on:                                                             # data packets hopping toward the hub
        for k in range(min(on, 18)):
            i = (k * 7 + frame // 6) % on
            u = (frame % 24) / 24.0
            a, b = P[i], xy(*HOME)
            ctx.arc(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, 3 * S, 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 1, 0.7)
            ctx.fill()
    for name, lon_, lat_ in CITIES:
        x, y = xy(lon_, lat_)
        _text(ctx, name, x + 10 * S, y - 10 * S, 20 * S, DIM)
    hx, hy = xy(*HOME)
    ctx.arc(hx, hy, 13 * S, 0, 2 * math.pi)
    ctx.set_source_rgb(0.98, 0.80, 0.25)
    ctx.set_line_width(3 * S)
    ctx.stroke()
    # the side panel: counts
    px = W * 0.72
    _text(ctx, "STATIONS ONLINE", px, 170 * S, 26 * S, DIM)
    _text(ctx, f"{on} / {len(pts)}", px, 240 * S, 64 * S, OK)
    _text(ctx, "LINK  LoRa 868 MHz · 50 km", px, 300 * S, 24 * S, DIM)
    if bad and on:
        n_bad = len([i for i in bad if i < on])
        _text(ctx, "ODD READINGS", px, 400 * S, 26 * S, DIM)
        _text(ctx, f"{n_bad}", px, 470 * S, 64 * S, BAD)


def data(ctx, W, H, S, spec, t, frame):
    if spec.get("fit"):                                                # inside the 2.39 film frame (the bars would
        ctx.set_source_rgb(*BG)                                        # cut the title and the first graph)
        ctx.paint()
        k = 0.76
        ctx.save()
        ctx.translate(W * (1 - k) / 2, H * (1 - k) / 2)
        ctx.scale(k, k)
        data(ctx, W, H, S, dict(spec, fit=False), t, frame)
        ctx.restore()
        return
    _frame(ctx, W, H, S, spec.get("title", "Station readings · last 30 days"))
    series = spec.get("series") or [{"name": "UV index", "from": 7, "to": 12},
                                    {"name": "Ozone (DU)", "from": 290, "to": 240},
                                    {"name": "Magnetic field (nT)", "from": 45000, "to": 43900}]
    grow = float(spec.get("grow", 8.0))
    u = 1.0 if grow <= 0 else min(1.0, max(0.02, t / grow))
    n = len(series)
    top, gap = 110 * S, 24 * S
    ph = (H - top - 60 * S - gap * (n - 1)) / n
    for k, s_ in enumerate(series):
        y0 = top + k * (ph + gap)
        x0, x1 = 60 * S, W - 360 * S
        ctx.rectangle(x0, y0, W - 120 * S, ph)
        ctx.set_source_rgb(*PANEL)
        ctx.fill()
        _text(ctx, s_.get("name", ""), x0 + 20 * S, y0 + 40 * S, 28 * S, TEXT)
        a, b = float(s_.get("from", 0)), float(s_.get("to", 1))
        lo, hi = min(a, b), max(a, b)
        pad = (hi - lo) * 0.25 or 1.0
        rng = random.Random(k * 31 + 5)
        npt = 60
        vals = [a + (b - a) * (i / (npt - 1)) ** 1.6 + rng.uniform(-0.08, 0.08) * (hi - lo) for i in range(npt)]
        m = max(2, int(npt * u))
        gx0, gy0, gw, gh = x0 + 20 * S, y0 + 60 * S, x1 - x0 - 40 * S, ph - 80 * S
        for g in range(5):                                             # grid lines
            yy = gy0 + gh * g / 4
            ctx.move_to(gx0, yy)
            ctx.line_to(gx0 + gw, yy)
        ctx.set_source_rgba(*LINE, 0.6)
        ctx.set_line_width(1 * S)
        ctx.stroke()
        rising_bad = (b > a) == bool(s_.get("bad_up", "UV" in s_.get("name", "")))
        col = BAD if rising_bad and u > 0.5 else OK
        for i in range(m):
            x = gx0 + gw * i / (npt - 1)
            y = gy0 + gh * (1 - (vals[i] - (lo - pad)) / ((hi + pad) - (lo - pad)))
            (ctx.move_to if i == 0 else ctx.line_to)(x, y)
        ctx.set_source_rgb(*col)
        ctx.set_line_width(4 * S)
        ctx.stroke()
        v = vals[m - 1]
        _text(ctx, f"{v:,.0f}" if abs(v) >= 100 else f"{v:.1f}", x1 + 20 * S, y0 + ph * 0.62, 52 * S, col)
        _text(ctx, s_.get("unit", ""), x1 + 20 * S, y0 + ph * 0.62 + 34 * S, 22 * S, DIM)
    warn = spec.get("warn")
    if warn and u >= 1.0 and (frame // 12) % 2 == 0:                   # the warning blinks once the graphs are drawn
        wd = _width(warn, 34 * S) + 60 * S
        ctx.rectangle(W - wd - 40 * S, 14 * S, wd, 44 * S)
        ctx.set_source_rgb(*BAD)
        ctx.fill()
        _text(ctx, warn, W - wd - 10 * S, 47 * S, 34 * S, (1, 1, 1))


def forum(ctx, W, H, S, spec, t, frame):
    _frame(ctx, W, H, S, spec.get("title", "Forum · weather & space"))
    posts = spec.get("posts") or []
    per = float(spec.get("every", 2.5))
    y = 110 * S
    for i, p in enumerate(posts):
        if t < i * per:
            break
        user, txt = str(p[0]), str(p[1])
        votes = p[2] if len(p) > 2 else ""
        lines = _wrap(txt, 34 * S, W - 340 * S)
        hh = (70 + 44 * len(lines)) * S
        ctx.rectangle(60 * S, y, W - 120 * S, hh)
        ctx.set_source_rgb(*PANEL)
        ctx.fill()
        ctx.move_to(98 * S, y + 22 * S)                               # an up-vote arrow
        ctx.line_to(114 * S, y + 50 * S)
        ctx.line_to(82 * S, y + 50 * S)
        ctx.close_path()
        ctx.set_source_rgb(0.98, 0.55, 0.25)
        ctx.fill()
        _text(ctx, str(votes), 84 * S, y + 92 * S, 24 * S, DIM)
        _text(ctx, user, 170 * S, y + 40 * S, 22 * S, DIM)
        for k, ln in enumerate(lines):
            _text(ctx, ln, 170 * S, y + (84 + 44 * k) * S, 34 * S, TEXT)
        y += hh + 18 * S
        if y > H - 80 * S:
            break


def chat(ctx, W, H, S, spec, t, frame):
    ctx.set_source_rgb(*BG)
    ctx.paint()
    pw, phh = 620 * S, H - 80 * S                                     # a phone in the middle of the frame
    px, py = (W - pw) / 2, 40 * S
    ctx.rectangle(px, py, pw, phh)
    ctx.set_source_rgb(0.93, 0.95, 0.94)
    ctx.fill()
    ctx.rectangle(px, py, pw, 90 * S)
    ctx.set_source_rgb(0.13, 0.45, 0.38)
    ctx.fill()
    _text(ctx, spec.get("title", "Chat"), px + 30 * S, py + 58 * S, 32 * S, (1, 1, 1))
    per = float(spec.get("every", 2.0))
    y = py + 120 * S
    me = spec.get("me", "")
    for i, m in enumerate(spec.get("messages") or []):
        if t < i * per:
            break
        who, txt = str(m[0]), str(m[1])
        mine = who == me
        lines = _wrap(txt, 28 * S, pw - 180 * S)
        bw = max(_width(ln, 28 * S) for ln in lines) + 40 * S
        bh = (40 + 36 * len(lines)) * S
        bx = px + pw - bw - 24 * S if mine else px + 24 * S
        ctx.rectangle(bx, y, bw, bh)
        ctx.set_source_rgb(*((0.84, 0.96, 0.78) if mine else (1, 1, 1)))
        ctx.fill()
        _text(ctx, who, bx + 20 * S, y + 28 * S, 20 * S, (0.13, 0.45, 0.38))
        for k, ln in enumerate(lines):
            _text(ctx, ln, bx + 20 * S, y + (62 + 36 * k) * S, 28 * S, (0.1, 0.1, 0.1))
        y += bh + 16 * S
        if y > py + phh - 60 * S:
            break


def land(ctx, W, H, S, spec, t, frame):
    """the land seen from above, growing plot by plot: 10 acres at first, then the next fields as they are
    bought, to `to` acres (each square is 10 acres, about 200 m a side); the year counts up with it"""
    _frame(ctx, W, H, S, spec.get("title", "Deepak's land · near Bhopal"))
    a0, a1 = float(spec.get("from", 10)), float(spec.get("to", 300))
    y0, y1 = int(spec.get("from_year", 2026)), int(spec.get("to_year", 2027))
    grow = float(spec.get("grow", 10.0))
    u = 1.0 if grow <= 0 else min(1.0, max(0.0, t / grow))
    u = u * u * (3 - 2 * u)
    total_ = max(1, int(round(a1 / 10.0)))                             # plots of 10 acres, as many as the land needs
    cols = max(3, int(math.ceil(math.sqrt(total_ * 1.25))))
    rows = int(math.ceil(total_ / cols))
    gx, gy = 80 * S, 110 * S
    cell = min((W * 0.62 - gx) / cols, (H - gy - 80 * S) / rows)
    start = (cols // 2 - 1, rows // 2)
    order = sorted(((c, r) for c in range(cols) for r in range(rows)),
                   key=lambda p: (abs(p[0] - start[0]) + abs(p[1] - start[1]), p[1], p[0]))
    total = max(1, int(round(a1 / 10.0)))
    owned_n = max(1, int(round((a0 + (a1 - a0) * u) / 10.0)))
    owned = set(order[:min(total, owned_n)])
    rng = random.Random(3)
    for c in range(cols):                                              # fields: dry scrub, the owned ones fenced
        for r in range(rows):
            x, y = gx + c * cell, gy + r * cell
            mine = (c, r) in owned
            base = (0.78, 0.68, 0.46) if mine else (0.42, 0.52, 0.36)
            v = rng.uniform(-0.04, 0.04)
            ctx.rectangle(x + 2 * S, y + 2 * S, cell - 4 * S, cell - 4 * S)
            ctx.set_source_rgb(*(min(1, b + v) for b in base))
            ctx.fill()
    # the boundary of the owned land (outer edges of owned squares)
    ctx.set_source_rgb(0.98, 0.82, 0.25)
    ctx.set_line_width(5 * S)
    for (c, r) in owned:
        x, y = gx + c * cell, gy + r * cell
        for (dc, dr), seg in (((0, -1), ((x, y), (x + cell, y))), ((0, 1), ((x, y + cell), (x + cell, y + cell))),
                              ((-1, 0), ((x, y), (x, y + cell))), ((1, 0), ((x + cell, y), (x + cell, y + cell)))):
            if (c + dc, r + dr) not in owned:
                ctx.move_to(*seg[0])
                ctx.line_to(*seg[1])
    ctx.stroke()
    # a road along the bottom, a river on the right
    ctx.rectangle(gx - 20 * S, gy + rows * cell + 14 * S, cols * cell + 40 * S, 22 * S)
    ctx.set_source_rgb(0.55, 0.55, 0.57)
    ctx.fill()
    ctx.move_to(gx + cols * cell + 40 * S, gy - 10 * S)
    ctx.curve_to(gx + cols * cell + 10 * S, gy + cell * 2, gx + cols * cell + 70 * S, gy + cell * 3.5,
                 gx + cols * cell + 30 * S, gy + rows * cell + 10 * S)
    ctx.set_source_rgb(0.35, 0.62, 0.85)
    ctx.set_line_width(14 * S)
    ctx.stroke()
    sx, sy = gx + (start[0] + 0.5) * cell, gy + (start[1] + 0.5) * cell   # the first plot: the house mark
    ctx.move_to(sx - 16 * S, sy + 10 * S)
    ctx.line_to(sx, sy - 12 * S)
    ctx.line_to(sx + 16 * S, sy + 10 * S)
    ctx.close_path()
    ctx.set_source_rgb(0.85, 0.30, 0.25)
    ctx.fill()
    px = W * 0.70
    acres = 10 * len(owned)
    year = int(round(y0 + (y1 - y0) * u))
    _text(ctx, "LAND", px, 190 * S, 26 * S, DIM)
    _text(ctx, f"{acres} acres", px, 270 * S, 72 * S, (0.98, 0.82, 0.25))
    _text(ctx, f"about {acres * 5 / 3:.0f} bigha", px, 320 * S, 26 * S, DIM)
    _text(ctx, "YEAR", px, 420 * S, 26 * S, DIM)
    _text(ctx, str(year), px, 500 * S, 72 * S, TEXT)


# a cartoon world map (lon, lat): rough continent outlines, enough to read as "the whole world"
CONTINENTS = [
    [(-168, 66), (-140, 70), (-95, 72), (-62, 60), (-55, 50), (-80, 25), (-97, 18), (-83, 9), (-78, 7), (-105, 20),
     (-118, 33), (-125, 48), (-140, 60)],                                                   # North America
    [(-78, 8), (-60, 10), (-35, -6), (-40, -22), (-58, -38), (-70, -54), (-75, -45), (-72, -18), (-81, -4)],  # South America
    [(-10, 36), (-17, 15), (-8, 4), (10, 4), (12, -6), (20, -35), (32, -28), (40, -15), (51, 11), (43, 12),
     (33, 31), (10, 37)],                                                                   # Africa
    [(-10, 36), (-9, 43), (-2, 50), (5, 58), (20, 70), (40, 68), (60, 70), (100, 77), (140, 72), (180, 66),
     (160, 58), (142, 46), (130, 35), (122, 25), (108, 18), (105, 9), (98, 15), (92, 22), (88, 21), (80, 15),
     (77, 8), (72, 21), (66, 25), (57, 25), (52, 13), (43, 12), (35, 30), (28, 37), (12, 44)],   # Eurasia
    [(114, -22), (122, -18), (136, -12), (145, -15), (153, -26), (150, -37), (140, -38), (130, -32), (116, -35)],  # Australia
]
HUBS = [(-122, 37, "California"), (-95, 30, "Texas"), (-74, 41, "New York"), (-47, -15, "Brazil"), (-80, 9, "Panama"),
        (77, 23, "India"), (2, 48, "France"), (139, 36, "Japan"), (28, -26, "South Africa"), (151, -34, "Australia")]


def world_map(ctx, W, H, S, spec, t, frame):
    """the world, its monitoring stations as dots; "dark_at" seconds: many stations go dark at once (the dots die,
    rings show where); "alert": a red banner; "storms": [[lon, lat], ...] spinning cyclones"""
    _frame(ctx, W, H, S, spec.get("title", "Global monitoring network"))
    x0, y0, mw = 40 * S, 90 * S, W - 80 * S
    mh = mw / 2.0

    def xy(lon, lat):
        return x0 + (lon + 180) / 360 * mw, y0 + (90 - lat) / 180 * mh
    ctx.rectangle(x0, y0, mw, min(mh, H - y0 - 40 * S))
    ctx.set_source_rgb(0.06, 0.13, 0.20)
    ctx.fill()
    for poly in CONTINENTS:
        q = [xy(*p) for p in poly]
        ctx.move_to(*q[0])
        for p in q[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        ctx.set_source_rgb(0.16, 0.30, 0.26)
        ctx.fill_preserve()
        ctx.set_source_rgb(0.32, 0.62, 0.50)
        ctx.set_line_width(2 * S)
        ctx.stroke()
    rng = random.Random(5)
    pts = []
    while len(pts) < 900:                                              # stations on land
        lon, lat = rng.uniform(-170, 175), rng.uniform(-50, 72)
        if any(_inside((lon, lat), poly) for poly in CONTINENTS):
            pts.append((lon, lat))
    dark_at = spec.get("dark_at")
    gone = set()
    if dark_at is not None and t >= float(dark_at):
        r2 = random.Random(9)
        gone = set(r2.sample(range(len(pts)), int(len(pts) * float(spec.get("dark_share", 0.35)))))
    for i, (lon, lat) in enumerate(pts):
        x, y = xy(lon, lat)
        if i in gone:
            u = min(1.0, (t - float(dark_at)) / 1.5)
            ctx.arc(x, y, (3 + 9 * u) * S, 0, 2 * math.pi)
            ctx.set_source_rgba(*BAD, 0.5 * (1 - u) + 0.15)
            ctx.set_line_width(1.2 * S)
            ctx.stroke()
            continue
        blink = 0.55 + 0.45 * math.sin(frame * 0.3 + i)
        ctx.arc(x, y, 2.4 * S, 0, 2 * math.pi)
        ctx.set_source_rgba(*OK, blink)
        ctx.fill()
    for k, (lon, lat) in enumerate(spec.get("storms") or ()):          # cyclones: spiral arms turning
        x, y = xy(lon, lat)
        for arm in range(3):
            a0 = frame * 0.12 + arm * 2 * math.pi / 3
            ctx.move_to(x, y)
            for j in range(1, 16):
                a, r = a0 + j * 0.35, j * 2.6 * S
                ctx.line_to(x + r * math.cos(a), y + r * math.sin(a))
            ctx.set_source_rgba(0.85, 0.92, 1.0, 0.85)
            ctx.set_line_width(3 * S)
            ctx.stroke()
    for lon, lat, name in HUBS if spec.get("labels", True) else ():
        x, y = xy(lon, lat)
        _text(ctx, name, x + 8 * S, y - 6 * S, 18 * S, DIM)
    alert = spec.get("alert")
    if alert and (dark_at is None or t >= float(dark_at) + 1.0) and (frame // 10) % 3 != 0:
        wd = _width(alert, 40 * S) + 80 * S
        ctx.rectangle((W - wd) / 2, H - 140 * S, wd, 70 * S)
        ctx.set_source_rgb(*BAD)
        ctx.fill()
        _text(ctx, alert, (W - wd) / 2 + 40 * S, H - 92 * S, 40 * S, (1, 1, 1))
    n_live = len(pts) - len(gone)
    _text(ctx, f"STATIONS ONLINE  {n_live} / {len(pts)}", W - 520 * S, 52 * S, 28 * S, BAD if gone else OK)


def call(ctx, W, H, S, spec, t, frame):
    """a phone ringing / in a call: the caller's name, where from, the call timer"""
    ctx.set_source_rgb(*BG)
    ctx.paint()
    pw, ph = 560 * S, H - 100 * S
    px, py = (W - pw) / 2, 50 * S
    ctx.rectangle(px, py, pw, ph)
    ctx.set_source_rgb(0.10, 0.20, 0.18)
    ctx.fill()
    name = str(spec.get("name", "Unknown"))
    sub = str(spec.get("from", ""))
    cx, cy = px + pw / 2, py + 330 * S
    ring = spec.get("ringing", t < float(spec.get("answer_at", 2.0)))
    for k in range(3 if ring else 0):                                  # rings pulsing out of the photo
        u = ((t * 0.8 + k / 3) % 1.0)
        ctx.arc(cx, cy, (90 + 120 * u) * S, 0, 2 * math.pi)
        ctx.set_source_rgba(0.4, 0.9, 0.6, 0.5 * (1 - u))
        ctx.set_line_width(4 * S)
        ctx.stroke()
    ctx.arc(cx, cy, 90 * S, 0, 2 * math.pi)
    ctx.set_source_rgb(0.30, 0.55, 0.50)
    ctx.fill()
    _text(ctx, name[:1].upper(), cx - _width(name[:1].upper(), 90 * S) / 2, cy + 32 * S, 90 * S, (1, 1, 1))
    _text(ctx, name, cx - _width(name, 44 * S) / 2, cy + 180 * S, 44 * S, (1, 1, 1))
    _text(ctx, sub, cx - _width(sub, 26 * S) / 2, cy + 225 * S, 26 * S, DIM)
    if ring:
        msg = "incoming call..."
    else:
        el = max(0.0, t - float(spec.get("answer_at", 2.0)))
        msg = f"{int(el // 60):02d}:{int(el % 60):02d}"
    _text(ctx, msg, cx - _width(msg, 30 * S) / 2, cy + 280 * S, 30 * S, OK)
    for k, col in enumerate(((0.85, 0.25, 0.22), (0.25, 0.75, 0.40))):
        bx = cx + (-120 + 240 * k) * S
        ctx.arc(bx, py + ph - 120 * S, 46 * S, 0, 2 * math.pi)
        ctx.set_source_rgb(*col)
        ctx.fill()


def doc(ctx, W, H, S, spec, t, frame):
    """a confidential document on screen: a stamp, a title, lines of text appearing; "highlight": a line index lit"""
    ctx.set_source_rgb(*BG)
    ctx.paint()
    px, py, pw = W * 0.2, 60 * S, W * 0.6
    ctx.rectangle(px, py, pw, H - 120 * S)
    ctx.set_source_rgb(0.96, 0.95, 0.90)
    ctx.fill()
    title = str(spec.get("title", "CONFIDENTIAL"))
    _text(ctx, title, px + 50 * S, py + 80 * S, 40 * S, (0.12, 0.12, 0.15))
    st = str(spec.get("stamp", "CONFIDENTIAL"))                        # the red stamp
    sw = _width(st, 30 * S) + 30 * S
    sx0, sy0 = px + pw - sw - 40 * S, py + 40 * S
    ctx.rectangle(sx0, sy0, sw, 52 * S)
    ctx.set_source_rgb(0.80, 0.15, 0.15)
    ctx.set_line_width(4 * S)
    ctx.stroke()
    _text(ctx, st, sx0 + 15 * S, sy0 + 38 * S, 30 * S, (0.80, 0.15, 0.15))
    lines = spec.get("lines") or []
    per = float(spec.get("every", 1.4))
    hl = spec.get("highlight")
    y = py + 160 * S
    for i, ln in enumerate(lines):
        if t < i * per:
            break
        for k, part in enumerate(_wrap(str(ln), 28 * S, pw - 100 * S)):
            if hl is not None and int(hl) == i and t > (i + 1) * per:
                ctx.rectangle(px + 44 * S, y - 30 * S, _width(part, 28 * S) + 12 * S, 40 * S)
                ctx.set_source_rgba(1.0, 0.85, 0.2, 0.6)
                ctx.fill()
            _text(ctx, part, px + 50 * S, y, 28 * S, (0.2, 0.2, 0.24))
            y += 42 * S
        y += 14 * S


def plan(ctx, W, H, S, spec, t, frame):
    """the underground settlement in cross-section: the fields on top, the layers of earth, and levels built down to
    the design depth (default 100 m) - homes, farms under lights, water, power, hospital, workshops - drawn in as
    time goes on; the people count beside it"""
    _frame(ctx, W, H, S, spec.get("title", "Underground settlement · cross-section (concept)"))
    depth = float(spec.get("depth", 100))
    gx0, gx1, gy = 80 * S, W - 520 * S, 210 * S
    gy1 = H - 80 * S
    ctx.rectangle(gx0, 90 * S, gx1 - gx0, gy - 90 * S)                 # the sky
    ctx.set_source_rgb(0.30, 0.52, 0.72)
    ctx.fill()
    for k, col in enumerate(((0.45, 0.62, 0.30), (0.52, 0.40, 0.28), (0.44, 0.34, 0.25), (0.36, 0.30, 0.25), (0.30, 0.27, 0.25))):
        y0 = gy + (gy1 - gy) * (0 if k == 0 else (0.02 + 0.245 * (k - 1)))
        y1 = gy + (gy1 - gy) * (0.02 if k == 0 else (0.02 + 0.245 * k))
        ctx.rectangle(gx0, y0, gx1 - gx0, y1 - y0)
        ctx.set_source_rgb(*col)
        ctx.fill()
    shaft_x = gx0 + (gx1 - gx0) * 0.18                                  # the entrance: the farmhouse and its shaft
    ctx.rectangle(shaft_x - 30 * S, gy - 40 * S, 60 * S, 40 * S)
    ctx.set_source_rgb(0.95, 0.90, 0.80)
    ctx.fill()
    levels = spec.get("levels") or ["Homes", "Farms under lights", "Hospital · school", "Water · recycling",
                                    "Power · workshops"]
    grow = float(spec.get("grow", 8.0))
    shown = len(levels) if grow <= 0 else int(len(levels) * min(1.0, t / grow) + 0.999)
    lh = (gy1 - gy - 60 * S) / len(levels)
    shaft_bottom = gy + 30 * S + lh * max(1, shown)
    ctx.rectangle(shaft_x - 14 * S, gy, 28 * S, shaft_bottom - gy)
    ctx.set_source_rgb(0.12, 0.12, 0.14)
    ctx.fill()
    cols = [(0.95, 0.80, 0.40), (0.50, 0.85, 0.45), (0.95, 0.55, 0.55), (0.45, 0.70, 0.95), (0.80, 0.80, 0.82)]
    for i in range(shown):
        y = gy + 40 * S + i * lh
        ctx.rectangle(shaft_x + 30 * S, y, (gx1 - shaft_x) - 80 * S, lh - 24 * S)
        ctx.set_source_rgb(*cols[i % len(cols)])
        ctx.fill()
        _text(ctx, levels[i], shaft_x + 60 * S, y + (lh - 24 * S) / 2 + 12 * S, 30 * S, (0.12, 0.12, 0.14))
    ctx.move_to(gx1 + 30 * S, gy)                                      # the depth scale
    ctx.line_to(gx1 + 30 * S, gy1 - 20 * S)
    ctx.set_source_rgb(*TEXT)
    ctx.set_line_width(3 * S)
    ctx.stroke()
    for k in range(5):
        y = gy + (gy1 - 20 * S - gy) * k / 4
        _text(ctx, f"{int(depth * k / 4)} m", gx1 + 45 * S, y + 10 * S, 24 * S, DIM)
    px = W - 420 * S
    _text(ctx, "PEOPLE", px, 220 * S, 26 * S, DIM)
    _text(ctx, f"{int(spec.get('people', 10000)):,}", px, 300 * S, 72 * S, OK)
    _text(ctx, "TARGET", px, 400 * S, 26 * S, DIM)
    _text(ctx, str(spec.get("year", 2035)), px, 480 * S, 72 * S, TEXT)
    _text(ctx, "LAND", px, 580 * S, 26 * S, DIM)
    _text(ctx, f"{int(spec.get('acres', 500))} acres", px, 650 * S, 56 * S, (0.98, 0.82, 0.25))


INKC = (0.18, 0.14, 0.12)


def _poly(ctx, pts, fill, S, ink=INKC, lw=2.2):
    ctx.move_to(*pts[0])
    for q in pts[1:]:
        ctx.line_to(*q)
    ctx.close_path()
    ctx.set_source_rgb(*fill)
    if ink is None:
        ctx.fill()
        return
    ctx.fill_preserve()
    ctx.set_source_rgb(*ink)
    ctx.set_line_width(lw * S)
    ctx.set_line_join(1)
    ctx.stroke()


def _rrect(ctx, x, y, w, h, r, fill, S, ink=INKC, lw=2.2):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()
    ctx.set_source_rgb(*fill)
    if ink is None:
        ctx.fill()
        return
    ctx.fill_preserve()
    ctx.set_source_rgb(*ink)
    ctx.set_line_width(lw * S)
    ctx.stroke()


def _disc(ctx, x, y, r, fill, S, ink=INKC, lw=2.0):
    ctx.new_sub_path()
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.set_source_rgb(*fill)
    if ink is None:
        ctx.fill()
        return
    ctx.fill_preserve()
    ctx.set_source_rgb(*ink)
    ctx.set_line_width(lw * S)
    ctx.stroke()


def _truck2d(ctx, x, y, S, k=1.0, f=1):
    """a flat yellow dump truck, side on (x, y = the middle of its wheels' base), f = +1 facing right"""
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(f * k * S, k * S)
    _poly(ctx, [(-70, -28), (30, -28), (36, -70), (-80, -70)], (0.98, 0.76, 0.16), 1)          # the bed
    _poly(ctx, [(30, -24), (66, -24), (66, -48), (52, -66), (34, -66)], (0.99, 0.80, 0.22), 1)   # the cab
    _poly(ctx, [(40, -46), (56, -46), (50, -60), (40, -60)], (0.30, 0.64, 0.76), 1, lw=1.5)
    _poly(ctx, [(-72, -28), (68, -28), (68, -18), (-72, -18)], (0.42, 0.43, 0.46), 1)
    for wx in (-48, -22, 46):
        _disc(ctx, wx, -12, 13, (0.38, 0.39, 0.42), 1)
        _disc(ctx, wx, -12, 6, (0.98, 0.76, 0.16), 1, lw=1.2)
    ctx.restore()


def _worker(ctx, x, y, S, t, ph, k=1.0):
    """a miner in silhouette: helmet with a lamp, swinging a pickaxe at the rock face"""
    sw = math.sin(t * 4.0 + ph)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(k * S, k * S)
    ctx.set_source_rgb(0.16, 0.14, 0.14)
    ctx.set_line_width(6)
    ctx.set_line_cap(1)
    ctx.move_to(-8, 0); ctx.line_to(0, -26); ctx.line_to(8, 0)                       # legs
    ctx.move_to(0, -26); ctx.line_to(2, -52)                                         # body
    a = -0.9 + 0.8 * sw                                                              # the swing
    hx, hy = 2 + 22 * math.cos(a), -48 + 22 * math.sin(a)
    ctx.move_to(2, -48); ctx.line_to(hx, hy)
    ctx.stroke()
    ctx.set_line_width(4)
    tip = (hx + 24 * math.cos(a + 1.3), hy + 24 * math.sin(a + 1.3))
    ctx.move_to(hx - 6 * math.cos(a + 1.3), hy - 6 * math.sin(a + 1.3)); ctx.line_to(*tip)
    ctx.stroke()
    ctx.move_to(tip[0] - 9 * math.cos(a), tip[1] - 9 * math.sin(a)); ctx.line_to(tip[0] + 9 * math.cos(a), tip[1] + 9 * math.sin(a))
    ctx.stroke()
    ctx.arc(3, -61, 9, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgb(0.98, 0.82, 0.25)                                             # the helmet lamp
    ctx.arc(10, -66, 3.2, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def mine(ctx, W, H, S, spec, t, frame):
    """the underground works in cut-away (like a mine): the surface with its headframe tower and turning wheel,
    silos, a conveyor, ore heaps, trucks and the cliffs beyond; below, the layers of earth, the lift shaft with its
    cage going up and down, two tunnel levels joined by a ramp, rails with ore carts, the boring machine cutting
    the tunnel longer as time goes on, and miners at the face. spec: "grow" (seconds for the tunnels to reach
    full length, default 10), "depth" (m, default 100: the scale on the right), "title" (a small label)"""
    rng = random.Random(7)
    gy = 0.43 * H                                                      # the surface
    g = cairo.LinearGradient(0, 0, 0, gy)
    g.add_color_stop_rgb(0, 0.42, 0.72, 0.95)
    g.add_color_stop_rgb(1, 0.76, 0.90, 0.98)
    ctx.set_source(g)
    ctx.paint()
    for cx, cy, cw in ((0.12, 0.06, 1.0), (0.38, 0.09, 0.8), (0.70, 0.05, 1.1), (0.92, 0.10, 0.7)):
        x0 = (cx * W + t * 6 * S) % (W + 300 * S) - 150 * S              # clouds drift
        for dx, r in ((-40, 22), (0, 30), (40, 22)):
            _disc(ctx, x0 + dx * cw * S, cy * H, r * cw * S, (1, 1, 1), S, ink=None)
    x = -20 * S                                                        # the cliffs (mesas) on the horizon
    while x < W:
        w_ = rng.uniform(140, 260) * S
        h_ = rng.uniform(0.14, 0.26) * H
        top = gy - 40 * S - h_
        pts = [(x, gy - 30 * S), (x + 10 * S, top + 30 * S), (x + 30 * S, top), (x + w_ - 40 * S, top + rng.uniform(-10, 10) * S),
               (x + w_ - 10 * S, top + 40 * S), (x + w_, gy - 30 * S)]
        _poly(ctx, pts, rng.choice(((0.62, 0.50, 0.42), (0.56, 0.44, 0.37), (0.66, 0.55, 0.46))), S)
        for j in range(3):
            lx = x + rng.uniform(0.2, 0.8) * w_
            ctx.move_to(lx, top + 20 * S)
            ctx.line_to(lx + rng.uniform(-6, 6) * S, gy - 40 * S)
            ctx.set_source_rgba(0.30, 0.22, 0.18, 0.6)
            ctx.set_line_width(2 * S)
            ctx.stroke()
        x += w_ - 30 * S
    _poly(ctx, [(0, gy - 36 * S), (W, gy - 36 * S), (W, gy), (0, gy)], (0.88, 0.80, 0.66), S, ink=None)
    for k in range(5):                                                 # dunes of spoil
        x0 = (0.1 + k * 0.2) * W
        _poly(ctx, [(x0 - 120 * S, gy - 20 * S), (x0, gy - 60 * S), (x0 + 140 * S, gy - 20 * S)], (0.84, 0.75, 0.60),
              S, ink=None)
    lay = [(0.55, 0.45, 0.36), (0.48, 0.38, 0.30), (0.42, 0.33, 0.27), (0.36, 0.29, 0.24), (0.30, 0.25, 0.21)]
    for k, col in enumerate(lay):                                      # the layers of earth
        y0 = gy + (H - gy) * k / len(lay)
        _poly(ctx, [(0, y0), (W, y0 + 6 * S * math.sin(k)), (W, H), (0, H)], col, S, ink=None)
    for k in range(70):                                                # stones in the earth
        sx, sy = rng.uniform(0, W), rng.uniform(gy + 20 * S, H)
        ctx.save()
        ctx.translate(sx, sy)
        ctx.scale(1.0, 0.6)
        ctx.arc(0, 0, rng.uniform(5, 12) * S, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgba(0.78, 0.70, 0.62, 0.5)
        ctx.fill()
    grow = float(spec.get("grow", 10.0))
    u = 1.0 if grow <= 0 else max(0.25, min(1.0, t / grow))
    sx = 0.27 * W                                                      # the shaft and the tunnels
    y1, y2 = gy + 0.30 * (H - gy), gy + 0.78 * (H - gy)
    th = 0.11 * (H - gy)
    rim = (0.20, 0.16, 0.14)
    end_ = W - 200 * S                                                 # (the tunnels stop short of the scale)
    l1 = (0.22 * W + 0.50 * W * u) * (end_ - 0.27 * W) / (0.72 * W)
    l2 = (0.30 * W + 0.55 * W * min(1.0, u * 1.2)) * (end_ - 0.15 * W) / (0.85 * W)
    rx = sx - 0.12 * W                                                 # the ramp joining the two levels
    for pad, col in ((14 * S, rim), (0.0, (0.86, 0.80, 0.72))):
        _rrect(ctx, sx - 34 * S - pad, gy - pad, 68 * S + 2 * pad, y1 + th - gy + pad * 2, 10 * S, col, S, ink=None)
        _rrect(ctx, sx - pad, y1 - pad, l1 + 2 * pad, th + 2 * pad, th / 2, col, S, ink=None)
        _rrect(ctx, rx - pad, y1 - pad, sx - rx + 40 * S + 2 * pad, th + 2 * pad, th / 2, col, S, ink=None)
        _rrect(ctx, rx - pad, y1 - pad, 70 * S + 2 * pad, y2 - y1 + th + 2 * pad, 30 * S, col, S, ink=None)
        _rrect(ctx, rx - pad, y2 - pad, l2 + 2 * pad, th + 2 * pad, th / 2, col, S, ink=None)
    for (x0, x1, yy) in ((sx, sx + l1 - 40 * S, y1 + th - 10 * S), (rx + 20 * S, rx + l2 - 40 * S, y2 + th - 10 * S)):
        ctx.move_to(x0, yy)                                            # the rails and their sleepers
        ctx.line_to(x1, yy)
        ctx.set_source_rgb(0.40, 0.36, 0.34)
        ctx.set_line_width(4 * S)
        ctx.stroke()
        xx = x0
        while xx < x1:
            ctx.rectangle(xx, yy - 2 * S, 6 * S, 8 * S)
            xx += 22 * S
        ctx.set_source_rgb(0.46, 0.34, 0.24)
        ctx.fill()
    cage = 0.5 - 0.5 * math.cos(t * 0.6)                               # the lift: down, wait, up
    cy = gy + 20 * S + cage * (y1 - gy - 30 * S)
    ctx.move_to(sx, gy - 230 * S)
    ctx.line_to(sx, cy)
    ctx.set_source_rgb(0.25, 0.25, 0.27)
    ctx.set_line_width(3 * S)
    ctx.stroke()
    lg = cairo.LinearGradient(0, cy, 0, cy + 110 * S)                  # its lamp lights the shaft below
    lg.add_color_stop_rgba(0, 1, 1, 0.92, 0.85)
    lg.add_color_stop_rgba(1, 1, 1, 0.92, 0.0)
    ctx.move_to(sx - 16 * S, cy + 26 * S)
    ctx.line_to(sx + 16 * S, cy + 26 * S)
    ctx.line_to(sx + 30 * S, cy + 110 * S)
    ctx.line_to(sx - 30 * S, cy + 110 * S)
    ctx.close_path()
    ctx.set_source(lg)
    ctx.fill()
    _rrect(ctx, sx - 24 * S, cy, 48 * S, 28 * S, 4 * S, (0.72, 0.74, 0.78), S)
    for row, (x0, x1, yy, n, ph) in enumerate(((sx + 60 * S, sx + l1 - 260 * S, y1 + th - 14 * S, 4, 0.0),
                                               (rx + 80 * S, rx + l2 - 160 * S, y2 + th - 14 * S, 4, 1.7))):
        span = max(10 * S, x1 - x0)                                     # ore carts rolling along the rails
        base = x0 + (0.5 - 0.5 * math.cos(t * 0.35 + ph)) * span * 0.6
        for j in range(n):
            cx_ = base + j * 46 * S
            _poly(ctx, [(cx_ - 18 * S, yy - 28 * S), (cx_ + 18 * S, yy - 28 * S), (cx_ + 14 * S, yy - 6 * S),
                        (cx_ - 14 * S, yy - 6 * S)], (0.52, 0.36, 0.28), S)
            _poly(ctx, [(cx_ - 16 * S, yy - 28 * S), (cx_ - 6 * S, yy - 38 * S), (cx_ + 8 * S, yy - 36 * S),
                        (cx_ + 16 * S, yy - 28 * S)], (0.20, 0.18, 0.18), S, lw=1.4)
            for wx in (-9, 9):
                _disc(ctx, cx_ + wx * S, yy - 4 * S, 5 * S, (0.30, 0.28, 0.28), S, lw=1.2)
    bx = sx + l1 - 60 * S                                              # the boring machine at the face
    by = y1 + th - 12 * S
    _poly(ctx, [(bx - 120 * S, by - 4 * S), (bx - 10 * S, by - 4 * S), (bx - 4 * S, by - 18 * S), (bx - 126 * S, by - 18 * S)],
          (0.30, 0.30, 0.32), S)
    _poly(ctx, [(bx - 112 * S, by - 18 * S), (bx - 20 * S, by - 18 * S), (bx - 14 * S, by - 52 * S), (bx - 80 * S, by - 58 * S),
                (bx - 112 * S, by - 44 * S)], (0.99, 0.75, 0.15), S)
    _poly(ctx, [(bx - 104 * S, by - 44 * S), (bx - 82 * S, by - 44 * S), (bx - 82 * S, by - 70 * S), (bx - 100 * S, by - 70 * S)],
          (0.99, 0.80, 0.22), S)
    _poly(ctx, [(bx - 99 * S, by - 50 * S), (bx - 87 * S, by - 50 * S), (bx - 87 * S, by - 64 * S), (bx - 99 * S, by - 64 * S)],
          (0.30, 0.64, 0.76), S, lw=1.2)
    ctx.move_to(bx - 30 * S, by - 40 * S)
    ctx.line_to(bx + 6 * S, by - 56 * S)
    ctx.set_source_rgb(0.99, 0.75, 0.15)
    ctx.set_line_width(10 * S)
    ctx.stroke()
    _disc(ctx, bx + 14 * S, by - 56 * S, 26 * S, (0.62, 0.60, 0.58), S)    # the cutter head, turning
    for j in range(8):
        a = t * 5 + j * math.pi / 4
        ctx.move_to(bx + 14 * S, by - 56 * S)
        ctx.line_to(bx + 14 * S + 24 * S * math.cos(a), by - 56 * S + 24 * S * math.sin(a))
    ctx.set_source_rgb(*INKC)
    ctx.set_line_width(2.5 * S)
    ctx.stroke()
    for k in range(4):                                                 # miners at the lower face
        _worker(ctx, rx + l2 - (60 + k * 150) * S, y2 + th - 12 * S, S, t, k * 1.3, 1.0)
    hx = sx                                                            # the headframe: a lattice tower, its wheel
    ty = gy - 230 * S
    for a_, b_ in (((hx - 40 * S, gy), (hx - 10 * S, ty)), ((hx + 40 * S, gy), (hx + 10 * S, ty))):
        ctx.move_to(*a_)
        ctx.line_to(*b_)
    for k in range(6):
        yy = gy - k * (gy - ty) / 6
        wd = 40 * S - 30 * S * k / 6
        ctx.move_to(hx - wd, yy)
        ctx.line_to(hx + wd - 30 * S / 6, yy - (gy - ty) / 6)
        ctx.move_to(hx + wd, yy)
        ctx.line_to(hx - wd + 30 * S / 6, yy - (gy - ty) / 6)
    ctx.set_source_rgb(0.20, 0.18, 0.18)
    ctx.set_line_width(3 * S)
    ctx.stroke()
    _disc(ctx, hx, ty, 22 * S, (0.42, 0.42, 0.44), S)
    for j in range(6):
        a = -t * 2.0 + j * math.pi / 3
        ctx.move_to(hx, ty)
        ctx.line_to(hx + 20 * S * math.cos(a), ty + 20 * S * math.sin(a))
    ctx.set_source_rgb(*INKC)
    ctx.set_line_width(2 * S)
    ctx.stroke()
    for bx_, bh, bw in ((0.08, 190, 70), (0.165, 240, 76)):           # brick towers
        x0 = bx_ * W
        _poly(ctx, [(x0, gy), (x0, gy - bh * S), (x0 + bw / 2 * S, gy - (bh + 26) * S), (x0 + bw * S, gy - bh * S),
                    (x0 + bw * S, gy)], (0.50, 0.38, 0.34), S)
        for r_ in range(int(bh / 50)):
            for c_ in range(2):
                ctx.rectangle(x0 + (12 + c_ * 30) * S, gy - (bh - 20 - r_ * 50) * S, 14 * S, 20 * S)
        ctx.set_source_rgb(0.24, 0.18, 0.16)
        ctx.fill()
    ctx.move_to(hx + 40 * S, gy - 30 * S)                              # the conveyor to the shed
    ctx.line_to(0.40 * W, gy - 120 * S)
    ctx.set_source_rgb(0.28, 0.26, 0.26)
    ctx.set_line_width(8 * S)
    ctx.stroke()
    _poly(ctx, [(0.38 * W, gy), (0.38 * W, gy - 110 * S), (0.45 * W, gy - 130 * S), (0.45 * W, gy)], (0.58, 0.48, 0.42), S)
    _disc(ctx, 0.415 * W, gy - 60 * S, 22 * S, (0.40, 0.38, 0.38), S)
    for k, x0 in enumerate((0.52, 0.60)):                              # silos
        x0 *= W
        _poly(ctx, [(x0 - 32 * S, gy - 70 * S), (x0 + 32 * S, gy - 70 * S), (x0 + 32 * S, gy - 190 * S),
                    (x0 - 32 * S, gy - 190 * S)], (0.80, 0.82, 0.86), S)
        _poly(ctx, [(x0 - 32 * S, gy - 70 * S), (x0 + 32 * S, gy - 70 * S), (x0, gy - 30 * S)], (0.70, 0.72, 0.76), S)
        for lx in (-20, 20):
            ctx.move_to(x0 + lx * S, gy - 50 * S)
            ctx.line_to(x0 + lx * S, gy)
        ctx.set_source_rgb(*INKC)
        ctx.set_line_width(3 * S)
        ctx.stroke()
    for x0, h0, col in ((0.50, 50, (0.30, 0.30, 0.32)), (0.66, 70, (0.25, 0.24, 0.25)), (0.93, 120, (0.62, 0.50, 0.40))):
        _poly(ctx, [((x0 - 0.06) * W, gy), (x0 * W, gy - h0 * S), ((x0 + 0.07) * W, gy)], col, S)   # heaps
    tx = (0.40 + 0.40 * (0.5 - 0.5 * math.cos(t * 0.3))) * W           # trucks on the surface road
    _truck2d(ctx, tx, gy - 4 * S, S, 0.9, 1 if math.sin(t * 0.3) >= 0 else -1)
    _truck2d(ctx, 0.78 * W, gy - 4 * S, S, 1.1, -1)
    depth = float(spec.get("depth", 100))                              # the depth scale
    ctx.move_to(W - 60 * S, gy)
    ctx.line_to(W - 60 * S, H - 30 * S)
    ctx.set_source_rgba(1, 1, 1, 0.7)
    ctx.set_line_width(3 * S)
    ctx.stroke()
    for k in range(5):
        yy = gy + (H - 30 * S - gy) * k / 4
        _text(ctx, f"{int(depth * k / 4)} m", W - 150 * S, yy + 8 * S, 24 * S, (1, 1, 1))
    if spec.get("title"):
        _rrect(ctx, 30 * S, 24 * S, _width(spec["title"], 30 * S) + 40 * S, 52 * S, 10 * S, (0.10, 0.12, 0.16), S, ink=None)
        _text(ctx, spec["title"], 50 * S, 60 * S, 30 * S, (1, 1, 1))


def news(ctx, W, H, S, spec, t, frame):
    """a TV news broadcast seen on a television (an insert shot, as films do): the anchor at the desk, the live
    pictures of the storm beside them (a hurricane's spiral on radar, then rain, bending palms and waves), the red
    BREAKING NEWS bar, the place, the channel and the ticker running along the bottom. spec: "channel", "headline",
    "place", "ticker", "footage" ("hurricane" | "heat" | "flood"), "tv": false for the broadcast alone (full frame)"""
    if spec.get("tv", True) is not False:                              # the television in a dark room: the
        ctx.set_source_rgb(0.06, 0.05, 0.05)                           # broadcast is drawn full size, then fitted
        ctx.paint()                                                    # into the screen
        bx, by, bw, bh = 150 * S, 70 * S, W - 300 * S, H - 170 * S
        _rrect(ctx, bx - 26 * S, by - 26 * S, bw + 52 * S, bh + 52 * S, 22 * S, (0.12, 0.12, 0.13), S, ink=None)
        _rrect(ctx, W / 2 - 160 * S, by + bh + 26 * S, 320 * S, 18 * S, 6 * S, (0.10, 0.10, 0.11), S, ink=None)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W), int(H))
        news(cairo.Context(surf), W, H, S, dict(spec, tv=False), t, frame)
        ctx.save()
        ctx.translate(bx, by)
        ctx.scale(bw / W, bh / H)
        ctx.set_source_surface(surf, 0, 0)
        ctx.paint()
        ctx.restore()
        g = cairo.LinearGradient(0, 0, W, H)                           # the glass of the screen
        g.add_color_stop_rgba(0, 1, 1, 1, 0.07)
        g.add_color_stop_rgba(0.5, 1, 1, 1, 0.0)
        ctx.set_source(g)
        ctx.rectangle(bx, by, bw, bh)
        ctx.fill()
        return
    ctx.save()
    ctx.set_source_rgb(0.10, 0.16, 0.32)                               # the studio: a deep blue set with light bands
    ctx.paint()
    for k in range(6):
        ctx.rectangle(0, H * (0.08 + k * 0.11), W, 6 * S)
        ctx.set_source_rgba(0.35, 0.55, 0.95, 0.18)
        ctx.fill()
    fx0, fy0, fw, fh = W * 0.47, H * 0.12, W * 0.48, H * 0.52          # the live pictures
    ctx.save()
    ctx.rectangle(fx0, fy0, fw, fh)
    ctx.clip()
    kind = str(spec.get("footage", "hurricane")).lower()
    seg = int(t / 4.0) % 2
    if kind == "hurricane" and seg == 0:                               # radar: the spiral turning over the coast
        ctx.set_source_rgb(0.05, 0.08, 0.12)
        ctx.paint()
        _poly(ctx, [(fx0, fy0 + fh * 0.55), (fx0 + fw * 0.45, fy0 + fh * 0.5), (fx0 + fw * 0.7, fy0 + fh * 0.62),
                    (fx0 + fw, fy0 + fh * 0.58), (fx0 + fw, fy0 + fh), (fx0, fy0 + fh)], (0.18, 0.30, 0.20), S, ink=None)
        cx, cy = fx0 + fw * 0.42, fy0 + fh * 0.45
        for arm in range(4):
            for j in range(60):
                a = j * 0.12 + arm * math.pi / 2 - t * 0.9
                r = 6 * S + j * 3.2 * S
                x, y = cx + r * math.cos(a), cy + r * math.sin(a) * 0.8
                col = (0.95, 0.20, 0.15) if j < 18 else ((0.98, 0.80, 0.20) if j < 38 else (0.25, 0.80, 0.35))
                _disc(ctx, x, y, (10 - j * 0.1) * S, col, S, ink=None)
        _disc(ctx, cx, cy, 8 * S, (0.05, 0.08, 0.12), S, ink=None)
        _text(ctx, "RADAR · LIVE", fx0 + 14 * S, fy0 + 34 * S, 22 * S, (1, 1, 1))
    else:                                                              # the street: rain, bending palms, waves
        g = cairo.LinearGradient(0, fy0, 0, fy0 + fh)
        g.add_color_stop_rgb(0, 0.30, 0.33, 0.38)
        g.add_color_stop_rgb(1, 0.18, 0.20, 0.24)
        ctx.set_source(g)
        ctx.paint()
        sea_y = fy0 + fh * 0.62
        ctx.rectangle(fx0, sea_y, fw, fh)
        ctx.set_source_rgb(0.20, 0.30, 0.36)
        ctx.fill()
        for k in range(5):                                             # waves breaking over the sea wall
            wx = fx0 + ((k * 0.23 + t * 0.12) % 1.0) * fw
            _poly(ctx, [(wx - 60 * S, sea_y + 10 * S), (wx, sea_y - 40 * S - 20 * S * math.sin(t * 3 + k)),
                        (wx + 60 * S, sea_y + 10 * S)], (0.85, 0.90, 0.95), S, ink=None)
        bend = 0.5 + 0.25 * math.sin(t * 2.5)
        for k, px in enumerate((0.25, 0.55, 0.8)):                     # palms bent by the wind
            x0, y0 = fx0 + fw * px, sea_y + 30 * S
            tx_, ty_ = x0 + 70 * S * bend, y0 - 150 * S
            ctx.move_to(x0, y0)
            ctx.curve_to(x0, y0 - 80 * S, tx_ - 20 * S, ty_ + 40 * S, tx_, ty_)
            ctx.set_source_rgb(0.30, 0.22, 0.16)
            ctx.set_line_width(9 * S)
            ctx.stroke()
            for j in range(5):
                a = -0.3 + j * 0.35 + bend * 0.6
                ctx.move_to(tx_, ty_)
                ctx.curve_to(tx_ + 40 * S * math.cos(a), ty_ - 20 * S, tx_ + 70 * S * math.cos(a), ty_ + 10 * S,
                             tx_ + 90 * S * math.cos(a), ty_ + 45 * S * math.sin(a) + 20 * S)
                ctx.set_source_rgb(0.20, 0.42, 0.22)
                ctx.set_line_width(6 * S)
                ctx.stroke()
        r = random.Random(frame * 31 + 5)                              # the rain, driven sideways
        ctx.set_source_rgba(0.85, 0.88, 0.95, 0.5)
        ctx.set_line_width(2 * S)
        for _ in range(220):
            x, y = fx0 + r.uniform(-0.1, 1.0) * fw, fy0 + r.uniform(0, 1) * fh
            ctx.move_to(x, y)
            ctx.line_to(x + 22 * S, y + 30 * S)
        ctx.stroke()
        _text(ctx, "LIVE", fx0 + 14 * S, fy0 + 34 * S, 24 * S, (1, 0.3, 0.3))
    ctx.restore()
    ctx.rectangle(fx0, fy0, fw, fh)
    ctx.set_source_rgb(0.85, 0.88, 0.95)
    ctx.set_line_width(4 * S)
    ctx.stroke()
    ax, ay = W * 0.24, H * 0.62                                        # the anchor at the desk
    _poly(ctx, [(ax - 110 * S, ay - 150 * S), (ax + 110 * S, ay - 150 * S), (ax + 120 * S, ay + 20 * S),
                (ax - 120 * S, ay + 20 * S)], (0.16, 0.18, 0.24), S)
    ctx.move_to(ax - 18 * S, ay - 150 * S)
    ctx.line_to(ax, ay - 110 * S)
    ctx.line_to(ax + 18 * S, ay - 150 * S)
    ctx.set_source_rgb(0.85, 0.15, 0.18)
    ctx.set_line_width(8 * S)
    ctx.stroke()
    _disc(ctx, ax, ay - 210 * S, 62 * S, (0.98, 0.84, 0.72), S)
    ctx.new_sub_path()
    ctx.arc(ax, ay - 222 * S, 64 * S, math.pi * 1.05, math.pi * 1.95)
    ctx.close_path()
    ctx.set_source_rgb(0.45, 0.30, 0.18)
    ctx.fill()
    for ex in (-22, 22):
        _disc(ctx, ax + ex * S, ay - 212 * S, 6 * S, (0.12, 0.1, 0.1), S, ink=None)
    talk = abs(math.sin(t * 9.0)) * (0.5 + 0.5 * math.sin(t * 2.3)) if spec.get("talking", True) else 0.0
    ctx.save()
    ctx.translate(ax, ay - 182 * S)
    ctx.scale(1.0, max(0.15, talk))
    ctx.arc(0, 0, 14 * S, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgb(0.45, 0.12, 0.12)
    ctx.fill()
    _poly(ctx, [(0, ay + 10 * S), (W, ay + 10 * S), (W, H), (0, H)], (0.20, 0.24, 0.36), S, ink=None)
    by_ = H * 0.74                                                     # the BREAKING NEWS bar
    _poly(ctx, [(0, by_), (W * 0.26, by_), (W * 0.26, by_ + 70 * S), (0, by_ + 70 * S)], (0.85, 0.08, 0.10), S, ink=None)
    _text(ctx, "BREAKING NEWS", 24 * S, by_ + 48 * S, 34 * S, (1, 1, 1))
    _poly(ctx, [(W * 0.26, by_), (W, by_), (W, by_ + 70 * S), (W * 0.26, by_ + 70 * S)], (0.97, 0.97, 0.97), S, ink=None)
    _text(ctx, str(spec.get("headline", "HURRICANE MAKES LANDFALL")), W * 0.27 + 10 * S, by_ + 48 * S, 34 * S,
          (0.08, 0.08, 0.10))
    _poly(ctx, [(0, by_ + 70 * S), (W, by_ + 70 * S), (W, by_ + 112 * S), (0, by_ + 112 * S)], (0.10, 0.14, 0.26), S,
          ink=None)
    _text(ctx, str(spec.get("place", "Houston, Texas")) + " · LIVE", 24 * S, by_ + 100 * S, 26 * S, (1, 0.85, 0.3))
    tk = "   ·   ".join([str(spec.get("ticker", "Record UV levels reported across the southern United States"))] * 4)
    tw = _width(tk, 26 * S)
    _poly(ctx, [(0, H - 52 * S), (W, H - 52 * S), (W, H), (0, H)], (0.05, 0.06, 0.10), S, ink=None)
    _text(ctx, tk, W - (t * 160 * S) % (tw + W), H - 16 * S, 26 * S, (1, 1, 1))
    _rrect(ctx, W - 210 * S, 24 * S, 180 * S, 60 * S, 10 * S, (0.85, 0.08, 0.10), S, ink=None)
    _text(ctx, str(spec.get("channel", "WNN 24")), W - 190 * S, 66 * S, 32 * S, (1, 1, 1))
    ctx.restore()


def station_log(ctx, W, H, S, spec, t, frame):
    """the station's own log on Deepak's rugged tablet, in the rain: the readings come in line by line, each
    checked green, then ALL SENSORS OK (or a red line where "bad" says). spec: "station", "rows":
    [["Air temperature", "31.2 °C"], ...], "bad": index of a failing row, "rain": drops on the glass (default on)"""
    ctx.set_source_rgb(0.12, 0.13, 0.12)                               # the tablet in its rubber case
    ctx.paint()
    _rrect(ctx, 70 * S, 140 * S, W - 140 * S, H - 280 * S, 40 * S, (0.20, 0.22, 0.20), S, ink=None)
    sx, sy, sw, sh = 120 * S, 165 * S, W - 240 * S, H - 330 * S       # inside the cinema bars too
    _rrect(ctx, sx, sy, sw, sh, 14 * S, (0.06, 0.09, 0.12), S, ink=None)
    _text(ctx, f"STATION {spec.get('station', 133)} · LOG", sx + 40 * S, sy + 70 * S, 40 * S, (0.55, 0.90, 1.0))
    _text(ctx, "LoRa 868 MHz · last packet 00:00:04 ago", sx + 40 * S, sy + 112 * S, 24 * S, DIM)
    rows = spec.get("rows") or [["Air temperature", "27.4 °C"], ["Humidity", "91 %"], ["Rain", "14 mm/h"],
                                ["Wind", "22 km/h  SW"], ["UV index", "1.8"], ["Pressure", "998 hPa"],
                                ["Battery", "92 %"], ["Signal", "-97 dBm"]]
    bad = spec.get("bad")
    per = float(spec.get("per", 0.45))
    shown = min(len(rows), int(max(0.0, t - 0.4) / per) + 1)
    rh = (sh - 230 * S) / len(rows)
    for i in range(shown):
        y = sy + 140 * S + i * rh
        _text(ctx, rows[i][0], sx + 60 * S, y + rh * 0.65, 28 * S, TEXT)
        _text(ctx, rows[i][1], sx + sw * 0.52, y + rh * 0.65, 28 * S, TEXT)
        ok = bad is None or int(bad) != i
        cx, cy = sx + sw - 110 * S, y + rh * 0.45
        _disc(ctx, cx, cy, 16 * S, OK if ok else BAD, S, ink=None)
        ctx.move_to(cx - 8 * S, cy)
        if ok:
            ctx.line_to(cx - 2 * S, cy + 7 * S)
            ctx.line_to(cx + 9 * S, cy - 7 * S)
        else:
            ctx.move_to(cx - 7 * S, cy - 7 * S)
            ctx.line_to(cx + 7 * S, cy + 7 * S)
            ctx.move_to(cx + 7 * S, cy - 7 * S)
            ctx.line_to(cx - 7 * S, cy + 7 * S)
        ctx.set_source_rgb(1, 1, 1)
        ctx.set_line_width(4 * S)
        ctx.stroke()
    if shown >= len(rows) and t > 0.4 + per * len(rows):              # the verdict
        good = bad is None
        _rrect(ctx, sx + 40 * S, sy + sh - 80 * S, sw - 80 * S, 58 * S, 10 * S, OK if good else BAD, S, ink=None)
        _text(ctx, "ALL SENSORS OK" if good else "SENSOR FAULT", sx + 70 * S, sy + sh - 38 * S, 34 * S, (0.05, 0.08, 0.08))
    if spec.get("rain", True):                                         # rain drops on the glass
        r = random.Random(int(t * 2) * 7 + 3)
        for i in range(70):
            x, y = r.uniform(sx, sx + sw), r.uniform(sy, sy + sh)
            rr = r.uniform(3, 9) * S
            ctx.new_sub_path()
            ctx.arc(x, y, rr, 0, 2 * math.pi)
            ctx.set_source_rgba(0.75, 0.82, 0.90, 0.18)
            ctx.fill()
            ctx.new_sub_path()
            ctx.arc(x - rr * 0.3, y - rr * 0.3, rr * 0.25, 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 1, 0.35)
            ctx.fill()


def station_box(ctx, W, H, S, spec, t, frame):
    """an insert close-up: Deepak opens the station box in the rain and we look inside (like the real one): a
    white louvred case (the slats let air through but keep sun and rain out), a dark solar glass lid, the stubby
    LoRa antenna, and inside on a perfboard the microcontroller, the LoRa radio with its shield can, the wires and
    the LiPo battery. The front door swings open over "open" seconds (0 = already open); the green TX LED blinks
    each time a packet goes out. "rain": drops (default on)"""
    ctx.save()
    sky = cairo.LinearGradient(0, 0, 0, H)                             # behind: the corn out of focus in the rain
    sky.add_color_stop_rgb(0, 0.46, 0.54, 0.58)
    sky.add_color_stop_rgb(0.45, 0.24, 0.36, 0.24)
    sky.add_color_stop_rgb(1, 0.14, 0.22, 0.14)
    ctx.set_source(sky)
    ctx.paint()
    r = random.Random(11)
    for i in range(40):                                                # soft blurred stalks and leaves
        x = r.uniform(0, W)
        ctx.set_source_rgba(0.30, 0.50, 0.26, r.uniform(0.15, 0.35))
        ctx.set_line_width(r.uniform(14, 40) * S)
        ctx.move_to(x, H)
        ctx.curve_to(x + r.uniform(-40, 40) * S, H * 0.6, x + r.uniform(-60, 60) * S, H * 0.3, x + r.uniform(-90, 90) * S, r.uniform(0, H * 0.3))
        ctx.stroke()
    k = S * 0.78 * (1.0 + 0.025 * t)                                    # a slow push in (fits the 2.39 frame)
    ctx.translate(W / 2, H / 2 + 60 * S)
    ctx.scale(k, k)
    ink = (0.30, 0.30, 0.32)
    white, shade = (0.95, 0.95, 0.93), (0.80, 0.80, 0.78)
    _rrect(ctx, 90, -470, 70, 110, 30, white, 1, ink=ink)            # the mounting tab with its hole
    _disc(ctx, 125, -430, 13, (0.25, 0.30, 0.25), 1, ink=None)
    ctx.set_line_cap(1)                                                # the stubby antenna
    ctx.set_source_rgb(*ink)
    ctx.set_line_width(30)
    ctx.move_to(-250, -330)
    ctx.line_to(-268, -640)
    ctx.stroke()
    ctx.set_source_rgb(0.88, 0.88, 0.88)
    ctx.set_line_width(24)
    ctx.move_to(-250, -330)
    ctx.line_to(-268, -640)
    ctx.stroke()
    _poly(ctx, [(310, -330), (365, -380), (365, 300), (310, 345)], shade, 1, ink=ink)   # the right outer side
    for i in range(14):                                                # its louvres
        y = -300 + i * 42
        _poly(ctx, [(318, y), (357, y - 34), (357, y - 24), (318, y + 10)], (0.62, 0.62, 0.60), 1, ink=None)
    _poly(ctx, [(-290, -320), (290, -320), (290, 320), (-290, 320)], (0.20, 0.22, 0.20), 1, ink=None)
    _poly(ctx, [(-220, -280), (230, -280), (230, 270), (-220, 270)], (0.90, 0.89, 0.85), 1, ink=None)   # back wall
    _poly(ctx, [(-290, -320), (-220, -280), (-220, 270), (-290, 320)], (0.84, 0.84, 0.81), 1, ink=None)  # left wall
    _poly(ctx, [(290, -320), (230, -280), (230, 270), (290, 320)], (0.76, 0.76, 0.73), 1, ink=None)     # right wall
    _poly(ctx, [(-290, 320), (-220, 270), (230, 270), (290, 320)], (0.88, 0.87, 0.83), 1, ink=None)     # floor
    for i in range(12):                                                # the slats of the inner walls, light between
        f = i / 12.0
        for x0, x1, top0, top1 in ((-288, -222, -318, -278), (288, 232, -318, -278)):
            y0 = top0 + f * 600
            y1 = top1 + f * 520
            _poly(ctx, [(x0, y0), (x1, y1), (x1, y1 + 16), (x0, y0 + 20)], (0.98, 0.98, 0.96), 1, ink=None)
    _rrect(ctx, -175, -255, 370, 320, 6, (0.28, 0.52, 0.26), 1, ink=(0.16, 0.30, 0.15), lw=3)   # the perfboard
    ctx.set_source_rgb(0.62, 0.52, 0.30)
    for yy in range(-245, 60, 14):
        for xx in range(-165, 190, 14):
            ctx.rectangle(xx, yy, 3.5, 3.5)
    ctx.fill()
    for (sx, sy) in ((-162, -242), (182, -242), (-162, 52), (182, 52)):
        _disc(ctx, sx, sy, 7, (0.75, 0.75, 0.75), 1, ink=(0.4, 0.4, 0.4), lw=1.5)
    _rrect(ctx, -150, -225, 120, 255, 4, (0.10, 0.20, 0.42), 1, ink=(0.05, 0.08, 0.18), lw=2)   # the microcontroller
    _rrect(ctx, -120, -130, 55, 55, 3, (0.08, 0.08, 0.09), 1, ink=None)
    _rrect(ctx, -140, -205, 26, 18, 2, (0.78, 0.78, 0.80), 1, ink=None)          # its crystal
    for i in range(12):                                                 # header pins down both sides
        ctx.set_source_rgb(0.82, 0.68, 0.30)
        ctx.rectangle(-147, -215 + i * 20, 8, 8)
        ctx.rectangle(-42, -215 + i * 20, 8, 8)
        ctx.fill()
    _disc(ctx, -72, -200, 6, (0.95, 0.20, 0.15), 1, ink=None)             # the power LED
    tx = (t % 2.0) < 0.18                                               # a packet goes out every 2 s
    _disc(ctx, -52, -200, 6, (0.30, 1.0, 0.45) if tx else (0.10, 0.30, 0.15), 1, ink=None)
    if tx:
        g = cairo.RadialGradient(-52, -200, 0, -52, -200, 30)
        g.add_color_stop_rgba(0, 0.4, 1.0, 0.5, 0.6)
        g.add_color_stop_rgba(1, 0.4, 1.0, 0.5, 0.0)
        ctx.set_source(g)
        ctx.arc(-52, -200, 30, 0, 2 * math.pi)
        ctx.fill()
    _rrect(ctx, 10, -235, 150, 150, 4, (0.12, 0.42, 0.28), 1, ink=(0.05, 0.20, 0.12), lw=2)   # the LoRa radio
    _rrect(ctx, 35, -205, 100, 90, 3, (0.78, 0.79, 0.80), 1, ink=(0.55, 0.55, 0.56), lw=2)    # its shield can
    for i in range(7):
        ctx.set_source_rgb(0.85, 0.72, 0.32)
        ctx.rectangle(14, -225 + i * 20, 7, 10)
        ctx.rectangle(149, -225 + i * 20, 7, 10)
        ctx.fill()
    _disc(ctx, 145, -222, 7, (0.85, 0.72, 0.32), 1, ink=None)             # the u.FL plug, coax up to the antenna
    ctx.set_source_rgb(0.15, 0.15, 0.15)
    ctx.set_line_width(5)
    ctx.move_to(145, -222)
    ctx.curve_to(150, -300, -100, -330, -235, -300)
    ctx.stroke()
    ctx.set_source_rgb(0.08, 0.08, 0.09)                                 # a black pin header at the bottom
    ctx.rectangle(-60, 40, 100, 20)
    ctx.fill()
    _rrect(ctx, -165, 175, 360, 90, 10, (0.82, 0.82, 0.84), 1, ink=(0.45, 0.45, 0.48), lw=2)   # the LiPo battery
    _rrect(ctx, -130, 185, 170, 70, 6, (0.92, 0.48, 0.16), 1, ink=None)
    ctx.set_source_rgb(0.25, 0.12, 0.05)
    for i in range(3):
        ctx.rectangle(-115, 200 + i * 18, 90 + 40 * (i % 2), 6)
    ctx.fill()
    _rrect(ctx, 150, 180, 55, 80, 6, (0.20, 0.40, 0.80), 1, ink=None)       # the blue tape at its end
    wires = [((0.85, 0.12, 0.10), [(-170, 210), (-260, 150), (-200, 0), (-120, 45)]),     # red: battery +
             ((0.10, 0.10, 0.10), [(-170, 230), (-250, 200), (-230, 60), (-100, 50)]),    # black: ground
             ((0.95, 0.80, 0.15), [(-130, -230), (-60, -320), (60, -300), (100, -240)]),  # yellow: data
             ((0.85, 0.12, 0.10), [(-30, -225), (60, -330), (200, -260), (175, -120)]),   # red: radio power
             ((0.20, 0.40, 0.85), [(-150, -100), (-230, -60), (-230, 120), (-160, 175)]),  # blue: the sensor line
             ((0.85, 0.12, 0.10), [(200, 220), (260, 220), (250, 140), (190, 30)]),       # the plug leads
             ((0.10, 0.10, 0.10), [(200, 240), (270, 250), (265, 140), (175, 40)])]
    for col, (a, b, c, d) in wires:
        ctx.set_source_rgb(*col)
        ctx.set_line_width(7)
        ctx.move_to(*a)
        ctx.curve_to(*b, *c, *d)
        ctx.stroke()
    sh = cairo.LinearGradient(0, -320, 0, -120)                        # the shade under the lid
    sh.add_color_stop_rgba(0, 0, 0, 0, 0.35)
    sh.add_color_stop_rgba(1, 0, 0, 0, 0.0)
    ctx.set_source(sh)
    ctx.rectangle(-290, -320, 580, 200)
    ctx.fill()
    for x0, x1 in ((-310, -290), (290, 310)):                          # the white frame posts and the sill
        _poly(ctx, [(x0, -330), (x1, -330), (x1, 345), (x0, 345)], white, 1, ink=ink)
    _poly(ctx, [(-310, 320), (310, 320), (310, 350), (-310, 350)], white, 1, ink=ink)
    _poly(ctx, [(-345, -330), (345, -330), (345, -300), (-345, -300)], white, 1, ink=ink)    # the roof's front edge
    _poly(ctx, [(-345, -330), (345, -330), (395, -385), (-295, -385)], white, 1, ink=ink)    # the roof top
    _poly(ctx, [(-320, -336), (330, -336), (372, -380), (-278, -380)], (0.36, 0.24, 0.16), 1, ink=None)  # solar glass
    ctx.set_source_rgba(1, 1, 1, 0.18)                                  # a sky reflection across the glass
    ctx.move_to(-100, -336)
    ctx.line_to(20, -336)
    ctx.line_to(80, -380)
    ctx.line_to(-40, -380)
    ctx.fill()
    op = float(spec.get("open", 1.0))                                  # the door swings out on its left hinge
    u = 1.0 if op <= 0 else max(0.0, min(1.0, t / op))
    u = u * u * (3 - 2 * u)
    ang = u * math.radians(115)
    fx = -300 + 600 * math.cos(ang)                                     # the free edge, seen from the front
    bulge = 60 * math.sin(ang)                                          # nearer to us: it looks taller
    if u < 0.999 or op > 0:
        face = white if math.cos(ang) > 0 else shade
        _poly(ctx, [(-300, -325), (fx, -325 - bulge), (fx, 340 + bulge), (-300, 340)], face, 1, ink=ink)
        if abs(fx + 300) > 40:
            for i in range(13):                                         # the door's louvres
                f = (i + 0.7) / 14.0
                ya, yb = -325 + f * 665, -325 - bulge + f * (665 + 2 * bulge)
                _poly(ctx, [(-300 + (fx + 300) * 0.08, ya), (fx - (fx + 300) * 0.08, yb),
                            (fx - (fx + 300) * 0.08, yb + 12), (-300 + (fx + 300) * 0.08, ya + 12)],
                      (0.72, 0.72, 0.70), 1, ink=None)
    if spec.get("rain", True):                                          # drips off the roof edge
        for i in range(9):
            x = -330 + i * 80 + 20 * math.sin(i * 3.1)
            ph = (t * 1.3 + i * 0.37) % 1.0
            _disc(ctx, x, -298 + ph * ph * 700, 6, (0.80, 0.88, 0.95), 1, ink=None)
    ctx.restore()
    if spec.get("rain", True):                                          # the rain between us and the box
        rr = random.Random(frame * 31 + 5)
        ctx.set_line_width(2.0 * S)
        for i in range(160):
            x, y = rr.uniform(-50, W), rr.uniform(-50, H)
            ctx.set_source_rgba(0.85, 0.90, 0.95, rr.uniform(0.15, 0.4))
            ctx.move_to(x, y)
            ctx.line_to(x - 8 * S, y + 46 * S)
            ctx.stroke()


def car_nav(ctx, W, H, S, spec, t, frame):
    """an insert in the car: the phone on its dashboard holder, the map app guiding him to the station; the car
    arrow runs along the blue route and "You have arrived" comes up. The rainy windscreen is behind (out of focus),
    the wiper crossing it. spec: "to" (the place name), "arrive" (seconds until arrival, default 2.2)"""
    sky = cairo.LinearGradient(0, 0, 0, H)                             # the windscreen, soft: grey sky, green field
    sky.add_color_stop_rgb(0, 0.52, 0.58, 0.64)
    sky.add_color_stop_rgb(0.5, 0.40, 0.48, 0.42)
    sky.add_color_stop_rgb(0.62, 0.28, 0.40, 0.24)
    sky.add_color_stop_rgb(1, 0.24, 0.32, 0.20)
    ctx.set_source(sky)
    ctx.paint()
    r = random.Random(int(t * 3) * 5 + 1)                              # drops on the glass
    for i in range(80):
        x, y = r.uniform(0, W), r.uniform(0, H * 0.7)
        rr = r.uniform(4, 12) * S
        ctx.new_sub_path()
        ctx.arc(x, y, rr, 0, 2 * math.pi)
        ctx.set_source_rgba(0.80, 0.86, 0.92, 0.22)
        ctx.fill()
        ctx.new_sub_path()
        ctx.arc(x - rr * 0.3, y - rr * 0.3, rr * 0.3, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.4)
        ctx.fill()
    wa = math.sin(t * 2.4)                                             # the wiper
    ctx.move_to(W * 0.3, H * 1.05)
    ctx.line_to(W * 0.3 + math.cos(-math.pi / 2 + wa) * W * 0.7, H * 1.05 + math.sin(-math.pi / 2 + wa) * W * 0.7)
    ctx.set_source_rgb(0.06, 0.06, 0.07)
    ctx.set_line_width(12 * S)
    ctx.stroke()
    ctx.move_to(0, H * 0.74)                                           # the dashboard
    ctx.curve_to(W * 0.3, H * 0.66, W * 0.7, H * 0.66, W, H * 0.72)
    ctx.line_to(W, H)
    ctx.line_to(0, H)
    ctx.close_path()
    ctx.set_source_rgb(0.13, 0.13, 0.15)
    ctx.fill()
    ctx.move_to(0, 0)                                                  # the windscreen pillar on the left
    ctx.line_to(W * 0.10, 0)
    ctx.line_to(W * 0.02, H * 0.78)
    ctx.line_to(0, H * 0.80)
    ctx.close_path()
    ctx.set_source_rgb(0.09, 0.09, 0.10)
    ctx.fill()
    ctx.new_sub_path()                                                 # the steering wheel's rim at the bottom left
    ctx.arc(W * 0.20, H * 1.18, H * 0.36, math.pi * 1.08, math.pi * 1.92)
    ctx.set_source_rgb(0.06, 0.06, 0.07)
    ctx.set_line_width(30 * S)
    ctx.stroke()
    pw, ph = 900 * S, 500 * S                                          # the phone, sideways in its holder
    px, py = W / 2 - pw / 2, H * 0.5 - ph / 2 + 30 * S
    _rrect(ctx, W / 2 - 40 * S, py + ph - 10 * S, 80 * S, 120 * S, 10 * S, (0.08, 0.08, 0.09), S, ink=None)
    _rrect(ctx, px - 18 * S, py - 18 * S, pw + 36 * S, ph + 36 * S, 34 * S, (0.06, 0.06, 0.07), S, ink=None)
    arrive = float(spec.get("arrive", 2.2))
    nav_phone(ctx, px, py, pw, ph, max(0.0, min(1.0, t / arrive)), str(spec.get("to", "Weather Station 133")))


def nav_phone(ctx, px, py, pw, ph, u, to="Weather Station 133"):
    """the map app on the phone's screen (px, py, pw, ph in pixels): fields, roads, the river, the blue route with
    the car arrow running along it (u = 0..1 of the way), then the "You have arrived" card"""
    S = pw / 900.0                                                     # (drawn for a 900 px wide screen)
    ctx.save()
    ctx.rectangle(px, py, pw, ph)
    ctx.clip()
    ctx.set_source_rgb(0.90, 0.92, 0.88)                               # the map: fields, roads, the river
    ctx.paint()
    for i in range(9):
        fx_ = px + (i % 3) * pw / 3 + 8 * S
        fy_ = py + (i // 3) * ph / 3 + 8 * S
        _rrect(ctx, fx_, fy_, pw / 3 - 16 * S, ph / 3 - 16 * S, 6 * S, (0.78, 0.88, 0.70) if i % 2 else (0.84, 0.90, 0.76),
               S, ink=None)
    ctx.set_source_rgb(0.62, 0.78, 0.92)
    ctx.set_line_width(14 * S)
    ctx.move_to(px + pw * 0.85, py - 10 * S)
    ctx.curve_to(px + pw * 0.7, py + ph * 0.4, px + pw * 0.95, py + ph * 0.7, px + pw * 0.8, py + ph + 10 * S)
    ctx.stroke()
    ctx.set_source_rgb(1, 1, 1)
    ctx.set_line_width(10 * S)
    for a, b in (((px, py + ph * 0.66), (px + pw, py + ph * 0.66)), ((px + pw * 0.34, py), (px + pw * 0.34, py + ph))):
        ctx.move_to(*a)
        ctx.line_to(*b)
        ctx.stroke()
    route = [(px + pw * 0.10, py + ph * 0.66), (px + pw * 0.34, py + ph * 0.66), (px + pw * 0.34, py + ph * 0.36),
             (px + pw * 0.62, py + ph * 0.36)]
    seglen = [math.dist(a, b) for a, b in zip(route, route[1:])]
    tot = sum(seglen)
    d = u * tot
    car = route[-1]
    for (a, b), L_ in zip(zip(route, route[1:]), seglen):
        if d <= L_:
            car = (a[0] + (b[0] - a[0]) * d / L_, a[1] + (b[1] - a[1]) * d / L_)
            break
        d -= L_
    ctx.set_source_rgb(0.20, 0.50, 0.95)                               # the route still ahead
    ctx.set_line_width(9 * S)
    ctx.move_to(*car)
    passed = False
    d = u * tot
    for (a, b), L_ in zip(zip(route, route[1:]), seglen):
        if passed or d <= L_:
            ctx.line_to(*b)
            passed = True
        d -= L_
    ctx.stroke()
    pin = route[-1]                                                    # the destination pin
    _disc(ctx, pin[0], pin[1] - 26 * S, 16 * S, (0.90, 0.22, 0.20), S, ink=None)
    _poly(ctx, [(pin[0] - 12 * S, pin[1] - 20 * S), (pin[0] + 12 * S, pin[1] - 20 * S), pin], (0.90, 0.22, 0.20), S, ink=None)
    _disc(ctx, pin[0], pin[1] - 26 * S, 6 * S, (1, 1, 1), S, ink=None)
    _disc(ctx, car[0], car[1], 15 * S, (1, 1, 1), S, ink=None)          # the car: a blue arrow in a white ring
    _disc(ctx, car[0], car[1], 11 * S, (0.20, 0.50, 0.95), S, ink=None)
    if u < 1.0:
        _rrect(ctx, px, py, pw, 80 * S, 0, (0.10, 0.45, 0.30), S, ink=None)
        _text(ctx, f"{int((1 - u) * 180)} m  ·  {to}", px + 28 * S, py + 54 * S, 36 * S, (1, 1, 1))
    else:
        _rrect(ctx, px, py + ph - 130 * S, pw, 130 * S, 0, (1, 1, 1), S, ink=None)
        _disc(ctx, px + 66 * S, py + ph - 65 * S, 34 * S, (0.20, 0.70, 0.40), S, ink=None)
        ctx.move_to(px + 50 * S, py + ph - 65 * S)
        ctx.line_to(px + 62 * S, py + ph - 52 * S)
        ctx.line_to(px + 82 * S, py + ph - 80 * S)
        ctx.set_source_rgb(1, 1, 1)
        ctx.set_line_width(7 * S)
        ctx.stroke()
        _text(ctx, "You have arrived", px + 120 * S, py + ph - 72 * S, 44 * S, (0.10, 0.12, 0.14))
        _text(ctx, to, px + 120 * S, py + ph - 26 * S, 30 * S, (0.40, 0.44, 0.48))
    ctx.restore()


def _wrap(txt, size, width):
    words, lines, cur = txt.split(), [], ""
    for w_ in words:
        nxt = (cur + " " + w_).strip()
        if cur and _width(nxt, size) > width:
            lines.append(cur)
            cur = w_
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines or [""]


def caption(ctx, W, H, text):
    """a line of the story over a screen: white words on a dark band at the bottom (the screen stays readable)"""
    S = H / 1080.0
    ctx.identity_matrix()
    lines = _wrap(str(text), 40 * S, W - 260 * S)
    bh = (36 + 52 * len(lines)) * S
    ctx.rectangle(0, H - bh, W, bh)
    ctx.set_source_rgba(0, 0, 0, 0.72)
    ctx.fill()
    for k, ln in enumerate(lines):
        _text(ctx, ln, (W - _width(ln, 40 * S)) / 2, H - bh + (62 + 52 * k) * S - 14 * S, 40 * S, (1, 1, 1))


def sheet(ctx, W, H, S, spec, t, frame):
    """over Deepak's shoulder at the station: the laptop on its case in the rain, Mark's file open
    (uv_all_sensors.csv - the rows come in, the impossible ones flash red) and the chat beside it, Deepak typing
    his answer. spec: "file", "cols", "rows" [[time, uv, o3], ...], "bad" (UV above this is red), "chat"
    [[who, text], ...], "me", "reply" (typed from "type_at" s)"""
    rng = random.Random(9)
    ctx.set_source_rgb(0.10, 0.14, 0.11)                               # the corn behind, out of focus
    ctx.paint()
    for k in range(40):
        ctx.arc(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(30, 120) * S, 0, 2 * math.pi)
        ctx.set_source_rgba(0.18 + rng.uniform(0, 0.1), 0.30 + rng.uniform(0, 0.12), 0.16, 0.35)
        ctx.fill()
    ctx.save()                                                         # the laptop, a little turned to us
    ctx.translate(W * 0.58, H * 0.50)
    ctx.transform(cairo.Matrix(1.0, -0.035, 0.05, 1.0, 0, 0))
    sw, sh = W * 0.60, H * 0.66
    _rrect(ctx, -sw / 2 - 18 * S, -sh / 2 - 18 * S, sw + 36 * S, sh + 36 * S, 16 * S, (0.13, 0.13, 0.15), S)
    outer = ctx                                                        # the screen is drawn flat, then tilted
    scr = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(sw), int(sh))    # (text is laid in pixels)
    ctx = cairo.Context(scr)
    ctx.rectangle(0, 0, sw, sh)
    ctx.set_source_rgb(0.86, 0.88, 0.90)
    ctx.fill()
    x0, y0 = 16 * S, 16 * S                       # the sheet's window
    ww, wh = sw * 0.62, sh - 32 * S
    ctx.rectangle(x0, y0, ww, wh)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()
    ctx.rectangle(x0, y0, ww, 44 * S)
    ctx.set_source_rgb(0.90, 0.92, 0.95)
    ctx.fill()
    _text(ctx, str(spec.get("file", "uv_all_sensors.csv")), x0 + 16 * S, y0 + 31 * S, 26 * S, (0.1, 0.1, 0.12))
    cols = spec.get("cols") or ["Time (IST)", "UV index", "O3 (ppb)"]
    cw = [ww * 0.5, ww * 0.25, ww * 0.25]
    rows = spec.get("rows") or [["2026-10-13 12:00", 2.1, 18], ["2026-10-13 12:10", 20.4, 220],
                                ["2026-10-13 12:20", 19.8, 210], ["2026-10-13 12:30", 3.2, 25],
                                ["2026-10-13 12:40", 1.9, 20]]
    bad = float(spec.get("bad", 10))
    rh = 46 * S
    yy = y0 + 54 * S
    cx_ = x0
    for j, c in enumerate(cols):
        _text(ctx, str(c), cx_ + 14 * S, yy + 30 * S, 22 * S, (0.1, 0.1, 0.12))
        cx_ += cw[j]
    per = float(spec.get("every", 0.3))
    for i, r_ in enumerate(rows):
        if t < 0.3 + i * per:
            break
        yy += rh
        hot = float(r_[1]) > bad
        cx_ = x0
        for j in range(3):
            if j and hot:
                on = (frame // 8) % 2 == 0 or t > 0.3 + len(rows) * per + 1.5
                ctx.rectangle(cx_ + 2, yy + 3, cw[j] - 4, rh - 6)
                ctx.set_source_rgb(*((0.98, 0.78, 0.78) if on else (1.0, 0.90, 0.90)))
                ctx.fill()
            ctx.rectangle(cx_, yy, cw[j], rh)
            ctx.set_source_rgb(0.80, 0.82, 0.86)
            ctx.set_line_width(1.2 * S)
            ctx.stroke()
            val = str(r_[j])
            _text(ctx, val, cx_ + 14 * S, yy + 31 * S, 24 * S, (0.85, 0.12, 0.12) if j and hot else (0.12, 0.12, 0.14))
            cx_ += cw[j]
    px, py, pw, ph = x0 + ww + 16 * S, y0, sw - (x0 + ww + 16 * S) - 16 * S, wh   # the chat
    ctx.rectangle(px, py, pw, ph)
    ctx.set_source_rgb(0.96, 0.97, 0.96)
    ctx.fill()
    by = py + 20 * S
    me = spec.get("me", "Deepak")
    for i, (who, txt) in enumerate(spec.get("chat") or [["Mark", "Check your stations tonight."]]):
        if t < 0.5 + i * 0.6:
            break
        lines = _wrap(str(txt), 24 * S, pw - 50 * S)
        bh = (34 + 30 * len(lines)) * S
        ctx.rectangle(px + 12 * S, by, pw - 24 * S, bh)
        ctx.set_source_rgb(1, 1, 1)
        ctx.fill()
        _text(ctx, str(who), px + 24 * S, by + 24 * S, 18 * S, (0.13, 0.45, 0.38))
        for k, ln in enumerate(lines):
            _text(ctx, ln, px + 24 * S, by + (52 + 30 * k) * S, 24 * S, (0.1, 0.1, 0.1))
        by += bh + 12 * S
    rep = str(spec.get("reply", ""))
    ta = float(spec.get("type_at", 2.0))
    if rep and t > ta:
        n = min(len(rep), int((t - ta) * 20))
        typed = rep[:n] + ("|" if (frame // 10) % 2 == 0 else "")
        lines = _wrap(typed, 24 * S, pw - 50 * S)
        bh = (34 + 30 * len(lines)) * S
        ctx.rectangle(px + 12 * S, by, pw - 24 * S, bh)
        ctx.set_source_rgb(0.84, 0.96, 0.78)
        ctx.fill()
        _text(ctx, str(me), px + 24 * S, by + 24 * S, 18 * S, (0.13, 0.45, 0.38))
        for k, ln in enumerate(lines):
            _text(ctx, ln, px + 24 * S, by + (52 + 30 * k) * S, 24 * S, (0.1, 0.1, 0.1))
    g = cairo.LinearGradient(0, 0, sw, sh)         # rain on the screen's glass
    g.add_color_stop_rgba(0, 1, 1, 1, 0.10)
    g.add_color_stop_rgba(0.5, 1, 1, 1, 0.0)
    ctx.set_source(g)
    ctx.rectangle(0, 0, sw, sh)
    ctx.fill()
    for k in range(26):
        dx, dy = rng.uniform(0, sw), rng.uniform(0, sh)
        ctx.arc(dx, dy + (t * 30 * S * (k % 3)) % (40 * S), rng.uniform(3, 7) * S, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.25)
        ctx.fill()
    ctx = outer
    ctx.set_source_surface(scr, -sw / 2, -sh / 2)
    ctx.paint()
    ctx.restore()
    hx, hy, r = W * 0.12, H * 0.60, H * 0.24                           # Deepak's head and cap, near the lens
    ctx.move_to(-20 * S, H)                                            # his shoulder (the teal shirt)
    ctx.curve_to(W * 0.05, H * 0.80, W * 0.22, H * 0.78, W * 0.30, H)
    ctx.close_path()
    ctx.set_source_rgb(0.25, 0.50, 0.57)
    ctx.fill()
    ctx.arc(hx, hy, r, 0, 2 * math.pi)
    ctx.set_source_rgb(0.62, 0.45, 0.32)
    ctx.fill()
    ctx.arc(hx, hy - r * 0.08, r * 1.04, math.pi * 0.95, math.pi * 2.05)
    ctx.close_path()
    ctx.set_source_rgb(0.12, 0.13, 0.15)
    ctx.fill()
    ctx.move_to(hx + r * 0.6, hy - r * 0.18)                           # the peak, pointing at the screen
    ctx.curve_to(hx + r * 1.2, hy - r * 0.25, hx + r * 1.55, hy - r * 0.05, hx + r * 1.6, hy + r * 0.02)
    ctx.line_to(hx + r * 0.7, hy + r * 0.02)
    ctx.close_path()
    ctx.fill()
    ctx.arc(hx + r * 0.05, hy + r * 0.25, r * 0.16, 0, 2 * math.pi)    # his ear
    ctx.set_source_rgb(0.55, 0.39, 0.27)
    ctx.fill()
    ctx.set_line_width(1.5 * S)                                        # the rain between us and the screen
    for k in range(120):
        x = (rng.uniform(0, W * 1.2) + t * 200 * S) % (W * 1.2) - W * 0.1
        y = (rng.uniform(0, H) + t * 1400 * S) % H
        ctx.move_to(x, y)
        ctx.line_to(x - 8 * S, y + 36 * S)
    ctx.set_source_rgba(0.85, 0.90, 0.95, 0.35)
    ctx.stroke()



KINDS = {"world_map": world_map, "call": call, "doc": doc, "document": doc, "plan": plan, "land": land, "mp_map": mp_map, "map": mp_map, "data": data, "graphs": data, "forum": forum, "reddit": forum, "chat": chat, "mine": mine, "underground": mine, "cutaway": mine, "news": news, "tv": news, "station_log": station_log, "log": station_log, "station_box": station_box, "box_inside": station_box, "open_box": station_box, "car_nav": car_nav, "gps": car_nav, "navigation": car_nav, "sheet": sheet, "csv": sheet, "laptop": sheet}


def draw(ctx, W, H, spec, t, frame):
    """one full-frame screen; returns False for an unknown kind"""
    if isinstance(spec, str):
        spec = {"kind": spec}
    fn = KINDS.get(str(spec.get("kind", "")).lower())
    if fn is None:
        return False
    ctx.identity_matrix()
    fn(ctx, W, H, H / 1080.0, spec, t, frame)
    return True



def radar(ctx, W, H, S, spec, t, frame):
    """a hurricane on a forecast screen: "style": "radar" - rain-rate colours (blue, green, yellow, red) wound in a
    spiral over the dark map, or "sat" - the satellite view (white cloud on the dark sea); a lat/long grid, the
    coast, the storm's track, a label. The spiral turns slowly anticlockwise (northern hemisphere)."""
    style = str(spec.get("style", "radar"))
    rng = random.Random(int(spec.get("seed", 3)))
    ctx.set_source_rgb(0.03, 0.07, 0.16) if style == "radar" else ctx.set_source_rgb(0.05, 0.12, 0.25)
    ctx.paint()
    land = [(0.0, 0.18), (0.35, 0.22), (0.52, 0.30), (0.60, 0.42), (0.78, 0.40), (0.92, 0.28), (1.0, 0.26), (1.0, 0.0),
            (0.0, 0.0)]                                                # a coast along the top (the Gulf from above)
    ctx.move_to(land[0][0] * W, land[0][1] * H)
    for x, y in land[1:]:
        ctx.line_to(x * W, y * H)
    ctx.close_path()
    ctx.set_source_rgb(*((0.10, 0.20, 0.12) if style == "radar" else (0.30, 0.34, 0.22)))
    ctx.fill()
    ctx.set_source_rgba(0.5, 0.7, 1.0, 0.15)                           # the lat / long grid
    ctx.set_line_width(1 * S)
    for k in range(1, 8):
        ctx.move_to(W * k / 8, 0)
        ctx.line_to(W * k / 8, H)
        ctx.move_to(0, H * k / 6)
        ctx.line_to(W, H * k / 6)
    ctx.stroke()
    cx, cy = W * float(spec.get("x", 0.5)), H * float(spec.get("y", 0.58))
    R = min(W, H) * float(spec.get("size", 0.42))
    rot = -t * 0.25
    cols = [(0.10, 0.35, 0.95), (0.10, 0.75, 0.45), (0.95, 0.90, 0.20), (0.98, 0.55, 0.10), (0.90, 0.12, 0.12),
            (0.85, 0.20, 0.75)]
    halo = cairo.RadialGradient(cx, cy, R * 0.1, cx, cy, R * 1.05)        # the storm's whole cloud shield
    halo.add_color_stop_rgba(0, *((0.95, 0.55, 0.1) if style == "radar" else (0.9, 0.9, 0.92)), 0.55)
    halo.add_color_stop_rgba(0.5, *((0.1, 0.7, 0.4) if style == "radar" else (0.75, 0.78, 0.82)), 0.35)
    halo.add_color_stop_rgba(1, 0.1, 0.3, 0.9, 0.0)
    ctx.set_source(halo)
    ctx.arc(cx, cy, R * 1.05, 0, 2 * math.pi)
    ctx.fill()
    for arm in range(5):
        for i in range(220):
            u = i / 219.0
            ang = rot + arm * 2 * math.pi / 5 + u * 4.6
            rr = R * (0.08 + 0.92 * u ** 1.2)
            px, py = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr * 0.9
            inten = max(0.0, 1.0 - u) ** 0.8 * rng.uniform(0.6, 1.0)  # strongest near the eye wall
            pr = (10 + 40 * u) * S
            if style == "radar":
                c = cols[min(len(cols) - 1, int(inten * len(cols)))]
                ctx.set_source_rgba(*c, 0.75)
            else:
                g = 0.65 + 0.35 * inten
                ctx.set_source_rgba(g, g, g, 0.8)
            ctx.arc(px, py, pr, 0, 2 * math.pi)
            ctx.fill()
    ctx.arc(cx, cy, R * 0.05, 0, 2 * math.pi)                           # the eye
    ctx.set_source_rgb(*((0.03, 0.07, 0.16) if style == "radar" else (0.1, 0.2, 0.35)))
    ctx.fill()
    if spec.get("track", True):                                        # the forecast track to the coast
        ctx.set_source_rgba(1, 1, 1, 0.8)
        ctx.set_line_width(3 * S)
        ctx.set_dash([10 * S, 8 * S])
        ctx.move_to(cx, cy)
        ctx.curve_to(cx - W * 0.05, cy - H * 0.15, cx - W * 0.02, cy - H * 0.25, W * 0.48, H * 0.27)
        ctx.stroke()
        ctx.set_dash([])
    lab = str(spec.get("label", ""))
    if lab:
        ctx.rectangle(30 * S, H - 90 * S, _width(lab, 34 * S) + 40 * S, 60 * S)
        ctx.set_source_rgba(0, 0, 0, 0.6)
        ctx.fill()
        _text(ctx, lab, 50 * S, H - 48 * S, 34 * S, (1, 1, 1))


KINDS.update({"radar": radar, "satellite": radar, "sat": radar})
