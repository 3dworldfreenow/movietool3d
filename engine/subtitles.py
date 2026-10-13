"""Subtitles: cue building, SRT export and burned-in drawing."""
import cairo

from .util import lighter

MAX_CHARS = 84          # per cue (two lines of ~42)


class Cue:
    __slots__ = ("start", "end", "speaker", "color", "text", "narration")

    def __init__(self, start, end, speaker, color, text, narration=False):
        self.start, self.end, self.speaker = start, end, speaker
        self.color, self.text, self.narration = color, text, narration


def split_text(text, limit=MAX_CHARS):
    words = str(text).split()
    chunks, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > limit and cur:
            chunks.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
        if cur.endswith((".", "!", "?")) and len(cur) > limit * 0.55:
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks or [""]


def cues_for(speech, offset, name, color, narration):
    chunks = split_text(speech.text)
    total = sum(len(c) for c in chunks) or 1
    t = offset + speech.start
    out = []
    for c in chunks:
        d = speech.dur * len(c) / total
        out.append(Cue(t, t + d, name, color, c, narration))
        t += d
    return out


def _ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            label = "" if c.narration or not c.speaker else f"{c.speaker}: "
            f.write(f"{i}\n{_ts(c.start)} --> {_ts(c.end)}\n{label}{c.text}\n\n")


def _wrap(ctx, text, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if ctx.text_extents(test).x_advance > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def draw_cue(ctx, cue, t, W, H, style=None):
    style = style or {}
    k = H / 1080.0
    fade = min(1.0, (t - cue.start) / 0.12, (cue.end - t) / 0.12)
    if fade <= 0:
        return
    ctx.identity_matrix()
    size = float(style.get("font_size", 46)) * k
    face = style.get("font", "DejaVu Sans")
    ctx.select_font_face(face, cairo.FONT_SLANT_ITALIC if cue.narration else cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    max_w = W * 0.78
    label = "" if cue.narration or not cue.speaker else cue.speaker + ": "
    from . import textfx
    indic = textfx.needs(label + cue.text)             # Hindi / Tamil ...: shaped with the bundled Noto fonts
    paras = (label + cue.text).split("\n")             # "both" subtitles: one paragraph per language
    lines = []
    for para in paras:
        lines += textfx.wrap(para, size, max_w) if indic else _wrap(ctx, para, max_w)
    widths = [textfx.width(l, size) for l in lines] if indic else [ctx.text_extents(l).x_advance for l in lines]
    lh = size * 1.3
    box_w = max(widths) + 50 * k
    box_h = lh * len(lines) + 26 * k
    bottom = H - float(style.get("margin", 60)) * k
    x0, y0 = (W - box_w) / 2, bottom - box_h
    r = 18 * k
    ctx.new_sub_path()
    ctx.arc(x0 + box_w - r, y0 + r, r, -1.5708, 0)
    ctx.arc(x0 + box_w - r, y0 + box_h - r, r, 0, 1.5708)
    ctx.arc(x0 + r, y0 + box_h - r, r, 1.5708, 3.1416)
    ctx.arc(x0 + r, y0 + r, r, 3.1416, 4.7124)
    ctx.close_path()
    ctx.set_source_rgba(0.05, 0.05, 0.08, 0.62 * fade)
    ctx.fill()
    y = y0 + 13 * k + size * 1.02
    if indic:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (int(box_w) + 4, int(box_h) + 4), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        A = int(255 * fade)
        lc = tuple(int(255 * v) for v in lighter(cue.color, 0.45)) + (A,)
        body = (255, 255, 235 if cue.narration else 255, A)
        yy = 13 * k + size * 1.02
        for i, line in enumerate(lines):
            xx = (box_w - widths[i]) / 2
            if i == 0 and label and line.startswith(label.strip()):
                xx = textfx.draw_line(dr, xx, yy, label, size, lc)
                textfx.draw_line(dr, xx, yy, line[len(label):], size, body)
            else:
                textfx.draw_line(dr, xx, yy, line, size, body)
            yy += lh
        textfx.paint(ctx, img, int(x0), int(y0))
        return
    for i, line in enumerate(lines):
        x = (W - widths[i]) / 2
        ctx.move_to(x, y)
        if i == 0 and label and line.startswith(label.strip()):
            ctx.set_source_rgba(*lighter(cue.color, 0.45), fade)
            ctx.show_text(label)
            ctx.set_source_rgba(1, 1, 1, fade)
            ctx.show_text(line[len(label):])
        else:
            ctx.set_source_rgba(1, 1, 0.92 if cue.narration else 1, fade)
            ctx.show_text(line)
        y += lh
