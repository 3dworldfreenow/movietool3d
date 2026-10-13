"""🧊 Stick 3D on its own: a small web page to render Stick 3D stories (pick or paste a story JSON -> video).

    pip install -r requirements.txt
    python tools/get_piper_voices.py          # the offline voices (optional: edge voices need no download)
    STICK3D_PASSWORD=secret python stick3d_server.py --host 0.0.0.0 --port 8000

It is private like the studio: with no STICK3D_PASSWORD it only answers on this computer (127.0.0.1).
One render at a time; the videos land in output/stick3d/, the pasted stories in stories/mine/.
"""
import argparse
import glob
import hmac
import json
import os
import re
import subprocess
import sys
import threading
import time

from flask import Flask, abort, jsonify, redirect, request, send_from_directory, session

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output", "stick3d")
MINE = os.path.join(ROOT, "stories", "mine")
PASSWORD = os.environ.get("STICK3D_PASSWORD", "")

app = Flask(__name__)
app.secret_key = os.environ.get("STICK3D_SECRET") or os.urandom(24)
JOB = {"state": "idle", "story": "", "video": "", "log": [], "started": 0.0}
LOCK = threading.Lock()


def _safe(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:60] or "story"


def _is_stick3d(path):
    try:
        with open(path, encoding="utf-8") as f:
            s = f.read()
        return '"stick_place"' in s or '"stick3d"' in s
    except OSError:
        return False


def _stories():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "stories", "**", "*.json"), recursive=True)):
        if _is_stick3d(p):
            out.append(os.path.relpath(p, ROOT).replace(os.sep, "/"))
    return out


@app.before_request
def _gate():
    if request.endpoint in ("login", "static"):
        return None
    if not PASSWORD:
        if request.remote_addr not in ("127.0.0.1", "::1"):
            abort(403)                                     # (no password: this computer only)
        return None
    if not session.get("ok"):
        return redirect("/login") if request.method == "GET" and not request.path.startswith("/api") else abort(401)
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if PASSWORD and hmac.compare_digest(request.form.get("password", ""), PASSWORD):
            session["ok"] = True
            return redirect("/")
        time.sleep(1.0)                                    # (slow down guessing)
    return ("<!doctype html><meta name=viewport content='width=device-width'><title>Stick 3D</title>"
            "<form method=post style='font:16px sans-serif;margin:20vh auto;max-width:300px'>"
            "<h2>🧊 Stick 3D</h2><input type=password name=password placeholder=Password autofocus "
            "style='width:100%;padding:8px'><button style='margin-top:8px;padding:8px 16px'>Log in</button></form>")


def _run(story, opts):
    cmd = [sys.executable, "main.py", "render", story, "-o", os.path.join(OUT, _safe(
        os.path.splitext(os.path.basename(story))[0]) + ".mp4"), "--tts", opts.get("tts", "auto"),
        "--resolution", opts.get("resolution", "1280x720"), "--no-hook"]
    if opts.get("scene"):
        cmd += ["--scene", str(int(opts["scene"]))]
    os.makedirs(OUT, exist_ok=True)
    try:
        p = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
        for line in p.stdout:
            JOB["log"] = (JOB["log"] + [line.rstrip()])[-40:]
        p.wait()
        video = cmd[cmd.index("-o") + 1]
        ok = p.returncode == 0 and os.path.exists(video)
        JOB.update(state="done" if ok else "failed", video=os.path.basename(video) if ok else "")
    except Exception as ex:
        JOB.update(state="failed", log=JOB["log"] + [str(ex)])
    finally:
        LOCK.release()


@app.route("/api/stories")
def api_stories():
    return jsonify(_stories())


@app.route("/api/story")
def api_story():
    rel = request.args.get("path", "")
    if rel not in _stories():
        abort(404)
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return jsonify({"path": rel, "text": f.read()})


@app.route("/api/save", methods=["POST"])
def api_save():
    d = request.get_json(force=True)
    try:
        story = json.loads(d.get("text", ""))
    except ValueError as ex:
        return jsonify({"ok": False, "error": f"not JSON: {ex}"}), 400
    os.makedirs(MINE, exist_ok=True)
    rel = f"stories/mine/{_safe(d.get('name') or story.get('title', 'story'))}.json"
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)
    r = subprocess.run([sys.executable, "main.py", "validate", rel], cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    return jsonify({"ok": True, "path": rel, "check": (r.stdout + r.stderr)[-3000:]})


@app.route("/api/render", methods=["POST"])
def api_render():
    d = request.get_json(force=True)
    rel = d.get("path", "")
    if rel not in _stories():
        return jsonify({"ok": False, "error": "pick a Stick 3D story first"}), 400
    if not LOCK.acquire(blocking=False):
        return jsonify({"ok": False, "error": "a render is already running"}), 409
    JOB.update(state="running", story=rel, video="", log=[], started=time.time())
    threading.Thread(target=_run, args=(rel, d), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/job")
def api_job():
    return jsonify(dict(JOB, seconds=int(time.time() - JOB["started"]) if JOB["started"] else 0))


@app.route("/api/videos")
def api_videos():
    files = sorted(glob.glob(os.path.join(OUT, "*.mp4")), key=os.path.getmtime, reverse=True)
    return jsonify([{"name": os.path.basename(f), "mb": round(os.path.getsize(f) / 1e6, 1)} for f in files])


@app.route("/video/<path:name>")
def video(name):
    return send_from_directory(OUT, os.path.basename(name), as_attachment=bool(request.args.get("dl")))


PAGE = r"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>Stick 3D</title><style>
body{font:15px system-ui,sans-serif;margin:0;background:#f6f4ee;color:#222}
main{max-width:980px;margin:auto;padding:16px}h1{font-size:22px}
section{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;margin:12px 0}
textarea{width:100%;height:260px;font:12px monospace;box-sizing:border-box}
select,input,button{font:inherit;padding:6px 10px;margin:2px}button{cursor:pointer}
pre{background:#222;color:#cfc;padding:8px;max-height:220px;overflow:auto;font-size:12px;white-space:pre-wrap}
video{width:100%;max-height:480px;background:#000}li{margin:4px 0}
</style></head><body><main><h1>🧊 Stick 3D</h1>
<section><b>1. Story</b><br>
<select id=pick style="max-width:100%"></select> <button onclick=load()>Open</button>
<input type=file id=file accept=.json> <br>
<textarea id=text placeholder="Paste a Stick 3D story JSON here (or open one above)"></textarea><br>
<input id=name placeholder="name (to save a pasted story)"> <button onclick=save()>Save + check</button></section>
<section><b>2. Render</b><br>
Voices <select id=tts><option>auto</option><option>piper</option><option>edge</option><option>silent</option></select>
Size <select id=res><option>1280x720</option><option>1920x1080</option><option>1080x1920</option><option>854x480</option></select>
Only scene <input id=scene type=number min=1 style=width:70px>
<button onclick=render()>▶ Render</button> <span id=state></span><pre id=log></pre></section>
<section><b>3. Videos</b><video id=player controls></video><ul id=vids></ul></section>
</main><script>
const $ = id => document.getElementById(id);
async function j(u, o) { const r = await fetch(u, o); return r.json(); }
async function stories(sel) { const s = await j('/api/stories');
  $('pick').innerHTML = s.map(p => `<option${p === sel ? ' selected' : ''}>${p}</option>`).join(''); }
async function load() { const r = await j('/api/story?path=' + encodeURIComponent($('pick').value)); $('text').value = r.text; }
$('file').onchange = async e => { const f = e.target.files[0]; if (!f) return;
  $('text').value = await f.text(); $('name').value = f.name.replace(/\.json$/, ''); };
async function save() { const r = await j('/api/save', {method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({text: $('text').value, name: $('name').value})});
  $('log').textContent = r.ok ? 'saved ' + r.path + '\n' + r.check : r.error; if (r.ok) stories(r.path); }
async function render() { const r = await j('/api/render', {method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({path: $('pick').value, tts: $('tts').value, resolution: $('res').value, scene: $('scene').value})});
  if (!r.ok) $('log').textContent = r.error; poll(); }
async function poll() { const r = await j('/api/job');
  $('state').textContent = r.state === 'running' ? `rendering ${r.story} … ${r.seconds} s` : r.state;
  $('log').textContent = r.log.join('\n'); $('log').scrollTop = 1e9;
  if (r.state === 'running') setTimeout(poll, 2000); else videos(); }
async function videos() { const v = await j('/api/videos');
  $('vids').innerHTML = v.map(x => `<li><a href="#" onclick="$('player').src='/video/${x.name}';return false">▶ ${x.name}</a>
    (${x.mb} MB) <a href="/video/${x.name}?dl=1">⬇</a></li>`).join('') || '<li>none yet</li>'; }
stories(); poll();
</script></body></html>"""


@app.route("/")
def index():
    return PAGE


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    if a.host not in ("127.0.0.1", "localhost") and not PASSWORD:
        sys.exit("set STICK3D_PASSWORD before opening Stick 3D to other computers")
    app.run(host=a.host, port=a.port, threaded=True)
