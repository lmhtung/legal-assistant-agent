## Project Architecture

Mục tiêu của backend là xây một legal assistant có retrieval mạnh, có căn cứ rõ ràng, và xuất được đúng format `results.json` cho cuộc thi.

```text
src/
  config.py                         # Typed settings, database registry config, MCP config
  schemas/
    legal.py                        # LegalArticle, retrieval result, answer format, competition record
    ingestion.py                    # Input file/database registration/ingestion result schemas
    api/chat.py                     # Chat + batch competition API schemas
  services/
    ingestion/
      document_preprocessor.py      # PDF text/PDF OCR/Markdown/Text -> Markdown
      article_parser.py             # Markdown -> LegalArticle chunks by Điều X
      pipeline.py                   # Preprocess + parse + add articles to vector registry
    vector_store/
      base.py                       # LegalVectorStore protocol + VectorStoreRegistry
      in_memory.py                  # Local lexical BM25-like store for development/testing
    agents/
      base/
        context.py                  # AgentContext: session, databases, top_k, MCP flags
        state.py                    # AgentState shared by graph nodes
      legal_assistant/
        prompt.py                   # Grounded answer prompt with citation rules
        tools.py                    # search_legal_articles tool factory
        agent.py                    # LangGraph agent with fallback when langgraph is unavailable
```

## Runtime Flow

1. Register or choose a database, for example `default`, `enterprise_law`, `tax`, `labor`.
2. Ingest input documents:
   - `.md` is used directly.
   - text PDF is converted to Markdown with `pypdf` when available.
   - scanned PDF falls back to MinerU OCR and then Markdown.
3. Parse Markdown into `LegalArticle` records split by `Điều X`.
4. Add articles into a registered vector store.
5. Agent receives a question and calls `search_legal_articles`.
6. Retrieval returns grounded candidates with `law_id`, `law_name`, `article`, score, source.
7. Answer node generates a grounded Vietnamese answer.
8. Format node emits competition fields:
   - `answer`
   - `relevant_docs`: `law_id|law_name`
   - `relevant_articles`: `law_id|law_name|Điều X`

## Extension Points

- Replace `InMemoryLegalStore` with Chroma/Qdrant/FAISS by implementing `LegalVectorStore`.
- Add a new database by registering another store in `VectorStoreRegistry` or config `legal_assistant.vector_store.databases`.
- Add MCP search by writing an MCP-backed store/tool that returns the same `RetrievedCandidate` schema.
- Improve ranking with hybrid retrieval: BM25 + embedding similarity + reranker + RRF.
- Improve answer quality by passing `LLMClient` into `LegalAssistantAgent(llm=...)`.
