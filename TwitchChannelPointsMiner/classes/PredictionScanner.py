"""
PredictionScanner - Scanne tous les streams actifs pour détecter les prédictions
"""

import logging
import asyncio
import time
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from TwitchChannelPointsMiner.classes.entities.StreamerPredictionProfiler import StreamerPredictionProfiler
from TwitchChannelPointsMiner.classes.entities.AdaptiveBetStrategy import AdaptiveBetStrategy

logger = logging.getLogger(__name__)

# Instance globale pour accès depuis l'API
_scanner_instance = None

def get_scanner_instance():
    """Récupère l'instance globale du scanner."""
    return _scanner_instance

def set_scanner_instance(scanner):
    """Définit l'instance globale du scanner."""
    global _scanner_instance
    _scanner_instance = scanner


class PredictionScanner:
    """
    Scanne tous les streams actifs pour détecter les prédictions.
    Peut être utilisé en complément du système WebSocket existant.
    """

    def __init__(self, twitch_instance, streamers_list, events_predictions_dict):
        """
        Args:
            twitch_instance: Instance de la classe Twitch
            streamers_list: Liste des streamers suivis
            events_predictions_dict: Dictionnaire des prédictions actives (partagé avec WebSocketsPool)
        """
        self.twitch = twitch_instance
        self.streamers = streamers_list
        self.events_predictions = events_predictions_dict
        self.profiler = StreamerPredictionProfiler()
        self.adaptive_strategy = AdaptiveBetStrategy(self.profiler)
        self.running = False
        self.scan_interval = 30  # Secondes entre chaque scan

    def get_active_streams(self) -> List[Dict[str, Any]]:
        """Récupère la liste des streams actifs."""
        active_streams = []
        
        for streamer in self.streamers:
            if hasattr(streamer, 'is_online') and streamer.is_online:
                active_streams.append({
                    'channel_id': str(streamer.channel_id),
                    'channel_name': streamer.username,
                    'streamer': streamer
                })
        
        return active_streams

    def check_prediction(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Vérifie s'il y a une prédiction active sur un channel.
        Utilise l'API GraphQL de Twitch.
        """
        try:
            from TwitchChannelPointsMiner.classes.Twitch import GQLOperations
            import copy
            
            # Requête GraphQL pour obtenir les prédictions actives
            json_data = {
                "operationName": "ChannelPredictions",
                "variables": {
                    "channelID": channel_id
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "e2d67415aead910f7f9ceb45a77b750a1e1d9622c936d832328a0689e054db62"
                    }
                }
            }
            
            response = self.twitch.post_gql_request(json_data)
            
            if "data" in response and "channel" in response["data"]:
                channel_data = response["data"]["channel"]
                if "activePrediction" in channel_data and channel_data["activePrediction"]:
                    prediction = channel_data["activePrediction"]
                    
                    return {
                        'id': prediction.get('id'),
                        'title': prediction.get('title', ''),
                        'status': prediction.get('status', 'ACTIVE'),
                        'outcomes': prediction.get('outcomes', []),
                        'created_at': prediction.get('createdAt'),
                        'prediction_window_seconds': prediction.get('predictionWindowSeconds', 120),
                        'channel_id': channel_id
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur lors de la vérification de prédiction pour {channel_id}: {e}")
            return None

    def scan_all_active_streams(self) -> List[Dict[str, Any]]:
        """
        Parcourt tous les streams en cours et détecte les prédictions.
        Returns:
            Liste des prédictions trouvées avec leurs métadonnées
        """
        active_streams = self.get_active_streams()
        predictions_found = []
        
        logger.debug(f"Scanning {len(active_streams)} active streams for predictions...")
        
        for stream in active_streams:
            try:
                # Vérifie s'il y a une prédiction active
                prediction = self.check_prediction(stream['channel_id'])
                
                if prediction:
                    prediction_id = prediction['id']
                    
                    # Vérifie si on ne l'a pas déjà détectée
                    if prediction_id not in self.events_predictions:
                        predictions_found.append({
                            'streamer': stream['channel_name'],
                            'streamer_id': stream['channel_id'],
                            'streamer_obj': stream['streamer'],
                            'prediction': prediction
                        })
                        logger.info(
                            f"🎯 Nouvelle prédiction détectée: {stream['channel_name']} - {prediction['title']}",
                            extra={"emoji": ":dart:", "event": None}
                        )
            
            except Exception as e:
                logger.debug(f"Erreur lors du scan pour {stream['channel_name']}: {e}")
        
        return predictions_found

    def analyze_and_decide(self, pred_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyse une prédiction et prend une décision de betting.
        """
        try:
            prediction = pred_data['prediction']
            streamer = pred_data['streamer_obj']
            
            # Convertit les outcomes au format attendu
            outcomes = []
            for outcome in prediction.get('outcomes', []):
                outcomes.append({
                    'id': outcome.get('id'),
                    'title': outcome.get('title', ''),
                    'color': outcome.get('color', 'BLUE'),
                    'total_users': outcome.get('totalUsers', 0),
                    'total_points': outcome.get('totalPoints', 0),
                    'top_points': outcome.get('topPoints', 0),
                    'percentage_users': outcome.get('percentageUsers', 0),
                    'odds': outcome.get('odds', 0),
                    'odds_percentage': outcome.get('oddsPercentage', 0)
                })
            
            # Utilise la stratégie adaptive
            balance = streamer.channel_points if hasattr(streamer, 'channel_points') else 0
            
            decision = self.adaptive_strategy.make_decision(
                outcomes=outcomes,
                balance=balance,
                streamer_id=pred_data['streamer_id'],
                streamer_name=pred_data['streamer'],
                prediction_title=prediction.get('title', ''),
                base_percentage=streamer.settings.bet.percentage if hasattr(streamer, 'settings') else 5.0,
                max_bet=streamer.settings.bet.max_points if hasattr(streamer, 'settings') else 50000,
                min_bet=10
            )
            
            return decision
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de la prédiction: {e}", exc_info=True)
            return None

    def start_continuous_scan(self, interval: int = 30):
        """
        Lance le scan continu en arrière-plan.
        Args:
            interval: Intervalle en secondes entre chaque scan
        """
        self.scan_interval = interval
        self.running = True
        
        def scan_loop():
            while self.running:
                try:
                    predictions = self.scan_all_active_streams()
                    
                    for pred_data in predictions:
                        # Analyse et décide
                        decision = self.analyze_and_decide(pred_data)
                        
                        if decision:
                            logger.info(
                                f"""
🎯 NOUVELLE PRÉDICTION DÉTECTÉE
├─ Streamer: {pred_data['streamer']}
├─ Titre: {pred_data['prediction']['title']}
├─ Décision: Option {decision.get('choice', 'N/A') + 1}
├─ Confiance: {decision.get('confidence', 0):.0%}
├─ Montant: {decision.get('amount', 0):,} points
└─ Raison: {decision.get('reason', 'N/A')}
                                """.strip(),
                                extra={"emoji": ":dart:", "event": None}
                            )
                            
                            # Note: Le bet sera placé par le système WebSocket normal
                            # Ce scanner sert principalement à la détection et au logging
                        else:
                            logger.debug(f"Pas de décision pour {pred_data['streamer']}: {pred_data['prediction']['title']}")
                
                except Exception as e:
                    logger.error(f"Erreur dans la boucle de scan: {e}", exc_info=True)
                
                # Attendre avant le prochain scan
                time.sleep(self.scan_interval)
        
        # Lance dans un thread séparé
        import threading
        scan_thread = threading.Thread(target=scan_loop, daemon=True, name="PredictionScanner")
        scan_thread.start()
        
        logger.info(f"✅ PredictionScanner démarré (intervalle: {interval}s)")

    def stop(self):
        """Arrête le scanner."""
        self.running = False
        logger.info("🛑 PredictionScanner arrêté")

    def get_statistics(self) -> Dict[str, Any]:
        """Retourne des statistiques sur le scanner."""
        active_streams = self.get_active_streams()
        active_predictions = len(self.events_predictions)
        
        return {
            'active_streams': len(active_streams),
            'active_predictions': active_predictions,
            'scan_interval': self.scan_interval,
            'running': self.running
        }

