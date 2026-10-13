"""Frame renderer (pycairo) and the FFmpeg encoder pipe."""
import math
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time

import cairo

from . import realworld
from .background import set_layer, Camera
from .character import draw_character
from . import char3d
from .poses import a_wave, a_idle, ACTIONS
from .animals import actions_for, animal_ctx
from .effects import draw_icon, draw_effect, ICON_LIFE, anime_fx, SCREEN_FX, HELD
from .vehicles import VehicleDraw
from .timeline import boat_bob
from .props import draw_prop
from .objects import draw_object, is_object, size as obj_size
from .subtitles import draw_cue
from .util import clamp, lerp, hex_to_rgb, TAU, smoothstep
from .depth import (p_of_z, lift_of_p, P_HORIZON, mood_params, draw_mood, blur_surface, draw_foreground_leaves,
                    draw_front_view, rim_light)
from .timing import estimate, record, fmt
from .timeline import parse_z
from .scene3d import FOCAL as FOCAL_
from .character import BONES as BONES_

_P = None          # project inside worker processes
SHOT_TINT = [None]  # shot check (engine/shotcheck.py): the character to draw in flat magenta
_SURF = None



def _track_fn(thing):
    """time -> (x, y, facing, speed) of a character or a vehicle / prop (for effects that follow it)."""
    if hasattr(thing, "x_at") and hasattr(thing, "y_at") and not hasattr(thing, "pos"):
        def f(tt):
            x, y = thing.x_at(tt), thing.y_at(tt)
            sp = abs(thing.x_at(tt + 0.05) - thing.x_at(tt - 0.05)) / 0.1
            return x, y, (thing.facing_at(tt) or 1), sp
        return f
    if hasattr(thing, "pos"):
        def f(tt):
            x, y, fc = thing.pos(tt)
            sp = abs(thing.pos(tt + 0.05)[0] - thing.pos(tt - 0.05)[0]) / 0.1
            try:
                z0, z1 = thing.z_at(tt - 0.05), thing.z_at(tt + 0.05)
                sp = math.hypot(sp, (z1 - z0) / 0.1 * 2.0)
            except Exception:
                pass
            return x, y, (1 if (fc or 1) >= 0 else -1), sp
        return f
    return None

def _init_worker(project, rss_cap_gb=None):
    global _P, _RSS_CAP
    _P = project
    _RSS_CAP = rss_cap_gb


def _yuv_ok(P):
    """frames go to FFmpeg as YUV 4:2:0 (what the video stores: 3 MB a 1080p frame instead of 8 MB of BGRA) when
    OpenCV is there to convert them in the workers - less to copy between processes, and FFmpeg skips its own
    conversion"""
    if P.W % 2 or P.H % 2:
        return False
    try:
        import cv2  # noqa: F401
        return True
    except Exception:                                   # noqa: BLE001
        return False


def encoder_frame(fi, project=None):
    """frame fi as the bytes FFmpeg is fed (YUV 4:2:0 when _yuv_ok, else BGRA)"""
    P = project or _P
    data = render_frame(fi, P)
    if not _yuv_ok(P):
        return data
    import cv2
    import numpy as np
    img = np.frombuffer(data, np.uint8).reshape(P.H, P.W, 4)
    return cv2.cvtColor(img, cv2.COLOR_BGRA2YUV_I420).tobytes()


# ---------------------------------------------------------------------------- RAM while rendering
_RSS_CAP = None            # GB one worker may hold before it empties its caches (None = no limit)
_FRAMES_SEEN = [0]
LOW_RAM = [False]          # "--low-ram": small caches, 2 workers, short parts, light FFmpeg
KEEP_CACHES = ("engine.codedraw",)   # tiny and slow to rebuild


def free_caches():
    """Empty the big memory stores (3D models, worlds, puppets, backgrounds ...). They fill again by themselves
    with only what the next frames need. -> how many stores were emptied"""
    import gc
    n = 0
    for name, mod in list(sys.modules.items()):
        if not name.startswith("engine.") or name in KEEP_CACHES or mod is None:
            continue
        for k, v in list(vars(mod).items()):
            if ("CACHE" in k.upper() or k in ("_PACK", "_EXT", "_FACES", "_LIVE", "_INST", "_TURN3")) and \
                    isinstance(v, dict) and v:
                v.clear()
                n += 1
    try:
        from . import code3d as _c3
        _c3._PACK_BYTES[0] = 0
    except Exception:                                    # noqa: BLE001
        pass
    gc.collect()
    return n


def _mem_guard():
    """every 30 frames: a worker over its share of the RAM lets go of its caches"""
    _FRAMES_SEEN[0] += 1
    if _RSS_CAP is None or _FRAMES_SEEN[0] % 30:
        return
    from . import sysmon
    r = sysmon.rss_gb()
    if r is not None and r > _RSS_CAP:
        free_caches()


def _surface(W, H):
    global _SURF
    if _SURF is None or _SURF.get_width() != W or _SURF.get_height() != H:
        _SURF = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    return _SURF


def render_frame(fi, project=None, ctx=None):
    """one frame as BGRA bytes; with ctx (a livedraw.Recorder) the drawing goes there and no pixels are made"""
    P = project or _P
    if project is None:
        _mem_guard()
    W, H, S = P.W, P.H, P.S
    live = ctx is not None
    surf = None if live else _surface(W, H)
    if not live:
        ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    t = fi / P.fps
    it = P.item_at(t)
    lt = t - it.start
    sketch_ = getattr(P, "art", "clean") in ("sketch", "stick3d")   # ✏ the sketch engines: pencil / flat colour
    if sketch_ and P.art == "stick3d" and it.kind in ("scene", "hook") and not live:
        from . import sketch, stick3d                     # 🧊 Stick 3D: the same story in a real 3D world
        if it.kind == "scene":
            stick3d.draw_scene(ctx, P, it, lt, P.cue_at(t))
        else:
            stick3d.draw_scene(ctx, P, it.src, it.src_at + lt, P.cue_at(t))
    elif sketch_:
        from . import sketch
        cue_ = P.cue_at(t)
        if it.kind == "scene":
            sketch.draw_scene(ctx, P, it, lt, cue_)
        elif it.kind == "hook":
            sketch.draw_scene(ctx, P, it.src, it.src_at + lt, cue_)
        else:
            sketch.draw_card(ctx, P, it, lt)
    elif it.kind == "scene":
        _draw_scene(ctx, P, it, lt)
    elif it.kind == "hook":
        _draw_scene(ctx, P, it.src, it.src_at + lt)
        _hook_overlay(ctx, P, it, lt)
    else:
        _draw_card(ctx, P, it, lt)
    if not live and it.kind in ("scene", "hook") and getattr(P, "art", "clean") == "klaus":
        from . import klaus                               # 💡 warm light, cool shadows, a readable night
        klaus.grade(surf)
    if not live and it.kind in ("scene", "hook") and getattr(P, "art", "clean") in ("storybook", "wolfwalkers", "handmade"):
        from . import storybook                           # 🖌 ink, watercolour and paper (2.5D)
        storybook.apply(surf)
    # subtitles
    if P.subtitles_on and not sketch_:                     # (the sketch look speaks in bubbles)
        cue = P.cue_at(t)
        if cue is not None:
            draw_cue(ctx, cue, t, W, H, P.sub_style)
    # fades
    a = 0.0
    if it.fade_in and lt < it.fade_in:
        a = 1 - lt / it.fade_in
    if it.fade_out and lt > it.duration - it.fade_out:
        a = max(a, 1 - (it.duration - lt) / it.fade_out)
    if a > 0:
        ctx.identity_matrix()
        if getattr(P, "art", "") == "sketch":             # (pencil fades to the blank page; Stick 3D, like a film,
            #                                               dips to black)
            ctx.set_source_rgba(*sketch.PAPER, clamp(a, 0, 1))
        else:
            ctx.set_source_rgba(0, 0, 0, clamp(a, 0, 1))
        ctx.paint()
    if live:
        return None
    surf.flush()
    return bytes(surf.get_data())


def _blur_amount(sc, lt):
    """0..1 focus-blur strength at time lt (camera moves with "focus_blur": true), with 0.5 s ramps."""
    k, prev_on, st = 0.0, False, None
    for t0, on in sc.blur:
        if t0 > lt:
            break
        prev_on, st = on, t0
    if st is None:
        return 0.0
    # state before the latest switch
    before = False
    for t0, on in sc.blur:
        if t0 >= st:
            break
        before = on
    ramp = smoothstep((lt - st) / 0.5)
    a, b = (1.0 if before else 0.0), (1.0 if prev_on else 0.0)
    return a + (b - a) * ramp


def _leaves_amount(sc, lt):
    k = 0.0
    for a, b in sc.leaves:
        if a <= lt <= b + 1.0:
            k = max(k, smoothstep((lt - a) / 0.8) * (1.0 - smoothstep((lt - b) / 0.8)))
    return k


def _rim_on(bg, mood):
    if bg.time in ("sunset", "evening", "night") and not bg.indoor:
        return True
    return mood.get("tint") is not None and mood.get("vignette", 0) > 0.3


def _draw_scene(ctx, P, it, lt):
    """A scene frame; handheld roll, dutch angles, 3D shake and whip-pan motion blur are applied to the
    finished picture."""
    W, H, S = P.W, P.H, P.S
    f = clamp(int(lt * P.fps), 0, len(it.cams) - 1)
    cam = it.cams[f]
    mode3d = getattr(it.scene, "mode3d", False)
    from . import code3d
    code3d.TOON[0] = bool(getattr(P, "toon", False))      # anime (cel) shading for 3D code drawings
    from . import klaus                                   # 💡 2.5D "art": "klaus": the people lit by the scene's sun
    if getattr(P, "art", "clean") == "klaus" and not getattr(it.bg, "full3d", False):
        from .realworld import time_word
        klaus.LIGHT[0] = klaus.light_for(time_word(it.bg))
    else:
        klaus.LIGHT[0] = None
    from . import palette as _palette                     # a world palette (alien pink grass, autumn ...)
    _palette.use(it.scene.spec.get("palette") if mode3d else None)
    roll = getattr(cam, "roll", 0.0) or 0.0
    blur = (getattr(cam, "blur", 0.0) or 0.0) * S
    shake = mode3d and (cam.sx or cam.sy)
    if abs(roll) < 0.02 and abs(blur) < 3 and not shake:
        _draw_scene_inner(ctx, P, it, lt)
        _anime(ctx, P, it, lt)
        return _grade(ctx, cam, P)
    live = hasattr(ctx, "ops")                           # ▶ live player (livedraw): no picture to turn - the turn
    if not live:                                         # becomes the base transform of the drawing below
        tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        tctx = cairo.Context(tmp)
        tctx.set_antialias(cairo.ANTIALIAS_BEST)
        _draw_scene_inner(tctx, P, it, lt)
        src = tmp
    if abs(blur) >= 3 and not live:
        src = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        bc = cairo.Context(src)
        bc.set_operator(cairo.OPERATOR_ADD)
        n = 7
        for i in range(n):
            bc.set_source_surface(tmp, blur * (i / (n - 1) - 0.5), 0)
            bc.paint_with_alpha(1.0 / n)
    th = abs(math.radians(roll))
    k = math.cos(th) + max(W / H, H / W) * math.sin(th)
    k *= 1.0 + min(abs(blur), W * 0.3) / W
    if shake:
        k *= 1.0 + 2.0 * (abs(cam.sx) + abs(cam.sy)) * S / min(W, H)
    ctx.identity_matrix()
    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()
    ctx.translate(W / 2 + (cam.sx * S if shake else 0.0), H / 2 + (cam.sy * S if shake else 0.0))
    ctx.rotate(math.radians(roll))
    ctx.scale(k, k)
    ctx.translate(-W / 2, -H / 2)
    if live:
        ctx.op("Ib", *[round(v, 4) for v in ctx.get_matrix()])
        _draw_scene_inner(ctx, P, it, lt)
        ctx.op("Ib")
    else:
        ctx.set_source_surface(src, 0, 0)
        ctx.paint()
    ctx.identity_matrix()
    _anime(ctx, P, it, lt)
    _grade(ctx, cam, P)


def _anime(ctx, P, it, lt):
    """Anime screen effects (speed lines, impact frame, rays, gloom, sparkles, swirl) over the finished frame."""
    effs = [e for e in getattr(it.scene, "effects", ()) if e.get("kind") in SCREEN_FX]
    if effs:
        ctx.identity_matrix()
        anime_fx(ctx, effs, lt, P.W, P.H, P.S)


_FG_CACHE = {}


def _foreground(ctx, cam, P):
    """Soft, out-of-focus things right in front of the lens (a pillar edge, leaves, grass, a pole) - the
    near layer that makes a film frame deep. Drawn small and scaled up (= lens blur), slides faster than the
    scene when the camera moves (parallax)."""
    fg = getattr(cam, "fg", None)
    if not isinstance(fg, dict):
        return
    import random
    W, H = P.W, P.H
    kind = str(fg.get("kind", "leaves"))
    side = -1 if str(fg.get("side", "left")) == "left" else 1
    seed = int(fg.get("seed", 0))
    k = 3                                              # drawn at 1/3 size, then blurred: a smooth soft focus
    w, h = max(8, W // k), max(8, H // k)
    m = int(w * 0.35)                                  # extra room past the frame edge (it can slide both ways)
    key = (kind, side, seed, w, h)
    surf = _FG_CACHE.get(key)
    if surf is None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w + m, h)
        c = cairo.Context(surf)
        r = random.Random(seed * 31 + len(kind))
        ex = float(m) if side < 0 else float(w)           # the frame edge it comes in from

        def at(fx):                                        # fx: 0 = at the edge .. 1 = into the frame
            return ex + (fx * w if side < 0 else -fx * w)
        if kind == "pillar":                                # a soft stone column right at the lens
            pw = w * r.uniform(0.11, 0.15) + m                # reaches past the frame edge
            x0 = at(0.0) - m if side < 0 else at(0.0) - (pw - m)
            g = cairo.LinearGradient(x0, 0, x0 + pw, 0)
            lit = 0.72 if side < 0 else 0.28                  # the side that faces the light
            g.add_color_stop_rgba(0, 0.2, 0.15, 0.11, 0.93)
            g.add_color_stop_rgba(lit, 0.36, 0.28, 0.2, 0.93)
            g.add_color_stop_rgba(1, 0.17, 0.13, 0.1, 0.93)
            c.set_source(g)
            c.rectangle(x0, 0, pw, h)
            c.fill()
            for yy in (h * 0.06, h * 0.9):                    # a slightly wider band at the top and the base
                c.set_source_rgba(0.14, 0.11, 0.08, 0.5)
                c.rectangle(x0, yy, pw, h * 0.035)
                c.fill()
        elif kind == "pole":
            pw = w * 0.022
            x0 = at(r.uniform(0.04, 0.09))
            c.set_source_rgba(0.12, 0.12, 0.13, 0.95)
            c.rectangle(x0 - pw / 2, 0, pw, h)
            c.fill()
        elif kind == "grass":
            for _ in range(90):
                fx = r.uniform(-0.3, 0.45)
                bx = at(fx)
                bh = h * r.uniform(0.08, 0.26) * (1.0 - fx * 0.9)
                lean = r.uniform(-0.6, 0.6) * bh * 0.4
                c.move_to(bx - w * 0.006, h)
                c.line_to(bx + lean, h - bh)
                c.line_to(bx + w * 0.006, h)
                c.close_path()
                gcol = r.uniform(0.0, 0.05)
                c.set_source_rgba(0.08 + gcol, 0.17 + gcol, 0.06, 0.93)
                c.fill()
        else:                                              # leaves (and "branch"): a bough from a top corner
            c.set_source_rgba(0.09, 0.07, 0.05, 0.95)
            c.set_line_width(h * 0.02)
            c.move_to(at(-0.3), h * 0.0)
            c.curve_to(at(0.12), h * 0.1, at(0.22), h * 0.12, at(0.34), h * 0.2)
            c.stroke()
            n = 44 if kind != "branch" else 30
            for _ in range(n):
                fx = r.uniform(-0.25, 0.42)
                ly = h * (r.uniform(0.0, 0.46) * (1.15 - fx) if kind != "branch" else r.uniform(0.05, 0.34))
                rx, ry = w * r.uniform(0.04, 0.07), h * r.uniform(0.03, 0.05)
                gcol = r.uniform(0.0, 0.07)
                base = (0.13 + gcol, 0.3 + gcol * 1.3, 0.11)
                # a soft round clump lit from above (the clay look of the trees), not a flat dark blot
                gr = cairo.RadialGradient(at(fx) - rx * 0.3, ly - ry * 0.45, 0, at(fx), ly, max(rx, ry) * 1.1)
                gr.add_color_stop_rgba(0, min(1, base[0] * 1.9), min(1, base[1] * 1.55), min(1, base[2] * 1.6), 0.95)
                gr.add_color_stop_rgba(1, base[0] * 0.6, base[1] * 0.62, base[2] * 0.6, 0.95)
                c.save()
                c.translate(at(fx), ly)
                c.rotate(r.uniform(0, math.pi))
                c.scale(rx, ry)
                c.arc(0, 0, 1, 0, TAU)
                c.restore()
                c.set_source(gr)
                c.fill()
        surf = blur_surface(surf, 3)                       # out of focus (smooth, not blocky pixels)
        if len(_FG_CACHE) > 64:
            _FG_CACHE.clear()
        _FG_CACHE[key] = surf
    dx = float(fg.get("dx", 0.0)) * P.S * 1.6               # parallax: the near layer slides faster
    fade = min(1.0, max(0.0, 1.0 - (abs(dx) - W * 0.25) / (W * 0.2)))
    if fade <= 0.01:
        return
    ctx.save()
    ctx.identity_matrix()
    sx = W / float(w)
    ctx.translate(-dx - (m * sx if side < 0 else 0.0), 0)
    ctx.scale(sx, H / float(h))
    ctx.set_source_surface(surf, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint_with_alpha(fade)
    ctx.restore()


def _grade(ctx, cam, P):
    """Camera 'look': darker picture with a vignette (dark_wide / "dark"), and cinema letterbox bars."""
    W, H = P.W, P.H
    _foreground(ctx, cam, P)
    dim = getattr(cam, "dim", 0.0) or 0.0
    ctx.identity_matrix()
    if dim > 0.01:
        ctx.set_source_rgba(0.02, 0.03, 0.08, 0.55 * dim)
        ctx.paint()
        g = cairo.RadialGradient(W / 2, H / 2, min(W, H) * 0.25, W / 2, H / 2, max(W, H) * 0.75)
        g.add_color_stop_rgba(0, 0, 0, 0, 0)
        g.add_color_stop_rgba(1, 0, 0, 0, min(0.9, 0.95 * dim))
        ctx.set_source(g)
        ctx.paint()
    bars = max(getattr(cam, "bars", 0.0) or 0.0, 1.0 if getattr(P, "letterbox", False) else 0.0)
    if bars > 0.01 and W > H:
        bh = (H - W / 2.39) / 2.0 * bars                   # 2.39:1 cinemascope
        ctx.set_source_rgb(0, 0, 0)
        ctx.rectangle(0, 0, W, bh)
        ctx.rectangle(0, H - bh, W, bh)
        ctx.fill()


def _draw_scene_inner(ctx, P, it, lt):
    W, H, S = P.W, P.H, P.S
    sc, bg = it.scene, it.bg
    f = clamp(int(lt * P.fps), 0, len(it.cams) - 1)
    cam = it.cams[f]
    mood = mood_params(sc.mood_fx, lt) if sc.mood_fx else {}
    blur_k = _blur_amount(sc, lt) if sc.blur else 0.0
    rim = _rim_on(bg, mood)
    depth_mode = sc.depth

    ctx_main = ctx
    _weather_now(sc, bg, lt)                       # weather that changes during the scene (engine/weatherline.py)
    realworld.set_scene(bg, sc)
    from . import nightlights
    nightlights.reset(bg)
    try:                                           # 👁 the 3D eyes: pupils open wide in the dark
        from . import char3d as _c3
        _c3.SCENE_DARK = nightlights.night_amount(bg)
        _c3.FACE_EX = float(getattr(sc, "exaggeration", 1.0) or 1.0)
    except Exception:                              # noqa: BLE001
        pass                                       # (lights register while drawing; the night pass is in _post)

    # ---------------------------------------------------------------- characters (shared helpers)
    infos, layer_of = {}, {}
    states = {cid: tr.state(lt, sc) for cid, tr in sc.tracks.items()}
    haze = bg.haze_color()

    def draw_person(tr, stt, alpha=None, is_crowd=False, cx=None):
        """Draw one character in the CURRENT layer transform (of ctx, or of cx). Returns its info dict."""
        ctx = cx if cx is not None else ctx_main
        c = tr.cdef
        pose = stt.pose
        seat = stt.seat
        a = stt.alpha if alpha is None else alpha
        i = tr.seg_index(lt)
        act = tr.segments[i].action if i >= 0 else "idle"
        if not stt.riding and not is_crowd:
            furn = bg.seat_at(stt.x, c.scale)
            if furn:
                if furn[0] == "seat" and act == "sit":
                    seat = False
                if furn[0] == "bed" and act in ("sleep", "lie"):
                    pose = dict(pose, lift=pose.get("lift", 0) + furn[1] / c.scale)
        sx, sy = getattr(stt, "squash", (1.0, 1.0)) or (1.0, 1.0)
        squash = abs(sx - 1) > 0.005 or abs(sy - 1) > 0.005
        if squash and char3d.ON[0]:
            squash = False                                    # 3D: squashed in the model itself
            sq3 = (sx, sy)
        else:
            sq3 = None
        if squash:
            ctx.save()
            ctx.translate(stt.x, stt.y)
            ctx.scale(sx, sy)
            ctx.translate(-stt.x, -stt.y)

        def paint(cx):
            if char3d.ON[0]:                                      # the 3D page: a real 3D figure
                hd_ = char3d.HEAD.get(id(tr))
                if hd_ is None:
                    mnt_ = getattr(stt, "mount", None)
                    if mnt_ and mnt_ in sc.tracks:
                        hd_ = char3d.HEAD.get(id(sc.tracks[mnt_]))
                if hd_ is None:
                    hd_ = {"camera": math.pi, "away": 0.0}.get(stt.view,
                                                               (1 if stt.facing >= 0 else -1) * (math.pi / 2 + char3d.CHEAT))
                # a bird is in flight when its pose says so (legs tucked and lifted off the ground) - not when it walks
                # or stands a little above the base ground (a walking flamingo was drawn tucked up, as if flying)
                fly_ = c.kind == "bird" and float(pose.get("leg", 0.0)) > 0.6 and float(pose.get("lift", 0.0)) > 10.0
                got3 = char3d.draw(cx, c, pose, stt.x, stt.y, hd_, stt.face, 0.0 if is_crowd else stt.mouth,
                                   lt + (tr.phase if is_crowd else 0.0), a, stt.blink, fly_,
                                   detail=0.6 if is_crowd else 1.0, drag=(stt.extras or {}).get("drag"),
                                   squash=sq3, bank=(stt.extras or {}).get("bank", 0.0))
                if got3 is not None:
                    return got3
            if stt.view in ("camera", "away"):
                mnt = getattr(stt, "mount", None)
                if mnt and mnt in sc.tracks and c.kind == "human":
                    from .animal_front import body_half_width
                    from .character import solve
                    hip = stt.y + solve(pose, c.scale)["hip"][1]             # the saddle
                    leg = (BONES_["thigh"] + BONES_["shin"]) * c.scale
                    return draw_front_view(cx, c, pose, stt.x, hip - leg, stt.view, stt.face, stt.mouth, lt, a,
                                           stt.blink, astride=body_half_width(sc.tracks[mnt].cdef))
                return draw_front_view(cx, c, pose, stt.x, stt.y, stt.view, stt.face, stt.mouth, lt, a, stt.blink)
            return draw_character(cx, c, pose, stt.x, stt.facing, stt.face, 0.0 if is_crowd else stt.mouth,
                                  lt + (tr.phase if is_crowd else 0.0), stt.extras, a, stt.blink, seat,
                                  y=stt.y, shadow=not stt.riding)
        if rim and not is_crowd and not stt.riding and not char3d.ON[0]:
            # (2D only: the rim's clip box is measured in story units round the 2D figure - a 3D figure is drawn
            # by the real camera somewhere else on screen and was cut away whole; 3D figures have their own rim)
            info = _with_rim(ctx, paint, stt, c, S)
        else:
            info = paint(ctx)
        if squash:
            ctx.restore()
        return info

    def depth_insert(cid, tr, stt, is_crowd=False):
        p = p_of_z(stt.z)

        def fn():
            set_layer(ctx, cam, p, W, H, S)
            ctx.translate(0, lift_of_p(p))
            h = 0.5 * (1.0 - p) / (1.0 - P_HORIZON)
            if h > 0.02:
                ctx.push_group()
                info = draw_person(tr, stt, 0.95 if is_crowd else None, is_crowd)
                pat = ctx.pop_group()
                ctx.set_source(pat)
                ctx.paint()
                ctx.set_source_rgba(*haze, min(0.6, h))
                ctx.mask(pat)
            else:
                info = draw_person(tr, stt, 0.95 if is_crowd else None, is_crowd)
            if not is_crowd:
                infos[cid] = info
                layer_of[cid] = p
        return p, fn

    def front_plane(skip_deep):
        """Props, vehicles, riders and front characters (z ~ 0) in the main plane (p = 1)."""
        set_layer(ctx, cam, 1.0, W, H, S)
        held, vehicles = [], []
        for pr in sc.props.values():
            if pr.vtype:
                vx, vy, vf = pr.pos(lt)
                vy += boat_bob(pr, lt)
                vd = _vdraw(pr)
                spin = pr.travel(lt) / (55.0 * pr.scale)
                moving = pr.moving(lt)
                vd.draw_back(ctx, vx, vy, vf, spin, lt, moving, doors=pr.doors_at(lt))
                vehicles.append((pr, vd, vx, vy, vf, spin, moving))
                continue
            state, st0 = pr.at(lt)
            if state[0] in ("rest", "move"):
                if skip_deep and pr.z_at(lt) > 1.0:
                    continue                                   # drawn in its own depth layer
                x, y, _ = pr.pos(lt)
                draw_object(ctx, pr, x, y, lt)
            elif state[0] == "held":
                held.append((pr, state[1]))
        for cid, tr in sorted(sc.tracks.items(), key=lambda kv: -kv[1].z_at(lt)):   # far seats first
            stt = states[cid]
            if stt.riding and stt.alpha >= 0.01:
                infos[cid] = _in_vehicle(ctx, sc.props.get(stt.riding), lt, lambda tr=tr, stt=stt: draw_person(tr, stt))
                layer_of[cid] = 1.0
        for pr, vd, vx, vy, vf, spin, moving in vehicles:
            vd.draw_front(ctx, vx, vy, vf, spin, lt, moving, doors=pr.doors_at(lt))

        def size(tr):
            c = tr.cdef
            return c.scale * (c.animal["girth"] / 40.0 if c.kind == "quadruped" else (0.4 if c.kind == "bird" else 1.0))
        def rider_rank(cid):
            m = getattr(states[cid], "mount", None)
            if not m:
                return 0
            return -1 if states.get(m) is not None and states[m].view == "camera" else 1   # behind a head-on animal
        order = sorted(sc.tracks.items(), key=lambda kv: (rider_rank(kv[0]),
                                                          kv[1].speaking(lt) is not None, -size(kv[1])))
        for cid, tr in order:
            stt = states[cid]
            if stt.riding or stt.alpha < 0.01:
                continue
            if skip_deep and stt.z > 1.0:
                continue
            set_layer(ctx, cam, 1.0, W, H, S)
            infos[cid] = draw_person(tr, stt)
            layer_of[cid] = 1.0
        for pr, who in held:
            if who in infos:
                p = layer_of.get(who, 1.0)
                set_layer(ctx, cam, p, W, H, S)
                if p < 1.0:
                    ctx.translate(0, lift_of_p(p))
                hx, hy = infos[who]["hand"]
                draw_object(ctx, pr, hx, hy, lt, held_hand=(hx, hy))

    if getattr(sc, "mode3d", False):
        _scene3d(ctx, P, it, lt, f, cam, sc, bg, blur_k, states, draw_person, infos)
        _post(ctx, P, it, sc, bg, cam, lt, mood, skip_front=True)
        return

    # ---------------------------------------------------------------- background (+ optional focus blur)
    def background(target_ctx, inserts):
        if depth_mode:
            bg.draw_back_depth(target_ctx, cam, lt, W, H, S, inserts)
        else:
            bg.draw_back(target_ctx, cam, lt, W, H, S)

    inserts = []
    if depth_mode:
        for tr in sc.crowd:
            inserts.append(depth_insert(None, tr, tr.state(lt, sc), True))
        def _rank(cid):
            m = getattr(states[cid], "mount", None)
            if not m:
                return 0
            return -1 if states.get(m) is not None and states[m].view == "camera" else 1
        for cid, tr in sorted(sc.tracks.items(), key=lambda kv: _rank(kv[0])):
            stt = states[cid]
            if not stt.riding and stt.alpha >= 0.01 and stt.z > 1.0:
                inserts.append(depth_insert(cid, tr, stt))
        for pr in sc.props.values():
            if pr.vtype or pr.at(lt)[0][0] == "held" or pr.z_at(lt) <= 1.0:
                continue
            def obj_fn(pr=pr):
                p = p_of_z(pr.z_at(lt))
                set_layer(ctx, cam, p, W, H, S)
                ctx.translate(0, lift_of_p(p))
                x, y, _ = pr.pos(lt)
                draw_object(ctx, pr, x, y, lt)
            inserts.append((p_of_z(pr.z_at(lt)) - 1e-4, obj_fn))
        inserts.append((1.0, lambda: front_plane(True)))

    if blur_k > 0.01:
        bsurf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        bctx = cairo.Context(bsurf)
        if depth_mode:
            bg.draw_back_depth(bctx, cam, lt, W, H, S, (), elements_only=True)
        else:
            bg.draw_back(bctx, cam, lt, W, H, S)
        blurred = blur_surface(bsurf, radius_div=max(2, int(2 + 6 * blur_k)))
        ctx.identity_matrix()
        ctx.set_source_surface(bsurf, 0, 0)
        ctx.paint()
        ctx.set_source_surface(blurred, 0, 0)
        ctx.paint_with_alpha(blur_k)
        if depth_mode:
            for p, fn in sorted(inserts, key=lambda i: i[0]):
                fn()
    else:
        background(ctx, inserts)

    if not depth_mode:
        if sc.crowd:
            set_layer(ctx, cam, 0.93, W, H, S)
            for tr in sc.crowd:
                stt = tr.state(lt, sc)
                draw_person(tr, stt, 0.95, True)
        front_plane(False)

    # ---------------------------------------------------------------- effects + icons
    set_layer(ctx, cam, 1.0, W, H, S)
    for eff in sc.effects:
        if lt < eff["start"] or lt > eff["start"] + eff.get("dur", 2) + 3.0:
            continue
        p = 1.0
        trf = None
        if eff.get("follow") and eff["follow"] in sc.props:
            ax, ay, _ = sc.props[eff["follow"]].pos(lt)
            trf = _track_fn(sc.props[eff["follow"]])
        elif eff.get("who") and eff["who"] in sc.tracks:
            trk = sc.tracks[eff["who"]]
            ax, ay = trk.x_at(lt), trk.y_at(lt)
            if eff["kind"] in HELD and eff["who"] in infos:
                ax, ay = infos[eff["who"]]["hand"]
            trf = _track_fn(trk)
            p = layer_of.get(eff["who"], 1.0)
        else:
            ax, ay = float(eff.get("x") or 0), float(eff.get("y") or 0)
            if depth_mode and float(eff.get("z", 0) or 0) > 1.0:
                p = p_of_z(float(eff["z"]))
        set_layer(ctx, cam, p, W, H, S)
        if p < 1.0:
            ctx.translate(0, lift_of_p(p))
        draw_effect(ctx, eff, lt, (ax, ay), track=trf)
    for cid, tr in sc.tracks.items():
        if cid not in infos:
            continue
        for st0, kind in tr.icons:
            if st0 <= lt <= st0 + ICON_LIFE:
                p = layer_of.get(cid, 1.0)
                set_layer(ctx, cam, p, W, H, S)
                if p < 1.0:
                    ctx.translate(0, lift_of_p(p))
                info = infos[cid]
                draw_icon(ctx, kind, info["head"], info["head_r"], states[cid].facing, lt - st0,
                          max(tr.cdef.scale, 0.7))

    _post(ctx, P, it, sc, bg, cam, lt, mood)


def _post(ctx, P, it, sc, bg, cam, lt, mood, skip_front=False):
    """Everything drawn over the scene: front strip, weather, tint, leaves, mood, picture moments."""
    W, H, S = P.W, P.H, P.S
    if not skip_front:
        bg.draw_front(ctx, cam, lt, W, H, S)
        bg.draw_weather(ctx, lt, W, H)
    else:
        ctx.identity_matrix()
        bg._rain3d = True                                # 3D mode draws its own rain in depth
        if bg.weather not in ("rain", "storm"):
            bg.draw_weather(ctx, lt, W, H)
        bg._rain3d = False
    from . import nightlights                         # lamps, diyas, windows, headlights: pools of light at night
    if getattr(bg, "_plate", False):                  # a 2.5D plate was rendered with its own sky, night and lamps:
        nightlights.LIGHTS.clear()                    # only the people are dimmed (scene3d.SCENE_DARK), not it again
    else:
        bg.tint(ctx, W, H)
        nightlights.apply(ctx, W, H, S, bg, lt, dark_k=0.14 if skip_front else 0.32)   # (3D already has its night)
    wx = getattr(bg, "wx", None)
    if wx is not None and wx.get("changing"):            # a changing sky: clouds, fog, drips and steam after rain
        from . import weatherline
        ctx.identity_matrix()
        weatherline.draw_clouds_cover(ctx, W, H, max(0.0, wx["cloud"] - 0.2) / 0.8 * (1 - 0.6 * wx["rain"]))
        weatherline.draw_fog(ctx, W, H, wx["fog"] * (0.8 if wx["fog"] > 0.3 else 0.0))
        weatherline.draw_drips(ctx, W, H, lt, wx["drips"])
        gy = H * 0.8
        if not skip_front:                                # where the ground is on the screen (2D)
            set_layer(ctx, cam, 1.0, W, H, S)
            gy = clamp(ctx.user_to_device(0, 0)[1], H * 0.3, H)
            ctx.identity_matrix()
        weatherline.draw_steam(ctx, W, H, lt, wx["steam"], ground=gy / H)
    leaves = _leaves_amount(sc, lt) if sc.leaves else 0.0
    if leaves > 0.01:
        draw_foreground_leaves(ctx, cam, lt, W, H, S, leaves, seed=7 + sc.index)
    if mood:
        draw_mood(ctx, mood, lt, W, H)
    for pic in sc.pictures:
        if pic["start"] <= lt <= pic["start"] + pic["dur"]:
            _draw_picture(ctx, pic, lt, W, H, S)
    for tr in getattr(sc, "space_trips", ()):                  # 🚀 a rocket trip: the whole frame
        if tr["start"] <= lt <= tr["start"] + tr["dur"]:
            from . import spacetrip
            spacetrip.draw(ctx, {"route": tr["route"], "dur": tr["dur"]}, lt - tr["start"], W, H, S)
    for tx in getattr(sc, "texts", ()):
        if tx["start"] <= lt <= tx["start"] + tx["dur"]:
            draw_screen_text(ctx, tx, lt - tx["start"], W, H, S)
    for hud in getattr(sc, "physics_huds", ()):               # ⚛ stopwatch, numbers and the graph
        if hud["start"] <= lt <= hud["start"] + hud["dur"]:
            from . import physics
            physics.draw_hud(ctx, hud, lt, W, H, S)


# ============================================================================ weather + true 2.5D (3D) mode
RAIN_LEVEL = {"rain": 1.0, "storm": 1.0, "thunderstorm": 1.0, "monsoon": 1.0, "heavy_rain": 1.0,
              "drizzle": 0.45, "light_rain": 0.45}


def _weather_now(sc, bg, lt):
    """The weather levels now -> bg.wx (cloud, rain, snow, fog, wind, wet, puddles, rainbow ...), and the plain
    weather word for the code that only reads names."""
    from . import weatherline
    if not hasattr(bg, "_weather0"):
        bg._weather0 = bg.weather
    key = (id(sc), round(lt, 3))
    got = getattr(bg, "_wx_key", None)
    if got != key:
        bg.wx = weatherline.state(sc, bg, lt)
        bg._wx_key = key
        if bg.wx.get("changing"):
            bg.weather = weatherline.name_for(bg.wx)
    return bg.wx


def _rain_amount(sc, bg, lt):
    wx = getattr(bg, "wx", None)
    if wx is not None and wx.get("changing"):
        return wx["rain"]
    base = getattr(bg, "_weather0", bg.weather)
    amt = RAIN_LEVEL.get(base, 0.0)
    for st, w, fade in getattr(sc, "weather_fx", ()):
        if st > lt:
            break
        tgt = RAIN_LEVEL.get(w, 0.0)
        amt = amt + (tgt - amt) * smoothstep((lt - st) / max(fade, 0.01))
    return amt


def _apply_weather(bg, sc, lt):
    """Weather events: switch the place's weather (normal mode draws it flat, 3D mode in depth)."""
    if not hasattr(bg, "_weather0"):
        bg._weather0 = bg.weather
    w = bg._weather0
    for st, name, fade in sc.weather_fx:
        if st + fade * 0.4 <= lt:
            w = {"drizzle": "rain", "light_rain": "rain", "heavy_rain": "rain", "monsoon": "rain",
                 "thunderstorm": "storm", "sunny": "clear", "stop": "clear", "none": "clear"}.get(name, name)
    bg.weather = w


def _flash_amount(sc, lt):
    f = 0.0
    for eff in sc.effects:
        if eff["kind"] != "lightning":
            continue
        for d, a in ((0.0, 1.0), (0.18, 0.7)):
            age = lt - eff["start"] - d
            if 0 <= age < 0.25:
                f = max(f, a * (1 - age / 0.25) * eff.get("intensity", 1.0))
    return clamp(f, 0, 1)


_WORLDS = {}


def _action_points(sc, bg):
    """World (X, Z) of everywhere a character, animal, object or vehicle is during the scene."""
    from .world3d import X_of, p3, Z_of_z
    cx = bg.world_w / 2.0
    pts = set()
    dur = max(getattr(sc, "duration", 0.0) or 0.0, 1.0)
    n = int(min(400, dur / 0.2))
    for k in range(n + 1):
        t = dur * k / max(n, 1)
        for tr in sc.tracks.values():
            try:
                x, z = tr.x_at(t), tr.z_at(t)
            except Exception:
                continue
            pts.add((round(X_of(x, p3(z), cx) / 20) * 20, round(Z_of_z(z) / 20) * 20))
        for pr in sc.props.values():
            try:
                x = pr.pos(t)[0] if pr.vtype else (pr.at(t)[0][1] if pr.at(t)[0][0] == "rest" else None)
                if x is None:
                    continue
                z = pr.z_at(t)
            except Exception:
                continue
            pts.add((round(X_of(x, p3(z), cx) / 20) * 20, round(Z_of_z(z) / 20) * 20))
    return list(pts)


def _worn_spots(sc, bg):
    """World (X, Z, radius) of worn, trodden earth: round the things people use (a well, a hand pump, a cot, a door,
    a stall) and where the characters stand most."""
    from .world3d import X_of, p3, Z_of_z
    from . import objects
    cx = bg.world_w / 2.0
    out = []
    for pr in sc.props.values():
        if pr.vtype:
            continue
        try:
            st, _ = pr.at(0.0)
            if st[0] != "rest":
                continue
            x, z = st[1], pr.z_at(0.0)
            w, _h = objects.size(pr)
        except Exception:
            continue
        name = f"{pr.id} {getattr(pr, 'type', '')}".lower()
        if any(k in name for k in ("tree", "bush", "rock", "hill", "fence", "grass", "flower", "cloud")):
            continue
        r = clamp(w * 0.55 + 60.0, 90.0, 420.0)
        out.append((X_of(x, p3(z), cx), Z_of_z(z), r / max(p3(z), 0.3)))
    for tr in sc.tracks.values():                    # where each character starts
        try:
            x, z = tr.x_at(0.0), tr.z_at(0.0)
        except Exception:
            continue
        out.append((X_of(x, p3(z), cx), Z_of_z(z), 110.0 / max(p3(z), 0.3)))
    return out[:40]


SOFT_GROUND = ("dirt", "mud", "sand", "snow")


def _ground_decals(sc, bg, lt, world):
    """Footprints behind walkers and tyre tracks behind vehicles on soft ground; they fade away after a while."""
    if getattr(sc, "spec", {}).get("tracks") is False:
        return []
    from .world3d import X_of, p3
    kind = world.ground_kind()
    cache = getattr(sc, "_decal_surf", None)
    if cache is None:
        cache = sc._decal_surf = {}
    cx = bg.world_w / 2.0
    out = []
    ink = {"snow": (0.55, 0.62, 0.72), "sand": (0.62, 0.5, 0.33), "mud": (0.22, 0.15, 0.1)}.get(kind, (0.35, 0.25, 0.16))

    def W_(x, z):
        p = p3(z)
        return X_of(x, p, cx), FOCAL_ / p

    def soft(x, z, key):
        got = cache.get(key)
        if got is None:
            try:
                got = cache[key] = sc.surface_at(x, z) in SOFT_GROUND
            except Exception:
                got = cache[key] = kind in SOFT_GROUND
        return got
    LIFE = 9.0
    for n, (t0, who, _k) in enumerate(getattr(sc, "footsteps", []) or []):
        if t0 > lt or lt - t0 > LIFE or who not in sc.tracks:
            continue
        tr = sc.tracks[who]
        if tr.cdef.kind == "bird":
            continue
        x, z = tr.x_at(t0), tr.z_at(t0)
        if tr.y_at(t0) > 5 or not soft(x, z, ("f", n)):
            continue
        X, Z = W_(x, z)
        X2, Z2 = W_(tr.x_at(t0 + 0.08), tr.z_at(t0 + 0.08))
        ang = math.atan2(Z2 - Z, X2 - X) if abs(X2 - X) + abs(Z2 - Z) > 0.5 else 0.0
        side = 1 if n % 2 else -1
        off = 11.0 * tr.cdef.scale
        X += -math.sin(ang) * off * side
        Z += math.cos(ang) * off * side
        a = 0.32 * (1.0 - (lt - t0) / LIFE)
        big = 1.5 if tr.cdef.kind != "human" else 1.0
        out.append(("ellipse", X, Z, 12.0 * big * tr.cdef.scale, 6.0 * big * tr.cdef.scale, ang, (*ink, a)))
    for pid, v in sc.props.items():
        if v.vtype not in ("car", "jeep", "bus", "auto", "bike"):
            continue
        moving = [(tt, s_) for tt, s_ in v.states if s_[0] == "move" and tt < lt and lt - (tt + s_[5]) < 14.0]
        if not moving:
            continue
        gap = {"bus": 95.0, "bike": 0.0, "auto": 55.0}.get(v.vtype, 62.0)
        for tt, s_ in moving:
            t_a, t_b = max(tt, lt - 14.0), min(lt, tt + s_[5])
            if t_b - t_a < 0.1:
                continue
            x0_, z0_ = v.pos(t_a)[0], v.z_at(t_a)
            if not soft(x0_, z0_, ("v", pid, round(tt, 2))):
                continue
            k = max(2, int((t_b - t_a) / 0.2))
            pts = [W_(v.pos(t_a + (t_b - t_a) * j / k)[0], v.z_at(t_a + (t_b - t_a) * j / k)) for j in range(k + 1)]
            a = 0.28 * (1.0 - min(1.0, (lt - t_b) / 14.0))
            for sd in ((-1, 1) if gap > 0 else (0,)):
                line = []
                for j, (X, Z) in enumerate(pts):
                    Xa, Za = pts[max(0, j - 1)]
                    Xb, Zb = pts[min(len(pts) - 1, j + 1)]
                    L = math.hypot(Xb - Xa, Zb - Za) or 1.0
                    line.append((X - (Zb - Za) / L * gap * sd, Z + (Xb - Xa) / L * gap * sd))
                out.append(("strip", line, 9.0 if v.vtype != "bike" else 4.0, (*ink, a)))
    return out


def _world_for(it, bg, W, H):
    key = (id(it), W, H)
    w = _WORLDS.get(key)
    if w is None:
        from .world3d import World3D
        from .room3d import Room3D
        if len(_WORLDS) > 12:
            _WORLDS.clear()
        if getattr(it.scene, "photo3d", None):
            from .photoworld import PhotoWorld3D
            w = _WORLDS[key] = PhotoWorld3D(it.scene.photo3d, bg.world_w, W, H,
                                             smooth=str(bg.spec.get("photo_mode", "smooth")) != "layers")
            from .world3d import element_obj
            w.place_actors = [o for o in (element_obj(bg, e, w.cx) for e in bg.elements
                                          if e.get("z") is not None) if o is not None]   # place JSON things
            return w
        cls = Room3D if getattr(it.scene, "room3d", False) else World3D
        if cls is World3D:
            bg._keep_clear = _action_points(it.scene, bg)       # houses / barns / trees stay out of the action
        w = _WORLDS[key] = cls(bg, W, H, seed=(getattr(it.scene, "index", 0) * 31 + 7))
        if cls is World3D:
            try:
                w.ground_marks = _worn_spots(it.scene, bg)
            except Exception:
                w.ground_marks = []
    return w


FRONT_VIEW_VEHICLES = ("jeep", "car", "auto", "bus")


def _in_vehicle(ctx, v, lt, paint):
    """Draw someone sitting in a car / jeep / bus / auto: nothing below the floor of the body shows."""
    from .timeline import CLOSED_VEHICLES
    if v is None or v.vtype not in CLOSED_VEHICLES:
        return paint()
    vx, vy, vf = v.pos(lt)
    ctx.save()
    ctx.rectangle(vx - 5000, vy + 44 * v.scale, 10000, 5000)
    ctx.clip()
    info = paint()
    ctx.restore()
    return info


PLATE_WIDE = [1.0]       # tools/make_plates.py: render the place this much wider than a normal shot


def _plate_camera(c3, world, cam=None):
    """A plate is right only from the place it was rendered from: keep the camera there and turn the dolly the
    director wanted into the same framing with the lens (a push-in = a zoom, following someone = a pan). Seen
    from its own point every card lines up exactly, at any zoom and any turn - no tears, no holes."""
    from .scene3d import FOCAL
    from .world3d import Z_of_z
    Zs = Z_of_z(getattr(cam, "d", 0.0) or 0.0) if cam is not None else c3.z + max(c3.focus or 0.0, 80.0)
    # (the subject the shot was framed on: its real depth, not the focus distance)
    Xs = getattr(cam, "x", c3.x) if cam is not None else c3.x
    d_old = max(Zs - c3.z, 80.0)
    d_new = max(Zs, 80.0)                                          # (the plate camera stands at z = 0)
    fz = clamp(c3.fz * d_new / d_old, 1.0, 2.8)
    over = float(world.meta.get("overscan", 1.1))                   # how much bigger than the screen the plate is
    view = math.atan(960.0 / (FOCAL * fz))                         # half the view, and half the picture
    room = max(0.0, math.atan(960.0 * over / FOCAL) - view)
    c3.x, c3.z, c3.h = world.cx, 0.0, world.cam_h
    c3.fz = fz
    c3.yaw = clamp(math.atan2(Xs - world.cx, d_new), -room, room)
    # tilt (= a crop of the plate: still exact) so the subject's chest sits a little above the middle, keeping the
    # zoomed plate over the whole frame (it covers 1080 x 1.1 px around its own horizon at zoom 1)
    hy0 = world.hor0 * 1080.0
    want = 0.56 * 1080.0 - (world.cam_h - 170.0) * FOCAL * fz / d_new     # horizon row that puts Y=170 at 56%
    half = 540.0 * over * fz
    centre = clamp(want + (540.0 - hy0) * fz, 1080.0 - half, half)        # the plate's middle row on screen
    c3.horizon = (centre - (540.0 - hy0) * fz) / 1080.0
    c3.shift = 0.0
    c3.focus = d_new


def _scene3d(ctx, P, it, lt, f, cam, sc, bg, blur_k, states, draw_person, infos):
    """True 2.5D frame: the place as a depth world, everyone placed at their real distance."""
    from .world3d import p3, X_of, cam3_from, Z_of_z
    from .scene3d import Obj, jeep_front
    from .scene3d import Cam3
    W, H, S = P.W, P.H, P.S
    world = _world_for(it, bg, W, H)
    world.look = str((getattr(sc, "cinema", None) or {}).get("look", "flat") or "flat")
    c3 = cam3_from(cam)
    if PLATE_WIDE[0] != 1.0:                       # making a plate: a wider view than the screen (room to frame)
        c3.fz /= PLATE_WIDE[0]
    foc = getattr(it, "focus3d", None)
    c3.focus = foc[min(f, len(foc) - 1)] if foc else c3.focus
    # depth of field: soft enough to lift the subject off the background, never so much that the scene melts
    c3.aperture = min(1.25, 0.35 + 0.7 * blur_k + 0.6 * (getattr(cam, "ap", 0.0) or 0.0))
    world.rain = _rain_amount(sc, bg, lt)
    wx_ = getattr(bg, "wx", None) or {}
    world.cloud = wx_.get("cloud", 0.0) if wx_.get("changing") else 0.0     # clouds over the sun: softer light
    world.wx = wx_
    world.decals = _ground_decals(sc, bg, lt, world) if getattr(world, "ground_kind", None) else []
    world.flash = _flash_amount(sc, lt)
    world.frame = f
    lights_on = bg.time in ("evening", "night", "sunset") or world.rain > 0.2
    actors = []
    rev = getattr(cam, "rev", None)
    full = bool(getattr(world, "full", False))         # the 3D page: a whole world, the camera can turn any way
    rev_real = full and rev is not None                # a real reverse angle: the camera goes round to the far side
    d_sub = getattr(cam, "d", 0.0) or 0.0
    if full and d_sub > 900.0 and rev is None and not getattr(cam, "pov", None):
        # the action is far out in the world (a drive up the jungle path): the camera travels out there too,
        # instead of a long telephoto through 40 m of haze
        from .world3d import Z_of_z as _Zz
        from .scene3d import FOCAL as _F
        Zs_ = _Zz(d_sub)
        lens_ = max(1.0, getattr(cam, "lens", 1.0) or 1.0)     # (a long lens still stands back a little)
        want_ = Zs_ - _F / max(0.3, cam.z) * lens_
        if want_ > c3.z:
            c3.z = want_
            c3.fz = lens_
            c3.focus = max(Zs_ - c3.z, 80.0)

    def zmap(z):                                   # reverse angle: near and far swap around the pivot
        return clamp(2.0 * rev - z, 0.0, 3000.0) if (rev is not None and not rev_real) else z

    if rev is not None:
        swap = {"camera": "away", "away": "camera"}
        for stt in states.values():
            if not rev_real:
                if 2.0 * rev - stt.z < -40:
                    stt.alpha = 0.0                    # it is behind the camera now
                stt.z = zmap(stt.z)
            stt.view = swap.get(stt.view, stt.view)
    if rev_real:                                   # same framing, seen from the far side (mirrored: the people
        d_sw = getattr(cam, "d", 0.0) or 0.0       # keep their sides of the screen - the 180-degree rule)
        ds_ = Z_of_z(d_sw) - c3.z
        c3.z = Z_of_z(clamp(2.0 * rev - d_sw, 0.0, 3000.0)) + ds_
        c3.yaw = math.pi
        c3.mirror = True
    elif full and (getattr(cam, "orb", 0.0) or getattr(cam, "arc", 0.0)):
        Zp = Z_of_z(getattr(cam, "d", 0.0) or 0.0)         # a real orbit: the camera goes round the subject
        ds_ = max(Zp - c3.z, 150.0)
        a_ = math.radians(getattr(cam, "orb", 0.0) or 0.0) + math.atan2(getattr(cam, "arc", 0.0) or 0.0, ds_)
        c3.x = cam.x + ds_ * math.sin(a_)
        c3.z = Zp - ds_ * math.cos(a_)
        c3.yaw = -a_
        c3.shift = 0.0
    if full and getattr(cam, "yaw", 0.0) and not getattr(cam, "pov", None):
        c3.yaw = (c3.yaw or 0.0) + math.radians(cam.yaw)          # "turn": the camera turns its head

    room = getattr(world, "room", False)
    if getattr(world, "people_on_top", False):     # 🖼 a 2.5D plate (tools/make_plates.py): the camera stays where
        _plate_camera(c3, world, cam)              # the plate was made - it zooms and turns, so it never tears
        bg._plate = True                           # (its night and lamps are already in the picture: see _post)
    elif getattr(world, "photo", False):            # your picture: its own camera height and horizon
        c3.h = clamp(c3.h * world.cam_h / 345.0, world.cam_h * 0.8, world.cam_h * 1.25)
        c3.horizon = clamp(c3.horizon + world.hor0 - 0.5, world.hor0 - 0.07, world.hor0 + 0.07)
        c3.z = max(c3.z, -80.0)                      # (one picture: no big cranes / tilts that leave it)
        c3.x = world.clamp_x(c3)                     # the camera stays inside the picture
    if room:
        from .room3d import ROOM_H
        c3.h = min(c3.h, getattr(world, "room_h", ROOM_H) - 70.0)   # cranes stop under the ceiling

    def at(x, z):
        p = p3(z)
        X = x if room else X_of(x, p, world.cx)
        if rev is not None and not rev_real:   # the scenery is mirrored, the people keep their sides (180-degree rule)
            X = 2.0 * c3.x - X
        return X, FOCAL_ / p

    pov = getattr(cam, "pov", None)
    if pov in sc.tracks and pov in states:          # through this character's eyes
        ps = states[pov]
        X, Z = at(ps.x, ps.z)
        tr_ = sc.tracks[pov]
        eye = (255.0 if tr_.cdef.kind == "human" else 150.0) * tr_.cdef.scale + ps.y
        c3 = Cam3(x=X, h=eye, z=Z - 25.0, horizon=0.5 + (getattr(cam, "hor", 0.5) - 0.5), focus=c3.focus,
                  aperture=c3.aperture)
        c3.focus = 900.0
        c3.pov = True
        best = None                                     # look at who they are facing / talking to
        look = getattr(cam, "look", None)
        if look:                                        # "look_at": this person / thing / place
            if look in states and look != pov:
                Xo, Zo = at(states[look].x, states[look].z)
                best = ((0, 0), Xo, Zo)
            elif look in sc.props:
                pr_ = sc.props[look]
                Xo, Zo = at(pr_.pos(lt)[0], pr_.z_at(lt))
                best = ((0, 0), Xo, Zo)
            else:
                for e in bg.elements:                   # a thing of the place (well, hut, temple ...)
                    if e.get("id") == look and e.get("z") is not None:
                        Xo, Zo = at(float(e["x"]), float(e["z"]))
                        best = ((0, 0), Xo, Zo)
                        break
        for oid, os_ in (states.items() if best is None else ()):
            if oid == pov or os_.alpha < 0.01:
                continue
            Xo, Zo = at(os_.x, os_.z)
            if (Zo - c3.z < 60 and not full) or math.hypot(Xo - c3.x, Zo - c3.z) < 150:
                continue
            spk = any(sp.who == oid and sp.start <= lt < sp.end for sp in sc.speeches)
            sc_ = (0 if spk else 1, abs(Zo - c3.z) + 0.5 * abs(Xo - X))
            if best is None or sc_ < best[0]:
                best = (sc_, Xo, Zo)
        if best is not None:                            # turn the head toward them
            a_ = math.atan2(best[1] - c3.x, best[2] - c3.z)
            c3.yaw = a_ if full else clamp(a_, -1.1, 1.1)
            c3.focus = max(200.0, math.hypot(best[1] - c3.x, best[2] - c3.z))
        elif full:                                      # nobody to look at: where they face
            c3.yaw = {"away": 0.0, "camera": math.pi}.get(ps.view, 0.9 * (1 if ps.facing >= 0 else -1))
        if full and getattr(cam, "yaw", 0.0):
            c3.yaw += math.radians(cam.yaw)             # look around / turn the head
        if tr_.gait_at(lt) > 0:                         # walking: the head bobs a little
            run_ = 1.6 if getattr(tr_, "running_at", None) and tr_.running_at(lt) else 1.0
            c3.h += 7.0 * run_ * (abs(math.sin(math.pi * 1.9 * run_ * lt)) - 0.5)
            c3.yaw += 0.012 * run_ * math.sin(math.pi * 0.95 * run_ * lt)
    if full and not rev_real and c3.yaw and abs(math.sin(c3.yaw)) + abs(1 - math.cos(c3.yaw)) > 0.05:
        # the camera went round (orbit / spin / point of view / turn): standing people show the side the camera
        # really sees - their back from behind, the other profile from the far side
        fy, cyw = math.sin(c3.yaw), math.cos(c3.yaw)
        for cid, tr in sc.tracks.items():
            stt = states.get(cid)
            if stt is None or stt.alpha < 0.01 or stt.riding or getattr(stt, "mount", None) or tr.crowd:
                continue
            if tr.cdef.kind == "bird" or (tr.cdef.kind == "human" and getattr(tr.cdef, "style", "") == "classic"):
                continue
            if tr.gait_at(lt) > 0 or tr.flip_at(lt) is not None:
                continue                                  # walkers: handled just below
            if stt.view == "camera":
                wx, wz = 0.0, -1.0
            elif stt.view == "away":
                wx, wz = 0.0, 1.0
            else:
                wx, wz = (1.0 if stt.facing >= 0 else -1.0), 0.0
            dot = wx * fy + wz * cyw                       # + = the camera looks the way they look (their back)
            if dot > 0.6:
                stt.view = "away"
            elif dot < -0.6:
                stt.view = "camera"
            else:
                stt.view = None
                side = wx * cyw - wz * fy
                if abs(side) > 1e-3:
                    stt.facing = 1 if side > 0 else -1
    # camera-relative views (how 2D characters live in 3D games: the drawing is chosen from the angle between
    # where the character walks and where the camera is) - walkers show front / back / side as the camera moves
    cy_, sy_ = math.cos(c3.yaw or 0.0), math.sin(c3.yaw or 0.0)
    for cid, tr in sc.tracks.items():
        stt = states.get(cid)
        if stt is None or stt.alpha < 0.01 or stt.riding or getattr(stt, "mount", None) or tr.crowd:
            continue
        cdef_ = tr.cdef
        if cdef_.kind == "bird" or (cdef_.kind == "human" and getattr(cdef_, "style", "") == "classic"):
            continue
        if tr.gait_at(lt) <= 0 or tr.flip_at(lt) is not None:
            continue
        X1, Z1 = at(stt.x, stt.z)
        X2, Z2 = at(tr.x_at(lt + 0.15), zmap(tr.z_at(lt + 0.15)))
        hx, hz = X2 - X1, Z2 - Z1
        hl = math.hypot(hx, hz)
        if hl < 4.0:
            continue
        hx, hz = hx / hl, hz / hl
        cxv, czv = c3.x - X1, c3.z - Z1
        cl = math.hypot(cxv, czv) or 1.0
        dot = (hx * cxv + hz * czv) / cl
        speaking = any(sp.who == cid and sp.start <= lt < sp.end for sp in sc.speeches)
        if dot > 0.55:
            stt.view = "camera"
        elif dot < -0.55 and not speaking:
            stt.view = "away"
        else:
            stt.view = None
            side = hx * cy_ - hz * sy_
            if getattr(c3, "mirror", False):
                side = -side
            if abs(side) > 1e-3:
                stt.facing = 1 if side > 0 else -1
    char3d.ON[0] = full and bool(getattr(bg, "chars3d", True))
    char3d.HEAD.clear()
    if char3d.ON[0]:                                   # real 3D figures: which way each one really faces
        others_ = [t_ for t_ in sc.tracks.values() if not t_.crowd]
        for cid, tr in sc.tracks.items():
            if states.get(cid) is not None and states[cid].alpha >= 0.01:
                hd_ = char3d.heading(tr, lt, at, others_)
                try:                                   # "facing": "camera" -> toward where the camera really is now
                    if tr.view_at(lt) == "camera" and tr.gait_at(lt) <= 0 and tr.convo_face(lt) is None:
                        X1_, Z1_ = at(tr.x_at(lt), tr.z_at(lt))
                        if math.hypot(c3.x - X1_, c3.z - Z1_) > 1.0:
                            hd_ = math.atan2(c3.x - X1_, c3.z - Z1_)
                except Exception:                      # noqa: BLE001
                    pass
                char3d.HEAD[id(tr)] = hd_
    inside = getattr(cam, "inside", None)
    if inside in sc.props and sc.props[inside].vtype:
        return _inside_vehicle(ctx, P, it, lt, cam, sc, bg, world, states, draw_person, infos, inside, at)

    def person_obj(cid, tr, stt, is_crowd=False):
        X, Z = at(stt.x, stt.z)
        x0 = stt.x
        i_ = tr.seg_index(lt) if cid else -1
        ex_ = tr.segments[i_].params.get("_exit") if i_ >= 0 else None
        if ex_ and len(ex_) > 3 and ex_[3] is not None and lt < ex_[2] + 1.2 and ex_[0] in sc.props:
            Z = at(0, sc.props[ex_[0]].z_at(lt))[1] + 3.0      # stepping out from behind the car's side
        if getattr(stt, "mount", None) and stt.mount in states:
            # side / back view: the rider is in front of the animal's body; front view: the animal's head is nearer
            Z += 2.0 if states[stt.mount].view == "camera" else -2.0

        def draw(c, t, tr=tr, stt=stt, cid=cid, x0=x0):
            c.translate(-x0, 0)
            info = draw_person(tr, stt, 0.95 if is_crowd else None, is_crowd, cx=c)
            if is_crowd or not info:
                return
            infos[cid] = info
            for pr in sc.props.values():                           # a prop in this character's hand
                if not pr.vtype:
                    state, _ = pr.at(lt)
                    if state[0] == "held" and state[1] == cid:
                        hx, hy = info["hand"]
                        draw_object(c, pr, hx, hy, lt, held_hand=(hx, hy))
            for eff in sc.effects:                                  # effects attached to this character
                if eff.get("who") == cid and eff["start"] <= lt <= eff["start"] + eff.get("dur", 2) + 3.0:
                    anc_ = info["hand"] if eff["kind"] in HELD else (tr.x_at(lt), tr.y_at(lt))
                    draw_effect(c, eff, lt, anc_, track=_track_fn(tr))
            for st0, kind in tr.icons:
                if st0 <= lt <= st0 + ICON_LIFE:
                    draw_icon(c, kind, info["head"], info["head_r"], stt.facing, lt - st0, max(tr.cdef.scale, 0.7))
        o_ = Obj(X, Z, draw, w=320, tag="actor")
        if cid and not is_crowd:                    # the see-through rule: scenery in front of a person fades
            seg_ = tr.segments[i_] if i_ >= 0 else None
            hiding = seg_ is not None and seg_.action in ("hide", "peek") and lt <= seg_.end + 60
            if not hiding:
                o_.person = True
            o_.h = (300.0 if tr.cdef.kind == "human" else 170.0) * tr.cdef.scale + max(0.0, stt.y)
            o_.tint = cid == SHOT_TINT[0]
        return o_

    for tr in sc.crowd:
        stt = tr.state(lt, sc)
        if stt.alpha >= 0.01:
            actors.append(person_obj(None, tr, stt, True))
    riders = {}
    for cid, tr in sc.tracks.items():
        stt = states[cid]
        if stt.alpha < 0.01:
            continue
        if stt.riding:
            riders.setdefault(stt.riding, []).append((cid, tr, stt))
            continue
        if cid == pov:
            continue
        actors.append(person_obj(cid, tr, stt))
    from . import drive3d
    for pr in sc.props.values():
        if pr.vtype:
            vx, vy, vf = pr.pos(lt)
            vy += boat_bob(pr, lt)
            z_story = pr.z_at(lt)
            z = zmap(z_story)
            X, Z = at(vx, z)
            mdl = drive3d.model_of(pr, getattr(P, "settings", None))
            if mdl is not None:                       # a real 3D vehicle: turned the way its nose points
                name_, meta_ = mdl
                hx_, hz_ = pr.heading_at(lt)
                deg_ = drive3d.world_deg(at, zmap, vx, z_story, hx_, hz_)
                moving_ = pr.moving(lt)
                sp_ = float((meta_.get("ride") or {}).get("speed") or 220.0)
                tdrive = pr.travel(lt) / max(1.0, sp_) * 4.0

                def draw(c, t, pr=pr, vx=vx, vy=vy, deg_=deg_, name_=name_, meta_=meta_, tdrive=tdrive,
                         moving_=moving_):
                    c.translate(-vx, 0)
                    sc_ = pr.scale * float(pr.spec.get("height") or meta_.get("height") or 240) / \
                        float(meta_.get("height") or 240)
                    h_ = float(meta_.get("height") or 240) * sc_
                    bump = (1.6 * math.sin(lt * 23.0) if moving_ else 0.0) * sc_
                    inside = sorted(riders.get(pr.id, ()), key=lambda r: r[0])
                    seats = drive3d.seat_offsets(meta_, deg_, sc_)
                    a_ = math.radians(deg_)
                    hX, hZ = math.cos(a_), -math.sin(a_)          # the nose on the ground (world X, Z)

                    def paint_riders():
                        if not seats:                             # no seat points: where the story put them
                            for cid, tr, stt in inside:
                                infos[cid] = draw_person(tr, stt, cx=c)
                            return
                        order = []
                        for n_, (cid, tr, stt) in enumerate(inside):
                            if not seats:
                                break
                            dx_, dy_, dz_ = seats[min(n_, len(seats) - 1)]
                            order.append((dz_, cid, tr, stt, dx_, dy_))
                        for dz_, cid, tr, stt, dx_, dy_ in sorted(order, key=lambda o: -o[0]):   # far seats first
                            stt.x = vx + dx_
                            hip = 126.0 if (meta_.get("ride") or {}).get("pose") == "pedal" else 82.5
                            stt.y = vy + bump + max(0.0, dy_ - hip * tr.cdef.scale)
                            if abs(hZ) > 1.25 * abs(hX):
                                stt.view = "camera" if hZ < 0 else "away"
                            else:
                                stt.view = None
                                stt.facing = 1 if hX >= 0 else -1
                            old_h = char3d.HEAD.get(id(tr))
                            char3d.HEAD[id(tr)] = math.atan2(hX, hZ)      # 3D figures sit facing where it goes
                            try:
                                infos[cid] = draw_person(tr, stt, cx=c)
                            finally:
                                if old_h is None:
                                    char3d.HEAD.pop(id(tr), None)
                                else:
                                    char3d.HEAD[id(tr)] = old_h
                    if name_ not in drive3d.OPEN:
                        paint_riders()                            # inside: the body and glass go over them
                    try:
                        tilt_ = drive3d.body_tilt(pr, lt) if pr.vtype not in ("bike",) else (0.0, 0.0)
                    except Exception:
                        tilt_ = (0.0, 0.0)
                    ok = drive3d.draw(c, name_, meta_, vx, vy + bump, h_, deg_, tdrive, pr.spec.get("color"), tilt=tilt_)
                    if name_ in drive3d.OPEN or not ok:
                        paint_riders()
                vo = Obj(X, Z + 1.0, draw, w=700 * pr.scale, tag="actor")
                vo.seethru = not moving_ and not riders.get(pr.id)
                actors.append(vo)
                continue
            view = pr.view_at(lt) if pr.vtype in FRONT_VIEW_VEHICLES else None
            if rev is not None:
                view = {"front": "back", "back": "front"}.get(view, view)
            moving = pr.moving(lt)
            spd = pr.speed_at(lt) if moving else 0.0

            def draw(c, t, pr=pr, vx=vx, vy=vy, vf=vf, view=view, moving=moving, spd=spd):
                c.translate(-vx, 0)
                if view:
                    c.save()
                    c.translate(vx, vy)
                    k = pr.scale * {"bus": 1.45, "auto": 0.8}.get(pr.vtype, 1.0)
                    c.scale(k, k)
                    col = pr.spec.get("color") or ("#5b7f3a" if pr.vtype == "jeep" else "#c0392b")
                    inside = riders.get(pr.id, ())

                    def riders_fn(cc, inside=inside, back=(view == "back")):
                        seats = (-72, 72, 0)
                        for n_, (cid_, tr_, stt_) in enumerate(sorted(inside, key=lambda r: r[0])):
                            sx_ = seats[n_ % 3] * (-1 if back else 1)
                            leg = 142.0 * tr_.cdef.scale
                            draw_front_view(cc, tr_.cdef, stt_.pose, sx_, 150 - leg, "away" if back else "camera",
                                            stt_.face, stt_.mouth, lt, 1.0, stt_.blink)
                    jeep_front(c, t, col, 1.0 if lights_on or pr.spec.get("lights") else 0.0, spd, world.rain,
                               back=(view == "back"), riders_fn=riders_fn if inside else None,
                               driver=bool(pr.spec.get("driver", False)))
                    c.restore()
                    return                                            # riders sit inside, behind the glass
                vd = _vdraw(pr)
                spin = pr.travel(lt) / (55.0 * pr.scale)
                doors = pr.doors_at(lt)
                vd.draw_back(c, vx, vy, vf, spin, lt, moving, doors=doors)
                for cid, tr, stt in sorted(riders.get(pr.id, ()), key=lambda r: -r[1].z_at(lt)):   # far seats first
                    infos[cid] = _in_vehicle(c, pr, lt, lambda tr=tr, stt=stt: draw_person(tr, stt, cx=c))
                vd.draw_front(c, vx, vy, vf, spin, lt, moving, doors=doors)
            vo = Obj(X, Z + 1.0, draw, w=700 * pr.scale, tag="actor")
            vo.seethru = not moving and not riders.get(pr.id)     # a parked bus never hides the people
            actors.append(vo)
            continue
        state, _ = pr.at(lt)
        if state[0] in ("rest", "move"):
            x, y, _ = pr.pos(lt)
            if rev is not None and 2.0 * rev - pr.z_at(lt) < -40:
                continue
            X, Z = at(x, zmap(pr.z_at(lt)))

            def draw(c, t, pr=pr, x=x, y=y):
                c.translate(-x, 0)
                draw_object(c, pr, x, y, lt)
            ow = obj_size(pr)[0] if is_object(pr) else 120
            ob = Obj(X, Z + 1.5, draw, w=max(200, ow * 1.6), tag="actor")
            back = _ground_back(pr)
            if back is not None:                        # a hill / stage / floor: sort by its back edge
                ob.sortZ = Z + back
            actors.append(ob)
    for eff in sc.effects:
        if eff.get("who") or not (eff["start"] <= lt <= eff["start"] + eff.get("dur", 2) + 3.0):
            continue
        if eff["kind"] == "lightning":                               # the bolt strikes far away
            Zl = 7000.0
            k = Zl / FOCAL_

            def draw(c, t, eff=eff, k=k):
                c.scale(k, k)
                draw_effect(c, eff, lt, (0.0, 0.0))
            actors.append(Obj(c3.x + 900, Zl, draw, w=5000, tag="actor"))
            continue
        trf = None
        if eff.get("follow") and eff["follow"] in sc.props:
            v = sc.props[eff["follow"]]
            ax, ay, _ = v.pos(lt)
            z = v.z_at(lt)
            trf = _track_fn(v)
        else:
            ax, ay, z = float(eff.get("x") or 0), float(eff.get("y") or 0), float(eff.get("z", 0) or 0)
        X, Z = at(ax, zmap(z))

        def draw(c, t, eff=eff, ax=ax, ay=ay, trf=trf):
            c.translate(-ax, 0)
            draw_effect(c, eff, lt, (ax, ay), track=trf)
        actors.append(Obj(X, Z - 1.0, draw, w=800, tag="actor"))
    ctx.identity_matrix()
    world.render(ctx, c3, lt, actors)
    ctx.identity_matrix()


def _inside_vehicle(ctx, P, it, lt, cam, sc, bg, world, states, draw_person, infos, vid, at):
    """3D mode "inside" shot: the camera rides in the vehicle. The riders sit in the cabin in profile,
    the world streams past the windows behind them with real parallax."""
    import copy
    from .scene3d import Cam3, Obj
    from .timeline import VEHICLES
    from .util import hex_to_rgb, darker, lighter
    W, H, S = P.W, P.H, P.S
    v = sc.props[vid]
    vx, vy, vf = v.pos(lt)
    Xv, Zv = at(vx, v.z_at(lt))
    moving = v.moving(lt)
    kind = v.vtype
    c3 = Cam3(x=Xv, h=175.0, z=Zv - 300.0, horizon=0.5, focus=200.0, aperture=0.9)
    cw = Cam3(x=Xv, h=175.0 + (3.0 * math.sin(lt * 13.0) + 1.5 * math.sin(lt * 23.0) if moving else 0.0),
              z=c3.z, horizon=0.5, focus=2600.0, aperture=1.0)
    lights_on = bg.time in ("evening", "night", "sunset")
    actors = []
    inside = []
    for cid, tr in sc.tracks.items():
        stt = states[cid]
        if stt.alpha < 0.01:
            continue
        if stt.riding == vid:
            inside.append((cid, tr, stt))
            continue
        X, Z = at(stt.x, stt.z)
        if Z - cw.z < 380:
            continue

        def draw(c, t, tr=tr, stt=stt):
            c.translate(-stt.x, 0)
            draw_person(tr, stt, cx=c)
        actors.append(Obj(X, Z, draw, w=320, tag="actor"))
    for pr in sc.props.values():
        if pr.vtype and pr.id != vid:
            px, py, pf = pr.pos(lt)
            X, Z = at(px, pr.z_at(lt))
            if Z - cw.z > 380:
                vd = _vdraw(pr)

                def draw(c, t, pr=pr, px=px, py=py, pf=pf, vd=vd):
                    c.translate(-px, 0)
                    sp = pr.travel(lt) / (55.0 * pr.scale)
                    vd.draw_back(c, px, py, pf, sp, lt, pr.moving(lt))
                    vd.draw_front(c, px, py, pf, sp, lt, pr.moving(lt))
                actors.append(Obj(X, Z, draw, w=700, tag="actor"))
    ctx.identity_matrix()
    world.render(ctx, cw, lt, actors)
    ctx.identity_matrix()
    # ---- the cabin wall with its windows (fixed to the camera: it rides along)
    Zw = c3.z + 560.0
    col = hex_to_rgb(v.spec.get("color") or {"bus": "#f2b134", "jeep": "#5b7f3a", "auto": "#2e7d32"}.get(kind, "#c0392b"))
    wall = lighter(col, 0.55) if kind != "jeep" else lighter(col, 0.3)
    if kind == "bus":
        wins, y0, y1 = [(k * 300 - 120, k * 300 + 120) for k in range(-5, 6)], 115.0, 285.0
    elif kind in ("auto", "jeep"):
        wins, y0, y1 = [(-900, 900)], 120.0, 300.0
    else:
        wins, y0, y1 = [(-620, -40), (40, 620)], 150.0, 290.0
    rects = []
    for a, b in wins:
        p0 = world.project(c3, Xv + a, y1, Zw)
        p1 = world.project(c3, Xv + b, y0, Zw)
        if p0 and p1:
            rects.append((p0[0], p0[1], p1[0] - p0[0], p1[1] - p0[1]))
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    ctx.rectangle(0, 0, W, H)
    for r in rects:
        ctx.rectangle(*r)
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *darker(wall, 0.55))
    g.add_color_stop_rgb(0.3, *wall)
    g.add_color_stop_rgb(1, *darker(wall, 0.7))
    ctx.set_source(g)
    ctx.fill()
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    for (x, y, w, h) in rects:                                     # frames + a soft glass reflection
        ctx.rectangle(x, y, w, h)
        ctx.set_source_rgba(*darker(col, 0.5), 1.0)
        ctx.set_line_width(7 * S)
        ctx.stroke()
        if kind not in ("auto", "jeep"):
            rg = cairo.LinearGradient(x, y, x + w, y + h)
            rg.add_color_stop_rgba(0.0, 1, 1, 1, 0.0)
            rg.add_color_stop_rgba(0.45, 1, 1, 1, 0.10)
            rg.add_color_stop_rgba(0.55, 1, 1, 1, 0.0)
            ctx.set_source(rg)
            ctx.rectangle(x, y, w, h)
            ctx.fill()
    if lights_on:
        ctx.set_source_rgba(0.05, 0.07, 0.15, 0.35)
        ctx.paint()
    # ---- the riders on their seats, in profile, facing the way the vehicle goes
    n = len(inside)
    spacing = 230.0 if kind != "bus" else 260.0
    Zr = c3.z + 340.0
    for k, (cid, tr, stt) in enumerate(sorted(inside, key=lambda r: r[2].x * vf)):
        s2 = copy.copy(stt)
        s2.y = 0.0
        s2.facing = vf
        s2.view = None
        s2.riding = vid
        Xr = Xv + (k - (n - 1) / 2.0) * spacing

        def draw(c, t, tr=tr, s2=s2):
            c.translate(-s2.x, 0)
            sw = 26.0 * tr.cdef.scale                                   # the seat: cushion + backrest
            c.set_source_rgb(*darker(col, 0.45))
            c.rectangle(s2.x - s2.facing * 70 * tr.cdef.scale - 16, 0, 16 + 110 * tr.cdef.scale, 62 * tr.cdef.scale)
            c.fill()
            c.rectangle(s2.x - s2.facing * (70 * tr.cdef.scale + 8) - sw / 2, 0, sw, 185 * tr.cdef.scale)
            c.fill()
            infos[cid] = draw_person(tr, s2, cx=c)
        world.draw_obj(ctx, c3, Obj(Xr, Zr, draw, w=400, tag="actor"), lt)
    ctx.identity_matrix()
    # the near seat row / door panel at the bottom of the frame
    pb = world.project(c3, Xv, 60.0, c3.z + 250.0)
    if pb:
        ctx.rectangle(0, pb[1], W, H - pb[1])
        ctx.set_source_rgb(*darker(wall, 0.45))
        ctx.fill()
    ctx.identity_matrix()


def focus_path(it, fps):
    """3D mode: per-frame focus distance - the speaker if someone talks, else the camera's subject -
    smoothed like a focus puller would."""
    from .world3d import cam3_from, Z_of_z
    sc = it.scene
    out, cur = [], None
    prev = prev_rev = prev_pov = None
    a = 1 - math.exp(-1.0 / (fps * 0.25))
    for f, cam in enumerate(it.cams):
        t = f / fps
        c3 = cam3_from(cam)
        target = c3.focus
        rev = getattr(cam, "rev", None)
        zm = (lambda z: clamp(2.0 * rev - z, 0.0, 3000.0)) if rev is not None else (lambda z: z)
        foc = getattr(cam, "foc", None)
        if foc in sc.tracks:                                  # rack focus: the camera says who is sharp
            target = max(80.0, Z_of_z(zm(sc.tracks[foc].z_at(t))) - c3.z)
        elif getattr(cam, "pov", None):
            target = 900.0
        elif getattr(cam, "sub", None) in sc.tracks and sc._visible(cam.sub, t):
            target = max(80.0, Z_of_z(zm(sc.tracks[cam.sub].z_at(t))) - c3.z)   # the shot's subject stays sharp
        else:                                                 # (a reaction shot is about the listener)
            for sp in sc.speeches:
                if sp.start <= t < sp.end and sp.who in sc.tracks:
                    target = max(80.0, Z_of_z(zm(sc.tracks[sp.who].z_at(t))) - c3.z)
                    break
        jump = prev is not None and (abs(c3.z - prev.z) > 150 or abs(c3.x - prev.x) > 250 or
                                     getattr(cam, "rev", None) != prev_rev or getattr(cam, "pov", None) != prev_pov)
        cur = target if (cur is None or jump) else cur + (target - cur) * a
        prev, prev_rev, prev_pov = c3, getattr(cam, "rev", None), getattr(cam, "pov", None)
        out.append(cur)
    return out


def _draw_picture(ctx, pic, lt, W, H, S):
    """Real image moment: full-screen photo with a slow 'Ken Burns' zoom, or a framed photo over the scene."""
    from . import images
    age, dur = lt - pic["start"], pic["dur"]
    fade = clamp(min(age / 0.4, (dur - age) / 0.4), 0.0, 1.0)
    u = clamp(age / max(dur, 0.1), 0, 1)
    ctx.identity_matrix()
    if pic["style"] in ("frame", "framed", "photo", "polaroid"):
        ctx.set_source_rgba(0, 0, 0, 0.55 * fade)
        ctx.paint()
        got = images.surface(pic["name"], age, pic.get("speed", 1.0), pic.get("loop", "loop"))
        if got:
            w, h = got[1], got[2]
            sc = min(W * 0.6 / w, H * 0.66 / h) * (0.92 + 0.08 * smoothstep(age / 0.5)) * (1 + 0.04 * u)
            dw, dh = w * sc, h * sc
            b = 16 * S
            ctx.save()
            ctx.translate(W / 2, H * 0.46)
            ctx.rotate(-0.03)
            ctx.set_source_rgba(0, 0, 0, 0.35 * fade)
            ctx.rectangle(-dw / 2 - b + 10 * S, -dh / 2 - b + 14 * S, dw + 2 * b, dh + 2 * b)
            ctx.fill()
            ctx.set_source_rgba(1, 1, 1, fade)
            ctx.rectangle(-dw / 2 - b, -dh / 2 - b, dw + 2 * b, dh + 2 * b)
            ctx.fill()
            ctx.translate(-dw / 2, -dh / 2)
            ctx.scale(sc, sc)
            pat = cairo.SurfacePattern(got[0])
            pat.set_filter(cairo.FILTER_GOOD)
            ctx.set_source(pat)
            ctx.rectangle(0, 0, w, h)
            ctx.clip()
            ctx.paint_with_alpha(fade)
            ctx.restore()
    else:
        ctx.set_source_rgba(0, 0, 0, fade)
        ctx.paint()
        zoom = 1.0 + 0.12 * (u if pic.get("move", "in") != "out" else 1 - u)
        pan = (0.35 + 0.3 * u, 0.5) if pic.get("move") == "pan" else (0.5, 0.5)
        if pic.get("move") == "zoom_to" and pic.get("focus"):     # 🗺 a map flies in to one place: "focus": [fx, fy] of the picture
            got = images.surface(pic["name"], age, pic.get("speed", 1.0), pic.get("loop", "loop"))
            if got:
                k = smoothstep(clamp(age / max(dur * 0.85, 0.1), 0, 1))
                zoom = 1.0 + (float(pic.get("zoom", 4.0)) - 1.0) * k
                sc = max(W / got[1], H / got[2]) * zoom
                dw, dh = got[1] * sc, got[2] * sc
                fx = 0.5 + (float(pic["focus"][0]) - 0.5) * k
                fy = 0.5 + (float(pic["focus"][1]) - 0.5) * k
                pan = (clamp((W / 2 - fx * dw) / (W - dw), 0, 1) if dw > W else 0.5,
                       clamp((H / 2 - fy * dh) / (H - dh), 0, 1) if dh > H else 0.5)
        images.draw_cover(ctx, pic["name"], W, H, zoom, pan, fade, t=age, speed=pic.get("speed", 1.0),
                          loop=pic.get("loop", "loop"))
    cap = pic.get("caption")
    if cap:
        ctx.identity_matrix()
        ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(50 * S)
        from . import textfx
        if textfx.needs(cap):                         # Hindi / Tamil ... caption: bundled Noto fonts
            fs = 50 * S
            wd = textfx.width(cap, fs)
            if wd > W * 0.86:
                fs *= W * 0.86 / wd
                wd = textfx.width(cap, fs)
            x, y = (W - wd) / 2, H * 0.12 + fs * 0.8
            ca = fade * smoothstep((age - 0.3) / 0.4)
            ctx.set_source_rgba(0, 0, 0, 0.55 * ca)
            ctx.rectangle(x - 26 * S, y - fs * 0.8 - 22 * S, wd + 52 * S, fs * 0.8 + 44 * S + fs * 0.3)
            ctx.fill()
            textfx.show_at(ctx, cap, x, y, fs, (1, 1, 1, ca))
            return
        ext = ctx.text_extents(cap)
        if ext.width > W * 0.86:
            ctx.set_font_size(50 * S * W * 0.86 / ext.width)
            ext = ctx.text_extents(cap)
        x = (W - ext.width) / 2 - ext.x_bearing
        y = H * 0.12 + ext.height
        ca = fade * smoothstep((age - 0.3) / 0.4)
        ctx.set_source_rgba(0, 0, 0, 0.55 * ca)
        ctx.rectangle(x - 26 * S, y - ext.height - 22 * S, ext.width + 52 * S, ext.height + 44 * S)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, ca)
        ctx.move_to(x, y)
        ctx.show_text(cap)


def _with_rim(ctx, paint, stt, c, S):
    """Draw a character with a warm/cool rim of light on its edge (sunset, night and dramatic moods)."""
    if hasattr(ctx, "ops"):                             # ▶ live player: the plain character (no picture to edge)
        return paint(ctx)
    s = c.scale * (1.6 if c.kind == "quadruped" else 1.0)
    pts = [ctx.user_to_device(stt.x + dx * 230 * s, stt.y + dy * 470 * s) for dx in (-1, 1) for dy in (-0.1, 1)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    if x1 - x0 < 4 or y1 - y0 < 4 or x1 < 0 or y1 < 0 or x0 > 1e5:
        return paint(ctx)
    holder = {}

    def draw_fn(cx):
        holder["info"] = paint(cx)
    rim_light(ctx, draw_fn, (x0, y0, x1, y1), 3.0 * S, color=(1.0, 0.82, 0.55), strength=0.85)
    return holder.get("info") or {"hand": (stt.x, stt.y + 100), "head": (stt.x, stt.y + 250), "hip": (stt.x, stt.y + 100),
                                  "head_r": 30, "mouth": (stt.x, stt.y + 240)}


def draw_screen_text(ctx, tx, u, W, H, S):
    """Words on the screen: "sign" = a green highway board (top right), "time" = "2 hours later..." low in the
    middle, "label" = a small white tag, "title" = big words in the middle. u = seconds since it came up."""
    from . import textfx
    txt = str(tx.get("text", ""))
    dur = float(tx.get("dur", 3.0))
    a = clamp(min(u / 0.35, (dur - u) / 0.35), 0.0, 1.0)
    if a <= 0 or not txt:
        return
    style = tx.get("style", "title")
    ctx.save()
    ctx.identity_matrix()
    size = {"sign": 40, "time": 44, "label": 26, "title": 64}.get(style, 48) * S
    ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    line = txt
    arrow = bool(tx.get("arrow"))                        # drawn as a shape (fonts may not have the arrow sign)
    indic = textfx.needs(line)
    wd = textfx.width(line, size) if indic else ctx.text_extents(line).width

    def show(x, y, col):
        if indic:
            textfx.show_at(ctx, line, x, y, size, col)
        else:
            ctx.set_source_rgba(*col)
            ctx.move_to(x, y)
            ctx.show_text(line)
    if style == "sign":                                  # a road sign board that slides in
        pad = 22 * S
        aw = size * 1.3 if arrow else 0.0
        bw, bh = wd + 2 * pad + aw, size * 1.9
        x0 = W - bw - 40 * S + (1 - a) * (bw + 60 * S)
        y0 = 60 * S
        ctx.set_source_rgba(0.3, 0.3, 0.32, 1)
        ctx.rectangle(x0 + bw * 0.25 - 4 * S, y0 + bh, 8 * S, 90 * S)
        ctx.rectangle(x0 + bw * 0.75 - 4 * S, y0 + bh, 8 * S, 90 * S)
        ctx.fill()
        ctx.set_source_rgba(0.05, 0.42, 0.22, 1)
        ctx.rectangle(x0, y0, bw, bh)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.set_line_width(4 * S)
        ctx.rectangle(x0 + 7 * S, y0 + 7 * S, bw - 14 * S, bh - 14 * S)
        ctx.stroke()
        show(x0 + pad, y0 + bh * 0.66, (1, 1, 1, 1))
        if arrow:
            ax, ay = x0 + pad + wd + size * 0.3, y0 + bh * 0.5
            ctx.set_source_rgba(1, 1, 1, 1)
            ctx.move_to(ax, ay - size * 0.12)
            ctx.line_to(ax + size * 0.55, ay - size * 0.12)
            ctx.line_to(ax + size * 0.55, ay - size * 0.38)
            ctx.line_to(ax + size * 1.0, ay)
            ctx.line_to(ax + size * 0.55, ay + size * 0.38)
            ctx.line_to(ax + size * 0.55, ay + size * 0.12)
            ctx.line_to(ax, ay + size * 0.12)
            ctx.close_path()
            ctx.fill()
    elif style == "time":                                # "2 घंटे बाद ..." on a dark band
        y = H * 0.78
        ctx.set_source_rgba(0, 0, 0, 0.5 * a)
        ctx.rectangle((W - wd) / 2 - 30 * S, y - size * 1.1, wd + 60 * S, size * 1.55)
        ctx.fill()
        show((W - wd) / 2, y, (1, 0.95, 0.8, a))
    elif style == "label":
        x, y = float(tx.get("x", 40)) * S, float(tx.get("y", 60)) * S
        ctx.set_source_rgba(1, 1, 1, 0.85 * a)
        ctx.rectangle(x - 10 * S, y - size, wd + 20 * S, size * 1.45)
        ctx.fill()
        show(x, y, (0.1, 0.1, 0.12, a))
    else:
        y = H * 0.45
        ctx.set_source_rgba(0, 0, 0, 0.35 * a)
        ctx.rectangle((W - wd) / 2 - 30 * S, y - size * 1.05, wd + 60 * S, size * 1.5)
        ctx.fill()
        show((W - wd) / 2, y, (1, 1, 1, a))
    ctx.restore()


def _hook_overlay(ctx, P, it, lt):
    """Cinematic bars + a question caption on the flash-forward, then a white flash into the title."""
    W, H, S = P.W, P.H, P.S
    ctx.identity_matrix()
    bar = 70 * S * min(1.0, lt / 0.3)
    ctx.set_source_rgb(0, 0, 0)
    ctx.rectangle(0, 0, W, bar)
    ctx.rectangle(0, H - bar, W, bar)
    ctx.fill()
    cap = getattr(it, "caption", "")
    if cap:
        a = min(1.0, lt / 0.4) * min(1.0, (it.duration - lt) / 0.4)
        ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(52 * S)
        from . import textfx
        indic = textfx.needs(cap)
        wd = textfx.width(cap, 52 * S) if indic else ctx.text_extents(cap).width
        x = (W - wd) / 2 - (0 if indic else ctx.text_extents(cap).x_bearing)
        y = bar + 80 * S
        ctx.set_source_rgba(0, 0, 0, 0.55 * a)
        ctx.rectangle(x - 24 * S, y - 58 * S, wd + 48 * S, 80 * S)
        ctx.fill()
        if indic:
            textfx.show_at(ctx, cap, x, y, 52 * S, (1, 0.87, 0.2, a))
        else:
            ctx.set_source_rgba(1, 0.87, 0.2, a)
            ctx.move_to(x, y)
            ctx.show_text(cap)
    ctx.set_source_rgba(1, 1, 1, 0.9)
    ctx.set_font_size(24 * S)
    ctx.move_to(W - 150 * S, H - bar / 2 + 8 * S)
    if int(lt * 2) % 2 == 0:
        ctx.show_text("● LATER")
    flash = max(0.0, 1 - (it.duration - lt) / 0.35)
    if flash > 0:
        ctx.set_source_rgba(1, 1, 1, flash * 0.9)
        ctx.paint()


_VD = {}


def _ground_back(pr):
    """For a ground-like walkable 3D thing (a hill, a stage, a floor, steps): how far its back edge is behind
    its middle (world units) - it is sorted by that edge, so a temple on a hill or people on a stage are drawn
    after it. None for everything else."""
    try:
        from . import objects, images
        if not objects.is_object(pr) or float(pr.spec.get("y") or 0.0) > 64.0:
            return None
        img = objects._image_name(pr)
        meta = (images.info(img) or {}) if img else {}
        fp = meta.get("foot")
        if not meta.get("walk") or not fp:
            return None
        if float(meta.get("height") or 0.0) > 0.6 * max(fp[1] - fp[0], fp[3] - fp[2]):
            return None                                 # tall (a throne with steps, a temple): not ground-like
        h_draw = objects.size(pr)[1]
        sc = h_draw / max(1.0, float(meta.get("height") or h_draw))
        return max(0.0, float(fp[3]) * sc)
    except Exception:
        return None


def _vdraw(p):
    key = id(p)
    if key not in _VD:
        _VD[key] = VehicleDraw(p.vtype, p.spec)
    return _VD[key]


def _draw_card(ctx, P, it, lt):
    W, H, S = P.W, P.H, P.S
    ctx.identity_matrix()
    title = it.kind == "title"
    top, bot = ("#1d3557", "#457b9d") if title else ("#22223b", "#4a4e69")
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *hex_to_rgb(top))
    g.add_color_stop_rgb(1, *hex_to_rgb(bot))
    ctx.set_source(g)
    ctx.paint()
    # floating circles for a bit of life
    for k in range(14):
        x = (k * 173.3 + lt * 22 * (1 + k % 3)) % (W + 200) - 100
        y = H * (0.1 + 0.8 * ((k * 0.377) % 1))
        ctx.set_source_rgba(1, 1, 1, 0.05)
        ctx.arc(x, y, (30 + (k * 37) % 70) * S, 0, TAU)
        ctx.fill()
    text = P.title if title else it.spec.get("text", "The End")
    sub = P.settings.get("subtitle", "") if title else it.spec.get("sub", "")
    pop = smoothstep(lt / 0.6)
    size = (104 if len(text) < 22 else 76) * S * (0.85 + 0.15 * pop)
    ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    from . import textfx
    y = H * 0.36
    if textfx.needs(text):
        wd = textfx.width(text, size)
        if wd > W * 0.9:
            size *= W * 0.9 / wd
            wd = textfx.width(text, size)
        x = (W - wd) / 2
        textfx.show_at(ctx, text, x + 5 * S, y + 5 * S, size, (0, 0, 0, 0.3))
        textfx.show_at(ctx, text, x, y, size, (1, 1, 1, 1))
    else:
        ext = ctx.text_extents(text)
        if ext.width > W * 0.9:
            ctx.set_font_size(size * W * 0.9 / ext.width)
            ext = ctx.text_extents(text)
        x = (W - ext.width) / 2 - ext.x_bearing
        ctx.set_source_rgba(0, 0, 0, 0.3)
        ctx.move_to(x + 5 * S, y + 5 * S)
        ctx.show_text(text)
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(x, y)
        ctx.show_text(text)
    if sub:
        ctx.set_font_size(40 * S)
        if textfx.needs(sub):
            textfx.show_at(ctx, sub, (W - textfx.width(sub, 40 * S)) / 2, y + 80 * S, 40 * S, (1, 1, 1, 0.8 * pop))
        else:
            e2 = ctx.text_extents(sub)
            ctx.set_source_rgba(1, 1, 1, 0.8 * pop)
            ctx.move_to((W - e2.width) / 2 - e2.x_bearing, y + 80 * S)
            ctx.show_text(sub)
    credits = [] if title else (it.spec.get("credits") or [])
    if credits:                                          # imported 3D models: who made them
        line = "3D models: " + " · ".join(credits)
        ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        fs = 24 * S
        ctx.set_font_size(fs)
        e3 = ctx.text_extents(line)
        if e3.width > W * 0.92:
            fs *= W * 0.92 / e3.width
            ctx.set_font_size(fs)
            e3 = ctx.text_extents(line)
        ctx.set_source_rgba(1, 1, 1, 0.75 * pop)
        ctx.move_to((W - e3.width) / 2 - e3.x_bearing, H - 30 * S)
        ctx.show_text(line)
    # the cast waving on a little ground strip
    chars = list(P.characters.values())
    if chars:
        cam = Camera(960, 345, 1.0)
        set_layer(ctx, cam, 1.0, W, H, S)
        ctx.set_source_rgba(1, 1, 1, 0.15)
        ctx.rectangle(-500, -8, 3000, 8)
        ctx.fill()
        n = len(chars)
        span = min(1500, 260 * n)
        w3 = str((getattr(P, "settings", None) or {}).get("world", "3d") or "3d").lower() not in ("2d", "flat", "2.5d", "classic", "side")
        for k, c in enumerate(chars):
            cx = 960 - span / 2 + span * (k + 0.5) / n
            tt = lt + k * 0.37
            table = actions_for(c) or ACTIONS
            name = "wave" if c.kind == "human" else ("happy" if c.kind == "quadruped" else "sing")
            if not ((k + int(lt)) % 2 == 0 or not title):
                name = "idle"
            actx = {"params": {}, "speed": 0, "dist": 0}
            actx.update(animal_ctx(c) if c.kind != "human" else {})
            pose, _ = table[name].fn(tt, 3, actx)
            if w3 and _cast3d(ctx, c, pose, cx, tt, W, H, S):        # a 3D story: the cast as real 3D figures too
                continue
            draw_character(ctx, c, pose, cx, 1 if cx < 960 else -1, "happy", 0.0, tt, {},
                           1.0, (tt % 3.1) < 0.12)


def _cast3d(ctx, c, pose, cx, tt, W, H, S):
    """one member of the cast as a 3D figure on the title card (the same model as in the film), all at one scale"""
    try:
        from . import code3d
        pen = code3d.Pen3()
        pen.push()
        pen.turn(math.degrees(math.pi) - 90.0 + (25 if cx < 960 else -25))   # turned a little toward the middle
        char3d.build(pen, c, pose, "happy", 0.0, (tt % 3.1) < 0.12, tt, 0.8, False)
        pen.pop()
        faces = pen.faces
        if not faces:
            return False
        ex = code3d.extent(faces) or (-100, 100, 0, 300, -100, 100)
        size = max(ex[1] - ex[0], ex[3] - ex[2], ex[5] - ex[4], 320.0)
        mx = ctx.get_matrix()
        k = abs(mx.xx)                                        # pixels per story unit on the strip
        tw, th = max(8, int(900 * k)), max(8, int(620 * k))
        f_ = min(tw, th) * 1.35
        D = f_ / k                                            # the camera distance that gives exactly that scale
        surf = code3d.preview_view(faces, tw, th, angle=0.0, elev=6.0, bg=False, person=False, zoom=size * 2.2 / D, shadow=False)
        px, py = mx.transform_point(cx, 0.0)                  # the foot of the figure on the strip, in pixels
        ex_c = (ex[2] + ex[3]) / 2                            # (the view centres the figure's middle at 52 % down)
        ctx.save()
        ctx.identity_matrix()
        ctx.set_source_surface(surf, px - tw / 2, py - th * 0.52 - ex_c * k)
        ctx.paint()
        ctx.restore()
        return True
    except Exception:                                         # noqa: BLE001
        return False


# ---------------------------------------------------------------------- encoding
def find_ffmpeg():
    exe = None
    try:                                     # the bundled FFmpeg first: it is modern everywhere (old Linux
        import imageio_ffmpeg                # systems like CentOS 7 ship an FFmpeg too old for this app)
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    if not exe:
        exe = shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("FFmpeg not found. Install it (https://ffmpeg.org) or `pip install imageio-ffmpeg`.")
    return exe


def _parts_key(P, crf, preset):
    """Fingerprint of what the parts show: a changed story / size / quality starts the parts again."""
    import hashlib
    h = hashlib.sha1(f"{P.n_frames}|{P.W}x{P.H}|{P.fps}|{crf}|{preset}".encode())
    try:
        with open(getattr(P, "story_path", "") or "", "rb") as f:
            h.update(f.read())
    except OSError:
        pass
    return h.hexdigest()[:16]


def held(P):
    """how many frames each drawing is shown for: the sketch look is animated "on twos" like hand-drawn cartoons
    (12 drawings a second at 24 fps - half the drawing work); "settings": {"twos": false} draws every frame"""
    if getattr(P, "art", "") in ("sketch", "stick3d") and P.settings.get("twos", True) is not False:
        return 2
    return 1


def _render_part(P, a, b, path, workers, crf, preset, ff, report):
    """Frames a..b-1 -> one video-only MP4. Fresh worker processes for every part (their caches die with
    them) and only a few frames in memory at a time - a long episode never fills the RAM."""
    light = LOW_RAM[0]
    cmd = [ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "yuv420p" if _yuv_ok(P) else "bgra",
           "-s", f"{P.W}x{P.H}",
           "-r", str(P.fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", preset, "-crf", str(crf)]
    if getattr(P, "art", "") in ("sketch", "stick3d"):
        cmd += ["-tune", "animation"]                    # (flat paper + ink lines: x264's cartoon setting)
    if light:                                            # FFmpeg keeps fewer frames to look ahead
        cmd += ["-rc-lookahead", "10", "-threads", "2"]
    cmd += ["-pix_fmt", "yuv420p", "-r", str(P.fps), path + ".tmp.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    from . import sysmon
    try:
        h = held(P)
        if workers <= 1:
            for i in range(a, b):
                if (i - a) % h == 0:
                    frame = encoder_frame(i, P)
                proc.stdin.write(frame)
                report(i + 1)
                if (i - a) % 60 == 59:
                    _ram_pause(log=None)
                    if ram_high():
                        free_caches()
        else:
            _render_pool(P, a, b, workers, proc, report)
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise SystemExit("FFmpeg failed while encoding a part (see error above).")
    os.replace(path + ".tmp.mp4", path)                  # only a finished part counts (resume after a crash)


def ram_limits():
    """(high, danger) RAM % : over high = fewer workers, over danger = pause"""
    from . import sysmon
    lim = sysmon.get_limit()
    high = max(50.0, min(85.0, lim))
    return high, max(high + 4.0, 93.0)


def ram_high():
    from . import sysmon
    p = sysmon.ram_percent()
    return p is not None and p > ram_limits()[0]


def _ram_pause(log=print, max_wait=40.0):
    """The last safety net: RAM nearly full -> wait (the workers have finished their frames; FFmpeg and the
    system catch up) instead of the computer freezing. -> True if it had to wait"""
    from . import sysmon
    high, danger = ram_limits()
    p = sysmon.ram_percent()
    if p is None or p < danger:
        return False
    if log:
        log(f"\n  RAM {p:.0f} % - pausing a moment so the computer does not freeze")
    free_caches()
    t0 = time.time()
    while time.time() - t0 < max_wait:
        time.sleep(1.0)
        p = sysmon.ram_percent()
        if p is None or p < high:
            break
    return True


def _is3d(P):
    return any(getattr(getattr(it, "scene", None), "mode3d", False) for it in getattr(P, "items", []))


def ram_per_worker_gb(P):
    """RAM one worker needed last time for this size of video (measured), or a careful first guess"""
    v = estimate(f"ram_worker:{P.W}x{P.H}:{'3d' if _is3d(P) else '2d'}")
    if v:
        return float(v)
    px = P.W * P.H / (1920 * 1080)
    return 0.45 + 0.35 * px + (0.35 if _is3d(P) else 0.0)


def workers_for_ram(P, workers):
    """No more workers than the free RAM can hold (keeps 0.8 GB for the system, FFmpeg and the app)."""
    from . import sysmon
    av = sysmon.ram_available_gb()
    if av is None:
        return workers
    per = ram_per_worker_gb(P) * 1.15
    fit = int((av - 0.8 - (0.25 if LOW_RAM[0] else 0.6)) / per)
    return max(1, min(workers, fit))


def _render_pool(P, a, b, workers, proc, report):
    """Frames a..b-1 on a pool of workers, watching the RAM between small batches:
    over the limit -> fewer workers (a new, smaller pool), nearly full -> pause; well under -> back up again.
    Each worker gets a RAM share and empties its caches when it goes over it, and is replaced after 400 frames
    (memory that Python keeps is given back)."""
    from . import sysmon
    method = "fork" if "fork" in mp.get_all_start_methods() else "spawn"
    ctxm = mp.get_context(method)
    want = workers
    high, _danger = ram_limits()
    peak = [0.0]

    def cap_for(w):
        av = sysmon.ram_available_gb()
        if av is None:
            return None
        per = max(0.35, (av + (sysmon.rss_gb(children=True) or 0.0)) * 0.8 / max(1, w + 1))
        return per * (0.6 if LOW_RAM[0] else 1.0)

    s0 = a
    while s0 < b:
        w = workers
        good = 0
        with ctxm.Pool(w, initializer=_init_worker, initargs=(P, cap_for(w)), maxtasksperchild=400) as pool:
            while s0 < b:
                h = held(P)
                batch = w * 3 * h                        # frames waiting in memory: a handful, never thousands
                end = min(b, s0 + batch)
                keys = range(s0, end, h)                 # (on twos: each drawing is shown for h frames)
                for i, frame in zip(keys, pool.imap(encoder_frame, keys)):
                    for _ in range(min(h, end - i)):
                        proc.stdin.write(frame)
                    report(min(end, i + h))
                s0 = end
                kids = [r for n_, r in sysmon.child_rss_gb() if "ffmpeg" not in n_.lower()]
                if kids:
                    peak[0] = max(peak[0], max(kids))
                p = sysmon.ram_percent()
                if p is None:
                    continue
                if _ram_pause(log=print):
                    workers = 1
                    break
                if p > high and w > 1:
                    workers = max(1, w // 2)
                    print(f"\n  RAM {p:.0f} % - now {workers} worker process(es)", flush=True)
                    break
                good = good + 1 if p < high - 25 else 0
                if good >= 15 and w < want:              # lots of room again: one more worker
                    workers = w + 1
                    break
    if peak[0] > 0.05:
        record(f"ram_worker:{P.W}x{P.H}:{'3d' if _is3d(P) else '2d'}", peak[0])


def cut_audio(path, t0, t1):
    """The sound between t0 and t1 seconds as a new WAV next to it (a time-window part)."""
    ff = find_ffmpeg()
    out = os.path.splitext(path)[0] + f".{t0:.2f}-{t1:.2f}.wav"
    r = subprocess.run([ff, "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{max(0.05, t1 - t0):.3f}", "-i", path, out])
    if r.returncode != 0:
        raise SystemExit("FFmpeg could not cut the sound for this part.")
    return out


def cut_srt(path, t0, t1):
    """Keep only the subtitles between t0 and t1, moved so t0 is 0:00 (rewritten in place)."""
    import re as _re
    try:
        txt = open(path, encoding="utf-8").read()
    except OSError:
        return

    def sec(ts):
        h, m, rest = ts.split(":")
        s_, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s_) + int(ms) / 1000.0

    def ts(v):
        v = max(0.0, v)
        return f"{int(v // 3600):02d}:{int(v % 3600 // 60):02d}:{int(v % 60):02d},{int(round(v % 1 * 1000)) % 1000:03d}"
    out, n = [], 0
    for block in _re.split(r"\n\s*\n", txt.strip()):
        lines = block.splitlines()
        if len(lines) < 2 or "-->" not in lines[1]:
            continue
        a, b = [sec(x.strip()) for x in lines[1].split("-->")]
        if b <= t0 or a >= t1:
            continue
        n += 1
        out.append(f"{n}\n{ts(max(a, t0) - t0)} --> {ts(min(b, t1) - t0)}\n" + "\n".join(lines[2:]))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(out) + ("\n\n" if out else ""))


def encode(P, audio_path, srt_path, out_path, workers=None, crf=18, preset="medium", log=print, part_sec=60,
           window=None, low_ram=False):
    """Render the video in parts of part_sec seconds (0 = one piece), each saved to <out>.parts/ as soon as
    it is done; run the same command again after a crash / stop and the finished parts are kept. At the end
    the parts are joined (no re-encoding) with the sound and subtitles."""
    ff = find_ffmpeg()
    n = P.n_frames
    if getattr(P, "art", "") in ("sketch", "stick3d") and preset in ("medium", "slow", "slower", "veryslow"):
        preset = "veryfast"                              # ✏ line art on paper packs small even with the fast x264
    explicit = workers is not None                       # --workers N: exactly that; else it follows the limit
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    if not explicit:
        from . import sysmon
        workers = sysmon.workers_for_limit(workers)
    LOW_RAM[0] = bool(low_ram)
    from . import code3d as _c3
    _c3.PACK_BUDGET[0] = 90e6 if low_ram else 220e6
    if low_ram:                                          # one click for a 4-8 GB laptop
        workers = min(workers, 2)
        part_sec = min(part_sec or 20, 20)
        if preset in ("medium", "slow", "slower", "veryslow"):
            preset = "faster"
    if not explicit:
        w_ram = workers_for_ram(P, workers)
        from . import sysmon
        av = sysmon.ram_available_gb()
        log(f"  RAM: {av:.1f} GB free, about {ram_per_worker_gb(P):.2f} GB per worker"
            + (f" - {w_ram} worker(s) instead of {workers} so the RAM does not fill up" if w_ram < workers else "")
            if av is not None else "  RAM: unknown")
        workers = w_ram
    fps_est = estimate_render_fps(P, workers, preset)
    f0, f1 = 0, n
    if window:                                           # only this time window of the video (a time part)
        f0 = max(0, min(n - 1, int(round(window[0] * P.fps))))
        f1 = max(f0 + 1, min(n, int(round(window[1] * P.fps))))
    per = int(part_sec * P.fps) if part_sec and part_sec > 0 else (f1 - f0)
    per = max(per, P.fps * 5)
    ranges = [(a, min(f1, a + per)) for a in range(f0, f1, per)]
    n = f1 - f0
    log(f"  {n} frames on {workers} worker process(es) in {len(ranges)} part(s) - estimated render time "
        f"~{fmt(n / fps_est)}")
    pdir = os.path.splitext(out_path)[0] + ".parts"
    key = _parts_key(P, crf, preset) + f"|{per}|{f0}-{f1}"  # a new piece length / window starts again (never mixes)
    kfile = os.path.join(pdir, "key.txt")
    try:
        with open(kfile) as f:
            old = f.read().strip()
    except OSError:
        old = None
    if old != key and os.path.isdir(pdir):
        shutil.rmtree(pdir, ignore_errors=True)          # the story changed: old parts are not this video
    os.makedirs(pdir, exist_ok=True)
    with open(kfile, "w") as f:
        f.write(key)
    t0 = time.time()
    done0 = [0]

    def report(i):
        i -= f0                                           # count from the start of the window (a time part)
        if i % max(1, P.fps) == 0 or i == n:
            el = time.time() - t0
            got = max(i - done0[0], 1)
            eta = el / got * (n - i)
            sys.stdout.write(f"\r  rendering frame {i}/{n}  ({got / max(el, 1e-6):.1f} fps, ~{eta:.0f}s left)   ")
            sys.stdout.flush()

    parts = []
    for k, (a, b) in enumerate(ranges):
        path = os.path.join(pdir, f"part_{k + 1:03d}.mp4")
        parts.append(path)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            log(f"\n  part {k + 1}/{len(ranges)} already done - kept")
            done0[0] += b - a
            continue
        if not explicit:                                  # "Maximum system usage" can change while it runs
            from . import sysmon
            w_now = sysmon.workers_for_limit(max(1, (os.cpu_count() or 2) - 1))
            w_now = workers_for_ram(P, min(w_now, 2) if low_ram else w_now)
            if w_now != workers:
                log(f"\n  resource limit: now {w_now} worker process(es)")
                workers = w_now
        print(f"\n  part {k + 1}/{len(ranges)}", flush=True)
        _render_part(P, a, b, path, workers, crf, preset, ff, report)
    sys.stdout.write("\n")
    lst = os.path.join(pdir, "parts.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p_ in parts:
            f.write("file '" + os.path.abspath(p_).replace("\\", "/").replace("'", "'\\''") + "'\n")
    cmd = [ff, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", audio_path]
    maps = ["-map", "0:v", "-map", "1:a"]
    if srt_path and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
        cmd += ["-i", srt_path]
        maps += ["-map", "2:s", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
    cmd += maps + ["-c:v", "copy", "-c:a", "aac", "-strict", "-2", "-b:a", "192k", "-movflags", "+faststart",
                   out_path]
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit(f"FFmpeg could not join the parts (they are kept in {pdir}).")
    shutil.rmtree(pdir, ignore_errors=True)
    el = time.time() - t0
    made = n - done0[0]
    if made > 60:
        record(_fps_key(P, workers, preset), made / el)
        if getattr(P, "_bench_fps", None):
            record(_fps_key(P, workers, preset).replace("render_fps", "render_ratio"), (made / el) / P._bench_fps)
        log(f"  rendered {made} frames in {fmt(el)} ({made / el:.1f} fps; estimate was ~{fmt(made / fps_est)})")
    return out_path


def _fps_key(P, workers, preset="medium"):
    return f"render_fps:{P.W}x{P.H}:w{workers}:{preset}"


def _bench_fps(P, workers):
    idx = [int(P.n_frames * f) for f in (0.15, 0.4, 0.65, 0.9)]
    t0 = time.time()
    for i in idx:
        render_frame(i, P)
    per = (time.time() - t0) / len(idx)
    enc = 0.012 * (P.W * P.H) / (1920 * 1080)          # rough x264 cost per frame
    return 1.0 / (per / (min(workers, os.cpu_count() or 1) * 0.85) + enc)


def estimate_render_fps(P, workers, preset="medium"):
    """Benchmark 4 frames of THIS video, corrected by how past estimates compared to reality."""
    bench = _bench_fps(P, workers)
    P._bench_fps = bench
    ratio = estimate(_fps_key(P, workers, preset).replace("render_fps", "render_ratio"))
    return bench * (ratio or 1.0)


def _has_cues(srt):
    """A subtitle file with at least one line (a title / end card or a scene without words has none - FFmpeg
    cannot open an empty .srt)."""
    try:
        return os.path.getsize(srt) > 0 and "-->" in open(srt, encoding="utf-8", errors="replace").read(4096)
    except OSError:
        return False


def mux_languages(video, primary, extras, log=print, extra_files=True):
    """video: MP4 already encoded with the primary audio (+ primary subtitles).
    extras: [(lang, wav, srt)].  Produces:
      <video>                  every audio language as a selectable track + every subtitle language
      <name>.<lang>.mp4        one video per extra language (that language is the default audio)
      <name>.<lang>.m4a        audio only - upload to YouTube Studio > Languages > Add audio track
    """
    from .tts import ISO3, LANG_NAMES
    ff = find_ffmpeg()
    base = os.path.splitext(video)[0]
    iso = lambda l: ISO3.get(l.split("-")[0].lower(), "und")
    tmp = base + ".tmp_multi.mp4"
    cmd = [ff, "-y", "-v", "error", "-i", video]
    for lang, wav, srt in extras:
        cmd += ["-i", wav]
    subs = [(l, s) for l, s in [(primary[0], primary[1])] + [(l, s) for l, _, s in extras] if _has_cues(s)]
    for lang, srt in subs:
        cmd += ["-i", srt]
    n_in = 1 + len(extras)
    cmd += ["-map", "0:v", "-map", "0:a"]
    for k in range(len(extras)):
        cmd += ["-map", f"{k + 1}:a"]
    for k in range(len(subs)):
        cmd += ["-map", f"{n_in + k}:s"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-strict", "-2", "-b:a", "192k", "-c:s", "mov_text"]
    langs = [primary[0]] + [l for l, _, _ in extras]
    for k, l in enumerate(langs):
        cmd += [f"-metadata:s:a:{k}", f"language={iso(l)}", f"-metadata:s:a:{k}", f"title={LANG_NAMES.get(l, l)}"]
        cmd += [f"-disposition:a:{k}", "default" if k == 0 else "0"]
    for k, (l, _) in enumerate(subs):
        cmd += [f"-metadata:s:s:{k}", f"language={iso(l)}", f"-metadata:s:s:{k}", f"title={LANG_NAMES.get(l, l)}"]
    cmd += ["-movflags", "+faststart", tmp]
    subprocess.run(cmd, check=True)
    os.replace(tmp, video)
    outs = [video]
    for lang, wav, srt in (extras if extra_files else []):
        code = lang.split("-")[0].lower()
        mp4 = f"{base}.{code}.mp4"
        sub_in, sub_map = (["-i", srt], ["-map", "2:s", "-c:s", "mov_text", "-metadata:s:s:0", f"language={iso(lang)}"]) \
            if _has_cues(srt) else ([], [])
        subprocess.run([ff, "-y", "-v", "error", "-i", video, "-i", wav] + sub_in + ["-map", "0:v", "-map", "1:a"] + sub_map +
                       ["-c:v", "copy", "-c:a", "aac", "-strict", "-2", "-b:a", "192k",
                        "-metadata:s:a:0", f"language={iso(lang)}", "-movflags", "+faststart", mp4], check=True)
        m4a = f"{base}.{code}.m4a"
        subprocess.run([ff, "-y", "-v", "error", "-i", wav, "-c:a", "aac", "-strict", "-2", "-b:a", "192k", m4a], check=True)
        outs += [mp4, m4a]
        log(f"  {LANG_NAMES.get(lang, lang)}: {os.path.basename(mp4)} (video) + {os.path.basename(m4a)} (audio track for YouTube)")
    return outs
