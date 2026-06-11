# annotate-ui — local annotation tool

A tiny, dependency-free (Python stdlib) local web app for attaching **editorial
annotations** to any data layer of a litmap-style project, without hand-editing
JSON. It's a backend authoring tool — **local only, never deployed, no auth.**

```bash
# from the project root:
python3 pipeline/annotate-ui/serve.py
# → open http://127.0.0.1:8765/
# annotate another project:
python3 pipeline/annotate-ui/serve.py --root /path/to/project --port 8765
```

## What it does

- Reads the project's `config.json`, lists its **works** (Dubliners, Ulysses, …).
- Shows each work's features (grouped by story/episode, with a text filter);
  edited features get a dot, own additions an "own" tag.
- **Edit a feature** — click it; fields are read-only until you press **✎ Edit**,
  then *every* field is editable: title (`name`), `story`/group, `character`,
  `time`, `seq`, `gloss`, `quote`, `ref`, `srcText`, `essay`, `verified`, and the
  **location** — paste a GeoJSON export (Feature / FeatureCollection / bare
  geometry; a `Point` for a place, a `LineString` for a route) to set the
  geometry. **Save** stores only the fields that differ from the base into the
  per-work overlay `data/<work>-annotations.json` (key = stable id). Overridden
  fields are tagged and can be reverted to base. Reload the map to see it.
- **+ New object** — create a brand-new place or route in your own layer: pick a
  group, give a name, then **paste GeoJSON** (the kind is taken from the
  geometry) or give a geocode query (creates a place), plus optional fields. It's
  written to `data/<work>-own-source.json` and rendered to
  `data/<work>-own.geojson` (`source: "own"`) via the geocoder.

Pasted GeoJSON is parsed client-side: the geometry is extracted, elevation (a
3rd coordinate, as BRouter exports) is dropped, and values are rounded to 6 dp —
so you can drop a BRouter/uMap export straight in.

## How it fits (the overlay model)

The base GeoJSON layers are **never modified**. Annotations live in a separate
overlay file and are merged onto matching features **at load time** by the
engine (`engine.js`: `loadOverlay`/`applyOverlay`). So:

- provenance stays clean — base data is one author's, the overlay is yours;
- removing an annotation simply drops it on the next reload (no stale data);
- an optional `seq` field reorders features within their group (the engine
  sorts by it), which also lets own additions interleave with the base layer.

Features carry no stored id; a stable id is **derived** from
`slug(story)/slug(name)` (with `-2`/`-3` for duplicates). The exact same rule
lives in `engine.js` (`annSlug`/`assignIds`) and `pipeline/overlay.py`
(`slugify`/`feature_ids`), so the overlay keys always match.

## Wiring a new work

The engine only applies a work's overlay if the work has an `annotations` path
in `config.json`, e.g.:

```json
"dubliners": { "…": "…", "annotations": "data/dubliners-annotations.json" }
```

If you annotate a work that doesn't have it yet, the Save response tells you the
exact line to add (and the header shows "⚠ not wired into config yet").

## Notes

- Overriding the **title or coordinates** of a base feature doesn't change its
  id: the id is derived from the *base* `story`/`name` before the overlay is
  applied, so it stays stable even after you rename or move the feature.
- A route's line is replaced by pasting a fresh GeoJSON `LineString` (the
  typical loop: redraw it in BRouter/uMap, export, paste) — the tool doesn't
  edit individual vertices.
- New objects need their `data/<work>-own.geojson` listed in the work's `data`
  in `config.json` (and overrides need the work's `annotations` path) — if it's
  missing, the response tells you the exact line to add.
