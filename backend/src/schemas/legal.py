"""Pydantic schemas for retrieval and answer generation."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class LegalArticle(BaseModel):
    """A normalized legal knowledge unit used by retrieval and answer prompts."""

    id: str
    article_id: str
    law_id: str
    law_name: str
    doc_type: str
    database: str = "default"
    chapter: str | None = None
    article: str
    article_title: str | None = None
    content: str
    author: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None

    @computed_field
    @property
    def doc_ref(self) -> str:
        """Competition document reference: ``law_id|law_name``."""

        return f"{self.law_id}|{self.law_name}"

    @computed_field
    @property
    def article_ref(self) -> str:
        """Competition article reference: ``law_id|law_name|Điều X``."""

        return f"{self.law_id}|{self.law_name}|{self.article}"

    @computed_field
    @property
    def title_text(self) -> str:
        """Compact title string for display/debugging."""

        values = [self.doc_type, self.law_id, self.law_name, self.chapter, self.article, self.article_title]
        return " ".join(item for item in values if item)

    @computed_field
    @property
    def vector_text(self) -> str:
        """Canonical text embedded for vector retrieval."""

        title_line = " ".join(item for item in [self.article, self.article_title] if item)
        return "\n".join(
            [
                f"{self.doc_type} {self.law_id} {self.law_name}".strip(),
                title_line.strip(),
                self.content.strip(),
            ]
        ).strip()


class RetrievedCandidate(BaseModel):
    """One retrieval hit from BM25, vector search, or hybrid fusion."""

    article: LegalArticle
    source: Literal["bm25", "vector", "hybrid"] = "bm25"
    score: float = 0.0
    rank: int | None = None
    reason: str | None = None


class RetrievalQuery(BaseModel):
    """Internal retrieval request sent to registered vector stores."""

    question: str
    original_question: str | None = None
    query_variants: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8

    @property
    def all_queries(self) -> list[str]:
        """Deduplicate rewritten/original query variants for lexical search."""

        values: list[str] = []
        for item in [self.question, self.original_question, *self.query_variants]:
            if item and item not in values:
                values.append(item)
        return values


class LegalAnswerRequest(BaseModel):
    """API request for one legal question."""

    id: int | None = None
    question: str
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8
    include_debug: bool = False


class LegalAnswerResponse(BaseModel):
    """Grounded answer plus competition-compatible references."""

    id: int | None = None
    question: str
    answer: str
    relevant_docs: list[str] = Field(default_factory=list)
    relevant_articles: list[str] = Field(default_factory=list)
    selected_articles: list[LegalArticle] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)

    def to_competition_record(self) -> dict[str, Any]:
        """Return only fields expected by the competition ``results.json``."""

        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "relevant_docs": self.relevant_docs,
            "relevant_articles": self.relevant_articles,
        }


class BatchLegalAnswerRequest(BaseModel):
    """Batch answer request for test sets."""

    items: list[LegalAnswerRequest]


class BatchLegalAnswerResponse(BaseModel):
    """Batch answer response with a helper for exporting results.json."""

    results: list[LegalAnswerResponse]

    def to_results_json(self) -> list[dict[str, Any]]:
        """Convert every response to the competition JSON shape."""

        return [item.to_competition_record() for item in self.results]
