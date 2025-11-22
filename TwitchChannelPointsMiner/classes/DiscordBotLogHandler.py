"""
DiscordBotLogHandler - Envoie les logs Python vers Discord via fichier partagé
Version inter-processus qui fonctionne même si le bot Discord tourne séparément
"""

import logging
import json
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
import threading


class SharedLogQueue:
    """
    Queue de logs partagée via fichier JSON.
    Le Twitch Miner écrit les logs, le bot Discord les lit.
    """

    def __init__(self, log_file: str = "discord_logs_queue.json"):
        # Utiliser DATA_DIR si défini
        import os
        data_dir = Path(os.getenv("DATA_DIR", "."))
        self.log_file = data_dir / log_file
        self.lock = threading.Lock()

    def add_log(self, level: str, message: str, module: str = "", func: str = ""):
        """Ajoute un log à la queue partagée."""
        try:
            with self.lock:
                # Lire les logs existants
                if self.log_file.exists():
                    try:
                        with open(self.log_file, 'r') as f:
                            logs = json.load(f)
                    except (json.JSONDecodeError, Exception):
                        logs = []
                else:
                    logs = []

                # Ajouter le nouveau log
                logs.append({
                    'level': level,
                    'message': message,
                    'module': module,
                    'func': func,
                    'timestamp': datetime.utcnow().isoformat()
                })

                # Limiter à 1000 logs max (éviter que le fichier grossisse trop)
                if len(logs) > 1000:
                    logs = logs[-1000:]

                # Écrire de manière atomique
                temp_file = self.log_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(logs, f)
                temp_file.replace(self.log_file)

        except Exception as e:
            # Ne jamais crasher le logging
            print(f"⚠️ Erreur ajout log partagé: {e}")

    def get_logs(self, clear: bool = True):
        """Récupère tous les logs et les efface si clear=True."""
        try:
            with self.lock:
                if not self.log_file.exists():
                    return []

                with open(self.log_file, 'r') as f:
                    logs = json.load(f)

                if clear and logs:
                    # Effacer le fichier après lecture
                    self.log_file.unlink()

                return logs

        except Exception as e:
            print(f"⚠️ Erreur lecture logs partagés: {e}")
            return []


class DiscordBotLogHandler(logging.Handler):
    """
    Handler logging qui écrit les logs dans un fichier partagé.
    Le bot Discord lit ce fichier et envoie les logs.
    """

    def __init__(self, level: int = logging.INFO):
        """
        Args:
            level: Niveau de log minimum (INFO par défaut)
        """
        super().__init__(level)
        self.shared_queue = SharedLogQueue()

    def emit(self, record: logging.LogRecord):
        """Appelé par le système de logging."""
        try:
            # Filtre les logs verbeux inutiles
            message = self.format(record)

            # Liste des patterns à ignorer (logs de progression, spam, etc.)
            ignore_patterns = [
                # 🚫 Logs de progression
                "📊",
                "streamers chargés",
                "channel points chargés",
                "min restantes",

                # 🚫 Messages d'attente et chargement
                "Please wait",
                "Loading data for",
                "Saving cookies to your computer",

                # 🚫 Auth et session (SAUF codes d'activation qui sont critiques !)
                "Start session:",
                # ✅ GARDE: "You'll have to login" (important)
                # ✅ GARDE: "Trying the TV login" (important)
                # ✅ GARDE: "Open https://www.twitch.tv/activate" (critique!)
                # ✅ GARDE: "and enter this code:" (critique!)
                # ✅ GARDE: "Hurry up! It will expire" (critique!)

                # 🚫 Données de chargement
                "Streamers passés au miner",
                "après filtrage blacklist",
                "Chargement des channel IDs",
                "channel IDs chargés",
                "Vérification de l'état en ligne",
                "bot_data.json mis à jour",

                # 🚫 API et cache
                "Utilisation API Twitch Helix",
                "User ID Twitch:",
                "Chargement des followers via API",
                "followers chargés",
                "Total:",
                "Cache GitHub sauvegardé",
                "Fichier JSON chargé",

                # 🚫 Système
                "Système de timing optimal",
                "SmartBetTiming",
                "MONITORING V2 STARTED",
                "Monitoring adaptatif démarré",

                # 🚫 Streamers inexistants (peu important)
                "does not exist",

                # 🚫 Online/Offline répétitifs (trop verbeux)
                "is Online!",
                "is Offline!",
                "Join IRC Chat:",
                "Leave IRC Chat:",

                # 🚫 Bet callbacks techniques
                "Bet callback appelé",
                "Going to complete bet for",
            ]

            # Ignorer si le message contient un pattern
            if any(pattern in message for pattern in ignore_patterns):
                return

            # Détermine le niveau Discord
            if record.levelno >= logging.ERROR:
                level = 'error'
            elif record.levelno >= logging.WARNING:
                level = 'warning'
            else:
                level = 'info'

            # Ajoute au fichier partagé
            self.shared_queue.add_log(
                level=level,
                message=message,
                module=record.module,
                func=record.funcName
            )

        except Exception as e:
            # Ne jamais crasher le logging
            self.handleError(record)


class DiscordBotErrorHandler(DiscordBotLogHandler):
    """Handler spécialisé pour les erreurs uniquement."""

    def __init__(self):
        super().__init__(level=logging.ERROR)


class DiscordBotWarningHandler(DiscordBotLogHandler):
    """Handler spécialisé pour les warnings."""

    def __init__(self):
        super().__init__(level=logging.WARNING)

    def filter(self, record):
        """Filtre : seulement les warnings (pas les erreurs)."""
        return record.levelno < logging.ERROR


class DiscordBotInfoHandler(DiscordBotLogHandler):
    """Handler spécialisé pour les infos."""

    def __init__(self):
        super().__init__(level=logging.INFO)

    def filter(self, record):
        """Filtre : seulement les infos (pas les warnings/erreurs)."""
        return record.levelno < logging.WARNING


def setup_discord_bot_logging(logger_name: Optional[str] = None):
    """
    Configure le logging Discord via fichier partagé pour un logger.

    Args:
        logger_name: Nom du logger (None = root logger)

    Example:
        # Dans run.py, après la configuration du TwitchChannelPointsMiner:
        from TwitchChannelPointsMiner.classes.DiscordBotLogHandler import setup_discord_bot_logging
        setup_discord_bot_logging()
    """
    logger = logging.getLogger(logger_name)

    # Handler erreurs
    error_handler = DiscordBotErrorHandler()
    logger.addHandler(error_handler)

    # Handler warnings
    warning_handler = DiscordBotWarningHandler()
    logger.addHandler(warning_handler)

    # Handler infos
    info_handler = DiscordBotInfoHandler()
    logger.addHandler(info_handler)

    return logger
