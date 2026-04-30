"""Vibe-check benchmark — runs a curated prompt set and writes a Markdown report.

Usage:
    uv run python -m bench.vibe_check \
        --server http://127.0.0.1:8080 \
        --model mlx-community/Llama-3.1-8B-Instruct-4bit \
        --prompts bench/prompts/vibe_check.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import httpx


def _ask(server_url: str, model: str, prompt: str, max_tokens: int) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
    }
    with httpx.Client(timeout=300.0) as client:
        r = client.post(f"{server_url}/v1/chat/completions", json=payload)
        r.raise_for_status()
        return r.json()


def run_vibe_check(
    *,
    server_url: str,
    model: str,
    prompts_path: Path,
    out_path: Path,
    max_tokens: int = 256,
) -> None:
    prompts = json.loads(prompts_path.read_text())
    by_cat: dict[str, list[dict]] = {}
    for p in prompts:
        by_cat.setdefault(p["category"], []).append(p)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# Vibe check — {model}")
    lines.append("")
    lines.append(f"_generated {datetime.now().isoformat(timespec='seconds')} against {server_url}_")
    lines.append("")
    for cat, items in by_cat.items():
        lines.append(f"## {cat}")
        lines.append("")
        for item in items:
            resp = _ask(server_url, model, item["prompt"], max_tokens)
            content = resp["choices"][0]["message"]["content"]
            stats = resp.get("x_local_model_stats", {})
            lines.append(f"**Prompt:** {item['prompt']}")
            lines.append("")
            lines.append("**Response:**")
            lines.append("")
            lines.append("> " + content.replace("\n", "\n> "))
            lines.append("")
            if stats:
                lines.append(
                    f"_{stats.get('token_count', '?')} tokens · "
                    f"ttft {stats.get('ttft_ms', 0):.0f}ms · "
                    f"{stats.get('tps', 0):.1f} tok/s_"
                )
            lines.append("")
            lines.append("---")
            lines.append("")
    out_path.write_text("\n".join(lines))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://127.0.0.1:8080")
    p.add_argument("--model", required=True)
    p.add_argument("--prompts", default="bench/prompts/vibe_check.json")
    p.add_argument("--max-tokens", type=int, default=256)
    p.add_argument("--out", default=None)
    args = p.parse_args()
    out = (
        Path(args.out)
        if args.out
        else Path(
            f"bench/results/vibe-{args.model.replace('/', '_')}-"
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        )
    )
    run_vibe_check(
        server_url=args.server,
        model=args.model,
        prompts_path=Path(args.prompts),
        out_path=out,
        max_tokens=args.max_tokens,
    )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
