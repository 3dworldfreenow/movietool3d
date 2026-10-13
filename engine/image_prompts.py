"""Image prompt builder: writes prompts for AI image tools (ChatGPT / Gemini / Leonardo / Midjourney / Kling ...)
that follow the engine's rules, so every generated picture drops straight into the Studio and "just works":

  * backgrounds: 16:9, the floor line where characters stand at ~80 % height, open walkable ground in the middle,
    big things only at the sides, no people / animals / text
  * objects and props: one complete object, straight side-front view, isolated on pure white (easy to cut out),
    standing on its base, no ground and no shadow
  * the same house style every time (flat cartoon with soft shading, light from the top right)

It also returns the settings to type in the upload form: name, "mainly used as", height, floor line,
abilities (what characters can do with it) and a description for the AI story writer.
"""
import re

STYLES = {
    "cartoon": "2D cartoon illustration for a children's animated series, flat vector style with soft shading, "
               "clean shapes, bright friendly colours, light coming from the top right",
    "painted": "2D cartoon background painting like a modern animated film, soft painterly shading, rich colours, "
               "gentle atmospheric depth, light coming from the top right",
    "photo": "realistic photograph, natural light, sharp focus",
}
NO_JUNK = "no people, no animals, no characters, no text, no letters, no logo, no watermark, no frame, no border"

# typical sizes in engine units (an adult is ~300 tall)
SIZES = [
    (("log", "tree trunk"), 90), (("banyan", "huge tree", "giant tree", "big tree"), 900), (("palm",), 650), (("tree",), 650),
    (("house", "temple", "shop", "building", "hut"), 450), (("statue", "idol"), 350), (("tower",), 900),
    (("waterfall",), 500), (("well",), 170), (("cart", "bullock cart"), 200), (("boat",), 150),
    (("big rock", "boulder", "large rock"), 230), (("rock",), 130), (("stone", "pebble"), 32),
    (("log", "tree trunk"), 90), (("bush", "shrub"), 150), (("fern", "plant"), 120), (("flower",), 45),
    (("chest", "treasure box", "trunk box"), 95), (("crate", "box"), 80), (("pot", "matka", "vase", "jar"), 60),
    (("bench",), 110), (("chair",), 120), (("table",), 110), (("lamp", "lantern"), 60), (("torch",), 70),
    (("ball",), 30), (("bag",), 50), (("book",), 25), (("bucket",), 45), (("drum", "dhol"), 60),
    (("fire", "campfire"), 110), (("flag",), 380), (("sign", "signboard"), 200), (("ladder",), 320),
    (("gate", "door"), 320), (("fence",), 110), (("bridge",), 150), (("car",), 200), (("bike", "cycle"), 180),
]

# what characters can do with it (see engine/objects.py)
ABILITY_WORDS = [
    (("stone", "pebble"), ["movable", "light", "round", "throw", "sinks"]),
    (("big rock", "boulder", "large rock"), ["movable", "heavy", "round", "sit", "stand", "hide"]),
    (("rock",), ["movable", "heavy", "sit", "stand", "hide"]),
    (("log", "tree trunk"), ["movable", "heavy", "sit", "stand", "floats"]),
    (("chest", "treasure", "box", "crate"), ["movable", "open", "sit", "stand"]),
    (("pot", "matka", "vase", "jar"), ["movable", "light", "break", "throw"]),
    (("ball",), ["movable", "light", "round", "throw", "floats"]),
    (("banyan", "tree", "palm"), ["climb", "hide"]),
    (("bush", "shrub", "haystack", "cart", "wall"), ["hide"]),
    (("bench", "chair", "stool"), ["movable", "sit"]),
    (("lamp", "lantern", "torch", "diya", "candle"), ["movable", "light", "switch"]),
    (("campfire", "fire", "stove", "tv", "radio"), ["switch"]),
    (("bucket", "bag", "basket", "book", "drum", "dhol"), ["movable", "light", "throw"]),
    (("ladder",), ["movable", "climb"]),
    (("boat",), ["floats", "sit"]),
]
ABILITIES = ["movable", "light", "heavy", "round", "throw", "sit", "stand", "climb", "hide", "open", "break",
             "floats", "sinks", "switch"]

KINDS = {
    "background": "Background scene (the place where the story happens)",
    "backdrop": "Far backdrop (mountains / city / sea far away)",
    "object": "Object that stands in the scene (tree, rock, house, statue ...)",
    "prop": "Small prop characters hold (pot, torch, ball, bag ...)",
    "animated": "Moving object (fire, waterfall, flag - GIF / short clip)",
    "picture": "Picture moment (full-screen illustration)",
}


def slug(text, n=32):
    s = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    return s[:n] or "picture"


def _match(subject, phrases):
    """True if every word of one of the phrases appears in the subject ("big mossy rock" matches "big rock")."""
    words = set(re.findall(r"[a-z]+", subject.lower()))
    for ph in phrases:
        need = ph.split()
        if all(any(w == n or w == n + "s" or w == n + "es" for w in words) for n in need):
            return True
    return False


def _size(subject):
    for words, h in SIZES:
        if _match(subject, words):
            return h
    return 200


def _abilities(subject):
    for words, ab in ABILITY_WORDS:
        if _match(subject, words):
            return list(ab)
    return []


def build(kind="background", subject="", place="", time="day", season="", style="cartoon", extra="", india=True):
    """Returns {prompt, tips[], upload{name, kind, height, ground, abilities, description}}."""
    kind = kind if kind in KINDS else "background"
    subject = (subject or "").strip()
    place = (place or "").strip()
    st = STYLES.get(style, STYLES["cartoon"])
    when = {"morning": "early morning, soft golden light", "day": "bright daylight", "sunset": "sunset, warm orange sky",
            "evening": "evening, soft purple sky", "night": "night, moonlight, dark blue sky with stars"}.get(time, time)
    seas = f", {season} season" if season else ""
    region = " in India" if india and style != "photo" else ""
    extra_s = f" {extra.strip().rstrip('.')}." if extra.strip() else ""
    up = {"kind": kind if kind in ("object", "prop", "background", "picture") else
          ("object" if kind == "animated" else "background"),
          "name": slug(subject or place or kind), "height": None, "ground": None, "abilities": [],
          "description": ""}
    tips = []
    if kind == "background":
        what = subject or place or "village"
        prompt = (f"{st}. A wide 16:9 background scene of {what}{region}, {when}{seas}.{extra_s} "
                  "Layout rules: the flat open ground where characters stand is at about 80% of the image height "
                  "and runs across the whole width; the middle 60% of the ground is EMPTY (only a path or grass, "
                  "no objects on it); big trees, buildings and rocks only near the left and right edges; the horizon "
                  "at about 45% height with distant hills or trees; the top part is open sky. Straight-on eye-level "
                  f"view, not from above. 1920x1080. {NO_JUNK}.")
        up.update(ground=0.80, description=f"{what}{', ' + time if time else ''} background")
        tips = ["If the characters float or sink when you preview it, change the floor line (0.75 - 0.88).",
                "Keep the middle ground empty - characters stand and walk there.",
                "After upload the Studio turns it into 🧊 2.5D depth layers (Depth Anything V2): with "
                "\"camera_mode\": \"3d\" the camera moves through your picture with real parallax."]
    elif kind == "backdrop":
        what = subject or "distant green hills and blue mountains"
        prompt = (f"{st}. A very wide panoramic backdrop of {what}{region}, {when}{seas}.{extra_s} Everything is FAR "
                  "away: soft hazy colours, low contrast, no foreground objects, the bottom quarter is a soft hazy "
                  f"line of distant trees, the top half is sky. 21:9, 2560x1080. {NO_JUNK}.")
        up.update(kind="background", ground=0.9, description=f"far backdrop: {what}")
        tips = ["Use it as \"background\": {\"image\": name} for wide, calm establishing shots."]
    elif kind in ("object", "prop", "animated"):
        what = subject or ("big mossy rock" if kind == "object" else "clay pot")
        base = (f"A single {what}, {st}. The complete object from top to bottom, straight side-front view at eye "
                "level, standing upright on its flat base, centred, filling about 80% of the image height, "
                "isolated on a plain PURE WHITE background, no ground, no shadow, no other objects, thick clean "
                f"outline so it is easy to cut out.{extra_s} Square 1:1, 1024x1024. {NO_JUNK}.")
        if kind == "animated":
            prompt = (base.replace("A single", "A short seamless looping animation of a single") +
                      " Animation: 2 seconds, seamless loop (the last frame matches the first), the object stays in "
                      "the same place, only its own motion (flames flicker / water flows / cloth waves). Export as GIF, "
                      "animated WebP or MP4.")
            tips = ["Image tools: make the still first, then animate it in a video tool (Kling, Runway, Pika, "
                    "Luma) with 'seamless loop, camera fixed, white background'.",
                    "Keep the white background: the Studio makes it transparent when you upload (GIF / WebP / "
                    "MP4)."]
        else:
            prompt = base
            tips = ["No need to cut it out yourself: the Studio removes the white background when you upload "
                    "(✂ Make transparent)."]
        up.update(kind="prop" if kind == "prop" else "object", height=_size(what), abilities=_abilities(what),
                  description=what + (" (animated)" if kind == "animated" else ""))
        tips.append("Height is in story units: an adult is about 300, a child 245.")
    else:  # picture moment
        what = subject or place or "a beautiful Indian landscape"
        prompt = (f"{st}. A beautiful full-screen illustration of {what}{region}, {when}{seas}.{extra_s} Cinematic "
                  f"composition, storybook feeling, 16:9, 1920x1080. {NO_JUNK}.")
        up.update(kind="picture", description=what)
        tips = ["Show it with {\"picture\": name, \"caption\": \"...\", \"duration\": 4}."]
    tips.append("Always keep the same style words in every prompt so all your pictures look like one family.")
    return {"prompt": prompt, "tips": tips, "upload": up}
