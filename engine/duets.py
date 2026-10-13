"""💞 Two people together: the moves that need BOTH bodies - a hug, a kiss, holding hands, a couple dance, a proposal,
lifting someone (in the arms, overhead, on the shoulders), throwing them, and a real fight (punch / slap / kick ->
the other is hit, blocks, or is knocked out).

    {"who": "raju", "do": "hug", "target": "priya"}
    {"who": "raju", "do": "kiss", "target": "priya", "on": "cheek | forehead | hand | lips"}
    {"who": "raju", "do": "hold_hands", "target": "priya"}            {"who": "raju", "do": "dance_with", "target": "priya", "twirl": true}
    {"who": "raju", "do": "propose", "target": "priya", "prop": "ring"}
    {"who": "bheem", "do": "lift", "target": "kallu", "how": "arms | overhead | shoulders", "to": {"x": 900}}
    {"who": "bheem", "do": "throw", "target": "kallu", "distance": 400}
    {"who": "bheem", "do": "fight", "target": "kallu", "moves": ["punch", "slap", "kick"], "rounds": 3, "knockout": true}
    {"who": "bheem", "do": "punch | slap | uppercut | kick", "target": "kallu"}           (one blow; "block": true = blocked)

The timeline (engine/timeline.py) calls handle() before its other people actions. Both people are walked face to
face at the right distance for the move (the one who acts walks up), both get their part at the same moment,
the taller one bends to the shorter one, and the sounds / icons / impacts are added.
"""
import math

from .poses import ACTIONS
from .realworld import G_U

WORDS = {
    "hug": "hug", "embrace": "hug", "hug_tight": "hug", "cuddle": "hug", "gale_milo": "hug",
    "kiss": "kiss", "peck": "kiss", "kiss_cheek": "kiss", "kiss_forehead": "kiss", "kiss_hand": "kiss",
    "kiss_lips": "kiss", "smooch": "kiss", "chumma": "kiss",
    "hold_hands": "hold_hands", "hold_hand": "hold_hands", "take_hands": "hold_hands", "haath_pakdo": "hold_hands",
    "dance_with": "dance_with", "couple_dance": "dance_with", "slow_dance": "dance_with", "dance_together": "dance_with",
    "waltz": "dance_with",
    "propose": "propose", "propose_marriage": "propose", "kneel_propose": "propose", "go_down_on_knee": "propose",
    "lift": "lift", "pick_up": "lift", "lift_up": "lift", "carry_person": "lift", "carry_in_arms": "lift",
    "carry": "lift", "hold": "lift", "pick": "lift", "lift_overhead": "lift", "put_on_shoulders": "lift",
    "piggyback": "lift", "uthao": "lift",
    "throw": "throw", "toss": "throw", "hurl": "throw", "fling": "throw", "throw_person": "throw", "pheko": "throw",
    "fight": "fight", "brawl": "fight", "fist_fight": "fight", "beat_up": "fight", "maar_peet": "fight",
    "punch": "blow", "slap": "blow", "uppercut": "blow", "hook": "blow", "jab": "blow", "kick": "blow",
    "thappad": "blow", "ghoonsa": "blow", "hit_person": "blow", "smack": "blow",
}
HOW = {"arms": "bridal", "bridal": "bridal", "in_arms": "bridal", "princess": "bridal", "overhead": "overhead",
       "over_head": "overhead", "above_head": "overhead", "up": "overhead", "shoulders": "shoulders",
       "on_shoulders": "shoulders", "shoulder": "shoulders", "piggyback": "shoulders"}
PERSON_H = 300.0                                      # a grown-up is ~300 story units tall (engine/realworld.py M)
SCULPT_BIG = 0.3                                      # sculpted people stand ~1.3x the rig (engine/sculpt_rig.py k)


def _human(tr):
    return tr is not None and tr.cdef.kind == "human"


def _height(tr):
    return PERSON_H * float(getattr(tr.cdef, "scale", 1.0) or 1.0)


def _gap(a, b, base):
    """centre-to-centre distance for a move, grown for big / chubby bodies"""
    s = (a.cdef.scale + b.cdef.scale) / 2.0
    extra = 0.0
    for t_ in (a, b):
        sp = getattr(t_.cdef, "spec", None) or {}
        if sp.get("look3d") == "sculpt":
            s *= 1.0 + SCULPT_BIG / 2.0                # (a sculpted body is sized by its legs: bigger than the rig)
        card = sp.get("sculpt") if isinstance(sp.get("sculpt"), dict) else sp
        if str(card.get("build", card.get("body", ""))).lower() in ("chubby", "fat", "heavy", "big", "round", "stocky"):
            extra += 14.0
    return base * s + extra


def _lean_for(me, other):
    """the taller one bends to the shorter one: degrees of extra lean"""
    dh = _height(me) - _height(other)
    return max(0.0, min(28.0, dh / max(_height(other), 1.0) * 70.0))


def _meet(tl, me, other, gap, t, run=False):
    """walk `me` up to `other`, face to face at `gap` (the other turns to face). -> the time they are there"""
    mx, ox, oz = me.x_at(t), other.x_at(t), other.z_at(t)
    side = -1 if mx < ox else 1                      # come from the side I am on
    if abs(mx - ox) < 1:
        side = -me.last_facing()
    goal = ox + side * gap
    if abs(goal - mx) > 22 or abs(me.z_at(t) - oz) > 25:
        t = tl._add_action(me, "run" if run else "walk", {"to": {"x": round(goal), "z": round(oz)}}, t, None)
    return t


def _both(tl, me, other, a_me, a_other, t, dur, e_me=None, e_other=None, emotion=None):
    e1 = dict(e_me or {}, facing=other.cdef.id, duration=dur)
    e2 = dict(e_other or {}, facing=me.cdef.id, duration=dur)
    end1 = tl._add_action(me, a_me, e1, t, emotion)
    end2 = tl._add_action(other, a_other, e2, t, None)
    return max(end1, end2)


def handle(tl, tr, raw, e, start, emotion):
    """-> the end time, or None (not a two-person move: the timeline carries on as before)"""
    move = WORDS.get(raw)
    if move is None or not _human(tr):
        return None
    me = tr.cdef.id
    tgt = tl._who_target(e, me) or (e.get("with") if e.get("with") in tl.tracks else None)
    other = tl.tracks.get(tgt) if tgt else None
    if not _human(other) or other is tr:
        if move == "blow" and raw in ("punch", "slap", "uppercut", "hook", "jab", "thappad", "ghoonsa", "smack"):
            # a blow at nobody (a punch at the air / a bag): just the move
            return tl._add_action(tr, "slap" if raw in ("slap", "thappad", "smack") else "punch",
                                  dict(e, move=_blow_kind(raw)), start, emotion or "angry")
        return None
    if move in ("lift", "throw") and other.cdef.age in ("baby", "toddler") and move == "lift":
        return None                                  # babies: the baby carry (engine/timeline.py _baby_carry)
    fn = {"hug": _hug, "kiss": _kiss, "hold_hands": _hold_hands, "dance_with": _dance, "propose": _propose,
          "lift": _lift, "throw": _throw, "fight": _fight, "blow": _blow}[move]
    return fn(tl, tr, other, raw, e, start, emotion)


# ---------------------------------------------------------------------------- affection and romance
def _hug(tl, me, other, raw, e, t, emotion):
    t = _meet(tl, me, other, _gap(me, other, 60.0), t, run=bool(e.get("run")))
    dur = float(e.get("duration", 2.8))
    end = _both(tl, me, other, "hug_pair", "hug_pair", t, dur, {"_lean": _lean_for(me, other)},
                {"_lean": _lean_for(other, me)}, emotion)
    if emotion not in ("sad", "crying"):
        me.icons.append((t + 0.4, "heart"))
        tl.effects.append(dict(start=t + 0.5, kind="hearts", who=me.cdef.id, dur=min(dur, 2.0)))
    return end


def _kiss(tl, me, other, raw, e, t, emotion):
    on = str(e.get("on") or {"kiss_forehead": "forehead", "kiss_hand": "hand", "kiss_lips": "lips"}.get(raw, "cheek"))
    on = on if on in ("cheek", "forehead", "hand", "lips") else "cheek"
    t = _meet(tl, me, other, _gap(me, other, 120.0 if on == "hand" else 66.0), t)
    dur = float(e.get("duration", 2.0))
    end = _both(tl, me, other, "kiss", "kissed", t, dur, {"on": on, "_lean": _lean_for(me, other)},
                {"on": on, "_lean": _lean_for(other, me)}, emotion)
    tl.sfx.append((t + dur * 0.35, "kiss", 0.7, me.cdef.id))
    other.icons.append((t + dur * 0.45, "blush"))
    tl.effects.append(dict(start=t + dur * 0.35, kind="hearts", who=other.cdef.id, dur=1.6))
    return end


def _hold_hands(tl, me, other, raw, e, t, emotion):
    t = _meet(tl, me, other, _gap(me, other, 96.0), t)
    dur = float(e.get("duration", 2.5))
    return _both(tl, me, other, "hold_hands", "hold_hands", t, dur, {"_lean": _lean_for(me, other)},
                 {"_lean": _lean_for(other, me)}, emotion)


def _dance(tl, me, other, raw, e, t, emotion):
    t = _meet(tl, me, other, _gap(me, other, 74.0), t)
    dur = float(e.get("duration", 5.0))
    tw = (dur * 0.45, dur * 0.45 + 1.0) if e.get("twirl", True) else None
    end = _both(tl, me, other, "couple_dance", "couple_dance", t, dur, {"_role": "lead", "_lean": _lean_for(me, other)},
                {"_role": "follow", "_twirl": tw, "_lean": _lean_for(other, me)}, emotion)
    me.icons.append((t + 0.5, "music"))
    return end


def _propose(tl, me, other, raw, e, t, emotion):
    t = _meet(tl, me, other, _gap(me, other, 125.0), t)
    dur = float(e.get("duration", 3.2))
    e1 = {"facing": other.cdef.id, "duration": dur}
    if e.get("prop"):
        e1["prop"] = e["prop"]
    end = tl._add_action(me, "kneel_propose", e1, t, emotion or "happy")
    tl._add_action(other, "overjoyed", {"facing": me.cdef.id, "duration": dur * 0.75}, t + dur * 0.25, None)
    other.icons.append((t + dur * 0.3, "heart"))
    tl.sfx.append((t + dur * 0.28, "magic", 0.5, me.cdef.id))
    tl.effects.append(dict(start=t + dur * 0.35, kind="hearts", who=other.cdef.id, dur=2.0))
    return end


# ---------------------------------------------------------------------------- lifting and throwing people
def _carried_by(tl, other, t):
    m = other.mounted_at(t)
    return m.cdef.id if m is not None else None


def _lift(tl, me, other, raw, e, t, emotion, how=None):
    from .timeline import Segment
    how = how or HOW.get(str(e.get("how") or e.get("on") or ""), None) or \
        {"lift_overhead": "overhead", "put_on_shoulders": "shoulders", "piggyback": "shoulders"}.get(raw, "bridal")
    if _carried_by(tl, other, t) != me.cdef.id:
        t = _meet(tl, me, other, _gap(me, other, 52.0), t)
        dur = 1.1
        tl._add_action(me, "lift_person", {"facing": other.cdef.id, "how": how, "duration": dur}, t, emotion)
        f = 1 if other.x_at(t) >= me.x_at(t) else -1
        seg = Segment("mount", other.actions.get("carried") or ACTIONS["carried"], t + dur * 0.55, 0.6,
                      me.x_at(t), me.x_at(t), f, {"_mount": me.cdef.id, "_carry": how,
                                                   "_struggle": bool(e.get("struggle"))})
        other.segments.append(seg)
        other.segments.sort(key=lambda s_: s_.start)
        tl.sfx.append((t + dur * 0.5, "whoosh", 0.4, me.cdef.id))
        if how == "overhead":
            me.icons.append((t + dur * 0.6, "anger"))
        t += dur
    if "to" in e or "by" in e:                        # carry them somewhere
        t = tl._add_action(me, "walk", {k: v for k, v in e.items() if k in ("to", "by", "speed", "duration")}, t, None)
    return t


def _throw(tl, me, other, raw, e, t, emotion):
    """lift (overhead, if not held yet), heave, and the other flies a real ballistic arc and lands hard"""
    from .timeline import Segment
    if _carried_by(tl, other, t) != me.cdef.id:
        t = _lift(tl, me, other, "lift_overhead", {}, t, emotion, how="overhead")
    dur = 1.0
    tl._add_action(me, "throw_person", {"duration": dur}, t, emotion or "angry")
    rel = t + dur * 0.5
    f = me.facing_at(rel) or 1
    x0, y0 = me.saddle_at(rel)
    s_ = me.cdef.scale
    d = float(e.get("distance", 380.0)) * s_
    # real physics: launch at 35 degrees from the release height y0; the speed that lands it d away (no air drag
    # for a body over a few metres): v^2 = g d^2 / (2 cos^2(th) (y0 + d tan(th)))
    th = math.radians(float(e.get("angle", 35.0)))
    g = G_U
    v = math.sqrt(g * d * d / (2.0 * math.cos(th) ** 2 * max(1.0, y0 + d * math.tan(th))))
    T = d / (v * math.cos(th))
    fly = {"y0": y0 * 0.75, "vy": v * math.sin(th), "g": g, "spin": 360.0 if T > 0.6 else 180.0}
    seg = Segment("flung", ACTIONS["flung"], rel, T, x0, x0 + f * d, f, {"_fly": fly}, "scared")
    other.segments.append(seg)
    other.segments.sort(key=lambda s_: s_.start)
    land = rel + T
    tl._add_action(other, "fall", {"duration": 1.0}, land, "sad")
    other.icons.append((land + 0.1, "stars"))
    tl.sfx.append((rel, "whoosh", 0.8, me.cdef.id))
    tl.sfx.append((land, "thud", 0.9, other.cdef.id))
    tl._impact(land, other.cdef.id, size=1.3)
    return max(t + dur, land + 1.0)


# ---------------------------------------------------------------------------- fights
def _blow_kind(raw):
    return {"slap": "slap", "thappad": "slap", "smack": "slap", "uppercut": "uppercut", "hook": "hook",
            "kick": "kick"}.get(raw, "jab")


def _strike(tl, me, other, kind, t, emotion, react="hit", last=False):
    """one blow and the answer: the blow lands ~0.33 s in; the other is hit (head snaps), blocks, or goes down"""
    aname = {"slap": "slap", "kick": "kick"}.get(kind, "punch")
    dur = ACTIONS[aname].dur
    tl._add_action(me, aname, {"facing": other.cdef.id, "move": kind, "duration": dur}, t, emotion or "angry")
    hit = t + dur * (0.5 if aname != "kick" else 0.55)
    tl.sfx.append((t + dur * 0.25, "whoosh", 0.5, me.cdef.id))
    if react == "block":
        tl._add_action(other, "block", {"facing": me.cdef.id, "duration": 0.7}, hit - 0.15, "angry")
        tl.sfx.append((hit, "thud", 0.4, other.cdef.id))
        return t + dur
    if last:                                         # the knockout: off the feet, flat on the back, stars
        tl._add_action(other, "knocked_out", {"facing": me.cdef.id, "duration": 1.2}, hit, "sad")
        other.icons.append((hit + 0.7, "stars"))
        tl.sfx.append((hit, "slap" if kind == "slap" else "punch", 1.0, other.cdef.id))
        tl.sfx.append((hit + 0.65, "thud", 0.9, other.cdef.id))
        tl._impact(hit + 0.65, other.cdef.id, size=1.2)
        if isinstance(getattr(tl, "camera", None), list):              # the knockout blow shakes the picture
            tl.camera.append((hit, {"type": "punch", "intensity": 0.5, "duration": 0.3}))
        return hit + 1.2
    tl._add_action(other, "hit", {"facing": me.cdef.id, "duration": 0.7, "_by": kind}, hit - 0.03, "angry")
    tl.sfx.append((hit, "slap" if kind == "slap" else "punch", 0.9, other.cdef.id))
    return t + dur


def _blow(tl, me, other, raw, e, t, emotion):
    t = _meet(tl, me, other, _gap(me, other, 105.0 if raw != "kick" else 120.0), t)
    return _strike(tl, me, other, _blow_kind(raw), t, emotion, "block" if e.get("block") else "hit",
                   bool(e.get("knockout")))


def _fight(tl, me, other, raw, e, t, emotion):
    """a real exchange: both square up, then blow after blow (the first one attacks, the other answers every other
    round unless "one_sided"), blocks now and then, and "knockout": true ends it with the other one down"""
    t = _meet(tl, me, other, _gap(me, other, 105.0), t, run=bool(e.get("run")))
    moves = e.get("moves") or ["jab", "hook", "slap", "kick", "uppercut"]
    moves = [m if m in ("jab", "hook", "uppercut", "slap", "kick", "punch") else "jab" for m in moves]
    rounds = max(1, min(12, int(e.get("rounds", 4))))
    one_sided = bool(e.get("one_sided"))
    tl._add_action(me, "fight", {"facing": other.cdef.id, "duration": 0.6}, t, "angry")
    tl._add_action(other, "fight", {"facing": me.cdef.id, "duration": 0.6}, t, "angry")
    t += 0.6
    for r in range(rounds):
        att, dfn = (me, other) if (one_sided or r % 2 == 0) else (other, me)
        kind = moves[r % len(moves)]
        kind = "jab" if kind == "punch" else kind
        last = bool(e.get("knockout", True)) and r == rounds - 1 and att is me
        react = "block" if (r % 3 == 1 and not last) else "hit"
        t = _strike(tl, att, dfn, kind, t, None, react, last) + 0.12
    if e.get("knockout", True) and not (one_sided or (rounds - 1) % 2 == 0):
        t = _strike(tl, me, other, "uppercut", t, None, "hit", True)
    return t
