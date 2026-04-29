from pathlib import Path

import pytest

from server.store.db import connect, migrate
from server.store.presets import (
    Preset,
    create_preset,
    delete_preset,
    get_preset,
    list_presets,
)


@pytest.fixture()
def conn(tmp_path: Path):
    c = connect(tmp_path / "p.db")
    migrate(c)
    yield c
    c.close()


def test_create_preset(conn):
    p = create_preset(
        conn,
        name="coder",
        system_prompt="You are a coding assistant.",
        default_params={"temperature": 0.2},
    )
    assert isinstance(p, Preset)
    assert p.name == "coder"
    assert p.default_params == {"temperature": 0.2}


def test_list_presets(conn):
    create_preset(conn, name="a", system_prompt="A")
    create_preset(conn, name="b", system_prompt="B")
    rows = list_presets(conn)
    assert {r.name for r in rows} == {"a", "b"}


def test_get_preset_returns_none_for_missing(conn):
    assert get_preset(conn, "nope") is None


def test_delete_preset(conn):
    p = create_preset(conn, name="x", system_prompt="X")
    delete_preset(conn, p.id)
    assert get_preset(conn, p.id) is None
