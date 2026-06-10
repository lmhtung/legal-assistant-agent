from __future__ import annotations

import re
from pathlib import Path

from src.schemas.ingestion import IngestionRequest
from src.schemas.legal import LegalArticle

_ARTICLE_RE = re.compile(r"(?m)^\s*(Điều\s+\d+[a-zA-Z]?\.?)(?:\s+([^\n]+))?")


class LegalArticleParser:
    def parse_markdown(self, markdown_path: Path, request: IngestionRequest) -> list[LegalArticle]:
        text = Path(markdown_path).read_text(encoding="utf-8")
        matches = list(_ARTICLE_RE.finditer(text))
        if not matches:
            return [self._build_article("Toàn văn", None, text, request, markdown_path)]

        articles: list[LegalArticle] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            article = match.group(1).rstrip(".")
            title = (match.group(2) or "").strip() or None
            content = text[start:end].strip()
            articles.append(self._build_article(article, title, content, request, markdown_path))
        return articles

    def _build_article(
        self,
        article: str,
        title: str | None,
        content: str,
        request: IngestionRequest,
        markdown_path: Path,
    ) -> LegalArticle:
        article_id = f"{request.law_id}|{request.law_name}|{article}"
        return LegalArticle(
            article_id=article_id,
            law_id=request.law_id,
            law_name=request.law_name,
            doc_type=request.doc_type,
            database=request.database,
            article=article,
            article_title=title,
            content=content,
            markdown=content,
            source_file=request.source_file or str(request.input_path),
            extra={"markdown_path": str(markdown_path)},
        )
