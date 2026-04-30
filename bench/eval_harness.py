"""Driver for lm-evaluation-harness against the local OpenAI-compatible server.

Requires the `[bench]` extras group:
    uv sync --extra bench

Usage:
    uv run python -m bench.eval_harness \
        --server http://127.0.0.1:8080 \
        --model mlx-community/Llama-3.1-8B-Instruct-4bit \
        --task mmlu_stem --num-fewshot 5
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def build_lm_eval_command(
    *,
    server_url: str,
    model: str,
    task: str,
    num_fewshot: int,
    out_dir: Path,
) -> list[str]:
    return [
        "lm_eval",
        "--model",
        "local-completions",
        "--model_args",
        f"model={model},base_url={server_url}/v1,tokenized_requests=False,num_concurrent=1",
        "--tasks",
        task,
        "--num_fewshot",
        str(num_fewshot),
        "--output_path",
        str(out_dir),
    ]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://127.0.0.1:8080")
    p.add_argument("--model", required=True)
    p.add_argument("--task", default="mmlu_stem")
    p.add_argument("--num-fewshot", type=int, default=5)
    p.add_argument("--out-dir", default="bench/results")
    args = p.parse_args()
    cmd = build_lm_eval_command(
        server_url=args.server,
        model=args.model,
        task=args.task,
        num_fewshot=args.num_fewshot,
        out_dir=Path(args.out_dir),
    )
    print("Running:", " ".join(shlex.quote(c) for c in cmd))
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
