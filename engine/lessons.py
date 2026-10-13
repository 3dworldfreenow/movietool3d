"""📚 planet lessons (12.9 / 12.10): short step-by-step answers, each step shown on a real Solar-System world.
Every number is read from the same rules the planet cards and the walk use (atmos / shields / elements) -
nothing here is typed by hand except the words round them. Cheap: built on request, nothing stored."""
from functools import lru_cache


def _d(name):
    import planetweb
    from . import galaxy
    return planetweb.detail(galaxy.solar(name), {"solar": name})


def _gas(d, g):
    return (d.get("chem") or {}).get("gases", {}).get(g, 0)


def _field(s):
    f = s.get("field") or 0
    return "almost none left" if f < 0.05 else f"now {f:.2g}× Earth's"


def _venus():
    v, e, me = _d("venus"), _d("earth"), _d("mercury")
    cv, ce = v["chem"], e["chem"]
    return {"id": "venus_hot", "title": "Why is Venus so hot?", "icon": "🔥", "steps": [
        {"planet": "venus", "head": "Hotter than Mercury",
         "text": f"Venus is {v['temperature_c']} °C at the ground - hotter than Mercury (average {me['temperature_c']} °C), which is twice as close to the Sun. "
                 f"So closeness alone can't be the answer."},
        {"planet": "venus", "head": "A white mirror of cloud",
         "text": f"Its clouds of {', '.join(cv['clouds']) or 'acid'} throw back {round(cv['albedo'] * 100)} % of the sunlight "
                 f"(Earth: {round(ce['albedo'] * 100)} %). Venus actually takes in LESS sunlight than Earth."},
        {"planet": "venus", "head": "A blanket 92 times thicker",
         "text": f"The air is {cv['pressure']:g} bar ({cv['pressure'] / ce['pressure']:.0f}× Earth) and {_gas(v, 'CO₂'):.1f} % carbon dioxide. "
                 f"Sunlight gets in, but the heat (infrared) can't get out: the greenhouse adds +{cv['greenhouse_K']} K "
                 f"(Earth's adds +{ce['greenhouse_K']} K - just enough for liquid water)."},
        {"planet": "earth", "head": "Why Earth didn't do the same",
         "text": "On Earth, rain washes CO₂ out of the air and the seas lock it into limestone (CaCO₃). Venus lost its water, "
                 "so the CO₂ stayed in the air - a runaway greenhouse."},
    ]}


def _oxygen():
    e, m = _d("earth"), _d("mars")
    return {"id": "earth_oxygen", "title": "How did Earth get its oxygen?", "icon": "🌿", "steps": [
        {"planet": "mars", "head": "Oxygen doesn't stay on its own",
         "text": f"Free oxygen is too eager to react: it rusts rocks and burns things. Mars's air is only {_gas(m, 'O₂'):.2f} % O₂ - "
                 "and its red rust (Fe₂O₃) shows where the oxygen went."},
        {"planet": "earth", "head": "Life makes it",
         "text": "About 2.4 billion years ago tiny ocean microbes (cyanobacteria) learnt photosynthesis: "
                 "CO₂ + H₂O + light → sugar + O₂. They have been making oxygen ever since."},
        {"planet": "earth", "head": "First the rocks, then the air",
         "text": "For hundreds of millions of years the seas' iron soaked it up (banded iron rocks). Only when the iron was used up "
                 f"did O₂ build up in the air - now {_gas(e, 'O₂'):.1f} %."},
        {"planet": "earth", "head": "A bonus: the ozone shield",
         "text": "Sunlight turns some O₂ into ozone (O₃) high up. It blocks the harsh UV, so life could finally leave the water. "
                 "A planet with lots of free oxygen is a strong sign of life."},
    ]}


def _titan():
    t = _d("titan")
    ct = t["chem"]
    return {"id": "titan_orange", "title": "Why is Titan orange?", "icon": "🟠", "steps": [
        {"planet": "titan", "head": "Thick, cold air",
         "text": f"Titan is a moon with air {ct['pressure']:g}× as thick as Earth's: {_gas(t, 'N₂'):.1f} % nitrogen and "
                 f"{_gas(t, 'CH₄'):.1f} % methane, at {t['temperature_c']} °C."},
        {"planet": "titan", "head": "Sunlight breaks the methane",
         "text": "Ultraviolet light from the Sun splits CH₄ and N₂ high up. The pieces join into bigger and bigger molecules (tholins) "
                 "- an orange-brown smog."},
        {"planet": "titan", "head": "The haze eats blue light",
         "text": "The smog bits soak up blue light and let red and orange through, so the sky and the ground look orange "
                 "(on Earth tiny air molecules scatter blue - our blue sky)."},
        {"planet": "titan", "head": "Methane rain and lakes",
         "text": f"It is cold enough for methane to rain and fill lakes ({', '.join(ct['clouds']) or 'methane'} clouds) - "
                 "the only other place we know with rain, rivers and seas, just not of water."},
    ]}


def _mars():
    m, e = _d("mars"), _d("earth")
    sm = m["shields"]
    return {"id": "mars_air", "title": "Why does Mars have so little air?", "icon": "🔴", "steps": [
        {"planet": "mars", "head": "Thin air",
         "text": f"Mars's air is just {m['chem']['pressure']:g} bar - {e['chem']['pressure'] / max(m['chem']['pressure'], 1e-6):.0f}× thinner than Earth's. "
                 "Water would boil and freeze at once; you'd need a pressure suit."},
        {"planet": "mars", "head": "Small and weak",
         "text": f"Gravity is only {m['g']} m/s² (Earth {e['g']}). Light gas molecules escape to space more easily."},
        {"planet": "mars", "head": "It lost its shield",
         "text": f"Mars is small, so its core cooled and its magnetic field died ({_field(sm)}). "
                 "Without it the Sun's wind slowly stripped the air away over billions of years."},
        {"planet": "mars", "head": "It used to be wetter",
         "text": "Old river valleys, clays and salt flats show Mars once had a thicker air and liquid water. "
                 f"Without a field, the ground now gets {sm['dose_msv_day']:.2f} mSv of radiation a day (≈ {sm['xrays_day']:g} chest X-rays)."},
    ]}


def _jupiter():
    j = _d("jupiter")
    w = (j.get("winds") or {}).get("lines") or []
    return {"id": "jupiter_stripes", "title": "What makes Jupiter's stripes?", "icon": "🪐", "steps": [
        {"planet": "jupiter", "head": "A ball of gas",
         "text": f"Jupiter has no ground: {_gas(j, 'H₂'):.0f} % hydrogen and {_gas(j, 'He'):.0f} % helium all the way down."},
        {"planet": "jupiter", "head": "It spins fast",
         "text": "A day on Jupiter is under 10 hours, and it is 11× wider than Earth. The fast spin (the Coriolis effect) "
                 f"breaks the rising and sinking air into many belts: {w[0] if w else 'many wind belts'}."},
        {"planet": "jupiter", "head": "Light zones, dark belts",
         "text": f"Where gas rises it cools and makes white {', '.join(j['chem']['clouds']) or 'ammonia'} ice clouds (zones). "
                 "Where it sinks the clouds clear and we see deeper, darker, browner layers (belts)."},
        {"planet": "jupiter", "head": "Storms between the belts",
         "text": "Neighbouring belts blow in opposite directions at hundreds of km/h. Where they rub, storms spin up - "
                 "the Great Red Spot is one bigger than Earth, seen for over 190 years."},
    ]}


def _protect():
    e, m, mo, v = _d("earth"), _d("mars"), _d("moon"), _d("venus")
    se, sm, smo = e["shields"], m["shields"], mo["shields"]
    return {"id": "earth_protects", "title": "How the Earth protects us", "icon": "🛡", "steps": [
        {"planet": "earth", "head": "Five shields",
         "text": "Air, a magnetic field, ozone, Jupiter and the Moon. Each one is easiest to see on a world that doesn't have it."},
        {"planet": "mars", "head": "🧲 The magnetic field",
         "text": f"Earth's hot iron core makes a magnetic field that turns away the Sun's wind (auroras show it working). "
                 f"Mars's field died ({_field(sm)}) and the wind stripped its air. Radiation on Mars: {sm['dose_msv_day']:.2f} mSv a day, "
                 f"on Earth {se['dose_msv_day']:.3f}."},
        {"planet": "moon", "head": "🌫 The air",
         "text": f"Our air burns up most space rocks as shooting stars. The Moon has none: every rock hits, so it is covered in craters, "
                 f"and its ground gets {smo['dose_msv_day']:.2f} mSv a day."},
        {"planet": "mars", "head": "☀ The ozone layer",
         "text": f"Life's oxygen makes ozone, which blocks the harsh UV (Earth: UV {se['uv']}). No free oxygen means no ozone - "
                 f"on Mars the UV is {sm['uv']}; life would have to hide under rock or ice."},
        {"planet": "jupiter", "head": "🪐 A giant guard",
         "text": "Jupiter's huge gravity flings many comets away from the inner planets - fewer giant impacts on Earth."},
        {"planet": "earth", "head": "🌙 A big moon",
         "text": f"Our big Moon steadies Earth's tilt, so the seasons stay the same for millions of years "
                 f"({'Earth has one ✅' if se['big_moon'] else '-'}; Mars's tiny moons can't, so its tilt wobbles a lot)."},
        {"planet": "venus", "head": "And the right amount of greenhouse",
         "text": f"Earth's greenhouse adds +{e['chem']['greenhouse_K']} K - just enough for liquid water. "
                 f"Venus's runaway one adds +{v['chem']['greenhouse_K']} K: {v['temperature_c']} °C."},
    ]}


def _blackhole():
    from . import compact
    sg, st = compact.centre(1, "spiral", True), compact.black_hole(10)
    BH = {"ground": "#000000", "sky": "#f2a250"}
    return {"id": "black_hole", "title": "What is a black hole?", "icon": "⚫", "steps": [
        {"planet": None, "name": "a black hole", "colours": BH, "head": "Gravity that even light can't beat",
         "text": "Squeeze enough mass into a small enough ball and the speed needed to escape it passes the speed of light. "
                 "The edge where that happens is the horizon, at r = 2GM/c² (the Schwarzschild radius)."},
        {"planet": None, "name": "a star's black hole", "colours": BH, "head": "Made by a dying giant star",
         "text": f"A star born with more than ~20 Suns' mass collapses at the end. A 10-Sun black hole has a horizon of just {st['horizon']} - "
                 f"its average density would be {st['density_text'].split(': ')[-1]}."},
        {"planet": None, "name": sg["name"], "colours": BH, "head": "A giant in the middle of our galaxy",
         "text": f"{sg['name']} weighs {sg['mass_sun'] / 1e6:.3g} million Suns. Its horizon reaches {sg['horizon']} from the middle - "
                 "smaller than Mercury's orbit. Stars racing round it gave its mass (Nobel prize 2020)."},
        {"planet": None, "name": "near the horizon", "colours": BH, "head": "Clocks run slow",
         "text": f"Near a black hole time passes more slowly: {sg['dilation'][1]['text']}; at 1.01× the horizon, 1 hour = "
                 f"{sg['dilation'][3]['factor']:.0f} hours far away."},
        {"planet": None, "name": "falling in", "colours": BH, "head": "Stretched - or not",
         "text": f"The pull on your feet is stronger than on your head. At a 10-Sun hole: {st['tidal_text']}. "
                 f"At {sg['name']}: {sg['tidal_text']}."},
        {"planet": None, "name": "seeing one", "colours": BH, "head": "How we see something black",
         "text": "Gas swirling in gets hot and glows; light passing close is bent into rings (lensing). In 2022 the "
                 "Event Horizon Telescope photographed the shadow of " + sg["name"] + " - a dark middle in a bright ring."},
    ]}


def _stars():
    import math
    from . import galaxy
    lt = {m: galaxy.lifetime_gyr(m) for m in (0.1, 1, 10, 40)}
    yrs = lambda g: f"{g / 1000:.1f} trillion years" if g >= 1000 else f"{g:,.0f} billion years" if g >= 1 else f"{g * 1000:,.0f} million years" if g >= 0.001 else f"{g * 1e6:,.0f} thousand years"
    Gk = 4.30e-6                                                  # G in kpc·(km/s)²/Sun
    seen = 6e10                                                   # the Milky Way's stars + gas, in Suns (mostly inside ~10 kpc)
    kep = {r: math.sqrt(Gk * seen / r) for r in (8.2, 25)}
    flat = galaxy.rotation_kms(0.5)
    alock = 0.5 * 0.12 ** (1 / 3) * (4.85 / 4.5) ** (1 / 6)
    STAR = {"ground": "#ffd27a", "sky": "#fff6d8"}
    GAL = {"ground": "#3b2f6b", "sky": "#c9b8ff"}
    return {"id": "stars", "title": "Stars and the galaxy", "icon": "⭐", "steps": [
        {"planet": None, "name": "a big star", "colours": {"ground": "#5a8cff", "sky": "#e8f0ff"}, "head": "Why big stars die young",
         "text": f"A star's life ≈ 10 billion years × M^-2.5 (M in Suns): a bigger star burns its fuel far faster than it has more of it. "
                 f"The Sun: {yrs(lt[1])}. 10 Suns: {yrs(lt[10])}. 40 Suns: {yrs(lt[40])}. A small red dwarf (0.1): {yrs(lt[0.1])} - "
                 "longer than the universe has existed, so not one has died yet."},
        {"planet": None, "name": "starlight", "colours": STAR, "head": "How far away the stars are",
         "text": "Light travels 300 000 km every second - 9.46 million million km in a year (a light year). The Sun's light is 8.3 minutes old; "
                 "the nearest star, Proxima Centauri, is 4.24 light years away, so you see it as it was 4 years ago. "
                 "The galaxy's far side: light that left 80 000 years ago."},
        {"planet": None, "name": "the Milky Way", "colours": GAL, "head": "Why the galaxy needs dark matter",
         "text": f"Stars far out should circle slowly, like the outer planets (Kepler): from the stars and gas we can see, about "
                 f"{kep[8.2]:.0f} km/s at our distance and {kep[25]:.0f} km/s at 25 kpc. But they all go about {flat:.0f} km/s. "
                 "Something unseen adds pull - about 5× more mass than all the stars: dark matter."},
        {"planet": "moon", "head": "Tidal locking",
         "text": "A moon's pull stretches its planet a little, and the planet's pull stretches the moon much more. The rubbing slows the spin "
                 "until one side always faces - why we only ever see one face of our Moon. Planets close to small stars lock too "
                 f"(round a red dwarf like Proxima, anything inside ~{alock:.2f} AU): endless day on one side, endless night on the other."},
        {"planet": None, "name": "two suns", "colours": {"ground": "#ffb070", "sky": "#ffe2c0"}, "head": "Two suns and their shadows",
         "text": "About half of all stars have a partner. A planet can circle both when it is far out (more than ~3-4× their distance apart), "
                 "or one of them when the other is far away. With two suns everything casts two shadows - each one lit by the other sun, so "
                 "they come in two colours when the suns are different."},
        {"planet": None, "name": "a black hole", "colours": {"ground": "#000000", "sky": "#f2a250"}, "head": "How a black hole bends light",
         "text": "Mass bends space, and light follows the bend. A star exactly behind a black hole (or a galaxy) is seen as a ring - the Einstein "
                 "ring; slightly off, as two arcs. Astronomers use this lensing to weigh galaxies - and to find dark matter."},
    ]}


def _address():
    from . import milkyway
    near = sorted(((v[0], k, v) for k, v in milkyway.STARS.items()), key=lambda x: x[0])[:6]
    names = ", ".join(f"{milkyway.nice(k, True) if hasattr(milkyway, 'nice') else k.title()} ({d:g} ly)" for d, k, v in near)
    nexo = len(milkyway.PLANETS)
    GAL = {"ground": "#3b2f6b", "sky": "#c9b8ff"}
    return {"id": "address", "title": "Our address in space", "icon": "🏠", "steps": [
        {"planet": "earth", "head": "Earth",
         "text": "Our home: the third planet from the Sun, 150 million km (1 AU) out - 8.3 light-minutes."},
        {"planet": None, "name": "the Solar System", "colours": {"ground": "#ffcf6b", "sky": "#fff3c8"}, "head": "The Solar System",
         "text": "One star (the Sun), 8 planets, dwarf planets like Pluto, and the comets of the Oort cloud reaching out ~1 light year."},
        {"planet": None, "name": "the Orion Arm", "colours": GAL, "head": "The Orion Arm",
         "text": "We sit in a small spur of the Milky Way, the Orion Arm, about 26 000 light years (8.2 kpc) from the middle - "
                 "in the galaxy's safer, quieter suburbs. We circle the middle at ~220 km/s: one lap every ~230 million years."},
        {"planet": None, "name": "the Milky Way", "colours": GAL, "head": "The Milky Way",
         "text": "A barred spiral galaxy ~100 000 light years wide with 100-400 billion stars, and Sagittarius A* in the middle. "
                 "It is part of the Local Group (with Andromeda) inside the Laniakea supercluster."},
        {"planet": None, "name": "our neighbours", "colours": {"ground": "#ff8a5c", "sky": "#ffd8c2"}, "head": "The nearest stars",
         "text": "The closest: " + names + ". Most nearby stars are small red dwarfs - too dim to see without a telescope."},
        {"planet": None, "name": "51 Pegasi b", "colours": {"ground": "#c9873a", "sky": "#f3d29a"}, "head": "The first exoplanets",
         "text": "1992: planets round a dead star (the pulsar PSR B1257+12). 1995: 51 Pegasi b, a 'hot Jupiter' round a Sun-like star "
                 "(Nobel prize 2019). Today more than 5 000 are known; " + str(nexo) + " of the nearby ones are on our Milky Way map."},
        {"planet": None, "name": "finding planets", "colours": {"ground": "#ffd27a", "sky": "#fff6d8"}, "head": "How we find them",
         "text": "The wobble: a planet tugs its star to and fro, shifting its light's colour a tiny bit (Doppler). The dip: when a planet "
                 "passes in front, its star dims by (planet size / star size)² - Earth dims the Sun by just 0.008 %. Kepler and TESS "
                 "found thousands this way."},
    ]}


BUILD = [_venus, _oxygen, _titan, _mars, _jupiter, _protect, _blackhole, _stars, _address]


@lru_cache(maxsize=1)
def all_lessons():
    from . import galaxy
    out = []
    for f in BUILD:
        L = f()
        for s in L["steps"]:
            if not s.get("planet"):
                continue
            p = galaxy.solar(s["planet"])
            s["name"] = p.get("name", s["planet"].title())
            s["colours"] = p.get("colours") or {}
        out.append(L)
    return out
