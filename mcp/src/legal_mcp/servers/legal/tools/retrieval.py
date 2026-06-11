"""Tool registration cho legal retrieval server."""
from __future__ import annotations


def register_retrieval_tools(server) -> None:
    """Đăng ký các tools legal vào FastMCP instance của server."""

    @server._mcp.tool()
    def search_legal_articles(
        query: str,
        original_question: str | None = None,
        query_variants: list[str] | None = None,
        databases: list[str] | None = None,
        top_k: int | None = None,
    ) -> dict:
        """Search vector DB đã build sẵn và trả legal article candidates."""

        del original_question, query_variants
        limit = top_k or server.settings.vector_store.top_k
        candidates = server.vector_retriever.search(
            query=query,
            databases=databases or ["default"],
            top_k=limit,
        )
        return {"candidates": [candidate.model_dump(mode="json") for candidate in candidates]}

    @server._mcp.tool()
    async def search_relevant(
        extra_refs: list[str],
        databases: list[str] | None = None,
        top_k: int = 16,
    ) -> dict:
        """Tìm điều luật liên quan từ extra trong PostgreSQL, không dùng embedding."""

        candidates = await server.postgres_repository.fetch_related(
            extra_refs=extra_refs,
            databases=databases or [],
            limit=top_k,
        )
        return {"candidates": [candidate.model_dump(mode="json") for candidate in candidates]}
