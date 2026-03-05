# Documentation Index

Welcome to the Real-Time Voice Assistant documentation! This comprehensive guide explains the entire system from architecture to code implementation.

## 📚 Documentation Files

### 1. **[ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)** - Start Here! 🎯
- System design and block diagram
- Data flow from user recording to response
- Latency budget breakdown
- Resilience patterns and session management
- Configuration priority system

**Best for:** Understanding the big picture and how components connect.

---

### 2. **[HOW_IT_WORKS.md](./HOW_IT_WORKS.md)** - User Journey 🎤
- Complete end-to-end user experience
- Step-by-step: Recording → Processing → Response
- Real-time event streaming flow
- Barge-in interrupt mechanism
- Error handling scenarios
- Complete request lifecycle with timestamps

**Best for:** Understanding what happens when a user interacts with the system.

---

### 3. **[BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md)** - Backend Overview 🏗️
- Tech stack (FastAPI, asyncio, Pydantic)
- Directory structure
- Core components explanation
- Data flow within backend
- Concurrency model
- Error handling architecture
- Telemetry pipeline
- Configuration system

**Best for:** Understanding backend systems, components, and data flow.

---

### 4. **[FRONTEND_ARCHITECTURE.md](./FRONTEND_ARCHITECTURE.md)** - Frontend Overview ⚛️
- Tech stack (React, TypeScript, Vite, Tailwind)
- Directory structure
- Component hierarchy
- Data flow in frontend
- Audio encoding pipeline
- WebSocket communication protocol
- State management pattern
- Error handling in frontend
- Performance optimizations
- Responsive design

**Best for:** Understanding frontend systems, components, and UI flows.

---

### 5. **[BACKEND_FILES.md](./BACKEND_FILES.md)** - Backend Code Details 🔍
- Line-by-line explanation of each Python file
- `config.py` - Configuration management
- `server.py` - FastAPI entry point
- `models/events.py` - Event definitions
- `models/session.py` - Session tracking
- `models/telemetry.py` - Latency records
- `services/circuit_breaker.py` - Fault tolerance
- `services/asr.py` - Speech recognition
- `services/llm.py` - Language model
- `services/tts.py` - Text-to-speech
- `pipeline/orchestrator.py` - Main pipeline coordinator
- `pipeline/session_manager.py` - Session lifecycle
- `pipeline/replay.py` - Session replay
- `telemetry/metrics.py` - Latency tracking
- `telemetry/dashboard.py` - Metrics endpoint
- `telemetry/logger.py` - Structured logging
- `mock_providers.py` - Development mocks

**Best for:** Deep-dive code understanding, file-by-file breakdown.

---

### 6. **[FRONTEND_FILES.md](./FRONTEND_FILES.md)** - Frontend Code Details 🔍
- Line-by-line explanation of each TypeScript/React file
- `main.tsx` - Vite entry point
- `types.ts` - TypeScript interfaces
- `App.tsx` - Root component and state management
- `components/StatusHeader.tsx` - Connection status
- `components/ConnectionPanel.tsx` - Server connection UI
- `components/AudioRecorder.tsx` - Audio capture and encoding
- `components/EventsDisplay.tsx` - Real-time event feed
- `components/TelemetryDashboard.tsx` - Metrics visualization
- `services/websocket.ts` - WebSocket abstraction layer
- Component tree and data flow
- Design patterns used

**Best for:** Deep-dive code understanding, React component breakdown.

---

## 🗺️ Reading Guide

### I want to understand...

**...how the entire system works** → Start with [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) then [HOW_IT_WORKS.md](./HOW_IT_WORKS.md)

**...the backend** → Read [BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md) then [BACKEND_FILES.md](./BACKEND_FILES.md)

**...the frontend** → Read [FRONTEND_ARCHITECTURE.md](./FRONTEND_ARCHITECTURE.md) then [FRONTEND_FILES.md](./FRONTEND_FILES.md)

**...a specific component** → Search for it in [BACKEND_FILES.md](./BACKEND_FILES.md) or [FRONTEND_FILES.md](./FRONTEND_FILES.md)

**...the entire request lifecycle** → Read [HOW_IT_WORKS.md](./HOW_IT_WORKS.md#-complete-request-lifecycle)

**...error handling** → Search "Error" in [HOW_IT_WORKS.md](./HOW_IT_WORKS.md) or [BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md)

---

## 🎯 Key Concepts

### Architecture Layers
```
Frontend (React + TypeScript)
    ↓ WebSocket + HTTP
Backend (FastAPI + async)
    ↓ HTTP
External Services (OpenAI, HuggingFace, etc)
```

### Request Stages
1. **Audio Capture** - Microphone → 16-bit PCM (frontend)
2. **Audio Accumulation** - Chunks buffered until end_of_utterance (backend)
3. **ASR** - Audio → Text (~250-300ms)
4. **LLM** - Text → Response (~140-150ms)
5. **TTS** - Response → Audio (~130-140ms)
6. **Telemetry** - Latency recorded and aggregated

### Key Technologies
- **Backend:** Python 3.13, FastAPI, asyncio, Pydantic
- **Frontend:** React 18, TypeScript, Web Audio API, TailwindCSS
- **Communication:** WebSocket (binary audio, JSON events)
- **Observability:** Structured logging, percentile latencies

### Design Principles
- **Real-time streaming** - Events/audio streamed, not batched
- **Resilience** - Circuit breakers, fallbacks, graceful degradation
- **Observability** - Telemetry, correlation IDs, structured logs
- **Performance** - Sub-1.2s P95 latency target
- **Developer-friendly** - Environment-based config, mock providers

---

## 📊 System Statistics

| Metric | Value |
|--------|-------|
| Backend framework | FastAPI 0.135.1 |
| Frontend framework | React 18.2.0 |
| Max concurrent sessions | 50 |
| Conversation context | 10 turns |
| Latency P95 target | 1,200ms |
| Actual P95 performance | ~575ms (2x budget) |
| Audio sample rate | 16kHz |
| Frame size | 4096 samples (~256ms) |
| Audio format | 16-bit PCM, mono |
| WebSocket path | /ws |
| Telemetry window | Last 100 requests |

---

## 🚀 Getting Started

### Run Backend
```bash
cd real-time-voice-assistant
source .venv/bin/activate
SERVER_REQUIRE_TLS=false python -m uvicorn src.server:app --host 0.0.0.0 --port 8000
```

### Run Frontend
```bash
cd client
npm run dev
# Opens http://localhost:5173
```

### Test
1. Open browser to http://localhost:5173
2. Click "Connect"
3. Click "Start Recording"
4. Speak: "Hello, how are you?"
5. Click "Stop Recording"
6. Watch real-time events appear
7. Check Telemetry tab for latencies

---

## 🔧 Configuration

### Environment Variables
```bash
# Provider selection
PROVIDER_MODE=mock|real|hybrid

# Server settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_REQUIRE_TLS=false
SERVER_WS_PATH=/ws

# API keys (for real providers)
OPENAI_API_KEY=sk-...
HUGGINGFACE_API_KEY=hf_...

# Performance targets
ASR_BUDGET_MS=500
LLM_BUDGET_MS=400
TTS_BUDGET_MS=250
```

### .env File
Create `.env` in project root:
```env
PROVIDER_MODE=mock
SERVER_REQUIRE_TLS=false
```

---

## 📝 File Summary

| Layer | File | Lines | Purpose |
|-------|------|-------|---------|
| **Backend** | config.py | ~100 | Environment config |
| | server.py | ~150 | FastAPI entry point |
| | orchestrator.py | ~400 | Main pipeline |
| | metrics.py | ~150 | Latency tracking |
| | models/*.py | ~330 | Data models |
| | services/*.py | ~300 | ASR/LLM/TTS services |
| **Frontend** | App.tsx | ~150 | Root component |
| | components/*.tsx | ~800 | React components |
| | services/websocket.ts | ~150 | WebSocket client |
| | types.ts | ~60 | TypeScript types |

---

## 🎓 Learning Path

1. **Beginner** - Read [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)
2. **Intermediate** - Read [HOW_IT_WORKS.md](./HOW_IT_WORKS.md)
3. **Advanced** - Read [BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md) + [FRONTEND_ARCHITECTURE.md](./FRONTEND_ARCHITECTURE.md)
4. **Expert** - Read [BACKEND_FILES.md](./BACKEND_FILES.md) + [FRONTEND_FILES.md](./FRONTEND_FILES.md)

---

## ❓ FAQ

**Q: What happens if a service fails?**
A: Circuit breaker opens, fallback strategy engages. See [BACKEND_ARCHITECTURE.md#resilience-features](./BACKEND_ARCHITECTURE.md#resilience-features)

**Q: Can users interrupt responses?**
A: Yes! Barge-in support cancels ongoing pipeline and starts new one. See [HOW_IT_WORKS.md#barge-in-interrupt](./HOW_IT_WORKS.md#-barge-in-interrupt)

**Q: How is latency tracked?**
A: LatencyTracker captures timestamps at stage boundaries, computes percentiles. See [BACKEND_FILES.md#13-src-telemetry-metrics-py](./BACKEND_FILES.md#13-srctele metrymetricspy---latency-measurement)

**Q: Can I use real APIs (OpenAI, etc)?**
A: Yes! Set `PROVIDER_MODE=real` and add API keys to `.env`. See [BACKEND_ARCHITECTURE.md#configuration-system](./BACKEND_ARCHITECTURE.md#configuration-system)

**Q: What's the audio format?**
A: 16-bit PCM, 16kHz sample rate, mono channel. See [FRONTEND_FILES.md#audio-encoding](./FRONTEND_FILES.md#audio-encoding-pipeline)

---

## 📞 Support

For questions about specific components:
- **Backend components:** See [BACKEND_FILES.md](./BACKEND_FILES.md)
- **Frontend components:** See [FRONTEND_FILES.md](./FRONTEND_FILES.md)
- **Data flow:** See [HOW_IT_WORKS.md](./HOW_IT_WORKS.md)
- **Architecture:** See [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)

---

**Last Updated:** March 5, 2026
**Version:** 1.0.0
**Status:** Production-Ready ✅
