"""✏🧊 Stick 3D step-1 test: the sketch village in real 3D, two stickmen, an orbiting camera -> MP4 + speed.

    python tools/stick3d_test.py out.mp4 [--res 1920x1080] [--secs 10]
"""
import argparse
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import poses, stick3d  # noqa: E402


def people_at(t):
    """Raju walks in from the left, stops by Munni and talks; Munni waits, then answers"""
    walk_end = 4.0
    x = -650 + 170 * min(t, walk_end) * 1.2
    if t < walk_end:
        pose_r, _ = poses.a_walk(t, walk_end, {})
        face_r, mouth_r = "happy", 0.0
    else:
        pose_r, _ = poses.a_talk(t, 3.0, {}) if t < 7 else poses.a_idle(t, 3.0, {})
        face_r, mouth_r = "happy", (0.5 + 0.5 * math.sin(t * 17)) if t < 7 else 0.0
    pose_m, _ = poses.a_talk(t, 3.0, {}) if t >= 7 else poses.a_idle(t, 3.0, {})
    return [
        {"id": "raju", "pos": (min(x, 160), 0, 420), "dir": 0.0, "pose": pose_r, "face": face_r, "mouth": mouth_r},
        {"id": "munni", "pos": (380, 0, 470), "dir": math.pi, "pose": pose_m,
         "face": "happy" if t >= 7 else "surprised", "mouth": (0.5 + 0.5 * math.sin(t * 15)) if t >= 7 else 0.0},
    ]


KIDS = {"raju": {"shirt": (0.98, 0.80, 0.20), "pants": (0.25, 0.35, 0.65), "hair": "short", "skin": "wheat"},
        "munni": {"shirt": (0.95, 0.45, 0.60), "dress": True, "hair": "bunches", "skin": "wheat"}}


def bubble_at(t):
    if 4.2 <= t < 7:
        return ("raju", "Munni, mela chalogi?")
    if t >= 7.2:
        return ("munni", "Haan! Chalo!")
    return None


def cam_at(t, W, H, secs):
    a = -1.95 + 1.2 * (t / secs)                                   # orbit a third of the way round
    r = 1050 - 250 * (t / secs)                                    # and push in a little
    cx, cz = 0.0, 450.0
    return stick3d.Cam((cx + r * math.cos(a), 300, cz + r * math.sin(a)), (cx, 190, cz), fov=46, W=W, H=H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--secs", type=float, default=10.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--kids", action="store_true", help="doodle kids (clothes, hair, sticker edge)")
    ap.add_argument("--look", default="wash", choices=("lines", "bold", "wash"))
    a = ap.parse_args()
    W, H = (int(v) for v in a.res.split("x"))
    world = stick3d.village()
    stick3d.STYLE[0] = a.look
    n = int(a.secs * a.fps)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                           "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation",
                           "-crf", "20", "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
    t_draw = 0.0
    frame = None
    for i in range(n):
        if i % 2 == 0:                                             # on twos, like the 2D sketch
            t = i / a.fps
            t0 = time.time()
            people = people_at(t)
            for p in people if a.kids else ():
                p["look"] = KIDS[p["id"]]
            frame = stick3d.draw_frame(W, H, cam_at(t, W, H, a.secs), world, people, t, i, bubble_at(t))
            t_draw += time.time() - t0
        ff.stdin.write(frame)
    ff.stdin.close()
    ff.wait()
    drawings = (n + 1) // 2
    print(f"{drawings} drawings, {t_draw / drawings * 1000:.0f} ms per drawing at {W}x{H} on one core "
          f"({len(world)} shapes)")


if __name__ == "__main__":
    main()
