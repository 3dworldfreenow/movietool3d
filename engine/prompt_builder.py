"""Builds the story->JSON prompt from the live catalog (built-ins + your Studio assets + recent episodes).

The same text is used by Gemini, by the "Copy prompt" button (for ChatGPT etc.) and is written to
prompts/story_to_json_prompt.md whenever something changes - so all three are always in sync.
"""
import os

from . import catalog

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_FILE = os.path.join(HERE, "prompts", "story_to_json_prompt.md")
PLACEHOLDER = "<PASTE YOUR STORY HERE>"


def _j(items):
    return ", ".join(str(i) for i in items)


LIB_GROUPS = ("characters", "species", "places", "pictures", "kits", "puppets")


def library():
    """Everything from the user's library that can go into the prompt, for the "what Gemini gets" checkboxes."""
    o = catalog.options()
    from . import images, puppet, scene_kit
    out = {g: [] for g in LIB_GROUPS}
    for k, v in sorted(o["custom_characters"].items()):
        out["characters"].append({"id": k, "desc": v})
    for k, v in sorted(o["custom_species_desc"].items()):
        out["species"].append({"id": k, "desc": str(v)})
    for k, v in sorted(o["custom_places_desc"].items()):
        out["places"].append({"id": k, "desc": v})
    kit_pics = set()
    for kit in scene_kit.list_kits():
        st = scene_kit.status(kit)
        got = [st[p["name"]]["name"] for p in kit["pieces"] if st[p["name"]]["uploaded"]]
        if got:
            kit_pics.update(got)
            out["kits"].append({"id": kit["id"], "desc": f"{kit.get('title', '')} - {len(got)} pictures",
                                "pictures": got})
    for n, i in sorted(images.list_images().items()):
        if i.get("state_of") or i.get("part_of"):       # a state picture / a piece of a code place
            continue
        out["pictures"].append({"id": n, "desc": i.get("description") or i.get("kind") or "picture",
                                "kind": i.get("kind"), "in_kit": n in kit_pics})
    for p in puppet.list_puppets():
        if p["ready"]:
            out["puppets"].append({"id": p["name"], "desc": "front + back" if "head_front" in p["parts"] else "side"})
    return out


def _chooser(include):
    """include = {group: [ids]} - a group that is left out means 'all', an empty list means 'none'."""
    include = include if isinstance(include, dict) else {}

    def ok(group, name):
        sel = include.get(group)
        return sel is None or name in set(sel)
    return ok


def is_3d_world(world):
    return str(world or "").lower().split(":", 1)[0] in ("3d", "3d-first", "3d_first", "full3d")


def ride_vehicles_text():
    """The user's own vehicles that say how they are ridden (RIDE in their 3D code)."""
    from . import images
    how = {"pedal": "pedalled like a bicycle", "sit": "people sit on it", "stand": "people stand on it",
           "row": "rowed like a small boat"}
    rows = []
    for n, m in sorted(images.list_images().items()):
        r = (m or {}).get("ride")
        if (m or {}).get("kind") == "vehicle" and isinstance(r, dict):
            k = len(r.get("seats") or [0])
            rows.append(f"  - {n}: {k} seat{'s' if k != 1 else ''}, {how.get(r.get('pose'), 'people sit on it')}"
                        f"{', speed ' + str(int(r['speed'])) if r.get('speed') else ''} - {m.get('description', '')}")
    return "\n".join(rows)



def _physics_list():
    try:
        from .physics import describe
        return describe()
    except Exception:                                    # noqa: BLE001
        return ""

def build_prompt_text(recent=None, include=None, world=None):
    is3 = is_3d_world(world)
    o = catalog.options()
    from .objects import BUILTIN
    ok = _chooser(include)
    objs = "; ".join(f"{k} ({' '.join(v['traits'])})" for k, v in BUILTIN.items() if k != "experiment")
    custom_chars = {k: v for k, v in o["custom_characters"].items() if ok("characters", k)}
    custom_species = {k: v for k, v in o["custom_species_desc"].items() if ok("species", k)}
    custom_places = {k: v for k, v in o["custom_places_desc"].items() if ok("places", k)}
    o = dict(o)
    o["custom_species"] = [k for k in o["custom_species"] if ok("species", k)]
    rides = ride_vehicles_text()
    rides_block = ""
    if rides:
        rides_block = ("  YOUR RIDE VEHICLES (made in 3D - riders sit on its seats in order, the wheels stop when it "
                       "stops):\n" + rides + "\n"
                       '  ride it: { "who": "ravi", "do": "ride", "vehicle": "cycle1", "to": 1600 }   more riders: '
                       'the same "ride" (each takes the next seat)\n'
                       '  go on: { "who": "ravi", "do": "drive", "vehicle": "cycle1", "to": 2200 }   get down: '
                       '{ "who": "ravi", "do": "get_off" }')

    lib = []
    if custom_chars:
        lib.append("SAVED CHARACTERS (reuse them by id - just write \"<id>\": {} in \"characters\"):\n" +
                   "\n".join(f"  - {k}: {v}" for k, v in sorted(custom_chars.items())))
    if custom_species:
        lib.append("CUSTOM ANIMALS (use as \"species\"):\n" +
                   "\n".join(f"  - {k}: {v}" for k, v in sorted(custom_species.items())))
    if custom_places:
        def _p3(k):
            try:
                from . import registry as _rg
                sp = _rg.place(k) or {}
                th = [t.get("what") for t in (sp.get("things") or []) if isinstance(t, dict)]
                return any((images.info(w) or {}).get("is3d") for w in th[:3] if w)
            except Exception:
                return False
        from . import images
        lib.append("SAVED PLACES (use as background \"preset\"):\n" +
                   "\n".join(f"  - {k}{' [REAL 3D PLACE - use camera_mode 3d]' if _p3(k) else ''}: {v}"
                              for k, v in sorted(custom_places.items())))
    from . import images, scene_kit
    kit_rows, kit_pics = [], set()
    for kit in scene_kit.list_kits():
        if not ok("kits", kit["id"]):
            continue
        st = scene_kit.status(kit)
        bg = [st[p["name"]]["name"] for p in kit["pieces"] if p["role"] == "background" and st[p["name"]]["uploaded"]]
        ob = [st[p["name"]]["name"] for p in kit["pieces"] if p["role"] != "background" and st[p["name"]]["uploaded"]]
        if not bg and not ob:
            continue
        kit_pics.update(bg + ob)
        water = any(p.get("water") for p in kit["pieces"] if p["role"] == "background")
        kit_rows.append(f"  - {kit.get('title', kit['id'])}: background \"image\": \"{bg[0] if bg else '-'}\""
                        f"{' (has water)' if water else ''}; its objects: {', '.join(ob) or 'none'}")
    if kit_rows:
        lib.append("SCENE KITS (a background + objects drawn to match - use them TOGETHER in one scene: the background "
                   "as \"background\": {\"image\": ...} with \"camera_mode\": \"3d\", the objects in \"objects\"):\n" +
                   "\n".join(kit_rows))
    imgs = {n: i for n, i in images.list_images().items()
            if (ok("pictures", n) or n in kit_pics) and not i.get("state_of") and not i.get("part_of")}
    if imgs:
        rows = []
        for n, i in sorted(imgs.items()):
            use = {"object": "object in a scene", "prop": "prop", "background": "whole background",
                   "picture": "picture moment",
                   "vehicle": "vehicle: \"vehicles\": [{\"id\": \"v1\", \"type\": \"" + n + "\", \"x\": 1500}]"
                   }.get(i.get("kind"), "any use")
            if i.get("is3d"):
                use = "REAL 3D - " + use
            ab = i.get("abilities") or []
            from . import photodepth
            d3 = ", has depth layers - works as a 3D background" if photodepth.status(n) else ""
            rows.append(f"  - {n}: {i.get('description') or 'picture'} ({use}"
                        f"{', transparent' if i.get('has_alpha') else ''}"
                        f"{', OBJECT that can: ' + ' '.join(ab) if ab else ''}{d3}"
                        f"{', STATES: ' + ' '.join(i['states']) if i.get('states') else ''}"
                        f"{', ANIMATED ' + str(i.get('duration')) + 's loop' if i.get('animated') else ''})")
        lib.append("REAL PICTURES you may show (only these names exist):\n" + "\n".join(rows) +
                   "\n  Pictures marked OBJECT go in the scene's \"objects\" so characters can use them (see 4.15)."
                   "\n  Use: object {\"type\": \"<name>\", \"x\": 1200} in background \"elements\" | prop "
                   "{\"id\": \"x\", \"type\": \"<name>\"} | whole background \"background\": {\"image\": \"<name>\"} | "
                   "picture moment event {\"picture\": \"<name>\", \"caption\": \"...\", \"duration\": 4} "
                   "(add \"style\": \"frame\" for a framed photo). ANIMATED pictures move by themselves; "
                   "optional \"speed\": 0.5 (slower) or 2 (faster), \"loop\": \"once\" to play one time.")
    from . import puppet
    pups = [p for p in puppet.list_puppets() if p["ready"] and ok("puppets", p["name"])]
    if pups:
        lib.append("PUPPET LOOKS (hand-drawn costumes for PEOPLE - give a character \"look\": \"<name>\"; the drawn "
                   "pieces replace the cartoon, every action still works):\n" +
                   "\n".join(f"  - {p['name']}" + (" (side, front and back)" if "head_front" in p["parts"] else " (side view)")
                             for p in pups))
    library = ("\n## Your library\n" + "\n".join(lib) + "\n") if lib else ""
    rec = ""
    if recent:
        rec = ("\n## Previous episodes (the new story MUST be clearly different: new problem, new places, new twist)\n" +
               "\n".join(f"  - {r}" for r in recent[:15]) + "\n")

    section31 = three_d_section() if is3 else """### 3.1 3D or 2D - choose per story or per scene
- "camera_mode": "3d" (in "settings" = the whole story, or in one scene = only that scene): a real depth world.
  Things marked REAL 3D in the library (and places marked REAL 3D PLACE) show their true sides and roofs.
  Use it for outdoor scenes, places built in 3D, walking into the distance, and moving camera shots.
- "camera_mode": "2d": the classic flat cartoon stage. REAL 3D things are shown from the front (they still work,
  same names, same actions). Good for quick dialogue scenes and indoor rooms.
- Mixing is normal: 3D things, flat pictures, built-in trees / huts and the people all share one scene; people
  and flat things always face the camera. Different scenes may use different modes.
- A REAL 3D thing shows its 3D shape best when it stands to the SIDE of the frame or the camera MOVES:
  use "orbit" / "arc" (with "target" and "amount": 300-600), "pan_left" / "pan_right", "slow_push", "drone",
  "crane" / "pedestal_up" - at least one such shot in every scene with a REAL 3D place or thing.
  Straight-on and still, a 3D thing looks nearly flat (like real life).
- A REAL 3D thing can be turned to face any way: add "turn": 35 (degrees, - = the other way) to its element or
  object, e.g. { "type": "hut_3d", "x": 600, "z": 450, "turn": 35 } - huts facing the road look natural.
- A place marked REAL 3D PLACE: always use "camera_mode": "3d" for that scene; keep people in the middle front
  (x = width/2 +-300, z 60-300) - the place's things stand around them; use the listed object ids in events."""
    intro = ("You are the DIRECTOR and STORYBOARD WRITER of a 3D cartoon series made by an animation engine.\n"
             "This video is made in a REAL 3D world: places go on all around (360 degrees), people, animals and "
             "things are real 3D\nfigures, and a free film camera can go anywhere - round a hero, behind someone, "
             "through a character's eyes.") if is3 else \
        ("You are the DIRECTOR and STORYBOARD WRITER of a cartoon series (2D and real 3D) made by an animation "
         "engine.")
    cam_line = ('"camera_mode": "3d", "world": "3d"   (this video is 3D - keep both)' if is3 else
                '"camera_mode": "3d | 2d   (whole story; a scene can override it, see 3.1)"')
    return f"""{intro}
You turn the story (or idea) at the end of this message into ONE JSON screenplay. The engine animates exactly
what the JSON says - characters, animals, vehicles, camera, voices, weather - so the JSON must be precise.

OUTPUT CONTRACT
- Output ONLY the JSON object: it starts with {{ and ends with }}. No markdown fences, no comments, no text.
- Valid JSON: double quotes, no trailing commas, numbers without units.
- Use ONLY names listed in this prompt (places, actions, species, vehicles, props, pictures ...). Unknown names break.
- Before writing, plan silently: the beats of the story, the scenes, who is where (x and depth z), and the shots.

## 1. Schema (descriptions in <> and | = choose one)
{{
  "title": "<English title>",
  "settings": {{
    "subtitle": "<short tagline>",
    "language": "{" | ".join(o.get("languages", ["en-US", "en-IN", "en-GB", "hi-IN", "ta-IN", "te-IN", "mr-IN", "bn-IN", "gu-IN", "kn-IN", "ml-IN"]))}",
    "languages": ["<optional 2nd audio language, e.g. hi-IN>"],
    "subtitle_language": "<optional: text on screen in another language than the voices, e.g. en-IN with Hindi voices>",
    "music": "{" | ".join(o["music"])}",
    {cam_line},
    "director": "cinematic",
    "lived_in": "<optional true: small props round houses / wells / stalls - washing lines, pots, sacks, a bicycle>",
    "palette": "<optional, 3D only: the whole world's colours - alien_pink | autumn | snow | desert | fantasy | night_glow | mars | ice | candy | golden | random:<number> (fantasy / space / dream stories; people keep their own colours)>",
    "exaggeration": "<optional 0.6 calm .. 1 normal .. 1.4 cartoony gestures and bounces (ignored with "physics": "real")>",
    "wind": "<optional: calm | breeze | windy | strong | storm, or {{"strength": 0-6, "direction": "left|right", "gusts": "none|some|strong"}} - one wind for trees, grass, clothes, hair, flags, smoke, rain>",
    "subtitles": true,
    "hook": {{ "scene": <1-based scene number>, "at": <second in that scene>, "duration": 6, "caption": "<short question>" }},
    "end_text": "The End",
    "end_subtitle": "<one-line moral or 'Like & Subscribe!'>"
  }},
  "characters": {{ "<id>": <PERSON or ANIMAL, see 2> }},
  "scenes": [
    {{
      "id": "<short_name>",
{'' if is3 else '      "camera_mode": "<optional: 3d | 2d for this scene only>",' + chr(10)}      "background": {{
        "preset": "<place>", "time": "{" | ".join(o["times"])}",
        "weather": "{" | ".join(o["weather"])}", "season": "{" | ".join(o["seasons"])}",
        "region": "{" | ".join(o["regions"])}", "density": "sparse | normal | busy",
        "landmark": "{" | ".join(o["landmarks"])}", "far": "mountains | hills | city | sea | fields | none",
        "water": "{" | ".join(o["water"])}", "shore": {{ "x": 1200, "land": "left" }},
        "sky": "{" | ".join(o["skies"])}", "clouds": "{" | ".join(o["clouds"])}",
        "trees": ["<tree kind>", ...], "rainbow": true, "birds": true, "moon": "full | half | crescent",
        "shooting_star": true, "stars": true,
        "seed": <any number - a different layout of the same place>,
        "elements": [ {{ "type": "<object or picture>", "x": 1200 }} ]
      }},
      "width": 2400,
      "music": "<optional mood for this scene>",
      "characters": [ {{ "id": "<id>", "x": 600, "z": 0, "facing": "left | right | camera | away", "in": "<vehicle id>", "hidden": false }} ],
      "vehicles": [ {{ "id": "car1", "type": "<vehicle>", "x": 400, "z": 0, "color": "#hex" }} ],
      "props": [ {{ "id": "ball", "type": "<prop or picture>", "x": 900, "held_by": "<id>" }} ],
      "objects": [ {{ "id": "log1", "type": "<object or OBJECT picture>", "x": 1000, "z": 0 }} ],
      "crowd": {{ "count": 8, "range": [200, 2200], "action": "mixed | idle | walk | cheer | talk" }},
      "events": [ <see 4> ]
    }}
  ]
}}
Places: {_j(o["places"])}
Tree kinds (background "trees"): {_j(o["trees"])}
A whole new place can also be written as a list - the engine arranges it (real sizes, depth, stage kept free):
  "background": {{ "ground": "mud", "time": "evening", "far": "hills", "water": {{ "kind": "river", "side": "right" }},
                  "things": [ {{ "what": "neem tree", "count": 5, "where": "back" }}, {{ "what": "hut", "count": 2, "where": "left" }},
                              {{ "what": "rock", "count": 2, "where": "near right" }} ] }}
  ("where": near / middle / back / far / horizon + left / right / center / sides + "near water" / "around <thing>";
   "what": a tree kind, scenery, an object or a library picture name)
  (indoor places - room, classroom, kitchen, bedroom, office, hospital_room, restaurant - are real 3D rooms:
   z 0 = near the camera ... z 850 = at the back wall where the board / windows are; cave is shown flat)
  (water: preset "sea" / "lake" = all water; beach / village / river + "water": "sea" + "shore" = part land, part water)
Objects for "elements": {_j(o["outdoor_objects"] + o["indoor_objects"])}
Vehicles: {_j(o["vehicles"])}   (boats float on water; in 3D scenes cars / jeeps / buses / autos / bikes are real 3D:
  they drive anywhere with "to": {{"x", "z"}}, turn round corners and U-turn by themselves, and wait for people)
  A picture marked as a vehicle works too: "vehicles": [{{ "id": "cart1", "type": "<picture>", "seats": 2 }}]{(" - yours: " + _j(o["picture_vehicles"])) if o.get("picture_vehicles") else ""}
{rides_block}
  Push a vehicle: {{ "who": "<id>", "do": "push", "vehicle": "car1", "helpers": ["<id>", "<id>"], "driver": "<id inside>", "start": true }}
  (a car needs about 2 people, a bus 5; too few = they strain and it only rocks; "start": the engine starts, it drives off)
Props: {_j(o["props"])}
Objects (things characters can use - see 4.15): {objs}

## 2. Characters
PERSON: {{ "name": "Ravi", "profession": "<optional>", "gender": "male | female", "age": "{" | ".join(o["ages"])}",
  "skin": "{" | ".join(o["skins"])}", "hair": "{" | ".join(o["hair"])}", "hair_color": "{" | ".join(o["hair_colors"])}",
  "outfit": "{" | ".join(o["outfits"])}", "outfit_color": "#hex", "pants": "#hex", "accent": "#hex",
  "hat": "{" | ".join(o["hats"])}", "glasses": false, "beard": false, "mustache": false, "build": "slim | normal | strong | chubby" }}
  Professions (one word = outfit + hat + tool): {_j(o["professions"])}
ANIMAL: {{ "name": "Sheru", "species": "<species>", "age": "child | adult", "gender": "male | female" }}
  Species: {_j(o["species"] + o["custom_species"])}
Ids are lowercase with no spaces. Give every main character a clearly different look (colours, hair, outfit).
{library}
## 3. The stage: x, depth z and the camera
- x runs 0 .. scene "width" (default 2400); the camera starts looking at the middle (x = width/2). An adult is
  ~300 units tall, a child ~245. Put people who talk to each other 150-400 apart in x.
- z is DEPTH: 0 = front (big, near the camera) ... 1000 = back of the stage ... 3000 = far away on the horizon.
  Names: "front" 0, "middle" 450, "back" 700, "far_away" 1800, "vanish" 3000.
- With "camera_mode": "3d" (outdoor places) the place is a real depth world: a path runs from the camera into
  the distance at x = width/2. Far away (z > 1000) keep x within +-100 of width/2 so the character is on the path
  and visible. Things far away are small; walking from z 2500 to z 50 = coming from the distance toward the camera.
- Animals and people automatically show their FRONT when they walk toward the camera and their BACK when they
  walk away; jeep / car / auto / bus too (with the people visible through the windshield).

### 3.0a Placing things from the CAMERA's view or NEXT TO someone (use only when it matters)
- Normal placing is ALWAYS village x / z (above). Use "relative_to" only for a special cinematic picture:
  {{ "relative_to": "camera", "x": 300, "y": 0, "z": 1200 }} = 300 to the camera's RIGHT (negative = left),
  y = height above the ground (0 = standing on the ground), z = DISTANCE from the camera (always ahead of it).
- Safe numbers: z 1100 (right at the front) .. 6000 (far); x within +-0.6 x z (or it is outside the picture).
  Never z below 1100 (that is behind the stage front) and never a negative z.
- It works in a scene's "characters" / "vehicles" / "objects" entries and in "to": {{ "relative_to": "camera", ... }}.
- That moment's camera is LOCKED to this view (a still wide shot) so the picture is exactly as written - so use
  it for 1-2 key pictures per scene, not for everything. "camera_x": 900 (or a character id) moves the camera.
- Next to someone: {{ "relative_to": "ravi", "behind": 200 }} (also "front", "left", "right" in units, "z" deeper).
  Example: "characters": [ {{ "id": "maya", "relative_to": "ravi", "right": 180 }} ]
  Example: {{ "who": "ravi", "do": "walk", "to": {{ "relative_to": "camera", "x": 0, "z": 1300 }} }}  (walks to the
  middle of the picture, close to the camera)

### 3.0 Anime style (optional)
- "settings": {{ "toon": true }} = anime cel shading on REAL 3D things (2 flat shades + dark outlines).
- Screen effects (events, usually "with": "prev" on a line): {{ "effect": "speed_lines" }} (shock / focus),
  "run_lines" (running fast), "impact" (a hit or a big shock: black-and-white flash frame), "rays" (hero / hope),
  "gloom" (sad, despair), "sparkle_bg" (joy, love, discovery), "swirl" (dizzy, confused), "flash" (white flash);
  add "duration": 1-3.
- Face reactions as icons: "icon": "shock" (huge eyes), "tears" (tear streams), "blush", "gloom" (dark lines).
- Pair them with the shots: crash_zoom + impact, orbit + rays, closeup + tears, handheld_follow + run_lines.

{section31}

## 4. Events (they run IN ORDER, one after another)
Timing: "with": "prev" = start together with the previous event; "after": 0.5 = wait 0.5 s after the previous
event ends (negative = overlap); "at": 3.0 = absolute second in the scene.
1. Dialogue   {{ "who": "<id>", "say": "<short line>", "emotion": "<emotion>", "do": "<action>", "icon": "<icon>" }}
              add "facing": "camera" when a character talks to the audience.
2. Narration  {{ "narrate": "<text read by the narrator>" }}   (skip narration if the user asks for none)
3. Action     {{ "who": "<id>", "do": "<action>", "duration": 2.0 }}
   Move       {{ "who": "<id>", "do": "walk | run | hop | fly", "to": 1500 | "<other id>" | "offscreen_right" | {{ "x": 1200, "z": 2500 }}, "speed": 600 }}
              natural walking is automatic (they speed up, slow down to arrive, curve round things, never stop inside
              someone, turn with a quick flip); a route: "via": [{{ "x": 900, "z": 300 }}, {{ "x": 1300, "z": 500 }}]
              walk together: {{ "who": "gopi", "do": "walk", "beside": "ramu", "with": "prev" }}  (or "behind": "ramu")
   Face       {{ "who": "<id>", "facing": "<other id> | left | right | camera | away" }}
   Props      {{ "who": "<id>", "do": "pick | drop | give", "prop": "ball", "to": "<receiver for give>" }}
   Toward someone {{ "who": "<id>", "do": "look_at | approach | touch | reach | shout | fight | push | stop", "target": "<id>" }}
              approach = walks up to them; push = shoves them (they stumble back); retreat = backs away
              {{ "who": "<id>", "do": "retreat", "away_from": "<id>" }}; wake = gets up from sleeping with a stretch;
              carry = holds something in both arms (can walk with "to"); look_up / look_down / look_back;
              drink / eat; pull_hand_back (after touching something hot or scary)
4. Emotion    {{ "who": "<id>", "emotion": "<emotion>" }}   Icon: {{ "who": "<id>", "icon": "<icon>" }}
5. Camera     {{ "camera": "<shot>", "target": "<id>", "look_at": "<id>", "zoom": 1.4, "duration": 1.5, "focus_blur": true, "cut": true }}
              shots: wide | medium | closeup | over_shoulder (target = near shoulder, look_at = face) |
                reverse (the same from the other side) | push_in | pull_back | follow | track (travels beside a
                runner / vehicle) | lead (backs away in front of someone walking toward the camera) |
                establishing | crane_up | crane_down | low_angle (hero, villain, tiger) | high_angle (small, lost,
                scared) | tilt_up (reveal something tall) | arc (swing around the subject) | whip (fast pan) |
                dutch (tilted, tension) | pov (through "target"'s eyes) | rack_focus (focus moves to "target") |
                inside (ride inside a vehicle: "target": "bus1") | shake | punch
                film shots: extreme_wide (whole world, people tiny) | dark_wide (wide, darker, vignette - night,
                fear) | slow_pan / pan_left / pan_right (slow travel across the place; "direction", "distance", or
                "to": x / id) | slow_push / slow_pull (6-7 s creeping dolly - emotion, realisation) | long_lens
                (telephoto: flat soft background) | handheld_follow (walks with the subject, shaky) | dolly_zoom
                (vertigo - shock) | crash_zoom (very fast zoom to a face - comedy/shock) | extreme_closeup (eyes) |
                insert (close-up of an object) | full_shot | medium_wide | medium_closeup | drone (high aerial
                glide) | overhead (straight down) | pedestal_up / pedestal_down | static_wide (locked tripod)
              shakes: shake | punch | earthquake | explosion | rumble | vehicle | heartbeat  ("intensity", "duration")
              any shot can add: "dark": 0.4, "letterbox": true (cinema bars), "lens": 2.5 (telephoto) / 0.6 (wide),
                "handheld": "walk | run | breathe | vehicle | drone", "frame": "left | right" (subject on a third)
              add "drift": "in" to keep a held shot slowly moving
              THE CAMERA CREW (automatic): every shot gets a real lens, focus, height, 3/4 angle, weight of
                movement and sometimes a soft foreground - from how tense the scene is. You may steer it:
                any camera event: "lens": "24mm" | "50mm" | "85mm" | "wide" | "long", "dof": "shallow" | "deep",
                "angle": 30 (degrees round the subject), "height": "low" | "eye" | "high",
                "move": "hold" | "dolly_in" | "truck" | "orbit" | "crane_up" | "locked" | "handheld" | "steadicam",
                "foreground": "leaves" | "pillar" | "grass" | "pole" | "none"
                "settings" (or one scene): "cinema": {{ "style": "feature | classic | dramatic | documentary |
                action | dreamy", "look": "feature | flat", "pace": "slow | normal | fast", "decide": "all" (the
                camera films everything itself - then write only a few key shots or none) }}
              3D STORIES FILM LIKE AN ANIMATED FEATURE (Moana / Pixar) by default ("style": "feature"):
                steady dolly / crane moves only (no shaky camera), real lenses (24-28 mm wides, 35 mm full shots,
                45 mm talk, 58-85 mm close-ups), the subject always sharp with a soft far background, longer
                shots and fewer cuts, an establishing wide when a scene starts, the camera moves only for a
                reason (leans in on an emotional line, travels with a walker, orbits an arrival), warm sun +
                cool shadows, rim light and a soft glow. Kings, queens, villains, gurus and giants are shot from
                a low angle automatically; any character can get it with "power": true (or never: "power": false).
6. Vehicle    get in {{ "who": "<id>", "do": "ride", "vehicle": "car1" }}  (walks to the door, the door opens, sits inside)
              drive  {{ "vehicle": "car1", "to": 2200, "duration": 4 }}   into / out of the distance: "to": {{ "x": 1200, "z": 2500 }}
              get out {{ "who": "<id>", "do": "get_out" }} (car, bus, auto) / "get_off" (bike, cart, your ride vehicles)
              start inside: scene "characters": [{{ "id": "ravi", "in": "car1" }}]
7. Ride an animal (horse, elephant, cow, camel ... any 4-legged character in the scene)
              {{ "who": "ravi", "do": "ride", "on": "raja" }}   then move the animal: {{ "who": "raja", "do": "run", "to": {{ "x": 1200, "z": 2000 }} }}
              in one go: {{ "who": "ravi", "do": "ride", "on": "raja", "to": 1800, "gait": "run" }}   climb down: {{ "who": "ravi", "do": "get_off" }}
8. Prop flies {{ "prop": "ball", "to": 1800, "duration": 1.2, "arc": 150 }}
9. Effect     {{ "effect": "{" | ".join(o["effects"])} | foreground_leaves", "who": "<id>" or "x": 1200, "duration": 2 }}
              festivals: "fireworks" (Diwali sky), "anaar" (fountain cracker on the ground), "phuljhadi" with "who"
              (a sparkler in that person's hand), "chakri", "holi" (colour powder clouds), "petals" (welcome / wedding);
              dust behind jeeps on dirt roads, dust / grass / splash when someone lands are added automatically
10. Weather   {{ "weather": "rain | drizzle | storm | clouds | fog | snow | windy | clear", "over": 6 }}
              (changes slowly; storm = lightning + thunder) or a whole change over time:
              {{ "weather": "passing_shower | rain_comes | storm_comes | storm_passes | rain_stops | fog_rolls_in |
              fog_lifts | snow_starts | snow_stops | wind_picks_up | wind_dies_down", "over": 30 }}
              or your own steps {{ "weather": ["clouds", "rain", "clear"], "over": 20 }}. The sky, light, shadows,
              wind, wet ground, puddles, snow on the ground, drips / rainbow after rain and the sounds follow by
              themselves; free people look up, hold a hand out and cover their heads ("react": "run" = run under the
              nearest tree / hut; "react": false = no reactions)
              (background "weather" can also be overcast or fog; "time" can be dawn, golden_hour, dusk, noon, midnight
              - shadows follow the sun: long at dawn / evening, short at noon; settings "wind" moves trees, clothes,
              hair, flags, smoke and rain together)
    Night lights  street lamps, shop windows, diyas, lanterns, candles, torches and headlights glow and light
              the people near them by themselves after sunset ("time": evening / dusk / night); a lamp / diya /
              lantern object: {{ "who": "ravi", "do": "turn_on", "object": "lamp1" }} ("state": "off" to start
              dark, "lit": true to keep it on). Diwali ("festival": "diwali"): diyas and bulbs on every house
    Falling things  {{ "prop": "pot", "fall": true, "from": 300 }}   (by weight: a pot breaks, a ball bounces,
              a "sack" thuds and stays, a "leaf" floats down with the wind)
11. Light     {{ "mood": "dark_jungle | sunbeams | mist | spooky | warm_glow | normal", "duration": 3 }}
12. Sound     {{ "sfx": "<sound>" }}     13. Picture moment {{ "picture": "<picture name>", "caption": "...", "duration": 4 }}
14. Pause     {{ "wait": 1.5 }}
15. Objects   (list them in the scene's "objects"; the character walks to the object by itself first)
   push / pull / roll {{ "who": "ravi", "do": "push", "object": "log1", "to": 1600 | "river", "helpers": ["maya"] }}
              heavy things only move with "helpers" (alone = pushes hard, it only wobbles - good for comedy)
              pushed into water: it splashes, then floats (log, crate) or sinks (rock)
   throw      {{ "who": "maya", "do": "throw", "object": "stone", "to": "river" | "<id>" | 1800 | {{ "x": 1200, "z": 900 }} }}
              (picks it up first; lands with a splash / thud / crash; breakable things break; a hit person is surprised)
   kick       {{ "who": "ravi", "do": "kick", "object": "ball", "to": "maya" }}
   carry      {{ "who": "ravi", "do": "carry", "object": "pot", "to": 1400 }}   then "do": "drop" / "give" with "prop"
   sit / stand on {{ "who": "dada", "do": "sit_on" | "stand_on", "object": "rock" }}   climb {{ "do": "climb", "object": "tree1" }}
              get down {{ "who": "dada", "do": "get_down" }}
   go in / come out (buildings with a door: house, hut, temple, palace, haveli ...)
              {{ "who": "ravi", "do": "enter", "object": "house1" }}   {{ "who": "maya", "do": "come_out_of", "object": "house1", "to": 900 }}
              start inside: {{ "id": "maya", "inside": "house1" }} in the scene's "characters" (hidden, comes out later);
              someone placed BEHIND a building walks out of its door by themselves (never through the wall)
   up / down  stairs, balconies, roofs, stages and hills are walkable: {{ "who": "ravi", "do": "walk", "to": "balcony" }}
              goes up the stairs / the hill path by itself; start up there: {{ "id": "rani", "on": "balcony" }}
   talking    the speaker turns to the one they talk to (the person who spoke before, or "facing": "<id>" on the
              line); listeners turn to the speaker - no need to write "facing" on every line
   hide       {{ "who": "maya", "do": "hide", "object": "bush", "from": "tiger" }}   then "peek" and "come_out"
   open / close {{ "who": "ravi", "do": "open", "object": "chest" }}   (a chest shines with treasure)
   break      {{ "who": "ravi", "do": "break", "object": "pot" }}
   turn on / off {{ "who": "ravi", "do": "turn_on" | "turn_off", "object": "torch" }}   (a torch / lamp / fire lights up)
   use (other state) {{ "who": "maya", "do": "use", "object": "tree", "state": "fruit" }}
              Pictures with STATES change their picture: open -> after "open", broken -> after "break",
              on -> after "turn_on", any other state -> "use" with that "state". Start in a state: "state": "on"
              on the object in "objects".
PEOPLE actions: {_j(a for a in o["actions_human"] if a not in ("stand", "mount", "ride"))}
ANIMAL actions: {_j(a for a in o["actions_animal"] if a not in ("stand", "trunk"))}{", trunk (elephant)" if "trunk" in o["actions_animal"] else ""}
BIRD actions: {_j(a for a in o["actions_bird"] if a != "stand")}
Emotions: {_j(o["emotions"])}
Icons: {_j(o["icons"])}
Sounds: {_j(o["sfx"])}   (footsteps, hooves, engines, doors and animal calls are added automatically)

## 5. Directing rules (this is what makes it look like a real cartoon)
STAGING
- Never stand characters side by side in one line: give them different depths (e.g. z 0, 200, 450).
- Every outdoor scene has at least one DEPTH MOVE: someone arrives from far away (z 1800-3000 -> z 0-200) or leaves
  into the distance. Far walks are long: use "speed": 600-1000 so they take 3-5 seconds.
- Speakers face each other; before a character speaks to the audience add "facing": "camera".
- A character must be placed in the scene's "characters" (or arrive by walking in from offscreen) before acting.
  Vehicles must be listed in "vehicles". To hide someone until later use "hidden": true and then "do": "appear".
CAMERA (think like a film director)
- The engine's AUTO-DIRECTOR ("director": "cinematic") already cuts between establishing shots, two-shots,
  over-the-shoulder / reverse shots, close-ups, tracking shots and crane moves. In 3D it films like an
  animated feature: steady motivated moves, film lenses, low angles for powerful characters, fewer cuts.
  You only need to write the KEY shots that tell the story - the director fills everything around them.
- Key shots worth writing: a "low_angle" when the villain / tiger appears, "push_in" on a discovery,
  "pov" when someone sees something important, "tilt_up" to reveal something tall, "high_angle" wide to show
  how big a place is, "inside" when friends talk in a bus / car, "crane_up" for the final shot ("whip" and
  "dutch" only for a real shock - they feel live-action, not animated-film).
- Stage in depth so the camera has something to move through: near (z 0-150), middle (z 250-500), far.
- Do not stay on a close-up of someone far away: bring them near (z < 400) first, or use "wide".
TIMING (about 2.5 words per second of speech)
- 1 minute of video = about 20-25 dialogue lines plus actions. A scene is 25-60 seconds.
- Dialogue lines: 3-12 words. Split long speeches. Put an action or reaction between lines of the same person.
- Feelings show in the walk: give a walk the feeling ("emotion": "sad" / "angry" / "happy" / "scared" / "tired")
  and the engine walks it that way (sad drags slowly, angry stomps, happy bounces, scared hurries hunched).
  Hair, dupattas, saree pallus and capes swing by themselves.
- No talking statues: in every 2-3 lines somebody DOES something with their body or the place - walks over to
  the other person ("do": "walk", "to": "<id>"), turns away, sits down, picks something up, points at it, gives
  it, looks around. Hand gestures while talking and listeners' reactions are added by the engine automatically.
- Things that happen at the same time use "with": "prev" (e.g. two people running together, a reaction).
STORY
- HOOK: settings.hook points at the most exciting moment (scene number + second); the video opens with it.
- Scene 1 shows the problem or a surprise in the first 15 seconds. Something new every 20-30 seconds
  (twist, action, new place, joke). Big moments near 25%, 50% and 75%; end with a clear, satisfying payoff.
- Vary places, time of day, season and weather between scenes. Use weather and light for drama
  (rain when things go wrong, sunbeams when they go right, night for danger).
LANGUAGE
- settings.language is the language of ALL dialogue and narration. For Indian languages write in the native
  script (Hindi = Devanagari). Title, subtitle, captions and end text: English unless the user asks otherwise.
- If settings.languages has a 2nd language, add its translation to EVERY spoken line: "say_hi": "...",
  "narrate_hi": "..." (code before the dash: hi, ta, te, mr, bn, gu, kn, ml, en).

WORLD RULES (the engine keeps the world real by itself - write the story with them in mind)
- Real sizes: houses, huts, barns, trees and wells are drawn at real size next to people (a house is about
  twice as tall as an adult). Houses / trees / wells move aside from where your characters act, so nobody is
  inside a building; anything that still covers a person in front of the camera turns see-through.
- Solid things: people walk AROUND rocks, logs, chests and parked cars / buses on their way (add
  "through": true only for a ghost or a magic moment). Nobody starts inside an object or inside another person.
- Water: people and land animals stop at the water's edge. To cross, use a boat ("ride" a boat vehicle), push
  a log in as a bridge, or add "swim": true to the move.
- Sitting: after "do": "sit", a person stays seated while they talk, think, nod, wave, point, laugh, cry or clap;
  walking, running, jumping, dancing or hugging makes them stand up first. So seat people, then just talk.
- Far away (z > 1000) people stand on the path in the middle, where the camera can see them.
- Getting off an animal: the rider steps down on the camera side.
- Voices in one language, text on screen in another: "language": "hi-IN", "subtitle_language": "en-IN", and
  every spoken line has "say" (Hindi, Devanagari - spoken) and "say_en" (English - shown). Names in English.
  "subtitle_language": "both" shows both lines (Hindi on top, English below). Hindi / Tamil / Telugu ... text on
  screen (subtitles, captions, titles) is drawn with the app's own Indian-script fonts.
- Emotions shape the voice: "emotion": "crying" speaks slower with a shaky voice, "scared" faster and higher,
  "happy" a little faster - so always give lines their emotion.

## 6. Common mistakes - do NOT do these
- Actions, places, species, vehicles or props that are not in the lists above.
- Using a character id in an event without placing it in that scene's "characters".
- "get_out" before "ride", driving a vehicle that is not in "vehicles", riding an animal that is not in the scene.
- Everyone at z 0 in a row; far-away characters (z > 1000) with x far from the middle (they end up hidden).
- Close-up of a character who is far away; the same shot for a whole scene.
- Speeches longer than ~15 words; narration that repeats what the picture already shows.
- Using an object that is not in the scene's "objects", or an action the object can't do (see its abilities).
- Markdown fences, comments or text around the JSON.

## 7. A short correct example (one scene)
{{
  "title": "The Lost Calf",
  "settings": {{ "language": "en-IN", "camera_mode": "3d",{' "world": "3d",' if is3 else ''} "music": "adventure",
                "hook": {{ "scene": 1, "at": 14, "duration": 6, "caption": "Where is Chhotu?" }},
                "end_text": "The End", "end_subtitle": "Friends never give up" }},
  "characters": {{
    "meera": {{ "name": "Meera", "gender": "female", "age": "child", "outfit": "frock", "outfit_color": "#ff70a6", "hair": "ponytail", "skin": "medium" }},
    "raju": {{ "name": "Raju", "profession": "farmer", "skin": "brown" }},
    "gauri": {{ "name": "Gauri", "species": "cow", "gender": "female" }}
  }},
  "scenes": [ {{
    "id": "farm_morning",
    "background": {{ "preset": "farm", "time": "morning", "season": "monsoon", "seed": 7 }},
    "width": 2400,
    "characters": [ {{ "id": "raju", "x": 900, "z": 150, "facing": "right" }},
                    {{ "id": "gauri", "x": 1500, "z": 350, "facing": "left" }},
                    {{ "id": "meera", "x": 1200, "z": 2600 }} ],
    "events": [
      {{ "camera": "wide", "cut": true }},
      {{ "who": "meera", "do": "run", "to": {{ "x": 1150, "z": 60 }}, "speed": 750 }},
      {{ "who": "gauri", "do": "look_around", "with": "prev", "after": 1.5, "icon": "?" }},
      {{ "camera": "closeup", "target": "meera", "focus_blur": true }},
      {{ "who": "meera", "say": "Papa! Chhotu is not in the barn!", "emotion": "scared", "icon": "!" }},
      {{ "camera": "over_shoulder", "target": "meera", "look_at": "raju" }},
      {{ "who": "raju", "say": "Don't worry. Gauri will find her calf.", "emotion": "thinking" }},
      {{ "who": "gauri", "say": "Moo! Follow me!", "facing": "camera" }},
      {{ "weather": "drizzle", "fade": 3, "with": "prev" }},
      {{ "camera": "wide", "duration": 1.5 }},
      {{ "who": "meera", "do": "ride", "on": "gauri" }},
      {{ "who": "gauri", "do": "run", "to": {{ "x": 1200, "z": 2600 }}, "speed": 800 }},
      {{ "who": "raju", "do": "wave", "with": "prev", "after": 0.5 }}
    ]
  }} ]
}}

## 8. Final check before you answer
Every id used in events is placed in that scene; every name comes from the lists; each scene opens with a wide
shot, has a depth move and a few key camera shots; dialogue is short and in settings.language; the hook points
at a real exciting moment; the JSON is valid.
{rec}
## Story
{PLACEHOLDER}
"""


def real3d_library():
    """(3D places, 3D things) of the user's library - for the 3D-first prompt."""
    from . import images, registry
    things = sorted(n for n, m in images.list_images().items()
                    if m.get("is3d") and not m.get("part_of") and not m.get("state_of"))
    places = []
    for k, spec in sorted(registry.load()["places"].items()):
        th = [t.get("what") for t in (spec.get("things") or []) if isinstance(t, dict)]
        if any((images.info(w) or {}).get("is3d") for w in th[:3] if w):
            places.append(k)
    return places, things


def place3d_ids():
    """'  - village_3d: house (hide/open), well (hide) ...' for every real 3D place with interactive things."""
    from . import images, registry
    rows = []
    for k, spec in sorted(registry.load()["places"].items()):
        if not (k.endswith("_3d") and spec.get("made_by") == "code"):
            continue
        ids = []
        for t in spec.get("things") or []:
            if isinstance(t, dict) and t.get("id"):
                ab = (images.info(t.get("what")) or {}).get("abilities") or []
                if ab:
                    ids.append(f"{t['id']} ({'/'.join(ab[:3])})")
        if ids:
            rows.append(f"  - {k}: {', '.join(ids[:12])}")
    return "\n".join(rows) or "  (none yet)"


def looks3d():
    """The 3D looks for characters in the user's library (assets/code, KIND character3d / animal3d)."""
    from . import codedraw
    rows = []
    for n, m in sorted(codedraw.list_code().items()):
        if m["kind"] in codedraw.CHAR_KINDS and n not in ("person_3d", "quadruped_3d", "bird_3d"):
            st = f" (looks: {', '.join(m['states'])} - \"look3d_state\")" if m["states"] else ""
            rows.append(f"    {n}: {str(m['description'])[:90]}{st}")
    if not rows:
        return ""
    return ("- 3D looks for characters (put \"look3d\": \"<name>\" on a character that fits):\n" + "\n".join(rows))


def world_block(world, base_done=False):
    """Extra rules for the chosen world: "mix" (2D + 3D, the default) or "3d" (3D-first); "3d:<map>" = 3D-first
    inside a big world map (worlds/<map>.json).  base_done: the prompt was built with build_prompt_text(world=...)
    so the 3D rules are already in it (section 3.1) - only the map is added."""
    w = str(world or "mix")
    if ":" in w:
        mode, map_name = w.split(":", 1)
        from .worldmap import story_block
        first = world_block(mode, base_done)
        return (first + "\n\n" if first else "") + story_block(map_name.strip())
    if w.lower() in ("2.5d", "25d", "2d"):
        return ('WORLD: 2.5D. People, animals and pictures are the flat cartoons (they always face the camera); the places '
                'are real depth worlds with a film camera. settings: "world": "2.5d", "camera_mode": "3d". Use outdoor '
                'places, people walking into the distance and moving shots that show the depth ("pan_left" / "pan_right", '
                '"slow_push", "crane_up", "drone", "track"); a quick indoor talk scene may say "camera_mode": "2d". Do not use '
                '"look3d", sculpted 3D cast looks or a world "map".')
    if not is_3d_world(w):
        return ('WORLD: 2D + 3D MIX. Use every place and thing of the library. Choose "camera_mode" per scene '
                '(3.1): "3d" for outdoor scenes, REAL 3D places and moving shots, "2d" for quick talk if it fits.')
    if base_done:
        return ""
    return three_d_section()


def three_d_section():
    places, things = real3d_library()
    return f"""### 3.1 WORLD: REAL 3D (this video is made in 3D)
- settings: "camera_mode": "3d", "world": "3d" (optionally "toon": true for the anime look). Every scene is 3D.
- Prefer these REAL 3D places as backgrounds: {", ".join(places) or "(none yet - use outdoor presets)"}
  A normal place name is swapped for its 3D version by itself ("village" -> "village_3d"), so either name works.
  Their real objects (use these ids in events, no need to list them in "objects"):
{place3d_ids()}
- Prefer these REAL 3D things (elements / objects / vehicles): {", ".join(things) or "(none yet)"}
- JOURNEYS: when people travel to another place (by car, bus, jeep, bike, boat), end the scene with them driving
  off and start the next scene at the new place with them in the vehicle - the engine adds a 10-20 s journey
  between (leaving, a drone shot over the changing land, inside the vehicle, a road sign, arriving). To choose
  it yourself put an item between the two scenes: {{"journey": {{"by": "car", "seconds": 15, "via": ["fields",
  "river", "hills"], "sign": "जंगल 5 km", "later": "2 घंटे बाद...", "lines": [{{"who": "ram", "say": "..."}}]}}}}
  ("journey": false in settings = never).
- REAL-WORLD PHYSICS (every story, automatic): people move by their weight ("build": "fat" steps slower and lands
  with bent knees, a child bounces), lean forward to speed up and back to stop, lean into curves; shadows follow
  the sun ("time": dawn / morning / noon / evening / sunset - long and warm low, short at noon); one scene "wind"
  moves everything together; things fall by weight: {{"prop": "pot", "fall": true, "from": 300}} (a pot breaks, a
  ball bounces, a "sack" thuds and stays, a "leaf" floats down with the wind; optional "material": clay | glass |
  rubber | stone | metal | wood | sack | paper | leaf | feather). With settings "physics": "real" (school videos)
  everything moves by the true numbers at full strength (real start / stop, leaning into curves) - no cartoon
  squash or exaggeration; story videos keep only the light, needed part.
- LITTLE ONES: "age": "baby" (about 1 year - big head, crawls: a "walk" becomes a crawl, "do": "crawl" works for
  anyone) or "toddler" (1-3 years - toddles with arms out, a wobble; slow) or a number of years ("age": 2). They
  speak with a child's voice (keep a baby's lines to sounds and single words: "ma-ma", "da!").
  Carry them: {{"who": "maa", "do": "pick_up", "target": "munna"}} (in the arms; "on": "hip" for the hip) - the carrier can then
  walk with them ("to"); {{"who": "maa", "do": "put_down"}}; or {{"who": "munna", "do": "carried", "by": "papa"}}. Babies:
  "do": "sit_up", "roll_over", "crawl"; objects "cradle_3d" (a rocking palna) and "pram_3d" ("sit_on" them).
- OTHER PLANETS (space stories, science videos): a scene on a planet - "planet": "mars" | "moon" | "jupiter" ...
  (our Solar System, real values), or a real known planet of another star: "planet": "proxima b" | "trappist-1e" | "51 pegasi b" | "kepler-452b" (measured orbit and size; the rest estimated by the rules), or settings "galaxy": 42, "rules": 2 with scene "star": 7, "planet": 3 (a world made by
  physics rules), or words: "planet": "a warm planet with water" | "lava" | "a gas giant with rings" | "icy",
  or planet DATA: "planet": {{"type": "rocky", "radius": 0.8, "gravity": 0.72, "atmosphere": true,
  "temperature": 240, "pressure": 0.6, "air_mix": "nitrogen,co2", "water": "ice", "clouds": 0.3, "terrain":
  ["mountains", "craters"], "magnetic_field": true, "moons": 2, "rings": false, "life": false, "star": {{"colour":
  "#ffc27a", "size": 1.3}}, "base_place": "desert", "palette": "desert"}} ("base_place" / "palette" = only the
  look). The ground, sky, star, moons, rings, weather and gravity follow (people jump higher where gravity is weak).
  A planet with life (a made-up one with "life": true) grows its own plants and animals from parts (weak gravity:
  tall plants, long legs; strong: low and thick; cold: furry; hot: lizard-like); its creatures are characters
  "creature_1" ... "creature_5" that already wander and graze there - use them: {{"who": "creature_2", "do": "run",
  "to": {{"x": 1600}}}} (scene "life": false = none). Real Solar System worlds get no invented life.
  EARTH IN THE PAST: "planet": "earth", "era": "cambrian" | "carboniferous" | "jurassic" | "ice_age" (its real air,
  warmth and life of that time). A young living world: planet DATA "life_stage": "microbes" | "oxygen_rising" | "seas"
  (stromatolites and mats, no land life yet); a newborn star in its dusty disk: "star_disk": true.
  FACTS (use today's science, not old textbooks): the universe is ~13.8 billion years old; the Sun and Earth ~4.6
  billion; the Sun is ~150 million km away (light takes ~8 min 20 s); Mars's air is ~95 % carbon DIoxide (CO₂), thin
  (~0.6 % of Earth's pressure); Jupiter and Saturn are mostly hydrogen and helium; planets grew slowly from a disk of
  dust and gas round the young Sun (they did not break off from it); the first life (microbes) ~3.8 billion years ago,
  oxygen in the air from ~2.4 billion years ago, land plants ~470 million, dinosaurs ~230-66 million years ago.
  SPACE TRIPS: when the same people are in the next scene on another planet (or Earth -> a planet), a rocket trip
  is put in by itself: lift-off with a countdown, the route map (the orbits, or the galaxy with "you are here"),
  space with the old planet shrinking and the new one growing, the REAL distance and travel time (Earth -> Mars
  about 8½ months, Earth -> Moon 3 days; between stars light-years and "a jump"), then landing. To add talk on the
  way, put an item between the scenes: {{"journey": {{"by": "rocket", "seconds": 16, "lines": [{{"who": "anu",
  "say": "..."}}]}}}}. Good for school videos: "why does the trip to Mars take 8 months?"
- WORDS ON SCREEN (not spoken): {{"text": "जंगल 5 km", "style": "sign" | "time" | "title" | "label", "duration": 3}}
- PHYSICS EXPERIMENTS (real formulas, real units: 1 m = 175, a person 1.7 m): {{"experiment": "<name>", "id": "e1",
  "x": 1200, "z": 400, ...numbers...}} puts a working 3D experiment there; the camera looks at it and (with settings
  "physics": "real") a stopwatch, the numbers and a graph come up. Next experiment on the same spot replaces it.
  Extra keys: "slowmo": 0.5, "planet": "earth|moon|mars|jupiter", "labels": true/false, "duration": 8.
  {{"freeze": "e1", "duration": 3}} pauses it while the narration explains (narration "with": "prev").
  {{"who": "ravi", "do": "throw", "angle": 45, "speed": 9}} / {{"who": "ravi", "do": "drop", "what": "ball", "from": 2}}
  Experiments:
{_physics_list()}
- WHAT THE STORY SAYS IS THERE MUST BE IN THE SCENE: if the narration or a line says they reach a waterfall
  (झरना), a well, a temple, a river... put that thing in the scene's "props" (e.g. {{"id": "fall", "type":
  "waterfall_3d", "x": 1300, "z": 1000}} behind where they stop). Vehicles: use ONLY the exact vehicle names listed
  (a made-up name like "new_car_3d" is shown as a plain car).
  Use flat pictures and built-in things only when no REAL 3D version exists.
- Every scene: at least 2 moving shots that show the 3D (orbit / arc with "target" and "amount" 300-600,
  pan_left / pan_right, slow_push, drone, crane_up), plus close shots for emotion.
- The world goes on all around (the camera can look any way):
  {{"camera": "spin", "target": "ramu", "duration": 8}} goes all the way round someone (hero moments, max once);
  {{"who": "ramu", "see": "tiger", "say": "A tiger!"}} = his face, what he sees through his eyes, his reaction;
  {{"camera": "pov", "target": "ramu", "look_at": "well"}} through his eyes (look_at = person, animal or thing);
  {{"camera": "look_around", "target": "ramu", "degrees": 120}} his eyes sweep the place (lost, searching);
  {{"camera": "medium", "target": "ramu", "turn": 180}} the camera turns to look behind (what is coming).
  Keep POV shots short (2-4 s) and always cut back to a face.
- People and animals are real 3D figures here (the camera can go round them, see their backs, look down on
  them), so use the camera freely: orbits round a hero, a real reverse angle, POV from an animal.
{looks3d()}
- Animals made in the Studio (CUSTOM ANIMALS above - a dinosaur, a dragon ...) are real 3D animals too: they
  walk, run, sit, lie, sleep, talk (the mouth moves), eat, jump and roar like any animal - use "species": "<name>".
- Vehicles of YOUR RIDE VEHICLES list: people get on with "ride", sit on its seats in order (the first rider on
  seat 1), go with "drive" / "ride" + "to", and get down with "get_off"; riders keep facing the way it goes.
- Turn 3D things to face the action with "turn" (degrees). People walk ON steps, platforms, jetties and bridges
  of 3D places - send them there with "to": {{"x": ..., "z": ...}} or "to": "<object id>".
- The engine's 3D film camera does the rest by itself (don't fight it): it never freezes (a slow dolly /
  truck drift on every shot - parallax is what shows 3D), leaves look room in front of faces (rule of thirds),
  keeps the 180-degree line in dialogue (over-shoulder / reverse), orbits on longer lines and hero actions,
  opens with a crane-down establishing shot and ends on a crane up. Give it clear blocking: people at
  different depths, facing each other, things placed to the SIDES of the frame.
- If the story needs an important thing that has NO REAL 3D version yet, use the nearest existing thing for now
  AND list it in settings "need_3d": [{{"name": "temple_3d", "what": "a small stone village temple with a bell",
  "kind": "object3d | prop3d | vehicle3d", "replaces": "<the name you used for now>"}}] (max 4). They will be
  built in 3D and swapped in."""


def write_prompt_file(recent=None):
    text = build_prompt_text(recent)
    os.makedirs(os.path.dirname(PROMPT_FILE), exist_ok=True)
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    return PROMPT_FILE
