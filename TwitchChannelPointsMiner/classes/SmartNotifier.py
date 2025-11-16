"""
SmartNotifier - Système de notifications intelligentes pour Discord
"""

import logging
import time
import requests
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SmartNotifier:
    """Envoie des notifications Discord seulement pour les choses importantes."""

    def __init__(self, discord_webhook: Optional[str] = None):
        """
        Args:
            discord_webhook: URL du webhook Discord (optionnel)
        """
        self.webhook = discord_webhook
        self.last_notifications = {}
        self.cooldown = 300  # 5 minutes entre notifs similaires
        self.enabled = bool(discord_webhook)
        
        if not self.enabled:
            logger.debug("SmartNotifier désactivé (pas de webhook Discord)")
        else:
            logger.info("✅ SmartNotifier activé")

    def _send_webhook(self, embed: Dict[str, Any]) -> bool:
        """Envoie un webhook Discord."""
        if not self.enabled or not self.webhook:
            return False
        
        try:
            response = requests.post(
                self.webhook,
                json={"embeds": [embed]},
                timeout=5
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.debug(f"Erreur envoi webhook Discord: {e}")
            return False

    def _check_cooldown(self, key: str) -> bool:
        """Vérifie si on peut envoyer une notification (cooldown)."""
        if key not in self.last_notifications:
            return True
        
        elapsed = time.time() - self.last_notifications[key]
        return elapsed >= self.cooldown

    def notify_high_value_prediction(
        self, 
        prediction_data: Dict[str, Any], 
        decision: Dict[str, Any]
    ) -> bool:
        """
        Notifie pour une prédiction à forte valeur.
        
        Critères:
        - Confiance >= 75%
        - Montant >= 5000 points
        """
        if not self.enabled:
            return False
        
        confidence = decision.get('confidence', 0)
        amount = decision.get('amount', 0)
        
        # Critères pour "high value"
        if confidence < 0.75:
            return False
        
        if amount < 5000:
            return False
        
        # Cooldown pour éviter le spam
        key = f"prediction_{prediction_data.get('streamer_id', 'unknown')}"
        if not self._check_cooldown(key):
            return False
        
        self.last_notifications[key] = time.time()
        
        # Créer l'embed
        embed = {
            "title": "🎯 High Value Bet Opportunity",
            "color": 0x00ff00,  # Vert
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Streamer",
                    "value": prediction_data.get('streamer_name', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "Confidence",
                    "value": f"{confidence:.0%}",
                    "inline": True
                },
                {
                    "name": "Amount",
                    "value": f"{amount:,} points",
                    "inline": True
                },
                {
                    "name": "Prediction",
                    "value": prediction_data.get('title', 'N/A'),
                    "inline": False
                },
                {
                    "name": "Strategy",
                    "value": decision.get('reason', 'N/A'),
                    "inline": False
                }
            ],
            "footer": {
                "text": "Twitch Mining Bot"
            }
        }
        
        return self._send_webhook(embed)

    def notify_big_win(self, amount: int, streamer: str, prediction_title: str = "") -> bool:
        """
        Notifie pour un gros gain.
        
        Critères:
        - Montant >= 10000 points
        """
        if not self.enabled:
            return False
        
        if amount < 10000:
            return False
        
        # Pas de cooldown pour les gros gains
        embed = {
            "title": "💰 BIG WIN!",
            "color": 0xffd700,  # Or
            "description": f"Tu as gagné **{amount:,} points** sur **{streamer}**!",
            "timestamp": datetime.utcnow().isoformat(),
            "fields": []
        }
        
        if prediction_title:
            embed["fields"].append({
                "name": "Prediction",
                "value": prediction_title,
                "inline": False
            })
        
        embed["footer"] = {"text": "Twitch Mining Bot"}
        
        return self._send_webhook(embed)

    def notify_big_loss(self, amount: int, streamer: str, prediction_title: str = "") -> bool:
        """
        Notifie pour une grosse perte (optionnel, pour tracking).
        
        Critères:
        - Montant >= 10000 points
        """
        if not self.enabled:
            return False
        
        if amount < 10000:
            return False
        
        # Cooldown pour éviter le spam de pertes
        key = f"big_loss_{streamer}"
        if not self._check_cooldown(key):
            return False
        
        self.last_notifications[key] = time.time()
        
        embed = {
            "title": "⚠️ Big Loss",
            "color": 0xff0000,  # Rouge
            "description": f"Perte de **{amount:,} points** sur **{streamer}**",
            "timestamp": datetime.utcnow().isoformat(),
            "fields": []
        }
        
        if prediction_title:
            embed["fields"].append({
                "name": "Prediction",
                "value": prediction_title,
                "inline": False
            })
        
        embed["footer"] = {"text": "Twitch Mining Bot"}
        
        return self._send_webhook(embed)

    def send_daily_summary(self, stats: Dict[str, Any]) -> bool:
        """
        Envoie un résumé quotidien.
        
        Args:
            stats: Dict avec les stats du jour
                - watch_time: Temps de watch en secondes
                - points_earned: Points gagnés
                - predictions_won: Nombre de prédictions gagnées
                - predictions_total: Nombre total de prédictions
                - win_rate: Taux de victoire (%)
                - roi: ROI (%)
                - best_streamer: Meilleur streamer
        """
        if not self.enabled:
            return False
        
        watch_hours = stats.get('watch_time', 0) // 3600
        watch_minutes = (stats.get('watch_time', 0) % 3600) // 60
        
        embed = {
            "title": f"📊 Daily Summary - {datetime.now().strftime('%Y-%m-%d')}",
            "color": 0x9147ff,  # Violet Twitch
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "⏱️ Watch Time",
                    "value": f"{watch_hours}h {watch_minutes}m",
                    "inline": True
                },
                {
                    "name": "💰 Points Earned",
                    "value": f"+{stats.get('points_earned', 0):,}",
                    "inline": True
                },
                {
                    "name": "🎲 Predictions",
                    "value": f"{stats.get('predictions_won', 0)}/{stats.get('predictions_total', 0)}",
                    "inline": True
                },
                {
                    "name": "📈 Win Rate",
                    "value": f"{stats.get('win_rate', 0):.1f}%",
                    "inline": True
                },
                {
                    "name": "💵 ROI",
                    "value": f"{stats.get('roi', 0):+.1f}%",
                    "inline": True
                },
                {
                    "name": "🏆 Best Streamer",
                    "value": stats.get('best_streamer', 'N/A'),
                    "inline": True
                }
            ],
            "footer": {
                "text": "Twitch Mining Bot"
            }
        }
        
        return self._send_webhook(embed)

    def notify_streamer_online(self, streamer: str, viewers: int = 0) -> bool:
        """
        Notifie quand un streamer important passe en ligne.
        (Optionnel, peut être activé pour certains streamers)
        """
        if not self.enabled:
            return False
        
        # Cooldown pour éviter le spam
        key = f"online_{streamer}"
        if not self._check_cooldown(key):
            return False
        
        self.last_notifications[key] = time.time()
        
        embed = {
            "title": "🟢 Streamer Online",
            "color": 0x00ff00,
            "description": f"**{streamer}** est maintenant en ligne",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if viewers > 0:
            embed["fields"] = [{
                "name": "Viewers",
                "value": f"{viewers:,}",
                "inline": True
            }]
        
        embed["footer"] = {"text": "Twitch Mining Bot"}
        
        return self._send_webhook(embed)

    def notify_prediction_created(
        self, 
        streamer: str, 
        title: str, 
        options: list,
        high_value: bool = False
    ) -> bool:
        """
        Notifie quand une nouvelle prédiction est créée.
        (Seulement si high_value=True ou si cooldown OK)
        """
        if not self.enabled:
            return False
        
        if not high_value:
            # Cooldown pour les prédictions normales
            key = f"pred_created_{streamer}"
            if not self._check_cooldown(key):
                return False
            self.last_notifications[key] = time.time()
        
        embed = {
            "title": "🎲 New Prediction" + (" (High Value)" if high_value else ""),
            "color": 0x9147ff if high_value else 0x808080,
            "description": f"**{streamer}** a créé une nouvelle prédiction",
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Title",
                    "value": title,
                    "inline": False
                },
                {
                    "name": "Options",
                    "value": "\n".join([f"• {opt}" for opt in options[:2]]),
                    "inline": False
                }
            ],
            "footer": {
                "text": "Twitch Mining Bot"
            }
        }
        
        return self._send_webhook(embed)

    def notify_error(self, error_message: str, context: str = "") -> bool:
        """
        Notifie pour une erreur importante.
        """
        if not self.enabled:
            return False
        
        embed = {
            "title": "❌ Error",
            "color": 0xff0000,
            "description": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if context:
            embed["fields"] = [{
                "name": "Context",
                "value": context,
                "inline": False
            }]
        
        embed["footer"] = {"text": "Twitch Mining Bot"}
        
        return self._send_webhook(embed)

    def set_cooldown(self, seconds: int):
        """Modifie le cooldown entre notifications."""
        self.cooldown = seconds
        logger.debug(f"Cooldown modifié à {seconds}s")

    def clear_cooldown(self, key: Optional[str] = None):
        """Efface le cooldown pour une clé ou toutes les clés."""
        if key:
            self.last_notifications.pop(key, None)
        else:
            self.last_notifications.clear()
        logger.debug(f"Cooldown effacé pour {key or 'toutes les clés'}")

