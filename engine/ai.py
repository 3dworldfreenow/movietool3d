"""Gemini integration: one-line idea -> full story -> validated story JSON.

Configure once (any of these):
    python main.py config --gemini-key YOUR_KEY --model gemini-2.5-flash
    export GEMINI_API_KEY=YOUR_KEY            (environment variable wins over config.json)
    the Settings panel in the web app

Get a free key at https://aistudio.google.com/apikey
List the model versions your key can use:   python main.py models
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(HERE, "config.json")
PROMPT_PATH = os.path.join(HERE, "prompts", "story_to_json_prompt.md")
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_API_VERSION = "v1beta"
BASE = "https://generativelanguage.googleapis.com"


class GeminiError(Exception):
    pass


class GeminiUnavailable(GeminiError):
    """Gemini can't be used right now (no key, bad key, quota, network). Carries the ready-to-paste prompt."""
    def __init__(self, msg, prompt=""):
        super().__init__(msg)
        self.prompt = prompt


FALLBACK_HINT = ("Gemini is not available, so use any chatbot instead:\n"
                 "  1. Copy the prompt (saved to {path})\n"
                 "  2. Paste it into ChatGPT / Gemini website / Claude and send\n"
                 "  3. Save the JSON answer as a .json file and run:  python main.py <file>.json\n"
                 "     (or paste it into the Story JSON box in the web app)")
MANUAL_PROMPT = os.path.join(HERE, "prompts", "manual_prompt.txt")


# ---------------------------------------------------------------------------- config
def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(**kw):
    cfg = load_config()
    for k, v in kw.items():
        if v is None:
            continue
        if v == "":
            cfg.pop(k, None)
        else:
            cfg[k] = v
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(CONFIG_PATH, 0o600)       # key file readable only by you
    except OSError:
        pass
    return cfg


def get_key(cfg=None):
    cfg = cfg if cfg is not None else load_config()
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or cfg.get("gemini_api_key", "")


def mask(key):
    return f"...{key[-4:]}" if key and len(key) > 8 else ("set" if key else "")


def settings(overrides=None):
    """Effective AI settings: CLI/web overrides > config.json > defaults."""
    cfg = load_config()
    o = {k: v for k, v in (overrides or {}).items() if v not in (None, "")}
    return {
        "key": o.get("key") or get_key(cfg),
        "model": clean_model(o.get("model") or cfg.get("gemini_model") or DEFAULT_MODEL),
        "api_version": o.get("api_version") or cfg.get("gemini_api_version") or DEFAULT_API_VERSION,
        "temperature": float(o.get("temperature", cfg.get("gemini_temperature", 0.9))),
    }


def clean_model(m):
    m = str(m).strip()
    return m[len("models/"):] if m.startswith("models/") else m


# ---------------------------------------------------------------------------- client
class Gemini:
    def __init__(self, key, model=DEFAULT_MODEL, api_version=DEFAULT_API_VERSION, timeout=240, log=print):
        if not key:
            raise GeminiError("No Gemini API key. Run:  python main.py config --gemini-key YOUR_KEY\n"
                              "(free key: https://aistudio.google.com/apikey)")
        self.key, self.model = key, clean_model(model)
        self.api_version, self.timeout, self.log = api_version, timeout, log

    def _request(self, method, path, body=None):
        url = f"{BASE}/{self.api_version}/{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json", "x-goog-api-key": self.key})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                try:
                    msg = json.load(e).get("error", {}).get("message", "")
                except Exception:
                    msg = ""
                if e.code in (429, 500, 503) and attempt < 3:
                    wait = 5 * (attempt + 1) * (3 if e.code == 429 else 1)
                    self.log(f"  Gemini busy ({e.code}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise GeminiError(_explain(e.code, msg, self.model)) from None
            except urllib.error.URLError as e:
                if attempt < 2:
                    time.sleep(3)
                    continue
                raise GeminiError(f"Can't reach Gemini ({e.reason}). Check your internet connection.") from None
            except TimeoutError:
                if attempt < 1:
                    continue
                raise GeminiError("Gemini took too long to answer. Try again or use a faster model.") from None

    def list_models(self):
        out, token = [], None
        while True:
            q = "models?pageSize=100" + (f"&pageToken={token}" if token else "")
            r = self._request("GET", q)
            for m in r.get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    out.append({"name": clean_model(m["name"]), "display": m.get("displayName", ""),
                                "input_limit": m.get("inputTokenLimit"), "output_limit": m.get("outputTokenLimit")})
            token = r.get("nextPageToken")
            if not token:
                break
        return sorted(out, key=lambda m: m["name"], reverse=True)

    def generate(self, prompt, system=None, json_mode=True, temperature=0.9, max_tokens=32768, images=None):
        """images: optional [(mime_type, bytes)] sent with the prompt (Gemini looks at them)."""
        import base64
        parts = [{"inline_data": {"mime_type": m, "data": base64.b64encode(b).decode()}} for m, b in (images or [])]
        parts.append({"text": prompt})
        body = {"contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        r = self._request("POST", f"models/{self.model}:generateContent", body)
        fb = r.get("promptFeedback", {})
        if fb.get("blockReason"):
            raise GeminiError(f"Gemini blocked the request ({fb['blockReason']}). Try rewording the idea.")
        cands = r.get("candidates") or []
        if not cands:
            raise GeminiError("Gemini returned no answer. Try again.")
        c = cands[0]
        text = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", []) if not p.get("thought"))
        reason = c.get("finishReason", "")
        if reason == "MAX_TOKENS":
            self.log("  ! answer was cut off (MAX_TOKENS) - will try to repair")
        elif reason in ("SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST"):
            raise GeminiError(f"Gemini stopped the answer ({reason}). Try rewording the idea.")
        if not text.strip():
            raise GeminiError(f"Gemini returned an empty answer (finishReason={reason}).")
        return text


def _explain(code, msg, model):
    low = msg.lower()
    if code == 400 and ("api key" in low or "api_key" in low):
        return "Your Gemini API key is invalid. Get a new one at https://aistudio.google.com/apikey"
    if code == 403:
        return f"Permission denied for this key ({msg}). Is the Generative Language API enabled for it?"
    if code == 404:
        return (f"Model '{model}' not found for this API version. Run `python main.py models` to see "
                f"the model names your key can use.")
    if code == 429:
        return "Gemini quota / rate limit reached. Wait a minute, or switch to a lighter model (e.g. a 'flash' model)."
    return f"Gemini API error {code}: {msg or 'unknown error'}"


# ---------------------------------------------------------------------------- JSON helpers
def extract_json(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("no JSON object found in the answer")
    t = t[a:b + 1]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        t2 = re.sub(r",\s*([}\]])", r"\1", t)                 # trailing commas
        t2 = re.sub(r"//[^\n\"]*\n", "\n", t2)                   # // comments
        return json.loads(t2)


# ---------------------------------------------------------------------------- story creation
SYSTEM = ("You are an award-winning children's cartoon writer and storyboard artist. You write short, "
          "warm, funny, visual stories for a YouTube stickman animation channel, and you always answer "
          "with valid JSON only.")


def build_prompt(idea, scenes=None, minutes=None, language=None, style=None, audience=None, full_story=False,
                 include=None, world=None, physics=False, notes=None):
    """notes: extra text for the request (the writers' room: the series bible and the director's notes).
    include = {group: [ids]} picks which library items (characters, species, places, pictures, kits, puppets)
    the prompt lists; a group that is left out means all of it."""
    from .prompt_builder import build_prompt_text
    from .episodes import recent_summaries
    s3d = str(world or "").lower() == "stick3d"
    if s3d:                                              # 🧊 Stick 3D: only what that renderer draws, and the
        from . import prompt_stick3d                     # director's rules for every scene
        base = prompt_stick3d.build() + "\n\nTHE STORY:\n<PASTE YOUR STORY HERE>\n\nAnswer with the JSON only."
    else:
        base = build_prompt_text(recent_summaries(), include, world)
    req = []
    if full_story:
        req.append("Here is the finished story. Stay faithful to it.")
    else:
        req.append("This is only an IDEA. First invent a complete original story with a clear beginning, "
                   "a problem, a funny or emotional middle, and a satisfying ending (a moral if it fits). "
                   "Give characters memorable names and personalities. Then turn it into the JSON.")
    if scenes:
        req.append(f"Use exactly {int(scenes)} scenes.")
    if minutes:
        req.append(f"Target total length: about {float(minutes):g} minute(s) of video "
                   f"(roughly {int(float(minutes) * 130)} words of narration + dialogue in total).")
    if language:
        from .tts import LANG_NAMES
        name = LANG_NAMES.get(language, language)
        native = {"hi": "Devanagari", "mr": "Devanagari", "ta": "Tamil script", "te": "Telugu script",
                  "bn": "Bengali script", "gu": "Gujarati script", "kn": "Kannada script", "ml": "Malayalam script"}
        script = native.get(str(language)[:2])
        req.append(f'Set settings.language to "{language}".'
                   + (f" Write ALL narration and dialogue in {name} ({script}); keep the title, captions and "
                      f"end text in English." if script else ""))
    if style:
        req.append(f"Style / tone: {style}.")
    if audience:
        req.append(f"Audience: {audience}.")
    req.append("Vary backgrounds between scenes, use props where they help, and use the camera cinematically.")
    if physics:                                          # ⚛ a physics lesson for schools
        req.append('This is a PHYSICS LESSON video for school students: set settings.physics to "real", '
                   'settings.camera_mode and settings.world to "3d". A teacher (or curious children) shows 3-6 real '
                   'experiments with {"experiment": ...} events (see PHYSICS EXPERIMENTS), each followed by narration '
                   '(with "with": "prev") that explains what we see with the real numbers and the formula; use '
                   '{"freeze": "<id>", "duration": 3} to pause and explain, "slowmo": 0.5 for fast things, and change '
                   'one number in a second run of the same experiment to compare. End with a short recap. Every number said in '
                   'a line (seconds, metres, m/s, g ...) must be the experiment\'s real result - the engine checks '
                   'each one against its formulas.')
    if physics and not s3d and "PHYSICS EXPERIMENTS" not in base:    # a 2D / mixed prompt: add the experiments list too
        from .prompt_builder import _physics_list
        req.append('PHYSICS EXPERIMENTS: {"experiment": "<name>", "id": "e1", "x": 1200, "z": 400, ...numbers...}; '
                   '{"freeze": "e1", "duration": 3}; "slowmo": 0.5; "planet": "moon". Experiments:\n' + _physics_list())
    from .prompt_builder import world_block
    wb = None if s3d else world_block(world, base_done=True)
    if wb:
        req.append(wb)
    if notes:
        req.append(str(notes).strip())
    block = "\n".join("- " + r for r in req) + "\n\n" + str(idea).strip()
    return base.replace("<PASTE YOUR STORY HERE>", block)


def repair_prompt(data_or_text, problems):
    body = data_or_text if isinstance(data_or_text, str) else json.dumps(data_or_text, ensure_ascii=False)
    return ("The JSON below has problems. Fix ALL of them and return the COMPLETE corrected JSON "
            "(same story, same schema). Only the JSON.\n\nProblems:\n"
            + "\n".join(f"- {p}" for p in problems[:25]) + "\n\nJSON:\n" + body)


def slug(text, n=40):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(text)).strip("_").lower()
    return s[:n] or "story"


def create_story(idea, validate, out_dir, overrides=None, scenes=None, minutes=None, language=None,
                 style=None, audience=None, full_story=False, max_repairs=2, log=print, tick=None, include=None,
                 world=None, physics=False, room=None):
    """idea -> validated story JSON file. `validate(path)` returns a list of problem strings.
    tick(label, elapsed, expected) is called every second while waiting for Gemini.
    room: the writers' room (engine/writersroom.py: series bible -> beat sheet -> story doctor -> screenplay with
    the director's notes -> film checks). None = on for an idea, off for a finished story (it still gets the bible
    and the director's notes); False = the old one-pass way."""
    from . import timing, writersroom as wr
    st = settings(overrides)
    series = wr.detect_series(idea, world)
    bible = wr.series_bible(series)
    use_room = (not full_story and not physics) if room is None else bool(room)
    notes = ("SERIES BIBLE (keep every character in character):\n" + bible + "\n\n" if bible else "") + wr.DIRECTOR_NOTES

    if str(world or "").lower() == "stick3d":           # 🧊 the director's check: wrong spots / shots / cast
        _v = validate                                    # are sent back to Gemini to fix, like other problems

        def validate(path, _v=_v):
            from . import prompt_stick3d
            probs = list(_v(path) or [])
            with open(path, encoding="utf-8") as f:
                probs += [f"scene {i}: {p}" for i, p in prompt_stick3d.check(json.load(f))]
            return probs

    def make(text, full):
        return build_prompt(text, scenes, minutes, language, style, audience, full, include, world,
                            physics=physics, notes=notes)
    full_prompt = make(idea, full_story)
    ctx = {"wr": wr, "idea": idea, "bible": bible, "people": wr.cast(series) if series else {},
           "minutes": minutes, "scenes": scenes, "make": make} if use_room else None
    try:
        return _create(full_prompt, idea, st, validate, out_dir, max_repairs, log, tick, timing, room=ctx)
    except GeminiError as ex:
        msg = str(ex)
        if isinstance(ex, GeminiUnavailable) or any(k in msg.lower() for k in (
                "no gemini api key", "invalid", "quota", "rate limit", "can't reach", "permission", "too long",
                "not found", "api error 5", "busy")):
            os.makedirs(os.path.dirname(MANUAL_PROMPT), exist_ok=True)
            manual = wr.manual_prompt(full_prompt) if use_room else full_prompt
            with open(MANUAL_PROMPT, "w", encoding="utf-8") as f:
                f.write(manual)
            raise GeminiUnavailable(msg, manual) from None
        raise


def _create(full_prompt, idea, st, validate, out_dir, max_repairs, log, tick, timing, room=None):
    g = Gemini(st["key"], st["model"], st["api_version"], log=log)
    exp = timing.gemini_estimate(st["model"])
    log(f"  asking Gemini ({st['model']}) to write the story - usually takes ~{timing.fmt(exp)}")
    t0 = time.time()

    def ask(prompt, temperature, label, key, expected, system=SYSTEM):
        cb = (lambda el: tick(label, el, expected)) if tick else (lambda el: None)
        with timing.Ticker(cb) as tk:
            out = g.generate(prompt, system=system, temperature=temperature)
        if tick:
            tick(None, tk.elapsed, expected)          # lets the console end its \r line
        timing.record(key, tk.elapsed)
        return out

    plan = None
    if room:                                       # 🎬 the writers' room plans the episode first
        wr = room["wr"]
        plan = wr.plan_episode(lambda p, t, label: ask(p, t, label, f"gemini:{st['model']}", exp, wr.WRITER_SYSTEM),
                               room["idea"], room["bible"], room["minutes"], room["scenes"], wr.recent_titles(),
                               room["people"], log, extract_json)
        if plan:
            full_prompt = room["make"](wr.plan_to_story(plan), True)
    text = ask(full_prompt, st["temperature"], "writing story", f"gemini:{st['model']}", exp)
    os.makedirs(out_dir, exist_ok=True)
    data, path = None, None
    for attempt in range(max_repairs + 1):
        problems = []
        try:
            data = extract_json(text)
        except (ValueError, json.JSONDecodeError) as ex:
            problems = [f"The answer is not valid JSON: {ex}"]
            data = None
        if data is not None:
            if not data.get("scenes"):
                problems.append("There are no scenes.")
            if path is None:
                path = os.path.join(out_dir, f"{slug(data.get('title') or idea)}_{time.strftime('%Y%m%d_%H%M%S')}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if not problems:
                problems = validate(path)
            if not problems and room and attempt < max_repairs:     # the film checks (soft: only while repairs are left)
                problems = room["wr"].direction_problems(data, room["people"], (plan or {}).get("main"))
        if not problems:
            log(f"  story ready in {time.time() - t0:.0f}s: \"{data.get('title', '')}\" "
                f"({len(data.get('scenes', []))} scenes)")
            return data, path
        if attempt == max_repairs:
            break
        rexp = timing.estimate(f"gemini_repair:{st['model']}", timing.DEFAULTS["gemini_repair"])
        log(f"  fixing {len(problems)} problem(s) with Gemini (attempt {attempt + 1}/{max_repairs}, ~{timing.fmt(rexp)})...")
        text = ask(repair_prompt(data if data is not None else text, problems), 0.3, "fixing story",
                   f"gemini_repair:{st['model']}", rexp)
    if data is None:
        raise GeminiError("Gemini did not return usable JSON after repairs. Try again or another model.")
    log(f"  ! {len(problems)} small problem(s) remain; the engine will auto-correct them when rendering.")
    return data, path



# ---------------------------------------------------------------------------- translation (dual language)
def _spoken_lines(data):
    """[(ref, field, text)] for every spoken line: ref = the dict that holds it."""
    out = []
    for sc in data.get("scenes", []):
        if isinstance(sc.get("narration"), str):
            out.append((sc, "narration", sc["narration"]))
        for e in sc.get("events", sc.get("actions", [])) or []:
            if not isinstance(e, dict):
                continue
            for f in ("narrate", "narration", "say", "dialogue", "line"):
                if isinstance(e.get(f), str) and e[f].strip():
                    out.append((e, f, e[f]))
                    break
    return out


def translate_prompt(data, target):
    from .tts import LANG_NAMES
    lines = _spoken_lines(data)
    name = LANG_NAMES.get(target, target)
    items = {str(i + 1): text for i, (_, _, text) in enumerate(lines)}
    extra = " Write in Devanagari script." if target.startswith(("hi", "mr")) else ""
    return (f"Translate these lines of a children's cartoon into natural, simple spoken {name}.{extra} "
            "Keep character names as they are, keep it short and warm, and keep the same meaning and emotion. "
            "Answer with ONLY a JSON object that has the SAME keys and the translated text as values.\n\n"
            + json.dumps(items, ensure_ascii=False, indent=1)), lines


def apply_translation(data, target, answer, lines=None):
    """Insert translated lines as '<field>_<code>' next to the originals and add the language to settings."""
    if lines is None:
        lines = _spoken_lines(data)
    code = target.split("-")[0].lower()
    tr = extract_json(answer) if isinstance(answer, str) else answer
    done = 0
    for i, (ref, field, _) in enumerate(lines):
        t = tr.get(str(i + 1))
        if t:
            ref[f"{field}_{code}"] = str(t)
            done += 1
    st = data.setdefault("settings", {})
    langs = [l for l in (st.get("languages") or []) if l]
    if target not in langs:
        langs.append(target)
    st["languages"] = langs
    return done, len(lines)


def translate_story(data, target, overrides=None, log=print, chunk=60):
    """Gemini translates every spoken line. Returns (translated, total)."""
    st = settings(overrides)
    g = Gemini(st["key"], st["model"], st["api_version"], log=log)
    lines = _spoken_lines(data)
    answer = {}
    for k in range(0, len(lines), chunk):
        part = {"scenes": [{"events": [{"say": t} for _, _, t in lines[k:k + chunk]]}]}
        prompt, _ = translate_prompt(part, target)
        log(f"  translating lines {k + 1}-{min(k + chunk, len(lines))} of {len(lines)} ...")
        got = extract_json(g.generate(prompt, temperature=0.3))
        for kk, v in got.items():
            try:
                answer[str(int(kk) + k)] = v
            except ValueError:
                pass
    return apply_translation(data, target, answer, lines)
