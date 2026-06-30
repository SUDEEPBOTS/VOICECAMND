"""
VoiceSraver Bot Configuration
All settings loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Telegram API ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "your_api_hash_here")

# --- String Session (for cloud deployment) ---
# Generate with: python gen_session.py
# If set, .session file is NOT needed
STRING_SESSION = os.getenv("STRING_SESSION", "")

# --- AI & Moderation ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Session fallback (file-based, for local dev) ---
SESSION_NAME = os.getenv("SESSION_NAME", "voicesraver")

# --- Vosk Model ---
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", str(Path(__file__).parent.parent / "model"))

# --- Audio Settings (DO NOT CHANGE) ---
INPUT_SAMPLE_RATE = 48000   # pytgcalls output
INPUT_SAMPLE_WIDTH = 2      # 16-bit
INPUT_CHANNELS = 1          # mono
VOSK_SAMPLE_RATE = 16000    # Vosk requirement

# --- Transcription ---
AUDIO_QUEUE_MAX_SIZE = 2000
MIN_TEXT_LENGTH = 2
MESSAGE_COOLDOWN = 1.5
BATCH_WINDOW_SECONDS = 2.0

# --- Admin IDs ---
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- FastAPI Server ---
FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))

# --- WebSocket ---
WS_MAX_CONNECTIONS = int(os.getenv("WS_MAX_CONNECTIONS", "50"))
