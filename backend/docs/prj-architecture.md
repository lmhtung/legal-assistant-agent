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

```