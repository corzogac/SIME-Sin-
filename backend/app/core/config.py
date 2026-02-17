"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database (PostgreSQL+PostGIS recommended, SQLite for dev)
    database_url: str = "sqlite+aiosqlite:///./data/sime.db"

    # Open-Meteo
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    open_meteo_flood_url: str = "https://flood-api.open-meteo.com/v1/flood"

    # OpenWeatherMap (optional)
    openweathermap_api_key: str = ""

    # DEM data
    dem_data_dir: str = "./data/dem"

    # Colombia bounding box
    colombia_lat_min: float = -4.23
    colombia_lat_max: float = 13.39
    colombia_lon_min: float = -81.73
    colombia_lon_max: float = -66.85

    # Cache TTL (seconds)
    weather_cache_ttl: int = 900
    flood_cache_ttl: int = 3600

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
