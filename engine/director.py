"""Auto-director: decides the shots like a film director / editor, so every scene looks like a movie
even when the story JSON has few (or no) camera events.

  "settings": {"director": "cinematic"}   default - fills every stretch the story does not direct itself
  "settings": {"director": "full"}        ignores the story's camera moves and directs everything
  "settings": {"director": "off"}         only the story's own camera events
  (also per scene: "director": "...")     "handheld": 0 .. 1  how much the camera breathes (default 0.35)

Grammar it follows:
  * open on an establishing shot (crane down in True 2.5D), end on a crane up / pull back
  * dialogue: two-shot for the first line, then over-the-shoulder / reverse shots that keep the
    180-degree rule, close-ups for strong emotion, low angle for anger / big animals, high angle for fear
  * movement: track alongside a runner, lead someone walking toward the camera, hold wide when
    someone walks away, ride inside a vehicle, whip-pan between people far apart
  * actions: low angle for pushing, tilt up for climbing, push in on discoveries, punch-in on impacts
  * never the same shot twice in a row, shots 1.6 - 6 s, long shots keep drifting slowly
Story camera events always win: the director only fills the gaps around them.
"""
import math

INTENSE = ("angry", "scared", "surprised", "crying", "sad", "shocked", "afraid")
BIG_ANIMALS = ("tiger", "lion", "elephant", "bear", "wolf", "crocodile", "dinosaur", "gorilla", "rhino", "bull")
ACTS = {"push": "low_angle", "pull": "low_angle", "throw": "medium", "open": "push_in", "smash": "medium",
        "hide": "high_angle", "climb": "tilt_up", "perch": "low_angle", "step_up": "medium", "sit_on": "medium",
        "celebrate": "medium", "dance": "medium", "fall": "medium", "pounce": "low_angle", "roar": "low_angle",
        "kick": "medium", "jump": "medium", "cry": "closeup", "scared": "closeup", "surprised": "closeup",
        "hug": "medium", "appear": "push_in", "peek": "closeup", "struggle": "medium"}
IMPACT_SFX = {"crash": ("punch", 1.0), "thunder": ("shake", 0.6), "splash": ("punch", 0.5),
              "thud": ("punch", 0.6), "roar": ("shake", 0.45), "boing": ("punch", 0.4), "stomp": ("shake", 0.5)}
MIN_SHOT = 1.6


def _visible(tl, cid, t):
    try:
        return tl._visible(cid, t)
    except Exception:
        return True


def plan(tl, mode="cinematic", mode3d=False, film3d=False, bg=None):
    """Returns camera commands [(time, cmd)] to add to tl.camera (and removes story moves in "full" mode).
    film3d: the 3D film grammar on top (3D page / "world": "3d") - see _film3d().
    Then the cinematographer (cinema.py) chooses lens, focus, height, angle, moves and foreground for
    every shot - the story's own shots only get the settings they did not give."""
    from . import cinema
    opts = getattr(tl, "cinema", None) or cinema.options({})
    tl.cinema = opts
    tl._bg_preset = str(getattr(bg, "preset", "") or "") + " " + str((getattr(bg, "spec", None) or {}).get("image", ""))
    out = _plan(tl, mode, mode3d)
    if mode3d and cinema.is_feature(opts):
        out = _feature(tl, out)                     # animated-feature layout: every move has a reason
    elif film3d and mode3d:
        out = _film3d(tl, out)
    if str(opts.get("style", "")).lower() in ("off", "none", "simple") or \
            str(mode or "").lower() in ("off", "none", "manual", "false", "no", "simple"):
        return out
    fx = ("shake", "punch", "impact", "pulse", "zoom_pulse", "earthquake", "explosion", "rumble", "vehicle",
          "heartbeat", "rack_focus")
    story = [(t, dict(c, _story=True)) for t, c in tl.camera if c.get("type") not in fx]
    shaped = cinema.shape(tl, story + [(t, c) for t, c in out if c.get("type") not in fx], mode3d, opts, bg)
    tl.camera = [(t, c) for t, c in tl.camera if c.get("type") in fx] + \
        [(t, c) for t, c in shaped if c.get("_story")]
    return [(t, c) for t, c in shaped if not c.get("_story")] + [(t, c) for t, c in out if c.get("type") in fx]


FILM3D_DRIFT = ("left", "in", "right", "in")


def _film3d(tl, out):
    """3D film grammar (how 3D animation layout / game cinematic cameras work - Cinemachine, previs):
      * the camera is never frozen: every auto shot drifts (truck / dolly), because parallax is what shows 3D
      * look room: a single shot puts the subject off-centre, with space in front of the face (rule of thirds)
      * an orbit (arc) on every third longer line and on hero actions - a slow move that reveals the space
      * the 180-degree line is kept by the dialogue coverage (over-shoulder / reverse)"""
    res = []
    n_single = 0
    for t, c in out:
        c = dict(c)
        typ = c.get("type")
        tgt = c.get("target")
        tr = tl.tracks.get(tgt) if tgt else None
        if typ in ("medium", "closeup", "wide", "auto", "over_shoulder", "reverse", "high_angle", "low_angle") \
                and c.get("drift") in (None, "in") and not c.get("_fx"):
            c["drift"] = FILM3D_DRIFT[len(res) % len(FILM3D_DRIFT)]      # trucks left / right show parallax
        if typ in ("medium", "closeup") and tr is not None and "offset" not in c:
            n_single += 1
            try:
                f = tr.facing_at(t + 0.2)
            except Exception:
                f = 0
            if f:
                c["offset"] = (120.0 if typ == "medium" else 70.0) * (1 if f > 0 else -1)
            if typ == "medium" and n_single % 3 == 0:
                c = {"type": "arc", "target": tgt, "amount": 320,
                     "direction": "left" if (n_single // 3) % 2 else "right", "duration": 4.0,
                     "_auto": c.get("_auto", True)}
        res.append((t, c))
    return res


MOTIVE_EMO = ("angry", "scared", "surprised", "crying", "sad", "shocked", "afraid", "thinking", "happy", "laughing")
BIG_PLACES = ("palace", "castle", "fort", "mahal", "hill", "mountain", "sea", "beach", "desert", "kishkindha", "valley",
              "lake", "river", "temple", "ocean", "canyon", "cliff", "snow")


def _feature(tl, out):
    """Animated-feature layout (how Moana / Pixar previs moves the camera):
      * the camera only moves for a reason - a slow dolly in on an emotional or long line, a truck with someone
        walking, an orbit on an arrival or a narration, a crane to open and close; otherwise it holds
      * look room in singles (space in front of the face)
      * no whip pans, dutch tilts or impact shakes (story shots can still ask for them)"""
    res = []
    for t, c in out:
        c = dict(c)
        typ = c.get("type")
        tgt = c.get("target")
        tr = tl.tracks.get(tgt) if tgt else None
        if typ in ("shake", "punch", "impact") and c.get("_auto"):
            continue
        if typ in ("whip", "dutch"):
            c["type"] = typ = "medium" if tr is not None else "wide"
        if typ in ("medium", "closeup", "medium_closeup", "over_shoulder", "reverse", "low_angle", "high_angle", "auto"):
            sp = next((s for s in tl.speeches if s.start - 0.5 <= t <= s.end and s.who in (tgt, c.get("look_at"))),
                      None)
            emo = str(getattr(sp, "emotion", "") or "").lower() if sp else ""
            if sp is not None and (emo in MOTIVE_EMO or sp.dur > 4.5):
                c["drift"] = "in"                     # the line matters: we lean in
            elif c.get("drift") in ("in", "left", "right"):
                c["drift"] = None                     # no reason to move: a locked-off composition
        if typ in ("medium", "closeup", "medium_closeup") and tr is not None and "offset" not in c:
            try:
                f = tr.facing_at(t + 0.2)
            except Exception:
                f = 0
            if f:
                c["offset"] = (110.0 if typ == "medium" else 60.0) * (1 if f > 0 else -1)
        res.append((t, c))
    return res


# ============================================================================ choosing the best shot (score + DP)
BIG_GESTURES = ("point", "wave_off", "beckon", "excited", "explain", "fist", "palms_up")
SIZE = {"auto": 0, "wide": 0, "medium": 2, "over_shoulder": 2, "reverse": 2, "low_angle": 2, "high_angle": 2,
        "medium_closeup": 3, "closeup": 4}


def best_shots(tl, mode3d, feat, humans, x_of, z_of):
    """The best camera shot for every line of dialogue, chosen like a director / editor would - not one rule at a
    time but the whole conversation at once (IEEE "Bridging Script and Animation", auto-cinematography):

      * 3-8 candidate shots per line (two-shot, medium, close-up, over-the-shoulder, reverse, low / high angle)
      * each candidate gets a score: is the speaker visible (nobody standing in front), the right size for what
        happens (a close-up for strong feeling, a two-shot to start a talk, a medium when the hands talk, a wide
        shot when people are far apart), a low angle for a powerful / angry character, a high angle for a scared
        small one
      * each CUT between two shots gets a score too: no jump cuts (same person, nearly the same size), shot /
        reverse-shot pairs are good, the same shot twice in a row is bad
      * dynamic programming (Viterbi) picks the sequence with the best total.
    -> {id(speech): camera command}"""
    from . import cinema
    try:
        from .timeline import _act_prepare
        _act_prepare(tl)
    except Exception:
        pass
    says = [sp for sp in tl.speeches if sp.who in tl.tracks and tl.tracks[sp.who].riding_at(sp.start) is None]
    says.sort(key=lambda sp: sp.start)
    out = {}
    if not says:
        return out
    # conversations: lines with less than 6 s between them
    convs, cur = [], [says[0]]
    for sp in says[1:]:
        if sp.start - cur[-1].end > 6.0:
            convs.append(cur)
            cur = []
        cur.append(sp)
    convs.append(cur)
    for conv in convs:
        prev_spk = None
        beats = []
        for n, sp in enumerate(conv):
            a = sp.who
            t = sp.start
            cands_b = [c for c in humans if c != a and _visible(tl, c, t) and tl.tracks[c].riding_at(t) is None]
            if not cands_b:
                b = None
            elif prev_spk in cands_b and abs(x_of(prev_spk, t) - x_of(a, t)) < 1100:
                b = prev_spk
            else:
                b = min(cands_b, key=lambda c: abs(x_of(c, t) - x_of(a, t)) + 0.8 * abs(z_of(c, t) - z_of(a, t)))
            beats.append((sp, a, b, n))
            prev_spk = a
        table = []
        for sp, a, b, n in beats:
            table.append(_candidates(tl, sp, a, b, n, mode3d, feat, humans, x_of, z_of, cinema))
        # Viterbi
        best = [{k: (u, None) for k, (cmd, u) in enumerate(table[0])}]
        for i in range(1, len(table)):
            row = {}
            same_spk = beats[i][1] == beats[i - 1][1]
            for k, (cmd, u) in enumerate(table[i]):
                sc_, arg = -1e9, None
                for j, (pcmd, _pu) in enumerate(table[i - 1]):
                    v = best[i - 1][j][0] + _cut_score(pcmd, cmd, same_spk)
                    if v > sc_:
                        sc_, arg = v, j
                row[k] = (sc_ + u, arg)
            best.append(row)
        k = max(best[-1], key=lambda kk: best[-1][kk][0])
        picks = []
        for i in range(len(table) - 1, -1, -1):
            picks.append(table[i][k][0])
            k = best[i][k][1]
        picks.reverse()
        for (sp, _a, _b, _n), cmd in zip(beats, picks):
            out[id(sp)] = dict(cmd)
    return out


def _candidates(tl, sp, a, b, n, mode3d, feat, humans, x_of, z_of, cinema):
    t = sp.start
    tr = tl.tracks[a]
    emo = (sp.emotion or tr.mood(t) or "").lower()
    text = str(sp.text).strip()
    words = len(text.split())
    intense = emo in INTENSE or (text.endswith("!") and words <= 6)
    species = str(getattr(tr.cdef, "species", "") or "").lower()
    big = tr.cdef.kind != "human" and any(k in species for k in BIG_ANIMALS)
    power = (feat and cinema.is_power(tr.cdef)) or big
    gest = getattr(sp, "gest", None)
    far = b is not None and abs(x_of(a, t) - x_of(b, t)) > 1000
    xa, za = x_of(a, t), z_of(a, t)
    blocked = any(c != a and _visible(tl, c, t) and z_of(c, t) < za - 40 and abs(x_of(c, t) - xa) < 110
                  for c in humans)                       # someone stands between the camera and the speaker
    cands = [({"type": "medium", "target": a, "drift": "in"}, 1.0),
             ({"type": "closeup", "target": a, "focus_blur": True}, 0.0),
             ({"type": "medium_closeup", "target": a}, 0.3)]
    if b is not None:
        cands += [({"type": "auto", "drift": "in"}, 0.0), ({"type": "over_shoulder", "target": b, "look_at": a}, 0.8)]
        if mode3d:
            cands.append(({"type": "reverse", "target": b, "look_at": a}, 0.6 if za < z_of(b, t) - 60 else -1.5))
    if mode3d:
        cands.append(({"type": "low_angle", "target": a}, -1.0))
        if tr.cdef.scale < 0.9:
            cands.append(({"type": "high_angle", "target": a}, -1.5))
    together = any(o is not sp and o.who != a and o.who in tl.tracks and abs(o.start - sp.start) < 0.6
                   for o in tl.speeches)                 # two people talk at once: show both
    out = []
    for cmd, u in cands:
        typ = cmd["type"]
        if together:
            u += 6.0 if typ == "auto" else -2.0
        if n == 0:                                       # a talk starts: show who is talking to whom
            u += {"auto": 3.0, "medium": 1.0, "over_shoulder": -0.5, "closeup": -2.0, "medium_closeup": -1.0}.get(typ, 0)
        if intense:
            u += {"closeup": 3.0, "medium_closeup": 2.0, "auto": -1.0, "medium": -0.5}.get(typ, 0)
        if emo == "angry" and power and typ == "low_angle":
            u += 4.0
        elif typ == "low_angle" and (emo == "angry" or power) and n > 0:
            u += 1.5
        if emo in ("scared", "afraid") and tr.cdef.scale < 0.9 and typ == "high_angle":
            u += 3.5
        if sp.dur > 4.5:
            u += {"medium": 1.5, "medium_closeup": 1.0, "over_shoulder": 0.8}.get(typ, 0)
        if gest in BIG_GESTURES:                         # the hands talk: keep them in the frame
            u += {"medium": 1.2, "auto": 0.6, "closeup": -1.2}.get(typ, 0)
        if text.endswith("?"):
            u += {"over_shoulder": 1.0, "closeup": 0.4}.get(typ, 0)
        if far:
            u += {"auto": -2.0, "over_shoulder": -1.5, "reverse": -1.0, "medium": 1.0}.get(typ, 0)
        if blocked and typ in ("medium", "closeup", "medium_closeup", "auto", "low_angle"):
            u -= 2.0                                     # the speaker would be hidden behind someone
        if words <= 3 and typ in ("auto",) and n > 0:
            u -= 0.5
        out.append((cmd, u))
    return out


def _cut_score(p, c, same_spk):
    """How good the cut from shot p to shot c is."""
    tp, tc = p.get("type"), c.get("type")
    same_tgt = p.get("target") == c.get("target") and p.get("look_at") == c.get("look_at")
    if same_spk and tp == tc and same_tgt:
        return 1.0                                       # the same person goes on talking: just hold the shot
    if tp == tc and same_tgt:
        return -3.0                                      # the same shot again
    if p.get("target") == c.get("target") and abs(SIZE.get(tp, 2) - SIZE.get(tc, 2)) <= 1 and \
            (p.get("look_at") is None and c.get("look_at") is None):
        return -1.8                                      # a jump cut (same person, nearly the same size)
    if tp in ("over_shoulder", "reverse") and tc in ("over_shoulder", "reverse") and \
            p.get("target") == c.get("look_at") and p.get("look_at") == c.get("target"):
        return 1.6                                       # shot / reverse shot
    if tp == "closeup" and tc == "closeup":
        return -0.4
    if tp == tc:
        return -0.6
    return 0.0


def _plan(tl, mode="cinematic", mode3d=False):
    mode = str(mode or "cinematic").lower()
    if mode in ("off", "none", "manual", "false", "no"):
        return []
    fx_types = ("shake", "punch", "impact", "pulse", "zoom_pulse")
    if mode == "full":
        tl.camera = [(t, c) for t, c in tl.camera if c.get("type") in fx_types]
    user = [(t, c) for t, c in tl.camera if c.get("type") not in fx_types]
    user_fx = [t for t, c in tl.camera if c.get("type") in fx_types]
    dur_all = tl.duration

    def hold_of(c):
        typ = c.get("type")
        d = float(c.get("duration", 0) or 0)
        base = 3.2 if typ in ("push_in", "pull_back", "crane_up", "crane_down", "establishing", "arc") else 2.4
        return max(base, d + 0.8)

    def covered(t):
        for ut, uc in user:
            if ut - 0.7 <= t <= ut + hold_of(uc):
                return True
        return False

    humans = [cid for cid, tr in tl.tracks.items() if not tr.crowd]
    photo = bool(getattr(tl, "photo3d", None))
    from . import cinema
    copts = getattr(tl, "cinema", None) or cinema.options({})
    feat = mode3d and cinema.is_feature(copts)
    spoke = set()

    def min_shot(t):                       # calm = long takes, tension = quick cuts ("pace" in "cinema")
        if copts.get("style") == "off":
            return MIN_SHOT
        try:
            return cinema.min_shot(tl, t, copts)
        except Exception:
            return MIN_SHOT
    out = []
    state = dict(last_t=-99.0, last=None, busy=-1.0, conv_t=-99.0, conv_n=0, prev_speaker=None, ots=0)

    def add(t, cmd, busy=0.0, force=False, wait=0.0):
        """wait: how late the shot may start if the previous one is still too fresh (moves, long lines)."""
        t = max(0.0, t)
        if not force:
            te = max(t, state["last_t"] + min_shot(state["last_t"]), state["busy"] - 0.2)
            if te > t + wait + 1e-6 or covered(te):
                return False
            busy = max(0.0, busy - (te - t))
            t = te
        cmd = dict(cmd)
        prev = state["last"]
        if prev and prev.get("type") == cmd.get("type") and prev.get("target") == cmd.get("target") \
                and cmd["type"] not in ("track", "lead", "inside"):
            if cmd.get("look_at") and cmd["type"] in ("over_shoulder", "reverse"):
                cmd["target"] = cmd["look_at"]          # (the new shot is on the one who talks, not the listener)
            cmd["type"] = {"closeup": "medium", "medium": "closeup", "over_shoulder": "closeup",
                           "reverse": "closeup", "low_angle": "medium", "high_angle": "medium",
                           "wide": "arc" if mode3d else "medium", "push_in": "medium"}.get(cmd["type"], "medium")
            cmd.pop("look_at", None)
            if cmd["type"] == "arc" and not cmd.get("target"):
                cmd["type"] = "wide"
        if photo:                                   # one picture: keep the camera at its own height
            cmd["type"] = {"low_angle": "medium", "high_angle": "medium", "tilt_up": "push_in",
                           "tilt_down": "medium", "establishing": "wide", "crane_up": "pull_back",
                           "crane_down": "wide"}.get(cmd["type"], cmd["type"])
            if cmd["type"] == "wide":
                cmd.setdefault("drift", "in")
        cmd.setdefault("cut", True)
        cmd["_auto"] = True
        out.append((t, cmd))
        state["last_t"], state["last"] = t, cmd
        state["busy"] = max(state["busy"], t + busy)
        return True

    def z_of(cid, t):
        tr = tl.tracks.get(cid)
        return tr.z_at(t) if tr else 0.0

    def x_of(cid, t):
        tr = tl.tracks.get(cid)
        return tr.x_at(t) if tr else 0.0

    def listener(a, t):
        cands = [c for c in humans if c != a and _visible(tl, c, t) and tl.tracks[c].riding_at(t) is None]
        if not cands:
            return None
        if state["prev_speaker"] in cands and abs(x_of(state["prev_speaker"], t) - x_of(a, t)) < 1100:
            return state["prev_speaker"]
        return min(cands, key=lambda c: abs(x_of(c, t) - x_of(a, t)) + 0.8 * abs(z_of(c, t) - z_of(a, t)))

    WIDE = ("establishing", "wide", "auto", "crane_down", "crane_up", "pull_back", "arc")

    def shows(c, who, t):
        """Does shot c (an auto shot) have this character in it?"""
        if not c:
            return False
        if who in (c.get("target"), c.get("look_at")):
            return True
        if c.get("type") in WIDE:
            return True
        if c.get("type") == "over_shoulder" and c.get("target") in tl.tracks and c.get("look_at") is None:
            return False
        return False

    # ---------------------------------------------------------------- beats
    beats = []
    for sp in tl.speeches:
        if sp.who in tl.tracks:
            beats.append((sp.start, 1, "say", sp))
        elif sp.who == "narrator":
            beats.append((sp.start, 3, "narr", sp))
    for cid in humans:
        tr = tl.tracks[cid]
        for s in tr.segments:
            if s.spec.moving and s.dur >= 1.2 and s.action not in ("push", "pull"):
                beats.append((s.start, 2, "move", (cid, s)))
            elif s.action in ACTS and not s.params.get("_exit"):
                beats.append((s.start, 2, "act", (cid, s)))
            elif s.action == "mount":
                beats.append((s.start, 2, "act", (cid, s)))
    for pid, pr in tl.props.items():
        if not pr.vtype:
            continue
        for tt, s in pr.states:
            if s[0] == "move" and s[5] >= 2.5:
                beats.append((tt, 2, "drive", (pid, s[5], abs(s[3] - s[1]))))
    beats.sort(key=lambda b: (b[0], b[1]))

    dp_shots = {}
    if str(copts.get("shots", copts.get("shot_choice", "best"))).lower() not in ("rules", "off", "simple"):
        try:
            dp_shots = best_shots(tl, mode3d, feat, humans, x_of, z_of)
        except Exception:
            dp_shots = {}

    # ---------------------------------------------------------------- opening
    first_user = min([t for t, _ in user], default=99.0)
    if first_user > 0.8:
        first = beats[0][0] if beats else 3.0
        if mode3d:
            d = min(4.0, max(2.5, first + 1.0))
            if feat:                                # a feature lets the place breathe first (bigger for big places)
                pre = str(getattr(tl, "_bg_preset", "") or "").lower()
                big_place = any(k in pre for k in BIG_PLACES)
                d = min(5.5 if big_place else 4.5, max(3.2, first + 1.5))
            add(0.0, {"type": "establishing", "duration": d, "cut": True}, busy=min(d, 3.0), force=True)
        else:
            add(0.0, {"type": "wide", "cut": True, "drift": "in"}, busy=1.5, force=True)

    # ---------------------------------------------------------------- the beats
    for t, _pri, kind, data in beats:
        if kind == "say":
            sp = data
            a = sp.who
            tr = tl.tracks[a]
            if tr.riding_at(t) is not None:                     # riding: stay with the vehicle shot
                continue
            if t - state["conv_t"] > 6.0:
                state["conv_n"] = 0
            state["conv_t"] = sp.end
            b = listener(a, t)
            emo = (sp.emotion or tr.mood(t) or "").lower()
            words = len(str(sp.text).split())
            intense = emo in INTENSE or (str(sp.text).strip().endswith("!") and words <= 6)
            kind_a = tr.cdef.kind
            species = str(getattr(tr.cdef, "species", "") or "").lower()
            big = kind_a != "human" and any(k in species for k in BIG_ANIMALS)
            cmd = None
            first_line = a not in spoke
            spoke.add(a)
            if feat and cinema.is_power(tr.cdef) and (first_line or emo == "angry" or intense) \
                    and emo not in ("scared", "crying", "sad"):
                cmd = {"type": "low_angle", "target": a}   # a king / villain: we look up at them
            elif big and (emo == "angry" or intense):
                cmd = {"type": "low_angle", "target": a}
            elif intense and state["conv_n"] > 0:
                cmd = {"type": "closeup", "target": a, "focus_blur": True}
                if emo in ("scared", "afraid") and tr.cdef.scale < 0.9 and mode3d:
                    cmd = {"type": "high_angle", "target": a}
            elif b is None:
                cmd = {"type": "medium" if state["conv_n"] % 2 == 0 else "closeup", "target": a, "drift": "in"}
            elif state["conv_n"] == 0:
                far = abs(x_of(a, t) - x_of(b, t)) > 900
                cmd = {"type": "medium", "target": a, "drift": "in"} if far else {"type": "auto", "drift": "in"}
            else:
                za, zb = z_of(a, t), z_of(b, t)
                far = abs(x_of(a, t) - x_of(b, t)) > 1000
                state["ots"] += 1
                if far and state["ots"] % 3 == 0 and not feat:
                    cmd = {"type": "whip", "target": a}
                elif state["ots"] % 3 == 2:
                    cmd = {"type": "closeup" if sp.dur < 3.5 else "medium", "target": a, "drift": "in"}
                elif mode3d and za < zb - 60:
                    cmd = {"type": "reverse", "target": b, "look_at": a}
                else:
                    cmd = {"type": "over_shoulder", "target": b, "look_at": a}
            if id(sp) in dp_shots and state["conv_n"] >= 0:
                cmd = dict(dp_shots[id(sp)])                # the best sequence of shots (score + DP)
                if cmd.get("type") in ("over_shoulder", "reverse") and cmd.get("target") != b:
                    if b is None:
                        cmd = {"type": "medium", "target": a, "drift": "in"}
                    else:
                        cmd["target"] = b
            if sp.dur > 4.5 and "drift" not in cmd:
                cmd["drift"] = "in"
            lead_in = 0.28 if (state["conv_n"] > 0 and copts.get("style") != "off") else 0.1   # J-cut
            if not add(t - lead_in, cmd, wait=min(0.9, sp.dur * 0.4)) and not shows(state["last"], a, t):
                # too soon for a new shot, but the shot on screen does not show who talks now: the audience
                # must see the speaker - cut anyway (a little later, never on top of the last cut)
                tf = max(t - lead_in, state["last_t"] + 0.9)
                if tf < sp.end - 0.6 and not covered(tf):
                    add(tf, cmd, force=True)
            react = copts.get("reactions", True) is not False and b is not None and copts.get("style") != "off"
            if react and sp.dur > 4.2 and state["conv_n"] > 0:       # a long line: the listener's face in the middle
                tr_ = t + sp.dur * 0.58
                if add(tr_, {"type": "medium_closeup", "target": b, "_reaction": True}, wait=0.6):
                    add(tr_ + 1.4, {"type": "medium_closeup", "target": a}, wait=0.4)
            elif react and intense and sp.dur < 3.5:                  # a shock: cut to who it hits
                nxt = min((o for o in tl.speeches if o.start > sp.start + 0.05), key=lambda o: o.start, default=None)
                if nxt is None or nxt.start - sp.end > 1.4 or nxt.who == b:   # (not when someone else speaks next)
                    add(sp.end + 0.05, {"type": "closeup", "target": b, "_reaction": True}, wait=0.3)
            state["conv_n"] += 1
            state["prev_speaker"] = a
        elif kind == "narr":
            sp = data
            if sp.dur > 4.0 and mode3d and humans:
                main = min(humans, key=lambda c: z_of(c, t))
                add(t, {"type": "arc", "target": main, "duration": min(sp.dur + 0.5, 8.0),
                        "direction": "right" if len(out) % 2 else "left"}, busy=min(sp.dur, 6.0))
            else:
                add(t, {"type": "wide", "drift": "left" if len(out) % 2 else "right"})
        elif kind == "move":
            cid, s = data
            dx = abs(s.x1 - s.x0)
            z0 = s.z0 if s.z0 is not None else z_of(cid, s.start)
            dz = (s.z1 - z0) if s.z1 is not None else 0.0
            if mode3d and dz < -300 and -dz * 0.8 > dx:            # coming toward the camera
                if z0 > 1400:                                     # seen far away first, then led in
                    t2 = t + min(s.dur * 0.45, 3.0)
                    add(t, {"type": "wide", "drift": "in"}, busy=min(s.dur * 0.4, 3.0), wait=s.dur * 0.2)
                    add(t2, {"type": "lead", "target": cid}, busy=min(s.dur - (t2 - t), 5.0),
                        wait=max(0.0, s.dur * 0.8 - (t2 - t)))
                else:
                    add(t, {"type": "lead", "target": cid}, busy=min(s.dur, 5.0), wait=min(s.dur * 0.5, 3.0))
            elif mode3d and dz > 300 and dz * 0.8 > dx:            # walking away into the distance
                add(t, {"type": "wide" if len(out) % 2 else "high_angle", "target": cid, "drift": "in"},
                    busy=min(s.dur, 4.0), wait=s.dur * 0.4)
            elif dx > 250:
                if s.action in ("run", "gallop") or s.dur > 2.5:
                    add(t, {"type": "track" if mode3d else "follow", "target": cid}, busy=min(s.dur, 5.0),
                        wait=min(s.dur * 0.5, 3.0))
        elif kind == "act":
            cid, s = data
            typ = ACTS.get(s.action, "medium")
            if s.action == "mount":
                typ = "medium"
            if typ in ("low_angle", "high_angle", "tilt_up") and not mode3d:
                typ = "medium" if typ != "tilt_up" else "push_in"
            cmd = {"type": typ, "target": cid}
            if typ == "push_in":
                cmd.update(zoom=1.7, duration=min(2.5, s.dur + 0.6))
            if typ == "tilt_up":
                cmd["duration"] = min(3.0, s.dur + 0.5)
            add(t, cmd, busy=min(s.dur, 3.0) if typ in ("tilt_up", "push_in") else 0.0, wait=min(0.8, s.dur * 0.5))
        elif kind == "drive":
            pid, d, dist = data
            pr = tl.props[pid]
            riders = [c for c in humans if tl.tracks[c].riding_at(t + 0.2) is not None and
                      tl.tracks[c].riding_at(t + 0.2).params.get("_vehicle") == pid]
            if mode3d and dist > 300:
                if add(t, {"type": "track", "target": pid, "zoom": 0.95}, busy=d * 0.45, wait=d * 0.3) and riders \
                        and pr.vtype in ("bus", "car", "jeep", "auto") and d > 3.5:
                    add(t + d * 0.45, {"type": "inside", "target": pid}, busy=d * 0.4,
                        force=not covered(t + d * 0.45))
            elif mode3d:
                add(t, {"type": "wide", "drift": "in"}, busy=d * 0.6)
            else:
                add(t, {"type": "follow", "target": pid}, busy=d)

    # ---------------------------------------------------------------- ending
    if dur_all > 12 and not covered(dur_all - 3.2):
        last_t = max([t for t, _ in out + user], default=0.0)
        if dur_all - 3.2 - last_t > 1.2:
            out.append((dur_all - 3.2, {"type": "crane_up" if (mode3d and not photo) else "pull_back", "duration": 3.2,
                                         "_auto": True}))

    # ---------------------------------------------------------------- long static stretches keep moving
    shots = sorted(out + [(t, c) for t, c in user], key=lambda s: s[0])
    extra = []
    for (t0, c0), (t1, _c1) in zip(shots, shots[1:] + [(dur_all, None)]):
        gap = t1 - t0
        if gap > 7.0 and c0.get("type") not in ("track", "lead", "inside", "follow", "auto"):
            tm = t0 + gap / 2
            if not covered(tm) and humans and all(abs(tm - x) > MIN_SHOT * 1.5 for x, _ in out + user):
                main = min(humans, key=lambda c: z_of(c, tm))
                extra.append((tm, {"type": "arc" if mode3d else "medium", "target": main,
                                   "duration": min(gap / 2, 6.0), "cut": True, "_auto": True}))
    out += extra

    # ---------------------------------------------------------------- impacts: punch-ins and shakes
    for tt, name, vol, who, *_rest in ([] if feat else tl.sfx):
        k = IMPACT_SFX.get(str(name))
        if not k or vol < 0.45:
            continue
        if any(abs(tt - u) < 0.6 for u in user_fx):
            continue
        typ, inten = k
        out.append((tt, {"type": typ, "intensity": inten * min(1.0, vol + 0.2),
                         "duration": 0.35 if typ == "punch" else 0.5, "_auto": True}))
        user_fx.append(tt)
    return out
