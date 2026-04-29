import pytest

from server.backends.fake import FakeBackend
from server.registry import ModelNotLoaded, ModelRegistry


def test_load_returns_info():
    r = ModelRegistry(backend=FakeBackend())
    info = r.load("m1")
    assert info.id == "m1"
    assert r.current() == "m1"


def test_load_swaps_existing():
    r = ModelRegistry(backend=FakeBackend())
    r.load("m1")
    r.load("m2")
    assert r.current() == "m2"
    assert r.loaded_ids() == ["m2"]


def test_unload():
    r = ModelRegistry(backend=FakeBackend())
    r.load("m1")
    r.unload("m1")
    assert r.current() is None
    assert r.loaded_ids() == []


def test_require_current_raises_when_unloaded():
    r = ModelRegistry(backend=FakeBackend())
    with pytest.raises(ModelNotLoaded):
        r.require_current()


def test_require_current_returns_id():
    r = ModelRegistry(backend=FakeBackend())
    r.load("m1")
    assert r.require_current() == "m1"
