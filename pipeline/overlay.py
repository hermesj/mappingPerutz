#!/usr/bin/env python3
"""Shared helpers for the annotation overlay (used by the annotate-ui tool).

A work's features carry no stored id; a stable id is *derived* from
slug(story)/slug(name) (with -2/-3 for duplicates), computed over the work's
features in load order. The exact same rule lives in engine.js (annSlug /
assignIds) so the overlay keys match what the engine applies at runtime.

The overlay file (`data/<work>-annotations.json`) has the shape:
    { "work": "...", "annotations": { "<id>": { "character": "...", ... } } }
"""
import json
import os
import re


def slugify(s):
    s = (s or "").lower().replace("'", "").replace("’", "").replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def feature_ids(features):
    """List of stable ids, one per feature, in the given order (dedup-aware)."""
    seen, ids = {}, []
    for f in features:
        p = f.get("properties", {})
        base = slugify(p.get("story")) + "/" + slugify(p.get("name"))
        seen[base] = seen.get(base, 0) + 1
        ids.append(base if seen[base] == 1 else "{}-{}".format(base, seen[base]))
    return ids


def normalize_data(work_cfg):
    """A work's `data` -> list of {url, source}; accepts a string or array."""
    entries = work_cfg.get("data")
    if not isinstance(entries, list):
        entries = [entries]
    out = []
    for e in entries:
        out.append({"url": e} if isinstance(e, str) else dict(e))
    return out


def load_work_features(root, work_cfg):
    """Concatenate a work's data files (in order), stamping `source`. Returns the
    feature list in the same order the engine sees before applying the overlay."""
    feats = []
    for e in normalize_data(work_cfg):
        path = os.path.join(root, e["url"])
        if not os.path.exists(path):
            continue
        geo = json.load(open(path, encoding="utf-8"))
        for f in geo.get("features", []):
            if e.get("source") and f["properties"].get("source") is None:
                f["properties"]["source"] = e["source"]
            feats.append(f)
    return feats


def overlay_path(root, work_key, work_cfg):
    rel = work_cfg.get("annotations") or os.path.join("data", work_key + "-annotations.json")
    return os.path.join(root, rel)


def load_overlay(path):
    if os.path.exists(path):
        d = json.load(open(path, encoding="utf-8"))
        return d.get("annotations", {}), d
    return {}, None


def save_overlay(path, work_key, annotations):
    doc = {
        "_comment": ("Editorial annotation overlay for the %s layer — original work by "
                     "J. Hermes, applied on top of the base features at load time (the base "
                     "GeoJSON is never modified). Key = stable feature id; value = a patch of "
                     "fields to merge. Edited via pipeline/annotate-ui/." % work_key),
        "work": work_key,
        "annotations": {k: v for k, v in sorted(annotations.items()) if v},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
