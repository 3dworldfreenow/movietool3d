"""Login for the web app: accounts with a password each, a session cookie (30 days), everything else locked.

    the admin   the first account (STICKMAN_USER / STICKMAN_PASSWORD, as before) - can add and remove accounts at /admin/users
    accounts    kept in output/.users.json: a name and a password hash each (never the password); names a-z 0-9 _ (3-20)
    sign-up     OFF (the studio is private: the admin adds accounts at /admin/users); STICKMAN_SIGNUP=on opens /signup
    studio      only the admin and accounts the admin added (or let in) may use it - the old game's self-made
                player accounts stay in output/.users.json but cannot log in (the admin can let one in)

Change them without touching code (e.g. in the systemd service file):
    Environment=STICKMAN_USER=newname
    Environment=STICKMAN_PASSWORD=newpassword
Only a hash of the default password is kept here. 🔒 The login is ON: the admin ("admin") logs in; no accounts are made
(sign-up off). STICKMAN_LOGIN=off switches the login off (e.g. localhost only).
"""
import hmac
import os
import secrets
import time
from datetime import timedelta

from flask import jsonify, redirect, request, session
import json
import re
from werkzeug.security import check_password_hash, generate_password_hash

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_USER = "admin"
DEFAULT_HASH = "scrypt:32768:8:1$DntVX7Qaj0T7ApY9$346850ea80c56b7b237a003f3da20ee50aa2b42b4013d01105f38477e64d7dcff3cb706d3276bfdb25ff25fb804045c3a6dff7cb2a6cfcfef1fd254db21dd67c"
OPEN = ("/login", "/logout", "/favicon.ico", "/signup")
PUBLIC = ()                                                         # (nothing is public: the studio is private)
USERS = os.path.join(HERE, "output", ".users.json")
NAME_RE = re.compile(r"^[a-z0-9_.\-]{3,40}$")                      # a user name ...
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")          # ... or an email address
_FAILS = {}                                     # ip -> [times of wrong tries]
MAX_TRIES, WINDOW = 5, 300                      # 5 wrong tries in 5 minutes -> wait


def _secret_key():
    """A random key kept on disk, so people stay logged in when the app restarts."""
    path = os.path.join(HERE, "output", ".secret_key")
    try:
        with open(path) as f:
            k = f.read().strip()
        if len(k) >= 32:
            return k
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    k = secrets.token_hex(32)
    with open(path, "w") as f:
        f.write(k)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return k


def _admin_name():
    return os.environ.get("STICKMAN_USER") or DEFAULT_USER


def _users():
    try:
        with open(USERS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_users(d):
    os.makedirs(os.path.dirname(USERS), exist_ok=True)
    tmp = USERS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, separators=(",", ":"))
    os.replace(tmp, USERS)
    try:
        os.chmod(USERS, 0o600)
    except OSError:
        pass


def add_user(name, pw, studio=False):
    """-> error text or "" (ok)"""
    name = str(name or "").strip().lower()
    if len(name) > 80 or not (NAME_RE.match(name) or EMAIL_RE.match(name)):
        return "Use an email address, or a user name of 3-40 letters a-z, digits, . - or _"
    if not str(pw or ""):
        return "Type a password (any password is fine)"
    d = _users()
    if name in d or name == _admin_name():
        return "That name is taken"
    d[name] = {"hash": generate_password_hash(str(pw)), "created": int(time.time()), "studio": bool(studio)}
    _save_users(d)
    return ""


def remove_user(name):
    d = _users()
    if d.pop(str(name), None) is not None:
        _save_users(d)


def _check(user, pw):
    """-> "admin" / "user" / None"""
    user = str(user).strip()
    env_pw = os.environ.get("STICKMAN_PASSWORD")
    if hmac.compare_digest(user, _admin_name()):
        ok = hmac.compare_digest(str(pw), env_pw) if env_pw else check_password_hash(DEFAULT_HASH, str(pw))
        return "admin" if ok else None
    u = _users().get(user.lower())
    if u and u.get("studio") and check_password_hash(u["hash"], str(pw)):   # (🔒 only accounts the admin let into the studio)
        return "user"
    check_password_hash(DEFAULT_HASH, "x")                      # (same time either way: no hint which names exist)
    return None


def current_user():
    """the logged-in account name ("local" when the login is off) - used for each person's own saved data"""
    if str(os.environ.get("STICKMAN_LOGIN", "on")).lower() in ("off", "0", "false", "no"):
        return "local"
    try:
        return session.get("user") or None
    except RuntimeError:
        return None


def signup_on():
    return str(os.environ.get("STICKMAN_SIGNUP", "off")).lower() in ("on", "1", "true", "yes")


def _ip():
    """The visitor's address. Behind Caddy (HTTPS) every request comes from 127.0.0.1, so then the address Caddy adds
    is used; from anywhere else X-Forwarded-For is ignored (anyone could fake it to dodge the wait)."""
    ip = request.remote_addr or "?"
    if ip in ("127.0.0.1", "::1") and request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"].split(",")[-1].strip()
    return ip


def _locked(ip):
    now = time.time()
    tries = [t for t in _FAILS.get(ip, []) if now - t < WINDOW]
    _FAILS[ip] = tries
    return len(tries) >= MAX_TRIES


def init(app):
    if str(os.environ.get("STICKMAN_LOGIN", "on")).lower() in ("off", "0", "false", "no"):
        return
    app.secret_key = _secret_key()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=timedelta(days=30))

    @app.before_request
    def _gate():
        if request.path in OPEN or (PUBLIC and request.path.startswith(PUBLIC)):
            return None
        if session.get("user") and (session.get("admin") or (_users().get(session["user"]) or {}).get("studio")):
            return None                                         # (🔒 an old game login, still in its cookie, is not let in)
        if session.get("user"):
            session.clear()
        if request.path.startswith("/api/") or request.method != "GET":
            return jsonify(ok=False, error="Please log in again.", login=True), 401
        nxt = request.full_path if request.query_string else request.path
        return redirect("/login?next=" + nxt)

    @app.route("/login", methods=["GET", "POST"])
    def _login():
        err = ""
        nxt = request.values.get("next") or "/"
        if not nxt.startswith("/") or nxt.startswith("//"):
            nxt = "/"
        if request.method == "POST":
            ip = _ip()
            if _locked(ip):
                err = "Too many wrong tries - wait 5 minutes."
            elif (role := _check(request.form.get("user", ""), request.form.get("password", ""))):
                _FAILS.pop(ip, None)
                session.clear()
                session["user"] = request.form.get("user", "").strip().lower() if role == "user" else request.form.get("user", "").strip()
                session["admin"] = role == "admin"
                session.permanent = bool(request.form.get("remember"))
                return redirect(nxt)
            else:
                _FAILS.setdefault(ip, []).append(time.time())
                time.sleep(0.6)                              # slows down guessing
                err = "Wrong email / user name or password."
        q = nxt.replace('"', "&quot;").replace("<", "&lt;")
        return LOGIN_PAGE.replace("{{TITLE}}", "Log in").replace("{{H1}}", "Welcome back").replace("{{P}}", "Log in to the studio.").replace("{{BTN}}", "Log in").replace(
            "{{SIGNUP}}", f'<div class="alt">New here? <a href="/signup?next={q}">Create an account</a></div>' if signup_on() else "").replace("{{ERR}}", f'<div class="err">{err}</div>' if err else "").replace(
            "{{NEXT}}", nxt.replace('"', "&quot;").replace("<", "&lt;")).replace(
            "{{USER}}", (request.form.get("user", "") if request.method == "POST" else "").replace('"', "&quot;").replace("<", "&lt;"))

    @app.get("/logout")
    def _logout():
        session.clear()
        return redirect("/login")

    @app.route("/signup", methods=["GET", "POST"])
    def _signup():
        if not signup_on():
            return redirect("/login")
        err = ""
        nxt = request.values.get("next") or "/"                     # (🆘 from the home page: straight into the game after)
        if not nxt.startswith("/") or nxt.startswith("//"):
            nxt = "/"
        if request.method == "POST":
            ip = _ip()
            if _locked(ip):
                err = "Too many tries - wait 5 minutes."
            else:
                _FAILS.setdefault(ip, []).append(time.time())     # (each sign-up counts: no account flooding)
                err = add_user(request.form.get("user", ""), request.form.get("password", ""), studio=True)
                if not err:
                    session.clear()
                    session["user"] = request.form.get("user", "").strip().lower()
                    session.permanent = True
                    return redirect(nxt)
        q = nxt.replace('"', "&quot;").replace("<", "&lt;")
        page = LOGIN_PAGE.replace("{{TITLE}}", "Sign up").replace("{{H1}}", "Create your account").replace(
            "{{P}}", "An account for the studio.").replace("{{BTN}}", "Create").replace(
            "{{SIGNUP}}", f'<div class="alt">Already have an account? <a href="/login?next={q}">Log in</a></div>').replace(
            'action="/login"', 'action="/signup"').replace('autocomplete="current-password"', 'autocomplete="new-password"')
        return page.replace("{{ERR}}", f'<div class="err">{err}</div>' if err else "").replace("{{NEXT}}", q).replace("{{USER}}", "")

    @app.route("/admin/users", methods=["GET", "POST"])
    def _admin_users():
        if not session.get("admin"):
            return redirect("/login")
        msg = ""
        if request.method == "POST":
            act = request.form.get("act")
            if act == "add":
                msg = add_user(request.form.get("user", ""), request.form.get("password", ""), studio=True) or "Added."
            elif act == "let":
                d = _users()
                if request.form.get("user", "") in d:
                    d[request.form.get("user", "")]["studio"] = not d[request.form.get("user", "")].get("studio")
                    _save_users(d)
                msg = "Changed."
            elif act == "remove":
                remove_user(request.form.get("user", ""))
                msg = "Removed (their saved walk data stays until you delete users/<name>/)."
        rows = "".join(f"<tr><td>{n}</td><td>{time.strftime('%Y-%m-%d', time.localtime(u.get('created', 0)))}</td><td>"
                       f"<form method=post style='margin:0;display:inline'><input type=hidden name=act value=let><input type=hidden name=user value='{n}'><button>{'🔓 studio' if u.get('studio') else '🔒 no studio'}</button></form> "
                       f"<form method=post style='margin:0;display:inline'><input type=hidden name=act value=remove><input type=hidden name=user value='{n}'><button>remove</button></form></td></tr>"
                       for n, u in sorted(_users().items()))
        return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Accounts</title>"
                f"<body style='font:15px system-ui;max-width:640px;margin:20px auto;padding:0 16px'><h2>👥 Accounts</h2><p>{msg}</p>"
                f"<table style='width:100%'><tr><th align=left>name</th><th align=left>made</th><th></th></tr>{rows}</table><h3>Add one</h3>"
                f"<form method=post><input type=hidden name=act value=add><input name=user placeholder='email or user name' required> "
                f"<input name=password type=password placeholder='password' required> <button>Add</button></form>"
                f"<p style='color:#666'>Sign-up for everyone is {'ON' if signup_on() else 'off'} (STICKMAN_SIGNUP).</p></body>")


# when a page stays open and the login runs out, the next action goes to the login page instead of failing
RELOGIN_JS = """<script>(()=>{const f=window.fetch;window.fetch=async function(){const r=await f.apply(this,arguments);
if(r.status===401){try{const j=await r.clone().json();if(j&&j.login){location.href='/login?next='+encodeURIComponent(location.pathname+location.search);}}catch(e){}}
return r;};})();</script>"""

LOGIN_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#000000"><title>Planet Explorer · {{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800;900&display=swap" rel="stylesheet">
<style>
/* the same clean look as the home page: black, one font (Inter), one red button */
:root{--red:#e50914;--t:#fff;--m:#a3a3a3;--line:rgba(255,255,255,.14);--bad:#f87171}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px 20px;background:radial-gradient(900px 500px at 70% 10%,rgba(229,9,20,.12),transparent),#000;color:var(--t);
 font:16px/1.5 Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.box{width:100%;max-width:400px}
.brand{display:block;font:900 20px Inter,sans-serif;letter-spacing:-.02em;color:var(--red);text-transform:uppercase;text-decoration:none;margin-bottom:40px}
h1{font:900 clamp(32px,9vw,40px)/1.05 Inter,sans-serif;letter-spacing:-.035em;margin:0 0 10px}p{margin:0 0 28px;color:var(--m);font-size:16px}
label{display:block;font-size:13px;font-weight:600;color:var(--m);margin-bottom:16px}
input[type=text],input[type=password]{display:block;width:100%;margin-top:6px;font:inherit;font-size:16px;color:var(--t);background:#141414;
 border:1px solid var(--line);border-radius:6px;padding:13px 14px;min-height:50px}
input:focus{outline:none;border-color:#fff}
.chk{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:500;color:var(--m)}
.chk input{width:17px;height:17px;accent-color:var(--red);margin:0}
button{width:100%;min-height:52px;margin-top:8px;border:0;border-radius:6px;background:var(--red);color:#fff;font:700 17px Inter,sans-serif;cursor:pointer}
button:hover{background:#f6121d}
.err{background:rgba(248,113,113,.12);color:var(--bad);border-radius:6px;padding:11px 13px;font-size:14px;margin-bottom:16px}
.pw{position:relative}.pw button{position:absolute;right:6px;bottom:7px;width:auto;min-height:36px;margin:0;padding:0 12px;background:transparent;color:var(--m);font-size:14px;font-weight:600}
.alt{margin:22px 0 0;text-align:center;color:var(--m);font-size:15px}.alt a{color:var(--t);font-weight:600}
.fine{margin-top:26px;text-align:center;color:#737373;font-size:12.5px}
</style></head><body>
<form class="box" method="post" action="/login" autocomplete="on">
 <a class="brand" href="/">Planet Explorer</a>
 <h1>{{H1}}</h1><p>{{P}}</p>
 {{ERR}}
 <input type="hidden" name="next" value="{{NEXT}}">
 <label>Email or user name<input type="text" name="user" value="{{USER}}" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" required autofocus></label>
 <label class="pw">Password<input type="password" name="password" id="pw" autocomplete="current-password" required>
  <button type="button" onclick="const p=document.getElementById('pw');p.type=p.type==='password'?'text':'password';this.textContent=p.type==='password'?'Show':'Hide'">Show</button></label>
 <label class="chk"><input type="checkbox" name="remember" checked> Keep me logged in (30 days)</label>
 <button type="submit">{{BTN}}</button>
 {{SIGNUP}}
 <div class="fine">Free to play. We never show your email to other players.</div>
</form></body></html>"""
