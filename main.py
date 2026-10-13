#!/usr/bin/env python3
"""Stickman Studio - Story JSON -> animated 1080p MP4.

  python main.py stories/lost_kite.json                 # full 1080p render
  python main.py stories/lost_kite.json --preview       # fast 640x360 draft
  python main.py stories/lost_kite.json --scene 2       # render only scene 2
  python main.py stories/lost_kite.json --still 12.5    # save one frame as PNG
  python main.py validate stories/lost_kite.json        # check an AI-written JSON
  python main.py poses                                  # PNG sheet of every pose

  Gemini (idea -> story -> video, fully automatic):
  python main.py config --gemini-key KEY --model gemini-2.5-flash
  python main.py models                                 # model versions your key can use
  python main.py idea "a lazy lion learns hard work"    # writes story JSON + renders MP4
  python main.py batch ideas.txt --preview              # one video per line
"""
import argparse
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def cmd_render(a):
    from engine.project import Project
    from engine.render import encode, render_frame
    from engine import codedraw
    codedraw.ensure_built()                              # pictures of new / changed code drawings (fast when none)

    opts = {"tts": a.tts, "scene": a.scene, "cache": os.path.join(HERE, "cache"), "style": getattr(a, "style_", None),
            "languages": getattr(a, "languages", None), "only_block": getattr(a, "only", None)}
    if getattr(a, "hook", None):
        opts["hook"] = a.hook
    if a.preview:
        opts.update(resolution="640x360", fps=24, preview=True)
    if getattr(a, "world_detail", None):
        opts["world_detail"] = a.world_detail
    if a.resolution:
        opts["resolution"] = a.resolution
    if a.fps:
        opts["fps"] = a.fps
    if a.no_subs:
        opts["subtitles"] = False                        # no text on the video (the .srt file is still written)
    elif getattr(a, "subs", False):
        opts["subtitles"] = True                         # text on the video, even if the story says off
    if getattr(a, "three_d", False):
        opts["camera_mode"] = "3d"
    from engine.timing import StepTimer, fmt
    os.chdir(HERE)
    t0 = time.time()
    T = StepTimer()
    T.start("voices")
    print(f"[1/4] Reading story + generating voices: {a.story}")
    P = Project(a.story, opts)
    print(f"      video length {fmt(P.duration)} ({len(P.items)} blocks, {P.n_frames} frames at {P.W}x{P.H}@{P.fps})"
          f"  voices: {', '.join(sorted(P.tts.used)) or 'none'}")

    from engine import pacing, episodes
    if getattr(a, "fix_pacing", False):
        n = pacing.fix(P)
        if n:
            print(f"      pacing: added {n} camera change(s) to break up slow stretches")
    if not getattr(a, "only", None):                     # a title / end card alone: nothing to pace or compare
        issues = pacing.analyze(P)
        if issues:
            print("      " + pacing.report(issues).replace("\n", "\n      "))
        score, closest, var = episodes.check(P.data, exclude_title=P.data.get("title"))
        for v in var:
            print("      ! " + v)
    out = a.output or os.path.join(HERE, "output",
                                   os.path.splitext(os.path.basename(a.story))[0] + (".preview" if a.preview else "") + ".mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    if a.still is not None:
        import cairo  # noqa
        P.strip_for_workers()
        fi = int(float(a.still) * P.fps)
        data = render_frame(min(fi, P.n_frames - 1), P)
        from engine.render import _SURF
        png = os.path.splitext(out)[0] + f".t{a.still}.png"
        _SURF.write_to_png(png)
        print(f"saved {png}")
        return

    tmp = tempfile.mkdtemp(prefix="stickman_")
    wav = os.path.join(tmp, "mix.wav")
    T.start("audio")
    print("[2/4] Mixing voices, sound effects, ambience and music")
    P.build_audio(wav, {"music": a.music} if a.music else None)
    srt = os.path.splitext(out)[0] + ".srt"
    extras = []
    for lang in P.languages[1:]:
        code = lang.split("-")[0].lower()
        lw = os.path.join(tmp, f"mix.{code}.wav")
        print(f"      extra audio track: {lang}")
        P.build_audio(lw, {"music": a.music} if a.music else None, lang=lang)
        ls = os.path.splitext(out)[0] + f".{code}.srt"
        P.write_srt(ls, lang)
        extras.append((lang, lw, ls))
    print("[3/4] Writing subtitles ->", srt)
    P.write_srt(srt)
    window = None
    if getattr(a, "t_from", None) is not None or getattr(a, "t_to", None) is not None:
        from engine.render import cut_audio, cut_srt
        w0 = max(0.0, float(a.t_from or 0.0))
        w1 = min(P.duration, float(a.t_to)) if a.t_to is not None else P.duration
        if w1 - w0 < 0.2:
            raise SystemExit(f"nothing to render between {w0:.1f} s and {w1:.1f} s (the video is {P.duration:.1f} s)")
        window = (w0, w1)
        print(f"      only {w0:.1f} s - {w1:.1f} s of {P.duration:.1f} s")
        wav = cut_audio(wav, w0, w1)
        cut_srt(srt, w0, w1)
        extras = [(lg, cut_audio(lw_, w0, w1), ls_) for lg, lw_, ls_ in extras]
        for _lg, _lw, ls_ in extras:
            cut_srt(ls_, w0, w1)
    T.start("render")
    print("[4/4] Rendering frames + encoding with FFmpeg")
    P.strip_for_workers()
    part_sec = getattr(a, "part", None)
    if part_sec is None and not getattr(a, "pieces", None):   # the story's "save_every", else studio_settings.json
        from engine.production import save_every, piece_args
        pa = piece_args(save_every(None, P.data), "60")
        if pa[:1] == ["--pieces"]:
            a.pieces = int(pa[1])
        elif pa[:1] == ["--part"]:
            part_sec = float(pa[1])
    part_sec = 60 if part_sec is None else part_sec
    if getattr(a, "pieces", None):                       # "split into N pieces": each piece = length / N
        part_sec = max(5.0, P.duration / max(1, int(a.pieces)) + 0.01)
        print(f"      saving in {int(a.pieces)} piece(s) of about {part_sec:.0f} s")
    encode(P, wav, srt, out, workers=a.workers, crf=a.crf, preset="veryfast" if a.preview else a.preset,
           part_sec=part_sec, window=window, low_ram=bool(getattr(a, "low_ram", False)))
    if extras:
        from engine.render import mux_languages
        print("      adding language tracks")
        mux_languages(out, (P.language, srt), extras, extra_files=not getattr(a, "no_lang_files", False))
    if not a.preview and not getattr(a, "no_remember", False):
        episodes.remember(P.data, a.story)
    print(f"\nDone in {fmt(time.time() - t0)}  ->  {out}")
    print("  " + T.summary())
    if P.warnings:
        print(f"{len(P.warnings)} warning(s) - see above.")


def story_problems(path):
    """Validate a story file quietly; return a list of problem strings (used by the Gemini repair loop)."""
    from engine.project import Project
    from engine import pacing, episodes
    msgs = []
    try:
        P = Project(path, {"tts": "silent", "cache": os.path.join(HERE, "cache", "validate")}, log=lambda *x: None)
        msgs = list(P.warnings)
        msgs += [i["message"] for i in pacing.analyze(P) if i["level"] == "warn"][:4]
        _, _, var = episodes.check(P.data, exclude_title=P.data.get("title"))
        msgs += [v for v in var if not v.startswith("variety (info)")]
        try:                                           # ⚛ physics lessons: a wrong number in a line is a problem
            from engine import physcheck
            msgs += physcheck.problems(physcheck.check(P))[:8]
        except Exception:                              # noqa: BLE001
            pass
    except SystemExit as ex:
        msgs = [str(ex)]
    except Exception as ex:  # noqa
        msgs = [f"engine error: {type(ex).__name__}: {ex}"]
    return [m for m in msgs if "voice engine" not in m]


_PRINT_LOCK = __import__("threading").Lock()


def _locked_print(*args):
    with _PRINT_LOCK:
        print(*args, flush=True)


def _ai_overrides(a):
    return {"model": getattr(a, "model", None), "api_version": getattr(a, "api_version", None)}


def cmd_config(a):
    from engine import ai
    if a.gemini_key is not None or a.model or a.api_version or a.temperature is not None:
        ai.save_config(gemini_api_key=a.gemini_key, gemini_model=ai.clean_model(a.model) if a.model else None,
                       gemini_api_version=a.api_version,
                       gemini_temperature=a.temperature)
        print("Saved to", ai.CONFIG_PATH)
    st = ai.settings()
    src = "environment variable" if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") else "config.json"
    print(f"  Gemini key : {ai.mask(st['key']) or 'NOT SET'}" + (f"  ({src})" if st["key"] else ""))
    print(f"  Model      : {st['model']}")
    print(f"  API version: {st['api_version']}")
    print(f"  Temperature: {st['temperature']}")


def cmd_models(a):
    from engine import ai
    st = ai.settings(_ai_overrides(a))
    try:
        models = ai.Gemini(st["key"], st["model"], st["api_version"]).list_models()
    except ai.GeminiError as ex:
        raise SystemExit(f"Error: {ex}")
    print(f"{len(models)} models support text generation (current: {st['model']}):\n")
    for m in models:
        cur = "  <- current" if m["name"] == st["model"] else ""
        print(f"  {m['name']:<40} {m['display']}{cur}")
    print("\nSet one with:  python main.py config --model <name>")


def _ai_story(idea, a, full_story=False, quiet=False):
    from engine import ai, timing

    def tick(label, el, expected):
        if label is None:
            sys.stdout.write("\r" + " " * 100 + "\r")
            sys.stdout.flush()
        else:
            timing.console_tick(label, expected)(el)
    try:
        data, path = ai.create_story(idea, story_problems, os.path.join(HERE, "stories", "ai"),
                                     tick=None if quiet else tick,
                                     log=(lambda msg: _locked_print(f"  [{idea[:24]}] {str(msg).strip()}")) if quiet else print,
                                     overrides=_ai_overrides(a), scenes=a.scenes, minutes=a.minutes,
                                     language=a.language, style=a.style, audience=a.audience,
                                     full_story=full_story, world=getattr(a, "world", None))
    except ai.GeminiUnavailable as ex:
        raise SystemExit(f"Gemini problem: {ex}\n\n" + ai.FALLBACK_HINT.format(path=ai.MANUAL_PROMPT))
    except ai.GeminiError as ex:
        raise SystemExit(f"Error: {ex}")
    from engine import episodes
    episodes.remember(data, path)
    langs = getattr(a, "languages", None)
    if langs:
        import json as _json
        from engine.tts import norm_lang, LANG_NAMES
        for lang in [norm_lang(x) for x in str(langs).replace(";", ",").split(",") if x.strip()]:
            try:
                done, total = ai.translate_story(data, lang, _ai_overrides(a))
                _locked_print(f"  {LANG_NAMES.get(lang, lang)}: translated {done}/{total} lines")
            except ai.GeminiError as ex:
                _locked_print(f"  ! could not translate to {lang}: {ex}")
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
        a.languages = None                 # already stored in the story settings
    _locked_print(f"  saved story JSON -> {path}")
    return path


def _render_after(path, a):
    if a.no_render:
        print(f"Render later with:  python main.py \"{path}\"")
        return
    a.story, a.output, a.still = path, None, None
    cmd_render(a)


def cmd_idea(a):
    text = a.idea
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    if not text:
        raise SystemExit("Give an idea in quotes, or --file story.txt")
    print("[AI] Writing story with Gemini")
    path = _ai_story(text, a, full_story=bool(a.file) or len(text) > 400)
    _render_after(path, a)


def cmd_batch(a):
    from concurrent.futures import ThreadPoolExecutor
    from engine import ai, timing
    with open(a.ideas_file, encoding="utf-8") as f:
        ideas = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    par = max(1, min(a.parallel, len(ideas) or 1))
    exp = timing.gemini_estimate(ai.settings(_ai_overrides(a))["model"])
    waves = -(-len(ideas) // par)
    print(f"{len(ideas)} idea(s). Step 1: Gemini writes {par} stories at a time "
          f"- estimated ~{timing.fmt(waves * exp * 1.15)}. Step 2: render each video (estimate shown per video).")
    t0 = time.time()

    def one(idea):
        try:
            return idea, _ai_story(idea, a, quiet=par > 1)
        except SystemExit as ex:
            print(f"  FAILED [{idea[:40]}]: {ex}")
            return idea, None
    with ThreadPoolExecutor(par) as ex:
        results = list(ex.map(one, ideas))
    ok = [(i, p) for i, p in results if p]
    print(f"\nStories done in {timing.fmt(time.time() - t0)}: {len(ok)}/{len(ideas)} ok.")
    for k, (idea, path) in enumerate(ok, 1):
        print(f"\n===== render [{k}/{len(ok)}] {idea[:70]}")
        try:
            _render_after(path, a)
        except SystemExit as ex:
            print(f"  FAILED: {ex}")
    print(f"\nBatch finished in {timing.fmt(time.time() - t0)}.")


def cmd_check(a):
    """Validation + pacing + variety report without rendering."""
    from engine.project import Project
    from engine import pacing, episodes
    os.chdir(HERE)
    P = Project(a.story, {"tts": "silent", "cache": os.path.join(HERE, "cache", "validate")})
    print(f"\n{len(P.characters)} characters, {sum(1 for i in P.items if i.kind == 'scene')} scenes, "
          f"~{P.duration:.0f}s (estimated)")
    print(pacing.report(pacing.analyze(P)))
    score, closest, var = episodes.check(P.data, exclude_title=P.data.get("title"))
    print(f"Variety: {score}% similar to your closest past episode" + (f" ('{closest}')" if closest else ""))
    for v in var:
        print("  ! " + v)
    _object_mentions(a.story)


def cmd_prompt(a):
    from engine.prompt_builder import write_prompt_file, build_prompt_text
    from engine.episodes import recent_summaries
    from engine import prompt_refresh
    prompt_refresh.refresh(force=True)                    # every prompt file, with the whole library, checked
    path = write_prompt_file(recent_summaries())
    if a.idea:
        from engine import ai
        text = ai.build_prompt(a.idea, world=a.world)
        with open(ai.MANUAL_PROMPT, "w", encoding="utf-8") as f:
            f.write(text)
        print(text)
        print(f"\n(saved to {ai.MANUAL_PROMPT} - paste it into ChatGPT or any chatbot)")
    else:
        print(f"Prompt updated: {path}  (2D + 3D)")
        p3 = path.replace(".md", "_3d.md")
        from engine.prompt_builder import world_block
        t3 = build_prompt_text(recent_summaries(), None, a.world or "3d")
        wb = world_block(a.world or "3d", base_done=True)
        with open(p3, "w", encoding="utf-8") as f:
            f.write(t3 + ("\n\n" + wb if wb else ""))
        print(f"Prompt updated: {p3}  (3D page{', world ' + a.world.split(':', 1)[1] if a.world and ':' in a.world else ''})")
        from engine import prompt_stick3d
        ps = path.replace(".md", "_stick3d.md")
        with open(ps, "w", encoding="utf-8") as f:
            f.write(prompt_stick3d.build() + "\n\nTHE STORY:\n<PASTE YOUR STORY HERE>\n\nAnswer with the JSON only.\n")
        print(f"Prompt updated: {ps}  (Stick 3D page: only Stick 3D things + the director's rules)")


def cmd_translate(a):
    """Add a second (third...) language to a story: every spoken line gets a translation."""
    import json as _json
    from engine import ai
    from engine.tts import norm_lang, LANG_NAMES
    target = norm_lang(a.to)
    with open(a.story, encoding="utf-8") as f:
        data = _json.load(f)
    out = a.output or a.story
    if a.answer:                                   # answer pasted from ChatGPT etc.
        with open(a.answer, encoding="utf-8") as f:
            done, total = ai.apply_translation(data, target, f.read())
    else:
        try:
            done, total = ai.translate_story(data, target, _ai_overrides(a))
        except ai.GeminiError as ex:
            prompt, _ = ai.translate_prompt(data, target)
            p = os.path.join(HERE, "prompts", f"translate_{target}.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write(prompt)
            raise SystemExit(f"Gemini not available ({ex}).\nManual way: paste the prompt in {p} into ChatGPT, "
                             f"save its JSON answer as answer.json, then run:\n"
                             f"  python main.py translate \"{a.story}\" --to {target} --answer answer.json")
    with open(out, "w", encoding="utf-8") as f:
        _json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"{LANG_NAMES.get(target, target)}: translated {done}/{total} lines -> {out}")
    print(f"Render with both languages:  python main.py \"{out}\"")


def _object_mentions(story_path, fix=False):
    """Things the lines talk about that are not in the scene (a tea cup nobody holds): shown in RED."""
    from engine import mentions
    try:
        with open(story_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return 0
    probs = mentions.check(data)
    if not probs:
        return 0
    red, end = ("\033[91m", "\033[0m") if sys.stdout.isatty() or os.environ.get("FORCE_COLOR") else ("", "")
    print(f"\n{red}{len(probs)} talked-about thing(s) missing from the scene:{end}")
    for p in probs:
        print(f"{red}  x {mentions.message(p)}{end}")
    if fix:
        with open(story_path, "w", encoding="utf-8") as f:
            json.dump(mentions.fix(data, probs), f, indent=2, ensure_ascii=False)
        print(f"  -> fixed: the props were written into {story_path}")
    else:
        print("  (python main.py validate <story> --fix-objects  writes these fixes into the JSON for you)")
    return len(probs)


def cmd_planet(a):
    """Print a planet as data: from a galaxy seed + star + planet number, a Solar System name, or words."""
    from engine import galaxy
    if a.list:
        for i in range(a.list):
            s = galaxy.star(a.galaxy, i)
            print(f"star {i}: {s['name']} - {s['kind']}, {s['mass']:.2f} Suns, {s['planets']} planet(s)")
            for k in range(1, s["planets"] + 1):
                print("    " + galaxy.describe(galaxy.planet(a.galaxy, i, k)))
        return
    if a.find:
        p = galaxy.find(a.galaxy, a.find) if a.find.lower() not in galaxy.SOLAR else galaxy.solar(a.find)
    else:
        p = galaxy.planet(a.galaxy, a.star, a.planet)
    if p is None:
        print("no planet fits that")
        return
    print(galaxy.describe(p))
    for w in galaxy.why(p):
        print("  - " + w)
    from engine import alien_life
    life_ = alien_life.describe(p)
    if life_:
        print("life: " + life_)
    print(json.dumps(galaxy.to_data(p), indent=2, ensure_ascii=False))


def cmd_validate(a):
    from engine.project import Project
    from engine import codedraw
    os.chdir(HERE)
    codedraw.ensure_built()
    P = Project(a.story, {"tts": "silent", "cache": os.path.join(HERE, "cache", "validate")})
    print(f"OK: {len(P.characters)} characters, {sum(1 for i in P.items if i.kind == 'scene')} scenes, "
          f"~{P.duration:.0f}s (timing estimated without real voices)")
    try:
        from engine import continuity
        for n in continuity.check(P):
            print(f"  ~ continuity: {n}")
    except Exception as ex:                            # advice only - never blocks
        print(f"  (continuity check skipped: {ex})")
    n_obj = _object_mentions(a.story, getattr(a, "fix_objects", False))
    n_phys = 0
    try:                                               # ⚛ is every number in the lines right? (physics lessons)
        from engine import physcheck
        items = physcheck.check(P)
        if items:
            print(physcheck.report(items))
            n_phys = sum(1 for i in items if i["level"] != "ok")
    except Exception as ex:                            # advice only - never blocks
        print(f"  (physics check skipped: {ex})")
    print("No problems found." if not (P.warnings or n_obj or n_phys) else
          f"{len(P.warnings) + n_obj + n_phys} problem(s) listed above.")


def cmd_shots(a):
    """Shot check: can every speaker be seen when they talk? (renders small frames, no video)"""
    from engine.project import Project
    from engine import shotcheck
    os.chdir(HERE)
    P = Project(a.story, {"tts": "silent", "cache": os.path.join(HERE, "cache", "validate"), "resolution": "480x270",
                          "fps": 12})
    issues = shotcheck.check(P, log=print)
    print(shotcheck.report(issues))


def cmd_storyboard(a):
    """One picture per camera shot with its line - check the story in seconds (no video)."""
    from engine import storyboard
    os.chdir(HERE)
    storyboard.storyboard(a.story, a.output)


def cmd_colorscript(a):
    """The colour script: one frame per scene with its beat's colour - the film's emotional rhythm on one page."""
    from engine import storyboard
    os.chdir(HERE)
    storyboard.colorscript(a.story, a.output)


def cmd_voicescript(a):
    """The lines one character says, ready to paste into a voice service (ElevenLabs...)."""
    from engine import voicecut
    with open(a.story, "r", encoding="utf-8") as f:
        print(voicecut.script(json.load(f), a.who))


def cmd_voices(a):
    """Match one recording of a character's lines to the story: each line gets its part (voice_file, from, to)."""
    from engine import voicecut
    voicecut.apply(a.story, a.recording, a.who, dry=a.dry)


def cmd_thumbnail(a):
    """A YouTube thumbnail: the best frame (or four) with the title written on it."""
    from engine import storyboard
    os.chdir(HERE)
    storyboard.thumbnail(a.story, a.output, mosaic=a.mosaic)


def cmd_place(a):
    """A place from a list (place JSON): check it, save a preview picture, and save it for stories."""
    import json as _json
    from engine import placegen, preview, registry
    os.chdir(HERE)
    try:
        with open(a.file, encoding="utf-8") as fh:
            text = fh.read()
        i, j = text.find("{"), text.rfind("}")          # an AI answer pasted as it is: text / fences around are fine
        spec = _json.loads(text[i:j + 1] if i >= 0 and j > i else text)
    except (OSError, ValueError) as ex:
        sys.exit(f"can't read {a.file}: {ex}")
    probs = placegen.validate(spec)
    if probs:
        sys.exit("Problems:\n  " + "\n  ".join(probs))
    chk = placegen.check(spec)
    comp = placegen.compile_place(spec, 2400)
    print("Found:  " + ", ".join(f"{f['what']} -> {f['type']}" for f in chk["found"]))
    print("Placed: " + ", ".join(f"{v}x {k}" for k, v in comp["summary"].items())
          + f"  ({len(comp['objects'])} real objects)")
    for n in comp["notes"]:
        print("  ~ " + n)
    if chk["missing"]:
        print("Missing (make them in Studio > Places > 'Gemini draws them', or upload a picture with that name):")
        for m in chk["missing"]:
            print(f"  - {m['what']}" + (f"  (did you mean {', '.join(m['suggest'])}?)" if m["suggest"] else ""))
    out = os.path.splitext(a.file)[0] + f"_{a.mode}.png"
    with open(out, "wb") as fh:
        fh.write(preview.place_json_preview(spec, a.mode, still=True))
    print(f"Preview: {out}")
    if a.save:
        name = registry.save("places", str(spec.get("place")), spec)
        print(f'Saved - use it in stories as  "background": {{"preset": "{name}"}}')


def cmd_place_prompt(a):
    """The place prompt for any AI (ChatGPT, Claude, Gemini web): always lists everything the app has now."""
    from engine import placegen
    os.chdir(HERE)
    path = placegen.write_prompt_file()
    if a.idea:
        path = os.path.join(HERE, "prompts", "place_prompt_" + "".join(c if c.isalnum() else "_" for c in a.idea)[:30] + ".md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(placegen.full_prompt(a.idea))
    print(f"Prompt written: {path}\nCopy it into any AI, save its answer as places/<name>.json, then run:\n"
          f"  python main.py place places/<name>.json --save")


def cmd_world(a):
    """python main.py world new NAME [--from FILE | --empty | --copy WORLD] | list | check NAME | prompt [IDEA]"""
    from engine import worldmap
    os.chdir(HERE)
    if a.action == "list":
        for n in worldmap.list_worlds():
            w = worldmap.load(n)
            print(f"  {n}: {w.title} - {len(w.places)} places, {len(w.areas)} areas, {len(w.roads)} roads")
        return
    if a.action == "prompt":
        idea = " ".join(a.args) or "<DESCRIBE YOUR WORLD HERE>"
        print(worldmap.world_prompt(idea))
        print("\n(also saved as", worldmap.write_prompt_file(), ")", file=sys.stderr)
        return
    if a.action in ("check", "new"):
        from engine import codedraw
        os.chdir(HERE)
        codedraw.ensure_built()                  # new / changed 3D places (e.g. zoo_enclosure_3d) exist before checking
    if a.action == "check":
        if not a.args:
            sys.exit("which world?  python main.py world check NAME")
        w = worldmap.load(a.args[0])
        if w is None:
            sys.exit(f"no world called {a.args[0]}")
        probs, notes = w.check()
        for p in probs:
            print("  ✖", p)
        for n in notes:
            print("  ·", n)
        print("No problems found." if not probs else f"{len(probs)} problem(s).")
        return
    if a.action == "new":
        if not a.args:
            sys.exit("give it a name:  python main.py world new NAME [--from FILE | --empty | --copy WORLD]")
        name = a.args[0]
        if a.copy:
            src = worldmap.load(a.copy)
            if src is None:
                sys.exit(f"no world called {a.copy}")
            spec = json.loads(json.dumps(src.spec))
            spec["title"] = worldmap._clean(name).replace("_", " ").title()
        elif a.empty:
            spec = worldmap.empty_world(name)
        else:
            if a.from_:
                with open(a.from_, encoding="utf-8") as fh:
                    text = fh.read()
            else:
                print("Paste the world JSON (from Gemini / ChatGPT / any AI), then press Ctrl+D "
                      "(Windows: Ctrl+Z then Enter):", file=sys.stderr)
                text = sys.stdin.read()
            try:
                spec = worldmap.parse_text(text)
            except ValueError as ex:
                sys.exit(f"not a world JSON: {ex}")
        try:
            ok, probs, notes, name = worldmap.create(name, spec, force=a.force)
        except ValueError as ex:
            sys.exit(str(ex))
        for p in probs:
            print("  ✖", p)
        for n in notes:
            print("  ·", n)
        if not ok:
            sys.exit("not saved - fix the problems above (or add --force to save it anyway and fix it in the "
                     "World Explorer)")
        print(f"saved worlds/{name}.json - open it: http://127.0.0.1:5000/world?w={name}  "
              f"· in a story: \"settings\": {{\"map\": \"{name}\"}}")
        return
    sys.exit("python main.py world new NAME | list | check NAME | prompt [IDEA]")


def cmd_code(a):
    """Save a code drawing (assets/code/<name>.py or any .py / AI answer file) -> picture or wearable."""
    from engine import codedraw
    os.chdir(HERE)
    if a.file in ("all", "changed"):                      # python main.py code all  -> rebuild every drawing
        n = codedraw.ensure_built(force=a.file == "all")
        print(f"built {n} code drawing(s)")
        return
    src = a.file
    if not os.path.exists(src) and os.path.exists(codedraw.path_of(src)):
        src = codedraw.path_of(src)
    if not os.path.exists(src):
        sys.exit(f"not found: {a.file}")
    with open(src, encoding="utf-8") as fh:
        code = codedraw.extract_code(fh.read())
    name = a.name or os.path.splitext(os.path.basename(src))[0]
    r = codedraw.run_safe({"do": "save", "name": name, "code": code}, timeout=120)
    if not r.get("ok"):
        sys.exit("drawing failed: " + str(r.get("error")))
    if r["kind"] == "wear":
        print(f"saved wearable '{r['name']}' - use \"hat\": \"{r['name']}\" on a character")
    else:
        print(f"saved {r['kind']} '{r['name']}' ({r['height']} tall) as {', '.join(r['pictures'])}")
    if a.png:
        with open(a.png, "wb") as fh:
            fh.write(codedraw.preview_png(code, name=name))
        print("preview:", a.png)
    try:
        from engine.prompt_builder import write_prompt_file
        from engine import placegen
        write_prompt_file()
        placegen.write_prompt_file()
        codedraw.write_help_file()
    except Exception:
        pass


def cmd_poses(a):
    import math
    import cairo
    from engine.poses import ACTIONS
    from engine.character import CharacterDef, draw_character
    names = list(ACTIONS)
    cols = 9
    rows = math.ceil(len(names) / cols)
    W, H = 1800, rows * 330
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    c = CharacterDef("a", {"hair": "spiky"})
    for i, n in enumerate(names):
        cx, gy = (i % cols) * 200 + 100, (i // cols) * 330 + 300
        spec = ACTIONS[n]
        dur = spec.dur or 2
        pose, ex = spec.fn(dur * 0.5, dur, {"params": {}, "speed": 0})
        ctx.save()
        ctx.translate(cx, gy)
        ctx.scale(0.85, -0.85)
        draw_character(ctx, c, pose, 0, 1, ex.get("face", "neutral"), 0, 0.3, ex, seat=ex.get("seat", False))
        ctx.restore()
        ctx.set_source_rgb(0, 0, 0)
        ctx.set_font_size(18)
        ctx.move_to(cx - 40, gy + 22)
        ctx.show_text(n)
    out = a.output or os.path.join(HERE, "output", "pose_sheet.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    surf.write_to_png(out)
    print("saved", out)


def main():
    argv = sys.argv[1:]
    if argv and argv[0] not in ("render", "storyboard", "colorscript", "voicescript", "voices", "thumbnail", "validate", "planet", "shots", "world", "place", "place-prompt", "code", "poses", "idea", "batch", "config", "models", "check", "prompt", "translate",
                                "-h", "--help"):
        argv = ["render"] + argv
    ap = argparse.ArgumentParser(description="Stickman Studio: story JSON -> MP4")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render a story to MP4")
    r.add_argument("story")
    r.add_argument("-o", "--output")
    r.add_argument("--preview", action="store_true", help="fast 640x360 draft")
    r.add_argument("--scene", type=int, help="render only this scene number")
    r.add_argument("--only", choices=["title", "end"], help="render only the title card or only the end card")
    r.add_argument("--no-remember", action="store_true", help="don't add this render to the episode memory (parts)")
    r.add_argument("--no-lang-files", action="store_true", help="2 languages: only the one video with every track "
                   "(no separate <name>.<lang>.mp4 / .m4a)")
    r.add_argument("--still", help="save a single frame at this time (seconds) as PNG")
    r.add_argument("--tts", choices=["auto", "edge", "piper", "local", "pyttsx3", "espeak", "silent"])
    r.add_argument("--music", help="mood (happy, calm, sad, tense, adventure, funny, mystery, romantic), file, or none")
    r.add_argument("--resolution", help="e.g. 1920x1080, 1080x1920 (Shorts), 3840x2160")
    r.add_argument("--fps", type=int)
    r.add_argument("--workers", type=int, help="parallel render processes (default: CPU cores - 1)")
    r.add_argument("--low-ram", dest="low_ram", action="store_true",
                   help="for a 4-8 GB computer: 2 workers, 20 s parts, small caches, light FFmpeg (slower, safe)")
    r.add_argument("--pieces", type=int, help="render in this many pieces (each saved as it finishes)")
    r.add_argument("--world-detail", dest="world_detail", choices=["low", "medium", "high"],
                   help="how much of a big world map is drawn round each scene (low = fastest, least RAM)")
    r.add_argument("--from", dest="t_from", type=float, help="render only from this second on (a time part)")
    r.add_argument("--to", dest="t_to", type=float, help="render only up to this second (a time part)")
    r.add_argument("--part", type=float, help="render in parts of this many seconds, saved as they finish and "
                   "joined at the end - a crash / stop resumes (default 60, 0 = one piece)")
    r.add_argument("--crf", type=int, default=18, help="quality: lower = better/bigger (default 18)")
    r.add_argument("--preset", default="medium", help="x264 preset (veryfast..slow)")
    r.add_argument("--no-subs", action="store_true", help="don't burn subtitles into the video")
    r.add_argument("--subs", action="store_true", help="burn subtitles into the video even if the story turns them off")
    r.add_argument("--languages", help="extra audio languages, e.g. hi-IN or hi-IN,ta-IN (needs translations - see 'translate')")
    r.add_argument("--char-style", dest="style_", choices=["cartoon", "toon", "classic"], help="coloured cartoon (default), toon (big-head TV cartoon, the 2.5D look) or classic thin stickman")
    r.add_argument("--3d", dest="three_d", action="store_true",
                   help="true 2.5D: every outdoor scene becomes a real depth world with a moving 3D camera")
    r.add_argument("--fix-pacing", action="store_true", help="add camera changes to break up slow stretches")
    r.add_argument("--no-hook", dest="hook", action="store_const", const="off", help="no flash-forward opening")
    r.set_defaults(fn=cmd_render)
    sb = sub.add_parser("storyboard", help="one picture per camera shot with its line (check before rendering)")
    sb.add_argument("story")
    sb.add_argument("-o", "--output")
    sb.set_defaults(fn=cmd_storyboard)
    cs = sub.add_parser("colorscript", help="the colour script: one frame per scene with its mood colour")
    cs.add_argument("story")
    cs.add_argument("-o", "--output")
    cs.set_defaults(fn=cmd_colorscript)
    vs = sub.add_parser("voicescript", help="a character's lines, to paste into a voice service (ElevenLabs)")
    vs.add_argument("story")
    vs.add_argument("--who", required=True)
    vs.set_defaults(fn=cmd_voicescript)
    vo = sub.add_parser("voices", help="match one recording of a character's lines to the story (voice_file/from/to)")
    vo.add_argument("story")
    vo.add_argument("recording")
    vo.add_argument("--who", required=True)
    vo.add_argument("--dry", action="store_true", help="only show the cuts, change nothing")
    vo.set_defaults(fn=cmd_voices)
    tb = sub.add_parser("thumbnail", help="a YouTube thumbnail: the best frame + the title")
    tb.add_argument("story")
    tb.add_argument("-o", "--output")
    tb.add_argument("--mosaic", action="store_true", help="four strong moments in one picture")
    tb.set_defaults(fn=cmd_thumbnail)
    pg = sub.add_parser("planet", help="a planet as data (rule-based galaxy): --galaxy 42 --star 3 --planet 2, "
                                       "--find \"a warm planet with water\", --find mars, --list 10")
    pg.add_argument("--galaxy", type=int, default=1)
    pg.add_argument("--star", type=int, default=0)
    pg.add_argument("--planet", type=int, default=1)
    pg.add_argument("--find", default=None)
    pg.add_argument("--list", type=int, default=0)
    pg.set_defaults(fn=cmd_planet)
    v = sub.add_parser("validate", help="check a story JSON for mistakes")
    v.add_argument("story")
    v.add_argument("--fix-objects", action="store_true",
                   help="add the missing props (a cup, a ball ... that a line talks about) to the JSON")
    v.set_defaults(fn=cmd_validate)
    pl = sub.add_parser("place", help="build a place from a list (place JSON): check + preview + --save")
    pl.add_argument("file")
    pl.add_argument("--mode", choices=["3d", "2d"], default="3d")
    pl.add_argument("--save", action="store_true", help="save it so stories can use it by name")
    pl.set_defaults(fn=cmd_place)
    pp = sub.add_parser("place-prompt", help="write the place prompt for any AI (optionally with your idea)")
    pp.add_argument("idea", nargs="?", default="")
    pp.set_defaults(fn=cmd_place_prompt)
    cd = sub.add_parser("code", help="save a Python drawing (assets/code/<name>.py) as a picture / wearable")
    cd.add_argument("file", help="a .py file, an AI answer .txt/.md, the name of a drawing in assets/code, "
                                        "'changed' (build new / changed drawings) or 'all' (rebuild every drawing)")
    cd.add_argument("--name", default="", help="name to use in stories (default: file name)")
    cd.add_argument("--png", default="", help="also write a preview PNG here")
    cd.set_defaults(fn=cmd_code)
    wd = sub.add_parser("world", help="big 3D world maps: new NAME (paste JSON) | list | check NAME | prompt IDEA")
    wd.add_argument("action", choices=("new", "list", "check", "prompt"))
    wd.add_argument("args", nargs="*")
    wd.add_argument("--from", dest="from_", default="", help="a .json / .txt file with the world (an AI answer is fine)")
    wd.add_argument("--empty", action="store_true", help="start with an empty 5 km map")
    wd.add_argument("--copy", default="", help="start as a copy of this world")
    wd.add_argument("--force", action="store_true", help="save even with problems (fix them in the Explorer)")
    wd.set_defaults(fn=cmd_world)
    sh = sub.add_parser("shots", help="shot check: is every speaker visible when they talk?")
    sh.add_argument("story")
    sh.set_defaults(fn=cmd_shots)
    def render_flags(x):
        x.add_argument("--preview", action="store_true", help="fast 640x360 draft")
        x.add_argument("--tts", choices=["auto", "edge", "piper", "local", "pyttsx3", "espeak", "silent"])
        x.add_argument("--music", help="mood, file, or none")
        x.add_argument("--resolution")
        x.add_argument("--fps", type=int)
        x.add_argument("--workers", type=int)
        x.add_argument("--part", type=float)
        x.add_argument("--pieces", type=int)
        x.add_argument("--world-detail", dest="world_detail", choices=["low", "medium", "high"])
        x.add_argument("--from", dest="t_from", type=float)
        x.add_argument("--to", dest="t_to", type=float)
        x.add_argument("--crf", type=int, default=18)
        x.add_argument("--preset", default="medium")
        x.add_argument("--no-subs", action="store_true")
        x.add_argument("--subs", action="store_true")
        x.add_argument("--languages", help="extra audio languages, e.g. hi-IN (the story is translated automatically)")
        x.add_argument("--char-style", dest="style_", choices=["cartoon", "toon", "classic"])
        x.add_argument("--3d", dest="three_d", action="store_true", help="true 2.5D depth worlds")
        x.add_argument("--fix-pacing", action="store_true")
        x.add_argument("--no-hook", dest="hook", action="store_const", const="off")
        x.add_argument("--no-render", action="store_true", help="only write the story JSON")
        x.add_argument("--model", help="Gemini model for this run, e.g. gemini-2.5-pro")
        x.add_argument("--api-version", help="v1beta (default) or v1")
        x.add_argument("--scenes", type=int, help="number of scenes")
        x.add_argument("--minutes", type=float, help="target video length")
        x.add_argument("--language", help="en-US, en-IN, en-GB, hi-IN")
        x.add_argument("--style", help='tone, e.g. "funny", "moral story", "spooky but kid-safe"')
        x.add_argument("--audience", help='e.g. "kids 4-8"')
        x.set_defaults(scene=None)

    i = sub.add_parser("idea", help="Gemini writes a story from your idea, then renders it")
    i.add_argument("idea", nargs="?", default="")
    i.add_argument("--file", help="a .txt with your full story instead of a one-line idea")
    i.add_argument("--world", help='"3d" = a real 3D video, "3d:<world map>" = inside a world map')
    render_flags(i)
    i.set_defaults(fn=cmd_idea)
    b = sub.add_parser("batch", help="one video per line of a text file")
    b.add_argument("ideas_file")
    b.add_argument("--parallel", type=int, default=3, help="stories Gemini writes at the same time (default 3)")
    b.add_argument("--world", help='"3d" = real 3D videos, "3d:<world map>" = inside a world map')
    render_flags(b)
    b.set_defaults(fn=cmd_batch)
    c = sub.add_parser("config", help="set Gemini API key / model / API version")
    c.add_argument("--gemini-key", help='your key ("" to remove)')
    c.add_argument("--model", help="e.g. gemini-2.5-flash, gemini-2.5-pro, or any name from `models`")
    c.add_argument("--api-version", help="v1beta (default) or v1")
    c.add_argument("--temperature", type=float, help="creativity 0.0-2.0 (default 0.9)")
    c.set_defaults(fn=cmd_config)
    m = sub.add_parser("models", help="list Gemini models your key can use")
    m.add_argument("--api-version")
    m.set_defaults(fn=cmd_models)
    ck = sub.add_parser("check", help="pacing + variety report for a story (no render)")
    ck.add_argument("story")
    ck.set_defaults(fn=cmd_check)
    pr = sub.add_parser("prompt", help="rebuild the AI prompt; with an idea, print a ready-to-paste prompt")
    pr.add_argument("idea", nargs="?", default="")
    pr.add_argument("--world", help='"3d" = the 3D page prompt, "3d:<world map>" = inside a world map (default: 2D + 3D mix)')
    pr.set_defaults(fn=cmd_prompt)
    tr = sub.add_parser("translate", help="add another language to a story (Gemini, or a ChatGPT answer)")
    tr.add_argument("story")
    tr.add_argument("--to", required=True, help="hi-IN, en-IN, ta-IN, te-IN, mr-IN, bn-IN, gu-IN, kn-IN, ml-IN, es-ES, fr-FR")
    tr.add_argument("-o", "--output", help="write to a new file instead of updating the story")
    tr.add_argument("--answer", help="JSON answer from ChatGPT etc. (manual mode)")
    tr.add_argument("--model")
    tr.add_argument("--api-version")
    tr.set_defaults(fn=cmd_translate)
    p = sub.add_parser("poses", help="save a PNG sheet of every pose")
    p.add_argument("-o", "--output")
    p.set_defaults(fn=cmd_poses)
    a = ap.parse_args(argv)
    if getattr(a, "story", None):
        a.story = os.path.abspath(a.story)
    if hasattr(a, "output") and a.output:
        a.output = os.path.abspath(a.output)
    a.fn(a)


if __name__ == "__main__":
    main()
