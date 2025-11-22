"""
LiveDashboard - Dashboard web pour monitorer le bot en temps réel
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Import Flask seulement si disponible
try:
    from flask import Flask, render_template, jsonify
    from flask_socketio import SocketIO, emit
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    logger.warning("Flask et Flask-SocketIO non disponibles. Dashboard désactivé.")


class LiveDashboard:
    """Dashboard web pour monitorer le bot en temps réel."""

    def __init__(self, bot_instance=None, port: int = 5000, host: str = '127.0.0.1'):
        """
        Args:
            bot_instance: Instance du bot TwitchChannelPointsMiner
            port: Port pour le serveur web
            host: Host pour le serveur web
        """
        if not FLASK_AVAILABLE:
            logger.error("Flask non disponible. Installez avec: pip install flask flask-socketio")
            self.available = False
            return
        
        self.bot = bot_instance
        self.port = port
        self.host = host
        self.available = True
        
        # Initialise Flask
        self.app = Flask(__name__, 
                        template_folder=Path(__file__).parent.parent.parent / 'templates',
                        static_folder=Path(__file__).parent.parent.parent / 'static')
        self.app.config['SECRET_KEY'] = os.urandom(24)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Profiler pour les stats
        try:
            from TwitchChannelPointsMiner.classes.entities.StreamerPredictionProfiler import (
                StreamerPredictionProfiler
            )
            self.profiler = StreamerPredictionProfiler()
        except Exception as e:
            logger.warning(f"Impossible d'initialiser le profiler: {e}")
            self.profiler = None
        
        # Routes
        self._setup_routes()
        
        # Stats en cache
        self.cache = {
            'last_update': datetime.now(),
            'stats': {},
            'streamers': [],
            'recent_bets': []
        }

    def _setup_routes(self):
        """Configure les routes Flask."""
        
        @self.app.route('/')
        def index():
            """Page principale."""
            return render_template('dashboard.html') if self._template_exists('dashboard.html') else self._default_dashboard()
        
        @self.app.route('/api/stats')
        def get_stats():
            """API pour les stats globales."""
            return jsonify(self._get_global_stats())
        
        @self.app.route('/api/streamers')
        def get_streamers():
            """Liste des streamers avec leurs performances."""
            return jsonify(self._get_streamers_stats())
        
        @self.app.route('/api/recent_bets')
        def get_recent_bets():
            """Derniers bets placés."""
            return jsonify(self._get_recent_bets())
        
        @self.app.route('/api/predictions')
        def get_active_predictions():
            """Prédictions actives."""
            return jsonify(self._get_active_predictions())
        
        @self.socketio.on('connect')
        def handle_connect():
            """Client connecté."""
            emit('connected', {'message': 'Connected to Twitch Mining Bot Dashboard'})
        
        @self.socketio.on('request_update')
        def handle_update_request():
            """Demande de mise à jour."""
            self.emit_update()

    def _template_exists(self, template_name: str) -> bool:
        """Vérifie si un template existe."""
        template_path = Path(self.app.template_folder) / template_name
        return template_path.exists()

    def _default_dashboard(self):
        """Dashboard HTML par défaut si pas de template."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Twitch Mining Bot Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: 'Segoe UI', Arial, sans-serif;
                    background: #0e0e10;
                    color: #efeff1;
                    padding: 20px;
                }
                .container { max-width: 1200px; margin: 0 auto; }
                h1 { color: #9147ff; margin-bottom: 30px; }
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .stat-card {
                    background: #18181b;
                    border: 1px solid #2d2d30;
                    border-radius: 8px;
                    padding: 20px;
                }
                .stat-value {
                    font-size: 32px;
                    font-weight: bold;
                    color: #9147ff;
                }
                .stat-label {
                    color: #adadb8;
                    margin-top: 5px;
                }
                .section {
                    background: #18181b;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                }
                .streamer-item, .bet-item {
                    padding: 15px;
                    border-bottom: 1px solid #2d2d30;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .live-indicator {
                    width: 10px;
                    height: 10px;
                    background: #f00;
                    border-radius: 50%;
                    display: inline-block;
                    margin-right: 10px;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                .status { color: #adadb8; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎮 Twitch Mining Bot Dashboard</h1>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value" id="total-points">Loading...</div>
                        <div class="stat-label">Total Points</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="active-streams">0</div>
                        <div class="stat-label">Active Streams</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="today-profit">+0</div>
                        <div class="stat-label">Today's Profit</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="win-rate">0%</div>
                        <div class="stat-label">Prediction Win Rate</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>📊 Top Streamers</h2>
                    <div id="streamer-list">Loading...</div>
                </div>
                
                <div class="section">
                    <h2>🎲 Recent Bets</h2>
                    <div id="recent-bets">Loading...</div>
                </div>
            </div>
            
            <script>
                const socket = io();
                
                async function loadStats() {
                    try {
                        const res = await fetch('/api/stats');
                        const data = await res.json();
                        
                        document.getElementById('total-points').textContent = 
                            (data.total_points || 0).toLocaleString();
                        document.getElementById('active-streams').textContent = 
                            data.active_streams || 0;
                        document.getElementById('today-profit').textContent = 
                            '+' + (data.today_profit || 0).toLocaleString();
                        document.getElementById('win-rate').textContent = 
                            data.predictions?.win_rate || '0%';
                    } catch (e) {
                        console.error('Error loading stats:', e);
                    }
                }
                
                async function loadStreamers() {
                    try {
                        const res = await fetch('/api/streamers');
                        const streamers = await res.json();
                        
                        const html = streamers.map(s => `
                            <div class="streamer-item">
                                <div>
                                    ${s.is_live ? '<span class="live-indicator"></span>' : ''}
                                    <strong>${s.name}</strong>
                                </div>
                                <div style="text-align: right;">
                                    <div>${(s.points_earned || 0).toLocaleString()} pts</div>
                                    <div class="status">
                                        ${s.predictions_count || 0} bets | ${(s.win_rate || 0).toFixed(0)}% WR
                                    </div>
                                </div>
                            </div>
                        `).join('');
                        
                        document.getElementById('streamer-list').innerHTML = html || 'No data';
                    } catch (e) {
                        console.error('Error loading streamers:', e);
                    }
                }
                
                async function loadRecentBets() {
                    try {
                        const res = await fetch('/api/recent_bets');
                        const bets = await res.json();
                        
                        const html = bets.map(b => `
                            <div class="bet-item">
                                <div>
                                    <strong>${b.streamer}</strong><br>
                                    <small>${b.title}</small>
                                </div>
                                <div style="text-align: right;">
                                    <div>${b.choice || 'N/A'}</div>
                                    <div class="status">${b.result || 'pending'}</div>
                                </div>
                            </div>
                        `).join('');
                        
                        document.getElementById('recent-bets').innerHTML = html || 'No bets';
                    } catch (e) {
                        console.error('Error loading bets:', e);
                    }
                }
                
                socket.on('new_prediction', (data) => {
                    console.log('New prediction:', data);
                    loadStats();
                    loadRecentBets();
                });
                
                socket.on('stats_updated', () => {
                    loadStats();
                    loadStreamers();
                    loadRecentBets();
                });
                
                // Refresh toutes les 10 secondes
                setInterval(loadStats, 10000);
                setInterval(loadStreamers, 30000);
                setInterval(loadRecentBets, 30000);
                
                // Charge au démarrage
                loadStats();
                loadStreamers();
                loadRecentBets();
            </script>
        </body>
        </html>
        """

    def _get_global_stats(self) -> Dict[str, Any]:
        """Récupère les stats globales."""
        try:
            total_points = 0
            active_streams = 0
            
            if self.bot and hasattr(self.bot, 'streamers'):
                for streamer in self.bot.streamers:
                    if hasattr(streamer, 'channel_points'):
                        total_points += streamer.channel_points
                    if hasattr(streamer, 'is_online') and streamer.is_online:
                        active_streams += 1
            
            # Stats depuis le profiler
            predictions_today = 0
            predictions_won = 0
            
            if self.profiler:
                try:
                    recent = self.profiler.get_recent_predictions(limit=100)
                    today = datetime.now().date()
                    for pred in recent:
                        pred_date = datetime.fromisoformat(pred['timestamp']).date()
                        if pred_date == today:
                            predictions_today += 1
                            if pred.get('payout', 0) > 0:
                                predictions_won += 1
                except Exception as e:
                    logger.debug(f"Erreur récupération stats profiler: {e}")
            
            win_rate = f"{(predictions_won / predictions_today * 100):.1f}%" if predictions_today > 0 else "0%"
            
            return {
                'total_points': total_points,
                'active_streams': active_streams,
                'today_profit': 0,  # À calculer depuis l'historique
                'predictions': {
                    'today': predictions_today,
                    'won': predictions_won,
                    'win_rate': win_rate
                }
            }
        except Exception as e:
            logger.error(f"Erreur récupération stats globales: {e}")
            return {'error': str(e)}

    def _get_streamers_stats(self) -> List[Dict[str, Any]]:
        """Récupère les stats par streamer."""
        streamers = []
        
        try:
            if self.bot and hasattr(self.bot, 'streamers'):
                for streamer in self.bot.streamers:
                    profile = None
                    if self.profiler:
                        try:
                            profile = self.profiler.get_streamer_profile(str(streamer.channel_id))
                        except:
                            pass
                    
                    streamers.append({
                        'name': streamer.username if hasattr(streamer, 'username') else 'Unknown',
                        'is_live': streamer.is_online if hasattr(streamer, 'is_online') else False,
                        'points_earned': streamer.channel_points if hasattr(streamer, 'channel_points') else 0,
                        'predictions_count': profile['stats']['total_predictions'] if profile and profile.get('stats') else 0,
                        'win_rate': profile['stats']['crowd_accuracy'] if profile and profile.get('stats') else 0
                    })
            
            # Trie par rentabilité
            streamers.sort(key=lambda x: x['points_earned'], reverse=True)
        except Exception as e:
            logger.error(f"Erreur récupération stats streamers: {e}")
        
        return streamers

    def _get_recent_bets(self) -> List[Dict[str, Any]]:
        """Récupère les derniers bets."""
        bets = []
        
        try:
            if self.profiler:
                recent = self.profiler.get_recent_predictions(limit=20)
                for row in recent:
                    bets.append({
                        'streamer': row.get('streamer_name', 'Unknown'),
                        'title': row.get('prediction_title', ''),
                        'choice': f"Option {row.get('bet_choice', 'N/A') + 1}" if row.get('bet_choice') is not None else 'N/A',
                        'result': 'win' if row.get('payout', 0) > 0 else ('pending' if row.get('winner') is None else 'loss'),
                        'time': row.get('timestamp', '')
                    })
        except Exception as e:
            logger.error(f"Erreur récupération bets récents: {e}")
        
        return bets

    def _get_active_predictions(self) -> List[Dict[str, Any]]:
        """Récupère les prédictions actives."""
        predictions = []
        
        try:
            if self.bot and hasattr(self.bot, 'events_predictions'):
                for event_id, event in self.bot.events_predictions.items():
                    predictions.append({
                        'id': event_id,
                        'streamer': event.streamer.username if hasattr(event.streamer, 'username') else 'Unknown',
                        'title': event.title,
                        'status': event.status,
                        'bet_placed': event.bet_placed
                    })
        except Exception as e:
            logger.error(f"Erreur récupération prédictions actives: {e}")
        
        return predictions

    def emit_new_prediction(self, prediction_data: Dict[str, Any]):
        """Envoie une notification WebSocket quand nouvelle prédiction."""
        if not self.available:
            return
        
        try:
            self.socketio.emit('new_prediction', {
                'streamer': prediction_data.get('streamer', 'Unknown'),
                'title': prediction_data.get('title', ''),
                'options': [o.get('title', '') for o in prediction_data.get('outcomes', [])]
            })
        except Exception as e:
            logger.debug(f"Erreur emission WebSocket: {e}")

    def emit_update(self):
        """Émet une mise à jour des stats."""
        if not self.available:
            return
        
        try:
            self.socketio.emit('stats_updated')
        except Exception as e:
            logger.debug(f"Erreur emission update: {e}")

    def run(self, debug: bool = False):
        """Lance le serveur web."""
        if not self.available:
            logger.error("Dashboard non disponible (Flask non installé)")
            return
        
        logger.info(f"🌐 Dashboard démarré sur http://{self.host}:{self.port}")
        try:
            self.socketio.run(self.app, host=self.host, port=self.port, debug=debug, allow_unsafe_werkzeug=True)
        except Exception as e:
            logger.error(f"Erreur démarrage dashboard: {e}")

    def run_async(self, debug: bool = False):
        """Lance le serveur web en arrière-plan."""
        if not self.available:
            return
        
        import threading
        
        def run_server():
            try:
                self.socketio.run(self.app, host=self.host, port=self.port, debug=debug, 
                                allow_unsafe_werkzeug=True, use_reloader=False)
            except Exception as e:
                logger.error(f"Erreur serveur dashboard: {e}")
        
        server_thread = threading.Thread(target=run_server, daemon=True, name="DashboardServer")
        server_thread.start()
        logger.info(f"🌐 Dashboard démarré en arrière-plan sur http://{self.host}:{self.port}")

