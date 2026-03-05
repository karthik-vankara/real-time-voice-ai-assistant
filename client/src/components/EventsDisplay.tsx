import type { PipelineEvent } from '../types'

interface EventsDisplayProps {
  events: PipelineEvent[]
  onPlayAudio?: (correlationId: string) => void
}

export function EventsDisplay({ events, onPlayAudio }: EventsDisplayProps) {
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
      default:
        return 'bg-slate-700 border-slate-600'
    }
  }

  const getEventEmoji = (eventType: string) => {
    switch (eventType) {
      case 'speech_started':
        return '🔊'
      case 'transcription_provisional':
        return '📝'
      case 'transcription_final':
        return '✅'
      case 'llm_token':
        return '🤖'
      case 'tts_audio_chunk':
        return '🔊'
      case 'error':
        return '❌'
      default:
        return '📌'
    }
  }

  const extractText = (event: PipelineEvent): string => {
    const payload = event.payload as any
    
    // Handle TTS audio chunks - show size instead of base64
    if (event.event_type === 'tts_audio_chunk') {
      const bytes = payload.audio_b64 ? Math.ceil(payload.audio_b64.length * 0.75) : 0
      const isLast = payload.is_last ? ' (final)' : ''
      return `Audio chunk: ${bytes} bytes${isLast}`
    }
    
    if (payload.text) return payload.text
    if (payload.token) return payload.token
    if (payload.accumulated_text) return payload.accumulated_text
    if (payload.message) return payload.message
    return JSON.stringify(payload)
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <div className="max-h-96 overflow-y-auto space-y-3">
        {events.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <p>No events yet. Start recording to see real-time events...</p>
          </div>
        ) : (
          events.map((event, idx) => (
            <div
              key={`${event.correlation_id}-${idx}`}
              className={`rounded border p-3 fade-in ${getEventColor(event.event_type)}`}
            >
              <div className="flex items-start gap-3">
                <span className="text-xl">{getEventEmoji(event.event_type)}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-semibold text-sm">{event.event_type.replace(/_/g, ' ')}</h3>
                    <span className="text-xs text-slate-300 opacity-70">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2 mt-1">
                    <p className="text-sm break-words whitespace-pre-wrap">{extractText(event)}</p>
                    {event.event_type === 'tts_audio_chunk' && onPlayAudio && (
                      <button
                        onClick={() => onPlayAudio(event.correlation_id)}
                        className="px-2 py-1 text-xs bg-cyan-600 hover:bg-cyan-500 rounded transition whitespace-nowrap"
                      >
                        ▶ Play
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-2 opacity-60 font-mono">
                    {event.correlation_id}
                  </p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
