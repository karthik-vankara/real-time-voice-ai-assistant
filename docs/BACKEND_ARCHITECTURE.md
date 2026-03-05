# Backend Architecture - Detailed Explanation

## Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Web Framework | FastAPI | 0.135.1 | High-performance async web server |
| ASGI Server | Uvicorn | Latest | HTTP/WebSocket server |
| Python Runtime | Python | 3.13.2 | Core language |
| Data Validation | Pydantic | v2 2.12.5 | Type-safe configuration & models |
| HTTP Client | httpx | Async | Non-blocking API calls |
| Async Utilities | asyncio | Built-in | Concurrency primitives |

## Directory Structure

```
src/
├── __init__.py                      # Package marker
├── config.py                        # Configuration loader (env vars)
├── server.py                        # FastAPI app entry point
├── mock_providers.py                # Mock ASR/LLM/TTS for testing
│
├── models/                          # Data models (Pydantic)
│   ├── __init__.py
│   ├── events.py                    # Pipeline events (SpeechStarted, Transcription, etc)
│   ├── session.py                   # Session & conversation turn models
│   └── telemetry.py                 # Latency record model
│
├── services/                        # Microservices
│   ├── __init__.py
│   ├── circuit_breaker.py           # Fault tolerance pattern
│   ├── asr.py                       # Speech-to-text service
│   ├── llm.py                       # Language model service
│   └── tts.py                       # Text-to-speech service
│
├── pipeline/                        # Core processing logic
│   ├── __init__.py
│   ├── orchestrator.py              # Main pipeline coordinator
│   ├── session_manager.py           # Session lifecycle management
│   └── replay.py                    # Session replay for debugging
│
├── fallback/                        # Error handling strategies
│   ├── __init__.py
│   ├── strategies.py                # Fallback service selectors
│   └── bridge_audio.py              # Synthesized audio fallback
│
└── telemetry/                       # Observability
    ├── __init__.py
    ├── logger.py                    # Structured JSON logging
    ├── metrics.py                   # Latency tracking & percentiles
    └── dashboard.py                 # HTTP endpoint for metrics
```

## Core Components

### 1. **FastAPI Application** (`server.py`)
- Entry point for HTTP/WebSocket connections
- Enforces TLS for production (configurable)
- Routes incoming WebSocket to orchestrator
- Provides health check and telemetry endpoints
- CORS enabled for cross-origin requests

### 2. **Pipeline Orchestrator** (`orchestrator.py`)
- **Main coordinator** for entire voice processing pipeline
- Manages per-session state
- Receives audio frames from client
- Triggers ASR → LLM → TTS stages
- Emits events back to client
- Tracks latency per request
- Implements barge-in support

### 3. **Session Manager** (`session_manager.py`)
- Maintains active sessions (max 50)
- Stores 10-turn conversation history
- Tracks session timeout
- Provides cleanup on disconnect

### 4. **Service Layer** (ASR, LLM, TTS)
Each service:
- Calls external API (OpenAI, HuggingFace, etc)
- Or calls mock provider for development
- Has its own circuit breaker
- Returns structured results
- Integrates with latency tracking

### 5. **Circuit Breaker** (`circuit_breaker.py`)
- Tracks failures per service
- States: CLOSED → OPEN → HALF_OPEN
- Protects against cascading failures
- Auto-recovery with exponential backoff

### 6. **Telemetry System** (`metrics.py`, `dashboard.py`)
- Captures timestamps at stage boundaries
- Computes latency: total_e2e, asr, llm, tts, overhead
- Maintains sliding window (last 100 requests)
- Calculates P50, P95, P99 percentiles
- Exposes `/telemetry/latency` HTTP endpoint

### 7. **Configuration** (`config.py`)
- Loads settings from environment variables
- Supports multiple provider modes (mock, real, hybrid)
- Configurable latency budgets
- Server settings (host, port, TLS)

### 8. **Models** (`models/`)
- **events.py**: EventType enums, event payload structures
- **session.py**: Session, ConversationTurn for history tracking
- **telemetry.py**: LatencyRecord for metrics

## Data Flow in Backend

### Incoming Audio Stream
```
Client WebSocket Binary Message
    ↓
server.py: websocket_endpoint()
    ↓
orchestrator.py: handle_session()
    ↓
Message received (audio frame)
    ↓
validate_audio_frame() [16-bit PCM check]
    ↓
Append to audio_chunks[]
    ↓
(repeat until end_of_utterance signal)
```

### Pipeline Execution
```
audio_chunks[] (concatenated binary)
    ↓
_run_pipeline():
    │
    ├─→ LatencyTracker.start("asr")
    ├─→ _run_asr() → ASR Service → Transcript
    ├─→ LatencyTracker.stop("asr")
    ├─→ Emit: transcription_final event
    │
    ├─→ LatencyTracker.start("llm")
    ├─→ _run_llm() + 10-turn history
    ├─→ LLM Service → Response tokens
    ├─→ LatencyTracker.stop("llm")
    ├─→ Emit: llm_token events (stream)
    │
    ├─→ LatencyTracker.start("tts")
    ├─→ _run_tts() → TTS Service
    ├─→ Emit: tts_audio_chunk events (stream)
    ├─→ LatencyTracker.stop("tts")
    │
    ├─→ Update session history (add turn)
    ├─→ aggregator.add(record) [telemetry]
    │
    └─→ Return to orchestrator
```

### Event Streaming
```
Each event is JSON-serialized and sent immediately:

{
  "event_type": "transcription_final",
  "correlation_id": "abc-123",
  "timestamp": "2026-03-05T...",
  "schema_version": "1.0.0",
  "payload": {
    "text": "hello how are you",
    "is_final": true
  }
}

WebSocket: await ws.send_json(event.model_dump(mode="json"))
```

## Concurrency Model

```
Main Uvicorn Process
    ↓
FastAPI Application
    ↓
Event Loop (asyncio)
    ├─ WebSocket 1: handle_session() [Session A]
    ├─ WebSocket 2: handle_session() [Session B]
    ├─ WebSocket 3: handle_session() [Session C]
    └─ (Up to 50 concurrent sessions)
```

Each session runs in its own async task, allowing:
- Non-blocking I/O
- Multiple clients simultaneously
- Efficient resource usage

## Error Handling Architecture

```
ASR Call Failed
    ↓
Check Circuit Breaker
    ├─ CLOSED: Retry
    ├─ OPEN: Use fallback strategy
    └─ HALF_OPEN: Try, then update state
    ↓
Fallback Strategies:
    ├─ Bridge audio: Synthesize "Sorry, I didn't catch that"
    ├─ Use mock provider: Return dummy response
    └─ Return error event to client
```

## Resilience Features

### 1. Circuit Breaker (per service)
- Tracks consecutive failures
- Opens after 3 failures in 30 seconds
- Half-open after 60 seconds for retry
- Prevents resource exhaustion

### 2. Timeout Handling
- ASR: 5 second timeout
- LLM: 10 second timeout
- TTS: 5 second timeout
- Each service configurable

### 3. Fallback Services
- If OpenAI Whisper fails → Mock ASR
- If GPT-4 fails → Mock LLM
- If TTS fails → Synthesized "error" audio

### 4. Graceful Degradation
- User gets error event with explanation
- Session continues (can try again)
- No cascading app-wide failures

## Configuration System

### Environment Variables Priority
```
.env file (user-defined)
    ↓
sys.environ (OS environment)
    ↓
Default in config.py (fallback)
```

### Key Configuration Options
```python
# Provider selection
PROVIDER_MODE=mock|real|hybrid

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_REQUIRE_TLS=false|true
SERVER_WS_PATH=/ws

# API Keys
OPENAI_API_KEY=sk-...
HUGGINGFACE_API_KEY=hf_...

# Latency budgets
ASR_BUDGET_MS=500
LLM_BUDGET_MS=400
TTS_BUDGET_MS=250

# Session management
MAX_CONCURRENT_SESSIONS=50
CONTEXT_WINDOW_TURNS=10
```

## Telemetry Pipeline

```
Request Received
    ↓
LatencyTracker created with correlation_id
    ↓
Each stage: tracker.start("asr") → service call → tracker.stop("asr")
    ↓
tracker.to_record() → LatencyRecord {
    asr_ms: 250.5,
    llm_ms: 145.2,
    tts_ms: 135.8,
    overhead_ms: 0.1,
    total_e2e_ms: 531.6
}
    ↓
aggregator.add(record)
    ↓
Sliding window updated (keep last 100 records)
    ↓
Percentile calculation (P50, P95, P99) happens on GET /telemetry/latency
    ↓
Response to client:
{
  "sample_count": 42,
  "percentiles": {
    "total_e2e": {"p50": 530.2, "p95": 575.8, "p99": 580.1},
    "asr": {"p50": 245.3, "p95": 298.1, "p99": 301.2},
    ...
  }
}
```

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Max concurrent sessions | 50 | Configurable in config.py |
| Context window | 10 turns | Per session conversation history |
| Max audio duration | 60s | Per utterance |
| Percentile window | 100 requests | Sliding window for P50/95/99 |
| WebSocket frame size | 8KB | 4096 samples × 2 bytes per sample |
| Latency budget | 1200ms P95 | Aggressive but achievable |

## Logging & Observability

### Structured Logging
- All logs as JSON for easy parsing
- Includes: timestamp, level, message, correlation_id, pipeline_stage
- Environment: `LOGLEVEL=debug|info|warning|error`

### Metrics Exposed
- `/health` - Simple health check
- `/telemetry/latency` - Real-time percentile latencies
- Internal logs - Budget breaches, circuit breaker state changes, errors

---

**Next:** [Backend Files](./BACKEND_FILES.md) - Line-by-line code explanation
