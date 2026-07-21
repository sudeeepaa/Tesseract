"""
Threadline configuration.

All settings are read from environment variables (or a .env file).
The effective_*_backend properties implement the auto-degradation logic:
  • if EXTRACTOR_BACKEND=openai but OPENAI_API_KEY is empty → mock
  • if GRAPH_BACKEND=neo4j  but Neo4j is unreachable           → memory
  • if VECTOR_BACKEND=qdrant but Qdrant is unreachable         → memory
The store-level fallback (neo4j/qdrant) is handled in the store factories,
not here; config just exposes the user's requested backend.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractorBackend(str, Enum):
    openai = "openai"
    gemini = "gemini"
    mock   = "mock"


class GraphBackend(str, Enum):
    neo4j  = "neo4j"
    memory = "memory"


class VectorBackend(str, Enum):
    qdrant = "qdrant"
    memory = "memory"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def fallback_neo4j_user(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map case-insensitively
            username = (
                data.get("NEO4J_USERNAME")
                or data.get("neo4j_username")
                or data.get("NEO4J_USER")
                or data.get("neo4j_user")
            )
            if username:
                data["neo4j_user"] = username
        return data

    # ── LLM ──────────────────────────────────────────────────────────────────
    openai_api_key:      str              = Field(default="", alias="OPENAI_API_KEY")
    openai_model:        str              = "gpt-4o-mini"
    gemini_api_key:      str              = Field(default="", alias="GEMINI_API_KEY")
    gemini_model:        str              = "gemini-1.5-flash"
    extractor_backend:   ExtractorBackend = ExtractorBackend.openai

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    neo4j_uri:      str          = "bolt://localhost:7687"
    neo4j_user:     str          = "neo4j"
    neo4j_password: str          = "threadline_dev"
    graph_backend:  GraphBackend = GraphBackend.neo4j

    # ── Qdrant ───────────────────────────────────────────────────────────────
    qdrant_url:        str          = "http://localhost:6333"
    qdrant_api_key:    str          = ""
    qdrant_collection: str          = "threadline_facts"
    vector_backend:    VectorBackend = VectorBackend.qdrant

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim:   int = 384

    # ── App ──────────────────────────────────────────────────────────────────
    log_level:    str       = "INFO"
    api_host:     str       = "0.0.0.0"
    api_port:     int       = 8000
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    # ── Derived / auto-degradation ────────────────────────────────────────────

    @property
    def effective_extractor_backend(self) -> ExtractorBackend:
        """
        Returns the extractor backend that will actually be used.
        Degrades to mock when the requested backend has no API key.
        """
        if self.extractor_backend == ExtractorBackend.openai and not self.openai_api_key:
            return ExtractorBackend.mock
        if self.extractor_backend == ExtractorBackend.gemini and not self.gemini_api_key:
            return ExtractorBackend.mock
        return self.extractor_backend


# Module-level singleton — import with get_settings() so tests can override.
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def override_settings(new_settings: Settings) -> None:
    """Used in tests to inject a test-specific Settings instance."""
    global _settings
    _settings = new_settings
