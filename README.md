# MscAI Legal Assistant

`backend/config.yaml` là nguồn cấu hình duy nhất cho ứng dụng:

```text
config.yaml
├── app: FastAPI host/port
├── ui: Next.js host/port
├── llm: endpoint/model
├── embeddings: endpoint/model
├── short_memory
└── legal_assistant: PostgreSQL/retrieval/vector store
```

Không còn dùng `.env`, `.env.local`, `NEXT_PUBLIC_API_BASE_URL` hoặc biến môi
trường để ghi đè cấu hình runtime.

## Cấu hình

Chỉ sửa [backend/config.yaml](backend/config.yaml). Ví dụ:

```yaml
app:
  host: 0.0.0.0
  port: 8025

ui:
  host: 0.0.0.0
  port: 5173

llm:
  base_url: http://localhost:8017/v1
  default_model: qwen35-9b

embeddings:
  base_url: http://localhost:8013/v1
  model: bge-m3

legal_assistant:
  competition:
    enabled: false
  postgres:
    database_url: postgresql://postgres:postgres@localhost:23432/legal_assistant
```

`legal_assistant.competition.enabled=true` dùng khi chạy tập test: agent bỏ qua
bước Intent và đi thẳng vào legal RAG. UI cũng có nút `Competition` để bật tạm
thời mà không cần sửa YAML.

Sau khi sửa YAML, restart service liên quan.

## Chạy bằng Docker

Dùng wrapper để Compose nhận PostgreSQL/UI port từ YAML:

```bash
./compose.sh build backend ui
./compose.sh up -d postgres
```

Nạp dataset:

```bash
./compose.sh run --rm backend python scripts/load_postgres.py --truncate
```

Chạy backend và UI:

```bash
./compose.sh up -d backend ui
./compose.sh logs -f backend
```

Với cấu hình hiện tại:

```text
UI:         http://localhost:5173
Backend:    http://localhost:8025
Health:     http://localhost:8025/health
PostgreSQL: localhost:23432
```

Dừng project, giữ volume:

```bash
./compose.sh down
```

`compose.sh` chỉ đọc YAML rồi gọi Docker Compose. Không tạo một file config thứ
hai. Docker dùng host network để các URL `localhost` trong YAML giữ nguyên ý
nghĩa cả khi backend chạy trong container.

## Chạy development trên máy

### 1. PostgreSQL

```bash
./compose.sh up -d postgres
```

### 2. Backend

```bash
cd backend
uv sync --frozen
uv run python scripts/load_postgres.py --truncate
uv run python scripts/run_backend.py --reload
```

`run_backend.py` tự đọc `app.host` và `app.port`; không truyền port bằng CLI.

### 3. UI

Terminal khác:

```bash
cd ui
npm ci
npm run dev
```

UI gọi `/backend-api/...`. Next.js proxy đọc `app.port` trực tiếp từ
`backend/config.yaml`, nên không cần `.env.local`.

## Competition mode

Input tập test là JSON array trực tiếp:

```json
[
  {
    "id": 1,
    "question": "Các cơ sở ươm tạo và khu làm việc chung được hưởng những chính sách hỗ trợ nào về thuế và đất đai?"
  }
]
```

Endpoint backend:

```text
POST /api/v1/legal/competition
```

Response là array submit tối giản gồm `id`, `question`, `answer`,
`relevant_docs`, `relevant_articles`. Trong UI, bật nút `Competition`, chọn file
`.json`, kết quả sẽ hiện trong đoạn chat hiện tại.

## Dataset và index

Dataset mặc định:

```text
backend/src/categories/crawled_articles_category.json
```

Luồng:

```text
JSON -> PostgreSQL -> backend startup -> Chroma + BM25 -> agent
```

Script import upsert theo `id` và xóa manifest/cache retrieval. Backend sẽ rebuild
Chroma/BM25 ở lần khởi động kế tiếp. Sau đó BM25 được nạp từ
`backend/chroma_db/legal_bm25_cache.json`, nên không tokenize lại ở mỗi lần
restart nếu config và dữ liệu không đổi. Dataset hiện có 13.969 record thuộc 57
category.
