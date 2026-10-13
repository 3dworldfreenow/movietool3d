"""Boids: flocks, schools, herds and crowds that move together (Python Playground ch. 5, Reynolds 1987).

Every member follows three local rules - keep apart from the ones too close (separation), fly / walk the same way as
the neighbours (alignment), stay with the group (cohesion) - plus, here, a goal to head for (the far side of the sky,
the herder, the way out) and something to run from (a tiger). Nothing is scripted per bird, yet the group swirls,
stretches and closes up like a real one.

The whole run is worked out ONCE (numpy, a few milliseconds) and kept, so any frame can be drawn on its own and
parallel rendering keeps working:
    sky birds   world3d / nature: a flock crossing the sky instead of a fixed V
    effects     "fish_school" (under the water), "butterflies" (round a flower bush)
    events      {"who": ["goat1", "goat2", "goat3"], "do": "herd", "follow": "ramu", "duration": 8}
                {"crowd": "flee", "from": "tiger"}   (the scene's crowd runs away together)
"""
import math

import numpy as np

_CACHE = {}


def simulate(n, seed, T, dt=1 / 15.0, start=(0.0, 0.0), spread=60.0, v0=(80.0, 0.0), goal=None, flee=None,
             speed=(60.0, 140.0), sep=(28.0, 1.6), ali=(90.0, 0.6), coh=(120.0, 0.35), goal_w=0.7, flee_r=420.0,
             flee_w=3.0, wander=0.25, bounds=None):
    """-> (pos (F, n, 2), vel (F, n, 2)) for a group of n.
    goal(t) -> (x, y) or None: where the group heads; flee(t) -> (x, y) or None: what it runs from.
    sep / ali / coh = (radius, weight). bounds = (x0, y0, x1, y1): gently kept inside."""
    key = (n, seed, round(T, 2), dt, start, spread, v0, id(goal), id(flee), speed, sep, ali, coh, goal_w, flee_r,
           flee_w, wander, bounds)
    got = _CACHE.get(key)
    if got is not None:
        return got
    rng = np.random.default_rng(seed)
    P = np.array(start, float) + rng.normal(0.0, spread, (n, 2))
    V = np.array(v0, float) + rng.normal(0.0, 15.0, (n, 2))
    F = int(T / dt) + 2
    pos = np.zeros((F, n, 2))
    vel = np.zeros((F, n, 2))
    lo, hi = speed
    for f in range(F):
        t = f * dt
        pos[f], vel[f] = P, V
        D = P[:, None, :] - P[None, :, :]                 # D[i, j] = P[i] - P[j]
        dist = np.sqrt((D ** 2).sum(-1)) + np.eye(n) * 1e9
        acc = np.zeros((n, 2))
        # separation: push away from the ones too close (stronger the closer)
        m = dist < sep[0]
        if m.any():
            k_ = np.where(m, (sep[0] - dist) / sep[0], 0.0)
            push = (D / np.maximum(dist, 1e-3)[..., None] * k_[..., None]).sum(1)
            acc += push * sep[1] * hi * 2.0
        # alignment: steer toward the neighbours' average heading
        m = dist < ali[0]
        cnt = m.sum(1)
        if cnt.any():
            avgv = (V[None, :, :] * m[..., None]).sum(1) / np.maximum(cnt, 1)[:, None]
            acc += np.where(cnt[:, None] > 0, (avgv - V) * ali[1], 0.0)
        # cohesion: steer toward the neighbours' centre
        m = dist < coh[0]
        cnt = m.sum(1)
        if cnt.any():
            ctr = (P[None, :, :] * m[..., None]).sum(1) / np.maximum(cnt, 1)[:, None]
            acc += np.where(cnt[:, None] > 0, (ctr - P) * coh[1], 0.0)
        if goal is not None:
            g = goal(t)
            if g is not None:
                d = np.array(g, float) - P
                L = np.sqrt((d ** 2).sum(-1, keepdims=True)) + 1e-6
                acc += (d / L * hi - V) * goal_w
        if flee is not None:
            q = flee(t)
            if q is not None:
                d = P - np.array(q, float)
                L = np.sqrt((d ** 2).sum(-1, keepdims=True)) + 1e-6
                near = np.clip(1.0 - L / flee_r, 0.0, 1.0)
                acc += d / L * hi * near * flee_w
        if bounds is not None:
            x0, y0, x1, y1 = bounds
            acc[:, 0] += np.clip(x0 - P[:, 0], 0, None) * 0.8 - np.clip(P[:, 0] - x1, 0, None) * 0.8
            acc[:, 1] += np.clip(y0 - P[:, 1], 0, None) * 0.8 - np.clip(P[:, 1] - y1, 0, None) * 0.8
        acc += rng.normal(0.0, wander * hi, (n, 2))
        V = V + acc * dt
        sp = np.sqrt((V ** 2).sum(-1, keepdims=True)) + 1e-6
        V = V / sp * np.clip(sp, lo, hi)
        P = P + V * dt
    if len(_CACHE) > 60:
        _CACHE.clear()
    _CACHE[key] = (pos, vel)
    return pos, vel


def at(sim, t, dt=1 / 15.0):
    """Positions and velocities at time t (interpolated)."""
    pos, vel = sim
    f = t / dt
    i = int(max(0, min(len(pos) - 2, math.floor(f))))
    u = max(0.0, min(1.0, f - i))
    return pos[i] * (1 - u) + pos[i + 1] * u, vel[i] * (1 - u) + vel[i + 1] * u


# ------------------------------------------------------------------ birds in the sky
_SKY = {}


def sky_flock(W, H, seed, period=16.0, n=11):
    """A flock that crosses a W x H sky (screen units, y down) in one period, left -> right or right -> left."""
    key = (W, H, seed, period, n)
    if key in _SKY:
        return _SKY[key]
    rng = np.random.default_rng(seed)
    left = bool(rng.integers(0, 2))
    y0 = H * rng.uniform(0.1, 0.25)
    x_from, x_to = (-0.15 * W, 1.25 * W) if left else (1.15 * W, -0.25 * W)

    def goal(t):
        u = t / period
        return (x_from + (x_to - x_from) * min(1.0, u + 0.25), y0 + 0.06 * H * math.sin(u * 5.0 + seed))
    sp = 1.4 * W / period
    sim = simulate(n, seed, period, start=(x_from, y0), spread=0.03 * W, v0=(sp if left else -sp, 0.0), goal=goal,
                   speed=(sp * 0.7, sp * 1.25), sep=(0.022 * W, 1.6), ali=(0.08 * W, 0.8), coh=(0.12 * W, 0.25),
                   goal_w=0.5, wander=0.12)
    _SKY[key] = sim
    return sim


def draw_birds(ctx, sim, t, S=1.0, col=(0.15, 0.17, 0.2), alpha=0.8, size=10.0, dx=0.0):
    P, V = at(sim, t)
    ctx.set_source_rgba(col[0], col[1], col[2], alpha)
    ctx.set_line_width(2.2 * S)
    for k in range(len(P)):
        x, y = P[k, 0] + dx, P[k, 1]
        vx = V[k, 0]
        f = math.sin(t * 9.0 + k * 1.3)
        w = size * S * (0.9 + 0.2 * ((k * 37) % 5) / 4.0)
        tilt = max(-0.4, min(0.4, V[k, 1] / max(1.0, abs(vx)))) * w * 0.4
        ctx.move_to(x - w, y - f * 5 * S - tilt)
        ctx.line_to(x, y + 2 * S)
        ctx.line_to(x + w, y - f * 5 * S + tilt)
        ctx.stroke()


# ------------------------------------------------------------------ fish and butterflies (effects)
def fish_school(ctx, age, dur, x, y, s, seed, inten):
    n = max(6, int(14 * inten))
    sim = simulate(n, seed, max(dur, 1.0) + 3.0, start=(x, y + 40 * s), spread=40 * s, v0=(70 * s, 0.0),
                   goal=lambda t: (x + 260 * s * math.sin(t * 0.45), y + 40 * s + 30 * s * math.sin(t * 0.8)),
                   speed=(50 * s, 120 * s), sep=(18 * s, 1.5), ali=(70 * s, 0.7), coh=(110 * s, 0.4), goal_w=0.4)
    P, V = at(sim, age)
    a = min(1.0, age / 0.4) * max(0.0, min(1.0, (dur + 2.5 - age) / 0.6))
    for k in range(n):
        px, py = P[k]
        ang = math.atan2(V[k, 1], V[k, 0])
        ctx.save()
        ctx.translate(px, py)
        ctx.rotate(ang)
        ctx.scale(11 * s, 4.5 * s)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgba(0.95, 0.6, 0.2, 0.75 * a)
        ctx.fill()
        ctx.move_to(px - math.cos(ang) * 10 * s, py - math.sin(ang) * 10 * s)
        ctx.line_to(px - math.cos(ang) * 17 * s - math.sin(ang) * 5 * s, py - math.sin(ang) * 17 * s + math.cos(ang) * 5 * s)
        ctx.line_to(px - math.cos(ang) * 17 * s + math.sin(ang) * 5 * s, py - math.sin(ang) * 17 * s - math.cos(ang) * 5 * s)
        ctx.close_path()
        ctx.fill()


def butterflies(ctx, age, dur, x, y, s, seed, inten):
    n = max(3, int(7 * inten))
    sim = simulate(n, seed, max(dur, 1.0) + 3.0, start=(x, y + 160 * s), spread=60 * s, v0=(30 * s, 10 * s),
                   goal=lambda t: (x + 120 * s * math.sin(t * 0.7), y + 170 * s + 60 * s * math.sin(t * 1.1)),
                   speed=(25 * s, 80 * s), sep=(30 * s, 1.2), ali=(40 * s, 0.1), coh=(160 * s, 0.15), goal_w=0.25,
                   wander=0.9)
    P, _V = at(sim, age)
    cols = [(0.98, 0.55, 0.15), (0.95, 0.85, 0.2), (0.4, 0.6, 0.95), (0.95, 0.4, 0.7)]
    for k in range(n):
        px, py = P[k]
        fl = abs(math.sin(age * 14 + k))
        c = cols[k % len(cols)]
        ctx.set_source_rgba(c[0], c[1], c[2], 0.95)
        for sd in (-1, 1):
            ctx.save()
            ctx.translate(px + sd * 5 * s * fl, py)
            ctx.scale(6 * s * (0.3 + fl), 7 * s)
            ctx.arc(0, 0, 1, 0, 2 * math.pi)
            ctx.restore()
            ctx.fill()


# ------------------------------------------------------------------ herds and crowds (story events)
def herd_paths(members, leader_path, T, seed, step=0.5, flee=None, speed=(80.0, 260.0), zk=2.0, solids=(),
               size=110.0):
    """members: [(x, z)] start spots; leader_path(t) -> (x, z) or None (the herder / the way to go);
    flee(t) -> (x, z) or None. -> [ [(t, x, z), ...] per member ] sampled every `step` seconds (story units;
    z is scaled by zk so depth and x count the same on the ground)."""
    n = len(members)
    start = np.array([(x, z * zk) for x, z in members], float)

    def goal(t):
        g = leader_path(t) if leader_path else None
        return None if g is None else (g[0], g[1] * zk)

    def run_from(t):
        q = flee(t) if flee else None
        return None if q is None else (q[0], q[1] * zk)
    out = []
    rects = [(ox, oz * zk, hw, hd * zk) for ox, oz, hw, hd in solids]
    sim2 = _simulate_from(start, seed, T, goal if leader_path else None, run_from if flee else None, speed, rects, size)
    P = sim2
    k = max(1, int(round(step * 15)))
    for i in range(n):
        out.append([(f / 15.0, float(P[f, i, 0]), float(P[f, i, 1]) / zk) for f in range(0, len(P), k)])
    return out


def _simulate_from(start, seed, T, goal, flee, speed, rects=(), size=110.0):
    rng = np.random.default_rng(seed)
    n = len(start)
    P = start.copy()
    V = rng.normal(0.0, 5.0, (n, 2))
    dt = 1 / 15.0
    F = int(T / dt) + 2
    out = np.zeros((F, n, 2))
    lo, hi = speed
    for f in range(F):
        t = f * dt
        out[f] = P
        D = P[:, None, :] - P[None, :, :]
        dist = np.sqrt((D ** 2).sum(-1)) + np.eye(n) * 1e9
        acc = np.zeros((n, 2))
        m = dist < size
        if m.any():
            k_ = np.where(m, (size - dist) / size, 0.0)
            acc += (D / np.maximum(dist, 1e-3)[..., None] * k_[..., None]).sum(1) * hi * 4.0
        m = dist < 200.0
        cnt = m.sum(1)
        avgv = (V[None, :, :] * m[..., None]).sum(1) / np.maximum(cnt, 1)[:, None]
        acc += np.where(cnt[:, None] > 0, (avgv - V) * 0.5, 0.0)
        m = dist < size * 3.0
        cnt = m.sum(1)
        ctr = (P[None, :, :] * m[..., None]).sum(1) / np.maximum(cnt, 1)[:, None]
        acc += np.where(cnt[:, None] > 0, (ctr - P) * 0.2, 0.0)
        want = np.zeros((n, 2))
        if goal is not None:
            g = goal(t)
            if g is not None:
                d = np.array(g, float) - P
                L = np.sqrt((d ** 2).sum(-1, keepdims=True)) + 1e-6
                slow = np.clip(L / 260.0, 0.0, 1.0)              # stop near the herder, do not trample him
                want += d / L * hi * slow * 0.8
        if flee is not None:
            q = flee(t)
            if q is not None:
                d = P - np.array(q, float)
                L = np.sqrt((d ** 2).sum(-1, keepdims=True)) + 1e-6
                near = np.clip(1.4 - L / 700.0, 0.0, 1.0)
                want += d / L * hi * near * 1.4
        acc += (want - V) * 1.2
        for ox, oz, hw, hd in rects:                          # walk round solid things (a well, a hut, a cart)
            dx, dz = P[:, 0] - ox, P[:, 1] - oz
            ex, ez = hw + 60.0, hd + 60.0
            inside = (np.abs(dx) < ex) & (np.abs(dz) < ez)
            if inside.any():
                px_, pz_ = ex - np.abs(dx), ez - np.abs(dz)
                along_x = px_ / ex < pz_ / ez
                acc[:, 0] += np.where(inside & along_x, np.sign(dx + 1e-6) * px_ * 12.0, 0.0)
                acc[:, 1] += np.where(inside & ~along_x, np.sign(dz + 1e-6) * pz_ * 12.0, 0.0)
        acc += rng.normal(0.0, 0.1 * hi, (n, 2))
        V = V + acc * dt
        sp = np.sqrt((V ** 2).sum(-1, keepdims=True)) + 1e-6
        V = V / sp * np.minimum(sp, hi)
        P = P + V * dt
        P[:, 1] = np.maximum(P[:, 1], 0.0)                     # never in front of the stage
        for ox, oz, hw, hd in rects:                          # and never inside one
            dx, dz = P[:, 0] - ox, P[:, 1] - oz
            inside = (np.abs(dx) < hw) & (np.abs(dz) < hd)
            if inside.any():
                px_, pz_ = hw - np.abs(dx), hd - np.abs(dz)
                along_x = px_ / hw < pz_ / hd
                P[:, 0] = np.where(inside & along_x, ox + np.sign(dx + 1e-6) * hw, P[:, 0])
                P[:, 1] = np.where(inside & ~along_x, oz + np.sign(dz + 1e-6) * hd, P[:, 1])
    del lo
    return out
