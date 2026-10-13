"""Classic thin-line stickman renderer (style: "classic")."""
import math

import cairo

from .poses import BONES, SHOULDER_DROP
from .util import hex_to_rgb, darker, lighter, rotate, dirv, clamp, TAU, stable_hash
from .character import solve



# ---------------------------------------------------------------------------- drawing
def _line(ctx, pts, width, color, alpha):
    ctx.set_source_rgba(*color, alpha)
    ctx.set_line_width(width)
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.stroke()


def draw_classic(ctx, cdef, pose, x, facing, face="neutral", mouth=0.0, t=0.0,
                   extras=None, alpha=1.0, blink=False, seat=False):
    """Draw in WORLD coordinates (the context is already y-up). Returns key world points."""
    extras = extras or {}
    s = cdef.scale
    from .character import body_of
    J = solve(pose, s, BONES["head_r"], body_of(cdef))
    f = -1.0 if facing < 0 else 1.0

    def W(p):
        return (x + f * p[0], p[1])

    col = cdef.color
    far_col = lighter(col, 0.35)
    lw = 7.0 * s * cdef.thickness
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    if seat:
        _draw_stool(ctx, W(J["hip"]), s, alpha)

    # cape goes behind everything
    if cdef.outfit == "cape":
        sway = 6 * math.sin(TAU * 0.7 * t)
        shp, hp = W(J["sh"]), W(J["hip"])
        ctx.set_source_rgba(*cdef.accent, alpha * 0.95)
        ctx.move_to(*shp)
        ctx.line_to(shp[0] - f * 10 * s, shp[1])
        ctx.line_to(hp[0] - f * (52 + sway) * s, hp[1] - 18 * s)
        ctx.line_to(hp[0] - f * 8 * s, hp[1] - 10 * s)
        ctx.close_path()
        ctx.fill()

    # far limbs
    _line(ctx, [W(J["hip"]), W(J["kf"]), W(J["ff"]), W(J["toe_f"])], lw * 0.92, far_col, alpha)
    _line(ctx, [W(J["sh"]), W(J["ef"]), W(J["hf"])], lw * 0.92, far_col, alpha)
    # body
    if cdef.outfit == "dress":
        ctx.set_source_rgba(*cdef.accent, alpha)
        ctx.move_to(*W(J["waist"]))
        ctx.line_to(*W(J["skirt_l"]))
        ctx.line_to(*W(J["skirt_r"]))
        ctx.close_path()
        ctx.fill_preserve()
        ctx.set_source_rgba(*darker(cdef.accent, 0.7), alpha)
        ctx.set_line_width(lw * 0.4)
        ctx.stroke()
    _line(ctx, [W(J["hip"]), W(J["neck"])], lw, col, alpha)
    if cdef.outfit == "tie":
        a = J["neck"]
        b = (J["neck"][0] * 0.62 + J["hip"][0] * 0.38, J["neck"][1] * 0.62 + J["hip"][1] * 0.38)
        _line(ctx, [W(a), W(b)], lw * 0.8, cdef.accent, alpha)
    _line(ctx, [W(J["hip"]), W(J["kn"]), W(J["fn"]), W(J["toe_n"])], lw, col, alpha)

    # head
    hx, hy = W(J["head"])
    r = BONES["head_r"] * s
    head_ang = pose.get("rot", 0.0) - pose["torso"] - pose["head"]
    ctx.save()
    ctx.translate(hx, hy)
    ctx.scale(f, 1)
    ctx.rotate(math.radians(head_ang))
    _draw_hair_back(ctx, cdef, r, alpha, lw)
    ctx.arc(0, 0, r, 0, TAU)
    ctx.set_source_rgba(*cdef.head_fill, alpha)
    ctx.fill_preserve()
    ctx.set_source_rgba(*col, alpha)
    ctx.set_line_width(lw)
    ctx.stroke()
    _draw_face(ctx, cdef, r, face, mouth, blink, alpha, lw)
    _draw_head_top(ctx, cdef, r, alpha, lw)
    ctx.restore()

    # near arm on top
    _line(ctx, [W(J["sh"]), W(J["en"]), W(J["hn"])], lw, col, alpha)
    hand = W(J["hn"])
    ctx.set_source_rgba(*col, alpha)
    ctx.arc(hand[0], hand[1], lw * 0.75, 0, TAU)
    ctx.fill()

    # effects
    if extras.get("tears"):
        eye = rotate((0.42 * r, 0.12 * r), head_ang)
        ex, ey = hx + f * eye[0], hy + eye[1]
        ctx.set_source_rgba(0.35, 0.65, 1.0, alpha * 0.9)
        for k in range(3):
            ph = (t * 1.6 + k / 3.0) % 1.0
            dy = ph * 60 * s
            ctx.arc(ex + f * 6 * s, ey - dy, (4.2 - 2 * ph) * s, 0, TAU)
            ctx.fill()
    if extras.get("zzz"):
        for k in range(3):
            ph = (t * 0.45 + k / 3.0) % 1.0
            ctx.save()
            ctx.translate(hx + f * (20 + 40 * ph) * s, hy + (30 + 90 * ph) * s)
            ctx.scale(1, -1)
            ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size((18 + 22 * ph) * s)
            ctx.set_source_rgba(*col, alpha * (1 - ph))
            ctx.move_to(0, 0)
            ctx.show_text("Z")
            ctx.restore()
    return {"hand": hand, "head": (hx, hy), "hip": W(J["hip"]), "head_r": r}


def _draw_stool(ctx, hip, s, alpha):
    h = hip[1] - 4 * s
    if h < 10:
        return
    wood, dark = (0.62, 0.42, 0.25), (0.42, 0.27, 0.15)
    ctx.set_source_rgba(*wood, alpha)
    ctx.rectangle(hip[0] - 30 * s, h - 9 * s, 60 * s, 9 * s)
    ctx.fill()
    ctx.set_source_rgba(*dark, alpha)
    ctx.set_line_width(6 * s)
    for dx in (-22, 22):
        ctx.move_to(hip[0] + dx * s, h - 9 * s)
        ctx.line_to(hip[0] + dx * 1.15 * s, 0)
        ctx.stroke()


def _draw_face(ctx, cdef, r, face, mouth, blink, alpha, lw):
    col = cdef.color
    ctx.set_source_rgba(*col, alpha)
    e1, e2 = (0.14 * r, 0.16 * r), (0.56 * r, 0.16 * r)
    ew = lw * 0.5
    ctx.set_line_width(ew)
    closed = blink or face in ("sleeping",)
    if face in ("laughing",):
        for ex, ey in (e1, e2):         # ^ ^
            ctx.move_to(ex - 0.12 * r, ey - 0.02 * r)
            ctx.line_to(ex, ey + 0.1 * r)
            ctx.line_to(ex + 0.12 * r, ey - 0.02 * r)
            ctx.stroke()
    elif face == "crying":
        for ex, ey in (e1, e2):
            ctx.move_to(ex - 0.12 * r, ey + 0.05 * r)
            ctx.line_to(ex + 0.12 * r, ey - 0.02 * r)
            ctx.stroke()
    elif closed:
        for ex, ey in (e1, e2):
            ctx.move_to(ex - 0.11 * r, ey)
            ctx.curve_to(ex - 0.05 * r, ey - 0.07 * r, ex + 0.05 * r, ey - 0.07 * r, ex + 0.11 * r, ey)
            ctx.stroke()
    else:
        er = 0.13 * r if face in ("surprised", "scared") else 0.095 * r
        for ex, ey in (e1, e2):
            ctx.arc(ex, ey, er, 0, TAU)
            ctx.fill()

    # brows
    if face in ("angry", "sad", "crying", "surprised", "scared", "thinking"):
        by = 0.42 * r
        ctx.set_line_width(ew)
        for ex, _ in (e1, e2):
            if face == "angry":
                inner = ex + (0.15 * r if ex < 0.3 * r else -0.15 * r)
                ctx.move_to(ex - 0.14 * r if ex < 0.3 * r else ex + 0.14 * r, by + 0.07 * r)
                ctx.line_to(inner, by - 0.05 * r)
            elif face in ("sad", "crying", "scared"):
                ctx.move_to(ex - 0.13 * r if ex < 0.3 * r else ex + 0.13 * r, by - 0.05 * r)
                ctx.line_to(ex + (0.1 * r if ex < 0.3 * r else -0.1 * r), by + 0.05 * r)
            elif face == "thinking":
                if ex > 0.3 * r:
                    ctx.move_to(ex - 0.12 * r, by + 0.02 * r)
                    ctx.line_to(ex + 0.12 * r, by + 0.1 * r)
                else:
                    continue
            else:
                ctx.move_to(ex - 0.13 * r, by + 0.05 * r)
                ctx.curve_to(ex - 0.05 * r, by + 0.12 * r, ex + 0.05 * r, by + 0.12 * r, ex + 0.13 * r, by + 0.05 * r)
            ctx.stroke()

    # mouth
    mx, my = 0.38 * r, -0.38 * r
    mw = 0.36 * r
    ctx.set_line_width(ew)
    if cdef.mustache:
        ctx.move_to(mx - 0.22 * r, my + 0.14 * r)
        ctx.line_to(mx + 0.22 * r, my + 0.14 * r)
        ctx.set_line_width(ew * 1.6)
        ctx.stroke()
        ctx.set_line_width(ew)
    if mouth > 0.06:
        h = (0.06 + 0.34 * mouth) * r
        ctx.save()
        ctx.translate(mx, my)
        ctx.scale(mw * 0.55, h)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(*darker(col, 0.6), alpha)
        ctx.fill()
        return
    if face in ("laughing",):
        ctx.move_to(mx - mw * 0.7, my + 0.06 * r)
        ctx.line_to(mx + mw * 0.7, my + 0.06 * r)
        ctx.curve_to(mx + mw * 0.7, my - 0.3 * r, mx - mw * 0.7, my - 0.3 * r, mx - mw * 0.7, my + 0.06 * r)
        ctx.close_path()
        ctx.fill()
    elif face in ("surprised", "scared"):
        ctx.arc(mx, my, 0.1 * r if face == "surprised" else 0.07 * r, 0, TAU)
        ctx.stroke()
    elif face in ("sad", "crying"):
        ctx.move_to(mx - mw / 2, my - 0.08 * r)
        ctx.curve_to(mx - mw / 4, my + 0.06 * r, mx + mw / 4, my + 0.06 * r, mx + mw / 2, my - 0.08 * r)
        ctx.stroke()
    elif face == "angry":
        ctx.move_to(mx - mw / 2, my - 0.03 * r)
        ctx.curve_to(mx - mw / 4, my + 0.03 * r, mx + mw / 4, my + 0.03 * r, mx + mw / 2, my - 0.03 * r)
        ctx.stroke()
    elif face in ("sleeping", "thinking"):
        ctx.move_to(mx - mw / 3, my)
        ctx.line_to(mx + mw / 3, my - (0.03 * r if face == "thinking" else 0))
        ctx.stroke()
    else:  # neutral / happy
        depth = 0.16 * r if face == "happy" else 0.08 * r
        ctx.move_to(mx - mw / 2, my + 0.04 * r)
        ctx.curve_to(mx - mw / 4, my - depth, mx + mw / 4, my - depth, mx + mw / 2, my + 0.04 * r)
        ctx.stroke()


def _draw_hair_back(ctx, cdef, r, alpha, lw):
    hair = cdef.hair
    col = cdef.color
    ctx.set_source_rgba(*col, alpha)
    if hair == "long":
        ctx.move_to(0.3 * r, 0.9 * r)
        ctx.curve_to(-1.2 * r, 1.3 * r, -1.35 * r, -0.4 * r, -0.95 * r, -1.45 * r)
        ctx.line_to(-0.55 * r, -1.25 * r)
        ctx.curve_to(-0.8 * r, -0.4 * r, -0.7 * r, 0.5 * r, 0.3 * r, 0.9 * r)
        ctx.fill()
    elif hair == "ponytail":
        ctx.arc(-1.05 * r, 0.35 * r, 0.28 * r, 0, TAU)
        ctx.fill()
        ctx.move_to(-1.1 * r, 0.3 * r)
        ctx.curve_to(-1.6 * r, 0.0, -1.5 * r, -0.7 * r, -1.25 * r, -1.0 * r)
        ctx.set_line_width(lw * 1.6)
        ctx.stroke()
    elif hair == "bun":
        ctx.arc(-0.55 * r, 0.95 * r, 0.36 * r, 0, TAU)
        ctx.fill()


def _draw_head_top(ctx, cdef, r, alpha, lw):
    col, acc = cdef.color, cdef.accent
    hair, hat = cdef.hair, cdef.hat
    ctx.set_source_rgba(*col, alpha)
    if hair in ("long", "ponytail", "bun", "short") and hat in ("none", None, "bow"):
        # fringe cap of hair on top of the skull
        ctx.arc(0, 0, r * 1.02, math.radians(35), math.radians(200))
        ctx.curve_to(-0.5 * r, 0.25 * r, 0.1 * r, 0.55 * r, 0.83 * r, 0.6 * r)
        ctx.close_path()
        ctx.fill()
    elif hair == "spiky" and hat in ("none", None):
        ctx.set_line_width(lw * 0.8)
        for k in range(6):
            a = math.radians(45 + k * 24)
            ctx.move_to(math.cos(a) * r, math.sin(a) * r)
            ctx.line_to(math.cos(a) * r * 1.45, math.sin(a) * r * 1.45)
        ctx.stroke()
    elif hair == "curly" and hat in ("none", None):
        for k in range(7):
            a = math.radians(30 + k * 22)
            ctx.arc(math.cos(a) * r * 1.05, math.sin(a) * r * 1.05, 0.22 * r, 0, TAU)
            ctx.fill()

    if hat == "cap":
        ctx.set_source_rgba(*acc, alpha)
        ctx.arc(-0.05 * r, 0.42 * r, r * 0.97, math.radians(-8), math.radians(188))
        ctx.close_path()
        ctx.fill()
        ctx.rectangle(0.3 * r, 0.34 * r, 0.95 * r, 0.14 * r)
        ctx.fill()
    elif hat == "top":
        ctx.set_source_rgba(*darker(col, 0.8), alpha)
        ctx.rectangle(-1.05 * r, 0.75 * r, 2.1 * r, 0.18 * r)
        ctx.fill()
        ctx.rectangle(-0.72 * r, 0.9 * r, 1.44 * r, 1.1 * r)
        ctx.fill()
        ctx.set_source_rgba(*acc, alpha)
        ctx.rectangle(-0.72 * r, 0.92 * r, 1.44 * r, 0.2 * r)
        ctx.fill()
    elif hat == "crown":
        ctx.set_source_rgba(0.95, 0.75, 0.15, alpha)
        ctx.move_to(-0.7 * r, 0.75 * r)
        for k, (px, py) in enumerate([(-0.7, 1.45), (-0.35, 1.05), (0, 1.55), (0.35, 1.05), (0.7, 1.45), (0.7, 0.75)]):
            ctx.line_to(px * r, py * r)
        ctx.close_path()
        ctx.fill()
    elif hat == "bow":
        ctx.set_source_rgba(*acc, alpha)
        cx, cy = -0.45 * r, 0.95 * r
        ctx.move_to(cx, cy)
        ctx.line_to(cx - 0.5 * r, cy + 0.3 * r)
        ctx.line_to(cx - 0.5 * r, cy - 0.3 * r)
        ctx.close_path()
        ctx.move_to(cx, cy)
        ctx.line_to(cx + 0.5 * r, cy + 0.3 * r)
        ctx.line_to(cx + 0.5 * r, cy - 0.3 * r)
        ctx.close_path()
        ctx.fill()
        ctx.arc(cx, cy, 0.14 * r, 0, TAU)
        ctx.fill()
    elif hat == "turban":
        ctx.set_source_rgba(*acc, alpha)
        ctx.arc(0, 0.2 * r, r * 1.08, math.radians(-5), math.radians(185))
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgba(*darker(acc, 0.75), alpha)
        ctx.set_line_width(lw * 0.45)
        for k in range(3):
            ctx.move_to(-0.95 * r, (0.35 + 0.25 * k) * r)
            ctx.curve_to(-0.3 * r, (0.7 + 0.25 * k) * r, 0.3 * r, (0.5 + 0.2 * k) * r, 0.95 * r, (0.3 + 0.2 * k) * r)
        ctx.stroke()

    if cdef.glasses:
        ctx.set_source_rgba(*col, alpha)
        ctx.set_line_width(lw * 0.45)
        for ex in (0.14 * r, 0.56 * r):
            ctx.arc(ex, 0.16 * r, 0.2 * r, 0, TAU)
            ctx.stroke()
        ctx.move_to(0.34 * r, 0.18 * r)
        ctx.line_to(0.36 * r, 0.18 * r)
        ctx.stroke()
    if cdef.beard:
        ctx.set_source_rgba(*col, alpha)
        ctx.move_to(-0.3 * r, -0.2 * r)
        ctx.curve_to(-0.2 * r, -1.2 * r, 0.9 * r, -1.1 * r, 0.9 * r, -0.2 * r)
        ctx.curve_to(0.7 * r, -0.55 * r, 0.05 * r, -0.55 * r, -0.3 * r, -0.2 * r)
        ctx.fill()
