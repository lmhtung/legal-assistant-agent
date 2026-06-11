## Project Architecture

Backend hiện chỉ giữ một luồng tri thức chính:

```text
structured legal dataset -> PostgreSQL -> vector index -> hybrid retrieval -> legal assistant agent -> competition output
```

Không còn OCR, raw PDF parser, markdown folder loader, hay corpus chunking trong API chính.

## Data Model

Dataset đầu vào là record đã xử lý sẵn:

```json
{
  "id": "44_2013_ND_CP",
  "law_id": "44/2013/NĐ-CP",
  "law_name": "Quy định chi tiết thi hành một số điều của Bộ luật lao động về hợp đồng lao động",
  "doc_type": "Nghị định",
  "chapter": "Chương I NHỮNG QUY ĐỊNH CHUNG",
  "article": "Điều 1",
  "article_title": "Phạm vi điều chỉnh",
  "content": "...",
  "author": "Chính phủ"
}
```

Text dùng để embedding được build cố định:

```text
doc_type + " " + law_id + " " + law_name
article + " " + article_title
content
```

## Active Modules

```text
src/
  config.py                         # app, llm, embeddings, postgres, retrieval/vector config
  schemas/
    knowledge.py                    # structured dataset records + import request/response
    legal.py                        # retrieval/query/answer schemas
    api/chat.py                     # chat/batch API schemas
  services/
    dataset/
      repository.py                 # PostgreSQL upsert + schema creation
      service.py                    # import records, save PostgreSQL, index vector store
    vector_store/
      in_memory.py                  # lexical/BM25-like retrieval
      chroma.py                     # vector retrieval via embedding endpoint
      hybrid.py                     # RRF merge of lexical + vector results
      factory.py                    # create bm25/chroma/hybrid store from config
    agents/
      base/                         # BaseAgent, AgentContext, AgentState
      legal_assistant/              # rewrite/HyDE retrieval, grounded answer, submission format
  routers/
    dataset.py                      # POST /api/v1/dataset/import
    legal.py                        # answer/chat/batch endpoints
    health.py                       # GET /health
```

## Retrieval Modes

Configured at `legal_assistant.retrieval.query_mode`:

- `rewrite_query`: LLM rewrites the user question, then the rewritten query is embedded/searched.
- `hypothetical_answer`: LLM creates a short hypothetical answer, then that text is embedded/searched.

Both modes still return grounded answers from retrieved legal records only.

## API

- `POST /api/v1/dataset/import`: import structured records, optionally save to PostgreSQL and index vectors.
- `POST /api/v1/legal/answer`: answer one question, returns competition-compatible fields.
- `POST /api/v1/legal/batch`: answer many questions.
- `POST /api/v1/legal/chat`: chat-style wrapper.
