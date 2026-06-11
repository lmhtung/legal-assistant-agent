# Legal Assistant Agent

Backend này là **agent runtime** cho trợ lý pháp lý tiếng Việt. Phần database/vector database được tách sang MCP server và hệ thống data bên ngoài. Backend không import data, không sửa data và không expose API quản lý dataset.

Luồng chính:

```text
Backend Agent -> MCP Retrieval Tools -> Vector DB / PostgreSQL
```

Backend vẫn giữ tool local làm fallback/dev. Khi cần thêm tool mới, ưu tiên viết trong plugin MCP `servers/legal`, không cần nhét thêm logic data vào agent.

Tài liệu backend: [backend/README.md](backend/README.md)

Tài liệu MCP retrieval: [mcp/README.md](mcp/README.md)

Tài liệu cấu trúc data: [backend/docs/data-structure.md](backend/docs/data-structure.md)
