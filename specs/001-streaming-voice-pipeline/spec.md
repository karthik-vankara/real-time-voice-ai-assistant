# Feature Specification: Real-Time Streaming Voice Assistant

**Feature Branch**: `001-streaming-voice-pipeline`  
**Created**: 2026-03-04  
**Status**: Draft  
**Input**: User description: "Build a real-time streaming voice assistant. It should continuously listen to user speech (sent in audio chunks via WebSocket), transcribe it with minimal delay, generate a contextual response with an LLM, and speak the answer via text-to-speech—all in a seamless pipeline. The system must target sub-1.2s p95 end-to-end latency and must handle slowdowns gracefully (e.g. by playing a 'thinking...' audio or switching to a faster model). Do not specify particular vendors; focus on the user experience (instant voice interaction, clear feedback on delays) and key requirements (streaming pipeline, strict latency SLOs, and fallback behavior)."

## Clarifications

### Session 2026-03-04

- Q: What is the transport security and audio data retention policy? → A: Encrypted transport (WSS) required; audio and transcriptions retained only for the session lifetime (ephemeral).
- Q: What is the maximum conversation context window size? → A: Last 10 conversational turns (user + assistant pairs).
- Q: When should the circuit breaker open (threshold strategy)? → A: After 3 consecutive failures or timeouts within a 30-second window.
- Q: On barge-in, what happens to the in-progress response? → A: Cancel and discard the interrupted response entirely; process the new utterance immediately.
- Q: How is the faithfulness check implemented? → A: Text-level input verification — confirm TTS input text matches LLM output text exactly (zero latency overhead).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Speak and Hear an Instant Response (Priority: P1)

A user opens the voice assistant, begins speaking naturally, and hears a spoken response within moments of finishing their utterance. The user perceives the interaction as conversational—there is no visible "processing" spinner, no awkward silence. Audio flows in both directions seamlessly.

**Why this priority**: This is the fundamental value proposition. Without a working end-to-end voice loop (speech → transcription → reasoning → spoken reply), no other feature has meaning. It validates the entire streaming pipeline.

**Independent Test**: Connect a client that sends a pre-recorded audio clip via WebSocket, verify the system returns an audible spoken response, and confirm the total elapsed time from the end of speech to the start of audio playback is under 1.2 seconds at the 95th percentile.

**Acceptance Scenarios**:

1. **Given** the assistant is idle and listening, **When** the user speaks a complete sentence ("What is the weather like today?"), **Then** the system begins playing a spoken response within 1.2 seconds (P95) of the user finishing their sentence.
2. **Given** the assistant is idle and listening, **When** the user speaks a short phrase ("Hello"), **Then** the system produces a contextually appropriate spoken reply (e.g., a greeting) and the reply audio begins within the latency target.
3. **Given** the user is mid-conversation, **When** the user asks a follow-up question, **Then** the system uses prior conversational context to produce a relevant spoken answer.

---

### User Story 2 - Real-Time Transcription Feedback (Priority: P2)

While the user is speaking, the system provides real-time provisional transcription feedback so the user can see their words being recognized. Once the user pauses, the transcription is finalized and sent for reasoning.

**Why this priority**: Visual transcription feedback reassures the user that the system is listening and understanding them. This is critical for trust and perceived responsiveness, even though the core pipeline can function without it.

**Independent Test**: Connect a client that sends streaming audio, observe that provisional transcription events are emitted within 300 ms of each audio chunk, and verify that a final transcription event is emitted when the user stops speaking.

**Acceptance Scenarios**:

1. **Given** the user is speaking, **When** audio chunks arrive at the system, **Then** provisional transcription events are emitted continuously so the user sees their words appearing in near real-time.
2. **Given** the user has been speaking, **When** the user pauses for a natural sentence boundary, **Then** a final transcription event is emitted that represents the complete, corrected text of the utterance.
3. **Given** the user speaks an ambiguous or mumbled phrase, **When** the provisional transcription is inaccurate, **Then** the final transcription corrects itself to the best possible interpretation without user intervention.

---

### User Story 3 - Graceful Degradation Under Slowdowns (Priority: P3)

When any component in the pipeline (speech recognition, reasoning, or speech synthesis) experiences high latency or becomes temporarily unavailable, the user receives clear audible feedback rather than silence. The system degrades gracefully—for example, playing a "Let me think about that..." bridge audio—and recovers automatically when services return to normal.

**Why this priority**: Production systems inevitably face service instability. Handling degradation gracefully is what separates a demo from a production-ready product. Without this, users encounter unexplained silences and abandon the experience.

**Independent Test**: Simulate a slow or unresponsive reasoning service, verify the system plays a bridge audio response within the latency target, and confirm it seamlessly resumes normal responses when the service recovers.

**Acceptance Scenarios**:

1. **Given** the reasoning service is responding slowly (exceeding its latency budget), **When** the user asks a question, **Then** the system plays an audible bridge response (e.g., "Let me think about that...") within the overall latency target and delivers the full answer when ready.
2. **Given** the speech synthesis service is temporarily unavailable, **When** the system has a generated text response, **Then** it falls back to a pre-generated audio clip acknowledging the delay and retries synthesis automatically.
3. **Given** the speech recognition service times out on an audio chunk, **When** the user has spoken, **Then** the system notifies the user audibly ("I didn't catch that, could you repeat?") and begins listening again.
4. **Given** the reasoning service is persistently slow, **When** multiple successive requests breach the latency budget, **Then** the system automatically switches to a faster, lower-fidelity reasoning approach to maintain responsiveness.
5. **Given** a degraded service recovers, **When** the next user utterance arrives, **Then** the system routes to the primary service again and resumes full-quality responses.

---

### User Story 4 - Per-Request Latency Visibility (Priority: P4)

An operator or developer can view a breakdown of latency for each request—showing how much time was spent in speech recognition, reasoning, speech synthesis, and orchestration overhead. This visibility enables performance debugging and ensures the latency budget is being met.

**Why this priority**: Without observability into latency components, the team cannot diagnose P95/P99 breaches or make informed optimization decisions. This story supports the operational maturity required for production.

**Independent Test**: Process a voice request end-to-end and verify that telemetry data is emitted containing per-stage timing (ASR, LLM TTFT, TTS TTFB, orchestration overhead, total E2E) with P50/P95/P99 aggregation.

**Acceptance Scenarios**:

1. **Given** a voice request has been processed, **When** an operator inspects telemetry, **Then** the latency is decomposed into: speech recognition time, reasoning time-to-first-token, synthesis time-to-first-byte, orchestration overhead, and total end-to-end time.
2. **Given** multiple requests have been processed, **When** an operator views aggregated metrics, **Then** P50, P95, and P99 percentiles are available for each latency component.
3. **Given** a request breaches the P95 latency target, **When** the operator reviews that request, **Then** the telemetry clearly identifies which component exceeded its budget allocation.

---

### User Story 5 - Deterministic Replay for Debugging (Priority: P5)

A developer can feed a recorded, timestamped audio session back through the pipeline to reproduce timing-dependent bugs, transcription errors, or race conditions in a controlled environment.

**Why this priority**: Real-time streaming systems produce non-deterministic bugs that are notoriously difficult to reproduce. Replay mode is essential for reliable debugging and regression testing but is not needed for core functionality.

**Independent Test**: Record a session that triggers a known edge case, replay it through the pipeline, and verify the same sequence of events (transcriptions, responses, timings) is reproduced.

**Acceptance Scenarios**:

1. **Given** a recorded audio session with timestamps, **When** a developer feeds it into replay mode, **Then** the pipeline processes it identically to a live session and emits the same sequence of pipeline events.
2. **Given** a recorded session that originally triggered a race condition, **When** replayed, **Then** the race condition is reproduced consistently, enabling diagnosis.
3. **Given** a recorded session, **When** replayed with modified timing parameters, **Then** the developer can simulate slower services to test degradation paths.

---

### Edge Cases

- **Silence / no speech**: What happens when the user connects but does not speak for an extended period? The system should remain in a listening state without timing out prematurely. After a configurable idle period (default: 60 seconds), the system may send a gentle prompt or close the session gracefully.
- **Overlapping speech (barge-in)**: What happens when the user begins speaking while the assistant is still delivering a response? The system detects the interruption, immediately cancels and discards the in-progress response (stops audio playback), and processes the new utterance as a fresh conversational turn.
- **Very long utterances**: What happens when the user speaks continuously for over 30 seconds? The system should process the audio in streaming chunks and produce intermediate transcriptions, handling the full utterance even if it exceeds typical sentence length.
- **Background noise**: How does the system handle sustained background noise without speech? The system should not emit false transcriptions for non-speech audio; voice activity detection should filter noise.
- **Multiple rapid utterances**: What happens when the user fires several short questions in quick succession? The system should queue and process each utterance sequentially, delivering responses in order without dropping any.
- **Network interruption mid-utterance**: What happens when the WebSocket connection drops briefly while the user is speaking? The system should detect the disconnection, allow reconnection, and either resume the session or cleanly start a new one.
- **Malformed audio input**: What happens when the system receives corrupted or unsupported audio data? The system should reject the chunk with a structured error event and continue listening for valid audio.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept streaming audio input from a client via a persistent bidirectional connection and process it in real-time chunks (no batch upload required).
- **FR-002**: System MUST transcribe incoming audio with both provisional (partial) and final transcription outputs, streaming provisional results back to the client as audio is received.
- **FR-003**: System MUST send final transcriptions to a reasoning service that generates a contextual, conversational response.
- **FR-004**: System MUST support multi-turn conversation context so that follow-up questions receive contextually relevant answers. The context window MUST be capped at the last 10 conversational turns (user utterance + assistant response pairs); older turns are discarded on a rolling basis.
- **FR-005**: System MUST synthesize the reasoning service's text output into streaming audio and begin playback to the user as soon as the first audio segment is available (not waiting for complete synthesis).
- **FR-006**: System MUST enforce strict schema validation on all inter-service messages; every event transmitted through the pipeline MUST conform to a registered, versioned schema.
- **FR-007**: System MUST define and implement explicit event types including at minimum: `speech_started`, `transcription_provisional`, `transcription_final`, `llm_token_generated`, `tts_audio_chunk`, and `error`.
- **FR-008**: System MUST handle concurrent connections without blocking; one slow client MUST NOT degrade performance for other connected users.
- **FR-009**: System MUST implement circuit-breaking logic for each external service (speech recognition, reasoning, speech synthesis) with configurable timeout thresholds. The circuit MUST open after 3 consecutive failures or timeouts within a 30-second sliding window. Once open, all requests to the affected service are routed to the defined fallback until the circuit enters a half-open probe state.
- **FR-010**: System MUST provide at least one fallback behavior when each service exceeds its latency budget: an audible bridge response for slow reasoning, a cached fallback audio for synthesis failure, and an audible retry prompt for recognition failure.
- **FR-011**: System MUST support switching to a faster, lower-fidelity reasoning approach when the primary reasoning service is persistently slow.
- **FR-012**: System MUST detect user barge-in (user speaking while assistant audio is playing) and immediately cancel the in-progress response—stopping audio playback and discarding any remaining synthesized audio. The new utterance MUST be processed as a fresh turn with full priority.
- **FR-013**: System MUST track and emit per-request latency telemetry decomposed into: speech recognition time, reasoning time-to-first-token, synthesis time-to-first-byte, orchestration overhead, and total end-to-end response time.
- **FR-014**: System MUST aggregate latency telemetry into P50, P95, and P99 percentiles and make them accessible for monitoring.
- **FR-015**: System MUST support a replay mode that accepts recorded, timestamped audio sessions and processes them through the pipeline identically to live input.
- **FR-016**: System MUST emit structured log events with correlation IDs that trace a single user utterance across all pipeline stages.
- **FR-017**: System MUST perform a faithfulness check verifying that the text sent to the speech synthesis service is an exact match of the reasoning service's generated text output (text-level input verification). Any mismatch (truncation, mutation, insertion) MUST be logged as a faithfulness violation and the response MUST be flagged in telemetry. No audio re-transcription round-trip is required.
- **FR-018**: System MUST validate all incoming audio against expected formats and reject malformed input with a structured error event.
- **FR-019**: System MUST handle client disconnection gracefully, cleaning up resources and session state without affecting other active sessions.

### Key Entities

- **Session**: Represents a single user conversation session. Attributes: unique session ID, connection state (active/idle/closed), conversation history, creation timestamp, last activity timestamp, idle timeout configuration.
- **Utterance**: A single spoken input from the user within a session. Attributes: utterance ID, parent session ID, raw audio reference, provisional transcriptions (ordered list), final transcription, timestamps (speech start, speech end, transcription final).
- **Pipeline Event**: A structured message flowing through the pipeline. Attributes: event type (from the defined set), correlation ID (links to utterance), timestamp, payload (schema-validated content specific to event type), source stage.
- **Response**: The system's reply to an utterance. Attributes: response ID, parent utterance ID, generated text from reasoning, synthesized audio segments (streaming), latency breakdown (per-stage timings), degradation flag (whether fallback was used).
- **Latency Record**: Per-request performance data. Attributes: correlation ID, ASR latency, LLM time-to-first-token, TTS time-to-first-byte, orchestration overhead, total end-to-end time, timestamp, whether any budget was breached.

## Assumptions

- The system is designed for single-user-per-session interaction (one speaker per connection); multi-speaker diarization is out of scope.
- Audio format negotiation (sample rate, codec) will use sensible defaults (16 kHz, 16-bit PCM) with the ability to configure at connection time.
- Conversation context is maintained in-memory for the duration of a session, capped at the last 10 conversational turns (user + assistant pairs). Older turns are discarded on a rolling basis. Long-term persistence of conversation history across sessions is out of scope for this feature.
- The idle timeout before session cleanup defaults to 60 seconds but is configurable.
- Voice activity detection (distinguishing speech from silence/noise) is assumed to be a capability of the speech recognition stage.
- The system targets a single language (English) initially; multi-language support is a future enhancement.
- Authentication and authorization for connecting clients are out of scope for this feature and will be addressed separately.
- All WebSocket connections MUST use encrypted transport (WSS/TLS). Unencrypted WS connections MUST be rejected.
- Audio data and transcription content are ephemeral: retained only for the lifetime of the active session and purged on session close. No persistent storage of voice data occurs within this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of voice requests receive the start of a spoken response within 1.2 seconds of the user finishing their utterance (P95 end-to-end latency < 1.2 s).
- **SC-002**: 99% of voice requests receive the start of a spoken response within 1.8 seconds (P99 end-to-end latency < 1.8 s).
- **SC-003**: Provisional transcription feedback appears to the user within 300 milliseconds of each audio chunk being received.
- **SC-004**: When any pipeline component exceeds its latency budget, the user hears audible feedback (bridge response or error prompt) within the overall 1.2-second P95 target—never silence.
- **SC-005**: The system recovers from a degraded service state and resumes full-quality responses within 10 seconds of the service returning to normal operation.
- **SC-006**: Per-request latency telemetry is available for 100% of processed requests, decomposed into all defined stages.
- **SC-007**: A recorded audio session can be replayed through the pipeline and produces the same sequence of transcription and response events as the original live session.
- **SC-008**: The system supports at least 50 concurrent voice sessions without any single session's P95 latency exceeding the 1.2-second target.
- **SC-009**: The faithfulness check confirms that synthesized audio matches the reasoning service's text output for at least 99% of responses (no hallucination during synthesis).
- **SC-010**: Barge-in detection interrupts assistant playback and begins processing the new utterance within 500 milliseconds of the user starting to speak.
