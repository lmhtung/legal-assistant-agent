"""Các node xử lý của legal assistant workflow."""
from __future__ import annotations

import asyncio
import json
from time import perf_counter
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
    default_law_category_slugs,
)
from src.services.agents.legal_assistant.state import LegalAssistantState
from src.services.agents.legal_assistant.tools import search_legal_articles
from src.services.agents.progress import emit_progress


async def analyze_intent_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 1: phân tích query pháp luật hay chat thường."""

    started = perf_counter()
    await emit_progress(
        "memory",
        "completed",
        "Đã sẵn sàng ngữ cảnh hội thoại",
        metadata={"enabled": runtime.settings.short_memory.enabled},
    )
    await emit_progress(
        "intent",
        "started",
        "Đang phân tích câu hỏi có cần tra cứu pháp luật hay không",
        detail="Gọi LLM để chọn SKIP hoặc NEXT.",
    )
    flag = "NEXT"
    error: str | None = None
    if runtime.llm is not None:
        try:
            flag = (await runtime.llm.ainvoke(build_intent_prompt(state["question"]))).strip().upper()
        except Exception as exc:  # pragma: no cover
            error = str(exc)
            state.setdefault("debug", {})["intent_error"] = error
    if flag != "SKIP":
        flag = "NEXT"
    state["legal_flag"] = flag
    state["skip_retrieval"] = flag == "SKIP"
    state.setdefault("tool_calls", []).append(
        {"name": "analyze_intent", "provider": "llm" if runtime.llm else "fallback", "result": flag}
    )
    await emit_progress(
        "intent",
        "warning" if error else "completed",
        "Phân tích ý định hoàn tất" if not error else "LLM intent lỗi, tiếp tục theo NEXT",
        elapsed_ms=_elapsed_ms(started),
        detail=error or ("Bỏ qua legal retrieval." if flag == "SKIP" else "Tiếp tục legal RAG."),
        metadata={"legal_flag": flag},
    )
    return state


async def prepare_retrieval_query_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 2: none/rewrite/hyde để tạo text retrieval."""

    started = perf_counter()
    question = state["question"]
    mode = runtime.settings.legal_assistant.retrieval.query_mode
    rewrite_enabled = runtime.settings.legal_assistant.query_rewrite.enabled
    if not rewrite_enabled and mode in {"rewrite", "hyde"}:
        mode = "none"
    state["retrieval_mode"] = mode
    await emit_progress(
        "prepare_query",
        "started",
        f"Đang chuẩn bị truy vấn retrieval theo mode {mode}",
        detail="Không gọi retrieval nếu intent là SKIP." if state.get("skip_retrieval") else None,
        metadata={"mode": mode},
    )

    if state.get("skip_retrieval") or mode == "none":
        result = _set_retrieval_text(runtime, state, question, mode="none", provider="config")
        await emit_progress(
            "prepare_query",
            "completed",
            "Dùng trực tiếp câu hỏi gốc",
            elapsed_ms=_elapsed_ms(started),
            metadata={"mode": "none", "retrieval_question": question},
        )
        return result

    retrieval_text = question
    provider = "fallback"
    error: str | None = None
    if runtime.llm is not None and runtime.settings.legal_assistant.query_rewrite.use_llm:
        provider = "llm"
        prompt = build_rewrite_query_prompt(question) if mode == "rewrite" else build_hyde_prompt(question)
        try:
            candidate = (await runtime.llm.ainvoke(prompt)).strip()
            retrieval_text = _clean_retrieval_text(candidate, mode) or question
        except Exception as exc:  # pragma: no cover
            error = str(exc)
            state.setdefault("debug", {})["prepare_retrieval_error"] = error

    result = _set_retrieval_text(runtime, state, retrieval_text, mode=mode, provider=provider)
    await emit_progress(
        "prepare_query",
        "warning" if error else "completed",
        f"Đã chuẩn bị truy vấn {mode}" if not error else f"{mode} lỗi, dùng câu hỏi gốc",
        elapsed_ms=_elapsed_ms(started),
        detail=error,
        metadata={"mode": mode, "provider": provider, "retrieval_question": retrieval_text},
    )
    return result


async def classify_categories_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 3 non-HyDE: phân tích query thuộc category luật nào."""

    started = perf_counter()
    await emit_progress(
        "categories",
        "started",
        "Đang xác định các category pháp luật cần tìm",
        detail="LLM chọn category từ law_names.json.",
    )
    if state.get("skip_retrieval"):
        await emit_progress(
            "categories",
            "completed",
            "Bỏ qua phân loại category",
            elapsed_ms=_elapsed_ms(started),
            detail="Intent là SKIP.",
        )
        return state

    settings = runtime.settings.legal_assistant.categories
    available_categories = default_law_category_slugs()
    mode = state.get("retrieval_mode")
    if mode == "hyde":
        categories = available_categories or state.get("categories") or ["default"]
        state["categories"] = categories
        state["per_category"] = False
        state["retrieval_top_k"] = settings.hyde_top_k
        await emit_progress(
            "categories",
            "completed",
            "HyDE tìm trên toàn bộ category",
            elapsed_ms=_elapsed_ms(started),
            metadata={"category_count": len(categories), "top_k": settings.hyde_top_k},
        )
        return state

    query = state.get("retrieval_question") or state["question"]
    categories = state.get("categories") or ["default"]
    error: str | None = None
    if available_categories and runtime.llm is not None:
        try:
            raw = await runtime.llm.ainvoke(build_category_prompt(query, available_categories))
            categories = _parse_categories(raw, available_categories) or categories
        except Exception as exc:  # pragma: no cover
            error = str(exc)
            state.setdefault("debug", {})["category_error"] = error

    state["categories"] = categories
    state["per_category"] = True
    state["retrieval_top_k"] = (
        settings.top_k_when_le_2_categories if len(categories) <= 2 else settings.top_k_when_many_categories
    )
    state.setdefault("tool_calls", []).append(
        {"name": "classify_categories", "provider": "llm" if available_categories and runtime.llm else "config", "result": categories}
    )
    await emit_progress(
        "categories",
        "warning" if error else "completed",
        "Đã chọn category" if not error else "Phân loại category lỗi, dùng category fallback",
        elapsed_ms=_elapsed_ms(started),
        detail=error,
        metadata={"categories": categories, "top_k_per_category": state["retrieval_top_k"]},
    )
    return state


async def retrieve_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 4: embedding/search theo category đã chọn."""

    started = perf_counter()
    if state.get("skip_retrieval"):
        state["retrieved"] = []
        state["selected_articles"] = []
        state.setdefault("tool_calls", []).append({"name": "skip_retrieval", "provider": "backend", "num_results": 0})
        await emit_progress(
            "retrieval",
            "completed",
            "Bỏ qua retrieval",
            elapsed_ms=_elapsed_ms(started),
            detail="Intent là SKIP.",
        )
        return state

    query = RetrievalQuery(
        question=state.get("retrieval_question") or state["question"],
        original_question=state["question"],
        query_variants=state.get("query_variants", [state["question"]]),
        categories=state.get("categories") or ["default"],
        top_k=state.get("retrieval_top_k") or 3,
        per_category=state.get("per_category", False),
    )
    search_mode = runtime.settings.legal_assistant.vector_store.mode
    await emit_progress(
        "retrieval",
        "started",
        f"Đang chạy {search_mode} search",
        detail="Embedding query, tìm Chroma/BM25 và hợp nhất RRF." if search_mode == "hybrid" else None,
        metadata={"categories": query.categories, "top_k": query.top_k, "mode": search_mode},
    )
    error: str | None = None
    try:
        # Retrieval là code đồng bộ và có thể nặng; chạy trong thread để SSE
        # heartbeat vẫn tiếp tục báo thời gian chờ cho UI.
        candidates = await asyncio.to_thread(search_legal_articles, query, runtime.registry, runtime.store_factory)
    except Exception as exc:
        candidates = []
        error = str(exc)
        state.setdefault("debug", {})["local_retrieval_error"] = error

    state.setdefault("tool_calls", []).append(
        {
            "name": "search_legal_articles",
            "provider": "backend",
            "args": query.model_dump(mode="json"),
            "num_results": len(candidates),
            "error": error,
        }
    )
    state["retrieved"] = candidates
    state["selected_articles"] = [candidate.article for candidate in candidates]
    await emit_progress(
        "retrieval",
        "error" if error else ("completed" if candidates else "warning"),
        "Retrieval lỗi" if error else f"Retrieval trả về {len(candidates)} kết quả",
        elapsed_ms=_elapsed_ms(started),
        detail=error or (None if candidates else "Không tìm thấy candidate phù hợp."),
        metadata={"num_results": len(candidates), "mode": search_mode, "categories": query.categories},
    )
    return state


async def generate_answer_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 5: tổng hợp điều luật tìm được và trả lời user."""

    started = perf_counter()
    articles = None if state.get("skip_retrieval") else state.get("selected_articles", [])
    await emit_progress(
        "answer",
        "started",
        "Đang gọi LLM tổng hợp câu trả lời",
        detail=f"Đưa {len(articles or [])} điều luật vào context." if articles is not None else "Trả lời hội thoại thông thường.",
        metadata={"article_count": len(articles or []), "skip_retrieval": state.get("skip_retrieval", False)},
    )
    state["answer"] = await _chat_answer(runtime, state, articles)
    error = state.get("debug", {}).get("llm_error")
    await emit_progress(
        "answer",
        "warning" if error else "completed",
        "Đã tạo câu trả lời" if not error else "LLM trả lời lỗi, đã dùng fallback",
        elapsed_ms=_elapsed_ms(started),
        detail=str(error) if error else None,
        metadata={"answer_length": len(state.get("answer", ""))},
    )
    return state


async def format_submission_node(_: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Tạo nguồn theo format bài thi và ghi AIMessage vào memory."""

    started = perf_counter()
    await emit_progress("format", "started", "Đang chuẩn hóa nguồn và lưu short-memory")
    if state.get("skip_retrieval"):
        state["relevant_docs"] = []
        state["relevant_articles"] = []
        _append_ai_message(state)
        await emit_progress(
            "format",
            "completed",
            "Đã hoàn tất câu trả lời không retrieval",
            elapsed_ms=_elapsed_ms(started),
        )
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
    await emit_progress(
        "format",
        "completed",
        "Đã chuẩn hóa kết quả và cập nhật short-memory",
        elapsed_ms=_elapsed_ms(started),
        metadata={"document_count": len(docs), "article_count": len(article_refs)},
    )
    return state


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)


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
