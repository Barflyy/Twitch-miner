# discord_notifier.py
import os
import requests
from datetime import datetime
from typing import Optional

class DiscordNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
        
        if not self.enabled:
            print("⚠️  Discord webhook non configuré, notifications désactivées")
    
    def send_embed(self, title: str, description: str, color: int, fields: list = None):
        """Envoie un message embed sur Discord"""
        if not self.enabled:
            return
        
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Twitch Channel Points Miner"
            }
        }
        
        if fields:
            embed["fields"] = fields
        
        payload = {
            "embeds": [embed]
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
        except Exception as e:
            print(f"❌ Erreur webhook Discord: {e}")
    
    def streamer_online(self, streamer_name: str, game: str = "Unknown"):
        """Notification quand un streamer passe en ligne"""
        self.send_embed(
            title="🟢 Streamer En Ligne",
            description=f"**{streamer_name}** vient de démarrer son stream !",
            color=0x00FF00,  # Vert
            fields=[
                {"name": "🎮 Jeu", "value": game, "inline": True},
                {"name": "📺 Streamer", "value": streamer_name, "inline": True}
            ]
        )
    
    def streamer_offline(self, streamer_name: str, watch_time: int = 0):
        """Notification quand un streamer passe hors ligne"""
        hours = watch_time // 3600
        minutes = (watch_time % 3600) // 60
        
        self.send_embed(
            title="🔴 Streamer Hors Ligne",
            description=f"**{streamer_name}** a terminé son stream",
            color=0xFF0000,  # Rouge
            fields=[
                {"name": "⏱️ Temps regardé", "value": f"{hours}h {minutes}m", "inline": True},
                {"name": "📺 Streamer", "value": streamer_name, "inline": True}
            ]
        )
    
    def points_earned(self, streamer_name: str, points: int, reason: str, total_points: int):
        """Notification pour les points gagnés"""
        self.send_embed(
            title="💰 Points Gagnés !",
            description=f"**+{points}** points sur **{streamer_name}**",
            color=0xFFD700,  # Or
            fields=[
                {"name": "📝 Raison", "value": reason, "inline": True},
                {"name": "💎 Total", "value": f"{total_points:,} points", "inline": True}
            ]
        )
    
    def claim_bonus(self, streamer_name: str, points: int):
        """Notification pour les bonus réclamés"""
        self.send_embed(
            title="🎁 Bonus Réclamé",
            description=f"**+{points}** points bonus !",
            color=0x9B59B6,  # Violet
            fields=[
                {"name": "📺 Streamer", "value": streamer_name, "inline": True},
                {"name": "💰 Points", "value": f"+{points}", "inline": True}
            ]
        )
    
    def prediction_made(self, streamer_name: str, title: str, choice: str, points: int):
        """Notification pour les prédictions"""
        self.send_embed(
            title="🎲 Prédiction Placée",
            description=f"Prédiction sur **{streamer_name}**",
            color=0x3498DB,  # Bleu
            fields=[
                {"name": "❓ Question", "value": title[:100], "inline": False},
                {"name": "✅ Choix", "value": choice, "inline": True},
                {"name": "💰 Mise", "value": f"{points} points", "inline": True}
            ]
        )
    
    def prediction_result(self, streamer_name: str, result: str, points_won: int):
        """Notification pour les résultats de prédiction"""
        if points_won > 0:
            color = 0x00FF00  # Vert (gagné)
            emoji = "🎉"
            description = f"**+{points_won}** points gagnés !"
        else:
            color = 0xFF0000  # Rouge (perdu)
            emoji = "😢"
            description = "Prédiction perdue"
        
        self.send_embed(
            title=f"{emoji} Résultat Prédiction",
            description=description,
            color=color,
            fields=[
                {"name": "📺 Streamer", "value": streamer_name, "inline": True},
                {"name": "📊 Résultat", "value": result, "inline": True}
            ]
        )
    
    def daily_summary(self, username: str, stats: dict):
        """Résumé quotidien"""
        fields = [
            {"name": "💰 Points gagnés", "value": f"{stats.get('points_earned', 0):,}", "inline": True},
            {"name": "⏱️ Temps total", "value": f"{stats.get('watch_time', 0) // 3600}h", "inline": True},
            {"name": "🎲 Prédictions", "value": f"{stats.get('predictions', 0)}", "inline": True},
            {"name": "✅ Victoires", "value": f"{stats.get('predictions_won', 0)}", "inline": True},
            {"name": "📺 Streamers", "value": f"{stats.get('streamers_watched', 0)}", "inline": True}
        ]
        
        self.send_embed(
            title=f"📊 Résumé Quotidien - {username}",
            description="Voici ton récapitulatif de la journée !",
            color=0x2ECC71,  # Vert
            fields=fields
        )
    
    def bot_started(self, username: str, streamers: list):
        """Notification au démarrage du bot"""
        self.send_embed(
            title="🚀 Bot Démarré",
            description=f"Mining démarré pour **{username}**",
            color=0x3498DB,  # Bleu
            fields=[
                {"name": "📺 Streamers suivis", "value": ", ".join(streamers[:10]), "inline": False},
                {"name": "📈 Nombre total", "value": str(len(streamers)), "inline": True}
            ]
        )
    
    def error_occurred(self, error_message: str):
        """Notification d'erreur"""
        self.send_embed(
            title="⚠️ Erreur Détectée",
            description=f"```{error_message[:500]}```",
            color=0xFF0000  # Rouge
        )
