"""Parts and the final mix.

A story is made of PARTS, one per section of its JSON:
    title        the opening title card      (settings.title_card / "title")
    scene1..N    every scene                 ("scenes"[i])
    end          the end card                (settings.end_text / end_subtitle)

Every part is rendered on its own into output/production/parts/<fingerprint>.mp4. The fingerprint is a hash of
exactly what that part shows (its JSON section, the characters, the settings and the render options), so a
part that did not change is never rendered again - change one scene and only that scene is made again.

The final mix joins the ticked parts (video copied, sound re-encoded, subtitles moved to their new times) into
one MP4. Everything runs in a background thread of the web app: closing the browser does not stop it, the state
is saved in output/production/state.json, and a stopped job keeps every finished part (and the finished 30 s
pieces of the part it was making) so "Resume" goes on from there.
"""
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDIR = os.path.join(HERE, "output", "production")
PARTS = os.path.join(PDIR, "parts")
STATE_FILE = os.path.join(PDIR, "state.json")
STORY_FILE = os.path.join(PDIR, "story.json")
VERSION = 2                                    # bump when the engine changes how parts look (old ones are remade)
PIECE_SEC = 30          # while a part renders it is saved in pieces of this many seconds (Stop / Resume goes on from
                        # the last finished piece). Smaller = more, shorter pieces: less work lost on a stop (e.g. 15)
OPTS = ("preview", "tts", "music", "vertical", "mode3d", "size", "subs", "detail")
# quick previews: size -> (landscape, vertical, fps). Smaller + fewer frames = much faster to check a story
PREVIEW_SIZES = {"360": ("640x360", "360x640", 24), "240": ("426x240", "240x426", 20), "144": ("256x144", "144x256", 15)}


def render_args(preview, size=None, vertical=False):
    """main.py flags for the quality: full 1080p, or a quick preview of 360p / 240p / 144p."""
    if not preview:
        return ["--resolution", "1080x1920"] if vertical else []
    size = str(size or "360").rstrip("p")
    land, vert, fps = PREVIEW_SIZES.get(size, PREVIEW_SIZES["360"])
    out = ["--preview", "--resolution", vert if vertical else land]
    if fps != 24:
        out += ["--fps", str(fps)]
    return out


def subs_args(subs):
    """Subtitles on the video: "on" / "off" -> main.py flag; anything else = what the story says."""
    return {"on": ["--subs"], "off": ["--no-subs"]}.get(str(subs or "").lower(), [])


def piece_args(piece, default=None):
    """The "💾 Save progress" choice -> main.py flags. "15" = every 15 seconds, "n3" = 3 pieces, "0" = in one go.
    It only changes how often a render is saved (Stop / Resume), never the picture - so it is NOT part of a
    part's fingerprint: changing it never makes finished parts again."""
    v = str(piece if piece not in (None, "") else (default if default is not None else "")).strip().lower()
    if not v:
        return []
    try:
        if v.startswith("n"):
            return ["--pieces", str(max(1, min(50, int(v[1:]))))]
        sec = float(v)
        return ["--part", "0" if sec <= 0 else str(max(5.0, min(600.0, sec)))]
    except ValueError:
        return []


WEIGHT = {"title": 0.3, "end": 0.3, "scene": 1.0}

os.makedirs(PARTS, exist_ok=True)


# ============================================================================ story <-> parts
def _end_text(st):
    return st.get("end_text", "The End")


def flag_on(v, default=True):
    """A JSON on/off setting the same way everywhere: false / 0 / null / "" / "false" / "off" / "no" = off."""
    if v is None and default is not None:
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("", "false", "off", "no", "0", "none")
    return bool(v)


def scene_no(key):
    """"scene3" / "scene3.2" (piece 2 of scene 3, when parts are cut by time) -> 3."""
    return int(str(key)[5:].split(".")[0])


STUDIO_FILE = os.path.join(HERE, "studio_settings.json")


def studio():
    """Your own defaults (studio_settings.json): {"cut_parts": 0, "save_every": 30}. Read fresh every time."""
    try:
        with open(STUDIO_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _pick(page, data, story_key, file_key):
    """What counts, in order: the web page's choice ("" / "auto" = no choice) > the story's "settings" >
    studio_settings.json > None."""
    if page not in (None, "", "auto"):
        return page
    st = (data or {}).get("settings") or {}
    if st.get(story_key) not in (None, ""):
        return st.get(story_key)
    v = studio().get(file_key)
    return None if v in (None, "") else v


def cut_of(opts, data=None):
    """"✂ Cut parts by": 0 = by scene, else seconds per part (long scenes become several parts).
    Page choice > story "settings": {"cut_parts": 5} > studio_settings.json "cut_parts" > by scene."""
    try:
        v = float(_pick((opts or {}).get("cut"), data, "cut_parts", "cut_parts") or 0)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if v <= 0 else max(5.0, min(600.0, v))


def save_every(page, data=None):
    """"💾 Save progress": page choice > story "settings": {"save_every": 10} > studio_settings.json > PIECE_SEC."""
    v = _pick(page, data, "save_every", "save_every")
    return str(PIECE_SEC) if v is None else str(v)


DUR_FILE = os.path.join(PDIR, "scene_lengths.json")


def _dur_key(data, key, opts):
    o = _norm_opts(opts)
    blob = json.dumps({"v": VERSION, "story": part_story(data, key), "tts": o["tts"], "mode3d": o["mode3d"],
                       "subs": o["subs"]}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def scene_lengths(data, opts, log=None):
    """{"scene3": seconds} - how long every scene REALLY is (its voices, its actions), worked out the same way
    the render does, so time parts are cut exactly. Remembered: a scene is measured again only when it changes."""
    try:
        with open(DUR_FILE, encoding="utf-8") as f:
            known = json.load(f)
    except (OSError, ValueError):
        known = {}
    out, todo = {}, []
    for i, _sc in enumerate(data.get("scenes") or []):
        k = f"scene{i + 1}"
        dk = _dur_key(data, k, opts)
        if dk in known:
            out[k] = known[dk]
        else:
            todo.append((k, dk))
    if todo:
        from .project import Project
        import tempfile
        o = _norm_opts(opts)
        for k, dk in todo:
            if log:
                log(f"working out how long {k} is ...")
            fd, path = tempfile.mkstemp(suffix=".json", prefix="len_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(part_story(data, k), f, ensure_ascii=False)
            try:
                popts = {"tts": o["tts"] or None, "cache": os.path.join(HERE, "cache")}
                if o["mode3d"]:
                    popts["camera_mode"] = "3d"
                P = Project(path, popts, log=lambda *a: None)
                out[k] = known[dk] = round(float(P.duration), 3)
            finally:
                os.remove(path)
        known = dict(list(known.items())[-2000:])
        with open(DUR_FILE, "w", encoding="utf-8") as f:
            json.dump(known, f)
    return out


def _pieces(length, cut):
    """[(t0, t1 or None)] - the time parts of a scene (the last runs to the end; a short tail joins it)."""
    if not cut or length <= cut * 1.4:
        return [(0.0, None)]
    k = int(length // cut)
    if length - k * cut < cut * 0.4:
        k -= 1                                           # a tiny last bit joins the part before
    return [(j * cut, (j + 1) * cut) for j in range(k)] + [(k * cut, None)]


def _mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def plan(data, opts=None, lengths=None):
    """[{key, kind, index, label, detail, on}] for a story dict - the parts it is made of, in order.
    The title and end cards are always offered (when there is a title / always); "on" = switched on in the JSON,
    so an AI story with "title_card": false shows its title part unticked instead of losing it."""
    st = data.get("settings") or {}
    out = []
    if data.get("title"):
        on = flag_on(st.get("title_card", True))
        out.append({"key": "title", "kind": "title", "index": 0, "label": "Opening title", "on": on,
                    "detail": str(data.get("title")) + ("" if on else " · off in the story JSON - tick it to add it")})
    for i, sc in enumerate(data.get("scenes") or []):
        bg = sc.get("background")
        place = bg.get("preset") or bg.get("image") if isinstance(bg, dict) else bg
        who = [c.get("id") if isinstance(c, dict) else c for c in (sc.get("characters") or [])][:4]
        lines = sum(1 for e in (sc.get("events") or []) if isinstance(e, dict) and (e.get("say") or e.get("narrate")))
        base = {"key": f"scene{i + 1}", "kind": "scene", "index": i + 1,
                "label": f"Scene {i + 1}" + (f": {sc.get('id')}" if sc.get("id") else ""),
                "on": True,
                "detail": " · ".join(x for x in [str(place or ""), ", ".join(str(w) for w in who if w),
                                                 f"{lines} line(s)"] if x)}
        cut = cut_of(opts, data)
        ln = (lengths or {}).get(f"scene{i + 1}")
        pcs = _pieces(ln, cut) if (cut and ln) else [(0.0, None)]
        if len(pcs) == 1:
            out.append(base)
            continue
        for j, (t0, t1) in enumerate(pcs):                # ✂ cut by time: this scene is several parts
            out.append(dict(base, key=f"scene{i + 1}.{j + 1}", piece=j + 1, window=[t0, t1],
                            label=f"{base['label']} · {_mmss(t0)}–{_mmss(t1 if t1 is not None else ln)}",
                            detail=f"part {j + 1} of {len(pcs)} of this scene · " + base["detail"]))
    end_on = bool(_end_text(st))
    out.append({"key": "end", "kind": "end", "index": 999, "label": "End card", "on": end_on,
                "detail": str(_end_text(st) or "The End") + ("" if end_on else " · off in the story JSON - tick it to add it")})
    return out


def get_section(data, key):
    """The JSON section a part maps to (what "Edit JSON" shows)."""
    st = data.get("settings") or {}
    if key == "title":
        return {"title": data.get("title", ""), "title_duration": st.get("title_duration", 3.5)}
    if key == "end":
        return {"end_text": _end_text(st), "end_subtitle": st.get("end_subtitle", ""),
                "end_duration": st.get("end_duration", 3.0)}
    i = scene_no(key) - 1
    return (data.get("scenes") or [])[i]


def set_section(data, key, sec):
    """Put an edited section back into the story (returns a new dict)."""
    d = copy.deepcopy(data)
    st = d.setdefault("settings", {})
    if key == "title":
        if "title" in sec:
            d["title"] = sec["title"]
        if "title_duration" in sec:
            st["title_duration"] = sec["title_duration"]
    elif key == "end":
        for k in ("end_text", "end_subtitle", "end_duration"):
            if k in sec:
                st[k] = sec[k]
    else:
        i = scene_no(key) - 1
        if not isinstance(sec, dict) or not isinstance(sec.get("events", []), list):
            raise ValueError("a scene must be a JSON object (with \"events\": [...])")
        d["scenes"][i] = sec
    return d


def final_story(data, keys):
    """The story with only the ticked parts: unticked scenes are left out, an unticked title / end card is
    switched off in "settings"."""
    d = copy.deepcopy(data)
    keys = set(keys)
    scenes_in = {scene_no(k) for k in keys if str(k).startswith("scene")}      # a scene is in if any of its parts is
    d["scenes"] = [sc for i, sc in enumerate(d.get("scenes") or []) if i + 1 in scenes_in]
    st = d.setdefault("settings", {})
    st["title_card"] = "title" in keys and bool(d.get("title"))          # ticked = on, even if the JSON had it off
    if "end" in keys:
        st["end_text"] = _end_text(st) or "The End"
    else:
        st["end_text"] = ""
    return d


def _norm_opts(opts):
    o = {k: (opts or {}).get(k) for k in OPTS}
    o["preview"] = bool(o["preview"])
    o["vertical"] = bool(o["vertical"])
    o["mode3d"] = bool(o["mode3d"])
    o["tts"] = o["tts"] or ""
    o["music"] = o["music"] or ""
    o["subs"] = str(o["subs"] or "").lower() if str(o["subs"] or "").lower() in ("on", "off") else ""
    o["detail"] = str(o["detail"] or "").lower() if str(o["detail"] or "").lower() in ("low", "medium", "high") else ""
    if not o["detail"]:
        o.pop("detail")                                  # not set: parts made before this setting keep their fingerprint
    o["size"] = (str(o["size"] or "360").rstrip("p") if o["preview"] else "full")
    if o["size"] not in PREVIEW_SIZES and o["preview"]:
        o["size"] = "360"
    return o


def part_story(data, key):
    """The story file that renders just this part (no hook / title / end card around a scene)."""
    d = copy.deepcopy(data)
    st = d.setdefault("settings", {})
    st["hook"] = "off"
    st.pop("need_3d", None)
    scenes = d.get("scenes") or []
    if key in ("title", "end"):
        d["scenes"] = scenes[:1]                           # the engine needs one scene; only the card is drawn
        if key == "title":
            st["title_card"] = True
            for k in ("end_text", "end_subtitle", "end_duration"):
                st.pop(k, None)
        else:
            st["end_text"] = _end_text(st) or "The End"
            for k in ("title_card", "title_duration"):
                st.pop(k, None)
    else:
        i = scene_no(key) - 1
        d["scenes"] = [scenes[i]]
        st["title_card"] = False
        st["end_text"] = ""
        for k in ("title_duration", "end_subtitle", "end_duration"):
            st.pop(k, None)                                # card settings don't change a scene
    return d


def fingerprint(data, key, opts, window=None):
    d = part_story(data, key)
    if key in ("title", "end"):                            # a card does not depend on the scene next to it
        d["scenes"] = []
    what = {"v": VERSION, "part": key if key in ("title", "end") else "scene", "story": d, "opts": _norm_opts(opts)}
    if window:                                             # a time part: which seconds of the scene
        what["window"] = [round(window[0], 3), None if window[1] is None else round(window[1], 3)]
    blob = json.dumps(what, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def part_file(fp):
    return os.path.join(PARTS, fp + ".mp4")


def describe(data, opts, log=None):
    """plan() + for every part: its fingerprint and whether it is already made (reused, not made again)."""
    rows = []
    lengths = scene_lengths(data, opts, log) if cut_of(opts, data) else None
    for p in plan(data, opts, lengths):
        fp = fingerprint(data, p["key"], opts, p.get("window"))
        f = part_file(fp)
        made = os.path.exists(f)
        p.update(fp=fp, made=made, file=os.path.basename(f) if made else None,
                 made_at=os.path.getmtime(f) if made else None,
                 size_mb=round(os.path.getsize(f) / 1e6, 1) if made else None,
                 duration=_duration(f) if made else None,
                 partial=os.path.isdir(os.path.join(PARTS, fp + ".tmp.parts")))
        rows.append(p)
    return rows


# ============================================================================ ffmpeg helpers
def _ff():
    from .render import find_ffmpeg
    return find_ffmpeg()


def _duration(path):
    try:
        r = subprocess.run([_ff(), "-i", path], capture_output=True, text=True, timeout=30)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except (OSError, subprocess.SubprocessError, SystemExit):
        pass
    return None


def _srt_items(path):
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
    except OSError:
        return []
    out = []
    for block in re.split(r"\n\s*\n", txt.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        out.append((a, b, "\n".join(lines[2:])))
    return out


def _ts(t):
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)) % 1000:03d}"


# ============================================================================ the runner
class Runner:
    """One production job at a time, in a background thread. Its state is saved on disk."""

    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.proc = None
        self.stop_flag = False
        self.state = self._load()
        if self.state.get("status") in ("running", "stopping"):      # the app restarted while it ran
            self._kill_orphan(self.state.get("pid"))
            self.state["status"] = "interrupted"
            self.state["message"] = "The app was restarted while this was running - press Resume to go on."
            for p in self.state.get("parts", []):
                if p.get("status") in ("rendering", "queued"):
                    p["status"] = "waiting"
            self._save(force=True)
        self._saved_at = 0.0

    @staticmethod
    def _kill_orphan(pid):
        """A render left over from before a restart would fight the resumed one over the same files."""
        if not pid:
            return
        try:
            with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
                cmd = f.read().decode(errors="replace")
        except (OSError, ValueError):
            cmd = None
        if cmd is None:
            try:
                import psutil
                cmd = " ".join(psutil.Process(int(pid)).cmdline())
            except Exception:                                   # noqa: BLE001
                return
        if "main.py" in cmd and "render" in cmd:
            from . import sysmon
            sysmon.kill_tree(int(pid))

    # ---------------------------------------------------------------- state
    def _load(self):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"status": "idle"}

    def _save(self, force=False):
        now = time.time()
        if not force and now - getattr(self, "_saved_at", 0.0) < 1.0:
            return
        self._saved_at = now
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)

    def snapshot(self):
        with self.lock:
            s = copy.deepcopy(self.state)
        s["log"] = (s.get("log") or [])[-40:]
        s["alive"] = bool(self.thread and self.thread.is_alive())
        return s

    def busy(self):
        return bool(self.thread and self.thread.is_alive())

    def _set(self, **kw):
        with self.lock:
            self.state.update(kw)
            self._save(force=True)

    def _part(self, key, **kw):
        with self.lock:
            for p in self.state.get("parts", []):
                if p["key"] == key:
                    p.update(kw)
            self._progress()
            self._save()

    def _progress(self):
        parts = [p for p in self.state.get("parts", []) if p.get("selected")]
        tot = sum(WEIGHT[p["kind"]] for p in parts) or 1.0
        done = 0.0
        for p in parts:
            w = WEIGHT[p["kind"]]
            if p.get("status") in ("done", "reused"):
                done += w
            elif p.get("status") in ("rendering", "stopped"):
                done += w * float(p.get("progress") or 0.0)
        mixing = self.state.get("mode") == "mix"
        frac = done / tot
        if mixing:
            frac = frac * 0.96 + (0.04 if self.state.get("stage") == "done" else 0.0)
        self.state["progress"] = round(min(1.0, frac), 4)

    def _log(self, line):
        with self.lock:
            lg = self.state.setdefault("log", [])
            lg.append(line)
            del lg[:-300]

    # ---------------------------------------------------------------- start / stop
    def start(self, data, keys, opts, mode, delete_parts=True, force=None):
        """mode "make": render the ticked parts that are missing. mode "mix": that, then the final mix."""
        if self.busy():
            raise RuntimeError("A process is already running - stop it or wait until it is done.")
        keys = [k for k in (keys or [])]
        if mode == "mix":
            data = final_story(data, keys)              # the final JSON: only the ticked parts
            lengths = scene_lengths(data, opts) if cut_of(opts, data) else None
            skip = set((opts or {}).get("skip") or [])  # single time parts left out of a scene that stays
            keys = [p["key"] for p in plan(data, opts, lengths) if p["on"] and p["key"] not in skip]
        with open(STORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        rows = describe(data, opts)
        force = set(force or [])
        for r in rows:
            r["selected"] = r["key"] in keys
            r["status"] = ("reused" if r["made"] and r["key"] not in force else "waiting") if r["selected"] else "skipped"
            r["progress"] = 1.0 if r["status"] == "reused" else 0.0
        run_id = uuid.uuid4().hex[:6]
        title = re.sub(r"[^a-zA-Z0-9]+", "_", str(data.get("title", "story"))).strip("_")[:40] or "story"
        with self.lock:
            self.state = {"id": run_id, "status": "running", "mode": mode, "title": data.get("title", "story"),
                          "slug": title, "opts": _norm_opts(opts), "keys": keys, "delete_parts": bool(delete_parts),
                          "piece": save_every((opts or {}).get("piece"), data),
                          "force": sorted(force), "parts": rows, "current": None, "stage": "starting",
                          "progress": 0.0, "started": time.time(), "log": [], "final": None, "message": ""}
            self._progress()
            self._save(force=True)
        self.stop_flag = False
        self.thread = threading.Thread(target=self._run, daemon=True, name="production")
        self.thread.start()
        return run_id

    def resume(self):
        s = self.snapshot()
        if s.get("status") not in ("stopped", "interrupted", "failed"):
            raise RuntimeError("Nothing to resume.")
        try:
            with open(STORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            raise RuntimeError("The story of that job is gone - start it again.") from None
        keys = [p["key"] for p in s.get("parts", []) if p.get("selected")]
        done_forced = {p["key"] for p in s.get("parts", []) if p.get("status") == "done"}
        force = [k for k in s.get("force", []) if k not in done_forced]
        # the story is already the final one for a mix
        self.start(data, keys, s.get("opts") or {}, s.get("mode") or "make", s.get("delete_parts", True), force)

    def stop(self):
        self.stop_flag = True
        proc = self.proc
        if proc is not None and proc.poll() is None:
            from . import sysmon
            sysmon.kill_tree(proc.pid)
        if self.busy():
            self._set(status="stopping", stage="stopping…")
            return True
        return False

    def dismiss(self):
        if self.busy():
            return False
        self._set(status="idle", message="")
        return True

    # ---------------------------------------------------------------- the work
    def _cmd(self, story_path, key, out, opts):
        cmd = [sys.executable, "-u", os.path.join(HERE, "main.py"), "render", story_path, "-o", out, "--no-remember",
               "--no-lang-files"]
        cmd += piece_args((self.state or {}).get("piece"), str(PIECE_SEC))
        if (opts or {}).get("detail"):
            cmd += ["--world-detail", opts["detail"]]
        if (opts or {}).get("low_ram"):
            cmd.append("--low-ram")
        row = next((r for r in (self.state or {}).get("parts", []) if r.get("key") == key), None)
        win = (row or {}).get("window")
        if win:                                          # ✂ a time part: only these seconds of the scene
            cmd += ["--from", str(win[0])] + (["--to", str(win[1])] if win[1] is not None else [])
        cmd += render_args(opts.get("preview"), opts.get("size"), opts.get("vertical"))
        if opts.get("tts"):
            cmd += ["--tts", opts["tts"]]
        if opts.get("music"):
            cmd += ["--music", opts["music"]]
        if opts.get("mode3d"):
            cmd.append("--3d")
        cmd += subs_args(opts.get("subs"))
        if key in ("title", "end"):
            cmd += ["--only", key]
        return cmd

    def _render_part(self, data, p, opts):
        from . import sysmon
        key, fp = p["key"], p["fp"]
        story_path = os.path.join(PARTS, fp + ".json")
        with open(story_path, "w", encoding="utf-8") as f:
            json.dump(part_story(data, key), f, ensure_ascii=False, indent=2)
        tmp_out = os.path.join(PARTS, fp + ".tmp.mp4")
        self._part(key, status="rendering", progress=0.0, started=time.time())
        self._set(current=key, stage=f"{p['label']}: starting")
        self._log(f"── {p['label']} ──")
        proc = subprocess.Popen(self._cmd(story_path, key, tmp_out, opts), cwd=HERE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
        self.proc = proc
        self._set(pid=proc.pid)
        sysmon.GOV.watch(proc.pid)
        buf = ""
        try:
            while True:
                ch = proc.stdout.read(1)
                if not ch:
                    break
                if ch not in "\r\n":
                    buf += ch
                    continue
                line, buf = buf.strip(), ""
                if not line:
                    continue
                m = re.search(r"frame (\d+)/(\d+)", line)
                if m:
                    prog = int(m.group(1)) / max(1, int(m.group(2)))
                    self._part(key, progress=round(prog * 0.97, 4))
                    with self.lock:
                        self.state["stage"] = f"{p['label']}: {line}"
                else:
                    self._log(line)
                    if line.startswith("[") or "part " in line:
                        with self.lock:
                            self.state["stage"] = f"{p['label']}: {line}"
        finally:
            rc = proc.wait()
            sysmon.GOV.unwatch(proc.pid)
            self.proc = None
        if self.stop_flag:
            self._part(key, status="stopped")
            return False
        if rc != 0 or not os.path.exists(tmp_out):
            self._part(key, status="failed")
            raise RuntimeError(f"{p['label']} failed (see the log)")
        final = part_file(fp)
        os.replace(tmp_out, final)
        tmp_base = os.path.splitext(tmp_out)[0]                  # <fp>.tmp.srt, <fp>.tmp.en.srt ... -> <fp>.srt, <fp>.en.srt
        for f in os.listdir(PARTS):
            full = os.path.join(PARTS, f)
            if full.startswith(tmp_base + ".") and f.endswith(".srt"):
                os.replace(full, os.path.join(PARTS, fp + full[len(tmp_base):]))
        self._part(key, status="done", progress=1.0, file=os.path.basename(final), made=True,
                   duration=_duration(final), size_mb=round(os.path.getsize(final) / 1e6, 1), made_at=time.time())
        return True

    def _mix(self, parts):
        self._set(stage="Final mix: joining the parts", current="mix")
        self._log("── Final mix ──")
        ff = _ff()
        work = os.path.join(PDIR, "mix_" + self.state["id"])
        os.makedirs(work, exist_ok=True)
        lst = os.path.join(work, "parts.txt")
        try:                                                     # the story's languages: every one gets its track
            with open(STORY_FILE, encoding="utf-8") as f:
                st = (json.load(f).get("settings") or {})
        except (OSError, ValueError):
            st = {}
        from .tts import ISO3, LANG_NAMES
        langs = [st.get("language") or "en-IN"] + [l for l in (st.get("languages") or []) if l != st.get("language")]
        sufs = [""] + ["." + l.split("-")[0].lower() for l in langs[1:]]      # <fp>.srt, <fp>.en.srt ...
        cues = {s: [] for s in sufs}
        t = 0.0
        with open(lst, "w", encoding="utf-8") as f:
            for p in parts:
                path = part_file(p["fp"])
                f.write("file '" + os.path.abspath(path).replace("\\", "/").replace("'", "'\\''") + "'\n")
                for s in sufs:
                    for a, b, text in _srt_items(os.path.splitext(path)[0] + s + ".srt"):
                        cues[s].append((a + t, b + t, text))
                t += _duration(path) or 0.0
        out = os.path.join(HERE, "output", f"{self.state['slug']}_{self.state['id']}.final.mp4")
        cmd = [ff, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst]
        maps, meta, n_in, k_sub = ["-map", "0:v", "-map", "0:a?"], [], 1, 0
        iso = lambda l: ISO3.get(l.split("-")[0].lower(), "und")               # noqa: E731
        for k, l in enumerate(langs):                            # audio tracks: the same order as in the parts
            meta += [f"-metadata:s:a:{k}", f"language={iso(l)}", f"-metadata:s:a:{k}", f"title={LANG_NAMES.get(l, l)}"]
        for s, l in zip(sufs, langs):
            srt = os.path.splitext(out)[0] + s + ".srt"
            with open(srt, "w", encoding="utf-8") as f:
                for n, (a, b, text) in enumerate(sorted(cues[s]), 1):
                    f.write(f"{n}\n{_ts(a)} --> {_ts(b)}\n{text}\n\n")
            if cues[s]:
                cmd += ["-i", srt]
                maps += ["-map", f"{n_in}:s"]
                meta += [f"-metadata:s:s:{k_sub}", f"language={iso(l)}", f"-metadata:s:s:{k_sub}", f"title={LANG_NAMES.get(l, l)}"]
                n_in += 1
                k_sub += 1
            elif s:
                os.remove(srt)
        if k_sub:
            maps += ["-c:s", "mov_text"]
        cmd += maps + meta + ["-c:v", "copy", "-c:a", "aac", "-strict", "-2", "-b:a", "192k", "-movflags", "+faststart", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        shutil.rmtree(work, ignore_errors=True)
        if r.returncode != 0 or not os.path.exists(out):
            raise RuntimeError("Final mix failed: " + (r.stderr.strip()[-400:] or "ffmpeg error"))
        return out

    def _run(self):
        try:
            with open(STORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
            opts = self.state["opts"]
            todo = [p for p in self.state["parts"] if p.get("selected")]
            for p in todo:
                if self.stop_flag:
                    break
                if p.get("status") == "reused":
                    continue
                if p["key"] in set(self.state.get("force") or []):       # "make again": drop the old one
                    for ext in (".mp4", ".srt"):
                        try:
                            os.remove(os.path.splitext(part_file(p["fp"]))[0] + ext)
                        except OSError:
                            pass
                if not self._render_part(data, p, opts):
                    break
            if self.stop_flag:
                self._set(status="stopped", stage="Stopped - finished parts are kept", current=None,
                          message="Stopped. Every finished part is kept; Resume goes on from where it stopped.")
                return
            if self.state.get("mode") == "mix":
                out = self._mix(todo)
                if self.state.get("delete_parts"):
                    for p in todo:                             # the parts were only steps to the final video
                        for f in os.listdir(PARTS):
                            if f.startswith(p["fp"] + "."):
                                try:
                                    os.remove(os.path.join(PARTS, f))
                                except OSError:
                                    pass
                self._set(final=os.path.basename(out), stage="done")
                with self.lock:
                    self._progress()
                    self.state["progress"] = 1.0
                self._set(status="done", current=None, finished=time.time(),
                          message=f"Final video ready: {os.path.basename(out)}")
            else:
                self._set(status="done", current=None, stage="Parts ready", progress=1.0, finished=time.time(),
                          message="All ticked parts are ready. Check them, then press Final mix.")
        except Exception as ex:                                # noqa: BLE001
            self._log(f"✖ {ex}")
            self._set(status="failed", current=None, stage=f"Failed: {ex}",
                      message=f"{ex}. Finished parts are kept - fix it and press Resume.")
        finally:
            from . import sysmon
            sysmon.GOV.release_all()


RUNNER = None


def runner():
    global RUNNER
    if RUNNER is None:
        RUNNER = Runner()
    return RUNNER


# ============================================================================ change one part with Gemini
CHANGE_SYSTEM = ("You edit Stickman Studio story JSON. You change ONLY what the user asks, keep every id, name and "
                 "the exact same JSON format, and answer with the JSON object only.")


def change_prompt(data, key, request):
    sec = get_section(data, key)
    chars = sorted((data.get("characters") or {}).keys())
    what = "scene" if str(key).startswith("scene") else ("title card settings" if key == "title" else "end card settings")
    return (f"Here is one {what} of the story \"{data.get('title', '')}\" (characters: {', '.join(chars)}).\n\n"
            f"{json.dumps(sec, ensure_ascii=False, indent=2)}\n\n"
            f"Change it like this: {request}\n\n"
            f"Rules: keep the same JSON structure and keys; use only characters, places, actions, camera shots "
            f"and objects that are already used in the story or are standard engine names; keep dialogue short. "
            f"Answer with the changed {what} JSON object only.")


def change_part(data, key, request):
    """-> (new story dict, new section). Raises GeminiError (the caller offers the ChatGPT prompt instead)."""
    from . import ai
    st = ai.settings()
    g = ai.Gemini(st["key"], st["model"], st["api_version"], log=lambda *a: None)
    text = g.generate(change_prompt(data, key, request), system=CHANGE_SYSTEM, json_mode=True,
                      temperature=min(0.7, st["temperature"]))
    sec = ai.extract_json(text)
    return set_section(data, key, sec), sec
