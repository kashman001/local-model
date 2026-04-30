import json
from pathlib import Path

import respx
from httpx import Response

from bench.vibe_check import run_vibe_check


@respx.mock
def test_run_vibe_check_writes_markdown_report(tmp_path: Path):
    upstream = "http://127.0.0.1:8080"
    respx.post(f"{upstream}/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "x_local_model_stats": {
                    "ttft_ms": 10.0,
                    "tps": 50.0,
                    "token_count": 1,
                    "total_ms": 20.0,
                },
            },
        )
    )
    prompts = tmp_path / "prompts.json"
    prompts.write_text(json.dumps([{"category": "smoke", "prompt": "say hi"}]))
    out = tmp_path / "report.md"
    run_vibe_check(server_url=upstream, model="m", prompts_path=prompts, out_path=out, max_tokens=8)
    md = out.read_text()
    assert "## smoke" in md
    assert "say hi" in md
    assert "ok" in md
    assert "tok/s" in md
