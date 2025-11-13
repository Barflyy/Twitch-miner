# run.py
import logging
import os
import sys
from discord_events import DiscordWebhook

print("🔍 Démarrage du script...")

from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition

# Configuration depuis les variables d'environnement
username = os.getenv("TWITCH_USERNAME")
auth_token = os.getenv("TWITCH_AUTH_TOKEN")
streamers_list = os.getenv("STREAMERS", "")

# Validation
if not username:
    print("❌ TWITCH_USERNAME non défini")
    sys.exit(1)

if not auth_token:
    print("❌ TWITCH_AUTH_TOKEN non défini")
    sys.exit(1)

if not streamers_list:
    print("❌ STREAMERS non défini")
    sys.exit(1)

streamers = [s.strip() for s in streamers_list.split(",") if s.strip()]

print("="*50)
print("🎮 Twitch Channel Points Miner")
print("="*50)
print(f"👤 Username: {username}")
print(f"📺 Streamers: {', '.join(streamers)}")
print("="*50)

# Initialiser Discord webhook
discord = DiscordWebhook()

# Envoyer notification de démarrage
if discord.enabled:
    discord.send_embed(
        title="🚀 Bot Démarré",
        description=f"Mining démarré pour **{username}**",
        color=0x00FF00,
        fields=[
            {"name": "📺 Streamers", "value": ", ".join(streamers[:5]), "inline": False},
            {"name": "📊 Total", "value": str(len(streamers)), "inline": True}
        ]
    )

# Configuration du TwitchChannelPointsMiner
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=auth_token,
    claim_drops_startup=False,
    priority=[
        Priority.STREAK,
        Priority.DROPS,
        Priority.ORDER
    ],
    logger_settings=LoggerSettings(
        save=True,
        less=False,
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
            filter_condition=FilterCondition(
                by=OutcomeKeys.TOTAL_USERS,
                where=Condition.LTE,
                value=800
            )
        )
    )
)

# ⭐ IMPORTANT: Intercepter les events avec notre Discord webhook
original_fire_event = twitch_miner.events_handler.fire_event if hasattr(twitch_miner, 'events_handler') else None

def custom_fire_event(event_name, event_data=None):
    """Intercepte tous les events et les envoie sur Discord"""
    # Appeler l'event handler original si il existe
    if original_fire_event:
        try:
            original_fire_event(event_name, event_data)
        except:
            pass
    
    # Envoyer sur Discord
    if discord.enabled and event_data:
        discord.on_event(event_name, event_data)
    
    # Log dans la console
    print(f"🔔 Event: {event_name}")

# Remplacer le fire_event
if hasattr(twitch_miner, 'events_handler'):
    twitch_miner.events_handler.fire_event = custom_fire_event
    print("✅ Event handler Discord configuré")

# Alternative: Utiliser les hooks du logger
class DiscordLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = record.getMessage()
            
            # Parser les messages de log pour déclencher des events Discord
            if "+10 points" in msg or "watching" in msg.lower():
                # Extraire le streamer
                import re
                match = re.search(r'for\s+(\w+)', msg)
                if match and discord.enabled:
                    streamer_name = match.group(1)
                    discord.on_event("gain_points", {
                        "streamer": {"username": streamer_name},
                        "points": 10,
                        "reason": "Watch",
                        "balance": 0
                    })
            
            elif "bonus" in msg.lower() and "claim" in msg.lower():
                import re
                match = re.search(r'(\d+).*?on\s+(\w+)', msg)
                if match and discord.enabled:
                    points = int(match.group(1))
                    streamer_name = match.group(2)
                    discord.on_event("claim_bonus", {
                        "streamer": {"username": streamer_name},
                        "points": points
                    })
        except:
            pass

# Ajouter le handler de log
discord_log_handler = DiscordLogHandler()
discord_log_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(discord_log_handler)

# Convertir en objets Streamer
streamer_objects = [Streamer(name) for name in streamers]

print("🚀 Démarrage du mining...")
print("🔔 Notifications Discord actives" if discord.enabled else "⚠️  Notifications Discord désactivées")

try:
    twitch_miner.mine(streamer_objects, followers=False)
except KeyboardInterrupt:
    print("\n⏹️  Arrêt du bot...")
    if discord.enabled:
        discord.send_embed(
            title="⏹️ Bot Arrêté",
            description=f"Mining arrêté pour **{username}**",
            color=0xFF0000
        )
except Exception as e:
    error_msg = str(e)
    print(f"❌ Erreur: {error_msg}")
    if discord.enabled:
        discord.send_embed(
            title="⚠️ Erreur Critique",
            description=f"```{error_msg[:500]}```",
            color=0xFF0000
        )
    raise
