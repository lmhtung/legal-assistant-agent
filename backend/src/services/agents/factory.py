"""Agent factory helpers."""
from __future__ import annotations

from src.services.agents.legal_assistant import LegalAssistantAgent
from src.services.vector_store import VectorStoreRegistry, vector_store_registry


def create_legal_assistant_agent(
    registry: VectorStoreRegistry = vector_store_registry,
    llm=None,
) -> LegalAssistantAgent:
    """Create the single legal assistant used by the application."""

    return LegalAssistantAgent(registry=registry, llm=llm)
