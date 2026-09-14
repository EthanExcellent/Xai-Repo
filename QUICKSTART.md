# Quick Start Guide for Voice Assistant on Termux

## Setup

Install Termux from F-Droid or GitHub releases. The Google Play build may be
outdated. Copy the project to the phone, then run:

```bash
cd ~/voiceassistant
bash setup.sh
```

The setup script installs Python, creates a virtual environment, and installs
the supported Python dependencies. It avoids mandatory native packages so the
initial install works on Android ARM.

## Run

```bash
source venv/bin/activate
python voiceassistant.py "help"
python voiceassistant.py --no-voice "battery"
python voiceassistant.py
```

## Optional Termux API

Install the separate Termux:API app, then run:

```bash
pkg install termux-api
```

Grant microphone and Termux:API permissions when Android asks. These are
needed for microphone input, SMS, battery status, screenshots, and related
phone features.

## Configuration

```bash
export VOICE_ENABLED=false
export LOCAL_ONLY=true
export DEBUG=true
```

Use `--no-voice` for text-only operation. Use `--local-only` to disable
internet-dependent commands.

Gemini is optional. Install it separately only if you need open-ended AI
answers:

```bash
python -m pip install --prefer-binary -r requirements-gemini.txt
export GEMINI_API_KEY=your_key_here
```

## Offline Speech Recognition

Pocketsphinx is optional because it may require a native build on Android ARM.
Install it only after the assistant itself is working:

```bash
python -m pip install --prefer-binary pocketsphinx
python voiceassistant.py --stt pocketsphinx
```

## Shizuku

Configure Shizuku and the `rish` bridge separately if you want privileged
Android shell commands:

```bash
command -v rish
rish -c 'settings get system screen_brightness'
python voiceassistant.py "shizuku settings put system screen_brightness 100"
```

## Troubleshooting

If setup appears stuck, stop it with `Ctrl+C`, update Termux packages, remove
the incomplete virtual environment, and retry:

```bash
pkg update -y
pkg upgrade -y
rm -rf ~/voiceassistant/venv
cd ~/voiceassistant
bash setup.sh
```

Check the installation with:

```bash
bash test.sh
```
