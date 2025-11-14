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
    print("📍 Vérification du token...")
    
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ DISCORD_BOT_TOKEN manquant !")
        return
    
    print(f"✅ Token présent (longueur: {len(token)})")
    
    try:
        import sys
        import subprocess
        
        # Lancer avec sortie en temps réel
        process = subprocess.Popen(
            [sys.executable, "-u", "discord_bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Afficher les logs en temps réel
        for line in process.stdout:
            print(f"[BOT] {line.rstrip()}")
        
        process.wait()
        
    except KeyboardInterrupt:
        print("🛑 Bot Discord arrêté")
    except Exception as e:
        print(f"❌ Erreur Bot Discord: {e}")
        import traceback
        traceback.print_exc()

def run_miner():
    """Lance le miner Twitch"""
    print("⛏️  Démarrage du Miner...")
    time.sleep(5)  # Attendre que le bot Discord soit connecté
    
    try:
        # Lancer avec sortie en temps réel
        process = subprocess.Popen(
            [sys.executable, "-u", "run.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Afficher les logs en temps réel
        for line in process.stdout:
            print(f"[MINER] {line.rstrip()}")
        
        process.wait()
        
    except KeyboardInterrupt:
        print("🛑 Miner arrêté")
    except Exception as e:
        print(f"❌ Erreur Miner: {e}")
        import traceback
        traceback.print_exc()

def main():
    # Forcer unbuffered pour Railway
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    print("=" * 50, flush=True)
    print("🚀 LAUNCHER - Twitch Miner + Bot Discord", flush=True)
    print("=" * 50, flush=True)
    
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
        print("\n⚠️  Variables d'environnement manquantes:", flush=True)
        for m in missing:
            print(m, flush=True)
        print("\nConfigurez-les dans Railway Settings → Variables", flush=True)
        sys.exit(1)
    
    print("\n✅ Toutes les variables sont configurées", flush=True)
    print(f"✅ Bot Discord: Canal {os.getenv('DISCORD_CHANNEL_ID')}", flush=True)
    print(f"✅ Twitch: {os.getenv('TWITCH_USERNAME')}", flush=True)
    print(f"✅ Mode Bot Discord: {os.getenv('USE_DISCORD_BOT', 'true')}", flush=True)
    print(flush=True)
    
    # Lancer les deux processus en parallèle
    discord_thread = Thread(target=run_discord_bot, daemon=True, name="Discord-Bot")
    miner_thread = Thread(target=run_miner, daemon=True, name="Twitch-Miner")
    
    discord_thread.start()
    miner_thread.start()
    
    print("🔄 Les deux bots sont lancés en parallèle", flush=True)
    print("📊 Surveillez les logs ci-dessous...", flush=True)
    print("=" * 50, flush=True)
    print(flush=True)
    
    # Attendre que les threads se terminent
    try:
        discord_thread.join()
        miner_thread.join()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé...", flush=True)
        sys.exit(0)

if __name__ == "__main__":
    main()

