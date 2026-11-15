/* Chaman Places Atlas - front end. Talks to the Flask/PostGIS API (see api/app.py). */
(() => {
  const API = window.API_BASE || "";            // same origin by default
  const CATS = {
    "Police station": { cls: "police", color: "#1f4e9e", label: "Police station" },
    "Park":           { cls: "park",   color: "#2a9d4f", label: "Park" },
    "Petrol station": { cls: "petrol", color: "#e67e22", label: "Petrol station" },
  };
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const km = (m) => (m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(2)} km`);

  // ------------------------------------------------------------------ map
  const map = L.map("map").setView([30.91, 66.45], 13);
  const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
  const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 19, attribution: "Tiles &copy; Esri" });
  L.control.layers({ "OpenStreetMap": osm, "Satellite (Esri)": sat }, {}, { collapsed: true }).addTo(map);
  L.control.scale({ imperial: false }).addTo(map);

  const placeLayer = L.layerGroup().addTo(map);
  const nearestLayer = L.layerGroup().addTo(map);
  const markers = new Map();                       // id -> marker
  let studyBounds = null;

  // legend (shape + colour)
  const legend = L.control({ position: "bottomright" });
  legend.onAdd = () => {
    const d = L.DomUtil.create("div", "legend");
    d.innerHTML = "<h4>Legend</h4>" +
      Object.values(CATS).map((c) => `<div><span class="sym ${c.cls}"></span>${esc(c.label)}</div>`).join("") +
      '<hr><div><span class="box"></span>Study area extent</div>' +
      '<div><span class="dot" style="background:#f4a300"></span>Nearest result</div>';
    return d;
  };
  legend.addTo(map);

  // ------------------------------------------------------------------ helpers
  async function getJSON(path) {
    const r = await fetch(API + path);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
    return body;
  }
  const showError = (msg) => { $("badges").innerHTML = `<span class="badge" style="background:#b3261e">⚠ ${esc(msg)}</span>`; };

  function icon(cat) {
    return L.divIcon({ className: "mkwrap", html: `<div class="mk ${CATS[cat].cls}"></div>`,
                       iconSize: [22, 22], iconAnchor: [11, 11], popupAnchor: [0, -11] });
  }

  function popupHTML(p, lat, lon) {
    const row = (k, v) => (v ? `<tr><td>${k}</td><td>${v}</td></tr>` : "");
    const c = CATS[p.category];
    const phone = p.phone ? `<a href="tel:${esc(p.phone.replace(/[^+\d]/g, ""))}">${esc(p.phone)}</a>` : "";
    const web = /^https?:\/\//i.test(p.website || "") ? `<a href="${esc(p.website)}" target="_blank" rel="noopener">Website</a>` : "";
    const dir = `<a href="https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}" target="_blank" rel="noopener">Directions</a>`;
    const hours = p.open_24h ? "Open 24/7" : esc(p.opening_hours);
    let specific = row("Type", esc(p.subtype));
    if (p.category === "Police station") specific += row("Operator", esc(p.operator));
    if (p.category === "Park") specific += row("Access", esc(p.access)) + row("Entry fee", esc(p.fee));
    if (p.category === "Petrol station") specific += row("Brand", esc(p.brand)) + row("Fuel", esc(p.fuel_types)) + row("Operator", esc(p.operator));
    return `<div class="pop"><h3>${esc(p.name)}</h3>
      <div class="tags"><span class="tag" style="background:${c.color}">${esc(p.category)}</span>${p.open_24h ? '<span class="tag own">24/7</span>' : ""}</div>
      <table>${specific}${row("Address", esc(p.address))}${row("Phone", phone)}${row("Hours", hours)}
        ${row("Source", esc(p.source))}${row("Coordinates", `${lat.toFixed(5)}, ${lon.toFixed(5)}`)}</table>
      <p style="margin:6px 0 0">${dir}${web ? " · " + web : ""}</p></div>`;
  }

  // ------------------------------------------------------------------ category filter checkboxes
  const fs = $("typeFilters");
  Object.entries(CATS).forEach(([k, c]) => {
    const l = document.createElement("label");
    l.className = "chk";
    l.style.margin = "0";
    l.innerHTML = `<input type="checkbox" value="${esc(k)}" checked><span class="sym ${c.cls}"></span>${esc(k)}`;
    fs.appendChild(l);
  });

  // ------------------------------------------------------------------ data loading
  function currentQuery() {
    const cats = [...fs.querySelectorAll("input:checked")].map((i) => i.value);
    if (cats.length === 0) return null;
    const q = new URLSearchParams();
    if (cats.length < Object.keys(CATS).length) q.set("category", cats.join(","));
    if ($("open24").checked) q.set("open24", "1");
    if ($("search").value.trim()) q.set("q", $("search").value.trim());
    return q.toString();
  }

  async function loadPlaces() {
    const qs = currentQuery();
    placeLayer.clearLayers();
    markers.clear();
    const list = $("list");
    list.innerHTML = "";
    if (qs === null) { $("count").textContent = "(0)"; return; }
    try {
      const fc = await getJSON("/api/places" + (qs ? "?" + qs : ""));
      $("count").textContent = `(${fc.features.length})`;
      fc.features.forEach((f) => {
        const [lon, lat] = f.geometry.coordinates;
        const p = f.properties;
        const m = L.marker([lat, lon], { icon: icon(p.category), title: p.name, riseOnHover: true })
          .bindPopup(popupHTML(p, lat, lon)).bindTooltip(p.name).addTo(placeLayer);
        markers.set(p.id, m);
        const li = document.createElement("li");
        li.tabIndex = 0;
        li.innerHTML = `<span class="sym ${CATS[p.category].cls}" style="margin-top:3px"></span><span>${esc(p.name)}<small>${esc(p.subtype || p.category)}${p.open_24h ? " · 24/7" : ""}</small></span>`;
        const open = () => { map.setView(m.getLatLng(), Math.max(map.getZoom(), 16)); m.openPopup(); };
        li.addEventListener("click", open);
        li.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
        list.appendChild(li);
      });
      if (!fc.features.length) list.innerHTML = '<li style="cursor:default">No place matches these filters.</li>';
    } catch (e) { showError(e.message); }
  }

  async function loadStudyArea() {
    const f = await getJSON("/api/study-area");
    const layer = L.geoJSON(f, { style: { color: "#0f5c6e", weight: 2, dashArray: "6 5", fillColor: "#0f5c6e", fillOpacity: 0.05 }, interactive: false }).addTo(map);
    studyBounds = layer.getBounds();
    map.fitBounds(studyBounds.pad(0.05));
  }

  async function loadStats() {
    const s = await getJSON("/api/stats");
    $("badges").innerHTML = `<span class="badge"><b>${s.total}</b> places</span>` +
      s.by_category.map((t) => `<span class="badge">${t.count} ${esc(t.label.toLowerCase())}${t.count === 1 ? "" : "s"}</span>`).join("");
    const n = Object.fromEntries(s.by_category.map((c) => [c.label, c.count]));
    $("facts").innerHTML = `<dt>Total points</dt><dd>${s.total}</dd><dt>Police stations</dt><dd>${n["Police station"] || 0}</dd>` +
      `<dt>Parks</dt><dd>${n["Park"] || 0}</dd><dt>Petrol stations</dt><dd>${n["Petrol station"] || 0}</dd>` +
      `<dt>Open 24/7</dt><dd>${s.open_24h}</dd>`;
  }

  // ------------------------------------------------------------------ nearest places
  async function findNearest(lat, lng) {
    nearestLayer.clearLayers();
    L.marker([lat, lng], { title: "Selected location" }).addTo(nearestLayer);
    const cat = $("nearCat").value;
    try {
      const fc = await getJSON(`/api/places/nearest?lat=${lat}&lng=${lng}&limit=5` + (cat ? `&category=${encodeURIComponent(cat)}` : ""));
      const ol = $("nearest");
      ol.innerHTML = "";
      fc.features.forEach((f) => {
        const [lon, la] = f.geometry.coordinates, p = f.properties;
        L.polyline([[lat, lng], [la, lon]], { color: "#f4a300", weight: 2, dashArray: "4 4", interactive: false }).addTo(nearestLayer);
        L.circleMarker([la, lon], { radius: 14, color: "#f4a300", weight: 3, fill: false, interactive: false }).addTo(nearestLayer);
        const li = document.createElement("li");
        li.innerHTML = `${esc(p.name)} <span>– ${km(p.distance_m)} · ${esc(p.category)}</span>`;
        li.addEventListener("click", () => { const m = markers.get(p.id); if (m) { map.setView(m.getLatLng(), 16); m.openPopup(); } });
        ol.appendChild(li);
      });
      if (!fc.features.length) ol.innerHTML = "<li>Nothing found.</li>";
    } catch (e) { showError(e.message); }
  }
  map.on("click", (e) => findNearest(e.latlng.lat, e.latlng.lng));
  $("locate").addEventListener("click", () => {
    if (!navigator.geolocation) { alert("Geolocation is not supported by this browser."); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => { map.setView([pos.coords.latitude, pos.coords.longitude], 14); findNearest(pos.coords.latitude, pos.coords.longitude); },
      () => alert("Could not get your location. Click on the map instead."));
  });

  // ------------------------------------------------------------------ events + start
  let t;
  fs.addEventListener("change", loadPlaces);
  $("open24").addEventListener("change", loadPlaces);
  $("search").addEventListener("input", () => { clearTimeout(t); t = setTimeout(loadPlaces, 250); });
  $("reset").addEventListener("click", () => {
    fs.querySelectorAll("input").forEach((i) => (i.checked = true));
    $("open24").checked = false; $("search").value = "";
    nearestLayer.clearLayers(); $("nearest").innerHTML = "";
    loadPlaces();
    if (studyBounds) map.fitBounds(studyBounds.pad(0.05));
  });

  (async () => {
    try { await Promise.all([loadStudyArea(), loadStats()]); } catch (e) { showError(e.message); }
    loadPlaces();
  })();
})();
