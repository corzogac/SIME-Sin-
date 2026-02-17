"""SIME - Sistema de Informacion para Manejo de Emergencias.

Main application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.requests import Request

from backend.app.api.routes import router
from backend.app.core.config import settings

app = FastAPI(
    title="SIME - Sistema de Informacion para Manejo de Emergencias",
    description=(
        "Real-time flood emergency management system for Colombia. "
        "Provides flood risk mapping, safe routing, and forecast-based alerts."
    ),
    version="0.1.0",
)

# CORS — allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# API routes
app.include_router(router)


@app.get("/")
async def index(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.on_event("startup")
async def startup():
    logger.info("SIME starting up...")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Open-Meteo URL: {settings.open_meteo_base_url}")


@app.on_event("shutdown")
async def shutdown():
    logger.info("SIME shutting down...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
