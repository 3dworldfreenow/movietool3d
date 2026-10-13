"""🧪 The 118 real elements, where they come from, and what a planet is made of - by real rules.

    ELEMENTS            symbol -> {z, name, mass, cat, melt, boil, density, sun, crust, origin, job}
                        (melt / boil in K, density g/cm³ - only where well measured; None = not measured / not needed)
    origin(z)           where the element is made (Big Bang, stars, supernovae, neutron-star mergers, cosmic rays, labs)
    composition(p)      what a planet is made of: metallicity from its star's place in the galaxy, what can condense
                        where it formed (iron / rock near the star, ices past the snow line, gas for giants), the layers
                        (core / mantle / crust / ice / gas), the main elements in %, the carbon-to-oxygen ratio, its
                        inside heat from radioactive elements; our Solar System = real measured values
Nothing is stored: worked out from the seed (and the real tables) each time.
"""
import math
import random

from .util import clamp, stable_hash

# symbol, name, standard atomic mass (brackets in tables = most stable isotope)
_T = """H Hydrogen 1.008|He Helium 4.0026|Li Lithium 6.94|Be Beryllium 9.0122|B Boron 10.81|C Carbon 12.011|N Nitrogen 14.007|O Oxygen 15.999|F Fluorine 18.998|Ne Neon 20.180|
Na Sodium 22.990|Mg Magnesium 24.305|Al Aluminium 26.982|Si Silicon 28.085|P Phosphorus 30.974|S Sulfur 32.06|Cl Chlorine 35.45|Ar Argon 39.95|K Potassium 39.098|Ca Calcium 40.078|
Sc Scandium 44.956|Ti Titanium 47.867|V Vanadium 50.942|Cr Chromium 51.996|Mn Manganese 54.938|Fe Iron 55.845|Co Cobalt 58.933|Ni Nickel 58.693|Cu Copper 63.546|Zn Zinc 65.38|
Ga Gallium 69.723|Ge Germanium 72.630|As Arsenic 74.922|Se Selenium 78.971|Br Bromine 79.904|Kr Krypton 83.798|Rb Rubidium 85.468|Sr Strontium 87.62|Y Yttrium 88.906|Zr Zirconium 91.224|
Nb Niobium 92.906|Mo Molybdenum 95.95|Tc Technetium 98|Ru Ruthenium 101.07|Rh Rhodium 102.91|Pd Palladium 106.42|Ag Silver 107.87|Cd Cadmium 112.41|In Indium 114.82|Sn Tin 118.71|
Sb Antimony 121.76|Te Tellurium 127.60|I Iodine 126.90|Xe Xenon 131.29|Cs Caesium 132.91|Ba Barium 137.33|La Lanthanum 138.91|Ce Cerium 140.12|Pr Praseodymium 140.91|Nd Neodymium 144.24|
Pm Promethium 145|Sm Samarium 150.36|Eu Europium 151.96|Gd Gadolinium 157.25|Tb Terbium 158.93|Dy Dysprosium 162.50|Ho Holmium 164.93|Er Erbium 167.26|Tm Thulium 168.93|Yb Ytterbium 173.05|
Lu Lutetium 174.97|Hf Hafnium 178.49|Ta Tantalum 180.95|W Tungsten 183.84|Re Rhenium 186.21|Os Osmium 190.23|Ir Iridium 192.22|Pt Platinum 195.08|Au Gold 196.97|Hg Mercury 200.59|
Tl Thallium 204.38|Pb Lead 207.2|Bi Bismuth 208.98|Po Polonium 209|At Astatine 210|Rn Radon 222|Fr Francium 223|Ra Radium 226|Ac Actinium 227|Th Thorium 232.04|
Pa Protactinium 231.04|U Uranium 238.03|Np Neptunium 237|Pu Plutonium 244|Am Americium 243|Cm Curium 247|Bk Berkelium 247|Cf Californium 251|Es Einsteinium 252|Fm Fermium 257|
Md Mendelevium 258|No Nobelium 259|Lr Lawrencium 266|Rf Rutherfordium 267|Db Dubnium 268|Sg Seaborgium 269|Bh Bohrium 270|Hs Hassium 269|Mt Meitnerium 278|Ds Darmstadtium 281|
Rg Roentgenium 282|Cn Copernicium 285|Nh Nihonium 286|Fl Flerovium 289|Mc Moscovium 290|Lv Livermorium 293|Ts Tennessine 294|Og Oganesson 294"""

# well-measured melting point K, boiling point K, density g/cm³ (at room temperature; gases at 0 °C, 1 atm)
_PHYS = {"H": (14.01, 20.28, 0.0000899), "He": (None, 4.22, 0.000179), "Li": (453.7, 1615, 0.534), "Be": (1560, 2742, 1.85),
         "B": (2349, 4200, 2.34), "C": (None, 3915, 2.27), "N": (63.15, 77.36, 0.00125), "O": (54.36, 90.19, 0.00143),
         "F": (53.5, 85.03, 0.0017), "Ne": (24.56, 27.07, 0.0009), "Na": (370.9, 1156, 0.971), "Mg": (923, 1363, 1.738),
         "Al": (933.5, 2792, 2.70), "Si": (1687, 3538, 2.33), "P": (317.3, 550, 1.82), "S": (388.4, 717.8, 2.07),
         "Cl": (171.6, 239.1, 0.0032), "Ar": (83.8, 87.3, 0.00178), "K": (336.5, 1032, 0.862), "Ca": (1115, 1757, 1.55),
         "Ti": (1941, 3560, 4.506), "V": (2183, 3680, 6.0), "Cr": (2180, 2944, 7.19), "Mn": (1519, 2334, 7.21),
         "Fe": (1811, 3134, 7.874), "Co": (1768, 3200, 8.90), "Ni": (1728, 3186, 8.908), "Cu": (1357.8, 2835, 8.96),
         "Zn": (692.7, 1180, 7.14), "Ga": (302.9, 2477, 5.91), "Ge": (1211, 3106, 5.32), "Se": (494, 958, 4.81),
         "Br": (265.8, 332, 3.10), "Kr": (115.8, 119.9, 0.00375), "Rb": (312.5, 961, 1.53), "Sr": (1050, 1655, 2.64),
         "Zr": (2128, 4682, 6.52), "Mo": (2896, 4912, 10.28), "Ag": (1234.9, 2435, 10.49), "Sn": (505.1, 2875, 7.31),
         "I": (386.9, 457.4, 4.93), "Xe": (161.4, 165.1, 0.0059), "Cs": (301.6, 944, 1.93), "Ba": (1000, 2170, 3.51),
         "W": (3695, 5828, 19.25), "Pt": (2041.4, 4098, 21.45), "Au": (1337.3, 3129, 19.30), "Hg": (234.3, 629.9, 13.53),
         "Pb": (600.6, 2022, 11.34), "Rn": (202, 211.3, 0.00973), "Ra": (973, 2010, 5.5), "Th": (2023, 5061, 11.7),
         "U": (1405.3, 4404, 19.1)}
# the Sun's mass fractions (Asplund et al. 2009, rounded) and Earth's crust mass fractions (CRC, rounded)
_SUN = {"H": 0.7381, "He": 0.2485, "O": 0.0057, "C": 0.0024, "Ne": 0.0013, "Fe": 0.0013, "N": 0.0007, "Si": 0.0007,
        "Mg": 0.0007, "S": 0.0003, "Ar": 0.00007, "Ni": 0.00007, "Ca": 0.00006, "Al": 0.00006, "Na": 0.00003}
_CRUST = {"O": 0.461, "Si": 0.282, "Al": 0.0823, "Fe": 0.0563, "Ca": 0.0415, "Na": 0.0236, "Mg": 0.0233, "K": 0.0209,
          "Ti": 0.00565, "H": 0.0014, "P": 0.00105, "Mn": 0.00095, "F": 0.000585, "Ba": 0.000425, "Sr": 0.00037,
          "S": 0.00035, "C": 0.0002, "Zr": 0.000165, "Cl": 0.000145, "Cr": 0.000102, "Ni": 0.000084, "Zn": 0.00007,
          "Cu": 0.00006, "Pb": 0.000014, "U": 0.0000027, "Au": 0.000000004}

_CAT = {}
for z in (3, 11, 19, 37, 55, 87): _CAT[z] = "alkali metal"
for z in (4, 12, 20, 38, 56, 88): _CAT[z] = "alkaline earth metal"
for z in list(range(21, 31)) + list(range(39, 49)) + list(range(72, 81)) + list(range(104, 113)): _CAT[z] = "transition metal"
for z in (13, 31, 49, 50, 81, 82, 83, 84, 113, 114, 115, 116): _CAT[z] = "post-transition metal"
for z in (5, 14, 32, 33, 51, 52): _CAT[z] = "metalloid"
for z in (1, 6, 7, 8, 15, 16, 34): _CAT[z] = "nonmetal"
for z in (9, 17, 35, 53, 85, 117): _CAT[z] = "halogen"
for z in (2, 10, 18, 36, 54, 86, 118): _CAT[z] = "noble gas"
for z in range(57, 72): _CAT[z] = "lanthanide (rare earth)"
for z in range(89, 104): _CAT[z] = "actinide"


def origin(z):
    """where element z is made (real nucleosynthesis, simplified)"""
    if z in (1, 2):
        return "the Big Bang (the first minutes of the universe)"
    if z == 3:
        return "the Big Bang + cosmic rays + old stars"
    if z in (4, 5):
        return "cosmic rays splitting heavier atoms in space"
    if z <= 26:
        return "made inside stars by fusion (up to iron in big stars), spread by stellar winds and supernovae"
    if z in (43, 61):
        return "unstable - only tiny traces in nature (made in reactors / stars)"
    if z <= 83:
        return ("mostly neutron-star mergers and rare supernovae (the r-process)" if z in (52, 63, 76, 77, 78, 79)
                else "slow neutron capture in old giant stars (s-process) + supernovae / neutron-star mergers")
    if z <= 92 or z == 94:
        return "neutron-star mergers (r-process); radioactive - some decay into others" + (" (made in labs too)" if z == 94 else "")
    return "made only in laboratories (too short-lived to last in nature)"


_JOBS = {"H": "stars, gas giants, water; light enough to escape small warm planets",
         "He": "stars, gas giants; escapes small planets; no chemistry", "C": "life's backbone; CO₂ / methane in the air; carbon worlds",
         "N": "most of Earth's air; proteins / DNA", "O": "rocks (silicates), water, breathing, ozone (O₃)",
         "Si": "rock-maker (silicates) - the crust and mantle", "Mg": "rock-maker (mantle); chlorophyll's middle",
         "Fe": "the core -> the magnetic field; rust-red rocks; red blood", "Ni": "the core (with iron)",
         "S": "volcanic gas, sulfuric-acid clouds, yellow crusts; life's recipe", "P": "DNA and bones (life's recipe)",
         "Ca": "limestone (takes CO₂ out of the air), shells, bones", "Al": "rock-maker (crust: feldspar, clay)",
         "Na": "salty seas, salt flats", "Cl": "salt (NaCl) in seas", "K": "rock-maker; K-40 heats the inside, dates rocks",
         "Cu": "green / blue minerals; blue blood (octopuses)", "U": "inside heat (radioactive), dating rocks",
         "Th": "inside heat (radioactive)", "Ar": "noble gas in the air (from K-40 decay)", "Ne": "noble gas", "Ti": "colours gems, strong rocks",
         "Au": "rare ore; from neutron-star mergers", "Pt": "rare ore; from neutron-star mergers", "Ra": "radioactive", "Rn": "radioactive gas from rocks"}
_GROUP_JOB = {"alkali metal": "salts in seas / rocks", "alkaline earth metal": "rocks and shells", "transition metal": "ores, colours of minerals",
              "post-transition metal": "ores", "metalloid": "rocks (traces)", "nonmetal": "gases, life", "halogen": "salts in seas",
              "noble gas": "air without chemistry", "lanthanide (rare earth)": "traces in rocks (a civilization's tech)",
              "actinide": "radioactive: inside heat (U, Th) or lab-made"}

ELEMENTS = {}
for z, row in enumerate([r.strip() for r in _T.replace("\n", "").split("|")], start=1):
    sym, name, mass = row.split()
    cat = _CAT.get(z, "unknown")
    mp, bp, d = _PHYS.get(sym, (None, None, None))
    ELEMENTS[sym] = {"z": z, "symbol": sym, "name": name, "mass": float(mass), "cat": cat, "melt": mp, "boil": bp, "density": d,
                     "sun": _SUN.get(sym), "crust": _CRUST.get(sym), "origin": origin(z), "job": _JOBS.get(sym, _GROUP_JOB.get(cat, "")),
                     "natural": z <= 94 and z not in (43, 61) or z in (43, 61), "man_made": z > 94}
BY_Z = {e["z"]: e for e in ELEMENTS.values()}

# real measured bulk mixes (mass %) and layers (mass %) for our Solar System
REAL = {
    "earth": ({"Fe": 32.1, "O": 30.1, "Si": 15.1, "Mg": 13.9, "S": 2.9, "Ni": 1.8, "Ca": 1.5, "Al": 1.4}, {"core": 32.5, "mantle": 67.1, "crust": 0.4}),
    "venus": ({"Fe": 31.2, "O": 30.9, "Si": 15.8, "Mg": 14.5, "S": 1.9, "Ni": 1.8, "Ca": 1.6, "Al": 1.4}, {"core": 30, "mantle": 69.6, "crust": 0.4}),
    "mercury": ({"Fe": 64.5, "O": 15.5, "Si": 7.5, "Mg": 6.8, "Ni": 4.1, "S": 0.6, "Ca": 0.5, "Al": 0.5}, {"core": 70, "mantle": 29.5, "crust": 0.5}),
    "mars": ({"O": 36.8, "Fe": 23.7, "Si": 16.6, "Mg": 14.9, "S": 4.0, "Ca": 1.7, "Al": 1.4, "Ni": 1.4}, {"core": 24, "mantle": 75.5, "crust": 0.5}),
    "moon": ({"O": 43.0, "Si": 20.2, "Mg": 19.3, "Fe": 10.7, "Ca": 3.2, "Al": 3.2, "Ti": 0.2, "Na": 0.1}, {"core": 1.5, "mantle": 97.5, "crust": 1.0}),
    "jupiter": ({"H": 71.0, "He": 24.0, "O": 1.6, "C": 0.8, "N": 0.3, "S": 0.2, "Ne": 0.2, "Fe": 0.2}, {"core": 5, "gas": 95}),
    "saturn": ({"H": 74.0, "He": 21.0, "O": 2.0, "C": 1.0, "N": 0.4, "S": 0.2, "Fe": 0.3, "Si": 0.3}, {"core": 15, "gas": 85}),
    "uranus": ({"O": 40.0, "H": 23.0, "C": 12.0, "N": 8.0, "He": 5.0, "Si": 4.0, "Fe": 4.0, "Mg": 3.0}, {"core": 10, "ice": 75, "gas": 15}),
    "neptune": ({"O": 41.0, "H": 22.0, "C": 12.0, "N": 8.0, "He": 4.0, "Si": 5.0, "Fe": 4.0, "Mg": 3.0}, {"core": 12, "ice": 75, "gas": 13}),
}


def _rng(*parts):
    return random.Random(stable_hash("|".join(str(x) for x in parts)) % (2 ** 31))


def metallicity(p):
    """[Fe/H] (0 = the Sun): from the star's place in the galaxy - richer near the middle (many generations of stars
    have lived and blown up there), poorer far out; a little scatter from the seed"""
    if p.get("solar"):
        return 0.0
    if p.get("mw"):                                                            # a real known star: its measured metals
        from . import milkyway
        return milkyway.FEH.get(p.get("real_star"), 0.0)
    try:
        from . import galaxy
        s = galaxy.star(galaxy.gseed(p), int(p.get("star", 0)), p.get("rules", 1))
        if s.get("feh") is not None:                                          # rules 2: worked out with the star (place + age)
            return s["feh"]
        d = math.hypot(s["x"], s["y"])                                       # 0 middle .. 1 edge
    except Exception:                                                          # noqa: BLE001
        d = 0.55
    r = _rng("feh", p.get("name", ""))
    return round(clamp(0.9 * (0.55 - d) + r.gauss(0, 0.12), -1.2, 0.5), 2)


def composition(p):
    """what this planet is made of (see the module doc) -> dict"""
    solar = p.get("solar") or ""
    if solar in ("io", "europa", "enceladus", "titan"):     # moons of the giants: heat from being squeezed (tidal heating)
        from .galaxy import MOON_OF
        mo = MOON_OF[solar]
        rocky = solar == "io"
        return {"metallicity": 0.0, "bulk": {"O": 45, "Si": 15, "Fe": 18, "Mg": 12, "S": 6, "other": 4} if rocky else
                {"H₂O ice": 50, "rock": 45, "other": 5}, "layers": {"core": 20 if rocky else 15, "mantle": 79 if rocky else 50,
                "crust": 1 if rocky else 35}, "c_to_o": 0.55, "inside_heat": mo["tidal"], "real": True, "tidal": True,
                "why": ["real measured values", "🌋 tidal heating: " + mo["why"]]}
    if solar in REAL:
        bulk, layers = REAL[solar]
        return {"metallicity": 0.0, "bulk": bulk, "layers": layers, "c_to_o": 0.55, "inside_heat": 1.0 if solar == "earth" else
                {"venus": 0.9, "mars": 0.35, "mercury": 0.3, "moon": 0.1}.get(solar, 1.0), "real": True,
                "why": ["real measured values"]}
    r = _rng("comp", p.get("name", ""))
    feh = metallicity(p)
    metal = 10 ** feh                                                          # heavy elements next to the Sun
    lum = 1.0
    try:
        from . import galaxy
        lum = galaxy.star(galaxy.gseed(p), int(p.get("star", 0)), p.get("rules", 1))["luminosity"]
    except Exception:                                                          # noqa: BLE001
        pass
    a = float(p.get("distance_au") or 1.0)
    if p.get("mw") and p.get("star_flux") is not None:                         # a real known planet: its real star
        lum = p["star_flux"] * a * a
    T_form = 1100 * lum ** 0.25 / math.sqrt(max(0.05, a))                   # how hot the disk was where it formed (K)
    snow = 2.7 * math.sqrt(max(0.01, lum))
    c_to_o = round(clamp(0.55 * 10 ** r.gauss(0, 0.12) * (1 + 0.3 * feh), 0.2, 1.5), 2)
    why = [f"metallicity [Fe/H] {feh:+.2f}: " + ("rich in heavy elements (near the galaxy's middle)" if feh > 0.15 else
                                                   "poor in heavy elements (far out)" if feh < -0.2 else "about like the Sun")]
    if p.get("gas"):
        z = 0.013 * metal * r.uniform(2, 5)
        bulk = {"H": 73 * (1 - z), "He": 25 * (1 - z), "O": 45 * z, "C": 20 * z, "N": 8 * z, "Fe": 10 * z, "Si": 9 * z, "S": 8 * z}
        layers = {"core": round(8 * metal, 1), "gas": round(100 - 8 * metal, 1)}
        why.append("a gas giant: it grabbed hydrogen and helium from the young disk")
    else:
        core = clamp(0.32 + 0.38 * (T_form - 1100) / 800, 0.08, 0.72) * clamp(metal ** 0.3, 0.6, 1.4)
        ice = clamp((a - snow) / snow, 0.0, 0.5) if a > snow else 0.0
        e = {"Fe": 32.1 * core / 0.32, "Ni": 1.8 * core / 0.32, "O": 30.1, "Si": 15.1, "Mg": 13.9, "S": 2.9 * (1.5 if T_form < 900 else 1),
             "Ca": 1.5, "Al": 1.4}
        if c_to_o > 0.85:
            e["C"] = 12 * (c_to_o - 0.8)
            e["O"] *= 0.7
            why.append(f"carbon-to-oxygen {c_to_o}: a carbon world - graphite and carbide rocks, diamond deep inside")
        tot = sum(e.values())
        e = {k: v / tot * 100 * (1 - ice) for k, v in e.items()}
        if ice:
            e["O"] = e.get("O", 0) + 89 * ice
            e["H"] = e.get("H", 0) + 11 * ice
            why.append(f"formed past the snow line ({snow:.1f} AU): {round(ice * 100)} % ices (water, ammonia, methane)")
        bulk = e
        layers = {"core": round(core * 100 * (1 - ice), 1), "mantle": round((1 - core) * 100 * (1 - ice) - 0.5, 1), "crust": 0.5}
        if ice:
            layers["ice"] = round(ice * 100, 1)
        if T_form > 1400:
            why.append("formed hot, close to its star: an iron-rich world with a big core (like Mercury)")
        elif T_form < 700 and not ice:
            why.append("formed cool: more sulfur and water-bearing rock")
    heat = round(clamp(metal * (float(p.get("mass") or 1.0)) ** 0.3, 0.05, 4.0), 2)
    extras = []
    st = None
    try:
        from . import galaxy
        if p.get("star") is not None and not p.get("mw"):
            st = galaxy.star(galaxy.gseed(p), int(p.get("star", 0)), p.get("rules", 1))
    except Exception:                                                          # noqa: BLE001
        st = None
    if st and st.get("age_gyr") is not None:
        age = st["age_gyr"]
        if age > 8 and feh < -0.2:                                              # 2) born early, from gas few stars had enriched yet
            why.append(f"its star is old ({age:.1f} billion years): born from gas with few heavy elements - smaller iron cores, fewer rocky planets")
        elif age < 2 and feh > 0.1:
            why.append(f"its star is young ({age:.1f} billion years): made of gas recycled by many earlier stars - rich in iron and rock")
        # 4) the neighbourhood: a supernova nearby when it formed, or long ago a neutron-star merger (a kilonova)
        try:
            near = [f for f in galaxy.features(galaxy.gseed(p)) if f["kind"] == "supernova remnant"
                    and math.hypot(f["x"] - st["x"], f["y"] - st["y"]) < f["size"] * 4]
        except Exception:                                                      # noqa: BLE001
            near = []
        if near and not p.get("gas"):
            heat = round(min(4.0, heat * (1.35 if age < 0.2 else 1.1)), 2)
            extras.append("extra O, Si, Fe from a nearby supernova")
            why.append("formed near an exploded star (a supernova remnant on the map): extra oxygen, silicon and iron" +
                       (", and radioactive Al-26 that kept its young insides molten" if age < 0.2 else ""))
        if _rng("kilonova", str(galaxy.gseed(p)), str(p.get("star"))).random() < 0.04 + 0.04 * (feh > 0.2):   # one birth cloud: the whole system
            heat = round(min(4.0, heat * 1.25), 2)
            extras.append("gold, platinum and uranium ×3 (a kilonova)")
            why.append("its birth cloud caught the debris of two neutron stars colliding long ago (a kilonova): ~3× the gold, platinum and "
                       "uranium - more uranium = more heat inside")
        if st.get("mass", 1) < 0.5 and not p.get("gas") and a < snow:
            why.append("a red dwarf's planet: it formed close in and dry - its water had to come later from comets, if at all")
    if heat > 1.5:
        why.append("lots of radioactive U / Th / K inside: a hot interior (volcanoes, a long-lived magnetic field)")
    elif heat < 0.4:
        why.append("little radioactive heat: a cold, quiet interior")
    top = dict(sorted(((k, round(v, 1)) for k, v in bulk.items() if v >= 0.05), key=lambda kv: -kv[1])[:8])
    return {"metallicity": feh, "bulk": top, "layers": layers, "c_to_o": c_to_o, "inside_heat": heat, "real": False, "why": why, "extras": extras}


def table():
    """all 118 for the page / API"""
    return [BY_Z[z] for z in range(1, 119)]


MINERALS = [
    # name, formula, test(ctx) -> bool, why
    ("basalt (olivine, pyroxene)", "(Mg,Fe)₂SiO₄ …", lambda c: c["rocky"], "cooled lava - the first rock of every rocky world"),
    ("quartz", "SiO₂", lambda c: c["rocky"] and c["T"] < 1600, "silicon + oxygen: the most common mineral in a crust that has melted and cooled again"),
    ("clay", "Al₂Si₂O₅(OH)₄", lambda c: c["rocky"] and (c["liquid_water"] or c["solar"] == "mars"), "rock slowly turned soft by liquid water (weathering; Mars: its old lake beds)"),
    ("limestone / calcite", "CaCO₃", lambda c: c["rocky"] and c["liquid_water"] and c["co2"] > 0, "CO₂ dissolved in seas joins calcium (the carbon-silicate cycle) - often built by shells"),
    ("rust / hematite", "Fe₂O₃", lambda c: c["rocky"] and c["o2"] > 0.1 and (c["liquid_water"] or c["solar"] == "mars"), "iron + free oxygen + water (Mars: from long ago)"),
    ("magnetite", "Fe₃O₄", lambda c: c["rocky"] and c["o2"] <= 0.1, "iron oxide that forms without free oxygen - black, magnetic"),
    ("gypsum", "CaSO₄·2H₂O", lambda c: c["rocky"] and c["water_any"] and c["sulfur"] and c["T"] < 60, "calcium + sulfur + water; above ~60 °C it loses its water"),
    ("rock salt (halite)", "NaCl", lambda c: c["rocky"] and c["water_any"] and (c["T"] > 20 or c["solar"] == "mars"), "left behind where salty water dried up"),
    ("serpentine", "Mg₃Si₂O₅(OH)₄", lambda c: c["rocky"] and c["water_any"] and c["heat"] > 0.6, "hot water seeping through deep olivine (it makes hydrogen - food for microbes)"),
    ("native sulfur", "S", lambda c: c["sulfur"] and c["T"] < 115, "yellow crystals round volcano vents; it melts at 115 °C"),
    ("graphite", "C", lambda c: c["c_to_o"] > 0.8, "a carbon-rich world: spare carbon becomes graphite (and diamond deep down)"),
    ("water ice", "H₂O", lambda c: c["T"] < 0 and c["water_any"], "frozen water"),
    ("methane clathrate", "CH₄·5.75H₂O", lambda c: c["T"] < -10 and c["water_any"] and c["ch4"] > 0, "methane trapped in a cage of water ice - cold, under pressure"),
    ("dry ice", "CO₂", lambda c: c["T"] < -78 and c["co2"] > 0, "carbon dioxide frozen solid (below -78 °C) - Mars's polar caps"),
    ("ammonia ice", "NH₃", lambda c: c["T"] < -78 and c["nh3"] > 0, "frozen ammonia (below -78 °C)"),
    ("nitrogen ice", "N₂", lambda c: c["T"] < -210, "even the air freezes (below -210 °C) - Pluto's plains"),
    ("molten rock", "-", lambda c: c["rocky"] and c["T"] > 1100, "too hot for most crystals to stay solid - a lava world"),
]


def minerals(p):
    """🪨 which minerals can form here - real stability rules (temperature, pressure, water, air, elements)
    -> [{"name", "formula", "why"}, ...] (cheap: once per planet)"""
    from . import atmos
    try:
        a = atmos.air(p)
    except Exception:                                                          # noqa: BLE001
        a = {"gases": {}, "liquid": None}
    gs = a.get("gases") or {}
    comp = composition(p)
    T = float(p.get("temperature_c") or 0)
    c = {"T": T, "rocky": not p.get("gas"), "liquid_water": a.get("liquid") == "water",
         "water_any": p.get("water") in ("oceans", "lakes", "ice", "steam") or a.get("liquid") == "water",
         "co2": gs.get("CO₂", 0), "o2": gs.get("O₂", 0), "ch4": gs.get("CH₄", 0), "nh3": gs.get("NH₃", 0),
         "sulfur": "SO₂" in gs or "volcanoes" in (p.get("terrain") or []) or comp.get("inside_heat", 1) > 1.3 or p.get("solar") == "io",
         "heat": comp.get("inside_heat", 1.0), "c_to_o": comp.get("c_to_o", 0.55), "solar": p.get("solar") or ""}
    out = []
    for name, formula, test, why in MINERALS:
        try:
            if test(c):
                out.append({"name": name, "formula": formula, "why": why})
        except Exception:                                                      # noqa: BLE001
            pass
    return out
