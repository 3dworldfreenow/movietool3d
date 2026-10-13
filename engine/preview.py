"""Fast animated previews for the Studio (characters, animals, places) as animated WebP."""
import io
import math

import cairo
from PIL import Image

from .background import Background, Camera
from .character import CharacterDef, draw_character
from .poses import ACTIONS, resolve_action
from . import animals

PW, PH = 560, 340


def _to_pil(surf):
    w, h = surf.get_width(), surf.get_height()
    img = Image.frombuffer("RGBA", (w, h), bytes(surf.get_data()), "raw", "BGRA", 0, 1)
    return img.convert("RGB")


def _encode(frames, fps):
    buf = io.BytesIO()
    frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:], duration=int(1000 / fps),
                   loop=0, quality=80, method=3)
    return buf.getvalue()


def _backdrop(ctx):
    g = cairo.LinearGradient(0, 0, 0, PH)
    g.add_color_stop_rgb(0, 0.86, 0.93, 0.98)
    g.add_color_stop_rgb(0.78, 0.97, 0.97, 0.94)
    g.add_color_stop_rgb(0.78, 0.84, 0.9, 0.78)
    g.add_color_stop_rgb(1, 0.78, 0.86, 0.72)
    ctx.set_source(g)
    ctx.paint()


def character_frames(spec, action="walk", seconds=2.0, fps=12, cid="preview"):
    c = CharacterDef(cid, spec or {}, 0)
    table = animals.actions_for(c) or ACTIONS
    if c.kind == "human":
        name, _ = resolve_action(action)
    else:
        name, _ = animals.resolve_animal_action(c, action)
    act = table.get(name) or table["idle"]
    base_ctx = {"params": {}, "speed": 0.0, "dist": 0.0}
    base_ctx.update(animals.animal_ctx(c) if c.kind != "human" else {})
    if c.kind == "bird" and name in ("fly", "hover"):
        base_ctx["params"] = {"height": 90}
    frames = []
    n = int(seconds * fps)
    # fit the character in frame
    if c.kind == "quadruped":
        a = c.animal
        na = math.radians(a.get("neck_angle", 32))
        length = (a["body"] + a["girth"] + a["neck"] * math.cos(na) + a["head"] * 2.5 + 60) * c.scale
        height = (a["thigh"] + a["shin"] + a["girth"] + a["neck"] * math.sin(na) + a["head"] * 2.2) * c.scale
        k = min(1.1, 470.0 / length, 250.0 / height)
    elif c.kind == "bird":
        k = 1.6
    else:
        k = min(1.05, 270.0 / (330 * c.scale))
    dur = act.dur or 2.0
    for i in range(n):
        t = i / fps
        lt = t % dur if (act.oneshot or name in ("jump", "pick", "drop", "give", "bow", "kick")) else t
        pose, ex = act.fn(lt, dur, dict(base_ctx))
        talking = name == "talk"
        mouth = abs(math.sin(t * 9)) * 0.8 if talking else 0.0
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, PW, PH)
        ctx = cairo.Context(surf)
        _backdrop(ctx)
        ctx.translate(PW / 2, PH * 0.84)
        ctx.scale(k, -k)
        face = ex.get("face", "happy" if name in ("wave", "celebrate", "dance") else "neutral")
        blink = (t % 3.1) < 0.12
        draw_character(ctx, c, pose, 0, 1, face, mouth, t, ex, ex.get("alpha", 1.0), blink,
                       bool(ex.get("seat")))
        frames.append(_to_pil(surf))
    return frames


def character_preview(spec, action="walk", seconds=2.0, fps=12):
    return _encode(character_frames(spec, action, seconds, fps), fps)


def place_preview(bg_spec, seconds=3.0, fps=10, world_w=2400):
    bg = Background(bg_spec or {"preset": "park"}, world_w, seed=int((bg_spec or {}).get("seed", 1)))
    frames = []
    n = int(seconds * fps)
    W, H = PW, PH
    S = H / 1080
    for i in range(n):
        t = i / fps
        u = i / max(n - 1, 1)
        cam = Camera(world_w * (0.3 + 0.4 * u), 345, 1.0)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        ctx = cairo.Context(surf)
        bg.draw_back(ctx, cam, t + 2, W, H, S)
        bg.draw_front(ctx, cam, t + 2, W, H, S)
        bg.draw_weather(ctx, t + 2, W, H)
        bg.tint(ctx, W, H)
        frames.append(_to_pil(surf))
    return _encode(frames, fps)


def still_png(frames):
    buf = io.BytesIO()
    frames[len(frames) // 3].save(buf, format="PNG")
    return buf.getvalue()


def image_use_preview(name, use="object", height=None, ground=None, style="full"):
    """One PNG showing how a real image looks in a story: as an object next to a person (for size),
    as the whole background, as a prop in a character's hand, or as a full-screen picture moment."""
    from .background import set_layer
    from .props import draw_prop
    from . import images
    W, H = PW * 2, PH * 2
    S = H / 1080
    world_w = 2400
    ravi = CharacterDef("preview_kid", {"age": "child", "outfit": "tshirt", "hat": "cap", "accent": "#e63946",
                                         "skin": "wheat"}, 0)
    meta = images.info(name) or {}
    if use == "backdrop":
        bg = Background({"image": name, "ground": ground or meta.get("ground") or 0.86}, world_w, seed=1)
    else:
        spec = {"preset": "village", "seed": 3}
        if use == "object":
            spec["elements"] = [{"type": "image", "name": name, "x": 1320, "height": height or meta.get("height") or 300,
                                 "layer": "mid", "p": 1.0}]
        bg = Background(spec, world_w, seed=3)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    cam = Camera(1200, 345, 1.1)
    bg.draw_back(ctx, cam, 2.0, W, H, S)
    set_layer(ctx, cam, 1.0, W, H, S)
    pose, _ = ACTIONS["idle"].fn(0.5, 1, {"params": {}})
    if use == "prop":
        pose = dict(pose, an_u=48, an_l=28)
    info = draw_character(ctx, ravi, pose, 1000, 1, "happy", 0.0, 0.5, {}, 1.0, False, False)
    if use == "prop":
        hx, hy = info["hand"]
        draw_prop(ctx, name, hx, hy, 0.5, {"height": height or meta.get("height") or 70}, held_hand=(hx, hy))
    bg.draw_front(ctx, cam, 2.0, W, H, S)
    if use == "picture":
        from .render import _draw_picture
        _draw_picture(ctx, {"start": 0.0, "name": name, "dur": 4.0, "caption": "Your caption here",
                            "style": style, "move": "in"}, 2.0, W, H, S)
    buf = io.BytesIO()
    _to_pil(surf).save(buf, format="PNG")
    return buf.getvalue()


def place_json_preview(spec, mode="3d", frames_n=10, still=False):
    """A place JSON rendered by the real engine (with its real objects, a child for size and a slow pan):
    animated WebP (or one PNG with still=True)."""
    import json as _json
    import os as _os
    import tempfile
    from .project import Project
    from . import render as R
    from PIL import Image as _Image
    here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    cache = _os.path.join(here, "cache", "placeprev")
    _os.makedirs(cache, exist_ok=True)
    story = {"title": "place preview",
             "settings": {"language": "en-IN", "music": "none", "title_card": False, "end_text": "", "hook": "off",
                          "director": "off", "handheld": 0, **({"camera_mode": "3d"} if mode == "3d" else {})},
             "characters": {"size_kid": {"name": "Kid", "age": "child", "gender": "male"}},
             "scenes": [{"id": "p", "background": spec,
                         "characters": [{"id": "size_kid", "x": 1200, "z": 120, "facing": "camera"}],
                         "events": [{"camera": "wide", "cut": True},
                                    {"camera": "slow_pan", "direction": "right", "distance": 500, "duration": 3.5},
                                    {"wait": 3.6}]}]}
    fd, path = tempfile.mkstemp(suffix=".json", dir=cache)
    with _os.fdopen(fd, "w", encoding="utf-8") as fh:
        _json.dump(story, fh)
    try:
        P = Project(path, {"tts": "silent", "cache": _os.path.join(here, "cache", "validate"),
                           "resolution": f"{PW}x{PH}"}, log=lambda *a: None)
        frames = []
        n = 1 if still else frames_n
        for i in range(n):
            t = 0.2 + (3.6 * i / max(n - 1, 1) if n > 1 else 1.8)
            R.render_frame(int(t * P.fps), P)
            s = R._SURF
            frames.append(_Image.frombuffer("RGBA", (s.get_width(), s.get_height()), bytes(s.get_data()), "raw",
                                            "BGRA", s.get_stride()).convert("RGB"))
    finally:
        try:
            _os.remove(path)
        except OSError:
            pass
    if still:
        buf = io.BytesIO()
        frames[0].save(buf, format="PNG")
        return buf.getvalue()
    return _encode(frames, 4)
