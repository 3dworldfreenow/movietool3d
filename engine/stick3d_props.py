"""🧊 Stick 3D: the story's props as flat cartoon things - in a hand or standing on the ground.

The story engine already says who holds what and when (pick, give, put, carry, drop); here each prop is drawn in
the flat look: a simple shape in its colour with an ink outline, at its real size (world units: a person is about
330 tall, so a laptop is 38 wide). A prop we have no flat drawing for is drawn as the 2.5D ink drawing.
"""
import math

INK = (0.16, 0.14, 0.18)

# words in a prop's id / type -> its flat drawing (checked before the sketch engine's own list)
WORDS = (
    (("laptop", "computer", "notebook_pc"), "laptop"),
    (("phone", "mobile", "smartphone"), "phone"),
    (("tablet", "ipad"), "tablet"),
    (("station", "sensor", "weather_box", "device", "lora", "node"), "station"),
    (("antenna", "aerial"), "antenna"),
    (("toolbox", "tool_box", "tools", "kit"), "toolbox"),
    (("drum", "barrel", "jerrycan", "can"), "drum"),
    (("bucket", "balti"), "bucket"),
    (("map", "naksha", "plan", "blueprint", "drawing"), "map"),
    (("file", "paper", "letter", "document", "report", "kagaz", "chitthi"), "paper"),
    (("book", "kitab", "diary", "notebook"), "book"),
    (("spade", "shovel", "kudal", "phawda", "hoe"), "spade"),
    (("bottle", "botal"), "bottle"),
    (("cable", "wire", "rope", "coil"), "coil"),
    (("box", "carton", "crate", "parcel", "dabba", "chest", "trunk"), "box"),
    (("bag", "sack", "jhola", "backpack"), "bag"),
    (("pot", "matka", "ghada", "kalash"), "pot"),
    (("stick", "lathi", "rod", "pole", "danda"), "stick"),
    (("cup", "glass", "chai", "tea"), "cup"),
    (("mic", "microphone"), "mic"),
    (("rifle", "carbine", "ak47", "insas"), "rifle"),
    (("gun", "pistol", "revolver", "bandook", "weapon", "glock"), "gun"),
)
BOOST = {"gun": 2.6, "cup": 2.2, "mic": 2.4, "phone": 1.7, "bottle": 1.6, "tablet": 1.3}  # small things drawn bigger (a cartoon: real size
#                                                                    would be a speck in a doodle hand)
BIG = {"box", "drum", "station", "toolbox", "bag", "pot", "bucket"}     # carried in front of the body


def kind_of(pr):
    s = (str(getattr(pr, "id", "")) + " " + str(getattr(pr, "type", "")) + " " +
         str((getattr(pr, "spec", None) or {}).get("look", ""))).lower()
    for words, kind in WORDS:
        if any(w in s for w in words):
            return kind
    return None


def _col(pr, default):
    c = (getattr(pr, "spec", None) or {}).get("color")
    if isinstance(c, str) and c.startswith("#") and len(c) == 7:
        return tuple(int(c[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    if isinstance(c, (list, tuple)) and len(c) == 3:
        return tuple(float(v) for v in c)
    return default


def _shape(ctx, pts, col, lw):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.set_source_rgb(*col)
    ctx.fill_preserve()
    ctx.set_source_rgb(*INK)
    ctx.set_line_width(lw)
    ctx.set_line_join(1)
    ctx.stroke()


def _rect(ctx, x, y, w, h, col, lw):
    _shape(ctx, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], col, lw)


def _line(ctx, pts, col, wd):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.set_source_rgb(*col)
    ctx.set_line_width(wd)
    ctx.set_line_cap(1)
    ctx.stroke()


def draw(ctx, pr, kind, sx, sy, k, f, held, t):
    """draw one prop: (sx, sy) = the hand (held) or the spot on the ground, k = screen px per world unit,
    f = +1 / -1 the way the holder faces on screen. Returns False if there is no flat drawing for it."""
    if kind is None:
        return False
    sc = float(getattr(pr, "scale", 1.0) or 1.0) * BOOST.get(kind, 1.0)
    ctx.save()
    ctx.translate(sx, sy)
    ctx.scale(k * sc * f, -k * sc)                                     # world units, y up, facing +x
    lw = 1.6 / max(0.05, k * sc)
    if held and kind in BIG:                                           # big things are held against the body
        ctx.translate(-6, -4)
    if kind == "laptop":
        if held:                                                       # carried shut under the arm
            _rect(ctx, -20, -2, 38, 4, _col(pr, (0.62, 0.64, 0.68)), lw)
        else:
            _rect(ctx, -20, 0, 40, 3, _col(pr, (0.62, 0.64, 0.68)), lw)
            _shape(ctx, [(-20, 3), (-24, 30), (14, 30), (18, 3)], (0.25, 0.27, 0.30), lw)
            _shape(ctx, [(-19, 6), (-22, 27), (12, 27), (15, 6)], (0.35, 0.65, 0.92), lw * 0.6)
    elif kind in ("phone", "tablet"):
        w, h = (8, 15) if kind == "phone" else (18, 25)
        dy = 8 if held else 0
        _rect(ctx, -w / 2, dy, w, h, (0.15, 0.15, 0.17), lw)
        glow = 0.75 + 0.25 * math.sin(t * 3)
        _rect(ctx, -w / 2 + 1.2, dy + 1.5, w - 2.4, h - 4, (0.35 * glow, 0.70 * glow, 0.95), lw * 0.3)
    elif kind == "station":                                            # Deepak's weather station box
        _rect(ctx, -12, -14 if held else 0, 24, 28, (0.98, 0.98, 0.96), lw)
        y0 = -14 if held else 0
        for j in range(4):
            _line(ctx, [(-9, y0 + 5 + 5 * j), (9, y0 + 5 + 5 * j)], (0.55, 0.57, 0.60), 1.2 * lw)
        _shape(ctx, [(-13, y0 + 28), (13, y0 + 28), (10, y0 + 36), (-10, y0 + 36)], (0.20, 0.30, 0.52), lw)
        _line(ctx, [(8, y0 + 36), (8, y0 + 62)], INK, 1.3 * lw)
    elif kind == "antenna":
        _line(ctx, [(0, -10), (0, 70)], (0.2, 0.2, 0.22), 2.2 * lw)
        _rect(ctx, -4, -14, 8, 6, (0.3, 0.3, 0.32), lw)
    elif kind == "toolbox":
        y0 = -10 if held else 0
        _rect(ctx, -18, y0, 36, 16, _col(pr, (0.85, 0.22, 0.20)), lw)
        _line(ctx, [(-8, y0 + 16), (-8, y0 + 22), (8, y0 + 22), (8, y0 + 16)], INK, 1.6 * lw)
    elif kind == "box":
        y0 = -14 if held else 0
        _rect(ctx, -16, y0, 32, 26, _col(pr, (0.82, 0.64, 0.42)), lw)
        _line(ctx, [(-16, y0 + 13), (16, y0 + 13)], (0.62, 0.46, 0.28), 2 * lw)
    elif kind in ("drum", "bucket"):
        w, h = (24, 34) if kind == "drum" else (20, 20)
        y0 = -h / 2 if held else 0
        col = _col(pr, (0.25, 0.48, 0.75) if kind == "drum" else (0.65, 0.66, 0.70))
        _shape(ctx, [(-w / 2, y0), (w / 2, y0), (w / 2 + 1.5, y0 + h), (-w / 2 - 1.5, y0 + h)], col, lw)
        for j in (0.3, 0.7):
            _line(ctx, [(-w / 2, y0 + h * j), (w / 2, y0 + h * j)], tuple(c * 0.7 for c in col), 1.3 * lw)
    elif kind in ("map", "paper"):
        dy = 4 if held else 0
        _rect(ctx, -11, dy, 22, 28, (0.98, 0.97, 0.92), lw)
        if kind == "map":
            _shape(ctx, [(-7, dy + 6), (2, dy + 4), (8, dy + 12), (4, dy + 23), (-6, dy + 20)], (0.55, 0.80, 0.62), lw * 0.6)
        else:
            for j in range(5):
                _line(ctx, [(-7, dy + 6 + 4 * j), (7, dy + 6 + 4 * j)], (0.6, 0.6, 0.62), 0.9 * lw)
    elif kind == "book":
        _rect(ctx, -10, 2 if held else 0, 20, 26, _col(pr, (0.25, 0.45, 0.70)), lw)
    elif kind == "spade":
        _line(ctx, [(0, -40 if held else 0), (0, 100)], (0.55, 0.40, 0.25), 3 * lw)
        y0 = -40 if held else 0
        _shape(ctx, [(-9, y0), (9, y0), (8, y0 - 22), (0, y0 - 28), (-8, y0 - 22)], (0.62, 0.64, 0.68), lw)
    elif kind == "bottle":
        _shape(ctx, [(-5, 0), (5, 0), (5, 16), (2, 20), (2, 26), (-2, 26), (-2, 20), (-5, 16)],
               _col(pr, (0.45, 0.70, 0.90)), lw)
    elif kind == "coil":
        ctx.arc(0, 8, 9, 0, 2 * math.pi)
        ctx.set_source_rgb(*INK)
        ctx.set_line_width(4 * lw)
        ctx.stroke()
        ctx.arc(0, 8, 9, 0, 2 * math.pi)
        ctx.set_source_rgb(*_col(pr, (0.85, 0.30, 0.20)))
        ctx.set_line_width(2.4 * lw)
        ctx.stroke()
    elif kind == "bag":
        y0 = -12 if held else 0
        _shape(ctx, [(-14, y0), (14, y0), (16, y0 + 22), (8, y0 + 28), (-8, y0 + 28), (-16, y0 + 22)],
               _col(pr, (0.40, 0.45, 0.35)), lw)
    elif kind == "pot":
        y0 = -14 if held else 0
        ctx.arc(0, y0 + 14, 14, 0, 2 * math.pi)
        ctx.set_source_rgb(*_col(pr, (0.72, 0.42, 0.26)))
        ctx.fill_preserve()
        ctx.set_source_rgb(*INK)
        ctx.set_line_width(lw)
        ctx.stroke()
    elif kind == "stick":
        _line(ctx, [(0, -30 if held else 0), (0, 110)], (0.55, 0.40, 0.25), 3 * lw)
    elif kind == "cup":
        _shape(ctx, [(-5, 0), (5, 0), (6, 10), (-6, 10)], _col(pr, (0.95, 0.95, 0.92)), lw)
    elif kind == "mic":                                                # a reporter's mic: handle, the channel's
        _line(ctx, [(0, -6 if held else 0), (0, 14)], (0.12, 0.12, 0.14), 3.2 * lw)   # cube, the foam head
        _rect(ctx, -3.6, 6, 7.2, 5, _col(pr, (0.80, 0.16, 0.18)), lw * 0.8)
        ctx.arc(0, 17, 4.2, 0, 2 * math.pi)
        ctx.set_source_rgb(0.20, 0.20, 0.22)
        ctx.fill_preserve()
        ctx.set_source_rgb(*INK)
        ctx.set_line_width(lw)
        ctx.stroke()
    elif kind == "gun":                                                # a pistol, barrel forward (held low): gunmetal
        dy = -2 if held else 0                                         # with a light shine on the slide, so it reads
        _shape(ctx, [(-3, dy + 2), (15, dy + 2), (15, dy + 7), (-4, dy + 7)], _col(pr, (0.30, 0.31, 0.34)), lw)   # against
        _shape(ctx, [(-3, dy + 2), (2, dy + 2), (0, dy - 8), (-5, dy - 8)], (0.22, 0.22, 0.24), lw)   # a black suit
        _line(ctx, [(-2, dy + 6), (14, dy + 6)], (0.78, 0.80, 0.84), 1.4 * lw)
        _line(ctx, [(2, dy + 2), (4, dy - 1), (6, dy + 2)], (0.55, 0.56, 0.60), 0.9 * lw)          # trigger guard
    elif kind == "rifle":                                              # a carbine slung across the body
        dy = -6 if held else 0
        _shape(ctx, [(-22, dy), (-6, dy + 4), (26, dy + 4), (26, dy + 8), (-8, dy + 8), (-24, dy + 5)],
               _col(pr, (0.30, 0.31, 0.34)), lw)
        _line(ctx, [(-6, dy + 7), (25, dy + 7)], (0.78, 0.80, 0.84), 1.4 * lw)
        _shape(ctx, [(4, dy + 4), (9, dy + 4), (7, dy - 6), (3, dy - 6)], (0.16, 0.16, 0.18), lw)    # the magazine
        _line(ctx, [(26, dy + 6), (36, dy + 6)], (0.10, 0.10, 0.12), 1.8 * lw)                     # the barrel
    ctx.restore()
    return True
