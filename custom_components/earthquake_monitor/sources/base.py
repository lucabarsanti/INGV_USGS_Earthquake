"""Base class for earthquake data sources.

To add a new source (for example a local seismograph), subclass
``EarthquakeSource``, implement ``async_fetch`` and register the class in
``sources/__init__.py`` (``SOURCE_REGISTRY``). The coordinator treats every
registered source identically: it merges, deduplicates and filters the events
each source returns.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from aiohttp import ClientSession

from ..models import Quake


class EarthquakeSource(ABC):
    """A provider of earthquake events."""

    key: str = "base"
    name: str = "Base source"

    @abstractmethod
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
        """Fetch earthquakes since ``start`` around the given point.

        Implementations should return normalized ``Quake`` objects with UTC
        aware ``time`` values. ``distance_km`` is filled in by the coordinator.
        Implementations may pre-filter server-side but the coordinator applies
        the radius / magnitude filters again locally.
        """
