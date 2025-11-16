#!/usr/bin/env python3
"""
setup_discord_logs.py - Configure Discord webhooks pour les logs

Ce script crée automatiquement:
1. Une catégorie "📊 Administration"
2. Trois salons textuels: #errors, #warnings, #infos
3. Des webhooks pour chaque salon
4. Affiche les variables d'environnement à ajouter
"""

import discord
import asyncio
import os
import sys


async def setup_discord_log_channels():
    """Configure les salons Discord pour les logs."""

    # Récupère le token du bot
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ DISCORD_BOT_TOKEN non défini !")
        print("Définissez-le avec : export DISCORD_BOT_TOKEN='votre_token'")
        sys.exit(1)

    # ID du serveur Discord
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if not guild_id:
        print("❌ DISCORD_GUILD_ID non défini !")
        print("Pour obtenir l'ID de votre serveur:")
        print("1. Activez le mode développeur dans Discord (Paramètres > Avancés)")
        print("2. Clic droit sur votre serveur > Copier l'identifiant")
        print("3. export DISCORD_GUILD_ID='votre_id'")
        sys.exit(1)

    guild_id = int(guild_id)

    # Crée le client Discord
    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"✅ Connecté en tant que {client.user}")

        # Récupère le serveur
        guild = client.get_guild(guild_id)
        if not guild:
            print(f"❌ Serveur {guild_id} non trouvé !")
            await client.close()
            return

        print(f"✅ Serveur trouvé : {guild.name}")

        # Cherche ou crée la catégorie "Administration"
        category = None
        for cat in guild.categories:
            if cat.name.lower() in ["administration", "📊 administration", "admin"]:
                category = cat
                print(f"✅ Catégorie existante trouvée : {cat.name}")
                break

        if not category:
            print("📁 Création de la catégorie '📊 Administration'...")
            category = await guild.create_category("📊 Administration")
            print(f"✅ Catégorie créée : {category.name}")

        # Configuration des salons
        channels_config = [
            {
                "name": "🔴-errors",
                "topic": "Logs d'erreurs critiques du Twitch Miner",
                "env_var": "DISCORD_ERROR_WEBHOOK"
            },
            {
                "name": "⚠️-warnings",
                "topic": "Logs d'avertissements du Twitch Miner",
                "env_var": "DISCORD_WARNING_WEBHOOK"
            },
            {
                "name": "ℹ️-infos",
                "topic": "Logs d'informations du Twitch Miner",
                "env_var": "DISCORD_INFO_WEBHOOK"
            }
        ]

        webhooks = {}

        for config in channels_config:
            channel_name = config["name"]
            topic = config["topic"]
            env_var = config["env_var"]

            # Cherche si le salon existe déjà
            channel = discord.utils.get(category.channels, name=channel_name)

            if not channel:
                print(f"📝 Création du salon {channel_name}...")
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    topic=topic
                )
                print(f"✅ Salon créé : {channel.name}")
            else:
                print(f"✅ Salon existant : {channel.name}")

            # Cherche ou crée le webhook
            existing_webhooks = await channel.webhooks()
            webhook = None

            for wh in existing_webhooks:
                if wh.name == "Twitch Miner Logs":
                    webhook = wh
                    print(f"✅ Webhook existant trouvé pour {channel.name}")
                    break

            if not webhook:
                print(f"🔗 Création du webhook pour {channel.name}...")
                webhook = await channel.create_webhook(
                    name="Twitch Miner Logs",
                    reason="Logs automatiques du Twitch Miner"
                )
                print(f"✅ Webhook créé pour {channel.name}")

            webhooks[env_var] = webhook.url

        # Affiche les variables d'environnement
        print("\n" + "=" * 60)
        print("🎉 CONFIGURATION TERMINÉE !")
        print("=" * 60)
        print("\n📋 Ajoutez ces variables d'environnement à votre système :\n")

        print("# Pour Railway/Fly.io (dans les variables d'environnement):")
        for env_var, url in webhooks.items():
            print(f"{env_var}={url}")

        print("\n# Pour .env local:")
        for env_var, url in webhooks.items():
            print(f"{env_var}=\"{url}\"")

        print("\n# Pour export direct (terminal):")
        for env_var, url in webhooks.items():
            print(f"export {env_var}=\"{url}\"")

        print("\n" + "=" * 60)
        print("📌 Configuration automatique dans run.py")
        print("=" * 60)
        print("\nLes logs seront automatiquement envoyés vers Discord")
        print("dès que les variables d'environnement seront définies.\n")

        print("✅ Catégories créées :")
        print(f"   └─ 📊 {category.name}")
        for config in channels_config:
            print(f"      └─ {config['name']}")

        await client.close()

    try:
        await client.start(token)
    except Exception as e:
        print(f"❌ Erreur : {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🔧 Configuration des logs Discord pour Twitch Miner")
    print("=" * 60)
    asyncio.run(setup_discord_log_channels())
