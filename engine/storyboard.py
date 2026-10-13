"""Storyboard preview and YouTube thumbnail - check a story in seconds before the full render.

Storyboard (2D animation: the story reel): one small picture per camera shot - the real shot the video will show,
with the auto-director's choices - and under it the scene, the time, the shot ("close-up on Ravi") and the line
being spoken. A 4-minute story is checked in about 20-40 seconds instead of a full render.

    python main.py storyboard stories/lost_kite.json          -> output/lost_kite.storyboard.png (+ more pages)
    python main.py thumbnail stories/lost_kite.json           -> output/lost_kite.thumbnail.png (1280 x 720)
    python main.py thumbnail stories/lost_kite.json --mosaic  -> four strong moments in one picture

The thumbnail is chosen like an editor would (Python Playground ch. 7, photomosaics, for the mosaic): close shots
with a strong feeling (surprise, fear, laughter), bright colourful frames, the hook moment - then the title is
written big on it with a thick outline.
"""
import math
import multiprocessing as mp
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageStat

FX_TYPES = ("shake", "punch", "impact", "pulse", "zoom_pulse", "earthquake", "explosion", "rumble", "vehicle",
            "heartbeat", "rack_focus")
NAMES = {"closeup": "close-up", "medium_closeup": "medium close-up", "over_shoulder": "over the shoulder",
         "auto": "two-shot", "establishing": "establishing", "low_angle": "low angle", "high_angle": "high angle",
         "crane_up": "crane up", "crane_down": "crane down", "pull_back": "pull back", "push_in": "push in",
         "static_wide": "locked wide", "extreme_wide": "extreme wide", "slow_push": "slow push in"}
STRONG = {"surprised": 3.0, "scared": 3.0, "shocked": 3.0, "laughing": 2.5, "angry": 2.5, "crying": 2.2,
          "happy": 1.5, "excited": 2.0, "love": 1.2, "sad": 1.2}

_P = None


def _init(P):
    global _P
    _P = P


def _frame(fi):
    from . import render as R
    data = R.render_frame(fi, _P)
    return data


def _font(size, bold=True):
    for name in ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "NotoSansDevanagari-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build(story, resolution="480x270", tts="silent", log=print):
    """-> Project made small for pictures only (silent voices give the same timing as real ones' estimates)."""
    from .project import Project
    from . import codedraw
    codedraw.ensure_built(log=None)
    W, H = (int(v) for v in resolution.split("x"))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    P = Project(story, {"tts": tts, "cache": os.path.join(root, "cache", "validate"), "resolution": f"{W}x{H}",
                        "fps": 12, "subtitles": False})
    return P


def shots(P):
    """[{t (whole video), scene, shot, who, line, emotion, lt}] - one per camera shot (cut), with the moment to show."""
    out = []
    for it in P.items:
        if it.kind != "scene":
            continue
        sc = it.scene
        cams = sorted([(t, c) for t, c in sc.camera if c.get("type") not in FX_TYPES], key=lambda x: x[0])
        if not cams or cams[0][0] > 0.3:
            cams = [(0.0, {"type": "wide"})] + cams
        merged = []
        for t, c in cams:                                   # moves without a cut inside a shot are one shot
            if merged and (t - merged[-1][0] < 0.5 or not c.get("cut", True)):
                if t - merged[-1][0] < 0.5:
                    merged[-1] = (merged[-1][0], c)
                continue
            merged.append((t, c))
        for k, (t, c) in enumerate(merged):
            t_end = merged[k + 1][0] if k + 1 < len(merged) else sc.duration
            if t_end - t < 0.25:
                continue
            lt = t + min(1.2, (t_end - t) * 0.5)
            sp = next((s for s in sc.speeches if s.start <= lt < s.end), None) or \
                next((s for s in sc.speeches if t <= s.start < t_end), None)
            who = c.get("target")
            name = None
            if who in sc.tracks:
                name = sc.tracks[who].cdef.name
            typ = str(c.get("type"))
            label = NAMES.get(typ, typ.replace("_", " "))
            if name:
                label += f" on {name}" if typ not in ("over_shoulder", "reverse") else \
                    f" ({name}'s shoulder)"
            if c.get("look_at") in sc.tracks:
                label += f" -> {sc.tracks[c['look_at']].cdef.name}"
            spk = sc.tracks[sp.who].cdef.name if sp is not None and sp.who in sc.tracks else \
                ("Narrator" if sp is not None else None)
            emo = (sp.emotion if sp is not None else None) or None
            out.append(dict(t=round(it.start + lt, 2), lt=lt, scene=sc.index + 1, shot=label, type=typ,
                            who=spk, line=str(sp.text) if sp is not None else "", emotion=emo,
                            dur=round(t_end - t, 1), sid=it.spec.get("id")))
    return out


def render_times(P, times, workers=None, log=print):
    """Render frames at the given video times (seconds) in parallel. -> [PIL images]"""
    from . import render as R
    P.strip_for_workers()
    fis = [min(P.n_frames - 1, int(t * P.fps)) for t in times]
    workers = workers or max(1, min(len(fis), (os.cpu_count() or 2)))
    if workers <= 1 or len(fis) <= 1:
        _init(P)
        datas = [_frame(fi) for fi in fis]
    else:
        method = "fork" if "fork" in mp.get_all_start_methods() else "spawn"
        with mp.get_context(method).Pool(workers, initializer=_init, initargs=(P,)) as pool:
            datas = pool.map(_frame, fis, chunksize=1)
    del R
    return [Image.frombuffer("RGBA", (P.W, P.H), d, "raw", "BGRA", 0, 1).convert("RGB") for d in datas]


def _fmt(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def sheet(P, items, images, title="", cols=4, per_page=24):
    """Pages of tiles: the picture, then 'scene 2 · 0:41 · close-up on Ravi', then the line. -> [PIL images]"""
    tw, th = images[0].size if images else (480, 270)
    cap_h = 92
    pages = []
    f1, f2, ft = _font(15), _font(14, bold=False), _font(26)
    for p0 in range(0, len(items), per_page):
        chunk = list(zip(items[p0:p0 + per_page], images[p0:p0 + per_page]))
        rows = int(math.ceil(len(chunk) / float(cols)))
        page = Image.new("RGB", (cols * (tw + 12) + 12, 60 + rows * (th + cap_h + 12) + 12), (246, 244, 238))
        d = ImageDraw.Draw(page)
        d.text((14, 16), f"{title}  -  storyboard {p0 // per_page + 1}/{int(math.ceil(len(items) / float(per_page)))}"
               f"  ({len(items)} shots)", fill=(30, 30, 40), font=ft)
        for k, (s, im) in enumerate(chunk):
            x = 12 + (k % cols) * (tw + 12)
            y = 60 + (k // cols) * (th + cap_h + 12)
            page.paste(im, (x, y))
            d.rectangle((x, y + th, x + tw, y + th + cap_h), fill=(255, 255, 255))
            d.rectangle((x, y, x + 36, y + 22), fill=(20, 20, 30))
            d.text((x + 6, y + 3), str(p0 + k + 1), fill=(255, 255, 255), font=f1)
            d.text((x + 6, y + th + 4), f"scene {s['scene']} · {_fmt(s['t'])} · {s['dur']}s · {s['shot']}",
                   fill=(40, 60, 120), font=f1)
            if s["line"]:
                who = f"{s['who']}: " if s["who"] else ""
                emo = f" ({s['emotion']})" if s.get("emotion") else ""
                txt = textwrap.wrap(f"{who}{s['line']}{emo}", width=max(20, tw // 8))[:3]
                for j, ln in enumerate(txt):
                    d.text((x + 6, y + th + 26 + j * 19), ln, fill=(30, 30, 30), font=f2)
        pages.append(page)
    return pages


def storyboard(story, out=None, resolution="480x270", log=print):
    """Make the storyboard pages. -> [paths]"""
    import time
    t0 = time.time()
    P = build(story, resolution, log=log)
    items = shots(P)
    log(f"storyboard: {len(items)} shots in {len(P.items)} blocks - drawing them ...")
    imgs = render_times(P, [s["t"] for s in items], log=log)
    pages = sheet(P, items, imgs, title=str(P.data.get("title", os.path.basename(story))))
    base = out or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output",
                               os.path.splitext(os.path.basename(story))[0] + ".storyboard.png")
    os.makedirs(os.path.dirname(os.path.abspath(base)), exist_ok=True)
    paths = []
    for i, pg in enumerate(pages):
        p = base if i == 0 else base.replace(".png", f".{i + 1}.png")
        pg.save(p)
        paths.append(p)
    log(f"storyboard: {len(paths)} page(s) in {time.time() - t0:.0f} s -> {', '.join(paths)}")
    return paths, items


# ============================================================================ thumbnail
def _score(s, im, hook_t=None):
    """How good this frame is for a thumbnail."""
    st = ImageStat.Stat(im.convert("HSV"))
    sat, val = st.mean[1] / 255.0, st.mean[2] / 255.0
    contrast = ImageStat.Stat(im.convert("L")).stddev[0] / 80.0
    sc = 1.5 * sat + 1.0 * min(val, 0.75) + 0.8 * min(contrast, 1.0)
    sc += {"closeup": 2.2, "medium_closeup": 2.0, "low_angle": 1.4, "medium": 1.0, "over_shoulder": 0.6,
           "auto": 0.6, "high_angle": 0.4}.get(s["type"], 0.0)
    sc += STRONG.get(str(s.get("emotion") or ""), 0.0)
    if hook_t is not None and abs(s["t"] - hook_t) < 4.0:
        sc += 1.5
    if val < 0.25:
        sc -= 2.0                                        # too dark
    return sc


def _hook_time(P):
    try:
        h = (P.data.get("settings") or {}).get("hook")
        if not isinstance(h, dict):
            return None
        n = int(h.get("scene", 1))
        k = 0
        for it in P.items:
            if it.kind == "scene":
                k += 1
                if k == n:
                    return it.start + float(h.get("at", 0))
    except Exception:
        return None
    return None


def _title_on(img, title, sub=None):
    W, H = img.size
    d = ImageDraw.Draw(img)
    size = int(H * 0.13)
    lines = textwrap.wrap(title.upper(), width=18)[:3]
    while lines and size > 30:
        f = _font(size)
        if all(d.textlength(ln, font=f) < W * 0.92 for ln in lines):
            break
        size -= 4
    f = _font(size)
    y = H - 30 - len(lines) * (size + 8)
    for ln in lines:
        w = d.textlength(ln, font=f)
        x = (W - w) / 2
        d.text((x, y), ln, font=f, fill=(255, 225, 40), stroke_width=max(4, size // 9), stroke_fill=(0, 0, 0))
        y += size + 8
    if sub:
        fs = _font(int(size * 0.42))
        w = d.textlength(sub, font=fs)
        d.text(((W - w) / 2, 24), sub, font=fs, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    return img


def thumbnail(story, out=None, mosaic=False, log=print):
    """-> path of a 1280 x 720 thumbnail."""
    P = build(story, "640x360", log=log)
    items = shots(P)
    if not items:
        raise SystemExit("no shots in this story")
    step = max(1, len(items) // 40)
    cand = items[::step]
    imgs = render_times(P, [s["t"] for s in cand], log=log)
    hook_t = _hook_time(P)
    ranked = sorted(zip(cand, imgs), key=lambda p: -_score(p[0], p[1], hook_t))
    title = str(P.data.get("title", ""))
    if mosaic:
        pick = [im for _s, im in ranked[:4]]
        while len(pick) < 4:
            pick.append(pick[-1])
        big = Image.new("RGB", (1280, 720))
        for k, im in enumerate(pick):
            big.paste(im.resize((640, 360)), ((k % 2) * 640, (k // 2) * 360))
    else:
        s, im = ranked[0]
        big = im.resize((1280, 720), Image.LANCZOS)
    big = _title_on(big, title)
    path = out or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output",
                               os.path.splitext(os.path.basename(story))[0] + ".thumbnail.png")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    big.save(path)
    log(f"thumbnail -> {path}")
    return path


# ============================================================================ colour script
BEAT_COL = {"calm": (200, 196, 180), "warm": (240, 170, 90), "hope": (245, 200, 110), "wonder": (120, 190, 240),
            "secret": (70, 95, 120), "tense": (90, 110, 130), "danger": (200, 50, 35), "sad": (90, 110, 160),
            "doom": (150, 70, 40)}


def colorscript(story, out=None, resolution="320x180", log=print):
    """The colour script (as an animation studio pins on the wall): one small frame from the middle of every scene,
    in story order, each with the colour band of its beat ("mood") under it - to see the emotional rhythm of the
    whole film at a glance: where it is warm, where it goes cold, where the danger peaks. -> path"""
    import time
    from . import stick3d
    t0 = time.time()
    P = build(story, resolution, log=log)
    scenes = [it for it in P.items if it.kind == "scene"]
    times = [it.start + it.duration * 0.55 for it in scenes]
    log(f"colorscript: {len(scenes)} scenes - drawing them ...")
    imgs = render_times(P, times, log=log)
    W, H = P.W, P.H
    cols = 8
    rows = (len(imgs) + cols - 1) // cols
    band, gap, top = 22, 10, 70
    sheet_ = Image.new("RGB", (cols * (W + gap) + gap, top + rows * (H + band + 34 + gap) + gap), (24, 24, 28))
    d = ImageDraw.Draw(sheet_)
    try:
        f1 = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
        f2 = ImageFont.truetype("DejaVuSans.ttf", 15)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    d.text((gap, 18), f"{P.data.get('title', '')} - colour script", fill=(240, 240, 240), font=f1)
    for k, (it, im) in enumerate(zip(scenes, imgs)):
        x = gap + (k % cols) * (W + gap)
        y = top + (k // cols) * (H + band + 34 + gap)
        sheet_.paste(im, (x, y))
        mood = stick3d.scene_mood(it.scene, it.spec) or "calm"
        d.rectangle((x, y + H, x + W, y + H + band), fill=BEAT_COL.get(mood, (128, 128, 128)))
        d.text((x + 6, y + H + 3), mood, fill=(10, 10, 10) if mood in ("calm", "warm", "hope", "wonder") else (245, 245, 245),
               font=f2)
        d.text((x, y + H + band + 6), f"{k + 1}. {it.spec.get('id', '')}  {_fmt(it.start)}", fill=(200, 200, 205), font=f2)
    base = out or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output",
                               os.path.splitext(os.path.basename(story))[0] + ".colorscript.png")
    os.makedirs(os.path.dirname(os.path.abspath(base)), exist_ok=True)
    sheet_.save(base)
    log(f"colorscript: {len(scenes)} scenes in {time.time() - t0:.0f} s -> {base}")
    return base
