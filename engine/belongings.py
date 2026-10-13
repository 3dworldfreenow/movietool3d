"""Things remember where they are from scene to scene - like a real home.

A lota picked up from the table and carried out of the house is still in Golu's hand when the next scene starts at
the chowk; if he gives it to Kallu, Kallu has it after that. A glass put on the kitchen platform is on the platform
the next time the story comes back into that house, and the table no longer has it. Things put in a bag stay in
the bag (not seen) until someone takes them out.

The project calls  inject(scene, memory, ...)  before it makes a scene's timeline (adding what people carry and what
was moved in this place) and  record(timeline, memory, ...)  after (where everything ended up).
Story setting  "remember_things": false  turns it off.
"""

KEEP = ("type", "scale", "height", "flip", "image")


def place_key(sc):
    """Which place a scene is in: its background (and its spot on a map: "at")."""
    bg = sc.get("background", "park")
    pre = bg.get("preset", bg.get("type", bg.get("image", ""))) if isinstance(bg, dict) else bg
    at = sc.get("at")
    if not at and isinstance(sc.get("map"), dict):
        at = sc["map"].get("at")
    return f"{str(pre).lower()}@{at}" if at else str(pre).lower()


def people_in(sc):
    ids = set()
    for c in sc.get("characters") or []:
        cid = c.get("id") if isinstance(c, dict) else c
        if cid:
            ids.add(str(cid))
    for e in sc.get("events") or []:
        if isinstance(e, dict) and e.get("who"):
            ids.add(str(e["who"]))
    return ids


def new_memory():
    return {"places": {}, "held": {}}


def inject(sc, mem, key):
    """-> the scene with the remembered things added to its "objects" (the story's own objects always win)."""
    places, held = mem["places"].get(key) or {}, mem["held"]
    if not places and not held:
        return sc
    objs = [dict(o) if isinstance(o, dict) else {"id": o, "type": o} for o in (sc.get("objects") or [])]
    mine = {o.get("id") for o in objs}
    added = []
    here = people_in(sc)
    for who in sorted(here):                             # what the people in this scene are carrying
        for pid, ent in (held.get(who) or {}).items():
            if pid not in mine:
                added.append(dict({k: v for k, v in ent.items() if k in KEEP}, id=pid, held_by=who, _kept=True))
                mine.add(pid)
    for pid, ent in places.items():                      # what was moved / taken away in this place
        if pid in mine:
            continue
        if ent.get("gone"):
            added.append({"id": pid, "gone": True})
        else:
            o = dict({k: v for k, v in ent.items() if k in KEEP}, id=pid, x=ent["x"], z=ent["z"], _kept=True)
            if ent.get("y"):
                o["y"] = ent["y"]
            if ent.get("in"):
                o["in"] = ent["in"]
            added.append(o)
        mine.add(pid)
    if not added:
        return sc
    return dict(sc, objects=objs + added)


def record(tl, mem, key):
    """After a scene: who holds what now, and where the moved things of this place are."""
    end = float(getattr(tl, "duration", 0.0) or 0.0) + 1.0
    places = mem["places"].setdefault(key, {})
    held = mem["held"]
    for pid, p in tl.props.items():
        if getattr(p, "vtype", None):
            continue                                     # vehicles have their own story
        s, _ = p.at(end)
        moved = len(p.states) > 1 or p.spec.get("_kept")
        ent = {k: p.spec[k] for k in KEEP if k in p.spec}
        ent["type"] = p.type
        for who in list(held):                           # nobody else holds it any more
            if pid in held[who] and not (s[0] == "held" and s[1] == who):
                held[who].pop(pid, None)
        if s[0] == "held" and s[1] in tl.tracks:
            held.setdefault(s[1], {})[pid] = ent
            if p.spec.get("_place") or pid in places or p.spec.get("_kept"):
                places[pid] = {"gone": True}             # it left with them: not in this place any more
            continue
        if not moved:
            continue
        x, y, _f = p.pos(end)
        ent.update(x=round(float(x), 1), z=round(float(p.z_at(end)), 1))
        if y:
            ent["y"] = round(float(y), 1)
        if s[0] == "in":
            ent["in"] = s[1]
        places[pid] = ent
