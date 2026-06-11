"""Wrapper cho embedding endpoint OpenAI-compatible."""
from __future__ import annotations

from src.config import settings


class EmbeddingsClient:
    """Client embedding dùng LangChain ``OpenAIEmbeddings``.

    Endpoint có thể là server local bạn đã host, miễn là API tương thích OpenAI.
    """

    def __init__(self):
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:  # pragma: no cover - guard khi thiếu dependency
            raise RuntimeError("Install langchain-openai to use the embeddings endpoint") from exc

        self.embeddings = OpenAIEmbeddings(
            model=settings.embeddings.model,
            base_url=settings.embeddings.base_url,
            api_key=settings.embeddings.api_key,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed nhiều record pháp luật khi build vector database."""

        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed một query đã rewrite/HyDE để search vector store."""

        return self.embeddings.embed_query(text)
