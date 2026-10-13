KIND = "animal3d"
FOR = "quadruped"
DESCRIPTION = "the normal 3D four-legged animal - every animal uses this unless it has its own file (change it = change them all)"
PREVIEW = {"species": "tiger"}

# The engine hands you a posed skeleton: rig. Everything you draw moves with every action (walk, run, sit, roar ...).
#   x = forward (where the animal looks), y = up, z = to the side.  An adult person is about 300 tall.
#   rig.legs() -> [(top, knee, paw, "front"|"middle"|"back"|"arm", side), ...] (0-8 legs, by the planet)   rig.along(f) -> a point on the spine
#        (f = 0 at the hips, 1 at the shoulders; below 0 / above 1 goes past them)
#   rig.neck_base  rig.neck_end  rig.head (middle)  rig.head_r  rig.fwd (where the face looks)
#   rig.face_point(forward, up, side) -> a point on the head (units of the head size)
#   rig.g = body thickness (radius)   rig.lat = how far apart the legs are   rig.legw = leg radius
#   colours: rig.fur rig.belly rig.dark rig.leg_color rig.hoof rig.muzzle rig.mane rig.color("#hex")
#   the species settings: rig.species, rig.sp (pattern, ears, tail, horns, trunk, tusks, hump, snout ...)
#   now: rig.tail rig.wag rig.jaw rig.trunk (pose angles), rig.mouth, rig.blink   rig.show("ears") = False when hidden


def draw(pen, rig, t, state):
    sp, g, hr = rig.sp, rig.g, rig.head_r
    # ---------------- legs + paws / hooves
    if rig.show("legs"):
        for top, knee, paw, end, side in rig.legs():
            w = rig.legw * (0.5 if end == "arm" else 0.65 if sp.get("legs", 4) >= 6 else 1.0)   # arms and many legs: thinner
            pen.tube([top, knee, paw], [w * 1.35, w, w * 0.85], c=rig.leg_color, sides=7, smooth=False)
            if end == "arm":
                pen.sphere(paw[0], paw[1], paw[2], r=w * 1.1, c=rig.leg_color, rings=3, sides=6)
                continue
            pen.ellipsoid(paw[0] + w * 0.3, paw[1] + w * 0.5, paw[2], rx=w * 1.2, ry=w * 0.6, rz=w * 1.05,
                          c=rig.hoof, rings=3, sides=6)
    # ---------------- body + belly
    if rig.show("body"):
        pts = [rig.along(f) for f in (-0.12, 0.2, 0.55, 0.85, 1.08)]
        pen.tube(pts, [g * 0.55, g * 0.95, g, g * 0.95, g * 0.6], c=rig.fur, sides=12, smooth=True)
        m = rig.along(0.5)
        pen.ellipsoid(m[0], m[1] - g * 0.45, 0, rx=rig.length * 0.42, ry=g * 0.55, rz=g * 0.75, c=rig.belly,
                      rings=4, sides=9)
        if sp.get("hump"):
            pen.sphere(m[0], m[1] + g * 0.8, 0, r=g * 0.6, c=rig.fur, rings=4, sides=8)
    # ---------------- stripes and spots
    pat = sp.get("pattern")
    if rig.show("pattern") and pat in ("stripes", "zebra", "stripes_light"):
        col = rig.color(sp.get("stripe_color", "#161616")) if pat == "zebra" else \
            (rig.dark if pat == "stripes_light" else "#291a0f")
        for k, f in enumerate((0.12, 0.26, 0.4, 0.54, 0.68, 0.82)):
            p = rig.along(f)
            ln = 0.55 + 0.15 * (k % 2)
            for side in (-1, 1):                                  # down the flanks
                pen.ellipsoid(p[0], p[1] + g * 0.25, side * g * 0.9, rx=g * 0.07, ry=g * ln, rz=g * 0.16, c=col,
                              rings=3, sides=6)
            pen.ellipsoid(p[0], p[1] + g * 0.93, 0, rx=g * 0.07, ry=g * 0.14, rz=g * 0.55, c=col, rings=3, sides=6)
    elif rig.show("pattern") and pat in ("spots", "leopard", "giraffe", "patches", "panda"):
        col = {"spots": "white", "giraffe": "#8c4a1c", "panda": "#1a1a1a", "patches": "#26211f"}.get(pat, "#1f140c")
        size = 0.12 if pat in ("spots", "leopard") else 0.22
        for k in range(9 if pat != "panda" else 2):
            p = rig.along(0.15 + 0.7 * ((k * 37) % 9) / 9.0)
            up = 0.35 + 0.4 * ((k * 53) % 7) / 7.0
            for side in (-1, 1):
                pen.sphere(p[0], p[1] + g * up, side * g * math.sqrt(max(0.0, 1 - up * up)) * 0.97, r=g * size,
                           c=col, rings=3, sides=6, squash=0.5)
    # ---------------- neck, mane, head
    nb, ne, hd = rig.neck_base, rig.neck_end, rig.head
    if rig.show("neck"):
        pen.tube([nb, ne], [rig.neck_w * 1.05, rig.neck_w * 0.85], c=rig.fur, sides=10, smooth=False)
    if rig.show("mane") and rig.mane and rig.species in ("horse", "zebra", "donkey"):
        pen.tube([(nb[0] - rig.neck_w * 0.2, nb[1] + rig.neck_w * 0.9, 0),
                  (ne[0] - rig.neck_w * 0.3, ne[1] + rig.neck_w * 0.7, 0)], rig.neck_w * 0.35, c=rig.mane,
                 sides=6, smooth=False)
    if rig.show("mane") and rig.mane and rig.species == "lion":
        p = rig.face_point(-0.25, 0, 0)
        pen.sphere(p[0], p[1], p[2], r=hr * 1.55, c=rig.mane, rings=6, sides=12)
    if rig.show("head"):
        pen.sphere(hd[0], hd[1], 0, r=hr, c=rig.fur, rings=6, sides=12)
        sl, sw = rig.snout
        if sl > 1:                                                 # the snout, with a nose at the tip
            tip = rig.face_point(0.75 + sl / hr * 0.6, 0, 0)
            pen.tube([rig.face_point(0.55, 0, 0), tip], [sw * 0.55, sw * 0.45], c=rig.muzzle, sides=9, smooth=False)
            pen.sphere(tip[0] + rig.fwd[0] * sw * 0.35, tip[1] + rig.fwd[1] * sw * 0.35 + sw * 0.1, 0, r=sw * 0.22,
                       c="#1f1414", rings=3, sides=6)
            jaw = max(rig.mouth_shape["jaw"] * (1.0 - rig.mouth_shape["closed"]), rig.jaw / 20.0)
            if jaw > 0.1:                                          # talking / roar / bark: the mouth opens
                pen.ellipsoid(tip[0] - rig.fwd[0] * sw * 0.2, tip[1] - sw * 0.4, 0, rx=sw * 0.4,
                              ry=sw * (0.12 + 0.3 * jaw), rz=sw * (0.35 - 0.12 * rig.mouth_shape["round"]),
                              c="#801a1f", rings=3, sides=7)
        for side in (-1, 1):                                       # eyes
            p = rig.face_point(0.55, 0.35, 0)
            pen.sphere(p[0] + rig.fwd[1] * hr * 0.25, p[1], side * hr * 0.55, r=hr * (0.06 if rig.blink else 0.16),
                       c="#140f0c", rings=3, sides=6)
    # ---------------- ears, horns, antlers
    ears = sp.get("ears", "round")
    back = rig.face_point(-0.2, 0.85, 0)
    if rig.show("ears"):
        for side in (-1, 1):
            z = side * hr * 0.6
            if ears in ("pointy", "pointy_tall"):
                pen.cone(back[0], back[1] - hr * 0.2, z, r=hr * 0.3, h=hr * (0.7 if ears == "pointy" else 1.0),
                         c=rig.fur, sides=5)
            elif ears == "long":
                pen.tube([(back[0], back[1] - hr * 0.1, z * 0.6), (back[0] - hr * 0.3, back[1] + hr * 1.6, z * 0.8)],
                         [hr * 0.22, hr * 0.14], c=rig.fur, sides=6, smooth=False)
            elif ears == "huge":
                p = rig.face_point(-0.3, 0.1, 0)
                pen.ellipsoid(p[0], p[1], side * hr * 0.95, rx=hr * 0.7, ry=hr * 0.85, rz=hr * 0.12,
                              c=pen.dark(rig.fur, 0.92), rings=5, sides=9)
            elif ears in ("floppy", "side"):
                pen.ellipsoid(back[0], back[1] - hr * 0.55, side * hr * 0.95, rx=hr * 0.25,
                              ry=hr * (0.45 if ears == "floppy" else 0.18), rz=hr * 0.1, c=pen.dark(rig.fur, 0.85),
                              rings=3, sides=6)
            else:
                pen.sphere(back[0], back[1], z, r=hr * 0.3, c=rig.fur, rings=3, sides=7, squash=0.6)
    horns = sp.get("horns")
    if rig.show("horns") and (horns or sp.get("antlers")):
        for side in (-1, 1):
            b0 = (back[0] + rig.fwd[0] * hr * 0.2, back[1] + hr * 0.05, side * hr * 0.35)
            if sp.get("antlers"):
                p1 = (b0[0] - hr * 0.2, b0[1] + hr * 1.2, side * hr * 0.8)
                pen.tube([b0, p1], hr * 0.08, c="#735433", sides=5, smooth=False)
                pen.tube([rig.mix(b0, p1, 0.5), (b0[0] + hr * 0.3, b0[1] + hr * 1.0, side * hr * 0.6)], hr * 0.06,
                         c="#735433", sides=5, smooth=False)
            elif horns == "curved":
                pen.tube([b0, (b0[0] - hr * 0.4, b0[1] + hr * 0.5, side * hr * 0.7),
                          (b0[0] - hr * 0.2, b0[1] + hr * 0.2, side * hr * 1.0)], [hr * 0.12, hr * 0.08, hr * 0.04],
                         c="#d9ccb3", sides=5)
            else:
                pen.cone(b0[0], b0[1], b0[2], r=hr * 0.1, h=hr * 0.45, c="#e6dbc2", sides=5)
    # ---------------- elephant trunk and tusks
    if rig.show("trunk") and sp.get("trunk"):
        p0 = rig.face_point(0.8, -0.1, 0)
        pts = [p0]
        ang = -1.35 + math.radians(rig.trunk)
        x, y = p0[0], p0[1]
        for k in range(4):
            x += math.cos(ang) * hr * 0.5
            y += math.sin(ang) * hr * 0.5
            pts.append((x, y, 0))
            ang += 0.25 + math.radians(rig.trunk) * 0.2
        pen.tube(pts, [hr * 0.3, hr * 0.24, hr * 0.19, hr * 0.14, hr * 0.1], c=rig.fur, sides=8)
        if sp.get("tusks"):
            for side in (-1, 1):
                a = (p0[0], p0[1] - hr * 0.1, side * hr * 0.35)
                pen.tube([a, (a[0] + hr * 0.5, a[1] - hr * 0.35, a[2]), (a[0] + hr * 0.75, a[1] - hr * 0.1, a[2])],
                         [hr * 0.09, hr * 0.06, hr * 0.03], c="#f7f2e0", sides=5)
    # ---------------- tail
    if rig.show("tail"):
        kind = sp.get("tail")
        tl = {"long": 1.0, "long_up": 0.8, "bushy": 0.8, "tuft": 0.75, "tuft_thin": 0.5, "long_hair": 0.8,
              "curve": 0.6, "short_up": 0.2, "puff": 0.1, "curly": 0.25}.get(kind, 0.5) * rig.length * 1.0
        ta, wag = math.radians(rig.tail), math.radians(rig.wag)
        root = rig.along(-0.05)
        root = (root[0] - g * 0.4, root[1] + g * 0.35, 0)
        pts = [root]
        hang = kind in ("long_hair", "tuft", "tuft_thin")          # horses, cows, elephants: tails hang down
        for k in range(1, 4):
            f = k / 3.0
            if hang:
                pts.append((root[0] - tl * 0.25 * f, root[1] - tl * f * 0.95, tl * f * math.sin(wag) * 0.4))
            else:
                pts.append((root[0] - tl * f * math.cos(ta * 0.8), root[1] + tl * f * (math.sin(ta) - 0.35 * f),
                            tl * f * math.sin(wag) * 0.6))
        tw = g * (0.28 if kind in ("bushy", "long_hair") else 0.1)
        if tl > 5:
            pen.tube(pts, [tw, tw, tw * 0.8, tw * 0.5], c=rig.dark if kind == "long_hair" else rig.fur, sides=6)
        end = pts[-1]
        if kind in ("tuft", "tuft_thin") or sp.get("tail_tip"):
            pen.sphere(end[0], end[1], end[2], r=g * 0.16, c=rig.tail_tip, rings=3, sides=6)
        if kind == "puff":
            pen.sphere(end[0], end[1], end[2], r=g * 0.3, c="white", rings=3, sides=7)
