"""
AI Agent for VoiceSraver using OpenCode (OpenAI Compatible) API.
Handles Smart Moderation, Voice Command Extraction, and Summaries.
"""

import json
import logging
from openai import AsyncOpenAI
from app import config

logger = logging.getLogger("VoiceSraver.AI")

if config.OPENCODE_API_KEY:
    client = AsyncOpenAI(
        api_key=config.OPENCODE_API_KEY,
        base_url="https://opencode.ai/zen/v1"
    )
    MODEL_NAME = "big-pickle"
else:
    client = None
    logger.warning("OPENCODE_API_KEY is not set! AI features are disabled.")


async def analyze_text_with_ai(text: str) -> dict:
    """
    Sends the transcribed text to OpenCode API to detect abuse, voice commands, and translation.
    """
    default_response = {"is_abusive": False, "voice_command": None, "song_name": None, "dj_recommendation": None, "translated_text": ""}
    
    if not client or not text.strip():
        return default_response
        
    prompt = f"""
    You are an AI assistant analyzing live voice chat transcriptions (mix of Hindi/English).
    Return ONLY a raw JSON object with these exact keys:
    1. "is_abusive" (boolean): True if toxic/abusive/profane.
    2. "voice_command" (string or null): Core command ("play", "pause", "skip", "stop") if requested.
    3. "song_name" (string or null): If command is play, extract the song.
    4. "dj_recommendation" (string or null): If the text expresses a mood (e.g., "I'm sad", "let's party"), recommend a song genre or vibe for the DJ. Else null.
    5. "translated_text" (string): The English translation of the text.

    Text to analyze: "{text}"
    """
    
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        return result
    except Exception as e:
        logger.error(f"AI Analysis Error: {e}")
        return default_response


async def summarize_chat(history: list[str]) -> str:
    """
    Takes a list of transcribed sentences and returns a concise meeting summary.
    """
    if not client or not history:
        return "AI is disabled or chat history is empty."
    
    full_text = "\n".join(history[-50:]) # Limit to last 50 messages to save context limit
    prompt = f"""
    You are an AI meeting assistant. Below is the transcript of a voice chat.
    Please provide a concise, bullet-pointed summary of the key topics discussed, 
    important decisions made, or main themes of the conversation. 
    Keep it clear and professional.

    Transcript:
    {full_text}
    """
    
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"AI Summary Error: {e}")
        return f"Failed to generate summary: {str(e)}"
