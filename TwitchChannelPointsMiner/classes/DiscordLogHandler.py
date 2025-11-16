"""
DiscordLogHandler - Envoie les logs Python vers Discord via webhooks
Système robuste avec rate limiting, batching et retry
"""

import logging
import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional
from collections import deque
from datetime import datetime
import threading


class DiscordLogHandler(logging.Handler):
    """
    Handler logging qui envoie les logs vers Discord via webhook.

    Features:
    - Rate limiting automatique (respect des limites Discord)
    - Batching des logs similaires
    - Embeds colorés selon niveau de log
    - Retry automatique en cas d'erreur
    - Thread séparé pour éviter blocking
    """

    # Couleurs Discord selon niveau de log
    LOG_COLORS = {
        logging.CRITICAL: 0x8B0000,  # Rouge foncé
        logging.ERROR: 0xFF0000,     # Rouge
        logging.WARNING: 0xFFA500,   # Orange
        logging.INFO: 0x00FF00,      # Vert
        logging.DEBUG: 0x808080,     # Gris
    }

    # Emojis selon niveau
    LOG_EMOJIS = {
        logging.CRITICAL: "💀",
        logging.ERROR: "❌",
        logging.WARNING: "⚠️",
        logging.INFO: "ℹ️",
        logging.DEBUG: "🔍",
    }

    def __init__(
        self,
        webhook_url: str,
        level: int = logging.INFO,
        batch_time: float = 2.0,
        max_batch_size: int = 10,
        rate_limit_per_minute: int = 30
    ):
        """
        Args:
            webhook_url: URL du webhook Discord
            level: Niveau de log minimum (INFO par défaut)
            batch_time: Temps d'attente avant envoi d'un batch (secondes)
            max_batch_size: Nombre max de logs dans un batch
            rate_limit_per_minute: Limite d'envois par minute
        """
        super().__init__(level)
        self.webhook_url = webhook_url
        self.batch_time = batch_time
        self.max_batch_size = max_batch_size
        self.rate_limit_per_minute = rate_limit_per_minute

        # File d'attente des logs
        self.queue = deque(maxlen=1000)  # Max 1000 logs en attente
        self.lock = threading.Lock()

        # Rate limiting
        self.sent_times = deque(maxlen=rate_limit_per_minute)

        # Thread d'envoi
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def emit(self, record: logging.LogRecord):
        """Appelé par le système de logging."""
        try:
            # Formate le message
            msg = self.format(record)

            # Ajoute à la queue
            with self.lock:
                self.queue.append({
                    'level': record.levelno,
                    'levelname': record.levelname,
                    'message': msg,
                    'timestamp': time.time(),
                    'module': record.module,
                    'funcName': record.funcName,
                })

        except Exception as e:
            # Ne jamais crasher le logging
            self.handleError(record)

    def _worker(self):
        """Thread worker qui envoie les logs par batch."""
        # Crée un event loop pour ce thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self.running:
                # Attends batch_time ou que la queue soit pleine
                time.sleep(self.batch_time)

                # Récupère un batch
                batch = self._get_batch()

                if batch:
                    # Envoie de manière asynchrone
                    loop.run_until_complete(self._send_batch(batch))

        except Exception as e:
            print(f"DiscordLogHandler worker error: {e}")
        finally:
            loop.close()

    def _get_batch(self) -> List[Dict]:
        """Récupère un batch de logs depuis la queue."""
        batch = []

        with self.lock:
            while len(batch) < self.max_batch_size and self.queue:
                batch.append(self.queue.popleft())

        return batch

    async def _send_batch(self, batch: List[Dict]):
        """Envoie un batch de logs vers Discord."""
        if not batch:
            return

        # Vérification rate limit
        if not self._check_rate_limit():
            # Rate limit atteint, remet les logs dans la queue
            with self.lock:
                self.queue.extendleft(reversed(batch))
            await asyncio.sleep(2)  # Attends un peu
            return

        # Groupe par niveau de log
        grouped = {}
        for log in batch:
            level = log['level']
            if level not in grouped:
                grouped[level] = []
            grouped[level].append(log)

        # Envoie un embed par niveau
        async with aiohttp.ClientSession() as session:
            for level, logs in grouped.items():
                try:
                    embed = self._create_embed(level, logs)
                    payload = {
                        "embeds": [embed],
                        "username": "Twitch Miner Logs"
                    }

                    async with session.post(
                        self.webhook_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 429:  # Rate limited
                            # Discord nous rate limit, attends
                            retry_after = float(response.headers.get('Retry-After', 5))
                            await asyncio.sleep(retry_after)
                        elif response.status >= 400:
                            print(f"Discord webhook error {response.status}: {await response.text()}")

                except Exception as e:
                    print(f"Error sending logs to Discord: {e}")

        # Enregistre l'envoi pour rate limiting
        self._record_send()

    def _create_embed(self, level: int, logs: List[Dict]) -> Dict:
        """Crée un embed Discord pour un groupe de logs."""
        color = self.LOG_COLORS.get(level, 0x808080)
        emoji = self.LOG_EMOJIS.get(level, "📝")
        level_name = logging.getLevelName(level)

        # Titre
        if len(logs) == 1:
            title = f"{emoji} {level_name}"
        else:
            title = f"{emoji} {level_name} ({len(logs)} logs)"

        # Description : combine les messages
        description_lines = []
        for log in logs[:10]:  # Max 10 logs par embed
            timestamp = datetime.fromtimestamp(log['timestamp']).strftime('%H:%M:%S')
            module = log['module']
            func = log['funcName']

            # Tronque le message si trop long
            message = log['message']
            if len(message) > 200:
                message = message[:197] + "..."

            description_lines.append(f"`{timestamp}` **{module}.{func}**\n{message}")

        description = "\n\n".join(description_lines)

        # Limite Discord : 4096 caractères
        if len(description) > 4000:
            description = description[:3997] + "..."

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": f"Twitch Miner • {len(logs)} event(s)"
            }
        }

        return embed

    def _check_rate_limit(self) -> bool:
        """Vérifie si on peut envoyer (rate limit)."""
        now = time.time()

        # Nettoie les anciens timestamps (> 1 minute)
        while self.sent_times and now - self.sent_times[0] > 60:
            self.sent_times.popleft()

        # Vérifie si on est sous la limite
        return len(self.sent_times) < self.rate_limit_per_minute

    def _record_send(self):
        """Enregistre un envoi pour rate limiting."""
        self.sent_times.append(time.time())

    def close(self):
        """Ferme le handler proprement."""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=5)
        super().close()


class DiscordErrorHandler(DiscordLogHandler):
    """Handler spécialisé pour les erreurs uniquement."""

    def __init__(self, webhook_url: str):
        super().__init__(
            webhook_url=webhook_url,
            level=logging.ERROR,
            batch_time=1.0,  # Envoi plus rapide pour les erreurs
            max_batch_size=5,
            rate_limit_per_minute=20
        )


class DiscordWarningHandler(DiscordLogHandler):
    """Handler spécialisé pour les warnings."""

    def __init__(self, webhook_url: str):
        super().__init__(
            webhook_url=webhook_url,
            level=logging.WARNING,
            batch_time=3.0,
            max_batch_size=10,
            rate_limit_per_minute=15
        )


class DiscordInfoHandler(DiscordLogHandler):
    """Handler spécialisé pour les infos (plus permissif sur batching)."""

    def __init__(self, webhook_url: str):
        super().__init__(
            webhook_url=webhook_url,
            level=logging.INFO,
            batch_time=5.0,  # Batch plus long
            max_batch_size=20,  # Plus de logs par batch
            rate_limit_per_minute=10  # Moins d'envois
        )


def setup_discord_logging(
    error_webhook: Optional[str] = None,
    warning_webhook: Optional[str] = None,
    info_webhook: Optional[str] = None,
    logger_name: Optional[str] = None
):
    """
    Configure le logging Discord pour un logger.

    Args:
        error_webhook: URL webhook pour les erreurs
        warning_webhook: URL webhook pour les warnings
        info_webhook: URL webhook pour les infos
        logger_name: Nom du logger (None = root logger)

    Example:
        setup_discord_logging(
            error_webhook="https://discord.com/api/webhooks/...",
            warning_webhook="https://discord.com/api/webhooks/...",
            info_webhook="https://discord.com/api/webhooks/..."
        )
    """
    logger = logging.getLogger(logger_name)

    # Handler erreurs
    if error_webhook:
        error_handler = DiscordErrorHandler(error_webhook)
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)

    # Handler warnings
    if warning_webhook:
        warning_handler = DiscordWarningHandler(warning_webhook)
        warning_handler.setLevel(logging.WARNING)
        warning_handler.addFilter(lambda record: record.levelno < logging.ERROR)
        logger.addHandler(warning_handler)

    # Handler infos
    if info_webhook:
        info_handler = DiscordInfoHandler(info_webhook)
        info_handler.setLevel(logging.INFO)
        info_handler.addFilter(lambda record: record.levelno < logging.WARNING)
        logger.addHandler(info_handler)

    return logger
