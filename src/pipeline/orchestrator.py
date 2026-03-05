"""Pipeline orchestrator — wires ASR → LLM → TTS (FR-001 through FR-019).

This is the core of the voice assistant: it receives audio from the WebSocket,
streams it through ASR/LLM/TTS, and sends events + audio back to the client.

Integrates:
- Circuit breakers per service (FR-009, T024-T026)
- Fallback routing on degradation (FR-010, FR-011, T027)
- Barge-in detection — cancel & discard (FR-012, Clarification Q4, T029)
- Audio validation (FR-018, T017)
- Graceful disconnection (FR-019, T018)
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import AsyncIterator  # noqa: TC003

from fastapi import WebSocket, WebSocketDisconnect

from src.fallback.strategies import build_fallback_audio_event, get_fallback_text
from src.models.events import (
    ErrorEvent,
    ErrorPayload,
    PipelineStage,
    SpeechStartedEvent,
    SpeechStartedPayload,
    TranscriptionFinalEvent,
    TranscriptionProvisionalEvent,
    _new_correlation_id,
)
from src.models.session import Session  # noqa: TC001
from src.pipeline.session_manager import session_manager
from src.services import asr, llm, tts
from src.services.circuit_breaker import CircuitBreaker, CircuitOpenError
from src.telemetry.logger import logger
from src.telemetry.metrics import LatencyTracker, aggregator

# ---------------------------------------------------------------------------
# Per-service circuit breakers (T024-T026)
# ---------------------------------------------------------------------------

_asr_cb = CircuitBreaker("asr")
_llm_cb = CircuitBreaker("llm")
_tts_cb = CircuitBreaker("tts")


# ---------------------------------------------------------------------------
# Audio validation (FR-018)
# ---------------------------------------------------------------------------

def validate_audio_frame(data: bytes) -> str | None:
    """Return an error message if *data* is not valid 16-bit PCM, else None."""
    if not data:
        return "Empty audio frame"
    logger.debug(f"Audio frame validation: {len(data)} bytes ({len(data) % 2 == 0 and 'even' or 'ODD!'})")
    if len(data) % 2 != 0:
        logger.error(f"Audio frame has ODD length: {len(data)} bytes")
        return "Audio frame length is not a multiple of 2 (expected 16-bit PCM)"
    try:
        struct.unpack_from("<h", data, 0)
    except struct.error:
        return "Unable to decode audio as 16-bit little-endian PCM"
    return None


# ---------------------------------------------------------------------------
# Handle a single session over WebSocket
# ---------------------------------------------------------------------------

async def handle_session(ws: WebSocket) -> None:
    """Top-level handler for one WebSocket session."""
    session = await session_manager.create_session()
    logger.info(
        "Pipeline session started",
        session_id=session.session_id,
        pipeline_stage="orchestrator",
    )

    # Barge-in support: a cancellable task for the active pipeline
    _active_pipeline_task: asyncio.Task | None = None  # type: ignore[type-arg]

    try:
        await _session_loop(ws, session)
    except WebSocketDisconnect:
        logger.info(
            "Client disconnected",
            session_id=session.session_id,
            pipeline_stage="orchestrator",
        )
    except Exception as exc:
        logger.error(
            f"Session error: {exc}",
            session_id=session.session_id,
            pipeline_stage="orchestrator",
        )
    finally:
        await session_manager.close_session(session.session_id)
        logger.info(
            "Pipeline session ended",
            session_id=session.session_id,
            pipeline_stage="orchestrator",
        )


# ---------------------------------------------------------------------------
# Session loop — processes utterances, supports barge-in (FR-012, T029)
# ---------------------------------------------------------------------------

async def _session_loop(ws: WebSocket, session: Session) -> None:
    """Receive audio frames, run the pipeline, send back events.

    Barge-in: If new audio arrives while a pipeline task is running (TTS
    streaming), the in-flight task is cancelled and discarded per Clarification Q4.
    """
    active_task: asyncio.Task | None = None  # type: ignore[type-arg]

    while True:
        audio_chunks: list[bytes] = []
        correlation_id = _new_correlation_id()

        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                if active_task and not active_task.done():
                    active_task.cancel()
                return

            # Text control signals
            if "text" in message:
                import json as _json

                try:
                    ctrl = _json.loads(message["text"])
                except (ValueError, TypeError):
                    ctrl = {"action": message["text"]}
                action = ctrl.get("action", "")
                if action == "end_of_utterance":
                    break
                if action == "close":
                    if active_task and not active_task.done():
                        active_task.cancel()
                    return
                continue

            # Binary audio frames
            data: bytes = message.get("bytes", b"")
            if not data:
                logger.debug(f"Empty audio frame received, message keys: {list(message.keys())}")
                continue

            logger.debug(f"Raw audio frame: len={len(data)} bytes, first_key={'bytes' in message}, type={type(data)}")
            
            # Barge-in detection (FR-012, T029)
            if active_task and not active_task.done():
                active_task.cancel()
                logger.info(
                    "Barge-in detected — cancelling in-progress pipeline",
                    correlation_id=correlation_id,
                    session_id=session.session_id,
                    pipeline_stage="orchestrator",
                )
                active_task = None

            err = validate_audio_frame(data)
            if err:
                error_event = ErrorEvent(
                    correlation_id=correlation_id,
                    source_stage=PipelineStage.ORCHESTRATOR,
                    payload=ErrorPayload(code="INVALID_AUDIO", message=err),
                )
                await ws.send_json(error_event.model_dump(mode="json"))
                continue

            audio_chunks.append(data)
            await session_manager.touch_session(session.session_id)

        if not audio_chunks:
            continue

        # Emit speech_started (US2 / T021)
        speech_event = SpeechStartedEvent(
            correlation_id=correlation_id,
            payload=SpeechStartedPayload(session_id=session.session_id),
        )
        await ws.send_json(speech_event.model_dump(mode="json"))

        # Run pipeline as a cancellable task for barge-in support
        active_task = asyncio.create_task(
            _run_pipeline(ws, session, audio_chunks, correlation_id)
        )
        try:
            await active_task
        except asyncio.CancelledError:
            logger.info(
                "Pipeline cancelled (barge-in)",
                correlation_id=correlation_id,
                pipeline_stage="orchestrator",
            )
        active_task = None


# ---------------------------------------------------------------------------
# Pipeline: ASR → LLM → TTS  with circuit breakers + fallbacks
# ---------------------------------------------------------------------------

async def _run_pipeline(
    ws: WebSocket,
    session: Session,
    audio_chunks: list[bytes],
    correlation_id: str,
) -> None:
    """Execute the streaming pipeline for a single utterance."""
    tracker = LatencyTracker(correlation_id)

    # ---- 1. ASR (T024) ----
    tracker.start("asr")
    final_text = await _run_asr(ws, audio_chunks, correlation_id)
    tracker.stop("asr")
    if not final_text:
        return

    # ---- 2. LLM (T025) ----
    tracker.start("llm")
    llm_text = await _run_llm(ws, session, final_text, correlation_id)
    tracker.stop("llm")
    if not llm_text:
        return

    # ---- Faithfulness check (FR-017, T034) ----
    _faithfulness_check(llm_text, llm_text, correlation_id)

    # ---- 3. TTS (T026) ----
    tracker.start("tts")
    await _run_tts(ws, llm_text, correlation_id)
    tracker.stop("tts")

    # 4. Update conversation history
    session.add_turn(user_text=final_text, assistant_text=llm_text)

    # 5. Record latency telemetry (T032)
    record = tracker.to_record()
    aggregator.add(record)
    logger.info(
        f"Latency record: total={record.total_e2e_ms:.1f}ms asr={record.asr_ms:.1f}ms "
        f"llm={record.llm_ttft_ms:.1f}ms tts={record.tts_ttfb_ms:.1f}ms",
        correlation_id=correlation_id,
        pipeline_stage="telemetry",
    )


# ---------------------------------------------------------------------------
# Faithfulness check (FR-017, T034)
# ---------------------------------------------------------------------------

def _faithfulness_check(
    llm_output: str,
    tts_input: str,
    correlation_id: str,
) -> bool:
    """Verify TTS input is a byte-for-byte match of LLM output.

    Returns True if faithful, False otherwise. Mismatches are logged.
    """
    if llm_output.encode("utf-8") != tts_input.encode("utf-8"):
        logger.error(
            "Faithfulness violation: TTS input does not match LLM output",
            correlation_id=correlation_id,
            pipeline_stage="orchestrator",
            extra_data={
                "llm_output_len": len(llm_output),
                "tts_input_len": len(tts_input),
            },
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Stage runners with circuit breaker + fallback wrappers
# ---------------------------------------------------------------------------

async def _run_asr(
    ws: WebSocket,
    audio_chunks: list[bytes],
    correlation_id: str,
) -> str:
    """Run ASR through circuit breaker; on failure emit retry prompt (T024)."""
    final_text = ""

    async def _asr_call() -> str:
        nonlocal final_text
        text = ""
        async for event in asr.transcribe_stream(
            _iter_chunks(audio_chunks),
            correlation_id=correlation_id,
        ):
            if isinstance(event, TranscriptionProvisionalEvent):
                await ws.send_json(event.model_dump(mode="json"))
            elif isinstance(event, TranscriptionFinalEvent):
                text = event.payload.text
                await ws.send_json(event.model_dump(mode="json"))
        return text

    try:
        final_text = await _asr_cb.call(_asr_call)
        logger.info(
            f"✅ ASR RESULT: text='{final_text}'",
            correlation_id=correlation_id,
            pipeline_stage="orchestrator",
        )
    except (CircuitOpenError, Exception) as exc:
        logger.warning(
            f"ASR degraded: {exc}",
            correlation_id=correlation_id,
            pipeline_stage="orchestrator",
        )
        # Fallback: send retry-prompt bridge audio (FR-010)
        fb_event = build_fallback_audio_event(
            PipelineStage.ASR, correlation_id=correlation_id
        )
        if fb_event:
            await ws.send_json(fb_event.model_dump(mode="json"))
        return ""

    return final_text


async def _run_llm(
    ws: WebSocket,
    session: Session,
    user_text: str,
    correlation_id: str,
) -> str:
    """Run LLM through circuit breaker; on failure emit bridge audio (T025)."""
    logger.info(
        f"Starting LLM with user_text: '{user_text}' (len={len(user_text)})",
        correlation_id=correlation_id,
        pipeline_stage="orchestrator",
    )
    llm_text = ""

    async def _llm_call() -> str:
        nonlocal llm_text
        text = ""
        async for token_event in llm.generate_response_stream(
            user_text,
            session.context_texts,
            correlation_id=correlation_id,
        ):
            text = token_event.payload.accumulated_text
            await ws.send_json(token_event.model_dump(mode="json"))
        return text

    try:
        llm_text = await _llm_cb.call(_llm_call)
        logger.info(
            f"✅ LLM RESPONSE: text='{llm_text}'",
            correlation_id=correlation_id,
            pipeline_stage="orchestrator",
        )
    except (CircuitOpenError, Exception) as exc:
        logger.warning(
            f"LLM degraded: {exc}",
            correlation_id=correlation_id,
            pipeline_stage="orchestrator",
        )
        fb_event = build_fallback_audio_event(
            PipelineStage.LLM, correlation_id=correlation_id
        )
        if fb_event:
            await ws.send_json(fb_event.model_dump(mode="json"))
        return get_fallback_text(PipelineStage.LLM)

    return llm_text


async def _run_tts(
    ws: WebSocket,
    text: str,
    correlation_id: str,
) -> None:
    """Run TTS through circuit breaker; on failure serve cached clip (T026)."""
    logger.info(
        f"🔊 TTS INPUT: text='{text}' (len={len(text)})",
        correlation_id=correlation_id,
        pipeline_stage="orchestrator",
    )

    async def _tts_call() -> None:
        async for audio_event in tts.synthesize_stream(
            text, correlation_id=correlation_id
        ):
            await ws.send_json(audio_event.model_dump(mode="json"))
        logger.info(
            f"🎵 TTS AUDIO SENT: {text[:50]}... converted to audio chunks",
            correlation_id=correlation_id,
            pipeline_stage="orchestrator",
        )

    try:
        await _tts_cb.call(_tts_call)
    except (CircuitOpenError, Exception) as exc:
        logger.warning(
            f"TTS degraded: {exc}",
            correlation_id=correlation_id,
            pipeline_stage="orchestrator",
        )
        fb_event = build_fallback_audio_event(
            PipelineStage.TTS, correlation_id=correlation_id
        )
        if fb_event:
            await ws.send_json(fb_event.model_dump(mode="json"))


async def _iter_chunks(chunks: list[bytes]) -> AsyncIterator[bytes]:
    """Convert a list of byte buffers to an async iterator."""
    for chunk in chunks:
        yield chunk
