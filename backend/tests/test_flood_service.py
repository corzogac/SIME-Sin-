"""Tests for the flood service risk classification."""

from backend.app.models.schemas import RiskLevel
from backend.app.services.flood_service import _classify_discharge_risk


def test_classify_low_risk():
    assert _classify_discharge_risk(100, 100) == RiskLevel.LOW


def test_classify_moderate_risk():
    assert _classify_discharge_risk(200, 100) == RiskLevel.MODERATE


def test_classify_high_risk():
    assert _classify_discharge_risk(400, 100) == RiskLevel.HIGH


def test_classify_very_high_risk():
    assert _classify_discharge_risk(700, 100) == RiskLevel.VERY_HIGH


def test_classify_extreme_risk():
    assert _classify_discharge_risk(1500, 100) == RiskLevel.EXTREME


def test_classify_zero_median():
    assert _classify_discharge_risk(500, 0) == RiskLevel.LOW
