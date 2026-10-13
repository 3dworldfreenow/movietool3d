"""🏺 Sculpted things for Ghatti Nagar: household items, furniture and the home itself made of smooth clay like the
people and animals (engine/sculpt3d.py) - a brass lota, steel glasses, a thali, a chai patila, a matka, a broom, a
charpai, a table, chairs, an almirah ... Each recipe is built once at its REAL size (story units: a person is 300
tall, 1 m = 175), meshed and cached, then any 3D code drawing puts it in with

    pen.sculpt("lota", x, y, z, turn=30)                 (engine/code3d.py Pen3.sculpt)

so a sculpted thing is still a normal thing of the engine: a prop people pick up, carry, put down and give, a seat,
a door that opens. names() lists them; SIZE gives each one's size for the place builder.
"""
import math
import os

import numpy as np

from . import sculpt3d as s3
from .sculpt3d import Sculpt

U = 1.0 / 175.0                 # story units -> metres (engine/realworld.py: 175 units = 1 m)
# The sculpted people stand ~ 400 units tall (engine/sculpt_people.py), not the engine's 300: the clay world is built
# to the same measure as them - every sculpted thing, house, tree and room is drawn 1.35 x its recipe (a door 2.1 m
# to a person's 1.7 m, a table top at their hip), so nothing looks like a doll's house next to its people.
CLAY_SCALE = 1.35
BRASS, STEEL, CLAY, WOOD, DARKWOOD = "#c99a2e", "#c9ced6", "#b5562a", "#9b6a3c", "#6b4424"
_MEM = {}
CACHE_VERSION = 16


def _metal(S, c, prof, col, **kw):
    kw.setdefault("gloss", 0.8)
    return S.lathe(c, prof, col, **kw)


# ---------------------------------------------------------------------------- the recipes (y up from 0, centred)
def lota(S):
    """a brass lota: round belly, narrow neck, flared lip"""
    _metal(S, (0, 0, 0), [(0, 0), (6, 0), (12, 6), (13, 12), (10, 18), (6, 22), (6.5, 25), (8, 27), (7, 27.5), (5, 25),
                          (5, 22), (0, 22)], BRASS, k=1.5)


def glass(S):
    """a steel tumbler (open, hollow)"""
    _metal(S, (0, 0, 0), [(0, 0), (6, 0), (7.5, 18), (0, 18)], STEEL, k=0.5)
    S.paint(lambda P: np.maximum(np.hypot(P[:, 0], P[:, 2]) - 6.8, 18 - 0.6 - P[:, 1]), "#a9cfe8", soft=0.3)   # (water)


def cup(S):
    """a white chai cup with a handle"""
    S.lathe((0, 0, 0), [(0, 0), (5, 0), (7, 13), (0, 13)], "#f4efe6", k=0.5, gloss=0.6)
    S.paint(lambda P: np.maximum(np.hypot(P[:, 0], P[:, 2]) - 6.3, 13 - 0.6 - P[:, 1]), "#8a5a2b", soft=0.3)   # (chai)
    S.paint(lambda P: np.abs(P[:, 1] - 11.5) - 0.8, "#c0392b", soft=0.3)
    S.torus((7.3, 7, 0), 3.2, 0.9, "#f4efe6", axis=(0, 0, 1), k=0.5, gloss=0.6)


def saucer(S):
    S.lathe((0, 0, 0), [(0, 0), (5, 0), (11, 2.5), (0, 2.5)], "#f4efe6", k=0.4, gloss=0.6)


def thali(S):
    """a steel plate with a raised rim"""
    _metal(S, (0, 0, 0), [(0, 0), (24, 0), (27, 4), (0, 4)], STEEL, k=0.6)
    S.paint(lambda P: np.maximum(np.abs(np.hypot(P[:, 0], P[:, 2]) - 24.5) - 0.6, 3.4 - P[:, 1]), "#9aa0a8", soft=0.3)


def katori(S):
    _metal(S, (0, 0, 0), [(0, 0), (5, 0), (8, 6), (0, 6)], STEEL, k=0.5)
    S.paint(lambda P: np.maximum(np.hypot(P[:, 0], P[:, 2]) - 7.3, 6 - 0.6 - P[:, 1]), "#e0a030", soft=0.3)   # (dal)


def patila(S):
    """the chai patila: a steel pan with a long handle"""
    _metal(S, (0, 0, 0), [(0, 0), (13, 0), (14, 14), (0, 14)], STEEL, k=0.8)
    S.paint(lambda P: np.maximum(np.hypot(P[:, 0], P[:, 2]) - 13.2, 14 - 0.6 - P[:, 1]), "#9a6a3c", soft=0.3)   # (chai)
    S.capsule((13, 11, 0), (36, 15, 0), 2.2, 1.8, "#2b2b2b", k=1.0, gloss=0.4)


def kettle(S):
    _metal(S, (0, 0, 0), [(0, 0), (11, 0), (13, 8), (11, 16), (5, 19), (1, 20), (0, 20)], STEEL, k=1.0)
    S.tube([(10, 6, 0), (17, 12, 0), (21, 18, 0)], 1.6, STEEL, k=0.8, gloss=0.8)
    S.tube([(-8, 15, 0), (-6, 26, 0), (6, 26, 0), (8, 15, 0)], 1.4, "#2b2b2b", k=0.6, gloss=0.4)
    S.sphere((0, 21, 0), 2.2, "#2b2b2b", k=0.8, gloss=0.4)


def cooker(S):
    """a pressure cooker: the pot, the lid, the whistle and the black handle"""
    _metal(S, (0, 0, 0), [(0, 0), (15, 0), (16, 22), (14, 25), (0, 25)], STEEL, k=1.2)
    S.cyl((0, 25, 0), 2.5, 6, "#2b2b2b", gloss=0.4)
    S.capsule((14, 21, 0), (40, 23, 0), 2.8, 2.6, "#1f1f1f", k=1.2, gloss=0.4)


def tiffin(S):
    """a three-tier steel tiffin carrier with its clip handle"""
    for k in range(3):
        _metal(S, (0, k * 11, 0), [(0, 0), (11, 0), (11.6, 10), (0, 10)], STEEL, k=0.8)
    S.tube([(-12, 6, 0), (-13, 40, 0), (13, 40, 0), (12, 6, 0)], 1.1, STEEL, k=0.5, gloss=0.85)


def dabba(S):
    """a steel canister (masala / atta)"""
    _metal(S, (0, 0, 0), [(0, 0), (10, 0), (10, 24), (9, 26), (0, 26)], STEEL, k=1.0)
    S.sphere((0, 27, 0), 2.2, STEEL, k=0.8, gloss=0.85)


def tawa(S):
    S.lathe((0, 0, 0), [(0, 0), (20, 0), (22, 2.5), (0, 2.5)], "#2a2a2a", k=0.8, gloss=0.35)
    S.capsule((21, 2, 0), (38, 4, 0), 1.6, 1.4, DARKWOOD, k=0.8)


def belan(S):
    """the rolling pin"""
    S.capsule((-14, 3, 0), (14, 3, 0), 2.8, 2.8, "#d9b27a", k=1.0, gloss=0.25)
    for s_ in (-1, 1):
        S.capsule((s_ * 14, 3, 0), (s_ * 21, 3, 0), 1.4, 1.2, "#c49460", k=0.8)


def matka(S):
    """a clay water pot"""
    S.lathe((0, 0, 0), [(0, 0), (10, 0), (22, 14), (24, 26), (18, 40), (11, 47), (12.5, 51), (10.5, 51), (9, 47), (0, 47)],
            CLAY, k=2.0, gloss=0.15)
    S.paint(lambda P: np.abs(P[:, 1] - 38) - 1.2, "#f2e6d0", soft=0.5)


def bucket(S):
    """a plastic balti with a steel handle"""
    S.lathe((0, 0, 0), [(0, 0), (16, 0), (20, 34), (0, 34)], "#2f74c0", k=1.0, gloss=0.45)
    S.paint(lambda P: np.maximum(np.hypot(P[:, 0], P[:, 2]) - 18.8, 34 - 0.6 - P[:, 1]), "#7fb3d8", soft=0.3)   # (water)
    S.tube([(-19.5, 30, 0), (-12, 46, 0), (12, 46, 0), (19.5, 30, 0)], 0.9, STEEL, k=0.5, gloss=0.85)


def mug(S):
    """the bathing mug (lota-mug) with its handle"""
    S.lathe((0, 0, 0), [(0, 0), (8, 0), (9, 14), (0, 14)], "#e9c46a", k=0.6, gloss=0.4)
    S.paint(lambda P: np.maximum(np.hypot(P[:, 0], P[:, 2]) - 8.2, 14 - 0.6 - P[:, 1]), "#b8952e", soft=0.3)   # (inside)
    S.capsule((8.5, 9, 0), (18, 10, 0), 1.8, 1.4, "#e9c46a", k=0.8, gloss=0.4)


def broom(S):
    """the jhadu: a bundle of grass bound with string"""
    S.capsule((0, 40, 0), (0, 110, 0), 4.5, 3.5, "#d9b56f", k=1.5, gloss=0.1)
    S.capsule((0, 0, 0), (0, 42, 0), 14, 5, "#e3c27d", k=3.0, gloss=0.08)
    S.paint(lambda P: np.abs(P[:, 1] - 46) - 2.0, "#c0392b", soft=0.6)
    S.paint(lambda P: np.abs(((P[:, 0] + P[:, 2]) * 0.8) % 2.4 - 1.2) - 0.25 + np.maximum(0, P[:, 1] - 38), "#c8a35c",
            soft=0.3)


def pillow(S):
    S.rbox((0, 7, 0), (30, 7, 18), "#f6efe0", r=6, k=2.0, gloss=0.15)
    S.paint(lambda P: np.abs(np.abs(P[:, 0]) - 26) - 1.0, "#d98c9f", soft=0.5)


def blanket(S):
    """a folded razai"""
    S.rbox((0, 11, 0), (40, 11, 30), "#a33b3b", r=7, k=2.0, gloss=0.08)
    S.paint(lambda P: np.abs(((P[:, 0] + 40) % 16) - 8) - 2.5, "#e9c46a", soft=0.6)


def lantern(S):
    """the lalten: a base tank, a glass chimney, a wire frame and the carrying ring"""
    S.cyl((0, 0, 0), 9, 9, "#c0392b", gloss=0.5)
    S.lathe((0, 9, 0), [(0, 0), (6, 0), (8, 9), (6, 18), (3.5, 21), (0, 21)], "#fff3b0", k=0.8, gloss=0.9)
    S.cyl((0, 30, 0), 7, 4, "#c0392b", gloss=0.5)
    for a in range(4):
        x, z = 9 * math.cos(a * math.pi / 2), 9 * math.sin(a * math.pi / 2)
        S.capsule((x, 9, z), (x * 0.8, 30, z * 0.8), 0.6, 0.6, "#3a3a3a", k=0.3)
    S.torus((0, 40, 0), 6, 0.8, "#3a3a3a", axis=(1, 0, 0), k=0.4, gloss=0.4)


def phone(S):
    """a mobile phone"""
    S.rbox((0, 0.8, 0), (4, 0.8, 8), "#1d1f24", r=0.7, k=0.2, gloss=0.8)
    S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) - 3.5, np.abs(P[:, 2]) - 7.4), 1.2 - P[:, 1]), "#2a4d7a",
            soft=0.15, gloss=0.95)


def radio(S):
    S.rbox((0, 12, 0), (20, 12, 7), "#8b3a2a", r=3, k=1.0, gloss=0.4)
    S.paint(lambda P: np.maximum(np.hypot(P[:, 0] + 8, P[:, 1] - 12) - 7, -P[:, 2]), "#3a2a20", soft=0.4)
    for x in (8, 14):
        S.cyl((x, 15, 7), 2, 2, "#e9c46a", rr=0.5, gloss=0.6)
    S.tube([(-14, 24, -3), (-18, 50, -3)], 0.6, STEEL, k=0.2, gloss=0.9)


def clock(S):
    """a round wall clock, standing up and facing +z (it hangs: its back is at z = 0)"""
    S.ellipsoid((0, 17, 2), (16, 16, 2), "#fbf6e9", k=0.5, gloss=0.4)
    S.torus((0, 17, 2), 16, 2.2, "#7a4a24", axis=(0, 0, 1), k=0.6, gloss=0.4)
    front = lambda P: np.maximum(0, 3.0 - P[:, 2]) * 9          # the hands are drawn on the face only
    S.paint(lambda P: np.maximum(np.abs(P[:, 0]) - 0.8, np.maximum(17 - P[:, 1], P[:, 1] - 28)) + front(P), "#1d1d1d", soft=0.2)
    S.paint(lambda P: np.maximum(np.abs(P[:, 1] - 17) - 0.8, np.maximum(-P[:, 0], P[:, 0] - 8)) + front(P), "#1d1d1d", soft=0.2)
    S.paint_ball((0, 17, 4), 1.4, "#b3261e")


def book(S):
    S.rbox((0, 2.5, 0), (10, 2.5, 14), "#1d4e89", r=0.6, k=0.2, gloss=0.2)
    S.paint(lambda P: P[:, 0] - 9.2, "#f4efe1", soft=0.2)


def books(S):
    for k, (c, w) in enumerate((("#1d4e89", 10), ("#a33b3b", 9), ("#2a9d8f", 10.5), ("#e9c46a", 9.5))):
        S.rbox((k * 0.8 - 1, 2.5 + k * 5, k * 0.5), (w, 2.4, 14), c, r=0.6, k=0.2, gloss=0.2)


def school_bag(S):
    S.rbox((0, 22, 0), (17, 22, 8), "#e76f51", r=6, k=2.0, gloss=0.25)
    S.rbox((0, 13, 8), (12, 9, 3), "#d65a3c", r=3, k=1.0, gloss=0.25)
    S.torus((0, 45, -1), 5, 1.1, "#3a3a3a", axis=(0, 0, 1), k=0.5)
    for s_ in (-1, 1):
        S.tube([(s_ * 9, 42, -8), (s_ * 11, 22, -12), (s_ * 9, 4, -8)], 1.5, "#3a3a3a", k=0.6)


def umbrella(S):
    """a folded black umbrella with a curved handle"""
    S.capsule((0, 6, 0), (0, 70, 0), 4.5, 1.2, "#1d1d1d", k=2.0, gloss=0.3)
    S.tube([(0, 70, 0), (0, 84, 0), (3, 88, 0), (6, 84, 0)], 1.4, DARKWOOD, k=0.6, gloss=0.4)
    S.capsule((0, 0, 0), (0, 8, 0), 0.8, 0.8, STEEL, k=0.3, gloss=0.8)


def chappal(S):
    """a pair of chappals"""
    for s_ in (-1, 1):
        S.rbox((s_ * 6, 1, 0), (4.5, 1, 13), "#5a3a22", r=0.9, k=0.3, gloss=0.2)
        S.tube([(s_ * 6 - 4, 2, 4), (s_ * 6, 5, 5), (s_ * 6 + 4, 2, 4)], 1.0, "#c0392b", k=0.4)


def newspaper(S):
    S.rbox((0, 0.6, 0), (16, 0.6, 22), "#efe9dc", r=0.3, k=0.1, gloss=0.05)
    S.paint(lambda P: np.maximum(np.abs(((P[:, 2] + 22) % 3.2) - 1.6) - 0.35, np.abs(P[:, 0]) - 14), "#8a8a8a",
            soft=0.15)
    S.paint(lambda P: np.maximum(np.abs(P[:, 2] + 17) - 3, np.abs(P[:, 0]) - 13), "#222222", soft=0.2)


def photo_frame(S):
    S.rbox((0, 13, 0), (10, 13, 1.2), "#6b4424", r=0.8, k=0.3, gloss=0.4)
    S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) - 7.5, np.abs(P[:, 1] - 13) - 10.5), -P[:, 2]), "#7fa7c9",
            soft=0.3)
    S.capsule((0, 6, -1), (0, 0, -8), 0.7, 0.7, "#6b4424", k=0.3)


def mirror(S):
    """a hand mirror"""
    S.lathe((0, 0, 0), [(0, 0), (8, 0), (8.5, 1.5), (0, 1.5)], "#b5651d", k=0.4, gloss=0.4)
    S.paint(lambda P: np.hypot(P[:, 0], P[:, 2]) - 7 + np.maximum(0, 1.2 - P[:, 1]) * 9, "#dfe9f3", soft=0.2, gloss=1.0)
    S.capsule((0, 0.8, 8), (0, 0.8, 20), 1.6, 1.4, "#b5651d", k=0.6, gloss=0.4)


def comb(S):
    S.rbox((0, 0.4, 0), (1.2, 0.4, 8), "#3a3a3a", r=0.2, k=0.1, gloss=0.4)
    S.paint(lambda P: np.maximum(np.abs((P[:, 2] + 8) % 1.0 - 0.5) - 0.18, P[:, 0] - 0.2), "#1a1a1a", soft=0.05)


def bottle(S):
    """a plastic water bottle"""
    S.lathe((0, 0, 0), [(0, 0), (5, 0), (5.5, 22), (3, 27), (2.2, 30), (0, 30)], "#9fd3f0", k=0.6, gloss=0.9)
    S.cyl((0, 29, 0), 2.6, 4, "#2f74c0", gloss=0.5)


def diya(S):
    S.lathe((0, 0, 0), [(0, 0), (3, 0), (7, 3), (6.2, 3.4), (2.6, 1), (0, 1)], CLAY, k=0.4, gloss=0.2)


def chair(S):
    """a wooden chair (seat 80 high)"""
    S.fine = 3.2                                        # thin legs need a finer grid than the chair's size gives
    for x in (-18, 18):
        for z in (-16, 16):
            S.capsule((x, 0, z), (x, 78, z), 3.4, 3.0, WOOD, k=1.5, gloss=0.3)
    S.rbox((0, 80, 0), (21, 3, 19), WOOD, r=2, k=1.5, gloss=0.3)
    for x in (-18, 18):
        S.capsule((x, 80, -17), (x * 1.05, 158, -21), 3.4, 3.0, WOOD, k=1.2, gloss=0.3)
    S.rbox((0, 145, -20), (20, 10, 2), DARKWOOD, r=1.5, k=1.2, gloss=0.3)
    S.rbox((0, 115, -18.5), (19, 2.5, 1.6), DARKWOOD, r=1, k=0.8, gloss=0.3)


def stool(S):
    """a round moodha / stool (seat 70 high)"""
    S.lathe((0, 0, 0), [(0, 0), (22, 0), (14, 35), (22, 66), (22, 72), (0, 72)], "#c8a165", k=2.0, gloss=0.1)
    S.paint(lambda P: np.abs(((np.arctan2(P[:, 2], P[:, 0]) * 6) % 2) - 1) - 0.3 + np.maximum(0, P[:, 1] - 64) * 2,
            "#a9824a", soft=0.6)
    S.cyl((0, 64, 0), 22.5, 8, "#a33b3b", gloss=0.15)


def table(S):
    """a wooden table (top 130 high)"""
    S.rbox((0, 125, 0), (75, 5, 45), WOOD, r=2.5, k=2.0, gloss=0.35)
    for x in (-66, 66):
        for z in (-37, 37):
            S.capsule((x, 0, z), (x, 122, z), 4, 3.5, DARKWOOD, k=2.0, gloss=0.3)
    S.rbox((0, 110, 0), (70, 4, 40), DARKWOOD, r=1.5, k=1.5, gloss=0.3)


def charpai(S):
    """a woven charpai (string bed 1.9 m x 0.9 m, top 78 high)"""
    S.fine = 6.0
    for x in (-160, 160):
        for z in (-74, 74):
            S.lathe((x, 0, z), [(0, 0), (7, 0), (8, 30), (5.5, 52), (8, 72), (7, 80), (0, 80)], DARKWOOD, k=1.5, gloss=0.3)
    for z in (-74, 74):
        S.capsule((-160, 74, z), (160, 74, z), 5, 5, WOOD, k=1.5, gloss=0.3)
    for x in (-160, 160):
        S.capsule((x, 74, -74), (x, 74, 74), 5, 5, WOOD, k=1.5, gloss=0.3)
    S.rbox((0, 73, 0), (157, 4.5, 71), "#e0c58f", r=2, k=1.0, gloss=0.05)     # the woven top (thick enough to mesh)
    S.paint(lambda P: np.minimum(np.abs(((P[:, 0] + P[:, 2]) % 10) - 5), np.abs(((P[:, 0] - P[:, 2]) % 10) - 5)) - 1.1,
            "#c8a96b", soft=0.5)


def bed(S):
    """a double bed (1.9 m x 1.4 m) with a headboard, a mattress and a sheet (top 92); its pillows are their own things"""
    S.rbox((0, 32, 0), (122, 32, 166), DARKWOOD, r=4, k=2.5, gloss=0.3)
    S.rbox((0, 76, 6), (118, 16, 158), "#f3efe6", r=10, k=3.0, gloss=0.1)
    S.paint(lambda P: (np.abs(((P[:, 0] + 200) % 28) - 14) - 4) + np.maximum(0, 64 - P[:, 1]) + np.maximum(0, -150 - P[:, 2]) * 9,
            "#7aa6c2", soft=1.4)
    S.rbox((0, 120, -164), (124, 80, 7), DARKWOOD, r=6, k=2.0, gloss=0.3)
    S.paint(lambda P: np.maximum(np.abs(P[:, 0]) - 100, np.abs(P[:, 1] - 140) - 40) + np.maximum(0, P[:, 2] + 160) * 9,
            "#8a5a32", soft=1.0)


def almirah(S):
    """a steel almirah (cupboard 1.85 m tall) with two doors"""
    S.rbox((0, 162, 0), (78, 162, 44), "#5b7f95", r=4, k=2.0, gloss=0.55)
    S.paint(lambda P: np.maximum(np.abs(P[:, 0]) - 1.6, -P[:, 2] + 40), "#2e4553", soft=0.6)
    S.paint(lambda P: np.maximum(np.abs(P[:, 1] - 300) - 1.2, -P[:, 2] + 42), "#2e4553", soft=0.4)
    for s_ in (-1, 1):
        S.capsule((s_ * 7, 150, 46), (s_ * 7, 190, 46), 1.6, 1.6, STEEL, k=0.6, gloss=0.9)


def trunk(S):
    """a blue tin trunk (petti, 75 cm long, top 72)"""
    S.rbox((0, 36, 0), (65, 36, 40), "#1f4e8c", r=4, k=1.5, gloss=0.5)
    S.paint(lambda P: np.abs(P[:, 1] - 58) - 1.6, "#c9a227", soft=0.5)
    S.capsule((-16, 73, 0), (16, 73, 0), 1.8, 1.8, "#c9a227", k=0.6, gloss=0.8)


def shelf(S):
    """a wall shelf: three wooden boards on brackets (the boards at 120, 165 and 210)"""
    for y in (120, 165, 210):
        S.rbox((0, y, 0), (60, 2.5, 14), WOOD, r=1, k=0.8, gloss=0.3)
    for x in (-58, 58):
        S.rbox((x, 165, -12), (2.5, 48, 2.5), DARKWOOD, r=1, k=0.8, gloss=0.3)


def platform(S):
    """the kitchen platform (1.6 m long, top 150 = 85 cm) with a two-burner gas stove"""
    S.rbox((0, 72, 0), (140, 72, 50), "#d8cbb5", r=3, k=2.0, gloss=0.2)
    S.rbox((0, 146, 0), (142, 4, 52), "#3d3d3d", r=2, k=1.5, gloss=0.7)
    S.rbox((-40, 153, 4), (40, 4, 22), "#2b2b2b", r=2, k=1.0, gloss=0.6)
    for x in (-60, -20):
        S.torus((x, 158, 4), 8, 1.4, "#6b6b6b", axis=(0, 1, 0), k=0.5, gloss=0.6)
    for x in (-70, 0, 70):                               # cupboard doors under the top
        S.paint(lambda P, x=x: np.maximum(np.abs(np.abs(P[:, 0] - x) - 32), np.abs(P[:, 1] - 70) - 55) - 1.2
                + np.maximum(0, 48 - P[:, 2]) * 2, "#b9a98f", soft=0.6)


def tv(S):
    """a TV on a low stand"""
    S.rbox((0, 30, 0), (60, 30, 22), DARKWOOD, r=3, k=1.5, gloss=0.3)
    S.rbox((0, 92, 0), (50, 30, 3), "#151515", r=2, k=1.0, gloss=0.6)
    S.paint(lambda P: np.maximum(np.maximum(np.abs(P[:, 0]) - 46, np.abs(P[:, 1] - 92) - 26), -P[:, 2] + 2), "#2d3b4a",
            soft=0.3, gloss=0.95)
    S.rbox((0, 62, 0), (14, 2, 8), "#151515", r=1, k=0.8, gloss=0.6)


def sofa(S):
    """a three-seat sofa (1.8 m) with cushions (seat 80)"""
    S.rbox((0, 36, 0), (158, 36, 50), "#7a4a24", r=7, k=2.0, gloss=0.2)
    for x in (-98, 0, 98):
        S.rbox((x, 76, 6), (47, 11, 44), "#b23a48", r=8, k=2.5, gloss=0.15)
        S.rbox((x, 118, -40), (47, 36, 10), "#b23a48", r=9, k=2.5, gloss=0.15)
    for s_ in (-1, 1):
        S.rbox((s_ * 156, 90, 0), (12, 28, 48), "#7a4a24", r=8, k=2.0, gloss=0.2)


def mandir(S):
    """the small home temple on a wall shelf: a carved shelf, a little idol, a diya and a bell"""
    S.rbox((0, 175, 0), (32, 3, 15), "#c99a2e", r=1.5, k=1.0, gloss=0.6)
    S.rbox((0, 205, -12), (30, 30, 3), "#e9c46a", r=4, k=1.0, gloss=0.5)
    S.ellipsoid((0, 190, -4), (6, 12, 5), "#e76f51", k=2.0, gloss=0.5)
    S.lathe((14, 178, 4), [(0, 0), (3, 0), (6, 2.5), (5.4, 2.8), (2.6, 0.8), (0, 0.8)], BRASS, k=0.3, gloss=0.8)


RECIPES = {f.__name__: f for f in (lota, glass, cup, saucer, thali, katori, patila, kettle, cooker, tiffin, dabba, tawa,
                                    belan, matka, bucket, mug, broom, pillow, blanket, lantern, phone, radio, clock, book,
                                    books, school_bag, umbrella, chappal, newspaper, photo_frame, mirror, comb, bottle,
                                    diya, chair, stool, table, charpai, bed, almirah, trunk, shelf, platform, tv, sofa,
                                    mandir)}
# what kind of thing each is (engine/objects.py abilities) and where people put things on it (top height)
CARRY = ("lota", "glass", "cup", "saucer", "thali", "katori", "patila", "kettle", "cooker", "tiffin", "dabba", "tawa",
         "belan", "bucket", "mug", "broom", "pillow", "blanket", "lantern", "phone", "radio", "clock", "book", "books",
         "school_bag", "umbrella", "chappal", "newspaper", "photo_frame", "mirror", "comb", "bottle", "diya")
BREAKS = ("glass", "cup", "saucer", "matka", "lantern", "mirror", "photo_frame", "diya")
TOPS = {"table": 130, "charpai": 78, "bed": 92, "trunk": 74, "shelf": 122, "platform": 150, "tv": 60, "stool": 72,
        "chair": 83, "sofa": 87, "almirah": 324, "mandir": 178}


def names():
    """the household things (the village's houses and trees are in engine/sculpt_village.py)"""
    return sorted(RECIPES)


def _recipe(name):
    if name in RECIPES:
        return RECIPES[name]
    from . import sculpt_village
    return sculpt_village.RECIPES[name]


def abilities(name):
    ab = []
    if name in CARRY:
        ab += ["movable", "light", "throw"]
    if name in BREAKS:
        ab.append("break")
    if name in ("chair", "stool", "charpai", "bed", "sofa", "trunk"):
        ab += ["sit"]
    if name in ("chair", "stool", "matka", "bucket", "trunk"):
        ab += ["movable"]
    if name in ("trunk", "almirah"):
        ab += ["open"]
    if name in ("charpai", "table", "bed"):
        ab += ["stand"]
    if name in ("lantern", "radio", "tv"):
        ab += ["switch"]
    return sorted(set(ab))


# ---------------------------------------------------------------------------- build, cache, faces
def _cell(S):
    lo = np.min([x.box[0] for x in S.shapes if x.box is not None and x.mode == "add"], axis=0)
    hi = np.max([x.box[1] for x in S.shapes if x.box is not None and x.mode == "add"], axis=0)
    size = float(np.max(hi - lo))
    return max(min(size * 0.035, getattr(S, "fine", 1e9)), 0.85), size


FAR_CELL = 0.06                 # the far mesh: a cell of 6 % of the thing's size (a house ~ 900 faces, not 9000)


def _occlusion(S, P, N, size):
    """baked once into the clay's colours: how open each point is to the sky - dark under the eaves, in a doorway,
    under a tree's crown, where a wall meets the ground (the ground counts: y = 0); a warm bounce keeps it soft"""
    F = lambda Q: np.minimum(S.all_field(Q), Q[:, 1])           # noqa: E731
    step = min(max(size * 0.02, 0.02), 0.06)                    # (metres: reaches 30 cm at most - a soft corner,
                                                                #  not a smudge round a window)
    occ, w = np.zeros(len(P)), 1.0
    for i in range(1, 6):
        h = step * i
        occ += w * np.clip(h - F(P + N * h), 0, None) / h
        w *= 0.6
    ao = np.clip(1.0 - 0.55 * occ, 0.45, 1.0)
    return 0.62 + 0.38 * ao                                     # (never black: clay in daylight)


def mesh(name, far=False):
    """-> (V, Q, N, C, G) in story units (built once: memory + cache/sculpt_things/<name>.npz). far=True: the light
    mesh drawn when the thing is small on the screen (a house down the road) - same clay, far fewer faces"""
    key = (name, bool(far))
    if key in _MEM:
        return _MEM[key]
    from .sculpt_animals import _to_metres
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "sculpt_things",
                        f"{name}{'_far' if far else ''}_v{CACHE_VERSION}.npz")
    if os.path.exists(path):
        try:
            z = np.load(path)
            _MEM[key] = (z["V"], z["Q"], z["N"], z["C"], z["G"])
            return _MEM[key]
        except Exception:                               # noqa: BLE001 - a broken cache file: make it again
            pass
    S = Sculpt()
    _recipe(name)(S)
    cell, size_ = _cell(S)
    if far:
        cell = max(cell * 1.8, min(size_ * FAR_CELL, cell * 3.0))
    S = _to_metres(S, U)
    S.color_tau = cell * U * 0.35
    parts = S.build(cell=cell * U, quads=True)
    if far and not parts:
        return mesh(name)                                # too thin for the light mesh: the full one
    V = np.concatenate([p.V for p in parts]) / U
    Q, N, C, G, off = [], [], [], [], 0
    for p in parts:
        Q.append(p.T + off)
        N.append(p.N)
        C.append(np.clip(p.C, 0, 1))
        G.append(p.G)
        off += len(p.V)
    Ca, Na = np.concatenate(C), np.concatenate(N)
    Ca = Ca * _occlusion(S, V * U, Na, size_ * U)[:, None]
    got = (V.astype(np.float32), np.concatenate(Q).astype(np.int32), Na.astype(np.float32),
           np.clip(Ca, 0, 1).astype(np.float32), np.concatenate(G).astype(np.float32))
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp.npz"
        np.savez_compressed(tmp, V=got[0], Q=got[1], N=got[2], C=got[3], G=got[4])
        os.replace(tmp, path)
    except OSError:
        pass
    _MEM[key] = got
    return got


def size(name):
    V = mesh(name)[0]
    lo, hi = V.min(axis=0), V.max(axis=0)
    return {"w": float(hi[0] - lo[0]), "h": float(hi[1] - lo[1]), "d": float(hi[2] - lo[2])}
