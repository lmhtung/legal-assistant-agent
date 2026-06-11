# Legal Assistant Agent

Hệ thống trợ lý pháp lý tiếng Việt gồm hai khối tách biệt rõ:

- **Offline Data Builder**: chạy job nội bộ để import structured dataset, lưu PostgreSQL và build vector index. Khối này không mở API để view/search data.
- **Agent Service**: FastAPI runtime nhận câu hỏi, rewrite query hoặc sinh hypothetical answer, search kho vector đã build, prompt LLM và trả kết quả theo format bài thi.

Tài liệu backend chi tiết: [backend/README.md](backend/README.md)

Tài liệu cấu trúc data: [backend/docs/data-structure.md](backend/docs/data-structure.md)
