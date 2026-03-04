import { useEffect, useState } from 'react'
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
          console.error('WebSocket error:', error)
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
          console.log(`📊 Raw telemetry response:`, data)
          
          // Transform backend response to frontend LatencyMetrics format
          const totalE2E = data.percentiles?.total_e2e || { p50: 0, p95: 0, p99: 0 }
          const transformed: LatencyMetrics = {
            p50_ms: totalE2E.p50,
            p95_ms: totalE2E.p95,
            p99_ms: totalE2E.p99,
          }
          console.log(`📊 Transformed metrics: P50=${transformed.p50_ms}ms P95=${transformed.p95_ms}ms P99=${transformed.p99_ms}ms (${data.sample_count} samples)`)
          setMetrics(transformed)
        }
      } catch (error) {
        console.error('Failed to fetch metrics:', error)
      }
    }

    const interval = setInterval(fetchMetrics, 2000)
    return () => clearInterval(interval)
  }, [])

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
                  <EventsDisplay events={events} />
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
