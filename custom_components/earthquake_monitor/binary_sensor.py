"""Alert binary sensor for Earthquake Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EarthquakeCoordinator
from .entity import EarthquakeMonitorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: EarthquakeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EarthquakeAlertBinarySensor(coordinator)])


class EarthquakeAlertBinarySensor(EarthquakeMonitorEntity, BinarySensorEntity):
    """On when a recent earthquake matches the alert distance and magnitude."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: EarthquakeCoordinator) -> None:
        super().__init__(coordinator, "earthquake_alert")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.alert_quakes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        coordinator = self.coordinator
        matching = coordinator.data.alert_quakes
        return {
            "alert_radius_km": coordinator.alert_radius_km,
            "alert_min_magnitude": coordinator.alert_min_magnitude,
            "alert_window_minutes": int(
                coordinator.alert_window.total_seconds() // 60
            ),
            "matching_quakes": [q.as_dict() for q in matching],
            "latest_alert": matching[0].as_dict() if matching else None,
        }
