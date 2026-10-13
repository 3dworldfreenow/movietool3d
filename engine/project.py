"""Project: loads the story JSON and prepares everything needed to render."""
import bisect
import time
import json
import math
import os

import numpy as np

from .audio import Mixer, lip_curve, write_wav, decode_stereo, SR
from .background import Background
from .camera import CameraDirector
from .character import CharacterDef, make_distinct
from .timeline import VEHICLES
from .music import generate as gen_music, resolve_mood
from .sfx import SfxBank, ambient as gen_ambient, default_ambient
from .subtitles import cues_for, write_srt, Cue
from .timeline import SceneTimeline
from .tts import TTS, build_voice
from .util import hex_to_rgb, clamp, stable_hash


# how a line is spoken for its emotion: (rate %, pitch steps)
EMO_DELIVERY = {"happy": (6, 2), "laughing": (9, 3), "sad": (-10, -2), "crying": (-14, -1), "angry": (7, -2),
                "surprised": (7, 4), "scared": (12, 3), "thinking": (-8, 0), "sleeping": (-16, -3)}


def _line_emotion(e):
    if not isinstance(e, dict):
        return None
    emo = e.get("emotion")
    if not emo and str(e.get("do", "")).lower() in ("cry", "laugh", "angry", "scared", "surprised", "sad", "think"):
        emo = {"cry": "crying", "laugh": "laughing", "think": "thinking"}.get(str(e["do"]).lower(), str(e["do"]).lower())
    return str(emo).lower() if emo else None


# story "settings" a scene can also set for itself (the scene's own value wins)
STORY_TO_SCENE = ("acting", "follow_roads", "drive_side", "exaggeration", "cloth", "anticipation", "walk_mood",
                  "lived_in", "dust", "tracks", "show_mentioned", "palette", "physics", "wind")


BEAT_MUSIC = {"calm": "calm", "warm": "calm", "hope": "adventure", "wonder": "adventure", "secret": "mystery",
              "tense": "tense", "danger": "tense", "sad": "sad", "doom": "sad", "hurricane": "tense", "hall": "tense"}   # a scene's "mood" (its beat) -> score


def _stick3d_ambient(spec, st):
    """the sound of a Stick 3D place by its hour: a farm or a field (birds by day, crickets at night, wind), a
    meeting room (the room's hum), a basement (the fan); None for a screen (the music carries it)"""
    if spec.get("stick_screen"):
        return None
    pl = str(spec.get("stick_place") or "").lower()
    tm = str(spec.get("stick_time") or st.get("stick_time") or "").lower()
    night = tm in ("night", "evening")
    if pl in ("meeting_room", "office"):
        return "room"
    if pl in ("basement_2026", "farmhouse_office"):
        return "fan"
    if pl:
        return ["night", "wind"] if night else ["farm" if "farm" in pl or "field" in pl else "birds", "wind"]
    return None

def _shape_sound(clip, opts, left, seed=0):
    """a story sound event cut to what the scene needs: {"sound": "siren", "for": 4} plays 4 s, "loop": true repeats
    a short sound to fill that (seamless joins), "from_sec": 2.5 skips the start of the file, "fade": 0.5 the fade-out;
    with no "for" it stops where its scene ends (left = seconds to the scene's end) unless "carry": true lets it run
    on into the next scenes"""
    import numpy as np
    from .sfx import _looped
    x = np.asarray(clip, np.float32)
    if opts.get("from"):
        x = x[..., int(max(0.0, float(opts["from"])) * SR):]
    want = opts.get("for")
    if want is None and not opts.get("carry"):
        want = max(0.2, float(left))
    if want is None or x.shape[-1] == 0:
        return x
    n = int(float(want) * SR)
    if opts.get("loop") and x.ndim == 1 and x.shape[-1] < n:
        x = _looped(x, n, np.random.default_rng(seed), fade=0.25)
    if x.shape[-1] > n:                                                # cut, with a short fade so it doesn't click
        x = x[..., :n].copy()
        f = int(min(float(opts.get("fade") or 0.4), want / 3) * SR)
        if f > 0:
            x[..., -f:] *= np.linspace(1, 0, f, dtype=np.float32)
    return x


class MultiClip(dict):
    """Voice audio of one line in every language: {lang: samples}. .texts = {lang: text}."""
    def __init__(self, clips, texts, primary):
        super().__init__(clips)
        self.texts = texts
        self.primary = primary


def voice_clip(clip, lang=None):
    if isinstance(clip, MultiClip):
        return clip.get(lang or clip.primary, clip.get(clip.primary))
    return clip


def line_text(value, lang):
    """A spoken line may be a plain string or {"en": "...", "hi": "..."}."""
    if isinstance(value, dict):
        code = lang.split("-")[0].lower()
        for k in (lang, lang.lower(), code):
            if value.get(k):
                return str(value[k])
        return None
    return value


class _CueLine:
    __slots__ = ("text", "start", "dur")

    def __init__(self, text, start, dur):
        self.text, self.start, self.dur = text, start, dur


class Item:
    """One block on the global timeline: a title card, a scene, or the end card."""

    def __init__(self, kind, start, duration, scene=None, bg=None, spec=None):
        self.kind, self.start, self.duration = kind, start, duration
        self.scene, self.bg, self.spec = scene, bg, spec or {}
        self.cams = None
        self.fade_in = self.fade_out = 0.0

    @property
    def end(self):
        return self.start + self.duration


class Project:
    def __init__(self, story_path, opts=None, log=print):
        opts = opts or {}
        self.log = log
        self.warnings = []
        self.notes = []                  # rules the engine applied by itself (not problems)
        self.story_path = story_path
        with open(story_path, "r", encoding="utf-8") as f:
            try:
                self.data = json.load(f)
            except json.JSONDecodeError as ex:
                raise SystemExit(f"Story JSON is invalid: {ex}\nTip: paste it into jsonlint.com to find the problem.")
        d = self.data
        st = dict(d.get("settings", {}) or {})
        if str(st.get("art") or "").lower() in ("sketch", "stick3d"):   # ✏ the sketch engines draws on the flat 2D stage (its
            st["camera_mode"] = "2d"                           # places' things become pencil drawings): no 3D world
            if str(st.get("world", "")).lower() not in ("", "2d"):
                st.pop("world", None)
            st.pop("map", None)
            st.pop("toon", None)
            for sc_ in d.get("scenes", []) or []:
                if isinstance(sc_, dict):
                    sc_.pop("camera_mode", None)
        self.settings = st
        res = str(opts.get("resolution") or st.get("resolution", "1920x1080"))
        self.W, self.H = (int(v) for v in res.lower().split("x"))
        self.S = self.H / 1080.0
        self.fps = int(opts.get("fps") or st.get("fps", 24 if str(st.get("art") or "").lower() in ("sketch", "stick3d") else 30))
        self.letterbox = bool(opts.get("letterbox", st.get("letterbox", st.get("cinematic_bars", False))))
        self.toon = bool(opts.get("toon", st.get("toon", str(st.get("style", "")).lower() in ("anime", "toon"))))
        self.art = str(st.get("art") or "clean").lower()   # 🖌 "storybook" = the hand-made frame (2.5D, opt-in)
        self.title = d.get("title", "")
        from .tts import norm_lang
        self.language = norm_lang(st.get("language", "en-US"))
        extra = opts.get("languages") or st.get("languages") or []
        if isinstance(extra, str):
            extra = [x for x in extra.replace(";", ",").split(",") if x.strip()]
        # "subtitle_language": the text on screen in another language than the voices (Hindi voices, English text)
        sl = str(st.get("subtitle_language") or "").strip()
        self.sub_both = sl.lower() == "both"             # two lines: the spoken language + the 2nd language
        self.sub_lang = norm_lang(sl) if sl and not self.sub_both else None
        if self.sub_lang == self.language:
            self.sub_lang = None
        if self.sub_lang and self.sub_lang not in [norm_lang(x) for x in extra]:
            extra = list(extra) + [self.sub_lang]
        self.languages = [self.language]
        for l in extra:
            l = norm_lang(l)
            if l and l not in self.languages:
                self.languages.append(l)
        self._missing = {}
        self.base_dir = os.path.dirname(os.path.abspath(story_path))
        self.cache_dir = opts.get("cache", os.path.join(os.getcwd(), "cache"))
        self.subtitles_on = bool(opts.get("subtitles", st.get("subtitles", True)))
        self.sub_style = st.get("subtitle_style", {})
        self.show_narration_subs = bool(st.get("narration_subtitles", True))

        chars = d.get("characters", {})
        if isinstance(chars, list):
            chars = {c.get("id", f"char{i}"): c for i, c in enumerate(chars)}
        chars = self._merge_library(chars, st)
        # 🗿 in a 3D story every person without a look of their own is sculpted from their story card
        # (engine/sculpt_people.py reads the story card too); "sculpt_people": false keeps the older 3D body
        is3d = str(st.get("world", "")).startswith("3d") or st.get("camera_mode") == "3d" or bool(st.get("map"))
        if is3d and st.get("sculpt_people", True) is not False:
            for cid, spec in list(chars.items()):
                if isinstance(spec, dict) and not spec.get("species") and not spec.get("look3d") \
                        and str(spec.get("kind", "human")) == "human":
                    chars[cid] = dict(spec, look3d="sculpt")
        flat_world = str(st.get("world", "")).lower() in ("2.5d", "25d", "2d", "flat")
        self.char_style = str(opts.get("style") or st.get("character_style",
                                                         "toon" if flat_world else "cartoon")).lower()   # 2.5D: the TV-cartoon look
        self.characters = {cid: CharacterDef(cid, spec, i, self.char_style) for i, (cid, spec) in enumerate(chars.items())}
        # 📏 animals at their real size next to the people (a tiger's back at ~1 m, an elephant's at 2.6 m)
        if is3d and st.get("real_size", True) is not False:
            from .animals import REAL_SHOULDER_M, UNITS_PER_M, canon
            from . import char3d
            per_m, ks = UNITS_PER_M, []                      # story units per metre: the people's own size
            for cid, c in self.characters.items():           # (a sculpted person is sized by the legs: often bigger)
                if c.kind == "human" and (chars.get(cid) or {}).get("look3d") == "sculpt":
                    try:
                        from . import sculpt_rig
                        r = char3d.make_rig(c, char3d.pose_at(c, "idle", 0.0)[0])
                        ks.append(sculpt_rig.bone_moves(sculpt_rig.joints_of(sculpt_rig.card_of(c)), r)[0])
                    except Exception:                        # noqa: BLE001
                        pass
            if ks:
                per_m = sorted(ks)[len(ks) // 2]
            for cid, c in self.characters.items():
                real = REAL_SHOULDER_M.get(canon(c.species)) if c.kind == "quadruped" else None
                if not real or "scale" in (chars.get(cid) or {}):
                    continue
                try:
                    r = char3d.make_rig(c, char3d.pose_at(c, "idle", 0.0)[0])
                    back = r.along(1.0)[1] + r.g                 # the top of the shoulders now
                    grow = real * per_m * (0.7 if c.age == "child" else 1.0) / max(back, 1.0)
                    if grow > 1.0:
                        c.scale *= grow
                except Exception:                            # noqa: BLE001 - keep the cartoon size
                    pass
        # 🐅 sculpted animals keep their true shape and the hunters (tiger, lion, leopard, cheetah, wolf) get a fierce face;
        # "animal_style": "cute" gives every animal the cartoon cute shape instead (big head, short chubby legs) - both
        # after the real size is set from the true body, so the animal stays its real size
        if is3d and st.get("sculpt_animals", True) is not False:
            from .animals import canon
            from .sculpt_animals import make_cute, make_fierce, FIERCE
            style = str(st.get("animal_style", "real")).lower()
            for cid, c in self.characters.items():
                if c.kind != "quadruped" or (chars.get(cid) or {}).get("look3d") not in (None, "", "sculpt"):
                    continue
                if style == "cute":
                    c.animal = make_cute(c.animal)
                elif canon(c.species) in FIERCE and (chars.get(cid) or {}).get("fierce", True) is not False:
                    c.animal = make_fierce(c.animal)
        # 🗿 a sculpted hero / heroine with real proportions ("proportions": "real": long legs) is sized by the legs like
        # everyone sculpted - so the rig's legs grow to match, and they stand at their true height next to the toon cast
        for cid, c in self.characters.items():
            spec_ = chars.get(cid) if isinstance(chars.get(cid), dict) else {}
            card_ = spec_.get("sculpt") if isinstance(spec_.get("sculpt"), dict) else spec_
            if c.kind == "human" and spec_.get("look3d") == "sculpt" and "scale" not in spec_ and str(
                    (card_.get("body") or {}).get("proportions", "")).lower() in ("real", "realistic", "heroine", "hero",
                                                                                    "model", "tall"):
                c.scale *= 0.49 / 0.40                     # (engine/sculpt_people.py: hip height 0.49 H real, 0.40 H toon)
        # 🐯 ... and every four-legged animal is sculpted too (engine/sculpt_animals.py); "sculpt_animals": false = off
        if is3d and st.get("sculpt_animals", True) is not False:
            for cid, c in self.characters.items():
                if c.kind in ("quadruped", "bird") and isinstance(chars.get(cid), dict) and not chars[cid].get("look3d"):
                    chars[cid] = dict(chars[cid], look3d="sculpt")
                    c.spec = dict(c.spec or {}, look3d="sculpt")
        for cid, spec in chars.items():                  # 3D looks (assets/code/<name>.py) must exist
            lk = (spec or {}).get("look3d") if isinstance(spec, dict) else None
            if lk == "sculpt" and self.characters[cid].kind != "human":
                continue                                 # a sculpted animal: made from its species
            if lk == "sculpt":                           # 🗿 a sculpted figure (engine/sculpt_rig.py): its card is checked
                from . import sculpt_people
                card = spec.get("sculpt") if isinstance(spec.get("sculpt"), dict) else spec
                for n in sculpt_people.check(card)[1][:3]:
                    self.warn(f"character '{cid}': sculpt card - {n}")
                continue
            if lk:
                from . import codedraw
                got = None
                try:
                    got = codedraw._load(str(lk))
                except Exception as ex:
                    self.warn(f"character '{cid}': the 3D look '{lk}' has a problem ({ex}) - the normal body is used")
                    continue
                if not got or got[2].get("KIND") not in codedraw.CHAR_KINDS:
                    have = sorted(n for n, m in codedraw.list_code().items() if m["kind"] in codedraw.CHAR_KINDS)
                    self.warn(f"character '{cid}': there is no 3D look called '{lk}' (3D looks: {', '.join(have)}) - "
                              f"the normal body is used")
        make_distinct(list(self.characters.values()))
        self.voices_by_lang = {}
        for lang in self.languages:
            def keep(vo):                      # other languages keep pitch/speed but not a named voice
                vo = vo or {}
                return {k: vo[k] for k in ("pitch", "rate") if k in vo}
            seat = {}                          # one person in two costumes (the same name) keeps one voice
            for i, (cid, c) in enumerate(self.characters.items()):
                seat.setdefault(c.name, i)
            vs = {cid: build_voice(c, lang, seat[c.name], (c.voice or {}) if lang == self.language else keep(c.voice))
                  for cid, c in self.characters.items()}
            vs["narrator"] = build_voice(None, lang, 0, (st.get("narrator_voice") or {}) if lang == self.language
                                         else keep(st.get("narrator_voice")))
            self.voices_by_lang[lang] = vs
        self.voices = self.voices_by_lang[self.language]
        cast = []                                        # the voice cast, so you can hear who is who
        for cid, c in self.characters.items():
            v = self.voices.get(cid) or {}
            cast.append(f"{c.name}={str(v.get('edge', '')).split('-')[-1].replace('Neural', '')}"
                        f"{'' if not v.get('pitch') else ('%+d' % v.get('pitch'))}")
        if cast:
            log("  voice cast: " + ", ".join(cast))
        if len(self.languages) > 1:
            if not opts.get("subtitles") and not st.get("burn_subtitles") and not self.sub_lang and not self.sub_both:
                self.subtitles_on = False      # each language gets its own subtitle file/track instead
            log(f"  languages: {', '.join(self.languages)} (timing fits the longest version of every line)")

        self.tts = TTS(opts.get("tts") or st.get("tts_engine", "auto"), self.cache_dir, self.language,
                       warn=self.warn, log=log)
        from .sfx import REAL_DIR
        self.sfx = SfxBank(REAL_DIR, warn=self.warn)                  # (assets/sfx next to the engine: the Sounds panel)
        self.items = []
        self.cues = []
        self.cues_by_lang = {l: [] for l in self.languages}
        self._voice_mem = {}
        st_ = self.data.get("settings") or {}
        if st_.get("world_only") and (st_.get("map") or st_.get("world_map")):
            w_ = self._world_map(st_)                  # "only what is in the world": list what the story added
            if w_ is not None:
                from . import worldmap
                for m in worldmap.only_check(self.data, w_):
                    self.warn(m)
        self._build(opts)

    def _merge_library(self, chars, st):
        """Reuse characters from a library file (characters.json) so a series keeps the same cast."""
        paths = st.get("character_library", [])
        if isinstance(paths, str):
            paths = [paths]
        default = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "characters.json")
        if not paths and os.path.exists(default):
            paths = [default]
        lib = {}
        try:                                            # saved characters (assets/characters/*.json, e.g. the
            from . import registry                      # Ramayan cast) work in EVERY story by id
            lib.update(registry.load()["characters"])
        except Exception as ex:                         # noqa: BLE001
            self.warn(f"saved characters not loaded: {ex}")
        for p in paths:
            full = p if os.path.isabs(p) else os.path.join(self.base_dir, p)
            if not os.path.exists(full):
                full = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p)
            try:
                with open(full, encoding="utf-8") as f:
                    data = json.load(f)
                lib.update(data.get("characters", data))
            except (OSError, ValueError) as ex:
                self.warn(f"character library '{p}' not loaded: {ex}")
        try:                                            # the people and animals who LIVE in the story's world:
            wm = self._world_map(st) if (st.get("map") or st.get("world_map")) else None   # same look every video
            if wm is not None:
                from . import worldmap
                for rid, rv in worldmap.residents(wm).items():
                    lib.setdefault(rid, worldmap.resident_look(rv))
        except Exception as ex:                         # noqa: BLE001 - never stop a story for this
            self.warn(f"world residents not loaded: {ex}")
        out = {}
        for cid, spec in chars.items():
            spec = spec or {}
            base = lib.get(spec.get("from", cid), {})
            if base and "from" not in spec and spec.get("outfit") and base.get("outfit") and \
                    str(spec["outfit"]).lower() != str(base["outfit"]).lower():
                # the story describes its OWN person who only shares the name (a modern "Ram" in a shirt is not
                # the Ramayan's Ram): don't dress him in the saved one's crown and bow
                self.warn(f"fixed: '{cid}' is the story's own person (not the saved '{cid}') - "
                          f"write \"from\": \"{cid}\" to use the saved look")
                base = {}
            merged = dict(base)
            merged.update({k: v for k, v in spec.items() if k != "from"})
            out[cid] = merged
        return out

    def _crowd_person(self, i, rng, spec):
        from .character import SKIN, OUTFITS
        gender = rng.choice(["male", "female"])
        age = rng.choice(["adult", "adult", "adult", "child", "old", "teen"])
        outfits_m = ["shirt", "tshirt", "kurta", "shirt", "tshirt"]
        outfits_f = ["salwar", "saree", "dress", "tshirt", "salwar"]
        cols = ["#e63946", "#457b9d", "#2a9d8f", "#e9c46a", "#f4a261", "#8338ec", "#6a994e", "#bc4749", "#577590"]
        s = {"gender": gender, "age": age, "skin": rng.choice(list(SKIN)[1:7]),
             "outfit": spec.get("outfit") or rng.choice(outfits_m if gender == "male" else outfits_f),
             "shirt": rng.choice(cols), "pants": rng.choice(["#2f3e55", "#34497a", "#5c5c5c", "#8e7a5c", "#f3eee4"]),
             "hair": rng.choice(["short", "curly", "spiky"]) if gender == "male" else rng.choice(["long", "bun", "ponytail", "braid"]),
             "mustache": gender == "male" and rng.random() < 0.3, "glasses": rng.random() < 0.15}
        if s["outfit"] in ("saree", "dress", "salwar"):
            s["accent"] = rng.choice(cols)
        s.update(spec.get("look", {}))
        return CharacterDef(f"crowd_{i}", s, i, self.char_style)

    def _world_detail(self, opts, st):
        """How much of a big world is drawn round a scene: the page / --world-detail > the story's "world_detail" >
        studio_settings.json "world_detail" > low for a quick preview, high for the real video."""
        for v in ((opts or {}).get("world_detail"), st.get("world_detail")):
            if str(v or "").lower() in ("low", "medium", "high"):
                return str(v).lower()
        try:
            from .production import studio
            v = studio().get("world_detail")
            if str(v or "").lower() in ("low", "medium", "high"):
                return str(v).lower()
        except Exception:                                   # noqa: BLE001
            pass
        return "low" if (opts or {}).get("preview") else "high"

    def _world_map(self, st):
        """The big world of this story ("settings": {"map": "sonpur_valley"}) or None."""
        name = st.get("map") or st.get("world_map")
        if not name:
            return None
        if getattr(self, "_wmap", ("", None))[0] == name:
            return self._wmap[1]
        from . import worldmap
        w = worldmap.load(name)
        if w is None:
            self.warn(f"there is no world called '{name}' (worlds: {', '.join(worldmap.list_worlds()) or 'none yet'})")
        self._wmap = (name, w)
        return w

    def _world_objects(self, sc, w, spot, width, i):
        """World objects used by name in this scene's events (sit on 'stone_4', hide behind 'big_banyan' ...)
        become real objects of the scene at their true spot."""
        from . import worldmap
        have = {o.get("id") for k in ("objects", "vehicles") for o in (sc.get(k) or []) if isinstance(o, dict)}
        used = set()
        for e in sc.get("events") or []:
            if isinstance(e, dict):
                for k in ("object", "to", "on", "target", "look_at", "from", "prop", "vehicle", "in", "into"):
                    v = e.get(k)
                    if isinstance(v, str):
                        used.add(v)
        spot.setdefault("exclude", set())
        for oid in sorted(used - have):
            o = w.byid.get(worldmap._clean(oid))
            if not o or not o.get("type") or o.get("place"):
                continue
            got = worldmap.to_story(o["at"], spot["anchor"], spot["heading"], width)
            if got is None:
                d = math.hypot(o["at"][0] - spot["anchor"][0], o["at"][1] - spot["anchor"][1])
                self.warn(f"scene {i + 1}: '{oid}' is {d:.0f} m away from this scene - too far to use here "
                          f"(make a scene \"at\": \"{oid}\" or at a place near it)")
                continue
            typ = o["type"]
            from . import images
            if o.get("state") and images.exists(f"{typ}_{o['state']}"):
                typ = f"{typ}_{o['state']}"
            elif not o.get("state"):                         # after dark: windows lit, lamps on
                from .placegen import _lit_look
                bgs_ = sc.get("background")
                typ = _lit_look(typ, bgs_.get("time") if isinstance(bgs_, dict) else None) or typ
            turn = (o["turn"] - math.degrees(spot["heading"])) if o.get("turn") is not None else None
            from .timeline import vehicle_type
            if vehicle_type(typ) or str((images.info(typ) or {}).get("kind", "")).lower() == "vehicle":
                # a car / cart / boat parked in the world: a REAL vehicle here - people get in and drive it away
                a = math.radians(turn or 0.0)
                sc.setdefault("vehicles", []).append({"id": oid, "type": typ, "x": got[0], "z": got[1],
                                                      "facing": "right" if math.cos(a) >= 0 else "left"})
            else:
                sc.setdefault("objects", []).append({"id": oid, "type": typ, "x": got[0], "z": got[1],
                                                     **({"turn": turn} if turn is not None else {})})
            spot["exclude"].add(o["id"])

    def warn(self, msg):
        if str(msg).startswith("road: "):              # information: a vehicle follows a road / path
            if msg not in self.notes:
                self.notes.append(msg)
                self.log(f"  🛣 {msg[6:]}")
            return
        if str(msg).startswith("fixed: "):             # a real-world rule the engine applied by itself
            if msg not in self.notes:
                self.notes.append(msg)
                self.log(f"  ✓ {msg}")
            return
        if msg not in self.warnings:
            self.warnings.append(msg)
            self.log(f"  ! {msg}")

    # ------------------------------------------------------------------ build
    def _voice_for(self, lang, who, emo=None):
        """The character's own voice, with the delivery of this line's emotion (faster when happy or scared,
        slower and lower when sad or crying)."""
        v = dict(self.voices_by_lang[lang][who])
        d = EMO_DELIVERY.get(str(emo or "").lower())
        if d and self.settings.get("emotional_voices", True):
            v["rate"] = int(v.get("rate", 0)) + d[0]
            v["pitch"] = float(v.get("pitch", 0)) + d[1]
        return v

    def _synth(self, lang, who, text, emo=None):
        who = who if who in self.voices else "narrator"
        emo = str(emo or "").lower() if str(emo or "").lower() in EMO_DELIVERY else None
        key = (lang, who, " ".join(str(text).split()), emo)
        audio = self._voice_mem.get(key)
        if audio is None:
            audio, _ = self.tts.synth(text, self._voice_for(lang, who, emo))
            if emo == "crying" and len(audio) and self.settings.get("emotional_voices", True):
                import numpy as _np                     # a shaky, sobbing voice
                tt = _np.arange(len(audio)) / SR
                audio = (audio * (1.0 - 0.2 * (0.5 + 0.5 * _np.sin(2 * _np.pi * 5.5 * tt)))).astype(_np.float32)
            self._voice_mem[key] = audio
        return audio

    def _translation(self, e, field, lang):
        if not isinstance(e, dict):
            return None
        code = lang.split("-")[0].lower()
        fields = [field] + {"narrate": ["narration"], "say": ["dialogue", "line"]}.get(field, [])
        for f in fields:
            for k in (f"{f}_{code}", f"{f}_{lang}", f"{f}_{lang.lower()}", f"{f}_{lang.replace('-', '_').lower()}"):
                if e.get(k):
                    return str(e[k])
            if isinstance(e.get(f), dict):
                t = line_text(e[f], lang)
                if t:
                    return t
        return None

    def _line_texts(self, text, e=None, field="say"):
        """{lang: text} for one spoken line."""
        primary = line_text(text, self.language)
        if primary is None and isinstance(text, dict):
            primary = next(iter(text.values()), "")
        texts = {self.language: str(primary)}
        for lang in self.languages[1:]:
            t = self._translation(e, field, lang) if e is not None else None
            if t is None and isinstance(text, dict):
                t = line_text(text, lang)
            if t is None:
                self._missing[lang] = self._missing.get(lang, 0) + 1
                t = str(primary)
            texts[lang] = t
        return texts

    def _speak(self, who, text, e=None, field="say"):
        vf = (e or {}).get("voice_file") if isinstance(e, dict) else None
        if vf:                                         # a recorded line (an actor, ElevenLabs...): used as it is
            from .audio import decode_audio
            path = vf if os.path.isabs(vf) else os.path.join(self.base_dir, vf)
            if not os.path.exists(path):                       # (takes uploaded on the web page live in output/)
                path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), vf)
            if os.path.exists(path):
                audio = self._voice_mem.get(("file", path))
                if audio is None:
                    audio = self._voice_mem[("file", path)] = decode_audio(path)
                if e.get("from") is not None or e.get("to") is not None:   # its part of a longer take
                    a = int(float(e.get("from") or 0) * SR)
                    b = int(float(e["to"]) * SR) if e.get("to") is not None else len(audio)
                    audio = audio[max(0, a):max(a, b)]
                return len(audio) / SR, audio
            self.warn(f"voice_file '{vf}' not found - using the built-in voice")
        emo = _line_emotion(e) if field == "say" else None
        if len(self.languages) == 1 and not isinstance(text, dict):
            audio = self._synth(self.language, who, text, emo)
            return len(audio) / SR, audio
        texts = self._line_texts(text, e, field)
        clips = {lang: self._synth(lang, who, t, emo) for lang, t in texts.items()}
        dur = max(len(c) for c in clips.values()) / SR
        return dur, MultiClip(clips, texts, self.language)

    def _voice_lines(self, scenes):
        """[(lang, who, text)] for every spoken line in every language."""
        lines = []
        for sc in scenes:
            if sc.get("narration"):
                lines.append(("narrator", sc["narration"], sc, "narration"))
            for e in sc.get("events", sc.get("actions", [])) or []:
                if not isinstance(e, dict):
                    continue
                n = e.get("narrate") or e.get("narration")
                if n:
                    lines.append(("narrator", n, e, "narrate"))
                s = e.get("say") or e.get("dialogue") or e.get("line")
                w = e.get("who") or e.get("character")
                if s:
                    lines.append((w if w in self.voices else "narrator", s, e, "say"))
        seen, out = set(), []
        saved = dict(self._missing)
        for who, text, e, field in lines:
            emo = _line_emotion(e) if field == "say" else None
            emo = emo if emo in EMO_DELIVERY else None
            for lang, t in self._line_texts(text, e, field).items():
                k = (lang, who, " ".join(str(t).split()), emo)
                if k not in seen:
                    seen.add(k)
                    out.append(k)
        self._missing = saved                       # counted again when the timeline is built
        return out

    def prefetch_voices(self, scenes, workers=None):
        """Generate every voice line in parallel before building timelines."""
        from concurrent.futures import ThreadPoolExecutor
        from . import timing
        lines = [k for k in self._voice_lines(scenes) if k not in self._voice_mem]
        if not lines:
            return
        todo = [k for k in lines if not self.tts.cached(k[2], self._voice_for(k[0], k[1], k[3]))]
        t0 = time.time()
        # first uncached line runs alone: it decides which voice engine works on this machine
        if todo:
            self._synth(*todo[0])
        eng = next(iter(self.tts.used), "espeak")
        n_workers = workers or (8 if eng == "edge" else max(2, os.cpu_count() or 2))
        rest = [k for k in lines if k not in self._voice_mem]
        uncached = max(0, len(todo) - 1)
        per = timing.estimate(f"tts_wall:{eng}", timing.DEFAULTS.get(f"tts_line:{eng}", 0.5) / min(n_workers, 4))
        self.log(f"  voices: {len(lines)} lines ({len(lines) - len(todo)} cached) with '{eng}', "
                 f"{n_workers} in parallel - estimated ~{timing.fmt(uncached * per)}")
        with ThreadPoolExecutor(n_workers) as ex:
            list(ex.map(lambda k: self._synth(*k), rest))
        el = time.time() - t0
        if len(todo) >= 3:
            timing.record(f"tts_wall:{eng}", el / len(todo))
        self.log(f"  voices done in {timing.fmt(el)}")

    def _build(self, opts):
        st = self.settings
        t = 0.0
        self._s3_prev = None
        scenes = self.data.get("scenes", [])
        if not scenes:
            raise SystemExit("Story has no scenes.")
        only = opts.get("scene")
        block = str(opts.get("only_block") or "").lower()     # "title" / "end": just that card (a part of a mix)
        if block not in ("title", "end"):
            block = ""
        if block:
            only = None
        if not block and len(scenes) >= 2:              # 🚗 show the drive between two places
            from . import journey
            scenes = journey.add(scenes, st, str(self.language or "en"), log=self.notes.append)
            if only:                                     # one scene: it comes with the journey that leads to it
                def _leads(k_):                          # a journey scene (or a rocket trip's 3) right before it
                    while k_ + 1 < len(scenes) and scenes[k_ + 1].get("_journey"):
                        k_ += 1
                    return k_ + 1 < len(scenes) and scenes[k_ + 1].get("_orig") == int(only) - 1
                scenes = [s_ for k_, s_ in enumerate(scenes)
                          if s_.get("_orig") == int(only) - 1 or (s_.get("_journey") and _leads(k_))]
        pick = (lambda i_, s_: True) if not only else (lambda i_, s_: s_.get("_orig", i_) == int(only) - 1
                                                       or bool(s_.get("_journey")))
        self.prefetch_voices([] if block else [s for i, s in enumerate(scenes) if pick(i, s)],
                             opts.get("voice_workers"))
        hook_spec = opts.get("hook", st.get("hook", "auto"))
        if isinstance(hook_spec, str) and hook_spec.lower() in ("off", "none", "false", "no"):
            hook_spec = None
        if hook_spec is False or only or block or len(scenes) < 2:
            hook_spec = None
        hook_item = None
        if hook_spec is not None:
            hd = float(hook_spec.get("duration", 6.0)) if isinstance(hook_spec, dict) else 6.0
            hook_item = Item("hook", t, max(3.0, min(hd, 10.0)))
            hook_item.fade_in, hook_item.fade_out = 0.0, 0.25
            self.items.append(hook_item)
            t = hook_item.end
        from .production import flag_on
        if (block == "title" or (not block and flag_on(st.get("title_card", True)))) and self.title and not only:
            it = Item("title", t, float(st.get("title_duration", 2.5 if hook_item else 3.5)))
            it.fade_in, it.fade_out = (0.2 if hook_item else 0.5), 0.5
            self.items.append(it)
            t = it.end
        from . import belongings                         # 🏠 things stay where they were left, scene to scene
        keep_mem = belongings.new_memory() if st.get("remember_things", True) is not False else None
        for i, sc in enumerate(scenes):
            if (only and not pick(i, sc)) or block:
                continue
            keep_key = belongings.place_key(sc) if keep_mem is not None else None
            if keep_mem is not None:
                sc = belongings.inject(sc, keep_mem, keep_key)
            self.log(f"  scene {i + 1}/{len(scenes)}: voices + timeline")
            world_w = float(sc.get("width", sc.get("world_width", 2400)))
            seed = stable_hash(f"{self.title}|{sc.get('id', '')}|{i}") % 1000003
            wsel_ = str(st.get("world", "3d") or "3d").lower()       # full 3D is the default (a story can still say "world": "2d")
            w3 = "" if wsel_ in ("2d", "flat", "2.5d", "classic", "side") else "3d"
            world3d = bool(w3) or bool(opts.get("force3d"))   # the 3D page: EVERY scene is 3D
            bg_spec = sc.get("background", "park")
            planet_ = None
            if sc.get("planet") is not None or st.get("planet") is not None:   # on a planet (engine/galaxy.py)
                from . import galaxy
                try:
                    planet_ = galaxy.resolve(st, sc)
                except Exception as ex:                    # noqa: BLE001
                    self.warn(f"scene {i + 1}: planet not found ({ex})")
                if planet_ is None:
                    self.warn(f"scene {i + 1}: no planet fits '{sc.get('planet', st.get('planet'))}' - try a "
                              f"number, a Solar System name (mars, moon ...) or other words")
                else:
                    bg_spec, extra_ = galaxy.place_spec(planet_, bg_spec)
                    sc = dict(sc)                           # (the story's own dict stays as written)
                    if "palette" not in sc and "palette" not in st:
                        sc["palette"] = extra_["palette"]
                    sc.setdefault("gravity", extra_["gravity"])
                    if "wind" in extra_ and "wind" not in sc:
                        sc["wind"] = extra_["wind"]
                    sc["_planet"] = planet_
                    self.notes.append(f"scene {i + 1}: on {galaxy.describe(planet_)}")
                    if planet_.get("life") and not planet_.get("solar") and sc.get("life") is not False:      # its creatures (engine/alien_life.py)
                        from . import alien_life
                        try:
                            sc = alien_life.populate(planet_, sc, self.characters, world_w,
                                                     lambda cid, spec, k: CharacterDef(cid, spec, k, self.char_style))
                            life_ = alien_life.describe(planet_)
                            if life_:
                                self.notes.append(f"scene {i + 1}: life - {life_}")
                        except Exception as ex:            # noqa: BLE001
                            self.warn(f"scene {i + 1}: planet life skipped ({ex})")
            wspot = None
            wmap = self._world_map(st)
            if wmap is not None:                             # a big world: the scene stands at a place of it
                w3, world3d = "3d", True
                at_ = sc.get("at") or (bg_spec.get("at") if isinstance(bg_spec, dict) else None)
                if at_ is None:
                    at_ = wmap.places[0]["id"] if wmap.places else [wmap.size[0] / 2, wmap.size[1] / 2]
                    self.warn(f"scene {i + 1}: no \"at\" - using '{at_}' of the world '{wmap.name}'")
                try:
                    from . import worldmap
                    wspot = worldmap.scene_spec(wmap, at_, sc.get("look"), bg_spec if isinstance(bg_spec, dict) else None)
                    bg_spec = wspot["bg_spec"]
                    for n_ in wspot["notes"]:
                        self.warn(f"scene {i + 1}: {n_}")
                    if str(wmap.spec.get("look", "")).lower() == "clay":   # 🗿 its places' trees, huts ... in clay too
                        bg_spec = dict(bg_spec, clay=True) if isinstance(bg_spec, dict) else {"preset": bg_spec, "clay": True}
                    from . import registry as _reg
                    pre_w = bg_spec.get("preset") if isinstance(bg_spec, dict) else bg_spec
                    if (_reg.place(pre_w) or {}).get("indoor"):
                        wspot = None                         # inside a house: no fields, trees, ground or hills of the world
                        bg_spec = {k: v for k, v in bg_spec.items() if k in ("preset", "time", "weather", "clay", "mood")}
                    else:
                        self._world_objects(sc, wmap, wspot, world_w, i)
                except ValueError as ex:
                    self.warn(f"scene {i + 1}: {ex}")
            if world3d and st.get("code3d_places", True) is not False:
                from .background import place3d_for
                p3 = place3d_for(bg_spec)
                if p3:                                   # village -> village_3d (real 3D code place, same settings)
                    bg_spec = dict(bg_spec) if isinstance(bg_spec, dict) else {"preset": bg_spec}
                    self.notes.append(f"scene {i + 1}: place '{bg_spec.get('preset')}' -> real 3D '{p3}'")
                    bg_spec["preset"] = p3
            bg = Background(bg_spec, world_w, seed=seed)
            # a room drawn in real 3D (a code place3d: walls, floor, ceiling all round) is a whole world too: the people
            # in it are real 3D figures (sculpted clay in Ghatti Nagar), not flat cartoons pasted on the room
            pre_ = str((bg_spec or {}).get("preset") if isinstance(bg_spec, dict) else bg_spec or "")
            room3d = bg.indoor and pre_.endswith("_3d") and bool(getattr(bg, "place_objects", None))
            bg.full3d = bool(world3d) and (not bg.indoor or room3d) and st.get("full_world", True) is not False
            bg.chars3d = bg.full3d and str(st.get("characters", "3d")).lower() not in ("2d", "flat", "2.5d")
            if wspot is not None:
                bg.worldmap = dict(world=wmap, **wspot, detail=self._world_detail(opts, st))
            if getattr(bg, "_warn_img", None):
                self.warn(f"scene {i + 1}: {bg._warn_img}")
            want3d = world3d or str(sc.get("camera_mode", st.get("camera_mode", opts.get("camera_mode", w3)) or "")).lower() in (
                "3d", "true3d", "true_3d", "world", "depth3d", "2.5d_true")
            if "auto_stage" not in sc:                      # staging in depth: only where the camera can use it
                sc["auto_stage"] = bool(st.get("auto_stage", True)) and want3d
            photo_meta = None
            if want3d and bg.backdrop:                       # your picture: depth layers + its water, before the
                try:                                         # timeline needs to know where the water is
                    from . import photodepth
                    photo_meta = photodepth.status(bg.backdrop["name"])
                    if photo_meta is None:
                        self.log(f"  scene {i + 1}: making 2.5D depth layers for '{bg.backdrop['name']}' ...")
                        photo_meta = photodepth.process(bg.backdrop["name"], log=self.log, preview=False)
                    bg.water_zones = photodepth.zones(photo_meta, world_w)
                except Exception as ex:
                    self.warn(f"scene {i + 1}: could not make 2.5D layers for the picture ({ex}) - using the "
                              f"normal look")
                    photo_meta = False
            sc_tl = sc
            if any(k_ in st and k_ not in sc for k_ in STORY_TO_SCENE):
                sc_tl = dict(sc)                           # story settings the scene does not set itself
                for k_ in STORY_TO_SCENE:
                    if k_ in st and k_ not in sc:
                        sc_tl[k_] = st[k_]
            if isinstance(bg_spec, dict) and bg_spec.get("clay") and not bg.indoor and "lived_in" not in sc_tl:
                sc_tl = dict(sc_tl, lived_in=True)     # 🏘 a clay village is lived in: pots, washing, firewood by the houses
            tl = SceneTimeline(sc_tl, self.characters, self.fps, i, self.warn, self._speak, world_w,
                               crowd_fn=self._crowd_person, bg=bg)
            if keep_mem is not None:
                belongings.record(tl, keep_mem, keep_key)
            deepest = 0.0                                   # the palace / school wall goes behind everyone
            for tr in tl.tracks.values():
                zs = [tr.z0] + [s_.z1 for s_ in tr.segments if s_.z1 is not None]
                deepest = max(deepest, max(z for z in zs if z <= 1000.0) if any(z <= 1000.0 for z in zs) else 0.0)
            for pr_ in tl.props.values():
                try:
                    zp_ = pr_.z_at(0)
                    if zp_ <= 1000.0:
                        deepest = max(deepest, zp_)
                except Exception:
                    pass
            from .background import push_back_walls
            for typ_, z0_, z1_ in push_back_walls(bg, deepest):
                self.notes.append(f"scene {i + 1}: the {typ_.replace('_building', '').replace('lm_', '')} wall was at "
                                  f"depth {z0_:.0f}, people stand up to {deepest:.0f} - moved it back to {z1_:.0f} "
                                  f"so nobody is hidden behind it")
            if bg.water:                                    # boats float on the water surface
                from .timeline import WATER_VEHICLES
                for p in tl.props.values():
                    if p.vtype in WATER_VEHICLES:
                        p.spec["_sea"] = bg.sea_amp()
                        if "y" not in p.spec:
                            wy = bg.water_y()
                            p.states = [(tt, (st[0], st[1], st[2] + wy) if st[0] == "rest" else
                                         ((st[0], st[1], st[2] + wy, st[3], st[4] + wy) + tuple(st[5:]))
                                         if st[0] == "move" else st) for tt, st in p.states]
            mode = str(sc.get("camera_mode", st.get("camera_mode", opts.get("camera_mode", w3)) or "")).lower()
            if world3d:
                if mode not in ("", "3d"):
                    self.notes.append(f"scene {i + 1}: \"camera_mode\": \"{mode}\" ignored - this story is 3D (world 3d)")
                mode = "3d"
            if mode in ("3d", "true3d", "true_3d", "world", "depth3d", "2.5d_true"):
                if bg.backdrop:                             # your own picture: depth layers (photo -> 2.5D)
                    if photo_meta:
                        if photo_meta.get("backend") == "basic":
                            self.warn(f"scene {i + 1}: '{bg.backdrop['name']}' uses basic depth - install PyTorch + "
                                      f"transformers for real depth (see README)")
                        tl.mode3d = True
                        tl.photo3d = bg.backdrop["name"]
                elif bg.preset in ("cave",):
                    self.warn(f"scene {i + 1}: camera_mode 3d does not work for '{bg.preset}' - using the normal "
                              f"2.5D look")
                else:
                    tl.mode3d = True
                    tl.room3d = bool(bg.indoor)            # indoor places become a real 3D room
            it = Item("scene", t, tl.duration, tl, bg, sc)
            trans = str(sc.get("transition", st.get("transition", "fade"))).lower()
            it.fade_in = it.fade_out = 0.4 if trans == "fade" else 0.0
            if str(st.get("art", "")).lower() == "stick3d" and "transition" not in sc:   # Stick 3D, like a film: a
                pl_ = (sc.get("stick_place"), sc.get("stick_screen") is not None)        # straight cut inside one
                prev_ = getattr(self, "_s3_prev", None)                                 # place, a short dip to
                if prev_ is not None and prev_[0] == pl_:                               # black to a new place
                    it.fade_in = prev_[1].fade_out = 0.0
                else:
                    it.fade_in = 0.3
                    if prev_ is not None:
                        prev_[1].fade_out = 0.3
                it.fade_out = 0.3
                self._s3_prev = (pl_, it)
            n = int(round(tl.duration * self.fps)) + 2
            dmode = str(sc.get("director", st.get("director", opts.get("director", "cinematic")))).lower()
            if dmode not in ("off", "none", "manual", "false", "no"):
                from .director import plan as auto_direct
                from .cinema import options as _cin_opts
                tl.cinema = _cin_opts(st, sc, mode3d=tl.mode3d)
                if str(tl.cinema.get("decide", "")).lower() in ("all", "everything", "full") and dmode == "cinematic":
                    dmode = "full"                          # the camera decides every shot itself
                autos = auto_direct(tl, dmode, mode3d=tl.mode3d, film3d=world3d and tl.mode3d, bg=bg)
                if self.art in ("sketch", "stick3d"):       # ✏ a drawn cartoon: locked-off shots and cuts (a
                    for _t, c_ in autos:                        # camera that never stops drifting redraws the whole
                        if isinstance(c_, dict):                # page every frame - slow to make and to encode)
                            c_["drift"] = None
                            c_.pop("foreground", None)
                            c_["type"] = {"establishing": "wide", "push_in": "medium", "pull_back": "wide",
                                          "crane_up": "wide", "crane_down": "wide", "arc": "wide",
                                          "zoom": "medium"}.get(c_.get("type"), c_.get("type"))
                tl.camera = list(tl.camera) + autos             # (the director also fills in the story's shots)
                tl.handheld = float(sc.get("handheld", st.get("handheld",
                                                              0.0 if tl.cinema.get("style") == "feature" or
                                                              self.art in ("sketch", "stick3d") else 0.35)))
            it.cams = CameraDirector(tl, self.fps, world_w).path(n)
            if tl.mode3d:
                from .render import focus_path
                it.focus3d = focus_path(it, self.fps)
            for sp in tl.speeches:
                sp.lip = self._lip(sp.clip)
                if sp.who != "narrator" and st.get("lipsync", True) is not False:
                    try:                                    # mouth shapes + brows / nods / blinks from text + voice
                        from . import lipsync
                        from .audio import SR
                        a = sp.clip.get(sp.clip.primary) if isinstance(sp.clip, MultiClip) else sp.clip
                        if a is not None and len(a):
                            sp.talk = lipsync.analyze(a, sp.text, self.fps, self.language, sr=SR, emotion=sp.emotion)
                    except Exception as ex:
                        if not getattr(self, "_lip_warned", False):
                            self._lip_warned = True
                            self.warn(f"lip sync: {ex} - using the simple mouth")
                self._add_cues(sp, t)
            self.items.append(it)
            t = it.end
        if hook_item is not None:
            if not self._setup_hook(hook_item, hook_spec):
                self.items.remove(hook_item)                 # nothing suitable: drop it and shift
                shift = hook_item.duration
                for it2 in self.items:
                    it2.start -= shift
                for lst in self.cues_by_lang.values():
                    for c in lst:
                        c.start -= shift
                        c.end -= shift
                t -= shift
        end_text = st.get("end_text", "The End")
        if block == "end" and not end_text:
            end_text = "The End"
        if end_text and not only and block != "title":
            credits = []
            if st.get("model_credits", True):
                try:
                    from . import model3d
                    txt = json.dumps(self.data)
                    wm = self._world_map(st) if (st.get("map") or st.get("world_map")) else None
                    if wm is not None:
                        txt += json.dumps(getattr(wm, "data", None) or wm, default=str)
                    credits = model3d.credits_for(txt)
                except Exception:
                    credits = []
            it = Item("end", t, float(st.get("end_duration", 3.0)), spec={"text": end_text,
                                                                         "sub": st.get("end_subtitle", ""),
                                                                         "credits": credits})
            it.fade_in, it.fade_out = 0.5, 0.8
            self.items.append(it)
            t = it.end
        from .tts import LANG_NAMES
        for lang, n in self._missing.items():
            self.warn(f"{n} line(s) have no {LANG_NAMES.get(lang, lang)} text - they will be spoken in the original "
                      f"language. Add translations with:  python main.py translate <story.json> --to {lang}")
        self.duration = t
        self.n_frames = int(round(t * self.fps))
        self._starts = [it.start for it in self.items]
        self.cues.sort(key=lambda c: c.start)
        self._cue_starts = [c.start for c in self.cues]

    def _lip(self, clip):
        if not isinstance(clip, MultiClip):
            return lip_curve(clip, self.fps)
        curves = [lip_curve(c, self.fps) for c in clip.values()]      # mouth moves while ANY language speaks
        n = max(len(c) for c in curves)
        out = np.zeros(n, np.float32)
        for c in curves:
            out[:len(c)] = np.maximum(out[:len(c)], c)
        return out

    def _add_cues(self, sp, offset, until=None):
        """Subtitle cues for one speech in every language (primary -> self.cues)."""
        narr = sp.who == "narrator"
        if narr and not self.show_narration_subs:
            return
        name, color = ("", (1, 1, 1)) if narr else (self.characters[sp.who].name, self.characters[sp.who].color)
        texts = sp.clip.texts if isinstance(sp.clip, MultiClip) else {self.language: sp.text}
        for lang in self.languages:
            line = _CueLine(texts.get(lang, sp.text), sp.start, sp.dur)
            new = cues_for(line, offset, name, color, narr)
            if until is not None:
                new = [c for c in new if c.start < until]
                for c in new:
                    c.end = min(c.end, until - 0.05)
            self.cues_by_lang[lang] += new
            if lang == (self.sub_lang or self.language) and not self.sub_both:
                self.cues += new
        if self.sub_both and len(self.languages) > 1:      # one cue, both languages on two lines
            other = next((l for l in self.languages if l != self.language), None)
            both = f"{texts.get(self.language, sp.text)}\n{texts.get(other, '')}".strip()
            new = [Cue(offset + sp.start, offset + sp.start + sp.dur, name, color, both, narr)]
            if until is not None:
                new = [x for x in new if x.start < until]
                for x in new:
                    x.end = min(x.end, until - 0.05)
            self.cues += new

    # ------------------------------------------------------------------ hook (flash-forward cold open)
    def _setup_hook(self, hook, spec):
        from .pacing import _scene_moments
        scenes = [it for it in self.items if it.kind == "scene"]
        if not scenes:
            return False
        src, at = None, None
        if isinstance(spec, dict) and spec.get("scene") is not None:
            ref = spec["scene"]
            for it in scenes:
                if it.spec.get("_orig", it.scene.index) + 1 == ref or it.spec.get("id") == ref:
                    src = it
            if src is not None:
                at = float(spec.get("at", 0.0))
        if src is None:                              # auto: densest cluster of big moments after the opening
            best, total = None, scenes[-1].end - scenes[0].start
            for it in scenes:
                m = _scene_moments(it)
                for t0, kind, big in m:
                    if (t0 - scenes[0].start) < total * 0.2:
                        continue
                    window = [x for x in m if t0 - 1.5 <= x[0] <= t0 + hook.duration - 1.5]
                    score = sum(3 if b else 1 for _, _, b in window) + sum(2 for _, k, _ in window if k == "speech")
                    if best is None or score > best[0]:
                        best = (score, it, t0 - it.start - 1.2)
            if best is None:
                return False
            _, src, at = best
        at = max(0.0, min(at, src.duration - hook.duration))
        hook.scene, hook.bg, hook.spec, hook.cams = src.scene, src.bg, src.spec, src.cams
        hook.src, hook.src_at = src, at
        cap = spec.get("caption") if isinstance(spec, dict) else None
        hook.caption = cap if cap is not None else "Coming up..."
        for sp in src.scene.speeches:                # subtitles of the borrowed moment
            if at <= sp.start < at + hook.duration:
                self._add_cues(sp, hook.start - at, until=hook.end)
        self.cues.sort(key=lambda c: c.start)
        self._cue_starts = [c.start for c in self.cues]
        return True

    # ------------------------------------------------------------------ lookup
    def item_at(self, t):
        i = max(0, bisect.bisect_right(self._starts, t) - 1)
        return self.items[i]

    def cue_at(self, t):
        i = bisect.bisect_right(self._cue_starts, t) - 1
        if i >= 0 and self.cues[i].start <= t < self.cues[i].end:
            return self.cues[i]
        return None

    # ------------------------------------------------------------------ audio
    def _pan_for(self, item, who, local_t):
        if who not in item.scene.tracks or not item.cams:
            return 0.0
        f = min(int(local_t * self.fps), len(item.cams) - 1)
        cam = item.cams[max(f, 0)]
        tr = item.scene.tracks[who]
        x = tr.x_at(local_t)
        if getattr(item.scene, "mode3d", False):
            from .world3d import p3, X_of
            p = p3(tr.z_at(local_t))
            return clamp((X_of(x, p, item.scene.world_w / 2.0) - cam.x) * p * cam.z / 960.0, -1, 1) * 0.7
        return clamp((x - cam.x) * cam.z / 960.0, -1, 1) * 0.55

    def _depth_gain(self, it, who, t, voice=False):
        """Farther away = quieter (footsteps, sounds; voices only a little so dialogue stays clear)."""
        sc = it.scene
        tr = sc.tracks.get(who) if who else None
        if tr is not None:
            z = tr.z_at(t)
        elif who in sc.props:
            z = sc.props[who].z_at(t)
        else:
            return 1.0
        if getattr(sc, "mode3d", False):
            from .world3d import p3
            p = p3(z)
        elif sc.depth:
            from .depth import p_of_z
            p = p_of_z(z)
        else:
            return 1.0
        return 0.65 + 0.35 * min(1.0, p) if voice else clamp(p ** 1.3, 0.05, 1.0)

    def _scene_audio(self, mix, it, T, window=None, lang=None):
        """All sounds of one scene, placed at video time T + t. With window=(a, b) only that part is used."""
        st = self.settings
        sc = it.scene
        a, b = window if window else (-1e9, 1e9)

        def put(bus, sig, tt, gain, pan=0.0):
            if sig is None or not (a <= tt < b):
                return
            if window:
                sig = sig[..., : max(0, int((b - tt) * SR))]
            mix.add(bus, sig, T + tt, gain, pan)

        for sp in sc.speeches:
            pan = 0.0 if sp.who == "narrator" else self._pan_for(it, sp.who, sp.start)
            put("voice", voice_clip(sp.clip, lang), sp.start,
                1.0 if sp.who == "narrator" else self._depth_gain(it, sp.who, sp.start, True), pan)
        for (tt, who, kind) in sc.footsteps:
            sfx = self.sfx.get({"walk": "footstep", "run": "run_step"}.get(kind, kind))
            tr = sc.tracks.get(who)
            put("sfx", sfx, tt, 0.45 * min(1.3, (tr.cdef.scale if tr else 1)) * self._depth_gain(it, who, tt),
                self._pan_for(it, who, tt))
        for ev in sc.sfx:
            tt, name, vol, who = ev[:4]
            clip = self.sfx.get(name)
            if len(ev) > 4 and clip is not None:                       # a story's {"sound": ...}: only as long as needed
                clip = _shape_sound(clip, ev[4], it.duration - tt, int(tt * 1000) + len(name))
            put("sfx", clip, tt, vol * (self._depth_gain(it, who, tt) if who else 1.0),
                self._pan_for(it, who, tt) if who else 0.0)
        if st.get("snore", True):
            for tr in sc.tracks.values():
                for k, seg in enumerate(tr.segments):
                    if seg.action == "sleep":
                        stop = tr.segments[k + 1].start if k + 1 < len(tr.segments) else sc.duration
                        tt = seg.start + 1.2
                        while tt + 2.6 < stop:
                            put("sfx", self.sfx.get("snore"), tt, 0.5, self._pan_for(it, tr.cdef.id, tt))
                            tt += 3.0
        for (a0, a1, name, vol, src) in sc.loops:
            clip = self.sfx.get(name)
            if clip is None:
                continue
            s0, s1 = max(a0, a), min(a1, b)
            if s1 <= s0:
                continue
            n = int((s1 - s0) * SR)
            if len(clip) < n:
                clip = np.tile(clip, int(np.ceil(n / len(clip))))
            clip = clip[:n].copy()
            f = min(int(0.3 * SR), n // 3)
            if f > 0:
                clip[:f] *= np.linspace(0, 1, f)
                clip[-f:] *= np.linspace(1, 0, f)
            if src in sc.props and (getattr(sc, "mode3d", False) or sc.depth):   # engine fades with distance
                blk = int(0.05 * SR)
                for j in range(0, n, blk):
                    clip[j:j + blk] *= self._depth_gain(it, src, s0 + j / SR)
            mix.add("sfx", clip, T + s0, vol)
        s3 = str(st.get("art", "")).lower() == "stick3d"
        if s3:                                             # Stick 3D: the cars of the scene drive with sound
            self._stick3d_car_audio(put, it.spec.get("stick_cars") or [], it.duration)
            self._stick3d_storm_audio(put, it.spec, it.duration, int(it.start * 10))
            hl = it.spec.get("stick_hail")
            if isinstance(hl, dict):                       # hail drumming on everything while it falls
                h0, h1 = float(hl.get("start", 0)), min(it.duration, float(hl.get("end", it.duration)))
                clip = self.sfx.get("hail")
                tt = h0
                while clip is not None and tt < h1 - 0.3:
                    put("sfx", clip[: int(min(4.0, h1 - tt) * SR)], tt, 0.55)
                    tt += 3.8
        changing = bool(getattr(sc, "weather_fx", None)) and not getattr(it.bg, "no_air", False)
        amb = it.spec.get("ambient", (_stick3d_ambient(it.spec, st) if s3 else None)
                          or default_ambient(it.bg, place_only=changing))
        ambs = amb if isinstance(amb, list) else [amb]
        s0 = max(0.0, a)
        dur = min(it.duration, b) - s0
        if changing and dur > 0:                           # the weather's own sound follows it: wind, drops, rain
            from .sfx import weather_bed
            bed = weather_bed(sc, it.bg, s0, dur + 0.8, seed=int(it.start * 10) % 1000)
            if bed is not None:
                mix.add("ambient", bed, T + s0, float(it.spec.get("ambient_volume", 1.0)))
        for am in ambs:
            if am and am != "none" and dur > 0:
                mix.add("ambient", gen_ambient(am, dur + 0.8, seed=int(stable_hash(am) % 1000 + it.start * 10)),
                        T + s0, float(it.spec.get("ambient_volume", 1.0)))

    def _stick3d_storm_audio(self, put, spec, dur, seed):
        """a disaster's sounds: helicopters' rotors overhead, things hitting things in the wind (planks, tin, glass),
        cars torn off the road, people screaming in the street, the news camera crashing down and the feed dying"""
        rng = np.random.default_rng(seed + 5)
        for c in spec.get("stick_cars") or ():
            if not isinstance(c, dict):
                continue
            if str(c.get("kind", "")) in ("jet", "plane", "aircraft"):     # a jet: idling, then full power to climb
                cl = c.get("climb") if isinstance(c.get("climb"), dict) else None
                a = max(0.0, float(cl.get("at", 0)) - 2.5) if cl else 0.0
                put("sfx", self.sfx.get("jet"), a, 0.55 if cl else 0.25)
                continue
            if str(c.get("kind", "")) in ("helicopter", "heli", "chopper", "apache", "gunship", "army_helicopter"):
                clip = self.sfx.get("rotor")
                if clip is not None:                       # (louder the lower it flies)
                    vol = max(0.12, min(0.6, 8.0 / max(4.0, float(c.get("alt", 25)))))
                    tt = 0.0
                    while tt < dur:
                        put("sfx", clip[: int(min(len(clip) / SR, dur - tt) * SR)], tt, vol)
                        tt += len(clip) / SR - 0.05
            fl = c.get("fly")
            if isinstance(fl, dict) and fl.get("mode", "shake") == "shake":   # rocked by gusts: springs creak,
                tt = float(fl.get("at", 0)) + 0.3                               # the body thumps back down
                while tt < dur:
                    put("sfx", self.sfx.get("creak"), tt, 0.3)
                    put("sfx", self.sfx.get("thud"), tt + 0.35, 0.35)
                    tt += 1.6
            elif isinstance(fl, dict):                     # a car lifted: the scrape, the bang, the tumble
                a = float(fl.get("at", 0))
                put("sfx", self.sfx.get("scrape"), a, 0.5)
                put("sfx", self.sfx.get("crash"), a + 0.3, 0.55)
                put("sfx", self.sfx.get("clang"), a + 1.1, 0.4)
        amt = float(spec.get("stick_debris") or 0)
        for _ in range(int(dur * amt * 1.6)):              # debris hitting walls, roofs, the road
            put("sfx", self.sfx.get(str(rng.choice(["clang", "thud", "crash", "whoosh", "creak"]))),
                float(rng.uniform(0, max(0.1, dur - 0.5))), float(rng.uniform(0.15, 0.35) * min(1.0, amt + 0.3)))
        if spec.get("stick_panic"):
            clip = self.sfx.get("panic")
            tt = 0.0
            while clip is not None and tt < dur:
                put("sfx", clip[: int(min(len(clip) / SR, dur - tt) * SR)], tt, float(spec.get("stick_panic")) * 0.4)
                tt += len(clip) / SR
        for key, name in (("stick_murmur", "murmur"), ("stick_whispers", "whispers")):
            sp = spec.get(key)                             # a hall talking low / whispering: {"at", "end", "volume"}
            if not sp:
                continue
            sp = sp if isinstance(sp, dict) else {"volume": float(sp)}
            clip = self.sfx.get(name)
            tt, t1 = float(sp.get("at", 0)), min(dur, float(sp.get("end", dur)))
            while clip is not None and tt < t1 - 0.1:
                put("sfx", clip[: int(min(len(clip) / SR, t1 - tt) * SR)], tt, float(sp.get("volume", 0.5)) * 0.6)
                tt += len(clip) / SR
        live = spec.get("stick_live")
        if isinstance(live, dict) and live.get("fall_at") is not None:
            f = float(live["fall_at"])
            put("sfx", self.sfx.get("crash"), f + 0.55, 0.8)
            put("sfx", self.sfx.get("static"), f + 0.7, 0.45)

    def _stick3d_car_audio(self, put, cars, dur):
        """each car of "stick_cars": its engine while it drives (rising as it sets off, dying away as it parks), the
        doors as people get in before it leaves and out after it stops, a police car's siren while it drives"""
        eng = self.sfx.get("engine")
        for c in cars:
            if not isinstance(c, dict) or not c.get("from") or not c.get("to") or c.get("fly"):
                continue                                   # (a car pushed by the wind has no engine running)
            t0, t1 = float(c.get("start", 0)), float(c.get("end", 0))
            if t1 <= t0 or eng is None:
                continue
            a0, a1 = max(0.0, t0 - 0.6), min(dur, t1 + 0.8)
            n = int((a1 - a0) * SR)
            if n <= 0:
                continue
            clip = np.tile(eng, int(np.ceil(n / len(eng))))[:n].copy()
            tt = a0 + np.arange(n) / SR
            u = np.clip((tt - t0) / max(0.1, t1 - t0), 0, 1)
            loud = np.clip(np.minimum((tt - a0) / 0.6, (a1 - tt) / 0.8), 0, 1) * (0.55 + 0.45 * np.sin(np.pi * u))
            put("sfx", clip * loud.astype(np.float32), a0, 0.6)
            if c.get("kind") == "police":
                put("sfx", self.sfx.get("siren"), max(0.0, t0 - 0.2), 0.35)
            if t0 > 1.2:
                put("sfx", self.sfx.get("car_door"), t0 - 1.0, 0.55)
                put("sfx", self.sfx.get("car_door"), t0 - 0.75, 0.45)
            if t1 + 1.0 < dur and t0 < 0.5 * dur:
                put("sfx", self.sfx.get("car_door"), t1 + 0.7, 0.55)
                put("sfx", self.sfx.get("car_door"), t1 + 1.0, 0.45)

    def build_audio(self, path, opts=None, lang=None):
        opts = opts or {}
        st = self.settings
        mix = Mixer(self.duration + 1.0)
        music_spec = opts.get("music", st.get("music", "happy"))
        mood_runs = []
        for it in self.items:
            if it.kind == "scene":
                self._scene_audio(mix, it, it.start, lang=lang)
                mood = it.spec.get("music") or BEAT_MUSIC.get(str(it.spec.get("mood", "")).lower()) or music_spec
            elif it.kind == "hook" and getattr(it, "src", None) is not None:
                self._scene_audio(mix, it.src, it.start - it.src_at, (it.src_at, it.src_at + it.duration), lang=lang)
                mood = it.src.spec.get("music", music_spec)
            else:
                mood = music_spec
            if mood_runs and mood_runs[-1][0] == mood:
                mood_runs[-1][2] = it.end
            else:
                mood_runs.append([mood, it.start, it.end])
        # music (ducked under voices inside mixdown)
        for k, (mood, a, b) in enumerate(mood_runs):
            if not mood or str(mood).lower() in ("none", "off", "false"):
                continue
            dur = b - a + (1.5 if k + 1 < len(mood_runs) else 0.5)
            fpath = mood if os.path.isabs(str(mood)) else os.path.join(self.base_dir, str(mood))
            if os.path.isfile(fpath):
                m = decode_stereo(fpath)
                reps = int(np.ceil(dur * SR / m.shape[1]))
                m = np.tile(m, (1, reps))[:, : int(dur * SR)]
                f = min(int(1.5 * SR), m.shape[1] // 3)
                m[:, :f] *= np.linspace(0, 1, f)
                m[:, -f:] *= np.linspace(1, 0, f)
            else:
                if resolve_mood(mood) is None:
                    self.warn(f"unknown music mood '{mood}', using 'happy'")
                style = str(st.get("music_style", "auto")).lower()
                if style == "auto":                              # Indian music for Indian festival / raga moods only
                    style = "indian" if str(mood).lower().startswith("raga") else "western"
                m = gen_music(mood, dur, seed=k + 3, style=style)
            mix.add("music", m, a, 1.0)
        # title / end stingers
        if self.items and self.items[-1].kind == "end" and st.get("end_sound", True):
            mix.add("sfx", self.sfx.get("tada"), self.items[-1].start + 0.3, 0.5)
        vol = st.get("volumes", {})
        out = mix.mixdown(music_gain=float(vol.get("music", st.get("music_volume", 0.22))),
                          ambient_gain=float(vol.get("ambient", 0.35)), sfx_gain=float(vol.get("sfx", 0.75)),
                          voice_gain=float(vol.get("voice", 1.0)), total=self.duration)
        write_wav(path, out)
        return path

    def write_srt(self, path, lang=None):
        if lang and (lang != self.language or self.sub_lang):
            cues = sorted(self.cues_by_lang.get(lang, []), key=lambda c: c.start)
        else:
            cues = self.cues
        write_srt(cues, path)

    def strip_for_workers(self):
        """Drop heavy/unpicklable things before handing the project to render workers."""
        self.tts = None
        self.sfx = None
        for it in self.items:
            if it.scene:
                it.scene._speak = None
                it.scene.warn = None
                for sp in it.scene.speeches:
                    sp.clip = None
