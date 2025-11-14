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
    send_discord(
        "🚀 Bot Démarré",
        f"Mining pour **{username}**\nStreamer: JLTomy",
        0x00FF00
    )

# Importer le bot
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority, Events
from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition

print("🔧 Configuration du bot...")

# Configuration Discord avec tous les événements
discord_config = None
if WEBHOOK:
    discord_config = Discord(
        webhook_api=WEBHOOK,
        events=[
            Events.STREAMER_ONLINE,
            Events.STREAMER_OFFLINE,
            Events.GAIN_FOR_RAID,
            Events.GAIN_FOR_CLAIM,
            Events.GAIN_FOR_WATCH,
            Events.GAIN_FOR_WATCH_STREAK,
            Events.BET_WIN,
            Events.BET_LOSE,
            Events.BET_REFUND,
            Events.BET_START,
            Events.BONUS_CLAIM,
            Events.MOMENT_CLAIM,
            Events.JOIN_RAID,
            Events.DROP_CLAIM,
            Events.CHAT_MENTION,
        ]
    )
    print("✅ Notifications Discord activées pour tous les événements")

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
        discord=discord_config,  # ✅ Configuration Discord intégrée
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
    # Suivre uniquement JLTomy
    twitch_miner.mine(
        [Streamer("JLTomy")],
        followers=False
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