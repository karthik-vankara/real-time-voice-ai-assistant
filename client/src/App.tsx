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
  const ttsChunksRef = useRef<Map<string, { chunks: Map<number, string>; isComplete: boolean; maxIndex: number; gotFinalFlag?: boolean; expectedFinalIndex?: number }>>(new Map())
  const audioBuffersRef = useRef<Map<string, AudioBuffer>>(new Map())

  const handlePlayAudio = (correlationId: string) => {
    const audioBuffer = audioBuffersRef.current.get(correlationId)
    if (!audioBuffer) {
      console.warn(`Audio buffer not found for ${correlationId}`)
      return
    }

    const audioCtx = audioContextRef.current
    if (!audioCtx) {
      console.error('Audio context not initialized')
      return
    }

    try {
      console.log(
        `Playing audio: ${correlationId}, duration: ${audioBuffer.duration.toFixed(2)}s, channels: ${audioBuffer.numberOfChannels}, sample rate: ${audioBuffer.sampleRate}Hz`,
      )
      const source = audioCtx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioCtx.destination)
      source.start(0)
    } catch (error) {
      console.error('Error playing audio:', error)
    }
  }

  // Helper function to build secure WebSocket URL
  const getWebSocketUrl = (): string => {
    let httpBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    
    // Ensure protocol is specified (handle case where only domain is provided)
    if (!httpBase.startsWith('http://') && !httpBase.startsWith('https://')) {
      httpBase = 'https://' + httpBase
    }
    
    // Remove trailing slash if present
    httpBase = httpBase.replace(/\/$/, '')
    
    // Convert http(s) to ws(s) - preserve security protocol
    let wsUrl: string
    if (httpBase.startsWith('https://')) {
      wsUrl = 'wss://' + httpBase.slice(8) + '/ws'  // Remove 'https://', add 'wss://'
    } else {
      wsUrl = 'ws://' + httpBase.slice(7) + '/ws'   // Remove 'http://', add 'ws://'
    }
    console.log(`[WS] Connecting to: ${wsUrl}`)
    return wsUrl
  }

  useEffect(() => {
    // Build WebSocket URL from HTTP base URL
    const wsUrl = getWebSocketUrl()
    
    const client = new WebSocketClient(
      wsUrl,
      {
        onConnect: () => {
          setIsConnected(true)
          setEvents([])
          // Clear old audio buffers on new connection
          audioBuffersRef.current.clear()
          ttsChunksRef.current.clear()
        },
        onDisconnect: () => {
          setIsConnected(false)
        },
        onMessage: (event) => {
          // Log important events for debugging
          if (event.event_type === 'transcription_final') {
            const payload = event.payload as any
            console.log('[ASR RESULT]', payload.text, event.correlation_id)
          } else if (event.event_type === 'llm_token') {
            const payload = event.payload as any
            console.log('[LLM TOKEN]', {
              token: payload.token,
              accumulated: payload.accumulated_text,
            })
          } else if (event.event_type === 'tts_audio_chunk') {
            const payload = event.payload as any
            console.log('[TTS CHUNK]', {
              index: payload.chunk_index,
              is_last: payload.is_last,
              size: Math.ceil(payload.audio_b64.length * 0.75),
            })
          } else if (event.event_type === 'intent_detected') {
            const payload = event.payload as any
            console.log('[INTENT]', {
              intent: payload.intent,
              query: payload.query,
              requires_search: payload.requires_search,
            })
          } else if (event.event_type === 'web_search_result') {
            const payload = event.payload as any
            console.log('[SEARCH RESULT]', {
              query: payload.query,
              source_count: payload.source_count,
            })
          }
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
        let httpBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
        
        // Ensure protocol is specified
        if (!httpBase.startsWith('http://') && !httpBase.startsWith('https://')) {
          httpBase = 'https://' + httpBase
        }
        
        // Remove trailing slash
        httpBase = httpBase.replace(/\/$/, '')
        
        const response = await fetch(`${httpBase}/telemetry/latency`)
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
        const chunk_index = payload.chunk_index ?? 0
        const is_last = payload.is_last
        const correlationId = event.correlation_id

        if (!ttsChunksRef.current.has(correlationId)) {
          ttsChunksRef.current.set(correlationId, {
            chunks: new Map(),
            isComplete: false,
            maxIndex: 0,
            gotFinalFlag: false,
            expectedFinalIndex: undefined,
          })
        }

        const session = ttsChunksRef.current.get(correlationId)!

        // Store chunk by index (preserve order, ignore duplicates)
        if (!session.isComplete && audio_b64) {
          session.chunks.set(chunk_index, audio_b64)
          session.maxIndex = Math.max(session.maxIndex, chunk_index)
        }

        // When we get the final chunk, mark that we got is_last but DON'T decode yet
        if (!session.isComplete && is_last) {
          console.log(
            `[TTS FINAL CHUNK] Got is_last flag at chunk ${chunk_index}. Stored so far: ${session.chunks.size}`,
          )
          session.expectedFinalIndex = chunk_index
          session.gotFinalFlag = true
        }

        // Check if we have all chunks (0 to expectedFinalIndex)
        if (session.gotFinalFlag && !session.isComplete) {
          const expectedCount = session.expectedFinalIndex! + 1
          const actualCount = session.chunks.size

          // Check which chunks are missing
          const missingChunks: number[] = []
          for (let i = 0; i <= session.expectedFinalIndex!; i++) {
            if (!session.chunks.has(i)) {
              missingChunks.push(i)
            }
          }

          if (missingChunks.length === 0) {
            // All chunks arrived! Now we can decode
            session.isComplete = true
            console.log(
              `[TTS READY] All ${actualCount} chunks received (0-${session.expectedFinalIndex}). Starting decode...`,
            )

            // Decode and store audio
            const decodeAudio = async () => {
              try {
                const audioCtx = audioContextRef.current
                if (!audioCtx) {
                  console.error('Audio context not initialized')
                  return
                }

                // Give a small delay to ensure all chunks are truly in place
                await new Promise((resolve) => setTimeout(resolve, 50))

                // Reconstruct audio in proper order using chunk indices
                const allBytes: number[] = []
                for (let i = 0; i <= session.expectedFinalIndex!; i++) {
                  const b64 = session.chunks.get(i)
                  if (!b64) {
                    console.warn(`Missing chunk at index ${i}`)
                    continue
                  }
                  const binaryString = atob(b64)
                  for (let j = 0; j < binaryString.length; j++) {
                    allBytes.push(binaryString.charCodeAt(j))
                  }
                }

                if (allBytes.length === 0) {
                  console.error('No audio data to decode')
                  return
                }

                console.log(
                  `[TTS DECODED] Total audio data: ${allBytes.length} bytes, from ${session.chunks.size} chunks`,
                )

                // Convert to ArrayBuffer
                const binaryData = new Uint8Array(allBytes)
                const arrayBuffer = binaryData.buffer

                // Use Web Audio API to decode the audio (handles MP3, AAC, etc.)
                audioCtx.decodeAudioData(
                  arrayBuffer.slice(0),
                  (decodedBuffer) => {
                    audioBuffersRef.current.set(correlationId, decodedBuffer)
                    console.log(
                      `Audio decoded successfully for ${correlationId}: ${session.chunks.size} chunks, ${(arrayBuffer.byteLength / 1024).toFixed(1)}KB`,
                    )
                  },
                  (error) => {
                    console.error(`Error decoding audio for ${correlationId}:`, error)
                  },
                )
              } catch (error) {
                console.error('Error processing audio chunks:', error)
              }
            }

            decodeAudio()
          } else {
            console.log(
              `⏳ Waiting for chunks... Have ${actualCount}/${expectedCount}. Missing: [${missingChunks.join(', ')}]`,
            )
          }
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
