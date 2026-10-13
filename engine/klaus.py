"""💡 Klaus-style light for 2.5D (settings "art": "klaus"): the flat cartoon people lit as if they were round -
a soft shadow side away from the light, a bright rim on the edge that faces it, the scene's light colour on them -
and a warm / cool colour grade on the frame (warm light, cool shadows; at night a readable blue moonlight).

The light comes from the scene's real sun (engine/realworld.py: where it is and its colour by the time of day), so
the shading always agrees with the shadows on the ground. Art only - the light itself is the real sun."""
import math

import cairo

LIGHT = [None]          # this scene's light (set by render.py for "art": "klaus"; None = off)


def light_for(time_word):
    """{side, key, shade, rim, rim_k, shade_k, night} for a time of day"""
    from .realworld import sun
    s = sun(time_word)
    night = bool(s.get("night"))
    key = tuple(s["color"])
    side = 1.0 if s["side"] >= 0 else -1.0                 # the side of the picture the light comes from
    low = 1.0 - min(1.0, s["elev"] / 70.0)                 # a low sun: stronger modelling, a brighter rim
    if night:
        return dict(side=side, key=(0.72, 0.82, 1.0), shade=(0.08, 0.1, 0.28), rim=(0.75, 0.86, 1.0),
                    shade_k=0.42, rim_k=0.55, night=True, warm=0.0)
    return dict(side=side, key=key, shade=(0.16, 0.14, 0.32), rim=tuple(min(1.0, 0.55 + 0.5 * c) for c in key),
                shade_k=0.34 + 0.16 * low, rim_k=0.3 + 0.45 * low, night=False, warm=float(s.get("warmth", 0.3)))


def lit(ctx, draw, x, y, scale, alpha=1.0):
    """draw(ctx) a character inside a group, then light it: the shadow side, the rim. x, y, scale in world units
    (the character's feet and its size). Falls back to a plain draw when there is no light."""
    L = LIGHT[0]
    if L is None or alpha < 0.05:
        return draw(ctx)
    w, h = 150.0 * scale, 470.0 * scale                     # room round the character (arms, hats, a raised hand)
    ctx.save()
    ctx.rectangle(x - w, y - 40.0 * scale, 2 * w, h)
    ctx.clip()
    ctx.push_group()
    out = draw(ctx)
    pat = ctx.pop_group()
    ctx.set_source(pat)
    ctx.paint()
    side = L["side"]
    # ---- the shadow side: a soft cool shade across the body, away from the light (only where the character is)
    hw = 62.0 * scale
    g = cairo.LinearGradient(x + side * hw, 0, x - side * hw, 0)
    sr, sg_, sb = L["shade"]
    g.add_color_stop_rgba(0.0, sr, sg_, sb, 0.0)
    g.add_color_stop_rgba(0.45, sr, sg_, sb, 0.0)
    g.add_color_stop_rgba(1.0, sr, sg_, sb, L["shade_k"] * alpha)
    ctx.set_source(g)
    ctx.mask(pat)
    # ---- the rim: the edge that faces the light catches it (the character minus itself moved toward the light)
    d = 5.0 * scale
    ctx.push_group()
    ctx.set_source_rgba(*L["rim"], 1.0)
    ctx.mask(pat)
    ctx.set_operator(cairo.OPERATOR_DEST_OUT)
    ctx.save()
    ctx.translate(-side * d, -0.7 * d)                    # (world y is up: the light is a little above)
    ctx.set_source_rgba(0, 0, 0, 1)
    ctx.mask(pat)
    ctx.restore()
    rim = ctx.pop_group()
    ctx.set_source(rim)
    ctx.paint_with_alpha(L["rim_k"] * alpha)
    ctx.restore()
    return out


def grade(surf):
    """the warm / cool colour of the frame: warm light, cool shadows; at night the darks lifted into a readable
    blue moonlight (faces stay visible). numpy on the finished frame (BGRA), a few ms."""
    import numpy as np
    L = LIGHT[0]
    if L is None:
        return
    surf.flush()
    W, H = surf.get_width(), surf.get_height()
    a = np.ndarray((H, surf.get_stride() // 4, 4), np.uint8, surf.get_data())[:, :W]
    img = a[..., :3].astype(np.float32) * (1.0 / 255.0)           # B, G, R
    lum = img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299
    if L["night"]:
        img = np.power(img, 0.72)                                  # lift the darks: a cartoon night you can read
        img *= np.array([1.06, 0.98, 0.9], np.float32)             # moon blue
    else:
        sh = (1.0 - lum)[..., None] ** 2                           # cool shadows
        hi = lum[..., None] ** 2                                   # warm light
        wk = 0.06 + 0.08 * L["warm"]
        img += sh * np.array([0.05, 0.01, -0.03], np.float32) + hi * np.array([-wk, 0.0, wk * 0.6], np.float32)
    np.clip(img * 255.0, 0, 255, out=img)
    a[..., :3] = img.astype(np.uint8)
    surf.mark_dirty()
