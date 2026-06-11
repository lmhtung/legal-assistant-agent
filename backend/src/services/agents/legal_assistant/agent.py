"""LangGraph legal assistant agent.

The agent runs four conceptual steps:
1. rewrite the query or generate a hypothetical answer for retrieval,
2. retrieve grounded legal records,
3. generate a grounded Vietnamese answer,
4. format references for competition output.
"""
from __future__ import annotations

from src.config import get_settings
from src.schemas.legal import LegalAnswerRequest, LegalAnswerResponse, RetrievalQuery
from src.services.agents.base.client import BaseAgent
from src.services.agents.base.context import AgentContext
from src.services.agents.legal_assistant.prompt import (
    build_grounded_answer_prompt,
    build_hypothetical_answer_prompt,
    build_query_rewrite_prompt,
)
from src.services.agents.legal_assistant.state import LegalAssistantState
from src.services.vector_store import VectorStoreRegistry, vector_store_registry


class LegalAssistantAgent(BaseAgent[LegalAnswerRequest, LegalAnswerResponse, LegalAssistantState]):
    """Single production agent used by this backend."""

    name = "legal-assistant"
    description = "Vietnamese legal retrieval and grounded QA agent"

    def __init__(self, registry: VectorStoreRegistry = vector_store_registry, llm=None) -> None:
        self.registry = registry
        self.llm = llm
        self.settings = get_settings()
        super().__init__()

    def build_initial_state(self, request: LegalAnswerRequest) -> LegalAssistantState:
        """Create the initial graph state from the public API request."""

        rewrite_enabled = self.settings.legal_assistant.query_rewrite.enabled
        context = AgentContext(
            databases=request.databases,
            top_k=request.top_k or self.settings.legal_assistant.vector_store.top_k,
            competition_mode=True,
            rewrite_query_enabled=rewrite_enabled,
        )
        return {
            "question_id": request.id,
            "question": request.question,
            "retrieval_question": request.question,
            "query_variants": [request.question],
            "context": context,
            "tool_calls": [],
            "debug": {},
        }

    def build_response(
        self,
        state: LegalAssistantState,
        request: LegalAnswerRequest,
    ) -> LegalAnswerResponse:
        """Convert final graph state into API response shape."""

        return self._to_response(state, include_debug=request.include_debug)

    def _compile_graph(self):
        """Compile LangGraph if installed; otherwise fallback mode is used."""

        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            return None

        graph = StateGraph(LegalAssistantState)
        graph.add_node("rewrite_query", self._rewrite_query_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("generate_answer", self._generate_answer_node)
        graph.add_node("format_submission", self._format_submission_node)
        graph.set_entry_point("rewrite_query")
        graph.add_edge("rewrite_query", "retrieve")
        graph.add_edge("retrieve", "generate_answer")
        graph.add_edge("generate_answer", "format_submission")
        graph.add_edge("format_submission", END)
        return graph.compile()

    async def run_without_graph(self, state: LegalAssistantState) -> LegalAssistantState:
        """Run the same node order without LangGraph."""

        state = await self._rewrite_query_node(state)
        state = await self._retrieve_node(state)
        state = await self._generate_answer_node(state)
        return await self._format_submission_node(state)

    async def _rewrite_query_node(self, state: LegalAssistantState) -> LegalAssistantState:
        """Prepare the text that retrieval will embed/search."""

        context = state.get("context") or AgentContext()
        question = state["question"]
        if not context.rewrite_query_enabled:
            state["retrieval_question"] = question
            state["query_variants"] = [question]
            state.setdefault("debug", {})["query_rewrite"] = "disabled"
            return state

        mode = self.settings.legal_assistant.retrieval.query_mode
        retrieval_text = question
        tool_name = mode
        if self.llm is not None and self.settings.legal_assistant.query_rewrite.use_llm:
            prompt = (
                build_hypothetical_answer_prompt(question)
                if mode == "hypothetical_answer"
                else build_query_rewrite_prompt(question)
            )
            try:
                candidate = (await self.llm.ainvoke(prompt)).strip()
                if candidate:
                    retrieval_text = candidate.splitlines()[0].strip(" -\t") or question
            except Exception as exc:  # pragma: no cover - network/model fallback
                state.setdefault("debug", {})[f"{mode}_error"] = str(exc)

        if mode == "hypothetical_answer":
            state["hypothetical_answer"] = retrieval_text
        else:
            state["rewritten_question"] = retrieval_text
        state["retrieval_question"] = retrieval_text
        state["query_variants"] = self._build_query_variants(question, retrieval_text)
        state.setdefault("tool_calls", []).append(
            {
                "name": tool_name,
                "args": {"question": question, "enabled": True},
                "result": retrieval_text,
            }
        )
        return state

    async def _retrieve_node(self, state: LegalAssistantState) -> LegalAssistantState:
        """Call the registered vector stores and keep selected articles in state."""

        context = state.get("context") or AgentContext()
        query = RetrievalQuery(
            question=state.get("retrieval_question") or state["question"],
            original_question=state["question"],
            query_variants=state.get("query_variants", [state["question"]]),
            databases=context.databases,
            top_k=context.top_k,
        )
        candidates = self.registry.search(query)
        state["retrieved"] = candidates
        state["selected_articles"] = [candidate.article for candidate in candidates]
        state.setdefault("tool_calls", []).append(
            {
                "name": "search_legal_articles",
                "args": query.model_dump(mode="json"),
                "num_results": len(candidates),
            }
        )
        return state

    async def _generate_answer_node(self, state: LegalAssistantState) -> LegalAssistantState:
        """Generate the final answer from retrieved legal records."""

        articles = state.get("selected_articles", [])
        if not articles:
            state["answer"] = (
                "Chưa tìm thấy điều luật phù hợp trong kho dữ liệu đã đăng ký. "
                "Tôi không nên đưa ra kết luận pháp lý khi không có căn cứ rõ ràng."
            )
            return state
        prompt = build_grounded_answer_prompt(state["question"], articles)
        if self.llm is None:
            state["answer"] = self._fallback_answer(state["question"], articles)
            state.setdefault("debug", {})["answer_prompt"] = prompt
            return state
        try:
            state["answer"] = await self.llm.ainvoke(prompt)
        except Exception as exc:  # pragma: no cover - network/model fallback
            state["answer"] = self._fallback_answer(state["question"], articles)
            state.setdefault("debug", {})["llm_error"] = str(exc)
        return state

    async def _format_submission_node(self, state: LegalAssistantState) -> LegalAssistantState:
        """Build competition-compatible document/article reference lists."""

        articles = state.get("selected_articles", [])
        docs: list[str] = []
        article_refs: list[str] = []
        for article in articles:
            if article.doc_ref not in docs:
                docs.append(article.doc_ref)
            if article.article_ref not in article_refs:
                article_refs.append(article.article_ref)
        state["relevant_docs"] = docs
        state["relevant_articles"] = article_refs
        return state

    def _build_query_variants(self, question: str, rewritten: str) -> list[str]:
        """Keep original and generated retrieval text for lexical search."""

        variants: list[str] = []
        for item in [rewritten, question]:
            if item and item not in variants:
                variants.append(item)
        return variants[: self.settings.legal_assistant.query_rewrite.max_variants]

    def _fallback_answer(self, question: str, articles) -> str:
        """Deterministic answer used when no LLM is available."""

        lead = f"Dựa trên các căn cứ đã truy hồi cho câu hỏi: {question}"
        bullets = []
        for article in articles[:5]:
            excerpt = " ".join(article.content.split())[:450]
            bullets.append(f"- {article.article} của {article.law_name}: {excerpt}")
        warning = "Thông tin trên chỉ mang tính tham khảo; với vụ việc cụ thể nên tham vấn chuyên gia pháp lý."
        return "\n".join([lead, *bullets, warning])

    def _to_response(self, state: LegalAssistantState, include_debug: bool = False) -> LegalAnswerResponse:
        """Create the public response object and optional debug payload."""

        debug = state.get("debug", {}).copy() if include_debug else {}
        if include_debug:
            debug.update(
                {
                    "tool_calls": state.get("tool_calls", []),
                    "rewritten_question": state.get("rewritten_question"),
                    "hypothetical_answer": state.get("hypothetical_answer"),
                    "retrieval_question": state.get("retrieval_question"),
                    "query_variants": state.get("query_variants", []),
                }
            )
        return LegalAnswerResponse(
            id=state.get("question_id"),
            question=state["question"],
            answer=state.get("answer", ""),
            relevant_docs=state.get("relevant_docs", []),
            relevant_articles=state.get("relevant_articles", []),
            selected_articles=state.get("selected_articles", []),
            debug=debug,
        )
