"""Các HTTP endpoint phục vụ hỏi đáp pháp lý."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.dependencies import get_legal_assistant_agent
from src.schemas.api.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamDoneEvent,
    ChatStreamErrorEvent,
    ChatStreamMessagePayload,
    ChatStreamResultEvent,
    ChatStreamStatusEvent,
    CompetitionBatchRequest,
    CompetitionBatchResponse,
)
from src.schemas.legal import LegalAnswerRequest, LegalAnswerResponse
from src.services.agents.legal_assistant import LegalAssistantAgent

router = APIRouter(prefix="/api/v1/legal", tags=["legal-assistant"])


@router.post("/answer", response_model=LegalAnswerResponse)
async def answer_question(
    request: LegalAnswerRequest,
    agent: LegalAssistantAgent = Depends(get_legal_assistant_agent),
) -> LegalAnswerResponse:
    """Trả lời một câu hỏi pháp lý đơn lẻ, không tự ghi short-memory."""

    return await agent.answer(request)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: LegalAssistantAgent = Depends(get_legal_assistant_agent),
) -> ChatResponse:
    """Chat wrapper dùng ``session_id`` làm LangGraph thread_id."""

    answer = await agent.answer(
        LegalAnswerRequest(
            session_id=request.session_id,
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


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    agent: LegalAssistantAgent = Depends(get_legal_assistant_agent),
) -> StreamingResponse:
    """Stream trạng thái xử lý và trả kết quả chat cuối cùng bằng SSE."""

    async def events():
        def pack(stream_event) -> str:
            event = stream_event.event
            data = stream_event.data.model_dump(mode="json")
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        try:
            yield pack(ChatStreamStatusEvent(data=ChatStreamMessagePayload(message="Chuẩn bị hội thoại")))
            yield pack(ChatStreamStatusEvent(data=ChatStreamMessagePayload(message="Gọi legal agent")))
            answer = await agent.answer(
                LegalAnswerRequest(
                    session_id=request.session_id,
                    question=request.message,
                    databases=request.databases,
                    top_k=request.top_k,
                    include_debug=True,
                )
            )
            yield pack(ChatStreamStatusEvent(data=ChatStreamMessagePayload(message="Đã nhận kết quả")))
            response = ChatResponse(
                session_id=request.session_id,
                message=request.message,
                answer=answer,
                tool_calls=answer.debug.get("tool_calls", []),
            )
            yield pack(ChatStreamResultEvent(data=response))
            yield pack(ChatStreamDoneEvent(data=ChatStreamMessagePayload(message="Hoàn tất")))
        except Exception as exc:  # pragma: no cover - trả lỗi runtime cho UI
            yield pack(ChatStreamErrorEvent(data=ChatStreamMessagePayload(message=str(exc))))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/batch", response_model=CompetitionBatchResponse)
async def answer_batch(
    request: CompetitionBatchRequest,
    agent: LegalAssistantAgent = Depends(get_legal_assistant_agent),
) -> CompetitionBatchResponse:
    """Trả lời nhiều câu hỏi, phù hợp khi chạy tập test của cuộc thi."""

    results = [await agent.answer(item) for item in request.items]
    return CompetitionBatchResponse(results=results)
