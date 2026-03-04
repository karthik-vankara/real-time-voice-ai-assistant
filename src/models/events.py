"""Pydantic v2 pipeline event schemas (FR-006, FR-007).

All inter-service messages are schema-validated.  Event types use a literal
discriminator for exhaustive matching.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventType(StrEnum):
    """Canonical pipeline event types (FR-007)."""

    SPEECH_STARTED = "speech_started"
    TRANSCRIPTION_PROVISIONAL = "transcription_provisional"
    TRANSCRIPTION_FINAL = "transcription_final"
    LLM_TOKEN_GENERATED = "llm_token_generated"
    TTS_AUDIO_CHUNK = "tts_audio_chunk"
    ERROR = "error"


class PipelineStage(StrEnum):
    """Originating stage for an event."""

    CLIENT = "client"
    ASR = "asr"
    LLM = "llm"
    TTS = "tts"
    ORCHESTRATOR = "orchestrator"
    FALLBACK = "fallback"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_correlation_id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Typed payloads
# ---------------------------------------------------------------------------


class SpeechStartedPayload(BaseModel):
    """Payload for speech_started events."""

    model_config = ConfigDict(frozen=True)
    session_id: str


class TranscriptionProvisionalPayload(BaseModel):
    """Payload for interim ASR results."""

    model_config = ConfigDict(frozen=True)
    text: str
    is_partial: Literal[True] = True


class TranscriptionFinalPayload(BaseModel):
    """Payload for final ASR transcription."""

    model_config = ConfigDict(frozen=True)
    text: str
    is_partial: Literal[False] = False


class LLMTokenPayload(BaseModel):
    """Payload for a single streamed LLM token."""

    model_config = ConfigDict(frozen=True)
    token: str
    accumulated_text: str = ""


class TTSAudioChunkPayload(BaseModel):
    """Payload for a TTS audio chunk (raw bytes represented as base64)."""

    model_config = ConfigDict(frozen=True)
    audio_b64: str
    chunk_index: int = 0
    is_last: bool = False


class ErrorPayload(BaseModel):
    """Payload for error events (FR-018 and others)."""

    model_config = ConfigDict(frozen=True)
    code: str
    message: str
    details: str | None = None


# ---------------------------------------------------------------------------
# Concrete event types (discriminated union members)
# ---------------------------------------------------------------------------


class _EventBase(BaseModel):
    """Shared fields for all pipeline events."""

    model_config = ConfigDict(frozen=True)
    correlation_id: str = Field(default_factory=_new_correlation_id)
    timestamp: datetime = Field(default_factory=_utcnow)
    schema_version: str = "1.0.0"


class SpeechStartedEvent(_EventBase):
    event_type: Literal[EventType.SPEECH_STARTED] = EventType.SPEECH_STARTED
    source_stage: Literal[PipelineStage.ORCHESTRATOR] = PipelineStage.ORCHESTRATOR
    payload: SpeechStartedPayload


class TranscriptionProvisionalEvent(_EventBase):
    event_type: Literal[EventType.TRANSCRIPTION_PROVISIONAL] = EventType.TRANSCRIPTION_PROVISIONAL
    source_stage: Literal[PipelineStage.ASR] = PipelineStage.ASR
    payload: TranscriptionProvisionalPayload


class TranscriptionFinalEvent(_EventBase):
    event_type: Literal[EventType.TRANSCRIPTION_FINAL] = EventType.TRANSCRIPTION_FINAL
    source_stage: Literal[PipelineStage.ASR] = PipelineStage.ASR
    payload: TranscriptionFinalPayload


class LLMTokenEvent(_EventBase):
    event_type: Literal[EventType.LLM_TOKEN_GENERATED] = EventType.LLM_TOKEN_GENERATED
    source_stage: Literal[PipelineStage.LLM] = PipelineStage.LLM
    payload: LLMTokenPayload


class TTSAudioChunkEvent(_EventBase):
    event_type: Literal[EventType.TTS_AUDIO_CHUNK] = EventType.TTS_AUDIO_CHUNK
    source_stage: Literal[PipelineStage.TTS] = PipelineStage.TTS
    payload: TTSAudioChunkPayload


class ErrorEvent(_EventBase):
    event_type: Literal[EventType.ERROR] = EventType.ERROR
    source_stage: PipelineStage = PipelineStage.ORCHESTRATOR
    payload: ErrorPayload


# ---------------------------------------------------------------------------
# Discriminated union type
# ---------------------------------------------------------------------------

PipelineEvent = Annotated[
    SpeechStartedEvent
    | TranscriptionProvisionalEvent
    | TranscriptionFinalEvent
    | LLMTokenEvent
    | TTSAudioChunkEvent
    | ErrorEvent,
    Field(discriminator="event_type"),
]
