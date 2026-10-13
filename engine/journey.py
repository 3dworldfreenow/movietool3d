"""The journey between two places: "they drove to the jungle" SHOWS the drive (10-20 s) instead of jumping there.

Found by itself: a scene ends with a vehicle driving off and the next scene is another place where the same
people / vehicle are -> a journey scene is put between them. Or written in the story:

    a scene item       {"journey": {"by": "car", "seconds": 15, "via": ["fields", "river", "hills"],
                                    "sign": "जंगल 5 km", "later": "2 घंटे बाद...",
                                    "lines": [{"who": "ram", "say": "..."}]}}
    or on a scene      "journey_before": {...} / true
    story setting      "journey": false (never) | true (default: found by itself) | 12 (seconds)

The journey: the car leaving, a drone shot over the road while the land changes from the first place to the
next (houses -> fields -> trees ...), inside the car with the friends, a road sign board, then arriving.

🚀 Space: when the next scene is on another planet (or "by": "rocket"), the journey is a rocket trip
(engine/spacetrip.py): lift-off on the first planet, the route map + space (the old planet shrinking, the new one
growing, the real distance and travel time), then landing on the new one. Found by itself when the same people
are in both scenes (not in a physics lesson); "journey": false = never.
"""
import copy
import random

DEFAULT_SECONDS = 14.0

KIND_WORDS = [
    ("snow", ("snow", "ice", "himalaya")),
    ("desert", ("desert", "dune", "thar", "rajasthan")),
    ("beach", ("beach", "sea", "coast", "rameshwaram")),
    ("hills", ("mountain", "hill", "pahad", "pahadi", "valley", "kishkindha")),
    ("forest", ("jungle", "forest", "bamboo", "garden", "park", "panchavati", "ashok_vatika", "zoo")),
    ("village", ("village", "farm", "homestead", "ashram", "gaon", "mustard", "field")),
    ("town", ("street", "market", "road", "city", "tea_stall", "school", "station", "hospital", "palace",
              "haveli", "temple", "office", "fair", "ground")),
]
THINGS = {
    "town": ["house_3d", "shop_3d", "building_3d", "lamp_3d", "stall_3d", "tree_round_3d"],
    "village": ["hut_3d", "house_3d", "haystack_3d", "well_3d", "handpump_3d", "tree_round_3d", "banyan_3d"],
    "fields": ["crops_3d", "crops_3d", "haystack_3d", "fence_3d", "tree_round_3d"],
    "forest": ["banyan_3d", "palm_3d", "tree_round_3d", "bush_3d", "bush_3d", "rock_3d", "pine_3d"],
    "hills": ["pine_3d", "pine_3d", "rock_3d", "tree_round_3d", "bush_3d"],
    "desert": ["cactus_3d", "rock_3d", "mudhouse_desert_3d", "cactus_3d"],
    "snow": ["pine_3d", "pine_3d", "rock_3d"],
    "beach": ["palm_3d", "palm_3d", "beach_umbrella_3d", "rock_3d"],
    "river": ["palm_3d", "tree_round_3d", "bush_3d", "rock_3d"],
}
FRONT_OK = ("bush_3d", "crops_3d", "fence_3d", "rock_3d", "cactus_3d")     # low things that may pass in front
GAP = {"forest": 190, "hills": 260, "town": 330, "village": 360, "fields": 300, "desert": 420, "snow": 300,
       "beach": 380, "river": 300}
NAMES = {"forest": ("जंगल", "Jungle"), "hills": ("पहाड़", "Hills"), "village": ("गाँव", "Village"),
         "town": ("शहर", "Town"), "desert": ("रेगिस्तान", "Desert"), "snow": ("बर्फ़ीली वादी", "Snow Valley"),
         "beach": ("समुद्र तट", "Beach"), "fields": ("खेत", "Fields"), "river": ("नदी", "River")}
LATER = {"hi": "कुछ देर बाद...", "en": "A little later..."}
WATER_VEHICLES = ("boat", "rowboat", "fishing_boat", "sailboat", "ship", "paper_boat")


def kind_of(bg):
    """a scene background -> town / village / forest / hills / desert / snow / beach"""
    tries = [str(bg.get(k, "")) for k in ("preset", "type", "region", "far")] if isinstance(bg, dict) else [str(bg or "")]
    for raw in tries:                                   # the place's own name first, then its region
        raw = raw.lower()
        for k, words in KIND_WORDS:
            if raw and any(w in raw for w in words):
                return k
    return "village"


def _preset(bg):
    return str((bg.get("preset") or bg.get("type") or "") if isinstance(bg, dict) else (bg or "")).lower()


def _drive_off(sc):
    """(vehicle id, riders) when the scene ends with a vehicle driving away, else (None, [])"""
    evs = [e for e in sc.get("events", []) or [] if isinstance(e, dict)]
    vid, riders = None, []
    for e in evs:
        v = e.get("vehicle")
        if isinstance(v, str) and str(e.get("do", "")).lower() in ("ride", "get_in", "board", "sit_in"):
            if e.get("who") and e["who"] not in riders:
                riders.append(e["who"])
    for e in reversed(evs[-6:]):
        v = e.get("vehicle")
        if isinstance(v, str) and str(e.get("do", "drive")).lower() in ("drive", "go", "move", "sail", "row"):
            vid = v
            break
    for c in sc.get("characters", []) or []:
        if isinstance(c, dict) and c.get("in") == vid and c.get("id") not in riders:
            riders.append(c["id"])
    return vid, riders


def _arrives(sc, vid):
    """the next scene has the same vehicle, or people sitting in it"""
    if any(isinstance(v, dict) and v.get("id") == vid for v in sc.get("vehicles", []) or []):
        return True
    return any(isinstance(c, dict) and c.get("in") == vid for c in sc.get("characters", []) or [])


def make(a, b, spec=None, lang="en", index=0):
    """The journey scene between scene a and scene b (dicts). spec = the story's journey wishes (dict)."""
    spec = dict(spec or {})
    secs = max(6.0, min(30.0, float(spec.get("seconds", DEFAULT_SECONDS))))
    vid, riders = _drive_off(a)
    vspec = None
    for v in (a.get("vehicles", []) or []) + (b.get("vehicles", []) or []):
        if isinstance(v, dict) and (vid is None or v.get("id") == vid):
            vspec = dict(v)
            vid = v.get("id")
            break
    by = str(spec.get("by") or (vspec or {}).get("type") or "car").lower()
    if vspec is None:
        vid = vid or "journey_vehicle"
        vspec = {"id": vid, "type": {"bus": "bus_3d", "jeep": "jeep_3d", "bike": "bicycle_3d", "cycle": "bicycle_3d",
                                     "auto": "auto_rickshaw_3d", "boat": "boat_3d"}.get(by, "car_3d")}
    if not riders:
        riders = [c["id"] for c in (b.get("characters", []) or []) if isinstance(c, dict) and c.get("in") == vid]
    if spec.get("who"):
        riders = list(spec["who"]) if isinstance(spec["who"], (list, tuple)) else [spec["who"]]
    water = any(w in str(vspec.get("type", "")).lower() for w in WATER_VEHICLES) or by in WATER_VEHICLES
    ka, kb = kind_of(a.get("background")), kind_of(b.get("background"))
    via = spec.get("via")
    if isinstance(via, str):
        via = [via]
    if not via:
        via = [ka] + (["fields"] if "fields" not in (ka, kb) and not water else []) + [kb]
    via = [str(v).lower() for v in via]
    via = [("forest" if v in ("jungle", "trees") else "hills" if v in ("mountains", "mountain") else v) for v in via]
    if via[0] != ka:
        via = [ka] + via
    if via[-1] != kb:
        via = via + [kb]
    speed = 430.0 if not water else 170.0
    L = max(3600.0, min(9000.0, speed * secs * 0.92 + 900))
    bga = a.get("background") if isinstance(a.get("background"), dict) else {"preset": a.get("background", "")}
    bgb = b.get("background") if isinstance(b.get("background"), dict) else {"preset": b.get("background", "")}
    road = "tar" if "town" in (ka, kb) else ("sand" if "desert" in (ka, kb) else "dirt")
    bg = {"preset": "river" if water else "plain", "code3d": False,
          "time": bgb.get("time") or bga.get("time") or "day",
          "weather": bgb.get("weather") or bga.get("weather") or "clear",
          "season": bgb.get("season") or bga.get("season") or "summer",
          "far": bgb.get("far") or ("mountains" if kb in ("hills", "snow") else "hills"),
          "birds": True}
    for k in ("region",):
        if bgb.get(k):
            bg[k] = bgb[k]
    if not water:                                        # a road along the way (tar near towns, else a mud track)
        bg["road"] = {"z0": 190, "z1": 430, "style": road}
        bg["ground"] = {"desert": "sand", "snow": "snow", "beach": "sand"}.get(kb, "grass")
    rng = random.Random(f"journey{index}{_preset(bga)}{_preset(bgb)}")
    props = []
    wts = [1.0] * len(via)
    wts[-1] = 1.6                                         # the place they go to fills the last part of the road
    edges, acc = [], 0.0
    for w_ in wts:
        acc += w_
        edges.append(acc / sum(wts) * L)
    from . import images
    ok = {}

    def have(t):
        if t not in ok:
            ok[t] = bool(images.exists(t))
        return ok[t]
    x = 350.0
    n = 0
    while x < L - 250:
        k = via[next((i_ for i_, e_ in enumerate(edges) if x < e_), len(via) - 1)]
        pool = [t for t in THINGS.get(k, THINGS["village"]) if have(t)] or [t for t in THINGS["forest"] if have(t)]
        if not pool:
            break
        sides = ("back", "back", "back", "front") if k in ("forest", "hills", "snow") else ("back", "back", "front")
        for side in sides:
            t = rng.choice(pool)
            if side == "front":
                if t not in FRONT_OK or rng.random() < 0.55:
                    continue
                z = rng.uniform(-170, -60)
            else:
                z = rng.uniform(560, 1000) if rng.random() < 0.55 else rng.uniform(1050, 2200)
            n += 1
            props.append({"id": f"_road_{n}", "type": t, "x": round(x + rng.uniform(-60, 60), 1), "z": round(z, 1),
                          "_dressing": True})
        x += GAP.get(k, 320) * rng.uniform(0.7, 1.25)
    music = b.get("music") or a.get("music")
    v = dict(vspec)
    v["x"], v["z"] = 260.0, 300.0
    v.pop("to", None)
    S = secs
    ev = [{"camera": "follow", "target": vid, "cut": True, "at": 0.0, "duration": round(S * 0.22, 2)},
          {"vehicle": vid, "do": "drive", "to": round(L - 380, 1), "duration": round(S, 2),
           "at": 0.05},
          {"camera": "drone", "target": vid, "cut": True, "at": round(S * 0.22, 2), "duration": round(S * 0.26, 2)}]
    t_in = S * 0.48
    if riders:
        ev.append({"camera": "inside", "target": vid, "cut": True, "at": round(t_in, 2), "duration": round(S * 0.2, 2)})
    else:
        ev.append({"camera": "track", "target": vid, "cut": True, "at": round(t_in, 2), "duration": round(S * 0.2, 2)})
    tt = t_in + 0.4
    for ln in spec.get("lines", []) or []:                 # small talk on the way (the story's own lines)
        if isinstance(ln, dict) and ln.get("who") and (ln.get("say") or ln.get("narrate")):
            e2 = dict(ln)
            e2["at"] = round(tt, 2)
            ev.append(e2)
            tt += 2.6
    hi = str(lang).lower().startswith("hi")
    sign = spec.get("sign")
    if sign is None and spec.get("sign", True) is not False:
        nm = NAMES.get(kb, ("", kb.title()))
        sign = f"{nm[0] if hi else nm[1]} {rng.choice((3, 5, 8))} km"
    t_sign = S * 0.68
    ev.append({"camera": "track", "target": vid, "cut": True, "at": round(t_sign, 2), "duration": round(S * 0.17, 2)})
    if sign:
        ev.append({"text": str(sign), "style": "sign", "at": round(t_sign + 0.3, 2), "duration": round(S * 0.17, 2)})
    ev.append({"camera": "establishing", "cut": True, "at": round(S * 0.85, 2), "duration": round(S * 0.15 + 0.6, 2)})
    later = spec.get("later")
    if later is None and (bga.get("time") and bgb.get("time") and bga.get("time") != bgb.get("time")):
        later = LATER["hi" if hi else "en"]
    if later:
        ev.append({"text": str(later), "style": "time", "at": round(S * 0.86, 2), "duration": 2.4})
    if not riders:
        chars = []
    else:
        chars = [{"id": r, "in": vid} for r in riders]
    out = {"id": f"journey_{index}", "_journey": True, "background": bg, "width": round(L), "vehicles": [v],
           "characters": chars, "props": props, "events": ev, "tail": 0.6, "show_mentioned": False,
           "lived_in": False}
    if music:
        out["music"] = music
    for k in ("palette",):
        if b.get(k):
            out[k] = b[k]
    return out


PLANET_KEYS = ("planet", "star", "galaxy", "planet_system")
SPACE_BY = ("rocket", "spaceship", "space", "shuttle", "spacecraft")


def _where(sc, settings):
    """which world a scene is on: None = Earth places, else a key of its planet"""
    pv = sc.get("planet", settings.get("planet"))
    if pv is None or pv is False or str(pv).lower() in ("earth", "prithvi"):
        return None
    import json
    return json.dumps([sc.get(k, settings.get(k)) for k in PLANET_KEYS], sort_keys=True, default=str)


def _planet(sc, settings):
    if _where(sc, settings) is None:
        return None
    from . import galaxy
    try:
        return galaxy.resolve(settings, sc)
    except Exception:                                              # noqa: BLE001
        return None


def _people(sc):
    return [c["id"] for c in (sc.get("characters") or []) if isinstance(c, dict) and c.get("id")
            and not str(c["id"]).startswith("creature_")]


def make_space(a, b, spec=None, settings=None, lang="en", index=0):
    """the rocket trip between scene a and scene b: [lift-off, the trip, landing] scenes"""
    from . import spacetrip
    spec, settings = dict(spec or {}), settings or {}
    secs = max(8.0, min(30.0, float(spec.get("seconds", 16.0))))
    pa, pb = _planet(a, settings), _planet(b, settings)
    R = spacetrip.route(pa, pb, a, b, settings)
    if spacetrip.wants_black_hole(spec):                        # ⚫ the way goes past a black hole
        R["bh"] = spacetrip.bh_pass(R, spec, settings)
        if "seconds" not in spec:
            secs = 26.0
    riders = spec.get("who")
    riders = (list(riders) if isinstance(riders, (list, tuple)) else [riders]) if riders else \
        [c for c in _people(a) if c in _people(b)] or _people(b)[:2]
    rid = "journey_rocket"
    rocket = {"id": rid, "type": "rocket", "x": 1200, "z": 320, "text": str(spec.get("name") or "")[:12]}
    hi = str(lang).lower().startswith("hi")
    here = {k: a[k] for k in PLANET_KEYS + ("background", "palette", "time") if k in a}
    there = {k: b[k] for k in PLANET_KEYS + ("background", "palette", "time") if k in b}
    t_lift = secs * 0.3
    lift = dict(here, id=f"journey_{index}_liftoff", _journey=True, life=False, show_mentioned=False,
                lived_in=False, vehicles=[rocket], characters=[{"id": riders[0], "in": rid}] if riders else [],
                tail=0.2, events=[
                    {"camera": "wide", "cut": True, "at": 0.0, "duration": t_lift},
                    {"text": "3… 2… 1…" if not hi else "3… 2… 1…", "style": "title", "at": 0.2, "duration": 1.6},
                    {"sfx": "rocket", "at": 1.5},
                    {"vehicle": rid, "to": [1200, 3200], "duration": max(3.0, t_lift - 1.6), "at": 1.6}])
    t_trip = secs * 0.45
    ev = [{"space_trip": R, "at": 0.0, "duration": round(t_trip, 2)},
          {"sfx": "engine", "at": 0.3}]
    tt = t_trip * 0.42
    for ln in spec.get("lines", []) or []:                          # talk on the way
        if isinstance(ln, dict) and ln.get("who") and (ln.get("say") or ln.get("narrate")):
            e2 = dict(ln)
            e2["at"] = round(tt, 2)
            ev.append(e2)
            tt += 2.8
    trip = {"id": f"journey_{index}_space", "_journey": True, "background": {"preset": "space", "time": "night"},
            "characters": [{"id": r, "x": 900 + 160 * k, "z": 200} for k, r in enumerate(riders)], "events": ev,
            "show_mentioned": False, "lived_in": False, "tail": 0.0, "music": b.get("music") or a.get("music") or "mystery"}
    t_land = secs * 0.25
    land = dict(there, id=f"journey_{index}_landing", _journey=True, life=False, show_mentioned=False,
                lived_in=False, vehicles=[dict(rocket, y=3200)], characters=[{"id": riders[0], "in": rid}] if riders else [],
                tail=0.3, events=[
                    {"camera": "wide", "cut": True, "at": 0.0, "duration": t_land + 0.5},
                    {"sfx": "rocket", "at": 0.0},
                    {"vehicle": rid, "to": [1200, 0], "duration": max(2.5, t_land - 0.6), "at": 0.1},
                    {"text": R["to"], "style": "title", "at": round(max(2.6, t_land - 0.4), 2), "duration": 1.8}])
    return [lift, trip, land]


def add(scenes, settings, lang="en", log=None):
    """scenes (the story's list) -> a new list with journey scenes put in. Each original scene keeps its number
    in "_orig" (the hook and "render scene N" still mean the story's own scenes)."""
    want = settings.get("journey", True)
    if want in (False, "off", "no", "none", 0):
        return [dict(s, _orig=i) if isinstance(s, dict) else s for i, s in enumerate(scenes)]
    base = {}
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        base["seconds"] = float(want)
    elif isinstance(want, dict):
        base.update(want)
    out, orig_i, pending = [], 0, None
    real = [s for s in scenes if isinstance(s, dict) and not (set(s) <= {"journey", "id"} and "journey" in s)]
    for s in scenes:
        if not isinstance(s, dict):
            out.append(s)
            continue
        if "journey" in s and "events" not in s and "background" not in s:      # a journey written as its own item
            pending = s["journey"] if isinstance(s["journey"], dict) else {}
            continue
        prev = next((x for x in reversed(out) if isinstance(x, dict) and not x.get("_journey")), None)
        js = None
        if prev is not None:
            jb = s.get("journey_before")
            if pending is not None or jb:
                js = dict(base, **(pending or {}), **(jb if isinstance(jb, dict) else {}))
            elif want not in (False,) and _where(prev, settings) != _where(s, settings) and \
                    set(_people(prev)) & set(_people(s)) and str(settings.get("physics", "")).lower() != "real":
                js = dict(base, by="rocket")                       # the same people, another planet: they flew
            elif want not in (False,):
                vid, _r = _drive_off(prev)
                if vid and _arrives(s, vid) and _preset(prev.get("background")) != _preset(s.get("background")):
                    js = dict(base)
        space = js is not None and prev is not None and (
            str(js.get("by", "")).lower() in SPACE_BY or _where(prev, settings) != _where(s, settings))
        if space:
            try:
                trip = make_space(prev, s, js, settings, lang, len(out))
                out.extend(trip)
                if log:
                    log(f"journey: rocket trip {trip[1]['events'][0]['space_trip']['from']} -> "
                        f"{trip[1]['events'][0]['space_trip']['to']} added before scene {orig_i + 1}")
            except Exception as ex:                    # noqa: BLE001 - never stop a story for this
                if log:
                    log(f"rocket trip before scene {orig_i + 1} skipped ({ex})")
            js = None
        if js is not None and prev is not None:
            try:
                j = make(prev, s, js, lang, len(out))
                out.append(j)
                if log:
                    log(f"journey: {kind_of(prev.get('background'))} -> {kind_of(s.get('background'))} "
                        f"({j['events'][1]['duration']:.0f} s drive) added before scene {orig_i + 1}")
            except Exception as ex:                    # noqa: BLE001 - never stop a story for this
                if log:
                    log(f"journey before scene {orig_i + 1} skipped ({ex})")
        pending = None
        s2 = copy.copy(s)
        s2["_orig"] = orig_i
        orig_i += 1
        out.append(s2)
    _ = real
    return out
