"""Variety guard: remembers every story you make and warns when a new one is too similar.

YouTube (July 2026) does not monetise "generic, repetitive or template-based" videos, while a series with
the same characters and *distinct storylines* is fine. This checks the storyline, places and title of a new
story against your previous episodes (stored in cache/episodes.json).
"""
import json
import os
import re
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "cache", "episodes.json")
STOP = set("""a an the and or but so to of in on at for with from by is are was were be been it its this that
these those he she they them his her their we you i me my your our us not no yes do did does have has had will
would can could just very too then than there here what when where who how all some any one two three said says
say let lets go going went come came get got up down out into over about like okay ok oh hey hi""".split())


def _load():
    try:
        with open(DB, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save(items):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(items[-300:], f, ensure_ascii=False, indent=1)


def _words(text):
    return [w for w in re.findall(r"[a-zA-Zऀ-ॿ']+", str(text).lower()) if w not in STOP and len(w) > 2]


def fingerprint(data):
    texts, places, species, actions = [], [], set(), []
    chars = data.get("characters", {}) or {}
    if isinstance(chars, list):
        chars = {c.get("id", str(i)): c for i, c in enumerate(chars)}
    for c in chars.values():
        if isinstance(c, dict) and c.get("species"):
            species.add(str(c["species"]).lower())
    for sc in data.get("scenes", []) or []:
        bg = sc.get("background", "park")
        places.append(str(bg.get("preset", "park") if isinstance(bg, dict) else bg).lower())
        if sc.get("narration"):
            texts.append(str(sc["narration"]))
        for e in sc.get("events", []) or []:
            if not isinstance(e, dict):
                continue
            for k in ("narrate", "say"):
                if e.get(k):
                    v = e[k]                             # a line may be one text or one per language
                    texts.extend([v] if isinstance(v, str) else [str(x) for x in (v.values() if isinstance(v, dict)
                                                                                   else v if isinstance(v, list) else [v])])
            if e.get("do"):
                actions.append(str(e["do"]).lower())
    words = _words(" ".join(texts))
    shingles = sorted({" ".join(words[i:i + 3]) for i in range(max(0, len(words) - 2))})
    return {
        "title": data.get("title", ""),
        "words": sorted(set(words)),
        "shingles": shingles,
        "places": places,
        "species": sorted(species),
        "summary": summarize(data),
    }


def summarize(data):
    """One line for the AI prompt: title + first narration/dialogue."""
    first = ""
    for sc in data.get("scenes", []) or []:
        for e in sc.get("events", []) or []:
            if isinstance(e, dict) and (e.get("narrate") or e.get("say")):
                first = e.get("narrate") or e.get("say")
                break
        if first:
            break
    places = ", ".join(dict.fromkeys(
        (sc.get("background", {}).get("preset", "") if isinstance(sc.get("background"), dict) else str(sc.get("background", "")))
        for sc in data.get("scenes", []) or []))
    return f"{data.get('title', 'untitled')} ({places}) - {first[:110]}"


def _jac(a, b):
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(fp, other):
    story = 0.55 * _jac(fp["shingles"], other["shingles"]) * 2.2 + 0.45 * _jac(fp["words"], other["words"])
    story = min(story, 1.0)
    places = _jac(fp["places"], other["places"])
    title = _jac(_words(fp["title"]), _words(other["title"]))
    return round(100 * (0.62 * story + 0.23 * places + 0.15 * title))


def check(data, exclude_title=None, threshold=55):
    """-> (max_score, closest_title, list_of_warnings)"""
    fp = fingerprint(data)
    best, best_t = 0, None
    for ep in _load():
        if exclude_title and ep.get("title") == exclude_title:
            continue
        s = similarity(fp, ep)
        if s > best:
            best, best_t = s, ep.get("title")
    warns = []
    if best >= threshold:
        warns.append(f"variety: this story is {best}% similar to your episode '{best_t}'. "
                     f"Change the problem, places or twist so YouTube sees it as a new storyline.")
    elif best >= threshold - 15:
        warns.append(f"variety (info): {best}% similar to '{best_t}' - OK, but consider a fresher twist.")
    return best, best_t, warns


def remember(data, path=None):
    items = [e for e in _load() if e.get("title") != data.get("title")]
    fp = fingerprint(data)
    fp.update(path=path or "", time=time.strftime("%Y-%m-%d %H:%M"))
    items.append(fp)
    _save(items)


def recent_summaries(n=15):
    return [e.get("summary") or e.get("title") for e in reversed(_load()[-n:])]
