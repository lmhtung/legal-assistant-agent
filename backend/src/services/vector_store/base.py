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
    """Registry in-process map tên category sang store cụ thể."""

    def __init__(self) -> None:
        self._stores: dict[str, LegalVectorStore] = {}

    def register(self, category: str, store: LegalVectorStore) -> None:
        """Đăng ký store cho một category pháp luật."""

        self._stores[category] = store

    def get(self, category: str) -> LegalVectorStore:
        """Lấy store theo category, báo lỗi nếu chưa đăng ký."""

        if category not in self._stores:
            raise KeyError(f"Category '{category}' is not registered")
        return self._stores[category]

    def has(self, category: str) -> bool:
        """Kiểm tra category đã có store trong process chưa."""

        return category in self._stores

    def list_databases(self) -> list[str]:
        """Liệt kê category đang được mở trong process hiện tại."""

        return sorted(self._stores)

    def search(self, query: RetrievalQuery) -> list[RetrievedCandidate]:
        """Search các category được chọn và merge theo score.

        Với mode non-HyDE, ``per_category=True`` nghĩa là mỗi category đã tự lấy
        ``top_k`` kết quả, nên registry không cắt global nữa. Với HyDE hoặc search
        thường, registry cắt global theo ``top_k``.
        """

        merged: list[RetrievedCandidate] = []
        for category in query.categories:
            if category not in self._stores:
                continue
            merged.extend(self._stores[category].search(query))
        merged.sort(key=lambda item: item.score, reverse=True)
        return merged if query.per_category else merged[: query.top_k]


# Registry dùng chung trong FastAPI process. Dữ liệu bền vững nằm ở PostgreSQL
# và vector DB; registry chỉ giữ các object store đang mở theo category.
vector_store_registry = VectorStoreRegistry()
