"""🐄 The Stick 3D animal library on one sheet: every animal as its 3D model, seen three-quarters from the front.

    python tools/animal_sheet.py out.png [--action walk|sit|eat|run|lie] [--only cow,goat,hen] [--angle 35]
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cairo  # noqa: E402
import numpy as np  # noqa: E402

from engine import stick3d as S3  # noqa: E402
from engine import stick3d_animals as SA  # noqa: E402
from engine.sketch import Pen  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--action", default="idle")
    ap.add_argument("--only", default="")
    ap.add_argument("--t", type=float, default=0.4)
    ap.add_argument("--angle", type=float, default=35.0, help="degrees the camera stands round from the side")
    a = ap.parse_args()
    names = [n.strip() for n in a.only.split(",") if n.strip()] or SA.LIBRARY
    S3.STYLE[0] = "flat"
    cols, cw, ch = 6, 330, 300
    rows = (len(names) + cols - 1) // cols
    W, H = cols * cw, rows * ch
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(0.97, 0.97, 0.94)
    ctx.paint()
    pen = Pen(ctx, 0, unit=1.0)
    for i, n in enumerate(names):
        x0, y0 = (i % cols) * cw, (i // cols) * ch
        it = {"id": n, "species": n, "pos": (0.0, 0.0, 0.0), "dir": 0.0, "do": a.action,
              "moving": a.action in ("walk", "run")}
        parts, head = SA.meshes(S3, it, a.t)
        if not parts:
            continue
        V = np.concatenate([m.v for m in parts])
        lo, hi = V.min(axis=0), V.max(axis=0)
        c = (lo + hi) / 2
        size = float(np.max(hi - lo))
        ang = math.radians(-90 + a.angle)                              # (the animal faces +x; we stand at -z)
        eye = c + np.array([math.cos(ang), 0.35, math.sin(ang)]) * size * 1.9
        cam = S3.Cam(tuple(eye), tuple(c), fov=36.0, W=cw, H=ch - 30)
        ctx.save()
        ctx.rectangle(x0, y0, cw, ch - 30)
        ctx.clip()
        ctx.translate(x0, y0)
        S3._shadow(ctx, cam, 0.0, 0.0, *SA.shadow_size(n), 1.0)
        order = sorted(parts, key=lambda m: -float(np.dot(m.center - cam.pos, cam.fwd)))
        for m in order:
            S3._ink_mesh(ctx, pen, cam, m, 0.4, 0.0)
        ctx.restore()
        ctx.set_source_rgb(0.3, 0.3, 0.32)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(20)
        e = ctx.text_extents(n)
        ctx.move_to(x0 + cw / 2 - e.width / 2, y0 + ch - 10)
        ctx.show_text(n)
    surf.write_to_png(a.out)
    print("saved", a.out, len(names), "animals")


if __name__ == "__main__":
    main()
