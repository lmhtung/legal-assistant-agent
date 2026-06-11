"""PostgreSQL repository for structured legal knowledge records."""
from __future__ import annotations

import json

from src.config import get_settings
from src.schemas.knowledge import LegalKnowledgeRecord


class PostgresKnowledgeRepository:
    """Persist normalized legal records in PostgreSQL."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or get_settings().postgres.database_url

    async def init_schema(self) -> None:
        """Create the knowledge table if it does not exist."""

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
                    extra JSONB NOT NULL DEFAULT '{}'::jsonb,
                    vector_text TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        finally:
            await conn.close()

    async def upsert_many(self, records: list[LegalKnowledgeRecord]) -> None:
        """Insert or update records by stable dataset id."""

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
                        json.dumps(record.extra, ensure_ascii=False),
                        record.vector_text,
                    )
                    for record in records
                ],
            )
        finally:
            await conn.close()

    async def _connect(self):
        """Create one asyncpg connection."""

        try:
            import asyncpg
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("Install asyncpg to use PostgreSQL dataset storage") from exc
        return await asyncpg.connect(self.database_url)
