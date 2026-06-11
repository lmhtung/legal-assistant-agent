"""Orchestrator cho job import dataset offline.

DatasetService nối các bước data lại với nhau: load record, lưu PostgreSQL, tạo
store retrieval theo config và index các điều luật. Service này không expose API.
"""
from __future__ import annotations

from src.config import get_settings
from src.schemas.knowledge import DatasetImportRequest, DatasetImportResponse, LegalKnowledgeRecord, load_records_from_path
from src.services.dataset.repository import PostgresKnowledgeRepository
from src.services.vector_store import VectorStoreFactory, VectorStoreRegistry, vector_store_registry


class DatasetService:
    """Load structured records, persist DB và build retrieval index."""

    def __init__(
        self,
        registry: VectorStoreRegistry = vector_store_registry,
        repository: PostgresKnowledgeRepository | None = None,
    ) -> None:
        self.settings = get_settings()
        self.registry = registry
        self.repository = repository or PostgresKnowledgeRepository()
        self.store_factory = VectorStoreFactory(self.settings.legal_assistant.vector_store)

    async def import_dataset(self, request: DatasetImportRequest) -> DatasetImportResponse:
        """Import record từ request/file, rồi ghi DB và/hoặc index vector store."""

        records = self._records_from_request(request)
        if request.save_to_postgres and self.settings.postgres.enabled:
            await self.repository.init_schema()
            await self.repository.upsert_many(records)
        if request.index_vector_store:
            self._index_records(request.database, records)
        return DatasetImportResponse(
            database=request.database,
            num_records=len(records),
            ids=[record.id for record in records],
        )

    def _records_from_request(self, request: DatasetImportRequest) -> list[LegalKnowledgeRecord]:
        """Gộp record inline và record đọc từ ``input_path``."""

        records = list(request.records)
        if request.input_path is not None:
            records.extend(load_records_from_path(request.input_path))
        return records

    def _index_records(self, database: str, records: list[LegalKnowledgeRecord]) -> None:
        """Tạo store theo database nếu chưa có rồi add articles vào index."""

        if not self.registry.has(database):
            self.registry.register(database, self.store_factory.create(database))
        articles = [record.to_legal_article(database=database) for record in records]
        self.registry.get(database).add_articles(articles)
