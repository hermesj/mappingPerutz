# Mapping Perutz

An interactive [OpenStreetMap](https://www.openstreetmap.org/)-based map of
Leo Perutz's novel ***Zwischen neun und neun*** (*Between Nine and Nine*, 1918):
the stations and paths of Stanislaus Demba through a **single Vienna day —
between nine in the morning and nine at night**.

- **Live:** <https://hermesj.github.io/mappingPerutz/>
- **Engine:** built from the **[litmap](https://github.com/hermesj/litmap)**
  template (config + data only, no engine edits). Sibling project:
  [Mapping Joyce](https://hermesj.github.io/mappingJoyce/).

## What it shows

The novel's 20 chapters as colour-coded layers, plus thematic layers that group
places across the book — *Reiseziele* (the imagined journeys), *Orte der
Gelehrten* (the scholars' places), *Orte der Betrüger* (the cities the swindlers
name-drop) and *Meta / Kontext*. Demba's day is also traced as colour-coded
**route segments**, chapter by chapter.

Each scene of the day carries the **clock time** of Demba's passage (the book's
twelve hours invite Ulysses-style time chips) and the **characters** present;
places that are merely mentioned stay deliberately chip-less. A muted
green–yellow–red **halo** shows how certain each location is (*gesichert /
straßengenau / hypothetisch*). Every node has an editorial gloss and, sparingly,
a short quotation. On first load only the chapter layers are shown; the thematic
layers can be switched on in the sidebar.

> All twenty chapters are mapped — a first complete version; context nodes and
> route shapes may still be refined.

## Rights (important, and different from Joyce)

Leo Perutz died in **1957**. His work is:

- **public domain in the USA** (published 1918, i.e. before 1929) — which is why
  [Project Gutenberg #36901](https://www.gutenberg.org/ebooks/36901) can host it;
- **still in copyright in the EU until 31 Dec 2027** (life + 70, counted from
  the end of the year of death) — **public domain on 1 January 2028**.

This project therefore, until 2028:

- contains **no full text** in the repository (the `text/` NER corpus of the
  Joyce project has no counterpart here yet);
- uses quotations **sparingly, as short evidentiary excerpts** under the German
  right of quotation (§ 51 UrhG), each serving the map's commentary;
- consists otherwise of **original, factual geodata** (places, routes, glosses
  — facts are not copyrightable), CC BY-NC 4.0.

See [`NOTICE.md`](NOTICE.md).

## Editing the data

Everything lives in one key-based source,
`data/zwischen-neun-und-neun-source.json` (chapter **and** thematic groups; add
`places` / `routes`), rendered with the generic geocoder:

```bash
python3 pipeline/geocode_source.py data/zwischen-neun-und-neun-source.json \
        data/zwischen-neun-und-neun.geojson --region=48.12,16.25,48.28,16.50
```

For interactive work, the local annotation tool creates and edits nodes, groups,
ordering, confidence and default visibility, and accepts pasted Google-Maps
coordinates or GeoJSON. New objects land in a separate `…-own-source.json` layer:

```bash
python3 pipeline/annotate-ui/serve.py     # → http://127.0.0.1:8765/
```

Geometry can also be round-tripped through [uMap](https://umap.openstreetmap.fr/):

```bash
python3 pipeline/export_umap.py           # → exports/zwischen-neun-und-neun-umap.geojson
# …reshape points/lines in uMap, export, then write the geometry back:
python3 pipeline/import_umap.py <edited>.geojson \
        data/zwischen-neun-und-neun-source.json
```

To fold the working layers (own-layer + annotation overlay) back into the single
source and re-render — the end-of-session step, no LLM needed:

```bash
python3 pipeline/consolidate.py
```

Before committing, lint:

```bash
python3 pipeline/check.py
```

## Local preview

```bash
python3 -m http.server 8082
# → http://localhost:8082/
```

## Licensing

- **Code** (`engine/`, `pipeline/`) — MIT ([`LICENSE`](LICENSE), litmap).
- **Geodata** (`data/`) — original dataset, **CC BY-NC 4.0**.
- **Source text** — see *Rights* above; basemap © OpenStreetMap contributors
  © CARTO. A non-commercial academic project.
