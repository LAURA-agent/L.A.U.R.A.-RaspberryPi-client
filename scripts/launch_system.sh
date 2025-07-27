#!/bin/bash
# System Launcher Script - Launches Claude Code ecosystem
# This script starts all components in the correct order

echo "🚀 Starting LAURA System Components..."
echo "====================================="

# 1. Launch Claude Code
echo "$(date): Launching Claude Code..."
# Launch Claude Code in interactive mode in background
lxterminal -t "Claude Code" -e "bash -c 'claude --mode interactive; read -p \"Claude Code exited. Press Enter to close...\"'" &
CLAUDE_CODE_PID=$!
echo "$(date): Claude Code launched (PID: $CLAUDE_CODE_PID)"

# Wait a moment for Claude Code to initialize
sleep 3

# 2. Launch Claude-to-Speech
echo "$(date): Launching Claude-to-Speech TTS Server..."
lxterminal -t "Claude TTS" -e "bash -c 'cd /home/user/claude-to-speech && source venv/bin/activate && python server/tts_launcher.py; read -p \"TTS Server exited. Press Enter to close...\"'" &
TTS_PID=$!
echo "$(date): Claude-to-Speech launched (PID: $TTS_PID)"

# Wait a moment for TTS to initialize
sleep 3

# 3. Launch Start L.A.U.R.A.
echo "$(date): Launching L.A.U.R.A. Client..."
lxterminal -t "L.A.U.R.A." -e "/home/user/RP500-Client/LAURA" &
LAURA_PID=$!
echo "$(date): L.A.U.R.A. launched (PID: $LAURA_PID)"

echo "====================================="
echo "🟢 All components launched successfully!"
echo "   - Claude Code: PID $CLAUDE_CODE_PID"
echo "   - Claude TTS:  PID $TTS_PID" 
echo "   - L.A.U.R.A.:  PID $LAURA_PID"
echo ""
echo "💡 Usage:"
echo "   - Normal wake words → L.A.U.R.A. server"
echo "   - SHIFT+Left Meta → Claude Code"
echo ""
echo "Press Ctrl+C to exit this launcher (components will continue running)"

# Keep the launcher script running
while true; do
    sleep 10
    # Check if any processes have died and report
    if ! kill -0 $CLAUDE_CODE_PID 2>/dev/null; then
        echo "⚠️  Claude Code process has exited"
        break
    fi
    if ! kill -0 $TTS_PID 2>/dev/null; then
        echo "⚠️  Claude TTS process has exited"
        break
    fi
    if ! kill -0 $LAURA_PID 2>/dev/null; then
        echo "⚠️  L.A.U.R.A. process has exited"
        break
    fi
done

echo "$(date): System launcher exiting..."