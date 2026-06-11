#!/usr/bin/env python3
"""Re-import an edited uMap export (KML or GeoJSON) back into a *-source.json.

Matches each incoming feature to an existing source entry by (episode, name)
and writes the edited geometry back:
  - Point      -> the place's lat / lon
  - LineString -> the route's coords ([lon,lat] list)

Names and episode numbers are preserved from the source; only geometry is
updated, so glosses/quotes/times stay intact. After running, regenerate the
GeoJSON:  python3 geocode_source.py <source.json> <out.geojson>

Usage:
    python3 import_umap.py <edited.kml|edited.geojson> <source.json>
"""
import json
import re
import sys
import xml.etree.ElementTree as ET

KML_NS = {"k": "http://www.opengis.net/kml/2.2"}


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def parse_kml(path):
    """Yield dicts: {name, episode, kind, coords:[[lon,lat],...]} per Placemark."""
    root = ET.parse(path).getroot()
    for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
        name = pm.findtext("k:name", default="", namespaces=KML_NS)
        ep = None
        for data in pm.iter("{http://www.opengis.net/kml/2.2}Data"):
            key = data.get("name")
            val = data.findtext("k:value", namespaces=KML_NS)
            if key in ("episode", "group") and val not in (None, ""):
                try:
                    ep = int(val)
                except ValueError:
                    pass
        pt = pm.find(".//k:Point/k:coordinates", KML_NS)
        ls = pm.find(".//k:LineString/k:coordinates", KML_NS)
        raw = (pt.text if pt is not None else ls.text if ls is not None else "")
        coords = []
        for chunk in (raw or "").replace("\n", " ").split():
            parts = chunk.split(",")
            if len(parts) >= 2:
                coords.append([round(float(parts[0]), 6), round(float(parts[1]), 6)])
        if coords:
            yield {"name": name, "episode": ep,
                   "kind": "route" if ls is not None else "place", "coords": coords}


def parse_geojson(path):
    geo = json.load(open(path, encoding="utf-8"))
    for f in geo.get("features", []):
        p = f.get("properties", {})
        g = f.get("geometry", {})
        ep = p.get("episode", p.get("group"))
        try:
            ep = int(ep)
        except (TypeError, ValueError):
            ep = None
        if g.get("type") == "Point":
            yield {"name": p.get("name", ""), "episode": ep, "kind": "place",
                   "coords": [g["coordinates"][:2]]}
        elif g.get("type") == "LineString":
            yield {"name": p.get("name", ""), "episode": ep, "kind": "route",
                   "coords": [c[:2] for c in g["coordinates"]]}


def main(edited, src_path):
    incoming = list(parse_geojson(edited) if edited.lower().endswith((".geojson", ".json"))
                    else parse_kml(edited))
    src = json.load(open(src_path, encoding="utf-8"))
    places = src.get("places", [])
    routes = src.get("routes", [])

    def find(entries, ep, name):
        # exact (episode, name); fall back to name-only if unambiguous
        hits = [e for e in entries if norm(e.get("name")) == norm(name)]
        if ep is not None:
            ep_hits = [e for e in hits if e.get("episode") == ep]
            if ep_hits:
                return ep_hits[0]
        return hits[0] if len(hits) == 1 else None

    updated, ambiguous = 0, []
    for feat in incoming:
        if feat["kind"] == "route":
            r = find(routes, feat["episode"], feat["name"])
            if r:
                r["coords"] = feat["coords"]
                updated += 1
            else:
                ambiguous.append(("route", feat["name"], feat["episode"]))
        else:
            pl = find(places, feat["episode"], feat["name"])
            if pl:
                lon, lat = feat["coords"][0]
                pl["lat"], pl["lon"] = lat, lon
                updated += 1
            else:
                ambiguous.append(("place", feat["name"], feat["episode"]))

    json.dump(src, open(src_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Updated {updated} of {len(incoming)} incoming features in {src_path}")
    if ambiguous:
        print(f"Unmatched/ambiguous ({len(ambiguous)}) — check names/episodes:")
        for kind, name, ep in ambiguous:
            print(f"  [{kind}] {name!r} (episode {ep})")
    print("Now regenerate: python3 geocode_source.py", src_path, "<out.geojson>")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: import_umap.py <edited.kml|edited.geojson> <source.json>")
    main(sys.argv[1], sys.argv[2])
