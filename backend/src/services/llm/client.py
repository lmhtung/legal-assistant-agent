"""Wrapper cho chat model OpenAI-compatible.

Local vLLM thường expose API tương thích OpenAI, nên dùng ``ChatOpenAI`` của
LangChain giúp agent gọi model local giống như gọi OpenAI API.
"""
from __future__ import annotations

from src.config import settings


class LLMClient:
    """Client mỏng bọc LangChain ``ChatOpenAI``."""

    def __init__(self):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - guard khi thiếu dependency
            raise RuntimeError("Install langchain-openai to use the LLM endpoint") from exc

        self.chat = ChatOpenAI(
            model=settings.llm.model_name,
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        )

    async def ainvoke(self, prompt: str) -> str:
        """Gọi chat model bất đồng bộ bằng plain prompt và trả về plain text."""

        response = await self.chat.ainvoke(prompt)
        return response.content

    async def ainvoke_messages(self, messages) -> str:
        """Gọi chat model bằng danh sách LangChain messages."""

        response = await self.chat.ainvoke(messages)
        return response.content
