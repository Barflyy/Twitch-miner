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
# auth_token = os.getenv("TWITCH_AUTH_TOKEN")  # Utilise le token si fourni, sinon TV Login
auth_token = None  # ⚠️ FORCE TV LOGIN : On ignore le token pour forcer la génération d'un nouveau via code activation

if not username:
    print("❌ Configuration manquante : TWITCH_USERNAME requis")
    sys.exit(1)

if auth_token:
    print("🔐 Mode d'authentification: Token fourni (TWITCH_AUTH_TOKEN)")
else:
    print("🔐 Mode d'authentification: TV Login (code d'activation Twitch)")

# Configuration des chemins persistants
DATA_DIR = Path(os.getenv("DATA_DIR", "."))
if not DATA_DIR.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

print(f"📂 Dossier de données : {DATA_DIR.absolute()}")

# Sur Fly.io, les cookies sont sauvegardés dans le dossier projet (persiste entre déploiements)
# Vérifier si des cookies existent déjà
cookie_file = DATA_DIR / f"{username}_cookies.pkl"

if cookie_file.exists():
    print(f"✅ Cookies trouvés: {cookie_file}")
    # print("💡 Utilisation des cookies sauvegardés (pas de code d'activation requis)")
    # Cookies preservation
    if cookie_file.exists():
        print(f"✅ Cookies trouvés: {cookie_file}")
    else:
        print("ℹ️ Aucun cookie trouvé, une nouvelle session sera créée")
else:
    print("⚠️ Aucun cookie trouvé")
    print("💡 PREMIÈRE FOIS : Le bot va afficher un code d'activation")
    print("📱 Va sur https://www.twitch.tv/activate et entre le code affiché")
    print("⏳ ATTENTION: Sur Fly.io, tu as 15 minutes pour entrer le code avant timeout")
    
    # Supprimer les anciens cookies obsolètes
    # if not os.getenv("FLY_APP_NAME"):
    #     cookies_dir = Path("cookies")
    #     if cookies_dir.exists():
    #         for old_cookie in cookies_dir.glob("*.pkl"):
    #             try:
    #                 old_cookie.unlink()
    #                 print(f"🗑️ Cookie obsolète supprimé: {old_cookie.name}")
    #             except Exception as e:
    #                 print(f"⚠️ Erreur suppression: {e}")

# Mode FICHIER JSON : Utilise directement barflyy__followers.json comme liste de streamers
# Le fichier est mis à jour en arrière-plan via l'API Helix pour détecter les nouveaux follows
followers_dir = DATA_DIR / "followers_data"
if not followers_dir.exists():
    followers_dir.mkdir(parents=True, exist_ok=True)

followers_json_file = followers_dir / f"{username}_followers.json"
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
blacklist_file = DATA_DIR / "blacklist.json"
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
from TwitchChannelPointsMiner.classes.Settings import Priority, Events, FollowersOrder
from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition, DelayMode

# === CONFIGURATION OPTIMALE POUR GAGNER LES PARIS ===
# Stratégie CROWD_WISDOM : Analyse l'intelligence collective des parieurs
# - Détecte les "sharp bettors" (minorité avec gros bets)
# - Analyse le money flow (où va l'argent des gros parieurs)
# - Suit le consensus fort (>70%) quand il existe
from TwitchChannelPointsMiner.classes.Chat import ChatPresence

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
    enable_analytics=True,  # Activer analytics pour le dashboard web
    # Priorités optimisées pour followers
    priority=[
        Priority.STREAK,        # Maintenir les streaks
        Priority.DROPS,         # Récupérer les drops
        Priority.ORDER          # Ordre de la liste/followers
    ],
    logger_settings=LoggerSettings(
        save=True,
        console_level=logging.INFO,
        file_level=logging.WARNING,
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
        make_predictions=True,          # Participer aux prédictions
        follow_raid=True,               # Suivre les raids pour bonus points
        claim_drops=True,               # Réclamer les drops automatiquement
        claim_moments=True,             # Réclamer les Moments Twitch (bonus points)
        watch_streak=True,              # Maintenir les streaks de visionnage
        chat=ChatPresence.ONLINE,       # Rejoindre le chat quand en ligne (augmente watch-time)
        bet=BetSettings(
            # === STRATÉGIE CROWD_WISDOM ===
            # Analyse l'intelligence collective pour maximiser les gains
            # Priorité: Sharp Signals > Strong Consensus > Money Flow > Majorité
            strategy=Strategy.CROWD_WISDOM,
            
            # === GESTION DU RISQUE ===
            percentage=5,               # 5% du solde de base
            percentage_gap=20,          # Écart minimum entre les choix
            max_points=30000,           # Maximum par pari (réduit pour limiter les pertes)
            minimum_points=5000,        # Parier seulement si on a au moins 5k
            
            # === PROTECTION ===
            stealth_mode=True,          # Évite d'être le plus gros parieur
            
            # === TIMING OPTIMISÉ ===
            # Attendre 10 secondes avant la fin pour avoir des données stables
            delay=10,
            delay_mode=DelayMode.FROM_END,
            
            # === FILTRES INTELLIGENTS ===
            # Min 30 votants pour données fiables
            min_voters=30,
            # Ne pas skip les votes divisés (CROWD_WISDOM gère ça intelligemment)
            skip_if_divided=False,
            
            # Filtre: Entre 30 et 500 votants (évite les petites ET grosses prédictions)
            # Les très grosses prédictions ont des odds moins fiables
            filter_condition=FilterCondition(
                by=OutcomeKeys.TOTAL_USERS,
                where=Condition.LTE,        # Less Than or Equal (≤)
                value=500                   # Maximum 500 votants
            ),
        )
    )
)

# Activer le logging vers Discord via fichier partagé
# Le bot Discord lit ce fichier et envoie les logs automatiquement
try:
    from TwitchChannelPointsMiner.classes.DiscordBotLogHandler import setup_discord_bot_logging
    setup_discord_bot_logging()
    print("✅ Logs redirigés vers Discord (via discord_logs_queue.json)")
except Exception as e:
    print(f"⚠️ Erreur configuration logging Discord: {e}")

# Démarrer le serveur Analytics
# host="0.0.0.0" permet l'accès depuis l'extérieur (Docker/Fly.io)
# Port 5001 pour éviter conflit avec AirPlay Receiver (port 5000) sur macOS
print("📊 Démarrage du serveur Analytics sur http://localhost:5001")
twitch_miner.analytics(host="0.0.0.0", port=5001, refresh=5, days_ago=7)

# Mode FICHIER JSON ou FOLLOWERS
if USE_FOLLOWERS:
    print("🚀 Démarrage du mining en mode FOLLOWERS...")
    print("📋 Le bot va charger les follows via l'API Helix (première fois)")
    if blacklist:
        print(f"🚫 Blacklist active : {len(blacklist)} streamer(s) exclus")
else:
    print("🚀 Démarrage du mining en mode FICHIER JSON...")
    print(f"📋 Le bot va miner {len(streamers_from_json)} streamer(s) depuis le fichier JSON")
    print(f"📂 Fichier utilisé : {followers_json_file}")
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
                        from pathlib import Path as PathLib
                        # Utiliser le répertoire courant au lieu de __file__ (non disponible dans thread)
                        current_dir = PathLib.cwd()
                        sys.path.append(str(current_dir))
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