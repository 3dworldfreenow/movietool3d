"""✏🦖 Stick 3D flat-colour test: a doodle kid runs from a cartoon T-rex through the village.

    python tools/stick3d_chase.py still out.png | python tools/stick3d_chase.py video out.mp4
"""
import sys, time, subprocess, math
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from engine import stick3d, poses
from engine.stick3d import M
from PIL import Image
import numpy as np
W, H = 1920, 1080
stick3d.STYLE[0] = "flat"
world = stick3d.village()
LANE = 150.0
KID = {"shirt": (0.98, 0.80, 0.20), "pants": (0.25, 0.35, 0.65), "hair": "short", "skin": "wheat"}

def scene(t):
    kx = (-12 + 5.2 * t) * M
    pose, _ = poses.a_run(t, 10, {"mood": "scared"})
    kid = {"id": "raju", "pos": (kx, 0, LANE), "dir": 0.0, "pose": pose, "face": "scared",
           "mouth": 0.7 + 0.3 * math.sin(t * 20), "look": KID, "speed": 1}
    dino = {"id": "rex", "kind": "dino", "pos": (kx - 6.0 * M, 0, LANE + 40), "dir": 0.0, "run": 1.0}
    cx = kx - 2.6 * M
    cam = stick3d.Cam((cx + 1.0 * M, 1.5 * M, LANE - 10.5 * M), (cx, 2.1 * M, LANE), fov=46, W=W, H=H)
    bub = ("raju", "Bachaooo!") if 1.0 < t < 4.0 else None
    return cam, [kid, dino], bub

if sys.argv[1] == "still":
    o = Image.new('RGB', (1920, 1080))
    for i, t in enumerate((0.3, 1.5, 2.6, 4.2)):
        cam, pp, bub = scene(t)
        b = stick3d.draw_frame(W, H, cam, world, pp, t, int(t * 24), bub)
        a = np.frombuffer(b, np.uint8).reshape(H, W, 4)[..., [2, 1, 0]]
        o.paste(Image.fromarray(a.copy()).resize((960, 540)), ((i % 2) * 960, (i // 2) * 540))
    o.save(sys.argv[2])
else:
    secs, fps = 5.0, 24
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation",
                           "-crf", "20", "-pix_fmt", "yuv420p", sys.argv[2]], stdin=subprocess.PIPE)
    td = 0
    for i in range(int(secs * fps)):
        if i % 2 == 0:
            t = i / fps
            cam, pp, bub = scene(t)
            t0 = time.time()
            fr = stick3d.draw_frame(W, H, cam, world, pp, t, i, bub)
            td += time.time() - t0
        ff.stdin.write(fr)
    ff.stdin.close(); ff.wait()
    print(f"{td / (secs * fps / 2) * 1000:.0f} ms per drawing")
