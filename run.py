# run.py
import logging
import os
import sys
import time

print("🔍 Démarrage du script...")
print(f"📂 Répertoire: {os.getcwd()}")
print(f"📁 Fichiers: {os.listdir('.')}")

# Créer le dossier logs s'il n'existe pas
os.makedirs("logs", exist_ok=True)
print(f"📋 Dossier logs créé/vérifié")

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
    print("❌ Variables manquantes")
    sys.exit(1)

streamers = [s.strip() for s in streamers_list.split(",") if s.strip()]

print("="*50)
print("🎮 Twitch Channel Points Miner")
print("="*50)
print(f"👤 Username: {username}")
print(f"📺 Streamers: {', '.join(streamers)}")
print("="*50)

# Démarrer le watcher
watcher = LogWatcher()
watcher.start()

# Notification de démarrage
if watcher.enabled:
    watcher.send_discord(
        "🚀 Bot Démarré",
        f"Mining démarré pour **{username}**",
        0x00FF00,
        [
            {"name": "📺 Streamers suivis", "value": ", ".join(streamers[:5]), "inline": False},
            {"name": "📈 Nombre total", "value": str(len(streamers)), "inline": True}
        ]
    )

# Attendre que le watcher soit prêt
time.sleep(3)

# Configuration du miner avec VERBOSE logging
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=auth_token,
    claim_drops_startup=False,
    priority=[Priority.STREAK, Priority.DROPS, Priority.ORDER],
    logger_settings=LoggerSettings(
        save=True,
        less=False,  # IMPORTANT: Ne pas réduire les logs
        console_level=logging.DEBUG,  # VERBOSE
        file_level=logging.DEBUG,     # VERBOSE
        emoji=True,
        colored=True,
        color_palette=ColorPalette(
            STREAMER_online="GREEN",
            streamer_offline="red",
            BET_wiped="YELLOW"
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

# Configurer le logging Python standard aussi
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/miner.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

streamer_objects = [Streamer(name) for name in streamers]

print("🚀 Démarrage du mining...")
print("🔊 Mode VERBOSE activé")

try:
    twitch_miner.mine(streamer_objects, followers=False)
except KeyboardInterrupt:
    print("\n⏹️  Arrêt...")
    watcher.stop()
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    watcher.stop()
    raise