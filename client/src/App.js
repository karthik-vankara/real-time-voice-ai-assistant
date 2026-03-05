import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import { WebSocketClient } from './services/websocket';
import { ConnectionPanel } from './components/ConnectionPanel';
import { AudioRecorder } from './components/AudioRecorder';
import { EventsDisplay } from './components/EventsDisplay';
import { TelemetryDashboard } from './components/TelemetryDashboard';
import { StatusHeader } from './components/StatusHeader';
function App() {
    const [ws, setWs] = useState(null);
    const [isConnected, setIsConnected] = useState(false);
    const [events, setEvents] = useState([]);
    const [metrics, setMetrics] = useState({
        p50_ms: 0,
        p95_ms: 0,
        p99_ms: 0,
    });
    const [activeTab, setActiveTab] = useState('transcript');
    const audioContextRef = useRef(null);
    const ttsChunksRef = useRef(new Map());
    const audioBuffersRef = useRef(new Map());
    const handlePlayAudio = (correlationId) => {
        const audioBuffer = audioBuffersRef.current.get(correlationId);
        if (!audioBuffer) {
            return;
        }
        const audioCtx = audioContextRef.current;
        if (!audioCtx) {
            return;
        }
        try {
            const source = audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioCtx.destination);
            source.start(0);
        }
        catch (error) {
            console.error('Error playing audio:', error);
        }
    };
    useEffect(() => {
        const client = new WebSocketClient('ws://localhost:8000/ws', {
            onConnect: () => {
                setIsConnected(true);
                setEvents([]);
            },
            onDisconnect: () => {
                setIsConnected(false);
            },
            onMessage: (event) => {
                setEvents((prev) => {
                    const updated = [event, ...prev];
                    return updated.slice(0, 100); // Keep last 100 events
                });
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
                    },
                ]);
            },
        });
        setWs(client);
        return () => {
            client.disconnect();
        };
    }, []);
    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                const response = await fetch('http://localhost:8000/telemetry/latency');
                if (response.ok) {
                    const data = await response.json();
                    // Transform backend response to frontend LatencyMetrics format
                    const totalE2E = data.percentiles?.total_e2e || { p50: 0, p95: 0, p99: 0 };
                    const transformed = {
                        p50_ms: totalE2E.p50,
                        p95_ms: totalE2E.p95,
                        p99_ms: totalE2E.p99,
                    };
                    setMetrics(transformed);
                }
            }
            catch (error) {
                // Silently handle telemetry fetch errors
            }
        };
        const interval = setInterval(fetchMetrics, 2000);
        return () => clearInterval(interval);
    }, []);
    // Auto-play TTS audio chunks
    useEffect(() => {
        // Initialize audio context on first render
        if (!audioContextRef.current && typeof AudioContext !== 'undefined') {
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }
        // Process TTS chunks for playback
        for (const event of events) {
            if (event.event_type === 'tts_audio_chunk') {
                const payload = event.payload;
                const audio_b64 = payload.audio_b64;
                const chunk_index = payload.chunk_index ?? 0;
                const is_last = payload.is_last;
                const correlationId = event.correlation_id;
                if (!ttsChunksRef.current.has(correlationId)) {
                    ttsChunksRef.current.set(correlationId, { chunks: new Map(), isComplete: false, maxIndex: 0 });
                }
                const session = ttsChunksRef.current.get(correlationId);
                // Store chunk by index (preserve order, ignore duplicates)
                if (!session.isComplete && audio_b64) {
                    session.chunks.set(chunk_index, audio_b64);
                    session.maxIndex = Math.max(session.maxIndex, chunk_index);
                }
                // When we get the final chunk, decode all accumulated chunks in order
                if (!session.isComplete && is_last) {
                    session.isComplete = true;
                    // Decode and store audio
                    const playAudioChunks = async () => {
                        try {
                            const audioCtx = audioContextRef.current;
                            if (!audioCtx) {
                                console.error('Audio context not initialized');
                                return;
                            }
                            // Reconstruct audio in proper order using chunk indices
                            const allBytes = [];
                            for (let i = 0; i <= session.maxIndex; i++) {
                                const b64 = session.chunks.get(i);
                                if (!b64) {
                                    console.warn(`Missing chunk at index ${i} for correlation ${correlationId}`);
                                    continue;
                                }
                                const binaryString = atob(b64);
                                for (let j = 0; j < binaryString.length; j++) {
                                    allBytes.push(binaryString.charCodeAt(j));
                                }
                            }
                            if (allBytes.length === 0) {
                                console.error('No audio data to decode');
                                return;
                            }
                            // Convert to ArrayBuffer
                            const binaryData = new Uint8Array(allBytes);
                            const arrayBuffer = binaryData.buffer;
                            // Use Web Audio API to decode the audio (handles MP3, AAC, etc.)
                            audioCtx.decodeAudioData(arrayBuffer.slice(0), // Copy to ensure clean buffer
                            (decodedBuffer) => {
                                // Store the decoded AudioBuffer for manual playback
                                audioBuffersRef.current.set(correlationId, decodedBuffer);
                                console.log(`Audio decoded successfully for ${correlationId}: ${session.chunks.size} chunks, ${(arrayBuffer.byteLength / 1024).toFixed(1)}KB`);
                            }, (error) => {
                                console.error(`Error decoding audio for ${correlationId}:`, error);
                            });
                        }
                        catch (error) {
                            console.error('Error processing audio chunks:', error);
                        }
                    };
                    playAudioChunks();
                }
            }
        }
    }, [events]);
    return (_jsxs("div", { className: "min-h-screen bg-slate-900 text-slate-100", children: [_jsx(StatusHeader, { isConnected: isConnected }), _jsx("div", { className: "max-w-7xl mx-auto p-6 space-y-6", children: _jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-6", children: [_jsxs("div", { className: "lg:col-span-1 space-y-4", children: [_jsx(ConnectionPanel, { ws: ws, isConnected: isConnected }), isConnected && _jsx(AudioRecorder, { ws: ws })] }), _jsx("div", { className: "lg:col-span-2", children: isConnected ? (_jsxs(_Fragment, { children: [_jsxs("div", { className: "flex gap-2 mb-4 border-b border-slate-700", children: [_jsxs("button", { onClick: () => setActiveTab('transcript'), className: `px-4 py-2 font-semibold transition ${activeTab === 'transcript'
                                                    ? 'text-blue-400 border-b-2 border-blue-400'
                                                    : 'text-slate-400 hover:text-slate-300'}`, children: ["Transcript & Events (", events.length, ")"] }), _jsx("button", { onClick: () => setActiveTab('metrics'), className: `px-4 py-2 font-semibold transition ${activeTab === 'metrics'
                                                    ? 'text-blue-400 border-b-2 border-blue-400'
                                                    : 'text-slate-400 hover:text-slate-300'}`, children: "Telemetry" })] }), activeTab === 'transcript' ? (_jsx(EventsDisplay, { events: events, onPlayAudio: handlePlayAudio })) : (_jsx(TelemetryDashboard, { metrics: metrics }))] })) : (_jsx("div", { className: "bg-slate-800 border border-slate-700 rounded-lg p-8 text-center", children: _jsx("p", { className: "text-slate-400", children: "Connect to the server first to start testing..." }) })) })] }) })] }));
}
export default App;
