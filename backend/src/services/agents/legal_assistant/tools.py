"""LangChain tool wrappers for legal retrieval."""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.legal import RetrievalQuery
from src.services.vector_store import VectorStoreRegistry, vector_store_registry


class SearchLegalArticlesInput(BaseModel):
    """Input schema for the search_legal_articles tool."""

    question: str = Field(..., description="Legal question in Vietnamese")
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8


def search_legal_articles(
    question: str,
    databases: list[str] | None = None,
    top_k: int = 8,
    registry: VectorStoreRegistry = vector_store_registry,
) -> list[dict]:
    """Search registered legal databases and return JSON-serializable hits."""

    query = RetrievalQuery(question=question, databases=databases or ["default"], top_k=top_k)
    candidates = registry.search(query)
    return [candidate.model_dump(mode="json") for candidate in candidates]


def build_search_legal_articles_tool(registry: VectorStoreRegistry = vector_store_registry):
    """Create a LangChain StructuredTool when langchain-core is installed."""

    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        return lambda question, databases=None, top_k=8: search_legal_articles(
            question=question,
            databases=databases,
            top_k=top_k,
            registry=registry,
        )

    def _run(question: str, databases: list[str] | None = None, top_k: int = 8) -> list[dict]:
        return search_legal_articles(
            question=question,
            databases=databases,
            top_k=top_k,
            registry=registry,
        )

    return StructuredTool.from_function(
        name="search_legal_articles",
        description="Retrieve relevant Vietnamese legal articles and source references.",
        func=_run,
        args_schema=SearchLegalArticlesInput,
    )
