"""Tests for distance helpers."""
from custom_components.earthquake_monitor.util import haversine_km


def test_haversine_one_degree_longitude_at_equator():
    assert abs(haversine_km(0, 0, 0, 1) - 111.19) < 0.5


def test_haversine_zero_distance():
    assert haversine_km(42.5, 13.0, 42.5, 13.0) == 0.0


def test_haversine_rome_milan():
    # Rome (41.90, 12.50) to Milan (45.46, 9.19) is ~477 km.
    assert abs(haversine_km(41.90, 12.50, 45.46, 9.19) - 477) < 10
