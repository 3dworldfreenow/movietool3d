KIND = "character3d"
FOR = "human"
DESCRIPTION = "the normal 3D person - every person uses this unless they have their own file (change it = change everyone)"
PREVIEW = {"age": "adult", "gender": "male", "outfit": "shirt", "hair": "short", "mustache": True}

# The engine hands you a posed skeleton: rig. Everything you draw moves with every action (walk, sit, dance ...).
#   x = forward (where the person looks), y = up, z = to the side.  An adult is about 300 tall.
#   rig.leg("near") -> (hip, knee, foot, toe)      rig.arm("near") -> (shoulder, elbow, hand)   ("far" = the other side)
#   rig.hip  rig.waist  rig.chest  rig.neck  rig.neck_top   rig.head (middle)  rig.head_r
#   rig.on_head(forward, up, side) -> a point on the head (units of the head size; 1 = on the surface)
#   rig.cap(pen, covered, colour, size) -> part of a ball round the head (hair, caps): covered(up, forward) -> True/False
#   colours: rig.skin rig.top rig.bottom rig.shoes rig.hair_color rig.accent
#   looks: rig.gender rig.age rig.hair rig.outfit rig.bottom_kind rig.sleeves rig.mustache rig.beard
#   now: rig.face (happy, sad ...) rig.mouth (0..1 talking) rig.blink   rig.show("hair") = False when hidden


def draw(pen, rig, t, state):
    s, K = rig.s, rig.K
    # ---------------- legs + shoes
    if rig.show("legs"):
        for side in ("near", "far"):
            hip, knee, foot, toe = rig.leg(side)
            lr = 6.6 * K
            if rig.bottom_kind == "shorts":
                mid = rig.mix(hip, knee, 0.9)
                pen.tube([hip, mid], [lr * 1.25, lr * 1.2], c=rig.bottom, sides=8, smooth=False)
                pen.tube([mid, knee, foot], lr * 0.85, c=rig.skin, sides=8, smooth=False)
            elif rig.bottom_kind == "none":
                pen.tube([hip, knee, foot], lr * 0.9, c=rig.skin, sides=8, smooth=False)
            else:
                pen.tube([hip, knee, foot], [lr * 1.1, lr, lr * 0.9], c=rig.bottom, sides=8, smooth=False)
            if rig.show("shoes"):
                fx = toe[0] - foot[0]
                pen.ellipsoid(foot[0] + fx * 0.45, foot[1] + 2.5 * s, foot[2], rx=11 * s, ry=4.5 * s, rz=6 * s,
                              c=rig.shoes, rings=4, sides=8)
    # ---------------- skirt / dress / saree / dhoti over the legs
    if rig.show("skirt") and rig.bottom_kind in ("skirt", "long_skirt", "dhoti"):
        top_y = rig.waist[1] * 0.55 + rig.hip[1] * 0.45
        if rig.bottom_kind == "long_skirt":
            low = min(rig.leg("near")[2][1], rig.leg("far")[2][1]) + 10 * s
        elif rig.bottom_kind == "skirt":
            low = rig.leg("near")[1][1] + 4 * s
        else:
            low = (rig.leg("near")[1][1] + rig.leg("near")[2][1]) / 2
        x = (rig.hip[0] + rig.waist[0]) / 2
        pen.cylinder(x, low, 0, r=rig.hw * 1.9 + 6 * s, r2=rig.hw + 6 * s, h=max(10.0, top_y - low), c=rig.bottom,
                     sides=10)
    # ---------------- body (from the hips up to the neck)
    if rig.show("body"):
        w = rig.sw * (0.95 if rig.gender == "female" else 1.0)
        pen.tube([rig.hip, rig.waist, rig.chest, rig.neck], [rig.hw * 1.35, rig.hw * 1.25 + 1.5 * s, w * 0.95, w * 0.55],
                 c=rig.top, sides=10, smooth=False)
        # the neck: tapered and round (thicker for a heavier body), and the shoulder
        # muscles (trapezius) sloping from it to the shoulders, so the head does not sit on a stick
        nr = rig.head_r * 0.36 * max(0.85, min(1.3, (K / s) ** 1.0))
        nb, nt = rig.neck, rig.neck_top
        # one solid piece (thin rings let the clothes behind show through as stripes)
        pen.tube([(nb[0], nb[1] - 4 * s, nb[2]), (nt[0], nt[1] + 9 * s, nt[2])], [nr * 1.08, nr * 0.86], c=rig.skin, sides=20, smooth=False, ends=False)
        cloth = rig.top if rig.outfit != "none" else rig.skin
        for side in ("near", "far"):
            sh = rig.arm(side)[0]
            pen.tube([(nb[0] - 1.5 * s, nb[1] - 4 * s, sh[2] * 0.3), (sh[0] - 1 * s, sh[1] + 1.5 * s, sh[2] * 0.8)], [nr * 0.85, nr * 0.55],
                     c=cloth, sides=10, smooth=False)
    # ---------------- arms + hands
    if rig.show("arms"):
        for side in ("near", "far"):
            sh, el, hd = rig.arm(side)
            ar = 5.4 * K
            if rig.sleeves == "long":
                pen.tube([sh, el, hd], [ar * 1.15, ar, ar * 0.9], c=rig.top, sides=8, smooth=False)
            elif rig.sleeves == "short":
                mid = rig.mix(sh, el, 0.55)
                pen.tube([sh, mid], [ar * 1.3, ar * 1.2], c=rig.top, sides=8, smooth=False)
                pen.tube([mid, el, hd], ar * 0.85, c=rig.skin, sides=8, smooth=False)
            else:
                pen.tube([sh, el, hd], ar * 0.85, c=rig.skin, sides=8, smooth=False)
            pen.sphere(hd[0], hd[1], hd[2], r=6.2 * s, c=rig.skin, rings=4, sides=7)
    # ---------------- cloth that swings: dupatta, saree pallu, cape (they trail behind and settle: rig.drag)
    if rig.show("cloth"):
        draw_cloth(pen, rig, s)
    # ---------------- head
    r = rig.head_r
    if rig.show("head"):
        rig.skull(pen)                                             # the sculpted head, smooth shading
    # ---------------- hair (a cap over the top and back: the face stays open)
    hs = rig.hair
    if rig.show("hair") and hs not in ("bald", "none"):
        long_hair = hs in ("long", "braid")

        def covered(up, fwd):
            if hs == "bald_sides":
                return -0.45 < up < 0.35 and fwd < -0.05
            if up > 0.42:
                return True                                      # the top, down to the hairline
            if fwd < (0.25 if long_hair else 0.1):
                return up > (-0.95 if long_hair else -0.5)       # sides and back
            return False
        rig.cap(pen, covered, rig.hair_color, 1.13 if hs == "spiky" else 1.1)
        if hs == "spiky":
            for k in range(5):
                p = rig.on_head(-0.2 + 0.12 * k, 1.0, -0.5 + 0.25 * k)
                pen.cone(p[0], p[1] - 3 * s, p[2], r=5 * s, h=10 * s, c=rig.hair_color, sides=5)
        if long_hair:                                    # swings behind when walking / running (rig.drag)
            a = rig.on_head(-0.55, 0.1, 0)
            pen.tube([a, rig.swing(a, rig.on_head(-0.7, -1.9, 0), 0.7)], [r * 0.85, r * 0.55],
                     c=rig.hair_color, sides=9, smooth=False)
        elif hs == "ponytail":
            a = rig.on_head(-1.0, 0.3, 0)
            pen.tube([a, rig.swing(a, rig.on_head(-1.35, -0.9, 0), 1.0)], [r * 0.3, r * 0.15],
                     c=rig.hair_color, sides=7, smooth=False)
        elif hs == "bun":
            p = rig.on_head(-0.75, 0.6, 0)
            pen.smooth_ellipsoid(p[0], p[1], p[2], rx=r * 0.42, ry=r * 0.42, rz=r * 0.42, c=rig.hair_color, rings=6, sides=10)
        if hs != "spiky":
            hair_locks(pen, rig, r, hs)
    # ---------------- ears
    if rig.show("ears") and hs not in ("long", "braid"):
        for sd in (-1.0, 1.0):
            p = rig.on_head(-0.02, -0.08, sd * (0.98 + 0.06 * (rig.look.get("ears", 1.0) - 1.0)))
            ek = rig.look.get("ears", 1.0)                        # (big cartoon ears stick out more)
            pen.smooth_ellipsoid(p[0], p[1], p[2], rx=r * 0.15 * ek, ry=r * 0.24 * ek, rz=r * 0.09 * ek ** 1.5, c=rig.skin, rings=5, sides=9)
    # ---------------- face: big cartoon eyes, eyebrows, nose, mouth - they follow the emotion AND the voice:
    #   rig.mouth_shape = {jaw, wide, round, closed, teeth, tongue} (M/B/P shut, O round, AA wide open ...)
    #   rig.brow (0..1 up on stressed words / questions), rig.gaze (x, y glances), rig.lid (0 open .. 1 shut)
    #   rig.look = this person's own face (eye size / gap, nose, mouth, brows, iris colour)
    #   Every part is painted on an anchor in front of the face (rig.face_anchor + rig.layer), in order, so
    #   eyes, lids and mouth always stack right from every camera angle.
    if rig.show("face"):
        draw_face(pen, rig, r)
    if rig.show("beard") and rig.beard:
        p = rig.on_head(0.55, -0.72, 0)
        pen.ellipsoid(p[0], p[1], p[2], rx=r * 0.5, ry=r * 0.42, rz=r * 0.62, c=rig.hair_color, rings=4, sides=9)
        if _close(pen, rig):                           # close up: the beard in clumps along the jaw
            for k in range(9):
                lat = -0.75 + 1.5 * k / 8
                u0 = -0.45 - 0.35 * (1 - abs(lat))
                _lock(pen, rig, (0.62 - 0.3 * abs(lat), u0, lat), (0.25, -1.0, lat * 0.3), 0.32 + 0.12 * (1 - abs(lat)),
                      r * 0.11, _shade(pen, rig.hair_color, k), sway=0.2)


def _close(pen, rig):
    """hair locks only where they show: the head big on screen (close-ups, medium shots)"""
    return pen.detail >= 0.75 and rig.head_r * (pen.px_unit or 6.0) > 24.0


def _shade(pen, c, k):
    """locks catch the light differently: a few lighter, a few darker"""
    return pen.mix(c, "#a07a5c", 0.3) if k % 3 == 0 else (pen.dark(c, 0.78) if k % 3 == 1 else pen.mix(c, "#a07a5c", 0.12))


def _lock(pen, rig, start, d, length, w, c, sway=1.0, hang=1.0, swing=0.0):
    """💇 one lock of hair: a tapered clump from a point on the head (f, u, lat in head sizes) along d, bending down
    under its weight, kept outside the head, swaying a little in the wind / with the head (rig.t, rig.drag)."""
    f0, u0, l0 = start
    dn = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
    df, du, dl = d[0] / dn, d[1] / dn, d[2] / dn
    ph = (f0 * 3.1 + l0 * 5.3 + u0 * 1.7)
    wv = 0.05 * sway * math.sin(rig.t * 2.3 + ph)
    pts = []
    for i in range(5):
        t = i / 4.0
        f = f0 + df * length * t
        u = u0 + du * length * t - 0.35 * hang * (length * t) ** 2
        l = l0 + dl * length * t + wv * t * t
        R = math.sqrt(f * f + u * u + l * l)
        if R < 1.05 and R > 1e-6:                        # stay on top of the head, not inside it
            f, u, l = f * 1.05 / R, u * 1.05 / R, l * 1.05 / R
        pts.append(rig.on_head(f, u, l))
    if swing:
        pts = [pts[0]] + [rig.swing(pts[0], p, swing) for p in pts[1:]]
    pen.tube(pts, [w, w * 0.9, w * 0.7, w * 0.42, w * 0.12], c=c, sides=5, smooth=False, ends=False)


def hair_locks(pen, rig, r, hs):
    """Hair as shaped clumps (film look) on top of the hair cap - only in close-ups / medium shots"""
    if not _close(pen, rig) or hs in ("bald", "none", "bald_sides"):
        return
    hc = rig.hair_color
    long_hair = hs in ("long", "braid")
    n = 14
    for k in range(n):                                   # the crown: locks fan out from the parting and lie down
        a = 2 * math.pi * (k + 0.5) / n
        ca, sa = math.cos(a), math.sin(a)
        if ca > 0.55 and not long_hair and hs not in ("ponytail", "bun"):
            continue                                     # (the fringe covers the front)
        _lock(pen, rig, (0.25 * ca - 0.05, 1.02, 0.25 * sa), (ca, -0.35, sa), 0.55 if hs == "short" else 0.75,
              r * 0.17, _shade(pen, hc, k), sway=0.4)
    if hs in ("short", "long", "braid"):
        for k in range(5):                               # a fringe at the hairline
            lat = -0.42 + 0.21 * k
            _lock(pen, rig, (0.55, 0.78, lat), (0.6, -0.7, lat * 0.6), 0.28 if hs == "short" else 0.36, r * 0.12,
                  _shade(pen, hc, k + 1), sway=0.6)
    if long_hair:                                        # long hair: locks hanging down the back and framing the face
        for k in range(9):
            lat = -0.95 + 1.9 * k / 8
            _lock(pen, rig, (-0.35 - 0.35 * (1 - abs(lat)), 0.4, lat * 0.95), (-0.25, -1.0, lat * 0.25), 1.55,
                  r * 0.2, _shade(pen, hc, k), sway=1.0, hang=0.2, swing=0.7)
        for sd in (-1.0, 1.0):
            _lock(pen, rig, (0.2, 0.45, sd * 0.98), (0.1, -1.0, sd * 0.15), 1.25, r * 0.16, _shade(pen, hc, 2 if sd > 0 else 0),
                  sway=0.9, hang=0.2, swing=0.5)
    elif hs == "ponytail":                               # the tail as a few strands
        a = rig.on_head(-1.0, 0.3, 0)
        for k in range(4):
            off = (k - 1.5) * 0.08
            _lock(pen, rig, (-1.02, 0.3 + off, off), (-0.35, -1.0, off), 1.2, r * 0.12, _shade(pen, hc, k), sway=1.2, hang=0.3, swing=1.0)


def draw_cloth(pen, rig, s):
    ex = rig.extras
    if not ({"dupatta", "pallu", "cape"} & ex):
        return
    ch, nk, hp = rig.chest, rig.neck, rig.hip
    w = rig.sw
    acc = rig.accent
    if "cape" in ex:
        top = [(ch[0] - 4 * s, ch[1] + 2 * s, -w * 1.05), (ch[0] - 7 * s, ch[1] + 4 * s, 0.0),
               (ch[0] - 4 * s, ch[1] + 2 * s, w * 1.05)]
        rows = [top]
        for k in (1, 2, 3):
            f = k / 3.0
            row = []
            for j, p in enumerate(top):
                flare = 1.0 + 0.45 * f
                end = (p[0] - 6 * s, p[1] - 140 * s * f, p[2] * flare)
                q = rig.swing(p, end, 0.9 * f + 0.1)
                row.append(q)
            rows.append(row)
        for a, b in zip(rows, rows[1:]):
            for j in range(len(a) - 1):
                pen.poly([a[j], a[j + 1], b[j + 1], b[j]], c=acc, two_sided=True)
    if "dupatta" in ex:                    # over both shoulders, the ends hanging down the back
        fr = [(nk[0] + 6 * s, nk[1] - 10 * s, -w * 0.7), (nk[0] + 7 * s, nk[1] - 14 * s, 0.0),
              (nk[0] + 6 * s, nk[1] - 10 * s, w * 0.7)]
        pen.tube(fr, 4.2 * s, c=acc, sides=5, smooth=True)
        for sd in (-1.0, 1.0):
            sh = (ch[0] - 2 * s, ch[1] + 3 * s, sd * w * 0.85)
            end = (sh[0] - 8 * s, sh[1] - 105 * s, sd * w * 0.95)
            pen.tube([sh, rig.mix(sh, rig.swing(sh, end, 0.6), 0.5), rig.swing(sh, end, 1.0)], [5 * s, 6 * s, 6.5 * s],
                     c=acc, sides=5, smooth=False)
    if "pallu" in ex:                      # saree end: from the waist across the chest, over the far shoulder
        wa = (hp[0] + 9 * s, rig.waist[1], -w * 0.5)
        sh = (ch[0] + 2 * s, ch[1] + 4 * s, w * 0.8)
        mid = rig.mix(wa, sh, 0.5)
        mid = (mid[0] + 8 * s, mid[1], mid[2])
        pen.tube([wa, mid, sh], 7.5 * s, c=pen.dark(rig.bottom, 0.9), sides=5, smooth=True)
        end = (sh[0] - 10 * s, sh[1] - 120 * s, sh[2])
        pen.tube([sh, rig.mix(sh, rig.swing(sh, end, 0.6), 0.5), rig.swing(sh, end, 1.0)], [8 * s, 9 * s, 10 * s],
                 c=pen.dark(rig.bottom, 0.9), sides=5, smooth=False)


# emotion -> upper lid (0 open .. 1 shut), lid tilt (+ inner corner down = cross), lower lid (squint), eye size,
#            iris size, brows up, brow tilt (+ inner end up = worried), smile (+ corners up), mouth open, round,
#            teeth, cheeks pink
EMO = {
    "neutral":   (0.12, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.015, 0.0, 0.0, 0.0, 0),
    "happy":     (0.08, 0.0, 0.3, 1.0, 1.0, 0.04, -0.03, 0.12, 0.09, 0.0, 1.0, 1),
    "laughing":  (1.0, 0.0, 0.0, 1.0, 1.0, 0.08, -0.03, 0.12, 0.24, 0.0, 1.0, 1),
    "love":      (0.15, 0.0, 0.3, 1.0, 1.0, 0.05, 0.03, 0.07, 0.0, 0.0, 0.0, 1),
    "shy":       (0.3, 0.0, 0.25, 0.95, 1.0, 0.0, 0.06, 0.04, 0.0, 0.0, 0.0, 1),
    "sad":       (0.38, -0.5, 0.0, 1.0, 1.0, -0.02, 0.14, -0.07, 0.0, 0.0, 0.0, 0),
    "crying":    (0.5, -0.5, 0.2, 1.0, 1.0, -0.02, 0.16, -0.09, 0.12, 0.0, 0.0, 0),
    "angry":     (0.36, 0.75, 0.15, 1.0, 0.9, -0.06, -0.16, -0.05, 0.08, 0.0, 1.0, 0),
    "surprised": (0.0, 0.0, 0.0, 1.16, 0.75, 0.15, 0.03, 0.0, 0.2, 0.9, 0.0, 0),
    "scared":    (0.0, -0.3, 0.0, 1.14, 0.68, 0.12, 0.12, -0.05, 0.11, 0.2, 1.0, 0),
    "thinking":  (0.32, 0.0, 0.1, 1.0, 1.0, 0.06, 0.0, 0.0, 0.0, 0.0, 0.0, 0),
    "sleeping":  (1.0, 0.0, 0.0, 1.0, 1.0, -0.02, 0.0, 0.02, 0.0, 0.0, 0.0, 0),
    "sleepy":    (0.55, -0.2, 0.0, 1.0, 1.0, -0.02, 0.04, 0.0, 0.0, 0.0, 0.0, 0),
    "tired":     (0.5, -0.2, 0.0, 1.0, 1.0, -0.02, 0.06, -0.03, 0.0, 0.0, 0.0, 0),
    "bored":     (0.48, 0.0, 0.0, 1.0, 1.0, -0.02, 0.0, -0.02, 0.0, 0.0, 0.0, 0),
    "suspicious": (0.45, 0.4, 0.2, 1.0, 1.0, -0.03, -0.06, -0.02, 0.0, 0.0, 0.0, 0),
    "proud":     (0.3, 0.0, 0.1, 1.0, 1.0, 0.03, -0.02, 0.06, 0.0, 0.0, 0.0, 0),
    "confused":  (0.15, 0.0, 0.0, 1.0, 1.0, 0.05, 0.05, -0.02, 0.0, 0.0, 0.0, 0),
    "excited":   (0.0, 0.0, 0.1, 1.08, 0.95, 0.1, 0.0, 0.11, 0.18, 0.0, 1.0, 1),
    "disgusted": (0.3, 0.3, 0.35, 0.95, 0.95, -0.04, -0.08, -0.06, 0.05, 0.0, 1.0, 0),
}
NEUTRAL_E = EMO["neutral"]


def _curve(n, fn):
    return [fn(-1.0 + 2.0 * i / (n - 1)) for i in range(n)]


def draw_face(pen, rig, r):
    look = rig.look
    e = EMO.get(rig.face, EMO["neutral"])
    if rig.face_from and rig.face_from in EMO and rig.face_k < 1.0:     # changing expression: blend smoothly
        e0, k = EMO[rig.face_from], rig.face_k * rig.face_k * (3 - 2 * rig.face_k)
        e = tuple(a + (b - a) * k for a, b in zip(e0, e))
    ex = rig.face_ex                                    # the story's exaggeration: bigger (cartoon) or smaller (calm) faces
    if abs(ex - 1.0) > 0.02:
        e = tuple((n_ + (v - n_) * ex) if i_ not in (0, 10, 11) else v for i_, (v, n_) in enumerate(zip(e, NEUTRAL_E)))
        e = (e[0], e[1], max(0.0, e[2]), max(0.6, e[3]), max(0.5, e[4])) + e[5:]
    lid0, ltilt, low, esz, isz, bup, btilt, smile, mopen, mround, teeth, pink = e
    far = pen.detail < 0.55                             # far away: fewer parts (fast), same look
    ink = "#1d1615"
    gx, gy = rig.gaze
    if rig.face == "shy":
        gy -= 0.6
    lid = max(lid0, min(1.0, rig.lid if rig.face != "laughing" else 0.0))
    if rig.blink or rig.lid > 0.85:
        lid = 1.0
    happy_closed = rig.face == "laughing" and lid0 > 0.9
    es = look["eyes"] * esz
    ry, rz, rx = 0.2 * es, 0.145 * es, 0.06 * es
    eu = 0.1
    brow_c = pen.dark(rig.hair_color, 0.85)
    for sd in (-1.0, 1.0):
        el = sd * look["gap"]
        anc = rig.face_anchor(pen, eu, el)
        # cheeks (pink when happy / shy / in love)
        n0 = len(pen.faces)
        if not far:                                        # rosy cheeks: always a faint warm blush, stronger when happy / shy
            cu = -0.22 + 0.55 * max(0.0, smile)            # a smile lifts the cheeks (and makes them rounder)
            ck = 1.0 + 1.5 * max(0.0, smile)
            # a soft blush (blood red, not brown): a faint wide glow and a stronger middle, so it has no hard edge
            # (face paint is not lit like skin, so a blush on a calm face reads as a dirty patch: only when it shows)
            for kk, mix_ in (((1.25, 0.06), (0.7, 0.1)) if (pink or smile > 0.15) else ()):
                rig.face_patch(pen, _curve(9, lambda s: (cu + 0.08 * ck * kk * math.sqrt(1 - s * s), el * 1.38 + s * 0.12 * ck * kk)) +
                               _curve(9, lambda s: (cu - 0.07 * ck * kk * math.sqrt(1 - s * s), el * 1.38 - s * 0.12 * ck * kk)),
                               pen.mix(rig.skin, "#e0505a", (2.4 if pink else 1.0) * mix_), lift=0.01)
        rig.layer(pen, anc, n0, 0)
        # the eye: white, iris, pupil, shine
        n0 = len(pen.faces)
        c0 = rig.on_face(eu, el, -0.02)
        white = pen.material("#f8f5ef", roughness=0.9, emission=0.55)
        if not far:                                                # a round, softly lit eyeball
            pen.smooth_ellipsoid(c0[0], c0[1], c0[2], rx=r * rx, ry=r * ry, rz=r * rz, c=white, rings=7, sides=12)
        else:
            pen.ellipsoid(c0[0], c0[1], c0[2], rx=r * rx, ry=r * ry, rz=r * rz, c=white, rings=5, sides=10)
        rig.layer(pen, anc, n0, 1)
        n0 = len(pen.faces)
        if not far and lid < 0.9:                          # the upper lid's soft shadow on the eyeball
            S7 = [-1.0 + 2.0 * i / 6 for i in range(7)]
            rig.face_patch(pen, [(eu + ry * 1.02 * math.sqrt(max(0.0, 1 - s * s)), el + s * rz) for s in S7] +
                           [(eu + ry * (0.45 + 0.5 * lid) * math.sqrt(max(0.0, 1 - s * s)), el + s * rz * 0.95) for s in reversed(S7)],
                           pen.mix("#f8f5ef", rig.skin, 0.45), lift=rx * 0.92)
        rig.layer(pen, anc, n0, 1)
        n0 = len(pen.faces)
        iu, il = eu + max(-0.6, min(0.6, gy)) * ry * 0.35, el + max(-0.6, min(0.6, gx)) * rz * 0.45
        ci = rig.on_face(iu, il, rx * 0.8)
        ir = 0.13 * es * isz
        if not far:                                        # film eyes: a dark ring round the iris, the iris, a lighter
            pen.ellipsoid(ci[0], ci[1], ci[2], rx=r * 0.028, ry=r * ir * 1.06, rz=r * ir * 0.87,   # ring inside it
                          c=pen.dark(look["iris"], 0.45), rings=4, sides=12)
        pen.ellipsoid(ci[0], ci[1], ci[2], rx=r * 0.03, ry=r * ir * (0.9 if not far else 1.0), rz=r * ir * (0.74 if not far else 0.82),
                      c=look["iris"], rings=4, sides=12 if not far else 9)
        if not far:
            cc = rig.on_face(iu, il, rx * 0.8 + 0.01)
            pen.ellipsoid(cc[0], cc[1], cc[2], rx=r * 0.026, ry=r * ir * 0.56, rz=r * ir * 0.46,
                          c=pen.mix(look["iris"], "#f2d8a0", 0.35), rings=3, sides=10)
        rig.layer(pen, anc, n0, 2)
        n0 = len(pen.faces)
        cp = rig.on_face(iu, il, rx * 0.8 + 0.02)
        pu = look.get("pupil", 1.0) * rig.pupil       # bigger in the dark / in fear (char3d.SCENE_DARK)
        pen.ellipsoid(cp[0], cp[1], cp[2], rx=r * 0.025, ry=r * ir * 0.45 * pu, rz=r * ir * 0.37 * pu, c="#0b0808", rings=3,
                      sides=10)
        if not far:                                        # the wet shine: a big soft one and a small sharp one, on the
            hs_ = rig.on_face(iu + ir * 0.42, il + ir * 0.3, rx * 0.8 + 0.05)     # same side for both eyes (one light)
            pen.sphere(hs_[0], hs_[1], hs_[2], r=r * ir * 0.27, c=pen.material("white", emission=1.0), rings=2, sides=8)
            hs2 = rig.on_face(iu - ir * 0.38, il - ir * 0.32, rx * 0.8 + 0.05)
            pen.sphere(hs2[0], hs2[1], hs2[2], r=r * ir * 0.1, c=pen.material("white", emission=1.0), rings=2, sides=6)
        rig.layer(pen, anc, n0, 3)
        # lids: the upper lid comes down (and tilts with the mood), the lower one comes up (smiling squint)
        n0 = len(pen.faces)
        lt = 0.04 if not far else 0.03

        def edge_up(s, L=lid):
            inner = -sd * s
            u = eu + ry * math.sqrt(max(0.0, 1 - s * s)) * (1 - 2 * L)
            u -= max(ltilt, 0) * ry * (0.5 + 0.5 * inner) * 0.9 * (1 - L)
            u -= max(-ltilt, 0) * ry * (0.5 - 0.5 * inner) * 0.9 * (1 - L)
            return u
        top = [(eu + ry * 1.12 * math.sqrt(max(0.0, 1 - s * s)) + 0.012, el + s * rz * 1.08) for s in
               [-1.0 + 2.0 * i / 8 for i in range(9)]]
        bot = [(eu - ry * 1.12 * math.sqrt(max(0.0, 1 - s * s)) - 0.012, el + s * rz * 1.08) for s in
               [-1.0 + 2.0 * i / 8 for i in range(9)]]
        S9 = [-1.0 + 2.0 * i / 8 for i in range(9)]
        if happy_closed:                                   # laughing: happy closed eyes (^ ^)
            rig.face_patch(pen, top + list(reversed(bot)), rig.skin, lift=rx + lt)
            rig.layer(pen, anc, n0, 4)
            n0 = len(pen.faces)
            rig.face_line(pen, [(eu - ry * 0.25 + ry * 0.75 * math.sqrt(max(0, 1 - s * s)), el + s * rz) for s in S9],
                          0.045, ink, lift=rx + lt + 0.01)
            rig.layer(pen, anc, n0, 5)
        else:
            if lid >= 0.97:                                # shut: lid over the whole eye, lashes curve down
                rig.face_patch(pen, top + list(reversed(bot)), rig.skin, lift=rx + lt)
                line = [(eu - ry * 0.15 - ry * 0.3 * math.sqrt(max(0, 1 - s * s)), el + s * rz) for s in S9]
            else:
                if lid > 0.02 or ltilt:
                    edge = [(min(top[i][0], max(eu - ry, edge_up(s))), el + s * rz * 1.08) for i, s in enumerate(S9)]
                    rig.face_patch(pen, top + list(reversed(edge)), rig.skin, lift=rx + lt)
                    line = [(u, el + s * rz) for (u, _), s in zip(edge, S9)]
                else:
                    line = [(eu + ry * math.sqrt(max(0, 1 - s * s)), el + s * rz) for s in S9]
                if low > 0.02:
                    ledge = [(eu - ry * math.sqrt(max(0.0, 1 - s * s)) * (1 - 2 * low), el + s * rz * 1.08) for s in S9]
                    rig.face_patch(pen, list(bot) + list(reversed(ledge)), rig.skin, lift=rx + lt)
            rig.layer(pen, anc, n0, 4)
            n0 = len(pen.faces)
            rig.face_line(pen, line, 0.05 if look.get("lashes") else 0.038, ink, lift=rx + lt + 0.01)
            if look.get("lashes") and not far and lid < 0.97:   # a little flick at the outer corner
                a = line[0] if sd < 0 else line[-1]
                rig.face_line(pen, [a, (a[0] + 0.05, a[1] + sd * 0.06)], 0.035, ink, lift=rx + lt + 0.01)
            rig.layer(pen, anc, n0, 5)
        if not far and lid < 0.95 and not happy_closed:    # the lid crease above the eye
            n0 = len(pen.faces)
            rig.face_line(pen, [(eu + ry * (1.3 - 0.4 * lid) * math.sqrt(max(0.0, 1 - s * s)) + 0.035, el + s * rz * 0.95)
                                for s in [-0.9, -0.45, 0.0, 0.45, 0.9]], 0.016, pen.dark(rig.skin, 0.8), lift=0.045)
            rig.layer(pen, anc, n0, 5)
        # tears
        if rig.face == "crying" and not far:
            n0 = len(pen.faces)
            k = (rig.t * 0.9 + (0.5 if sd > 0 else 0.0)) % 1.0
            p = rig.on_face(eu - ry - 0.05 - 0.45 * k, el + sd * rz * 0.5, 0.06)
            pen.ellipsoid(p[0], p[1], p[2], rx=r * 0.03, ry=r * 0.07, rz=r * 0.045, c="#8fd3ff", rings=3, sides=6)
            rig.layer(pen, anc, n0, 6)
        # eyebrow
        n0 = len(pen.faces)
        up = bup + 0.12 * rig.brow
        if rig.face == "thinking" and sd > 0:
            up += 0.08                                     # one brow up
        bw = 0.055 * look["brows"]
        rig.face_line(pen, [(eu + ry + 0.1 + up + 0.035 * (1 - s * s) + btilt * 0.5 * (-sd * s), el + s * 0.17)
                            for s in [-1.0, -0.5, 0.0, 0.5, 1.0]], bw, brow_c, lift=0.06)
        rig.layer(pen, anc, n0, 7)
    # ---- the middle of the face: mouth, nose, mustache
    if rig.face in ("angry", "disgusted") and not far:   # a nose wrinkle: little creases across the bridge
        ancn = rig.face_anchor(pen, -0.05, 0.0, 0.3)
        n0 = len(pen.faces)
        for k in range(2):
            uu = -0.02 - 0.05 * k
            for sd in (-1.0, 1.0):
                rig.face_line(pen, [(uu + 0.015, sd * 0.03), (uu, sd * 0.075), (uu - 0.018, sd * 0.11)], 0.013,
                              pen.dark(rig.skin, 0.72), lift=0.03)
        rig.layer(pen, ancn, n0, 6)
    anc = rig.face_anchor(pen, -0.3, 0.0, 0.3)
    ms = rig.mouth_shape
    talking = ms["jaw"] > 0.03 or ms["closed"] < 0.5
    w = 0.17 * look["mouth"] * (1.0 + 0.3 * ms["wide"] - 0.4 * ms["round"] - 0.6 * mround) * (1.15 if smile > 0.08 else 1.0)
    h = max(mopen, (0.03 + 0.26 * ms["jaw"]) * (1.0 - 0.9 * ms["closed"]) if talking else 0.0)
    rnd = max(mround, ms["round"])
    sm = smile * (1.0 - 0.5 * rnd)
    um = -0.46
    up_ = lambda s: um + sm * s * s + h * 0.3 * rnd * math.sqrt(max(0, 1 - s * s))
    lo_ = lambda s: um + sm * s * s * max(0.0, 1 - h / 0.12) - h * math.sqrt(max(0.0, 1 - s * s)) ** (0.8 if rnd < 0.5 else 1.0)
    S = [-1.0 + 2.0 * i / 10 for i in range(11)]
    lip = pen.mix(pen.dark(rig.skin, 0.62), "#9a3040", 0.45)
    lk_ = look.get("lips", 1.0) * (0.8 if far else 1.0)
    lip_c = pen.mix(pen.dark(rig.skin, 0.74), "#b04a5a", 0.38 if rig.gender == "female" else 0.2)    # the lips' own colour
    lip_lo = pen.mix(lip_c, "#ffffff", 0.1)                                                    # the lower lip catches light
    tu, tl = 0.026 * lk_, 0.036 * lk_                                                         # upper / lower lip thickness
    bow = lambda s: 1.0 - 0.45 * math.exp(-(s / 0.2) ** 2)                                     # the cupid's bow
    rim = lambda s: math.sqrt(max(0.0, 1.0 - s * s)) ** 0.7
    n0 = len(pen.faces)
    if h < 0.025:                                          # closed: two lips meeting in a soft line
        if not far:
            rig.face_patch(pen, [(up_(s) + tu * rim(s) * bow(s), s * w) for s in S] + [(up_(s), s * w) for s in reversed(S)], lip_c, lift=0.018)
            rig.face_patch(pen, [(up_(s), s * w * 0.97) for s in S] + [(up_(s) - tl * rim(s), s * w * 0.93) for s in reversed(S)], lip_lo, lift=0.018)
        rig.face_line(pen, [(up_(s), s * w) for s in S], 0.02 if not far else 0.035, pen.dark(lip_c, 0.55) if not far else lip, lift=0.022)
        if sm > 0.05 and not far:                          # smiling: little dimples at the corners
            for sd in (-1.0, 1.0):
                rig.face_line(pen, [(up_(sd) + 0.02, sd * w * 1.06), (up_(sd) - 0.025, sd * w * 1.1)], 0.012, pen.dark(rig.skin, 0.75), lift=0.02)
        rig.layer(pen, anc, n0, 1)
    else:
        rig.face_patch(pen, [(up_(s), s * w) for s in S] + [(lo_(s), s * w) for s in reversed(S)], "#4a1016", lift=0.02)
        rig.layer(pen, anc, n0, 1)
        n0 = len(pen.faces)
        th = min(h * 0.4, 0.06)
        if (teeth or ms["teeth"] > 0.2) and h > 0.04:
            if rig.face == "angry":                        # gritted teeth
                th = h * 0.9
            S2 = [s for s in S if abs(s) <= 0.81]
            rig.face_patch(pen, [(up_(s) - 0.004, s * w) for s in S2] +
                           [(max(lo_(s), up_(s) - th), s * w) for s in reversed(S2)], "#f6f2e6", lift=0.025)
        if ms["tongue"] > 0.3 or h > 0.12:
            S3 = [s * 0.55 for s in S]
            rig.face_patch(pen, [(lo_(s) + h * (0.45 if ms["tongue"] > 0.3 else 0.32) * math.sqrt(max(0, 1 - (s / 0.55) ** 2)),
                                  s * w) for s in S3] + [(lo_(s) + 0.006, s * w) for s in reversed(S3)],
                           "#d9606c", lift=0.025)
        rig.layer(pen, anc, n0, 2)
        n0 = len(pen.faces)
        if not far:                                        # lips round the open mouth (upper with its bow, lower fuller)
            if (teeth or ms["teeth"] > 0.2) and h > 0.13:  # wide open: the lower teeth show too
                S4 = [s for s in S if abs(s) <= 0.7]
                rig.face_patch(pen, [(lo_(s) + min(h * 0.22, 0.035), s * w) for s in S4] + [(lo_(s) + 0.004, s * w) for s in reversed(S4)], "#efe9dc", lift=0.026)
            rig.face_patch(pen, [(up_(s) + tu * rim(s) * bow(s), s * w) for s in S] + [(up_(s), s * w) for s in reversed(S)], lip_c, lift=0.03)
            rig.face_patch(pen, [(lo_(s), s * w) for s in S] + [(lo_(s) - tl * rim(s), s * w * 0.95) for s in reversed(S)], lip_lo, lift=0.03)
        else:
            rig.face_line(pen, [(up_(s), s * w) for s in S], 0.022, lip, lift=0.03)
            rig.face_line(pen, [(lo_(s), s * w) for s in S], 0.03, lip, lift=0.03)
        rig.layer(pen, anc, n0, 3)
    # nose
    n0 = len(pen.faces)
    nk = look["nose"]
    nose_c = pen.mix(rig.skin, "#c8505a", 0.07)            # the nose tip is a little warmer (thin skin, blood)
    nw, nl = look.get("nose_w", 1.0), look.get("nose_len", 1.0)      # this person's nose: width, length
    if not far:                                              # a real nose: wings, the bridge, the tip, nostrils
        for sd in (-1.0, 1.0):
            p = rig.on_face(-0.06 - 0.11 * nl, sd * 0.075 * nk * nw, 0.0)
            pen.smooth_ellipsoid(p[0], p[1], p[2], rx=r * 0.07 * nk, ry=r * 0.055 * nk, rz=r * 0.055 * nk * nw, c=nose_c, rings=5, sides=9)
        p = rig.on_face(0.02 - 0.06 * nl, 0.0, 0.0)
        pen.smooth_ellipsoid(p[0], p[1], p[2], rx=r * 0.075 * nk, ry=r * 0.13 * nk * nl, rz=r * 0.055 * nk, c=nose_c, rings=6, sides=9)
        p = rig.on_face(-0.04 - 0.11 * nl, 0.0, 0.05 * nl)
        pen.smooth_ellipsoid(p[0], p[1], p[2], rx=r * 0.09 * nk, ry=r * 0.075 * nk, rz=r * 0.08 * nk * (0.6 + 0.4 * nw), c=nose_c, rings=6, sides=10)
        for sd in (-1.0, 1.0):
            p = rig.on_face(-0.1 - 0.115 * nl, sd * 0.045 * nk * nw, 0.04)
            pen.ellipsoid(p[0], p[1], p[2], rx=r * 0.012, ry=r * 0.014 * nk, rz=r * 0.024 * nk, c=pen.dark(rig.skin, 0.45), rings=2, sides=6)
        # (a real 3D nose: sorted by depth like the head, so it shows in profile too - not painted on the face)
    else:
        p = rig.on_face(-0.13, 0.0, 0.0)
        pen.ellipsoid(p[0], p[1], p[2], rx=r * 0.14 * nk, ry=r * 0.11 * nk, rz=r * 0.12 * nk, c=pen.dark(rig.skin, 0.93),
                      rings=4, sides=8)
        rig.layer(pen, anc, n0, 4)
    if rig.show("mustache") and rig.mustache:
        n0 = len(pen.faces)
        p = rig.on_face(-0.3, 0.0, 0.03)
        pen.ellipsoid(p[0], p[1], p[2], rx=r * 0.08, ry=r * 0.055, rz=r * 0.3, c=rig.hair_color, rings=3, sides=8)
        if _close(pen, rig):                           # close up: the moustache in small clumps
            for sd in (-1.0, 1.0):
                for k in range(3):
                    _lock(pen, rig, (1.0, -0.36, sd * (0.04 + 0.09 * k)), (0.1, -0.5, sd * 1.0), 0.16, r * 0.045,
                          _shade(pen, rig.hair_color, k), sway=0.0, hang=0.6)
        rig.layer(pen, anc, n0, 5)
    # ---- lines of the face: smile lines (deeper with age), forehead lines and crow's feet for older people
    if not far:
        old_k = look.get("age_lines", 0.0)
        n0 = len(pen.faces)
        line_c = pen.dark(rig.skin, 0.8 if old_k else 0.93)
        if old_k or (sm > 0.1 and not rig.child):           # children have no smile lines; adults only in a big smile
            for sd in (-1.0, 1.0):                         # a soft curve from the nose wing round to the mouth corner
                a0, a1 = (-0.2, 0.13 * nw), (-0.5, w + 0.06)
                pts_ = []
                for i in range(5):
                    q = i / 4.0
                    bulge = 0.035 * math.sin(math.pi * q)
                    pts_.append((a0[0] + (a1[0] - a0[0]) * q, sd * (a0[1] + (a1[1] - a0[1]) * q + bulge)))
                rig.face_line(pen, pts_, 0.013 if old_k else 0.007, line_c, lift=0.025)
        rig.layer(pen, anc, n0, 6)
        if old_k:
            fa = rig.face_anchor(pen, 0.55, 0.0)
            n0 = len(pen.faces)
            if rig.hair in ("bald", "bald_sides", "none") or not rig.show("hair"):   # the forehead (only where no hair covers it)
                for i in range(3):
                    u0 = 0.5 + 0.075 * i
                    rig.face_line(pen, [(u0 + 0.02 * (1 - q * q), q * 0.3) for q in (-1.0, -0.5, 0.0, 0.5, 1.0)], 0.011, line_c, lift=0.03)
            for sd in (-1.0, 1.0):                         # crow's feet at the outer eye corners
                el_ = sd * look["gap"]
                for k in (-1, 0, 1):
                    a = rig.on_face(0.1 + 0.035 * k, el_ + sd * 0.17, 0.0)
                    rig.face_line(pen, [(0.1 + 0.03 * k, el_ + sd * 0.19), (0.1 + 0.07 * k, el_ + sd * 0.27)], 0.009, line_c, lift=0.03)
            rig.layer(pen, fa, n0, 1)
