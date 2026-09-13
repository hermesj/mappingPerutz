# pipeline/

Data-preparation and editing tools (plain Python 3, standard library; routing
also uses `curl`). They turn hand-curated `data/<work>-source.json` files into
the `data/<work>.geojson` the engine renders, keep an editorial overlay, and
support round-trip editing in uMap. Nothing here is deployed.

The `*-source.json` files are the **single source of truth**. Each place caches
its `lat`/`lon` and each route its `coords` once resolved, so re-running the
geocoder is idempotent — it re-emits the same GeoJSON without re-fetching.

## Scripts

| Script | Purpose |
|--------|---------|
| `geocode_source.py` | source JSON → GeoJSON. Geocodes places (Nominatim) and draws routes between endpoints — **driving** via OSRM, **foot** via BRouter, chosen per route `mode`. Caches `lat`/`lon` and route `coords` back into the source. Emits exactly the engine's data contract (`PROP_KEYS`); `metadata` (title/note/licence) comes from the source file's own `metadata` block. |
| `check.py` | **project lint** — run before committing. Catches silent failures: features whose `story` matches no group (invisible), orphaned annotation keys, unresolved person refs, duplicate ids, stale own layers, forgotten enrichment steps; `--mirror ../litmap` also reports drift of the shared artefacts. |
| `overlay.py` | shared helpers (stable feature ids, overlay load/save, data-file normalisation) used by `check.py`, `annotate-ui/` and `consolidate.py`. |
| `annotate-ui/` | local stdlib web app to edit/annotate features, create new ones, manage groups and ordering — see its README. |
| `consolidate.py` | end-of-session step: bakes the overlay into the source, merges the own-layer, normalises group refs to config keys, re-renders — for every work that has a `-source.json` (`--work` to pick one, `--dry-run` to preview). |
| `export_umap.py` | one `exports/<work>-umap.geojson` (stable ids, group colours, markdown popups, overlay merged in) to reshape points/lines in [uMap](https://umap.openstreetmap.fr/). |
| `import_umap.py` | edited KML/GeoJSON from uMap → geometry written back into the source (matched by name). |
| `geojson_to_kml.py` | GeoJSON → KML (group folders, colours, ExtendedData) — the older uMap/Google-Earth export path. |

## Parametrisation (config / args)

- **Gazetteer focus** — bias ambiguous geocodes to a region:
  `python3 geocode_source.py src.json out.geojson --region=S,W,N,E`
  (Nominatim viewbox + bounded; e.g. Dublin `--region=53.0,-6.7,53.7,-6.0`).
- **Routing mode** — per route in the source: `"mode": "driving"` (default,
  OSRM) or `"mode": "foot"` (BRouter). Rail/other bespoke paths: paste a
  `coords` array directly (then it is used as-is).
- **Routing services** — endpoints are the `OSRM` / `BROUTER` constants at the
  top of `geocode_source.py`.
- **Licence / provenance** — put a `metadata` block into the source
  (`{"license": "CC BY-NC 4.0", "note": "…"}`); it is copied into the GeoJSON.

## Typical loops

Edit the source directly, then regenerate:

```bash
python3 pipeline/geocode_source.py data/<work>-source.json data/<work>.geojson --region=S,W,N,E
python3 pipeline/check.py
```

- **New place** — add an entry with its group key, `name`, a findable
  `geocode` query and optional `time` / `gloss` / `quote` / `ref` …. It is
  geocoded once and the result cached back.
- **Wrong coordinate** — set `lat`/`lon` by hand (overrides geocoding).
- **Route** — give `from`/`to` `[lat,lon]` + a `mode`, or paste a `coords`
  array (`[[lon,lat],…]`) for a bespoke path.

Interactive editing and uMap round-trip:

```bash
python3 pipeline/annotate-ui/serve.py                 # → http://127.0.0.1:8765/
python3 pipeline/export_umap.py                       # → exports/<work>-umap.geojson
python3 pipeline/import_umap.py <edited>.geojson data/<work>-source.json
python3 pipeline/consolidate.py                       # fold overlay + own-layer back
```

## Project-specific additions

A project may keep converters for its own third-party sources next to these
generic scripts (e.g. Mapping Joyce's `example-dubliners/`, documented in its
own README there). They are not part of the shared, synced pipeline.
