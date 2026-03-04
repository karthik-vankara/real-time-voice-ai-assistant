"""Structured JSON logger with correlation ID injection (FR-016).

Provides a pipeline-aware logger that always emits structured JSON lines with
mandatory ``correlation_id`` and ``pipeline_stage`` fields.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class _JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Inject extra fields set by PipelineLogger
        for key in ("correlation_id", "pipeline_stage", "session_id"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        # Forward any additional extras
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry, default=str)


def _build_handler() -> logging.StreamHandler:  # type: ignore[type-arg]
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    return handler


# Module-level singleton handler so we don't duplicate on repeated import
_HANDLER = _build_handler()


class PipelineLogger:
    """Thin wrapper around stdlib ``logging.Logger`` with correlation context."""

    def __init__(self, name: str = "pipeline") -> None:
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            self._logger.addHandler(_HANDLER)
            self._logger.setLevel(logging.DEBUG)
            self._logger.propagate = False

    def _log(
        self,
        level: int,
        msg: str,
        *,
        correlation_id: str | None = None,
        pipeline_stage: str | None = None,
        session_id: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        extra: dict[str, Any] = {}
        if correlation_id:
            extra["correlation_id"] = correlation_id
        if pipeline_stage:
            extra["pipeline_stage"] = pipeline_stage
        if session_id:
            extra["session_id"] = session_id
        if extra_data:
            extra["extra_data"] = extra_data
        self._logger.log(level, msg, extra=extra)

    # Convenience methods ------------------------------------------------

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, **kwargs)


# Default logger instance
logger = PipelineLogger()
