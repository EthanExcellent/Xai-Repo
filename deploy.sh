#!/bin/bash
# Copy Voice Assistant to Termux phone storage
# Run this on your Linux desktop/laptop to send the project to phone

PHONE_IP="${1:-192.168.1.100}"
TERMUX_USER="u0_a123"  # Change this to your Android UID
TERMUX_PATH="/data/data/com.termux/files/home/voiceassistant"

echo "🚀 Copying Voice Assistant to Termux on $PHONE_IP"

# Using adb (Android Debug Bridge)
if command -v adb &> /dev/null; then
    echo "Using ADB..."
    adb push . "$TERMUX_PATH/"
    adb shell "cd $TERMUX_PATH && bash setup.sh"
else
    echo "ADB not found. Using SSH instead..."
    ssh termux@"$PHONE_IP" "mkdir -p ~/voiceassistant"
    scp -r . termux@"$PHONE_IP":~/voiceassistant/
    ssh termux@"$PHONE_IP" "cd ~/voiceassistant && bash setup.sh"
fi

echo "✅ Done! SSH into your phone and run:"
echo "   cd ~/voiceassistant"
echo "   source venv/bin/activate"
echo "   python voiceassistant.py"
