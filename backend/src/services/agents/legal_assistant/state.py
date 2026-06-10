from __future__ import annotations

from src.services.agents.base.state import AgentState


class LegalAssistantState(AgentState, total=False):
    """State passed between LangGraph nodes for the legal assistant."""
