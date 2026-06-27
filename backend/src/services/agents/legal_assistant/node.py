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

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate
from src.services.agents.legal_assistant.prompt import (
    SYSTEM_PROMPT,
    build_category_messages,
    build_hyde_messages,
    build_intent_messages,
    build_legal_context_message,
    build_rewrite_query_messages,
    default_law_category_slugs,
)
from src.services.agents.legal_assistant.state import LegalAssistantState
from src.services.agents.legal_assistant.tools import search_legal_articles
from src.services.agents.progress import emit_progress, emit_token, has_progress_callback


async def analyze_intent_node(runtime: Any, state: LegalAssistantState) -> LegalAssistantState:
    """Bước 1: phân tích query pháp luật hay chat thường."""

    started = perf_counter()
    await emit_progress(
        "memory",
        "completed",
        "Đã sẵn sàng ngữ cảnh hội thoại",
        metadata={"enabled": runtime.settings.short_memory.enabled},
    )
    if state.get("competition_mode"):
        state["legal_flag"] = "NEXT"
        state["skip_retrieval"] = False
        state.setdefault("tool_calls", []).append(
            {"name": "analyze_intent", "provider": "competition", "result": "NEXT"}
        )
        await emit_progress(
            "intent",
            "completed",
            "Competition mode: bỏ qua intent",
            elapsed_ms=_elapsed_ms(started),
            detail="Đi thẳng vào legal RAG để chạy tập test.",
            metadata={"legal_flag": "NEXT", "competition_mode": True},
        )
        return state

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
            system_prompt, human_prompt = build_intent_messages(state["question"])
            flag = (await _invoke_prompt_messages(runtime, system_prompt, human_prompt)).strip().upper()
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
    """Bước 2: tạo query variants từ rewrite và/hoặc HyDE."""

    started = perf_counter()
    question = state["question"]
    rewrite_enabled = runtime.settings.legal_assistant.rewrite.enabled
    hyde_enabled = runtime.settings.legal_assistant.hyde.enabled
    mode = _retrieval_mode(rewrite_enabled, hyde_enabled)
    state["retrieval_mode"] = mode
    await emit_progress(
        "prepare_query",
        "started",
        f"Đang chuẩn bị truy vấn retrieval theo mode {mode}",
        detail="Không gọi retrieval nếu intent là SKIP." if state.get("skip_retrieval") else None,
        metadata={"mode": mode, "rewrite_enabled": rewrite_enabled, "hyde_enabled": hyde_enabled},
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

    rewritten_question: str | None = None
    hypothetical_answer: str | None = None
    errors: list[str] = []
    provider = "llm" if runtime.llm is not None else "fallback"

    if runtime.llm is not None and rewrite_enabled:
        try:
            system_prompt, human_prompt = build_rewrite_query_messages(question)
            candidate = (await _invoke_prompt_messages(runtime, system_prompt, human_prompt)).strip()
            rewritten_question = _clean_retrieval_text(candidate, "rewrite") or question
            state["rewritten_question"] = rewritten_question
        except Exception as exc:  # pragma: no cover
            errors.append(f"rewrite: {exc}")
            state.setdefault("debug", {})["rewrite_error"] = str(exc)

    if runtime.llm is not None and hyde_enabled and not rewrite_enabled:
        try:
            system_prompt, human_prompt = build_hyde_messages(question)
            candidate = (await _invoke_prompt_messages(runtime, system_prompt, human_prompt)).strip()
            hypothetical_answer = _clean_retrieval_text(candidate, "hyde") or question
            state["hypothetical_answer"] = hypothetical_answer
        except Exception as exc:  # pragma: no cover
            errors.append(f"hyde: {exc}")
            state.setdefault("debug", {})["hyde_error"] = str(exc)

    retrieval_text = hypothetical_answer or rewritten_question or question
    state["retrieval_question"] = retrieval_text
    state["query_variants"] = _build_query_variants(runtime, question, rewritten_question, hypothetical_answer)
    state.setdefault("tool_calls", []).append(
        {
            "name": "prepare_retrieval_query",
            "provider": provider,
            "args": {"mode": mode},
            "result": retrieval_text,
            "query_variants": state["query_variants"],
        }
    )
    await emit_progress(
        "prepare_query",
        "warning" if errors else "completed",
        f"Đã chuẩn bị truy vấn {mode}" if not errors else "Một phần rewrite/HyDE lỗi, dùng phần còn lại",
        elapsed_ms=_elapsed_ms(started),
        detail="; ".join(errors) or None,
        metadata={
            "mode": mode,
            "provider": provider,
            "retrieval_question": retrieval_text,
            "query_variant_count": len(state["query_variants"]),
        },
    )
    return state


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
    rewrite_enabled = runtime.settings.legal_assistant.rewrite.enabled
    hyde_enabled = runtime.settings.legal_assistant.hyde.enabled
    hyde_only = bool(state.get("hypothetical_answer")) and hyde_enabled and not rewrite_enabled
    if hyde_only:
        categories = available_categories or state.get("categories") or ["default"]
        state["categories"] = categories
        state["per_category"] = False
        state["retrieval_top_k"] = settings.hyde_top_k
        await emit_progress(
            "categories",
            "completed",
            "HyDE tìm trên toàn bộ category",
            elapsed_ms=_elapsed_ms(started),
            metadata={"category_count": len(categories), "top_k": settings.hyde_top_k, "mode": mode},
        )
        return state

    query = state.get("rewritten_question") or state["question"]
    categories = state.get("categories") or ["default"]
    error: str | None = None
    if available_categories and runtime.llm is not None:
        try:
            system_prompt, human_prompt = build_category_messages(query, available_categories)
            raw = await _invoke_prompt_messages(runtime, system_prompt, human_prompt)
            categories = _parse_categories(raw, available_categories) or categories
        except Exception as exc:  # pragma: no cover
            error = str(exc)
            state.setdefault("debug", {})["category_error"] = error

    state["categories"] = categories
    if rewrite_enabled and hyde_enabled:
        category_answers, hyde_errors = await _build_category_hypothetical_answers(runtime, state, categories)
        if category_answers:
            state["category_hypothetical_answers"] = category_answers
            state["per_category"] = True
            state["retrieval_top_k"] = settings.hyde_top_k
            state.setdefault("tool_calls", []).append(
                {"name": "category_hyde", "provider": "llm", "result": category_answers, "errors": hyde_errors}
            )
            await emit_progress(
                "categories",
                "warning" if error or hyde_errors else "completed",
                "Đã chọn category và sinh HyDE theo từng category",
                elapsed_ms=_elapsed_ms(started),
                detail=("; ".join([item for item in [error, *hyde_errors] if item])) or None,
                metadata={
                    "categories": categories,
                    "category_count": len(categories),
                    "hyde_top_k_per_category": settings.hyde_top_k,
                    "category_hyde_count": len(category_answers),
                },
            )
            return state

    state["per_category"] = True
    state["retrieval_top_k"] = (
        settings.top_k_when_le_threshold_categories
        if len(categories) <= settings.many_category_threshold
        else settings.top_k_when_many_categories
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
        metadata={
            "categories": categories,
            "category_count": len(categories),
            "many_category_threshold": settings.many_category_threshold,
            "top_k_per_category": state["retrieval_top_k"],
        },
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

    category_hydes = state.get("category_hypothetical_answers") or {}
    if category_hydes:
        query = RetrievalQuery(
            question=state.get("retrieval_question") or state["question"],
            original_question=state["question"],
            query_variants=state.get("query_variants", [state["question"]]),
            categories=list(category_hydes),
            top_k=runtime.settings.legal_assistant.categories.hyde_top_k,
            per_category=True,
        )
    else:
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
        if category_hydes:
            candidates = await asyncio.to_thread(_search_category_hydes, runtime, state, category_hydes)
        else:
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
    """Cập nhật query retrieval khi không cần gọi LLM rewrite/HyDE."""

    question = state["question"]
    state["retrieval_mode"] = mode
    state["retrieval_question"] = retrieval_text
    state["query_variants"] = _build_query_variants(runtime, question, retrieval_text, None)
    state.setdefault("tool_calls", []).append(
        {"name": "prepare_retrieval_query", "provider": provider, "args": {"mode": mode}, "result": retrieval_text}
    )
    return state


def _parse_categories(raw: str, allowed: list[str]) -> list[str]:
    """Parse JSON/list text từ LLM và chỉ giữ category có trong law_names.json."""

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


def _prompt_messages(system_prompt: str, human_prompt: str) -> list[Any] | str:
    """Tạo messages đúng role; fallback về plain text nếu thiếu LangChain."""

    if SystemMessage is None or HumanMessage is None:
        return f"system: {system_prompt}\n\nhuman: {human_prompt}"
    return [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]


async def _invoke_prompt_messages(runtime: Any, system_prompt: str, human_prompt: str) -> str:
    """Gọi LLM cho các node nội bộ bằng SystemMessage/HumanMessage."""

    messages = _prompt_messages(system_prompt, human_prompt)
    if isinstance(messages, str):
        return await runtime.llm.ainvoke(messages)
    if hasattr(runtime.llm, "ainvoke_messages"):
        return await runtime.llm.ainvoke_messages(messages)
    return await runtime.llm.ainvoke(_messages_to_prompt(messages))


async def _build_category_hypothetical_answers(
    runtime: Any,
    state: LegalAssistantState,
    categories: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Sinh HyDE riêng cho từng category sau khi đã classify category."""

    output: dict[str, str] = {}
    errors: list[str] = []
    base_query = state.get("rewritten_question") or state["question"]
    for category in categories:
        category_question = f"{base_query}\nCategory cần tra cứu: {category}"
        try:
            system_prompt, human_prompt = build_hyde_messages(category_question)
            answer = (await _invoke_prompt_messages(runtime, system_prompt, human_prompt)).strip()
            output[category] = _clean_retrieval_text(answer, "hyde") or base_query
        except Exception as exc:  # pragma: no cover
            errors.append(f"{category}: {exc}")
    return output, errors


def _search_category_hydes(
    runtime: Any,
    state: LegalAssistantState,
    category_hydes: dict[str, str],
) -> list[RetrievedCandidate]:
    """Search từng category bằng hypothetical answer riêng rồi merge kết quả."""

    results: list[RetrievedCandidate] = []
    original_question = state["question"]
    base_variants = state.get("query_variants", [original_question])
    top_k = runtime.settings.legal_assistant.categories.hyde_top_k
    for category, hyde_answer in category_hydes.items():
        variants = []
        for item in [hyde_answer, *base_variants, original_question]:
            if item and item not in variants:
                variants.append(item)
        query = RetrievalQuery(
            question=hyde_answer,
            original_question=original_question,
            query_variants=variants,
            categories=[category],
            top_k=top_k,
            per_category=True,
        )
        results.extend(search_legal_articles(query, runtime.registry, runtime.store_factory))
    return _dedupe_candidates(results)


def _dedupe_candidates(candidates: list[RetrievedCandidate]) -> list[RetrievedCandidate]:
    """Bỏ trùng article_id, giữ candidate score cao nhất."""

    best = {}
    for candidate in candidates:
        article_id = candidate.article.article_id
        current = best.get(article_id)
        if current is None or candidate.score > current.score:
            best[article_id] = candidate
    return sorted(best.values(), key=lambda item: item.score, reverse=True)


def _clean_retrieval_text(text: str, mode: str) -> str:
    return text.splitlines()[0].strip(" -\t") if mode == "rewrite" else text.strip()


def _retrieval_mode(rewrite_enabled: bool, hyde_enabled: bool) -> str:
    if rewrite_enabled and hyde_enabled:
        return "rewrite+hyde"
    if rewrite_enabled:
        return "rewrite"
    if hyde_enabled:
        return "hyde"
    return "none"


def _build_query_variants(
    runtime: Any,
    question: str,
    rewritten_question: str | None,
    hypothetical_answer: str | None,
) -> list[str]:
    variants: list[str] = []
    for item in [hypothetical_answer, rewritten_question, question]:
        if item and item not in variants:
            variants.append(item)
    return variants[: runtime.settings.legal_assistant.rewrite.max_variants]


async def _chat_answer(runtime: Any, state: LegalAssistantState, articles: list[LegalArticle] | None) -> str:
    messages = _build_llm_messages(state, articles)
    if runtime.llm is None:
        return _fallback_answer(state["question"], articles)
    try:
        if runtime.settings.legal_assistant.chat.token_streaming and has_progress_callback():
            streamed = await _stream_chat_answer(runtime, messages)
            if streamed:
                return streamed
        if isinstance(messages, str):
            return await runtime.llm.ainvoke(messages)
        if hasattr(runtime.llm, "ainvoke_messages"):
            return await runtime.llm.ainvoke_messages(messages)
        return await runtime.llm.ainvoke(_messages_to_prompt(messages))
    except Exception as exc:
        state.setdefault("debug", {})["llm_error"] = str(exc)
        return _fallback_answer(state["question"], articles)


async def _stream_chat_answer(runtime: Any, messages: list[Any] | str) -> str:
    """Stream token trong node LangGraph answer và gom lại full answer."""

    chunks: list[str] = []
    if isinstance(messages, str):
        if not hasattr(runtime.llm, "astream"):
            return ""
        async for token in runtime.llm.astream(messages):
            chunks.append(token)
            await emit_token(token)
    else:
        if hasattr(runtime.llm, "astream_messages"):
            async for token in runtime.llm.astream_messages(messages):
                chunks.append(token)
                await emit_token(token)
        elif hasattr(runtime.llm, "astream"):
            async for token in runtime.llm.astream(_messages_to_prompt(messages)):
                chunks.append(token)
                await emit_token(token)
    return "".join(chunks).strip()


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
