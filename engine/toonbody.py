"""🎨 The 2.5D toon body (engine/character.py draws a "toon" person with these; 3D and the other styles never do):
shaped like a TV cartoon, not a stickman -

    limbs     tapered: thick at the shoulder / hip, slimmer at the wrist / ankle (a real arm or leg narrows the same
              way), one bold ink line round the whole limb
    hands     a mitten with a thumb, turned along the forearm
    feet      a rounded shoe pointing forward, the sole a shade darker
    torso     shoulders, a waist and hips (a chubby person's belly pushes the front out), flat colour with a cel shadow
              on the back side and a soft light on the chest - the way hand-painted cartoons are lit
    clothes   a kurta's collar band and buttons, a shirt's collar and pocket, a saree's pallu across the chest and its
              gold border at the hem
All drawn in world coordinates (y up), the same units as engine/character.py."""
import math

import cairo

from .util import darker, lighter, TAU


def _seg_quad(ctx, a, b, wa, wb):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln, dx / ln
    ctx.move_to(a[0] + nx * wa, a[1] + ny * wa)
    ctx.line_to(b[0] + nx * wb, b[1] + ny * wb)
    ctx.line_to(b[0] - nx * wb, b[1] - ny * wb)
    ctx.line_to(a[0] - nx * wa, a[1] - ny * wa)
    ctx.close_path()


def _shape(ctx, pts, ws, extra):
    """the limb's outline as separate pieces (each filled on its own: no holes where pieces overlap)"""
    for i in range(len(pts) - 1):
        _seg_quad(ctx, pts[i], pts[i + 1], ws[i] / 2 + extra, ws[i + 1] / 2 + extra)
        yield
    for p, w in zip(pts, ws):
        ctx.new_sub_path()
        ctx.arc(p[0], p[1], w / 2 + extra, 0, TAU)
        yield


def limb(ctx, pts, ws, color, alpha, outline=None, ow=0.0):
    """a tapered limb through pts with widths ws (one per point), an ink line round it"""
    if outline is not None and ow > 0:
        ctx.set_source_rgba(*outline, alpha)
        for _ in _shape(ctx, pts, ws, ow):
            ctx.fill()
    if isinstance(color, tuple):
        ctx.set_source_rgba(*color, alpha)
    else:
        ctx.set_source(color)
    for _ in _shape(ctx, pts, ws, 0.0):
        ctx.fill()


def hand(ctx, elbow, wrist, size, color, alpha, outline, ow, f):
    """a mitten with a thumb, along the forearm (f: which way the person faces)"""
    ang = math.atan2(wrist[1] - elbow[1], wrist[0] - elbow[0])
    ctx.save()
    ctx.translate(*wrist)
    ctx.rotate(ang)
    for pass_ in (0, 1):
        e = ow if pass_ == 0 else 0.0
        if pass_ == 0:
            ctx.set_source_rgba(*outline, alpha)
        else:
            ctx.set_source_rgba(*color, alpha)
        ctx.save()                                             # the palm: a fat oval past the wrist
        ctx.translate(size * 0.55, 0)
        ctx.scale(size * 0.72 + e, size * 0.58 + e)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.fill()
        ctx.save()                                             # the thumb, on the front side
        ctx.translate(size * 0.35, f * size * 0.5)
        ctx.rotate(f * 0.6)
        ctx.scale(size * 0.34 + e, size * 0.22 + e)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.fill()
    ctx.restore()


def shoe(ctx, ankle, toe, size, color, alpha, outline, ow):
    """a rounded shoe from the ankle to past the toe; the sole a shade darker"""
    dx, dy = toe[0] - ankle[0], toe[1] - ankle[1]
    ang = math.atan2(dy, dx)
    ln = math.hypot(dx, dy) or size

    def oval(e):
        ctx.save()
        ctx.translate(*ankle)
        ctx.rotate(ang)
        ctx.translate(ln * 0.45, 0)
        ctx.scale(ln * 0.78 + size * 0.25 + e, size * 0.62 + e)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()                                           # (the path stays where it was drawn)
    oval(ow)
    ctx.set_source_rgba(*outline, alpha)
    ctx.fill()
    oval(0.0)
    ctx.set_source_rgba(*color, alpha)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    low = min(ankle[1], toe[1]) - size * 0.1                    # the sole: the bottom of the shoe (y is up)
    ctx.rectangle(ankle[0] - ln * 3, low - size * 3, ln * 6, size * 3)
    ctx.set_source_rgba(*darker(color, 0.62), alpha)
    ctx.fill()
    ctx.restore()


# the torso's half-width along the spine (0 = hips, 1 = the shoulders' top): hips, a waist, a chest, round shoulders
PROFILE = ((0.0, 0.96), (0.3, 0.86), (0.62, 0.98), (0.86, 1.06), (1.0, 0.8))
PROFILE_F = ((0.0, 1.04), (0.3, 0.84), (0.6, 0.98), (0.86, 0.98), (1.0, 0.76))       # (women: wider hips, a waist)


def _hw(u, prof):
    for (u0, w0), (u1, w1) in zip(prof, prof[1:]):
        if u <= u1:
            k = (u - u0) / max(1e-6, u1 - u0)
            k = k * k * (3 - 2 * k)
            return w0 + (w1 - w0) * k
    return prof[-1][1]


def torso_path(ctx, hip, top, px, py, tw, belly=0.0, female=False, n=14):
    """the torso's outline: front side up, back side down (px, py point to the front)"""
    prof = PROFILE_F if female else PROFILE
    front, back = [], []
    for i in range(n + 1):
        u = i / n
        cx, cy = hip[0] + (top[0] - hip[0]) * u, hip[1] + (top[1] - hip[1]) * u
        hw = tw * 0.5 * _hw(u, prof)
        bulge = belly * math.exp(-((u - 0.32) / 0.22) ** 2)          # a belly pushes the front out, low
        front.append((cx + px * (hw + bulge), cy + py * (hw + bulge)))
        back.append((cx - px * hw, cy - py * hw))
    pts = front + back[::-1]
    ctx.move_to(*pts[0])
    for i in range(1, len(pts)):                                     # smooth: through the midpoints
        mx, my = (pts[i - 1][0] + pts[i][0]) / 2, (pts[i - 1][1] + pts[i][1]) / 2
        ctx.curve_to(pts[i - 1][0], pts[i - 1][1], pts[i - 1][0], pts[i - 1][1], mx, my)
    ctx.line_to(*pts[-1])
    ctx.close_path()
    return front, back


def torso(ctx, hip, top, px, py, tw, color, alpha, outline, ow, belly=0.0, female=False):
    """the shaped torso: flat colour, a cel shadow down the back, a soft light on the chest, an ink line"""
    front, back = torso_path(ctx, hip, top, px, py, tw, belly, female)
    ctx.set_source_rgba(*color, alpha)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip_preserve()
    ctx.new_path()
    for (fx, fy), (bx, by) in zip(front, back):                       # the shadow side: the back third
        ctx.line_to(bx + (fx - bx) * 0.3, by + (fy - by) * 0.3)
    for bx, by in back[::-1]:
        ctx.line_to(bx - px * tw, by - py * tw)
    ctx.close_path()
    ctx.set_source_rgba(*darker(color, 0.8), alpha)
    ctx.fill()
    cu = 0.7                                                          # a soft light on the chest
    c0 = (hip[0] + (top[0] - hip[0]) * cu + px * tw * 0.25, hip[1] + (top[1] - hip[1]) * cu + py * tw * 0.25)
    g = cairo.RadialGradient(c0[0], c0[1], 0, c0[0], c0[1], tw * 0.6)
    g.add_color_stop_rgba(0, *lighter(color, 0.18), 0.55 * alpha)
    g.add_color_stop_rgba(1, *color, 0.0)
    ctx.set_source(g)
    ctx.paint()
    ctx.restore()
    torso_path(ctx, hip, top, px, py, tw, belly, female)
    ctx.set_source_rgba(*outline, alpha)
    ctx.set_line_width(ow)
    ctx.stroke()


def _pt(hip, top, u, px, py, off):
    return (hip[0] + (top[0] - hip[0]) * u + px * off, hip[1] + (top[1] - hip[1]) * u + py * off)


def clothes(ctx, c, hip, top, px, py, tw, s, alpha, ow, f):
    """the marks that say which clothes these are (drawn over the torso)"""
    out = c.outfit
    ink = darker(c.top or c.skin, 0.55)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    if out in ("kurta", "dhoti", "farmer", "sadhu", "royal"):            # a collar band + a button strip down the front
        a, b = _pt(hip, top, 0.97, px, py, tw * 0.3), _pt(hip, top, 0.55, px, py, tw * 0.36)
        ctx.set_source_rgba(*ink, 0.75 * alpha)
        ctx.set_line_width(ow * 0.8)
        ctx.move_to(*a)
        ctx.line_to(*b)
        ctx.stroke()
        for u in (0.88, 0.76, 0.64):
            p = _pt(hip, top, u, px, py, tw * 0.36)
            ctx.arc(p[0], p[1], 2.3 * s, 0, TAU)
            ctx.set_source_rgba(*lighter(c.accent, 0.1) if out == "royal" else (0.96, 0.92, 0.8), alpha)
            ctx.fill_preserve()
            ctx.set_source_rgba(*ink, alpha)
            ctx.set_line_width(ow * 0.4)
            ctx.stroke()
        n0, n1 = _pt(hip, top, 1.0, px, py, -tw * 0.1), _pt(hip, top, 1.0, px, py, tw * 0.42)
        ctx.move_to(*n0)
        ctx.line_to(*n1)
        ctx.set_source_rgba(*darker(c.top or c.skin, 0.75), alpha)
        ctx.set_line_width(5 * s)
        ctx.stroke()
    elif out in ("shirt", "uniform", "pilot", "police", "army"):        # a pointed collar and a pocket
        top_c = c.top or c.skin
        col = lighter(top_c, 0.25) if out != "uniform" else (1, 1, 1)
        for side in (0.1, 0.42):
            a = _pt(hip, top, 1.0, px, py, tw * side)
            ctx.move_to(*a)
            ctx.line_to(*_pt(hip, top, 0.86, px, py, tw * (side + 0.12)))
            ctx.line_to(*_pt(hip, top, 0.95, px, py, tw * (side + 0.22)))
            ctx.close_path()
            ctx.set_source_rgba(*col, alpha)
            ctx.fill_preserve()
            ctx.set_source_rgba(*darker(top_c, 0.55), alpha)
            ctx.set_line_width(ow * 0.6)
            ctx.stroke()
        pk = [_pt(hip, top, u, px, py, tw * o) for u, o in ((0.78, 0.05), (0.78, 0.3), (0.62, 0.3), (0.62, 0.05))]
        ctx.move_to(*pk[0])
        for p in pk[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        ctx.set_source_rgba(*darker(top_c, 0.55), 0.8 * alpha)
        ctx.set_line_width(ow * 0.55)
        ctx.stroke()
    elif out == "saree":                                                # the pallu: a wide band from the hip to the shoulder
        band = lighter(c.top or c.skin, 0.08)
        gold = (0.93, 0.74, 0.22)
        a0, a1 = _pt(hip, top, 0.2, px, py, tw * 0.5), _pt(hip, top, 0.2, px, py, tw * 0.05)
        b0, b1 = _pt(hip, top, 1.0, px, py, -tw * 0.2), _pt(hip, top, 1.0, px, py, -tw * 0.55)
        ctx.move_to(*a0)
        ctx.line_to(*b0)
        ctx.line_to(*b1)
        ctx.line_to(*a1)
        ctx.close_path()
        ctx.set_source_rgba(*band, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*darker(band, 0.6), alpha)
        ctx.set_line_width(ow * 0.7)
        ctx.stroke()
        ctx.move_to(*a0)                                                 # its gold edge
        ctx.line_to(*b0)
        ctx.set_source_rgba(*gold, alpha)
        ctx.set_line_width(4.5 * s)
        ctx.stroke()


def hem(ctx, front, back, s, alpha, color=(0.93, 0.74, 0.22)):
    """a saree's gold border along the hem (front and back are the hem's two ends)"""
    ctx.move_to(*front)
    ctx.line_to(*back)
    ctx.set_source_rgba(*color, alpha)
    ctx.set_line_width(6 * s)
    ctx.stroke()
