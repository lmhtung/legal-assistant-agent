"""Tự động dựng Chroma từ PostgreSQL khi backend khởi động."""
from __future__ import annotations

import fcntl
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.config import Settings
from src.schemas.legal import LegalArticle
from src.services.embeddings.client import get_embeddings_client
from src.services.vector_store.base import VectorStoreRegistry, vector_store_registry
from src.services.vector_store.chroma import ChromaLegalStore, safe_collection_name
from src.services.vector_store.hybrid import HybridLegalStore
from src.services.vector_store.in_memory import InMemoryLegalStore

logger = logging.getLogger("uvicorn.error")
_MANIFEST_NAME = "legal_index_manifest.json"
_LOCK_NAME = ".legal_index.lock"


def quote_identifier(value: str) -> str:
    """Quote table/column đã được validate bởi cấu hình Pydantic."""

    return ".".join(f'"{part}"' for part in value.split("."))


async def initialize_legal_index(
    settings: Settings,
    registry: VectorStoreRegistry = vector_store_registry,
) -> None:
    """Đồng bộ PostgreSQL -> Chroma một lần và nạp BM25 cho process hiện tại.

    Chroma chỉ được rebuild khi chưa có manifest, collection không đủ record,
    nguồn PostgreSQL thay đổi hoặc embedding endpoint/model thay đổi. BM25 luôn
    được nạp lại vì index này chỉ tồn tại trong RAM của backend process.
    """

    postgres = settings.legal_assistant.postgres
    logger.info("[index] Bắt đầu chuẩn bị retrieval index")
    if not postgres.enabled:
        logger.info("Bỏ qua auto-index vì legal_assistant.postgres.enabled=false")
        return

    persist_directory = settings.legal_assistant.vector_store.persist_directory
    persist_directory.mkdir(parents=True, exist_ok=True)
    lock_path = persist_directory / _LOCK_NAME

    # File lock ngăn nhiều uvicorn worker cùng embedding lại một bộ dữ liệu.
    with lock_path.open("w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        logger.info("[index] Đang đọc legal records từ PostgreSQL")
        articles_by_category = await _fetch_articles(settings)
        if not articles_by_category:
            return
        total_records = sum(len(items) for items in articles_by_category.values())
        logger.info(
            "[index] Đã đọc %s record thuộc %s category",
            total_records,
            len(articles_by_category),
        )
        expected_manifest = _manifest(settings, articles_by_category)
        manifest_path = persist_directory / _MANIFEST_NAME
        current_manifest = _read_manifest(manifest_path)

        rebuild = current_manifest != expected_manifest or not _collections_are_complete(
            settings,
            expected_manifest["categories"],
        )
        if rebuild:
            logger.info("[index] Chroma chưa hợp lệ, bắt đầu embedding và rebuild")
            _rebuild_chroma(settings, articles_by_category)
            manifest_path.write_text(
                json.dumps(expected_manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("Đã build Chroma: %s records", expected_manifest["total_records"])
        else:
            logger.info("Chroma index hợp lệ, bỏ qua embedding lại")

        logger.info("[index] Bắt đầu nạp BM25/runtime stores")
        _register_runtime_stores(settings, registry, articles_by_category)
        logger.info("[index] Hoàn tất chuẩn bị retrieval index")


async def _fetch_articles(settings: Settings) -> dict[str, list[LegalArticle]]:
    """Đọc toàn bộ record luật từ PostgreSQL và nhóm theo category."""

    try:
        import asyncpg
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("Cần cài asyncpg để tự động build Chroma từ PostgreSQL") from exc

    postgres = settings.legal_assistant.postgres
    conn = await asyncpg.connect(postgres.database_url)
    try:
        available_columns = await _get_columns(conn, postgres.table_name)
        required = {
            "id",
            "law_id",
            "law_name",
            "doc_type",
            "article",
            "article_title",
            "content",
            "author",
            postgres.category_column,
        }
        missing = required - available_columns
        if missing:
            raise RuntimeError(f"Bảng PostgreSQL thiếu cột bắt buộc: {sorted(missing)}")

        optional_selects = [
            quote_identifier(name) if name in available_columns else f"NULL AS {quote_identifier(name)}"
            for name in ("chapter", "extra")
        ]
        sql = f"""
            SELECT id, law_id, law_name, doc_type, article, article_title,
                   content, author, {', '.join(optional_selects)},
                   {quote_identifier(postgres.category_column)} AS category
            FROM {quote_identifier(postgres.table_name)}
            ORDER BY {quote_identifier(postgres.category_column)}, id
        """
        rows = await conn.fetch(sql)
    finally:
        await conn.close()

    if not rows:
        logger.warning("PostgreSQL chưa có legal record; backend khởi động với index rỗng")
        return {}

    grouped: dict[str, list[LegalArticle]] = defaultdict(list)
    for row in rows:
        data = dict(row)
        data["id"] = str(data["id"])
        data["category"] = str(data.get("category") or "default")
        data["extra"] = _normalize_extra(data.get("extra"))
        grouped[data["category"]].append(LegalArticle.model_validate(data))
    return dict(grouped)


async def _get_columns(conn: Any, table_name: str) -> set[str]:
    """Lấy danh sách cột để hỗ trợ schema không có chapter/extra."""

    parts = table_name.split(".")
    schema, table = (parts[0], parts[1]) if len(parts) == 2 else ("public", parts[0])
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        """,
        schema,
        table,
    )
    return {str(row["column_name"]) for row in rows}


def _normalize_extra(value: Any) -> set[str]:
    """Chuẩn hóa extra từ JSON/array PostgreSQL về set string."""

    if value is None:
        return set()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {value} if value else set()
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if item}
    return set()


def _manifest(settings: Settings, grouped: dict[str, list[LegalArticle]]) -> dict[str, Any]:
    """Tạo dấu vân tay đủ để không trộn vector từ hai embedding model."""

    postgres = settings.legal_assistant.postgres
    parsed = urlparse(postgres.database_url)
    return {
        "version": 1,
        "postgres": {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/"),
            "table": postgres.table_name,
            "category_column": postgres.category_column,
        },
        "embedding": {
            "base_url": settings.embeddings.base_url.rstrip("/"),
            "model": settings.embeddings.model,
        },
        "vector_text": "law_name\narticle_title\ncontent",
        "categories": {category: len(items) for category, items in sorted(grouped.items())},
        "total_records": sum(len(items) for items in grouped.values()),
    }


def _read_manifest(path: Path) -> dict[str, Any] | None:
    """Đọc manifest cũ; file lỗi được xem như chưa từng build."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _collections_are_complete(settings: Settings, categories: dict[str, int]) -> bool:
    """Đối chiếu số vector trong Chroma với manifest PostgreSQL."""

    try:
        import chromadb

        vector = settings.legal_assistant.vector_store
        client = chromadb.PersistentClient(path=str(vector.persist_directory))
        for category, expected_count in categories.items():
            name = safe_collection_name(f"{vector.default_collection}_{category}")
            if client.get_collection(name).count() != expected_count:
                return False
        return True
    except Exception:
        return False


def _rebuild_chroma(settings: Settings, grouped: dict[str, list[LegalArticle]]) -> None:
    """Xóa collection legal cũ rồi embed/upsert từng category theo batch."""

    import chromadb

    vector = settings.legal_assistant.vector_store
    postgres = settings.legal_assistant.postgres
    client = chromadb.PersistentClient(path=str(vector.persist_directory))
    prefix = safe_collection_name(vector.default_collection)
    for collection in client.list_collections():
        name = collection if isinstance(collection, str) else collection.name
        if name == prefix or name.startswith(f"{prefix}_"):
            client.delete_collection(name)

    embeddings = get_embeddings_client()
    total_categories = len(grouped)
    processed_records = 0
    for category_index, (category, articles) in enumerate(grouped.items(), start=1):
        logger.info(
            "[index][Chroma %s/%s] %s: %s record",
            category_index,
            total_categories,
            category,
            len(articles),
        )
        store = ChromaLegalStore(
            database=category,
            persist_directory=str(vector.persist_directory),
            collection_prefix=vector.default_collection,
            embeddings=embeddings,
        )
        for start in range(0, len(articles), postgres.batch_size):
            batch = articles[start : start + postgres.batch_size]
            store.add_articles(batch)
            processed_records += len(batch)
            logger.info(
                "[index][Chroma] Đã embedding %s/%s record",
                processed_records,
                sum(len(items) for items in grouped.values()),
            )


def _register_runtime_stores(
    settings: Settings,
    registry: VectorStoreRegistry,
    grouped: dict[str, list[LegalArticle]],
) -> None:
    """Đăng ký Chroma và nạp BM25 để hybrid search dùng được ngay."""

    vector = settings.legal_assistant.vector_store
    embeddings = get_embeddings_client()
    total_categories = len(grouped)
    for category_index, (category, articles) in enumerate(grouped.items(), start=1):
        logger.info(
            "[index][Runtime %s/%s] %s: nạp %s record",
            category_index,
            total_categories,
            category,
            len(articles),
        )
        chroma_store = ChromaLegalStore(
            database=category,
            persist_directory=str(vector.persist_directory),
            collection_prefix=vector.default_collection,
            embeddings=embeddings,
        )
        if vector.mode == "chroma":
            registry.register(category, chroma_store)
            continue

        lexical_store = InMemoryLegalStore(
            database=category,
            tokenizer=vector.bm25_tokenizer,
            k1=vector.bm25_k1,
            b=vector.bm25_b,
            epsilon=vector.bm25_epsilon,
        )
        lexical_store.add_articles(articles)
        if vector.mode == "bm25":
            registry.register(category, lexical_store)
        else:
            registry.register(
                category,
                HybridLegalStore(lexical_store, chroma_store, rrf_k=vector.rrf_k),
            )
