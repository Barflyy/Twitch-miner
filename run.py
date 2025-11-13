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
streamers_list = os.getenv("STREAMERS", "")
WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
USE_FOLLOWERS = os.getenv("USE_FOLLOWERS", "true").lower() == "true"

if not username or not password:
    print("❌ Configuration manquante")
    sys.exit(1)

# Parser les streamers ou utiliser followers
if USE_FOLLOWERS:
    streamers = []  # Vide = utiliser tous les followers
    print("📺 Mode: TOUS LES FOLLOWERS")
else:
    streamers = [s.strip() for s in streamers_list.split(",") if s.strip()]
    print(f"📺 Streamers spécifiques: {', '.join(streamers)}")

print("🎮 Twitch Points Miner")
print(f"👤 User: {username}")
print(f"🔔 Discord: {'✅' if WEBHOOK else '❌'}")

# Fonction Discord
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
    mode_text = "🌟 **TOUS LES FOLLOWERS**" if USE_FOLLOWERS else f"Streamers: {', '.join(streamers)}"
    send_discord(
        "🚀 Bot Démarré",
        f"Mining pour **{username}**\n{mode_text}",
        0x00FF00
    )

# Handler Discord pour les logs
class DiscordLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.last_messages = {}
        
    def emit(self, record):
        try:
            msg = record.getMessage()
            
            # Anti-spam
            msg_key = msg[:50]
            now = time.time()
            if msg_key in self.last_messages:
                if now - self.last_messages[msg_key] < 30:
                    return
            self.last_messages[msg_key] = now
            
            # Parser les messages
            if "goes ONLINE" in msg or "is ONLINE" in msg:
                import re
                match = re.search(r'\[(\w+)\].*?ONLINE', msg)
                if match:
                    streamer = match.group(1)
                    send_discord("🟢 En Ligne", f"**{streamer}** est en ligne !", 0x00FF00)
                    print(f"🟢 {streamer} ONLINE")
            
            elif "goes OFFLINE" in msg or "is OFFLINE" in msg:
                import re
                match = re.search(r'\[(\w+)\].*?OFFLINE', msg)
                if match:
                    streamer = match.group(1)
                    send_discord("🔴 Hors Ligne", f"**{streamer}** est hors ligne", 0xFF0000)
                    print(f"🔴 {streamer} OFFLINE")
            
            elif "Earned" in msg and "points" in msg:
                import re
                match = re.search(r'Earned\s+(\d+)\s+points.*?\[(\w+)\]', msg)
                if match:
                    points = match.group(1)
                    streamer = match.group(2)
                    send_discord("💰 Points", f"**+{points}** points sur **{streamer}**", 0xFFD700)
                    print(f"💰 +{points} points ({streamer})")
            
            elif "Claimed" in msg and "bonus" in msg:
                import re
                match = re.search(r'Claimed\s+(\d+).*?\[(\w+)\]', msg)
                if match:
                    points = match.group(1)
                    streamer = match.group(2)
                    send_discord("🎁 Bonus", f"**+{points}** bonus sur **{streamer}**", 0x9B59B6)
                    print(f"🎁 +{points} bonus ({streamer})")
            
        except Exception:
            pass

# Configurer le handler
discord_handler = DiscordLogHandler()
discord_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(discord_handler)
logging.getLogger("TwitchChannelPointsMiner").addHandler(discord_handler)

# Importer le bot
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition

print("🔧 Configuration du bot...")

# Configuration avec priorités optimisées
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=password,
    claim_drops_startup=False,
    # Priorités pour followers
    priority=[
        Priority.STREAK,        # Maintenir les streaks
        Priority.DROPS,         # Récupérer les drops
        Priority.ORDER          # Ordre de la liste/followers
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
            percentage=5,                     # Parier 5% des points
            percentage_gap=20,                 # Écart de 20% minimum
            max_points=50000,                  # Maximum 50k points par pari
            filter_condition=FilterCondition(
                by=OutcomeKeys.TOTAL_USERS,
                where=Condition.LTE,
                value=800                      # Seulement si moins de 800 votants
            )
        )
    )
)

print("🚀 Démarrage du mining...")

try:
    if USE_FOLLOWERS:
        # ⭐ UTILISER TOUS LES FOLLOWERS
        print("📋 Récupération de tous les followers...")
        twitch_miner.mine(
            [],                    # Liste vide = utiliser les followers
            followers=True,        # ⭐ ACTIVER LE MODE FOLLOWERS
            blacklist=[],          # Optionnel : blacklist de streamers à ignorer
        )
    else:
        # Utiliser la liste spécifique
        streamer_objects = [Streamer(s) for s in streamers]
        twitch_miner.mine(
            streamer_objects,
            followers=False        # Mode normal
        )
        
except KeyboardInterrupt:
    print("\n⏹️ Arrêt...")
    if WEBHOOK:
        send_discord("⏹️ Arrêt", f"Bot arrêté pour **{username}**", 0xFF0000)
except Exception as e:
    print(f"❌ Erreur: {e}")
    if WEBHOOK:
        send_discord("❌ Erreur", str(e)[:500], 0xFF0000)
    raise