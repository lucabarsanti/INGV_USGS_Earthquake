"""End-to-end tests: setup, entities, dedup, events, alerts."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.earthquake_monitor.const import (
    DOMAIN,
    EVENT_QUAKE,
    EVENT_QUAKE_UPDATED,
)

from .conftest import HOME_LAT, HOME_LON, ingv_feature, register_feeds, usgs_feature


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entities_and_dedup(hass, aioclient_mock, config_entry):
    # Same quake seen by INGV and USGS (within 75 km / 40 s) plus one
    # USGS-only quake: after dedup there must be exactly two.
    register_feeds(
        aioclient_mock,
        ingv=[ingv_feature(1, 3.7, HOME_LAT + 0.3, HOME_LON, minutes_ago=30)],
        usgs=[
            usgs_feature("dup1", 4.1, HOME_LAT + 0.31, HOME_LON, minutes_ago=30),
            usgs_feature("only", 2.5, HOME_LAT + 2.0, HOME_LON, minutes_ago=200),
        ],
    )
    await _setup(hass, config_entry)

    count = hass.states.get("sensor.earthquake_monitor_earthquake_count")
    assert count is not None
    assert count.state == "2"
    # INGV solution must win the dedup.
    assert count.attributes["by_source"] == {"ingv": 1, "usgs": 1}

    last = hass.states.get("sensor.earthquake_monitor_last_earthquake")
    assert last.state == "3.7"
    assert len(last.attributes["quakes"]) == 2
    assert last.attributes["config_latitude"] == HOME_LAT

    # The INGV quake is ~33 km away and M 3.7 >= 3.5 -> alert on.
    alert = hass.states.get("binary_sensor.earthquake_monitor_earthquake_alert")
    assert alert.state == "on"

    nearest = hass.states.get("sensor.earthquake_monitor_nearest_earthquake")
    assert float(nearest.state) < 50

    # geo_location entities for both quakes.
    geo = [
        s for s in hass.states.async_all("geo_location")
        if s.attributes.get("source") == DOMAIN
    ]
    assert len(geo) == 2


async def test_no_alert_for_weak_quake(hass, aioclient_mock, config_entry):
    register_feeds(
        aioclient_mock,
        ingv=[ingv_feature(1, 2.4, HOME_LAT + 0.2, HOME_LON, minutes_ago=10)],
    )
    await _setup(hass, config_entry)
    alert = hass.states.get("binary_sensor.earthquake_monitor_earthquake_alert")
    assert alert.state == "off"


async def test_events_on_new_and_revised_quakes(hass, aioclient_mock, config_entry):
    register_feeds(
        aioclient_mock,
        ingv=[ingv_feature(1, 3.0, HOME_LAT + 0.5, HOME_LON, minutes_ago=40)],
    )
    await _setup(hass, config_entry)

    new_events = async_capture_events(hass, EVENT_QUAKE)
    updated_events = async_capture_events(hass, EVENT_QUAKE_UPDATED)
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Second refresh: quake 1 revised upward, quake 2 appears fresh.
    aioclient_mock.clear_requests()
    register_feeds(
        aioclient_mock,
        ingv=[
            ingv_feature(1, 3.6, HOME_LAT + 0.5, HOME_LON, minutes_ago=40),
            ingv_feature(2, 4.2, HOME_LAT + 0.4, HOME_LON, minutes_ago=5),
        ],
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(new_events) == 1
    payload = new_events[0].data
    assert payload["id"] == "ingv:2"
    assert payload["is_alert"] is True
    assert payload["distance_km"] < 100

    assert len(updated_events) == 1
    assert updated_events[0].data["id"] == "ingv:1"
    assert updated_events[0].data["previous_magnitude"] == 3.0


async def test_simulate_service_fires_event(hass, aioclient_mock, config_entry):
    register_feeds(aioclient_mock)
    await _setup(hass, config_entry)

    events = async_capture_events(hass, EVENT_QUAKE)
    await hass.services.async_call(
        DOMAIN,
        "simulate_quake",
        {"magnitude": 5.0, "distance_km": 20},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["simulated"] is True
    assert events[0].data["is_alert"] is True


async def test_one_source_down_keeps_working(hass, aioclient_mock, config_entry):
    aioclient_mock.get(
        "https://webservices.ingv.it/fdsnws/event/1/query",
        json={
            "type": "FeatureCollection",
            "features": [ingv_feature(1, 3.0, HOME_LAT + 0.5, HOME_LON)],
        },
    )
    aioclient_mock.get(
        "https://earthquake.usgs.gov/fdsnws/event/1/query", status=503
    )
    await _setup(hass, config_entry)

    count = hass.states.get("sensor.earthquake_monitor_earthquake_count")
    assert count.state == "1"
