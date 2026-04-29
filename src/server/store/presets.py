"""Preset DAO — saved system prompts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Preset:
    id: str
    name: str
    system_prompt: str
    default_params: dict[str, Any]
    created_at: datetime


def _row_to_preset(row: sqlite3.Row) -> Preset:
    return Preset(
        id=row["id"],
        name=row["name"],
        system_prompt=row["system_prompt"],
        default_params=json.loads(row["default_params"] or "{}"),
        created_at=row["created_at"],
    )


def create_preset(
    conn: sqlite3.Connection,
    name: str,
    system_prompt: str,
    default_params: dict[str, Any] | None = None,
) -> Preset:
    pid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO preset (id, name, system_prompt, default_params) VALUES (?, ?, ?, ?)",
        (pid, name, system_prompt, json.dumps(default_params or {})),
    )
    conn.commit()
    return get_preset(conn, pid)  # type: ignore[return-value]


def get_preset(conn: sqlite3.Connection, pid: str) -> Preset | None:
    row = conn.execute("SELECT * FROM preset WHERE id = ?", (pid,)).fetchone()
    return _row_to_preset(row) if row else None


def list_presets(conn: sqlite3.Connection) -> list[Preset]:
    rows = conn.execute("SELECT * FROM preset ORDER BY name").fetchall()
    return [_row_to_preset(r) for r in rows]


def delete_preset(conn: sqlite3.Connection, pid: str) -> None:
    conn.execute("DELETE FROM preset WHERE id = ?", (pid,))
    conn.commit()
