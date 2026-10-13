"""One catalog of everything the engine can do. Used by the Studio dropdowns AND the AI prompt,
so both are always in sync with the engine and with your custom assets."""
from . import animals, registry
from .background import PRESETS
from .character import OUTFITS, SKIN, HAIR, BUILD
from .poses import ACTIONS
from .professions import PROFESSIONS
from .styles import SEASONS, REGIONS, MOODS, LANDMARKS, WATER_KINDS
from .timeline import VEHICLES
from .props import PROP_TYPES
from .nature import SKY_LOOKS, CLOUD_STYLES, MORE_TREES

HATS = ["none", "cap", "top", "crown", "bow", "turban", "police", "straw", "helmet", "hard_hat", "fire_helmet",
        "chef", "nurse", "beret", "pilot"]
HAIRS = ["short", "spiky", "curly", "long", "ponytail", "bun", "braid", "bald", "bald_sides"]
EMOTIONS = ["neutral", "happy", "sad", "angry", "surprised", "scared", "laughing", "crying", "sleeping", "thinking"]
ICONS = ["!", "?", "heart", "idea", "sweat", "anger", "stars", "music", "zzz", "blush", "tears", "shock", "gloom"]
EFFECTS = ["confetti", "sparkle", "smoke", "fire", "splash", "hearts", "explosion", "leaves", "lightning", "dust",
           "fireworks", "anaar", "phuljhadi", "chakri", "holi", "petals", "fountain", "sparks", "waterfall_mist",
           "speed_lines", "run_lines", "impact", "rays", "gloom", "sparkle_bg", "swirl", "flash"]
WEATHER = ["clear", "windy", "rain", "storm", "snow", "cyclone", "overcast", "fog"]
TIMES = ["morning", "day", "sunset", "evening", "night", "dawn", "golden_hour", "dusk", "noon", "midnight"]
CAMERAS = ["auto", "wide", "follow", "closeup", "focus", "pan", "zoom", "shake", "punch", "extreme_wide", "dark_wide",
           "slow_pan", "pan_left", "pan_right", "slow_push", "slow_pull", "long_lens", "handheld_follow", "dolly_zoom",
           "crash_zoom", "extreme_closeup", "insert", "full_shot", "medium_wide", "medium_closeup", "drone",
           "overhead", "pedestal_up", "pedestal_down", "static_wide", "earthquake", "explosion", "rumble", "vehicle",
           "heartbeat"]
MUSIC = ["happy", "calm", "sad", "tense", "adventure", "funny", "mystery", "romantic",
         "raga_calm", "raga_happy", "raga_sad", "raga_morning", "raga_rain", "raga_mystery", "raga_festival",
         "raga_adventure", "none"]
SFX = ["door", "knock", "clap", "whoosh", "pop", "ding", "bell", "tada", "boing", "splash", "crash", "thunder",
       "car_horn", "phone", "heartbeat", "magic", "bird", "dog", "roar", "meow", "moo", "neigh", "trumpet", "caw",
       "quack", "cluck", "rocket", "engine", "gulp", "crunch", "punch", "hoot", "coo", "firework", "fizz",
       "crackle", "kiss", "slap"]
EARS = ["round", "pointy", "pointy_tall", "floppy", "side", "long", "huge"]
TAILS = ["long", "tuft", "tuft_thin", "long_up", "curve", "bushy", "long_hair", "puff", "short_up", "curly"]
PATTERNS = ["none", "stripes", "stripes_light", "zebra", "giraffe", "spots", "patches", "panda", "leopard", "wool"]
INDOOR_OBJECTS = ["tv", "fan", "table_fan", "fridge", "stove", "bed", "sofa", "table", "bookshelf", "wardrobe",
                  "lamp_floor", "plant", "clock", "picture", "window", "door"]
OUTDOOR_OBJECTS = ["tree", "house", "shop", "hut", "bench", "rock", "lamp", "fence", "well", "stall", "barn",
                   "haystack", "sign", "swing", "slide", "goal", "hedge", "cactus", "umbrella"]


def _code_hats():
    try:
        from . import codedraw
        return [h for h in codedraw.wearables() if h not in HATS]
    except Exception:
        return []


def _picture_vehicles():
    from . import images
    return sorted(n for n, m in images.list_images().items() if (m or {}).get("kind") == "vehicle")


def base_species():
    custom = set(animals.CUSTOM)
    quads = [k for k in animals.QUADS if k not in custom]
    birds = [k for k in animals.BIRDS if k not in custom]
    return quads, birds


def options():
    reg = registry.load()
    quads, birds = base_species()
    return {
        "professions": sorted(PROFESSIONS),
        "outfits": sorted(k for k in OUTFITS if k != "none") + ["none"],
        "skins": list(SKIN), "hair": HAIRS, "hair_colors": list(dict.fromkeys(HAIR)), "hats": HATS + _code_hats(),
        "builds": ["slim", "normal", "strong", "chubby"], "ages": ["baby", "toddler", "child", "teen", "adult", "old"],
        "species": quads + ["monkey"] + birds, "species_quads": quads, "species_birds": birds,
        "custom_species": sorted(animals.CUSTOM),
        "ears": EARS, "tails": TAILS, "patterns": PATTERNS,
        "places": sorted(set(PRESETS)), "custom_places": sorted(reg["places"]),
        "seasons": list(SEASONS), "regions": list(REGIONS), "moods": list(MOODS), "landmarks": list(LANDMARKS),
        "water": list(WATER_KINDS), "weather": WEATHER, "times": TIMES,
        "vehicles": sorted(VEHICLES),
        "picture_vehicles": _picture_vehicles(), "props": list(PROP_TYPES), "effects": EFFECTS, "icons": ICONS,
        "emotions": EMOTIONS, "cameras": CAMERAS, "music": MUSIC, "sfx": SFX,
        "skies": list(SKY_LOOKS), "clouds": list(CLOUD_STYLES),
        "trees": ["round", "pine", "palm", "banyan", "mango", "coconut", "banana_tree", "acacia", "cactus_tree", "bare",
                  "blossom", "mushroom_tree"] + list(MORE_TREES),
        "actions_human": [a for a in ACTIONS if a not in ("appear", "disappear", "perch", "step_up", "hop_down",
                                                          "smash", "sit_on", "push", "pull", "throw", "climb",
                                                          "hide", "peek", "open", "stumble")],
        "actions_animal": list(animals.Q_ACTIONS), "actions_bird": list(animals.B_ACTIONS),
        "indoor_objects": INDOOR_OBJECTS, "outdoor_objects": OUTDOOR_OBJECTS,
        "custom_characters": {k: _describe_char(v) for k, v in reg["characters"].items()},
        "custom_species_desc": dict(animals.CUSTOM),
        "custom_places_desc": {k: v.get("description", v.get("preset", "")) for k, v in reg["places"].items()},
    }


def _describe_char(spec):
    bits = [spec.get("name", "")]
    if spec.get("species") and spec["species"] != "human":
        bits.append(spec["species"])
    for k in ("profession", "age", "gender"):
        if spec.get(k):
            bits.append(str(spec[k]))
    if spec.get("description"):
        bits.append(spec["description"])
    if spec.get("look"):
        bits.append(f"wears puppet look {spec['look']}")
    return ", ".join(b for b in bits if b)
