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
        # Sur Fly.io, sauvegarder dans le dossier du projet (persiste entre déploiements)
        # Sinon utiliser ./cookies comme avant
        # Utiliser DATA_DIR si défini (pour la persistance sur Fly.io)
        data_dir = os.getenv("DATA_DIR")
        if data_dir:
            base_path = Path(data_dir)
            self.cookies_file = os.path.join(base_path, f"{username}_cookies.pkl")
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
                
                # Vérifier les scopes du token
                scope_validation = self.twitch_login.validate_token_scopes()
                if scope_validation and scope_validation.get("valid"):
                    scopes = scope_validation.get("scopes", [])
                    token_client_id = scope_validation.get("client_id")
                    
                    # 🔍 DIAGNOSTIC: Vérifier si le Client-ID du token correspond
                    logger.info(f"🔑 Client-ID du bot: {CLIENT_ID}")
                    logger.info(f"🔑 Client-ID du token: {token_client_id}")
                    
                    if token_client_id and token_client_id != CLIENT_ID:
                        logger.warning("⚠️ PROBLÈME DÉTECTÉ: Le Client-ID du token ne correspond pas au Client-ID du bot!")
                        logger.warning(
                            f"   Client-ID attendu: {CLIENT_ID}\n"
                            f"   Client-ID du token: {token_client_id}\n"
                            "✅ Le bot va utiliser le Client-ID du token pour les appels API Helix."
                        )
                        # Sauvegarder le Client-ID du token pour l'utiliser dans les appels Helix
                        self.twitch_login.token_client_id = token_client_id
                    
                    # Scopes requis pour les prédictions
                    prediction_scopes = ["channel:read:predictions", "channel:manage:predictions"]
                    missing_prediction_scopes = [s for s in prediction_scopes if s not in scopes]
                    
                    # Scopes requis pour récupérer les follows via Helix API
                    follows_scopes = ["user:read:follows"]
                    missing_follows_scopes = [s for s in follows_scopes if s not in scopes]
                    
                    # Afficher les warnings et recommandations
                    if missing_prediction_scopes:
                        logger.warning(
                            f"⚠️ Token OAuth manque des scopes pour les prédictions: {', '.join(missing_prediction_scopes)}"
                        )
                    else:
                        logger.info("✅ Token OAuth a tous les scopes nécessaires pour les prédictions")
                    
                    if missing_follows_scopes:
                        logger.warning(
                            f"⚠️ Token OAuth manque des scopes pour récupérer les follows: {', '.join(missing_follows_scopes)}"
                        )
                        logger.warning(
                            "⚠️ Le bot utilisera la méthode GraphQL (plus lente) pour charger vos follows"
                        )
                    else:
                        logger.info("✅ Token OAuth a le scope pour récupérer les follows via Helix API")
                    
                    # Si des scopes manquent, afficher les instructions
                    all_missing = missing_prediction_scopes + missing_follows_scopes
                    if all_missing:
                        logger.warning(
                            "💡 Pour obtenir un token avec tous les scopes nécessaires:\n"
                            f"   1. Allez sur https://twitchtokengenerator.com/\n"
                            f"   2. Sélectionnez 'Custom Scope Token Generator'\n"
                            f"   3. Cochez ces scopes: {', '.join(set(prediction_scopes + follows_scopes))}\n"
                            f"   4. Générez le token et mettez à jour TWITCH_AUTH_TOKEN"
                        )
                
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

        # Protection contre les réponses None ou malformées
        if response is None or response == {}:
            raise StreamerIsOfflineException

        # Vérifier que la structure de données existe
        if "data" not in response or response["data"] is None:
            raise StreamerIsOfflineException

        if "user" not in response["data"] or response["data"]["user"] is None:
            raise StreamerIsOfflineException

        if response["data"]["user"]["stream"] is None:
            raise StreamerIsOfflineException

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
    
    def _get_channel_ids_batch(self, streamer_usernames: list) -> dict:
        """
        🚀 Récupère les channel IDs en batch via l'API Helix (beaucoup plus rapide)
        
        Args:
            streamer_usernames: Liste des usernames à convertir en IDs
        
        Returns:
            dict: {username: channel_id} pour tous les streamers trouvés
        """
        try:
            # Utiliser le token OAuth User déjà authentifié
            user_token = self.twitch_login.get_auth_token()
            if not user_token:
                logger.warning("⚠️ Pas de token OAuth pour récupérer les channel IDs en batch")
                return {}
            
            client_id = self.twitch_login.token_client_id or CLIENT_ID
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {user_token}"
            }
            
            username_to_id = {}
            
            # Diviser en chunks de 100 (limite API Helix)
            chunks = create_chunks(streamer_usernames, 100)
            
            for chunk in chunks:
                # Construire la requête avec plusieurs usernames
                usernames_param = "&".join([f"login={username}" for username in chunk])
                users_url = f"https://api.twitch.tv/helix/users?{usernames_param}"
                
                try:
                    users_response = requests.get(users_url, headers=headers, timeout=10)
                    users_response.raise_for_status()
                    users_data = users_response.json()
                    
                    for user in users_data.get("data", []):
                        user_id = user.get("id")
                        username = user.get("login", "").lower()
                        if user_id and username:
                            username_to_id[username] = user_id
                except Exception as e:
                    logger.debug(f"⚠️ Erreur récupération IDs pour chunk: {e}")
                    continue
            
            return username_to_id
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération channel IDs en batch : {e}")
            return {}

    def _get_followers_via_helix_api(self):
        """
        🚀 NOUVELLE MÉTHODE RAPIDE : API Twitch Helix officielle

        Récupère TOUS les followers via l'API Helix (bien plus rapide que GraphQL)
        Utilise le User Access Token OAuth déjà authentifié par le bot

        Returns:
            list: Liste des usernames des streamers suivis, ou None si erreur
        """
        try:
            # 1. Utiliser le token OAuth User déjà authentifié
            user_token = self.twitch_login.get_auth_token()
            if not user_token:
                logger.warning("⚠️ Pas de token OAuth utilisateur disponible")
                logger.warning("⚠️ Fallback sur méthode GraphQL (plus lente)")
                return None

            # 2. Headers pour les requêtes API Helix avec User Access Token
            # L'API Helix nécessite un User Access Token pour /channels/followed
            client_id = self.twitch_login.token_client_id or CLIENT_ID
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {user_token}"
            }

            # 3. Récupérer l'ID utilisateur depuis le username (déjà disponible)
            user_id = self.twitch_login.get_user_id()
            if not user_id:
                logger.error("❌ User ID introuvable")
                return None

            logger.info(f"🔑 Utilisation API Twitch Helix avec User Access Token")
            logger.info(f"✅ User ID Twitch: {user_id}")

            # 4. Récupérer tous les followers avec pagination (API Helix)
            followers = []
            cursor = None
            start_time = time.time()

            logger.info("🚀 Chargement des followers via API Twitch Helix (rapide)...")

            while True:
                # API Helix: Get Followed Channels
                follows_url = f"https://api.twitch.tv/helix/channels/followed?user_id={user_id}&first=100"
                if cursor:
                    follows_url += f"&after={cursor}"

                follows_response = requests.get(follows_url, headers=headers, timeout=10)
                follows_response.raise_for_status()

                data = follows_response.json()

                # Extraire les noms des streamers (broadcaster_login)
                batch = [follow["broadcaster_login"].lower() for follow in data.get("data", [])]
                followers.extend(batch)

                # Progress log
                elapsed = time.time() - start_time
                rate = len(followers) / elapsed if elapsed > 0 else 0
                logger.info(f"📈 {len(followers)} followers chargés ({rate:.1f}/sec)...")

                # Vérifier s'il y a une page suivante
                cursor = data.get("pagination", {}).get("cursor")
                if not cursor:
                    break

            elapsed = time.time() - start_time
            rate = len(followers) / elapsed if elapsed > 0 else 0
            logger.info(
                f"✅ Total: {len(followers)} followers chargés via API Helix en {elapsed:.1f}s ({rate:.1f}/sec)",
                extra={"emoji": ":rocket:"}
            )

            return followers

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur API Twitch Helix: {e}")
            logger.warning("⚠️ Fallback sur méthode GraphQL (plus lente)")
            return None
        except KeyError as e:
            logger.error(f"❌ Erreur parsing réponse API Helix: {e}")
            logger.warning("⚠️ Fallback sur méthode GraphQL (plus lente)")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur inattendue API Helix: {e}")
            logger.warning("⚠️ Fallback sur méthode GraphQL (plus lente)")
            return None

    def get_followed_streams_online(self, streamer_usernames: list = None):
        """
        🚀 Récupère les streams en ligne des follows via l'API Twitch Helix
        
        Cette méthode est beaucoup plus efficace que de vérifier chaque streamer individuellement.
        Elle récupère tous les streams en ligne d'un coup via l'API Helix.
        
        Args:
            streamer_usernames: Liste optionnelle des usernames à vérifier.
                              Si None, récupère tous les streams en ligne des follows.
        
        Returns:
            dict: {
                'online': set of usernames en ligne,
                'offline': set of usernames hors ligne,
                'streams_data': dict avec infos détaillées des streams
            }
        """
        try:
            # 1. Utiliser le token OAuth User déjà authentifié
            user_token = self.twitch_login.get_auth_token()
            if not user_token:
                logger.warning("⚠️ Pas de token OAuth pour récupérer les streams en ligne")
                return None

            # 2. Headers pour les requêtes API Helix
            client_id = self.twitch_login.token_client_id or CLIENT_ID
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {user_token}"
            }

            # 3. Si aucune liste fournie, récupérer tous les follows d'abord
            if streamer_usernames is None:
                # Récupérer tous les follows
                all_follows = self._get_followers_via_helix_api()
                if not all_follows:
                    logger.warning("⚠️ Impossible de récupérer la liste des follows")
                    return None
                streamer_usernames = all_follows

            # 4. Récupérer les IDs des streamers (nécessaire pour l'API /streams)
            # L'API /streams nécessite des user_id, pas des usernames
            # On va utiliser l'API /users pour convertir usernames -> user_ids
            user_ids = []
            username_to_id = {}
            
            # Diviser en chunks de 100 (limite API Helix)
            chunks = create_chunks(streamer_usernames, 100)
            
            for chunk in chunks:
                # Construire la requête avec plusieurs usernames
                usernames_param = "&".join([f"login={username}" for username in chunk])
                users_url = f"https://api.twitch.tv/helix/users?{usernames_param}"
                
                try:
                    users_response = requests.get(users_url, headers=headers, timeout=10)
                    users_response.raise_for_status()
                    users_data = users_response.json()
                    
                    for user in users_data.get("data", []):
                        user_id = user.get("id")
                        username = user.get("login", "").lower()
                        if user_id and username:
                            user_ids.append(user_id)
                            username_to_id[username] = user_id
                except Exception as e:
                    logger.debug(f"⚠️ Erreur récupération IDs pour chunk: {e}")
                    continue

            if not user_ids:
                logger.warning("⚠️ Aucun ID utilisateur récupéré")
                return None

            # 5. Récupérer les streams en ligne (API /streams)
            # Diviser en chunks de 100 (limite API Helix)
            online_streams = {}
            all_checked_usernames = set()
            
            user_id_chunks = create_chunks(user_ids, 100)
            for chunk in user_id_chunks:
                user_ids_param = "&".join([f"user_id={uid}" for uid in chunk])
                streams_url = f"https://api.twitch.tv/helix/streams?{user_ids_param}&first=100"
                
                try:
                    streams_response = requests.get(streams_url, headers=headers, timeout=10)
                    streams_response.raise_for_status()
                    streams_data = streams_response.json()
                    
                    for stream in streams_data.get("data", []):
                        user_id = stream.get("user_id")
                        username = stream.get("user_login", "").lower()
                        if user_id and username:
                            online_streams[username] = {
                                "user_id": user_id,
                                "game_name": stream.get("game_name", ""),
                                "title": stream.get("title", ""),
                                "viewer_count": stream.get("viewer_count", 0),
                                "started_at": stream.get("started_at", ""),
                            }
                            all_checked_usernames.add(username)
                except Exception as e:
                    logger.debug(f"⚠️ Erreur récupération streams pour chunk: {e}")
                    continue

            # 6. Construire le résultat
            online_usernames = set(online_streams.keys())
            all_usernames_lower = {u.lower() for u in streamer_usernames}
            offline_usernames = all_usernames_lower - online_usernames

            logger.debug(
                f"📊 Streams suivis: {len(online_usernames)} en ligne, {len(offline_usernames)} hors ligne"
            )

            return {
                "online": online_usernames,
                "offline": offline_usernames,
                "streams_data": online_streams
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur API Twitch Helix (streams): {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur inattendue récupération streams: {e}")
            return None

    def monitor_followed_streams(self, streamers, check_interval=60):
        """
        🔄 Surveille automatiquement les streams suivis et met à jour leur statut
        
        Cette méthode utilise l'API Helix pour détecter rapidement les changements
        d'état (en ligne/hors ligne) et met à jour les objets Streamer automatiquement.
        
        Args:
            streamers: Liste des objets Streamer à surveiller
            check_interval: Intervalle de vérification en secondes (défaut: 60)
        """
        while self.running:
            try:
                # Récupérer tous les usernames des streamers suivis
                streamer_usernames = [s.username for s in streamers]
                
                if not streamer_usernames:
                    time.sleep(check_interval)
                    continue

                # Récupérer les streams en ligne via l'API Helix
                streams_status = self.get_followed_streams_online(streamer_usernames)
                
                if not streams_status:
                    # Si l'API échoue, utiliser la méthode individuelle classique
                    logger.debug("⚠️ API Helix échouée, fallback sur vérification individuelle")
                    for streamer in streamers:
                        if time.time() >= streamer.offline_at + 60:
                            self.check_streamer_online(streamer)
                    time.sleep(check_interval)
                    continue

                online_usernames = streams_status["online"]
                offline_usernames = streams_status["offline"]
                streams_data = streams_status.get("streams_data", {})

                # Mettre à jour chaque streamer selon son statut
                for streamer in streamers:
                    username_lower = streamer.username.lower()
                    
                    if username_lower in online_usernames:
                        # Streamer est en ligne selon l'API
                        if not streamer.is_online:
                            # Il vient de passer en ligne !
                            logger.info(
                                f"🟢 {streamer.username} vient de passer EN LIGNE (détecté via API Helix)",
                                extra={"emoji": ":green_circle:", "event": Events.STREAMER_ONLINE}
                            )
                            try:
                                # Mettre à jour les infos du stream
                                self.get_spade_url(streamer)
                                self.update_stream(streamer)
                                streamer.set_online()
                            except Exception as e:
                                logger.debug(f"⚠️ Erreur mise à jour stream {streamer.username}: {e}")
                        else:
                            # Déjà en ligne, juste mettre à jour les infos
                            try:
                                self.update_stream(streamer)
                            except StreamerIsOfflineException:
                                # Le stream vient de s'arrêter entre temps
                                streamer.set_offline()
                            except Exception as e:
                                logger.debug(f"⚠️ Erreur update stream {streamer.username}: {e}")
                    
                    elif username_lower in offline_usernames:
                        # Streamer est hors ligne selon l'API
                        if streamer.is_online:
                            # Il vient de passer hors ligne !
                            logger.info(
                                f"🔴 {streamer.username} vient de passer HORS LIGNE (détecté via API Helix)",
                                extra={"emoji": ":red_circle:", "event": Events.STREAMER_OFFLINE}
                            )
                            streamer.set_offline()
                        # Sinon, déjà hors ligne, rien à faire

                # Attendre avant la prochaine vérification
                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"❌ Erreur dans monitor_followed_streams: {e}", exc_info=True)
                time.sleep(check_interval)

    def get_followers(
        self, limit: int = 10000, order: FollowersOrder = FollowersOrder.ASC, blacklist: list = []
    ):
        # 📂 SOURCE PRINCIPALE : Le fichier GitHub followers_data/username_followers.json
        # 🔄 FALLBACK : API Helix pour mettre à jour le fichier si nécessaire

        # Importer le cache GitHub
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from github_cache import get_github_cache

        github_cache = get_github_cache(self.twitch_login.username)

        # 1. Essayer de charger depuis le fichier JSON (source principale)
        logger.info("📂 Chargement des followers depuis le fichier JSON GitHub...")
        github_followers = github_cache.load_followers()

        if github_followers:
            # Filtrer la blacklist
            if blacklist:
                original_count = len(github_followers)
                github_followers = [f for f in github_followers if f.lower() not in [b.lower() for b in blacklist]]
                if original_count != len(github_followers):
                    logger.info(f"🚫 {original_count - len(github_followers)} streamer(s) blacklisté(s)")

            logger.info(f"✅ {len(github_followers)} followers chargés depuis le fichier JSON")
            return github_followers

        # 2. Si le fichier n'existe pas ou est expiré, utiliser l'API Helix pour le mettre à jour
        logger.info("🔄 Fichier JSON expiré ou absent, mise à jour via API Helix...")
        helix_followers = self._get_followers_via_helix_api()

        if helix_followers is not None and len(helix_followers) > 0:
            # API Helix a réussi, sauvegarder dans le fichier JSON
            try:
                success = github_cache.save_followers(helix_followers)
                if success:
                    logger.info(
                        f"📂 Fichier JSON mis à jour : {len(helix_followers)} followers",
                        extra={"emoji": ":file_folder:"}
                    )
                else:
                    logger.warning("⚠️ Échec sauvegarde fichier JSON (non bloquant)")
            except Exception as e:
                logger.warning(f"⚠️ Erreur sauvegarde fichier JSON : {e}")

            # Filtrer la blacklist
            if blacklist:
                original_count = len(helix_followers)
                helix_followers = [f for f in helix_followers if f.lower() not in [b.lower() for b in blacklist]]
                if original_count != len(helix_followers):
                    logger.info(f"🚫 {original_count - len(helix_followers)} streamer(s) blacklisté(s)")

            return helix_followers
        else:
            # Si l'API Helix échoue aussi, retourner une liste vide
            logger.error("❌ Impossible de charger les followers (fichier JSON absent et API Helix échouée)")
            return []

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
            # logger.debug(
            #     f"Data: {json_data}, Status code: {response.status_code}, Content: {response.text}"
            # )
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
        """
        Met à jour la version du client Twitch en récupérant le build ID depuis twitch.tv.
        Gère les erreurs de connexion de manière gracieuse.
        """
        try:
            # Ajouter un timeout pour éviter les attentes infinies
            response = requests.get(
                URL,
                timeout=5,  # 5 secondes max
                headers={"User-Agent": self.user_agent}
            )
            if response.status_code != 200:
                logger.debug(
                    f"Error with update_client_version: HTTP {response.status_code}"
                )
                return self.client_version
            
            matcher = re.search(self.twilight_build_id_pattern, response.text)
            if not matcher:
                logger.debug("Error with update_client_version: no match found in response")
                return self.client_version
            
            self.client_version = matcher.group(1)
            logger.debug(f"Client version updated: {self.client_version}")
            return self.client_version
            
        except requests.exceptions.Timeout:
            # Timeout - connexion trop lente
            logger.debug("update_client_version: Timeout (connexion trop lente), utilisation version existante")
            return self.client_version
            
        except requests.exceptions.ConnectionError as e:
            # Erreurs de connexion (IncompleteRead, Connection broken, etc.)
            logger.debug(f"update_client_version: Erreur de connexion ({type(e).__name__}), utilisation version existante")
            return self.client_version
            
        except requests.exceptions.RequestException as e:
            # Autres erreurs requests
            logger.debug(f"update_client_version: Erreur requête ({type(e).__name__}), utilisation version existante")
            return self.client_version
        except Exception as e:
            # Erreurs inattendues
            logger.debug(f"update_client_version: Erreur inattendue ({type(e).__name__}: {e}), utilisation version existante")
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
                        # Vérifier que spade_url est défini avant de faire la requête
                        if not streamers[index].stream.spade_url:
                            logger.debug(
                                f"⚠️ spade_url non défini pour {streamers[index]}, récupération..."
                            )
                            try:
                                self.get_spade_url(streamers[index])
                            except Exception as e:
                                logger.debug(
                                    f"⚠️ Impossible de récupérer spade_url pour {streamers[index]}: {e}"
                                )
                                continue
                        
                        # Vérifier à nouveau après tentative de récupération
                        if not streamers[index].stream.spade_url:
                            logger.debug(
                                f"⚠️ spade_url toujours None pour {streamers[index]}, skip..."
                            )
                            continue
                        
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

        # Protection contre response None ou malformée
        if response is None or response == {}:
            return

        if "data" not in response or response["data"] is None:
            return

        if "community" not in response["data"] or response["data"]["community"] is None:
            raise StreamerDoesNotExistException

        channel = response["data"]["community"].get("channel")
        if channel is None:
            return

        # Vérifier que self et communityPoints existent
        if "self" not in channel or channel["self"] is None:
            return

        if "communityPoints" not in channel["self"] or channel["self"]["communityPoints"] is None:
            return

        community_points = channel["self"]["communityPoints"]
        streamer.channel_points = community_points.get("balance", 0)
        streamer.activeMultipliers = community_points.get("activeMultipliers", [])

        if streamer.settings.community_goals is True:
            if "communityPointsSettings" in channel and channel["communityPointsSettings"] is not None:
                if "goals" in channel["communityPointsSettings"]:
                    streamer.community_goals = {
                        goal["id"]: CommunityGoal.from_gql(goal)
                        for goal in channel["communityPointsSettings"]["goals"]
                    }

        if community_points.get("availableClaim") is not None:
            self.claim_bonus(
                streamer, community_points["availableClaim"]["id"])

        if streamer.settings.community_goals is True:
            self.contribute_to_community_goals(streamer)

    def check_predictions_available(self, streamer):
        """
        Vérifie si les prédictions sont disponibles pour un streamer via l'API Helix
        
        Returns:
            True: Prédictions disponibles
            False: Blocage régional confirmé (ne pas continuer)
            None: Incertitude (continuer quand même car peut être temporaire)
        """
        try:
            user_token = self.twitch_login.get_auth_token()
            if not user_token:
                return None  # Pas de token, on ne peut pas vérifier
            
            headers = {
                "Client-ID": CLIENT_ID,
                "Authorization": f"Bearer {user_token}"
            }
            
            # Vérifier les prédictions actives pour ce streamer
            predictions_url = f"https://api.twitch.tv/helix/predictions?broadcaster_id={streamer.channel_id}&first=1"
            response = requests.get(predictions_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                predictions = data.get("data", [])
                # Si on peut récupérer les prédictions, elles sont disponibles
                return True
            elif response.status_code == 403:
                # 403 Forbidden peut indiquer des restrictions régionales ou de permissions
                # Ou simplement un rate limit / erreur temporaire
                try:
                    error_data = response.json()
                    error_message = error_data.get("message", "").lower()
                    
                    # Ne détecter un blocage régional que si le message est explicite
                    # Vérifier des termes plus spécifiques pour éviter les faux positifs
                    explicit_regional_keywords = [
                        "not available in your region",
                        "not available in this region",
                        "geographic restriction",
                        "region locked",
                        "blocked in your region",
                        "unavailable in your geographic"
                    ]
                    
                    # Vérifier si le message contient un terme explicite de blocage régional
                    is_explicitly_blocked = any(keyword in error_message for keyword in explicit_regional_keywords)
                    
                    if is_explicitly_blocked:
                        # Blocage régional confirmé par message explicite
                        return False
                    else:
                        # 403 mais pas de message explicite de blocage régional
                        # Peut être rate limit, permissions temporaires, etc.
                        # On retourne None pour continuer quand même
                        logger.debug(f"⚠️ 403 reçu mais pas de message explicite de blocage régional pour {streamer.username}: {error_message}")
                        return None
                        
                except (ValueError, KeyError) as e:
                    # Erreur parsing JSON - ne peut pas déterminer
                    logger.debug(f"⚠️ Erreur parsing réponse 403 pour {streamer.username}: {e}")
                    return None
            elif response.status_code == 429:
                # Rate limiting - temporaire, continuer
                logger.debug(f"⚠️ Rate limit détecté pour {streamer.username}, continuer quand même")
                return None
            else:
                # Autre erreur - incertitude
                logger.debug(f"⚠️ Status {response.status_code} pour vérification prédictions {streamer.username}")
                return None
        except requests.exceptions.Timeout:
            logger.debug(f"⚠️ Timeout vérification prédictions pour {streamer.username}")
            return None  # Timeout = temporaire, continuer
        except requests.exceptions.RequestException as e:
            logger.debug(f"⚠️ Erreur réseau vérification prédictions pour {streamer.username}: {e}")
            return None  # Erreur réseau = temporaire, continuer
        except Exception as e:
            logger.debug(f"⚠️ Erreur vérification prédictions disponibles pour {streamer.username}: {e}")
            return None  # En cas d'erreur, on ne peut pas déterminer (continuer)
    
    def make_predictions(self, event):
        # Vérifier que l'événement existe toujours et est actif
        if event is None:
            logger.warning(
                "⚠️ Événement None dans make_predictions, impossible de placer le bet",
                extra={
                    "emoji": ":warning:",
                    "event": Events.BET_FAILED,
                },
            )
            return
        
        # Vérifier le statut de l'événement
        if event.status != "ACTIVE":
            logger.info(
                f"⚠️ Événement {event.event_id} n'est plus ACTIVE (statut: {event.status}), bet annulé",
                extra={
                    "emoji": ":warning:",
                    "event": Events.BET_FAILED,
                },
            )
            return

        decision = event.bet.calculate(event.streamer.channel_points)
        # selector_index = 0 if decision["choice"] == "A" else 1

        # Log avec la raison si disponible (pour CROWD_WISDOM)
        reason = decision.get("reason", "")
        strategy = event.streamer.settings.bet.strategy
        
        # Log détaillé de la décision
        log_message = f"🎯 [{strategy}] {event.streamer.username}: {event.title}"
        if reason:
            log_message += f"\n   → {reason}"
        
        # Afficher les stats de l'événement
        total_users = event.bet.total_users
        total_points = event.bet.total_points
        log_message += f"\n   📊 {total_users} votants, {_millify(total_points)} points totaux"
        
        logger.info(
            log_message,
            extra={
                "emoji": ":four_leaf_clover:",
                "event": Events.BET_GENERAL,
            },
        )
        
        # Vérification préventive : vérifier si les prédictions sont disponibles
        predictions_available = self.check_predictions_available(event.streamer)
        if predictions_available is False:
            logger.warning(
                f"⚠️ Prédictions non disponibles (blocage régional probable) pour {event.streamer.username}",
                extra={
                    "emoji": ":no_entry_sign:",
                    "event": Events.BET_FAILED,
                },
            )
            return  # Ne pas essayer de placer le pari
        
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
                        f"Place {_millify(decision['amount'])} channel points on {event.streamer.username}: {event.bet.get_outcome(decision['choice'])}",
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
                        error_code = str(error_info.get("code", "UNKNOWN")).upper()
                        error_message = str(error_info.get("message", "")).strip()
                        
                        # Log full error for debugging if message is empty
                        if not error_message:
                            logger.debug(f"Full error response: {error_info}")
                        
                        # Normaliser le message pour la comparaison (lowercase)
                        error_message_lower = error_message.lower() if error_message else ""
                        
                        # Détecter les erreurs de blocage régional (codes d'erreur Twitch connus)
                        # Codes d'erreur possibles pour restrictions géographiques :
                        # - GEOBLOCKED, REGION_BLOCKED, GEOGRAPHIC_RESTRICTION
                        # - UNAVAILABLE_IN_REGION, NOT_AVAILABLE_IN_YOUR_REGION
                        # - PREDICTION_NOT_AVAILABLE (peut être lié à la région)
                        # - REGION_LOCKED (nouveau code détecté)
                        # Vérifier d'abord le code d'erreur explicite
                        explicit_region_codes = ["REGION_LOCKED", "REGION_BLOCKED", "GEOBLOCKED", 
                                                  "GEOGRAPHIC_RESTRICTION", "UNAVAILABLE_IN_REGION"]
                        
                        # Vérifier des messages explicites dans le message d'erreur
                        explicit_region_messages = [
                            "not available in your region",
                            "not available in this region",
                            "geographic restriction",
                            "region locked",
                            "blocked in your region"
                        ]
                        
                        # Détecter blocage régional seulement si code explicite OU message explicite
                        is_code_explicit = error_code in explicit_region_codes or any(code in error_code for code in ["REGION_LOCKED", "REGION_BLOCKED", "GEOBLOCKED"])
                        is_message_explicit = any(msg in error_message_lower for msg in explicit_region_messages)
                        
                        is_region_blocked = (
                            is_code_explicit or is_message_explicit or
                            # Fallback pour codes moins explicites mais probablement régionaux
                            (("REGION" in error_code and "LOCKED" in error_code) or
                             ("GEO" in error_code and "BLOCKED" in error_code))
                        )
                        
                        if is_region_blocked:
                            # Message plus informatif si le message d'erreur est vide
                            if not error_message:
                                error_display = f"Code: {error_code} (message non fourni par Twitch)"
                            else:
                                error_display = f"Code: {error_code}, Message: {error_message}"
                            
                            logger.error(
                                f"❌ Blocage régional détecté pour les paris! {error_display}",
                                extra={
                                    "emoji": ":no_entry_sign:",
                                    "event": Events.BET_FAILED,
                                },
                            )
                            
                            # Vérifier les scopes du token pour diagnostiquer
                            scope_validation = self.twitch_login.validate_token_scopes()
                            scope_info = ""
                            if scope_validation and scope_validation.get("valid"):
                                scopes = scope_validation.get("scopes", [])
                                required_scopes = ["channel:read:predictions", "channel:manage:predictions"]
                                missing_scopes = [s for s in required_scopes if s not in scopes]
                                
                                if missing_scopes:
                                    scope_info = (
                                        f"\n   ⚠️ PROBLÈME DÉTECTÉ: Votre token OAuth manque les scopes:\n"
                                        f"      - {', '.join(missing_scopes)}\n"
                                        f"   → Régénérez votre token sur https://twitchtokengenerator.com/\n"
                                    )
                                else:
                                    scope_info = (
                                        f"\n   ✅ Votre token OAuth a les bons scopes\n"
                                        f"   → Le problème vient probablement de la RÉGION du serveur Railway\n"
                                    )
                            
                            logger.warning(
                                "💡 Solutions possibles:\n"
                                "   1. Vérifiez que votre token OAuth contient les scopes:\n"
                                "      - channel:read:predictions\n"
                                "      - channel:manage:predictions\n"
                                "   2. 🚨 RÉGION UE (Amsterdam) : Twitch bloque souvent les prédictions dans l'UE\n"
                                "      → Solution Fly.io: Changez la région dans fly.toml (primary_region)\n"
                                "      → Régions recommandées: 'iad' (US), 'sin' (Singapour), 'hnd' (Japon)\n"
                                "      → Command: fly regions set iad\n"
                                "   3. Si vous utilisez Railway, changez la région du service\n"
                                "      → Régions recommandées: US (Washington, Oregon)\n"
                                "   4. Alternative: Utilisez un VPN (mais moins stable pour un serveur)\n"
                                "   5. Certaines régions (ex: UE) ont des restrictions sur les paris Twitch"
                                + scope_info,
                                extra={
                                    "emoji": ":bulb:",
                                    "event": Events.BET_FAILED,
                                },
                            )
                        else:
                            # Message plus informatif si le message d'erreur est vide
                            if not error_message:
                                error_display = f"error code: {error_code} (message non fourni par Twitch)"
                            else:
                                error_display = f"error code: {error_code}, message: {error_message}"
                            
                            logger.error(
                                f"Failed to place bet, {error_display}",
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
            # Protection contre response None ou malformée
            if response is None or response == {}:
                return []

            if "data" not in response or response["data"] is None:
                return []

            if "channel" not in response["data"] or response["data"]["channel"] is None:
                return []

            if response["data"]["channel"]["viewerDropCampaigns"] is None:
                return []

            return [
                item["id"]
                for item in response["data"]["channel"]["viewerDropCampaigns"]
            ]
        except (ValueError, KeyError, TypeError):
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
