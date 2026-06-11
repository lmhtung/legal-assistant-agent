# Legal Assistant System Report

Tài liệu này mô tả lại toàn bộ kiến trúc hiện tại của hệ thống legal assistant sau khi đã tách rõ ba phần: data system bên ngoài, MCP retrieval server và backend agent runtime.

## 1. Mục Tiêu Thiết Kế

Hệ thống được thiết kế để trả lời câu hỏi pháp lý tiếng Việt dựa trên dữ liệu luật đã được xử lý sẵn. Backend agent không import dữ liệu, không xử lý PDF/OCR, không sửa database và không expose API quản lý dataset.

Mục tiêu chính:

- Tách data pipeline khỏi agent runtime.
- Cho phép data/vector DB tự cập nhật độc lập.
- Đưa các tool đọc/search dữ liệu vào MCP để dễ mở rộng.
- Giữ backend agent đơn giản: nhận câu hỏi, tối ưu query, gọi tool, sinh câu trả lời.
- Trả output có `answer`, `relevant_docs`, `relevant_articles` phù hợp với format bài test.

## 2. Sơ Đồ Tổng Thể

```mermaid
flowchart LR
    User[Người dùng / Test set] --> API[FastAPI Agent Backend]
    API --> Rewrite[Rewrite Query / HyDE]
    Rewrite --> MCPClient[MCP Retrieval Client]
    MCPClient --> MCP[MCP Legal Retrieval Server]
    MCP --> Vector[(Vector DB / Chroma)]
    MCP --> PG[(PostgreSQL Legal Records)]
    MCP --> MCPClient
    MCPClient --> Agent[Grounded Answer Agent]
    Agent --> Output[answer + relevant_docs + relevant_articles]

    Data[External Data System] --> PG
    Data --> Vector
```

Ý nghĩa:

- `External Data System` là phần nằm ngoài backend này. Nó tự thêm/sửa dữ liệu, tự build PostgreSQL và vector index.
- `MCP Legal Retrieval Server` là boundary đọc dữ liệu. Backend chỉ gọi tool MCP.
- `FastAPI Agent Backend` không ghi database, không import dataset.

## 3. Các Thành Phần Chính

### 3.1 External Data System

Phần này không nằm trong backend agent. Nó chịu trách nhiệm:

- Chuẩn hóa dữ liệu luật thành record có cấu trúc.
- Lưu record vào PostgreSQL.
- Tạo vector index từ text chuẩn.
- Đảm bảo metadata trong vector DB đủ để MCP trả về `LegalArticle`.

Backend chỉ kỳ vọng data đã có sẵn.

### 3.2 MCP Legal Retrieval Server

Thư mục chính:

```text
mcp/src/legal_mcp/
```

Cấu trúc:

```text
legal_mcp/main.py                  # entrypoint chạy MCP
legal_mcp/config.py                # đọc mcp/config.yaml
legal_mcp/core/                    # BaseMCPServer, registry, factory, runner
legal_mcp/servers/legal/           # plugin legal retrieval
legal_mcp/servers/legal/tools/     # nơi thêm MCP tools
legal_mcp/vector.py                # đọc Chroma vector index
legal_mcp/postgres.py              # query PostgreSQL cho search_relevant
legal_mcp/schemas.py               # schema output của MCP tools
```

Điểm học từ project mẫu:

- Có `ServerRegistry` để đăng ký server plugin.
- Có `ServerFactory` để tạo server theo config.
- Có `MultiServerRunner` để chạy server bằng uvicorn.
- Tool nằm trong plugin `servers/legal`, không trộn vào core.

### 3.3 Backend Agent Runtime

Thư mục chính:

```text
backend/src/
```

Các file quan trọng:

```text
main.py                                      # FastAPI entrypoint
config.py                                    # cấu hình backend
services/agents/legal_assistant/agent.py     # LangGraph agent chính
services/mcp/client.py                       # MCP retrieval client
schemas/legal.py                             # schema request/response/retrieval
routers/legal.py                             # API hỏi đáp
```

Backend làm các việc:

- Nhận request từ API.
- Rewrite query hoặc sinh hypothetical answer.
- Gọi MCP tool `search_legal_articles`.
- Nếu bật, gọi tiếp MCP tool `search_relevant` dựa trên `extra`.
- Đọc short-memory theo `session_id` khi dùng endpoint `/chat`.
- Prompt LLM bằng các điều luật đã retrieve và ngữ cảnh chat ngắn.
- Format nguồn theo `relevant_docs`, `relevant_articles`.

## 4. Luồng Xử Lý Một Câu Hỏi

```mermaid
sequenceDiagram
    participant U as User/Test
    participant B as Backend Agent
    participant L as LLM
    participant M as MCP Server
    participant V as Vector DB
    participant P as PostgreSQL

    U->>B: POST /api/v1/legal/chat hoặc /answer
    B->>B: lấy short-memory nếu có session_id
    B->>L: rewrite_query hoặc hypothetical_answer
    L-->>B: retrieval_text
    B->>M: search_legal_articles(retrieval_text, databases, top_k)
    M->>V: vector search
    V-->>M: candidates + metadata + extra
    M-->>B: retrieved candidates

    B->>M: search_relevant(extra_refs, databases)
    M->>P: exact match by doc_type/law_id/law_name/article
    P-->>M: related legal records
    M-->>B: related candidates

    B->>L: grounded answer prompt
    L-->>B: answer
    B-->>U: answer + relevant_docs + relevant_articles
```

Nếu `mcp_retrieval.enabled=false`, backend dùng local retrieval fallback để dev/test. Trong production nên bật MCP để đúng kiến trúc data tách biệt.

## 5. MCP Tools

### 5.1 `search_legal_articles`

Input:

```json
{
  "query": "truy vấn đã rewrite hoặc HyDE",
  "original_question": "câu hỏi gốc",
  "query_variants": ["..."],
  "databases": ["labor"],
  "top_k": 8
}
```

Nhiệm vụ:

- Embed `query`.
- Search vector DB theo từng `database`.
- Trả candidates có metadata đầy đủ.

Output rút gọn:

```json
{
  "candidates": [
    {
      "article": {
        "id": "...",
        "article_id": "...",
        "law_id": "44/2013/NĐ-CP",
        "law_name": "...",
        "doc_type": "Nghị định",
        "database": "labor",
        "article": "Điều 1",
        "article_title": "...",
        "content": "...",
        "extra": ["Nghị định|44/2013/NĐ-CP|...|Điều 2"]
      },
      "source": "vector",
      "score": 0.87,
      "rank": 1
    }
  ]
}
```

### 5.2 `search_relevant`

Input:

```json
{
  "extra_refs": [
    "Nghị định|44/2013/NĐ-CP|Tên văn bản|Điều 2"
  ],
  "databases": ["labor"],
  "top_k": 16
}
```

Nhiệm vụ:

- Parse từng item trong `extra`.
- Query PostgreSQL bằng exact match theo:
  - `doc_type`
  - `law_id`
  - `law_name`
  - `article`
- Không dùng embedding.

Vì sao cần tool này:

- `extra` là quan hệ pháp lý đã được data system xác định.
- Nếu search chính trúng `Điều 1`, hệ thống có thể lấy đầy đủ nội dung `Điều 2`, `Điều 3` liên quan mà không cần vector search lại.
- Điều này giúp prompt có thêm căn cứ liên quan và giúp output nguồn ổn định hơn.

## 6. Schema Dữ Liệu Chuẩn

Record chuẩn mà data system cần lưu:

```json
{
  "id": "44_2013_ND_CP_Dieu_1",
  "law_id": "44/2013/NĐ-CP",
  "law_name": "Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động",
  "doc_type": "Nghị định",
  "database": "labor",
  "chapter": "Chương I NHỮNG QUY ĐỊNH CHUNG",
  "article": "Điều 1",
  "article_title": "Phạm vi điều chỉnh",
  "content": "...",
  "author": "Chính phủ",
  "extra": [
    "Nghị định|44/2013/NĐ-CP|Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động|Điều 2"
  ]
}
```

Text nên được embedding:

```text
{doc_type} {law_id} {law_name}
{article} {article_title}
{content}
```

Không embedding `extra`, vì `extra` là quan hệ nguồn để mở rộng sau retrieval.

## 7. Cấu Hình Chính

### 7.1 Backend

File:

```text
backend/config.yaml
```

Short-memory cho chat:

```yaml
short_memory:
  enabled: true
  max_turns: 6
  max_chars: 4000
```

Memory này chỉ áp dụng cho `/api/v1/legal/chat`. Client cần gửi cùng `session_id` để backend nối các lượt chat lại với nhau. `/answer` và `/batch` vẫn stateless.

MCP retrieval:

```yaml
mcp_retrieval:
  enabled: false
  primary_server: legal_retrieval
  servers:
    legal_retrieval:
      url: http://localhost:8765/mcp
      transport: http
  fallback_to_local: true
  fetch_related: true
  related_top_k: 16
```

Ý nghĩa:

- `enabled`: bật/tắt MCP retrieval.
- `primary_server`: server MCP chính mà backend gọi.
- `servers`: danh sách MCP servers.
- `fallback_to_local`: MCP lỗi thì dùng local fallback.
- `fetch_related`: có gọi `search_relevant` từ `extra` hay không.
- `related_top_k`: số điều luật liên quan tối đa lấy từ PostgreSQL.

Query mode:

```yaml
legal_assistant:
  retrieval:
    query_mode: rewrite_query # rewrite_query | hypothetical_answer
```

- `rewrite_query`: LLM viết lại câu hỏi thành truy vấn pháp lý.
- `hypothetical_answer`: LLM sinh câu trả lời ngắn dự kiến rồi dùng nó để search.

### 7.2 MCP

File:

```text
mcp/config.yaml
```

Ví dụ:

```yaml
servers:
  legal_retrieval:
    enabled: true
    host: 0.0.0.0
    port: 8765
    path: /mcp
    settings:
      postgres:
        database_url: postgresql://user:password@localhost:25432/legal_assistant
        table_name: legal_knowledge_records
        database_column: database
      embeddings:
        base_url: http://localhost:8002/v1
        model: bge-m3
      vector_store:
        provider: chroma
        persist_directory: ../backend/chroma_db
        collection_prefix: legal_articles
```

## 8. Cách Chạy

Chạy MCP server:

```bash
cd mcp
pip install -r requirements.txt
PYTHONPATH=src python -m legal_mcp.main
```

Chạy backend agent:

```bash
cd backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Gọi API:

```text
POST /api/v1/legal/answer
POST /api/v1/legal/batch
POST /api/v1/legal/chat
GET  /health
```

## 9. Sơ Đồ Module MCP

```mermaid
flowchart TD
    Main[legal_mcp.main] --> Import[import legal_mcp.servers]
    Import --> Register[ServerRegistry.register legal_retrieval]
    Main --> Factory[ServerFactory.create_enabled_servers]
    Factory --> LegalServer[LegalRetrievalServer]
    LegalServer --> Tools[register_retrieval_tools]
    Tools --> Search[search_legal_articles]
    Tools --> Relevant[search_relevant]
    Search --> Chroma[ChromaRetriever]
    Relevant --> Postgres[PostgresLegalRepository]
    Main --> Runner[MultiServerRunner]
    Runner --> Uvicorn[uvicorn]
```

## 10. Sơ Đồ Module Backend

```mermaid
flowchart TD
    API[routers/legal.py] --> Dep[dependencies.py]
    Dep --> Agent[LegalAssistantAgent]
    Dep --> MCPClient[MCPRetrievalClient]
    Agent --> Rewrite[_rewrite_query_node]
    Rewrite --> Retrieve[_retrieve_node]
    Retrieve --> MCPClient
    MCPClient --> MCP[MCP Server]
    Retrieve --> Local[local vector fallback]
    Retrieve --> Generate[_generate_answer_node]
    Generate --> Format[_format_submission_node]
    Format --> Response[LegalAnswerResponse]
```

## 11. Short-Memory Trong Chat

Short-memory được đặt trong backend runtime, không nằm ở MCP và không ghi database.

Luồng hoạt động:

```text
/chat request có session_id
-> ShortMemoryStore lấy vài lượt gần nhất
-> LegalAnswerRequest.conversation_history
-> rewrite/HyDE prompt dùng history để làm rõ câu hỏi
-> grounded answer prompt dùng history để hiểu ngữ cảnh
-> lưu lượt user/assistant mới vào memory
```

Giới hạn:

- Memory mất khi backend process restart.
- Không dùng làm căn cứ pháp lý.
- Chỉ dùng để hiểu câu hỏi nối tiếp trong cùng đoạn chat.

## 12. Điểm Mạnh Của Kiến Trúc Hiện Tại

- Data tách khỏi agent, đúng yêu cầu không import/sửa dữ liệu trong backend.
- MCP là nơi mở rộng tools, backend không ôm data logic.
- `search_relevant` giúp khai thác quan hệ `extra` bằng exact lookup, không tốn embedding.
- Backend vẫn có fallback local để dev/test.
- MCP server có plugin structure đủ gọn nhưng vẫn học được điểm hay từ project mẫu.
- Output nguồn được kiểm soát deterministic hơn nhờ `extra`.

## 13. Cách Mở Rộng

### Thêm tool MCP mới

Thêm file hoặc hàm trong:

```text
mcp/src/legal_mcp/servers/legal/tools/
```

Sau đó đăng ký trong:

```text
mcp/src/legal_mcp/servers/legal/tools/retrieval.py
```

Hoặc tách thành module riêng rồi import trong:

```text
mcp/src/legal_mcp/servers/legal/server.py
```

### Thêm database pháp luật mới

Data system bên ngoài tự build PostgreSQL/vector DB. Backend chỉ cần request:

```json
{
  "question": "...",
  "databases": ["labor", "civil"]
}
```

MCP sẽ search các collection/database tương ứng.

### Tắt fallback local khi production

Trong production, nếu muốn bắt buộc dùng MCP:

```yaml
mcp_retrieval:
  enabled: true
  fallback_to_local: false
```

## 14. Những Phần Đã Cố Tình Loại Bỏ

Các phần sau không còn nằm trong backend agent:

- OCR/PDF ingestion.
- Script `import_dataset.py`.
- Dataset router/API.
- Dataset service ghi PostgreSQL.
- Schema import dataset riêng.
- Logic phân loại hoặc chỉnh sửa data trong backend.

Lý do: data system là khối độc lập, tự cập nhật và tự build index.

## 15. Kết Luận

Kiến trúc hiện tại phù hợp với mục tiêu legal assistant có dữ liệu tách biệt:

```text
Data tự quản lý -> MCP tools đọc/search -> Backend agent suy luận/trả lời
```

Backend agent tập trung vào workflow hỏi đáp. MCP tập trung vào tool/data boundary. Data system tập trung vào chất lượng và cập nhật tri thức. Ba phần này tách nhau đủ rõ để dễ nâng cấp, test và triển khai.
