"""Các node xử lý của legal assistant workflow."""
from __future__ import annotations

from typing import Any

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
except ImportError:  # pragma: no cover - fallback khi chưa cài LangChain
    AIMessage = None
    HumanMessage = None
    SystemMessage = None

from src.schemas.legal import LegalArticle, RetrievalQuery
from src.services.agents.base.context import AgentContext
from src.services.agents.legal_assistant.prompt import (
    SYSTEM_PROMPT,
    build_hyde_prompt,
    build_legal_context_message,
    build_rewrite_query_prompt,
)
from src.services.agents.legal_assistant.state import LegalAssistantState


async def prepare_retrieval_query_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Chọn text đem đi embedding/search theo mode none, rewrite hoặc hyde."""

    context = state.get("context") or AgentContext()
    question = state["question"]
    mode = runtime.settings.legal_assistant.retrieval.query_mode
    state["retrieval_mode"] = mode

    if not context.rewrite_query_enabled or mode == "none":
        return _set_retrieval_text(runtime, state, question, mode="none", provider="config")

    retrieval_text = question
    provider = "fallback"
    if runtime.llm is not None and runtime.settings.legal_assistant.query_rewrite.use_llm:
        provider = "llm"
        prompt = _query_prompt(question, mode)
        try:
            candidate = (await runtime.llm.ainvoke(prompt)).strip()
            if candidate.upper() == "SKIP":
                return _skip_retrieval(state, mode)
            if candidate:
                retrieval_text = _clean_retrieval_text(candidate, mode) or question
        except Exception as exc:  # pragma: no cover - fallback khi LLM endpoint lỗi
            state.setdefault("debug", {})["prepare_retrieval_error"] = str(exc)

    return _set_retrieval_text(runtime, state, retrieval_text, mode=mode, provider=provider)


async def retrieve_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Search qua MCP nếu bật; nếu không dùng local fallback."""

    if state.get("skip_retrieval"):
        state["retrieved"] = []
        state["selected_articles"] = []
        state.setdefault("tool_calls", []).append(
            {"name": "skip_retrieval", "provider": "backend", "num_results": 0}
        )
        return state

    context = state.get("context") or AgentContext()
    query = RetrievalQuery(
        question=state.get("retrieval_question") or state["question"],
        original_question=state["question"],
        query_variants=state.get("query_variants", [state["question"]]),
        databases=context.databases,
        top_k=context.top_k,
    )

    candidates = await _search_with_mcp(runtime, query, state)
    if candidates is None:
        candidates = _search_local(runtime, query, context, state)

    state["retrieved"] = candidates
    state["selected_articles"] = [candidate.article for candidate in candidates]
    return state


async def generate_answer_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Sinh câu trả lời từ messages hiện có và legal context nếu đã retrieval."""

    articles = None if state.get("skip_retrieval") else state.get("selected_articles", [])
    state["answer"] = await _chat_answer(runtime, state, articles)
    return state


async def format_submission_node(_: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Tạo danh sách nguồn theo format bài thi và ghi AIMessage vào memory."""

    if state.get("skip_retrieval"):
        state["relevant_docs"] = []
        state["relevant_articles"] = []
        _append_ai_message(state)
        return state

    docs: list[str] = []
    article_refs: list[str] = []
    for article in state.get("selected_articles", []):
        _append_once(article.doc_ref, docs)
        _append_once(article.article_ref, article_refs)
        for related_ref in sorted(article.extra):
            doc_ref, article_ref = normalize_related_ref(related_ref)
            _append_once(doc_ref, docs)
            _append_once(article_ref, article_refs)

    state["relevant_docs"] = docs
    state["relevant_articles"] = article_refs
    _append_ai_message(state)
    return state


def _query_prompt(question: str, mode: str) -> str:
    if mode == "rewrite":
        return build_rewrite_query_prompt(question)
    return build_hyde_prompt(question)


def _skip_retrieval(state: LegalAssistantState, mode: str) -> LegalAssistantState:
    state["skip_retrieval"] = True
    state["retrieval_question"] = state["question"]
    state["query_variants"] = [state["question"]]
    state.setdefault("debug", {})["retrieval_query"] = "skip"
    state.setdefault("tool_calls", []).append(
        {
            "name": "prepare_retrieval_query",
            "provider": "llm",
            "args": {"question": state["question"], "mode": mode},
            "result": "SKIP",
        }
    )
    return state


def _set_retrieval_text(
    runtime: Any,
    state: LegalAssistantState,
    retrieval_text: str,
    mode: str,
    provider: str,
) -> LegalAssistantState:
    question = state["question"]
    state["retrieval_mode"] = mode
    state["retrieval_question"] = retrieval_text
    if mode == "rewrite":
        state["rewritten_question"] = retrieval_text
    elif mode == "hyde":
        state["hypothetical_answer"] = retrieval_text
    state["query_variants"] = _build_query_variants(runtime, question, retrieval_text)
    state.setdefault("tool_calls", []).append(
        {
            "name": "prepare_retrieval_query",
            "provider": provider,
            "args": {"question": question, "mode": mode},
            "result": retrieval_text,
        }
    )
    return state


def _clean_retrieval_text(text: str, mode: str) -> str:
    if mode == "rewrite":
        return text.splitlines()[0].strip(" -\t")
    return text.strip()


def _build_query_variants(runtime: Any, question: str, retrieval_text: str) -> list[str]:
    variants: list[str] = []
    for item in [retrieval_text, question]:
        if item and item not in variants:
            variants.append(item)
    return variants[: runtime.settings.legal_assistant.query_rewrite.max_variants]


async def _search_with_mcp(runtime: Any, query: RetrievalQuery, state: LegalAssistantState):
    if runtime.mcp_client is None or not runtime.settings.mcp_retrieval.enabled:
        return None
    try:
        candidates = await runtime.mcp_client.search_legal_articles(query)
        related = await _search_relevant_with_mcp(runtime, candidates, query)
        state.setdefault("tool_calls", []).append(
            {
                "name": runtime.mcp_client.search_tool_name,
                "provider": "mcp",
                "args": query.model_dump(mode="json"),
                "num_results": len(candidates),
            }
        )
        if related:
            state.setdefault("tool_calls", []).append(
                {
                    "name": runtime.mcp_client.relevant_tool_name,
                    "provider": "mcp",
                    "num_results": len(related),
                }
            )
        return _merge_candidates(candidates, related)
    except Exception as exc:  # pragma: no cover - MCP là service ngoài
        state.setdefault("debug", {})["mcp_retrieval_error"] = str(exc)
        if runtime.settings.mcp_retrieval.fallback_to_local:
            return None
        raise


async def _search_relevant_with_mcp(runtime: Any, candidates: list, query: RetrievalQuery):
    if not runtime.settings.mcp_retrieval.fetch_related:
        return []
    refs = sorted({ref for candidate in candidates for ref in candidate.article.extra})
    if not refs:
        return []
    return await runtime.mcp_client.search_relevant(
        extra_refs=refs,
        databases=query.databases,
        top_k=runtime.settings.mcp_retrieval.related_top_k,
    )


def _search_local(runtime: Any, query: RetrievalQuery, context: AgentContext, state: LegalAssistantState):
    try:
        for database in context.databases:
            if not runtime.registry.has(database):
                runtime.registry.register(database, runtime.store_factory.create(database))
        candidates = runtime.registry.search(query)
    except Exception as exc:  # local fallback có thể thiếu dependency hoặc chưa có index
        candidates = []
        state.setdefault("debug", {})["local_retrieval_error"] = str(exc)

    state.setdefault("tool_calls", []).append(
        {
            "name": "search_legal_articles",
            "provider": "backend-local",
            "args": query.model_dump(mode="json"),
            "num_results": len(candidates),
        }
    )
    return candidates


def _merge_candidates(primary: list, related: list) -> list:
    merged = []
    seen: set[str] = set()
    for candidate in [*primary, *related]:
        article_id = candidate.article.article_id
        if article_id in seen:
            continue
        seen.add(article_id)
        merged.append(candidate)
    return merged


async def _chat_answer(runtime: Any, state: LegalAssistantState, articles: list[LegalArticle] | None) -> str:
    messages = _build_llm_messages(state, articles)
    if runtime.llm is None:
        return _fallback_answer(state["question"], articles)
    try:
        if isinstance(messages, str):
            return await runtime.llm.ainvoke(messages)
        if hasattr(runtime.llm, "ainvoke_messages"):
            return await runtime.llm.ainvoke_messages(messages)
        return await runtime.llm.ainvoke(_messages_to_prompt(messages))
    except Exception as exc:  # pragma: no cover - fallback khi LLM endpoint lỗi
        state.setdefault("debug", {})["llm_error"] = str(exc)
        return _fallback_answer(state["question"], articles)


def _build_llm_messages(state: LegalAssistantState, articles: list[LegalArticle] | None) -> list[Any] | str:
    history_messages = list(state.get("messages", []))
    if SystemMessage is None or HumanMessage is None:
        chunks = [SYSTEM_PROMPT]
        chunks.extend(getattr(message, "content", str(message)) for message in history_messages)
        if articles is not None:
            chunks.append(build_legal_context_message(articles))
        return "\n\n".join(str(chunk) for chunk in chunks if chunk)

    messages: list[Any] = [SystemMessage(content=SYSTEM_PROMPT), *history_messages]
    if articles is not None:
        messages.append(HumanMessage(content=build_legal_context_message(articles)))
    return messages


def _messages_to_prompt(messages: list[Any]) -> str:
    lines = []
    for message in messages:
        role = getattr(message, "type", message.__class__.__name__)
        content = getattr(message, "content", str(message))
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _fallback_answer(question: str, articles: list[LegalArticle] | None) -> str:
    if articles is None:
        return "Mình là MscAI. Hiện chưa gọi được mô hình ngôn ngữ để xử lý hội thoại tự nhiên."
    if not articles:
        return "Mình chưa tìm thấy căn cứ trong kho dữ liệu đã đăng ký, nên chưa thể kết luận nội dung pháp lý cụ thể."

    lead = f"Dựa trên các căn cứ đã truy hồi cho câu hỏi: {question}"
    bullets = []
    for article in articles[:5]:
        excerpt = " ".join(article.content.split())[:450]
        bullets.append(f"- {article.article} của {article.law_name}: {excerpt}")
    warning = "Thông tin trên chỉ mang tính tham khảo; với vụ việc cụ thể nên tham vấn chuyên gia pháp lý."
    return "\n".join([lead, *bullets, warning])


def _append_ai_message(state: LegalAssistantState) -> None:
    answer = state.get("answer")
    if not answer or AIMessage is None:
        return
    messages = state.setdefault("messages", [])
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].content == answer:
        return
    messages.append(AIMessage(content=answer))


def _append_once(value: str | None, values: list[str]) -> None:
    if value and value not in values:
        values.append(value)


def normalize_related_ref(reference: str) -> tuple[str | None, str | None]:
    parts = [part.strip() for part in reference.split("|") if part.strip()]
    if len(parts) == 4:
        _, law_id, law_name, article = parts
        return f"{law_id}|{law_name}", f"{law_id}|{law_name}|{article}"
    if len(parts) == 3:
        law_id, law_name, article = parts
        return f"{law_id}|{law_name}", f"{law_id}|{law_name}|{article}"
    return None, None
