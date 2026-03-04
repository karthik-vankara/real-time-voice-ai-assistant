import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
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
                console.error('WebSocket error:', error);
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
                    setMetrics(data);
                }
            }
            catch (error) {
                console.error('Failed to fetch metrics:', error);
            }
        };
        const interval = setInterval(fetchMetrics, 2000);
        return () => clearInterval(interval);
    }, []);
    return (_jsxs("div", { className: "min-h-screen bg-slate-900 text-slate-100", children: [_jsx(StatusHeader, { isConnected: isConnected }), _jsx("div", { className: "max-w-7xl mx-auto p-6 space-y-6", children: _jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-6", children: [_jsxs("div", { className: "lg:col-span-1 space-y-4", children: [_jsx(ConnectionPanel, { ws: ws, isConnected: isConnected }), isConnected && _jsx(AudioRecorder, { ws: ws })] }), _jsx("div", { className: "lg:col-span-2", children: isConnected ? (_jsxs(_Fragment, { children: [_jsxs("div", { className: "flex gap-2 mb-4 border-b border-slate-700", children: [_jsxs("button", { onClick: () => setActiveTab('transcript'), className: `px-4 py-2 font-semibold transition ${activeTab === 'transcript'
                                                    ? 'text-blue-400 border-b-2 border-blue-400'
                                                    : 'text-slate-400 hover:text-slate-300'}`, children: ["Transcript & Events (", events.length, ")"] }), _jsx("button", { onClick: () => setActiveTab('metrics'), className: `px-4 py-2 font-semibold transition ${activeTab === 'metrics'
                                                    ? 'text-blue-400 border-b-2 border-blue-400'
                                                    : 'text-slate-400 hover:text-slate-300'}`, children: "Telemetry" })] }), activeTab === 'transcript' ? (_jsx(EventsDisplay, { events: events })) : (_jsx(TelemetryDashboard, { metrics: metrics }))] })) : (_jsx("div", { className: "bg-slate-800 border border-slate-700 rounded-lg p-8 text-center", children: _jsx("p", { className: "text-slate-400", children: "Connect to the server first to start testing..." }) })) })] }) })] }));
}
export default App;
