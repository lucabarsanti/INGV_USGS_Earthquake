"""EMSC (European-Mediterranean Seismological Centre) event source.

API: https://www.seismicportal.eu/fdsnws/event/1/ (JSON output).
EMSC is often the fastest catalog for the Euro-Mediterranean region.
"""
from __future__ import annotations

from datetime import UTC, datetime
import logging

from aiohttp import ClientSession
from homeassistant.util import dt as dt_util

from ..models import Quake
from .base import EarthquakeSource

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.seismicportal.eu/fdsnws/event/1/query"
KM_PER_DEGREE = 111.19
REQUEST_TIMEOUT = 30


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return dt_util.as_utc(parsed)
    return None


class EmscSource(EarthquakeSource):
    """Earthquakes from the EMSC seismicportal FDSN web service."""

    key = "emsc"
    name = "EMSC"

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
            "format": "json",
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
            # seismicportal replies 204 when there are no matching events.
            if resp.status == 204:
                return []
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        quakes: list[Quake] = []
        for feature in data.get("features", []):
            try:
                props = feature.get("properties", {})
                event_time = _parse_time(props.get("time"))
                magnitude = props.get("mag")
                lat = props.get("lat")
                lon = props.get("lon")
                if event_time is None or magnitude is None or lat is None:
                    continue
                unid = str(props.get("unid") or feature.get("id"))
                # properties.depth is positive km (geometry uses negative z).
                depth = props.get("depth")
                quakes.append(
                    Quake(
                        id=f"emsc:{unid}",
                        source=self.key,
                        magnitude=float(magnitude),
                        mag_type=props.get("magtype"),
                        place=(props.get("flynn_region") or "Unknown location").title(),
                        time=event_time,
                        latitude=float(lat),
                        longitude=float(lon),
                        depth_km=float(depth) if depth is not None else None,
                        url=f"https://www.seismicportal.eu/eventdetails.html?unid={unid}",
                    )
                )
            except (TypeError, ValueError) as err:
                _LOGGER.debug("Skipping malformed EMSC feature: %s", err)
        return quakes
