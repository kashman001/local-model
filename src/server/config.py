"""Server configuration via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOCAL_MODEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend: Literal["mlx", "vllm"] = Field(default="mlx")
    default_model: str = Field(default="mlx-community/Llama-3.1-8B-Instruct-4bit")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8080)
    db_path: str = Field(default="data/history.db")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    models_dir: str = Field(default="models")

    @property
    def db_path_resolved(self) -> Path:
        return Path(self.db_path).resolve()
