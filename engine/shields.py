"""🛡 What keeps a planet - and life - safe (how our Earth does it), by simple real rules:

    shields(p) -> {field (Earth = 1), dose_msv_day, xrays_day, ozone, uv, giant_guard, big_moon, life_recipe: {...}, why: [...]}

    magnetic field   a dynamo needs a liquid iron core (12.8: core size + inside heat) and a fast spin; Mars and Venus
                     have none (Mars' core froze; Venus spins too slowly) -> the star's wind slowly strips the air
    radiation        cosmic rays + the star's particles, stopped by the air column above you (g/cm² = p / g) and the
                     field: Earth ≈ 0.007 mSv a day, Mars ≈ 0.7, the Moon ≈ 1.4 (a chest X-ray ≈ 0.1 mSv)
    ozone            O₂ + UV -> O₃ - only where there is free oxygen (made by life); it blocks the star's harsh UV
    a giant guard    a gas giant further out pulls many comets away (Jupiter) -> fewer big impacts
    a big moon       steadies the tilt (our Moon) -> steady seasons
    life's recipe    liquid water + energy (starlight / inside heat) + C H N O P S
Our Solar System: real values.
"""
import math

from .util import clamp

REAL_FIELD = {"earth": 1.0, "mercury": 0.011, "venus": 0.0, "moon": 0.0, "mars": 0.0, "jupiter": 14.0, "saturn": 0.7,
              "uranus": 0.75, "neptune": 0.45, "pluto": 0.0, "ganymede": 0.025}   # (Ganymede: the only moon with its own field, ~720 nT)


REAL_TILT = {"mercury": 0.03, "venus": 177.4, "earth": 23.44, "moon": 6.7, "mars": 25.19, "jupiter": 3.13, "saturn": 26.73, "uranus": 97.77,
             "neptune": 28.32, "pluto": 122.5, "io": 0.0, "europa": 0.1, "enceladus": 0.0, "titan": 0.3,
             "ganymede": 0.33, "callisto": 0.0, "triton": 0.0, "charon": 119.6, "ceres": 4.0, "vesta": 29.0}
TILT_RANGE = {"earth": (22.1, 24.5), "mars": (0.0, 60.0), "venus": (177.0, 178.0), "mercury": (0.0, 0.1), "moon": (6.7, 6.7),
              "jupiter": (3.0, 3.3), "saturn": (26.0, 27.5), "uranus": (97.7, 97.9), "neptune": (28.0, 28.6), "pluto": (102.0, 126.0)}


def shields(p):
    from . import atmos, elements, galaxy
    solar = p.get("solar") or ""
    comp = elements.composition(p)
    chem = atmos.air(p)
    why = []
    # the magnetic field
    if solar in REAL_FIELD:
        field = REAL_FIELD[solar]
    else:
        core = (comp.get("layers") or {}).get("core", 30) / 32.5
        heat = comp.get("inside_heat", 1.0)
        spin = clamp(24.0 / max(1.0, float(p.get("day_hours") or 24)), 0.05, 3.0)
        mass = float(p.get("mass") or 1.0)
        field = 0.0 if (heat < 0.3 or mass < 0.15) else round(clamp(core * heat * spin ** 0.5 * mass ** 0.3, 0, 30), 2)
        if p.get("gas"):
            field = round(clamp(5 * spin * (mass / 100) ** 0.5, 0.2, 30), 2)
    if field >= 0.3:
        why.append(f"a magnetic field ({field}× Earth's) turns away the star's wind - auroras at the poles show it working")
    elif p.get("air") != "none" and not p.get("gas"):
        why.append("no real magnetic field: the star's wind slowly strips the air (as it did to Mars)")
    # radiation at the ground
    P = chem.get("pressure", 0.0) or 0.0
    g = max(0.1, float(p.get("g") or 9.81))
    col = P * 1e5 / g / 10.0                                                         # g/cm² of air above you (Earth ≈ 1030)
    if solar in ("jupiter", "saturn", "uranus", "neptune") or p.get("gas"):
        dose = 0.0
    else:
        dose = 1.37 * math.exp(-col / 25.0) * (1 - 0.6 * min(1.0, field)) + 0.005 * comp.get("inside_heat", 1.0)
        if solar == "earth":
            dose = 0.0066
    dose = round(dose, 4)
    xr = round(dose / 0.1, 2)
    if dose > 0.3:
        why.append(f"☢ radiation {dose} mSv a day (≈ {xr} chest X-rays) - a suit / shelter needed for long stays")
    if p.get("air") != "none" and not p.get("gas"):
        why.append("the air burns up most meteoroids 80-120 km up: shooting stars instead of craters" if P > 0.05 else
                   "the air is too thin to burn up meteoroids well: many reach the ground")
    elif not p.get("gas"):
        why.append("no air to burn up meteoroids: every rock hits the ground - craters everywhere")
    # ozone + UV
    o2 = (chem.get("gases") or {}).get("O₂", 0)
    ozone = o2 > 1.0
    hot_star = any(k in str(p.get("star_kind", "")) for k in ("blue", "white"))
    uv = "low" if (ozone or P > 5) else ("very high" if hot_star or P < 0.1 else "high")
    if ozone:
        why.append("an ozone layer (O₂ + UV -> O₃, from life's oxygen) blocks the harsh UV")
    elif p.get("air") != "none":
        why.append(f"no ozone (no free oxygen): UV at the ground is {uv} - life would hide under water, ice or rock")
    # a giant guard further out / a big moon
    guard = False
    if solar:
        guard = solar in ("mercury", "venus", "earth", "moon", "mars")
    elif p.get("mw"):                                                                 # a real known planet
        from . import milkyway
        mine = milkyway.PLANETS.get(p["mw"])
        guard = bool(mine) and any(v[0] == mine[0] and v[1] > mine[1] and (v[4] or 0) > 15 for v in milkyway.PLANETS.values())
    else:
        try:
            s = galaxy.star(galaxy.gseed(p), int(p.get("star", 0)), p.get("rules", 1))
            for k in range(int(p.get("k", 1)) + 1, int(s.get("planets", 0)) + 1):
                if galaxy.planet(galaxy.gseed(p), int(p.get("star", 0)), k, p.get("rules", 1)).get("gas"):
                    guard = True
                    break
        except Exception:                                                             # noqa: BLE001
            guard = False
    if guard and not p.get("gas"):
        why.append("a giant planet further out pulls many comets away (like Jupiter): fewer big impacts")
    from .util import stable_hash
    big_moon = solar == "earth" or (not solar and int(p.get("moons") or 0) >= 1 and float(p.get("radius") or 1) < 2
                                    and stable_hash("bigmoon|" + p.get("name", "")) % 3 == 0)
    # 🌍 the tilt over millions of years: steadied by a big moon (Earth 22.1-24.5°), chaotic without one (Mars 0-60°+, Laskar)
    tilt = float(p.get("tilt") if p.get("tilt") is not None else REAL_TILT.get(solar, 20.0))
    if solar in TILT_RANGE:
        lo, hi = TILT_RANGE[solar]
    elif big_moon or p.get("gas"):
        lo, hi = max(0.0, tilt - 1.2), tilt + 1.2
    elif p.get("tidal_lock"):
        lo, hi = 0.0, 0.0
    else:
        lo, hi = max(0.0, tilt - 25 - stable_hash("tilt|" + p.get("name", "")) % 10), min(85.0, tilt + 30 + stable_hash("tilt2|" + p.get("name", "")) % 15)
    swing = hi - lo
    if big_moon:
        why.append(f"a big moon steadies its tilt: over millions of years it only nods between {lo:.1f}° and {hi:.1f}° - steady seasons, gentle ice ages")
    elif p.get("tidal_lock"):
        why.append("tidally locked: no tilt to wobble - the same side always faces the star")
    elif swing > 10:
        why.append(f"no big moon to steady it: over millions of years its tilt wobbles chaotically between {lo:.0f}° and {hi:.0f}° - "
                   "at high tilt the poles bake in summer and the ice moves to the middle; the climate swings hard (Mars' ice ages)")
    else:
        why.append(f"its tilt stays steady ({lo:.1f}°-{hi:.1f}°)")
    # life's recipe
    water = chem.get("liquid") == "water"
    energy = True
    chnops = comp.get("metallicity", 0) > -0.9
    recipe = {"liquid water": water, "energy (light / inside heat)": energy, "C H N O P S": chnops,
              "a magnetic field": field >= 0.3, "ozone": ozone}
    score = sum(recipe.values())
    return {"field": field, "dose_msv_day": dose, "xrays_day": xr, "ozone": ozone, "uv": uv, "giant_guard": guard,
            "big_moon": bool(big_moon), "tilt_range": [round(lo, 1), round(hi, 1)], "life_recipe": recipe, "life_score": score, "why": why}
