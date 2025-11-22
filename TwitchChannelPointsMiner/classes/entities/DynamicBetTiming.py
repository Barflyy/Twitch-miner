"""
DynamicBetTiming - Détecte quand les données de prédiction sont stables pour placer le bet au bon moment
"""

import logging
import time
from typing import Dict, Any, Optional, List
from TwitchChannelPointsMiner.classes.entities.Bet import OutcomeKeys

logger = logging.getLogger(__name__)

# Mapping des clés pour compatibilité
TOTAL_USERS = OutcomeKeys.TOTAL_USERS
TOTAL_POINTS = OutcomeKeys.TOTAL_POINTS
PERCENTAGE_USERS = OutcomeKeys.PERCENTAGE_USERS
TOP_POINTS = OutcomeKeys.TOP_POINTS
ODDS = OutcomeKeys.ODDS


class DynamicBetTiming:
    """
    Détermine le moment optimal pour parier en fonction de la stabilité des données.
    """

    def __init__(self):
        self.prediction_snapshots = {}  # Stocke l'évolution des données
        self.stability_threshold = 3    # Nombre de snapshots stables requis

    def monitor_prediction(self, prediction_id: str, prediction_data: dict) -> Dict[str, Any]:
        """
        Surveille une prédiction et détecte quand les données sont stables.

        Args:
            prediction_id: ID unique de la prédiction
            prediction_data: Données de la prédiction (outcomes, time_remaining, etc.)

        Returns:
            dict avec 'ready_to_bet' et 'confidence_level'
        """

        if prediction_id not in self.prediction_snapshots:
            self.prediction_snapshots[prediction_id] = {
                'snapshots': [],
                'first_seen': time.time(),
                'time_left': prediction_data.get('time_remaining', 0)
            }

        current_snapshot = self._create_snapshot(prediction_data)
        self.prediction_snapshots[prediction_id]['snapshots'].append(current_snapshot)

        # Nettoie les vieux snapshots (garde max 10)
        if len(self.prediction_snapshots[prediction_id]['snapshots']) > 10:
            self.prediction_snapshots[prediction_id]['snapshots'] = \
                self.prediction_snapshots[prediction_id]['snapshots'][-10:]

        # Met à jour le temps restant
        self.prediction_snapshots[prediction_id]['time_left'] = \
            prediction_data.get('time_remaining', 0)

        # Analyse de stabilité
        stability_analysis = self._analyze_stability(prediction_id)

        return stability_analysis

    def _create_snapshot(self, prediction_data: dict) -> dict:
        """Crée un snapshot des données importantes."""

        outcomes = prediction_data.get('outcomes', [])

        if len(outcomes) < 2:
            # Retourne un snapshot minimal si pas assez d'outcomes
            return {
                'timestamp': time.time(),
                'time_remaining': prediction_data.get('time_remaining', 0),
                'total_users': 0,
                'total_points': 0,
                'option_1_pct': 0,
                'option_2_pct': 0,
                'option_1_avg_bet': 0,
                'option_2_avg_bet': 0,
                'option_1_top': 0,
                'option_2_top': 0,
                'odds_1': 0,
                'odds_2': 0
            }

        outcome1 = outcomes[0]
        outcome2 = outcomes[1]

        total_users = sum(o.get(TOTAL_USERS, 0) for o in outcomes)
        total_points = sum(o.get(TOTAL_POINTS, 0) for o in outcomes)

        return {
            'timestamp': time.time(),
            'time_remaining': prediction_data.get('time_remaining', 0),
            'total_users': total_users,
            'total_points': total_points,
            'option_1_pct': outcome1.get(PERCENTAGE_USERS, 0),
            'option_2_pct': outcome2.get(PERCENTAGE_USERS, 0),
            'option_1_avg_bet': outcome1.get(TOTAL_POINTS, 0) / max(outcome1.get(TOTAL_USERS, 1), 1),
            'option_2_avg_bet': outcome2.get(TOTAL_POINTS, 0) / max(outcome2.get(TOTAL_USERS, 1), 1),
            'option_1_top': outcome1.get(TOP_POINTS, 0),
            'option_2_top': outcome2.get(TOP_POINTS, 0),
            'odds_1': outcome1.get(ODDS, 0),
            'odds_2': outcome2.get(ODDS, 0)
        }

    def _analyze_stability(self, prediction_id: str) -> Dict[str, Any]:
        """
        Analyse si les données sont suffisamment stables pour prendre une décision.

        Critères de stabilité :
        1. Volume suffisant (>100 users)
        2. Pourcentages stabilisés (variance < 5% sur les derniers snapshots)
        3. Avg bets stabilisés (variance < 20%)
        4. Au moins 3 snapshots consécutifs stables
        """

        if prediction_id not in self.prediction_snapshots:
            return {
                'ready_to_bet': False,
                'reason': 'Pas de données',
                'confidence': 0,
                'wait_time': 10
            }

        data = self.prediction_snapshots[prediction_id]
        snapshots = data['snapshots']

        # Besoin d'au moins 3 snapshots pour analyser la tendance
        if len(snapshots) < 3:
            return {
                'ready_to_bet': False,
                'reason': 'Pas assez de données',
                'confidence': 0,
                'wait_time': 10  # Attendre 10 secondes
            }

        # Prend les 3 derniers snapshots
        recent = snapshots[-3:]

        # === CRITÈRE 1 : Volume suffisant ===
        latest_users = recent[-1]['total_users']
        if latest_users < 100:
            return {
                'ready_to_bet': False,
                'reason': f'Volume insuffisant ({latest_users} users)',
                'confidence': 0,
                'wait_time': 15
            }

        # === CRITÈRE 2 : Stabilité des pourcentages ===
        pct_variance = self._calculate_variance([s['option_1_pct'] for s in recent])

        if pct_variance > 5:  # Variance > 5%
            return {
                'ready_to_bet': False,
                'reason': f'Pourcentages instables (var: {pct_variance:.1f}%)',
                'confidence': 0,
                'wait_time': 10
            }

        # === CRITÈRE 3 : Stabilité des avg bets ===
        avg1_variance = self._calculate_variance([s['option_1_avg_bet'] for s in recent])
        avg2_variance = self._calculate_variance([s['option_2_avg_bet'] for s in recent])
        
        # Évite division par zéro
        avg1_mean = recent[-1]['option_1_avg_bet'] or 1
        avg_variance_pct = max(avg1_variance, avg2_variance) / avg1_mean * 100

        if avg_variance_pct > 20:  # Variance > 20%
            return {
                'ready_to_bet': False,
                'reason': f'Avg bets instables (var: {avg_variance_pct:.0f}%)',
                'confidence': 0,
                'wait_time': 10
            }

        # === CRITÈRE 4 : Croissance du volume ralentit ===
        # Si les users continuent d'affluer rapidement, attendre
        if len(recent) >= 2 and recent[-2]['total_users'] > 0:
            user_growth_rate = (recent[-1]['total_users'] - recent[-2]['total_users']) / \
                             max(recent[-2]['total_users'], 1)

            if user_growth_rate > 0.15:  # +15% en snapshot = croissance rapide
                return {
                    'ready_to_bet': False,
                    'reason': f'Volume encore en croissance ({user_growth_rate*100:.0f}%/snapshot)',
                    'confidence': 0,
                    'wait_time': 10
                }

        # === DONNÉES STABLES ! ===
        # Calcule un score de confiance basé sur le volume et la stabilité
        confidence = min(
            (latest_users / 500) * 0.5 +  # Volume (max 0.5)
            (1 - pct_variance / 10) * 0.3 +  # Stabilité pct (max 0.3)
            (1 - avg_variance_pct / 30) * 0.2,  # Stabilité avg (max 0.2)
            1.0
        )

        return {
            'ready_to_bet': True,
            'reason': f'Données stables (vol: {latest_users}, var_pct: {pct_variance:.1f}%)',
            'confidence': confidence,
            'time_remaining': recent[-1]['time_remaining'],
            'stable_data': recent[-1]  # Snapshot stable pour la décision
        }

    def _calculate_variance(self, values: List[float]) -> float:
        """Calcule la variance d'une série de valeurs."""
        if len(values) < 2:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)

        return variance ** 0.5  # Standard deviation

    def cleanup(self, prediction_id: str):
        """Nettoie les données d'une prédiction terminée."""
        if prediction_id in self.prediction_snapshots:
            del self.prediction_snapshots[prediction_id]

    def get_sharp_signal(self, prediction_data: dict) -> bool:
        """
        Détection rapide de sharp signal.
        
        Sharp signal = minorité (<35%) avec avg bet 2x supérieur
        """
        outcomes = prediction_data.get('outcomes', [])

        if len(outcomes) < 2:
            return False

        avg1 = outcomes[0].get(TOTAL_POINTS, 0) / max(outcomes[0].get(TOTAL_USERS, 1), 1)
        avg2 = outcomes[1].get(TOTAL_POINTS, 0) / max(outcomes[1].get(TOTAL_USERS, 1), 1)

        pct1 = outcomes[0].get(PERCENTAGE_USERS, 0)
        pct2 = outcomes[1].get(PERCENTAGE_USERS, 0)

        # Sharp signal = minorité (<35%) avec avg bet 2x supérieur
        if pct1 < 35 and avg1 > avg2 * 2.0:
            return True
        if pct2 < 35 and avg2 > avg1 * 2.0:
            return True

        return False

