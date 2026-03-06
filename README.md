# Real-Time AI Voice Assistant — Technical Report

## 🚀 Live Demo (Production)

**Try it now!** The application is deployed and live:

- **Frontend UI:** https://real-time-voice-ai-assistant.vercel.app/
- **Backend API:** https://real-time-voice-ai-assistant-production.up.railway.app/health

### How to Use the Live Demo

1. Open the [frontend URL](https://real-time-voice-ai-assistant.vercel.app/)
2. Click **"Connect to Server"** to establish connection
3. Click **"Start Recording"** and speak your query
4. Watch as the system:
   - Transcribes your speech (ASR - Whisper)
   - Detects intent via OpenAI function calling (GPT-4o-mini)
   - Searches the web for real-time data when needed (Tavily API)
   - Generates an accurate AI response (LLM - GPT-4o)
   - Converts text to speech (TTS - OpenAI tts-1-hd)
   - Plays the audio response automatically

**Technology Stack:** React 18.2 (Vercel) + FastAPI (Railway) + OpenAI APIs + Tavily Search API

---

## System Architecture

### High-Level Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                              │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │              React UI (Vercel)                                │   │
│  │  - Audio recording + playback                                 │   │
│  │  - Connection status display                                  │   │
│  │  - Real-time event streaming                                  │   │
│  └────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
                                    ║
                         WebSocket (WSS)
                                    ║
┌───────────────────────────────────────────────────────────────────────┐
│                         FASTAPI SERVER                                 │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │               WebSocket Connection Handler                     │   │
│  │  - Receives audio chunks (16-bit PCM)                          │   │
│  │  - Routes events to orchestrator per session                  │   │
│  │  - Streams responses back to client                           │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                    ║                                    │
│                        ┌───────────┴───────────┐                       │
│                        ▼                       ▼                        │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐   │
│  │   Session Manager            │  │  Telemetry / Logging         │   │
│  │  (pipeline/session_manager)  │  │  (telemetry/*, models/*)     │   │
│  │  - Manage per-session state  │  │  - Latency tracking          │   │
│  │  - Context window (10-turn)  │  │  - Correlation IDs           │   │
│  └───────────────┬──────────────┘  │  - Event metrics             │   │
│                  ▼                  └──────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │           Orchestrator (stream coordinator)                   │   │
│  │        (pipeline/orchestrator.py per-session)                │   │
│  │  - Schema-validated event handling                            │   │
│  │  - ASR → Intent Detection → [Web Search] → LLM → TTS         │   │
│  │  - OpenAI function calling for intent routing                 │   │
│  │  - Task cancellation for barge-in detection                   │   │
│  └────┬──────────────┬──────────────┬───────────────────────┬────┘   │
│       │                  │                      │                │    │
│       ▼                  ▼                      ▼                ▼    │
│  ┌──────────┐     ┌───────────┐          ┌──────────┐    ┌──────────┐│
│  │   ASR    │     │  Search   │          │   LLM    │    │   TTS    ││
│  │ Adapter  │     │  Adapter  │          │ Adapter  │    │ Adapter  ││
│  └────┬─────┘     └─────┬─────┘          └────┬─────┘    └────┬─────┘│
│       │                 │                     │               │      │
│       ▼                 ▼                     ▼               ▼      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│  │   Circuit    │ │   Circuit    │ │   Circuit    │ │   Circuit    ││
│  │   Breaker    │ │   Breaker    │ │   Breaker    │ │   Breaker    ││
│  │  (ASR)       │ │  (Search)    │ │  (LLM)       │ │  (TTS)       ││
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘│
│         │                │                │                │        │
│         ▼                ▼                ▼                ▼        │
│   ┌──────────┐    ┌──────────┐    ┌──────────────┐   ┌──────────┐  │
│   │ Fallback │    │ Fallback │    │ Fallback     │   │ Fallback │  │
│   │ Strategy │    │ Strategy │    │ Strategy     │   │ Strategy │  │
│   │ (bridge) │    │ (skip)   │    │ (bridge)     │   │ (cached) │  │
│   └──────────┘    └──────────┘    └──────────────┘   └──────────┘  │
└───────────────────────────────────────────────────────────────────────┘
        ║                ║                  ║                ║
        ║ HTTP/HTTPS     ║ HTTP/HTTPS       ║ HTTP/HTTPS     ║ HTTP/HTTPS
        ▼                ▼                  ▼                ▼
   ┌─────────┐    ┌──────────┐       ┌──────────┐     ┌──────────┐
   │   ASR   │    │  Search  │       │   LLM    │     │   TTS    │
   │Provider │    │ Provider │       │Provider  │     │Provider  │
   │(OpenAI  │    │ (Tavily  │       │(OpenAI   │     │(OpenAI   │
   │Whisper) │    │  API)    │       │GPT-4o)   │     │tts-1-hd) │
   └─────────┘    └──────────┘       └──────────┘     └──────────┘
```

### Data Flow

#### Request Flow (Upstream)
1. **Client → Server**: Audio frames (16-bit PCM) streamed over persistent WSS connection
2. **Server → Orchestrator**: Audio chunks routed to active session orchestrator
3. **Orchestrator → ASR Adapter**: Streaming audio forwarded to ASR provider
4. **ASR → Orchestrator**: Provisional + final transcription events received
5. **Orchestrator → LLM (Call #1 — Intent Detection)**: Transcription + context + tool definitions sent to GPT-4o-mini
6. **LLM decides**: Either responds directly (general conversation) or requests a tool call (web_search / factual_lookup)
7. **If tool call → Orchestrator → Search Adapter**: Executes Tavily web search
8. **Search → Orchestrator**: Formatted search results returned
9. **Orchestrator → LLM (Call #2 — Answer Synthesis)**: Search results + strict system prompt sent to GPT-4o (temperature=0)
10. **LLM → Orchestrator**: Token-by-token response streamed back with exact data from search
11. **Orchestrator → TTS Adapter**: Accumulated text buffered and sent for synthesis

#### Response Flow (Downstream)
1. **TTS → Orchestrator**: Audio chunks received
2. **Orchestrator → Server**: TTS audio events queued for client
3. **Server → Client**: Audio events streamed via WebSocket for immediate playback

### Event Schema & Validation

All internal events follow strict Pydantic v2 schemas:
- `ASRTranscriptionEvent` (provisional/final variants)
- `IntentDetectedEvent` (intent type, search query, requires_search flag)
- `WebSearchResultEvent` (query, results summary, source count)
- `LLMTokenEvent` (with accumulated text)
- `TTSAudioChunkEvent` (base64-encoded PCM)
- `ErrorEvent` (with error codes and fallback flags)
- Every event tagged with `correlation_id` for end-to-end tracing

### Fault Tolerance

**Circuit Breaker per Service**
- State: CLOSED (healthy) → OPEN (failures detected) → HALF_OPEN (testing) → CLOSED
- Threshold: 3 failures in 30s sliding window
- Recovery cooldown: 10s, then single probe
- Independent per ASR/LLM/TTS

**Fallback Strategies**
- **ASR Failure**: Bridge audio + "I didn't catch that, could you repeat?"
- **Search Failure**: Graceful skip — LLM responds without search results (no user-visible error)
- **LLM Failure**: Bridge audio + "Let me think about that..."
- **TTS Failure**: Pre-generated cached audio clip

**Barge-in Detection**
- Task cancellation: `asyncio.Task.cancel()` on new user input
- Graceful cleanup: `try/except CancelledError` in all pipeline stages
- Immediate re-routing to new utterance

---

### Data Flow

1. **Client → Server**: 16-bit PCM audio chunks over persistent WebSocket (WSS).
2. **Server → ASR**: Streaming audio forwarded via httpx chunked POST.
3. **ASR → Orchestrator**: `transcription_provisional` and `transcription_final` events.
4. **Orchestrator → LLM**: Final transcription + 10-turn context + tool definitions sent for intent detection.
5. **LLM (GPT-4o-mini)**: Decides to respond directly or request a tool call (web_search / factual_lookup).
6. **If tool call → Orchestrator → Search**: Tavily web search executed for real-time data.
7. **LLM (GPT-4o, temp=0)**: Synthesizes search results into accurate spoken response.
8. **Orchestrator → TTS**: Accumulated text sent for synthesis.
9. **TTS → Client**: `tts_audio_chunk` events streamed back via WebSocket.

All events are **Pydantic v2-validated** with correlation IDs for end-to-end tracing.

## Technology Selection Trade-Offs

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.13 | Mature async ecosystem, fast prototyping, strong ML/AI library support |
| **Framework** | FastAPI | Native WebSocket support, Pydantic v2 integration, async-first |
| **Schema Validation** | Pydantic v2 | Strict JSON validation, discriminated unions, computed fields |
| **HTTP Client** | httpx | Async streaming support, connection pooling, timeout control |
| **Intent Detection** | OpenAI Function Calling | No separate service needed — LLM autonomously decides when to search |
| **Web Search** | Tavily API | Purpose-built for AI agents, returns structured results + AI answer |
| **LLM (Intent)** | GPT-4o-mini | Fast, cost-effective for routing decisions |
| **LLM (Answer)** | GPT-4o | Superior instruction-following for accurate factual responses |
| **Storage** | In-memory | Session-scoped ephemeral data — no persistence requirement |

### Trade-offs Accepted

- **In-memory only**: No cross-session persistence. Simplifies architecture but limits horizontal scaling without a shared state layer.
- **Single-language (English)**: Avoids multi-model complexity. Multi-language support would require ASR/TTS provider negotiation.
- **No authentication**: Out of scope per spec. Production deployment must add auth middleware.
- **Placeholder bridge audio**: Generated tones instead of real TTS clips. Production would use pre-recorded human voice clips.

## Latency Budget Breakdown

| Stage | P95 Budget | Measurement |
|-------|-----------|-------------|
| ASR (speech recognition) | 500 ms | Audio chunk received → final transcription |
| LLM (time to first token) | 400 ms | Transcription sent → first token received |
| TTS (time to first byte) | 250 ms | Text sent → first audio chunk received |
| Orchestration overhead | 100 ms | Routing, validation, context assembly |
| **Total E2E** | **1,200 ms** | End of speech → start of audio playback |
| Total E2E (P99) | 1,800 ms | Relaxed target for tail latency |

Telemetry endpoint: `GET /telemetry/latency` returns P50/P95/P99 for all stages.

## Circuit Breaker & Degradation

- **Threshold**: 3 failures in 30-second sliding window → circuit OPEN
- **Recovery**: After 10s cooldown → HALF_OPEN → single probe → CLOSED on success
- **ASR failure**: "I didn't catch that, could you repeat?" bridge audio
- **LLM failure**: "Let me think about that..." bridge audio
- **TTS failure**: Pre-generated cached audio clip
- **Barge-in**: Cancel + discard in-progress response, process new utterance immediately

## Project Structure

```
src/
├── models/          # Pydantic event schemas, session, telemetry models
├── services/        # ASR, LLM, TTS, Search, Tools adapters + circuit breaker
├── pipeline/        # Orchestrator, session manager, replay engine
├── telemetry/       # Metrics, structured logger, dashboard
├── fallback/        # Bridge audio, fallback strategies
├── server.py        # FastAPI entry point
└── config.py        # All configuration (budgets, timeouts, thresholds)
tests/
├── contract/        # Schema validation tests
├── integration/     # End-to-end pipeline tests
├── unit/            # Per-module unit tests
└── fixtures/        # Recorded sessions for replay
```

## Lessons Learned & Iterative Pivots

1. **Schema-first design pays off**: Defining all event types upfront (events.py) before writing any service code made integration straightforward across all 5 user stories.

2. **Circuit breaker granularity matters**: A single global circuit breaker would mask which service is degraded. Per-service breakers with independent thresholds allow targeted fallback strategies.

3. **Barge-in via task cancellation**: Using `asyncio.Task.cancel()` for barge-in detection is clean but requires careful `try/except CancelledError` handling in all pipeline stages to avoid resource leaks.

4. **Faithfulness check is zero-cost**: Comparing LLM output text to TTS input text before synthesis is a simple string equality check — no re-transcription needed, no latency overhead.

5. **Replay mode design**: Recording sessions as timestamped JSON (not raw binary) makes them human-inspectable and version-controllable. The delay multiplier enables stress testing degradation paths.

## Testing with Mock Providers

For rapid testing **without API keys**, the system includes mock ASR/LLM/TTS services that simulate realistic provider behavior:

```bash
# 1. Set mock mode in .env (or leave PROVIDER_MODE=mock)
export PROVIDER_MODE=mock

# 2. Start both mock services + main app (all-in-one script)
python run_local_mock.py

# Alternatively, run them separately:
# Terminal 1: Mock providers on :9000
python -m src.mock_providers

# Terminal 2: Main app on :8000
export PROVIDER_MODE=mock
uvicorn src.server:app --reload
```

**What the mocks do:**
- **ASR mock** (`/asr/stream`): Returns streaming transcription events (provisional + final)
- **LLM mock** (`/llm/stream`): Returns token-by-token LLM response
- **TTS mock** (`/tts/stream`): Returns synthesized audio chunks (440 Hz sine wave tone)

All mocks introduce realistic latencies (20-50ms per event) to simulate network conditions.

**Switching to Real Providers:**
When you have API keys, simply update `.env`:

```bash
# Switch mode
PROVIDER_MODE=real

# Configure real provider URLs and API keys
ASR_PROVIDER_URL=https://api.openai.com/v1/audio/transcriptions
ASR_API_KEY=sk-...
# ... etc
```

Then restart the server. No code changes needed—configuration is loaded at startup.

---

## Running the Server

### Prerequisites & Setup

1. **Clone the repository**:
```bash
git clone git@github.com:karthik-vankara/real-time-voice-ai-assistant.git
cd real-time-voice-ai-assistant
```

2. **Create a Python virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

3. **Install dependencies**:
```bash
pip install -e ".[dev]"
```
This installs all runtime + development dependencies (pytest, ruff, etc.) and enables python-dotenv for environment variable loading.

4. **Configure environment variables**:
```bash
# Copy the example .env file
cp .env.example .env

# For quick testing with mocks (recommended):
# Leave PROVIDER_MODE=mock (already set in .env.example)

# For production with real APIs:
# Edit .env and set PROVIDER_MODE=real
# Then add your provider URLs and API keys
nano .env
```

**Environment Variables Reference**:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVIDER_MODE` | `mock` | `"mock"` for testing without API keys, `"real"` for production |
| `ASR_PROVIDER_URL` | `http://localhost:9000/asr/stream` | Speech-to-text provider endpoint (mock) or real provider URL |
| `ASR_API_KEY` | `` (empty) | API key for ASR provider authentication |
| `LLM_PROVIDER_URL` | `http://localhost:9000/llm/stream` | Language model provider endpoint (mock) or real provider URL |
| `LLM_API_KEY` | `` (empty) | API key for LLM provider authentication |
| `TTS_PROVIDER_URL` | `http://localhost:9000/tts/stream` | Text-to-speech provider endpoint (mock) or real provider URL |
| `TTS_API_KEY` | `` (empty) | API key for TTS provider authentication |
| `SEARCH_API_KEY` | `` (empty) | Tavily API key for web search (get free at tavily.com) |
| `ENABLE_WEB_SEARCH` | `true` | Enable/disable web search intent detection |
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8000` | Server port |
| `SERVER_REQUIRE_TLS` | `false` | Enforce WebSocket Secure (WSS) for production |

### Example Provider Integrations

**OpenAI (ASR + TTS via Whisper + TTS APIs)**:
```bash
ASR_PROVIDER_URL=https://api.openai.com/v1/audio/transcriptions
ASR_API_KEY=sk-...

LLM_PROVIDER_URL=https://api.openai.com/v1/chat/completions
LLM_API_KEY=sk-...

TTS_PROVIDER_URL=https://api.openai.com/v1/audio/speech
TTS_API_KEY=sk-...
```

**Local Mock Services** (for testing):
For development without real API keys, you can mock the services on localhost:
- ASR mock on 9001
- LLM mock on 9002
- TTS mock on 9003

Example mock server (Python):
```python
# mock_services.py - simple async server returning valid responses
from fastapi import FastAPI

app = FastAPI()

@app.post("/asr/stream")
async def mock_asr(request: bytes):
    return {"text": "hello world", "is_final": True}

@app.post("/llm/stream")
async def mock_llm(request_data: dict):
    return {"token": "Hello! ", "done": False}

@app.post("/tts/stream")
async def mock_tts(request_data: dict):
    # Return base64-encoded audio chunk
    return {"audio_b64": "...", "is_last": True}
```

### Start the Server

**Quick start with mock providers (recommended for testing)**:
```bash
# One command to start mock services + main app
python run_local_mock.py
```

This starts:
- Mock providers on `http://localhost:9000` (ASR/LLM/TTS endpoints)
- Main app on `http://localhost:8000` (WebSocket server)

**Manual startup** (separate terminals):
```bash
# Activate venv
source .venv/bin/activate

# Terminal 1: Start mock providers
python -m src.mock_providers

# Terminal 2: Start main app
export PROVIDER_MODE=mock
uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
```

**Production with real providers**:
```bash
source .venv/bin/activate
export PROVIDER_MODE=real  # Use .env for configuration
export ASR_PROVIDER_URL=... ASR_API_KEY=... # etc
uvicorn src.server:app --host 0.0.0.0 --port 8000
```

### Health Check

```bash
curl http://localhost:8000/health
# Output: {"status": "ok"}
```

### Telemetry Dashboard

```bash
curl http://localhost:8000/telemetry/latency
# Output: {"p50_ms": 850, "p95_ms": 1100, "p99_ms": 1500}
```

### Client Connection Example

```python
import asyncio
import websockets
import json

async def connect():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        # Send 16-bit PCM audio chunks
        audio_chunk = b'\x00\x01\x00\x02...'  # 16kHz, 16-bit mono
        await ws.send(audio_chunk)
        
        # Receive streaming events
        async for message in ws:
            event = json.loads(message)
            print(f"Event: {event['event_type']}")
            if event['event_type'] == 'tts_audio_chunk':
                print(f"Received {len(event['payload']['audio_b64'])} bytes of audio")

asyncio.run(connect())
```
