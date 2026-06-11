"""Cấu hình ứng dụng đọc từ ``backend/config.yaml`` và biến môi trường.

File này là nơi gom toàn bộ cấu hình runtime: FastAPI, LLM, embedding,
MCP retrieval, short-memory và fallback vector store local. Các class cấu hình dùng Pydantic để:

- validate kiểu dữ liệu ngay khi app khởi động;
- có default rõ ràng khi thiếu config;
- cho phép override bằng biến môi trường dạng ``SECTION__FIELD=value``;
- tránh truyền dict thô rời rạc khắp codebase.
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

# PRJ_ROOT trỏ tới thư mục backend. Các path tương đối trong config.yaml sẽ được
# resolve dựa trên thư mục này để chạy từ đâu cũng ổn định.
PRJ_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PRJ_ROOT / "config.yaml"


class ConfigModel(BaseModel):
    """BaseModel chung cho các block config con.

    ``extra='ignore'`` giúp config.yaml có thể chứa key mới trong tương lai mà
    code cũ không bị crash. ``populate_by_name=True`` cho phép dùng cả alias
    và tên field Python khi validate.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AppSettings(ConfigModel):
    """Cấu hình host/port mặc định cho FastAPI agent service."""

    host: str = "0.0.0.0"
    port: int = 8000


class LLMSettings(ConfigModel):
    """Cấu hình chat model OpenAI-compatible, thường trỏ tới vLLM local."""

    api_key: str = "sk-1234"
    base_url: str = "http://localhost:8001/v1"
    # AliasChoices cho phép config.yaml dùng ``default_model`` hoặc
    # ``model_name`` mà code vẫn đọc về cùng một field.
    model_name: str = Field(
        "qwen3-8b-fp8",
        validation_alias=AliasChoices("model_name", "default_model"),
    )
    temperature: float = 0.0
    max_tokens: int | None = None


class EmbeddingsSettings(ConfigModel):
    """Cấu hình embedding endpoint OpenAI-compatible."""

    api_key: str = "sk-1234"
    base_url: str = "http://localhost:8002/v1"
    model: str = "bge-m3"


class ShortMemorySettings(ConfigModel):
    """Cấu hình short-memory cho endpoint chat theo session_id.

    Memory này chỉ nằm trong RAM của backend process, dùng để giữ vài lượt gần
    nhất trong cùng một đoạn chat. Nó không thay thế database/checkpoint dài hạn.
    """

    enabled: bool = True
    max_turns: int = 6
    max_chars: int = 4000


class MCPServerSettings(ConfigModel):
    """Một MCP server mà backend có thể gọi tool."""

    url: str
    transport: Literal["http", "streamable_http"] = "http"


class MCPRetrievalSettings(ConfigModel):
    """Cấu hình gọi MCP server cho retrieval bên ngoài backend.

    Backend chỉ cần biết MCP server nào đang chạy. Tên tool là contract cố định
    giữa backend và legal MCP server, không để người dùng phải chỉnh trong YAML.
    """

    enabled: bool = False
    primary_server: str = "legal_retrieval"
    servers: dict[str, MCPServerSettings] = Field(default_factory=dict)
    fallback_to_local: bool = True
    fetch_related: bool = True
    related_top_k: int = 16


class RetrievalSettings(ConfigModel):
    """Chọn cách tạo text đem đi embedding/search trước retrieval."""

    query_mode: Literal["rewrite_query", "hypothetical_answer"] = "rewrite_query"


class QueryRewriteSettings(ConfigModel):
    """Bật/tắt bước LLM rewrite hoặc HyDE trước khi truy hồi."""

    enabled: bool = True
    use_llm: bool = True
    max_variants: int = 3


class VectorStoreSettings(ConfigModel):
    """Cấu hình backend retrieval: lexical, Chroma vector hoặc hybrid."""

    mode: Literal["bm25", "chroma", "hybrid"] = "hybrid"
    persist_directory: Path = Path("./chroma_db")
    default_collection: str = "legal_articles"
    rrf_k: int = 60
    top_k: int = 8

    @model_validator(mode="after")
    def resolve_persist_directory(self):
        """Chuẩn hóa path Chroma sau khi Pydantic parse xong model.

        Người dùng có thể viết ``./chroma_db`` trong YAML. Validator này đổi nó
        thành absolute path dưới thư mục backend để fallback local luôn nhìn đúng
        vị trí vector index.
        """

        if not self.persist_directory.is_absolute():
            self.persist_directory = PRJ_ROOT / self.persist_directory
        return self


class LegalAssistantSettings(ConfigModel):
    """Nhóm cấu hình riêng cho agent pháp lý."""

    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    query_rewrite: QueryRewriteSettings = Field(default_factory=QueryRewriteSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)


class Settings(BaseSettings):
    """Root settings object được inject vào toàn bộ ứng dụng."""

    app: AppSettings = Field(default_factory=AppSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    short_memory: ShortMemorySettings = Field(default_factory=ShortMemorySettings)
    mcp_retrieval: MCPRetrievalSettings = Field(default_factory=MCPRetrievalSettings)
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
        """Quy định thứ tự đọc config.

        Thứ tự này cho phép tham số truyền trực tiếp và biến môi trường ghi đè
        YAML, rất hữu ích khi deploy bằng Docker/Kubernetes.
        """

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Trả về settings đã cache để không parse YAML nhiều lần."""

    return Settings()


# Biến tiện ích cho các module đơn giản cần đọc config trực tiếp.
settings = get_settings()
