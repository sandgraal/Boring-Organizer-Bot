"""Configuration management for B.O.B.

Loads configuration from:
1. bob.yaml in current directory
2. ~/.config/bob/bob.yaml
3. Environment variables (BOB_* prefix)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: Path = Field(default=Path("./data/bob.db"))
    wal_mode: bool = True


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""

    model: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    device: str = "cpu"
    batch_size: int = 32


class ChunkingConfig(BaseModel):
    """Chunking configuration."""

    target_size: int = 512
    overlap: int = 50
    min_size: int = 100
    max_size: int = 1024


class DefaultsConfig(BaseModel):
    """Default values."""

    project: str = "main"
    language: str = "en"
    top_k: int = 5


class DateConfidenceConfig(BaseModel):
    """Date confidence thresholds."""

    outdated_threshold_days: int = 180
    high_max_days: int = 30
    medium_max_days: int = 90


class SearchConfig(BaseModel):
    """Search and retrieval configuration."""

    # Hybrid search settings
    hybrid_enabled: bool = False
    vector_weight: float = 0.7
    keyword_weight: float = 0.3

    # BM25 parameters
    bm25_k1: float = 1.2
    bm25_b: float = 0.75

    # Metadata boosts
    recency_boost_enabled: bool = False
    recency_half_life_days: int = 180


class HealthConfig(BaseModel):
    """Health dashboard thresholds."""

    low_volume_document_threshold: int = 5
    low_hit_rate_threshold: float = 0.4
    search_window_hours: int = 168
    min_searches_for_rate: int = 5
    staleness_buckets_days: list[int] = Field(default_factory=lambda: [90, 180, 365])


class PathsConfig(BaseModel):
    """Paths configuration."""

    ignore: list[str] = Field(
        default_factory=lambda: [
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            ".env",
            "*.pyc",
            ".DS_Store",
        ]
    )
    extensions: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "markdown": [".md", ".markdown"],
            "pdf": [".pdf"],
            "word": [".docx"],
            "excel": [".xlsx", ".xls"],
            "recipe": [".recipe.yaml", ".recipe.json"],
        }
    )
    vault: Path = Field(default=Path("./vault"))


class PermissionsConfig(BaseModel):
    """Permission configuration for vault writes and optional connectors."""

    default_scope: int = Field(
        default=3,
        description="Current scope level; template writes require level 3",
    )
    enabled_connectors: dict[str, bool] = Field(
        default_factory=lambda: {"calendar_import": False, "browser_saves": False},
        description="Toggles for opt-in connectors (calendar, browser saves)",
    )
    allowed_vault_paths: list[str] = Field(
        default_factory=lambda: [
            "vault/routines",
            "vault/decisions",
            "vault/trips",
            "vault/meetings",
            "vault/manual-saves",
        ],
        description="Directories that template writes may target",
    )


class GitDocsConfig(BaseModel):
    """Git documentation settings."""

    include_paths: list[str] = Field(
        default_factory=lambda: ["README.md", "README", "docs/", "documentation/"]
    )
    default_branch: str | None = None
    clone_depth: int = 1


class LLMConfig(BaseModel):
    """Optional LLM configuration."""

    enabled: bool = False
    model_path: Path | None = None
    context_size: int = 4096
    temperature: float = 0.7
    max_tokens: int = 512


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Path | None = None


class Config(BaseSettings):
    """Main configuration for B.O.B."""

    model_config = SettingsConfigDict(
        env_prefix="BOB_",
        env_nested_delimiter="__",
    )

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    date_confidence: DateConfidenceConfig = Field(default_factory=DateConfidenceConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    git_docs: GitDocsConfig = Field(default_factory=GitDocsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def find_config_file() -> Path | None:
    """Find the configuration file.

    Searches in order:
    1. ./bob.yaml
    2. ~/.config/bob/bob.yaml
    """
    locations = [
        Path.cwd() / "bob.yaml",
        Path.home() / ".config" / "bob" / "bob.yaml",
    ]

    for path in locations:
        if path.exists():
            return path

    return None


def load_config() -> Config:
    """Load configuration from file and environment.

    Returns:
        Config: The loaded configuration.
    """
    config_data: dict[str, Any] = {}

    # Load from file if exists
    config_file = find_config_file()
    if config_file:
        with open(config_file) as f:
            config_data = yaml.safe_load(f) or {}

    # Environment overrides for common settings
    env_overrides = {
        "BOB_DB_PATH": ("database", "path"),
        "BOB_EMBEDDING_MODEL": ("embedding", "model"),
        "BOB_DEFAULT_PROJECT": ("defaults", "project"),
    }

    for env_var, path in env_overrides.items():
        value = os.environ.get(env_var)
        if value:
            section, key = path
            if section not in config_data:
                config_data[section] = {}
            config_data[section][key] = value

    return Config(**config_data)


# Global config instance (lazy loaded)
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        Config: The configuration instance.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
