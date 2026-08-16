"""Earthquake Monitor (INGV + USGS + EMSC) integration for Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import CARD_FILENAME, DOMAIN, EVENT_QUAKE, PLATFORMS, URL_BASE
from .coordinator import EarthquakeCoordinator
from .util import haversine_km

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_REFRESH = "refresh"
SERVICE_SIMULATE = "simulate_quake"

SIMULATE_SCHEMA = vol.Schema(
    {
        vol.Optional("magnitude", default=4.5): vol.Coerce(float),
        vol.Optional("distance_km", default=30.0): vol.Coerce(float),
        vol.Optional("depth_km", default=10.0): vol.Coerce(float),
        vol.Optional("place", default="Simulated earthquake"): cv.string,
    }
)

KM_PER_DEGREE = 111.19


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    """Register the card as a Lovelace resource (storage mode).

    ``add_extra_js_url`` scripts are loaded in parallel with the first
    dashboard render, so on slow connections the card can be briefly
    undefined ("Custom element doesn't exist"). Lovelace *resources* are
    awaited before rendering, which makes the card load deterministic.
    """
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None or not hasattr(resources, "async_create_item"):
        # Lovelace not loaded, or dashboards in YAML mode (the user manages
        # resources manually in that case).
        return
    try:
        if not resources.loaded:
            await resources.async_load()
            resources.loaded = True
        base_url = url.split("?")[0]
        for item in resources.async_items():
            if item.get("url", "").split("?")[0] == base_url:
                if item["url"] != url:  # version changed -> cache bust
                    await resources.async_update_item(
                        item["id"], {"res_type": "module", "url": url}
                    )
                return
        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.debug("Registered Lovelace resource %s", url)
    except Exception as err:  # noqa: BLE001 - never break setup over this
        _LOGGER.warning("Could not register the Lovelace resource: %s", err)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up shared resources: the Lovelace map card and services."""
    hass.data.setdefault(DOMAIN, {})

    if hass.http is not None:
        www_path = Path(__file__).parent / "www"
        card_url = f"{URL_BASE}/{CARD_FILENAME}"
        await hass.http.async_register_static_paths(
            [
                # The card itself must never be cached so updates apply instantly.
                StaticPathConfig(card_url, str(www_path / CARD_FILENAME), False),
                # Vendored assets (Leaflet) are versioned by integration release.
                StaticPathConfig(f"{URL_BASE}/vendor", str(www_path / "vendor"), True),
            ]
        )
        integration = await async_get_integration(hass, DOMAIN)
        versioned_url = f"{card_url}?v={integration.version}"
        # Belt and braces: extra JS for YAML-mode dashboards, plus a proper
        # Lovelace resource (awaited before render) for storage mode.
        add_extra_js_url(hass, versioned_url)

        async def _register_resource(_event: Event | None = None) -> None:
            await _async_register_lovelace_resource(hass, versioned_url)

        if hass.state is CoreState.running:
            await _register_resource()
        else:
            # Lovelace is not loaded yet during startup — register once
            # Home Assistant is fully started.
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, _register_resource
            )

    async def _coordinators() -> list[EarthquakeCoordinator]:
        return [
            c
            for c in hass.data[DOMAIN].values()
            if isinstance(c, EarthquakeCoordinator)
        ]

    async def _handle_refresh(call: ServiceCall) -> None:
        for coordinator in await _coordinators():
            await coordinator.async_request_refresh()

    async def _handle_simulate(call: ServiceCall) -> None:
        """Fire a synthetic quake event so users can test their automations."""
        coordinators = await _coordinators()
        if not coordinators:
            return
        for coordinator in coordinators:
            distance = call.data["distance_km"]
            latitude = coordinator.latitude + distance / KM_PER_DEGREE
            longitude = coordinator.longitude
            magnitude = call.data["magnitude"]
            hass.bus.async_fire(
                EVENT_QUAKE,
                {
                    "entry_id": coordinator.entry.entry_id,
                    "is_alert": magnitude >= coordinator.alert_min_magnitude
                    and distance <= coordinator.alert_radius_km,
                    "simulated": True,
                    "id": "simulated:test",
                    "source": "simulated",
                    "magnitude": magnitude,
                    "mag_type": "ML",
                    "place": call.data["place"],
                    "time": dt_util.utcnow().isoformat(),
                    "latitude": latitude,
                    "longitude": longitude,
                    "depth_km": call.data["depth_km"],
                    "url": None,
                    "distance_km": round(
                        haversine_km(
                            coordinator.latitude,
                            coordinator.longitude,
                            latitude,
                            longitude,
                        ),
                        1,
                    ),
                    "tsunami": False,
                    "felt": None,
                    "mmi": None,
                },
            )

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _handle_refresh)
    hass.services.async_register(
        DOMAIN, SERVICE_SIMULATE, _handle_simulate, schema=SIMULATE_SCHEMA
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Earthquake Monitor from a config entry."""
    coordinator = EarthquakeCoordinator(hass, entry)
    await coordinator.async_load_store()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
