#!/usr/bin/env python
"""Start mock providers and main application for local testing.

Usage:
    python run_local_mock.py

This script:
1. Activates the virtual environment
2. Sets PROVIDER_MODE=mock
3. Starts mock providers on :9000
4. Starts main app on :8000
5. Handles graceful shutdown on Ctrl+C
"""

import os
import subprocess
import sys
import time
import signal


def run():
    """Start services."""
    # Set environment
    os.environ["PROVIDER_MODE"] = "mock"
    
    # Ensure venv is activated
    venv_path = os.path.join(os.getcwd(), ".venv")
    if not os.path.exists(venv_path):
        print("❌ Virtual environment not found at .venv/")
        print("Please create it first: python3 -m venv .venv")
        sys.exit(1)
    
    print("🚀 Starting Real-Time Voice Assistant with Mock Providers")
    print("=" * 60)
    print(f"   Provider Mode: {os.environ['PROVIDER_MODE']}")
    print(f"   Mock Services: http://localhost:9000")
    print(f"   Main App: http://localhost:8000")
    print(f"   WebSocket: ws://localhost:8000/ws")
    print("=" * 60)
    
    # Start mock providers
    print("\n🎭 Starting mock providers on http://localhost:9000...")
    try:
        mock_proc = subprocess.Popen(
            [sys.executable, "-m", "src.mock_providers"],
            env={**os.environ, "PROVIDER_MODE": "mock"},
        )
    except Exception as e:
        print(f"❌ Failed to start mock providers: {e}")
        sys.exit(1)
    
    # Wait for mock providers to start
    time.sleep(2)
    
    # Start main application
    print("🎙️  Starting main application on http://localhost:8000...")
    print("   Health: http://localhost:8000/health")
    print("   Telemetry: http://localhost:8000/telemetry/latency")
    print("\nPress Ctrl+C to stop both services\n")
    
    try:
        app_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "src.server:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
            ],
            env={**os.environ, "PROVIDER_MODE": "mock"},
        )
    except Exception as e:
        print(f"❌ Failed to start main app: {e}")
        mock_proc.terminate()
        sys.exit(1)
    
    # Handle signals
    def shutdown_handler(sig, frame):
        print("\n\n🛑 Shutting down services...")
        mock_proc.terminate()
        app_proc.terminate()
        try:
            mock_proc.wait(timeout=5)
            app_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mock_proc.kill()
            app_proc.kill()
        print("✅ Services stopped")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Wait for both processes
    try:
        mock_proc.wait()
        app_proc.wait()
    except KeyboardInterrupt:
        shutdown_handler(None, None)


if __name__ == "__main__":
    run()
