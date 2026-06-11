"""OpenAI-compatible embedding client wrapper."""
from __future__ import annotations

from src.config import settings


class EmbeddingsClient:
    """Wrapper around LangChain OpenAIEmbeddings for the local embedding server."""

    def __init__(self):
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("Install langchain-openai to use the embeddings endpoint") from exc

        self.embeddings = OpenAIEmbeddings(
            model=settings.embeddings.model,
            base_url=settings.embeddings.base_url,
            api_key=settings.embeddings.api_key,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed many indexed legal records."""

        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed one retrieval query."""

        return self.embeddings.embed_query(text)
