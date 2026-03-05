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
    """Stream tokens from the LLM provider.

    Protocol contract:
    - POST JSON body: ``{"messages": [...], "stream": true}``
    - Response: newline-delimited JSON with ``{"token": str, "done": bool}``
    """
    provider_url = provider_url or config.provider.llm_url
    messages = [*context, {"role": "user", "content": user_text}]
    payload = {"messages": messages, "stream": True}

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
                if not line.strip():
                    continue
                data = json.loads(line)
                token: str = data.get("token", "")
                accumulated += token
                yield LLMTokenEvent(
                    correlation_id=correlation_id,
                    payload=LLMTokenPayload(
                        token=token,
                        accumulated_text=accumulated,
                    ),
                )
                if data.get("done", False):
                    break
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
