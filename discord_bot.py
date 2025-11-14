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
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
DATA_FILE = "bot_data.json"

# Intents (avec message_content pour les commandes)
intents = discord.Intents.default()
intents.message_content = True  # Nécessaire pour !status, !refresh, etc.

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Stockage des message IDs pour les fiches
streamer_cards = {}  # {streamer: message_id}
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

def save_cards():
    """Sauvegarde les message IDs des fiches"""
    try:
        with open('streamer_cards.json', 'w') as f:
            json.dump(streamer_cards, f)
    except Exception as e:
        print(f"❌ Erreur sauvegarde cards: {e}")

def load_cards():
    """Charge les message IDs des fiches"""
    global streamer_cards
    try:
        if Path('streamer_cards.json').exists():
            with open('streamer_cards.json', 'r') as f:
                streamer_cards = json.load(f)
    except Exception as e:
        print(f"❌ Erreur chargement cards: {e}")
        streamer_cards = {}

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
    
    # Points totaux gagnés depuis le début
    total_earned = data.get('total_earned', 0)
    starting_balance = data.get('starting_balance', 0)
    
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
    
    # Solde avec gains totaux depuis le début
    solde_text = f"**{balance_display}** points"
    if total_earned > 0:
        solde_text += f"\n🔼 **+{total_earned:,}** gagnés au total".replace(',', ' ')
    
    embed.add_field(
        name="💎 Solde",
        value=solde_text,
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
    
    # Charger les données
    load_cards()
    load_data()
    
    # Démarrer la boucle de mise à jour
    if not update_cards.is_running():
        update_cards.start()
    
    print("🔄 Mise à jour automatique activée (30 secondes)")
    
    # Afficher les fiches immédiatement au démarrage
    if CHANNEL_ID and CHANNEL_ID != 0:
        print("📊 Création des fiches initiales...")
        await asyncio.sleep(2)  # Attendre un peu que les données soient prêtes
        await update_cards()  # Forcer une mise à jour immédiate
        print("✅ Fiches initiales créées")

@tasks.loop(seconds=30)
async def update_cards():
    """Met à jour les fiches streamers toutes les 30 secondes"""
    if not CHANNEL_ID or CHANNEL_ID == 0:
        return
    
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            return
        
        # Recharger les données
        load_data()
        
        # Pour chaque streamer dans les données
        for streamer in streamer_data.keys():
            embed = create_streamer_embed(streamer)
            
            # Si la fiche existe, la mettre à jour
            if streamer in streamer_cards:
                try:
                    message = await channel.fetch_message(streamer_cards[streamer])
                    await message.edit(embed=embed)
                except discord.NotFound:
                    # Message supprimé, en créer un nouveau
                    message = await channel.send(embed=embed)
                    streamer_cards[streamer] = message.id
                    save_cards()
                except Exception as e:
                    print(f"❌ Erreur update {streamer}: {e}")
            else:
                # Créer une nouvelle fiche
                message = await channel.send(embed=embed)
                streamer_cards[streamer] = message.id
                save_cards()
    
    except Exception as e:
        print(f"❌ Erreur update_cards: {e}")

@update_cards.before_loop
async def before_update_cards():
    await bot.wait_until_ready()

@bot.command(name='refresh')
async def refresh_cards(ctx):
    """Force la mise à jour des fiches"""
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    await ctx.send("🔄 Mise à jour forcée...")
    
    load_data()
    
    for streamer in streamer_data.keys():
        embed = create_streamer_embed(streamer)
        
        if streamer in streamer_cards:
            try:
                message = await ctx.channel.fetch_message(streamer_cards[streamer])
                await message.edit(embed=embed)
            except discord.NotFound:
                message = await ctx.send(embed=embed)
                streamer_cards[streamer] = message.id
                save_cards()
        else:
            message = await ctx.send(embed=embed)
            streamer_cards[streamer] = message.id
            save_cards()
    
    await ctx.send("✅ Fiches mises à jour !")

@bot.command(name='reset')
async def reset_cards(ctx):
    """Réinitialise toutes les fiches"""
    # Supprimer la commande de l'utilisateur
    try:
        await ctx.message.delete()
    except:
        pass
    
    global streamer_cards
    streamer_cards = {}
    save_cards()
    await ctx.send("✅ Fiches réinitialisées ! Utilisez `!refresh` pour les recréer.")

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
            await ctx.send(f"❌ Streamer `{streamer}` non trouvé. Streamers disponibles: {', '.join(streamer_data.keys())}")
            return
        
        # Créer un embed pour ce streamer
        embed = create_streamer_embed(streamer_lower)
        await ctx.send(embed=embed)
    
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
        embed.add_field(name="📋 Fiches actives", value=str(len(streamer_cards)), inline=True)
        
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
        
        await ctx.send(embed=embed)

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
        value="Affiche l'état général du bot (🟢 on/off, streamers suivis)",
        inline=False
    )
    
    embed.add_field(
        name="!status <streamer>",
        value="Affiche la fiche détaillée d'un streamer\nExemple: `!status jltomy`",
        inline=False
    )
    
    embed.add_field(
        name="!refresh",
        value="Force la mise à jour immédiate de toutes les fiches",
        inline=False
    )
    
    embed.add_field(
        name="!reset",
        value="Réinitialise les fiches (supprime et recrée les messages)",
        inline=False
    )
    
    embed.add_field(
        name="!help",
        value="Affiche cette aide",
        inline=False
    )
    
    embed.set_footer(text="💡 Les fiches se mettent à jour automatiquement toutes les 30 secondes")
    
    await ctx.send(embed=embed)

def main():
    if not BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN non défini !")
        print("Créez un bot sur https://discord.com/developers/applications")
        return
    
    if not CHANNEL_ID or CHANNEL_ID == 0:
        print("⚠️  DISCORD_CHANNEL_ID non défini - les fiches auto ne fonctionneront pas")
        print("Utilisez !refresh dans un canal pour créer les fiches manuellement")
    
    print("🚀 Démarrage du bot Discord...")
    bot.run(BOT_TOKEN)

if __name__ == "__main__":
    main()

