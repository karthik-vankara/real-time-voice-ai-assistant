"""Telemetry dashboard endpoint (FR-014, T033).

HTTP GET endpoint returning current P50/P95/P99 percentiles for all
latency components as JSON.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.telemetry.metrics import aggregator

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/latency")
async def latency_dashboard() -> dict:
    """Return aggregated latency percentiles.

    Response shape::

        {
          "sample_count": 42,
          "percentiles": {
            "asr": {"p50": 120.3, "p95": 480.1, "p99": 510.0},
            "llm_ttft": {"p50": 200.0, "p95": 390.0, "p99": 420.0},
            ...
          }
        }
    """
    percentiles = aggregator.get_percentiles()
    return {
        "sample_count": aggregator.count,
        "percentiles": {
            name: {"p50": sp.p50, "p95": sp.p95, "p99": sp.p99}
            for name, sp in percentiles.items()
        },
    }
