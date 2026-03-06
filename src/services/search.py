"""Web search service adapter — Tavily API integration.

Provides real-time web search capability for queries that need current
information (weather, news, stocks, current events, factual lookups).
"""

from __future__ import annotations

import httpx

from src.config import config
from src.telemetry.logger import logger


async def web_search(
    query: str,
    *,
    search_depth: str = "advanced",
    max_results: int = 5,
    correlation_id: str,
) -> str:
    """Execute a web search via Tavily API and return formatted results.

    Args:
        query: The search query string.
        search_depth: "basic" (faster) or "advanced" (more thorough).
        max_results: Maximum number of results to return (1-5).
        correlation_id: For telemetry/logging.

    Returns:
        A formatted string of search results suitable for LLM context injection.
        Returns empty string on failure.
    """
    api_key = config.provider.search_api_key
    if not api_key:
        logger.warning(
            "Search API key not configured — skipping web search",
            correlation_id=correlation_id,
            pipeline_stage="search",
        )
        return ""

    timeout = httpx.Timeout(
        connect=config.service_timeout.connect_timeout,
        read=config.service_timeout.search_timeout,
        write=config.service_timeout.search_timeout,
        pool=config.service_timeout.connect_timeout,
    )

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        # Format results for LLM context injection
        formatted = _format_search_results(data, query)

        logger.info(
            f"🔍 Web search completed: query='{query}', results={len(data.get('results', []))}",
            correlation_id=correlation_id,
            pipeline_stage="search",
        )

        return formatted

    except httpx.TimeoutException:
        logger.error(
            "Search provider timeout",
            correlation_id=correlation_id,
            pipeline_stage="search",
        )
        return ""
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"Search provider HTTP error: {exc.response.status_code}",
            correlation_id=correlation_id,
            pipeline_stage="search",
        )
        return ""
    except Exception as exc:
        logger.error(
            f"Search adapter error: {exc}",
            correlation_id=correlation_id,
            pipeline_stage="search",
        )
        return ""


def _format_search_results(data: dict, query: str) -> str:
    """Format Tavily API response into a clean context string for the LLM.

    Args:
        data: Raw Tavily API response.
        query: The original search query.

    Returns:
        Formatted string with answer and source summaries.
    """
    parts: list[str] = []

    # Tavily's AI-generated answer (if available)
    answer = data.get("answer")
    if answer:
        parts.append(f"Quick Answer: {answer}")

    # Individual search results
    results = data.get("results", [])
    if results:
        parts.append("\nSearch Results:")
        for i, result in enumerate(results[:5], 1):
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")
            # Truncate content to keep context window manageable
            if len(content) > 300:
                content = content[:300] + "..."
            parts.append(f"{i}. {title}\n   {content}\n   Source: {url}")

    if not parts:
        return f"No search results found for: {query}"

    return "\n".join(parts)
