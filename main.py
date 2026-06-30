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
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from gtts import gTTS
import uvicorn

from dotenv import load_dotenv
load_dotenv()

from app import config
from app.bot import create_bot
from app.ws_manager import WSManager
from keep_alive import start_keep_alive

class SpeakRequest(BaseModel):
    chat_id: int
    text: str

class MuteRequest(BaseModel):
    chat_id: int
    mute: bool

class JoinGroupRequest(BaseModel):
    invite_link: str

# Logging
logging.basicConfig(
    level=getattr(config, "LOG_LEVEL", "INFO"),
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

    # Start 24/7 Keep Alive thread
    start_keep_alive()

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
            "join_group": "POST /api/join_group",
            "join_vc": "POST /api/joinvc?chat_id=xxx",
            "leave_vc": "POST /api/leavevc",
            "pause": "POST /api/pause",
            "resume": "POST /api/resume",
            "mute": "POST /api/mute",
            "unmute": "POST /api/unmute",
            "speak": "POST /api/speak",
            "summary": "GET /api/summary?chat_id=xxx",
            "websocket": "WS /ws/transcription",
        },
    }

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the Live Web Dashboard."""
    try:
        with open("app/templates/dashboard.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard Template Not Found</h1>", status_code=404)


@app.get("/api/status")
async def api_status():
    if vc_manager is None:
        raise HTTPException(503, "Bot not initialized")
    status = vc_manager.get_status()
    status["ws_connections"] = ws_manager.connection_count
    return status


@app.post("/api/join_group")
async def api_join_group(req: JoinGroupRequest):
    """Make the userbot join a group via invite link."""
    if pyrogram_app is None:
        raise HTTPException(503, "Bot not initialized")
    try:
        chat = await pyrogram_app.join_chat(req.invite_link)
        return {"status": "success", "chat_id": chat.id, "title": chat.title}
    except Exception as e:
        raise HTTPException(400, f"Failed to join group: {e}")


@app.post("/api/joinvc")
async def api_joinvc(chat_id: int):
    if vc_manager is None or pyrogram_app is None:
        raise HTTPException(503, "Bot not initialized")
    if vc_manager.is_active:
        raise HTTPException(409, f"Already in chat {vc_manager.active_chat_id}")
        
    # Check if bot is actually in the group
    try:
        await pyrogram_app.get_chat(chat_id)
    except Exception as e:
        raise HTTPException(400, f"Bot is not in the group or chat_id is invalid: {e}")

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


@app.post("/api/speak")
async def api_speak(req: SpeakRequest):
    """Generates Text-to-Speech and sends it as a voice note to the chat."""
    if not vc_manager.is_active or vc_manager.active_chat_id != req.chat_id:
        raise HTTPException(400, "Bot is not active in this chat.")
    try:
        tts = gTTS(text=req.text, lang='hi')
        file_path = f"tts_{req.chat_id}.mp3"
        tts.save(file_path)
        await pyrogram_app.send_voice(req.chat_id, voice=file_path, caption="🗣️ **VoiceSraver TTS**")
        if os.path.exists(file_path):
            os.remove(file_path)
        return {"status": "success", "message": "Voice note sent!"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/summary")
async def api_summary(chat_id: int):
    """Generates an AI summary of the current VC transcript."""
    if not vc_manager.is_active or vc_manager.active_chat_id != chat_id:
        raise HTTPException(400, "Bot is not active in this chat.")
    if not vc_manager.transcription_manager:
        raise HTTPException(400, "Transcription manager not initialized.")
        
    history = vc_manager.transcription_manager.transcript_history
    if not history:
        return {"summary": "No transcription data available yet."}
        
    from app.ai_agent import summarize_chat
    summary = await summarize_chat(history)
    return {"status": "success", "summary": summary}

@app.get("/api/participants")
async def api_participants(chat_id: int):
    """Returns the list of participants currently in the VC."""
    if not vc_manager.is_active or vc_manager.active_chat_id != chat_id:
        raise HTTPException(400, "Bot is not active in this chat.")
    try:
        participants = await vc_manager.group_call_factory.get_participants(chat_id)
        data = [{"user_id": getattr(p, 'user_id', 'Unknown'), "muted": getattr(p, 'muted', False), "volume": getattr(p, 'volume', 0)} for p in participants]
        return {"status": "success", "participants_count": len(data), "participants": data}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/transcript/download")
async def api_transcript_download(chat_id: int):
    """Downloads the full transcription history as a .txt file."""
    if not vc_manager.is_active or vc_manager.active_chat_id != chat_id:
        raise HTTPException(400, "Bot is not active in this chat.")
    if not vc_manager.transcription_manager:
        raise HTTPException(400, "Transcription manager not initialized.")
        
    history = vc_manager.transcription_manager.transcript_history
    if not history:
        raise HTTPException(404, "No transcription data available.")
        
    file_path = f"transcript_{chat_id}.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("=== VoiceSraver VC Transcript ===\n\n")
        for line in history:
            f.write(f"- {line}\n")
            
    return FileResponse(path=file_path, filename=f"VC_Transcript_{chat_id}.txt", media_type="text/plain", background=None)


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
