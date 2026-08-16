"""INGV (Istituto Nazionale di Geofisica e Vulcanologia) FDSN event source.

API: https://webservices.ingv.it/ (FDSN event web service, GeoJSON output).
Data license: CC BY 4.0 — https://terremoti.ingv.it/
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiohttp import ClientSession

from homeassistant.util import dt as dt_util

from ..models import Quake
from .base import EarthquakeSource

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://webservices.ingv.it/fdsnws/event/1/query"
# FDSN uses degrees for maxradius; ~111.19 km per degree.
KM_PER_DEGREE = 111.19
REQUEST_TIMEOUT = 30


def _parse_time(value: object) -> datetime | None:
    """INGV returns ISO strings; be tolerant of epoch milliseconds too."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return dt_util.as_utc(parsed)
    return None


class IngvSource(EarthquakeSource):
    """Earthquakes from the INGV FDSN event web service."""

    key = "ingv"
    name = "INGV"

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
            "maxradius": str(round(radius_km / KM_PER_DEGREE, 4)),
            "orderby": "time",
        }
        async with session.get(
            BASE_URL, params=params, timeout=REQUEST_TIMEOUT
        ) as resp:
            # INGV replies 204 when there are no matching events.
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
                event_time = _parse_time(props.get("time"))
                magnitude = props.get("mag")
                if event_time is None or magnitude is None or len(coords) < 2:
                    continue
                event_id = str(
                    props.get("eventId") or feature.get("id") or props.get("time")
                )
                depth = coords[2] if len(coords) > 2 else None
                quakes.append(
                    Quake(
                        id=f"ingv:{event_id}",
                        source=self.key,
                        magnitude=float(magnitude),
                        mag_type=props.get("magType"),
                        place=props.get("place") or "Unknown location",
                        time=event_time,
                        latitude=float(coords[1]),
                        longitude=float(coords[0]),
                        depth_km=float(depth) if depth is not None else None,
                        url=f"https://terremoti.ingv.it/event/{event_id}",
                    )
                )
            except (TypeError, ValueError) as err:
                _LOGGER.debug("Skipping malformed INGV feature: %s", err)
        return quakes
