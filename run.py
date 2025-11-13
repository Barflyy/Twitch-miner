# run.py
import logging
import os
import sys
import requests
from datetime import datetime

print("🔍 Démarrage du script...")

from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority, Events
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition

# Configuration
username = os.getenv("TWITCH_USERNAME")
auth_token = os.getenv("TWITCH_AUTH_TOKEN")
streamers_list = os.getenv("STREAMERS", "")
discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")

if not username or not auth_token or not streamers_list:
    print("❌ Variables manquantes")
    sys.exit(1)

streamers = [s.strip() for s in streamers_list.split(",") if s.strip()]

print("="*50)
print("🎮 Twitch Channel Points Miner")
print(f"👤 Username: {username}")
print(f"📺 Streamers: {', '.join(streamers)}")
print(f"🔔 Discord: {'✅ Activé' if discord_webhook else '❌ Désactivé'}")
print("="*50)

# Fonction pour envoyer sur Discord
def send_discord(title, description, color, fields=None):
    if not discord_webhook:
        return
    
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Twitch Points Miner"}
    }
    
    if fields:
        embed["fields"] = fields
    
    try:
        response = requests.post(
            discord_webhook,
            json={"embeds": [embed]},
            timeout=5
        )
    except Exception as e:
        print(f"❌ Discord error: {e}")

# Notification de démarrage
if discord_webhook:
    send_discord(
        "🚀 Bot Démarré",
        f"Mining pour **{username}**",
        0x00FF00,
        [{"name": "📺 Streamers", "value": ", ".join(streamers), "inline": False}]
    )

# Configuration du TwitchChannelPointsMiner
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=auth_token,
    claim_drops_startup=False,
    priority=[Priority.STREAK, Priority.DROPS, Priority.ORDER],
    enable_analytics=True,  # Activer les analytics
    disable_ssl_cert_verification=False,
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
            filter_condition=FilterCondition(
                by=OutcomeKeys.TOTAL_USERS,
                where=Condition.LTE,
                value=800
            )
        )
    )
)

# Handlers pour les événements
def on_websocket_connected(ws):
    print(f"✅ WebSocket connecté")

def on_streamer_online(streamer):
    streamer_name = streamer.username if hasattr(streamer, 'username') else str(streamer)
    game = streamer.game if hasattr(streamer, 'game') else "En direct"
    
    print(f"🟢 {streamer_name} est EN LIGNE ({game})")
    send_discord(
        "🟢 Streamer En Ligne",
        f"**{streamer_name}** est en ligne !",
        0x00FF00,
        [
            {"name": "🎮 Jeu", "value": str(game)[:100], "inline": True},
            {"name": "📺 Streamer", "value": streamer_name, "inline": True}
        ]
    )

def on_streamer_offline(streamer):
    streamer_name = streamer.username if hasattr(streamer, 'username') else str(streamer)
    
    print(f"🔴 {streamer_name} est HORS LIGNE")
    send_discord(
        "🔴 Streamer Hors Ligne",
        f"**{streamer_name}** est hors ligne",
        0xFF0000,
        [{"name": "📺 Streamer", "value": streamer_name, "inline": True}]
    )

def on_minute_watched_event(event_data):
    streamer = event_data.get("streamer", {})
    earned = event_data.get("earned", 0)
    
    if earned > 0:
        streamer_name = streamer.get("username", "Unknown")
        print(f"💰 +{earned} points sur {streamer_name}")
        send_discord(
            "💰 Points Gagnés",
            f"**+{earned}** points sur **{streamer_name}**",
            0xFFD700,
            [
                {"name": "📝 Raison", "value": "Watch time", "inline": True},
                {"name": "💰 Points", "value": f"+{earned}", "inline": True}
            ]
        )

def on_community_points_claimed(event_data):
    streamer = event_data.get("streamer", {})
    points = event_data.get("claimed_points", 0)
    
    streamer_name = streamer.get("username", "Unknown")
    print(f"🎁 +{points} bonus sur {streamer_name}")
    send_discord(
        "🎁 Bonus Réclamé",
        f"**+{points}** points bonus !",
        0x9B59B6,
        [
            {"name": "📺 Streamer", "value": streamer_name, "inline": True},
            {"name": "💰 Points", "value": f"+{points}", "inline": True}
        ]
    )

def on_drop_claimed(drop):
    drop_name = drop.name if hasattr(drop, 'name') else "Drop"
    
    print(f"🎁 Drop réclamé: {drop_name}")
    send_discord(
        "🎁 Drop Réclamé",
        f"Drop réclamé: **{drop_name}**",
        0x9B59B6
    )

def on_bet_placed(event_data):
    streamer = event_data.get("streamer", {})
    bet = event_data.get("bet", {})
    
    streamer_name = streamer.get("username", "Unknown")
    amount = bet.get("amount", 0)
    
    print(f"🎲 Prédiction placée: {amount} points sur {streamer_name}")
    send_discord(
        "🎲 Prédiction Placée",
        f"Pari sur **{streamer_name}**",
        0x3498DB,
        [{"name": "💰 Mise", "value": f"{amount} pts", "inline": True}]
    )

def on_bet_result(event_data):
    won = event_data.get("won", False)
    bet = event_data.get("bet", {})
    streamer = event_data.get("streamer", {})
    
    streamer_name = streamer.get("username", "Unknown")
    amount = bet.get("amount", 0)
    
    if won:
        profit = bet.get("profit", amount)
        print(f"🎉 Prédiction GAGNÉE: +{profit} pts ({streamer_name})")
        send_discord(
            "🎉 Prédiction Gagnée !",
            f"**+{profit}** points gagnés",
            0x00FF00,
            [
                {"name": "📺 Streamer", "value": streamer_name, "inline": True},
                {"name": "🏆 Gain", "value": f"+{profit} pts", "inline": True}
            ]
        )
    else:
        print(f"😢 Prédiction PERDUE: -{amount} pts ({streamer_name})")
        send_discord(
            "😢 Prédiction Perdue",
            f"**-{amount}** points perdus",
            0xFF0000,
            [
                {"name": "📺 Streamer", "value": streamer_name, "inline": True},
                {"name": "💸 Perte", "value": f"-{amount} pts", "inline": True}
            ]
        )

def on_raid_update(raid):
    print(f"🎯 Raid update: {raid}")

# Enregistrer les handlers d'événements
twitch_miner.events_manager.on(Events.on_websocket_connected, on_websocket_connected)
twitch_miner.events_manager.on(Events.on_streamer_online, on_streamer_online)
twitch_miner.events_manager.on(Events.on_streamer_offline, on_streamer_offline)
twitch_miner.events_manager.on(Events.on_minute_watched_event, on_minute_watched_event)
twitch_miner.events_manager.on(Events.on_community_points_claimed, on_community_points_claimed)
twitch_miner.events_manager.on(Events.on_drop_claimed, on_drop_claimed)
twitch_miner.events_manager.on(Events.on_bet_placed, on_bet_placed)
twitch_miner.events_manager.on(Events.on_bet_result, on_bet_result)
twitch_miner.events_manager.on(Events.on_raid_update, on_raid_update)

print("✅ Event handlers configurés")

# Créer les objets Streamer
streamer_objects = [Streamer(name) for name in streamers]

print("🚀 Démarrage du mining...")

try:
    twitch_miner.mine(streamer_objects, followers=False)
except KeyboardInterrupt:
    print("\n⏹️  Arrêt du bot...")
    if discord_webhook:
        send_discord("⏹️ Bot Arrêté", f"Mining arrêté pour **{username}**", 0xFF0000)
except Exception as e:
    error_msg = str(e)[:500]
    print(f"❌ Erreur: {error_msg}")
    if discord_webhook:
        send_discord("⚠️ Erreur", f"```{error_msg}```", 0xFF0000)
    raise