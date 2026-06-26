# Legal Assistant Backend

Backend chỉ đọc cấu hình từ `config.yaml`. Biến môi trường không ghi đè YAML.

## Chạy local

```bash
uv sync --frozen
uv run python scripts/run_backend.py --reload
```

Launcher đọc:

```yaml
app:
  host: 0.0.0.0
  port: 8025
```

## PostgreSQL và dataset

```bash
# Từ root project
./compose.sh up -d postgres

# Trong backend/
uv run python scripts/load_postgres.py --truncate
```

Dataset mặc định là `src/categories/crawled_articles_category.json`.

## Competition mode

Trong `config.yaml`:

```yaml
legal_assistant:
  chat:
    streaming: true
    token_streaming: true
  competition:
    enabled: false
    max_concurrency: 4
    save_outputs: true
    output_dir: ./outputs
```

`chat.streaming=true` là mode mặc định cho UI/chat client. Khi tắt, UI dùng
endpoint `/api/v1/legal/chat` thay vì `/api/v1/legal/chat/stream`.
`chat.token_streaming=true` cho phép node trả lời stream token-by-token qua SSE,
nên người dùng thấy câu trả lời xuất hiện ngay trong bubble chat.

Khi bật `true`, agent bỏ qua Intent và luôn chạy legal RAG. `max_concurrency` giới hạn số câu chạy song song; mặc định là 4. Endpoint nhận trực
tiếp JSON array tập test:

```text
POST /api/v1/legal/competition          # trả JSON cuối
POST /api/v1/legal/competition/stream   # stream tiến độ từng câu cho UI
```

Response trả array tối giản theo format submit: `id`, `question`, `answer`,
`relevant_docs`, `relevant_articles`. Nếu `save_outputs=true`, backend tự lưu kết quả vào `backend/outputs/competition_<timestamp>_<status>.json` khi hoàn tất hoặc khi lỗi.

Chạy không cần UI, phù hợp tmux:

```bash
uv run python scripts/run_competition.py --file path/to/test.json
```

Script ghi `competition_<run_id>_running.json` sau mỗi câu, và luôn ghi
`outputs/report.log`. Khi kết thúc/lỗi/dừng giữa chừng, script ghi file final
`competition_<run_id>_success.json` hoặc `competition_<run_id>_error.json`.

## Auto index

Khi startup, backend:

1. đọc PostgreSQL;
2. nhóm record theo category;
3. embed `law_name + "\n" + article_title + "\n" + content`;
4. build/reuse Chroma;
5. nạp BM25 từ cache nếu mode là `bm25` hoặc `hybrid`;
6. nếu cache BM25 chưa có hoặc lệch config/data thì tokenize và ghi cache một lần;
7. mở FastAPI sau khi retrieval stores sẵn sàng.

Chroma được rebuild khi manifest, nguồn PostgreSQL, số record hoặc embedding
model thay đổi. BM25 dùng `legal_bm25_cache.json` trong `chroma_db`, nên không
chạy lại tokenizer tiếng Việt ở mỗi lần backend restart. Cache BM25 chỉ rebuild
khi dataset/PostgreSQL source, tokenizer hoặc tham số BM25 thay đổi.

## Docker

Dùng wrapper từ root:

```bash
./compose.sh up -d --build
```

Backend container mount trực tiếp `backend/config.yaml` và dùng host network, do
đó LLM, embedding và PostgreSQL URL trong YAML không bị Compose ghi đè.
