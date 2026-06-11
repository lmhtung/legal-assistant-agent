"""Dataset import HTTP endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dependencies import get_dataset_service
from src.schemas.knowledge import DatasetImportRequest, DatasetImportResponse
from src.services.dataset import DatasetService

router = APIRouter(prefix="/api/v1/dataset", tags=["dataset"])


@router.post("/import", response_model=DatasetImportResponse)
async def import_dataset(
    request: DatasetImportRequest,
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetImportResponse:
    """Import structured records into PostgreSQL and/or vector store."""

    return await service.import_dataset(request)
