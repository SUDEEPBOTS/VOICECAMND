"""
Admin Commands Plugin — /ping, /alive, /restart
"""

import asyncio
import logging
import time

from pyrogram import Client, filters
from pyrogram.types import Message

from app import config, __version__
from app.vc_manager import VCManager

logger = logging.getLogger("VoiceSraver.Admin")

# Track bot start time
_start_time = time.time()


def _is_admin(user_id: int) -> bool:
    if not config.ADMIN_IDS:
        return True
    return user_id in config.ADMIN_IDS


def _format_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def setup_admin_commands(app: Client, vc_manager: VCManager):
    """Register admin command handlers."""

    @app.on_message(filters.command("ping"))
    async def cmd_ping(client: Client, message: Message):
        start = time.time()
        msg = await message.reply("\ud83c\udfd3 Pong!")
        latency = (time.time() - start) * 1000
        await msg.edit_text(f"\ud83c\udfd3 Pong! `{latency:.0f}ms`")

    @app.on_message(filters.command("alive"))
    async def cmd_alive(client: Client, message: Message):
        uptime = time.time() - _start_time
        from pathlib import Path
        model_exists = Path(config.VOSK_MODEL_PATH).exists()
        me = await client.get_me()

        await message.reply(
            "\ud83e\udd16 **VoiceSraver is Alive!**\n\n"
            f"\ud83d\udcbb Version: `{__version__}`\n"
            f"\ud83d\udc64 Account: {me.first_name} (@{me.username})\n"
            f"\u23f1 Uptime: `{_format_uptime(uptime)}`\n"
            f"\ud83e\udde0 Model: {'\u2705 Loaded' if model_exists else '\u274c Not found'}\n"
            f"\ud83d\udce1 VC Active: {'Yes' if vc_manager.is_active else 'No'}\n"
            f"\ud83d\udd12 Admins: {len(config.ADMIN_IDS) if config.ADMIN_IDS else 'All'}"
        )

    @app.on_message(filters.command("restart") & (filters.group | filters.supergroup))
    async def cmd_restart(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else 0
        if not _is_admin(user_id):
            await message.reply("\u26d4 You are not authorized.")
            return

        if not vc_manager.is_active:
            await message.reply("\u26a0\ufe0f Not in any VC to restart!")
            return

        chat_id = vc_manager.active_chat_id
        status_msg = await message.reply("\ud83d\udd04 Restarting transcription...")

        try:
            await vc_manager.leave()
            await asyncio.sleep(1)
            loop = asyncio.get_event_loop()
            await vc_manager.join(chat_id, loop)
            await status_msg.edit_text("\u2705 Transcription restarted successfully!")
        except Exception as e:
            logger.error(f"Restart error: {e}", exc_info=True)
            await status_msg.edit_text(f"\u274c Restart failed:\n`{e}`")
