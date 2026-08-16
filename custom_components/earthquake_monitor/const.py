"""Constants for the Earthquake Monitor (INGV + USGS) integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "earthquake_monitor"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.GEO_LOCATION,
]

# Configuration keys
CONF_SOURCES = "sources"
CONF_RADIUS = "radius_km"
CONF_MIN_MAGNITUDE = "min_magnitude"
CONF_ALERT_RADIUS = "alert_radius_km"
CONF_ALERT_MIN_MAGNITUDE = "alert_min_magnitude"
CONF_ALERT_WINDOW = "alert_window_minutes"
CONF_LOOKBACK = "lookback_hours"
CONF_SCAN_INTERVAL = "scan_interval_minutes"

# Source identifiers
SOURCE_INGV = "ingv"
SOURCE_USGS = "usgs"
# Reserved for a future local seismograph source (Raspberry Shake, MQTT, ...).
SOURCE_LOCAL = "local"

DEFAULT_NAME = "Earthquake Monitor"
DEFAULT_SOURCES = [SOURCE_INGV, SOURCE_USGS]
DEFAULT_RADIUS_KM = 500.0
DEFAULT_MIN_MAGNITUDE = 2.0
DEFAULT_ALERT_RADIUS_KM = 100.0
DEFAULT_ALERT_MIN_MAGNITUDE = 3.5
DEFAULT_ALERT_WINDOW_MINUTES = 60
DEFAULT_LOOKBACK_HOURS = 24
DEFAULT_SCAN_INTERVAL_MINUTES = 5

MIN_SCAN_INTERVAL_MINUTES = 1
MAX_QUAKES_KEPT = 200
MAX_QUAKES_IN_ATTRIBUTES = 50

# Event fired for every newly detected earthquake.
EVENT_QUAKE = f"{DOMAIN}_quake"

# Frontend card
URL_BASE = f"/{DOMAIN}"
CARD_FILENAME = "earthquake-map-card.js"

ATTRIBUTION = (
    "Data: INGV (FDSN web services, CC BY 4.0) and USGS (GeoJSON feeds, public domain)"
)
