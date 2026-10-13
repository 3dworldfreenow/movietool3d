"""Gemini draws pictures for the Studio (optional - uploading your own pictures always works too).

Uses the same API key as the story writer. Image models are PAID on the API (no free tier):
roughly $0.03 - $0.07 per picture. Every picture made is written to cache/imagegen_log.json with its
estimated cost, so the Studio can show what was spent.

  generate(prompt, refs=[(mime, bytes)], aspect="16:9") -> (mime, bytes)
  refs are pictures Gemini looks at while drawing (a parts sheet to match, a background for the style).
"""
import base64
import json
import os
import time
import uuid

from . import ai

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "cache", "imagegen")
LOG = os.path.join(HERE, "cache", "imagegen_log.json")

MODELS = {                                   # id -> (label, estimated $ per 1K picture) - known prices only;
    "gemini-3.1-flash-lite-image": ("Nano Banana 2 Lite - cheapest", 0.034),     # any model on your key works
    "gemini-3.1-flash-image": ("Nano Banana 2 - best quality", 0.067),
}
DEFAULT = "gemini-3.1-flash-lite-image"
ASPECTS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
USD_INR = 88.0

KIND_ASPECT = {"background": "16:9", "backdrop": "21:9", "picture": "16:9", "object": "3:4", "prop": "1:1",
               "animated": "1:1", "sheet": "21:9", "heads": "16:9"}


def model():
    return ai.clean_model(ai.load_config().get("gemini_image_model") or DEFAULT)


def set_model(m):
    ai.save_config(gemini_image_model=ai.clean_model(m) if m else "")
    return model()


def price(m=None):
    return MODELS.get(m or model(), ("", 0.07))[1]


def spent():
    rows = _log()
    usd = sum(r.get("usd", 0) for r in rows)
    return {"pictures": len(rows), "usd": round(usd, 3), "inr": round(usd * USD_INR)}


def _log():
    try:
        with open(LOG, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def _remember(m, what):
    rows = _log()
    rows.append({"t": int(time.time()), "model": m, "usd": price(m), "what": str(what)[:60]})
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as fh:
        json.dump(rows[-2000:], fh)


def list_image_models():
    """Every model on YOUR key that can draw: Gemini image models (generateContent) and Imagen (predict)."""
    st = ai.settings()
    g = ai.Gemini(st["key"], st["model"], st["api_version"], timeout=60, log=lambda *a: None)
    out, token = [], None
    while True:
        r = g._request("GET", "models?pageSize=100" + (f"&pageToken={token}" if token else ""))
        for m in r.get("models", []):
            name = ai.clean_model(m["name"])
            meth = m.get("supportedGenerationMethods", [])
            if ("image" in name and "generateContent" in meth) or name.startswith("imagen"):
                out.append({"name": name, "display": m.get("displayName", ""),
                            "kind": "imagen" if name.startswith("imagen") else "gemini",
                            "usd": MODELS.get(name, ("", None))[1]})
        token = r.get("nextPageToken")
        if not token:
            break
    return sorted(out, key=lambda x: x["name"], reverse=True)


def _imagen(g, m, prompt, aspect):
    """Imagen models: text -> picture only (they cannot look at a reference picture)."""
    body = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}
    if aspect in ("1:1", "3:4", "4:3", "9:16", "16:9"):
        body["parameters"]["aspectRatio"] = aspect
    r = g._request("POST", f"models/{m}:predict", body)
    for p in r.get("predictions") or []:
        if p.get("bytesBase64Encoded"):
            return p.get("mimeType") or "image/png", base64.b64decode(p["bytesBase64Encoded"])
    raise ai.GeminiError("Imagen gave no picture (maybe blocked by its safety filter). Change the prompt a little.")


def generate(prompt, refs=None, aspect="16:9", what="", m=None):
    """One picture from Gemini. Returns (mime, bytes). Raises ai.GeminiError with a readable message."""
    st = ai.settings()
    m = ai.clean_model(m or model())
    g = ai.Gemini(st["key"], m, st["api_version"], timeout=180, log=lambda *a: None)
    if m.startswith("imagen"):
        prompt = prompt.replace(STYLE_MATCH, "")
        if refs:                                        # Imagen can't look at pictures: describe the match in words
            prompt += " Keep one consistent character design and art style."
        try:
            out = _imagen(g, m, prompt, aspect if aspect != "21:9" else "16:9")
        except ai.GeminiError as ex:
            raise ai.GeminiError(f"{ex}  (image model: {m})") from None
        _remember(m, what or prompt)
        return out
    parts = [{"inline_data": {"mime_type": mm, "data": base64.b64encode(b).decode()}} for mm, b in (refs or [])]
    parts.append({"text": prompt})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
    if aspect in ASPECTS:
        body["generationConfig"]["imageConfig"] = {"aspectRatio": aspect}
    try:
        r = g._request("POST", f"models/{m}:generateContent", body)
    except ai.GeminiError as ex:
        if "imageConfig" in str(ex) or "aspect" in str(ex).lower():      # older model: no aspect setting
            body["generationConfig"].pop("imageConfig", None)
            r = g._request("POST", f"models/{m}:generateContent", body)
        else:
            raise ai.GeminiError(f"{ex}  (image model: {m} - pick another one in 🎨 Gemini images)") from None
    text = []
    for c in r.get("candidates") or []:
        for p in (c.get("content") or {}).get("parts") or []:
            d = p.get("inlineData") or p.get("inline_data")
            if d and d.get("data"):
                _remember(m, what or prompt)
                return d.get("mimeType") or d.get("mime_type") or "image/png", base64.b64decode(d["data"])
            if p.get("text"):
                text.append(p["text"])
    why = (r.get("promptFeedback") or {}).get("blockReason") or \
        ((r.get("candidates") or [{}])[0].get("finishReason")) or ""
    raise ai.GeminiError("Gemini gave no picture" + (f" ({why})" if why else "") +
                         (": " + " ".join(text)[:300] if text else "") + ". Try again or change the prompt a little.")


def save_temp(mime, data):
    """Keep a generated picture for the Studio to show before you upload it. Returns its id."""
    os.makedirs(OUT, exist_ok=True)
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(mime, "png")
    gid = uuid.uuid4().hex[:12]
    with open(os.path.join(OUT, f"{gid}.{ext}"), "wb") as fh:
        fh.write(data)
    return gid, ext


def temp_path(gid):
    if not gid.isalnum():
        return None
    for ext in ("png", "jpg", "webp"):
        p = os.path.join(OUT, f"{gid}.{ext}")
        if os.path.exists(p):
            return p
    return None


STYLE_MATCH = ("Use the attached picture ONLY as the style reference: the same art style, outline, colours and "
               "lighting. Do not copy its scene. ")
