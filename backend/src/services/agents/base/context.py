from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8
    competition_mode: bool = True
    allow_mcp: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
