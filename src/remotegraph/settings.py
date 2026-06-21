from __future__ import annotations

from pathlib import Path
from typing import Any

import toml
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = REPO_ROOT / "remotegraph.toml"
DEFAULT_BACKEND = "aegra"


class Settings(BaseSettings):
    """LLM connection details, loaded from .env. Model name is never hardcoded."""

    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), extra="ignore")

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str | None = None


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {"active_backend": DEFAULT_BACKEND}
    return toml.load(CONFIG_FILE)


def save_config(config: dict[str, Any]) -> None:
    CONFIG_FILE.write_text(toml.dumps(config))


def get_active_backend() -> str:
    return load_config().get("active_backend", DEFAULT_BACKEND)


def set_active_backend(name: str) -> None:
    config = load_config()
    config["active_backend"] = name
    save_config(config)
