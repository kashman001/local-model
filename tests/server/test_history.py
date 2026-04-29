from pathlib import Path

import pytest

from server.store.db import connect, migrate
from server.store.history import (
    Conversation,
    create_conversation,
    delete_conversation,
    get_conversation,
    insert_message,
    list_conversations,
    list_messages,
)


@pytest.fixture()
def conn(tmp_path: Path):
    c = connect(tmp_path / "h.db")
    migrate(c)
    yield c
    c.close()


def test_create_conversation_returns_row(conn):
    convo = create_conversation(conn, title="t", model_id="m")
    assert isinstance(convo, Conversation)
    assert convo.title == "t"
    assert convo.model_id == "m"
    assert convo.id


def test_list_conversations_orders_by_updated_desc(conn):
    a = create_conversation(conn, title="A", model_id="m")
    b = create_conversation(conn, title="B", model_id="m")
    rows = list_conversations(conn)
    assert [r.id for r in rows][:2] == [b.id, a.id]


def test_get_conversation_returns_none_for_missing(conn):
    assert get_conversation(conn, "missing") is None


def test_insert_message_and_list(conn):
    c = create_conversation(conn, title="t", model_id="m")
    m1 = insert_message(conn, c.id, role="user", content="hi")
    m2 = insert_message(conn, c.id, role="assistant", content="hello", tps=42.0, ttft_ms=10.0)
    msgs = list_messages(conn, c.id)
    assert [m.id for m in msgs] == [m1.id, m2.id]
    assert msgs[1].tps == 42.0


def test_delete_conversation_cascades(conn):
    c = create_conversation(conn, title="t", model_id="m")
    insert_message(conn, c.id, role="user", content="hi")
    delete_conversation(conn, c.id)
    assert get_conversation(conn, c.id) is None
    assert list_messages(conn, c.id) == []
