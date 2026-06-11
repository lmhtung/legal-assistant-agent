"""API schemas for chat and competition batch endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.legal import LegalAnswerRequest, LegalAnswerResponse


class ChatRequest(BaseModel):
    """Chat-style request mapped internally to LegalAnswerRequest."""

    message: str
    session_id: str | None = None
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8


class ChatResponse(BaseModel):
    """Chat response with tool-call debug information."""

    session_id: str | None = None
    message: str
    answer: LegalAnswerResponse
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class CompetitionBatchRequest(BaseModel):
    """Batch request using the same item schema as single-answer API."""

    items: list[LegalAnswerRequest]


class CompetitionBatchResponse(BaseModel):
    """Batch response with helper for results.json export."""

    results: list[LegalAnswerResponse]

    def to_results_json(self) -> list[dict[str, Any]]:
        """Return all answers in competition submission format."""

        return [item.to_competition_record() for item in self.results]
