"""Application configuration.

Latency budgets, timeouts, audio format defaults, and circuit breaker
thresholds.  All values sourced from the constitution performance standards
and spec clarifications.

Environment variables (via .env):
  - ASR_PROVIDER_URL, ASR_API_KEY
  - LLM_PROVIDER_URL, LLM_API_KEY
  - TTS_PROVIDER_URL, TTS_API_KEY
  - SERVER_HOST, SERVER_PORT, SERVER_REQUIRE_TLS
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Load .env if available (for local dev)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True, slots=True)
class AudioConfig:
    """Audio format defaults (FR-018, Assumptions)."""

    sample_rate_hz: int = 16_000
    bit_depth: int = 16
    channels: int = 1
    encoding: str = "pcm_s16le"
    # Derived: bytes per second = sample_rate * (bit_depth / 8) * channels
    bytes_per_second: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "bytes_per_second",
            self.sample_rate_hz * (self.bit_depth // 8) * self.channels,
        )


@dataclass(frozen=True, slots=True)
class LatencyBudgetMs:
    """Per-stage P95 latency budgets in milliseconds (Constitution Principle III)."""

    asr: int = 500
    llm_ttft: int = 400
    tts_ttfb: int = 250
    orchestration_overhead: int = 100
    total_e2e: int = 1_200
    total_e2e_p99: int = 1_800


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    """Circuit breaker settings (FR-009, Clarification Q3)."""

    failure_threshold: int = 3
    window_seconds: float = 30.0
    half_open_timeout_seconds: float = 10.0


@dataclass(frozen=True, slots=True)
class SessionConfig:
    """Session lifecycle settings (FR-004, Clarification Q2, Assumptions)."""

    max_context_turns: int = 10
    idle_timeout_seconds: float = 60.0
    max_concurrent_sessions: int = 50


@dataclass(frozen=True, slots=True)
class ServiceTimeoutConfig:
    """Per-service HTTP/streaming timeout in seconds."""

    asr_timeout: float = 1.0
    llm_timeout: float = 1.0
    tts_timeout: float = 0.5
    connect_timeout: float = 0.5


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    """Telemetry / metrics aggregation settings."""

    percentile_window_size: int = 1000  # sliding window of recent records
    log_format: str = "json"


@dataclass(frozen=True, slots=True)
class ServerConfig:
    """FastAPI / uvicorn server settings."""

    host: str = "0.0.0.0"
    port: int = 8000
    ws_path: str = "/ws"
    require_tls: bool = True


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """External service provider URLs and API keys."""

    asr_url: str
    asr_api_key: str
    llm_url: str
    llm_api_key: str
    tts_url: str
    tts_api_key: str


def _load_provider_config() -> ProviderConfig:
    """Load provider URLs and API keys from environment variables."""
    return ProviderConfig(
        asr_url=os.getenv("ASR_PROVIDER_URL", "http://localhost:9001/asr/stream"),
        asr_api_key=os.getenv("ASR_API_KEY", ""),
        llm_url=os.getenv("LLM_PROVIDER_URL", "http://localhost:9002/llm/stream"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        tts_url=os.getenv("TTS_PROVIDER_URL", "http://localhost:9003/tts/stream"),
        tts_api_key=os.getenv("TTS_API_KEY", ""),
    )


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Root application configuration aggregating all sub-configs."""

    audio: AudioConfig = field(default_factory=AudioConfig)
    latency: LatencyBudgetMs = field(default_factory=LatencyBudgetMs)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    service_timeout: ServiceTimeoutConfig = field(default_factory=ServiceTimeoutConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    provider: ProviderConfig = field(default_factory=_load_provider_config)


# Singleton default configuration — importable anywhere
config = AppConfig()
