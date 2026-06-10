from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


InputKind = Literal["auto", "pdf_text", "pdf_ocr", "markdown", "text"]


class DatabaseRegistration(BaseModel):
    database: str = "default"
    name: str
    description: str = ""
    document_types: list[str] = Field(default_factory=list)
    mcp_server: str | None = None


class IngestionRequest(BaseModel):
    input_path: Path
    law_id: str
    law_name: str
    database: str = "default"
    doc_type: str | None = None
    source_file: str | None = None
    input_kind: InputKind = "auto"
    use_ocr: bool | None = None


class IngestionResult(BaseModel):
    database: str
    law_id: str
    law_name: str
    markdown_path: Path
    num_articles: int
    article_ids: list[str] = Field(default_factory=list)
