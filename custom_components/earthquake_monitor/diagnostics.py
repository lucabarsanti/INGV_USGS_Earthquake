"""Diagnostics support for Earthquake Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EarthquakeCoordinator

# Coordinates could reveal the home location.
REDACT_KEYS = {"latitude", "longitude", "config_latitude", "config_longitude"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EarthquakeCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    def redact(mapping: dict[str, Any]) -> dict[str, Any]:
        return {
            k: "**REDACTED**" if k in REDACT_KEYS else v for k, v in mapping.items()
        }

    return {
        "options": redact({**entry.data, **entry.options}),
        "sources": [source.key for source in coordinator.sources],
        "quake_count": len(data.quakes),
        "alert_quake_count": len(coordinator.current_alert_quakes()),
        "last_alert_time": coordinator.last_alert_time.isoformat()
        if coordinator.last_alert_time
        else None,
        "last_quake": redact(data.last.as_dict()) if data.last else None,
        "last_update_success": coordinator.last_update_success,
    }
