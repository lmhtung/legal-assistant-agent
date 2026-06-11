"""Schema cho dataset pháp luật đã được xử lý sẵn.

Backend không xử lý PDF/OCR trong luồng chính nữa. Dữ liệu đầu vào cần đã ở
dạng JSON/JSONL có cấu trúc, mỗi record tương ứng một điều luật hoặc một đơn vị
tri thức pháp lý đủ nhỏ để embedding.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from src.schemas.legal import LegalArticle


class LegalKnowledgeRecord(BaseModel):
    """Record thô từ dataset dùng ở bước import/build tri thức.

    ``extra`` chứa các điều luật liên quan theo format
    ``doc_type|law_id|law_name|article``. Nó là quan hệ pháp lý thủ công/đã xử
    lý, nên không đưa vào embedding; agent chỉ dùng nó sau retrieval để mở rộng
    danh sách nguồn liên quan.
    """

    id: str
    law_id: str
    law_name: str
    doc_type: str
    chapter: str | None = None
    article: str
    article_title: str | None = None
    content: str
    author: str | None = None
    extra: set[str] = Field(default_factory=set)

    @property
    def vector_text(self) -> str:
        """Text chuẩn dùng để embedding và index lexical.

        Công thức đúng theo yêu cầu: ``doc_type + law_id + law_name`` rồi đến
        ``article + article_title`` và cuối cùng là ``content``. Thứ tự này giúp
        vector chứa cả ngữ cảnh văn bản, số hiệu luật và nội dung điều luật.
        """

        title_line = " ".join(item for item in [self.article, self.article_title] if item)
        return "\n".join(
            [
                f"{self.doc_type} {self.law_id} {self.law_name}".strip(),
                title_line.strip(),
                self.content.strip(),
            ]
        ).strip()

    def to_legal_article(self, database: str = "default") -> LegalArticle:
        """Đổi record import sang schema runtime dùng cho retrieval và prompt."""

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
            extra=set(self.extra),
        )


class DatasetImportRequest(BaseModel):
    """Input cho job import dataset offline.

    Có thể truyền record trực tiếp qua ``records`` khi test, hoặc truyền
    ``input_path`` khi chạy script import file JSON/JSONL thật.
    """

    database: str = "default"
    records: list[LegalKnowledgeRecord] = Field(default_factory=list)
    input_path: Path | None = None
    save_to_postgres: bool = True
    index_vector_store: bool = True


class DatasetImportResponse(BaseModel):
    """Kết quả tóm tắt sau khi import dataset."""

    database: str
    num_records: int
    ids: list[str] = Field(default_factory=list)


def load_records_from_path(path: Path) -> list[LegalKnowledgeRecord]:
    """Load record từ file JSON hoặc JSONL và validate bằng Pydantic.

    JSONL phù hợp với dataset lớn vì mỗi dòng là một object độc lập. JSON thường
    dùng cho dataset nhỏ, có thể là một object hoặc một mảng object.
    """

    text = Path(path).read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [LegalKnowledgeRecord.model_validate_json(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    return [LegalKnowledgeRecord.model_validate(item) for item in data]
