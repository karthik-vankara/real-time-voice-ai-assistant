"""Generic async circuit breaker (FR-009, Clarification Q3).

State machine: CLOSED → OPEN → HALF_OPEN → CLOSED (on success) or OPEN (on failure).
Opens after ``failure_threshold`` failures within ``window_seconds``.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable, Coroutine  # noqa: TC003
from enum import StrEnum
from typing import Any, TypeVar

from src.config import config as app_config
from src.telemetry.logger import logger

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an open circuit."""


class CircuitBreaker:
    """Async circuit breaker wrapping an external service call.

    Parameters
    ----------
    name:
        Human-readable name for logging.
    failure_threshold:
        Number of failures in the sliding window before opening.
    window_seconds:
        Width of the sliding failure-count window.
    half_open_timeout:
        Seconds to wait in OPEN state before transitioning to HALF_OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int | None = None,
        window_seconds: float | None = None,
        half_open_timeout: float | None = None,
    ) -> None:
        cb = app_config.circuit_breaker
        self.name = name
        self.failure_threshold = failure_threshold or cb.failure_threshold
        self.window_seconds = window_seconds or cb.window_seconds
        self.half_open_timeout = half_open_timeout or cb.half_open_timeout_seconds

        self._state = CircuitState.CLOSED
        self._failure_timestamps: deque[float] = deque()
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute *func* through the circuit breaker.

        Raises ``CircuitOpenError`` if the circuit is open and the half-open
        timeout has not elapsed.
        """
        async with self._lock:
            self._purge_old_failures()
            if self._state == CircuitState.OPEN:
                if self._should_attempt_half_open():
                    self._state = CircuitState.HALF_OPEN
                    logger.info(
                        f"Circuit '{self.name}' entering HALF_OPEN",
                        pipeline_stage="circuit_breaker",
                    )
                else:
                    raise CircuitOpenError(
                        f"Circuit '{self.name}' is OPEN — call rejected"
                    )

        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            await self._record_failure()
            raise exc
        else:
            await self._record_success()
            return result

    async def reset(self) -> None:
        """Force-close the circuit (e.g., for testing)."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_timestamps.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _purge_old_failures(self) -> None:
        cutoff = time.monotonic() - self.window_seconds
        while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
            self._failure_timestamps.popleft()

    def _should_attempt_half_open(self) -> bool:
        return (time.monotonic() - self._last_failure_time) >= self.half_open_timeout

    async def _record_failure(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._failure_timestamps.append(now)
            self._last_failure_time = now
            self._purge_old_failures()

            if len(self._failure_timestamps) >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit '{self.name}' OPENED after {self.failure_threshold} failures",
                        pipeline_stage="circuit_breaker",
                    )
            elif self._state == CircuitState.HALF_OPEN:
                # Failed during probe → reopen
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit '{self.name}' probe failed — reopened",
                    pipeline_stage="circuit_breaker",
                )

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_timestamps.clear()
                logger.info(
                    f"Circuit '{self.name}' CLOSED after successful probe",
                    pipeline_stage="circuit_breaker",
                )
