"""TTS service adapter — async streaming interface (FR-005).

Accepts text tokens, yields audio chunks.  Provider URL is configurable.
For OpenAI TTS API, sends HTTP request and receives binary MP3/AAC audio.
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
    """Stream audio chunks from the TTS provider (OpenAI format).

    OpenAI TTS API:
    - POST JSON body: {"model": "tts-1", "input": "text", "voice": "alloy"}
    - Response: Binary audio (MP3 or ACC format)
    - We chunk the binary and encode to base64 for streaming to client
    """
    provider_url = provider_url or config.provider.tts_url
    payload = {
        "model": "tts-1-hd",  # High-quality model for better audio clarity
        "input": text,
        "voice": "nova",  # Better voice quality than 'alloy'
    }
    timeout = httpx.Timeout(
        connect=config.service_timeout.connect_timeout,
        read=config.service_timeout.tts_timeout,
        write=config.service_timeout.tts_timeout,
        pool=config.service_timeout.connect_timeout,
    )

    try:
        headers = {"Content-Type": "application/json"}
        if config.provider.tts_api_key:
            headers["Authorization"] = f"Bearer {config.provider.tts_api_key}"
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                provider_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            
            # Get full binary audio
            audio_bytes = response.content
            
            # Split into chunks (8KB each, same as mock)
            chunk_size = 8192
            total_chunks = (len(audio_bytes) + chunk_size - 1) // chunk_size
            
            for idx in range(total_chunks):
                start = idx * chunk_size
                end = min(start + chunk_size, len(audio_bytes))
                chunk = audio_bytes[start:end]
                is_last = (idx == total_chunks - 1)
                
                # Encode chunk to base64
                audio_b64 = base64.b64encode(chunk).decode()
                
                yield TTSAudioChunkEvent(
                    correlation_id=correlation_id,
                    payload=TTSAudioChunkPayload(
                        audio_b64=audio_b64,
                        chunk_index=idx,
                        is_last=is_last,
                    ),
                )
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
