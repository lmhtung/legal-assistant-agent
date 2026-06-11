"""Chroma vector store for structured legal records."""
from __future__ import annotations

import re
from typing import Any

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate
from src.services.embeddings.client import EmbeddingsClient

_NON_WORD_RE = re.compile(r"[^\w]+")


def safe_collection_name(value: str) -> str:
    """Convert arbitrary database names into Chroma-safe collection names."""

    name = _NON_WORD_RE.sub("_", value.lower()).strip("_")
    return name[:60] or "legal_articles"


class ChromaLegalStore:
    """Persistent vector store backed by Chroma and the local embedding endpoint."""

    def __init__(
        self,
        database: str,
        persist_directory: str,
        collection_prefix: str = "legal_articles",
        embeddings: EmbeddingsClient | None = None,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("Install chromadb to use ChromaLegalStore") from exc

        self.database = database
        self.embeddings = embeddings or EmbeddingsClient()
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=safe_collection_name(f"{collection_prefix}_{database}"),
            metadata={"hnsw:space": "cosine"},
        )

    def add_articles(self, articles: list[LegalArticle]) -> None:
        """Embed and upsert structured records into Chroma."""

        if not articles:
            return
        documents = [index_text(article) for article in articles]
        self.collection.upsert(
            ids=[article.article_id for article in articles],
            documents=documents,
            embeddings=self.embeddings.embed_documents(documents),
            metadatas=[self._metadata(article) for article in articles],
        )

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Embed the retrieval text and return nearest legal records."""

        result = self.collection.query(
            query_embeddings=[self.embeddings.embed_query(query.question)],
            n_results=query.top_k,
            include=["documents", "metadatas", "distances"],
        )
        candidates = self._to_candidates(result)
        for rank, candidate in enumerate(candidates[: query.top_k], start=1):
            candidate.rank = rank
        return candidates[: query.top_k]

    def _metadata(self, article: LegalArticle) -> dict[str, Any]:
        """Serialize record fields Chroma can store as metadata."""

        return {
            "id": article.id,
            "law_id": article.law_id,
            "law_name": article.law_name,
            "doc_type": article.doc_type,
            "database": article.database,
            "chapter": article.chapter or "",
            "article": article.article,
            "article_title": article.article_title or "",
            "content": article.content,
            "author": article.author or "",
            "vector_text": index_text(article),
        }

    def _to_candidates(self, result: dict[str, Any]) -> list[RetrievedCandidate]:
        """Convert Chroma query output into retrieval candidates."""

        candidates: list[RetrievedCandidate] = []
        ids = result.get("ids", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for article_id, metadata, distance in zip(ids, metadatas, distances):
            score = 1.0 / (1.0 + float(distance or 0.0))
            article = LegalArticle(
                id=str(metadata.get("id") or article_id),
                article_id=article_id,
                law_id=str(metadata.get("law_id") or ""),
                law_name=str(metadata.get("law_name") or ""),
                doc_type=str(metadata.get("doc_type") or ""),
                database=str(metadata.get("database") or self.database),
                chapter=str(metadata.get("chapter") or "") or None,
                article=str(metadata.get("article") or ""),
                article_title=str(metadata.get("article_title") or "") or None,
                content=str(metadata.get("content") or ""),
                author=str(metadata.get("author") or "") or None,
                extra={"vector_text": str(metadata.get("vector_text") or "")},
                score=score,
            )
            candidates.append(RetrievedCandidate(article=article, source="vector", score=score))
        return candidates


def index_text(article: LegalArticle) -> str:
    """Return canonical text used for embedding structured records."""

    return str(article.extra.get("vector_text") or article.vector_text)
