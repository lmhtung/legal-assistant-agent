"""OpenAI-compatible chat client wrapper."""
from __future__ import annotations

from src.config import settings


class LLMClient:
    """Thin wrapper around LangChain's ChatOpenAI client."""

    def __init__(self):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("Install langchain-openai to use the LLM endpoint") from exc

        self.chat = ChatOpenAI(
            model=settings.llm.model_name,
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        )

    async def ainvoke(self, prompt: str) -> str:
        """Call the chat model and return plain text content."""

        response = await self.chat.ainvoke(prompt)
        return response.content
