# Legal Assistant Backend

Backend này phục vụ bài toán truy hồi và hỏi đáp pháp luật tiếng Việt trên **dataset đã xử lý sẵn**. Hệ thống không xử lý raw PDF, không OCR, không chunk markdown trong API chính. Tri thức đầu vào là các record JSON có cấu trúc rõ ràng.

## Luồng Xử Lý Chính

```text
Structured JSON/JSONL dataset
        ↓
POST /api/v1/dataset/import
        ↓
PostgreSQL lưu record gốc + vector_text
        ↓
Vector store index record theo vector_text
        ↓
POST /api/v1/legal/answer hoặc /batch
        ↓
Agent rewrite query hoặc sinh hypothetical answer
        ↓
Hybrid retrieval: BM25-like + Chroma vector search
        ↓
LLM sinh câu trả lời grounded trên điều luật đã truy hồi
        ↓
Response có answer, relevant_docs, relevant_articles
```

## Cấu Hình

File cấu hình chính: `backend/config.yaml`.

Các block quan trọng:

```yaml
llm:
  base_url: http://localhost:8001/v1
  default_model: qwen3-8b-fp8

embeddings:
  base_url: http://localhost:8002/v1
  model: bge-m3

postgres:
  enabled: true
  database_url: postgresql://user:password@localhost:5432/legal_assistant

legal_assistant:
  retrieval:
    query_mode: rewrite_query # rewrite_query | hypothetical_answer
  vector_store:
    mode: hybrid # bm25 | chroma | hybrid
```

## Retrieval Modes

`rewrite_query`: LLM viết lại câu hỏi thành truy vấn ngắn, giàu từ khóa pháp luật hơn. Text rewrite được embed và search.

`hypothetical_answer`: LLM sinh một đoạn trả lời ngắn giả định. Đoạn này thường giàu ngữ nghĩa hơn câu hỏi, nên được embed và search kiểu HyDE.

## Vector Text

Mỗi record được embedding bằng công thức cố định:

```text
doc_type + " " + law_id + " " + law_name
article + " " + article_title
content
```

Ví dụ:

```text
Nghị định 44/2013/NĐ-CP Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động
Điều 1 Phạm vi điều chỉnh
Nghị định này quy định chi tiết thi hành...
```

## API

### Health

```http
GET /health
```

### Import Dataset

```http
POST /api/v1/dataset/import
```

Body có thể truyền `records` trực tiếp:

```json
{
  "database": "labor",
  "save_to_postgres": true,
  "index_vector_store": true,
  "records": [
    {
      "id": "44_2013_ND_CP_Dieu_1",
      "law_id": "44/2013/NĐ-CP",
      "law_name": "Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động",
      "doc_type": "Nghị định",
      "chapter": "Chương I NHỮNG QUY ĐỊNH CHUNG",
      "article": "Điều 1",
      "article_title": "Phạm vi điều chỉnh",
      "content": "Nghị định này quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động.",
      "author": "Chính phủ"
    }
  ]
}
```

Hoặc truyền `input_path` tới file JSON/JSONL local:

```json
{
  "database": "labor",
  "input_path": "/path/to/legal_records.jsonl",
  "save_to_postgres": true,
  "index_vector_store": true
}
```

### Answer

```http
POST /api/v1/legal/answer
```

```json
{
  "id": 1,
  "question": "Phạm vi điều chỉnh của hợp đồng lao động được quy định ở đâu?",
  "databases": ["labor"],
  "top_k": 8,
  "include_debug": true
}
```

Response chính:

```json
{
  "id": 1,
  "question": "...",
  "answer": "...",
  "relevant_docs": ["44/2013/NĐ-CP|..."],
  "relevant_articles": ["44/2013/NĐ-CP|...|Điều 1"],
  "selected_articles": []
}
```

### Batch

```http
POST /api/v1/legal/batch
```

Dùng để chạy tập test và xuất `results.json`.

## Chạy Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Điều kiện cần:

- PostgreSQL chạy và đúng `postgres.database_url`.
- LLM endpoint OpenAI-compatible chạy ở `llm.base_url`.
- Embedding endpoint OpenAI-compatible chạy ở `embeddings.base_url`.

## Cấu Trúc Code

```text
src/
  config.py                  # typed config từ config.yaml
  main.py                    # FastAPI app factory
  dependencies.py            # singleton dependencies cho FastAPI
  routers/
    dataset.py               # import structured records
    legal.py                 # answer/chat/batch
    health.py                # health check
  schemas/
    knowledge.py             # dataset import schema
    legal.py                 # retrieval/answer schema
    api/chat.py              # chat/batch API schema
  services/
    dataset/                 # PostgreSQL + vector indexing service
    vector_store/            # BM25-like, Chroma, hybrid retrieval
    agents/                  # BaseAgent + LegalAssistantAgent
    llm/                     # ChatOpenAI wrapper
    embeddings/              # OpenAIEmbeddings wrapper
```
