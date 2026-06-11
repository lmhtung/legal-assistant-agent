"""TypedDict state shared by LangGraph nodes."""
from __future__ import annotations

from typing import Any, TypedDict

from src.schemas.legal import LegalArticle, RetrievedCandidate
from src.services.agents.base.context import AgentContext


class AgentState(TypedDict, total=False):
    """Mutable state object passed from node to node."""

    question_id: int | None
    question: str
    rewritten_question: str
    hypothetical_answer: str
    retrieval_question: str
    query_variants: list[str]
    context: AgentContext
    messages: list[Any]
    tool_calls: list[dict[str, Any]]
    retrieved: list[RetrievedCandidate]
    selected_articles: list[LegalArticle]
    answer: str
    relevant_docs: list[str]
    relevant_articles: list[str]
    debug: dict[str, Any]
