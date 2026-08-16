"""Shared fixtures and feed payload builders for the test suite."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.earthquake_monitor.const import DOMAIN

INGV_URL = "https://webservices.ingv.it/fdsnws/event/1/query"
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
EMSC_URL = "https://www.seismicportal.eu/fdsnws/event/1/query"

# Test home: central Italy.
HOME_LAT = 42.5
HOME_LON = 13.0

ENTRY_DATA: dict[str, Any] = {
    "name": "Earthquake Monitor",
    "latitude": HOME_LAT,
    "longitude": HOME_LON,
    "sources": ["ingv", "usgs"],
    "radius_km": 500.0,
    "min_magnitude": 2.0,
    "alert_radius_km": 100.0,
    "alert_min_magnitude": 3.5,
    "alert_window_minutes": 60,
    "max_depth_km": 700.0,
    "lookback_hours": 24,
    "scan_interval_minutes": 5,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, title="Earthquake Monitor", data=ENTRY_DATA)


def utc_iso(minutes_ago: float) -> str:
    return (
        datetime.now(UTC) - timedelta(minutes=minutes_ago)
    ).strftime("%Y-%m-%dT%H:%M:%S.%f")


def epoch_ms(minutes_ago: float) -> int:
    return int(
        (datetime.now(UTC) - timedelta(minutes=minutes_ago)).timestamp()
        * 1000
    )


def ingv_feature(
    event_id: int,
    magnitude: float,
    lat: float,
    lon: float,
    depth: float = 10.0,
    minutes_ago: float = 30,
    place: str = "Test place (IT)",
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "eventId": event_id,
            "time": utc_iso(minutes_ago),
            "magType": "ML",
            "mag": magnitude,
            "place": place,
            "type": "earthquake",
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat, depth]},
    }


def usgs_feature(
    event_id: str,
    magnitude: float,
    lat: float,
    lon: float,
    depth: float = 10.0,
    minutes_ago: float = 30,
    place: str = "Test place, Italy",
    tsunami: int = 0,
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": event_id,
        "properties": {
            "mag": magnitude,
            "place": place,
            "time": epoch_ms(minutes_ago),
            "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}",
            "magType": "mb",
            "tsunami": tsunami,
            "felt": 12,
            "mmi": 4.1,
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat, depth]},
    }


def feed(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def register_feeds(
    aioclient_mock,
    ingv: list[dict[str, Any]] | None = None,
    usgs: list[dict[str, Any]] | None = None,
    emsc: list[dict[str, Any]] | None = None,
) -> None:
    aioclient_mock.get(INGV_URL, json=feed(ingv or []))
    aioclient_mock.get(USGS_URL, json=feed(usgs or []))
    aioclient_mock.get(EMSC_URL, json=feed(emsc or []))
