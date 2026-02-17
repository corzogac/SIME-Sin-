"""Pydantic models for API request/response schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"


class Coordinates(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class WeatherData(BaseModel):
    coordinates: Coordinates
    timestamp: datetime
    temperature_c: float | None = None
    humidity_pct: float | None = None
    precipitation_mm: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    pressure_hpa: float | None = None


class FloodZone(BaseModel):
    zone_id: str
    name: str
    risk_level: RiskLevel
    coordinates: list[Coordinates]
    estimated_depth_m: float | None = None
    river_discharge_m3s: float | None = None
    timestamp: datetime


class FloodForecast(BaseModel):
    zone_id: str
    name: str
    risk_level: RiskLevel
    forecast_date: datetime
    probability_pct: float
    expected_discharge_m3s: float | None = None
    coordinates: list[Coordinates]


class RoutePoint(BaseModel):
    lat: float
    lon: float
    elevation_m: float | None = None
    risk_level: RiskLevel = RiskLevel.LOW


class SafeRoute(BaseModel):
    origin: Coordinates
    destination: Coordinates
    waypoints: list[RoutePoint]
    total_distance_km: float
    estimated_time_min: float
    max_risk_level: RiskLevel
    avoids_flood_zones: bool = True


class FloodAlert(BaseModel):
    alert_id: str
    title: str
    description: str
    risk_level: RiskLevel
    affected_area: str
    coordinates: Coordinates
    issued_at: datetime
    expires_at: datetime | None = None
    source: str


class MonitoringStation(BaseModel):
    station_id: str
    name: str
    coordinates: Coordinates
    station_type: str
    department: str
    river_name: str | None = None
    current_level_m: float | None = None
    last_update: datetime | None = None
