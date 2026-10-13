"""Planet systems you keep (planets/<name>.json) - your own star with your own planets, written as planet DATA
(engine/galaxy.py from_data), made in the 🪐 Planets page (/planets) or copied from a star of a galaxy.

    {"name": "vela", "about": "a school trip system",
     "star": {"name": "Vela", "kind": "orange star", "colour": "#ffc27a", "size": 1.3},
     "planets": [{"name": "Vela b", "type": "rocky", "gravity": 0.72, "temperature": 240, "life": true, ...}, ...]}

A story uses one with settings "planet_system": "vela" and scene "planet": "Vela b" (or 1, 2 ... in order).
The video page's 🪐 Planets picker tells the AI which worlds it may use: none, our Solar System, a galaxy
(by its number) or one of these systems (prompt_block / apply).
"""
import json
import os
import re

from . import galaxy

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "planets")


INFO_KEYS = ("escape_speed_kms", "breathable")          # written by galaxy.to_data for reading; worked out again


def clean(name):
    return re.sub(r"[^a-z0-9_-]+", "_", str(name or "").strip().lower()).strip("_")[:48]


def path_of(name):
    return os.path.join(DIR, clean(name) + ".json")


def names():
    if not os.path.isdir(DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(DIR) if f.endswith(".json") and not f.startswith("."))


def load(name):
    p = path_of(name)
    if not clean(name) or not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def check(data):
    """problems (strings) with a system's data; [] = fine"""
    out = []
    if not isinstance(data, dict):
        return ["the system must be a JSON object {name, star, planets}"]
    if not clean(data.get("name")):
        out.append("the system needs a \"name\"")
    pl = data.get("planets")
    if not isinstance(pl, list) or not pl:
        out.append("\"planets\" must be a list with at least one planet")
        return out
    seen = set()
    for i, d in enumerate(pl):
        if not isinstance(d, dict):
            out.append(f"planet {i + 1} is not an object")
            continue
        nm = str(d.get("name") or "").strip()
        if not nm:
            out.append(f"planet {i + 1} needs a \"name\"")
        elif nm.lower() in seen:
            out.append(f"two planets are called '{nm}'")
        seen.add(nm.lower())
        odd = [k for k in d if k not in galaxy.DATA_KEYS and k not in INFO_KEYS]
        if odd:
            out.append(f"planet '{nm or i + 1}': unknown key(s) {', '.join(odd)} (ignored)")
        try:
            galaxy.from_data(_with_star(d, data))
        except Exception as ex:                                     # noqa: BLE001
            out.append(f"planet '{nm or i + 1}': {ex}")
    return out


def save(data):
    """-> (name, problems). Saves even with small problems (unknown keys); refuses broken data."""
    probs = check(data)
    hard = [p for p in probs if "unknown key" not in p]
    if hard:
        return None, probs
    os.makedirs(DIR, exist_ok=True)
    nm = clean(data["name"])
    data = dict(data, name=nm)
    with open(path_of(nm), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    return nm, probs


def delete(name):
    p = path_of(name)
    if clean(name) and os.path.exists(p):
        os.remove(p)
        return True
    return False


def _with_star(d, sysdata):
    d = dict(d)
    if "star" not in d and isinstance(sysdata.get("star"), dict):
        d["star"] = sysdata["star"]
    return d


def planets_of(sysdata):
    """[(planet data, planet dict)] of a system, in order"""
    out = []
    for d in sysdata.get("planets") or []:
        if isinstance(d, dict):
            try:
                out.append((d, galaxy.from_data(_with_star(d, sysdata))))
            except Exception:                                       # noqa: BLE001
                continue
    return out


def find_planet(sysname, key):
    """a planet of a saved system by its name (any case) or its number (1, 2 ...); None if not there"""
    data = load(sysname)
    if not data:
        return None
    pl = planets_of(data)
    k = str(key).strip().lower()
    for d, p in pl:
        if str(d.get("name", "")).strip().lower() == k:
            return p
    if k.isdigit() and 1 <= int(k) <= len(pl):
        return pl[int(k) - 1][1]
    return None


def from_star(seed, star_index, name=None):
    """a saved-system dict copied from a star of a galaxy (its planets as data you can then change)"""
    s = galaxy.star(seed, star_index)
    pl = []
    for k in range(1, s["planets"] + 1):
        d = galaxy.to_data(galaxy.planet(seed, star_index, k))
        d.pop("star", None)
        pl.append(d)
    return {"name": clean(name or s["name"]), "about": f"copied from star {star_index} of galaxy {seed}",
            "star": {"name": s["name"], "kind": s["kind"], "colour": s["colour"],
                     "size": round(s["mass"] ** 0.8, 2), "temperature": round(s["temperature"])},
            "planets": pl}


# ---------------------------------------------------------------------------------------------- the video picker
def choices():
    """options for the 🪐 Planets picker of the video page"""
    out = [{"value": "", "label": "None - Earth places only"},
           {"value": "solar", "label": "☀ Our Solar System (real values)"}]
    for n in (42, 7, 2026):
        out.append({"value": f"galaxy:{n}", "label": f"🌌 Galaxy {n} (made by physics rules)"})
    for n in names():
        out.append({"value": f"sys:{n}", "label": f"🪐 {n} (my system)"})
    return out


def _life_line(p):
    from . import alien_life
    life = alien_life.describe(p)
    return f"\n      lives there: {life}" if life else ""


def prompt_block(sel, limit=24):
    """text for the AI prompt: which planets this story may use and how to write them"""
    sel = str(sel or "").strip()
    if not sel:
        return ""
    head = ("PLANETS FOR THIS STORY (the 🪐 Planets choice): scenes may happen on these worlds. A scene on a planet "
            "gets its ground, sky, star, gravity, weather and life by itself - write only the story. To travel, just "
            "put the same people in the next scene on another planet: the rocket trip (lift-off, route map, real "
            "distance and travel time, landing) is added by itself; talk on the way = an item {\"journey\": "
            "{\"by\": \"rocket\", \"lines\": [...]}} between the two scenes.\n")
    if sel == "solar":
        lines = [f"  - \"planet\": \"{n}\": {galaxy.describe(galaxy.solar(n))}" for n in galaxy.SOLAR]
        return head + "Our Solar System (real values) - scene \"planet\": \"<name>\":\n" + "\n".join(lines) + \
            "\n  Earth scenes need no \"planet\" (normal places). Real worlds have no aliens."
    if sel.startswith("galaxy:"):
        try:
            seed = int(sel.split(":", 1)[1])
        except ValueError:
            return ""
        lines, n = [], 0
        for i in range(60):
            s = galaxy.star(seed, i)
            for k in range(1, s["planets"] + 1):
                p = galaxy.planet(seed, i, k)
                if not (p["life"] or p["gas"] or p["rings"] or p["surface"] in ("lava", "ice") or k == 1):
                    continue
                lines.append(f"  - \"star\": {i}, \"planet\": {k}: {galaxy.describe(p)}" + _life_line(p))
                n += 1
                if n >= limit:
                    break
            if n >= limit:
                break
        return head + (f"Galaxy {seed} - put settings \"galaxy\": {seed}, \"rules\": 2; a scene on a planet has \"star\": <i>, "
                       f"\"planet\": <k> (or words: \"planet\": \"a warm planet with water\"):\n") + "\n".join(lines)
    if sel.startswith("sys:"):
        nm = clean(sel[4:])
        data = load(nm)
        if not data:
            return ""
        st = data.get("star") or {}
        lines = [f"  - \"planet\": \"{d.get('name')}\": {galaxy.describe(p)}" + _life_line(p)
                 for d, p in planets_of(data)]
        about = f" ({data['about']})" if data.get("about") else ""
        return head + (f"The planet system '{nm}'{about}, star {st.get('name', '?')} - put settings "
                       f"\"planet_system\": \"{nm}\"; a scene on a planet has \"planet\": \"<its name>\":\n") + \
            "\n".join(lines)
    return ""


def apply(story, sel):
    """after the AI wrote the story: make sure its settings point at the chosen planets"""
    sel = str(sel or "").strip()
    if not sel or not isinstance(story, dict):
        return story
    stt = story.setdefault("settings", {})
    if sel.startswith("galaxy:"):
        try:
            stt.setdefault("galaxy", int(sel.split(":", 1)[1]))
        except ValueError:
            pass
    elif sel.startswith("sys:"):
        stt.setdefault("planet_system", clean(sel[4:]))
    return story
