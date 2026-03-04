# Implementation Plan: Real-Time Streaming Voice Assistant

**Branch**: `001-streaming-voice-pipeline` | **Date**: 2026-03-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-streaming-voice-pipeline/spec.md`

## Summary

Build a production-grade, real-time voice assistant that streams user audio over WebSocket, transcribes with an ASR provider, generates contextual responses via an LLM, and synthesizes spoken audio via TTS — all within a P95 end-to-end latency budget of 1.2 seconds. The system enforces strict Pydantic-validated event schemas across all pipeline stages, implements circuit-breaking with configurable fallbacks for every external service, emits per-request latency telemetry with P50/P95/P99 decomposition, and supports deterministic replay of recorded sessions for debugging.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI (WebSocket server), Pydantic v2 (schema validation), websockets (client connections), httpx (async HTTP for service calls), asyncio (non-blocking I/O)  
**Storage**: In-memory only (session state, conversation history capped at 10 turns; ephemeral — purged on session close)  
**Testing**: pytest + pytest-asyncio (unit/integration), hypothesis (property-based for schema edge cases)  
**Target Platform**: Linux server (containerised), macOS for local development  
**Project Type**: web-service (async WebSocket server with streaming pipeline)  
**Performance Goals**: P95 E2E < 1.2 s, P99 E2E < 1.8 s, provisional transcription feedback < 300 ms, 50 concurrent sessions  
**Constraints**: P95 ASR < 500 ms, P95 LLM TTFT < 400 ms, P95 TTS TTFB < 250 ms, orchestration overhead P95 < 100 ms; WSS/TLS transport mandatory; audio data ephemeral  
**Scale/Scope**: 50 concurrent voice sessions; single-language (English); single-speaker per session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Gate Criterion | Status |
|---|-----------|---------------|--------|
| I | Streaming-First Pipeline | WebSocket orchestration, non-blocking I/O, modular replaceable components | ✅ PASS — FastAPI + asyncio WebSocket server; ASR/LLM/TTS designed as independent async service adapters |
| II | Strict Schema Validation | Pydantic-enforced JSON schemas for all events; versioned event types | ✅ PASS — Pydantic v2 models for all 6+ event types; schema version field included |
| III | Latency Budget Discipline | P95 < 1.2 s E2E; P50/P95/P99 tracked per stage; budget allocated per component | ✅ PASS — Budget breakdown in Performance Standards; telemetry FR-013/FR-014 |
| IV | Resilience & Graceful Degradation | Circuit breaker per service; timeout + fallback defined; FMEA documented | ✅ PASS — FR-009 (3 failures / 30 s window), FR-010/FR-011 fallback strategies |
| V | Observability & Telemetry | Per-request latency decomposition; structured logs with correlation IDs | ✅ PASS — FR-013/FR-014/FR-016 cover all requirements |
| VI | Deterministic Debugging & Replay | Replay mode; timestamped event logging; faithfulness check | ✅ PASS — FR-015 (replay mode), FR-017 (text-level faithfulness check) |
| VII | Documentation as Engineering Record | README as technical report; trade-off rationale; lessons learned section | ✅ PASS — will be enforced via Documentation Gate at PR level |

**Gate result: PASS** — no violations. Complexity Tracking section is empty (no deviations to justify).

## Project Structure

### Documentation (this feature)

```text
specs/001-streaming-voice-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── websocket-events.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── models/              # Pydantic event schemas, session/utterance models
│   ├── events.py        # Pipeline event type definitions
│   ├── session.py       # Session & conversation context models
│   └── telemetry.py     # Latency record models
├── services/            # External service adapters (ASR, LLM, TTS)
│   ├── asr.py           # Speech recognition adapter (streaming)
│   ├── llm.py           # Reasoning service adapter (streaming tokens)
│   ├── tts.py           # Text-to-speech adapter (streaming audio)
│   └── circuit_breaker.py  # Generic circuit breaker implementation
├── pipeline/            # Core orchestration logic
│   ├── orchestrator.py  # Main pipeline coordinator
│   ├── session_manager.py  # Session lifecycle management
│   └── replay.py        # Replay mode for recorded sessions
├── telemetry/           # Observability infrastructure
│   ├── metrics.py       # P50/P95/P99 aggregation
│   ├── logger.py        # Structured JSON logging with correlation IDs
│   └── dashboard.py     # Console/endpoint latency decomposition
├── fallback/            # Degradation strategies
│   ├── bridge_audio.py  # Pre-generated bridge response audio
│   └── strategies.py    # Fallback routing logic per service
├── server.py            # FastAPI WebSocket entry point
└── config.py            # Configuration (timeouts, budgets, audio format)

tests/
├── contract/            # Schema contract tests (Pydantic model validation)
├── integration/         # End-to-end pipeline tests with mocked services
├── unit/                # Per-module unit tests
└── fixtures/            # Recorded audio sessions for replay tests
```

**Structure Decision**: Single-project layout. The system is a single async
WebSocket server with modular service adapters. No frontend/backend split
needed — clients connect directly via WebSocket. The `pipeline/` directory
separates orchestration logic from service adapters (`services/`) and data
models (`models/`).

## Complexity Tracking

> No Constitution Check violations. This section intentionally left empty.
