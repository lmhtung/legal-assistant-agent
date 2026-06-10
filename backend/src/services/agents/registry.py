from __future__ import annotations

from typing import Any


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}

    def register(self, name: str, agent: Any) -> None:
        self._agents[name] = agent

    def get(self, name: str) -> Any:
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        return sorted(self._agents)


agent_registry = AgentRegistry()
