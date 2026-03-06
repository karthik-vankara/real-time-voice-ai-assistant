"""OpenAI function calling tool definitions.

Defines the tools (functions) that the LLM can invoke during conversation.
When the LLM determines it needs real-time data, it will call one of these
tools, and the orchestrator will execute the corresponding service.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Tool definitions for OpenAI Chat Completions API (function calling)
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the internet for real-time or current information. "
            "Use this for: weather, news, stock prices, sports scores, "
            "current events, recent happenings, or any query that requires "
            "up-to-date data that you don't have in your training data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web.",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["general", "news"],
                    "description": (
                        "Type of search: 'general' for broad web search, "
                        "'news' for recent news articles."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

FACTUAL_LOOKUP_TOOL = {
    "type": "function",
    "function": {
        "name": "factual_lookup",
        "description": (
            "Look up a specific factual claim or piece of information that "
            "may need verification. Use this for: 'who is the president of...', "
            "'what is the population of...', 'when did X happen', or any "
            "verifiable factual question where accuracy is critical."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The factual question to verify via web search.",
                },
            },
            "required": ["query"],
        },
    },
}

# All tools available to the LLM
AVAILABLE_TOOLS: list[dict] = [WEB_SEARCH_TOOL, FACTUAL_LOOKUP_TOOL]

# Map tool names to their definitions for quick lookup
TOOL_REGISTRY: dict[str, dict] = {
    tool["function"]["name"]: tool for tool in AVAILABLE_TOOLS
}
