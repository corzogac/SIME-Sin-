"""Service for Digital Elevation Model (DEM) based flood extent estimation.

Uses rasterio to read GeoTIFF elevation tiles (Copernicus DEM GLO-30 or FABDEM)
and estimates flood extent by identifying areas below a projected water level
along river channels.

DEM data must be downloaded separately and placed in the configured dem_data_dir.
Recommended source: FABDEM (30m, forest/building-removed) from
https://zenodo.org/records/8101259

How it works:
1. Load DEM tile covering the area of interest
2. Given a river point and estimated water level rise, find all connected
   cells whose elevation is below the flood water surface
3. Return the flood extent as a list of coordinate polygons
"""

from pathlib import Path

import numpy as np
from loguru import logger

from backend.app.core.config import settings
from backend.app.models.schemas import Coordinates, RiskLevel

# Approximate meters per degree of latitude at Colombia's latitude (~5 deg N)
METERS_PER_DEG_LAT = 111_320
METERS_PER_DEG_LON = 110_540  # at ~5 deg N


def _find_dem_tile(lat: float, lon: float) -> Path | None:
    """Find the DEM GeoTIFF tile that covers the given coordinates.

    Searches the DEM data directory for tiles following standard naming
    conventions (e.g., Copernicus GLO-30 or FABDEM naming).
    """
    dem_dir = Path(settings.dem_data_dir)
    if not dem_dir.exists():
        logger.warning(f"DEM directory does not exist: {dem_dir}")
        return None

    # Try common naming patterns
    # Copernicus: Copernicus_DSM_COG_10_N04_00_W075_00_DEM.tif
    # FABDEM: N04W075_FABDEM_V1-2.tif
    # Generic: srtm_XX_YY.tif

    lat_prefix = "N" if lat >= 0 else "S"
    lon_prefix = "W" if lon < 0 else "E"
    lat_int = int(abs(lat))
    lon_int = int(abs(lon))

    patterns = [
        f"*{lat_prefix}{lat_int:02d}*{lon_prefix}{lon_int:03d}*.tif",
        f"*{lat_prefix}{lat_int:02d}*{lon_prefix}{lon_int:03d}*.tiff",
        "*.tif",
    ]

    for pattern in patterns:
        matches = list(dem_dir.glob(pattern))
        if matches:
            # If multiple matches, try to find the one containing our point
            for match in matches:
                if _tile_contains_point(match, lat, lon):
                    return match
            # Fallback to first match
            return matches[0]

    return None


def _tile_contains_point(filepath: Path, lat: float, lon: float) -> bool:
    """Check if a DEM tile covers the given point (requires rasterio)."""
    try:
        import rasterio

        with rasterio.open(filepath) as src:
            bounds = src.bounds
            return (
                bounds.left <= lon <= bounds.right
                and bounds.bottom <= lat <= bounds.top
            )
    except Exception:
        return False


def estimate_flood_extent(
    river_lat: float,
    river_lon: float,
    water_rise_m: float,
    search_radius_km: float = 5.0,
) -> dict:
    """Estimate flood extent around a river point given a water level rise.

    Args:
        river_lat: Latitude of the river gauge/point.
        river_lon: Longitude of the river gauge/point.
        water_rise_m: Estimated water level rise in meters.
        search_radius_km: Radius to search for flood extent.

    Returns:
        Dict with flood extent info including affected coordinates and area.
    """
    tile_path = _find_dem_tile(river_lat, river_lon)
    if tile_path is None:
        logger.warning(
            f"No DEM tile found for ({river_lat}, {river_lon}). "
            "Download DEM data to the configured directory."
        )
        return _fallback_estimate(river_lat, river_lon, water_rise_m)

    try:
        import rasterio
        from rasterio.windows import from_bounds

        return _dem_based_estimate(
            tile_path, river_lat, river_lon, water_rise_m, search_radius_km
        )
    except ImportError:
        logger.warning("rasterio not installed, using fallback estimation")
        return _fallback_estimate(river_lat, river_lon, water_rise_m)
    except Exception as e:
        logger.error(f"DEM flood estimation failed: {e}")
        return _fallback_estimate(river_lat, river_lon, water_rise_m)


def _dem_based_estimate(
    tile_path: Path,
    river_lat: float,
    river_lon: float,
    water_rise_m: float,
    search_radius_km: float,
) -> dict:
    """Perform DEM-based flood fill estimation."""
    import rasterio
    from rasterio.windows import from_bounds

    radius_deg_lat = search_radius_km / (METERS_PER_DEG_LAT / 1000)
    radius_deg_lon = search_radius_km / (METERS_PER_DEG_LON / 1000)

    with rasterio.open(tile_path) as src:
        # Define the window around our point of interest
        window = from_bounds(
            river_lon - radius_deg_lon,
            river_lat - radius_deg_lat,
            river_lon + radius_deg_lon,
            river_lat + radius_deg_lat,
            src.transform,
        )

        # Read elevation data for the window
        elevation = src.read(1, window=window)
        transform = src.window_transform(window)

        if elevation.size == 0:
            return _fallback_estimate(river_lat, river_lon, water_rise_m)

        # Find the river point in the raster
        row, col = ~transform * (river_lon, river_lat)
        row, col = int(row), int(col)

        if not (0 <= row < elevation.shape[0] and 0 <= col < elevation.shape[1]):
            return _fallback_estimate(river_lat, river_lon, water_rise_m)

        # River bed elevation
        river_elevation = elevation[row, col]
        flood_surface = river_elevation + water_rise_m

        # Find all connected cells below flood surface (flood fill)
        flooded = _flood_fill(elevation, row, col, flood_surface)

        # Convert flooded cells back to coordinates
        flooded_coords = []
        ys, xs = np.where(flooded)
        # Sample up to 200 boundary points for the polygon
        step = max(1, len(ys) // 200)
        for i in range(0, len(ys), step):
            lon, lat = transform * (xs[i], ys[i])
            flooded_coords.append(Coordinates(lat=lat, lon=lon))

        # Estimate area
        cell_area_m2 = abs(transform.a * transform.e) * METERS_PER_DEG_LAT * METERS_PER_DEG_LON
        total_area_km2 = np.sum(flooded) * cell_area_m2 / 1e6

        risk = _area_to_risk(total_area_km2, water_rise_m)

        return {
            "river_elevation_m": float(river_elevation),
            "flood_surface_m": float(flood_surface),
            "water_rise_m": water_rise_m,
            "flooded_area_km2": round(total_area_km2, 3),
            "flooded_cells": int(np.sum(flooded)),
            "risk_level": risk,
            "boundary_coordinates": flooded_coords,
            "source": "dem",
        }


def _flood_fill(
    elevation: np.ndarray, start_row: int, start_col: int, max_elevation: float
) -> np.ndarray:
    """Perform flood fill from a starting point, filling all connected cells
    whose elevation is at or below the given water surface level.

    Uses BFS for connected-component analysis.
    """
    rows, cols = elevation.shape
    flooded = np.zeros((rows, cols), dtype=bool)

    if elevation[start_row, start_col] > max_elevation:
        return flooded

    queue = [(start_row, start_col)]
    flooded[start_row, start_col] = True

    # 4-connected neighbors
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    # Limit iterations for large areas
    max_iterations = 500_000
    iterations = 0

    while queue and iterations < max_iterations:
        r, c = queue.pop(0)
        iterations += 1

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not flooded[nr, nc]:
                if elevation[nr, nc] <= max_elevation:
                    flooded[nr, nc] = True
                    queue.append((nr, nc))

    if iterations >= max_iterations:
        logger.warning("Flood fill hit iteration limit")

    return flooded


def _fallback_estimate(
    river_lat: float, river_lon: float, water_rise_m: float
) -> dict:
    """Simple radius-based flood estimate when DEM is unavailable.

    Uses empirical relationship: flood radius ~ sqrt(water_rise) * factor
    for relatively flat Colombian river valleys.
    """
    # Empirical: ~1 km radius per meter of rise in flat terrain
    estimated_radius_km = min(water_rise_m * 0.8, 20.0)
    estimated_area_km2 = 3.14159 * estimated_radius_km ** 2

    risk = _area_to_risk(estimated_area_km2, water_rise_m)

    # Generate approximate circular boundary
    n_points = 24
    coords = []
    for i in range(n_points):
        angle = 2 * 3.14159 * i / n_points
        dlat = estimated_radius_km / (METERS_PER_DEG_LAT / 1000) * np.sin(angle)
        dlon = estimated_radius_km / (METERS_PER_DEG_LON / 1000) * np.cos(angle)
        coords.append(Coordinates(lat=river_lat + dlat, lon=river_lon + dlon))

    return {
        "river_elevation_m": None,
        "flood_surface_m": None,
        "water_rise_m": water_rise_m,
        "flooded_area_km2": round(estimated_area_km2, 3),
        "flooded_cells": 0,
        "risk_level": risk,
        "boundary_coordinates": coords,
        "source": "fallback_estimate",
    }


def _area_to_risk(area_km2: float, depth_m: float) -> RiskLevel:
    """Classify risk based on estimated flood area and depth."""
    score = area_km2 * 0.5 + depth_m * 10

    if score < 5:
        return RiskLevel.LOW
    if score < 15:
        return RiskLevel.MODERATE
    if score < 40:
        return RiskLevel.HIGH
    if score < 80:
        return RiskLevel.VERY_HIGH
    return RiskLevel.EXTREME


def discharge_to_water_rise(
    discharge_m3s: float, median_discharge_m3s: float
) -> float:
    """Estimate water level rise from discharge anomaly.

    Uses a simplified power-law rating curve approximation:
    h ~ (Q/Q_median)^0.4 - 1 (meters above normal)
    """
    if median_discharge_m3s <= 0 or discharge_m3s <= median_discharge_m3s:
        return 0.0
    ratio = discharge_m3s / median_discharge_m3s
    return max(0.0, (ratio ** 0.4 - 1) * 3.0)  # scale factor ~3m for significant events
