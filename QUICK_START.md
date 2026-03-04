# Quick Start Guide — Full Application Testing

Complete instructions to run the entire real-time voice assistant system with the test client.

## Architecture

```
Browser (React + Vite)
    ↓ WebSocket (ws://localhost:8000/ws)
    ↑ JSON events + audio playback
    
FastAPI Server (localhost:8000)
    ├── /health                      (health check)
    ├── /ws                          (WebSocket endpoint)
    ├── /telemetry/latency          (metrics)
    └── /replay                      (session replay)

Mock Providers OR Real Providers (localhost:9000 or cloud APIs)
    ├── ASR (Speech Recognition)
    ├── LLM (Language Model)
    └── TTS (Text-to-Speech)
```

## Step-by-Step Setup

### Terminal 1: Backend (Mock Providers + Main App)

```bash
cd /path/to/real-time-voice-assistant

# Ensure in correct env
source .venv/bin/activate

# Start both services (one command)
python run_local_mock.py

# Output should show:
# 🚀 Starting Real-Time Voice Assistant with Mock Providers
# ============================================
#    Provider Mode: mock
#    Mock Services: http://localhost:9000
#    Main App: http://localhost:8000
#    WebSocket: ws://localhost:8000/ws
```

This starts:
- ✅ Mock ASR on `:9000/asr/stream`
- ✅ Mock LLM on `:9000/llm/stream`
- ✅ Mock TTS on `:9000/tts/stream`
- ✅ Main FastAPI server on `:8000`

### Terminal 2: Frontend (React + Vite)

```bash
cd /path/to/real-time-voice-assistant/client

# Install dependencies (one-time)
npm install

# Start dev server
npm run dev

# Output should show:
#   VITE v5.x.x  ready in XXX ms
#   ➜  Local:   http://localhost:5173/
#   ➜  press h to show help
```

Open browser: **http://localhost:5173**

---

## Testing Workflow

### 1. **Verify Connection**
- [ ] Green status indicator ("✓ Connected")
- [ ] Test connection: `curl http://localhost:8000/health` → `{"status": "ok"}`

### 2. **Record Audio**
- [ ] Click "🎤 Start Recording"
- [ ] Speak into microphone (1-2 seconds)
- [ ] Click "⏹ Stop Recording"
- [ ] Check that audio bytes are being sent

### 3. **Monitor Events in Real-Time**
- [ ] "Transcript & Events" tab shows incoming events:
  - 🔊 `speech_started`
  - 📝 `transcription_provisional` (interim)
  - ✅ `transcription_final` (complete)
  - 🤖 `llm_token` (GPT response tokens)
  - 🔊 `tts_audio_chunk` (audio for playback)

### 4. **Check Latency Metrics**
- [ ] Click "Telemetry" tab
- [ ] P50 (median) latency should be < 1200ms
- [ ] P95 and P99 shown with color indicators
- [ ] Green = good, Amber = okay, Red = slow

### 5. **Test Barge-in** (Advanced)
- [ ] Start recording utterance 1
- [ ] While processing, start recording utterance 2
- [ ] Server should cancel utterance 1 and process utterance 2
- [ ] Events show cancellation, new transcription begins

### 6. **Test Fallbacks** (Simulate Failure)
- Optional: Stop mock provider to trigger circuit breaker
- Client should show `error` events with fallback bridge audio

---

## What Each Component Tests

### Client App Tests

| Component | Tests | Coverage |
|-----------|-------|----------|
| **StatusHeader** | Connection indicator | Connection state |
| **ConnectionPanel** | Connect/Disconnect | WebSocket lifecycle |
| **AudioRecorder** | Microphone access | Audio input capture |
| **EventsDisplay** | Event rendering | Pipeline events |
| **TelemetryDashboard** | Latency metrics | Performance monitoring |

### Backend Features

| Feature | How to Test | Expected Behavior |
|---------|------------|-------------------|
| **Streaming ASR** | Start recording | Provisional + final transcriptions flow |
| **LLM Tokens** | Watch event stream | Token-by-token response |
| **TTS Audio** | Monitor chunks | Audio payload in base64 |
| **Circuit Breaker** | (Stop mock provider) | Error event + fallback audio |
| **Barge-in** | Record while processing | New audio cancels old |
| **Session Context** | Multi-turn | 10-turn context maintained |
| **Telemetry** | Monitor latencies | P50/P95/P99 updated |

---

## Troubleshooting

### WebSocket Connection Failed

**Problem:** Can't connect to server
```
backend: Check Backend Server is Running:
  curl http://localhost:8000/health
  
Fix: Restart backend with: python run_local_mock.py
```

### No Microphone Access

**Problem:** Browser won't grant microphone permission
```
Solution:
  1. Check browser permissions (camera/mic settings)
  2. Ensure http:// or https:// (not file://)
  3. Try incognito mode
  4. Check OS microphone privacy settings
```

### Events Not Appearing

**Problem:** Events list stays empty after recording
```
Check:
  1. Click "Connect" first
  2. Verify recording timer increments
  3. Check browser DevTools console for errors
  4. Verify mock providers running: curl http://localhost:9000/health
```

### Telemetry Shows Zero

**Problem:** All metrics are 0
```
Note: Telemetry updates every 2 seconds
Solution:
  1. Generate some events by recording
  2. Wait 2 seconds for metrics to update
  3. Verify endpoint: curl http://localhost:8000/telemetry/latency
```

### Build Errors

**Problem:** TypeScript compilation fails
```
Solution:
  rm -rf node_modules dist
  npm install
  npm run build
```

---

## Advanced Testing

### Test with Real Providers (When You Have API Keys)

1. **Update server .env**:
```bash
PROVIDER_MODE=real
ASR_PROVIDER_URL=https://api.openai.com/v1/audio/transcriptions
ASR_API_KEY=sk-...
LLM_PROVIDER_URL=https://api.openai.com/v1/chat/completions
LLM_API_KEY=sk-...
TTS_PROVIDER_URL=https://api.openai.com/v1/audio/speech
TTS_API_KEY=sk-...
```

2. **Restart backend**:
```bash
# Kill previous process (Ctrl+C)
python run_local_mock.py
# Or just uvicorn if real providers are on separate machines
```

3. **Client auto-reconnects** and uses new provider URLs

### Session Replay (Debugging)

Test recorded session playback:
```bash
curl http://localhost:8000/replay \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_session.json
```

---

## Performance Benchmarks (Expected)

Running on mock providers:

| Metric | Expected Range |
|--------|-----------------|
| P50 (Median) | 100-300 ms |
| P95 | 300-800 ms |
| P99 | 500-1200 ms |
| Events/sec | 10-20 |
| Session limit | 50 concurrent |

---

## Common Commands Reference

```bash
# Start backend
cd real-time-voice-assistant
source .venv/bin/activate
python run_local_mock.py

# Start frontend
cd real-time-voice-assistant/client
npm run dev

# Test health
curl http://localhost:8000/health

# Test metrics
curl http://localhost:8000/telemetry/latency

# Build client
cd client
npm run build

# Run in production mode
npm run preview
```

---

## Next Steps

1. ✅ **Test End-to-End**: Complete all testing workflow steps
2. ✅ **Verify All Features**: Check off every feature in the test matrix
3. 📊 **Collect Metrics**: Record P50/P95/P99 latencies
4. 🔌 **Integrate Real Providers**: Swap mock for real APIs
5. 📦 **Deploy**: Use production build for deployment

---

## Need Help?

- Check browser **DevTools Console** for client-side errors
- Check **server logs** in terminal for backend errors
- Verify **network tab** in DevTools to see WebSocket messages
- Read **client/README.md** for app-specific docs
- Read **README.md** in root for server-specific docs

Happy testing! 🎉
