"""Centralised configuration loaded from the project .env file.

Every secret/key the application needs is read here exactly once and exposed
through a cached `Settings` object, so the rest of the code never touches
environment variables directly.
"""

from functools import lru_cache  # Cache the Settings instance so the .env is parsed only once
from pathlib import Path  # Build filesystem paths in an OS-independent way

from pydantic_settings import BaseSettings, SettingsConfigDict  # Typed settings backed by .env

# The project root is two levels up from this file: app/ -> backend/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# The .env file lives at the project root next to the design documents
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Strongly-typed view over the environment variables in `.env`.

    Optional keys default to empty strings; agents that need a missing key
    degrade gracefully (the related parameter is reported as not-measurable).
    """

    # --- LLM providers ---
    gemini_api_key: str = ""  # Google Gemini key (primary AI judgement)
    gemini_model: str = "gemini-3.1-flash-lite-preview"  # Gemini model id used for all judgement
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"  # OpenAI-compatible endpoint
    openai_api_key: str = ""  # OpenAI key (ChatGPT-style citation checks)

    # --- Google data + performance APIs ---
    google_api_key: str = ""  # PageSpeed Insights + Knowledge Graph
    google_application_credentials: str = ""  # Path to the GA4/GSC service-account JSON (optional fallback)
    google_oauth_client_secrets: str = ""  # OAuth desktop-client JSON from Google Cloud Console
    google_oauth_token_path: str = ""  # Saved OAuth refresh token (default: secrets/google-oauth-token.json)
    google_cloud_project: str = ""  # GCP project id (informational)

    # --- GEO external APIs ---
    serper_api_key: str = ""  # Serper web search (press mentions, awards)
    perplexity_api_key: str = ""  # Perplexity Sonar citations
    serpapi_api_key: str = ""  # SerpApi Google AI Overview citations
    firecrawl_api_key: str = ""  # Firecrawl render/extract fallback
    x_bearer_token: str = ""  # X (Twitter) brand-mention search
    x_api_base_url: str = "https://api.x.com/2"  # X API base URL

    # --- Crawl behaviour tunables (sensible defaults; override via .env) ---
    crawl_timeout_seconds: float = 20.0  # Per-request timeout for page/API fetches
    crawl_max_internal_pages: int = 50  # Upper bound on pages pulled during the shallow internal crawl
    crawl_user_agent: str = "SEO-GEO-Auditor/1.0 (+https://github.com/seo-geo-auditor)"  # UA sent on crawls
    enable_playwright: bool = True  # Whether to render JS with Playwright (off => raw HTML only)

    # Registry mapping connected domains -> { gsc_site_url, ga4_property_id }
    connected_properties_path: str = str(PROJECT_ROOT / "backend" / "connected_properties.json")

    # Full Site Audit trend snapshots (SQLite; one row per audit when metrics change)
    audit_history_db_path: str = str(PROJECT_ROOT / "backend" / "data" / "audit_history.db")
    audit_history_points: int = 12  # Snapshots shown on Full Site Audit trend charts

    # pydantic-settings configuration: read from .env, ignore unknown extra keys
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),  # Absolute path to the .env at the project root
        env_file_encoding="utf-8",  # Encoding of the .env file
        extra="ignore",  # Ignore env vars we do not explicitly model (e.g. ANTHROPIC_API_KEY)
        case_sensitive=False,  # GEMINI_API_KEY and gemini_api_key are treated the same
    )


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide singleton `Settings` instance.

    `lru_cache` guarantees the .env is parsed only on first access.
    """
    return Settings()  # Construct (and cache) the settings on first call
