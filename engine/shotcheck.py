"""Shot check: after the story is built, look at the moment every line is spoken and check that the person
speaking can really be seen - like a script supervisor watching the monitor.

For each spoken line the frame is rendered small, with the speaker painted in flat magenta; counting the magenta
that survives tells how much of them the audience sees. Reported problems:
  hidden     most of the speaker is covered (by scenery, a vehicle, another person, the picture)
  cut off    the speaker is mostly outside the frame
  too small  the speaker is tiny (far away) while talking
  invisible  the speaker is hidden / not on stage while talking
The camera, the auto-director and the world rules are all included, so this is what the video will show.
"""
import numpy as np

from . import render as R


def _fmt(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _in_front(sc, tr, lt):
    """Another character standing in front of this one (nearer the camera, overlapping), if any."""
    try:
        x, z = tr.x_at(lt), tr.z_at(lt)
    except Exception:
        return None
    best = None
    for oid, o in sc.tracks.items():
        if o is tr:
            continue
        try:
            ox, oz = o.x_at(lt), o.z_at(lt)
        except Exception:
            continue
        if oz < z - 10 and abs(ox - x) < 110:
            if best is None or oz > best[0]:
                best = (oz, o.cdef.name)
    return best[1] if best else None


def check(P, log=None, limit=120):
    """Returns [{time, scene, who, name, problem, detail, line}] (time = seconds in the whole video)."""
    W, H = P.W, P.H
    out = []
    todo = []
    for it in P.items:
        if it.kind != "scene":
            continue
        sc = it.scene
        for sp in getattr(sc, "speeches", []):
            if sp.who not in sc.tracks:
                continue
            t_local = sp.start + min(sp.dur * 0.5, 1.4)
            todo.append((it, sc, sp, t_local))
    if len(todo) > limit:                                   # long stories: an even sample of the lines
        step = len(todo) / float(limit)
        todo = [todo[int(i * step)] for i in range(limit)]
    for n, (it, sc, sp, lt) in enumerate(todo):
        tr = sc.tracks[sp.who]
        t = it.start + lt
        name = tr.cdef.name
        line = str(getattr(sp, "text", "") or "")[:60]
        base = dict(time=round(t, 2), at=_fmt(t), scene=sc.index + 1, who=sp.who, name=name, line=line)
        try:
            st = tr.state(lt, sc)
        except Exception:
            continue
        if st.riding or tr.mounted_at(lt) is not None:
            continue                                        # inside a vehicle / on an animal: drawn differently
        i_ = tr.seg_index(lt)
        if i_ >= 0 and tr.segments[i_].action in ("hide", "peek"):
            continue                                        # hiding on purpose
        if st.alpha < 0.05:
            out.append(dict(base, problem="invisible", detail="is not visible (hidden or not on stage yet)"))
            continue
        for w in list(R._WORLDS.values()):
            w._tint_area = None
            w._tint_box = None
        R.SHOT_TINT[0] = sp.who
        try:
            R.render_frame(int(t * P.fps), P)
        finally:
            R.SHOT_TINT[0] = None
        area, box = None, None
        for w in R._WORLDS.values():
            if getattr(w, "_tint_area", None) is not None:
                area, box = w._tint_area, w._tint_box
        if area is None:
            continue                                        # 2D mode / drawn another way: can't tell
        surf = R._SURF
        a = np.ndarray((H, surf.get_stride() // 4), np.uint32, surf.get_data())[:, :W]
        r_, g_, b_ = (a >> 16) & 255, (a >> 8) & 255, a & 255
        r_, g_, b_ = r_.astype(np.int32), g_.astype(np.int32), b_.astype(np.int32)
        seen = int(((r_ > 1.6 * g_ + 18) & (b_ > 1.6 * g_ + 18) &              # magenta, even in night light
                    (np.abs(r_ - b_) < 0.45 * np.maximum(r_, b_) + 8)).sum())
        if box is not None:
            x0, y0, x1, y1 = box
            bw, bh = max(1.0, x1 - x0), max(1.0, y1 - y0)
            ix = max(0.0, min(x1, W) - max(x0, 0)) * max(0.0, min(y1, H) - max(y0, 0))
            inside = ix / (bw * bh)
            if inside < 0.45:
                out.append(dict(base, problem="cut off", detail=f"is {int((1 - inside) * 100)}% outside the frame"))
                continue
            if bh < 0.075 * H:
                out.append(dict(base, problem="too small",
                                detail=f"is tiny on screen ({int(bh / H * 100)}% of the height) - far away"))
                continue
        if area > 30:
            vis = seen / float(area)
            if vis < 0.45:
                who = _in_front(sc, tr, lt)
                out.append(dict(base, problem="hidden", detail=f"only {int(vis * 100)}% visible - "
                                + (f"standing behind {who}" if who else "something covers them")))
        if log and n % 10 == 9:
            log(f"  shot check {n + 1}/{len(todo)}")
    return out


def report(issues):
    if not issues:
        return "Shot check: every speaker can be seen. ✔"
    lines = [f"Shot check: {len(issues)} moment(s) to look at:"]
    for i in issues:
        lines.append(f"  {i['at']}  scene {i['scene']}  {i['name']} {i['detail']}"
                     + (f'  - "{i["line"]}"' if i.get("line") else ""))
    return "\n".join(lines)
