#!/usr/bin/env python3
"""
Launcher pour Railway - Lance le Bot Discord et le Miner ensemble
"""

import subprocess
import sys
import time
import os
from threading import Thread

def run_discord_bot():
    """Lance le bot Discord"""
    print("🤖 Démarrage du Bot Discord...")
    try:
        subprocess.run([sys.executable, "discord_bot.py"], check=True)
    except KeyboardInterrupt:
        print("🛑 Bot Discord arrêté")
    except Exception as e:
        print(f"❌ Erreur Bot Discord: {e}")

def run_miner():
    """Lance le miner Twitch"""
    print("⛏️  Démarrage du Miner...")
    time.sleep(3)  # Attendre que le bot Discord soit prêt
    try:
        subprocess.run([sys.executable, "run.py"], check=True)
    except KeyboardInterrupt:
        print("🛑 Miner arrêté")
    except Exception as e:
        print(f"❌ Erreur Miner: {e}")

def main():
    print("=" * 50)
    print("🚀 LAUNCHER - Twitch Miner + Bot Discord")
    print("=" * 50)
    
    # Vérifier les variables d'environnement
    required_vars = {
        "DISCORD_BOT_TOKEN": "Token du bot Discord",
        "DISCORD_CHANNEL_ID": "ID du canal Discord",
        "TWITCH_USERNAME": "Username Twitch",
        "TWITCH_AUTH_TOKEN": "Token d'authentification Twitch"
    }
    
    missing = []
    for var, desc in required_vars.items():
        if not os.getenv(var):
            missing.append(f"  ❌ {var} ({desc})")
    
    if missing:
        print("\n⚠️  Variables d'environnement manquantes:")
        for m in missing:
            print(m)
        print("\nConfigurez-les dans Railway Settings → Variables")
        sys.exit(1)
    
    print("\n✅ Toutes les variables sont configurées")
    print(f"✅ Bot Discord: Canal {os.getenv('DISCORD_CHANNEL_ID')}")
    print(f"✅ Twitch: {os.getenv('TWITCH_USERNAME')}")
    print(f"✅ Mode Bot Discord: {os.getenv('USE_DISCORD_BOT', 'true')}")
    print()
    
    # Lancer les deux processus en parallèle
    discord_thread = Thread(target=run_discord_bot, daemon=True)
    miner_thread = Thread(target=run_miner, daemon=True)
    
    discord_thread.start()
    miner_thread.start()
    
    print("🔄 Les deux bots sont lancés en parallèle")
    print("📊 Surveillez les logs ci-dessous...")
    print("=" * 50)
    print()
    
    # Attendre que les threads se terminent
    try:
        discord_thread.join()
        miner_thread.join()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé...")
        sys.exit(0)

if __name__ == "__main__":
    main()

