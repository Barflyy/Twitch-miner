"""
OptimalBetTimingSystem - Système complet combinant toutes les stratégies de timing optimal
"""

import logging
import time
from typing import Dict, Any, Optional
from TwitchChannelPointsMiner.classes.entities.DynamicBetTiming import DynamicBetTiming
from TwitchChannelPointsMiner.classes.entities.EarlyCloseDetector import EarlyCloseDetector
from TwitchChannelPointsMiner.classes.entities.AdaptiveBetStrategy import AdaptiveBetStrategy

logger = logging.getLogger(__name__)


class OptimalBetTimingSystem:
    """
    Système complet combinant toutes les stratégies.
    
    Logique :
    1. Check le profil du streamer (close early?)
    2. Si streamer "early closer" → mode agressif (bet dès que stable)
    3. Si streamer normal → mode hybride (early + fallback)
    4. Si streamer "late closer" → mode patient (attend max d'infos)
    """

    def __init__(self, bet_strategy: Optional[AdaptiveBetStrategy] = None):
        self.stability_detector = DynamicBetTiming()
        self.early_close_detector = EarlyCloseDetector()
        self.bet_strategy = bet_strategy or AdaptiveBetStrategy()
        self.active_predictions = {}  # Track les prédictions en cours

    def get_optimal_bet_timing(
        self,
        prediction_data: Dict[str, Any],
        current_timestamp: time.struct_time,
        announced_duration: int
    ) -> Dict[str, Any]:
        """
        Calcule le timing optimal pour placer un bet.
        
        Args:
            prediction_data: Données de la prédiction (outcomes, time_remaining, etc.)
            current_timestamp: Timestamp actuel
            announced_duration: Durée annoncée de la prédiction en secondes
            
        Returns:
            dict avec:
                - 'wait_time': secondes à attendre avant de bet
                - 'strategy': 'early' | 'standard' | 'late'
                - 'reason': raison du timing
                - 'confidence': niveau de confiance
        """
        prediction_id = prediction_data.get('id') or prediction_data.get('event_id', '')
        streamer_id = prediction_data.get('streamer_id', '')
        streamer_name = prediction_data.get('streamer_name', '')
        
        # 1. Analyse le profil du streamer
        close_pattern = self.early_close_detector.get_streamer_close_pattern(streamer_id)
        
        logger.debug(f"""
        📊 PROFIL DU STREAMER ({streamer_name})
        ├─ Early close rate: {close_pattern['early_close_rate']:.0%}
        ├─ Avg offset: {close_pattern['avg_close_offset']:.0f}s
        ├─ Recommandation: {close_pattern['recommendation']}
        └─ Sample: {close_pattern['sample_size']} prédictions
        """.strip())

        # 2. Détermine la stratégie de timing
        if close_pattern['recommendation'] == 'early':
            # === STRATÉGIE AGGRESSIVE ===
            strategy = 'early'
            min_volume = 50  # Seuil de volume abaissé
            max_wait_time = announced_duration - 30  # Bet au plus tard à T-30s
            check_interval = 5

        elif close_pattern['recommendation'] == 'late':
            # === STRATÉGIE PATIENTE ===
            strategy = 'late'
            min_volume = 150  # Seuil de volume élevé
            max_wait_time = 10  # Bet au plus tard à T-10s
            check_interval = 15

        else:
            # === STRATÉGIE STANDARD ===
            strategy = 'standard'
            min_volume = 100
            max_wait_time = 15
            check_interval = 10

        # 3. Analyse la stabilité des données
        outcomes = prediction_data.get('outcomes', [])
        time_remaining = prediction_data.get('time_remaining', announced_duration)
        
        # Crée un snapshot de données pour analyse
        monitor_data = {
            'id': prediction_id,
            'outcomes': outcomes,
            'time_remaining': time_remaining
        }
        
        # Analyse de stabilité (monitor_prediction est synchrone)
        try:
            stability = self.stability_detector.monitor_prediction(prediction_id, monitor_data)
        except Exception as e:
            logger.debug(f"Erreur lors de l'analyse de stabilité: {e}")
            # Fallback: mode synchrone simplifié
            stability = self._quick_stability_check(outcomes, time_remaining)

        # 4. Check pour sharp signal
        has_sharp = self.stability_detector.get_sharp_signal(monitor_data)

        # 5. Détermine le timing optimal
        should_bet_now = False
        wait_time = 0
        reason = ""

        # Condition 1 : Données stables + volume suffisant
        if stability.get('ready_to_bet') and \
           stability.get('stable_data', {}).get('total_users', 0) >= min_volume:
            should_bet_now = True
            wait_time = 0  # Bet immédiatement
            reason = f"Données stables ({stability.get('reason', '')})"

        # Condition 2 : Sharp signal détecté (bet immédiatement)
        elif has_sharp:
            should_bet_now = True
            wait_time = 0
            reason = "Sharp signal détecté (priorité haute)"

        # Condition 3 : Temps limite atteint (fallback)
        elif time_remaining <= max_wait_time:
            should_bet_now = True
            # Bet au moment optimal (5-10s avant la fin selon stratégie)
            optimal_bet_time = max(5, min(10, time_remaining - 3))
            wait_time = max(0, time_remaining - optimal_bet_time)
            reason = f"Fallback (T-{time_remaining:.0f}s, stratégie: {strategy})"

        else:
            # Pas encore prêt, attendre
            should_bet_now = False
            wait_time = min(check_interval, stability.get('wait_time', 10))
            reason = stability.get('reason', f'En attente de stabilité (stratégie: {strategy})')

        return {
            'wait_time': wait_time,
            'should_bet_now': should_bet_now,
            'strategy': strategy,
            'reason': reason,
            'confidence': stability.get('confidence', 0.5),
            'stability': stability,
            'has_sharp_signal': has_sharp,
            'close_pattern': close_pattern
        }

    def _quick_stability_check(self, outcomes: list, time_remaining: int) -> Dict[str, Any]:
        """
        Check rapide de stabilité sans historique (fallback synchrone).
        """
        if len(outcomes) < 2:
            return {
                'ready_to_bet': False,
                'reason': 'Pas assez d\'outcomes',
                'confidence': 0,
                'wait_time': 10
            }

        total_users = sum(o.get('total_users', 0) for o in outcomes)

        if total_users < 50:
            return {
                'ready_to_bet': False,
                'reason': f'Volume insuffisant ({total_users} users)',
                'confidence': 0,
                'wait_time': 15,
                'stable_data': {'total_users': total_users}
            }

        # Si volume OK et temps restant suffisant, on peut bet
        if total_users >= 100 and time_remaining > 10:
            return {
                'ready_to_bet': True,
                'reason': f'Volume suffisant ({total_users} users)',
                'confidence': 0.7,
                'wait_time': 0,
                'stable_data': {'total_users': total_users}
            }

        return {
            'ready_to_bet': False,
            'reason': 'Attente de plus de volume',
            'confidence': 0.3,
            'wait_time': 10,
            'stable_data': {'total_users': total_users}
        }

    def log_prediction_result(
        self,
        streamer_id: str,
        streamer_name: str,
        prediction_id: str,
        announced_duration: int,
        actual_duration: int
    ):
        """Enregistre le résultat d'une prédiction pour apprentissage."""
        self.early_close_detector.log_prediction_close(
            streamer_id=streamer_id,
            streamer_name=streamer_name,
            prediction_id=prediction_id,
            announced_duration=announced_duration,
            actual_duration=actual_duration
        )

    def cleanup_prediction(self, prediction_id: str):
        """Nettoie les données d'une prédiction terminée."""
        self.stability_detector.cleanup(prediction_id)
        if prediction_id in self.active_predictions:
            del self.active_predictions[prediction_id]

