# SIME - Sistema de Informacion para Manejo de Emergencias

**Real-time flood emergency management system for Colombia.**

SIME uses real-time meteorological data, river discharge forecasts, and terrain analysis to identify flood-risk zones and generate safe evacuation paths across Colombian territory.

## Features

- **Real-time flood monitoring** — Ingests live data from IDEAM (Colombia's hydrometeorological institute) and Open-Meteo APIs
- **Flood risk mapping** — Combines elevation models (DEM), precipitation forecasts, and river discharge data to estimate flood extent
- **Safe path routing** — Generates evacuation routes that avoid current and predicted flood zones
- **Forecast-based alerts** — Uses GloFAS river discharge forecasts (up to 7 days ahead) to flag high-risk areas before flooding occurs
- **Interactive map dashboard** — Web-based visualization of flood zones, risk levels, and recommended paths

## Architecture

```
SIME-Sin-/
├── backend/
│   ├── app/
│   │   ├── api/          # REST API endpoints
│   │   ├── core/         # Configuration and startup
│   │   ├── models/       # Data models
│   │   ├── services/     # Business logic (flood modeling, routing, data ingestion)
│   │   └── utils/        # Helper functions
│   └── tests/            # Backend tests
├── frontend/
│   ├── static/           # CSS, JS, images
│   └── templates/        # HTML templates
├── data/                 # Local data cache (DEM tiles, etc.)
├── docs/                 # Documentation
└── scripts/              # Utility scripts (data download, setup)
```

## Data Sources

| Source | Type | Access |
|--------|------|--------|
| [Open-Meteo Weather API](https://open-meteo.com/) | Precipitation, temperature, wind forecasts | Free, no API key |
| [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) | GloFAS river discharge forecasts | Free, no API key |
| [IDEAM DHIME](https://dhime.ideam.gov.co/) | Historical hydrological/meteorological data | Free, portal access |
| [IDEAM Open Data](http://www.pronosticosyalertas.gov.co/datos-abiertos-ideam) | City-level weather forecasts (CSV) | Free download |
| [Copernicus DEM GLO-30](https://dataspace.copernicus.eu/) | 30m elevation model | Free |
| [GloFAS](https://global-flood.emergency.copernicus.eu/) | Global flood awareness system | Free with registration |

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/corzogac/SIME-Sin-.git
cd SIME-Sin-

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run the application
python -m backend.app.main
```

The application will be available at `http://localhost:8000`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/flood/current` | Current flood risk zones |
| GET | `/api/v1/flood/forecast` | Forecast-based flood risk (1-7 days) |
| GET | `/api/v1/weather/current?lat=&lon=` | Current weather for coordinates |
| GET | `/api/v1/route/safe?origin=&dest=` | Safe route avoiding flood zones |
| GET | `/api/v1/alerts` | Active flood alerts for Colombia |
| GET | `/api/v1/stations` | Monitoring station data |

## License

MIT License
