"""Pacing checker: finds dull stretches and missing "big moments", and can fix dull stretches
automatically with camera variety.

Research-based targets (animated YouTube videos): something new every 20-30 s, interest peaks near
25 / 50 / 75 % of the story, and the main problem shown within the first 15 s.
"""

BIG_ACTIONS = {"surprised", "scared", "jump", "pounce", "fall", "celebrate", "run", "roar", "dance", "cry", "laugh",
               "angry", "hug", "kick", "fly", "struggle", "give", "ride"}
BIG_EMOTIONS = {"surprised", "scared", "angry", "crying", "laughing"}
BIG_CAMERA = {"shake", "punch", "closeup", "impact", "push_in", "zoom_pulse"}
GAP = 25.0


def _scene_moments(it):
    """[(time, kind, big)] for one scene item, in video time."""
    sc, T = it.scene, it.start
    out = []
    for sp in sc.speeches:
        out.append((T + sp.start, "speech", sp.emotion in BIG_EMOTIONS))
    for tr in list(sc.tracks.values()):
        for s in tr.segments:
            if s.action in ("idle", "stand"):
                continue
            out.append((T + s.start, "action:" + s.action, s.action in BIG_ACTIONS or (s.emotion in BIG_EMOTIONS)))
        for st, kind in tr.icons:
            out.append((T + st, "icon", kind in ("!", "stars", "anger")))
    for t, cmd in sc.camera:
        out.append((T + t, "camera:" + cmd["type"], cmd["type"] in BIG_CAMERA))
    for t, name, *_ in sc.sfx:
        out.append((T + t, "sfx", name in ("crash", "thunder", "boing", "tada", "roar", "trumpet", "explosion")))
    for e in sc.effects:
        out.append((T + e["start"], "effect:" + e["kind"], e["kind"] not in ("dust",)))
    for p in sc.props.values():
        for t, st in p.states:
            if st[0] == "move":
                out.append((T + t, "move", bool(p.vtype)))
    return sorted(out)


def analyze(P):
    """-> list of {"level", "time", "scene", "message"}"""
    issues = []
    scenes = [it for it in P.items if it.kind == "scene"]
    if not scenes:
        return issues
    all_m = []
    for idx, it in enumerate(scenes):
        m = _scene_moments(it)
        all_m += m
        times = [it.start] + [t for t, _, _ in m] + [it.end]
        for a, b in zip(times, times[1:]):
            if b - a >= GAP:
                issues.append(dict(level="warn", time=a, scene=it.scene.index + 1,
                                   message=f"{b - a:.0f}s with nothing new (from {fmt(a)} to {fmt(b)}) - add a camera "
                                           f"change, action, joke or twist"))
    first = scenes[0]
    early = [t for t, k, big in _scene_moments(first) if t - first.start <= 15 and (big or k == "speech")]
    if not early:
        issues.append(dict(level="warn", time=first.start, scene=first.scene.index + 1,
                           message="nothing happens in the first 15 seconds of scene 1 - show the problem earlier"))
    t0, t1 = scenes[0].start, scenes[-1].end
    total = t1 - t0
    bigs = [t for t, _, big in all_m if big]
    for q in (0.25, 0.5, 0.75):
        target = t0 + total * q
        if not any(abs(t - target) <= total * 0.12 for t in bigs):
            issues.append(dict(level="info", time=target, scene=None,
                               message=f"no big moment near {int(q * 100)}% ({fmt(target)}) - a surprise, chase, "
                                       f"shock or laugh here keeps viewers watching"))
    if total > 30:
        density = len([1 for _, k, _ in all_m if not k.startswith("camera")]) / (total / 60.0)
        if density < 6:
            issues.append(dict(level="info", time=t0, scene=None,
                               message=f"only {density:.0f} story beats per minute - aim for 8+ "
                                       f"(more dialogue, actions or scene changes)"))
    return sorted(issues, key=lambda i: i["time"])


def fix(P):
    """Break up dull stretches with alternating camera moves. Returns number of fixes."""
    from .camera import CameraDirector
    n = 0
    for it in P.items:
        if it.kind != "scene":
            continue
        sc = it.scene
        m = [t - it.start for t, _, _ in _scene_moments(it)]
        times = [0.0] + sorted(m) + [sc.duration]
        added = []
        for a, b in zip(times, times[1:]):
            gap = b - a
            if gap < GAP * 0.7:
                continue
            k = int(gap // 9)
            for j in range(1, k + 1):
                t = a + gap * j / (k + 1)
                speaker = next((sp.who for sp in sc.speeches if sp.start <= t < sp.end and sp.who in sc.tracks), None)
                target = speaker or next(iter(sc.tracks), None)
                kind = ("closeup" if (len(added) % 2 == 0 and target) else "wide")
                cmd = {"type": kind, "duration": 1.2}
                if kind == "closeup":
                    cmd.update(target=target, zoom=1.35)
                added.append((t, cmd))
                added.append((t + 4.0, {"type": "auto", "duration": 1.2}))
        if added:
            sc.camera = sorted(sc.camera + added, key=lambda c: c[0])
            n += len(added) // 2
            it.cams = CameraDirector(sc, P.fps, sc.world_w).path(int(round(sc.duration * P.fps)) + 2)
    return n


def fmt(t):
    m, s = divmod(int(max(t, 0)), 60)
    return f"{m}:{s:02d}"


def report(issues):
    if not issues:
        return "Pacing: looks good - something happens regularly and the big moments are well spread."
    lines = ["Pacing report:"]
    for i in issues:
        tag = "!" if i["level"] == "warn" else "i"
        sc = f"scene {i['scene']}, " if i["scene"] else ""
        lines.append(f"  [{tag}] {sc}{fmt(i['time'])}: {i['message']}")
    return "\n".join(lines)
