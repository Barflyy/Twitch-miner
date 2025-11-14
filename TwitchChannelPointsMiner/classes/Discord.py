from textwrap import dedent
from datetime import datetime
import re
import requests

from TwitchChannelPointsMiner.classes.Settings import Events


class Discord(object):
    __slots__ = ["webhook_api", "events"]

    def __init__(self, webhook_api: str, events: list):
        self.webhook_api = webhook_api
        self.events = [str(e) for e in events]

    def send(self, message: str, event: Events) -> None:
        if str(event) not in self.events:
            return
        
        # Parser le message pour extraire les informations
        embed = self._create_embed(message, event)
        
        if embed:
            requests.post(
                url=self.webhook_api,
                json={
                    "embeds": [embed],
                    "username": "Twitch Channel Points Miner",
                    "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                },
            )
    
    def _create_embed(self, message: str, event: Events) -> dict:
        """Crée un embed Discord formaté selon le type d'événement"""
        
        # Extraire le streamer et les points
        streamer_match = re.search(r'username=(\w+)', message)
        points_match = re.search(r'channel_points=([\d.]+)([mk]?)', message)
        
        streamer = streamer_match.group(1) if streamer_match else "Unknown"
        
        if points_match:
            points_value = points_match.group(1)
            points_unit = points_match.group(2).upper()
            points_display = f"{points_value}{points_unit}" if points_unit else points_value
        else:
            points_display = "0"
        
        embed = {
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": f"Solde: {points_display} points"}
        }
        
        # Selon le type d'événement
        if event == Events.STREAMER_ONLINE:
            embed.update({
                "title": "🟢 Stream En Ligne",
                "description": f"**{streamer}** est maintenant en ligne !",
                "color": 0x00FF00
            })
        
        elif event == Events.STREAMER_OFFLINE:
            embed.update({
                "title": "🔴 Stream Hors Ligne",
                "description": f"**{streamer}** s'est déconnecté",
                "color": 0xFF0000
            })
        
        elif "GAIN_FOR" in str(event):
            gain_match = re.search(r'\+(\d+)', message)
            reason_match = re.search(r'Reason: (\w+)', message)
            
            points_gained = gain_match.group(1) if gain_match else "0"
            reason = reason_match.group(1) if reason_match else "WATCH"
            
            reason_emoji = {
                "WATCH": "👀",
                "WATCH_STREAK": "🔥",
                "CLAIM": "🎁",
                "RAID": "🎯"
            }
            
            embed.update({
                "title": f"{reason_emoji.get(reason, '💰')} +{points_gained} Points",
                "description": f"**{streamer}**",
                "color": 0xFFD700,
                "fields": [{"name": "Type", "value": reason, "inline": True}]
            })
        
        elif event == Events.BONUS_CLAIM:
            gain_match = re.search(r'\+(\d+)', message)
            points_gained = gain_match.group(1) if gain_match else "50"
            
            embed.update({
                "title": "🎁 Bonus Réclamé",
                "description": f"**+{points_gained}** points sur **{streamer}**",
                "color": 0x9B59B6
            })
        
        elif event == Events.BET_WIN:
            embed.update({
                "title": "🎉 Pari Gagné !",
                "description": f"Victoire sur **{streamer}**",
                "color": 0x00FF00
            })
        
        elif event == Events.BET_LOSE:
            embed.update({
                "title": "😢 Pari Perdu",
                "description": f"Défaite sur **{streamer}**",
                "color": 0xFF0000
            })
        
        elif event == Events.BET_START:
            embed.update({
                "title": "🎲 Pari Placé",
                "description": f"Prédiction sur **{streamer}**",
                "color": 0x3498DB
            })
        
        elif event == Events.DROP_CLAIM:
            embed.update({
                "title": "🎁 Drop Réclamé",
                "description": f"Drop obtenu sur **{streamer}**",
                "color": 0x9B59B6
            })
        
        else:
            # Fallback: message simple
            embed.update({
                "description": message,
                "color": 0x5865F2
            })
        
        return embed
