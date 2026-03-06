"""LLM service adapter — async streaming interface (FR-003, FR-004, FR-005).

Accepts transcription text + conversation context, yields token-by-token
response events.  Provider URL is configurable.

Supports OpenAI function calling (tools API) for intent detection:
when the LLM decides it needs web search or factual lookup, it returns
a tool call instead of a text response.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator  # noqa: TC003
from dataclasses import dataclass

import httpx

from src.config import config
from src.models.events import LLMTokenEvent, LLMTokenPayload
from src.telemetry.logger import logger


# ---------------------------------------------------------------------------
# Tool call signal — raised when LLM wants to call a function
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRequest:
    """Represents a tool call requested by the LLM via function calling."""

    name: str
    arguments: dict
    tool_call_id: str


class ToolCallRequested(Exception):
    """Raised when the LLM streams a tool call instead of a text response.

    The orchestrator catches this and dispatches the tool call (e.g., web search).
    """

    def __init__(self, tool_call: ToolCallRequest) -> None:
        self.tool_call = tool_call
        super().__init__(f"LLM requested tool call: {tool_call.name}")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a helpful voice assistant. Keep responses concise (1-3 sentences) "
    "and clear for text-to-speech conversion. Avoid lists and technical jargon. "
    "When you receive web search results, always cite the EXACT numbers and facts "
    "from the search results — never round, estimate, or paraphrase numerical data. "
    "Mention the source when relevant."
)


# ---------------------------------------------------------------------------
# Streaming response generator
# ---------------------------------------------------------------------------

async def generate_response_stream(
    user_text: str,
    context: list[dict[str, str]],
    *,
    correlation_id: str,
    provider_url: str | None = None,
    tools: list[dict] | None = None,
) -> AsyncIterator[LLMTokenEvent]:
    """Stream tokens from the LLM provider (OpenAI Chat API format).

    When *tools* are provided and the LLM decides to call one, this function
    raises ``ToolCallRequested`` instead of yielding tokens.

    OpenAI returns Server-Sent Events (SSE):
    data: {"choices":[{"delta":{"content":"token"}}]}
    """
    provider_url = provider_url or config.provider.llm_url
    system_message = {"role": "system", "content": SYSTEM_PROMPT}
    messages = [system_message, *context, {"role": "user", "content": user_text}]
    payload: dict = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }

    # Include tools for function calling (intent detection)
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

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

            # Track tool call state across streamed chunks
            tool_call_id = ""
            tool_call_name = ""
            tool_call_args = ""
            is_tool_call = False

            async for line in response.aiter_lines():
                if not line.strip() or not line.startswith("data: "):
                    continue

                try:
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break

                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    # --- Check for tool calls (function calling) ---
                    tool_calls = delta.get("tool_calls")
                    if tool_calls:
                        is_tool_call = True
                        tc = tool_calls[0]
                        # First chunk has id and function name
                        if tc.get("id"):
                            tool_call_id = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            tool_call_name = fn["name"]
                        if fn.get("arguments"):
                            tool_call_args += fn["arguments"]
                        continue

                    # --- Regular text token ---
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

            # After stream ends, check if we got a complete tool call
            if is_tool_call and tool_call_name:
                try:
                    args = json.loads(tool_call_args) if tool_call_args else {}
                except json.JSONDecodeError:
                    args = {"query": user_text}  # Fallback: use original text

                logger.info(
                    f"🔧 LLM requested tool call: {tool_call_name}({args})",
                    correlation_id=correlation_id,
                    pipeline_stage="llm",
                )
                raise ToolCallRequested(
                    ToolCallRequest(
                        name=tool_call_name,
                        arguments=args,
                        tool_call_id=tool_call_id,
                    )
                )

    except ToolCallRequested:
        raise  # Re-raise tool call requests — orchestrator handles them
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


# ---------------------------------------------------------------------------
# Second-pass streaming (after tool execution)
# ---------------------------------------------------------------------------

async def generate_response_with_tool_result(
    messages: list[dict],
    *,
    correlation_id: str,
    provider_url: str | None = None,
) -> AsyncIterator[LLMTokenEvent]:
    """Stream the LLM's final response after a tool call has been executed.

    This is "LLM call #2": the messages list includes the original conversation,
    the assistant's tool call, and the tool result. The LLM synthesizes everything
    into a natural spoken response.

    No tools are passed here — this call should always produce text.
    Uses temperature=0 for deterministic, accurate responses.
    Uses gpt-4o for better instruction following on factual data.
    """
    provider_url = provider_url or config.provider.llm_url
    payload: dict = {
        "model": "gpt-4o",
        "messages": messages,
        "stream": True,
        "temperature": 0,
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

                try:
                    data_str = line[6:]
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
            "LLM provider timeout (tool result pass)",
            correlation_id=correlation_id,
            pipeline_stage="llm",
        )
        raise
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"LLM provider HTTP error (tool result pass): {exc.response.status_code}",
            correlation_id=correlation_id,
            pipeline_stage="llm",
        )
        raise
    except Exception as exc:
        logger.error(
            f"LLM adapter error (tool result pass): {exc}",
            correlation_id=correlation_id,
            pipeline_stage="llm",
        )
        raise


# ---------------------------------------------------------------------------
# Non-streaming convenience
# ---------------------------------------------------------------------------

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
    return accumulated
