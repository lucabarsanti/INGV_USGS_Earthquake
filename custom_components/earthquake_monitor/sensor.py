"""Sensors for Earthquake Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_QUAKES_IN_ATTRIBUTES
from .coordinator import EarthquakeCoordinator
from .entity import EarthquakeMonitorEntity
from .models import Quake


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: EarthquakeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LastEarthquakeSensor(coordinator),
            NearestEarthquakeSensor(coordinator),
            StrongestEarthquakeSensor(coordinator),
            EarthquakeCountSensor(coordinator),
        ]
    )


def _quake_attributes(quake: Quake | None) -> dict[str, Any]:
    if quake is None:
        return {}
    return quake.as_dict()


class LastEarthquakeSensor(EarthquakeMonitorEntity, SensorEntity):
    """Most recent earthquake; carries the full quake list for the map card."""

    _attr_icon = "mdi:pulse"
    _attr_native_unit_of_measurement = "M"
    # The quakes list is for the card / templates only — keep it out of the DB.
    _unrecorded_attributes = frozenset({"quakes"})

    def __init__(self, coordinator: EarthquakeCoordinator) -> None:
        super().__init__(coordinator, "last_earthquake")

    @property
    def native_value(self) -> float | None:
        last = self.coordinator.data.last
        return last.magnitude if last else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        coordinator = self.coordinator
        return {
            **_quake_attributes(coordinator.data.last),
            "config_latitude": coordinator.latitude,
            "config_longitude": coordinator.longitude,
            "radius_km": coordinator.radius_km,
            "alert_radius_km": coordinator.alert_radius_km,
            "min_magnitude": coordinator.min_magnitude,
            "alert_min_magnitude": coordinator.alert_min_magnitude,
            "quakes": [
                q.as_dict()
                for q in coordinator.data.quakes[:MAX_QUAKES_IN_ATTRIBUTES]
            ],
        }


class NearestEarthquakeSensor(EarthquakeMonitorEntity, SensorEntity):
    """Distance to the closest earthquake in the monitored window."""

    _attr_icon = "mdi:map-marker-distance"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: EarthquakeCoordinator) -> None:
        super().__init__(coordinator, "nearest_earthquake")

    @property
    def native_value(self) -> float | None:
        nearest = self.coordinator.data.nearest
        return nearest.distance_km if nearest else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _quake_attributes(self.coordinator.data.nearest)


class StrongestEarthquakeSensor(EarthquakeMonitorEntity, SensorEntity):
    """Strongest earthquake in the monitored window."""

    _attr_icon = "mdi:chart-bell-curve"
    _attr_native_unit_of_measurement = "M"

    def __init__(self, coordinator: EarthquakeCoordinator) -> None:
        super().__init__(coordinator, "strongest_earthquake")

    @property
    def native_value(self) -> float | None:
        strongest = self.coordinator.data.strongest
        return strongest.magnitude if strongest else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _quake_attributes(self.coordinator.data.strongest)


class EarthquakeCountSensor(EarthquakeMonitorEntity, SensorEntity):
    """Number of earthquakes in the monitored window."""

    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EarthquakeCoordinator) -> None:
        super().__init__(coordinator, "earthquake_count")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.quakes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        by_source: dict[str, int] = {}
        for quake in self.coordinator.data.quakes:
            by_source[quake.source] = by_source.get(quake.source, 0) + 1
        return {"by_source": by_source}
