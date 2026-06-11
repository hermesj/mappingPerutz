/* Engine — interactive Leaflet map for literary geography, driven entirely by
   config.json + data/*.geojson (no project-specific literals here). The
   reference project it currently serves is "Mapping Joyce". See ARCHITECTURE.md.

   A work is a list of colour-coded `groups` (stories / episodes / chapters);
   every GeoJSON feature carries a `story` property naming its group. */

(function () {
  "use strict";

  // Populated from config.json at startup.
  var CFG, WORKS, UI, REGION;
  var params = new URLSearchParams(location.search);
  var lang = "en";   // set from config.site.defaultLang once loaded
  var work;          // set from ?work= or config.site.defaultWork once loaded

  var map, layers = {}, bounds = {}, placesByGroup = {};
  var selectedRoute = null;   // stays highlighted after its popup closes, until another feature is picked

  function groupsOf() { return WORKS[work].groups; }
  function groupFor(story) {
    return groupsOf().find(function (g) { return g.key === story; });
  }
  function colorFor(story) { var g = groupFor(story); return g ? g.color : "#777"; }
  function titleFor(story) { var g = groupFor(story); return g ? (lang === "de" ? g.de : g.key) : story; }

  // Route line styling: thin dashed by default; when its popup is open the route
  // is emphasised (thick, solid, on top) so it stands out from sibling routes
  // that share the same group colour. The colour itself never changes.
  var ROUTE_STYLE = { weight: 3, opacity: 0.65, dashArray: "5,5" };
  function routeStyle(color) {
    return { color: color, weight: ROUTE_STYLE.weight,
             opacity: ROUTE_STYLE.opacity, dashArray: ROUTE_STYLE.dashArray };
  }
  function highlightRoute(layer, on) {
    if (!layer || !(layer instanceof L.Polyline) || !layer.setStyle) return;
    if (on) { layer.setStyle({ weight: 6, opacity: 1, dashArray: null }); layer.bringToFront(); }
    else { layer.setStyle({ weight: ROUTE_STYLE.weight, opacity: ROUTE_STYLE.opacity, dashArray: ROUTE_STYLE.dashArray }); }
  }

  function esc(s) {
    return (s || "").replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  }

  // Build a "read in context" link into the work's public-domain source text,
  // from the per-work `sourceText` config (url + episode/chapter anchor) plus a
  // browser text-fragment (#:~:text=) that scrolls to and highlights the quote.
  function srcSnippet(quote) {
    // Pick a contiguous, apostrophe-free run of words to use as the text
    // fragment. Apostrophes are skipped because the source page uses curly ’
    // (a straight ' wouldn't match); breaking at the *first* one would yield an
    // empty snippet for dialogue like "I'm…"/"She's…", so we take the first run
    // of >=4 such words (falling back to the longest), capped and cut at a
    // sentence end.
    var s = (quote || "").replace(/^[\s"'’“”–—\-]+/, "");
    var words = s.split(/\s+/), runs = [], cur = [];
    function close() { if (cur.length) runs.push(cur); cur = []; }
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (/['’]/.test(w)) { close(); continue; }
      cur.push(w);
      if (/[.?!]$/.test(w) || cur.length >= 9) close();
    }
    close();
    var pick = null, j;
    for (j = 0; j < runs.length; j++) { if (runs[j].length >= 4) { pick = runs[j]; break; } }
    if (!pick) pick = runs.sort(function (a, b) { return b.length - a.length; })[0] || [];
    return pick.slice(0, 9).join(" ").replace(/[.,;:?!]+$/, "");
  }
  function sourceLink(p) {
    var st = WORKS[work].sourceText;
    if (!st || !p.quote) return "";
    // A route only gets a deep link when it carries a pinned, verbatim `srcText`
    // fragment: a route's quote is usually a representative passage, and a
    // snippet generated from it may not match the source page verbatim.
    if (p.kind === "route" && !p.srcText) return "";
    // Chapter/story ordinal = position of the feature's group in the work's
    // group list (Gutenberg HTML anchors run chap01, chap02 … in that order).
    // Falls back to the numeric `group` if the story isn't found.
    var idx = groupsOf().findIndex(function (g) { return g.key === p.story; });
    var gn = idx >= 0 ? idx + 1 : p.group;
    var anchor = (st.anchor || "").replace("{n2}", String(gn).padStart(2, "0"))
                                  .replace("{n}", String(gn));
    // A fixed `srcText` (verbatim from the source page) wins over a fragment
    // generated from the displayed quote — lets the quote text differ from the
    // edition without breaking the highlight.
    var frag = p.srcText || srcSnippet(p.quote);
    var href = st.url + "#" + anchor + ":~:text=" + encodeURIComponent(frag);
    var label = (st.label && st.label[lang]) || st.label || "source";
    return '<a class="pop-src" target="_blank" rel="noopener" href="' + href + '">↗ ' + esc(label) + "</a>";
  }

  // Optional secondary "further reading" link, from a per-work `essay` config
  // ({source, label:{place,route}}) plus a feature's own `essay` URL — e.g. the
  // Mapping Dubliners per-place essays. Sits at the foot of the popup.
  function essayLink(p) {
    var e = WORKS[work].essay;
    if (!e || !p.essay) return "";
    var kind = p.kind === "route" ? "route" : "place";
    var lo = e.label && e.label[kind];
    var lbl = (lo && (lo[lang] || lo.en || lo)) ||
              (kind === "route" ? "about this route" : "about this place");
    var src = e.source ? " (" + e.source + ")" : "";
    return '<a class="pop-essay" target="_blank" rel="noopener" href="' +
      esc(p.essay) + '">📖 ' + esc(lbl) + esc(src) + " →</a>";
  }

  // Provenance byline for a feature whose `source` has an entry (with a byline)
  // in the per-work `sources` config — e.g. flagging own additions as distinct
  // from the derived base layer. Default-source features get no byline.
  function sourceByline(p) {
    var sm = WORKS[work].sources;
    if (!sm || !p.source || !sm[p.source]) return "";
    var b = sm[p.source].byline;
    var txt = b && (b[lang] || b.en || b);
    return txt ? '<div class="pop-source">' + esc(txt) + "</div>" : "";
  }

  function popupHtml(p) {
    var t = UI[lang];
    var h = '<div class="pop-name">' + esc(p.name);
    if (p.kind === "route") h += ' <span style="font-weight:400;color:#9a8a7a">(' + t.route + ")</span>";
    h += "</div>";
    var sub = titleFor(p.story);
    // The data schema carries the group number as `group` (geocode_source.py).
    var epNum = p.group;
    var gp = WORKS[work].groupPrefix;          // e.g. {en:"Episode"} or null
    if (gp && epNum != null) sub = gp[lang] + " " + epNum + " · " + sub;
    h += '<div class="pop-story">' + esc(sub);
    if (p.time) h += ' <span class="pop-time">' + esc(p.time) + "</span>";
    h += "</div>";
    if (p.character) h += '<div class="pop-char">' + esc(p.character) + "</div>";
    if (p.gloss) h += '<div class="pop-gloss">' + esc(p.gloss) + "</div>";
    if (p.quote) {
      h += '<div class="pop-quote">' + esc(p.quote);
      var src = sourceLink(p);
      if (src) h += src;
      else if (p.page) h += '<span class="pop-page">' + t.page + " " + p.page + "</span>";
      else if (p.ref) h += '<span class="pop-page">' + esc(p.ref) + "</span>";
      h += "</div>";
    }
    h += essayLink(p);
    if (p.verified === false) h += '<div class="pop-unverified">⚠ not yet verified</div>';
    h += sourceByline(p);
    return h;
  }

  // Opening-view extent: a feature is "in region" if it falls inside the
  // config bounding box [S, W, N, E]. Far-off references stay on the map but
  // do not pull the initial fitBounds outward.
  function inRegion(lat, lon) {
    return lat > REGION[0] && lat < REGION[2] && lon > REGION[1] && lon < REGION[3];
  }

  function clearLayers() {
    Object.keys(layers).forEach(function (k) {
      if (map.hasLayer(layers[k])) map.removeLayer(layers[k]);
    });
    layers = {}; bounds = {};
  }

  // Cap a popup to the map pane's pixel height (minus room for the tip,
  // wrapper chrome and autoPan padding). The pane sits below the header, so a
  // popup no taller than this can never be clipped behind it; anything longer
  // gets Leaflet's scrollbar. Pane height is independent of zoom — only the
  // viewport size matters — so this is stable except across window resizes.
  function popupMaxHeight() {
    return Math.max(120, (map ? map.getSize().y : 600) - 64);
  }

  // ── Annotation overlay ──────────────────────────────────────────────────
  // A work may carry an optional `annotations` file (id → patch). The base
  // GeoJSON layers stay untouched; the patch fields are merged onto matching
  // features at load time (so removing a patch simply drops it on reload, and
  // provenance stays clean: base = the data files, annotations = this overlay).
  // The id is derived identically here and in pipeline/overlay.py.
  function annSlug(s) {
    return (s == null ? "" : String(s)).toLowerCase()
      .replace(/['’.]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }
  function assignIds(features) {
    var seen = {}, ids = [];
    features.forEach(function (f) {
      var b = annSlug(f.properties.story) + "/" + annSlug(f.properties.name);
      seen[b] = (seen[b] || 0) + 1;
      ids.push(seen[b] === 1 ? b : b + "-" + seen[b]);
    });
    return ids;
  }
  function loadOverlay() {
    var path = WORKS[work].annotations;
    if (!path) return Promise.resolve({});
    // no-cache: revalidate so a just-saved annotation shows up on plain reload
    return fetch(path, { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (o) { return (o && o.annotations) || {}; })
      .catch(function () { return {}; });
  }
  function applyOverlay(features, ann) {
    if (!ann || !Object.keys(ann).length) return;
    var ids = assignIds(features);
    features.forEach(function (f, i) {
      var patch = ann[ids[i]];
      if (!patch) return;
      Object.keys(patch).forEach(function (k) {
        if (k === "lat" || k === "lon" || k === "coords") return;   // geometry, handled below
        f.properties[k] = patch[k];
      });
      // Geometry overrides (correcting a base feature's placement).
      if (patch.coords) f.geometry = { type: "LineString", coordinates: patch.coords };
      else if (patch.lat != null && patch.lon != null)
        f.geometry = { type: "Point", coordinates: [patch.lon, patch.lat] };
    });
  }
  function sortBySeq(features) {
    features.forEach(function (f, i) { f.__i = i; });
    features.sort(function (a, b) {
      var sa = a.properties.seq == null ? Infinity : a.properties.seq;
      var sb = b.properties.seq == null ? Infinity : b.properties.seq;
      return sa === sb ? a.__i - b.__i : sa - sb;
    });
  }

  function loadWork() {
    clearLayers();
    // A work may narrow the opening-view region (e.g. Dubliners' outlying
    // seaside points would otherwise zoom the start view far out).
    REGION = WORKS[work].regionBBox || CFG.view.regionBBox;
    groupsOf().forEach(function (g) { layers[g.key] = L.layerGroup().addTo(map); });

    placesByGroup = {};
    groupsOf().forEach(function (g) { placesByGroup[g.key] = []; });

    // `data` may be one file (string) or several. An array entry can be a bare
    // URL or { url, source } — the source is stamped onto each loaded feature
    // (unless it carries its own), so layers of different provenance (e.g.
    // Mulliken-derived vs. own additions) can live in separate files yet render
    // together. Files are concatenated in order.
    var entries = WORKS[work].data;
    if (!Array.isArray(entries)) entries = [entries];
    entries = entries.map(function (e) { return typeof e === "string" ? { url: e } : e; });
    Promise.all(entries.map(function (e) {
      return fetch(e.url).then(function (r) { return r.json(); }).then(function (geo) {
        geo.features.forEach(function (f) {
          if (e.source && f.properties.source == null) f.properties.source = e.source;
        });
        return geo.features;
      });
    }))
      .then(function (lists) {
        var features = Array.prototype.concat.apply([], lists);
        return loadOverlay().then(function (ann) {
        applyOverlay(features, ann);   // merge each feature's annotation patch (by id)
        sortBySeq(features);           // honour an optional `seq` ordering key
        var all = L.latLngBounds([]), region = L.latLngBounds([]);
        features.forEach(function (f) {
          var p = f.properties, grp = layers[p.story];
          if (!grp) return;
          var layer;
          if (f.geometry.type === "Point") {
            var ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
            layer = L.circleMarker(ll, { radius: 6, weight: 1.5, color: "#fff",
              fillColor: colorFor(p.story), fillOpacity: 0.9 });
            all.extend(ll); if (inRegion(ll[0], ll[1])) region.extend(ll);
            (bounds[p.story] = bounds[p.story] || L.latLngBounds([])).extend(ll);
          } else if (f.geometry.type === "LineString") {
            var lls = f.geometry.coordinates.map(function (c) { return [c[1], c[0]]; });
            layer = L.polyline(lls, routeStyle(colorFor(p.story)));
            lls.forEach(function (ll) {
              all.extend(ll); if (inRegion(ll[0], ll[1])) region.extend(ll);
              (bounds[p.story] = bounds[p.story] || L.latLngBounds([])).extend(ll);
            });
          }
          if (layer) {
            // maxHeight (sized to the map pane) lets Leaflet add a scrollbar
            // when a long quote would otherwise overflow; autoPan then nudges
            // the popup fully into view below the header.
            layer.bindPopup(popupHtml(p), { maxWidth: 300, maxHeight: popupMaxHeight() });
            layer.addTo(grp);
            (placesByGroup[p.story] || (placesByGroup[p.story] = [])).push({
              name: p.name,
              kind: p.kind || (f.geometry.type === "LineString" ? "route" : "place"),
              verified: p.verified,
              layer: layer
            });
          }
        });
        if (region.isValid()) map.fitBounds(region.pad(0.05));
        else if (all.isValid()) map.fitBounds(all.pad(0.05));
        buildSidebar();
        });
      })
      .catch(function (e) {
        document.getElementById("story-list").innerHTML =
          '<p style="padding:1em;font-size:0.85rem">Could not load data: ' + e + "</p>";
      });
  }

  // Pan/zoom to a single place and open its popup, making sure its group
  // layer is switched on first.
  function focusPlace(groupKey, entry, item) {
    if (!map.hasLayer(layers[groupKey])) {
      layers[groupKey].addTo(map);
      if (item) item.classList.remove("off");
    }
    // Open the popup only once the camera has settled: opening mid-flight lets
    // the in-progress flyTo re-centre the marker and override the popup's
    // autoPan, which is what pushed tall popups up behind the header.
    var opened = false;
    function open() { if (!opened) { opened = true; entry.layer.openPopup(); } }
    map.once("moveend", function () { setTimeout(open, 60); });
    setTimeout(open, 1100); // fallback if the view doesn't actually move
    if (entry.kind === "route" && entry.layer.getBounds) {
      map.flyToBounds(entry.layer.getBounds().pad(0.3));
    } else if (entry.layer.getLatLng) {
      map.flyTo(entry.layer.getLatLng(), 16);
    } else {
      open();
    }
  }

  function buildSidebar() {
    var t = UI[lang];
    var box = document.getElementById("story-list");
    box.innerHTML = "";
    var numbered = WORKS[work].numberedGroups;
    groupsOf().forEach(function (g, idx) {
      var entries = placesByGroup[g.key] || [];
      var label = lang === "de" ? g.de : g.key;
      if (numbered) label = (idx + 1) + ". " + label;
      var unverified = entries.some(function (e) { return e.verified === false; });

      // ── the group row (click = expand/collapse; swatch = layer on/off) ──
      var item = document.createElement("div");
      item.className = "story-item";
      item.innerHTML =
        '<span class="caret">▸</span>' +
        '<span class="swatch" style="background:' + g.color + '" title="' + t.toggleLayer + '"></span>' +
        '<span class="story-name">' + esc(label) + "</span>" +
        (unverified ? '<span class="grp-unverified">unverified yet</span>' : "") +
        '<span class="count">' + entries.length + "</span>";

      // ── the collapsible list of this group's places ──
      var sub = document.createElement("div");
      sub.className = "place-list";
      sub.hidden = true;
      entries.forEach(function (e) {
        var pi = document.createElement("div");
        pi.className = "place-item";
        pi.innerHTML = esc(e.name) +
          (e.kind === "route" ? ' <span class="pl-route">' + t.route + "</span>" : "");
        pi.addEventListener("click", function (ev) {
          ev.stopPropagation();
          focusPlace(g.key, e, item);
        });
        sub.appendChild(pi);
      });

      item.addEventListener("click", function () {
        var opening = sub.hidden;
        sub.hidden = !opening;
        item.classList.toggle("expanded", opening);
        if (opening && !map.hasLayer(layers[g.key])) {
          layers[g.key].addTo(map);
          item.classList.remove("off");
        }
      });

      item.querySelector(".swatch").addEventListener("click", function (ev) {
        ev.stopPropagation();
        var turnOn = !map.hasLayer(layers[g.key]);
        if (turnOn) layers[g.key].addTo(map); else map.removeLayer(layers[g.key]);
        item.classList.toggle("off", !turnOn);
      });

      box.appendChild(item);
      box.appendChild(sub);
    });
  }

  function setVisible(show) {
    document.querySelectorAll(".story-item").forEach(function (item, i) {
      var key = groupsOf()[i].key;
      item.classList.toggle("off", !show);
      if (show) layers[key].addTo(map); else map.removeLayer(layers[key]);
    });
  }

  function applyLang() {
    var t = UI[lang];
    document.documentElement.lang = lang;
    var w = WORKS[work];
    var tagEl = document.getElementById("tagline");
    if (w.experimental) {
      tagEl.innerHTML = esc(w.tagline[lang]) + ' <span class="exp-note">— ' + esc(t.expNote) + "</span>";
    } else {
      tagEl.textContent = w.tagline[lang];
    }
    document.getElementById("btnShowAll").textContent = t.showAll;
    document.getElementById("btnHideAll").textContent = t.hideAll;
    var creditEl = document.getElementById("credit");
    creditEl.innerHTML = w.credit[lang] + " · " + CFG.basemap.attribution +
      ' · <a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>';
    if (CFG.site.impressum) {
      var imp = document.createElement("a");
      imp.className = "impressum-link";
      imp.href = "#";
      imp.textContent = "Impressum";
      imp.addEventListener("click", function (e) { e.preventDefault(); showImpressum(); });
      creditEl.appendChild(document.createTextNode("  ·  "));
      creditEl.appendChild(imp);
    }
    var bd = document.getElementById("btnDe"), be = document.getElementById("btnEn");
    if (bd) bd.className = lang === "de" ? "active" : "";
    if (be) be.className = lang === "en" ? "active" : "";
    Object.keys(WORKS).forEach(function (key) {
      var el = document.getElementById("work-" + key);
      if (!el) return;
      el.className = work === key ? "active" : "";
      el.innerHTML = esc(WORKS[key].label[lang]) +
        (WORKS[key].experimental ? ' <sup class="exp" title="' + esc(t.expNote) + '">' + esc(t.exp) + "</sup>" : "");
    });
  }

  // Language and work switches reload with query params so popups and the
  // legend rebuild cleanly in one place.
  window.switchLang = function (l) {
    if (l === lang) return;
    params.set("lang", l); location.search = params.toString();
  };
  window.switchWork = function (w) {
    if (w === work || !WORKS[w]) return;
    params.set("work", w); location.search = params.toString();
  };

  // Build the work tabs from config (applyLang fills their text + active state).
  function buildWorkTabs() {
    var box = document.getElementById("work-switch");
    if (!box) return;
    box.innerHTML = "";
    Object.keys(WORKS).forEach(function (key) {
      var a = document.createElement("a");
      a.id = "work-" + key;
      a.addEventListener("click", function () { switchWork(key); });
      box.appendChild(a);
    });
  }

  // Build a hidden impressum/about overlay from config.site.impressum (HTML).
  function buildImpressum(htmlStr) {
    if (document.getElementById("impressum-modal")) return;
    var m = document.createElement("div");
    m.id = "impressum-modal";
    m.innerHTML = '<div class="impressum-box"><button class="impressum-close" type="button" aria-label="Close">×</button>' +
      '<div class="impressum-content">' + htmlStr + "</div></div>";
    function close() { m.classList.remove("open"); }
    m.addEventListener("click", function (e) {
      if (e.target === m || e.target.classList.contains("impressum-close")) close();
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
    document.body.appendChild(m);
  }
  window.showImpressum = function () {
    var m = document.getElementById("impressum-modal");
    if (m) m.classList.add("open");
  };

  document.addEventListener("DOMContentLoaded", function () {
    fetch("config.json")
      .then(function (r) { return r.json(); })
      .then(function (cfg) {
        CFG = cfg; WORKS = cfg.works; UI = cfg.ui; REGION = cfg.view.regionBBox;
        lang = cfg.site.defaultLang || "en";
        work = WORKS[params.get("work")] ? params.get("work") : cfg.site.defaultWork;

        document.title = cfg.site.title;
        var st = document.getElementById("site-title");
        if (st) st.textContent = cfg.site.title;
        buildWorkTabs();
        if (cfg.site.impressum) buildImpressum(cfg.site.impressum);

        // Leaflet's own attribution control is disabled: all attribution lives
        // in the single #credit footer (built in applyLang), so the two no
        // longer overlap at the bottom of the map.
        map = L.map("map", { zoomControl: true, attributionControl: false })
          .setView(cfg.view.center, cfg.view.zoom);
        L.tileLayer(cfg.basemap.url, { maxZoom: cfg.basemap.maxZoom }).addTo(map);

        // Central popup sizing + placement, for every open path (sidebar click
        // or a direct marker click). Cap the height to the map pane (so a long
        // quote scrolls instead of overflowing) and converge autoPan over a few
        // settle steps so the popup ends up fully inside the pane, below the
        // header — a single autoPan pass undershoots for tall popups.
        map.on("popupopen", function (e) {
          var p = e.popup, src = p._source;
          // Selecting a new feature drops the previous route's highlight; a route
          // then stays emphasised even after its own popup is closed, until the
          // next feature is picked (the popup can hide part of the line).
          if (selectedRoute && selectedRoute !== src) { highlightRoute(selectedRoute, false); selectedRoute = null; }
          if (src instanceof L.Polyline) { highlightRoute(src, true); selectedRoute = src; }
          p.options.maxHeight = popupMaxHeight();
          p.update();
          [60, 320, 650].forEach(function (d) {
            setTimeout(function () { if (p.isOpen && p.isOpen() && p._adjustPan) p._adjustPan(); }, d);
          });
        });

        // Re-fit an open popup when the window (and thus the map pane) is resized.
        map.on("resize", function () {
          var p = map._popup;
          if (p && p.isOpen()) { p.options.maxHeight = popupMaxHeight(); p.update(); if (p._adjustPan) p._adjustPan(); }
        });

        applyLang();
        loadWork();
        document.getElementById("btnShowAll").addEventListener("click", function () { setVisible(true); });
        document.getElementById("btnHideAll").addEventListener("click", function () { setVisible(false); });
      })
      .catch(function (e) {
        document.getElementById("story-list").innerHTML =
          '<p style="padding:1em;font-size:0.85rem">Could not load config.json: ' + e + "</p>";
      });
  });
})();
