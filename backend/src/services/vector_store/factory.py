"""Factory for creating retrieval stores from configuration."""
from __future__ import annotations

from src.config import VectorStoreSettings
from src.services.vector_store.base import LegalVectorStore
from src.services.vector_store.chroma import ChromaLegalStore
from src.services.vector_store.hybrid import HybridLegalStore
from src.services.vector_store.in_memory import InMemoryLegalStore


class VectorStoreFactory:
    """Build the configured vector-store implementation for a database."""

    def __init__(self, settings: VectorStoreSettings) -> None:
        self.settings = settings

    def create(self, database: str) -> LegalVectorStore:
        """Create bm25, chroma, or hybrid store according to config.yaml."""

        if self.settings.mode == "bm25":
            return InMemoryLegalStore(database=database)
        if self.settings.mode == "chroma":
            return ChromaLegalStore(
                database=database,
                persist_directory=str(self.settings.persist_directory),
                collection_prefix=self.settings.default_collection,
            )
        return HybridLegalStore(
            lexical_store=InMemoryLegalStore(database=database),
            vector_store=ChromaLegalStore(
                database=database,
                persist_directory=str(self.settings.persist_directory),
                collection_prefix=self.settings.default_collection,
            ),
            rrf_k=self.settings.rrf_k,
        )
