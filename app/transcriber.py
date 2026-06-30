"""
Vosk Transcription Engine for VoiceSraver.
Runs in a separate thread, receives audio from a queue,
transcribes using Vosk, sends results to Telegram and WebSocket.
"""

import asyncio
import json
import logging
import queue
import threading
import time

import numpy as np
from vosk import Model, KaldiRecognizer, SetLogLevel

from app import config
from app.ws_manager import WSManager
from app.ai_agent import analyze_text_with_ai

logger = logging.getLogger("VoiceSraver.STT")

# Suppress Vosk internal logs
SetLogLevel(-1)


def resample_48k_to_16k(pcm_bytes: bytes) -> bytes:
    """
    Downsample PCM audio from 48kHz to 16kHz using numpy decimation.
    Input:  PCM 16-bit signed, 48000 Hz, mono
    Output: PCM 16-bit signed, 16000 Hz, mono
    Decimation factor: 3 (48000 / 16000 = 3)
    """
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if len(samples) == 0:
        return b""
    resampled = samples[::3]
    return resampled.tobytes()


class TranscriptionManager:
    """
    Manages the Vosk transcription pipeline.
    Runs in a separate thread, receives audio from a queue,
    and sends transcribed text to Telegram + WebSocket.
    """

    def __init__(
        self,
        pyrogram_app,
        chat_id: int,
        loop: asyncio.AbstractEventLoop,
        ws_manager: WSManager | None = None,
    ):
        self.pyrogram_app = pyrogram_app
        self.chat_id = chat_id
        self.loop = loop
        self.ws_manager = ws_manager

        self.audio_queue: queue.Queue = queue.Queue(
            maxsize=config.AUDIO_QUEUE_MAX_SIZE
        )
        self.is_running = False
        self._thread: threading.Thread | None = None

        # Message batching
        self._message_buffer: list[str] = []
        self._last_send_time: float = 0
        
        # History for AI Summaries and Downloading
        self.transcript_history: list[str] = []

    def start(self):
        """Start the transcription worker thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(
            target=self._worker,
            name="TranscriptionWorker",
            daemon=True,
        )
        self._thread.start()
        logger.info("Transcription worker started")

    def stop(self):
        """Stop the transcription worker and flush remaining text."""
        self.is_running = False
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("Transcription worker stopped")

    def feed_audio(self, pcm_data: bytes):
        """Feed resampled 16kHz audio data into the queue."""
        if not self.is_running:
            return
        try:
            self.audio_queue.put_nowait(pcm_data)
        except queue.Full:
            pass  # Drop chunk to prevent memory overflow

    def _worker(self):
        """Main transcription loop in a separate thread."""
        try:
            logger.info(f"Loading Vosk model from: {config.VOSK_MODEL_PATH}")
            model = Model(config.VOSK_MODEL_PATH)
            recognizer = KaldiRecognizer(model, config.VOSK_SAMPLE_RATE)
            recognizer.SetWords(True)
            logger.info("Vosk model loaded successfully \u2705")
        except Exception as e:
            logger.error(f"Failed to load Vosk model: {e}")
            self.is_running = False
            self._send_message_sync("\u274c Vosk model load failed! Check VOSK_MODEL_PATH.")
            return

        while self.is_running:
            try:
                try:
                    data = self.audio_queue.get(timeout=0.5)
                except queue.Empty:
                    self._flush_buffer()
                    continue

                if recognizer.AcceptWaveform(data):
                    # Complete utterance (after silence)
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text and len(text) >= config.MIN_TEXT_LENGTH:
                        self._add_to_buffer(text)
                else:
                    # Partial result — broadcast via WS only
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = partial.get("partial", "").strip()
                    if partial_text and self.ws_manager:
                        asyncio.run_coroutine_threadsafe(
                            self.ws_manager.broadcast_transcription(
                                partial_text, is_partial=True
                            ),
                            self.loop,
                        )

            except Exception as e:
                logger.error(f"Transcription error: {e}", exc_info=True)
                time.sleep(0.1)

        # Final flush
        try:
            final = json.loads(recognizer.FinalResult())
            text = final.get("text", "").strip()
            if text and len(text) >= config.MIN_TEXT_LENGTH:
                self._add_to_buffer(text)
            self._flush_buffer(force=True)
        except Exception:
            pass

        logger.info("Transcription worker loop ended")

    def _add_to_buffer(self, text: str):
        """Add text to batch buffer, flush if window expired."""
        self._message_buffer.append(text)
        now = time.time()
        if now - self._last_send_time >= config.BATCH_WINDOW_SECONDS:
            self._flush_buffer()

    def _flush_buffer(self, force: bool = False):
        """Send batched text as one Telegram message + WS broadcast."""
        if not self._message_buffer:
            return
        now = time.time()
        if not force and now - self._last_send_time < config.MESSAGE_COOLDOWN:
            return

        combined = " ".join(self._message_buffer)
        self._message_buffer.clear()
        self._last_send_time = now

        # Delegate AI check and Telegram sending to the asyncio loop
        asyncio.run_coroutine_threadsafe(self._process_and_send(combined), self.loop)

    async def _process_and_send(self, text: str):
        """Asynchronously process text with AI, then send to Telegram and WS."""
        
        # 1. Ask AI for moderation and commands
        analysis = await analyze_text_with_ai(text)
        
        # Store in history
        self.transcript_history.append(text)
        
        # 2. Moderation check
        if analysis.get("is_abusive"):
            text = "[CENSORED BY AI MODERATOR]"
            if self.ws_manager:
                await self.ws_manager.broadcast_event("moderation_alert", {
                    "chat_id": self.chat_id,
                    "reason": "Abusive language detected"
                })
            
        # 3. Voice Commands check
        command = analysis.get("voice_command")
        if command:
            song = analysis.get("song_name")
            if self.ws_manager:
                await self.ws_manager.broadcast_event("voice_command", {
                    "chat_id": self.chat_id,
                    "command": command,
                    "song_name": song
                })

        # 4. AI DJ Mode Check
        dj = analysis.get("dj_recommendation")
        if dj:
            if self.ws_manager:
                await self.ws_manager.broadcast_event("dj_recommendation", {
                    "chat_id": self.chat_id,
                    "recommendation": dj
                })

        # 5. Get Translation
        translation = analysis.get("translated_text", "")
        
        # 6. Broadcast final transcription to WebSocket (with translation)
        if self.ws_manager:
            await self.ws_manager.broadcast_event("transcription", {
                "text": text,
                "translation": translation,
                "is_partial": False
            })
            # To maintain compatibility with existing WS structure, we can also use broadcast_transcription
            # but let's override the broadcast manually for the dashboard
            import json
            from datetime import datetime, timezone
            message = json.dumps({
                "type": "transcription",
                "text": text,
                "translation": translation,
                "is_partial": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await self.ws_manager._broadcast(message)
