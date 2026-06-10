from __future__ import annotations

import math
import re
from collections import Counter

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


class InMemoryLegalStore:
    """Small lexical store for local tests; replace with Chroma/Qdrant behind the same API."""

    def __init__(self, database: str = "default") -> None:
        self.database = database
        self._articles: dict[str, LegalArticle] = {}
        self._term_freqs: dict[str, Counter[str]] = {}
        self._doc_freqs: Counter[str] = Counter()

    def add_articles(self, articles: list[LegalArticle]) -> None:
        for article in articles:
            article.database = article.database or self.database
            self._articles[article.article_id] = article
            terms = Counter(tokenize(" ".join([article.article, article.article_title or "", article.content])))
            self._term_freqs[article.article_id] = terms
        self._rebuild_doc_freqs()

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        query_terms = tokenize(query.question)
        if not query_terms:
            return []
        query_counter = Counter(query_terms)
        total_docs = max(len(self._articles), 1)
        scored: list[RetrievedCandidate] = []
        for article_id, article in self._articles.items():
            score = 0.0
            terms = self._term_freqs.get(article_id, Counter())
            for term, query_weight in query_counter.items():
                tf = terms.get(term, 0)
                if not tf:
                    continue
                df = self._doc_freqs.get(term, 0)
                idf = math.log((1 + total_docs) / (1 + df)) + 1.0
                score += query_weight * (1 + math.log(tf)) * idf
            if score > 0:
                article_with_score = article.model_copy(update={"score": score})
                scored.append(
                    RetrievedCandidate(
                        article=article_with_score,
                        source="bm25",
                        score=score,
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        for rank, candidate in enumerate(scored[: query.top_k], start=1):
            candidate.rank = rank
        return scored[: query.top_k]

    def _rebuild_doc_freqs(self) -> None:
        self._doc_freqs = Counter()
        for terms in self._term_freqs.values():
            self._doc_freqs.update(terms.keys())
