# litmap

A small, zero-build engine for **literary-geography maps** — plot the places,
routes and characters of a text on an interactive OpenStreetMap, driven
entirely by a `config.json` and GeoJSON data. No framework, no build step:
plain HTML/CSS/JS + [Leaflet](https://leafletjs.com/).

This repository is a **GitHub template**. Click **“Use this template”** to start
a new project; it ships with a tiny working demo you then replace.

## The idea

```
engine/        the reusable machine (no project names in the code)
config.json    your project: works, groups, colours, strings, view, basemap
data/          your places & routes as GeoJSON
```

> A new project = edit `config.json` + add `data/`. You should never need to
> touch `engine/`. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the
> diagram [`docs/engine-vs-project.svg`](docs/engine-vs-project.svg).

## Quick start

```bash
python3 -m http.server 8000     # from the repo root
# open http://localhost:8000/   → the bundled "Demoville" demo
```

Then make it yours:

1. Edit **`config.json`** — site title, basemap, opening view + `regionBBox`,
   and your `works` (each with `groups`: label + colour).
2. Replace **`data/*.geojson`** with your features. Each feature carries
   `story` (= a group key), `name`, `kind` (`place`/`route`), and optional
   `character`, `time`, `gloss`, `quote`, `ref`.
3. (Optional) Use **`pipeline/`** to build the GeoJSON from a hand-curated
   source (geocoding + routing) and to round-trip edits through uMap — see
   [`pipeline/README.md`](pipeline/README.md).
4. Push and enable GitHub Pages.

## Features (all shown by the demo)

- Multiple **works** with switchable tabs; optional **experimental** badge.
- Colour-coded, toggleable **groups** in an accordion sidebar; optional
  numbering and a group **prefix** (e.g. “Stop 1 · …”).
- **Points and routes**; **character** attribution and **time** chips.
- Scrollable **popups** (gloss / quote / reference), kept clear of the header.
- A **region bounding box** for the opening view; far-off places stay reachable.

## Reference example

The full, real-world project this engine was extracted from is **Mapping
Joyce** (Joyce's *Dubliners* / *Ulysses* / *A Portrait …*), including the
text-processing / NER pipeline:

- Live: <https://hermesj.github.io/mappingJoyce/>
- Source: <https://github.com/hermesj/hermesj.github.io/tree/main/mappingJoyce>

It uses this same engine by copy, and additionally demonstrates **one** way to
*find and verify* places — a spaCy NER pass over the public-domain text.

## Bringing your own data

That annotation step is **deliberately not part of litmap.** The engine only
cares that your `data/` matches the schema (see `docs/ARCHITECTURE.md`); how you
compile it — close reading, an existing gazetteer, NER in any toolkit, QGIS, a
script of your own — is entirely up to you and your text's language. litmap
ships the rendering engine and a generic geocoding/routing/round-trip pipeline;
the *Mapping Joyce* example shows the NER route for those who want it.

## Licensing

- **Code** (`engine/`, `pipeline/`) — MIT, see [`LICENSE`](LICENSE).
- **Demo data** (`data/`) — fictional, CC0.
- Your own data and texts: see [`NOTICE.md`](NOTICE.md) for the per-layer
  rights model to adopt (geodata licence per project; source texts public
  domain only).

Basemap tiles © OpenStreetMap contributors © CARTO; geocoding/routing derive
from OpenStreetMap (ODbL).
