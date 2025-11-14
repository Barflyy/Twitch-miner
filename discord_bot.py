#!/usr/bin/env python3
# discord_bot.py - Bot Discord pour contrôler et monitorer le Twitch Miner

import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))  # Canal pour les commandes
CATEGORY_ID = int(os.getenv("DISCORD_CATEGORY_ID", "0"))  # Catégorie pour les salons streamers
DATA_FILE = "bot_data.json"

# Intents (avec message_content + guilds pour gérer les salons)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Stockage des salons et messages
streamer_channels = {}  # {streamer: channel_id}
streamer_messages = {}  # {streamer: message_id} (message dans le salon)
streamer_data = {}   # {streamer: {stats}}

def load_data():
    """Charge les données depuis le fichier JSON"""
    global streamer_data
    try:
        if Path(DATA_FILE).exists():
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                streamer_data = data.get('streamers', {})
    except Exception as e:
        print(f"❌ Erreur chargement data: {e}")
        streamer_data = {}

def save_channels():
    """Sauvegarde les IDs des salons streamers"""
    try:
        data = {
            'channels': streamer_channels,
            'messages': streamer_messages
        }
        with open('streamer_channels.json', 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ Erreur sauvegarde channels: {e}")

def load_channels():
    """Charge les IDs des salons streamers"""
    global streamer_channels, streamer_messages
    try:
        if Path('streamer_channels.json').exists():
            with open('streamer_channels.json', 'r') as f:
                data = json.load(f)
                streamer_channels = data.get('channels', {})
                streamer_messages = data.get('messages', {})
    except Exception as e:
        print(f"❌ Erreur chargement channels: {e}")
        streamer_channels = {}
        streamer_messages = {}

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
    
    embed = discord.Embed(
        title=f"{status_emoji} {streamer.upper()}",
        description=f"**Statut:** {status_text}",
        color=color,
        timestamp=datetime.utcnow()
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

@bot.event
async def on_ready():
    print(f'✅ Bot connecté: {bot.user.name}')
    print(f'📋 ID: {bot.user.id}')
    
    # Vérifier qu'on a une catégorie définie
    if not CATEGORY_ID or CATEGORY_ID == 0:
        print("[BOT] ⚠️ DISCORD_CATEGORY_ID non défini !")
        print("[BOT] Le bot fonctionne sans salons automatiques")
        print("[BOT] Ajoutez DISCORD_CATEGORY_ID pour activer le système de salons streamers")
        print("[BOT] Pour l'instant, utilisez les commandes !status, !add, !list, etc.")
        # Ne pas bloquer le démarrage, le bot reste fonctionnel pour les commandes
        return
    
    # Charger les données
    load_channels()
    load_data()
    
    # Démarrer la boucle de mise à jour
    if not update_channels.is_running():
        update_channels.start()
    
    print("🔄 Mise à jour automatique activée (30 secondes)")
    
    # Créer/mettre à jour les salons immédiatement
    print("📊 Création/mise à jour des salons streamers...")
    await asyncio.sleep(2)  # Attendre un peu que les données soient prêtes
    await update_channels()
    print("✅ Salons streamers créés/mis à jour")

@tasks.loop(seconds=30)
async def update_channels():
    """Met à jour les salons streamers selon leur statut"""
    if not CATEGORY_ID or CATEGORY_ID == 0:
        return
    
    try:
        category = bot.get_channel(CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            print(f"❌ Catégorie {CATEGORY_ID} introuvable ou invalide")
            return
        
        guild = category.guild
        
        # Recharger les données
        load_data()
        
        # Pour chaque streamer dans les données
        for streamer, data in streamer_data.items():
            is_online = data.get('online', False)
            status_emoji = "🟢" if is_online else "🔴"
            channel_name = f"{status_emoji}-{streamer.lower()}"
            
            # Si le salon existe déjà
            if streamer in streamer_channels:
                channel_id = streamer_channels[streamer]
                channel = guild.get_channel(channel_id)
                
                if channel:
                    # Mettre à jour le nom si le statut a changé
                    if channel.name != channel_name:
                        await channel.edit(name=channel_name)
                        print(f"🔄 Salon renommé: {channel_name}")
                    
                    # Mettre à jour le message dans le salon
                    embed = create_streamer_embed(streamer)
                    
                    if streamer in streamer_messages:
                        try:
                            message = await channel.fetch_message(streamer_messages[streamer])
                            await message.edit(embed=embed)
                        except discord.NotFound:
                            # Message supprimé, en créer un nouveau
                            message = await channel.send(embed=embed)
                            streamer_messages[streamer] = message.id
                            save_channels()
                    else:
                        # Créer le message initial
                        message = await channel.send(embed=embed)
                        streamer_messages[streamer] = message.id
                        save_channels()
                else:
                    # Le salon a été supprimé, le recréer
                    print(f"🔄 Recréation du salon: {channel_name}")
                    channel = await guild.create_text_channel(
                        name=channel_name,
                        category=category
                    )
                    streamer_channels[streamer] = channel.id
                    
                    # Créer le message initial
                    embed = create_streamer_embed(streamer)
                    message = await channel.send(embed=embed)
                    streamer_messages[streamer] = message.id
                    save_channels()
            
            else:
                # Créer un nouveau salon pour ce streamer
                print(f"✅ Création du salon: {channel_name}")
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category
                )
                streamer_channels[streamer] = channel.id
                
                # Créer le message initial
                embed = create_streamer_embed(streamer)
                message = await channel.send(embed=embed)
                streamer_messages[streamer] = message.id
                save_channels()
        
        # Supprimer les salons des streamers qui ne sont plus dans la liste
        for streamer in list(streamer_channels.keys()):
            if streamer not in streamer_data:
                channel_id = streamer_channels[streamer]
                channel = guild.get_channel(channel_id)
                if channel:
                    await channel.delete()
                    print(f"🗑️  Salon supprimé: {streamer}")
                
                del streamer_channels[streamer]
                if streamer in streamer_messages:
                    del streamer_messages[streamer]
                save_channels()
    
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
    
    load_data()
    await update_channels()
    
    await msg.edit(content=f"✅ Salons mis à jour ! ({len(streamer_data)} streamers)")
    await msg.delete(delay=5)

@bot.command(name='reset')
async def reset_channels(ctx):
    """Supprime tous les salons streamers et réinitialise"""
    global streamer_channels, streamer_messages
    
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
        for streamer, channel_id in list(streamer_channels.items()):
            channel = guild.get_channel(channel_id)
            if channel:
                await channel.delete()
                print(f"🗑️  Salon supprimé: {streamer}")
        
        streamer_channels = {}
        streamer_messages = {}
        save_channels()
        
        await msg.edit(content="✅ Tous les salons ont été supprimés ! Utilisez `!refresh` pour les recréer.")
    else:
        await msg.edit(content="❌ Catégorie introuvable !")
    
    await msg.delete(delay=5)

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
    
    load_data()
    
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
        
        # Liste des streamers
        if streamer_data:
            streamers_list = []
            for name, data in streamer_data.items():
                status_emoji = "🟢" if data.get('online', False) else "🔴"
                streamers_list.append(f"{status_emoji} {name}")
            
            embed.add_field(
                name="📋 Streamers suivis",
                value="\n".join(streamers_list) if streamers_list else "Aucun",
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
        name="!refresh",
        value="Force la mise à jour des salons",
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
    
    embed.set_footer(text="💡 Salons auto-update 30s • 🟢 = Online • 🔴 = Offline")
    
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
