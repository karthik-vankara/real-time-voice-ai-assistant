"""ASR service adapter — async streaming interface (FR-001, FR-002).

Accepts audio chunks, yields transcription events.  The adapter
communicates with an external ASR provider via HTTP streaming (httpx).
Provider URL is configurable.

In Phase 4 (US2) this adapter is extended to emit provisional events.
In Phase 5 (US3) calls are wrapped with a circuit breaker.
"""

from __future__ import annotations

from collections.abc import AsyncIterator  # noqa: TC003

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

    The function acts as an async generator — callers iterate to receive
    events as they arrive from the provider.

    Protocol contract with the ASR provider:
    - POST streaming body (chunked transfer)
    - Response: newline-delimited JSON objects with keys:
      ``{"text": str, "is_final": bool}``
    """
    provider_url = provider_url or config.provider.asr_url
    timeout = httpx.Timeout(
        connect=config.service_timeout.connect_timeout,
        read=config.service_timeout.asr_timeout,
        write=config.service_timeout.asr_timeout,
        pool=config.service_timeout.connect_timeout,
    )

    try:
        headers = {"Content-Type": "application/octet-stream"}
        if config.provider.asr_api_key:
            headers["Authorization"] = f"Bearer {config.provider.asr_api_key}"
        
        async with httpx.AsyncClient(timeout=timeout) as client, client.stream(
            "POST",
            provider_url,
            content=_chunk_sender(audio_chunks),
            headers=headers,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                import json

                data = json.loads(line)
                text: str = data.get("text", "")
                is_final: bool = data.get("is_final", False)

                if is_final:
                    yield TranscriptionFinalEvent(
                        correlation_id=correlation_id,
                        payload=TranscriptionFinalPayload(text=text),
                    )
                else:
                    yield TranscriptionProvisionalEvent(
                        correlation_id=correlation_id,
                        payload=TranscriptionProvisionalPayload(text=text),
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


async def _chunk_sender(audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Adapter to feed audio chunks as an async byte stream for httpx."""
    async for chunk in audio_chunks:
        yield chunk


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
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                provider_url,
                content=audio_data,
                headers={"Content-Type": "application/octet-stream"},
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
