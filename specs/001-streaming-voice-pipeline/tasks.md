# Tasks: Real-Time Streaming Voice Assistant

**Input**: Design documents from `/specs/001-streaming-voice-pipeline/`
**Prerequisites**: plan.md ✅, spec.md ✅

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency management, and basic structure

- [x] T001 Create project directory structure matching plan.md layout: `src/models/`, `src/services/`, `src/pipeline/`, `src/telemetry/`, `src/fallback/`, `tests/contract/`, `tests/integration/`, `tests/unit/`, `tests/fixtures/`
- [x] T002 Initialize Python 3.12 project with pyproject.toml including dependencies: fastapi, uvicorn[standard], pydantic>=2.0, websockets, httpx, pytest, pytest-asyncio, hypothesis
- [x] T003 [P] Configure linting (ruff) and formatting (ruff format) in pyproject.toml
- [x] T004 [P] Create application configuration module with latency budgets, timeouts, audio format defaults, and circuit breaker thresholds in `src/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Define all Pydantic v2 pipeline event schemas (`speech_started`, `transcription_provisional`, `transcription_final`, `llm_token_generated`, `tts_audio_chunk`, `error`) with event type discriminator, correlation ID, timestamp, schema version, and typed payloads in `src/models/events.py`
- [x] T006 [P] Create Session model with session ID, connection state enum (active/idle/closed), conversation history (capped at 10 turns), creation timestamp, last activity timestamp, and idle timeout config in `src/models/session.py`
- [x] T007 [P] Create LatencyRecord model with correlation ID, per-stage timing fields (ASR, LLM TTFT, TTS TTFB, orchestration overhead, total E2E), timestamp, and budget breach flag in `src/models/telemetry.py`
- [x] T008 Implement generic async circuit breaker with configurable failure threshold (default: 3), sliding window (default: 30 s), half-open probe state, and open/closed/half-open state machine in `src/services/circuit_breaker.py`
- [x] T009 [P] Implement structured JSON logger with correlation ID injection, pipeline stage tagging, and timestamp formatting in `src/telemetry/logger.py`
- [x] T010 Create FastAPI application with WSS WebSocket endpoint, TLS enforcement (reject non-WSS), connection lifecycle hooks, and CORS configuration in `src/server.py`

**Checkpoint**: Foundation ready — event schemas validated, circuit breaker available, server accepting WebSocket connections. User story implementation can now begin.

---

## Phase 3: User Story 1 — Speak and Hear an Instant Response (Priority: P1) 🎯 MVP

**Goal**: End-to-end voice loop: user speaks → ASR transcribes → LLM reasons → TTS speaks back, all within P95 < 1.2 s.

**Independent Test**: Send a pre-recorded audio clip via WebSocket client, verify an audible spoken response returns, confirm E2E latency < 1.2 s at P95.

### Implementation for User Story 1

- [x] T011 [P] [US1] Implement ASR service adapter with async streaming interface (accepts audio chunks, yields transcription events) and configurable provider URL in `src/services/asr.py`
- [x] T012 [P] [US1] Implement LLM service adapter with async streaming interface (accepts transcription text + conversation context, yields token-by-token response) and configurable provider URL in `src/services/llm.py`
- [x] T013 [P] [US1] Implement TTS service adapter with async streaming interface (accepts text tokens, yields audio chunks) and configurable provider URL in `src/services/tts.py`
- [x] T014 [US1] Implement session manager with session creation, lookup by ID, conversation history management (10-turn rolling window), idle timeout tracking, and cleanup on close in `src/pipeline/session_manager.py`
- [x] T015 [US1] Implement pipeline orchestrator that wires ASR → LLM → TTS in a non-blocking async flow: receives audio chunks from WebSocket, streams to ASR, forwards final transcription to LLM with session context, pipes LLM tokens to TTS, and sends TTS audio chunks back to client via WebSocket in `src/pipeline/orchestrator.py`
- [x] T016 [US1] Integrate orchestrator with FastAPI WebSocket endpoint: handle connection accept, spawn per-session pipeline, route incoming audio frames to orchestrator, send outgoing events (transcription + audio) to client, handle disconnection with session cleanup in `src/server.py`
- [x] T017 [US1] Add audio format validation (16 kHz, 16-bit PCM) on incoming WebSocket frames; reject malformed input with a structured `error` event per FR-018 in `src/server.py`
- [x] T018 [US1] Add graceful disconnection handling: detect WebSocket close, cancel in-flight async tasks, purge session state and ephemeral audio data per FR-019 in `src/pipeline/session_manager.py`

**Checkpoint**: At this point, a client can connect via WebSocket, speak, and receive a spoken response. User Story 1 is fully functional and independently testable as MVP.

---

## Phase 4: User Story 2 — Real-Time Transcription Feedback (Priority: P2)

**Goal**: While the user speaks, emit provisional transcription events in near real-time so the client can display live text feedback.

**Independent Test**: Send streaming audio via WebSocket, verify `transcription_provisional` events arrive within 300 ms of each chunk, and a `transcription_final` event fires on speech pause.

### Implementation for User Story 2

- [x] T019 [US2] Extend ASR adapter to emit `transcription_provisional` events as intermediate results arrive (not just final) and distinguish provisional from final via event type in `src/services/asr.py`
- [x] T020 [US2] Update orchestrator to forward provisional transcription events to the client WebSocket immediately upon receipt from ASR (do not wait for final transcription) in `src/pipeline/orchestrator.py`
- [x] T021 [US2] Add `speech_started` event emission: detect the first audio chunk of a new utterance and emit a `speech_started` event to the client in `src/pipeline/orchestrator.py`

**Checkpoint**: User Stories 1 AND 2 both work independently — client receives live transcription feedback while speaking, plus a spoken response after.

---

## Phase 5: User Story 3 — Graceful Degradation Under Slowdowns (Priority: P3)

**Goal**: When ASR, LLM, or TTS exceeds its latency budget or fails, the user hears audible feedback (bridge audio, retry prompt) instead of silence. System auto-recovers.

**Independent Test**: Simulate a slow/unresponsive LLM, verify bridge audio plays within 1.2 s, then restore service and confirm normal responses resume within 10 s.

### Implementation for User Story 3

- [x] T022 [P] [US3] Create bridge audio assets (pre-generated audio clips: "Let me think about that...", "I didn't catch that, could you repeat?", "One moment please...") and loader utility in `src/fallback/bridge_audio.py`
- [x] T023 [P] [US3] Implement fallback strategy registry mapping each service (ASR, LLM, TTS) to its fallback action (bridge audio, cached clip, retry prompt, model switch) in `src/fallback/strategies.py`
- [x] T024 [US3] Wrap ASR adapter calls with circuit breaker: apply timeout from config, on failure/timeout emit audible retry prompt event to client, on circuit open route to fallback in `src/services/asr.py`
- [x] T025 [US3] Wrap LLM adapter calls with circuit breaker: apply timeout from config, on single timeout emit bridge audio immediately, on circuit open switch to faster lower-fidelity reasoning approach per FR-011 in `src/services/llm.py`
- [x] T026 [US3] Wrap TTS adapter calls with circuit breaker: apply timeout from config, on failure fall back to cached pre-generated audio clip, on circuit open use fallback for all requests in `src/services/tts.py`
- [x] T027 [US3] Update orchestrator to integrate fallback routing: when a service call triggers fallback, route response through the fallback strategy and still deliver an audible response to the client within the latency budget in `src/pipeline/orchestrator.py`
- [x] T028 [US3] Implement circuit half-open recovery logic: after configurable cooldown, probe the primary service with a single request; on success close the circuit and resume primary routing in `src/services/circuit_breaker.py`
- [x] T029 [US3] Implement barge-in detection: when new audio arrives while TTS audio is still streaming to client, immediately cancel the in-progress TTS stream, discard remaining audio, and process the new utterance as a fresh turn in `src/pipeline/orchestrator.py`

**Checkpoint**: System handles all degradation scenarios gracefully. No silent failures. Barge-in works. Auto-recovery confirmed.

---

## Phase 6: User Story 4 — Per-Request Latency Visibility (Priority: P4)

**Goal**: Every request emits telemetry with per-stage latency breakdown. Operators can view P50/P95/P99 aggregated metrics.

**Independent Test**: Process a voice request E2E, verify telemetry contains ASR latency, LLM TTFT, TTS TTFB, orchestration overhead, and total E2E. Check P50/P95/P99 after multiple requests.

### Implementation for User Story 4

- [x] T030 [P] [US4] Implement per-request latency tracker: instrument the orchestrator to capture timestamps at each stage boundary (ASR start/end, LLM first token, TTS first byte) and compute deltas, populating a LatencyRecord in `src/telemetry/metrics.py`
- [x] T031 [P] [US4] Implement P50/P95/P99 percentile aggregator using a sliding window of recent LatencyRecords with configurable window size in `src/telemetry/metrics.py`
- [x] T032 [US4] Wire latency tracker into orchestrator: start timers at each pipeline stage, record completion, build LatencyRecord per request, flag budget breaches, and emit via structured logger in `src/pipeline/orchestrator.py`
- [x] T033 [US4] Implement telemetry dashboard endpoint (HTTP GET) that returns current P50/P95/P99 percentiles for all latency components as JSON in `src/telemetry/dashboard.py`
- [x] T034 [US4] Add faithfulness check: after LLM completes and before TTS begins, verify the text payload sent to TTS is an exact byte-for-byte match of LLM output; log any mismatch as a faithfulness violation in telemetry in `src/pipeline/orchestrator.py`

**Checkpoint**: Full latency observability operational. Operators can diagnose P95/P99 breaches by component.

---

## Phase 7: User Story 5 — Deterministic Replay for Debugging (Priority: P5)

**Goal**: Developers can replay recorded, timestamped audio sessions through the pipeline to reproduce timing-dependent bugs.

**Independent Test**: Record a session, replay it, verify the same sequence of transcription and response events is produced.

### Implementation for User Story 5

- [x] T035 [P] [US5] Implement session recorder: capture all incoming audio chunks with timestamps and all pipeline events for a session, serializable to JSON in `src/pipeline/replay.py`
- [x] T036 [US5] Implement replay engine: accept a recorded session file, feed audio chunks into the pipeline at original timestamps (or modified timing), and emit pipeline events in `src/pipeline/replay.py`
- [x] T037 [US5] Add replay mode entry point: support a CLI flag or API endpoint that accepts a recorded session file path and runs it through replay instead of live WebSocket input in `src/server.py`
- [x] T038 [US5] Support timing modification in replay: allow configurable delay multipliers to simulate slow services during replay for degradation path testing in `src/pipeline/replay.py`
- [x] T039 [US5] Create a sample recorded session fixture for testing replay functionality in `tests/fixtures/sample_session.json`

**Checkpoint**: Developers can replay any recorded session deterministically. Race conditions and transcription errors are reproducible.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T040 [P] Write README.md as a Technical Report: system architecture overview, technology selection trade-offs (ASR/LLM/TTS choices), latency budget breakdown, and a "Lessons Learned & Iterative Pivots" section in `README.md`
- [x] T041 [P] Add concurrent session handling: verify `session_manager` supports 50 simultaneous sessions with proper isolation, no cross-session state leakage, and no event-loop blocking in `src/pipeline/session_manager.py`
- [x] T042 [P] Create FMEA document: enumerate all identified failure modes (ASR timeout, LLM 503, TTS connection drop, WebSocket disconnect, malformed audio), their severity, likelihood, and the mitigation strategy implemented in `docs/fmea.md`
- [x] T043 Security hardening: verify WSS/TLS enforcement rejects plain WS connections, confirm ephemeral data purge on session close, audit for correlation ID leakage in `src/server.py`
- [x] T044 Code cleanup: ensure all modules have docstrings, type hints on all public functions, and consistent error handling patterns across `src/`
- [x] T045 Run end-to-end validation: start server, connect WebSocket client, send audio, verify full pipeline (transcription → response → audio playback) works within latency targets

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — delivers MVP
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2); extends ASR adapter from US1
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2); wraps service adapters from US1
- **User Story 4 (Phase 6)**: Depends on Foundational (Phase 2); instruments orchestrator from US1
- **User Story 5 (Phase 7)**: Depends on Foundational (Phase 2); records events from orchestrator
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **User Story 2 (P2)**: Can start after Phase 2 — extends ASR streaming from US1, but independently testable (provisional transcription works even without full pipeline)
- **User Story 3 (P3)**: Can start after Phase 2 — wraps the same service adapters, independently testable via simulated failures
- **User Story 4 (P4)**: Can start after Phase 2 — instruments the orchestrator, independently testable via metrics endpoint
- **User Story 5 (P5)**: Can start after Phase 2 — records/replays sessions, independently testable via fixture playback

### Within Each User Story

- Models before services
- Services before orchestrator integration
- Orchestrator integration before server wiring
- Core implementation before edge-case handling

### Parallel Opportunities

- **Phase 1**: T003 and T004 can run in parallel
- **Phase 2**: T006, T007, T009 can run in parallel (different files). T005 should complete first (events.py is imported by other models). T008 and T010 are independent of each other.
- **Phase 3**: T011, T012, T013 can run in parallel (three different service adapter files)
- **Phase 5**: T022, T023 can run in parallel (different fallback files)
- **Phase 6**: T030, T031 can run in parallel (same file but independent functions)
- **Phase 7**: T035 can start independently
- **Phase 8**: T040, T041, T042 can run in parallel (different files)

---

## Parallel Example: User Story 1

```bash
# Launch all three service adapters in parallel (different files):
Task T011: "Implement ASR service adapter in src/services/asr.py"
Task T012: "Implement LLM service adapter in src/services/llm.py"
Task T013: "Implement TTS service adapter in src/services/tts.py"

# Then sequentially:
Task T014: "Implement session manager in src/pipeline/session_manager.py"
Task T015: "Implement orchestrator in src/pipeline/orchestrator.py"
Task T016: "Integrate with server in src/server.py"
```

## Parallel Example: User Story 3

```bash
# Launch fallback infrastructure in parallel (different files):
Task T022: "Create bridge audio assets in src/fallback/bridge_audio.py"
Task T023: "Implement fallback strategy registry in src/fallback/strategies.py"

# Then wrap each service adapter with circuit breaker (can be parallelized across adapters):
Task T024: "Wrap ASR with circuit breaker in src/services/asr.py"
Task T025: "Wrap LLM with circuit breaker in src/services/llm.py"
Task T026: "Wrap TTS with circuit breaker in src/services/tts.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test E2E voice loop independently — send audio, get spoken response
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (**MVP!**)
3. Add User Story 2 → Test independently → Deploy/Demo (live transcription feedback)
4. Add User Story 3 → Test independently → Deploy/Demo (graceful degradation)
5. Add User Story 4 → Test independently → Deploy/Demo (latency observability)
6. Add User Story 5 → Test independently → Deploy/Demo (replay debugging)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (MVP — highest priority)
   - Developer B: User Story 3 (circuit breaker + fallbacks — can stub services)
   - Developer C: User Story 4 (telemetry — can instrument stubs)
3. After US1 completes, US2 extends the ASR adapter
4. US5 can start any time after Phase 2

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- No test tasks generated (tests not explicitly requested in spec)
