"""Startup capability detection for backends."""

from __future__ import annotations

import importlib
import platform


class CapabilityError(RuntimeError):
    """Raised at startup when a required runtime capability is missing."""


def check_mlx() -> None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise CapabilityError(
            "MLX backend unavailable: requires Apple Silicon "
            f"(got {platform.system()}/{platform.machine()})."
        )
    try:
        importlib.import_module("mlx")
    except ImportError as e:
        raise CapabilityError(
            "MLX backend unavailable: `mlx` package not importable. "
            "Run `uv sync` on an Apple Silicon Mac."
        ) from e


def check_vllm() -> None:
    try:
        importlib.import_module("vllm")
    except ImportError as e:
        raise CapabilityError(
            "vLLM backend unavailable: `vllm` package not importable. "
            "Install with `uv sync --extra vllm` on a CUDA host."
        ) from e
