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
        
        # D'abord essayer avec la liste en mémoire
        for streamer in self.streamers:
            if hasattr(streamer, 'is_online') and streamer.is_online:
                active_streams.append({
                    'channel_id': str(streamer.channel_id),
                    'channel_name': streamer.username,
                    'streamer': streamer
                })
        
        # Si aucun stream trouvé, utiliser bot_data.json en fallback
        if not active_streams:
            try:
                data_dir = os.getenv("DATA_DIR", ".")
                bot_data_path = os.path.join(data_dir, "bot_data.json")
                
                if os.path.exists(bot_data_path):
                    with open(bot_data_path, 'r') as f:
                        data = json.load(f)
                    
                    streamers_data = data.get('streamers', {})
                    for name, sdata in streamers_data.items():
                        if sdata.get('online', False):
                            active_streams.append({
                                'channel_id': str(sdata.get('channel_id', '')),
                                'channel_name': name,
                                'streamer': None
                            })
                    
                    logger.debug(f"Fallback bot_data.json: {len(active_streams)} streams en ligne")
            except Exception as e:
                logger.debug(f"Erreur lecture bot_data.json: {e}")
        
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

    def sync_predictions_to_bot_data(self) -> Dict[str, Any]:
        """
        Synchronise les prédictions actives avec bot_data.json.
        Utile pour récupérer après un bug ou une désynchronisation.
        
        Returns:
            Dict avec le résultat de la synchronisation
        """
        try:
            from TwitchChannelPointsMiner.classes.WebSocketsPool import update_active_prediction, atomic_write_json, _bot_data_lock
            
            data_dir = os.getenv("DATA_DIR", ".")
            bot_data_path = os.path.join(data_dir, "bot_data.json")
            
            # Charger les données actuelles
            with _bot_data_lock:
                if os.path.exists(bot_data_path):
                    with open(bot_data_path, 'r') as f:
                        data = json.load(f)
                else:
                    data = {'streamers': {}, 'bet_history': [], 'active_predictions': []}
            
            # IDs des prédictions dans bot_data
            bot_data_pred_ids = {p.get('event_id') for p in data.get('active_predictions', [])}
            
            # IDs des prédictions dans events_predictions (mémoire)
            memory_pred_ids = set(self.events_predictions.keys())
            
            synced = []
            removed = []
            added = []
            
            # 1. Scanner tous les streams en ligne pour trouver les prédictions réelles
            active_streams = self.get_active_streams()
            real_predictions = {}
            
            logger.info(f"🔍 Scan de récupération: {len(active_streams)} streams en ligne")
            
            for stream in active_streams:
                try:
                    prediction = self.check_prediction(stream['channel_id'])
                    if prediction and prediction.get('status') in ['ACTIVE', 'LOCKED']:
                        real_predictions[prediction['id']] = {
                            'prediction': prediction,
                            'streamer': stream['channel_name'],
                            'streamer_obj': stream['streamer']
                        }
                except Exception as e:
                    logger.debug(f"Erreur scan {stream['channel_name']}: {e}")
            
            # 2. Supprimer les prédictions obsolètes de bot_data
            current_active = data.get('active_predictions', [])
            updated_active = []
            
            for pred in current_active:
                pred_id = pred.get('event_id')
                # Garder si c'est une vraie prédiction ou si on a un pari placé
                if pred_id in real_predictions or pred.get('our_bet'):
                    updated_active.append(pred)
                else:
                    removed.append(pred.get('title', pred_id))
                    logger.info(f"🗑️ Suppression prédiction obsolète: {pred.get('title', pred_id)}")
            
            # 3. Ajouter les nouvelles prédictions trouvées
            for pred_id, pred_data in real_predictions.items():
                # Vérifier si cette prédiction est déjà dans bot_data
                exists = any(p.get('event_id') == pred_id for p in updated_active)
                
                if not exists:
                    prediction = pred_data['prediction']
                    streamer = pred_data['streamer']
                    
                    # Construire les outcomes
                    outcomes = []
                    for outcome in prediction.get('outcomes', []):
                        total_users = outcome.get('totalUsers', 0)
                        total_points = outcome.get('totalPoints', 0)
                        outcomes.append({
                            'title': outcome.get('title', ''),
                            'color': outcome.get('color', 'BLUE'),
                            'users': total_users,
                            'points': total_points,
                            'odds': round(1 / (outcome.get('oddsPercentage', 50) / 100), 2) if outcome.get('oddsPercentage', 0) > 0 else 1,
                            'percentage': outcome.get('percentageUsers', 50)
                        })
                    
                    new_pred = {
                        'event_id': pred_id,
                        'streamer': streamer,
                        'title': prediction.get('title', ''),
                        'outcomes': outcomes,
                        'time_remaining': prediction.get('prediction_window_seconds', 0),
                        'total_time': prediction.get('prediction_window_seconds', 120),
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'status': 'active' if prediction.get('status') == 'ACTIVE' else 'locked',
                        'our_bet': None
                    }
                    
                    updated_active.append(new_pred)
                    added.append(f"{streamer}: {prediction.get('title', '')}")
                    logger.info(f"➕ Nouvelle prédiction ajoutée: {streamer} - {prediction.get('title', '')}")
                else:
                    synced.append(pred_id)
            
            # 4. Sauvegarder
            data['active_predictions'] = updated_active
            
            with _bot_data_lock:
                atomic_write_json(bot_data_path, data)
            
            result = {
                'success': True,
                'streams_scanned': len(active_streams),
                'predictions_found': len(real_predictions),
                'synced': len(synced),
                'added': added,
                'removed': removed,
                'total_active': len(updated_active),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            logger.info(f"✅ Synchronisation terminée: {len(added)} ajoutées, {len(removed)} supprimées, {len(synced)} synchronisées")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

    def recovery_scan(self) -> Dict[str, Any]:
        """
        Effectue un scan complet de récupération.
        Alias pour sync_predictions_to_bot_data avec logging supplémentaire.
        """
        logger.info("🔄 Démarrage du scan de récupération...")
        return self.sync_predictions_to_bot_data()
