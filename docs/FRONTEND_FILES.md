# Frontend Files - Line-by-Line Explanation

## 1. client/src/main.tsx - Vite Entry Point

**Purpose:** Initialize React app and mount to DOM.

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

**Why:** 
- `React.StrictMode`: Highlights potential bugs in development
- Mounts App root component to `#root` div in index.html
- Vite uses this as entry point

---

## 2. client/src/types.ts - TypeScript Interfaces

**Purpose:** Centralized type definitions for entire app.

### PipelineEvent Interface
```typescript
export interface PipelineEvent {
  event_type: 
    | 'speech_started'
    | 'transcription_provisional'
    | 'transcription_final'
    | 'llm_token'
    | 'tts_audio_chunk'
    | 'error'
  correlation_id: string           // UUID linking events in one request
  timestamp: string                // ISO 8601
  schema_version: string           // "1.0.0"
  payload: Record<string, any>     // Event-specific data
}
```

**Why:** Type-safe event handling. Prevents runtime type errors.

### Specialized Event Types
```typescript
export interface TranscriptionEvent extends PipelineEvent {
  event_type: 'transcription_provisional' | 'transcription_final'
  payload: {
    text: string                   // "hello how are you"
    is_final: boolean              // true only for final
  }
}

export interface LLMTokenEvent extends PipelineEvent {
  event_type: 'llm_token'
  payload: {
    token: string                  // "I'm", "doing", "great", etc.
  }
}

export interface TTSAudioChunkEvent extends PipelineEvent {
  event_type: 'tts_audio_chunk'
  payload: {
    audio_base64: string           // Encoded audio bytes
  }
}

export interface ErrorEvent extends PipelineEvent {
  event_type: 'error'
  payload: {
    code: string                   // "INVALID_AUDIO", "SERVICE_ERROR"
    message: string                // Error description
  }
}
```

**Why:** Prevents payload field typos. IDE autocomplete works.

### LatencyMetrics Interface
```typescript
export interface LatencyMetrics {
  p50_ms: number      // Median latency
  p95_ms: number      // 95th percentile
  p99_ms: number      // 99th percentile
}
```

**Why:** Frontend telemetry state. Matches backend response format.

---

## 3. client/src/App.tsx - Root Component & State

**Purpose:** Central state hub. Manages WebSocket and polling. Routes props to children.

```typescript
export interface AppContextType {
  ws: WebSocketClient | null
  isConnected: boolean
  events: PipelineEvent[]
  metrics: LatencyMetrics
}

function App() {
  // State
  const [ws, setWs] = useState<WebSocketClient | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [events, setEvents] = useState<PipelineEvent[]>([])
  const [metrics, setMetrics] = useState<LatencyMetrics>({
    p50_ms: 0,
    p95_ms: 0,
    p99_ms: 0,
  })
  const [activeTab, setActiveTab] = useState<'transcript' | 'metrics'>('transcript')
```

### Effect 1: Initialize WebSocket
```typescript
useEffect(() => {
  const client = new WebSocketClient('ws://localhost:8000/ws', {
    onConnect: () => {
      setIsConnected(true)
      setEvents([])  // Clear old events on new connection
    },
    onDisconnect: () => {
      setIsConnected(false)
    },
    onMessage: (event) => {
      setEvents((prev) => {
        const updated = [event, ...prev]
        return updated.slice(0, 100)  // Keep last 100 events
      })
    },
    onError: (error) => {
      // Create error event
      setEvents((prev) => [
        ...prev,
        {
          event_type: 'error',
          correlation_id: 'error-' + Date.now(),
          timestamp: new Date().toISOString(),
          schema_version: '1.0.0',
          payload: {
            error_type: 'connection',
            message: error.message,
          },
        } as any,
      ])
    },
  })
  setWs(client)

  return () => {
    client.disconnect()  // Cleanup on unmount
  }
}, [])  // Run once on mount
```

**Why:**
- Initializes WebSocket client with callbacks
- Connects automatically
- Clears state on reconnect
- Cleanup on component unmount

### Effect 2: Telemetry Polling
```typescript
useEffect(() => {
  const fetchMetrics = async () => {
    try {
      const response = await fetch('http://localhost:8000/telemetry/latency')
      if (response.ok) {
        const data = await response.json()
        
        // Transform backend response to frontend format
        const totalE2E = data.percentiles?.total_e2e || { p50: 0, p95: 0, p99: 0 }
        const transformed: LatencyMetrics = {
          p50_ms: totalE2E.p50,
          p95_ms: totalE2E.p95,
          p99_ms: totalE2E.p99,
        }
        
        console.log(`📊 Telemetry: P50=${transformed.p50_ms}ms P95=${transformed.p95_ms}ms`)
        setMetrics(transformed)
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error)
    }
  }

  const interval = setInterval(fetchMetrics, 2000)  // Poll every 2 seconds
  return () => clearInterval(interval)
}, [])  // Run once on mount
```

**Why:**
- Fetches latency metrics every 2 seconds
- Transforms nested backend response to flat frontend interface
- Updates telemetry display without re-rendering WebSocket

### Render
```typescript
return (
  <div className="min-h-screen bg-slate-900 text-slate-100">
    <StatusHeader isConnected={isConnected} />

    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Controls */}
        <div className="lg:col-span-1 space-y-4">
          <ConnectionPanel ws={ws} isConnected={isConnected} />
          {isConnected && <AudioRecorder ws={ws} />}  {/* Only show if connected */}
        </div>

        {/* Right: Display */}
        <div className="lg:col-span-2">
          {isConnected ? (
            <>
              <div className="flex gap-2 mb-4">
                <button
                  onClick={() => setActiveTab('transcript')}
                  className={activeTab === 'transcript' ? 'active-button' : 'inactive-button'}
                >
                  Transcript & Events ({events.length})
                </button>
                <button
                  onClick={() => setActiveTab('metrics')}
                  className={activeTab === 'metrics' ? 'active-button' : 'inactive-button'}
                >
                  Telemetry
                </button>
              </div>

              {activeTab === 'transcript' ? (
                <EventsDisplay events={events} />
              ) : (
                <TelemetryDashboard metrics={metrics} />
              )}
            </>
          ) : (
            <div className="bg-slate-800 text-center p-8">
              <p>Connect to the server first...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  </div>
)
```

**Why:**
- Responsive grid layout
- Tab UI for switching between transcript and telemetry
- Conditional rendering based on connection state

---

## 4. client/src/components/StatusHeader.tsx - Connection Status Bar

**Purpose:** Top bar showing connection status.

```typescript
interface StatusHeaderProps {
  isConnected: boolean
}

export function StatusHeader({ isConnected }: StatusHeaderProps) {
  return (
    <div className="bg-slate-950 border-b border-slate-700 px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center gap-3">
        {/* Connection indicator */}
        <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
        
        {/* Status text */}
        <span className={`font-semibold ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
          {isConnected ? 'Connected to server' : 'Disconnected'}
        </span>
        
        {/* Latency info */}
        {isConnected && (
          <span className="text-sm text-slate-400 ml-auto">
            ws://localhost:8000/ws
          </span>
        )}
      </div>
    </div>
  )
}
```

**Why:** Immediate visual feedback. User knows if connected before trying to record.

---

## 5. client/src/components/ConnectionPanel.tsx - Server Connection

**Purpose:** Button to connect/disconnect from WebSocket.

```typescript
interface ConnectionPanelProps {
  ws: WebSocketClient | null
  isConnected: boolean
}

export function ConnectionPanel({ ws, isConnected }: ConnectionPanelProps) {
  const handleConnect = async () => {
    if (!ws) return
    
    try {
      console.log('🔌 Attempting to connect...')
      await ws.connect()
    } catch (error) {
      console.error('Failed to connect:', error)
      alert(`Connection failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleDisconnect = () => {
    if (!ws) return
    console.log('🔌 Disconnecting...')
    ws.disconnect()
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-semibold mb-4">Server Connection</h2>

      <button
        onClick={isConnected ? handleDisconnect : handleConnect}
        disabled={!ws}
        className={`w-full px-4 py-3 rounded font-medium transition ${
          isConnected
            ? 'bg-red-600 hover:bg-red-700 text-white'
            : 'bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50'
        }`}
      >
        {isConnected ? '🔌 Disconnect' : '🔌 Connect'}
      </button>

      <div className="bg-slate-900 rounded p-3 mt-3 text-xs text-slate-400">
        Server: ws://localhost:8000/ws
      </div>
    </div>
  )
}
```

**Why:**
- Simple button to toggle connection
- Error handling with user feedback
- Disabled state when ws not ready

---

## 6. client/src/components/AudioRecorder.tsx - Microphone Recording

**Purpose:** Core audio capture UI. Records audio, sends to server.

### Audio Encoding
```typescript
const floatTo16BitPCM = (floats: Float32Array): Uint8Array => {
  // Log input properties
  console.log(`📊 Input floats: length=${floats.length}, byteLength=${floats.byteLength}`)
  
  const numSamples = floats.length
  
  // Create Int16Array - this will have numSamples elements, each 2 bytes
  const pcm = new Int16Array(numSamples)
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, floats[i]))  // Clamp to [-1, 1]
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff       // Scale to 16-bit
  }
  
  console.log(`📊 Int16Array created: length=${pcm.length}, byteLength=${pcm.byteLength}`)
  
  // Create Uint8Array view from the ArrayBuffer
  const uint8Data = new Uint8Array(pcm.buffer)
  const expectedBytes = numSamples * 2
  const actualBytes = uint8Data.byteLength
  
  console.log(`📊 Uint8Array created: byteLength=${actualBytes} (expected ${expectedBytes})`)
  console.log(`✅ Status: ${actualBytes % 2 === 0 ? 'EVEN (valid)' : 'ODD (invalid)'}`)
  
  if (actualBytes !== expectedBytes) {
    throw new Error(`PCM: byte length mismatch`)
  }
  
  if (actualBytes % 2 !== 0) {
    throw new Error(`PCM: odd-length data`)
  }
  
  return uint8Data
}
```

**Why:**
- Converts Web Audio API float samples to 16-bit PCM
- Validates output
- Comprehensive logging for debugging

### Recording Logic
```typescript
const startRecording = async () => {
  try {
    // Request microphone access
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: { ideal: 16000 },
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })
    streamRef.current = stream

    // Create Web Audio API context
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    audioContextRef.current = audioContext

    const source = audioContext.createMediaStreamSource(stream)

    // Create ScriptProcessor for raw audio chunks
    const processor = audioContext.createScriptProcessor(4096, 1, 1)
      // 4096: buffer size (samples)
      // 1: input channels
      // 1: output channels

    processor.onaudioprocess = (event) => {
      const inputData = event.inputBuffer.getChannelData(0)  // Float32Array
      const pcmData = floatTo16BitPCM(inputData)             // Uint8Array

      if (ws?.isConnected()) {
        ws.sendAudio(pcmData)  // Send binary Uint8Array
      }
    }

    processorRef.current = processor
    source.connect(processor)
    processor.connect(audioContext.destination)

    setIsRecording(true)
    setRecordingTime(0)

    timerRef.current = setInterval(() => {
      setRecordingTime((prev) => prev + 1)
    }, 1000)
  } catch (error) {
    console.error('Failed to start recording:', error)
    alert('Microphone access denied or not available')
  }
}
```

**Why:**
- Request microphone with specific settings (16kHz, mono)
- ScriptProcessor fires onaudioprocess event every ~256ms
- Encode and immediately send each chunk

### Stop Recording
```typescript
const stopRecording = () => {
  if (isRecording) {
    // Stop audio context
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }

    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    // Stop media stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }

    setIsRecording(false)

    if (timerRef.current) {
      clearInterval(timerRef.current)
    }

    // Send end_of_utterance signal to trigger pipeline
    console.log('🎤 Recording stopped, sending end_of_utterance signal')
    ws?.sendControl('end_of_utterance')  // CRITICAL: Tells server to process
  }
}
```

**Why:**
- Clean up all audio context resources
- Send `end_of_utterance` message to trigger backend pipeline
- Without this, server keeps waiting for more audio

### UI
```typescript
<button
  onClick={isRecording ? stopRecording : startRecording}
  className={`w-full px-4 py-3 rounded font-medium transition ${
    isRecording
      ? 'bg-red-600 hover:bg-red-700 text-white'
      : 'bg-green-600 hover:bg-green-700 text-white'
  }`}
>
  {isRecording ? '⏹ Stop Recording' : '🎤 Start Recording'}
</button>
```

**Why:** Visual feedback. Button color changes based on recording state.

---

## 7. client/src/components/EventsDisplay.tsx - Real-Time Event Feed

**Purpose:** Display incoming events from server in real-time.

### Event Color Coding
```typescript
const getEventColor = (eventType: string) => {
  switch (eventType) {
    case 'speech_started':
      return 'bg-blue-900 border-blue-700'
    case 'transcription_provisional':
      return 'bg-amber-900 border-amber-700'
    case 'transcription_final':
      return 'bg-green-900 border-green-700'
    case 'llm_token':
      return 'bg-purple-900 border-purple-700'
    case 'tts_audio_chunk':
      return 'bg-cyan-900 border-cyan-700'
    case 'error':
      return 'bg-red-900 border-red-700'
  }
}
```

**Why:** Visual differentiation. User instantly sees which stage is happening.

### Text Extraction
```typescript
const extractText = (event: PipelineEvent): string => {
  const payload = event.payload as any
  if (payload.text) return payload.text               // Transcription, LLM
  if (payload.token) return payload.token            // LLM tokens
  if (payload.accumulated_text) return payload.accumulated_text
  if (payload.message) return payload.message        // Error
  return JSON.stringify(payload)                     // Fallback
}
```

**Why:** Flexible payload handling. Different event types have different fields.

### Rendering
```typescript
<div className="max-h-96 overflow-y-auto space-y-3">
  {events.length === 0 ? (
    <div className="text-center py-12 text-slate-400">
      <p>No events yet. Start recording...</p>
    </div>
  ) : (
    events.map((event, idx) => (
      <div
        key={`${event.correlation_id}-${idx}`}
        className={`rounded border p-3 fade-in ${getEventColor(event.event_type)}`}
      >
        <div className="flex items-start gap-3">
          <span className="text-xl">{getEventEmoji(event.event_type)}</span>
          <div className="flex-1">
            <h3 className="font-semibold text-sm">
              {event.event_type.replace(/_/g, ' ')}  {/* "llm_token" → "llm token" */}
            </h3>
            <p className="text-sm mt-1 break-words">
              {extractText(event)}
            </p>
            <p className="text-xs text-slate-400 mt-2 opacity-60 font-mono">
              {event.correlation_id}
            </p>
          </div>
          <span className="text-xs text-slate-300">
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>
    ))
  )}
</div>
```

**Why:**
- Scrollable container
- Each event shows emoji, type, text, timestamp
- fade-in CSS animation
- Correlation ID for debugging

---

## 8. client/src/components/TelemetryDashboard.tsx - Metrics Dashboard

**Purpose:** Display latency metrics with visual progress bars.

### MetricCard Component
```typescript
const MetricCard = ({
  label,
  value,
  unit = 'ms',
  target = 1200,
}: {
  label: string
  value: number
  unit?: string
  target?: number
}) => {
  const percentage = (value / target) * 100
  const isGood = percentage < 50
  const isOkay = percentage < 80
  const color = isGood ? 'bg-green-600' : isOkay ? 'bg-amber-600' : 'bg-red-600'
  const roundedValue = value.toFixed(5)  // Round to 5 decimals

  return (
    <div className="bg-slate-700 rounded-lg p-4">
      <p className="text-sm text-slate-400 mb-2">{label}</p>
      <div className="flex items-end gap-2 mb-2">
        <span className="text-3xl font-bold">{roundedValue}</span>
        <span className="text-sm text-slate-400">{unit}</span>
      </div>
      <div className="w-full bg-slate-600 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-300`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      <p className="text-xs text-slate-400 mt-2">Target: &lt;{target}{unit}</p>
    </div>
  )
}
```

**Why:**
- Reusable metric card component
- Color gradient: green → amber → red based on budget usage
- Progress bar visualization

### Dashboard Render
```typescript
<div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
  <h2 className="text-lg font-semibold mb-4">Latency Metrics (P-percentiles)</h2>

  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
    <MetricCard label="P50 (Median)" value={metrics.p50_ms} target={1200} />
    <MetricCard label="P95 (95th %ile)" value={metrics.p95_ms} target={1200} />
    <MetricCard label="P99 (99th %ile)" value={metrics.p99_ms} target={1800} />
  </div>

  {/* Breakdown table */}
  <div className="mt-6 bg-slate-700 rounded-lg p-4">
    <h3 className="font-semibold text-sm mb-3">Latency Budget Breakdown</h3>
    <div className="space-y-2 text-xs text-slate-400">
      <div className="flex justify-between">
        <span>ASR (Speech Recognition)</span>
        <span className="font-mono">500 ms</span>
      </div>
      <div className="flex justify-between">
        <span>LLM (Time to First Token)</span>
        <span className="font-mono">400 ms</span>
      </div>
      <div className="flex justify-between">
        <span>TTS (Time to First Byte)</span>
        <span className="font-mono">250 ms</span>
      </div>
      <div className="flex justify-between">
        <span>Orchestration Overhead</span>
        <span className="font-mono">100 ms</span>
      </div>
      <div className="border-t border-slate-600 pt-2 mt-2 flex justify-between font-semibold text-white">
        <span>Total E2E (P95)</span>
        <span className="font-mono">1,200 ms</span>
      </div>
    </div>
  </div>

  {/* System status */}
  <div className="mt-6 bg-slate-700 rounded-lg p-4">
    <h3 className="font-semibold text-sm mb-2">System Status</h3>
    <ul className="text-xs text-slate-400 space-y-1">
      <li>✓ Circuit breakers: Per-service resilience</li>
      <li>✓ Fallback strategies: Bridge audio on failure</li>
      <li>✓ 10-turn context: Conversation history maintained</li>
      <li>✓ Barge-in support: Interrupt in-progress responses</li>
      <li>✓ Session replay: Record & playback for debugging</li>
    </ul>
  </div>
</div>
```

**Why:**
- 3-column grid for large screens (responsive)
- Budget breakdown table for education
- System status checklist

---

## 9. client/src/services/websocket.ts - WebSocket Client

**Purpose:** Abstraction layer for WebSocket communication.

### Configuration Interface
```typescript
export interface WebSocketClientConfig {
  onConnect?: () => void
  onDisconnect?: () => void
  onMessage?: (event: PipelineEvent) => void
  onError?: (error: Error) => void
}
```

### WebSocketClient Class
```typescript
export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private config: WebSocketClientConfig
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000

  constructor(url: string, config: WebSocketClientConfig = {}) {
    this.url = url
    this.config = config
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
          console.log('✅ WebSocket connected')
          this.reconnectAttempts = 0
          this.config.onConnect?.()
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            this.config.onMessage?.(data)
          } catch (error) {
            console.error('Failed to parse message:', error)
          }
        }

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error)
          this.config.onError?.(new Error('WebSocket error'))
          reject(new Error('WebSocket connection failed'))
        }

        this.ws.onclose = () => {
          console.log('❌ WebSocket disconnected')
          this.config.onDisconnect?.()
          this.attemptReconnect()
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`🔄 Reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`)
      setTimeout(() => {
        this.connect().catch((error) => {
          console.error('Reconnection failed:', error)
        })
      }, this.reconnectDelay)
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  sendAudio(audioData: Uint8Array): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const byteLength = audioData.byteLength
      const isEven = byteLength % 2 === 0
      console.log(`📤 Sending ${byteLength} bytes (${isEven ? 'EVEN ✅' : 'ODD ❌'})`)
      this.ws.send(audioData)
    } else {
      console.warn('⚠️ WebSocket is not connected')
    }
  }

  sendControl(action: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ action })
      console.log(`📤 Sending control: ${action}`)
      this.ws.send(message)
    } else {
      console.warn(`⚠️ WebSocket not connected`)
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
```

**Why:**
- Abstraction hides WebSocket implementation details
- Auto-reconnect on disconnect (up to 5 attempts)
- Type-safe callbacks
- Binary audio support + text control messages

---

## Component Tree

```
App
├── StatusHeader
├── Layout (grid)
│  ├── Left Column
│  │  ├── ConnectionPanel
│  │  └── AudioRecorder (if connected)
│  │
│  └── Right Column
│     ├── Tabs (Transcript | Telemetry)
│     ├── EventsDisplay (if connected)
│     └── TelemetryDashboard (if connected)
```

---

## Data Flow Summary

```
User → AudioRecorder component
  ↓
Record mic → floatTo16BitPCM conversion
  ↓
Uint8Array PCM data
  ↓
WebSocketClient.sendAudio()
  ↓
Binary WebSocket frame to server
  ↓
(Server processes)
  ↓
Server emits JSON events
  ↓
WebSocketClient.onmessage
  ↓
App.onMessage handler
  ↓
setEvents() updates state
  ↓
EventsDisplay re-renders
  ↓
User sees event card
```

---

## Key Design Patterns

### 1. **Props Drilling**
Pass `ws` prop from App → ConnectionPanel, AudioRecorder, etc.
Simple for small app, works fine here.

### 2. **Callback-Based Events**
WebSocketClient uses callbacks (`onConnect`, `onMessage`, etc) instead of Pub/Sub.
Simpler implementation.

### 3. **Declarative Rendering**
React components render based on state. When state changes, re-render automatically.

### 4. **Refs for DOM/Non-State Values**
`audioContextRef`, `streamRef`, `processorRef` don't cause re-renders when updated.

### 5. **Cleanup in Effects**
Disconnect WebSocket, clear intervals — all in return statements of useEffect.

---

## Performance Notes

- **Event Limiting:** Keep max 100 events (auto-prune oldest)
- **Lazy Polling:** Telemetry every 2 seconds, not 100ms
- **No Redux/Context:** Simple prop drilling is fine here
- **Tailwind:** Scoped CSS, no global pollution
- **Vite Build:** Code-split by route, tree-shaken dead code

---

**Summary:** Frontend is a React+TypeScript SPA with real-time WebSocket streaming and latency visualization.

