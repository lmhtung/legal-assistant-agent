"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from src.config import get_settings
from src.routers import dataset_router, health_router, legal_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI app instance."""

    settings = get_settings()
    app = FastAPI(
        title="Vietnamese Legal Assistant Agent",
        version="0.1.0",
    )
    # Store settings on app.state for future lifecycle hooks or middleware.
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(dataset_router)
    app.include_router(legal_router)
    return app


app = create_app()
