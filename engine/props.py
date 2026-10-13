"""Simple props that characters can hold, drop, give, or that can fly around."""
import math

from .util import hex_to_rgb, darker, lighter, TAU

PROP_TYPES = ("ball", "box", "gift", "kite", "balloon", "book", "bag", "apple", "flower", "phone",
              "letter", "cup", "star", "stick", "umbrella", "sign")


def draw_prop(ctx, ptype, x, y, t, spec, spin=0.0, held_hand=None, alpha=1.0):
    """Draw in world coords (y-up). (x, y) = bottom-centre when resting, hand when held. A lamp / diya / lantern /
    candle / torch gives light at night (engine/nightlights.py)."""
    _draw_prop(ctx, ptype, x, y, t, spec, spin, held_hand, alpha)
    from . import nightlights as nl
    name = f"{ptype} {spec.get('id') or ''} {spec.get('image') or ''}"
    st = spec.get("state")
    if nl.is_light_name(name) and st != "off" and (nl.ON[0] or st == "on" or spec.get("lit")):
        flame = nl.is_flame_name(name)
        h = float(spec.get("height") or 70)
        nl.add_device(ctx, x, y + (h * 0.6 if held_hand is None else 10), max(150.0, h * 2.6),
                      nl.FLAME if flame else nl.WARM, 0.65, flame=flame,
                      ground=(x, y) if held_hand is None else None, kind="prop")


def _draw_prop(ctx, ptype, x, y, t, spec, spin=0.0, held_hand=None, alpha=1.0):
    from . import images
    img = spec.get("image") or (ptype if ptype not in PROP_TYPES and images.exists(ptype) else None)
    if img and images.exists(img):
        h = float(spec.get("height") or (images.info(img) or {}).get("height") or 70)
        ao = images.anim_opts(spec)
        if held_hand is not None:
            images.draw(ctx, img, x, y, h, bool(spec.get("flip")), alpha, anchor="center", t=t, **ao)
        else:
            images.draw(ctx, img, x, y, h, bool(spec.get("flip")), alpha, rotate=-spin * 0.2 if spin else 0.0,
                        t=t, **ao)
        return
    s = float(spec.get("scale", 1.0))
    col = hex_to_rgb(spec.get("color", {"ball": "#e63946", "balloon": "#ff4d6d", "kite": "#ffb703",
                                         "apple": "#d62828", "gift": "#8338ec", "box": "#c8905b",
                                         "book": "#1d4e89", "bag": "#6a4c93", "cup": "#ffffff",
                                         "star": "#ffd60a", "phone": "#222222", "letter": "#fdfcdc",
                                         "umbrella": "#219ebc", "sign": "#e9c46a"}.get(ptype, "#e76f51")))
    ctx.save()
    ctx.set_line_cap(1)
    held = held_hand is not None
    if ptype == "balloon":
        by = y + (110 if held else 140) * s + 6 * math.sin(t * 1.7)
        bx = x + 8 * math.sin(t * 1.1)
        ctx.set_source_rgba(0.3, 0.3, 0.3, alpha)
        ctx.set_line_width(2)
        ctx.move_to(x, y)
        ctx.curve_to(x + 10, y + 40 * s, bx - 10, by - 60 * s, bx, by - 38 * s)
        ctx.stroke()
        ctx.save()
        ctx.translate(bx, by)
        ctx.scale(30 * s, 38 * s)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(*col, alpha)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.35 * alpha)
        ctx.arc(bx - 9 * s, by + 12 * s, 7 * s, 0, TAU)
        ctx.fill()
    elif ptype == "kite":
        kx = x - 180 * s + 25 * math.sin(t * 0.9)
        ky = y + 330 * s + 20 * math.sin(t * 1.3)
        ctx.set_source_rgba(0.25, 0.25, 0.25, alpha)
        ctx.set_line_width(1.8)
        ctx.move_to(x, y)
        ctx.curve_to(x - 60 * s, y + 100 * s, kx + 20, ky - 150 * s, kx, ky - 45 * s)
        ctx.stroke()
        ctx.save()
        ctx.translate(kx, ky)
        ctx.rotate(0.25 * math.sin(t * 1.3))
        ctx.set_source_rgba(*col, alpha)
        ctx.move_to(0, 55 * s)
        ctx.line_to(38 * s, 0)
        ctx.line_to(0, -45 * s)
        ctx.line_to(-38 * s, 0)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgba(*darker(col, 0.7), alpha)
        ctx.set_line_width(3)
        ctx.move_to(0, 55 * s)
        ctx.line_to(0, -45 * s)
        ctx.move_to(-38 * s, 0)
        ctx.line_to(38 * s, 0)
        ctx.stroke()
        ctx.set_line_width(2.5)
        ctx.move_to(0, -45 * s)
        for k in range(1, 6):
            ctx.line_to(12 * math.sin(t * 3 + k) * s, (-45 - k * 22) * s)
        ctx.stroke()
        for k in range(1, 5):
            ctx.set_source_rgba(*lighter(col, 0.3) if k % 2 else hex_to_rgb("#e63946"), alpha)
            ctx.arc(12 * math.sin(t * 3 + k) * s, (-45 - k * 22) * s, 5 * s, 0, TAU)
            ctx.fill()
        ctx.restore()
    else:
        cy = y - (12 * s if held else 0)
        ctx.translate(x, cy)
        if ptype == "ball":
            r = 22 * s
            ctx.translate(0, r if not held else 0)
            ctx.rotate(-spin)
            ctx.set_source_rgba(*col, alpha)
            ctx.arc(0, 0, r, 0, TAU)
            ctx.fill()
            ctx.set_source_rgba(1, 1, 1, alpha)
            ctx.set_line_width(4 * s)
            ctx.arc(0, 0, r * 0.62, 0.3, 2.6)
            ctx.stroke()
        elif ptype in ("box", "gift"):
            w = 50 * s
            if held:
                ctx.translate(0, -w / 2)
            ctx.set_source_rgba(*col, alpha)
            ctx.rectangle(-w / 2, 0, w, w)
            ctx.fill()
            ctx.set_source_rgba(*(hex_to_rgb("#ffd60a") if ptype == "gift" else darker(col, 0.7)), alpha)
            ctx.rectangle(-5 * s, 0, 10 * s, w)
            ctx.fill()
            if ptype == "gift":
                ctx.rectangle(-w / 2, w / 2 - 5 * s, w, 10 * s)
                ctx.fill()
                ctx.arc(-8 * s, w + 6 * s, 8 * s, 0, TAU)
                ctx.arc(8 * s, w + 6 * s, 8 * s, 0, TAU)
                ctx.fill()
        elif ptype == "apple":
            ctx.set_source_rgba(*col, alpha)
            ctx.arc(0, 14 * s, 14 * s, 0, TAU)
            ctx.fill()
            ctx.set_source_rgba(0.3, 0.6, 0.2, alpha)
            ctx.arc(6 * s, 30 * s, 5 * s, 0, TAU)
            ctx.fill()
        elif ptype == "book":
            ctx.set_source_rgba(*col, alpha)
            ctx.rectangle(-22 * s, 0, 44 * s, 30 * s)
            ctx.fill()
            ctx.set_source_rgba(1, 1, 1, alpha)
            ctx.rectangle(-18 * s, 3 * s, 36 * s, 5 * s)
            ctx.fill()
        elif ptype == "bag":
            ctx.set_source_rgba(*col, alpha)
            ctx.rectangle(-24 * s, -40 * s if held else 0, 48 * s, 40 * s)
            ctx.fill()
            ctx.set_line_width(4 * s)
            ctx.arc(0, (0 if held else 40 * s), 14 * s, 0, math.pi)
            ctx.stroke()
        elif ptype == "flower":
            ctx.set_source_rgba(0.25, 0.55, 0.2, alpha)
            ctx.set_line_width(3 * s)
            ctx.move_to(0, 0)
            ctx.line_to(0, 40 * s)
            ctx.stroke()
            ctx.set_source_rgba(*col, alpha)
            for a in range(0, 360, 60):
                ctx.arc(9 * s * math.cos(math.radians(a)), 44 * s + 9 * s * math.sin(math.radians(a)), 7 * s, 0, TAU)
                ctx.fill()
            ctx.set_source_rgba(1, 0.85, 0.2, alpha)
            ctx.arc(0, 44 * s, 6 * s, 0, TAU)
            ctx.fill()
        elif ptype == "phone":
            ctx.set_source_rgba(*col, alpha)
            ctx.rectangle(-9 * s, 0, 18 * s, 32 * s)
            ctx.fill()
            ctx.set_source_rgba(0.5, 0.8, 1, alpha)
            ctx.rectangle(-7 * s, 4 * s, 14 * s, 22 * s)
            ctx.fill()
        elif ptype == "letter":
            ctx.set_source_rgba(*col, alpha)
            ctx.rectangle(-22 * s, 0, 44 * s, 28 * s)
            ctx.fill()
            ctx.set_source_rgba(0.5, 0.4, 0.3, alpha)
            ctx.set_line_width(2)
            ctx.move_to(-22 * s, 28 * s)
            ctx.line_to(0, 12 * s)
            ctx.line_to(22 * s, 28 * s)
            ctx.stroke()
        elif ptype == "cup":
            ctx.set_source_rgba(*col, alpha)
            ctx.rectangle(-12 * s, 0, 24 * s, 28 * s)
            ctx.fill()
            ctx.set_source_rgba(*darker(col, 0.6), alpha)
            ctx.set_line_width(3)
            ctx.rectangle(-12 * s, 0, 24 * s, 28 * s)
            ctx.stroke()
        elif ptype == "star":
            ctx.set_source_rgba(*col, alpha)
            ctx.translate(0, 25 * s)
            ctx.rotate(t * 0.8)
            for k in range(10):
                r = (24 if k % 2 == 0 else 10) * s
                a = math.pi / 2 + k * math.pi / 5
                (ctx.move_to if k == 0 else ctx.line_to)(r * math.cos(a), r * math.sin(a))
            ctx.close_path()
            ctx.fill()
        elif ptype == "stick":
            ctx.set_source_rgba(0.45, 0.3, 0.15, alpha)
            ctx.set_line_width(6 * s)
            ctx.move_to(0, -30 * s if held else 0)
            ctx.line_to(20 * s, 70 * s)
            ctx.stroke()
        elif ptype == "umbrella":
            ctx.set_source_rgba(0.2, 0.2, 0.2, alpha)
            ctx.set_line_width(4)
            ctx.move_to(0, 0)
            ctx.line_to(0, 120 * s)
            ctx.stroke()
            ctx.set_source_rgba(*col, alpha)
            ctx.arc(0, 110 * s, 80 * s, 0, math.pi)
            ctx.close_path()
            ctx.fill()
        elif ptype == "sign":
            ctx.set_source_rgba(0.45, 0.3, 0.15, alpha)
            ctx.rectangle(-4 * s, 0, 8 * s, 110 * s)
            ctx.fill()
            ctx.set_source_rgba(*col, alpha)
            ctx.rectangle(-60 * s, 90 * s, 120 * s, 60 * s)
            ctx.fill()
            txt = str(spec.get("text", ""))
            if txt:
                ctx.save()
                ctx.translate(0, 112 * s)
                ctx.scale(1, -1)
                ctx.select_font_face("DejaVu Sans", 0, 1)
                ctx.set_font_size(22 * s)
                ext = ctx.text_extents(txt)
                ctx.set_source_rgba(0.15, 0.1, 0.05, alpha)
                ctx.move_to(-ext.x_advance / 2, 0)
                ctx.show_text(txt)
                ctx.restore()
        else:
            ctx.set_source_rgba(*col, alpha)
            ctx.arc(0, 18 * s, 18 * s, 0, TAU)
            ctx.fill()
    ctx.restore()
