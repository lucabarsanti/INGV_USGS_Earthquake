"""Data models for Earthquake Monitor."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Quake:
    """A single earthquake event, normalized across sources."""

    id: str
    source: str
    magnitude: float
    mag_type: str | None
    place: str
    time: datetime
    latitude: float
    longitude: float
    depth_km: float | None
    url: str | None
    distance_km: float | None = field(default=None)
    # USGS extras (None for catalogs that do not provide them)
    tsunami: bool = field(default=False)
    felt: int | None = field(default=None)
    mmi: float | None = field(default=None)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation (attributes / events)."""
        return {
            "id": self.id,
            "source": self.source,
            "magnitude": self.magnitude,
            "mag_type": self.mag_type,
            "place": self.place,
            "time": self.time.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "depth_km": self.depth_km,
            "url": self.url,
            "distance_km": round(self.distance_km, 1)
            if self.distance_km is not None
            else None,
            "tsunami": self.tsunami,
            "felt": self.felt,
            "mmi": self.mmi,
        }
