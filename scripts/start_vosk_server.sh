#!/bin/bash
# Start VOSK WebSocket Server
# This script starts the shared VOSK server that both RP500-Client and Claude Code wrapper can use

cd /home/user/RP500-Client

# Activate virtual environment
source venv/bin/activate

echo "🗣️ Starting VOSK WebSocket Server..."
echo "Using model: $(python3 -c 'from client_config import VOSK_MODEL_PATH; print(VOSK_MODEL_PATH)')"
echo "Server will be available at ws://localhost:8765"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python3 vosk_server.py

echo "VOSK Server stopped."