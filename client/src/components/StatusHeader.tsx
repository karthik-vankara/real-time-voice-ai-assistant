export function StatusHeader({ isConnected }: { isConnected: boolean }) {
  return (
    <div className="bg-slate-800 border-b border-slate-700">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">🎙️ Voice Assistant</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time streaming pipeline test client</p>
        </div>
        <div className="flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 pulse-ring' : 'bg-red-500'}`}
          />
          <span className="text-sm font-medium">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>
    </div>
  )
}
