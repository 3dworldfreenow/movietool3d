"""🛡 Safe for real users - the small, important things (section 19.6 / 13):

    limits    requests per minute per person (their account, or their address when not logged in) on every /api/
              call - so one person (or one stuck script) cannot slow the server for everyone. The live walk sends up to
              4 a second, so it gets its own, bigger allowance. Over the limit: "429 slow down" for the rest of the minute.
    errors    every server error is written to logs/errors.log (with where it happened); the admin sees a summary of the
              last 24 hours at /api/admin/errors - the visitor only gets a friendly message, never the details
    backups   once a day users/, planets/ and minds/ (the peoples' memories) are zipped to backups/<date>.zip; the newest 7 are kept
    reports   🚩 "report a problem" from the walk: a short text + where you were -> reports/reports.jsonl (bad words
              masked, at most 6 an hour a person); the admin reads them at /api/admin/reports
"""
import json
import logging
import os
import threading
import time
import traceback
import zipfile
from collections import defaultdict
from logging.handlers import RotatingFileHandler

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS, BACKUPS, REPORTS = (os.path.join(HERE, d) for d in ("logs", "backups", "reports"))
LIMITS = [("/api/planets/live", 600), ("/api/me/", 180), ("/api/report", 20), ("/api/minds/say", 30), ("/api/p2p", 120), ("/api/home/life", 20), ("/api/home/town", 40), ("/api/", 300)]   # per minute (talking to the people: 30 - an AI answer costs)
KEEP_BACKUPS, REPORTS_PER_HOUR = 7, 6
_hits = defaultdict(lambda: [0, 0])                    # (who, rule) -> [minute, count]
_rep = defaultdict(list)
_lock = threading.Lock()
_log = None


def _who():
    from flask import request
    from . import auth
    try:
        u = auth.current_user()
    except Exception:                                  # noqa: BLE001
        u = None
    return u if u and u != "local" else (auth._ip() if hasattr(auth, "_ip") else request.remote_addr or "?")


def allow(who, path):
    """-> True when this request is within the person's allowance for this minute"""
    rule, cap = next(((p, c) for p, c in LIMITS if path.startswith(p)), (None, None))
    if not rule:
        return True
    m = int(time.time() // 60)
    with _lock:
        if len(_hits) > 20000:
            for k in [k for k, v in _hits.items() if v[0] != m]:
                del _hits[k]
        h = _hits[(who, rule)]
        if h[0] != m:
            h[0], h[1] = m, 0
        h[1] += 1
        return h[1] <= cap


def _logger():
    global _log
    if _log is None:
        os.makedirs(LOGS, exist_ok=True)
        _log = logging.getLogger("stickman.errors")
        _log.setLevel(logging.ERROR)
        h = RotatingFileHandler(os.path.join(LOGS, "errors.log"), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s\t%(message)s"))
        _log.addHandler(h)
        _log.propagate = False
    return _log


def log_error(where, ex):
    tb = traceback.extract_tb(ex.__traceback__)
    at = f"{os.path.basename(tb[-1].filename)}:{tb[-1].lineno}" if tb else "?"
    _logger().error("%s\t%s\t%s: %s\t%s", where, at, type(ex).__name__, str(ex)[:300].replace("\t", " ").replace("\n", " "),
                    " | ".join(f"{os.path.basename(f.filename)}:{f.lineno}" for f in tb[-6:]))


def error_summary(hours=24):
    """the last day's errors, grouped: [{error, where, count, last}]"""
    out, cut = {}, time.time() - hours * 3600
    for name in sorted(os.listdir(LOGS)) if os.path.isdir(LOGS) else []:
        if not name.startswith("errors.log"):
            continue
        try:
            with open(os.path.join(LOGS, name), encoding="utf-8") as f:
                for line in f:
                    p = line.rstrip("\n").split("\t")
                    if len(p) < 4:
                        continue
                    try:
                        t = time.mktime(time.strptime(p[0][:19], "%Y-%m-%d %H:%M:%S"))
                    except ValueError:
                        continue
                    if t < cut:
                        continue
                    k = (p[3][:120], p[2])
                    r = out.setdefault(k, {"error": p[3][:200], "where": p[2], "path": p[1], "count": 0, "last": p[0][:19]})
                    r["count"] += 1
                    r["last"] = max(r["last"], p[0][:19])
        except OSError:
            continue
    return sorted(out.values(), key=lambda r: -r["count"])


# ---------------------------------------------------------------- 💾 daily backups
def backup_now():
    os.makedirs(BACKUPS, exist_ok=True)
    day = time.strftime("%Y-%m-%d")
    path = os.path.join(BACKUPS, f"{day}.zip")
    if os.path.exists(path):
        return path
    with zipfile.ZipFile(path + ".tmp", "w", zipfile.ZIP_DEFLATED) as z:
        for top in ("users", "planets", "reports", "minds"):
            base = os.path.join(HERE, top)
            for root, _, files in os.walk(base):
                for fn in files:
                    if fn.endswith(".tmp"):
                        continue
                    full = os.path.join(root, fn)
                    z.write(full, os.path.relpath(full, HERE))
    os.replace(path + ".tmp", path)
    olds = sorted(f for f in os.listdir(BACKUPS) if f.endswith(".zip"))
    for f in olds[:-KEEP_BACKUPS]:
        try:
            os.remove(os.path.join(BACKUPS, f))
        except OSError:
            pass
    return path


def _backup_loop():
    while True:
        try:
            backup_now()
        except Exception as ex:                        # noqa: BLE001
            log_error("backup", ex)
        time.sleep(6 * 3600)


# ---------------------------------------------------------------- 🚩 reports
def add_report(who, text, planet=None, at=None, page=None):
    from . import wordfilter
    now = time.time()
    with _lock:
        ts = [t for t in _rep[who] if now - t < 3600]
        if len(ts) >= REPORTS_PER_HOUR:
            _rep[who] = ts
            return False
        _rep[who] = ts + [now]
    os.makedirs(REPORTS, exist_ok=True)
    row = {"t": int(now), "who": str(who)[:60], "text": wordfilter.clean(text, 500), "planet": str(planet or "")[:80],
           "at": at if isinstance(at, list) and len(at) == 2 and all(isinstance(v, (int, float)) for v in at) else None,
           "page": str(page or "")[:120]}
    with _lock, open(os.path.join(REPORTS, "reports.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True


def reports(n=100):
    try:
        with open(os.path.join(REPORTS, "reports.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(x) for x in f if x.strip()]
    except (OSError, ValueError):
        rows = []
    return list(reversed(rows[-n:]))


# ---------------------------------------------------------------- wiring
def init(app):
    from flask import jsonify, request
    from werkzeug.exceptions import HTTPException

    @app.before_request
    def _limit():
        if request.path.startswith("/api/") and not allow(_who(), request.path):
            return jsonify(ok=False, error="Too many requests - please slow down a little.", slow=True), 429
        return None

    @app.errorhandler(Exception)
    def _err(ex):
        if isinstance(ex, HTTPException):
            return ex
        log_error(f"{request.method} {request.path}", ex)
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Something went wrong on our side - it has been written down. Please try again."), 500
        return ("<h2>Something went wrong</h2><p>It has been written down. <a href='/'>Back</a></p>", 500)

    def _admin():
        from . import auth, userdata
        u = auth.current_user()
        return u and userdata.is_admin(u)

    @app.get("/api/admin/errors")
    def _errors():
        if not _admin():
            return jsonify(ok=False, error="admin only"), 403
        return jsonify(ok=True, errors=error_summary(int(request.args.get("hours", 24) or 24)))

    @app.get("/api/admin/updates")
    def _updates():
        if not _admin():
            return jsonify(ok=False, error="admin only"), 403
        try:
            with open(os.path.join(LOGS, "update.log"), encoding="utf-8") as f:
                lines = f.read().splitlines()[-80:]
        except OSError:
            lines = []
        return jsonify(ok=True, log=list(reversed(lines)))

    @app.get("/api/admin/reports")
    def _reports():
        if not _admin():
            return jsonify(ok=False, error="admin only"), 403
        return jsonify(ok=True, reports=reports())

    @app.post("/api/report")
    def _report():
        b = request.get_json(force=True, silent=True) or {}
        if len(request.get_data() or b"") > 4096:
            return jsonify(ok=False, error="too big"), 400
        text = str(b.get("text") or "").strip()
        if len(text) < 3:
            return jsonify(ok=False, error="please say what went wrong"), 400
        ok = add_report(_who(), text, b.get("planet"), b.get("at"), b.get("page"))
        return jsonify(ok=ok, error=None if ok else "thanks - you already sent a few reports this hour")

    if os.environ.get("STICKMAN_BACKUP", "on").lower() not in ("off", "0", "no"):
        threading.Thread(target=_backup_loop, daemon=True, name="backups").start()
