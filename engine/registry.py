"""Asset registry: everything you add in assets/ (or from the Studio) is loaded here.

assets/characters/<id>.json   one character (person or animal) - reusable in any story by id
assets/species/<name>.json    a new animal built from an existing body, e.g. zebra = horse + stripes
assets/places/<name>.json     a saved background (preset + style knobs + elements), usable as a preset name
assets/sfx/, assets/music/    your own sounds
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets")
KINDS = ("characters", "species", "places")

_CACHE = {"stamp": None, "data": None}


def _stamp():
    s = []
    for k in KINDS:
        d = os.path.join(ASSETS, k)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                s.append((f, os.path.getmtime(p)))
    return tuple(s)


_CODE_SP = {"stamp": None}


def code_species():
    """A 3D animal code file whose FOR is a new animal (FOR = "dinosaur") makes that species real:
    stories can use "species": "dinosaur" and it gets every animal action.  Its SPECIES = {...} says
    base body ("tiger", "horse", "dog", "parrot" ...), size, walk / run speed, sound, colours, other names
    ("aliases") and which action to use for a word ("actions": {"attack": "pounce"})."""
    from . import animals, codedraw
    d = codedraw.DIR
    try:
        st = tuple(sorted((f, os.path.getmtime(os.path.join(d, f))) for f in os.listdir(d) if f.endswith(".py")))
    except OSError:
        return
    if st == _CODE_SP["stamp"]:
        return
    _CODE_SP["stamp"] = st
    codes = codedraw.list_code()
    alive = {m.get("for") for m in codes.values() if m.get("kind") == "animal3d"}
    for sp in [k for k in animals.FROM_CODE if k not in alive]:        # its file was deleted: forget the animal
        animals.FROM_CODE.pop(sp, None)
        animals.CUSTOM.pop(sp, None)
        animals.QUADS.pop(sp, None)
        animals.BIRDS.pop(sp, None)
        for a in [a for a, v in animals.ALIASES.items() if v == sp]:
            animals.ALIASES.pop(a, None)
    for name, m in codes.items():
        sp = m.get("for") or ""
        if m.get("kind") != "animal3d" or not sp or sp in ("quadruped", "bird", "human", "animal"):
            continue
        if sp in animals.BUILTIN or (sp in animals.CUSTOM and sp not in animals.FROM_CODE):
            continue                                   # a known animal: the file only changes its look
        install_code_species(sp, m.get("species"), m.get("description"), name)


def install_code_species(sp, S, description=None, file_name=None):
    """Make species sp from a SPECIES = {...} block (base, size, aliases, kind, + any body setting)."""
    from . import animals
    S = dict(S or {})
    kind = str(S.pop("kind", "")).lower()
    base = str(S.pop("base", "") or ("parrot" if kind == "bird" else "tiger")).lower()
    size = S.pop("size", None)
    aliases = S.pop("aliases", []) or []
    spec = dict(S)
    spec["base"] = base
    spec["description"] = description or f"{sp.replace('_', ' ')} (3D animal)"
    cb = animals.canon(base)
    tbl = animals.QUADS if cb in animals.QUADS else animals.BIRDS
    if size is not None and cb in tbl:
        try:
            spec["scale"] = float(tbl[cb].get("scale", 1.0)) * float(size)
        except (TypeError, ValueError):
            pass
    _install_species({sp: spec})
    animals.FROM_CODE[sp] = file_name or sp
    for a in aliases if isinstance(aliases, (list, tuple)) else [aliases]:
        a = str(a).lower().strip().replace(" ", "_")
        if a and a not in animals.BUILTIN:
            animals.ALIASES[a] = sp


def load(force=False):
    """{kind: {name: spec}} for all custom assets (cached until files change)."""
    try:
        code_species()
    except Exception as ex:                                # never stop a render for this
        print("3D animal species:", ex)
    st = _stamp()
    if not force and _CACHE["stamp"] == st and _CACHE["data"] is not None:
        return _CACHE["data"]
    data = {k: {} for k in KINDS}
    for k in KINDS:
        d = os.path.join(ASSETS, k)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    spec = json.load(fh)
            except (OSError, ValueError):
                continue
            name = os.path.splitext(f)[0].lower()
            if isinstance(spec, dict) and k == "characters" and "characters" in spec:
                data[k].update({kk.lower(): vv for kk, vv in spec["characters"].items()})
            elif isinstance(spec, dict):
                data[k][name] = spec
    _CACHE.update(stamp=st, data=data)
    _install_species(data["species"])
    return data


def save(kind, name, spec):
    if kind not in KINDS:
        raise ValueError(kind)
    name = "".join(c if c.isalnum() or c in "_-" else "_" for c in str(name).lower().strip())[:40]
    if not name:
        raise ValueError("name required")
    d = os.path.join(ASSETS, kind)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    load(force=True)
    return name


def delete(kind, name):
    p = os.path.join(ASSETS, kind, str(name).lower() + ".json")
    if os.path.exists(p):
        os.remove(p)
    load(force=True)


def character(cid):
    return load()["characters"].get(str(cid).lower())


def place(name):
    return load()["places"].get(str(name).lower())


def install_temp(name, spec):
    """Install a species definition in memory only (Studio preview)."""
    _install_species({name: spec})


def species_base(name):
    """Plain (JSON-safe) parameters of an existing species, for the Studio sliders."""
    from . import animals
    from .util import hex_to_rgb  # noqa
    s = animals.canon(name)
    d = animals.QUADS.get(s) or animals.BIRDS.get(s) or {}
    out = {}
    for k, v in d.items():
        if isinstance(v, tuple) and len(v) == 3 and all(isinstance(x, float) for x in v):
            v = "#%02x%02x%02x" % tuple(int(x * 255) for x in v)
        elif isinstance(v, tuple):
            v = list(v)
        out[k] = v
    out["kind"] = "bird" if s in animals.BIRDS else "quadruped"
    return out


def _install_species(species):
    """Custom animals: copy a base body and override its parameters."""
    from . import animals
    for name, spec in species.items():
        base = animals.canon(spec.get("base", "dog"))
        table = animals.QUADS if base in animals.QUADS else (animals.BIRDS if base in animals.BIRDS else None)
        if table is None:
            continue
        new = dict(table[base])
        for k, v in spec.items():
            if k in ("base", "name", "description"):
                continue
            if k == "snout" and isinstance(v, (list, tuple)):
                v = tuple(v)
            if k == "beak" and isinstance(v, (list, tuple)):
                v = tuple(v)
            new[k] = v
        table[name] = new
        animals.CUSTOM[name] = spec.get("description", f"custom animal based on {base}")
