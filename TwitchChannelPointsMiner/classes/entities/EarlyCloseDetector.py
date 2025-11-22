"""
EarlyCloseDetector - Track les streamers qui closent souvent les prédictions en avance
"""

import logging
import sqlite3
import os
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EarlyCloseDetector:
    """
    Track les streamers qui closent souvent les prédictions en avance.
    Adapte le timing en conséquence.
    """

    def __init__(self, db_path: str = "early_close_tracking.db"):
        # Utilise un chemin dans le répertoire courant si absolu non fourni
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.getcwd(), db_path)
        
        self.db_path = db_path
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row  # Pour accéder aux colonnes par nom
        self.create_table()

    def create_table(self):
        """Crée la table de tracking si elle n'existe pas."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS prediction_timing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                streamer_id TEXT,
                streamer_name TEXT,
                prediction_id TEXT,
                announced_duration INTEGER,  -- Durée annoncée (secondes)
                actual_duration INTEGER,     -- Durée réelle
                closed_early BOOLEAN,        -- TRUE si fermé avant la fin
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_streamer_id 
            ON prediction_timing(streamer_id, timestamp)
        """)
        self.db.commit()

    def log_prediction_close(
        self, 
        streamer_id: str,
        streamer_name: str,
        prediction_id: str,
        announced_duration: int,
        actual_duration: int
    ):
        """Enregistre quand une prédiction se ferme."""
        try:
            # Fermé avec >10% d'avance = early close
            closed_early = actual_duration < (announced_duration * 0.9)

            self.db.execute("""
                INSERT INTO prediction_timing 
                (streamer_id, streamer_name, prediction_id, announced_duration, actual_duration, closed_early)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                streamer_id,
                streamer_name,
                prediction_id,
                announced_duration,
                actual_duration,
                closed_early
            ))
            self.db.commit()
            
            logger.debug(
                f"✅ Logged prediction close: {streamer_name} - "
                f"announced: {announced_duration}s, actual: {actual_duration}s, "
                f"early: {closed_early}"
            )
        except Exception as e:
            logger.error(f"Erreur lors du logging de prediction close: {e}", exc_info=True)

    def get_streamer_close_pattern(self, streamer_id: str) -> Dict[str, Any]:
        """
        Analyse le pattern de fermeture d'un streamer.

        Returns:
            {
                'early_close_rate': 0.0-1.0,
                'avg_close_offset': seconds,  // Combien de secondes avant la fin en moyenne
                'recommendation': 'early' | 'standard' | 'late'
            }
        """
        try:
            cursor = self.db.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN closed_early THEN 1 ELSE 0 END) as early_closes,
                    AVG(announced_duration - actual_duration) as avg_offset
                FROM prediction_timing
                WHERE streamer_id = ?
                AND timestamp > datetime('now', '-30 days')  -- Derniers 30 jours
            """, (streamer_id,))

            row = cursor.fetchone()

            if not row or row['total'] < 5:  # Moins de 5 prédictions
                return {
                    'early_close_rate': 0.3,  # Assume 30% par défaut
                    'avg_close_offset': 15,
                    'recommendation': 'standard',
                    'sample_size': row['total'] if row else 0
                }

            total = row['total']
            early_closes = row['early_closes'] or 0
            avg_offset = row['avg_offset'] or 0

            early_close_rate = early_closes / total

            # Détermine la recommandation
            if early_close_rate > 0.5:  # >50% fermées en avance
                recommendation = 'early'  # Bet dès que données stables
            elif early_close_rate > 0.25:
                recommendation = 'standard'  # Timing normal
            else:
                recommendation = 'late'  # Peut attendre plus longtemps

            return {
                'early_close_rate': early_close_rate,
                'avg_close_offset': avg_offset,
                'recommendation': recommendation,
                'sample_size': total
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'analyse du pattern: {e}", exc_info=True)
            return {
                'early_close_rate': 0.3,
                'avg_close_offset': 15,
                'recommendation': 'standard',
                'sample_size': 0
            }

    def get_adaptive_bet_time(
        self, 
        streamer_id: str, 
        announced_duration: int
    ) -> int:
        """
        Calcule le temps optimal pour bet en fonction du streamer.

        Returns:
            Nombre de secondes avant la fin du timer pour placer le bet
        """
        pattern = self.get_streamer_close_pattern(streamer_id)

        if pattern['recommendation'] == 'early':
            # Ce streamer close souvent tôt → bet dès que stable
            return max(5, announced_duration - 30)  # Bet à partir de T-30s minimum T-5s

        elif pattern['recommendation'] == 'standard':
            # Streamer normal → bet standard
            return 10  # Bet à T-10s

        else:  # 'late'
            # Streamer qui laisse tourner → on peut attendre
            return 5  # Bet à T-5s

    def close(self):
        """Ferme la connexion à la base de données."""
        if self.db:
            self.db.close()

    def __del__(self):
        """Destructeur pour fermer proprement la DB."""
        self.close()

