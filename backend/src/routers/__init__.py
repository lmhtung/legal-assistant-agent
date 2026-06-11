"""Router exports used by the FastAPI app factory."""
from src.routers.dataset import router as dataset_router
from src.routers.health import router as health_router
from src.routers.legal import router as legal_router

__all__ = ["dataset_router", "health_router", "legal_router"]
