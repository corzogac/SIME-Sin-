"""Service for fetching real-time weather data from Open-Meteo and IDEAM."""

from datetime import datetime, timezone

import httpx
from cachetools import TTLCache
from loguru import logger

from backend.app.core.config import settings
from backend.app.models.schemas import Coordinates, WeatherData

_weather_cache: TTLCache = TTLCache(maxsize=500, ttl=settings.weather_cache_ttl)


def _cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 2)}:{round(lon, 2)}"


async def get_current_weather(lat: float, lon: float) -> WeatherData:
    """Fetch current weather conditions for a given location via Open-Meteo."""
    key = _cache_key(lat, lon)
    if key in _weather_cache:
        logger.debug(f"Weather cache hit for {key}")
        return _weather_cache[key]

    url = f"{settings.open_meteo_base_url}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "wind_direction_10m",
            "surface_pressure",
        ]),
        "timezone": "America/Bogota",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    current = data.get("current", {})
    weather = WeatherData(
        coordinates=Coordinates(lat=lat, lon=lon),
        timestamp=datetime.now(timezone.utc),
        temperature_c=current.get("temperature_2m"),
        humidity_pct=current.get("relative_humidity_2m"),
        precipitation_mm=current.get("precipitation"),
        wind_speed_kmh=current.get("wind_speed_10m"),
        wind_direction_deg=current.get("wind_direction_10m"),
        pressure_hpa=current.get("surface_pressure"),
    )

    _weather_cache[key] = weather
    logger.info(f"Fetched weather for ({lat}, {lon}): {weather.precipitation_mm}mm precip")
    return weather


async def get_precipitation_forecast(
    lat: float, lon: float, days: int = 7
) -> list[dict]:
    """Fetch hourly precipitation forecast for flood risk estimation."""
    url = f"{settings.open_meteo_base_url}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation,precipitation_probability",
        "forecast_days": min(days, 16),
        "timezone": "America/Bogota",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    precip = hourly.get("precipitation", [])
    prob = hourly.get("precipitation_probability", [])

    forecasts = []
    for i, t in enumerate(times):
        forecasts.append({
            "time": t,
            "precipitation_mm": precip[i] if i < len(precip) else None,
            "probability_pct": prob[i] if i < len(prob) else None,
        })

    logger.info(f"Fetched {len(forecasts)} hourly precipitation forecasts for ({lat}, {lon})")
    return forecasts
