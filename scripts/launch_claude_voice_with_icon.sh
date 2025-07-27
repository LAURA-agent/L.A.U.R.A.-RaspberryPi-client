#!/bin/bash
# Claude Code Voice Launcher with Custom Window Icon

WINDOW_TITLE="Claude Code - Voice Enabled"

# Launch lxterminal in background with scrollbar and larger buffer
lxterminal -t "$WINDOW_TITLE" --geometry=120x40 -e /home/user/RP500-Client/launch_claude_voice_tmux.sh &
TERMINAL_PID=$!

# Wait for window to appear
sleep 2

# Find and modify the window properties
WINDOW_ID=$(wmctrl -l | grep "$WINDOW_TITLE" | head -1 | awk '{print $1}')

if [ -n "$WINDOW_ID" ]; then
    # Set window class to match our desktop entry
    xprop -id "$WINDOW_ID" -set WM_CLASS "claude-code-voice, Claude-Code-Voice"
    echo "Set window class for Claude Code Voice: $WINDOW_ID"
fi

# Wait for terminal process
wait $TERMINAL_PID