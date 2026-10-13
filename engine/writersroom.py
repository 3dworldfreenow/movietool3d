"""🎬 The writers' room: an episode is written the way a TV show writes one, not in one shot.

    1. series bible   - who the people are, their habits and catchphrases, the town, the tone
                        (prompts/series/<series>.md + the cast file + the world's places)
    2. beat sheet     - Gemini plans the episode: logline, theme, plants and payoffs, and the beats
                        (cold open, problem, rising trouble, midpoint surprise, low point, climax, button)
    3. story doctor   - a second read scores the plan (hook, stakes, escalation, character moments, payoffs,
                        climax, ending, comedy, visuals) and rewrites the weak beats
    4. screenplay     - the plan goes to the normal story -> JSON prompt as a finished story, with the
                        director's notes (shot grammar)
    5. checks         - code checks on the plan and on the final JSON (hook, camera variety, close-ups on the
                        feelings, short lines, everyone gets a moment); problems go to the repair loop

Without a Gemini key the manual prompt asks a chatbot to do the same steps by itself, then give the JSON.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIES_DIR = os.path.join(HERE, "prompts", "series")
CAST_FILES = {"ghatti_nagar": os.path.join(HERE, "assets", "characters", "ghatti_nagar_cast.json")}
WORLD_FILES = {"ghatti_nagar": os.path.join(HERE, "worlds", "ghatti_nagar.json")}

BEATS = ["cold_open", "setup", "problem", "rising", "midpoint", "low_point", "climax", "resolution", "button"]
RUBRIC = ["hook", "goal_and_stakes", "escalation", "character_moments", "setup_payoff", "climax",
          "ending", "comedy", "heart", "visuals"]

WRITER_SYSTEM = ("You are the head writer of a hit family animated TV series. You plan episodes in beats the way "
                 "Pixar and good sitcom rooms do: a hook in the first seconds, a clear goal, trouble that grows, "
                 "a surprise, a low point, a climax the characters earn with who they are, and a final joke. "
                 "You always answer with valid JSON only.")

DIRECTOR_NOTES = """DIRECTOR'S NOTES (shot grammar - follow them, this is a film, not a slideshow):
- Open on the cold open: an image that asks a question, and point settings.hook at the most exciting moment.
- Every scene starts with an establishing shot (wide / extreme_wide / drone) the first time we are in a place,
  then goes closer as the scene gets tense: wide -> medium -> closeup. Cut back wide when people move.
- Feelings get close-ups: every emotional line (sad, scared, crying, surprised, love, angry) is on a closeup or
  extreme_closeup of the speaker, often with "focus_blur": true. The quiet real moment gets a slow_push.
- Conversations: over_shoulder shots, alternating, speakers facing each other; a reaction shot (closeup of the
  listener, no line) after a big line.
- Comedy: crash_zoom on the shocked face, a hold (wide, 1-2 s, nobody talks) after a gag, an insert of the
  object that goes wrong (the gadget, the jalebi, the cold tea).
- Use at least 5 different shot kinds in the episode and never the same shot three times in a row.
- Lines are short (at most ~18 words), with an emotion each; let actions and faces tell what words do not need to.
- Every main character in the episode gets one moment that only they could have (their habit or catchphrase).
- End on the button: a last joke or warm image, then the end text."""


# ---------------------------------------------------------------------------- series bible
def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def cast(series):
    d = _load(CAST_FILES.get(series, "")) or {}
    return d.get("characters") or {}


def detect_series(idea="", world=None):
    """The series this story belongs to: chosen by its world ("3d:ghatti_nagar") or by naming its people."""
    w = str(world or "").lower()
    for s in CAST_FILES:
        if s in w:
            return s
    low = str(idea or "").lower()
    for s in CAST_FILES:
        people = cast(s)
        hits = sum(1 for cid, c in people.items()
                   if cid in low or str(c.get("name", "")).lower() in low)
        if hits >= 1 and (hits >= 2 or s.replace("_", " ") in low or "ghatti" in low):
            return s
    return None


def series_bible(series):
    """The bible as text: the show's notes + every person (id, name, who they are, home) + the town's places."""
    if not series:
        return ""
    parts = []
    p = os.path.join(SERIES_DIR, series + ".md")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            parts.append(f.read().strip())
    people = cast(series)
    if people:
        parts.append("CAST (use these exact ids; they look and sound the same in every episode - just write "
                     '"<id>": {} in "characters"):\n' + "\n".join(
                         f'- {cid}: {c.get("name", cid)} - {c.get("about", "")}' + (f' (home: {c["home"]})' if c.get("home") else "")
                         for cid, c in people.items()))
    w = _load(WORLD_FILES.get(series, "")) or {}
    places = [pl.get("id") or pl.get("name") for pl in w.get("places", []) if isinstance(pl, dict)]
    if places:
        parts.append("PLACES in the town: " + ", ".join(p for p in places if p))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------- 2. beat sheet
def beats_prompt(idea, bible="", minutes=None, scenes=None, recent=None):
    n = int(scenes) if scenes else None
    length = (f"about {float(minutes):g} minute(s)" if minutes else "about 3-5 minutes") + \
             (f", exactly {n} scenes" if n else ", 5-9 scenes")
    rec = ""
    if recent:
        rec = "\nEPISODES ALREADY MADE (do NOT repeat their plots or jokes):\n" + "\n".join(f"- {r}" for r in recent[:12])
    head = ("SERIES BIBLE\n" + bible + "\n") if bible else ""
    return f"""{head}{rec}

TASK: plan ONE episode from this idea ({length}). Do not write the JSON video yet - only the plan.

IDEA:
{str(idea).strip()}

Think like a TV writers' room:
- What does the main character WANT, what stands in the way, what happens if they fail (stakes)?
- Trouble must GROW: each try fails and makes things worse, in a way only that character could fail.
- Plant 1-3 things early (an object, a habit, a line) that PAY OFF in the climax.
- The climax is won by the characters' own habits/skills, not by luck or a stranger.
- One quiet, real feeling (heart) and real jokes (comedy from character). End on a button (last joke/image).

Answer with JSON only:
{{
  "title": "<catchy episode title>",
  "logline": "<one sentence: who wants what, what stands in the way>",
  "theme": "<what it is really about, one line>",
  "main": ["<character ids with the biggest parts>"],
  "plants": [{{"plant": "<set up early>", "payoff": "<how it pays off later>"}}],
  "beats": [
    {{"beat": "<one of {", ".join(BEATS)}>", "where": "<place>", "who": ["<ids>"],
      "what": "<what happens, 2-3 sentences>", "conflict": "<what goes wrong / who is against whom>",
      "feeling": "<the emotion of the beat>", "moment": "<the joke or moving moment of this beat>",
      "shot": "<the key camera shot idea>", "music": "<mood>"}}
  ]
}}
Use every beat in this order: {", ".join(BEATS)} (several beats may share a scene; a long episode may add more
"rising" beats)."""


# ---------------------------------------------------------------------------- 3. story doctor
def doctor_prompt(plan, bible=""):
    head = ("SERIES BIBLE\n" + bible + "\n\n") if bible else ""
    return f"""{head}You are the STORY DOCTOR. Here is an episode plan:

{json.dumps(plan, ensure_ascii=False, indent=1)}

1. Score it 1-10 on: {", ".join(RUBRIC)}. Be strict: a 10 is a great TV episode.
2. For every score under 8 write what is wrong and fix it IN THE PLAN (rewrite those beats; add a plant or a
   payoff; make a try fail worse; give a quiet character a moment; sharpen the button joke; make the cold open
   a question). Keep what works, the same characters and the same idea.
Answer with JSON only:
{{"scores": {{"<rubric>": <1-10>}}, "notes": ["<what you fixed>"], "plan": {{<the full improved plan, same format>}}}}"""


def check_beats(plan, people=None):
    """Code checks on a plan; [] = good."""
    if not isinstance(plan, dict):
        return ["The plan is not a JSON object."]
    out = []
    for k in ("title", "logline"):
        if not str(plan.get(k) or "").strip():
            out.append(f'The plan has no "{k}".')
    beats = plan.get("beats") or []
    if not isinstance(beats, list) or len(beats) < 6:
        out.append("The plan needs at least 6 beats.")
        return out
    have = [str(b.get("beat", "")).lower() for b in beats if isinstance(b, dict)]
    for need in ("cold_open", "problem", "climax", "button"):
        if need not in have:
            out.append(f'Missing the "{need}" beat.')
    if "low_point" not in have and "midpoint" not in have:
        out.append('Add a "midpoint" surprise or a "low_point" - the middle is flat.')
    if not plan.get("plants"):
        out.append("No plants and payoffs: set something up early that pays off in the climax.")
    if people:
        for m in (plan.get("main") or [])[:6]:
            if m not in people:
                out.append(f'Main character "{m}" is not a cast id ({", ".join(list(people)[:8])}).')
    flat = [b.get("beat") for b in beats if isinstance(b, dict) and not str(b.get("conflict") or "").strip()
            and b.get("beat") in ("problem", "rising", "midpoint", "low_point", "climax")]
    if flat:
        out.append("These beats have no conflict: " + ", ".join(map(str, flat)) + ".")
    return out


def plan_to_story(plan):
    """The plan as a finished story for the screenplay pass."""
    L = [f"TITLE: {plan.get('title', '')}", f"LOGLINE: {plan.get('logline', '')}", f"THEME: {plan.get('theme', '')}"]
    for p in plan.get("plants") or []:
        if isinstance(p, dict):
            L.append(f"PLANT: {p.get('plant', '')} -> PAYOFF: {p.get('payoff', '')}")
    L.append("")
    for i, b in enumerate(plan.get("beats") or [], 1):
        if not isinstance(b, dict):
            continue
        L.append(f"{i}. [{str(b.get('beat', '')).upper()}] at {b.get('where', '?')} - {', '.join(b.get('who') or [])}")
        for k in ("what", "conflict", "feeling", "moment", "shot", "music"):
            if b.get(k):
                L.append(f"   {k}: {b[k]}")
    L.append("\nTurn EVERY beat into scenes and events (the cold open becomes the hook). Keep the plants and their "
             "payoffs, the jokes and the quiet moment; write the dialogue now, short and in character.")
    return "\n".join(L)


# ---------------------------------------------------------------------------- 5. direction checks on the JSON
EMO_CLOSE = {"sad", "scared", "crying", "surprised", "love", "angry", "shocked", "worried", "afraid"}
CLOSE = {"closeup", "extreme_closeup", "medium_closeup", "slow_push", "push_in", "dolly_zoom", "crash_zoom", "over_shoulder", "insert", "pov"}


def direction_problems(data, people=None, main=None):
    """Film-making checks on a finished story JSON; [] = good. Soft rules: they ask for a better film."""
    if not isinstance(data, dict) or not data.get("scenes"):
        return []
    out = []
    st = data.get("settings") or {}
    if st.get("hook") in (None, "", "off") or not isinstance(st.get("hook"), dict):
        out.append('settings.hook is not set: point it at the most exciting moment '
                   '{"scene": n, "at": s, "duration": 6, "caption": "<question>"}.')
    kinds, run, last = set(), 0, None
    speakers, long_lines, bare_feelings = {}, [], 0
    for sc in data["scenes"]:
        cam = None
        for ev in sc.get("events") or []:
            if not isinstance(ev, dict):
                continue
            if ev.get("camera"):
                cam = str(ev["camera"])
                kinds.add(cam)
                run = run + 1 if cam == last else 1
                last = cam
                if run == 3:
                    out.append(f'Scene {sc.get("id", "?")}: the same "{cam}" shot three times in a row - vary it.')
            if ev.get("say"):
                who = ev.get("who")
                speakers[who] = speakers.get(who, 0) + 1
                if len(str(ev["say"]).split()) > 24:
                    long_lines.append(str(ev["say"])[:40])
                if str(ev.get("emotion", "")).lower() in EMO_CLOSE and cam not in CLOSE:
                    bare_feelings += 1
    if len(kinds) < 5:
        out.append(f"Only {len(kinds)} kinds of camera shot ({', '.join(sorted(kinds)) or 'none'}): use at least 5 "
                   "(wide, medium, closeup, over_shoulder, crash_zoom, slow_push, drone, insert ...).")
    if long_lines:
        out.append(f"{len(long_lines)} line(s) are too long (over 24 words), e.g. \"{long_lines[0]}...\": split or cut them.")
    if bare_feelings >= 3:
        out.append(f"{bare_feelings} emotional lines are not on a close shot: put a closeup (focus_blur) before them.")
    for m in (main or [])[:6]:
        if m in (data.get("characters") or {}) and not speakers.get(m):
            out.append(f'"{m}" is a main character but never speaks - give them their moment.')
    return out[:8]


# ---------------------------------------------------------------------------- the manual (no key) version
def manual_prompt(full_prompt, bible=""):
    """One prompt a chatbot can follow on its own: plan, doctor, then the JSON."""
    head = ("WORK IN THREE STEPS (write steps 1 and 2 briefly as notes, then the JSON):\n"
            f"STEP 1 - BEAT SHEET: logline, theme, plants and payoffs, and the beats in order: {', '.join(BEATS)}. "
            "Each beat: where, who, what happens, the conflict, the feeling, the joke or moving moment, the key shot.\n"
            f"STEP 2 - STORY DOCTOR: score your plan 1-10 on {', '.join(RUBRIC)}; fix every score under 8.\n"
            "STEP 3 - the final JSON below, from the improved plan, following the director's notes. "
            "Put the JSON last, in one ```json block.\n\n")
    return head + (("SERIES BIBLE\n" + bible + "\n\n") if bible else "") + full_prompt   # (the bible and the director's notes are in full_prompt already)


def plan_episode(ask, idea, bible="", minutes=None, scenes=None, recent=None, people=None, log=print, parse=None):
    """Steps 2-3 with Gemini. ask(prompt, temperature, label) -> text; parse(text) -> JSON. Returns the plan or None."""
    plan = None
    try:
        plan = parse(ask(beats_prompt(idea, bible, minutes, scenes, recent), 0.95, "planning the episode"))
    except (ValueError, json.JSONDecodeError) as ex:
        log(f"  beat sheet was not JSON ({ex}); writing without a plan")
        return None
    log(f"  beat sheet: \"{plan.get('title', '')}\" - {len(plan.get('beats') or [])} beats")
    try:
        doc = parse(ask(doctor_prompt(plan, bible), 0.5, "story doctor"))
        if isinstance(doc, dict) and isinstance(doc.get("plan"), dict) and doc["plan"].get("beats"):
            sc = doc.get("scores") or {}
            if sc:
                log("  story doctor: " + ", ".join(f"{k} {v}" for k, v in sc.items()))
            plan = doc["plan"]
    except (ValueError, json.JSONDecodeError):
        log("  story doctor answer was not JSON; keeping the first plan")
    probs = check_beats(plan, people)
    if probs:
        log("  plan notes: " + "; ".join(probs))
        try:
            fixed = parse(ask("Fix these problems in the episode plan and return the full plan JSON only:\n"
                              + "\n".join("- " + p for p in probs) + "\n\n" + json.dumps(plan, ensure_ascii=False),
                              0.4, "fixing the plan"))
            if isinstance(fixed, dict) and fixed.get("beats"):
                plan = fixed
        except (ValueError, json.JSONDecodeError):
            pass
    return plan


def recent_titles():
    try:
        from .episodes import recent_summaries
        r = recent_summaries()
        if isinstance(r, str):
            return [x.strip("- ").strip() for x in r.splitlines() if x.strip()][:12]
        return [str(x) for x in (r or [])][:12]
    except Exception:  # (no history yet: a fresh studio)
        return []

