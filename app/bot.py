"""
Bot Setup Module — Creates Pyrogram client and wires everything together.
"""

import logging
from pathlib import Path

from pyrogram import Client
from pytgcalls import GroupCallFactory

from app import config
from app.vc_manager import VCManager
from app.ws_manager import WSManager
from app.plugins.vc_commands import setup_vc_commands
from app.plugins.admin_commands import setup_admin_commands

logger = logging.getLogger("VoiceSraver.Bot")


def create_bot(ws_manager: WSManager | None = None) -> tuple[Client, VCManager]:
    """
    Create and configure the Pyrogram client, GroupCallFactory,
    VCManager, and register all command plugins.

    Returns: (pyrogram_app, vc_manager)
    """

    # --- Create Pyrogram Client ---
    if config.STRING_SESSION:
        logger.info("Using string session (cloud mode)")
        app = Client(
            name="voicesraver",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=config.STRING_SESSION,
        )
    else:
        logger.info(f"Using file session: {config.SESSION_NAME}")
        app = Client(
            name=config.SESSION_NAME,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            workdir=str(Path(__file__).parent.parent),
        )

    # --- Create GroupCallFactory ---
    group_call_factory = GroupCallFactory(
        app,
        enable_logs_to_console=(config.LOG_LEVEL == "DEBUG"),
    )

    # --- Create VCManager ---
    vc_manager = VCManager(
        pyrogram_app=app,
        group_call_factory=group_call_factory,
        ws_manager=ws_manager,
    )

    # --- Register Plugins ---
    setup_vc_commands(app, vc_manager)
    setup_admin_commands(app, vc_manager)
    logger.info("\u2705 All plugins registered")

    return app, vc_manager
