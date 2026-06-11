# Legal Assistant Backend

Backend được chia thành 2 luồng, nhưng chỉ có agent là HTTP service:

```text
Offline Data Builder -> structured dataset -> PostgreSQL + vector index
Agent Service        -> question -> rewrite/HyDE -> retrieval -> grounded answer
```

Data flow và prompt flow tách biệt. Data builder tự xử lý import/index dữ liệu, còn agent service chỉ đọc kho đã được build để trả lời.

## 1. Offline Data Builder

Data builder không chạy port riêng và không expose endpoint. Nó là job nội bộ dùng khi cần thêm hoặc rebuild dữ liệu.

Nhiệm vụ:

- Đọc structured legal dataset dạng JSON/JSONL.
- Lưu record vào PostgreSQL nếu `postgres.enabled=true`.
- Tạo vector index từ `vector_text`.
- Chia dữ liệu theo `database` logic, ví dụ `labor`, `civil`, `criminal`.

Chạy import:

```bash
cd backend
PYTHONPATH=. python scripts/import_dataset.py --database labor --input data/labor.jsonl
```

Nếu chỉ muốn build vector hoặc chỉ muốn lưu PostgreSQL:

```bash
PYTHONPATH=. python scripts/import_dataset.py --database labor --input data/labor.jsonl --skip-postgres
PYTHONPATH=. python scripts/import_dataset.py --database labor --input data/labor.jsonl --skip-vector
```

PostgreSQL dùng Docker như bạn đang chạy thì chỉ cần cấu hình đúng `postgres.database_url`, ví dụ port mapping `0.0.0.0:25432->5432/tcp` tương ứng với:

```yaml
postgres:
  enabled: true
  database_url: postgresql://user:password@localhost:25432/legal_assistant
```

`25432` ở đây là port PostgreSQL, không phải port service data.

## 2. Agent Service

Agent Service là FastAPI runtime, mặc định port `8000`.

Nhiệm vụ:

- Nhận câu hỏi người dùng.
- Rewrite query hoặc sinh hypothetical answer theo config.
- Search các vector store đã build theo `databases` được chọn.
- Prompt LLM với các điều luật đã tìm được.
- Trả `answer`, `relevant_docs`, `relevant_articles` theo format bài thi.

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

## Config

File: `backend/config.yaml`.

```yaml
legal_assistant:
  retrieval:
    query_mode: rewrite_query # rewrite_query | hypothetical_answer
  query_rewrite:
    enabled: true
    use_llm: true
    max_variants: 3
  vector_store:
    mode: hybrid # bm25 | chroma | hybrid
    persist_directory: ./chroma_db
    default_collection: legal_articles
    top_k: 8
```

`query_mode` có 2 mode:

- `rewrite_query`: LLM viết lại câu hỏi thành truy vấn pháp lý ngắn, rồi embedding truy vấn đó để search.
- `hypothetical_answer`: LLM sinh câu trả lời ngắn dự kiến, rồi embedding đoạn trả lời đó để search. Cách này giống HyDE, hữu ích khi câu hỏi người dùng quá đời thường.

## Dataset Record

```json
{
  "id": "44_2013_ND_CP_Dieu_1",
  "law_id": "44/2013/NĐ-CP",
  "law_name": "Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động",
  "doc_type": "Nghị định",
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

`extra` là các điều luật liên quan. Khi search trúng record, agent dùng `extra` để mở rộng `relevant_articles` và `relevant_docs` một cách deterministic, không để LLM tự đoán nguồn.

## Vector Text

Mỗi record được embedding bằng:

```text
doc_type + " " + law_id + " " + law_name
article + " " + article_title
content
```

`extra` không được embed. Nó chỉ dùng để mở rộng danh sách điều luật liên quan sau retrieval.
