"""🌌 Our real Milky Way: a small catalogue of what is really measured, on top of the galaxy rules.

    shape       a barred spiral ~100 000 light years wide; the Sun 26 700 ly (8.2 kpc) from the middle, between the
                Sagittarius and Perseus arms on the small Orion Spur; Sagittarius A* (4.15 million Suns) in the middle;
                four main arms (Perseus, Sagittarius-Carina, Scutum-Centaurus, Norma) - logarithmic spirals ~12°
    STARS       the real known stars near us (distance, galactic longitude l / latitude b, mass, temperature, kind)
    PLANETS     their real known planets: orbit, size or mass, year - measured; the ground, air and weather nobody has
                measured yet are worked out by our rules and marked "estimated"
    OBJECTS     real black holes, nebulae and clusters
    the rest    the Milky Way's other 100-400 billion stars are made by the same rules as every galaxy, placed in its
                real shape (galaxy.star("milkyway", i))
Positions: map units (1 = 15 kpc) with the middle at (0, 0) and the Sun at (0, 0.547); l = 0 points to the middle,
l = 90° the way we turn round it.
"""
import math

from .util import clamp

LY_PER_KPC = 3261.56
SUN_KPC = 8.2
SUN_XY = (0.0, SUN_KPC / 15.0)
SHAPE = {"kind": "barred spiral", "arms": 4, "pitch": 12.0, "bar": 0.33, "bar_angle": 0.47, "clumps": [(0, 0)] * 4}

# name: (distance ly, l°, b°, mass Suns, T K, kind, radius Suns, notes)
STARS = {
    "alpha centauri a": (4.37, 315.7, -0.7, 1.10, 5790, "yellow star (G2)", 1.22, "with B: a pair 11-35 AU apart; Proxima circles both far out"),
    "alpha centauri b": (4.37, 315.7, -0.7, 0.91, 5260, "orange star (K1)", 0.86, "Alpha Centauri A's partner"),
    "proxima centauri": (4.24, 313.9, -1.9, 0.122, 3042, "red dwarf (M5.5)", 0.154, "the nearest star to the Sun; a flare star"),
    "barnard's star": (5.96, 31.0, 14.1, 0.16, 3134, "red dwarf (M4)", 0.19, "the fastest-moving star in our sky"),
    "wolf 359": (7.86, 244.0, 56.1, 0.11, 2800, "red dwarf (M6)", 0.14, "a small, dim flare star"),
    "sirius a": (8.6, 227.2, -8.9, 2.06, 9940, "white star (A1)", 1.71, "the brightest star in our night sky"),
    "sirius b": (8.6, 227.2, -8.9, 1.02, 25000, "white dwarf", 0.0084, "Sirius A's partner: a white dwarf, Earth-sized, as heavy as the Sun"),
    "epsilon eridani": (10.5, 195.8, -48.1, 0.82, 5084, "orange star (K2)", 0.74, "young (~0.5 billion years), with dust belts"),
    "ross 128": (11.0, 270.1, 59.5, 0.17, 3192, "red dwarf (M4)", 0.20, "a quiet red dwarf"),
    "tau ceti": (11.9, 173.1, -73.4, 0.78, 5344, "yellow-orange star (G8)", 0.79, "Sun-like, older and poorer in metals"),
    "altair": (16.7, 47.7, -8.9, 1.79, 7700, "white star (A7)", 1.8, "spins so fast it bulges at its equator"),
    "vega": (25.0, 67.4, 19.2, 2.14, 9600, "white star (A0)", 2.36, "a dusty disk round it; once the pole star, again in 12 000 years"),
    "trappist-1": (40.7, 69.7, -56.6, 0.0898, 2566, "red dwarf (M8)", 0.119, "seven Earth-sized planets, all closer than Mercury"),
    "51 pegasi": (50.6, 90.1, -34.7, 1.11, 5768, "yellow star (G2)", 1.27, "the first Sun-like star found with a planet (1995)"),
    "polaris": (433.0, 123.3, 26.5, 5.4, 6015, "yellow supergiant (F7)", 37.5, "the North Star: right above Earth's north pole"),
    "betelgeuse": (548.0, 199.8, -9.0, 18.0, 3600, "red supergiant", 764.0, "will explode as a supernova (within ~100 000 years)"),
    "kepler-186": (579.0, 76.0, 13.0, 0.54, 3755, "red dwarf (M1)", 0.52, "Kepler-186f: the first Earth-sized planet in a habitable zone"),
    "rigel": (860.0, 209.2, -25.2, 21.0, 12100, "blue supergiant (B8)", 79.0, "a young giant, 100 000× brighter than the Sun"),
    "kepler-452": (1800.0, 76.0, 13.5, 1.04, 5757, "yellow star (G2)", 1.11, "an older cousin of the Sun"),
}
# planet: (star, a AU, year days, radius Earths or None, mass Earths or None, T_eq K, note)
PLANETS = {
    "proxima b": ("proxima centauri", 0.0485, 11.19, None, 1.07, 234, "the nearest planet outside the Solar System, in its star's habitable zone"),
    "proxima d": ("proxima centauri", 0.0289, 5.12, None, 0.26, 360, "a small hot world"),
    "barnard b": ("barnard's star", 0.0229, 3.15, None, 0.37, 400, "found in 2024"),
    "ross 128 b": ("ross 128", 0.0496, 9.87, None, 1.40, 280, "a temperate world round a quiet star"),
    "epsilon eridani b": ("epsilon eridani", 3.48, 2690.0, None, 210.0, 120, "a gas giant like Jupiter"),
    "tau ceti e": ("tau ceti", 0.538, 162.9, None, 3.9, 320, "a super-Earth (a candidate)"),
    "tau ceti f": ("tau ceti", 1.334, 636.1, None, 3.9, 200, "a cold super-Earth (a candidate)"),
    "trappist-1b": ("trappist-1", 0.01154, 1.511, 1.116, 1.374, 400, "JWST: no thick air"),
    "trappist-1c": ("trappist-1", 0.01580, 2.422, 1.097, 1.308, 342, "JWST: no thick CO₂ air"),
    "trappist-1d": ("trappist-1", 0.02227, 4.050, 0.788, 0.388, 288, ""),
    "trappist-1e": ("trappist-1", 0.02925, 6.101, 0.920, 0.692, 251, "the best bet for liquid water in the system"),
    "trappist-1f": ("trappist-1", 0.03849, 9.207, 1.045, 1.039, 219, ""),
    "trappist-1g": ("trappist-1", 0.04683, 12.352, 1.129, 1.321, 198, ""),
    "trappist-1h": ("trappist-1", 0.06189, 18.773, 0.755, 0.326, 173, ""),
    "51 pegasi b": ("51 pegasi", 0.0527, 4.23, 15.0, 146.0, 1260, "the first planet found round a Sun-like star (1995): a hot Jupiter"),
    "kepler-186f": ("kepler-186", 0.432, 129.9, 1.17, None, 188, "Earth-sized, at the cool edge of its habitable zone"),
    "kepler-452b": ("kepler-452", 1.046, 384.8, 1.63, None, 265, "a year of 385 days round a Sun-like star"),
}
# objects: (kind, distance ly, l°, b°, extra)
OBJECTS = {
    "sagittarius a*": ("black hole", 26700.0, 0.0, 0.0, {"mass_sun": 4.15e6, "note": "the supermassive black hole in the middle (imaged in 2022)"}),
    "gaia bh1": ("black hole", 1560.0, 21.7, 17.3, {"mass_sun": 9.6, "note": "the nearest known black hole, with a Sun-like star circling it (2022)"}),
    "cygnus x-1": ("black hole", 7200.0, 71.3, 3.1, {"mass_sun": 21.2, "note": "the first black hole found (1964-72): it eats from a blue supergiant"}),
    "orion nebula": ("nebula", 1344.0, 209.0, -19.4, {"colour": "#ff6f9d", "note": "a star nursery you can see with your eyes, below Orion's belt"}),
    "eagle nebula": ("nebula", 5700.0, 17.0, 0.8, {"colour": "#e6a06a", "note": "the Pillars of Creation - towers of gas where stars are born"}),
    "crab nebula": ("supernova remnant", 6500.0, 184.6, -5.8, {"note": "a star that blew up in 1054 (seen from Earth); its pulsar spins 30× a second"}),
    "pleiades": ("open cluster", 444.0, 166.6, -23.5, {"note": "the Seven Sisters: ~1 000 young stars, ~100 million years old"}),
    "omega centauri": ("globular cluster", 17090.0, 309.1, 15.0, {"note": "~10 million very old stars (~11.5 billion years), maybe an eaten galaxy's core"}),
}
VOYAGER_KMS = 17.0
FEH = {"proxima centauri": 0.21, "barnard's star": -0.4, "ross 128": -0.02, "epsilon eridani": -0.09, "tau ceti": -0.5,
       "trappist-1": 0.04, "51 pegasi": 0.2, "kepler-186": -0.26, "kepler-452": 0.21}     # measured [Fe/H]


def xy(dist_ly, l_deg):
    """map position (units of 15 kpc) of something dist_ly away toward galactic longitude l (seen from the Sun)"""
    d = dist_ly / LY_PER_KPC / 15.0
    return SUN_XY[0] + d * math.sin(math.radians(l_deg)), SUN_XY[1] - d * math.cos(math.radians(l_deg))


def arms():
    """the four main arms as log spirals with real names, set so the Sun sits between Sagittarius and Perseus"""
    tp = math.tan(math.radians(SHAPE["pitch"]))
    sun_r, sun_th = math.hypot(*SUN_XY), math.atan2(SUN_XY[1], SUN_XY[0])
    base = sun_th - math.log(sun_r / 0.05) / tp + math.pi / 4
    out = []
    for k in range(4):
        ph = base + k * math.pi / 2
        # where this arm crosses the Sun's direction (radii)
        cross = [0.05 * math.exp((sun_th - ph + 2 * math.pi * n) * tp) for n in range(-3, 4)]
        out.append({"phase": ph, "cross": sorted(c for c in cross if 0.08 < c < 1.2)})
    outer = min((a for a in out if any(c > sun_r for c in a["cross"])), key=lambda a: min(c for c in a["cross"] if c > sun_r))
    inner = max((a for a in out if a is not outer and any(c < sun_r for c in a["cross"])), key=lambda a: max(c for c in a["cross"] if c < sun_r))
    rest = [a for a in out if a is not outer and a is not inner]
    names = {id(outer): "Perseus Arm", id(inner): "Sagittarius-Carina Arm", id(rest[0]): "Scutum-Centaurus Arm", id(rest[1]): "Norma Arm"}
    return [{"name": names[id(a)], "phase": round(a["phase"] % (2 * math.pi), 4)} for a in out]


def galaxy_shape():
    return dict(SHAPE, phase0=arms()[0]["phase"])


def catalogue():
    """everything real, with map positions, for the Milky Way map / list"""
    stars = []
    for n, (d, l, b, m, T, kind, R, note) in STARS.items():
        x, y = xy(d, l)
        stars.append({"name": nice(n, True), "key": n, "ly": d, "l": l, "b": b, "mass": m, "temperature": T, "kind": kind,
                      "radius": R, "note": note, "x": round(x, 5), "y": round(y, 5), "colour": _star_colour(T),
                      "planets": [k for k, v in PLANETS.items() if v[0] == n]})
    objs = []
    for n, (kind, d, l, b, ex) in OBJECTS.items():
        x, y = (0.0, 0.0) if n == "sagittarius a*" else xy(d, l)
        objs.append(dict(ex, name=nice(n).replace("Bh1", "BH1").replace("X-1", "X-1") if n != "sagittarius a*" else "Sagittarius A*", key=n, kind=kind, ly=d, x=round(x, 4), y=round(y, 4)))
    return {"sun": SUN_XY, "stars": stars, "objects": objs, "arms": arms(), "shape": galaxy_shape(),
            "address": ["Earth", "the Solar System (8 planets round the Sun)", "the Local Bubble of nearby stars",
                        "the Orion Spur, between the Sagittarius and Perseus arms", f"the Milky Way, {SUN_KPC * LY_PER_KPC:,.0f} light years from its middle",
                        "the Local Group (with Andromeda, 2.5 million light years away)", "the Virgo Supercluster"]}


def nice(k, star=False):
    """'trappist-1e' -> 'TRAPPIST-1e', 'proxima b' -> 'Proxima b', 'wolf 359' -> 'Wolf 359'"""
    return " ".join((w.upper() if star else w) if len(w) == 1 else w[0].upper() + w[1:] for w in k.split()).replace("Trappist-1", "TRAPPIST-1")


_SHAPE = None


def galaxy_shape_cached():
    global _SHAPE
    if _SHAPE is None:
        _SHAPE = galaxy_shape()
    return _SHAPE


def _star_colour(T):
    from .galaxy import star_colour
    return star_colour(T)


def planet(key):
    """a real known planet as a planet dict: measured numbers + the rules for what nobody has measured (marked)"""
    from . import galaxy
    key = str(key).lower().strip()
    if key not in PLANETS:
        return None
    sname, a, year, R, M, Teq, note = PLANETS[key]
    d, l, b, ms, Ts, kind, Rs, _ = STARS[sname]
    est = []
    if R is None:                                       # only the mass is measured (radial velocity): size by the rocky rule
        R = M ** 0.27 if M < 10 else (M ** 0.55 if M < 120 else 11.0)
        est.append("radius")
    if M is None:                                       # only the size is measured (transits): mass by the rocky rule
        M = R ** 3.7 if R < 1.5 else R ** 3.3 if R < 2.0 else R ** 2.06 * 2.7      # (Kepler-452b ≈ 5 Earths)
        est.append("mass")
    gas = M > 15 or R > 3.0
    g = 9.81 * M / (R * R)
    v_esc = 11.2 * math.sqrt(M / R)
    v_gas = 0.517 * math.sqrt(Teq / 300.0)
    keeps = gas or (v_esc > 7.0 * v_gas and M > 0.08)
    flare = Ts < 3700 and a < 0.15                       # a red dwarf's flares strip close planets (JWST sees bare TRAPPIST-1 b, c)
    if key in ("trappist-1b", "trappist-1c"):
        keeps = False
    elif flare and not gas and keeps and M < 1.0:
        keeps = False
    pressure = 0.0 if not keeps else (round(clamp(M, 0.3, 5), 2) if not gas else 50.0)
    T = Teq + (0 if not keeps else (33 * min(1.5, pressure) if not gas else 0))
    Tc = T - 273.15
    water = "none" if gas else ("ice" if Tc < -10 else "oceans" if (keeps and Tc < 90) else "none")
    est += ["air", "temperature (equilibrium + a greenhouse guess)", "ground", "water", "weather"]
    data = {"name": nice(key),
            "type": "gas" if gas else ("ocean" if water == "oceans" else "ice" if water == "ice" else "rocky"),
            "radius": round(R, 3), "mass": round(M, 3), "gravity": round(g / 9.81, 3), "atmosphere": bool(keeps),
            "pressure": pressure, "air_mix": "hydrogen,helium" if gas else ("nitrogen,co2" if keeps else ""),
            "temperature": round(T), "year_days": year, "day_hours": round(year * 24, 1), "water": water, "life": False,
            "moons": 0, "rings": False, "star": {"name": nice(sname, True), "kind": kind, "colour": _star_colour(Ts), "temperature": Ts,
                                                  "size": round(Rs / a, 4)}}
    p = galaxy.from_data(data)
    lum = (Rs ** 2) * (Ts / 5778.0) ** 4
    a_lock = 0.5 * ms ** (1 / 3)
    p.update(mw=key, real_star=sname, rules=2, star_stage="main" if "dwarf" not in kind or "red" in kind else "white dwarf",
             star_flux=round(lum / a ** 2, 6), tidal_lock=a < a_lock and not gas, distance_au=a, distance_ly=d, galaxy_r_kpc=round(
                 math.hypot(*xy(d, l)) * 15, 2), star_class=kind.split("(")[-1].rstrip(")")[:1] if "(" in kind else "-",
             star_notes=[note] if note else [], measured=["orbit", "year"] + (["radius"] if "radius" not in est else []) + (["mass"] if "mass" not in est else []),
             estimated=est, real_world=True)
    if p["tidal_lock"]:
        p["star_notes"].append("tidally locked (very likely so close to a small star): one side always day, one always night")
    p["star_notes"].append("measured: " + ", ".join(p["measured"]) + " · estimated by our rules: " + ", ".join(est))
    return p


def find_planet(name):
    """'proxima b', 'trappist-1e', 'TRAPPIST-1 e' ... -> a planet dict or None"""
    n = str(name).lower().strip().replace("trappist-1 ", "trappist-1").replace("’", "'")
    return planet(n) if n in PLANETS else None


def travel(name_b):
    """the honest trip numbers from Earth to a real star / planet"""
    key = str(name_b).lower()
    sname = PLANETS[key][0] if key in PLANETS else key
    if sname not in STARS:
        return None
    d = STARS[sname][0]
    years = d * 9.4607e12 / VOYAGER_KMS / 3.156e7
    return {"ly": d, "dist": f"{d:g} light years ({d * 9.4607e12:,.3g} km)",
            "time": f"light takes {d:g} years; today's fastest probe (Voyager 1, 17 km/s) would need ≈ {years:,.0f} years"}
