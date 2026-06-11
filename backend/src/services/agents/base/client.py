"""Base agent contract shared by concrete agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from src.services.agents.base.state import AgentState

RequestT = TypeVar("RequestT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)
StateT = TypeVar("StateT", bound=AgentState)


class BaseAgent(ABC, Generic[RequestT, ResponseT, StateT]):
    """Common lifecycle for agent implementations.

    Concrete agents only define state construction, graph/fallback execution,
    and response construction. The public ``answer`` method stays consistent.
    """

    name: str = "base-agent"
    description: str = "Abstract base agent"

    def __init__(self) -> None:
        self.graph: Any | None = self._compile_graph()

    async def answer(self, request: RequestT) -> ResponseT:
        """Run the full request -> state -> graph -> response lifecycle."""

        state = self.build_initial_state(request)
        state = await self.run_graph(state)
        return self.build_response(state, request)

    async def run_graph(self, state: StateT) -> StateT:
        """Use LangGraph when available, otherwise use manual fallback."""

        if self.graph is not None:
            return await self.graph.ainvoke(state)
        return await self.run_without_graph(state)

    @abstractmethod
    def build_initial_state(self, request: RequestT) -> StateT:
        """Convert an external request into graph state."""

    @abstractmethod
    def build_response(self, state: StateT, request: RequestT) -> ResponseT:
        """Convert final graph state into an API response."""

    @abstractmethod
    async def run_without_graph(self, state: StateT) -> StateT:
        """Fallback execution path when LangGraph is not installed."""

    @abstractmethod
    def _compile_graph(self) -> Any | None:
        """Create and compile the LangGraph graph, or return None."""
