# run.py
import logging
import os
import sys
import json
import time
import threading
from pathlib import Path

# Configuration
username = os.getenv("TWITCH_USERNAME")

# MODE D'AUTHENTIFICATION :
# Les tokens OAuth des sites tiers (twitchtokengenerator) n'ont PAS les scopes GraphQL requis
# On utilise donc la méthode TV Login officielle de Twitch (plus fiable)
auth_token = None  # Force l'utilisation du TV Login

if not username:
    print("❌ Configuration manquante : TWITCH_USERNAME requis")
    sys.exit(1)

print("🔐 Mode d'authentification: TV Login (code d'activation Twitch)")

# Sur Fly.io, les cookies sont sauvegardés dans le dossier projet (persiste entre déploiements)
# Vérifier si des cookies existent déjà
if os.getenv("FLY_APP_NAME"):
    cookie_file = Path(f".{username}_cookies.pkl")
else:
    cookie_file = Path("cookies") / f"{username}.pkl"

if cookie_file.exists():
    print(f"✅ Cookies trouvés: {cookie_file}")
    print("💡 Utilisation des cookies sauvegardés (pas de code d'activation requis)")
else:
    print("⚠️ Aucun cookie trouvé")
    print("💡 PREMIÈRE FOIS : Le bot va afficher un code d'activation")
    print("📱 Va sur https://www.twitch.tv/activate et entre le code affiché")
    print("⏳ ATTENTION: Sur Fly.io, tu as 15 minutes pour entrer le code avant timeout")
    
    # Supprimer les anciens cookies obsolètes
    if not os.getenv("FLY_APP_NAME"):
        cookies_dir = Path("cookies")
        if cookies_dir.exists():
            for old_cookie in cookies_dir.glob("*.pkl"):
                try:
                    old_cookie.unlink()
                    print(f"🗑️ Cookie obsolète supprimé: {old_cookie.name}")
                except Exception as e:
                    print(f"⚠️ Erreur suppression: {e}")

# Mode FICHIER JSON : Utilise directement barflyy__followers.json comme liste de streamers
# Le fichier est mis à jour en arrière-plan via l'API Helix pour détecter les nouveaux follows
followers_json_file = Path(f"followers_data/{username}_followers.json")
streamers_from_json = []

# Charger le fichier JSON pour miner (source principale)
if followers_json_file.exists():
    try:
        with open(followers_json_file, 'r') as f:
            data = json.load(f)
        
        if 'followers' in data and isinstance(data['followers'], list) and len(data['followers']) > 0:
            streamers_from_json = data['followers']
            print(f"📂 Fichier JSON chargé : {len(streamers_from_json)} streamer(s)")
            print(f"📂 Source : {followers_json_file}")
            print(f"📂 Dernière mise à jour : {data.get('last_update', 'Inconnue')}")
            USE_FOLLOWERS = False
        else:
            print("⚠️ Fichier JSON invalide ou vide")
            USE_FOLLOWERS = True
    except Exception as e:
        print(f"⚠️ Erreur lecture fichier JSON : {e}")
        USE_FOLLOWERS = True
else:
    print(f"⚠️ Fichier JSON introuvable : {followers_json_file}")
    print("💡 Le fichier sera créé automatiquement via l'API Helix")
    USE_FOLLOWERS = True

# Blacklist optionnelle : streamers à exclure
blacklist_file = Path("blacklist.json")
if blacklist_file.exists():
    with open(blacklist_file, 'r') as f:
        blacklist = json.load(f)
    print(f"🚫 Blacklist: {', '.join(blacklist) if blacklist else 'Aucune'}")
else:
    blacklist = []
    # Créer le fichier blacklist vide
    with open(blacklist_file, 'w') as f:
        json.dump(blacklist, f, indent=2)
    print(f"🚫 Blacklist: Aucune")

print("🎮 Twitch Points Miner")
print(f"👤 User: {username}")

# Pas de fonction webhook - le bot Discord gère toutes les notifications

# Importer le bot
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Settings import Priority, Events
from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition

print("🔧 Configuration du bot...")

# Configuration Discord - SEULEMENT Bot Discord (pas de webhook)
USE_DISCORD_BOT = os.getenv("USE_DISCORD_BOT", "true").lower() == "true"

discord_config = None
if USE_DISCORD_BOT:
    # Mode Bot Discord uniquement (pas de spam webhook)
    discord_config = Discord(
        webhook_api="",  # Pas de webhook
        events=[
            Events.STREAMER_ONLINE,
            Events.STREAMER_OFFLINE,
            Events.GAIN_FOR_RAID,
            Events.GAIN_FOR_CLAIM,
            Events.GAIN_FOR_WATCH,
            Events.GAIN_FOR_WATCH_STREAK,
            Events.BET_WIN,
            Events.BET_LOSE,
            Events.BET_REFUND,
            Events.BET_START,
            Events.BONUS_CLAIM,
            Events.MOMENT_CLAIM,
            Events.JOIN_RAID,
            Events.DROP_CLAIM,
            Events.CHAT_MENTION,
        ],
        use_bot=True  # Mode bot Discord avec fiches éditables
    )
    print("✅ Mode Bot Discord activé (fiches éditables, pas de spam webhook)")

# Configuration avec priorités optimisées et timeouts ajustés
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=auth_token,  # Utilise le token OAuth comme password
    claim_drops_startup=False,
    enable_analytics=False,  # Désactiver analytics pour économiser mémoire
    # Priorités optimisées pour followers
    priority=[
        Priority.STREAK,        # Maintenir les streaks
        Priority.DROPS,         # Récupérer les drops
        Priority.ORDER          # Ordre de la liste/followers
    ],
    logger_settings=LoggerSettings(
        save=True,
        console_level=logging.INFO,
        file_level=logging.DEBUG,
        emoji=True,
        colored=True,
        color_palette=ColorPalette(
            STREAMER_online="GREEN",
            streamer_offline="red",
            BET_lose="red",
            BET_won="green"
        ),
        discord=discord_config,  # ✅ Configuration Discord intégrée
    ),
    streamer_settings=StreamerSettings(
        make_predictions=True,
        follow_raid=True,
        claim_drops=True,
        watch_streak=True,
        bet=BetSettings(
            strategy=Strategy.SMART,
            percentage=5,                     # Parier 5% des points
            percentage_gap=20,                 # Écart de 20% minimum
            max_points=50000,                  # Maximum 50k points par pari
            filter_condition=FilterCondition(
                by=OutcomeKeys.TOTAL_USERS,
                where=Condition.LTE,
                value=800                      # Seulement si moins de 800 votants
            )
        )
    )
)

# Mode FICHIER JSON ou FOLLOWERS
if USE_FOLLOWERS:
    print("🚀 Démarrage du mining en mode FOLLOWERS...")
    print("📋 Le bot va charger les follows via l'API Helix (première fois)")
    if blacklist:
        print(f"🚫 Blacklist active : {len(blacklist)} streamer(s) exclus")
else:
    print("🚀 Démarrage du mining en mode FICHIER JSON...")
    print(f"📋 Le bot va miner {len(streamers_from_json)} streamer(s) depuis le fichier JSON")
    print(f"📂 Fichier utilisé : followers_data/{username}_followers.json")
    print("🔄 Mise à jour du fichier en arrière-plan via l'API Helix (détection nouveaux follows)...")
    if blacklist:
        print(f"🚫 Blacklist active : {len(blacklist)} streamer(s) exclus")

try:
    if USE_FOLLOWERS:
        # Mode FOLLOWERS : Utilise l'API Helix pour charger (première fois seulement)
        # Les streamers dans blacklist.json seront exclus
        twitch_miner.mine(
            streamers=[],  # Liste vide = utilise followers
            blacklist=blacklist,  # Streamers à exclure
            followers=True  # Active le mode followers automatique
        )
    else:
        # Mode FICHIER JSON : Utilise directement le fichier JSON pour miner
        # L'API Helix met à jour le fichier en arrière-plan pour détecter les nouveaux follows
        # Filtrer la blacklist
        streamers_filtered = [s for s in streamers_from_json if s.lower() not in [b.lower() for b in blacklist]]
        if len(streamers_filtered) != len(streamers_from_json):
            print(f"🚫 {len(streamers_from_json) - len(streamers_filtered)} streamer(s) blacklisté(s)")
        
        # Lancer la mise à jour du fichier en arrière-plan (thread séparé)
        # Met à jour le fichier JSON toutes les 5 minutes pour détecter les nouveaux follows
        import threading
        def update_followers_file_loop():
            """Met à jour le fichier JSON via l'API Helix toutes les 5 minutes"""
            # 1. Attendre que l'authentification Twitch soit complète
            max_wait = 300  # Maximum 5 minutes d'attente
            wait_interval = 2  # Vérifier toutes les 2 secondes
            waited = 0
            
            print("⏳ Attente de l'authentification Twitch...")
            while waited < max_wait:
                try:
                    # Vérifier si le token OAuth est disponible
                    auth_token = twitch_miner.twitch.twitch_login.get_auth_token()
                    if auth_token:
                        print("✅ Authentification Twitch complète")
                        break
                except:
                    pass
                
                time.sleep(wait_interval)
                waited += wait_interval
                
                if waited % 30 == 0:  # Afficher un message toutes les 30 secondes
                    print(f"⏳ Attente authentification... ({waited}s)")
            
            if waited >= max_wait:
                print("⚠️ Timeout : authentification Twitch non complète après 5 minutes")
                print("⚠️ La mise à jour périodique du fichier JSON sera ignorée")
                return
            
            # Attendre encore quelques secondes pour que tout soit initialisé
            time.sleep(5)
            
            # 2. Boucle de mise à jour toutes les 5 minutes
            update_interval = 300  # 5 minutes en secondes
            print(f"🔄 Mise à jour automatique du fichier JSON activée (toutes les {update_interval // 60} minutes)")
            
            while True:
                try:
                    print("🔄 Mise à jour du fichier JSON via l'API Helix...")
                    # Utiliser l'API Helix pour récupérer les followers
                    helix_followers = twitch_miner.twitch._get_followers_via_helix_api()
                    if helix_followers and len(helix_followers) > 0:
                        # Sauvegarder dans le fichier JSON
                        import sys
                        sys.path.append(str(Path(__file__).parent))
                        from github_cache import get_github_cache
                        github_cache = get_github_cache(username)
                        success = github_cache.save_followers(helix_followers)
                        if success:
                            # Charger l'ancienne liste pour comparer
                            old_followers = github_cache.load_followers()
                            old_count = len(old_followers) if old_followers else len(streamers_from_json)
                            new_count = len(helix_followers) - old_count
                            
                            print(f"✅ Fichier JSON mis à jour : {len(helix_followers)} followers", end="")
                            if new_count > 0:
                                print(f" (+{new_count} nouveaux)")
                            elif new_count < 0:
                                print(f" ({abs(new_count)} en moins)")
                            else:
                                print(" (aucun changement)")
                        else:
                            print("⚠️ Échec sauvegarde fichier JSON")
                    else:
                        print("⚠️ API Helix n'a pas retourné de followers")
                except Exception as e:
                    print(f"⚠️ Erreur mise à jour fichier JSON : {e}")
                
                # Attendre 5 minutes avant la prochaine mise à jour
                print(f"⏰ Prochaine mise à jour dans {update_interval // 60} minutes...")
                time.sleep(update_interval)
        
        # Lancer la mise à jour en arrière-plan
        update_thread = threading.Thread(target=update_followers_file_loop, daemon=True)
        update_thread.start()
        
        # Miner avec le fichier JSON (sans attendre la mise à jour)
        print(f"🚀 Démarrage du mining avec {len(streamers_filtered)} streamer(s) depuis le fichier JSON")
        print(f"📋 Premiers streamers : {', '.join(streamers_filtered[:5])}{'...' if len(streamers_filtered) > 5 else ''}")
        twitch_miner.mine(
            streamers=streamers_filtered,  # Liste depuis le fichier JSON
            blacklist=blacklist,  # Streamers à exclure
            followers=False  # Désactive le mode followers automatique (on utilise le fichier directement)
        )
        
except KeyboardInterrupt:
    print("\n⏹️ Arrêt...")
except Exception as e:
    print(f"❌ Erreur: {e}")
    raise