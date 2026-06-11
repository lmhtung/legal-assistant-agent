"""Các dependency provider dùng bởi FastAPI.

FastAPI gọi các hàm trong file này thông qua ``Depends``. Việc cache bằng
``lru_cache`` giúp mỗi process chỉ tạo một LLM client và một agent, tránh khởi
tạo connection/model wrapper lặp lại cho từng request.
"""
from __future__ import annotations

from functools import lru_cache

from src.config import get_settings
from src.services.agents.legal_assistant import LegalAssistantAgent
from src.services.llm.client import LLMClient
from src.services.mcp import MCPRetrievalClient


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Tạo LLM client dùng chung cho toàn bộ FastAPI process."""

    return LLMClient()


@lru_cache(maxsize=1)
def get_mcp_retrieval_client() -> MCPRetrievalClient | None:
    """Tạo MCP retrieval client nếu config bật MCP."""

    settings = get_settings()
    if not settings.mcp_retrieval.enabled:
        return None
    return MCPRetrievalClient(
        servers=settings.mcp_retrieval.servers,
        primary_server=settings.mcp_retrieval.primary_server,
    )


@lru_cache(maxsize=1)
def get_legal_assistant_agent() -> LegalAssistantAgent:
    """Tạo agent pháp lý duy nhất của service.

    Nếu config tắt ``query_rewrite.use_llm`` thì agent vẫn chạy được, nhưng sẽ
    bỏ qua LLM ở bước rewrite/HyDE và dùng fallback answer khi cần.
    """

    settings = get_settings()
    llm = get_llm_client() if settings.legal_assistant.query_rewrite.use_llm else None
    return LegalAssistantAgent(llm=llm, mcp_client=get_mcp_retrieval_client())
