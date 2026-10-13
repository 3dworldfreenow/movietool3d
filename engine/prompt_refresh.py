"""Keep every AI prompt up to date with the whole library.

refresh() runs when the app starts (after the pictures of new code drawings are made) and after every save:
  1. loads everything: pictures, 3D things, 3D animal files (new species), vehicles, places, characters,
     world maps, imported models
  2. writes all prompt files again when something changed or a file is missing:
       prompts/story_to_json_prompt.md     (2D + 3D page)      prompts/story_to_json_prompt_3d.md  (3D page)
       prompts/place_to_json_prompt.md     prompts/world_prompt.md
       prompts/code_drawing_prompt.md      prompts/code3d_drawing_prompt.md
  3. checks that every thing of the library is named in the story prompts - and says which are missing
"""
import json
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(ROOT, "prompts")
STAMP = os.path.join(PROMPTS, ".library_stamp.json")
FILES = ("story_to_json_prompt.md", "story_to_json_prompt_3d.md", "place_to_json_prompt.md", "world_prompt.md",
         "code_drawing_prompt.md", "code3d_drawing_prompt.md")
WATCH = ("assets/images", "assets/code", "assets/species", "assets/places", "assets/characters", "assets/kits",
         "assets/puppets", "assets/models", "worlds")
DEFAULT_BODIES = ("person_3d", "quadruped_3d", "bird_3d")
_LOCK = threading.Lock()
LAST = {"missing": {}, "counts": {}, "when": None, "rebuilt": False}


def _stamp():
    """names + change times of everything the prompts are made from (fast: no file is opened)."""
    out = {}
    for rel in WATCH:
        d = os.path.join(ROOT, rel)
        if not os.path.isdir(d):
            continue
        for dirpath, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if not x.startswith(".") and x != "__pycache__"]
            for f in files:
                if f.startswith(".") or f.endswith((".pyc",)):
                    continue
                p = os.path.join(dirpath, f)
                try:
                    out[os.path.relpath(p, ROOT)] = round(os.path.getmtime(p), 2)
                except OSError:
                    pass
    import hashlib
    return hashlib.sha1(json.dumps(sorted(out.items())).encode()).hexdigest(), len(out)


def library_names():
    """{group: [names]} of everything a story can use."""
    from . import animals, catalog, codedraw, images, registry
    reg = registry.load(force=True)
    imgs = images.list_images()
    o = catalog.options()
    tops = sorted(n for n, m in imgs.items()
                  if not (m or {}).get("part_of") and not (m or {}).get("state_of") and not (m or {}).get("set_of"))
    looks = sorted(n for n, m in codedraw.list_code().items()
                   if m["kind"] in ("character3d", "animal3d") and n not in DEFAULT_BODIES
                   and not (m["kind"] == "animal3d" and m.get("for") in animals.FROM_CODE))
    return {"pictures and 3D things": tops, "animals": sorted(animals.CUSTOM), "places": sorted(reg["places"]),
            "characters": sorted(reg["characters"]), "vehicles": sorted(o.get("picture_vehicles") or []),
            "3D looks": looks}


def check(texts=None):
    """{group: [names not found in the story prompts]} (empty = all good)."""
    from .prompt_builder import build_prompt_text
    if texts is None:
        texts = [build_prompt_text(None, None, None), build_prompt_text(None, None, "3d")]
    joined = "\n".join(texts)
    miss = {}
    for g, names in library_names().items():
        m = [n for n in names if n not in joined]
        if m:
            miss[g] = m
    return miss


def refresh(log=print, force=False):
    """-> dict(rebuilt, missing, counts). Rebuilds only when the library changed or a prompt file is missing."""
    with _LOCK:
        from . import codedraw, placegen, registry, worldmap
        from .episodes import recent_summaries
        from .prompt_builder import build_prompt_text, write_prompt_file
        stamp, nfiles = _stamp()
        old = {}
        try:
            with open(STAMP, encoding="utf-8") as fh:
                old = json.load(fh)
        except (OSError, ValueError):
            pass
        have_all = all(os.path.isfile(os.path.join(PROMPTS, f)) for f in FILES)
        if not force and have_all and old.get("stamp") == stamp:
            LAST.update(rebuilt=False)
            return dict(LAST)
        registry._CODE_SP["stamp"] = None                   # new 3D animal files -> species
        registry.load(force=True)
        os.makedirs(PROMPTS, exist_ok=True)
        recent = recent_summaries()
        write_prompt_file(recent)                           # 2D + 3D
        mix = build_prompt_text(recent, None, None)
        d3 = build_prompt_text(recent, None, "3d")
        with open(os.path.join(PROMPTS, "story_to_json_prompt_3d.md"), "w", encoding="utf-8") as fh:
            fh.write(d3)
        for fn in (placegen.write_prompt_file, worldmap.write_prompt_file, codedraw.write_help_file):
            try:
                fn()
            except Exception as ex:                         # one broken prompt never stops the others
                log(f"  prompt: {getattr(fn, '__module__', '')} failed ({ex})")
        miss = check([mix, d3])
        counts = {g: len(v) for g, v in library_names().items()}
        with open(STAMP, "w", encoding="utf-8") as fh:
            json.dump({"stamp": stamp, "files": nfiles, "counts": counts, "missing": miss}, fh, indent=1)
        import time
        LAST.update(rebuilt=True, missing=miss, counts=counts, when=time.strftime("%H:%M:%S"))
        log("AI prompts updated: " + ", ".join(f"{v} {k}" for k, v in counts.items() if v))
        for g, names in miss.items():
            log(f"  ! not in the story prompt ({g}): {', '.join(names[:12])}{' ...' if len(names) > 12 else ''}")
        return dict(LAST)


def status():
    """LAST, or what the last run saved (the app was just started and the refresh is still running)."""
    if LAST.get("when"):
        return dict(LAST)
    try:
        with open(STAMP, encoding="utf-8") as fh:
            d = json.load(fh)
        return {"counts": d.get("counts", {}), "missing": d.get("missing", {}), "when": "last run", "rebuilt": False}
    except (OSError, ValueError):
        return dict(LAST)


def refresh_in_background(log=print, force=False, after_build=True):
    """Start-up / after a save: make missing pictures of code drawings first, then the prompts (never blocks)."""
    def run():
        try:
            if after_build:
                from . import codedraw
                codedraw.ensure_built(log=log)
            refresh(log=log, force=force)
        except Exception as ex:
            log(f"prompt refresh failed: {ex}")
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t
