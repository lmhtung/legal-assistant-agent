"""Context runtime truyền qua các node của agent."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Các tùy chọn runtime không nên trộn trực tiếp vào câu hỏi người dùng.

    Context giúp state rõ ràng hơn: câu hỏi là dữ liệu đầu vào chính, còn
    ``databases``, ``top_k`` hay flag rewrite là điều khiển cách agent xử lý.
    """

    session_id: str | None = None
    user_id: str | None = None
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8
    competition_mode: bool = True
    rewrite_query_enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
