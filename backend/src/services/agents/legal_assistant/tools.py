"""Backend tools dùng bởi legal assistant.

File này chứa tool retrieval chạy trực tiếp trong backend. Tool sử dụng registry
Chroma/BM25 đã được nạp từ PostgreSQL khi service khởi động.
"""
from __future__ import annotations

from src.schemas.legal import RetrievalQuery, RetrievedCandidate
from src.services.vector_store import VectorStoreFactory, VectorStoreRegistry


def search_legal_articles(
    query: RetrievalQuery,
    registry: VectorStoreRegistry,
    store_factory: VectorStoreFactory,
) -> list[RetrievedCandidate]:
    """Search điều luật trong vector store local theo category.

    Hàm này là tool search chính của backend agent:
    - mỗi ``category`` tương ứng một collection/index riêng;
    - nếu category chưa được mở trong process thì tạo store lazy;
    - registry chịu trách nhiệm merge/rank kết quả cuối cùng.
    """

    for category in query.categories:
        if not registry.has(category):
            registry.register(category, store_factory.create(category))
    return registry.search(query)
