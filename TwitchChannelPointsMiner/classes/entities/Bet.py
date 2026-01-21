import copy
import logging
from enum import Enum, auto
from random import uniform

from millify import millify

#from TwitchChannelPointsMiner.utils import char_decision_as_index, float_round
from TwitchChannelPointsMiner.utils import float_round

logger = logging.getLogger(__name__)


class Strategy(Enum):
    MOST_VOTED = auto()
    HIGH_ODDS = auto()
    PERCENTAGE = auto()
    SMART_MONEY = auto()
    SMART = auto()
    CROWD_WISDOM = auto()  # Nouvelle stratégie basée sur l'intelligence collective
    FOLLOW_MAJORITY = auto()  # Suit la majorité simple (>51%)
    NUMBER_1 = auto()
    NUMBER_2 = auto()
    NUMBER_3 = auto()
    NUMBER_4 = auto()
    NUMBER_5 = auto()
    NUMBER_6 = auto()
    NUMBER_7 = auto()
    NUMBER_8 = auto()

    def __str__(self):
        return self.name


class Condition(Enum):
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()

    def __str__(self):
        return self.name


class OutcomeKeys(object):
    # Real key on Bet dict ['']
    PERCENTAGE_USERS = "percentage_users"
    ODDS_PERCENTAGE = "odds_percentage"
    ODDS = "odds"
    TOP_POINTS = "top_points"
    # Real key on Bet dict [''] - Sum()
    TOTAL_USERS = "total_users"
    TOTAL_POINTS = "total_points"
    # This key does not exist
    DECISION_USERS = "decision_users"
    DECISION_POINTS = "decision_points"


class DelayMode(Enum):
    FROM_START = auto()
    FROM_END = auto()
    PERCENTAGE = auto()

    def __str__(self):
        return self.name


class FilterCondition(object):
    __slots__ = [
        "by",
        "where",
        "value",
    ]

    def __init__(self, by=None, where=None, value=None, decision=None):
        self.by = by
        self.where = where
        self.value = value

    def __repr__(self):
        return f"FilterCondition(by={self.by.upper()}, where={self.where}, value={self.value})"


class BetSettings(object):
    __slots__ = [
        "strategy",
        "percentage",
        "percentage_gap",
        "max_points",
        "minimum_points",
        "stealth_mode",
        "filter_condition",
        "delay",
        "delay_mode",
        "min_voters",  # Nombre minimum de votants pour parier
        "skip_if_divided",  # Skip si 45-55% (trop incertain)
    ]

    def __init__(
        self,
        strategy: Strategy = None,
        percentage: int = None,
        percentage_gap: int = None,
        max_points: int = None,
        minimum_points: int = None,
        stealth_mode: bool = None,
        filter_condition: FilterCondition = None,
        delay: float = None,
        delay_mode: DelayMode = None,
        min_voters: int = None,
        skip_if_divided: bool = None,
    ):
        self.strategy = strategy
        self.percentage = percentage
        self.percentage_gap = percentage_gap
        self.max_points = max_points
        self.minimum_points = minimum_points
        self.stealth_mode = stealth_mode
        self.filter_condition = filter_condition
        self.delay = delay
        self.delay_mode = delay_mode
        self.min_voters = min_voters
        self.skip_if_divided = skip_if_divided

    def default(self):
        self.strategy = self.strategy if self.strategy is not None else Strategy.CROWD_WISDOM
        self.percentage = self.percentage if self.percentage is not None else 5
        self.percentage_gap = (
            self.percentage_gap if self.percentage_gap is not None else 20
        )
        self.max_points = self.max_points if self.max_points is not None else 50000
        self.minimum_points = (
            self.minimum_points if self.minimum_points is not None else 0
        )
        self.stealth_mode = (
            self.stealth_mode if self.stealth_mode is not None else False
        )
        self.delay = self.delay if self.delay is not None else 8  # Augmenté pour plus de données
        self.delay_mode = (
            self.delay_mode if self.delay_mode is not None else DelayMode.FROM_END
        )
        self.min_voters = self.min_voters if self.min_voters is not None else 50  # Min 50 votants
        self.skip_if_divided = self.skip_if_divided if self.skip_if_divided is not None else False

    def __repr__(self):
        return f"BetSettings(strategy={self.strategy}, percentage={self.percentage}, percentage_gap={self.percentage_gap}, max_points={self.max_points}, minimum_points={self.minimum_points}, stealth_mode={self.stealth_mode}, min_voters={self.min_voters})"


class Bet(object):
    __slots__ = ["outcomes", "decision", "total_users", "total_points", "settings", "_event_title", "_streamer_id", "_streamer_name"]

    def __init__(self, outcomes: list, settings: BetSettings):
        self.outcomes = outcomes
        self.__clear_outcomes()
        self.decision: dict = {}
        self.total_users = 0
        self.total_points = 0
        self.settings = settings
        self._event_title = ""  # Titre de l'événement pour logging (utilisé par CROWD_WISDOM)
        self._streamer_id = ""  # ID du streamer pour stratégie ADAPTIVE
        self._streamer_name = ""  # Nom du streamer pour stratégie ADAPTIVE

    def update_outcomes(self, outcomes):
        for index in range(0, len(self.outcomes)):
            self.outcomes[index][OutcomeKeys.TOTAL_USERS] = int(
                outcomes[index][OutcomeKeys.TOTAL_USERS]
            )
            self.outcomes[index][OutcomeKeys.TOTAL_POINTS] = int(
                outcomes[index][OutcomeKeys.TOTAL_POINTS]
            )
            if outcomes[index]["top_predictors"] != []:
                # Sort by points placed by other users
                outcomes[index]["top_predictors"] = sorted(
                    outcomes[index]["top_predictors"],
                    key=lambda x: x["points"],
                    reverse=True,
                )
                # Get the first elements (most placed)
                top_points = outcomes[index]["top_predictors"][0]["points"]
                self.outcomes[index][OutcomeKeys.TOP_POINTS] = top_points

        # Inefficient, but otherwise outcomekeys are represented wrong
        self.total_points = 0
        self.total_users = 0
        for index in range(0, len(self.outcomes)):
            self.total_users += self.outcomes[index][OutcomeKeys.TOTAL_USERS]
            self.total_points += self.outcomes[index][OutcomeKeys.TOTAL_POINTS]

        if (
            self.total_users > 0
            and self.total_points > 0
        ):
            for index in range(0, len(self.outcomes)):
                self.outcomes[index][OutcomeKeys.PERCENTAGE_USERS] = float_round(
                    (100 * self.outcomes[index][OutcomeKeys.TOTAL_USERS]) / self.total_users
                )
                self.outcomes[index][OutcomeKeys.ODDS] = float_round(
                    #self.total_points / max(self.outcomes[index][OutcomeKeys.TOTAL_POINTS], 1)
                    0
                    if self.outcomes[index][OutcomeKeys.TOTAL_POINTS] == 0
                    else self.total_points / self.outcomes[index][OutcomeKeys.TOTAL_POINTS]
                )
                self.outcomes[index][OutcomeKeys.ODDS_PERCENTAGE] = float_round(
                    #100 / max(self.outcomes[index][OutcomeKeys.ODDS], 1)
                    0
                    if self.outcomes[index][OutcomeKeys.ODDS] == 0
                    else 100 / self.outcomes[index][OutcomeKeys.ODDS]
                )

        self.__clear_outcomes()

    def __repr__(self):
        return f"Bet(total_users={millify(self.total_users)}, total_points={millify(self.total_points)}), decision={self.decision})\n\t\tOutcome A({self.get_outcome(0)})\n\t\tOutcome B({self.get_outcome(1)})"

    def get_decision(self, parsed=False):
        #decision = self.outcomes[0 if self.decision["choice"] == "A" else 1]
        decision = self.outcomes[self.decision["choice"]]
        return decision if parsed is False else Bet.__parse_outcome(decision)

    @staticmethod
    def __parse_outcome(outcome):
        return f"{outcome['title']} ({outcome['color']}), Points: {millify(outcome[OutcomeKeys.TOTAL_POINTS])}, Users: {millify(outcome[OutcomeKeys.TOTAL_USERS])} ({outcome[OutcomeKeys.PERCENTAGE_USERS]}%), Odds: {outcome[OutcomeKeys.ODDS]} ({outcome[OutcomeKeys.ODDS_PERCENTAGE]}%)"

    def get_outcome(self, index):
        return Bet.__parse_outcome(self.outcomes[index])

    def __clear_outcomes(self):
        for index in range(0, len(self.outcomes)):
            keys = copy.deepcopy(list(self.outcomes[index].keys()))
            for key in keys:
                if key not in [
                    OutcomeKeys.TOTAL_USERS,
                    OutcomeKeys.TOTAL_POINTS,
                    OutcomeKeys.TOP_POINTS,
                    OutcomeKeys.PERCENTAGE_USERS,
                    OutcomeKeys.ODDS,
                    OutcomeKeys.ODDS_PERCENTAGE,
                    "title",
                    "color",
                    "id",
                ]:
                    del self.outcomes[index][key]
            for key in [
                OutcomeKeys.PERCENTAGE_USERS,
                OutcomeKeys.ODDS,
                OutcomeKeys.ODDS_PERCENTAGE,
                OutcomeKeys.TOP_POINTS,
            ]:
                if key not in self.outcomes[index]:
                    self.outcomes[index][key] = 0

    '''def __return_choice(self, key) -> str:
        return "A" if self.outcomes[0][key] > self.outcomes[1][key] else "B"'''

    def __return_choice(self, key) -> int:
        largest=0
        for index in range(0, len(self.outcomes)):
            if self.outcomes[index][key] > self.outcomes[largest][key]:
                largest = index
        return largest

    def __return_number_choice(self, number) -> int:
        if (len(self.outcomes) > number):
            return number
        else:
            return 0

    def skip(self) -> bool:
        """
        Vérifie si le pari doit être ignoré selon les filtres configurés.
        
        Returns:
            (should_skip, compared_value) - Tuple avec booléen et valeur de comparaison
        """
        # === FILTRE 1: Nombre minimum de votants ===
        min_voters = getattr(self.settings, 'min_voters', 50)
        if min_voters and min_voters > 0:
            if self.total_users < min_voters:
                logger.info(f"❌ Skip: Pas assez de votants ({self.total_users} < {min_voters})")
                return True, self.total_users
        
        # === FILTRE 2: Skip si trop divisé (45-55%) ===
        skip_divided = getattr(self.settings, 'skip_if_divided', False)
        if skip_divided and len(self.outcomes) >= 2:
            pct1 = self.outcomes[0].get(OutcomeKeys.PERCENTAGE_USERS, 0)
            pct2 = self.outcomes[1].get(OutcomeKeys.PERCENTAGE_USERS, 0)
            max_pct = max(pct1, pct2)
            if 45 <= max_pct <= 55:
                logger.info(f"❌ Skip: Vote trop divisé ({max_pct:.0f}%) - trop incertain")
                return True, max_pct
        
        # === FILTRE 3: Filtre condition personnalisé ===
        if self.settings.filter_condition is not None:
            # key == by , condition == where
            key = self.settings.filter_condition.by
            condition = self.settings.filter_condition.where
            value = self.settings.filter_condition.value

            fixed_key = (
                key
                if key not in [OutcomeKeys.DECISION_USERS, OutcomeKeys.DECISION_POINTS]
                else key.replace("decision", "total")
            )
            if key in [OutcomeKeys.TOTAL_USERS, OutcomeKeys.TOTAL_POINTS]:
                compared_value = (
                    self.outcomes[0][fixed_key] + self.outcomes[1][fixed_key]
                )
            else:
                #outcome_index = char_decision_as_index(self.decision["choice"])
                outcome_index = self.decision["choice"]
                compared_value = self.outcomes[outcome_index][fixed_key]

            # Check if condition is satisfied
            if condition == Condition.GT:
                if compared_value > value:
                    return False, compared_value
            elif condition == Condition.LT:
                if compared_value < value:
                    return False, compared_value
            elif condition == Condition.GTE:
                if compared_value >= value:
                    return False, compared_value
            elif condition == Condition.LTE:
                if compared_value <= value:
                    return False, compared_value
            return True, compared_value  # Else skip the bet
        else:
            return False, 0  # Default don't skip the bet

    def _analyze_sharp_signal(self) -> dict:
        """
        Détecte les 'sharp bettors' (parieurs informés).
        Signal fort: Option minoritaire (<40%) avec gros bets moyens (1.5x+)
        """
        if len(self.outcomes) < 2:
            return {"detected": False}
        
        pct1 = self.outcomes[0].get(OutcomeKeys.PERCENTAGE_USERS, 0)
        pct2 = self.outcomes[1].get(OutcomeKeys.PERCENTAGE_USERS, 0)
        
        users1 = self.outcomes[0].get(OutcomeKeys.TOTAL_USERS, 0)
        users2 = self.outcomes[1].get(OutcomeKeys.TOTAL_USERS, 0)
        points1 = self.outcomes[0].get(OutcomeKeys.TOTAL_POINTS, 0)
        points2 = self.outcomes[1].get(OutcomeKeys.TOTAL_POINTS, 0)
        
        if users1 == 0 or users2 == 0:
            return {"detected": False}
        
        avg_bet_1 = points1 / users1
        avg_bet_2 = points2 / users2
        
        # Option 1 minoritaire mais gros bets moyens
        if pct1 < 40 and avg_bet_1 > avg_bet_2 * 1.5:
            return {
                "detected": True,
                "choice": 0,
                "strength": "strong" if avg_bet_1 > avg_bet_2 * 2 else "medium",
                "reason": f"Option 1 minoritaire ({pct1:.0f}%) mais bet moyen {avg_bet_1/avg_bet_2:.1f}x plus élevé"
            }
        
        # Option 2 minoritaire mais gros bets moyens
        if pct2 < 40 and avg_bet_2 > avg_bet_1 * 1.5:
            return {
                "detected": True,
                "choice": 1,
                "strength": "strong" if avg_bet_2 > avg_bet_1 * 2 else "medium",
                "reason": f"Option 2 minoritaire ({pct2:.0f}%) mais bet moyen {avg_bet_2/avg_bet_1:.1f}x plus élevé"
            }
        
        return {"detected": False}
    
    def _analyze_money_flow(self) -> dict:
        """
        Analyse où va l'argent (gros parieurs vs petits).
        TOP_POINTS élevé sur une option = gros parieurs informés
        """
        if len(self.outcomes) < 2:
            return {}
        
        users1 = self.outcomes[0].get(OutcomeKeys.TOTAL_USERS, 0)
        users2 = self.outcomes[1].get(OutcomeKeys.TOTAL_USERS, 0)
        points1 = self.outcomes[0].get(OutcomeKeys.TOTAL_POINTS, 0)
        points2 = self.outcomes[1].get(OutcomeKeys.TOTAL_POINTS, 0)
        top1 = self.outcomes[0].get(OutcomeKeys.TOP_POINTS, 0)
        top2 = self.outcomes[1].get(OutcomeKeys.TOP_POINTS, 0)
        
        avg_bet_1 = points1 / users1 if users1 > 0 else 0
        avg_bet_2 = points2 / users2 if users2 > 0 else 0
        
        return {
            "avg_bet_1": int(avg_bet_1),
            "avg_bet_2": int(avg_bet_2),
            "top_bet_1": top1,
            "top_bet_2": top2,
            "big_money_on": 0 if avg_bet_1 > avg_bet_2 else 1,
            "avg_ratio": avg_bet_1 / avg_bet_2 if avg_bet_2 > 0 else 999
        }
    
    def _detect_consensus(self) -> dict:
        """
        Identifie le type de consensus.
        - strong_consensus: >70% sur une option
        - weak_consensus: 55-70%
        - divided: 45-55%
        """
        if len(self.outcomes) < 2:
            return {"type": "unknown", "confidence": 0.5}
        
        pct1 = self.outcomes[0].get(OutcomeKeys.PERCENTAGE_USERS, 0)
        pct2 = self.outcomes[1].get(OutcomeKeys.PERCENTAGE_USERS, 0)
        max_pct = max(pct1, pct2)
        majority_choice = 0 if pct1 > pct2 else 1
        
        if max_pct > 70:
            return {
                "type": "strong_consensus",
                "choice": majority_choice,
                "confidence": min(max_pct / 100, 0.9),
                "percentage": max_pct
            }
        elif max_pct > 55:
            return {
                "type": "weak_consensus",
                "choice": majority_choice,
                "confidence": 0.65,
                "percentage": max_pct
            }
        else:
            return {
                "type": "divided",
                "choice": majority_choice,
                "confidence": 0.5,
                "percentage": max_pct
            }
    
    def _crowd_wisdom_decision(self, balance: int) -> dict:
        """
        Stratégie CROWD_WISDOM - Intelligence collective avancée
        
        Priorité des signaux :
        1. Sharp Signal (minorité + gros bets) → Haute confiance
        2. Strong Consensus + Gros bets alignés → Moyenne-haute confiance
        3. Money Flow divergent → Suit l'argent
        4. Weak Consensus → Suit majorité avec prudence
        5. Divided → Skip ou bet minimal
        """
        decision = {"choice": None, "amount": 0, "id": None, "reason": ""}
        
        # Analyse des signaux
        sharp = self._analyze_sharp_signal()
        consensus = self._detect_consensus()
        money_flow = self._analyze_money_flow()
        
        # Multiplicateur de confiance (affecte le montant)
        confidence_mult = 1.0
        
        # === SIGNAL 1: Sharp Bettors détectés ===
        if sharp.get("detected"):
            decision["choice"] = sharp["choice"]
            confidence_mult = 1.5 if sharp["strength"] == "strong" else 1.2
            decision["reason"] = f"🎯 SHARP: {sharp['reason']}"
            logger.info(f"CROWD_WISDOM: Sharp signal détecté - {sharp['reason']}")
        
        # === SIGNAL 2: Strong Consensus ===
        elif consensus["type"] == "strong_consensus":
            decision["choice"] = consensus["choice"]
            
            # Vérifie si le gros argent est aligné avec la majorité
            big_money_aligned = money_flow.get("big_money_on") == consensus["choice"]
            
            if big_money_aligned:
                confidence_mult = 1.3
                decision["reason"] = f"💪 CONSENSUS FORT ({consensus['percentage']:.0f}%) + Argent aligné"
            else:
                confidence_mult = 1.0
                decision["reason"] = f"👥 CONSENSUS FORT ({consensus['percentage']:.0f}%) mais argent divergent"
            
            logger.info(f"CROWD_WISDOM: Strong consensus {consensus['percentage']:.0f}% sur option {consensus['choice']}")
        
        # === SIGNAL 3: Money Flow divergent ===
        elif consensus["type"] == "weak_consensus" and money_flow:
            avg_ratio = money_flow.get("avg_ratio", 1.0)
            
            # Si le ratio d'argent est significativement différent (>1.3 ou <0.77)
            if avg_ratio > 1.3 or avg_ratio < 0.77:
                # L'argent et les votes divergent → Suit l'argent
                decision["choice"] = money_flow["big_money_on"]
                confidence_mult = 1.1
                decision["reason"] = f"💰 MONEY FLOW: Argent diverge de la foule (ratio {avg_ratio:.2f})"
                logger.info(f"CROWD_WISDOM: Money flow divergent, suit l'argent sur option {decision['choice']}")
            else:
                # Argent et votes alignés → Suit la majorité
                decision["choice"] = consensus["choice"]
                confidence_mult = 1.0
                decision["reason"] = f"👥 CONSENSUS ({consensus['percentage']:.0f}%) + argent aligné"
        
        # === SIGNAL 4: Divided (50/50) ===
        elif consensus["type"] == "divided":
            # Dans un 50/50, on cherche des indices subtils
            if money_flow:
                # Suit l'argent dans un 50/50
                avg_ratio = money_flow.get("avg_ratio", 1.0)
                if avg_ratio > 1.2:
                    decision["choice"] = 0
                    confidence_mult = 0.7  # Réduit car incertain
                    decision["reason"] = "🤔 50/50 - Suit l'argent (option 1)"
                elif avg_ratio < 0.83:
                    decision["choice"] = 1
                    confidence_mult = 0.7
                    decision["reason"] = "🤔 50/50 - Suit l'argent (option 2)"
                else:
                    # Vraiment 50/50, suit la majorité par défaut
                    decision["choice"] = consensus["choice"]
                    confidence_mult = 0.5  # Très réduit
                    decision["reason"] = "❓ 50/50 pur - Suit majorité par défaut"
        
        # === Fallback ===
        else:
            decision["choice"] = self.__return_choice(OutcomeKeys.TOTAL_USERS)
            confidence_mult = 0.8
            decision["reason"] = "📊 MOST_VOTED fallback"
        
        # Calcul du montant avec confiance
        if decision["choice"] is not None:
            index = decision["choice"]
            decision["id"] = self.outcomes[index]["id"]
            
            base_amount = int(balance * (self.settings.percentage / 100))
            decision["amount"] = min(
                int(base_amount * confidence_mult),
                self.settings.max_points
            )
            
            # Stealth mode
            if (
                self.settings.stealth_mode is True
                and decision["amount"] >= self.outcomes[index].get(OutcomeKeys.TOP_POINTS, 0)
            ):
                reduce_amount = uniform(1, 5)
                decision["amount"] = max(
                    10,
                    int(self.outcomes[index].get(OutcomeKeys.TOP_POINTS, decision["amount"]) - reduce_amount)
                )
            
            decision["amount"] = max(10, int(decision["amount"]))
        
        return decision

    def calculate(self, balance: int) -> dict:
        self.decision = {"choice": None, "amount": 0, "id": None}
        if self.settings.strategy == Strategy.MOST_VOTED:
            self.decision["choice"] = self.__return_choice(OutcomeKeys.TOTAL_USERS)
        elif self.settings.strategy == Strategy.HIGH_ODDS:
            self.decision["choice"] = self.__return_choice(OutcomeKeys.ODDS)
        elif self.settings.strategy == Strategy.PERCENTAGE:
            self.decision["choice"] = self.__return_choice(OutcomeKeys.ODDS_PERCENTAGE)
        elif self.settings.strategy == Strategy.SMART_MONEY:
            self.decision["choice"] = self.__return_choice(OutcomeKeys.TOP_POINTS)
        elif self.settings.strategy == Strategy.NUMBER_1:
            self.decision["choice"] = self.__return_number_choice(0)
        elif self.settings.strategy == Strategy.NUMBER_2:
            self.decision["choice"] = self.__return_number_choice(1)
        elif self.settings.strategy == Strategy.NUMBER_3:
            self.decision["choice"] = self.__return_number_choice(2)
        elif self.settings.strategy == Strategy.NUMBER_4:
            self.decision["choice"] = self.__return_number_choice(3)
        elif self.settings.strategy == Strategy.NUMBER_5:
            self.decision["choice"] = self.__return_number_choice(4)
        elif self.settings.strategy == Strategy.NUMBER_6:
            self.decision["choice"] = self.__return_number_choice(5)
        elif self.settings.strategy == Strategy.NUMBER_7:
            self.decision["choice"] = self.__return_number_choice(6)
        elif self.settings.strategy == Strategy.NUMBER_8:
            self.decision["choice"] = self.__return_number_choice(7)
        elif self.settings.strategy == Strategy.SMART:
            difference = abs(
                self.outcomes[0][OutcomeKeys.PERCENTAGE_USERS]
                - self.outcomes[1][OutcomeKeys.PERCENTAGE_USERS]
            )
            self.decision["choice"] = (
                self.__return_choice(OutcomeKeys.ODDS)
                if difference < self.settings.percentage_gap
                else self.__return_choice(OutcomeKeys.TOTAL_USERS)
            )
        
        elif self.settings.strategy == Strategy.CROWD_WISDOM:
            # Stratégie basée sur l'intelligence collective des parieurs
            self.decision = self._crowd_wisdom_decision(balance)
        
        elif self.settings.strategy == Strategy.FOLLOW_MAJORITY:
            # Suit simplement la majorité (>51%)
            pct1 = self.outcomes[0].get(OutcomeKeys.PERCENTAGE_USERS, 0)
            pct2 = self.outcomes[1].get(OutcomeKeys.PERCENTAGE_USERS, 0)
            if pct1 > 51:
                self.decision["choice"] = 0
            elif pct2 > 51:
                self.decision["choice"] = 1
            else:
                # Pas de majorité claire, utiliser MOST_VOTED
                self.decision["choice"] = self.__return_choice(OutcomeKeys.TOTAL_USERS)

        if self.decision["choice"] is not None:
            #index = char_decision_as_index(self.decision["choice"])
            index = self.decision["choice"]
            self.decision["id"] = self.outcomes[index]["id"]
            self.decision["amount"] = min(
                int(balance * (self.settings.percentage / 100)),
                self.settings.max_points,
            )
            if (
                self.settings.stealth_mode is True
                and self.decision["amount"]
                >= self.outcomes[index][OutcomeKeys.TOP_POINTS]
            ):
                reduce_amount = uniform(1, 5)
                self.decision["amount"] = (
                    self.outcomes[index][OutcomeKeys.TOP_POINTS] - reduce_amount
                )
            self.decision["amount"] = int(self.decision["amount"])
        return self.decision
