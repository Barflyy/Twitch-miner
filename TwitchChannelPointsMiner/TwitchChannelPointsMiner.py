# -*- coding: utf-8 -*-

import logging
import os
import random
import signal
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from TwitchChannelPointsMiner.classes.Chat import ChatPresence, ThreadChat
from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.classes.Exceptions import StreamerDoesNotExistException
from TwitchChannelPointsMiner.classes.Settings import FollowersOrder, Priority, Settings
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.WebSocketsPool import WebSocketsPool
from TwitchChannelPointsMiner.logger import LoggerSettings, configure_loggers
from TwitchChannelPointsMiner.utils import (
    _millify,
    at_least_one_value_in_settings_is,
    check_versions,
    get_user_agent,
    internet_connection_available,
    set_default_settings,
)

# Suppress:
#   - chardet.charsetprober - [feed]
#   - chardet.charsetprober - [get_confidence]
#   - requests - [Starting new HTTPS connection (1)]
#   - Flask (werkzeug) logs
#   - irc.client - [process_data]
#   - irc.client - [_dispatcher]
#   - irc.client - [_handle_message]
logging.getLogger("chardet.charsetprober").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("irc.client").setLevel(logging.ERROR)
logging.getLogger("seleniumwire").setLevel(logging.ERROR)
logging.getLogger("websocket").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class TwitchChannelPointsMiner:
    __slots__ = [
        "username",
        "twitch",
        "claim_drops_startup",
        "enable_analytics",
        "disable_ssl_cert_verification",
        "disable_at_in_nickname",
        "priority",
        "streamers",
        "events_predictions",
        "minute_watcher_thread",
        "sync_campaigns_thread",
        "stream_monitor_thread",
        "ws_pool",
        "session_id",
        "running",
        "start_datetime",
        "original_streamers",
        "logs_file",
        "queue_listener",
    ]

    def __init__(
        self,
        username: str,
        password: str = None,
        claim_drops_startup: bool = False,
        enable_analytics: bool = False,
        disable_ssl_cert_verification: bool = False,
        disable_at_in_nickname: bool = False,
        # Settings for logging and selenium as you can see.
        priority: list = [Priority.STREAK, Priority.DROPS, Priority.ORDER],
        # This settings will be global shared trought Settings class
        logger_settings: LoggerSettings = LoggerSettings(),
        # Default values for all streamers
        streamer_settings: StreamerSettings = StreamerSettings(),
    ):
        # Fixes TypeError: 'NoneType' object is not subscriptable
        if not username or username == "your-twitch-username":
            logger.error("Please edit your runner file (usually run.py) and try again.")
            logger.error("No username, exiting...")
            sys.exit(0)

        # This disables certificate verification and allows the connection to proceed, but also makes it vulnerable to man-in-the-middle (MITM) attacks.
        Settings.disable_ssl_cert_verification = disable_ssl_cert_verification

        Settings.disable_at_in_nickname = disable_at_in_nickname

        import socket

        def is_connected():
            try:
                # resolve the IP address of the Twitch.tv domain name
                socket.gethostbyname("twitch.tv")
                return True
            except OSError:
                pass
            return False

        # check for Twitch.tv connectivity every 5 seconds
        error_printed = False
        while not is_connected():
            if not error_printed:
                logger.error("Waiting for Twitch.tv connectivity...")
                error_printed = True
            time.sleep(5)

        # Analytics switch
        Settings.enable_analytics = enable_analytics

        if enable_analytics is True:
            # Utiliser DATA_DIR si défini
            data_dir = os.getenv("DATA_DIR")
            base_path = Path(data_dir) if data_dir else Path().absolute()
            
            Settings.analytics_path = os.path.join(
                base_path, "analytics", username
            )
            Path(Settings.analytics_path).mkdir(parents=True, exist_ok=True)

        self.username = username

        # Set as global config
        Settings.logger = logger_settings

        # Init as default all the missing values
        streamer_settings.default()
        streamer_settings.bet.default()
        Settings.streamer_settings = streamer_settings

        # user_agent = get_user_agent("FIREFOX")
        user_agent = get_user_agent("CHROME")
        self.twitch = Twitch(self.username, user_agent, password)

        self.claim_drops_startup = claim_drops_startup
        self.priority = priority if isinstance(priority, list) else [priority]

        self.streamers: list[Streamer] = []
        self.events_predictions = {}
        self.minute_watcher_thread = None
        self.sync_campaigns_thread = None
        self.stream_monitor_thread = None
        self.ws_pool = None

        self.session_id = str(uuid.uuid4())
        self.running = False
        self.start_datetime = None
        self.original_streamers = []

        self.logs_file, self.queue_listener = configure_loggers(
            self.username, logger_settings
        )

        # Check for the latest version of the script
        current_version, github_version = check_versions()

        logger.info(
            f"Twitch Channel Points Miner v2-{current_version} (fork by rdavydov)"
        )
        logger.info("https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2")

        if github_version == "0.0.0":
            logger.error(
                "Unable to detect if you have the latest version of this script"
            )
        elif current_version != github_version:
            logger.info(f"You are running version {current_version} of this script")
            logger.info(f"The latest version on GitHub is {github_version}")

        for sign in [signal.SIGINT, signal.SIGSEGV, signal.SIGTERM]:
            signal.signal(sign, self.end)

    def analytics(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        refresh: int = 5,
        days_ago: int = 7,
    ):
        # Analytics switch
        if Settings.enable_analytics is True:
            from TwitchChannelPointsMiner.classes.AnalyticsServer import AnalyticsServer

            days_ago = days_ago if days_ago <= 365 * 15 else 365 * 15
            http_server = AnalyticsServer(
                host=host,
                port=port,
                refresh=refresh,
                days_ago=days_ago,
                username=self.username,
            )
            http_server.daemon = True
            http_server.name = "Analytics Thread"
            http_server.start()
        else:
            logger.error("Can't start analytics(), please set enable_analytics=True")

    def mine(
        self,
        streamers: list = [],
        blacklist: list = [],
        followers: bool = False,
        followers_order: FollowersOrder = FollowersOrder.ASC,
    ):
        self.run(streamers=streamers, blacklist=blacklist, followers=followers)

    def run(
        self,
        streamers: list = [],
        blacklist: list = [],
        followers: bool = False,
        followers_order: FollowersOrder = FollowersOrder.ASC,
    ):
        if self.running:
            logger.error("You can't start multiple sessions of this instance!")
        else:
            logger.info(
                f"Start session: '{self.session_id}'", extra={"emoji": ":bomb:"}
            )
            self.running = True
            self.start_datetime = datetime.now()

            self.twitch.login()

            if self.claim_drops_startup is True:
                self.twitch.claim_all_drops_from_inventory()

            streamers_name: list = []
            streamers_dict: dict = {}

            logger.info(f"📋 Streamers passés au miner : {len(streamers)}")
            for streamer in streamers:
                username = (
                    streamer.username
                    if isinstance(streamer, Streamer)
                    else streamer.lower().strip()
                )
                if username not in blacklist:
                    streamers_name.append(username)
                    streamers_dict[username] = streamer

            logger.info(f"📋 Streamers après filtrage blacklist : {len(streamers_name)}")

            if followers is True:
                # Passer la blacklist pour filtrer lors du chargement du cache
                followers_array = self.twitch.get_followers(order=followers_order, blacklist=blacklist)
                logger.info(
                    f"Load {len(followers_array)} followers from your profile!",
                    extra={"emoji": ":clipboard:"},
                )
                for username in followers_array:
                    if username not in streamers_dict and username not in blacklist:
                        streamers_name.append(username)
                        streamers_dict[username] = username.lower().strip()

            logger.info(
                f"Loading data for {len(streamers_name)} streamers. Please wait...",
                extra={"emoji": ":nerd_face:"},
            )
            
            # 🚀 OPTIMISATION : Charger tous les channel IDs en batch via API Helix
            logger.info("⚡ Chargement des channel IDs en batch via API Helix...")
            start_time = time.time()
            channel_ids_map = self.twitch._get_channel_ids_batch(streamers_name)
            batch_time = time.time() - start_time
            logger.info(f"✅ {len(channel_ids_map)} channel IDs chargés en {batch_time:.1f}s (batch)")
            
            loaded_count = 0
            failed_count = 0
            start_time = time.time()
            for username in streamers_name:
                if username in streamers_name:
                    try:
                        streamer = (
                            streamers_dict[username]
                            if isinstance(streamers_dict[username], Streamer) is True
                            else Streamer(username)
                        )
                        
                        # Utiliser le channel ID récupéré en batch
                        if username in channel_ids_map:
                            streamer.channel_id = channel_ids_map[username]
                        else:
                            # Fallback sur méthode individuelle si pas trouvé en batch
                            logger.debug(f"⚠️ {username} non trouvé en batch, fallback individuel...")
                            streamer.channel_id = self.twitch.get_channel_id(username)
                        
                        streamer.settings = set_default_settings(
                            streamer.settings, Settings.streamer_settings
                        )
                        streamer.settings.bet = set_default_settings(
                            streamer.settings.bet, Settings.streamer_settings.bet
                        )
                        if streamer.settings.chat != ChatPresence.NEVER:
                            streamer.irc_chat = ThreadChat(
                                self.username,
                                self.twitch.twitch_login.get_auth_token(),
                                streamer.username,
                            )
                        self.streamers.append(streamer)
                        loaded_count += 1
                        if loaded_count % 50 == 0:
                            elapsed = time.time() - start_time
                            remaining = (elapsed / loaded_count) * (len(streamers_name) - loaded_count)
                            logger.info(f"📊 {loaded_count}/{len(streamers_name)} streamers chargés... (~{remaining/60:.1f} min restantes)")
                    except StreamerDoesNotExistException:
                        failed_count += 1
                        logger.info(
                            f"Streamer {username} does not exist",
                            extra={"emoji": ":cry:"},
                        )
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"❌ Erreur chargement streamer {username}: {e}")
            
            logger.info(f"✅ {loaded_count} streamers chargés avec succès, {failed_count} échecs")

            # 🚀 OPTIMISATION : Vérifier l'état en ligne en batch via API Helix
            logger.info("⚡ Vérification de l'état en ligne en batch via API Helix...")
            start_time = time.time()
            online_status = self.twitch.get_followed_streams_online([s.username for s in self.streamers])
            if online_status:
                online_set = online_status.get('online', set())
                offline_set = online_status.get('offline', set())
                streams_data = online_status.get('streams_data', {})
                
                # Mettre à jour l'état en ligne de tous les streamers
                for streamer in self.streamers:
                    if streamer.username in online_set:
                        streamer.set_online()
                        # Mettre à jour les infos du stream si disponibles
                        if streamer.username in streams_data:
                            stream_data = streams_data[streamer.username]
                            game_name = stream_data.get('game_name', '')
                            streamer.stream.update(
                                broadcast_id=None,  # Pas disponible via Helix
                                title=stream_data.get('title', ''),
                                game={'name': game_name, 'displayName': game_name} if game_name else {},
                                tags=[],
                                viewers_count=stream_data.get('viewer_count', 0)
                            )
                    elif streamer.username in offline_set:
                        streamer.set_offline()
                
                batch_time = time.time() - start_time
                logger.info(f"✅ État en ligne vérifié en {batch_time:.1f}s : {len(online_set)} en ligne, {len(offline_set)} hors ligne")
            else:
                logger.warning("⚠️ Impossible de vérifier l'état en ligne en batch, fallback individuel...")
                # Fallback sur méthode individuelle
                for streamer in self.streamers:
                    time.sleep(random.uniform(0.1, 0.3))
                    try:
                        self.twitch.check_streamer_online(streamer)
                    except StreamerDoesNotExistException:
                        pass

            # Populate the streamers with default values.
            # 1. Load channel points and auto-claim bonus (nécessite GraphQL, pas d'optimisation possible)
            # Note: Les channel points sont des données privées, nécessitent GraphQL avec auth
            logger.info("⚡ Chargement des channel points (GraphQL, peut prendre du temps)...")
            start_time = time.time()
            points_loaded = 0
            for streamer in self.streamers:
                time.sleep(random.uniform(0.1, 0.2))  # Réduire le délai
                try:
                    self.twitch.load_channel_points_context(streamer)
                    points_loaded += 1
                    if points_loaded % 50 == 0:
                        elapsed = time.time() - start_time
                        remaining = (elapsed / points_loaded) * (len(self.streamers) - points_loaded)
                        logger.info(f"📊 {points_loaded}/{len(self.streamers)} channel points chargés... (~{remaining/60:.1f} min restantes)")
                except StreamerDoesNotExistException:
                    logger.info(
                        f"Streamer {streamer.username} does not exist",
                        extra={"emoji": ":cry:"},
                    )
            
            points_time = time.time() - start_time
            logger.info(f"✅ {points_loaded} channel points chargés en {points_time:.1f}s")
            
            # 🔄 Mettre à jour bot_data.json avec les points chargés pour que le bot Discord actualise les fiches
            try:
                import json
                from pathlib import Path
                # Utiliser DATA_DIR si défini
                data_dir = os.getenv("DATA_DIR")
                base_path = Path(data_dir) if data_dir else Path()
                data_file = base_path / "bot_data.json"
                
                # Charger les données existantes
                if data_file.exists():
                    with open(data_file, 'r') as f:
                        data = json.load(f)
                else:
                    data = {'streamers': {}}
                
                # Mettre à jour les points de tous les streamers
                updated_count = 0
                for streamer in self.streamers:
                    streamer_name = streamer.username.lower()
                    if streamer_name not in data['streamers']:
                        data['streamers'][streamer_name] = {
                            'online': streamer.is_online,
                            'balance': streamer.channel_points,
                            'starting_balance': streamer.channel_points,
                            'total_earned': 0,
                            'session_points': 0,
                            'watch_points': 0,
                            'bonus_points': 0,
                            'bets_placed': 0,
                            'bets_won': 0,
                            'bets_lost': 0
                        }
                        updated_count += 1
                    else:
                        # Mettre à jour le solde et le statut
                        old_balance = data['streamers'][streamer_name].get('balance', 0)
                        data['streamers'][streamer_name]['balance'] = streamer.channel_points
                        data['streamers'][streamer_name]['online'] = streamer.is_online
                        
                        # Si le solde a changé et qu'on n'a pas encore de starting_balance, l'initialiser
                        if 'starting_balance' not in data['streamers'][streamer_name] or data['streamers'][streamer_name]['starting_balance'] == 0:
                            data['streamers'][streamer_name]['starting_balance'] = streamer.channel_points
                
                # Sauvegarder
                with open(data_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.info(f"📊 bot_data.json mis à jour : {updated_count} nouveaux streamers, {len(self.streamers)} total")
            except Exception as e:
                logger.warning(f"⚠️ Erreur mise à jour bot_data.json : {e}")

            self.original_streamers = [
                streamer.channel_points for streamer in self.streamers
            ]

            # If we have at least one streamer with settings = make_predictions True
            make_predictions = at_least_one_value_in_settings_is(
                self.streamers, "make_predictions", True
            )

            # If we have at least one streamer with settings = claim_drops True
            # Spawn a thread for sync inventory and dashboard
            if (
                at_least_one_value_in_settings_is(self.streamers, "claim_drops", True)
                is True
            ):
                self.sync_campaigns_thread = threading.Thread(
                    target=self.twitch.sync_campaigns,
                    args=(self.streamers,),
                )
                self.sync_campaigns_thread.name = "Sync campaigns/inventory"
                self.sync_campaigns_thread.start()
                time.sleep(30)

            self.minute_watcher_thread = threading.Thread(
                target=self.twitch.send_minute_watched_events,
                args=(self.streamers, self.priority),
            )
            self.minute_watcher_thread.name = "Minute watcher"
            self.minute_watcher_thread.start()

            # 🚀 Surveillance automatique des streams suivis via API Helix
            # Détecte rapidement les changements d'état (en ligne/hors ligne)
            if followers is True:
                self.stream_monitor_thread = threading.Thread(
                    target=self.twitch.monitor_followed_streams,
                    args=(self.streamers,),
                    kwargs={"check_interval": 60}  # Vérifie toutes les 60 secondes
                )
                self.stream_monitor_thread.name = "Stream monitor (API Helix)"
                self.stream_monitor_thread.start()
                logger.info(
                    "🔄 Surveillance automatique des streams activée (API Helix, toutes les 60s)",
                    extra={"emoji": ":satellite:"}
                )

            self.ws_pool = WebSocketsPool(
                twitch=self.twitch,
                streamers=self.streamers,
                events_predictions=self.events_predictions,
            )

            # Subscribe to community-points-user. Get update for points spent or gains
            user_id = self.twitch.twitch_login.get_user_id()
            # print(f"!!!!!!!!!!!!!! USER_ID: {user_id}")

            # Fixes 'ERR_BADAUTH'
            if not user_id:
                logger.error("No user_id, exiting...")
                self.end(0, 0)

            self.ws_pool.submit(
                PubsubTopic(
                    "community-points-user-v1",
                    user_id=user_id,
                )
            )

            # Going to subscribe to predictions-user-v1. Get update when we place a new prediction (confirm)
            if make_predictions is True:
                self.ws_pool.submit(
                    PubsubTopic(
                        "predictions-user-v1",
                        user_id=user_id,
                    )
                )

            for streamer in self.streamers:
                self.ws_pool.submit(
                    PubsubTopic("video-playback-by-id", streamer=streamer)
                )

                if streamer.settings.follow_raid is True:
                    self.ws_pool.submit(PubsubTopic("raid", streamer=streamer))

                if streamer.settings.make_predictions is True:
                    self.ws_pool.submit(
                        PubsubTopic("predictions-channel-v1", streamer=streamer)
                    )

                if streamer.settings.claim_moments is True:
                    self.ws_pool.submit(
                        PubsubTopic("community-moments-channel-v1", streamer=streamer)
                    )

                if streamer.settings.community_goals is True:
                    self.ws_pool.submit(
                        PubsubTopic("community-points-channel-v1", streamer=streamer)
                    )

            refresh_context = time.time()
            while self.running:
                time.sleep(random.uniform(20, 60))
                # Do an external control for WebSocket. Check if the thread is running
                # Check if is not None because maybe we have already created a new connection on array+1 and now index is None
                for index in range(0, len(self.ws_pool.ws)):
                    if (
                        self.ws_pool.ws[index].is_reconnecting is False
                        and self.ws_pool.ws[index].elapsed_last_ping() > 10
                        and internet_connection_available() is True
                    ):
                        logger.info(
                            f"#{index} - The last PING was sent more than 10 minutes ago. Reconnecting to the WebSocket..."
                        )
                        WebSocketsPool.handle_reconnection(self.ws_pool.ws[index])

                if ((time.time() - refresh_context) // 60) >= 30:
                    refresh_context = time.time()
                    for index in range(0, len(self.streamers)):
                        if self.streamers[index].is_online:
                            self.twitch.load_channel_points_context(
                                self.streamers[index]
                            )

    def end(self, signum, frame):
        if not self.running:
            return
        
        logger.info("CTRL+C Detected! Please wait just a moment!")

        for streamer in self.streamers:
            if (
                streamer.irc_chat is not None
                and streamer.settings.chat != ChatPresence.NEVER
            ):
                streamer.leave_chat()
                if streamer.irc_chat.is_alive() is True:
                    streamer.irc_chat.join()

        self.running = self.twitch.running = False
        if self.ws_pool is not None:
            self.ws_pool.end()

        if self.minute_watcher_thread is not None:
            self.minute_watcher_thread.join()

        if self.sync_campaigns_thread is not None:
            self.sync_campaigns_thread.join()

        if self.stream_monitor_thread is not None:
            self.stream_monitor_thread.join()

        # Check if all the mutex are unlocked.
        # Prevent breaks of .json file
        for streamer in self.streamers:
            if streamer.mutex.locked():
                streamer.mutex.acquire()
                streamer.mutex.release()

        self.__print_report()

        # Stop the queue listener to make sure all messages have been logged
        self.queue_listener.stop()

        sys.exit(0)

    def __print_report(self):
        print("\n")
        logger.info(
            f"Ending session: '{self.session_id}'", extra={"emoji": ":stop_sign:"}
        )
        if self.logs_file is not None:
            logger.info(
                f"Logs file: {self.logs_file}", extra={"emoji": ":page_facing_up:"}
            )
        logger.info(
            f"Duration {datetime.now() - self.start_datetime}",
            extra={"emoji": ":hourglass:"},
        )

        if not Settings.logger.less and self.events_predictions != {}:
            print("")
            for event_id in self.events_predictions:
                event = self.events_predictions[event_id]
                if (
                    event.bet_confirmed is True
                    and event.streamer.settings.make_predictions is True
                ):
                    logger.info(
                        f"{event.streamer.settings.bet}",
                        extra={"emoji": ":wrench:"},
                    )
                    if event.streamer.settings.bet.filter_condition is not None:
                        logger.info(
                            f"{event.streamer.settings.bet.filter_condition}",
                            extra={"emoji": ":pushpin:"},
                        )
                    logger.info(
                        f"{event.print_recap()}",
                        extra={"emoji": ":bar_chart:"},
                    )

        print("")
        for streamer_index in range(0, len(self.streamers)):
            if self.streamers[streamer_index].history != {}:
                gained = (
                    self.streamers[streamer_index].channel_points
                    - self.original_streamers[streamer_index]
                )
                
                from colorama import Fore
                streamer_highlight = Fore.YELLOW
                
                streamer_gain = (
                    f"{streamer_highlight}{self.streamers[streamer_index]}{Fore.RESET}, Total Points Gained: {_millify(gained)}"
                    if Settings.logger.less
                    else f"{streamer_highlight}{repr(self.streamers[streamer_index])}{Fore.RESET}, Total Points Gained (after farming - before farming): {_millify(gained)}"
                )
                
                indent = ' ' * 25
                streamer_history = '\n'.join(f"{indent}{history}" for history in self.streamers[streamer_index].print_history().split('; ')) 
                
                logger.info(
                    f"{streamer_gain}\n{streamer_history}",
                    extra={"emoji": ":moneybag:"},
                )