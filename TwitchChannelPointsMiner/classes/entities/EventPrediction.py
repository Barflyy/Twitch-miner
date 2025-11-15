from TwitchChannelPointsMiner.classes.entities.Bet import Bet
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.utils import _millify, float_round


class EventPrediction(object):
    __slots__ = [
        "streamer",
        "event_id",
        "title",
        "created_at",
        "prediction_window_seconds",
        "status",
        "result",
        "box_fillable",
        "bet_confirmed",
        "bet_placed",
        "bet",
    ]

    def __init__(
        self,
        streamer: Streamer,
        event_id,
        title,
        created_at,
        prediction_window_seconds,
        status,
        outcomes,
    ):
        self.streamer = streamer

        self.event_id = event_id
        self.title = title.strip()
        self.created_at = created_at
        self.prediction_window_seconds = prediction_window_seconds
        self.status = status
        self.result: dict = {"string": "", "type": None, "gained": 0}

        self.box_fillable = False
        self.bet_confirmed = False
        self.bet_placed = False
        self.bet = Bet(outcomes, streamer.settings.bet)
        # Passer le titre à la stratégie Bet pour le logging (via attribut dynamique)
        self.bet._event_title = self.title

    def __repr__(self):
        return f"EventPrediction(event_id={self.event_id}, streamer={self.streamer}, title={self.title})"

    def __str__(self):
        return (
            f"EventPrediction: {self.streamer} - {self.title}"
            if Settings.logger.less
            else self.__repr__()
        )

    def elapsed(self, timestamp):
        return float_round((timestamp - self.created_at).total_seconds())

    def closing_bet_after(self, timestamp):
        return float_round(self.prediction_window_seconds - self.elapsed(timestamp))
    
    def get_bet_delay(self, timestamp):
        """
        Calcule le délai réel avant de placer le bet selon delay_mode et delay
        Retourne le nombre de secondes à attendre avant de placer le bet
        """
        from TwitchChannelPointsMiner.classes.entities.Bet import DelayMode
        
        bet_settings = self.streamer.settings.bet
        if bet_settings is None:
            # Fallback : utiliser closing_bet_after si pas de settings
            return self.closing_bet_after(timestamp)
        
        # S'assurer que les valeurs par défaut sont appliquées
        if not hasattr(bet_settings, 'delay') or bet_settings.delay is None:
            bet_settings.default()
        if not hasattr(bet_settings, 'delay_mode') or bet_settings.delay_mode is None:
            bet_settings.default()
        
        delay_mode = bet_settings.delay_mode
        delay = bet_settings.delay
        elapsed = self.elapsed(timestamp)
        remaining = self.closing_bet_after(timestamp)
        
        # Calculer le délai selon le mode
        if delay_mode == DelayMode.FROM_START:
            # Placer le bet 'delay' secondes après le début
            wait_time = max(0, delay - elapsed)
            return float_round(wait_time)
        elif delay_mode == DelayMode.FROM_END:
            # Placer le bet 'delay' secondes avant la fin
            # Exemple : si remaining = 1800s et delay = 6s, on attend 1794s
            wait_time = max(0, remaining - delay)
            return float_round(wait_time)
        elif delay_mode == DelayMode.PERCENTAGE:
            # Placer le bet quand 'delay' pourcent du temps est écoulé
            # delay est un pourcentage (0.0 à 1.0)
            target_elapsed = self.prediction_window_seconds * delay
            wait_time = max(0, target_elapsed - elapsed)
            return float_round(wait_time)
        else:
            # Fallback : utiliser FROM_END avec delay=6 par défaut
            wait_time = max(0, remaining - 6)
            return float_round(wait_time)

    def print_recap(self) -> str:
        return f"{self}\n\t\t{self.bet}\n\t\tResult: {self.result['string']}"

    def parse_result(self, result) -> dict:
        result_type = result["type"]

        points = {}
        points["placed"] = (
            self.bet.decision["amount"] if result_type != "REFUND" else 0
        )
        points["won"] = (
            result["points_won"]
            if result["points_won"] or result_type == "REFUND"
            else 0
        )
        points["gained"] = (
            points["won"] - points["placed"] if result_type != "REFUND" else 0
        )
        points["prefix"] = "+" if points["gained"] >= 0 else ""

        action = (
            "Lost"
            if result_type == "LOSE"
            else ("Refunded" if result_type == "REFUND" else "Gained")
        )

        self.result = {
            "string": f"{result_type}, {action}: {points['prefix']}{_millify(points['gained'])}",
            "type": result_type,
            "gained": points["gained"],
        }

        return points
