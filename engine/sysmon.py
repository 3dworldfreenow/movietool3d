"""System monitor + resource limit ("Maximum system usage").

    sample()          latest {cpu, ram, ram_used_gb, ram_total_gb, gpu, gpu_temp, temp, cores, time}
    get_limit()       the limit in % (10..100), saved in output/.limits.json - read by every render
    set_limit(p)      change it; the governor and the renderer pick it up at once (no restart)
    Governor          keeps the whole machine under the limit while a render runs: it pauses and resumes the
                      render processes many times a second (like a dimmer), and slows down more when the CPU
                      is hot. Needs psutil (pip install psutil); without it only the worker count follows the limit.

Works without psutil on Linux (/proc) with fewer details. GPU numbers come from nvidia-smi when it exists.
"""
import json
import os
import shutil
import subprocess
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT_FILE = os.path.join(HERE, "output", ".limits.json")
HOT_C = 85.0                       # above this the renders slow down by themselves

try:
    import psutil
except Exception:                  # noqa: BLE001
    psutil = None

_LATEST = {"cpu": None, "ram": None, "ram_used_gb": None, "ram_total_gb": None, "gpu": None, "gpu_temp": None,
           "temp": None, "cores": os.cpu_count() or 1, "time": 0.0}
_HIST = []
_LOCK = threading.Lock()
_STARTED = [False]


# ---------------------------------------------------------------------------- the limit
def get_limit():
    try:
        with open(LIMIT_FILE) as f:
            v = float(json.load(f).get("max_usage", 100))
        return max(10.0, min(100.0, v))
    except (OSError, ValueError, TypeError):
        return 100.0


def set_limit(p):
    p = max(10.0, min(100.0, float(p)))
    os.makedirs(os.path.dirname(LIMIT_FILE), exist_ok=True)
    tmp = LIMIT_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"max_usage": p}, f)
    os.replace(tmp, LIMIT_FILE)
    return p


def workers_for_limit(default_workers):
    """Worker processes for the next render part: about limit% of the cores, fewer while the RAM is over."""
    lim = get_limit()
    cores = os.cpu_count() or 1
    w = max(1, int(round(cores * lim / 100.0)))
    w = min(w, max(1, default_workers))
    ram = _ram_percent()
    if ram is not None and ram > lim:
        w = max(1, w // 2)
    return w


# ---------------------------------------------------------------------------- readings
_PREV_CPU = [None]


def _cpu_percent():
    if psutil is not None:
        return psutil.cpu_percent(interval=None)
    try:                                                  # Linux without psutil
        with open("/proc/stat") as f:
            v = [float(x) for x in f.readline().split()[1:]]
        idle, total = v[3] + (v[4] if len(v) > 4 else 0.0), sum(v)
        prev = _PREV_CPU[0]
        _PREV_CPU[0] = (idle, total)
        if prev is None or total <= prev[1]:
            return None
        return 100.0 * (1.0 - (idle - prev[0]) / (total - prev[1]))
    except (OSError, ValueError):
        return None


def _ram():
    if psutil is not None:
        m = psutil.virtual_memory()
        return m.percent, (m.total - m.available) / 1e9, m.total / 1e9
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = float(v.split()[0]) * 1024
        tot, av = info["MemTotal"], info.get("MemAvailable", info.get("MemFree", 0.0))
        return 100.0 * (1 - av / tot), (tot - av) / 1e9, tot / 1e9
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        return None, None, None


def _ram_percent():
    return _ram()[0]


def ram_percent():
    """% of the RAM in use now (None when it can't be read)"""
    return _ram()[0]


def ram_available_gb():
    """RAM still free for new work, in GB (None when unknown)"""
    p, used, tot = _ram()
    if tot is None:
        return None
    return max(0.0, tot - used)


def rss_gb(pid=None, children=False):
    """RAM held by a process (and its child processes) in GB, or None without psutil"""
    if psutil is None:
        return None
    try:
        pr = psutil.Process(pid or os.getpid())
        tot = pr.memory_info().rss
        if children:
            for c in pr.children(recursive=True):
                try:
                    tot += c.memory_info().rss
                except Exception:                        # noqa: BLE001 - it just ended
                    pass
        return tot / 1e9
    except Exception:                                    # noqa: BLE001
        return None


def child_rss_gb(pid=None):
    """[RAM of each child process] in GB (the render workers, FFmpeg)"""
    if psutil is None:
        return []
    out = []
    try:
        for c in psutil.Process(pid or os.getpid()).children(recursive=True):
            try:
                out.append((c.name(), c.memory_info().rss / 1e9))
            except Exception:                            # noqa: BLE001
                pass
    except Exception:                                    # noqa: BLE001
        pass
    return out


def _temp():
    """Hottest CPU sensor in °C, or None (many virtual servers have no sensor)."""
    best = None
    if psutil is not None and hasattr(psutil, "sensors_temperatures"):
        try:
            for name, arr in (psutil.sensors_temperatures() or {}).items():
                for s in arr:
                    if s.current and 5 < s.current < 130 and (best is None or s.current > best):
                        best = s.current
        except Exception:                                  # noqa: BLE001
            pass
    if best is None:
        try:
            for z in os.listdir("/sys/class/thermal"):
                if not z.startswith("thermal_zone"):
                    continue
                with open(f"/sys/class/thermal/{z}/temp") as f:
                    c = float(f.read().strip()) / 1000.0
                if 5 < c < 130 and (best is None or c > best):
                    best = c
        except (OSError, ValueError):
            pass
    return best


_NV = [shutil.which("nvidia-smi"), 0.0, (None, None)]


def _gpu():
    """(GPU load %, GPU °C) from nvidia-smi, at most every 3 s; (None, None) without an NVIDIA card."""
    if not _NV[0]:
        return None, None
    if time.time() - _NV[1] < 3.0:
        return _NV[2]
    _NV[1] = time.time()
    try:
        r = subprocess.run([_NV[0], "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=3)
        vals = [ln.split(",") for ln in r.stdout.strip().splitlines() if ln.strip()]
        if vals:
            load = max(float(v[0]) for v in vals)
            temp = max(float(v[1]) for v in vals)
            _NV[2] = (load, temp)
    except (OSError, ValueError, subprocess.SubprocessError):
        _NV[2] = (None, None)
    return _NV[2]


def _read():
    ram, used, tot = _ram()
    gpu, gpu_t = _gpu()
    cpu = _cpu_percent()
    return {"cpu": None if cpu is None else round(cpu, 1), "ram": None if ram is None else round(ram, 1),
            "ram_used_gb": None if used is None else round(used, 1), "ram_total_gb": None if tot is None else round(tot, 1),
            "gpu": gpu, "gpu_temp": gpu_t, "temp": _temp(), "cores": os.cpu_count() or 1, "time": time.time()}


def _loop():
    _cpu_percent()
    while True:
        time.sleep(1.0)
        s = _read()
        with _LOCK:
            _LATEST.update(s)
            _HIST.append((s["time"], s["cpu"], s["ram"], s["temp"]))
            del _HIST[:-120]


def start():
    """Start sampling once per second (idempotent)."""
    if _STARTED[0]:
        return
    _STARTED[0] = True
    threading.Thread(target=_loop, daemon=True, name="sysmon").start()


def sample():
    with _LOCK:
        d = dict(_LATEST)
        d["history"] = [list(h) for h in _HIST[-60:]]
    d["limit"] = get_limit()
    d["psutil"] = psutil is not None
    d["hot"] = HOT_C
    return d


# ---------------------------------------------------------------------------- the governor
def _tree(pid):
    """pid + all its children (render workers, ffmpeg)."""
    if psutil is None:
        return []
    try:
        p = psutil.Process(pid)
        return [p] + p.children(recursive=True)
    except psutil.Error:
        return []


class Governor:
    """Keeps the machine under the limit while jobs run: in every 0.4 s window the job's processes run for
    `duty` of it and pause for the rest. `duty` follows the measured CPU (and the temperature)."""
    PERIOD = 0.4

    def __init__(self):
        self.pids = set()
        self.duty = 1.0
        self.paused_by_us = False
        self.status = "idle"
        self._lock = threading.Lock()
        self._t = None

    def watch(self, pid):
        with self._lock:
            self.pids.add(pid)
        self._ensure()

    def unwatch(self, pid):
        with self._lock:
            self.pids.discard(pid)

    def _ensure(self):
        if self._t is None and psutil is not None:
            self._t = threading.Thread(target=self._run, daemon=True, name="governor")
            self._t.start()

    def _procs(self):
        with self._lock:
            pids = list(self.pids)
        out = []
        for pid in pids:
            t = _tree(pid)
            if not t:
                self.unwatch(pid)
            out += t
        return out

    @staticmethod
    def _each(procs, fn):
        for p in procs:
            try:
                getattr(p, fn)()
            except psutil.Error:
                pass

    def _run(self):
        psutil.cpu_percent(interval=None)
        cached, cached_t = [], 0.0
        while True:
            if time.time() - cached_t > 1.0:
                cached, cached_t = self._procs(), time.time()
            if not cached:
                self.duty, self.status = 1.0, "idle"
                time.sleep(0.5)
                continue
            lim = get_limit()
            if lim >= 99.5:
                self.duty, self.status = 1.0, "full speed"
                self._each(cached, "resume")
                time.sleep(0.5)
                psutil.cpu_percent(interval=None)
                continue
            on = self.PERIOD * self.duty
            self._each(cached, "resume")
            time.sleep(on)
            if self.duty < 0.999:
                self._each(cached, "suspend")
                time.sleep(self.PERIOD - on)
            cpu = psutil.cpu_percent(interval=None)            # the whole machine over this window
            temp = _LATEST.get("temp")
            target = lim
            if temp is not None and temp > HOT_C:
                target = min(target, lim * 0.6)                 # too hot: slow down more
            err = (target - cpu) / 100.0
            self.duty = max(0.08, min(1.0, self.duty + 0.6 * err))
            self.status = f"limited to {lim:.0f}%" + (" (hot)" if target < lim else "")

    def release_all(self):
        """Make sure nothing stays paused (a stop / a finished job)."""
        if psutil is None:
            return
        self._each(self._procs(), "resume")


GOV = Governor()


def kill_tree(pid):
    """Stop a job: its process and every child (workers, ffmpeg)."""
    if psutil is not None:
        procs = _tree(pid)
        for p in procs:
            try:
                p.resume()
            except psutil.Error:
                pass
        for p in reversed(procs):
            try:
                p.kill()
            except psutil.Error:
                pass
        return
    import signal
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (OSError, AttributeError):
        try:
            os.kill(pid, 9)
        except OSError:
            pass
