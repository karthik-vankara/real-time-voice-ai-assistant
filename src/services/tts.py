"""TTS service adapter — async streaming interface (FR-005).

Accepts text tokens, yields audio chunks.  Provider URL is configurable.
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator  # noqa: TC003

import httpx

from src.config import config
from src.models.events import TTSAudioChunkEvent, TTSAudioChunkPayload
from src.telemetry.logger import logger


async def synthesize_stream(
    text: str,
    *,
    correlation_id: str,
    provider_url: str | None = None,
) -> AsyncIterator[TTSAudioChunkEvent]:
    """Stream audio chunks from the TTS provider.

    Protocol contract:
    - POST JSON body: ``{"text": str}``
    - Response: newline-delimited JSON with
      ``{"audio_b64": str, "chunk_index": int, "is_last": bool}``
    """
    provider_url = provider_url or config.provider.tts_url
    payload = {"text": text}
    timeout = httpx.Timeout(
        connect=config.service_timeout.connect_timeout,
        read=config.service_timeout.tts_timeout,
        write=config.service_timeout.tts_timeout,
        pool=config.service_timeout.connect_timeout,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client, client.stream(
            "POST",
            provider_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as response:
            response.raise_for_status()
            chunk_idx = 0
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                data = json.loads(line)
                audio_b64: str = data.get("audio_b64", "")
                is_last: bool = data.get("is_last", False)

                yield TTSAudioChunkEvent(
                    correlation_id=correlation_id,
                    payload=TTSAudioChunkPayload(
                        audio_b64=audio_b64,
                        chunk_index=chunk_idx,
                        is_last=is_last,
                    ),
                )
                chunk_idx += 1
    except httpx.TimeoutException:
        logger.error(
            "TTS provider timeout",
            correlation_id=correlation_id,
            pipeline_stage="tts",
        )
        raise
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"TTS provider HTTP error: {exc.response.status_code}",
            correlation_id=correlation_id,
            pipeline_stage="tts",
        )
        raise
    except Exception as exc:
        logger.error(
            f"TTS adapter error: {exc}",
            correlation_id=correlation_id,
            pipeline_stage="tts",
        )
        raise


async def synthesize_full(
    text: str,
    *,
    correlation_id: str,
    provider_url: str | None = None,
) -> bytes:
    """Non-streaming convenience: synthesize full audio and return raw bytes."""
    provider_url = provider_url or config.provider.tts_url
    chunks: list[bytes] = []
    async for event in synthesize_stream(
        text, correlation_id=correlation_id, provider_url=provider_url
    ):
        chunks.append(base64.b64decode(event.payload.audio_b64))
    return b"".join(chunks)
