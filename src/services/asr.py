"""ASR service adapter — async streaming interface (FR-001, FR-002).

Accepts audio chunks, yields transcription events.  The adapter
communicates with an external ASR provider via HTTP.
Provider URL is configurable. For OpenAI Whisper, sends multipart/form-data.

In Phase 4 (US2) this adapter is extended to emit provisional events.
In Phase 5 (US3) calls are wrapped with a circuit breaker.
"""

from __future__ import annotations

from collections.abc import AsyncIterator  # noqa: TC003
import json

import httpx

from src.config import config
from src.models.events import (
    TranscriptionFinalEvent,
    TranscriptionFinalPayload,
    TranscriptionProvisionalEvent,
    TranscriptionProvisionalPayload,
)
from src.telemetry.logger import logger


async def transcribe_stream(
    audio_chunks: AsyncIterator[bytes],
    *,
    correlation_id: str,
    provider_url: str | None = None,
) -> AsyncIterator[TranscriptionFinalEvent | TranscriptionProvisionalEvent]:
    """Stream audio chunks to the ASR provider and yield transcription events.

    For OpenAI Whisper: collects all chunks, sends as multipart/form-data.
    Response: JSON with {"text": str}
    """
    provider_url = provider_url or config.provider.asr_url
    timeout = httpx.Timeout(
        connect=config.service_timeout.connect_timeout,
        read=config.service_timeout.asr_timeout,
        write=config.service_timeout.asr_timeout,
        pool=config.service_timeout.connect_timeout,
    )

    try:
        # Collect all audio chunks
        audio_data = b""
        async for chunk in audio_chunks:
            audio_data += chunk
        
        # Prepare headers
        headers = {}
        if config.provider.asr_api_key:
            headers["Authorization"] = f"Bearer {config.provider.asr_api_key}"
        
        # Send as multipart form data (OpenAI Whisper format)
        files = {
            "file": ("audio.wav", audio_data, "audio/wav"),
            "model": (None, "whisper-1"),
        }
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                provider_url,
                files=files,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            text: str = data.get("text", "")
            
            # Emit transcription as final (no streaming from Whisper API)
            yield TranscriptionFinalEvent(
                correlation_id=correlation_id,
                payload=TranscriptionFinalPayload(text=text),
            )
    except httpx.TimeoutException:
        logger.error(
            "ASR provider timeout",
            correlation_id=correlation_id,
            pipeline_stage="asr",
        )
        raise
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"ASR provider HTTP error: {exc.response.status_code}",
            correlation_id=correlation_id,
            pipeline_stage="asr",
        )
        raise
    except Exception as exc:
        logger.error(
            f"ASR adapter error: {exc}",
            correlation_id=correlation_id,
            pipeline_stage="asr",
        )
        raise


async def transcribe_audio(
    audio_data: bytes,
    *,
    correlation_id: str,
    provider_url: str | None = None,
) -> str:
    """Convenience: transcribe a complete audio buffer and return final text.

    Useful for replay mode and simple callers that don't need streaming.
    """
    provider_url = provider_url or config.provider.asr_url
    timeout = httpx.Timeout(
        connect=config.service_timeout.connect_timeout,
        read=config.service_timeout.asr_timeout,
        write=config.service_timeout.asr_timeout,
        pool=config.service_timeout.connect_timeout,
    )
    try:
        headers = {}
        if config.provider.asr_api_key:
            headers["Authorization"] = f"Bearer {config.provider.asr_api_key}"
        
        # Send as multipart form data (OpenAI Whisper format)
        files = {
            "file": ("audio.wav", audio_data, "audio/wav"),
            "model": (None, "whisper-1"),
        }
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                provider_url,
                files=files,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("text", "")
    except Exception as exc:
        logger.error(
            f"ASR transcribe_audio error: {exc}",
            correlation_id=correlation_id,
            pipeline_stage="asr",
        )
        raise
