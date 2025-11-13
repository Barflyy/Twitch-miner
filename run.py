# run.py
import logging
import os
import sys
import requests
from datetime import datetime
from threading import Thread
import time

# Configuration
username = os.getenv("TWITCH_USERNAME")
password = os.getenv("TWITCH_AUTH_TOKEN") 
streamers = os.getenv("STREAMERS", "").split(",")
WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")

if not username or not password or not streamers:
    print("❌ Configuration manquante")
    sys.exit(1)

print("🎮 Twitch Points Miner")
print(f"👤 User: {username}")
print(f"📺 Streamers: {', '.join(streamers)}")
print(f"🔔 Discord: {'✅' if WEBHOOK else '❌'}")

# Fonction pour envoyer sur Discord
def send_discord(title, description, color):
    if not WEBHOOK:
        return
    try:
        requests.post(WEBHOOK, json={
            "embeds": [{
                "title": title,
                "description": description[:2000],
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "Twitch Miner"}
            }]
        }, timeout=5)
    except:
        pass

# Notification de démarrage
if WEBHOOK:
    send_discord(
        "🚀 Bot Démarré",
        f"Mining pour **{username}**\nStreamers: {', '.join(streamers)}",
        0x00FF00
    )

# Handler personnalisé pour intercepter les logs
class DiscordLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.last_messages = {}
        
    def emit(self, record):
        try:
            msg = record.getMessage()
            
            # Anti-spam : pas le même message dans les 30s
            msg_key = msg[:50]
            now = time.time()
            if msg_key in self.last_messages:
                if now - self.last_messages[msg_key] < 30:
                    return
            self.last_messages[msg_key] = now
            
            # Parser les messages importants
            # Streamer ONLINE
            if "goes ONLINE" in msg or "is ONLINE" in msg:
                import re
                match = re.search(r'\[(\w+)\].*?ONLINE', msg)
                if match:
                    streamer = match.group(1)
                    send_discord("🟢 En Ligne", f"**{streamer}** est en ligne !", 0x00FF00)
                    print(f"🟢 {streamer} ONLINE")
            
            # Streamer OFFLINE
            elif "goes OFFLINE" in msg or "is OFFLINE" in msg:
                import re
                match = re.search(r'\[(\w+)\].*?OFFLINE', msg)
                if match:
                    streamer = match.group(1)
                    send_discord("🔴 Hors Ligne", f"**{streamer}** est hors ligne", 0xFF0000)
                    print(f"🔴 {streamer} OFFLINE")
            
            # Points gagnés
            elif "Earned" in msg and "points" in msg:
                import re
                match = re.search(r'Earned\s+(\d+)\s+points.*?\[(\w+)\]', msg)
                if match:
                    points = match.group(1)
                    streamer = match.group(2)
                    send_discord("💰 Points", f"**+{points}** points sur **{streamer}**", 0xFFD700)
                    print(f"💰 +{points} points ({streamer})")
            
            # Bonus claim
            elif "Claimed" in msg and "bonus" in msg:
                import re
                match = re.search(r'Claimed\s+(\d+).*?\[(\w+)\]', msg)
                if match:
                    points = match.group(1)
                    streamer = match.group(2)
                    send_discord("🎁 Bonus", f"**+{points}** bonus sur **{streamer}**", 0x9B59B6)
                    print(f"🎁 +{points} bonus ({streamer})")
            
            # Prédiction placée
            elif "Bet placed" in msg:
                import re
                match = re.search(r'(\d+).*?\[(\w+)\]', msg)
                if match:
                    points = match.group(1)
                    streamer = match.group(2)
                    send_discord("🎲 Prédiction", f"**{points}** points pariés sur **{streamer}**", 0x3498DB)
                    print(f"🎲 {points} pts pariés ({streamer})")
            
            # Prédiction gagnée
            elif "won" in msg and ("bet" in msg.lower() or "prediction" in msg.lower()):
                import re
                match = re.search(r'(\d+).*?\[(\w+)\]', msg)
                if match:
                    points = match.group(1)
                    streamer = match.group(2)
                    send_discord("🎉 Gagné", f"**+{points}** points gagnés sur **{streamer}**", 0x00FF00)
                    print(f"🎉 +{points} pts gagnés ({streamer})")
            
            # Prédiction perdue
            elif "lost" in msg and ("bet" in msg.lower() or "prediction" in msg.lower()):
                import re
                match = re.search(r'(\d+).*?\[(\w+)\]', msg)
                if match:
                    points = match.group(1)
                    streamer = match.group(2)
                    send_discord("😢 Perdu", f"**-{points}** points perdus sur **{streamer}**", 0xFF0000)
                    print(f"😢 -{points} pts perdus ({streamer})")
            
        except Exception as e:
            pass

# Configurer le handler AVANT l'import
discord_handler = DiscordLogHandler()
discord_handler.setLevel(logging.INFO)

# Ajouter à tous les loggers possibles
logging.getLogger().addHandler(discord_handler)
logging.getLogger("TwitchChannelPointsMiner").addHandler(discord_handler)
logging.getLogger("TwitchChannelPointsMiner.classes.Twitch").addHandler(discord_handler)
logging.getLogger("TwitchChannelPointsMiner.classes.Bet").addHandler(discord_handler)

# MAINTENANT importer le bot
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings

print("🔧 Configuration du bot...")

twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=password,
    claim_drops_startup=False,
    priority=[
        Priority.STREAK,
        Priority.DROPS,
        Priority.ORDER
    ],
    logger_settings=LoggerSettings(
        save=True,
        console_level=logging.INFO,
        file_level=logging.DEBUG,
        emoji=True,
        colored=True,
        color_palette=ColorPalette(
            STREAMER_online="GREEN",
            streamer_offline="red",
            BET_lose="red",
            BET_won="green"
        ),
    ),
    streamer_settings=StreamerSettings(
        make_predictions=True,
        follow_raid=True,
        claim_drops=True,
        watch_streak=True,
        bet=BetSettings(
            strategy=Strategy.SMART,
            percentage=5,
            percentage_gap=20,
            max_points=50000,
        )
    )
)

print("🚀 Démarrage du mining...")

# Miner
try:
    twitch_miner.mine([Streamer(s.strip()) for s in streamers])
except KeyboardInterrupt:
    print("\n⏹️ Arrêt...")
    if WEBHOOK:
        send_discord("⏹️ Arrêt", f"Bot arrêté pour **{username}**", 0xFF0000)
except Exception as e:
    print(f"❌ Erreur: {e}")
    if WEBHOOK:
        send_discord("❌ Erreur", str(e)[:500], 0xFF0000)
    raise