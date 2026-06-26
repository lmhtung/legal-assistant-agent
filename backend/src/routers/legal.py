"""Các HTTP endpoint phục vụ hỏi đáp pháp lý."""
from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from time import perf_counter

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
    """Stream từng stage, heartbeat và kết quả chat cuối cùng bằng SSE."""

    async def events():
        def pack(stream_event) -> str:
            event = stream_event.event
            data = stream_event.data.model_dump(mode="json")
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        started = perf_counter()
        stage_started = started
        current_stage = "request"
        current_message = "Đang chuẩn bị request"
        current_status = "started"
        progress_queue: asyncio.Queue[dict] = asyncio.Queue()

        async def on_progress(payload: dict) -> None:
            await progress_queue.put(payload)
            # Nhường event loop để StreamingResponse gửi event trước khi node
            # tiếp tục một tác vụ nặng.
            await asyncio.sleep(0)

        answer_request = LegalAnswerRequest(
            session_id=request.session_id,
            question=request.message,
            databases=request.databases,
            top_k=request.top_k,
            include_debug=True,
        )
        task = asyncio.create_task(agent.answer_with_progress(answer_request, on_progress))
        try:
            yield pack(
                ChatStreamStatusEvent(
                    data=ChatStreamMessagePayload(
                        message="Đã nhận request chat",
                        stage="request",
                        status="started",
                        elapsed_ms=0,
                        detail=f"Session: {request.session_id or 'tạm thời'}; {len(request.message)} ký tự.",
                    )
                )
            )

            while not task.done() or not progress_queue.empty():
                try:
                    payload = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if current_status in {"completed", "warning", "error"}:
                        current_stage = "response"
                        current_message = "Đang hoàn thiện response"
                        current_status = "running"
                        stage_started = perf_counter()
                    elapsed_ms = round((perf_counter() - stage_started) * 1000)
                    yield pack(
                        ChatStreamStatusEvent(
                            data=ChatStreamMessagePayload(
                                message=f"{current_message} ({elapsed_ms / 1000:.1f}s)",
                                stage=current_stage,
                                status="running",
                                elapsed_ms=elapsed_ms,
                                detail="Backend vẫn đang xử lý stage này; kết nối SSE còn hoạt động.",
                            )
                        )
                    )
                    continue

                current_stage = str(payload.get("stage") or current_stage)
                current_message = str(payload.get("message") or current_message)
                current_status = str(payload.get("status") or current_status)
                if payload.get("status") == "started":
                    stage_started = perf_counter()
                elif payload.get("elapsed_ms") is None:
                    payload["elapsed_ms"] = round((perf_counter() - stage_started) * 1000)
                yield pack(ChatStreamStatusEvent(data=ChatStreamMessagePayload.model_validate(payload)))

            answer = await task
            response = ChatResponse(
                session_id=request.session_id,
                message=request.message,
                answer=answer,
                tool_calls=answer.debug.get("tool_calls", []),
            )
            yield pack(ChatStreamResultEvent(data=response))
            yield pack(
                ChatStreamDoneEvent(
                    data=ChatStreamMessagePayload(
                        message="Hoàn tất request",
                        stage="request",
                        status="completed",
                        elapsed_ms=round((perf_counter() - started) * 1000),
                    )
                )
            )
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception as exc:  # pragma: no cover - trả lỗi runtime cho UI
            yield pack(
                ChatStreamErrorEvent(
                    data=ChatStreamMessagePayload(
                        message=f"Lỗi tại stage {current_stage}: {exc}",
                        stage=current_stage,
                        status="error",
                        elapsed_ms=round((perf_counter() - stage_started) * 1000),
                        detail=exc.__class__.__name__,
                        metadata={"request_elapsed_ms": round((perf_counter() - started) * 1000)},
                    )
                )
            )
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

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
