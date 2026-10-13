"""Front ("camera") and back ("away") views of four-legged animals.

Used automatically when an animal walks or runs toward / away from the camera (depth moves), or when a story
says "facing": "camera" / "away". Heights (shoulder, hip, head, each paw) come from the same side-view rig and
poses, so every action - walk, run, sit, lie, jump, roar, wag - also works seen from the front or back:
the four legs step in turn, the body bobs, the head nods and the tail swings.
"""
import math

import cairo

from .animals import q_solve, _ellipse, _fill, _stroke, _rgb, _trunk
from .util import darker, lighter, TAU, clamp


def body_half_width(c):
    """Half width of a four-legged animal's body seen from the front / back (world units)."""
    sp = c.animal
    return sp["girth"] * c.scale * (1.3 if sp["girth"] < 45 else 1.12 if sp["girth"] < 60 else 1.0) * 0.72


def draw_quad_front(ctx, c, pose, x, y, view, face, mouth, t, alpha, blink, scale_mul=1.0, extras=None, shadow=True):
    """World coordinates, y-up; (x, y) = point on the ground under the animal. Returns the info dict."""
    from .character import draw_shadow
    sp = c.animal
    s = c.scale * scale_mul
    J = q_solve(pose, sp, s)
    back = view == "away"
    fur, belly = sp["fur"], sp["belly"]
    fo = darker(fur, 0.58)
    OW = 2.6 * s
    g = sp["girth"] * s * (1.3 if sp["girth"] < 45 else 1.12 if sp["girth"] < 60 else 1.0)   # front view is wider
    hr = sp["head"] * s
    leg_w = sp.get("leg_w", sp["girth"] * 0.34) * s
    leg_col = _rgb(sp["leg_color"]) if sp.get("leg_color") else ((0.1, 0.1, 0.1) if sp.get("pattern") == "panda" else fur)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    sh_y = y + J["sj"][1]                      # shoulder joint height
    hip_y = y + J["hj"][1]
    head_y = y + J["head"][1]
    chest_y = y + (J["sh"][1] + J["sj"][1]) / 2
    rump_y = y + (J["hip"][1] + J["hj"][1]) / 2
    fx = g * 0.44                              # front legs apart
    bx = g * 0.40                              # back legs apart
    leg_w *= 1.18
    # the neck points toward the camera (front view) or away (back view): the head sits lower, over the chest
    lift_head = max((head_y - chest_y) * (0.6 if not back else 0.72), g * 0.42 + hr * 0.55)
    head_y = chest_y + lift_head
    sway = 0.06 * g * math.sin(TAU * t * 0.9)  # tiny weight shift
    if shadow:
        low = min(J["pfn"][1], J["pff"][1], J["pbn"][1], J["pbf"][1])
        draw_shadow(ctx, x, max(0.0, low / max(s, 0.1) - 2), g * 0.95 + 18 * s, alpha, y)

    def foot(key_paw, key_root):
        """(lift, forward) of a paw from the side rig: lift = height, forward = toward the head."""
        py = J[key_paw][1]
        dx = J[key_paw][0] - J[key_root][0]
        return py, dx

    def leg(xr, top_y, key_knee, key_paw, key_root, near, toward):
        py, dx = foot(key_paw, key_root)
        # a paw stepping toward the camera lands a little lower on screen and looks a little bigger
        k = (1.0 if toward else -1.0) * (1 if near else 0.6)
        paw_y = y + py - clamp(dx * 0.10 * k, -8 * s, 8 * s)
        knee_y = y + J[key_knee][1]
        w = leg_w * (1.0 if near else 0.85) * (1 + clamp(dx * 0.002 * k, -0.08, 0.08))
        col = leg_col if near else darker(leg_col, 0.8)
        kx = xr + (0.06 * g if xr > x else -0.06 * g)
        pts = [(xr, top_y), (kx, (knee_y + top_y) / 2 if knee_y > top_y else knee_y), (xr, paw_y + w * 0.3)]
        _stroke(ctx, pts, w, col, alpha, darker(col, 0.58), OW)
        if sp.get("hooves"):
            _ellipse(ctx, xr, paw_y + w * 0.25, w * 0.55, w * 0.32)
            _fill(ctx, (0.2, 0.17, 0.15), alpha)
        else:
            _ellipse(ctx, xr, paw_y + w * 0.3, w * 0.62, w * 0.42)
            _fill(ctx, col, alpha, darker(col, 0.58), OW * 0.8)
            ctx.set_source_rgba(*darker(col, 0.5), alpha)
            ctx.set_line_width(OW * 0.5)
            for d in (-0.22, 0.22):
                ctx.move_to(xr + d * w, paw_y + w * 0.05)
                ctx.line_to(xr + d * w, paw_y + w * 0.3)
            ctx.stroke()

    toward = not back
    if not back:
        # ---------------------------------------------------------- FRONT: rump + back legs far, chest near
        leg(x - bx + sway, rump_y - g * 0.1, "kbf", "pbf", "hj", False, toward)
        leg(x + bx + sway, rump_y - g * 0.1, "kbn", "pbn", "hj", False, toward)
        _tail_peek(ctx, sp, x, rump_y + g * 0.45, g, t, pose, alpha, OW, s)
        _ellipse(ctx, x + sway, rump_y + g * 0.12, g * 0.66, g * 0.5)               # rump behind the chest
        _fill(ctx, darker(fur, 0.9), alpha, fo, OW)
        leg(x - fx + sway * 0.4, chest_y - g * 0.1, "kff", "pff", "sj", True, toward)
        leg(x + fx + sway * 0.4, chest_y - g * 0.1, "kfn", "pfn", "sj", True, toward)
        _body_front(ctx, sp, x + sway * 0.5, chest_y, g, alpha, OW, s, belly)     # chest over the leg tops
        _neck_front(ctx, sp, x, chest_y + g * 0.2, head_y, s, alpha, OW)
        if sp.get("mane") and sp["name"] == "lion":
            _mane_ring(ctx, sp, x, head_y, hr, alpha, OW)
        ctx.save()
        ctx.translate(x, head_y)
        ctx.rotate(math.radians(pose.get("head", 0) * 0.25) * 0.3)
        mouth_pt = _head_front(ctx, c, sp, hr, face, max(mouth, pose.get("jaw", 0)), blink, alpha, OW, t, pose, s)
        ctx.restore()
        mx, my = x + mouth_pt[0], head_y + mouth_pt[1]
    else:
        # ---------------------------------------------------------- BACK: head + front legs far, rump near
        if sp.get("mane") and sp["name"] == "lion":
            _mane_ring(ctx, sp, x, head_y, hr, alpha, OW)
        ctx.save()
        ctx.translate(x, head_y)
        _head_back(ctx, sp, hr, alpha, OW, t, pose, s)
        ctx.restore()
        _neck_front(ctx, sp, x, chest_y + g * 0.3, head_y, s, alpha, OW, dark=True)
        leg(x - fx - sway * 0.4, chest_y - g * 0.1, "kff", "pff", "sj", False, toward)
        leg(x + fx - sway * 0.4, chest_y - g * 0.1, "kfn", "pfn", "sj", False, toward)
        _ellipse(ctx, x - sway * 0.5, chest_y + g * 0.08, g * 0.64, g * 0.5)        # shoulders behind the rump
        _fill(ctx, darker(fur, 0.88), alpha, fo, OW)
        leg(x - bx * 1.1 - sway, rump_y - g * 0.1, "kbf", "pbf", "hj", True, toward)
        leg(x + bx * 1.1 - sway, rump_y - g * 0.1, "kbn", "pbn", "hj", True, toward)
        _rump_back(ctx, sp, x - sway, rump_y, g, alpha, OW, s)                     # rump over the leg tops
        for side in (-1, 1):
            hx_ = x - sway + side * bx * 1.05
            _ellipse(ctx, hx_, rump_y - g * 0.12, g * 0.3, g * 0.36)                 # haunches
            _fill(ctx, darker(fur, 0.97), alpha)
            ctx.save()
            ctx.arc(hx_, rump_y - g * 0.12, g * 0.3, math.radians(200), math.radians(340))
            ctx.set_source_rgba(*fo, alpha)
            ctx.set_line_width(OW * 0.8)
            ctx.stroke()
            ctx.restore()
        _tail_back(ctx, sp, x - sway, rump_y + g * 0.32, g, t, pose, alpha, OW, s)
        mx, my = x, head_y
    extras = extras or {}
    if extras.get("tears") and not back:
        ctx.set_source_rgba(0.35, 0.68, 1.0, alpha * 0.9)
        for k in range(3):
            ph = (t * 1.6 + k / 3.0) % 1.0
            for sx in (-1, 1):
                ctx.arc(x + sx * hr * 0.4, head_y + hr * 0.1 - ph * 50 * s, (4.4 - 2 * ph) * s, 0, TAU)
                ctx.fill()
    return {"hand": (mx, my), "head": (x, head_y), "hip": (x, hip_y), "head_r": hr, "mouth": (mx, my)}


# ============================================================================ body parts
def _body_front(ctx, sp, x, cy, g, alpha, OW, s, belly):
    fur = sp["fur"]
    _ellipse(ctx, x, cy, g * 0.72, g * 0.62)
    gr = cairo.RadialGradient(x + g * 0.2, cy + g * 0.22, g * 0.05, x, cy, g * 0.8)
    gr.add_color_stop_rgba(0, *lighter(fur, 0.12), alpha)
    gr.add_color_stop_rgba(1, *darker(fur, 0.86), alpha)
    ctx.set_source(gr)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    ctx.new_path()
    _ellipse(ctx, x, cy - g * 0.2, g * 0.34, g * 0.46)                               # light chest / bib
    ctx.set_source_rgba(*belly, alpha)
    ctx.fill()
    pat = sp.get("pattern")
    if pat in ("stripes", "stripes_light", "zebra"):
        col = (0.12, 0.08, 0.06) if pat != "stripes_light" else darker(fur, 0.7)
        ctx.set_source_rgba(*col, alpha * (0.95 if pat != "stripes_light" else 0.7))
        for side in (-1, 1):
            for k in range(3):
                yy = cy + g * (0.25 - k * 0.22)
                ctx.move_to(x + side * g * 0.74, yy)
                ctx.curve_to(x + side * g * 0.4, yy - g * 0.02, x + side * g * 0.32, yy - g * 0.08, x + side * g * 0.26, yy - g * 0.05)
                ctx.line_to(x + side * g * 0.34, yy - g * 0.13)
                ctx.curve_to(x + side * g * 0.42, yy - g * 0.12, x + side * g * 0.5, yy - g * 0.1, x + side * g * 0.56, yy - g * 0.12)
                ctx.close_path()
                ctx.fill()
    elif pat == "patches":
        ctx.set_source_rgba(0.12, 0.12, 0.13, alpha)
        _ellipse(ctx, x - g * 0.32, cy + g * 0.18, g * 0.2, g * 0.24, 0.3)
        ctx.fill()
        _ellipse(ctx, x + g * 0.36, cy - g * 0.2, g * 0.14, g * 0.18, -0.2)
        ctx.fill()
    elif pat == "spots":
        ctx.set_source_rgba(1, 1, 1, alpha * 0.85)
        for dx, dy in ((-0.38, 0.1), (0.4, 0.2), (-0.3, -0.25), (0.35, -0.15)):
            ctx.arc(x + dx * g, cy + dy * g, 4 * s, 0, TAU)
            ctx.fill()
    ctx.restore()
    _ellipse(ctx, x, cy, g * 0.72, g * 0.62)
    ctx.set_source_rgba(*darker(fur, 0.58), alpha)
    ctx.set_line_width(OW)
    ctx.stroke()


def _rump_back(ctx, sp, x, cy, g, alpha, OW, s):
    fur = sp["fur"]
    _ellipse(ctx, x, cy + g * 0.05, g * 0.72, g * 0.58)
    gr = cairo.RadialGradient(x + g * 0.15, cy + g * 0.25, g * 0.05, x, cy, g * 0.8)
    gr.add_color_stop_rgba(0, *lighter(fur, 0.1), alpha)
    gr.add_color_stop_rgba(1, *darker(fur, 0.86), alpha)
    ctx.set_source(gr)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    ctx.new_path()
    pat = sp.get("pattern")
    if pat in ("stripes", "stripes_light", "zebra"):
        col = (0.12, 0.08, 0.06) if pat != "stripes_light" else darker(fur, 0.7)
        ctx.set_source_rgba(*col, alpha * 0.9)
        for k in range(4):
            yy = cy + g * (0.45 - k * 0.2)
            for side in (-1, 1):
                ctx.move_to(x + side * g * 0.08, yy)
                ctx.curve_to(x + side * g * 0.25, yy + g * 0.04, x + side * g * 0.4, yy - g * 0.02, x + side * g * 0.55, yy - g * 0.1)
                ctx.line_to(x + side * g * 0.55, yy - g * 0.02)
                ctx.curve_to(x + side * g * 0.4, yy + g * 0.08, x + side * g * 0.25, yy + g * 0.12, x + side * g * 0.08, yy + g * 0.07)
                ctx.close_path()
                ctx.fill()
    elif pat == "patches":
        ctx.set_source_rgba(0.12, 0.12, 0.13, alpha)
        _ellipse(ctx, x + g * 0.25, cy + g * 0.2, g * 0.22, g * 0.2, 0.3)
        ctx.fill()
    ctx.restore()
    _ellipse(ctx, x, cy + g * 0.05, g * 0.72, g * 0.58)
    ctx.set_source_rgba(*darker(fur, 0.58), alpha)
    ctx.set_line_width(OW)
    ctx.stroke()
    if sp.get("udder"):
        _ellipse(ctx, x, cy - g * 0.42, 12 * s, 8 * s)
        _fill(ctx, (0.96, 0.7, 0.72), alpha, darker((0.96, 0.7, 0.72), 0.7), OW * 0.7)


def _neck_front(ctx, sp, x, y0, head_y, s, alpha, OW, dark=False):
    if sp["neck"] <= 8:
        return
    fur = sp["fur"] if not dark else darker(sp["fur"], 0.92)
    _stroke(ctx, [(x, y0), (x, head_y)], sp["neck_w"] * s * 0.95, fur, alpha, darker(sp["fur"], 0.58), OW)
    if sp["name"] in ("horse", "zebra", "donkey") and sp.get("mane"):
        ctx.set_source_rgba(*_rgb(sp["mane"]), alpha)
        ctx.set_line_width(9 * s)
        ctx.move_to(x, y0 + 8 * s)
        ctx.line_to(x, head_y + sp["head"] * s * 0.9)
        ctx.stroke()


def _mane_ring(ctx, sp, x, y, hr, alpha, OW):
    ctx.save()
    ctx.translate(x, y - hr * 0.1)
    n = 20
    ctx.move_to(hr * 1.75, 0)
    for k in range(1, n * 2 + 1):
        a = math.pi * k / n
        rr = hr * (1.75 if k % 2 == 0 else 1.45)
        ctx.line_to(rr * math.cos(a), rr * math.sin(a))
    ctx.close_path()
    ctx.restore()
    _fill(ctx, _rgb(sp["mane"]), alpha, darker(_rgb(sp["mane"]), 0.6), OW)


def _tail_peek(ctx, sp, x, y, g, t, pose, alpha, OW, s):
    """Front view: the tail tip sways up behind the body on one side."""
    kind = sp.get("tail")
    if kind in (None, "puff", "short_up", "curly"):
        return
    fur = sp["fur"]
    wag = pose.get("wag", 0) * math.sin(TAU * 5 * t) * 0.5 + 0.25 * math.sin(TAU * t / 2.3)
    tip = (x + g * (0.55 + 0.25 * wag), y + g * (0.35 + 0.1 * math.cos(TAU * t / 2.3)))
    w = (14 if kind == "bushy" else 7 if kind in ("tuft", "long_hair") else 8) * s
    col = _rgb(sp["mane"]) if (kind == "long_hair" and sp.get("mane")) else fur
    _stroke(ctx, [(x + g * 0.3, y - g * 0.1), ((x + g * 0.3 + tip[0]) / 2 + g * 0.1, (y + tip[1]) / 2), tip], w, col,
            alpha, darker(fur, 0.58), OW)
    if kind in ("tuft", "tuft_thin"):
        ctx.arc(tip[0], tip[1], 7 * s, 0, TAU)
        _fill(ctx, _rgb(sp["mane"]) if sp.get("mane") else darker(fur, 0.6), alpha)
    if sp.get("tail_tip"):
        ctx.arc(tip[0], tip[1], w * 0.6, 0, TAU)
        _fill(ctx, _rgb(sp["tail_tip"]), alpha)


def _tail_back(ctx, sp, x, y, g, t, pose, alpha, OW, s):
    """Back view: the tail hangs / curls / wags from the middle of the rump."""
    kind = sp.get("tail")
    fur = sp["fur"]
    wag = pose.get("wag", 0) * math.sin(TAU * 5 * t) + 0.35 * math.sin(TAU * t / 2.3)
    up = math.radians(pose.get("tail", 15))
    if kind == "puff":
        ctx.arc(x, y, 11 * s, 0, TAU)
        _fill(ctx, (1, 1, 1), alpha, (0.75, 0.75, 0.75), OW * 0.7)
        return
    if kind == "curly":
        ctx.set_source_rgba(*darker(fur, 0.8), alpha)
        ctx.set_line_width(4 * s)
        for k in range(18):
            a = k * 0.6
            rr = 3 + k * 0.5
            px, py = x + rr * math.cos(a) * s, y + rr * math.sin(a) * s
            (ctx.move_to if k == 0 else ctx.line_to)(px, py)
        ctx.stroke()
        return
    n, seg, w, curl = {"long": (7, 13, 9, 0.1), "long_up": (7, 12, 8, 0.2), "curve": (5, 11, 10, 0.25),
                       "bushy": (5, 15, 18, 0.08), "tuft": (6, 12, 6, -0.1), "tuft_thin": (6, 10, 4, -0.1),
                       "long_hair": (6, 15, 16, -0.05), "short_up": (2, 10, 9, 0.3)}.get(kind, (5, 12, 8, 0.1))
    pts = [(x, y)]
    a = -math.pi / 2 + up * 1.4 + 0.5 * wag
    for k in range(n):
        a += curl * (1 if wag >= 0 else -1) * 0.6 + 0.08 * wag
        lx, ly = pts[-1]
        pts.append((lx + math.cos(a) * seg * s * 0.9, ly + math.sin(a) * seg * s))
    col = _rgb(sp["mane"]) if (kind == "long_hair" and sp.get("mane")) else fur
    _stroke(ctx, pts, w * s, col, alpha, darker(fur, 0.58), OW)
    if kind == "long":
        ctx.set_source_rgba(0.12, 0.08, 0.06, alpha)
        for p in pts[2::2]:
            ctx.arc(p[0], p[1], 4.5 * s, 0, TAU)
            ctx.fill()
    elif kind in ("tuft", "tuft_thin"):
        e = pts[-1]
        ctx.arc(e[0], e[1], 8 * s, 0, TAU)
        _fill(ctx, _rgb(sp["mane"]) if sp.get("mane") else darker(fur, 0.6), alpha)
    if sp.get("tail_tip"):
        e = pts[-1]
        ctx.arc(e[0], e[1], w * s * 0.55, 0, TAU)
        _fill(ctx, _rgb(sp["tail_tip"]), alpha)


# ============================================================================ heads
def _ears(ctx, sp, hr, fur, fo, alpha, ow, ear, behind=True):
    ek = sp.get("ears")
    if ek == "long":
        for sx in (-1, 1):
            _ellipse(ctx, sx * hr * 0.42, hr * (1.25 + 0.1 * ear), hr * 0.26, hr * 0.9, sx * (0.15 + 0.2 * ear))
            _fill(ctx, fur, alpha, fo, ow)
            _ellipse(ctx, sx * hr * 0.42, hr * (1.25 + 0.1 * ear), hr * 0.12, hr * 0.65, sx * (0.15 + 0.2 * ear))
            _fill(ctx, (0.95, 0.7, 0.75), alpha)
    elif ek in ("pointy", "pointy_tall"):
        hgt = 0.95 if ek == "pointy_tall" else 0.65
        for sx in (-1, 1):
            ctx.move_to(sx * hr * 0.25, hr * 0.75)
            ctx.line_to(sx * hr * (0.72 + 0.1 * ear), hr * (0.62 + hgt))
            ctx.line_to(sx * hr * 0.88, hr * 0.35)
            ctx.close_path()
            _fill(ctx, fur, alpha, fo, ow)
            ctx.move_to(sx * hr * 0.4, hr * 0.7)
            ctx.line_to(sx * hr * (0.7 + 0.1 * ear), hr * (0.5 + hgt * 0.9))
            ctx.line_to(sx * hr * 0.78, hr * 0.45)
            ctx.close_path()
            _fill(ctx, (0.95, 0.72, 0.72), alpha * 0.8)
    elif ek == "round":
        ear_col = (0.1, 0.1, 0.1) if sp.get("pattern") == "panda" else fur
        for sx in (-1, 1):
            ctx.arc(sx * hr * 0.72, hr * 0.72, hr * 0.3, 0, TAU)
            _fill(ctx, ear_col, alpha, fo, ow)
            ctx.arc(sx * hr * 0.72, hr * 0.72, hr * 0.15, 0, TAU)
            _fill(ctx, darker(fur, 0.6), alpha)
    elif ek == "side":
        for sx in (-1, 1):
            _ellipse(ctx, sx * hr * 1.1, hr * 0.35, hr * 0.45, hr * 0.17, sx * (0.25 - 0.3 * ear))
            _fill(ctx, fur, alpha, fo, ow)
            _ellipse(ctx, sx * hr * 1.12, hr * 0.35, hr * 0.28, hr * 0.08, sx * (0.25 - 0.3 * ear))
            _fill(ctx, (0.95, 0.72, 0.72), alpha * 0.8)
    elif ek == "huge":
        flap = 0.1 * math.sin(TAU * 0.4)
        for sx in (-1, 1):
            _ellipse(ctx, sx * hr * 1.15, -hr * 0.05, hr * 0.75, hr * 0.95, sx * (flap - 0.15))
            _fill(ctx, darker(fur, 0.92), alpha, fo, ow)
            _ellipse(ctx, sx * hr * 1.12, -hr * 0.05, hr * 0.5, hr * 0.7, sx * (flap - 0.15))
            _fill(ctx, (0.93, 0.74, 0.76), alpha * 0.5)


def _horns(ctx, sp, hr, alpha, s):
    if sp.get("horns") == "small":
        ctx.set_source_rgba(0.95, 0.9, 0.78, alpha)
        ctx.set_line_width(6 * s)
        for sx in (-1, 1):
            ctx.move_to(sx * hr * 0.45, hr * 0.8)
            ctx.curve_to(sx * hr * 0.7, hr * 1.05, sx * hr * 0.95, hr * 1.1, sx * hr * 1.0, hr * 1.35)
            ctx.stroke()
    elif sp.get("horns") == "curved":
        ctx.set_source_rgba(0.55, 0.47, 0.38, alpha)
        ctx.set_line_width(6 * s)
        for sx in (-1, 1):
            ctx.move_to(sx * hr * 0.3, hr * 0.85)
            ctx.curve_to(sx * hr * 0.4, hr * 1.5, sx * hr * 1.1, hr * 1.4, sx * hr * 0.95, hr * 0.8)
            ctx.stroke()
    if sp.get("antlers"):
        ctx.set_source_rgba(0.55, 0.38, 0.2, alpha)
        ctx.set_line_width(4 * s)
        for sx in (-1, 1):
            bx = sx * hr * 0.4
            ctx.move_to(bx, hr * 0.85)
            ctx.line_to(bx + sx * hr * 0.45, hr * 1.9)
            for k, ly in enumerate((1.2, 1.5, 1.75)):
                px = bx + sx * hr * 0.45 * (ly - 0.85) / 1.05
                ctx.move_to(px, hr * ly)
                ctx.line_to(px + sx * hr * (0.35 if k % 2 == 0 else -0.25), hr * (ly + 0.3))
            ctx.stroke()


def _head_front(ctx, c, sp, hr, face, mouth, blink, alpha, ow, t, pose, s):
    """Head seen from the front, centred at the origin (y up). Returns the mouth point."""
    fur = sp["fur"]
    fo = darker(fur, 0.58)
    name = sp["name"]
    ear = pose.get("ear", 0)
    ctx.set_line_width(ow)
    _ears(ctx, sp, hr, fur, fo, alpha, ow, ear)
    _horns(ctx, sp, hr, alpha, s)
    # skull
    _ellipse(ctx, 0, 0, hr * 1.02, hr * 0.96)
    gr = cairo.RadialGradient(hr * 0.25, hr * 0.3, hr * 0.1, 0, 0, hr * 1.05)
    gr.add_color_stop_rgba(0, *lighter(fur, 0.12), alpha)
    gr.add_color_stop_rgba(1, *darker(fur, 0.9), alpha)
    ctx.set_source(gr)
    ctx.fill_preserve()
    ctx.set_source_rgba(*fo, alpha)
    ctx.stroke()
    pat = sp.get("pattern")
    if pat == "stripes":
        ctx.set_source_rgba(0.12, 0.08, 0.06, alpha)
        for px, py, a in ((0, 0.78, 0), (-0.28, 0.72, 0.35), (0.28, 0.72, -0.35)):
            _ellipse(ctx, px * hr, py * hr, 0.07 * hr, 0.2 * hr, a)
            ctx.fill()
        for sx in (-1, 1):
            for k in range(2):
                ctx.move_to(sx * hr * 0.98, hr * (0.1 - 0.22 * k))
                ctx.line_to(sx * hr * 0.66, hr * (0.02 - 0.22 * k))
                ctx.line_to(sx * hr * 0.96, hr * (-0.06 - 0.22 * k))
                ctx.close_path()
                ctx.fill()
    elif pat == "patches":
        ctx.set_source_rgba(0.12, 0.12, 0.13, alpha)
        _ellipse(ctx, -hr * 0.45, hr * 0.35, hr * 0.35, hr * 0.3, 0.4)
        ctx.fill()
    if sp.get("ears") == "floppy":
        for sx in (-1, 1):
            _ellipse(ctx, sx * hr * 0.92, hr * 0.0, hr * 0.26, hr * 0.62, sx * (0.25 - 0.2 * ear))
            _fill(ctx, darker(fur, 0.75), alpha, fo, ow)
    if pat == "panda":
        for sx in (-1, 1):
            _ellipse(ctx, sx * hr * 0.38, hr * 0.15, hr * 0.26, hr * 0.32, sx * -0.4)
            _fill(ctx, (0.1, 0.1, 0.1), alpha)
    # eyes (both, looking at the viewer)
    ey = hr * 0.18
    er = hr * 0.19
    dark = (0.1, 0.08, 0.08)
    for sx in (-1, 1):
        ex = sx * hr * 0.4
        if blink or face in ("sleeping", "crying"):
            ctx.move_to(ex - er, ey)
            ctx.curve_to(ex - er * 0.4, ey - er * 0.6, ex + er * 0.4, ey - er * 0.6, ex + er, ey)
            ctx.set_source_rgba(*dark, alpha)
            ctx.set_line_width(ow)
            ctx.stroke()
        elif face == "laughing":
            ctx.move_to(ex - er, ey - er * 0.2)
            ctx.curve_to(ex - er * 0.4, ey + er * 0.7, ex + er * 0.4, ey + er * 0.7, ex + er, ey - er * 0.2)
            ctx.set_source_rgba(*dark, alpha)
            ctx.set_line_width(ow)
            ctx.stroke()
        else:
            big = 1.25 if face in ("surprised", "scared") else 1.0
            _ellipse(ctx, ex, ey, er * big, er * 1.15 * big)
            _fill(ctx, (1, 1, 1), alpha, darker(fur, 0.5), ow * 0.6)
            ctx.arc(ex, ey - er * 0.05, er * 0.62, 0, TAU)
            _fill(ctx, dark, alpha)
            ctx.arc(ex + er * 0.2, ey + er * 0.25, er * 0.2, 0, TAU)
            _fill(ctx, (1, 1, 1), alpha)
        if face in ("angry", "sad", "scared", "crying"):
            ctx.set_source_rgba(*darker(fur, 0.45), alpha)
            ctx.set_line_width(ow * 1.2)
            if face == "angry":
                ctx.move_to(ex + sx * er * 1.1, ey + er * 1.8)
                ctx.line_to(ex - sx * er * 1.0, ey + er * 1.15)
            else:
                ctx.move_to(ex - sx * er * 1.0, ey + er * 1.75)
                ctx.line_to(ex + sx * er * 1.1, ey + er * 1.2)
            ctx.stroke()
    # snout / muzzle (seen end-on) + nose + mouth
    sl, sw = sp["snout"]
    mouth_pt = (0.0, -hr * 0.55)
    if name == "elephant":
        ctx.save()
        ctx.translate(-hr * 0.1, 0)
        ctx.rotate(-0.15)
        _trunk_front(ctx, sp, hr, alpha, ow, t, pose, s)
        ctx.restore()
        if sp.get("tusks"):
            ctx.set_source_rgba(0.98, 0.97, 0.9, alpha)
            ctx.set_line_width(7 * s)
            for sx in (-1, 1):
                ctx.move_to(sx * hr * 0.35, -hr * 0.45)
                ctx.curve_to(sx * hr * 0.5, -hr * 0.9, sx * hr * 0.3, -hr * 1.05, sx * hr * 0.15, -hr * 1.0)
                ctx.stroke()
        return (0.0, -hr * 0.6)
    long_face = sl > sp["head"] * 1.08                 # horse / deer: long face
    mc = sp.get("muzzle") or lighter(fur, 0.35)
    mcy = -hr * (0.62 if long_face else 0.42)
    mrx = max(sw * s * 0.8, hr * 0.42)
    mry = hr * (0.5 if long_face else 0.32)
    _ellipse(ctx, 0, mcy, mrx, mry)
    _fill(ctx, mc, alpha, fo, ow)
    if sp.get("snout_flat") or name in ("cow", "horse", "goat", "deer", "pig", "zebra", "donkey", "camel", "buffalo", "sheep", "giraffe"):
        ny = mcy - mry * 0.1
        for sx in (-1, 1):
            _ellipse(ctx, sx * mrx * 0.38, ny, mrx * 0.13, mry * 0.2)
            _fill(ctx, darker(mc, 0.55), alpha)
        mouth_y = mcy - mry * 0.6
    else:
        ny = mcy + mry * 0.45
        ctx.move_to(-hr * 0.16, ny + hr * 0.06)
        ctx.line_to(hr * 0.16, ny + hr * 0.06)
        ctx.line_to(0, ny - hr * 0.1)
        ctx.close_path()
        _fill(ctx, (0.15, 0.1, 0.1), alpha)
        ctx.set_source_rgba(0.15, 0.1, 0.1, alpha)
        ctx.set_line_width(ow * 0.8)
        ctx.move_to(0, ny - hr * 0.1)
        ctx.line_to(0, mcy - mry * 0.2)
        ctx.stroke()
        mouth_y = mcy - mry * 0.35
    mouth_pt = (0.0, mouth_y)
    if mouth > 0.06:
        _ellipse(ctx, 0, mouth_y - mouth * 6 * s, hr * 0.28, mouth * 11 * s + 2 * s)
        _fill(ctx, (0.45, 0.1, 0.12), alpha)
        if mouth > 0.35 and name in ("dog",) and face in ("happy", "laughing"):
            _ellipse(ctx, 0, mouth_y - mouth * 12 * s, hr * 0.12, mouth * 8 * s)
            _fill(ctx, (0.95, 0.45, 0.5), alpha)
        if mouth > 0.5 and name in ("tiger", "lion", "wolf", "dog", "fox", "bear", "cat"):
            ctx.set_source_rgba(1, 1, 1, alpha)
            for sx in (-1, 1):
                ctx.move_to(sx * hr * 0.18 - 2 * s, mouth_y + 1 * s)
                ctx.line_to(sx * hr * 0.16, mouth_y - 8 * s)
                ctx.line_to(sx * hr * 0.14 + 2 * s, mouth_y + 1 * s)
                ctx.fill()
    else:
        ctx.set_source_rgba(0.2, 0.12, 0.1, alpha)
        ctx.set_line_width(ow * 0.8)
        smile = 4 * s if face in ("happy", "laughing") else (-3 * s if face in ("sad", "crying") else 0)
        if name in ("cat", "tiger", "lion", "dog", "wolf", "fox", "rabbit", "bear"):
            for sx in (-1, 1):                              # the "w" mouth of cats and dogs
                ctx.move_to(0, mouth_y + 2 * s)
                ctx.curve_to(sx * hr * 0.05, mouth_y - 3 * s - smile * 0.4, sx * hr * 0.18, mouth_y - 3 * s - smile * 0.4,
                             sx * hr * 0.24, mouth_y + smile * 0.5)
        else:
            ctx.move_to(-hr * 0.2, mouth_y)
            ctx.curve_to(-hr * 0.08, mouth_y - smile, hr * 0.08, mouth_y - smile, hr * 0.2, mouth_y)
        ctx.stroke()
    if sp.get("whiskers"):
        ctx.set_source_rgba(0.15, 0.1, 0.1, alpha * 0.7)
        ctx.set_line_width(1.2 * s)
        for sx in (-1, 1):
            for dy in (-4, 0, 4):
                ctx.move_to(sx * mrx * 0.6, mcy + dy * s * 0.4)
                ctx.line_to(sx * (mrx * 0.6 + 22 * s), mcy + dy * s * 1.5)
        ctx.stroke()
    if sp.get("beard"):
        ctx.move_to(-hr * 0.15, mcy - mry * 0.9)
        ctx.line_to(0, mcy - mry * 0.9 - hr * 0.55)
        ctx.line_to(hr * 0.15, mcy - mry * 0.9)
        ctx.close_path()
        _fill(ctx, darker(fur, 0.85), alpha)
    return mouth_pt


def _trunk_front(ctx, sp, hr, alpha, ow, t, pose, s):
    fur = sp["fur"]
    up = pose.get("trunk", 0)
    sway = 0.2 * math.sin(TAU * t / 2.2)
    pts = [(0.0, -hr * 0.1)]
    a = -math.pi / 2 + sway + up * 2.0
    for k in range(8):
        a += 0.04 + up * 0.15 + sway * 0.05
        lx, ly = pts[-1]
        pts.append((lx + math.cos(a) * hr * 0.18, ly + math.sin(a) * hr * 0.18))
    for k in range(len(pts) - 1):
        w = hr * 0.44 * (1 - 0.5 * k / len(pts))
        _stroke(ctx, [pts[k], pts[k + 1]], w, fur, alpha, darker(fur, 0.58), ow)
    for k in range(len(pts) - 1):
        w = hr * 0.44 * (1 - 0.5 * k / len(pts))
        _stroke(ctx, [pts[k], pts[k + 1]], w, fur, alpha)
    ctx.set_source_rgba(*darker(fur, 0.75), alpha)
    ctx.set_line_width(1.5 * s)
    for p in pts[1:-1:2]:
        ctx.move_to(p[0] - hr * 0.12, p[1])
        ctx.line_to(p[0] + hr * 0.12, p[1])
    ctx.stroke()


def _head_back(ctx, sp, hr, alpha, ow, t, pose, s):
    """Back of the head: fur, ears, horns - no face."""
    fur = sp["fur"]
    fo = darker(fur, 0.58)
    ctx.set_line_width(ow)
    _horns(ctx, sp, hr, alpha, s)
    _ellipse(ctx, 0, 0, hr * 1.0, hr * 0.95)
    _fill(ctx, darker(fur, 0.95), alpha, fo, ow)
    if sp.get("pattern") == "stripes":
        ctx.set_source_rgba(0.12, 0.08, 0.06, alpha)
        for k in range(3):
            _ellipse(ctx, 0, hr * (0.55 - k * 0.35), hr * 0.35, hr * 0.06)
            ctx.fill()
    _ears(ctx, sp, hr, darker(fur, 0.9), fo, alpha, ow, pose.get("ear", 0))
    if sp.get("ears") == "floppy":
        for sx in (-1, 1):
            _ellipse(ctx, sx * hr * 0.92, 0, hr * 0.26, hr * 0.62, sx * 0.25)
            _fill(ctx, darker(fur, 0.75), alpha, fo, ow)
