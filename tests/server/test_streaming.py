import json

from server.backends.base import Token
from server.streaming import sse_chat_stream


def test_sse_chat_stream_emits_chunks_and_done():
    def gen():
        yield Token(text="he", token_id=1, logprob=0.0, elapsed_ms=1.0)
        yield Token(text="llo", token_id=2, logprob=0.0, elapsed_ms=2.0)

    out = list(sse_chat_stream(gen(), model_id="m"))
    text = "".join(out)
    assert "data: " in text
    assert "[DONE]" in text
    # find the chunks
    chunks = [
        json.loads(line[len("data: ") :])
        for line in text.split("\n")
        if line.startswith("data: ") and "[DONE]" not in line
    ]
    contents = [c["choices"][0]["delta"].get("content", "") for c in chunks]
    assert "".join(contents) == "hello"
    assert chunks[-1]["choices"][0].get("finish_reason") == "stop"
    assert "x_local_model_stats" in chunks[-1]


def test_sse_chat_stream_empty_generator():
    out = list(sse_chat_stream(iter([]), model_id="m"))
    assert "[DONE]" in "".join(out)
