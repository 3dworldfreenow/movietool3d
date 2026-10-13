"""🗣 Download the Piper voices (the local, offline voice engine) into assets/voices/piper/.

    pip install piper-tts
    python tools/get_piper_voices.py            # the voices the studio uses: English, Hindi, 900+ English speakers in
                                                # one file, Indian-English speakers (~60-130 MB a file, ~0.7 GB)
    python tools/get_piper_voices.py --list     # what is there

Each voice comes from the Piper voice library on Hugging Face (rhasspy/piper-voices); when that cannot be reached
the English ones come from Piper's GitHub release (older "low"/"medium" files of the same speakers). The files stay
out of git (.gitignore).
"""
import argparse
import io
import os
import sys
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.tts import PIPER_DIR, PIPER_VOICES, PIPER_MULTI, PIPER_INDIAN  # noqa: E402

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang}/{loc}/{spk}/{q}/{name}{ext}"
GH = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-{key}.tar.gz"
GH_KEYS = {"en_US-ryan-medium": "en-us-ryan-medium", "en_US-lessac-medium": "en-us-lessac-medium",
           "en_US-amy-medium": "en-us-amy-low", "en_GB-alan-medium": "en-gb-alan-low",
           "en_US-libritts-high": "en-us-libritts-high"}
ALT = {"en_US-libritts_r-medium": "en_US-libritts-high"}      # (when Hugging Face is out of reach)


def _get(url, timeout=120):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def fetch(name):
    """one voice -> assets/voices/piper/<name>.onnx + .onnx.json; returns where it came from"""
    out = os.path.join(PIPER_DIR, name + ".onnx")
    if os.path.exists(out) and os.path.exists(out + ".json"):
        return "already there"
    loc, spk, q = name.split("-")
    try:
        parts = {ext: _get(HF.format(lang=loc.split("_")[0], loc=loc, spk=spk, q=q, name=name, ext=ext))
                 for ext in (".onnx.json", ".onnx")}
        src = "Hugging Face"
    except Exception as ex:
        if name in ALT:
            return fetch(ALT[name]) + f" (as {ALT[name]})"
        if name not in GH_KEYS:
            raise RuntimeError(f"cannot reach Hugging Face ({ex}) and there is no GitHub copy of {name}")
        data = _get(GH.format(key=GH_KEYS[name]), timeout=600)
        parts = {}
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            for m in tf.getmembers():
                if m.name.endswith(".onnx"):
                    parts[".onnx"] = tf.extractfile(m).read()
                elif m.name.endswith(".onnx.json"):
                    parts[".onnx.json"] = tf.extractfile(m).read()
        src = "GitHub (" + GH_KEYS[name] + ")"
    os.makedirs(PIPER_DIR, exist_ok=True)
    for ext, b in parts.items():
        with open(os.path.join(PIPER_DIR, name + ext), "wb") as f:
            f.write(b)
    return src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("names", nargs="*", help="only these voices (default: every voice the studio uses)")
    a = ap.parse_args()
    want = a.names or sorted({v for lang in PIPER_VOICES.values() for v in lang.values()} |
                             {PIPER_MULTI[0], PIPER_INDIAN[0]})
    if a.list:
        for n in want + [ALT[k] for k in ALT if k in want]:
            print(("✔ " if os.path.exists(os.path.join(PIPER_DIR, n + ".onnx")) else "○ ") + n)
        return
    for n in want:
        try:
            print(f"{n}: {fetch(n)}")
        except Exception as ex:
            print(f"{n}: ⚠ {ex}")


if __name__ == "__main__":
    main()
