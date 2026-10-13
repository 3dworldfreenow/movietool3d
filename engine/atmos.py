"""⚗ The air, clouds and seas by chemistry (school level, simplified - every step a real reaction / rule):

    air(p) -> {gases: {formula: %}, pressure, M (g/mol), gamma, scatter (Rayleigh, Earth air = 1),
               greenhouse_K, clouds: [...], liquid, boil_c, sea: {...}, why: [...]}

    1. hydrogen kept or lost (Jeans escape: kept if the escape speed > ~6× hydrogen's speed): kept -> a "reducing" air -
       carbon becomes methane CH₄, nitrogen ammonia NH₃, oxygen water H₂O (Jupiter, Titan); lost -> carbon becomes
       CO₂, nitrogen stays N₂ (Venus, Mars, the early Earth)
    2. heat shifts the balance: CH₄ + H₂O ⇌ CO + 3H₂ - above ~1000 K carbon is CO, below it methane
    3. volcanoes breathe out H₂O, CO₂, SO₂, N₂ (more with more inside heat); argon builds up from K-40 decay
    4. gases taken away: liquid water + moving rock pull CO₂ into limestone (the carbon-silicate cycle); rocks rust
       free O₂ away - only life keeps O₂ in the air (photosynthesis: 6CO₂ + 6H₂O -> C₆H₁₂O₆ + 6O₂)
    5. UV light splits water high up; the hydrogen escapes (Venus lost its seas)
    6. clouds condense where their temperature allows: water, sulfuric acid (SO₂ + H₂O), ammonia, methane, rock
    7. seas: water is liquid between freezing and its boiling point at this pressure (Clausius-Clapeyron); very cold
       worlds with methane have methane lakes; CO₂ / SO₂ make them acid; rivers make them salty over time
Our Solar System: the real measured airs (the same rules have to give them - a check).
"""
import math

from .util import clamp

REAL_AIR = {
    "earth": {"N₂": 78.08, "O₂": 20.95, "Ar": 0.93, "H₂O": 1.0, "CO₂": 0.042},
    "mars": {"CO₂": 95.3, "N₂": 2.6, "Ar": 1.9, "O₂": 0.17, "CO": 0.08},
    "venus": {"CO₂": 96.5, "N₂": 3.5, "SO₂": 0.015},
    "jupiter": {"H₂": 89.8, "He": 10.2, "CH₄": 0.3, "NH₃": 0.026},
    "saturn": {"H₂": 96.3, "He": 3.25, "CH₄": 0.45},
    "uranus": {"H₂": 82.5, "He": 15.2, "CH₄": 2.3},
    "neptune": {"H₂": 80.0, "He": 19.0, "CH₄": 1.5},
    "titan": {"N₂": 98.4, "CH₄": 1.4, "H₂": 0.1},
}
M = {"N₂": 28.0, "O₂": 32.0, "Ar": 39.9, "CO₂": 44.0, "H₂O": 18.0, "CH₄": 16.0, "NH₃": 17.0, "H₂": 2.0, "He": 4.0,
     "SO₂": 64.1, "CO": 28.0, "H₂S": 34.1}
GAMMA = {"N₂": 1.4, "O₂": 1.4, "Ar": 1.67, "CO₂": 1.29, "H₂O": 1.33, "CH₄": 1.31, "NH₃": 1.31, "H₂": 1.41, "He": 1.67,
         "SO₂": 1.29, "CO": 1.4, "H₂S": 1.32}
SCAT = {"N₂": 1.0, "O₂": 0.83, "Ar": 0.89, "CO₂": 2.3, "H₂O": 0.8, "CH₄": 2.1, "NH₃": 1.6, "H₂": 0.22, "He": 0.012,
        "SO₂": 3.5, "CO": 1.1, "H₂S": 3.0}                                     # Rayleigh strength ∝ (n-1)², next to N₂


def boil_c(pressure_bar, L=40700.0, Tb=373.15):
    """water's boiling point at this pressure (Clausius-Clapeyron); None below the triple point (no liquid at all)"""
    if pressure_bar < 0.00612:
        return None
    return round(1.0 / (1.0 / Tb - 8.314 * math.log(pressure_bar / 1.01325) / L) - 273.15, 1)


def _mix_from_words(words, life):
    w = words.lower()
    if "hydrogen" in w or "helium" in w:
        return {"H₂": 86.0, "He": 13.6, "CH₄": 0.3, "NH₃": 0.03}
    if "methane" in w:
        return {"N₂": 94.0, "CH₄": 5.6, "H₂": 0.1}
    if "co2" in w and "nitrogen" in w:
        return {"N₂": 60.0, "CO₂": 38.0, "Ar": 1.5, "H₂O": 0.5}
    if "co2" in w:
        return {"CO₂": 95.0, "N₂": 3.0, "Ar": 1.6, "SO₂": 0.1}
    return {"N₂": 78.0, "O₂": 21.0, "Ar": 0.9, "CO₂": 0.04} if life or "oxygen" in w else {"N₂": 95.0, "CO₂": 3.5, "Ar": 1.5}


def air(p):
    from . import alien_life, elements
    if p.get("air") == "none":
        return {"gases": {}, "pressure": 0.0, "why": ["no air: too small or too hot to hold one (it escaped to space)"], "clouds": [],
                "liquid": None, "boil_c": None, "sea": None, "greenhouse_K": 0, "M": 0, "gamma": 0, "scatter": 0}
    solar = p.get("solar") or ""
    T = float(p["temperature_c"]) + 273.15
    P = alien_life.air_density(p) if not solar else {"earth": 1.0, "mars": 0.006, "venus": 92.0, "titan": 1.47}.get(solar, 10.0)
    comp = elements.composition(p)
    why = []
    life = bool(p.get("life"))
    if p.get("era_gases"):                                                  # 🕰 Earth in a past era (galaxy.earth_era)
        gases = dict(p["era_gases"])
        why.append("Earth's air in that era - read from air bubbles in old ice, fossil leaves (their breathing pores) and old rocks")
    elif solar in REAL_AIR:
        gases = dict(REAL_AIR[solar])
        why.append("real measured air")
    elif p.get("galaxy") is None and not p.get("mw") and str(p.get("air_mix") or "").strip():
        gases = _mix_from_words(str(p["air_mix"]), life)        # a planet written as data: its own air, as given
        why.append("its air as the planet's data says (" + str(p["air_mix"]) + ")")
    elif p.get("gas"):
        gases = {"H₂": 86.0, "He": 13.5, "CH₄": 0.4, "NH₃": 0.05, "H₂O": 0.05}
        why.append("a giant keeps the young disk's hydrogen and helium; carbon, nitrogen and oxygen are there as CH₄, NH₃, H₂O")
    else:
        v_esc = float(p.get("escape_kms") or 11.2)
        v_h2 = 1.57 * math.sqrt(T / 300.0)                                   # km/s: hydrogen's thermal speed
        keeps_h = v_esc > 6 * v_h2
        heat = comp.get("inside_heat", 1.0)
        wet = p.get("water") in ("oceans", "lakes")
        if keeps_h:
            gases = {"H₂": 55.0, "N₂": 20.0, "CH₄": 12.0, "H₂O": 6.0, "NH₃": 5.0, "He": 2.0}
            why.append("heavy and cold enough to keep hydrogen: a reducing air - methane, ammonia, water")
            if T > 1000:
                gases["CO"] = gases.pop("CH₄"); why.append("so hot that methane turns into CO + H₂ (CH₄ + H₂O ⇌ CO + 3H₂)")
        else:
            why.append("its hydrogen escaped to space: carbon ends up as CO₂, nitrogen as N₂")
            if wet and heat >= 0.4:
                gases = {"N₂": 95.0, "CO₂": 0.8, "Ar": 1.0 * heat, "H₂O": 1.0}
                why.append("liquid water + moving rock pull CO₂ into limestone (the carbon-silicate cycle)")
            else:
                gases = {"CO₂": 90.0, "N₂": 7.0, "Ar": 1.5 * heat}
                why.append("no seas to take the CO₂ out: it stays in the air" + (" (a runaway greenhouse)" if T > 400 else ""))
            if heat > 1.3:
                gases["SO₂"] = 0.3 * heat; why.append("lots of volcanoes: SO₂ in the air")
            stage = p.get("life_stage")
            if not life and stage in ("microbes", "oxygen_rising", "seas"):     # 🦠 a younger living world (galaxy.life_stage)
                o2, ch4 = {"microbes": (0.0, 1.2), "oxygen_rising": (1.5, 0.15), "seas": (12.0, 0.01)}[stage]
                gases["CO₂"] = max(gases.get("CO₂", 0), {"microbes": 3.0, "oxygen_rising": 1.0, "seas": 0.3}[stage])
                gases["CH₄"] = ch4
                if o2:
                    gases["O₂"] = o2
                why.append({"microbes": "microbes that live without oxygen make methane (CO₂ + 4H₂ -> CH₄ + 2H₂O): no free oxygen yet - "
                                        "a 'reducing' air like young Earth's",
                            "oxygen_rising": "microbes that use sunlight split water and let out oxygen (6CO₂ + 6H₂O -> C₆H₁₂O₆ + 6O₂); "
                                             "most of it still rusts the iron in rocks and seas - only ~1-2 % reaches the air",
                            "seas": "seaweed and sea life pour out oxygen: ~12 % now (you need ~16 % to breathe) - the methane is "
                                    "gone, burnt by the oxygen"}[stage])
            if life:
                o2 = 21.0 if wet else 8.0
                gases["O₂"] = o2; gases["CO₂"] = min(gases.get("CO₂", 0), 0.1); gases["CH₄"] = 0.0002
                why.append("life makes oxygen (photosynthesis) - rocks rust it away, so O₂ stays only while life keeps making it")
            if "co2" in str(p.get("air_mix") or "").lower() and not life:
                gases.setdefault("CO₂", 50)
        if comp.get("c_to_o", 0.55) > 0.85 and not keeps_h:
            gases["CO"] = gases.get("CO", 0) + 5; gases["CH₄"] = gases.get("CH₄", 0) + 2; why.append("a carbon world: smoggy CO and hydrocarbons")
        if not keeps_h and T > 340 and p.get("water") in ("none", "steam") and "blue" in str(p.get("star_kind", "")) + "white":
            why.append("strong UV split its water high up; the hydrogen escaped - the seas are gone")
    tot = sum(gases.values()) or 1
    gases = {k: round(v / tot * 100, 3 if v / tot < 0.01 else 2) for k, v in sorted(gases.items(), key=lambda kv: -kv[1]) if v > 0}
    # the gas's numbers
    Mavg = sum(M[g] * f for g, f in gases.items()) / 100.0
    gam = sum(GAMMA.get(g, 1.4) * f for g, f in gases.items()) / 100.0
    sc = sum(SCAT.get(g, 1.0) * f for g, f in gases.items()) / 100.0
    # the greenhouse: an optical depth from the heat-trapping gases (simple grey model, tuned so Earth ≈ +33 K)
    pp = {g: P * f / 100.0 for g, f in gases.items()}
    tau = grey_tau(P, pp.get("CO₂", 0), pp.get("H₂O", 0), pp.get("CH₄", 0), pp.get("NH₃", 0))
    T_eq = T / (1 + 0.75 * tau) ** 0.25
    gh = round(T - T_eq)
    # albedo: how much sunlight the ground and clouds throw back (ice / snow ~0.6, ocean ~0.06, rock ~0.15, clouds ~0.5)
    alb = {"ice": 0.6, "oceans": 0.06, "lakes": 0.12, "none": 0.18, "steam": 0.5}.get(str(p.get("water")), 0.18)
    if p.get("gas") or P > 30:
        alb = 0.5
    if solar in REAL_ALBEDO:                                                   # measured Bond albedo
        alb = REAL_ALBEDO[solar]
    elif p.get("albedo") is not None:                                           # rules 3: from the planet's own climate loop
        alb = p["albedo"]
        why.extend(p.get("climate_why") or [])
    if p.get("climate_why"):
        why.append(f"it throws back {alb * 100:.0f} % of the sunlight (albedo {alb:g}) - that and the greenhouse set its temperature")
    elif p.get("water") == "ice" and T < 263 and solar not in REAL_ALBEDO:
        why.append(f"ice throws back ~{alb * 100:.0f} % of the sunlight (albedo): it stays cold, and the cold keeps the ice - a snowball world locks itself in")
    elif p.get("water") == "oceans":
        why.append("dark seas soak up ~94 % of the sunlight (albedo 0.06): they store heat and soften the seasons")
    # clouds: what condenses at these temperatures
    clouds = []
    if "H₂O" in gases or p.get("water") in ("oceans", "lakes"):
        if 200 < T < 400 and not (solar == "venus"):
            clouds.append("water")
    if "SO₂" in gases and T > 240 and P > 0.5:
        clouds.append("sulfuric acid (SO₂ + H₂O -> H₂SO₄)")
    if "NH₃" in gases and T < 250:
        clouds.append("ammonia")
    if "CH₄" in gases and gases["CH₄"] > 0.5 and T < 120:
        clouds.append("methane")
    if T > 1500:
        clouds.append("rock / iron (it rains molten rock)")
    # the seas
    bp = boil_c(P)
    liquid, sea = None, None
    if T < 115 and gases.get("CH₄", 0) > 1 and P > 0.5:
        liquid = "methane / ethane"
        sea = {"liquid": liquid, "pH": None, "salt": None, "why": "-180 °C: methane is liquid (like Titan's lakes)"}
    elif 195 < T < 240 and gases.get("NH₃", 0) > 1 and P > 0.06 and p.get("water") in ("ice", "oceans", "lakes"):
        liquid = "ammonia"                                                      # NH₃ is liquid from -78 to -33 °C (at 1 bar)
        sea = {"liquid": liquid, "pH": 11.5, "salt": None, "why": f"{T - 273:.0f} °C: ammonia is liquid here (-78 to -33 °C) - strongly alkaline seas (pH ~11.5)"}
    elif p.get("water") in ("oceans", "lakes") and bp is not None and 273 < T < bp + 273.15:
        liquid = "water"
        acid = gases.get("CO₂", 0) * P / 100 > 0.01 or "SO₂" in gases
        pH = 8.1 if not acid else (2.5 if "SO₂" in gases and gases["SO₂"] > 0.05 else 6.0)
        salt = round(clamp(3.5 * (comp.get("inside_heat", 1.0) ** 0.3), 0.5, 8), 1)
        sea = {"liquid": "water", "pH": pH, "salt": salt,
               "why": ("acid from dissolved CO₂ / SO₂" if acid else "buffered by rocks (like Earth's seas, pH 8.1)") + f"; {salt} % salt washed from the rocks"}
    # 🟠 photolysis: the star's UV splits CH₄ (and N₂) high up; the pieces join into tholins - an orange smog that eats blue
    # light (Titan). Needs methane, enough air to hold the haze, no free oxygen (O₂ would burn the pieces) and not too hot
    haze = None
    if gases.get("CH₄", 0) >= 0.5 and P >= 0.05 and gases.get("O₂", 0) < 1 and T < 400 and not p.get("gas"):
        haze = {"colour": "#c8913a", "strength": round(clamp(math.sqrt(gases["CH₄"] * P) / 2.5, 0.25, 1.0), 2)}
        why.append("UV light splits the methane high up; the pieces stick into tholins - an orange smog that soaks up blue light (like Titan)")
    return {"albedo": alb, "gases": gases, "pressure": round(P, 4), "M": round(Mavg, 2), "gamma": round(gam, 3), "scatter": round(sc, 2),
            "greenhouse_K": gh, "clouds": clouds, "liquid": liquid, "boil_c": bp, "sea": sea, "why": why, "haze": haze}


def grey_tau(P, co2, h2o=0.0, ch4=0.0, nh3=0.0):
    """the greenhouse's optical depth (bars in). CO₂ grows with the log of its amount (its bands saturate) plus a
    p² part at huge pressures (collision-induced absorption - Venus); water vapour, methane, ammonia by √p; the
    rest of the air broadens the lines (0.4 √P). Tuned: Earth +33 K, Mars +5 K, Venus +500 K (with its clouds)."""
    return (0.04 * math.log(1 + co2 / 1e-4) + 0.0159 * co2 * co2 + 2.5 * math.sqrt(h2o) + 6 * math.sqrt(ch4)
            + 3 * math.sqrt(nh3) + 0.4 * math.sqrt(P))


REAL_ALBEDO = {"mercury": 0.088, "venus": 0.76, "earth": 0.306, "moon": 0.11, "mars": 0.25, "jupiter": 0.503, "saturn": 0.342,
               "uranus": 0.30, "neptune": 0.29, "pluto": 0.72, "io": 0.63, "europa": 0.68, "enceladus": 0.81, "titan": 0.27,
               "ganymede": 0.43, "callisto": 0.22, "triton": 0.76, "charon": 0.38, "ceres": 0.09, "vesta": 0.42}


def circulation(p, lat=None):
    """🌀 the winds by the planet's spin (the Coriolis effect): moving air is turned right in the north, left in the
    south - so storms spin anticlockwise in the north, clockwise in the south; the faster and bigger the planet, the
    more wind belts each half gets (Earth 3: trade winds, westerlies, polar easterlies; Jupiter many bands; slow
    Venus one big cell from the equator to the pole). Tidally locked: air flows from the night side to the day side."""
    if p.get("air") == "none":
        return None
    if p.get("solar") in SOLAR_CELLS:
        cells = SOLAR_CELLS[p["solar"]]
    else:
        spin = 24.0 / max(1.0, float(p.get("day_hours") or 24))
        R = float(p.get("radius") or 1.0)
        cells = 1 if p.get("tidal_lock") else int(clamp(round(3 * (spin * R) ** 0.35), 1, 12))
    out = {"cells": cells, "lines": []}
    if p.get("tidal_lock"):
        out["lines"].append("tidally locked: the air rises over the hot day side and sinks on the night side - near the ground, winds blow from the night side toward the sun")
        out["prevailing"] = "from the night side"
        return out
    out["lines"].append(f"{cells} wind belt(s) in each half of the planet" + (" - like Earth's trade winds, westerlies and polar easterlies" if cells == 3 else
                        " - many striped bands (a fast, big spinner)" if cells > 4 else " - one big loop from the equator to the pole (a slow spinner)" if cells == 1 else ""))
    out["lines"].append("storms spin anticlockwise in the north and clockwise in the south (the Coriolis effect)")
    if lat is not None:
        band = int(min(cells - 1, abs(float(lat)) / (90.0 / cells)))
        east = band % 2 == 0                                   # the band at the equator blows from the east (trade winds)
        out["prevailing"] = ("from the east" if east else "from the west")
        out["band"] = band
        out["lines"].append(f"here ({abs(float(lat)):.0f}° {'N' if float(lat) >= 0 else 'S'}) the usual wind blows {out['prevailing']}")
    return out


SOLAR_CELLS = {"earth": 3, "mars": 2, "venus": 1, "jupiter": 7, "saturn": 6, "uranus": 3, "neptune": 3}
