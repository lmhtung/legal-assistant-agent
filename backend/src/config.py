"""Application configuration loaded from ``backend/config.yaml``.

Only settings required by the structured-dataset pipeline are kept here:
FastAPI app settings, OpenAI-compatible LLM/embedding endpoints, PostgreSQL,
and retrieval/vector-store options.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Tuple, Type

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

PRJ_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PRJ_ROOT / "config.yaml"


class ConfigModel(BaseModel):
    """Base class for nested config blocks.

    ``extra='ignore'`` lets config.yaml contain harmless future keys while the
    code only reads fields explicitly declared here.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AppSettings(ConfigModel):
    """FastAPI host/port settings."""

    host: str = "0.0.0.0"
    port: int = 8000


class LLMSettings(ConfigModel):
    """OpenAI-compatible chat model settings, backed by the local vLLM server."""

    api_key: str = "sk-1234"
    base_url: str = "http://localhost:8001/v1"
    model_name: str = Field(
        "qwen3-8b-fp8",
        validation_alias=AliasChoices("model_name", "default_model"),
    )
    temperature: float = 0.0
    max_tokens: int | None = None


class EmbeddingsSettings(ConfigModel):
    """OpenAI-compatible embedding model settings, backed by the local server."""

    api_key: str = "sk-1234"
    base_url: str = "http://localhost:8002/v1"
    model: str = "bge-m3"


class PostgreSQLSettings(ConfigModel):
    """PostgreSQL storage for structured legal records."""

    enabled: bool = True
    database_url: str = "postgresql://user:password@localhost:5432/legal_assistant"


class RetrievalSettings(ConfigModel):
    """Controls which text is embedded at query time before retrieval."""

    query_mode: Literal["rewrite_query", "hypothetical_answer"] = "rewrite_query"


class QueryRewriteSettings(ConfigModel):
    """Controls the LLM rewrite/HyDE pre-retrieval step."""

    enabled: bool = True
    use_llm: bool = True
    max_variants: int = 3


class VectorStoreSettings(ConfigModel):
    """Vector and hybrid retrieval settings."""

    mode: Literal["bm25", "chroma", "hybrid"] = "hybrid"
    persist_directory: Path = Path("./chroma_db")
    default_collection: str = "legal_articles"
    rrf_k: int = 60
    top_k: int = 8

    @model_validator(mode="after")
    def resolve_persist_directory(self):
        """Resolve a relative Chroma path against the backend directory."""

        if not self.persist_directory.is_absolute():
            self.persist_directory = PRJ_ROOT / self.persist_directory
        return self


class LegalAssistantSettings(ConfigModel):
    """Top-level legal assistant settings."""

    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    query_rewrite: QueryRewriteSettings = Field(default_factory=QueryRewriteSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)


class Settings(BaseSettings):
    """Root settings object used by the application."""

    app: AppSettings = Field(default_factory=AppSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    postgres: PostgreSQLSettings = Field(default_factory=PostgreSQLSettings)
    legal_assistant: LegalAssistantSettings = Field(
        default_factory=LegalAssistantSettings,
        validation_alias=AliasChoices("legal_assistant", "legal-assistant"),
    )

    model_config = SettingsConfigDict(
        yaml_file=CONFIG_FILE,
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Read init/env/dotenv first, then YAML, then file secrets."""

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object for dependency injection."""

    return Settings()


settings = get_settings()
