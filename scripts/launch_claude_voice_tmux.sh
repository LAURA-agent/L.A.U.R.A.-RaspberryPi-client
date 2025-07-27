#!/bin/bash
# Claude Code Voice-Enabled Terminal Launcher (tmux version)
# This script opens Claude Code in a tmux session for reliable voice injection

SESSION_NAME="claude-voice-$$"
SESSION_INFO="/tmp/claude_voice_session_$$"

# Create session info file
echo "{
  \"pid\": $$,
  \"tmux_session\": \"$SESSION_NAME\",
  \"terminal\": \"tmux\",
  \"created\": $(date +%s)
}" > "$SESSION_INFO"

# Cleanup function
cleanup() {
    rm -f "$SESSION_INFO"
    tmux kill-session -t "$SESSION_NAME" 2>/dev/null
}
trap cleanup EXIT

# Kill any existing claude-voice sessions
tmux list-sessions 2>/dev/null | grep "^claude-voice-" | cut -d: -f1 | xargs -I{} tmux kill-session -t {} 2>/dev/null

# Create new tmux session and run Claude
tmux new-session -d -s "$SESSION_NAME" -n "Claude-Voice"

# Send the startup banner
tmux send-keys -t "$SESSION_NAME" "clear" Enter
tmux send-keys -t "$SESSION_NAME" "echo '=============================================' " Enter
tmux send-keys -t "$SESSION_NAME" "echo '🎙️  CLAUDE CODE - VOICE ENABLED SESSION' " Enter
tmux send-keys -t "$SESSION_NAME" "echo '=============================================' " Enter
tmux send-keys -t "$SESSION_NAME" "echo '• You can type commands normally' " Enter
tmux send-keys -t "$SESSION_NAME" "echo '• Voice commands will appear automatically' " Enter
tmux send-keys -t "$SESSION_NAME" "echo '• Session: $SESSION_NAME' " Enter
tmux send-keys -t "$SESSION_NAME" "echo '=============================================' " Enter
tmux send-keys -t "$SESSION_NAME" "echo '' " Enter

# Start Claude Code
tmux send-keys -t "$SESSION_NAME" "claude" Enter

# Attach to the session
tmux attach-session -t "$SESSION_NAME"