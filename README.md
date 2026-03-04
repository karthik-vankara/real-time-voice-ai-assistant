# Real-Time AI Voice Assistant — Technical Report

## System Architecture

```
Client (WebSocket) ──WSS──▶ FastAPI Server
                              │
                              ▼
                      ┌───────────────┐
                      │  Orchestrator  │  (pipeline/orchestrator.py)
                      │  per-session   │
                      └──┬────┬────┬──┘
                         │    │    │
               ┌─────────┘    │    └─────────┐
               ▼              ▼              ▼
          ┌─────────┐   ┌─────────┐   ┌─────────┐
          │   ASR   │   │   LLM   │   │   TTS   │
          │ adapter │   │ adapter │   │ adapter │
          └────┬────┘   └────┬────┘   └────┬────┘
               │              │              │
          Circuit Breaker  Circuit Breaker  Circuit Breaker
               │              │              │
          External ASR    External LLM    External TTS
          Provider        Provider        Provider
```

### Data Flow

1. **Client → Server**: 16-bit PCM audio chunks over persistent WebSocket (WSS).
2. **Server → ASR**: Streaming audio forwarded via httpx chunked POST.
3. **ASR → Orchestrator**: `transcription_provisional` and `transcription_final` events.
4. **Orchestrator → LLM**: Final transcription + 10-turn context sent for reasoning.
5. **LLM → Orchestrator**: Token-by-token streaming response.
6. **Orchestrator → TTS**: Accumulated text sent for synthesis.
7. **TTS → Client**: `tts_audio_chunk` events streamed back via WebSocket.

All events are **Pydantic v2-validated** with correlation IDs for end-to-end tracing.

## Technology Selection Trade-Offs

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.12 | Mature async ecosystem, fast prototyping, strong ML/AI library support |
| **Framework** | FastAPI | Native WebSocket support, Pydantic v2 integration, async-first |
| **Schema Validation** | Pydantic v2 | Strict JSON validation, discriminated unions, computed fields |
| **HTTP Client** | httpx | Async streaming support, connection pooling, timeout control |
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
├── services/        # ASR, LLM, TTS adapters + circuit breaker
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

## Running the Server

```bash
# Install dependencies
pip install -e ".[dev]"

# Start server (local dev, TLS disabled)
uvicorn src.server:app --host 0.0.0.0 --port 8000

# Health check
curl http://localhost:8000/health

# Telemetry dashboard
curl http://localhost:8000/telemetry/latency
```
