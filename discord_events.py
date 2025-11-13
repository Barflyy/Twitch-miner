# discord_events.py
import os
import requests
from datetime import datetime

class DiscordWebhook:
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
        
        if not self.enabled:
            print("⚠️  Discord webhook désactivé")
        else:
            print(f"✅ Discord webhook configuré")
    
    def send_embed(self, title, description, color, fields=None, thumbnail=None):
        if not self.enabled:
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
        
        if thumbnail:
            embed["thumbnail"] = {"url": thumbnail}
        
        try:
            response = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            print(f"❌ Erreur Discord webhook: {e}")
    
    def on_event(self, event_name, event_data):
        """Handler principal pour tous les events"""
        
        if event_name == "streamer_online":
            self._streamer_online(event_data)
        
        elif event_name == "streamer_offline":
            self._streamer_offline(event_data)
        
        elif event_name == "gain_points":
            self._gain_points(event_data)
        
        elif event_name == "claim_bonus":
            self._claim_bonus(event_data)
        
        elif event_name == "bet_placed":
            self._bet_placed(event_data)
        
        elif event_name == "bet_won":
            self._bet_won(event_data)
        
        elif event_name == "bet_lost":
            self._bet_lost(event_data)
        
        elif event_name == "claim_drop":
            self._claim_drop(event_data)
    
    def _streamer_online(self, data):
        streamer = data.get("streamer", {})
        username = streamer.get("username", "Unknown")
        game = data.get("game", {}).get("name", "Unknown")
        title = data.get("title", "")
        
        self.send_embed(
            title="🟢 Streamer En Ligne",
            description=f"**{username}** vient de passer en ligne !",
            color=0x00FF00,
            fields=[
                {"name": "🎮 Jeu", "value": game, "inline": True},
                {"name": "📺 Streamer", "value": username, "inline": True},
                {"name": "📝 Titre", "value": title[:100] if title else "Pas de titre", "inline": False}
            ]
        )
    
    def _streamer_offline(self, data):
        streamer = data.get("streamer", {})
        username = streamer.get("username", "Unknown")
        
        self.send_embed(
            title="🔴 Streamer Hors Ligne",
            description=f"**{username}** a terminé son stream",
            color=0xFF0000,
            fields=[
                {"name": "📺 Streamer", "value": username, "inline": True}
            ]
        )
    
    def _gain_points(self, data):
        streamer = data.get("streamer", {})
        username = streamer.get("username", "Unknown")
        points = data.get("points", 0)
        reason = data.get("reason", "Watch")
        balance = data.get("balance", 0)
        
        self.send_embed(
            title="💰 Points Gagnés",
            description=f"**+{points}** points sur **{username}**",
            color=0xFFD700,
            fields=[
                {"name": "📝 Raison", "value": reason, "inline": True},
                {"name": "💎 Solde", "value": f"{balance:,} points", "inline": True}
            ]
        )
    
    def _claim_bonus(self, data):
        streamer = data.get("streamer", {})
        username = streamer.get("username", "Unknown")
        points = data.get("points", 0)
        
        self.send_embed(
            title="🎁 Bonus Réclamé",
            description=f"**+{points}** points bonus !",
            color=0x9B59B6,
            fields=[
                {"name": "📺 Streamer", "value": username, "inline": True},
                {"name": "💰 Points", "value": f"+{points}", "inline": True}
            ]
        )
    
    def _bet_placed(self, data):
        streamer = data.get("streamer", {})
        username = streamer.get("username", "Unknown")
        bet = data.get("bet", {})
        title = bet.get("title", "Unknown")
        choice = bet.get("choice", "Unknown")
        amount = bet.get("amount", 0)
        
        self.send_embed(
            title="🎲 Prédiction Placée",
            description=f"Pari sur **{username}**",
            color=0x3498DB,
            fields=[
                {"name": "❓ Question", "value": title[:100], "inline": False},
                {"name": "✅ Choix", "value": choice, "inline": True},
                {"name": "💰 Mise", "value": f"{amount:,} points", "inline": True}
            ]
        )
    
    def _bet_won(self, data):
        streamer = data.get("streamer", {})
        username = streamer.get("username", "Unknown")
        bet = data.get("bet", {})
        amount = bet.get("amount", 0)
        won = bet.get("won", 0)
        
        self.send_embed(
            title="🎉 Prédiction Gagnée !",
            description=f"Bravo ! **+{won}** points gagnés",
            color=0x00FF00,
            fields=[
                {"name": "📺 Streamer", "value": username, "inline": True},
                {"name": "💰 Mise", "value": f"{amount:,} points", "inline": True},
                {"name": "🏆 Gain", "value": f"+{won:,} points", "inline": True}
            ]
        )
    
    def _bet_lost(self, data):
        streamer = data.get("streamer", {})
        username = streamer.get("username", "Unknown")
        bet = data.get("bet", {})
        amount = bet.get("amount", 0)
        
        self.send_embed(
            title="😢 Prédiction Perdue",
            description=f"Dommage... **-{amount}** points",
            color=0xFF0000,
            fields=[
                {"name": "📺 Streamer", "value": username, "inline": True},
                {"name": "💸 Perte", "value": f"-{amount:,} points", "inline": True}
            ]
        )
    
    def _claim_drop(self, data):
        streamer = data.get("streamer", {})
        username = streamer.get("username", "Unknown")
        drop = data.get("drop", {})
        name = drop.get("name", "Drop")
        
        self.send_embed(
            title="🎁 Drop Réclamé",
            description=f"Drop réclamé sur **{username}**",
            color=0x9B59B6,
            fields=[
                {"name": "🎮 Drop", "value": name, "inline": True},
                {"name": "📺 Streamer", "value": username, "inline": True}
            ]
        )