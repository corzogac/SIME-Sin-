"""Service for parsing and ingesting IDEAM open forecast data.

IDEAM publishes city/municipality-level weather forecasts at:
http://www.pronosticosyalertas.gov.co/datos-abiertos-ideam

The data comes as CSV/TXT files with columns:
    Latitud, Longitud, IdMunicipio, Municipio, IdDepartamento, Departamento,
    Region, FechaPrediccion, HoraPrediccion, Temperatura, Velocidadviento,
    Direccionviento, PresionAtmosferica, PuntoRocio, NubosidadTotal,
    Precipitacion, ProbTormenta, HumedadRelativa

This service parses those files and converts them into our internal models.
"""

import csv
import io
from datetime import datetime
from pathlib import Path

from loguru import logger

from backend.app.models.schemas import Coordinates, RiskLevel

# Precipitation thresholds (mm/3h) for risk classification
# Based on IDEAM classification for Colombia's tropical climate
PRECIP_THRESHOLDS = {
    "light": 2.5,       # < 2.5 mm/3h
    "moderate": 7.5,    # 2.5 - 7.5 mm/3h
    "heavy": 15.0,      # 7.5 - 15 mm/3h
    "very_heavy": 30.0, # 15 - 30 mm/3h
    "torrential": 50.0, # > 30 mm/3h
}

# Colombian departments most vulnerable to flooding (historically)
HIGH_VULNERABILITY_DEPARTMENTS = {
    "Choco", "Bolivar", "Magdalena", "Atlantico", "Sucre",
    "Cordoba", "Cesar", "La Guajira", "Norte de Santander",
    "Santander", "Antioquia", "Cauca", "Narino", "Putumayo",
    "Caqueta", "Amazonas",
}


def classify_precip_risk(
    precip_mm: float, department: str = ""
) -> RiskLevel:
    """Classify flood risk based on predicted precipitation and location."""
    # Increase sensitivity for historically vulnerable departments
    vulnerability_factor = 0.7 if department in HIGH_VULNERABILITY_DEPARTMENTS else 1.0

    adjusted = precip_mm / vulnerability_factor

    if adjusted < PRECIP_THRESHOLDS["light"]:
        return RiskLevel.LOW
    if adjusted < PRECIP_THRESHOLDS["moderate"]:
        return RiskLevel.MODERATE
    if adjusted < PRECIP_THRESHOLDS["heavy"]:
        return RiskLevel.HIGH
    if adjusted < PRECIP_THRESHOLDS["very_heavy"]:
        return RiskLevel.VERY_HIGH
    return RiskLevel.EXTREME


def parse_ideam_forecast(content: str) -> list[dict]:
    """Parse IDEAM forecast CSV content into structured records.

    Args:
        content: Raw CSV text from IDEAM open data file.

    Returns:
        List of parsed forecast records with risk classification.
    """
    records = []
    reader = csv.DictReader(io.StringIO(content))

    for row in reader:
        try:
            lat = float(row.get("Latitud", 0))
            lon = float(row.get("Longitud", 0))
            municipality = row.get("Municipio", "").strip()
            department = row.get("Departamento", "").strip()
            region = row.get("Region", "").strip()

            date_str = row.get("FechaPrediccion", "").strip()
            hour_str = row.get("HoraPrediccion", "").strip()

            precip = _safe_float(row.get("Precipitacion"))
            temperature = _safe_float(row.get("Temperatura"))
            humidity = _safe_float(row.get("HumedadRelativa"))
            wind_speed = _safe_float(row.get("Velocidadviento"))
            wind_dir = _safe_float(row.get("Direccionviento"))
            pressure = _safe_float(row.get("PresionAtmosferica"))
            cloud_cover = _safe_float(row.get("NubosidadTotal"))
            storm_prob = _safe_float(row.get("ProbTormenta"))
            dew_point = _safe_float(row.get("PuntoRocio"))

            # Parse datetime
            forecast_dt = None
            if date_str:
                try:
                    if hour_str:
                        forecast_dt = datetime.strptime(
                            f"{date_str} {hour_str}", "%Y-%m-%d %H:%M"
                        )
                    else:
                        forecast_dt = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    forecast_dt = None

            # Classify precipitation risk
            risk = RiskLevel.LOW
            if precip is not None:
                risk = classify_precip_risk(precip, department)

            # Boost risk if storm probability is high
            if storm_prob is not None and storm_prob > 70:
                risk_order = [
                    RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH,
                    RiskLevel.VERY_HIGH, RiskLevel.EXTREME,
                ]
                idx = risk_order.index(risk)
                if idx < len(risk_order) - 1:
                    risk = risk_order[idx + 1]

            records.append({
                "coordinates": Coordinates(lat=lat, lon=lon),
                "municipality": municipality,
                "department": department,
                "region": region,
                "forecast_datetime": forecast_dt,
                "precipitation_mm": precip,
                "temperature_c": temperature,
                "humidity_pct": humidity,
                "wind_speed_kmh": wind_speed,
                "wind_direction_deg": wind_dir,
                "pressure_hpa": pressure,
                "cloud_cover_pct": cloud_cover,
                "storm_probability_pct": storm_prob,
                "dew_point_c": dew_point,
                "risk_level": risk,
            })
        except Exception as e:
            logger.warning(f"Skipping malformed IDEAM row: {e}")
            continue

    logger.info(f"Parsed {len(records)} IDEAM forecast records")
    return records


def parse_ideam_file(filepath: str | Path) -> list[dict]:
    """Parse an IDEAM forecast file from disk."""
    path = Path(filepath)
    if not path.exists():
        logger.error(f"IDEAM file not found: {path}")
        return []

    # IDEAM files may use latin-1 encoding
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            content = path.read_text(encoding=encoding)
            return parse_ideam_forecast(content)
        except UnicodeDecodeError:
            continue

    logger.error(f"Could not decode IDEAM file: {path}")
    return []


def aggregate_department_risk(records: list[dict]) -> dict[str, dict]:
    """Aggregate forecast records by department to get overall risk levels.

    Returns:
        Dict mapping department name to aggregated risk info.
    """
    departments: dict[str, list] = {}

    for rec in records:
        dept = rec.get("department", "Unknown")
        if dept not in departments:
            departments[dept] = []
        departments[dept].append(rec)

    result = {}
    risk_order = [
        RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH,
        RiskLevel.VERY_HIGH, RiskLevel.EXTREME,
    ]

    for dept, recs in departments.items():
        precip_values = [
            r["precipitation_mm"] for r in recs
            if r.get("precipitation_mm") is not None
        ]
        risks = [r["risk_level"] for r in recs]

        max_risk = RiskLevel.LOW
        for r in risks:
            if risk_order.index(r) > risk_order.index(max_risk):
                max_risk = r

        # Find the center coordinates for the department
        lats = [r["coordinates"].lat for r in recs]
        lons = [r["coordinates"].lon for r in recs]

        result[dept] = {
            "department": dept,
            "max_risk_level": max_risk,
            "num_municipalities": len(recs),
            "max_precipitation_mm": max(precip_values) if precip_values else 0,
            "avg_precipitation_mm": (
                sum(precip_values) / len(precip_values) if precip_values else 0
            ),
            "center_lat": sum(lats) / len(lats),
            "center_lon": sum(lons) / len(lons),
            "high_risk_count": sum(
                1 for r in risks
                if risk_order.index(r) >= risk_order.index(RiskLevel.HIGH)
            ),
        }

    return result


def _safe_float(value: str | None) -> float | None:
    """Safely convert a string to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None
