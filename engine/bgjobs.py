"""🕒 Background renders: full renders that run on their own while you keep working - a queue of jobs, one rendering
at a time, each with Pause / Resume / Cancel. The list is saved on disk (output/bgjobs/jobs.json), so a server
restart loses nothing: what was rendering or waiting carries on by itself, what you paused stays paused.

A render is made in parts (main.py render --part): every finished part is kept, so Pause (or a restart) only loses
the part that was being made - Resume runs the same command again and it goes on from there."""
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = [os.path.join(HERE, "output", "bgjobs")]          # (a list: tests point it at a temporary folder)
STATES = ("queued", "running", "paused", "done", "failed", "cancelled")


class Queue:
    """the background jobs; one thread runs them one by one"""

    def __init__(self, busy=lambda: False, log=print):
        self.lock = threading.Lock()
        self.jobs = []
        self.proc = None
        self.cur = None
        self.busy = busy                               # a render started from the page is running: wait for it
        self.log = log
        self.wake = threading.Event()
        self.thread = None
        self._saved = 0.0
        self._load()

    # ---------------------------------------------------------------- saved list
    def _file(self):
        return os.path.join(DIR[0], "jobs.json")

    def _load(self):
        try:
            with open(self._file(), encoding="utf-8") as f:
                self.jobs = json.load(f).get("jobs", [])
        except (OSError, ValueError):
            self.jobs = []
        for j in self.jobs:                            # the server stopped while this rendered: it goes on
            if j.get("state") == "running":
                _kill_orphan(j.get("pid"))
                j["state"] = "queued"
                j["stage"] = "carrying on after a restart (finished parts are kept)"
                j["pid"] = None
        self._save(force=True)

    def _save(self, force=False):
        now = time.time()
        if not force and now - self._saved < 2.0:
            return
        self._saved = now
        os.makedirs(DIR[0], exist_ok=True)
        tmp = self._file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"jobs": self.jobs}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self._file())

    # ---------------------------------------------------------------- what the page can do
    def add(self, cmd, output, label, name=""):
        j = dict(id=uuid.uuid4().hex[:10], name=name, label=label, cmd=list(cmd), output=output,
                 file=os.path.basename(output), state="queued", progress=0.0, stage="waiting for its turn",
                 created=time.time(), updated=time.time(), log=[], pid=None)
        with self.lock:
            self.jobs.append(j)
            self._save(force=True)
        self.wake.set()
        return j["id"]

    def list(self):
        with self.lock:
            out = []
            for j in self.jobs:
                d = {k: v for k, v in j.items() if k != "cmd"}
                d["log"] = j.get("log", [])[-8:]
                out.append(d)
        return out

    def _get(self, jid):
        return next((j for j in self.jobs if j["id"] == jid), None)

    def pause(self, jid):
        with self.lock:
            j = self._get(jid)
            if j is None or j["state"] not in ("queued", "running"):
                return False
            was = j["state"]
            j["state"], j["stage"] = "paused", "paused - finished parts are kept; Resume goes on from them"
            self._save(force=True)
        if was == "running":
            self._stop_proc()
        return True

    def resume(self, jid):
        with self.lock:
            j = self._get(jid)
            if j is None or j["state"] not in ("paused", "failed"):
                return False
            j["state"], j["stage"] = "queued", "waiting for its turn"
            self._save(force=True)
        self.wake.set()
        return True

    def cancel(self, jid):
        with self.lock:
            j = self._get(jid)
            if j is None or j["state"] in ("done", "cancelled"):
                return False
            was = j["state"]
            j["state"], j["stage"] = "cancelled", "cancelled"
            self._save(force=True)
        if was == "running":
            self._stop_proc()
        return True

    def remove(self, jid):
        """take a finished / cancelled job off the list (its video stays in the videos)"""
        with self.lock:
            j = self._get(jid)
            if j is None or j["state"] in ("queued", "running"):
                return False
            self.jobs.remove(j)
            self._save(force=True)
        return True

    def running(self):
        with self.lock:
            return any(j["state"] == "running" for j in self.jobs)

    # ---------------------------------------------------------------- the worker
    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
        return self

    def _stop_proc(self):
        p = self.proc
        if p is not None and p.poll() is None:
            from . import sysmon
            sysmon.kill_tree(p.pid)

    def _next(self):
        with self.lock:
            return next((j for j in self.jobs if j["state"] == "queued"), None)

    def _loop(self):
        while True:
            j = self._next()
            if j is None or self.busy():
                self.wake.wait(3.0)
                self.wake.clear()
                continue
            self._run(j)

    def _run(self, j):
        with self.lock:
            j["state"], j["stage"], j["updated"] = "running", "starting", time.time()
            self._save(force=True)
        try:
            proc = subprocess.Popen(j["cmd"], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    bufsize=1, start_new_session=True)
        except OSError as ex:
            with self.lock:
                j["state"], j["stage"] = "failed", f"could not start: {ex}"
                self._save(force=True)
            return
        self.proc = proc
        with self.lock:
            j["pid"] = proc.pid
            self._save(force=True)
        buf = ""
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
            with self.lock:
                if m:
                    j["progress"] = int(m.group(1)) / max(1, int(m.group(2)))
                    j["stage"] = line
                else:
                    j["log"] = (j.get("log", []) + [line])[-40:]
                    if line.startswith("[") or "part" in line.lower():
                        j["stage"] = line
                j["updated"] = time.time()
                self._save()
        rc = proc.wait()
        self.proc = None
        with self.lock:
            j["pid"] = None
            if j["state"] == "running":                # (paused / cancelled while it ran: keep that)
                ok = rc == 0 and os.path.exists(j["output"])
                j["state"] = "done" if ok else "failed"
                j["progress"] = 1.0 if ok else j["progress"]
                j["stage"] = "done ✔" if ok else f"failed (code {rc}) - see the log; Resume tries again"
            j["updated"] = time.time()
            self._save(force=True)


def _kill_orphan(pid):
    """a render left from before a restart would fight the resumed one over the same parts"""
    if not pid:
        return
    try:
        with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
            cmd = f.read().decode(errors="replace")
    except (OSError, ValueError):
        return
    if "main.py" in cmd and "render" in cmd:
        from . import sysmon
        sysmon.kill_tree(int(pid))


_Q = [None]


def queue(busy=None):
    """the one queue of this server (made on first use, its worker started)"""
    if _Q[0] is None:
        _Q[0] = Queue(busy=busy or (lambda: False)).start()
    return _Q[0]
