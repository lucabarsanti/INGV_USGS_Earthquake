# Contributing

Thanks for your interest! / Grazie per l'interesse!

## Adding a new earthquake source (e.g. a local seismograph)

1. Create `custom_components/earthquake_monitor/sources/<key>.py`
2. Subclass `EarthquakeSource` (`sources/base.py`) and implement
   `async_fetch(...)`, returning normalized `Quake` objects (UTC times,
   depth in km, a stable `id` prefixed with your source key).
3. Register the class in `SOURCE_REGISTRY` (`sources/__init__.py`).
4. Add the source label to `strings.json` and `translations/*.json` under
   `selector.sources.options`.

That's it — the coordinator, sensors, alerts, events, blueprint and map card
pick the new source up automatically.

## Development

- Python side follows Home Assistant custom integration conventions
  (async only, no blocking I/O, `DataUpdateCoordinator`).
- The card (`www/earthquake-map-card.js`) is dependency-free vanilla JS;
  Leaflet is loaded at runtime.
- CI runs `hassfest` and HACS validation on every push/PR.

Please open an issue before large changes.
