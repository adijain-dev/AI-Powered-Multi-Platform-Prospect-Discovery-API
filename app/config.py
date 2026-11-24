import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application Settings and Configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server Configuration
    HOST: str = Field(default="0.0.0.0", description="Server host interface")
    PORT: int = Field(default=4000, description="Server port (required: 4000)")
    ENVIRONMENT: str = Field(default="development", description="Environment mode: development / production")
    DEBUG: bool = Field(default=False, description="Debug mode")

    # LLM Provider Configuration
    # Supported: "gemini", "openai", "claude", "groq", "heuristic"
    LLM_PROVIDER: str = Field(default="gemini", description="Primary LLM provider")
    LLM_FALLBACK_PROVIDER: str = Field(default="heuristic", description="Fallback LLM provider")

    # Google Gemini Settings
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API Key")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash", description="Gemini model name")

    # OpenAI Settings
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API Key")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI model name")

    # Anthropic Settings
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API Key")
    ANTHROPIC_MODEL: str = Field(default="claude-3-5-haiku-latest", description="Anthropic model name")

    # Groq Settings (optional high-speed fallback)
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API Key")
    GROQ_MODEL: str = Field(default="qwen/qwen3.8-27b", description="Groq model name")

    # Search Provider Keys (Optional: if empty, DuckDuckGo zero-config search is used)
    SERPER_API_KEY: Optional[str] = Field(default=None, description="Google Serper API Key")
    SERPAPI_API_KEY: Optional[str] = Field(default=None, description="SerpApi Key")
    GOOGLE_SEARCH_API_KEY: Optional[str] = Field(default=None, description="Google Custom Search API Key")
    GOOGLE_SEARCH_CX: Optional[str] = Field(default=None, description="Google Custom Search Engine ID")
    TAVILY_API_KEY: Optional[str] = Field(default=None, description="Tavily Search API Key")
    BING_SEARCH_API_KEY: Optional[str] = Field(default=None, description="Bing Web Search API Key")

    # Discovery & Scraping Settings
    MAX_PROSPECTS_PER_QUERY: int = Field(default=15, description="Maximum prospects to return")
    SEARCH_RESULTS_PER_PLATFORM: int = Field(default=6, description="Search results to fetch per platform")
    HTTP_TIMEOUT_SECONDS: float = Field(default=10.0, description="HTTP request timeout in seconds")
    MAX_PARALLEL_SEARCHES: int = Field(default=5, description="Concurrent platform searches")

    # Caching Settings
    ENABLE_CACHE: bool = Field(default=True, description="Enable in-memory LRU/TTL caching")
    CACHE_TTL_SECONDS: int = Field(default=3600, description="Cache time to live in seconds")


settings = Settings()
