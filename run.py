# run.py
import logging
import os
import sys
import time

print("🔍 Démarrage du bot...")

# Créer dossier logs
os.makedirs("logs", exist_ok=True)

from log_watcher import LogWatcher
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition

# Configuration
username = os.getenv("TWITCH_USERNAME")
auth_token = os.getenv("TWITCH_AUTH_TOKEN")
streamers_list = os.getenv("STREAMERS", "")

if not username or not auth_token or not streamers_list:
    print("❌ Configuration manquante")
    sys.exit(1)

streamers = [s.strip() for s in streamers_list.split(",") if s.strip()]

print(f"👤 User: {username}")
print(f"📺 Streamers: {', '.join(streamers)}")

# Démarrer monitoring Discord
watcher = LogWatcher()
watcher.start()

# Notification de démarrage
if watcher.enabled:
    watcher.send_discord(
        "🚀 Bot Démarré",
        f"Mining pour **{username}**",
        0x00FF00,
        [
            {"name": "📺 Streamers", "value": ", ".join(streamers), "inline": False},
        ]
    )

time.sleep(2)

# Configuration du miner
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=auth_token,
    claim_drops_startup=False,
    priority=[Priority.STREAK, Priority.DROPS, Priority.ORDER],
    logger_settings=LoggerSettings(
        save=True,
        less=False,
        console_level=logging.INFO,  # INFO au lieu de DEBUG
        file_level=logging.DEBUG,
        emoji=True,
        colored=True,
        color_palette=ColorPalette(
            STREAMER_online="GREEN",
            streamer_offline="red",
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

streamer_objects = [Streamer(name) for name in streamers]

print("🚀 Mining démarré...")

try:
    twitch_miner.mine(streamer_objects, followers=False)
except KeyboardInterrupt:
    print("\n⏹️  Arrêt...")
    watcher.stop()
except Exception as e:
    print(f"❌ Erreur: {e}")
    watcher.stop()
    raise