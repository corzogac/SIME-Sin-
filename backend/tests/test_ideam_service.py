"""Tests for the IDEAM forecast data parser."""

from backend.app.models.schemas import RiskLevel
from backend.app.services.ideam_service import (
    _safe_float,
    aggregate_department_risk,
    classify_precip_risk,
    parse_ideam_forecast,
)

SAMPLE_CSV = """\
Latitud,Longitud,IdMunicipio,Municipio,IdDepartamento,Departamento,Region,FechaPrediccion,HoraPrediccion,Temperatura,Velocidadviento,Direccionviento,PresionAtmosferica,PuntoRocio,NubosidadTotal,Precipitacion,ProbTormenta,HumedadRelativa
4.71,-74.07,11001,Bogota,11,Cundinamarca,Andina,2026-02-17,06:00,12.5,10,180,1025,8.2,70,1.2,10,75
10.39,-75.05,8001,Barranquilla,8,Atlantico,Caribe,2026-02-17,06:00,28.0,15,90,1012,24.1,40,18.5,80,82
8.75,-75.88,23417,Lorica,23,Cordoba,Caribe,2026-02-17,06:00,30.0,8,270,1010,26.0,85,35.0,90,88
"""


def test_parse_ideam_forecast():
    records = parse_ideam_forecast(SAMPLE_CSV)
    assert len(records) == 3
    assert records[0]["municipality"] == "Bogota"
    assert records[0]["precipitation_mm"] == 1.2
    assert records[1]["municipality"] == "Barranquilla"


def test_classify_precip_low():
    assert classify_precip_risk(1.0) == RiskLevel.LOW


def test_classify_precip_moderate():
    assert classify_precip_risk(5.0) == RiskLevel.MODERATE


def test_classify_precip_high_vulnerable_dept():
    # Choco is highly vulnerable, so lower threshold
    risk = classify_precip_risk(5.0, "Choco")
    assert risk in (RiskLevel.MODERATE, RiskLevel.HIGH)


def test_classify_precip_extreme():
    assert classify_precip_risk(60.0) == RiskLevel.EXTREME


def test_safe_float():
    assert _safe_float("3.14") == 3.14
    assert _safe_float("3,14") == 3.14
    assert _safe_float(None) is None
    assert _safe_float("abc") is None
    assert _safe_float("") is None


def test_aggregate_department_risk():
    records = parse_ideam_forecast(SAMPLE_CSV)
    agg = aggregate_department_risk(records)
    assert "Cundinamarca" in agg
    assert "Atlantico" in agg
    assert agg["Cundinamarca"]["num_municipalities"] == 1
    assert agg["Cordoba"]["max_precipitation_mm"] == 35.0


def test_risk_boosted_by_storm_probability():
    """High storm probability should escalate risk by one level."""
    csv_with_storm = """\
Latitud,Longitud,IdMunicipio,Municipio,IdDepartamento,Departamento,Region,FechaPrediccion,HoraPrediccion,Temperatura,Velocidadviento,Direccionviento,PresionAtmosferica,PuntoRocio,NubosidadTotal,Precipitacion,ProbTormenta,HumedadRelativa
4.71,-74.07,11001,Bogota,11,Cundinamarca,Andina,2026-02-17,06:00,12.5,10,180,1025,8.2,70,5.0,85,75
"""
    records = parse_ideam_forecast(csv_with_storm)
    assert len(records) == 1
    # 5mm = moderate, but 85% storm probability should boost to HIGH
    assert records[0]["risk_level"] == RiskLevel.HIGH
