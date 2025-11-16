"""
DiscordBotLogHandler - Envoie les logs Python vers Discord via le bot Discord
Version optimisée qui utilise le bot existant au lieu de webhooks
"""

import logging
import asyncio
from typing import Optional


class DiscordBotLogHandler(logging.Handler):
    """
    Handler logging qui envoie les logs vers Discord via le bot Discord.

    Plus simple que DiscordLogHandler car utilise le bot existant :
    - Pas besoin de webhooks
    - Pas de connexion HTTP séparée
    - Le bot gère automatiquement le rate limiting et batching
    """

    def __init__(self, send_log_func, level: int = logging.INFO):
        """
        Args:
            send_log_func: La fonction async send_log() du bot Discord
            level: Niveau de log minimum (INFO par défaut)
        """
        super().__init__(level)
        self.send_log_func = send_log_func
        self.loop = None

    def emit(self, record: logging.LogRecord):
        """Appelé par le système de logging."""
        try:
            # Détermine le niveau Discord
            if record.levelno >= logging.ERROR:
                level = 'error'
            elif record.levelno >= logging.WARNING:
                level = 'warning'
            else:
                level = 'info'

            # Formate le message
            message = self.format(record)

            # Récupère ou crée l'event loop
            if self.loop is None:
                try:
                    self.loop = asyncio.get_running_loop()
                except RuntimeError:
                    # Pas de loop en cours, utiliser le loop principal du bot
                    self.loop = asyncio.get_event_loop()

            # Envoie de manière asynchrone (non-bloquant)
            asyncio.run_coroutine_threadsafe(
                self.send_log_func(
                    level=level,
                    title=record.levelname,
                    message=message,
                    module=record.module,
                    func=record.funcName
                ),
                self.loop
            )

        except Exception as e:
            # Ne jamais crasher le logging
            self.handleError(record)


class DiscordBotErrorHandler(DiscordBotLogHandler):
    """Handler spécialisé pour les erreurs uniquement."""

    def __init__(self, send_log_func):
        super().__init__(send_log_func, level=logging.ERROR)


class DiscordBotWarningHandler(DiscordBotLogHandler):
    """Handler spécialisé pour les warnings."""

    def __init__(self, send_log_func):
        super().__init__(send_log_func, level=logging.WARNING)

    def filter(self, record):
        """Filtre : seulement les warnings (pas les erreurs)."""
        return record.levelno < logging.ERROR


class DiscordBotInfoHandler(DiscordBotLogHandler):
    """Handler spécialisé pour les infos."""

    def __init__(self, send_log_func):
        super().__init__(send_log_func, level=logging.INFO)

    def filter(self, record):
        """Filtre : seulement les infos (pas les warnings/erreurs)."""
        return record.levelno < logging.WARNING


def setup_discord_bot_logging(
    send_log_func,
    logger_name: Optional[str] = None
):
    """
    Configure le logging Discord via le bot pour un logger.

    Args:
        send_log_func: La fonction async send_log() du bot Discord
        logger_name: Nom du logger (None = root logger)

    Example:
        # Dans discord_bot.py, après avoir défini send_log():
        from TwitchChannelPointsMiner.classes.DiscordBotLogHandler import setup_discord_bot_logging
        setup_discord_bot_logging(send_log)
    """
    logger = logging.getLogger(logger_name)

    # Handler erreurs
    error_handler = DiscordBotErrorHandler(send_log_func)
    logger.addHandler(error_handler)

    # Handler warnings
    warning_handler = DiscordBotWarningHandler(send_log_func)
    logger.addHandler(warning_handler)

    # Handler infos
    info_handler = DiscordBotInfoHandler(send_log_func)
    logger.addHandler(info_handler)

    return logger
