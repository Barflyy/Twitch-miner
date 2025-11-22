from TwitchChannelPointsMiner.classes.entities.Bet import Bet
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.utils import _millify, float_round
import time


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
        "optimal_timing_system",  # Système de timing optimal (optionnel)
        "prediction_start_time",  # Timestamp de début pour tracking
        "_data_quality_multiplier",  # Data quality score de SmartBetTiming V2
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
        # Passer les infos à la stratégie Bet pour le logging (via attributs)
        self.bet._event_title = self.title
        self.bet._streamer_id = str(streamer.channel_id) if hasattr(streamer, 'channel_id') else ""
        self.bet._streamer_name = streamer.username if hasattr(streamer, 'username') else ""
        
        # Système de timing optimal (initialisé à None, peut être injecté)
        self.optimal_timing_system = None
        self.prediction_start_time = time.time()

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
        
        Si optimal_timing_system est disponible, utilise le système de timing optimal.
        Sinon, utilise la méthode classique.
        """
        # Si le système de timing optimal est disponible et les outcomes sont mis à jour, l'utiliser
        if self.optimal_timing_system is not None and hasattr(self.bet, 'outcomes') and self.bet.outcomes:
            try:
                # Prépare les données pour le système optimal
                prediction_data = {
                    'id': self.event_id,
                    'event_id': self.event_id,
                    'streamer_id': str(self.streamer.channel_id) if hasattr(self.streamer, 'channel_id') else "",
                    'streamer_name': self.streamer.username if hasattr(self.streamer, 'username') else "",
                    'outcomes': self.bet.outcomes,
                    'time_remaining': self.closing_bet_after(timestamp)
                }
                
                # Obtient le timing optimal
                timing_result = self.optimal_timing_system.get_optimal_bet_timing(
                    prediction_data=prediction_data,
                    current_timestamp=timestamp,
                    announced_duration=self.prediction_window_seconds
                )
                
                if timing_result.get('should_bet_now'):
                    # Log si nécessaire
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"""
                    🎯 TIMING OPTIMAL CALCULÉ
                    ├─ Streamer: {self.streamer.username if hasattr(self.streamer, 'username') else 'N/A'}
                    ├─ Prédiction: {self.title}
                    ├─ Stratégie: {timing_result.get('strategy', 'N/A')}
                    ├─ Raison: {timing_result.get('reason', 'N/A')}
                    ├─ Confiance: {timing_result.get('confidence', 0):.0%}
                    └─ Wait time: {timing_result.get('wait_time', 0):.1f}s
                    """.strip())
                
                return float_round(timing_result.get('wait_time', 0))
                
            except Exception as e:
                # En cas d'erreur, fallback vers la méthode classique
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Erreur dans timing optimal, fallback classique: {e}")
        
        # Méthode classique (fallback)
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
