"""Data update coordinator for Earthquake Monitor."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALERT_MIN_MAGNITUDE,
    CONF_ALERT_RADIUS,
    CONF_ALERT_WINDOW,
    CONF_LOOKBACK,
    CONF_MAX_DEPTH,
    CONF_MIN_MAGNITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    DEFAULT_ALERT_MIN_MAGNITUDE,
    DEFAULT_ALERT_RADIUS_KM,
    DEFAULT_ALERT_WINDOW_MINUTES,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_MAX_DEPTH_KM,
    DEFAULT_MIN_MAGNITUDE,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SOURCES,
    DOMAIN,
    EVENT_QUAKE,
    EVENT_QUAKE_UPDATED,
    FAILURES_BEFORE_ISSUE,
    MAGNITUDE_REVISION_THRESHOLD,
    MAX_QUAKES_KEPT,
    MIN_SCAN_INTERVAL_MINUTES,
    STORAGE_VERSION,
)
from .models import Quake
from .sources import SOURCE_REGISTRY, EarthquakeSource
from .util import haversine_km

_LOGGER = logging.getLogger(__name__)

# Two events from different networks are considered the same earthquake when
# they are closer than this in space and time.
DEDUP_MAX_KM = 75.0
DEDUP_MAX_SECONDS = 40.0
# Preference order when the same quake is reported by several networks.
DEDUP_PRIORITY = {"ingv": 0, "emsc": 1, "usgs": 2}
# Never fire notification events for earthquakes older than this.
EVENT_MAX_AGE = timedelta(hours=2)


@dataclass
class EarthquakeData:
    """Result of one coordinator refresh."""

    quakes: list[Quake] = field(default_factory=list)
    last: Quake | None = None
    nearest: Quake | None = None
    strongest: Quake | None = None


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
        self.max_depth_km: float = options.get(CONF_MAX_DEPTH, DEFAULT_MAX_DEPTH_KM)
        scan_minutes = max(
            MIN_SCAN_INTERVAL_MINUTES,
            options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        )

        source_keys = options.get(CONF_SOURCES, DEFAULT_SOURCES)
        self.sources: list[EarthquakeSource] = [
            SOURCE_REGISTRY[key]() for key in source_keys if key in SOURCE_REGISTRY
        ]

        # id -> last known magnitude, persisted across restarts.
        self._seen: dict[str, float] = {}
        self._first_refresh_done = False
        self._failure_counts: dict[str, int] = {}
        self.last_alert_time: datetime | None = None
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=scan_minutes),
        )

    async def async_load_store(self) -> None:
        """Restore seen quake ids so a restart does not swallow new events."""
        stored = await self._store.async_load()
        if not stored:
            return
        self._seen = dict(stored.get("seen", {}))
        if last_alert := stored.get("last_alert"):
            self.last_alert_time = dt_util.parse_datetime(last_alert)
        # With restored state we can safely fire events from the first refresh.
        self._first_refresh_done = bool(self._seen)

    def _save_store(self) -> None:
        self._store.async_delay_save(
            lambda: {
                "seen": self._seen,
                "last_alert": self.last_alert_time.isoformat()
                if self.last_alert_time
                else None,
            },
            15,
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
        failed_all = True
        for source, result in zip(self.sources, results, strict=True):
            if isinstance(result, BaseException):
                _LOGGER.warning("Fetching from %s failed: %s", source.name, result)
                self._register_failure(source)
                continue
            failed_all = False
            self._register_success(source)
            quakes.extend(result)

        if self.sources and failed_all:
            raise UpdateFailed("All earthquake sources failed")

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
            and (q.depth_km is None or q.depth_km <= self.max_depth_km)
        ]
        quakes = self._deduplicate(quakes)
        quakes.sort(key=lambda q: q.time, reverse=True)
        quakes = quakes[:MAX_QUAKES_KEPT]

        data = EarthquakeData(quakes=quakes)
        if quakes:
            data.last = quakes[0]
            data.nearest = min(quakes, key=lambda q: q.distance_km or 0)
            data.strongest = max(quakes, key=lambda q: q.magnitude)

        self._fire_events(data)

        alerts = self.alert_quakes_in(data.quakes)
        if alerts:
            newest = max(alerts, key=lambda q: q.time)
            if self.last_alert_time is None or newest.time > self.last_alert_time:
                self.last_alert_time = newest.time

        self._save_store()
        return data

    def is_alert_quake(self, quake: Quake) -> bool:
        """Check the distance + magnitude alert condition (no time check)."""
        return (
            quake.magnitude >= self.alert_min_magnitude
            and (quake.distance_km or 0) <= self.alert_radius_km
        )

    def alert_quakes_in(self, quakes: list[Quake]) -> list[Quake]:
        """Quakes currently matching the alert criteria, evaluated at call time."""
        cutoff = dt_util.utcnow() - self.alert_window
        return [q for q in quakes if q.time >= cutoff and self.is_alert_quake(q)]

    def current_alert_quakes(self) -> list[Quake]:
        """Alert quakes for the latest refresh, with a live time window."""
        if self.data is None:
            return []
        return self.alert_quakes_in(self.data.quakes)

    def _deduplicate(self, quakes: list[Quake]) -> list[Quake]:
        """Drop cross-network duplicates, preferring INGV > EMSC > USGS."""
        ordered = sorted(quakes, key=lambda q: DEDUP_PRIORITY.get(q.source, 9))
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
        """Fire bus events for new quakes and significant magnitude revisions."""
        now = dt_util.utcnow()
        for quake in data.quakes:
            known_magnitude = self._seen.get(quake.id)
            if known_magnitude is None:
                if self._first_refresh_done and now - quake.time <= EVENT_MAX_AGE:
                    self.hass.bus.async_fire(
                        EVENT_QUAKE,
                        {
                            "entry_id": self.entry.entry_id,
                            "is_alert": self.is_alert_quake(quake),
                            **quake.as_dict(),
                        },
                    )
            elif (
                abs(quake.magnitude - known_magnitude)
                >= MAGNITUDE_REVISION_THRESHOLD
            ):
                self.hass.bus.async_fire(
                    EVENT_QUAKE_UPDATED,
                    {
                        "entry_id": self.entry.entry_id,
                        "is_alert": self.is_alert_quake(quake),
                        "previous_magnitude": known_magnitude,
                        **quake.as_dict(),
                    },
                )
            self._seen[quake.id] = quake.magnitude

        # Bound memory: once the map grows well past the feed size, drop ids
        # that are no longer in any feed (they cannot re-fire anyway).
        if len(self._seen) > 5000:
            current_ids = {q.id for q in data.quakes}
            self._seen = {
                qid: mag for qid, mag in self._seen.items() if qid in current_ids
            }
        self._first_refresh_done = True

    def _register_failure(self, source: EarthquakeSource) -> None:
        count = self._failure_counts.get(source.key, 0) + 1
        self._failure_counts[source.key] = count
        if count == FAILURES_BEFORE_ISSUE:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"source_unavailable_{self.entry.entry_id}_{source.key}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="source_unavailable",
                translation_placeholders={"source": source.name},
            )

    def _register_success(self, source: EarthquakeSource) -> None:
        if self._failure_counts.get(source.key, 0) >= FAILURES_BEFORE_ISSUE:
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                f"source_unavailable_{self.entry.entry_id}_{source.key}",
            )
        self._failure_counts[source.key] = 0
