# For documentation on Twitch GraphQL API see:
# https://www.apollographql.com/docs/
# https://github.com/mauricew/twitch-graphql-api
# Full list of available methods: https://azr.ivr.fi/schema/query.doc.html (a bit outdated)


import copy
import logging
import os
import random
import re
import string
import time
import requests
import validators
import json

from pathlib import Path
from secrets import choice, token_hex
from typing import Dict, Any
# from urllib.parse import quote
# from base64 import urlsafe_b64decode
# from datetime import datetime

from TwitchChannelPointsMiner.classes.entities.Campaign import Campaign
from TwitchChannelPointsMiner.classes.entities.CommunityGoal import CommunityGoal
from TwitchChannelPointsMiner.classes.entities.Drop import Drop
from TwitchChannelPointsMiner.classes.Exceptions import (
    StreamerDoesNotExistException,
    StreamerIsOfflineException,
)
from TwitchChannelPointsMiner.classes.Settings import (
    Events,
    FollowersOrder,
    Priority,
    Settings,
)
from TwitchChannelPointsMiner.classes.TwitchLogin import TwitchLogin
from TwitchChannelPointsMiner.constants import (
    CLIENT_ID,
    CLIENT_VERSION,
    URL,
    GQLOperations,
)
from TwitchChannelPointsMiner.utils import (
    _millify,
    create_chunks,
    internet_connection_available,
)

logger = logging.getLogger(__name__)
JsonType = Dict[str, Any]


class Twitch(object):
    __slots__ = [
        "cookies_file",
        "user_agent",
        "twitch_login",
        "running",
        "device_id",
        # "integrity",
        # "integrity_expire",
        "client_session",
        "client_version",
        "twilight_build_id_pattern",
    ]

    def __init__(self, username, user_agent, password=None):
        # Sur Railway, sauvegarder dans le dossier du projet (persiste entre déploiements)
        # Sinon utiliser ./cookies comme avant
        if os.getenv("RAILWAY_ENVIRONMENT"):
            # Railway : sauvegarder dans le répertoire du projet
            self.cookies_file = os.path.join(Path().absolute(), f".{username}_cookies.pkl")
        else:
            # Local : utiliser le dossier cookies
            cookies_path = os.path.join(Path().absolute(), "cookies")
            Path(cookies_path).mkdir(parents=True, exist_ok=True)
            self.cookies_file = os.path.join(cookies_path, f"{username}.pkl")
        self.user_agent = user_agent
        self.device_id = "".join(
            choice(string.ascii_letters + string.digits) for _ in range(32)
        )
        self.twitch_login = TwitchLogin(
            CLIENT_ID, self.device_id, username, self.user_agent, password=password
        )
        self.running = True
        # self.integrity = None
        # self.integrity_expire = 0
        self.client_session = token_hex(16)
        self.client_version = CLIENT_VERSION
        self.twilight_build_id_pattern = re.compile(
            r'window\.__twilightBuildID\s*=\s*"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"'
        )

    def login(self):
        # Si un token OAuth est fourni directement (password est un token OAuth)
        # Un token OAuth Twitch fait généralement 30-40 caractères
        if self.twitch_login.password and len(self.twitch_login.password) >= 30:
            # Utiliser directement le token OAuth fourni
            logger.info("Using provided OAuth token for authentication")
            logger.info(f"Token length: {len(self.twitch_login.password)} characters")
            
            # Nettoyer le token (enlever oauth: si présent, espaces, etc.)
            token = self.twitch_login.password.strip()
            if token.startswith("oauth:"):
                token = token[6:]  # Enlever le préfixe "oauth:"
                logger.info("Removed 'oauth:' prefix from token")
            
            # Réinitialiser le résultat de vérification pour forcer une nouvelle vérification
            self.twitch_login.login_check_result = False
            self.twitch_login.set_token(token)
            
            # Vérifier que le token est valide
            logger.info("Validating OAuth token...")
            if self.twitch_login.check_login():
                logger.info(f"✅ OAuth token valid! User ID: {self.twitch_login.user_id}")
                # Sauvegarder le token dans les cookies pour les prochaines fois
                self.twitch_login.save_cookies(self.cookies_file)
                return
            else:
                logger.error("❌ Provided OAuth token is INVALID!")
                logger.error("Please verify your TWITCH_AUTH_TOKEN:")
                logger.error("1. Go to https://twitchtokengenerator.com/")
                logger.error("2. Generate 'Custom Scope Token' with: user:read:follows, channel:read:redemptions")
                logger.error("3. Update TWITCH_AUTH_TOKEN in Railway")
                logger.warning("Falling back to login flow (will fail without valid credentials)")
        
        # Méthode normale : utiliser les cookies ou login flow
        if not os.path.isfile(self.cookies_file):
            if self.twitch_login.login_flow():
                self.twitch_login.save_cookies(self.cookies_file)
        else:
            self.twitch_login.load_cookies(self.cookies_file)
            self.twitch_login.set_token(self.twitch_login.get_auth_token())

    # === STREAMER / STREAM / INFO === #
    def update_stream(self, streamer):
        if streamer.stream.update_required() is True:
            stream_info = self.get_stream_info(streamer)
            if stream_info is not None:
                streamer.stream.update(
                    broadcast_id=stream_info["stream"]["id"],
                    title=stream_info["broadcastSettings"]["title"],
                    game=stream_info["broadcastSettings"]["game"],
                    tags=stream_info["stream"]["tags"],
                    viewers_count=stream_info["stream"]["viewersCount"],
                )

                event_properties = {
                    "channel_id": streamer.channel_id,
                    "broadcast_id": streamer.stream.broadcast_id,
                    "player": "site",
                    "user_id": self.twitch_login.get_user_id(),
                    "live": True,
                    "channel": streamer.username,
                }

                if (
                    streamer.stream.game_name() is not None
                    and streamer.stream.game_id() is not None
                    and streamer.settings.claim_drops is True
                ):
                    event_properties["game"] = streamer.stream.game_name()
                    event_properties["game_id"] = streamer.stream.game_id()
                    # Update also the campaigns_ids so we are sure to tracking the correct campaign
                    streamer.stream.campaigns_ids = (
                        self.__get_campaign_ids_from_streamer(streamer)
                    )

                streamer.stream.payload = [
                    {"event": "minute-watched", "properties": event_properties}
                ]

    def get_spade_url(self, streamer):
        try:
            # fixes AttributeError: 'NoneType' object has no attribute 'group'
            # headers = {"User-Agent": self.user_agent}
            from TwitchChannelPointsMiner.constants import USER_AGENTS

            headers = {"User-Agent": USER_AGENTS["Linux"]["FIREFOX"]}

            main_page_request = requests.get(
                streamer.streamer_url, headers=headers)
            response = main_page_request.text
            # logger.info(response)
            regex_settings = "(https://static.twitchcdn.net/config/settings.*?js|https://assets.twitch.tv/config/settings.*?.js)"
            settings_url = re.search(regex_settings, response).group(1)

            settings_request = requests.get(settings_url, headers=headers)
            response = settings_request.text
            regex_spade = '"spade_url":"(.*?)"'
            streamer.stream.spade_url = re.search(
                regex_spade, response).group(1)
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Something went wrong during extraction of 'spade_url': {e}")

    def get_broadcast_id(self, streamer):
        json_data = copy.deepcopy(GQLOperations.WithIsStreamLiveQuery)
        json_data["variables"] = {"id": streamer.channel_id}
        response = self.post_gql_request(json_data)
        if response != {}:
            stream = response["data"]["user"]["stream"]
            if stream is not None:
                return stream["id"]
            else:
                raise StreamerIsOfflineException

    def get_stream_info(self, streamer):
        json_data = copy.deepcopy(
            GQLOperations.VideoPlayerStreamInfoOverlayChannel)
        json_data["variables"] = {"channel": streamer.username}
        response = self.post_gql_request(json_data)
        if response != {}:
            if response["data"]["user"]["stream"] is None:
                raise StreamerIsOfflineException
            else:
                return response["data"]["user"]

    def check_streamer_online(self, streamer):
        if time.time() < streamer.offline_at + 60:
            return

        if streamer.is_online is False:
            try:
                self.get_spade_url(streamer)
                self.update_stream(streamer)
            except StreamerIsOfflineException:
                streamer.set_offline()
            else:
                streamer.set_online()
        else:
            try:
                self.update_stream(streamer)
            except StreamerIsOfflineException:
                streamer.set_offline()

    def get_channel_id(self, streamer_username):
        json_data = copy.deepcopy(GQLOperations.GetIDFromLogin)
        json_data["variables"]["login"] = streamer_username
        json_response = self.post_gql_request(json_data)
        if (
            "data" not in json_response
            or "user" not in json_response["data"]
            or json_response["data"]["user"] is None
        ):
            raise StreamerDoesNotExistException
        else:
            return json_response["data"]["user"]["id"]

    def get_followers(
        self, limit: int = 10000, order: FollowersOrder = FollowersOrder.ASC, blacklist: list = []
    ):
        # 🚀 CACHE HYBRIDE : GitHub (permanent) + Local (rapide)
        # 1. GitHub Cache = persistance absolue via Git commits
        # 2. Local Cache = accès ultra-rapide
        
        # Importer le cache GitHub
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from github_cache import get_github_cache
        
        github_cache = get_github_cache(self.twitch_login.username)
        
        # Cache local pour accès rapide
        if os.getenv("RAILWAY_ENVIRONMENT"):
            # Railway : utiliser le répertoire du projet (persiste avec le code)
            cache_file = Path(f".followers_cache_{self.twitch_login.username}.json")
        else:
            # Local : utiliser le dossier cookies (même persistance que l'authentification)
            cookies_dir = Path("cookies")
            cookies_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cookies_dir / f"followers_cache_{self.twitch_login.username}.json"
        
        cache_max_age = 24 * 3600  # 24 heures - followers changent peu (1h = 3600, 48h = 172800)
        
        # Vérifier si le cache existe et est récent
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Vérifications de validité du cache
                cache_username = cache_data.get('username', '')
                cache_count = cache_data.get('count', 0)
                
                if cache_username != self.twitch_login.username:
                    logger.warning(f"⚠️ Cache invalide : appartient à {cache_username}, pas à {self.twitch_login.username}")
                    cache_file.unlink()  # Supprimer le cache invalide
                elif cache_count < 200:  # Si le cache a moins de 200 followers, il est incomplet
                    logger.warning(f"⚠️ Cache incomplet ({cache_count} followers), rechargement complet...")
                    cache_file.unlink()  # Supprimer le cache incomplet
                else:
                    cache_time = cache_data.get('timestamp', 0)
                    cache_age = time.time() - cache_time
                    
                    if cache_age < cache_max_age:
                        follows = cache_data.get('followers', [])
                        # Validation des données du cache
                        if not isinstance(follows, list):
                            logger.warning("⚠️ Cache corrompu : format invalide")
                            cache_file.unlink()
                        else:
                            # Filtrer la blacklist lors du chargement du cache
                            if blacklist:
                                original_count = len(follows)
                                follows = [f for f in follows if f.lower() not in [b.lower() for b in blacklist]]
                                if original_count != len(follows):
                                    logger.info(
                                        f"🚫 {original_count - len(follows)} streamer(s) blacklisté(s) retiré(s) du cache",
                                        extra={"emoji": ":no_entry_sign:"}
                                    )
                            hours_old = cache_age / 3600
                            logger.info(
                                f"⚡ Cache local utilisé : {len(follows)} followers (mis à jour il y a {hours_old:.1f}h)",
                                extra={"emoji": ":zap:"}
                            )
                            return follows
                    else:
                        logger.info(
                            f"🔄 Cache expiré ({cache_age / 3600:.1f}h), rechargement...",
                            extra={"emoji": ":arrows_counterclockwise:"}
                        )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"⚠️ Cache corrompu, suppression : {e}")
                try:
                    cache_file.unlink()
                except:
                    pass
            except Exception as e:
                logger.warning(f"⚠️ Erreur lecture cache local : {e}")
        
        # Essayer le cache GitHub si pas de cache local
        logger.info("🔍 Vérification cache GitHub...")
        github_followers = github_cache.load_followers()
        if github_followers:
            # Filtrer la blacklist
            if blacklist:
                original_count = len(github_followers)
                github_followers = [f for f in github_followers if f.lower() not in [b.lower() for b in blacklist]]
                if original_count != len(github_followers):
                    logger.info(f"🚫 {original_count - len(github_followers)} streamer(s) blacklisté(s)")
            
            # Recréer le cache local à partir du GitHub
            try:
                cache_data = {
                    'timestamp': time.time(),
                    'username': self.twitch_login.username,
                    'followers': github_followers,
                    'count': len(github_followers),
                    'version': '3.0'
                }
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
                logger.info(f"📂 Cache local restauré depuis GitHub : {len(github_followers)} followers")
            except:
                pass  # Non bloquant
                
            return github_followers
        
        # Charger depuis Twitch API (lent, mais optimisé)
        logger.info(
            "📥 Chargement des followers depuis Twitch (peut prendre plusieurs minutes)...",
            extra={"emoji": ":inbox_tray:"}
        )
        
        # Optimisation: Chargement accéléré avec chunks plus gros et progress
        json_data = copy.deepcopy(GQLOperations.ChannelFollows)
        json_data["variables"] = {"limit": 100, "order": str(order)}  # Chunks de 100 au lieu de 20
        
        has_next = True
        last_cursor = ""
        follows = []
        chunk_count = 0
        start_time = time.time()
        
        logger.info("🚀 Chargement optimisé des followers (chunks de 100)...")
        
        while has_next and len(follows) < limit:
            json_data["variables"]["cursor"] = last_cursor
            json_response = self.post_gql_request(json_data)
            chunk_count += 1
            
            try:
                follows_response = json_response["data"]["user"]["follows"]
                chunk_follows = []
                last_cursor = None
                
                for f in follows_response["edges"]:
                    chunk_follows.append(f["node"]["login"].lower())
                    last_cursor = f["cursor"]
                
                follows.extend(chunk_follows)
                has_next = follows_response["pageInfo"]["hasNextPage"]
                
                # Progress log toutes les 5 requêtes (500 followers)
                if chunk_count % 5 == 0:
                    elapsed = time.time() - start_time
                    rate = len(follows) / elapsed if elapsed > 0 else 0
                    logger.info(f"📈 {len(follows)} followers chargés ({rate:.1f}/sec)")
                    
            except KeyError as e:
                logger.error(f"❌ Erreur récupération followers: {e}")
                logger.error(f"❌ Réponse API: {json_response}")
                # Vérifier si c'est une erreur d'authentification
                if "errors" in json_response:
                    for error in json_response["errors"]:
                        logger.error(f"❌ Twitch API Error: {error.get('message', 'Unknown error')}")
                return []
        
        # Sauvegarder le cache pour les prochains redémarrages (persistance renforcée)
        try:
            cache_data = {
                'timestamp': time.time(),
                'username': self.twitch_login.username,  # Identifier le propriétaire du cache
                'followers': follows,
                'count': len(follows),
                'version': '2.0'  # Version du cache pour futures migrations
            }
            
            # Écriture atomique pour éviter la corruption du cache
            temp_cache_file = cache_file.with_suffix('.tmp')
            with open(temp_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            # Renommer pour remplacer l'ancien cache (opération atomique)
            temp_cache_file.replace(cache_file)
            
            logger.info(
                f"💾 Cache local sauvegardé : {len(follows)} followers (valide 24h) → {cache_file}",
                extra={"emoji": ":floppy_disk:"}
            )
            
            # Sauvegarder aussi sur GitHub (backup permanent)
            github_cache.save_followers(follows)
        except Exception as e:
            logger.warning(f"⚠️ Erreur sauvegarde cache : {e}")
            # Nettoyer le fichier temporaire en cas d'erreur
            if 'temp_cache_file' in locals() and temp_cache_file.exists():
                try:
                    temp_cache_file.unlink()
                except:
                    pass
        
        return follows

    def update_raid(self, streamer, raid):
        if streamer.raid != raid:
            streamer.raid = raid
            json_data = copy.deepcopy(GQLOperations.JoinRaid)
            json_data["variables"] = {"input": {"raidID": raid.raid_id}}
            self.post_gql_request(json_data)

            logger.info(
                f"Joining raid from {streamer} to {raid.target_login}!",
                extra={"emoji": ":performing_arts:",
                       "event": Events.JOIN_RAID},
            )

    def viewer_is_mod(self, streamer):
        json_data = copy.deepcopy(GQLOperations.ModViewChannelQuery)
        json_data["variables"] = {"channelLogin": streamer.username}
        response = self.post_gql_request(json_data)
        try:
            streamer.viewer_is_mod = response["data"]["user"]["self"]["isModerator"]
        except (ValueError, KeyError):
            streamer.viewer_is_mod = False

    # === 'GLOBALS' METHODS === #
    # Create chunk of sleep of speed-up the break loop after CTRL+C
    def __chuncked_sleep(self, seconds, chunk_size=3):
        sleep_time = max(seconds, 0) / chunk_size
        for i in range(0, chunk_size):
            time.sleep(sleep_time)
            if self.running is False:
                break

    def __check_connection_handler(self, chunk_size):
        # The success rate It's very hight usually. Why we have failed?
        # Check internet connection ...
        while internet_connection_available() is False:
            random_sleep = random.randint(1, 3)
            logger.warning(
                f"No internet connection available! Retry after {random_sleep}m"
            )
            self.__chuncked_sleep(random_sleep * 60, chunk_size=chunk_size)

    def post_gql_request(self, json_data):
        try:
            response = requests.post(
                GQLOperations.url,
                json=json_data,
                headers={
                    "Authorization": f"OAuth {self.twitch_login.get_auth_token()}",
                    "Client-Id": CLIENT_ID,
                    # "Client-Integrity": self.post_integrity(),
                    "Client-Session-Id": self.client_session,
                    "Client-Version": self.update_client_version(),
                    "User-Agent": self.user_agent,
                    "X-Device-Id": self.device_id,
                },
            )
            logger.debug(
                f"Data: {json_data}, Status code: {response.status_code}, Content: {response.text}"
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Error with GQLOperations ({json_data['operationName']}): {e}"
            )
            return {}

    # Request for Integrity Token
    # Twitch needs Authorization, Client-Id, X-Device-Id to generate JWT which is used for authorize gql requests
    # Regenerate Integrity Token 5 minutes before expire
    """def post_integrity(self):
        if (
            self.integrity_expire - datetime.now().timestamp() * 1000 > 5 * 60 * 1000
            and self.integrity is not None
        ):
            return self.integrity
        try:
            response = requests.post(
                GQLOperations.integrity_url,
                json={},
                headers={
                    "Authorization": f"OAuth {self.twitch_login.get_auth_token()}",
                    "Client-Id": CLIENT_ID,
                    "Client-Session-Id": self.client_session,
                    "Client-Version": self.update_client_version(),
                    "User-Agent": self.user_agent,
                    "X-Device-Id": self.device_id,
                },
            )
            logger.debug(
                f"Data: [], Status code: {response.status_code}, Content: {response.text}"
            )
            self.integrity = response.json().get("token", None)
            # logger.info(f"integrity: {self.integrity}")

            if self.isBadBot(self.integrity) is True:
                logger.info(
                    "Uh-oh, Twitch has detected this miner as a \"Bad Bot\". Don't worry.")

            self.integrity_expire = response.json().get("expiration", 0)
            # logger.info(f"integrity_expire: {self.integrity_expire}")
            return self.integrity
        except requests.exceptions.RequestException as e:
            logger.error(f"Error with post_integrity: {e}")
            return self.integrity

    # verify the integrity token's contents for the "is_bad_bot" flag
    def isBadBot(self, integrity):
        stripped_token: str = self.integrity.split('.')[2] + "=="
        messy_json: str = urlsafe_b64decode(
            stripped_token.encode()).decode(errors="ignore")
        match = re.search(r'(.+)(?<="}).+$', messy_json)
        if match is None:
            # raise MinerException("Unable to parse the integrity token")
            logger.info("Unable to parse the integrity token. Don't worry.")
            return
        decoded_header = json.loads(match.group(1))
        # logger.info(f"decoded_header: {decoded_header}")
        if decoded_header.get("is_bad_bot", "false") != "false":
            return True
        else:
            return False"""

    def update_client_version(self):
        try:
            response = requests.get(URL)
            if response.status_code != 200:
                logger.debug(
                    f"Error with update_client_version: {response.status_code}"
                )
                return self.client_version
            matcher = re.search(self.twilight_build_id_pattern, response.text)
            if not matcher:
                logger.debug("Error with update_client_version: no match")
                return self.client_version
            self.client_version = matcher.group(1)
            logger.debug(f"Client version: {self.client_version}")
            return self.client_version
        except requests.exceptions.RequestException as e:
            logger.error(f"Error with update_client_version: {e}")
            return self.client_version

    def send_minute_watched_events(self, streamers, priority, chunk_size=3):
        while self.running:
            try:
                streamers_index = [
                    i
                    for i in range(0, len(streamers))
                    if streamers[i].is_online is True
                    and (
                        streamers[i].online_at == 0
                        or (time.time() - streamers[i].online_at) > 30
                    )
                ]

                for index in streamers_index:
                    if (streamers[index].stream.update_elapsed() / 60) > 10:
                        # Why this user It's currently online but the last updated was more than 10minutes ago?
                        # Please perform a manually update and check if the user it's online
                        self.check_streamer_online(streamers[index])

                streamers_watching = []
                for prior in priority:
                    if prior == Priority.ORDER and len(streamers_watching) < 2:
                        # Get the first 2 items, they are already in order
                        streamers_watching += streamers_index[:2]

                    elif (
                        prior in [Priority.POINTS_ASCENDING,
                                  Priority.POINTS_DESCENDING]
                        and len(streamers_watching) < 2
                    ):
                        items = [
                            {"points": streamers[index].channel_points,
                                "index": index}
                            for index in streamers_index
                        ]
                        items = sorted(
                            items,
                            key=lambda x: x["points"],
                            reverse=(
                                True if prior == Priority.POINTS_DESCENDING else False
                            ),
                        )
                        streamers_watching += [item["index"]
                                               for item in items][:2]

                    elif prior == Priority.STREAK and len(streamers_watching) < 2:
                        """
                        Check if we need need to change priority based on watch streak
                        Viewers receive points for returning for x consecutive streams.
                        Each stream must be at least 10 minutes long and it must have been at least 30 minutes since the last stream ended.
                        Watch at least 6m for get the +10
                        """
                        for index in streamers_index:
                            if (
                                streamers[index].settings.watch_streak is True
                                and streamers[index].stream.watch_streak_missing is True
                                and (
                                    streamers[index].offline_at == 0
                                    or (
                                        (time.time() -
                                         streamers[index].offline_at)
                                        // 60
                                    )
                                    > 30
                                )
                                # fix #425
                                and streamers[index].stream.minute_watched < 7
                            ):
                                streamers_watching.append(index)
                                if len(streamers_watching) == 2:
                                    break

                    elif prior == Priority.DROPS and len(streamers_watching) < 2:
                        for index in streamers_index:
                            if streamers[index].drops_condition() is True:
                                streamers_watching.append(index)
                                if len(streamers_watching) == 2:
                                    break

                    elif prior == Priority.SUBSCRIBED and len(streamers_watching) < 2:
                        streamers_with_multiplier = [
                            index
                            for index in streamers_index
                            if streamers[index].viewer_has_points_multiplier()
                        ]
                        streamers_with_multiplier = sorted(
                            streamers_with_multiplier,
                            key=lambda x: streamers[x].total_points_multiplier(
                            ),
                            reverse=True,
                        )
                        streamers_watching += streamers_with_multiplier[:2]

                """
                Twitch has a limit - you can't watch more than 2 channels at one time.
                We take the first two streamers from the list as they have the highest priority (based on order or WatchStreak).
                """
                streamers_watching = streamers_watching[:2]

                for index in streamers_watching:
                    # next_iteration = time.time() + 60 / len(streamers_watching)
                    next_iteration = time.time() + 20 / len(streamers_watching)

                    try:
                        ####################################
                        # Start of fix for 2024/5 API Change
                        # Create the JSON data for the GraphQL request
                        json_data = copy.deepcopy(
                            GQLOperations.PlaybackAccessToken)
                        json_data["variables"] = {
                            "login": streamers[index].username,
                            "isLive": True,
                            "isVod": False,
                            "vodID": "",
                            "playerType": "site"
                            # "playerType": "picture-by-picture",
                        }

                        # Get signature and value using the post_gql_request method
                        try:
                            responsePlaybackAccessToken = self.post_gql_request(
                                json_data)
                            logger.debug(
                                f"Sent PlaybackAccessToken request for {streamers[index]}")

                            if 'data' not in responsePlaybackAccessToken:
                                logger.error(
                                    f"Invalid response from Twitch: {responsePlaybackAccessToken}")
                                continue

                            streamPlaybackAccessToken = responsePlaybackAccessToken["data"].get(
                                'streamPlaybackAccessToken', {})
                            signature = streamPlaybackAccessToken.get(
                                "signature")
                            value = streamPlaybackAccessToken.get("value")

                            if not signature or not value:
                                logger.error(
                                    f"Missing signature or value in Twitch response: {responsePlaybackAccessToken}")
                                continue

                        except Exception as e:
                            logger.error(
                                f"Error fetching PlaybackAccessToken for {streamers[index]}: {str(e)}")
                            continue

                        # encoded_value = quote(json.dumps(value))

                        # Construct the URL for the broadcast qualities
                        RequestBroadcastQualitiesURL = f"https://usher.ttvnw.net/api/channel/hls/{streamers[index].username}.m3u8?sig={signature}&token={value}"

                        # Get list of video qualities
                        responseBroadcastQualities = requests.get(
                            RequestBroadcastQualitiesURL,
                            headers={"User-Agent": self.user_agent},
                            timeout=20,
                        )  # timeout=60
                        logger.debug(
                            f"Send RequestBroadcastQualitiesURL request for {streamers[index]} - Status code: {responseBroadcastQualities.status_code}"
                        )
                        if responseBroadcastQualities.status_code != 200:
                            continue
                        BroadcastQualities = responseBroadcastQualities.text

                        # Just takes the last line, which should be the URL for the lowest quality
                        BroadcastLowestQualityURL = BroadcastQualities.split(
                            "\n")[-1]
                        if not validators.url(BroadcastLowestQualityURL):
                            continue

                        # Get list of video URLs
                        responseStreamURLList = requests.get(
                            BroadcastLowestQualityURL,
                            headers={"User-Agent": self.user_agent},
                            timeout=20,
                        )  # timeout=60
                        logger.debug(
                            f"Send BroadcastLowestQualityURL request for {streamers[index]} - Status code: {responseStreamURLList.status_code}"
                        )
                        if responseStreamURLList.status_code != 200:
                            continue
                        StreamURLList = responseStreamURLList.text

                        # Just takes the last line, which should be the URL for the lowest quality
                        StreamLowestQualityURL = StreamURLList.split("\n")[-2]
                        if not validators.url(StreamLowestQualityURL):
                            continue

                        # Perform a HEAD request to simulate watching the stream
                        responseStreamLowestQualityURL = requests.head(
                            StreamLowestQualityURL,
                            headers={"User-Agent": self.user_agent},
                            timeout=20,
                        )  # timeout=60
                        logger.debug(
                            f"Send StreamLowestQualityURL request for {streamers[index]} - Status code: {responseStreamLowestQualityURL.status_code}"
                        )
                        if responseStreamLowestQualityURL.status_code != 200:
                            continue
                        # End of fix for 2024/5 API Change
                        ##################################
                        response = requests.post(
                            streamers[index].stream.spade_url,
                            data=streamers[index].stream.encode_payload(),
                            headers={"User-Agent": self.user_agent},
                            # timeout=60,
                            timeout=20,
                        )
                        logger.debug(
                            f"Send minute watched request for {streamers[index]} - Status code: {response.status_code}"
                        )
                        if response.status_code == 204:
                            streamers[index].stream.update_minute_watched()

                            """
                            Remember, you can only earn progress towards a time-based Drop on one participating channel at a time.  [ ! ! ! ]
                            You can also check your progress towards Drops within a campaign anytime by viewing the Drops Inventory.
                            For time-based Drops, if you are unable to claim the Drop in time, you will be able to claim it from the inventory page until the Drops campaign ends.
                            """

                            for campaign in streamers[index].stream.campaigns:
                                for drop in campaign.drops:
                                    # We could add .has_preconditions_met condition inside is_printable
                                    if (
                                        drop.has_preconditions_met is not False
                                        and drop.is_printable is True
                                    ):
                                        drop_messages = [
                                            f"{streamers[index]} is streaming {streamers[index].stream}",
                                            f"Campaign: {campaign}",
                                            f"Drop: {drop}",
                                            f"{drop.progress_bar()}",
                                        ]
                                        for single_line in drop_messages:
                                            logger.info(
                                                single_line,
                                                extra={
                                                    "event": Events.DROP_STATUS,
                                                    "skip_telegram": True,
                                                    "skip_discord": True,
                                                    "skip_webhook": True,
                                                    "skip_matrix": True,
                                                    "skip_gotify": True
                                                },
                                            )

                                        if Settings.logger.telegram is not None:
                                            Settings.logger.telegram.send(
                                                "\n".join(drop_messages),
                                                Events.DROP_STATUS,
                                            )

                                        if Settings.logger.discord is not None:
                                            Settings.logger.discord.send(
                                                "\n".join(drop_messages),
                                                Events.DROP_STATUS,
                                            )
                                        if Settings.logger.webhook is not None:
                                            Settings.logger.webhook.send(
                                                "\n".join(drop_messages),
                                                Events.DROP_STATUS,
                                            )
                                        if Settings.logger.gotify is not None:
                                            Settings.logger.gotify.send(
                                                "\n".join(drop_messages),
                                                Events.DROP_STATUS,
                                            )

                    except requests.exceptions.ConnectionError as e:
                        logger.error(
                            f"Error while trying to send minute watched: {e}")
                        self.__check_connection_handler(chunk_size)
                    except requests.exceptions.Timeout as e:
                        logger.error(
                            f"Error while trying to send minute watched: {e}")

                    self.__chuncked_sleep(
                        next_iteration - time.time(), chunk_size=chunk_size
                    )

                if streamers_watching == []:
                    # self.__chuncked_sleep(60, chunk_size=chunk_size)
                    self.__chuncked_sleep(20, chunk_size=chunk_size)
            except Exception:
                logger.error(
                    "Exception raised in send minute watched", exc_info=True)

    # === CHANNEL POINTS / PREDICTION === #
    # Load the amount of current points for a channel, check if a bonus is available
    def load_channel_points_context(self, streamer):
        json_data = copy.deepcopy(GQLOperations.ChannelPointsContext)
        json_data["variables"] = {"channelLogin": streamer.username}

        response = self.post_gql_request(json_data)
        if response != {}:
            if response["data"]["community"] is None:
                raise StreamerDoesNotExistException
            channel = response["data"]["community"]["channel"]
            community_points = channel["self"]["communityPoints"]
            streamer.channel_points = community_points["balance"]
            streamer.activeMultipliers = community_points["activeMultipliers"]

            if streamer.settings.community_goals is True:
                streamer.community_goals = {
                    goal["id"]: CommunityGoal.from_gql(goal)
                    for goal in channel["communityPointsSettings"]["goals"]
                }

            if community_points["availableClaim"] is not None:
                self.claim_bonus(
                    streamer, community_points["availableClaim"]["id"])

            if streamer.settings.community_goals is True:
                self.contribute_to_community_goals(streamer)

            if streamer.settings.community_goals is True:
                self.contribute_to_community_goals(streamer)

    def make_predictions(self, event):
        decision = event.bet.calculate(event.streamer.channel_points)
        # selector_index = 0 if decision["choice"] == "A" else 1

        logger.info(
            f"Going to complete bet for {event}",
            extra={
                "emoji": ":four_leaf_clover:",
                "event": Events.BET_GENERAL,
            },
        )
        if event.status == "ACTIVE":
            skip, compared_value = event.bet.skip()
            if skip is True:
                logger.info(
                    f"Skip betting for the event {event}",
                    extra={
                        "emoji": ":pushpin:",
                        "event": Events.BET_FILTERS,
                    },
                )
                logger.info(
                    f"Skip settings {event.bet.settings.filter_condition}, current value is: {compared_value}",
                    extra={
                        "emoji": ":pushpin:",
                        "event": Events.BET_FILTERS,
                    },
                )
            else:
                if decision["amount"] >= 10:
                    logger.info(
                        # f"Place {_millify(decision['amount'])} channel points on: {event.bet.get_outcome(selector_index)}",
                        f"Place {_millify(decision['amount'])} channel points on: {event.bet.get_outcome(decision['choice'])}",
                        extra={
                            "emoji": ":four_leaf_clover:",
                            "event": Events.BET_GENERAL,
                        },
                    )

                    json_data = copy.deepcopy(GQLOperations.MakePrediction)
                    json_data["variables"] = {
                        "input": {
                            "eventID": event.event_id,
                            "outcomeID": decision["id"],
                            "points": decision["amount"],
                            "transactionID": token_hex(16),
                        }
                    }
                    response = self.post_gql_request(json_data)
                    if (
                        "data" in response
                        and "makePrediction" in response["data"]
                        and "error" in response["data"]["makePrediction"]
                        and response["data"]["makePrediction"]["error"] is not None
                    ):
                        error_info = response["data"]["makePrediction"]["error"]
                        error_code = error_info.get("code", "UNKNOWN")
                        error_message = error_info.get("message", "")
                        
                        # Détecter les erreurs de blocage régional
                        is_region_blocked = (
                            "REGION" in str(error_code).upper()
                            or "GEO" in str(error_code).upper()
                            or "BLOCKED" in str(error_code).upper()
                            or "region" in str(error_message).lower()
                            or "blocked" in str(error_message).lower()
                            or "geographic" in str(error_message).lower()
                        )
                        
                        if is_region_blocked:
                            logger.error(
                                f"❌ Blocage régional détecté pour les paris! Code: {error_code}, Message: {error_message}",
                                extra={
                                    "emoji": ":no_entry_sign:",
                                    "event": Events.BET_FAILED,
                                },
                            )
                            logger.warning(
                                "💡 Solutions possibles:\n"
                                "   1. Vérifiez que votre token OAuth contient les scopes:\n"
                                "      - channel:read:predictions\n"
                                "      - channel:manage:predictions\n"
                                "   2. Les prédictions peuvent être bloquées dans votre région par Twitch\n"
                                "   3. Vérifiez votre localisation et les restrictions géographiques",
                                extra={
                                    "emoji": ":bulb:",
                                    "event": Events.BET_FAILED,
                                },
                            )
                        else:
                            logger.error(
                                f"Failed to place bet, error code: {error_code}, message: {error_message}",
                                extra={
                                    "emoji": ":four_leaf_clover:",
                                    "event": Events.BET_FAILED,
                                },
                            )
                else:
                    logger.info(
                        f"Bet won't be placed as the amount {_millify(decision['amount'])} is less than the minimum required 10",
                        extra={
                            "emoji": ":four_leaf_clover:",
                            "event": Events.BET_GENERAL,
                        },
                    )
        else:
            logger.info(
                f"Oh no! The event is not active anymore! Current status: {event.status}",
                extra={
                    "emoji": ":disappointed_relieved:",
                    "event": Events.BET_FAILED,
                },
            )

    def claim_bonus(self, streamer, claim_id):
        if Settings.logger.less is False:
            logger.info(
                f"Claiming the bonus for {streamer}!",
                extra={"emoji": ":gift:", "event": Events.BONUS_CLAIM},
            )

        json_data = copy.deepcopy(GQLOperations.ClaimCommunityPoints)
        json_data["variables"] = {
            "input": {"channelID": streamer.channel_id, "claimID": claim_id}
        }
        self.post_gql_request(json_data)

    # === MOMENTS === #
    def claim_moment(self, streamer, moment_id):
        if Settings.logger.less is False:
            logger.info(
                f"Claiming the moment for {streamer}!",
                extra={"emoji": ":video_camera:",
                       "event": Events.MOMENT_CLAIM},
            )

        json_data = copy.deepcopy(GQLOperations.CommunityMomentCallout_Claim)
        json_data["variables"] = {"input": {"momentID": moment_id}}
        self.post_gql_request(json_data)

    # === CAMPAIGNS / DROPS / INVENTORY === #
    def __get_campaign_ids_from_streamer(self, streamer):
        json_data = copy.deepcopy(
            GQLOperations.DropsHighlightService_AvailableDrops)
        json_data["variables"] = {"channelID": streamer.channel_id}
        response = self.post_gql_request(json_data)
        try:
            return (
                []
                if response["data"]["channel"]["viewerDropCampaigns"] is None
                else [
                    item["id"]
                    for item in response["data"]["channel"]["viewerDropCampaigns"]
                ]
            )
        except (ValueError, KeyError):
            return []

    def __get_inventory(self):
        response = self.post_gql_request(GQLOperations.Inventory)
        try:
            return (
                response["data"]["currentUser"]["inventory"] if response != {} else {}
            )
        except (ValueError, KeyError, TypeError):
            return {}

    def __get_drops_dashboard(self, status=None):
        response = self.post_gql_request(GQLOperations.ViewerDropsDashboard)
        campaigns = (
            response.get("data", {})
            .get("currentUser", {})
            .get("dropCampaigns", [])
            or []
        )

        if status is not None:
            campaigns = (
                list(filter(lambda x: x["status"] == status.upper(), campaigns)) or []
            )

        return campaigns

    def __get_campaigns_details(self, campaigns):
        result = []
        chunks = create_chunks(campaigns, 20)
        for chunk in chunks:
            json_data = []
            for campaign in chunk:
                json_data.append(copy.deepcopy(
                    GQLOperations.DropCampaignDetails))
                json_data[-1]["variables"] = {
                    "dropID": campaign["id"],
                    "channelLogin": f"{self.twitch_login.get_user_id()}",
                }

            response = self.post_gql_request(json_data)
            if not isinstance(response, list):
                logger.debug("Unexpected campaigns response format, skipping chunk")
                continue
            for r in response:
                drop_campaign = (
                    r.get("data", {}).get("user", {}).get("dropCampaign", None)
                )
                if drop_campaign is not None:
                    result.append(drop_campaign)
        return result

    def __sync_campaigns(self, campaigns):
        # We need the inventory only for get the real updated value/progress
        # Get data from inventory and sync current status with streamers.campaigns
        inventory = self.__get_inventory()
        if inventory not in [None, {}] and inventory["dropCampaignsInProgress"] not in [
            None,
            {},
        ]:
            # Iterate all campaigns from dashboard (only active, with working drops)
            # In this array we have also the campaigns never started from us (not in nventory)
            for i in range(len(campaigns)):
                campaigns[i].clear_drops()  # Remove all the claimed drops
                # Iterate all campaigns currently in progress from out inventory
                for progress in inventory["dropCampaignsInProgress"]:
                    if progress["id"] == campaigns[i].id:
                        campaigns[i].in_inventory = True
                        campaigns[i].sync_drops(
                            progress["timeBasedDrops"], self.claim_drop
                        )
                        # Remove all the claimed drops
                        campaigns[i].clear_drops()
                        break
        return campaigns

    def claim_drop(self, drop):
        logger.info(
            f"Claim {drop}", extra={"emoji": ":package:", "event": Events.DROP_CLAIM}
        )

        json_data = copy.deepcopy(GQLOperations.DropsPage_ClaimDropRewards)
        json_data["variables"] = {
            "input": {"dropInstanceID": drop.drop_instance_id}}
        response = self.post_gql_request(json_data)
        try:
            # response["data"]["claimDropRewards"] can be null and respose["data"]["errors"] != []
            # or response["data"]["claimDropRewards"]["status"] === DROP_INSTANCE_ALREADY_CLAIMED
            if ("claimDropRewards" in response["data"]) and (
                response["data"]["claimDropRewards"] is None
            ):
                return False
            elif ("errors" in response["data"]) and (response["data"]["errors"] != []):
                return False
            elif ("claimDropRewards" in response["data"]) and (
                response["data"]["claimDropRewards"]["status"]
                in ["ELIGIBLE_FOR_ALL", "DROP_INSTANCE_ALREADY_CLAIMED"]
            ):
                return True
            else:
                return False
        except (ValueError, KeyError):
            return False

    def claim_all_drops_from_inventory(self):
        inventory = self.__get_inventory()
        if inventory not in [None, {}]:
            if inventory["dropCampaignsInProgress"] not in [None, {}]:
                for campaign in inventory["dropCampaignsInProgress"]:
                    for drop_dict in campaign["timeBasedDrops"]:
                        drop = Drop(drop_dict)
                        drop.update(drop_dict["self"])
                        if drop.is_claimable is True:
                            drop.is_claimed = self.claim_drop(drop)
                            time.sleep(random.uniform(5, 10))

    def sync_campaigns(self, streamers, chunk_size=3):
        campaigns_update = 0
        campaigns = []
        while self.running:
            try:
                # Get update from dashboard each 60minutes
                if (
                    campaigns_update == 0
                    # or ((time.time() - campaigns_update) / 60) > 60
                    # TEMPORARY AUTO DROP CLAIMING FIX
                    # 30 minutes instead of 60 minutes
                    or ((time.time() - campaigns_update) / 30) > 30
                    #####################################
                ):
                    campaigns_update = time.time()

                    # TEMPORARY AUTO DROP CLAIMING FIX
                    self.claim_all_drops_from_inventory()
                    #####################################

                    # Get full details from current ACTIVE campaigns
                    # Use dashboard so we can explore new drops not currently active in our Inventory
                    campaigns_details = self.__get_campaigns_details(
                        self.__get_drops_dashboard(status="ACTIVE")
                    )
                    campaigns = []

                    # Going to clear array and structure. Remove all the timeBasedDrops expired or not started yet
                    for index in range(0, len(campaigns_details)):
                        if campaigns_details[index] is not None:
                            campaign = Campaign(campaigns_details[index])
                            if campaign.dt_match is True:
                                # Remove all the drops already claimed or with dt not matching
                                campaign.clear_drops()
                                if campaign.drops != []:
                                    campaigns.append(campaign)
                        else:
                            continue

                # Divide et impera :)
                campaigns = self.__sync_campaigns(campaigns)

                # Check if user It's currently streaming the same game present in campaigns_details
                for i in range(0, len(streamers)):
                    if streamers[i].drops_condition() is True:
                        # yes! The streamer[i] have the drops_tags enabled and we It's currently stream a game with campaign active!
                        # With 'campaigns_ids' we are also sure that this streamer have the campaign active.
                        # yes! The streamer[index] have the drops_tags enabled and we It's currently stream a game with campaign active!
                        streamers[i].stream.campaigns = list(
                            filter(
                                lambda x: x.drops != []
                                and x.game == streamers[i].stream.game
                                and x.id in streamers[i].stream.campaigns_ids,
                                campaigns,
                            )
                        )

            except (ValueError, KeyError, requests.exceptions.ConnectionError) as e:
                logger.error(f"Error while syncing inventory: {e}")
                campaigns = []
                self.__check_connection_handler(chunk_size)

            self.__chuncked_sleep(60, chunk_size=chunk_size)

    def contribute_to_community_goals(self, streamer):
        # Don't bother doing the request if no goal is currently started or in stock
        if any(
            goal.status == "STARTED" and goal.is_in_stock
            for goal in streamer.community_goals.values()
        ):
            json_data = copy.deepcopy(GQLOperations.UserPointsContribution)
            json_data["variables"] = {"channelLogin": streamer.username}
            response = self.post_gql_request(json_data)
            user_goal_contributions = response["data"]["user"]["channel"]["self"][
                "communityPoints"
            ]["goalContributions"]

            logger.debug(
                f"Found {len(user_goal_contributions)} community goals for the current stream"
            )

            for goal_contribution in user_goal_contributions:
                goal_id = goal_contribution["goal"]["id"]
                goal = streamer.community_goals[goal_id]
                if goal is None:
                    # TODO should this trigger a new load context request
                    logger.error(
                        f"Unable to find context data for community goal {goal_id}"
                    )
                else:
                    user_stream_contribution = goal_contribution[
                        "userPointsContributedThisStream"
                    ]
                    user_left_to_contribute = (
                        goal.per_stream_user_maximum_contribution
                        - user_stream_contribution
                    )
                    amount = min(
                        goal.amount_left(),
                        user_left_to_contribute,
                        streamer.channel_points,
                    )
                    if amount > 0:
                        self.contribute_to_community_goal(
                            streamer, goal_id, goal.title, amount
                        )
                    else:
                        logger.debug(
                            f"Not contributing to community goal {goal.title}, user channel points {streamer.channel_points}, user stream contribution {user_stream_contribution}, all users total contribution {goal.points_contributed}"
                        )

    def contribute_to_community_goal(self, streamer, goal_id, title, amount):
        json_data = copy.deepcopy(
            GQLOperations.ContributeCommunityPointsCommunityGoal)
        json_data["variables"] = {
            "input": {
                "amount": amount,
                "channelID": streamer.channel_id,
                "goalID": goal_id,
                "transactionID": token_hex(16),
            }
        }

        response = self.post_gql_request(json_data)

        error = response["data"]["contributeCommunityPointsCommunityGoal"]["error"]
        if error:
            logger.error(
                f"Unable to contribute channel points to community goal '{title}', reason '{error}'"
            )
        else:
            logger.info(
                f"Contributed {amount} channel points to community goal '{title}'"
            )
            streamer.channel_points -= amount
