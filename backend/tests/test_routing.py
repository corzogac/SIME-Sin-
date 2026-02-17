"""Tests for the routing service utility functions."""

from backend.app.services.routing_service import (
    _haversine_km,
    _snap_to_grid,
)


def test_haversine_bogota_to_cali():
    # Bogota to Cali is approximately 300 km
    dist = _haversine_km(4.71, -74.07, 3.45, -76.52)
    assert 280 < dist < 320


def test_haversine_same_point():
    dist = _haversine_km(4.71, -74.07, 4.71, -74.07)
    assert dist == 0.0


def test_snap_to_grid():
    assert _snap_to_grid(4.714) == 4.71
    assert _snap_to_grid(4.715) == 4.72
    assert _snap_to_grid(0.0) == 0.0


def test_snap_to_grid_negative():
    snapped = _snap_to_grid(-74.073)
    assert abs(snapped - (-74.07)) < 0.001
