"""Browser chat client settings."""

from __future__ import annotations

import json
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Endpoint(dict):
    """A {name, url} dict."""


class ClientSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOCAL_MODEL_CLIENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    endpoints: list[dict[str, Any]] = Field(
        default_factory=lambda: [{"name": "local", "url": "http://127.0.0.1:8080"}]
    )
    port: int = Field(default=8000)
    host: str = Field(default="127.0.0.1")

    @field_validator("endpoints", mode="before")
    @classmethod
    def _parse(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
