from __future__ import annotations

from typing import Optional

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Application settings loaded from environment variables."""

    search_api_key: Optional[str] = Field(None, alias="SEARCH_API_KEY")
    search_api_url: HttpUrl = Field(
        "https://html.duckduckgo.com/html/", alias="SEARCH_API_URL"
    )
    search_provider: str = Field("duckduckgo_html", alias="SEARCH_PROVIDER")
    max_concurrent_per_agent: int = Field(5, alias="MAX_CONCURRENT_PER_AGENT")
    max_queries_per_minute: int = Field(60, alias="MAX_QUERIES_PER_MIN")
    request_timeout_seconds: int = Field(15, alias="REQUEST_TIMEOUT_SECONDS")
    metadata_retention_days: int = Field(30, alias="METADATA_RETENTION_DAYS")
    enable_tracing: bool = Field(False, alias="ENABLE_TRACING")
    use_stub_data: bool = Field(False, alias="USE_STUB_DATA")
    enable_query_cache: bool = Field(True, alias="ENABLE_QUERY_CACHE")
    cache_ttl_seconds: int = Field(600, alias="CACHE_TTL_SECONDS")
    search_user_agent: str = Field(
        "Mozilla/5.0 (compatible; MCPWebSearch/0.1; +https://example.com/bot)",
        alias="SEARCH_USER_AGENT",
    )
    search_language: str = Field("us-en", alias="SEARCH_LANGUAGE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @model_validator(mode="after")
    def default_stub_when_missing_key(self) -> "AppConfig":
        if (
            not self.search_api_key
            and self.search_provider in {"bing", "bing_api"}
        ):
            self.use_stub_data = True
        return self
