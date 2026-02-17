"""API routes for SIME emergency flood management system."""

from fastapi import APIRouter, HTTPException, Query

from backend.app.models.schemas import (
    FloodAlert,
    FloodForecast,
    FloodZone,
    MonitoringStation,
    SafeRoute,
    WeatherData,
)
from backend.app.services.dem_service import estimate_flood_extent
from backend.app.services.flood_service import (
    COLOMBIA_MONITORING_POINTS,
    get_active_alerts,
    get_current_flood_zones,
    get_flood_forecast,
)
from backend.app.services.routing_service import find_safe_route
from backend.app.services.weather_service import (
    get_current_weather,
    get_precipitation_forecast,
)

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "SIME"}


@router.get("/weather/current", response_model=WeatherData)
async def weather_current(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
):
    """Get current weather conditions for a location in Colombia."""
    try:
        return await get_current_weather(lat, lon)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather API error: {e}")


@router.get("/weather/forecast")
async def weather_forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    days: int = Query(7, ge=1, le=16),
):
    """Get precipitation forecast for flood risk estimation."""
    try:
        return await get_precipitation_forecast(lat, lon, days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forecast API error: {e}")


@router.get("/flood/current", response_model=list[FloodZone])
async def flood_current():
    """Get current flood risk zones across Colombia."""
    try:
        return await get_current_flood_zones()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flood assessment error: {e}")


@router.get("/flood/forecast", response_model=list[FloodForecast])
async def flood_forecast(
    days: int = Query(7, ge=1, le=30, description="Forecast days ahead"),
):
    """Get flood risk forecasts for the next N days."""
    try:
        return await get_flood_forecast(days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flood forecast error: {e}")


@router.get("/route/safe", response_model=SafeRoute)
async def route_safe(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    dest_lat: float = Query(..., ge=-90, le=90),
    dest_lon: float = Query(..., ge=-180, le=180),
):
    """Find a safe route between two points, avoiding flood zones."""
    try:
        return await find_safe_route(origin_lat, origin_lon, dest_lat, dest_lon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {e}")


@router.get("/alerts", response_model=list[FloodAlert])
async def alerts():
    """Get active flood alerts for Colombia."""
    try:
        return await get_active_alerts()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Alert generation error: {e}")


@router.get("/flood/extent")
async def flood_extent(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    water_rise_m: float = Query(..., ge=0, le=50, description="Water level rise in meters"),
    radius_km: float = Query(5.0, ge=0.5, le=50, description="Search radius in km"),
):
    """Estimate flood extent around a river point using DEM data."""
    try:
        return estimate_flood_extent(lat, lon, water_rise_m, radius_km)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flood extent error: {e}")


@router.get("/stations", response_model=list[MonitoringStation])
async def stations():
    """Get list of monitoring stations across Colombia."""
    station_list = []
    for lat, lon, name, river in COLOMBIA_MONITORING_POINTS:
        # Determine department based on known locations
        dept_map = {
            "Bogota": "Cundinamarca",
            "Medellin": "Antioquia",
            "Cali": "Valle del Cauca",
            "Barranquilla": "Atlantico",
            "Cartagena": "Bolivar",
            "Bucaramanga": "Santander",
            "Barrancabermeja": "Santander",
            "Pasto": "Narino",
            "Ibague": "Tolima",
            "Popayan": "Cauca",
            "Tunja": "Boyaca",
            "Florencia": "Caqueta",
            "Lorica": "Cordoba",
            "San Marcos": "Sucre",
            "Apartado": "Antioquia",
        }
        from backend.app.models.schemas import Coordinates

        station_list.append(MonitoringStation(
            station_id=f"st-{name.lower().replace(' ', '-')}",
            name=name,
            coordinates=Coordinates(lat=lat, lon=lon),
            station_type="hydrological",
            department=dept_map.get(name, "Unknown"),
            river_name=river,
        ))
    return station_list
