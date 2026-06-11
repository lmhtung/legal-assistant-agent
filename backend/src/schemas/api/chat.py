"""Schema cho endpoint chat và batch theo format bài thi."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.legal import LegalAnswerRequest, LegalAnswerResponse


class ChatRequest(BaseModel):
    """Request kiểu chat, được map nội bộ sang ``LegalAnswerRequest``."""

    message: str
    session_id: str | None = None
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8


class ChatResponse(BaseModel):
    """Response kiểu chat, giữ lại debug tool-call để dễ quan sát agent."""

    session_id: str | None = None
    message: str
    answer: LegalAnswerResponse
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class CompetitionBatchRequest(BaseModel):
    """Batch request; mỗi item dùng đúng schema hỏi đáp đơn lẻ."""

    items: list[LegalAnswerRequest]


class CompetitionBatchResponse(BaseModel):
    """Batch response có helper xuất ra ``results.json``."""

    results: list[LegalAnswerResponse]

    def to_results_json(self) -> list[dict[str, Any]]:
        """Chỉ lấy các field mà bài thi thường yêu cầu khi submit."""

        return [item.to_competition_record() for item in self.results]
