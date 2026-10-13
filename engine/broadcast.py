"""📰 The news of every planet, for everyone: one feed the whole server shares (planets/.shared/_news.json).

What goes in: what explorers live through (a kill and the family left behind, a death, a starving herd, a flood, a
landing on a new world) and what the planets do on their own (a herd migrates, a drought) - each with the planet
(its `ref`, so anyone can open it) and the spot where it happened, so a reader can 🚀 join there.

Small and safe: the newest 300 stories kept, each ≤ 300 characters, at most 12 per explorer per hour (no flooding
the feed), the same story from the same planet only once; nothing personal but the shown name."""
import json
import os
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "planets", ".shared", "_news.json")
KEEP, PER_HOUR, TEXT = 300, 12, 300
_lock = threading.Lock()
_RATE = {}                                                    # who -> [times of their last stories]


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def _save(items):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH + ".tmp", "w", encoding="utf-8") as f:
        json.dump(items, f, separators=(",", ":"), ensure_ascii=False)
    os.replace(PATH + ".tmp", PATH)


def _num(v, d=0.0):
    try:
        v = float(v)
        return v if abs(v) < 1e7 else d
    except (TypeError, ValueError):
        return d


def add(text, planet, ref=None, at=None, who=None, kind="walk"):
    """one story; -> True when it went in (False: empty, a repeat, or too many from this explorer this hour)"""
    from . import wordfilter
    text = wordfilter.clean(" ".join(str(text or "").split())[:TEXT], TEXT)          # 🛡 no bad words in anyone's news
    who = wordfilter.clean(who, 40) if who else who
    if not text:
        return False
    now = time.time()
    if who:
        ts = [t for t in _RATE.get(who, []) if now - t < 3600]
        if len(ts) >= PER_HOUR:
            _RATE[who] = ts
            return False
        _RATE[who] = ts + [now]
    ref_s = json.dumps(ref or {}, separators=(",", ":"))
    item = {"t": int(now), "text": text, "planet": str(planet or "?")[:80], "ref": ref if isinstance(ref, dict) and len(ref_s) < 600 else {},
            "who": str(who or "")[:40], "kind": str(kind)[:12]}
    if isinstance(at, (list, tuple)) and len(at) == 2:
        item["at"] = [round(_num(at[0]), 1), round(_num(at[1]), 1)]
    with _lock:
        items = _load()
        if any(i.get("text") == item["text"] and i.get("planet") == item["planet"] and now - i.get("t", 0) < 86400 for i in items[-60:]):
            return False                                     # (the same story from the same planet: once a day)
        items.append(item)
        _save(items[-KEEP:])
    return True


def latest(n=60, planet=None, after=0):
    items = [i for i in _load() if i.get("t", 0) > after and (not planet or i.get("planet") == planet)]
    return list(reversed(items[-n:]))
