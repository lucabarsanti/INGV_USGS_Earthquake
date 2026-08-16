"""Placeholder for a future local seismograph source.

Planned support (roadmap):
- Raspberry Shake (local API / UDP data stream)
- Generic MQTT seismograph (an MQTT topic publishing detected events)
- Seedlink / ObsPy based station readers

To implement, subclass :class:`EarthquakeSource`, return normalized ``Quake``
objects from ``async_fetch`` (use ``source="local"``) and register the class in
``sources/__init__.py``. The coordinator, sensors, alerts, events, blueprint
and the map card will pick the events up automatically — no other changes are
required.
"""
from __future__ import annotations

from datetime import datetime

from aiohttp import ClientSession

from ..models import Quake
from .base import EarthquakeSource


class LocalSeismographSource(EarthquakeSource):
    """Not yet implemented — see module docstring for the integration plan."""

    key = "local"
    name = "Local seismograph"

    async def async_fetch(
        self,
        session: ClientSession,
        *,
        start: datetime,
        latitude: float,
        longitude: float,
        radius_km: float,
        min_magnitude: float,
    ) -> list[Quake]:
        raise NotImplementedError(
            "Local seismograph support is planned but not implemented yet"
        )
