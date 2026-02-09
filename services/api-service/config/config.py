"""
Centralised configuration
────────────────────────────────────────
Load secrets / flags from .env or OS env-vars.

    from config.config import settings
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env once at import time
load_dotenv()


class _Settings(BaseSettings):
    # ─────────── LLM API Keys ───────────
    OPENAI_API_KEY:  str | None = None
    CLAUDE_API_KEY:  str | None = None
    GEMINI_API_KEY:  str | None = None
    GROK_API_KEY:    str | None = None

    # ─────────── LLM Model Settings ───────────
    # OpenAI
    OPENAI_MODEL: str = "gpt-5-mini"
    OPENAI_TEMPERATURE: float = 0.0
    OPENAI_MAX_TOKENS: int = 4000
    
    # Claude
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"
    CLAUDE_TEMPERATURE: float = 0.0
    CLAUDE_MAX_TOKENS: int = 4000
    
    # Gemini
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    GEMINI_TEMPERATURE: float = 0.0
    GEMINI_MAX_TOKENS: int = 4000
    
    # Grok
    GROK_MODEL: str = "grok-beta"
    GROK_BASE_URL: str = "https://api.x.ai/v1"
    GROK_TEMPERATURE: float = 0.0
    GROK_MAX_TOKENS: int = 4000

    # ─────────── Database ───────────
    DATABASE_URL: str = Field(
        "postgresql://user:pass@localhost:5432/secondbrain",
        description="asyncpg-style connection URL",
    )
    
    # Vector Database
    CHROMA_DB_PATH: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "second_brain_knowledge"

    # ─────────── Notion integration ───────────
    NOTION_TOKEN:     str | None = Field(default=os.getenv("NOTION_TOKEN"))
    NOTION_DB_ID: str | None = Field(
        default=os.getenv("NOTION_DB_ID"),  # Database ID
        description="Parent database where new pages will be created",
    )
    NOTION_DATE_COL: str = "Date"

    # ─────────── Server & UI ───────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000          # FastAPI / Uvicorn
    UI_PORT:  int = 3000          # Gradio or static UI
    GRADIO_SHARE: bool = False    # Enable public gradio share link?

    # ─────────── Model config ───────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",            # ← ignore unknown env vars (e.g. POSTGRES_USER)
    )


# Lazily instantiate once;
# any module can `from config.config import settings`
@lru_cache(maxsize=1)
def _get_settings() -> _Settings:
    return _Settings()


settings: _Settings = _get_settings()
