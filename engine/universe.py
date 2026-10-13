"""🌌 The universe of the game: our Milky Way, nothing else (🎮 game rule: one galaxy you can know by heart - its nine regions
are the journey, engine/regions.py). The other 999 galaxies of the old game are gone from maps and jumps; an old world's
address there still loads, and its only way out is home to the Milky Way.

    places    every galaxy has a fixed spot in a ball ~40 million light years across (about the size of our real
              "Local Volume", which holds a few hundred to a thousand galaxies); the Milky Way sits in the middle
    links     each galaxy is linked to its 3 nearest, plus the links that join every group into ONE web (a minimum
              spanning tree) - so from any galaxy you can reach any other, jump by jump
    travel    🚀 flying between galaxies (real physics): impossible - millions of light years, and the ramscoop has
              almost nothing to drink out there (~1 atom per cubic metre: a million times thinner than inside a galaxy)
              ⚡ fast drive (a GAME RULE, not real physics - nothing real goes faster than light): a jump along a link,
              for a lot of fusion fuel (FAST_FUEL)
"""
import hashlib
import math

N = 999
R_MLY = 20.0                                 # the ball's radius, million light years
FAST_FUEL = 25000.0                          # kg of fusion fuel per jump (🎮 the ship's engines need a tenth: 2.5 t of its 60 t tank - ship.FUEL_EFF)
_CACHE = {}


def clamp_seed(seed):
    """galaxy numbers are 1 .. 999 (or "milkyway")"""
    if str(seed).lower() == "milkyway":
        return "milkyway"
    try:
        s = int(seed)
    except (TypeError, ValueError):
        return 42
    return (s - 1) % N + 1


def _u(seed, k):
    h = hashlib.sha256(f"universe|{seed}|{k}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def pos(seed):
    """(x, y, z) in million light years"""
    if seed == "milkyway":
        return (0.0, 0.0, 0.0)
    r = R_MLY * _u(seed, "r") ** (1 / 3)                     # evenly through the ball
    th, ph = 2 * math.pi * _u(seed, "a"), math.acos(2 * _u(seed, "b") - 1)
    return (r * math.sin(ph) * math.cos(th), r * math.sin(ph) * math.sin(th), r * math.cos(ph))


def _graph():
    """the universe now: only the journey's galaxies (KEEP), each linked to the next on the road home"""
    if "g" in _CACHE:
        return _CACHE["g"]
    keep = KEEP()
    P = {i: pos(i) for i in keep}
    links = {i: set() for i in keep}
    for a, b in zip(keep, keep[1:]):
        links[a].add(b)
        links[b].add(a)
    _CACHE["g"] = (P, links)
    return _CACHE["g"]


def KEEP():
    """the galaxies there are: the Milky Way"""
    return ["milkyway"]


def _old_path(a, b):
    _, L = _full_graph()
    prev, q = {a: None}, [a]
    while q:
        x = q.pop(0)
        if x == b:
            break
        for y in L[x]:
            if y not in prev:
                prev[y] = x
                q.append(y)
    out, x = [], b
    while x is not None:
        out.append(x)
        x = prev.get(x)
    return list(reversed(out))


def _nearest_kept(seed):
    p = pos(seed)
    return min(KEEP(), key=lambda j: math.dist(p, pos(j)))


def _full_graph():
    """(the old web of all 999: only used to find the journey's road)"""
    if "full" in _CACHE:
        return _CACHE["full"]
    ids = ["milkyway"] + list(range(1, N + 1))
    P = {i: pos(i) for i in ids}
    links = {i: set() for i in ids}
    for i in ids:                                            # the 3 nearest
        near = sorted(ids, key=lambda j: math.dist(P[i], P[j]))[1:4]
        for j in near:
            links[i].add(j)
            links[j].add(i)
    # join every group into one web: Prim's minimum spanning tree over all galaxies (adds the short links needed)
    seen, best = {"milkyway"}, {}
    for j in ids:
        if j != "milkyway":
            best[j] = (math.dist(P["milkyway"], P[j]), "milkyway")
    while best:
        j = min(best, key=lambda k: best[k][0])
        d, i = best.pop(j)
        links[i].add(j)
        links[j].add(i)
        seen.add(j)
        for k in best:
            dk = math.dist(P[j], P[k])
            if dk < best[k][0]:
                best[k] = (dk, j)
    _CACHE["full"] = (P, links)
    return _CACHE["full"]


def neighbours(seed):
    P, L = _graph()
    seed = clamp_seed(seed)
    if seed not in L:                                        # (an old galaxy, off the map now: its way back is the nearest of the nine)
        return [_nearest_kept(seed)]
    return sorted(L[seed], key=lambda j: math.dist(P[seed], P[j]))


def linked(a, b):
    a, b = clamp_seed(a), clamp_seed(b)
    return b in neighbours(a)


def distance_mly(a, b):
    return math.dist(pos(clamp_seed(a)), pos(clamp_seed(b)))


def path(a, b):
    """the fewest jumps from galaxy a to galaxy b (breadth-first); from an old galaxy, through the nearest of the nine"""
    _, L = _graph()
    a, b = clamp_seed(a), clamp_seed(b)
    if b not in L:
        return []
    if a not in L:
        rest = path(_nearest_kept(a), b)
        return [a] + rest if rest else []
    prev, q = {a: None}, [a]
    while q:
        x = q.pop(0)
        if x == b:
            break
        for y in L[x]:
            if y not in prev:
                prev[y] = x
                q.append(y)
    out, x = [], b
    while x is not None:
        out.append(x)
        x = prev.get(x)
    return list(reversed(out)) if out and out[-1] == a else []


def arrival(seed, galaxy_mod):
    """where a jump into a galaxy comes out: the first star (of the first 40) with a solid world"""
    if seed == "milkyway":
        return {"solar": "earth"}
    for i in range(40):
        st = galaxy_mod.star(seed, i)
        for k in range(1, int(st.get("planets", 0)) + 1):
            if not galaxy_mod.planet(seed, i, k).get("gas"):
                return {"seed": seed, "star": i, "k": k}
    return {"seed": seed, "star": 0, "k": 1}


def all_galaxies():
    P, L = _graph()
    return [{"id": i, "pos": [round(v, 3) for v in P[i]], "links": sorted(L[i], key=str)} for i in P]
