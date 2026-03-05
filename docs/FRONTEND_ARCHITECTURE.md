# Frontend Architecture - Detailed Explanation

## Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| UI Framework | React | 18.2.0 | Component-based UI |
| Language | TypeScript | 5.3.3 | Type-safe JavaScript |
| Build Tool | Vite | 5.2.0 | Lightning-fast dev/build |
| Styling | Tailwind CSS | 3.4.1 | Utility-first CSS |
| Node Runtime | Node.js | 20+ | JavaScript runtime |
| Audio API | Web Audio API | Native | Real-time audio capture |
| Networking | WebSocket | Native | Bidirectional streaming |

## Directory Structure

```
client/
├── src/
│   ├── App.tsx                          # Root component
│   ├── main.tsx                         # Vite entry point
│   ├── index.css                        # Global styles
│   ├── types.ts                         # TypeScript interfaces
│   │
│   ├── components/                      # React components
│   │   ├── StatusHeader.tsx             # Connection status bar
│   │   ├── ConnectionPanel.tsx          # Server connection button
│   │   ├── AudioRecorder.tsx            # Mic recording UI
│   │   ├── EventsDisplay.tsx            # Real-time event feed
│   │   └── TelemetryDashboard.tsx       # Latency metrics display
│   │
│   ├── services/                        # Business logic
│   │   └── websocket.ts                 # WebSocket client class
│   │
│   └── types.ts                         # Shared TypeScript types
│
├── dist/                                # Production build output
├── index.html                           # HTML template
├── vite.config.ts                       # Vite configuration
├── tsconfig.json                        # TypeScript config
├── tailwind.config.js                   # Tailwind CSS config
└── package.json                         # Dependencies & scripts
```

## Component Architecture

```
App (State Manager)
 │
 ├─→ State: isConnected, events[], metrics
 ├─→ Effects: Connect WebSocket, Poll telemetry
 │
 ├─ StatusHeader
 │   └─ Shows connection icon + latency
 │
 └─ Main Grid
    ├─ Left Column (Controls)
    │  ├─ ConnectionPanel
    │  │  └─ Connect button
    │  │
    │  └─ AudioRecorder
    │     ├─ Start/Stop recording
    │     └─ Timer display
    │
    └─ Right Column (Display)
       ├─ Tabs: "Transcript & Events" | "Telemetry"
       │
       ├─ EventsDisplay
       │  ├─ Shows all pipeline events
       │  ├─ Color-coded by type
       │  └─ Auto-appends new events
       │
       └─ TelemetryDashboard
          ├─ P50/P95/P99 latency cards
          ├─ Progress bars
          └─ Budget breakdown table
```

## Data Flow

### 1. Initialization
```
App mounted
    ↓
useState for connection, events, metrics
    ↓
useEffect[]: Create WebSocketClient
    ├─ Connect to ws://localhost:8000/ws
    ├─ onConnect: setIsConnected(true), clear events
    ├─ onMessage: append event to events[]
    ├─ onDisconnect: setIsConnected(false)
    └─ onError: emit error event
    ↓
useEffect[]: Polling loop
    ├─ Every 2000ms: fetch('/telemetry/latency')
    ├─ Parse response
    ├─ Transform percentiles
    └─ setMetrics(transformed)
```

### 2. Audio Recording Flow
```
User clicks "Start Recording"
    ↓
AudioRecorder.startRecording()
    ├─ getUserMedia() → microphone access
    ├─ Create AudioContext
    ├─ Create MediaStreamSource
    ├─ Create ScriptProcessorNode (4096 samples)
    └─ Set onaudioprocess handler
    ↓
Audio captured at 16kHz (every ~256ms)
    ↓
onaudioprocess event
    ├─ Read channel data [Float32Array]
    ├─ Convert to Int16Array (16-bit signed)
    ├─ Wrap as Uint8Array (binary)
    └─ ws.sendAudio(pcmData)
    ↓
WebSocket sends binary frame
    ↓
User clicks "Stop Recording"
    ↓
AudioRecorder.stopRecording()
    ├─ Disconnect processor
    ├─ Close audio context
    ├─ Stop media stream
    └─ ws.sendControl('end_of_utterance')
```

### 3. Event Reception & Display
```
Server emits event (JSON over WebSocket)
    ↓
WebSocketClient.onmessage
    ├─ Parse JSON
    └─ config.onMessage(data)
    ↓
App.onMessage handler
    ├─ setEvents(prev => [event, ...prev].slice(0, 100))
    └─ Keep last 100 events
    ↓
EventsDisplay re-renders
    ├─ Map events to colored cards
    ├─ Extract text from payload
    ├─ Show emoji + timestamp
    └─ Fade-in animation
```

### 4. Telemetry Polling
```
useEffect polling interval
    ↓
fetch('http://localhost:8000/telemetry/latency')
    ↓
Backend response:
{
  sample_count: 10,
  percentiles: {
    total_e2e: {p50, p95, p99},
    asr: {p50, p95, p99},
    llm_ttft: {p50, p95, p99},
    tts_ttfb: {p50, p95, p99}
  }
}
    ↓
Transform & round to 5 decimals
    ↓
setMetrics({p50_ms, p95_ms, p99_ms})
    ↓
TelemetryDashboard re-renders with new values
```

## Component Details

### App.tsx (Root)
**Purpose:** Central state management hub
- Maintains: `isConnected`, `events[]`, `metrics`
- Creates WebSocket client on mount
- Passes ws to children
- Polls telemetry every 2 seconds
- Renders layout with tabs

### StatusHeader.tsx
**Purpose:** Top bar showing connection status
- Green/red icon based on connection state
- Shows "Connected" or "Disconnected"
- Can show latency badge

### ConnectionPanel.tsx
**Purpose:** Server connection UI
- Connect button
- Disable when already connected
- Shows server URL
- Try blocks on click

### AudioRecorder.tsx
**Purpose:** Microphone recording interface
- "Start Recording" button
- Real-time timer display
- PCM audio encoding logic
- End-of-utterance signal on stop
- Inline JSDoc logging for debugging

### EventsDisplay.tsx
**Purpose:** Real-time event feed
- Maps `events[]` array
- Color-codes by event type
- Extracts text from payload
- Shows correlation_id
- Scrollable with fade-in animation
- Empty state message

### TelemetryDashboard.tsx
**Purpose:** Performance metrics visualization
- MetricCard component (reusable)
- Shows P50, P95, P99
- Progress bars with color gradient
- Target comparison
- Latency budget breakdown table
- System status checklist

## Audio Encoding Pipeline

```
Microphone Audio Signal (analog)
    ↓
AudioContext sample rate conversion: 48kHz → 16kHz
    ↓
MediaStreamSource (from getUserMedia)
    ↓
ScriptProcessorNode buffer (4096 samples @ 16kHz)
    ↓
onaudioprocess event fired
    ↓
event.inputBuffer.getChannelData(0) → Float32Array
    ├─ Range: -1.0 to +1.0 (floating point)
    ├─ Length: 4096 samples
    └─ Each sample: 32-bit float
    ↓
floatTo16BitPCM() conversion:
    ├─ For each sample:
    │  ├─ Clamp to [-1, 1]
    │  ├─ Scale: s < 0 ? s * 0x8000 : s * 0x7fff
    │  └─ Result: 16-bit signed integer (-32768 to +32767)
    │
    ├─ Create Int16Array (4096 elements)
    ├─ Create Uint8Array view (8192 bytes)
    ├─ Verify even byte count
    └─ Return Uint8Array
    ↓
Uint8Array (binary data) 8192 bytes
    ↓
WebSocket.send(pcmData)
```

## WebSocket Communication Protocol

### Client → Server (Binary)
```
1. Audio frames (Uint8Array)
   - Content: 16-bit PCM samples
   - Frequency: Every ~256ms while recording
   - Size: 8192 bytes per frame

2. Control messages (JSON string)
   {
     "action": "end_of_utterance"
   }
   or
   {
     "action": "close"
   }
```

### Server → Client (JSON)
```
Event payload (JSON string):
{
  "event_type": "speech_started" | "transcription_final" | "llm_token" | ...,
  "correlation_id": "uuid-style-string",
  "timestamp": "2026-03-05T12:34:56.789Z",
  "schema_version": "1.0.0",
  "payload": {
    // Event-specific data
    text?: "hello how are you",
    token?: "Hello,",
    session_id?: "session-uuid"
  }
}
```

## State Management Pattern

```
App component
├─ State: ws, isConnected, events[], metrics
│
├─ Effect 1: Initialize WebSocket
│  ├─ Create client
│  ├─ Set callbacks
│  ├─ Connect
│  └─ Cleanup on unmount
│
├─ Effect 2: Poll telemetry
│  ├─ Fetch metrics every 2s
│  ├─ Transform data
│  ├─ Update state
│  └─ Cleanup interval
│
└─ Render
   ├─ Pass ws to children (props drilling)
   ├─ Pass events to EventsDisplay
   ├─ Pass metrics to TelemetryDashboard
   └─ Show/hide components based on isConnected
```

**Note:** No Redux/Context API needed—simple prop drilling works fine for this app.

## Error Handling

### Connection Errors
```
WebSocket fails to connect
    ↓
onError callback fires
    ↓
Create error event object
    ├─ event_type: "error"
    ├─ message: error.message
    └─ payload: {error_type: "connection"}
    ↓
appended to events[]
    ↓
Displayed in EventsDisplay (red background)
```

### Recording Errors
```
getUserMedia fails (microphone denied)
    ↓
catch block in startRecording()
    ↓
console.error()
    ↓
alert("Microphone access denied")
```

## Performance Optimizations

1. **Audio Chunking:** 4096-sample buffers prevent memory bloat
2. **Event Limiting:** Keep max 100 events in state (auto-prune)
3. **Lazy Polling:** Telemetry polls every 2 seconds, not continuously
4. **Debounced Renders:** Async state updates batch efficiently
5. **CSS:** Tailwind minified, scoped classes prevent conflicts
6. **Vite:** Optimized bundling, code splitting

## Responsive Design

```
Small screens (mobile):
└─ Stack vertically
   ├─ StatusHeader
   ├─ ConnectionPanel
   ├─ AudioRecorder
   └─ Events/Metrics tab

Large screens (desktop):
└─ Two-column layout
   ├─ Left: Controls (fixed 1/3 width)
   └─ Right: Display (2/3 width)
```

Used Tailwind's `lg:` responsive prefix throughout.

## Build & Deployment

### Development
```
npm run dev
    ↓
Vite dev server on http://localhost:5173
    ├─ Hot module replacement (HMR)
    ├─ Fast TypeScript compilation
    └─ Live reload
```

### Production
```
npm run build
    ↓
TypeScript type checking
    ├─ dist/index.html (minified)
    ├─ dist/assets/*.css (scoped)
    └─ dist/assets/*.js (chunked)
```

---

**Next:** [Backend Files](./BACKEND_FILES.md) - Detailed backend code explanation
