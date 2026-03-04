<!--
  Sync Impact Report
  ===========================
  Version change: N/A (initial) → 1.0.0
  Modified principles: N/A (initial ratification)
  Added sections:
    - Core Principles (7 principles)
    - Performance Standards & Latency Budget
    - Development Workflow & Quality Gates
    - Governance
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ compatible (Constitution Check
      section is dynamic; Performance Goals / Constraints fields align
      with Principle III latency budget)
    - .specify/templates/spec-template.md ✅ compatible (requirements and
      success criteria sections align with measurable principle gates)
    - .specify/templates/tasks-template.md ✅ compatible (phase structure
      maps to the 3-phase roadmap; foundational phase aligns with
      Principles I-II; polish phase covers Principles V-VII)
  Follow-up TODOs: none
-->

# Real-Time AI Voice Assistant Constitution

## Core Principles

### I. Streaming-First Pipeline Architecture

- Every feature MUST be designed as a component within a modular,
  event-driven streaming pipeline.
- The orchestration layer MUST use WebSockets for low-latency,
  bidirectional full-duplex communication between all services
  (ASR, LLM, TTS).
- The pipeline MUST support non-blocking I/O: the WebSocket server
  MUST handle concurrent streams without blocking the event loop,
  allowing simultaneous ASR ingestion and LLM processing.
- Each pipeline component (ASR, Reasoning, TTS) MUST be independently
  deployable and replaceable without requiring changes to adjacent
  components.

**Rationale**: A streaming-first design ensures deterministic data
movement and enables the sub-1.2 s latency target. Blocking any
single stage propagates delay across the entire user-facing response.

### II. Strict Schema Validation (NON-NEGOTIABLE)

- All WebSocket events MUST be validated against a strict JSON schema
  enforced by a validation library (Pydantic or equivalent).
- The project MUST define and implement explicit event types including
  at minimum: `speech_started`, `transcription_provisional`,
  `transcription_final`, `llm_token_generated`, `tts_audio_chunk`,
  and `error`.
- No untyped or free-form string payloads are permitted on the
  WebSocket protocol. Every message MUST conform to a registered
  schema.
- Schema changes MUST follow a versioned migration process; breaking
  changes require a MAJOR version bump in the event protocol.

**Rationale**: Strict schemas eliminate an entire class of runtime
bugs caused by malformed payloads, enable deterministic testing,
and provide self-documenting contracts between pipeline stages.

### III. Latency Budget Discipline (NON-NEGOTIABLE)

- The system MUST sustain a P95 total end-to-end response time of
  less than 1.2 seconds (from end of user speech to start of audio
  playback).
- Relying on "average" latency as the sole performance indicator is
  PROHIBITED. All latency reporting MUST include P50, P95, and P99
  percentiles.
- The following metrics MUST be tracked individually per request:
  - **ASR Latency**: audio chunk submission → final transcription.
  - **LLM TTFT**: transcription delivery → first reasoning token.
  - **TTS TTFB**: first LLM token sent → first audio byte received.
  - **Orchestration Overhead**: serialization, deserialization, and
    network round-trip time between services.
  - **Total E2E Response Time**: end of user speech → start of audio
    playback.
- Every component MUST have an explicit latency budget allocation
  documented in the implementation plan.

**Rationale**: User-perceived quality degrades non-linearly at tail
latencies. A P95 discipline exposes the performance spikes that
averages conceal and forces engineering investment where it matters.

### IV. Resilience & Graceful Degradation

- The system MUST implement circuit-breaking logic for every external
  service call (ASR, LLM, TTS). No single component is permitted to
  block the pipeline indefinitely.
- Every external call MUST have an explicit timeout. If the timeout is
  exceeded, the circuit breaker MUST trigger a fallback strategy.
- Fallback strategies MUST be defined for each service:
  - **LLM high latency**: emit an audible "bridge" response
    (e.g., "Let me think...") or switch to a lower-latency model.
  - **TTS failure**: fall back to a cached or pre-generated audio
    clip indicating temporary degradation.
  - **ASR failure**: notify the user audibly and retry with
    exponential backoff.
- System design MUST be informed by Failure Mode and Effects Analysis
  (FMEA); each identified failure mode MUST have a documented
  severity, likelihood, and mitigation strategy.

**Rationale**: Real-world voice systems face inevitable service
interruptions. A system that hangs silently is worse than one that
communicates degradation transparently to the user.

### V. Observability & Telemetry

- The system MUST expose a real-time telemetry dashboard (or
  structured console output) that decomposes latency for every
  request into its component stages.
- All services MUST emit structured logs (JSON format) with
  correlation IDs that trace a single user utterance across the
  full pipeline.
- Metrics MUST be exportable in a standard format (e.g., Prometheus,
  OpenTelemetry) for integration with external monitoring.
- Anomaly detection SHOULD alert when P99 latency exceeds the 1.2 s
  budget for a sustained window.

**Rationale**: You cannot optimize what you cannot measure. Per-request
latency decomposition pinpoints which component is responsible for a
P99 breach, turning vague performance complaints into actionable
engineering tasks.

### VI. Deterministic Debugging & Replay

- The system MUST support a Replay Mode that feeds recorded,
  timestamped audio inputs back through the pipeline to reproduce
  issues deterministically.
- All pipeline events MUST be loggable with timestamps sufficient
  for post-hoc replay at original timing fidelity.
- A "Golden Evaluation" check MUST verify that the assistant's
  voice output remains faithful to the LLM's generated intent—no
  hallucination or drift may be introduced during streaming TTS
  synthesis.
- Race conditions and transcription errors MUST be reproducible in
  a controlled environment using replay data before they are
  considered resolved.

**Rationale**: Real-time systems exhibit timing-dependent bugs that
are impossible to reproduce with standard unit tests. Replay mode
transforms ephemeral failures into repeatable, debuggable artifacts.

### VII. Documentation as Engineering Record

- The project README MUST serve as a Technical Report, not a setup
  guide alone.
- The README MUST include a "Lessons Learned & Iterative Pivots"
  section documenting at least one specific failure encountered
  during development and the systematic engineering steps taken
  to resolve it.
- All technology selection decisions (e.g., Deepgram vs. Whisper,
  ElevenLabs vs. Cartesia) MUST be documented with explicit
  trade-off rationale covering latency, accuracy, cost, and
  integration complexity.
- Architecture Decision Records (ADRs) SHOULD be maintained for
  significant design changes.

**Rationale**: Documenting pivots and trade-offs demonstrates
system-level thinking and differentiates a senior architect from a
tutorial follower. The engineering narrative is as valuable as the
code itself.

## Performance Standards & Latency Budget

The following performance standards are mandatory for production
readiness and MUST be validated before any release:

| Metric                  | P50 Target | P95 Target | P99 Target |
|-------------------------|------------|------------|------------|
| ASR Latency             | < 300 ms   | < 500 ms   | < 700 ms   |
| LLM TTFT               | < 200 ms   | < 400 ms   | < 600 ms   |
| TTS TTFB               | < 150 ms   | < 250 ms   | < 400 ms   |
| Orchestration Overhead  | < 50 ms    | < 100 ms   | < 150 ms   |
| **Total E2E Response**  | **< 700 ms** | **< 1200 ms** | **< 1800 ms** |

- These targets MUST be measured under realistic concurrent-load
  conditions, not single-request benchmarks.
- Any breach of the P95 total E2E target MUST trigger an
  investigation and documented remediation plan.
- Technology selection (ASR provider, LLM model size, TTS engine)
  MUST be justified against these targets with benchmark data.

### Technology Stack Guidance

| Component       | Recommended          | Role in Pipeline                              |
|-----------------|----------------------|-----------------------------------------------|
| Orchestration   | WebSockets           | Low-latency bidirectional full-duplex comms    |
| ASR             | Deepgram or Whisper  | Real-time audio → text transcription           |
| Reasoning       | LLM (model-agnostic) | Contextual response generation                |
| TTS             | ElevenLabs / Cartesia| Text → high-fidelity streaming audio           |

Selection trade-offs to document:
- **Deepgram vs. Whisper**: streaming latency vs. batch accuracy.
- **ElevenLabs vs. Cartesia**: vocal naturalness vs. ultra-low TTFB.

## Development Workflow & Quality Gates

### Phased Implementation Roadmap

| Phase            | Core Skill                          | Key Trade-off                            |
|------------------|-------------------------------------|------------------------------------------|
| Phase 1: Pipeline| System Integration & Schema Design  | Developer Velocity vs. Type Safety       |
| Phase 2: Latency | Performance Engineering             | Cost vs. Speed (P95 Optimization)        |
| Phase 3: Resilience | Reliability Engineering (SRE)    | Quality vs. Availability (Degradation)   |

### Quality Gates

1. **Schema Gate**: No WebSocket message may be transmitted without
   passing Pydantic (or equivalent) validation. CI MUST enforce
   schema contract tests.
2. **Latency Gate**: Every PR that modifies the hot path MUST include
   benchmark results demonstrating no P95 regression.
3. **Resilience Gate**: Before Phase 3 completion, every identified
   FMEA failure mode MUST have a passing integration test that
   exercises the fallback path.
4. **Replay Gate**: Critical bug fixes MUST include a replay test
   case that reproduces the original failure.
5. **Documentation Gate**: PRs introducing new services or changing
   the pipeline topology MUST update the README trade-off analysis
   and architecture diagrams.

### Code Review Requirements

- All PRs MUST be reviewed against the Constitution principles
  before merge.
- Performance-sensitive changes MUST include latency benchmark data
  in the PR description.
- Schema changes MUST include migration documentation.

## Governance

- This Constitution supersedes all other development practices and
  conventions for this project. In case of conflict, the Constitution
  is authoritative.
- Amendments to this Constitution MUST follow this procedure:
  1. Propose the change with rationale in a dedicated PR.
  2. Document the impact on existing principles and downstream
     templates.
  3. Update the version according to semantic versioning:
     - **MAJOR**: Principle removal or incompatible redefinition.
     - **MINOR**: New principle or materially expanded guidance.
     - **PATCH**: Clarifications, wording, or non-semantic fixes.
  4. Update the Sync Impact Report at the top of this file.
- Compliance reviews MUST occur at the start of each development
  phase (Pipeline, Latency, Resilience) to verify alignment with
  the principles defined herein.
- All PRs and code reviews MUST verify compliance with the
  applicable principles. Deviations MUST be documented in the
  Complexity Tracking section of the implementation plan with
  explicit justification.

**Version**: 1.0.0 | **Ratified**: 2026-03-04 | **Last Amended**: 2026-03-04
