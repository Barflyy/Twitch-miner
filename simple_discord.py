# simple_discord.py
import os
import sys
import re
import requests
from datetime import datetime

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord(title, description, color):
    if not WEBHOOK_URL:
        return
    
    try:
        requests.post(WEBHOOK_URL, json={
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }]
        }, timeout=5)
    except:
        pass

class DiscordLogger:
    def __init__(self, stream):
        self.stream = stream
        
    def write(self, text):
        self.stream.write(text)
        
        # Parser et envoyer sur Discord
        if "+10" in text and "points" in text:
            match = re.search(r'for\s+(\w+)', text)
            if match:
                streamer = match.group(1)
                send_discord("💰 Points", f"+10 points sur **{streamer}**", 0xFFD700)
        
        elif "bonus" in text.lower():
            match = re.search(r'(\d+).*?(\w+)', text)
            if match:
                points = match.group(1)
                send_discord("🎁 Bonus", f"+{points} points bonus", 0x9B59B6)
        
        elif "ONLINE" in text:
            match = re.search(r'(\w+).*?ONLINE', text)
            if match:
                streamer = match.group(1)
                send_discord("🟢 Online", f"**{streamer}** en ligne", 0x00FF00)
        
        elif "OFFLINE" in text:
            match = re.search(r'(\w+).*?OFFLINE', text)
            if match:
                streamer = match.group(1)
                send_discord("🔴 Offline", f"**{streamer}** hors ligne", 0xFF0000)
    
    def flush(self):
        self.stream.flush()

# Rediriger stdout
sys.stdout = DiscordLogger(sys.stdout)
sys.stderr = DiscordLogger(sys.stderr)