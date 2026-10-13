"""Small math / colour helpers shared by every module."""
import math
import random

TAU = math.pi * 2


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease(t, kind="inout"):
    t = clamp(t, 0.0, 1.0)
    if kind == "linear":
        return t
    if kind == "in":
        return t * t
    if kind == "out":
        return 1 - (1 - t) * (1 - t)
    return smoothstep(t)


def rad(d):
    return d * math.pi / 180.0


def dirv(deg):
    """Unit vector for an angle measured from straight DOWN, positive = forward (+x)."""
    r = rad(deg)
    return math.sin(r), -math.cos(r)


def rotate(p, deg, origin=(0.0, 0.0)):
    r = rad(deg)
    c, s = math.cos(r), math.sin(r)
    x, y = p[0] - origin[0], p[1] - origin[1]
    return origin[0] + x * c - y * s, origin[1] + x * s + y * c


def hex_to_rgb(h, default=(0.1, 0.1, 0.1)):
    if isinstance(h, (tuple, list)):
        return tuple(float(c) for c in h[:3])
    if not isinstance(h, str):
        return default
    named = NAMED_COLORS.get(h.lower())
    if named:
        h = named
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return default


def mix(c1, c2, t):
    return tuple(lerp(a, b, t) for a, b in zip(c1, c2))


def darker(c, f=0.75):
    return tuple(x * f for x in c)


def lighter(c, f=0.3):
    return tuple(x + (1 - x) * f for x in c)


def seeded(seed):
    return random.Random(seed)


def stable_hash(text):
    h = 2166136261
    for ch in str(text):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


NAMED_COLORS = {
    "black": "#1b1b1b", "white": "#ffffff", "red": "#d62828", "blue": "#1d4e89",
    "green": "#2a9d4f", "yellow": "#f4c430", "orange": "#f77f00", "purple": "#6a3fa0",
    "pink": "#e75480", "brown": "#7b4a2a", "gray": "#6c757d", "grey": "#6c757d",
    "navy": "#14213d", "teal": "#1a7f7a", "maroon": "#7a1f2b", "gold": "#d4a017",
}
