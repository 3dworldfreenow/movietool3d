"""🏘 Ghatti Nagar's village in soft clay, like its people: the tiled mud house of the Satpura hills (khaprail), a round
thatched hut, a pucca house, a two-storey clinic / office, a little shop, the trees (banyan, mahua, mango, neem), a bush,
the well, a haystack and the hand pump. Same sizes as the older flat-shaded ones (assets/code/khaprail_house_3d.py ...)
so the world's layout still fits; the fronts face -z (toward the camera), doors are real doors people walk through
(assets/code/clay_village_3d.py: pen.doorway).

The recipes join engine/sculpt_things.py (same cache, same mesh), so  pen.sculpt("clay_khaprail_house")  works.
Real sizes (story units, 175 = 1 m): a door 2 m tall, walls 2.6 m, a banyan 5 m high with a 9 m crown.
"""
import numpy as np

MUD, GERU, CHUNA, KHAPRAIL, THATCH = "#c9a57a", "#9b4a2e", "#f2ece0", "#b5532f", "#c8a45a"
BARK, LEAF, LEAF_DARK, LEAF_LIGHT = "#6e4b33", "#4f8a3a", "#3b6e2c", "#7aa84a"
DOOR = "#6b4424"


def _gable(S, c, half_w, half_d, rise, colour, thick=14.0, axis="x", **kw):
    """a gable roof (two sloping sides meeting at a ridge along axis) with eaves: c = middle of its foot"""
    c = np.asarray(c, float)

    def f(P):
        q = P - c
        a, b = (q[:, 0], q[:, 2]) if axis == "x" else (q[:, 2], q[:, 0])
        hb = half_d
        slope = rise / hb
        top = q[:, 1] - (rise - np.abs(b) * slope)          # above the roof slope: > 0
        under = (rise - np.abs(b) * slope) - thick - q[:, 1]  # below the underside: > 0
        return np.maximum(np.maximum(top, under) / np.sqrt(1 + slope * slope),
                          np.maximum(np.abs(a) - half_w, np.abs(b) - hb))
    ext = np.array([half_w, 0, half_d]) if axis == "x" else np.array([half_d, 0, half_w])
    kw.setdefault("box", (c - ext - np.array([0, thick, 0]), c + ext + np.array([0, rise, 0])))
    return S._add(f, colour, **kw)


def _tiles(S, c, half_d, rise, colour, axis="x", step=26.0):
    """the rows of country tiles running down the roof (khaprail: half-round clay tiles)"""
    c = np.asarray(c, float)
    S.paint(lambda P: np.abs(((P[:, 0 if axis == "x" else 2] - c[0 if axis == "x" else 2]) % step) - step / 2) - 3.5
            + np.maximum(0, c[1] + 4 - P[:, 1]) * 9, colour, soft=2.0)


def _canopy(S, c, r, n, colour, seed, squash=0.75, k=40.0):
    """a tree crown: clumps of leaves melted together (more round blobs on the outside, light on top)"""
    rng = np.random.default_rng(seed)
    c = np.asarray(c, float)
    S.ellipsoid(c, (r * 0.78, r * 0.62 * squash / 0.75, r * 0.78), colour, k=k, gloss=0.05)
    for _ in range(n):
        u = rng.normal(size=3)
        u[1] = abs(u[1]) * 0.6 + 0.1
        u /= np.linalg.norm(u)
        rr = r * rng.uniform(0.32, 0.48)
        p = c + u * np.array([r * 0.72, r * 0.5 * squash / 0.75, r * 0.72])
        S.ellipsoid(p, (rr, rr * 0.8, rr), colour, k=k, gloss=0.05)
    top = c[1] + r * 0.2
    near = lambda P: np.maximum(0.0, np.linalg.norm((P - c) / np.array([1.0, 0.8, 1.0]), axis=1) - r * 0.75) * 0.6  # noqa: E731
    S.paint(lambda P: top - P[:, 1] + 4.0 * np.sin(P[:, 0] * 0.05) * np.cos(P[:, 2] * 0.05) + near(P), LEAF_LIGHT,
            soft=30.0)
    S.paint(lambda P: np.maximum(np.maximum(P[:, 1] - (c[1] - r * 0.25), c[1] - r * 0.9 - P[:, 1]), near(P) - 30.0),
            LEAF_DARK, soft=30.0)


def _crown(S, c, rx, ry, rz, n, cols, seed, k=40.0, clump=(0.32, 0.48), core=True, flat=1.0, branches=None):
    """a tree's crown with its own character: its size (rx, ry, rz), how many clumps of leaves, their greens, how
    much they melt together (k: small = airy, separate clumps), a solid core or not, flat clumps (big leaves);
    branches = a point the clumps' twigs grow from (airy trees show them)"""
    rng = np.random.default_rng(seed)
    c = np.asarray(c, float)
    if core:
        S.ellipsoid(c, (rx * 0.8, ry * 0.68, rz * 0.8), cols[0], k=k, gloss=0.05)
    for i in range(n):
        u = rng.normal(size=3)
        u[1] = abs(u[1]) * 0.7 + (0.05 if core else -0.2)
        u /= np.linalg.norm(u)
        m = min(rx, rz)
        rr = m * rng.uniform(*clump)
        p = c + u * np.array([rx * 0.78, ry * 0.62, rz * 0.78])
        S.ellipsoid(p, (rr * (1.25 if flat < 1 else 1.0), rr * 0.82 * flat, rr * (1.25 if flat < 1 else 1.0)),
                    cols[i % len(cols)], k=k, gloss=0.06)
        if branches is not None:
            S.capsule(branches, p, max(6.0, m * 0.025), max(4.0, m * 0.016), "#5a4030", k=6)
    top = c[1] + ry * 0.35
    near = lambda P: np.maximum(0.0, np.linalg.norm((P - c) / np.array([rx, ry, rz]), axis=1) - 0.78) * 300.0  # noqa
    base = np.array([int(cols[0][i:i + 2], 16) for i in (1, 3, 5)], float)
    lit = base + (np.array([196.0, 214.0, 120.0]) - base) * 0.38         # its own green, warmer where the sun is
    S.paint(lambda P: top - P[:, 1] + 6.0 * np.sin(P[:, 0] * 0.04) * np.cos(P[:, 2] * 0.04) + near(P),
            "#%02x%02x%02x" % tuple(int(v) for v in lit), soft=ry * 0.12)   # sunlit top
    S.paint(lambda P: np.maximum(P[:, 1] - (c[1] - ry * 0.3), near(P) - 30.0), "#2a4a22", soft=ry * 0.12)


def _trunk(S, base, top, r0, r1, colour=BARK, k=20.0):
    S.capsule(base, top, r0, r1, colour, k=k, gloss=0.1)


def _door(S, cx, y0, zf, w, h, leaf=DOOR, frame="#5a3a22", depth=30, arch=False, double=True):
    """a real doorway in a front wall (front face at z = zf, facing -z): a raised wooden frame, the opening cut into
    the clay, and the door leaves set back inside it (arch = a rounded top)"""
    S.color_abs = True
    top = y0 + h
    S.rbox((cx, y0 + h / 2 + 6, zf - 5), (w / 2 + 14, h / 2 + 10, 9), frame, r=3, k=2, gloss=0.2)
    hb = h - (w / 2 if arch else 0)
    S.rbox((cx, y0 + hb / 2, zf + depth / 2 - 14), (w / 2, hb / 2, depth / 2 + 14), "#000000", mode="sub", r=2, k=1.5)
    if arch:
        S.ellipsoid((cx, top - w / 2, zf + depth / 2 - 14), (w / 2, w / 2, depth / 2 + 14), "#000000", mode="sub", k=1.5)
    S.rbox((cx, y0 + h / 2 - 2, zf + depth - 9), (w / 2 + 2, h / 2 + 2, 6), leaf, r=2, k=1.5, gloss=0.25)
    if double:                                           # two leaves: the line between them, and their iron rings
        S.paint(lambda P: np.maximum(np.abs(P[:, 0] - cx) - 1.6, np.abs(P[:, 2] - (zf + depth - 15)) - 4),
                "#2e1c10", soft=0.8)
        for sx in (-1, 1):
            S.torus((cx + sx * 11, y0 + h * 0.5, zf + depth - 17), 5, 1.6, "#3a3a3a", axis=(0, 0, 1), k=0.5, gloss=0.6)


def _window(S, cx, cy, zf, w, h, frame="#5a3a22", inside="#2a2018", bars=3, depth=22):
    """a real window: a wooden frame standing out, a sill, the opening cut in, dark inside, iron bars across"""
    S.color_abs = True
    S.rbox((cx, cy, zf - 4), (w / 2 + 11, h / 2 + 11, 8), frame, r=3, k=2, gloss=0.2)
    S.rbox((cx, cy - h / 2 - 12, zf - 10), (w / 2 + 18, 6, 14), frame, r=2, k=1.5, gloss=0.2)      # the sill
    S.rbox((cx, cy, zf + depth / 2 - 12), (w / 2, h / 2, depth / 2 + 12), "#000000", mode="sub", r=2, k=1.5)
    S.rbox((cx, cy, zf + depth - 4), (w / 2 + 2, h / 2 + 2, 4), inside, r=1, k=1, gloss=0.0)
    for i in range(bars):
        x = cx - w / 2 + w * (i + 1) / (bars + 1)
        S.capsule((x, cy - h / 2, zf + 4), (x, cy + h / 2, zf + 4), 4.5, 4.5, "#3a3a3a", k=1, gloss=0.5)


# ---------------------------------------------------------------------------- houses
def clay_khaprail_house(S):
    """the Satpura mud house: an earthen plinth, thick mud walls with a geru band and white chuna patterns, a red
    khaprail (country tile) gable roof, a front verandah on wooden posts"""
    S.fine = 22.0
    S.rbox((0, 30, 0), (470, 30, 330), "#b88d5e", r=10, k=8)                       # the chabutra (plinth)
    S.rbox((0, 60 + 228, 60), (400, 228, 250), MUD, r=14, k=10, gloss=0.05)       # the walls (2.6 m)
    S.paint(lambda P: P[:, 1] - 150, GERU, soft=4)                                # the geru band below
    S.paint(lambda P: np.hypot(((P[:, 0] + 600) % 60) - 30, P[:, 1] - 165) - 7, CHUNA, soft=2)   # white chuna dots
    _gable(S, (0, 516, 60), 450, 320, 170, KHAPRAIL, thick=44, k=6, gloss=0.2)
    _tiles(S, (0, 516, 60), 320, 170, "#8e3c22")
    S.rbox((0, 300, -250), (430, 8, 90), KHAPRAIL, r=4, k=4)                      # the verandah roof
    for x in (-380, -130, 130, 380):
        S.capsule((x, 60, -320), (x, 300, -320), 11, 10, "#7a5230", k=4, gloss=0.2)
    _door(S, -60, 60, -190, 136, 360)
    for wx in (210, -280):
        _window(S, wx, 290, -190, 110, 90)


def clay_hut(S):
    """a round mud hut with a conical thatched roof"""
    S.fine = 18.0
    S.lathe((0, 0, 0), [(0, 0), (215, 0), (208, 40), (200, 300), (0, 300)], MUD, k=8, gloss=0.05)
    S.paint(lambda P: P[:, 1] - 70, GERU, soft=4)
    S.lathe((0, 270, 0), [(0, 0), (260, 0), (250, 20), (40, 225), (0, 241)], THATCH, k=10, gloss=0.05)
    S.paint(lambda P: np.abs(((np.arctan2(P[:, 2], P[:, 0]) * 40) % 2) - 1) - 0.35 + np.maximum(0, 275 - P[:, 1]) * 9,
            "#a8873f", soft=0.3)
    _door(S, 0, 0, -203, 120, 290, depth=34, double=False)


def clay_pucca_house(S):
    """a small pucca (brick and cement) house: lime-washed walls, a flat roof with a parapet, steps to the door"""
    S.fine = 20.0
    S.rbox((0, 205, 30), (250, 205, 200), "#e8d9a8", r=12, k=8, gloss=0.08)
    S.rbox((0, 420, 30), (262, 14, 212), "#d8c895", r=6, k=5)                    # roof slab
    S.rbox((0, 449, 30), (262, 15, 212), "#e8d9a8", r=6, k=4)                    # parapet
    S.rbox((0, 449, 30), (240, 30, 190), "#e8d9a8", mode="sub", r=4, k=3)
    S.paint(lambda P: P[:, 1] - 60, "#9a8f7a", soft=3)                          # plinth band
    S.rbox((0, 15, -195), (90, 15, 40), "#b9b0a0", r=4, k=4)                     # steps
    _door(S, 0, 30, -170, 120, 330, leaf="#2f6db5")
    for wx in (-165, 165):
        _window(S, wx, 250, -170, 100, 100, frame="#3a5f7a")


def clay_building(S):
    """a two-storey building of the village (the clinic, the vakil's chamber, the panchayat): a balcony slab over the
    door, a sign board, windows on both floors"""
    S.fine = 20.0
    S.rbox((0, 310, 0), (225, 310, 165), "#e6cfa0", r=12, k=8, gloss=0.08)
    S.rbox((0, 630, 0), (235, 12, 175), "#cdb68a", r=5, k=4)
    S.rbox((0, 320, -195), (180, 10, 40), "#cdb68a", r=4, k=4)                   # balcony
    S.paint(lambda P: P[:, 1] - 70, "#a08a64", soft=3)
    S.paint(lambda P: np.abs(P[:, 1] - 318) - 6, "#a08a64", soft=3)             # the floor line
    S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) - 150, np.abs(P[:, 1] - 395) - 28), P[:, 2] + 150),
            "#1f5f8b", soft=2)                                                   # the sign board
    _door(S, 0, 10, -165, 120, 340, leaf="#5b3a22")
    for wx, wy in ((-150, 230), (150, 230), (-120, 500), (0, 500), (120, 500)):
        _window(S, wx, wy, -165, 80, 100, frame="#4a5f6b")


def clay_shop(S):
    """a village shop: a box with its front open, a sloping tin awning on poles, a counter"""
    S.fine = 16.0
    S.rbox((0, 140, 40), (175, 140, 130), "#d9b98a", r=10, k=6, gloss=0.08)
    S.rbox((0, 140, -60), (150, 115, 60), "#4a3426", mode="sub", r=6, k=4)       # the open front
    S.rbox((0, 45, -110), (160, 45, 22), "#8a5a32", r=5, k=4)                    # counter
    S.rbox((0, 300, -150), (190, 8, 75), "#7a8c96", r=3, k=3, gloss=0.5)         # tin awning
    for x in (-180, 180):
        S.capsule((x, 0, -215), (x, 296, -215), 7, 6, "#6b4424", k=3)
    S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) - 150, np.abs(P[:, 1] - 260) - 22), P[:, 2] + 60),
            "#c0392b", soft=2)                                                    # the shop's name board


# ---------------------------------------------------------------------------- trees and the rest
def clay_banyan(S):
    """the old banyan: a thick trunk of many melted stems, great spreading limbs, a huge low flat-topped crown wider
    than it is tall, and aerial roots hanging all round it (some reached the ground and became pillars)"""
    S.fine = 30.0
    for a in range(6):
        t = a * 1.05
        _trunk(S, (70 * np.cos(t), 0, 70 * np.sin(t)), (20 * np.cos(t), 430, 20 * np.sin(t)), 70, 48, k=34)
    for a in range(7):
        t = a * 0.9 + 0.2
        _trunk(S, (0, 400, 0), (620 * np.cos(t), 600, 520 * np.sin(t)), 40, 20, k=25)
    rng = np.random.default_rng(31)
    for a in range(16):                                   # aerial roots: thin ones hang, thick ones are pillars
        t = a * 0.39 + rng.uniform(-0.1, 0.1)
        rr = rng.uniform(300, 640)
        x, z = rr * np.cos(t), rr * 0.85 * np.sin(t)
        thick = a % 4 == 0
        S.capsule((x, 0 if thick else rng.uniform(120, 300), z), (x, 640, z), 28 if thick else 16, 16, "#7d5a3c", k=8)
    _crown(S, (0, 760, 0), 900, 300, 780, 26, ("#3f7a33", "#356b2b", "#4a8a3a"), seed=1, k=60)


def clay_mahua(S):
    """the mahua: a straight stout trunk, the crown starting high - a tall dense rounded dome"""
    S.fine = 24.0
    _trunk(S, (0, 0, 0), (0, 700, 0), 56, 38)
    for t in (0.4, 2.2, 4.1):
        _trunk(S, (0, 600, 0), (230 * np.cos(t), 900, 230 * np.sin(t)), 28, 14)
    _crown(S, (0, 1020, 0), 420, 470, 420, 16, ("#5a8f3c", "#6a9a40", "#7a9c45"), seed=2, k=45)


def clay_mango(S):
    """the mango tree: a short thick trunk splitting low into big limbs, a wide dense dark glossy dome down to
    head height"""
    S.fine = 24.0
    _trunk(S, (0, 0, 0), (0, 260, 0), 56, 44)
    for t in (0.0, 1.6, 3.2, 4.7):
        _trunk(S, (0, 240, 0), (260 * np.cos(t), 520, 260 * np.sin(t)), 30, 16)
    _crown(S, (0, 640, 0), 560, 400, 540, 24, ("#2f5f26", "#356b2b", "#2a5422", "#3a722f"), seed=3, k=34,
           clump=(0.24, 0.36))


def clay_neem(S):
    """the neem: a leaning trunk, branches you can see, an airy crown of separate light-green clumps with sky
    between them"""
    S.fine = 22.0
    _trunk(S, (0, 0, 0), (50, 560, 10), 40, 26)
    _crown(S, (60, 860, 0), 480, 330, 460, 15, ("#7fb24a", "#8cbc52", "#6fa543"), seed=4, k=12, clump=(0.2, 0.3),
           core=False, branches=(50, 560, 10))


def clay_bush(S):
    S.fine = 14.0
    rng = np.random.default_rng(5)
    for _ in range(7):
        p = (rng.uniform(-100, 100), rng.uniform(45, 85), rng.uniform(-50, 50))
        r = rng.uniform(55, 80)
        S.ellipsoid(p, (r, r * 0.8, r), LEAF, k=25, gloss=0.05)
    S.paint(lambda P: 90 - P[:, 1], LEAF_LIGHT, soft=20)


def clay_well(S):
    """the village well: a round wall of stone and lime, a wooden frame with a pulley across it"""
    S.fine = 10.0
    S.lathe((0, 0, 0), [(0, 0), (100, 0), (100, 70), (94, 76), (72, 76), (70, 66), (0, 66)], "#b8ab95", k=4)
    S.paint(lambda P: np.abs(((P[:, 1] + 6) % 24) - 12) - 1.5, "#8f8470", soft=1)
    for x in (-82, 82):
        S.capsule((x, 70, 0), (x, 230, 0), 7, 6, "#6b4424", k=3)
    S.capsule((-90, 225, 0), (90, 225, 0), 6, 6, "#6b4424", k=3)
    S.torus((0, 205, 0), 14, 4, "#5a5a5a", axis=(1, 0, 0), k=2, gloss=0.6)


def clay_haystack(S):
    """a haystack (paddy straw heaped round a pole)"""
    S.fine = 14.0
    S.lathe((0, 0, 0), [(0, 0), (150, 0), (160, 70), (140, 170), (80, 260), (0, 300)], "#d9b45a", k=10, gloss=0.03)
    S.paint(lambda P: np.abs(np.sin(P[:, 1] * 0.15 + np.arctan2(P[:, 2], P[:, 0]) * 3)) - 0.8, "#b8933f", soft=0.2)
    S.capsule((0, 280, 0), (0, 330, 0), 4, 3, "#6b4424", k=2)


def clay_handpump(S):
    """the India Mark II hand pump on its cement platform"""
    S.fine = 6.0
    S.cyl((0, 0, 0), 70, 14, "#b9b0a0", k=3)
    S.cyl((0, 14, 0), 13, 140, "#3f5f7a", k=2, gloss=0.6)
    S.rbox((0, 158, 0), (16, 10, 16), "#3f5f7a", r=4, k=2, gloss=0.6)
    S.capsule((0, 160, 0), (-110, 190, 0), 4, 4, "#3f5f7a", k=2, gloss=0.6)        # the handle
    S.capsule((12, 120, 0), (34, 112, 0), 5, 4, "#3f5f7a", k=2, gloss=0.6)          # the spout


def clay_sal(S):
    """the sal of the Satpura forests: a tall straight grey-brown trunk, a high narrow crown like a column"""
    S.fine = 26.0
    _trunk(S, (0, 0, 0), (0, 1250, 0), 46, 26, colour="#5e5048")
    for t in (0.5, 2.5, 4.4):
        _trunk(S, (0, 1000, 0), (150 * np.cos(t), 1350, 150 * np.sin(t)), 18, 10, colour="#5e5048")
    _crown(S, (0, 1520, 0), 270, 520, 270, 12, ("#3f7a33", "#4a8a3a"), seed=6, k=40)


def clay_teak(S):
    """the teak: a straight trunk, a broad uneven crown of big flat leaf clumps, yellow-green after the rains"""
    S.fine = 26.0
    _trunk(S, (0, 0, 0), (0, 950, 0), 40, 24, colour="#7a6450")
    for t in (0.2, 2.3, 4.3):
        _trunk(S, (0, 820, 0), (260 * np.cos(t), 1100, 260 * np.sin(t)), 18, 10, colour="#7a6450")
    _crown(S, (0, 1200, 0), 520, 300, 480, 13, ("#8aa64a", "#9ab052", "#7c9a40"), seed=7, k=30, flat=0.55)


def clay_bamboo(S):
    """a clump of bamboo: tall green canes leaning out, leafy tops"""
    S.fine = 22.0
    rng = np.random.default_rng(8)
    for i in range(9):
        a = i * 0.7
        top = (np.cos(a) * rng.uniform(150, 300), rng.uniform(1300, 1750), np.sin(a) * rng.uniform(150, 300))
        S.capsule((np.cos(a) * 25, 0, np.sin(a) * 25), top, 22, 14, "#7a9a3a", k=6, gloss=0.3)
        for f in (0.62, 0.82, 1.0):                     # feathery leaves hang along the upper cane
            p = np.array(top) * f + np.array([np.cos(a) * 25, 0, np.sin(a) * 25]) * (1 - f)
            S.ellipsoid(p + np.array([np.cos(a) * 60, -60, np.sin(a) * 60]), (190, 120, 190), "#5d8f32", k=60, gloss=0.05)
    S.paint(lambda P: np.abs((P[:, 1] % 160) - 80) - 74 + np.maximum(0, P[:, 1] - 1200) * 9, "#5c7a2a", soft=2)


def clay_rock(S):
    """a boulder: lumps of sandstone melted together"""
    S.fine = 12.0
    S.ellipsoid((0, 45, 0), (100, 55, 90), "#a08f7a", k=20, gloss=0.1)
    S.ellipsoid((50, 70, 20), (55, 40, 50), "#a08f7a", k=20, gloss=0.1)
    S.ellipsoid((-40, 30, -40), (60, 35, 50), "#a08f7a", k=20, gloss=0.1)
    S.paint(lambda P: 30 - P[:, 1], "#7d6e5c", soft=15)


def clay_tree(S):
    """a round tree"""
    S.fine = 24.0
    _trunk(S, (0, 0, 0), (0, 420, 0), 36, 24)
    _canopy(S, (0, 620, 0), 300, 10, LEAF, seed=9, squash=0.8)


def clay_cart(S):
    """a bullock cart: a wooden bed, two big spoked wheels, the long yoke pole"""
    S.fine = 8.0
    S.rbox((60, 95, 0), (130, 8, 75), "#8a5a32", r=3, k=3, gloss=0.2)
    for z in (-82, 82):
        S.torus((60, 70, z), 62, 7, "#6b4424", axis=(0, 0, 1), k=2, gloss=0.2)
        for a in range(6):
            t = a * np.pi / 6
            S.capsule((60 + 62 * np.cos(t), 70 + 62 * np.sin(t), z), (60 - 62 * np.cos(t), 70 - 62 * np.sin(t), z),
                      3.5, 3.5, "#6b4424", k=1)
    S.capsule((-60, 95, 0), (-260, 70, 0), 6, 5, "#8a5a32", k=3)
    for z in (-75, 75):
        S.capsule((-60, 103, z), (190, 103, z), 4, 4, "#6b4424", k=2)


def clay_fence(S):
    """a bamboo fence: posts and two rails"""
    S.fine = 4.0
    for x in range(-250, 260, 50):
        S.capsule((x, 0, 0), (x, 100, 0), 4, 3.5, "#a07a45", k=1.5)
    for y in (40, 80):
        S.capsule((-255, y, 0), (255, y, 0), 3, 3, "#a07a45", k=1.5)


def clay_gothan(S):
    """the gothan: a long open cattle shed - wooden posts under a sloping khaprail roof, a feeding trough"""
    S.fine = 24.0
    S.rbox((40, 10, 0), (620, 10, 250), "#9a8a6a", r=4, k=4)
    for x in range(-540, 680, 200):
        for z in (-230, 230):
            S.capsule((x, 0, z), (x, 290 if z < 0 else 250, z), 12, 10, "#6b4424", k=4)
    _gable(S, (40, 250, 0), 640, 270, 90, KHAPRAIL, thick=40, k=6, gloss=0.2)
    S.rbox((40, 30, 150), (560, 30, 30), "#8a7a5a", r=8, k=4)



# ---------------------------------------------------------------------------- the rest of the village's places
STONE, PLASTER, TRIM, SAFFRON = "#c2b49a", "#e9c9a0", "#8b3a2b", "#f08a24"


def _arch_paint(S, cx, cy_bottom, w, h, zf, colour):
    """an arched opening painted on a front wall (front at z = zf, facing -z)"""
    r = w / 2.0
    S.paint(lambda P: np.maximum(np.minimum(np.maximum(np.abs(P[:, 0] - cx) - r, np.maximum(cy_bottom - P[:, 1],
                                                                                          P[:, 1] - (cy_bottom + h - r))),
                                            np.hypot(P[:, 0] - cx, P[:, 1] - (cy_bottom + h - r)) - r),
                                 P[:, 2] - zf - 12), colour, soft=2)


def _steps(S, w, h, d, n, colour, rise_to="+z", **kw):
    """n steps (a total height h over depth d), climbing toward +z (or toward -x)"""
    for i in range(n):
        hi = h * (i + 1) / n
        if rise_to == "+z":
            z0 = -d / 2 + d * i / n
            S.rbox((0, hi / 2, (z0 + d / 2) / 2), (w / 2, hi / 2, (d / 2 - z0) / 2), colour, r=2.5, k=2, **kw)
        else:                                            # climbing toward -x
            x1 = d / 2 - d * i / n
            S.rbox(((x1 - d / 2) / 2, hi / 2, 0), ((x1 + d / 2) / 2, hi / 2, w / 2), colour, r=2.5, k=2, **kw)


def clay_haveli(S):
    """the haveli: a plinth, two plastered storeys with a maroon trim, an arched door and windows, a roof slab with a
    parapet and two little chhatris with saffron domes (the balcony and stairs are their own things)"""
    S.fine = 20.0
    S.rbox((0, 15, 0), (320, 15, 170), "#c4a37e", r=6, k=4)
    S.rbox((0, 30 + 235, 0), (300, 235, 150), PLASTER, r=8, k=6, gloss=0.08)
    S.rbox((0, 507, 0), (310, 7, 160), "#c9a985", r=3, k=3)
    S.rbox((0, 539, 0), (310, 25, 160), PLASTER, r=5, k=3)
    S.rbox((0, 539, 0), (290, 30, 140), "#000000", mode="sub", r=3, k=2)
    for y0 in (30, 270, 484):
        S.paint(lambda P, y0=y0: np.abs(P[:, 1] - y0 - 8) - 8, TRIM, soft=2)
    _arch_paint(S, 0, 270, 100, 190, -150, "#6b3a1e")
    for kx in (-260, 260):
        S.cyl((kx, 564, -140), 36, 10, TRIM, k=2)
        S.lathe((kx, 574, -140), [(0, 0), (38, 0), (30, 30), (12, 50), (0, 60)], "#f4a300", k=3, gloss=0.5)
    _door(S, -120, 30, -150, 110, 200, leaf="#6b3a1e", frame=TRIM, arch=True)
    for wx, wy in ((110, 160), (230, 160), (-200, 390), (200, 390)):
        _window(S, wx, wy, -150, 70, 100, frame=TRIM, bars=2)


def clay_balcony(S):
    """the haveli's balcony floor and the landing at the top of its stairs (people stand on it)"""
    S.fine = 8.0
    S.rbox((0, 7, 0), (339, 7, 60), "#b89a7a", r=3, k=2)


def clay_railing(S):
    S.fine = 4.0
    for k in range(15):
        x = -266 + k * 38
        S.capsule((x, 0, 0), (x, 62, 0), 3.5, 3.5, TRIM, k=1.5)
    S.rbox((0, 64, 0), (280, 4, 5), TRIM, r=2, k=1.5)


def clay_stairs(S):
    """ten stone steps up to the haveli's landing (climbing away from the camera)"""
    S.fine = 6.0
    _steps(S, 100, 264, 344, 10, "#c9b8a0")


def clay_stairs_wall(S):
    S.fine = 4.0
    S.rbox((0, 45, 0), (4, 45, 172), "#ab9c86", r=2, k=2)


def clay_tulsi(S):
    """the tulsi chaura: a little plastered pillar with a pot and the holy basil on top"""
    S.fine = 6.0
    S.rbox((0, 35, 0), (40, 35, 40), "#efe4cf", r=6, k=4)
    S.paint(lambda P: np.abs(P[:, 1] - 52) - 5, "#c0392b", soft=1.5)
    S.lathe((0, 70, 0), [(0, 0), (26, 0), (30, 14), (24, 22), (0, 22)], "#b5562a", k=2)
    rng = np.random.default_rng(11)
    for _ in range(8):
        S.ellipsoid((rng.uniform(-18, 18), rng.uniform(100, 130), rng.uniform(-18, 18)), (16, 18, 16), "#3f7a2e", k=8)


def clay_temple(S):
    """the Hanuman mandir: a stepped stone plinth (walk up it), a pillared porch, the curved shikhara spire with its
    amalaka and kalash, a saffron flag"""
    S.fine = 22.0
    for i, (w, d) in enumerate(((280, 300), (250, 270), (220, 240))):
        S.rbox((0, 12 + 24 * i, 20), (w, 12, d), STONE, r=4, k=3)
    S.rbox((0, 70 + 160, 120), (150, 160, 150), "#eadbc0", r=8, k=6, gloss=0.08)            # the sanctum
    S.lathe((0, 380, 120), [(0, 0), (175, 0), (165, 90), (130, 200), (85, 290), (40, 340), (0, 350)], "#e8cfa4",
            k=10, gloss=0.08)                                                                # shikhara
    S.paint(lambda P: np.abs(((P[:, 1] - 380) % 45) - 22) - 4 + np.maximum(0, 380 - P[:, 1]) * 9, "#c9a77a", soft=2)
    S.ellipsoid((0, 742, 120), (38, 16, 38), "#c9a77a", k=4)                                 # amalaka
    S.lathe((0, 756, 120), [(0, 0), (12, 0), (14, 12), (6, 22), (2, 34), (0, 36)], "#f4a300", k=2, gloss=0.8)
    S.capsule((40, 740, 120), (40, 860, 120), 3, 3, "#6b4424", k=1)
    S.rbox((75, 835, 120), (34, 18, 2), SAFFRON, r=1.5, k=1)
    S.rbox((0, 70 + 8, -110), (150, 8, 90), STONE, r=3, k=2)                                 # porch
    S.rbox((0, 300, -110), (165, 14, 100), "#e8cfa4", r=5, k=3)
    for x in (-130, -45, 45, 130):
        S.capsule((x, 86, -195), (x, 288, -195), 13, 11, "#eadbc0", k=4)
    _arch_paint(S, 0, 70, 100, 170, -30, "#5a2d16")
    S.paint(lambda P: np.maximum(np.abs(P[:, 0]) - 150, np.abs(P[:, 1] - 290) - 6), TRIM, soft=2)


def clay_school(S):
    """Ghatti's government school: a long single-storey building with an arched verandah, a taller middle with the
    name board, the flag on a pole, the walls in the school colours (cream, a blue band)"""
    S.fine = 26.0
    S.rbox((0, 15, 30), (960, 15, 200), "#b9ab90", r=6, k=4)
    S.rbox((0, 30 + 175, 80), (950, 175, 150), "#efe1bb", r=10, k=6, gloss=0.08)
    S.rbox((0, 30 + 280, 80), (240, 280, 155), "#efe1bb", r=10, k=6, gloss=0.08)            # the taller middle
    S.rbox((0, 392, -60), (960, 10, 115), "#c9b38a", r=4, k=3)                              # verandah roof
    for x in range(-900, 960, 150):
        if abs(x) > 260:
            S.capsule((x, 30, -165), (x, 384, -165), 14, 12, "#efe1bb", k=4)
    S.paint(lambda P: np.abs(P[:, 1] - 90) - 22, "#3b6fb5", soft=3)                        # the blue band
    S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) - 170, np.abs(P[:, 1] - 470) - 40), P[:, 2] + 60),
            "#1f4f8a", soft=2)                                                               # name board
    S.capsule((520, 0, -260), (520, 620, -260), 6, 5, "#c9ced6", k=2, gloss=0.6)            # flag pole
    for i, c in enumerate(("#ff9933", "#ffffff", "#138808")):
        S.rbox((585, 600 - 26 * i, -260), (60, 13, 2), c, r=1, k=1)
    _door(S, 0, 30, -70, 260, 240, leaf="#6b4424")
    for wx in (-750, -550, -380, 380, 550, 750):
        _window(S, wx, 220, -70, 90, 110, frame="#3e5a6b", bars=4)


def clay_stall(S):
    """a mela / haat stall: bamboo poles, a striped cloth roof, a low table heaped with goods"""
    S.fine = 8.0
    for x in (-140, 140):
        for z in (-65, 65):
            S.capsule((x, 0, z), (x, 250, z), 5, 5, "#b08a50", k=2)
    S.rbox((0, 258, 0), (160, 9, 82), "#d94b4b", r=4, k=3)
    S.paint(lambda P: np.abs(((P[:, 0] + 400) % 60) - 30) - 14 + np.maximum(0, 250 - P[:, 1]) * 9, "#f2e2b6", soft=1)
    S.rbox((0, 60, -10), (130, 8, 55), "#8a5a32", r=3, k=2)
    for x in (-110, 110):
        for z in (-50, 30):
            S.capsule((x, 0, z), (x, 56, z), 4, 4, "#6b4424", k=1.5)
    rng = np.random.default_rng(12)
    for i in range(14):
        c = ("#e63946", "#f4a261", "#2a9d4f", "#e9c46a", "#9b5de5")[i % 5]
        S.ellipsoid((rng.uniform(-110, 110), 78, rng.uniform(-45, 30)), (14, 10, 14), c, k=4, gloss=0.3)


def clay_lamp(S):
    """a street lamp: an iron pole with a curved arm and a lantern"""
    S.fine = 4.0
    S.cyl((0, 0, 0), 14, 20, "#5a5f66", k=2)
    S.capsule((0, 20, 0), (0, 500, 0), 6, 4.5, "#5a5f66", k=2, gloss=0.5)
    S.capsule((0, 500, 0), (-45, 515, 0), 4, 4, "#5a5f66", k=2, gloss=0.5)
    S.lathe((-49, 470, 0), [(0, 0), (8, 0), (11, 18), (14, 34), (0, 40)], "#f5e7b0", k=2, gloss=0.6)


def clay_swing(S):
    """a jhula: an A-frame of poles, a crossbar, two ropes and a plank seat"""
    S.fine = 3.5
    for x in (-150, 150):
        S.capsule((x, 0, -70), (x, 300, 0), 7, 6, "#8a5a32", k=2)
        S.capsule((x, 0, 70), (x, 300, 0), 7, 6, "#8a5a32", k=2)
    S.capsule((-155, 300, 0), (155, 300, 0), 7, 7, "#6b4424", k=2)
    for x in (-50, 50):
        S.capsule((x, 296, 0), (x, 70, 0), 3.6, 3.6, "#d9c7a0", k=1)
    S.rbox((0, 66, 0), (62, 4, 18), "#a0522d", r=2, k=1.5)


def clay_bench(S):
    """a wooden bench"""
    S.fine = 5.0
    S.rbox((0, 70, 0), (120, 5, 30), "#9b6a3c", r=3, k=2, gloss=0.2)
    S.rbox((0, 120, 28), (120, 18, 4), "#9b6a3c", r=2, k=2, gloss=0.2)
    for x in (-100, 100):
        S.rbox((x, 35, 0), (6, 35, 26), "#6b4424", r=2, k=2)


def clay_goal(S):
    """a football goal: two posts, a crossbar, a net"""
    S.fine = 5.0
    for x in (-230, 230):
        S.capsule((x, 0, 0), (x, 240, 0), 6, 6, "#f4f4f4", k=2)
        S.capsule((x, 240, 0), (x * 0.95, 0, 140), 3, 3, "#d9d9d9", k=1)
    S.capsule((-230, 240, 0), (230, 240, 0), 6, 6, "#f4f4f4", k=2)


def clay_tea_shop(S):
    """the tea stall: a little shop with its front open, a counter with a big kettle and glasses, a red CHAI board,
    a tin awning"""
    S.fine = 14.0
    S.rbox((0, 140, 40), (190, 140, 140), "#d9b98a", r=10, k=6, gloss=0.08)
    S.rbox((0, 150, -60), (165, 120, 70), "#4a3426", mode="sub", r=6, k=4)
    S.rbox((0, 50, -120), (175, 50, 25), "#8a5a32", r=5, k=4)
    S.rbox((0, 300, -160), (205, 8, 80), "#7a8c96", r=3, k=3, gloss=0.5)
    for x in (-195, 195):
        S.capsule((x, 0, -230), (x, 296, -230), 7, 6, "#6b4424", k=3)
    S.rbox((0, 336, -236), (115, 26, 5), "#c0392b", r=3, k=2)                    # the CHAI board over the awning
    S.paint(lambda P: np.maximum(np.abs(P[:, 0]) - 95, np.abs(P[:, 1] - 336) - 9) + np.maximum(0, P[:, 2] + 238) * 9,
            "#f6e7b0", soft=1.5)
    S.lathe((-90, 100, -120), [(0, 0), (22, 0), (26, 18), (16, 32), (6, 38), (0, 40)], "#c9ced6", k=2, gloss=0.8)
    for i in range(5):
        S.lathe((20 + 22 * i, 100, -125), [(0, 0), (5, 0), (6.5, 16), (0, 16)], "#e8f2f8", k=1, gloss=0.6)


def clay_stove(S):
    """the tea stall's chulha on a stand: a mud stove with the chai patila on it"""
    S.fine = 5.0
    S.rbox((0, 45, 0), (45, 45, 35), "#8a5a32", r=4, k=3)
    S.lathe((0, 90, 0), [(0, 0), (34, 0), (32, 34), (24, 40), (0, 40)], "#b5562a", k=3)
    S.lathe((0, 130, 0), [(0, 0), (22, 0), (28, 26), (0, 26)], "#c9ced6", k=2, gloss=0.8)
    S.paint(lambda P: np.maximum(np.hypot(P[:, 0], P[:, 2]) - 25, 155 - 0.8 - P[:, 1]), "#8a5a2b", soft=1)


def clay_shrine(S):
    """a little white shrine by the river: a step, the cella with an arched opening, a small spire, a flag"""
    S.fine = 6.0
    S.rbox((0, 8, 0), (57, 8, 57), STONE, r=3, k=2)
    S.rbox((0, 16 + 65, 0), (45, 65, 45), "#f4efe4", r=5, k=3, gloss=0.08)
    S.lathe((0, 146, 0), [(0, 0), (50, 0), (40, 35), (20, 70), (0, 80)], "#f4efe4", k=4)
    _arch_paint(S, 0, 20, 44, 80, -45, "#c0392b")
    S.capsule((0, 220, 0), (0, 250, 0), 2, 2, "#6b4424", k=1)
    S.rbox((14, 244, 0), (12, 6, 1), SAFFRON, r=1, k=1)


def clay_reeds(S):
    S.fine = 2.5
    rng = np.random.default_rng(13)
    for _ in range(14):
        x, z = rng.uniform(-60, 60), rng.uniform(-30, 30)
        S.capsule((x, 0, z), (x + rng.uniform(-10, 10), rng.uniform(40, 58), z), 2.5, 1.2, "#6f9a3a", k=1)


def clay_ghat(S):
    """the ghat's raised stone bank (people walk on it)"""
    S.fine = 14.0
    S.rbox((0, 50, 0), (240, 50, 190), STONE, r=6, k=4)
    S.paint(lambda P: np.minimum(np.abs(((P[:, 0] + 600) % 80) - 40), np.abs(((P[:, 2] + 600) % 60) - 30)) - 1.6
            + np.maximum(0, 96 - P[:, 1]) * 9, "#a8997e", soft=1)


def clay_front_steps(S):
    S.fine = 6.0
    _steps(S, 260, 100, 130, 4, STONE)


def clay_side_steps(S):
    S.fine = 6.0
    _steps(S, 300, 104, 110, 4, STONE, rise_to="-x")


def clay_jetty(S):
    """a wooden jetty out over the water"""
    S.fine = 5.0
    S.rbox((0, 30, 0), (190, 6, 55), "#9b6a3c", r=2, k=2)
    S.paint(lambda P: np.abs(((P[:, 0] + 400) % 24) - 12) - 0.9, "#6b4424", soft=0.8)
    for x in (-140, 0, 140):
        for z in (-45, 45):
            S.capsule((x, -40, z), (x, 28, z), 6, 6, "#6b4424", k=2)



# ---------------------------------------------------------------------------- lived-in things round the houses
def clay_washing_line(S):
    """a washing line between two bamboo posts with clothes drying on it (a sari, a kurta, a gamchha)"""
    S.fine = 3.5
    for x in (-150, 150):
        S.capsule((x, 0, 0), (x, 168, 0), 4, 3.5, "#a07a45", k=1.5)
    S.capsule((-150, 165, 0), (0, 150, 0), 1.6, 1.6, "#d9d2c0", k=0.5)
    S.capsule((0, 150, 0), (150, 165, 0), 1.6, 1.6, "#d9d2c0", k=0.5)
    for k, (x, h, c) in enumerate(((-108, 80, "#c9184a"), (-50, 55, "#f4a261"), (8, 90, "#2a9d8f"),
                                   (66, 55, "#e9c46a"), (112, 70, "#457b9d"))):
        y = 150 + 15 * (1 - abs(x) / 150.0) - 3
        S.rbox((x, y - h / 2, 0), (22, h / 2, 2.2), c, r=2, k=1.5)


def clay_matka_stack(S):
    """clay pots stacked by the door"""
    S.fine = 4.0
    for (x, y, z, r) in ((0, 0, 0, 26), (42, 0, 10, 22), (18, 46, 5, 19)):
        S.lathe((x, y, z), [(0, 0), (r * 0.5, 0), (r, r * 0.8), (r * 0.95, r * 1.4), (r * 0.55, r * 1.85),
                            (r * 0.62, r * 2.0), (0, r * 2.0)], "#b5562a", k=1.5, gloss=0.15)
    S.paint(lambda P: np.abs(P[:, 1] - 24) - 2, "#e8d9b5", soft=1)


def clay_firewood(S):
    """a heap of firewood (lakdi) for the chulha"""
    S.fine = 4.0
    rng = np.random.default_rng(21)
    for i in range(12):
        y = 8 + (i // 4) * 13
        z = -26 + (i % 4) * 17 + rng.uniform(-3, 3)
        S.capsule((-70 + rng.uniform(-8, 8), y, z), (70 + rng.uniform(-8, 8), y + rng.uniform(-3, 3), z),
                  7, 6, ("#7a5230", "#8d6440", "#6b4424")[i % 3], k=1)


def clay_grain_sacks(S):
    """jute sacks of grain"""
    S.fine = 5.0
    for x, z, y in ((-30, 0, 0), (30, 5, 0), (0, 0, 40)):
        S.rbox((x, y + 21, z), (30, 21, 20), "#d8c7a0", r=12, k=4)
        S.paint(lambda P, x=x, y=y: np.abs(P[:, 1] - y - 36) - 1.5 + np.maximum(0, np.abs(P[:, 0] - x) - 26) * 9,
                "#a8946a", soft=0.8)


def clay_basket(S):
    """a bamboo basket with vegetables"""
    S.fine = 3.0
    S.lathe((0, 0, 0), [(0, 0), (24, 0), (31, 26), (28, 27), (0, 6)], "#c8a165", k=1.5)
    S.paint(lambda P: np.abs(((P[:, 1]) % 6) - 3) - 0.7, "#a9824a", soft=0.4)
    for k, c in enumerate(("#e63946", "#f4a261", "#2a9d4f")):
        S.sphere((-12 + 12 * k, 27, 0), 10, c, k=2, gloss=0.3)


def clay_tea_tray(S):
    """a tray of glasses of chai on a stool"""
    S.fine = 2.5
    S.cyl((0, 0, 0), 22, 52, "#8a5a32", k=2)
    S.cyl((0, 52, 0), 30, 3, "#c9ced6", k=1, gloss=0.8)
    for x, z in ((-12, -8), (10, -10), (0, 10), (16, 8)):
        S.lathe((x, 55, z), [(0, 0), (4, 0), (5, 12), (0, 12)], "#e8d7b0", k=0.6, gloss=0.6)
        S.paint(lambda P, x=x, z=z: np.maximum(np.hypot(P[:, 0] - x, P[:, 2] - z) - 4.6, 66.4 - P[:, 1]),
                "#8a5a2b", soft=0.4)


def clay_bicycle(S):
    """an old black bicycle leaning on its stand"""
    S.fine = 2.5
    for x in (-60, 60):
        S.torus((x, 34, 0), 32, 3.2, "#222222", axis=(0, 0, 1), k=1)
    S.capsule((-60, 34, 0), (-8, 34, 0), 2.6, 2.6, "#1d1d1d", k=1, gloss=0.5)
    S.capsule((-8, 34, 0), (40, 80, 0), 2.6, 2.6, "#1d1d1d", k=1, gloss=0.5)
    S.capsule((-8, 34, 0), (-30, 82, 0), 2.6, 2.6, "#1d1d1d", k=1, gloss=0.5)
    S.capsule((-30, 82, 0), (40, 80, 0), 2.6, 2.6, "#1d1d1d", k=1, gloss=0.5)
    S.capsule((40, 80, 0), (60, 34, 0), 2.6, 2.6, "#1d1d1d", k=1, gloss=0.5)
    S.capsule((-60, 34, 0), (-30, 82, 0), 2.2, 2.2, "#1d1d1d", k=1, gloss=0.5)
    S.rbox((-32, 88, 0), (10, 3, 5), "#5a3a22", r=2, k=1)
    S.capsule((40, 80, 0), (44, 100, 0), 2.4, 2.4, "#1d1d1d", k=1, gloss=0.5)
    S.capsule((44, 100, -18), (44, 100, 18), 2.2, 2.2, "#c9ced6", k=1, gloss=0.8)


RECIPES = {f.__name__: f for f in (clay_khaprail_house, clay_hut, clay_pucca_house, clay_building, clay_shop,
                                   clay_banyan, clay_mahua, clay_mango, clay_neem, clay_bush, clay_well, clay_haystack,
                                   clay_handpump, clay_sal, clay_teak, clay_bamboo, clay_rock, clay_tree, clay_cart,
                                   clay_fence, clay_gothan, clay_haveli, clay_balcony, clay_railing, clay_stairs,
                                   clay_stairs_wall, clay_tulsi, clay_temple, clay_school, clay_stall, clay_lamp,
                                   clay_swing, clay_bench, clay_goal, clay_tea_shop, clay_stove, clay_shrine, clay_reeds,
                                   clay_ghat, clay_front_steps, clay_side_steps, clay_jetty, clay_washing_line,
                                   clay_matka_stack, clay_firewood, clay_grain_sacks, clay_basket, clay_tea_tray,
                                   clay_bicycle)}
