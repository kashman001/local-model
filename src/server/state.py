"""Container for app-scoped objects (registry, db connection, etc.)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from server.registry import ModelRegistry


@dataclass(slots=True)
class AppState:
    registry: ModelRegistry
    db: sqlite3.Connection
