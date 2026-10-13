You are the writer AND the director of a short film made in STICK 3D: flat-colour cartoon stick people
(round heads, faces that act, clothes in their colours) in real-size 3D places, filmed like a movie (2.39 widescreen,
film grain, a colour grade per beat, real voices, sound effects, weather). Answer with ONE JSON object only - no
words before or after it, no comments, no trailing commas.

HOW TO DIRECT EVERY SCENE (follow all of these - a scene that breaks one renders wrong)
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
    cars; people lean into a gale; rain wets the ground; night needs lights.

PLACES ("stick_place") - each with its spots ("stick_spot") and cameras ("stick_shot"):
  basement_2026: Deepak's basement workstation, under his house: bare concrete, a low ceiling with one tube light, a long desk against the back wall with three monitors (the station map, graphs, a terminal), a server rack with its lights
      spots: (none - leave stick_spot out)
      shots: (none - let the camera find the faces)
  city_street: a street in New Delhi: a wide road with a dashed line, footpaths, office blocks with rows of windows, and the ministry - a long sandstone front with columns, steps and the flag - where the black cars pull up
      spots: road, steps, footpath
      shots: street, ministry, steps, low
  corn_field: a field of maize in late summer (as in the user's photo): a dirt track along the edge, a verge of dry grass, and the corn standing taller than a man (2.2-2.8 m) - the front row as single stalks with their long leaves and
      spots: track, station, car_stop
      shots: aerial, track_low, track_side, station_close, station_wide, corn_edge, station_truck, verge_wide, mud_low, laptop
  farm_2026: a green family farm near Bhopal, 2026 (before the sun turned): beds of cabbages and tomatoes in grass all round, a sandy path winding back, a bamboo fence, a lime-plastered brick farmhouse with a clay-tiled roof and a ve
      spots: toilet, gate, path, field, yard, porch, door, inside, room, desk, hatch, well, shed
      shots: farm_wide, from_gate, through_window, window_out, inside_wide, desk, hatch, toilet, well
  farmhouse_office: inside the farmhouse (farm_2026): Deepak's office for now - and the way down to the underground home the 300 acres will hold
      spots: (none - leave stick_spot out)
      shots: (none - let the camera find the faces)
  field_2026: a field in a Madhya Pradesh district, 2026: rows of soybean, a dirt road, an electric line, a village far off - and one of Deepak's weather stations on its pole (50 km from the next one)
      spots: station, road
      shots: station_low, station_close, hands, antenna, station_wide, behind
  highway: a highway across the plains: two lanes with a dashed line, sandy shoulders, fields, street lamps every 25 m, a green sign board, hills far off
      spots: road, shoulder
      shots: roadside, reporter, reporter_close, low, long, above
  home_2026: Deepak's home in a small Madhya Pradesh town, 2026 (before anything went wrong): a two-room pucca house with a flat roof - his first weather station on it and a LoRa mast - a tin-roofed workshop beside it with a workbenc
      spots: (none - leave stick_spot out)
      shots: (none - let the camera find the faces)
  land_2027: the land, 2027: 300 acres of dry scrub near Bhopal with a boundary of stone posts and wire, survey flags, a site office (a tin shed), a digger and the first pit of the underground home with its mounds of earth
      spots: (none - leave stick_spot out)
      shots: (none - let the camera find the faces)
  meeting_room: a secure government meeting room in Delhi: panelled walls, a long table with chairs down both sides, a big screen on the back wall (maps and charts), a lectern beside it, tall windows on the right with the city outside, 
      spots: front, screen, table
      shots: room, screen, table
  panama_office: a research office in Panama: the other end of a phone call
      spots: desk, room
      shots: desk, close, room, side
  ruined_city: a city after the storms (the film's later chapters): broken towers with jagged tops and dark empty windows, rubble across a cracked road, burnt-out cars, dead trees, smoke, under a rust-red sky
      spots: street, rubble
      shots: ruins_wide, street_low, down_road
  site_2027: the underground home's building site (2027-2035): a stepped pit going down in benches of 4 m (the real dig goes 100 m down; we see its top levels and the tunnel mouth at the bottom), a tower crane, dump trucks on the ram
      spots: edge, office, gate
      shots: pit_wide, edge, down, crane, headframe, silos
  storm_coast: Galveston, Texas, in Hurricane Delia: the seafront road (Seawall Boulevard) under a few centimetres of surge water, palms bent down-wind, beach houses up on stilts with roofs torn off, leaning power poles and their wires
      spots: street, road
      shots: reporter, reporter_close, street_wide, street_up, aerial, coast_wide, coast_high, storm_low
  texas_lab: Mark's research office in Texas (desk, monitors, a flag): the other end of a phone call
      spots: desk, room
      shots: desk, close, room, side
  tunnel_2030: inside the underground works (a mine tunnel, as in the cut-away): a rock tunnel 6 m wide and 4.5 m high, open on the camera side like a stage, steel arches every 4 m, lamps along the roof, rails with ore carts, the tunne
      spots: tunnel, face, lift
      shots: tunnel, down_tunnel, face, lift
  village: a small Indian village around an open square (huts, houses, trees, a well)
      spots: (none - leave stick_spot out)
      shots: (none - let the camera find the faces)
  village_2030: the same village in 2030 under a white-hot UV sky: dry, cracked, shaded, people in masks
      spots: (none - leave stick_spot out)
      shots: (none - let the camera find the faces)

SCENE FIELDS (Stick 3D only)
  "stick_place", "stick_spot", "stick_shot", "stick_shot_hold": true (keep that one camera - a TV news camera)
  "stick_time": sunset | evening | dawn | morning | night
  "mood": the beat's colour grade + music: calm | warm | hope | wonder | secret | tense | danger | sad | doom | monsoon | hurricane
  "transition": "cut"     "tail": seconds of picture after the last event (default 1.2; 0.1 for inserts)
  "characters": [{"id", "x", "z", "hidden"}]   "props": [{"id", "type", "held_by" | "x", "z"}]  prop types: antenna, bag, book, bottle, box, bucket, coil, cup, drum, laptop, map, mic, paper, phone, pot, spade, station, stick, tablet, toolbox
  "stick_cars": [{"id", "kind", "color" (name or #hex), "from", "to", "start", "end", "heading", "path": [{x, z}],
                 "rider": "<character id>", "lights": bool, "mud": bool, "door": [open s, close s],
                 "fly": {"at": s, "rock": deg} (a gust rocks a parked car), "alt": metres (helicopters)}]
      kinds: car, suv, police, agent, pickup, bike, motorbike, scooter, dump_truck, excavator, bulldozer, mixer, loader, helicopter, apache
  "stick_follow": {"car": id, "side": behind | side | front | drone | driver | profile | shoulder | pov | drone_behind}
  "stick_screen": {"kind": ...} a full-frame insert instead of the 3D place: box_inside, call, car_nav, chat, csv, cutaway, data, doc, document, forum, gps, graphs, land, laptop, log, map, mine, mp_map, navigation, news, open_box, plan, reddit, sheet, station_box, station_log, tv, underground, world_map
  "stick_live": {"channel", "name", "role", "place", "ticker", "fall_at": s} - seen through a TV news camera
  "stick_hurricane": {"eye": [0.5, 0.45], "size": 0.8, "glow": bool} the storm's spiral in the sky
  "stick_debris": 0..1.5 (planks, tin, leaves flying)  "stick_panic": 1 (people screaming)  "stick_lens_rain": 1
  "stick_shake": [{"start", "end", "amount"}]  "stick_hail": {"start", "end"}  "stick_stormwall": {"start", "end"}
  "stick_blackout": {"at": s}  "stick_burnt": true  "stick_muddy": ["<id>", ...] (muddy shoes)
  "stick_bubbles": true (speech bubbles; default off - the voices speak)

EVENTS (run one after another; "at": s = at that second; "with": "prev" = together with the one before)
  {"who", "say": "...", "emotion": happy | sad | angry | scared | surprised | worried | excited | calm}   (+ "voice_file", "from", "to" for a recorded take)
  {"who", "do": "<action>", "to": {"x", "z"}, "target": "<id>", "prop": "<id>", "facing": "camera"}
  {"weather": clear | sunny | clouds | overcast | drizzle | rain | storm | fog | snow | windy | cyclone | calm | rain_comes | storm_comes | passing_shower | storm_passes | rain_stops | fog_rolls_in | fog_lifts | snow_starts | snow_stops | wind_picks_up | wind_dies_down, "over": s, "react": false}
  {"effect": lightning | sparks | fire | smoke | explosion | dust | rocks, "x", "z"}     {"sound": "<sound>"}     {"wait": s}
  a child on a hip: {"who": "kid", "do": "carried", "by": "<mother>", "on": "hip"}

ACTIONS: angry, appear, bathe, block, bow, brace_wind, brush_teeth, carried, carry, celebrate, check_shoe, clap, climb, couple_dance, cover_head, crawl, cry, dance, disappear, drink, drop, eat, fall, feel_rain, fight, flung, give, hide, hit, hold_hands, hop_down, hug, hug_pair, idle, jump, kick, kiss, kissed, kneel_propose, knocked_out, laugh, lie, lift_person, look_around, look_at, look_back, look_down, look_up, mount, nod, open, overjoyed, peek, perch, pick, point, pull, pull_hand_back, punch, push, put, reach, retreat, ride, roll_over, run, sad, scared, shout, shove, shrug, sit, sit_on, sit_up, slap, sleep, smash, stand, step_up, stir, stop, stretch, struggle, stumble, surprised, sweep, talk, think, throw, throw_person, touch, turn, wake, walk, wash_face, wave

SOUNDS: applause, bag_thud, bark, bell, bird, birds, bite, bleat, boing, boom, car, car_door, car_horn, cat, caw, chirp, chopper, clang, clap, cluck, coo, cow, crackle, crash, creak, crow, crowd_panic, crunch, ding, dog, door, door_close, door_open, drag, drink, duck, eagle, eat, elephant, engine, explosion, fall, fan, firework, fireworks, fizz, flap, footstep, footsteps, goat, growl, gulp, hail, heartbeat, helicopter, hen, hiss, hit, hoof, hoot, horn, horse, howl, jump, kiss, knock, land, launch, leaves, lion, magic, meow, metal, moo, muah, neigh, no_signal, oink, owl, panic, parrot, patakha, paw, phone, pigeon, plop, pop, punch, quack, ring, roar, rocket, roll, rotor, rumble, run_step, running, rustle, sack, scrape, scream, screech, shout, sing, siren, slap, slip, smack, smooch, snore, sparkle, sparkler, splash, squawk, static, step, stomp, success, swallow, swoosh, tada, thappad, thud, thunder, tiger, trumpet, tweet, whoosh, wings, wolf, zap

CHARACTER LOOKS (in "characters" at the top): "name", "gender": male | female, "age": child | toddler | adult | old,
  "skin": light | brown | dark, "shirt", "pants", "dress", "hair": short | bob | bunches, "hair_col", "cap": true,
  "hood": true | "rain" (a raincoat hood), "cloth" (cap / hood colour), "shades", "goggles", "mask", "mustache",
  "beard", "to_camera": true (a reporter who talks to the lens), "species": "dinosaur",
  "voice": {"name": "en-IN-PrabhatNeural", "pitch": -4}

A SHORT EXAMPLE (the shape, not the story to copy):
{"title": "The Last Signal", "settings": {"art": "stick3d", "stick_look": "flat", "stick_cinema": true, "language": "en-IN", "music": "mystery", "subtitle": "Episode 1"},
 "characters": {
  "deepak": {"name": "Deepak", "shirt": "#4f9aad", "pants": "#36435f", "cap": true, "cloth": "#1e2125", "voice": {"name": "en-IN-PrabhatNeural"}},
  "mark": {"name": "Dr. Mark Ellis", "skin": "light", "shirt": "#f2c230", "hood": "rain", "cloth": "#f2c230", "to_camera": true, "voice": {"name": "en-US-GuyNeural"}}
 },
 "scenes": [
  {"id": "s1_station", "stick_place": "corn_field", "stick_spot": "station", "stick_shot": "station_close", "stick_time": "morning", "mood": "monsoon", "transition": "cut", "characters": [{"id": "deepak", "x": 960, "z": 120}, {"id": "mark", "x": -900, "hidden": true}], "props": [{"id": "phone", "type": "phone", "held_by": "deepak"}], "stick_cars": [{"id": "truck", "kind": "pickup", "color": "#e6e4dc", "mud": true, "to": {"x": 200, "z": -39}, "heading": 0}], "events": [{"weather": "rain", "over": 0, "react": false}, {"who": "deepak", "do": "look_down"}, {"who": "deepak", "say": "Battery full... all readings normal.", "emotion": "happy"}, {"sound": "phone"}, {"who": "deepak", "say": "Mark? It's six in the morning in Texas...", "emotion": "surprised"}]},
  {"id": "s2_call", "transition": "cut", "mood": "tense", "tail": 0.1, "characters": [{"id": "deepak", "x": -900, "hidden": true}], "stick_screen": {"kind": "call", "name": "Mark Ellis", "from": "Galveston, Texas", "answer_at": 0.8}, "events": [{"wait": 1.4}]}
 ]
}

THE STORY:
<PASTE YOUR STORY HERE>

Answer with the JSON only.
