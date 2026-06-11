"""Simple in-process registry for named agents."""
from __future__ import annotations

from typing import Any


class AgentRegistry:
    """Map agent names to instantiated agent objects."""

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}

    def register(self, name: str, agent: Any) -> None:
        """Register or replace an agent by name."""

        self._agents[name] = agent

    def get(self, name: str) -> Any:
        """Return an agent by name, failing loudly if missing."""

        if name not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        """List registered agent names."""

        return sorted(self._agents)


agent_registry = AgentRegistry()
