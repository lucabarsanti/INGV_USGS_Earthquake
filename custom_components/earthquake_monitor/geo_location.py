"""Geolocation events for Earthquake Monitor.

Each earthquake becomes a ``geo_location`` entity, so events automatically
show up on the built-in Home Assistant map card as well.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTRIBUTION, DOMAIN
from .coordinator import EarthquakeCoordinator
from .models import Quake


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the geo_location platform."""
    coordinator: EarthquakeCoordinator = hass.data[DOMAIN][entry.entry_id]
    manager = QuakeEntityManager(coordinator, async_add_entities)
    entry.async_on_unload(coordinator.async_add_listener(manager.async_update))
    manager.async_update()


class QuakeEntityManager:
    """Keep one geolocation entity per earthquake currently in the feed."""

    def __init__(
        self,
        coordinator: EarthquakeCoordinator,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self._coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._entities: dict[str, EarthquakeEvent] = {}

    @callback
    def async_update(self) -> None:
        current = {q.id: q for q in self._coordinator.data.quakes}

        for quake_id in list(self._entities):
            entity = self._entities[quake_id]
            if quake_id in current:
                entity.async_update_quake(current[quake_id])
            else:
                del self._entities[quake_id]
                entity.hass.async_create_task(entity.async_remove(force_remove=True))

        new_entities = [
            EarthquakeEvent(quake)
            for quake_id, quake in current.items()
            if quake_id not in self._entities
        ]
        for entity in new_entities:
            self._entities[entity.quake.id] = entity
        if new_entities:
            self._async_add_entities(new_entities)


class EarthquakeEvent(GeolocationEvent):
    """A single earthquake on the map."""

    _attr_should_poll = False
    _attr_source = DOMAIN
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:pulse"

    def __init__(self, quake: Quake) -> None:
        self.quake = quake
        self._apply(quake)

    def _apply(self, quake: Quake) -> None:
        self._attr_name = f"M {quake.magnitude:.1f} - {quake.place}"
        self._attr_latitude = quake.latitude
        self._attr_longitude = quake.longitude
        self._attr_distance = quake.distance_km

    @callback
    def async_update_quake(self, quake: Quake) -> None:
        """Refresh from newer feed data (solutions get revised)."""
        self.quake = quake
        self._apply(quake)
        if self.hass:
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "external_id": self.quake.id,
            "data_source": self.quake.source,
            "magnitude": self.quake.magnitude,
            "mag_type": self.quake.mag_type,
            "depth_km": self.quake.depth_km,
            "time": self.quake.time.isoformat(),
            "url": self.quake.url,
        }
