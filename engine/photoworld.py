"""True 2.5D for your own background pictures: the depth layers made by engine/photodepth.py stand at their
real distances in front of the engine's camera, so tracking, push-ins, arcs and cranes get real parallax,
characters walk on the picture's ground at the right size, and near parts of the picture (plants, trees)
can hide them.

Card geometry: at the default camera (x = scene centre, height 345, horizon at mid-screen) a card at
distance Z reproduces the original picture exactly; any other camera sees it from a new place.
"""
import math
import os

import cairo

from .scene3d import DepthScene, Obj, FOCAL, NEAR
from .util import clamp, stable_hash

H0 = 345.0
HY0 = 540.0


class PhotoWorld3D(DepthScene):
    photo = True

    def __init__(self, name, world_w, W, H, seed=0, smooth=True):
        from . import photodepth
        self.meta = photodepth.status(name) or photodepth.ensure(name, log=lambda *a: None)
        self.dir = photodepth.folder(name)
        self.smooth = bool(smooth) and os.path.exists(os.path.join(self.dir, "zmap.npz"))
        self._pts = None
        self.cam_h = float(self.meta.get("cam_h", H0))       # the picture's own camera height and horizon
        self.hor0 = float(self.meta.get("hor", 0.5))
        self.hy = self.hor0 * 1080.0
        self.cx = world_w / 2.0
        self.people_on_top = bool(self.meta.get("people_on_top"))   # a plate: its scenery never hides the people
        self.has_path = False
        self.shafts = False
        self.birds = False
        self.vignette = 0.22
        self._surfs = {}
        super().__init__(W, H, seed=seed)

    def path_x(self, Z):
        return self.cx

    # ------------------------------------------------------------------ cards
    def _surf(self, fname):
        s = self._surfs.get(fname)
        if s is None:
            s = self._surfs[fname] = cairo.ImageSurface.create_from_png(os.path.join(self.dir, fname))
        return s

    def _build(self):
        for c in self.meta["cards"]:
            Z = c["Z"]
            k = Z / FOCAL                                  # screen px (1080p) -> world units at this distance
            X = self.cx + (c["u"] - 960.0) * k
            Yb = self.cam_h - (c["v"] + c["h"] - self.hy) * k      # bottom edge of the card
            tag = "photo_far" if c["kind"] == "far" else "photo"
            self.objs.append(Obj(X, Z, self._card_draw(c, k), Y=Yb, w=10 ** 7, tag=tag))

    def _streaks(self):
        """A tile of soft light streaks that slides over the water (ripples / glints)."""
        s = getattr(self, "_streak_tile", None)
        if s is None:
            import random
            s = self._streak_tile = cairo.ImageSurface(cairo.FORMAT_ARGB32, 256, 96)
            c = cairo.Context(s)
            r = random.Random(3)
            for _ in range(22):
                x, y = r.uniform(0, 256), r.uniform(0, 96)
                ln, a = r.uniform(18, 60), r.uniform(0.25, 0.6)
                for dx in (-256, 0, 256):
                    g = cairo.LinearGradient(x + dx - ln / 2, 0, x + dx + ln / 2, 0)
                    g.add_color_stop_rgba(0, 1, 1, 1, 0)
                    g.add_color_stop_rgba(0.5, 1, 1, 1, a)
                    g.add_color_stop_rgba(1, 1, 1, 1, 0)
                    c.set_source(g)
                    c.rectangle(x + dx - ln / 2, y, ln, 2.2)
                    c.fill()
        return s

    def _water_draw(self, c, k):
        fname, w, h = c["file"], c["w"], c["h"]

        def draw(ctx, t):
            mask = self._surf(fname)
            sw, sh = mask.get_width(), mask.get_height()
            ctx.scale(k, k)
            ctx.translate(0, h)
            ctx.scale(1, -1)
            mp = cairo.SurfacePattern(mask)
            m = cairo.Matrix()
            m.scale(sw / w, sh / h)
            mp.set_matrix(m)
            for speed, scale, alpha in ((22.0, 1.0, 0.55), (-14.0, 1.7, 0.35)):
                src = cairo.SurfacePattern(self._streaks())
                src.set_extend(cairo.EXTEND_REPEAT)
                sm = cairo.Matrix()
                sm.scale(1 / scale, 1 / scale)
                sm.translate(-t * speed, 0)
                src.set_matrix(sm)
                ctx.push_group()
                ctx.set_source(src)
                ctx.mask(mp)
                ctx.pop_group_to_source()
                ctx.paint_with_alpha(alpha)
        return draw

    def _card_draw(self, c, k):
        fname, w, h, pad = c["file"], c["w"], c["h"], c["pad"]
        kind = c["kind"]
        if kind == "water":
            return self._water_draw(c, k)
        phase = (stable_hash(fname) % 100) / 16.0

        def draw(ctx, t):
            surf = self._surf(fname)
            sw, sh = surf.get_width(), surf.get_height()
            ctx.scale(k, k)                                # 1 unit = 1 screen px (1080p), y up, origin bottom-left
            ctx.translate(0, h)
            ctx.scale(1, -1)                               # y down, origin top-left of the card
            if kind == "object":                           # wind: tops sway, the bottom stays put
                sh_ = 0.005 * math.sin(t * 1.15 + phase) + 0.002 * math.sin(t * 2.7 + phase * 2)
                ctx.translate(0, h)
                ctx.transform(cairo.Matrix(1, 0, sh_, 1, 0, 0))
                ctx.translate(0, -h)
            pat = cairo.SurfacePattern(surf)
            m = cairo.Matrix()
            m.scale(sw / w, sh / h)
            pat.set_matrix(m)
            pat.set_filter(cairo.FILTER_GOOD)
            if pad:                                        # edges continue so moving never shows the border
                pat.set_extend(cairo.EXTEND_PAD)
                ex = 900.0
                top = ex if kind == "far" else 0.0
                bottom = 700.0 if kind == "ground" else ex
                ctx.rectangle(-ex, -top, w + 2 * ex, h + top + bottom)
            else:
                ctx.rectangle(0, 0, w, h)
            ctx.set_source(pat)
            ctx.fill()
        return draw

    def clamp_x(self, cam):
        """Keep the view inside the picture (at the stage front) so pans never show its edge."""
        pic_half = self.meta["width"] * self.meta["scale"] / 2.0          # 1080p px = world units at Z = F
        d = max(FOCAL - cam.z, 60.0)
        view_half = 960.0 * d / (FOCAL * max(cam.fz, 0.3))
        lim = max(0.0, pic_half - view_half)
        return clamp(cam.x, self.cx - lim - cam.shift * d / FOCAL, self.cx + lim - cam.shift * d / FOCAL)

    def _build_rain(self):
        self.puddles = []

    # ------------------------------------------------------------------ look
    def _haze_amount(self, d):
        return 0.0                                          # the picture already has its own atmosphere

    def _sky(self, ctx, cam, t):
        ctx.set_source_rgb(0.55, 0.7, 0.85)
        ctx.paint()

    def _ground(self, ctx, cam, t):
        pass

    def _blur_div(self, cam, d):
        div = super()._blur_div(cam, d)
        return min(div, 6)                                  # keep the painted picture readable


    # ================================================================== smooth mode (DepthFlow-style)
    # Every pixel of the picture stands at its own distance; each frame the pixels are moved to where the
    # engine's camera sees them (forward warp, far pixels first so near ones cover them), gaps are filled from
    # the FARTHER neighbour (what was hidden behind), and characters are hidden per pixel wherever the picture
    # is nearer than them - no layer seams, a tree trunk in front hides exactly the right part of a person.
    def _points(self):
        if self._pts is not None:
            return self._pts
        import numpy as np
        from PIL import Image
        z = np.load(os.path.join(self.dir, "zmap.npz"))["z"].astype(np.float32)
        img = Image.open(os.path.join(self.dir, "photo.jpg")).convert("RGB")
        ih, iw = z.shape
        cap = 1280                                         # enough detail, fast enough on a CPU
        if iw > cap:
            nh = int(round(ih * cap / iw))
            z = np.asarray(Image.fromarray(z).resize((cap, nh), Image.NEAREST), dtype=np.float32)
            img = img.resize((cap, nh), Image.LANCZOS)
            ih, iw = z.shape
        rgb = np.asarray(img, dtype=np.uint8)
        try:                                               # stray depth values at object edges fly apart when
            from scipy import ndimage                      # the camera moves: snap them to their neighbours
            z = ndimage.median_filter(z, size=5, mode="nearest")
        except Exception:
            pass
        s = self.meta["width"] * self.meta["scale"] / iw   # picture px -> 1080p screen px
        ox, oy = 960.0 - iw * s / 2.0, 540.0 - ih * s / 2.0
        u = (ox + (np.arange(iw, dtype=np.float32) + 0.5) * s)[None, :].repeat(ih, 0)
        v = (oy + (np.arange(ih, dtype=np.float32) + 0.5) * s)[:, None].repeat(iw, 1)
        k = z / FOCAL
        X = self.cx + (u - 960.0) * k
        Y = self.cam_h - (v - self.hy) * k
        order = np.argsort(-z.ravel(), kind="stable")      # far first: near pixels are written last
        self._pts = dict(X=X.ravel()[order], Y=Y.ravel()[order], Z=z.ravel()[order],
                         rgb=rgb.reshape(-1, 3)[order], step=s)
        return self._pts

    def _warp(self, cam):
        import numpy as np
        P = self._points()
        W, H = self.W, self.H
        dx, d = P["X"] - cam.x, P["Z"] - cam.z
        if cam.yaw:
            c_, s_ = math.cos(cam.yaw), math.sin(cam.yaw)
            dx, d = dx * c_ - d * s_, dx * s_ + d * c_
        ok = d > NEAR
        k = FOCAL * self.S * cam.fz / np.maximum(d, NEAR)
        if cam.mirror:
            dx = -dx
        px = W / 2 + cam.shift * self.S + dx * k
        py = H * cam.horizon + (cam.h - P["Y"]) * k
        ix, iy = px.astype(np.int32), py.astype(np.int32)
        ok &= (ix >= -1) & (iy >= -1) & (ix < W) & (iy < H)
        ix, iy, dd, col = ix[ok], iy[ok], d[ok], P["rgb"][ok]
        img = np.zeros((H + 1, W + 1, 3), np.uint8)
        zb = np.full((H + 1, W + 1), np.inf, np.float32)
        ix, iy = ix + 1, iy + 1                            # 1-px guard band for the splats
        # splat size per point: how many screen px one picture px covers at ITS distance (near = bigger)
        spr = P["Z"][ok] / np.maximum(dd, NEAR) * (P["step"] * self.S * cam.fz)
        r = np.clip(np.ceil(spr - 0.05), 1, 5).astype(np.int8)
        for oy_ in range(int(r.max()) if len(r) else 1):
            for ox_ in range(int(r.max()) if len(r) else 1):
                m = r > max(ox_, oy_)
                if not m.any():
                    continue
                xx, yy, z_ = np.minimum(ix[m] + ox_, W), np.minimum(iy[m] + oy_, H), dd[m]
                front = z_ <= zb[yy, xx]                   # z-test against earlier passes (far first inside)
                xx, yy, z_ = xx[front], yy[front], z_[front]
                img[yy, xx] = col[m][front]
                zb[yy, xx] = z_
        img, zb = img[1:, 1:], zb[1:, 1:]
        hole = ~np.isfinite(zb)
        if hole.any():                                     # gaps: take the FARTHER neighbour (the hidden side)
            for _ in range(8):
                if not hole.any():
                    break
                far_z = np.full(zb.shape, -1.0, np.float32)
                far_c = np.zeros_like(img)
                near_z = np.full(zb.shape, np.inf, np.float32)
                near_c = np.zeros_like(img)
                for sy, sx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    nz = np.roll(zb, (sy, sx), (0, 1))
                    nc = np.roll(img, (sy, sx), (0, 1))
                    fin = hole & np.isfinite(nz)
                    t1 = fin & (nz > far_z)
                    far_z[t1] = nz[t1]
                    far_c[t1] = nc[t1]
                    t2 = fin & (nz < near_z)
                    near_z[t2] = nz[t2]
                    near_c[t2] = nc[t2]
                # a real edge (near thing next to far thing): show the far side, which was hidden behind it;
                # a small gap inside one surface: fill from that surface, never from the sky behind it
                edge = far_z > near_z * 1.25
                best_z = np.where(edge, far_z, np.where(np.isfinite(near_z), near_z, -1.0)).astype(np.float32)
                best_c = np.where(edge[..., None], far_c, near_c)
                got = hole & (best_z > 0)
                zb[got] = best_z[got]
                img[got] = best_c[got]
                hole &= ~got
            if hole.any():                                 # big gaps at the very edge: stretch the nearest row
                from scipy import ndimage
                idx = ndimage.distance_transform_edt(hole, return_distances=False, return_indices=True)
                img = img[idx[0], idx[1]]
                zb = zb[idx[0], idx[1]]
        return img, zb

    def render(self, ctx, cam, t, actors=()):
        actors = list(actors) + list(getattr(self, "place_actors", ()))   # things a place JSON stood in the photo
        if not self.smooth:
            return super().render(ctx, cam, t, actors)
        if hasattr(ctx, "ops"):                            # ▶ the live player (livedraw): the browser draws the
            return self._render_live(ctx, cam, t, actors)  # picture; only the people are sent as drawing
        import numpy as np
        W, H = self.W, self.H
        img, zb = self._warp(cam)
        bg = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        buf = np.ndarray((H, bg.get_stride() // 4), np.uint32, bg.get_data())
        buf[:, :W] = (0xFF000000 | (img[..., 0].astype(np.uint32) << 16) | (img[..., 1].astype(np.uint32) << 8)
                      | img[..., 2].astype(np.uint32))
        bg.mark_dirty()
        ctx.set_source_surface(bg, 0, 0)
        ctx.paint()
        if cam.yaw:
            c_, s_ = math.cos(cam.yaw), math.sin(cam.yaw)
            dep = lambda o: (o.X - cam.x) * s_ + (o.Z - cam.z) * c_   # noqa: E731
        else:
            dep = lambda o: o.Z - cam.z                  # noqa: E731
        self._people = []
        for o in sorted(actors, key=lambda o: -dep(o)):
            d = dep(o)
            if d < NEAR:
                continue
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
            c2 = cairo.Context(surf)
            self.draw_obj(c2, cam, o, t)
            surf.flush()
            a = np.ndarray((H, surf.get_stride() // 4), np.uint32, surf.get_data())[:, :W]
            if not self.people_on_top:                     # a plate never hides its people (see photodepth)
                a[zb < d - 45.0] = 0                       # the picture is nearer here: it covers the actor
            surf.mark_dirty()
            div = self._div(cam, d)
            if div > 1:
                from .depth import blur_surface
                surf = blur_surface(surf, div)
            ctx.set_source_surface(surf, 0, 0)
            ctx.paint()
        self._light(ctx, t)

    def _render_live(self, ctx, cam, t, actors):
        from .livedraw import plate_op
        ctx.op(*plate_op(self, cam, self.W, self.H, self.S))
        if cam.yaw:
            c_, s_ = math.cos(cam.yaw), math.sin(cam.yaw)
            dep = lambda o: (o.X - cam.x) * s_ + (o.Z - cam.z) * c_   # noqa: E731
        else:
            dep = lambda o: o.Z - cam.z                  # noqa: E731
        self._people = []
        for o in sorted(actors, key=lambda o: -dep(o)):
            if dep(o) >= NEAR:
                ctx.save()
                self.draw_obj(ctx, cam, o, t)
                ctx.restore()
        self._light(ctx, t)
