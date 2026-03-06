# Backend Files - Line-by-Line Explanation

## 1. src/config.py - Configuration Management

**Purpose:** Load and store application settings from environment variables with type safety via Pydantic.

### Key Classes

#### `ServerConfig`
```python
@dataclass
class ServerConfig:
    host: str = "0.0.0.0"           # Bind address
    port: int = 8000                # Port number
    require_tls: bool = True        # Enforce HTTPS/WSS
    ws_path: str = "/ws"            # WebSocket endpoint
```
**Why:** Separates server settings from business logic. Can be overridden via env vars.

#### `ProviderConfig`
```python
@dataclass
class ProviderConfig:
    mode: str = "mock"              # Options: mock, real, hybrid
    asr_url: str = "..."            # ASR service endpoint
    llm_url: str = "..."            # LLM service endpoint
    tts_url: str = "..."            # TTS service endpoint
    api_keys: dict[str, str]        # API keys for services
    search_api_key: str = ""        # Tavily API key for web search
    enable_web_search: bool = True  # Feature flag to toggle search
```
**Why:** Allows swapping between providers (dev vs production) without code changes. Web search is toggleable via env var.

#### `TelemetryConfig`
```python
@dataclass
class TelemetryConfig:
    percentile_window_size: int = 100   # Sliding window for P50/95/99
    budget_asr_ms: int = 500            # ASR latency budget
    budget_llm_ms: int = 400            # LLM latency budget
    budget_tts_ms: int = 250            # TTS latency budget
```
**Why:** Centralizes performance targets and observability settings.

#### `AppConfig` (Main Config)
```python
@dataclass
class AppConfig:
    server: ServerConfig
    provider: ProviderConfig
    telemetry: TelemetryConfig
    max_sessions: int = 50              # Concurrent session limit
    context_window_turns: int = 10      # Conversation history depth
```

### How It Works
1. Environment variable `.env` file is loaded via `python-dotenv`
2. `_load_server_config()` function reads `SERVER_*` env vars
3. Returns in priority: env var → default
4. Pydantic validates types
5. Module-level singleton `config = AppConfig(...)` available globally

### Usage Pattern
```python
from src.config import config

print(config.server.host)           # "0.0.0.0"
print(config.provider.mode)         # "mock"
print(config.telemetry.budget_asr_ms)  # 500
```

---

## 2. src/server.py - FastAPI Entry Point

**Purpose:** HTTP/WebSocket server entry point. Accepts connections, enforces security, routes to orchestrator.

### Lifespan Context Manager
```python
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Voice assistant server starting", pipeline_stage="server")
    yield
    logger.info("Voice assistant server shutting down", pipeline_stage="server")
```
**Why:** Logs when server starts and stops. Useful for debugging.

### FastAPI App Creation
```python
def create_app() -> FastAPI:
    app = FastAPI(...)
    app.add_middleware(CORSMiddleware, ...)  # Allow cross-origin requests
    app.include_router(telemetry_router)    # Mount telemetry endpoints
    return app
```

### Health Endpoint
```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```
**Why:** Simple liveness check for load balancers/monitoring.

### WebSocket Endpoint
```python
@app.websocket(config.server.ws_path)  # Usually /ws
async def websocket_endpoint(ws: WebSocket) -> None:
    # TLS enforcement
    if config.server.require_tls and ws.url.scheme not in ("wss", "https"):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    await ws.accept()
    await handle_session(ws)  # Delegate to orchestrator
```
**Why:**
- Rejects non-TLS connections if configured
- Accepts connection
- Delegates to orchestrator for business logic

### Replay Endpoint
```python
@app.post("/replay")
async def replay_session(file_path: str, delay_multiplier: float = 1.0) -> dict:
    # Load recorded session
    # Re-run through pipeline
    # Return results
```
**Why:** Debug/test feature. Re-play past user interactions for analysis.

---

## 3. src/models/events.py - Event Definitions

**Purpose:** Define all event types and payloads that flow between server and client.

### PipelineStage Enum
```python
class PipelineStage(str, Enum):
    ORCHESTRATOR = "orchestrator"
    ASR = "asr"
    LLM = "llm"
    TTS = "tts"
    SEARCH = "search"
    TELEMETRY = "telemetry"
```
**Why:** Log tag to identify which component generated the event. Includes `SEARCH` stage for web search events.

### Base Event
```python
@dataclass
class BaseEvent(BaseModel):
    correlation_id: str              # UUID linking all events in one request
    timestamp: str                   # ISO 8601 timestamp
    schema_version: str = "1.0.0"    # For versioning compatibility
```

### Event Types
```python
class SpeechStartedEvent(BaseEvent):
    event_type: str = "speech_started"
    payload: SpeechStartedPayload

class TranscriptionFinalEvent(BaseEvent):
    event_type: str = "transcription_final"
    payload: TranscriptionPayload

class LLMTokenEvent(BaseEvent):
    event_type: str = "llm_token"
    payload: LLMTokenPayload

class TTSAudioChunkEvent(BaseEvent):
    event_type: str = "tts_audio_chunk"
    payload: TTSAudioChunkPayload

class IntentDetectedEvent(BaseEvent):
    event_type: str = "intent_detected"
    payload: IntentDetectedPayload  # intent, query, requires_search

class WebSearchResultEvent(BaseEvent):
    event_type: str = "web_search_result"
    payload: WebSearchResultPayload  # query, results_summary, source_count

class ErrorEvent(BaseEvent):
    event_type: str = "error"
    payload: ErrorPayload
```

**Why:** Type-safe event schemas. Easy serialization to JSON.

---

## 4. src/models/session.py - Session & Conversation

**Purpose:** Track conversation history and session metadata.

### ConversationTurn
```python
@dataclass
class ConversationTurn:
    user_text: str              # "Hello, how are you?"
    assistant_text: str         # "I'm doing great!"
    timestamp: str              # When turn occurred
```

### Session
```python
@dataclass
class Session:
    session_id: str             # UUID
    created_at: str             # ISO 8601
    turns: list[ConversationTurn] = field(default_factory=list)
    
    def add_turn(self, user_text: str, assistant_text: str) -> None:
        """Add new conversation turn to history."""
        self.turns.append(ConversationTurn(...))
    
    def get_context(self, max_turns: int = 10) -> str:
        """Extract last N turns for LLM context."""
        # Format as: "User: ...\nAssistant: ...\n..."
```

**Why:**
- Session persistence across multiple user utterances
- LLM gets last 10 turns for coherent conversation
- Tracks session lifetime for cleanup

---

## 5. src/models/telemetry.py - Latency Records

**Purpose:** Define latency measurement data structure.

### LatencyRecord
```python
@dataclass
class LatencyRecord:
    correlation_id: str
    asr_ms: float               # ASR stage latency
    llm_ttft_ms: float          # LLM time-to-first-token
    tts_ttfb_ms: float          # TTS time-to-first-byte
    orchestration_overhead_ms: float
    
    @property
    def total_e2e_ms(self) -> float:
        """End-to-end latency in ms."""
        return self.asr_ms + self.llm_ttft_ms + self.tts_ttfb_ms + self.orchestration_overhead_ms
    
    @property
    def budget_breached(self) -> bool:
        """Check if any stage exceeded budget."""
        return (
            self.asr_ms > config.telemetry.budget_asr_ms or
            self.llm_ttft_ms > config.telemetry.budget_llm_ms or
            self.tts_ttfb_ms > config.telemetry.budget_tts_ms
        )
    
    @property
    def stage_breaches(self) -> dict:
        """Which stages exceeded budget."""
        return {
            "asr": self.asr_ms > config.telemetry.budget_asr_ms,
            "llm": self.llm_ttft_ms > config.telemetry.budget_llm_ms,
            "tts": self.tts_ttfb_ms > config.telemetry.budget_tts_ms,
        }
```

**Why:** Encapsulates latency measurement logic. Properties auto-compute derived fields.

---

## 6. src/services/circuit_breaker.py - Fault Tolerance

**Purpose:** Prevent cascading failures by tracking service health.

### CircuitBreaker Class
```python
class CircuitBreaker:
    def __init__(self, service_name: str, failure_threshold: int = 3, timeout_seconds: int = 30):
        self.service_name = service_name
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
```

### State Machine
```
CLOSED (healthy)
    ↓
Call service successfully → stay CLOSED
Error occurs → increment failure_count
    ↓
OPEN (failing)
    ↓
Timeout expires (30 sec) → HALF_OPEN
    ↓
HALF_OPEN (recovery attempt)
    ↓
Try call → success = reset to CLOSED
        → fail = back to OPEN
```

### Usage
```python
async def _run_asr(...):
    async with _asr_cb:  # Context manager
        return await asr_service.transcribe(audio)
    # If fails 3 times → circuit opens
    # Subsequent calls instantly raise without trying
```

**Why:** Protects backend from hammering failing services. Auto-recovery via half-open state.

---

## 7. src/services/asr.py - Speech Recognition

**Purpose:** Convert audio to text.

### ASR Service
```python
class ASRService:
    async def transcribe(self, audio_bytes: bytes) -> str:
        """
        Convert audio bytes to text.
        
        Args:
            audio_bytes: 16-bit PCM audio data
        
        Returns:
            Transcribed text
        """
        if config.provider.mode == "mock":
            return await mock_provider.asr_transcribe(audio_bytes)
        else:
            return await openai_whisper.transcribe(audio_bytes)
```

**Why:** Abstraction layer. Can swap providers without changing orchestrator.

---

## 8. src/services/llm.py - Language Model

**Purpose:** Generate conversational responses with intent detection via OpenAI function calling.

### Key Components

#### `ToolCallRequest` dataclass
```python
@dataclass
class ToolCallRequest:
    name: str        # "web_search" or "factual_lookup"
    arguments: dict  # {"query": "..."}
    tool_call_id: str
```

#### `ToolCallRequested` exception
Raised when the LLM streams a tool call instead of text. The orchestrator catches this and dispatches web search.

#### `generate_response_stream()` (LLM Call #1 — Intent)
```python
async def generate_response_stream(
    user_text, context, *, correlation_id, tools=None
) -> AsyncIterator[LLMTokenEvent]:
    # Model: gpt-4o-mini, temperature: 0.7
    # If tools provided: LLM can invoke web_search or factual_lookup
    # Monitors streaming SSE for tool_calls in delta responses
    # Raises ToolCallRequested if LLM wants a tool
    # Otherwise yields LLMTokenEvent for each text token
```

#### `generate_response_with_tool_result()` (LLM Call #2 — Answer)
```python
async def generate_response_with_tool_result(
    messages, *, correlation_id
) -> AsyncIterator[LLMTokenEvent]:
    # Model: gpt-4o (better instruction following)
    # Temperature: 0 (deterministic, no hallucination)
    # No tools passed — always produces text
    # Used after search results are injected into messages
```

**Why:** Dual-model architecture ensures fast intent detection (GPT-4o-mini) and accurate factual responses (GPT-4o with temp=0).

---

## 8a. src/services/search.py - Web Search (NEW)

**Purpose:** Execute real-time web searches via Tavily API.

### `web_search()` function
```python
async def web_search(
    query: str,
    *,
    search_depth: str = "advanced",  # "basic" or "advanced"
    max_results: int = 5,
    correlation_id: str,
) -> str:
    # Calls Tavily API: https://api.tavily.com/search
    # Returns formatted string with:
    #   - AI-generated quick answer
    #   - Numbered search results (title, content, URL)
    # Returns empty string on failure (graceful degradation)
```

### `_format_search_results()` helper
```python
def _format_search_results(data: dict, query: str) -> str:
    # Formats Tavily response into LLM-consumable context:
    # "Quick Answer: Nifty 50 is at 24,450.45"
    # "1. Economic Times\n   Content...\n   Source: https://..."
    # Truncates content to 300 chars per result
```

**Why:** Clean adapter pattern. Tavily provides structured results + AI answer. Graceful error handling returns empty string so pipeline continues.

---

## 8b. src/services/tools.py - Tool Definitions (NEW)

**Purpose:** Define OpenAI function calling tools available to the LLM.

### Tool Definitions
```python
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the internet for real-time information...",
        "parameters": {
            "properties": {
                "query": {"type": "string"},
                "search_type": {"type": "string", "enum": ["general", "news"]}
            },
            "required": ["query"]
        }
    }
}

FACTUAL_LOOKUP_TOOL = {
    "type": "function",
    "function": {
        "name": "factual_lookup",
        "description": "Verify a specific factual claim...",
        "parameters": { ... }
    }
}

AVAILABLE_TOOLS = [WEB_SEARCH_TOOL, FACTUAL_LOOKUP_TOOL]
TOOL_REGISTRY = {t["function"]["name"]: t for t in AVAILABLE_TOOLS}
```

**Why:** Centralized tool definitions. LLM uses these schemas to decide when to call tools. The orchestrator uses `TOOL_REGISTRY` for quick lookup.

---

## 9. src/services/tts.py - Text-to-Speech

**Purpose:** Convert text response back to audio.

### TTS Service
```python
class TTSService:
    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Stream audio bytes for given text.
        
        Args:
            text: Response text to synthesize
        
        Yields:
            Audio chunks (PCM bytes) as generated
        """
        if config.provider.mode == "mock":
            async for chunk in mock_provider.tts_stream(text):
                yield chunk
        else:
            async for chunk in huggingface_tts.stream(text):
                yield chunk
```

**Why:** Streams audio chunks back to client in real-time.

---

## 10. src/pipeline/session_manager.py - Session Lifecycle

**Purpose:** Track active sessions, manage cleanup.

### SessionManager
```python
class SessionManager:
    def __init__(self, max_sessions: int = 50):
        self._sessions: dict[str, Session] = {}
        self._max_sessions = max_sessions
    
    async def create_session(self) -> Session:
        """Create new session, check max limit."""
        if len(self._sessions) >= self._max_sessions:
            raise RuntimeError("Max concurrent sessions reached")
        
        session = Session(session_id=uuid4())
        self._sessions[session.session_id] = session
        return session
    
    async def close_session(self, session_id: str) -> None:
        """Clean up session on disconnect."""
        del self._sessions[session_id]
    
    async def touch_session(self, session_id: str) -> None:
        """Update session last-activity timestamp."""
        self._sessions[session_id].last_activity = time.time()
```

**Why:** Manages session lifecycle. Cleanup on disconnect. Prevents resource leaks.

---

## 11. src/pipeline/orchestrator.py - Main Pipeline Coordinator

**Purpose:** The heart of the system. Orchestrates ASR → LLM (Intent) → [Web Search] → LLM (Answer) → TTS, tracks latency, emits events.

### validate_audio_frame()
```python
def validate_audio_frame(data: bytes) -> str | None:
    """Check if data is valid 16-bit PCM.
    
    Returns error message if invalid, None if valid.
    """
    if not data:
        return "Empty audio frame"
    if len(data) % 2 != 0:
        return "Audio frame length is not a multiple of 2"
    try:
        struct.unpack_from("<h", data, 0)  # Try unpacking first 16 bits
    except struct.error:
        return "Unable to decode audio as 16-bit little-endian PCM"
    return None
```

**Why:** Rejects malformed audio early. 16-bit PCM requires even byte count.

### handle_session()
```python
async def handle_session(ws: WebSocket) -> None:
    """Top-level handler for one WebSocket session."""
    session = await session_manager.create_session()
    
    try:
        await _session_loop(ws, session)
    except WebSocketDisconnect:
        logger.info("Client disconnected", session_id=session.session_id)
    finally:
        await session_manager.close_session(session.session_id)
```

**Why:** Main entry point from server.py. Wraps session lifecycle.

### _session_loop()
```python
async def _session_loop(ws: WebSocket, session: Session) -> None:
    """Receive utterances until disconnect."""
    active_task = None
    
    while True:
        audio_chunks = []
        correlation_id = _new_correlation_id()
        
        # Phase 1: Accumulate audio frames
        while True:
            message = await ws.receive()
            
            # Check for end_of_utterance signal
            if "text" in message:
                ctrl = json.loads(message["text"])
                if ctrl.get("action") == "end_of_utterance":
                    break  # Exit inner loop, process pipeline
            
            # Binary audio frame
            data = message.get("bytes", b"")
            if not data:
                continue
            
            # Barge-in: cancel ongoing response if new audio arrives
            if active_task and not active_task.done():
                active_task.cancel()
            
            # Validate & append
            err = validate_audio_frame(data)
            if err:
                await ws.send_json(ErrorEvent(...).model_dump())
                continue
            
            audio_chunks.append(data)
        
        # Phase 2: Run pipeline
        if audio_chunks:
            speech_event = SpeechStartedEvent(...)
            await ws.send_json(speech_event.model_dump())
            
            active_task = asyncio.create_task(
                _run_pipeline(ws, session, audio_chunks, correlation_id)
            )
            
            try:
                await active_task
            except asyncio.CancelledError:
                logger.info("Pipeline cancelled (barge-in)")
            
            active_task = None
```

**Why:** Accumulates audio, detects end-of-utterance, supports barge-in via task cancellation.

### _run_pipeline()
```python
async def _run_pipeline(ws, session, audio_chunks, correlation_id):
    """Execute ASR → LLM (Intent) → [Search] → LLM (Answer) → TTS."""
    tracker = LatencyTracker(correlation_id)
    
    # ASR
    tracker.start("asr")
    final_text = await _run_asr(ws, audio_chunks, correlation_id)
    tracker.stop("asr")
    
    if not final_text:
        return
    
    # LLM (with intent detection + optional web search)
    tracker.start("llm")
    llm_text = await _run_llm(ws, session, final_text, correlation_id)
    # _run_llm now internally handles:
    #   - Passing tool definitions (web_search, factual_lookup)
    #   - Catching ToolCallRequested exceptions
    #   - Delegating to _handle_tool_call() for search
    #   - Returning final response text
    tracker.stop("llm")
    
    if not llm_text:
        return
    
    # TTS
    tracker.start("tts")
    await _run_tts(ws, llm_text, correlation_id)
    tracker.stop("tts")
    
    # Update history + telemetry
    session.add_turn(user_text=final_text, assistant_text=llm_text)
    record = tracker.to_record()
    aggregator.add(record)
```

### _handle_tool_call() (NEW)
```python
async def _handle_tool_call(ws, session, tool_call, user_text, context, correlation_id):
    """Execute a tool call requested by the LLM."""
    # 1. Emit IntentDetectedEvent to frontend
    # 2. Execute Tavily web search (via circuit breaker _search_cb)
    # 3. Emit WebSearchResultEvent to frontend
    # 4. Build messages with strict system prompt:
    #    "Your ONLY job is to speak the exact data from the search results.
    #     Quote ALL numbers EXACTLY as they appear."
    # 5. Call generate_response_with_tool_result() (GPT-4o, temp=0)
    # 6. Stream response tokens back to client
    # 7. Return accumulated response text
```

**Why:** Main pipeline logic. Tracks every stage. Emits events. Records telemetry.

---

## 12. src/pipeline/replay.py - Session Replay

**Purpose:** Record and replay user interactions for debugging/testing.

### RecordedSession
```python
@dataclass
class RecordedSession:
    session_id: str
    events: list[dict]      # All events from session
    audio_chunks: list[bytes]  # All audio frames
    
    def to_json(self) -> str:
        """Serialize to JSON for storage."""
        return json.dumps({
            "session_id": self.session_id,
            "events": self.events,
            "audio_chunks": [base64.b64encode(chunk).decode() for chunk in self.audio_chunks]
        })
```

### ReplayEngine
```python
class ReplayEngine:
    async def replay(self) -> list[dict]:
        """Re-run recorded session through pipeline."""
        # Recreate WebSocket simulation
        # Feed audio chunks
        # Capture output events
        # Return results
```

**Why:** Debug tool. Save problematic sessions for analysis/replay.

---

## 13. src/telemetry/metrics.py - Latency Measurement

**Purpose:** Track per-request latencies, compute percentiles.

### LatencyTracker
```python
class LatencyTracker:
    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self._starts = {}
        self._durations = {}
        self._overall_start = time.monotonic()
    
    def start(self, stage: str):
        self._starts[stage] = time.monotonic()
    
    def stop(self, stage: str):
        if stage in self._starts:
            self._durations[stage] = (time.monotonic() - self._starts[stage]) * 1000  # ms
    
    def to_record(self) -> LatencyRecord:
        """Compute total, check budgets."""
        total = (time.monotonic() - self._overall_start) * 1000
        
        return LatencyRecord(
            correlation_id=self.correlation_id,
            asr_ms=self._durations.get("asr", 0),
            llm_ttft_ms=self._durations.get("llm", 0),
            tts_ttfb_ms=self._durations.get("tts", 0),
            orchestration_overhead_ms=max(0, total - sum(self._durations.values()))
        )
```

**Why:** Measures each stage. Computes overhead. Detects budget breaches.

### PercentileAggregator
```python
class PercentileAggregator:
    def __init__(self, window_size: int = 100):
        self._records = deque(maxlen=window_size)  # Keep last 100
    
    def add(self, record: LatencyRecord):
        self._records.append(record)  # Old records auto-drop
    
    def get_percentiles(self) -> dict:
        """Compute P50, P95, P99 for each field."""
        # For each field (asr_ms, llm_ttft_ms, tts_ttfb_ms, total_e2e_ms):
        #   Sort all values
        #   Interpolate at p=50, p=95, p=99
        return {
            "total_e2e": {"p50": 530, "p95": 575, "p99": 578},
            "asr": {"p50": 245, "p95": 298, "p99": 301},
            ...
        }

    def percentile(self, values: list[float], p: float) -> float:
        """Linear interpolation percentile."""
        if not values:
            return 0
        k = (p / 100) * (len(values) - 1)
        f = int(k)
        c = f + 1 if f + 1 < len(values) else f
        d = k - f
        return values[f] + d * (values[c] - values[f])
```

**Why:** Sliding window percentile computation. Efficient: O(n log n) on each get_percentiles() call.

---

## 14. src/telemetry/dashboard.py - Metrics HTTP Endpoint

**Purpose:** Expose `/telemetry/latency` HTTP endpoint for frontend polling.

### latency_dashboard()
```python
@router.get("/latency")
async def latency_dashboard() -> dict:
    """Return current percentiles."""
    percentiles = aggregator.get_percentiles()
    return {
        "sample_count": aggregator.count,
        "percentiles": {
            name: {"p50": sp.p50, "p95": sp.p95, "p99": sp.p99}
            for name, sp in percentiles.items()
        }
    }
```

**Why:** Simple JSON endpoint. Frontend polls every 2 seconds to update dashboard.

---

## 15. src/telemetry/logger.py - Structured Logging

**Purpose:** Emit structured (JSON) logs for observability.

### StructuredLogger
```python
class StructuredLogger:
    def info(self, message: str, **kwargs):
        """Log info with structured data."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "logger": "pipeline",
            "message": message,
            **kwargs  # correlation_id, session_id, pipeline_stage, etc.
        }
        print(json.dumps(log_entry))
```

**Why:** JSON logs are machine-parseable. Easy for log aggregation (ELK, DataDog, etc.).

---

## 16. src/mock_providers.py - Development Providers

**Purpose:** Mock ASR/LLM/TTS for dev/testing without API keys.

### Mock ASR
```python
async def asr_transcribe(audio_bytes: bytes) -> str:
    """Simulate ASR with delay."""
    await asyncio.sleep(0.250)  # Simulate 250ms latency
    return "hello how are you"  # Fixed response
```

### Mock LLM
```python
async def llm_generate(prompt: str) -> str:
    """Simulate LLM with delay."""
    await asyncio.sleep(0.150)  # Simulate 150ms latency
    return "I'm doing great! How can I help?"
```

### Mock TTS
```python
async def tts_stream(text: str) -> AsyncGenerator[bytes, None]:
    """Yield synthetic audio chunks."""
    for i in range(5):  # 5 chunks
        await asyncio.sleep(0.025)
        yield b"\x00\x01" * 512  # 1KB of silence
```

### Mock Search (NEW)
```python
@app.post("/search/query")
async def mock_search(request: dict):
    """Return mock Tavily-like search results."""
    return {
        "answer": "Mock search answer for: " + request.get("query", ""),
        "results": [{"title": "Mock Result", "content": "...", "url": "https://example.com"}]
    }
```

**Why:** Test full pipeline without API costs/keys. Search mock enables testing the intent detection flow.

---

## Summary Table

| File | Lines | Purpose |
|------|-------|---------|
| config.py | ~100 | Environment configuration |
| server.py | ~150 | FastAPI entry point |
| events.py | ~200 | Event type definitions (incl. IntentDetected, WebSearchResult) |
| session.py | ~80 | Conversation tracking |
| telemetry.py | ~50 | Latency record model |
| circuit_breaker.py | ~120 | Fault tolerance |
| asr.py | ~80 | Speech recognition |
| llm.py | ~330 | Language generation (dual-model: intent + answer) |
| tts.py | ~100 | Text-to-speech |
| **search.py** | **~140** | **Web search (Tavily API) — NEW** |
| **tools.py** | **~75** | **OpenAI function calling tool definitions — NEW** |
| session_manager.py | ~100 | Session lifecycle |
| orchestrator.py | ~500 | **Main pipeline** (incl. _handle_tool_call) |
| replay.py | ~200 | Session replay |
| metrics.py | ~150 | Latency tracking |
| dashboard.py | ~50 | Metrics endpoint |
| logger.py | ~100 | Structured logging |
| mock_providers.py | ~200 | Development mocks (incl. search) |

---

**Next:** [Frontend Files](./FRONTEND_FILES.md) - Frontend component breakdown
