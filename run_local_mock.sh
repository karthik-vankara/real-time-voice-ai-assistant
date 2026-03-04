#!/bin/bash
# Start both mock providers and main application for local testing
# Usage: ./run_local_mock.sh

set -e

echo "🚀 Starting Real-Time Voice Assistant with Mock Providers"
echo "=============================================="

# Check if venv is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo "⚠️  Activating virtual environment..."
    source .venv/bin/activate
fi

# Set mock mode
export PROVIDER_MODE=mock

# Start mock providers in background
echo "🎭 Starting mock providers on http://localhost:9000..."
python -m src.mock_providers &
MOCK_PID=$!

# Wait for mock providers to start
sleep 2

# Start main application
echo ""
echo "🎙️  Starting main application on http://localhost:8000..."
echo "   WebSocket: ws://localhost:8000/ws"
echo "   Health: http://localhost:8000/health"
echo "   Telemetry: http://localhost:8000/telemetry/latency"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload &
APP_PID=$!

# Handle cleanup on Ctrl+C
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $MOCK_PID $APP_PID 2>/dev/null || true
    wait $MOCK_PID $APP_PID 2>/dev/null || true
    echo "✅ Services stopped"
}

trap cleanup EXIT SIGINT SIGTERM

# Wait for both processes
wait
