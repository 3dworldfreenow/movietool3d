"""🔊 A starter pack of real recordings (all CC0: free, no credit needed) from GitHub, saved under the studio's
sound names in assets/sfx - the same as uploading them in the Sounds panel.

    python tools/get_sound_pack.py            # what isn't there yet (a sound you uploaded is never replaced)
    python tools/get_sound_pack.py --list     # the pack and what is there
    python tools/get_sound_pack.py --force    # replace too

Where they come from (each one CC0 in its source's own credits):
  rain, rain_2 (a storm with thunder), wind, murmur (a café full of people), jet (inside an airliner)
      github.com/mateusfg7/Noisekun - recordings by SFX Producer, Borys Kozielski (storm), Felix Blume (wind)
  thunder
      github.com/lavenderdotpet/CC0-Public-Domain-Sounds (100 CC0 SFX vol. 2)
Not in any CC0 collection on GitHub yet (get them from freesound.org with the CC0 filter or pixabay.com/sound-effects
and upload them in the Sounds panel): siren, rotor (helicopter), panic / scream, whispers, engine, car_door.
"""
import argparse
import os
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import sfx, sfxlib  # noqa: E402

NK = "https://raw.githubusercontent.com/mateusfg7/Noisekun/main/.github/assets/sounds/"
LV = "https://raw.githubusercontent.com/lavenderdotpet/CC0-Public-Domain-Sounds/main/"
PACK = [   # (file name in assets/sfx, url, what it is)
    ("rain.ogg", NK + "rain.ogg", "steady rain, 81 s (SFX Producer, CC0)"),
    ("rain_2.ogg", NK + "storm.ogg", "a rainstorm with thunder, 187 s (Borys Kozielski, CC0)"),
    ("wind.ogg", NK + "wind.ogg", "wind, 93 s (Felix Blume, CC0)"),
    ("thunder.ogg", LV + "100-cc0-sfx-2/sfx100v2_thunder_01.ogg", "a thunder clap, 5 s (CC0)"),
    ("murmur.ogg", NK + "coffee.ogg", "a room full of people talking, 115 s (SFX Producer, CC0)"),
    ("jet.ogg", NK + "air-plane.ogg", "inside an airliner, 60 s (SFX Producer, CC0)"),
]


def _have(fname, folder):
    base = os.path.splitext(fname)[0]
    return any(os.path.splitext(f)[0] == base for f in os.listdir(folder)) if os.path.isdir(folder) else False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--force", action="store_true", help="replace a sound that is already there")
    ap.add_argument("--dir", help="save somewhere else (a test)")
    a = ap.parse_args()
    folder = a.dir or sfx.REAL_DIR
    if a.list:
        for f, _u, what in PACK:
            print(("✔ " if _have(f, folder) else "○ ") + f"{os.path.splitext(f)[0]:8s} {what}")
        return
    os.makedirs(folder, exist_ok=True)
    for f, url, what in PACK:
        if _have(f, folder) and not a.force:
            print(f"- {f}: already there (kept)")
            continue
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                data = r.read()
            fd, tmp = tempfile.mkstemp(suffix=".ogg")
            with os.fdopen(fd, "wb") as out:
                out.write(data)
            got = sfxlib.check(tmp)                                    # (the engine can read it, not silent)
            if "silent - nothing to hear" in got["warn"]:
                raise ValueError("silent")
            with open(os.path.join(folder, f), "wb") as out:
                out.write(data)
            os.remove(tmp)
            print(f"✔ {f}: {what} - {got['dur']} s")
        except Exception as ex:
            print(f"⚠ {f}: {ex}")
    sfx._REAL.clear()


if __name__ == "__main__":
    main()
