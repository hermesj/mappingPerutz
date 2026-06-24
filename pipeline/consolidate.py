#!/usr/bin/env python3
"""Consolidate a litmap project into a single, key-based source of truth.

End-of-session housekeeping (no LLM needed): folds the working layers back into
the hand-curated main source, so everything lives in ONE file.

  1. regenerates the layers, then BAKES the annotation overlay
     (data/<work>-annotations.json) into the matching source entries — field
     edits, renames (`name`), group moves (`story`) and geometry — and empties
     the overlay;
  2. MERGES the annotator's own-layer (data/<work>-own-source.json) into the
     main source (data/<work>-source.json), normalising every `group` reference
     to its config key (so the project becomes uniformly key-based);
  3. drops the own GeoJSON from config.json `data` and deletes the redundant
     own files;
  4. regenerates data/<work>.geojson.

Afterwards the annotator simply re-creates a fresh own-layer the next time you
add objects. Run `python3 pipeline/check.py` afterwards to confirm.

Usage:
    python3 pipeline/consolidate.py [--root <project>] [--dry-run]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import geocode_source as gs   # noqa: E402


def ann_slug(s):
    s = "" if s is None else str(s)
    s = s.lower()
    s = re.sub(r"['’.]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)


def assign_ids(features):
    """Derive each feature's overlay id (annSlug(story)/annSlug(name), -2/-3 for
    duplicates) — identical to overlay.py / engine.js."""
    seen, ids = {}, []
    for f in features:
        p = f.get("properties", {})
        b = ann_slug(p.get("story")) + "/" + ann_slug(p.get("name"))
        seen[b] = seen.get(b, 0) + 1
        ids.append(b if seen[b] == 1 else b + "-" + str(seen[b]))
    return ids


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def data_urls(w):
    d = w["data"] if isinstance(w["data"], list) else [w["data"]]
    return [e if isinstance(e, str) else e.get("url") for e in d]


def find_entry(src, name):
    if not src:
        return None
    for coll in ("places", "routes"):
        for e in src.get(coll, []):
            if e.get("name") == name:
                return e
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.abspath(os.path.join(HERE, "..")))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = args.root
    cfg_path = os.path.join(root, "config.json")
    cfg = load(cfg_path)
    wkey = next(iter(cfg["works"]))
    w = cfg["works"][wkey]

    def dp(name):
        return os.path.join(root, "data", name)

    src_path, own_path = dp(wkey + "-source.json"), dp(wkey + "-own-source.json")
    ann_path = dp(wkey + "-annotations.json")
    main_geo, own_geo = dp(wkey + ".geojson"), dp(wkey + "-own.geojson")
    region = w.get("regionBBox") or (cfg.get("view") or {}).get("regionBBox")

    main_src = load(src_path)
    own_src = load(own_path) if os.path.exists(own_path) else None

    # config key list + positional int->key fallback (the annotator already
    # writes keys; this only rescues any legacy numeric refs).
    keys = [g.get("key") for g in w.get("groups", [])]
    num2key = {i + 1: k for i, k in enumerate(keys)}

    def to_key(g):
        if isinstance(g, list):
            return [to_key(x) for x in g]
        if isinstance(g, int):
            return num2key.get(g, str(g))
        return g

    # 0. refresh rendered layers so derived ids line up with the overlay keys
    if not args.dry_run:
        gs.main(src_path, main_geo, region)
        if own_src is not None:
            gs.main(own_path, own_geo, region)

    # 1. bake the overlay into the source entries
    baked, skipped = 0, []
    if os.path.exists(ann_path):
        o = load(ann_path)
        ann = o.get("annotations", o) if isinstance(o, dict) else {}
        feats, origin = [], []
        for url in data_urls(w):
            p = os.path.join(root, url)
            if os.path.exists(p):
                fs = load(p).get("features", [])
                feats += fs
                origin += [("own" if url.endswith("-own.geojson") else "main")] * len(fs)
        idmap = {fid: (f["properties"].get("name"), origin[i])
                 for i, (f, fid) in enumerate(zip(feats, assign_ids(feats)))}
        for fid, patch in ann.items():
            name, where = idmap.get(fid, (None, None))
            e = (find_entry(main_src if where == "main" else own_src, name)
                 or find_entry(main_src, name) or find_entry(own_src, name))
            if not e:
                skipped.append(fid)
                continue
            for k, v in patch.items():
                if k in ("lat", "lon", "coords"):
                    continue
                # an annotator group-move stores the target as `story` → `group`
                e["group" if k == "story" else k] = v
            if patch.get("coords"):
                e["coords"] = patch["coords"]
            elif patch.get("lat") is not None and patch.get("lon") is not None:
                e["lat"] = round(float(patch["lat"]), 6)
                e["lon"] = round(float(patch["lon"]), 6)
            baked += 1

    # 2. normalise every group ref to a key; merge own-layer into the main source
    own_count = 0
    for coll in ("places", "routes"):
        for e in main_src.get(coll, []):
            if "group" in e:
                e["group"] = to_key(e["group"])
        if own_src:
            for e in own_src.get(coll, []):
                if "group" in e:
                    e["group"] = to_key(e["group"])
            own_count += len(own_src.get(coll, []))
            main_src.setdefault(coll, []).extend(own_src.get(coll, []))
    main_src.pop("groups", None)   # fully key-based → the n->key list is obsolete

    # 3. config: drop the own GeoJSON from `data`
    new_data = [u for u in data_urls(w) if not u.endswith("-own.geojson")]

    if args.dry_run:
        print("DRY RUN: would bake %d patch(es)%s, merge %d own entr(ies), "
              "set data=%s, delete own files."
              % (baked, (" (%d unmatched)" % len(skipped)) if skipped else "",
                 own_count, new_data))
        return

    dump(src_path, main_src)
    if os.path.exists(ann_path):
        o = load(ann_path)
        o = o if isinstance(o, dict) else {}
        o["annotations"] = {}
        dump(ann_path, o)
    w["data"] = new_data
    dump(cfg_path, cfg)
    for p in (own_path, own_geo):
        if os.path.exists(p):
            os.remove(p)
    gs.main(src_path, main_geo, region)

    print("Consolidated '%s':" % wkey)
    print("  baked %d overlay patch(es)%s" % (
        baked, (", %d unmatched/skipped" % len(skipped)) if skipped else ""))
    print("  merged %d own-layer entr(ies) into the main source" % own_count)
    print("  config data -> %s ; deleted own files ; regenerated %s"
          % (new_data, os.path.basename(main_geo)))
    print("  now run:  python3 pipeline/check.py")


if __name__ == "__main__":
    main()
