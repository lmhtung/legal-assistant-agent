# Project Architecture

Hệ thống có 2 luồng tách biệt: data build offline và agent runtime. Chỉ agent runtime là FastAPI service.

## Offline Data Builder

Entry point thao tác dữ liệu: `scripts/import_dataset.py`.

Không chạy port riêng, không có API view/search data, và không nằm trong `src` runtime. Đây là script nội bộ dùng khi cần import hoặc rebuild tri thức.

```text
structured JSON/JSONL dataset -> PostgreSQL -> Chroma/vector index
```

Vai trò:

- Validate record bằng schema `LegalKnowledgeRecord`.
- Ghi record vào bảng `legal_knowledge_records`.
- Embed text chuẩn hóa `doc_type + law_id + law_name + article + article_title + content`.
- Index theo từng `database` logic để agent search đúng nhóm pháp luật.

Port Docker PostgreSQL, ví dụ `25432`, chỉ nằm trong `postgres.database_url`. Nó không tạo thêm service HTTP nào.

## Agent Service

Entry point: `src.main:app`.

Chạy ở port API, ví dụ `8000`.

```text
question -> rewrite_query/hypothetical_answer -> vector search -> grounded answer -> competition output
```

Agent không tự xử lý raw data và không expose endpoint dataset. Khi request chỉ định `databases`, agent mở store tương ứng từ cấu hình và search trên index đã build trước đó.

## Retrieval Modes

`legal_assistant.retrieval.query_mode` hỗ trợ:

- `rewrite_query`: rewrite câu hỏi thành truy vấn pháp lý, embedding truy vấn rồi search.
- `hypothetical_answer`: sinh câu trả lời ngắn dự kiến, embedding đoạn đó rồi search.

`legal_assistant.query_rewrite.enabled=false` sẽ bỏ qua bước rewrite/HyDE và search trực tiếp bằng câu hỏi gốc.

## Extra References

Mỗi record có `extra`, là danh sách các điều luật liên quan theo format:

```text
doc_type|law_id|law_name|article
```

Agent dùng `extra` sau retrieval để mở rộng `relevant_articles` và `relevant_docs` một cách deterministic. `extra` không được đưa vào embedding vì nó là quan hệ nguồn, không phải nội dung điều luật chính.
