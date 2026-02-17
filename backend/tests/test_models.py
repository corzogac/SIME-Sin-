"""Tests for SIME data models."""

from datetime import datetime, timezone

from backend.app.models.schemas import (
    Coordinates,
    FloodAlert,
    FloodZone,
    RiskLevel,
    RoutePoint,
    SafeRoute,
    WeatherData,
)


def test_coordinates_valid():
    c = Coordinates(lat=4.71, lon=-74.07)
    assert c.lat == 4.71
    assert c.lon == -74.07


def test_weather_data():
    w = WeatherData(
        coordinates=Coordinates(lat=4.71, lon=-74.07),
        timestamp=datetime.now(timezone.utc),
        temperature_c=18.5,
        precipitation_mm=2.3,
    )
    assert w.temperature_c == 18.5
    assert w.precipitation_mm == 2.3


def test_flood_zone():
    zone = FloodZone(
        zone_id="zone-bogota",
        name="Bogota - Rio Bogota",
        risk_level=RiskLevel.HIGH,
        coordinates=[Coordinates(lat=4.71, lon=-74.07)],
        river_discharge_m3s=150.0,
        timestamp=datetime.now(timezone.utc),
    )
    assert zone.risk_level == RiskLevel.HIGH
    assert zone.river_discharge_m3s == 150.0


def test_risk_levels():
    assert RiskLevel.LOW.value == "low"
    assert RiskLevel.EXTREME.value == "extreme"


def test_safe_route():
    route = SafeRoute(
        origin=Coordinates(lat=4.71, lon=-74.07),
        destination=Coordinates(lat=3.45, lon=-76.52),
        waypoints=[
            RoutePoint(lat=4.71, lon=-74.07, risk_level=RiskLevel.LOW),
            RoutePoint(lat=3.45, lon=-76.52, risk_level=RiskLevel.LOW),
        ],
        total_distance_km=300.5,
        estimated_time_min=450.0,
        max_risk_level=RiskLevel.LOW,
        avoids_flood_zones=True,
    )
    assert route.total_distance_km == 300.5
    assert route.avoids_flood_zones is True


def test_flood_alert():
    alert = FloodAlert(
        alert_id="test-001",
        title="Alerta de inundacion: Bogota",
        description="Riesgo alto de inundacion",
        risk_level=RiskLevel.HIGH,
        affected_area="Bogota - Rio Bogota",
        coordinates=Coordinates(lat=4.71, lon=-74.07),
        issued_at=datetime.now(timezone.utc),
        source="SIME",
    )
    assert alert.risk_level == RiskLevel.HIGH
    assert "Bogota" in alert.title
