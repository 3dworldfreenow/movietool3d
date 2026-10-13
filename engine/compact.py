"""🕳 Black holes and neutron stars - the real numbers (general relativity at school level):

    black_hole(M)    event horizon r_s = 2GM/c² (≈ 2.95 km per Sun), the photon sphere 1.5 r_s (light can circle),
                     the last stable orbit 3 r_s, the shadow seen from far ≈ 2.6 r_s across each side (√27/2),
                     time dilation for someone hovering at r: 1/√(1 - r_s/r) ("1 hour there = N hours far away"),
                     the tidal stretch on a 1.8 m person at the horizon: Δa = 2GM·L/r³ (deadly near small ones,
                     hardly felt at a giant's - a surprising, true fact)
    neutron_star(M)  ~12 km across, heavier than the Sun: density, a teaspoon's weight, surface gravity, escape speed,
                     a pulsar's spin
    centre(seed)     every big galaxy has a supermassive black hole in its middle (mass grows with the bulge;
                     Milky Way: Sagittarius A* = 4.15 million Suns)
"""
import math

from .util import clamp, stable_hash

G, C, MSUN = 6.674e-11, 2.998e8, 1.989e30
SGR_A = 4.15e6


def _num(x):
    """a readable number"""
    for v, w in ((1e15, "million billion"), (1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
        if x >= v:
            return f"{x / v:.3g} {w}"
    return f"{x:,.3g}" if x < 1000 else f"{x:,.0f}"


def _km(m):
    if m >= 1.496e11 * 0.05:
        return f"{m / 1.496e11:.3g} AU ({_num(m / 1000)} km)"
    return f"{_num(m / 1000)} km"


def black_hole(M_sun):
    M = float(M_sun) * MSUN
    rs = 2 * G * M / C ** 2
    dil = []
    for k in (10.0, 2.0, 1.1, 1.01):
        f = 1 / math.sqrt(1 - 1 / k)
        dil.append({"at": f"{k:g} r_s", "factor": round(f, 3), "text": f"1 hour hovering at {k:g}× the horizon = {f:.3g} hours far away"})
    tidal = 2 * G * M * 1.8 / rs ** 3                                      # m/s² between head and feet at the horizon
    feel = ("you are torn apart long before the horizon (spaghettified)" if tidal > 1e3 else
            "a strong but survivable stretch" if tidal > 20 else "you would hardly feel it - you cross the horizon without noticing")
    return {"kind": "black hole", "mass_sun": M_sun, "r_s_m": rs, "horizon": _km(rs), "photon_sphere": _km(1.5 * rs),
            "last_orbit": _km(3 * rs), "shadow": _km(2 * 2.598 * rs) + " across", "dilation": dil,
            "tidal_ms2": tidal, "tidal_g": tidal / 9.81, "tidal_text": f"head-to-foot pull at the horizon: {_num(tidal / 9.81)} g - {feel}",
            "density_text": f"its average density inside the horizon: {_num(M / (4 / 3 * math.pi * rs ** 3))} kg/m³"
                            + (" - less than water!" if M / (4 / 3 * math.pi * rs ** 3) < 1000 else ""),
            "why": ["more than ~20 Suns at birth: the core collapsed and nothing - not even light - can climb out from inside r = 2GM/c²",
                    "light passing close is bent (gravitational lensing): stars behind it smear into rings",
                    "gas falling in forms a hot glowing disk; the side moving toward you is brighter (Doppler beaming)"]}


def neutron_star(M_sun=1.4, R_km=12.0, period_s=None):
    M, R = float(M_sun) * MSUN, R_km * 1000.0
    rho = M / (4 / 3 * math.pi * R ** 3)
    g = G * M / R ** 2
    v = math.sqrt(2 * G * M / R)
    out = {"kind": "neutron star", "mass_sun": M_sun, "radius_km": R_km, "density": rho,
           "teaspoon_t": rho * 5e-6 / 1000, "g": g, "escape_c": v / C,
           "lines": [f"{2 * R_km:g} km across - a city - but {M_sun:g}× the Sun's mass",
                     f"a teaspoon of it weighs {_num(rho * 5e-6 / 1000)} tonnes (like a mountain)",
                     f"gravity at its surface: {_num(g / 9.81)} g; escape speed {v / C * 100:.0f} % of light's"],
           "why": ["8-20 Suns at birth: a supernova crushed the core until electrons and protons became neutrons"]}
    if period_s:
        out["period_s"] = period_s
        out["lines"].append(f"a pulsar: it turns {1 / period_s:,.3g} times a second, sweeping two beams of radiation like a lighthouse")
    return out


def pulsar_period(seed_key):
    """a pulsar's spin (s): young ones 0.03-1 s, recycled 'millisecond pulsars' 1.5-10 ms"""
    h = (stable_hash("psr|" + str(seed_key)) % 10000) / 10000.0
    return round(0.0015 + 0.008 * h, 4) if h < 0.15 else round(0.03 + 1.2 * h * h, 3)


def centre(galaxy_seed, kind="spiral", milky_way=False):
    """the supermassive black hole in the middle (mass grows with the bulge: ellipticals hold the giants)"""
    if milky_way:
        M = SGR_A
    else:
        h = (stable_hash(f"smbh|{galaxy_seed}") % 10000) / 10000.0
        lo, hi = {"elliptical": (8.0, 10.0), "irregular": (4.5, 6.0)}.get(kind, (6.0, 8.0))
        M = 10 ** (lo + (hi - lo) * h)
    out = black_hole(M)
    out.update(name="Sagittarius A*" if milky_way else "the central black hole", supermassive=True,
               why=["every big galaxy has a supermassive black hole in its middle; its mass grows with the galaxy's bulge "
                    "(ellipticals hold the biggest: billions of Suns)"] + out["why"][1:])
    return out


def for_star(s):
    """the card numbers for a dead star's remnant (or None)"""
    st = s.get("stage")
    if st == "black hole":
        return black_hole(s.get("mass") or 10)
    if st in ("neutron star", "pulsar"):                       # every neutron star spins; we see pulses only if a beam sweeps over us
        key = f"{s.get('galaxy')}|{s.get('index')}"
        out = neutron_star(1.4, 12.0, pulsar_period(key))
        if st != "pulsar" and stable_hash("beam|" + key) % 100 >= 25:
            out["lines"][-1] = f"it turns {1 / out['period_s']:,.3g} times a second; its two beams miss us, so from here it does not pulse"
            out["beams_miss"] = True
        return out
    return None
