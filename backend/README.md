# Legal Assistant Backend

Backend này chỉ chạy agent hỏi đáp. Phần database/vector database được quản lý qua MCP server hoặc hệ thống data bên ngoài.

```text
External Data System -> tự build PostgreSQL/vector DB
MCP Server           -> expose retrieval tools
Agent Service        -> question -> rewrite/HyDE -> MCP tool call -> grounded answer
```

Backend agent không có script import data, không có endpoint dataset, không mở port data và không ghi PostgreSQL. Khi bật MCP, agent gọi tool MCP trên server `legal_retrieval`. Khi MCP tắt hoặc lỗi và `fallback_to_local=true`, agent dùng tool local cũ trong backend.

## Agent Service

Chạy agent:

```bash
cd backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoint chính:

```text
POST /api/v1/legal/answer
POST /api/v1/legal/batch
POST /api/v1/legal/chat
GET  /health
```

## MCP Retrieval

Bật MCP trong `backend/config.yaml`:

```yaml
mcp_retrieval:
  enabled: true
  primary_server: legal_retrieval
  servers:
    legal_retrieval:
      url: http://localhost:8765/mcp
      transport: http
  fallback_to_local: true
  fetch_related: true
  related_top_k: 16
```

Khi bật, agent gọi:

```text
search_legal_articles -> search vector DB qua MCP
search_relevant       -> đọc extra rồi query PostgreSQL exact match, không embedding
```

## Query Mode

```yaml
legal_assistant:
  retrieval:
    query_mode: rewrite_query # rewrite_query | hypothetical_answer
```

- `rewrite_query`: LLM viết lại câu hỏi thành truy vấn pháp lý ngắn, rồi gửi sang MCP để search.
- `hypothetical_answer`: LLM sinh câu trả lời ngắn dự kiến, rồi gửi đoạn đó sang MCP để search.

## Hợp Đồng Dữ Liệu

MCP tool cần trả đủ metadata để backend dựng lại `LegalArticle`: `id`, `article_id`, `law_id`, `law_name`, `doc_type`, `database`, `chapter`, `article`, `article_title`, `content`, `author`, `extra`, `score`.

`extra` dùng format:

```text
doc_type|law_id|law_name|article
```

Agent dùng `extra` để gọi `search_relevant`, lấy nội dung điều luật liên quan từ PostgreSQL và đưa thêm vào context trả lời.
