"""🎥 Act it yourself: a video of a person (phone camera is fine) -> a move every character can do, body AND face.

The idea of DigiHuman (github.com/Danial-Kord/DigiHuman: video -> MediaPipe -> a 3D character), done our own way on
the server (MediaPipe, Apache-2.0; no DigiHuman code): the actor's 33 body points in 3D become our pose angles
(the same ones a Mixamo move or a hand-made action uses: torso lean, head, thighs, shins, upper arms, forearms, a
jump's lift) and the 52 face values (jaw open, smile, brows, blinks, pucker, eyes looking) become our talking-face
controls. It is smoothed (a low-pass, like DigiHuman) and saved small in assets/moves/<name>.json:

    python -m engine.videomocap my_dance.mp4 golu_dance          # -> {"who": "golu_dada", "do": "golu_dance"}

Our figures move in their own front / up plane, so an arm held out to the side counts as raised (the energy and the
timing of the actor stay). The face plays on the character when the move plays (no line being spoken over it).
"""
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "assets", "mocap_models")
URLS = {"pose": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/"
                "pose_landmarker_full.task",
        "face": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/"
                "face_landmarker.task"}
FPS = 15.0
# MediaPipe pose points
NOSE, L_EAR, R_EAR = 0, 7, 8
L_SH, R_SH, L_EL, R_EL, L_WR, R_WR = 11, 12, 13, 14, 15, 16
L_HIP, R_HIP, L_KN, R_KN, L_AN, R_AN = 23, 24, 25, 26, 27, 28
L_TOE, R_TOE = 31, 32


def _model(kind):
    path = os.path.join(MODELS, os.path.basename(URLS[kind]))
    if not os.path.exists(path):                       # fetched once (pose 9 MB, face 4 MB)
        import urllib.request
        os.makedirs(MODELS, exist_ok=True)
        urllib.request.urlretrieve(URLS[kind], path)
    return path


def _frames(path, fps):
    """the video's frames at our fps -> (rgb uint8 array, time ms)"""
    import cv2
    cap = cv2.VideoCapture(path)
    vf = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1.0, vf / fps)
    i, nxt = 0, 0.0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i >= nxt - 1e-6:
            nxt += step
            yield cv2.cvtColor(fr, cv2.COLOR_BGR2RGB), int(i * 1000.0 / vf)
        i += 1
    cap.release()


def _smooth(rows, keys, win=2):
    """a centred moving average over +-win frames (angles the short way round): the shake of the tracker goes"""
    out = []
    n = len(rows)
    for i in range(n):
        r = dict(rows[i])
        for k in keys:
            if k not in r:
                continue
            base = rows[i][k]
            acc, w = 0.0, 0.0
            for j in range(max(0, i - win), min(n, i + win + 1)):
                if k in rows[j]:
                    d = (rows[j][k] - base + 180.0) % 360.0 - 180.0
                    ww = 1.0 / (1 + abs(i - j))
                    acc += d * ww
                    w += ww
            r[k] = round(base + acc / max(w, 1e-9), 2)
        out.append(r)
    return out


def _pose_of(P, up):
    """33 world points (metres, y up) -> our pose angles (degrees)"""
    left = P[L_HIP] - P[R_HIP]
    left = left - up * np.dot(left, up)
    fwd = np.cross(left, up)
    fwd /= (np.linalg.norm(fwd) or 1.0)
    if np.dot(P[NOSE] - (P[L_EAR] + P[R_EAR]) / 2, fwd) < 0:     # (the nose is in front: fix a flipped body)
        fwd = -fwd

    def ang(v):
        L = float(np.linalg.norm(v)) or 1.0
        f, u = float(np.dot(v, fwd)) / L, float(np.dot(v, up)) / L
        elev = math.degrees(math.acos(max(-1.0, min(1.0, -u))))
        if abs(f) > 0.25:
            return elev if f > 0 else -elev
        return elev                                    # held out to the side: counts as raised (never a noisy flip)

    def bend(a, b):
        """the real 3D angle at a joint (0 = straight): elbows and knees never fold the wrong way from tracker noise"""
        ca = float(np.dot(a, b)) / ((float(np.linalg.norm(a)) * float(np.linalg.norm(b))) or 1.0)
        return math.degrees(math.acos(max(-1.0, min(1.0, ca))))

    def lean(v):
        return math.degrees(math.atan2(float(np.dot(v, fwd)), float(np.dot(v, up))))

    def wrap(a):
        return (a + 180.0) % 360.0 - 180.0
    hips, sh = (P[L_HIP] + P[R_HIP]) / 2, (P[L_SH] + P[R_SH]) / 2
    p = {"torso": lean(sh - hips)}
    p["head"] = wrap(lean((P[L_EAR] + P[R_EAR]) / 2 - sh) - p["torso"])
    for side, (hp, kn, an, s_, el, wr) in (("n", (R_HIP, R_KN, R_AN, R_SH, R_EL, R_WR)),
                                           ("f", (L_HIP, L_KN, L_AN, L_SH, L_EL, L_WR))):
        p[f"l{side}_t"] = ang(P[kn] - P[hp])
        p[f"l{side}_s"] = -bend(P[kn] - P[hp], P[an] - P[kn])          # knees bend back
        p[f"a{side}_u"] = ang(P[el] - P[s_])
        p[f"a{side}_l"] = bend(P[el] - P[s_], P[wr] - P[el])           # elbows bend forward
    p["rot"] = 0.0
    return p


def _talk_of(bs):
    """the 52 face values (ARKit names) -> our face controls"""
    g = lambda *k: sum(bs.get(x, 0.0) for x in k) / len(k)        # noqa: E731
    jaw = min(1.0, g("jawOpen") * 1.4)
    smile = g("mouthSmileLeft", "mouthSmileRight")
    pucker = max(g("mouthPucker"), g("mouthFunnel"))
    closed = max(0.0, min(1.0, g("mouthClose") * 2.0 + g("mouthPressLeft", "mouthPressRight") - jaw))
    return {"jaw": round(jaw, 3), "wide": round(min(1.0, 0.4 + smile + g("mouthStretchLeft", "mouthStretchRight")), 3),
            "round": round(min(1.0, pucker * 1.3), 3), "closed": round(closed if jaw < 0.08 else 0.0, 3),
            "teeth": round(1.0 if (smile > 0.35 and jaw > 0.1) else 0.0, 3), "tongue": 0.0,
            "brow": round(min(1.0, g("browInnerUp") + g("browOuterUpLeft", "browOuterUpRight")) -
                          0.6 * g("browDownLeft", "browDownRight"), 3),
            "lid": round(g("eyeBlinkLeft", "eyeBlinkRight"), 3),
            "gx": round(g("eyeLookOutRight", "eyeLookInLeft") - g("eyeLookInRight", "eyeLookOutLeft"), 3),
            "gy": round(g("eyeLookUpLeft", "eyeLookUpRight") - g("eyeLookDownLeft", "eyeLookDownRight"), 3),
            "smile": round(smile, 3), "nod": 0.0}


def capture(path, fps=FPS, face=True, progress=None):
    """video -> (poses [dict per frame, with "_talk" when a face was seen], seconds, report)"""
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    pose_lm = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=_model("pose")), running_mode=vision.RunningMode.VIDEO,
        num_poses=1))
    face_lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=_model("face")), running_mode=vision.RunningMode.VIDEO,
        output_face_blendshapes=True, num_faces=1)) if face else None
    up = np.array([0.0, 1.0, 0.0])
    rows, hip_y, legs, seen_face = [], [], [], 0
    last = None
    for k, (rgb, ms) in enumerate(_frames(path, fps)):
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        r = pose_lm.detect_for_video(img, ms)
        if r.pose_world_landmarks:
            W = np.array([[q.x, -q.y, -q.z] for q in r.pose_world_landmarks[0]])     # (MediaPipe y points down)
            row = _pose_of(W, up)
            N = r.pose_landmarks[0]
            hy = (N[L_HIP].y + N[R_HIP].y) / 2
            lg = abs((N[L_AN].y + N[R_AN].y) / 2 - hy)
            last = row
        else:
            row = dict(last) if last else None             # (lost for a moment: hold the last pose)
            hy, lg = (hip_y[-1], legs[-1]) if hip_y else (0.5, 0.4)
        if row is None:
            continue
        hip_y.append(hy)
        legs.append(lg)
        if face_lm is not None:
            f = face_lm.detect_for_video(img, ms)
            if f.face_blendshapes:
                row["_talk"] = _talk_of({c.category_name: c.score for c in f.face_blendshapes[0]})
                seen_face += 1
        rows.append(row)
        if progress and k % 15 == 0:
            progress(k)
    pose_lm.close()
    if face_lm is not None:
        face_lm.close()
    if not rows:
        raise ValueError("no person found in this video (the whole body should be in the picture)")
    base = float(np.median(hip_y))                         # a jump: the hips rise above their usual height
    leg = float(np.median(legs)) or 0.4
    for i, r in enumerate(rows):
        r["lift"] = round(max(0.0, (base - hip_y[i]) / leg * 142.0), 1)
    rows = _smooth(rows, ["torso", "head", "ln_t", "ln_s", "lf_t", "lf_s", "an_u", "an_l", "af_u", "af_l", "lift"])
    secs = round(len(rows) / fps, 3)
    return rows, secs, {"frames": len(rows), "seconds": secs, "face_frames": seen_face}


def import_video(path, name=None, face=True, loop=False):
    """a video file -> a saved move (body + face). -> (name, report)"""
    from .mocap import save_move
    rows, secs, rep = capture(path, face=face)
    nm = save_move(name or os.path.splitext(os.path.basename(path))[0], rows, secs, os.path.basename(path), loop=loop)
    return nm, rep


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    nm, rep = import_video(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print("saved move", nm, rep)
