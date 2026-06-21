"""Các node xử lý của legal assistant workflow."""
from __future__ import annotations

import json
from typing import Any

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
except ImportError:  # pragma: no cover
    AIMessage = None
    HumanMessage = None
    SystemMessage = None

from src.schemas.legal import LegalArticle, RetrievalQuery
from src.services.agents.base.context import AgentContext
from src.services.agents.legal_assistant.prompt import (
    SYSTEM_PROMPT,
    build_category_prompt,
    build_hyde_prompt,
    build_intent_prompt,
    build_legal_context_message,
    build_rewrite_query_prompt,
)
from src.services.agents.legal_assistant.state import LegalAssistantState
from src.services.agents.legal_assistant.tools import search_legal_articles


async def analyze_intent_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 1: phân tích query pháp luật hay chat thường."""

    flag = "NEXT"
    if runtime.llm is not None:
        try:
            flag = (await runtime.llm.ainvoke(build_intent_prompt(state["question"]))).strip().upper()
        except Exception as exc:  # pragma: no cover
            state.setdefault("debug", {})["intent_error"] = str(exc)
    if flag != "SKIP":
        flag = "NEXT"
    state["legal_flag"] = flag
    state["skip_retrieval"] = flag == "SKIP"
    state.setdefault("tool_calls", []).append(
        {"name": "analyze_intent", "provider": "llm" if runtime.llm else "fallback", "result": flag}
    )
    return state


async def prepare_retrieval_query_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 2: none/rewrite/hyde để tạo text retrieval."""

    question = state["question"]
    mode = runtime.settings.legal_assistant.retrieval.query_mode
    rewrite_enabled = runtime.settings.legal_assistant.query_rewrite.enabled
    if not rewrite_enabled and mode in {"rewrite", "hyde"}:
        mode = "none"
    state["retrieval_mode"] = mode

    if state.get("skip_retrieval") or mode == "none":
        return _set_retrieval_text(runtime, state, question, mode="none", provider="config")

    retrieval_text = question
    provider = "fallback"
    if runtime.llm is not None and runtime.settings.legal_assistant.query_rewrite.use_llm:
        provider = "llm"
        prompt = build_rewrite_query_prompt(question) if mode == "rewrite" else build_hyde_prompt(question)
        try:
            candidate = (await runtime.llm.ainvoke(prompt)).strip()
            retrieval_text = _clean_retrieval_text(candidate, mode) or question
        except Exception as exc:  # pragma: no cover
            state.setdefault("debug", {})["prepare_retrieval_error"] = str(exc)

    return _set_retrieval_text(runtime, state, retrieval_text, mode=mode, provider=provider)


async def classify_categories_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 3 non-HyDE: phân tích query thuộc category luật nào."""

    if state.get("skip_retrieval"):
        return state

    settings = runtime.settings.legal_assistant.categories
    mode = state.get("retrieval_mode")
    if mode == "hyde":
        categories = settings.available or state.get("categories") or settings.default
        state["categories"] = categories
        state["per_category"] = False
        state["retrieval_top_k"] = settings.hyde_top_k
        return state

    query = state.get("retrieval_question") or state["question"]
    categories = state.get("categories") or settings.default
    if settings.available and runtime.llm is not None:
        try:
            raw = await runtime.llm.ainvoke(build_category_prompt(query, settings.available))
            categories = _parse_categories(raw, settings.available) or categories
        except Exception as exc:  # pragma: no cover
            state.setdefault("debug", {})["category_error"] = str(exc)

    state["categories"] = categories
    state["per_category"] = True
    state["retrieval_top_k"] = (
        settings.top_k_when_le_2_categories if len(categories) <= 2 else settings.top_k_when_many_categories
    )
    state.setdefault("tool_calls", []).append(
        {"name": "classify_categories", "provider": "llm" if settings.available and runtime.llm else "config", "result": categories}
    )
    return state


async def retrieve_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 4: embedding/search theo category đã chọn."""

    if state.get("skip_retrieval"):
        state["retrieved"] = []
        state["selected_articles"] = []
        state.setdefault("tool_calls", []).append({"name": "skip_retrieval", "provider": "backend", "num_results": 0})
        return state

    query = RetrievalQuery(
        question=state.get("retrieval_question") or state["question"],
        original_question=state["question"],
        query_variants=state.get("query_variants", [state["question"]]),
        categories=state.get("categories") or ["default"],
        top_k=state.get("retrieval_top_k") or 3,
        per_category=state.get("per_category", False),
    )
    try:
        candidates = search_legal_articles(query, runtime.registry, runtime.store_factory)
    except Exception as exc:
        candidates = []
        state.setdefault("debug", {})["local_retrieval_error"] = str(exc)

    state.setdefault("tool_calls", []).append(
        {
            "name": "search_legal_articles",
            "provider": "backend",
            "args": query.model_dump(mode="json"),
            "num_results": len(candidates),
        }
    )
    state["retrieved"] = candidates
    state["selected_articles"] = [candidate.article for candidate in candidates]
    return state


async def generate_answer_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 5: tổng hợp điều luật tìm được và trả lời user."""

    articles = None if state.get("skip_retrieval") else state.get("selected_articles", [])
    state["answer"] = await _chat_answer(runtime, state, articles)
    return state


async def format_submission_node(_: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Tạo nguồn theo format bài thi và ghi AIMessage vào memory."""

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


def _set_retrieval_text(runtime: Any, state: LegalAssistantState, retrieval_text: str, mode: str, provider: str):
    question = state["question"]
    state["retrieval_mode"] = mode
    state["retrieval_question"] = retrieval_text
    if mode == "rewrite":
        state["rewritten_question"] = retrieval_text
    elif mode == "hyde":
        state["hypothetical_answer"] = retrieval_text
    state["query_variants"] = _build_query_variants(runtime, question, retrieval_text)
    state.setdefault("tool_calls", []).append(
        {"name": "prepare_retrieval_query", "provider": provider, "args": {"mode": mode}, "result": retrieval_text}
    )
    return state


def _parse_categories(raw: str, allowed: list[str]) -> list[str]:
    text = raw.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = [item.strip(' -"') for item in text.replace("\n", ",").split(",")]
    if isinstance(value, str):
        value = [value]
    allowed_set = set(allowed)
    output: list[str] = []
    for item in value if isinstance(value, list) else []:
        if item in allowed_set and item not in output:
            output.append(item)
    return output


def _clean_retrieval_text(text: str, mode: str) -> str:
    return text.splitlines()[0].strip(" -\t") if mode == "rewrite" else text.strip()


def _build_query_variants(runtime: Any, question: str, retrieval_text: str) -> list[str]:
    variants: list[str] = []
    for item in [retrieval_text, question]:
        if item and item not in variants:
            variants.append(item)
    return variants[: runtime.settings.legal_assistant.query_rewrite.max_variants]


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
    except Exception as exc:
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
    return "\n\n".join(
        f"{getattr(message, 'type', message.__class__.__name__)}: {getattr(message, 'content', str(message))}"
        for message in messages
    )


def _fallback_answer(question: str, articles: list[LegalArticle] | None) -> str:
    if articles is None:
        return "Mình là MscAI. Bạn muốn hỏi vấn đề pháp lý nào?"
    if not articles:
        return "Mình chưa tìm thấy căn cứ trong kho dữ liệu đã đăng ký, nên chưa thể kết luận nội dung pháp lý cụ thể."
    lead = f"Dựa trên các căn cứ đã truy hồi cho câu hỏi: {question}"
    bullets = [f"- {article.article} của {article.law_name}: {' '.join(article.content.split())[:450]}" for article in articles[:5]]
    return "\n".join([lead, *bullets])


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
