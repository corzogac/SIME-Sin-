"""Utility script to download IDEAM open forecast data for Colombia.

IDEAM publishes city-level weather forecasts as downloadable CSV files at:
http://www.pronosticosyalertas.gov.co/datos-abiertos-ideam

This script fetches the latest forecast file and stores it locally for
offline processing or database ingestion.

Usage:
    python scripts/fetch_ideam_forecast.py
"""

import sys
from datetime import datetime
from pathlib import Path

import httpx

IDEAM_FORECAST_URL = "http://www.pronosticosyalertas.gov.co/datos-abiertos-ideam"
OUTPUT_DIR = Path("data")


def fetch_forecast():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"ideam_forecast_{timestamp}.html"

    print(f"Fetching IDEAM forecast data from: {IDEAM_FORECAST_URL}")

    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.get(IDEAM_FORECAST_URL)
            response.raise_for_status()

        output_file.write_text(response.text, encoding="utf-8")
        print(f"Saved to: {output_file}")
        print(f"Size: {output_file.stat().st_size:,} bytes")
        print(
            "\nNote: This page contains links to downloadable CSV/TXT forecast files."
        )
        print(
            "Parse the HTML to extract download links and fetch individual data files."
        )
    except httpx.HTTPError as e:
        print(f"Error fetching data: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    fetch_forecast()
