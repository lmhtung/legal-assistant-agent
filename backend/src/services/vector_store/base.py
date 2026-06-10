from __future__ import annotations

from typing import Protocol

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate


class LegalVectorStore(Protocol):
    def add_articles(self, articles: list[LegalArticle]) -> None:
        ...

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        ...


class VectorStoreRegistry:
    def __init__(self) -> None:
        self._stores: dict[str, LegalVectorStore] = {}

    def register(self, database: str, store: LegalVectorStore) -> None:
        self._stores[database] = store

    def get(self, database: str) -> LegalVectorStore:
        if database not in self._stores:
            raise KeyError(f"Database '{database}' is not registered")
        return self._stores[database]

    def has(self, database: str) -> bool:
        return database in self._stores

    def list_databases(self) -> list[str]:
        return sorted(self._stores)

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        merged: list[RetrievedCandidate] = []
        for database in query.databases:
            if database not in self._stores:
                continue
            merged.extend(self._stores[database].search(query))
        merged.sort(key=lambda item: item.score, reverse=True)
        return merged[: query.top_k]


vector_store_registry = VectorStoreRegistry()
