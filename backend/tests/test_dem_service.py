"""Tests for the DEM-based flood extent estimation service."""

import numpy as np

from backend.app.models.schemas import RiskLevel
from backend.app.services.dem_service import (
    _area_to_risk,
    _fallback_estimate,
    _flood_fill,
    discharge_to_water_rise,
)


def test_flood_fill_flat_area():
    """Flood fill on a flat surface should fill everything below water level."""
    elevation = np.array([
        [5.0, 5.0, 5.0, 10.0],
        [5.0, 3.0, 5.0, 10.0],
        [5.0, 5.0, 5.0, 10.0],
        [10.0, 10.0, 10.0, 10.0],
    ])
    flooded = _flood_fill(elevation, 1, 1, 6.0)
    # All cells with elevation <= 6.0 that are connected to (1,1)
    assert flooded[1, 1]  # Start point (3.0)
    assert flooded[0, 0]  # 5.0 <= 6.0
    assert flooded[2, 2]  # 5.0 <= 6.0
    assert not flooded[0, 3]  # 10.0 > 6.0
    assert not flooded[3, 3]  # 10.0 > 6.0


def test_flood_fill_no_flooding():
    """If start point is above water level, nothing gets flooded."""
    elevation = np.array([
        [10.0, 10.0],
        [10.0, 10.0],
    ])
    flooded = _flood_fill(elevation, 0, 0, 5.0)
    assert not flooded.any()


def test_flood_fill_valley():
    """Flood fill respects ridges/barriers."""
    elevation = np.array([
        [3.0, 3.0, 20.0, 3.0],
        [3.0, 3.0, 20.0, 3.0],
    ])
    flooded = _flood_fill(elevation, 0, 0, 5.0)
    assert flooded[0, 0]
    assert flooded[0, 1]
    assert not flooded[0, 2]  # Ridge blocks flood
    assert not flooded[0, 3]  # Can't reach past ridge


def test_area_to_risk():
    assert _area_to_risk(0.5, 0.1) == RiskLevel.LOW
    assert _area_to_risk(10.0, 1.0) == RiskLevel.MODERATE
    assert _area_to_risk(20.0, 3.0) == RiskLevel.HIGH
    assert _area_to_risk(50.0, 5.0) == RiskLevel.VERY_HIGH
    assert _area_to_risk(200.0, 10.0) == RiskLevel.EXTREME


def test_discharge_to_water_rise_normal():
    """Normal discharge should produce no water rise."""
    rise = discharge_to_water_rise(100, 100)
    assert rise == 0.0


def test_discharge_to_water_rise_elevated():
    """Elevated discharge should produce positive water rise."""
    rise = discharge_to_water_rise(500, 100)
    assert rise > 0


def test_discharge_to_water_rise_zero_median():
    rise = discharge_to_water_rise(100, 0)
    assert rise == 0.0


def test_fallback_estimate():
    result = _fallback_estimate(4.71, -74.07, 2.0)
    assert result["source"] == "fallback_estimate"
    assert result["flooded_area_km2"] > 0
    assert result["risk_level"] in list(RiskLevel)
    assert len(result["boundary_coordinates"]) == 24
