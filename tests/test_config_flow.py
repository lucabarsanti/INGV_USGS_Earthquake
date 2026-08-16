"""Tests for the config and options flows."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.data_entry_flow import FlowResultType

from custom_components.earthquake_monitor.const import DOMAIN

USER_INPUT = {
    "latitude": 42.5,
    "longitude": 13.0,
    "sources": ["ingv", "usgs"],
    "radius_km": 500,
    "min_magnitude": 2.0,
    "alert_radius_km": 100,
    "alert_min_magnitude": 3.5,
    "alert_window_minutes": 60,
    "max_depth_km": 700,
    "lookback_hours": 24,
    "scan_interval_minutes": 5,
}


async def test_user_flow_success(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.earthquake_monitor.config_flow._async_test_sources",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["sources"] == ["ingv", "usgs"]
    assert result["data"]["radius_km"] == 500.0
    assert result["data"]["scan_interval_minutes"] == 5


async def test_user_flow_cannot_connect(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "custom_components.earthquake_monitor.config_flow._async_test_sources",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_no_sources(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "sources": []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"sources": "no_sources"}


async def test_options_flow(hass, aioclient_mock, config_entry):
    from .conftest import register_feeds

    register_feeds(aioclient_mock)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.earthquake_monitor.config_flow._async_test_sources",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**USER_INPUT, "alert_radius_km": 50}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["alert_radius_km"] == 50.0
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    assert coordinator.alert_radius_km == 50.0
