#!/usr/bin/env python3
"""Project lint — validate data, overlays and wiring before committing.

Catches the failure modes that are otherwise silent:

  * a feature whose `story` matches no config group  → it never renders
  * an annotation key that matches no feature id     → the annotation is lost
  * an annotations file on disk that isn't wired into config (never applied)
  * duplicate derived ids (order-dependent -2/-3 suffixes — fragile keys)
  * own-source entries missing from the rendered own GeoJSON (stale rebuild)
  * a work with an `essay` popup config but no feature carrying an essay URL
    (e.g. `add_essays.py` was forgotten after a Dubliners rebuild)
  * a work with `sourceText` whose quotes lost every `srcText`
    (e.g. `add_srctext.py` was forgotten after a Dubliners rebuild)

Usage:
    python3 pipeline/check.py [--root <project>] [--mirror <template repo>]

`--mirror` additionally diffs the shared engine/pipeline artefacts against a
template clone (e.g. ../litmap) and reports drift. Exit code 1 on errors
(warnings don't fail).
"""
import argparse
import filecmp
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import overlay as ov   # noqa: E402

ERRORS, WARNINGS = [], []


def err(msg):
    ERRORS.append(msg)
    print("  ERROR   " + msg)


def warn(msg):
    WARNINGS.append(msg)
    print("  warn    " + msg)


def ok(msg):
    print("  ok      " + msg)


def check_work(root, key, w):
    print("· %s" % key)
    group_keys = {g.get("key") for g in w.get("groups", [])}

    # data files exist + parse; collect features
    feats = []
    for e in ov.normalize_data(w):
        path = os.path.join(root, e["url"])
        if not os.path.exists(path):
            err("data file missing: %s" % e["url"])
            continue
        try:
            geo = json.load(open(path, encoding="utf-8"))
        except Exception as ex:
            err("data file unreadable: %s (%s)" % (e["url"], ex))
            continue
        for f in geo.get("features", []):
            feats.append(f)
    if not feats:
        warn("no features")
        return

    # required fields + story↔group match (a mismatched story never renders)
    for f in feats:
        p = f.get("properties", {})
        name = p.get("name") or "<unnamed>"
        if not p.get("name"):
            err("feature without name (story %r)" % p.get("story"))
        if not p.get("story"):
            err("feature %r has no story" % name)
        elif p["story"] not in group_keys:
            err("feature %r: story %r matches no config group → invisible" % (name, p["story"]))
        # A multi-chapter place also lists itself under each key in `stories`;
        # any that matches no config group would silently fail to render there.
        for s in p.get("stories", []):
            if s not in group_keys:
                err("feature %r: stories entry %r matches no config group → invisible" % (name, s))
        if p.get("confidence") and p["confidence"] not in ("high", "medium", "low"):
            warn("feature %r: confidence %r not in high|medium|low → halo won't render" % (name, p["confidence"]))
        g = f.get("geometry") or {}
        if g.get("type") not in ("Point", "LineString"):
            err("feature %r: unsupported geometry %r" % (name, g.get("type")))
    ok("%d features, stories match config groups" % len(feats))

    # duplicate derived ids (fragile overlay keys)
    ids = ov.feature_ids(feats)
    dups = [i for i, c in Counter(
        i[:-2] if i.endswith(("-2", "-3", "-4")) else i for i in ids).items() if c > 1]
    if dups:
        warn("duplicate-name ids (order-dependent -N suffixes): %s" % ", ".join(sorted(dups)))

    # annotations: wiring + orphans
    ann_cfg = w.get("annotations")
    default_path = os.path.join(root, "data", key + "-annotations.json")
    if not ann_cfg and os.path.exists(default_path):
        err("data/%s-annotations.json exists but works.%s.annotations is not set "
            "→ the map never applies it" % (key, key))
    if ann_cfg:
        path = os.path.join(root, ann_cfg)
        if not os.path.exists(path):
            warn("annotations wired (%s) but file missing — fine until first save" % ann_cfg)
        else:
            ann, _ = ov.load_overlay(path)
            idset = set(ids)
            orphans = [k for k in ann if k not in idset]
            for o in orphans:
                err("orphaned annotation %r — no feature derives this id "
                    "(renamed in the source?)" % o)
            for k, patch in ann.items():
                if "seq" in patch and not isinstance(patch["seq"], int):
                    err("annotation %r: seq must be an integer" % k)
            if not orphans:
                ok("%d annotations, all match a feature" % len(ann))

    # own-source ↔ rendered own.geojson consistency
    own_src = os.path.join(root, "data", key + "-own-source.json")
    if os.path.exists(own_src):
        src = json.load(open(own_src, encoding="utf-8"))
        want = [p["name"] for p in src.get("places", [])] + \
               [r["name"] for r in src.get("routes", [])]
        have = set()
        for e in ov.normalize_data(w):
            if e["url"].endswith("-own.geojson"):
                p = os.path.join(root, e["url"])
                if os.path.exists(p):
                    have = {f["properties"].get("name")
                            for f in json.load(open(p, encoding="utf-8")).get("features", [])}
        missing = [n for n in want if n not in have]
        if missing:
            err("own-source entries not in the rendered own layer (re-run "
                "geocode_source): %s" % ", ".join(missing))
        elif want:
            ok("own additions rendered (%d)" % len(want))

    # forgotten enrichment steps after a rebuild
    n_quotes = sum(1 for f in feats if f["properties"].get("quote"))
    if w.get("essay") and not any(f["properties"].get("essay") for f in feats):
        err("works.%s has an `essay` popup config but NO feature carries an essay "
            "URL — forgot add_essays.py after a rebuild?" % key)
    if w.get("sourceText") and n_quotes >= 20 and \
            not any(f["properties"].get("srcText") for f in feats):
        warn("%d quotes but zero srcText — forgot add_srctext.py after a rebuild?" % n_quotes)


def check_mirror(root, mirror):
    print("· mirror drift (%s)" % mirror)
    shared = ["engine/engine.js", "engine/engine.css",
              "pipeline/geocode_source.py", "pipeline/overlay.py", "pipeline/check.py",
              "pipeline/annotate-ui/serve.py", "pipeline/annotate-ui/app.js",
              "pipeline/annotate-ui/index.html", "docs/ARCHITECTURE.md"]
    for rel in shared:
        a, b = os.path.join(root, rel), os.path.join(mirror, rel)
        if not os.path.exists(b):
            warn("not in mirror: %s" % rel)
        elif not os.path.exists(a):
            warn("not in project: %s" % rel)
        elif not filecmp.cmp(a, b, shallow=False):
            warn("DRIFT: %s differs from the mirror" % rel)
    if not WARNINGS:
        ok("no drift")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.abspath(os.path.join(HERE, "..")))
    ap.add_argument("--mirror", help="template repo to diff shared artefacts against")
    args = ap.parse_args()
    root = args.root
    cfg_path = os.path.join(root, "config.json")
    if not os.path.exists(cfg_path):
        sys.exit("no config.json in %s" % root)
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    for key, w in cfg.get("works", {}).items():
        check_work(root, key, w)
    if args.mirror:
        check_mirror(root, args.mirror)
    print()
    if ERRORS:
        print("FAILED: %d error(s), %d warning(s)" % (len(ERRORS), len(WARNINGS)))
        sys.exit(1)
    print("PASSED: 0 errors, %d warning(s)" % len(WARNINGS))


if __name__ == "__main__":
    main()
