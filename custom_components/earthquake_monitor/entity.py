"""Base entity for Earthquake Monitor."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import EarthquakeCoordinator


class EarthquakeMonitorEntity(CoordinatorEntity[EarthquakeCoordinator]):
    """Common base: one service device per config entry."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: EarthquakeCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="INGV / USGS",
            model="Earthquake Monitor",
            entry_type=DeviceEntryType.SERVICE,
        )
