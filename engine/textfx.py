"""Text in Indian scripts (Hindi / Marathi Devanagari, Tamil, Telugu, Bengali, Gujarati, Kannada, Malayalam).

Cairo's simple text drawing shows boxes for these scripts and can't join their letters, so text that contains
them is laid out with Pillow + libraqm (proper shaping: matras, conjuncts) using the bundled free Noto Sans fonts
(assets/fonts, SIL Open Font License), then painted onto the frame.
"""
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(HERE, "assets", "fonts")

RANGES = [((0x0900, 0x097F), "devanagari"), ((0xA8E0, 0xA8FF), "devanagari"), ((0x1CD0, 0x1CFF), "devanagari"),
          ((0x0980, 0x09FF), "bengali"), ((0x0A80, 0x0AFF), "gujarati"), ((0x0B80, 0x0BFF), "tamil"),
          ((0x0C00, 0x0C7F), "telugu"), ((0x0C80, 0x0CFF), "kannada"), ((0x0D00, 0x0D7F), "malayalam")]
_FONTS = {}
_WARNED = [False]


def script_of(ch):
    o = ord(ch)
    for (a, b), name in RANGES:
        if a <= o <= b:
            return name
    return None


def needs(text):
    """True if the text has letters cairo can't draw (Indian scripts)."""
    return any(script_of(c) for c in str(text))


def font(script, size):
    key = (script, int(size))
    f = _FONTS.get(key)
    if f is None:
        from PIL import ImageFont, features
        fname = os.path.join(FONT_DIR, f"NotoSans-{script}-Bold.woff")
        if not os.path.exists(fname):
            fname = os.path.join(FONT_DIR, "NotoSans-latin-Bold.woff")
        layout = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
        if layout == ImageFont.Layout.BASIC and not _WARNED[0]:
            _WARNED[0] = True
            print("  ! your Pillow has no libraqm: Indian-script letters may not join perfectly "
                  "(pip install --upgrade pillow)")
        f = _FONTS[key] = ImageFont.truetype(fname, max(6, int(size)), layout_engine=layout)
    return f


def runs(text):
    """[(script or 'latin', piece)]: spaces / punctuation stay with the run they are in."""
    out = []
    for ch in str(text):
        sc = script_of(ch)
        if sc is None and ch in " ‌‍" and out:
            sc = out[-1][0]                             # a space or joiner continues the current run
        sc = sc or "latin"
        if out and out[-1][0] == sc:
            out[-1] = (sc, out[-1][1] + ch)
        else:
            out.append((sc, ch))
    return out


def width(text, size):
    return sum(font(sc, size).getlength(piece) for sc, piece in runs(text))


def wrap(text, size, max_w):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if width(test, size) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def draw_line(draw, x, baseline, text, size, fill):
    """Draw one line on a Pillow ImageDraw, each script in its own font, all on one baseline."""
    for sc, piece in runs(text):
        f = font(sc, size)
        draw.text((x, baseline), piece, font=f, fill=fill, anchor="ls")
        x += f.getlength(piece)
    return x


def paint(ctx, img, x, y):
    """Paint a Pillow RGBA image onto a cairo context at (x, y) (device pixels)."""
    import cairo
    import numpy as np
    a = np.asarray(img.convert("RGBA"), dtype=np.uint16)
    al = a[..., 3:4]
    pre = (a[..., :3] * al // 255).astype(np.uint8)                   # cairo wants premultiplied BGRA
    bgra = np.dstack([pre[..., 2], pre[..., 1], pre[..., 0], a[..., 3].astype(np.uint8)]).copy()
    h, w = bgra.shape[:2]
    surf = cairo.ImageSurface.create_for_data(memoryview(bgra), cairo.FORMAT_ARGB32, w, h, w * 4)
    ctx.save()
    ctx.identity_matrix()
    ctx.set_source_surface(surf, x, y)
    ctx.paint()
    ctx.restore()
    surf.finish()


def show_at(ctx, text, x, baseline, size, rgba):
    """Like cairo's move_to + show_text for text with Indian scripts (x = left, baseline in device px)."""
    from PIL import Image, ImageDraw
    w = width(text, size)
    if hasattr(ctx, "ops"):                            # ▶ live player: the browser shapes these scripts itself
        ctx.save()
        ctx.identity_matrix()
        ctx.op("y", "Noto Sans", 1)
        ctx.op("z", round(size, 2))
        ctx.op("c", *[round(float(c), 3) for c in (tuple(rgba) + (1.0,))[:4]])
        ctx.op("t", text, round(x, 2), round(baseline, 2), round(w, 2))
        ctx.restore()
        return w
    img = Image.new("RGBA", (int(w) + 12, int(size * 1.7)), (0, 0, 0, 0))
    col = tuple(int(max(0.0, min(1.0, c)) * 255) for c in rgba[:3]) + (int(255 * (rgba[3] if len(rgba) > 3 else 1.0)),)
    draw_line(ImageDraw.Draw(img), 6, size * 1.2, text, size, col)
    paint(ctx, img, int(x - 6), int(baseline - size * 1.2))
    return w
