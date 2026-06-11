# Rights model

A litmap project typically combines layers with **different licences**. Keep
them separate and document each.

| Layer | What | Licence (in this template) |
|-------|------|----------------------------|
| **Code** | `engine/`, `pipeline/` | **MIT** — [`LICENSE`](LICENSE) |
| **Demo data** | `data/*.geojson` | **CC0** (fictional) |
| **Your geodata** | (replaces `data/`) | choose per project (see below) |
| **Source texts** | (if you add any) | **public domain only** |

Cross-cutting:

- **Basemap**: tiles © OpenStreetMap contributors © CARTO (configurable in
  `config.json`).
- **Coordinates & routes**: if produced with `pipeline/` they derive from
  OpenStreetMap via Nominatim / OSRM / BRouter — **© OpenStreetMap
  contributors, ODbL**.

## Choosing a geodata licence for your project

- If your geodata is **your own original compilation**, pick what you like
  (e.g. CC BY 4.0, or CC BY-NC 4.0 for non-commercial).
- If it is **derived from another dataset**, you must honour that source's
  licence (e.g. CC BY-NC + attribution).
- **Source texts** must be **public domain** to be redistributed here (author
  died ≥ 70 years ago in the EU, or published before 1929 in the US). Do not
  commit copyrighted critical editions; citing their line numbers is fine
  (facts are not copyrightable).

Record your choices in a `data/NOTICE.md` (geodata) and a
`text/raw/NOTICE.md` (texts), as the *Mapping Joyce* example does.
