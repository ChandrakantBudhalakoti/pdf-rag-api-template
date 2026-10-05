"""Centralized configuration.

All settings come from environment variables (optionally loaded from a `.env`
file in the project root). Nothing secret is ever printed: `Settings.__repr__`
masks the API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULTS = {
    "AI_PROVIDER": "openai",
    "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost:5432/ragdb",
    "CHUNK_SIZE": "1000",
    "CHUNK_OVERLAP": "200",
    "COLLECTION_NAME": "rag_documents",
    "TOP_K": "4",
    "LLM_REQUESTS_PER_MINUTE": "0",
    "PDF_DIR": "data/pdfs",
    "MAX_UPLOAD_MB": "20",
}


# Default models per provider, used when EMBEDDING_MODEL / LLM_MODEL are empty.
PROVIDER_DEFAULTS = {
    "openai": {"EMBEDDING_MODEL": "text-embedding-3-small", "LLM_MODEL": "gpt-4o-mini"},
    "gemini": {"EMBEDDING_MODEL": "gemini-embedding-001", "LLM_MODEL": "gemini-2.5-flash"},
}
# Model-name prefixes that clearly belong to the *other* provider (catches half-edited .env files).
_FOREIGN_MODEL_PREFIXES = {
    "openai": ("gemini", "text-embedding-004", "embedding-001"),
    "gemini": ("gpt-", "text-embedding-3", "text-embedding-ada", "o1", "o3", "o4"),
}
API_KEY_HELP = {
    "openai": "OPENAI_API_KEY (get one at https://platform.openai.com/api-keys)",
    "gemini": "GOOGLE_API_KEY (get one at https://aistudio.google.com/apikey)",
}


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


def _parse_int(name: str, raw: str) -> int:
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None


def validate_chunk_params(chunk_size: int, chunk_overlap: int) -> None:
    """Chunk size must be positive; overlap must be >= 0 and smaller than size."""
    if chunk_size <= 0:
        raise ConfigError(f"CHUNK_SIZE must be positive, got {chunk_size}")
    if chunk_overlap < 0:
        raise ConfigError(f"CHUNK_OVERLAP must be non-negative, got {chunk_overlap}")
    if chunk_overlap >= chunk_size:
        raise ConfigError(
            f"CHUNK_OVERLAP ({chunk_overlap}) must be smaller than CHUNK_SIZE ({chunk_size})"
        )


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = field(repr=False)
    database_url: str
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    llm_model: str
    collection_name: str
    top_k: int
    pdf_dir: Path
    provider: str = "openai"
    google_api_key: str = field(default="", repr=False)
    llm_requests_per_minute: int = 0  # 0 = no client-side limit
    service_api_key: str = field(default="", repr=False)  # protects the HTTP API; empty = no auth
    max_upload_mb: int = 20

    def __post_init__(self) -> None:
        if self.provider not in PROVIDER_DEFAULTS:
            raise ConfigError(
                f"AI_PROVIDER must be one of {sorted(PROVIDER_DEFAULTS)}, got {self.provider!r}"
            )
        validate_chunk_params(self.chunk_size, self.chunk_overlap)
        if self.top_k <= 0:
            raise ConfigError(f"TOP_K must be positive, got {self.top_k}")
        if self.llm_requests_per_minute < 0:
            raise ConfigError(f"LLM_REQUESTS_PER_MINUTE must be >= 0, got {self.llm_requests_per_minute}")
        if self.max_upload_mb <= 0:
            raise ConfigError(f"MAX_UPLOAD_MB must be positive, got {self.max_upload_mb}")
        if not self.database_url:
            raise ConfigError("DATABASE_URL is not set. See .env.example.")
        if not self.database_url.startswith("postgresql"):
            raise ConfigError("DATABASE_URL must be a PostgreSQL URL (postgresql+psycopg://...)")
        for name, value in (
            ("EMBEDDING_MODEL", self.embedding_model),
            ("LLM_MODEL", self.llm_model),
            ("COLLECTION_NAME", self.collection_name),
        ):
            if not value:
                raise ConfigError(f"{name} must not be empty")
        for name, value in (("EMBEDDING_MODEL", self.embedding_model), ("LLM_MODEL", self.llm_model)):
            if value.lower().startswith(_FOREIGN_MODEL_PREFIXES[self.provider]):
                raise ConfigError(
                    f"{name}={value!r} is not a {self.provider} model but AI_PROVIDER={self.provider}. "
                    f"Use e.g. {name}={PROVIDER_DEFAULTS[self.provider][name]} "
                    "(or leave it empty to use the provider default)."
                )

    @property
    def api_key(self) -> str:
        """API key of the active provider."""
        return self.google_api_key if self.provider == "gemini" else self.openai_api_key

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def require_api_key(self) -> None:
        """Call before any step that talks to the AI provider (embeddings or chat)."""
        if not self.api_key:
            raise ConfigError(
                f"AI_PROVIDER is {self.provider} but {API_KEY_HELP[self.provider]} is not set. "
                "Add it to .env (see .env.example)."
            )

    @property
    def psycopg_url(self) -> str:
        """DATABASE_URL without the SQLAlchemy driver suffix, for direct psycopg use."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, load_dotenv_file: bool = True) -> "Settings":
        """Build settings from `env` (defaults to os.environ, after loading .env)."""
        if env is None:
            if load_dotenv_file:
                # Real environment variables win over values in .env.
                load_dotenv(PROJECT_ROOT / ".env", override=False)
            env = dict(os.environ)

        def get(name: str) -> str:
            value = env.get(name)
            if value is None or value.strip() == "":
                return DEFAULTS.get(name, "")
            return value.strip()

        provider = get("AI_PROVIDER").lower()
        provider_defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])

        pdf_dir = Path(get("PDF_DIR"))
        if not pdf_dir.is_absolute():
            pdf_dir = PROJECT_ROOT / pdf_dir

        return cls(
            openai_api_key=env.get("OPENAI_API_KEY", "").strip(),
            database_url=get("DATABASE_URL"),
            chunk_size=_parse_int("CHUNK_SIZE", get("CHUNK_SIZE")),
            chunk_overlap=_parse_int("CHUNK_OVERLAP", get("CHUNK_OVERLAP")),
            embedding_model=get("EMBEDDING_MODEL") or provider_defaults["EMBEDDING_MODEL"],
            llm_model=get("LLM_MODEL") or provider_defaults["LLM_MODEL"],
            collection_name=get("COLLECTION_NAME"),
            top_k=_parse_int("TOP_K", get("TOP_K")),
            pdf_dir=pdf_dir,
            provider=provider,
            llm_requests_per_minute=_parse_int("LLM_REQUESTS_PER_MINUTE", get("LLM_REQUESTS_PER_MINUTE")),
            google_api_key=(env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY") or "").strip(),
            service_api_key=env.get("SERVICE_API_KEY", "").strip(),
            max_upload_mb=_parse_int("MAX_UPLOAD_MB", get("MAX_UPLOAD_MB")),
        )
