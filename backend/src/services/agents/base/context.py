"""Context runtime truyền qua các node của agent."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Các tùy chọn runtime không trộn trực tiếp vào câu hỏi người dùng."""

    session_id: str | None = None
    categories: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8

    @property
    def databases(self) -> list[str]:
        """Alias tương thích: database cũ chính là category hiện tại."""

        return self.categories
