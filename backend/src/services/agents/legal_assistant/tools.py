"""Tool wrapper cho legal retrieval nếu muốn dùng theo style LangChain tools."""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.legal import RetrievalQuery
from src.services.vector_store import VectorStoreRegistry, vector_store_registry


class SearchLegalArticlesInput(BaseModel):
    """Schema input cho tool ``search_legal_articles``."""

    question: str = Field(..., description="Legal question in Vietnamese")
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8


def search_legal_articles(
    question: str,
    databases: list[str] | None = None,
    top_k: int = 8,
    registry: VectorStoreRegistry = vector_store_registry,
) -> list[dict]:
    """Search các legal database đã đăng ký và trả kết quả JSON-serializable."""

    query = RetrievalQuery(question=question, databases=databases or ["default"], top_k=top_k)
    candidates = registry.search(query)
    return [candidate.model_dump(mode="json") for candidate in candidates]


def build_search_legal_articles_tool(registry: VectorStoreRegistry = vector_store_registry):
    """Tạo LangChain StructuredTool nếu ``langchain-core`` có sẵn.

    Nếu dependency chưa cài, hàm trả về callable thường để phần còn lại của code
    vẫn chạy được trong môi trường test nhẹ.
    """

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
        """Adapter đồng bộ đúng signature mà StructuredTool mong đợi."""

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
