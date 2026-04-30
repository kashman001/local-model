"""Engine-level throughput benchmark — hits /v1/chat/completions and records TTFT/TPS.

Usage:
    uv run python -m bench.throughput \
        --server http://127.0.0.1:8080 \
        --model mlx-community/Llama-3.1-8B-Instruct-4bit \
        --prompt "Write a haiku about debugging" \
        --max-tokens 128 --runs 3
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


def _one_run(server_url: str, model: str, prompt: str, max_tokens: int) -> dict[str, float]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": max_tokens,
    }
    stats: dict[str, Any] = {}
    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", f"{server_url}/v1/chat/completions", json=payload) as r:
            for raw in r.iter_lines():
                if not raw.startswith("data: "):
                    continue
                data = raw[len("data: ") :]
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if "x_local_model_stats" in chunk:
                    stats = chunk["x_local_model_stats"]
    return {
        "ttft_ms": float(stats.get("ttft_ms", 0.0)),
        "tps": float(stats.get("tps", 0.0)),
        "token_count": int(stats.get("token_count", 0)),
        "total_ms": float(stats.get("total_ms", 0.0)),
    }


def run_throughput(
    *,
    server_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    runs: int,
    out_path: Path,
) -> dict[str, Any]:
    samples = [_one_run(server_url, model, prompt, max_tokens) for _ in range(runs)]
    report = {
        "model": model,
        "server_url": server_url,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "runs": runs,
        "samples": samples,
        "mean_ttft_ms": statistics.mean(s["ttft_ms"] for s in samples),
        "mean_tps": statistics.mean(s["tps"] for s in samples),
        "median_tps": statistics.median(s["tps"] for s in samples),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://127.0.0.1:8080")
    p.add_argument("--model", required=True)
    p.add_argument("--prompt", default="Write a haiku about debugging.")
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--out", default=None)
    args = p.parse_args()
    out = (
        Path(args.out)
        if args.out
        else Path(
            f"bench/results/throughput-{args.model.replace('/', '_')}-"
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
    )
    report = run_throughput(
        server_url=args.server,
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        runs=args.runs,
        out_path=out,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
