"""
AI Agent for VoiceSraver using Google Gemini API.
Handles Smart Moderation and Voice Command Extraction.
"""

import json
import logging
import google.generativeai as genai
from app import config

logger = logging.getLogger("VoiceSraver.AI")

if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)
    # Using flash model for fast, low-latency text processing
    model = genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config={
            "response_mime_type": "application/json",
        }
    )
else:
    model = None
    logger.warning("GEMINI_API_KEY is not set! AI features (Moderation, Commands) are disabled.")


async def analyze_text_with_ai(text: str) -> dict:
    """
    Sends the transcribed text to Gemini API to detect abuse and voice commands.
    Returns a dict with 'is_abusive', 'voice_command', and 'song_name'.
    """
    default_response = {"is_abusive": False, "voice_command": None, "song_name": None}
    
    if not model or not text.strip():
        return default_response
        
    prompt = f"""
    You are an AI assistant listening to real-time voice chat transcriptions in a mix of Hindi and English.
    Analyze the text and return a JSON object with three keys:
    1. "is_abusive" (boolean): True if the text contains severe profanity, swear words, hate speech, or explicit abuse. False otherwise.
    2. "voice_command" (string or null): If the text contains a clear command directed at a music bot (e.g., "play song", "skip", "pause", "stop", "volume up"), extract the core intent (e.g., "play", "pause", "skip", "stop"). Return null if it's just casual conversation.
    3. "song_name" (string or null): If the voice_command is "play", extract the name of the song requested. Otherwise return null.

    Text to analyze: "{text}"
    """
    
    try:
        response = await model.generate_content_async(prompt)
        result = json.loads(response.text)
        return result
    except Exception as e:
        logger.error(f"AI Analysis Error: {e}")
        return default_response


async def summarize_chat(history: list[str]) -> str:
    """
    Takes a list of transcribed sentences and returns a concise meeting summary.
    """
    if not model or not history:
        return "AI is disabled or chat history is empty."
    
    full_text = "\n".join(history)
    prompt = f"""
    You are an AI meeting assistant. Below is the transcript of a voice chat.
    Please provide a concise, bullet-pointed summary of the key topics discussed, 
    important decisions made, or main themes of the conversation. 
    Keep it clear and professional.

    Transcript:
    {full_text}
    """
    
    try:
        # Override response type just for this call to get plain text
        summary_model = genai.GenerativeModel('gemini-1.5-flash')
        response = await summary_model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        logger.error(f"AI Summary Error: {e}")
        return f"Failed to generate summary: {str(e)}"
