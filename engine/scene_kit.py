"""Scene kit: one idea -> a matching SET of image prompts (one background + the objects characters will use +
an optional moving thing), each with its upload settings, all in the same style. When the pictures are
uploaded the kit knows its pieces and writes a ready story JSON that puts them together.

Why separate pictures: an object made alone on white comes out complete, so it can be pushed, thrown,
climbed or broken and still look right; the background is made without those objects, so nothing has to be
guessed behind them. The background still becomes 2.5D with its depth layers (engine/photodepth.py).

Kits are saved in assets/kits/<id>.json.
"""
import json
import os
import re
import time

from . import image_prompts as ip

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "assets", "kits")

MATCH = ("Match the exact art style, outline thickness, colours and lighting of the background picture of the "
         "same scene")

PLAN = """You plan a SCENE KIT for a 2.5D cartoon animation engine: separate pictures that are generated one by
one with an AI image tool and then combined by the engine. Characters are added by the engine (never draw
people or animals). Answer with JSON only:
{
  "title": "short name of the scene, 2-4 words",
  "place": "jungle | village | river | temple | school | home | beach | mountains | desert | city | other",
  "time": "morning | day | sunset | evening | night",
  "season": "summer | monsoon | winter | spring | autumn | ''",
  "background": {
     "subject": "the place itself, WITHOUT the separate objects below (under 15 words)",
     "extra": "2-4 visual details: what is far away, what frames the left and right edges (under 35 words)",
     "water": {"kind": "river | lake | pond | sea | none", "side": "left | right | back | none"}
  },
  "objects": [
     {"subject": "one thing characters USE, e.g. 'fallen tree log', 'big mossy boulder', 'clay pot'",
      "abilities": ["from: movable, light, heavy, round, throw, sit, stand, climb, hide, open, break, floats, sinks"],
      "side": "left | right | middle",
      "why": "what a character can do with it in a story (short)"}
  ],
  "animated": {"subject": "one thing that moves by itself (waterfall, campfire, flag) or ''"}
}
Rules: 3-5 objects that make good story actions (push into water, climb, hide behind, sit on, throw, open,
break). Big things (trees, boulders) at the sides; small things anywhere. If there is water, include at least
one thing that floats and one that sinks. Idea: """

# offline plans (no Gemini key): keyword -> plan
TEMPLATES = {
    "river": dict(place="river", background=dict(subject="a jungle river bank with a wide open dirt bank",
                                                  extra="dense jungle far away, tall trees at both edges",
                                                  water=dict(kind="river", side="right")),
                  objects=[("fallen tree log", ["movable", "heavy", "sit", "stand", "floats"], "left"),
                           ("big leafy climbing tree", ["climb", "hide"], "left"),
                           ("small round river stone", ["movable", "light", "round", "throw", "sinks"], "middle"),
                           ("big mossy boulder", ["movable", "heavy", "round", "hide", "stand"], "right")]),
    "jungle": dict(place="jungle", background=dict(subject="a sunny jungle clearing with an open dirt ground",
                                                   extra="waterfall far away, giant trees and vines at both edges",
                                                   water=dict(kind="none", side="none")),
                   objects=[("big leafy climbing tree", ["climb", "hide"], "left"),
                            ("big mossy boulder", ["movable", "heavy", "round", "hide", "stand"], "right"),
                            ("wooden treasure chest", ["movable", "open", "sit", "stand"], "right"),
                            ("clay pot", ["movable", "light", "throw", "break"], "middle")]),
    "village": dict(place="village", background=dict(subject="an Indian village square with a packed earth ground",
                                                      extra="mud houses far away, a big tree at the left edge",
                                                      water=dict(kind="none", side="none")),
                    objects=[("haystack", ["hide", "climb"], "left"),
                             ("wooden cart wheel", ["movable", "round", "stand"], "right"),
                             ("clay water pot", ["movable", "light", "throw", "break"], "middle"),
                             ("wooden bench", ["movable", "sit"], "right")]),
    "home": dict(place="home", background=dict(subject="a cosy Indian living room with a clear floor",
                                               extra="window with curtains, shelves at the edges",
                                               water=dict(kind="none", side="none")),
                 objects=[("sofa", ["sit", "hide"], "left"), ("wooden box of toys", ["movable", "open"], "right"),
                          ("glass vase", ["movable", "light", "break"], "middle")]),
}
SIDE_X = {"left": (420, 820), "right": (1580, 1980), "middle": (1050, 1350)}


def _now_id(title):
    return f"{ip.slug(title, 24)}_{int(time.time()) % 100000}"


def _fallback_plan(idea):
    low = idea.lower()
    key = next((k for k in ("river", "lake", "pond", "stream", "jungle", "forest", "village", "home", "room", "house")
                if k in low), "jungle")
    key = {"lake": "river", "pond": "river", "stream": "river", "forest": "jungle", "room": "home",
           "house": "home"}.get(key, key)
    t = TEMPLATES[key]
    return {"title": idea[:40] or key, "place": t["place"], "time": "day", "season": "",
            "background": dict(t["background"]),
            "objects": [{"subject": s, "abilities": ab, "side": side, "why": ""} for s, ab, side in t["objects"]],
            "animated": {"subject": "waterfall" if key == "river" else ""}}


def plan_kit(idea, use_gemini=True):
    """The plan (title, background, objects ...). Gemini when a key is set, else a built-in template."""
    if use_gemini:
        from . import ai
        if ai.settings().get("key"):
            st = ai.settings()
            g = ai.Gemini(st["key"], st["model"], st["api_version"], timeout=90, log=lambda *a: None)
            r = ai.extract_json(g.generate(PLAN + json.dumps(str(idea)), json_mode=True, temperature=0.8,
                                           max_tokens=2048))
            if isinstance(r, dict) and r.get("objects"):
                r["_by"] = "gemini"
                return r
    r = _fallback_plan(idea)
    r["_by"] = "template"
    return r


def make_kit(idea, style="cartoon", india=True, use_gemini=True):
    plan = plan_kit(idea, use_gemini)
    title = str(plan.get("title") or idea or "scene")
    place = str(plan.get("place", "") or "")
    tm = str(plan.get("time", "day") or "day")
    season = str(plan.get("season", "") or "")
    kit_id = _now_id(title)
    pieces = []
    bgp = plan.get("background") or {}
    water = bgp.get("water") or {}
    wk = str(water.get("kind", "none")).lower()
    extra = str(bgp.get("extra", ""))
    if wk not in ("", "none"):
        side = str(water.get("side", "right")).lower()
        where = {"left": "along the left third of the ground", "right": "along the right third of the ground",
                 "back": "across the back of the ground, behind the open bank"}.get(side, "at one side")
        extra = (extra + f". A calm {wk} {where}, its near bank on the flat front ground so characters can stand "
                         f"right next to the water; clear water surface").strip(". ")
    bg = ip.build("background", bgp.get("subject") or title, place, tm, season, style, extra, india)
    bg["upload"]["name"] = ip.slug(f"{title}_bg", 32)
    bg["upload"]["description"] = f"{title} background - {bgp.get('subject', '')}".strip(" -")
    pieces.append(dict(role="background", name=bg["upload"]["name"], prompt=bg["prompt"], tips=bg["tips"],
                       upload=bg["upload"], water=wk if wk not in ("", "none") else None))
    used = set()
    for k, o in enumerate(plan.get("objects") or []):
        subj = str(o.get("subject", "")).strip()
        if not subj:
            continue
        kind = "prop" if any(w in subj.lower() for w in ("pot", "stone", "ball", "vase", "bag", "torch", "book",
                                                           "apple", "pebble")) else "object"
        r = ip.build(kind, subj, place, tm, season, style, MATCH, india)
        name = ip.slug(subj, 28)
        while name in used:
            name += "_2"
        used.add(name)
        up = r["upload"]
        up["name"] = name
        ab = [a for a in (o.get("abilities") or []) if a in ip.ABILITIES] or up.get("abilities") or []
        up["abilities"] = ab
        up["description"] = subj + (f" - {o['why']}" if o.get("why") else "")
        up["kind"] = "object"
        lo, hi = SIDE_X.get(str(o.get("side", "middle")).lower(), SIDE_X["middle"])
        x = lo + (hi - lo) * ((k * 0.37) % 1.0)
        pieces.append(dict(role="object", name=name, prompt=r["prompt"],
                           tips=["Paste the BACKGROUND picture into the image tool too and say: draw this object "
                                 "in exactly the same style, alone on white."] + r["tips"],
                           upload=up, x=round(x), z=round(60 + 110 * (k % 3))))
    anim = str((plan.get("animated") or {}).get("subject", "")).strip()
    if anim:
        r = ip.build("animated", anim, place, tm, season, style, MATCH, india)
        r["upload"]["name"] = ip.slug(anim, 28)
        pieces.append(dict(role="animated", name=r["upload"]["name"], prompt=r["prompt"], tips=r["tips"],
                           upload=r["upload"], x=1900, z=900))
    kit = dict(id=kit_id, idea=idea, title=title, style=style, place=place, time=tm, by=plan.get("_by", ""),
               pieces=pieces, created=int(time.time()))
    save(kit)
    return kit


# ---------------------------------------------------------------------------- storage + status
def save(kit):
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, kit["id"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(kit, fh, indent=1, ensure_ascii=False)


def load(kit_id):
    try:
        with open(os.path.join(DIR, re.sub(r"[^a-z0-9_]", "", kit_id) + ".json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def list_kits():
    out = []
    if os.path.isdir(DIR):
        for f in sorted(os.listdir(DIR), reverse=True):
            if f.endswith(".json"):
                k = load(f[:-5])
                if k:
                    out.append(k)
    return sorted(out, key=lambda k: -k.get("created", 0))


def status(kit):
    """Which pieces are uploaded (by the name the kit expects, or recorded when uploading)."""
    from . import images, photodepth
    st = {}
    for p in kit["pieces"]:
        name = p.get("uploaded_as") or p["name"]
        st[p["name"]] = dict(uploaded=images.exists(name), name=name,
                             depth=bool(photodepth.status(name)) if p["role"] == "background" else None)
    return st


def mark_uploaded(kit_id, piece, name):
    kit = load(kit_id)
    if not kit:
        return
    for p in kit["pieces"]:
        if p["name"] == piece:
            p["uploaded_as"] = name
    save(kit)


def story_json(kit):
    """A ready test story that puts the uploaded pieces together (missing pieces are left out)."""
    from . import images
    st = status(kit)
    bg = next((p for p in kit["pieces"] if p["role"] == "background"), None)
    scene = {"id": kit["id"], "width": 2400, "characters": [{"id": "ravi", "x": 1150, "z": 60},
                                                            {"id": "maya", "x": 1300, "z": 260}]}
    if bg and st[bg["name"]]["uploaded"]:
        scene["background"] = {"image": st[bg["name"]]["name"]}
    else:
        scene["background"] = {"preset": kit.get("place") if kit.get("place") in ("jungle", "village", "river")
                               else "jungle", "time": kit.get("time", "day")}
    objs, events = [], [{"who": "ravi", "say": "Look at this place!", "facing": "camera", "emotion": "happy"}]
    water = bool(bg and bg.get("water"))
    zone = None
    if bg and st[bg["name"]]["uploaded"]:
        from . import photodepth
        zs = photodepth.zones(photodepth.status(st[bg["name"]]["name"]), 2400)
        zone = zs[0] if zs else None
        water = water or bool(zone)
    for p in kit["pieces"]:
        if p["role"] == "background" or not st[p["name"]]["uploaded"]:
            continue
        name = st[p["name"]]["name"]
        if p["role"] == "animated":
            objs.append({"id": name, "type": name, "x": p.get("x", 1900), "z": p.get("z", 900)})
            continue
        info = images.info(name) or {}
        ab = set(info.get("abilities") or p["upload"].get("abilities") or [])
        x = p.get("x", 1200)
        if zone and ab & {"floats", "sinks", "throw"} and "climb" not in ab:     # things for the water go near it
            near = zone[0] - 380 if zone[0] > 700 else zone[1] + 380
            x = near - (len(objs) % 2) * 170
        objs.append({"id": name, "type": name, "x": round(x), "z": p.get("z", 100)})   # height: the upload's
        who = "maya" if len(events) % 2 == 0 else "ravi"
        if "climb" in ab:
            events += [{"who": who, "do": "climb", "object": name}, {"who": who, "say": "I can see everything!"},
                       {"who": who, "do": "get_down"}]
        elif "throw" in ab or "light" in ab:
            events.append({"who": who, "do": "throw", "object": name, **({"to": "water"} if water else {})})
        elif "movable" in ab and "heavy" in ab:
            events.append({"who": who, "do": "push", "object": name, "helpers": ["maya" if who == "ravi" else "ravi"],
                           **({"to": "water"} if water else {"by": 300})})
        elif "open" in ab:
            events.append({"who": who, "do": "open", "object": name})
        elif "sit" in ab:
            events.append({"who": who, "do": "sit_on", "object": name})
        elif "hide" in ab:
            events.append({"who": who, "do": "hide", "object": name})
    scene["objects"] = objs
    scene["events"] = events + [{"who": "maya", "say": "What a great day!", "emotion": "happy"}]
    return {"title": kit["title"], "settings": {"language": "en-IN", "camera_mode": "3d", "director": "cinematic",
                                                "music": "adventure", "hook": "off"},
            "characters": {"ravi": {"name": "Ravi", "age": "child", "gender": "male", "outfit": "tshirt",
                                    "outfit_color": "#1d4e89", "hair": "spiky"},
                           "maya": {"name": "Maya", "age": "child", "gender": "female", "outfit": "frock",
                                    "outfit_color": "#ff70a6", "hair": "ponytail"}},
            "scenes": [scene], "_missing": [p["name"] for p in kit["pieces"] if not st[p["name"]]["uploaded"]
                                           ]}
