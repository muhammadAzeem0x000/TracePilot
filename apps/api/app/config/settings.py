from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DATABASE_EMBEDDING_DIMENSIONS = 768


class Settings(BaseSettings):
    """Environment-backed API settings.

    Supabase values are required when an incident repository is constructed, while
    `/health` intentionally remains available for diagnosing missing configuration.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str | None = None
    supabase_key: str | None = None
    github_token: str | None = None
    github_api_url: str = "https://api.github.com"
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "DEEPSEEK_API"),
    )
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    max_tool_calls: int = Field(default=6, ge=1, le=20)
    final_output_retries: int = Field(default=1, ge=0, le=3)
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_API_KEY", "GEMINI_API_KEY"),
    )
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = Field(default=DATABASE_EMBEDDING_DIMENSIONS, ge=128, le=2_000)
    embedding_base_url: str = "https://generativelanguage.googleapis.com"
    knowledge_chunk_max_tokens: int = Field(default=350, ge=100, le=1_000)
    knowledge_chunk_overlap_tokens: int = Field(default=50, ge=0, le=250)
    knowledge_context_budget_tokens: int = Field(default=1_800, ge=300, le=8_000)
    knowledge_candidate_limit: int = Field(default=12, ge=5, le=30)
    knowledge_rerank_enabled: bool = True
    cors_origins: str = Field(default="http://localhost:3000")

    @model_validator(mode="after")
    def validate_knowledge_configuration(self) -> "Settings":
        if self.embedding_dimensions != DATABASE_EMBEDDING_DIMENSIONS:
            raise ValueError(
                "EMBEDDING_DIMENSIONS must match the database vector dimension "
                f"({DATABASE_EMBEDDING_DIMENSIONS})"
            )
        if self.knowledge_chunk_overlap_tokens >= self.knowledge_chunk_max_tokens:
            raise ValueError(
                "KNOWLEDGE_CHUNK_OVERLAP_TOKENS must be smaller than "
                "KNOWLEDGE_CHUNK_MAX_TOKENS"
            )
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def require_supabase(self) -> tuple[str, str]:
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_KEY", self.supabase_key),
            )
            if not value
        ]
        if missing:
            names = ", ".join(missing)
            raise RuntimeError(f"Missing required incident storage configuration: {names}")
        assert self.supabase_url is not None
        assert self.supabase_key is not None
        return self.supabase_url.rstrip("/"), self.supabase_key

    def require_github(self) -> tuple[str, str]:
        if not self.github_token:
            raise RuntimeError("Missing required GitHub configuration: GITHUB_TOKEN")
        return self.github_api_url.rstrip("/"), self.github_token

    def require_llm(self) -> tuple[str, str, str]:
        if not self.llm_api_key:
            raise RuntimeError("Missing required LLM configuration: LLM_API_KEY")
        return self.llm_base_url.rstrip("/"), self.llm_api_key, self.llm_model

    def require_embedding(self) -> tuple[str, str, str, int]:
        if not self.embedding_api_key:
            raise RuntimeError("Missing required embedding configuration: EMBEDDING_API_KEY")
        return (
            self.embedding_base_url.rstrip("/"),
            self.embedding_api_key,
            self.embedding_model,
            self.embedding_dimensions,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
