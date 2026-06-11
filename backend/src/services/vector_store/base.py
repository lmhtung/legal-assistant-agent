"""Interface và registry chung cho các vector store."""
from __future__ import annotations

from typing import Protocol

from src.schemas.legal import LegalArticle, RetrievalQuery, RetrievedCandidate


class LegalVectorStore(Protocol):
    """Contract tối thiểu mà mọi retrieval backend phải implement.

    Dùng ``Protocol`` giúp code type-check được mà không ép các store phải kế
    thừa class cụ thể. Chroma store, in-memory BM25 và hybrid store chỉ cần có
    đúng hai method này.
    """

    def add_articles(self, articles: list[LegalArticle]) -> None:
        """Thêm hoặc cập nhật các record pháp luật vào store."""
        ...

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Trả danh sách candidate đã rank cho một retrieval query."""
        ...


class VectorStoreRegistry:
    """Registry in-process map tên database sang store cụ thể."""

    def __init__(self) -> None:
        self._stores: dict[str, LegalVectorStore] = {}

    def register(self, database: str, store: LegalVectorStore) -> None:
        """Đăng ký store cho một nhóm dữ liệu pháp luật."""

        self._stores[database] = store

    def get(self, database: str) -> LegalVectorStore:
        """Lấy store theo database, báo lỗi nếu chưa đăng ký."""

        if database not in self._stores:
            raise KeyError(f"Database '{database}' is not registered")
        return self._stores[database]

    def has(self, database: str) -> bool:
        """Kiểm tra database đã có store trong process chưa."""

        return database in self._stores

    def list_databases(self) -> list[str]:
        """Liệt kê tên database đang được mở trong process hiện tại."""

        return sorted(self._stores)

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Search tất cả database request yêu cầu và merge theo score."""

        merged: list[RetrievedCandidate] = []
        for database in query.databases:
            if database not in self._stores:
                continue
            merged.extend(self._stores[database].search(query))
        merged.sort(key=lambda item: item.score, reverse=True)
        return merged[: query.top_k]


# Registry dùng chung trong FastAPI process. Dữ liệu bền vững nằm ở hệ
# thống data/vector store bên ngoài; registry chỉ giữ các object store đang mở.
vector_store_registry = VectorStoreRegistry()
