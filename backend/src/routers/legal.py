"""Các HTTP endpoint phục vụ hỏi đáp pháp lý."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dependencies import get_legal_assistant_agent
from src.schemas.api.chat import ChatRequest, ChatResponse, CompetitionBatchRequest, CompetitionBatchResponse
from src.schemas.legal import LegalAnswerRequest, LegalAnswerResponse
from src.services.agents.legal_assistant import LegalAssistantAgent

router = APIRouter(prefix="/api/v1/legal", tags=["legal-assistant"])


@router.post("/answer", response_model=LegalAnswerResponse)
async def answer_question(
    request: LegalAnswerRequest,
    agent: LegalAssistantAgent = Depends(get_legal_assistant_agent),
) -> LegalAnswerResponse:
    """Trả lời một câu hỏi pháp lý đơn lẻ bằng agent chính."""

    return await agent.answer(request)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: LegalAssistantAgent = Depends(get_legal_assistant_agent),
) -> ChatResponse:
    """Wrapper dạng chat cho cùng luồng ``LegalAnswerRequest``.

    Endpoint này tiện cho UI hội thoại: request dùng ``message`` thay vì
    ``question`` và response trả kèm ``tool_calls`` để debug quá trình retrieve.
    """

    answer = await agent.answer(
        LegalAnswerRequest(
            question=request.message,
            databases=request.databases,
            top_k=request.top_k,
            include_debug=True,
        )
    )
    return ChatResponse(
        session_id=request.session_id,
        message=request.message,
        answer=answer,
        tool_calls=answer.debug.get("tool_calls", []),
    )


@router.post("/batch", response_model=CompetitionBatchResponse)
async def answer_batch(
    request: CompetitionBatchRequest,
    agent: LegalAssistantAgent = Depends(get_legal_assistant_agent),
) -> CompetitionBatchResponse:
    """Trả lời nhiều câu hỏi, phù hợp khi chạy tập test của cuộc thi."""

    results = [await agent.answer(item) for item in request.items]
    return CompetitionBatchResponse(results=results)
