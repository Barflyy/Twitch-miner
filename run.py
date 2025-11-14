# run.py
import logging
import os
import sys
import json
from pathlib import Path

# Configuration
username = os.getenv("TWITCH_USERNAME")
auth_token = os.getenv("TWITCH_AUTH_TOKEN")  # Token OAuth au lieu de password

if not username or not auth_token:
    print("❌ Configuration manquante : TWITCH_USERNAME et TWITCH_AUTH_TOKEN requis")
    sys.exit(1)

# Mode FOLLOWERS : Suit automatiquement tous vos follows Twitch
# Blacklist optionnelle : streamers à exclure
blacklist_file = Path("blacklist.json")
if blacklist_file.exists():
    with open(blacklist_file, 'r') as f:
        blacklist = json.load(f)
    print(f"🚫 Blacklist: {', '.join(blacklist) if blacklist else 'Aucune'}")
else:
    blacklist = []
    # Créer le fichier blacklist vide
    with open(blacklist_file, 'w') as f:
        json.dump(blacklist, f, indent=2)
    print(f"🚫 Blacklist: Aucune")

print("🎮 Twitch Points Miner")
print(f"👤 User: {username}")

# Pas de fonction webhook - le bot Discord gère toutes les notifications

# Importer le bot
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority, Events
from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition

print("🔧 Configuration du bot...")

# Configuration Discord - SEULEMENT Bot Discord (pas de webhook)
USE_DISCORD_BOT = os.getenv("USE_DISCORD_BOT", "true").lower() == "true"

discord_config = None
if USE_DISCORD_BOT:
    # Mode Bot Discord uniquement (pas de spam webhook)
    discord_config = Discord(
        webhook_api="",  # Pas de webhook
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
        ],
        use_bot=True  # Mode bot Discord avec fiches éditables
    )
    print("✅ Mode Bot Discord activé (fiches éditables, pas de spam webhook)")

# Configuration avec priorités optimisées
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=auth_token,  # Utilise le token OAuth comme password
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

# Mode TEST : Un seul streamer pour les tests
test_streamers = [
    "Viper"
]

print("🚀 Démarrage du mining en mode TEST (1 streamer)...")
print(f"📋 Le bot va suivre : {test_streamers[0]}")

try:
    # Mode TEST : Un seul streamer pour les tests
    # Les streamers dans blacklist.json seront exclus
    twitch_miner.mine(
        streamers=test_streamers,  # Viper uniquement
        blacklist=blacklist,  # Streamers à exclure
        followers=False  # Mode test : pas de followers automatiques
    )
        
except KeyboardInterrupt:
    print("\n⏹️ Arrêt...")
except Exception as e:
    print(f"❌ Erreur: {e}")
    raise