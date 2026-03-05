import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function EventsDisplay({ events, onPlayAudio }) {
    const getEventColor = (eventType) => {
        switch (eventType) {
            case 'speech_started':
                return 'bg-blue-900 border-blue-700';
            case 'transcription_provisional':
                return 'bg-amber-900 border-amber-700';
            case 'transcription_final':
                return 'bg-green-900 border-green-700';
            case 'llm_token':
                return 'bg-purple-900 border-purple-700';
            case 'tts_audio_chunk':
                return 'bg-cyan-900 border-cyan-700';
            case 'error':
                return 'bg-red-900 border-red-700';
            default:
                return 'bg-slate-700 border-slate-600';
        }
    };
    const getEventEmoji = (eventType) => {
        switch (eventType) {
            case 'speech_started':
                return '🔊';
            case 'transcription_provisional':
                return '📝';
            case 'transcription_final':
                return '✅';
            case 'llm_token':
                return '🤖';
            case 'tts_audio_chunk':
                return '🔊';
            case 'error':
                return '❌';
            default:
                return '📌';
        }
    };
    const extractText = (event) => {
        const payload = event.payload;
        // Handle TTS audio chunks - show size instead of base64
        if (event.event_type === 'tts_audio_chunk') {
            const bytes = payload.audio_b64 ? Math.ceil(payload.audio_b64.length * 0.75) : 0;
            const isLast = payload.is_last ? ' (final)' : '';
            return `Audio chunk: ${bytes} bytes${isLast}`;
        }
        if (payload.text)
            return payload.text;
        if (payload.token)
            return payload.token;
        if (payload.accumulated_text)
            return payload.accumulated_text;
        if (payload.message)
            return payload.message;
        return JSON.stringify(payload);
    };
    return (_jsx("div", { className: "bg-slate-800 border border-slate-700 rounded-lg p-6", children: _jsx("div", { className: "max-h-96 overflow-y-auto space-y-3", children: events.length === 0 ? (_jsx("div", { className: "text-center py-12 text-slate-400", children: _jsx("p", { children: "No events yet. Start recording to see real-time events..." }) })) : (events.map((event, idx) => (_jsx("div", { className: `rounded border p-3 fade-in ${getEventColor(event.event_type)}`, children: _jsxs("div", { className: "flex items-start gap-3", children: [_jsx("span", { className: "text-xl", children: getEventEmoji(event.event_type) }), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsxs("div", { className: "flex items-center justify-between gap-2", children: [_jsx("h3", { className: "font-semibold text-sm", children: event.event_type.replace(/_/g, ' ') }), _jsx("span", { className: "text-xs text-slate-300 opacity-70", children: new Date(event.timestamp).toLocaleTimeString() })] }), _jsxs("div", { className: "flex items-center justify-between gap-2 mt-1", children: [_jsx("p", { className: "text-sm break-words whitespace-pre-wrap", children: extractText(event) }), event.event_type === 'tts_audio_chunk' && onPlayAudio && (_jsx("button", { onClick: () => onPlayAudio(event.correlation_id), className: "px-2 py-1 text-xs bg-cyan-600 hover:bg-cyan-500 rounded transition whitespace-nowrap", children: "\u25B6 Play" }))] }), _jsx("p", { className: "text-xs text-slate-400 mt-2 opacity-60 font-mono", children: event.correlation_id })] })] }) }, `${event.correlation_id}-${idx}`)))) }) }));
}
