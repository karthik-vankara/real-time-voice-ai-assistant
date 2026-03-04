"""Session lifecycle manager (FR-004, FR-008, FR-019).

Manages creation, lookup, idle timeout, and cleanup of voice sessions.
Supports up to ``max_concurrent_sessions`` (default 50).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from src.config import config
from src.models.session import Session
from src.telemetry.logger import logger


class SessionManager:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_session(self) -> Session:
        """Create a new session, enforcing max_concurrent_sessions (FR-008)."""
        async with self._lock:
            active = sum(1 for s in self._sessions.values() if s.is_active)
            if active >= config.session.max_concurrent_sessions:
                msg = (
                    f"Maximum concurrent sessions"
                    f" ({config.session.max_concurrent_sessions}) reached"
                )
                raise RuntimeError(msg)
            session = Session()
            self._sessions[session.session_id] = session
            logger.info(
                "Session created",
                session_id=session.session_id,
                pipeline_stage="session_manager",
            )
            return session

    async def get_session(self, session_id: str) -> Session | None:
        """Look up a session by ID."""
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close and purge a session (FR-019)."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is not None:
                session.close()
                logger.info(
                    "Session closed and purged",
                    session_id=session_id,
                    pipeline_stage="session_manager",
                )

    async def touch_session(self, session_id: str) -> None:
        """Update last activity timestamp."""
        session = self._sessions.get(session_id)
        if session:
            session.touch()

    # ------------------------------------------------------------------
    # Idle timeout
    # ------------------------------------------------------------------

    async def cleanup_idle_sessions(self) -> list[str]:
        """Close sessions that have exceeded the idle timeout."""
        now = datetime.now(UTC)
        to_close: list[str] = []
        for sid, session in list(self._sessions.items()):
            if not session.is_active:
                continue
            elapsed = (now - session.last_activity).total_seconds()
            if elapsed > session.idle_timeout_seconds:
                to_close.append(sid)

        for sid in to_close:
            await self.close_session(sid)
            logger.info(
                "Idle session cleaned up",
                session_id=sid,
                pipeline_stage="session_manager",
            )
        return to_close

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def active_session_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.is_active)

    @property
    def session_ids(self) -> list[str]:
        return list(self._sessions.keys())


# Module-level singleton
session_manager = SessionManager()
