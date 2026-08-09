/* ---------------------------------------------------------------------
   AED Discovery Copilot — client-side demo logic.

   This intentionally re-implements the same two algorithms as
   src/baseline.py and src/ranker.py, in JS, so the map demo can run as
   a static page with no backend. The Python versions in src/ are the
   ones used for the evaluation report (docs/EVALUATION_REPORT.md) —
   keep the two in sync if you change the ranking logic.
   ------------------------------------------------------------------- */

const DATA_URL = "../data/aed_sample.geojson";
const URBAN_DETOUR_FACTOR = 1.35;
const TOP_K = 5;
const DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

let AEDS = [];
let map, queryMarker, resultLayer;
let currentQuery = null; // { lat, lon }
let activeMode = "ranker";

function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dPhi = toRad(lat2 - lat1);
  const dLambda = toRad(lon2 - lon1);
  const a =
    Math.sin(dPhi / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLambda / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function parseOperatingHours(text) {
  if (!text || !text.trim()) return { rules: [], warnings: ["empty operating-hours field"] };
  const warnings = [];
  const rules = [];
  const segments = text.split(";").map((s) => s.trim()).filter(Boolean);
  const dayRangeRe = /(mon|tue|wed|thu|fri|sat|sun)\s*-\s*(mon|tue|wed|thu|fri|sat|sun)/i;
  const singleDayRe = /(mon|tue|wed|thu|fri|sat|sun)(?!\s*-)/gi;
  const timeRangeRe = /(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})/;

  for (const seg of segments) {
    const segL = seg.toLowerCase();
    const tm = timeRangeRe.exec(segL);
    if (!tm) { warnings.push(`could not find a time range in segment: '${seg}'`); continue; }
    const [, h1, m1, h2, m2] = tm.map((x, i) => (i === 0 ? x : parseInt(x, 10)));
    const startMin = h1 * 60 + m1;
    const endMin = h2 * 60 + m2;

    let days = [];
    const dr = dayRangeRe.exec(segL);
    if (dr) {
      const d1 = DAY_ORDER.indexOf(dr[1].toLowerCase());
      const d2 = DAY_ORDER.indexOf(dr[2].toLowerCase());
      if (d2 >= d1) { for (let i = d1; i <= d2; i++) days.push(DAY_ORDER[i]); }
      else { for (let i = d1; i < 7; i++) days.push(DAY_ORDER[i]); for (let i = 0; i <= d2; i++) days.push(DAY_ORDER[i]); }
    } else {
      let m;
      while ((m = singleDayRe.exec(segL)) !== null) days.push(m[1].toLowerCase());
    }
    if (days.length === 0) { warnings.push(`could not find a day range in segment: '${seg}'`); continue; }
    for (const d of days) rules.push({ day: d, startMin, endMin });
  }
  if (rules.length === 0) warnings.push("no rules could be parsed — treat as UNKNOWN");
  return { rules, warnings };
}

function isOpenAt(rules, weekdayIdx, minuteOfDay) {
  const dayName = DAY_ORDER[weekdayIdx];
  for (const r of rules) {
    if (r.day !== dayName) continue;
    if (r.startMin <= r.endMin) {
      if (minuteOfDay >= r.startMin && minuteOfDay <= r.endMin) return true;
    } else {
      if (minuteOfDay >= r.startMin || minuteOfDay <= r.endMin) return true;
    }
  }
  return false;
}

function rankBaseline(qLat, qLon, aeds) {
  return aeds
    .map((a) => ({
      aed: a,
      distance_m: haversineM(qLat, qLon, a.LATITUDE, a.LONGITUDE),
    }))
    .sort((a, b) => a.distance_m - b.distance_m)
    .slice(0, TOP_K)
    .map((r) => ({
      aed: r.aed,
      status: null,
      confidence: null,
      reason: "Baseline ignores operating hours entirely (required minimum baseline).",
      distance_m: r.distance_m,
      isBaseline: true,
    }));
}

function rankImproved(qLat, qLon, aeds, weekdayIdx, minuteOfDay) {
  const scored = aeds.map((a) => {
    const straight = haversineM(qLat, qLon, a.LATITUDE, a.LONGITUDE);
    const dist = straight * URBAN_DETOUR_FACTOR;
    const { rules, warnings } = parseOperatingHours(a.OPERATING_HOURS || "");
    let status, confidence, reason;
    if (warnings.length && rules.length === 0) {
      status = "UNKNOWN_HOURS"; confidence = "low";
      reason = "Operating hours could not be parsed; accessibility cannot be established.";
    } else {
      const open = isOpenAt(rules, weekdayIdx, minuteOfDay);
      status = open ? "LIKELY_OPEN" : "LIKELY_CLOSED";
      confidence = warnings.length ? "medium" : "high";
      reason = open
        ? "Parsed operating-hours text covers the query time."
        : "Parsed operating-hours text does not cover the query time.";
    }
    return { aed: a, distance_m: dist, status, confidence, reason, isBaseline: false };
  });
  const statusRank = { LIKELY_OPEN: 0, UNKNOWN_HOURS: 1, LIKELY_CLOSED: 2 };
  scored.sort((a, b) => statusRank[a.status] - statusRank[b.status] || a.distance_m - b.distance_m);
  return scored.slice(0, TOP_K);
}

function markerColorFor(status) {
  if (status === "LIKELY_OPEN") return "#2dd6b5";
  if (status === "UNKNOWN_HOURS") return "#f2b54c";
  if (status === "LIKELY_CLOSED") return "#8892a8";
  return "#5f6d8a"; // baseline (no status)
}

function renderResults(results) {
  const list = document.getElementById("resultsList");
  list.innerHTML = "";
  results.forEach((r, i) => {
    const card = document.createElement("div");
    card.className = "result-card";
    if (r.status) card.dataset.status = r.status;
    const chip = r.status
      ? `<span class="status-chip" data-status="${r.status}">${r.status.replace("_", " ")}</span>`
      : `<span class="status-chip" style="color:#5f6d8a;background:#1c2438;">HOURS IGNORED</span>`;
    card.innerHTML = `
      <div class="result-card__head">
        <span class="result-card__building">${r.aed.BUILDING_NAME || "Unnamed site"}</span>
        <span class="result-card__rank">#${i + 1}</span>
      </div>
      <div class="result-card__desc">${r.aed.AED_LOCATION_DESCRIPTION || ""}</div>
      <div class="result-card__stats">
        <span><span class="stat-label">dist</span> ${r.distance_m.toFixed(0)} m</span>
        <span><span class="stat-label">id</span> ${r.aed.AED_ID}</span>
        ${chip}
      </div>
      <div class="result-card__reason">${r.reason}</div>
    `;
    list.appendChild(card);
  });
}

function renderMapResults(results) {
  resultLayer.clearLayers();
  results.forEach((r, i) => {
    const color = markerColorFor(r.status);
    const marker = L.circleMarker([r.aed.LATITUDE, r.aed.LONGITUDE], {
      radius: 8,
      color,
      weight: 2,
      fillColor: color,
      fillOpacity: 0.5,
    }).addTo(resultLayer);
    marker.bindPopup(
      `<strong>#${i + 1} ${r.aed.BUILDING_NAME || "Unnamed site"}</strong><br/>` +
      `${r.aed.AED_LOCATION_DESCRIPTION || ""}<br/>` +
      `${r.distance_m.toFixed(0)} m &middot; ${r.aed.OPERATING_HOURS || "no hours listed"}`
    );
  });
}

function runQuery() {
  if (!currentQuery) return;
  const day = parseInt(document.getElementById("daySelect").value, 10);
  const [hh, mm] = document.getElementById("timeInput").value.split(":").map(Number);
  const minuteOfDay = hh * 60 + mm;

  const results =
    activeMode === "ranker"
      ? rankImproved(currentQuery.lat, currentQuery.lon, AEDS, day, minuteOfDay)
      : rankBaseline(currentQuery.lat, currentQuery.lon, AEDS);

  renderResults(results);
  renderMapResults(results);
}

function initMap() {
  map = L.map("map", { zoomControl: true }).setView([1.3521, 103.8198], 12);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 19,
  }).addTo(map);

  resultLayer = L.layerGroup().addTo(map);

  map.on("click", (e) => {
    currentQuery = { lat: e.latlng.lat, lon: e.latlng.lng };
    if (queryMarker) map.removeLayer(queryMarker);
    queryMarker = L.marker([e.latlng.lat, e.latlng.lng]).addTo(map);
    document.querySelector(".query-controls__hint").textContent =
      `Query point: ${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)} (simulated, not a live position)`;
    runQuery();
  });
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("tab--active"));
      btn.classList.add("tab--active");
      activeMode = btn.dataset.mode;
      runQuery();
    });
  });
}

async function loadData() {
  const res = await fetch(DATA_URL);
  const geo = await res.json();
  AEDS = geo.features.map((f) => ({
    ...f.properties,
    LONGITUDE: f.geometry.coordinates[0],
    LATITUDE: f.geometry.coordinates[1],
  }));
  const nReal = AEDS.filter((a) => a.SOURCE === "real_sample").length;
  document.getElementById("datasetCount").textContent =
    `${AEDS.length} AEDs (${nReal} real, ${AEDS.length - nReal} synthetic)`;

  const layer = L.layerGroup().addTo(map);
  AEDS.forEach((a) => {
    L.circleMarker([a.LATITUDE, a.LONGITUDE], {
      radius: 3,
      color: a.SOURCE === "real_sample" ? "#2dd6b5" : "#5f6d8a",
      weight: 1,
      fillOpacity: 0.6,
    }).addTo(layer);
  });
}

document.getElementById("daySelect").addEventListener("change", runQuery);
document.getElementById("timeInput").addEventListener("change", runQuery);

initMap();
initTabs();
loadData();
