"""Tests for the source parsers against realistic API payloads."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.earthquake_monitor.sources.emsc import EmscSource
from custom_components.earthquake_monitor.sources.ingv import IngvSource
from custom_components.earthquake_monitor.sources.usgs import UsgsSource

from .conftest import (
    EMSC_URL,
    INGV_URL,
    USGS_URL,
    feed,
    ingv_feature,
    usgs_feature,
    utc_iso,
)

FETCH_KWARGS = {
    "latitude": 42.5,
    "longitude": 13.0,
    "radius_km": 500.0,
    "min_magnitude": 2.0,
}


async def test_ingv_parsing(hass, aioclient_mock):
    aioclient_mock.get(
        INGV_URL, json=feed([ingv_feature(123, 3.7, 44.14, 10.04, depth=10.4)])
    )
    quakes = await IngvSource().async_fetch(
        async_get_clientsession(hass),
        start=datetime.now(UTC) - timedelta(hours=24),
        **FETCH_KWARGS,
    )
    assert len(quakes) == 1
    quake = quakes[0]
    assert quake.id == "ingv:123"
    assert quake.source == "ingv"
    assert quake.magnitude == 3.7
    assert quake.latitude == 44.14
    assert quake.longitude == 10.04
    assert quake.depth_km == 10.4
    assert quake.time.tzinfo is not None
    assert "terremoti.ingv.it" in quake.url


async def test_usgs_parsing_with_extras(hass, aioclient_mock):
    aioclient_mock.get(
        USGS_URL,
        json=feed([usgs_feature("us6000aaaa", 4.1, 44.13, 10.05, tsunami=1)]),
    )
    quakes = await UsgsSource().async_fetch(
        async_get_clientsession(hass),
        start=datetime.now(UTC) - timedelta(hours=24),
        **FETCH_KWARGS,
    )
    assert len(quakes) == 1
    quake = quakes[0]
    assert quake.id == "usgs:us6000aaaa"
    assert quake.tsunami is True
    assert quake.felt == 12
    assert quake.mmi == 4.1


async def test_emsc_parsing(hass, aioclient_mock):
    aioclient_mock.get(
        EMSC_URL,
        json={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "20260816_0000421",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [10.0712, 44.1387, -8.6],
                    },
                    "properties": {
                        "time": utc_iso(20) + "Z",
                        "flynn_region": "NORTHERN ITALY",
                        "lat": 44.1387,
                        "lon": 10.0712,
                        "depth": 8.6,
                        "mag": 2.0,
                        "magtype": "ml",
                        "unid": "20260816_0000421",
                    },
                }
            ],
        },
    )
    quakes = await EmscSource().async_fetch(
        async_get_clientsession(hass),
        start=datetime.now(UTC) - timedelta(hours=24),
        **FETCH_KWARGS,
    )
    assert len(quakes) == 1
    quake = quakes[0]
    assert quake.id == "emsc:20260816_0000421"
    assert quake.place == "Northern Italy"
    assert quake.depth_km == 8.6  # positive, from properties


async def test_malformed_features_are_skipped(hass, aioclient_mock):
    broken = ingv_feature(1, 3.0, 44.0, 10.0)
    broken["properties"]["mag"] = None
    aioclient_mock.get(
        INGV_URL, json=feed([broken, ingv_feature(2, 2.5, 43.0, 12.0)])
    )
    quakes = await IngvSource().async_fetch(
        async_get_clientsession(hass),
        start=datetime.now(UTC) - timedelta(hours=24),
        **FETCH_KWARGS,
    )
    assert [q.id for q in quakes] == ["ingv:2"]
