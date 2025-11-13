# run.py
import logging
import os
import sys
from discord_notifier import DiscordNotifier

print("🔍 Démarrage du script...")
print(f"📂 Répertoire de travail : {os.getcwd()}")

from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority, Events
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings

# Configuration
username = os.getenv("TWITCH_USERNAME")
auth_token = os.getenv("TWITCH_AUTH_TOKEN")
streamers_list = os.getenv("STREAMERS", "")

# Initialiser Discord Notifier
discord = DiscordNotifier()

if not username:
    discord.error_occurred("TWITCH_USERNAME non défini")
    print("❌ TWITCH_USERNAME non défini")
    sys.exit(1)

if not auth_token:
    discord.error_occurred("TWITCH_AUTH_TOKEN non défini")
    print("❌ TWITCH_AUTH_TOKEN non défini")
    sys.exit(1)

if not streamers_list:
    discord.error_occurred("STREAMERS non défini")
    print("❌ STREAMERS non défini")
    sys.exit(1)

streamers = [s.strip() for s in streamers_list.split(",") if s.strip()]

print("="*50)
print("🎮 Twitch Channel Points Miner")
print("="*50)
print(f"👤 Username: {username}")
print(f"📺 Streamers: {', '.join(streamers)}")
print("="*50)

# Notification de démarrage
discord.bot_started(username, streamers)

# Configuration du miner avec events
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=auth_token,
    claim_drops_startup=False,
    priority=[Priority.STREAK, Priority.DROPS, Priority.ORDER],
    logger_settings=LoggerSettings(
        save=True,
        console_level=logging.INFO,
        file_level=logging.DEBUG,
        emoji=True,
        colored=True,
        color_palette=ColorPalette(
            STREAMER_online="GREEN",
            streamer_offline="red"
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

# Event Handlers pour Discord
def on_streamer_online(event):
    """Appelé quand un streamer passe en ligne"""
    streamer_name = event.get("streamer", "Unknown")
    game = event.get("game", "Unknown")
    discord.streamer_online(streamer_name, game)
    print(f"🟢 {streamer_name} est EN LIGNE ({game})")

def on_streamer_offline(event):
    """Appelé quand un streamer passe hors ligne"""
    streamer_name = event.get("streamer", "Unknown")
    watch_time = event.get("watch_time", 0)
    discord.streamer_offline(streamer_name, watch_time)
    print(f"🔴 {streamer_name} est HORS LIGNE")

def on_points_earned(event):
    """Appelé quand des points sont gagnés"""
    streamer_name = event.get("streamer", "Unknown")
    points = event.get("points", 0)
    reason = event.get("reason", "Watch time")
    total = event.get("total_points", 0)
    discord.points_earned(streamer_name, points, reason, total)
    print(f"💰 +{points} points sur {streamer_name} ({reason})")

def on_claim_bonus(event):
    """Appelé quand un bonus est réclamé"""
    streamer_name = event.get("streamer", "Unknown")
    points = event.get("points", 0)
    discord.claim_bonus(streamer_name, points)
    print(f"🎁 Bonus réclamé: +{points} points ({streamer_name})")

def on_prediction_made(event):
    """Appelé quand une prédiction est faite"""
    streamer_name = event.get("streamer", "Unknown")
    title = event.get("title", "Unknown")
    choice = event.get("choice", "Unknown")
    points = event.get("points", 0)
    discord.prediction_made(streamer_name, title, choice, points)
    print(f"🎲 Prédiction sur {streamer_name}: {choice} ({points} points)")

def on_prediction_result(event):
    """Appelé quand une prédiction est résolue"""
    streamer_name = event.get("streamer", "Unknown")
    result = event.get("result", "Unknown")
    points_won = event.get("points_won", 0)
    discord.prediction_result(streamer_name, result, points_won)
    print(f"📊 Prédiction {result}: {'+' if points_won > 0 else ''}{points_won} points")

# Enregistrer les event handlers
try:
    twitch_miner.events_handler.add_event_handler(Events.STREAMER_ONLINE, on_streamer_online)
    twitch_miner.events_handler.add_event_handler(Events.STREAMER_OFFLINE, on_streamer_offline)
    twitch_miner.events_handler.add_event_handler(Events.POINTS_EARNED, on_points_earned)
    twitch_miner.events_handler.add_event_handler(Events.BONUS_CLAIM, on_claim_bonus)
    twitch_miner.events_handler.add_event_handler(Events.BET_PLACED, on_prediction_made)
    twitch_miner.events_handler.add_event_handler(Events.BET_RESULT, on_prediction_result)
    print("✅ Event handlers Discord configurés")
except Exception as e:
    print(f"⚠️  Impossible de configurer les events: {e}")

# Convertir en objets Streamer
streamer_objects = [Streamer(name) for name in streamers]

print("🚀 Démarrage du mining...")

try:
    twitch_miner.mine(streamer_objects, followers=False)
except Exception as e:
    error_msg = f"Erreur critique: {str(e)}"
    discord.error_occurred(error_msg)
    print(f"❌ {error_msg}")
    raise
