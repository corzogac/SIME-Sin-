"""SIME - Sistema de Informacion para Manejo de Emergencias.

Main application entry point.
"""

import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.requests import Request

from backend.app.api.routes import router
from backend.app.api.websocket import ws_router
from backend.app.core.config import settings
from backend.app.core.database import close_db, init_db
from backend.app.services.alert_monitor import monitor_loop

_monitor_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    global _monitor_task

    logger.info("SIME starting up...")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Database: {settings.database_url}")
    logger.info(f"Open-Meteo URL: {settings.open_meteo_base_url}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start background alert monitor
    _monitor_task = asyncio.create_task(monitor_loop(interval_seconds=300))
    logger.info("Alert monitor started")

    yield

    # Shutdown
    if _monitor_task:
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
    await close_db()
    logger.info("SIME shut down")


app = FastAPI(
    title="SIME - Sistema de Informacion para Manejo de Emergencias",
    description=(
        "Real-time flood emergency management system for Colombia. "
        "Provides flood risk mapping, safe routing, and forecast-based alerts."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# CORS
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

# REST API routes
app.include_router(router)

# WebSocket routes
app.include_router(ws_router)


@app.get("/")
async def index(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
