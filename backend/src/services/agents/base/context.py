"""Context object passed through agent nodes."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Runtime options that should not be mixed into the user question."""

    session_id: str | None = None
    user_id: str | None = None
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8
    competition_mode: bool = True
    rewrite_query_enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
