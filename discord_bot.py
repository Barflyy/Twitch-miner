#!/usr/bin/env python3
# discord_bot.py - Bot Discord pour contrôler et monitorer le Twitch Miner

import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
import aiohttp

# Configuration
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))  # Canal pour les commandes
CATEGORY_ID = int(os.getenv("DISCORD_CATEGORY_ID", "0"))  # Catégorie pour les salons streamers

# Configuration des chemins persistants
DATA_DIR = Path(os.getenv("DATA_DIR", "."))
if not DATA_DIR.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE = DATA_DIR / "bot_data.json"
CHANNELS_FILE = DATA_DIR / "streamer_channels.json"

# Intents (avec message_content + guilds pour gérer les salons)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Stockage des salons et messages
streamer_channels = {}  # {streamer: channel_id} - DÉPRÉCIÉ : Utilisé seulement pour compatibilité
streamer_messages = {}  # {streamer: message_id} - DÉPRÉCIÉ : Utilisé seulement pour compatibilité
streamer_data = {}   # {streamer: {stats}}
streamer_data_cache = {}  # Cache pour détecter les changements
category_channels = {}  # {category_id: [channel_ids]} - Suivi des canaux par catégorie
category_cache = {}  # Cache des catégories {category_index: category}
MAX_CHANNELS_PER_CATEGORY = 50  # Limite Discord
last_data_load = 0  # Timestamp du dernier chargement
DATA_CACHE_TTL = 2  # Cache les données pendant 2 secondes (réduit pour détecter plus vite les changements offline)
STATS_CATEGORY_NAME = "📊 Statistiques"  # Nom de la catégorie pour les stats
stats_channel_id = None  # ID du salon de stats
stats_message_id = None  # ID du message de stats
bot_start_time = None  # Heure de démarrage du bot
channels_index = {}  # Index des canaux {streamer_name: channel} pour recherche rapide
channels_index_loaded = False  # Flag pour savoir si l'index est chargé
# Salons de statistiques détaillées
online_count_channel_id = None  # ID du salon "streams en ligne"
followers_count_channel_id = None  # ID du salon "followers Barflyy_"
online_count_message_id = None  # ID du message dans le salon "streams en ligne"
followers_count_message_id = None  # ID du message dans le salon "followers Barflyy_"
TWITCH_USERNAME_TO_TRACK = os.getenv("TWITCH_USERNAME")  # Nom d'utilisateur Twitch à suivre pour les followers

# 🆕 NOUVEAU SYSTÈME : Message épinglé unique
pinned_list_channel_id = None  # ID du salon pour le message épinglé
pinned_list_message_id = None  # ID du message épinglé qui liste tous les streamers
USE_PINNED_MESSAGE = True  # Activer le système de message épinglé (au lieu de salons individuels)

# Noms des catégories et salons (SIMPLIFIÉ)
CATEGORY_NAME = "🟣 TWITCH MINER"
CHANNEL_DASHBOARD = "📊-dashboard"
CHANNEL_LOGS = "📝-logs"

# Anciens noms pour compatibilité (ne pas utiliser)
STATS_CATEGORY_NAME = CATEGORY_NAME
LOGS_CATEGORY_NAME = CATEGORY_NAME
SYSTEM_CATEGORY_NAME = CATEGORY_NAME
CHANNEL_LIST = CHANNEL_DASHBOARD
CHANNEL_GAINS = CHANNEL_LOGS
CHANNEL_DROPS = CHANNEL_LOGS
CHANNEL_ERRORS = CHANNEL_LOGS
CHANNEL_DEBUG = CHANNEL_LOGS

async def get_or_create_discord_category(guild, category_name):
    """Récupère ou crée une catégorie Discord"""
    for cat in guild.categories:
        if cat.name == category_name:
            return cat
    try:
        cat = await guild.create_category(category_name)
        print(f"✅ Catégorie créée: {category_name}")
        return cat
    except Exception as e:
        print(f"❌ Erreur création catégorie {category_name}: {e}")
        return None

async def get_or_create_discord_channel(guild, category, channel_name):
    """Récupère ou crée un salon Discord"""
    channel = discord.utils.get(guild.text_channels, name=channel_name)
    if not channel:
        channel = await guild.create_text_channel(channel_name, category=category)
        print(f"✅ Salon créé: {channel_name}")
    elif channel.category != category:
        await channel.edit(category=category)
    return channel

def get_cache_file_path():
    """Retourne le chemin du fichier de cache (persiste sur Fly.io et local)"""
    # Sur Fly.io et local, sauvegarder dans le répertoire du projet
    return DATA_DIR / "followers_cache.json"

def load_data(force=False):
    """Charge les données depuis le fichier JSON avec cache"""
    global streamer_data, last_data_load
    import time
    
    current_time = time.time()
    
    # Utiliser le cache si récent et pas de force
    if not force and (current_time - last_data_load) < DATA_CACHE_TTL:
        return
    
    try:
        if Path(DATA_FILE).exists():
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                streamer_data = data.get('streamers', {})
        else:
            streamer_data = {}
        last_data_load = current_time
    except Exception as e:
        print(f"❌ Erreur chargement data: {e}")
        streamer_data = {}

def save_data():
    """Sauvegarde les données des streamers dans le fichier JSON"""
    try:
        data = {'streamers': streamer_data}
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"❌ Erreur sauvegarde data: {e}")

def save_channels():
    """Sauvegarde les IDs des salons streamers"""
    try:
        data = {
            'channels': streamer_channels,
            'messages': streamer_messages,
            'category_channels': category_channels,
            'stats_channel_id': stats_channel_id,
            'stats_message_id': stats_message_id,
            'online_count_channel_id': online_count_channel_id,
            'followers_count_channel_id': followers_count_channel_id,
            'online_count_message_id': online_count_message_id,
            'followers_count_message_id': followers_count_message_id,
            'pinned_list_channel_id': pinned_list_channel_id,
            'pinned_list_message_id': pinned_list_message_id,
            'log_channel_id': log_channel_id,  # 💰 Salon unique de logs
            'log_category_id': log_category_id
        }
        with open(CHANNELS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ Erreur sauvegarde channels: {e}")

def load_channels():
    """Charge les IDs des salons streamers"""
    global streamer_channels, streamer_messages, category_channels, stats_channel_id, stats_message_id
    global online_count_channel_id, followers_count_channel_id
    global online_count_message_id, followers_count_message_id
    global pinned_list_channel_id, pinned_list_message_id
    global log_channel_id, log_category_id  # 💰 Salon unique de logs
    try:
        if CHANNELS_FILE.exists():
            with open(CHANNELS_FILE, 'r') as f:
                data = json.load(f)
                streamer_channels = data.get('channels', {})
                streamer_messages = data.get('messages', {})
                category_channels = data.get('category_channels', {})
                stats_channel_id = data.get('stats_channel_id')
                stats_message_id = data.get('stats_message_id')
                online_count_channel_id = data.get('online_count_channel_id')
                followers_count_channel_id = data.get('followers_count_channel_id')
                online_count_message_id = data.get('online_count_message_id')
                followers_count_message_id = data.get('followers_count_message_id')
                pinned_list_channel_id = data.get('pinned_list_channel_id')
                pinned_list_message_id = data.get('pinned_list_message_id')
                # 💰 Charger le salon unique de logs
                log_channel_id = data.get('log_channel_id')
                log_category_id = data.get('log_category_id')
    except Exception as e:
        print(f"❌ Erreur chargement channels: {e}")
        streamer_channels = {}
        streamer_messages = {}
        category_channels = {}
        stats_channel_id = None
        stats_message_id = None
        online_count_channel_id = None
        followers_count_channel_id = None
        online_count_message_id = None
        followers_count_message_id = None
        pinned_list_channel_id = None
        pinned_list_message_id = None

def create_streamer_embed(streamer: str) -> discord.Embed:
    """Crée un embed pour un streamer"""
    data = streamer_data.get(streamer.lower(), {})
    
    # Statut
    is_online = data.get('online', False)
    status_emoji = "🟢" if is_online else "🔴"
    status_text = "En ligne" if is_online else "Hors ligne"
    
    # Points
    balance = data.get('balance', 0)
    balance_display = f"{balance:,.0f}".replace(',', ' ')
    
    # Gains de la session
    session_points = data.get('session_points', 0)
    watch_points = data.get('watch_points', 0)
    bonus_points = data.get('bonus_points', 0)
    
    # Paris
    bets_placed = data.get('bets_placed', 0)
    bets_won = data.get('bets_won', 0)
    bets_lost = data.get('bets_lost', 0)
    
    # Couleur selon statut
    color = 0x00FF00 if is_online else 0x808080
    
    # URL du stream si en ligne
    stream_url = f"https://twitch.tv/{streamer}" if is_online else None
    
    embed = discord.Embed(
        title=f"{status_emoji} {streamer.upper()}",
        description=f"**Statut:** {status_text}",
        color=color,
        timestamp=datetime.utcnow(),
        url=stream_url
    )
    
    # Solde
    embed.add_field(
        name="💎 Solde",
        value=f"**{balance_display}** points",
        inline=False
    )
    
    # Session en cours
    if session_points > 0:
        session_text = f"**+{session_points}** points\n"
        if watch_points > 0:
            session_text += f"└ Watch: +{watch_points}\n"
        if bonus_points > 0:
            session_text += f"└ Bonus: +{bonus_points}\n"
        
        embed.add_field(
            name="💰 Session Actuelle",
            value=session_text,
            inline=True
        )
    
    # Paris
    if bets_placed > 0:
        win_rate = (bets_won / bets_placed * 100) if bets_placed > 0 else 0
        bets_text = f"Placés: **{bets_placed}**\n"
        bets_text += f"✅ Gagnés: {bets_won}\n"
        bets_text += f"❌ Perdus: {bets_lost}\n"
        bets_text += f"📊 Taux: {win_rate:.0f}%"
        
        embed.add_field(
            name="🎲 Paris",
            value=bets_text,
            inline=True
        )
    
    # Temps en ligne
    if is_online and 'online_since' in data:
        online_since = datetime.fromisoformat(data['online_since'])
        duration = datetime.utcnow() - online_since
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        embed.add_field(
            name="⏱️ Durée",
            value=f"{hours}h {minutes}m",
            inline=True
        )
    
    embed.set_footer(text="Twitch Channel Points Miner • Mise à jour auto")
    
    return embed

def create_stats_embed() -> discord.Embed:
    """Crée un embed avec les statistiques globales"""
    global bot_start_time
    
    # Compter les streams en ligne/hors ligne
    total_streamers = len(streamer_data)
    online_streamers = sum(1 for s in streamer_data.values() if s.get('online', False))
    offline_streamers = total_streamers - online_streamers
    
    # Calculer le temps d'activité du bot
    uptime_text = "N/A"
    if bot_start_time:
        uptime = datetime.utcnow() - bot_start_time
        days = int(uptime.total_seconds() // 86400)
        hours = int((uptime.total_seconds() % 86400) // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        
        if days > 0:
            uptime_text = f"{days}j {hours}h {minutes}m"
        elif hours > 0:
            uptime_text = f"{hours}h {minutes}m"
        else:
            uptime_text = f"{minutes}m"
    
    # Calculer les totaux de points
    total_balance = sum(s.get('balance', 0) for s in streamer_data.values())
    total_session_points = sum(s.get('session_points', 0) for s in streamer_data.values())
    
    # Statistiques de paris
    total_bets_placed = sum(s.get('bets_placed', 0) for s in streamer_data.values())
    total_bets_won = sum(s.get('bets_won', 0) for s in streamer_data.values())
    total_bets_lost = sum(s.get('bets_lost', 0) for s in streamer_data.values())
    win_rate = (total_bets_won / total_bets_placed * 100) if total_bets_placed > 0 else 0
    
    # Nombre de salons Discord créés
    total_channels = len(streamer_channels)
    
    embed = discord.Embed(
        title="📊 Statistiques Globales - Twitch Miner",
        description="Statistiques en temps réel du bot de mining",
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    # Statut des streams
    embed.add_field(
        name="📺 Streams",
        value=f"🟢 **{online_streamers}** en ligne\n🔴 **{offline_streamers}** hors ligne\n📋 **{total_streamers}** total",
        inline=True
    )
    
    # Nombre de followers totaux (basé sur les salons Discord créés)
    embed.add_field(
        name="👥 Followers Totaux",
        value=f"📁 **{total_channels}** streamers suivis\n💬 Salons Discord créés\n🔄 Mise à jour: 30s",
        inline=True
    )
    
    # Temps d'activité
    embed.add_field(
        name="⏱️ Temps d'activité",
        value=f"🟢 **{uptime_text}**",
        inline=True
    )
    
    # Points totaux
    balance_display = f"{total_balance:,.0f}".replace(',', ' ')
    session_display = f"{total_session_points:,.0f}".replace(',', ' ')
    embed.add_field(
        name="💎 Points Totaux",
        value=f"💰 Solde: **{balance_display}**\n📈 Session: **+{session_display}**",
        inline=True
    )
    
    # Statistiques de paris
    if total_bets_placed > 0:
        embed.add_field(
            name="🎲 Paris",
            value=f"🎯 Placés: **{total_bets_placed}**\n✅ Gagnés: **{total_bets_won}**\n❌ Perdus: **{total_bets_lost}**\n📊 Taux: **{win_rate:.1f}%**",
            inline=True
        )
    
    # Nombre de catégories
    if CATEGORY_ID:
        try:
            category = bot.get_channel(CATEGORY_ID)
            if category:
                categories_count = len([c for c in category.guild.categories if c.name.startswith(category.name)])
                embed.add_field(
                    name="📁 Catégories",
                    value=f"📂 **{categories_count}** catégorie(s)\n📊 Max: 50 canaux/catégorie",
                    inline=True
                )
        except:
            pass
    
    embed.set_footer(text="Twitch Channel Points Miner • Statistiques globales")
    
    return embed

async def get_or_create_stats_category(guild):
    """Récupère ou crée la catégorie de statistiques"""
    # Chercher par nom
    for cat in guild.categories:
        if cat.name == STATS_CATEGORY_NAME:
            return cat
            
    # Créer si n'existe pas
    try:
        cat = await guild.create_category(STATS_CATEGORY_NAME, position=0)
        print(f"✅ Catégorie stats créée: {STATS_CATEGORY_NAME}")
        return cat
    except Exception as e:
        print(f"❌ Erreur création catégorie stats: {e}")
        return None

async def update_stats_channel(guild):
    """Crée ou met à jour le salon de statistiques"""
    global stats_channel_id, stats_message_id
    
    try:
        # Attendre que les données soient chargées
        if len(streamer_data) == 0:
            return  # Ne rien faire tant que les données ne sont pas prêtes
        
        stats_category = await get_or_create_stats_category(guild)
        if not stats_category:
            return
        
        # Placer la catégorie en haut (position 0) - toujours en premier
        try:
            # Essayer de mettre la catégorie en position 0 (tout en haut)
            if stats_category.position != 0:
                await stats_category.edit(position=0)
                print(f"📌 Catégorie stats déplacée en haut (position 0)")
        except discord.Forbidden:
            print(f"⚠️  Permission insuffisante pour déplacer la catégorie stats")
        except Exception as e:
            print(f"⚠️  Erreur déplacement catégorie stats: {e}")
        
        channel_name = "📊-statistiques-globales"
        
        # Si le salon existe déjà
        if stats_channel_id:
            channel = guild.get_channel(stats_channel_id)
            if not channel:
                # Le salon a été supprimé, le recréer
                stats_channel_id = None
                stats_message_id = None
        
        # Créer le salon s'il n'existe pas
        if not stats_channel_id:
            # Vérifier si un salon avec ce nom existe déjà
            existing_channel = None
            for ch in stats_category.channels:
                if isinstance(ch, discord.TextChannel) and ch.name == channel_name:
                    existing_channel = ch
                    break
            
            if existing_channel:
                stats_channel_id = existing_channel.id
                channel = existing_channel
                print(f"🔍 Salon stats existant trouvé: {channel_name}")
            else:
                # Créer le nouveau salon
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=stats_category,
                    position=0  # Placer en haut de la catégorie
                )
                stats_channel_id = channel.id
                print(f"✅ Salon stats créé: {channel_name}")
                save_channels()
        else:
            channel = guild.get_channel(stats_channel_id)
            if not channel:
                return
        
        # Créer ou mettre à jour le message de stats
        embed = create_stats_embed()
        
        if stats_message_id:
            try:
                message = await channel.fetch_message(stats_message_id)
                await message.edit(embed=embed)
                # Log silencieux : pas de spam
            except discord.NotFound:
                # Message supprimé, en créer un nouveau
                message = await channel.send(embed=embed)
                stats_message_id = message.id
                save_channels()
                print(f"✅ Message stats globales recréé")
        else:
            # Créer le message initial
            message = await channel.send(embed=embed)
            stats_message_id = message.id
            save_channels()
            print(f"✅ Message stats globales créé")
            
    except Exception as e:
        print(f"❌ Erreur update_stats_channel: {e}")
        import traceback
        traceback.print_exc()

async def get_twitch_followers_count(username: str) -> int:
    """Récupère le nombre de followers d'un utilisateur Twitch via l'API GraphQL publique"""
    try:
        # Utiliser l'API GraphQL publique de Twitch
        async with aiohttp.ClientSession() as session:
            gql_url = "https://gql.twitch.tv/gql"
            headers = {
                "Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko"  # Client ID public de Twitch
            }
            gql_payload = {
                "query": """
                query($login: String!) {
                    user(login: $login) {
                        followers {
                            totalCount
                        }
                    }
                }
                """,
                "variables": {"login": username}
            }
            async with session.post(gql_url, json=gql_payload, headers=headers) as gql_response:
                if gql_response.status == 200:
                    gql_data = await gql_response.json()
                    if "data" in gql_data and "user" in gql_data["data"]:
                        if gql_data["data"]["user"] and "followers" in gql_data["data"]["user"]:
                            return gql_data["data"]["user"]["followers"].get("totalCount", 0)
        return 0
    except Exception as e:
        print(f"❌ Erreur récupération followers pour {username}: {e}")
        return 0

async def check_twitch_last_stream(username: str) -> dict:
    """Vérifie quand un streamer a stream pour la dernière fois via l'API Twitch publique
    
    Returns:
        dict: {
            'is_live': bool,
            'last_stream_ago_days': int or None,
            'error': str or None
        }
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Utiliser l'API GraphQL publique de Twitch
            gql_url = "https://gql.twitch.tv/gql"
            headers = {
                "Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko"
            }
            
            # Query pour récupérer les infos du streamer
            gql_payload = {
                "query": """
                query($login: String!) {
                    user(login: $login) {
                        stream {
                            id
                        }
                        lastBroadcast {
                            startedAt
                        }
                    }
                }
                """,
                "variables": {"login": username}
            }
            
            async with session.post(gql_url, json=gql_payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if "data" in data and "user" in data["data"] and data["data"]["user"]:
                        user = data["data"]["user"]
                        
                        # Vérifier si en ligne
                        is_live = user.get("stream") is not None
                        
                        # Calculer le temps depuis le dernier stream
                        last_broadcast = user.get("lastBroadcast")
                        days_ago = None
                        
                        if last_broadcast and "startedAt" in last_broadcast:
                            from datetime import datetime
                            last_stream_time = datetime.fromisoformat(last_broadcast["startedAt"].replace("Z", "+00:00"))
                            days_ago = (datetime.now(last_stream_time.tzinfo) - last_stream_time).days
                        
                        return {
                            'is_live': is_live,
                            'last_stream_ago_days': days_ago,
                            'error': None
                        }
                
                return {'is_live': False, 'last_stream_ago_days': None, 'error': f'API returned {response.status}'}
        
    except Exception as e:
        return {'is_live': False, 'last_stream_ago_days': None, 'error': str(e)}

async def get_last_stream_dates_batch(usernames: list) -> dict:
    """🚀 Récupère la dernière date de stream pour plusieurs streamers en batch via API Helix
    
    Args:
        usernames: Liste des usernames à vérifier
    
    Returns:
        dict: {username: {'days_ago': int, 'last_stream_date': str or None}}
    """
    results = {}
    
    try:
        # Utiliser l'API Helix /videos pour récupérer les dernières vidéos
        # On doit d'abord récupérer les user_ids
        async with aiohttp.ClientSession() as session:
            CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # Client ID public Twitch
            
            # Diviser en chunks de 100 (limite API Helix)
            chunks = [usernames[i:i+100] for i in range(0, len(usernames), 100)]
            username_to_id = {}
            
            # Étape 1: Convertir usernames -> user_ids
            for chunk in chunks:
                usernames_param = "&".join([f"login={username}" for username in chunk])
                users_url = f"https://api.twitch.tv/helix/users?{usernames_param}"
                headers = {"Client-ID": CLIENT_ID}
                
                async with session.get(users_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        for user in data.get("data", []):
                            username_to_id[user.get("login", "").lower()] = user.get("id")
            
            # Étape 2: Récupérer les dernières vidéos pour chaque user_id
            for username in usernames:
                username_lower = username.lower()
                user_id = username_to_id.get(username_lower)
                
                if not user_id:
                    results[username_lower] = {'days_ago': None, 'last_stream_date': None}
                    continue
                
                # Récupérer la dernière vidéo (type=archive = streams archivés)
                videos_url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&type=archive&first=1"
                headers = {"Client-ID": CLIENT_ID}
                
                async with session.get(videos_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        videos = data.get("data", [])
                        
                        if videos:
                            # Prendre la vidéo la plus récente
                            last_video = videos[0]
                            created_at = last_video.get("created_at")
                            
                            if created_at:
                                from datetime import datetime
                                last_stream_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                                days_ago = (datetime.now(last_stream_time.tzinfo) - last_stream_time).days
                                results[username_lower] = {
                                    'days_ago': days_ago,
                                    'last_stream_date': created_at
                                }
                            else:
                                results[username_lower] = {'days_ago': None, 'last_stream_date': None}
                        else:
                            # Pas de vidéos = jamais streamé ou pas de VODs
                            results[username_lower] = {'days_ago': None, 'last_stream_date': None}
                    else:
                        results[username_lower] = {'days_ago': None, 'last_stream_date': None}
                
                # Rate limiting: pause toutes les 20 requêtes
                if list(results.keys()).index(username_lower) % 20 == 0:
                    await asyncio.sleep(0.5)
    
    except Exception as e:
        print(f"❌ Erreur get_last_stream_dates_batch: {e}")
        # En cas d'erreur, retourner None pour tous
        for username in usernames:
            results[username.lower()] = {'days_ago': None, 'last_stream_date': None}
    
    return results

async def update_stats_channels(guild):
    """(Désactivé) Ancienne fonction pour le compteur de streams en ligne"""
    pass

# ═══════════════════════════════════════════════════════════════════
# 📊 SYSTÈME DE LOGS DISCORD
# ═══════════════════════════════════════════════════════════════════

async def create_log_channels(guild):
    """Crée automatiquement la catégorie 'Gains' et le salon unique pour points/bets"""
    global log_category_id, log_channel_id

    try:
        category_name = "💰 Gains"

        # Supprimer l'ancienne catégorie "📊 Administration" si elle existe
        for cat in guild.categories:
            if cat.name == "📊 Administration":
                print(f"🗑️ Suppression de l'ancienne catégorie {cat.name}...")
                for channel in cat.channels:
                    await channel.delete()
                await cat.delete()
                print(f"✅ Ancienne catégorie supprimée")
                break

        # Chercher si la nouvelle catégorie existe déjà
        category = None
        for cat in guild.categories:
            if cat.name == category_name:
                category = cat
                log_category_id = cat.id
                print(f"✅ Catégorie {category_name} trouvée")
                break

        # Créer la catégorie si elle n'existe pas
        if not category:
            print(f"📁 Création de la catégorie {category_name}...")
            category = await guild.create_category(category_name)
            log_category_id = category.id
            print(f"✅ Catégorie {category_name} créée")

        # Créer ou récupérer le salon unique
        channel_name = "💰-gains-et-bets"
        topic = "Points gagnés, bets placés, résultats des paris"

        # Chercher si le salon existe déjà dans la catégorie
        channel = discord.utils.get(category.channels, name=channel_name)

        if not channel:
            print(f"📝 Création du salon {channel_name}...")
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=topic
            )
            print(f"✅ Salon {channel_name} créé")
        else:
            print(f"✅ Salon {channel_name} existant trouvé")

        log_channel_id = channel.id

        save_channels()
        print("✅ Salon de logs configuré et sauvegardé")
        return True

    except Exception as e:
        print(f"❌ Erreur création salon de logs: {e}")
        import traceback
        traceback.print_exc()
        return False

@tasks.loop(seconds=3)
async def process_log_queue():
    """Traite la file d'attente des logs et les envoie dans le salon unique"""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            # Importer SharedLogQueue
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent))
            from TwitchChannelPointsMiner.classes.DiscordBotLogHandler import SharedLogQueue

            # Lire les logs depuis le fichier partagé
            shared_queue = SharedLogQueue()
            logs_from_file = shared_queue.get_logs(clear=True)

            if not logs_from_file:
                await asyncio.sleep(3)
                continue

            # Convertir timestamps
            from datetime import datetime
            all_logs = []
            for log_entry in logs_from_file:
                try:
                    log_entry['timestamp'] = datetime.fromisoformat(log_entry['timestamp'])
                except:
                    log_entry['timestamp'] = datetime.now()
                all_logs.append(log_entry)

            if not all_logs:
                await asyncio.sleep(3)
                continue

            # Récupérer le salon de logs unique
            log_channel = bot.get_channel(log_channel_id)
            if not log_channel:
                # Essayer de le trouver par nom
                log_channel = discord.utils.get(bot.get_all_channels(), name=CHANNEL_LOGS)
                if not log_channel:
                    await asyncio.sleep(3)
                    continue

            # Grouper par TYPE (pour avoir des embeds de couleurs différentes)
            # On utilise des clés virtuelles pour send_batch_to_channel
            logs_by_type = {
                "DROPS": [],
                "ERRORS": [],
                "GAINS": [],
                "DEBUG": []
            }
            
            for log in all_logs:
                msg = log.get('message', '')
                level = log.get('level', 'INFO')
                
                if "DROP" in msg.upper() or "CLAIM" in msg.upper() and "drop" in msg.lower():
                    logs_by_type["DROPS"].append(log)
                elif level in ["ERROR", "CRITICAL"] or "Exception" in msg or "❌" in msg:
                    logs_by_type["ERRORS"].append(log)
                elif any(keyword in msg.upper() for keyword in ["BET", "WIN", "LOSE", "BONUS", "POINTS", "PLACE", "RAID"]):
                    logs_by_type["GAINS"].append(log)
                else:
                    logs_by_type["DEBUG"].append(log)
            
            # Envoyer chaque groupe comme un embed séparé dans le MÊME salon
            for type_name, logs in logs_by_type.items():
                if logs:
                    await send_batch_to_channel(log_channel, logs, type_name)
                        
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"❌ Erreur process_log_queue: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(3)

async def send_batch_to_channel(channel, logs, type_name="DEBUG"):
    """Envoie un batch de logs dans un salon spécifique avec le bon format"""
    if not logs:
        return

    from datetime import datetime
    import re
    
    # Déterminer couleur et icône selon le type de log
    color = 0x9146FF  # Purple par défaut
    icon = "📝"
    title = "Logs Système"
    
    if type_name == "DROPS":
        color = 0x3498DB  # Bleu
        icon = "🎁"
        title = "Drops & Récompenses"
    elif type_name == "ERRORS":
        color = 0xE74C3C  # Rouge
        icon = "🚨"
        title = "Alertes & Erreurs"
    elif type_name == "GAINS":
        # Analyser le contenu pour déterminer la couleur
        full_text = " ".join([l.get('message', '') for l in logs])
        if "BET_WIN" in full_text or "won" in full_text.lower():
            color = 0xFFD700  # Or
            icon = "🏆"
            title = "Victoire !"
        elif "BET_LOSE" in full_text or "lost" in full_text.lower():
            color = 0xE74C3C  # Rouge
            icon = "💸"
            title = "Défaite..."
        elif "Place" in full_text and "points on" in full_text:
            color = 0x9146FF  # Purple
            icon = "🎲"
            title = "Pari Placé"
        else:
            color = 0x2ECC71  # Vert
            icon = "💰"
            title = "Gains de Points"
    
    # Créer l'embed
    embed = discord.Embed(
        title=f"{icon} {title}",
        color=color,
        timestamp=datetime.utcnow()
    )
    
    # Formater les messages
    description_lines = []
    
    for log in logs:
        # Timestamp court (HH:MM)
        try:
            timestamp = log['timestamp'].strftime('%H:%M')
        except:
            timestamp = "??:??"
            
        msg = log.get('message', '')
        
        # 🎯 FORMATAGE AMÉLIORÉ
        formatted_msg = msg
        
        # 1. Pari placé (Nouveau format avec streamer inclus)
        # Log: "Place 160 channel points on STREAMER: CHOICE (COLOR), Points: ..., Users: ..."
        if "Place" in msg and "channel points on" in msg:
            # Regex pour le nouveau format (avec streamer)
            match = re.search(r'Place (.+?) channel points on (.+?): (.+?), Points: (.+?), Users: (.+?) \((.+?)%\)', msg)
            # Regex fallback pour l'ancien format (sans streamer)
            match_old = re.search(r'Place (.+?) channel points on: (.+?), Points: (.+?), Users: (.+?) \((.+?)%\)', msg)
            
            if match:
                amount, streamer, choice, total_points, users, percentage = match.groups()
            elif match_old:
                amount, choice, total_points, users, percentage = match_old.groups()
                # Essayer de trouver le streamer ailleurs ou mettre ?
                streamer_match = re.search(r'Streamer\(username=([^,]+)', msg)
                streamer = streamer_match.group(1) if streamer_match else "?"
            else:
                amount, streamer, choice, total_points, users, percentage = None, None, None, None, None, None

            if amount:
                formatted_msg = (
                    f"**🎲 Pari sur {streamer}**\n"
                    f"```yaml\n"
                    f"Mise   : {amount} pts\n"
                    f"Choix  : {choice}\n"
                    f"Vote   : {percentage}% ({users} votants)\n"
                    f"Total  : {total_points} pts\n"
                    f"```"
                )
        
        # 2. Résultat de pari (victoire)
        elif "won" in msg.lower() and "+" in msg:
            match = re.search(r'([+-]\d+)\s*→\s*Streamer\(username=([^,]+)', msg)
            if match:
                points, streamer = match.groups()
                formatted_msg = f"**🏆 {streamer}** • `+{points} pts` • *Victoire*"
        
        # 3. Résultat de pari (défaite)
        elif "lost" in msg.lower() and "-" in msg:
            match = re.search(r'([+-]\d+)\s*→\s*Streamer\(username=([^,]+)', msg)
            if match:
                points, streamer = match.groups()
                formatted_msg = f"**💸 {streamer}** • `{points} pts` • *Défaite*"
        
        # 4. Gains réguliers (watch, claim, raid)
        elif "→" in msg and "Reason:" in msg and "BET" not in msg.upper():
            match = re.search(r'([+-]\d+)\s*→\s*Streamer\(username=([^,]+),.+?Reason:\s*(\w+)', msg)
            if match:
                points, streamer, reason = match.groups()
                reason_map = {
                    "WATCH": "👁️ Visionnage",
                    "CLAIM": "🎁 Coffre",
                    "RAID": "⚔️ Raid",
                    "WATCH_STREAK": "🔥 Série"
                }
                reason_text = reason_map.get(reason, reason.lower())
                formatted_msg = f"**{streamer}** • `+{points} pts` • *{reason_text}*"
        
        # 5. Bonus claims
        elif "Claiming the bonus" in msg or "BONUS" in msg.upper():
            match = re.search(r'Streamer\(username=([^,]+)', msg)
            if match:
                streamer = match.group(1)
                formatted_msg = f"**{streamer}** • `+50 pts` • *Bonus 🎁*"
        
        # 6. Raids (Nouveau !)
        elif "Joining raid" in msg:
            # Log: "Joining raid from Streamer(username=forky, ...) to spoodah!"
            match = re.search(r'Joining raid from Streamer\(username=([^,]+).+? to (.+?)!', msg)
            if match:
                raider, target = match.groups()
                formatted_msg = f"**⚔️ Raid** : **{raider}** ➡️ **{target}**"
        
        # 7. Code d'activation (CRITIQUE)
        elif "activate" in msg.lower() and "code" in msg.lower():
            if "Open https://www.twitch.tv/activate" in msg:
                formatted_msg = f"🚨 **ACTION REQUISE** 🚨\n> Ouvre : https://www.twitch.tv/activate"
            elif "enter this code:" in msg:
                match = re.search(r'code:\s*([A-Z0-9]+)', msg)
                if match:
                    code = match.group(1)
                    formatted_msg = f"🔑 **CODE** : `{code}`"
            elif "Hurry up" in msg:
                formatted_msg = f"⏰ **Vite !** Expire dans 30 minutes"
        
        # Tronquer si trop long
        if len(formatted_msg) > 300:
            formatted_msg = formatted_msg[:297] + "..."
        
        description_lines.append(f"`{timestamp}` {formatted_msg}")
    
    embed.description = "\n".join(description_lines)
    
    # Limite Discord
    if len(embed.description) > 4000:
        embed.description = embed.description[:3997] + "..."
    
    embed.set_footer(
        text="Twitch Miner • v3.0",
        icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Twitch_Glitch_Logo_Purple.svg/878px-Twitch_Glitch_Logo_Purple.svg.png"
    )
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Erreur envoi log vers {channel.name}: {e}")

# ═══════════════════════════════════════════════════════════════════



@bot.command(name="sync")
async def sync(ctx):
    """Synchronise les commandes slash (instantané pour ce serveur)"""
    try:
        # Synchroniser uniquement sur ce serveur (instantané)
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ {len(synced)} commandes synchronisées pour ce serveur !")
    except Exception as e:
        await ctx.send(f"❌ Erreur de synchronisation : {e}")

@bot.command(name="reload")
async def reload_msg(ctx):
    """Commande !reload : Recharge les données (version message)"""
    try:
        load_data(force=True)
        load_channels()
        await ctx.send("✅ Données et configuration rechargées avec succès !")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors du rechargement : {e}")

@bot.tree.command(name="status", description="Affiche l'état du bot et des statistiques rapides")
async def status_command(interaction: discord.Interaction):
    """Commande /status : Affiche l'état du bot"""
    # Calculer l'uptime
    uptime_text = "N/A"
    if bot_start_time:
        uptime = datetime.utcnow() - bot_start_time
        days = int(uptime.total_seconds() // 86400)
        hours = int((uptime.total_seconds() % 86400) // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        if days > 0:
            uptime_text = f"{days}j {hours}h {minutes}m"
        else:
            uptime_text = f"{hours}h {minutes}m"

    # Stats rapides
    total_streamers = len(streamer_data)
    online_streamers = sum(1 for s in streamer_data.values() if s.get('online', False))
    
    embed = discord.Embed(
        title="🤖 Statut du Bot",
        color=0x00FF00,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="⏱️ Uptime", value=uptime_text, inline=True)
    embed.add_field(name="📺 Streamers", value=f"**{online_streamers}** en ligne\n**{total_streamers}** total", inline=True)
    embed.add_field(name="💾 Persistance", value="✅ Active (/data)", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reload", description="Recharge la configuration et les données")
async def reload_command(interaction: discord.Interaction):
    """Commande /reload : Recharge les données"""
    await interaction.response.defer(ephemeral=True)
    try:
        load_data(force=True)
        load_channels()
        await interaction.followup.send("✅ Données et configuration rechargées avec succès !", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors du rechargement : {e}", ephemeral=True)

# ═══════════════════════════════════════════════════════════════════
# 🚀 CONFIGURATION COMPLÈTE DES SALONS DISCORD
# ═══════════════════════════════════════════════════════════════════

async def setup_all_channels(guild):
    """Configure les salons Discord (Version Simplifiée)"""
    global log_channel_id, stats_channel_id, pinned_list_channel_id
    
    try:
        print("📁 Création de la structure Discord simplifiée...")
        
        # 1. Catégorie Unique
        category = await get_or_create_discord_category(guild, CATEGORY_NAME)
        if not category:
            return False
            
        # 2. Salon Dashboard (Stats + Liste)
        dash_chan = await get_or_create_discord_channel(guild, category, CHANNEL_DASHBOARD)
        # Permissions : Lecture seule pour @everyone
        await dash_chan.set_permissions(guild.default_role, send_messages=False, read_messages=True)
        
        stats_channel_id = dash_chan.id
        pinned_list_channel_id = dash_chan.id  # Le dashboard sert aussi de liste
        
        # 3. Salon Logs (Tout en un)
        logs_chan = await get_or_create_discord_channel(guild, category, CHANNEL_LOGS)
        # Permissions : Lecture seule pour @everyone
        await logs_chan.set_permissions(guild.default_role, send_messages=False, read_messages=True)
        
        log_channel_id = logs_chan.id
        
        # Nettoyage des anciennes catégories (optionnel mais propre)
        for cat in guild.categories:
            if cat.name in ["📊 Statistiques", "📝 Logs & Activité", "⚙️ Système", "💰 Gains", "📺 TWITCH MINER - LISTE"]:
                if cat.id != category.id:
                    print(f"🗑️ Suppression ancienne catégorie: {cat.name}")
                    for ch in cat.channels:
                        await ch.delete()
                    await cat.delete()

        save_channels()
        print("✅ Structure Discord simplifiée configurée !")
        return True
        
    except Exception as e:
        print(f"❌ Erreur setup_all_channels: {e}")
        import traceback
        traceback.print_exc()
        return False

# ═══════════════════════════════════════════════════════════════════
# 🤖 ÉVÉNEMENTS DU BOT
# ═══════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    global bot_start_time, pinned_list_channel_id, pinned_list_message_id
    bot_start_time = datetime.utcnow()
    
    print(f'✅ Bot connecté: {bot.user.name}')
    print(f'📋 ID: {bot.user.id}')

    # Synchroniser les commandes slash
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} commandes slash synchronisées")
    except Exception as e:
        print(f"❌ Erreur synchro commandes slash: {e}")
    
    # Charger les données
    load_channels()
    load_data(force=True)
    
    # 🚀 OPTIMISATION : Nettoyage agressif au démarrage
    # 🚀 OPTIMISATION : Nettoyage agressif au démarrage
    if USE_PINNED_MESSAGE:
        # Attendre que les guilds soient disponibles
        if not bot.guilds:
            print("⏳ Attente de la disponibilité des serveurs Discord...")
            await asyncio.sleep(5)
        
        print(f"📋 Serveurs trouvés : {len(bot.guilds)}")
        
        for guild in bot.guilds:
            print(f"🔧 Configuration du serveur : {guild.name}")
            print("🧹 Nettoyage complet des anciens salons (MODE NUCLÉAIRE)...")
            
            # 1. Supprimer les catégories obsolètes (et tout ce qu'elles contiennent)
            old_categories = ["📊 Statistiques", "📝 Logs & Activité", "⚙️ Système", "💰 Gains", "📺 TWITCH MINER - LISTE"]
            
            categories = list(guild.categories)
            for cat in categories:
                if cat.name in old_categories:
                    print(f"🗑️ Suppression catégorie obsolète: {cat.name}")
                    for ch in cat.channels:
                        try:
                            await ch.delete()
                            await asyncio.sleep(0.2)
                        except Exception as e:
                            print(f"⚠️ Erreur suppression salon {ch.name}: {e}")
                    try:
                        await cat.delete()
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"⚠️ Erreur suppression catégorie {cat.name}: {e}")

            # 2. Supprimer les salons orphelins ou mal placés (MODE NUCLÉAIRE)
            # On supprime TOUT ce qui ressemble à un salon de bot, peu importe où il est
            orphan_channels = ["📋-liste-streamers", "💰-gains-et-bets", "📦-drops-loot", "🚨-alertes-erreurs", "📝-logs-debug"]
            
            text_channels = list(guild.text_channels)
            for ch in text_channels:
                # Supprimer si nom exact dans la liste des orphelins
                if ch.name in orphan_channels:
                    try:
                        print(f"🗑️ Suppression salon orphelin: {ch.name}")
                        await ch.delete()
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        print(f"⚠️ Erreur suppression salon orphelin {ch.name}: {e}")
                
                # Supprimer si c'est un salon de streamer individuel (🟢-nom ou 🔴-nom)
                elif ch.name.startswith("🟢-") or ch.name.startswith("🔴-"):
                    try:
                        print(f"🗑️ Suppression salon streamer individuel: {ch.name}")
                        await ch.delete()
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        print(f"⚠️ Erreur suppression salon streamer {ch.name}: {e}")
                
                # Supprimer si c'est un salon de stats (ex: 🟢│X-streams-en-ligne)
                elif "streams-en-ligne" in ch.name or "followers-barflyy" in ch.name.lower():
                    try:
                        print(f"🗑️ Suppression salon stats: {ch.name}")
                        await ch.delete()
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        print(f"⚠️ Erreur suppression salon stats {ch.name}: {e}")

            # 📊 Créer la nouvelle structure unique
            print("📁 Configuration de la nouvelle structure Discord...")
            await setup_all_channels(guild)
            
            # Créer/Mettre à jour le message épinglé
            await create_or_update_pinned_list(guild)

            break  # On ne gère que le premier serveur pour l'instant
    
    # Initialiser le cache
    global streamer_data_cache
    streamer_data_cache = {k: v.copy() for k, v in streamer_data.items()}
    
    # Démarrer les boucles
    if not update_channels.is_running():
        update_channels.start()

    if not process_log_queue.is_running():
        process_log_queue.start()
        print("📊 Traitement des logs Discord activé")

    print("🚀 Bot opérationnel et optimisé !")

def count_channels_in_category(category):
    """Compte le nombre de canaux textuels dans une catégorie"""
    if not category:
        return 0
    return len([ch for ch in category.channels if isinstance(ch, discord.TextChannel)])

async def get_or_create_category(guild, base_category, category_index):
    """Récupère ou crée une catégorie pour les streamers (avec cache)"""
    if category_index == 0:
        # Utiliser la catégorie de base
        return base_category
    
    # Vérifier le cache
    if category_index in category_cache:
        cached_cat = category_cache[category_index]
        # Vérifier que la catégorie existe toujours
        if cached_cat in guild.categories:
            return cached_cat
        else:
            # Catégorie supprimée, retirer du cache
            del category_cache[category_index]
    
    # Chercher une catégorie existante avec le bon nom
    category_name = f"{base_category.name} ({category_index + 1})"
    for cat in guild.categories:
        if cat.name == category_name:
            category_cache[category_index] = cat
            return cat
    
    # Créer une nouvelle catégorie
    try:
        new_category = await guild.create_category(category_name)
        category_cache[category_index] = new_category
        print(f"📁 Catégorie créée: {category_name}")
        return new_category
    except Exception as e:
        print(f"❌ Erreur création catégorie {category_name}: {e}")
        return base_category

async def find_available_category(guild, base_category, start_index=0):
    """Trouve une catégorie disponible (avec moins de 50 canaux) ou en crée une nouvelle"""
    # Essayer d'abord la catégorie calculée
    category_index = start_index // MAX_CHANNELS_PER_CATEGORY
    category = await get_or_create_category(guild, base_category, category_index)
    
    # Vérifier si cette catégorie a de la place
    channel_count = count_channels_in_category(category)
    if channel_count < MAX_CHANNELS_PER_CATEGORY:
        return category
    
    # Si la catégorie est pleine, chercher la suivante disponible
    print(f"⚠️  Catégorie {category.name} est pleine ({channel_count}/50), recherche d'une catégorie disponible...")
    
    # Chercher dans les catégories existantes
    for cat in guild.categories:
        if cat.name.startswith(base_category.name):
            channel_count = count_channels_in_category(cat)
            if channel_count < MAX_CHANNELS_PER_CATEGORY:
                print(f"✅ Catégorie disponible trouvée: {cat.name} ({channel_count}/50)")
                return cat
    
    # Aucune catégorie disponible, créer une nouvelle
    # Trouver le prochain index de catégorie
    max_index = 0
    for cat in guild.categories:
        if cat.name.startswith(base_category.name):
            # Extraire l'index de la catégorie
            if cat.name == base_category.name:
                max_index = max(max_index, 0)
            else:
                # Format: "Nom (2)", "Nom (3)", etc.
                try:
                    if "(" in cat.name and ")" in cat.name:
                        idx_str = cat.name.split("(")[1].split(")")[0]
                        idx = int(idx_str)
                        max_index = max(max_index, idx)
                except:
                    pass
    
    # Créer une nouvelle catégorie avec l'index suivant
    new_index = max_index + 1
    print(f"📁 Création d'une nouvelle catégorie (index {new_index})...")
    new_category = await get_or_create_category(guild, base_category, new_index)
    
    # Vérifier que la nouvelle catégorie a bien été créée et a de la place
    channel_count = count_channels_in_category(new_category)
    if channel_count >= MAX_CHANNELS_PER_CATEGORY:
        # Si par hasard elle est pleine (peu probable), créer la suivante
        print(f"⚠️  La nouvelle catégorie {new_category.name} est aussi pleine, création d'une autre...")
        new_index = max_index + 2
        new_category = await get_or_create_category(guild, base_category, new_index)
    
    print(f"✅ Catégorie disponible: {new_category.name} ({count_channels_in_category(new_category)}/50)")
    return new_category

async def get_category_for_channel(guild, base_category, streamer_index):
    """Détermine dans quelle catégorie placer un canal selon son index"""
    return await find_available_category(guild, base_category, streamer_index)

async def build_channels_index(guild, base_category):
    """Construit un index de tous les canaux pour recherche rapide O(1)"""
    global channels_index, channels_index_loaded
    
    if channels_index_loaded:
        return
    
    print("🔍 Construction de l'index des canaux...")
    channels_index = {}
    
    # Parcourir toutes les catégories qui commencent par le nom de base
    for cat in guild.categories:
        if cat.name.startswith(base_category.name) or cat == base_category:
            for ch in cat.channels:
                if isinstance(ch, discord.TextChannel):
                    # Extraire le nom du streamer du nom du canal (format: "🟢-streamer" ou "🔴-streamer")
                    ch_name_lower = ch.name.lower()
                    if "-" in ch_name_lower:
                        streamer_name = ch_name_lower.split("-", 1)[1]  # Prendre tout après le premier "-"
                        channels_index[streamer_name] = ch
    
    channels_index_loaded = True
    print(f"✅ Index construit: {len(channels_index)} canaux indexés")

def has_data_changed(streamer, new_data):
    """Vérifie si les données d'un streamer ont changé
    
    Pour les streams hors ligne : ne met à jour que si le statut change (offline -> online)
    Pour les streams en ligne : met à jour si n'importe quelle donnée change
    """
    if streamer not in streamer_data_cache:
        return True  # Première fois, toujours mettre à jour
    
    old_data = streamer_data_cache[streamer]
    is_online = new_data.get('online', False)
    was_online = old_data.get('online', False)
    
    # Toujours détecter le changement de statut (offline -> online ou online -> offline)
    if is_online != was_online:
        return True
    
    # Si le stream est hors ligne, ne pas mettre à jour (sauf changement de statut déjà détecté)
    if not is_online:
        return False
    
    # Si le stream est en ligne, vérifier tous les champs importants
    important_fields = ['balance', 'session_points', 'watch_points', 
                       'bonus_points', 'bets_placed', 'bets_won', 'bets_lost']
    
    for field in important_fields:
        if old_data.get(field) != new_data.get(field):
            return True
    
    return False

async def create_pinned_channel(guild, force_recreate=False):
    """🆕 Crée la catégorie et le canal pour le message épinglé (supprime et recrée si force_recreate=True)"""
    global pinned_list_channel_id
    
    try:
        # Nom de la catégorie et du canal
        category_name = CATEGORY_NAME
        channel_name = CHANNEL_DASHBOARD
        
        # Si force_recreate, supprimer tout d'abord (sans chercher, on supprime tout ce qui correspond)
        if force_recreate:
            await cleanup_pinned_channel(guild)
            # Créer directement sans chercher
            print(f"📁 Création de la catégorie : {category_name}")
            category = await get_or_create_discord_category(guild, category_name)
            print(f"📝 Création du canal : {channel_name}")
            # Permissions : @everyone ne peut pas écrire, seulement lire
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=False,
                    add_reactions=False
                )
            }
            list_channel = await category.create_text_channel(
                channel_name,
                overwrites=overwrites
            )
            pinned_list_channel_id = list_channel.id
            save_channels()
            return list_channel
        
        # Sinon, utiliser le canal existant via l'ID sauvegardé (pas de recherche)
        if pinned_list_channel_id:
            list_channel = guild.get_channel(pinned_list_channel_id)
            if list_channel:
                return list_channel
        
        # Si pas d'ID sauvegardé, créer (première fois)
        print(f"📁 Création de la catégorie : {category_name}")
        category = await get_or_create_discord_category(guild, category_name)
        print(f"📝 Création du canal : {channel_name}")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=False,
                add_reactions=False
            )
        }
        list_channel = await category.create_text_channel(
            channel_name,
            overwrites=overwrites
        )
        pinned_list_channel_id = list_channel.id
        save_channels()
        return list_channel
    
    except Exception as e:
        print(f"❌ Erreur création catégorie/canal : {e}")
        import traceback
        traceback.print_exc()
        return None

async def cleanup_pinned_channel(guild):
    """🧹 Supprime la catégorie et le canal du message épinglé pour recréer proprement"""
    global pinned_list_channel_id, pinned_list_message_id
    
    try:
        deleted_channels = 0
        deleted_categories = 0
        # 1. Supprimer tous les canaux avec le nom "📋-liste-streamers" (peu importe où ils sont)
        for channel in guild.text_channels:
            if channel.name == "📋-liste-streamers":
                try:
                    await channel.delete()
                    deleted_channels += 1
                    print(f"🗑️ Canal 📋-liste-streamers supprimé")
                except Exception as e:
                    print(f"⚠️ Erreur suppression canal 📋-liste-streamers: {e}")
        
        # 2. Chercher et supprimer toutes les catégories avec le nom "📺 TWITCH MINER - LISTE"
        categories_to_delete = []
        for category in guild.categories:
            if category.name == "📺 TWITCH MINER - LISTE":
                categories_to_delete.append(category)
        
        # Supprimer tous les canaux restants dans ces catégories
        for category in categories_to_delete:
            for ch in list(category.channels):  # Utiliser list() pour éviter les modifications pendant l'itération
                try:
                    await ch.delete()
                    deleted_channels += 1
                except Exception as e:
                    print(f"⚠️ Erreur suppression canal dans catégorie: {e}")
        
        # Supprimer les catégories
        for category in categories_to_delete:
            try:
                await category.delete()
                deleted_categories += 1
                print(f"🗑️ Catégorie 📺 TWITCH MINER - LISTE supprimée")
            except Exception as e:
                print(f"⚠️ Erreur suppression catégorie 📺 TWITCH MINER - LISTE: {e}")
        
        if deleted_channels > 0 or deleted_categories > 0:
            print(f"✅ Nettoyage terminé : {deleted_channels} canal(x) et {deleted_categories} catégorie(s) supprimé(s)")
        
        # Réinitialiser les IDs
        pinned_list_channel_id = None
        pinned_list_message_id = None
        save_channels()
    
    except Exception as e:
        print(f"⚠️ Erreur nettoyage canal épinglé : {e}")
        import traceback
        traceback.print_exc()

async def create_or_update_pinned_list(guild):
    """🆕 Crée ou met à jour le message épinglé unique qui liste tous les streamers"""
    global pinned_list_channel_id, pinned_list_message_id
    
    # Variable globale pour suivre l'état précédent (persistance simple)
    global last_pinned_data_signature
    try:
        last_pinned_data_signature
    except NameError:
        last_pinned_data_signature = ""
    
    try:
        # Créer ou récupérer le canal (le bot le crée automatiquement si nécessaire)
        list_channel = await create_pinned_channel(guild, force_recreate=False)
        
        if not list_channel:
            print("❌ Impossible de créer/récupérer le canal pour le message épinglé")
            return
        
        # Charger les données
        load_data(force=True)
        
        # Vérifier qu'on a des données
        if not streamer_data or len(streamer_data) == 0:
            # print("⏳ En attente des données du miner...")
            return
        
        # Trier les streamers : en ligne d'abord, puis hors ligne
        sorted_streamers = sorted(
            streamer_data.items(),
            key=lambda x: (not x[1].get('online', False), x[0].lower())
        )
        
        online_count = sum(1 for _, d in sorted_streamers if d.get('online', False))
        offline_count = len(sorted_streamers) - online_count
        
        # Calculer les totaux de points pour le résumé
        total_balance = sum(s.get('balance', 0) for s in streamer_data.values())
        total_session_points = sum(s.get('session_points', 0) for s in streamer_data.values())
        total_watch_points = sum(s.get('watch_points', 0) for s in streamer_data.values())
        total_bonus_points = sum(s.get('bonus_points', 0) for s in streamer_data.values())
        total_bets_won = sum(s.get('bets_won', 0) for s in streamer_data.values())
        total_bets_lost = sum(s.get('bets_lost', 0) for s in streamer_data.values())
        
        # ⚡ OPTIMISATION : Vérifier si les données ont changé avant de reconstruire l'embed
        # On construit une signature unique basée sur les données affichées
        current_signature = f"{online_count}|{offline_count}|{total_balance}|{total_session_points}|{total_bets_won}|{total_bets_lost}"
        
        # Ajouter les détails des streamers en ligne (nom + balance + session) pour détecter les changements
        for s, d in sorted_streamers:
            if d.get('online', False):
                current_signature += f"|{s}:{d.get('balance', 0)}:{d.get('session_points', 0)}"
        
        # Si la signature est identique, on ne fait rien (économie d'API Discord)
        if last_pinned_data_signature == current_signature:
            return
            
        last_pinned_data_signature = current_signature
        
        # Formatage des nombres
        balance_display = f"{total_balance:,.0f}".replace(',', ' ')
        session_display = f"{total_session_points:,.0f}".replace(',', ' ')
        watch_display = f"{total_watch_points:,.0f}".replace(',', ' ')
        bonus_display = f"{total_bonus_points:,.0f}".replace(',', ' ')
        
        # Créer le contenu du message avec embed Discord
        embed = discord.Embed(
            title="🟣 TABLEAU DE BORD TWITCH",
            description=f"**{online_count}** En ligne • **{offline_count}** Hors ligne • **{len(sorted_streamers)}** Total",
            color=0x9146FF,
            timestamp=datetime.utcnow()
        )
        
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Twitch_Glitch_Logo_Purple.svg/878px-Twitch_Glitch_Logo_Purple.svg.png")
        
        # 📊 RÉSUMÉ EN HAUT : Points de chaîne gagnés
        summary_text = f"💰 **Solde Total** : `{balance_display}`\n"
        if total_session_points > 0:
            summary_text += f"📈 **Session** : `+{session_display}`\n"
        if total_watch_points > 0:
            summary_text += f"👁️ **Watch** : `+{watch_display}`\n"
        if total_bonus_points > 0:
            summary_text += f"🎁 **Bonus** : `+{bonus_display}`\n"
        
        embed.add_field(
            name="💎 STATISTIQUES GLOBALES",
            value=summary_text,
            inline=True
        )

        # Paris
        if total_bets_won > 0 or total_bets_lost > 0:
            bets_text = f"✅ **Gagnés** : `{total_bets_won}`\n❌ **Perdus** : `{total_bets_lost}`"
            embed.add_field(
                name="🎲 PARIS",
                value=bets_text,
                inline=True
            )
        
        # Séparateur visuel
        embed.add_field(
            name="\u200b",  # Caractère invisible pour séparateur
            value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            inline=False
        )
        
        # Streamers en ligne (limiter à 25 pour éviter embed trop long)
        online_list = []
        for streamer, data in sorted_streamers:
            if data.get('online', False):
                balance = data.get('balance', 0)
                balance_str = f"{balance:,.0f}".replace(',', ' ')
                session_points = data.get('session_points', 0)
                
                line = f"🟢 **{streamer}** • `{balance_str}`"
                if session_points > 0:
                    line += f" `(+{session_points})`"
                online_list.append(line)
                
                if len(online_list) >= 25:
                    online_list.append(f"*... et {online_count - 25} autres*")
                    break
        
        if online_list:
            embed.add_field(
                name=f"📡 EN LIGNE ({online_count})",
                value="\n".join(online_list),
                inline=False
            )
        else:
            embed.add_field(
                name="📡 EN LIGNE",
                value="*Aucun streamer en ligne pour le moment...*",
                inline=False
            )
        
        embed.set_footer(text="Mise à jour automatique • v3.0", icon_url="https://cdn-icons-png.flaticon.com/512/190/190411.png")
        
        # Créer ou mettre à jour le message
        if pinned_list_message_id:
            try:
                message = await list_channel.fetch_message(pinned_list_message_id)
                await message.edit(embed=embed)
                print(f"✅ Message épinglé mis à jour : {online_count} en ligne, {offline_count} hors ligne")
            except discord.NotFound:
                # Message supprimé, en créer un nouveau
                message = await list_channel.send(embed=embed)
                await message.pin()
                pinned_list_message_id = message.id
                pinned_list_channel_id = list_channel.id
                save_channels()
                
                # Supprimer le message système "message épinglé"
                await asyncio.sleep(1)
                try:
                    async for msg in list_channel.history(limit=10):
                        if msg.type == discord.MessageType.pins_add:
                            if msg.reference and msg.reference.message_id == message.id:
                                await msg.delete()
                                break
                        elif "épinglé" in msg.content.lower() or "pinned" in msg.content.lower():
                            await msg.delete()
                            break
                except:
                    pass
                
                print(f"✅ Nouveau message épinglé créé : {online_count} en ligne, {offline_count} hors ligne")
        else:
            # Créer le message et l'épingler
            message = await list_channel.send(embed=embed)
            await message.pin()
            pinned_list_message_id = message.id
            pinned_list_channel_id = list_channel.id
            save_channels()
            
            # Supprimer le message système "message épinglé"
            await asyncio.sleep(1)
            try:
                async for msg in list_channel.history(limit=10):
                    if msg.type == discord.MessageType.pins_add:
                        if msg.reference and msg.reference.message_id == message.id:
                            await msg.delete()
                            break
                    elif "épinglé" in msg.content.lower() or "pinned" in msg.content.lower():
                        await msg.delete()
                        break
            except:
                pass
            
            print(f"✅ Message épinglé créé : {online_count} en ligne, {offline_count} hors ligne")
    
    except Exception as e:
        print(f"❌ Erreur création/mise à jour message épinglé : {e}")
        import traceback
        traceback.print_exc()

async def cleanup_old_channels(guild):
    """🧹 Supprime les anciens salons individuels et catégories inutiles"""
    global streamer_channels, streamer_messages, category_channels
    
    if not CATEGORY_ID or CATEGORY_ID == 0:
        return
    
    try:
        base_category = bot.get_channel(CATEGORY_ID)
        if not base_category or not isinstance(base_category, discord.CategoryChannel):
            return
        
        deleted_channels = 0
        deleted_categories = 0
        
        # Supprimer tous les salons de streamers individuels
        for category in guild.categories:
            if category.name.startswith(base_category.name) or category == base_category:
                for channel in category.text_channels:
                    if isinstance(channel, discord.TextChannel):
                        # Vérifier si c'est un salon de streamer (format: 🟢-nom ou 🔴-nom)
                        if channel.name.startswith("🟢-") or channel.name.startswith("🔴-"):
                            try:
                                await channel.delete()
                                deleted_channels += 1
                                if deleted_channels % 5 == 0:
                                    await asyncio.sleep(1)  # Rate limiting
                            except Exception as e:
                                print(f"⚠️ Erreur suppression salon {channel.name}: {e}")
        
        # Supprimer les catégories vides (sauf la catégorie de base)
        for category in guild.categories:
            if category.name.startswith(base_category.name) and category != base_category:
                # Vérifier si la catégorie est vide
                text_channels = [ch for ch in category.channels if isinstance(ch, discord.TextChannel)]
                if len(text_channels) == 0:
                    try:
                        await category.delete()
                        deleted_categories += 1
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"⚠️ Erreur suppression catégorie {category.name}: {e}")
        
        # Nettoyer les références
        streamer_channels.clear()
        streamer_messages.clear()
        category_channels.clear()
        save_channels()
        
        if deleted_channels > 0 or deleted_categories > 0:
            print(f"🧹 Nettoyage terminé : {deleted_channels} salon(s) et {deleted_categories} catégorie(s) supprimé(s)")
    
    except Exception as e:
        print(f"❌ Erreur nettoyage salons : {e}")
        import traceback
        traceback.print_exc()

@tasks.loop(seconds=30)
async def update_channels():
    """Met à jour les salons streamers selon leur statut"""
    global USE_PINNED_MESSAGE
    
    # 🆕 NOUVEAU SYSTÈME : Message épinglé unique
    if USE_PINNED_MESSAGE:
        try:
            # Le bot crée automatiquement le canal, pas besoin de CHANNEL_ID
            # Utiliser le premier guild disponible
            for guild in bot.guilds:
                # Nettoyer les anciens salons au premier démarrage (une seule fois)
                if not pinned_list_message_id and CATEGORY_ID and CATEGORY_ID != 0:
                    print("🧹 Nettoyage des anciens salons individuels...")
                    await cleanup_old_channels(guild)
                
                await create_or_update_pinned_list(guild)
                return  # Ne pas créer de salons individuels
        except Exception as e:
            print(f"⚠️ Erreur système message épinglé : {e}")
            import traceback
            traceback.print_exc()
            # Ne pas désactiver automatiquement, laisser l'utilisateur décider
    
    # ANCIEN SYSTÈME : Salons individuels (fallback)
    if not CATEGORY_ID or CATEGORY_ID == 0:
        return
    
    try:
        base_category = bot.get_channel(CATEGORY_ID)
        if not base_category or not isinstance(base_category, discord.CategoryChannel):
            print(f"❌ Catégorie {CATEGORY_ID} introuvable ou invalide")
            return
        
        guild = base_category.guild
        
        # Recharger les données (force le rechargement pour détecter les changements offline)
        load_data(force=True)
        
        # Construire l'index des canaux au premier passage (une seule fois)
        if not channels_index_loaded:
            await build_channels_index(guild, base_category)
        
        # Trier les streamers : en ligne d'abord, puis hors ligne
        sorted_streamers = sorted(
            streamer_data.items(),
            key=lambda x: (not x[1].get('online', False), x[0].lower())
        )
        
        channels_modified = False  # Flag pour batch save
        updates_count = 0
        
        # Filtrer pour ne garder QUE les streamers en ligne
        online_streams = [(s, d) for s, d in sorted_streamers if d.get('online', False)]
        online_streamer_names = {s for s, d in online_streams}
        print(f"📊 Traitement de {len(online_streams)} streams en ligne (sur {len(sorted_streamers)} total)")
        
        # NETTOYAGE : Supprimer TOUS les salons hors ligne
        # Vérifier d'abord dans streamer_data, puis aussi directement dans les salons Discord
        if len(streamer_data) > 0:
            # Liste des streamers à supprimer : ceux qui sont dans streamer_channels mais pas en ligne
            offline_channels_to_delete = []
            
            for streamer_in_channel in list(streamer_channels.keys()):
                should_delete = False
                
                # Cas 1: Le streamer n'est plus dans streamer_data
                if streamer_in_channel not in streamer_data:
                    should_delete = True
                # Cas 2: Le streamer est dans streamer_data mais offline
                elif streamer_in_channel not in online_streamer_names:
                    # Vérifier explicitement le statut online
                    streamer_status = streamer_data.get(streamer_in_channel, {}).get('online', False)
                    if not streamer_status:
                        should_delete = True
                
                if should_delete:
                    offline_channels_to_delete.append(streamer_in_channel)
            
            # Vérifier aussi les salons Discord qui existent mais ne sont pas dans streamer_channels
            # (cas où un salon existe mais n'est pas dans notre mapping)
            for category in guild.categories:
                if category.name.startswith(base_category.name) or category == base_category:
                    for channel in category.text_channels:
                        if isinstance(channel, discord.TextChannel):
                            # Vérifier si c'est un salon de streamer (format: 🟢-nom ou 🔴-nom)
                            if channel.name.startswith("🟢-") or channel.name.startswith("🔴-"):
                                streamer_from_channel = channel.name.split("-", 1)[1] if "-" in channel.name else None
                                if streamer_from_channel:
                                    streamer_from_channel_lower = streamer_from_channel.lower()
                                    # Si le salon existe mais le streamer n'est pas en ligne
                                    if streamer_from_channel_lower not in online_streamer_names:
                                        # Vérifier le statut dans les données
                                        streamer_status = streamer_data.get(streamer_from_channel_lower, {}).get('online', False)
                                        if not streamer_status:
                                            # Le salon existe mais le streamer est offline
                                            if streamer_from_channel_lower not in offline_channels_to_delete:
                                                # Ajouter à la liste si pas déjà dedans
                                                offline_channels_to_delete.append(streamer_from_channel_lower)
                                                # Ajouter au mapping si pas présent
                                                if streamer_from_channel_lower not in streamer_channels:
                                                    streamer_channels[streamer_from_channel_lower] = channel.id
            
            if offline_channels_to_delete:
                print(f"🗑️  [NETTOYAGE] {len(offline_channels_to_delete)} salon(s) hors ligne à supprimer")
                deleted_count = 0
                
                for streamer_to_delete in offline_channels_to_delete:
                    channel_id = streamer_channels.get(streamer_to_delete)
                    if not channel_id:
                        # Si pas dans le mapping, chercher le salon directement
                        for category in guild.categories:
                            if category.name.startswith(base_category.name) or category == base_category:
                                for channel in category.text_channels:
                                    if isinstance(channel, discord.TextChannel):
                                        if channel.name.startswith("🟢-") or channel.name.startswith("🔴-"):
                                            streamer_from_channel = channel.name.split("-", 1)[1] if "-" in channel.name else None
                                            if streamer_from_channel and streamer_from_channel.lower() == streamer_to_delete.lower():
                                                channel_id = channel.id
                                                break
                                if channel_id:
                                    break
                    
                    channel = guild.get_channel(channel_id) if channel_id else None
                    
                    if channel:
                        try:
                            await channel.delete()
                            deleted_count += 1
                            print(f"🗑️  [{deleted_count}] Salon supprimé (hors ligne): {streamer_to_delete}")
                            # Rate limiting : pause toutes les 3 suppressions
                            if deleted_count % 3 == 0:
                                await asyncio.sleep(1)
                        except Exception as e:
                            print(f"⚠️  Erreur suppression {streamer_to_delete}: {e}")
                    
                    # Nettoyer les références
                    if streamer_to_delete in streamer_channels:
                        del streamer_channels[streamer_to_delete]
                    if streamer_to_delete in streamer_messages:
                        del streamer_messages[streamer_to_delete]
                    if streamer_to_delete in streamer_data_cache:
                        del streamer_data_cache[streamer_to_delete]
                    streamer_name_lower = streamer_to_delete.lower()
                    if streamer_name_lower in channels_index:
                        del channels_index[streamer_name_lower]
                    channels_modified = True
                
                if deleted_count > 0:
                    print(f"✅ [NETTOYAGE] {deleted_count} salon(s) supprimé(s)")
        else:
            print("⏳ En attente des données du miner...")
        
        # Mettre à jour ou créer les canaux SEULEMENT pour les streamers en ligne
        for index, (streamer, data) in enumerate(online_streams):
            # Rate limiting : 1s toutes les 10 requêtes (optimisé)
            if index > 0 and index % 10 == 0:
                await asyncio.sleep(1)
            
            # Tous les streamers ici sont en ligne (filtrés plus haut)
            channel_name = f"🟢-{streamer.lower()}"
            
            # Déterminer la catégorie appropriée (vérifie automatiquement si elle a de la place)
            target_category = await find_available_category(guild, base_category, index)
            
            # Si le salon existe déjà
            if streamer in streamer_channels:
                channel_id = streamer_channels[streamer]
                channel = guild.get_channel(channel_id)
                
                if channel:
                    needs_update = False
                    
                    # Vérifier si le canal doit être déplacé vers une autre catégorie
                    if channel.category != target_category:
                        try:
                            await channel.edit(category=target_category)
                            print(f"🔄 Canal déplacé: {channel_name} → {target_category.name}")
                            needs_update = True
                        except Exception as e:
                            print(f"⚠️  Erreur déplacement canal {channel_name}: {e}")
                    
                    # Mettre à jour le nom si nécessaire (doit être 🟢-nom)
                    if channel.name != channel_name:
                        await channel.edit(name=channel_name)
                        print(f"🔄 Salon renommé: {channel_name}")
                        needs_update = True
                    
                    # Mettre à jour le message seulement si les données ont changé
                    if has_data_changed(streamer, data):
                        embed = create_streamer_embed(streamer)
                        
                        if streamer in streamer_messages:
                            try:
                                message = await channel.fetch_message(streamer_messages[streamer])
                                await message.edit(embed=embed)
                                updates_count += 1
                            except discord.NotFound:
                                # Message supprimé, nettoyer le salon et créer une nouvelle fiche
                                # Supprimer tous les anciens messages
                                try:
                                    async for old_message in channel.history(limit=100):
                                        await old_message.delete()
                                except:
                                    pass
                                # Créer la nouvelle fiche
                                message = await channel.send(embed=embed)
                                streamer_messages[streamer] = message.id
                                channels_modified = True
                        else:
                            # Nettoyer le salon avant de créer la fiche (supprimer les anciennes fiches)
                            try:
                                async for old_message in channel.history(limit=100):
                                    await old_message.delete()
                            except:
                                pass
                            # Créer la fiche initiale
                            message = await channel.send(embed=embed)
                            streamer_messages[streamer] = message.id
                            channels_modified = True
                        
                        # Mettre à jour le cache
                        streamer_data_cache[streamer] = data.copy()
                else:
                    # Le salon a été supprimé, le recréer
                    print(f"🔄 Recréation du salon: {channel_name}")
                    try:
                        channel = await guild.create_text_channel(
                            name=channel_name,
                            category=target_category
                        )
                        streamer_channels[streamer] = channel.id
                        # Ajouter à l'index
                        streamer_name_lower = streamer.lower()
                        channels_index[streamer_name_lower] = channel
                        
                        # Créer le message initial
                        embed = create_streamer_embed(streamer)
                        message = await channel.send(embed=embed)
                        streamer_messages[streamer] = message.id
                        channels_modified = True
                        streamer_data_cache[streamer] = data.copy()
                    except Exception as e:
                        print(f"❌ Erreur création salon {channel_name}: {e}")
            
            else:
                # Vérifier si un salon avec ce nom existe déjà (recherche optimisée avec index)
                existing_channel = None
                streamer_name_lower = streamer.lower()
                
                # Recherche rapide O(1) dans l'index
                if streamer_name_lower in channels_index:
                    existing_channel = channels_index[streamer_name_lower]
                    # Vérifier que le canal existe toujours
                    if existing_channel not in guild.channels:
                        # Canal supprimé, retirer de l'index
                        del channels_index[streamer_name_lower]
                        existing_channel = None
                    else:
                        print(f"🔍 Salon existant trouvé (index): {existing_channel.name} → réutilisation (streamer: {streamer})")
                
                # Si pas trouvé dans l'index, chercher par ID dans streamer_channels
                if not existing_channel:
                    for other_streamer, other_channel_id in streamer_channels.items():
                        if other_streamer.lower() == streamer_name_lower:
                            potential_channel = guild.get_channel(other_channel_id)
                            if potential_channel and isinstance(potential_channel, discord.TextChannel):
                                existing_channel = potential_channel
                                # Ajouter à l'index pour la prochaine fois
                                channels_index[streamer_name_lower] = potential_channel
                                print(f"🔍 Salon existant trouvé par ID: {potential_channel.name} → réutilisation (streamer: {streamer})")
                                # Mettre à jour le mapping
                                streamer_channels[streamer] = other_channel_id
                                if other_streamer != streamer:
                                    # Nettoyer l'ancien mapping si le nom a changé
                                    del streamer_channels[other_streamer]
                                break
                
                if existing_channel:
                    # Réutiliser le salon existant
                    streamer_channels[streamer] = existing_channel.id
                    channel = existing_channel
                    channels_modified = True
                    
                    # Mettre à jour le nom si nécessaire
                    if channel.name != channel_name:
                        await channel.edit(name=channel_name)
                        print(f"🔄 Salon renommé: {channel_name}")
                    
                    # Vérifier la catégorie
                    if channel.category != target_category:
                        try:
                            await channel.edit(category=target_category)
                            print(f"🔄 Canal déplacé: {channel_name} → {target_category.name}")
                        except Exception as e:
                            print(f"⚠️  Erreur déplacement canal {channel_name}: {e}")
                    
                    # Créer ou mettre à jour le message seulement si les données ont changé
                    if has_data_changed(streamer, data):
                        embed = create_streamer_embed(streamer)
                        if streamer in streamer_messages:
                            try:
                                message = await channel.fetch_message(streamer_messages[streamer])
                                await message.edit(embed=embed)
                                updates_count += 1
                            except discord.NotFound:
                                # Message supprimé, nettoyer et créer une nouvelle fiche
                                try:
                                    async for old_message in channel.history(limit=100):
                                        await old_message.delete()
                                except:
                                    pass
                                message = await channel.send(embed=embed)
                                streamer_messages[streamer] = message.id
                                channels_modified = True
                        else:
                            # Nettoyer le salon avant de créer la fiche
                            try:
                                async for old_message in channel.history(limit=100):
                                    await old_message.delete()
                            except:
                                pass
                            message = await channel.send(embed=embed)
                            streamer_messages[streamer] = message.id
                            channels_modified = True
                        
                        streamer_data_cache[streamer] = data.copy()
                else:
                    # Créer un nouveau salon pour ce streamer
                    # Vérifier que la catégorie a de la place avant de créer
                    channel_count = count_channels_in_category(target_category)
                    if channel_count >= MAX_CHANNELS_PER_CATEGORY:
                        print(f"⚠️  Catégorie {target_category.name} est pleine ({channel_count}/50), recherche d'une autre...")
                        target_category = await find_available_category(guild, base_category, index)
                    
                    print(f"✅ Création du salon: {channel_name} dans {target_category.name}")
                    try:
                        channel = await guild.create_text_channel(
                            name=channel_name,
                            category=target_category
                        )
                        streamer_channels[streamer] = channel.id
                        # Ajouter à l'index
                        channels_index[streamer_name_lower] = channel
                        
                        # Nettoyer le salon (si jamais il y a des messages)
                        try:
                            async for old_message in channel.history(limit=100):
                                await old_message.delete()
                        except:
                            pass
                        # Créer le message initial
                        embed = create_streamer_embed(streamer)
                        message = await channel.send(embed=embed)
                        streamer_messages[streamer] = message.id
                        channels_modified = True
                        streamer_data_cache[streamer] = data.copy()
                    except Exception as e:
                        print(f"❌ Erreur création salon {channel_name}: {e}")
                        # Si erreur de limite, trouver une catégorie disponible
                        if "Maximum number of channels" in str(e):
                            try:
                                # Trouver une catégorie disponible (peut créer une nouvelle si nécessaire)
                                available_category = await find_available_category(guild, base_category, index)
                                # Vérifier une dernière fois avant de créer
                                channel_count = count_channels_in_category(available_category)
                                if channel_count >= MAX_CHANNELS_PER_CATEGORY:
                                    print(f"⚠️  Catégorie {available_category.name} toujours pleine, création d'une nouvelle...")
                                    available_category = await find_available_category(guild, base_category, index + 100)  # Forcer une nouvelle catégorie
                                
                                channel = await guild.create_text_channel(
                                    name=channel_name,
                                    category=available_category
                                )
                                streamer_channels[streamer] = channel.id
                                # Ajouter à l'index
                                channels_index[streamer_name_lower] = channel
                                embed = create_streamer_embed(streamer)
                                message = await channel.send(embed=embed)
                                streamer_messages[streamer] = message.id
                                channels_modified = True
                                streamer_data_cache[streamer] = data.copy()
                                print(f"✅ Salon créé dans catégorie disponible: {channel_name} → {available_category.name}")
                            except Exception as e2:
                                print(f"❌ Erreur création salon dans catégorie disponible: {e2}")
                                import traceback
                                traceback.print_exc()
        
        # Le nettoyage a déjà été fait plus haut, pas besoin de le refaire ici
        
        # Sauvegarder seulement si des modifications ont été faites
        if channels_modified:
                save_channels()
        
        # RÉORGANISATION : Trier les salons par ordre alphabétique dans chaque catégorie
        # S'exécute à chaque cycle si nécessaire (pas seulement après modifications)
        if len(online_streams) > 0:
            try:
                reordered_count = 0
                # Pour chaque catégorie de streams
                for cat in guild.categories:
                    if cat.name.startswith(base_category.name) or cat == base_category:
                        # Récupérer tous les salons textuels de cette catégorie
                        text_channels = [ch for ch in cat.channels if isinstance(ch, discord.TextChannel)]
                        
                        if len(text_channels) <= 1:
                            continue  # Pas besoin de trier 0 ou 1 salon
                        
                        # Trier par nom (alphabétique, ignore les emojis)
                        sorted_channels = sorted(text_channels, key=lambda ch: ch.name.lower())
                        
                        # Vérifier si l'ordre est déjà correct
                        needs_reorder = False
                        for i, channel in enumerate(sorted_channels):
                            if channel.position != i:
                                needs_reorder = True
                                break
                        
                        if needs_reorder:
                            # Discord permet de modifier plusieurs salons à la fois
                            try:
                                await cat.edit(channels=[(ch, pos) for pos, ch in enumerate(sorted_channels)])
                                reordered_count += len(sorted_channels)
                                print(f"📋 Catégorie {cat.name}: {len(sorted_channels)} salons triés alphabétiquement")
                                await asyncio.sleep(1)  # Rate limiting entre catégories
                            except Exception as e:
                                # Si bulk edit échoue, ne rien faire (pas critique)
                                print(f"⚠️  Erreur tri {cat.name}: {e}")
                
                if reordered_count > 0:
                    print(f"✅ {reordered_count} salons total réorganisés")
            except Exception as e:
                print(f"⚠️  Erreur réorganisation: {e}")
        
        # NETTOYAGE : Supprimer les catégories vides (sauf la catégorie de base)
        # Exemple : Si on passe de 60 streams (2 catégories) à 30 streams (1 catégorie)
        for cat in guild.categories:
            # Vérifier que c'est une catégorie de streams (commence par le nom de base)
            if cat.name.startswith(base_category.name) and cat != base_category:
                # Compter les salons dans cette catégorie
                channel_count = count_channels_in_category(cat)
                if channel_count == 0:
                    try:
                        await cat.delete()
                        print(f"🗑️  [NETTOYAGE] Catégorie vide supprimée: {cat.name}")
                        # Retirer du cache
                        for idx, cached_cat in list(category_cache.items()):
                            if cached_cat == cat:
                                del category_cache[idx]
                    except Exception as e:
                        print(f"⚠️  Erreur suppression catégorie vide {cat.name}: {e}")
        
        # Mettre à jour le salon de statistiques
        await update_stats_channel(guild)
        
        # Mettre à jour les salons de statistiques détaillées
        await update_stats_channels(guild)
        
        # Log du cycle complet (toutes les 30s) - plus informatif
        total_streamers = len(sorted_streamers)
        print(f"✅ Cycle: {len(online_streams)}/{total_streamers} en ligne | {updates_count} fiches mises à jour")
    
    except Exception as e:
        print(f"❌ Erreur update_channels: {e}")
        import traceback
        traceback.print_exc()

@update_channels.before_loop
async def before_update_channels():
    await bot.wait_until_ready()

@bot.command(name='refresh')
async def refresh_channels(ctx):
    """Force la mise à jour des salons"""
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    msg = await ctx.send("🔄 Mise à jour forcée des salons...")
    
    load_data(force=True)  # Force le rechargement
    await update_channels()
    
    await msg.edit(content=f"✅ Salons mis à jour ! ({len(streamer_data)} streamers)")
    await msg.delete(delay=5)

@bot.command(name='reset')
async def reset_channels(ctx):
    """Supprime tous les salons streamers et réinitialise"""
    global streamer_channels, streamer_messages, channels_index
    
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    if not CATEGORY_ID or CATEGORY_ID == 0:
        await ctx.send("❌ DISCORD_CATEGORY_ID non défini !", delete_after=5)
        return
    
    msg = await ctx.send("⚠️  Suppression de tous les salons streamers...")
    
    category = bot.get_channel(CATEGORY_ID)
    if category and isinstance(category, discord.CategoryChannel):
        guild = category.guild
        
        # Supprimer tous les salons
        deleted_count = 0
        for streamer, channel_id in list(streamer_channels.items()):
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.delete()
                    deleted_count += 1
                    print(f"🗑️  Salon supprimé ({deleted_count}): {streamer}")
                    # Rate limiting : pause toutes les 5 suppressions
                    if deleted_count % 5 == 0:
                        await asyncio.sleep(2)
                except Exception as e:
                    print(f"⚠️  Erreur suppression {streamer}: {e}")
        
        streamer_channels = {}
        streamer_messages = {}
        channels_index = {}
        save_channels()
        
        await msg.edit(content=f"✅ {deleted_count} salons supprimés ! Utilisez `!refresh` pour les recréer.")
    else:
        await msg.edit(content="❌ Catégorie introuvable !")
    
    await msg.delete(delay=10)

@bot.command(name='nuke')
async def nuke_all_channels(ctx):
    """SUPPRIME TOUS LES SALONS dans toutes les catégories (DANGEREUX)"""
    global streamer_channels, streamer_messages, channels_index
    
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    msg = await ctx.send("⚠️  🔥 NUKE : Suppression de TOUS les salons dans toutes les catégories...")
    
    guild = ctx.guild
    deleted_count = 0
    
    # Parcourir toutes les catégories qui contiennent des salons de streamers
    for category in guild.categories:
        for channel in category.text_channels:
            # Supprimer seulement les salons qui ressemblent à des salons de streamers (🟢- ou 🔴-)
            if channel.name.startswith("🟢-") or channel.name.startswith("🔴-"):
                try:
                    await channel.delete()
                    deleted_count += 1
                    print(f"🗑️  [NUKE] Salon supprimé ({deleted_count}): {channel.name}")
                    # Rate limiting : pause toutes les 3 suppressions
                    if deleted_count % 3 == 0:
                        print(f"⏸️  Pause de 2s après {deleted_count} suppressions...")
                        await asyncio.sleep(2)
                except Exception as e:
                    print(f"⚠️  Erreur suppression {channel.name}: {e}")
    
    # Réinitialiser tout
    streamer_channels = {}
    streamer_messages = {}
    channels_index = {}
    save_channels()
    
    await msg.edit(content=f"✅ 🔥 NUKE terminé : {deleted_count} salons supprimés !")
    await msg.delete(delay=15)

@bot.command(name='status')
async def status(ctx, streamer: str = None):
    """Affiche le statut du bot ou d'un streamer spécifique
    
    Usage:
        !status              - Statut général du bot
        !status jltomy       - Statut du streamer JLTomy
    """
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    load_data(force=True)  # Toujours charger les dernières données pour les commandes
    
    # Si un streamer est spécifié
    if streamer:
        streamer_lower = streamer.lower()
        
        if streamer_lower not in streamer_data:
            await ctx.send(f"❌ Streamer `{streamer}` non trouvé. Streamers disponibles: {', '.join(streamer_data.keys())}", delete_after=10)
            return
        
        # Créer un embed pour ce streamer
        embed = create_streamer_embed(streamer_lower)
        await ctx.send(embed=embed, delete_after=30)
    
    # Sinon, afficher le statut général
    else:
        total_streamers = len(streamer_data)
        online_streamers = sum(1 for s in streamer_data.values() if s.get('online', False))
        
        embed = discord.Embed(
            title="📊 Statut du Bot Twitch Miner",
            description="🟢 Bot actif et fonctionnel",
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="📺 Streamers", value=f"{online_streamers}/{total_streamers} en ligne", inline=True)
        embed.add_field(name="🔄 Update auto", value="30 secondes", inline=True)
        embed.add_field(name="📋 Salons actifs", value=str(len(streamer_channels)), inline=True)
        
        # Liste des streamers (triés : en ligne d'abord)
        # Limite Discord : 2000 caractères max par field, donc on limite à ~100 streamers
        if streamer_data:
            streamers_list = []
            # Trier : en ligne d'abord, puis hors ligne
            sorted_streamers = sorted(
                streamer_data.items(),
                key=lambda x: (not x[1].get('online', False), x[0].lower())
            )
            
            # Limiter l'affichage pour éviter de dépasser la limite Discord
            max_display = 100
            displayed_count = 0
            for name, data in sorted_streamers:
                if displayed_count >= max_display:
                    break
                status_emoji = "🟢" if data.get('online', False) else "🔴"
                streamers_list.append(f"{status_emoji} {name}")
                displayed_count += 1
            
            display_text = "\n".join(streamers_list) if streamers_list else "Aucun"
            if len(sorted_streamers) > max_display:
                display_text += f"\n\n... et {len(sorted_streamers) - max_display} autres"
            
            embed.add_field(
                name=f"📋 Streamers suivis ({len(sorted_streamers)} total)",
                value=display_text,
                inline=False
            )
        
        embed.set_footer(text="Utilisez !status <streamer> pour voir un streamer spécifique")
        
        await ctx.send(embed=embed, delete_after=30)

@bot.command(name='blacklist')
async def blacklist_streamer(ctx, streamer: str):
    """Ajoute un streamer à la blacklist (ne sera pas miné)"""
    # Supprimer la commande
    try:
        await ctx.message.delete()
    except:
        pass
    
    streamer_lower = streamer.lower()
    
    # Charger la blacklist actuelle
    blacklist_file = Path("blacklist.json")
    if blacklist_file.exists():
        with open(blacklist_file, 'r') as f:
            blacklist = json.load(f)
    else:
        blacklist = []
    
    # Vérifier si déjà présent
    if streamer_lower in blacklist:
        await ctx.send(f"⚠️  **{streamer}** est déjà dans la blacklist !", delete_after=5)
        return
    
    # Ajouter
    blacklist.append(streamer_lower)
    
    # Sauvegarder
    with open(blacklist_file, 'w') as f:
        json.dump(blacklist, f, indent=2)
    
    await ctx.send(f"🚫 **{streamer}** ajouté à la blacklist ! Redémarrez le miner pour appliquer.", delete_after=10)

@bot.command(name='unblacklist')
async def unblacklist_streamer(ctx, streamer: str):
    """Retire un streamer de la blacklist (sera à nouveau miné)"""
    # Supprimer la commande
    try:
        await ctx.message.delete()
    except:
        pass
    
    streamer_lower = streamer.lower()
    
    # Charger la blacklist actuelle
    blacklist_file = Path("blacklist.json")
    if blacklist_file.exists():
        with open(blacklist_file, 'r') as f:
            blacklist = json.load(f)
    else:
        blacklist = []
    
    # Vérifier si présent
    if streamer_lower not in blacklist:
        await ctx.send(f"⚠️  **{streamer}** n'est pas dans la blacklist !", delete_after=5)
        return
    
    # Retirer
    blacklist.remove(streamer_lower)
    
    # Sauvegarder
    with open(blacklist_file, 'w') as f:
        json.dump(blacklist, f, indent=2)
    
    await ctx.send(f"✅ **{streamer}** retiré de la blacklist ! Redémarrez le miner pour appliquer.", delete_after=10)

@bot.command(name='list')
async def list_blacklist(ctx):
    """Affiche la blacklist (streamers exclus du mining)"""
    # Supprimer la commande
    try:
        await ctx.message.delete()
    except:
        pass
    
    # Charger la blacklist
    blacklist_file = Path("blacklist.json")
    if blacklist_file.exists():
        with open(blacklist_file, 'r') as f:
            blacklist = json.load(f)
    else:
        blacklist = []
    
    embed = discord.Embed(
        title="🚫 Blacklist",
        description="Streamers exclus du mining automatique",
        color=0xFF0000
    )
    
    if blacklist:
        embed.add_field(
            name=f"📋 {len(blacklist)} streamer(s) blacklisté(s)",
            value="\n".join(f"• {s}" for s in blacklist),
            inline=False
        )
    else:
        embed.add_field(
            name="✅ Aucune blacklist",
            value="Tous vos follows Twitch sont minés !",
            inline=False
        )
    
    embed.set_footer(text="Mode FOLLOWERS : Tous vos follows Twitch sont automatiquement minés (sauf blacklist)")
    
    await ctx.send(embed=embed, delete_after=30)

@bot.command(name='addfollow')
async def add_follow_command(ctx, streamer: str):
    """Ajoute manuellement un nouveau follow sans redémarrer (optimisation)"""
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    streamer = streamer.lower().strip()
    
    # Vérifier si déjà dans la liste
    if streamer in streamer_data:
        await ctx.send(f"⚠️ **{streamer}** est déjà dans la liste !", delete_after=5)
        return
    
    # Ajouter aux données (sera chargé au prochain cycle)
    streamer_data[streamer] = {
        'online': False,
        'balance': 0,
        'session_points': 0,
        'watch_points': 0,
        'bonus_points': 0,
        'bets_placed': 0,
        'bets_won': 0,
        'bets_lost': 0
    }
    save_data()  # Sauvegarder
    
    # Ajouter au cache des followers pour le prochain redémarrage
    try:
        from pathlib import Path
        import json
        import time
        
        cache_file = get_cache_file_path()
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            if streamer not in cache_data.get('followers', []):
                cache_data['followers'].append(streamer)
                cache_data['count'] = len(cache_data['followers'])
                # NE PAS mettre à jour le timestamp pour garder l'âge du cache
                
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                
                print(f"✅ {streamer} ajouté au cache des followers")
    except Exception as e:
        print(f"⚠️ Erreur ajout au cache : {e}")
    
    await ctx.send(
        f"✅ **{streamer}** ajouté ! Il apparaîtra dans Discord s'il passe en ligne.\n"
        f"💡 Il sera miné automatiquement au prochain redémarrage (déjà en cache).",
        delete_after=15
    )

@bot.command(name='refreshcache')
async def refresh_cache_command(ctx):
    """Force le rechargement du cache des followers au prochain redémarrage"""
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    try:
        from pathlib import Path
        cache_file = get_cache_file_path()
        
        if cache_file.exists():
            cache_file.unlink()
            await ctx.send(
                "✅ **Cache supprimé !**\n"
                "Au prochain redémarrage, le bot rechargera tous vos follows Twitch.\n"
                "⚠️ Cela prendra ~6 minutes avec 465 followers.",
                delete_after=20
            )
            print("🗑️ Cache des followers supprimé (sera rechargé au prochain démarrage)")
        else:
            await ctx.send("⚠️ Aucun cache trouvé.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Erreur : {e}", delete_after=10)
        print(f"❌ Erreur suppression cache : {e}")

@bot.command(name='cleanup')
async def cleanup_inactive(ctx, days: int = 30, mode: str = "safe"):
    """🧹 Analyse et supprime les streamers inactifs depuis X jours
    
    Usage:
        !cleanup           - Mode SAFE: supprime seulement les jamais vus (rapide)
        !cleanup 60        - Analyse les streamers inactifs depuis 60 jours
        !cleanup 30 full   - Mode FULL: vérifie l'activité réelle sur Twitch (LENT, 465 requêtes)
    
    Modes:
        safe (défaut) - Supprime SEULEMENT les streamers jamais vus (0 points)
        full          - Vérifie l'activité RÉELLE sur Twitch (dernier stream)
    """
    # Supprimer la commande
    try:
        await ctx.message.delete()
    except:
        pass
    
    # Validation
    if days < 7:
        await ctx.send("⚠️ Minimum 7 jours requis (pour éviter les erreurs)", delete_after=10)
        return
    
    if days > 365:
        await ctx.send("⚠️ Maximum 365 jours", delete_after=10)
        return
    
    # Message de chargement
    loading_msg = await ctx.send("🔍 Analyse des streamers inactifs en cours...")
    
    try:
        load_data(force=True)
        
        # Message de progression
        await loading_msg.edit(content="🔍 Vérification de l'activité réelle sur Twitch API...")
        
        # Calculer la date limite
        import time
        cutoff_timestamp = time.time() - (days * 86400)  # X jours en secondes
        
        # Analyser les streamers en vérifiant leur VRAIE activité sur Twitch
        inactive_streamers = []
        active_streamers = []
        never_seen = []
        truly_inactive = []
        
        # Vérifier l'activité via l'API Twitch publique
        checked = 0
        total = len(streamer_data)
        
        for streamer, data in streamer_data.items():
            checked += 1
            if checked % 50 == 0:
                await loading_msg.edit(content=f"🔍 Analyse en cours... {checked}/{total} streamers vérifiés")
            
            # D'abord regarder les données locales
            balance = data.get('balance', 0)
            session_points = data.get('session_points', 0)
            is_online_now = data.get('online', False)
            
            # Si le streamer est online maintenant, il est actif
            if is_online_now:
                active_streamers.append(streamer)
                continue
            
            # Si jamais vu (0 points)
            if balance == 0 and session_points == 0:
                never_seen.append(streamer)
                continue
            
            # Pour les autres, vérifier selon le mode
            if mode.lower() == "full":
                # Mode FULL: vérifier l'activité réelle sur Twitch (sera fait en batch après)
                inactive_streamers.append(streamer)
            else:
                # Mode SAFE: juste marquer comme potentiellement inactif
                inactive_streamers.append(streamer)
        
        # Si mode FULL, vérifier l'activité réelle en batch via API Helix
        if mode.lower() == "full" and inactive_streamers:
            await loading_msg.edit(content=f"🔍 Vérification de l'activité réelle via API Helix (batch)... {len(inactive_streamers)} streamers à vérifier")
            last_stream_dates = await get_last_stream_dates_batch(inactive_streamers)
            
            # Réorganiser les listes selon les résultats
            truly_inactive = []
            newly_active = []
            still_inactive = []
            
            for streamer in inactive_streamers:
                streamer_lower = streamer.lower()
                stream_info = last_stream_dates.get(streamer_lower, {})
                days_ago = stream_info.get('days_ago')
                
                if days_ago is not None:
                    if days_ago > days:
                        # N'a pas stream depuis X jours → vraiment inactif
                        truly_inactive.append((streamer, days_ago))
                    else:
                        # A stream récemment → actif
                        newly_active.append(streamer)
                        active_streamers.append(streamer)
                else:
                    # Pas d'info de dernier stream → potentiellement inactif
                    still_inactive.append(streamer)
            
            inactive_streamers = still_inactive
        
        # Créer l'embed de résultats
        embed = discord.Embed(
            title=f"🧹 Analyse des Streamers Inactifs ({days} jours)",
            description=f"Analyse de **{len(streamer_data)}** streamers suivis",
            color=0xFF6B6B
        )
        
        # Streamers jamais vus en ligne
        if never_seen:
            never_seen_list = never_seen[:20]  # Limiter à 20 pour l'affichage
            embed.add_field(
                name=f"❌ Jamais vus en ligne ({len(never_seen)} streamers)",
                value=f"```{', '.join(never_seen_list)}{' ...' if len(never_seen) > 20 else ''}```",
                inline=False
            )
        
        # Streamers vraiment inactifs (mode FULL uniquement)
        if truly_inactive:
            inactive_list_full = [f"{s} ({d}j)" for s, d in sorted(truly_inactive, key=lambda x: x[1], reverse=True)[:20]]
            embed.add_field(
                name=f"🔴 Vraiment inactifs ({len(truly_inactive)} streamers)",
                value=f"```{', '.join(inactive_list_full)}{' ...' if len(truly_inactive) > 20 else ''}```"
                      f"\n⚠️ N'ont PAS stream depuis plus de {days} jours (vérifié sur Twitch)",
                inline=False
            )
        
        # Streamers potentiellement inactifs
        if inactive_streamers:
            inactive_list = inactive_streamers[:20]
            mode_text = "offline actuellement" if mode.lower() == "safe" else "sans info de dernier stream"
            embed.add_field(
                name=f"⚠️ Offline / Inconnus ({len(inactive_streamers)} streamers)",
                value=f"```{', '.join(inactive_list)}{' ...' if len(inactive_streamers) > 20 else ''}```"
                      f"\n💡 Mode SAFE: sont conservés (peuvent avoir stream récemment)\n"
                      f"💡 Utilisez `!cleanup {days} full` pour vérifier leur vraie activité",
                inline=False
            )
        
        # Streamers actifs
        embed.add_field(
            name=f"✅ Streamers actifs",
            value=f"**{len(active_streamers)}** streamers en ligne ou récemment actifs",
            inline=False
        )
        
        # En mode FULL, cleanup jamais vus + vraiment inactifs
        # En mode SAFE, cleanup seulement jamais vus
        if mode.lower() == "full":
            total_to_cleanup = len(never_seen) + len(truly_inactive)
            to_cleanup_list = never_seen + [s for s, _ in truly_inactive]
        else:
            total_to_cleanup = len(never_seen)
            to_cleanup_list = never_seen
        
        if total_to_cleanup == 0:
            embed.add_field(
                name="🎉 Résultat",
                value=f"Aucun streamer jamais vu détecté !\n"
                      f"💡 Utilisez `!cleanup force` pour aussi supprimer les {len(inactive_streamers)} offline.",
                inline=False
            )
            embed.color = 0x57F287
            await loading_msg.delete()
            await ctx.send(embed=embed, delete_after=30)
            return
        
        # Calculer l'économie
        estimated_time_saved = (total_to_cleanup * 0.77)  # ~0.77s par streamer
        embed.add_field(
            name="💡 Économie estimée",
            value=f"Suppression de **{total_to_cleanup}** streamers jamais vus = **-{estimated_time_saved:.1f}s** au redémarrage",
            inline=False
        )
        
        if mode.lower() == "full":
            embed.add_field(
                name="ℹ️ Mode FULL activé",
                value=f"Suppression: **{len(never_seen)} jamais vus** + **{len(truly_inactive)} vraiment inactifs**\n"
                      f"Conservés: **{len(inactive_streamers)} sans info** + **{len(active_streamers)} actifs**",
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Mode SAFE activé",
                value=f"Suppression: **{len(never_seen)} jamais vus** uniquement\n"
                      f"Conservés: **{len(inactive_streamers)} offline** (juliettearz, gotaga...) + **{len(active_streamers)} actifs**\n"
                      f"💡 Pour vérifier l'activité réelle: `!cleanup {days} full`",
                inline=False
            )
        
        embed.set_footer(text="⚠️ Réagissez avec ✅ pour confirmer la suppression (30s)")
        
        await loading_msg.delete()
        confirm_msg = await ctx.send(embed=embed)
        
        # Ajouter la réaction
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        # Attendre la confirmation
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
        
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await confirm_msg.delete()
                await ctx.send("❌ Nettoyage annulé.", delete_after=5)
                return
            
            # Confirmation reçue, procéder au nettoyage
            await confirm_msg.delete()
            progress_msg = await ctx.send("🧹 Nettoyage en cours...")
            
            # Utiliser la liste déterminée plus haut
            to_remove = to_cleanup_list
            
            # Ajouter à la blacklist (plus simple que d'unfollow via API)
            blacklist_file = Path("blacklist.json")
            if blacklist_file.exists():
                with open(blacklist_file, 'r') as f:
                    blacklist = json.load(f)
            else:
                blacklist = []
            
            # Ajouter les streamers inactifs à la blacklist
            added_count = 0
            for streamer in to_remove:
                if streamer not in blacklist:
                    blacklist.append(streamer)
                    added_count += 1
            
            # Sauvegarder la blacklist
            with open(blacklist_file, 'w') as f:
                json.dump(blacklist, f, indent=2)
            
            # Supprimer du cache des followers
            cache_file = get_cache_file_path()
            removed_from_cache = 0
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                original_count = len(cache_data.get('followers', []))
                cache_data['followers'] = [
                    f for f in cache_data.get('followers', []) 
                    if f not in to_remove
                ]
                removed_from_cache = original_count - len(cache_data['followers'])
                cache_data['count'] = len(cache_data['followers'])
                
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
            
            # Supprimer des données du bot
            for streamer in to_remove:
                if streamer in streamer_data:
                    del streamer_data[streamer]
            save_data()
            
            await progress_msg.delete()
            
            # Message de succès
            success_embed = discord.Embed(
                title="✅ Nettoyage Terminé !",
                description=f"**{added_count}** streamers ajoutés à la blacklist",
                color=0x57F287
            )
            
            success_embed.add_field(
                name="📊 Résultats",
                value=f"• Blacklist: +{added_count} streamers\n"
                      f"• Cache: -{removed_from_cache} followers\n"
                      f"• Gain: ~{estimated_time_saved:.1f}s au redémarrage",
                inline=False
            )
            
            success_embed.add_field(
                name="💡 Prochaines étapes",
                value="Les streamers blacklistés ne seront plus minés.\n"
                      "Utilisez `!list` pour voir la blacklist complète.\n"
                      "Utilisez `!unblacklist <nom>` pour restaurer un streamer.",
                inline=False
            )
            
            success_embed.set_footer(text=f"Streamers restants: {len(streamer_data)}")
            
            await ctx.send(embed=success_embed, delete_after=60)
            
            print(f"🧹 Cleanup: {added_count} streamers inactifs blacklistés")
            print(f"💾 Cache: {removed_from_cache} followers supprimés")
            
        except asyncio.TimeoutError:
            try:
                await confirm_msg.delete()
            except:
                pass
            await ctx.send("⏱️ Temps écoulé. Nettoyage annulé.", delete_after=5)
    
    except Exception as e:
        try:
            await loading_msg.delete()
        except:
            pass
        await ctx.send(f"❌ Erreur: {e}", delete_after=15)
        print(f"❌ Erreur cleanup: {e}")
        import traceback
        traceback.print_exc()

@bot.command(name='help')
async def help_command(ctx):
    """Affiche l'aide"""
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    embed = discord.Embed(
        title="📖 Commandes Disponibles",
        description="Commandes pour gérer le bot Twitch Miner",
        color=0x5865F2
    )
    
    embed.add_field(
        name="!status",
        value="Affiche l'état général du bot",
        inline=False
    )
    
    embed.add_field(
        name="!status <streamer>",
        value="Affiche la fiche d'un streamer\nEx: `!status jltomy`",
        inline=False
    )
    
    embed.add_field(
        name="🚫 Mode FOLLOWERS",
        value="Le bot mine automatiquement TOUS vos follows Twitch",
        inline=False
    )
    
    embed.add_field(
        name="!blacklist <streamer>",
        value="Exclut un streamer du mining\nEx: `!blacklist xqc`",
        inline=False
    )
    
    embed.add_field(
        name="!unblacklist <streamer>",
        value="Réactive un streamer blacklisté\nEx: `!unblacklist xqc`",
        inline=False
    )
    
    embed.add_field(
        name="!list",
        value="Affiche les streamers blacklistés",
        inline=False
    )
    
    embed.add_field(
        name="!addfollow <streamer>",
        value="⚡ Ajoute un nouveau follow SANS redémarrer\nEx: `!addfollow shroud`",
        inline=False
    )
    
    embed.add_field(
        name="!refreshcache",
        value="Force le rechargement des follows au prochain redémarrage",
        inline=False
    )
    
    embed.add_field(
        name="!cleanup [jours]",
        value="🧹 Supprime les streamers inactifs\nEx: `!cleanup` ou `!cleanup 60`",
        inline=False
    )
    
    embed.add_field(
        name="!refresh",
        value="Force la mise à jour des salons Discord",
        inline=False
    )
    
    embed.add_field(
        name="!reset",
        value="Supprime tous les salons streamers",
        inline=False
    )
    
    embed.add_field(
        name="!help",
        value="Affiche cette aide",
        inline=False
    )
    
    embed.set_footer(text="⚡ Cache des followers : redémarrage INSTANTANÉ (pas de rechargement 6min) • Salons auto-update 30s")
    
    await ctx.send(embed=embed, delete_after=60)

def main():
    if not BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN non défini !")
        print("Créez un bot sur https://discord.com/developers/applications")
        return
    
    if not CATEGORY_ID or CATEGORY_ID == 0:
        print("⚠️  DISCORD_CATEGORY_ID non défini !")
        print("Créez une catégorie Discord et ajoutez son ID dans les variables d'environnement")
        print("Le bot ne pourra pas créer de salons streamers")
    
    if not CHANNEL_ID or CHANNEL_ID == 0:
        print("⚠️  DISCORD_CHANNEL_ID non défini - les commandes devront être utilisées dans n'importe quel canal")
    
    print("🚀 Démarrage du bot Discord...")
    bot.run(BOT_TOKEN)

if __name__ == "__main__":
    main()
