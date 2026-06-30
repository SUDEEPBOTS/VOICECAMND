# 📖 VoiceSraver — Integration Guide (main.md)

## 🎯 Ye Kya Hai?

VoiceSraver ek **API server** hai jo:
1. Telegram VC mein join hota hai
2. Voice sunta hai → text mein convert karta hai (Vosk)
3. Text ko Telegram group mein bhejta hai (live captions)
4. WebSocket pe bhi live stream karta hai
5. REST API se control hota hai (tumhara music bot isko control karega)

---

## ⚠️ Problem: Gana Bajte Waqt Kya Hoga?

```
Music Bot gana bajaye → VoiceSraver bhi gana sune → 
Lyrics transcribe kare → ❌ Ye nahi chahiye!
```

### ✅ Solution: Pause/Resume API

Jab tumhara **music bot** gana play kare:
1. Music bot VoiceSraver ko API call kare: `POST /api/pause`
2. VoiceSraver **transcription band** kar dega (VC mein rahega but sunna band)
3. Gana khatam hone pe: `POST /api/resume`
4. VoiceSraver **phir se sunna shuru** karega

```
Music Bot: "Bhai play karna hai" 
    → POST /api/pause (VoiceSraver ko bolo chup raho)
    → Play song...
    → Song ends
    → POST /api/resume (VoiceSraver ko bolo ab suno)
```

> VoiceSraver VC mein **rehta hai** (leave nahi karta), sirf recording pause/resume hoti hai.
> Isse baar baar join/leave ka overhead nahi hota.

---

## 🏗️ Architecture: Music Bot + VoiceSraver

```
┌──────────────────────┐     ┌─────────────────────────┐
│     Music Bot        │     │     VoiceSraver         │
│  (Separate Account)  │     │   (Separate Account)    │
│                      │     │                          │
│  /play, /skip, /stop │     │  /joinvc, /leavevc      │
│  pytgcalls (play)    │     │  pytgcalls (listen)     │
│                      │     │                          │
│  Gana bajane se      │────>│  POST /api/pause        │
│  pehle pause karo    │     │  (transcription band)   │
│                      │     │                          │
│  Gana khatam hone    │────>│  POST /api/resume       │
│  pe resume karo      │     │  (transcription shuru)  │
└──────────────────────┘     └─────────────────────────┘
          │                             │
          │        Same Group VC        │
          └─────────┐    ┌──────────────┘
                    ▼    ▼
            ┌──────────────────┐
            │   Telegram VC    │
            │   (Group Call)   │
            └──────────────────┘
```

**IMPORTANT: 2 alag Telegram accounts chahiye!**
- Music Bot → Ek userbot/bot account
- VoiceSraver → Doosra userbot account
- Ek hi account se dono kaam nahi ho sakta

---

## 📡 All API Endpoints

### Base URL
```
http://your-vps-ip:8000
```

### 1. `GET /` — Health Check
```bash
curl http://localhost:8000/
```
```json
{
  "name": "VoiceSraver",
  "version": "1.0.0",
  "status": "running"
}
```

### 2. `GET /api/status` — Full Status
```bash
curl http://localhost:8000/api/status
```
```json
{
  "is_active": true,
  "chat_id": -1001234567890,
  "is_connected": true,
  "is_transcribing": true,
  "is_paused": false,
  "audio_queue_size": 12,
  "ws_connections": 2
}
```

### 3. `POST /api/joinvc` — Join Voice Chat
```bash
curl -X POST "http://localhost:8000/api/joinvc?chat_id=-1001234567890"
```
```json
{"status": "joined", "chat_id": -1001234567890}
```

### 4. `POST /api/leavevc` — Leave Voice Chat
```bash
curl -X POST "http://localhost:8000/api/leavevc"
```
```json
{"status": "left"}
```

### 5. `POST /api/pause` — ⏸️ Pause Transcription (MUSIC BOT KE LIYE!)
**Gana play karne se pehle ye call karo**
```bash
curl -X POST "http://localhost:8000/api/pause"
```
```json
{"status": "paused", "message": "Transcription paused. Recording stopped."}
```

### 6. `POST /api/resume` — ▶️ Resume Transcription
**Gana khatam hone ke baad ye call karo**
```bash
curl -X POST "http://localhost:8000/api/resume"
```
```json
{"status": "resumed", "message": "Transcription resumed. Listening again."}
```

### 7. `POST /api/mute` — 🔇 Mute Bot's Outgoing Audio
Bot ka mic band (VC mein kuch nahi bolega)
```bash
curl -X POST "http://localhost:8000/api/mute"
```

### 8. `POST /api/unmute` — 🔊 Unmute Bot's Outgoing Audio
```bash
curl -X POST "http://localhost:8000/api/unmute"
```

---

## 🔌 WebSocket: Live Transcription Stream

### Connect
```
ws://your-vps-ip:8000/ws/transcription
```

### Message Types

**Transcription:**
```json
{
  "type": "transcription",
  "text": "hello how are you",
  "is_partial": false,
  "timestamp": "2026-06-30T13:00:00Z"
}
```

**Event (joined/left/paused/resumed/error):**
```json
{
  "type": "event",
  "event": "paused",
  "data": {"chat_id": -1001234567890},
  "timestamp": "2026-06-30T13:00:00Z"
}
```

### JavaScript Example
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/transcription');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'transcription') {
        if (data.is_partial) {
            console.log('🗣️ Speaking:', data.text);
        } else {
            console.log('✅ Final:', data.text);
        }
    }
    
    if (data.type === 'event') {
        console.log('📢 Event:', data.event, data.data);
    }
};
```

### Python Example
```python
import asyncio, websockets, json

async def listen():
    async with websockets.connect("ws://localhost:8000/ws/transcription") as ws:
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "transcription" and not data["is_partial"]:
                print(f"🎙 {data['text']}")

asyncio.run(listen())
```

---

## 🎵 Music Bot Integration Code

### Tumhare Music Bot mein ye add karo:

```python
import aiohttp

VOICESRAVER_URL = "http://localhost:8000"

async def pause_voicesraver():
    """Gana play karne se pehle call karo"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{VOICESRAVER_URL}/api/pause") as resp:
                return await resp.json()
    except Exception:
        pass  # VoiceSraver down hai toh ignore karo

async def resume_voicesraver():
    """Gana khatam hone ke baad call karo"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{VOICESRAVER_URL}/api/resume") as resp:
                return await resp.json()
    except Exception:
        pass

# === Tumhara existing play command ===
@app.on_message(filters.command("play"))
async def play_song(client, message):
    song_url = get_song_url(message)
    
    # 1. Pehle VoiceSraver ko pause karo
    await pause_voicesraver()
    
    # 2. Gana play karo (tumhara existing code)
    await pytgcalls.play(chat_id, AudioPiped(song_url))

# === Jab gana khatam ho ===
@pytgcalls.on_stream_end()
async def on_song_end(client, update):
    # Gana khatam — VoiceSraver ko resume karo
    await resume_voicesraver()
```

### Flow:
```
User: "/play shape of you"
  │
  ├─ 1. POST /api/pause ──→ VoiceSraver pauses 🔇
  ├─ 2. Play song ─────────→ 🎵 Music plays...
  ├─ 3. Song ends
  └─ 4. POST /api/resume ──→ VoiceSraver resumes 🎙
```

---

## 🎤 Voice Commands (Future - AI)

WebSocket se transcribed text lo, commands detect karo:

```python
async def listen_for_commands():
    async with websockets.connect("ws://localhost:8000/ws/transcription") as ws:
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "transcription" and not data["is_partial"]:
                text = data["text"].lower()
                
                if "play" in text or "chala" in text or "bajao" in text:
                    song_name = extract_song_name(text)
                    await music_bot_play(song_name)
                
                elif "skip" in text or "next" in text:
                    await music_bot_skip()
                
                elif "stop" in text or "band karo" in text:
                    await music_bot_stop()
                
                elif "volume" in text:
                    level = extract_volume(text)
                    await music_bot_volume(level)
```

---

## 📋 Telegram Commands

| Command | Kya karta hai |
|---------|--------------|
| `/joinvc` | VC join, transcription shuru |
| `/leavevc` | VC leave, transcription band |
| `/vcstatus` | Status dekho |
| `/vchelp` | Help dikhao |
| `/ping` | Latency check |
| `/alive` | Bot info + uptime |
| `/restart` | Transcription restart |

---

## 🚀 Quick Start

### Terminal 1: VoiceSraver
```bash
cd ~/VOICESRAVER
source myenv/bin/activate
python main.py
# Server on port 8000
```

### Terminal 2: Music Bot
```bash
cd ~/your-music-bot
python bot.py
```

### Test:
1. Group mein VC start karo
2. `/joinvc` → VoiceSraver joins
3. Bolo kuch → Text aayega ✅
4. `/play song` → Music bot pauses VoiceSraver → gana bajta hai
5. Gana khatam → Resume → Voice phir se sun raha hai
6. `/leavevc` → Done!
