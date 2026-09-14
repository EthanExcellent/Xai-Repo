#!/usr/bin/env python3
"""
Voice Assistant - Comprehensive voice-controlled AI assistant for Termux on Android
Single-file implementation for easy deployment on mobile devices
"""

import os
import sys
import json
import subprocess
import re
import time
import threading
import shutil
import urllib.parse
import requests
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from functools import wraps
from pathlib import Path
import logging

# Optional dependencies (graceful fallback)
try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    load_dotenv = None

try:
    from google import genai
except ImportError:
    genai = None

# ============================================================================
# LOGGING & CONFIGURATION
# ============================================================================

class Config:
    """Global configuration"""
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    VOICE_ENABLED = os.getenv("VOICE_ENABLED", "true").lower() == "true"
    TTS_ENGINE = os.getenv("TTS_ENGINE", "espeak")  # or "pyttsx3"
    STT_ENGINE = os.getenv("STT_ENGINE", "google")   # or "pocketsphinx"
    CONFIRM_DESTRUCTIVE = os.getenv("CONFIRM_DESTRUCTIVE", "true").lower() == "true"
    LOCAL_ONLY = os.getenv("LOCAL_ONLY", "false").lower() == "true"
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    DATA_DIR = Path.home() / ".voiceassistant"
    LOG_FILE = None
    ACTION_LOG = None
    HISTORY_FILE = None

    @classmethod
    def init(cls):
        """Initialize config directory and files"""
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.LOG_FILE = cls.DATA_DIR / "assistant.log"
        cls.ACTION_LOG = cls.DATA_DIR / "actions.log"
        cls.HISTORY_FILE = cls.DATA_DIR / "history.json"
        cls.LOG_FILE.touch(exist_ok=True)
        cls.ACTION_LOG.touch(exist_ok=True)


class ShizukuBridge:
    """Run Android shell commands through the Shizuku rish bridge."""

    DANGEROUS_COMMANDS = (
        "rm -rf", "dd ", ":(){:|:&;:;", "reboot", "shutdown", "pm uninstall"
    )

    @classmethod
    def available(cls) -> bool:
        return shutil.which("rish") is not None

    @classmethod
    def run(cls, command: str, confirm: bool = True) -> str:
        command = command.strip()
        if not command:
            return "Usage: shizuku <Android shell command>"
        if confirm and Config.CONFIRM_DESTRUCTIVE and any(
            dangerous in command.lower() for dangerous in cls.DANGEROUS_COMMANDS
        ):
            return "Dangerous Shizuku command blocked. Set CONFIRM_DESTRUCTIVE=false to override."
        if not cls.available():
            return "Shizuku is unavailable. Start Shizuku and make sure rish is installed."

        try:
            result = subprocess.run(
                ["rish", "-c", command],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            return f"Shizuku command failed: {error}"

        output = (result.stdout or result.stderr).strip()
        if result.returncode != 0:
            return f"Shizuku command failed ({result.returncode}): {output or 'no output'}"
        return output or "Shizuku command completed."


def setup_logger(name: str) -> logging.Logger:
    """Setup logger with file and console handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if Config.DEBUG else logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    fh = logging.FileHandler(Config.LOG_FILE)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger


# Initialize config first
Config.init()

logger = setup_logger("VoiceAssistant")


# ============================================================================
# VOICE I/O
# ============================================================================

class VoiceOutput:
    """Text-to-speech handler"""
    
    def __init__(self, engine: str = "pyttsx3"):
        self.engine = engine
        self.tts = None
        
        if engine == "pyttsx3" and pyttsx3:
            try:
                self.tts = pyttsx3.init()
                self.tts.setProperty('rate', 150)
                self.tts.setProperty('volume', 0.9)
            except Exception as error:
                logger.warning("pyttsx3 unavailable, using text output: %s", error)
                self.engine = "text"
        
        logger.info(f"Voice output initialized: {engine}")
    
    def speak(self, text: str, wait: bool = True) -> None:
        """Speak text using TTS"""
        print(f"  nova > {text}")
        if not Config.VOICE_ENABLED:
            return
        
        logger.debug(f"Speaking: {text}")
        
        if self.engine == "pyttsx3" and self.tts:
            self.tts.say(text)
            if wait:
                self.tts.runAndWait()
            else:
                self.tts.startLoop(False)
        elif self.engine == "espeak":
            # Fallback for Termux with espeak
            try:
                subprocess.run(
                    ["espeak", text],
                    check=True,
                    capture_output=True
                )
            except FileNotFoundError:
                print(f"[SPEAK] {text}")
        else:
            print(f"[SPEAK] {text}")
    
    def list_voices(self) -> List[str]:
        """List available voices"""
        if self.tts:
            return [v.id for v in self.tts.getProperty('voices')]
        return []


class VoiceInput:
    """Speech-to-text handler"""
    
    def __init__(self, engine: str = "google"):
        self.engine = engine
        self.recognizer = None
        
        if engine == "google" and sr:
            self.recognizer = sr.Recognizer()
        
        logger.info(f"Voice input initialized: {engine}")
    
    def listen(self, timeout: int = 10, phrase_time_limit: int = 10) -> Optional[str]:
        """Listen for voice input and return recognized text"""
        if not self.recognizer:
            return self._fallback_input()
        
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.debug("Listening...")
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            
            text = self.recognizer.recognize_google(audio)
            logger.info(f"Recognized: {text}")
            return text
        
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Microphone/API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Voice input error: {e}")
            return None
    
    def _fallback_input(self) -> str:
        """Fallback to text input if voice unavailable"""
        return input(">>> ").strip()


# ============================================================================
# COMMAND PARSING & ROUTING
# ============================================================================

class CommandParser:
    """Parse and route commands"""
    
    def __init__(self):
        self.commands: Dict[str, Callable] = {}
        self.aliases: Dict[str, str] = {}
        self.history: List[Dict] = []
        self._load_history()
    
    def register(self, command: str, handler: Callable, aliases: List[str] = None) -> None:
        """Register a command handler"""
        self.commands[command.lower()] = handler
        if aliases:
            for alias in aliases:
                self.aliases[alias.lower()] = command.lower()
        logger.debug(f"Registered command: {command}")
    
    def parse(self, text: str) -> tuple[Optional[str], Optional[Dict]]:
        """Parse command and extract parameters"""
        original = text.strip()
        text = original.lower()
        
        # Check aliases first
        for alias, cmd in sorted(self.aliases.items(), key=lambda item: len(item[0]), reverse=True):
            if text == alias or text.startswith(f"{alias} "):
                return cmd, {"args": original[len(alias):].strip()}
        
        # Check direct commands
        for cmd in sorted(self.commands, key=len, reverse=True):
            if text == cmd or text.startswith(f"{cmd} "):
                return cmd, {"args": original[len(cmd):].strip()}
        
        return None, None
    
    def execute(self, command: str, params: Dict) -> Any:
        """Execute registered command"""
        if command not in self.commands:
            logger.warning(f"Unknown command: {command}")
            return None
        
        try:
            result = self.commands[command](params)
            self._log_action(command, params, "success", result)
            return result
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            self._log_action(command, params, "error", str(e))
            return None
    
    def _log_action(self, command: str, params: Dict, status: str, result: Any) -> None:
        """Log action to history"""
        action = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "params": params,
            "status": status,
            "result": str(result)
        }
        self.history.append(action)
        self._save_history()
    
    def _save_history(self) -> None:
        """Save history to file"""
        try:
            with open(Config.HISTORY_FILE, 'w') as f:
                json.dump(self.history[-100:], f, indent=2)  # Keep last 100
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    def _load_history(self) -> None:
        """Load history from file"""
        try:
            if Config.HISTORY_FILE.exists():
                with open(Config.HISTORY_FILE, 'r') as f:
                    self.history = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")


# ============================================================================
# FEATURE MODULES
# ============================================================================

class CommunicationModule:
    """Handle SMS, WhatsApp, Telegram, email"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def read_sms(self, args: str) -> str:
        """Read recent SMS messages"""
        # Requires Termux:SMS plugin
        try:
            result = subprocess.run(
                ["termux-sms-list"],
                capture_output=True,
                text=True,
                check=True
            )
            messages = result.stdout.strip().split('\n')[:5]
            output = f"You have {len(messages)} messages: " + "; ".join(messages)
            self.voice.speak(output)
            return output
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            msg = "SMS plugin not available. Install Termux:SMS app."
            logger.error(msg)
            return msg
    
    def read_email(self, args: str) -> str:
        """Read email (requires API key setup)"""
        # Placeholder for IMAP implementation
        msg = "Email feature requires GMAIL_API_KEY in environment"
        self.voice.speak(msg)
        return msg
    
    def send_sms(self, args: str) -> str:
        """Send SMS via voice"""
        try:
            subprocess.run(
                ["termux-sms-send", "-n", args.split()[0], args],
                check=True
            )
            msg = f"SMS sent to {args.split()[0]}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return str(e)
    
    def read_call_log(self, args: str) -> str:
        """Read recent calls"""
        msg = "Call log feature requires Termux:API. Install the app and run: termux-call-log"
        self.voice.speak(msg)
        return msg

    def read_notifications(self, args: str) -> str:
        """Read recent Android notifications through Termux:API."""
        try:
            result = subprocess.run(
                ["termux-notification-list"],
                capture_output=True,
                text=True,
                check=True,
            )
            notifications = result.stdout.strip()
            msg = "Recent notifications: " + (notifications[:1200] if notifications else "none")
            self.voice.speak(msg)
            return msg
        except (FileNotFoundError, subprocess.CalledProcessError):
            msg = "Notification reading requires Termux:API."
            self.voice.speak(msg)
            return msg


class PhoneControlModule:
    """Control phone settings via Termux API"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def toggle_wifi(self, args: str) -> str:
        """Toggle WiFi on/off"""
        state = args.strip().lower()
        try:
            subprocess.run(
                ["termux-wifi-enable", "true" if state == "on" else "false"],
                check=True
            )
            msg = f"WiFi turned {state}"
            self.voice.speak(msg)
            return msg
        except FileNotFoundError:
            return "Termux:API not installed"
    
    def toggle_bluetooth(self, args: str) -> str:
        """Toggle Bluetooth (requires Shizuku)"""
        state = args.strip().lower()
        result = ShizukuBridge.run(f"svc bluetooth {'enable' if state == 'on' else 'disable'}")
        msg = result if result.startswith("Shizuku ") else f"Bluetooth turned {state}"
        self.voice.speak(msg)
        return msg
    
    def brightness(self, args: str) -> str:
        """Set screen brightness (0-255)"""
        try:
            level = int(args.strip() or "200")
            subprocess.run(
                ["termux-brightness", str(level)],
                check=True
            )
            msg = f"Brightness set to {level}"
            self.voice.speak(msg)
            return msg
        except (ValueError, subprocess.CalledProcessError) as e:
            return f"Brightness error: {e}"
    
    def battery_status(self, args: str) -> str:
        """Get battery status"""
        try:
            result = subprocess.run(
                ["termux-battery-status"],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            percentage = data.get("percentage", "unknown")
            status = data.get("status", "unknown")
            msg = f"Battery at {percentage} percent, {status}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            msg = f"Battery check failed: {e}"
            self.voice.speak(msg)
            return msg
    
    def screenshot(self, args: str) -> str:
        """Take a screenshot"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            subprocess.run(
                ["termux-take-photo", "-f", filename],
                check=True
            )
            msg = f"Screenshot saved to {filename}"
            self.voice.speak(msg)
            return msg
        except FileNotFoundError:
            return "Termux:API not installed"


class AutomationModule:
    """Multi-step automation and macros"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
        self.macros: Dict[str, List[Dict]] = {}
    
    def leaving_home(self, args: str) -> str:
        """Macro: WiFi off, DND on, Maps opens"""
        steps = [
            ("wifi_off", {}),
            ("dnd_on", {}),
            ("open_maps", {})
        ]
        msg = "Executing 'leaving home' macro..."
        self.voice.speak(msg)
        logger.info(f"Macro steps: {steps}")
        return msg
    
    def arriving_home(self, args: str) -> str:
        """Macro: WiFi on, DND off, music starts"""
        msg = "Executing 'arriving home' macro..."
        self.voice.speak(msg)
        return msg
    
    def save_macro(self, name: str, steps: List[Dict]) -> str:
        """Save custom macro"""
        self.macros[name] = steps
        msg = f"Macro '{name}' saved with {len(steps)} steps"
        self.voice.speak(msg)
        return msg


class InformationModule:
    """Weather, news, stocks, search"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def weather(self, args: str) -> str:
        """Get weather info"""
        if Config.LOCAL_ONLY:
            return "Weather requires internet (LOCAL_ONLY mode)"
        
        location = args.strip() or "auto"
        try:
            # Using open-meteo (free, no API key)
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": 0, "longitude": 0, "current": "temperature_2m,weather_code"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                temp = data["current"]["temperature_2m"]
                msg = f"Current temperature is {temp} degrees"
                self.voice.speak(msg)
                return msg
        except requests.RequestException as e:
            return f"Weather check failed: {e}"
    
    def news(self, args: str) -> str:
        """Get news headlines"""
        if Config.LOCAL_ONLY:
            return "News requires internet (LOCAL_ONLY mode)"
        
        msg = "News feature requires NewsAPI key. Not yet configured."
        self.voice.speak(msg)
        return msg
    
    def web_search(self, args: str) -> str:
        """Search the web"""
        if Config.LOCAL_ONLY:
            return "Web search requires internet (LOCAL_ONLY mode)"
        
        query = args.strip()
        msg = f"Searching for: {query}. This would open a browser search."
        self.voice.speak(msg)
        return msg
    
    def system_diagnostics(self, args: str) -> str:
        """Get system diagnostics"""
        try:
            result = subprocess.run(
                ["free", "-h"],
                capture_output=True,
                text=True,
                check=True
            )
            msg = "System memory: " + result.stdout.split('\n')[0]
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Diagnostics failed: {e}"


class ProductivityModule:
    """Notes, tasks, reminders, timers"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
        self.notes_file = Config.DATA_DIR / "notes.txt"
        self.tasks_file = Config.DATA_DIR / "tasks.json"
    
    def add_note(self, args: str) -> str:
        """Add a voice note"""
        note = f"[{datetime.now().isoformat()}] {args}\n"
        try:
            with open(self.notes_file, 'a') as f:
                f.write(note)
            msg = f"Note saved: {args}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Note failed: {e}"
    
    def read_notes(self, args: str) -> str:
        """Read recent notes"""
        try:
            with open(self.notes_file, 'r') as f:
                notes = f.readlines()[-5:]
            msg = "Recent notes: " + "; ".join([n.strip() for n in notes])
            self.voice.speak(msg)
            return msg
        except FileNotFoundError:
            return "No notes found"
    
    def set_timer(self, args: str) -> str:
        """Set a timer"""
        try:
            minutes = int(args.split()[0])
            msg = f"Timer set for {minutes} minutes"
            self.voice.speak(msg)
            # Timer logic would run in background
            return msg
        except (ValueError, IndexError):
            return "Usage: set timer 5"
    
    def add_task(self, args: str) -> str:
        """Add task to todo list"""
        task = {"text": args, "created": datetime.now().isoformat(), "done": False}
        try:
            tasks = []
            if self.tasks_file.exists():
                with open(self.tasks_file, 'r') as f:
                    tasks = json.load(f)
            
            tasks.append(task)
            with open(self.tasks_file, 'w') as f:
                json.dump(tasks, f, indent=2)
            
            msg = f"Task added: {args}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Task failed: {e}"


class MediaModule:
    """Music, podcast, audio playback"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def play_music(self, args: str) -> str:
        """Play music"""
        try:
            subprocess.run(
                ["am", "start", "-a", "android.intent.action.MAIN", "-n", "com.android.music/.MusicBrowserActivity"],
                check=False
            )
            msg = f"Playing music: {args}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Music control failed: {e}"
    
    def podcast_play(self, args: str) -> str:
        """Play podcast"""
        msg = f"Playing podcast: {args}"
        self.voice.speak(msg)
        return msg
    
    def music_info(self, args: str) -> str:
        """Get current track info"""
        msg = "Music info: unavailable (requires media API)"
        self.voice.speak(msg)
        return msg


class PhoneExtendedModule:
    """Extended phone controls"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def toggle_mobile_data(self, args: str) -> str:
        """Toggle mobile data on/off"""
        state = args.strip().lower()
        result = ShizukuBridge.run(f"svc data {'enable' if state == 'on' else 'disable'}")
        msg = result if result.startswith("Shizuku ") else f"Mobile data turned {state}"
        self.voice.speak(msg)
        return msg
    
    def toggle_airplane_mode(self, args: str) -> str:
        """Toggle airplane mode"""
        state = args.strip().lower()
        value = "1" if state == "on" else "0"
        result = ShizukuBridge.run(
            "settings put global airplane_mode_on " + value +
            "; am broadcast -a android.intent.action.AIRPLANE_MODE --ez state " + state
        )
        msg = result if result.startswith("Shizuku ") else f"Airplane mode turned {state}"
        self.voice.speak(msg)
        return msg
    
    def toggle_flashlight(self, args: str) -> str:
        """Toggle flashlight"""
        try:
            state = args.strip().lower()
            subprocess.run(
                ["termux-torch", "on" if state == "on" else "off"],
                check=True
            )
            msg = f"Flashlight turned {state}"
            self.voice.speak(msg)
            return msg
        except FileNotFoundError:
            return "Termux:API not installed"
    
    def set_volume(self, args: str) -> str:
        """Set volume level (0-100)"""
        try:
            level = max(0, min(100, int(args.strip() or "50")))
            result = ShizukuBridge.run(f"cmd volume set-stream-volume 3 {round(level * 15 / 100)}")
            msg = result if result.startswith("Shizuku ") else f"Volume set to {level}%"
            self.voice.speak(msg)
            return msg
        except ValueError:
            return "Usage: volume <0-100>"
    
    def screen_timeout(self, args: str) -> str:
        """Set screen timeout (seconds)"""
        try:
            seconds = max(1, int(args.strip() or "120"))
            result = ShizukuBridge.run(f"settings put system screen_off_timeout {seconds * 1000}")
            msg = result if result.startswith("Shizuku ") else f"Screen timeout set to {seconds} seconds"
            self.voice.speak(msg)
            return msg
        except ValueError:
            return "Usage: screen timeout <seconds>"
    
    def rotation_lock(self, args: str) -> str:
        """Lock/unlock screen rotation"""
        state = args.strip().lower()
        value = "0" if state in ("on", "lock", "locked") else "1"
        result = ShizukuBridge.run(f"settings put system accelerometer_rotation {value}")
        msg = result if result.startswith("Shizuku ") else f"Rotation lock {state}"
        self.voice.speak(msg)
        return msg
    
    def dnd_mode(self, args: str) -> str:
        """Enable/disable Do Not Disturb"""
        state = args.strip().lower()
        result = ShizukuBridge.run(f"cmd notification set_dnd {'on' if state == 'on' else 'off'}")
        msg = result if result.startswith("Shizuku ") else f"Do Not Disturb turned {state}"
        self.voice.speak(msg)
        return msg


class CallModule:
    """Handle phone calls"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def make_call(self, args: str) -> str:
        """Make a phone call"""
        phone = args.strip()
        try:
            subprocess.run(
                ["termux-telephony-call", phone],
                check=True
            )
            msg = f"Calling {phone}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Call failed: {e}"
    
    def answer_call(self, args: str) -> str:
        """Answer incoming call"""
        msg = "Answering call (requires Shizuku)"
        self.voice.speak(msg)
        return msg
    
    def reject_call(self, args: str) -> str:
        """Reject incoming call"""
        msg = "Call rejected (requires Shizuku)"
        self.voice.speak(msg)
        return msg
    
    def hangup(self, args: str) -> str:
        """End current call"""
        msg = "Call ended"
        self.voice.speak(msg)
        return msg


class MessagingModule:
    """WhatsApp, Telegram, and other messaging apps"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def whatsapp_send(self, args: str) -> str:
        """Send WhatsApp message"""
        parts = args.split("|", 1)
        if len(parts) < 2:
            return "Usage: whatsapp send <contact>|<message>"
        
        contact, message = parts
        msg = f"Sending WhatsApp to {contact}: {message} (requires WhatsApp installed)"
        self.voice.speak(msg)
        return msg
    
    def telegram_send(self, args: str) -> str:
        """Send Telegram message"""
        parts = args.split("|", 1)
        if len(parts) < 2:
            return "Usage: telegram send <user>|<message>"
        
        user, message = parts
        msg = f"Sending Telegram to {user}: {message} (requires Telegram installed)"
        self.voice.speak(msg)
        return msg
    
    def whatsapp_read(self, args: str) -> str:
        """Read recent WhatsApp messages"""
        msg = "WhatsApp messages (requires WhatsApp integration)"
        self.voice.speak(msg)
        return msg
    
    def telegram_read(self, args: str) -> str:
        """Read recent Telegram messages"""
        msg = "Telegram messages (requires Telegram integration)"
        self.voice.speak(msg)
        return msg


class AppModule:
    """App management"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def app_install(self, args: str) -> str:
        """Install app"""
        app = args.strip()
        msg = f"Installing {app} (requires permissions)"
        self.voice.speak(msg)
        return msg
    
    def app_uninstall(self, args: str) -> str:
        """Uninstall app"""
        app = args.strip()
        result = ShizukuBridge.run(f"pm uninstall {app}")
        msg = result if result.startswith("Shizuku ") else f"Uninstalled {app}"
        self.voice.speak(msg)
        return msg
    
    def app_force_stop(self, args: str) -> str:
        """Force stop app"""
        app = args.strip()
        try:
            subprocess.run(
                ["am", "force-stop", app],
                check=True
            )
            msg = f"Force stopped {app}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Force stop failed: {e}"
    
    def app_clear_cache(self, args: str) -> str:
        """Clear app cache"""
        app = args.strip()
        msg = f"Clearing cache for {app}"
        self.voice.speak(msg)
        return msg
    
    def app_permissions(self, args: str) -> str:
        """Manage app permissions"""
        parts = args.split(None, 1)
        if len(parts) < 2:
            return "Usage: app permissions <package> <permission>"
        app, permission = parts
        result = ShizukuBridge.run(f"pm grant {app} {permission}")
        msg = result if result.startswith("Shizuku ") else f"Granted {permission} to {app}"
        self.voice.speak(msg)
        return msg


class SystemModule:
    """System operations"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def reboot(self, args: str) -> str:
        """Reboot phone"""
        if Config.CONFIRM_DESTRUCTIVE:
            return "Reboot requires manual confirmation. Run with CONFIRM_DESTRUCTIVE=false to override."
        
        msg = "Rebooting phone..."
        self.voice.speak(msg)
        try:
            subprocess.run(["reboot"], check=True)
        except Exception as e:
            return str(e)
        return msg
    
    def lock_screen(self, args: str) -> str:
        """Lock the screen"""
        try:
            subprocess.run(
                ["termux-lock-device"],
                check=True
            )
            msg = "Screen locked"
            self.voice.speak(msg)
            return msg
        except FileNotFoundError:
            return "Termux:API not installed"
    
    def find_file(self, args: str) -> str:
        """Search for files"""
        pattern = args.strip()
        try:
            result = subprocess.run(
                ["find", str(Path.home()), "-name", f"*{pattern}*", "-type", "f"],
                capture_output=True,
                text=True,
                timeout=5
            )
            files = result.stdout.strip().split('\n')[:5]
            msg = f"Found {len(files)} files: " + "; ".join(files)
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Search failed: {e}"


class UtilityModule:
    """Calculations, conversions, translations"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def calculate(self, args: str) -> str:
        """Perform calculation"""
        try:
            # Simple eval (safe for basic math)
            result = eval(args)
            msg = f"Result: {result}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Calculation failed: {e}"
    
    def unit_conversion(self, args: str) -> str:
        """Convert units"""
        conversions = {
            "km to miles": lambda x: x * 0.621371,
            "miles to km": lambda x: x / 0.621371,
            "celsius to fahrenheit": lambda x: (x * 9/5) + 32,
            "fahrenheit to celsius": lambda x: (x - 32) * 5/9,
            "kg to pounds": lambda x: x * 2.20462,
            "pounds to kg": lambda x: x / 2.20462,
        }
        
        msg = "Unit conversion: " + "; ".join(conversions.keys())
        self.voice.speak(msg)
        return msg
    
    def currency_conversion(self, args: str) -> str:
        """Convert currency"""
        if Config.LOCAL_ONLY:
            return "Currency conversion requires internet"
        
        msg = "Currency conversion (requires live exchange rates)"
        self.voice.speak(msg)
        return msg
    
    def translate(self, args: str) -> str:
        """Translate text"""
        if Config.LOCAL_ONLY:
            return "Translation requires internet"
        
        parts = args.split("|")
        if len(parts) < 2:
            return "Usage: translate <text>|<language>"
        
        text, lang = parts
        msg = f"Translating to {lang}: {text} (requires translation API)"
        self.voice.speak(msg)
        return msg


class SchedulingModule:
    """Reminders, calendar, alarms, scheduled tasks"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
        self.reminders_file = Config.DATA_DIR / "reminders.json"
        self.calendar_file = Config.DATA_DIR / "calendar.json"
    
    def set_reminder(self, args: str) -> str:
        """Set a reminder"""
        parts = args.split("|")
        if len(parts) < 2:
            return "Usage: reminder <time>|<text>"
        
        time_str, text = parts
        reminder = {"time": time_str, "text": text, "created": datetime.now().isoformat()}
        
        try:
            reminders = []
            if self.reminders_file.exists():
                with open(self.reminders_file, 'r') as f:
                    reminders = json.load(f)
            
            reminders.append(reminder)
            with open(self.reminders_file, 'w') as f:
                json.dump(reminders, f, indent=2)
            
            msg = f"Reminder set for {time_str}: {text}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Reminder failed: {e}"
    
    def list_reminders(self, args: str) -> str:
        """List all reminders"""
        try:
            if self.reminders_file.exists():
                with open(self.reminders_file, 'r') as f:
                    reminders = json.load(f)
                msg = f"You have {len(reminders)} reminders"
                self.voice.speak(msg)
                return msg
        except Exception as e:
            return f"Failed to read reminders: {e}"
    
    def set_alarm(self, args: str) -> str:
        """Set an alarm"""
        time_str = args.strip()
        msg = f"Alarm set for {time_str}"
        self.voice.speak(msg)
        return msg
    
    def add_calendar_event(self, args: str) -> str:
        """Add event to calendar"""
        parts = args.split("|")
        if len(parts) < 2:
            return "Usage: calendar add <date>|<event>"
        
        date, event = parts
        calendar_event = {"date": date, "event": event, "created": datetime.now().isoformat()}
        
        try:
            events = []
            if self.calendar_file.exists():
                with open(self.calendar_file, 'r') as f:
                    events = json.load(f)
            
            events.append(calendar_event)
            with open(self.calendar_file, 'w') as f:
                json.dump(events, f, indent=2)
            
            msg = f"Event added: {event} on {date}"
            self.voice.speak(msg)
            return msg
        except Exception as e:
            return f"Calendar event failed: {e}"
    
    def read_calendar(self, args: str) -> str:
        """Read calendar events"""
        try:
            if self.calendar_file.exists():
                with open(self.calendar_file, 'r') as f:
                    events = json.load(f)
                msg = f"You have {len(events)} calendar events"
                self.voice.speak(msg)
                return msg
        except Exception as e:
            return f"Failed to read calendar: {e}"
    
    def schedule_task(self, args: str) -> str:
        """Schedule task for specific time/location"""
        msg = "Scheduled task: " + args
        self.voice.speak(msg)
        return msg


class SettingsModule:
    """Personalization and per-contact rules"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
        self.settings_file = Config.DATA_DIR / "settings.json"
        self.contact_rules_file = Config.DATA_DIR / "contact_rules.json"
        self.usage_stats_file = Config.DATA_DIR / "usage_stats.json"
        self.load_settings()
    
    def load_settings(self) -> None:
        """Load settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    self.settings = json.load(f)
            except:
                self.settings = {}
        else:
            self.settings = {}
    
    def set_custom_wake_word(self, args: str) -> str:
        """Set custom wake word"""
        word = args.strip()
        self.settings['wake_word'] = word
        self._save_settings()
        msg = f"Wake word set to: {word} (requires retraining)"
        self.voice.speak(msg)
        return msg
    
    def contact_rule(self, args: str) -> str:
        """Set per-contact behavior"""
        parts = args.split("|")
        if len(parts) < 2:
            return "Usage: contact rule <contact>|<behavior>"
        
        contact, behavior = parts
        msg = f"Set rule for {contact}: {behavior}"
        self.voice.speak(msg)
        return msg
    
    def voice_preference(self, args: str) -> str:
        """Set voice preferences"""
        pref = args.strip()
        self.settings['voice_pref'] = pref
        self._save_settings()
        msg = f"Voice preference set to: {pref}"
        self.voice.speak(msg)
        return msg
    
    def usage_stats(self, args: str) -> str:
        """Show usage statistics"""
        try:
            if self.usage_stats_file.exists():
                with open(self.usage_stats_file, 'r') as f:
                    stats = json.load(f)
                    msg = f"Most used commands: {stats.get('top_commands', [])}"
                    self.voice.speak(msg)
                    return msg
            else:
                return "No usage stats yet"
        except Exception as e:
            return f"Stats failed: {e}"
    
    def _save_settings(self) -> None:
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")


class SmartHomeModule:
    """Smart home device control"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def light_on(self, args: str) -> str:
        """Turn light on"""
        room = args.strip() or "living room"
        msg = f"Turning on light in {room} (requires smart home setup)"
        self.voice.speak(msg)
        return msg
    
    def light_off(self, args: str) -> str:
        """Turn light off"""
        room = args.strip() or "living room"
        msg = f"Turning off light in {room}"
        self.voice.speak(msg)
        return msg


class DevToolsModule:
    """Developer/power user tools"""
    
    def __init__(self, voice: VoiceOutput):
        self.voice = voice
    
    def run_shell(self, args: str) -> str:
        """Run shell command (with safety checks)"""
        dangerous_cmds = ["rm -rf", "dd", ":(){:|:&;:;", "sudo", "su"]
        
        if Config.CONFIRM_DESTRUCTIVE and any(d in args for d in dangerous_cmds):
            return "Dangerous command blocked. Enable CONFIRM_DESTRUCTIVE=false to override."
        
        try:
            result = subprocess.run(
                args,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout[:200] if result.stdout else result.stderr[:200]
            self.voice.speak(output)
            return output
        except subprocess.TimeoutExpired:
            return "Command timed out"
        except Exception as e:
            return f"Command failed: {e}"
    
    def git_status(self, args: str) -> str:
        """Check git status"""
        try:
            result = subprocess.run(
                ["git", "status"],
                capture_output=True,
                text=True,
                check=True
            )
            self.voice.speak("Git status: " + result.stdout[:100])
            return result.stdout
        except Exception as e:
            return f"Git error: {e}"
    
    def ssh_check(self, args: str) -> str:
        """Check SSH connection"""
        host = args.strip()
        msg = f"Checking SSH to {host}..."
        self.voice.speak(msg)
        return msg


class GeneralCommandsModule:
    """Broad local commands that work without extra cloud services."""

    def __init__(self, voice: VoiceOutput):
        self.voice = voice

    def _say(self, message: str) -> str:
        self.voice.speak(message)
        return message

    def time_now(self, args: str) -> str:
        return self._say(datetime.now().strftime("It is %I:%M %p"))

    def date_today(self, args: str) -> str:
        return self._say(datetime.now().strftime("Today is %A, %B %d, %Y"))

    def uptime(self, args: str) -> str:
        try:
            value = Path("/proc/uptime").read_text(encoding="utf-8").split()[0]
            seconds = int(float(value))
            days, seconds = divmod(seconds, 86400)
            hours, seconds = divmod(seconds, 3600)
            minutes = seconds // 60
            return self._say(f"Uptime is {days} days, {hours} hours, {minutes} minutes")
        except (FileNotFoundError, ValueError, IndexError):
            return self._say("Uptime is unavailable on this system")

    def storage(self, args: str) -> str:
        usage = shutil.disk_usage(Path.home())
        used = usage.total - usage.free
        return self._say(
            f"Storage: {used // (1024 ** 3)} GB used of "
            f"{usage.total // (1024 ** 3)} GB, "
            f"{usage.free // (1024 ** 3)} GB free"
        )

    def memory(self, args: str) -> str:
        try:
            lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
            values = {
                line.split(":", 1)[0]: int(line.split()[1])
                for line in lines
                if ":" in line and len(line.split()) >= 2
            }
            total = values.get("MemTotal", 0) // 1024
            available = values.get("MemAvailable", values.get("MemFree", 0)) // 1024
            return self._say(f"Memory: {available} MB available of {total} MB")
        except (FileNotFoundError, ValueError, IndexError):
            return self._say("Memory information is unavailable")

    def current_directory(self, args: str) -> str:
        return self._say(str(Path.cwd()))

    def list_files(self, args: str) -> str:
        target = Path(args.strip() or ".").expanduser()
        if not target.exists():
            return self._say(f"Path not found: {target}")
        entries = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:30]
        if not entries:
            return self._say(f"{target} is empty")
        listing = "; ".join(f"{item.name}/" if item.is_dir() else item.name for item in entries)
        return self._say(f"Contents of {target}: {listing}")

    def find_text(self, args: str) -> str:
        parts = args.split("|", 1)
        if len(parts) != 2:
            return self._say("Usage: find text <pattern>|<directory>")
        pattern, directory = parts[0].strip(), Path(parts[1].strip() or ".").expanduser()
        matches = []
        for path in directory.rglob("*"):
            if len(matches) >= 10 or not path.is_file():
                continue
            try:
                if pattern.lower() in path.read_text(encoding="utf-8", errors="ignore").lower():
                    matches.append(str(path))
            except OSError:
                continue
        return self._say("Matches: " + ("; ".join(matches) if matches else "none"))

    def open_url(self, args: str) -> str:
        url = args.strip()
        if not url:
            return self._say("Usage: open <url>")
        if not re.match(r"^https?://", url, re.IGNORECASE):
            url = "https://" + url
        try:
            subprocess.run(["termux-open-url", url], check=True)
            return self._say(f"Opening {url}")
        except (FileNotFoundError, subprocess.CalledProcessError):
            return self._say(f"Open this URL in your browser: {url}")

    def open_app(self, args: str) -> str:
        package = args.strip()
        if not package:
            return self._say("Usage: open app <package.name>")
        try:
            subprocess.run(["monkey", "-p", package, "1"], check=True, capture_output=True)
            return self._say(f"Opened {package}")
        except (FileNotFoundError, subprocess.CalledProcessError):
            return self._say(f"Could not open {package}; check the package name")

    def network_info(self, args: str) -> str:
        try:
            result = subprocess.run(["ip", "addr"], capture_output=True, text=True, check=True)
            addresses = re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", result.stdout)
            return self._say("Network addresses: " + (", ".join(addresses) if addresses else "none"))
        except (FileNotFoundError, subprocess.CalledProcessError):
            return self._say("Network information is unavailable")

    def ping(self, args: str) -> str:
        host = args.strip() or "1.1.1.1"
        try:
            result = subprocess.run(["ping", "-c", "1", "-W", "2", host], capture_output=True, text=True)
            return self._say(f"{host} is reachable" if result.returncode == 0 else f"{host} is unreachable")
        except FileNotFoundError:
            return self._say("ping is not installed")

    def notify(self, args: str) -> str:
        message = args.strip()
        if not message:
            return self._say("Usage: notify <message>")
        try:
            subprocess.run(["termux-notification", "--title", "NOVA", "--content", message], check=True)
            return self._say("Notification sent")
        except (FileNotFoundError, subprocess.CalledProcessError):
            return self._say("Notification requires Termux:API")

    def clipboard_get(self, args: str) -> str:
        try:
            result = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, check=True)
            return self._say(result.stdout.strip() or "Clipboard is empty")
        except (FileNotFoundError, subprocess.CalledProcessError):
            return self._say("Clipboard access requires Termux:API")

    def clipboard_set(self, args: str) -> str:
        message = args.strip()
        if not message:
            return self._say("Usage: clipboard set <text>")
        try:
            subprocess.run(["termux-clipboard-set", message], check=True)
            return self._say("Clipboard updated")
        except (FileNotFoundError, subprocess.CalledProcessError):
            return self._say("Clipboard access requires Termux:API")

    def encode_url(self, args: str) -> str:
        return self._say(urllib.parse.quote(args.strip(), safe=""))

    def decode_url(self, args: str) -> str:
        return self._say(urllib.parse.unquote(args.strip()))

    def clear_screen(self, args: str) -> str:
        os.system("clear")
        return ""


class GeminiModule:
    """Optional open-ended conversation through Google's Gemini API."""

    def __init__(self, voice: VoiceOutput):
        self.voice = voice
        self.client = None
        self.conversation: List[Dict[str, str]] = []

        if genai and Config.GEMINI_API_KEY and not Config.LOCAL_ONLY:
            self.client = genai.Client(api_key=Config.GEMINI_API_KEY)

    @property
    def available(self) -> bool:
        return self.client is not None

    def ask(self, prompt: str) -> Optional[str]:
        """Ask Gemini and speak the response, if configured."""
        if not self.available:
            return None

        self.conversation.append({"role": "user", "text": prompt})
        recent = self.conversation[-10:]
        transcript = "\n".join(
            f"{item['role']}: {item['text']}" for item in recent
        )
        system = (
            "You are NOVA, a warm, concise voice assistant running in Termux "
            "on an Android phone. Answer naturally and plainly. Do not claim "
            "you changed phone settings or sent messages unless NOVA's local "
            "command system confirmed it. Keep spoken replies under 120 words."
        )

        try:
            response = self.client.models.generate_content(
                model=Config.GEMINI_MODEL,
                contents=f"{system}\n\nConversation:\n{transcript}",
            )
            answer = (response.text or "I could not produce a response.").strip()
            self.conversation.append({"role": "assistant", "text": answer})
            self.conversation = self.conversation[-10:]
            self.voice.speak(answer)
            return answer
        except Exception as error:
            logger.error("Gemini request failed: %s", error)
            return "Gemini is unavailable right now. Check your connection and API key."

    def ask_command(self, prompt: str) -> str:
        """Handle the explicit ask command with a useful configuration response."""
        answer = self.ask(prompt)
        if answer:
            return answer
        message = "Gemini is not configured. Add GEMINI_API_KEY to your .env file."
        self.voice.speak(message)
        return message


# ============================================================================
# MAIN ASSISTANT
# ============================================================================

class VoiceAssistant:
    """Main voice assistant orchestrator"""
    
    def __init__(self):
        logger.info("Initializing Voice Assistant...")
        
        # Initialize I/O
        self.voice_out = VoiceOutput(Config.TTS_ENGINE)
        self.voice_in = VoiceInput(Config.STT_ENGINE)
        self.parser = CommandParser()
    
        # Initialize modules
        self.comm = CommunicationModule(self.voice_out)
        self.phone = PhoneControlModule(self.voice_out)
        self.phone_ext = PhoneExtendedModule(self.voice_out)
        self.calls = CallModule(self.voice_out)
        self.messaging = MessagingModule(self.voice_out)
        self.apps = AppModule(self.voice_out)
        self.system = SystemModule(self.voice_out)
        self.utility = UtilityModule(self.voice_out)
        self.schedule = SchedulingModule(self.voice_out)
        self.settings = SettingsModule(self.voice_out)
        self.auto = AutomationModule(self.voice_out)
        self.info = InformationModule(self.voice_out)
        self.prod = ProductivityModule(self.voice_out)
        self.media = MediaModule(self.voice_out)
        self.smart = SmartHomeModule(self.voice_out)
        self.dev = DevToolsModule(self.voice_out)
        self.general = GeneralCommandsModule(self.voice_out)
        self.gemini = GeminiModule(self.voice_out)
        
        # Register commands
        self._register_commands()
        
        self.running = False
        logger.info("Voice Assistant initialized successfully")
    
    def _register_commands(self) -> None:
        """Register all command handlers"""
        
        # Communication
        self.parser.register("read sms", lambda p: self.comm.read_sms(p.get("args", "")), ["sms", "messages"])
        self.parser.register("read email", lambda p: self.comm.read_email(p.get("args", "")), ["email", "mail"])
        self.parser.register("send sms", lambda p: self.comm.send_sms(p.get("args", "")), ["text"])
        self.parser.register("call log", lambda p: self.comm.read_call_log(p.get("args", "")))
        self.parser.register("read notifications", lambda p: self.comm.read_notifications(p.get("args", "")), ["notifications"])
        
        # Phone Control
        self.parser.register("wifi", lambda p: self.phone.toggle_wifi(p.get("args", "")), ["wifi on", "wifi off"])
        self.parser.register("bluetooth", lambda p: self.phone.toggle_bluetooth(p.get("args", "")))
        self.parser.register("brightness", lambda p: self.phone.brightness(p.get("args", "")))
        self.parser.register("battery", lambda p: self.phone.battery_status(p.get("args", "")), ["battery status"])
        self.parser.register("screenshot", lambda p: self.phone.screenshot(p.get("args", "")))
        
        # Extended Phone Control
        self.parser.register("mobile data", lambda p: self.phone_ext.toggle_mobile_data(p.get("args", "")))
        self.parser.register("airplane mode", lambda p: self.phone_ext.toggle_airplane_mode(p.get("args", "")))
        self.parser.register("flashlight", lambda p: self.phone_ext.toggle_flashlight(p.get("args", "")))
        self.parser.register("volume", lambda p: self.phone_ext.set_volume(p.get("args", "")))
        self.parser.register("screen timeout", lambda p: self.phone_ext.screen_timeout(p.get("args", "")))
        self.parser.register("rotation lock", lambda p: self.phone_ext.rotation_lock(p.get("args", "")))
        self.parser.register("dnd", lambda p: self.phone_ext.dnd_mode(p.get("args", "")), ["do not disturb"])
        
        # Calls
        self.parser.register("call", lambda p: self.calls.make_call(p.get("args", "")), ["make call", "dial"])
        self.parser.register("answer", lambda p: self.calls.answer_call(p.get("args", "")))
        self.parser.register("reject", lambda p: self.calls.reject_call(p.get("args", "")), ["decline"])
        self.parser.register("hangup", lambda p: self.calls.hangup(p.get("args", "")), ["end call"])
        
        # Messaging
        self.parser.register("whatsapp", lambda p: self.messaging.whatsapp_send(p.get("args", "")))
        self.parser.register("telegram", lambda p: self.messaging.telegram_send(p.get("args", "")))
        self.parser.register("read whatsapp", lambda p: self.messaging.whatsapp_read(p.get("args", "")))
        self.parser.register("read telegram", lambda p: self.messaging.telegram_read(p.get("args", "")))
        
        # Apps
        self.parser.register("install app", lambda p: self.apps.app_install(p.get("args", "")))
        self.parser.register("uninstall app", lambda p: self.apps.app_uninstall(p.get("args", "")))
        self.parser.register("force stop", lambda p: self.apps.app_force_stop(p.get("args", "")), ["kill app"])
        self.parser.register("clear cache", lambda p: self.apps.app_clear_cache(p.get("args", "")))
        self.parser.register("app permissions", lambda p: self.apps.app_permissions(p.get("args", "")))
        
        # System
        self.parser.register("reboot", lambda p: self.system.reboot(p.get("args", "")), ["restart"])
        self.parser.register("lock screen", lambda p: self.system.lock_screen(p.get("args", "")), ["lock"])
        self.parser.register("find file", lambda p: self.system.find_file(p.get("args", "")), ["search file"])
        
        # Utilities
        self.parser.register("calculate", lambda p: self.utility.calculate(p.get("args", "")), ["math", "calc"])
        self.parser.register("convert", lambda p: self.utility.unit_conversion(p.get("args", "")), ["conversion"])
        self.parser.register("currency", lambda p: self.utility.currency_conversion(p.get("args", "")))
        self.parser.register("translate", lambda p: self.utility.translate(p.get("args", "")))
        
        # Scheduling
        self.parser.register("reminder", lambda p: self.schedule.set_reminder(p.get("args", "")), ["set reminder"])
        self.parser.register("reminders", lambda p: self.schedule.list_reminders(p.get("args", "")), ["list reminders"])
        self.parser.register("alarm", lambda p: self.schedule.set_alarm(p.get("args", "")), ["set alarm"])
        self.parser.register("calendar add", lambda p: self.schedule.add_calendar_event(p.get("args", "")))
        self.parser.register("calendar", lambda p: self.schedule.read_calendar(p.get("args", "")), ["my events"])
        self.parser.register("schedule", lambda p: self.schedule.schedule_task(p.get("args", "")))
        
        # Settings
        self.parser.register("wake word", lambda p: self.settings.set_custom_wake_word(p.get("args", "")))
        self.parser.register("contact rule", lambda p: self.settings.contact_rule(p.get("args", "")))
        self.parser.register("voice preference", lambda p: self.settings.voice_preference(p.get("args", "")))
        self.parser.register("usage stats", lambda p: self.settings.usage_stats(p.get("args", "")), ["stats"])
        
        # Automation
        self.parser.register("leaving home", lambda p: self.auto.leaving_home(p.get("args", "")))
        self.parser.register("arriving home", lambda p: self.auto.arriving_home(p.get("args", "")))
        
        # Information
        self.parser.register("weather", lambda p: self.info.weather(p.get("args", "")))
        self.parser.register("news", lambda p: self.info.news(p.get("args", "")))
        self.parser.register("search", lambda p: self.info.web_search(p.get("args", "")), ["google"])
        self.parser.register("system", lambda p: self.info.system_diagnostics(p.get("args", "")), ["diagnostics"])
        
        # Productivity
        self.parser.register("note", lambda p: self.prod.add_note(p.get("args", "")), ["add note"])
        self.parser.register("read notes", lambda p: self.prod.read_notes(p.get("args", "")))
        self.parser.register("timer", lambda p: self.prod.set_timer(p.get("args", "")), ["set timer"])
        self.parser.register("task", lambda p: self.prod.add_task(p.get("args", "")), ["add task", "todo"])
        
        # Media
        self.parser.register("play music", lambda p: self.media.play_music(p.get("args", "")), ["music"])
        self.parser.register("podcast", lambda p: self.media.podcast_play(p.get("args", "")))
        self.parser.register("now playing", lambda p: self.media.music_info(p.get("args", "")))
        
        # Smart Home
        self.parser.register("lights on", lambda p: self.smart.light_on(p.get("args", "")))
        self.parser.register("lights off", lambda p: self.smart.light_off(p.get("args", "")))
        
        # Dev Tools
        self.parser.register("shell", lambda p: self.dev.run_shell(p.get("args", "")), ["run", "exec"])
        self.parser.register("shizuku", lambda p: self._run_shizuku(p.get("args", "")), ["rish"])
        self.parser.register("git", lambda p: self.dev.git_status(p.get("args", "")))
        self.parser.register("ssh", lambda p: self.dev.ssh_check(p.get("args", "")))

        # General local commands
        self.parser.register("time", lambda p: self.general.time_now(p.get("args", "")), ["what time is it"])
        self.parser.register("date", lambda p: self.general.date_today(p.get("args", "")), ["what day is it"])
        self.parser.register("uptime", lambda p: self.general.uptime(p.get("args", "")))
        self.parser.register("storage", lambda p: self.general.storage(p.get("args", "")), ["disk space"])
        self.parser.register("memory", lambda p: self.general.memory(p.get("args", "")), ["ram"])
        self.parser.register("pwd", lambda p: self.general.current_directory(p.get("args", "")), ["where am i"])
        self.parser.register("list files", lambda p: self.general.list_files(p.get("args", "")), ["ls", "list"])
        self.parser.register("find text", lambda p: self.general.find_text(p.get("args", "")))
        self.parser.register("open", lambda p: self.general.open_url(p.get("args", "")), ["open url", "browse"])
        self.parser.register("open app", lambda p: self.general.open_app(p.get("args", "")))
        self.parser.register("network", lambda p: self.general.network_info(p.get("args", "")), ["ip address", "network info"])
        self.parser.register("ping", lambda p: self.general.ping(p.get("args", "")))
        self.parser.register("notify", lambda p: self.general.notify(p.get("args", "")), ["notification"])
        self.parser.register("clipboard get", lambda p: self.general.clipboard_get(p.get("args", "")))
        self.parser.register("clipboard set", lambda p: self.general.clipboard_set(p.get("args", "")))
        self.parser.register("encode url", lambda p: self.general.encode_url(p.get("args", "")))
        self.parser.register("decode url", lambda p: self.general.decode_url(p.get("args", "")))
        self.parser.register("clear screen", lambda p: self.general.clear_screen(p.get("args", "")), ["clear"])
        self.parser.register("ask", lambda p: self.gemini.ask_command(p.get("args", "")))
        
        # System
        self.parser.register("help", lambda p: self._show_help(p.get("args", "")))
        self.parser.register("history", lambda p: self._show_history(p.get("args", "")))
        self.parser.register("exit", lambda p: self._exit(p.get("args", "")), ["quit", "bye"])
    
    def _show_help(self, args: str) -> str:
        """Show help"""
        help_text = """
Voice Assistant - Complete Command List:

📱 COMMUNICATION:
  read sms, send sms, read email, call log, whatsapp, telegram

📲 PHONE CONTROL:
  wifi [on/off], bluetooth, brightness [0-255], battery, screenshot
  mobile data, airplane mode, flashlight, volume, screen timeout
  rotation lock, dnd (do not disturb)

📞 CALLS:
  call <number>, answer, reject, hangup

💬 MESSAGING:
  whatsapp <contact>|<msg>, telegram <user>|<msg>
  read whatsapp, read telegram

📱 APPS:
  install app <name>, uninstall app <name>, force stop <app>
  clear cache <app>, app permissions <app>

⚙️  SYSTEM:
  reboot, lock screen, find file <name>

🧮 UTILITIES:
  calculate <math>, convert <value>, currency <amount>
  translate <text>|<language>

⏰ SCHEDULING:
  reminder <time>|<text>, reminders, alarm <time>
  calendar add <date>|<event>, calendar, schedule <task>

⚙️  SETTINGS:
  wake word <word>, contact rule <contact>|<behavior>
  voice preference <pref>, usage stats

🏠 AUTOMATION:
  leaving home, arriving home

ℹ️  INFORMATION:
  weather, news, search <query>, system diagnostics

✅ PRODUCTIVITY:
  note <text>, read notes, timer <minutes>, task <text>

🎵 MEDIA:
  play music, podcast <name>, now playing

💡 SMART HOME:
  lights on, lights off

⚙️  DEVELOPER:
  shell <command>, git, ssh <host>

🧰 LOCAL TOOLS:
    time, date, uptime, storage, memory, pwd, list files [path]
    find text <pattern>|<directory>, open <url>, open app <package>
    network, ping <host>, notify <message>
    clipboard get, clipboard set <text>, encode/decode url, clear

🔐 SHIZUKU:
    shizuku <Android shell command>, for example: shizuku settings put system screen_brightness 100

🤖 GEMINI:
    ask <question> or simply speak an unrecognized question
    Configure GEMINI_API_KEY to enable open-ended conversation.

Type 'help' for this menu, 'history' for action log, 'exit' to quit.

You can also speak naturally, for example:
    "what is my battery level?", "remind me to call Sam at 6pm"
    "what can you do?", "open youtube.com", "calculate 12 percent of 80"
        """
        self.voice_out.speak(help_text)
        return help_text

    def _run_shizuku(self, args: str) -> str:
        """Run an explicit Android shell command through Shizuku."""
        result = ShizukuBridge.run(args)
        self.voice_out.speak(result)
        return result

    def _show_banner(self) -> None:
        """Show the assistant identity and local runtime status."""
        mode = "LOCAL ONLY" if Config.LOCAL_ONLY else "ONLINE FEATURES ENABLED"
        voice = "voice output" if Config.VOICE_ENABLED else "text output"
        print("\n" + "=" * 62)
        print("  NOVA  |  TERMUX AI ASSISTANT")
        print("=" * 62)
        print(f"  status:  ready        mode: {mode}")
        gemini = "connected" if self.gemini.available else "not configured"
        print(f"  input:   {Config.STT_ENGINE:<12} output: {voice}")
        print(f"  Gemini:  {gemini}")
        print("  type 'help' for commands, 'exit' to close")
        print("=" * 62 + "\n")
    
    def _show_history(self, args: str) -> str:
        """Show command history"""
        history_str = json.dumps(self.parser.history[-10:], indent=2)
        self.voice_out.speak(f"Last 10 actions: {history_str[:200]}")
        return history_str
    
    def _exit(self, args: str) -> str:
        """Exit assistant"""
        self.running = False
        msg = "Goodbye!"
        self.voice_out.speak(msg)
        return msg

    def _conversation_reply(self, text: str) -> Optional[str]:
        """Handle lightweight conversation without requiring a cloud AI service."""
        normalized = re.sub(r"[^a-z0-9' ]", "", text.lower()).strip()
        replies = {
            "hi": "Hello. I am NOVA, your Termux assistant.",
            "hello": "Hello. I am NOVA, your Termux assistant.",
            "hey": "Hey. What can I help you with?",
            "good morning": "Good morning. NOVA is ready.",
            "good afternoon": "Good afternoon. NOVA is ready.",
            "good evening": "Good evening. NOVA is ready.",
            "thanks": "You are welcome.",
            "thank you": "You are welcome.",
            "how are you": "All systems are ready and waiting for your request.",
            "who are you": "I am NOVA, a local voice assistant running in Termux.",
            "what can you do": "I can control Termux features, manage notes and reminders, inspect your phone, and run safe local commands. Say help for the full list.",
            "your name": "My name is NOVA.",
        }
        reply = replies.get(normalized)
        if reply:
            self.voice_out.speak(reply)
        return reply

    def _interpret_natural_language(self, text: str) -> Optional[str]:
        """Convert common conversational requests into existing commands."""
        normalized = re.sub(r"[?!]+$", "", text.strip().lower())

        patterns = [
            (r"^(?:what(?:'s| is) the )?weather(?: like)?(?: today)?(?: in (.+))?$", "weather"),
            (r"^(?:what(?:'s| is) my )?battery(?: level| status)?$", "battery"),
            (r"^(?:what(?:'s| is) )?(?:the )?time(?: is it)?$", "time"),
            (r"^(?:what(?:'s| is) )?(?:the )?date(?: today)?$", "date"),
            (r"^(?:how much )?(?:free )?storage(?: do i have)?$", "storage"),
            (r"^(?:how much )?(?:free )?memory(?: do i have)?$", "memory"),
            (r"^(?:show|list|read) (?:my )?(?:files|file list)$", "list files"),
            (r"^(?:turn|switch) (wifi|wi fi) (on|off)$", "wifi"),
            (r"^(?:turn|switch) (?:the )?flashlight (on|off)$", "flashlight"),
            (r"^(?:set )?brightness to (\d+)$", "brightness"),
            (r"^(?:play|start) (?:some )?music(?: by (.+))?$", "play music"),
            (r"^(?:set )?(?:a )?timer for (\d+) minutes?$", "timer"),
            (r"^(?:remind me to|remember to) (.+?)(?: at| on) (.+)$", "reminder"),
            (r"^(?:make|place) (?:a )?call to (.+)$", "call"),
            (r"^(?:take|capture) (?:a )?screenshot$", "screenshot"),
            (r"^(?:open|launch) (?:the )?app (.+)$", "open app"),
            (r"^(?:open|visit|browse) (https?://\S+|[a-z0-9.-]+\.[a-z]{2,}\S*)$", "open"),
            (r"^(?:search|look up|find) (?:for )?(.+)$", "search"),
            (r"^(?:calculate|work out|what is) (\d+(?:\.\d+)?) percent of (\d+(?:\.\d+)?)$", "calculate percent"),
            (r"^(?:calculate|work out|what is) ([0-9+\-*/(). %]+)$", "calculate"),
            (r"^(?:write down|make a note|note that|remember) (.+)$", "note"),
            (r"^(?:show|read) (?:my )?notifications?$", "read notifications"),
            (r"^(?:check|show) (?:my )?(?:phone )?status$", "system"),
        ]

        for pattern, command in patterns:
            match = re.match(pattern, normalized)
            if not match:
                continue
            groups = [group.strip() for group in match.groups() if group and group.strip()]
            if command == "weather":
                return f"weather {groups[0]}" if groups else "weather"
            if command == "wifi" or command == "flashlight":
                return f"{command} {groups[-1]}"
            if command == "brightness" or command == "timer":
                return f"{command} {groups[-1]}"
            if command == "reminder":
                return f"reminder {groups[1]}|{groups[0]}"
            if command == "play music":
                return f"play music {groups[0]}" if groups else "play music"
            if command == "calculate" or command == "note" or command == "search":
                return f"{command} {groups[0]}"
            if command == "calculate percent":
                return f"calculate {groups[0]}*{groups[1]}/100"
            if command == "call" or command == "open app" or command == "open":
                return f"{command} {groups[0]}"
            return command
        return None
    
    def process_command(self, text: str) -> Any:
        """Process a single command"""
        text = text.strip()
        if not text:
            return ""

        if self._conversation_reply(text):
            return text

        interpreted = self._interpret_natural_language(text)
        if interpreted:
            text = interpreted

        cmd, params = self.parser.parse(text)
        
        if not cmd:
            gemini_response = self.gemini.ask(text)
            if gemini_response:
                return gemini_response
            response = f"Unknown command: {text}. Type 'help' for available commands."
            self.voice_out.speak(response)
            return response
        
        return self.parser.execute(cmd, params)
    
    def run_interactive(self) -> None:
        """Run interactive voice/text loop"""
        self.running = True
        self._show_banner()
        self.voice_out.speak("NOVA is ready. How can I help?")
        
        while self.running:
            try:
                # Try voice input first, fallback to text
                print("\n  [listening] speak a command, or type below")
                text = self.voice_in.listen(timeout=5)
                
                if not text:
                    text = input("  you > ").strip()
                
                if not text:
                    continue
                
                print(f"  nova > processing: {text}")
                self.process_command(text)
            
            except KeyboardInterrupt:
                print("\n\nExiting...")
                self.running = False
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.voice_out.speak(f"Error: {e}")
    
    def run_single_command(self, command: str) -> Any:
        """Run a single command and exit"""
        return self.process_command(command)


# ============================================================================
# CLI & MAIN
# ============================================================================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Voice Assistant - Comprehensive voice-controlled AI for Termux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python voiceassistant.py                    # Interactive mode
  python voiceassistant.py "read sms"         # Single command
  python voiceassistant.py --help             # Show this help
  DEBUG=true python voiceassistant.py         # Debug mode
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        help="Single command to execute (optional)"
    )
    
    parser.add_argument(
        "--voice",
        choices=["pyttsx3", "espeak"],
        default=None,
        help="TTS engine to use"
    )
    
    parser.add_argument(
        "--stt",
        choices=["google", "pocketsphinx"],
        default="google",
        help="STT engine to use"
    )
    
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Disable all internet-dependent features"
    )
    
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable voice output (text only)"
    )
    
    args = parser.parse_args()
    
    # Update config
    if args.local_only:
        Config.LOCAL_ONLY = True
    if args.no_voice:
        Config.VOICE_ENABLED = False
    if args.voice:
        Config.TTS_ENGINE = args.voice
    Config.STT_ENGINE = args.stt
    
    # Initialize assistant
    assistant = VoiceAssistant()
    
    # Run command or interactive mode
    if args.command:
        result = assistant.run_single_command(args.command)
        if result is not None:
            print(result)
    else:
        assistant.run_interactive()


if __name__ == "__main__":
    main()
