import copy
from enum import Enum, auto
from random import uniform

from millify import millify

#from TwitchChannelPointsMiner.utils import char_decision_as_index, float_round
from TwitchChannelPointsMiner.utils import float_round


class Strategy(Enum):
    MOST_VOTED = auto()
    HIGH_ODDS = auto()
    PERCENTAGE = auto()
    SMART_MONEY = auto()
    SMART = auto()
    CROWD_WISDOM = auto()  # Nouvelle stratégie basée sur l'intelligence collective
    ADAPTIVE = auto()  # Stratégie adaptive basée sur le profil du streamer
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

    def default(self):
        self.strategy = self.strategy if self.strategy is not None else Strategy.SMART
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
        self.delay = self.delay if self.delay is not None else 6
        self.delay_mode = (
            self.delay_mode if self.delay_mode is not None else DelayMode.FROM_END
        )

    def __repr__(self):
        return f"BetSettings(strategy={self.strategy}, percentage={self.percentage}, percentage_gap={self.percentage_gap}, max_points={self.max_points}, minimum_points={self.minimum_points}, stealth_mode={self.stealth_mode})"


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

    def calculate(self, balance: int) -> dict:
        self.decision = {"choice": None, "amount": 0, "id": None}
        
        # Stratégie ADAPTIVE basée sur le profil du streamer
        if self.settings.strategy == Strategy.ADAPTIVE:
            try:
                from TwitchChannelPointsMiner.classes.entities.AdaptiveBetStrategy import (
                    AdaptiveBetStrategy
                )
                
                # Créer la stratégie adaptive
                adaptive_strategy = AdaptiveBetStrategy()
                
                # Récupérer les infos du streamer depuis l'event si disponible
                streamer_id = getattr(self, '_streamer_id', "")
                streamer_name = getattr(self, '_streamer_name', "")
                event_title = getattr(self, '_event_title', "")
                
                # Utiliser la stratégie adaptive
                decision = adaptive_strategy.make_decision(
                    outcomes=self.outcomes,
                    balance=balance,
                    streamer_id=streamer_id,
                    streamer_name=streamer_name,
                    prediction_title=event_title,
                    base_percentage=self.settings.percentage if self.settings.percentage else 5.0,
                    max_bet=self.settings.max_points if self.settings.max_points else 50000,
                    min_bet=10
                )
                
                if decision:
                    self.decision["choice"] = decision.get("choice")
                    self.decision["amount"] = decision.get("amount", 0)
                    self.decision["id"] = decision.get("id")
                    self.decision["reason"] = decision.get("reason", "Adaptive Strategy")
                    return self.decision
                else:
                    # Skip le bet si la stratégie retourne None
                    return self.decision
                    
            except ImportError as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Impossible d'importer AdaptiveBetStrategy, fallback vers CROWD_WISDOM: {e}")
                self.settings.strategy = Strategy.CROWD_WISDOM
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erreur dans ADAPTIVE, fallback vers CROWD_WISDOM: {e}")
                self.settings.strategy = Strategy.CROWD_WISDOM
        
        # Nouvelle stratégie CROWD_WISDOM basée sur l'intelligence collective
        if self.settings.strategy == Strategy.CROWD_WISDOM:
            try:
                from TwitchChannelPointsMiner.classes.entities.CrowdWisdom import (
                    CrowdWisdomStrategy, CrowdWisdomConfig
                )
                
                # Créer la stratégie avec config
                config = CrowdWisdomConfig()
                config.BASE_PERCENTAGE = self.settings.percentage if self.settings.percentage else 5.0
                config.MAX_BET = self.settings.max_points if self.settings.max_points else 50000
                config.MIN_BET = 10  # Minimum pour placer un bet
                
                strategy = CrowdWisdomStrategy(config)
                
                # Utiliser la stratégie crowd wisdom
                # Le titre peut être passé via l'event si disponible
                decision = strategy.should_bet(
                    outcomes=self.outcomes,
                    balance=balance,
                    title=getattr(self, '_event_title', "")  # Titre de l'événement si disponible
                )
                
                if decision:
                    self.decision["choice"] = decision.get("choice")
                    self.decision["amount"] = decision.get("amount", 0)
                    self.decision["id"] = decision.get("id")
                    # Stocker la raison pour le logging
                    self.decision["reason"] = decision.get("reason", "Crowd Wisdom")
                    return self.decision
                else:
                    # Skip le bet si la stratégie retourne None
                    return self.decision
                    
            except ImportError as e:
                # Fallback vers SMART si import échoue
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Impossible d'importer CrowdWisdom, fallback vers SMART: {e}")
                self.settings.strategy = Strategy.SMART
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erreur dans CROWD_WISDOM, fallback vers SMART: {e}")
                self.settings.strategy = Strategy.SMART
        
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

        if self.decision["choice"] is not None:
            # Si CROWD_WISDOM, le montant a déjà été calculé
            if self.settings.strategy == Strategy.CROWD_WISDOM and self.decision.get("amount", 0) > 0:
                # Le montant est déjà calculé par CrowdWisdomStrategy
                pass
            else:
                # Calcul classique pour les autres stratégies
                #index = char_decision_as_index(self.decision["choice"])
                index = self.decision["choice"]
                if self.decision.get("id") is None:
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
