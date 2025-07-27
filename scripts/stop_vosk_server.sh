#!/bin/bash
# Stop VOSK WebSocket Server
# This script cleanly shuts down the VOSK server

cd /home/user/RP500-Client

PID_FILE="logs/vosk_server.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    
    if kill -0 "$PID" 2>/dev/null; then
        echo "🛑 Stopping VOSK Server (PID: $PID)..."
        
        # Try graceful shutdown first
        kill -TERM "$PID"
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 "$PID" 2>/dev/null; then
                echo "✅ VOSK Server stopped gracefully"
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 1
        done
        
        # Force kill if still running
        echo "⚠️ Forcing VOSK Server shutdown..."
        kill -KILL "$PID" 2>/dev/null
        rm -f "$PID_FILE"
        echo "✅ VOSK Server forcefully stopped"
    else
        echo "⚠️ VOSK Server PID $PID not found (already stopped?)"
        rm -f "$PID_FILE"
    fi
else
    # Try to find VOSK server process by name
    VOSK_PID=$(pgrep -f "python3.*vosk_server.py")
    
    if [ -n "$VOSK_PID" ]; then
        echo "🛑 Found VOSK Server process (PID: $VOSK_PID), stopping..."
        kill -TERM "$VOSK_PID"
        sleep 2
        
        if kill -0 "$VOSK_PID" 2>/dev/null; then
            kill -KILL "$VOSK_PID"
            echo "✅ VOSK Server forcefully stopped"
        else
            echo "✅ VOSK Server stopped"
        fi
    else
        echo "ℹ️ No VOSK Server process found"
    fi
fi

# Clean up any stale websocket connections
echo "🧹 Cleaning up..."
pkill -f "python3.*vosk_websocket_client.py" 2>/dev/null || true

echo "✅ VOSK Server cleanup complete"