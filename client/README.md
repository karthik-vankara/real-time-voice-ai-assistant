# Real-Time Voice Assistant — Client App

A React + Vite test client for the real-time streaming voice assistant.

## Features

- 🎤 **Live Audio Recording**: Capture microphone input and send to server
- 📊 **Real-time Event Stream**: Display ASR/LLM/TTS events as they happen
- 📈 **Telemetry Dashboard**: P50/P95/P99 latency metrics
- 🔌 **WebSocket Connection**: Persistent connection with auto-reconnect
- 🎨 **Modern UI**: Clean, responsive Tailwind CSS design
- ✨ **Dark Mode**: Eye-friendly slate theme

## Getting Started

### Prerequisites

- Node.js 16+ and npm/yarn/pnpm
- Main server running on `http://localhost:8000`

### Installation

```bash
cd client
npm install
```

### Development

```bash
npm run dev
```

Then open http://localhost:5173 in your browser.

### Build

```bash
npm run build
npm run preview
```

## Architecture

```
src/
├── components/          # React UI components
│   ├── StatusHeader.tsx
│   ├── ConnectionPanel.tsx
│   ├── AudioRecorder.tsx
│   ├── EventsDisplay.tsx
│   └── TelemetryDashboard.tsx
├── services/            # Business logic
│   └── websocket.ts    # WebSocket client
├── types.ts            # TypeScript definitions
├── App.tsx             # Main app component
├── main.tsx            # Entry point
└── index.css           # Global styles
```

## Usage

1. **Connect**: Click "Connect" to establish WebSocket connection
2. **Record**: Click "Start Recording" to capture audio from microphone
3. **View Events**: Real-time events appear in "Transcript & Events" tab
4. **Monitor Latency**: Switch to "Telemetry" tab to see P50/P95/P99 metrics
5. **Stop**: Click "Stop Recording" and "Disconnect" when done

## Testing All Features

### 1. Basic Connection
- See "✓ Connected" indicator when connected
- Color changes from red → green with pulse animation

### 2. Audio Recording
- Microphone access is requested on first record
- Recording timer shows elapsed time
- Audio chunks are sent every 100ms

### 3. Event Streaming
- **Speech Started**: First event when recording begins
- **Transcription Provisional**: Interim transcription before final
- **Transcription Final**: Final recognized text
- **LLM Token**: Token-by-token response streaming
- **TTS Audio Chunk**: Audio chunks ready for playback
- **Error**: Any pipeline errors

### 4. Latency Metrics
- P50 (median), P95, P99 percentilities
- Color-coded progress bars (green < 50%, amber < 80%, red > 80%)
- Latency budget breakdown for each stage

### 5. Real-time Updates
- Events appear instantly as they stream
- Last 100 events kept in memory
- Telemetry refreshes every 2 seconds

## Mock vs Real Providers

This client works with both:

- **Mock Providers** (`PROVIDER_MODE=mock`): Perfect for testing without API keys
- **Real Providers** (`PROVIDER_MODE=real`): Production-ready with API keys

Just switch mode in `.env` on the server and restart. Client connects automatically.

## Troubleshooting

**WebSocket Connection Failed**
- Ensure server is running on `localhost:8000`
- Check CORS settings if accessing from different domain

**No Microphone Access**
- Allow microphone access when browser prompts
- Check browser permissions for the site

**No Events Appearing**
- Start recording after connecting
- Check server logs for errors
- Verify mock/real provider is running

**Telemetry Shows 0**
- Telemetry data updates every 2 seconds
- Try making a few requests first

## Components

### StatusHeader
- Connection status indicator
- Title and description

### ConnectionPanel
- Server URL display
- Connect/Disconnect buttons
- Feature list

### AudioRecorder
- Start/Stop recording buttons
- Recording timer
- Microphone instructions

### EventsDisplay
- Color-coded event types
- Event payload text
- Timestamp and correlation ID
- Scrollable event list

### TelemetryDashboard
- Latency metrics cards (P50/P95/P99)
- Latency budget breakdown
- System status checklist

## Performance Tips

- Keep last 100 events to prevent memory bloat
- Telemetry updates every 2 seconds (not on every request)
- Close dev tools if working with large payloads
- Use the mock provider for lightning-fast testing

## License

MIT
