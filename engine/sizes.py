"""Real sizes of everything, in story units (an adult person is 300 tall, a child about 220).

Every thing has a MEDIUM (normal) size, and five size words for variety:
    tiny · small · medium · big · huge        (no word = medium)
The words mean different things for different kinds of things - a "huge" tree is an old banyan (7x a person),
a "huge" house is a haveli (5.5x), a "tiny" rock is a pebble.  Numbers still work on top ("size": 1.2 = 20 % more).
Doors of huts, houses and shops are drawn so a person always fits through them.
"""

PERSON = 300.0
WORDS = ("tiny", "small", "medium", "big", "huge")
WORD_ALIASES = {"mini": "tiny", "little": "small", "short": "small", "normal": "medium", "average": "medium",
                "regular": "medium", "mid": "medium", "large": "big", "tall": "big", "extra_big": "huge",
                "very_big": "huge", "giant": "huge", "massive": "huge", "enormous": "huge", "grand": "huge",
                "chota": "small", "bada": "big", "bahut_bada": "huge"}

# medium height of each thing (adult = 300)
REAL = {
    # homes and buildings
    "hut": 690, "house": 900, "shop": 750, "barn": 900, "stall": 420, "chai_stall": 450, "bus_shelter": 420,
    "station_building": 1050, "hospital_building": 1500, "police_building": 1050, "palace_building": 2400,
    "castle_building": 2700, "fort": 1500, "lm_temple": 1800, "lm_school": 1050, "lm_statue": 900,
    "lm_clock_tower": 2400, "lm_water_tank": 1500, "lm_windmill": 1500, "lm_lighthouse": 2700,
    # small set dressing
    "well": 180, "lm_well": 180, "bench": 130, "lamp": 600, "sign": 360, "umbrella": 330, "swing": 360,
    "slide": 330, "tombstone": 120, "haystack": 300, "cart": 240, "goal": 280,
    # plants
    "tree": 1200, "jungle_tree": 1500, "big_tree": 1650, "banyan": 1650, "palm": 1350, "cactus": 450,
    "banana": 450,
    # land
    "hill_mound": 900,
}
# trees: medium height by kind
TREE_KIND = {"round": 1200, "mango": 1200, "neem": 1200, "gulmohar": 1200, "jacaranda": 1200, "amaltas": 1100,
             "autumn": 1200, "oak": 1350, "apple": 850, "blossom": 950, "pine": 1300, "fir": 1300, "palm": 1350,
             "coconut": 1400, "peepal": 1500, "banyan": 1650, "baobab": 1300, "bamboo": 1250, "cypress": 1350,
             "eucalyptus": 1600, "ashoka": 1250, "willow": 1150, "birch": 1200, "dead": 1000, "bare": 1000,
             "acacia": 950, "cactus_tree": 450, "mushroom_tree": 600, "banana_tree": 450}
# what each size word means, per family of things (x medium)
FAMILY_WORDS = {
    "hut": (0.57, 0.78, 1.0, 1.22, 1.43),        # 1.3x .. 3.3x a person
    "house": (0.67, 0.83, 1.0, 1.33, 1.83),      # 2x .. 5.5x (1 floor = medium, 2 floors = big, haveli = huge)
    "tree": (0.25, 0.63, 1.0, 1.38, 1.75),       # sapling 1x .. old banyan 7x
    "temple": (0.17, 0.5, 1.0, 1.5, 2.0),        # roadside shrine .. 12x
    "rock": (0.3, 0.55, 1.0, 1.6, 3.0),          # pebble .. boulder you climb
    "prop": (0.35, 0.6, 1.0, 1.6, 2.2),          # pots, boxes, baskets
    "default": (0.5, 0.75, 1.0, 1.3, 1.7),
    "hill": (0.17, 0.45, 1.0, 2.0, 3.6),         # a mound (1/2 a person) .. a big hill (11x)
}
FAMILY = {"hut": "hut", "house": "house", "shop": "house", "barn": "house", "station_building": "house",
          "hospital_building": "house", "police_building": "house", "palace_building": "house",
          "castle_building": "house", "fort": "house", "lm_school": "house", "tree": "tree", "jungle_tree": "tree",
          "big_tree": "tree", "banyan": "tree", "palm": "tree", "banana": "tree", "cactus": "tree",
          "lm_temple": "temple", "lm_statue": "temple", "lm_clock_tower": "temple", "lm_lighthouse": "temple",
          "lm_windmill": "temple", "lm_water_tank": "temple",
          "rock": "rock", "boulder": "rock", "stone": "rock", "log": "rock",
          "pot": "prop", "box": "prop", "crate": "prop", "barrel": "prop", "chest": "prop", "bag": "prop",
          "basket": "prop", "gift": "prop", "ball": "prop", "haystack": "prop", "hill_mound": "hill"}


def word(w):
    """'Big' / 'extra big' / 1.3 -> ('big', 1.0) ; unknown -> ('medium', 1.0) ; a number -> ('medium', n)."""
    if w is None or w == "":
        return "medium", 1.0
    if isinstance(w, (int, float)):
        return "medium", float(w)
    k = str(w).lower().strip().replace(" ", "_").replace("-", "_")
    k = WORD_ALIASES.get(k, k)
    if k in WORDS:
        return k, 1.0
    try:
        return "medium", float(k)
    except ValueError:
        return "medium", 1.0


def factor(typ, w="medium", kind=None):
    """How much bigger than medium this size word is for this kind of thing."""
    k, n = word(w)
    fam = FAMILY.get("tree" if kind and typ == "tree" else typ, "default")
    return FAMILY_WORDS[fam][WORDS.index(k)] * n


def real_height(typ, kind=None, w="medium"):
    """Real height (story units) of a thing of this type / tree kind at this size word; None if unknown."""
    if typ == "tree" and kind and kind in TREE_KIND:
        base = TREE_KIND[kind]
    else:
        base = REAL.get(typ)
    if base is None:
        return None
    return base * factor(typ, w, kind)


def split_words(words):
    """['big', 'old', 'hut'] -> ('big', ['old', 'hut'])"""
    out, found = [], None
    for x in words:
        k = WORD_ALIASES.get(x, x)
        if k in WORDS and found is None and len(words) > 1:
            found = k
        else:
            out.append(x)
    return found, out
