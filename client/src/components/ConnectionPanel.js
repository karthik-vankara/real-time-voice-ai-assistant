import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function ConnectionPanel({ ws, isConnected }) {
    const handleConnect = async () => {
        if (!ws)
            return;
        try {
            await ws.connect();
        }
        catch (error) {
            console.error('Connection failed:', error);
        }
    };
    const handleDisconnect = () => {
        if (ws) {
            ws.disconnect();
        }
    };
    return (_jsxs("div", { className: "bg-slate-800 border border-slate-700 rounded-lg p-6", children: [_jsx("h2", { className: "text-lg font-semibold mb-4", children: "Connection" }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "text-sm text-slate-400", children: "Server URL" }), _jsx("p", { className: "text-sm font-mono bg-slate-900 p-2 rounded mt-1", children: "ws://localhost:8000/ws" })] }), _jsxs("div", { className: "flex gap-2", children: [_jsx("button", { onClick: handleConnect, disabled: isConnected, className: `flex-1 px-4 py-2 rounded font-medium transition ${isConnected
                                    ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                                    : 'bg-blue-600 hover:bg-blue-700 text-white'}`, children: isConnected ? '✓ Connected' : 'Connect' }), _jsx("button", { onClick: handleDisconnect, disabled: !isConnected, className: `flex-1 px-4 py-2 rounded font-medium transition ${!isConnected
                                    ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                                    : 'bg-red-600 hover:bg-red-700 text-white'}`, children: "Disconnect" })] })] }), _jsxs("div", { className: "mt-6 pt-6 border-t border-slate-700", children: [_jsx("h3", { className: "text-sm font-semibold mb-3", children: "Features" }), _jsxs("ul", { className: "text-xs text-slate-400 space-y-2", children: [_jsx("li", { children: "\u2713 Real-time WebSocket streaming" }), _jsx("li", { children: "\u2713 Audio input recording" }), _jsx("li", { children: "\u2713 Live event display" }), _jsx("li", { children: "\u2713 Latency telemetry (P50/P95/P99)" }), _jsx("li", { children: "\u2713 Barge-in support" }), _jsx("li", { children: "\u2713 Error handling & fallbacks" })] })] })] }));
}
