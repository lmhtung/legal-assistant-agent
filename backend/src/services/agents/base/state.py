"""TypedDict mô tả state được truyền giữa các node LangGraph."""
from __future__ import annotations

from typing import Any, TypedDict

from src.schemas.legal import LegalArticle, RetrievedCandidate
from src.services.agents.base.context import AgentContext


class AgentState(TypedDict, total=False):
    """State mutable đi từ node này sang node khác.

    ``total=False`` cho phép mỗi node chỉ thêm field mình tạo ra. Ví dụ node
    rewrite thêm ``retrieval_question``, node retrieve thêm ``selected_articles``
    và node format thêm ``relevant_docs``/``relevant_articles``.
    """

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
