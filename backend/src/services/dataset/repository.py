"""Repository PostgreSQL cho structured legal records.

Repository chỉ lo lưu/ghi dữ liệu vào DB. Nó không biết về FastAPI, prompt hay
LLM, nhờ vậy data layer tách khỏi agent runtime.
"""
from __future__ import annotations

import json

from src.config import get_settings
from src.schemas.knowledge import LegalKnowledgeRecord


class PostgresKnowledgeRepository:
    """Lưu các record pháp luật đã normalize vào PostgreSQL."""

    def __init__(self, database_url: str | None = None) -> None:
        # Cho phép truyền database_url khi test; production dùng config.yaml.
        self.database_url = database_url or get_settings().postgres.database_url

    async def init_schema(self) -> None:
        """Tạo bảng tri thức nếu chưa tồn tại."""

        conn = await self._connect()
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS legal_knowledge_records (
                    id TEXT PRIMARY KEY,
                    law_id TEXT NOT NULL,
                    law_name TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    chapter TEXT,
                    article TEXT NOT NULL,
                    article_title TEXT,
                    content TEXT NOT NULL,
                    author TEXT,
                    extra JSONB NOT NULL DEFAULT '[]'::jsonb,
                    vector_text TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        finally:
            await conn.close()

    async def upsert_many(self, records: list[LegalKnowledgeRecord]) -> None:
        """Insert hoặc update nhiều record theo khóa chính ``id``.

        Upsert giúp chạy lại script import nhiều lần mà không tạo bản ghi trùng.
        Nếu nội dung luật được cập nhật, record cũ sẽ được ghi đè bằng bản mới.
        """

        if not records:
            return
        conn = await self._connect()
        try:
            await conn.executemany(
                """
                INSERT INTO legal_knowledge_records (
                    id, law_id, law_name, doc_type, chapter, article, article_title,
                    content, author, extra, vector_text, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,NOW())
                ON CONFLICT (id) DO UPDATE SET
                    law_id = EXCLUDED.law_id,
                    law_name = EXCLUDED.law_name,
                    doc_type = EXCLUDED.doc_type,
                    chapter = EXCLUDED.chapter,
                    article = EXCLUDED.article,
                    article_title = EXCLUDED.article_title,
                    content = EXCLUDED.content,
                    author = EXCLUDED.author,
                    extra = EXCLUDED.extra,
                    vector_text = EXCLUDED.vector_text,
                    updated_at = NOW()
                """,
                [
                    (
                        record.id,
                        record.law_id,
                        record.law_name,
                        record.doc_type,
                        record.chapter,
                        record.article,
                        record.article_title,
                        record.content,
                        record.author,
                        json.dumps(sorted(record.extra), ensure_ascii=False),
                        record.vector_text,
                    )
                    for record in records
                ],
            )
        finally:
            await conn.close()

    async def _connect(self):
        """Tạo một connection asyncpg tới PostgreSQL."""

        try:
            import asyncpg
        except ImportError as exc:  # pragma: no cover - guard khi thiếu dependency
            raise RuntimeError("Install asyncpg to use PostgreSQL dataset storage") from exc
        return await asyncpg.connect(self.database_url)
