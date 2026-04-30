from pathlib import Path

from bench.eval_harness import build_lm_eval_command


def test_build_command_for_mmlu():
    cmd = build_lm_eval_command(
        server_url="http://127.0.0.1:8080",
        model="m",
        task="mmlu_stem",
        num_fewshot=5,
        out_dir=Path("bench/results"),
    )
    assert cmd[0] == "lm_eval"
    assert "--model" in cmd
    idx = cmd.index("--model_args")
    assert "base_url=http://127.0.0.1:8080/v1" in cmd[idx + 1]
    assert "model=m" in cmd[idx + 1]
    assert "--tasks" in cmd
    assert cmd[cmd.index("--tasks") + 1] == "mmlu_stem"
    assert "--num_fewshot" in cmd
    assert cmd[cmd.index("--num_fewshot") + 1] == "5"
