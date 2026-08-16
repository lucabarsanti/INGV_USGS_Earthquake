"""USGS (United States Geological Survey) FDSN event source.

API: https://earthquake.usgs.gov/fdsnws/event/1/ (GeoJSON output).
USGS data is in the public domain.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiohttp import ClientSession

from ..models import Quake
from .base import EarthquakeSource

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
REQUEST_TIMEOUT = 30


class UsgsSource(EarthquakeSource):
    """Earthquakes from the USGS FDSN event web service."""

    key = "usgs"
    name = "USGS"

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
        params = {
            "format": "geojson",
            "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "minmagnitude": str(min_magnitude),
            "latitude": str(latitude),
            "longitude": str(longitude),
            "maxradiuskm": str(round(radius_km, 1)),
            "orderby": "time",
        }
        async with session.get(
            BASE_URL, params=params, timeout=REQUEST_TIMEOUT
        ) as resp:
            if resp.status == 204:
                return []
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        quakes: list[Quake] = []
        for feature in data.get("features", []):
            try:
                props = feature.get("properties", {})
                geometry = feature.get("geometry", {})
                coords = geometry.get("coordinates", [])
                time_ms = props.get("time")
                magnitude = props.get("mag")
                if time_ms is None or magnitude is None or len(coords) < 2:
                    continue
                event_id = str(feature.get("id") or time_ms)
                depth = coords[2] if len(coords) > 2 else None
                quakes.append(
                    Quake(
                        id=f"usgs:{event_id}",
                        source=self.key,
                        magnitude=float(magnitude),
                        mag_type=props.get("magType"),
                        place=props.get("place") or "Unknown location",
                        time=datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc),
                        latitude=float(coords[1]),
                        longitude=float(coords[0]),
                        depth_km=float(depth) if depth is not None else None,
                        url=props.get("url"),
                    )
                )
            except (TypeError, ValueError) as err:
                _LOGGER.debug("Skipping malformed USGS feature: %s", err)
        return quakes
