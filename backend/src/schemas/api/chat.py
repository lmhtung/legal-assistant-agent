"""API schemas for chat and competition-style answer endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.legal import LegalAnswerRequest, LegalAnswerResponse


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8


class ChatResponse(BaseModel):
    session_id: str | None = None
    message: str
    answer: LegalAnswerResponse
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class CompetitionBatchRequest(BaseModel):
    items: list[LegalAnswerRequest]


class CompetitionBatchResponse(BaseModel):
    results: list[LegalAnswerResponse]

    def to_results_json(self) -> list[dict[str, Any]]:
        return [item.to_competition_record() for item in self.results]
