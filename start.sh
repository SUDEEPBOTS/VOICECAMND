#!/bin/bash
# VoiceSraver — Start Script
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎙 VoiceSraver Starting..."

# Load .env
if [ -f .env ]; then
    echo "📄 Loading .env..."
    set -a && source .env && set +a
fi

# Activate venv
if [ -d "myenv" ]; then
    source myenv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check model
if [ ! -d "model" ]; then
    echo "⚠️  Vosk model not found! Run: bash download_model.sh"
fi

echo "🚀 Starting server..."
python main.py
