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
    """Base class for nested config sections loaded from YAML."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AppSettings(ConfigModel):
    host: str = "0.0.0.0"
    port: int = 8000


class LLMSettings(ConfigModel):
    api_key: str = "sk-1234"
    base_url: str = "http://localhost:8001/v1"
    model_name: str = Field(
        "qwen3-8b-fp8",
        validation_alias=AliasChoices("model_name", "default_model"),
    )
    temperature: float = 0.0
    max_tokens: int | None = None


class EmbeddingsSettings(ConfigModel):
    api_key: str = "sk-1234"
    base_url: str = "http://localhost:8002/v1"
    model: str = "bge-m3"


class OCRSettings(ConfigModel):
    api_key: str = "sk-1234"
    base_url: str = "http://localhost:8003/v1"
    model: str = "mineru-ocr"
    output_dir: Path = PRJ_ROOT / "outputs" / "mineru"

    @model_validator(mode="after")
    def resolve_output_dir(self):
        if not self.output_dir.is_absolute():
            self.output_dir = PRJ_ROOT / self.output_dir
        return self


class CheckpointSettings(ConfigModel):
    backend: Literal["memory", "postgres"] = "memory"
    database_url: str | None = None
    pool_min_size: int = 2
    pool_max_size: int = 10
    pool_max_idle: float = 300.0
    pool_timeout: float = 30.0


class RegisteredDatabaseSettings(ConfigModel):
    name: str
    description: str = ""
    document_types: list[str] = Field(default_factory=list)
    enabled: bool = True
    mcp_server: str | None = None


class VectorStoreSettings(ConfigModel):
    mode: Literal["bm25", "chroma", "hybrid"] = "hybrid"

    bm25_index_field: str = "content"
    bm25_k1: float = 2.0
    bm25_b: float = 1.0
    bm25_epsilon: float = 0.5

    chroma_mode: Literal["local", "remote"] = "local"
    persist_directory: Path = Path("./chroma_db")
    host: str = "localhost"
    port: int = 8000
    default_collection: str = "legal_articles"

    rrf_k: int = 60
    top_k: int = 8
    databases: dict[str, RegisteredDatabaseSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    def resolve_persist_directory(self):
        if not self.persist_directory.is_absolute():
            self.persist_directory = PRJ_ROOT / self.persist_directory
        return self


class MCPServerSettings(ConfigModel):
    url: str
    transport: Literal["http", "stdio", "sse"] = "http"


class MCPSettings(ConfigModel):
    enabled: bool = False
    servers: dict[str, MCPServerSettings] = Field(default_factory=dict)


class LegalAssistantSettings(ConfigModel):
    checkpoint: CheckpointSettings = Field(default_factory=CheckpointSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    ocr: OCRSettings = Field(default_factory=OCRSettings)
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

    @property
    def mineru(self) -> OCRSettings:
        return self.ocr

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
