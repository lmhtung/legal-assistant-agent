# Project Architecture

Hệ thống được tách thành ba phần:

```text
External Data System -> tự xử lý/tự cập nhật PostgreSQL và vector index
MCP Server           -> expose tools đọc/search data
Agent Runtime        -> hỏi đáp, không import hoặc sửa dữ liệu
```

## External Data System

Phần data không nằm trong backend agent. Nó tự tạo PostgreSQL/vector DB, tự update dữ liệu và tự đảm bảo metadata đúng contract trong `data-structure.md`.

## MCP Server

MCP là boundary tool cho data. MCP server dùng cấu trúc plugin tối giản: `core` quản lý registry/factory/runner, còn `servers/legal` chứa tools pháp luật. Khi thiếu tool mới, thêm tool ở MCP thay vì thêm logic data vào backend agent.

Tools hiện có:

```text
search_legal_articles(query, original_question, query_variants, databases, top_k)
search_relevant(extra_refs, databases, top_k)
```

`search_relevant` parse `extra` rồi query PostgreSQL bằng exact match theo `doc_type`, `law_id`, `law_name`, `article`. Tool này không dùng embedding.

## Agent Service

Entry point: `src.main:app`.

```text
question -> rewrite_query/hypothetical_answer -> MCP search -> grounded answer -> competition output
```

Nếu `mcp_retrieval.enabled=false`, agent dùng tool local cũ để dev/fallback. Nếu MCP bật nhưng lỗi và `fallback_to_local=true`, agent cũng fallback local.

## Retrieval Modes

`legal_assistant.retrieval.query_mode` hỗ trợ:

- `rewrite_query`: rewrite câu hỏi thành truy vấn pháp lý, gửi truy vấn sang MCP search.
- `hypothetical_answer`: sinh câu trả lời ngắn dự kiến, gửi đoạn đó sang MCP search.

`legal_assistant.query_rewrite.enabled=false` sẽ bỏ qua bước rewrite/HyDE và search trực tiếp bằng câu hỏi gốc.
