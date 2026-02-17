"""Service for flood risk assessment using GloFAS data, precipitation, and terrain.

Combines three data sources for comprehensive flood risk:
1. GloFAS river discharge forecasts (Open-Meteo Flood API)
2. Precipitation forecasts (Open-Meteo Weather API)
3. DEM-based flood extent estimation (when DEM tiles are available)
"""

from datetime import datetime, timezone
from uuid import uuid4

import httpx
from cachetools import TTLCache
from loguru import logger

from backend.app.core.config import settings
from backend.app.models.schemas import (
    Coordinates,
    FloodAlert,
    FloodForecast,
    FloodZone,
    RiskLevel,
)
from backend.app.services.dem_service import discharge_to_water_rise, estimate_flood_extent

_flood_cache: TTLCache = TTLCache(maxsize=200, ttl=settings.flood_cache_ttl)

# Key Colombian river monitoring points (lat, lon, name, river)
COLOMBIA_MONITORING_POINTS = [
    (7.09, -73.17, "Barrancabermeja", "Magdalena"),
    (10.40, -75.51, "Cartagena", "Canal del Dique"),
    (8.75, -75.88, "Lorica", "Sinu"),
    (9.24, -75.83, "San Marcos", "San Jorge"),
    (7.89, -76.63, "Apartado", "Rio Leon"),
    (4.44, -75.24, "Ibague", "Combeima"),
    (3.45, -76.52, "Cali", "Cauca"),
    (6.25, -75.56, "Medellin", "Medellin"),
    (4.71, -74.07, "Bogota", "Bogota"),
    (1.21, -77.28, "Pasto", "Pasto"),
    (10.39, -75.05, "Barranquilla", "Magdalena"),
    (7.12, -73.12, "Bucaramanga", "Rio de Oro"),
    (5.54, -73.36, "Tunja", "Chicamocha"),
    (2.44, -76.61, "Popayan", "Cauca"),
    (1.61, -75.61, "Florencia", "Hacha"),
]


def _classify_discharge_risk(discharge_m3s: float, median_m3s: float) -> RiskLevel:
    """Classify flood risk based on river discharge relative to median."""
    if median_m3s <= 0:
        return RiskLevel.LOW
    ratio = discharge_m3s / median_m3s
    if ratio < 1.5:
        return RiskLevel.LOW
    if ratio < 3.0:
        return RiskLevel.MODERATE
    if ratio < 5.0:
        return RiskLevel.HIGH
    if ratio < 10.0:
        return RiskLevel.VERY_HIGH
    return RiskLevel.EXTREME


async def get_river_discharge_forecast(lat: float, lon: float, days: int = 7) -> dict:
    """Fetch GloFAS river discharge forecast from Open-Meteo Flood API."""
    cache_key = f"discharge:{round(lat, 2)}:{round(lon, 2)}"
    if cache_key in _flood_cache:
        return _flood_cache[cache_key]

    url = settings.open_meteo_flood_url
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "river_discharge",
        "forecast_days": min(days, 210),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    _flood_cache[cache_key] = data
    logger.info(f"Fetched river discharge forecast for ({lat}, {lon})")
    return data


async def get_precipitation_risk(lat: float, lon: float) -> tuple[RiskLevel, float]:
    """Assess flood risk from accumulated precipitation forecasts.

    Fetches 72h precipitation forecast and evaluates accumulated risk.
    Returns (risk_level, total_precip_mm).
    """
    from backend.app.services.weather_service import get_precipitation_forecast

    try:
        forecasts = await get_precipitation_forecast(lat, lon, days=3)
        total_mm = sum(
            f.get("precipitation_mm", 0) or 0
            for f in forecasts
        )
        # 72h accumulated precipitation thresholds for Colombia
        if total_mm < 20:
            return RiskLevel.LOW, total_mm
        if total_mm < 50:
            return RiskLevel.MODERATE, total_mm
        if total_mm < 100:
            return RiskLevel.HIGH, total_mm
        if total_mm < 200:
            return RiskLevel.VERY_HIGH, total_mm
        return RiskLevel.EXTREME, total_mm
    except Exception as e:
        logger.warning(f"Precipitation risk check failed for ({lat}, {lon}): {e}")
        return RiskLevel.LOW, 0.0


def _combine_risks(discharge_risk: RiskLevel, precip_risk: RiskLevel) -> RiskLevel:
    """Combine discharge and precipitation risks, taking the worse of the two
    but also escalating when both indicate elevated risk."""
    order = [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.EXTREME]
    d_idx = order.index(discharge_risk)
    p_idx = order.index(precip_risk)

    base = max(d_idx, p_idx)

    # If both sources indicate at least moderate risk, escalate by one level
    if d_idx >= 1 and p_idx >= 1:
        base = min(base + 1, len(order) - 1)

    return order[base]


async def get_current_flood_zones() -> list[FloodZone]:
    """Assess current flood risk across Colombian monitoring points.

    Combines river discharge data with precipitation forecasts and,
    when available, DEM-based flood extent estimation.
    """
    zones = []

    for lat, lon, name, river in COLOMBIA_MONITORING_POINTS:
        try:
            data = await get_river_discharge_forecast(lat, lon, days=3)
            daily = data.get("daily", {})
            discharges = daily.get("river_discharge", [])

            if not discharges:
                continue

            current_discharge = discharges[0] if discharges[0] is not None else 0
            valid = [d for d in discharges if d is not None]
            median_proxy = sum(valid) / len(valid) if valid else 1

            discharge_risk = _classify_discharge_risk(current_discharge, median_proxy)

            # Also check precipitation forecasts
            precip_risk, total_precip = await get_precipitation_risk(lat, lon)

            # Combined risk assessment
            combined_risk = _combine_risks(discharge_risk, precip_risk)

            # Attempt DEM-based depth estimation
            estimated_depth = None
            flood_coords = [Coordinates(lat=lat, lon=lon)]
            water_rise = discharge_to_water_rise(current_discharge, median_proxy)
            if water_rise > 0:
                estimated_depth = round(water_rise, 2)
                try:
                    extent = estimate_flood_extent(lat, lon, water_rise)
                    if extent.get("boundary_coordinates"):
                        flood_coords = extent["boundary_coordinates"]
                except Exception as e:
                    logger.debug(f"DEM extent estimation unavailable for {name}: {e}")

            zone = FloodZone(
                zone_id=f"zone-{name.lower().replace(' ', '-')}",
                name=f"{name} - Rio {river}",
                risk_level=combined_risk,
                coordinates=flood_coords,
                estimated_depth_m=estimated_depth,
                river_discharge_m3s=current_discharge,
                timestamp=datetime.now(timezone.utc),
            )
            zones.append(zone)
        except Exception as e:
            logger.warning(f"Failed to assess flood zone at {name}: {e}")

    logger.info(f"Assessed {len(zones)} flood zones")
    return zones


async def get_flood_forecast(days: int = 7) -> list[FloodForecast]:
    """Generate flood forecasts for Colombian monitoring points."""
    forecasts = []

    for lat, lon, name, river in COLOMBIA_MONITORING_POINTS:
        try:
            data = await get_river_discharge_forecast(lat, lon, days=days)
            daily = data.get("daily", {})
            discharges = daily.get("river_discharge", [])
            dates = daily.get("time", [])

            if not discharges or not dates:
                continue

            valid = [d for d in discharges if d is not None]
            median_proxy = sum(valid) / len(valid) if valid else 1

            for i, (date_str, discharge) in enumerate(zip(dates, discharges)):
                if discharge is None:
                    continue
                risk = _classify_discharge_risk(discharge, median_proxy)
                if risk in (RiskLevel.LOW, RiskLevel.MODERATE):
                    continue  # Only include significant risk in forecasts

                forecasts.append(FloodForecast(
                    zone_id=f"forecast-{name.lower().replace(' ', '-')}-d{i}",
                    name=f"{name} - Rio {river}",
                    risk_level=risk,
                    forecast_date=datetime.fromisoformat(date_str),
                    probability_pct=min(95.0, 50.0 + (discharge / median_proxy) * 10),
                    expected_discharge_m3s=discharge,
                    coordinates=[Coordinates(lat=lat, lon=lon)],
                ))
        except Exception as e:
            logger.warning(f"Failed to forecast for {name}: {e}")

    logger.info(f"Generated {len(forecasts)} flood forecasts")
    return forecasts


async def get_active_alerts() -> list[FloodAlert]:
    """Generate alerts based on current high-risk conditions."""
    zones = await get_current_flood_zones()
    alerts = []

    for zone in zones:
        if zone.risk_level not in (RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.EXTREME):
            continue

        severity = {
            RiskLevel.HIGH: "Riesgo alto de inundacion",
            RiskLevel.VERY_HIGH: "Riesgo muy alto de inundacion",
            RiskLevel.EXTREME: "EMERGENCIA - Riesgo extremo de inundacion",
        }

        alerts.append(FloodAlert(
            alert_id=str(uuid4()),
            title=f"Alerta de inundacion: {zone.name}",
            description=(
                f"{severity[zone.risk_level]}. "
                f"Caudal actual: {zone.river_discharge_m3s:.1f} m3/s. "
                "Se recomienda precaucion y seguir instrucciones de autoridades locales."
            ),
            risk_level=zone.risk_level,
            affected_area=zone.name,
            coordinates=zone.coordinates[0],
            issued_at=datetime.now(timezone.utc),
            expires_at=None,
            source="SIME - Open-Meteo/GloFAS",
        ))

    logger.info(f"Generated {len(alerts)} active alerts")
    return alerts
