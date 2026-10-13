"""🧊 The Stick 3D prompt: only what the Stick 3D renderer draws (not the 2D pictures, planets, physics lessons ...).

The lists in it (places with their spots and cameras, vehicles, screens, actions, props, sounds, weather) are read
from the engine each time, so a new place or camera shows up in the prompt by itself. It makes the AI the DIRECTOR
of every scene: each scene names its place, its spot, its camera, where everyone stands and what moves, so the
story renders right the first time. check(story) finds the scenes that would not.
"""
import json

_PLACES = {}                                     # name -> (one line, spots, shots): built once (~2 s for all)
LINES = {"village": "a small Indian village around an open square (huts, houses, trees, a well)",
         "village_2030": "the same village in 2030 under a white-hot UV sky: dry, cracked, shaded, people in masks",
         "texas_lab": "Mark's research office in Texas (desk, monitors, a flag): the other end of a phone call",
         "panama_office": "a research office in Panama: the other end of a phone call"}

INTRO = """You are the writer AND the director of a short film made in STICK 3D: flat-colour cartoon stick people
(round heads, faces that act, clothes in their colours) in real-size 3D places, filmed like a movie (2.39 widescreen,
film grain, a colour grade per beat, real voices, sound effects, weather). Answer with ONE JSON object only - no
words before or after it, no comments, no trailing commas."""

SKELETON = {
    "title": "The Last Signal",
    "settings": {"art": "stick3d", "stick_look": "flat", "stick_cinema": True, "language": "en-IN",
                 "music": "mystery", "subtitle": "Episode 1"},
    "characters": {
        "deepak": {"name": "Deepak", "shirt": "#4f9aad", "pants": "#36435f", "cap": True, "cloth": "#1e2125",
                   "voice": {"name": "en-IN-PrabhatNeural"}},
        "mark": {"name": "Dr. Mark Ellis", "skin": "light", "shirt": "#f2c230", "hood": "rain", "cloth": "#f2c230",
                 "to_camera": True, "voice": {"name": "en-US-GuyNeural"}}},
    "scenes": [
        {"id": "s1_station", "stick_place": "corn_field", "stick_spot": "station", "stick_shot": "station_close",
         "stick_time": "morning", "mood": "monsoon", "transition": "cut",
         "characters": [{"id": "deepak", "x": 960, "z": 120}, {"id": "mark", "x": -900, "hidden": True}],
         "props": [{"id": "phone", "type": "phone", "held_by": "deepak"}],
         "stick_cars": [{"id": "truck", "kind": "pickup", "color": "#e6e4dc", "mud": True,
                         "to": {"x": 200, "z": -39}, "heading": 0}],
         "events": [{"weather": "rain", "over": 0, "react": False},
                    {"who": "deepak", "do": "look_down"},
                    {"who": "deepak", "say": "Battery full... all readings normal.", "emotion": "happy"},
                    {"sound": "phone"},
                    {"who": "deepak", "say": "Mark? It's six in the morning in Texas...", "emotion": "surprised"}]},
        {"id": "s2_call", "transition": "cut", "mood": "tense", "tail": 0.1,
         "characters": [{"id": "deepak", "x": -900, "hidden": True}],
         "stick_screen": {"kind": "call", "name": "Mark Ellis", "from": "Galveston, Texas", "answer_at": 0.8},
         "events": [{"wait": 1.4}]}]}

DIRECTOR = """HOW TO DIRECT EVERY SCENE (follow all of these - a scene that breaks one renders wrong)
1. Every scene that is not a screen insert names: "stick_place" (one of PLACES), "stick_spot" (a spot OF THAT
   place), "stick_shot" (a camera OF THAT place, or [[eye x, y, z], [look x, y, z]] in metres from the spot),
   "mood" and "stick_time" when it matters. Never use a spot or shot from another place.
2. Positions are STAGE units around the spot: "x" 960 = on the spot (1 m = 190 sideways), "z" 120 = on the spot
   (1 m = 211 deeper; bigger z = further from the camera, 0..3000). Put the people the shot is about within
   x 700-1250, z 60-400. People who are only a voice (a phone call): {"id": "...", "x": -900, "hidden": true}.
3. List EVERY character who is in the scene in its "characters" (also the hidden voices). A character that is not
   listed is not there. Props held from an earlier scene are carried by themselves - declare a prop only once.
4. Cars, trucks, helicopters are NOT remembered between scenes: put "stick_cars" in every scene they are in
   (a parked one: only "to" + "heading"). A moving one: "from", "to", "start", "end" (seconds).
5. One scene = one shot idea, 2-8 seconds. Cut often. A screen insert (phone, map, CSV, news) is 1-2 s:
   "events": [{"wait": 1.5}] and "tail": 0.1. Do not hold a shot with nothing new in it.
6. Dialogue: short lines (max ~16 words), each with "emotion". Put feeling in the punctuation (... ?! —) - the
   voices read it. Lines are the film's sound: no narrator unless asked.
7. Weather is set in each scene's events FIRST: {"weather": "rain", "over": 0, "react": false} ("over": 0 = it is
   already like that at the cut; a number = it changes over that many seconds).
8. Use the mood list for the colour of each beat; keep one place in one mood so the cut does not jump in colour.
9. Every "do" must be an action from ACTIONS, every "kind" from its list, every "sound" from SOUNDS.
10. Make it a FILM: establish (wide / aerial), then closer, reaction shots, an insert of what they see, a strong
    last image. A talking scene: let the camera find the faces (no "stick_shot") or name a close camera.
11. Physics is real unless the story needs a cheat: wind rocks cars and throws small things, it does not lift
    cars; people lean into a gale; rain wets the ground; night needs lights."""

FIELDS = """SCENE FIELDS (Stick 3D only)
  "stick_place", "stick_spot", "stick_shot", "stick_shot_hold": true (keep that one camera - a TV news camera)
  "stick_time": {times}
  "mood": the beat's colour grade + music: {moods}
  "transition": "cut"     "tail": seconds of picture after the last event (default 1.2; 0.1 for inserts)
  "characters": [{{"id", "x", "z", "hidden"}}]   "props": [{{"id", "type", "held_by" | "x", "z"}}]  prop types: {props}
  "stick_cars": [{{"id", "kind", "color" (name or #hex), "from", "to", "start", "end", "heading", "path": [{{x, z}}],
                 "rider": "<character id>", "lights": bool, "mud": bool, "door": [open s, close s],
                 "fly": {{"at": s, "rock": deg}} (a gust rocks a parked car), "alt": metres (helicopters)}}]
      kinds: {cars}
  "stick_follow": {{"car": id, "side": behind | side | front | drone | driver | profile | shoulder | pov | drone_behind}}
  "stick_screen": {{"kind": ...}} a full-frame insert instead of the 3D place: {screens}
  "stick_live": {{"channel", "name", "role", "place", "ticker", "fall_at": s}} - seen through a TV news camera
  "stick_hurricane": {{"eye": [0.5, 0.45], "size": 0.8, "glow": bool}} the storm's spiral in the sky
  "stick_debris": 0..1.5 (planks, tin, leaves flying)  "stick_panic": 1 (people screaming)  "stick_lens_rain": 1
  "stick_shake": [{{"start", "end", "amount"}}]  "stick_hail": {{"start", "end"}}  "stick_stormwall": {{"start", "end"}}
  "stick_blackout": {{"at": s}}  "stick_burnt": true  "stick_muddy": ["<id>", ...] (muddy shoes)
  "stick_bubbles": true (speech bubbles; default off - the voices speak)

EVENTS (run one after another; "at": s = at that second; "with": "prev" = together with the one before)
  {{"who", "say": "...", "emotion": {emotions}}}   (+ "voice_file", "from", "to" for a recorded take)
  {{"who", "do": "<action>", "to": {{"x", "z"}}, "target": "<id>", "prop": "<id>", "facing": "camera"}}
  {{"weather": {weathers} | {sequences}, "over": s, "react": false}}
  {{"effect": {effects}, "x", "z"}}     {{"sound": "<sound>"}}     {{"wait": s}}
  a child on a hip: {{"who": "kid", "do": "carried", "by": "<mother>", "on": "hip"}}

ACTIONS: {actions}

SOUNDS: {sounds}
  (a sound plays until its scene ends at most; {{"sound": "siren", "for": 4}} plays 4 s, "loop": true repeats a short
  one to fill that, "from_sec": 2 skips the file's start, "volume": 0.6, "carry": true lets it run into the next scene)

CHARACTER LOOKS (in "characters" at the top): "name", "gender": male | female, "age": child | toddler | adult | old,
  "skin": light | brown | dark, "shirt", "pants", "dress", "hair": short | bob | bunches, "hair_col", "cap": true,
  "hood": true | "rain" (a raincoat hood), "cloth" (cap / hood colour), "shades", "goggles", "mask", "mustache",
  "beard", "to_camera": true (a reporter who talks to the lens), "species": "dinosaur",
  🐄 ANIMALS (real shapes in ink lines, real size, in 3D like the T-rex): "species": one of {animals} - e.g. "moti": {{"name": "Moti", "species": "cow"}};
  they take "do" like people (walk, run, sit, lie, sleep, eat, jump, talk, wag, roar / moo / bark ...), and talk
  with "say" (a talking animal: a big open mouth); "size": 1.3 for a big one,
  "voice": {{"name": "en-IN-PrabhatNeural", "pitch": -4}}"""


def _places():
    if _PLACES:
        return _PLACES
    from . import stick3d as S
    from . import stick3d_places as P
    for name, make in S.PLACES.items():
        try:
            w = make()
        except Exception:
            continue
        fn = getattr(P, name, None) or (P.abroad_office if name in ("texas_lab", "panama_office") else None)
        doc = " ".join(((fn.__doc__ if fn else "") or "").split())
        line = LINES.get(name) or (doc.split(". ")[0][:220] if doc else name.replace("_", " "))
        _PLACES[name] = (line, list((getattr(w, "spots", None) or {}).keys()),
                         list((getattr(w, "shots", None) or {}).keys()))
    return _PLACES


def _lists():
    from . import poses, sfx, weatherline, stick3d_screens, stick3d_props, stick3d_animals
    from .stick3d import GRADES, MACHINES, HELIS
    acts = sorted(set(poses.ACTIONS) | {"say"} - {"say"})
    cars = ["car", "suv", "police", "agent", "pickup", "bike", "motorbike", "scooter"] + list(MACHINES) + \
        ["helicopter", "apache"]
    props = sorted({k for _, k in stick3d_props.WORDS})
    from .stick3d import TIMES
    return dict(times=" | ".join(TIMES), moods=" | ".join(GRADES), props=", ".join(props), cars=", ".join(cars),
                screens=", ".join(sorted(set(stick3d_screens.KINDS))),
                emotions="happy | sad | angry | scared | surprised | worried | excited | calm",
                weathers=" | ".join(weatherline.LEVELS), sequences=" | ".join(weatherline.SEQUENCES),
                effects="lightning | sparks | fire | smoke | explosion | dust | rocks",
                actions=", ".join(acts), sounds=", ".join(sorted(sfx.SFX)), helis=", ".join(HELIS),
                animals=", ".join(stick3d_animals.LIBRARY))


def places_block():
    out = ["PLACES (\"stick_place\") - each with its spots (\"stick_spot\") and cameras (\"stick_shot\"):"]
    for name, (line, spots, shots) in sorted(_places().items()):
        out.append(f"  {name}: {line}\n      spots: {', '.join(spots) or '(none - leave stick_spot out)'}"
                   f"\n      shots: {', '.join(shots) or '(none - let the camera find the faces)'}")
    return "\n".join(out)


def _compact(story):
    """the example JSON with one character / scene a line (short, still easy to read)"""
    d = lambda x: json.dumps(x, ensure_ascii=False)
    top = {k: v for k, v in story.items() if k not in ("characters", "scenes")}
    lines = ["{" + ", ".join(f"{d(k)}: {d(v)}" for k, v in top.items()) + ","]
    lines.append(' "characters": {')
    lines.append(",\n".join(f"  {d(k)}: {d(v)}" for k, v in story["characters"].items()))
    lines.append(" },")
    lines.append(' "scenes": [')
    lines.append(",\n".join("  " + d(sc) for sc in story["scenes"]))
    lines.append(" ]\n}")
    return "\n".join(lines)


def build(idea=None, notes=None):
    """the whole Stick 3D prompt; with an idea, the request at its end"""
    parts = [INTRO, DIRECTOR, places_block(), FIELDS.format(**_lists()),
             "A SHORT EXAMPLE (the shape, not the story to copy):\n" + _compact(SKELETON)]
    if notes:
        parts.append(str(notes))
    if idea:
        parts.append("THE IDEA:\n" + str(idea).strip() + "\n\nFirst invent the whole story (a hook, a problem, a "
                     "turn, a strong last image), then direct it scene by scene following HOW TO DIRECT EVERY SCENE. "
                     "Answer with the JSON only.")
    return "\n\n".join(parts)


def check(story):
    """the director's check of a Stick 3D story: [(scene number, problem)] for the things that would render wrong"""
    from . import poses
    probs = []
    places = _places()
    chars = set((story.get("characters") or {}).keys())
    acts = set(poses.ACTIONS) | set(getattr(poses, "ALIASES", {}))
    for i, sc in enumerate(story.get("scenes") or [], 1):
        if sc.get("stick_screen"):
            continue
        pl = sc.get("stick_place")
        if not pl:
            probs.append((i, 'no "stick_place"'))
        elif pl not in places:
            probs.append((i, f'unknown place "{pl}"'))
        else:
            _, spots, shots = places[pl]
            if sc.get("stick_spot") and sc["stick_spot"] not in spots:
                probs.append((i, f'spot "{sc["stick_spot"]}" is not in {pl} ({", ".join(spots)})'))
            sh = sc.get("stick_shot")
            if isinstance(sh, str) and sh not in shots:
                probs.append((i, f'shot "{sh}" is not in {pl} ({", ".join(shots)})'))
        listed = {c.get("id") for c in sc.get("characters") or [] if isinstance(c, dict)}
        for e in sc.get("events") or []:
            w = e.get("who")
            if w and w not in listed:
                probs.append((i, f'"{w}" acts but is not in the scene\'s "characters"'))
            if w and w not in chars and w not in listed:
                probs.append((i, f'"{w}" is not in the story\'s characters'))
            d = e.get("do")
            if d and d not in acts:
                probs.append((i, f'unknown action "{d}"'))
        for c in sc.get("characters") or []:
            if isinstance(c, dict) and not c.get("hidden") and float(c.get("z", 120)) > 3000:
                probs.append((i, f'"{c.get("id")}" stands at z {c.get("z")} (too far: 0..3000)'))
    return probs
