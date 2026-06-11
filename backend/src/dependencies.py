"""FastAPI dependency providers."""
from __future__ import annotations

from functools import lru_cache

from src.config import get_settings
from src.services.agents.legal_assistant import LegalAssistantAgent
from src.services.dataset import DatasetService
from src.services.llm.client import LLMClient


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Create one LLM client for the process."""

    return LLMClient()


@lru_cache(maxsize=1)
def get_legal_assistant_agent() -> LegalAssistantAgent:
    """Create the legal assistant with an LLM when rewrite/HyDE is enabled."""

    settings = get_settings()
    llm = get_llm_client() if settings.legal_assistant.query_rewrite.use_llm else None
    return LegalAssistantAgent(llm=llm)


@lru_cache(maxsize=1)
def get_dataset_service() -> DatasetService:
    """Create the structured dataset import service."""

    return DatasetService()
