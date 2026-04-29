"""TTFT + TPS instrumentation for streaming generations."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(slots=True)
class TimingSummary:
    token_count: int
    ttft_ms: float
    tps: float
    total_ms: float


class StreamTimer:
    """Measures time-to-first-token and tokens-per-second for a generate() call."""

    def __init__(self) -> None:
        self._t0: float | None = None
        self._t_first: float | None = None
        self._count = 0

    def start(self) -> None:
        self._t0 = time.perf_counter()

    def token(self) -> None:
        self._count += 1
        if self._t_first is None:
            self._t_first = time.perf_counter()

    def finish(self) -> TimingSummary:
        if self._t0 is None:
            return TimingSummary(0, 0.0, 0.0, 0.0)
        end = time.perf_counter()
        total_ms = (end - self._t0) * 1000.0
        if self._count == 0 or self._t_first is None:
            return TimingSummary(0, 0.0, 0.0, total_ms)
        ttft_ms = (self._t_first - self._t0) * 1000.0
        gen_seconds = max(end - self._t_first, 1e-9)
        tps = self._count / gen_seconds
        return TimingSummary(
            token_count=self._count,
            ttft_ms=ttft_ms,
            tps=tps,
            total_ms=total_ms,
        )
