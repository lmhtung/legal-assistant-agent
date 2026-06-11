"""Schemas for importing structured legal datasets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.schemas.legal import LegalArticle


class LegalKnowledgeRecord(BaseModel):
    """Raw structured record supplied by the data-building pipeline."""

    id: str
    law_id: str
    law_name: str
    doc_type: str
    chapter: str | None = None
    article: str
    article_title: str | None = None
    content: str
    author: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def vector_text(self) -> str:
        """Text embedded into Chroma and indexed by lexical retrieval."""

        title_line = " ".join(item for item in [self.article, self.article_title] if item)
        return "\n".join(
            [
                f"{self.doc_type} {self.law_id} {self.law_name}".strip(),
                title_line.strip(),
                self.content.strip(),
            ]
        ).strip()

    def to_legal_article(self, database: str = "default") -> LegalArticle:
        """Convert an import record into the retrieval schema."""

        return LegalArticle(
            id=self.id,
            article_id=self.id,
            law_id=self.law_id,
            law_name=self.law_name,
            doc_type=self.doc_type,
            database=database,
            chapter=self.chapter,
            article=self.article,
            article_title=self.article_title,
            content=self.content,
            author=self.author,
            extra={**self.extra, "vector_text": self.vector_text},
        )


class DatasetImportRequest(BaseModel):
    """Request body for importing records from JSON payload or local file."""

    database: str = "default"
    records: list[LegalKnowledgeRecord] = Field(default_factory=list)
    input_path: Path | None = None
    save_to_postgres: bool = True
    index_vector_store: bool = True


class DatasetImportResponse(BaseModel):
    """Import result summary."""

    database: str
    num_records: int
    ids: list[str] = Field(default_factory=list)


def load_records_from_path(path: Path) -> list[LegalKnowledgeRecord]:
    """Load records from either a JSON array/object file or JSONL file."""

    text = Path(path).read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [LegalKnowledgeRecord.model_validate_json(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    return [LegalKnowledgeRecord.model_validate(item) for item in data]
