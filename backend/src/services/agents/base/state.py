from __future__ import annotations

from typing import Any, TypedDict

from src.schemas.legal import LegalArticle, RetrievedCandidate
from src.services.agents.base.context import AgentContext


class AgentState(TypedDict, total=False):
    question_id: int | None
    question: str
    context: AgentContext
    messages: list[Any]
    tool_calls: list[dict[str, Any]]
    retrieved: list[RetrievedCandidate]
    selected_articles: list[LegalArticle]
    answer: str
    relevant_docs: list[str]
    relevant_articles: list[str]
    debug: dict[str, Any]
