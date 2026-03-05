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


def _pcm_to_wav(audio_pcm: bytes, sample_rate: int = 16000, channels: int = 1, bit_depth: int = 16) -> bytes:
    """Convert raw 16-bit PCM audio to WAV format (RIFF container + PCM data).
    
    WAV file structure:
    - RIFF header (12 bytes)
    - fmt chunk (24 bytes)
    - data chunk header (8 bytes) + data
    """
    bytes_per_sample = bit_depth // 8
    num_samples = len(audio_pcm) // bytes_per_sample
    byte_rate = sample_rate * channels * bytes_per_sample
    block_align = channels * bytes_per_sample
    
    # fmt chunk
    fmt_chunk = b'fmt '
    fmt_size = 16
    audio_format = 1  # PCM
    fmt_data = (
        fmt_size.to_bytes(4, 'little') +
        audio_format.to_bytes(2, 'little') +
        channels.to_bytes(2, 'little') +
        sample_rate.to_bytes(4, 'little') +
        byte_rate.to_bytes(4, 'little') +
        block_align.to_bytes(2, 'little') +
        bit_depth.to_bytes(2, 'little')
    )
    
    # data chunk
    data_chunk = b'data' + len(audio_pcm).to_bytes(4, 'little') + audio_pcm
    
    # RIFF header
    file_size = 4 + (8 + len(fmt_data)) + (8 + len(audio_pcm))
    riff_header = b'RIFF' + file_size.to_bytes(4, 'little') + b'WAVE'
    
    return riff_header + fmt_chunk + fmt_data + data_chunk


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
        
        # Convert raw PCM to WAV format (Whisper requires valid audio file)
        wav_data = _pcm_to_wav(audio_data, sample_rate=16000, channels=1, bit_depth=16)
        
        # Prepare headers
        headers = {}
        if config.provider.asr_api_key:
            headers["Authorization"] = f"Bearer {config.provider.asr_api_key}"
        
        # Send as multipart form data with WAV file
        files = {
            "file": ("audio.wav", wav_data, "audio/wav"),
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
            
            # Emit transcription as final
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
        
        # Convert raw PCM to WAV format
        wav_data = _pcm_to_wav(audio_data, sample_rate=16000, channels=1, bit_depth=16)
        
        # Send as multipart form data
        files = {
            "file": ("audio.wav", wav_data, "audio/wav"),
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
