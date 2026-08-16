# Changelog

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
