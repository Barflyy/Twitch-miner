"""
SmartBetTiming V2 - Système ultra-intelligent de timing pour les bets
Adaptatif selon durée de prédiction, profil streamer, et qualité des données
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, Callable
from TwitchChannelPointsMiner.classes.entities.Bet import OutcomeKeys

logger = logging.getLogger(__name__)

TOTAL_USERS = OutcomeKeys.TOTAL_USERS
TOTAL_POINTS = OutcomeKeys.TOTAL_POINTS
PERCENTAGE_USERS = OutcomeKeys.PERCENTAGE_USERS


class PredictionDurationProfile:
    """Profils de paramètres selon la durée de prédiction."""

    @staticmethod
    def get_params(prediction_window_seconds: int, streamer_profile: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Retourne les paramètres optimaux selon la durée de prédiction.

        Args:
            prediction_window_seconds: Durée totale de la prédiction
            streamer_profile: Profil du streamer (optionnel)

        Returns:
            Dict avec min_users, fallback_time, check_interval, absolute_min_users
        """
        duration = prediction_window_seconds

        # 1. Prédictions ultra-courtes (30-60s)
        if duration <= 60:
            params = {
                'min_users': 30,
                'min_points': 3000,
                'fallback_time': 12,
                'check_interval': 3,
                'absolute_min_users': 5,  # Réduit pour permettre MOST_VOTED avec peu d'utilisateurs
                'stability_threshold_pct': 8,  # Plus permissif
                'growth_threshold': 0.30,  # Accepter croissance plus rapide
            }

        # 2. Prédictions courtes (1-3min)
        elif duration <= 180:
            params = {
                'min_users': 80,
                'min_points': 5000,
                'fallback_time': 20,
                'check_interval': 4,
                'absolute_min_users': 5,  # Réduit pour permettre MOST_VOTED avec peu d'utilisateurs
                'stability_threshold_pct': 6,
                'growth_threshold': 0.25,
            }

        # 3. Prédictions moyennes (3-10min)
        elif duration <= 600:
            params = {
                'min_users': 150,
                'min_points': 10000,
                'fallback_time': 40,
                'check_interval': 5,
                'absolute_min_users': 5,  # Réduit pour permettre MOST_VOTED avec peu d'utilisateurs
                'stability_threshold_pct': 5,
                'growth_threshold': 0.20,
            }

        # 4. Prédictions longues (10-30min)
        else:
            params = {
                'min_users': 200,
                'min_points': 15000,
                'fallback_time': 90,
                'check_interval': 10,
                'absolute_min_users': 5,  # Réduit pour permettre MOST_VOTED avec peu d'utilisateurs
                'stability_threshold_pct': 3,  # Exiger plus de stabilité
                'growth_threshold': 0.15,
            }

        # Ajustements selon le profil du streamer
        if streamer_profile:
            # 5. Early closers (ferment souvent tôt)
            if streamer_profile.get('early_closer', False):
                params['fallback_time'] = int(params['fallback_time'] * 1.5)
                params['min_users'] = int(params['min_users'] * 0.7)

            # 6. Petits streamers (<100 viewers moyens)
            if streamer_profile.get('avg_viewers', 1000) < 100:
                params['min_users'] = max(20, int(params['min_users'] * 0.4))
                params['min_points'] = int(params['min_points'] * 0.5)
                params['absolute_min_users'] = 10

            # 7. Gros streamers (>1000 viewers moyens)
            elif streamer_profile.get('avg_viewers', 0) > 1000:
                params['min_users'] = 250
                params['min_points'] = 50000
                params['stability_threshold_pct'] = 3

            # 9. Prédictions troll/test (cancel_rate > 15%)
            if streamer_profile.get('cancel_rate', 0) > 0.15:
                params['min_wait_time'] = 45  # Attendre 45s minimum

        return params


class SmartBetTiming:
    """
    Système intelligent V2 de timing pour les bets.
    S'adapte automatiquement selon la durée et le profil du streamer.
    """

    def __init__(self, profiler=None):
        """
        Args:
            profiler: Instance de StreamerPredictionProfiler (optionnel)
        """
        self.active_predictions = {}
        self.lock = threading.Lock()
        self.profiler = profiler

        # Importer dynamiquement le profiler si disponible
        if self.profiler is None:
            try:
                from TwitchChannelPointsMiner.classes.entities.StreamerPredictionProfiler import StreamerPredictionProfiler
                self.profiler = StreamerPredictionProfiler()
            except ImportError:
                logger.debug("StreamerPredictionProfiler non disponible")

    def start_monitoring(self, event_prediction, bet_callback: Callable):
        """
        Démarre le monitoring adaptatif d'une prédiction.

        Args:
            event_prediction: Instance EventPrediction
            bet_callback: Fonction à appeler pour parier (event_prediction, data_quality_multiplier)
        """
        event_id = event_prediction.event_id
        streamer = event_prediction.streamer
        duration = event_prediction.prediction_window_seconds

        # Récupère le profil du streamer
        streamer_profile = None
        if self.profiler and hasattr(streamer, 'channel_id'):
            try:
                profile_data = self.profiler.get_streamer_profile(str(streamer.channel_id))
                if profile_data:
                    streamer_profile = {
                        'early_closer': profile_data.get('early_close_rate', 0) > 0.4,
                        'cancel_rate': profile_data.get('cancel_rate', 0),
                        'avg_viewers': profile_data.get('stats', {}).get('avg_prediction_users', 100),
                        'crowd_accuracy': profile_data.get('crowd_accuracy', 0.5),
                        'type': profile_data.get('profile_type', 'UNKNOWN')
                    }
            except Exception as e:
                logger.debug(f"Erreur récupération profil streamer: {e}")

        # Calcule les paramètres optimaux
        params = PredictionDurationProfile.get_params(duration, streamer_profile)

        with self.lock:
            self.active_predictions[event_id] = {
                'detected_at': time.time(),
                'snapshots': [],
                'prediction_start_time': event_prediction.prediction_start_time,
                'prediction_window_seconds': duration,
                'event': event_prediction,
                'callback': bet_callback,
                'monitoring': True,
                'bet_placed': False,
                'params': params,
                'streamer_profile': streamer_profile,
            }

        profile_info = f" | Profil: {streamer_profile.get('type', 'UNKNOWN')}" if streamer_profile else ""

        logger.info(f"""
        🔍 MONITORING V2 STARTED
        ├─ Streamer: {streamer.username}
        ├─ Prédiction: {event_prediction.title}
        ├─ Durée: {duration}s{profile_info}
        ├─ Paramètres adaptatifs:
        │  ├─ Min users: {params['min_users']} (absolu: {params['absolute_min_users']})
        │  ├─ Fallback: T-{params['fallback_time']}s
        │  └─ Check interval: {params['check_interval']}s
        └─ Stratégie: Timing adaptatif avec qualité des données
        """.strip())

        # Lance le monitoring
        monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(event_id,),
            daemon=True,
            name=f"SmartBetV2-{event_id[:8]}"
        )
        monitor_thread.start()

    def _monitoring_loop(self, event_id: str):
        """Boucle de monitoring principale avec logique adaptative."""
        try:
            while True:
                with self.lock:
                    if event_id not in self.active_predictions:
                        return

                    pred_data = self.active_predictions[event_id]
                    if not pred_data['monitoring'] or pred_data['bet_placed']:
                        return

                    event = pred_data['event']
                    params = pred_data['params']
                    streamer_profile = pred_data['streamer_profile']

                # Récupère les données actuelles
                current_data = self._get_current_data(event)

                if current_data is None or current_data['status'] != 'ACTIVE':
                    logger.warning(f"⚠️ Prédiction {event_id[:8]} fermée/invalide")
                    with self.lock:
                        if event_id in self.active_predictions:
                            del self.active_predictions[event_id]
                    return

                # Calcule le temps
                elapsed = time.time() - pred_data['detected_at']
                prediction_start = pred_data['prediction_start_time']
                prediction_window = pred_data['prediction_window_seconds']
                time_remaining = prediction_window - (time.time() - prediction_start)

                # Crée le snapshot
                snapshot = self._create_snapshot(current_data, elapsed, time_remaining)

                with self.lock:
                    if event_id in self.active_predictions:
                        self.active_predictions[event_id]['snapshots'].append(snapshot)
                        snapshots = self.active_predictions[event_id]['snapshots']
                        if len(snapshots) > 10:
                            self.active_predictions[event_id]['snapshots'] = snapshots[-10:]

                # === RÈGLE ABSOLUE : SKIP si < absolute_min_users ===
                if time_remaining <= params['fallback_time'] and snapshot['total_users'] < params['absolute_min_users']:
                    logger.warning(f"""
                    ❌ SKIP PREDICTION (données insuffisantes)
                    ├─ Users: {snapshot['total_users']} < {params['absolute_min_users']} (seuil minimal)
                    ├─ Points: {snapshot['total_points']:,}
                    └─ Raison: Pas assez de votants pour une décision fiable
                    """.strip())

                    with self.lock:
                        if event_id in self.active_predictions:
                            del self.active_predictions[event_id]
                    return

                # === 9. Détection prédictions troll/test ===
                if streamer_profile and streamer_profile.get('cancel_rate', 0) > 0.15:
                    min_wait = params.get('min_wait_time', 45)
                    if elapsed < min_wait and snapshot['total_users'] < 50:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"⏳ Streamer à cancel_rate élevé, attente {min_wait}s minimum")
                        time.sleep(params['check_interval'])
                        continue

                # === DÉCISION : Conditions optimales atteintes ? ===
                decision = self._should_bet_now(event_id, time_remaining, snapshot, params)

                if decision['should_bet']:
                    data_quality = decision.get('data_quality', 1.0)

                    logger.info(f"""
                    ✅ CONDITIONS OPTIMALES ATTEINTES
                    ├─ Raison: {decision['reason']}
                    ├─ Temps écoulé: {elapsed:.0f}s
                    ├─ Temps restant: {time_remaining:.0f}s
                    ├─ Users: {snapshot['total_users']} (min: {params['min_users']})
                    ├─ Points: {snapshot['total_points']:,}
                    └─ Qualité données: {data_quality*100:.0f}%
                    """.strip())

                    self._place_bet(event_id, data_quality)
                    return

                # === FALLBACK MODE ADAPTATIF ===
                if time_remaining <= params['fallback_time']:
                    # Calcule la qualité des données disponibles
                    data_quality = self._calculate_data_quality(snapshot, params)

                    # Détecte consensus instable
                    is_unstable = self._detect_unstable_consensus(event_id)

                    if is_unstable:
                        logger.warning(f"""
                        ❌ SKIP PREDICTION (consensus instable)
                        ├─ Variance > 8% entre snapshots OU inversion majoritaire
                        └─ Raison: Données trop chaotiques pour parier
                        """.strip())

                        with self.lock:
                            if event_id in self.active_predictions:
                                del self.active_predictions[event_id]
                        return

                    logger.warning(f"""
                    ⚠️ FALLBACK MODE ADAPTATIF
                    ├─ Temps restant: {time_remaining:.0f}s
                    ├─ Users: {snapshot['total_users']} (min: {params['min_users']})
                    ├─ Points: {snapshot['total_points']:,}
                    ├─ Qualité données: {data_quality*100:.0f}%
                    └─ Mise ajustée selon qualité disponible
                    """.strip())

                    self._place_bet(event_id, data_quality)
                    return

                # === 10. Détection sharp signals précoces ===
                sharp_signal = self._detect_early_sharp_signal(snapshot, current_data, elapsed)
                if sharp_signal['detected']:
                    logger.info(f"""
                    🎯 SHARP SIGNAL PRÉCOCE DÉTECTÉ
                    ├─ {sharp_signal['reason']}
                    ├─ Users: {snapshot['total_users']}
                    ├─ Temps écoulé: {elapsed:.0f}s
                    └─ Pari immédiat avec confiance réduite (60%)
                    """.strip())

                    self._place_bet(event_id, data_quality_multiplier=0.6)
                    return

                # Debug logging
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"""
                    ⏳ Monitoring V2 ({event_id[:8]})
                    ├─ Users: {snapshot['total_users']}/{params['min_users']}
                    ├─ {decision['reason']}
                    └─ T-{time_remaining:.0f}s
                    """.strip())

                time.sleep(params['check_interval'])

        except Exception as e:
            logger.error(f"❌ Erreur monitoring loop {event_id[:8]}: {e}", exc_info=True)
            with self.lock:
                if event_id in self.active_predictions:
                    del self.active_predictions[event_id]

    def _get_current_data(self, event_prediction) -> Optional[Dict[str, Any]]:
        """Récupère les données actuelles."""
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
            logger.debug(f"Erreur récupération données: {e}")
            return None

    def _create_snapshot(self, prediction_data: dict, elapsed: float, time_remaining: float) -> dict:
        """Crée un snapshot des données."""
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
                'option_1_users': 0,
                'option_2_users': 0,
                'option_1_points': 0,
                'option_2_points': 0,
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
            'option_1_users': outcomes[0].get(TOTAL_USERS, 0),
            'option_2_users': outcomes[1].get(TOTAL_USERS, 0) if len(outcomes) > 1 else 0,
            'option_1_points': outcomes[0].get(TOTAL_POINTS, 0),
            'option_2_points': outcomes[1].get(TOTAL_POINTS, 0) if len(outcomes) > 1 else 0,
        }

    def _should_bet_now(self, event_id: str, time_remaining: float, snapshot: dict, params: dict) -> dict:
        """
        Détermine si les conditions optimales sont atteintes.
        """
        with self.lock:
            if event_id not in self.active_predictions:
                return {'should_bet': False, 'reason': 'Prédiction supprimée'}

            snapshots = self.active_predictions[event_id]['snapshots']

        # Volume minimum
        if snapshot['total_users'] < params['min_users']:
            return {
                'should_bet': False,
                'reason': f"Pas assez de users ({snapshot['total_users']}/{params['min_users']})"
            }

        if snapshot['total_points'] < params['min_points']:
            return {
                'should_bet': False,
                'reason': f"Pas assez de points ({snapshot['total_points']:,}/{params['min_points']:,})"
            }

        # Stabilité (besoin de 2+ snapshots)
        if len(snapshots) < 2:
            return {
                'should_bet': False,
                'reason': "Pas assez de snapshots"
            }

        prev = snapshots[-2]
        curr = snapshots[-1]

        prev_users = prev.get('total_users', 0)
        if prev_users == 0:
            return {
                'should_bet': False,
                'reason': "Volume encore très faible"
            }

        user_growth = (curr['total_users'] - prev_users) / prev_users
        pct_change = abs(curr['option_1_pct'] - prev['option_1_pct'])

        # Croissance rapide
        if user_growth > params['growth_threshold']:
            return {
                'should_bet': False,
                'reason': f"Croissance rapide ({user_growth*100:.0f}%)"
            }

        # Instabilité
        if pct_change > params['stability_threshold_pct']:
            return {
                'should_bet': False,
                'reason': f"Pourcentages instables (Δ{pct_change:.1f}%)"
            }

        # CONDITIONS OPTIMALES !
        data_quality = self._calculate_data_quality(snapshot, params)

        return {
            'should_bet': True,
            'reason': f"Volume OK + Données stables",
            'data_quality': data_quality
        }

    def _calculate_data_quality(self, snapshot: dict, params: dict) -> float:
        """
        Calcule un score de qualité des données entre 0.0 et 1.0.

        Utilisé pour ajuster le montant du bet en FALLBACK MODE.
        """
        users_ratio = min(1.0, snapshot['total_users'] / params['min_users'])
        points_ratio = min(1.0, snapshot['total_points'] / params['min_points'])

        # Score moyen
        data_quality = (users_ratio + points_ratio) / 2

        # Système à 3 niveaux (table de l'utilisateur)
        if snapshot['total_users'] >= params['min_users']:
            return 1.0  # 100% - Données complètes
        elif snapshot['total_users'] >= 50:
            return min(0.7, data_quality)  # 30-70% selon volume
        elif snapshot['total_users'] >= 20:
            return 0.4  # 40% - Données faibles
        else:
            return 0.0  # SKIP (géré en amont)

    def _detect_unstable_consensus(self, event_id: str) -> bool:
        """
        Détecte un consensus instable (variance >8% ou inversion majoritaire).
        """
        with self.lock:
            if event_id not in self.active_predictions:
                return False

            snapshots = self.active_predictions[event_id]['snapshots']

        if len(snapshots) < 3:
            return False

        # Vérifie les 3 derniers snapshots
        recent = snapshots[-3:]

        # Variance des pourcentages
        pct_values = [s['option_1_pct'] for s in recent]
        variance = max(pct_values) - min(pct_values)

        if variance > 8:
            return True

        # Inversion majoritaire (option A devient minoritaire)
        for i in range(len(recent) - 1):
            prev_majority = recent[i]['option_1_pct'] > 50
            curr_majority = recent[i+1]['option_1_pct'] > 50

            if prev_majority != curr_majority:
                return True

        return False

    def _detect_early_sharp_signal(self, snapshot: dict, current_data: dict, elapsed: float) -> dict:
        """
        Détecte un sharp signal précoce (T+5-15s).

        Critères :
        - Minorité (<35%) avec avg bet 3x+ supérieur
        - Volume absolu > 30 users
        - Au moins 10 users sur option minoritaire
        """
        if elapsed < 5 or elapsed > 15:
            return {'detected': False}

        if snapshot['total_users'] < 30:
            return {'detected': False}

        outcomes = current_data.get('outcomes', [])
        if len(outcomes) < 2:
            return {'detected': False}

        # Identifie la minorité
        pct1 = outcomes[0].get(PERCENTAGE_USERS, 0)
        pct2 = outcomes[1].get(PERCENTAGE_USERS, 0)

        if pct1 < 35:
            minority_idx = 0
            minority_pct = pct1
        elif pct2 < 35:
            minority_idx = 1
            minority_pct = pct2
        else:
            return {'detected': False}

        majority_idx = 1 - minority_idx

        # Vérifie le nombre d'users sur minorité
        minority_users = outcomes[minority_idx].get(TOTAL_USERS, 0)
        if minority_users < 10:
            return {'detected': False}

        # Calcule l'avg bet de chaque côté
        minority_points = outcomes[minority_idx].get(TOTAL_POINTS, 0)
        majority_points = outcomes[majority_idx].get(TOTAL_POINTS, 0)
        majority_users = outcomes[majority_idx].get(TOTAL_USERS, 1)

        avg_minority = minority_points / max(minority_users, 1)
        avg_majority = majority_points / max(majority_users, 1)

        # Sharp signal si avg minorité 3x+ supérieur
        if avg_minority >= avg_majority * 3:
            return {
                'detected': True,
                'reason': f"Minorité {minority_pct:.0f}% avec avg bet {avg_minority/avg_majority:.1f}x supérieur",
                'minority_choice': minority_idx
            }

        return {'detected': False}

    def _place_bet(self, event_id: str, data_quality_multiplier: float = 1.0):
        """Place le bet avec ajustement de qualité."""
        with self.lock:
            if event_id not in self.active_predictions or self.active_predictions[event_id]['bet_placed']:
                return

            self.active_predictions[event_id]['bet_placed'] = True
            self.active_predictions[event_id]['monitoring'] = False
            callback = self.active_predictions[event_id]['callback']
            event = self.active_predictions[event_id]['event']

        try:
            # Injecte le data_quality_multiplier dans l'event pour ajustement du montant
            event._data_quality_multiplier = data_quality_multiplier
            callback(event)
        except Exception as e:
            logger.error(f"❌ Erreur callback bet {event_id[:8]}: {e}", exc_info=True)

        with self.lock:
            if event_id in self.active_predictions:
                del self.active_predictions[event_id]

    def stop_monitoring(self, event_id: str):
        """Arrête le monitoring."""
        with self.lock:
            if event_id in self.active_predictions:
                self.active_predictions[event_id]['monitoring'] = False
                del self.active_predictions[event_id]

    def cleanup(self):
        """Nettoie toutes les prédictions actives."""
        with self.lock:
            self.active_predictions.clear()
