"use strict";
/* Deutschland im Überblick — Kreiskarte (MVP)
 *
 * Daten:
 *   data/map_data.json   — columns (Registry inkl. Themenblock) + rows (400 Kreise)
 *   data/kreise.geo.json — vereinfachte VG250-Kreisgrenzen (rs = Join-Schluessel)
 *
 * Konventionen (bewusst):
 *   - Quintilsklassen ueber die 400 Kreise (kein Linear-Massstab)
 *   - Platz 1 = hoechster Wert. Keine Bewertung als "gut"/"schlecht";
 *     eine Polaritaets-Konfiguration je Variable ist bewusst NICHT
 *     Bestandteil des MVP.
 *   - Meta-Spalten (rs, name, type, bl, ost, name_vgrdl) sind keine
 *     Variablen; ost zusaetzlich von Ranglisten ausgeschlossen.
 */

var EXCLUDE_SELECTOR = ["rs", "name", "type", "bl", "ost", "name_vgrdl"];
var EXCLUDE_RANKING = ["ost"];
var DEFAULT_VAR = "verfeink_je_ew";
var CLASS_COLORS = ["#f1f5fa", "#c6dbef", "#6baed6", "#3182bd", "#08519c"];
var NO_DATA_COLOR = "#cfd4da";

/* ---------- reine Logik (in Node testbar) ---------- */

function numericColumns(columns, rows) {
  // Spalten, die in mindestens einem Kreis einen Zahlwert tragen
  var isNum = {};
  columns.forEach(function (c) { isNum[c.key] = false; });
  rows.forEach(function (r) {
    columns.forEach(function (c) {
      if (typeof r[c.key] === "number") isNum[c.key] = true;
    });
  });
  return columns.filter(function (c) { return isNum[c.key]; });
}

function selectableColumns(columns, rows) {
  var numeric = numericColumns(columns, rows).map(function (c) { return c.key; });
  var isNumeric = {};
  numeric.forEach(function (k) { isNumeric[k] = true; });
  return columns.filter(function (c) {
    return isNumeric[c.key] && EXCLUDE_SELECTOR.indexOf(c.key) < 0;
  });
}

function valuesOf(rows, key) {
  var out = [];
  rows.forEach(function (r) {
    if (typeof r[key] === "number") out.push(r[key]);
  });
  return out;
}

function computeBreaks(values, nClasses) {
  // Quintilsgrenzen: nClasses-1 innere Schwellen
  var v = values.slice().sort(function (a, b) { return a - b; });
  if (!v.length) return [];
  var breaks = [];
  for (var i = 1; i < nClasses; i++) {
    var idx = Math.floor(i * v.length / nClasses);
    if (idx >= v.length) idx = v.length - 1;
    breaks.push(v[idx]);
  }
  return breaks;
}

function classify(value, breaks) {
  // Klasse 0..breaks.length; hoeherer Wert = hoehere Klasse
  var cls = 0;
  for (var i = 0; i < breaks.length; i++) {
    if (value > breaks[i]) cls = i + 1;
  }
  return cls;
}

function rankOf(rows, key, x) {
  // Rang: 1 + Anzahl streng groesserer Werte (gleiche Werte gleicher Rang)
  if (typeof x !== "number") return null;
  var rank = 1, n = 0;
  rows.forEach(function (r) {
    if (typeof r[key] === "number") {
      n++;
      if (r[key] > x) rank++;
    }
  });
  return { rank: rank, n: n };
}

function topFlopPlacements(columns, rows, rs, count) {
  var row = null;
  rows.forEach(function (r) { if (String(r.rs).padStart(5, "0") === rs) row = r; });
  if (!row) return { top: [], flop: [] };
  var byLabel = {};
  columns.forEach(function (c) { byLabel[c.key] = c.label; });
  var entries = [];
  numericColumns(columns, rows).forEach(function (c) {
    if (EXCLUDE_RANKING.indexOf(c.key) >= 0) return;
    var res = rankOf(rows, c.key, row[c.key]);
    if (res && res.n >= 50) {  // Variablen mit fast nur Nullwerten skippen
      entries.push({
        key: c.key, label: byLabel[c.key], value: row[c.key],
        rank: res.rank, n: res.n, ratio: res.rank / res.n
      });
    }
  });
  var asc = entries.slice().sort(function (a, b) {
    return a.ratio - b.ratio || a.rank - b.rank;
  });
  var desc = entries.slice().sort(function (a, b) {
    return b.ratio - a.ratio || b.rank - a.rank;
  });
  return { top: asc.slice(0, count), flop: desc.slice(0, count) };
}

function fmtNum(v) {
  if (typeof v !== "number") return "–";
  return v.toLocaleString("de-DE", { maximumFractionDigits: 2 });
}

/* ---------- Bootstrap (Browser) ---------- */

function initBrowser() {
  var state = { columns: null, rows: null, byKey: null, varKey: DEFAULT_VAR,
                breaks: null, clsByRs: {}, layer: null, geoJson: null, map: null };

  function col(key) { return state.byKey[key]; }
  function rs5(r) { return String(r).padStart(5, "0"); }

  function setVariable(key) {
    state.varKey = key;
    var c = col(key);
    var vals = valuesOf(state.rows, key);
    state.breaks = computeBreaks(vals, CLASS_COLORS.length);
    state.clsByRs = {};
    state.rows.forEach(function (r) {
      var v = r[key];
      state.clsByRs[rs5(r.rs)] = (typeof v === "number")
        ? classify(v, state.breaks) : -1;
    });
    document.querySelectorAll(".varlist button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.key === key);
    });
    document.getElementById("current-label").textContent = c.label;
    document.getElementById("current-meta").textContent =
      c.einheit + " · " + c.quelle;
    var srcLink = document.getElementById("src-link");
    if (c.link) { srcLink.href = c.link; srcLink.style.display = ""; }
    else { srcLink.style.display = "none"; }
    document.getElementById("src-stand").textContent = c.jahr || "";
    renderLegend(c);
    restyleAll();
    if (!document.getElementById("detail").hidden) renderDetail(state.detailRs);
  }

  function colorOf(rs) {
    var cls = state.clsByRs[rs];
    return cls >= 0 ? CLASS_COLORS[cls] : NO_DATA_COLOR;
  }

  function styleFor(feature) {
    return { color: "#ffffff", weight: 0.7, opacity: 0.9,
             fillColor: colorOf(rs5(feature.properties.rs)),
             fillOpacity: 0.88 };
  }

  function restyleAll() {
    if (!state.layer) return;
    state.layer.eachLayer(function (l) {
      if (l.feature) l.setStyle(styleFor(l.feature));
    });
  }

  function renderLegend(c) {
    document.getElementById("legend-title").textContent =
      c.label + (c.einheit ? " (" + c.einheit + ")" : "");
    var rowsEl = document.getElementById("legend-rows");
    rowsEl.innerHTML = "";
    var fmt = function (v) { return fmtNum(v); };
    var vals = valuesOf(state.rows, state.varKey);
    var sorted = vals.slice().sort(function (a, b) { return a - b; });
    var lo = sorted.length ? sorted[0] : 0;
    var hi = sorted.length ? sorted[sorted.length - 1] : 0;
    var b = state.breaks;
    var spans = [
      ["bis " + fmt(b[0]), CLASS_COLORS[0]],
      [fmt(b[0]) + " – " + fmt(b[1]), CLASS_COLORS[1]],
      [fmt(b[1]) + " – " + fmt(b[2]), CLASS_COLORS[2]],
      [fmt(b[2]) + " – " + fmt(b[3]), CLASS_COLORS[3]],
      ["ab " + fmt(b[3]), CLASS_COLORS[4]]
    ];
    spans.forEach(function (s) {
      var row = document.createElement("div");
      row.className = "legend-row";
      var chip = document.createElement("span");
      chip.className = "chip";
      chip.style.background = s[1];
      var t = document.createElement("span");
      t.textContent = s[0];
      row.appendChild(chip); row.appendChild(t);
      rowsEl.appendChild(row);
    });
    var nodata = document.createElement("div");
    nodata.className = "legend-row";
    var chip = document.createElement("span");
    chip.className = "chip"; chip.style.background = NO_DATA_COLOR;
    var t = document.createElement("span"); t.textContent = "kein Wert";
    nodata.appendChild(chip); nodata.appendChild(t);
    rowsEl.appendChild(nodata);
  }

  function rowByRs(rs) {
    for (var i = 0; i < state.rows.length; i++) {
      if (rs5(state.rows[i].rs) === rs) return state.rows[i];
    }
    return null;
  }

  function renderDetail(rs) {
    state.detailRs = rs;
    var row = rowByRs(rs);
    var el = document.getElementById("detail");
    if (!row) { el.hidden = true; return; }
    var c = col(state.varKey);
    var res = rankOf(state.rows, state.varKey, row[state.varKey]);
    var tf = topFlopPlacements(state.columns, state.rows, rs, 5);

    var placeRows = function (list, cssClass) {
      return list.map(function (e) {
        return '<li class="' + cssClass + '"><span>' + e.label +
          ' <em style="color:var(--muted)">(' + fmtNum(e.value) + ')</em></span>' +
          '<span class="rank">Platz ' + e.rank + ' von ' + e.n + "</span></li>";
      }).join("");
    };

    el.innerHTML =
      '<button class="close" title="Schließen">✕</button>' +
      "<h2>" + row.name + "</h2>" +
      '<div class="sub">' + row.type + " · " + row.bl +
      (typeof row.pop === "number"
        ? " · " + fmtNum(row.pop) + " Einwohner" : "") + "</div>" +
      '<div class="aktuell"><b>' + c.label + ":</b> " +
      (typeof row[state.varKey] === "number" ? fmtNum(row[state.varKey]) : "kein Wert") +
      (c.einheit ? " " + c.einheit : "") +
      (res ? ' &nbsp;·&nbsp; <b>Platz ' + res.rank + " von " + res.n + "</b>" : "") +
      "</div>" +
      "<h3>Spitzenplätze — häufig vorn</h3>" +
      '<ul class="placement-list">' + placeRows(tf.top, "top") + "</ul>" +
      "<h3>Schlussplätze — häufig hinten</h3>" +
      '<ul class="placement-list">' + placeRows(tf.flop, "flop") + "</ul>" +
      '<div class="note">Über alle ' +
      (tf.top.length ? "numerischen Variablen" : "Variablen") +
      "; Platz 1 = höchster Wert je Variable — keine Bewertung als „gut“ oder „schlecht“.</div>";
    el.hidden = false;
    el.querySelector(".close").addEventListener("click", function () {
      el.hidden = true;
    });
  }

  function buildSidebar() {
    var nav = document.getElementById("blocks");
    var selectable = selectableColumns(state.columns, state.rows);
    var blocks = [];
    state.columns.forEach(function (c) {
      if (c.block && blocks.indexOf(c.block) < 0) blocks.push(c.block);
    });
    blocks.forEach(function (block) {
      var items = selectable.filter(function (c) { return c.block === block; });
      if (!items.length) return;
      var det = document.createElement("details");
      if (block === col(state.varKey).block) det.open = true;
      var sum = document.createElement("summary");
      sum.innerHTML = '<span><span class="count">' + items.length +
        "</span> " + block + "</span>";
      det.appendChild(sum);
      var ul = document.createElement("ul");
      ul.className = "varlist";
      items.forEach(function (c) {
        var li = document.createElement("li");
        var btn = document.createElement("button");
        btn.dataset.key = c.key;
        btn.innerHTML = "<span>" + c.label + '</span><span class="einheit">' +
          (c.einheit || "") + "</span>";
        btn.addEventListener("click", function () { setVariable(c.key); });
        li.appendChild(btn);
        ul.appendChild(li);
      });
      det.appendChild(ul);
      nav.appendChild(det);
    });
  }

  function initMap(geo) {
    var map = L.map("map", {
      minZoom: 5, maxZoom: 11,
      maxBounds: [[45.5, 3.5], [55.5, 17.5]],
      maxBoundsViscosity: 0.7,
      zoomControl: true
    });
    map.setView([51.1, 10.2], 6);
    state.map = map;
    state.geoJson = geo;
    state.layer = L.geoJSON(geo, {
      style: styleFor,
      onEachFeature: function (feature, lay) {
        var rs = rs5(feature.properties.rs);
        lay.bindTooltip(function () {
          var row = rowByRs(rs);
          var c = col(state.varKey);
          var v = row ? row[state.varKey] : null;
          return "<b>" + (row ? row.name : rs) + "</b><br>" + c.label + ": " +
            (typeof v === "number" ? fmtNum(v) + (c.einheit ? " " + c.einheit : "")
                                   : "kein Wert");
        }, { sticky: true, className: "kreis-tooltip" });
        lay.on("click", function () { renderDetail(rs); });
      }
    }).addTo(map);
    map.attributionControl.setPrefix("");
    map.attributionControl.addAttribution(
      "Kreisgrenzen: © GeoBasis-DE / BKG (VG250)");
  }

  Promise.all([
    fetch("data/map_data.json").then(function (r) { return r.json(); }),
    fetch("data/kreise.geo.json").then(function (r) { return r.json(); })
  ]).then(function (res) {
    state.columns = res[0].columns;
    state.rows = res[0].rows;
    state.byKey = {};
    state.columns.forEach(function (c) { state.byKey[c.key] = c; });
    buildSidebar();
    initMap(res[1]);
    setVariable(DEFAULT_VAR);
  }).catch(function (err) {
    document.getElementById("current-label").textContent =
      "Fehler beim Laden der Daten";
    console.error(err);
  });
}

if (typeof document !== "undefined" && typeof L !== "undefined") {
  initBrowser();
}
