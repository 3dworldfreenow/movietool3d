"""Continuity check (like a film's script supervisor): things that change between scenes without a reason.

Advice only - never an error. Checks:
  time       the day goes backwards (night -> morning) with no line telling us it's the next day
  props      someone ends a scene holding something, and the next scene with them has it gone / with someone else
  broken     an object that broke is whole again later (same id, no repair)
  weather    it stops raining between two scenes in the same place at the same time of day
"""
TIME_ORDER = {"morning": 0, "day": 1, "sunset": 2, "evening": 3, "night": 4}
NEXT_DAY = ("next day", "next morning", "tomorrow", "morning", "later", "days later", "week", "अगले दिन", "सुबह",
            "कल ", "दिन बाद", "हफ्ते", "subah", "agle din")


def _bg(sc):
    b = sc.get("background") or {}
    return b if isinstance(b, dict) else {}


def _text_of(sc):
    out = []
    for e in sc.get("events", []) or []:
        if isinstance(e, dict):
            for k, v in e.items():
                if k.startswith(("say", "narrate", "caption")) and isinstance(v, str):
                    out.append(v.lower())
    if sc.get("narration"):
        out.append(str(sc["narration"]).lower())
    return " ".join(out)


def check(P):
    data = P.data
    scenes = [s for s in data.get("scenes", []) if isinstance(s, dict)]
    notes = []
    # -- time of day
    for i in range(1, len(scenes)):
        a, b = _bg(scenes[i - 1]), _bg(scenes[i])
        ta, tb = TIME_ORDER.get(a.get("time", "day")), TIME_ORDER.get(b.get("time", "day"))
        if ta is not None and tb is not None and tb < ta:
            said = _text_of(scenes[i]) + " " + _text_of(scenes[i - 1])[-200:]
            if not any(k in said for k in NEXT_DAY):
                notes.append(f"scene {i + 1}: it is {b.get('time', 'day')} again after {a.get('time')} in scene {i} - "
                             "add a line or caption like \"Next morning...\" so the audience knows time passed")
        if a.get("preset") == b.get("preset") and a.get("time") == b.get("time"):
            ra = a.get("weather") in ("rain", "storm")
            rb = b.get("weather") in ("rain", "storm")
            cleared = any(isinstance(e, dict) and e.get("weather") == "clear" for e in scenes[i - 1].get("events", []) or [])
            if ra and not rb and not cleared:
                notes.append(f"scene {i + 1}: same place and time as scene {i}, but the rain has stopped - "
                             "add {\"weather\": \"clear\", \"fade\": 3} at the end of scene " + str(i))
    # -- props held at the end of a scene, and broken objects
    tls = [it.scene for it in P.items if it.kind == "scene"]
    broken = {}
    for n, sc in enumerate(tls):
        end = max(0.0, sc.duration - 0.05)
        for pid, pr in sc.props.items():
            if getattr(pr, "vtype", None):
                continue
            try:
                st, _ = pr.at(end)
            except Exception:
                continue
            is_broken = hasattr(pr, "broken_at") and pr.broken_at(end) is not None
            if st[0] == "held" and n + 1 < len(tls) and not is_broken:
                who = st[1]
                nxt = tls[n + 1]
                if who in nxt.tracks:
                    p2 = nxt.props.get(pid)
                    if p2 is None:
                        notes.append(f"scene {n + 2}: {sc.tracks[who].cdef.name} was holding '{pid}' at the end of "
                                     f"scene {n + 1}, but it is gone - add it with \"held_by\": \"{who}\" (or drop it first)")
                    else:
                        s2, _ = p2.at(0)
                        if s2[0] == "held" and s2[1] != who:
                            notes.append(f"scene {n + 2}: '{pid}' jumped from {sc.tracks[who].cdef.name} to "
                                         f"{nxt.tracks[s2[1]].cdef.name if s2[1] in nxt.tracks else s2[1]}")
            if hasattr(pr, "broken_at") and pr.broken_at(end) is not None:
                broken[pid] = n + 1
        for pid, at in list(broken.items()):
            if at < n + 1 and pid in sc.props and sc.props[pid].broken_at(0.0) is None and not getattr(
                    sc.props[pid], "vtype", None):
                notes.append(f"scene {n + 1}: '{pid}' broke in scene {at} but is whole again - use another id "
                             f"or add \"broken\": true")
                broken.pop(pid)
    return notes
