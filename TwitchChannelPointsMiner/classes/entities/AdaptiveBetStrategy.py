"""
AdaptiveBetStrategy - Stratégie qui s'adapte au profil de chaque streamer
"""

import logging
from typing import Optional, Dict, Any
from TwitchChannelPointsMiner.classes.entities.StreamerPredictionProfiler import StreamerPredictionProfiler
from TwitchChannelPointsMiner.classes.entities.CrowdWisdom import (
    CrowdWisdomStrategy, CrowdWisdomConfig, BetPatternAnalyzer
)
from TwitchChannelPointsMiner.classes.entities.Bet import OutcomeKeys

logger = logging.getLogger(__name__)


class AdaptiveBetStrategy:
    """
    Stratégie qui s'adapte au profil de chaque streamer.
    Combine le profiler avec la stratégie CrowdWisdom existante.
    """

    def __init__(self, profiler: StreamerPredictionProfiler = None):
        self.profiler = profiler or StreamerPredictionProfiler()
        
        # Configuration pour CrowdWisdom (stratégie de base)
        self.crowd_wisdom_config = CrowdWisdomConfig()
        self.base_strategy = CrowdWisdomStrategy(self.crowd_wisdom_config)
        self.pattern_analyzer = BetPatternAnalyzer(self.crowd_wisdom_config)

    def make_decision(
        self, 
        outcomes: list, 
        balance: int, 
        streamer_id: str = "",
        streamer_name: str = "",
        prediction_title: str = "",
        base_percentage: float = 5.0,
        max_bet: int = 50000,
        min_bet: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Décision adaptative basée sur le profil du streamer.
        
        Args:
            outcomes: Liste des outcomes de la prédiction
            balance: Balance actuelle de channel points
            streamer_id: ID du streamer
            streamer_name: Nom du streamer
            prediction_title: Titre de la prédiction
            base_percentage: Pourcentage de base pour le calcul
            max_bet: Montant maximum à parier
            min_bet: Montant minimum à parier
        
        Returns:
            Dict avec choice, amount, id, confidence, reason ou None si skip
        """
        if not streamer_id:
            # Pas d'ID streamer → utilise stratégie de base
            return self._use_base_strategy(outcomes, balance, prediction_title, base_percentage, max_bet, min_bet)

        # Prépare les données pour le profiler
        prediction_data = {
            'streamer_id': streamer_id,
            'streamer_name': streamer_name,
            'title': prediction_title,
            'outcomes': outcomes
        }

        # 1. Consulte le profil du streamer
        bet_assessment = self.profiler.should_bet_on_streamer(streamer_id, prediction_data)

        if not bet_assessment.get('should_bet', True):
            logger.info(f"❌ SKIP {streamer_name}: {bet_assessment.get('reason', '')}")
            return None

        # 2. Applique la stratégie recommandée
        strategy = bet_assessment.get('strategy', 'default')

        if strategy == 'follow_crowd':
            decision = self._follow_crowd_strategy(outcomes, balance, base_percentage, max_bet, min_bet)

        elif strategy == 'contrarian':
            decision = self._contrarian_strategy(outcomes, balance, base_percentage, max_bet, min_bet)

        elif strategy == 'sharp_only':
            decision = self._sharp_only_strategy(outcomes, balance, base_percentage, max_bet, min_bet)

        else:  # 'default'
            decision = self._use_base_strategy(outcomes, balance, prediction_title, base_percentage, max_bet, min_bet)

        if decision:
            # 3. Ajuste la confiance selon le profil
            confidence_modifier = bet_assessment.get('confidence_modifier', 1.0)
            if 'confidence' in decision:
                decision['confidence'] = min(decision['confidence'] * confidence_modifier, 1.0)
            
            # Ajuste le montant selon le modifier
            if 'amount' in decision and confidence_modifier != 1.0:
                original_amount = decision['amount']
                decision['amount'] = int(original_amount * confidence_modifier)
                decision['amount'] = max(min_bet, min(decision['amount'], max_bet))
            
            # Ajoute la raison du profiler
            if 'reason' in decision:
                decision['reason'] += f" | Profil: {bet_assessment.get('reason', '')}"
            else:
                decision['reason'] = bet_assessment.get('reason', '')

        return decision

    def _use_base_strategy(
        self, 
        outcomes: list, 
        balance: int, 
        title: str, 
        base_percentage: float, 
        max_bet: int, 
        min_bet: int
    ) -> Optional[Dict[str, Any]]:
        """Utilise la stratégie CrowdWisdom de base."""
        # Met à jour la config
        self.crowd_wisdom_config.BASE_PERCENTAGE = base_percentage
        self.crowd_wisdom_config.MAX_BET = max_bet
        self.crowd_wisdom_config.MIN_BET = min_bet
        
        return self.base_strategy.should_bet(outcomes, balance, title)

    def _follow_crowd_strategy(
        self, 
        outcomes: list, 
        balance: int, 
        base_percentage: float, 
        max_bet: int, 
        min_bet: int
    ) -> Optional[Dict[str, Any]]:
        """Suit simplement la majorité."""
        if len(outcomes) < 2:
            return None

        # Trouve la majorité
        pct1 = outcomes[0].get(OutcomeKeys.PERCENTAGE_USERS, 0)
        pct2 = outcomes[1].get(OutcomeKeys.PERCENTAGE_USERS, 0)
        
        majority_choice = 0 if pct1 > pct2 else 1
        majority_pct = max(pct1, pct2)

        if majority_pct < 55:
            return None  # Pas de majorité claire

        # Calcule le montant
        amount = min(int(balance * (base_percentage / 100)), max_bet)
        amount = max(amount, min_bet)

        return {
            'choice': majority_choice,
            'id': outcomes[majority_choice].get('id'),
            'amount': amount,
            'confidence': min(majority_pct / 100, 0.85),
            'reason': f"Follow crowd ({majority_pct:.0f}%)",
            'signal_type': 'follow_crowd',
            'conviction': 'medium'
        }

    def _contrarian_strategy(
        self, 
        outcomes: list, 
        balance: int, 
        base_percentage: float, 
        max_bet: int, 
        min_bet: int
    ) -> Optional[Dict[str, Any]]:
        """Parie contre la foule."""
        if len(outcomes) < 2:
            return None

        pct1 = outcomes[0].get(OutcomeKeys.PERCENTAGE_USERS, 0)
        pct2 = outcomes[1].get(OutcomeKeys.PERCENTAGE_USERS, 0)

        # Trouve la minorité
        minority_choice = 1 if pct1 > pct2 else 0
        minority_pct = min(pct1, pct2)

        # Vérifie que la minorité n'est pas trop faible (< 20%) ou trop forte (> 45%)
        if minority_pct < 20 or minority_pct > 45:
            return None

        # Montant réduit car plus risqué
        amount = min(int(balance * (base_percentage * 0.8 / 100)), max_bet)
        amount = max(amount, min_bet)

        return {
            'choice': minority_choice,
            'id': outcomes[minority_choice].get('id'),
            'amount': amount,
            'confidence': 0.65,
            'reason': f"Contrarian (minority {minority_pct:.0f}%)",
            'signal_type': 'contrarian',
            'conviction': 'low'
        }

    def _sharp_only_strategy(
        self, 
        outcomes: list, 
        balance: int, 
        base_percentage: float, 
        max_bet: int, 
        min_bet: int
    ) -> Optional[Dict[str, Any]]:
        """N'utilise que les sharp signals."""
        # Analyse les patterns
        pattern = self.pattern_analyzer.analyze_betting_pattern(outcomes)

        if pattern.get('sharp_signal', {}).get('detected'):
            sharp_choice = pattern['sharp_signal'].get('sharp_choice', 0)
            
            # Montant basé sur la confiance du sharp signal
            amount = min(int(balance * (base_percentage * 1.2 / 100)), max_bet)
            amount = max(amount, min_bet)

            return {
                'choice': sharp_choice - 1,  # Convertit de 1/2 à 0/1
                'id': outcomes[sharp_choice - 1].get('id'),
                'amount': amount,
                'confidence': 0.75,
                'reason': pattern['sharp_signal'].get('reason', 'Sharp signal detected'),
                'signal_type': 'sharp_signal',
                'conviction': 'high'
            }

        return None  # Skip si pas de sharp signal

