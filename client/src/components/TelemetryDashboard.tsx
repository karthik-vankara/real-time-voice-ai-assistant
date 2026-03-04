import type { LatencyMetrics } from '../types'

interface TelemetryDashboardProps {
  metrics: LatencyMetrics
}

export function TelemetryDashboard({ metrics }: TelemetryDashboardProps) {
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

    return (
      <div className="bg-slate-700 rounded-lg p-4">
        <p className="text-sm text-slate-400 mb-2">{label}</p>
        <div className="flex items-end gap-2 mb-2">
          <span className="text-3xl font-bold">{value}</span>
          <span className="text-sm text-slate-400">{unit}</span>
        </div>
        <div className="w-full bg-slate-600 rounded-full h-2 overflow-hidden">
          <div className={`h-full ${color} transition-all duration-300`} style={{ width: `${Math.min(percentage, 100)}%` }} />
        </div>
        <p className="text-xs text-slate-400 mt-2">Target: &lt;{target}{unit}</p>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-semibold mb-4">Latency Metrics (P-percentiles)</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard label="P50 (Median)" value={metrics.p50_ms} target={1200} />
        <MetricCard label="P95 (95th %ile)" value={metrics.p95_ms} target={1200} />
        <MetricCard label="P99 (99th %ile)" value={metrics.p99_ms} target={1800} />
      </div>

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
  )
}
