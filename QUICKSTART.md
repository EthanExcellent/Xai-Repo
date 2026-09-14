# Quick Start Guide for Voice Assistant on Termux

## 🚀 5-Minute Setup

### Step 1: Copy Files to Phone
```bash
# On your PC, copy project to phone storage:
adb push . /data/data/com.termux/files/home/voiceassistant/

# Or via SSH:
ssh termux@your-phone-ip "mkdir -p ~/voiceassistant"
scp -r . termux@your-phone-ip:~/voiceassistant/
```

### Step 2: Setup on Phone (Termux)
```bash
cd ~/voiceassistant
bash setup.sh
```

This will:
- Install Python packages
- Create virtual environment
- Setup directories
- Create command aliases

### Step 3: First Run
```bash
# Interactive mode
python voiceassistant.py

# Or with alias
va

# Test with a command
python voiceassistant.py "help"
```

---

## 📱 Termux Setup

If you haven't set up Termux yet:

1. **Install Termux** from Google Play Store
2. **Install Termux:API** (separate app) for advanced features
3. **Enable SSH** in Termux:
   ```bash
   pkg install openssh
   sshd
   ```
4. **Allow USB Storage** (Settings → Allow Access to USB Storage)

---

## 🎤 First Commands to Try

```bash
# Get help
python voiceassistant.py "help"

# Check battery
python voiceassistant.py "battery"

# Add a note
python voiceassistant.py "note remember milk"

# System diagnostics
python voiceassistant.py "system"

# Interactive mode (type or speak commands)
python voiceassistant.py
```

---

## 🔧 Configuration

### Environment Variables
```bash
# Enable debug logging
export DEBUG=true

# Use espeak instead of pyttsx3
export TTS_ENGINE=espeak

# Text-only (no voice output)
export VOICE_ENABLED=false

# Disable internet features
export LOCAL_ONLY=true
```

### Config File
Copy and edit `.env.example`:
```bash
cp .env.example .env
nano .env  # Edit as needed
```

---

## 📂 Files Overview

```
voiceassistant.py     ← MAIN FILE (single file, ~1000 lines)
requirements.txt      ← Dependencies
setup.sh              ← Auto-setup script
test.sh               ← Verify installation
.env.example          ← Configuration template
README.md             ← Full documentation
QUICKSTART.md         ← This file
```

---

## ⚙️ Advanced Usage

### Background Daemon
To run 24/7, use a process manager like `pm2` or `screen`:

```bash
# Using screen
screen -S va python voiceassistant.py

# Detach: Ctrl+A then D
# Reattach: screen -r va
```

### Custom Commands
Edit `voiceassistant.py` to add your own commands:

```python
# Find this section:
def _register_commands(self) -> None:
    # Add your custom command:
    self.parser.register("my command", lambda p: print("Hello!"))
```

### Voice Recognition Offline
Install pocketsphinx for offline speech recognition:
```bash
pip install pocketsphinx
python voiceassistant.py --stt pocketsphinx
```

---

## 🐛 Troubleshooting

### "Command not found: python"
Use `python3` instead:
```bash
python3 voiceassistant.py
```

### "ModuleNotFoundError: speech_recognition"
Install requirements:
```bash
pip install -r requirements.txt
```

### "Microphone not working"
1. Grant Termux microphone permission
2. Check phone isn't on mute
3. Try: `python voiceassistant.py --no-voice` (text-only)

### "Termux:API not working"
1. Install the separate "Termux:API" app
2. Run `pkg install termux-api`
3. Grant permissions in the Termux:API app

### Shizuku Controls

Configure Shizuku's `rish` bridge in Termux and authorize Termux in Shizuku:

```bash
command -v rish
rish -c 'settings get system screen_brightness'
```

NOVA can then run commands such as:

```bash
python voiceassistant.py "brightness 100"
python voiceassistant.py "shizuku settings put system screen_brightness 100"
```

Interactive mode also accepts `bluetooth on`, `mobile data off`, and `volume 50`.

### "Can't connect to phone via SSH"
```bash
# Check Termux SSH is running
sshd  # Start it

# Find your phone's IP
ip address  # Look for inet addr

# Test connection
ssh localhost  # From within Termux
```

---

## 🎯 Common Recipes

### Read SMS and Report Aloud
```bash
python voiceassistant.py "read sms"
```

### Set Brightness to 50%
```bash
python voiceassistant.py "brightness 128"
```

### Add Quick Note
```bash
python voiceassistant.py "note call john at 3pm"
```

### Check System Status
```bash
python voiceassistant.py "system"
```

### Search Something
```bash
python voiceassistant.py "search how to make coffee"
```

---

## 💾 Data Locations

All data saved locally in:
```
~/.voiceassistant/
├── assistant.log      # Debug logs
├── actions.log        # Action history
├── history.json       # Command history
├── notes.txt          # Voice notes
└── tasks.json         # Todo list
```

View logs:
```bash
cat ~/.voiceassistant/assistant.log
tail -f ~/.voiceassistant/assistant.log  # Follow in real-time
```

---

## 🚀 Next Steps

1. ✅ Install and run basic commands
2. 📱 Grant Termux:API permissions for SMS/battery
3. 🎤 Configure voice recognition (Google API or offline)
4. 📝 Customize commands to your needs
5. 🤖 Add personal automations

---

## 📚 Full Documentation

See `README.md` for complete feature list and API reference.

Happy voice commanding! 🎉
