from textwrap import dedent
from datetime import datetime
import re
import requests
import json
from pathlib import Path

from TwitchChannelPointsMiner.classes.Settings import Events


class Discord(object):
    __slots__ = ["webhook_api", "events", "use_bot"]

    def __init__(self, webhook_api: str, events: list, use_bot: bool = False):
        self.webhook_api = webhook_api
        self.events = [str(e) for e in events]
        self.use_bot = use_bot  # True = bot Discord, False = webhook simple

    def send(self, message: str, event: Events) -> None:
        if str(event) not in self.events:
            return
        
        # Si mode bot Discord, mettre à jour le fichier JSON
        if self.use_bot:
            self._update_bot_data(message, event)
        
        # Toujours envoyer le webhook aussi (pour logs)
        if self.webhook_api:
            embed = self._create_embed(message, event)
            if embed:
                try:
            requests.post(
                url=self.webhook_api,
                        json={
                            "embeds": [embed],
                    "username": "Twitch Channel Points Miner",
                    "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                },
                        timeout=5
                    )
                except Exception:
                    pass  # Ignore webhook errors
    
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
    
    def _update_bot_data(self, message: str, event: Events) -> None:
        """Met à jour le fichier JSON pour le bot Discord"""
        try:
            data_file = Path("bot_data.json")
            
            # Charger les données existantes
            if data_file.exists():
                with open(data_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {'streamers': {}}
            
            # Extraire les infos du message
            streamer_match = re.search(r'username=(\w+)', message)
            points_match = re.search(r'channel_points=([\d.]+)([mk]?)', message)
            
            if not streamer_match:
                return
            
            streamer = streamer_match.group(1).lower()
            
            # Initialiser le streamer si nécessaire
            if streamer not in data['streamers']:
                # Nouveau streamer - initialiser avec le solde actuel comme baseline
                current_balance = 0
                if points_match:
                    points_value = float(points_match.group(1))
                    points_unit = points_match.group(2).lower()
                    if points_unit == 'k':
                        points_value *= 1000
                    elif points_unit == 'm':
                        points_value *= 1000000
                    current_balance = int(points_value)
                
                data['streamers'][streamer] = {
                    'online': False,
                    'balance': current_balance,
                    'starting_balance': current_balance,  # Solde au démarrage
                    'total_earned': 0,  # Points gagnés depuis le début
                    'session_points': 0,
                    'watch_points': 0,
                    'bonus_points': 0,
                    'bets_placed': 0,
                    'bets_won': 0,
                    'bets_lost': 0
                }
            
            streamer_data = data['streamers'][streamer]
            
            # Mettre à jour le solde
            if points_match:
                points_value = float(points_match.group(1))
                points_unit = points_match.group(2).lower()
                
                if points_unit == 'k':
                    points_value *= 1000
                elif points_unit == 'm':
                    points_value *= 1000000
                
                streamer_data['balance'] = int(points_value)
            
            # Traiter selon l'événement
            if event == Events.STREAMER_ONLINE:
                streamer_data['online'] = True
                streamer_data['online_since'] = datetime.utcnow().isoformat()
                # Reset session
                streamer_data['session_points'] = 0
                streamer_data['watch_points'] = 0
                streamer_data['bonus_points'] = 0
            
            elif event == Events.STREAMER_OFFLINE:
                streamer_data['online'] = False
                if 'online_since' in streamer_data:
                    del streamer_data['online_since']
            
            elif "GAIN_FOR" in str(event):
                gain_match = re.search(r'\+(\d+)', message)
                if gain_match:
                    points_gained = int(gain_match.group(1))
                    streamer_data['session_points'] = streamer_data.get('session_points', 0) + points_gained
                    streamer_data['total_earned'] = streamer_data.get('total_earned', 0) + points_gained  # Total depuis le début
                    
                    reason_match = re.search(r'Reason: (\w+)', message)
                    if reason_match:
                        reason = reason_match.group(1)
                        if reason in ['WATCH', 'WATCH_STREAK']:
                            streamer_data['watch_points'] = streamer_data.get('watch_points', 0) + points_gained
            
            elif event == Events.BONUS_CLAIM:
                gain_match = re.search(r'\+(\d+)', message)
                if gain_match:
                    points_gained = int(gain_match.group(1))
                    streamer_data['session_points'] = streamer_data.get('session_points', 0) + points_gained
                    streamer_data['bonus_points'] = streamer_data.get('bonus_points', 0) + points_gained
                    streamer_data['total_earned'] = streamer_data.get('total_earned', 0) + points_gained  # Total depuis le début
            
            elif event == Events.BET_START:
                streamer_data['bets_placed'] = streamer_data.get('bets_placed', 0) + 1
            
            elif event == Events.BET_WIN:
                streamer_data['bets_won'] = streamer_data.get('bets_won', 0) + 1
            
            elif event == Events.BET_LOSE:
                streamer_data['bets_lost'] = streamer_data.get('bets_lost', 0) + 1
            
            # Sauvegarder
            data['last_update'] = datetime.utcnow().isoformat()
            
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            # Ignore silencieusement les erreurs pour ne pas casser le miner
            pass
