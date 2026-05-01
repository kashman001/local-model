# v1 Mac MLX baselines

Canonical measurements from the v1 ship session. Hardware: M5 Max
MacBook Pro, 128 GB unified memory. Backend: `MLXBackend` via `mlx_lm`.

These are committed deliberately (not under the gitignored
`bench/results/`) so the V2 session — which will run on a different
machine with `VLLMBackend` on RTX 4080 — can compare cross-platform.

## Files

- `throughput-llama-3.1-8b-4bit.json` — TTFT/TPS for the spec'd default
  model. Mean ~103 tok/s, ttft ~130 ms over 3 runs of 128 tokens.
  Recorded post-threading-fix (commits `56088ca` + `d90ec58`).
- `throughput-smollm-135m-4bit.json` — Tiny-model sanity baseline. Mean
  ~599 tok/s. Useful for verifying a brand-new vLLM install can run
  end-to-end on something cheap.
- `vibe-llama-3.1-8b-4bit.md` — 30-prompt qualitative responses across
  15 categories. Eyeball test for response quality on the spec'd
  default. Cross-check: V2's first vibe report should produce
  qualitatively similar (or better) answers.
- `vibe-smollm-135m-4bit.md` — Same prompts against a model too small
  to follow instructions cleanly. Reference for "what bad responses
  look like" so any V2 regression is recognizable.
- `mmlu-stem-llama-3.1-8b-4bit.json` *(added when the full mmlu_stem
  run completes — see lm_eval output under `bench/results/`)* — MMLU-STEM
  5-shot accuracy via lm_eval, measured against the live `/v1/completions`
  endpoint with `local-completions` adapter. The full run is 12,612
  loglikelihood requests; ~4 hours wall on Llama-8B.

## Reproducing

Server must be up with the model loaded:

```bash
LOCAL_MODEL_DEFAULT_MODEL=mlx-community/Llama-3.1-8B-Instruct-4bit \
  uv run uvicorn server.app:build_app_from_env --factory --port 8080
```

Then:

```bash
# Throughput
uv run python -m bench.throughput \
    --model mlx-community/Llama-3.1-8B-Instruct-4bit --runs 3

# Vibe check (30 prompts)
uv run python -m bench.vibe_check \
    --model mlx-community/Llama-3.1-8B-Instruct-4bit

# MMLU-STEM (5-shot, full run ~4 hours on M5 Max)
uv run python -m bench.eval_harness \
    --model mlx-community/Llama-3.1-8B-Instruct-4bit \
    --task mmlu_stem --num-fewshot 5
```

Output goes to `bench/results/` (gitignored). Copy into this directory
and commit if you want to capture a new baseline (e.g. after the V2
vLLM bring-up on the PC, this directory's V2 sibling becomes
`bench/baselines/v2-pc-vllm/`).
