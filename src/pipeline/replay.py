"""Session recorder and replay engine (FR-015, US5).

T035: SessionRecorder — capture audio chunks + events with timestamps.
T036: ReplayEngine — feed a recorded session back through the pipeline.
T038: Timing modification — configurable delay multipliers.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path  # noqa: TC003
from typing import Any

from src.models.events import _new_correlation_id
from src.telemetry.logger import logger

# ---------------------------------------------------------------------------
# T035: Session recorder
# ---------------------------------------------------------------------------

@dataclass
class RecordedChunk:
    """A single audio chunk with its relative timestamp."""

    offset_ms: float
    audio_hex: str  # hex-encoded raw bytes for JSON serialisation


@dataclass
class RecordedEvent:
    """A captured pipeline event with its relative timestamp."""

    offset_ms: float
    event_json: dict[str, Any]


@dataclass
class RecordedSession:
    """A fully recorded session that can be serialised/deserialised to JSON."""

    session_id: str
    recorded_at: str = ""
    audio_chunks: list[RecordedChunk] = field(default_factory=list)
    events: list[RecordedEvent] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialise to a JSON string."""
        return json.dumps(
            {
                "session_id": self.session_id,
                "recorded_at": self.recorded_at,
                "audio_chunks": [
                    {"offset_ms": c.offset_ms, "audio_hex": c.audio_hex}
                    for c in self.audio_chunks
                ],
                "events": [
                    {"offset_ms": e.offset_ms, "event_json": e.event_json}
                    for e in self.events
                ],
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, raw: str) -> RecordedSession:
        """Deserialise from a JSON string."""
        data = json.loads(raw)
        return cls(
            session_id=data["session_id"],
            recorded_at=data.get("recorded_at", ""),
            audio_chunks=[
                RecordedChunk(offset_ms=c["offset_ms"], audio_hex=c["audio_hex"])
                for c in data.get("audio_chunks", [])
            ],
            events=[
                RecordedEvent(offset_ms=e["offset_ms"], event_json=e["event_json"])
                for e in data.get("events", [])
            ],
        )


class SessionRecorder:
    """Captures audio chunks and pipeline events for a live session (T035)."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._start = time.monotonic()
        self._chunks: list[RecordedChunk] = []
        self._events: list[RecordedEvent] = []

    def record_audio(self, data: bytes) -> None:
        """Record an incoming audio chunk."""
        offset = (time.monotonic() - self._start) * 1000.0
        self._chunks.append(RecordedChunk(offset_ms=offset, audio_hex=data.hex()))

    def record_event(self, event_dict: dict[str, Any]) -> None:
        """Record a pipeline event (already serialised to dict)."""
        offset = (time.monotonic() - self._start) * 1000.0
        self._events.append(RecordedEvent(offset_ms=offset, event_json=event_dict))

    def build(self) -> RecordedSession:
        """Finalise the recording."""
        from datetime import datetime

        return RecordedSession(
            session_id=self.session_id,
            recorded_at=datetime.now(UTC).isoformat(),
            audio_chunks=list(self._chunks),
            events=list(self._events),
        )

    def save(self, path: Path) -> None:
        """Save the recorded session to a JSON file."""
        recording = self.build()
        path.write_text(recording.to_json(), encoding="utf-8")
        logger.info(
            f"Session recorded to {path}",
            session_id=self.session_id,
            pipeline_stage="replay",
        )


# ---------------------------------------------------------------------------
# T036 + T038: Replay engine with timing modification
# ---------------------------------------------------------------------------

class ReplayEngine:
    """Replays a recorded session through the pipeline (T036).

    Supports timing modification via *delay_multiplier* (T038):
    - 1.0 = original timing
    - 2.0 = simulate services that are twice as slow
    - 0.5 = replay at double speed
    """

    def __init__(
        self,
        recorded: RecordedSession,
        delay_multiplier: float = 1.0,
    ) -> None:
        self.recorded = recorded
        self.delay_multiplier = delay_multiplier
        self._result_events: list[dict[str, Any]] = []

    async def replay(self) -> list[dict[str, Any]]:
        """Feed recorded audio chunks into the pipeline at original timestamps.

        Returns the list of pipeline events produced during replay.
        """
        logger.info(
            f"Replaying session {self.recorded.session_id} "
            f"({len(self.recorded.audio_chunks)} chunks, "
            f"delay_multiplier={self.delay_multiplier})",
            pipeline_stage="replay",
        )

        # Import here to avoid circular imports
        from src.pipeline.session_manager import session_manager
        from src.services import asr

        session = await session_manager.create_session()
        correlation_id = _new_correlation_id()

        try:
            # Feed audio chunks with timing gaps
            prev_offset = 0.0
            audio_buffers: list[bytes] = []

            for chunk in self.recorded.audio_chunks:
                delay_ms = (chunk.offset_ms - prev_offset) * self.delay_multiplier
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)
                audio_buffers.append(bytes.fromhex(chunk.audio_hex))
                prev_offset = chunk.offset_ms

            # Run ASR on collected audio
            if audio_buffers:
                full_audio = b"".join(audio_buffers)
                try:
                    text = await asr.transcribe_audio(
                        full_audio, correlation_id=correlation_id
                    )
                    self._result_events.append({
                        "type": "transcription_final",
                        "correlation_id": correlation_id,
                        "text": text,
                    })
                except Exception as exc:
                    self._result_events.append({
                        "type": "error",
                        "correlation_id": correlation_id,
                        "message": str(exc),
                    })

        finally:
            await session_manager.close_session(session.session_id)

        logger.info(
            f"Replay complete: {len(self._result_events)} events produced",
            session_id=self.recorded.session_id,
            pipeline_stage="replay",
        )
        return self._result_events
