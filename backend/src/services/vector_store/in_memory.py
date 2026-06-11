"""Lexical retrieval store dùng như nhánh BM25-like của hybrid search."""
from __future__ import annotations

import math
import re
from collections import Counter

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tách token đơn giản cho tiếng Việt/văn bản pháp luật.

    Đây không phải Vietnamese tokenizer đầy đủ, nhưng đủ tốt cho tín hiệu exact
    match như số hiệu văn bản, số điều, thuật ngữ pháp lý và tên riêng.
    """

    return [token.lower() for token in _TOKEN_RE.findall(text)]


class InMemoryLegalStore:
    """Index lexical nhỏ, chạy trong RAM.

    Store này không thay thế Elasticsearch/OpenSearch. Nó bổ sung tín hiệu từ
    khóa cho hybrid retrieval, nhất là khi người dùng hỏi đúng số hiệu luật hoặc
    tên điều mà embedding đôi khi làm mờ.
    """

    def __init__(self, database: str = "default") -> None:
        self.database = database
        self._articles: dict[str, LegalArticle] = {}
        self._term_freqs: dict[str, Counter[str]] = {}
        self._doc_freqs: Counter[str] = Counter()

    def add_articles(self, articles: list[LegalArticle]) -> None:
        """Index text chuẩn của từng record vào bộ đếm term frequency."""

        for article in articles:
            article.database = article.database or self.database
            self._articles[article.article_id] = article
            self._term_freqs[article.article_id] = Counter(tokenize(index_text(article)))
        self._rebuild_doc_freqs()

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Tính score TF-IDF/BM25-like cho các record trong RAM."""

        query_terms: list[str] = []
        for query_text in query.all_queries:
            query_terms.extend(tokenize(query_text))
        if not query_terms:
            return []

        query_counter = Counter(query_terms)
        total_docs = max(len(self._articles), 1)
        scored: list[RetrievedCandidate] = []
        for article_id, article in self._articles.items():
            terms = self._term_freqs.get(article_id, Counter())
            score = 0.0
            for term, query_weight in query_counter.items():
                tf = terms.get(term, 0)
                if not tf:
                    continue
                df = self._doc_freqs.get(term, 0)
                idf = math.log((1 + total_docs) / (1 + df)) + 1.0
                score += query_weight * (1 + math.log(tf)) * idf
            if score > 0:
                scored.append(
                    RetrievedCandidate(
                        article=article.model_copy(update={"score": score}),
                        source="bm25",
                        score=score,
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        for rank, candidate in enumerate(scored[: query.top_k], start=1):
            candidate.rank = rank
        return scored[: query.top_k]

    def _rebuild_doc_freqs(self) -> None:
        """Tính lại document frequency sau mỗi lần add/update record."""

        self._doc_freqs = Counter()
        for terms in self._term_freqs.values():
            self._doc_freqs.update(terms.keys())


def index_text(article: LegalArticle) -> str:
    """Trả text chuẩn dùng chung cho lexical và vector retrieval."""

    return article.vector_text
