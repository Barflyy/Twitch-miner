"""
SmartBetTiming - Système intelligent de timing pour les bets
Remplace le timer fixe par un monitoring adaptatif basé sur les données
"""

import logging
import time
import threading
from typing import Dict, Any, Optional
from TwitchChannelPointsMiner.classes.entities.Bet import OutcomeKeys

logger = logging.getLogger(__name__)

TOTAL_USERS = OutcomeKeys.TOTAL_USERS
TOTAL_POINTS = OutcomeKeys.TOTAL_POINTS
PERCENTAGE_USERS = OutcomeKeys.PERCENTAGE_USERS


class SmartBetTiming:
    """
    Système intelligent de timing pour les bets.
    Remplace le timer fixe de 10s par un monitoring adaptatif.
    
    Attend que les données soient stables avant de parier.
    """

    def __init__(
        self,
        min_users_to_bet: int = 50,
        min_total_points: int = 5000,
        check_interval: float = 5.0,
        fallback_time: float = 15.0
    ):
        """
        Args:
            min_users_to_bet: Minimum de users avant de parier (défaut: 50)
            min_total_points: Minimum de points en jeu (défaut: 5000)
            check_interval: Intervalle entre chaque vérification en secondes (défaut: 5.0)
            fallback_time: Temps avant la fin pour fallback en secondes (défaut: 15.0)
        """
        self.active_predictions = {}  # Stocke l'historique de chaque prédiction
        self.min_users_to_bet = min_users_to_bet
        self.min_total_points = min_total_points
        self.check_interval = check_interval
        self.fallback_time = fallback_time
        self.lock = threading.Lock()

    def start_monitoring(self, event_prediction, bet_callback):
        """
        Démarre le monitoring d'une prédiction.
        
        Args:
            event_prediction: Instance EventPrediction à monitorer
            bet_callback: Fonction à appeler quand il faut parier (event_prediction)
        """
        event_id = event_prediction.event_id
        streamer = event_prediction.streamer

        with self.lock:
            # Initialise le tracking
            self.active_predictions[event_id] = {
                'detected_at': time.time(),
                'snapshots': [],
                'prediction_start_time': event_prediction.prediction_start_time,
                'prediction_window_seconds': event_prediction.prediction_window_seconds,
                'event': event_prediction,
                'callback': bet_callback,
                'monitoring': True,
                'bet_placed': False
            }

        logger.info(f"""
        🔍 MONITORING STARTED
        ├─ Streamer: {streamer.username}
        ├─ Prédiction: {event_prediction.title}
        ├─ Event ID: {event_id}
        └─ Stratégie: Attente de données stables (min {self.min_users_to_bet} users, {self.min_total_points:,} pts)
        """.strip())

        # Lance le monitoring dans un thread séparé
        monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(event_id,),
            daemon=True,
            name=f"SmartBetTiming-{event_id[:8]}"
        )
        monitor_thread.start()

    def _monitoring_loop(self, event_id: str):
        """Boucle de monitoring principale."""
        try:
            while True:
                with self.lock:
                    if event_id not in self.active_predictions:
                        return  # Prédiction supprimée
                    
                    pred_data = self.active_predictions[event_id]
                    if not pred_data['monitoring'] or pred_data['bet_placed']:
                        return  # Monitoring arrêté ou bet déjà placé

                    event = pred_data['event']
                
                # Récupère les données actuelles depuis event.bet.outcomes
                current_data = self._get_current_data(event)
                
                if current_data is None or current_data['status'] != 'ACTIVE':
                    logger.warning(f"⚠️ Prédiction {event_id} fermée ou invalide, arrêt du monitoring")
                    with self.lock:
                        if event_id in self.active_predictions:
                            del self.active_predictions[event_id]
                    return

                # Calcule le temps écoulé et restant
                elapsed = time.time() - pred_data['detected_at']
                prediction_start = pred_data['prediction_start_time']
                prediction_window = pred_data['prediction_window_seconds']
                time_remaining = prediction_window - (time.time() - prediction_start)

                # Enregistre le snapshot
                snapshot = self._create_snapshot(current_data, elapsed, time_remaining)
                
                with self.lock:
                    if event_id in self.active_predictions:
                        self.active_predictions[event_id]['snapshots'].append(snapshot)
                        # Garde max 10 snapshots
                        snapshots = self.active_predictions[event_id]['snapshots']
                        if len(snapshots) > 10:
                            self.active_predictions[event_id]['snapshots'] = snapshots[-10:]

                # === DÉCISION : Faut-il parier maintenant ? ===
                decision = self._should_bet_now(event_id, time_remaining, snapshot)

                if decision['should_bet']:
                    logger.info(f"""
                    ✅ CONDITIONS REMPLIES
                    ├─ Raison: {decision['reason']}
                    ├─ Temps écoulé: {elapsed:.0f}s
                    ├─ Temps restant: {time_remaining:.0f}s
                    ├─ Users: {snapshot['total_users']}
                    └─ Points: {snapshot['total_points']:,}
                    """.strip())

                    with self.lock:
                        if event_id in self.active_predictions and not self.active_predictions[event_id]['bet_placed']:
                            self.active_predictions[event_id]['bet_placed'] = True
                            self.active_predictions[event_id]['monitoring'] = False
                            callback = self.active_predictions[event_id]['callback']
                            event = self.active_predictions[event_id]['event']
                    
                    # Place le bet
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"❌ Erreur lors du callback de bet pour {event_id}: {e}", exc_info=True)
                    
                    # Nettoie
                    with self.lock:
                        if event_id in self.active_predictions:
                            del self.active_predictions[event_id]
                    
                    return

                # === FALLBACK : Temps limite atteint ===
                if time_remaining <= self.fallback_time:
                    logger.warning(f"""
                    ⚠️ FALLBACK MODE
                    ├─ Temps restant: {time_remaining:.0f}s
                    ├─ Users: {snapshot['total_users']} (min: {self.min_users_to_bet})
                    ├─ Points: {snapshot['total_points']:,} (min: {self.min_total_points:,})
                    └─ On parie maintenant ou jamais
                    """.strip())

                    with self.lock:
                        if event_id in self.active_predictions and not self.active_predictions[event_id]['bet_placed']:
                            self.active_predictions[event_id]['bet_placed'] = True
                            self.active_predictions[event_id]['monitoring'] = False
                            callback = self.active_predictions[event_id]['callback']
                            event = self.active_predictions[event_id]['event']
                    
                    # Place le bet
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"❌ Erreur lors du callback fallback pour {event_id}: {e}", exc_info=True)
                    
                    # Nettoie
                    with self.lock:
                        if event_id in self.active_predictions:
                            del self.active_predictions[event_id]
                    
                    return

                # Affiche l'état actuel (debug level pour éviter le spam)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"""
                    ⏳ Monitoring en cours ({event_id[:8]})
                    ├─ Users: {snapshot['total_users']} (min: {self.min_users_to_bet})
                    ├─ Points: {snapshot['total_points']:,} (min: {self.min_total_points:,})
                    ├─ Raison: {decision['reason']}
                    └─ Temps restant: {time_remaining:.0f}s
                    """.strip())

                # Attends avant le prochain check
                time.sleep(self.check_interval)

        except Exception as e:
            logger.error(f"❌ Erreur dans le monitoring loop pour {event_id}: {e}", exc_info=True)
            with self.lock:
                if event_id in self.active_predictions:
                    del self.active_predictions[event_id]

    def _get_current_data(self, event_prediction) -> Optional[Dict[str, Any]]:
        """Récupère les données actuelles depuis event.bet.outcomes."""
        try:
            if not hasattr(event_prediction, 'bet') or not hasattr(event_prediction.bet, 'outcomes'):
                return None
            
            outcomes = event_prediction.bet.outcomes
            if not outcomes or len(outcomes) < 2:
                return None

            return {
                'status': event_prediction.status,
                'outcomes': outcomes,
                'event_id': event_prediction.event_id
            }
        except Exception as e:
            logger.debug(f"Erreur récupération données pour {event_prediction.event_id}: {e}")
            return None

    def _create_snapshot(self, prediction_data: dict, elapsed: float, time_remaining: float) -> dict:
        """Crée un snapshot des données actuelles."""
        outcomes = prediction_data.get('outcomes', [])

        if len(outcomes) < 2:
            return {
                'timestamp': time.time(),
                'elapsed': elapsed,
                'time_remaining': time_remaining,
                'total_users': 0,
                'total_points': 0,
                'option_1_pct': 0,
                'option_2_pct': 0,
            }

        total_users = sum(o.get(TOTAL_USERS, 0) for o in outcomes)
        total_points = sum(o.get(TOTAL_POINTS, 0) for o in outcomes)

        return {
            'timestamp': time.time(),
            'elapsed': elapsed,
            'time_remaining': time_remaining,
            'total_users': total_users,
            'total_points': total_points,
            'option_1_pct': outcomes[0].get(PERCENTAGE_USERS, 0),
            'option_2_pct': outcomes[1].get(PERCENTAGE_USERS, 0) if len(outcomes) > 1 else 0,
        }

    def _should_bet_now(self, event_id: str, time_remaining: float, snapshot: dict) -> dict:
        """
        Détermine s'il faut parier maintenant.

        Critères :
        1. Volume suffisant (users + points)
        2. Données stables (2+ snapshots similaires)
        3. Pas trop tard (>fallback_time restantes)
        """

        with self.lock:
            if event_id not in self.active_predictions:
                return {'should_bet': False, 'reason': 'Prédiction supprimée'}
            
            snapshots = self.active_predictions[event_id]['snapshots']

        # === CRITÈRE 1 : Volume minimum ===
        if snapshot['total_users'] < self.min_users_to_bet:
            return {
                'should_bet': False,
                'reason': f"Pas assez de users ({snapshot['total_users']}/{self.min_users_to_bet})"
            }

        if snapshot['total_points'] < self.min_total_points:
            return {
                'should_bet': False,
                'reason': f"Pas assez de points ({snapshot['total_points']:,}/{self.min_total_points:,})"
            }

        # === CRITÈRE 2 : Stabilité (besoin de 2+ snapshots) ===
        if len(snapshots) < 2:
            return {
                'should_bet': False,
                'reason': "Pas assez de snapshots pour vérifier la stabilité"
            }

        # Compare les 2 derniers snapshots
        prev = snapshots[-2]
        curr = snapshots[-1]

        # Calcule la variation
        prev_users = prev.get('total_users', 0)
        if prev_users == 0:
            # Premiers users, attendre encore
            return {
                'should_bet': False,
                'reason': "Volume encore très faible (0 users précédemment)"
            }

        user_growth = (curr['total_users'] - prev_users) / prev_users
        pct_change = abs(curr['option_1_pct'] - prev['option_1_pct'])

        # Si croissance rapide (>20% de users en check_interval) → attendre
        if user_growth > 0.20:
            return {
                'should_bet': False,
                'reason': f"Croissance rapide ({user_growth*100:.0f}% users/{self.check_interval:.0f}s)"
            }

        # Si pourcentages encore instables (>5% de variation) → attendre
        if pct_change > 5:
            return {
                'should_bet': False,
                'reason': f"Pourcentages instables (Δ{pct_change:.1f}%)"
            }

        # === DONNÉES STABLES ! ===
        return {
            'should_bet': True,
            'reason': f"Volume OK ({snapshot['total_users']} users, {snapshot['total_points']:,} pts) + Données stables"
        }

    def stop_monitoring(self, event_id: str):
        """Arrête le monitoring d'une prédiction."""
        with self.lock:
            if event_id in self.active_predictions:
                self.active_predictions[event_id]['monitoring'] = False
                del self.active_predictions[event_id]

    def cleanup(self):
        """Nettoie toutes les prédictions actives."""
        with self.lock:
            self.active_predictions.clear()

