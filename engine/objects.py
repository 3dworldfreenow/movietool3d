"""Interactive objects: things in the scene that characters can push, roll, carry, throw, sit on, stand on,
climb, hide behind, open or break - and that splash, float or sink in water.

An object is any prop (scene "objects" or "props" list) whose type is a built-in object below, or a picture
from the Studio that has "abilities" (set when uploading, or in the scene with "abilities": [...]).

Abilities (traits):
    movable  can be pushed / pulled          light   one person can carry / throw it
    heavy    needs a big effort or helpers   round   rolls when pushed (turns while it moves)
    throw    can be thrown                   sit     characters can sit on it
    stand    characters can stand on it      climb   characters can climb it (tree, ladder)
    hide     characters can hide behind it   open    has a lid / door (chest, box)
    break    breaks into pieces (pot)        floats  floats in water (log, ball)
    sinks    sinks in water (stone)
"""
import math
import random

from .util import hex_to_rgb, darker, lighter, clamp, smoothstep, TAU

ABILITIES = ("movable", "light", "heavy", "round", "throw", "sit", "stand", "climb", "hide", "open", "break",
             "floats", "sinks", "switch")
# picture STATES (from an object sheet): the object's picture is swapped when its state changes
#   open    -> after "open"            broken -> after "break" (stays, instead of flying shards)
#   on      -> after "turn_on"/"light" (off again with "turn_off")
#   any other name -> {"who": "ravi", "do": "use", "object": "tree", "state": "fruit"}
STATE_ABILITY = {"open": "open", "broken": "break", "on": "switch"}

# type -> width, height (story units, adult = 300 tall), colour, traits
BUILTIN = {
    "stone": dict(w=40, h=30, color="#8e8e8e", traits=("movable", "light", "round", "throw", "sinks")),
    "rock": dict(w=200, h=130, color="#8a8a86", traits=("movable", "heavy", "sit", "stand", "hide", "sinks")),
    "boulder": dict(w=250, h=230, color="#7d7a74", traits=("movable", "heavy", "round", "hide", "stand", "sinks")),
    "log": dict(w=300, h=70, color="#8b5a2b", traits=("movable", "heavy", "sit", "stand", "floats")),
    "chest": dict(w=130, h=95, color="#8b5a2b", traits=("movable", "open", "sit", "stand", "sinks")),
    "crate": dict(w=95, h=85, color="#c8905b", traits=("movable", "stand", "sit", "break", "floats")),
    "barrel": dict(w=75, h=95, color="#9c6a3c", traits=("movable", "sit", "stand", "floats")),
    "pot": dict(w=62, h=62, color="#c1440e", traits=("movable", "light", "throw", "break", "sinks")),
    "bush": dict(w=220, h=150, color="#3f8f3a", traits=("hide",)),
    "haystack": dict(w=200, h=165, color="#e0b54a", traits=("hide", "climb")),
    "ball": dict(w=30, h=30, color="#e63946", traits=("movable", "light", "round", "throw", "floats")),
    "box": dict(w=70, h=60, color="#c8905b", traits=("movable", "light", "open", "throw", "floats")),
    "gift": dict(w=60, h=60, color="#8338ec", traits=("movable", "light", "open")),
    "apple": dict(w=20, h=22, color="#d62828", traits=("movable", "light", "throw", "floats")),
    "bag": dict(w=45, h=50, color="#6a4c93", traits=("movable", "light", "throw", "floats")),
    "book": dict(w=30, h=36, color="#1d4e89", traits=("movable", "light", "throw")),
    "stick": dict(w=12, h=90, color="#8b5a2b", traits=("movable", "light", "throw", "floats")),
    "sack": dict(w=80, h=95, color="#c9b48a", traits=("movable", "heavy", "sit")),           # grain: thuds, stays
    "leaf": dict(w=26, h=16, color="#5a9a3a", traits=("movable", "light", "floats")),        # floats down
    "experiment": dict(w=400, h=300, color="#888888", traits=()),      # a physics experiment (engine/physics.py)
}
ALIASES = {"pebble": "stone", "small_stone": "stone", "stones": "stone", "big_rock": "boulder",
           "large_rock": "boulder", "boulders": "boulder", "rocks": "rock", "tree_trunk": "log", "trunk": "log",
           "wood_log": "log", "logs": "log", "treasure": "chest", "treasure_chest": "chest", "trunk_box": "chest",
           "wooden_box": "crate", "matka": "pot", "clay_pot": "pot", "vase": "pot", "jar": "pot", "shrub": "bush",
           "hay": "haystack", "drum": "barrel",
           "bori": "sack", "grain_sack": "sack", "rice_bag": "sack", "gunny_bag": "sack", "leaves": "leaf",
           "patta": "leaf", "dry_leaf": "leaf"}
DRAWN_HERE = ("stone", "rock", "boulder", "log", "chest", "crate", "barrel", "pot", "bush", "haystack", "sack", "leaf")


def base_type(ptype):
    k = str(ptype or "").lower().strip().replace(" ", "_").replace("-", "_")
    return ALIASES.get(k, k)


def _image_name(pr):
    from . import images
    spec = pr.spec
    img = spec.get("image")
    if img and images.exists(img):
        return img
    if pr.type not in BUILTIN and images.exists(pr.type):
        return pr.type
    return None


def traits(pr):
    """Set of abilities of a PropTrack (built-in table + picture abilities + scene "abilities")."""
    got = getattr(pr, "_traits", None)
    if got is not None:
        return got
    out = set(BUILTIN.get(base_type(pr.type), {}).get("traits", ()))
    img = _image_name(pr)
    if img:
        from . import images
        meta = images.info(img) or {}
        out |= {str(a).lower() for a in (meta.get("abilities") or [])}
        if meta.get("is3d") and meta.get("foot") and not meta.get("walk") and float(meta.get("height") or 0) >= 40:
            out.add("solid")                    # a real 3D fence / wall / stall: people walk round it
        for st in (meta.get("states") or {}):
            if st in STATE_ABILITY:
                out.add(STATE_ABILITY[st])
    extra = pr.spec.get("abilities") or pr.spec.get("traits")
    if isinstance(extra, str):
        extra = [a.strip() for a in extra.replace(";", ",").split(",")]
    for a in extra or []:
        a = str(a).lower().strip()
        if a.startswith("-") or a.startswith("not_"):
            out.discard(a.lstrip("-").replace("not_", "", 1))
        elif a:
            out.add(a)
    if "heavy" in out:
        out.discard("light")
    if "throw" in out or "light" in out:
        out.add("movable")
    pr._traits = out
    return out


def state_image(pr, state):
    """The picture for this state of an image object (None if it has none)."""
    from . import images
    img = _image_name(pr)
    if not img or not state:
        return None
    meta = images.info(img) or {}
    name = (meta.get("states") or {}).get(state)
    if name and images.exists(name):
        return name
    guess = f"{img}_{state}"
    return guess if images.exists(guess) else None


def states_of(pr):
    from . import images
    img = _image_name(pr)
    return dict((images.info(img) or {}).get("states") or {}) if img else {}


def is_object(pr):
    if getattr(pr, "vtype", None):
        return False
    return base_type(pr.type) in BUILTIN or bool(traits(pr))


def size(pr):
    """(width, height) in story units, with the prop's scale."""
    got = getattr(pr, "_size", None)
    if got is not None:
        return got
    if pr.type == "experiment":
        from . import physics
        pr._size = physics.size(pr.spec)
        return pr._size
    sc = float(pr.spec.get("scale", 1.0))
    b = BUILTIN.get(base_type(pr.type))
    img = _image_name(pr)
    if img:
        from . import images
        meta = images.info(img) or {}
        h = float(pr.spec.get("height") or meta.get("height") or (b["h"] if b else 120))
        s = images.surface(img)
        w = h * s[1] / max(s[2], 1) if s else h
    elif b:
        h = float(pr.spec.get("height") or b["h"])
        w = b["w"] * h / b["h"]
    else:
        h = float(pr.spec.get("height") or 60)
        w = h
    pr._size = (w * sc, h * sc)
    return pr._size


def top_of(pr, sit=False):
    """Height of the surface you sit / stand on (a 3D thing can say where its seat is: SEAT = 122 in its code,
    or pen.thing(..., seat=122) in a place - a throne, a sofa, a bench with a back). Raised things (a thing on a
    stage, "y") count from their own height."""
    w, h = size(pr)
    y_off = float((getattr(pr, "spec", None) or {}).get("y") or 0.0)
    from . import images
    img = _image_name(pr)
    meta = (images.info(img) or {}) if img else {}
    if sit and meta.get("seat"):
        sc = h / max(1.0, float(meta.get("height") or h))
        return float(meta["seat"]) * sc + y_off
    bt = base_type(pr.type)
    return h * {"boulder": 0.93, "rock": 0.9, "bush": 0.8, "haystack": 0.92, "pot": 0.9}.get(bt, 1.0) + y_off


# ============================================================================ drawing
def draw_object(ctx, pr, x, y, t, held_hand=None, alpha=1.0):
    """Draw an object (or a plain prop) at (x, y) = bottom-centre, world coords y-up.
    Takes care of rolling, flying spin, the open lid, breaking into pieces and floating / sinking."""
    from .props import draw_prop
    if not is_object(pr):
        state = pr.at(t)[0]
        spin = (x - state[1]) / 22.0 if state[0] in ("rest", "move") else 0.0
        draw_prop(ctx, pr.type, x, y, t, _with_state(pr, t), spin=spin, held_hand=held_hand, alpha=alpha)
        return
    if pr.type == "experiment":                       # real physics, drawn from its formulas every frame
        from . import physics
        physics.draw_object(ctx, pr, x, y, t, alpha)
        return
    w, h = size(pr)
    bt = base_type(pr.type)
    br = pr.broken_at(t) if hasattr(pr, "broken_at") else None
    if br is not None and br > 0:
        bimg = state_image(pr, "broken")
        if bimg:                                          # the drawn broken pieces stay; a few shards fly first
            from . import images
            images.draw(ctx, bimg, x, y, h * _state_h(pr, bimg), bool(pr.spec.get("flip")), alpha)
            if br < 1.2:
                _draw_pieces(ctx, pr, x, y, w, h * 0.6, br, alpha * (1 - br / 1.2))
            return
        _draw_pieces(ctx, pr, x, y, w, h, br, alpha)
        return
    ang = 0.0
    if held_hand is not None:
        y = held_hand[1] - h * 0.5
        x = held_hand[0]
    else:
        tr = traits(pr)
        if "round" in tr and hasattr(pr, "roll_at"):
            ang = -pr.roll_at(t) / max(h * 0.5, 8.0)
        if hasattr(pr, "spin_at"):
            ang += pr.spin_at(t)
    wet = pr.water_at(t) if hasattr(pr, "water_at") else None
    sub = 0.0
    if wet is not None:
        kind, t0 = wet
        u = clamp((t - t0) / 1.4, 0, 1)
        if kind == "float":
            sub = h * (0.12 + 0.28 * smoothstep(clamp((t - t0) / 0.6, 0, 1))) - 4 * math.sin(1.8 * t + x * 0.01)
            ang += 0.05 * math.sin(1.3 * t + x)
        else:
            sub = h * (0.3 + 0.9 * smoothstep(u))
            if u >= 1:
                return
    ctx.save()
    if sub:
        ctx.save()
        ctx.rectangle(x - w * 3, 0, w * 6, h * 4 + 400)          # the part above the water line
        ctx.clip()
        _draw_whole(ctx, pr, bt, x, y - sub, w, h, t, ang, alpha)
        ctx.restore()
        ctx.rectangle(x - w * 3, -h * 3, w * 6, h * 3)            # under water: faint and blue-ish
        ctx.clip()
        a2 = alpha * (0.35 if wet[0] == "float" else 0.35 * (1 - clamp((t - wet[1]) / 1.4, 0, 1)))
        _draw_whole(ctx, pr, bt, x, y - sub, w, h, t, ang, a2)
    else:
        _draw_whole(ctx, pr, bt, x, y, w, h, t, ang, alpha)
    ctx.restore()


def _draw_whole(ctx, pr, bt, x, y, w, h, t, ang, alpha):
    from . import images
    ctx.save()
    ctx.translate(x, y)
    if ang:
        ctx.translate(0, h / 2)
        ctx.rotate(ang)
        ctx.translate(0, -h / 2)
    img = _image_name(pr)
    op = pr.open_at(t) if hasattr(pr, "open_at") else 0.0
    if img:
        name, hk = img, 1.0
        st = pr.state_at(t) if hasattr(pr, "state_at") else pr.spec.get("state")
        if st and state_image(pr, st):
            name = state_image(pr, st)
        elif op > 0.5 and state_image(pr, "open"):
            name = state_image(pr, "open")
        if name != img:
            hk = _state_h(pr, name)
        images.draw(ctx, name, 0, 0, h * hk, bool(pr.spec.get("flip")), alpha, t=t, turn=float(pr.spec.get("turn") or 0),
                    **images.anim_opts(pr.spec))
        if op > 0.05 and pr.spec.get("treasure"):
            _glow(ctx, 0, h * 0.9, w * 0.6, op * alpha, t)
    elif bt in DRAWN_HERE:
        col = hex_to_rgb(pr.spec.get("color") or BUILTIN[bt]["color"])
        globals()["_d_" + bt](ctx, w, h, col, t, alpha, pr, op)
    else:
        from .props import draw_prop
        draw_prop(ctx, pr.type, 0, 0, t, _with_state(pr, t), alpha=alpha)    # (gives its own light: props.py)
        ctx.restore()
        return
    _night_light(ctx, pr, w, h, t)
    ctx.restore()


def _with_state(pr, t):
    """The prop's spec with its state now (turned on / off during the scene) - a lamp knows if it is lit."""
    got = pr._last(t, ("state",)) if hasattr(pr, "_last") else None
    if got is None:
        return pr.spec
    return dict(pr.spec, state=got[2], id=pr.id)


def _night_light(ctx, pr, w, h, t):
    """A lamp / diya / lantern / candle / torch object gives light at night (engine/nightlights.py): by itself
    after sunset, or after "turn_on" (and not after "turn_off")."""
    from . import nightlights as nl
    name = f"{pr.id} {pr.type} {pr.spec.get('image') or ''}"
    if not nl.is_light_name(name):
        return
    got = pr._last(t, ("state",)) if hasattr(pr, "_last") else None
    st = got[2] if got else pr.spec.get("state")             # (also "off": state_at hides it)
    if st == "off" or not (st == "on" or nl.ON[0] or pr.spec.get("lit")):
        return
    flame = nl.is_flame_name(name)
    nl.add_device(ctx, 0, h * 0.8, max(140.0, max(w, h) * 2.4), nl.FLAME if flame else nl.WARM,
                  0.7 if st == "on" or pr.spec.get("lit") else 0.6, flame=flame, ground=(0, 0), kind="object")


def _state_h(pr, name):
    """A state picture keeps the size it had on the sheet next to the main picture (an open lid is taller,
    broken pieces are lower). Uses the heights measured on the sheet when known."""
    from . import images
    main = images.info(_image_name(pr)) or {}
    other = images.info(name) or {}
    a, b = main.get("sheet_px"), other.get("sheet_px")
    if a and b:
        return max(0.2, min(3.0, float(b) / float(a)))
    return 1.0


def _path(ctx, pts):
    ctx.move_to(*pts[0])
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        ctx.curve_to(x0 + (x1 - x0) * 0.5, y0 + (y1 - y0) * 0.1, x0 + (x1 - x0) * 0.9, y0 + (y1 - y0) * 0.5, x1, y1)
    ctx.close_path()


def _fill_stroke(ctx, col, alpha, lw=4.0, grad=None):
    if grad is not None:
        ctx.set_source(grad)
    else:
        ctx.set_source_rgba(*col, alpha)
    ctx.fill_preserve()
    ctx.set_source_rgba(*darker(col, 0.55), alpha)
    ctx.set_line_width(lw)
    ctx.stroke()


def _vgrad(col, alpha, y0, y1, k0=1.15, k1=0.8):
    import cairo
    g = cairo.LinearGradient(0, y1, 0, y0)
    g.add_color_stop_rgba(0, *(lighter(col, k0 - 1) if k0 > 1 else col), alpha)
    g.add_color_stop_rgba(1, *darker(col, k1), alpha)
    return g


def _d_stone(ctx, w, h, col, t, alpha, pr, op):
    ctx.save()
    ctx.translate(0, h / 2)
    ctx.scale(w / 2, h / 2)
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()
    _fill_stroke(ctx, col, alpha, 2.5, _vgrad(col, alpha, 0, h))
    ctx.set_source_rgba(1, 1, 1, 0.3 * alpha)
    ctx.arc(-w * 0.15, h * 0.68, h * 0.14, 0, TAU)
    ctx.fill()


def _d_rock(ctx, w, h, col, t, alpha, pr, op):
    pts = [(-w * 0.5, 0), (-w * 0.47, h * 0.42), (-w * 0.3, h * 0.86), (0, h), (w * 0.3, h * 0.9),
           (w * 0.47, h * 0.5), (w * 0.5, 0)]
    _path(ctx, pts)
    _fill_stroke(ctx, col, alpha, 4, _vgrad(col, alpha, 0, h))
    ctx.set_source_rgba(*darker(col, 0.6), 0.7 * alpha)
    ctx.set_line_width(3)
    ctx.move_to(w * 0.05, h * 0.95)
    ctx.line_to(w * 0.12, h * 0.6)
    ctx.line_to(w * 0.02, h * 0.4)
    ctx.move_to(-w * 0.3, h * 0.3)
    ctx.line_to(-w * 0.18, h * 0.18)
    ctx.stroke()
    if pr.spec.get("moss", True):
        ctx.set_source_rgba(0.35, 0.55, 0.25, 0.85 * alpha)
        ctx.move_to(-w * 0.36, h * 0.72)
        ctx.curve_to(-w * 0.25, h * 0.98, w * 0.1, h * 1.02, w * 0.22, h * 0.88)
        ctx.curve_to(w * 0.05, h * 0.84, -w * 0.2, h * 0.8, -w * 0.36, h * 0.72)
        ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.16 * alpha)
    ctx.arc(-w * 0.2, h * 0.62, h * 0.12, 0, TAU)
    ctx.fill()


def _d_boulder(ctx, w, h, col, t, alpha, pr, op):
    ctx.save()
    ctx.translate(0, h / 2)
    ctx.scale(w / 2, h / 2)
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()
    _fill_stroke(ctx, col, alpha, 5, _vgrad(col, alpha, 0, h))
    ctx.set_source_rgba(*darker(col, 0.6), 0.75 * alpha)       # cracks + moss turn with the boulder
    ctx.set_line_width(4)
    ctx.move_to(-w * 0.1, h * 0.95)
    ctx.line_to(-w * 0.02, h * 0.7)
    ctx.line_to(-w * 0.12, h * 0.5)
    ctx.move_to(w * 0.3, h * 0.3)
    ctx.line_to(w * 0.18, h * 0.22)
    ctx.line_to(w * 0.22, h * 0.1)
    ctx.stroke()
    ctx.set_source_rgba(0.35, 0.55, 0.25, 0.8 * alpha)
    ctx.arc(-w * 0.22, h * 0.78, h * 0.12, 0, TAU)
    ctx.arc(-w * 0.08, h * 0.86, h * 0.09, 0, TAU)
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.14 * alpha)
    ctx.arc(-w * 0.18, h * 0.62, h * 0.16, 0, TAU)
    ctx.fill()


def _d_log(ctx, w, h, col, t, alpha, pr, op):
    r = h / 2
    ctx.save()                                                  # the far (bark) end
    ctx.translate(-w / 2 + r * 0.4, r)
    ctx.scale(r * 0.4, r)
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()
    _fill_stroke(ctx, darker(col, 0.85), alpha, 4)
    ctx.rectangle(-w / 2 + r * 0.4, 0, w - r * 1.2, h)
    _fill_stroke(ctx, col, alpha, 4, _vgrad(col, alpha, 0, h))
    ang = -pr.roll_at(t) / max(r, 1) if hasattr(pr, "roll_at") else 0.0
    ctx.set_source_rgba(*darker(col, 0.6), 0.8 * alpha)       # bark lines slide round as it rolls
    ctx.set_line_width(3)
    for k in range(5):
        a = ang + k * TAU / 5
        if math.cos(a) <= 0.05:
            continue
        yy = r + r * 0.9 * math.sin(a)
        ctx.move_to(-w / 2 + r * 0.6, yy)
        ctx.line_to(w / 2 - r * 1.1, yy + 3 * math.sin(k))
    ctx.stroke()
    ctx.save()                                                  # the cut end with its rings
    ctx.translate(w / 2 - r * 0.8, r)
    ctx.scale(r * 0.55, r)
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()
    _fill_stroke(ctx, lighter(col, 0.45), alpha, 4)
    ctx.set_source_rgba(*darker(col, 0.8), 0.7 * alpha)
    ctx.set_line_width(2)
    for k in (0.65, 0.35):
        ctx.save()
        ctx.translate(w / 2 - r * 0.8, r)
        ctx.scale(r * 0.55 * k, r * k)
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.stroke()


def _d_chest(ctx, w, h, col, t, alpha, pr, op):
    body_h = h * 0.62
    gold = hex_to_rgb("#d4a83a")
    if op > 0.05 and pr.spec.get("treasure", True):
        _glow(ctx, 0, body_h, w * 0.7, op * alpha, t)
    ctx.rectangle(-w / 2, 0, w, body_h)
    _fill_stroke(ctx, col, alpha, 4, _vgrad(col, alpha, 0, body_h))
    ctx.set_source_rgba(*gold, alpha)
    for bx in (-w * 0.32, w * 0.32):
        ctx.rectangle(bx - 5, 0, 10, body_h)
    ctx.fill()
    if op > 0.05 and pr.spec.get("treasure", True):             # coins peeking over the rim
        ctx.set_source_rgba(1.0, 0.82, 0.25, alpha)
        for k in range(7):
            ctx.arc(-w * 0.36 + k * w * 0.12, body_h + 4 + 5 * math.sin(k * 2.1), 9, 0, TAU)
            ctx.fill()
    ctx.save()                                                  # the lid, hinged at the back (left) edge
    ctx.translate(-w / 2, body_h)
    ctx.rotate(op * math.radians(105))
    lid_h = h - body_h
    ctx.move_to(0, 0)
    ctx.line_to(0, lid_h * 0.55)
    ctx.curve_to(w * 0.1, lid_h * 1.05, w * 0.9, lid_h * 1.05, w, lid_h * 0.55)
    ctx.line_to(w, 0)
    ctx.close_path()
    _fill_stroke(ctx, lighter(col, 0.08), alpha, 4)
    ctx.set_source_rgba(*gold, alpha)
    for bx in (w * 0.18, w * 0.82):
        ctx.rectangle(bx - 5, 0, 10, lid_h * 0.95)
    ctx.fill()
    ctx.rectangle(w / 2 - 9, -10, 18, 16)                        # the lock
    ctx.fill()
    ctx.restore()


def _d_crate(ctx, w, h, col, t, alpha, pr, op):
    ctx.rectangle(-w / 2, 0, w, h)
    _fill_stroke(ctx, col, alpha, 4, _vgrad(col, alpha, 0, h))
    ctx.set_source_rgba(*darker(col, 0.65), alpha)
    ctx.set_line_width(3)
    for k in (1, 2):
        ctx.move_to(-w / 2, h * k / 3)
        ctx.line_to(w / 2, h * k / 3)
    ctx.stroke()
    ctx.set_line_width(6)
    ctx.move_to(-w / 2 + 6, 6)
    ctx.line_to(w / 2 - 6, h - 6)
    ctx.stroke()


def _d_barrel(ctx, w, h, col, t, alpha, pr, op):
    ctx.move_to(-w * 0.42, 0)
    ctx.curve_to(-w * 0.56, h * 0.35, -w * 0.56, h * 0.65, -w * 0.42, h)
    ctx.line_to(w * 0.42, h)
    ctx.curve_to(w * 0.56, h * 0.65, w * 0.56, h * 0.35, w * 0.42, 0)
    ctx.close_path()
    _fill_stroke(ctx, col, alpha, 4, _vgrad(col, alpha, 0, h))
    ctx.set_source_rgba(0.35, 0.35, 0.38, alpha)
    ctx.set_line_width(6)
    for k in (0.18, 0.82):
        ctx.move_to(-w * 0.5, h * k)
        ctx.line_to(w * 0.5, h * k)
    ctx.stroke()


def _d_pot(ctx, w, h, col, t, alpha, pr, op):
    r = w * 0.5
    ctx.arc(0, r * 0.95, r, 0, TAU)
    _fill_stroke(ctx, col, alpha, 3.5, _vgrad(col, alpha, 0, h))
    ctx.rectangle(-r * 0.45, r * 1.7, r * 0.9, h - r * 1.7)
    _fill_stroke(ctx, col, alpha, 3.5)
    ctx.rectangle(-r * 0.6, h - 6, r * 1.2, 7)
    _fill_stroke(ctx, lighter(col, 0.1), alpha, 3)
    ctx.set_source_rgba(1, 0.95, 0.8, 0.8 * alpha)
    ctx.set_line_width(3)
    ctx.move_to(-r * 0.8, r * 1.1)
    ctx.curve_to(-r * 0.3, r * 1.25, r * 0.3, r * 1.25, r * 0.8, r * 1.1)
    ctx.stroke()


def _d_bush(ctx, w, h, col, t, alpha, pr, op):
    sway = 0.02 * math.sin(t * 1.3 + w)
    rustle = pr.rustle_at(t) if hasattr(pr, "rustle_at") else 0.0
    sway += 0.05 * rustle * math.sin(t * 22)
    ctx.save()
    ctx.transform(__import__("cairo").Matrix(1, 0, sway, 1, 0, 0))
    blobs = [(-0.3, 0.35, 0.3), (0.28, 0.38, 0.3), (0.0, 0.55, 0.36), (-0.12, 0.3, 0.3), (0.14, 0.28, 0.28)]
    for k, (bx, by, br) in enumerate(blobs):
        c = darker(col, 0.8 + 0.08 * k) if k < 2 else lighter(col, 0.04 * (k - 2))
        ctx.arc(bx * w, by * h, br * h, 0, TAU)
        ctx.set_source_rgba(*c, alpha)
        ctx.fill()
    ctx.set_source_rgba(*lighter(col, 0.25), 0.6 * alpha)
    for k in range(9):
        a = k * 2.3
        ctx.arc(math.cos(a) * w * 0.3, h * (0.45 + 0.3 * math.sin(a * 1.7)), 7, 0, TAU)
        ctx.fill()
    ctx.restore()


def _d_haystack(ctx, w, h, col, t, alpha, pr, op):
    ctx.move_to(-w / 2, 0)
    ctx.curve_to(-w * 0.5, h * 0.8, -w * 0.2, h, 0, h)
    ctx.curve_to(w * 0.2, h, w * 0.5, h * 0.8, w / 2, 0)
    ctx.close_path()
    _fill_stroke(ctx, col, alpha, 3.5, _vgrad(col, alpha, 0, h))
    ctx.set_source_rgba(*darker(col, 0.7), 0.7 * alpha)
    ctx.set_line_width(2)
    rng = random.Random(7)
    for _ in range(26):
        x0 = rng.uniform(-w * 0.4, w * 0.4)
        y0 = rng.uniform(h * 0.05, h * 0.8)
        ctx.move_to(x0, y0)
        ctx.line_to(x0 + rng.uniform(-10, 10), y0 + rng.uniform(12, 24))
    ctx.stroke()


def _glow(ctx, x, y, r, a, t):
    import cairo
    g = cairo.RadialGradient(x, y, 0, x, y, r * (1.3 + 0.1 * math.sin(t * 5)))
    g.add_color_stop_rgba(0, 1.0, 0.9, 0.4, 0.75 * a)
    g.add_color_stop_rgba(1, 1.0, 0.8, 0.2, 0.0)
    ctx.set_source(g)
    ctx.arc(x, y, r * 1.5, 0, TAU)
    ctx.fill()


def _draw_pieces(ctx, pr, x, y, w, h, dt, alpha):
    """Shards flying out and settling, then fading away."""
    bt = base_type(pr.type)
    col = hex_to_rgb(pr.spec.get("color") or BUILTIN.get(bt, {}).get("color", "#a0785a"))
    rng = random.Random(len(pr.id) * 31 + int(x))
    fade = alpha * (1 - smoothstep(clamp((dt - 2.5) / 1.5, 0, 1)))
    if fade <= 0.01:
        return
    for k in range(9):
        vx = rng.uniform(-260, 260) * (w / 70) ** 0.5
        vy = rng.uniform(120, 380)
        tt = min(dt, 1.2)
        px = x + vx * tt * (1 - 0.35 * tt)
        py = max(0.0, y + h * 0.4 + vy * tt - 900 * tt * tt)
        s = rng.uniform(0.18, 0.32) * max(w, h) * 0.5
        rot = rng.uniform(-8, 8) * min(tt, 0.6)
        ctx.save()
        ctx.translate(px, py)
        ctx.rotate(rot)
        ctx.move_to(-s, 0)
        ctx.line_to(s * rng.uniform(0.2, 0.9), s * rng.uniform(0.4, 1.0))
        ctx.line_to(s, -s * rng.uniform(0.1, 0.5))
        ctx.close_path()
        ctx.set_source_rgba(*(col if k % 3 else darker(col, 0.75)), fade)
        ctx.fill_preserve()
        ctx.set_source_rgba(*darker(col, 0.5), fade)
        ctx.set_line_width(2)
        ctx.stroke()
        ctx.restore()


def _d_sack(ctx, w, h, col, t, alpha, pr, op):
    """A gunny sack of grain: a soft lumpy bag tied at the top."""
    pts = [(-w * 0.5, h * 0.05), (-w * 0.48, h * 0.6), (-w * 0.3, h * 0.86), (-w * 0.1, h * 0.84), (0, h),
           (w * 0.1, h * 0.84), (w * 0.3, h * 0.86), (w * 0.48, h * 0.6), (w * 0.5, h * 0.05)]
    _path(ctx, pts)
    _fill_stroke(ctx, col, alpha, 3.5, _vgrad(col, alpha, 0, h))
    ctx.set_source_rgba(*darker(col, 0.6), alpha)
    ctx.set_line_width(4)
    ctx.move_to(-w * 0.16, h * 0.82)
    ctx.line_to(w * 0.16, h * 0.82)
    ctx.stroke()
    ctx.set_line_width(1.5)
    for k in range(4):                                  # the weave
        y = h * (0.2 + 0.15 * k)
        ctx.move_to(-w * 0.4, y)
        ctx.line_to(w * 0.4, y)
    ctx.stroke()


def _d_leaf(ctx, w, h, col, t, alpha, pr, op):
    """A leaf: it tips from side to side while it floats down."""
    ctx.save()
    ctx.translate(0, h / 2)
    ctx.rotate(0.5 * math.sin(t * 3.1 + w))
    ctx.move_to(-w / 2, 0)
    ctx.curve_to(-w * 0.2, h * 0.7, w * 0.2, h * 0.7, w / 2, 0)
    ctx.curve_to(w * 0.2, -h * 0.7, -w * 0.2, -h * 0.7, -w / 2, 0)
    ctx.close_path()
    _fill_stroke(ctx, col, alpha, 1.5)
    ctx.set_source_rgba(*darker(col, 0.6), alpha)
    ctx.set_line_width(1)
    ctx.move_to(-w / 2, 0)
    ctx.line_to(w / 2, 0)
    ctx.stroke()
    ctx.restore()
