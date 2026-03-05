# How It Works - Complete User Journey

## End-to-End User Experience

### 📍 Step 1: User Opens Browser
```
http://localhost:5173 (Vite dev server)
    ↓
main.tsx mounts App component
    ↓
App renders with useEffect hooks
    ↓
WebSocket client created (NOT connected yet)
    ↓
Browser shows UI with "Connect" button
```

### 🔌 Step 2: User Clicks "Connect"
```
ConnectionPanel.handleConnect()
    ↓
WebSocketClient.connect()
    ↓
Opens WebSocket to ws://localhost:8000/ws
    ↓
Server: websocket_endpoint() called
    ↓
Server checks TLS (disabled in dev)
    ↓
Server: await ws.accept()
    ↓
Server: await handle_session(ws) starts
    ↓
Session created with session_id
    ↓
Backend: await _session_loop() listening for messages
    ↓
Frontend: onConnect callback → setIsConnected(true)
    ↓
"Start Recording" button appears ✅
```

### 🎤 Step 3: User Clicks "Start Recording"
```
AudioRecorder.startRecording()
    ↓
navigator.mediaDevices.getUserMedia()
    ↓
Browser: "Microphone access required" permission dialog
    ↓
User clicks "Allow"
    ↓
AudioContext created
    ↓
MediaStreamSource connected to microphone
    ↓
ScriptProcessorNode (4096-sample buffer) created
    ↓
onaudioprocess handler registered
    ↓
UI shows "Recording: 0:00" timer
    ↓
Ready to capture audio ✅
```

### 🗣️ Step 4: User Speaks
```
Microphone pickups analog sound
    ↓
AudioContext resamples 48kHz → 16kHz
    ↓
Every ~256ms, onaudioprocess fires:
    ├─ inputBuffer.getChannelData(0) → Float32Array
    ├─ floatTo16BitPCM() conversion:
    │  ├─ For each of 4096 samples:
    │  ├─ Clamp to [-1, 1]
    │  ├─ Scale: s < 0 ? s * 0x8000 : s * 0x7fff
    │  └─ Result: 16-bit signed int
    ├─ Create Int16Array (4096 elements)
    ├─ Create Uint8Array view (8192 bytes)
    └─ Return Uint8Array
    ↓
WebSocketClient.sendAudio(pcmData)
    ↓
WebSocket binary frame sent to server
    ↓
Server receives binary message
    ↓
_session_loop(): message.get("bytes") → raw PCM data
    ↓
validate_audio_frame() checks:
    ├─ Not empty? ✓
    ├─ Even byte length (16-bit requirement)? ✓
    ├─ Can unpack as int16? ✓
    ↓
audio_chunks.append(pcmData)
    ↓
Repeat: Every ~256ms, new chunk arrives
```

### ⏹️ Step 5: User Stops Recording
```
User clicks "Stop Recording"
    ↓
AudioRecorder.stopRecording()
    ↓
Disconnect processor
Close audio context
Stop microphone tracks
    ↓
WebSocketClient.sendControl('end_of_utterance')
    ↓
WebSocket text message: {"action": "end_of_utterance"}
    ↓
Server receives text message
    ↓
_session_loop(): message.get("text") where action == "end_of_utterance"
    ↓
Break inner loop → exit audio accumulation phase
    ↓
✅ Ready to process pipeline
```

---

## 🔄 Pipeline Execution (Backend)

### Phase 1: Send Initial Event
```
Server: SpeechStartedEvent created
    ├─ correlation_id: "xyz-123"
    ├─ timestamp: "2026-03-05T12:34:56Z"
    └─ payload: {session_id}
    ↓
await ws.send_json(event.model_dump())
    ↓
Frontend: WebSocket.onmessage
    ├─ Parse JSON
    ├─ App.onMessage(event)
    ├─ setEvents([event, ...prev])
    ↓
EventsDisplay shows blue "Speech Started" card ✅
```

### Phase 2: ASR (Speech → Text) = ~250-300ms
```
LatencyTracker.start("asr")
    ↓
ASRService.transcribe(audio_chunks):
    ├─ If mode="mock": await asyncio.sleep(0.25)
    ├─ If mode="real": Call OpenAI Whisper API
    ↓
Returns: "Hello, how are you?"
    ↓
LatencyTracker.stop("asr")
    ↓
Create TranscriptionFinalEvent:
    ├─ event_type: "transcription_final"
    ├─ payload.text: "Hello, how are you?"
    └─ payload.is_final: true
    ↓
await ws.send_json(transcription_event)
    ↓
Frontend: EventsDisplay shows green "✅ Transcription Final" card
    ├─ Displays text: "Hello, how are you?"
    └─ Shows timestamp
```

### Phase 3: LLM (Context + Prompt → Response) = ~140-150ms
```
Get 10-turn conversation history from session
    ├─ Last user: "..."
    ├─ Last assistant: "..."
    └─ ... (up to 10 turns)
    ↓
Build LLM prompt:
```
System: You are a friendly voice assistant.
Context:
User: Hello, how are you?
Assistant: I'm doing well.

Current User: Hello, how are you?
Respond naturally in 1-2 sentences.
```
    ↓
LatencyTracker.start("llm")
    ↓
LLMService.generate(prompt, context):
    ├─ If mode="mock": return "I'm doing great!"
    ├─ If mode="real": Stream from OpenAI GPT-4
    ↓
Receive tokens: "I'm", " doing", " great", "!", etc.
    ↓
LatencyTracker.stop("llm")
    ↓
For each token, create LLMTokenEvent:
    ├─ event_type: "llm_token"
    ├─ payload.token: "I'm"
    └─ (repeat for each token)
    ↓
await ws.send_json(token_event) for each token (streamed)
    ↓
Frontend: EventsDisplay shows purple cards
    ├─ One card per token: "I'm", "doing", "great", "!"
    └─ User sees response being generated in real-time
```

### Phase 4: TTS (Text → Audio) = ~130-140ms
```
Concatenate all LLM tokens: "I'm doing great!"
    ↓
LatencyTracker.start("tts")
    ↓
TTSService.synthesize(text):
    ├─ If mode="mock": Yield 5 chunks of silence
    ├─ If mode="real": Stream from HuggingFace TTS
    ↓
Receive audio chunks: bytes
    ↓
For each chunk, create TTSAudioChunkEvent:
    ├─ event_type: "tts_audio_chunk"
    ├─ payload.audio: base64-encoded audio
    └─ (repeat for each chunk)
    ↓
await ws.send_json(tts_chunk_event) for each chunk (streamed)
    ↓
LatencyTracker.stop("tts")
    ↓
Frontend: EventsDisplay shows cyan cards
    ├─ One card per audio chunk
    └─ (Browser could play audio in real-time with WebAudio API)
```

### Phase 5: Update & Telemetry
```
Compute total latency:
    ├─ asr_ms: 280.5
    ├─ llm_ms: 145.2
    ├─ tts_ms: 135.8
    └─ total_e2e_ms: 561.5
    ↓
Check budget breaches:
    ├─ ASR 280.5 < 500? ✓
    ├─ LLM 145.2 < 400? ✓
    ├─ TTS 135.8 < 250? ✓
    └─ All good, log normally
    ↓
Add to session history:
    ├─ session.add_turn(
    │   user_text="Hello, how are you?",
    │   assistant_text="I'm doing great!"
    │ )
    └─ Now session has 1 turn (for next request)
    ↓
Add latency record to aggregator:
    ├─ aggregator.add(record)
    ├─ Sliding window (keep last 100 records)
    └─ Old records auto-drop
    ↓
Log latency summary
```

---

## 📊 Telemetry & Metrics

### Real-Time Polling (Frontend)
```
useEffect[]:
    ↓
Every 2000ms (2 seconds):
    ├─ fetch('http://localhost:8000/telemetry/latency')
    ↓
Backend response:
{
  "sample_count": 5,
  "percentiles": {
    "asr": {"p50": 245.3, "p95": 298.1, "p99": 301.2},
    "llm_ttft": {"p50": 140.5, "p95": 148.3, "p99": 149.1},
    "tts_ttfb": {"p50": 130.2, "p95": 136.8, "p99": 137.1},
    "total_e2e": {"p50": 532.7, "p95": 574.6, "p99": 578.3}
  }
}
    ↓
Frontend transforms:
    ├─ p50_ms: 532.67733
    ├─ p95_ms: 574.61677
    └─ p99_ms: 578.34472
    ↓
TelemetryDashboard re-renders:
    ├─ P50 card: 532.67733 ms
    │  └─ Progress bar: 532/1200 = 44% → green
    ├─ P95 card: 574.61677 ms
    │  └─ Progress bar: 574/1200 = 48% → green
    └─ P99 card: 578.34472 ms
       └─ Progress bar: 578/1200 = 48% → green
```

### Budget Tracking
```
If any stage exceeds budget:
    ├─ asr_ms > 500? → Log warning
    ├─ llm_ms > 400? → Log warning
    ├─ tts_ms > 250? → Log warning
    └─ total > 1200? → Log warning
    ↓
Logs appear in backend console
Server admin sees performance issue
```

---

## 🔄 Barge-In (Interrupt)

### Scenario: User Interrupts with New Utterance
```
Server processing LLM stage (Token streaming)
    ↓
User starts new recording (during LLM response)
    ↓
AudioRecorder.startRecording() starts new audio capture
    ↓
onaudioprocess fires with new audio
    ↓
WebSocket sends new audio chunk
    ↓
_session_loop() receives new binary message
    ↓
Check: if active_task and not active_task.done():
    ├─ Yes! Previous pipeline is still running
    ├─ active_task.cancel()
    ├─ Emit barge-in log message
    └─ Task raises asyncio.CancelledError
    ↓
Previous _run_pipeline() catches cancellation
    ↓
Cleanup: close DB connections, cleanup resources
    ↓
Start fresh accumulation phase
    ├─ New audio chunks collected
    ├─ User says new utterance
    ├─ Sends end_of_utterance
    └─ New pipeline starts
```

---

## ❌ Error Scenarios

### Scenario 1: User Speaks Too Softly (ASR Fails)
```
ASR Service timeout after 5 seconds
    ↓
Catch exception in _run_asr()
    ↓
Check circuit breaker: _asr_cb.state
    ├─ Still CLOSED? Try again
    ├─ Opened? Use fallback
    ↓
Circuit breaker increment failure_count:
    ├─ 1st failure → stay CLOSED, wait
    ├─ 2nd failure → stay CLOSED
    ├─ 3rd failure → OPEN (stop calling service)
    ↓
Try fallback strategy:
    ├─ Use Mock ASR: return "Could you repeat that?"
    ↓
Create ErrorEvent:
    ├─ event_type: "error"
    ├─ code: "ASR_TIMEOUT"
    ├─ message: "Speech recognition timed out, using fallback"
    ↓
send to client
    ↓
Frontend: Red error card displayed
```

### Scenario 2: Invalid Audio (Client Bug)
```
AudioRecorder accidentally sends odd-byte chunk (client bug)
    ↓
Server receives 8193 bytes (odd!)
    ↓
validate_audio_frame():
    ├─ len(8193) % 2 != 0? True
    ├─ Return error message
    ↓
_session_loop() checks err
    ├─ Send ErrorEvent to client
    └─ Continue listening for next valid frame
    ↓
Frontend: Red error card with message
```

### Scenario 3: Network Disconnection
```
WebSocket closes unexpectedly
    ↓
Server catches WebSocketDisconnect
    ↓
Session cleanup triggered
    ↓
session_manager.close_session(session_id)
    ↓
Frontend: WebSocket.onclose
    ├─ config.onDisconnect()
    ├─ App: setIsConnected(false)
    └─ Hide AudioRecorder
    ↓
StatusHeader shows "Disconnected"
    ↓
Auto-reconnect logic:
    ├─ 1st attempt: 3s delay
    ├─ 2nd attempt: 3s delay
    ├─ ...up to 5 attempts
    └─ Give up after 5 failures
    ↓
User can manually click "Connect" again
```

---

## 📝 Complete Request Lifecycle

```
t=0ms:     User clicks "Start Recording"
t=100ms:   Microphone available
t=256ms:   1st audio chunk (4096 samples)
t=512ms:   2nd audio chunk
t=768ms:   3rd audio chunk
t=1000ms:  User speaks "Hello"
t=1500ms:  User stops recording, sends end_of_utterance
t=1610ms:  Server receives end_of_utterance
           ↓
           ASR starts: LatencyTracker.start("asr")
t=1700ms:  ASR returns transcript: "Hello, how are you?"
           LatencyTracker.stop("asr") → 90ms
           TranscriptionFinalEvent sent to client
           ↓
           LLM starts: LatencyTracker.start("llm")
t=1800ms:  LLM tokens streaming: "I'm", " doing", " great!"
t=1950ms:  LLM complete
           LatencyTracker.stop("llm") → 150ms
           ↓
           TTS starts: LatencyTracker.start("tts")
t=2050ms:  TTS audio chunks streaming
t=2200ms   TTS complete
           LatencyTracker.stop("tts") → 150ms
           ↓
           Total E2E: 90 + 150 + 150 = 390ms ✅
           Added to aggregator
           ↓
t=2500ms:  Frontend polls telemetry
           Gets updated P50/P95/P99
           ↓
t=3000ms:  Frontend polls telemetry again
           Can record new utterance anytime
```

---

## 🎯 Key Takeaways

### Data Flow
**User mic → Browser Web Audio API → 16-bit PCM conversion → WebSocket binary → Server → ASR/LLM/TTS → Events back via WebSocket → React state → UI update**

### Concurrency
- Frontend: Single-threaded (JavaScript event loop)
- Backend: Async/await (can handle 50+ concurrent sessions)
- WebSocket: Full-duplex (can send/receive simultaneously)

### Real-Time Streaming
- Audio frames sent as soon as captured (not batched)
- LLM tokens sent as generated (streamed response)
- TTS audio streamed back immediately
- Events pushed to client (not polled)

### Resilience
- Circuit breakers per service
- Fallback strategies when service fails
- Session auto-cleanup on disconnect
- Barge-in cancels in-flight tasks

### Observability
- Latency tracked per request
- Percentiles computed from sliding window
- All logs structured (JSON)
- Budget breaches logged and surfaced

---

This is a **production-grade architecture** designed for low-latency, conversational AI with excellent observability and fault tolerance.
