#!/bin/bash
# Claude Code Voice-Enabled Terminal Launcher
# This script opens Claude Code in a visible terminal that can receive voice commands

echo "🚀 Launching Claude Code in voice-enabled terminal..."

# Create a named pipe for voice command injection
VOICE_PIPE="/tmp/claude_voice_pipe_$$"
mkfifo "$VOICE_PIPE"

# Create session info file for session manager to detect
SESSION_INFO="/tmp/claude_voice_session_$$"
echo "{
  \"pid\": $$,
  \"voice_pipe\": \"$VOICE_PIPE\",
  \"terminal\": \"visible\",
  \"created\": $(date +%s)
}" > "$SESSION_INFO"

# Function to cleanup on exit
cleanup() {
    rm -f "$VOICE_PIPE" "$SESSION_INFO"
    echo -e "\n👋 Claude Code voice session ended."
}
trap cleanup EXIT

# Start Claude Code with a custom title and indicator
echo "============================================="
echo "🎙️  CLAUDE CODE - VOICE ENABLED SESSION"
echo "============================================="
echo "• You can type commands normally"
echo "• Voice commands will appear automatically"
echo "• Press Ctrl+D or type 'exit' to quit"
echo "============================================="
echo ""

# Launch Claude Code in current terminal
# This allows both direct typing and voice command injection
claude

# Cleanup will happen automatically via trap