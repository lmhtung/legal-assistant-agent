from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class LegalDocumentRef(BaseModel):
    law_id: str
    law_name: str
    doc_type: str | None = None

    @computed_field
    @property
    def competition_ref(self) -> str:
        return f"{self.law_id}|{self.law_name}"


class LegalArticle(BaseModel):
    article_id: str = Field(..., description="Unique id: law_id|law_name|article")
    law_id: str
    law_name: str
    doc_type: str | None = None
    database: str = "default"

    article: str = Field(..., description="Vi du: Dieu 4")
    article_title: str | None = None
    chapter: str | None = None
    section: str | None = None

    content: str
    markdown: str | None = None

    source_file: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    effective_date: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    score: float | None = None

    @computed_field
    @property
    def doc_ref(self) -> str:
        return f"{self.law_id}|{self.law_name}"

    @computed_field
    @property
    def article_ref(self) -> str:
        return f"{self.law_id}|{self.law_name}|{self.article}"


class RetrievedCandidate(BaseModel):
    article: LegalArticle
    source: Literal["bm25", "vector", "hybrid", "mcp", "memory"] = "memory"
    score: float = 0.0
    rank: int | None = None
    reason: str | None = None


class RetrievalQuery(BaseModel):
    question: str
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8
    filters: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    query: RetrievalQuery
    candidates: list[RetrievedCandidate] = Field(default_factory=list)

    @property
    def articles(self) -> list[LegalArticle]:
        return [candidate.article for candidate in self.candidates]


class LegalAnswerRequest(BaseModel):
    id: int | None = None
    question: str
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8
    include_debug: bool = False


class LegalAnswerResponse(BaseModel):
    id: int | None = None
    question: str
    answer: str
    relevant_docs: list[str] = Field(default_factory=list)
    relevant_articles: list[str] = Field(default_factory=list)
    selected_articles: list[LegalArticle] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)

    def to_competition_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "relevant_docs": self.relevant_docs,
            "relevant_articles": self.relevant_articles,
        }


class CompetitionResultRecord(BaseModel):
    id: int | None = None
    question: str
    answer: str
    relevant_docs: list[str]
    relevant_articles: list[str]


class BatchLegalAnswerRequest(BaseModel):
    items: list[LegalAnswerRequest]


class BatchLegalAnswerResponse(BaseModel):
    results: list[LegalAnswerResponse]

    def to_results_json(self) -> list[dict[str, Any]]:
        return [item.to_competition_record() for item in self.results]
