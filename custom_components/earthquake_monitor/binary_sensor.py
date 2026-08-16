"""Alert binary sensor for Earthquake Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time

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
    """On when a recent earthquake matches the alert distance and magnitude.

    The alert window is evaluated at read time and a timer re-writes the state
    exactly when the newest matching quake leaves the window, so the sensor
    turns off punctually instead of waiting for the next poll.
    """

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _unrecorded_attributes = frozenset({"matching_quakes"})

    def __init__(self, coordinator: EarthquakeCoordinator) -> None:
        super().__init__(coordinator, "earthquake_alert")
        self._expiry_unsub = None

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.current_alert_quakes())

    def _schedule_expiry(self) -> None:
        if self._expiry_unsub is not None:
            self._expiry_unsub()
            self._expiry_unsub = None
        matching = self.coordinator.current_alert_quakes()
        if not matching:
            return
        newest = max(matching, key=lambda q: q.time)
        expiry = newest.time + self.coordinator.alert_window

        @callback
        def _on_expiry(_now) -> None:
            self._expiry_unsub = None
            self.async_write_ha_state()
            self._schedule_expiry()

        self._expiry_unsub = async_track_point_in_utc_time(
            self.hass, _on_expiry, expiry
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._schedule_expiry()
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._schedule_expiry()

    async def async_will_remove_from_hass(self) -> None:
        if self._expiry_unsub is not None:
            self._expiry_unsub()
            self._expiry_unsub = None
        await super().async_will_remove_from_hass()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        coordinator = self.coordinator
        matching = coordinator.current_alert_quakes()
        return {
            "alert_radius_km": coordinator.alert_radius_km,
            "alert_min_magnitude": coordinator.alert_min_magnitude,
            "alert_window_minutes": int(
                coordinator.alert_window.total_seconds() // 60
            ),
            "matching_quakes": [q.as_dict() for q in matching],
            "latest_alert": matching[0].as_dict() if matching else None,
        }
