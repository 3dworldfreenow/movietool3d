"""Object sheets: ONE picture from a free AI app -> MANY objects (with their states) in your library.

  1. plan    you list what you need ("log, stone, treasure chest, torch") - each object gets a height, what
             characters can do with it, and its STATES (a chest closed + open, a pot whole + broken, a torch
             off + burning ...). From a scene kit, the kit's objects are filled in for you.
  2. prompt  one prompt asks for all drawings in a grid, in a fixed order, on plain white.
  3. cut     the uploaded picture is cut into pieces (engine/sheets.py); piece k = drawing k of the prompt.
  4. save    every piece becomes a library picture; state pictures are linked to their object, so the engine
             swaps the picture when a character opens / breaks / lights / uses it (engine/objects.py).

Saved in assets/objsheets/<id>.json (+ <id>/sheet.png and <id>/pieces/P<n>.png).
"""
import json
import math
import os
import re
import shutil
import time

from . import image_prompts as ip

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "assets", "objsheets")
MAX_CELLS = 16

STATE_WORDS = [
    (("chest", "treasure", "box", "trunk", "door", "gate", "cupboard", "wardrobe", "fridge", "basket", "gift",
      "suitcase", "window"), ["open"]),
    (("pot", "vase", "jar", "matka", "egg", "crate", "glass", "pumpkin", "coconut", "mirror", "plate", "bottle",
      "piggy"), ["broken"]),
    (("torch", "lamp", "lantern", "diya", "candle", "campfire", "fire", "stove", "tv", "radio", "bulb", "fan"), ["on"]),
]
STATE_TEXT = {
    "open": "with its lid / door wide OPEN (show what is inside)",
    "broken": "BROKEN into 4-6 pieces lying on the ground",
    "on": "switched ON: lit, burning or glowing",
}
STATE_ABILITY = {"open": "open", "broken": "break", "on": "switch"}
SMALL = ("stone", "pebble", "ball", "apple", "book", "bag", "pot", "torch", "lamp", "lantern", "diya", "candle",
         "bottle", "cup", "key", "coin", "egg", "stick", "rope", "bucket", "basket", "fruit", "mango", "coconut")


def _clean(name):
    return re.sub(r"[^a-z0-9_]+", "_", str(name).lower()).strip("_")[:40]


def _states_for(what):
    for words, st in STATE_WORDS:
        if ip._match(what, words):
            return list(st)
    return []


def item(what, name=None, height=None, abilities=None, states=None):
    """One object of the plan, with sensible defaults guessed from the words."""
    what = str(what).strip()
    states = [_clean(s) for s in (states if states is not None else _states_for(what)) if _clean(s)]
    ab = list(abilities) if abilities is not None else ip._abilities(what)
    for st in states:
        if STATE_ABILITY.get(st) and STATE_ABILITY[st] not in ab:
            ab.append(STATE_ABILITY[st])
    small = any(ip._match(what, (w,)) for w in SMALL)
    return {"name": _clean(name or ip.slug(what, 28)), "what": what, "height": int(height or ip._size(what)),
            "abilities": ab, "states": states[:3], "kind": "prop" if small else "object"}


def plan_from_text(text):
    """'log, stone, treasure chest (open), torch' -> items. '(state, state)' after a thing sets its states."""
    items, used = [], set()
    for part in re.split(r"[,\n;]+", str(text)):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", part)
        states = None
        if m:
            part, states = m.group(1).strip(), [s.strip() for s in m.group(2).split("/") if s.strip()]
            states = [s for x in states for s in x.split(" and ")]
        it = item(part, states=states)
        while it["name"] in used:
            it["name"] += "_2"
        used.add(it["name"])
        items.append(it)
    return items


def cells(items):
    """Drawing order: each object, then its states right after it."""
    out = []
    for it in items:
        out.append({"item": it["name"], "state": None})
        for st in it.get("states") or []:
            out.append({"item": it["name"], "state": st})
    return out[:MAX_CELLS]


def grid(n):
    c = min(4, max(1, n)) if n != 5 and n != 6 else 3
    return int(math.ceil(n / c)), c


def prompt(sheet):
    items = {it["name"]: it for it in sheet["items"]}
    cs = sheet["cells"]
    rows, cols = grid(len(cs))
    style = ip.STYLES.get(sheet.get("style", "cartoon"), ip.STYLES["cartoon"]) if hasattr(ip, "STYLES") else \
        "2D cartoon for a children's animated series, flat colours, soft shading, clean dark outline"
    lines = []
    for k, c in enumerate(cs):
        it = items[c["item"]]
        what = it["what"]
        if c["state"] is None:
            base = {"open": "closed", "broken": "whole, not broken", "on": "switched off / not lit"}
            first = [base[x] for x in it.get("states") or [] if x in base]
            lines.append(f"{k + 1}) {what}" + (", " + ", ".join(first) if first else ""))
        else:
            txt = STATE_TEXT.get(c["state"], f"in this state: {c['state'].replace('_', ' ')}")
            lines.append(f"{k + 1}) the SAME {what} (same size, same colours) {txt}")
    ref = (" Match the art style, colours and light of the background picture I attached."
           if sheet.get("kit") else "")
    return (f"{style}. An OBJECT SHEET for a cartoon animation: {len(cs)} separate drawings on a pure white "
            f"background, in a grid of {rows} row{'s' if rows > 1 else ''} and {cols} columns, read left to right, "
            f"top row first. Draw exactly these, in this order:\n" + "\n".join(lines) + "\n"
            "Every drawing: the WHOLE object, complete (nothing cut off, nothing hidden), seen from the front or "
            "a little from the side, standing upright on its base; each one fills its own grid cell; a drawing "
            "that shows the SAME object in another state keeps the same scale as the drawing before it. Clear white "
            "space between all drawings (nothing touches), no ground, no shadows on the ground, no text, no "
            "numbers, no labels, no people, no animals, no extra objects." + ref)


# ---------------------------------------------------------------------------- storage
def path(sid, *more):
    return os.path.join(DIR, _clean(sid), *more)


def save(sheet):
    os.makedirs(DIR, exist_ok=True)
    sheet["cells"] = cells(sheet["items"])
    sheet["prompt"] = prompt(sheet)
    with open(os.path.join(DIR, sheet["id"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(sheet, fh, indent=1, ensure_ascii=False)
    return sheet


def new(items, title="", style="cartoon", india=True, kit=None):
    sid = _clean(title or "objects")[:24] + "_" + str(int(time.time()) % 100000)
    return save({"id": sid, "title": title or "objects", "style": style, "india": bool(india), "kit": kit,
                 "items": items, "created": int(time.time())})


def load(sid):
    try:
        with open(os.path.join(DIR, _clean(sid) + ".json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def list_sheets():
    out = []
    if os.path.isdir(DIR):
        for f in os.listdir(DIR):
            if f.endswith(".json"):
                s = load(f[:-5])
                if s:
                    out.append({"id": s["id"], "title": s["title"], "n": len(s["items"]),
                                "saved": bool(s.get("saved")), "created": s.get("created", 0)})
    return sorted(out, key=lambda s: -s["created"])


def delete(sid):
    shutil.rmtree(path(sid), ignore_errors=True)
    try:
        os.remove(os.path.join(DIR, _clean(sid) + ".json"))
    except OSError:
        pass


def from_kit(kit):
    """An object sheet for a scene kit's objects (same names, so the kit sees them as uploaded)."""
    items = []
    for p in kit["pieces"]:
        if p["role"] != "object":
            continue
        up = p.get("upload") or {}
        what = (up.get("description") or p["name"]).split(" - ")[0]
        items.append(item(what, name=p["name"], height=up.get("height"), abilities=up.get("abilities")))
    return new(items, kit.get("title", "kit") + " objects", kit.get("style", "cartoon"), True, kit=kit["id"])


# ---------------------------------------------------------------------------- cut + save
def split(sid, data_bytes):
    """Cut the uploaded sheet. Returns the pieces with the drawing each one is (by order)."""
    from PIL import Image
    from . import sheets
    sh = load(sid)
    if not sh:
        raise ValueError("unknown object sheet")
    im = sheets.load_rgba(data_bytes)
    shutil.rmtree(path(sid), ignore_errors=True)
    os.makedirs(path(sid, "pieces"), exist_ok=True)
    im.save(path(sid, "sheet.png"))
    n = len(sh["cells"])
    rows, cols = grid(n)
    per_row = [cols] * (rows - 1) + [n - cols * (rows - 1)]
    pieces = sheets.cut_grid(im, per_row)                # the grid we asked for: shards stay one drawing
    how = "grid"
    if pieces is None:                                  # drawn differently: separate drawings by outline
        pieces = sheets.cut_pieces(im, min_share=0.012)
        how = "outline"
    out = []
    for k, (crop, box, hpx) in enumerate(pieces):
        pid = f"P{k + 1}"
        Image.fromarray(crop, "RGBA").save(path(sid, "pieces", pid + ".png"))
        c = sh["cells"][k] if k < len(sh["cells"]) else None
        out.append({"id": pid, "hpx": hpx, "w": box[2] - box[0], "h": box[3] - box[1], "box": list(box),
                    "cell": k if c else None})
    sh["pieces"] = out
    sh["cut"] = how
    sh["saved"] = False
    with open(os.path.join(DIR, sh["id"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(sh, fh, indent=1, ensure_ascii=False)
    return sh


def _merge(sid, ps):
    """One piece, or several pieces put back together where they were on the sheet (shards of a broken pot)."""
    from PIL import Image
    if len(ps) == 1:
        return dict(ps[0], file=path(sid, "pieces", ps[0]["id"] + ".png"))
    x0 = min(p["box"][0] for p in ps)
    y0 = min(p["box"][1] for p in ps)
    x1 = max(p["box"][2] for p in ps)
    y1 = max(p["box"][3] for p in ps)
    im = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for p in ps:
        part = Image.open(path(sid, "pieces", p["id"] + ".png")).convert("RGBA")
        im.alpha_composite(part, (p["box"][0] - x0, p["box"][1] - y0))
    f = path(sid, "pieces", "M_" + "_".join(p["id"] for p in ps) + ".png")
    im.save(f)
    import numpy as np
    ys = np.nonzero(np.asarray(im)[..., 3] > 90)[0]
    return {"id": "+".join(p["id"] for p in ps), "file": f, "hpx": int(ys.max() - ys.min() + 1) if len(ys) else y1 - y0}


def save_all(sid, assign=None, items=None):
    """assign = {piece id: cell index | None (skip)}. Every object (+ its states) becomes a library picture.
    Returns the names saved."""
    from . import images
    sh = load(sid)
    if not sh or not sh.get("pieces"):
        raise ValueError("upload the sheet picture first")
    if items:                                           # names / heights / abilities edited in the Studio
        sh["items"] = items
        sh["cells"] = cells(items)
    by_name = {it["name"]: it for it in sh["items"]}
    groups = {}                                         # (item, state) -> [pieces]  (several = merged)
    for p in sh["pieces"]:
        k = (assign or {}).get(p["id"], p.get("cell")) if assign is not None else p.get("cell")
        if k in (None, "", "ignore"):
            continue
        k = int(k)
        if 0 <= k < len(sh["cells"]):
            c = sh["cells"][k]
            groups.setdefault((c["item"], c["state"]), []).append(p)
    got = {key: _merge(sid, ps) for key, ps in groups.items()}
    saved = []
    for name, it in by_name.items():
        main = got.get((name, None))
        if not main:
            continue
        with open(main["file"], "rb") as fh:
            nm = images.save_upload(name, fh.read(), name + ".png", it["what"], it.get("height"), None,
                                    it.get("kind", "object"), it.get("abilities") or [], cutout="off")
        states = {}
        for st in it.get("states") or []:
            p = got.get((name, st))
            if not p:
                continue
            with open(p["file"], "rb") as fh:
                sn = images.save_upload(f"{name}_{st}", fh.read(), f"{name}_{st}.png", f"{it['what']} - {st}",
                                        None, None, "state", [], cutout="off")
            images.update_meta(sn, state_of=nm, state=st, sheet_px=p["hpx"], sheet=sid)
            states[st] = sn
            saved.append(sn)
        images.update_meta(nm, states=states or None, sheet_px=main["hpx"], sheet=sid)
        saved.insert(0, nm)
        if sh.get("kit"):
            from . import scene_kit
            scene_kit.mark_uploaded(sh["kit"], name, nm)
    sh["saved"] = True
    with open(os.path.join(DIR, sh["id"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(sh, fh, indent=1, ensure_ascii=False)
    return saved
