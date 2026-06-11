# Architecture & Blueprint

This project is built on a **reusable, config- and data-driven engine for
literary-geography maps** — take one or more texts, curate their places /
routes / characters, and present them on an interactive OpenStreetMap-based map
with layers, popups and a text-processing (NER/verification) pipeline. The
engine was extracted into the standalone **[litmap](https://github.com/hermesj/litmap)**
template; *mappingJoyce* is its reference example.

The litmus test for the blueprint: **you can stand up a new project (a
different author/city) by editing `config.json` and adding data — without
touching engine code.**

## Module boundaries

| Layer | What it is | Project-specific? |
|-------|------------|-------------------|
| **engine/** | Leaflet rendering, accordion sidebar, layer/work toggle, popups (character trajectories *planned*) | No — generic |
| **config.json** | declares works, groups, colours, i18n strings, default view + region, basemap + attribution, per-work group numbering + source-text links | **Yes** |
| **data/** | GeoJSON (rendered) + `*-source.json` (hand-editable) per work | **Yes** |
| **pipeline/** | geocode + routing (OSRM/BRouter); optional KML export + uMap round-trip | No — generic, parametrised |
| **text/** | episode/section splitter (markers/regex/incipits), NER annotate + candidates | splitter config is project-specific; NER is generic |

The engine (`engine.js`) is **fully config-driven** (Phase B, done): every
Joyce-specific part — the works/groups tables, taglines, the Dublin bounding
box, the "Episode N ·" prefix, the basemap + attribution — lives in
`config.json`, not the code. The engine carries no project literals, which is
what let it be lifted into the standalone **litmap** template (Phase C, done).

## Generic components (what the engine/template must provide)

**A — Content model**
- A **public-domain text base with place-NER**, whose entities are curated
  (semi-automatic).
- **Hierarchical text units**: work → section/chapter (variable depth; for
  Joyce: works with their own view, chapters/episodes within).
- **Places with a category/tier** (key / waypoint / mention) and **routes**,
  both **attributed to characters** (the basis for movement profiles).
- *(optional)* **time stamps** (temporal structure); an **uncertainty / fictional
  flag** for approximate or invented places.

**B — Pipeline**
- **NER/annotation** (language-specific model) + **verification against the
  text** (does the place/quote really occur there?).
- **Geocoding** (gazetteer + focus bounding box) and **routing** in several
  modes (driving / foot / rail / manual).
- **Round-trip editing**: export → uMap → re-import (fix geometry losslessly).

**C — Presentation**
- **Basemap** (modern *or historical*) + attribution.
- **Layers & toggles**: by section/chapter **and** by character **and**
  optionally by tier.
- **Trajectories** (character movement profiles from ordered places/routes).
- **Info popups**: place, citation/chapter, person(s), quote and/or note —
  scrollable.
- **Base zoom / focus area** + handling of **far-off ("elsewhere")** mentions.
- *(optional)* multilingual UI, place search/index, time filter/timeline.

**D — Cross-cutting**
- **Per-layer rights model** (code MIT · text PD only · geodata licensed
  per work) · geodata **provenance** · **zero-build / static**.

### Project-specific axes (not in every project)

| Axis | Variant A | Variant B |
|------|-----------|-----------|
| Works per project | one | several (Joyce: 3) |
| Time structure | single day, clock-precise (Ulysses) | years / diffuse (few times) |
| Route density | itinerary-heavy | static (few routes) |
| Basemap | modern tiles | historical (1904 / Victorian) |
| Language/script | EN | RU/other → own NER model + transliteration |
| Scale | one city | several cities / country |
| UI | monolingual | multilingual |

### Portability (other authors)

Two gates: (1) **text rights** — author d. + 70 yrs (EU) or published before
1929 (US); (2) **real, identifiable topography + character movement.** Gate 1
applies only to the **text/NER layer** — the *map* can be built from one's own
factual place data even for in-copyright works (facts aren't copyrightable);
only the full-text/NER corpus is gated.

- **Dickens / London** — top fit. Public domain (d. 1870), intensely
  topographic, clear itineraries; several novels = several "works". Caveat:
  Victorian city → historical basemap desirable; some composite/fictionalised
  places.
- **Dostoevsky / Petersburg** — very good, work-dependent. *Crime and
  Punishment* is near-ideal (real streets, abbreviated by Dostoevsky but
  scholarly-decoded; Raskolnikov's walks famously mapped). Caveats: Russian
  text → **ru-NER** + transliteration; use a PD translation (Garnett); some
  works use invented places (*Brothers Karamazov* → fictional town = poorly
  mappable).
- **Other strong candidates:** Woolf, *Mrs Dalloway* (London, single day like
  Ulysses, PD); Schnitzler/Vienna (PD); Zola/Paris (PD); Bely/Petersburg (PD).
  *Rights caveat:* Döblin, *Berlin Alexanderplatz* (very topographic, but EU
  public domain only in 2028).
- **Poor fit:** invented/diffuse settings, non-topographic works.

**Bottom line:** the template carries wherever a work has **real urban
geography + character movement** and a **public-domain text**. Dickens (London)
and Dostoevsky's *Crime and Punishment* (Petersburg) are both excellent second
examples — Dickens the smoothest (English, one city), Dostoevsky with the extra
step of Russian NER.

## `config.json` schema

The project file the engine reads at startup (excerpt — see the live
`config.json` for the full thing):

```jsonc
{
  "site":    { "title": "Mapping Joyce", "defaultWork": "dubliners",
               "defaultLang": "en", "impressum": "<h2>…</h2>" },   // impressum HTML optional
  "basemap": { "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
               "maxZoom": 19, "attribution": "© OpenStreetMap contributors © CARTO" },
  "view":    { "center": [53.3478, -6.2597], "zoom": 13,
               "regionBBox": [53.0, -6.7, 53.7, -6.0] },   // [S,W,N,E] = opening extent
  "ui":      { "en": { "showAll": "Show all", "route": "Route", "page": "p.", "…": "…" },
               "de": { "…": "…" } },                        // i18n UI strings
  "works": {
    "dubliners": {
      "label":   { "en": "Dubliners", "de": "Dubliner" },
      "tagline": { "en": "…", "de": "…" },
      "credit":  { "en": "Geodata derived from … (CC BY-NC 4.0)", "de": "…" },
      "data": [                        // one file (string) or several; an entry is
        { "url": "data/dubliners.geojson",     "source": "mulliken" },  // a bare URL
        { "url": "data/dubliners-own.geojson", "source": "own" }        // or {url, source}
      ],
      "sources": {                     // optional: a popup byline per source tag
        "own": { "byline": { "en": "Added by … — not part of the base layer" } }
      },
      "annotations": "data/dubliners-annotations.json",  // optional editorial overlay
      "regionBBox": [53.27, -6.33, 53.38, -6.09],  // optional per-work opening region
                                                   // (overrides view.regionBBox)
      "experimental": false,
      "numberedGroups": false,         // sidebar "1. …" numbering
      "groupPrefix": null,             // e.g. {"en":"Episode"} → popup "Episode 3 · …"
      "sourceText": {                  // optional: deep-link quotes into a PD text
        "url": "https://www.gutenberg.org/…/pg2814-images.html",
        "anchor": "chap{n2}", "label": { "en": "in context (Gutenberg)", "de": "…" }
      },
      "essay": {                       // optional: a feature.essay URL → "further reading" link
        "source": "Mapping Dubliners",
        "label": { "place": { "en": "about this place" }, "route": { "en": "about this route" } }
      },
      "groups": [
        { "key": "The Sisters", "de": "Die Schwestern", "color": "#b5651d" }
        /* … one per story/episode/chapter; `key` matches a feature's `story` */
      ]
    }
    /* ulysses: experimental true, numberedGroups true, groupPrefix {"en":"Episode"},
       sourceText → Gutenberg #4300 … */
  }
}
```

> *Planned extension* (not in the schema yet): a per-work `layerDimensions`
> (`["group","character","tier"]`) to toggle views by character or tier — the
> basis for the movement-profile feature (Roadmap D).

## Data schema

**Rendered GeoJSON — the data contract the engine reads.** Every
`Feature.properties` key below is one the engine actually consumes; the
pipeline emits *only* these (no decorative or duplicate fields — which work a
feature belongs to is implied by the file it lives in, and group titles come
from `config`, not the data).

| key | req? | meaning |
|-----|------|---------|
| `story` | **required** | the group's title — must match a `config.works.<w>.groups[].key` |
| `name` | **required** | place / route label |
| `kind` | **required** | `place` \| `route` (also inferable from geometry) |
| `group` | optional | numeric group ordinal; used for the `groupPrefix` popup label ("Episode 4 ·") and as the source-text anchor fallback. Absent for unnumbered works (Dubliners). |
| `character` | optional | mover(s), comma-separated (for trajectories) |
| `time` | optional | clock time chip in the popup |
| `gloss` | optional | editorial note |
| `quote` | optional | verbatim text quotation |
| `page` \| `ref` | optional | citation shown under the quote — two interchangeable styles (a page number vs. an "episode.line" / chapter ref); a feature uses whichever fits its work |
| `srcText` | optional | verbatim source-page fragment for the "in context" deep link, when it must differ from the displayed `quote` |
| `essay` | optional | URL of a secondary "further reading" link (the per-work `essay` config supplies its label + source name) |
| `source` | optional | provenance tag; the per-work `sources` config maps it to a popup byline (e.g. own additions vs. a derived base layer). May be set per feature or stamped from the `data` file it came from. |
| `seq` | optional | ordering key; the engine stable-sorts features by it (within their group), letting annotations reorder the list and own additions interleave with the base. |
| `verified` | optional | `false` flags an unchecked node (legend + popup badge); omit it for stable layers |
| geometry | **required** | `Point` (place) or `LineString` (route) |

> One contract, minor justified per-work variation: numbered works carry
> `group` + `time`; experimental layers carry `verified`; citation is `page`
> *or* `ref`. Nothing else is emitted. (Historically the data also carried
> `work`, `group_de`, `story_label` and a raw `description` blob — all removed,
> as the engine never read them.)

**Annotation overlay** (optional, `data/<work>-annotations.json`, pointed to by
`config.works.<w>.annotations`) — an *editorial layer on top of the base data*,
authored separately from it. Shape: `{ "<feature-id>": { field: value, … } }`,
where the id is derived as `slug(story)/slug(name)` (`-2`/`-3` for duplicates)
identically in `engine.js` and `pipeline/overlay.py`. The engine merges the
patch onto matching features **at load time** — the base GeoJSON is never
modified, so provenance stays clean and removing a patch just drops it on
reload. Edited with the local tool `pipeline/annotate-ui/` (stdlib, never
deployed). This is how field-level cross-author contributions are kept distinct
(e.g. Mulliken's place data vs. character/time annotations added by someone
else), with provenance recorded in `data/NOTICE.md`.

**Editable source** (`*-source.json`) — `groups`/`episodes`/`chapters` list +
`places` + optional `routes` (with `from`/`to` + cached `coords`, `mode`).
The source may use `episode` as the per-place group key (Ulysses) or `group`;
`pipeline/geocode_source.py` normalises it to `group` and turns source →
GeoJSON.

## Rights model (per layer — important for a public template)

- **Engine + pipeline code**: MIT (project default).
- **Source texts** (`text/raw/`): public domain only; document
  provenance in a `NOTICE.md` (see Ulysses 1922).
- **Geodata**: licence is per-work, declared in `config.works.*.credit` and a
  data `NOTICE`. Examples here: Dubliners = CC BY-NC 4.0 (derived from Mulliken);
  Ulysses/Portrait = original, CC BY-NC 4.0. **No copyrighted critical editions**
  (e.g. Gabler); cite their line numbers only.

## Start a new project (target workflow)

1. Use the GitHub **template** → new repo.
2. Edit `config.json`: site title, basemap, `view`/`regionBBox`, define `works`
   + `groups` (labels/colours).
3. Add data: write `data/<work>-source.json`, run
   `pipeline/geocode_source.py` → `<work>.geojson`.
4. (Optional) text pipeline: drop a public-domain text in `text/raw/`, configure
   the splitter, run NER `annotate.py` + `candidates.py` to find/verify places.
5. Push → GitHub Pages. Done, no engine edits.

## Roadmap

- **A. Spec** *(this document)* — define the engine/config/data contract. ✅
- **B. Config-driven engine** — all Joyce-specific literals moved out of
  `engine.js` into `config.json`; Joyce kept working at every step. ✅
- **C. Template-ise** — generic `engine/` + `pipeline/` + `docs/`; per-layer
  licences; validated with a tiny second example (Demoville); published as the
  separate **[litmap](https://github.com/hermesj/litmap)** GitHub template repo,
  with mappingJoyce as its reference example. ✅
- **D. Movement profiles** *(planned)* — a `tier` classification
  (key / waypoint / mention) plus per-character trajectories and character/tier
  layer toggles (`layerDimensions`).
