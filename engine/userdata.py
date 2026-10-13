"""👤 Each person's own saved data - small, numbers only, at most 30 MB a person (it never comes near that).

    where     users/<account>/walk.json - one small record per planet they have walked on:
                at      [x, z] where they last stood (they come back to the same spot)
                hp      their health then
                trust   creature ids that trust them (they can ride them) - at most 40
                seen    creature kinds they have met (their journal) - at most 60
                n       counters: metres walked, stones thrown, visits, last visit time
    rules     only numbers and short lists - no pictures, no land, no simulation (a planet's life is worked out on the
              server only when someone arrives - engine/ecosystem.py - and only its numbers are kept in between)
    quota     MAX_BYTES per person; if a write would go over, the planets visited longest ago are dropped first
    traffic   the walk asks for ONE planet's record when it starts (a few hundred bytes) and sends small changes every
              30 s and when you leave
"""
import json
import os
import re
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "users")
MAX_BYTES = 30 * 1024 * 1024
MEM_BYTES = 10 * 1024 * 1024                 # 💾 of that: the land's memory (what the animals and plants were doing where you walked)
LOG_BYTES = 4 * 1024 * 1024                  # 📖 of that: the explorer's logbook (discoveries, points, missions) - engine/logbook.py
MIND_BYTES = 10 * 1024 * 1024                # 🧠 of that: your memory of the journey (people, crew, reputations, decisions) - engine/minds.py
BACKUP_BYTES = 2 * 1024 * 1024              # 💾 of that: your home's backup, locked with your passphrase (the server cannot open it)
REC_BYTES = MAX_BYTES - MEM_BYTES - LOG_BYTES - MIND_BYTES - BACKUP_BYTES   # (the per-planet records: a few hundred bytes each - 4 MB is thousands of planets)
MAX_TRUST, MAX_SEEN, MAX_PLANETS, MAX_BOND = 40, 60, 5000, 80
MAX_EDITS, MAX_CRATERS = 400, 60
NEWS_PER_PLANET, NEWS_SHOWN = 2, 5          # 📰 news kept per planet, and how many the bell shows            # what you changed on a planet: broken rocks, felled plants, craters
_lock = threading.RLock()                    # (re-entrant: saving a record also updates the shared land)


def _safe(user):
    """the folder name of an account: the name itself when it is plain (a-z 0-9 _, ≤ 20); an email or a longer name
    gets a short fingerprint added, so two different accounts can never share a folder"""
    raw = str(user or "").strip().lower()
    u = re.sub(r"[^a-z0-9_]", "", raw)[:20]
    if not u and not raw:
        raise ValueError("no account")
    if u != raw:
        import hashlib
        u = (u[:12] or "user") + "_" + hashlib.sha1(raw.encode()).hexdigest()[:7]
    return u


def is_admin(user):
    """the admin (and the one person of a home install with the login off) gets the big allowance"""
    if user == "local":
        return True
    try:
        from .auth import _admin_name
        return user == _admin_name()
    except Exception:                                             # noqa: BLE001
        return False


def limits(user):
    """-> (record bytes, memory bytes): 16 + 10 MB (+ 4 MB logbook) for everyone, 100 + 400 MB (500 MB) for the admin"""
    return (100 * 1024 * 1024, 400 * 1024 * 1024) if is_admin(user) else (REC_BYTES, MEM_BYTES)


def _path(user):
    return os.path.join(DIR, _safe(user), "walk.json")


def _load(user):
    try:
        with open(_path(user), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(user, d):
    p = _path(user)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    raw = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    rec_max = limits(user)[0]
    while len(raw.encode()) > rec_max and len(d) > 1:                 # over the quota: forget the oldest planets first
        oldest = min(d, key=lambda k: (d[k].get("n") or {}).get("t", 0))
        d.pop(oldest)
        raw = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(raw)
    os.replace(tmp, p)
    return len(raw)


def _key(planet):
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(planet or ""))[:120]


def _num(v, lo=-1e7, hi=1e7):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(lo, min(hi, v)) if v == v else 0.0


def get(user, planet):
    """the one planet's record (or an empty one) - what the walk needs when it starts"""
    r = _load(user).get(_key(planet)) or {}
    return {"at": r.get("at"), "hp": r.get("hp"), "trust": r.get("trust", []), "seen": r.get("seen", []), "n": r.get("n", {}), "bond": r.get("bond", {}),
            "edits": _merge_edits(r.get("edits", []), shared_get(planet).get("edits", [])), "bio": r.get("bio")}


def put(user, planet, ch):
    """merge a small change: {at:[x,z], hp, trust_add:[ids], trust_del:[ids], seen_add:[kinds], edits_add:[[kind, x, z, a, b]], walked, thrown}"""
    k = _key(planet)
    if not k:
        raise ValueError("no planet")
    with _lock:
        d = _load(user)
        r = d.get(k) or {"trust": [], "seen": [], "n": {}}
        if isinstance(ch.get("at"), (list, tuple)) and len(ch["at"]) == 2:
            r["at"] = [round(_num(ch["at"][0]), 1), round(_num(ch["at"][1]), 1)]
        if isinstance(ch.get("bio"), (list, tuple)) and len(ch["bio"]) == 4:      # 🎒 water %, food %, bottle L, bag kcal
            r["bio"] = [round(_num(ch["bio"][0], 0, 100), 1), round(_num(ch["bio"][1], 0, 100), 1), round(_num(ch["bio"][2], 0, 1.5), 2), round(_num(ch["bio"][3], 0, 3000))]
        if ch.get("hp") is not None:
            r["hp"] = round(_num(ch["hp"], 0, 100))
        for t in (ch.get("trust_add") or [])[:10]:
            t = str(t)[:24]
            if t not in r["trust"]:
                r["trust"].append(t)
        drop = {str(t)[:24] for t in (ch.get("trust_del") or [])[:10]}
        r["trust"] = [t for t in r["trust"] if t not in drop][-MAX_TRUST:]
        for s in (ch.get("seen_add") or [])[:10]:
            s = str(s)[:24]
            if s not in r["seen"]:
                r["seen"].append(s)
        r["seen"] = r["seen"][-MAX_SEEN:]
        bond = r.get("bond") or {}                                         # 🍖 each animal's memory of you: [feedings, minute of the last]
        for b in (ch.get("bond_set") or [])[:10]:
            if isinstance(b, (list, tuple)) and len(b) == 3:
                bond[str(b[0])[:24]] = [int(_num(b[1], 0, 50)), int(_num(b[2], 0, 1e8))]
        if len(bond) > MAX_BOND:                                           # (the ones you fed longest ago are forgotten first)
            bond = dict(sorted(bond.items(), key=lambda kv: kv[1][1])[-MAX_BOND:])
        r["bond"] = bond
        ed = r.get("edits") or []
        for e in (ch.get("edits_add") or [])[:20]:                         # [kind, x, z, (a, b)] - a few numbers each
            if not isinstance(e, (list, tuple)) or len(e) < 3 or e[0] not in ("rock", "cut", "crater", "gone"):
                continue
            e = [e[0]] + [round(_num(v), 2) for v in list(e[1:5])]
            if e[0] == "crater":
                e[3] = min(max(e[3], 0.5), 6.0)
                e[4] = min(max(e[4], 0.1), 3.0) if len(e) > 4 else 1.0
            ed.append(e)
        if ch.get("edits_add"):
            _shared_edits(planet, [e for e in ed[-20:]])                   # 🌍 the land is the same for everyone: others see it too
        craters = [e for e in ed if e[0] == "crater"][-MAX_CRATERS:]
        r["edits"] = [e for e in ed if e[0] != "crater"][-(MAX_EDITS - len(craters)):] + craters
        if ch.get("pname"):
            r["name"] = str(ch["pname"])[:60]
        news = r.get("news") or []
        for it in (ch.get("news_add") or [])[:5]:                          # 📰 what happened there (kills, deaths, families)
            if isinstance(it, dict) and it.get("text"):
                news.append({"t": int(time.time()), "text": str(it["text"])[:300]})
        r["news"] = news[-NEWS_PER_PLANET:]                                # only the latest: older news is let go
        n = r.get("n") or {}
        n["walked"] = round(n.get("walked", 0) + _num(ch.get("walked"), 0, 1e5))
        n["thrown"] = int(n.get("thrown", 0) + _num(ch.get("thrown"), 0, 1000))
        played, pdays = _num(ch.get("played"), 0, 120), _num(ch.get("pdays"), 0, 50)    # ⏱ time spent here (seconds, planet days)
        n["secs"] = round(n.get("secs", 0) + played)
        n["pdays"] = round(n.get("pdays", 0) + pdays, 3)
        if ch.get("arrive"):
            n["visits"] = int(n.get("visits", 0)) + 1
        n["t"] = int(time.time())
        r["n"] = n
        d[k] = r
        if len(d) > MAX_PLANETS:                                           # (a hard cap on how many planets a person keeps)
            for old in sorted(d, key=lambda q: (d[q].get("n") or {}).get("t", 0))[:len(d) - MAX_PLANETS]:
                d.pop(old)
        size = _save(user, d)
        _profile(user, d, k, played, pdays)
    try:                                                                  # 📰 the same stories go to everyone's news (engine/broadcast.py)
        from . import broadcast
        pname, ref, at, who = r.get("name") or k.rsplit("_", 1)[0], ch.get("ref") if isinstance(ch.get("ref"), dict) else None, r.get("at"), display_name(user)
        if ch.get("arrive") and n.get("visits") == 1:
            broadcast.add(f"🚀 {who} landed on {pname} for the first time", pname, ref, at, who, "landing")
        for it in (ch.get("news_add") or [])[:5]:
            if isinstance(it, dict) and it.get("text"):
                broadcast.add(it["text"], pname, ref, it.get("at") or at, who, "walk")
    except Exception:                                                     # noqa: BLE001  (the news never stops a save)
        pass
    return {"ok": True, "bytes": size, "planets": len(d)}


def usage(user):
    n = 0
    for f in (_path, _mpath):
        try:
            n += os.path.getsize(f(user))
        except OSError:
            pass
    return n


# ---------------------------------------------------------------- 💾 the land's memory (walkmem.json, ≤ 10 MB)
# One small record per piece of land you walked through: {"t": ms, "c": [["kind_n", x, z, dead, hunger, cond, hurt, meat,
# rot, orphan, trust, starved, kind, young], ...], "b": [[x, z, ms] burnt plants]}. Keys "cs:ci,cj" (the
# piece size differs between a phone and a PC). Over 10 MB: the pieces visited longest ago are forgotten first.

def _mpath(user):
    return os.path.join(DIR, _safe(user), "walkmem.json")


def _mload(user):
    try:
        with open(_mpath(user), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _clean_rec(r):
    if not isinstance(r, dict):
        return None
    if r.get("v") != 2:
        return None
    out = {"v": 2, "t": int(_num(r.get("t"), 0, 1e14))}
    c = []
    for row in (r.get("c") or [])[:200]:
        if isinstance(row, (list, tuple)) and len(row) >= 14:
            c.append([re.sub(r"[^0-9_]", "", str(row[0]))[:16]] + [round(_num(v), 2) for v in row[1:14]])
    out["c"] = c
    out["b"] = [[round(_num(a), 2), round(_num(b), 2), int(_num(t, 0, 1e14))] for a, b, t in
                [x for x in (r.get("b") or [])[:200] if isinstance(x, (list, tuple)) and len(x) == 3]]
    return out


def mem_put(user, planet, recs):
    """merge pieces of land {key: record}; keep the whole memory ≤ MEM_BYTES (oldest pieces dropped first)"""
    k = _key(planet)
    if not k or not isinstance(recs, dict):
        raise ValueError("no planet")
    with _lock:
        d = _mload(user)
        pl = d.setdefault(k, {})
        for key, r in list(recs.items())[:60]:
            key = re.sub(r"[^0-9:,\-]", "", str(key))[:24]
            r = _clean_rec(r)
            if key and r is not None:
                pl[key] = r
        raw = json.dumps(d, separators=(",", ":"))
        mem_max = limits(user)[1]
        if len(raw.encode()) > mem_max:
            allk = sorted(((rec.get("t", 0), pk, ck) for pk, p_ in d.items() for ck, rec in p_.items()))
            i = 0
            while len(raw.encode()) > mem_max and i < len(allk):
                for _ in range(50):                                        # forget 50 at a time
                    if i >= len(allk):
                        break
                    _t, pk, ck = allk[i]
                    i += 1
                    d.get(pk, {}).pop(ck, None)
                raw = json.dumps(d, separators=(",", ":"))
        p = _mpath(user)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(raw)
        os.replace(tmp, p)
    _shared_mem(user, planet, recs)
    return {"ok": True, "bytes": len(raw)}


def mem_get(user, planet, x, z, cs, r=700.0):
    """the remembered pieces of land within r metres of (x, z) for this piece size"""
    pl = _mload(user).get(_key(planet)) or {}
    out = {}
    for key, rec in pl.items():
        try:
            c, ij = key.split(":")
            ci, cj = (int(v) for v in ij.split(","))
        except ValueError:
            continue
        if abs(abs(float(c)) - cs) > 0.5:
            continue
        if abs((ci + 0.5) * cs - x) < r and abs((cj + 0.5) * cs - z) < r:
            out[key] = rec
    sh = shared_get(planet)                                                # 🌍 a newer state left by someone else wins
    for key, rec in (sh.get("mem") or {}).items():
        try:
            c, ij = key.split(":")
            ci, cj = (int(v) for v in ij.split(","))
        except ValueError:
            continue
        if abs(abs(float(c)) - cs) > 0.5 or not (abs((ci + 0.5) * cs - x) < r and abs((cj + 0.5) * cs - z) < r):
            continue
        if key not in out or rec.get("t", 0) > out[key].get("t", 0):
            out[key] = rec
    return out


def history(user):
    """👤 your history: the planets you visited (latest first) and the latest news - at most 5, at most 2 per planet"""
    d = _load(user)
    planets, news = [], []
    for k, r in d.items():
        n = r.get("n") or {}
        nm = r.get("name") or k.rsplit("_", 1)[0]
        planets.append({"key": k, "name": nm, "visits": n.get("visits", 0), "walked_m": n.get("walked", 0), "last": n.get("t", 0),
                        "trust": len(r.get("trust", [])), "changes": len(r.get("edits", []))})
        for it in r.get("news", [])[-NEWS_PER_PLANET:]:
            news.append(dict(it, planet=nm))
    planets.sort(key=lambda p: -p["last"])
    news.sort(key=lambda it: -it["t"])
    return {"planets": planets, "news": news[:NEWS_SHOWN], "bytes": usage(user), "limit": sum(limits(user)), "admin": is_admin(user)}


# ---------------------------------------------------------------- 🌍 one land for everyone (planets/.shared/)
# What anyone changes on a planet is seen by everyone who comes to the same place: broken rocks, felled / burnt /
# washed-away plants, craters (edits), and the latest state of the animals there (the land's memory, with who left
# it and when). Per planet ≤ 8 MB (oldest places forgotten first), ≤ 3000 edits.
SHARED_DIR = os.path.join(HERE, "planets", ".shared")
SHARED_BYTES, SHARED_EDITS = 8 * 1024 * 1024, 3000


def _spath(planet):
    return os.path.join(SHARED_DIR, _key(planet) + ".json")


def shared_get(planet):
    try:
        with open(_spath(planet), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _shared_save(planet, d):
    os.makedirs(SHARED_DIR, exist_ok=True)
    raw = json.dumps(d, separators=(",", ":"))
    mem = d.get("mem") or {}
    while len(raw.encode()) > SHARED_BYTES and mem:
        for key in sorted(mem, key=lambda q: mem[q].get("t", 0))[:50]:
            mem.pop(key, None)
        raw = json.dumps(d, separators=(",", ":"))
    tmp = _spath(planet) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(raw)
    os.replace(tmp, _spath(planet))


def _ekey(e):
    return (e[0], round(float(e[1]), 1), round(float(e[2]), 1))


def _merge_edits(a, b):
    seen, out = set(), []
    for e in list(a) + list(b):
        try:
            k = _ekey(e)
        except (TypeError, ValueError, IndexError):
            continue
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out[-SHARED_EDITS:]


def _shared_edits(planet, edits):
    with _lock:
        d = shared_get(planet)
        d["edits"] = _merge_edits(d.get("edits", []), edits)
        _shared_save(planet, d)


def _shared_mem(user, planet, recs):
    who = display_name(user)
    with _lock:
        d = shared_get(planet)
        mem = d.setdefault("mem", {})
        for key, r in list(recs.items())[:60]:
            key = re.sub(r"[^0-9:,\-]", "", str(key))[:24]
            r = _clean_rec(r)
            if key and r is not None and r["t"] >= (mem.get(key) or {}).get("t", 0):
                r["by"] = who
                mem[key] = r
        _shared_save(planet, d)


# ---------------------------------------------------------------- 👥 players: a small public profile each
def _bpath(user):
    return os.path.join(DIR, _safe(user), "homebackup.json")


def backup_put(user, box):
    """💾 keep the locked box (made on the phone: {v, salt, iv, data} in base64) - only its shape is checked"""
    import base64 as _b
    if not isinstance(box, dict) or box.get("v") != 1 or not all(isinstance(box.get(k), str) for k in ("salt", "iv", "data")):
        return {"ok": False, "error": "not a backup"}
    try:
        n = len(_b.b64decode(box["data"], validate=True))
        _b.b64decode(box["salt"], validate=True); _b.b64decode(box["iv"], validate=True)
    except (ValueError, TypeError):
        return {"ok": False, "error": "not a backup"}
    out = {"v": 1, "gz": bool(box.get("gz")), "salt": box["salt"], "iv": box["iv"], "data": box["data"], "t": int(time.time()), "bytes": n}
    with _lock:
        os.makedirs(os.path.dirname(_bpath(user)), exist_ok=True)
        with open(_bpath(user) + ".tmp", "w", encoding="utf-8") as f:
            json.dump(out, f)
        os.replace(_bpath(user) + ".tmp", _bpath(user))
    return {"ok": True, "t": out["t"], "bytes": n}


def backup_get(user):
    try:
        with open(_bpath(user), encoding="utf-8") as f:
            return {"box": json.load(f)}
    except (OSError, ValueError):
        return {"box": None}


_NICKS = {"t": 0.0, "by_user": {}}                     # (the chosen names, read again at most every 30 s)


def _nick_file():
    return os.path.join(DIR, ".nicks.json")


def _nicks():
    import time as _t
    if _t.time() - _NICKS["t"] > 30:
        try:
            with open(_nick_file(), encoding="utf-8") as f:
                _NICKS["by_user"] = json.load(f)
        except (OSError, ValueError):
            _NICKS["by_user"] = {}
        _NICKS["t"] = _t.time()
    return _NICKS["by_user"]


def set_nick(user, nick):
    """✏ the name others see: 2-20 letters, digits, spaces, _ or -; clean words only; nobody else's"""
    import re
    import time as _t
    from . import wordfilter
    n = " ".join(str(nick or "").split())
    if not re.fullmatch(r"[\w \-]{2,20}", n, flags=re.UNICODE) or n.strip("_- ") == "":
        return {"ok": False, "error": "2-20 letters, digits, spaces, _ or -"}
    if wordfilter.clean(n) != n:
        return {"ok": False, "error": "choose a kinder name"}
    with _lock:
        _NICKS["t"] = 0.0
        ix = dict(_nicks())
        if any(v.lower() == n.lower() and k != _safe(user) for k, v in ix.items()):
            return {"ok": False, "error": "someone has that name - try another"}
        ix[_safe(user)] = n
        os.makedirs(DIR, exist_ok=True)
        with open(_nick_file() + ".tmp", "w", encoding="utf-8") as f:
            json.dump(ix, f, ensure_ascii=False)
        os.replace(_nick_file() + ".tmp", _nick_file())
        _NICKS.update(t=_t.time(), by_user=ix)
    return {"ok": True, "name": n}


def auto_named(user):
    """is the name only the login (an email, or a login with a code on its end) - worth choosing a real one?"""
    import re
    return _safe(user) not in _nicks() and ("@" in str(user) or bool(re.search(r"_[0-9a-f]{5,}$", str(user))))


def display_name(user):
    """a name others may see: the one you chose; else an email shows only its first letters"""
    u = str(user or "")
    nk = _nicks().get(_safe(u))
    if nk:
        return nk
    if "@" in u:
        a = u.split("@", 1)[0]
        return (a[:3] + "…") if len(a) > 3 else a[:1] + "…"
    return u[:24]


def _ppath(user):
    return os.path.join(DIR, _safe(user), "profile.json")


def _profile(user, d, planet_key, played, pdays):
    """keep the totals for the players list: time spent (s), planet days, where you are now"""
    try:
        with open(_ppath(user), encoding="utf-8") as f:
            pr = json.load(f)
    except (OSError, ValueError):
        pr = {}
    r = d.get(planet_key) or {}
    pr.update(name=display_name(user), secs=round(pr.get("secs", 0) + played), pdays=round(pr.get("pdays", 0) + pdays, 3),
              planet=r.get("name") or planet_key.rsplit("_", 1)[0], t=int(time.time()), planets=len(d))
    os.makedirs(os.path.dirname(_ppath(user)), exist_ok=True)
    with open(_ppath(user) + ".tmp", "w", encoding="utf-8") as f:
        json.dump(pr, f, separators=(",", ":"))
    os.replace(_ppath(user) + ".tmp", _ppath(user))


_TOP = {"t": 0, "rows": []}


def top_players(n=30):
    """👥 the 30 players who spent the most time on planets: where they are, time spent, planet days (cached 30 s)"""
    if time.time() - _TOP["t"] < 30:
        return _TOP["rows"][:n]
    rows = []
    try:
        names = os.listdir(DIR)
    except OSError:
        names = []
    for nm in names:
        try:
            with open(os.path.join(DIR, nm, "profile.json"), encoding="utf-8") as f:
                pr = json.load(f)
        except (OSError, ValueError):
            continue
        rows.append({"name": pr.get("name", nm), "planet": pr.get("planet", "?"), "secs": pr.get("secs", 0), "pdays": pr.get("pdays", 0),
                     "planets": pr.get("planets", 0), "last": pr.get("t", 0), "online": time.time() - pr.get("t", 0) < 90})
    rows.sort(key=lambda r: -r["secs"])
    _TOP.update(t=time.time(), rows=rows)
    return rows[:n]
