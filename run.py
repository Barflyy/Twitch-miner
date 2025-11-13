# run.py
import logging
import os
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition, DelayMode

# Variables d'environnement
username = os.getenv("TWITCH_USERNAME", "votre_username")
auth_token = os.getenv("TWITCH_AUTH_TOKEN", None)

# Liste des streamers (modifiez selon vos préférences)
streamers = os.getenv("STREAMERS", "").split(",") if os.getenv("STREAMERS") else []

if not streamers:
    print("⚠️  Aucun streamer configuré. Ajoutez la variable STREAMERS sur Railway")
    print("Exemple: streamer1,streamer2,streamer3")
    exit(1)

twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=auth_token,  # Peut être None, le bot demandera de se connecter
    claim_drops_startup=False,
    priority=[
        Priority.STREAK,  # Priorité à maintenir les streaks
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

# Convertir la liste de noms en objets Streamer
streamer_objects = [Streamer(name.strip()) for name in streamers if name.strip()]

print(f"🚀 Démarrage du miner pour {username}")
print(f"📺 Streamers: {', '.join(streamers)}")

twitch_miner.mine(streamer_objects, followers=False)
