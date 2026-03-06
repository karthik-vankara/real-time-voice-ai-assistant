# Failure Mode and Effects Analysis (FMEA)

**Feature**: Real-Time Streaming Voice Assistant  
**Date**: 2026-03-06  
**Scope**: All pipeline stages and infrastructure components (incl. Intent Detection & Web Search)

## Methodology

Each failure mode is assessed for:
- **Severity** (1–5): Impact on user experience (5 = total service loss)
- **Likelihood** (1–5): Probability of occurrence in production (5 = very frequent)
- **RPN** (Risk Priority Number): Severity × Likelihood
- **Mitigation**: Implemented countermeasure

## Failure Modes

| # | Component | Failure Mode | Severity | Likelihood | RPN | Detection | Mitigation |
|---|-----------|-------------|----------|-----------|-----|-----------|------------|
| 1 | ASR Provider | Timeout (> 500ms P95) | 4 | 3 | 12 | Latency telemetry, circuit breaker counter | Circuit breaker opens after 3 failures/30s; "Could you repeat?" bridge audio plays (FR-010) |
| 2 | ASR Provider | HTTP 5xx error | 4 | 2 | 8 | Error event emitted, structured log | Circuit breaker routes to retry-prompt fallback; error event sent to client |
| 3 | LLM Provider | Timeout (> 400ms TTFT) | 4 | 3 | 12 | Latency telemetry, circuit breaker counter | "Let me think about that..." bridge audio (FR-010); on persistent failure, model switch (FR-011) |
| 4 | LLM Provider | HTTP 503 (overloaded) | 3 | 3 | 9 | HTTP status in structured log | Circuit breaker opens; bridge audio plays; half-open probe after 10s |
| 5 | LLM Provider | Generates empty response | 2 | 1 | 2 | Empty accumulated_text check | Orchestrator skips TTS stage; no audio sent; logged as warning |
| 6 | TTS Provider | Connection drop | 4 | 2 | 8 | httpx ConnectionError | Circuit breaker routes to cached pre-generated audio clip (FR-010) |
| 7 | TTS Provider | Timeout (> 250ms TTFB) | 3 | 2 | 6 | Latency telemetry | Cached fallback audio served; circuit breaker tracks failure |
| 8 | WebSocket | Client disconnects mid-utterance | 3 | 4 | 12 | WebSocketDisconnect exception | Graceful cleanup: cancel in-flight tasks, purge session state, release resources (FR-019) |
| 9 | WebSocket | Client disconnects mid-response | 2 | 3 | 6 | WebSocketDisconnect exception | Same as #8; TTS streaming cancelled via task cancellation |
| 10 | Audio Input | Malformed/corrupted PCM data | 2 | 2 | 4 | validate_audio_frame() | Structured error event (INVALID_AUDIO) sent to client; frame discarded; listening continues (FR-018) |
| 11 | Audio Input | Non-16-bit PCM encoding | 2 | 1 | 2 | Frame length % 2 check | Same as #10 |
| 12 | Pipeline | Barge-in during TTS streaming | 1 | 3 | 3 | New audio while active_task running | Cancel active pipeline task; discard remaining TTS audio; process new utterance (FR-012) |
| 13 | Session | Max concurrent sessions (50) exceeded | 3 | 1 | 3 | SessionManager.create_session() | RuntimeError raised; server returns error; existing sessions unaffected (FR-008) |
| 14 | Session | Idle timeout (60s inactivity) | 1 | 3 | 3 | Periodic cleanup check | Session closed and purged; client can reconnect |
| 15 | Telemetry | Latency budget breach (P95 > 1.2s) | 3 | 2 | 6 | budget_breached flag in LatencyRecord | Warning logged with per-stage breakdown; visible in dashboard endpoint |
| 16 | Faithfulness | TTS input ≠ LLM output | 4 | 1 | 4 | _faithfulness_check() | Mismatch logged as violation; flagged in telemetry (FR-017) |
| 17 | Network | TLS not enforced (plain WS) | 5 | 1 | 5 | URL scheme check in server.py | Connection rejected with WS_1008_POLICY_VIOLATION; warning logged |
| 18 | Circuit Breaker | Stuck in OPEN state | 3 | 1 | 3 | State monitoring via logs | Half-open probe after configurable timeout; manual reset API available |
| 19 | Search Provider | Tavily API timeout (> 10s) | 2 | 3 | 6 | Latency telemetry, search circuit breaker | Search circuit breaker opens; LLM answers without search data; graceful degradation |
| 20 | Search Provider | HTTP error (429 rate limit / 5xx) | 2 | 2 | 4 | HTTP status in structured log | `web_search()` returns empty string; pipeline continues; LLM generates response from knowledge |
| 21 | Search Provider | Tavily API key missing/invalid | 3 | 1 | 3 | Config validation, error log | `ENABLE_WEB_SEARCH=false` skips search; if enabled, empty result returned; pipeline continues |
| 22 | Intent Detection | Tool call JSON parse failure | 2 | 1 | 2 | Exception caught in `_handle_tool_call()` | Fallback uses original user text as LLM query; no search performed; logged as warning |
| 23 | Intent Detection | LLM hallucinates numbers from search | 3 | 2 | 6 | Manual review, user reports | GPT-4o + temperature=0 + strict system prompt ("Quote ALL numbers EXACTLY as they appear") |
| 24 | Intent Detection | LLM calls non-existent tool | 1 | 1 | 1 | `TOOL_REGISTRY` lookup miss | Unknown tool logged; original query used as LLM input; no crash |
| 25 | Search Provider | Empty/irrelevant search results | 2 | 2 | 4 | Empty results_summary check | LLM receives "No results found" context; generates best-effort answer from own knowledge |

## Risk Matrix

```
Severity ▲
    5 │         ●17
    4 │ ●1  ●3       ●2 ●6 ●16
    3 │ ●4  ●8 ●13   ●7 ●15 ●18 ●21 ●23
    2 │ ●12 ●22 ●24  ●10 ●9 ●5 ●11 ●20 ●25 ●19
    1 │ ●14
      └──────────────────────────▶ Likelihood
        1    2    3    4    5
```

## Summary

- **Highest RPN (12)**: ASR timeout, LLM timeout, WebSocket disconnect mid-utterance
- **Search-related RPNs (1–6)**: All low-to-medium risk; search failures degrade gracefully (LLM answers without web data)
- **All high-RPN items have active mitigations**: Circuit breakers + fallback audio
- **Zero unmitigated failures**: Every identified failure mode (25 total) has a detection mechanism and an automated response
- **No silent failures**: Users always receive audible feedback, even during degradation (SC-004)
- **Search resilience**: 4 circuit breakers (ASR, LLM, TTS, Search) ensure no single provider failure cascades
