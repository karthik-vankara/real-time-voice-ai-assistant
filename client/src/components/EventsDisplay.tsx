import type { PipelineEvent } from '../types'

interface EventsDisplayProps {
  events: PipelineEvent[]
  onPlayAudio?: (correlationId: string) => void
}

export function EventsDisplay({ events, onPlayAudio }: EventsDisplayProps) {
  // Group TTS chunks by correlation_id - consolidate all chunks into 1 event per response
  const getConsolidatedEvents = () => {
    const consolidatedMap = new Map<string, PipelineEvent[]>()
    const orderedEvents: (PipelineEvent | { type: 'consolidated'; correlationId: string; events: PipelineEvent[] })[]
      = []

    for (const event of events) {
      if (event.event_type === 'tts_audio_chunk') {
        // Group TTS chunks by correlation_id
        if (!consolidatedMap.has(event.correlation_id)) {
          consolidatedMap.set(event.correlation_id, [])
          orderedEvents.push({
            type: 'consolidated',
            correlationId: event.correlation_id,
            events: consolidatedMap.get(event.correlation_id)!,
          })
        }
        consolidatedMap.get(event.correlation_id)!.push(event)
      } else {
        orderedEvents.push(event)
      }
    }

    return orderedEvents
  }

  const getEventColor = (eventType: string) => {
    switch (eventType) {
      case 'speech_started':
        return 'bg-blue-900 border-blue-700'
      case 'transcription_provisional':
        return 'bg-amber-900 border-amber-700'
      case 'transcription_final':
        return 'bg-green-900 border-green-700'
      case 'intent_detected':
        return 'bg-orange-900 border-orange-700'
      case 'web_search_result':
        return 'bg-teal-900 border-teal-700'
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
      case 'intent_detected':
        return '🎯'
      case 'web_search_result':
        return '🔍'
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

    // Handle intent detected events
    if (event.event_type === 'intent_detected') {
      const searchIcon = payload.requires_search ? '🔍 Searching: ' : '💬 Direct: '
      return `${searchIcon}${payload.intent}${payload.query ? ` — "${payload.query}"` : ''}`
    }

    // Handle web search result events
    if (event.event_type === 'web_search_result') {
      return `Found ${payload.source_count} sources for "${payload.query}"${payload.results_summary ? `\n${payload.results_summary}` : ''}`
    }

    if (payload.text) return payload.text
    if (payload.token) return payload.token
    if (payload.accumulated_text) return payload.accumulated_text
    if (payload.message) return payload.message
    return JSON.stringify(payload)
  }

  const consolidatedEvents = getConsolidatedEvents()

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <div className="max-h-96 overflow-y-auto space-y-3">
        {consolidatedEvents.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <p>No events yet. Start recording to see real-time events...</p>
          </div>
        ) : (
          consolidatedEvents.map((item, idx) => {
            // Handle consolidated TTS chunks
            const isConsolidated = 'type' in item && item.type === 'consolidated'
            if (isConsolidated) {
              const event = item.events[0] // Use first event for timestamp
              const totalBytes = item.events.reduce((sum, e) => {
                const payload = e.payload as any
                return sum + (payload.audio_b64 ? Math.ceil(payload.audio_b64.length * 0.75) : 0)
              }, 0)
              return (
                <div
                  key={`consolidated-${item.correlationId}-${idx}`}
                  className={`rounded border p-3 fade-in ${getEventColor('tts_audio_chunk')}`}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-xl">{getEventEmoji('tts_audio_chunk')}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="font-semibold text-sm">
                          TTS audio response ({item.events.length} chunks)
                        </h3>
                        <span className="text-xs text-slate-300 opacity-70">
                          {new Date(event.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-2 mt-1">
                        <p className="text-sm break-words whitespace-pre-wrap">Audio: {totalBytes} bytes</p>
                        {onPlayAudio && (
                          <button
                            onClick={() => onPlayAudio(item.correlationId)}
                            className="px-2 py-1 text-xs bg-cyan-600 hover:bg-cyan-500 rounded transition whitespace-nowrap"
                          >
                            ▶ Play
                          </button>
                        )}
                      </div>
                      <p className="text-xs text-slate-400 mt-2 opacity-60 font-mono">
                        {item.correlationId}
                      </p>
                    </div>
                  </div>
                </div>
              )
            }

            // Handle regular events
            const event = item as PipelineEvent
            return (
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
                    </div>
                    <p className="text-xs text-slate-400 mt-2 opacity-60 font-mono">
                      {event.correlation_id}
                    </p>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
