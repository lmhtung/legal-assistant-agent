"""Legal assistant state specialization."""
from __future__ import annotations

from src.services.agents.base.state import AgentState


class LegalAssistantState(AgentState, total=False):
    """Alias-style extension point for legal-agent-specific state fields."""
