"""
VC Commands Plugin — /joinvc, /leavevc, /vcstatus, /vchelp
"""

import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from app import config
from app.vc_manager import VCManager

logger = logging.getLogger("VoiceSraver.CMD")


def _is_admin(user_id: int) -> bool:
    if not config.ADMIN_IDS:
        return True
    return user_id in config.ADMIN_IDS


def setup_vc_commands(app: Client, vc_manager: VCManager):
    """Register VC command handlers on the Pyrogram client."""

    @app.on_message(filters.command("joinvc") & (filters.group | filters.supergroup))
    async def cmd_joinvc(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else 0
        if not _is_admin(user_id):
            await message.reply("\u26d4 You are not authorized.")
            return

        if vc_manager.is_active:
            if vc_manager.active_chat_id == message.chat.id:
                await message.reply("\u26a0\ufe0f Already transcribing in this VC!")
            else:
                await message.reply(
                    f"\u26a0\ufe0f Already active in chat `{vc_manager.active_chat_id}`.\n"
                    "Use /leavevc first."
                )
            return

        status_msg = await message.reply("\ud83d\udd04 Joining voice chat...")

        try:
            loop = asyncio.get_event_loop()
            await vc_manager.join(message.chat.id, loop)
            await status_msg.edit_text(
                "\u2705 **Joined Voice Chat!**\n\n"
                "\ud83c\udf99 Live transcription is now active.\n"
                "Everything spoken in VC will appear as text here.\n\n"
                "Use /leavevc to stop."
            )
        except FileNotFoundError as e:
            await status_msg.edit_text(f"\u274c {e}")
        except Exception as e:
            logger.error(f"Join VC error: {e}", exc_info=True)
            await status_msg.edit_text(f"\u274c Failed to join VC:\n`{e}`")

    @app.on_message(filters.command("leavevc") & (filters.group | filters.supergroup))
    async def cmd_leavevc(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else 0
        if not _is_admin(user_id):
            await message.reply("\u26d4 You are not authorized.")
            return

        if not vc_manager.is_active:
            await message.reply("\u26a0\ufe0f Not in any voice chat!")
            return

        status_msg = await message.reply("\ud83d\udd04 Leaving voice chat...")
        try:
            await vc_manager.leave()
            await status_msg.edit_text(
                "\u2705 **Left Voice Chat**\n\n"
                "Transcription stopped. All resources cleaned up."
            )
        except Exception as e:
            logger.error(f"Leave VC error: {e}", exc_info=True)
            await status_msg.edit_text(f"\u274c Error leaving VC:\n`{e}`")

    @app.on_message(filters.command("vcstatus"))
    async def cmd_vcstatus(client: Client, message: Message):
        status = vc_manager.get_status()
        if status["is_active"]:
            await message.reply(
                "\ud83d\udcca **VoiceSraver Status**\n\n"
                f"\ud83d\udfe2 State: Active\n"
                f"\ud83d\udccd Chat: `{status['chat_id']}`\n"
                f"\ud83d\udd17 VC Connected: {'Yes' if status['is_connected'] else 'No'}\n"
                f"\ud83c\udf99 Transcribing: {'Yes \u2705' if status['is_transcribing'] else 'No \u274c'}\n"
                f"\ud83d\udce6 Audio Queue: {status['audio_queue_size']}/{status['audio_queue_max']}\n"
                f"\ud83d\udcdd Model: `{status['model_path']}`"
            )
        else:
            await message.reply(
                "\ud83d\udcca **VoiceSraver Status**\n\n"
                "\ud83d\udd34 State: Idle\n"
                "Use /joinvc in a group to start."
            )

    @app.on_message(filters.command("vchelp"))
    async def cmd_vchelp(client: Client, message: Message):
        await message.reply(
            "\ud83c\udf99 **VoiceSraver Bot \u2014 Live VC Transcription**\n\n"
            "**Commands:**\n"
            "\u2022 `/joinvc` \u2014 Join VC & start transcription\n"
            "\u2022 `/leavevc` \u2014 Leave VC & stop transcription\n"
            "\u2022 `/vcstatus` \u2014 Check bot status\n"
            "\u2022 `/vchelp` \u2014 Show this help\n"
            "\u2022 `/ping` \u2014 Check latency\n"
            "\u2022 `/alive` \u2014 Bot info & uptime\n\n"
            "**API Endpoints:**\n"
            "\u2022 `GET /api/status` \u2014 Bot status\n"
            "\u2022 `POST /api/joinvc?chat_id=xxx` \u2014 Join VC\n"
            "\u2022 `POST /api/leavevc` \u2014 Leave VC\n"
            "\u2022 `WS /ws/transcription` \u2014 Live stream\n\n"
            "**How it works:**\n"
            "1. Start a voice chat in your group\n"
            "2. Send /joinvc\n"
            "3. Bot listens & transcribes\n"
            "4. Send /leavevc to stop"
        )
