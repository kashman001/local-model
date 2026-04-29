from pathlib import Path

import pytest

from server.store.db import connect, migrate


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


def test_connect_creates_file(tmp_db):
    conn = connect(tmp_db)
    assert tmp_db.exists()
    conn.close()


def test_migrate_creates_tables(tmp_db):
    conn = connect(tmp_db)
    migrate(conn)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = {row[0] for row in cur.fetchall()}
    assert {"conversation", "message", "preset"}.issubset(names)
    conn.close()


def test_migrate_is_idempotent(tmp_db):
    conn = connect(tmp_db)
    migrate(conn)
    migrate(conn)  # second call must not raise
    conn.close()


def test_foreign_keys_enabled(tmp_db):
    conn = connect(tmp_db)
    cur = conn.execute("PRAGMA foreign_keys")
    assert cur.fetchone()[0] == 1
    conn.close()
