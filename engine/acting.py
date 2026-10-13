"""Acting: body language that comes from the words, so a scene of pure talk still looks alive.

  * speakers: every line gets its own gesture, picked from what is said (a question -> open palms, "I / main" ->
    a hand on the chest, "look / dekho" -> a point, "come / chalo" -> a "come here" wave, anger -> a firm hand,
    sadness -> hands low ...). The hands hit the stressed words (the beats the lip sync already finds).
  * listeners: they never freeze - weight shifts, a stance of their own (arms folded, hands on hips, hands behind
    the back ...) that changes now and then, and a short reaction to a funny / shocking line.

Only the upper body changes; legs, walking, sitting and the story's own actions are never touched.
"settings": {"acting": "off"} (or per scene) turns it off; "calm" keeps the gestures smaller.
"""
import math
import re

from .poses import STAND, P, add, ik, keyframes, blend
from .util import clamp, smoothstep, stable_hash, TAU

# ----------------------------------------------------------------------------------------------- words -> gesture
_W = lambda *ws: re.compile(r"(?:^|[\s,.!?;:'\"(])(?:" + "|".join(ws) + r")(?=$|[\s,.!?;:'\")])", re.I)
QUESTION = _W("why", "what", "how", "where", "who", "when", "which", "kya", "kyun", "kyon", "kaise", "kaun", "kahan",
              "kab", "क्या", "क्यों", "कैसे", "कौन", "कहाँ", "कहां", "कब")
SELF = _W("i", "i'm", "im", "me", "my", "myself", "mine", "main", "mein", "mujhe", "mera", "meri", "mere", "hum",
          "मैं", "मुझे", "मेरा", "मेरी", "मेरे", "हम", "हमें", "हमारा")
POINT = _W("look", "there", "that", "see", "you", "your", "yours", "dekho", "wahan", "woh", "wo", "udhar", "tum",
           "tumhe", "tumne", "aap", "देखो", "देख", "वहाँ", "वहां", "वो", "उधर", "तुम", "तुम्हें", "तुमने", "आप")
COME = _W("come", "let's", "lets", "let us", "follow", "hurry", "chalo", "aao", "aaja", "idhar", "jaldi", "चलो", "आओ",
          "आजा", "इधर", "जल्दी")
NO = _W("no", "not", "never", "don't", "dont", "stop", "nahi", "nahin", "mat", "na", "bas", "नहीं", "मत", "ना", "बस")
THINK = _W("hmm", "maybe", "perhaps", "think", "wonder", "shayad", "socho", "soch", "शायद", "सोचो", "सोच", "हम्म")
FIRM = _W("must", "now", "never", "enough", "abhi", "zaroor", "अभी", "ज़रूर", "जरूर", "बस")
LAUGH = re.compile(r"\b(ha ?ha|hehe|lol)\b|हा ?हा|ही ?ही", re.I)

STYLES = ("explain", "baton", "palms_up", "chest", "point", "beckon", "fist", "calm", "excited", "wave_off", "think")


def classify(text, emotion=None, salt=0, prev=None):
    """The gesture for one line (a name from STYLES)."""
    s = " " + str(text or "").strip() + " "
    low = s.lower()
    emo = str(emotion or "").lower()
    first = " ".join(low.split()[:3])
    pick = None
    if emo in ("sad", "crying", "scared"):
        pick = "calm"
    elif emo == "angry" or (FIRM.search(low) and s.strip().endswith("!")):
        pick = "fist"
    elif LAUGH.search(low) or emo in ("laughing",):
        pick = "excited"
    elif COME.search(low):
        pick = "beckon"
    elif s.strip().endswith("?") or QUESTION.search(first + " "):
        pick = "palms_up"
    elif THINK.search(low):
        pick = "think"
    elif SELF.search(" " + first + " "):
        pick = "chest"
    elif POINT.search(low):
        pick = "point"
    elif NO.search(" " + first + " "):
        pick = "wave_off"
    elif emo in ("happy", "surprised") or s.strip().endswith("!"):
        pick = "excited"
    if pick is None:
        pick = ("explain", "baton")[salt % 2]
    if pick == prev:                                  # the same person never repeats the same gesture twice running
        pick = {"explain": "baton", "baton": "explain"}.get(pick, "explain" if prev != "explain" else "baton")
    return pick


def beats(sp, fps):
    """Seconds (from the start of the line) of the stressed words."""
    talk = getattr(sp, "talk", None)
    if talk is not None and getattr(talk, "peaks", None):
        return [p / float(fps) for p in talk.peaks]
    n = max(1, int(sp.dur / 0.55))
    return [0.3 + k * 0.55 for k in range(n) if 0.3 + k * 0.55 < sp.dur - 0.2]


def _beat(lt, bts, lead=0.06, w=0.11):
    """0..1 - the hand comes down on each beat, a little before the word (as real speakers do)."""
    v = 0.0
    for b in bts:
        d = (lt - (b - lead)) / w
        if -3 < d < 3:
            v = max(v, math.exp(-d * d))
    return v


def _arms(near=None, far=None):
    out = {}
    if near is not None:
        out["an_u"], out["an_l"] = ik(near)
    if far is not None:
        out["af_u"], out["af_l"] = ik(far)
    return out


CHEST = _arms(near=(16, -22))
LOW_HANDS = _arms(near=(18, -54), far=(15, -52))
CHIN = _arms(near=(24, 30))


def talk_pose(style, lt, dur, bts, k=1.0):
    """The upper body while saying a line (lt = seconds into it)."""
    b = _beat(lt, bts) * k
    sway = math.sin(TAU * 0.45 * lt)
    u = lt / max(dur, 0.1)
    base = add(STAND, torso=1.5 * sway)
    if style == "explain":                            # both hands open in front, dipping on the beats
        o = math.sin(TAU * 0.6 * lt)
        return add(base, an_u=32 + 6 * o - 14 * b, an_l=58 + 10 * o - 18 * b, af_u=24 - 6 * o - 10 * b,
                   af_l=62 - 8 * o - 14 * b, head=2 * b)
    if style == "baton":                              # one hand beats the rhythm
        return add(base, an_u=26 - 12 * b, an_l=62 + 8 * math.sin(TAU * 0.8 * lt) - 26 * b, af_u=4, af_l=8,
                   head=3 * b)
    if style == "palms_up":                           # a question: open palms, a small shrug at the end
        end = smoothstep((u - 0.7) / 0.3)
        return add(base, an_u=18 - 6 * b, an_l=96 - 10 * b, af_u=12, af_l=92, head=6 * end + 2 * b,
                   torso=-2 * end)
    if style == "chest":                              # "I / main": hand to the chest, then a beat
        hold = 1.0 - smoothstep((u - 0.6) / 0.25)
        p = dict(base)
        for kk, v in CHEST.items():
            p[kk] = v
        p = blend(add(base, an_u=26 - 12 * b, an_l=60 - 24 * b), p, hold)
        return add(p, torso=2 * hold, head=2 * b)
    if style == "point":                              # "look / you": a point that lands on the word, then baton
        a = smoothstep(lt / 0.35) * (1.0 - smoothstep((u - 0.55) / 0.25))
        pt = add(base, torso=3, head=-3, an_u=82, an_l=4)
        return blend(add(base, an_u=26 - 12 * b, an_l=60 - 24 * b), pt, a)
    if style == "beckon":                             # "come / chalo": a "come here" with the fingers
        c = 0.5 + 0.5 * math.sin(TAU * 2.2 * lt)
        return add(base, an_u=58, an_l=40 + 70 * c, af_u=6, af_l=8, torso=2)
    if style == "fist":                               # anger / "must": a firm hand chops down on the words
        return add(base, torso=6, head=-4 - 3 * b, an_u=44 - 20 * b, an_l=96 - 50 * b, af_u=-8, af_l=30)
    if style == "calm":                               # sad / scared / soft: hands low together, head down
        p = dict(base)
        for kk, v in LOW_HANDS.items():
            p[kk] = v
        return add(p, head=7 + 2 * b, torso=3)
    if style == "excited":                            # happy / "!": both hands open out on the beats
        return add(base, torso=-3, an_u=48 + 26 * b, an_l=30 + 10 * b, af_u=40 + 22 * b, af_l=32, head=-3 * b)
    if style == "wave_off":                           # "no / nahi": the hand sweeps it away
        sw = keyframes(min(1.0, lt / 0.9), [(0, dict(an=30.0)), (0.5, dict(an=72.0)), (1, dict(an=40.0))])["an"]
        return add(base, an_u=sw - 8 * b, an_l=24, af_u=4, af_l=8, head=-3 * math.sin(TAU * 1.6 * min(lt, 1.2)))
    if style == "think":                              # "hmm / shayad": hand at the chin first
        hold = 1.0 - smoothstep((u - 0.5) / 0.3)
        p = dict(base)
        for kk, v in CHIN.items():
            p[kk] = v
        p = add(p, head=8 * hold)
        return blend(add(base, an_u=26 - 12 * b, an_l=60 - 24 * b), p, hold)
    return base


# ----------------------------------------------------------------------------------------------- listening
STANCES = ("relaxed", "folded", "hips", "behind", "clasped")


def _stance_arms(name):
    if name == "folded":
        return _arms(near=(24, -30), far=(22, -27))
    if name == "hips":
        return dict(an_u=-28.0, an_l=80.0, af_u=-24.0, af_l=78.0)
    if name == "behind":
        return _arms(near=(-20, -48), far=(-18, -46))
    if name == "clasped":
        return _arms(near=(20, -52), far=(18, -50))
    return {}


def listen_pose(pose, me, t, react=None, kind="human", scale=1.0):
    """A standing, listening character: a stance of their own that changes now and then, weight shifts, and a
    short reaction (react = ("laugh" | "surprised" | "nod", seconds since it started))."""
    if kind != "human":
        return pose
    salt = stable_hash(me)
    period = 7.0 + (salt % 5)
    k = int((t + salt % 13) / period)
    name = STANCES[stable_hash(f"{me}#{k}") % len(STANCES)]
    if scale < 0.8 and name in ("folded", "behind"):
        name = "relaxed"                              # children rarely stand like that
    local = (t + salt % 13) - k * period
    w = smoothstep(local / 0.9) * (1.0 - smoothstep((local - period + 0.9) / 0.9))
    out = dict(pose)
    for kk, v in _stance_arms(name).items():
        out[kk] = out.get(kk, 0.0) + (v - out.get(kk, 0.0)) * w
    sh = math.sin(TAU * t / (5.5 + salt % 3))            # weight shift: the hips and legs move a little
    out["torso"] = out.get("torso", 0.0) + 1.4 * sh
    out["ln_t"] = out.get("ln_t", 0.0) + 2.0 * sh
    out["lf_t"] = out.get("lf_t", 0.0) - 2.0 * sh
    if react:
        kind_r, s = react
        a = smoothstep(s / 0.25) * (1.0 - smoothstep((s - 1.2) / 0.4))
        if kind_r == "laugh":
            out = add(out, torso=-6 * a * (1 + 0.4 * math.sin(TAU * 4 * s)), head=-10 * a, an_u=10 * a, af_u=8 * a)
        elif kind_r == "surprised":
            out = add(out, torso=-7 * a, head=-6 * a, an_u=22 * a, an_l=40 * a, af_u=18 * a, af_l=36 * a)
        elif kind_r == "nod":
            out = add(out, head=10 * a * abs(math.sin(TAU * 1.4 * s)))
    return out


def reaction_to(sp):
    """How listeners react when a line ends: "laugh" / "surprised" / None."""
    emo = str(getattr(sp, "emotion", "") or "").lower()
    text = str(getattr(sp, "text", "") or "")
    if emo in ("laughing", "funny") or LAUGH.search(text.lower()):
        return "laugh"
    if emo in ("surprised", "shocked") or (text.strip().endswith("!") and emo in ("angry", "scared")):
        return "surprised"
    if text.strip().endswith("?"):
        return None
    return "nod" if stable_hash(text) % 3 == 0 else None
