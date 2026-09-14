#!/bin/bash
# Voice Assistant Setup Script for Termux

echo "🎤 Voice Assistant Setup for Termux"
echo "===================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Update packages
echo "Updating packages..."
pkg update -y

# Install Python and dependencies
echo "Installing Python and dependencies..."
pkg install -y python ffmpeg espeak git

# Keep the launcher separate from the project directory.
mkdir -p ~/.voiceassistant

# Create virtual environment
echo "Creating virtual environment..."
python -m venv "$PROJECT_DIR/venv"
source "$PROJECT_DIR/venv/bin/activate"

# Install Python packages
echo "Installing Python packages..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install --prefer-binary -r "$PROJECT_DIR/requirements.txt"

echo ""
echo "Gemini support is optional. To install it later, run:"
echo "  python -m pip install --prefer-binary -r $PROJECT_DIR/requirements-gemini.txt"

# Create launcher script
echo "Creating launcher script..."
cat > ~/.voiceassistant/launch.sh << EOF
#!/bin/bash
PROJECT_DIR="$PROJECT_DIR"
source "$PROJECT_DIR/venv/bin/activate"
cd "$PROJECT_DIR"
python voiceassistant.py "\$@"
EOF

chmod +x ~/.voiceassistant/launch.sh

# Optional: Install Termux API
echo ""
echo "📱 Termux API Setup (Optional but Recommended)"
echo "=============================================="
echo "To use SMS, battery, screenshots, and other features:"
echo "1. Install 'Termux:API' app from Google Play Store"
echo "2. Run: pkg install termux-api"
echo "3. Grant permissions when prompted"
echo ""

# Create alias for easy access
echo "Creating shell alias..."
echo 'alias va="~/.voiceassistant/launch.sh"' >> ~/.bashrc
echo 'alias va="~/.voiceassistant/launch.sh"' >> ~/.zshrc

echo ""
echo "✅ Setup complete!"
echo ""
echo "Quick Start:"
echo "  source ~/.voiceassistant/venv/bin/activate"
echo "  python voiceassistant.py"
echo ""
echo "Or use the alias:"
echo "  va"
echo ""
echo "Try: python voiceassistant.py 'help'"
