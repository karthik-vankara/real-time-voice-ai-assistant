"""LLM service adapter — async streaming interface (FR-003, FR-004, FR-005).

Accepts transcription text + conversation context, yields token-by-token
response events.  Provider URL is configurable.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator  # noqa: TC003

import httpx

from src.config import config
from src.models.events import LLMTokenEvent, LLMTokenPayload
from src.telemetry.logger import logger


async def generate_response_stream(
    user_text: str,
    context: list[dict[str, str]],
    *,
    correlation_id: str,
    provider_url: str | None = None,
) -> AsyncIterator[LLMTokenEvent]:
    """Stream tokens from the LLM provider (OpenAI Chat API format).

    OpenAI returns Server-Sent Events (SSE):
    data: {"choices":[{"delta":{"content":"token"}}]}
    """
    provider_url = provider_url or config.provider.llm_url
    # Add system prompt to guide LLM responses
    system_message = {
        "role": "system",
        "content": "You are a helpful voice assistant. Keep responses concise (1-3 sentences) and clear for text-to-speech conversion. Avoid lists and technical jargon.",
    }
    messages = [system_message, *context, {"role": "user", "content": user_text}]
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }

    timeout = httpx.Timeout(
        connect=config.service_timeout.connect_timeout,
        read=config.service_timeout.llm_timeout,
        write=config.service_timeout.llm_timeout,
        pool=config.service_timeout.connect_timeout,
    )

    try:
        headers = {"Content-Type": "application/json"}
        if config.provider.llm_api_key:
            headers["Authorization"] = f"Bearer {config.provider.llm_api_key}"
        
        async with httpx.AsyncClient(timeout=timeout) as client, client.stream(
            "POST",
            provider_url,
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            accumulated = ""
            async for line in response.aiter_lines():
                if not line.strip() or not line.startswith("data: "):
                    continue
                
                # Parse SSE format: "data: {...}"
                try:
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break
                    
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    
                    delta = choices[0].get("delta", {})
                    token: str = delta.get("content", "")
                    
                    if token:
                        accumulated += token
                        yield LLMTokenEvent(
                            correlation_id=correlation_id,
                            payload=LLMTokenPayload(
                                token=token,
                                accumulated_text=accumulated,
                            ),
                        )
                except json.JSONDecodeError:
                    continue
    except httpx.TimeoutException:
        logger.error(
            "LLM provider timeout",
            correlation_id=correlation_id,
            pipeline_stage="llm",
        )
        raise
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"LLM provider HTTP error: {exc.response.status_code}",
            correlation_id=correlation_id,
            pipeline_stage="llm",
        )
        raise
    except Exception as exc:
        logger.error(
            f"LLM adapter error: {exc}",
            correlation_id=correlation_id,
            pipeline_stage="llm",
        )
        raise


async def generate_response(
    user_text: str,
    context: list[dict[str, str]],
    *,
    correlation_id: str,
    provider_url: str | None = None,
) -> str:
    """Non-streaming convenience: generate full response text."""
    provider_url = provider_url or config.provider.llm_url
    accumulated = ""
    async for event in generate_response_stream(
        user_text, context, correlation_id=correlation_id, provider_url=provider_url
    ):
        accumulated = event.payload.accumulated_text
    return accumulated
