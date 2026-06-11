"""Registry in-process cho các agent theo tên."""
from __future__ import annotations

from typing import Any


class AgentRegistry:
    """Map tên agent sang object agent đã khởi tạo."""

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}

    def register(self, name: str, agent: Any) -> None:
        """Đăng ký hoặc thay thế agent theo tên."""

        self._agents[name] = agent

    def get(self, name: str) -> Any:
        """Lấy agent theo tên, báo lỗi rõ nếu chưa đăng ký."""

        if name not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        """Liệt kê các agent đang có trong process."""

        return sorted(self._agents)


agent_registry = AgentRegistry()
