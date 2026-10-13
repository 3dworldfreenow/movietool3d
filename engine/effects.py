"""Emotion icons (! ? heart idea sweat anger stars music) and particle effects
(dust, confetti, sparkle/magic, smoke, fire, splash, hearts, explosion, leaves, lightning).

Everything is computed analytically from time, so any frame can be rendered independently
(which is what lets rendering run in parallel).
"""
import math
import random

import cairo

from .util import clamp, TAU, smoothstep, stable_hash

ICON_LIFE = 1.8



def _wind_drift(t):
    """How far smoke drifts with the scene wind over its life (engine/realworld.py)."""
    from .realworld import wind
    return wind().speed(t) * 0.6

def _text(ctx, x, y, txt, size, rgb, alpha, bold=True):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(1, -1)
    ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ext = ctx.text_extents(txt)
    ctx.move_to(-ext.width / 2 - ext.x_bearing, ext.height / 2)
    ctx.set_source_rgba(*rgb, alpha)
    ctx.show_text(txt)
    ctx.restore()


def _heart(ctx, x, y, r):
    ctx.move_to(x, y - r)
    ctx.curve_to(x - r * 1.6, y + r * 0.2, x - r * 0.8, y + r * 1.3, x, y + r * 0.5)
    ctx.curve_to(x + r * 0.8, y + r * 1.3, x + r * 1.6, y + r * 0.2, x, y - r)
    ctx.close_path()


def _star(ctx, x, y, r, rot=0.0):
    for k in range(10):
        rr = r if k % 2 == 0 else r * 0.45
        a = rot + math.pi / 2 + k * math.pi / 5
        (ctx.move_to if k == 0 else ctx.line_to)(x + rr * math.cos(a), y + rr * math.sin(a))
    ctx.close_path()


def draw_icon(ctx, kind, head, head_r, facing, age, s):
    """Pop-in icon above/next to a character's head (world coords, y-up)."""
    if age < 0 or age > ICON_LIFE:
        return
    pop = 1.0 + 0.35 * math.sin(math.pi * clamp(age / 0.25, 0, 1)) if age < 0.25 else 1.0
    pop *= smoothstep(age / 0.12)
    alpha = 1.0 - smoothstep((age - ICON_LIFE + 0.35) / 0.35)
    hx, hy = head
    x, y = hx + facing * head_r * 0.9, hy + head_r * 1.9 + 8 * age
    k = s * pop * 1.15
    kind = {"exclaim": "!", "question": "?", "love": "heart", "bulb": "idea", "dizzy": "stars"}.get(kind, kind)
    ctx.save()
    if kind in ("!", "?"):
        col = (0.9, 0.15, 0.15) if kind == "!" else (0.15, 0.4, 0.85)
        ctx.arc(x, y, 26 * k, 0, TAU)
        ctx.set_source_rgba(1, 1, 1, 0.95 * alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(*col, alpha)
        ctx.set_line_width(4 * k)
        ctx.stroke()
        _text(ctx, x, y, kind, 38 * k, col, alpha)
    elif kind == "heart":
        for j, (dx, dy, rr) in enumerate(((0, 0, 16), (-26, -18, 9), (24, -24, 7))):
            _heart(ctx, x + dx * k, y + dy * k + j * 6 * age * s, rr * k)
            ctx.set_source_rgba(0.93, 0.2, 0.35, alpha)
            ctx.fill()
    elif kind == "idea":
        ctx.arc(x, y + 6 * k, 18 * k, 0, TAU)
        ctx.set_source_rgba(1, 0.88, 0.25, alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(0.75, 0.55, 0.05, alpha)
        ctx.set_line_width(3 * k)
        ctx.stroke()
        ctx.rectangle(x - 8 * k, y - 22 * k, 16 * k, 12 * k)
        ctx.set_source_rgba(0.5, 0.5, 0.55, alpha)
        ctx.fill()
        ctx.set_source_rgba(1, 0.8, 0.1, alpha)
        ctx.set_line_width(3.5 * k)
        for a in range(-60, 241, 50):
            ar = math.radians(a)
            ctx.move_to(x + math.cos(ar) * 26 * k, y + 6 * k + math.sin(ar) * 26 * k)
            ctx.line_to(x + math.cos(ar) * 36 * k, y + 6 * k + math.sin(ar) * 36 * k)
        ctx.stroke()
    elif kind == "sweat":
        sx, sy = hx - facing * head_r * 0.2, hy + head_r * 0.9 - 30 * age * s
        ctx.move_to(sx, sy + 16 * k)
        ctx.curve_to(sx - 10 * k, sy, sx - 10 * k, sy - 10 * k, sx, sy - 10 * k)
        ctx.curve_to(sx + 10 * k, sy - 10 * k, sx + 10 * k, sy, sx, sy + 16 * k)
        ctx.set_source_rgba(0.45, 0.75, 1.0, alpha)
        ctx.fill()
    elif kind == "anger":
        ctx.set_source_rgba(0.9, 0.1, 0.1, alpha)
        ctx.set_line_width(5 * k)
        for a in range(4):
            ar = math.radians(45 + a * 90)
            cx, cy = x + math.cos(ar) * 10 * k, y + math.sin(ar) * 10 * k
            ctx.arc(cx, cy, 9 * k, ar + 2.0, ar + 4.3)
            ctx.stroke()
    elif kind == "stars":
        for j in range(3):
            a = age * 5 + j * TAU / 3
            _star(ctx, hx + math.cos(a) * head_r * 1.2, hy + head_r * 1.1 + math.sin(a) * head_r * 0.35, 11 * k, a)
            ctx.set_source_rgba(1, 0.85, 0.15, alpha)
            ctx.fill()
    elif kind == "music":
        for j in range(2):
            nx, ny = x + (j * 26 - 10) * k + 6 * math.sin(age * 4 + j), y + j * 14 * k + age * 20 * s
            ctx.set_source_rgba(0.2, 0.25, 0.45, alpha)
            ctx.save()
            ctx.translate(nx, ny)
            ctx.scale(8 * k, 6 * k)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.fill()
            ctx.set_line_width(3 * k)
            ctx.move_to(nx + 7 * k, ny)
            ctx.line_to(nx + 7 * k, ny + 30 * k)
            ctx.line_to(nx + 17 * k, ny + 24 * k)
            ctx.stroke()
    elif kind == "zzz":
        _text(ctx, x, y, "Zz", 30 * k, (0.25, 0.3, 0.55), alpha)
    # ---- anime reactions (on the face itself)
    elif kind == "blush":                                  # pink cheeks with little lines
        cx, cy = hx + facing * head_r * 0.42, hy - head_r * 0.28
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(head_r * 0.3, head_r * 0.16)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(1.0, 0.45, 0.55, 0.75 * alpha)
        ctx.fill()
        ctx.set_source_rgba(0.9, 0.25, 0.35, 0.8 * alpha)
        ctx.set_line_width(max(1.0, head_r * 0.05))
        for j in (-1, 0, 1):
            ctx.move_to(cx + (j * 0.14 - 0.05) * head_r, cy - 0.07 * head_r)
            ctx.line_to(cx + (j * 0.14 + 0.05) * head_r, cy + 0.07 * head_r)
        ctx.stroke()
    elif kind in ("tears", "crying_river"):                # anime tear streams
        ex, ey = hx + facing * head_r * 0.42, hy + head_r * 0.05
        ctx.set_source_rgba(0.45, 0.75, 1.0, 0.85 * alpha)
        for j, off in enumerate((0.0, 0.18)):
            L = head_r * (0.8 + 2.6 * clamp(age / 0.6, 0, 1)) * (1 - 0.3 * j)
            w0 = head_r * 0.13
            ctx.move_to(ex + facing * off * head_r - w0, ey)
            ctx.curve_to(ex + facing * off * head_r - w0 * 1.4, ey - L * 0.5, ex + facing * off * head_r - w0,
                         ey - L * 0.8, ex + facing * off * head_r, ey - L)
            ctx.curve_to(ex + facing * off * head_r + w0, ey - L * 0.8, ex + facing * off * head_r + w0 * 1.4,
                         ey - L * 0.5, ex + facing * off * head_r + w0, ey)
            ctx.close_path()
            ctx.fill()
    elif kind in ("shock", "big_eyes"):                    # huge white eyes with tiny pupils
        for j, (dx, rr) in enumerate(((0.55, 0.3), (0.12, 0.24))):
            ex, ey = hx + facing * dx * head_r, hy + head_r * 0.12
            ctx.arc(ex, ey, rr * head_r * min(1.0, pop), 0, TAU)
            ctx.set_source_rgba(1, 1, 1, alpha)
            ctx.fill_preserve()
            ctx.set_source_rgba(0.1, 0.1, 0.12, alpha)
            ctx.set_line_width(max(1.0, head_r * 0.06))
            ctx.stroke()
            ctx.arc(ex + facing * rr * head_r * 0.25, ey, rr * head_r * 0.22, 0, TAU)
            ctx.fill()
    elif kind in ("gloom", "despair"):                     # dark lines hanging over the head
        ctx.set_source_rgba(0.2, 0.15, 0.35, 0.7 * alpha)
        ctx.set_line_width(max(1.5, head_r * 0.07))
        for j in range(5):
            gx = hx + (j - 2) * head_r * 0.28
            ctx.move_to(gx, hy + head_r * 1.3)
            ctx.line_to(gx, hy + head_r * (0.2 + 0.15 * (j % 2)))
        ctx.stroke()
    ctx.restore()


# --------------------------------------------------------------------------- particles
# anime screen effects (drawn over the whole frame by anime_fx())
SCREEN_FX = {"speed_lines": "speed_lines", "action_lines": "speed_lines", "focus_lines": "speed_lines",
             "concentration_lines": "speed_lines", "run_lines": "run_lines", "motion_lines": "run_lines",
             "impact": "impact", "impact_frame": "impact", "hit_flash": "impact", "rays": "rays", "shine": "rays",
             "glory": "rays", "gloom": "gloom_bg", "despair_bg": "gloom_bg", "dark_lines": "gloom_bg",
             "sparkle_bg": "sparkle_bg", "shoujo": "sparkle_bg", "sparkles_bg": "sparkle_bg", "swirl": "swirl",
             "dizzy_bg": "swirl", "flash": "white_flash", "white_flash": "white_flash"}


def anime_fx(ctx, effects, t, W, H, S=1.0, focus=None):
    """Screen effects over the finished frame (device pixels). focus = (x, y) screen point (default centre)."""
    import cairo
    import numpy as np
    for eff in effects:
        kind = SCREEN_FX.get(eff.get("kind"))
        if not kind:
            continue
        dur = float(eff.get("dur", 1.2) or 1.2)
        if kind == "impact":
            dur = min(dur, 0.45)
        age = t - eff["start"]
        if age < 0 or age > dur:
            continue
        fade = min(1.0, age / 0.08) * (1.0 - smoothstep((age - dur + 0.25) / 0.25))
        inten = float(eff.get("intensity", 1.0))
        cx, cy = focus if (focus and eff.get("who")) else (W / 2, H * 0.45)
        fr = int(t * 24)                                   # lines jitter like drawn frames (12-24 fps)
        rng = random.Random(fr * 31 + int(eff["start"] * 100))
        ctx.save()
        ctx.identity_matrix()
        if kind == "speed_lines":                          # concentration lines from the edges to the subject
            R = math.hypot(W, H)
            n = int(90 * inten)
            for i in range(n):
                a = rng.uniform(0, TAU)
                r0 = rng.uniform(0.28, 0.5) * min(W, H)
                w = rng.uniform(1.5, 7.0) * S * 1.5
                ca, sa = math.cos(a), math.sin(a)
                ctx.move_to(cx + ca * r0, cy + sa * r0)
                ctx.line_to(cx + math.cos(a + w / R) * R, cy + math.sin(a + w / R) * R)
                ctx.line_to(cx + math.cos(a - w / R) * R, cy + math.sin(a - w / R) * R)
                ctx.close_path()
            ctx.set_source_rgba(0.05, 0.05, 0.07, 0.75 * fade)
            ctx.fill()
        elif kind == "run_lines":                          # horizontal streaks (fast running)
            for i in range(int(40 * inten)):
                y = rng.uniform(0, H)
                x0 = rng.uniform(-0.2, 0.9) * W
                ln = rng.uniform(0.15, 0.45) * W
                ctx.rectangle(x0, y, ln, rng.uniform(1.0, 4.0) * S * 1.5)
            ctx.set_source_rgba(1, 1, 1, 0.55 * fade)
            ctx.fill()
        elif kind == "rays":                               # glowing rays behind a hero moment
            spin = age * 0.25
            for i in range(24):
                a = spin + TAU * i / 24
                ctx.move_to(cx, cy)
                ctx.arc(cx, cy, math.hypot(W, H), a, a + TAU / 48)
                ctx.close_path()
            g = cairo.RadialGradient(cx, cy, 0, cx, cy, math.hypot(W, H) * 0.6)
            g.add_color_stop_rgba(0, 1, 0.95, 0.7, 0.45 * fade * inten)
            g.add_color_stop_rgba(1, 1, 0.85, 0.4, 0.0)
            ctx.set_source(g)
            ctx.fill()
        elif kind == "gloom_bg":                           # dark vertical lines from the top + a cold tint
            g = cairo.LinearGradient(0, 0, 0, H)
            g.add_color_stop_rgba(0, 0.12, 0.1, 0.28, 0.55 * fade)
            g.add_color_stop_rgba(0.7, 0.12, 0.1, 0.28, 0.0)
            ctx.set_source(g)
            ctx.paint()
            for i in range(int(60 * inten)):
                x = rng.uniform(0, W)
                ctx.rectangle(x, 0, rng.uniform(1, 3.5) * S * 1.5, H * rng.uniform(0.15, 0.55))
            ctx.set_source_rgba(0.1, 0.08, 0.2, 0.5 * fade)
            ctx.fill()
        elif kind == "sparkle_bg":                         # floating sparkles and bubbles (shoujo moment)
            for i in range(int(30 * inten)):
                x = rng.uniform(0, W)
                y = (rng.uniform(0, H) - age * 60 * S) % H
                r = rng.uniform(4, 14) * S * 1.5
                if i % 3:
                    _star(ctx, x, y, r, rng.uniform(0, 1))
                    ctx.set_source_rgba(1, 0.95, 0.7, 0.8 * fade)
                    ctx.fill()
                else:
                    ctx.arc(x, y, r * 1.4, 0, TAU)
                    ctx.set_source_rgba(1, 0.75, 0.85, 0.35 * fade)
                    ctx.fill()
        elif kind == "swirl":                              # dizzy / confused spiral
            ctx.set_line_width(4 * S * 1.5)
            for j in range(3):
                for k in range(140):
                    a = k * 0.12 + age * 4 + j * TAU / 3
                    r = k * 0.006 * min(W, H)
                    (ctx.line_to if k else ctx.move_to)(cx + math.cos(a) * r, cy + math.sin(a) * r)
                ctx.set_source_rgba(0.35, 0.2, 0.55, 0.35 * fade)
                ctx.stroke()
        elif kind == "white_flash":
            ctx.set_source_rgba(1, 1, 1, 0.9 * (1 - age / dur))
            ctx.paint()
        elif kind == "impact":                             # impact frame: stark inverted black & white, then flash
            tgt = ctx.get_target()
            if age < 0.2 and isinstance(tgt, cairo.ImageSurface):
                tgt.flush()
                buf = np.ndarray((tgt.get_height(), tgt.get_stride() // 4, 4), np.uint8, tgt.get_data())
                px = buf[:, :tgt.get_width(), :3].astype(np.float32)
                lum = px[..., 0] * 0.114 + px[..., 1] * 0.587 + px[..., 2] * 0.299
                val = np.where(lum > (110 if int(age / 0.07) % 2 == 0 else 150), 0, 255).astype(np.uint8)
                buf[:, :tgt.get_width(), 0] = val
                buf[:, :tgt.get_width(), 1] = val
                buf[:, :tgt.get_width(), 2] = val
                tgt.mark_dirty()
                for i in range(40):                        # a burst of lines on top
                    a = rng.uniform(0, TAU)
                    ctx.move_to(cx + math.cos(a) * min(W, H) * 0.15, cy + math.sin(a) * min(W, H) * 0.15)
                    ctx.line_to(cx + math.cos(a) * W, cy + math.sin(a) * W)
                ctx.set_source_rgba(1, 1, 1, 0.9)
                ctx.set_line_width(3 * S * 1.5)
                ctx.stroke()
            elif age < 0.3:
                ctx.set_source_rgba(1, 1, 1, 0.85 * (1 - (age - 0.2) / 0.1))
                ctx.paint()
        ctx.restore()


HELD = ("phuljhadi", "sparkler", "fuljhadi")              # drawn in the hand of "who"


def draw_effect(ctx, eff, t, anchor, s=1.0, track=None):
    """eff: dict(kind, start, dur, ...). t: scene time. anchor: (x, y) world point."""
    from . import particles
    if particles.draw(ctx, eff, t, anchor, s, track):   # fireworks, anaar, holi, dust trails ... (engine/particles.py)
        return
    age = t - eff["start"]
    dur = eff.get("dur", 2.0)
    kind = eff["kind"]
    if kind in SCREEN_FX:                                  # anime screen effects: drawn over the frame (render.py)
        return
    if age < 0 or age > dur + 1.5:
        return
    x, y = anchor
    rng = random.Random(int(eff["start"] * 1000) + stable_hash(kind) % 997)
    inten = eff.get("intensity", 1.0)
    fade = 1.0 - smoothstep((age - dur) / 1.2)
    if kind == "dust":
        for k in range(8):
            a = rng.uniform(math.pi * 0.05, math.pi * 0.95)
            sp = rng.uniform(40, 110) * s
            u = age / 0.9
            if u > 1:
                continue
            px, py = x + math.cos(a) * sp * u * 1.6 * rng.choice([-1, 1]), y + math.sin(a) * sp * u * 0.5
            ctx.arc(px, py + 6 * s, (8 + 22 * u) * s, 0, TAU)
            ctx.set_source_rgba(0.72, 0.66, 0.58, 0.45 * (1 - u))
            ctx.fill()
    elif kind in ("confetti", "celebration"):
        cols = [(0.95, 0.3, 0.35), (1, 0.8, 0.2), (0.3, 0.75, 0.95), (0.45, 0.85, 0.4), (0.8, 0.45, 0.95)]
        n = int(40 * inten)
        for k in range(n):
            t0 = rng.uniform(0, max(dur - 0.6, 0.1))
            a = age - t0
            if a < 0 or a > 2.2:
                continue
            px = x + rng.uniform(-260, 260) * s + 30 * math.sin(a * 4 + k) * s
            py = y + (420 - 260 * a) * s
            ctx.save()
            ctx.translate(px, py)
            ctx.rotate(a * rng.uniform(4, 9))
            ctx.rectangle(-6 * s, -3 * s, 12 * s, 6 * s)
            ctx.set_source_rgba(*cols[k % len(cols)], fade * (1 - smoothstep((a - 1.8) / 0.4)))
            ctx.fill()
            ctx.restore()
    elif kind in ("sparkle", "magic", "stars"):
        for k in range(int(26 * inten)):
            ph = (age * rng.uniform(0.6, 1.4) + rng.random()) % 1.0
            px = x + rng.uniform(-150, 150) * s
            py = y + rng.uniform(40, 320) * s + ph * 40 * s
            r = (4 + 10 * math.sin(math.pi * ph)) * s
            _star(ctx, px, py, r, age * 2)
            ctx.set_source_rgba(1, 0.92, 0.45, fade * math.sin(math.pi * ph))
            ctx.fill()
    elif kind == "smoke":
        for k in range(int(22 * inten)):
            ph = (age * 0.7 + k / 22.0) % 1.0
            if age < ph * 1.4 and age < 1.4:
                continue
            px = x + (rng.uniform(-40, 40) + 60 * ph * rng.choice([-1, 1]) + _wind_drift(age) * ph) * s
            py = y + (-10 + ph * 50) * s
            ctx.arc(px, py, (20 + 70 * ph) * s, 0, TAU)
            ctx.set_source_rgba(0.82, 0.82, 0.84, 0.5 * (1 - ph) * fade)
            ctx.fill()
    elif kind == "fire":
        for k in range(14):
            ph = (age * 1.8 + k / 14.0) % 1.0
            px = x + (rng.uniform(-45, 45) * (1 - ph)) * s
            py = y + ph * 150 * s
            r = (26 * (1 - ph) + 4) * s
            col = (1, 0.85 - 0.6 * ph, 0.2 * (1 - ph))
            ctx.arc(px, py, r, 0, TAU)
            ctx.set_source_rgba(*col, 0.8 * (1 - ph) * fade)
            ctx.fill()
    elif kind == "splash":
        k_s = max(0.35, inten) * s
        for k in range(3):                                   # rings spreading on the water
            u = (age - k * 0.18) / 1.6
            if 0 < u < 1:
                ctx.save()
                ctx.translate(x, y + 2)
                ctx.scale(1.0, 0.22)
                ctx.arc(0, 0, (30 + 190 * u) * k_s, 0, TAU)
                ctx.restore()
                ctx.set_source_rgba(0.85, 0.95, 1.0, 0.7 * (1 - u))
                ctx.set_line_width(4 * s)
                ctx.stroke()
        if age < 0.7:                                        # the water column
            u = age / 0.7
            hh = 170 * k_s * math.sin(math.pi * u)
            ctx.move_to(x - 30 * k_s, y)
            ctx.curve_to(x - 20 * k_s, y + hh * 0.6, x - 8 * k_s, y + hh, x, y + hh)
            ctx.curve_to(x + 8 * k_s, y + hh, x + 20 * k_s, y + hh * 0.6, x + 30 * k_s, y)
            ctx.close_path()
            ctx.set_source_rgba(0.75, 0.9, 1.0, 0.75 * (1 - u * 0.5))
            ctx.fill()
        for k in range(int(10 + 12 * min(inten, 1.5))):
            a = rng.uniform(0.25, math.pi - 0.25)
            sp = rng.uniform(150, 320) * k_s
            u = age
            if u > 1.1:
                continue
            px = x + math.cos(a) * sp * u
            py = y + math.sin(a) * sp * u - 420 * u * u * s
            if py < y - 5:
                continue
            ctx.arc(px, py, 5 * s * max(0.7, min(inten, 1.4)), 0, TAU)
            ctx.set_source_rgba(0.55, 0.8, 1.0, 0.85)
            ctx.fill()
    elif kind == "hearts":
        for k in range(10):
            ph = (age * 0.6 + k / 10.0) % 1.0
            px = x + rng.uniform(-120, 120) * s + 15 * math.sin(age * 3 + k) * s
            py = y + (60 + ph * 300) * s
            _heart(ctx, px, py, (8 + 6 * rng.random()) * s)
            ctx.set_source_rgba(0.95, 0.3, 0.45, (1 - ph) * fade)
            ctx.fill()
    elif kind == "explosion":
        u = clamp(age / 0.6, 0, 1)
        ctx.arc(x, y + 60 * s, (40 + 220 * u) * s, 0, TAU)
        ctx.set_source_rgba(1, 0.75, 0.2, 0.8 * (1 - u))
        ctx.fill()
        ctx.arc(x, y + 60 * s, (20 + 130 * u) * s, 0, TAU)
        ctx.set_source_rgba(1, 0.95, 0.7, 0.9 * (1 - u))
        ctx.fill()
        for k in range(16):
            a = rng.uniform(0, math.pi)
            sp = rng.uniform(200, 420) * s
            ctx.arc(x + math.cos(a) * sp * age, y + 60 * s + math.sin(a) * sp * age * 0.8, (20 + 40 * age) * s, 0, TAU)
            ctx.set_source_rgba(0.45, 0.45, 0.47, 0.5 * max(0, 1 - age / 1.8))
            ctx.fill()
    elif kind == "leaves":
        for k in range(int(26 * inten)):
            ph = (age * rng.uniform(0.25, 0.5) + rng.random()) % 1.0
            px = x + (-900 + ph * 1800) * s
            py = y + (rng.uniform(40, 500) + 60 * math.sin(age * 3 + k)) * s
            ctx.save()
            ctx.translate(px, py)
            ctx.rotate(age * rng.uniform(3, 8))
            ctx.scale(10 * s, 5 * s)
            ctx.arc(0, 0, 1, 0, TAU)
            ctx.restore()
            ctx.set_source_rgba(*rng.choice([(0.4, 0.65, 0.2), (0.85, 0.55, 0.15), (0.6, 0.45, 0.2)]), fade)
            ctx.fill()
    elif kind == "lightning":
        if age < 0.35:
            ctx.set_source_rgba(1, 1, 0.85, 0.9 * (1 - age / 0.35))
            ctx.set_line_width(7 * s)
            px, py = x, y + 900 * s
            ctx.move_to(px, py)
            while py > y + 40 * s:
                px += rng.uniform(-60, 60) * s
                py -= rng.uniform(60, 120) * s
                ctx.line_to(px, py)
            ctx.stroke()
