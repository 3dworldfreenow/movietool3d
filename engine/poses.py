"""Pose library + action library.

A *pose* is a dict of joint angles (degrees). Convention: every limb angle is
measured from straight DOWN, positive = rotating toward the direction the
character faces. Upper arms / thighs are absolute (body vertical), fore-arms
and shins are relative to their parent bone.

    torso  lean of the spine (+ forward)        head   head tilt (+ nods forward)
    an_u / an_l   near arm upper / fore-arm     af_u / af_l   far arm
    ln_t / ln_s   near leg thigh / shin         lf_t / lf_s   far leg
    rot    whole-body rotation (+90 = lying on back, -90 = face down)
    lift   extra height above the ground (jumps)

An *action* is a function  fn(t, dur, ctx) -> (pose, extras)  that returns the
pose at local time t.  extras can carry: face, tears, zzz, alpha, flip,
attach (0..1 moment to grab a prop), detach.
"""
import math

from .util import clamp, lerp, smoothstep, TAU

POSE_KEYS = ("torso", "head", "an_u", "an_l", "af_u", "af_l",
             "ln_t", "ln_s", "lf_t", "lf_s", "rot", "lift")

# Bone lengths of a 1.0-scale figure (world units ~ pixels at 1080p, zoom 1)
BONES = dict(torso=95, neck=12, head_r=28, upper_arm=55, fore_arm=50,
             thigh=72, shin=70, foot=14)
SHOULDER_DROP = 7   # shoulder sits a bit below the neck


def P(**kw):
    p = {k: 0.0 for k in POSE_KEYS}
    p.update(kw)
    return p


def blend(a, b, t):
    keys = a.keys() | b.keys()
    return {k: lerp(a.get(k, 0.0), b.get(k, 0.0), t) for k in keys}


def add(p, **kw):
    q = dict(p)
    for k, v in kw.items():
        q[k] = q.get(k, 0.0) + v
    return q


def keyframes(u, frames):
    """frames: [(time_0_to_1, pose), ...] -> smooth interpolation at u."""
    u = clamp(u, 0.0, 1.0)
    for (t0, p0), (t1, p1) in zip(frames, frames[1:]):
        if u <= t1:
            return blend(p0, p1, smoothstep((u - t0) / max(t1 - t0, 1e-6)))
    return dict(frames[-1][1])


def ik(target, bend="down"):
    """2-bone IK for an arm. target=(x, y) relative to the shoulder in torso space.
    Returns (upper, lower) angles in the pose convention."""
    a, b = BONES["upper_arm"], BONES["fore_arm"]
    tx, ty = target
    d = clamp(math.hypot(tx, ty), abs(a - b) + 1, a + b - 0.5)
    phi = math.degrees(math.atan2(tx, -ty))
    alpha = math.degrees(math.acos(clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1)))
    best = None
    for th1 in (phi - alpha, phi + alpha):
        ex, ey = a * math.sin(math.radians(th1)), -a * math.cos(math.radians(th1))
        th_t = math.degrees(math.atan2(tx - ex, -(ty - ey)))
        cand = (th1, th_t - th1, ey)
        if best is None or (bend == "down" and ey < best[2]) or (bend == "up" and ey > best[2]):
            best = cand
    return best[0], best[1]


def arms_to(near, far, bend="down"):
    nu, nl = ik(near, bend)
    fu, fl = ik(far, bend)
    return dict(an_u=nu, an_l=nl, af_u=fu, af_l=fl)


# --------------------------------------------------------------------------- static poses
STAND = P(an_u=8, an_l=8, af_u=-6, af_l=8, ln_t=2, ln_s=-2, lf_t=-4, lf_s=-2)
SIT = P(torso=-2, head=4, an_u=30, an_l=50, af_u=22, af_l=50, ln_t=86, ln_s=-86, lf_t=80, lf_s=-80)
LIE_BACK = P(rot=90, head=-4, an_u=6, an_l=4, af_u=-4, af_l=4, ln_t=2, lf_t=-3, ln_s=-2, lf_s=-2)
FACE_DOWN = P(rot=-88, head=-10, an_u=160, an_l=10, af_u=150, af_l=15, ln_t=0, lf_t=6, ln_s=-6, lf_s=-10)
CROUCH = P(torso=22, head=-6, an_u=-35, an_l=15, af_u=-28, af_l=15, ln_t=58, ln_s=-100, lf_t=52, lf_s=-96)
AIR = P(torso=4, head=-8, an_u=160, an_l=10, af_u=150, af_l=15, ln_t=28, ln_s=-65, lf_t=8, lf_s=-35)
ARMS_UP = add(STAND, an_u=157, an_l=0, af_u=164, af_l=2)
BEND = P(torso=78, head=18, an_u=6, an_l=4, af_u=-2, af_l=6,ln_t=18, ln_s=-32, lf_t=6, lf_s=-22)
HUG = add(STAND, torso=6, an_u=82, an_l=35, af_u=90, af_l=30)

_CRY_ARMS = arms_to((30, 44), (25, 40))
_LAUGH_ARMS = arms_to((22, -44), (17, -38))
_THINK_ARMS = dict(**{k: v for k, v in zip(("an_u", "an_l"), ik((22, 30)))},
                   **{k: v for k, v in zip(("af_u", "af_l"), ik((20, -30)))})
_SCARED_ARMS = arms_to((38, 40), (32, 28))


# --------------------------------------------------------------------------- action functions
def a_idle(t, dur, ctx):
    b = math.sin(TAU * t / 3.6)
    return add(STAND, torso=1.2 * b, head=1.5 * math.sin(TAU * t / 5.1), an_u=1.5 * b, af_u=-1.5 * b), {}


def a_talk(t, dur, ctx):
    s1 = math.sin(TAU * 0.85 * t)
    s2 = math.sin(TAU * 1.3 * t + 1.1)
    return add(STAND, torso=2 * math.sin(TAU * 0.45 * t), head=3 * s2,
               an_u=22 + 16 * s1, an_l=48 + 24 * s2, af_u=2 + 6 * s2, af_l=6), {}


def _cycle_phase(t, ctx, stride, cadence):
    dist = ctx.get("dist", 0.0)
    if ctx.get("speed", 0) > 1:
        return dist / stride
    return t * cadence          # moving "in place"


def leg_ik(fx, fy):
    """Thigh / shin angles (pose convention) that put the ankle at (fx, fy) from the hip; the knee bends forward."""
    L1, L2 = BONES["thigh"], BONES["shin"]
    d = clamp(math.hypot(fx, fy), abs(L1 - L2) + 1.0, L1 + L2 - 0.4)
    phi = math.degrees(math.atan2(fx, -fy))
    al = math.degrees(math.acos(clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1.0, 1.0)))
    be = math.degrees(math.acos(clamp((L2 * L2 + d * d - L1 * L1) / (2 * L2 * d), -1.0, 1.0)))
    return phi + al, -(al + be)


def _gait_legs(p, stride, hip_h, clear, bob):
    """Leg angles for a walk / run cycle at phase p with the standing foot LOCKED to the ground: while a foot is
    down it slides back under the body exactly as fast as the body moves forward (no skating), the other foot
    swings forward in an arc. Returns (ln_t, ln_s, lf_t, lf_s)."""
    reach = BONES["thigh"] + BONES["shin"] - 0.6
    half = stride / 4.0                                  # the foot goes from +half (heel strike) to -half (push off)
    out = []
    for ph in (p % 1.0, (p + 0.5) % 1.0):               # near leg, far leg half a cycle later
        if ph < 0.5:                                    # stance: on the ground, moving back at body speed
            u = ph / 0.5
            fx = half - 2.0 * half * u
            lift = 0.0
        else:                                           # swing: up and forward
            u = (ph - 0.5) / 0.5
            e = u * u * (3 - 2 * u)
            fx = -half + 2.0 * half * e
            lift = clear * math.sin(math.pi * u) ** 0.8
        out.append((fx, lift))
    # the hips: as high as the standing leg reaches (a little bob, highest over the foot)
    st_fx = out[0][0] if (p % 1.0) < 0.5 else out[1][0]
    h = min(hip_h + bob * math.cos(TAU * 2 * p), math.sqrt(max(1.0, reach * reach - st_fx * st_fx)))
    (nx, nl), (fx_, fl) = out
    ln_t, ln_s = leg_ik(nx, -h + nl)
    lf_t, lf_s = leg_ik(fx_, -h + fl)
    return ln_t, ln_s, lf_t, lf_s


# Walking by mood: the same locked-feet gait, but the body tells how the person feels.
#   stride (x normal), foot lift, hip bob, torso lean, head (+ = down), arm swing (x), elbow bend, speed (x)
MOOD_GAIT = {
    "happy":     dict(stride=1.04, clear=1.35, bob=7.0, torso=-1.0, head=-5.0, swing=1.3, bend=6.0, speed=1.06),
    "laughing":  dict(stride=1.04, clear=1.35, bob=7.0, torso=-1.0, head=-5.0, swing=1.3, bend=6.0, speed=1.06),
    "excited":   dict(stride=1.06, clear=1.5, bob=9.0, torso=0.0, head=-6.0, swing=1.45, bend=14.0, speed=1.15),
    "love":      dict(stride=0.96, clear=1.2, bob=5.0, torso=-1.0, head=-3.0, swing=1.0, bend=4.0, speed=0.95),
    "proud":     dict(stride=1.08, clear=1.1, bob=2.0, torso=-5.0, head=-8.0, swing=0.9, bend=0.0, speed=0.95),
    "sad":       dict(stride=0.8, clear=0.45, bob=1.0, torso=9.0, head=18.0, swing=0.35, bend=-8.0, speed=0.72),
    "crying":    dict(stride=0.78, clear=0.45, bob=1.0, torso=10.0, head=20.0, swing=0.3, bend=-8.0, speed=0.7),
    "tired":     dict(stride=0.78, clear=0.4, bob=1.5, torso=8.0, head=12.0, swing=0.4, bend=-6.0, speed=0.7),
    "sleepy":    dict(stride=0.78, clear=0.4, bob=1.5, torso=8.0, head=12.0, swing=0.4, bend=-6.0, speed=0.7),
    "bored":     dict(stride=0.86, clear=0.6, bob=1.0, torso=4.0, head=8.0, swing=0.55, bend=-4.0, speed=0.8),
    "angry":     dict(stride=1.08, clear=1.2, bob=4.5, torso=10.0, head=6.0, swing=1.25, bend=40.0, speed=1.12),
    "scared":    dict(stride=0.8, clear=0.9, bob=2.0, torso=14.0, head=4.0, swing=0.45, bend=70.0, speed=1.2),
    "suspicious": dict(stride=0.82, clear=0.8, bob=1.0, torso=8.0, head=4.0, swing=0.4, bend=30.0, speed=0.8),
    "thinking":  dict(stride=0.85, clear=0.8, bob=1.0, torso=5.0, head=10.0, swing=0.4, bend=10.0, speed=0.8),
}


def mood_gait(mood):
    return MOOD_GAIT.get(str(mood or "neutral"))


def mood_stride(mood, aname="walk"):
    g = MOOD_GAIT.get(str(mood or "neutral"))
    base = WALK_STRIDE if aname == "walk" else RUN_STRIDE
    return base * (g["stride"] if g else 1.0)


_NO_BODY = {"bob": 1.0, "clear": 1.0, "sink": 0.0, "swing": 1.0, "land": 0.35, "real": False}


CRAWL_STRIDE = 60.0


def a_crawl(t, dur, ctx, fast=False):
    """A baby crawling on hands and knees: the near arm and the far knee go forward together."""
    legk = ctx.get("legk", 1.0)
    p = _cycle_phase(t, ctx, CRAWL_STRIDE * legk, 1.6 if fast else 1.1)
    s = math.sin(TAU * p)
    th = 16 * s
    return P(torso=68 + 3 * math.sin(TAU * 2 * p), head=-58, an_u=-4 + 18 * s, af_u=-4 - 18 * s, an_l=0, af_l=0,
             ln_t=-6 - th, ln_s=-84 + th, lf_t=-6 + th, lf_s=-84 - th, lift=2 * abs(s)), {}


def _toddle(t, ctx, stride, run=False):
    """A toddler: short wide steps, arms out for balance, tummy forward, a wobble from side to side."""
    legk = ctx.get("legk", 1.0)
    p = _cycle_phase(t, ctx, stride * legk, 1.5)
    s = math.sin(TAU * p)
    ln_t, ln_s, lf_t, lf_s = _gait_legs(p, stride, 136.0, 22.0 if run else 16.0, 4.0)
    return P(torso=-5 + (8 if run else 0) + 3.5 * math.sin(TAU * p), head=4 - 3 * math.sin(TAU * p), ln_t=ln_t, ln_s=ln_s, lf_t=lf_t, lf_s=lf_s,
             an_u=52 + 10 * s, af_u=44 - 10 * s, an_l=24, af_l=24), {}


def a_walk(t, dur, ctx):
    age = ctx.get("age")
    if age == "baby":
        return a_crawl(t, dur, ctx)
    if age == "toddler":
        return _toddle(t, ctx, WALK_STRIDE * 0.8)
    g = MOOD_GAIT.get(str(ctx.get("mood") or "neutral"))
    w = ctx.get("body") or _NO_BODY                      # weight: heavy = lower, flatter steps; light = bouncy
    if g is None:
        p = _cycle_phase(t, ctx, WALK_STRIDE, 1.0)
        s = math.sin(TAU * p)
        ln_t, ln_s, lf_t, lf_s = _gait_legs(p, WALK_STRIDE, 139.0 - w["sink"], 20.0 * w["clear"],
                                            max(0.0, 3.0 * (w["bob"] - 1.0)))
        sw = 24 * w["swing"]
        return P(torso=4, head=-2, ln_t=ln_t, ln_s=ln_s, lf_t=lf_t, lf_s=lf_s,
                 an_u=-sw * s, af_u=sw * s, an_l=18 + 8 * max(0, s), af_l=18 + 8 * max(0, -s)), {}
    stride = WALK_STRIDE * g["stride"]
    p = _cycle_phase(t, ctx, stride, 1.0 / g["stride"] * g["speed"])
    s = math.sin(TAU * p)
    bob = g["bob"] * w["bob"]
    ln_t, ln_s, lf_t, lf_s = _gait_legs(p, stride, 139.0 - bob * 0.5 - w["sink"], 20.0 * g["clear"] * w["clear"], bob)
    sw = 24 * g["swing"] * w["swing"]
    b = g["bend"]
    jolt = 0.0
    if ctx.get("mood") == "angry":                       # a stomp: the body jolts as each foot lands
        jolt = 3.0 * max(0.0, math.cos(TAU * 2 * p)) ** 6
    return P(torso=4 + g["torso"] + jolt, head=-2 + g["head"], ln_t=ln_t, ln_s=ln_s, lf_t=lf_t, lf_s=lf_s,
             an_u=-sw * s, af_u=sw * s, an_l=max(0.0, 18 + b + 8 * max(0, s)),
             af_l=max(0.0, 18 + b + 8 * max(0, -s))), {}


def a_run(t, dur, ctx):
    age = ctx.get("age")
    if age == "baby":
        return a_crawl(t, dur, ctx, fast=True)
    if age == "toddler":
        return _toddle(t, ctx, WALK_STRIDE, run=True)
    g = MOOD_GAIT.get(str(ctx.get("mood") or "neutral"))
    k = g["stride"] if g else 1.0
    stride = RUN_STRIDE * k
    p = _cycle_phase(t, ctx, stride, 1.6)
    s = math.sin(TAU * p)
    w = ctx.get("body") or _NO_BODY
    ln_t, ln_s, lf_t, lf_s = _gait_legs(p, stride, 124.0 - 1.5 * w["sink"],
                                        44.0 * (min(1.2, g["clear"]) if g else 1.0) * w["clear"],
                                        max(0.0, 4.0 * (w["bob"] - 1.0)))
    if ctx.get("mood") == "scared":                      # running away: arms up and flailing, looking back
        return P(torso=20, head=-16, ln_t=ln_t, ln_s=ln_s, lf_t=lf_t, lf_s=lf_s,
                 an_u=120 + 25 * s, af_u=110 - 25 * s, an_l=40, af_l=45), {"face": "scared"}
    sw = 48 * (min(1.3, g["swing"]) if g else 1.0)
    return P(torso=16 + (g["torso"] * 0.5 if g else 0.0), head=-10 + (g["head"] * 0.4 if g else 0.0),
             ln_t=ln_t, ln_s=ln_s, lf_t=lf_t, lf_s=lf_s, an_u=-sw * s, af_u=sw * s, an_l=85, af_l=85), {}


def a_sit(t, dur, ctx):
    b = math.sin(TAU * t / 4.0)
    return add(SIT, torso=b, head=1.2 * b), {"seat": True}


def a_sleep(t, dur, ctx):
    return add(LIE_BACK, torso=0.8 * math.sin(TAU * t / 3.2)), {"face": "sleeping", "zzz": True}


def a_lie(t, dur, ctx):
    return dict(LIE_BACK), {}


def a_fall(t, dur, ctx):
    return dict(FACE_DOWN), {"face": "surprised" if t < 0.8 else "sad"}


def a_jump(t, dur, ctx):
    u = t / max(dur, 0.1)
    w = ctx.get("body") or _NO_BODY
    land = blend(STAND, CROUCH, clamp(0.65 + w["land"], 0.4, 1.25))   # heavier bodies sink deeper on landing
    pose = keyframes(u, [(0, STAND), (0.18, CROUCH), (0.3, AIR), (0.66, AIR),
                         (0.8, land), (1.0, STAND)])
    h = float(ctx.get("params", {}).get("height", 120))
    if 0.18 < u < 0.8:
        f = (u - 0.18) / 0.62
        # real: a parabola (constant gravity); cartoon: a sine that hangs a little at the top
        pose["lift"] += h * (4.0 * f * (1.0 - f) if w["real"] else math.sin(math.pi * f))
    return pose, {}


def a_wave(t, dur, ctx):
    return add(STAND, torso=-2, head=-4, an_u=150 + 5 * math.sin(TAU * 1.1 * t),
               an_l=15 + 32 * (0.5 + 0.5 * math.sin(TAU * 2.2 * t)) - 8), {"face": "happy"}


def a_point(t, dur, ctx):
    return add(STAND, torso=3, head=-4, an_u=84 + 2 * math.sin(TAU * t), an_l=2), {}


def a_think(t, dur, ctx):
    p = P(**{**STAND, **_THINK_ARMS})
    return add(p, head=12 + 2 * math.sin(TAU * t / 2.5), torso=-2), {"face": "thinking"}


def a_laugh(t, dur, ctx):
    s = math.sin(TAU * 4.2 * t)
    p = P(**{**STAND, **_LAUGH_ARMS})
    return add(p, torso=-12 + 4 * s, head=-18 + 4 * s, ln_s=-6, lf_s=-6), {"face": "laughing"}


def a_cry(t, dur, ctx):
    s = math.sin(TAU * 3.0 * t)
    p = P(**{**STAND, **_CRY_ARMS})
    return add(p, torso=12 + 2.5 * s, head=18 + 2 * s, ln_s=-6, lf_s=-6), {"face": "crying", "tears": True}


def a_sad(t, dur, ctx):
    return add(STAND, torso=12, head=24, an_u=-6, af_u=-12, an_l=2, af_l=2,
               ln_s=-4, lf_s=-4), {"face": "sad"}


def a_clap(t, dur, ctx):
    k = abs(math.sin(math.pi * 3.0 * t))
    nu, nl = ik((46, -2))
    fu, fl = ik((46 - 22 * k, -2))
    return P(**{**STAND, "an_u": nu, "an_l": nl, "af_u": fu, "af_l": fl, "head": -4}), {"face": "happy"}


def a_dance(t, dur, ctx):
    s = math.sin(TAU * 1.0 * t)
    b = abs(math.sin(TAU * 1.0 * t))
    return P(torso=10 * s, head=-8 * s, an_u=130 + 30 * s, an_l=30 - 25 * s,
             af_u=130 - 30 * s, af_l=30 + 25 * s,
             ln_t=14 * s, lf_t=-14 * s, ln_s=-20 - 20 * b, lf_s=-20 - 20 * (1 - b),
             lift=10 * b), {"face": "happy"}


def a_celebrate(t, dur, ctx):
    b = abs(math.sin(TAU * 0.8 * t))
    return add(ARMS_UP, lift=26 * b, an_u=6 * math.sin(TAU * 1.6 * t), ln_s=-10 * (1 - b),
               lf_s=-10 * (1 - b)), {"face": "laughing"}


def a_angry(t, dur, ctx):
    s = math.sin(TAU * 7 * t)
    return add(STAND, torso=8, head=8, an_u=22 + 3 * s, an_l=100, af_u=15 - 3 * s, af_l=100,
               lf_t=-8, ln_t=6), {"face": "angry"}


def a_surprised(t, dur, ctx):
    hop = 18 * math.sin(math.pi * clamp(t / 0.35, 0, 1))
    return add(STAND, torso=-9, head=-10, an_u=138, an_l=38, af_u=128, af_l=40, lift=hop), {"face": "surprised"}


def a_scared(t, dur, ctx):
    s = math.sin(TAU * 11 * t)
    p = P(**{**STAND, **_SCARED_ARMS})
    return add(p, torso=-12 + 2 * s, head=-6, ln_s=-26, lf_s=-22, ln_t=12, lf_t=6), {"face": "scared"}


def a_shrug(t, dur, ctx):
    u = smoothstep(t / 0.4) * (1 - smoothstep((t - dur + 0.4) / 0.4))
    return blend(STAND, add(STAND, head=12, an_u=10, an_l=105, af_u=2, af_l=105), u), {}


def a_bow(t, dur, ctx):
    u = t / max(dur, 0.1)
    bow = add(STAND, torso=58, head=12, an_u=4, af_u=-2)
    return keyframes(u, [(0, STAND), (0.35, bow), (0.65, bow), (1, STAND)]), {}


def a_nod(t, dur, ctx):
    return add(STAND, head=12 * abs(math.sin(TAU * 1.5 * t))), {}


def a_hug(t, dur, ctx):
    return dict(HUG), {"face": "happy"}


def a_kick(t, dur, ctx):
    u = t / max(dur, 0.1)
    kick = add(STAND, torso=-10, ln_t=80, ln_s=-5, an_u=-30, af_u=40, af_l=30)
    wind = add(STAND, torso=6, ln_t=-30, ln_s=-60, an_u=30, af_u=-30)
    return keyframes(u, [(0, STAND), (0.35, wind), (0.55, kick), (1, STAND)]), {}


def reach_level(h):
    """The pose that puts a grown-up's hand at height h (story units above their feet; a person is 300 tall):
    bent right down for the floor, half bent for a low stool, the arm out for a table or a kitchen platform,
    the arm up and on tip-toes for a high shelf. (Shoulder ~215 up, arm ~112 long.)"""
    if h is None or h <= 60:
        return BEND
    if h < 110:                                             # a low thing: bend over from the hips
        f = (110.0 - h) / 50.0
        return add(STAND, torso=26 + 48 * f, head=8 + 10 * f, an_u=34 - 26 * f, an_l=2, ln_t=6 + 10 * f,
                   ln_s=-10 - 20 * f, lf_s=-6 - 14 * f)
    a = math.degrees(math.acos(clamp((215.0 - h) / 112.0, -1.0, 1.0)))
    up = h > 235
    return add(STAND, torso=4 if up else 12, head=-14 if up else 6, an_u=a - 8, an_l=-2, af_u=4, af_l=6,
               lift=8 if up else 0)


def _level(ctx):
    h = ctx.get("params", {}).get("h")
    try:
        return float(h) if h is not None else None
    except (TypeError, ValueError):
        return None


def a_pick(t, dur, ctx):
    u = t / max(dur, 0.1)
    low = reach_level(_level(ctx))                           # from the floor, a table, a shelf ...
    return keyframes(u, [(0, STAND), (0.45, low), (0.55, low), (1, STAND)]), {"attach": 0.5}


def a_put(t, dur, ctx):
    """Putting something down where it belongs - on a table, a shelf, the bed, in a bag: the hand goes to that
    height and lets go (it is placed, not dropped)."""
    u = t / max(dur, 0.1)
    low = reach_level(_level(ctx))
    return keyframes(u, [(0, STAND), (0.45, low), (0.6, low), (1, STAND)]), {"detach": 0.52}


def a_drop(t, dur, ctx):
    u = t / max(dur, 0.1)
    return keyframes(u, [(0, STAND), (0.45, BEND), (0.55, BEND), (1, STAND)]), {"detach": 0.5}


def a_give(t, dur, ctx):
    u = t / max(dur, 0.1)
    reach = add(STAND, torso=8, an_u=80, an_l=5)
    return keyframes(u, [(0, STAND), (0.4, reach), (0.7, reach), (1, STAND)]), {"detach": 0.55}


def a_look_around(t, dur, ctx):
    u = t / max(dur, 0.1)
    return add(STAND, head=-6), {"flip": 0.3 < u < 0.7}


def a_turn(t, dur, ctx):
    return add(STAND, ln_s=-12, lf_s=-12), {}


def a_struggle(t, dur, ctx):
    s = math.sin(TAU * 1.3 * t)
    return add(STAND, torso=24 + 4 * s, head=10, an_u=95 + 10 * s, an_l=60, af_u=70 - 10 * s, af_l=80,
               ln_t=-18, ln_s=-10, lf_t=22, lf_s=-30), {"face": "scared"}


def a_mount(t, dur, ctx):
    """Sitting astride an animal: legs down both sides, hands forward on the reins / neck, bouncing with its gait."""
    g = ctx.get("params", {}).get("_gait", 0.0)
    b = math.sin(TAU * t * (1.0 + 1.6 * g))
    return P(torso=4 + 5 * g + 2 * b, head=-3 - 3 * g, an_u=38 + 4 * b, an_l=48, af_u=34 + 4 * b, af_l=50,
             ln_t=38, ln_s=-52, lf_t=34, lf_s=-50), {}


def a_ride(t, dur, ctx):
    kind = ctx.get("params", {}).get("_vehicle_kind", "car")
    if kind in ("ship", "paper_boat"):
        b = math.sin(TAU * t / 3.0)
        return add(STAND, torso=b, an_u=10 + 4 * b), {}
    if kind == "rowboat":
        p = math.sin(TAU * t / 1.8) * ctx.get("vmoving", 1.0)
        return add(SIT, torso=8 + 14 * p, an_u=70 + 25 * p, an_l=20, af_u=65 + 25 * p, af_l=20), {}
    if kind == "bike":
        mv = ctx.get("vmoving", 1.0)                        # the legs go round only while it moves
        p = t * 1.2
        c = math.cos(TAU * p) * mv
        s = math.sin(TAU * p) * mv
        nu, nl = ik((52, -18))
        return P(torso=22, head=-14, an_u=nu, an_l=nl, af_u=nu - 4, af_l=nl,
                 ln_t=40 + 28 * s, ln_s=-70 - 25 * c, lf_t=40 - 28 * s, lf_s=-70 + 25 * c), {}
    b = math.sin(TAU * t / 3.0)
    return add(SIT, torso=b, an_u=40, an_l=40), {}


def a_appear(t, dur, ctx):
    p, _ = a_idle(t, dur, ctx)
    return p, {"alpha": clamp(t / max(dur, 0.01), 0, 1)}


def a_disappear(t, dur, ctx):
    p, _ = a_idle(t, dur, ctx)
    return p, {"alpha": 1 - clamp(t / max(dur, 0.01), 0, 1)}


# --------------------------------------------------------------------------- working with objects
def _legs(ctx, t, stride, back=False, amp=20.0):
    ph = _cycle_phase(t, ctx, stride, 0.8)
    if back:
        ph = -ph
    s, c = math.sin(TAU * ph), math.cos(TAU * ph)
    return dict(ln_t=amp * s - 4, lf_t=-amp * s - 4,
                ln_s=-(10 + 34 * max(0.0, c)), lf_s=-(10 + 34 * max(0.0, -c))), s


def a_push(t, dur, ctx):
    """Leaning into something with both hands on it, small heavy steps."""
    prm = ctx.get("params", {})
    strain = prm.get("_strain", 0.0)
    legs, s = _legs(ctx, t, WALK_STRIDE * 0.55, amp=22)
    if ctx.get("speed", 0) <= 1:                     # not moving (straining): feet planted, legs braced
        legs = dict(ln_t=18, ln_s=-26, lf_t=-30, lf_s=-6)
    sh = strain * math.sin(TAU * 9 * t)
    h = float(prm.get("_hand", 0.0))                  # hand height relative to normal (+ = higher)
    return P(torso=34 + 3 * strain + 2 * sh, head=-22, an_u=78 + h + sh * 3, an_l=14, af_u=84 + h - sh * 3, af_l=10,
             **legs), ({"face": "angry"} if strain > 0.5 else {})


def a_pull(t, dur, ctx):
    """Leaning back, both hands forward on the object, walking backwards."""
    legs, s = _legs(ctx, t, WALK_STRIDE * 0.5, back=True, amp=18)
    if ctx.get("speed", 0) <= 1:
        legs = dict(ln_t=26, ln_s=-8, lf_t=-12, lf_s=-24)
    return P(torso=-20 + 2 * math.sin(TAU * 2 * t), head=10, an_u=70, an_l=6, af_u=74, af_l=4, **legs), {}


def a_throw(t, dur, ctx):
    u = t / max(dur, 0.1)
    wind = P(torso=-12, head=-6, an_u=200, an_l=40, af_u=60, af_l=20, ln_t=18, ln_s=-6, lf_t=-22, lf_s=-10)
    rel = P(torso=22, head=-8, an_u=95, an_l=0, af_u=-20, af_l=20, ln_t=26, ln_s=-20, lf_t=-28, lf_s=-4)
    follow = P(torso=26, head=-4, an_u=20, an_l=10, af_u=-30, af_l=20, ln_t=20, ln_s=-16, lf_t=-24, lf_s=-6)
    return keyframes(u, [(0, STAND), (0.3, wind), (0.45, rel), (0.65, follow), (1, STAND)]), {}


def a_climb(t, dur, ctx):
    """Climbing hand over hand (a tree / ladder / rock face)."""
    s = math.sin(TAU * 1.1 * t)
    return P(torso=8, head=-14, an_u=150 + 22 * s, an_l=20 - 12 * s, af_u=150 - 22 * s, af_l=20 + 12 * s,
             ln_t=50 + 30 * s, ln_s=-70 - 20 * s, lf_t=50 - 30 * s, lf_s=-70 + 20 * s), {}


def a_hide(t, dur, ctx):
    """Crouched low behind something, peeking forward."""
    b = math.sin(TAU * t / 2.4)
    return P(torso=40 + 2 * b, head=-24, an_u=62, an_l=60, af_u=52, af_l=70,
             ln_t=110, ln_s=-150, lf_t=100, lf_s=-146), {"face": "scared"}


def a_peek(t, dur, ctx):
    """Half up from hiding, looking over the top."""
    return P(torso=24, head=-18 + 3 * math.sin(TAU * t / 1.8), an_u=70, an_l=40, af_u=64, af_l=44,
             ln_t=64, ln_s=-104, lf_t=58, lf_s=-100), {}


def a_open(t, dur, ctx):
    """Bend, take hold of the lid, lift it up."""
    u = t / max(dur, 0.1)
    reach = P(torso=46, head=6, an_u=58, an_l=18, af_u=52, af_l=22, ln_t=14, ln_s=-26, lf_t=4, lf_s=-18)
    lift = P(torso=12, head=-12, an_u=128, an_l=12, af_u=120, af_l=16, ln_t=6, ln_s=-6, lf_t=-4, lf_s=-4)
    return keyframes(u, [(0, STAND), (0.35, reach), (0.7, lift), (1, STAND)]), {}


def a_smash(t, dur, ctx):
    """Both arms up, then a hard blow down."""
    u = t / max(dur, 0.1)
    up = P(torso=-8, head=-10, an_u=175, an_l=10, af_u=170, af_l=12, ln_t=14, ln_s=-8, lf_t=-12, lf_s=-6)
    hit = P(torso=44, head=10, an_u=62, an_l=4, af_u=58, af_l=6, ln_t=26, ln_s=-34, lf_t=-16, lf_s=-10)
    return keyframes(u, [(0, STAND), (0.35, up), (0.55, hit), (0.8, hit), (1, STAND)]), {"face": "angry"}


def a_sit_on(t, dur, ctx):
    """Sitting on a rock / log / chest: no stool, legs hanging and swinging a little."""
    b = math.sin(TAU * t / 3.0)
    return P(torso=-2 + b, head=3 + b, an_u=28, an_l=50, af_u=20, af_l=52,
             ln_t=84, ln_s=-78 + 8 * b, lf_t=80, lf_s=-74 - 8 * b), {}


def a_perch(t, dur, ctx):
    """Sitting up on a branch, one hand holding on above."""
    b = math.sin(TAU * t / 2.6)
    return P(torso=-4 + b, head=4, an_u=160, an_l=12, af_u=26, af_l=40,
             ln_t=80, ln_s=-70 + 10 * b, lf_t=76, lf_s=-66 - 10 * b), {}


def a_step_up(t, dur, ctx):
    """Climbing onto something low: knee up, then standing on top."""
    u = t / max(dur, 0.1)
    knee = P(torso=24, head=-8, an_u=40, an_l=30, af_u=-20, af_l=20, ln_t=95, ln_s=-110, lf_t=-8, lf_s=-6)
    return keyframes(u, [(0, STAND), (0.4, knee), (1, STAND)]), {}


def a_hop_down(t, dur, ctx):
    u = t / max(dur, 0.1)
    return keyframes(u, [(0, CROUCH), (0.3, AIR), (0.75, CROUCH), (1, STAND)]), {}


# --------------------------------------------------------------------------- everyday actions
_MOUTH = (26, 36)            # hand at the mouth, relative to the shoulder (forward, up)
_CHEST = arms_to((16, 2), (13, 4))
_GUARD = arms_to((30, 20), (24, 26), bend="down")


def a_look_down(t, dur, ctx):
    return add(STAND, torso=7, head=26 + 1.5 * math.sin(TAU * t / 3.0)), {}


def a_check_shoe(t, dur, ctx):
    """Stepped in mud: one foot lifted behind to look at the sole, shaken off, arms out for balance."""
    u = t / max(dur, 0.1)
    s = math.sin(TAU * 3.2 * t)
    up = add(STAND, torso=18, head=40, ln_t=40, ln_s=-105 + 12 * s, an_u=62, an_l=12, af_u=-48, af_l=8)
    return keyframes(u, [(0, STAND), (0.2, up), (0.85, up), (1, STAND)]), {"face": "sad"}


def a_look_up(t, dur, ctx):
    return add(STAND, torso=-7, head=-30 + 1.5 * math.sin(TAU * t / 3.0), an_u=-4, af_u=-8), {}


def a_feel_rain(t, dur, ctx):
    """The first drops: looking up, one hand held out palm up to feel them."""
    u = t / max(dur, 0.1)
    out = add(STAND, torso=-4, head=-24, an_u=62, an_l=-6 + 3 * math.sin(TAU * t * 0.8), af_u=-6)
    return keyframes(u, [(0, STAND), (0.3, out), (0.85, out), (1, STAND)]), {}


def a_cover_head(t, dur, ctx):
    """Heavy rain: both arms up over the head, hunched a little."""
    b = math.sin(TAU * t / 2.4)
    return add(STAND, torso=12 + b, head=10, an_u=158, an_l=105, af_u=150, af_l=112), {}


def a_brace_wind(t, dur, ctx):
    """Standing in a hurricane: leaning into the wind (a body leans until its weight's turning force balances the
    wind's push - ~15 degrees in a 150 km/h gust), the far arm up shielding the eyes, the near hand held out (the
    mic), and every gust (each ~1.7 s, sharper at its front) rocks him back half a step."""
    g = (t / 1.7) % 1.0
    gust = math.exp(-((g - 0.15) / 0.08) ** 2) * 1.0                   # a short hard push, then easing off
    sway = 3.0 * math.sin(TAU * t / 0.9)
    return add(STAND, torso=16 - 10 * gust + sway * 0.4, head=8 - 6 * gust, af_u=150 + 8 * gust, af_l=118,
               an_u=70 + 10 * gust, an_l=55, ln_t=-6 - 8 * gust, lf_t=10 + 6 * gust), \
        {"face": "scared" if gust > 0.5 else "worried"}


def a_look_back(t, dur, ctx):
    """Looking back over the shoulder, then turning forward again."""
    u = t / max(dur, 0.1)
    return add(STAND, torso=-3, head=-6), {"flip": 0.18 < u < 0.78}


def a_look_at(t, dur, ctx):
    """Turn toward someone / something and keep looking (the timeline turns the body to the target)."""
    return add(STAND, head=-2 + 1.2 * math.sin(TAU * t / 4.0)), {}


def a_carried(t, dur, ctx):
    """👶 a baby held in someone's arms / on the hip: sitting on the forearm, legs bent round, a hand on the
    carrier's shoulder, looking about (bounces gently when the carrier walks)."""
    g = ctx.get("params", {}).get("_gait", 0.0)
    b = math.sin(TAU * t * (0.6 + 1.6 * g))
    how = ctx.get("params", {}).get("_carry")
    kick = ctx.get("params", {}).get("_struggle")
    k_ = math.sin(TAU * 2.2 * t) if kick else 0.0
    if how == "bridal":                                  # 💞 across the arms: back on one arm, knees over the other,
        return P(rot=38, torso=0, head=-10 + 4 * b, an_u=140 + 20 * k_, an_l=70, af_u=40 + 30 * k_, af_l=50,     # an arm
                 ln_t=95 + 15 * k_, ln_s=-95, lf_t=88 - 15 * k_, lf_s=-90), {"face": "scared" if kick else "happy"}   # round the neck
    if how == "overhead":                                # flat on the back, up on the lifter's hands, arms and legs flailing
        return P(rot=90, head=-6, an_u=150 + 30 * k_, an_l=30, af_u=120 - 30 * k_, af_l=40, ln_t=20 + 25 * k_, ln_s=-30,
                 lf_t=-4 - 25 * k_, lf_s=-20), {"face": "scared"}
    if how == "shoulders":                               # sitting up there, hands on the head below, legs swinging
        return P(torso=-2 + 2 * b, head=-4, an_u=40, an_l=60, af_u=34, af_l=64, ln_t=60 + 6 * b, ln_s=-70 - 6 * b,
                 lf_t=56 - 6 * b, lf_s=-66 + 6 * b), {"face": "happy"}
    hip = how == "hip"
    return P(torso=-4 + 2 * b, head=5 * math.sin(TAU * t / 3.3), an_u=70 + 6 * b, an_l=40, af_u=20, af_l=30,
             ln_t=70 if not hip else 55, ln_s=-70 if not hip else -40, lf_t=64 if not hip else 30,
             lf_s=-66 if not hip else -45), {}


def a_sit_up(t, dur, ctx):
    """👶 a baby sits up by itself: a wobbly upright sit, hands down for balance now and then"""
    w = math.sin(TAU * t / 1.7)
    return P(torso=-4 + 5 * w, head=4 * math.sin(TAU * t / 2.3), an_u=-20 + 8 * w, an_l=30, af_u=-18 - 8 * w, af_l=30,
             ln_t=80, ln_s=-30, lf_t=75, lf_s=-28), {"seat": True}


def a_roll_over(t, dur, ctx):
    """👶 a baby rolls over from its back onto its tummy (and pushes up to look around)"""
    u = min(1.0, t / max(0.6, dur * 0.7))
    k = u * u * (3 - 2 * u)
    rot = 90 - 178 * k
    up = max(0.0, (u - 0.85) / 0.15)
    return P(rot=rot, head=-4 - 14 * up, an_u=6 + 150 * k, an_l=4 + 40 * up, af_u=-4 + 140 * k, af_l=4 + 40 * up,
             ln_t=2 + 10 * math.sin(math.pi * k), lf_t=-3, ln_s=-2, lf_s=-2), {}


HOLD_ARMS = arms_to((22, -26), (20, -22))          # 👶 cradling a baby against the chest
HOLD_HIP = dict(an_u=20, an_l=95)                  # 👶 one arm round a baby on the hip (the other free)
HOLD_BY = {"bridal": arms_to((40, -12), (36, -4)),          # 💞 a grown-up carried: arms under the back and the knees
           "overhead": arms_to((6, 104), (4, 104)),          # straight up under the body
           "shoulders": arms_to((26, 12), (22, 16))}         # holding the legs in front of the chest


def a_carry(t, dur, ctx):
    """Both arms out in front holding something, leaning back a little under the weight; walks with "to"."""
    legs, s = _legs(ctx, t, WALK_STRIDE * 0.8, amp=20)
    if ctx.get("speed", 0) <= 1:
        legs = dict(ln_t=4, ln_s=-4, lf_t=-6, lf_s=-4)
    arms = arms_to((40, -6), (36, -2))
    return P(torso=-5 + 1.5 * s, head=-3, **arms, **legs), {}


def a_drink(t, dur, ctx):
    """Cup to the mouth, head tips back, a few sips, cup down."""
    u = t / max(dur, 0.1)
    nu, nl = ik(_MOUTH)
    sip = P(**{**STAND, "an_u": nu, "an_l": nl, "head": -16, "torso": -4})
    return keyframes(u, [(0, STAND), (0.25, sip), (0.8, add(sip, head=-6)), (1, STAND)]), {}


def a_eat(t, dur, ctx):
    """Hand to the mouth for a few bites, chewing in between."""
    nu, nl = ik(_MOUTH)
    bite = P(**{**STAND, "an_u": nu, "an_l": nl, "head": 4})
    low = P(**{**STAND, **dict(zip(("an_u", "an_l"), ik((24, -4)))), "head": 6})
    ph = (t / 0.9) % 1.0
    pose = keyframes(ph, [(0, low), (0.35, bite), (0.55, bite), (1, low)])
    pose["head"] += 1.2 * math.sin(TAU * 1.6 * t)                         # the head moves a little with the chewing
    # the mouth: wide open for the bite while the hand is at the mouth, then chewing with the lips nearly closed
    # (the jaw goes up and down ~1.6 times a second)
    if 0.25 < ph < 0.55:
        mouth = 0.55 * math.sin(math.pi * (ph - 0.25) / 0.3)
    else:
        mouth = 0.08 + 0.12 * max(0.0, math.sin(TAU * 1.6 * t))
    return pose, {"face": "happy", "mouth": mouth, "chew": True}


def a_reach(t, dur, ctx):
    """Stretching an arm out and up toward something, on tip-toes."""
    u = t / max(dur, 0.1)
    far = add(STAND, torso=14, head=-14, an_u=128, an_l=4, af_u=-18, af_l=10, ln_t=-6, lf_t=4, lift=8)
    return keyframes(u, [(0, STAND), (0.35, far), (1, add(far, an_u=4 * math.sin(TAU * t)))]), {}


def a_touch(t, dur, ctx):
    """A careful hand out to touch something, holding it there."""
    u = t / max(dur, 0.1)
    out = add(STAND, torso=12, head=4, an_u=72, an_l=8, af_u=-4, af_l=14)
    return keyframes(u, [(0, STAND), (0.4, out), (0.85, out), (1, add(out, an_u=-10))]), {}


def a_pull_hand_back(t, dur, ctx):
    """Snatching the hand back (hot! scared!) and leaning away."""
    u = t / max(dur, 0.1)
    out = add(STAND, torso=12, an_u=72, an_l=8)
    back = P(**{**STAND, **_CHEST, "torso": -12, "head": -10})
    return keyframes(u, [(0, out), (0.25, back), (1, add(back, torso=6))]), {"face": "surprised"}


def a_shout(t, dur, ctx):
    """Leaning forward, chest out, arms pulled back, yelling."""
    s = math.sin(TAU * 6 * t)
    return add(STAND, torso=12 + 2 * s, head=-14, an_u=-30, an_l=18, af_u=-34, af_l=18, ln_t=8, lf_t=-10), \
        {"face": "angry"}


def a_retreat(t, dur, ctx):
    """Stepping backwards, away from something, hands up to keep it off."""
    legs, s = _legs(ctx, t, WALK_STRIDE * 0.6, back=True, amp=18)
    if ctx.get("speed", 0) <= 1:
        legs = dict(ln_t=-6, ln_s=-6, lf_t=-18, lf_s=-10)
    return P(torso=-10 + 2 * s, head=-6, **_SCARED_ARMS, **legs), {"face": "scared"}


def a_fight(t, dur, ctx):
    """Boxing: guard up, bouncing, quick punches with each hand."""
    ph = (t / 0.55) % 2.0
    pose = P(torso=14, head=-4, **_GUARD, ln_t=16, ln_s=-22, lf_t=-18, lf_s=-12,
             lift=3 * abs(math.sin(TAU * t / 0.55)))
    k = math.sin(math.pi * min(1.0, (ph % 1.0) / 0.45)) if (ph % 1.0) < 0.45 else 0.0
    if ph < 1.0:
        pose["an_u"] += (88 - pose["an_u"]) * k
        pose["an_l"] *= 1 - k
        pose["torso"] += 6 * k
    else:
        pose["af_u"] += (84 - pose["af_u"]) * k
        pose["af_l"] *= 1 - k
        pose["torso"] += 4 * k
    return pose, {"face": "angry"}


def a_shove(t, dur, ctx):
    """Pushing someone away: hands to the chest, then a hard shove forward."""
    u = t / max(dur, 0.1)
    wind = P(**{**STAND, **_CHEST, "torso": -4})
    hit = add(STAND, torso=22, head=-6, an_u=86, an_l=0, af_u=90, af_l=0, ln_t=24, ln_s=-10, lf_t=-22)
    return keyframes(u, [(0, STAND), (0.3, wind), (0.5, hit), (0.75, hit), (1, STAND)]), {"face": "angry"}


def a_stumble(t, dur, ctx):
    """Pushed: staggering backwards, arms flung out."""
    legs, s = _legs(ctx, t, WALK_STRIDE * 0.45, back=True, amp=24)
    return P(torso=-18 + 4 * s, head=-12, an_u=120, an_l=20, af_u=100, af_l=30, **legs), {"face": "surprised"}


def a_wake(t, dur, ctx):
    """Waking up: (sit up from lying), a big stretch and a yawn, then standing."""
    u = t / max(dur, 0.1)
    stretch = add(ARMS_UP, torso=-6, head=-12)
    if ctx.get("params", {}).get("_from_lying"):
        return keyframes(u, [(0, LIE_BACK), (0.3, CROUCH), (0.45, STAND), (0.75, stretch), (1, STAND)]), \
            {"face": "sleeping" if u < 0.3 else ("surprised" if u < 0.8 else "neutral")}
    return keyframes(u, [(0, STAND), (0.4, stretch), (0.7, stretch), (1, STAND)]), \
        {"face": "surprised" if 0.3 < u < 0.75 else "neutral"}


def a_stop(t, dur, ctx):
    """"Stop!" - one hand held up, palm forward."""
    u = t / max(dur, 0.1)
    hand = add(STAND, torso=-2, head=-4, an_u=78, an_l=82)
    return keyframes(u, [(0, STAND), (0.2, hand), (0.85, hand), (1, STAND)]), {}


# --------------------------------------------------------------------------- 💞 two people together (engine/duets.py)
# The timeline puts both people face to face at the right distance; "_lean" (degrees) is added when one is taller
# (the taller one bends down to the shorter one).
def _lean(ctx):
    return float(ctx.get("params", {}).get("_lean", 0.0))


def a_hug_pair(t, dur, ctx):
    """A real hug: step in, arms right round the other's back, a gentle rock side to side, let go."""
    u = t / max(dur, 0.1)
    ln = _lean(ctx)
    wrap = P(**{**STAND, **arms_to((44, -12), (46, -2)), "torso": 9 + ln, "head": 10})
    reach = P(**{**STAND, **arms_to((60, 4), (58, 10)), "torso": 4 + ln * 0.5, "head": 2})
    pose = keyframes(u, [(0, STAND), (0.18, reach), (0.32, wrap), (0.86, wrap), (1, STAND)])
    if 0.32 < u < 0.86:                                  # the rock: a slow sway while holding on
        pose["torso"] += 2.5 * math.sin(TAU * 0.7 * t)
        pose["head"] += 3 * math.sin(TAU * 0.7 * t + 0.6)
    return pose, {"face": "happy"}


def a_kiss(t, dur, ctx):
    """A kiss: lean in (a hand on the other's shoulder), hold, lean back. "on": cheek | forehead | lips | hand."""
    u = t / max(dur, 0.1)
    on = str(ctx.get("params", {}).get("on", "cheek"))
    ln = _lean(ctx)
    if on == "hand":                                     # a bow over the other's hand (both hands hold it)
        kiss = P(**{**STAND, **arms_to((36, -34), (34, -30)), "torso": 34, "head": 16})
    else:
        kiss = P(**{**STAND, **arms_to((40, -4), (24, -46)), "torso": 11 + ln + (6 if on == "forehead" else 0),
                    "head": 12 + (8 if on == "forehead" else 0)})
    return keyframes(u, [(0, STAND), (0.3, kiss), (0.78, kiss), (1, STAND)]), {"face": "happy"}


def a_kissed(t, dur, ctx):
    """The one being kissed: a small lean in, chin up, a shy happy face (and a hand out, for a kiss on the hand)."""
    u = t / max(dur, 0.1)
    on = str(ctx.get("params", {}).get("on", "cheek"))
    ln = _lean(ctx)
    if on == "hand":
        got = P(**{**STAND, "an_u": 70, "an_l": 10, "torso": -2, "head": -4})
    else:
        got = P(**{**STAND, **arms_to((34, -10), (30, -14)), "torso": 4 + ln, "head": -6 + (10 if on == "lips" else 0)})
    return keyframes(u, [(0, STAND), (0.3, got), (0.8, got), (1, STAND)]), {"face": "happy"}


def a_hold_hands(t, dur, ctx):
    """Face to face holding both hands, swaying a little."""
    s = math.sin(TAU * 0.5 * t)
    return P(**{**STAND, **arms_to((40, -40), (38, -38)), "torso": 3 + 2 * s + _lean(ctx), "head": 4 - 2 * s}), \
        {"face": "happy"}


def a_couple_dance(t, dur, ctx):
    """A slow couple dance: the lead's hand on the other's waist, the other hands joined out to the side, swaying
    and stepping together; "twirl" (the follower) turns under the raised hand once."""
    p_ = ctx.get("params", {})
    lead = p_.get("_role", "lead") == "lead"
    s = math.sin(TAU * 0.55 * t)
    step = math.sin(TAU * 0.55 * t + 0.4)
    arms = arms_to((46, -14), (22, 34)) if lead else arms_to((40, 22), (26, 32))
    pose = P(**{**STAND, **arms, "torso": 4 + 3 * s + _lean(ctx), "head": 2 - 3 * s,
                "ln_t": 6 + 10 * step, "ln_s": -6 - 8 * max(0.0, step), "lf_t": -6 - 10 * step, "lf_s": -6 - 8 * max(0.0, -step)})
    ex = {"face": "happy"}
    tw = p_.get("_twirl")
    if tw and not lead and tw[0] <= t <= tw[1]:          # the twirl: a hand up, the body turns round (flips twice)
        k = (t - tw[0]) / max(tw[1] - tw[0], 0.1)
        pose.update(an_u=165, an_l=10)
        ex["flip"] = 0.25 < k < 0.75
    return pose, ex


def a_kneel_propose(t, dur, ctx):
    """Down on one knee, looking up, one hand holding out a ring / a flower, the other on the heart."""
    u = t / max(dur, 0.1)
    kneel = P(torso=-4, head=-16, an_u=75, an_l=-10, af_u=40, af_l=110, ln_t=88, ln_s=-88, lf_t=-4, lf_s=-92)
    return keyframes(u, [(0, STAND), (0.25, kneel), (1, kneel)]), {"face": "happy"}


def a_overjoyed(t, dur, ctx):
    """Both hands to the mouth (can't believe it!), then a little happy bounce."""
    u = t / max(dur, 0.1)
    mouth = P(**{**STAND, **arms_to((24, 38), (22, 36)), "torso": -6, "head": -4})
    pose = keyframes(u, [(0, STAND), (0.2, mouth), (1, mouth)])
    if u > 0.5:
        pose["lift"] = 6 * abs(math.sin(TAU * 1.4 * t))
    return pose, {"face": "happy"}


def a_lift_person(t, dur, ctx):
    """Bend the knees, grab, lift with the legs (back straight) - "how": arms | overhead | shoulders."""
    u = t / max(dur, 0.1)
    how = ctx.get("params", {}).get("how", "arms")
    low = P(**{**CROUCH, **arms_to((44, -40), (40, -36)), "torso": 26})
    up = P(**{**STAND, **(arms_to((6, 104), (4, 104)) if how == "overhead" else arms_to((26, 12), (22, 16)) if
                         how == "shoulders" else arms_to((40, -12), (36, -4))), "torso": -6})
    return keyframes(u, [(0, STAND), (0.35, low), (0.55, low), (1, up)]), {"face": "angry" if how == "overhead" else None}


def a_throw_person(t, dur, ctx):
    """Throwing someone held overhead / in the arms: a step and a heave forward, the arms follow through."""
    u = t / max(dur, 0.1)
    held = P(**{**STAND, **arms_to((6, 104), (4, 104)), "torso": -10, "ln_t": 10, "lf_t": -14})
    heave = P(**{**STAND, **arms_to((70, 50), (66, 54)), "torso": 24, "head": -6, "ln_t": 30, "ln_s": -14, "lf_t": -28})
    follow = P(**{**STAND, **arms_to((70, -10), (66, -6)), "torso": 30, "head": -2, "ln_t": 26, "ln_s": -18, "lf_t": -24})
    return keyframes(u, [(0, held), (0.3, add(held, torso=-8)), (0.5, heave), (0.7, follow), (1, STAND)]), {"face": "angry"}


def a_flung(t, dur, ctx):
    """Thrown through the air: a ballistic arc (real gravity, see engine/duets.py), tumbling, arms and legs flailing."""
    p_ = ctx.get("params", {})
    fly = p_.get("_fly") or {}
    tt = min(t, dur)
    y = fly.get("y0", 150.0) + fly.get("vy", 0.0) * tt - 0.5 * fly.get("g", 1715.0) * tt * tt
    s = math.sin(TAU * 3.0 * t)
    pose = P(torso=0, head=-10, an_u=150 + 25 * s, an_l=20, af_u=120 - 25 * s, af_l=30, ln_t=40 + 20 * s, ln_s=-50,
             lf_t=10 - 20 * s, lf_s=-30, rot=-fly.get("spin", 360.0) * min(1.0, t / max(dur, 0.1)), lift=max(0.0, y))
    return pose, {"face": "scared"}


def a_punch(t, dur, ctx):
    """A punch: guard up, the near fist shoots straight out (the body turns into it), back to guard.
    "move": jab | hook | uppercut."""
    u = t / max(dur, 0.1)
    mv = ctx.get("params", {}).get("move", "jab")
    guard = P(torso=12, head=-4, **_GUARD, ln_t=16, ln_s=-22, lf_t=-18, lf_s=-12)
    if mv == "uppercut":
        hit = dict(guard, an_u=150, an_l=40, torso=4, head=-10, lift=6)
        wind = dict(guard, an_u=-10, an_l=100, torso=24)
    elif mv == "hook":
        hit = dict(guard, an_u=92, an_l=40, torso=20)
        wind = dict(guard, an_u=40, an_l=100, torso=4)
    else:
        hit = dict(guard, an_u=90, an_l=0, torso=22, ln_t=26)
        wind = dict(guard, an_u=20, an_l=110, torso=6)
    return keyframes(u, [(0, guard), (0.25, wind), (0.45, hit), (0.6, hit), (1, guard)]), {"face": "angry"}


def a_slap(t, dur, ctx):
    """A slap: the hand goes up and back, then sweeps across at face height."""
    u = t / max(dur, 0.1)
    wind = P(**{**STAND, "af_u": 150, "af_l": 40, "torso": -6, "head": -4})
    hit = P(**{**STAND, "af_u": 88, "af_l": 4, "torso": 14, "head": -2, "ln_t": 18, "lf_t": -16})
    return keyframes(u, [(0, STAND), (0.35, wind), (0.5, hit), (0.65, hit), (1, STAND)]), {"face": "angry"}


def a_hit(t, dur, ctx):
    """Hit: the head snaps back (or round, for a slap), the body rocks back, arms fly up, then recovers."""
    u = t / max(dur, 0.1)
    slap = ctx.get("params", {}).get("_by") == "slap"
    snap = P(torso=-16, head=-30 if not slap else 22, an_u=60, an_l=40, af_u=40, af_l=50, ln_t=-12, ln_s=-6, lf_t=10,
             lf_s=-4)
    return keyframes(u, [(0, STAND), (0.15, snap), (0.5, add(snap, torso=6, head=10)), (1, STAND)]), \
        {"face": "surprised" if u < 0.5 else "angry"}


def a_block(t, dur, ctx):
    """Blocking: both forearms up in front of the face, leaning away a little."""
    u = t / max(dur, 0.1)
    blk = P(**{**STAND, **arms_to((26, 54), (22, 56), bend="down"), "torso": -6, "head": 6, "ln_t": 10, "lf_t": -14})
    return keyframes(u, [(0, STAND), (0.2, blk), (0.8, blk), (1, STAND)]), {"face": "angry"}


def a_knocked_out(t, dur, ctx):
    """Knocked out: flies back off the feet and lands flat on the back, dizzy."""
    u = min(1.0, t / 0.7)
    pose = blend(add(STAND, torso=-20, head=-30, an_u=120, af_u=100), LIE_BACK, smoothstep(u))
    pose["lift"] = 30 * math.sin(math.pi * u) if u < 1 else 0.0
    return pose, {"face": "sad" if t > 0.7 else "surprised"}


WALK_STRIDE = 250.0      # distance per full walk cycle (two steps)
RUN_STRIDE = 330.0      # (a full cycle = two steps; with the locked feet this is about 3 steps a second)
WALK_SPEED = 230.0       # default world units / second
RUN_SPEED = 520.0


# ------------------------------------------------------------------ daily life (the little routines of a film)
def _arms(pose, near=None, far=None):
    """set the near and/or far hand to a point (forward, up) from the shoulder"""
    q = dict(pose)
    if near is not None:
        q["an_u"], q["an_l"] = ik(near)
    if far is not None:
        q["af_u"], q["af_l"] = ik(far)
    return P(**q)


def a_brush_teeth(t, dur, ctx):
    """Brushing teeth: the brush hand at the mouth scrubbing quickly side to side, the other hand holds a mug"""
    u = t / max(dur, 0.1)
    scrub = _arms(STAND, near=(28 + 4 * math.sin(TAU * 4.5 * t), 34 + 2 * math.cos(TAU * 4.5 * t)), far=(18, 4))
    pose = keyframes(u, [(0, STAND), (0.12, scrub), (0.92, scrub), (1, STAND)])
    pose["head"] = pose.get("head", 0) + 2 * math.sin(TAU * 4.5 * t)
    return pose, {"mouth": 0.25}


def a_wash_face(t, dur, ctx):
    """Washing the face at the tap / hand pump: bend over, cupped hands scoop water up to the face again and again"""
    ph = (t / 1.4) % 1.0
    bend = P(**{**STAND, "torso": 30, "head": 10})
    low = _arms(bend, near=(30, -12), far=(26, -12))
    up = _arms(bend, near=(24, 40), far=(20, 40))
    pose = keyframes(ph, [(0, low), (0.4, up), (0.6, up), (1, low)])
    u = t / max(dur, 0.1)
    pose = blend(STAND, pose, smoothstep(min(1.0, u * 6)) * smoothstep(min(1.0, (1 - u) * 6)))
    return pose, {"face": "calm"}


def a_bathe(t, dur, ctx):
    """A bucket bath (as in an Indian home): crouched by the bucket, the mug dips, rises over the head and pours;
    the other hand rubs the hair"""
    ph = (t / 2.4) % 1.0
    dip = _arms(CROUCH, near=(14, 62 + 3 * math.sin(TAU * 3 * t)), far=(34, -36))
    lift = _arms(CROUCH, near=(14, 62 + 3 * math.sin(TAU * 3 * t)), far=(10, 70))
    pour = add(lift, af_l=lift["af_l"] + 50, head=-10)
    pose = keyframes(ph, [(0, dip), (0.35, lift), (0.55, pour), (0.8, pour), (1, dip)])
    u = t / max(dur, 0.1)
    pose = blend(STAND, pose, smoothstep(min(1.0, u * 5)) * smoothstep(min(1.0, (1 - u) * 5)))
    return pose, {"face": "happy" if 0.5 < ph < 0.85 else "calm", "mouth": 0.3 if 0.5 < ph < 0.85 else 0.0}


def a_stretch(t, dur, ctx):
    """Waking up: arms high over the head, leaning back, a big yawn, then arms down"""
    u = t / max(dur, 0.1)
    up = add(ARMS_UP, torso=-8, head=-14)
    pose = keyframes(u, [(0, STAND), (0.3, up), (0.7, add(up, an_u=up["an_u"] + 6)), (1, STAND)])
    yawn = math.sin(math.pi * clamp((u - 0.2) / 0.6, 0.0, 1.0))
    return pose, {"mouth": 0.8 * yawn, "face": "sleepy" if yawn > 0.3 else "neutral"}


def a_stir(t, dur, ctx):
    """Cooking: stirring a pot with a spoon in slow circles, leaning over it"""
    lean = P(**{**STAND, "torso": 12, "head": 8})
    a = TAU * 0.9 * t
    pose = _arms(lean, near=(32 + 6 * math.cos(a), -8 + 3 * math.sin(a)), far=(10, -24))
    u = t / max(dur, 0.1)
    return blend(STAND, pose, smoothstep(min(1.0, u * 6)) * smoothstep(min(1.0, (1 - u) * 6))), {}


def a_sweep(t, dur, ctx):
    """Sweeping the yard with a short broom: bent over, both hands low, swinging side to side"""
    bend = P(**{**STAND, "torso": 34, "head": 6, "ln_t": 14, "ln_s": -20, "lf_t": 6, "lf_s": -14})
    sw = 10 * math.sin(TAU * 1.1 * t)
    pose = _arms(bend, near=(30 + sw, -30), far=(22 + sw, -18))
    u = t / max(dur, 0.1)
    return blend(STAND, pose, smoothstep(min(1.0, u * 6)) * smoothstep(min(1.0, (1 - u) * 6))), {}


class ActionSpec:
    def __init__(self, fn, dur, persistent=False, moving=False, blend_in=0.28, speed=0.0, oneshot=False):
        self.fn, self.dur, self.persistent, self.moving = fn, dur, persistent, moving
        self.blend_in, self.speed, self.oneshot = blend_in, speed, oneshot


ACTIONS = {
    "idle": ActionSpec(a_idle, 1.0, persistent=True),
    "stand": ActionSpec(a_idle, 0.6, persistent=True, blend_in=0.6),
    "talk": ActionSpec(a_talk, 2.0),
    "walk": ActionSpec(a_walk, 0, moving=True, blend_in=0.25, speed=WALK_SPEED),
    "crawl": ActionSpec(a_crawl, 0, moving=True, blend_in=0.3, speed=WALK_SPEED * 0.35),
    "run": ActionSpec(a_run, 0, moving=True, blend_in=0.2, speed=RUN_SPEED),
    "jump": ActionSpec(a_jump, 1.1, blend_in=0.1, oneshot=True),
    "sit": ActionSpec(a_sit, 0.8, persistent=True, blend_in=0.7),
    "sleep": ActionSpec(a_sleep, 1.2, persistent=True, blend_in=1.0),
    "lie": ActionSpec(a_lie, 1.0, persistent=True, blend_in=0.9),
    "fall": ActionSpec(a_fall, 1.0, persistent=True, blend_in=0.35),
    "wave": ActionSpec(a_wave, 2.0),
    "point": ActionSpec(a_point, 1.8),
    "think": ActionSpec(a_think, 2.5, blend_in=0.45),
    "laugh": ActionSpec(a_laugh, 2.2),
    "cry": ActionSpec(a_cry, 2.8, blend_in=0.5),
    "sad": ActionSpec(a_sad, 2.0, persistent=True, blend_in=0.7),
    "clap": ActionSpec(a_clap, 2.0),
    "dance": ActionSpec(a_dance, 3.0),
    "celebrate": ActionSpec(a_celebrate, 2.0),
    "angry": ActionSpec(a_angry, 2.0),
    "surprised": ActionSpec(a_surprised, 1.4, blend_in=0.12),
    "scared": ActionSpec(a_scared, 2.0, blend_in=0.15),
    "shrug": ActionSpec(a_shrug, 1.4),
    "bow": ActionSpec(a_bow, 1.8, oneshot=True),
    "nod": ActionSpec(a_nod, 1.2),
    "hug": ActionSpec(a_hug, 2.2, blend_in=0.4),
    "kick": ActionSpec(a_kick, 0.8, blend_in=0.1, oneshot=True),
    "pick": ActionSpec(a_pick, 1.4, oneshot=True),
    "drop": ActionSpec(a_drop, 1.4, oneshot=True),
    "put": ActionSpec(a_put, 1.4, oneshot=True),
    "give": ActionSpec(a_give, 1.4, oneshot=True),
    "look_around": ActionSpec(a_look_around, 2.0),
    "turn": ActionSpec(a_turn, 0.3, blend_in=0.1),
    "struggle": ActionSpec(a_struggle, 3.0, blend_in=0.3),
    "ride": ActionSpec(a_ride, 0.5, persistent=True, blend_in=0.3),
    "mount": ActionSpec(a_mount, 0.6, persistent=True, blend_in=0.35),
    "appear": ActionSpec(a_appear, 0.6, persistent=True, blend_in=0.0),
    "disappear": ActionSpec(a_disappear, 0.6, persistent=True, blend_in=0.0),
    # working with objects (see engine/objects.py; the timeline adds the object movement)
    "push": ActionSpec(a_push, 0, moving=True, blend_in=0.3, speed=110),
    "pull": ActionSpec(a_pull, 0, moving=True, blend_in=0.3, speed=90),
    "throw": ActionSpec(a_throw, 0.9, blend_in=0.1, oneshot=True),
    "climb": ActionSpec(a_climb, 1.5, persistent=True, blend_in=0.3),
    "hide": ActionSpec(a_hide, 0.7, persistent=True, blend_in=0.45),
    "peek": ActionSpec(a_peek, 1.0, persistent=True, blend_in=0.4),
    "open": ActionSpec(a_open, 1.2, oneshot=True, blend_in=0.2),
    "smash": ActionSpec(a_smash, 1.0, oneshot=True, blend_in=0.1),
    "sit_on": ActionSpec(a_sit_on, 0.8, persistent=True, blend_in=0.5),
    "perch": ActionSpec(a_perch, 0.8, persistent=True, blend_in=0.4),
    "step_up": ActionSpec(a_step_up, 0.7, persistent=True, blend_in=0.15),
    "hop_down": ActionSpec(a_hop_down, 0.6, oneshot=True, blend_in=0.1),
    # everyday actions
    "look_down": ActionSpec(a_look_down, 1.6, blend_in=0.35),
    "check_shoe": ActionSpec(a_check_shoe, 2.2, oneshot=True, blend_in=0.2),
    "look_up": ActionSpec(a_look_up, 1.6, blend_in=0.35),
    "feel_rain": ActionSpec(a_feel_rain, 2.2, blend_in=0.35),
    "cover_head": ActionSpec(a_cover_head, 3.0, blend_in=0.3),
    "brace_wind": ActionSpec(a_brace_wind, 4.0, blend_in=0.3),
    "look_back": ActionSpec(a_look_back, 1.6, blend_in=0.25),
    "look_at": ActionSpec(a_look_at, 1.2, persistent=True, blend_in=0.3),
    "carry": ActionSpec(a_carry, 0, moving=True, blend_in=0.3, speed=170),
    "carried": ActionSpec(a_carried, 0.6, persistent=True, blend_in=0.4),
    "sit_up": ActionSpec(a_sit_up, 1.2, persistent=True, blend_in=0.8),
    "roll_over": ActionSpec(a_roll_over, 1.6, persistent=True, blend_in=0.2),
    "drink": ActionSpec(a_drink, 2.2, blend_in=0.3),
    "brush_teeth": ActionSpec(a_brush_teeth, 3.5, blend_in=0.3),
    "wash_face": ActionSpec(a_wash_face, 3.0, blend_in=0.3),
    "bathe": ActionSpec(a_bathe, 5.0, blend_in=0.5),
    "stretch": ActionSpec(a_stretch, 2.4, blend_in=0.3),
    "stir": ActionSpec(a_stir, 3.0, blend_in=0.3),
    "sweep": ActionSpec(a_sweep, 3.5, blend_in=0.3),
    "eat": ActionSpec(a_eat, 2.7, blend_in=0.3),
    "reach": ActionSpec(a_reach, 1.8, blend_in=0.3),
    "touch": ActionSpec(a_touch, 1.6, blend_in=0.3),
    "pull_hand_back": ActionSpec(a_pull_hand_back, 0.9, blend_in=0.06),
    "shout": ActionSpec(a_shout, 1.8, blend_in=0.15),
    "retreat": ActionSpec(a_retreat, 0, moving=True, blend_in=0.2, speed=140),
    "fight": ActionSpec(a_fight, 3.0, blend_in=0.2),
    "shove": ActionSpec(a_shove, 1.0, blend_in=0.1, oneshot=True),
    "stumble": ActionSpec(a_stumble, 0, moving=True, blend_in=0.08, speed=220),
    "wake": ActionSpec(a_wake, 2.4, blend_in=0.2),
    "stop": ActionSpec(a_stop, 1.4, blend_in=0.15),
    # 💞 two people together (engine/duets.py places both; used alone they still read)
    "hug_pair": ActionSpec(a_hug_pair, 2.6, blend_in=0.3),
    "kiss": ActionSpec(a_kiss, 2.0, blend_in=0.3),
    "kissed": ActionSpec(a_kissed, 2.0, blend_in=0.3),
    "hold_hands": ActionSpec(a_hold_hands, 2.5, blend_in=0.4),
    "couple_dance": ActionSpec(a_couple_dance, 5.0, blend_in=0.4),
    "kneel_propose": ActionSpec(a_kneel_propose, 3.0, persistent=True, blend_in=0.3),
    "overjoyed": ActionSpec(a_overjoyed, 2.2, blend_in=0.15),
    "lift_person": ActionSpec(a_lift_person, 1.1, blend_in=0.2),
    "throw_person": ActionSpec(a_throw_person, 1.0, blend_in=0.1, oneshot=True),
    "flung": ActionSpec(a_flung, 1.0, moving=True, blend_in=0.05),
    "punch": ActionSpec(a_punch, 0.7, blend_in=0.1, oneshot=True),
    "slap": ActionSpec(a_slap, 0.75, blend_in=0.1, oneshot=True),
    "hit": ActionSpec(a_hit, 0.7, blend_in=0.05, oneshot=True),
    "block": ActionSpec(a_block, 0.7, blend_in=0.08, oneshot=True),
    "knocked_out": ActionSpec(a_knocked_out, 1.0, persistent=True, blend_in=0.05),
}

ALIASES = {
    "walking": "walk", "enter": "walk", "exit": "walk", "leave": "walk", "go": "walk",
    "move": "walk", "running": "run", "sprint": "run", "chase": "run", "sitting": "sit",
    "sit_down": "sit", "stand_up": "stand", "get_up": "stand", "wake_up": "wake", "awake": "wake",
    "brace": "brace_wind", "fight_wind": "brace_wind", "lean_wind": "brace_wind", "windy": "brace_wind",
    "yawn": "wake", "stretch": "wake", "look_downward": "look_down", "shake_foot": "check_shoe", "muddy_shoe": "check_shoe",
    "look_at_shoe": "check_shoe", "look_upward": "look_up", "look_up_at": "look_up",
    "look_over_shoulder": "look_back", "glance_back": "look_back", "turn_back": "look_back", "stare": "look_at",
    "look_towards": "look_at", "look_toward": "look_at", "watch": "look_at", "gaze": "look_at", "face": "look_at",
    "hold": "carry", "carrying": "carry", "sip": "drink", "drinking": "drink", "eating": "eat", "bite": "eat",
    "chew": "eat", "reach_out": "reach", "reach_for": "reach", "stretch_hand": "reach", "tap": "touch",
    "feel": "touch", "pet": "touch", "pat": "touch", "withdraw_hand": "pull_hand_back", "pull_back_hand": "pull_hand_back",
    "flinch": "pull_hand_back", "yell": "shout", "scream": "shout", "call_out": "shout", "back_away": "retreat",
    "step_back": "retreat", "back_off": "retreat", "move_back": "retreat", "box": "fight",
    "hit_person": "fight", "boxing": "fight", "brawl": "fight", "stagger": "stumble", "halt": "stop",
    "stop_gesture": "stop", "go_to": "walk",
    "sleeping": "sleep", "lie_down": "lie", "jumping": "jump", "hop": "jump",
    "talking": "talk", "speak": "talk", "laughing": "laugh", "crying": "cry", "weep": "cry",
    "brush": "brush_teeth", "brushing": "brush_teeth", "brush_teeth_": "brush_teeth", "wash": "wash_face",
    "washing_face": "wash_face", "bath": "bathe", "bathing": "bathe", "take_bath": "bathe", "nahana": "bathe",
    "yawn": "stretch", "wake_up_stretch": "stretch", "cook": "stir", "cooking": "stir", "stirring": "stir",
    "sweeping": "sweep", "jhadu": "sweep",
    "waving": "wave", "pointing": "point", "thinking": "think", "clapping": "clap",
    "dancing": "dance", "cheer": "celebrate", "yay": "celebrate", "shock": "surprised",
    "shocked": "surprised", "surprise": "surprised", "afraid": "scared", "fear": "scared",
    "frightened": "scared", "pick_up": "pick", "pickup": "pick", "grab": "pick", "take": "pick",
    "put_down": "drop", "trip": "fall", "hide": "disappear", "vanish": "disappear",
    "wait": "idle", "rest": "idle", "look": "look_around", "search": "look_around",
    "mad": "angry", "upset": "sad", "hand_over": "give", "embrace": "hug", "resist": "struggle",
    "windy": "struggle", "brace": "struggle", "board": "ride", "get_in": "ride", "enter_vehicle": "ride",
    "drive": "ride", "cycle": "ride", "get_out": "stand", "exit_vehicle": "stand",
}

FACES = ("neutral", "happy", "sad", "angry", "surprised", "scared", "laughing",
         "crying", "sleeping", "thinking")


def resolve_action(name):
    """Map an action name (possibly misspelled by the AI) to a known action."""
    import difflib
    key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    if key not in ACTIONS:
        try:                                      # moves imported from Mixamo (engine/mocap.py)
            from . import mocap
            mocap.register()
        except Exception:
            pass
    if key in ACTIONS:
        return key, None
    if key in ALIASES:
        return ALIASES[key], None
    close = difflib.get_close_matches(key, list(ACTIONS) + list(ALIASES), n=1, cutoff=0.6)
    if close:
        k = close[0]
        return ALIASES.get(k, k), f"unknown action '{name}', using '{ALIASES.get(k, k)}'"
    return "idle", f"unknown action '{name}', using 'idle'"
