"""A small "select anything" model on your own computer, run by the `transformers` library that Depth Anything
already uses. Two choices (Studio -> Images -> Take things out -> model):

  slimsam    SlimSAM, a 39 MB version of Meta's Segment Anything (default, nothing else to install)
  sam2_tiny  SAM 2.1 Tiny, 156 MB, about twice as fast on a CPU, outlines about the same;
             needs torchvision:  pip install torchvision --index-url https://download.pytorch.org/whl/cpu
             (if it can't load, SlimSAM is used)

  box_mask()   exact outline of the thing inside a box (sharp leafy edges, gaps between branches)
  find()       every separate thing in a picture (a grid of taps; the best, non-overlapping shapes)

The weights download once on first use. The picture is looked at once and remembered, so every further box or
tap on the same picture is quick.
"""
import threading

import numpy as np

MODELS = {
    "slimsam": {"id": "Zigeng/SlimSAM-uniform-77", "label": "SlimSAM · 39 MB (default)", "mb": 39},
    "sam2_tiny": {"id": "facebook/sam2.1-hiera-tiny", "label": "SAM 2.1 Tiny · 156 MB · faster", "mb": 156},
}
DEFAULT = "slimsam"
_M = {}                                     # which -> (model, processor)  or  which -> Exception
_EMB = {}
_FOUND = {}
_LOCK = threading.Lock()


def _base_ok():
    try:
        import torch  # noqa: F401
        from transformers import SamModel  # noqa: F401
        return True
    except Exception:
        return False


def sam2_ok():
    try:
        import torchvision  # noqa: F401
        from transformers import Sam2Model  # noqa: F401
        return True
    except Exception:
        return False


def chosen():
    from . import ai
    c = ai.load_config().get("sam_model") or DEFAULT
    return c if c in MODELS else DEFAULT


def set_choice(which):
    from . import ai
    ai.save_config(sam_model=which if which in MODELS and which != DEFAULT else "")
    _EMB.clear()
    _FOUND.clear()
    return chosen()


def backend():
    """The model that will really be used."""
    c = chosen()
    if c == "sam2_tiny" and sam2_ok() and not isinstance(_M.get("sam2_tiny"), Exception):
        return "sam2_tiny"
    return "slimsam"


def available():
    return _base_ok() and not isinstance(_M.get("slimsam"), Exception)


def status():
    return {"chosen": chosen(), "using": backend() if _base_ok() else None, "base": _base_ok(),
            "sam2_ready": sam2_ok(), "models": {k: v["label"] for k, v in MODELS.items()}}


def _load(which=None):
    which = which or backend()
    got = _M.get(which)
    if got is not None and not isinstance(got, Exception):
        return which, got[0], got[1]
    try:
        if which == "sam2_tiny":
            from transformers import Sam2Model, Sam2Processor
            m, p = Sam2Model.from_pretrained(MODELS[which]["id"]).eval(), Sam2Processor.from_pretrained(MODELS[which]["id"])
        else:
            from transformers import SamModel, SamProcessor
            m, p = SamModel.from_pretrained(MODELS[which]["id"]).eval(), SamProcessor.from_pretrained(MODELS[which]["id"])
        _M[which] = (m, p)
        return which, m, p
    except Exception as ex:
        if which != "slimsam":                         # SAM 2 can't load: fall back to SlimSAM
            print("SAM 2.1 Tiny not used:", ex)
            _M[which] = ex
            return _load("slimsam")
        _M[which] = ex
        raise


def _embed(key, im):
    import torch
    which, model, proc = _load()
    k = (which, key, im.size)
    if k not in _EMB:
        _EMB.clear()                                    # one picture at a time is enough (memory)
        with torch.no_grad():
            if which == "sam2_tiny":
                inp = proc(images=im, return_tensors="pt")
                _EMB[k] = (model.get_image_embeddings(inp["pixel_values"]), inp["original_sizes"], None)
            else:
                inp = proc(im, return_tensors="pt")
                _EMB[k] = (model.get_image_embeddings(inp["pixel_values"]), inp["original_sizes"],
                           inp["reshaped_input_sizes"])
    return which, model, proc, _EMB[k]


def box_mask(key, im, box, point=None):
    """box = (x0, y0, x1, y1) in picture pixels, point = (x, y) on the thing or None. Returns (bool mask, score)."""
    import torch
    W, H = im.size
    with _LOCK:
        which, model, proc, (emb, osz, rsz) = _embed(key, im)
        b = [float(v) for v in box]
        with torch.no_grad():
            if which == "sam2_tiny":
                kw = {"input_boxes": [[b]], "original_sizes": [[H, W]]}
                if point is not None:
                    kw.update(input_points=[[[list(map(float, point))]]], input_labels=[[[1]]])
                ip = proc(return_tensors="pt", **kw)
                args = {k: ip[k] for k in ("input_boxes", "input_points", "input_labels") if k in ip}
                out = model(image_embeddings=emb, multimask_output=True, **args)
                masks = proc.post_process_masks(out.pred_masks, osz)[0][0]
            else:
                kw = {"input_boxes": [[b]]}
                if point is not None:
                    kw["input_points"] = [[[list(map(float, point))]]]
                ip = proc(im, return_tensors="pt", **kw)
                args = {"input_boxes": ip["input_boxes"]}
                if point is not None:
                    args["input_points"] = ip["input_points"]
                    args["input_labels"] = torch.ones(ip["input_points"].shape[:-1], dtype=torch.long)
                out = model(image_embeddings=emb, multimask_output=True, **args)
                masks = proc.image_processor.post_process_masks(out.pred_masks, osz, rsz)[0][0]
        sc = out.iou_scores[0, 0].numpy()
    best = int(np.argmax(sc))
    return masks[best].numpy().astype(bool), float(sc[best])


def find(key, im, grid=(13, 7), min_score=0.86, min_area=0.003, max_area=0.14, keep=16):
    """Every separate, clear shape in the picture. Returns [(score, mask at picture size, (x0, y0, x1, y1))]."""
    import torch
    from PIL import Image
    fk = (backend(), key, im.size)
    if fk in _FOUND:
        return _FOUND[fk]
    W, H = im.size
    rgb = np.asarray(im)
    pts = [(W * (i + 0.5) / grid[0], H * (j + 0.5) / grid[1]) for j in range(grid[1]) for i in range(grid[0])]
    pts = [p for p in pts if not (p[1] < 0.4 * H and int(rgb[int(p[1]), int(p[0]), 2]) -
                                  int(rgb[int(p[1]), int(p[0]), 0]) > 40)]           # skip the sky
    cands = []
    with _LOCK:
        which, model, proc, (emb, osz, rsz) = _embed(key, im)
        for b in range(0, len(pts), 64):
            part = pts[b:b + 64]
            with torch.no_grad():
                if which == "sam2_tiny":
                    ip = proc(input_points=[[[list(p)] for p in part]], input_labels=[[[1] for _ in part]],
                              original_sizes=[[H, W]], return_tensors="pt")
                    out = model(image_embeddings=emb, input_points=ip["input_points"],
                                input_labels=ip["input_labels"], multimask_output=True)
                    low = out.pred_masks[0] > 0                                # square: the whole picture
                else:
                    rh, rw = [int(v) for v in rsz[0]]
                    k_ = 1024.0 / max(W, H)                                    # the model's view: longest side 1024
                    ipt = torch.tensor([[list(p)] for p in part], dtype=torch.float32)[None] * k_
                    out = model(image_embeddings=emb, input_points=ipt,
                                input_labels=torch.ones(ipt.shape[:-1], dtype=torch.long), multimask_output=True)
                    low = out.pred_masks[0][:, :, :rh // 4, :rw // 4] > 0
            sc = out.iou_scores[0].numpy()
            for k in range(low.shape[0]):
                for j in range(low.shape[1]):
                    if sc[k, j] < min_score:
                        continue
                    m = low[k, j].numpy()
                    a = m.mean()
                    if min_area <= a <= max_area:
                        cands.append((float(sc[k, j]) + 0.15 * min(a / 0.05, 1.0), m))
    cands.sort(key=lambda c: -c[0])
    chosen_ = []
    for s, m in cands:                                  # drop shapes that are mostly another chosen shape
        if all((m & c[1]).sum() / max(min(m.sum(), c[1].sum()), 1) < 0.6 for c in chosen_):
            chosen_.append((s, m))
        if len(chosen_) >= keep:
            break
    out = []
    for s, m in chosen_:
        big = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)) > 127
        ys, xs = np.nonzero(big)
        if len(ys):
            out.append((s, big, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)))
    _FOUND.clear()
    _FOUND[fk] = out
    return out
