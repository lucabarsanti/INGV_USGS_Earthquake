/*
 * earthquake-map-card
 *
 * Lovelace card for the Earthquake Monitor (INGV + USGS + EMSC) integration.
 * Renders a Leaflet map (raster tiles: CARTO / OpenStreetMap) with the
 * earthquakes exposed by sensor.<name>_last_earthquake, plus a compact list
 * and interactive filters (magnitude, period, world mode).
 *
 * Leaflet is served locally by the integration (no CDN required).
 * Map © Leaflet | Tiles © CARTO / © OpenStreetMap contributors
 * Data: INGV (CC BY 4.0) + USGS (public domain) + EMSC
 */

const VENDOR_BASE = "/earthquake_monitor/vendor/leaflet";
const LEAFLET_JS = `${VENDOR_BASE}/leaflet.js`;
// __DEMO_LEAFLET_CSS is only set by docs/demo.html (standalone preview).
const LEAFLET_CSS = window.__DEMO_LEAFLET_CSS || `${VENDOR_BASE}/leaflet.css`;

// USGS world feed used by the "world" filter (CORS-enabled, public domain).
const WORLD_FEED =
  "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson";
const WORLD_CACHE_MS = 5 * 60 * 1000;

const DEFAULT_ZOOM = 7;
const WORLD_ZOOM = 2;

const TILES = {
  carto_light: {
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  carto_dark: {
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  osm: {
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
};

const STRINGS = {
  en: {
    no_quakes: "No earthquakes match the current filters.",
    home: "Home",
    details: "details",
    depth: "Depth",
    distance: "Distance",
    deep: "km deep",
    tsunami: "Tsunami warning",
    felt: "felt reports",
    offline: "Map assets could not be loaded. Showing list only.",
    not_found: "Entity not found:",
    all: "All",
    period_all: "All",
    world: "🌍 World",
    world_hint: "USGS M2.5+ last 24 h (worldwide)",
    world_error: "Could not load the USGS world feed.",
    loading: "Loading…",
  },
  it: {
    no_quakes: "Nessun terremoto con i filtri attuali.",
    home: "Casa",
    details: "dettagli",
    depth: "Profondità",
    distance: "Distanza",
    deep: "km di profondità",
    tsunami: "Allerta tsunami",
    felt: "segnalazioni",
    offline: "Impossibile caricare la mappa. Mostro solo la lista.",
    not_found: "Entità non trovata:",
    all: "Tutte",
    period_all: "Tutto",
    world: "🌍 Mondo",
    world_hint: "USGS M2.5+ ultime 24 h (tutto il mondo)",
    world_error: "Impossibile caricare il feed mondiale USGS.",
    loading: "Carico…",
  },
};

const MAG_FILTERS = [0, 2, 3, 4, 5];
const HOUR_FILTERS = [1, 6, 24, null]; // null = whole window

// Home marker: minimal house glyph with a white outline for contrast on
// both light and dark tiles. Kept small and rendered below quake markers.
const HOME_ICON_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">' +
  '<path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" fill="#1976d2" stroke="#ffffff" stroke-width="1.4" stroke-linejoin="round"/></svg>';

/** Escape untrusted text before it goes anywhere near innerHTML. */
function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Only allow plain http(s) URLs from the feeds. */
function safeUrl(url) {
  return typeof url === "string" && /^https?:\/\//.test(url) ? url : null;
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.sqrt(a));
}

let leafletLoader = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletLoader) {
    leafletLoader = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = LEAFLET_JS;
      script.onload = () => resolve(window.L);
      script.onerror = () => {
        leafletLoader = null;
        reject(new Error("Failed to load Leaflet"));
      };
      document.head.appendChild(script);
    });
  }
  return leafletLoader;
}

function magColor(mag) {
  if (mag >= 5.5) return "#d32f2f";
  if (mag >= 4.5) return "#f4511e";
  if (mag >= 3.5) return "#fb8c00";
  if (mag >= 2.5) return "#fdd835";
  return "#43a047";
}

function magRadius(mag) {
  return Math.max(5, 4 + mag * 2.2);
}

function relativeTime(iso, locale) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60000);
  const rtf = new Intl.RelativeTimeFormat(locale || "en", { numeric: "auto" });
  if (minutes < 60) return rtf.format(-minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 48) return rtf.format(-hours, "hour");
  return rtf.format(-Math.round(hours / 24), "day");
}

class EarthquakeMapCard extends HTMLElement {
  static getStubConfig(hass) {
    const entity =
      Object.keys(hass.states).find(
        (id) => id.startsWith("sensor.") && id.includes("last_earthquake")
      ) || "sensor.earthquake_monitor_last_earthquake";
    return { entity };
  }

  static async getConfigElement() {
    return document.createElement("earthquake-map-card-editor");
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Set 'entity' to the *_last_earthquake sensor");
    }
    this._config = {
      title: null,
      height: 380,
      zoom: null,
      tiles: "auto", // auto | carto_light | carto_dark | osm
      show_list: true,
      max_list: 8,
      show_radius: true,
      show_filters: true,
      follow_last: false,
      ...config,
    };
    this._filters = { mag: 0, hours: null, world: false };
    this._built = false;
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass.states[this._config.entity];
    const lang = this._lang();
    if (!state) {
      this._renderError(
        `${STRINGS[lang].not_found} ${esc(this._config.entity)}`
      );
      return;
    }
    if (!this._built) this._build();
    if (this._lastUpdated !== state.last_updated || this._darkChanged()) {
      this._lastUpdated = state.last_updated;
      this._attrs = state.attributes || {};
      this._render();
    }
  }

  _lang() {
    const language =
      (this._hass && this._hass.locale && this._hass.locale.language) || "en";
    return language.startsWith("it") ? "it" : "en";
  }

  _t() {
    return STRINGS[this._lang()];
  }

  _darkChanged() {
    const dark = !!(this._hass.themes && this._hass.themes.darkMode);
    if (dark !== this._dark) {
      this._dark = dark;
      return true;
    }
    return false;
  }

  _renderError(message) {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<ha-card><div style="padding:16px;">${message}</div></ha-card>`;
    this._built = false;
  }

  _build() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const height = Number(this._config.height) || 380;
    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="${LEAFLET_CSS}" />
      <style>
        ha-card { overflow: hidden; }
        .header {
          padding: 12px 16px 0;
          font-size: 1.15em;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        .filters {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 4px;
          padding: 8px 12px;
        }
        .chip {
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 14px;
          background: none;
          color: var(--secondary-text-color);
          font: inherit;
          font-size: 11.5px;
          padding: 3px 10px;
          cursor: pointer;
          line-height: 1.4;
        }
        .chip:hover { border-color: var(--primary-color, #03a9f4); }
        .chip.active {
          background: var(--primary-color, #03a9f4);
          border-color: var(--primary-color, #03a9f4);
          color: var(--text-primary-color, #fff);
        }
        .chip-sep {
          width: 1px;
          align-self: stretch;
          margin: 2px 4px;
          background: var(--divider-color, #e0e0e0);
        }
        .filters .status {
          font-size: 11px;
          color: var(--secondary-text-color);
          margin-left: auto;
          padding-left: 6px;
        }
        #map {
          height: ${height}px;
          width: 100%;
          background: var(--card-background-color, #fafafa);
          z-index: 0;
        }
        .leaflet-container { font: inherit; }
        .home-marker {
          background: none;
          border: none;
          opacity: 0.92;
          filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.45));
        }
        .quake-popup { font-size: 13px; line-height: 1.5; }
        .quake-popup .mag { font-weight: 700; }
        .quake-popup .tsunami { color: #d32f2f; font-weight: 700; }
        .quake-popup a { color: var(--primary-color, #03a9f4); }
        .list { padding: 4px 0 8px; }
        .row {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 6px 16px;
          cursor: pointer;
        }
        .row:hover { background: var(--secondary-background-color, #f0f0f0); }
        .badge {
          min-width: 40px;
          text-align: center;
          border-radius: 12px;
          padding: 3px 6px;
          font-weight: 700;
          font-size: 12px;
          color: #fff;
          flex-shrink: 0;
        }
        .info { flex: 1; min-width: 0; }
        .place {
          font-size: 13px;
          color: var(--primary-text-color);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .meta { font-size: 11.5px; color: var(--secondary-text-color); }
        .empty { padding: 16px; color: var(--secondary-text-color); }
      </style>
      <ha-card>
        <div class="header" id="title" hidden></div>
        <div class="filters" id="filters" hidden></div>
        <div id="map"></div>
        <div class="list" id="list"></div>
      </ha-card>
    `;
    this._built = true;
    this._mapReady = false;
    this._markers = [];
    this._renderSeq = 0;
    this._renderFilters();

    loadLeaflet()
      .then(() => this._initMap())
      .catch(() => {
        this.shadowRoot.getElementById("map").innerHTML = `<div class="empty">${
          this._t().offline
        }</div>`;
      });
  }

  _renderFilters() {
    const bar = this.shadowRoot.getElementById("filters");
    if (!this._config.show_filters) {
      bar.hidden = true;
      return;
    }
    bar.hidden = false;
    const t = this._t();
    bar.innerHTML = "";

    const addChip = (label, active, title, onClick) => {
      const chip = document.createElement("button");
      chip.className = "chip" + (active ? " active" : "");
      chip.textContent = label;
      if (title) chip.title = title;
      chip.addEventListener("click", onClick);
      bar.appendChild(chip);
    };
    const addSep = () => {
      const sep = document.createElement("div");
      sep.className = "chip-sep";
      bar.appendChild(sep);
    };

    for (const mag of MAG_FILTERS) {
      addChip(
        mag === 0 ? t.all : `M${mag}+`,
        this._filters.mag === mag,
        null,
        () => {
          this._filters.mag = mag;
          this._renderFilters();
          this._render();
        }
      );
    }
    addSep();
    for (const hours of HOUR_FILTERS) {
      addChip(
        hours === null ? t.period_all : `${hours}h`,
        this._filters.hours === hours,
        null,
        () => {
          this._filters.hours = hours;
          this._renderFilters();
          this._render();
        }
      );
    }
    addSep();
    addChip(t.world, this._filters.world, t.world_hint, () => {
      this._filters.world = !this._filters.world;
      this._renderFilters();
      this._render();
      if (this._mapReady) {
        const attrs = this._attrs || {};
        const home = [
          attrs.config_latitude ?? 20,
          attrs.config_longitude ?? 0,
        ];
        this._map.setView(
          home,
          this._filters.world
            ? WORLD_ZOOM
            : Number(this._config.zoom) || DEFAULT_ZOOM
        );
      }
    });

    const status = document.createElement("span");
    status.className = "status";
    status.id = "filter-status";
    bar.appendChild(status);
  }

  _setStatus(text) {
    const el = this.shadowRoot.getElementById("filter-status");
    if (el) el.textContent = text || "";
  }

  async _worldQuakes() {
    const now = Date.now();
    if (this._worldCache && now - this._worldCacheTs < WORLD_CACHE_MS) {
      return this._worldCache;
    }
    const attrs = this._attrs || {};
    const homeLat = attrs.config_latitude;
    const homeLon = attrs.config_longitude;
    const resp = await fetch(WORLD_FEED);
    if (!resp.ok) throw new Error(`USGS feed HTTP ${resp.status}`);
    const data = await resp.json();
    const quakes = [];
    for (const f of data.features || []) {
      const p = f.properties || {};
      const c = (f.geometry || {}).coordinates || [];
      if (p.mag == null || c.length < 2) continue;
      quakes.push({
        id: `usgs:${f.id}`,
        source: "usgs",
        magnitude: p.mag,
        mag_type: p.magType,
        place: p.place || "Unknown location",
        time: new Date(p.time).toISOString(),
        latitude: c[1],
        longitude: c[0],
        depth_km: c.length > 2 ? c[2] : null,
        url: p.url,
        distance_km:
          homeLat != null && homeLon != null
            ? haversineKm(homeLat, homeLon, c[1], c[0])
            : null,
        tsunami: !!p.tsunami,
        felt: p.felt || null,
        mmi: p.mmi || null,
      });
    }
    quakes.sort((a, b) => new Date(b.time) - new Date(a.time));
    this._worldCache = quakes;
    this._worldCacheTs = now;
    return quakes;
  }

  async _render() {
    if (!this._built || !this._attrs) return;
    const seq = ++this._renderSeq;
    const t = this._t();

    const titleEl = this.shadowRoot.getElementById("title");
    if (this._config.title) {
      titleEl.hidden = false;
      titleEl.textContent = this._config.title;
    }

    let quakes;
    if (this._filters.world) {
      this._setStatus(t.loading);
      try {
        quakes = await this._worldQuakes();
      } catch (err) {
        quakes = [];
        this._setStatus(t.world_error);
      }
      if (seq !== this._renderSeq) return; // superseded by a newer render
      if (quakes.length) this._setStatus(t.world_hint);
    } else {
      quakes = this._attrs.quakes || [];
      this._setStatus("");
    }

    if (this._filters.mag > 0) {
      quakes = quakes.filter((q) => q.magnitude >= this._filters.mag);
    }
    if (this._filters.hours != null) {
      const cutoff = Date.now() - this._filters.hours * 3600 * 1000;
      quakes = quakes.filter((q) => new Date(q.time).getTime() >= cutoff);
    }

    const locale = (this._hass.locale && this._hass.locale.language) || "en";
    this._renderList(quakes, locale, t);
    this._renderMap(quakes, locale, t);
  }

  _tileConfig() {
    let key = this._config.tiles;
    if (key === "auto" || key === "carto") {
      key = this._dark ? "carto_dark" : "carto_light";
    }
    return TILES[key] || TILES.carto_light;
  }

  _initMap() {
    const L = window.L;
    const mapEl = this.shadowRoot.getElementById("map");
    this._map = L.map(mapEl, { zoomControl: true, attributionControl: true });
    this._map.setView([42.5, 12.5], Number(this._config.zoom) || DEFAULT_ZOOM);
    // Home pane sits between the tiles (200) and the quake overlay (400),
    // so the house stays visible but never covers earthquake markers.
    this._map.createPane("homePane").style.zIndex = 350;
    const tiles = this._tileConfig();
    this._tileLayer = L.tileLayer(tiles.url, {
      attribution: tiles.attribution,
      maxZoom: 19,
    }).addTo(this._map);
    this._layerGroup = L.layerGroup().addTo(this._map);
    this._mapReady = true;
    this._centeredOnce = false;

    new ResizeObserver(() => this._map && this._map.invalidateSize()).observe(
      mapEl
    );
    this._render();
  }

  _popupHtml(q, locale, t) {
    const time = new Date(q.time).toLocaleString(locale);
    const url = safeUrl(q.url);
    const link = url
      ? `<br><a href="${esc(url)}" target="_blank" rel="noreferrer noopener">${esc(
          q.source.toUpperCase()
        )} ${t.details}</a>`
      : "";
    const tsunami = q.tsunami
      ? `<br><span class="tsunami">🌊 ${t.tsunami}</span>`
      : "";
    const felt = q.felt ? ` · ${esc(q.felt)} ${t.felt}` : "";
    return `<div class="quake-popup">
        <span class="mag" style="color:${magColor(q.magnitude)}">M ${esc(
          q.magnitude.toFixed(1)
        )}${q.mag_type ? " " + esc(q.mag_type) : ""}</span>
        — ${esc(q.place)}<br>
        ${esc(time)} (${esc(relativeTime(q.time, locale))})<br>
        ${t.depth}: ${q.depth_km != null ? esc(q.depth_km.toFixed(1)) + " km" : "n/a"} ·
        ${t.distance}: ${
          q.distance_km != null ? esc(q.distance_km.toFixed(0)) + " km" : "n/a"
        }${felt}${tsunami}${link}
      </div>`;
  }

  _renderMap(quakes, locale, t) {
    if (!this._mapReady) return;
    const L = window.L;

    // Swap tiles when the theme changes.
    const tiles = this._tileConfig();
    if (this._tileUrl !== tiles.url) {
      this._tileUrl = tiles.url;
      this._tileLayer.setUrl(tiles.url);
    }

    this._layerGroup.clearLayers();
    this._markers = [];

    const attrs = this._attrs || {};
    const homeLat = attrs.config_latitude;
    const homeLon = attrs.config_longitude;

    if (homeLat != null && homeLon != null) {
      const homeIcon = L.divIcon({
        className: "home-marker",
        html: HOME_ICON_SVG,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
      L.marker([homeLat, homeLon], {
        icon: homeIcon,
        pane: "homePane",
        interactive: true,
        keyboard: false,
      })
        .bindTooltip(t.home)
        .addTo(this._layerGroup);
      if (
        this._config.show_radius &&
        attrs.alert_radius_km &&
        !this._filters.world
      ) {
        L.circle([homeLat, homeLon], {
          radius: attrs.alert_radius_km * 1000,
          color: "#d32f2f",
          weight: 1,
          dashArray: "6 6",
          fill: false,
        }).addTo(this._layerGroup);
      }
    }

    for (const q of quakes) {
      const marker = L.circleMarker([q.latitude, q.longitude], {
        radius: magRadius(q.magnitude),
        color: magColor(q.magnitude),
        weight: 1.5,
        fillColor: magColor(q.magnitude),
        fillOpacity: 0.55,
      });
      marker.bindPopup(this._popupHtml(q, locale, t));
      marker.addTo(this._layerGroup);
      this._markers.push({ id: q.id, marker });
    }

    if (!this._centeredOnce || this._config.follow_last) {
      if (quakes.length && this._config.follow_last) {
        this._map.setView(
          [quakes[0].latitude, quakes[0].longitude],
          Number(this._config.zoom) || DEFAULT_ZOOM
        );
      } else if (homeLat != null && homeLon != null && !this._centeredOnce) {
        this._map.setView(
          [homeLat, homeLon],
          Number(this._config.zoom) || DEFAULT_ZOOM
        );
      }
      this._centeredOnce = true;
    }
  }

  _renderList(quakes, locale, t) {
    const listEl = this.shadowRoot.getElementById("list");
    if (!this._config.show_list) {
      listEl.innerHTML = "";
      return;
    }
    if (!quakes.length) {
      listEl.innerHTML = `<div class="empty">${t.no_quakes}</div>`;
      return;
    }
    listEl.innerHTML = "";
    for (const q of quakes.slice(0, this._config.max_list)) {
      const row = document.createElement("div");
      row.className = "row";
      const meta = [
        relativeTime(q.time, locale),
        q.distance_km != null ? `${q.distance_km.toFixed(0)} km` : null,
        q.depth_km != null ? `${q.depth_km.toFixed(0)} ${t.deep}` : null,
        q.source.toUpperCase(),
        q.tsunami ? "🌊" : null,
      ]
        .filter(Boolean)
        .join(" · ");
      row.innerHTML = `
        <span class="badge" style="background:${magColor(
          q.magnitude
        )}">M ${esc(q.magnitude.toFixed(1))}</span>
        <span class="info">
          <div class="place">${esc(q.place)}</div>
          <div class="meta">${esc(meta)}</div>
        </span>`;
      row.addEventListener("click", () => {
        if (!this._mapReady) return;
        this._map.setView([q.latitude, q.longitude], 8);
        const found = this._markers.find((m) => m.id === q.id);
        if (found) found.marker.openPopup();
      });
      listEl.appendChild(row);
    }
  }

  getCardSize() {
    const mapRows = Math.ceil((Number(this._config.height) || 380) / 50);
    return mapRows + (this._config.show_list ? 3 : 0);
  }
}

class EarthquakeMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _schema() {
    return [
      {
        name: "entity",
        required: true,
        selector: { entity: { domain: "sensor" } },
      },
      { name: "title", selector: { text: {} } },
      {
        name: "height",
        selector: { number: { min: 150, max: 900, mode: "box" } },
      },
      { name: "zoom", selector: { number: { min: 1, max: 15, mode: "box" } } },
      {
        name: "tiles",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "auto", label: "Auto (CARTO, follows theme)" },
              { value: "carto_light", label: "CARTO light" },
              { value: "carto_dark", label: "CARTO dark" },
              { value: "osm", label: "OpenStreetMap" },
            ],
          },
        },
      },
      { name: "show_list", selector: { boolean: {} } },
      {
        name: "max_list",
        selector: { number: { min: 1, max: 50, mode: "box" } },
      },
      { name: "show_radius", selector: { boolean: {} } },
      { name: "show_filters", selector: { boolean: {} } },
      { name: "follow_last", selector: { boolean: {} } },
    ];
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) =>
        schema.name.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
      this._form.addEventListener("value-changed", (ev) => {
        const config = { type: "custom:earthquake-map-card", ...ev.detail.value };
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = this._schema();
  }
}

customElements.define("earthquake-map-card", EarthquakeMapCard);
customElements.define("earthquake-map-card-editor", EarthquakeMapCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "earthquake-map-card",
  name: "Earthquake Map Card",
  description:
    "Leaflet map + list of recent earthquakes from the Earthquake Monitor (INGV + USGS + EMSC) integration.",
  preview: false,
});
