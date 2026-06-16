"use strict";
(function () {
  var state = { work: null, groups: [], features: [], byId: {}, configured: true, selId: null, editing: false };
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return (s == null ? "" : String(s)).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  // Editable field definitions. scope "point" = only for Point features.
  var FIELDS = [
    { k: "name", t: "text" }, { k: "story", t: "group" },
    { k: "character", t: "text" }, { k: "time", t: "text" }, { k: "seq", t: "number" },
    { k: "gloss", t: "area" }, { k: "quote", t: "area" }, { k: "ref", t: "text" },
    { k: "srcText", t: "text" }, { k: "essay", t: "text" },
    { k: "confidence", t: "conf" }, { k: "verified", t: "tri" }
  ];
  // lat/lon (points) and coords (routes) are handled in a dedicated Location block.

  // Parse a pasted GeoJSON (Feature / FeatureCollection / bare geometry) into a
  // plain location: {type:"Point",lat,lon} or {type:"LineString",coords:[[lon,lat],…]}.
  // Elevation (a 3rd coordinate, as BRouter exports) is dropped; values rounded to 6 dp.
  function r6(x) { return Math.round(parseFloat(x) * 1e6) / 1e6; }
  function extractGeometry(d) {
    if (!d || typeof d !== "object") return null;
    if (d.type === "FeatureCollection" && Array.isArray(d.features)) {
      for (var i = 0; i < d.features.length; i++) {
        var g = d.features[i] && d.features[i].geometry;
        if (g && (g.type === "Point" || g.type === "LineString" || g.type === "MultiLineString")) return g;
      }
      return d.features[0] && d.features[0].geometry;
    }
    if (d.type === "Feature") return d.geometry;
    if (d.type === "Point" || d.type === "LineString" || d.type === "MultiLineString") return d;
    return null;
  }
  function parseGeoJSON(text) {
    var d = JSON.parse(text);              // throws on bad JSON
    var g = extractGeometry(d);
    if (!g) throw new Error("no Point/LineString geometry found");
    if (g.type === "Point") {
      var c = g.coordinates; return { type: "Point", lon: r6(c[0]), lat: r6(c[1]) };
    }
    var line = g.type === "MultiLineString" ? g.coordinates[0] : g.coordinates;
    if (!Array.isArray(line) || line.length < 2) throw new Error("LineString needs ≥2 points");
    return { type: "LineString", coords: line.map(function (c) { return [r6(c[0]), r6(c[1])]; }) };
  }

  function api(path, opts) {
    return fetch(path, opts).then(function (r) {
      return r.json().then(function (j) { if (!r.ok || j.error) throw new Error(j.error || r.status); return j; });
    });
  }

  // ── base / effective values ──
  function baseVal(f, k) {
    if (k === "lat") return f.geom && f.geom.type === "Point" ? f.geom.lat : undefined;
    if (k === "lon") return f.geom && f.geom.type === "Point" ? f.geom.lon : undefined;
    return f.base ? f.base[k] : undefined;
  }
  function effVal(f, k) { return (f.patch && f.patch.hasOwnProperty(k)) ? f.patch[k] : baseVal(f, k); }
  function isOverridden(f, k) { return !!(f.patch && f.patch.hasOwnProperty(k)); }
  function hasPatch(f) { return f.patch && Object.keys(f.patch).length; }

  // ── load ──
  function loadWorks() {
    api("/api/works").then(function (works) {
      var sel = $("workSel");
      sel.innerHTML = works.map(function (w) {
        return '<option value="' + esc(w.key) + '">' + esc(w.label) + "</option>"; }).join("");
      sel.onchange = function () { loadWork(sel.value); };
      if (works.length) loadWork(works[0].key);
    }).catch(fail);
  }

  function loadWork(key) {
    return api("/api/features?work=" + encodeURIComponent(key)).then(function (p) {
      state.work = key; state.groups = p.groups; state.features = p.features; state.configured = p.configured;
      state.byId = {}; p.features.forEach(function (f) { state.byId[f.id] = f; });
      state.selId = null; state.editing = false;
      updateMeta(); $("search").value = ""; renderList("");
      $("panel").innerHTML = '<p class="empty">Pick a feature to edit, or “+ New object”.</p>';
    }).catch(fail);
  }

  function updateMeta() {
    var n = state.features.length, a = state.features.filter(hasPatch).length;
    $("meta").textContent = n + " features · " + a + " edited" +
      (state.configured ? "" : " · ⚠ not wired into config yet");
  }

  // ── list ──
  function renderList(filter) {
    filter = (filter || "").toLowerCase();
    var order = [], seen = {};
    state.features.forEach(function (f) {
      if (filter && (f.name + " " + f.story).toLowerCase().indexOf(filter) < 0) return;
      if (!seen[f.story]) { seen[f.story] = []; order.push(f.story); }
      seen[f.story].push(f);
    });
    // Group headings follow the config chapter/story order (state.groups), not
    // the feature load order — so "Chapter 2" never sorts after "Chapter 10".
    var gi = {};
    state.groups.forEach(function (g, i) { gi[g.key] = i; });
    order.sort(function (a, b) {
      var ia = gi[a] == null ? Infinity : gi[a], ib = gi[b] == null ? Infinity : gi[b];
      return ia - ib || (a < b ? -1 : a > b ? 1 : 0);
    });
    $("list").innerHTML = order.map(function (story) {
      return '<div class="grp">' + esc(story) + "</div>" + seen[story].map(function (f) {
        return '<div class="row' + (f.id === state.selId ? " sel" : "") + '" data-id="' + esc(f.id) + '">' +
          '<span class="dot' + (hasPatch(f) ? " on" : "") + '"></span>' +
          '<span class="nm">' + esc(effVal(f, "name")) + "</span>" +
          (f.kind === "route" ? '<span class="rt">route</span>' : "") +
          (f.source === "own" ? '<span class="own">own</span>' : "") + "</div>";
      }).join("");
    }).join("") || '<p class="empty" style="padding:1em">no matches</p>';
    Array.prototype.forEach.call($("list").querySelectorAll(".row"), function (el) {
      el.onclick = function () { select(el.getAttribute("data-id")); };
    });
  }

  // ── field rendering ──
  function fieldControl(f, fld, editing) {
    var k = fld.k, val = effVal(f, k), dis = editing ? "" : " disabled";
    var v = val == null ? "" : val;
    if (fld.t === "area") return '<textarea id="f_' + k + '"' + dis + '>' + esc(v) + "</textarea>";
    if (fld.t === "number") return '<input id="f_' + k + '" type="number" step="' + (k === "seq" ? "1" : "any") + '" value="' + esc(v) + '"' + dis + ">";
    if (fld.t === "group") {
      return '<select id="f_' + k + '"' + dis + ">" + state.groups.map(function (g) {
        return '<option value="' + esc(g.key) + '"' + (g.key === v ? " selected" : "") + ">" + esc(g.label) + "</option>";
      }).join("") + "</select>";
    }
    if (fld.t === "conf") {
      var cv = val == null ? "" : val;
      return '<select id="f_' + k + '"' + dis + ">" +
        ['<option value="">(none)</option>',
         '<option value="high"' + (cv === "high" ? " selected" : "") + ">high</option>",
         '<option value="medium"' + (cv === "medium" ? " selected" : "") + ">medium</option>",
         '<option value="low"' + (cv === "low" ? " selected" : "") + ">low</option>"].join("") + "</select>";
    }
    if (fld.t === "tri") {
      var cur = val === true ? "true" : (val === false ? "false" : "");
      return '<select id="f_' + k + '"' + dis + ">" +
        ['<option value="">(inherit)</option>',
         '<option value="true"' + (cur === "true" ? " selected" : "") + ">verified</option>",
         '<option value="false"' + (cur === "false" ? " selected" : "") + ">unverified</option>"].join("") + "</select>";
    }
    return '<input id="f_' + k + '" type="text" value="' + esc(v) + '"' + dis + ">";
  }

  // Location editor: paste a GeoJSON export (BRouter/uMap) to set the geometry —
  // uniformly for points (→ lat/lon) and routes (→ coords).
  function locationHtml(f, editing) {
    var route = f.kind === "route";
    var ov = route ? isOverridden(f, "coords") : (isOverridden(f, "lat") || isOverridden(f, "lon"));
    var cur = route
      ? ((f.patch && f.patch.coords) ? f.patch.coords.length : (f.geom ? f.geom.npts : 0)) + " points"
      : effVal(f, "lat") + ", " + effVal(f, "lon");
    var rev = (editing && ov) ? '<span class="revert" data-k="' + (route ? "coords" : "latlon") + '">revert to base</span>' : "";
    var paste = editing ? '<div class="fieldrow"><label>paste GeoJSON to replace the location ' +
      "(Feature / FeatureCollection / geometry — leave empty to keep)</label>" +
      '<textarea id="f_geojson" placeholder="paste a BRouter / uMap export…"></textarea></div>' : "";
    return '<fieldset class="' + (ov ? "overridden" : "") + '"><legend>location' +
      (ov ? " — override" : "") + rev + "</legend>" +
      '<div class="group-hint">current: ' + esc(cur) + (ov ? " (overridden)" : "") + "</div>" + paste + "</fieldset>";
  }

  function fieldRow(f, fld, editing) {
    if (fld.scope === "point" && f.kind !== "place") return "";
    var ov = isOverridden(f, fld.k);
    var revert = (editing && ov) ? '<span class="revert" data-k="' + fld.k + '">revert to base</span>' : "";
    return '<div class="fieldrow' + (ov ? " overridden" : "") + '">' +
      "<label>" + fld.k + (ov ? ' <span class="ov">override</span>' : "") + revert + "</label>" +
      fieldControl(f, fld, editing) + "</div>";
  }

  // ── select & edit ──
  function select(id) {
    state.selId = id; state.editing = false;
    renderFeature(); renderList($("search").value);
  }

  function renderFeature() {
    var f = state.byId[state.selId]; if (!f) return;
    var editing = state.editing;
    var head = '<div class="ctx"><h2>' + esc(effVal(f, "name")) + "</h2>" +
      '<div class="sub">' + esc(effVal(f, "story")) + " · " + esc(f.kind) +
      (f.source ? " · source: " + esc(f.source) : "") + " · id: " + esc(f.id) +
      (f.geom && f.geom.type === "LineString" ? " · route (" + f.geom.npts + " pts)" : "") + "</div></div>";

    var bar = '<div class="editbar">' + (editing
      ? '<button class="save" id="saveBtn">Save</button><button class="edit" id="cancelBtn">Cancel</button>'
      : '<button class="edit" id="editBtn">✎ Edit</button>') +
      '<span id="status"></span></div>';

    var loc = locationHtml(f, editing);
    var rows = '<form id="annForm">' + FIELDS.map(function (fld) { return fieldRow(f, fld, editing); }).join("") + "</form>";

    var prov = '<div class="prov">Edits are an overlay (your work) saved to data/' + esc(state.work) +
      "-annotations.json and merged onto the base at load time — the base data is never modified." +
      (state.configured ? "" : " ⚠ This work isn’t wired into config.json yet (Save tells you the line to add).") + "</div>";

    $("panel").innerHTML = head + bar + rows + loc + prov;
    if (editing) {
      $("saveBtn").onclick = saveEdits;
      $("cancelBtn").onclick = function () { state.editing = false; renderFeature(); };
      Array.prototype.forEach.call($("panel").querySelectorAll(".revert"), function (el) {
        el.onclick = function () { revertField(el.getAttribute("data-k")); };
      });
    } else {
      $("editBtn").onclick = function () { state.editing = true; renderFeature(); };
    }
  }

  function revertField(k) {
    var f = state.byId[state.selId];
    if (k === "latlon") { delete f.patch.lat; delete f.patch.lon; }
    else delete f.patch[k];
    renderFeature();
  }

  function readField(fld) {
    var el = $("f_" + fld.k); if (!el) return undefined;
    if (fld.t === "tri") return el.value === "" ? undefined : (el.value === "true");
    var v = el.value.trim();
    if (v === "") return undefined;
    if (fld.t === "number") return fld.k === "seq" ? parseInt(v, 10) : parseFloat(v);
    return v;
  }

  function eqBase(f, fld, val) {
    var b = baseVal(f, fld.k);
    if (val === undefined) return b === undefined || b === null || b === "";
    if (fld.t === "number") return Number(b) === Number(val);
    return String(b == null ? "" : b) === String(val);
  }

  function saveEdits() {
    var f = state.byId[state.selId]; if (!f) return;
    var patch = {};
    FIELDS.forEach(function (fld) {
      var val = readField(fld);
      if (val === undefined) return;            // empty → no override (revert to base)
      if (eqBase(f, fld, val)) return;          // equals base → no override
      patch[fld.k] = val;
    });
    // ── geometry (Location block: paste GeoJSON) ──
    var gjEl = $("f_geojson"), gj = gjEl ? gjEl.value.trim() : "";
    if (gj !== "") {
      var loc;
      try { loc = parseGeoJSON(gj); } catch (e) { setStatus("GeoJSON: " + e.message, true); return; }
      if (f.kind === "route") {
        if (loc.type !== "LineString") { setStatus("this is a route — paste a LineString", true); return; }
        patch.coords = loc.coords;
      } else {
        if (loc.type !== "Point") { setStatus("this is a point — paste a Point", true); return; }
        patch.lat = loc.lat; patch.lon = loc.lon;
      }
    } else {   // empty → keep an existing geometry override (use “revert” to drop it)
      if (f.kind === "route" && f.patch && f.patch.coords) patch.coords = f.patch.coords;
      if (f.kind !== "route" && f.patch && f.patch.lat != null) { patch.lat = f.patch.lat; patch.lon = f.patch.lon; }
    }
    setStatus("saving…", false);
    api("/api/overlay?work=" + encodeURIComponent(state.work), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: f.id, patch: patch })
    }).then(function (res) {
      f.patch = patch; state.editing = false;
      updateMeta(); renderFeature(); renderList($("search").value);
      setStatus("saved ✓  (reload the map)", false);
      if (res.configHint) state.configured = false;
    }).catch(function (e) { setStatus("error: " + e.message, true); });
  }

  // ── new object ──
  function newObject() {
    state.selId = null; renderList($("search").value);
    var grp = state.groups.map(function (g) { return '<option value="' + g.n + '">' + esc(g.label) + "</option>"; }).join("");
    var opt = function (k, t) {
      if (t === "area") return '<div class="fieldrow"><label>' + k + '</label><textarea id="n_' + k + '"></textarea></div>';
      return '<div class="fieldrow"><label>' + k + '</label><input id="n_' + k + '" type="text"></div>';
    };
    $("panel").innerHTML =
      '<div class="ctx"><h2>New object</h2><div class="sub">added to your own layer (source: own)</div></div>' +
      '<form id="newForm">' +
      '<div class="fieldrow"><label>group / story (primary)</label><select id="n_group">' + grp + "</select></div>" +
      '<div class="fieldrow"><label>weitere Kapitel (optional, z. B. 9,10) — macht den Knoten mehrkapitlig</label>' +
        '<input id="n_groups_extra" type="text" placeholder="Komma-getrennte Kapitelnummern"></div>' +
      '<div class="fieldrow"><label>name *</label><input id="n_name" type="text"></div>' +
      '<fieldset><legend>location</legend>' +
        '<div class="fieldrow"><label>paste GeoJSON — Point or LineString (BRouter / uMap export)</label>' +
        '<textarea id="n_geojson" placeholder="the kind (place / route) is taken from the geometry"></textarea></div>' +
        '<div class="fieldrow"><label>…or geocode query (creates a place)</label>' +
        '<input id="n_geocode" type="text" placeholder="findable address, Dublin, Ireland"></div></fieldset>' +
      opt("character") + opt("time") + opt("seq") + opt("gloss", "area") + opt("quote", "area") +
      opt("ref") + opt("srcText") + opt("essay") +
      '<div class="fieldrow"><label>confidence</label><select id="n_confidence">' +
        '<option value="">(none)</option><option value="high">high</option>' +
        '<option value="medium">medium</option><option value="low">low</option></select></div>' +
      '<div class="editbar" style="border:none"><button type="button" class="save" id="createBtn">Create</button>' +
      '<button type="button" class="edit" id="cancelNew">Cancel</button><span id="status"></span></div></form>';
    $("cancelNew").onclick = function () { $("panel").innerHTML = '<p class="empty">Pick a feature to edit, or “+ New object”.</p>'; };
    $("createBtn").onclick = createObject;
  }

  function createObject() {
    var v = function (k) { var el = $("n_" + k); return el ? el.value.trim() : ""; };
    if (!v("name")) { setStatus("name is required", true); return; }
    var primary = parseInt($("n_group").value, 10);
    var extra = v("groups_extra")
      ? v("groups_extra").split(/[\s,]+/).map(function (x) { return parseInt(x, 10); }).filter(function (x) { return !isNaN(x); })
      : [];
    var body = { group: extra.length ? [primary].concat(extra) : primary, name: v("name") };
    ["character", "time", "ref", "srcText", "essay", "confidence", "gloss", "quote"].forEach(function (k) { if (v(k)) body[k] = v(k); });
    if (v("seq")) body.seq = parseInt(v("seq"), 10);
    var gj = v("geojson");
    if (gj) {
      var loc;
      try { loc = parseGeoJSON(gj); } catch (e) { setStatus("GeoJSON: " + e.message, true); return; }
      if (loc.type === "LineString") { body.kind = "route"; body.coords = loc.coords; }
      else { body.kind = "place"; body.lat = loc.lat; body.lon = loc.lon; }
    } else if (v("geocode")) { body.kind = "place"; body.geocode = v("geocode"); }
    else { setStatus("paste GeoJSON, or give a geocode query", true); return; }
    setStatus("creating… (geocoding may take a second)", false);
    api("/api/create?work=" + encodeURIComponent(state.work), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
    }).then(function (res) {
      setStatus("created ✓ (reload the map)" + (res.configHint ? " — " + res.configHint : ""), false);
      loadWork(state.work);
    }).catch(function (e) { setStatus("error: " + e.message, true); });
  }

  function setStatus(msg, err) { var s = $("status"); if (s) { s.textContent = msg; s.className = err ? "err" : ""; } }
  function fail(e) { $("panel").innerHTML = '<p class="empty" style="color:#b00020">' + esc(e.message) + "</p>"; }

  $("search").addEventListener("input", function () { renderList(this.value); });
  $("newBtn").addEventListener("click", newObject);
  loadWorks();
})();
