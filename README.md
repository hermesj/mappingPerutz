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

The novel's 20 chapters as colour-coded layers; each mapped place carries the
clock time of Demba's passage (the book's twelve hours invite Ulysses-style
time chips), an editorial gloss and, sparingly, a short quotation.

> The dataset is **experimental and under construction** — places are being
> added chapter by chapter.

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

The hand-curated source is `data/zwischen-neun-und-neun-source.json`
(20 chapter groups; add `places`/`routes`), rendered with the generic geocoder:

```bash
python3 pipeline/geocode_source.py data/zwischen-neun-und-neun-source.json \
        data/zwischen-neun-und-neun.geojson --region=48.12,16.25,48.28,16.50
```

Or use the local annotation/edit tool (create new places, override fields):

```bash
python3 pipeline/annotate-ui/serve.py     # → http://127.0.0.1:8765/
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
