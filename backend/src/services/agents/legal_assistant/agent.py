from __future__ import annotations

from src.schemas.legal import LegalAnswerRequest, LegalAnswerResponse, RetrievalQuery
from src.services.agents.base.context import AgentContext
from src.services.agents.legal_assistant.prompt import build_grounded_answer_prompt
from src.services.agents.legal_assistant.state import LegalAssistantState
from src.services.vector_store import VectorStoreRegistry, vector_store_registry


class LegalAssistantAgent:
    def __init__(self, registry: VectorStoreRegistry = vector_store_registry, llm=None) -> None:
        self.registry = registry
        self.llm = llm
        self.graph = self._compile_graph()

    async def answer(self, request: LegalAnswerRequest) -> LegalAnswerResponse:
        context = AgentContext(databases=request.databases, top_k=request.top_k, competition_mode=True)
        state: LegalAssistantState = {
            "question_id": request.id,
            "question": request.question,
            "context": context,
            "tool_calls": [],
            "debug": {},
        }
        if self.graph is not None:
            state = await self.graph.ainvoke(state)
        else:
            state = await self._run_without_graph(state)
        return self._to_response(state, include_debug=request.include_debug)

    def _compile_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            return None

        graph = StateGraph(LegalAssistantState)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("generate_answer", self._generate_answer_node)
        graph.add_node("format_submission", self._format_submission_node)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "generate_answer")
        graph.add_edge("generate_answer", "format_submission")
        graph.add_edge("format_submission", END)
        return graph.compile()

    async def _run_without_graph(self, state: LegalAssistantState) -> LegalAssistantState:
        state = await self._retrieve_node(state)
        state = await self._generate_answer_node(state)
        return await self._format_submission_node(state)

    async def _retrieve_node(self, state: LegalAssistantState) -> LegalAssistantState:
        context = state.get("context") or AgentContext()
        query = RetrievalQuery(
            question=state["question"],
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
            state.setdefault("debug", {})["prompt"] = prompt
            return state
        try:
            state["answer"] = await self.llm.ainvoke(prompt)
        except Exception as exc:  # pragma: no cover - network/model fallback
            state["answer"] = self._fallback_answer(state["question"], articles)
            state.setdefault("debug", {})["llm_error"] = str(exc)
        return state

    async def _format_submission_node(self, state: LegalAssistantState) -> LegalAssistantState:
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

    def _fallback_answer(self, question: str, articles) -> str:
        lead = f"Dựa trên các căn cứ đã truy hồi cho câu hỏi: {question}"
        bullets = []
        for article in articles[:5]:
            excerpt = " ".join(article.content.split())[:450]
            bullets.append(f"- {article.article} của {article.law_name}: {excerpt}")
        warning = "Thông tin trên chỉ mang tính tham khảo; với vụ việc cụ thể nên tham vấn chuyên gia pháp lý."
        return "\n".join([lead, *bullets, warning])

    def _to_response(self, state: LegalAssistantState, include_debug: bool = False) -> LegalAnswerResponse:
        return LegalAnswerResponse(
            id=state.get("question_id"),
            question=state["question"],
            answer=state.get("answer", ""),
            relevant_docs=state.get("relevant_docs", []),
            relevant_articles=state.get("relevant_articles", []),
            selected_articles=state.get("selected_articles", []),
            debug=state.get("debug", {}) if include_debug else {},
        )
