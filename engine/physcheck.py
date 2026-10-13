"""Auto-check for physics lessons: an education video must never be wrong.

Before rendering, every narration line / dialogue near an experiment is read for numbers and claims ("lands in 2
seconds", "goes 10 m", "T = 2 s", "the stone falls faster than the feather", "balanced") and compared with what
the experiment really does - its own formulas, the same numbers the on-screen panel shows:

    ✓ "lands in 2.0 s" - correct (2.02 s)
    ✗ "says 3 s" - it really takes 2.02 s  -> fix: change the number in the line, or the experiment
    ⚠ "says the feather lands later" - on the Moon (no air) they land together

Also: units and common mistakes (km/h vs m/s, cm vs m, mass vs weight, g of the wrong planet).

    check(P)            -> [item]  (dicts: level ok | bad | warn, scene, at, who, line, said, real, msg, fix)
    report(items)       -> text for the console / validate
    problems(items)     -> short strings for the AI repair loop (only bad / warn)
"""
import math
import re

# unit words -> (dimension, factor to the base unit)
UNITS = [
    (r"m\s*/\s*s\s*(?:²|2|\^2)|metres? per second squared|meters? per second squared", "accel", 1.0),
    (r"km\s*/\s*h|kmph|km per hour|kilometres? per hour|kilometers? per hour|किलोमीटर प्रति घंटा", "speed", 1 / 3.6),
    (r"m\s*/\s*s|metres? per second|meters? per second|मीटर प्रति सेकंड", "speed", 1.0),
    (r"kg\s*·?\s*m\s*/\s*s", "momentum", 1.0),
    (r"cm|centimetres?|centimeters?|सेंटीमीटर|सेमी", "length", 0.01),
    (r"km|kilometres?|kilometers?|किलोमीटर", "length", 1000.0),
    (r"m|metres?|meters?|मीटर", "length", 1.0),
    (r"ms|milliseconds?", "time", 0.001),
    (r"s|secs?|seconds?|सेकंड|सेकेंड|सेकण्ड", "time", 1.0),
    (r"minutes?|mins?|मिनट", "time", 60.0),
    (r"kg|kilograms?|kilos?|किलो(?:ग्राम)?", "mass", 1.0),
    (r"g|grams?|ग्राम", "mass", 0.001),
    (r"N|newtons?|न्यूटन", "force", 1.0),
    (r"Hz|hertz|हर्ट्ज़", "freq", 1.0),
    (r"°|degrees?|डिग्री", "angle", 1.0),
    (r"J|joules?|जूल", "energy", 1.0),
    (r"kWh|kilowatt[- ]hours?|units? of electricity", "kwh", 1.0),
    (r"kW|kilowatts?|किलोवाट", "power", 1000.0),
    (r"W|watts?|वाट", "power", 1.0),
    (r"mA|milliamps?|milliamperes?", "current", 0.001),
    (r"A|amps?|amperes?|एम्पियर", "current", 1.0),
    (r"kV|kilovolts?", "voltage", 1000.0),
    (r"V|volts?|वोल्ट", "voltage", 1.0),
    (r"Ω|ohms?|ओम", "resistance", 1.0),
    (r"%|per ?cent|प्रतिशत", "percent", 1.0),
]
_NUM = r"(\d+(?:[.,]\d+)?)"
CASE = ("N|", "J|", "g|", "W|", "A|", "V|", "kW|", "kV|", "mA|", "kWh|", "ms|")    # a capital letter means it


def _flags(u):
    return 0 if u.startswith(CASE) else re.I


_UNIT_RE = [(re.compile(_NUM + r"\s*(" + u + r")(?![A-Za-zऀ-ॿ/²])", _flags(u)), dim, f)
            for u, dim, f in UNITS]
DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
WORD_NUMS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "half a": 0.5, "half": 0.5}
NAMES = {"time": "time", "length": "distance", "speed": "speed", "accel": "acceleration", "mass": "mass",
         "force": "force", "freq": "frequency", "angle": "angle", "energy": "energy", "momentum": "momentum",
         "percent": "percent", "power": "power", "current": "current", "voltage": "voltage",
         "resistance": "resistance", "kwh": "energy (kWh)"}
BASE = {"time": "s", "length": "m", "speed": "m/s", "accel": "m/s²", "mass": "kg", "force": "N", "freq": "Hz",
        "angle": "°", "energy": "J", "momentum": "kg·m/s", "percent": "%", "power": "W", "current": "A",
        "voltage": "V", "resistance": "Ω", "kwh": "kWh"}
# spec keys that are inputs with a unit (the experiment's own settings - a line may repeat them)
SPEC_UNITS = {"height": "length", "from": "length", "h": "length", "length": "length", "lengths": "length",
              "radius": "length", "distance": "length", "speed": "speed", "v": "speed", "angle": "angle",
              "mass": "mass", "masses": "mass", "load": "mass", "frequency": "freq", "f": "freq", "duration": None}
PLANET_G = {"earth": 9.81, "moon": 1.62, "mars": 3.71, "jupiter": 24.79}


def _f(s):
    return float(str(s).replace(",", "."))


def quantities(text):
    """[(value in base units, dimension, raw number, raw unit, span)] found in a line."""
    t = str(text or "").translate(DEVANAGARI)
    for w, n in WORD_NUMS.items():                     # "two seconds" -> "2 seconds"
        t = re.sub(r"\b" + w + r"\b(?=\s+(?:sec|second|metre|meter|m\b|kg|minute))", str(n), t, flags=re.I)
    out, used = [], []
    for rx, dim, f in _UNIT_RE:
        for m in rx.finditer(t):
            a, b = m.span()
            if any(a < u1 and b > u0 for u0, u1 in used):
                continue
            used.append((a, b))
            out.append((_f(m.group(1)) * f, dim, m.group(1), m.group(2), (a, b)))
    return sorted(out, key=lambda q: q[4][0])


# ============================================================================ what the experiments really do
class Fact:
    def __init__(self, name, value, dim, eid):
        self.name, self.value, self.dim, self.eid = name, float(value), dim, eid

    def __repr__(self):
        return f"{self.name}={self.value:g}{BASE.get(self.dim, '')}"


def _stable_values(ex):
    """Panel readouts that stay the same while it runs (results and settings, not the moving numbers)."""
    L = ex.length()
    try:
        a = ex.values(L * 0.15)
        b = ex.values(L)
    except Exception:                                   # noqa: BLE001
        return []
    da = {k: v for k, v in a}
    return [(k, v) for k, v in b if da.get(k) == v]


def _stable_quantities(ex):
    """[(label, value, dim)]: the numbers on the panel that hold still for a while (results, settings, each stage
    of a staged experiment - "T = 2.02 s" from "T = 2.02 s, angle -16°") and the final readings at the end; a
    number that keeps changing (the angle of a swing) is not a fact a line can quote."""
    L = ex.length()
    n = 14
    samples = []
    for i in range(n + 1):
        try:
            vals = ex.values(L * i / n)
        except Exception:                               # noqa: BLE001
            vals = []
        q = {}
        for k, v in vals:
            for val, dim, _r, _u, _s in quantities(f"{k} {v}"):
                q.setdefault(k, set()).add((dim, round(val, 6)))
        samples.append(q)
    out, seen = [], set()
    for i in range(n + 1):
        for k, qs in samples[i].items():
            for dim, val in qs:
                held = (i > 0 and (dim, val) in samples[i - 1].get(k, ())) or i == n
                if held and (k, dim, val) not in seen:
                    seen.add((k, dim, val))
                    out.append((k, val, dim))
    return out


def facts_of(spec):
    """Facts (true numbers) of one experiment spec."""
    from . import physics
    try:
        ex = physics.get(dict(spec))
    except Exception:                                   # noqa: BLE001
        return [], None
    eid = spec.get("id") or spec.get("experiment")
    out = []
    for label, v, dim in _stable_quantities(ex):
        out.append(Fact(label or "result", v, dim, eid))
    for label, text in (ex.facts() if hasattr(ex, "facts") else []):     # key results an experiment names itself
        for v, dim, _r, _u, _s in quantities(f"{text}"):
            out.append(Fact(label, v, dim, eid))
    kind = getattr(ex, "name", spec.get("experiment"))
    if hasattr(ex, "land_time") and hasattr(ex, "objs"):                       # free fall
        for o in ex.objs:
            out.append(Fact(f"{o} lands after", ex.land_time(o), "time", eid))
        out.append(Fact("dropped from", ex.h, "length", eid))
        out.append(Fact("g", ex.g, "accel", eid))
        if not getattr(ex, "air", False):
            out.append(Fact("speed at the ground", math.sqrt(2 * ex.g * ex.h), "speed", eid))
    if kind in ("projectile", "catapult") and hasattr(ex, "T"):
        out += [Fact("time in the air", ex.T, "time", eid), Fact("lands at (range)", ex.R, "length", eid),
                Fact("highest point", ex.H, "length", eid), Fact("time to the top", ex.t_top, "time", eid),
                Fact("throw speed", ex.v, "speed", eid), Fact("angle", math.degrees(ex.a), "angle", eid)]
    out.append(Fact("g", getattr(ex, "g", 9.81), "accel", eid))
    for k, dim in SPEC_UNITS.items():                   # the settings themselves
        if dim and spec.get(k) is not None:
            vals = spec[k] if isinstance(spec[k], (list, tuple)) else str(spec[k]).split(",")
            for v in vals:
                try:
                    out.append(Fact(k, float(v), dim, eid))
                except (TypeError, ValueError):
                    pass
    return out, ex


# ============================================================================ the check
_LATER = r"(later|slower|slowly|after|takes longer|behind|बाद में|धीरे)"
_EARLIER = r"(first|faster|quicker|before|पहले|तेज़)"
_TOGETHER = r"(together|same time|same moment|at once|साथ|एक साथ|एक ही समय)"
_LIGHT_OBJ = ("feather", "paper", "leaf", "पंख", "कागज़", "पत्ता")


def _qualitative(line, ex, spec):
    """Claims without numbers: who lands first, together or not, balanced, floats / sinks."""
    low = str(line).lower()
    out = []
    if hasattr(ex, "land_time") and hasattr(ex, "objs") and len(ex.objs) >= 2:
        times = {o: ex.land_time(o) for o in ex.objs}
        together = max(times.values()) - min(times.values()) < 0.05
        mentions = [o for o in ex.objs if o in low] or (["feather"] if any(w in low for w in _LIGHT_OBJ) else [])
        planet = str(spec.get("planet", "earth")).lower()
        where = "on the Moon (no air)" if planet == "moon" else ("with no air" if not getattr(ex, "air", True)
                                                                 else "")
        if together and mentions and (re.search(_LATER, low) or re.search(_EARLIER, low)) and \
                not re.search(_TOGETHER, low):
            out.append(("warn", f"says one lands {('later' if re.search(_LATER, low) else 'first')} - "
                                f"{where or 'here'} they land together ({min(times.values()):.2f} s)",
                        None))
        if not together and re.search(_TOGETHER, low) and not re.search(r"\b(not|n't|नहीं)\b", low):
            slow = max(times, key=times.get)
            fast = min(times, key=times.get)
            out.append(("warn", f"says they land together - with air the {slow} lands later "
                                f"({times[slow]:.2f} s vs {times[fast]:.2f} s for the {fast})", None))
    vals = " ".join(f"{k} {v}" for k, v in _stable_values(ex)).lower() if ex is not None else ""
    if "balanced" in vals and re.search(r"\b(tips|goes down|falls to|not balanced|heavier side)\b", low):
        out.append(("warn", "says it tips - with these weights and distances it is balanced (m₁·d₁ = m₂·d₂)", None))
    if vals and "balanced" not in vals and "lever" in str(spec.get("experiment", "")) and \
            re.search(r"\bbalanced\b|बराबर", low) and not re.search(r"\b(not|n't)\b", low):
        out.append(("warn", "says it is balanced - the two sides are not equal (m₁·d₁ ≠ m₂·d₂)", None))
    for k, v in (_stable_values(ex) if ex is not None else []):
        kl = str(k).lower()
        vl = str(v).lower()
        if not kl or kl not in low:
            continue
        if "floats" in vl and re.search(r"\bsinks?\b|डूब", low) and not re.search(r"\bfloats?\b", low):
            out.append(("warn", f"says the {kl} sinks - it floats ({v})", None))
        if "sinks" in vl and re.search(r"\bfloats?\b|तैर", low) and not re.search(r"\bsinks?\b", low):
            out.append(("warn", f"says the {kl} floats - it sinks ({v})", None))
    return out


def _fmt(v, dim, like=None):
    """Format the true value like the number in the line (same number of decimals, at least what is needed)."""
    dec = len(like.split(".")[-1].split(",")[-1]) if like and ("." in like or "," in like) else 0
    if abs(v) < 10 and dec == 0:
        dec = 1 if abs(v - round(v)) > 0.05 else 0
    return f"{v:.{dec}f}"


def _close(said, real, dim, rough=False):
    """Said = real within rounding (a line says 2 s for 2.02 s; "about" / "nearly" allows more)."""
    tol = {"time": 0.035, "length": 0.035, "speed": 0.04, "accel": 0.03, "angle": 0.03}.get(dim, 0.05)
    ab = {"time": 0.05, "length": 0.05, "speed": 0.1, "angle": 1.0}.get(dim, 0.05)
    if rough:
        tol *= 3
    return abs(said - real) <= max(ab, tol * abs(real), 0.5 * 10 ** -_decimals_of(said))


def _decimals_of(v):
    t = f"{v:.6f}".rstrip("0")
    return len(t.split(".")[1]) if "." in t else 0


ROUGH = r"(about|around|nearly|almost|roughly|approx|लगभग|करीब|क़रीब)"


def check_line(line, exps):
    """[(level, msg, fix_line)] for one line against the experiments [(spec, facts, ex)]."""
    out = []
    qs = quantities(line)
    facts = [f for _s, fs, _e in exps for f in fs]
    g_real = {round(f.value, 2) for f in facts if f.name == "g"}
    for v, dim, raw, unit, span in qs:
        same = [f for f in facts if f.dim == dim]
        if dim == "speed" and "km" in unit.lower():       # km/h said where the panel shows m/s
            raw_v = _f(raw)
            twin = [f for f in facts if f.dim == "speed" and _close(raw_v, f.value, "speed")]
            if twin and not any(_close(v, f.value, "speed") for f in same):
                out.append(("bad", f'says {raw} {unit} - that is the speed in m/s ({twin[0].value:.2f} m/s = '
                                   f'{twin[0].value * 3.6:.1f} km/h)', line[:span[0]] + f"{raw} m/s" + line[span[1]:]))
                continue
        if dim == "length" and unit.lower() in ("cm", "centimetre", "centimeter", "centimetres", "centimeters"):
            twin = [f for f in facts if f.dim == "length" and _close(_f(raw), f.value, "length")]
            if twin and not any(_close(v, f.value, "length") for f in same):
                out.append(("bad", f"says {raw} cm - it is {twin[0].value:g} m", line[:span[0]] + f"{raw} m" +
                            line[span[1]:]))
                continue
        if dim == "mass" and re.search(r"weigh", line[max(0, span[0] - 25):span[0]], re.I):
            gg = max(g_real) if g_real else 9.81
            out.append(("warn", f"'weighs {raw} {unit}' - in physics weight is a force: {v:g} kg has a weight of "
                                f"{v * gg:.0f} N (mass stays {v:g} kg)", None))
        if not same:
            continue
        if dim == "accel" and g_real and abs(v - 9.8) < 0.2 and not any(abs(x - 9.81) < 0.2 for x in g_real):
            gx = sorted(g_real)[0]
            out.append(("bad", f"says g = {raw} - here g is {gx} m/s² (another planet)",
                        line[:span[0]] + _fmt(gx, dim, raw) + " " + unit + line[span[1]:]))
            continue
        best = min(same, key=lambda f: abs(f.value - v) / max(abs(f.value), 1e-6))
        rough = bool(re.search(ROUGH, line[max(0, span[0] - 18):span[0]], re.I))
        if _close(v, best.value, dim, rough):
            out.append(("ok", f'"{raw} {unit}" - correct ({best.value:.2f} {BASE[dim]}, {best.name})', None))
        else:
            fixed = line[:span[0]] + _fmt(best.value / ([f for _u, d, f in UNITS if d == dim and
                                                           re.fullmatch(_u, unit, re.I)] or [1.0])[0], dim, raw) + \
                " " + unit + line[span[1]:]
            out.append(("bad", f'says {raw} {unit} - it really is {best.value:.2f} {BASE[dim]} ({best.name})', fixed))
    for spec, _fs, ex in exps:
        for lvl, msg, fix in _qualitative(line, ex, spec):
            out.append((lvl, msg, fix))
    return out


def check(P):
    """Check every line said near an experiment, in every scene of a Project."""
    items = []
    for it in P.items:
        if it.kind != "scene":
            continue
        sc = it.scene
        exps = []
        for pr in sc.props.values():
            if getattr(pr, "type", "") != "experiment":
                continue
            spec = dict(pr.spec)
            fs, ex = facts_of(spec)
            if ex is None:
                continue
            st = float(spec.get("_start", 0.0))
            try:
                ln = ex.length() / float(spec.get("slowmo", 1.0) or 1.0)
            except Exception:                           # noqa: BLE001
                ln = 8.0
            end = float(spec.get("_end", st + ln))
            exps.append((spec, fs, ex, st, end))
        if not exps:
            continue
        for sp in sc.speeches:
            text = str(getattr(sp, "text", "") or "")
            if not text.strip():
                continue
            win = [(a, s, f, e) for s, f, e, a, b in exps if a - 1.0 <= sp.start <= b + 10.0]
            if win:                                      # the experiment just shown (the latest one started)
                last = max(a for a, _s, _f, _e in win if a <= sp.start + 1.0) if any(
                    a <= sp.start + 1.0 for a, _s, _f, _e in win) else min(a for a, _s, _f, _e in win)
                near = [(s, f, e) for a, s, f, e in win if abs(a - last) < 1e-6]
            else:                                        # a recap line: the experiments of this scene
                near = []
            if not near:
                near = [(s, f, e) for s, f, e, a, b in exps]
            for lvl, msg, fix in check_line(text, near):
                items.append(dict(level=lvl, scene=sc.index + 1, at=round(it.start + sp.start, 1), who=sp.who,
                                  line=text, msg=msg, fix=fix,
                                  experiment=", ".join(str(s.get("id") or s.get("experiment")) for s, _f, _e in near)))
    return items


def report(items):
    if not items:
        return ""
    sym = {"ok": "✓", "bad": "✗", "warn": "⚠"}
    bad = sum(1 for i in items if i["level"] != "ok")
    lines = [f"Physics check: {len(items)} number(s) / claim(s) in the lines, "
             + ("all correct ✔" if not bad else f"{bad} to fix:")]
    for i in items:
        lines.append(f"  {sym[i['level']]} scene {i['scene']} {i['at']:.1f}s {i['who']}: {i['msg']}")
        if i["level"] != "ok":
            lines.append(f'      line: "{i["line"]}"')
            if i.get("fix"):
                lines.append(f'      fix : "{i["fix"]}"   (or change the experiment {i["experiment"]} to match)')
    return "\n".join(lines)


def problems(items):
    """For the AI repair loop: what to change, in plain words."""
    out = []
    for i in items:
        if i["level"] == "ok":
            continue
        s = f'physics check (scene {i["scene"]}, {i["who"]}): "{i["line"]}" {i["msg"]}'
        if i.get("fix"):
            s += f' - write instead: "{i["fix"]}"'
        out.append(s)
    return out
