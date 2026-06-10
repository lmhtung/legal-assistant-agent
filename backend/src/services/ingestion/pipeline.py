from __future__ import annotations

from src.schemas.ingestion import IngestionRequest, IngestionResult
from src.services.ingestion.article_parser import LegalArticleParser
from src.services.ingestion.document_preprocessor import DocumentPreprocessor
from src.services.vector_store import InMemoryLegalStore, VectorStoreRegistry, vector_store_registry


class IngestionPipeline:
    def __init__(
        self,
        preprocessor: DocumentPreprocessor | None = None,
        parser: LegalArticleParser | None = None,
        registry: VectorStoreRegistry = vector_store_registry,
    ) -> None:
        self.preprocessor = preprocessor or DocumentPreprocessor()
        self.parser = parser or LegalArticleParser()
        self.registry = registry

    def ingest(self, request: IngestionRequest) -> IngestionResult:
        markdown_path = self.preprocessor.to_markdown(request.input_path, use_ocr=request.use_ocr)
        articles = self.parser.parse_markdown(markdown_path, request)
        if not self.registry.has(request.database):
            self.registry.register(request.database, InMemoryLegalStore(database=request.database))
        self.registry.get(request.database).add_articles(articles)
        return IngestionResult(
            database=request.database,
            law_id=request.law_id,
            law_name=request.law_name,
            markdown_path=markdown_path,
            num_articles=len(articles),
            article_ids=[article.article_id for article in articles],
        )
