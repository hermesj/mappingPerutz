#!/usr/bin/env python3
"""Geocode a hand-curated place source into a GeoJSON layer (generic).

Works for any single-work source file with this shape:

    {
      "work": "Portrait",
      "groups":   [ { "n": 1, "en": "Chapter 1", "de": "Kapitel 1" }, ... ],
      "places":   [ { "group": 1, "name": "...", "geocode": "...",
                      "gloss": "...", "quote": "...", "ref": "..." }, ... ],
      "routes":   [ { "group": 6, "name": "...", "from": [lat,lon],
                      "to": [lat,lon], "mode": "driving"|"foot" }, ... ]
    }

The group-list key may be "groups", "chapters" or "episodes"; the per-place
group key may be "group" or "episode". Points are geocoded via
OpenStreetMap/Nominatim (<=1 req/s); routes are drawn between their endpoints
via OSRM (driving) or BRouter (foot), per the route's `mode`. Results are
cached back into the source (lat/lon for places, coords for routes) so nothing
is re-fetched. Output matches the schema the engine reads (feature `story` =
the group's English title).

Usage:
    python3 geocode_source.py <source.json> [out.geojson] [--region=S,W,N,E]

  --region biases geocoding to a bounding box [South,West,North,East]
  (Nominatim viewbox + bounded), useful to keep ambiguous street names in the
  right city.
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/driving/"
BROUTER = "https://brouter.de/brouter"
UA = "litmap/1.0 (literary-geography mapping; OpenStreetMap geocoding)"


def geocode(query, region=None):
    p = {"q": query, "format": "json", "limit": 1}
    if region:  # [S, W, N, E] -> Nominatim viewbox "W,N,E,S" + bounded
        s, w, n, e = region
        p["viewbox"] = f"{w},{n},{e},{s}"
        p["bounded"] = 1
    req = urllib.request.Request(NOMINATIM + "?" + urllib.parse.urlencode(p),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if not data:
        return None
    return round(float(data[0]["lat"]), 6), round(float(data[0]["lon"]), 6)


def _curl_json(url):
    out = subprocess.run(["curl", "-s", "-m", "30", "-A", UA, url],
                         capture_output=True, text=True, timeout=40)
    return json.loads(out.stdout)


def route(frm, to, mode="driving"):
    """[lon,lat] path between two [lat,lon] endpoints.

    mode "foot" → BRouter (hiking, avoids motorways); otherwise OSRM driving.
    curl is used rather than urllib (the public OSRM/BRouter TLS handshakes
    fail under Python's ssl here, while curl negotiates them fine).
    """
    if mode == "foot":
        ll = f"{frm[1]},{frm[0]}|{to[1]},{to[0]}"
        url = f"{BROUTER}?lonlats={ll}&profile=hiking-beta&alternativeidx=0&format=geojson"
        data = _curl_json(url)
        if data.get("type") != "FeatureCollection" or not data.get("features"):
            return None
        line = data["features"][0]["geometry"]["coordinates"]
    else:
        pair = "{},{};{},{}".format(frm[1], frm[0], to[1], to[0])
        data = _curl_json(OSRM + pair + "?overview=full&geometries=geojson")
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        line = data["routes"][0]["geometry"]["coordinates"]
    return [[round(c[0], 6), round(c[1], 6)] for c in line]


def main(src_path, out_path, region=None):
    with open(src_path, encoding="utf-8") as f:
        src = json.load(f)

    groups = src.get("groups") or src.get("chapters") or src.get("episodes") or []
    by_n = {g["n"]: g for g in groups}
    work = src.get("work", "")
    prov = src.get("source")          # optional provenance tag → feature.source
    features = []
    changed = False

    for place in src["places"]:
        lat, lon = place.get("lat"), place.get("lon")
        if lat is None or lon is None:
            q = place.get("geocode") or place["name"]
            print(f"  geocoding: {q!r} ...", end=" ", flush=True)
            try:
                res = geocode(q, region)
            except Exception as e:
                print(f"FAILED ({e})")
                continue
            time.sleep(1.1)  # Nominatim courtesy rate limit
            if not res:
                print("no match — fix the 'geocode' query")
                continue
            lat, lon = res
            place["lat"], place["lon"] = lat, lon
            changed = True
            print(f"{lat}, {lon}")

        gn = place.get("group", place.get("episode"))
        # `group` may be a single chapter (int) or a list of chapters a place is
        # a scene of (primary first). The marker lives in the primary group; the
        # engine reads `stories` to list it under each additional group too.
        primary = gn[0] if isinstance(gn, list) else gn
        g = by_n.get(primary, {})
        props = {
            "group": gn,
            "story": g.get("en", str(primary)),
            "name": place["name"],
            "kind": place.get("kind", "place"),
        }
        if isinstance(gn, list):
            props["stories"] = [by_n.get(n, {}).get("en", str(n)) for n in gn]
        for k in ("character", "time", "gloss", "quote", "ref", "srcText", "essay", "essaySource", "confidence"):
            if place.get(k):
                props[k] = place[k]
        if "verified" in place:           # boolean → presence check, not truthiness
            props["verified"] = place["verified"]
        if place.get("source", prov):
            props["source"] = place.get("source", prov)
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })

    # Routes (LineStrings): drawn between [lat,lon] endpoints, cached in coords.
    for r in src.get("routes", []):
        coords = r.get("coords")
        if not coords:
            mode = r.get("mode", "driving")
            print(f"  routing ({mode}): {r['name']!r} ...", end=" ", flush=True)
            try:
                coords = route(r["from"], r["to"], mode)
            except Exception as e:
                print(f"FAILED ({e})")
                continue
            time.sleep(1.1)  # courtesy rate limit
            if not coords:
                print("no route — check the endpoints")
                continue
            r["coords"] = coords
            changed = True
            print(f"{len(coords)} points")

        gn = r.get("group", r.get("episode"))
        primary = gn[0] if isinstance(gn, list) else gn
        g = by_n.get(primary, {})
        props = {
            "group": gn, "story": g.get("en", str(primary)),
            "name": r["name"], "kind": "route",
        }
        if isinstance(gn, list):
            props["stories"] = [by_n.get(n, {}).get("en", str(n)) for n in gn]
        for k in ("character", "time", "gloss", "quote", "ref", "srcText", "essay", "essaySource", "confidence"):
            if r.get(k):
                props[k] = r[k]
        if "verified" in r:
            props["verified"] = r["verified"]
        if r.get("source", prov):
            props["source"] = r.get("source", prov)
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "LineString", "coordinates": coords},
        })

    if changed:
        with open(src_path, "w", encoding="utf-8") as f:
            json.dump(src, f, ensure_ascii=False, indent=2)

    fc = {
        "type": "FeatureCollection",
        "metadata": {
            "title": work,
            "note": "Dataset compiled from a public-domain text. Coordinates via "
                    "OpenStreetMap/Nominatim; routes via OSRM (driving) / BRouter (foot).",
            "license": "CC BY-NC 4.0",
        },
        "features": features,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=1)
    ngroups = len({x["properties"]["story"] for x in features})
    print(f"\nWrote {len(features)} features across {ngroups} groups -> {out_path}")


if __name__ == "__main__":
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    region = None
    for a in sys.argv[1:]:
        if a.startswith("--region="):
            region = [float(x) for x in a.split("=", 1)[1].split(",")]
    if not pos:
        sys.exit("usage: geocode_source.py <source.json> [out.geojson] [--region=S,W,N,E]")
    src = pos[0]
    out = pos[1] if len(pos) > 1 else os.path.splitext(src)[0].replace("-source", "") + ".geojson"
    main(src, out, region)
