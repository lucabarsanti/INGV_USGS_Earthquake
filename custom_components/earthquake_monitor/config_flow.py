"""Config flow for Earthquake Monitor (INGV + USGS)."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

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
    DEFAULT_NAME,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SOURCES,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .sources import SOURCE_REGISTRY

_LOGGER = logging.getLogger(__name__)


async def _async_test_sources(
    hass: HomeAssistant, source_keys: list[str], latitude: float, longitude: float
) -> bool:
    """Do a small test fetch against each selected source."""
    from homeassistant.util import dt as dt_util

    session = async_get_clientsession(hass)
    start = dt_util.utcnow() - timedelta(hours=1)

    async def _probe(key: str) -> None:
        await SOURCE_REGISTRY[key]().async_fetch(
            session,
            start=start,
            latitude=latitude,
            longitude=longitude,
            radius_km=100.0,
            min_magnitude=5.0,
        )

    try:
        await asyncio.gather(
            *(_probe(key) for key in source_keys if key in SOURCE_REGISTRY)
        )
    except Exception as err:  # noqa: BLE001 — any failure means "can't connect"
        _LOGGER.warning("Source connection test failed: %s", err)
        return False
    return True


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema shared by the initial config flow and the options flow."""
    source_options = list(SOURCE_REGISTRY)
    return vol.Schema(
        {
            vol.Required(
                CONF_LATITUDE, default=defaults[CONF_LATITUDE]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=-90, max=90, step="any", mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_LONGITUDE, default=defaults[CONF_LONGITUDE]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=-180, max=180, step="any", mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_SOURCES, default=defaults[CONF_SOURCES]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=source_options,
                    multiple=True,
                    translation_key="sources",
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Required(CONF_RADIUS, default=defaults[CONF_RADIUS]): NumberSelector(
                NumberSelectorConfig(
                    min=10,
                    max=20000,
                    step=10,
                    unit_of_measurement="km",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MIN_MAGNITUDE, default=defaults[CONF_MIN_MAGNITUDE]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=9, step=0.1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_ALERT_RADIUS, default=defaults[CONF_ALERT_RADIUS]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=20000,
                    step=1,
                    unit_of_measurement="km",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_ALERT_MIN_MAGNITUDE,
                default=defaults[CONF_ALERT_MIN_MAGNITUDE],
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=9, step=0.1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_ALERT_WINDOW, default=defaults[CONF_ALERT_WINDOW]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=1440,
                    step=5,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MAX_DEPTH, default=defaults[CONF_MAX_DEPTH]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=700,
                    step=1,
                    unit_of_measurement="km",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_LOOKBACK, default=defaults[CONF_LOOKBACK]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=168,
                    step=1,
                    unit_of_measurement="h",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL_MINUTES,
                    max=120,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    """Coerce selector output to the types the coordinator expects."""
    data = dict(user_input)
    for key in (
        CONF_LATITUDE,
        CONF_LONGITUDE,
        CONF_RADIUS,
        CONF_MIN_MAGNITUDE,
        CONF_ALERT_RADIUS,
        CONF_ALERT_MIN_MAGNITUDE,
        CONF_MAX_DEPTH,
    ):
        data[key] = float(data[key])
    for key in (CONF_ALERT_WINDOW, CONF_LOOKBACK, CONF_SCAN_INTERVAL):
        data[key] = int(data[key])
    return data


class EarthquakeMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_SOURCES):
                errors[CONF_SOURCES] = "no_sources"
            else:
                data = _normalize(user_input)
                if not await _async_test_sources(
                    self.hass,
                    data[CONF_SOURCES],
                    data[CONF_LATITUDE],
                    data[CONF_LONGITUDE],
                ):
                    errors["base"] = "cannot_connect"
                else:
                    data[CONF_NAME] = DEFAULT_NAME
                    return self.async_create_entry(title=DEFAULT_NAME, data=data)

        defaults = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
            CONF_SOURCES: DEFAULT_SOURCES,
            CONF_RADIUS: DEFAULT_RADIUS_KM,
            CONF_MIN_MAGNITUDE: DEFAULT_MIN_MAGNITUDE,
            CONF_ALERT_RADIUS: DEFAULT_ALERT_RADIUS_KM,
            CONF_ALERT_MIN_MAGNITUDE: DEFAULT_ALERT_MIN_MAGNITUDE,
            CONF_ALERT_WINDOW: DEFAULT_ALERT_WINDOW_MINUTES,
            CONF_MAX_DEPTH: DEFAULT_MAX_DEPTH_KM,
            CONF_LOOKBACK: DEFAULT_LOOKBACK_HOURS,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_MINUTES,
        }
        if user_input:
            defaults.update(user_input)

        return self.async_show_form(
            step_id="user", data_schema=_build_schema(defaults), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EarthquakeMonitorOptionsFlow()


class EarthquakeMonitorOptionsFlow(OptionsFlow):
    """Allow changing every setting after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_SOURCES):
                errors[CONF_SOURCES] = "no_sources"
            else:
                data = _normalize(user_input)
                if not await _async_test_sources(
                    self.hass,
                    data[CONF_SOURCES],
                    data[CONF_LATITUDE],
                    data[CONF_LONGITUDE],
                ):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(data=data)

        current = {**self.config_entry.data, **self.config_entry.options}
        defaults = {
            CONF_LATITUDE: current.get(CONF_LATITUDE, self.hass.config.latitude),
            CONF_LONGITUDE: current.get(CONF_LONGITUDE, self.hass.config.longitude),
            CONF_SOURCES: current.get(CONF_SOURCES, DEFAULT_SOURCES),
            CONF_RADIUS: current.get(CONF_RADIUS, DEFAULT_RADIUS_KM),
            CONF_MIN_MAGNITUDE: current.get(
                CONF_MIN_MAGNITUDE, DEFAULT_MIN_MAGNITUDE
            ),
            CONF_ALERT_RADIUS: current.get(CONF_ALERT_RADIUS, DEFAULT_ALERT_RADIUS_KM),
            CONF_ALERT_MIN_MAGNITUDE: current.get(
                CONF_ALERT_MIN_MAGNITUDE, DEFAULT_ALERT_MIN_MAGNITUDE
            ),
            CONF_ALERT_WINDOW: current.get(
                CONF_ALERT_WINDOW, DEFAULT_ALERT_WINDOW_MINUTES
            ),
            CONF_MAX_DEPTH: current.get(CONF_MAX_DEPTH, DEFAULT_MAX_DEPTH_KM),
            CONF_LOOKBACK: current.get(CONF_LOOKBACK, DEFAULT_LOOKBACK_HOURS),
            CONF_SCAN_INTERVAL: current.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
            ),
        }
        if user_input:
            defaults.update(user_input)

        return self.async_show_form(
            step_id="init", data_schema=_build_schema(defaults), errors=errors
        )
