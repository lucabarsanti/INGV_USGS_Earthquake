"""Earthquake data sources.

``SOURCE_REGISTRY`` maps a source key (used in the config flow) to its
implementation. Add new sources here — e.g. a local seismograph
(see ``local.py``) — and they become selectable and fully supported.
"""
from __future__ import annotations

from .base import EarthquakeSource
from .ingv import IngvSource
from .usgs import UsgsSource

SOURCE_REGISTRY: dict[str, type[EarthquakeSource]] = {
    IngvSource.key: IngvSource,
    UsgsSource.key: UsgsSource,
    # "local": LocalSeismographSource,  # planned — see local.py
}

__all__ = ["EarthquakeSource", "SOURCE_REGISTRY"]
