#!/usr/bin/env python3
"""Local annotation/edit tool — a tiny stdlib web app (no deps, never deployed).

Edits ANY data layer of a litmap-style project. It reads the project's
`config.json`, lists its works, and lets you:

  * override ANY field of an existing feature — title, character, time, seq,
    gloss, quote, ref, srcText, essay, verified, and (for points) the
    coordinates — via the per-work overlay `data/<work>-annotations.json`
    (the base GeoJSON is never modified; the engine merges the overlay at load);
  * create a NEW feature (place or route) → written to
    `data/<work>-own-source.json` and rendered to `data/<work>-own.geojson`
    via the geocoder (source: "own").

Run from the project (or point at one with --root):

    python3 pipeline/annotate-ui/serve.py            # http://127.0.0.1:8765/
    python3 pipeline/annotate-ui/serve.py --root /path/to/project --port 8765

Local-only (binds 127.0.0.1); no auth.
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))   # import pipeline/*.py
import overlay as ov          # noqa: E402
import geocode_source as gs   # noqa: E402

# Fields shown read-only as base context.
CONTEXT_FIELDS = ["name", "story", "character", "time", "seq", "gloss",
                  "quote", "ref", "srcText", "essay", "essaySource",
                  "confidence", "verified", "source"]
ROOT = HERE  # set in main()


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def lang_of(cfg):
    return (cfg.get("site", {}) or {}).get("defaultLang", "en")


def works_list(cfg):
    lang = lang_of(cfg)
    out = []
    for key, w in cfg.get("works", {}).items():
        label = w.get("label", {})
        out.append({"key": key, "label": label.get(lang) or label.get("en") or key,
                    "annotations": bool(w.get("annotations"))})
    return out


def groups_of(cfg, work_key):
    lang = lang_of(cfg)
    out = []
    for i, g in enumerate(cfg["works"][work_key].get("groups", []), start=1):
        out.append({"n": i, "key": g.get("key"),
                    "label": (g.get(lang) if lang != "en" else g.get("key")) or g.get("key")})
    return out


def geom_brief(f):
    g = f.get("geometry") or {}
    if g.get("type") == "Point":
        c = g["coordinates"]
        return {"type": "Point", "lon": c[0], "lat": c[1]}
    if g.get("type") == "LineString":
        return {"type": "LineString", "npts": len(g.get("coordinates", []))}
    return {"type": g.get("type")}


def features_payload(cfg, work_key):
    w = cfg["works"][work_key]
    feats = ov.load_work_features(ROOT, w)
    ids = ov.feature_ids(feats)
    ann, _ = ov.load_overlay(ov.overlay_path(ROOT, work_key, w))
    items = []
    for f, fid in zip(feats, ids):
        p = f["properties"]
        items.append({
            "id": fid, "story": p.get("story"), "name": p.get("name"),
            "kind": p.get("kind", "place"), "source": p.get("source"),
            "base": {k: p.get(k) for k in CONTEXT_FIELDS if p.get(k) is not None},
            "geom": geom_brief(f),
            "patch": ann.get(fid, {}),
        })
    return {"work": work_key, "label": w.get("label", {}),
            "configured": bool(w.get("annotations")),
            "groups": groups_of(cfg, work_key), "features": items}


def _coerce(k, v):
    if v in (None, "", []):
        return None
    if k == "seq":
        return int(v)
    if k in ("lat", "lon"):
        return round(float(v), 6)
    if k == "verified":
        return True if v in (True, "true") else (False if v in (False, "false") else None)
    return v


def save_patch(cfg, work_key, fid, patch):
    w = cfg["works"][work_key]
    path = ov.overlay_path(ROOT, work_key, w)
    ann, _ = ov.load_overlay(path)
    clean = {}
    for k, v in (patch or {}).items():
        cv = _coerce(k, v)
        if cv is not None:
            clean[k] = cv
    if clean:
        ann[fid] = clean
    else:
        ann.pop(fid, None)
    ov.save_overlay(path, work_key, ann)
    hint = None
    if not w.get("annotations"):
        hint = ('Add  "annotations": "%s"  to works.%s in config.json so the map '
                'applies these.' % (os.path.relpath(path, ROOT), work_key))
    return {"ok": True, "count": len(clean), "configHint": hint}


def own_source_path(work_key):
    return os.path.join(ROOT, "data", work_key + "-own-source.json")


def create_feature(cfg, work_key, body):
    """Append a new own feature to <work>-own-source.json and regenerate the
    rendered <work>-own.geojson via the geocoder."""
    src_path = own_source_path(work_key)
    if os.path.exists(src_path):
        src = json.load(open(src_path, encoding="utf-8"))
    else:
        src = {"work": work_key, "source": "own",
               "groups": [{"n": g["n"], "en": g["key"], "de": ""} for g in groups_of(cfg, work_key)],
               "places": [], "routes": []}
    src.setdefault("places", []); src.setdefault("routes", []); src["source"] = "own"

    kind = body.get("kind", "place")
    # `group` may be a single chapter (int) or a list of chapters (primary first,
    # for a multi-chapter place). The frontend sends ints; cast defensively.
    grp = body["group"]
    grp = [int(x) for x in grp] if isinstance(grp, list) else int(grp)
    entry = {"group": grp, "name": body["name"].strip()}
    for k in ("gloss", "quote", "character", "time", "ref", "srcText", "essay", "essaySource", "confidence"):
        if body.get(k):
            entry[k] = body[k]
    if body.get("seq") not in (None, ""):
        entry["seq"] = int(body["seq"])

    if kind == "route":
        if body.get("coords"):
            entry["coords"] = body["coords"]
        else:
            entry["from"] = body["from"]; entry["to"] = body["to"]
            entry["mode"] = body.get("mode", "driving")
        src["routes"].append(entry)
    else:
        if body.get("lat") not in (None, "") and body.get("lon") not in (None, ""):
            entry["lat"] = round(float(body["lat"]), 6)
            entry["lon"] = round(float(body["lon"]), 6)
        else:
            entry["geocode"] = body.get("geocode") or body["name"]
        src["places"].append(entry)

    with open(src_path, "w", encoding="utf-8") as f:
        json.dump(src, f, ensure_ascii=False, indent=2)

    region = (cfg.get("view") or {}).get("regionBBox")
    out_path = os.path.join(ROOT, "data", work_key + "-own.geojson")
    gs.main(src_path, out_path, region)   # geocode + render

    hint = None
    files = [e if isinstance(e, str) else e.get("url")
             for e in ov.normalize_data(cfg["works"][work_key])]
    if ("data/%s-own.geojson" % work_key) not in files:
        hint = ('Add  "data/%s-own.geojson"  to works.%s.data in config.json so the '
                'map loads your additions.' % (work_key, work_key))
    return {"ok": True, "configHint": hint}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _file(self, name, ctype):
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            return self._send(404, "not found", "text/plain")
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def log_message(self, *a):
        pass

    def _work(self, cfg, q):
        wk = (q.get("work") or [None])[0]
        return wk if wk in cfg.get("works", {}) else None

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self._file("index.html", "text/html; charset=utf-8")
            if u.path == "/app.js":
                return self._file("app.js", "text/javascript; charset=utf-8")
            if u.path == "/api/works":
                return self._json(200, works_list(load_config()))
            if u.path == "/api/features":
                cfg = load_config(); wk = self._work(cfg, q)
                if not wk:
                    return self._json(400, {"error": "unknown work"})
                return self._json(200, features_payload(cfg, wk))
            self._send(404, "not found", "text/plain")
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or "{}")
            cfg = load_config(); wk = self._work(cfg, q)
            if not wk:
                return self._json(400, {"error": "unknown work"})
            if u.path == "/api/overlay":
                return self._json(200, save_patch(cfg, wk, body["id"], body.get("patch", {})))
            if u.path == "/api/create":
                return self._json(200, create_feature(cfg, wk, body))
            self._send(404, "not found", "text/plain")
        except Exception as e:
            self._json(500, {"error": str(e)})


def main():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.abspath(os.path.join(HERE, "..", "..")))
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    ROOT = args.root
    if not os.path.exists(os.path.join(ROOT, "config.json")):
        sys.exit("No config.json in %s — pass --root <project dir>." % ROOT)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("Annotating project: %s" % ROOT)
    print("Open  http://127.0.0.1:%d/   (Ctrl-C to stop)" % args.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
