"""MCP client gọi legal retrieval tools từ server dữ liệu bên ngoài.

Thiết kế học từ project mẫu: backend chỉ cấu hình danh sách MCP server. Tên tool
là contract giữa backend và legal MCP server, không để rải trong YAML.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate


class MCPRetrievalClient:
    """Client mỏng gọi một legal MCP server qua Streamable HTTP."""

    search_tool_name = "search_legal_articles"
    relevant_tool_name = "search_relevant"

    def __init__(self, servers: Mapping[str, Any], primary_server: str) -> None:
        self.servers = dict(servers)
        self.primary_server = primary_server

    async def search_legal_articles(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Gọi tool MCP search vector/hybrid."""

        payload = await self._call_tool(
            self.search_tool_name,
            {
                "query": query.question,
                "original_question": query.original_question,
                "query_variants": query.query_variants,
                "databases": query.databases,
                "top_k": query.top_k,
            },
        )
        return self._parse_candidates(payload, default_source="mcp")

    async def search_relevant(
        self,
        extra_refs: list[str],
        databases: list[str],
        top_k: int,
    ) -> list[RetrievedCandidate]:
        """Gọi tool MCP lấy điều luật liên quan từ PostgreSQL, không embedding."""

        payload = await self._call_tool(
            self.relevant_tool_name,
            {"extra_refs": extra_refs, "databases": databases, "top_k": top_k},
        )
        return self._parse_candidates(payload, default_source="related")

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Gọi một MCP tool trên primary server."""

        server = self._get_primary_server()
        url = self._server_value(server, "url")
        if not url:
            raise RuntimeError(f"MCP server '{self.primary_server}' chưa cấu hình url")

        self._hide_local_mcp_folder_from_imports()
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường MCP
            raise RuntimeError("Cần cài package mcp để bật mcp_retrieval") from exc

        async with streamablehttp_client(url) as streams:
            read_stream, write_stream = streams[0], streams[1]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
        return self._extract_payload(result)

    def _get_primary_server(self) -> Any:
        """Lấy config server chính, báo lỗi rõ nếu thiếu."""

        if self.primary_server not in self.servers:
            raise RuntimeError(
                f"MCP primary_server='{self.primary_server}' không tồn tại. "
                f"Available: {list(self.servers)}"
            )
        return self.servers[self.primary_server]

    def _server_value(self, server: Any, key: str) -> Any:
        """Đọc value từ Pydantic model hoặc dict."""

        if isinstance(server, dict):
            return server.get(key)
        return getattr(server, key, None)

    def _hide_local_mcp_folder_from_imports(self) -> None:
        """Tránh folder ``/repo/mcp`` shadow package MCP SDK khi chạy từ repo root."""

        repo_root = Path(__file__).resolve().parents[4]
        sys.path[:] = [item for item in sys.path if item and Path(item).resolve() != repo_root]
        cached = sys.modules.get("mcp")
        module_paths = [Path(item).resolve() for item in getattr(cached, "__path__", [])] if cached else []
        if repo_root / "mcp" in module_paths:
            del sys.modules["mcp"]

    def _extract_payload(self, result: Any) -> Any:
        """Lấy structured content hoặc JSON text từ kết quả MCP."""

        for attr in ["structuredContent", "structured_content"]:
            value = getattr(result, attr, None)
            if value is not None:
                return value
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
        return {}

    def _parse_candidates(self, payload: Any, default_source: str) -> list[RetrievedCandidate]:
        """Chuẩn hóa output MCP về schema nội bộ của backend."""

        if isinstance(payload, str):
            payload = json.loads(payload)
        items = payload.get("candidates", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []

        candidates: list[RetrievedCandidate] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            article_data = item.get("article", item)
            if not isinstance(article_data, dict):
                continue
            article_data = self._normalize_article_payload(article_data)
            score = float(item.get("score") or article_data.get("score") or 0.0)
            source = item.get("source") or default_source
            rank = item.get("rank") or index
            article = LegalArticle.model_validate(article_data | {"score": score})
            candidates.append(RetrievedCandidate(article=article, source=source, score=score, rank=rank))
        return candidates

    def _normalize_article_payload(self, article_data: dict[str, Any]) -> dict[str, Any]:
        """Bù field thiếu và chuẩn hóa ``extra`` từ JSON/string/list."""

        data = dict(article_data)
        data.setdefault("article_id", data.get("id"))
        data.setdefault("database", "default")
        extra = data.get("extra") or []
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except json.JSONDecodeError:
                extra = [item.strip() for item in extra.split(";") if item.strip()]
        data["extra"] = set(extra)
        return data
