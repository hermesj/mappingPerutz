# pipeline/

Data-preparation scripts (plain Python 3, standard library; routing also uses
`curl`). They turn hand-curated sources into the `data/*.geojson` the engine
renders, and support round-trip editing in uMap.

## Generic (reusable for any project)

| Script | Purpose |
|--------|---------|
| `geocode_source.py` | source JSON → GeoJSON. Geocodes places (Nominatim) and draws routes between endpoints — **driving** via OSRM, **foot** via BRouter, chosen per route `mode`. Caches `lat`/`lon` and route `coords` back into the source so nothing is re-fetched. |
| `geojson_to_kml.py` | GeoJSON → KML (episode folders, colours, ExtendedData) for editing in uMap. |
| `import_umap.py` | edited KML/GeoJSON → back into the source (geometry only; matches by group + name). |

### Parametrisation (config / args)

- **Gazetteer focus** — bias ambiguous geocodes to a region:
  `python3 geocode_source.py src.json out.geojson --region=S,W,N,E`
  (Nominatim viewbox + bounded; e.g. Dublin `--region=53.0,-6.7,53.7,-6.0`).
- **Routing mode** — per route in the source: `"mode": "driving"` (default,
  OSRM) or `"mode": "foot"` (BRouter). Rail/other bespoke paths: paste a
  `coords` array directly (then it is used as-is).
- **Routing services** — endpoints are the `OSRM` / `BROUTER` constants at the
  top of `geocode_source.py`.

Typical loop:

```bash
python3 geocode_source.py ../data/<work>-source.json ../data/<work>.geojson
python3 geojson_to_kml.py ../data/<work>.geojson ../data/<work>.kml   # → edit in uMap
python3 import_umap.py edited.kml ../data/<work>-source.json          # ← pull edits back
python3 geocode_source.py ../data/<work>-source.json ../data/<work>.geojson
```

## Example-specific

- `example-dubliners/kml_to_geojson.py` (+ `source-doc.kml`) — converts the
  Mapping Dubliners Project KMZ into `data/dubliners.geojson`. Tied to that one
  source format; kept as the worked example for the flagship project, not part
  of the generic pipeline.

## Legacy

- `legacy/geocode_ulysses.py` — the original Ulysses-only geocoder, superseded
  by the generic `geocode_source.py`. Kept for reference only.
