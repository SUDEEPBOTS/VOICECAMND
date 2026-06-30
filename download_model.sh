#!/bin/bash
# =====================================================
# Vosk Model Downloader for VoiceSraver Bot
# =====================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="$SCRIPT_DIR/model"

echo "╔══════════════════════════════════════════╗"
echo "║   🎙 Vosk Model Downloader              ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Model options
echo "Available models:"
echo "  1) vosk-model-small-en-us-0.15  (~40MB)  - English (fast, light)"
echo "  2) vosk-model-small-hi-0.22     (~40MB)  - Hindi (fast, light)"
echo "  3) vosk-model-hi-0.22           (~1.5GB) - Hindi+English (best accuracy)"
echo "  4) vosk-model-en-us-0.22        (~1.8GB) - English (best accuracy)"
echo "  5) vosk-model-small-en-in-0.4   (~36MB)  - Indian English (fast)"
echo ""

read -p "Select model (1-5) [default: 3]: " choice
choice=${choice:-3}

case $choice in
    1) MODEL_NAME="vosk-model-small-en-us-0.15" ;;
    2) MODEL_NAME="vosk-model-small-hi-0.22" ;;
    3) MODEL_NAME="vosk-model-hi-0.22" ;;
    4) MODEL_NAME="vosk-model-en-us-0.22" ;;
    5) MODEL_NAME="vosk-model-small-en-in-0.4" ;;
    *) echo "❌ Invalid choice!"; exit 1 ;;
esac

MODEL_URL="https://alphacephei.com/vosk/models/${MODEL_NAME}.zip"

echo ""
echo "📥 Downloading: $MODEL_NAME"
echo "   URL: $MODEL_URL"
echo ""

# Download
if command -v wget &> /dev/null; then
    wget -c "$MODEL_URL" -O "/tmp/${MODEL_NAME}.zip"
elif command -v curl &> /dev/null; then
    curl -L -C - "$MODEL_URL" -o "/tmp/${MODEL_NAME}.zip"
else
    echo "❌ Neither wget nor curl found! Install one of them."
    exit 1
fi

echo ""
echo "📦 Extracting model..."

# Remove old model directory if exists
rm -rf "$MODEL_DIR"

# Extract
cd /tmp
unzip -q "${MODEL_NAME}.zip"

# Move to project directory as 'model'
mv "$MODEL_NAME" "$MODEL_DIR"

# Cleanup
rm -f "/tmp/${MODEL_NAME}.zip"

echo ""
echo "✅ Model installed at: $MODEL_DIR"
echo "   Model: $MODEL_NAME"
echo ""
echo "You can now start the bot with: python bot.py"
