#!/usr/bin/env python3
"""Export a mappingJoyce GeoJSON layer to KML for editing in uMap.

Groups features into one <Folder> per episode/chapter (in order), colours each
folder, writes a human-readable <description>, and stashes the structured
fields in <ExtendedData> so a later re-import can recover them. Points and
LineStrings (routes) are both supported.

Usage:
    python3 geojson_to_kml.py ../data/ulysses.geojson ../data/ulysses.kml
"""
import json
import sys
import xml.sax.saxutils as su

# Episode/chapter colours (must match the group colours in config.json).
COLORS = [
    "#c9a227", "#7b4f2a", "#2e7d32", "#e07b16", "#4e342e", "#2b2b2b",
    "#c0392b", "#7e1620", "#5d6d7e", "#6a5acd", "#ff7f50", "#1b5e20",
    "#7f9bb3", "#bdc3c7", "#8e44ad", "#607d8b", "#2c3e50", "#6d4c41",
]


def kml_color(hex_rgb, alpha="ff"):
    """#rrggbb -> KML aabbggrr."""
    h = hex_rgb.lstrip("#")
    return alpha + h[4:6] + h[2:4] + h[0:2]


def esc(s):
    return su.escape(str(s if s is not None else ""))


def coords_str(geom):
    if geom["type"] == "Point":
        lon, lat = geom["coordinates"][:2]
        return f"{lon},{lat},0"
    return " ".join(f"{c[0]},{c[1]},0" for c in geom["coordinates"])


def extended_data(props):
    keep = ["work", "group", "episode", "kind", "time", "gloss", "quote", "ref", "name"]
    rows = []
    for k in keep:
        if props.get(k) is not None:
            rows.append(f'<Data name="{k}"><value>{esc(props[k])}</value></Data>')
    return "<ExtendedData>" + "".join(rows) + "</ExtendedData>"


def description(props):
    bits = []
    if props.get("time"):
        bits.append(f"<b>{esc(props['time'])}</b>")
    if props.get("gloss"):
        bits.append(esc(props["gloss"]))
    if props.get("quote"):
        q = esc(props["quote"])
        if props.get("ref"):
            q += f" ({esc(props['ref'])})"
        bits.append(f"<i>{q}</i>")
    return "<![CDATA[" + "<br>".join(bits) + "]]>"


def placemark(f):
    p = f.properties if hasattr(f, "properties") else f["properties"]
    g = f["geometry"]
    name = esc(p.get("name", ""))
    geom = (f'<Point><coordinates>{coords_str(g)}</coordinates></Point>'
            if g["type"] == "Point"
            else f'<LineString><tessellate>1</tessellate>'
                 f'<coordinates>{coords_str(g)}</coordinates></LineString>')
    return (f"<Placemark><name>{name}</name>"
            f"<description>{description(p)}</description>"
            f"<styleUrl>#ep{p.get('group', p.get('episode', 0))}</styleUrl>"
            f"{extended_data(p)}{geom}</Placemark>")


def main(src, out):
    geo = json.load(open(src, encoding="utf-8"))
    feats = geo["features"]

    # Bucket by group number, remember each group's title.
    groups = {}
    titles = {}
    for f in feats:
        p = f["properties"]
        gn = p.get("group", p.get("episode", 0))
        groups.setdefault(gn, []).append(f)
        titles.setdefault(gn, p.get("story", str(gn)))

    styles = []
    for i, c in enumerate(COLORS, start=1):
        kc = kml_color(c)
        styles.append(
            f'<Style id="ep{i}">'
            f'<IconStyle><color>{kc}</color>'
            f'<Icon><href>https://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>'
            f'</IconStyle>'
            f'<LineStyle><color>{kc}</color><width>3</width></LineStyle>'
            f"</Style>")

    folders = []
    for gn in sorted(groups):
        title = f"{gn}. {titles[gn]}" if isinstance(gn, int) else titles[gn]
        pms = "".join(placemark(f) for f in groups[gn])
        folders.append(f"<Folder><name>{esc(title)}</name>{pms}</Folder>")

    doc = geo.get("metadata", {}).get("title", "Mapping Joyce")
    kml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"<name>{esc(doc)}</name>"
        + "".join(styles) + "".join(folders) +
        "</Document></kml>\n")
    open(out, "w", encoding="utf-8").write(kml)
    npts = sum(1 for f in feats if f["geometry"]["type"] == "Point")
    nlin = sum(1 for f in feats if f["geometry"]["type"] == "LineString")
    print(f"Wrote {len(feats)} placemarks ({npts} points, {nlin} routes) "
          f"in {len(folders)} folders -> {out}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: geojson_to_kml.py <in.geojson> <out.kml>")
    main(sys.argv[1], sys.argv[2])
