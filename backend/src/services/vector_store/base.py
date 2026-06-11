"""Shared vector-store interfaces and registry."""
from __future__ import annotations

from typing import Protocol

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate


class LegalVectorStore(Protocol):
    """Minimal contract implemented by lexical, vector, and hybrid stores."""

    def add_articles(self, articles: list[LegalArticle]) -> None:
        """Add or update legal records in the store."""
        ...

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Return ranked candidates for a retrieval query."""
        ...


class VectorStoreRegistry:
    """In-process registry mapping database names to concrete stores."""

    def __init__(self) -> None:
        self._stores: dict[str, LegalVectorStore] = {}

    def register(self, database: str, store: LegalVectorStore) -> None:
        """Register a store for a logical database name."""

        self._stores[database] = store

    def get(self, database: str) -> LegalVectorStore:
        """Return a registered store, failing loudly on unknown databases."""

        if database not in self._stores:
            raise KeyError(f"Database '{database}' is not registered")
        return self._stores[database]

    def has(self, database: str) -> bool:
        """Check whether a database has already been initialized."""

        return database in self._stores

    def list_databases(self) -> list[str]:
        """List database names available in this process."""

        return sorted(self._stores)

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Search all requested databases and merge by score."""

        merged: list[RetrievedCandidate] = []
        for database in query.databases:
            if database not in self._stores:
                continue
            merged.extend(self._stores[database].search(query))
        merged.sort(key=lambda item: item.score, reverse=True)
        return merged[: query.top_k]


# Shared registry used by API dependencies. It is intentionally in-memory;
# persistent data lives in PostgreSQL and Chroma.
vector_store_registry = VectorStoreRegistry()
