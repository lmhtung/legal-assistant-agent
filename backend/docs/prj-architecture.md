# Project Architecture

Hệ thống gồm ba khối rõ ràng:

```text
PostgreSQL Data Source -> Startup Index Builder -> Chroma + BM25
                                               -> Legal Agent -> FastAPI/UI
```

## 1. PostgreSQL

PostgreSQL là nguồn dữ liệu luật đã được xử lý sẵn. Backend chỉ đọc dữ liệu,
không cung cấp API thêm/sửa/xóa dataset và không xử lý PDF/OCR.

Mỗi record có `category`; category được dùng để tạo collection Chroma riêng.

## 2. Startup Index Builder

`src/services/vector_store/index_builder.py` chạy một lần trong FastAPI lifespan:

```text
backend startup
-> kết nối PostgreSQL
-> đọc và validate records
-> nhóm theo category
-> kiểm tra legal_index_manifest.json
-> build/reuse Chroma
-> nạp BM25 vào RAM
-> bắt đầu nhận request
```

Chroma không embedding lại khi manifest và collection count hợp lệ. Rebuild xảy
ra nếu nguồn PostgreSQL, số record, embedding endpoint/model hoặc format vector
text thay đổi.

## 3. Retrieval Stores

- Chroma: vector index persistent trong `backend/chroma_db`.
- BM25: lexical index trong RAM, nạp lại mỗi backend process.
- Hybrid: merge Chroma và BM25 bằng Reciprocal Rank Fusion.

Mỗi category có collection dạng `legal_articles_<category>`.

## 4. Agent Workflow

```text
question
-> analyze_intent: SKIP hoặc NEXT
-> prepare_retrieval_query: none/rewrite/hyde
-> classify_categories
-> search_legal_articles trong backend tools.py
-> hybrid retrieval
-> grounded answer
-> competition output
```

- `SKIP`: không retrieval, LLM trả lời hội thoại thông thường.
- `none`: embedding câu hỏi gốc.
- `rewrite`: embedding câu hỏi đã viết lại theo ngôn ngữ luật.
- `hyde`: embedding hypothetical answer do LLM tạo.

## 5. Embedding Consistency

Document build và query search đều dùng singleton `EmbeddingsClient`. Hai phía
dùng cùng `base_url`, `model` và tokenizer nằm trong embedding server. Manifest
lưu embedding configuration để không tái sử dụng vector từ model khác.

BM25 có tokenizer riêng vì đây là lexical retrieval, không phải vector embedding.

## 6. Short Memory

LangGraph `InMemorySaver` giữ lịch sử theo `session_id` khi backend đang chạy.
Memory mất hoàn toàn khi process dừng và không được lưu vào PostgreSQL/Chroma.
