from server.config import ServerSettings


def test_defaults():
    s = ServerSettings(_env_file=None)
    assert s.backend == "mlx"
    assert s.host == "127.0.0.1"
    assert s.port == 8080
    assert s.default_model == "mlx-community/Llama-3.1-8B-Instruct-4bit"
    assert s.db_path.endswith("history.db")
    assert s.log_level == "INFO"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LOCAL_MODEL_BACKEND", "vllm")
    monkeypatch.setenv("LOCAL_MODEL_PORT", "9999")
    s = ServerSettings(_env_file=None)
    assert s.backend == "vllm"
    assert s.port == 9999
