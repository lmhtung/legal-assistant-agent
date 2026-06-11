"""Schema Pydantic cho retrieval và trả lời pháp lý.

Các schema ở đây là hợp đồng dữ liệu của runtime agent: request từ API, record
đã normalize để prompt/search, candidate sau retrieval và response theo format
có thể xuất ra bài thi.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class LegalArticle(BaseModel):
    """Một đơn vị tri thức pháp luật đã chuẩn hóa để agent sử dụng.

    ``article_id`` là id dùng trong vector store. ``database`` là nhóm pháp luật
    logic. ``score`` chỉ có sau retrieval, không bắt buộc khi import.
    """

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
    extra: set[str] = Field(default_factory=set)
    score: float | None = None

    @computed_field
    @property
    def doc_ref(self) -> str:
        """Reference văn bản theo format bài thi: ``law_id|law_name``."""

        return f"{self.law_id}|{self.law_name}"

    @computed_field
    @property
    def article_ref(self) -> str:
        """Reference điều luật theo format bài thi: ``law_id|law_name|Điều X``."""

        return f"{self.law_id}|{self.law_name}|{self.article}"

    @computed_field
    @property
    def title_text(self) -> str:
        """Chuỗi tiêu đề gọn để debug hoặc hiển thị nội bộ."""

        values = [self.doc_type, self.law_id, self.law_name, self.chapter, self.article, self.article_title]
        return " ".join(item for item in values if item)

    @computed_field
    @property
    def vector_text(self) -> str:
        """Text chuẩn được embed vào vector database."""

        title_line = " ".join(item for item in [self.article, self.article_title] if item)
        return "\n".join(
            [
                f"{self.doc_type} {self.law_id} {self.law_name}".strip(),
                title_line.strip(),
                self.content.strip(),
            ]
        ).strip()


class RetrievedCandidate(BaseModel):
    """Một kết quả retrieval từ BM25, vector search hoặc hybrid fusion."""

    article: LegalArticle
    source: Literal["bm25", "vector", "hybrid"] = "bm25"
    score: float = 0.0
    rank: int | None = None
    reason: str | None = None


class RetrievalQuery(BaseModel):
    """Query nội bộ gửi tới các vector store đã đăng ký."""

    question: str
    original_question: str | None = None
    query_variants: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8

    @property
    def all_queries(self) -> list[str]:
        """Gộp query rewrite, câu hỏi gốc và biến thể, đồng thời bỏ trùng.

        Lexical search cần nhiều biến thể hơn vector search vì exact keyword như
        số hiệu luật hoặc tên điều có thể nằm ở câu hỏi gốc nhưng mất trong bản
        rewrite.
        """

        values: list[str] = []
        for item in [self.question, self.original_question, *self.query_variants]:
            if item and item not in values:
                values.append(item)
        return values


class LegalAnswerRequest(BaseModel):
    """API request cho một câu hỏi pháp lý."""

    id: int | None = None
    question: str
    databases: list[str] = Field(default_factory=lambda: ["default"])
    top_k: int = 8
    include_debug: bool = False


class LegalAnswerResponse(BaseModel):
    """Câu trả lời grounded kèm nguồn theo format bài thi."""

    id: int | None = None
    question: str
    answer: str
    relevant_docs: list[str] = Field(default_factory=list)
    relevant_articles: list[str] = Field(default_factory=list)
    selected_articles: list[LegalArticle] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)

    def to_competition_record(self) -> dict[str, Any]:
        """Chỉ giữ các field cần thiết khi xuất ``results.json``."""

        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "relevant_docs": self.relevant_docs,
            "relevant_articles": self.relevant_articles,
        }


class BatchLegalAnswerRequest(BaseModel):
    """Request batch cho tập test nhiều câu hỏi."""

    items: list[LegalAnswerRequest]


class BatchLegalAnswerResponse(BaseModel):
    """Response batch có helper xuất toàn bộ kết quả ra JSON submit."""

    results: list[LegalAnswerResponse]

    def to_results_json(self) -> list[dict[str, Any]]:
        """Chuyển mọi response sang format bài thi."""

        return [item.to_competition_record() for item in self.results]
