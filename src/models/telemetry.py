"""Latency record model (FR-013, FR-014, Constitution Principle III).

Captures per-request timing decomposition across all pipeline stages.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.config import config


class LatencyRecord(BaseModel):
    """Per-request performance data.

    All timing fields are in **milliseconds**.
    """

    model_config = ConfigDict(frozen=True)

    correlation_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Per-stage timings (ms)
    asr_ms: float = 0.0
    llm_ttft_ms: float = 0.0
    tts_ttfb_ms: float = 0.0
    orchestration_overhead_ms: float = 0.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_e2e_ms(self) -> float:
        """Total end-to-end latency (sum of stages)."""
        return (
            self.asr_ms
            + self.llm_ttft_ms
            + self.tts_ttfb_ms
            + self.orchestration_overhead_ms
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def budget_breached(self) -> bool:
        """Whether the total E2E latency exceeds the P95 budget."""
        return self.total_e2e_ms > config.latency.total_e2e

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stage_breaches(self) -> dict[str, bool]:
        """Per-stage budget breach flags."""
        return {
            "asr": self.asr_ms > config.latency.asr,
            "llm_ttft": self.llm_ttft_ms > config.latency.llm_ttft,
            "tts_ttfb": self.tts_ttfb_ms > config.latency.tts_ttfb,
            "orchestration": self.orchestration_overhead_ms > config.latency.orchestration_overhead,
        }
