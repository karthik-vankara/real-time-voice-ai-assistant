# Real-Time Voice Assistant - Architecture Overview

## System Design

This is a **production-grade real-time voice conversational AI system** built with a modern, scalable architecture that prioritizes latency, resilience, and observability.

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER (Browser)                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ WebSocket (ws://)
                     │ Binary Audio + Control Messages
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND (React + TypeScript)                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  Audio Recorder  │  │ Events Display   │  │  Telemetry   │  │
│  │  (Web Audio API) │  │ (Real-time)      │  │  Dashboard   │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ WebSocket Stream
                     │ + HTTP Polling (telemetry)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│               BACKEND (FastAPI + async/await)                   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              WebSocket Entry Point (server.py)           │  │
│  │  • TLS enforcement                                        │  │
│  │  • Connection lifecycle management                        │  │
│  └────────────────┬─────────────────────────────────────────┘  │
│                   │                                              │
│  ┌────────────────▼─────────────────────────────────────────┐  │
│  │        Pipeline Orchestrator (orchestrator.py)           │  │
│  │  • Session management (10-turn conversation history)     │  │
│  │  • Intent detection via OpenAI function calling          │  │
│  │  • Conditional web search (Tavily API)                   │  │
│  │  • Dual-LLM: GPT-4o-mini (intent) + GPT-4o (answer)     │  │
│  │  • Barge-in support (interrupt ongoing responses)        │  │
│  │  • Audio validation (16-bit PCM format check)            │  │
│  │  • Latency tracking (per-request measurements)           │  │
│  └────────────────┬─────────────────────────────────────────┘  │
│                   │                                              │
│    ┌──────────────┼──────────────┬──────────────┐               │
│    │              │              │              │               │
│    ▼              ▼              ▼              ▼               │
│  ┌──────┐     ┌──────┐      ┌──────┐      ┌──────┐            │
│  │ ASR  │     │Search│      │ LLM  │      │ TTS  │            │
│  │ 500ms│     │<10s  │      │400ms │      │250ms │            │
│  │ TTFR │     │      │      │TTFT  │      │TTFB  │            │
│  └──────┘     └──────┘      └──────┘      └──────┘            │
│    │              │              │              │               │
│  ┌─▼──────────────▼──────────────▼──────────────▼─┐            │
│  │   Circuit Breakers + Fallbacks                 │            │
│  │   • Per-service fault tolerance                │            │
│  │   • Search: graceful skip on failure           │            │
│  │   • Fallback: bridge audio                     │            │
│  └────────────────────────────────────────────────┘            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │        Telemetry System (metrics.py, dashboard.py)       │  │
│  │  • Real-time P50/P95/P99 computation                     │  │
│  │  • Budget breach detection                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌─────────┐  ┌──────┐  ┌────────────┐
│ OpenAI  │  │Mock  │  │ Tavily   │  │ HuggingFace│ (External Services)
│ Whisper │  │ASR   │  │ Search   │  │ TTS        │
│ GPT-4o  │  │(dev) │  │ API      │  │ etc.       │
└─────────┘  └──────┘  └────────────┘
```

## Data Flow: User Recording to Response

### 1️⃣ **Audio Capture Phase**
- User clicks "Start Recording"
- Browser requests microphone access
- Web Audio API captures raw audio at 16kHz, 16-bit PCM
- Audio flows in 4096-sample chunks (~256ms buffers)
- Each chunk is sent immediately as binary WebSocket message

### 2️⃣ **Audio Accumulation & Validation**
- Server receives binary audio frames
- Validates: is it 16-bit PCM? (even byte length check)
- User stops recording → sends `end_of_utterance` control message
- Server concatenates all audio chunks into one utterance

### 3️⃣ **Pipeline Execution** (ASR → LLM → TTS)

**Stage A: Automatic Speech Recognition (ASR)**
```
Audio chunks → ASR Service (Whisper API) 
→ "Hello, how are you?" (final transcript)
⏱ Latency: ~250-300ms
```

**Stage B: Intent Detection & Web Search (LLM Call #1)**
```
Transcript + 10-turn history + tool definitions → LLM (GPT-4o-mini)
→ Decision: direct response OR tool call (web_search / factual_lookup)
⏱ Latency: ~140-150ms
```

**Stage B.1: Web Search (Conditional)**
```
If LLM requests web_search or factual_lookup:
  Search query → Tavily API (advanced depth, 5 results)
  → Formatted search results (answer + sources)
  ⏱ Latency: ~500-2000ms (depends on search complexity)
```

**Stage C: Answer Synthesis (LLM Call #2 — only if search was needed)**
```
Search results + strict system prompt → LLM (GPT-4o, temp=0)
→ "The Nifty 50 is currently at 24,450.45" (exact data from search)
⏱ Latency: ~200-300ms
```

**Stage D: Text-to-Speech (TTS)**
```
Response text → TTS Service (TTS API)
→ Audio chunks streamed back to browser
→ Auto-plays on client
⏱ Latency: ~130-140ms
```

### 4️⃣ **Real-Time Event Streaming**
- Each pipeline stage emits events:
  - `speech_started`
  - `transcription_provisional` (interim results)
  - `transcription_final`
  - `intent_detected` (tool call intent: web_search, factual_lookup, or direct)
  - `web_search_result` (search query, results summary, source count)
  - `llm_token` (streaming LLM output)
  - `tts_audio_chunk` (streamed audio)
- Events flow back via WebSocket as JSON
- Frontend updates UI in real-time

### 5️⃣ **Latency Tracking**
- Each request gets a unique `correlation_id`
- Timestamps captured at each stage boundary
- Total E2E latency computed
- Added to sliding window (last 100 requests)
- P50/P95/P99 percentiles calculated
- Frontend polls `/telemetry/latency` every 2 seconds

## Key Architectural Principles

### 🔄 **Async/Await Throughout**
- All I/O operations are non-blocking
- WebSocket streams are handled concurrently
- Multiple sessions can run simultaneously

### 🧠 **Smart Intent Detection**
- OpenAI function calling (no separate intent service)
- LLM autonomously decides: answer directly vs. search the web
- Two-pass LLM: GPT-4o-mini for intent, GPT-4o for factual synthesis
- Strict system prompt + temperature=0 ensures exact number citation

### 🔍 **Real-Time Web Search**
- Tavily API integration for real-time data (stocks, news, weather, etc.)
- Advanced search depth, up to 5 results + AI-generated answer
- Feature flag: `ENABLE_WEB_SEARCH` env var to toggle
- Graceful degradation: if search fails, LLM answers without it

### 🛡️ **Circuit Breaker Pattern**
- Per-service failure tracking (ASR, LLM, TTS, Search)
- Auto-opens on 3 failures in 30 seconds
- Prevents cascading failures
- Fallback: if service down, plays synthesized message

### 💬 **Conversation History**
- 10-turn context maintained per session
- User and assistant turns tracked
- LLM gets full context for coherent responses

### 🔊 **Barge-In Support**
- User can interrupt ongoing response
- Active pipeline task is cancelled
- New audio recording starts immediately

### 📊 **Observability**
- Structured logging (JSON format)
- Per-request correlation IDs
- Real-time latency percentiles
- Budget breach detection & alerts

### 🔐 **Configuration via Environment**
- Provider selection: `PROVIDER_MODE=mock|real`
- Web search toggle: `ENABLE_WEB_SEARCH=true|false`
- Mock providers for dev/testing (no API keys needed)
- Real providers for production
- TLS enforcement configurable

## Latency Budget

Total P95 Target: **1,200ms**

| Component | Budget | Typical | Status |
|-----------|--------|---------|--------|
| ASR | 500ms | 250-300ms | ✅ 2x buffer |
| LLM | 400ms | 140-150ms | ✅ 2.7x buffer |
| TTS | 250ms | 130-140ms | ✅ 1.8x buffer |
| Overhead | 100ms | ~0.1ms | ✅ 1000x buffer |
| **Total E2E** | **1,200ms** | **~575ms** | **✅ 2x buffer** |

## Resilience Strategy

```
Request → ASR Circuit Breaker
           ├─ If CLOSED (healthy): Call ASR service
           ├─ If OPEN (failing): Play fallback "I didn't understand"
           └─ If HALF_OPEN: Try service, update state

Same pattern for LLM, TTS services
```

## Session Management

- One session per client connection
- Unique `session_id` per WebSocket connection
- Max 50 concurrent sessions (configurable)
- Auto-cleanup on disconnect
- 10-turn conversation history per session

## Configuration Priority

1. Environment variables (`.env`)
2. System environment
3. Hardcoded defaults in `src/config.py`

## Error Handling

- Invalid audio frames → error event to client
- Service timeouts → fallback strategy
- Circuit breaker open → fallback message + auto-retry
- WebSocket disconnect → graceful cleanup

---

## Next: Deep Dive

- [Backend Architecture](./BACKEND_ARCHITECTURE.md) - Backend components & services
- [Frontend Architecture](./FRONTEND_ARCHITECTURE.md) - React UI & state management
- [Backend Files](./BACKEND_FILES.md) - File-by-file backend code explanation
- [Frontend Files](./FRONTEND_FILES.md) - File-by-file frontend code explanation
