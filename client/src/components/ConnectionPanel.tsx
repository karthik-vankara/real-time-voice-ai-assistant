import { WebSocketClient } from '../services/websocket'

interface ConnectionPanelProps {
  ws: WebSocketClient | null
  isConnected: boolean
}

export function ConnectionPanel({ ws, isConnected }: ConnectionPanelProps) {
  const handleConnect = async () => {
    if (!ws) return
    try {
      await ws.connect()
    } catch (error) {
      console.error('Connection failed:', error)
    }
  }

  const handleDisconnect = () => {
    if (ws) {
      ws.disconnect()
    }
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-semibold mb-4">Connection</h2>

      <div className="space-y-3">
        <div>
          <label className="text-sm text-slate-400">Server URL</label>
          <p className="text-sm font-mono bg-slate-900 p-2 rounded mt-1 break-all">
            {(() => {
              let httpBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
              // Ensure protocol is specified
              if (!httpBase.startsWith('http://') && !httpBase.startsWith('https://')) {
                httpBase = 'https://' + httpBase
              }
              // Remove trailing slash
              httpBase = httpBase.replace(/\/$/, '')
              // Convert to WebSocket URL
              return httpBase.replace(/^https?/, 'ws') + '/ws'
            })()}
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleConnect}
            disabled={isConnected}
            className={`flex-1 px-4 py-2 rounded font-medium transition ${
              isConnected
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            }`}
          >
            {isConnected ? '✓ Connected' : 'Connect'}
          </button>
          <button
            onClick={handleDisconnect}
            disabled={!isConnected}
            className={`flex-1 px-4 py-2 rounded font-medium transition ${
              !isConnected
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                : 'bg-red-600 hover:bg-red-700 text-white'
            }`}
          >
            Disconnect
          </button>
        </div>
      </div>

      <div className="mt-6 pt-6 border-t border-slate-700">
        <h3 className="text-sm font-semibold mb-3">Features</h3>
        <ul className="text-xs text-slate-400 space-y-2">
          <li>✓ Real-time WebSocket streaming</li>
          <li>✓ Audio input recording</li>
          <li>✓ Live event display</li>
          <li>✓ Latency telemetry (P50/P95/P99)</li>
          <li>✓ Barge-in support</li>
          <li>✓ Error handling & fallbacks</li>
        </ul>
      </div>
    </div>
  )
}
