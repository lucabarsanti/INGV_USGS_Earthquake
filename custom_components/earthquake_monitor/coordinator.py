"""Data update coordinator for Earthquake Monitor."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALERT_MIN_MAGNITUDE,
    CONF_ALERT_RADIUS,
    CONF_ALERT_WINDOW,
    CONF_LOOKBACK,
    CONF_MIN_MAGNITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DEFAULT_ALERT_MIN_MAGNITUDE,
    DEFAULT_ALERT_RADIUS_KM,
    DEFAULT_ALERT_WINDOW_MINUTES,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_MIN_MAGNITUDE,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SOURCES,
    DOMAIN,
    EVENT_QUAKE,
    MAX_QUAKES_KEPT,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .models import Quake
from .sources import SOURCE_REGISTRY, EarthquakeSource
from .util import haversine_km

_LOGGER = logging.getLogger(__name__)

# Two events from different networks are considered the same earthquake when
# they are closer than this in space and time. INGV wins for its region.
DEDUP_MAX_KM = 75.0
DEDUP_MAX_SECONDS = 40.0
# Never fire notification events for earthquakes older than this.
EVENT_MAX_AGE = timedelta(hours=2)


@dataclass
class EarthquakeData:
    """Result of one coordinator refresh."""

    quakes: list[Quake] = field(default_factory=list)
    last: Quake | None = None
    nearest: Quake | None = None
    strongest: Quake | None = None
    alert_quakes: list[Quake] = field(default_factory=list)


class EarthquakeCoordinator(DataUpdateCoordinator[EarthquakeData]):
    """Fetch, merge and filter earthquakes from all configured sources."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        options = {**entry.data, **entry.options}
        self.latitude: float = options.get(CONF_LATITUDE, hass.config.latitude)
        self.longitude: float = options.get(CONF_LONGITUDE, hass.config.longitude)
        self.radius_km: float = options.get(CONF_RADIUS, DEFAULT_RADIUS_KM)
        self.min_magnitude: float = options.get(
            CONF_MIN_MAGNITUDE, DEFAULT_MIN_MAGNITUDE
        )
        self.alert_radius_km: float = options.get(
            CONF_ALERT_RADIUS, DEFAULT_ALERT_RADIUS_KM
        )
        self.alert_min_magnitude: float = options.get(
            CONF_ALERT_MIN_MAGNITUDE, DEFAULT_ALERT_MIN_MAGNITUDE
        )
        self.alert_window = timedelta(
            minutes=options.get(CONF_ALERT_WINDOW, DEFAULT_ALERT_WINDOW_MINUTES)
        )
        self.lookback = timedelta(
            hours=options.get(CONF_LOOKBACK, DEFAULT_LOOKBACK_HOURS)
        )
        scan_minutes = max(
            MIN_SCAN_INTERVAL_MINUTES,
            options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        )

        source_keys = options.get(CONF_SOURCES, DEFAULT_SOURCES)
        self.sources: list[EarthquakeSource] = [
            SOURCE_REGISTRY[key]() for key in source_keys if key in SOURCE_REGISTRY
        ]

        self._seen_ids: set[str] = set()
        self._first_refresh_done = False

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=scan_minutes),
        )

    async def _async_update_data(self) -> EarthquakeData:
        session = async_get_clientsession(self.hass)
        start = dt_util.utcnow() - self.lookback

        results = await asyncio.gather(
            *(
                source.async_fetch(
                    session,
                    start=start,
                    latitude=self.latitude,
                    longitude=self.longitude,
                    radius_km=self.radius_km,
                    min_magnitude=self.min_magnitude,
                )
                for source in self.sources
            ),
            return_exceptions=True,
        )

        quakes: list[Quake] = []
        failures: list[str] = []
        for source, result in zip(self.sources, results):
            if isinstance(result, BaseException):
                failures.append(source.name)
                _LOGGER.warning("Fetching from %s failed: %s", source.name, result)
                continue
            quakes.extend(result)

        if failures and len(failures) == len(self.sources):
            raise UpdateFailed(f"All sources failed: {', '.join(failures)}")

        for quake in quakes:
            quake.distance_km = haversine_km(
                self.latitude, self.longitude, quake.latitude, quake.longitude
            )

        quakes = [
            q
            for q in quakes
            if q.distance_km is not None
            and q.distance_km <= self.radius_km
            and q.magnitude >= self.min_magnitude
            and q.time >= start
        ]
        quakes = self._deduplicate(quakes)
        quakes.sort(key=lambda q: q.time, reverse=True)
        quakes = quakes[:MAX_QUAKES_KEPT]

        data = EarthquakeData(quakes=quakes)
        if quakes:
            data.last = quakes[0]
            data.nearest = min(quakes, key=lambda q: q.distance_km or 0)
            data.strongest = max(quakes, key=lambda q: q.magnitude)

        alert_cutoff = dt_util.utcnow() - self.alert_window
        data.alert_quakes = [
            q
            for q in quakes
            if q.time >= alert_cutoff
            and q.magnitude >= self.alert_min_magnitude
            and (q.distance_km or 0) <= self.alert_radius_km
        ]

        self._fire_events(data)
        return data

    def _deduplicate(self, quakes: list[Quake]) -> list[Quake]:
        """Drop cross-network duplicates, preferring INGV solutions."""
        # INGV first so it wins ties for events reported by both networks.
        ordered = sorted(quakes, key=lambda q: 0 if q.source == "ingv" else 1)
        kept: list[Quake] = []
        for quake in ordered:
            duplicate = any(
                quake.source != other.source
                and abs((quake.time - other.time).total_seconds()) <= DEDUP_MAX_SECONDS
                and haversine_km(
                    quake.latitude, quake.longitude, other.latitude, other.longitude
                )
                <= DEDUP_MAX_KM
                for other in kept
            )
            if not duplicate:
                kept.append(quake)
        return kept

    def _fire_events(self, data: EarthquakeData) -> None:
        """Fire an event on the HA bus for every newly detected earthquake."""
        new_ids: set[str] = set()
        now = dt_util.utcnow()
        for quake in data.quakes:
            new_ids.add(quake.id)
            if not self._first_refresh_done or quake.id in self._seen_ids:
                continue
            if now - quake.time > EVENT_MAX_AGE:
                continue
            is_alert = (
                quake.magnitude >= self.alert_min_magnitude
                and (quake.distance_km or 0) <= self.alert_radius_km
            )
            self.hass.bus.async_fire(
                EVENT_QUAKE,
                {
                    "entry_id": self.entry.entry_id,
                    "is_alert": is_alert,
                    **quake.as_dict(),
                },
            )

        # Keep known ids bounded: current feed plus what we already knew,
        # trimmed implicitly because old events fall out of the lookback.
        self._seen_ids |= new_ids
        if len(self._seen_ids) > 5000:
            self._seen_ids = new_ids
        self._first_refresh_done = True
