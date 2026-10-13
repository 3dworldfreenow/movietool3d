"""Recorded voices for a story: one long recording of a character's lines (an actor, ElevenLabs) is matched to
the lines of the story, so each spoken line plays its own part of the file.

How the cut is found (no markers needed in the text): every pause in the recording is a place a line could end;
a line takes about as long to say as it is long (syllables, plus a beat for each comma or full stop), so of all
the ways to cut the file into as many pieces as there are lines, the one whose piece lengths best fit the lines
wins. Each line then gets {"voice_file", "from", "to"} (seconds) - change the numbers by hand to nudge a cut.

    python main.py voicescript story.json --who deepak        the lines to paste into ElevenLabs
    python main.py voices story.json take.mp3 --who deepak    match a recording to the lines (--dry: only show)
"""
import json
import math
import os
import re
import shutil

import numpy as np

from .audio import decode_audio, SR


def lines_of(story, who):
    """[(scene index, event index, text)] of everything `who` says, in story order"""
    out = []
    for si, sc in enumerate(story.get("scenes") or []):
        for ei, e in enumerate(sc.get("events") or []):
            if isinstance(e, dict) and e.get("who") == who and isinstance(e.get("say"), str) and e["say"].strip():
                out.append((si, ei, e["say"].strip()))
    return out


def script(story, who):
    """the text for a voice service: one line each, in order"""
    return "\n".join(t for _, _, t in lines_of(story, who))


def _units(text):
    """how long a line takes to say, in rough syllables (a vowel group each) + beats for the pauses in it"""
    syl = len(re.findall(r"[aeiouy]+", text.lower())) or 1
    beats = 2.0 * (text.count(",") + text.count("?") + text.count("!")) + 2.5 * text.count(".")
    return syl + beats


def pauses(audio, sr=SR, floor_db=-35.0, min_len=0.22):
    """[(start, end)] seconds of the quiet stretches (below floor_db of the loudest 20 ms)"""
    win = int(0.02 * sr)
    n = len(audio) // win
    if n == 0:
        return [], 0.0, 0.0
    rms = np.sqrt(np.mean(audio[:n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    loud = rms > rms.max() * 10 ** (floor_db / 20.0)
    idx = np.nonzero(loud)[0]
    first, last = idx[0] * 0.02, (idx[-1] + 1) * 0.02          # where the speech starts and ends
    out, run = [], None
    for k in range(idx[0], idx[-1] + 1):
        if not loud[k]:
            run = k if run is None else run
        elif run is not None:
            if (k - run) * 0.02 >= min_len:
                out.append((run * 0.02, k * 0.02))
            run = None
    return out, first, last


def match(audio, texts, sr=SR):
    """cut the recording into len(texts) pieces at its pauses, best fitting each line's length:
    [(from, to, fit)] where fit = piece length / expected length (1.0 is perfect)"""
    gaps, first, last = pauses(audio, sr)
    n = len(texts)
    if n == 0:
        return []
    if len(gaps) < n - 1:
        raise ValueError(f"the recording has {len(gaps) + 1} parts but there are {n} lines")
    u = [_units(t) for t in texts]
    rate = (last - first) / sum(u)                                  # seconds per unit, from the whole take
    starts = [first] + [g[1] for g in gaps]                         # a piece starts after a pause ...
    ends = [g[0] for g in gaps] + [last]                            # ... and ends where the next one begins
    m = len(gaps) + 1
    INF = float("inf")
    best = [[INF] * (m + 1) for _ in range(n + 1)]                  # best[i][j]: lines 0..i-1 use pieces 0..j-1
    back = [[0] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(1, n + 1):
        for j in range(i, m - (n - i) + 1):
            for k in range(i - 1, j):
                if best[i - 1][k] == INF:
                    continue
                d = ends[j - 1] - starts[k]
                c = best[i - 1][k] + math.log(max(d, 0.05) / (u[i - 1] * rate)) ** 2
                if c < best[i][j]:
                    best[i][j], back[i][j] = c, k
    cuts, j = [], m
    for i in range(n, 0, -1):
        k = back[i][j]
        cuts.append((k, j))
        j = k
    cuts.reverse()
    out = []
    for i, (k, j) in enumerate(cuts):
        a, b = max(0.0, starts[k] - 0.06), min(len(audio) / sr, ends[j - 1] + 0.12)   # a breath of room each side
        out.append((round(a, 2), round(b, 2), round((ends[j - 1] - starts[k]) / (u[i] * rate), 2)))
    return out


def characters_with_lines(story):
    """the characters who speak, with how many lines each"""
    out = {}
    for sc in story.get("scenes") or []:
        for e in sc.get("events") or []:
            if isinstance(e, dict) and e.get("who") and isinstance(e.get("say"), str) and e["say"].strip():
                out[e["who"]] = out.get(e["who"], 0) + 1
    return out


def attach(story, recording, who, ref):
    """match `recording` to `who`'s lines in the story dict, writing voice_file=ref / from / to on each line;
    -> rows [{text, from, to, fit, check}]"""
    lines = lines_of(story, who)
    if not lines:
        raise ValueError(f"'{who}' has no lines in this story")
    cuts = match(decode_audio(recording), [t for _, _, t in lines])
    rows = []
    for (si, ei, text), (a, b, fit) in zip(lines, cuts):
        story["scenes"][si]["events"][ei].update({"voice_file": ref, "from": a, "to": b})
        rows.append({"text": text, "from": a, "to": b, "fit": fit, "check": not 0.6 <= fit <= 1.6})
    return rows


def apply(story_path, recording, who, dry=False, log=print):
    """match `recording` to `who`'s lines in the story and write voice_file / from / to into it"""
    with open(story_path, "r", encoding="utf-8") as f:
        story = json.load(f)
    lines = lines_of(story, who)
    if not lines:
        raise ValueError(f"'{who}' has no lines in this story")
    audio = decode_audio(recording)
    cuts = match(audio, [t for _, _, t in lines])
    base = os.path.dirname(os.path.abspath(story_path))
    name = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(os.path.basename(recording))[0].lower())[:40].strip("_")
    name = name if name.startswith(who) else f"{who}_{name}"
    rel = os.path.join("voices", f"{name}{os.path.splitext(recording)[1].lower()}")
    for (si, ei, text), (a, b, fit) in zip(lines, cuts):
        flag = "" if 0.6 <= fit <= 1.6 else "   <- check this one"
        log(f"  {a:6.2f} - {b:6.2f}  ({b - a:4.1f} s, fit {fit:4.2f})  {text[:60]}{flag}")
        if not dry:
            e = story["scenes"][si]["events"][ei]
            e.update({"voice_file": rel.replace(os.sep, "/"), "from": a, "to": b})
    if dry:
        return cuts
    os.makedirs(os.path.join(base, "voices"), exist_ok=True)
    dst = os.path.join(base, rel)
    if os.path.abspath(recording) != os.path.abspath(dst):
        shutil.copyfile(recording, dst)
    with open(story_path, "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=1)
    log(f"{len(lines)} lines of {who} now use {rel}")
    return cuts
