KIND = "animal3d"
FOR = "bird"
DESCRIPTION = "the normal 3D bird - every bird uses this unless it has its own file (change it = change them all)"
PREVIEW = {"species": "parrot"}

# rig.b = body size, rig.head_r, rig.y0 = body height above the ground, rig.flying (True in the air)
# colours: rig.fur rig.belly rig.wing rig.head_color rig.beak_color   rig.beak_len   rig.sp (tail_long, comb, crest ...)
# x = forward, y = up, z = to the side.  t = time (wings flap with it)


def draw(pen, rig, t, state):
    b, hr, y0 = rig.b, rig.head_r, rig.y0
    if rig.show("legs") and not rig.flying:
        for side in (-1, 1):
            pen.tube([(0, 0, side * b * 0.25), (0, y0 - b * 0.4, side * b * 0.25)], max(1.2, b * 0.05),
                     c="#d98c33", sides=4, smooth=False)
    if rig.show("body"):
        pen.ellipsoid(0, y0, 0, rx=b * 0.8, ry=b * 0.55, rz=b * 0.5, c=rig.fur, rings=6, sides=10)
        pen.ellipsoid(b * 0.15, y0 - b * 0.15, 0, rx=b * 0.55, ry=b * 0.38, rz=b * 0.42, c=rig.belly, rings=4, sides=8)
    hx, hy = b * 0.75, y0 + b * 0.45
    if rig.show("head"):
        pen.sphere(hx, hy, 0, r=hr, c=rig.head_color, rings=5, sides=9)
        pen.push()                                                  # the beak points forward
        pen.move(hx + hr * 0.8, hy - hr * 0.1, 0)
        pen.rotate_z(-90)
        pen.cone(0, 0, 0, r=hr * 0.32, h=rig.beak_len, c=rig.beak_color, sides=6)
        pen.pop()
        for side in (-1, 1):
            pen.sphere(hx + hr * 0.45, hy + hr * 0.25, side * hr * 0.7, r=hr * 0.16, c="#0d0d0d", rings=3, sides=5)
        if rig.sp.get("comb"):
            pen.ellipsoid(hx, hy + hr * 0.95, 0, rx=hr * 0.5, ry=hr * 0.35, rz=hr * 0.1, c="#d62828", rings=3, sides=6)
    if rig.show("wings"):
        flap = math.sin(t * 2 * math.pi * 4.5) if rig.flying else -0.9
        for side in (-1, 1):
            tipz = side * (b * 0.4 + b * 1.4 * math.cos(flap * 0.9))
            tipy = y0 + b * 0.2 + b * 1.1 * math.sin(flap * 0.9)
            pen.poly([(0.0, y0 + b * 0.2, side * b * 0.4), (b * 0.45, y0 + b * 0.2, side * b * 0.4), (b * 0.1, tipy, tipz),
                      (-b * 0.5, tipy - b * 0.1, tipz * 0.8)], rig.wing)
    if rig.show("tail"):
        pen.poly([(-b * 0.6, y0, -b * 0.12), (-b * 0.6, y0, b * 0.12),
                  (-b * (1.6 if rig.sp.get("tail_long") else 1.15), y0 - b * 0.1, 0)], rig.wing)
