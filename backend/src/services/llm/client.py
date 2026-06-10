from langchain_openai import ChatOpenAI
from src.config import settings


class LLMClient:
    def __init__(self):
        self.chat = ChatOpenAI(
            model=settings.llm.model_name,
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        )

    async def ainvoke(self, prompt: str) -> str:
        response = await self.chat.ainvoke(prompt)
        return response.content