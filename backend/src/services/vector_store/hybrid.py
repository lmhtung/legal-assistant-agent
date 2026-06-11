"""Hybrid retrieval by fusing lexical and vector rankings."""
from __future__ import annotations

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate
from src.services.vector_store.base import LegalVectorStore


class HybridLegalStore:
    """Combine BM25-like and vector search with Reciprocal Rank Fusion."""

    def __init__(self, lexical_store: LegalVectorStore, vector_store: LegalVectorStore, rrf_k: int = 60) -> None:
        self.lexical_store = lexical_store
        self.vector_store = vector_store
        self.rrf_k = rrf_k

    def add_articles(self, articles: list[LegalArticle]) -> None:
        """Index the same records in both retrieval backends."""

        self.lexical_store.add_articles(articles)
        self.vector_store.add_articles(articles)

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Merge lexical/vector ranks into one stable candidate list."""

        merged: dict[str, RetrievedCandidate] = {}
        scores: dict[str, float] = {}
        for source_results in [self.lexical_store.search(query), self.vector_store.search(query)]:
            for rank, candidate in enumerate(source_results, start=1):
                article_id = candidate.article.article_id
                scores[article_id] = scores.get(article_id, 0.0) + 1.0 / (self.rrf_k + rank)
                if article_id not in merged:
                    merged[article_id] = candidate
        ranked = sorted(merged.values(), key=lambda item: scores[item.article.article_id], reverse=True)
        for rank, candidate in enumerate(ranked[: query.top_k], start=1):
            score = scores[candidate.article.article_id]
            candidate.rank = rank
            candidate.score = score
            candidate.source = "hybrid"
            candidate.article.score = score
        return ranked[: query.top_k]
