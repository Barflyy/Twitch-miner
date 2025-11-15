"""
Stratégie de betting basée sur l'intelligence collective des viewers.
Analyse les patterns de paris pour détecter les signaux des parieurs informés.
"""

import logging
from typing import Optional, Dict, List
from TwitchChannelPointsMiner.classes.entities.Bet import OutcomeKeys

logger = logging.getLogger(__name__)


class CrowdWisdomConfig:
    """Configuration de la stratégie basée sur la foule."""

    # Seuils pour consensus
    STRONG_CONSENSUS_THRESHOLD = 75  # % minimum
    WEAK_CONSENSUS_THRESHOLD = 60

    # Seuils pour conviction
    HIGH_CONVICTION_AVG_BET = 5000   # Points
    MEDIUM_CONVICTION_AVG_BET = 2000

    # Seuils pour sharp detection
    SHARP_AVG_BET_RATIO = 1.5        # Minorité doit miser 50% plus
    SHARP_MINORITY_MAX = 40          # % max pour être "minorité"

    # Seuils pour money flow divergence
    SIGNIFICANT_RATIO_DIFF = 1.3     # 30% de différence minimum

    # === SYSTÈME DE MISE À 3 NIVEAUX ===
    CONSERVATIVE = 0.02              # 2% - Signaux faibles
    STANDARD = 0.05                  # 5% - Signaux standards
    AGGRESSIVE = 0.10                # 10% - Signaux forts
    
    # Montants
    BASE_PERCENTAGE = 5.0            # % de base de la bankroll (legacy, utilise les niveaux ci-dessus)
    MIN_BET = 50
    MAX_BET = 50000
    MAX_SINGLE_BET_PCT = 0.15        # Max 15% sur un bet
    MAX_PER_STREAM_PCT = 0.30        # Max 30% sur un streamer
    MAX_ACTIVE_BETS_PCT = 0.50       # Max 50% en bets actifs

    # Multiplicateurs de confiance
    CONFIDENCE_MULTIPLIERS = {
        0.85: 1.5,   # Très confiant → +50%
        0.75: 1.3,   # Confiant → +30%
        0.65: 1.0,   # Standard
        0.55: 0.8,   # Peu confiant → -20%
        0.45: 0.6    # Très incertain → -40%
    }
    
    # Multiplicateurs de conviction
    CONVICTION_MULTIPLIERS = {
        'high': 1.2,
        'medium': 1.0,
        'low': 0.7
    }
    
    # Ajustements dynamiques selon bankroll
    BANKROLL_ADJUSTMENTS = {
        1.5: 1.2,    # +50% → +20% mise
        1.2: 1.0,    # +20% → standard
        0.8: 1.0,    # -20% → standard
        0.5: 0.7,    # -50% → -30% mise
        0.0: 0.5     # -100%+ → -50% mise (survie)
    }

    # Filtres
    MIN_TOTAL_USERS = 150            # Skip si < 150 participants
    MIN_BET_SAMPLE = 10              # Skip si < 10 bets par option


class BetPatternAnalyzer:
    """Analyse les patterns de paris pour détecter l'information cachée."""

    def __init__(self, config: CrowdWisdomConfig = None):
        self.config = config or CrowdWisdomConfig()

    def analyze_betting_pattern(self, outcomes: List[Dict]) -> Dict:
        """
        Extrait les signaux des comportements de paris.

        Args:
            outcomes: Liste des outcomes avec leurs statistiques

        Returns:
            dict avec les insights détectés
        """
        if len(outcomes) < 2:
            return {}

        option_1 = outcomes[0]
        option_2 = outcomes[1]

        analysis = {
            "consensus_type": self._detect_consensus_type(option_1, option_2),
            "money_flow": self._detect_money_flow(option_1, option_2),
            "conviction_level": self._detect_conviction(option_1, option_2),
            "sharp_signal": self._detect_sharp_bettors(option_1, option_2)
        }

        return analysis

    def _detect_consensus_type(self, opt1: Dict, opt2: Dict) -> str:
        """
        Identifie le type de consensus.

        Types:
        - strong_consensus: >75% sur une option → viewers sont sûrs
        - weak_consensus: 60-75% → légère préférence
        - divided: 40-60% → incertitude totale
        """
        pct1 = opt1.get(OutcomeKeys.PERCENTAGE_USERS, 0)
        pct2 = opt2.get(OutcomeKeys.PERCENTAGE_USERS, 0)

        max_pct = max(pct1, pct2)

        if max_pct > self.config.STRONG_CONSENSUS_THRESHOLD:
            return "strong_consensus"
        elif max_pct > self.config.WEAK_CONSENSUS_THRESHOLD:
            return "weak_consensus"
        else:
            return "divided"

    def _detect_money_flow(self, opt1: Dict, opt2: Dict) -> Dict:
        """
        Analyse où va l'argent (gros parieurs vs petits).

        INSIGHT CLÉ: Si TOP_POINTS est élevé sur une option minoritaire,
        ça signifie que des gros parieurs (probablement + informés)
        parient contre la foule.
        """
        # Calcul du bet moyen par option
        total_users_1 = opt1.get(OutcomeKeys.TOTAL_USERS, 0)
        total_users_2 = opt2.get(OutcomeKeys.TOTAL_USERS, 0)
        total_points_1 = opt1.get(OutcomeKeys.TOTAL_POINTS, 0)
        total_points_2 = opt2.get(OutcomeKeys.TOTAL_POINTS, 0)

        avg_bet_1 = total_points_1 / total_users_1 if total_users_1 > 0 else 0
        avg_bet_2 = total_points_2 / total_users_2 if total_users_2 > 0 else 0

        # Ratio du plus gros bet
        top_points_1 = opt1.get(OutcomeKeys.TOP_POINTS, 0)
        top_points_2 = opt2.get(OutcomeKeys.TOP_POINTS, 0)
        top_ratio = top_points_1 / top_points_2 if top_points_2 > 0 else 999

        # Ratio des bets moyens
        avg_ratio = avg_bet_1 / avg_bet_2 if avg_bet_2 > 0 else 999

        return {
            "avg_bet_option_1": int(avg_bet_1),
            "avg_bet_option_2": int(avg_bet_2),
            "avg_ratio": round(avg_ratio, 2),
            "top_bet_option_1": top_points_1,
            "top_bet_option_2": top_points_2,
            "top_ratio": round(top_ratio, 2),
            "big_money_on": 1 if avg_bet_1 > avg_bet_2 else 2
        }

    def _detect_conviction(self, opt1: Dict, opt2: Dict) -> Dict:
        """
        Mesure la conviction des parieurs.

        Haute conviction = gros bets moyens + gros TOP_POINTS
        Basse conviction = petits bets moyens même avec beaucoup d'users
        """
        money_flow = self._detect_money_flow(opt1, opt2)

        # Si bet moyen > 5000 points → haute conviction
        # Si bet moyen < 1000 points → basse conviction
        avg_1 = money_flow["avg_bet_option_1"]
        avg_2 = money_flow["avg_bet_option_2"]

        conviction_1 = "high" if avg_1 > self.config.HIGH_CONVICTION_AVG_BET else \
                       "medium" if avg_1 > self.config.MEDIUM_CONVICTION_AVG_BET else "low"

        conviction_2 = "high" if avg_2 > self.config.HIGH_CONVICTION_AVG_BET else \
                       "medium" if avg_2 > self.config.MEDIUM_CONVICTION_AVG_BET else "low"

        return {
            "option_1_conviction": conviction_1,
            "option_2_conviction": conviction_2,
            "overall": "high" if "high" in [conviction_1, conviction_2] else "medium"
        }

    def _detect_sharp_bettors(self, opt1: Dict, opt2: Dict) -> Dict:
        """
        Détecte si des "sharp bettors" (parieurs informés) sont présents.

        Signal fort: Option minoritaire avec gros bets moyens
        → Des gens qui connaissent parient contre la foule
        """
        pct1 = opt1.get(OutcomeKeys.PERCENTAGE_USERS, 0)
        pct2 = opt2.get(OutcomeKeys.PERCENTAGE_USERS, 0)

        money_flow = self._detect_money_flow(opt1, opt2)

        # Scénario 1: Option 1 minoritaire mais gros avg bet
        if pct1 < self.config.SHARP_MINORITY_MAX and \
           money_flow["avg_bet_option_1"] > money_flow["avg_bet_option_2"] * self.config.SHARP_AVG_BET_RATIO:
            return {
                "detected": True,
                "sharp_choice": 1,
                "signal_strength": "strong",
                "reason": f"Option 1 minoritaire ({pct1:.0f}%) mais bet moyen {money_flow['avg_ratio']:.1f}x plus élevé"
            }

        # Scénario 2: Option 2 minoritaire mais gros avg bet
        if pct2 < self.config.SHARP_MINORITY_MAX and \
           money_flow["avg_bet_option_2"] > money_flow["avg_bet_option_1"] * self.config.SHARP_AVG_BET_RATIO:
            return {
                "detected": True,
                "sharp_choice": 2,
                "signal_strength": "strong",
                "reason": f"Option 2 minoritaire ({pct2:.0f}%) mais bet moyen {1/money_flow['avg_ratio']:.1f}x plus élevé"
            }

        return {"detected": False}


class CrowdWisdomStrategy:
    """Suit l'intelligence collective des viewers."""

    def __init__(self, config: CrowdWisdomConfig = None):
        self.config = config or CrowdWisdomConfig()
        self.analyzer = BetPatternAnalyzer(config)

    def make_decision(self, outcomes: List[Dict], title: str = "") -> Optional[Dict]:
        """
        Décide du bet en analysant le comportement de la foule.

        Args:
            outcomes: Liste des outcomes avec leurs statistiques
            title: Titre de la prédiction (pour logging)

        Returns:
            dict avec choice (0 ou 1), confidence, reason, amount_multiplier
            ou None si skip
        """
        if len(outcomes) < 2:
            return None

        # Analyse complète des patterns
        pattern = self.analyzer.analyze_betting_pattern(outcomes)

        logger.info(f"\n=== ANALYSE: {title} ===")
        logger.info(f"Consensus: {pattern['consensus_type']}")
        logger.info(f"Money flow: {pattern['money_flow']}")
        logger.info(f"Conviction: {pattern['conviction_level']}")
        logger.info(f"Sharp signal: {pattern['sharp_signal']}")

        # === STRATÉGIE 1: Sharp bettors détectés ===
        if pattern["sharp_signal"].get("detected"):
            sharp_choice = pattern["sharp_signal"]["sharp_choice"]
            return {
                "choice": sharp_choice - 1,  # Index 0 ou 1
                "confidence": 0.85,
                "reason": f"🎯 SHARP SIGNAL: {pattern['sharp_signal'].get('reason', '')}",
                "amount_multiplier": 1.8  # On mise gros
            }

        # === STRATÉGIE 2: Strong consensus avec haute conviction ===
        if pattern["consensus_type"] == "strong_consensus":
            # Quelle option a le consensus ?
            pct1 = outcomes[0].get(OutcomeKeys.PERCENTAGE_USERS, 0)
            pct2 = outcomes[1].get(OutcomeKeys.PERCENTAGE_USERS, 0)
            consensus_choice = 0 if pct1 > pct2 else 1
            consensus_pct = max(pct1, pct2)

            # Vérifie la conviction
            conviction = pattern["conviction_level"]

            if conviction["overall"] == "high":
                return {
                    "choice": consensus_choice,
                    "confidence": min(consensus_pct / 100, 0.9),  # Max 90%
                    "reason": f"💪 STRONG CONSENSUS ({consensus_pct:.0f}%) + haute conviction",
                    "signal_type": "strong_consensus",
                    "conviction": "high",
                    "amount_multiplier": 1.5  # Legacy
                }
            elif conviction["overall"] == "medium":
                return {
                    "choice": consensus_choice,
                    "confidence": 0.65,
                    "reason": f"👥 Consensus ({consensus_pct:.0f}%) mais conviction moyenne",
                    "signal_type": "strong_consensus",
                    "conviction": "medium",
                    "amount_multiplier": 1.0  # Legacy
                }
            else:
                # Consensus mais faible conviction = suspect
                logger.info("⚠️ Consensus suspect (faible conviction) → SKIP")
                return None

        # === STRATÉGIE 3: Weak consensus - analyse money flow ===
        if pattern["consensus_type"] == "weak_consensus":
            money_flow = pattern["money_flow"]

            # Si l'argent et les users vont dans le même sens → signal fort
            pct1 = outcomes[0].get(OutcomeKeys.PERCENTAGE_USERS, 0)
            majority_choice = 0 if pct1 > 50 else 1
            big_money_choice = money_flow["big_money_on"] - 1

            if majority_choice == big_money_choice:
                return {
                    "choice": majority_choice,
                    "confidence": 0.7,
                    "reason": f"💰 Consensus + big money alignés",
                    "signal_type": "weak_consensus",
                    "conviction": pattern["conviction_level"].get("overall", "medium"),
                    "amount_multiplier": 1.3  # Legacy
                }
            else:
                # Divergence users vs money → suit l'argent
                avg_ratio = money_flow["avg_ratio"]
                if avg_ratio > self.config.SIGNIFICANT_RATIO_DIFF or avg_ratio < (1 / self.config.SIGNIFICANT_RATIO_DIFF):
                    return {
                        "choice": big_money_choice,
                        "confidence": 0.65,
                        "reason": f"💵 Big money diverge de la foule (ratio {avg_ratio:.2f})",
                        "signal_type": "weak_consensus",
                        "conviction": pattern["conviction_level"].get("overall", "medium"),
                        "amount_multiplier": 1.2  # Legacy
                    }

        # === STRATÉGIE 4: Divided - cherche des indices subtils ===
        if pattern["consensus_type"] == "divided":
            conviction = pattern["conviction_level"]

            # Dans un 50/50, suit l'option avec plus de conviction
            if conviction["option_1_conviction"] == "high" and conviction["option_2_conviction"] != "high":
                return {
                    "choice": 0,
                    "confidence": 0.55,
                    "reason": "🤔 50/50 mais conviction sur option 1",
                    "signal_type": "divided",
                    "conviction": "high",
                    "amount_multiplier": 0.8  # Legacy
                }
            elif conviction["option_2_conviction"] == "high" and conviction["option_1_conviction"] != "high":
                return {
                    "choice": 1,
                    "confidence": 0.55,
                    "reason": "🤔 50/50 mais conviction sur option 2",
                    "signal_type": "divided",
                    "conviction": "high",
                    "amount_multiplier": 0.8  # Legacy
                }
            else:
                # Vraiment 50/50 sans signal → SKIP
                logger.info("❌ Aucun signal clair dans un 50/50 → SKIP")
                return None

        # Aucune stratégie applicable
        return None

    def calculate_amount_from_signal(self, balance: int, decision: Dict,
                                    base_percentage: float = 5.0,
                                    starting_balance: int = None) -> int:
        """
        Calcule le montant optimal selon le type de signal avec système à 3 niveaux.

        Args:
            balance: Solde actuel de channel points
            decision: Décision avec confidence, amount_multiplier, signal_type, conviction
            base_percentage: Pourcentage de base (legacy, non utilisé)
            starting_balance: Solde initial pour ajustement dynamique

        Returns:
            Montant à miser
        """
        signal_type = decision.get("signal_type", "divided")
        confidence = decision.get("confidence", 0.5)
        conviction = decision.get("conviction", "medium")
        
        # === NIVEAU 1: Sélection du % de base selon type de signal ===
        base_percentage = self._get_base_percentage(signal_type, conviction)
        
        # === NIVEAU 2: Ajustement selon confiance ===
        confidence_multiplier = self._get_confidence_multiplier(confidence)
        
        # === NIVEAU 3: Ajustement selon conviction ===
        conviction_multiplier = self._get_conviction_multiplier(conviction)
        
        # === NIVEAU 4: Ajustement dynamique selon bankroll ===
        bankroll_multiplier = 1.0
        if starting_balance and starting_balance > 0:
            bankroll_multiplier = self._get_bankroll_adjustment(balance, starting_balance)
        
        # Calcul final
        final_percentage = base_percentage * confidence_multiplier * conviction_multiplier * bankroll_multiplier
        
        # Limite de sécurité absolue
        final_percentage = min(final_percentage, self.config.MAX_SINGLE_BET_PCT)
        
        amount = int(balance * final_percentage)
        
        # Application des limites
        amount = max(self.config.MIN_BET, min(amount, self.config.MAX_BET))
        
        # Log détaillé
        logger.info(f"""
        💵 CALCUL MISE:
        ├─ Type signal: {signal_type}
        ├─ Base: {base_percentage*100:.1f}%
        ├─ × Confiance ({confidence:.0%}): {confidence_multiplier:.2f}
        ├─ × Conviction ({conviction}): {conviction_multiplier:.2f}
        ├─ × Bankroll: {bankroll_multiplier:.2f}
        ├─ = Final: {final_percentage*100:.1f}%
        └─ Montant: {amount:,} pts (bankroll: {balance:,})
        """)
        
        return amount
    
    def _get_base_percentage(self, signal_type: str, conviction: str) -> float:
        """
        Détermine le % de base selon le type de signal.
        
        Args:
            signal_type: 'sharp_signal', 'strong_consensus', 'weak_consensus', 'divided'
            conviction: 'high', 'medium', 'low'
        """
        if signal_type == 'sharp_signal':
            # Signal SHARP = meilleur signal possible
            return self.config.AGGRESSIVE  # 10%
        
        elif signal_type == 'strong_consensus':
            # Consensus fort avec conviction
            if conviction == 'high':
                return self.config.AGGRESSIVE  # 10%
            else:
                return self.config.STANDARD    # 5%
        
        elif signal_type == 'weak_consensus':
            # Consensus faible
            return self.config.STANDARD  # 5%
        
        elif signal_type == 'divided':
            # 50/50 avec signal subtil
            return self.config.CONSERVATIVE  # 2%
        
        else:
            return self.config.CONSERVATIVE  # 2% par défaut
    
    def _get_confidence_multiplier(self, confidence: float) -> float:
        """
        Ajuste selon la confiance (0.0 - 1.0).
        """
        # Trouve le multiplicateur le plus proche
        thresholds = sorted(self.config.CONFIDENCE_MULTIPLIERS.keys(), reverse=True)
        
        for threshold in thresholds:
            if confidence >= threshold:
                return self.config.CONFIDENCE_MULTIPLIERS[threshold]
        
        # Si confiance < 0.45, utiliser le plus bas
        return self.config.CONFIDENCE_MULTIPLIERS[0.45]
    
    def _get_conviction_multiplier(self, conviction: str) -> float:
        """
        Ajuste selon la conviction des autres parieurs.
        """
        return self.config.CONVICTION_MULTIPLIERS.get(conviction, 1.0)
    
    def _get_bankroll_adjustment(self, current_balance: int, starting_balance: int) -> float:
        """
        Ajuste le % selon l'état de la bankroll.
        
        Si on gagne beaucoup → on peut être plus agressif
        Si on perd → on devient conservateur
        """
        if starting_balance <= 0:
            return 1.0
        
        # Ratio actuel vs départ
        ratio = current_balance / starting_balance
        
        # Trouve le seuil le plus proche
        thresholds = sorted(self.config.BANKROLL_ADJUSTMENTS.keys(), reverse=True)
        
        for threshold in thresholds:
            if ratio >= threshold:
                return self.config.BANKROLL_ADJUSTMENTS[threshold]
        
        # Si ratio < 0.0 (impossible mais sécurité)
        return self.config.BANKROLL_ADJUSTMENTS[0.0]

    def should_bet(self, outcomes: List[Dict], balance: int, title: str = "") -> Optional[Dict]:
        """
        Point d'entrée principal pour décider si on bet et combien.

        Args:
            outcomes: Liste des outcomes avec leurs statistiques
            balance: Solde actuel
            title: Titre de la prédiction

        Returns:
            dict avec choice, amount, id, reason ou None si skip
        """
        if len(outcomes) < 2:
            return None

        # Filtre 1: Assez de participants ?
        total_users = sum(o.get(OutcomeKeys.TOTAL_USERS, 0) for o in outcomes)
        if total_users < self.config.MIN_TOTAL_USERS:
            logger.info(f"❌ Skip: seulement {total_users} users (min: {self.config.MIN_TOTAL_USERS})")
            return None

        # Filtre 2: Assez de bets par option ?
        for i, outcome in enumerate(outcomes):
            if outcome.get(OutcomeKeys.TOTAL_USERS, 0) < self.config.MIN_BET_SAMPLE:
                logger.info(f"❌ Skip: pas assez de bets sur option {i+1} ({outcome.get(OutcomeKeys.TOTAL_USERS, 0)} users)")
                return None

        # Analyse et décision
        decision = self.make_decision(outcomes, title)

        if decision is None:
            return None

        # Calcul du montant avec système à 3 niveaux
        # Note: starting_balance pourrait être passé depuis l'extérieur si disponible
        decision["amount"] = self.calculate_amount_from_signal(
            balance=balance,
            decision=decision,
            base_percentage=self.config.BASE_PERCENTAGE,
            starting_balance=None  # TODO: Passer depuis EventPrediction si disponible
        )

        # Ajouter l'ID de l'outcome choisi
        choice_index = decision["choice"]
        if choice_index < len(outcomes):
            decision["id"] = outcomes[choice_index].get("id")

        return decision

