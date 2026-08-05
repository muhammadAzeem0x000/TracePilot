from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: str = Field(default="http://localhost:3000")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
