"""
VoiceSraver — Main Entry Point
FastAPI server + Pyrogram bot + WebSocket

Endpoints:
  GET  /                    — Health check / welcome
  GET  /api/status          — Bot & VC status
  POST /api/joinvc          — Join a voice chat  
  POST /api/leavevc         — Leave voice chat
  WS   /ws/transcription    — Real-time transcription stream
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app import config
from app.bot import create_bot
from app.ws_manager import WSManager

# Logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("VoiceSraver")

# Shared instances
ws_manager = WSManager(max_connections=config.WS_MAX_CONNECTIONS)
pyrogram_app = None
vc_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global pyrogram_app, vc_manager

    if config.API_ID == 0 or config.API_HASH == "your_api_hash_here":
        logger.error("❌ Set API_ID and API_HASH in .env or environment!")
        logger.error("   Get them from: https://my.telegram.org")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("  🎙 VoiceSraver Starting...")
    logger.info("=" * 50)

    pyrogram_app, vc_manager = create_bot(ws_manager)

    await pyrogram_app.start()
    me = await pyrogram_app.get_me()
    logger.info(f"  ✅ Logged in as: {me.first_name} (@{me.username})")
    logger.info(f"  📝 Model: {config.VOSK_MODEL_PATH}")
    logger.info(f"  🔒 Admins: {config.ADMIN_IDS or 'ALL'}")
    logger.info(f"  🌐 API: http://0.0.0.0:{config.FASTAPI_PORT}")
    logger.info(f"  🔌 WS: ws://0.0.0.0:{config.FASTAPI_PORT}/ws/transcription")
    logger.info("=" * 50)

    yield

    logger.info("Shutting down...")
    if vc_manager and vc_manager.is_active:
        await vc_manager.leave()
    await pyrogram_app.stop()
    logger.info("Goodbye! 👋")


app = FastAPI(
    title="VoiceSraver API",
    description="Telegram VC Live Transcription Bot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ====== REST Endpoints ======

@app.get("/")
async def root():
    return {
        "name": "VoiceSraver",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "status": "GET /api/status",
            "join_vc": "POST /api/joinvc?chat_id=xxx",
            "leave_vc": "POST /api/leavevc",
            "pause": "POST /api/pause",
            "resume": "POST /api/resume",
            "mute": "POST /api/mute",
            "unmute": "POST /api/unmute",
            "websocket": "WS /ws/transcription",
        },
    }


@app.get("/api/status")
async def api_status():
    if vc_manager is None:
        raise HTTPException(503, "Bot not initialized")
    status = vc_manager.get_status()
    status["ws_connections"] = ws_manager.connection_count
    return status


@app.post("/api/joinvc")
async def api_joinvc(chat_id: int):
    if vc_manager is None:
        raise HTTPException(503, "Bot not initialized")
    if vc_manager.is_active:
        raise HTTPException(409, f"Already in chat {vc_manager.active_chat_id}")
    try:
        loop = asyncio.get_event_loop()
        await vc_manager.join(chat_id, loop)
        return {"status": "joined", "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/leavevc")
async def api_leavevc():
    if vc_manager is None:
        raise HTTPException(503, "Bot not initialized")
    if not vc_manager.is_active:
        raise HTTPException(409, "Not in any VC")
    try:
        await vc_manager.leave()
        return {"status": "left"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/pause")
async def api_pause():
    """Pause transcription (ignore audio)."""
    if vc_manager is None:
        raise HTTPException(503, "Bot not initialized")
    try:
        await vc_manager.pause_recording()
        return {"status": "paused", "message": "Transcription paused. Recording stopped."}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/resume")
async def api_resume():
    """Resume transcription (start listening again)."""
    if vc_manager is None:
        raise HTTPException(503, "Bot not initialized")
    try:
        await vc_manager.resume_recording()
        return {"status": "resumed", "message": "Transcription resumed. Listening again."}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/mute")
async def api_mute():
    """Mute the bot's outgoing audio in the VC."""
    if vc_manager is None:
        raise HTTPException(503, "Bot not initialized")
    try:
        await vc_manager.set_mute(True)
        return {"status": "muted"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/unmute")
async def api_unmute():
    """Unmute the bot's outgoing audio in the VC."""
    if vc_manager is None:
        raise HTTPException(503, "Bot not initialized")
    try:
        await vc_manager.set_mute(False)
        return {"status": "unmuted"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ====== WebSocket ======

@app.websocket("/ws/transcription")
async def ws_transcription(websocket: WebSocket):
    connected = await ws_manager.connect(websocket)
    if not connected:
        return
    try:
        if vc_manager:
            await websocket.send_json({"type": "status", "data": vc_manager.get_status()})
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        ws_manager.disconnect(websocket)


# ====== Entry Point ======

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.FASTAPI_HOST,
        port=config.FASTAPI_PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower(),
    )
