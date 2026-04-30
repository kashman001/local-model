import json
from pathlib import Path

import respx
from httpx import Response

from bench.throughput import run_throughput


@respx.mock
def test_run_throughput_against_streaming_endpoint(tmp_path: Path):
    upstream = "http://127.0.0.1:8080"
    sse_body = (
        'data: {"choices":[{"delta":{"content":"a"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"b"}}],"x_local_model_stats":'
        '{"ttft_ms":12.0,"tps":42.0,"token_count":2,"total_ms":50.0}}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post(f"{upstream}/v1/chat/completions").mock(
        return_value=Response(200, content=sse_body, headers={"content-type": "text/event-stream"})
    )
    out = tmp_path / "report.json"
    report = run_throughput(
        server_url=upstream,
        model="m",
        prompt="hello",
        max_tokens=2,
        runs=1,
        out_path=out,
    )
    assert report["runs"] == 1
    assert report["mean_ttft_ms"] == 12.0
    assert report["mean_tps"] == 42.0
    assert json.loads(out.read_text())["mean_tps"] == 42.0
