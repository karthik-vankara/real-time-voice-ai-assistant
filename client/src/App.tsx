import { useEffect, useRef, useState } from 'react'
import { WebSocketClient } from './services/websocket'
import { ConnectionPanel } from './components/ConnectionPanel'
import { AudioRecorder } from './components/AudioRecorder'
import { EventsDisplay } from './components/EventsDisplay'
import { TelemetryDashboard } from './components/TelemetryDashboard'
import { StatusHeader } from './components/StatusHeader'
import type { PipelineEvent, LatencyMetrics } from './types'

export interface AppContextType {
  ws: WebSocketClient | null
  isConnected: boolean
  events: PipelineEvent[]
  metrics: LatencyMetrics
}

function App() {
  const [ws, setWs] = useState<WebSocketClient | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [events, setEvents] = useState<PipelineEvent[]>([])
  const [metrics, setMetrics] = useState<LatencyMetrics>({
    p50_ms: 0,
    p95_ms: 0,
    p99_ms: 0,
  })
  const [activeTab, setActiveTab] = useState<'transcript' | 'metrics'>('transcript')
  const audioContextRef = useRef<AudioContext | null>(null)
  const ttsChunksRef = useRef<Map<string, { chunks: string[]; isComplete: boolean }>>(new Map())
  const audioBuffersRef = useRef<Map<string, AudioBuffer>>(new Map())

  const handlePlayAudio = (correlationId: string) => {
    const audioBuffer = audioBuffersRef.current.get(correlationId)
    if (!audioBuffer) {
      return
    }

    const audioCtx = audioContextRef.current
    if (!audioCtx) {
      return
    }

    try {
      const source = audioCtx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioCtx.destination)
      source.start(0)
    } catch (error) {
      console.error('Error playing audio:', error)
    }
  }

  useEffect(() => {
    const client = new WebSocketClient(
      'ws://localhost:8000/ws',
      {
        onConnect: () => {
          setIsConnected(true)
          setEvents([])
        },
        onDisconnect: () => {
          setIsConnected(false)
        },
        onMessage: (event) => {
          setEvents((prev) => {
            const updated = [event, ...prev]
            return updated.slice(0, 100) // Keep last 100 events
          })
        },
        onError: (error) => {
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
      },
    )
    setWs(client)

    return () => {
      client.disconnect()
    }
  }, [])

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch('http://localhost:8000/telemetry/latency')
        if (response.ok) {
          const data = await response.json()
          // Transform backend response to frontend LatencyMetrics format
          const totalE2E = data.percentiles?.total_e2e || { p50: 0, p95: 0, p99: 0 }
          const transformed: LatencyMetrics = {
            p50_ms: totalE2E.p50,
            p95_ms: totalE2E.p95,
            p99_ms: totalE2E.p99,
          }
          setMetrics(transformed)
        }
      } catch (error) {
        // Silently handle telemetry fetch errors
      }
    }

    const interval = setInterval(fetchMetrics, 2000)
    return () => clearInterval(interval)
  }, [])

  // Auto-play TTS audio chunks
  useEffect(() => {
    // Initialize audio context on first render
    if (!audioContextRef.current && typeof AudioContext !== 'undefined') {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()
    }

    // Process TTS chunks for playback
    for (const event of events) {
      if (event.event_type === 'tts_audio_chunk') {
        const payload = event.payload as any
        const audio_b64 = payload.audio_b64
        const is_last = payload.is_last
        const correlationId = event.correlation_id

        if (!ttsChunksRef.current.has(correlationId)) {
          ttsChunksRef.current.set(correlationId, { chunks: [], isComplete: false })
        }

        const session = ttsChunksRef.current.get(correlationId)!
        
        // Add chunk if not already stored
        if (!session.isComplete && audio_b64 && !session.chunks.includes(audio_b64)) {
          session.chunks.push(audio_b64)
        }

        // Check is_last SEPARATELY - even if chunk was already stored
        if (!session.isComplete && is_last) {
          session.isComplete = true

          // Decode and store audio
          const playAudioChunks = async () => {
            try {
              const audioCtx = audioContextRef.current
              if (!audioCtx) {
                return
              }

              // Decode all base64 chunks to PCM
              const allBytes: number[] = []
              for (const b64 of session.chunks) {
                const binaryString = atob(b64)
                for (let i = 0; i < binaryString.length; i++) {
                  allBytes.push(binaryString.charCodeAt(i))
                }
              }

              // Convert to ArrayBuffer for decoding
              const audioData = new Uint8Array(allBytes)

              // Assume 16-bit PCM, 16kHz mono
              // Create AudioBuffer for playback
              const sampleRate = 16000
              const audioBuffer = audioCtx.createBuffer(
                1, // mono
                audioData.length / 2, // 16-bit = 2 bytes per sample
                sampleRate
              )

              const channelData = audioBuffer.getChannelData(0)
              let offset = 0
              for (let i = 0; i < channelData.length; i++) {
                // Read 16-bit signed little-endian samples
                let sample = audioData[offset] | (audioData[offset + 1] << 8)
                // Convert to signed 16-bit
                if (sample >= 32768) sample -= 65536
                // Normalize to -1.0 to 1.0
                channelData[i] = sample / 32768.0
                offset += 2
              }

              // Store the audio buffer for manual playback
              audioBuffersRef.current.set(correlationId, audioBuffer)
            } catch (error) {
              console.error('Error decoding audio:', error)
            }
          }

          playAudioChunks()
        }
      }
    }
  }, [events])

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <StatusHeader isConnected={isConnected} />

      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Controls */}
          <div className="lg:col-span-1 space-y-4">
            <ConnectionPanel ws={ws} isConnected={isConnected} />
            {isConnected && <AudioRecorder ws={ws} />}
          </div>

          {/* Right: Display */}
          <div className="lg:col-span-2">
            {isConnected ? (
              <>
                <div className="flex gap-2 mb-4 border-b border-slate-700">
                  <button
                    onClick={() => setActiveTab('transcript')}
                    className={`px-4 py-2 font-semibold transition ${
                      activeTab === 'transcript'
                        ? 'text-blue-400 border-b-2 border-blue-400'
                        : 'text-slate-400 hover:text-slate-300'
                    }`}
                  >
                    Transcript & Events ({events.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('metrics')}
                    className={`px-4 py-2 font-semibold transition ${
                      activeTab === 'metrics'
                        ? 'text-blue-400 border-b-2 border-blue-400'
                        : 'text-slate-400 hover:text-slate-300'
                    }`}
                  >
                    Telemetry
                  </button>
                </div>

                {activeTab === 'transcript' ? (
                  <EventsDisplay events={events} onPlayAudio={handlePlayAudio} />
                ) : (
                  <TelemetryDashboard metrics={metrics} />
                )}
              </>
            ) : (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 text-center">
                <p className="text-slate-400">Connect to the server first to start testing...</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
