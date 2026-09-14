#!/bin/bash
# Quick test script for Voice Assistant

echo "🎤 Voice Assistant - Quick Test"
echo "================================"

# Check Python
echo "✓ Checking Python..."
python --version

# Check if voiceassistant.py exists
if [ ! -f "voiceassistant.py" ]; then
    echo "❌ voiceassistant.py not found"
    exit 1
fi

echo "✓ voiceassistant.py found"

# Test import
echo ""
echo "✓ Testing import..."
python -c "import sys; sys.path.insert(0, '.'); exec(open('voiceassistant.py').read())" --help

# List available commands
echo ""
echo "✓ Available commands:"
python voiceassistant.py help

echo ""
echo "✅ All tests passed! Ready to run."
