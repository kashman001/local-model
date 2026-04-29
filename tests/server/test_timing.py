import time

from server.timing import StreamTimer


def test_stream_timer_basic():
    t = StreamTimer()
    t.start()
    time.sleep(0.01)
    t.token()  # first token
    t.token()
    t.token()
    summary = t.finish()
    assert summary.token_count == 3
    assert summary.ttft_ms > 0
    assert summary.tps > 0


def test_stream_timer_zero_tokens():
    t = StreamTimer()
    t.start()
    summary = t.finish()
    assert summary.token_count == 0
    assert summary.ttft_ms == 0.0
    assert summary.tps == 0.0
