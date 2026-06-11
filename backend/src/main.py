"""Entry point FastAPI duy nhất của runtime agent.

File này chỉ đăng ký router hỏi đáp pháp lý và health check. Luồng import/build
data không nằm ở đây để tránh trộn data pipeline với prompt/answer pipeline.
"""
from __future__ import annotations

from fastapi import FastAPI

from src.config import get_settings
from src.routers import health_router, legal_router


def create_app() -> FastAPI:
    """Tạo FastAPI app cho agent service."""

    settings = get_settings()
    app = FastAPI(title="Vietnamese Legal Assistant Agent", version="0.1.0")
    # Lưu settings vào app.state để các middleware/tooling sau này có thể đọc
    # mà không cần parse lại YAML.
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(legal_router)
    return app


app = create_app()
