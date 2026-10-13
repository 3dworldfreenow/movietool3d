"""Talked-about things that are not there.

A line like  "Dadi, have this cup of tea"  or  "yeh chai le lo"  needs a cup in the scene - best in the
speaker's hand. This check reads every "say" / "narrate" line of every scene (English, Hindi, Hinglish) and
reports:

  missing      the line talks about a thing (cup, ball, kite, phone ...) and the scene has no such thing at all
  not_in_hand  the speaker says "this cup" / "yeh kap" / "le lo" but nobody near them is holding one

Every problem comes with a ready fix (a "props" entry, held by the speaker) that fix() writes into the story.

    python main.py validate story.json      # problems are shown in RED
    python main.py validate story.json --fix-objects   # also writes the fixes into the JSON
"""
import copy
import re

# thing -> words that name it (lower case; Devanagari, Hinglish and English). The key is the prop type used in a fix.
THINGS = {
    "cup": ["cup", "cups", "teacup", "tea cup", "mug", "kap", "कप", "pyala", "pyaala", "प्याला", "kulhad", "kullad",
            "कुल्हड़"],
    "glass": ["glass of", "a glass", "the glass", "this glass", "gilaas", "gilas", "glass", "गिलास"],
    "plate": ["plate", "thali", "थाली", "plet", "प्लेट"],
    "ball": ["ball", "balls", "gend", "gaind", "गेंद", "बॉल"],
    "kite": ["kite", "patang", "पतंग"],
    "book": ["book", "books", "kitab", "kitaab", "किताब", "pustak", "पुस्तक", "copy", "notebook", "कॉपी"],
    "phone": ["phone", "mobile", "cellphone", "फ़ोन", "फोन", "मोबाइल"],
    "bag": ["bag", "bags", "jhola", "thaila", "थैला", "झोला", "बैग", "basta", "बस्ता"],
    "umbrella": ["umbrella", "chhata", "chhatri", "छाता", "छतरी"],
    "letter": ["letter", "chitthi", "chithi", "चिट्ठी", "patra", "पत्र", "envelope"],
    "stick": ["stick", "lathi", "लाठी", "danda", "डंडा", "cane"],
    "apple": ["apple", "apples", "seb", "सेब"],
    "flower": ["flower", "flowers", "phool", "फूल", "rose", "gulab", "गुलाब"],
    "gift": ["gift", "present", "tohfa", "तोहफ़ा", "तोहफा", "uphaar", "उपहार"],
    "box": ["box", "dibba", "dabba", "डिब्बा", "sandook", "संदूक"],
    "balloon": ["balloon", "gubbara", "गुब्बारा"],
    "pot": ["pot", "matka", "मटका", "ghada", "घड़ा", "gagri", "गगरी"],
    "lamp": ["lamp", "deepak", "दीया", "दीपक", "lantern", "lalten", "लालटेन"],
    "sword": ["sword", "talwar", "तलवार"],
    "bow": ["bow and arrow", "dhanush", "धनुष", "arrow", "baan", "बाण", "teer", "तीर"],
    "bucket": ["bucket", "balti", "बाल्टी"],
    "basket": ["basket", "tokri", "टोकरी"],
    "key": ["key", "keys", "chabi", "chaabi", "चाबी"],
    "rope": ["rope", "rassi", "रस्सी"],
    "mango": ["mango", "mangoes", "aam", "आम"],
    "banana": ["banana", "bananas", "kela", "केला"],
    "sweets": ["laddoo", "laddu", "लड्डू", "mithai", "मिठाई", "sweets", "jalebi", "जलेबी"],
    "money": ["money", "coin", "coins", "rupees", "paisa", "paise", "पैसे", "सिक्का"],
    "bottle": ["bottle", "botal", "बोतल"],
    "hat": ["hat", "cap", "topi", "टोपी"],
    "crown": ["crown", "mukut", "मुकुट"],
    "ring": ["ring", "anguthi", "अंगूठी"],
    "pen": ["pen", "pencil", "कलम", "पेन"],
}
# words that are only a thing when pointed at: "chai" alone may just be the drink ("chalo chai peene")
POINTED = {"cup": ["tea", "chai", "चाय", "coffee", "कॉफ़ी"], "glass": ["water", "paani", "pani", "पानी", "lassi",
                                                                  "लस्सी", "milk", "doodh", "दूध"]}
# "this / here / take" words - the thing should be in (or next to) the speaker's hand
DEICTIC = ["this", "these", "here's", "here is", "take", "have this", "my", "yeh", "ye", "yah", "ise", "isko", "lo",
           "le lo", "lijiye", "lijie", "le lijiye", "pakdo", "pakad", "mera", "meri", "mere", "यह", "ये", "इसे",
           "लो", "ले लो", "लीजिए", "लीजिये", "पकड़ो", "मेरा", "मेरी", "मेरे"]
# words where a thing-word means something else: skip the match
NOT_A_THING = {"key": ["key point", "key to", "key idea"], "ball": ["ball game"], "copy": ["copy me", "copy that"],
               "present": ["present here", "at present", "the present"], "ring": ["ring the", "ring ring"],
               "cap": ["cap on"], "bow": ["take a bow", "bow down"], "pen": ["open"], "hat": ["that", "what"],
               "aam": ["aam aadmi", "aam log"], "lo": []}
# a line about a thing being GONE / lost / wished for / "if I had" does not need it in the scene
ABSENT = ["gone", "lost", "missing", "forgot", "forget", "where is", "where's", "where are", "where did", "where do", "stolen", "stole",
          "if i", "if you", "if we", "imagine", "no more", "don't have", "do not have", "wish", "want a", "buy",
          "kahan", "kahaan", "gum ho", "kho gaya", "kho gayi", "chori", "bhool", "agar", "nahi hai", "nahin hai",
          "कहाँ", "कहां", "खो", "गुम", "चोरी", "भूल", "अगर", "नहीं है", "नही है", "चाहिए", "खरीद"]
NEAR = 260.0     # story units: "next to" the speaker (an adult is 300 tall)


def _texts(v):
    """Every language's text of a "say" / "narrate" value."""
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [x for x in v.values() if isinstance(x, str)]
    if isinstance(v, list):
        return [x for y in v for x in _texts(y)]
    return []


def _has_word(text, w):
    """Whole-word match (works for Devanagari too: no letter / matra right before or after)."""
    pat = r"(?<![\wऀ-ॿ])" + re.escape(w) + r"(?![\wऀ-ॿ])"
    return re.search(pat, text) is not None


def _found(text, key):
    low = text.lower()
    for w in THINGS[key]:
        if _has_word(low, w) and not any(n in low for n in NOT_A_THING.get(w, [])):
            return w
    return None


def _pointed(text):
    low = text.lower()
    return any(_has_word(low, d) for d in DEICTIC)


def _names_of(entry):
    """Every name a prop / object / place thing goes by (id, type, picture)."""
    out = []
    if isinstance(entry, str):
        out.append(entry)
    elif isinstance(entry, dict):
        for k in ("id", "type", "image", "what", "name"):
            if isinstance(entry.get(k), str):
                out.append(entry[k])
    return [n.lower() for n in out]


def _matches(name, key):
    parts = re.split(r"[_\-\s]+", name.lower())
    words = [key] + [w for w in THINGS[key] if " " not in w]
    return any(w in parts or name.lower() == w for w in words)


def _place_things(bg):
    """Names of the things drawn in the scene's place (a code place: diya_left, singhasan, tea_stall ...)."""
    preset = bg.get("preset") if isinstance(bg, dict) else bg
    if not isinstance(preset, str):
        return []
    try:
        import os
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src = open(os.path.join(here, "assets", "code", preset + ".py"), encoding="utf-8").read()
    except OSError:
        return [preset.lower()]
    return [preset.lower()] + [m.lower() for m in re.findall(r"thing\(\s*[\"']([^\"']+)", src)]


def _no_names(text, names):
    """the text with the characters' names taken out (a hero called Deepak, Diya or Kamal is a person, not a
    lamp or a lotus)"""
    if not names:
        return text
    return re.sub(r"\b(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b", " ",
                  text, flags=re.I)


def check(story):
    """All talked-about-but-missing things in a story dict: a list of problems (dicts)."""
    probs = []
    names_ = set()                                     # the characters' names: never read as things
    for cid, cs in (story.get("characters") or {}).items():
        for n in [cid] + ([cs.get("name")] if isinstance(cs, dict) and cs.get("name") else []):
            names_.update(w for w in re.split(r"[\s_]+", str(n).lower()) if len(w) > 2)
    for si, sc in enumerate(story.get("scenes") or []):
        if not isinstance(sc, dict):
            continue
        present = []                                   # (names, holder or None, x)
        for k in ("props", "objects"):
            for p in sc.get(k) or []:
                present.append((_names_of(p), p.get("held_by") if isinstance(p, dict) else None,
                                p.get("x") if isinstance(p, dict) else None))
        things_ = {cid: (cs or {}).get("thing") for cid, cs in (story.get("characters") or {}).items()
                   if isinstance(cs, dict) and (cs or {}).get("thing")}
        for c in sc.get("characters") or []:
            if isinstance(c, dict):
                if things_.get(c.get("id")):            # ✏ a talking thing (the sketch look): the stick, the fire ...
                    present.append(([str(things_[c["id"]]).lower(), str(c.get("id")).lower()], None, c.get("x")))
                for k in ("holding", "hold", "prop", "carry"):
                    if c.get(k):
                        present.append((_names_of(c[k]), c.get("id"), None))
        for n in _place_things(sc.get("background")):
            present.append(([n], None, None))
        for e in sc.get("events") or []:                # ⚛ experiments bring their own balls, stones, carts ...
            if isinstance(e, dict) and ("experiment" in e or (e.get("do") in ("throw", "drop") and
                                                               any(k in e for k in ("angle", "speed", "from")))):
                words = ["ball", "stone", "feather", "box", "block", "cart", "weight", "bucket", "rope", "spring",
                         "prism", "mirror", "water", "boat", "coin", "pendulum", "swing", "slope", "ramp",
                         "balloon", "egg", "bulb", "battery", "cell", "wire", "switch", "magnet", "compass", "nail",
                         "pin", "pins", "clay", "tank", "ruler", "bell", "jar", "moon", "sun", "earth", "cloud", "rod",
                         "pot", "can", "wall", "ship", "gun", "bullet", "scale", "balance", "dam", "turbine",
                         "lamp", "candle", "lens", "glass", "plank", "see-saw", "wheel", "wheels"]
                words += ["ring", "disc", "car", "train", "trains", "satellite", "station", "tea", "cup", "ice",
                          "steam", "needle", "horn", "fork", "forks", "door", "top", "wing", "rail", "rails", "strip",
                          "boat", "piston", "engine", "string", "drum", "tray", "plate", "planet", "star"]
                try:                                     # + the words of the experiment's own title
                    from . import physics as _ph
                    k_ = _ph.kind_of(e.get("experiment"))
                    if k_:
                        words += re.findall(r"[a-z]+", _ph.EXPERIMENTS[k_].title.lower())
                except Exception:                        # noqa: BLE001
                    pass
                for k in ("objects", "balls", "surfaces", "what"):
                    v = e.get(k)
                    words += [w.strip() for w in (v if isinstance(v, list) else str(v or "").split(",")) if w.strip()]
                present.append((words, None, e.get("x")))
        xs = {c.get("id"): c.get("x") for c in sc.get("characters") or [] if isinstance(c, dict)}
        story_props = []                               # made on the way ("pick" a "prop" that the engine adds)
        seen = set()
        for ei, e in enumerate(sc.get("events") or []):
            if not isinstance(e, dict):
                continue
            for k in ("prop", "object"):
                if isinstance(e.get(k), str):
                    story_props.append(([e[k].lower()], e.get("who") if e.get("do") in ("pick", "pick_up", "take",
                                                                                          "carry", "hold") else None))
            who = e.get("who") or ("narrator" if "narrate" in e else None)
            for field in ("say", "narrate"):
                vals = [e.get(field)] + [v for k, v in e.items() if isinstance(k, str) and k.startswith(field + "_")]
                for text in _texts(vals):
                    text = _no_names(text, names_)              # "Deepak" the man is not a deepak (lamp)
                    if any(_has_word(text.lower(), a) or (" " in a and a in text.lower()) for a in ABSENT):
                        for key in THINGS:                 # talked about as gone / imagined: later lines about
                            if _found(text, key):          # it in this scene are the same story ("twelve mangoes!")
                                seen.update({(si, key, "missing"), (si, key, "hand")})
                        continue
                    for key in THINGS:
                        word = _found(text, key)
                        if word is None and key in POINTED and _pointed(text):
                            low = text.lower()
                            word = next((w for w in POINTED[key] if _has_word(low, w)), None)
                        if word is None:
                            continue
                        have = [p for p in present if any(_matches(n, key) for n in p[0])] + \
                               [(n, h, None) for n, h in story_props if any(_matches(x, key) for x in n)]
                        line = {"scene": si, "scene_id": sc.get("id", f"scene {si + 1}"), "event": ei, "who": who,
                                "text": text, "word": word, "thing": key}
                        if not have:
                            if (si, key, "missing") in seen:
                                continue
                            seen.add((si, key, "missing"))
                            holder = who if who and who != "narrator" and field == "say" else None
                            probs.append(dict(line, kind="missing", fix=_fix_for(sc, key, holder, xs)))
                        elif field == "say" and who and _pointed(text):
                            held = [p for p in have if p[1] is not None]
                            near = [p for p in have if p[1] is None and isinstance(p[2], (int, float)) and
                                    isinstance(xs.get(who), (int, float)) and abs(p[2] - xs[who]) <= NEAR]
                            if not held and not near and (si, key, "hand") not in seen:
                                seen.add((si, key, "hand"))
                                ex_ = next((q.get("id") for q in (sc.get("props") or []) if isinstance(q, dict)
                                            and any(_matches(n, key) for n in _names_of(q))), None)
                                probs.append(dict(line, kind="not_in_hand", existing=ex_,
                                                  fix=_fix_for(sc, key, who, xs)))
    return probs


# things with no picture of their own yet: drawn as the nearest built-in prop (make a picture with the real
# name - e.g. assets/images/glass.png - and it is used instead)
LOOKS_LIKE = {"glass": "cup", "plate": "box", "sweets": "box", "money": "letter", "basket": "bag", "bucket": "pot",
              "bottle": "cup", "key": "stick", "rope": "stick", "pen": "stick", "sword": "stick", "bow": "stick",
              "lamp": "pot", "mango": "apple", "banana": "apple", "hat": "bag", "crown": "gift", "ring": "gift"}


def _drawable(key):
    try:
        from . import images, objects
        from .props import PROP_TYPES
        if key in PROP_TYPES or key in objects.BUILTIN or images.exists(key):
            return key
    except Exception:
        pass
    return LOOKS_LIKE.get(key, key)


def _fix_for(sc, key, holder, xs):
    ids = {p.get("id") for k in ("props", "objects") for p in (sc.get(k) or []) if isinstance(p, dict)}
    pid, n = key, 2
    while pid in ids:
        pid, n = f"{key}_{n}", n + 1
    prop = {"id": pid, "type": _drawable(key)}
    if holder:
        prop["held_by"] = holder
    else:
        x = next((v for v in xs.values() if isinstance(v, (int, float))), 800)
        prop["x"] = x + 120
    return {"scene": None, "add_prop": prop}


def message(p):
    where = f"scene {p['scene'] + 1} ({p['scene_id']}), event {p['event'] + 1}"
    say = p["text"] if len(p["text"]) <= 70 else p["text"][:67] + "..."
    fx = p["fix"]["add_prop"]
    if p["kind"] == "missing":
        return (f"MISSING OBJECT - {where}: \"{say}\" talks about '{p['word']}' but there is no {p['thing']} in the "
                f"scene. Fix: add to this scene's \"props\": {_j(fx)}")
    if p.get("existing"):
        how = f"give it to them - add \"held_by\": \"{p['who']}\" to the '{p['existing']}' prop"
    else:
        how = f"add to this scene's \"props\": {_j(fx)}"
    return (f"NOT IN HAND - {where}: {p['who']} says \"{say}\" but is not holding the {p['thing']} "
            f"(and it is not next to them). Fix: {how} (or walk to it and \"pick\" it first)")


def _j(d):
    import json
    return json.dumps(d, ensure_ascii=False)


def fix(story, probs=None, only=None):
    """A copy of the story with the fixes written in (only = indexes into probs to apply)."""
    story = copy.deepcopy(story)
    probs = check(story) if probs is None else probs
    for i, p in enumerate(probs):
        if only is not None and i not in only:
            continue
        sc = story["scenes"][p["scene"]]
        prop = dict(p["fix"]["add_prop"])
        lst = sc.setdefault("props", [])
        if p["kind"] == "not_in_hand":                 # the thing is there: hand it to the speaker
            for q in sc.get("props") or []:
                if isinstance(q, dict) and any(_matches(n, p["thing"]) for n in _names_of(q)) and not q.get("held_by"):
                    q["held_by"] = prop["held_by"]
                    q.pop("x", None)
                    q.pop("y", None)
                    break
            else:
                lst.append(prop)
        elif not any(isinstance(q, dict) and q.get("id") == prop["id"] for q in lst):
            lst.append(prop)
    return story
