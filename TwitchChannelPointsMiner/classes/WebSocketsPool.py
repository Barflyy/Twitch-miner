import json
import logging
import os
import random
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Timer, Lock

from dateutil import parser

from TwitchChannelPointsMiner.classes.entities.CommunityGoal import CommunityGoal
from TwitchChannelPointsMiner.classes.entities.EventPrediction import EventPrediction
from TwitchChannelPointsMiner.classes.entities.Message import Message
from TwitchChannelPointsMiner.classes.entities.Raid import Raid
from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.classes.TwitchWebSocket import TwitchWebSocket
from TwitchChannelPointsMiner.constants import WEBSOCKET
from TwitchChannelPointsMiner.utils import (
    get_streamer_index,
    internet_connection_available,
)

logger = logging.getLogger(__name__)

# Lock pour éviter les problèmes de concurrence sur bot_data.json
_bot_data_lock = Lock()


def add_bet_to_history(bet_data: dict):
    """
    Ajoute un pari à l'historique dans bot_data.json.
    
    Args:
        bet_data: Dict avec les infos du pari:
            - streamer: Nom du streamer
            - title: Titre de la prédiction
            - choice: Choix fait (index)
            - choice_title: Titre du choix
            - amount: Montant misé
            - odds: Cote du pari
            - result: 'win', 'lose', 'refund', 'pending'
            - profit: Profit/perte
            - timestamp: Horodatage
    """
    try:
        with _bot_data_lock:
            data_dir = os.getenv("DATA_DIR", ".")
            bot_data_path = os.path.join(data_dir, "bot_data.json")
            
            if os.path.exists(bot_data_path):
                with open(bot_data_path, 'r') as f:
                    data = json.load(f)
            else:
                data = {'streamers': {}, 'bet_history': [], 'active_predictions': []}
            
            if 'bet_history' not in data:
                data['bet_history'] = []
            
            # Ajouter le pari à l'historique
            data['bet_history'].append(bet_data)
            
            # Garder seulement les 100 derniers paris
            if len(data['bet_history']) > 100:
                data['bet_history'] = data['bet_history'][-100:]
            
            with open(bot_data_path, 'w') as f:
                json.dump(data, f, indent=2)
                
    except Exception as e:
        logger.debug(f"Erreur ajout historique pari: {e}")


def update_active_prediction(prediction_data: dict, remove: bool = False):
    """
    Met à jour ou supprime une prédiction active.
    
    Args:
        prediction_data: Dict avec les infos:
            - event_id: ID de l'événement
            - streamer: Nom du streamer
            - title: Titre
            - outcomes: Liste des choix avec leurs stats
            - time_remaining: Temps restant
            - our_bet: Notre pari (si placé)
        remove: Si True, supprime la prédiction
    """
    try:
        with _bot_data_lock:
            data_dir = os.getenv("DATA_DIR", ".")
            bot_data_path = os.path.join(data_dir, "bot_data.json")
            
            if os.path.exists(bot_data_path):
                with open(bot_data_path, 'r') as f:
                    data = json.load(f)
            else:
                data = {'streamers': {}, 'bet_history': [], 'active_predictions': []}
            
            if 'active_predictions' not in data:
                data['active_predictions'] = []
            
            event_id = prediction_data.get('event_id')
            
            # Supprimer l'ancienne entrée si elle existe
            data['active_predictions'] = [
                p for p in data['active_predictions'] 
                if p.get('event_id') != event_id
            ]
            
            # Ajouter la nouvelle entrée si pas remove
            if not remove:
                data['active_predictions'].append(prediction_data)
            
            with open(bot_data_path, 'w') as f:
                json.dump(data, f, indent=2)
                
    except Exception as e:
        logger.debug(f"Erreur mise à jour prédiction active: {e}")


def update_bot_data(streamer_name: str, updates: dict):
    """
    Met à jour bot_data.json de manière thread-safe.
    
    Args:
        streamer_name: Nom du streamer (lowercase)
        updates: Dict avec les champs à mettre à jour:
            - balance: Solde actuel
            - online: État en ligne
            - session_points: Points gagnés cette session (incrementer)
            - watch_points: Points de watch (incrementer)
            - bonus_points: Points de bonus (incrementer)
            - bets_placed: Paris placés (incrementer)
            - bets_won: Paris gagnés (incrementer)
            - bets_lost: Paris perdus (incrementer)
            - bet_profits: Profits des paris (incrementer)
            - bet_losses: Pertes des paris (incrementer)
    """
    try:
        with _bot_data_lock:
            data_dir = os.getenv("DATA_DIR", ".")
            bot_data_path = os.path.join(data_dir, "bot_data.json")
            
            # Charger les données existantes
            if os.path.exists(bot_data_path):
                with open(bot_data_path, 'r') as f:
                    data = json.load(f)
            else:
                data = {'streamers': {}, 'session_start': time.time()}
            
            # S'assurer que streamers existe
            if 'streamers' not in data:
                data['streamers'] = {}
            
            streamer_key = streamer_name.lower()
            
            # Créer l'entrée si elle n'existe pas
            if streamer_key not in data['streamers']:
                data['streamers'][streamer_key] = {
                    'balance': 0,
                    'starting_balance': 0,
                    'online': False,
                    'session_points': 0,
                    'watch_points': 0,
                    'bonus_points': 0,
                    'bets_placed': 0,
                    'bets_won': 0,
                    'bets_lost': 0,
                    'bet_profits': 0,
                    'bet_losses': 0,
                    'total_earned': 0,
                    'last_update': None
                }
            
            streamer_data = data['streamers'][streamer_key]
            
            # Mettre à jour les champs
            for key, value in updates.items():
                if key == 'balance':
                    streamer_data['balance'] = value
                    # Calculer session_points comme différence avec starting_balance
                    starting = streamer_data.get('starting_balance', value)
                    streamer_data['session_points'] = value - starting
                elif key == 'online':
                    streamer_data['online'] = value
                elif key == 'starting_balance':
                    streamer_data['starting_balance'] = value
                elif key in ['session_points', 'watch_points', 'bonus_points', 
                           'bets_placed', 'bets_won', 'bets_lost', 
                           'bet_profits', 'bet_losses', 'total_earned']:
                    # Incrémenter ces valeurs
                    current = streamer_data.get(key, 0)
                    streamer_data[key] = current + value
            
            # Timestamp de mise à jour
            streamer_data['last_update'] = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Sauvegarder
            with open(bot_data_path, 'w') as f:
                json.dump(data, f, indent=2)
                
    except Exception as e:
        logger.debug(f"Erreur mise à jour bot_data.json: {e}")


class WebSocketsPool:
    __slots__ = ["ws", "twitch", "streamers", "events_predictions"]

    def __init__(self, twitch, streamers, events_predictions):
        self.ws = []
        self.twitch = twitch
        self.streamers = streamers
        self.events_predictions = events_predictions

    """
    API Limits
    - Clients can listen to up to 50 topics per connection. Trying to listen to more topics will result in an error message.
    - We recommend that a single client IP address establishes no more than 10 simultaneous connections.
    The two limits above are likely to be relaxed for approved third-party applications, as we start to better understand third-party requirements.
    """

    def submit(self, topic):
        # Check if we need to create a new WebSocket instance
        if self.ws == [] or len(self.ws[-1].topics) >= 50:
            self.ws.append(self.__new(len(self.ws)))
            self.__start(-1)

        self.__submit(-1, topic)

    def __submit(self, index, topic):
        # Topic in topics should never happen. Anyway prevent any types of duplicates
        if topic not in self.ws[index].topics:
            self.ws[index].topics.append(topic)

        if self.ws[index].is_opened is False:
            self.ws[index].pending_topics.append(topic)
        else:
            self.ws[index].listen(topic, self.twitch.twitch_login.get_auth_token())

    def __new(self, index):
        return TwitchWebSocket(
            index=index,
            parent_pool=self,
            url=WEBSOCKET,
            on_message=WebSocketsPool.on_message,
            on_open=WebSocketsPool.on_open,
            on_error=WebSocketsPool.on_error,
            on_close=WebSocketsPool.on_close
            # on_close=WebSocketsPool.handle_reconnection, # Do nothing.
        )

    def __start(self, index):
        # Stagger WebSocket startups to avoid simultaneous pings
        # With 40+ connections, starting all at once causes ping storms
        if index > 0:
            stagger_delay = min(index * 5, 30)  # Max 30 second stagger
            logger.info(f"#{index} - Staggering WebSocket start by {stagger_delay}s to reduce network congestion")
            time.sleep(stagger_delay)
        
        if Settings.disable_ssl_cert_verification is True:
            import ssl

            thread_ws = Thread(
                target=lambda: self.ws[index].run_forever(
                    sslopt={"cert_reqs": ssl.CERT_NONE}
                )
            )
            logger.warn("SSL certificate verification is disabled! Be aware!")
        else:
            thread_ws = Thread(target=lambda: self.ws[index].run_forever())
        thread_ws.daemon = True
        thread_ws.name = f"WebSocket #{self.ws[index].index}"
        thread_ws.start()

    def end(self):
        for index in range(0, len(self.ws)):
            self.ws[index].forced_close = True
            self.ws[index].close()

    @staticmethod
    def on_open(ws):
        def run():
            ws.is_opened = True
            # Délai initial randomisé pour éviter les pings simultanés
            time.sleep(random.uniform(1, 5))
            ws.ping()

            for topic in ws.pending_topics:
                ws.listen(topic, ws.twitch.twitch_login.get_auth_token())
                # Petit délai entre chaque subscribe pour éviter le rate limiting
                time.sleep(random.uniform(0.1, 0.3))

            while ws.is_closed is False:
                # Else: the ws is currently in reconnecting phase, you can't do ping or other operation.
                # Probably this ws will be closed very soon with ws.is_closed = True
                if ws.is_reconnecting is False:
                    try:
                        ws.ping()  # We need ping for keep the connection alive
                    except Exception as e:
                        logger.debug(f"#{ws.index} - Ping failed: {e}")
                        break
                    
                    # Ping moins fréquent (30-60s au lieu de 25-30s) pour réduire la charge réseau
                    time.sleep(random.uniform(30, 60))

                    if ws.elapsed_last_pong() > 5:
                        logger.info(
                            f"#{ws.index} - The last PONG was received more than 5 minutes ago"
                        )
                        WebSocketsPool.handle_reconnection(ws)

        thread_ws = Thread(target=run)
        thread_ws.daemon = True
        thread_ws.start()

    @staticmethod
    def on_error(ws, error):
        # Connection lost | [WinError 10054] An existing connection was forcibly closed by the remote host
        # Connection already closed | Connection is already closed (raise WebSocketConnectionClosedException)
        error_str = str(error)
        
        # Erreurs communes qui ne nécessitent pas de log d'erreur complet
        known_transient_errors = [
            "ping pong failed",
            "Broken pipe",
            "BAD_LENGTH",
            "Connection reset",
            "Connection refused",
            "timed out",
            "EOF occurred"
        ]
        
        is_transient = any(err in error_str for err in known_transient_errors)
        
        if is_transient:
            # Ne pas spammer les logs pour les erreurs transitoires connues
            logger.debug(f"#{ws.index} - WebSocket transient error: {error_str}")
        else:
            logger.error(f"#{ws.index} - WebSocket error: {error}")

    @staticmethod
    def on_close(ws, close_status_code, close_reason):
        # Log moins verbeux pour les fermetures
        logger.debug(f"#{ws.index} - WebSocket closed (code: {close_status_code})")
        # On close please reconnect automatically
        WebSocketsPool.handle_reconnection(ws)

    @staticmethod
    def handle_reconnection(ws):
        # Reconnect only if ws.is_reconnecting is False to prevent more than 1 ws from being created
        if ws.is_reconnecting is False:
            # Close the current WebSocket.
            ws.is_closed = True
            ws.keep_running = False
            # Reconnect only if ws.forced_close is False (replace the keep_running)

            # Set the current socket as reconnecting status
            # So the external ping check will be locked
            ws.is_reconnecting = True

            if ws.forced_close is False:
                # Délai basé sur l'index pour éviter les reconnexions simultanées
                # ws #0 attend 30s, ws #10 attend 35s, ws #20 attend 40s, etc.
                base_delay = 30
                stagger_delay = (ws.index % 20) * 3  # 0-60s selon l'index
                total_delay = base_delay + stagger_delay
                
                logger.debug(
                    f"#{ws.index} - Reconnecting in ~{total_delay}s"
                )
                time.sleep(total_delay)

                while internet_connection_available() is False:
                    random_sleep = random.randint(1, 3)
                    logger.warning(
                        f"#{ws.index} - No internet connection available! Retry after {random_sleep}m"
                    )
                    time.sleep(random_sleep * 60)

                # Why not create a new ws on the same array index? Let's try.
                self = ws.parent_pool
                # Create a new connection.
                self.ws[ws.index] = self.__new(ws.index)

                self.__start(ws.index)  # Start a new thread.
                # Add randomized delay before resubscribing to topics
                time.sleep(random.uniform(15, 45))  # 15-45 seconds instead of fixed 30

                for topic in ws.topics:
                    self.__submit(ws.index, topic)

    @staticmethod
    def on_message(ws, message):
        logger.debug(f"#{ws.index} - Received: {message.strip()}")
        response = json.loads(message)

        if response["type"] == "MESSAGE":
            # We should create a Message class ...
            message = Message(response["data"])

            # If we have more than one PubSub connection, messages may be duplicated
            # Check the concatenation between message_type.top.channel_id
            if (
                ws.last_message_type_channel is not None
                and ws.last_message_timestamp is not None
                and ws.last_message_timestamp == message.timestamp
                and ws.last_message_type_channel == message.identifier
            ):
                return

            ws.last_message_timestamp = message.timestamp
            ws.last_message_type_channel = message.identifier

            streamer_index = get_streamer_index(ws.streamers, message.channel_id)
            if streamer_index != -1:
                try:
                    if message.topic == "community-points-user-v1":
                        if message.type in ["points-earned", "points-spent"]:
                            balance = message.data["balance"]["balance"]
                            ws.streamers[streamer_index].channel_points = balance
                            
                            # Mettre à jour bot_data.json avec le nouveau solde
                            update_bot_data(ws.streamers[streamer_index].username, {
                                'balance': balance,
                                'online': ws.streamers[streamer_index].is_online
                            })
                            
                            # Analytics switch
                            if Settings.enable_analytics is True:
                                ws.streamers[streamer_index].persistent_series(
                                    event_type=message.data["point_gain"]["reason_code"]
                                    if message.type == "points-earned"
                                    else "Spent"
                                )

                        if message.type == "points-earned":
                            earned = message.data["point_gain"]["total_points"]
                            reason_code = message.data["point_gain"]["reason_code"]

                            logger.info(
                                f"+{earned} → {ws.streamers[streamer_index]} - Reason: {reason_code}.",
                                extra={
                                    "emoji": ":rocket:",
                                    "event": Events.get(f"GAIN_FOR_{reason_code}"),
                                },
                            )
                            ws.streamers[streamer_index].update_history(
                                reason_code, earned
                            )
                            
                            # Mettre à jour bot_data.json avec les gains par type
                            points_update = {'total_earned': earned}
                            if reason_code in ['WATCH', 'WATCH_STREAK']:
                                points_update['watch_points'] = earned
                            elif reason_code in ['CLAIM', 'RAID']:
                                points_update['bonus_points'] = earned
                            update_bot_data(ws.streamers[streamer_index].username, points_update)
                            
                            # Analytics switch
                            if Settings.enable_analytics is True:
                                ws.streamers[streamer_index].persistent_annotations(
                                    reason_code, f"+{earned} - {reason_code}"
                                )
                        elif message.type == "claim-available":
                            ws.twitch.claim_bonus(
                                ws.streamers[streamer_index],
                                message.data["claim"]["id"],
                            )

                    elif message.topic == "video-playback-by-id":
                        # There is stream-up message type, but it's sent earlier than the API updates
                        if message.type == "stream-up":
                            ws.streamers[streamer_index].stream_up = time.time()
                        elif message.type == "stream-down":
                            if ws.streamers[streamer_index].is_online is True:
                                ws.streamers[streamer_index].set_offline()
                        elif message.type == "viewcount":
                            if ws.streamers[streamer_index].stream_up_elapsed():
                                ws.twitch.check_streamer_online(
                                    ws.streamers[streamer_index]
                                )

                    elif message.topic == "raid":
                        if message.type == "raid_update_v2":
                            raid = Raid(
                                message.message["raid"]["id"],
                                message.message["raid"]["target_login"],
                            )
                            ws.twitch.update_raid(ws.streamers[streamer_index], raid)

                    elif message.topic == "community-moments-channel-v1":
                        if message.type == "active":
                            ws.twitch.claim_moment(
                                ws.streamers[streamer_index], message.data["moment_id"]
                            )

                    elif message.topic == "predictions-channel-v1":

                        event_dict = message.data["event"]
                        event_id = event_dict["id"]
                        event_status = event_dict["status"]

                        current_tmsp = parser.parse(message.timestamp)

                        if (
                            message.type == "event-created"
                            and event_id not in ws.events_predictions
                        ):
                            if event_status == "ACTIVE":
                                prediction_window_seconds = float(
                                    event_dict["prediction_window_seconds"]
                                )
                                # Reduce prediction window by 3/6s - Collect more accurate data for decision
                                prediction_window_seconds = ws.streamers[
                                    streamer_index
                                ].get_prediction_window(prediction_window_seconds)
                                event = EventPrediction(
                                    ws.streamers[streamer_index],
                                    event_id,
                                    event_dict["title"],
                                    parser.parse(event_dict["created_at"]),
                                    prediction_window_seconds,
                                    event_status,
                                    event_dict["outcomes"],
                                )
                                
                                if (
                                    ws.streamers[streamer_index].is_online
                                    and event.closing_bet_after(current_tmsp) > 0
                                ):
                                    streamer = ws.streamers[streamer_index]
                                    bet_settings = streamer.settings.bet
                                    if (
                                        bet_settings.minimum_points is None
                                        or streamer.channel_points
                                        > bet_settings.minimum_points
                                    ):
                                        ws.events_predictions[event_id] = event
                                        
                                        # === AJOUTER À ACTIVE_PREDICTIONS ===
                                        outcomes_data = []
                                        for i, outcome in enumerate(event_dict["outcomes"]):
                                            outcomes_data.append({
                                                'title': outcome.get('title', f'Option {i+1}'),
                                                'color': outcome.get('color', 'BLUE' if i == 0 else 'PINK'),
                                                'users': outcome.get('total_users', 0),
                                                'points': outcome.get('total_points', 0),
                                                'odds': 0
                                            })
                                        
                                        update_active_prediction({
                                            'event_id': event_id,
                                            'streamer': streamer.username,
                                            'title': event_dict["title"],
                                            'outcomes': outcomes_data,
                                            'time_remaining': int(event.closing_bet_after(current_tmsp)),
                                            'total_time': int(event_dict["prediction_window_seconds"]),
                                            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            'our_bet': None,
                                            'status': 'active'
                                        })
                                        
                                        # Calculer le délai réel selon delay_mode et delay
                                        start_after = event.closing_bet_after(current_tmsp)
                                        
                                        # Vérifier que le délai est valide (positif et pas trop long)
                                        if start_after <= 0:
                                            logger.warning(
                                                f"⚠️ Délai invalide ({start_after}s) pour {event}, placement immédiat",
                                                extra={
                                                    "emoji": ":warning:",
                                                    "event": Events.BET_START,
                                                },
                                            )
                                            # Placer immédiatement si délai invalide
                                            start_after = 0.1
                                        
                                        # Limiter le délai à 1 heure max pour éviter les timers trop longs
                                        if start_after > 3600:
                                            logger.warning(
                                                f"⚠️ Délai trop long ({start_after}s) pour {event}, limité à 1h",
                                                extra={
                                                    "emoji": ":warning:",
                                                    "event": Events.BET_START,
                                                },
                                            )
                                            start_after = 3600

                                        # Créer une fonction wrapper pour logger l'exécution
                                        def bet_timer_callback(event_arg):
                                            try:
                                                # Vérifier que l'événement est toujours actif
                                                if event_arg.status != "ACTIVE":
                                                    logger.info(
                                                        f"⏰ Timer exécuté mais événement n'est plus ACTIVE ({event_arg.status})",
                                                        extra={
                                                            "emoji": ":warning:",
                                                            "event": Events.BET_FILTERS,
                                                        },
                                                    )
                                                    return
                                                
                                                # Vérifier qu'on a assez de données (min_voters)
                                                min_voters = getattr(event_arg.streamer.settings.bet, 'min_voters', 30)
                                                total_users = event_arg.bet.total_users
                                                
                                                if total_users < min_voters:
                                                    logger.info(
                                                        f"⏰ Timer exécuté mais pas assez de votants ({total_users}/{min_voters})",
                                                        extra={
                                                            "emoji": ":warning:",
                                                            "event": Events.BET_FILTERS,
                                                        },
                                                    )
                                                    return
                                                
                                                logger.info(
                                                    f"⏰ Timer exécuté pour {event_arg.event_id} (statut: {event_arg.status}, {total_users} votants)",
                                                    extra={
                                                        "emoji": ":alarm_clock:",
                                                        "event": Events.BET_START,
                                                    },
                                                )
                                                ws.twitch.make_predictions(event_arg)
                                            except Exception as e:
                                                logger.error(
                                                    f"❌ Erreur dans Timer bet pour {event_arg.event_id}: {e}",
                                                    extra={
                                                        "emoji": ":warning:",
                                                        "event": Events.BET_FAILED,
                                                    },
                                                    exc_info=True,
                                                )
                                        
                                        place_bet_thread = Timer(
                                            start_after,
                                            bet_timer_callback,
                                            (ws.events_predictions[event_id],),
                                        )
                                        place_bet_thread.daemon = False  # Non-daemon pour s'assurer qu'il s'exécute
                                        place_bet_thread.start()

                                        logger.info(
                                            f"Place the bet after: {start_after}s for: {ws.events_predictions[event_id]}",
                                            extra={
                                                "emoji": ":alarm_clock:",
                                                "event": Events.BET_START,
                                            },
                                        )
                                    else:
                                        logger.info(
                                            f"{streamer} have only {streamer.channel_points} channel points and the minimum for bet is: {bet_settings.minimum_points}",
                                            extra={
                                                "emoji": ":pushpin:",
                                                "event": Events.BET_FILTERS,
                                            },
                                        )

                        elif (
                            message.type == "event-updated"
                            and event_id in ws.events_predictions
                        ):
                            ws.events_predictions[event_id].status = event_status
                            
                            # Game over we can't update anymore the values... The bet was placed!
                            if (
                                ws.events_predictions[event_id].bet_placed is False
                                and ws.events_predictions[event_id].bet.decision == {}
                            ):
                                ws.events_predictions[event_id].bet.update_outcomes(
                                    event_dict["outcomes"]
                                )

                    elif message.topic == "predictions-user-v1":
                        event_id = message.data["prediction"]["event_id"]
                        if event_id in ws.events_predictions:
                            event_prediction = ws.events_predictions[event_id]
                            if (
                                message.type == "prediction-result"
                                and event_prediction.bet_confirmed
                            ):
                                points = event_prediction.parse_result(
                                    message.data["prediction"]["result"]
                                )
                                
                                decision = event_prediction.bet.get_decision()
                                choice = event_prediction.bet.decision["choice"]

                                logger.info(
                                    (
                                        f"{event_prediction} - Decision: {choice}: {decision['title']} "
                                        f"({decision['color']}) - Result: {event_prediction.result['string']}\n"
                                        f"📊 Odds: {decision.get('odds', 0)} ({decision.get('odds_percentage', 0)}%)\n"
                                        f"👥 Users: {decision.get('percentage_users', 0)}% ({decision.get('total_users', 0)})\n"
                                    ),
                                    extra={
                                        "emoji": ":bar_chart:",
                                        "event": Events.get(
                                            f"BET_{event_prediction.result['type']}"
                                        ),
                                    },
                                )

                                ws.streamers[streamer_index].update_history(
                                    "PREDICTION", points["gained"]
                                )
                                
                                # === MISE À JOUR BOT_DATA.JSON POUR LES STATS DE PARIS ===
                                result_type = event_prediction.result["type"]
                                streamer_username = ws.streamers[streamer_index].username
                                bet_amount = event_prediction.bet.decision.get("amount", 0)
                                
                                # Calculer le profit/perte
                                profit = 0
                                if result_type == "WIN":
                                    profit = points["gained"]
                                    update_bot_data(streamer_username, {
                                        'bets_won': 1,
                                        'bet_profits': profit if profit > 0 else 0,
                                    })
                                    logger.info(f"✅ Pari gagné sur {streamer_username}: +{profit} points")
                                    
                                elif result_type == "LOSE":
                                    loss = points["placed"]
                                    profit = -loss
                                    update_bot_data(streamer_username, {
                                        'bets_lost': 1,
                                        'bet_losses': loss,
                                    })
                                    logger.info(f"❌ Pari perdu sur {streamer_username}: -{loss} points")
                                
                                # === AJOUTER À L'HISTORIQUE DES PARIS ===
                                add_bet_to_history({
                                    'streamer': streamer_username,
                                    'title': event_prediction.title,
                                    'choice': choice,
                                    'choice_title': decision.get('title', ''),
                                    'amount': bet_amount,
                                    'odds': decision.get('odds', 0),
                                    'result': result_type.lower(),
                                    'profit': profit,
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                })
                                
                                # Supprimer des prédictions actives
                                update_active_prediction({'event_id': event_id}, remove=True)
                                
                                # Remove duplicate history records from previous message sent in community-points-user-v1
                                if result_type == "REFUND":
                                    ws.streamers[streamer_index].update_history(
                                        "REFUND",
                                        -points["placed"],
                                        counter=-1,
                                    )
                                elif result_type == "WIN":
                                    ws.streamers[streamer_index].update_history(
                                        "PREDICTION",
                                        -points["won"],
                                        counter=-1,
                                    )

                                if event_prediction.result["type"]:
                                    # Analytics switch
                                    if Settings.enable_analytics is True:
                                        ws.streamers[
                                            streamer_index
                                        ].persistent_annotations(
                                            event_prediction.result["type"],
                                            f"{ws.events_predictions[event_id].title}",
                                        )
                            elif message.type == "prediction-made":
                                event_prediction.bet_confirmed = True
                                event_prediction.bet_placed = True
                                
                                # === ENREGISTRER LE PARI PLACÉ ===
                                streamer_username = ws.streamers[streamer_index].username
                                bet_amount = event_prediction.bet.decision.get("amount", 0)
                                bet_choice = event_prediction.bet.decision.get("choice", 0)
                                decision = event_prediction.bet.get_decision()
                                
                                update_bot_data(streamer_username, {
                                    'bets_placed': 1,
                                })
                                logger.info(f"🎲 Pari placé sur {streamer_username}: {bet_amount} points")
                                
                                # Mettre à jour la prédiction active avec notre pari
                                update_active_prediction({
                                    'event_id': event_id,
                                    'streamer': streamer_username,
                                    'title': event_prediction.title,
                                    'outcomes': [],
                                    'time_remaining': 0,
                                    'total_time': event_prediction.prediction_window_seconds,
                                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'our_bet': {
                                        'choice': bet_choice,
                                        'choice_title': decision.get('title', ''),
                                        'amount': bet_amount,
                                        'odds': decision.get('odds', 0)
                                    },
                                    'status': 'bet_placed'
                                })
                                
                                # Analytics switch
                                if Settings.enable_analytics is True:
                                    ws.streamers[streamer_index].persistent_annotations(
                                        "PREDICTION_MADE",
                                        f"Decision: {event_prediction.bet.decision['choice']} - {event_prediction.title}",
                                    )
                    elif message.topic == "community-points-channel-v1":
                        if message.type == "community-goal-created":
                            # TODO Untested, hard to find this happening live
                            ws.streamers[streamer_index].add_community_goal(
                                CommunityGoal.from_pubsub(message.data["community_goal"])
                            )
                        elif message.type == "community-goal-updated":
                            ws.streamers[streamer_index].update_community_goal(
                                CommunityGoal.from_pubsub(message.data["community_goal"])
                            )
                        elif message.type == "community-goal-deleted":
                            # TODO Untested, not sure what the message format for this is,
                            #      https://github.com/sammwyy/twitch-ps/blob/master/main.js#L417
                            #      suggests that it should be just the entire, now deleted, goal model
                            ws.streamers[streamer_index].delete_community_goal(message.data["community_goal"]["id"])

                        if message.type in ["community-goal-updated", "community-goal-created"]:
                            ws.twitch.contribute_to_community_goals(ws.streamers[streamer_index])

                except Exception:
                    logger.error(
                        f"Exception raised for topic: {message.topic} and message: {message}",
                        exc_info=True,
                    )

        elif response["type"] == "RESPONSE" and len(response.get("error", "")) > 0:
            # raise RuntimeError(f"Error while trying to listen for a topic: {response}")
            error_message = response.get("error", "")
            logger.error(f"Error while trying to listen for a topic: {error_message}")
            
            # Check if the error message indicates an authentication issue (ERR_BADAUTH)
            if "ERR_BADAUTH" in error_message:
                # Inform the user about the potential outdated cookie file
                username = ws.twitch.twitch_login.username
                logger.error(f"Received the ERR_BADAUTH error, most likely you have an outdated cookie file \"cookies\\{username}.pkl\". Delete this file and try again.")
                # Attempt to delete the outdated cookie file
                # try:
                #     cookie_file_path = os.path.join("cookies", f"{username}.pkl")
                #     if os.path.exists(cookie_file_path):
                #         os.remove(cookie_file_path)
                #         logger.info(f"Deleted outdated cookie file for user: {username}")
                #     else:
                #         logger.warning(f"Cookie file not found for user: {username}")
                # except Exception as e:
                #     logger.error(f"Error occurred while deleting cookie file: {str(e)}")

        elif response["type"] == "RECONNECT":
            logger.info(f"#{ws.index} - Reconnection required")
            WebSocketsPool.handle_reconnection(ws)

        elif response["type"] == "PONG":
            ws.last_pong = time.time()
