"""Factory tạo retrieval store từ cấu hình."""
from __future__ import annotations

from src.config import VectorStoreSettings
from src.services.embeddings.client import EmbeddingsClient
from src.services.vector_store.base import LegalVectorStore
from src.services.vector_store.chroma import ChromaLegalStore
from src.services.vector_store.hybrid import HybridLegalStore
from src.services.vector_store.in_memory import InMemoryLegalStore


class VectorStoreFactory:
    """Tạo đúng implementation vector store cho từng database logic."""

    def __init__(self, settings: VectorStoreSettings) -> None:
        self.settings = settings
        self._embeddings: EmbeddingsClient | None = None

    def create(self, database: str) -> LegalVectorStore:
        """Tạo store theo ``legal_assistant.vector_store.mode`` trong config.yaml."""

        if self.settings.mode == "bm25":
            return InMemoryLegalStore(database=database)
        if self.settings.mode == "chroma":
            return ChromaLegalStore(
                database=database,
                persist_directory=str(self.settings.persist_directory),
                collection_prefix=self.settings.default_collection,
                embeddings=self._get_embeddings(),
            )
        return HybridLegalStore(
            lexical_store=InMemoryLegalStore(database=database),
            vector_store=ChromaLegalStore(
                database=database,
                persist_directory=str(self.settings.persist_directory),
                collection_prefix=self.settings.default_collection,
                embeddings=self._get_embeddings(),
            ),
            rrf_k=self.settings.rrf_k,
        )

    def _get_embeddings(self) -> EmbeddingsClient:
        """Khởi tạo embedding client một lần cho local Chroma fallback."""

        if self._embeddings is None:
            self._embeddings = EmbeddingsClient()
        return self._embeddings
