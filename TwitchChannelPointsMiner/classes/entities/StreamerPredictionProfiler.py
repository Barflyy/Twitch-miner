"""
StreamerPredictionProfiler - Apprend les patterns de prédiction de chaque streamer
"""

import sqlite3
import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class StreamerPredictionProfiler:
    """
    Crée un profil de prédiction pour chaque streamer.
    Apprend leurs habitudes et optimise les bets.
    """

    def __init__(self, db_path: str = "streamer_profiles.db"):
        # Créer le dossier data s'il n'existe pas
        db_dir = Path(db_path).parent
        if db_dir and not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
        
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row  # Pour accès par nom de colonne
        self.create_tables()

    def create_tables(self):
        """Crée les tables SQLite si elles n'existent pas."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                streamer_id TEXT,
                streamer_name TEXT,
                prediction_title TEXT,
                prediction_type TEXT,
                game_category TEXT,
                option_1_text TEXT,
                option_1_pct REAL,
                option_1_odds REAL,
                option_2_text TEXT,
                option_2_pct REAL,
                option_2_odds REAL,
                winner INTEGER,
                bet_placed INTEGER DEFAULT 0,
                bet_choice INTEGER,
                bet_amount INTEGER,
                payout INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS streamer_stats (
                streamer_id TEXT PRIMARY KEY,
                streamer_name TEXT,
                total_predictions INTEGER DEFAULT 0,
                performance_predictions INTEGER DEFAULT 0,
                performance_wins INTEGER DEFAULT 0,
                objective_predictions INTEGER DEFAULT 0,
                objective_wins INTEGER DEFAULT 0,
                event_predictions INTEGER DEFAULT 0,
                event_wins INTEGER DEFAULT 0,
                troll_predictions INTEGER DEFAULT 0,
                troll_wins INTEGER DEFAULT 0,
                avg_confidence_level REAL,
                crowd_accuracy REAL,
                high_roller_accuracy REAL DEFAULT 0,
                sharp_signal_accuracy REAL DEFAULT 0,
                best_game_category TEXT,
                predictions_per_stream REAL,
                avg_time_between_predictions INTEGER,
                most_common_bet_time TEXT,
                total_bets_placed INTEGER DEFAULT 0,
                total_bets_won INTEGER DEFAULT 0,
                total_points_won INTEGER DEFAULT 0,
                total_points_lost INTEGER DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index pour améliorer les performances
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_streamer_id ON prediction_history(streamer_id)
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON prediction_history(timestamp)
        """)
        
        # Migration: Ajout des colonnes si elles manquent (pour les DB existantes)
        try:
            self.db.execute("ALTER TABLE streamer_stats ADD COLUMN high_roller_accuracy REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Colonne existe déjà
            
        try:
            self.db.execute("ALTER TABLE streamer_stats ADD COLUMN sharp_signal_accuracy REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Colonne existe déjà
        
        self.db.commit()

    def _classify_prediction(self, title: str) -> str:
        """Classifie automatiquement le type de prédiction."""
        if not title:
            return 'other'
        
        title_lower = title.lower()

        # Performance (victoire/défaite)
        if any(word in title_lower for word in ['gagner', 'win', 'victoire', 'perdre', 'lose', 'lose..', 'gagn', 'perd']):
            return 'performance'

        # Objectif chiffré
        if re.search(r'\d+', title_lower) and any(word in title_lower for word in ['but', 'kill', 'goal', 'point', 'score']):
            return 'objective'

        # Événement de jeu
        if any(word in title_lower for word in ['boss', 'round', 'niveau', 'phase', 'level', 'stage']):
            return 'event'

        # Troll/émotionnel
        if any(word in title_lower for word in ['rage', 'tilt', 'mort', 'fail', 'dead', 'die']):
            return 'troll'

        return 'other'

    def log_prediction(self, prediction_data: dict):
        """Enregistre une prédiction avec son résultat."""
        try:
            outcomes = prediction_data.get('outcomes', [])
            if len(outcomes) < 2:
                logger.warning("Pas assez d'outcomes pour logger la prédiction")
                return

            self.db.execute("""
                INSERT INTO prediction_history 
                (streamer_id, streamer_name, prediction_title, prediction_type, 
                 game_category, option_1_text, option_1_pct, option_1_odds,
                 option_2_text, option_2_pct, option_2_odds, winner, 
                 bet_placed, bet_choice, bet_amount, payout)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction_data.get('streamer_id', ''),
                prediction_data.get('streamer_name', ''),
                prediction_data.get('title', ''),
                self._classify_prediction(prediction_data.get('title', '')),
                prediction_data.get('game', ''),
                outcomes[0].get('title', ''),
                outcomes[0].get('percentage_users', 0),
                outcomes[0].get('odds', 0),
                outcomes[1].get('title', ''),
                outcomes[1].get('percentage_users', 0),
                outcomes[1].get('odds', 0),
                prediction_data.get('winner'),  # 0 ou 1
                prediction_data.get('bet_placed', 0),
                prediction_data.get('bet_choice'),
                prediction_data.get('bet_amount', 0),
                prediction_data.get('payout', 0)
            ))
            self.db.commit()

            # Met à jour les stats du streamer
            self.update_streamer_stats(prediction_data.get('streamer_id'))
            
        except Exception as e:
            logger.error(f"Erreur lors du logging de prédiction: {e}", exc_info=True)
            self.db.rollback()

    def update_streamer_stats(self, streamer_id: str):
        """Met à jour les statistiques d'un streamer."""
        try:
            # Compte les prédictions par type
            cursor = self.db.execute("""
                SELECT 
                    prediction_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN winner IS NOT NULL THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN winner = (CASE WHEN option_1_pct > 50 THEN 0 ELSE 1 END) THEN 1 ELSE 0 END) as crowd_wins
                FROM prediction_history
                WHERE streamer_id = ?
                GROUP BY prediction_type
            """, (streamer_id,))
            
            stats_by_type = {}
            total_predictions = 0
            total_crowd_wins = 0
            total_resolved = 0
            
            for row in cursor.fetchall():
                pred_type = row[0]
                total = row[1]
                resolved = row[2]
                crowd_wins = row[3]
                
                stats_by_type[pred_type] = {
                    'total': total,
                    'resolved': resolved,
                    'crowd_wins': crowd_wins
                }
                total_predictions += total
                total_resolved += resolved
                total_crowd_wins += crowd_wins
            
            # Calcule la précision de la foule
            crowd_accuracy = (total_crowd_wins / total_resolved * 100) if total_resolved > 0 else 0
            
            # Stats de betting
            cursor = self.db.execute("""
                SELECT 
                    COUNT(*) as total_bets,
                    SUM(CASE WHEN payout > 0 THEN 1 ELSE 0 END) as bets_won,
                    SUM(CASE WHEN payout > 0 THEN payout ELSE 0 END) as points_won,
                    SUM(CASE WHEN payout = 0 AND bet_amount > 0 THEN bet_amount ELSE 0 END) as points_lost
                FROM prediction_history
                WHERE streamer_id = ? AND bet_placed = 1
            """, (streamer_id,))
            
            bet_stats = cursor.fetchone()
            total_bets = bet_stats[0] if bet_stats else 0
            bets_won = bet_stats[1] if bet_stats else 0
            points_won = bet_stats[2] if bet_stats else 0
            points_won = bet_stats[2] if bet_stats else 0
            points_lost = bet_stats[3] if bet_stats else 0

            # --- NOUVEAUX CALCULS ---
            
            # 1. High Roller Accuracy (Est-ce que l'option avec le plus gros bet moyen gagne ?)
            # On récupère tout l'historique pour ce streamer
            cursor = self.db.execute("""
                SELECT 
                    option_1_pct, option_1_odds, 
                    option_2_pct, option_2_odds,
                    winner
                FROM prediction_history
                WHERE streamer_id = ? AND winner IS NOT NULL
            """, (streamer_id,))
            
            hr_wins = 0
            hr_total = 0
            sharp_wins = 0
            sharp_total = 0
            
            for row in cursor.fetchall():
                # Reconstitution approximative des volumes (car on n'a pas stocké les volumes exacts)
                # On utilise les odds pour déduire le ratio de volume
                # Odds = Total / Option_Pool
                # Donc Option_Pool = Total / Odds
                # Ratio Avg Bet = (Pool1/Users1) / (Pool2/Users2)
                
                # Simplification: On assume que Odds est inversement proportionnel au volume de points
                # Si Odds1 = 2.0 et Odds2 = 2.0 -> Volume égal
                # Si Odds1 = 1.5 (Gros favori points) et Odds2 = 3.0 -> Option 1 a 2x plus de points
                
                try:
                    opt1_pct = row['option_1_pct'] or 50
                    opt2_pct = row['option_2_pct'] or 50
                    
                    # Si les pourcentages sont dispos, on peut estimer le nombre d'users relatif
                    # (On n'a pas le nombre absolu, mais le ratio suffit)
                    
                    # Est-ce que le "Smart Money" (gros bets) est sur l'option 1 ?
                    # Smart Money = Part des points > Part des utilisateurs
                    # Part des points Opt 1 = 1 / row['option_1_odds'] (approximativement, normalisé)
                    
                    # Méthode plus simple:
                    # Si Option 1 a 30% des users mais 50% des points -> High Roller sur 1
                    
                    # On n'a pas stocké les points exacts dans l'historique, c'est une limitation.
                    # MAIS on a stocké les cotes (odds) !
                    # Cote = Total_Points / Option_Points
                    # Donc Option_Points_Share = 1 / Cote
                    
                    if not row['option_1_odds'] or not row['option_2_odds']:
                        continue
                        
                    opt1_points_share = 1 / row['option_1_odds']
                    opt2_points_share = 1 / row['option_2_odds']
                    total_share = opt1_points_share + opt2_points_share
                    
                    opt1_points_pct = (opt1_points_share / total_share) * 100
                    
                    # High Roller Choice = Là où le % de points est > % d'users
                    # Ex: 30% users, 50% points -> Avg bet plus élevé
                    
                    avg_bet_1_score = opt1_points_pct / opt1_pct if opt1_pct > 0 else 0
                    avg_bet_2_score = (100 - opt1_points_pct) / opt2_pct if opt2_pct > 0 else 0
                    
                    hr_choice = 0 if avg_bet_1_score > avg_bet_2_score else 1
                    winner_idx = row['winner'] # 0 ou 1
                    
                    # High Roller Stats
                    if abs(avg_bet_1_score - avg_bet_2_score) > 0.1: # Marge d'erreur
                        hr_total += 1
                        if hr_choice == winner_idx:
                            hr_wins += 1
                            
                    # Sharp Signal Stats (Minorité + Gros argent)
                    # Minorité (< 40%) MAIS Gros argent (Avg bet ratio > 1.2)
                    is_sharp_1 = (opt1_pct < 40) and (avg_bet_1_score > 1.2 * avg_bet_2_score)
                    is_sharp_2 = (opt2_pct < 40) and (avg_bet_2_score > 1.2 * avg_bet_1_score)
                    
                    if is_sharp_1:
                        sharp_total += 1
                        if winner_idx == 0:
                            sharp_wins += 1
                    elif is_sharp_2:
                        sharp_total += 1
                        if winner_idx == 1:
                            sharp_wins += 1
                            
                except Exception:
                    continue

            high_roller_accuracy = (hr_wins / hr_total * 100) if hr_total > 0 else 50
            sharp_signal_accuracy = (sharp_wins / sharp_total * 100) if sharp_total > 0 else 0
            
            # Récupère le nom du streamer
            cursor = self.db.execute("""
                SELECT streamer_name FROM prediction_history 
                WHERE streamer_id = ? LIMIT 1
            """, (streamer_id,))
            streamer_name_row = cursor.fetchone()
            streamer_name = streamer_name_row[0] if streamer_name_row else streamer_id
            
            # Met à jour ou insère les stats
            self.db.execute("""
                INSERT INTO streamer_stats 
                (streamer_id, streamer_name, total_predictions, 
                 performance_predictions, performance_wins,
                 objective_predictions, objective_wins,
                 event_predictions, event_wins,
                 troll_predictions, troll_wins,
                 crowd_accuracy, total_bets_placed, total_bets_won,
                 total_points_won, total_points_lost, high_roller_accuracy, sharp_signal_accuracy, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(streamer_id) DO UPDATE SET
                    streamer_name = excluded.streamer_name,
                    total_predictions = excluded.total_predictions,
                    performance_predictions = excluded.performance_predictions,
                    performance_wins = excluded.performance_wins,
                    objective_predictions = excluded.objective_predictions,
                    objective_wins = excluded.objective_wins,
                    event_predictions = excluded.event_predictions,
                    event_wins = excluded.event_wins,
                    troll_predictions = excluded.troll_predictions,
                    troll_wins = excluded.troll_wins,
                    crowd_accuracy = excluded.crowd_accuracy,
                    total_bets_placed = excluded.total_bets_placed,
                    total_bets_won = excluded.total_bets_won,
                    total_points_won = excluded.total_points_won,
                    total_points_lost = excluded.total_points_lost,
                    high_roller_accuracy = excluded.high_roller_accuracy,
                    sharp_signal_accuracy = excluded.sharp_signal_accuracy,
                    last_updated = CURRENT_TIMESTAMP
            """, (
                streamer_id,
                streamer_name,
                total_predictions,
                stats_by_type.get('performance', {}).get('total', 0),
                stats_by_type.get('performance', {}).get('crowd_wins', 0),
                stats_by_type.get('objective', {}).get('total', 0),
                stats_by_type.get('objective', {}).get('crowd_wins', 0),
                stats_by_type.get('event', {}).get('total', 0),
                stats_by_type.get('event', {}).get('crowd_wins', 0),
                stats_by_type.get('troll', {}).get('total', 0),
                stats_by_type.get('troll', {}).get('crowd_wins', 0),
                crowd_accuracy,
                total_bets,
                bets_won,
                points_won,
                points_lost,
                high_roller_accuracy,
                sharp_signal_accuracy
            ))
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des stats: {e}", exc_info=True)
            self.db.rollback()

    def get_streamer_profile(self, streamer_id: str) -> Optional[Dict[str, Any]]:
        """Récupère le profil complet d'un streamer."""
        try:
            # Stats globales
            cursor = self.db.execute("""
                SELECT * FROM streamer_stats WHERE streamer_id = ?
            """, (streamer_id,))
            stats_row = cursor.fetchone()

            if not stats_row:
                return None

            stats = dict(stats_row)

            # Patterns détaillés par type
            cursor = self.db.execute("""
                SELECT 
                    prediction_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN winner IS NOT NULL THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN winner = (CASE WHEN option_1_pct > 50 THEN 0 ELSE 1 END) THEN 1 ELSE 0 END) as crowd_wins,
                    AVG(ABS(option_1_pct - option_2_pct)) as avg_gap
                FROM prediction_history
                WHERE streamer_id = ?
                GROUP BY prediction_type
            """, (streamer_id,))

            patterns = {}
            for row in cursor.fetchall():
                pred_type = row[0]
                total = row[1]
                resolved = row[2]
                crowd_wins = row[3]
                avg_gap = row[4] if row[4] else 0

                patterns[pred_type] = {
                    'total': total,
                    'resolved': resolved,
                    'crowd_accuracy': (crowd_wins / resolved * 100) if resolved > 0 else 0,
                    'avg_gap': avg_gap
                }

            return {
                'stats': stats,
                'patterns': patterns,
                'recommendations': self._generate_recommendations(streamer_id, patterns, stats)
            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du profil: {e}", exc_info=True)
            return None

    def _generate_recommendations(self, streamer_id: str, patterns: dict, stats: dict) -> dict:
        """Génère des recommandations de stratégie pour ce streamer."""
        recommendations = {
            'optimal_strategy': None,
            'skip_types': [],
            'confidence_modifier': 1.0,
            'reasoning': []
        }

        # Analyse par type de prédiction
        for pred_type, data in patterns.items():
            crowd_acc = data.get('crowd_accuracy', 50)

            if crowd_acc > 75:
                recommendations['reasoning'].append(
                    f"✅ {pred_type}: La foule a raison {crowd_acc:.0f}% du temps → SUIVRE le consensus"
                )
                if recommendations['optimal_strategy'] is None:
                    recommendations['optimal_strategy'] = 'follow_crowd'

            elif crowd_acc < 45:
                recommendations['reasoning'].append(
                    f"⚠️ {pred_type}: La foule se trompe {100-crowd_acc:.0f}% du temps → CONTRE-courant"
                )
                recommendations['skip_types'].append(pred_type)

            else:
                recommendations['reasoning'].append(
                    f"🤔 {pred_type}: 50/50 ({crowd_acc:.0f}%) → Chercher des sharp signals"
                )

        # Ajustement de confiance global
        total_predictions = stats.get('total_predictions', 0)
        if total_predictions < 10:
            recommendations['confidence_modifier'] = 0.7
            recommendations['reasoning'].append(
                f"📊 Seulement {total_predictions} prédictions → Confiance réduite"
            )
        elif total_predictions > 50:
            recommendations['confidence_modifier'] = 1.2
            recommendations['reasoning'].append(
                f"📊 {total_predictions} prédictions → Profil fiable"
            )

        return recommendations

    def should_bet_on_streamer(self, streamer_id: str, prediction_data: dict) -> dict:
        """Décide si on doit parier en fonction du profil du streamer."""
        profile = self.get_streamer_profile(streamer_id)

        if not profile or not profile.get('stats'):
            # Pas assez de data → stratégie par défaut conservative
            return {
                'should_bet': True,
                'strategy': 'follow_crowd',
                'confidence_modifier': 0.8,
                'reason': "Nouveau streamer, mode apprentissage"
            }

        pred_type = self._classify_prediction(prediction_data.get('title', ''))
        recommendations = profile.get('recommendations', {})

        # Si ce type est dans la skip list
        if pred_type in recommendations.get('skip_types', []):
            return {
                'should_bet': False,
                'strategy': None,
                'confidence_modifier': 0,
                'reason': f"Type '{pred_type}' non profitable pour ce streamer"
            }

        # Pattern spécifique au type
        type_pattern = profile.get('patterns', {}).get(pred_type, {})
        crowd_accuracy = type_pattern.get('crowd_accuracy', 50)
        
        # Récupération des nouvelles stats
        stats = profile.get('stats', {})
        high_roller_acc = stats.get('high_roller_accuracy', 50)
        sharp_acc = stats.get('sharp_signal_accuracy', 0)

        # Logique de décision améliorée
        if sharp_acc > 65:
            strategy = 'sharp_only'
            reason = f"Sharp signals très fiables ({sharp_acc:.0f}%)"
            
        elif high_roller_acc > 60:
            strategy = 'follow_high_rollers'
            reason = f"Les gros parieurs gagnent souvent ({high_roller_acc:.0f}%)"
            
        elif crowd_accuracy > 52:
            strategy = 'follow_crowd'
            reason = f"La foule a souvent raison ({crowd_accuracy:.0f}%)"
            
        elif crowd_accuracy < 40:
            strategy = 'contrarian'
            reason = f"La foule a souvent tort ({crowd_accuracy:.0f}%)"
            
        else:
            strategy = 'follow_crowd' # Par défaut, on suit la foule comme demandé
            reason = "Pas de tendance claire, on suit la majorité"

        return {
            'should_bet': True,
            'strategy': strategy,
            'confidence_modifier': recommendations.get('confidence_modifier', 1.0),
            'reason': reason
        }

    def get_recent_predictions(self, limit: int = 20) -> list:
        """Récupère les prédictions récentes."""
        cursor = self.db.execute("""
            SELECT 
                streamer_name,
                prediction_title,
                option_1_text,
                option_2_text,
                winner,
                bet_placed,
                bet_choice,
                payout,
                timestamp
            FROM prediction_history
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Ferme la connexion à la base de données."""
        self.db.close()

