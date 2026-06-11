"""Health-check endpoint."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple readiness signal for load balancers and humans."""

    return {"status": "ok"}
