# Voice Assistant for Termux

A comprehensive voice-controlled AI assistant for Termux on Android devices (Samsung Galaxy A23+).

## Features

### 1. **Communication** 📱
- Read SMS messages
- Read email (with API setup)
- Send SMS by voice
- Check call log
- Voice-based message composition

### 2. **Phone Control** 📲
- Toggle WiFi, Bluetooth
- Adjust brightness, volume
- Battery status & charging control
- Screenshot on command
- App management (requires Shizuku)

### 3. **Automation & Workflows** 🏠
- Multi-step voice macros
- "Leaving home" / "Arriving home" scenarios
- Location-triggered automation
- Time-based scheduling

### 4. **Information & Queries** ℹ️
- Weather reports
- News headlines
- Web search
- System diagnostics
- Real-time stock/crypto (requires API)

### 5. **Productivity** ✅
- Voice note-taking
- Task/todo management
- Reminders and alarms
- Timer management
- Voice-to-text drafting

### 6. **Media & Entertainment** 🎵
- Music playback control
- Podcast support
- Track information
- Focus playlists

### 7. **Smart Home** 💡 (Optional)
- Light control
- Thermostat management
- Scene triggers

### 8. **Developer Tools** ⚙️
- Shell command execution
- Git operations
- SSH connection checks
- System monitoring

## Installation

### Prerequisites
- Termux app (free from Play Store)
- Samsung Galaxy A23+ or compatible Android device
- ~500MB free storage

### Quick Setup

```bash
cd /path/to/Xai
bash setup.sh
```

This will:
- Update Termux packages
- Install Python 3.11+
- Create a virtual environment
- Install dependencies
- Set up command aliases

### Manual Setup

```bash
pkg update && pkg upgrade
pkg install python python-dev ffmpeg espeak git

cd /path/to/Xai
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python voiceassistant.py
```

## Usage

### Interactive Mode
```bash
python voiceassistant.py
```
Then speak or type commands like:
- "read sms"
- "battery status"
- "set timer 5"
- "search python tutorials"
- "add note remember to call mom"

### Single Command
```bash
python voiceassistant.py "weather"
python voiceassistant.py "brightness 100"
```

### With Options
```bash
# Text-only mode (no voice output)
python voiceassistant.py --no-voice

# Local-only mode (no internet features)
python voiceassistant.py --local-only

# Different TTS engine
python voiceassistant.py --voice espeak
```

### Enable Debug Mode
```bash
DEBUG=true python voiceassistant.py
```

## Commands Reference

### Communication
```
read sms              - Read recent SMS messages
send sms <msg>        - Send SMS to number
read email            - Read emails (requires API key)
call log              - Show recent calls
```

### Phone Control
```
wifi [on/off]         - Toggle WiFi
bluetooth             - Toggle Bluetooth
brightness <0-255>    - Set screen brightness
battery               - Show battery status
screenshot            - Take screenshot
```

### Automation
```
leaving home          - Trigger "leaving home" macro
arriving home         - Trigger "arriving home" macro
```

### Information
```
weather               - Current weather
news                  - Latest headlines
search <query>        - Web search
system                - System diagnostics
```

### Productivity
```
note <text>           - Add voice note
read notes            - Display saved notes
timer <minutes>       - Set countdown timer
task <text>           - Add to task list
```

### Media
```
play music            - Open music player
podcast <name>        - Play podcast
now playing           - Show current track
```

### Developer
```
shell <command>       - Run shell command
git                   - Check git status
ssh <host>            - Check SSH connection
```

### System
```
help                  - Show all commands
history               - Show action log
exit                  - Quit assistant
```

## Optional: Termux API Features

For full functionality, install **Termux:API** app (free from Play Store):

```bash
pkg install termux-api
```

This enables:
- ✅ SMS read/send
- ✅ Call logs
- ✅ Battery status
- ✅ Screenshots
- ✅ Camera control
- ✅ Notification reading

## Shizuku Phone Control

NOVA uses Shizuku's `rish` shell bridge for Android commands. Install/configure
`rish` in Termux, authorize Termux in Shizuku, and verify the bridge:

```bash
command -v rish
rish -c 'settings get system screen_brightness'
```

The assistant accepts mapped commands such as `bluetooth on`, `mobile data off`,
`airplane mode on`, and `volume 50`. For another Android shell action, say:
`shizuku settings put system screen_brightness 100`.

Destructive Shizuku commands remain blocked while `CONFIRM_DESTRUCTIVE=true`.

## Configuration

### Optional Gemini Conversation

NOVA can use Gemini for open-ended conversation while keeping phone controls local.

1. Create an API key at `https://aistudio.google.com/apikey`.
2. Copy `.env.example` to `.env`.
3. Set `GEMINI_API_KEY` in `.env`.
4. Run `pip install -r requirements.txt` again after updating the project.

```bash
cp .env.example .env
nano .env
python voiceassistant.py "ask explain quantum computing simply"
```

Use `--local-only` to disable all Gemini/network requests. Never commit or share your API key.

Set environment variables to customize:

```bash
# Enable debug logging
export DEBUG=true

# Disable voice output
export VOICE_ENABLED=false

# Use espeak instead of pyttsx3
export TTS_ENGINE=espeak

# Disable internet features
export LOCAL_ONLY=true

# Run without confirmation for dangerous commands
export CONFIRM_DESTRUCTIVE=false
```

### Config Directory
```
~/.voiceassistant/
├── assistant.log      - Debug logs
├── actions.log        - Action history
├── history.json       - Command history
├── notes.txt          - Saved notes
└── tasks.json         - Task list
```

## Troubleshooting

### "Microphone not found"
- Check Termux has microphone permission
- Grant permission: Settings → Apps → Termux → Permissions → Microphone

### "Speech recognition failed"
- Ensure internet connection (for Google API)
- Or run with `--local-only` for offline mode
- Or install `pocketsphinx` for local STT

### "Termux:API not working"
- Install the **Termux:API** app (separate from Termux)
- Run `termux-api` command to verify
- Grant permission prompts in the API app

### "No audio output"
- Check `VOICE_ENABLED` is not set to `false`
- Try espeak: `python voiceassistant.py --voice espeak`
- Verify system volume is not muted

## Architecture

**Single-file design** for easy mobile deployment:

```
voiceassistant.py (single file, ~1000 lines)
├── VoiceOutput      - Text-to-speech
├── VoiceInput       - Speech recognition
├── CommandParser    - Command routing
├── Modules          - Feature implementations
│   ├── Communication
│   ├── PhoneControl
│   ├── Automation
│   ├── Information
│   ├── Productivity
│   ├── Media
│   ├── SmartHome
│   └── DevTools
└── VoiceAssistant   - Main orchestrator
```

## Privacy & Safety

- ✅ **Local-first**: Processes on-device by default
- ✅ **Confirmation prompts**: Asks before destructive actions
- ✅ **Action logging**: Full audit trail in `~/.voiceassistant/`
- ✅ **No cloud sync**: Data stays on device
- ✅ **Safe mode**: `--local-only` disables all external APIs

## Performance

- **RAM**: ~50-100 MB (with venv)
- **Startup**: <3 seconds
- **Command response**: <1 second (local), <2-3 seconds (network)

## Limitations & Known Issues

1. **Voice recognition** requires internet (Google API)
   - Workaround: Use text input or enable local STT
   
2. **Some Termux:API features** require specific permissions
   - Grant permissions in Termux:API app settings

3. **Smart home** features require device-specific setup
   - Not included out-of-box; requires configuration

4. **Background automation** may require Tasker
   - Voice assistant runs foreground only by default

## Future Enhancements

- [ ] Persistent background daemon
- [ ] Custom wake word recognition
- [ ] Local LLM integration (Ollama)
- [ ] Advanced NLP for multi-step workflows
- [ ] Cloud sync with encryption
- [ ] Mobile app UI (Flutter)

## Contributing

Contributions welcome! Feel free to:
- Add new modules
- Improve voice quality
- Add more commands
- Report bugs

## License

MIT License - Free for personal and commercial use

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Run with `DEBUG=true` for detailed logs
3. Review logs in `~/.voiceassistant/assistant.log`

---

**Made for Termux on Android** 🤖
Optimized for Samsung Galaxy A23+ • Minimal dependencies • Single-file deployment
