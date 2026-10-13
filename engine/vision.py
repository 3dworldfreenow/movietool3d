"""Gemini looks at your pictures and ideas, so the Studio fills everything in for you:

  describe_image(bytes)  -> name, kind, description, floor line, height, abilities, tips ... for the upload form
  improve_idea(text)     -> a short idea becomes full image-prompt settings (subject, place, time, details)
"""
import json
import re

from . import ai
from .image_prompts import ABILITIES, KINDS, slug

KINDS_OK = ("background", "object", "prop", "picture", "any")

DESCRIBE = f"""You look at ONE picture that will be used in a 2D/2.5D cartoon animation engine (stickman-style
characters walk in front of or inside it). Fill in the settings the engine needs. Answer with JSON only:

{{
  "name": "short_snake_case_name (2-4 words, what it is, e.g. jungle_clearing, big_mossy_rock)",
  "kind": "background | object | prop | picture",
  "description": "one sentence for the AI story writer: what it is + where things are (left/right/far),
                  e.g. 'bright cartoon jungle clearing, dirt ground in the middle, big rocks on the right,
                  waterfall far away' - under 30 words",
  "place": "jungle | village | city | temple | school | home | river | beach | mountains | desert | space | other",
  "time": "morning | day | sunset | evening | night",
  "style": "cartoon | painted | photo | 3d",
  "ground": 0.80,
  "horizon": 0.55,
  "height": 300,
  "abilities": ["..."],
  "water": {{"kind": "none | river | lake | pond | sea", "x0": 0.6, "x1": 1.0, "y0": 0.62, "y1": 0.95}},
  "transparent_background": false,
  "animated_look": false,
  "problems": ["short notes about anything that will look wrong in the engine"],
  "tips": ["short, practical tips to use or improve it"]
}}

Rules:
- kind "background": a whole scene / place characters stand in. "object": one thing that stands in a scene
  (tree, rock, house, statue, chest). "prop": a small thing a character can hold (pot, torch, ball, bag).
  "picture": an illustration or real photo to show full screen for a moment (map, landmark, portrait).
- ground (backgrounds only, else null): fraction 0..1 from the TOP of the picture where the feet of a person
  standing at the FRONT of the open ground would be - usually the lower edge of the flat walkable area,
  0.72 - 0.9. Look at the ground, not at foreground plants.
- horizon (backgrounds only, else null): fraction from the top where the flat ground ends in the distance
  (where the far ground meets distant hills / trees / sky) - always smaller than ground.
- height (objects/props only, else null): real size in engine units where an adult person is 300 units tall
  (child 245, door 320, big rock 230, tree 650, pot 60, ball 30).
- abilities (objects/props only, else []): choose from {", ".join(ABILITIES)}.
  movable = can be pushed; light = one person can carry/throw; heavy = needs helpers; round = rolls;
  sit / stand / climb / hide = characters can sit on / stand on / climb / hide behind it; open = has a lid
  or door; break = breaks into pieces; floats / sinks in water.
- water (backgrounds only): the box around the visible water surface (river / lake / sea / pond) as fractions
  of the picture width (x0 < x1) and height from the top (y0 < y1); kind "none" and zeros if there is no water.
  Do not count a far waterfall or the sky.
- problems: mention people, animals or text drawn in a background (they will not move), a floor line
  that is too high, very busy middle ground (characters get lost), a non-white background on an object
  that must be cut out, low resolution, a watermark. [] if none.
"""

IDEA = """Turn this short idea into settings for an image prompt for a 2D cartoon animation series.
Answer with JSON only:
{
  "kind": "background | backdrop | object | prop | animated | picture",
  "subject": "what to draw, specific and visual (under 15 words)",
  "place": "where / theme (under 6 words)",
  "time": "morning | day | sunset | evening | night",
  "season": "summer | monsoon | winter | spring | autumn | ''",
  "style": "cartoon | painted | photo",
  "extra": "2-4 concrete visual details that make it rich and specific: landmarks, colours, lighting,
            what is on the left and on the right (never in the middle of the ground), under 40 words",
  "india": true
}
Keep the middle of backgrounds open for the characters; big things only at the sides. No people, animals or
text in backgrounds or objects. Idea: """


def _client():
    st = ai.settings()
    return ai.Gemini(st["key"], st["model"], st["api_version"], timeout=90, log=lambda *a: None)


def _num(v, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(min(max(f, lo), hi), 3)


def _water(w):
    if not isinstance(w, dict):
        return None
    kind = str(w.get("kind", "none")).lower()
    if kind not in ("river", "lake", "pond", "sea"):
        return None
    box = [_num(w.get(k), 0, 1) for k in ("x0", "x1", "y0", "y1")]
    if None in box or box[1] - box[0] < 0.05 or box[3] - box[2] < 0.03:
        return None
    return {"kind": kind, "x0": box[0], "x1": box[1], "y0": box[2], "y1": box[3]}


def describe_image(data, mime="image/png", filename=""):
    """Ask Gemini what the picture is and how to use it. Returns a clean dict for the upload form."""
    if mime.startswith("video/"):
        raise ai.GeminiError("Gemini auto-fill works with pictures (PNG / JPG / WebP / GIF), not video clips.")
    if mime == "image/gif" or mime == "image/apng":
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(data))
        im.seek(0)
        buf = io.BytesIO()
        im.convert("RGBA").save(buf, "PNG")
        data, mime = buf.getvalue(), "image/png"
    text = _client().generate(DESCRIBE + (f"\nFile name: {filename}" if filename else ""), json_mode=True,
                              temperature=0.3, max_tokens=2048, images=[(mime, data)])
    r = ai.extract_json(text)
    kind = str(r.get("kind", "any")).lower()
    kind = kind if kind in KINDS_OK else "any"
    out = {
        "name": slug(r.get("name") or filename or "picture"),
        "kind": kind,
        "description": str(r.get("description", "")).strip()[:300],
        "place": str(r.get("place", "") or ""), "time": str(r.get("time", "") or ""),
        "style": str(r.get("style", "") or ""),
        "ground": _num(r.get("ground"), 0.45, 0.97) if kind in ("background", "any") else None,
        "horizon": _num(r.get("horizon"), 0.05, 0.9) if kind in ("background", "any") else None,
        "height": _num(r.get("height"), 10, 2000) if kind in ("object", "prop") else None,
        "abilities": [a for a in (r.get("abilities") or []) if a in ABILITIES] if kind in ("object", "prop") else [],
        "water": _water(r.get("water")) if kind in ("background", "any") else None,
        "transparent_background": bool(r.get("transparent_background")),
        "problems": [str(p) for p in (r.get("problems") or [])][:6],
        "tips": [str(p) for p in (r.get("tips") or [])][:6],
    }
    if out["height"]:
        out["height"] = int(round(out["height"]))
    return out


def improve_idea(idea, kind=None):
    text = _client().generate(IDEA + json.dumps(str(idea)) + (f"\nPreferred kind: {kind}" if kind else ""),
                              json_mode=True, temperature=0.8, max_tokens=1024)
    r = ai.extract_json(text)
    k = str(r.get("kind", kind or "background")).lower()
    return {
        "kind": k if k in KINDS else (kind or "background"),
        "subject": str(r.get("subject", "")).strip(),
        "place": str(r.get("place", "")).strip(),
        "time": str(r.get("time", "day")).lower() if str(r.get("time", "")).lower() in
        ("morning", "day", "sunset", "evening", "night") else "day",
        "season": re.sub(r"[^a-z ]", "", str(r.get("season", "")).lower()).strip(),
        "style": str(r.get("style", "cartoon")).lower() if str(r.get("style", "")).lower() in
        ("cartoon", "painted", "photo") else "cartoon",
        "extra": str(r.get("extra", "")).strip(),
        "india": bool(r.get("india", True)),
    }


FIND = """Look at this background picture for a cartoon animation. List the separate THINGS in it that characters
could use if they were real objects: trees to climb or hide behind, big rocks to sit on or hide behind, huts,
logs, carts, wells, statues ... Only clear, single things (not "bushes everywhere", not the ground, not the sky,
not far away things). At most 8. Answer with JSON only:
{"things": [{"name": "short_snake_case_name", "what": "a few words", "box": [x0, y0, x1, y1],
             "abilities": ["climb", "hide"]}]}
box = the thing's box as fractions 0..1 of the picture (x from the left, y from the top), tight around it.
abilities from: climb, hide, sit, stand, open, break, movable, heavy."""


def find_things(data, mime="image/png"):
    """Gemini (the free text model - it can look at pictures) points out things to take out of a background."""
    text = _client().generate(FIND, json_mode=True, temperature=0.2, max_tokens=2048, images=[(mime, data)])
    r = ai.extract_json(text)
    out = []
    for t in (r.get("things") or [])[:8]:
        box = [_num(v, 0, 1) for v in (t.get("box") or [])[:4]]
        if len(box) != 4 or None in box or box[2] - box[0] < 0.02 or box[3] - box[1] < 0.02:
            continue
        out.append({"name": slug(t.get("name") or t.get("what") or "thing"), "what": str(t.get("what", ""))[:60],
                    "box": box, "abilities": [a for a in (t.get("abilities") or []) if a in ABILITIES]})
    return out
