"""Audio utilities: decoding, WAV IO, lip-sync envelopes and the final mixer."""
import subprocess
import wave

import numpy as np

SR = 44100


def decode_audio(path, sr=SR):
    """Decode any audio file (mp3/wav/ogg/...) to mono float32 using FFmpeg."""
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).copy()


def decode_stereo(path, sr=SR):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).reshape(-1, 2).T.copy()


def write_wav(path, audio, sr=SR):
    a = np.asarray(audio, np.float32)
    if a.ndim == 1:
        a = a[None, :]
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2").T.copy()
    with wave.open(path, "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        n, ch = w.getnframes(), w.getnchannels()
        data = np.frombuffer(w.readframes(n), "<i2").astype(np.float32) / 32767.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data


def lip_curve(audio, fps, sr=SR):
    """Mouth openness (0..1) per video frame from a speech clip's loudness."""
    hop = sr / fps
    n = max(1, int(np.ceil(len(audio) / hop)))
    vals = np.zeros(n, np.float32)
    win = int(hop * 1.2)
    for i in range(n):
        a = int(i * hop)
        seg = audio[a:a + win]
        vals[i] = np.sqrt(np.mean(seg * seg)) if len(seg) else 0.0
    ref = np.percentile(vals, 92) if vals.max() > 0 else 1.0
    vals = np.clip(vals / max(ref, 1e-6), 0, 1.2)
    out = np.zeros_like(vals)
    prev = 0.0
    for i, v in enumerate(vals):          # fast open, slower close
        prev = v if v > prev else prev * 0.55 + v * 0.45
        out[i] = prev
    out[out < 0.15] = 0.0
    out = np.clip(out ** 0.75, 0, 1)
    # mouths should visibly close between syllables: add a subtle flutter
    flutter = 0.82 + 0.18 * np.sin(np.arange(n) * 2.1)
    return (out * flutter).astype(np.float32)


def pan_gains(pan):
    pan = max(-1.0, min(1.0, pan))
    a = (pan + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


class Mixer:
    BUSES = ("voice", "sfx", "ambient", "music")

    def __init__(self, duration, sr=SR):
        self.sr = sr
        self.n = int(duration * sr) + sr
        self.bus = {b: np.zeros((2, self.n), np.float32) for b in self.BUSES}

    def add(self, bus, sig, t, gain=1.0, pan=0.0):
        sig = np.asarray(sig, np.float32)
        a = int(round(t * self.sr))
        if a >= self.n or sig.size == 0:
            return
        if a < 0:
            sig = sig[..., -a:]
            a = 0
        if sig.ndim == 1:
            gl, gr = pan_gains(pan)
            m = min(len(sig), self.n - a)
            self.bus[bus][0, a:a + m] += sig[:m] * gain * gl * 1.414
            self.bus[bus][1, a:a + m] += sig[:m] * gain * gr * 1.414
        else:
            m = min(sig.shape[1], self.n - a)
            self.bus[bus][:, a:a + m] += sig[:, :m] * gain

    def mixdown(self, music_gain=0.22, ambient_gain=0.35, sfx_gain=0.7, voice_gain=1.0,
                duck_depth=0.72, total=None):
        v = self.bus["voice"]
        env = np.abs(v).max(axis=0)
        # envelope follower: 15 ms attack, 450 ms release  (block-wise for speed)
        blk = 256
        nb = int(np.ceil(self.n / blk))
        pad = np.zeros(nb * blk, np.float32)
        pad[:self.n] = env
        blocks = pad.reshape(nb, blk).max(axis=1)
        a_att = 1 - np.exp(-blk / (0.015 * self.sr))
        a_rel = 1 - np.exp(-blk / (0.45 * self.sr))
        sm = np.zeros(nb, np.float32)
        cur = 0.0
        for i, x in enumerate(blocks):
            cur += (x - cur) * (a_att if x > cur else a_rel)
            sm[i] = cur
        level = np.clip(sm / 0.25, 0, 1)
        duck = 1.0 - duck_depth * level
        # mixed in pieces of 10 s straight into the voice bus (no full-length copies: a 20-minute episode
        # used to need ~8 full-length arrays at once here)
        step = 10 * self.sr
        sfx, amb, mus = self.bus["sfx"], self.bus["ambient"], self.bus["music"]
        for a in range(0, self.n, step):
            b = min(self.n, a + step)
            d = np.repeat(duck[a // blk:(b + blk - 1) // blk + 1], blk)[a % blk:a % blk + (b - a)]
            seg = v[:, a:b]
            seg *= voice_gain
            seg += sfx[:, a:b] * sfx_gain
            seg += amb[:, a:b] * (ambient_gain * (0.55 + 0.45 * d))
            seg += mus[:, a:b] * (music_gain * d)
        self.bus = {"voice": v}                          # the other buses are let go now
        out = v[:, :int(total * self.sr)] if total else v
        peak = np.abs(out).max() if out.size else 0.0
        if peak > 0.98:
            np.multiply(out, 1.1, out=out)
            np.tanh(out, out=out)
            out /= np.tanh(1.1)
        return out
