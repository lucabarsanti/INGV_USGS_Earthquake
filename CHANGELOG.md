# Changelog

## 0.2.1 (2026-08-17)

- Card: the home position is now a **house marker** instead of a blue dot
- New minimal project **icon** (docs/icon.svg + PNGs, ready for the
  home-assistant/brands submission), shown in the README

## 0.2.0 (2026-08-16)

Robustness & features release / Solidità e nuove funzioni.

### Added
- **EMSC** (European-Mediterranean Seismological Centre) as a third source
- **`simulate_quake` service** to test automations and notifications
- `earthquake_monitor_quake_updated` event on significant magnitude revisions (≥ 0.3)
- `sensor.*_last_alert` timestamp sensor, persisted across restarts
- USGS extras per quake: tsunami flag, felt reports, ShakeMap MMI
- Maximum depth filter option
- Card: **visual editor**, IT/EN localization, tsunami/felt info in popups
- Connection test in the config/options flow (`cannot_connect`)
- Repair issues when a source keeps failing (auto-resolved on recovery)
- Seen-quake state persisted (no missed events after a restart, no duplicates)
- Alert binary sensor now turns off punctually (expiry timer)
- Notification blueprint: multiple devices, "only integration alerts" option
- Full test suite (pytest-homeassistant-custom-component) + ruff, run in CI
- Release workflow, Dependabot, issue templates, README screenshot

### Changed
- **Leaflet is now bundled and served locally** — no CDN, works offline
- De-duplication priority is now INGV > EMSC > USGS

## 0.1.0 (2026-08-16)

Initial release / Prima versione.

- INGV (FDSN) + USGS (FDSN/GeoJSON) sources with cross-network de-duplication
- Config flow + options flow (radius, magnitudes, alert settings, interval)
- Sensors: last / nearest / strongest earthquake, earthquake count
- `binary_sensor` earthquake alert (distance + magnitude + time window)
- `geo_location` entities for the built-in Home Assistant map
- `earthquake_monitor_quake` event for automations
- Notification blueprint (Companion app, optional critical alerts)
- `earthquake-map-card` Lovelace card (Leaflet, CARTO/OSM tiles, dark mode)
- `earthquake_monitor.refresh` service, diagnostics, EN/IT translations
- Pluggable source architecture, local seismograph planned (`sources/local.py`)
