# Earthquake Monitor (INGV + USGS + EMSC)

Real-time earthquakes from **INGV**, **USGS** and **EMSC** in Home Assistant:
sensors, alert binary sensor, `geo_location` entities, events for
notifications (`earthquake_monitor_quake` / `_quake_updated`), a
`simulate_quake` test service, a notification blueprint and a **Leaflet map
card** (auto-registered, visual editor, Leaflet bundled locally) with
CARTO / OpenStreetMap tiles.

Terremoti in tempo reale da **INGV**, **USGS** ed **EMSC** in Home Assistant:
sensori, sensore di allerta, entità `geo_location`, eventi per le notifiche
(`earthquake_monitor_quake` / `_quake_updated`), servizio di test
`simulate_quake`, blueprint di notifica e **scheda mappa Leaflet**
(registrata automaticamente, editor visuale, Leaflet incluso in locale) con
tile CARTO / OpenStreetMap.

⚠️ Not an early-warning system / Non è un sistema di allarme sismico.

Data: INGV FDSN (CC BY 4.0) · USGS GeoJSON (public domain) · EMSC seismicportal.
