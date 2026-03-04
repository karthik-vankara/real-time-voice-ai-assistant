"""Latency metrics: per-request tracker + P50/P95/P99 aggregator (FR-013, FR-014).

T030: LatencyTracker — captures timestamps at each stage boundary.
T031: PercentileAggregator — sliding window P50/P95/P99 computation.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from src.config import config
from src.models.telemetry import LatencyRecord
from src.telemetry.logger import logger

# ---------------------------------------------------------------------------
# T030: Per-request latency tracker
# ---------------------------------------------------------------------------

class LatencyTracker:
    """Captures start/end timestamps for each pipeline stage.

    Usage::

        tracker = LatencyTracker(correlation_id="abc123")
        tracker.start("asr")
        ...
        tracker.stop("asr")
        tracker.start("llm")
        ...
        tracker.stop("llm")
        record = tracker.to_record()
    """

    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id
        self._starts: dict[str, float] = {}
        self._durations: dict[str, float] = {}
        self._overall_start: float = time.monotonic()

    def start(self, stage: str) -> None:
        """Mark the start of *stage*."""
        self._starts[stage] = time.monotonic()

    def stop(self, stage: str) -> None:
        """Mark the end of *stage* and compute duration in ms."""
        start = self._starts.get(stage)
        if start is not None:
            self._durations[stage] = (time.monotonic() - start) * 1000.0

    def to_record(self) -> LatencyRecord:
        """Build a ``LatencyRecord`` from the collected timings."""
        total = (time.monotonic() - self._overall_start) * 1000.0
        asr_ms = self._durations.get("asr", 0.0)
        llm_ms = self._durations.get("llm", 0.0)
        tts_ms = self._durations.get("tts", 0.0)
        overhead = max(0.0, total - asr_ms - llm_ms - tts_ms)

        record = LatencyRecord(
            correlation_id=self.correlation_id,
            asr_ms=asr_ms,
            llm_ttft_ms=llm_ms,
            tts_ttfb_ms=tts_ms,
            orchestration_overhead_ms=overhead,
        )

        if record.budget_breached:
            breaches = {k: v for k, v in record.stage_breaches.items() if v}
            logger.warning(
                f"Latency budget breached: total={record.total_e2e_ms:.1f}ms, breaches={breaches}",
                correlation_id=self.correlation_id,
                pipeline_stage="telemetry",
            )

        return record


# ---------------------------------------------------------------------------
# T031: P50/P95/P99 percentile aggregator
# ---------------------------------------------------------------------------

@dataclass
class StagePercentiles:
    """Percentile values for one metric."""

    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0


class PercentileAggregator:
    """Sliding-window percentile computation over recent ``LatencyRecord``s.

    Thread-safe for concurrent reads. Writes are expected to happen from
    a single event loop.
    """

    def __init__(self, window_size: int | None = None) -> None:
        self._window_size = window_size or config.telemetry.percentile_window_size
        self._records: deque[LatencyRecord] = deque(maxlen=self._window_size)

    def add(self, record: LatencyRecord) -> None:
        """Add a record to the sliding window."""
        self._records.append(record)

    @property
    def count(self) -> int:
        return len(self._records)

    def percentile(self, values: list[float], p: float) -> float:
        """Compute the *p*-th percentile (0-100) of sorted *values*."""
        if not values:
            return 0.0
        k = (p / 100.0) * (len(values) - 1)
        f = int(k)
        c = f + 1 if f + 1 < len(values) else f
        d = k - f
        return values[f] + d * (values[c] - values[f])

    def _sorted_field(self, attr: str) -> list[float]:
        return sorted(getattr(r, attr) for r in self._records)

    def get_percentiles(self) -> dict[str, StagePercentiles]:
        """Return P50/P95/P99 for all latency components."""
        fields = {
            "asr": "asr_ms",
            "llm_ttft": "llm_ttft_ms",
            "tts_ttfb": "tts_ttfb_ms",
            "orchestration_overhead": "orchestration_overhead_ms",
            "total_e2e": "total_e2e_ms",
        }
        result: dict[str, StagePercentiles] = {}
        for name, attr in fields.items():
            vals = self._sorted_field(attr)
            result[name] = StagePercentiles(
                p50=self.percentile(vals, 50),
                p95=self.percentile(vals, 95),
                p99=self.percentile(vals, 99),
            )
        return result


# Module-level singleton
aggregator = PercentileAggregator()
