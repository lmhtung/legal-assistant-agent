"""Agent pháp lý chính viết bằng LangGraph/LangChain style.

Agent chạy bốn bước rõ ràng:
1. rewrite query hoặc sinh hypothetical answer để tối ưu retrieval;
2. search kho tri thức qua MCP hoặc fallback tool local;
3. tạo câu trả lời grounded từ các điều luật tìm được;
4. format nguồn theo yêu cầu bài thi, gồm cả mở rộng từ field ``extra``.
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
from src.services.vector_store import VectorStoreFactory, VectorStoreRegistry, vector_store_registry


class LegalAssistantAgent(BaseAgent[LegalAnswerRequest, LegalAnswerResponse, LegalAssistantState]):
    """Agent production duy nhất của backend hiện tại."""

    name = "legal-assistant"
    description = "Vietnamese legal retrieval and grounded QA agent"

    def __init__(self, registry: VectorStoreRegistry = vector_store_registry, llm=None, mcp_client=None) -> None:
        # registry giữ tool/vector store local để fallback khi MCP chưa bật hoặc lỗi.
        self.registry = registry
        self.llm = llm
        self.mcp_client = mcp_client
        self.settings = get_settings()
        self.store_factory = VectorStoreFactory(self.settings.legal_assistant.vector_store)
        super().__init__()

    def build_initial_state(self, request: LegalAnswerRequest) -> LegalAssistantState:
        """Tạo state ban đầu từ request public API."""

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
        """Đóng gói state cuối cùng thành response API."""

        return self._to_response(state, include_debug=request.include_debug)

    def _compile_graph(self):
        """Compile LangGraph nếu dependency đã được cài."""

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
        """Chạy đúng thứ tự node khi chưa dùng được LangGraph."""

        state = await self._rewrite_query_node(state)
        state = await self._retrieve_node(state)
        state = await self._generate_answer_node(state)
        return await self._format_submission_node(state)

    async def _rewrite_query_node(self, state: LegalAssistantState) -> LegalAssistantState:
        """Chuẩn bị text dùng cho retrieval."""

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
            except Exception as exc:  # pragma: no cover - fallback khi LLM endpoint lỗi
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
        """Search qua MCP nếu bật; nếu không thì dùng tool local trong backend."""

        context = state.get("context") or AgentContext()
        query = RetrievalQuery(
            question=state.get("retrieval_question") or state["question"],
            original_question=state["question"],
            query_variants=state.get("query_variants", [state["question"]]),
            databases=context.databases,
            top_k=context.top_k,
        )
        candidates = await self._search_with_mcp(query, state)
        if candidates is None:
            self._ensure_databases(context.databases)
            candidates = self.registry.search(query)
            state.setdefault("tool_calls", []).append(
                {
                    "name": "search_legal_articles",
                    "provider": "backend-local",
                    "args": query.model_dump(mode="json"),
                    "num_results": len(candidates),
                }
            )
        state["retrieved"] = candidates
        state["selected_articles"] = [candidate.article for candidate in candidates]
        return state

    async def _search_with_mcp(
        self,
        query: RetrievalQuery,
        state: LegalAssistantState,
    ):
        """Gọi MCP retrieval tools và trả ``None`` nếu cần fallback local."""

        if self.mcp_client is None or not self.settings.mcp_retrieval.enabled:
            return None
        try:
            candidates = await self.mcp_client.search_legal_articles(query)
            related = await self._search_relevant_with_mcp(candidates, query)
            merged = self._merge_candidates(candidates, related)
            state.setdefault("tool_calls", []).append(
                {
                    "name": self.mcp_client.search_tool_name,
                    "provider": "mcp",
                    "args": query.model_dump(mode="json"),
                    "num_results": len(candidates),
                }
            )
            if related:
                state.setdefault("tool_calls", []).append(
                    {
                        "name": self.mcp_client.relevant_tool_name,
                        "provider": "mcp",
                        "num_results": len(related),
                    }
                )
            return merged
        except Exception as exc:  # pragma: no cover - MCP là service ngoài
            state.setdefault("debug", {})["mcp_retrieval_error"] = str(exc)
            if self.settings.mcp_retrieval.fallback_to_local:
                return None
            raise

    async def _search_relevant_with_mcp(
        self,
        candidates: list,
        query: RetrievalQuery,
    ):
        """Dùng MCP tool ``search_relevant`` để lấy nội dung điều luật trong extra."""

        if not self.settings.mcp_retrieval.fetch_related:
            return []
        refs = sorted({ref for candidate in candidates for ref in candidate.article.extra})
        if not refs:
            return []
        return await self.mcp_client.search_relevant(
            extra_refs=refs,
            databases=query.databases,
            top_k=self.settings.mcp_retrieval.related_top_k,
        )

    def _merge_candidates(self, primary: list, related: list) -> list:
        """Gộp kết quả retrieval chính với điều luật liên quan, bỏ trùng article."""

        merged = []
        seen: set[str] = set()
        for candidate in [*primary, *related]:
            article_id = candidate.article.article_id
            if article_id in seen:
                continue
            seen.add(article_id)
            merged.append(candidate)
        return merged

    async def _generate_answer_node(self, state: LegalAssistantState) -> LegalAssistantState:
        """Sinh câu trả lời cuối cùng từ các điều luật đã retrieve."""

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
        except Exception as exc:  # pragma: no cover - fallback khi LLM endpoint lỗi
            state["answer"] = self._fallback_answer(state["question"], articles)
            state.setdefault("debug", {})["llm_error"] = str(exc)
        return state

    async def _format_submission_node(self, state: LegalAssistantState) -> LegalAssistantState:
        """Tạo danh sách nguồn theo format bài thi."""

        articles = state.get("selected_articles", [])
        docs: list[str] = []
        article_refs: list[str] = []
        for article in articles:
            self._append_reference(article.doc_ref, docs)
            self._append_reference(article.article_ref, article_refs)
            for related_ref in sorted(article.extra):
                doc_ref, article_ref = normalize_related_ref(related_ref)
                if doc_ref:
                    self._append_reference(doc_ref, docs)
                if article_ref:
                    self._append_reference(article_ref, article_refs)
        state["relevant_docs"] = docs
        state["relevant_articles"] = article_refs
        return state

    def _append_reference(self, value: str, values: list[str]) -> None:
        """Thêm reference một lần và giữ nguyên thứ tự ranking."""

        if value and value not in values:
            values.append(value)

    def _ensure_databases(self, databases: list[str]) -> None:
        """Mở store local theo database khi fallback cần dùng."""

        for database in databases:
            if not self.registry.has(database):
                self.registry.register(database, self.store_factory.create(database))

    def _build_query_variants(self, question: str, rewritten: str) -> list[str]:
        """Giữ bản rewrite và câu hỏi gốc để lexical search có thêm tín hiệu."""

        variants: list[str] = []
        for item in [rewritten, question]:
            if item and item not in variants:
                variants.append(item)
        return variants[: self.settings.legal_assistant.query_rewrite.max_variants]

    def _fallback_answer(self, question: str, articles) -> str:
        """Câu trả lời deterministic khi không có LLM hoặc LLM lỗi."""

        lead = f"Dựa trên các căn cứ đã truy hồi cho câu hỏi: {question}"
        bullets = []
        for article in articles[:5]:
            excerpt = " ".join(article.content.split())[:450]
            bullets.append(f"- {article.article} của {article.law_name}: {excerpt}")
        warning = "Thông tin trên chỉ mang tính tham khảo; với vụ việc cụ thể nên tham vấn chuyên gia pháp lý."
        return "\n".join([lead, *bullets, warning])

    def _to_response(self, state: LegalAssistantState, include_debug: bool = False) -> LegalAnswerResponse:
        """Tạo response public, chỉ kèm debug khi request yêu cầu."""

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


def normalize_related_ref(reference: str) -> tuple[str | None, str | None]:
    """Chuẩn hóa reference trong ``extra`` thành doc_ref và article_ref."""

    parts = [part.strip() for part in reference.split("|") if part.strip()]
    if len(parts) == 4:
        _, law_id, law_name, article = parts
        return f"{law_id}|{law_name}", f"{law_id}|{law_name}|{article}"
    if len(parts) == 3:
        law_id, law_name, article = parts
        return f"{law_id}|{law_name}", f"{law_id}|{law_name}|{article}"
    return None, None
