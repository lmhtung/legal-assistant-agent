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

## Auto index

Khi startup, backend:

1. đọc PostgreSQL;
2. nhóm record theo category;
3. embed `law_name + "\n" + article_title + "\n" + content`;
4. build/reuse Chroma;
5. nạp BM25 nếu mode là `bm25` hoặc `hybrid`;
6. mở FastAPI sau khi retrieval stores sẵn sàng.

Chroma được rebuild khi manifest, nguồn PostgreSQL, số record hoặc embedding
model thay đổi.

## Docker

Dùng wrapper từ root:

```bash
./compose.sh up -d --build
```

Backend container mount trực tiếp `backend/config.yaml` và dùng host network, do
đó LLM, embedding và PostgreSQL URL trong YAML không bị Compose ghi đè.
