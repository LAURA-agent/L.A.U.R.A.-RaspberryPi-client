#!/bin/bash
# Check current autostart configuration

echo "🔍 Current Autostart Configuration"
echo "=================================="

echo ""
echo "📋 Autostart Files:"
ls -la /home/user/.config/autostart/

echo ""
echo "🗣️ VOSK Server Autostart:"
if [ -f "/home/user/.config/autostart/VOSK-Server.desktop" ]; then
    echo "✅ VOSK-Server.desktop exists"
    echo "Content:"
    cat /home/user/.config/autostart/VOSK-Server.desktop
else
    echo "❌ VOSK-Server.desktop missing"
fi

echo ""
echo "🤖 LAURA Client Autostart:"
if [ -f "/home/user/.config/autostart/LAURA.desktop" ]; then
    echo "✅ LAURA.desktop exists"
    echo "Content:"
    cat /home/user/.config/autostart/LAURA.desktop
else
    echo "❌ LAURA.desktop missing"
fi

echo ""
echo "🏃 Running Processes:"
echo "VOSK Server:"
pgrep -f "vosk_server.py" && echo "✅ VOSK server running" || echo "❌ VOSK server not running"

echo "LAURA Client:"
pgrep -f "run_v2.py" && echo "✅ LAURA client running" || echo "❌ LAURA client not running"

echo ""
echo "📊 Boot Sequence Order:"
echo "1. System boot"
echo "2. Desktop login"
echo "3. VOSK Server starts (5 sec delay)"
echo "4. LAURA starts (waits for WiFi, then checks VOSK)"
echo "5. Both running independently"