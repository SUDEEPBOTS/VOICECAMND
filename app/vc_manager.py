"""
Voice Chat Manager for VoiceSraver.
Handles GroupCallRaw lifecycle — joining, leaving, audio capture.
"""

import asyncio
import logging
from pathlib import Path

from app import config
from app.transcriber import TranscriptionManager, resample_48k_to_16k
from app.ws_manager import WSManager

logger = logging.getLogger("VoiceSraver.VC")


class VCManager:
    """
    Manages the GroupCallRaw lifecycle.
    Handles joining/leaving VC and connecting audio to transcription.
    """

    def __init__(self, pyrogram_app, group_call_factory, ws_manager: WSManager | None = None):
        self.pyrogram_app = pyrogram_app
        self.group_call_factory = group_call_factory
        self.ws_manager = ws_manager

        self.group_call = None
        self.transcription_manager: TranscriptionManager | None = None
        self.active_chat_id: int | None = None
        self._is_paused: bool = False

    @property
    def is_active(self) -> bool:
        return self.active_chat_id is not None

    @property
    def is_connected(self) -> bool:
        if self.group_call:
            try:
                return self.group_call.is_connected
            except Exception:
                return False
        return False

    async def join(self, chat_id: int, loop: asyncio.AbstractEventLoop):
        """Join a voice chat and start transcription."""
        if self.is_active:
            raise RuntimeError(f"Already active in chat {self.active_chat_id}")

        # Validate model
        model_path = Path(config.VOSK_MODEL_PATH)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Vosk model not found at: {config.VOSK_MODEL_PATH}\n"
                "Run: bash download_model.sh"
            )

        logger.info(f"Joining VC in chat {chat_id}...")

        # Create GroupCallRaw with recording callback
        self.group_call = self.group_call_factory.get_raw_group_call(
            on_recorded_data=self._on_recorded_data
        )

        # Start transcription manager
        self.transcription_manager = TranscriptionManager(
            pyrogram_app=self.pyrogram_app,
            chat_id=chat_id,
            loop=loop,
            ws_manager=self.ws_manager,
        )
        self.transcription_manager.start()

        # Join the VC
        try:
            await self.group_call.start(chat_id)
            self.active_chat_id = chat_id
            logger.info(f"\u2705 Joined VC in chat {chat_id}")

            # Broadcast event
            if self.ws_manager:
                await self.ws_manager.broadcast_event("joined", {"chat_id": chat_id})

        except Exception as e:
            logger.error(f"Failed to join VC: {e}")
            await self._cleanup()
            raise

    async def leave(self):
        """Leave voice chat and stop transcription."""
        if not self.is_active:
            return

        chat_id = self.active_chat_id
        logger.info(f"Leaving VC in chat {chat_id}...")

        await self._cleanup()

        logger.info(f"\u2705 Left VC in chat {chat_id}")

        # Broadcast event
        if self.ws_manager:
            await self.ws_manager.broadcast_event("left", {"chat_id": chat_id})

    async def _cleanup(self):
        """Clean up all resources."""
        if self.transcription_manager:
            self.transcription_manager.stop()
            self.transcription_manager = None

        if self.group_call:
            try:
                await self.group_call.stop()
            except Exception as e:
                logger.warning(f"Error stopping group call: {e}")
            self.group_call = None

        self.active_chat_id = None
        self._is_paused = False

    async def pause_recording(self):
        """Pause sending audio to the transcription callback."""
        if not self.is_active or not self.group_call:
            raise RuntimeError("Not active in any VC")
        self.group_call.pause_recording()
        self._is_paused = True
        logger.info(f"Paused recording in chat {self.active_chat_id}")
        if self.ws_manager:
            await self.ws_manager.broadcast_event("paused", {"chat_id": self.active_chat_id})

    async def resume_recording(self):
        """Resume sending audio to the transcription callback."""
        if not self.is_active or not self.group_call:
            raise RuntimeError("Not active in any VC")
        self.group_call.resume_recording()
        self._is_paused = False
        logger.info(f"Resumed recording in chat {self.active_chat_id}")
        if self.ws_manager:
            await self.ws_manager.broadcast_event("resumed", {"chat_id": self.active_chat_id})

    async def set_mute(self, is_muted: bool):
        """Mute or unmute the bot in the voice chat."""
        if not self.is_active or not self.group_call:
            raise RuntimeError("Not active in any VC")
        await self.group_call.set_is_mute(is_muted)
        logger.info(f"Set bot mute state to {is_muted} in chat {self.active_chat_id}")

    def _on_recorded_data(self, group_call_instance, data: bytes, length: int):
        """
        Callback from GroupCallRaw.
        Receives raw PCM 16-bit 48kHz audio, resamples, feeds to transcriber.
        """
        if self.transcription_manager is None:
            return
        try:
            resampled = resample_48k_to_16k(data)
            if resampled:
                self.transcription_manager.feed_audio(resampled)
        except Exception as e:
            logger.error(f"Audio callback error: {e}")

    def get_status(self) -> dict:
        """Get current status as a dictionary."""
        queue_size = 0
        is_transcribing = False
        if self.transcription_manager:
            queue_size = self.transcription_manager.audio_queue.qsize()
            is_transcribing = self.transcription_manager.is_running

        return {
            "is_active": self.is_active,
            "chat_id": self.active_chat_id,
            "is_connected": self.is_connected,
            "is_transcribing": is_transcribing,
            "is_paused": self._is_paused,
            "audio_queue_size": queue_size,
            "audio_queue_max": config.AUDIO_QUEUE_MAX_SIZE,
            "model_path": config.VOSK_MODEL_PATH,
        }
