# Legal Retrieval MCP

MCP server này là boundary giữa backend agent và hệ thống dữ liệu/vector DB. Cấu trúc được giữ giống tinh thần project mẫu: có core runner/registry/factory và server plugin riêng.

## Cấu Trúc

```text
mcp/src/legal_mcp/core/              # hạ tầng chạy MCP server
mcp/src/legal_mcp/servers/legal/     # plugin legal retrieval
mcp/src/legal_mcp/vector.py          # đọc Chroma vector index
mcp/src/legal_mcp/postgres.py        # đọc PostgreSQL cho search_relevant
```

## Tools

```text
search_legal_articles(query, original_question, query_variants, databases, top_k)
```

Search vector DB đã build sẵn và trả candidates có metadata đủ để backend dựng `LegalArticle`.

```text
search_relevant(extra_refs, databases, top_k)
```

Parse `extra` theo format `doc_type|law_id|law_name|article`, rồi query PostgreSQL exact match. Tool này không dùng embedding.

## Chạy MCP Server

```bash
cd mcp
pip install -r requirements.txt
PYTHONPATH=src python -m legal_mcp.main
```

## Thêm Tool Mới

Thêm tool vào:

```text
mcp/src/legal_mcp/servers/legal/tools/
```

Sau đó import/đăng ký trong `servers/legal/server.py` hoặc `tools/retrieval.py`. Backend không cần biết chi tiết data layer, chỉ gọi MCP theo contract.
