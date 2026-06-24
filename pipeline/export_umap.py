#!/usr/bin/env python3
"""Export a litmap project's points + routes as a uMap-importable GeoJSON.

One FeatureCollection (points + lines). Each feature carries:
  - a stable `id` = annSlug(story)/annSlug(name) (same scheme as the overlay),
  - a markdown `description` (chapter · confidence, gloss, quote),
  - `kapitel` + `confidence` props and `_umap_options` with the chapter colour,
so it round-trips via import_umap.py (which matches incoming features by name).

The on-map state is reproduced faithfully: the base GeoJSON layers are read in
config `data` order and the annotation overlay is merged in (geometry + field
patches), exactly as engine.js does at load time.

Usage:
    python3 export_umap.py [--root <project>] [-o exports/<name>.geojson]
"""
import argparse
import json
import os
import re


def ann_slug(s):
    s = "" if s is None else str(s)
    s = s.lower()
    s = re.sub(r"['’.]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)


def assign_ids(features):
    """Derive the overlay id for each feature (annSlug(story)/annSlug(name),
    with -2/-3 suffixes for duplicates) — identical to overlay.py / engine.js."""
    seen, ids = {}, []
    for f in features:
        p = f.get("properties", {})
        b = ann_slug(p.get("story")) + "/" + ann_slug(p.get("name"))
        seen[b] = seen.get(b, 0) + 1
        ids.append(b if seen[b] == 1 else b + "-" + str(seen[b]))
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..")))
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()
    root = args.root
    cfg = json.load(open(os.path.join(root, "config.json"), encoding="utf-8"))
    lang = (cfg.get("site") or {}).get("defaultLang", "de")
    wkey = next(iter(cfg["works"]))
    w = cfg["works"][wkey]

    groups = {}
    for g in w.get("groups", []):
        label = g.get(lang) if lang != "en" else g.get("key")
        groups[g.get("key")] = {"label": label or g.get("key"),
                                "color": g.get("color") or "#777777"}
    conf_levels = (w.get("confidence") or {}).get("levels") or {}

    def conf_label(c):
        lo = conf_levels.get(c)
        if isinstance(lo, dict):
            return lo.get(lang) or lo.get("en") or c
        return lo or c

    # base layers in config order, concatenated (as the engine does)
    data = w["data"] if isinstance(w["data"], list) else [w["data"]]
    feats = []
    for e in data:
        url = e if isinstance(e, str) else e.get("url")
        path = os.path.join(root, url)
        if os.path.exists(path):
            feats += json.load(open(path, encoding="utf-8")).get("features", [])

    # merge the annotation overlay (geometry + field patches) by derived id
    ids = assign_ids(feats)
    ov_path = os.path.join(root, "data", wkey + "-annotations.json")
    if os.path.exists(ov_path):
        o = json.load(open(ov_path, encoding="utf-8"))
        ann = o.get("annotations", o)
        for f, fid in zip(feats, ids):
            patch = ann.get(fid)
            if not patch:
                continue
            for k, v in patch.items():
                if k not in ("lat", "lon", "coords"):
                    f["properties"][k] = v
            if patch.get("coords"):
                f["geometry"] = {"type": "LineString", "coordinates": patch["coords"]}
            elif patch.get("lat") is not None and patch.get("lon") is not None:
                f["geometry"] = {"type": "Point", "coordinates": [patch["lon"], patch["lat"]]}

    out_feats = []
    for f, fid in zip(feats, ids):
        p = f["properties"]
        g = groups.get(p.get("story"), {"label": p.get("story"), "color": "#777777"})
        is_line = f["geometry"]["type"] == "LineString"
        header = "**" + str(g["label"])
        if p.get("confidence"):
            header += " · " + conf_label(p["confidence"])
        header += "**"
        parts = [header]
        if p.get("gloss"):
            parts.append(p["gloss"])
        if p.get("quote"):
            parts.append("> " + p["quote"])
        props = {"id": fid, "name": p.get("name"), "description": "\n\n".join(parts),
                 "kapitel": g["label"]}
        if p.get("confidence"):
            props["confidence"] = p["confidence"]
        props["_umap_options"] = {"color": g["color"], "weight": 5 if is_line else 1}
        out_feats.append({"type": "Feature", "id": fid,
                          "geometry": f["geometry"], "properties": props})

    map_name = (cfg.get("site") or {}).get("title") or (w.get("label") or {}).get(lang) or wkey
    fc = {"type": "FeatureCollection",
          "_umap_options": {"name": map_name},
          "features": out_feats}
    out = args.out or os.path.join(root, "exports", wkey + "-umap.geojson")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(fc, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    npt = sum(1 for f in out_feats if f["geometry"]["type"] == "Point")
    dups = len(out_feats) - len({f["properties"]["name"] for f in out_feats})
    print("Wrote %d features (%d points, %d lines) -> %s"
          % (len(out_feats), npt, len(out_feats) - npt, out))
    if dups:
        print("  WARNING: %d duplicate names — round-trip by name may be ambiguous" % dups)


if __name__ == "__main__":
    main()
