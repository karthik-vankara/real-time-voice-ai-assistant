"""Mock provider services for testing without real API keys.

Provides FastAPI endpoints that simulate ASR, LLM, and TTS responses.
Useful for validating the pipeline architecture before integrating real providers.

Usage:
    python -m src.mock_providers
    # Serves on http://localhost:9000 (multi-service)
    # /asr/stream       (9001 in production, but mux on 9000)
    # /llm/stream       (9002 in production)
    # /tts/stream       (9003 in production)

Or via uvicorn:
    uvicorn src.mock_providers:app --port 9000 --host 0.0.0.0
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

app = FastAPI(title="Mock Providers", description="Mock ASR/LLM/TTS for testing")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "mock_providers"}


# ============================================================================
# ASR Mock (Speech-to-Text)
# ============================================================================


async def _asr_stream_generator() -> AsyncIterator[str]:
    """Simulate streaming ASR response with provisional and final transcriptions."""
    responses = [
        {"text": "hello", "is_final": False},
        {"text": "hello world", "is_final": False},
        {"text": "hello world how are", "is_final": False},
        {"text": "hello world how are you", "is_final": True},
    ]
    for resp in responses:
        await asyncio.sleep(0.05)  # Simulate latency
        yield json.dumps(resp) + "\n"


@app.post("/asr/stream")
async def asr_stream(request: Request):
    """Mock ASR streaming endpoint.

    Receives: Raw PCM audio bytes
    Returns: Newline-delimited JSON with {"text": str, "is_final": bool}
    """
    # Consume the body (simulate reading audio)
    await request.body()

    async def generate():
        async for line in _asr_stream_generator():
            yield line

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ============================================================================
# LLM Mock (Language Model)
# ============================================================================


async def _llm_stream_generator(user_text: str) -> AsyncIterator[str]:
    """Simulate token-by-token LLM response streaming."""
    # Mock response based on user input
    if "hello" in user_text.lower():
        tokens = ["Hello!", " How", " are", " you", " doing", "?"]
    elif "name" in user_text.lower():
        tokens = ["I'm", " Claude", ",", " an", " AI", " assistant", "."]
    else:
        tokens = ["That's", " an", " interesting", " question", "."]

    for token in tokens:
        await asyncio.sleep(0.02)  # Simulate token latency
        yield json.dumps({"token": token, "done": False}) + "\n"

    yield json.dumps({"token": "", "done": True}) + "\n"


@app.post("/llm/stream")
async def llm_stream(request: Request):
    """Mock LLM streaming endpoint.

    Receives: JSON with {"messages": [...], "stream": true}
    Returns: Newline-delimited JSON with {"token": str, "done": bool}
    """
    try:
        body = await request.json()
        messages = body.get("messages", [])
        user_text = messages[-1].get("content", "hello") if messages else "hello"
    except Exception:
        user_text = "hello"

    async def generate():
        async for line in _llm_stream_generator(user_text):
            yield line

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ============================================================================
# TTS Mock (Text-to-Speech)
# ============================================================================


def _generate_mock_audio() -> bytes:
    """Generate a simple 1-second 16-bit PCM audio tone (440 Hz sine wave).

    Returns:
        16-bit PCM audio bytes (16kHz, mono, 1 second)
    """
    import math

    sample_rate = 16_000
    frequency = 440  # A4 tone
    duration = 1  # 1 second

    samples = []
    for i in range(int(sample_rate * duration)):
        t = i / sample_rate
        sample = int(32767 * math.sin(2 * math.pi * frequency * t))
        # Convert to 16-bit signed little-endian
        samples.append(sample.to_bytes(2, byteorder="little", signed=True))

    return b"".join(samples)


async def _tts_stream_generator(text: str) -> AsyncIterator[str]:
    """Simulate streaming TTS response with audio chunks."""
    audio_bytes = _generate_mock_audio()

    # Split into 2 chunks
    chunk_size = len(audio_bytes) // 2
    chunks = [
        audio_bytes[:chunk_size],
        audio_bytes[chunk_size:],
    ]

    for idx, chunk in enumerate(chunks):
        await asyncio.sleep(0.05)  # Simulate synthesis latency
        audio_b64 = base64.b64encode(chunk).decode()
        response = {
            "audio_b64": audio_b64,
            "chunk_index": idx,
            "is_last": idx == len(chunks) - 1,
        }
        yield json.dumps(response) + "\n"


@app.post("/tts/stream")
async def tts_stream(request: Request):
    """Mock TTS streaming endpoint.

    Receives: JSON with {"text": str}
    Returns: Newline-delimited JSON with
             {"audio_b64": str, "chunk_index": int, "is_last": bool}
    """
    try:
        body = await request.json()
        text = body.get("text", "hello")
    except Exception:
        text = "hello"

    async def generate():
        async for line in _tts_stream_generator(text):
            yield line

    return StreamingResponse(generate(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting mock providers on http://localhost:9000")
    print("   ASR:  POST http://localhost:9000/asr/stream")
    print("   LLM:  POST http://localhost:9000/llm/stream")
    print("   TTS:  POST http://localhost:9000/tts/stream")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")
