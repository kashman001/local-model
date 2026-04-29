"""History DAO — Conversation + Message persistence."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Conversation:
    id: str
    title: str
    model_id: str
    preset_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    prompt_tokens: int | None
    completion_tokens: int | None
    tps: float | None
    ttft_ms: float | None
    created_at: datetime


def _row_to_conversation(row: sqlite3.Row) -> Conversation:
    return Conversation(
        id=row["id"],
        title=row["title"],
        model_id=row["model_id"],
        preset_id=row["preset_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_message(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content=row["content"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        tps=row["tps"],
        ttft_ms=row["ttft_ms"],
        created_at=row["created_at"],
    )


def create_conversation(
    conn: sqlite3.Connection,
    title: str,
    model_id: str,
    preset_id: str | None = None,
) -> Conversation:
    cid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO conversation (id, title, model_id, preset_id) VALUES (?, ?, ?, ?)",
        (cid, title, model_id, preset_id),
    )
    conn.commit()
    return get_conversation(conn, cid)  # type: ignore[return-value]


def get_conversation(conn: sqlite3.Connection, cid: str) -> Conversation | None:
    row = conn.execute("SELECT * FROM conversation WHERE id = ?", (cid,)).fetchone()
    return _row_to_conversation(row) if row else None


def list_conversations(conn: sqlite3.Connection) -> list[Conversation]:
    rows = conn.execute(
        "SELECT * FROM conversation ORDER BY updated_at DESC, rowid DESC"
    ).fetchall()
    return [_row_to_conversation(r) for r in rows]


def delete_conversation(conn: sqlite3.Connection, cid: str) -> None:
    conn.execute("DELETE FROM conversation WHERE id = ?", (cid,))
    conn.commit()


def insert_message(
    conn: sqlite3.Connection,
    conversation_id: str,
    role: str,
    content: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    tps: float | None = None,
    ttft_ms: float | None = None,
) -> Message:
    mid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO message
        (id, conversation_id, role, content, prompt_tokens, completion_tokens, tps, ttft_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (mid, conversation_id, role, content, prompt_tokens, completion_tokens, tps, ttft_ms),
    )
    conn.execute(
        "UPDATE conversation SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM message WHERE id = ?", (mid,)).fetchone()
    return _row_to_message(row)


def list_messages(conn: sqlite3.Connection, conversation_id: str) -> list[Message]:
    rows = conn.execute(
        "SELECT * FROM message WHERE conversation_id = ? ORDER BY created_at, rowid",
        (conversation_id,),
    ).fetchall()
    return [_row_to_message(r) for r in rows]
