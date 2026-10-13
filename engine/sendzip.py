"""Send a static script file compressed (gzip) and cached by the browser - three.js goes from 670 KB to ~167 KB.
The compressed bytes are kept in memory until the file changes; the browser re-checks with an ETag (304 = keep
yours). Files outside the folder are refused."""
import gzip
import os

from flask import Response, abort, request

_CACHE = {}


def send(folder, name, max_age=86400, mimetype="text/javascript"):
    path = os.path.realpath(os.path.join(folder, name))
    if not path.startswith(os.path.realpath(folder) + os.sep) or not os.path.isfile(path):
        abort(404)
    st = os.stat(path)
    etag = f'"{int(st.st_mtime)}-{st.st_size}"'
    if request.headers.get("If-None-Match") == etag:
        r = Response(status=304)
    else:
        key = (path, st.st_mtime, st.st_size)
        if key not in _CACHE:
            with open(path, "rb") as fh:
                raw = fh.read()
            _CACHE[key] = (raw, gzip.compress(raw, 6))
        raw, gz = _CACHE[key]
        if "gzip" in (request.headers.get("Accept-Encoding") or ""):
            r = Response(gz, mimetype=mimetype)
            r.headers["Content-Encoding"] = "gzip"
        else:
            r = Response(raw, mimetype=mimetype)
    r.headers["ETag"] = etag
    r.headers["Vary"] = "Accept-Encoding"
    r.headers["Cache-Control"] = f"private, max-age={max_age}"
    return r


# 📦 every data / page reply compressed too (the star map is ~170 KB of JSON: ~5× smaller gzipped) - phones load faster
_ZIP_TYPES = ("application/json", "text/html", "text/plain", "text/css", "application/javascript", "text/javascript", "image/svg+xml")


def init_app(app, min_size=1500):
    @app.after_request
    def _zip(resp):
        try:
            if (resp.status_code != 200 or resp.direct_passthrough or resp.headers.get("Content-Encoding")
                    or "gzip" not in (request.headers.get("Accept-Encoding") or "")
                    or not (resp.mimetype or "").startswith(_ZIP_TYPES)):
                return resp
            data = resp.get_data()
            if len(data) < min_size:
                return resp
            resp.set_data(gzip.compress(data, 5))
            resp.headers["Content-Encoding"] = "gzip"
            resp.headers["Content-Length"] = str(len(resp.get_data()))
            vary = resp.headers.get("Vary")
            resp.headers["Vary"] = (vary + ", Accept-Encoding") if vary and "Accept-Encoding" not in vary else (vary or "Accept-Encoding")
        except Exception:                                                    # noqa: BLE001 - never break a reply over compression
            pass
        return resp
