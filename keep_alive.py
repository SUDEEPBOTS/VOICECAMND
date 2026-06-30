"""
24/7 Keep Alive Script for Render/Heroku.
Pings the public URL every 10 minutes to prevent the server from sleeping.
"""

import time
import urllib.request
import os
import threading
import logging

logger = logging.getLogger("VoiceSraver.KeepAlive")

def ping_server():
    url = os.getenv("PING_URL")
    if not url:
        logger.info("PING_URL not set. 24/7 self-ping trick is disabled.")
        return

    logger.info(f"Starting 24/7 Keep Alive trick for: {url}")
    while True:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (VoiceSraver KeepAlive)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                logger.info(f"KeepAlive Ping ✅ Status: {response.getcode()}")
        except Exception as e:
            logger.error(f"KeepAlive Ping ❌ Failed: {e}")
        
        # Ping every 10 minutes (600 seconds)
        time.sleep(600)

def start_keep_alive():
    """Starts the keep-alive loop in a background daemon thread."""
    t = threading.Thread(target=ping_server, daemon=True, name="KeepAliveThread")
    t.start()
