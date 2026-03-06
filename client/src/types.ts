export interface PipelineEvent {
  event_type:
    | 'speech_started'
    | 'transcription_provisional'
    | 'transcription_final'
    | 'intent_detected'
    | 'web_search_result'
    | 'llm_token'
    | 'tts_audio_chunk'
    | 'error'
  correlation_id: string
  timestamp: string
  schema_version: string
  payload: Record<string, any>
}

export interface LatencyMetrics {
  p50_ms: number
  p95_ms: number
  p99_ms: number
}

export interface TranscriptionEvent extends PipelineEvent {
  event_type: 'transcription_provisional' | 'transcription_final'
  payload: {
    text: string
    is_final: boolean
  }
}

export interface LLMTokenEvent extends PipelineEvent {
  event_type: 'llm_token'
  payload: {
    token: string
    accumulated_text: string
  }
}

export interface TTSAudioChunkEvent extends PipelineEvent {
  event_type: 'tts_audio_chunk'
  payload: {
    audio_b64: string
    chunk_index: number
    is_last: boolean
  }
}

export interface SpeechStartedEvent extends PipelineEvent {
  event_type: 'speech_started'
  payload: Record<string, any>
}

export interface ErrorEvent extends PipelineEvent {
  event_type: 'error'
  payload: {
    error_type: string
    message: string
  }
}

export interface IntentDetectedEvent extends PipelineEvent {
  event_type: 'intent_detected'
  payload: {
    intent: string
    query: string
    requires_search: boolean
  }
}

export interface WebSearchResultEvent extends PipelineEvent {
  event_type: 'web_search_result'
  payload: {
    query: string
    results_summary: string
    source_count: number
  }
}
