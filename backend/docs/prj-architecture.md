## Project Architecture
```
src/
  main.py                   # create_app() factory
  config.py                 # Settings, AgentConfig, LLMSettings, etc.
  lifecycle.py              # 
  core/                     # Base comon process
  routers/                  # FastAPI route handlers
  schemas/                  # Pydantic models (api/, enums.py)
  services/
    agents/                 # LangGraph agents
      base/                 # BaseAgent, AgentState
      legal-assistant/      # LegalAgent, LegalAgentState, LegalTools, LegalPrompt
      factory.py            # Agent factory
      registry.py           # AgentRegistry
    llm/client.py           # LLMClient (wraps ChatOpenAI)
    embeddings/             # EmbeddingsClient (wraps OpenAIEmbeddings)
    checkpoint/             # CheckpointService (memory or postgres)
    vector_store/           # VectorStoreClient (BM25 or Chroma)
    mcp/                    # MCP integration

tests/
  conftest.py               # Root: Settings factory, image fixtures
  fixtures/                 # sample_data.py (image helpers)
  unit/                     # Pure logic tests — no network, patches at boundary
    conftest.py             # _FakeChatModel, patch_chat_openai, patch_openai_embeddings,
                            # llm_client, embeddings_client, checkpoint_memory, bm25_vector_store
    services/               # Tests for LLMClient, EmbeddingsClient, VectorStoreClient, etc.
    schemas/                # Tests for Pydantic schemas
  integration/              # FastAPI endpoint tests via httpx ASGI transport
    conftest.py             # mock_agent, mock_registry, app (create_app + mock state), async_client
  e2e/                      # Live server tests (E2E_BASE_URL env var)
    conftest.py             # e2e_client (httpx against live server)
```