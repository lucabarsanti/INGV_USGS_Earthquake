/*
 * earthquake-map-card
 *
 * Lovelace card for the Earthquake Monitor (INGV + USGS) integration.
 * Renders a Leaflet map (raster tiles: CARTO / OpenStreetMap) with the
 * earthquakes exposed by sensor.<name>_last_earthquake, plus a compact list.
 *
 * Map © Leaflet | Tiles © CARTO / © OpenStreetMap contributors
 * Data: INGV (CC BY 4.0) + USGS (public domain)
 */

const LEAFLET_VERSION = "1.9.4";
const LEAFLET_JS = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.js`;
const LEAFLET_CSS = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.css`;

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

let leafletLoader = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletLoader) {
    leafletLoader = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = LEAFLET_JS;
      script.onload = () => resolve(window.L);
      script.onerror = () => reject(new Error("Failed to load Leaflet"));
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
      follow_last: false,
      ...config,
    };
    this._built = false;
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass.states[this._config.entity];
    if (!state) {
      this._renderError(`Entity not found: ${this._config.entity}`);
      return;
    }
    if (!this._built) this._build();
    if (this._lastUpdated !== state.last_updated || this._darkChanged()) {
      this._lastUpdated = state.last_updated;
      this._update(state);
    }
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
        #map {
          height: ${height}px;
          width: 100%;
          background: var(--card-background-color, #fafafa);
          z-index: 0;
        }
        .leaflet-container { font: inherit; }
        .quake-popup { font-size: 13px; line-height: 1.5; }
        .quake-popup .mag { font-weight: 700; }
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
        <div id="map"></div>
        <div class="list" id="list"></div>
      </ha-card>
    `;
    this._built = true;
    this._mapReady = false;
    this._markers = [];

    loadLeaflet()
      .then(() => this._initMap())
      .catch(() => {
        this.shadowRoot.getElementById("map").innerHTML =
          '<div class="empty">Leaflet could not be loaded (offline?). Showing list only.</div>';
      });
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
    this._map.setView([42.5, 12.5], Number(this._config.zoom) || 6);
    const tiles = this._tileConfig();
    this._tileLayer = L.tileLayer(tiles.url, {
      attribution: tiles.attribution,
      maxZoom: 19,
    }).addTo(this._map);
    this._layerGroup = L.layerGroup().addTo(this._map);
    this._mapReady = true;

    new ResizeObserver(() => this._map && this._map.invalidateSize()).observe(
      mapEl
    );

    const state = this._hass.states[this._config.entity];
    if (state) this._update(state, true);
  }

  _update(state, initial = false) {
    const attrs = state.attributes || {};
    const quakes = attrs.quakes || [];
    const locale = (this._hass.locale && this._hass.locale.language) || "en";

    const titleEl = this.shadowRoot.getElementById("title");
    if (this._config.title) {
      titleEl.hidden = false;
      titleEl.textContent = this._config.title;
    }

    this._renderList(quakes, locale);

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

    const homeLat = attrs.config_latitude;
    const homeLon = attrs.config_longitude;

    if (homeLat != null && homeLon != null) {
      L.circleMarker([homeLat, homeLon], {
        radius: 6,
        color: "#1976d2",
        fillColor: "#1976d2",
        fillOpacity: 0.9,
      })
        .bindTooltip("Home")
        .addTo(this._layerGroup);
      if (this._config.show_radius && attrs.alert_radius_km) {
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
      const time = new Date(q.time).toLocaleString(locale);
      const link = q.url
        ? `<br><a href="${q.url}" target="_blank" rel="noreferrer">${q.source.toUpperCase()} details</a>`
        : "";
      marker.bindPopup(
        `<div class="quake-popup">
           <span class="mag" style="color:${magColor(q.magnitude)}">M ${q.magnitude.toFixed(1)}${q.mag_type ? " " + q.mag_type : ""}</span>
           — ${q.place}<br>
           ${time} (${relativeTime(q.time, locale)})<br>
           Depth: ${q.depth_km != null ? q.depth_km.toFixed(1) + " km" : "n/a"} ·
           Distance: ${q.distance_km != null ? q.distance_km.toFixed(0) + " km" : "n/a"}${link}
         </div>`
      );
      marker.addTo(this._layerGroup);
      this._markers.push({ id: q.id, marker });
    }

    if (initial || this._config.follow_last) {
      if (quakes.length && this._config.follow_last) {
        this._map.setView(
          [quakes[0].latitude, quakes[0].longitude],
          Number(this._config.zoom) || 7
        );
      } else if (homeLat != null && homeLon != null) {
        this._map.setView(
          [homeLat, homeLon],
          Number(this._config.zoom) || 6
        );
      }
    }
  }

  _renderList(quakes, locale) {
    const listEl = this.shadowRoot.getElementById("list");
    if (!this._config.show_list) {
      listEl.innerHTML = "";
      return;
    }
    if (!quakes.length) {
      listEl.innerHTML = '<div class="empty">No earthquakes in the monitored window.</div>';
      return;
    }
    listEl.innerHTML = "";
    for (const q of quakes.slice(0, this._config.max_list)) {
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `
        <span class="badge" style="background:${magColor(q.magnitude)}">M ${q.magnitude.toFixed(1)}</span>
        <span class="info">
          <div class="place">${q.place}</div>
          <div class="meta">${relativeTime(q.time, locale)} · ${
            q.distance_km != null ? q.distance_km.toFixed(0) + " km" : ""
          } · ${q.depth_km != null ? q.depth_km.toFixed(0) + " km deep" : ""} · ${q.source.toUpperCase()}</div>
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

customElements.define("earthquake-map-card", EarthquakeMapCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "earthquake-map-card",
  name: "Earthquake Map Card",
  description:
    "Leaflet map + list of recent earthquakes from the Earthquake Monitor (INGV + USGS) integration.",
  preview: false,
});
