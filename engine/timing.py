"""Timing history + estimates ("how long will this take?").

Every run records how long each step took in cache/timings.json; later runs use the
median of the recent history to predict durations. With no history we fall back to
sensible defaults or a quick benchmark.
"""
import json
import os
import statistics
import sys
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "cache", "timings.json")
_LOCK = threading.Lock()

DEFAULTS = {                     # used until we have real measurements
    "gemini": 40.0,              # seconds per story (flash models ~20-60s, pro ~60-180s)
    "gemini_pro": 110.0,
    "gemini_repair": 25.0,
    "tts_line:edge": 1.2,        # seconds per voice line (sequential)
    "tts_line:espeak": 0.15,
    "tts_line:pyttsx3": 0.6,
}


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def record(key, value):
    with _LOCK:
        d = _load()
        d.setdefault(key, []).append(round(float(value), 4))
        d[key] = d[key][-12:]
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, PATH)


def estimate(key, default=None):
    vals = _load().get(key)
    if vals:
        return statistics.median(vals[-6:])
    if default is not None:
        return default
    return DEFAULTS.get(key)


def gemini_estimate(model):
    d = DEFAULTS["gemini_pro"] if "pro" in model else DEFAULTS["gemini"]
    return estimate(f"gemini:{model}", d)


def fmt(sec):
    sec = max(0, int(round(sec)))
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


class Ticker:
    """Calls tick(elapsed_seconds) every second while a slow blocking call runs."""

    def __init__(self, tick, every=1.0):
        self.tick, self.every = tick, every
        self._stop = threading.Event()
        self.t0 = time.time()

    def __enter__(self):
        self.t0 = time.time()
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()
        return self

    def _run(self):
        while not self._stop.wait(self.every):
            try:
                self.tick(time.time() - self.t0)
            except Exception:
                pass

    def __exit__(self, *exc):
        self._stop.set()
        self._th.join(timeout=2)
        self.elapsed = time.time() - self.t0
        return False


def console_tick(label, expected):
    def tick(el):
        if expected:
            left = expected - el
            eta = f"~{fmt(left)} left" if left > 1 else "taking a bit longer than usual..."
            msg = f"\r  {label}... {fmt(el)} elapsed (usually ~{fmt(expected)}, {eta})      "
        else:
            msg = f"\r  {label}... {fmt(el)} elapsed      "
        sys.stdout.write(msg)
        sys.stdout.flush()
    return tick


class StepTimer:
    """Collects per-step durations for the final summary."""

    def __init__(self):
        self.steps = []
        self.t0 = time.time()
        self._s = None

    def start(self, name):
        self.stop()
        self._s = (name, time.time())

    def stop(self):
        if self._s:
            self.steps.append((self._s[0], time.time() - self._s[1]))
            self._s = None

    def summary(self):
        self.stop()
        total = time.time() - self.t0
        parts = "  ".join(f"{n} {fmt(s)}" for n, s in self.steps)
        return f"Time: {parts}  | total {fmt(total)}"
