import json
import logging
import os
from datetime import datetime
from pathlib import Path
from threading import Thread

import pandas as pd
from flask import Flask, Response, cli, render_template, request, jsonify

from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.utils import download_file

cli.show_server_banner = lambda *_: None
logger = logging.getLogger(__name__)

# Configuration globale modifiable via le dashboard
DASHBOARD_SETTINGS_FILE = None

def get_dashboard_settings_path():
    global DASHBOARD_SETTINGS_FILE
    if DASHBOARD_SETTINGS_FILE is None:
        data_dir = os.getenv("DATA_DIR", ".")
        DASHBOARD_SETTINGS_FILE = os.path.join(data_dir, "dashboard_settings.json")
    return DASHBOARD_SETTINGS_FILE

DEFAULT_DASHBOARD_SETTINGS = {
    "bot_enabled": True,
    "betting_enabled": True,
    "stealth_mode": True,
    "bet_percentage": 5,
    "max_points": 30000,
    "min_balance": 5000,
    "min_voters": 30,
    "delay_seconds": 10,
    "sound_notifications": True,
    "auto_claim_bonus": True,
    "follow_raid": True,
    "claim_drops": True,
    "watch_streak": True
}

def load_dashboard_settings():
    """Charge les paramètres du dashboard depuis le fichier JSON"""
    path = get_dashboard_settings_path()
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                saved = json.load(f)
                # Fusionner avec les defaults pour les nouvelles clés
                return {**DEFAULT_DASHBOARD_SETTINGS, **saved}
    except Exception as e:
        logger.error(f"Error loading dashboard settings: {e}")
    return DEFAULT_DASHBOARD_SETTINGS.copy()

def save_dashboard_settings(settings):
    """Sauvegarde les paramètres du dashboard"""
    path = get_dashboard_settings_path()
    try:
        with open(path, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving dashboard settings: {e}")
        return False

# Variable globale pour accéder aux settings depuis d'autres modules
_current_settings = None

def get_current_settings():
    global _current_settings
    if _current_settings is None:
        _current_settings = load_dashboard_settings()
    return _current_settings

def update_current_settings(new_settings):
    global _current_settings
    _current_settings = new_settings


def streamers_available():
    path = Settings.analytics_path
    return [
        f
        for f in os.listdir(path)
        if os.path.isfile(os.path.join(path, f)) and f.endswith(".json")
    ]


def aggregate(df, freq="30Min"):
    df_base_events = df[(df.z == "Watch") | (df.z == "Claim")]
    df_other_events = df[(df.z != "Watch") & (df.z != "Claim")]

    be = df_base_events.groupby(
        [pd.Grouper(freq=freq, key="datetime"), "z"]).max()
    be = be.reset_index()

    oe = df_other_events.groupby(
        [pd.Grouper(freq=freq, key="datetime"), "z"]).max()
    oe = oe.reset_index()

    result = pd.concat([be, oe])
    return result


def filter_datas(start_date, end_date, datas):
    # Note: https://stackoverflow.com/questions/4676195/why-do-i-need-to-multiply-unix-timestamps-by-1000-in-javascript
    start_date = (
        datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000
        if start_date is not None
        else 0
    )
    end_date = (
        datetime.strptime(end_date, "%Y-%m-%d")
        if end_date is not None
        else datetime.now()
    ).replace(hour=23, minute=59, second=59).timestamp() * 1000

    original_series = datas["series"]

    if "series" in datas:
        df = pd.DataFrame(datas["series"])
        df["datetime"] = pd.to_datetime(df.x // 1000, unit="s")

        df = df[(df.x >= start_date) & (df.x <= end_date)]

        datas["series"] = (
            df.drop(columns="datetime")
            .sort_values(by=["x", "y"], ascending=True)
            .to_dict("records")
        )
    else:
        datas["series"] = []

    # If no data is found within the timeframe, that usually means the streamer hasn't streamed within that timeframe
    # We create a series that shows up as a straight line on the dashboard, with 'No Stream' as labels
    if len(datas["series"]) == 0:
        new_end_date = start_date
        new_start_date = 0
        df = pd.DataFrame(original_series)
        df["datetime"] = pd.to_datetime(df.x // 1000, unit="s")

        # Attempt to get the last known balance from before the provided timeframe
        df = df[(df.x >= new_start_date) & (df.x <= new_end_date)]
        last_balance = df.drop(columns="datetime").sort_values(
            by=["x", "y"], ascending=True).to_dict("records")[-1]['y']

        datas["series"] = [{'x': start_date, 'y': last_balance, 'z': 'No Stream'}, {
            'x': end_date, 'y': last_balance, 'z': 'No Stream'}]

    if "annotations" in datas:
        df = pd.DataFrame(datas["annotations"])
        df["datetime"] = pd.to_datetime(df.x // 1000, unit="s")

        df = df[(df.x >= start_date) & (df.x <= end_date)]

        datas["annotations"] = (
            df.drop(columns="datetime")
            .sort_values(by="x", ascending=True)
            .to_dict("records")
        )
    else:
        datas["annotations"] = []

    return datas


def read_json(streamer, return_response=True):
    start_date = request.args.get("startDate", type=str)
    end_date = request.args.get("endDate", type=str)

    path = Settings.analytics_path
    streamer = streamer if streamer.endswith(".json") else f"{streamer}.json"

    # Check if the file exists before attempting to read it
    if not os.path.exists(os.path.join(path, streamer)):
        error_message = f"File '{streamer}' not found."
        logger.error(error_message)
        if return_response:
            return Response(json.dumps({"error": error_message}), status=404, mimetype="application/json")
        else:
            return {"error": error_message}

    try:
        with open(os.path.join(path, streamer), 'r') as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        error_message = f"Error decoding JSON in file '{streamer}': {str(e)}"
        logger.error(error_message)
        if return_response:
            return Response(json.dumps({"error": error_message}), status=500, mimetype="application/json")
        else:
            return {"error": error_message}

    # Handle filtering data, if applicable
    filtered_data = filter_datas(start_date, end_date, data)
    if return_response:
        return Response(json.dumps(filtered_data), status=200, mimetype="application/json")
    else:
        return filtered_data


def get_challenge_points(streamer):
    datas = read_json(streamer, return_response=False)
    if "series" in datas and datas["series"]:
        return datas["series"][-1]["y"]
    return 0  # Default value when 'series' key is not found or empty


def get_last_activity(streamer):
    datas = read_json(streamer, return_response=False)
    if "series" in datas and datas["series"]:
        return datas["series"][-1]["x"]
    return 0  # Default value when 'series' key is not found or empty


def json_all():
    return Response(
        json.dumps(
            [
                {
                    "name": streamer.strip(".json"),
                    "data": read_json(streamer, return_response=False),
                }
                for streamer in streamers_available()
            ]
        ),
        status=200,
        mimetype="application/json",
    )


def index(refresh=5, days_ago=7):
    # Nouveau dashboard moderne par défaut
    return render_template("dashboard.html")


def streamers():
    return Response(
        json.dumps(
            [
                {"name": s, "points": get_challenge_points(
                    s), "last_activity": get_last_activity(s)}
                for s in sorted(streamers_available())
            ]
        ),
        status=200,
        mimetype="application/json",
    )


def download_assets(assets_folder, required_files):
    Path(assets_folder).mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading assets to {assets_folder}")

    for f in required_files:
        if os.path.isfile(os.path.join(assets_folder, f)) is False:
            if (
                download_file(os.path.join("assets", f),
                              os.path.join(assets_folder, f))
                is True
            ):
                logger.info(f"Downloaded {f}")


def check_assets():
    required_files = [
        "banner.png",
        "charts.html",
        "script.js",
        "style.css",
        "dark-theme.css",
    ]
    assets_folder = os.path.join(Path().absolute(), "assets")
    if os.path.isdir(assets_folder) is False:
        logger.info(f"Assets folder not found at {assets_folder}")
        download_assets(assets_folder, required_files)
    else:
        for f in required_files:
            if os.path.isfile(os.path.join(assets_folder, f)) is False:
                logger.info(f"Missing file {f} in {assets_folder}")
                download_assets(assets_folder, required_files)
                break

last_sent_log_index = 0

class AnalyticsServer(Thread):
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        refresh: int = 5,
        days_ago: int = 7,
        username: str = None
    ):
        super(AnalyticsServer, self).__init__()

        check_assets()

        self.host = host
        self.port = port
        self.refresh = refresh
        self.days_ago = days_ago
        self.username = username

        def generate_log():
            global last_sent_log_index  # Use the global variable

            # Get the last received log index from the client request parameters
            last_received_index = int(request.args.get("lastIndex", last_sent_log_index))

            logs_path = os.path.join(Path().absolute(), "logs")
            log_file_path = os.path.join(logs_path, f"{username}.log")
            try:
                with open(log_file_path, "r", encoding="utf-8") as log_file:
                    log_content = log_file.read()

                # Extract new log entries since the last received index
                new_log_entries = log_content[last_received_index:]
                last_sent_log_index = len(log_content)  # Update the last sent index

                return Response(new_log_entries, status=200, mimetype="text/plain")

            except FileNotFoundError:
                return Response("Log file not found.", status=404, mimetype="text/plain")

        self.app = Flask(
            __name__,
            template_folder=os.path.join(Path().absolute(), "assets"),
            static_folder=os.path.join(Path().absolute(), "assets"),
        )
        self.app.add_url_rule(
            "/",
            "index",
            index,
            defaults={"refresh": refresh, "days_ago": days_ago},
            methods=["GET"],
        )
        self.app.add_url_rule("/streamers", "streamers",
                              streamers, methods=["GET"])
        self.app.add_url_rule(
            "/json/<string:streamer>", "json", read_json, methods=["GET"]
        )
        self.app.add_url_rule("/json_all", "json_all",
                              json_all, methods=["GET"])
        self.app.add_url_rule(
            "/log", "log", generate_log, methods=["GET"])
        
        # Nouvelle route pour le dashboard moderne
        @self.app.route("/dashboard")
        def dashboard():
            return render_template("dashboard.html")
        
        # Ancienne route pour les graphiques détaillés
        @self.app.route("/charts")
        def charts():
            return render_template("charts.html", refresh=self.refresh * 60 * 1000, daysAgo=self.days_ago)
        
        # Route pour servir bot_data.json
        @self.app.route("/bot_data.json")
        def bot_data():
            import os
            data_dir = os.getenv("DATA_DIR", ".")
            bot_data_path = os.path.join(data_dir, "bot_data.json")
            try:
                if os.path.exists(bot_data_path):
                    with open(bot_data_path, 'r') as f:
                        return Response(f.read(), status=200, mimetype="application/json")
                else:
                    return Response(json.dumps({"streamers": {}}), status=200, mimetype="application/json")
            except Exception as e:
                logger.error(f"Error reading bot_data.json: {e}")
                return Response(json.dumps({"streamers": {}}), status=200, mimetype="application/json")
        
        # ===== API de contrôle du Dashboard =====
        
        @self.app.route("/api/settings", methods=["GET"])
        def api_get_settings():
            """Récupère tous les paramètres"""
            settings = load_dashboard_settings()
            return jsonify(settings)
        
        @self.app.route("/api/settings", methods=["POST"])
        def api_update_settings():
            """Met à jour les paramètres"""
            try:
                new_settings = request.get_json()
                current = load_dashboard_settings()
                current.update(new_settings)
                if save_dashboard_settings(current):
                    update_current_settings(current)
                    logger.info(f"Dashboard settings updated: {new_settings}")
                    return jsonify({"success": True, "settings": current})
                else:
                    return jsonify({"success": False, "error": "Failed to save"}), 500
            except Exception as e:
                logger.error(f"Error updating settings: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route("/api/settings/reset", methods=["POST"])
        def api_reset_settings():
            """Réinitialise tous les paramètres"""
            if save_dashboard_settings(DEFAULT_DASHBOARD_SETTINGS):
                update_current_settings(DEFAULT_DASHBOARD_SETTINGS.copy())
                return jsonify({"success": True, "settings": DEFAULT_DASHBOARD_SETTINGS})
            return jsonify({"success": False}), 500
        
        @self.app.route("/api/stats/reset", methods=["POST"])
        def api_reset_stats():
            """Réinitialise les statistiques (compteurs à zéro)"""
            try:
                data_dir = os.getenv("DATA_DIR", ".")
                bot_data_path = os.path.join(data_dir, "bot_data.json")
                
                if os.path.exists(bot_data_path):
                    with open(bot_data_path, 'r') as f:
                        data = json.load(f)
                    
                    for name, s in data.get("streamers", {}).items():
                        balance = s.get("balance", 0)
                        s["starting_balance"] = balance
                        s["session_points"] = 0
                        s["watch_points"] = 0
                        s["bonus_points"] = 0
                        s["bets_placed"] = 0
                        s["bets_won"] = 0
                        s["bets_lost"] = 0
                        s["bet_profits"] = 0
                        s["bet_losses"] = 0
                        s["total_earned"] = 0
                    
                    with open(bot_data_path, 'w') as f:
                        json.dump(data, f, indent=2)
                    
                    logger.info("Stats reset from dashboard")
                    return jsonify({"success": True, "message": "Stats reset successfully"})
                
                return jsonify({"success": True, "message": "No data to reset"})
            except Exception as e:
                logger.error(f"Error resetting stats: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route("/api/streamer/<streamer_name>/toggle", methods=["POST"])
        def api_toggle_streamer(streamer_name):
            """Active/désactive un streamer spécifique"""
            try:
                data_dir = os.getenv("DATA_DIR", ".")
                bot_data_path = os.path.join(data_dir, "bot_data.json")
                
                if os.path.exists(bot_data_path):
                    with open(bot_data_path, 'r') as f:
                        data = json.load(f)
                    
                    if streamer_name in data.get("streamers", {}):
                        current = data["streamers"][streamer_name].get("enabled", True)
                        data["streamers"][streamer_name]["enabled"] = not current
                        
                        with open(bot_data_path, 'w') as f:
                            json.dump(data, f, indent=2)
                        
                        return jsonify({
                            "success": True, 
                            "streamer": streamer_name,
                            "enabled": not current
                        })
                
                return jsonify({"success": False, "error": "Streamer not found"}), 404
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route("/api/bets/history", methods=["GET"])
        def api_bet_history():
            """Récupère l'historique des paris"""
            try:
                data_dir = os.getenv("DATA_DIR", ".")
                bot_data_path = os.path.join(data_dir, "bot_data.json")
                
                if os.path.exists(bot_data_path):
                    with open(bot_data_path, 'r') as f:
                        content = f.read()
                    
                    # Vérifier si le contenu est vide
                    if not content.strip():
                        return jsonify({"bets": []})
                    
                    data = json.loads(content)
                    bets = data.get("bet_history", [])
                    # Retourne les 50 derniers paris
                    return jsonify({"bets": bets[-50:][::-1]})
                
                return jsonify({"bets": []})
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON in bet_history: {e}")
                return jsonify({"bets": [], "error": "JSON parsing error, file may be updating"})
            except Exception as e:
                logger.error(f"Error getting bet history: {e}")
                return jsonify({"bets": []})
        
        @self.app.route("/api/bets/active", methods=["GET"])
        def api_active_bets():
            """Récupère les paris en cours"""
            try:
                data_dir = os.getenv("DATA_DIR", ".")
                bot_data_path = os.path.join(data_dir, "bot_data.json")
                
                if os.path.exists(bot_data_path):
                    with open(bot_data_path, 'r') as f:
                        content = f.read()
                    
                    # Vérifier si le contenu est vide
                    if not content.strip():
                        return jsonify({"predictions": []})
                    
                    data = json.loads(content)
                    active = data.get("active_predictions", [])
                    return jsonify({"predictions": active})
                
                return jsonify({"predictions": []})
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON in active_bets: {e}")
                return jsonify({"predictions": [], "error": "JSON parsing error, file may be updating"})
            except Exception as e:
                logger.error(f"Error getting active bets: {e}")
                return jsonify({"predictions": []})
        
        @self.app.route("/api/recovery_scan", methods=["POST"])
        def api_recovery_scan():
            """
            Lance un scan de récupération pour synchroniser les prédictions.
            Scanne tous les streams en ligne pour détecter les prédictions manquées.
            """
            try:
                from TwitchChannelPointsMiner.classes.PredictionScanner import get_scanner_instance
                from datetime import datetime as dt
                import requests
                
                data_dir = os.getenv("DATA_DIR", ".")
                bot_data_path = os.path.join(data_dir, "bot_data.json")
                
                # Charger les données
                if not os.path.exists(bot_data_path):
                    return jsonify({'success': False, 'error': 'Pas de données'})
                
                with open(bot_data_path, 'r') as f:
                    data = json.load(f)
                
                # Récupérer les streamers en ligne depuis bot_data.json
                streamers_data = data.get('streamers', {})
                online_streamers = [
                    {'name': name, 'data': sdata}
                    for name, sdata in streamers_data.items()
                    if sdata.get('online', False)
                ]
                
                logger.info(f"🔍 Scan de récupération: {len(online_streamers)} streams en ligne")
                
                # Essayer d'utiliser le scanner si disponible
                scanner = get_scanner_instance()
                
                if scanner and hasattr(scanner, 'twitch'):
                    # Scanner disponible - faire un scan complet
                    result = scanner.recovery_scan()
                    return jsonify(result)
                
                # Scanner non disponible - faire un nettoyage basique
                logger.warning("Scanner non disponible, nettoyage basique...")
                
                current_active = data.get('active_predictions', [])
                cleaned = []
                removed = []
                
                for pred in current_active:
                    # Garder si on a un pari placé (en attente de résultat)
                    if pred.get('our_bet'):
                        cleaned.append(pred)
                    # Garder si la prédiction est récente (moins de 10 min)
                    elif pred.get('created_at'):
                        try:
                            created = dt.strptime(pred['created_at'], '%Y-%m-%d %H:%M:%S')
                            age_minutes = (dt.now() - created).total_seconds() / 60
                            if age_minutes < 10:
                                cleaned.append(pred)
                            else:
                                removed.append(pred.get('title', 'Unknown'))
                        except:
                            removed.append(pred.get('title', 'Unknown'))
                    else:
                        removed.append(pred.get('title', 'Unknown'))
                
                data['active_predictions'] = cleaned
                
                with open(bot_data_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return jsonify({
                    'success': True,
                    'mode': 'basic_cleanup',
                    'streams_scanned': len(online_streamers),
                    'removed': removed,
                    'total_active': len(cleaned),
                    'message': f'{len(online_streamers)} streams en ligne - Nettoyage effectué ({len(removed)} supprimées)'
                })
                
            except Exception as e:
                logger.error(f"Error during recovery scan: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route("/api/scanner/status", methods=["GET"])
        def api_scanner_status():
            """Récupère le status du scanner."""
            try:
                from TwitchChannelPointsMiner.classes.PredictionScanner import get_scanner_instance
                
                scanner = get_scanner_instance()
                
                if scanner:
                    stats = scanner.get_statistics()
                    return jsonify({
                        'available': True,
                        **stats
                    })
                
                return jsonify({
                    'available': False,
                    'message': 'Scanner non initialisé'
                })
            except Exception as e:
                return jsonify({
                    'available': False,
                    'error': str(e)
                })

    def run(self):
        logger.info(
            f"Analytics running on http://{self.host}:{self.port}/",
            extra={"emoji": ":globe_with_meridians:"},
        )
        self.app.run(host=self.host, port=self.port,
                     threaded=True, debug=False)
