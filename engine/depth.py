"""2.5D depth: perspective ground, depth <-> layer mapping, front/back character views, mood lighting,
focus blur, foreground leaves and rim light.

Depth "z": 0 = front (normal ground line) ... 1000 = far back near the horizon.
A character at depth z is drawn in the parallax layer p(z) - the same layers the background uses -
so it passes behind near trees, in front of far trees, shrinks, rises toward the horizon and gets hazy.
"""
import math

import cairo

from .util import clamp, lerp, smoothstep, mix, darker, lighter, TAU

P_HORIZON = 0.42         # layer of the far edge of the walkable ground
LIFT = 175.0             # how much higher (world units) the far ground sits


def p_of_z(z):
    return 1.0 - (1.0 - P_HORIZON) * clamp(z / 1000.0, 0.0, 1.0)


def lift_of_p(p):
    return LIFT * (1.0 - p) if p < 1.0 else 0.0


Z_NAMES = {"front": 0, "near": 0, "middle": 450, "mid": 450, "back": 700, "far_back": 950, "far": 950,
           "horizon": 1000, "distance": 950,
           # 3D mode only: deeper than the stage, into the distance
           "far_away": 1800, "deep": 1800, "very_far": 2500, "vanish": 3000, "disappear_far": 3000}


# ============================================================================ mood lighting
MOODS = {
    "normal": dict(),
    "dark_jungle": dict(tint=(0.05, 0.18, 0.08, 0.38), beams=0.55, vignette=0.45),
    "sunbeams": dict(beams=0.8, tint=(1.0, 0.85, 0.5, 0.06)),
    "mist": dict(mist=0.8, tint=(0.85, 0.9, 0.95, 0.12)),
    "spooky": dict(tint=(0.12, 0.08, 0.3, 0.42), vignette=0.65, mist=0.4),
    "warm_glow": dict(tint=(1.0, 0.55, 0.2, 0.15), vignette=0.3),
    "night": dict(tint=(0.05, 0.08, 0.25, 0.4), vignette=0.4),
    "dream": dict(tint=(0.6, 0.45, 0.95, 0.18), vignette=0.35, mist=0.3),
    "danger": dict(tint=(0.6, 0.05, 0.05, 0.2), vignette=0.55),
}
MOOD_ALIASES = {"dark": "dark_jungle", "jungle": "dark_jungle", "beams": "sunbeams", "god_rays": "sunbeams",
                "fog": "mist", "foggy": "mist", "scary": "spooky", "horror": "spooky", "warm": "warm_glow",
                "golden": "warm_glow", "cozy": "warm_glow", "magic": "dream", "magical": "dream", "red": "danger",
                "bright": "normal", "clear": "normal", "none": "normal"}


def mood_name(m):
    m = str(m or "normal").lower().strip()
    m = MOOD_ALIASES.get(m, m)
    return m if m in MOODS else "normal"


def mood_params(changes, t):
    """changes: [(start, name, fade)] -> blended parameter dict at time t."""
    cur, prev, w = MOODS["normal"], MOODS["normal"], 1.0
    for st, name, fade in changes:
        if st <= t:
            prev, cur = cur, MOODS[name]
            w = smoothstep((t - st) / max(fade, 0.01))
    out = {}
    for k in set(cur) | set(prev):
        a, b = prev.get(k), cur.get(k)
        if k == "tint":
            a = a or (b[0], b[1], b[2], 0.0)
            b = b or (a[0], a[1], a[2], 0.0)
            out[k] = tuple(lerp(x, y, w) for x, y in zip(a, b))
        else:
            out[k] = lerp(a or 0.0, b or 0.0, w)
    return out


def draw_mood(ctx, prm, t, W, H):
    if not prm:
        return
    ctx.identity_matrix()
    k = H / 1080.0
    beams = prm.get("beams", 0)
    if beams > 0.01:
        for i in range(5):
            x = W * (0.12 + 0.2 * i) + 40 * k * math.sin(t * 0.3 + i)
            w = (60 + 50 * (i % 3)) * k
            a = beams * (0.10 + 0.05 * math.sin(t * 0.7 + i * 1.7))
            g = cairo.LinearGradient(x, 0, x - 260 * k, H)
            g.add_color_stop_rgba(0, 1, 0.95, 0.75, a)
            g.add_color_stop_rgba(1, 1, 0.95, 0.75, 0)
            ctx.set_source(g)
            ctx.move_to(x - w / 2, 0)
            ctx.line_to(x + w / 2, 0)
            ctx.line_to(x + w / 2 - 300 * k, H)
            ctx.line_to(x - w / 2 - 380 * k, H)
            ctx.close_path()
            ctx.fill()
        for i in range(24):                               # dust in the light
            px = (W * ((i * 0.618) % 1) + t * 12 * k * (1 + i % 3)) % W
            py = (H * ((i * 0.37) % 1) + 20 * k * math.sin(t + i)) % H
            ctx.arc(px, py, 2.2 * k, 0, TAU)
            ctx.set_source_rgba(1, 0.95, 0.7, 0.5 * beams * (0.5 + 0.5 * math.sin(t * 2 + i)))
            ctx.fill()
    tint = prm.get("tint")
    if tint and tint[3] > 0.005:
        ctx.set_source_rgba(*tint)
        ctx.paint()
    mist = prm.get("mist", 0)
    if mist > 0.01:
        for i in range(5):
            y = H * (0.55 + 0.09 * i)
            x = ((t * (18 + 8 * i) * k) + i * 400 * k) % (W + 800 * k) - 400 * k
            for dx in (0, W * 0.6):
                g = cairo.RadialGradient(x + dx, y, 10, x + dx, y, 420 * k)
                g.add_color_stop_rgba(0, 0.92, 0.94, 0.97, 0.28 * mist)
                g.add_color_stop_rgba(1, 0.92, 0.94, 0.97, 0)
                ctx.set_source(g)
                ctx.save()
                ctx.translate(x + dx, y)
                ctx.scale(1.0, 0.35)
                ctx.translate(-(x + dx), -y)
                ctx.arc(x + dx, y, 420 * k, 0, TAU)
                ctx.fill()
                ctx.restore()
    vig = prm.get("vignette", 0)
    if vig > 0.01:
        g = cairo.RadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.95)
        g.add_color_stop_rgba(0, 0, 0, 0, 0)
        g.add_color_stop_rgba(1, 0, 0, 0, 0.75 * vig)
        ctx.set_source(g)
        ctx.paint()


# ============================================================================ blur helpers
def blur_surface(src, radius_div=6):
    """Cheap high-quality blur: downscale then upscale with bilinear filtering (twice)."""
    w, h = src.get_width(), src.get_height()
    sw, sh = max(1, w // radius_div), max(1, h // radius_div)
    small = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
    c = cairo.Context(small)
    c.scale(sw / w, sh / h)
    pat = cairo.SurfacePattern(src)
    pat.set_filter(cairo.FILTER_GOOD)
    c.set_source(pat)
    c.paint()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    c2 = cairo.Context(out)
    c2.scale(w / sw, h / sh)
    pat2 = cairo.SurfacePattern(small)
    pat2.set_filter(cairo.FILTER_BILINEAR)
    c2.set_source(pat2)
    c2.paint()
    return out


# ============================================================================ foreground leaves
def draw_foreground_leaves(ctx, cam, t, W, H, S, strength=1.0, seed=3):
    """Soft, dark leaves very close to the camera along the TOP and BOTTOM edges of the frame.
    They move faster than everything else (parallax p = 1.8) but never cover the middle of the picture."""
    import random
    rr = random.Random(seed)
    ctx.identity_matrix()
    p = 1.8
    span = W * 1.8
    for i in range(9):
        base = rr.uniform(0, span)
        x = (base - cam.x * S * p * 0.9 + t * 20 * S) % span - W * 0.4
        top = i % 2 == 0
        sc = rr.uniform(0.55, 0.95) * S
        y = rr.uniform(-60, -10) * S if top else H + rr.uniform(10, 70) * S
        ang = rr.uniform(-0.5, 0.5) + 0.07 * math.sin(t * 1.3 + i)
        col = rr.choice([(0.07, 0.24, 0.1), (0.1, 0.3, 0.13), (0.06, 0.2, 0.09)])
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(ang + (0 if top else math.pi))
        for j in range(5):
            ctx.save()
            ctx.rotate(-0.9 + j * 0.45)
            ctx.scale(sc, sc)
            g = cairo.RadialGradient(0, 120, 10, 0, 120, 150)
            g.add_color_stop_rgba(0, *col, 0.9 * strength)
            g.add_color_stop_rgba(0.75, *col, 0.8 * strength)
            g.add_color_stop_rgba(1, *col, 0.0)
            ctx.set_source(g)
            ctx.move_to(0, 0)
            ctx.curve_to(-60, 60, -50, 200, 0, 260)
            ctx.curve_to(50, 200, 60, 60, 0, 0)
            ctx.fill()
            ctx.restore()
        ctx.restore()


# ============================================================================ front / back view (people)
def draw_front_view(ctx, c, pose, x, y, view, face, mouth, t, alpha, blink, scale_mul=1.0, astride=0.0):
    """Symmetric front ("camera") or back ("away") view of a cartoon person. World coords, y-up."""
    if getattr(c, "kind", "human") == "quadruped":
        from .animal_front import draw_quad_front
        return draw_quad_front(ctx, c, pose, x, y, view, face, mouth, t, alpha, blink, scale_mul)
    if getattr(c, "look", None):
        from . import puppet
        if puppet.has_front(c, view):
            return puppet.draw_front(ctx, c, pose, x, y, view, face, mouth, t, alpha, blink, astride, scale_mul)
        if puppet.available(c.look):              # no front/back sheet: the side view, turned a little
            from .character import draw_character
            return draw_character(ctx, c, pose, x, 1, face, mouth, t, None, alpha, blink, False, y)
    from .character import _head, _hair_back, _stroke, _dot, draw_shadow, BONES
    s = c.scale * scale_mul
    from .character import KID_AGES, body_of, head_k
    child = c.age in KID_AGES
    hr = BONES["head_r"] * head_k(c) * s
    bd = body_of(c) or {}
    LK, AK, TK = bd.get("leg", 1.0), bd.get("arm", 1.0), bd.get("torso", 1.0)       # babies / toddlers
    K = s * c.thickness
    OW = 2.6 * K
    skin = c.skin
    so = darker(skin, 0.62)
    top = c.top or skin
    bottom = c.bottom or skin
    arm_w, leg_w = 11.5 * K * c.build ** 0.4, 13.5 * K * c.build ** 0.4
    tw = (30 if c.gender == "female" else 36) * K * c.build
    lift = pose.get("lift", 0.0) * s
    # walking in place: legs alternate
    ph = (pose.get("ln_t", 0) - pose.get("lf_t", 0)) / 48.0
    lk, rk = max(0.0, ph), max(0.0, -ph)
    thigh, shin = BONES["thigh"] * s * LK, BONES["shin"] * s * LK
    leg_len = thigh + shin
    hip_y = y + leg_len + lift
    neck_y = hip_y + BONES["torso"] * s * TK
    if astride <= 0:
        draw_shadow(ctx, x, lift / max(s, 0.1), 34 * s * c.build ** 0.5, alpha, y)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    back = view == "away"
    # legs
    if astride > 0:                  # sitting on an animal: hips on its back, legs around its body
        lk = rk = 0.0
        hip_y = y + leg_len
        neck_y = hip_y + BONES["torso"] * s * TK
    for side, k in ((-1, lk), (1, rk)):
        fx = x + side * tw * 0.28
        foot_y = y + lift + 26 * s * k
        knee = (fx + side * 4 * s, hip_y - thigh * (1 - 0.35 * k))
        if astride > 0:
            knee = (x + side * (astride + 6 * s), hip_y - thigh * 0.45)
            foot_y = hip_y - thigh * 0.45 - shin * 0.8
            fx = x + side * (astride * 0.92)
        kind = c.bottom_kind
        col = bottom if kind in ("pants", "dhoti") else skin
        _stroke(ctx, [(fx, hip_y), knee, (fx, foot_y)], leg_w * (1.08 if kind == "pants" else 0.95), col, alpha,
                darker(col, 0.62), OW)
        _stroke(ctx, [(fx - side * 3 * s, foot_y), (fx + side * 5 * s, foot_y)], leg_w * 1.05, c.shoes, alpha,
                darker(c.shoes, 0.55), OW)
    # arms (behind body when seen from back)
    def arm(side, up_deg, low_deg):
        sx_, sy_ = x + side * tw * 0.55, neck_y - 10 * s
        a1 = math.radians(abs(up_deg) * 0.55)
        ex_ = sx_ + side * math.sin(a1) * BONES["upper_arm"] * s * AK
        ey_ = sy_ - math.cos(a1) * BONES["upper_arm"] * s * AK
        a2 = a1 + math.radians(abs(low_deg) * 0.35)
        hx_ = ex_ + side * math.sin(a2) * BONES["fore_arm"] * s * AK
        hy_ = ey_ - math.cos(a2) * BONES["fore_arm"] * s * AK
        if c.sleeves == "long":
            _stroke(ctx, [(sx_, sy_), (ex_, ey_), (hx_, hy_)], arm_w * 1.08, top, alpha, darker(top, 0.62), OW)
        else:
            _stroke(ctx, [(ex_, ey_), (hx_, hy_)], arm_w, skin, alpha, so, OW)
            _stroke(ctx, [(sx_, sy_), (lerp(sx_, ex_, 0.7), lerp(sy_, ey_, 0.7))], arm_w * 1.25, top, alpha,
                    darker(top, 0.62), OW)
        _dot(ctx, (hx_, hy_), arm_w * 0.72, skin, alpha, so, OW * 0.8)
        return hx_, hy_
    hand_r = arm(1, pose.get("an_u", 8), pose.get("an_l", 8))
    arm(-1, pose.get("af_u", -6), pose.get("af_l", 8))
    # torso
    g = cairo.LinearGradient(x - tw / 2, 0, x + tw / 2, 0)
    g.add_color_stop_rgba(0, *darker(top, 0.82), alpha)
    g.add_color_stop_rgba(0.5, *lighter(top, 0.06), alpha)
    g.add_color_stop_rgba(1, *darker(top, 0.82), alpha)
    ctx.new_path()
    r = tw / 2
    ctx.move_to(x - r, hip_y)
    ctx.line_to(x - r, neck_y - r * 0.6)
    ctx.curve_to(x - r, neck_y, x + r, neck_y, x + r, neck_y - r * 0.6)
    ctx.line_to(x + r, hip_y)
    ctx.close_path()
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_source_rgba(*darker(top, 0.6), alpha)
    ctx.set_line_width(OW)
    ctx.stroke()
    if c.bottom_kind in ("skirt", "long_skirt") or c.tunic:
        L = (leg_len * (0.95 if c.bottom_kind == "long_skirt" else 0.5)) if c.bottom_kind in ("skirt", "long_skirt") \
            else leg_len * 0.3 * c.tunic
        colr = bottom if c.bottom_kind in ("skirt", "long_skirt") else top
        ctx.move_to(x - r, hip_y + 10 * s)
        ctx.line_to(x + r, hip_y + 10 * s)
        ctx.line_to(x + r * 1.45, hip_y - L)
        ctx.line_to(x - r * 1.45, hip_y - L)
        ctx.close_path()
        ctx.set_source_rgba(*colr, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*darker(colr, 0.6), alpha)
        ctx.stroke()
    if not back and "tie" in c.extras:
        _stroke(ctx, [(x, neck_y - 6 * s), (x, neck_y - 55 * s)], 7 * s, c.accent, alpha)
    # neck + head
    _stroke(ctx, [(x, neck_y), (x, neck_y + 12 * s)], 10 * s, skin, alpha, so, OW)
    hx, hy = x, neck_y + 12 * s + hr * 0.95
    ctx.save()
    ctx.translate(hx, hy)
    if back:
        ctx.arc(0, 0, hr, 0, TAU)
        ctx.set_source_rgba(*skin, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*so, alpha)
        ctx.set_line_width(OW)
        ctx.stroke()
        if c.hair not in ("bald",):
            ctx.arc(0, 0, hr * 1.04, 0, TAU)
            ctx.set_source_rgba(*c.hair_color, alpha)
            ctx.fill()
            if c.hair in ("long", "braid"):
                ctx.rectangle(-hr * 0.8, -hr * 1.6, hr * 1.6, hr * 1.6)
                ctx.fill()
            if c.hair == "ponytail":                          # tie + tail hanging down the back
                sw = 0.08 * math.sin(t * 3.0)
                ctx.move_to(-hr * 0.22, hr * 0.2)
                ctx.curve_to(-hr * 0.5, -hr * 0.6, -hr * 0.25 + sw * hr, -hr * 1.5, sw * hr * 2, -hr * 1.75)
                ctx.curve_to(hr * 0.25 + sw * hr, -hr * 1.5, hr * 0.5, -hr * 0.6, hr * 0.22, hr * 0.2)
                ctx.close_path()
                ctx.fill()
                ctx.set_source_rgba(*c.accent, alpha)
                ctx.arc(0, hr * 0.15, hr * 0.17, 0, TAU)
                ctx.fill()
            if c.hair == "bun":
                ctx.arc(0, hr * 0.7, hr * 0.42, 0, TAU)
                ctx.fill()
        from .character import _hat
        _hat(ctx, c, hr, alpha, OW)
    else:
        if c.hair == "ponytail":                              # tail swinging out behind one side of the head
            sw = 0.1 * math.sin(t * 3.0)
            ctx.move_to(hr * 0.55, hr * 0.75)
            ctx.curve_to(hr * 1.5, hr * (0.9 + sw), hr * 1.75, hr * 0.1, hr * (1.5 + sw), -hr * 0.9)
            ctx.curve_to(hr * 1.35, -hr * 0.2, hr * 1.1, hr * 0.3, hr * 0.7, hr * 0.35)
            ctx.close_path()
            ctx.set_source_rgba(*c.hair_color, alpha)
            ctx.fill_preserve()
            ctx.set_source_rgba(*darker(c.hair_color, 0.6), alpha)
            ctx.set_line_width(OW * 0.8)
            ctx.stroke()
        _front_face(ctx, c, hr, face, mouth, blink, alpha, OW)
    ctx.restore()
    return {"hand": hand_r, "head": (hx, hy), "hip": (x, hip_y), "head_r": hr, "mouth": (hx, hy - 0.4 * hr)}


def _front_face(ctx, c, r, face, mouth, blink, alpha, ow):
    from .character import _hat, darker as _dk
    skin, so = c.skin, darker(c.skin, 0.62)
    # hair behind for long styles
    if c.hair in ("long", "braid"):
        ctx.rectangle(-r * 1.02, -r * 1.3, r * 2.04, r * 1.4)
        ctx.set_source_rgba(*c.hair_color, alpha)
        ctx.fill()
    for sx in (-1, 1):                                  # ears
        ctx.arc(sx * r * 0.98, -r * 0.05, r * 0.2, 0, TAU)
        ctx.set_source_rgba(*skin, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*so, alpha)
        ctx.set_line_width(ow * 0.8)
        ctx.stroke()
    ctx.arc(0, 0, r, 0, TAU)
    g = cairo.RadialGradient(0, r * 0.3, r * 0.1, 0, 0, r * 1.05)
    g.add_color_stop_rgba(0, *lighter(skin, 0.12), alpha)
    g.add_color_stop_rgba(1, *darker(skin, 0.88), alpha)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_source_rgba(*so, alpha)
    ctx.set_line_width(ow)
    ctx.stroke()
    dark = (0.12, 0.1, 0.1)
    closed = blink or face in ("sleeping", "crying")
    for sx in (-1, 1):
        ex, ey = sx * r * 0.36, r * 0.1
        if closed or face == "laughing":
            ctx.move_to(ex - r * 0.13, ey)
            ctx.curve_to(ex - r * 0.05, ey + (0.1 if face == "laughing" else -0.08) * r,
                         ex + r * 0.05, ey + (0.1 if face == "laughing" else -0.08) * r, ex + r * 0.13, ey)
            ctx.set_source_rgba(*dark, alpha)
            ctx.set_line_width(ow * 1.1)
            ctx.stroke()
        else:
            big = 1.25 if face in ("surprised", "scared") else 1.0
            ctx.save()
            ctx.translate(ex, ey)
            ctx.scale(0.15 * r * big, 0.19 * r * big)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(1, 1, 1, alpha)
            ctx.fill_preserve()
            ctx.set_source_rgba(*dark, alpha * 0.8)
            ctx.set_line_width(ow * 0.6)
            ctx.stroke()
            ctl_ = getattr(mouth, "ctl", None) or {}
            gx_, gy_ = float(ctl_.get("gx", 0.0)), float(ctl_.get("gy", 0.0))   # where the eyes look
            px_, py_ = ex + gx_ * 0.06 * r, ey - 0.01 * r + gy_ * 0.07 * r
            ctx.arc(px_, py_, 0.085 * r, 0, TAU)
            ctx.set_source_rgba(*dark, alpha)
            ctx.fill()
            ctx.arc(px_ + 0.03 * r, py_ + 0.04 * r, 0.03 * r, 0, TAU)
            ctx.set_source_rgba(1, 1, 1, alpha)
            ctx.fill()
        # brows
        by = 0.4 * r
        ctx.set_source_rgba(*darker(c.hair_color, 0.9), alpha)
        ctx.set_line_width(ow * 1.2)
        inner = -sx
        if face == "angry":
            ctx.move_to(ex - inner * 0.14 * r, by + 0.06 * r)
            ctx.line_to(ex + inner * 0.1 * r, by - 0.06 * r)
        elif face in ("sad", "crying", "scared"):
            ctx.move_to(ex - inner * 0.14 * r, by - 0.05 * r)
            ctx.line_to(ex + inner * 0.1 * r, by + 0.06 * r)
        else:
            ctx.move_to(ex - 0.12 * r, by)
            ctx.curve_to(ex - 0.04 * r, by + 0.05 * r, ex + 0.04 * r, by + 0.05 * r, ex + 0.12 * r, by)
        ctx.stroke()
    if face in ("happy", "laughing"):
        for sx in (-1, 1):
            ctx.save()
            ctx.translate(sx * r * 0.55, -0.25 * r)
            ctx.scale(0.16 * r, 0.09 * r)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(1, 0.45, 0.5, 0.35 * alpha)
            ctx.fill()
    # nose
    ctx.move_to(-0.05 * r, -0.08 * r)
    ctx.curve_to(0, -0.2 * r, 0.06 * r, -0.2 * r, 0.05 * r, -0.12 * r)
    ctx.set_source_rgba(*so, alpha)
    ctx.set_line_width(ow * 0.8)
    ctx.stroke()
    my, mw = -0.45 * r, 0.36 * r
    if mouth > 0.06:
        h = (0.06 + 0.3 * mouth) * r
        ctx.save()
        ctx.translate(0, my)
        ctx.scale(mw * 0.55, h)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(0.45, 0.1, 0.12, alpha)
        ctx.fill()
    elif face in ("happy", "laughing"):
        ctx.move_to(-mw * 0.6, my + 0.05 * r)
        ctx.curve_to(-mw * 0.3, my - 0.24 * r, mw * 0.3, my - 0.24 * r, mw * 0.6, my + 0.05 * r)
        ctx.close_path()
        ctx.set_source_rgba(0.45, 0.1, 0.12, alpha)
        ctx.fill()
    elif face in ("surprised", "scared"):
        ctx.save()
        ctx.translate(0, my)
        ctx.scale(0.1 * r, 0.13 * r)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(0.45, 0.1, 0.12, alpha)
        ctx.fill()
    else:
        sad = face in ("sad", "crying", "angry")
        ctx.move_to(-mw / 2, my + (-0.06 if sad else 0.04) * r)
        ctx.curve_to(-mw / 4, my + (0.05 if sad else -0.08) * r, mw / 4, my + (0.05 if sad else -0.08) * r,
                     mw / 2, my + (-0.06 if sad else 0.04) * r)
        ctx.set_source_rgba(0.3, 0.12, 0.1, alpha)
        ctx.set_line_width(ow * 1.1)
        ctx.stroke()
    if c.mustache:
        ctx.move_to(-0.25 * r, -0.3 * r)
        ctx.curve_to(-0.1 * r, -0.22 * r, 0.1 * r, -0.22 * r, 0.25 * r, -0.3 * r)
        ctx.set_source_rgba(*c.hair_color, alpha)
        ctx.set_line_width(0.12 * r)
        ctx.stroke()
    if c.beard:
        ctx.move_to(-0.75 * r, -0.2 * r)
        ctx.curve_to(-0.6 * r, -1.3 * r, 0.6 * r, -1.3 * r, 0.75 * r, -0.2 * r)
        ctx.curve_to(0.4 * r, -0.62 * r, -0.4 * r, -0.62 * r, -0.75 * r, -0.2 * r)
        ctx.set_source_rgba(*c.hair_color, alpha)
        ctx.fill()
    # hair on top (symmetric)
    hat_covers = c.hat in ("top", "turban", "police", "cap", "crown", "straw", "helmet", "hard_hat", "fire_helmet",
                           "chef", "pilot", "beret")
    if c.hair not in ("bald",) and not (hat_covers and c.hair not in ("long", "ponytail", "braid")):
        ctx.arc(0, 0, r * 1.06, math.radians(15), math.radians(165))
        ctx.curve_to(-r * 0.6, r * 0.45, r * 0.6, r * 0.45, r * 1.02, r * 0.28)
        ctx.close_path()
        ctx.set_source_rgba(*c.hair_color, alpha)
        ctx.fill()
        if c.hair == "bun":
            ctx.arc(0, r * 1.05, r * 0.36, 0, TAU)
            ctx.fill()
        if c.hair == "spiky":
            for k in range(5):
                a = math.radians(40 + k * 25)
                ctx.move_to(math.cos(a) * r * 0.9, math.sin(a) * r * 0.9)
                ctx.line_to(math.cos(a) * r * 1.45, math.sin(a) * r * 1.45)
                ctx.line_to(math.cos(a + 0.25) * r * 0.95, math.sin(a + 0.25) * r * 0.95)
                ctx.fill()
    if c.glasses:
        ctx.set_source_rgba(0.15, 0.15, 0.18, alpha)
        ctx.set_line_width(ow * 0.9)
        for sx in (-1, 1):
            ctx.arc(sx * r * 0.36, r * 0.1, r * 0.22, 0, TAU)
            ctx.stroke()
        ctx.move_to(-r * 0.14, r * 0.12)
        ctx.line_to(r * 0.14, r * 0.12)
        ctx.stroke()
    ctx.save()
    ctx.translate(0.0, 0.0)
    _hat(ctx, c, r, alpha, ow)
    ctx.restore()


# ============================================================================ rim light
def rim_light(ctx, draw_fn, bbox, light_dx, color=(1.0, 0.85, 0.55), strength=0.9):
    """Draw a character with a coloured edge on the light side.
    draw_fn(ctx) draws the character in the CURRENT transform; bbox=(x0,y0,x1,y1) in device pixels."""
    x0, y0, x1, y1 = [int(v) for v in bbox]
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    c2 = cairo.Context(surf)
    c2.translate(-x0, -y0)
    c2.transform(ctx.get_matrix())
    draw_fn(c2)
    ctx.save()
    ctx.identity_matrix()
    ctx.set_source_rgba(*color, strength)
    ctx.mask_surface(surf, x0 + light_dx, y0 - abs(light_dx) * 0.4)
    ctx.set_source_surface(surf, x0, y0)
    ctx.paint()
    ctx.restore()
