"""A rule-based galaxy: one number (a seed) + simple real physics build the stars, their planets and what each
planet is like. The same number always gives the same world; only what the story visits is ever worked out.

Story:
    settings  "galaxy": 42                                   the galaxy (any number)
    scene     "star": 7, "planet": 3                         planet 3 of star 7 of that galaxy
              "planet": "mars" | "moon" | "jupiter" ...      our own Solar System (a table of real values)
              "planet": "a warm planet with water"           the first planet of the galaxy that fits the words
The scene then becomes that planet: its ground, sky, the star's size and colour, moons and rings in the sky, its
weather (or none, with no air) and its gravity (people jump higher where it is weak, experiments use its g).

The rules (school level, simplified):
    star      mass M (in Suns) -> surface temperature T ≈ 5778 K · M^0.5 -> colour (red / yellow / white / blue),
              brightness L ≈ M^3.5, how many planets
    planet    distance a (AU) -> year = √(a³ / M) (Kepler), temperature ≈ 278 K · L^¼ / √a (+ greenhouse);
              size R and mass m -> gravity g = 9.81 · m / R², escape speed = 11.2 km/s · √(m / R);
              keeps an air if escape speed > ~6 × the speed of its gas (hot, small planets lose it);
              temperature + air -> ice / lakes / rain / dust / none; gas giants have no ground (a floating platform)
"""
import copy
import math
import random

from .util import clamp, stable_hash

G_EARTH = 9.81

# --------------------------------------------------------------------------- our own Solar System (real values)
#             g m/s²  air     T °C  ground     sky          weather   rings  moons  star size (Earth=1)   kind
SOLAR = {
    "moon":    (1.62, "none",  -20, "#9b9ea6", None,      "clear",  False, 0, 1.0, "rock"),
    "mercury": (3.70, "none",  170, "#8e8478", None,      "clear",  False, 0, 2.6, "rock"),
    "venus":   (8.87, "thick", 465, "#c99a52", "#e8b864", "storm",  False, 0, 1.4, "rock"),
    "earth":   (9.81, "thin",   15, "#7cc15a", "#8ec5ee", "clear",  False, 1, 1.0, "rock"),
    "mars":    (3.72, "thin",  -60, "#c1673e", "#e0b08a", "windy",  False, 2, 0.66, "rock"),
    "jupiter": (24.8, "thick", -110, "#d9a066", "#e8c49a", "storm", True, 4, 0.19, "gas"),
    "saturn":  (10.4, "thick", -140, "#e3cf8c", "#efdcae", "windy", True, 7, 0.10, "gas"),
    "uranus":  (8.87, "thick", -195, "#9fe0e6", "#bfeef2", "windy", True, 5, 0.05, "ice_giant"),
    "neptune": (11.2, "thick", -200, "#4f7fe6", "#7fa6f0", "storm", True, 6, 0.03, "ice_giant"),
    "pluto":   (0.62, "none", -230, "#d8c3a8", None,      "clear",  False, 1, 0.025, "ice"),
    # moons of the giants (real values) - squeezed by their planet: tidal heating
    "io":      (1.80, "none", -143, "#d9c35a", None,      "clear",  False, 0, 0.19, "rock"),
    "europa":  (1.31, "none", -160, "#d8cdbb", None,      "clear",  False, 0, 0.19, "ice"),
    "enceladus": (0.11, "none", -198, "#f0f5f8", None,    "clear",  False, 0, 0.10, "ice"),
    "titan":   (1.35, "thick", -179, "#8a6236", "#d79a4a", "clouds", False, 0, 0.10, "ice"),
    "ganymede": (1.43, "none", -163, "#8f877c", None,     "clear",  False, 0, 0.19, "ice"),
    "callisto": (1.24, "none", -139, "#6d6358", None,     "clear",  False, 0, 0.19, "ice"),
    "triton":  (0.78, "none", -235, "#c9b8b0", None,      "clear",  False, 0, 0.033, "ice"),    # (its nitrogen air is 14 millionths of a bar: none to a walker)
    "charon":  (0.29, "none", -220, "#9a948e", None,      "clear",  False, 0, 0.025, "ice"),
    # the biggest asteroids (Dawn mapped both)
    "ceres":   (0.28, "none", -105, "#5e5a56", None,      "clear",  False, 0, 0.36, "rock"),
    "vesta":   (0.25, "none", -98,  "#8a8278", None,      "clear",  False, 0, 0.42, "rock"),
}
SOLAR_ALIASES = {"chand": "moon", "chandrama": "moon", "mangal": "mars", "shukra": "venus", "budh": "mercury",
                 "brihaspati": "jupiter", "guru": "jupiter", "shani": "saturn", "prithvi": "earth"}


# --------------------------------------------------------------------------- stars
def _rng(*parts):
    return random.Random(stable_hash("|".join(str(p) for p in parts)) % (2 ** 31))


RULES = 3          # the rules version (3: temperatures from albedo + greenhouse) for everything new; a story without "rules" keeps 1 (its stars stay as they were)
GAL_KPC = 15.0     # map radius 1 = 15 kpc (≈ 50 000 light years); our Sun sits at 8.2 kpc


def galaxy_type(galaxy_seed):
    """the galaxy's shape from its seed: spiral / barred spiral / elliptical / irregular, arms and their pitch angle
    ("milkyway": our real one - engine/milkyway.py)"""
    if str(galaxy_seed).lower() == "milkyway":
        from . import milkyway
        return milkyway.galaxy_shape_cached()
    r = _rng("gtype", galaxy_seed)
    x = r.random()
    kind = "spiral" if x < 0.45 else "barred spiral" if x < 0.75 else "elliptical" if x < 0.9 else "irregular"
    return {"kind": kind, "arms": r.choice((2, 2, 4)), "pitch": round(r.uniform(11, 26), 1),     # degrees (Milky Way ~12)
            "bar": round(r.uniform(0.12, 0.22), 3) if kind == "barred spiral" else 0.0,
            "clumps": [(r.uniform(-0.5, 0.5), r.uniform(-0.5, 0.5)) for _ in range(4)]}


def _place2(gt, r, index):
    """a star's place by the galaxy's real shape -> (x, y, part): a bright bulge, a bar, a thin exponential disk with
    logarithmic spiral arms (r = r0·e^(θ·tan pitch)), or an elliptical / irregular blob"""
    k = gt["kind"]
    if k == "elliptical":
        R = min(1.0, abs(r.gauss(0, 0.32))); a = r.uniform(0, 2 * math.pi)
        return R * math.cos(a), R * math.sin(a) * 0.65, "elliptical"
    if k == "irregular":
        cx, cy = gt["clumps"][index % 4]
        return clamp(cx + r.gauss(0, 0.14), -1, 1), clamp(cy + r.gauss(0, 0.14), -1, 1), "disk"
    u = r.random()
    if u < 0.12:                                                         # the bulge: old stars packed round the middle
        R = abs(r.gauss(0, 0.07)); a = r.uniform(0, 2 * math.pi)
        return R * math.cos(a), R * math.sin(a), "bulge"
    if gt["bar"] and u < 0.2:                                            # the bar
        t, ba = r.uniform(-gt["bar"], gt["bar"]), gt.get("bar_angle", 0.5)
        return t * math.cos(ba) - r.gauss(0, 0.018) * math.sin(ba), t * math.sin(ba) + r.gauss(0, 0.018) * math.cos(ba), "bar"
    R = clamp(r.expovariate(1 / 0.2) + r.expovariate(1 / 0.2), 0.04, 1.0)  # an exponential disk by area (scale length 3 kpc)
    if r.random() < 0.75:                                                # in an arm: a logarithmic spiral
        arm = index % gt["arms"]
        th = math.log(R / 0.05) / math.tan(math.radians(gt["pitch"])) + arm * 2 * math.pi / gt["arms"] + gt.get("phase0", 0.0) + r.gauss(0, 0.13)
    else:
        th = r.uniform(0, 2 * math.pi)
    return R * math.cos(th), R * math.sin(th), "disk"


def features(galaxy_seed):
    """what else is in the galaxy (map only, from the seed): glowing star-forming nebulae in the arms with young blue
    stars, young open clusters in the disk, very old globular clusters in a round halo, supernova remnants (shells)"""
    gt = galaxy_type(galaxy_seed)
    r = _rng("feat", galaxy_seed)
    out = []
    young = gt["kind"] != "elliptical"                                   # ellipticals made no new stars for billions of years
    for i in range(7 if young else 0):
        x, y, _ = _place2(dict(gt, bar=0.0), r, i)
        out.append({"kind": "nebula", "x": round(x, 3), "y": round(y, 3), "size": round(r.uniform(0.02, 0.05), 3),
                    "colour": r.choice(("#ff5d8f", "#ff7aa8", "#e0508a", "#7fd0ff"))})
    for i in range(6 if young else 0):
        x, y, _ = _place2(dict(gt, bar=0.0), r, i + 3)
        out.append({"kind": "open cluster", "x": round(x, 3), "y": round(y, 3), "size": 0.015})
    for i in range(14):
        R = 0.25 + r.random() * 0.75; a = r.uniform(0, 2 * math.pi)
        out.append({"kind": "globular cluster", "x": round(R * math.cos(a), 3), "y": round(R * math.sin(a), 3), "size": 0.012})
    for i in range(3 if young else 1):
        x, y, _ = _place2(dict(gt, bar=0.0), r, i)
        out.append({"kind": "supernova remnant", "x": round(x, 3), "y": round(y, 3), "size": round(r.uniform(0.01, 0.025), 3)})
    return out


def rotation_kms(R):
    """the galaxy's turning speed at R (0..1 of the map): it rises in the middle then stays flat (~220 km/s) far out -
    the stars' and gas's mass alone would make it fall like the planets round the Sun (Kepler): the extra pull is
    dark matter"""
    return 220.0 * (1.0 - math.exp(-max(0.0, R) / 0.06))


def rotation_kepler_kms(R):
    """what the speed would be with only the stars we see (falls as 1/√R beyond the bulk of the disk)"""
    R = max(0.001, R)
    return 220.0 * (1.0 - math.exp(-R / 0.06)) * (min(1.0, (0.25 / R)) ** 0.5)


def lifetime_gyr(m):
    """a star's life on the main sequence: ≈ 10 billion years × M^-2.5 (the Sun 10, a 10-Sun star 30 million, a red dwarf trillions)"""
    return 10.0 * m ** -2.5


def star_class(T):
    """the real letter (Harvard class) by surface temperature"""
    return "O" if T >= 30000 else "B" if T >= 10000 else "A" if T >= 7500 else "F" if T >= 6000 else "G" if T >= 5200 else "K" if T >= 3700 else "M"


def gseed(p):
    """a planet's galaxy seed: a number, or "milkyway" (our real galaxy)"""
    g = p.get("galaxy")
    return "milkyway" if str(g).lower() == "milkyway" else int(g or 0)


_STAR_CACHE = {}


def star(galaxy_seed, index, rules=None):
    """dict for star `index` of a galaxy: position, mass, temperature, colour, brightness, planets
    (+ rules 2: the galaxy's shape, age, life stage, a companion star, metals by position, rogue planets)"""
    rules = RULES if rules is None else int(rules)
    key = (galaxy_seed, index, rules)
    if key not in _STAR_CACHE:
        if len(_STAR_CACHE) > 4000:
            _STAR_CACHE.clear()
        _STAR_CACHE[key] = _star(galaxy_seed, index, rules)
    return dict(_STAR_CACHE[key])


def _star(galaxy_seed, index, rules):
    r = _rng("star", galaxy_seed, index)
    arm = index % 4
    d = 0.1 + 0.9 * math.sqrt(r.random())                               # distance from the middle (0..1)
    ang = arm * math.pi / 2 + d * 5.5 + r.gauss(0, 0.25)                 # spiral arms
    m = clamp(math.exp(r.gauss(-0.35, 0.7)), 0.12, 18.0)                 # most stars are small (red dwarfs)
    T = 5778.0 * m ** 0.5
    L = m ** 3.5
    n = 0 if m > 10 else int(clamp(r.gauss(4.5, 2.2), 0, 9))
    out = {"galaxy": galaxy_seed, "index": index, "x": d * math.cos(ang), "y": d * math.sin(ang), "mass": m,
           "temperature": T, "luminosity": L, "colour": star_colour(T), "kind": star_kind(T), "planets": n,
           "name": star_name(galaxy_seed, index), "rules": 1}
    if rules < 2:
        return out
    # ------------------------------------------------------------------ rules 2 (own random streams: v1 stays as it was)
    r2 = _rng("star2", galaxy_seed, index)
    gt = galaxy_type(galaxy_seed)
    x, y, part = _place2(gt, r2, index)
    Rk = GAL_KPC * math.hypot(x, y)
    out.update(x=x, y=y, part=part, r_kpc=round(Rk, 2), rules=2)
    if r2.random() < 0.03:                                               # a rogue planet: thrown out of its system, no sun
        out.update(kind="rogue planet", mass=0.0, temperature=0.0, luminosity=0.0, colour="#000000", planets=1,
                   stage="rogue", age_gyr=round(r2.uniform(1, 12), 2), cls="-", radius=0.0, slots=[1], feh=0.0,
                   companion=None, notes=["a rogue planet: thrown out of its young system, it drifts between the stars with no sun"])
        return out
    if m >= 10:                                                          # the rare heavy tail (Salpeter): up to ~80 Suns
        m = clamp(10.0 * math.exp(r2.expovariate(1.35)), 10.0, 80.0)
    old = gt["kind"] == "elliptical" or part == "bulge"
    age = r2.uniform(7.0, 13.0) if old else r2.uniform(0.001, 13.0)      # Gyr (old galaxies / bulges made no new stars)
    life = lifetime_gyr(m)
    notes = []
    stage, R_star = "main", m ** 0.8
    T, L = 5778.0 * m ** 0.5, m ** 3.5
    m_now = m
    if age < life:
        if age < 0.02:
            stage = "young"; L *= 1.5
            notes.append("a young star: still wrapped in its dusty disk, its planets newly made")
    elif age < life * 1.1:
        stage = "red giant" if m < 8 else "red supergiant"
        R_star = (60 if m < 8 else 700) * m ** 0.5
        T = 3600.0 if m < 8 else 3400.0
        L = R_star ** 2 * (T / 5778.0) ** 4
        notes.append(f"its hydrogen is used up: it swelled into a {stage} {R_star:.0f}× the Sun's size - its inner planets are scorched or swallowed")
    else:
        dead = age - life * 1.1
        if m < 8:
            stage, m_now, R_star = "white dwarf", min(1.3, 0.5 + 0.09 * m), 0.012
            T = clamp(25000.0 * (dead + 0.1) ** -0.4, 4000.0, 60000.0)
            L = R_star ** 2 * (T / 5778.0) ** 4
            notes.append("the end of a Sun-like star: a white dwarf, Earth-sized, hot but dim and slowly cooling - its old planets froze")
        elif m < 20:
            stage = "pulsar" if dead < 0.05 else "neutron star"
            m_now, R_star, T, L = 1.4, 1.6e-5, 1.0e6, 0.0
            notes.append(f"it blew up as a supernova; a {stage} is left - a city-sized ball of neutrons" + (" spinning many times a second, sweeping beams of radiation" if stage == "pulsar" else ""))
        else:
            stage, m_now, R_star, T, L = "black hole", round(0.3 * m, 1), 0.0, 0.0, 0.0
            notes.append(f"over ~20 Suns at birth: its core collapsed into a black hole of {0.3 * m:.0f} Suns - not even light escapes")
    feh = clamp(-0.06 * (Rk - 8.2) - 0.025 * (age - 4.6) + (0.1 if part == "bulge" else 0) + r2.gauss(0, 0.1), -1.5, 0.5)
    # planets: v1's count, then the rules
    n0 = out["planets"]
    if m >= 10 and stage in ("neutron star", "pulsar"):
        n0 = 1 if r2.random() < 0.1 else 0                               # pulsar planets (PSR B1257+12) are rare
    elif m >= 10:
        n0 = 0
    if feh < -0.6:
        n0 = int(n0 * clamp(1 + feh * 0.5, 0.3, 1))                       # too few heavy elements to build many planets
    comp = None
    bin_frac = 0.27 if m < 0.5 else 0.45 if m < 1.3 else 0.7             # real multiplicity: most big stars are pairs
    if stage not in ("black hole",) and r2.random() < bin_frac:
        q = r2.uniform(0.1, 1.0); m2 = m * q
        sep = clamp(10 ** r2.gauss(1.6, 1.4), 0.03, 20000.0)               # AU (median ~40)
        T2 = 5778.0 * m2 ** 0.5
        comp = {"mass": round(m2, 3), "sep_au": round(sep, 3), "temperature": round(T2), "luminosity": m2 ** 3.5,
                "colour": star_colour(T2), "kind": star_kind(T2), "radius": m2 ** 0.8}
    slots = []
    swallowed = 0
    for k in range(1, n0 + 1):
        a = 0.35 * (1.65 ** (k - 1)) * m ** 0.5                           # the slot's distance (planet() adds ±20 %)
        if stage in ("red giant", "red supergiant", "white dwarf") and a < R_star * 0.00465 * 1.6 + (0.3 if stage == "white dwarf" else 0):
            swallowed += 1; continue                                     # inside the giant (or tidally pulled in)
        if comp:
            if a * 0.85 > 3.5 * comp["sep_au"] or a * 1.2 < comp["sep_au"] / 3.0:
                slots.append(k)                                          # round both (far out) or round one (well inside)
            continue                                                     # between: no stable orbit
        slots.append(k)
    if swallowed:
        notes.append(f"{swallowed} inner planet(s) were swallowed when it swelled")
    if comp and len(slots) < n0 - swallowed:
        notes.append(f"a pair of stars {comp['sep_au']:g} AU apart: only orbits well inside or far outside the pair are stable")
    if Rk < 2.5:
        notes.append("close to the galaxy's crowded middle: supernovae and radiation - too harsh for complex life")
    elif feh < -0.7:
        notes.append("far out, poor in heavy elements: few rocky planets")
    hj = stage == "main" and 4500 < T < 7000 and r2.random() < 0.012
    out.update(mass=m_now, mass_born=round(m, 3), temperature=T, luminosity=L, colour=star_colour(T) if T else "#000000",
               kind=star_kind(T) if stage in ("main", "young") else stage, cls=star_class(T) if stage in ("main", "young") else "-",
               stage=stage, age_gyr=round(age, 3), lifetime_gyr=round(life, 3), radius=R_star, feh=round(feh, 2),
               companion=comp, slots=slots, planets=len(slots), hot_jupiter=hj, notes=notes)
    return out


CIVS = ("none", "ancient", "advanced")


def civilization_of(p, key):
    """none / ancient / advanced: only a living, breathable world grows people of its own (a separate random
    stream, so nothing else about the planet changes)"""
    if not p.get("life") or not p.get("breathable"):
        return "none"
    x = _rng("civ", key).random()
    return "advanced" if x < 0.15 else ("ancient" if x < 0.4 else "none")


def star_kind(T):
    return ("red dwarf" if T < 3700 else "orange star" if T < 5200 else "yellow star" if T < 6000 else
            "white star" if T < 7500 else "blue-white star" if T < 10000 else "blue giant")


def star_colour(T):
    """an approximate blackbody colour (hex)"""
    t = T / 100.0
    r = 255 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = (99.47 * math.log(t) - 161.1) if t <= 66 else 288.1 * (t - 60) ** -0.0755
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5 * math.log(t - 10) - 305.0)
    return "#%02x%02x%02x" % tuple(int(clamp(v, 0, 255)) for v in (r, g, b))


SYLL = ("ka", "ri", "so", "ma", "tu", "ve", "lo", "na", "shi", "ra", "di", "po", "zen", "ar", "il", "ku", "tha", "mi")


def star_name(galaxy_seed, index):
    if str(galaxy_seed).lower() == "milkyway":                          # ⭐ our galaxy: known names (engine/starnames.py)
        from .starnames import name
        return name(int(index))
    r = _rng("name", galaxy_seed, index)
    return "".join(r.choice(SYLL) for _ in range(r.randint(2, 3))).capitalize()


# --------------------------------------------------------------------------- 🌡 rules 3: the climate from albedo + greenhouse
def climate3(T_eq0, air, m, r):
    """surface temperature of a rocky planet worked out to a steady state (a few rounds of feedback):
       T_eq = T_eq0 · (1 - A)^¼  (A = albedo: ice 0.6, seas 0.06 + clouds, thick cloudy air 0.7, bare rock 0.12)
       T = T_eq · (1 + ¾ τ)^¼     (grey greenhouse: atmos.grey_tau - CO₂ by log + p², H₂O by √p; Earth ≈ +33 K)
       p(H₂O) follows the warmth (Clausius-Clapeyron, ~7 % more per K) - the water-vapour feedback; past ~70 °C with
       seas it runs away (Venus); the carbon-silicate cycle: with liquid seas, rain and rocks pull CO₂ down to a
       trace, without them volcanoes pile it up (Mars, Venus)
    -> {"T": K, "albedo", "greenhouse_K", "pressure", "co2", "wet": "oceans"/"lakes"/"none"/None, "why": [...]}"""
    from .atmos import grey_tau
    if air == "none":
        A = 0.12
        return {"T": T_eq0 * (1 - A) ** 0.25, "albedo": A, "greenhouse_K": 0, "pressure": 0.0, "co2": 0.0, "wet": None,
                "why": ["no air: no greenhouse - only the sunlight it soaks up (albedo 0.12)"]}
    P = r.uniform(0.3, 2.0) * min(3.0, max(0.5, m ** 0.5)) if air == "thin" else r.uniform(3, 95)
    seas_able = r.random() < 0.7                                  # was water delivered at all (comets, wet rocks)?
    T, A, why, wet = T_eq0, 0.3, [], None
    for _ in range(8):
        liquid = seas_able and 273 < T < 373 + 30 * math.log10(max(1.0, P))
        frozen = seas_able and T <= 263
        co2 = (0.0004 * P + 0.0002) if liquid else (0.95 * P if air == "thick" else 0.6 * P)   # carbon-silicate cycle
        sat = math.exp(3150 * (1 / 194.7 - 1 / max(60.0, T)))      # CO₂ frost: above this pressure it snows out (dry ice)
        if co2 > sat:
            P, co2 = max(0.006, P - (co2 - sat)), sat
        pw = 0.0
        if seas_able and T > 250:
            pw = min(P * 0.6 + (40.0 if T > 340 else 0.0), 0.01 * math.exp(0.065 * (T - 288)))
        tau = grey_tau(P, co2, pw)
        A = 0.6 if frozen else (0.7 if (P > 30 or pw > 1) else (0.3 if liquid else 0.22))
        Tn = T_eq0 * (1 - A) ** 0.25 * (1 + 0.75 * tau) ** 0.25
        T = 0.5 * T + 0.5 * Tn
    liquid = seas_able and 273 < T < 373 + 30 * math.log10(max(1.0, P))
    if liquid:
        wet = "oceans" if r.random() < 0.65 else "lakes"
        why.append("liquid seas pull CO₂ out of the air into rocks (the carbon-silicate cycle) - the warmth stays steady")
    elif seas_able and T >= 340:
        wet = "none"
        why.append("too warm: water vapour trapped more heat, which made more vapour - a runaway greenhouse (like Venus); the water was lost to space")
    elif seas_able and T <= 263:
        why.append("frozen: ice throws back sunlight, which keeps it frozen (a snowball world)")
    if co2 >= 0.99 * math.exp(3150 * (1 / 194.7 - 1 / max(60.0, T))) and T < 200:
        why.append("so cold that CO₂ froze out of the air as dry ice")
    elif not liquid and co2 > 1:
        why.append(f"no seas to take CO₂ out: it piled up from volcanoes ({co2:.0f} bar)")
    Te = T_eq0 * (1 - A) ** 0.25
    return {"T": T, "albedo": A, "greenhouse_K": round(T - Te), "pressure": round(P, 2), "co2": round(co2, 4), "wet": wet, "why": why}


# --------------------------------------------------------------------------- 🪨 belts of left-over rock and ice
def belts(galaxy_seed, star_index, rules=None):
    """where the planets leave gaps: between the last rocky planet and the first giant the giant's pull stirs the
    rocks too fast to stick into a planet - an asteroid belt (ours: 2.2-3.3 AU between Mars 1.52 and Jupiter 5.2);
    beyond the last planet the left-over ice stays as a Kuiper belt (ours 30-50 AU) - the home of comets.
    -> [{"kind", "from_au", "to_au", "why"}] (cheap: from the planets already made)"""
    s = star(galaxy_seed, star_index, rules)
    pl = [planet(galaxy_seed, star_index, k, rules) for k in range(1, int(s.get("planets") or 0) + 1)]
    pl = [p for p in pl if p.get("distance_au")]
    pl.sort(key=lambda p: p["distance_au"])
    out = []
    for a, b in zip(pl, pl[1:]):
        if not a.get("gas") and b.get("gas"):                              # the giant's 4:1 to 2:1 resonances (0.40-0.63 of its orbit)
            lo, hi = max(b["distance_au"] * 0.40, a["distance_au"] * 1.15), b["distance_au"] * 0.63
            if hi > lo * 1.15:
                out.append({"kind": "asteroid belt", "from_au": round(lo, 3), "to_au": round(hi, 3),
                            "why": f"between {a['name']} (rocky) and {b['name']} (a giant): the giant's regular tugs (its 4:1 to 2:1 resonances) "
                                   "stirred the rocks too hard to stick into a planet - like our belt inside Jupiter"})
            break
    comp = s.get("companion") or {}
    if comp.get("sep_au"):                                                      # no belt where the partner star's pull stirs everything
        lo, hi = comp["sep_au"] * 0.3, comp["sep_au"] * 3.0
        out = [x for x in out if x["to_au"] < lo or x["from_au"] > hi]
    edge = (comp.get("sep_au") or 1e9) * 0.3 if comp and pl and pl[-1]["distance_au"] < (comp.get("sep_au") or 0) else 1e9   # a partner star clears the outer disk
    if pl and any(p.get("gas") for p in pl) and pl[-1]["distance_au"] * 1.75 < edge:
        last = pl[-1]["distance_au"]
        out.append({"kind": "Kuiper belt", "from_au": round(last * 1.3, 2), "to_au": round(last * 1.75, 2),
                    "why": "beyond the last planet: icy left-overs that never grew - the home of comets (sometimes one is nudged inward and grows a tail)"})
    return out


# --------------------------------------------------------------------------- planets
_PLANET_CACHE = {}


def planet(galaxy_seed, star_index, k, rules=None):
    """dict for planet k (1-based) of a star, worked out from the rules (see the module doc)"""
    rules = RULES if rules is None else int(rules)
    key = (galaxy_seed, star_index, int(k or 1), rules)
    if key not in _PLANET_CACHE:
        if len(_PLANET_CACHE) > 3000:
            _PLANET_CACHE.clear()
        _PLANET_CACHE[key] = _planet(galaxy_seed, star_index, int(k or 1), rules)
    return copy.deepcopy(_PLANET_CACHE[key])


def _rogue(galaxy_seed, star_index, s):
    """a planet with no sun: dark and frozen on top; a big one may keep a thick hydrogen blanket (warm deep down)"""
    r = _rng("rogue", galaxy_seed, star_index)
    R = clamp(math.exp(r.gauss(0.0, 0.5)), 0.3, 3.0); m = R ** 3.7
    air = "thick" if m > 3 else "none"
    Tc = -230.0 if air == "none" else -200.0
    cols = _colours(r, "ice", air, "ice", {"colour": "#8899bb", "temperature": 3000}, Tc)
    return {"galaxy": galaxy_seed, "star": star_index, "k": 1, "name": f"{s['name']} (rogue)", "star_name": "no star",
            "star_kind": "rogue planet", "star_colour": "#000000", "star_size": 0.0, "distance_au": None, "year_days": None,
            "radius": R, "mass": m, "g": G_EARTH * m / (R * R), "escape_kms": 11.2 * math.sqrt(m / R), "temperature_c": Tc,
            "air": air, "water": "ice", "surface": "ice", "weather": "clear", "life": False, "moons": int(r.random() < 0.3),
            "rings": False, "gas": False, "colours": cols, "pressure": 0.0 if air == "none" else round(r.uniform(5, 50), 1),
            "air_mix": "" if air == "none" else "hydrogen,helium", "breathable": False, "day_hours": round(r.uniform(8, 40), 1),
            "tilt": round(abs(r.gauss(15, 15)), 1), "terrain": ["craters", "plains"], "magnetic_field": False, "clouds": None,
            "wind": None, "ice_caps": False, "planets_in_sky": 0, "civilization": "none", "rules": 2, "rogue": True, "star_flux": 0.0,
            "star_stage": "rogue", "star_age_gyr": s.get("age_gyr"), "galaxy_r_kpc": s.get("r_kpc"), "tidal_lock": False,
            "sun2": None, "star_notes": list(s.get("notes", [])) + ["no sunlight at all: the only light is the stars"
                                                                 + (" - deep under its hydrogen blanket it may be warm (inside heat)" if air != "none" else "")]}


def _planet(galaxy_seed, star_index, k, rules):
    s = star(galaxy_seed, star_index, rules)
    v2 = rules >= 2
    if v2 and s.get("stage") == "rogue":
        return _rogue(galaxy_seed, star_index, s)
    if s["planets"] < 1:
        s = dict(s, planets=1, slots=(s.get("slots") or [1]))
    k = int(clamp(k, 1, max(1, s["planets"])))
    slot = s["slots"][k - 1] if v2 and s.get("slots") else k            # rules 2: the k-th stable orbit
    r = _rng("planet", galaxy_seed, star_index, slot)
    m_born = s.get("mass_born", s["mass"])
    a = 0.35 * (1.65 ** (slot - 1)) * r.uniform(0.85, 1.2) * m_born ** 0.5      # AU
    comp = s.get("companion") if v2 else None
    round_both = bool(comp) and a > 2 * comp["sep_au"]
    L = s["luminosity"] + (comp["luminosity"] if round_both else 0.0)
    if v2 and s.get("stage") == "white dwarf":
        a *= m_born / s["mass"]                                          # the star lost mass: its orbits widened (a ∝ 1/M)
    snow_line = 2.7 * (m_born ** 3.5 if v2 else s["luminosity"]) ** 0.5    # where ice formed when the planets were made
    hot_j = v2 and s.get("hot_jupiter") and k == 1
    if hot_j:
        a = 0.05 * m_born ** 0.5
    giant_p = clamp(0.7 * 10 ** (1.2 * s.get("feh", 0.0)), 0.25, 0.95) if v2 else 0.7     # metal-rich stars grow more giants
    gas = (a > snow_line and r.random() < giant_p) or bool(hot_j)
    if gas:
        R = r.uniform(3.5, 12.0)                                           # Earth radii
        m = R ** 2.06 * r.uniform(0.6, 1.4) if R < 6 else r.uniform(15, 320)
    else:
        R = clamp(math.exp(r.gauss(0.0, 0.45)), 0.25, 2.2)
        m = R ** 3.7 * r.uniform(0.8, 1.15)
    g = G_EARTH * m / (R * R)
    v_esc = 11.2 * math.sqrt(m / R)                                         # km/s
    M_c = s["mass"] + (comp["mass"] if round_both else 0.0)
    year = math.sqrt(a ** 3 / max(1e-3, M_c)) * 365.25                       # days (Kepler III)
    T_eq = 278.0 * L ** 0.25 / math.sqrt(a)                                  # K, no air
    if v2 and s.get("stage") in ("pulsar", "neutron star"):
        T_eq = max(T_eq, 40.0)
    if v2 and s.get("stage") == "young":
        T_eq += 15.0                                                          # still warm from being made
    v_gas = 0.517 * math.sqrt(T_eq / 300.0)                                 # km/s: nitrogen's thermal speed
    keeps_air = gas or (v_esc > 7.0 * v_gas and m > 0.08)                   # (Jeans escape, simplified)
    air = "none"
    if keeps_air:
        air = "thick" if (gas or m > 1.6 or r.random() < 0.25) else "thin"
    T = T_eq + (0 if air == "none" else (30 if air == "thin" else r.uniform(60, 400)))
    clim3 = None
    if rules >= 3 and not gas:                                              # 🌡 rules 3: worked out, not guessed
        clim3 = climate3(T_eq, air, m, _rng("climate", galaxy_seed, star_index, k))
        T = clim3["T"]
    Tc = T - 273.15
    if gas:
        water, surface = "clouds", "gas"
    elif Tc > 400:
        water, surface = "none", "lava"
    elif air == "none":
        water, surface = ("ice" if Tc < -60 and r.random() < 0.5 else "none"), "rock"
    elif Tc < -10:
        water, surface = "ice", "ice"
    elif Tc < 95:
        water = "oceans" if r.random() < 0.55 else ("lakes" if r.random() < 0.6 else "none")
        if clim3 and clim3["wet"] is not None:                              # the climate loop already knows
            water = clim3["wet"]
        surface = "rock" if water == "none" else "wet"
    else:
        water, surface = ("none" if clim3 and clim3["wet"] == "none" else "steam"), "rock"   # rules 3: a runaway lost its water
    if air == "none":
        weather = "clear"
    elif gas:
        weather = "storm" if r.random() < 0.5 else "windy"
    elif water in ("oceans", "lakes"):
        weather = r.choice(("clear", "clear", "clouds", "rain", "storm" if Tc > 25 else "rain"))
    elif water == "ice":
        weather = r.choice(("snow", "clear", "windy"))
    else:
        weather = r.choice(("windy", "clear", "dust_storm" if air == "thin" else "storm"))
    life = (not gas) and air != "none" and water in ("oceans", "lakes") and -15 < Tc < 50
    notes = list(s.get("notes", [])) if v2 else []
    locked = False
    if v2:
        stg = s.get("stage")
        if stg in ("white dwarf", "pulsar", "neutron star", "black hole", "red giant", "red supergiant"):
            life = False                                                  # its star died or swelled: life is gone
        if stg == "pulsar":
            notes.append("the pulsar's beams of radiation blast its planets - no life")
        if s.get("age_gyr", 5) < 1.0 and life:
            life = False; notes.append(f"its star is only {s['age_gyr'] * 1000:.0f} million years old: too young for life to have grown")
        if s.get("r_kpc", 8) < 2.5 and life:
            life = False                                                  # the galaxy's harsh middle
        # tidal lock: the star's pull slows the spin until one side always faces it (a_lock ∝ M^(1/3) (t)^(1/6))
        a_lock = 0.5 * max(0.05, s["mass"]) ** (1 / 3) * (max(0.1, s.get("age_gyr", 4.5)) / 4.5) ** (1 / 6)
        if a < a_lock and not gas and s.get("stage") not in ("black hole",):
            locked = True
            notes.append("tidally locked: one side always faces its star (endless day), the other is endless night - "
                         "life (if any) lives in the twilight ring between")
        # flares: young red dwarfs flare hard; close planets with thin air lose it
        if s.get("cls") == "M" and a < 0.15 and air == "thin" and s.get("age_gyr", 5) < 3 and _rng("flare", galaxy_seed, star_index, slot).random() < 0.5:
            air, water, weather, life = "none", ("ice" if Tc < -20 else "none"), "clear", False
            surface = "rock" if surface == "wet" else surface
            notes.append("its red dwarf's flares stripped its thin air away")
        if hot_j:
            notes.append("a hot Jupiter: a gas giant that wandered in close to its star - a year of a few days, clouds of rock")
        if round_both:
            notes.append(f"it orbits both stars of the pair: two suns, two shadows, double sunsets")
    moons = int(clamp(r.gauss(0.5 + (6 if gas else 0) + m * 0.2, 1.5), 0, 12))
    rings = gas and r.random() < 0.55
    star_size = 1.0 * (s.get("radius", s["mass"] ** 0.8) if v2 else s["mass"] ** 0.8) / a       # how big the star looks (Sun from Earth = 1)
    sun2 = None
    if comp:
        d2 = abs(comp["sep_au"] - (0 if round_both else a)) or comp["sep_au"]
        sun2 = {"colour": comp["colour"], "kind": comp["kind"], "size": round(comp["radius"] / max(0.01, a if round_both else d2), 4),
                "far": not round_both, "sep_deg": round(math.degrees(min(1.2, comp["sep_au"] / a)), 1) if round_both else None,
                "bright": round(comp["luminosity"] / max(1e-6, (a if round_both else d2)) ** 2 / max(1e-6, L / a ** 2), 4)}
    cols = _colours(r, surface, air, water, s, Tc)
    out = {"galaxy": galaxy_seed, "star": star_index, "k": k, "name": f"{s['name']} {_roman(k)}",
            "star_name": s["name"], "star_kind": s["kind"], "star_colour": s["colour"], "star_size": star_size,
            "distance_au": a, "year_days": year, "radius": R, "mass": m, "g": g, "escape_kms": v_esc,
            "temperature_c": Tc, "air": air, "water": water, "surface": surface, "weather": weather, "life": life,
            "moons": moons, "rings": rings, "gas": gas, "colours": cols,
            "pressure": {"none": 0.0, "thin": 1.0, "thick": round(r.uniform(5, 90), 1)}[air],
            "air_mix": "" if air == "none" else ("hydrogen,helium" if gas else ("nitrogen,oxygen" if life else
                                                                                   r.choice(("co2", "nitrogen,co2")))),
            "breathable": life, "day_hours": round(r.uniform(9, 60), 1), "tilt": round(abs(r.gauss(15, 15)), 1),
            "terrain": [] if gas else ["craters"] if air == "none" else r.sample(("hills", "mountains", "dunes", "canyons",
                                                                   "plains"), 2) + (["volcanoes"] if Tc > 300 else []),
            "magnetic_field": m > 0.5 and r.random() < 0.5, "clouds": None, "wind": None,
            "ice_caps": water in ("oceans", "ice") and Tc < 30, "planets_in_sky": r.randint(0, 2)}
    if v2 and life:                                   # 🦠 life by the planet's age (Earth's clock, a little faster or slower)
        st_, age_ = life_stage(s.get("age_gyr", 4.6), f"{galaxy_seed}|{star_index}|{slot}")
        out["life_stage"] = st_
        notes.append(LIFE_STAGE_WHY[st_].format(age=s.get("age_gyr", 4.6)))
        if st_ != "land":                             # no land plants or animals yet: what the walk / videos show
            life = False
            out.update(life=False, breathable=False,
                       air_mix="nitrogen,co2,methane" if st_ in ("microbes", "oxygen_rising") else "nitrogen,co2,oxygen")
    if v2 and life and s.get("temperature"):          # 🌿 leaves coloured by the star's light (alien_life.pigment)
        from .alien_life import pigment
        pc, pwhy = pigment(s["temperature"], 1.0, out.get("pressure") or 1.0)
        out["colours"] = dict(out["colours"], plant=pc, leaves=pc)
        notes.append("🌿 " + pwhy)
    if v2:
        if sun2:
            sun2["period_days"] = round(math.sqrt(comp["sep_au"] ** 3 / max(0.05, s["mass"] + comp["mass"])) * 365.25, 2)
        if clim3:                                                           # rules 3: the air the climate loop found
            out["pressure"] = clim3["pressure"]
            if not life:
                out["air_mix"] = "co2" if clim3["co2"] > 0.5 * max(0.01, clim3["pressure"]) else "nitrogen,co2"
            out["albedo"], out["greenhouse_K"], out["climate_why"] = clim3["albedo"], clim3["greenhouse_K"], clim3["why"]
        out.update(rules=max(2, rules), k=k, tidal_lock=locked, sun2=sun2, star_flux=round(L / a ** 2, 6), star_stage=s.get("stage"), star_age_gyr=s.get("age_gyr"),
                   star_class=s.get("cls"), galaxy_r_kpc=s.get("r_kpc"), star_notes=notes, star_disk=s.get("stage") == "young",
                   star_temp=round(s["temperature"]))
        if locked:
            out["day_hours"] = round(year * 24, 1)                          # it turns once an orbit (no sunrise)
        if s.get("stage") in ("black hole", "neutron star"):
            out["star_colour"] = "#000000" if s.get("stage") == "black hole" else "#cfe0ff"
        if not life:
            out["breathable"] = False
    out["civilization"] = civilization_of(out, f"{galaxy_seed}|{star_index}|{k}")
    return out


# 🦠 Earth's own clock of life (billions of years after the planet formed): first microbes ~0.8 (3.8 Ga), oxygen from
# photosynthesising microbes builds up after ~2.2 (the Great Oxidation 2.4 Ga), sea life and simple plants ~3.4-4.0
# (Ediacaran / Cambrian), plants and animals on land after ~4.1 (470-400 Ma). Other worlds run a little faster or
# slower (0.75-1.4x): the chemistry is the same, the luck is not.
LIFE_STAGES = ("microbes", "oxygen_rising", "seas", "land")
LIFE_STAGE_WHY = {
    "microbes": "🦠 this world is {age:.1f} billion years old - life here is still only microbes: coloured mats in shallow "
                "water, slime on wet rock, stromatolite mounds; no free oxygen yet (the air is methane, CO₂ and nitrogen)",
    "oxygen_rising": "🦠 this world is {age:.1f} billion years old - microbes that use sunlight are slowly filling the air "
                     "with oxygen (rocks rust red first); stromatolites everywhere in the shallows, nothing on land",
    "seas": "🌊 this world is {age:.1f} billion years old - life fills the seas (seaweed, soft drifting animals) but the "
            "land is still bare rock; the oxygen is almost enough to breathe",
    "land": "🌳 this world is {age:.1f} billion years old - old enough for plants and animals on land",
}


def life_stage(age_gyr, key):
    """-> (stage, age): how far life has come on a living world of this age"""
    f = _rng("lifeclock", key).uniform(0.75, 1.4)
    a = float(age_gyr or 4.6)
    if a < 2.0 * f:
        return "microbes", a
    if a < 3.4 * f:
        return "oxygen_rising", a
    if a < 4.0 * f:
        return "seas", a
    return "land", a


# 🕰 Earth in the past (15.9: the geological time scale) - what the rocks, fossils and ice cores tell us
EARTH_ERAS = {
    "cambrian": dict(title="Cambrian (500 million years ago)", T=22, O2=13.0, CO2=0.45, weather="clear", life=False, stage="seas",
                     creatures=0, why="life exploded in the seas (trilobites, the first animals with shells and eyes) - nothing lives on "
                                      "land yet: bare rock, no soil, no plants; ~13 % oxygen, ~12× today's CO₂: warm"),
    "carboniferous": dict(title="Carboniferous (300 million years ago)", T=20, O2=33.0, CO2=0.08, weather="rain", life=True,
                          creatures=3, why="giant swamp forests of tree ferns and club mosses 30 m tall (they became our coal); "
                                           "~33 % oxygen - insects grew huge (dragonflies 70 cm across: their breathing tubes "
                                           "could feed a bigger body), forest fires burned even in damp wood; amphibians on land"),
    "jurassic": dict(title="Jurassic (150 million years ago)", T=24, O2=26.0, CO2=0.15, weather="clear", life=True, creatures=5,
                     why="dinosaurs: giant plant-eaters (30-tonne sauropods) and their hunters; conifers, cycads and ferns (no "
                         "flowers or grass yet); warmer than today - no ice at the poles"),
    "ice_age": dict(title="the last ice age (20,000 years ago)", T=7, O2=21.0, CO2=0.019, weather="snow", life=True, creatures=4,
                    why="ice sheets 3 km thick over the north; the sea 120 m lower (the water was locked in the ice); woolly "
                        "mammoths and rhinos with thick fur and big bodies (less skin per kilo keeps the heat in); only 190 ppm CO₂"),
}


def earth_era(era):
    """Earth as it was in a past era -> a planet dict (its air, warmth, weather and life made by our generators to fit)"""
    e = EARTH_ERAS.get(str(era).lower())
    if not e:
        return solar("earth")
    p = dict(solar("earth"))
    p.update(solar=None, real=False, era=str(era).lower(), name=f"Earth - {e['title']}", galaxy=None, star=None, k=None,
             radius=1.0, mass=1.0, escape_kms=11.2, star_flux=1.0, star_age_gyr=4.6, star_stage="main", rules=2,
             temperature_c=e["T"], weather=e["weather"], water="oceans", surface="wet", air="thin", pressure=1.0,
             air_mix="nitrogen,oxygen,co2", breathable=e["O2"] >= 16, civilization="none", terrain=["plains", "hills"],
             era_gases={"N₂": round(99.0 - e["O2"] - e["CO2"], 2), "O₂": e["O2"], "CO₂": e["CO2"], "Ar": 0.93, "H₂O": 1.0},
             life={"creatures": e["creatures"]} if e["life"] else False, star_notes=[f"🕰 {e['title']}: {e['why']}"])
    if not e["life"]:
        p["life_stage"] = e.get("stage", "seas")
    p["life_ok"] = bool(e["life"])
    return p


def _roman(k):
    return ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")[max(0, min(11, k - 1))]


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(clamp(v, 0, 1) * 255) for v in rgb)


def _hsv(h, s, v):
    import colorsys
    return _hex(colorsys.hsv_to_rgb(h % 1.0, clamp(s, 0, 1), clamp(v, 0, 1)))


def _colours(r, surface, air, water, s, Tc):
    """palette roles for the planet: the ground and rocks by the surface, the sky by the air and the star"""
    h = r.random()
    if surface == "lava":
        ground, rock, sand = "#2a1a16", "#3a2420", "#4a2a20"
    elif surface == "ice":
        ground, rock, sand = "#dbeef6", "#a9c4d4", "#eef6fa"
    elif surface == "gas":
        ground, rock, sand = _hsv(h * 0.15 + 0.05, 0.35, 0.85), _hsv(h * 0.15 + 0.03, 0.4, 0.65), "#f0e2c8"
    else:
        ground = _hsv(r.choice((0.02, 0.06, 0.08, 0.1, 0.55, 0.75)) + r.uniform(-0.03, 0.03), r.uniform(0.25, 0.6),
                      r.uniform(0.45, 0.8))
        rock, sand = _hsv(r.random(), 0.15, 0.5), _hsv(0.1, 0.3, 0.85)
    star_rgb = tuple(int(s["colour"][i:i + 2], 16) / 255 for i in (1, 3, 5))
    if air == "none":
        sky = "#05060d"
    elif air == "thin":
        sky = _hex(tuple(0.35 + 0.45 * c for c in star_rgb)) if s["temperature"] < 4500 else "#e0b08a" \
            if r.random() < 0.4 else "#8ec5ee"
    else:
        sky = _hex(tuple(0.5 * c + 0.4 for c in star_rgb))
    plant = {True: _hsv(r.choice((0.3, 0.33, 0.85, 0.08, 0.55)), 0.6, 0.6)}.get(True)
    if s["temperature"] < 4000:
        plant = _hsv(0.95, 0.5, 0.35)                                       # dark plants under a red star
    elif s["temperature"] > 7500:
        plant = _hsv(r.random(), 0.25, 0.85)                                # pale ones under a blue star
    water_c = "#3a7fc4" if water in ("oceans", "lakes") else ("#cfe6f2" if water == "ice" else "#556070")
    return {"ground": ground, "rock": rock, "sand": sand, "sky": sky, "fog": sky, "plant": plant, "leaves": plant,
            "wood": "#5a4632", "water": water_c}


def solar(name):
    """a planet dict (same keys as planet()) for a body of our Solar System"""
    n = SOLAR_ALIASES.get(str(name).lower(), str(name).lower())
    g, air, Tc, ground, sky, weather, rings, moons, star_size, kind = SOLAR[n]
    gas = kind in ("gas", "ice_giant")
    surface = "gas" if gas else ("ice" if kind == "ice" else ("lava" if Tc > 400 else "rock"))
    water = "oceans" if n == "earth" else ("ice" if n in ("mars", "pluto", "europa", "enceladus", "ganymede", "callisto", "triton", "charon", "ceres") else ("lakes" if n == "titan" else ("clouds" if gas else "none")))
    cols = {"ground": ground, "rock": "#8e8e8e" if not gas else ground, "sand": ground, "sky": sky or "#05060d",
            "fog": sky or "#05060d", "plant": "#3f9142" if n == "earth" else ground, "leaves": "#2d6b30",
            "wood": "#6b4528", "water": "#3a7fc4" if n == "earth" else "#cfe6f2"}
    return {"galaxy": None, "star": None, "k": None, "name": n.capitalize(), "star_name": "the Sun",
            "star_kind": "yellow star", "star_colour": "#fff2c8", "star_size": star_size, "distance_au": None,
            "year_days": None, "radius": None, "mass": None, "g": g, "escape_kms": None, "temperature_c": Tc,
            "air": air, "water": water, "surface": surface, "weather": weather, "life": n == "earth",
            "moons": moons, "rings": rings, "gas": gas, "colours": cols, "solar": n,
            "earth_in_sky": n == "moon", "civilization": "advanced" if n == "earth" else "none",
            **(MOON_OF.get(n) and {"parent": MOON_OF[n], "terrain": MOON_OF[n]["terrain"]} or {})}


# 🪐 the giant in the sky of its moons (real angular size seen from the moon) + what squeezing does to them
MOON_OF = {"io": {"name": "Jupiter", "deg": 19.5, "colour": "#d9a066", "bands": True, "rings": False, "tidal": 4.0, "terrain": ["volcanoes", "plains"], "plumes": "sulfur",
                  "why": "Jupiter's pull squeezes Io every 42 hours (its orbit is pushed oval by Europa and Ganymede): the "
                         "friction melts its inside - over 400 volcanoes, the most active place in the Solar System"},
           "europa": {"name": "Jupiter", "deg": 12.0, "colour": "#d9a066", "bands": True, "rings": False, "tidal": 1.4, "terrain": ["plains", "cliffs"], "lineae": True,
                      "why": "squeezing keeps an ocean of salty liquid water under its ice shell - more water than all "
                             "of Earth's seas; the shell cracks into long red-brown lines"},
           "enceladus": {"name": "Saturn", "deg": 31.0, "colour": "#e3cf8c", "bands": True, "rings": True, "tidal": 1.1, "terrain": ["plains", "canyons"], "plumes": "ice",
                         "why": "squeezing warms an ocean under the south pole: ice geysers shoot water vapour and ice "
                                "out of the 'tiger stripe' cracks into space (they feed Saturn's E ring)"},
           "ganymede": {"name": "Jupiter", "deg": 7.5, "colour": "#d9a066", "bands": True, "rings": False, "tidal": 0.3, "terrain": ["plains", "cliffs"],
                        "why": "the biggest moon - wider than Mercury; the only moon with its own magnetic field (its iron core "
                               "still stirs); a salty ocean lies deep under the ice"},
           "callisto": {"name": "Jupiter", "deg": 4.25, "colour": "#d9a066", "bands": True, "rings": False, "tidal": 0.05, "terrain": ["plains", "hills"],
                        "why": "too far out to be squeezed: its old ice crust has barely changed for 4 billion years - the most "
                               "cratered world we know"},
           "triton": {"name": "Neptune", "deg": 8.0, "colour": "#4f7fe6", "bands": False, "rings": False, "tidal": 0.2, "terrain": ["plains", "cliffs"], "plumes": "ice",
                      "why": "it goes round Neptune backwards: a world from the Kuiper belt caught by Neptune; sunlight on its "
                             "nitrogen ice drives dark geysers 8 km high; the coldest surface measured (38 K)"},
           "charon": {"name": "Pluto", "deg": 6.9, "colour": "#d9c7b0", "bands": False, "rings": False, "tidal": 0.0, "terrain": ["plains", "canyons"],
                      "why": "Pluto and Charon always show each other the same face (each locks the other): Pluto hangs still in "
                             "Charon's sky; gas escaping Pluto paints Charon's pole red"},
           "titan": {"name": "Saturn", "deg": 5.7, "colour": "#e3cf8c", "bands": True, "rings": True, "tidal": 0.6, "terrain": ["dunes", "hills"],
                     "why": "a thick nitrogen air (1.5 bar) with an orange smog of hydrocarbons; at -179 °C methane "
                            "is liquid - it rains methane into lakes and seas (the only other world with lakes)"}}


WORDS = {
    "warm": lambda p: 10 < p["temperature_c"] < 45, "hot": lambda p: p["temperature_c"] > 60,
    "cold": lambda p: p["temperature_c"] < -10, "frozen": lambda p: p["surface"] == "ice", "icy": lambda p: p["surface"] == "ice",
    "water": lambda p: p["water"] in ("oceans", "lakes"), "ocean": lambda p: p["water"] == "oceans",
    "sea": lambda p: p["water"] == "oceans", "lakes": lambda p: p["water"] == "lakes",
    "dry": lambda p: p["water"] in ("none", "steam"), "desert": lambda p: p["water"] == "none" and p["air"] != "none",
    "lava": lambda p: p["surface"] == "lava", "volcanic": lambda p: p["surface"] == "lava",
    "airless": lambda p: p["air"] == "none", "no air": lambda p: p["air"] == "none",
    "gas": lambda p: p["gas"], "giant": lambda p: p["gas"], "rings": lambda p: p["rings"],
    "life": lambda p: p["life"], "living": lambda p: p["life"], "alive": lambda p: p["life"],
    "small": lambda p: p["g"] < 5, "low gravity": lambda p: p["g"] < 5, "heavy": lambda p: p["g"] > 14,
    "red star": lambda p: "red" in p["star_kind"], "blue star": lambda p: "blue" in p["star_kind"],
    "stormy": lambda p: p["weather"] in ("storm", "dust_storm"), "snow": lambda p: p["weather"] == "snow",
    "moons": lambda p: p["moons"] >= 2,
}


def find(galaxy_seed, words, limit=400, rules=None):
    """the first planet (by star order) that fits the words ("a warm planet with water")"""
    low = str(words).lower()
    tests = [f for w, f in WORDS.items() if w in low]
    if not tests:
        return None
    for i in range(limit):
        s = star(galaxy_seed, i, rules)
        for k in range(1, s["planets"] + 1):
            p = planet(galaxy_seed, i, k, rules)
            if all(f(p) for f in tests):
                return p
    return None


TYPES = {"rocky": "rock", "rock": "rock", "terrestrial": "rock", "desert": "rock", "ice": "ice", "icy": "ice",
         "frozen": "ice", "ocean": "wet", "water": "wet", "lava": "lava", "volcanic": "lava", "gas": "gas",
         "gas_giant": "gas", "ice_giant": "gas"}
TERRAIN = ("flat", "hills", "mountains", "craters", "dunes", "canyons", "volcanoes", "cliffs", "plains")

# The planet data form - what a planet IS (physics) and, separately, how it LOOKS (only visuals):
DATA_KEYS = {
    # what it is
    "name": "its name", "type": "rocky | ice | ocean | lava | gas | ice_giant",
    "radius": "in Earths (1 = Earth)", "mass": "in Earths (else from radius and gravity)",
    "gravity": "in Earths (0.72 = 0.72 × 9.81 m/s²); above 3 it is read as m/s²",
    "atmosphere": "true | false | \"thin\" | \"thick\"", "pressure": "bar at the ground (Earth 1, Mars 0.006, Venus 92)",
    "air_mix": "\"nitrogen,oxygen\" | \"co2\" | \"methane\" ... (oxygen = breathable)",
    "temperature": "kelvin at the ground (or temperature_c)", "day_hours": "one turn (Earth 24)",
    "year_days": "one orbit (Earth 365)", "tilt": "axis tilt in degrees (seasons; Earth 23.4)",
    "water": "none | ice | lakes | oceans | steam (else from the temperature and air)",
    "ocean_cover": "0..1 of the ground under water", "ice_caps": "true / false",
    "clouds": "0..1 cloud cover", "weather": "clear | clouds | rain | storm | snow | windy | dust_storm",
    "wind": "0 calm .. 6 cyclone (the shared wind)", "terrain": "list: flat hills mountains craters dunes canyons "
    "volcanoes cliffs", "magnetic_field": "true -> auroras at night (needs an air)",
    "life": "true / false or {\"plants\": true, \"creatures\": 3}", "moons": "a number or a list of {\"size\", \"colour\"}",
    "rings": "true / false", "star": "{\"name\", \"kind\", \"colour\", \"size\", \"temperature\"} - its sun",
    "planets_in_sky": "other planets seen in the sky (a number)",
    "civilization": "none | ancient | advanced (people of its own: canoes and ruins, or boats and towns; else from life)",
    # how it looks (visual only - never changes the physics)
    "base_place": "the visual template: desert, snow, beach, lake, moon, hills, mountains, jungle ...",
    "palette": "a palette name (desert, mars, ice, alien_pink ...) or {ground, rock, sand, sky, plant, water}",
    "sky_colour": "the sky colour (#hex)", "time": "the time of day for the scene",
}


def _num_or(d, k, default):
    try:
        return float(d.get(k, default))
    except (TypeError, ValueError):
        return default


def from_data(d):
    """A planet written as data (see DATA_KEYS): the planet is defined by its numbers; "base_place", "palette",
    "sky_colour" and "time" only choose the LOOK - they never change the physics. Anything left out is worked out
    from the rest (water from temperature + air, weather from water + air, escape speed from size + gravity)."""
    typ = str(d.get("type", "rocky")).lower().replace(" ", "_").replace("-", "_")
    surface = TYPES.get(typ, "rock")
    gas = surface == "gas"
    R = _num_or(d, "radius", 1.0) or 1.0
    gv = d.get("gravity", d.get("g"))
    if gv is not None:
        g = float(gv) * G_EARTH if float(gv) <= 3.0 else float(gv)
        mass = _num_or(d, "mass", g / G_EARTH * R * R)
    else:
        mass = _num_or(d, "mass", R ** 3)
        g = G_EARTH * mass / (R * R)
    Tc = _num_or(d, "temperature_c", _num_or(d, "temperature", 288.0) - 273.15)
    atm = d.get("atmosphere", d.get("air", True))
    pressure = d.get("pressure")
    if isinstance(atm, str):
        air = {"none": "none", "no": "none", "false": "none", "thin": "thin", "thick": "thick"}.get(atm.lower(), "thin")
    else:
        air = ("thick" if gas else "thin") if atm else "none"
    if pressure is not None:                              # the pressure decides thin / thick
        pr = float(pressure)
        air = "none" if pr < 0.001 else ("thin" if pr < 3.0 else "thick")
    else:
        pr = {"none": 0.0, "thin": 1.0, "thick": 10.0}[air]
    mix_ = str(d.get("air_mix", "nitrogen,oxygen" if air != "none" else "")).lower()
    water = d.get("water")
    if water is None:                                   # from the numbers: frozen, liquid, steam or none
        if gas:
            water = "clouds"
        elif air == "none":
            water = "ice" if Tc < -60 and surface == "ice" else "none"
        elif surface == "wet" or (-10 < Tc < 95 and float(d.get("ocean_cover", 0) or 0) > 0.05):
            water = "oceans"
        elif surface == "ice" or Tc < -10:
            water = "ice"
        elif Tc >= 95:
            water = "steam"
        else:
            water = "none"
    if "type" not in d and surface == "rock" and Tc > 400:   # (an explicit type is never changed)
        surface = "lava"
    clouds = d.get("clouds")
    weather = d.get("weather")
    if weather is None:
        weather = ("clear" if air == "none" else ("storm" if gas else ("snow" if water == "ice" else
                                                  ("rain" if water == "oceans" and (clouds or 0) > 0.5 else
                                                   ("clouds" if water == "oceans" else "windy")))))
    if air == "none":
        weather, clouds = "clear", 0.0                   # no air: no weather at all
    terrain = d.get("terrain") or (["craters"] if air == "none" else (["dunes"] if water == "none" and not gas
                                                                      else ["hills"]))
    if isinstance(terrain, str):
        terrain = [w.strip() for w in terrain.replace(",", " ").split()]
    life = d.get("life")
    if life is None:
        life = (not gas) and air != "none" and water in ("oceans", "lakes") and -15 < Tc < 50
    star_d = d.get("star") if isinstance(d.get("star"), dict) else {}
    star_T = _num_or(star_d, "temperature", _num_or(d, "star_temperature", 5778.0))
    star_c = star_d.get("colour", star_d.get("color", d.get("star_colour", d.get("star_color", star_colour(star_T)))))
    moons = d.get("moons", 0)
    moon_list = moons if isinstance(moons, list) else []
    n_moons = len(moon_list) if moon_list else int(moons or 0)
    r = _rng("data", repr(sorted((k, repr(v)) for k, v in d.items())))
    cols = _colours(r, surface if surface != "wet" else "rock", air, water, {"colour": star_c, "temperature": star_T}, Tc)
    v_esc = 11.2 * math.sqrt(max(1e-6, mass / R))
    p = {"galaxy": None, "star": None, "k": None, "name": str(d.get("name", "the planet")),
         "star_name": str(star_d.get("name", d.get("star") if isinstance(d.get("star"), str) else "its star")),
         "star_kind": str(star_d.get("kind", star_kind(star_T))), "star_colour": star_c,
         "star_size": _num_or(star_d, "size", _num_or(d, "star_size", 1.0)), "distance_au": d.get("distance"),
         "year_days": d.get("year_days", d.get("year")), "radius": R, "mass": mass, "g": g, "escape_kms": v_esc,
         "temperature_c": Tc, "air": air, "pressure": pr, "air_mix": mix_,
         "breathable": "oxygen" in mix_ and 0.5 <= pr <= 3.0 and -40 < Tc < 50,
         "water": water, "ocean_cover": _num_or(d, "ocean_cover", 0.7 if water == "oceans" else 0.0),
         "ice_caps": bool(d.get("ice_caps", water in ("oceans", "ice") and Tc < 30)),
         "surface": surface, "weather": weather, "clouds": clouds, "wind": d.get("wind"),
         "terrain": terrain, "magnetic_field": bool(d.get("magnetic_field", False)),
         "day_hours": d.get("day_hours"), "tilt": d.get("tilt"),
         "life": life, "moons": n_moons, "moon_list": moon_list, "rings": bool(d.get("rings", False)),
         "planets_in_sky": int(d.get("planets_in_sky", 0) or 0), "gas": gas, "colours": cols}
    civ = str(d.get("civilization") or "").lower()
    p["civilization"] = civ if civ in CIVS else civilization_of(p, p["name"])
    if d.get("base_place"):                             # the look only
        p["base_place"] = str(d["base_place"])
    if d.get("time"):
        p["time"] = str(d["time"])
    pal = d.get("palette")
    if isinstance(pal, dict):
        p["colours"] = dict(cols, **{k: v for k, v in pal.items() if isinstance(v, str)})
    elif isinstance(pal, str) and pal:
        from .palette import PRESETS as _PP
        if pal.lower() in _PP:
            p["colours"] = dict(cols, **{k: v for k, v in _PP[pal.lower()].items() if isinstance(v, str)})
        p["palette_name"] = pal
    if d.get("sky_colour") or d.get("sky_color"):
        p["colours"] = dict(p["colours"], sky=d.get("sky_colour") or d.get("sky_color"))
        p["sky_colour"] = p["colours"]["sky"]
    if d.get("star_disk"):                                   # a newborn star still inside its disk of dust and gas
        p["star_disk"], p["star_stage"] = True, "young"
    if d.get("life_stage") in LIFE_STAGES:                   # 🦠 how far life has come (microbes / oxygen_rising / seas / land)
        p["life_stage"] = d["life_stage"]
        if d["life_stage"] != "land":
            p["life"], p["breathable"] = False, False
    return p


def to_data(p):
    """A planet as data (the same form from_data() reads): what it IS, then how it LOOKS."""
    out = {"name": p["name"],
           "type": "gas" if p["gas"] else {"rock": "rocky", "wet": "ocean", "ice": "ice", "lava": "lava"}.get(
               p["surface"], "rocky"),
           "radius": round(p["radius"], 2) if p.get("radius") else None,
           "mass": round(p["mass"], 2) if p.get("mass") else None, "gravity": round(p["g"] / G_EARTH, 2),
           "atmosphere": p["air"] != "none", "pressure": p.get("pressure", {"none": 0, "thin": 1, "thick": 10}[p["air"]]),
           "air_mix": p.get("air_mix"), "temperature": round(p["temperature_c"] + 273.15),
           "day_hours": p.get("day_hours"), "year_days": round(p["year_days"]) if p.get("year_days") else None,
           "tilt": p.get("tilt"), "water": p["water"], "ocean_cover": p.get("ocean_cover"),
           "ice_caps": p.get("ice_caps"), "clouds": p.get("clouds"), "weather": p["weather"], "wind": p.get("wind"),
           "terrain": p.get("terrain"), "magnetic_field": p.get("magnetic_field"), "life": p["life"], "civilization": p.get("civilization"),
           "moons": p.get("moon_list") or p["moons"], "rings": p["rings"], "planets_in_sky": p.get("planets_in_sky", 0),
           "star": {"name": p["star_name"], "kind": p["star_kind"], "colour": p["star_colour"],
                    "size": round(p["star_size"], 2)},
           "escape_speed_kms": round(p["escape_kms"], 1) if p.get("escape_kms") else None,
           "breathable": p.get("breathable"),
           # the look (visual only)
           "base_place": base_place(p), "palette": p.get("palette_name") or {k: p["colours"][k] for k in ("ground", "sky")}}
    return {k: v for k, v in out.items() if v is not None}


def base_place(p):
    """the visual template for a planet (only the look): chosen from what the planet is, unless it names one"""
    if p.get("base_place"):
        return p["base_place"]
    if p["air"] == "none":
        return "moon"
    if p["gas"] or p["surface"] == "ice":
        return "snow"
    if p["water"] == "oceans":
        return "beach"
    if p["water"] == "lakes":
        return "river"                     # (land with water in it - the "lake" place is all water in 3D)
    return "desert"


def resolve(settings, scene):
    """the planet a scene is on, or None. settings / scene keys: galaxy, star, planet (see the module doc);
    "planet" can also be planet data (a dict - see from_data)"""
    pv = scene.get("planet", settings.get("planet"))
    if pv is None or pv is False:
        return None
    if isinstance(pv, dict):
        return from_data(pv)
    sysname = scene.get("planet_system", settings.get("planet_system"))
    if sysname:                                     # a planet of a saved system (engine/planet_systems.py)
        from . import planet_systems
        p = planet_systems.find_planet(sysname, pv)
        if p is not None:
            return p
    seed = scene.get("galaxy", settings.get("galaxy", 1))
    if isinstance(pv, str):                          # a real known planet ("proxima b", "trappist-1e" ...)
        from . import milkyway
        mp = milkyway.find_planet(pv)
        if mp is not None:
            return mp
    rules = int(scene.get("rules", settings.get("rules", 1)) or 1)       # stories made before the new rules keep the old stars
    era = scene.get("era", settings.get("era"))
    if era and isinstance(pv, str) and pv.lower().strip() == "earth":     # 🕰 "planet": "earth", "era": "jurassic"
        return earth_era(era)
    if isinstance(pv, str) and not pv.strip().isdigit():
        n = SOLAR_ALIASES.get(pv.lower().strip(), pv.lower().strip())
        if n in SOLAR:
            return solar(n)
        return find(seed, pv, rules=rules)
    st = int(scene.get("star", settings.get("star", 0)) or 0)
    return planet(seed, st, int(pv), rules)


# --------------------------------------------------------------------------- the planet as a place
def place_spec(p, bg=None):
    """(background spec, scene extras) that turn a scene into this planet: a base place recoloured by the planet's
    palette, its weather, the star (size + colour), moons, rings and other planets in the sky."""
    bg = dict(bg) if isinstance(bg, dict) else ({"preset": bg} if isinstance(bg, str) and bg else {})
    base = base_place(p)                                 # only the look; the planet's numbers decide the rest
    spec = {"preset": base, "code3d": False, "planet_place": True, "life": bool(p["life"]), "gas": bool(p["gas"])}
    if p["gas"]:
        spec.update(clouds="many", path=False, fog=True)
    if p["air"] != "none":
        w = p["weather"]
        spec["weather"] = {"dust_storm": "windy", "clouds": "clear"}.get(w, w)
        cc = p.get("clouds")
        if cc is None and w == "clouds":
            cc = 0.7
        if cc is not None:                                  # cloud cover 0..1 -> how many clouds
            cc = float(cc)
            spec["clouds"] = ("none" if cc < 0.05 else "few" if cc < 0.25 else "some" if cc < 0.5 else
                              "many" if cc < 0.8 else "overcast")
        if p.get("time"):
            spec["time"] = p["time"]
        if p.get("magnetic_field") and str(p.get("time", "")).lower() in ("night", "midnight", "dusk"):
            spec["sky"] = "aurora"                          # a magnetic field + an air: auroras at night
    elif p.get("time"):
        spec["time"] = p["time"]
    sky = []
    stage = p.get("star_stage") or ""
    if p.get("rogue") or stage == "black hole":                             # no sun at all: starlight only
        spec["time"] = "night"
    elif stage in ("neutron star", "pulsar"):                              # a city-sized star: a hard blue-white point
        from . import compact
        from .util import stable_hash
        key = f"{p.get('galaxy')}|{p.get('star')}"
        sp = compact.pulsar_period(key) if stage == "pulsar" or stable_hash("beam|" + key) % 100 < 25 else None
        sky.append({"type": "sun", "x": 1480, "p": 0.02, "layer": "sky", "color": "#cfe0ff", "radius": 4, "pulse_s": sp})
        spec.setdefault("time", "night")                                   # (it gives almost no light)
    else:                                                                  # its real size in the sky: a red giant fills it, a white dwarf is a dot
        size = clamp(p["star_size"], 0.04, 25.0)
        sky.append({"type": "sun", "x": 1480, "p": 0.02, "layer": "sky", "color": p["star_colour"],
                    "radius": min(430, 56 * size ** 0.6), "disk": stage == "young" or bool(p.get("star_disk"))})
    s2 = p.get("sun2")
    if s2 and not p.get("rogue"):                                          # ⭐⭐ a second sun - or, far away, a very bright star
        sz2 = float(s2.get("size") or 0)
        sky.append({"type": "sun", "x": 1120, "y": 640 if s2.get("far") else 760, "p": 0.02, "layer": "sky", "color": s2.get("colour") or "#ffd2af",
                    "radius": 5 if s2.get("far") else min(300, 56 * clamp(sz2, 0.04, 25.0) ** 0.6)})
    rr = _rng("sky", p["name"])
    moon_list = p.get("moon_list") or [{} for _ in range(min(4, p["moons"]))]
    for mo in moon_list[:5]:
        mo = mo if isinstance(mo, dict) else {}
        sky.append({"type": "planet", "x": rr.uniform(200, 1300), "p": 0.04, "layer": "sky",
                    "y": rr.uniform(600, 860), "radius": float(mo.get("size", rr.uniform(0.3, 1.0))) * 34,
                    "color": mo.get("colour", mo.get("color", _hsv(rr.random(), 0.15, rr.uniform(0.6, 0.9))))})
    for j in range(min(3, int(p.get("planets_in_sky", 0) or 0))):           # other planets: small bright discs
        sky.append({"type": "planet", "x": rr.uniform(100, 1700), "p": 0.03, "layer": "sky",
                    "y": rr.uniform(760, 900), "radius": rr.uniform(4, 9), "color": _hsv(rr.random(), 0.4, 0.95)})
    gcol, rcol = p["colours"]["ground"], p["colours"]["rock"]
    caps = p["temperature_c"] < 5 and p["water"] in ("ice", "oceans", "lakes")      # snow only where it is cold + wet
    for tr in (p.get("terrain") or []):                                    # the land's shape (any visual template)
        tr = str(tr).lower()
        if tr in ("mountains", "cliffs", "canyons"):
            sky.append({"type": "mountains", "x": 0, "p": 0.15, "layer": "far", "color": rcol, "seed": rr.random(),
                        "big": tr == "mountains", "snow": caps})
        elif tr == "volcanoes":
            sky.append({"type": "mountains", "x": 0, "p": 0.13, "layer": "far", "color": "#3a2a26", "seed": rr.random(),
                        "big": True, "snow": False, "cap": "#ff7a2a"})
        elif tr == "hills":
            sky.append({"type": "hills", "x": 0, "p": 0.3, "layer": "far", "color": gcol, "seed": rr.random()})
        elif tr == "dunes":
            sky.append({"type": "dunes", "x": 0, "p": 0.4, "layer": "far"})
        elif tr == "craters" and base != "moon":
            for k in range(6):
                sky.append({"type": "crater", "x": rr.uniform(-200, 2600), "p": 1.0, "layer": "front",
                            "y": -rr.uniform(20, 140), "scale": rr.uniform(0.5, 1.4)})
    if p.get("life_stage") in ("microbes", "oxygen_rising", "seas") and not p["gas"]:   # 🦠 a young living world:
        tint = {"microbes": "#6c4b5e", "oxygen_rising": "#3f5a44", "seas": "#4d5a40"}[p["life_stage"]]   # stromatolite
        for k in range({"microbes": 4, "oxygen_rising": 8, "seas": 3}[p["life_stage"]]):           # mounds in the shallows
            sky.append({"type": "rock", "x": rr.uniform(-100, 2500), "p": 1.0, "layer": "front", "y": -rr.uniform(10, 120),
                        "scale": rr.uniform(0.7, 1.6), "color": tint if k % 2 else "#7d7464"})
    if p.get("earth_in_sky"):
        sky.append({"type": "earth", "x": 900, "p": 0.04, "layer": "sky", "y": 600, "radius": 85})
    if p["rings"]:
        sky.append({"type": "sky_ring", "x": 0, "p": 0.03, "layer": "sky", "color": p["colours"]["sand"]})
    if p.get("solar"):
        spec["solar"] = p["solar"]                                          # a real world: no invented life
    elif not p["gas"] and (p["life"] or p["air"] == "none") and (not isinstance(bg, dict) or bg.get("life") is not False):
        from . import alien_life                                            # its own plants (or bare crystals)
        sky += alien_life.plant_elements(p, 2400)
    spec["sky_extra"] = sky
    for k, v in bg.items():                                                 # what the story wrote still wins
        if k != "preset":
            spec[k] = v
    extras = {"palette": {k: p["colours"][k] for k in ("ground", "rock", "sand", "sky", "fog", "plant", "leaves",
                                                        "wood", "water")},
              "gravity": round(p["g"], 2), "_planet": p}
    if p.get("wind") is not None:
        extras["wind"] = p["wind"]
    if p["air"] == "none":
        extras["palette"].pop("sky", None)
    return spec, extras


def describe(p):
    """one paragraph for the AI prompt / the validate log: what is on this planet"""
    if p is None:
        return ""
    bits = [f"{p['name']} ({p['star_kind']} {p['star_name']})", f"gravity {p['g']:.1f} m/s²",
            f"{p['temperature_c']:.0f} °C", f"air: {p['air']}", f"water: {p['water']}", f"weather: {p['weather']}"]
    if p.get("year_days"):
        bits.append(f"a year of {p['year_days']:.0f} days")
    if p["moons"]:
        bits.append(f"{p['moons']} moon(s)")
    if p["rings"]:
        bits.append("rings")
    if p.get("pressure") is not None and p["air"] != "none":
        bits.append(f"{p['pressure']:g} bar of {p.get('air_mix') or 'air'}" + (" (breathable)" if p.get("breathable")
                                                                             else " (not breathable)"))
    if p.get("day_hours"):
        bits.append(f"a day of {p['day_hours']:g} h")
    if p.get("terrain"):
        bits.append("land: " + ", ".join(map(str, p["terrain"])))
    st_ = p.get("life_stage")
    if st_ and st_ != "land":
        bits.append("life: " + {"microbes": "only microbes (mats, slime, stromatolites)", "oxygen_rising":
                                "microbes making oxygen (stromatolites in the shallows)", "seas": "only in the seas (seaweed, "
                                "soft drifting animals) - bare land"}[st_] + f" ({p.get('star_age_gyr', 0):.1f} billion years old)")
    else:
        bits.append("life: " + ("yes" if p["life"] else "no"))
    if p.get("civilization") and p["civilization"] != "none":
        bits.append(f"civilization: {p['civilization']}")
    return ", ".join(bits)


def why(p):
    """the physics reasons (for a lesson: 'why did this planet lose its air?')"""
    out = []
    if p.get("escape_kms"):
        out.append(f"escape speed {p['escape_kms']:.1f} km/s - " +
                   ("strong enough to keep an air" if p["air"] != "none" else "too weak (or too hot) to hold an air"))
    if p["air"] == "none":
        out.append("no air: no weather, no sound, a black sky, sharp shadows, craters stay")
    if p["surface"] == "lava":
        out.append("so close to its star that the rock melts")
    if p["surface"] == "ice":
        out.append("too far from its star: the water is frozen")
    if p["gas"]:
        out.append("a gas giant: no solid ground - deep clouds and storms")
    return out


# 🌙 the moons of a made-up planet: the planet tells only how many - each one is made here from the same rules, so you can
# fly to it and walk on it. Size: most moons are small (a few % to ~35 % of Earth's radius), rocky or icy by where the
# planet is (past the snow line, cold: ice); gravity from size (density ~3.3 rock, ~1.9 ice: g ∝ ρR); too small to hold an
# atmosphere unless big AND cold (Titan's rule: a cold, heavy moon keeps its air - the escape speed beats the gas's speed);
# warmth: the planet's own equilibrium warmth (the same sunlight) minus what the missing air would have added.
def moon(galaxy_seed, star_index, k, m):
    """moon m (1-based) of planet k: a full planet dict (from_data), or None"""
    p = planet(galaxy_seed, star_index, k)
    n = int(p.get("moons") or 0)
    if p.get("solar") or not 1 <= int(m) <= max(0, min(6, n)):
        return None
    r = _rng("moon", galaxy_seed, star_index, k, m)
    T0 = float(p["temperature_c"])
    if p.get("air") != "none":                          # (the planet's air kept it warmer than its moon will be)
        T0 -= min(60.0, float(p.get("greenhouse_K") or 30.0))
    icy = T0 < -60 or (p.get("gas") and r.random() < 0.6)
    R = round(clamp(math.exp(r.uniform(math.log(0.03), math.log(0.38))), 0.02, 0.45), 3)
    rho = 1.9 if icy else 3.3
    g = round(R * rho / 5.51, 4)                        # in Earth g: g ∝ ρ·R (Earth: 5.51 g/cm³)
    keeps_air = R > 0.3 and T0 < -120                   # (Titan: big and cold)
    names = "abcdef"
    d = {"name": f"{p['name']} {names[int(m) - 1]}", "type": "icy" if icy else "rocky", "radius": R, "gravity": g,
         "temperature_c": round(T0 + r.uniform(-15, 5), 1), "atmosphere": "thick" if keeps_air else "none",
         "air_mix": "nitrogen,methane" if keeps_air else "", "terrain": ["craters", "plains"] if not keeps_air else ["dunes", "hills"],
         "life": False, "star_colour": p.get("star_colour"), "moons": 0}
    out = from_data(d)
    out.update(galaxy=galaxy_seed, star=star_index, parent=p["name"], moon_of=k, moon=int(m), civilization="none",
               star_kind=p.get("star_kind"), star_size=p.get("star_size"), star_flux=p.get("star_flux"), distance_au=p.get("distance_au"))
    return out
