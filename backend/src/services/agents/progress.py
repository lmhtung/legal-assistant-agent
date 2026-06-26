"""Progress callback theo từng async request của agent."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from typing import Any, Awaitable, Callable

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]
_progress_callback: ContextVar[ProgressCallback | None] = ContextVar("agent_progress_callback", default=None)


def set_progress_callback(callback: ProgressCallback | None) -> Token:
    """Gắn callback vào context hiện tại, không chia sẻ giữa các request."""

    return _progress_callback.set(callback)


def reset_progress_callback(token: Token) -> None:
    """Khôi phục callback trước đó sau khi request kết thúc."""

    _progress_callback.reset(token)


async def emit_progress(
    stage: str,
    status: str,
    message: str,
    *,
    elapsed_ms: int | None = None,
    detail: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Phát một progress event nếu request hiện tại có đăng ký callback."""

    callback = _progress_callback.get()
    if callback is None:
        return
    await callback(
        {
            "stage": stage,
            "status": status,
            "message": message,
            "elapsed_ms": elapsed_ms,
            "detail": detail,
            "metadata": metadata or {},
        }
    )
    await asyncio.sleep(0)
